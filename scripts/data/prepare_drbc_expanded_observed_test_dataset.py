#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pandas>=2.2",
#   "xarray>=2024.1",
#   "netcdf4>=1.7",
#   "py7zr>=0.22",
# ]
# ///
"""Prepare a test-only GenericDataset for the expanded observed DRBC split."""
from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd
import py7zr
import xarray as xr


TEST_START = pd.Timestamp("2014-01-01 00:00:00")
TEST_END = pd.Timestamp("2016-12-31 23:00:00")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("configs/basin_splits/drbc_expanded_observed_test/manifest.csv"),
    )
    parser.add_argument("--timeseries-archive", type=Path, default=Path("basins/CAMELSH_download/timeseries.7z"))
    parser.add_argument(
        "--timeseries-nonobs-archive",
        type=Path,
        default=Path("basins/CAMELSH_download/timeseries_nonobs.7z"),
    )
    parser.add_argument("--hourly2-zip", type=Path, default=Path("basins/CAMELSH_data/hourly_observed/Hourly2.zip"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/CAMELSH_generic/drbc_expanded_observed_test"),
    )
    parser.add_argument("--force", action="store_true", help="Rebuild files even when they already exist.")
    parser.add_argument("--limit-basins", type=int, default=None, help="Smoke-test only the first N selected basins.")
    return parser.parse_args()


def normalize_gauge_id(value: Any) -> str:
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(8)


def standardize_time_coord(ds: xr.Dataset) -> xr.Dataset:
    if "date" in ds.coords:
        return ds
    if "DateTime" in ds.coords or "DateTime" in ds.dims:
        return ds.rename({"DateTime": "date"})
    if "time" in ds.coords or "time" in ds.dims:
        return ds.rename({"time": "date"})
    raise ValueError("NetCDF dataset has no date, DateTime, or time coordinate.")


def read_hourly2_streamflow(zip_file: zipfile.ZipFile, member: str) -> xr.DataArray:
    with tempfile.NamedTemporaryFile(suffix=".nc") as tmp:
        tmp.write(zip_file.read(member))
        tmp.flush()
        ds = xr.open_dataset(tmp.name, engine="netcdf4")
        try:
            ds = standardize_time_coord(ds).load()
        finally:
            ds.close()
    if "streamflow" not in ds:
        raise ValueError(f"Hourly2 member has no streamflow variable: {member}")
    return ds["streamflow"].rename("Streamflow")


def open_forcing_dataset(path: Path) -> xr.Dataset:
    ds = xr.open_dataset(path, engine="netcdf4")
    try:
        ds = standardize_time_coord(ds).load()
    finally:
        ds.close()
    if "Streamflow" not in ds:
        ds["Streamflow"] = xr.full_like(ds[list(ds.data_vars)[0]], float("nan")).rename("Streamflow")
    return ds


def write_prepared_dataset(
    *,
    source_path: Path,
    row: pd.Series,
    hourly2_zip: zipfile.ZipFile,
    target_path: Path,
) -> dict[str, Any]:
    ds = open_forcing_dataset(source_path)
    try:
        if row["target_source_selected"] == "hourly2_streamflow":
            target = read_hourly2_streamflow(hourly2_zip, str(row["target_member_selected"]))
            if not target["date"].identical(ds["date"]):
                target = target.reindex(date=ds["date"])
            ds["Streamflow"] = target.astype("float64")
        elif row["target_source_selected"] != "timeseries_streamflow":
            raise ValueError(f"Unsupported target source: {row['target_source_selected']}")

        test_target = ds["Streamflow"].sel(date=slice(TEST_START, TEST_END))
        valid_count = int(test_target.notnull().sum().item())
        expected_count = int(pd.date_range(TEST_START, TEST_END, freq="h").size)
        coverage_fraction = valid_count / expected_count

        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target_path.with_suffix(".tmp.nc")
        tmp_path.unlink(missing_ok=True)
        ds.to_netcdf(tmp_path)
        tmp_path.replace(target_path)
        return {
            "actual_valid_target_count": valid_count,
            "expected_target_count": expected_count,
            "actual_coverage_fraction": coverage_fraction,
            "prepared_status": "prepared",
            "error": "",
        }
    except Exception as exc:
        target_path.unlink(missing_ok=True)
        return {
            "actual_valid_target_count": pd.NA,
            "expected_target_count": pd.NA,
            "actual_coverage_fraction": pd.NA,
            "prepared_status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        ds.close()


def build_static_attributes(output_dir: Path, basin_ids: set[str]) -> Path:
    attrs_dir = Path("basins/CAMELSH_data/attributes")
    basin_id = pd.read_csv(attrs_dir / "attributes_gageii_BasinID.csv", dtype={"STAID": str})[
        ["STAID", "DRAIN_SQKM", "HUC02", "STATE"]
    ].rename(columns={"STAID": "gauge_id", "DRAIN_SQKM": "area"})
    topo = pd.read_csv(attrs_dir / "attributes_gageii_Topo.csv", dtype={"STAID": str})[
        ["STAID", "SLOPE_PCT"]
    ].rename(columns={"STAID": "gauge_id", "SLOPE_PCT": "slope"})
    clim = pd.read_csv(attrs_dir / "attributes_nldas2_climate.csv", dtype={"STAID": str})[
        ["STAID", "aridity_index", "frac_snow"]
    ].rename(columns={"STAID": "gauge_id", "aridity_index": "aridity", "frac_snow": "snow_fraction"})
    soil = pd.read_csv(attrs_dir / "attributes_gageii_Soils.csv", dtype={"STAID": str})[
        ["STAID", "ROCKDEPAVE", "PERMAVE"]
    ].rename(columns={"STAID": "gauge_id", "ROCKDEPAVE": "soil_depth", "PERMAVE": "permeability"})
    hydro = pd.read_csv(attrs_dir / "attributes_gageii_Hydro.csv", dtype={"STAID": str})[
        ["STAID", "BFI_AVE"]
    ].rename(columns={"STAID": "gauge_id", "BFI_AVE": "baseflow_index"})
    lc = pd.read_csv(attrs_dir / "attributes_gageii_LC06_Basin.csv", dtype={"STAID": str})[
        ["STAID", "FORESTNLCD06"]
    ].rename(columns={"STAID": "gauge_id"})
    lc["forest_fraction"] = pd.to_numeric(lc["FORESTNLCD06"], errors="coerce") / 100.0
    lc = lc[["gauge_id", "forest_fraction"]]

    static_df = (
        basin_id.merge(topo, on="gauge_id")
        .merge(clim, on="gauge_id")
        .merge(soil, on="gauge_id")
        .merge(hydro, on="gauge_id")
        .merge(lc, on="gauge_id")
    )
    static_df["gauge_id"] = static_df["gauge_id"].map(normalize_gauge_id)
    static_df = static_df[static_df["gauge_id"].isin(basin_ids)].sort_values("gauge_id").reset_index(drop=True)
    out_path = output_dir / "attributes" / "static_attributes.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    static_df.to_csv(out_path, index=False)
    return out_path


def archive_for_source(source: str, timeseries_archive: Path, timeseries_nonobs_archive: Path) -> Path:
    if source == "timeseries":
        return timeseries_archive
    if source == "timeseries_nonobs":
        return timeseries_nonobs_archive
    raise ValueError(f"Unsupported forcing source: {source}")


def prepare_group(
    *,
    archive_path: Path,
    rows: pd.DataFrame,
    hourly2_zip: zipfile.ZipFile,
    time_series_dir: Path,
    force: bool,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    pending = rows.copy()
    if not force:
        pending = pending[~pending["gauge_id"].map(lambda basin: (time_series_dir / f"{basin}.nc").exists())].copy()
        existing = rows[~rows["gauge_id"].isin(set(pending["gauge_id"]))].copy()
        for _, row in existing.iterrows():
            results.append(
                {
                    "gauge_id": row["gauge_id"],
                    "forcing_source": row["forcing_source"],
                    "forcing_member": row["forcing_member"],
                    "target_source_selected": row["target_source_selected"],
                    "target_member_selected": row["target_member_selected"],
                    "target_variable_selected": row["target_variable_selected"],
                    "prepared_path": str(time_series_dir / f"{row['gauge_id']}.nc"),
                    "prepared_status": "existing",
                    "actual_valid_target_count": pd.NA,
                    "expected_target_count": pd.NA,
                    "actual_coverage_fraction": pd.NA,
                    "error": "",
                }
            )
    if pending.empty:
        return results

    with tempfile.TemporaryDirectory(prefix="camelsh_expanded_drbc_") as tmpdir:
        tmpdir_path = Path(tmpdir)
        members = pending["forcing_member"].tolist()
        print(f"Extracting {len(members)} members from {archive_path}", flush=True)
        with py7zr.SevenZipFile(archive_path, mode="r") as archive:
            archive.extract(path=tmpdir_path, targets=members)

        for index, (_, row) in enumerate(pending.iterrows(), start=1):
            gauge_id = row["gauge_id"]
            source_path = tmpdir_path / str(row["forcing_member"])
            target_path = time_series_dir / f"{gauge_id}.nc"
            print(f"  Preparing {index}/{len(pending)} {gauge_id}", flush=True)
            if not source_path.exists():
                result = {
                    "actual_valid_target_count": pd.NA,
                    "expected_target_count": pd.NA,
                    "actual_coverage_fraction": pd.NA,
                    "prepared_status": "failed",
                    "error": f"missing extracted member: {row['forcing_member']}",
                }
            else:
                result = write_prepared_dataset(
                    source_path=source_path,
                    row=row,
                    hourly2_zip=hourly2_zip,
                    target_path=target_path,
                )
                source_path.unlink(missing_ok=True)
            results.append(
                {
                    "gauge_id": gauge_id,
                    "forcing_source": row["forcing_source"],
                    "forcing_member": row["forcing_member"],
                    "target_source_selected": row["target_source_selected"],
                    "target_member_selected": row["target_member_selected"],
                    "target_variable_selected": row["target_variable_selected"],
                    "prepared_path": str(target_path),
                    **result,
                }
            )
    return results


def validate_prepared_rows(manifest: pd.DataFrame, time_series_dir: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    expected_count = int(pd.date_range(TEST_START, TEST_END, freq="h").size)
    for _, row in manifest.iterrows():
        gauge_id = row["gauge_id"]
        path = time_series_dir / f"{gauge_id}.nc"
        if not path.exists():
            rows.append({"gauge_id": gauge_id, "file_exists": False, "has_date_coord": False, "has_streamflow": False})
            continue
        ds = xr.open_dataset(path, engine="netcdf4")
        try:
            has_date = "date" in ds.coords
            has_streamflow = "Streamflow" in ds
            valid_count = int(ds["Streamflow"].sel(date=slice(TEST_START, TEST_END)).notnull().sum().item())
            rows.append(
                {
                    "gauge_id": gauge_id,
                    "file_exists": True,
                    "has_date_coord": has_date,
                    "has_streamflow": has_streamflow,
                    "test_valid_target_count": valid_count,
                    "test_expected_hours": expected_count,
                    "test_coverage_fraction": valid_count / expected_count,
                }
            )
        finally:
            ds.close()
    return pd.DataFrame(rows)


def main() -> int:
    args = parse_args()
    manifest = pd.read_csv(args.manifest, dtype={"gauge_id": str})
    manifest["gauge_id"] = manifest["gauge_id"].map(normalize_gauge_id)
    manifest = manifest.sort_values("gauge_id").reset_index(drop=True)
    if args.limit_basins is not None:
        manifest = manifest.head(args.limit_basins).copy()

    time_series_dir = args.output_dir / "time_series"
    splits_dir = args.output_dir / "splits"
    time_series_dir.mkdir(parents=True, exist_ok=True)
    splits_dir.mkdir(parents=True, exist_ok=True)

    all_results: list[dict[str, Any]] = []
    with zipfile.ZipFile(args.hourly2_zip) as hourly2_zip:
        for source, rows in manifest.groupby("forcing_source", sort=True):
            all_results.extend(
                prepare_group(
                    archive_path=archive_for_source(source, args.timeseries_archive, args.timeseries_nonobs_archive),
                    rows=rows.copy(),
                    hourly2_zip=hourly2_zip,
                    time_series_dir=time_series_dir,
                    force=args.force,
                )
            )

    result_df = pd.DataFrame(all_results).sort_values("gauge_id").reset_index(drop=True)
    result_path = splits_dir / "split_manifest.csv"
    result_df.to_csv(result_path, index=False)

    basin_ids = set(manifest["gauge_id"])
    test_path = splits_dir / "test.txt"
    test_path.write_text("\n".join(sorted(basin_ids)) + "\n", encoding="utf-8")
    attributes_path = build_static_attributes(args.output_dir, basin_ids)
    validation = validate_prepared_rows(manifest, time_series_dir)
    validation_path = splits_dir / "prepared_validation.csv"
    validation.to_csv(validation_path, index=False)

    failed = result_df[result_df["prepared_status"] == "failed"] if not result_df.empty else result_df
    summary = {
        "dataset_name": "drbc_expanded_observed_test",
        "description": "Test-only GenericDataset for evaluating existing subset300 Model 1/2 checkpoints on expanded DRBC.",
        "manifest": str(args.manifest),
        "output_dir": str(args.output_dir),
        "time_series_dir": str(time_series_dir),
        "attributes_path": str(attributes_path),
        "test_split_file": str(test_path),
        "split_manifest": str(result_path),
        "prepared_validation": str(validation_path),
        "requested_basin_count": int(len(manifest)),
        "prepared_file_count": int(validation["file_exists"].sum()),
        "failed_count": int(len(failed)),
        "test_period": {
            "start": TEST_START.isoformat(),
            "end": TEST_END.isoformat(),
        },
        "target_source_counts": {
            str(key): int(value)
            for key, value in manifest["target_source_selected"].value_counts().sort_index().to_dict().items()
        },
        "forcing_source_counts": {
            str(key): int(value)
            for key, value in manifest["forcing_source"].value_counts().sort_index().to_dict().items()
        },
        "validation": {
            "min_test_coverage_fraction": float(validation["test_coverage_fraction"].min()),
            "all_files_exist": bool(validation["file_exists"].all()),
            "all_have_date_coord": bool(validation["has_date_coord"].all()),
            "all_have_streamflow": bool(validation["has_streamflow"].all()),
            "all_coverage_gte_80pct": bool((validation["test_coverage_fraction"] >= 0.8).all()),
        },
    }
    summary_path = args.output_dir / "prepare_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 1 if len(failed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
