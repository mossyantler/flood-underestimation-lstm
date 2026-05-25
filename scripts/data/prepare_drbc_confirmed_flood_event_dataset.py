#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "xarray>=2024.1",
#   "netcdf4>=1.7",
#   "py7zr>=0.22",
# ]
# ///
"""Prepare a confirmed-flood event-level GenericDataset for DRBC inference."""
from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import py7zr
import xarray as xr


FORCING_VARS = [
    "Rainf",
    "Tair",
    "PotEvap",
    "SWdown",
    "Qair",
    "PSurf",
    "Wind_E",
    "Wind_N",
    "LWdown",
    "CAPE",
    "CRainf_frac",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog-csv",
        type=Path,
        default=Path("output/model_analysis/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv"),
        help="Confirmed flood catalog from build_drbc_confirmed_flood_event_catalog.py.",
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
        default=Path("data/CAMELSH_generic/drbc_holdout_confirmed_flood_events"),
    )
    parser.add_argument("--pre-hours", type=int, default=24)
    parser.add_argument("--post-hours", type=int, default=168)
    parser.add_argument("--warmup-days", type=int, default=21)
    parser.add_argument(
        "--min-window-forcing-coverage",
        type=float,
        default=0.90,
        help="Minimum coverage across all forcing variables over warmup+evaluation window.",
    )
    parser.add_argument(
        "--min-eval-target-coverage",
        type=float,
        default=0.90,
        help="Minimum observed Streamflow coverage over the evaluated event window.",
    )
    parser.add_argument("--force", action="store_true", help="Rebuild NetCDF files even when they already exist.")
    parser.add_argument("--limit-basins", type=int, default=None, help="Smoke-test only the first N catalog basins.")
    parser.add_argument("--limit-events", type=int, default=None, help="Smoke-test only the first N catalog events.")
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


def build_event_windows(
    catalog: pd.DataFrame,
    *,
    pre_hours: int,
    post_hours: int,
    warmup_days: int,
    limit_basins: int | None,
    limit_events: int | None,
) -> pd.DataFrame:
    events = catalog.copy()
    events["basin"] = events["usgs_id"].map(normalize_gauge_id)
    events["usgs_id"] = events["basin"]
    events["peak_time"] = pd.to_datetime(events["peak_time"]).dt.tz_localize(None)
    events = events.sort_values(["basin", "peak_time"]).reset_index(drop=True)

    if limit_basins is not None:
        selected = sorted(events["basin"].dropna().unique())[:limit_basins]
        events = events[events["basin"].isin(selected)].copy()
    if limit_events is not None:
        events = events.head(limit_events).copy()
    events = events.reset_index(drop=True)
    if events.empty:
        return events

    base_ids = events.apply(
        lambda row: f"{row['basin']}_{pd.Timestamp(row['peak_time']).strftime('%Y%m%dT%H%M%S')}",
        axis=1,
    )
    duplicate_seq = base_ids.groupby(base_ids).cumcount()
    duplicate_counts = base_ids.map(base_ids.value_counts())
    events["event_id"] = [
        base if count == 1 else f"{base}_{seq + 1:02d}"
        for base, seq, count in zip(base_ids, duplicate_seq, duplicate_counts, strict=True)
    ]
    events["eval_start"] = events["peak_time"] - pd.Timedelta(hours=pre_hours)
    events["eval_end"] = events["peak_time"] + pd.Timedelta(hours=post_hours)
    events["window_start"] = (
        events["peak_time"] - pd.Timedelta(days=warmup_days, hours=pre_hours)
    ).dt.floor("D")
    events["window_end"] = events["eval_end"].dt.ceil("D") - pd.Timedelta(hours=1)
    return events


def archive_member_map(archive_path: Path) -> dict[str, str]:
    with py7zr.SevenZipFile(archive_path, mode="r") as archive:
        names = archive.getnames()
    members: dict[str, str] = {}
    for name in names:
        path = Path(name)
        if path.suffix.lower() not in {".nc", ".nc4"}:
            continue
        members[normalize_gauge_id(path.stem.replace("_hourly", ""))] = name
    return members


def extract_member(archive_path: Path, member: str, tmpdir: Path) -> Path:
    with py7zr.SevenZipFile(archive_path, mode="r") as archive:
        archive.extract(path=tmpdir, targets=[member])
    extracted = tmpdir / member
    if not extracted.exists():
        raise FileNotFoundError(f"Archive member did not extract: {member}")
    return extracted


def extract_members(archive_path: Path, members: list[str], tmpdir: Path) -> None:
    if not members:
        return
    with py7zr.SevenZipFile(archive_path, mode="r") as archive:
        archive.extract(path=tmpdir, targets=members)


def read_hourly2_streamflow(zip_file: zipfile.ZipFile, basin: str) -> tuple[xr.DataArray | None, str | None]:
    member = f"Hourly2/{basin}_hourly.nc"
    if member not in zip_file.namelist():
        return None, None
    with tempfile.NamedTemporaryFile(suffix=".nc") as tmp:
        tmp.write(zip_file.read(member))
        tmp.flush()
        ds = xr.open_dataset(tmp.name, engine="netcdf4")
        try:
            ds = standardize_time_coord(ds).load()
        finally:
            ds.close()
    q_var = next((name for name in ("streamflow", "Streamflow") if name in ds), None)
    if q_var is None:
        return None, None
    return ds[q_var].rename("Streamflow").astype("float64"), member


def slice_expected_hours(start: pd.Timestamp, end: pd.Timestamp) -> int:
    return int(pd.date_range(start, end, freq="h").size)


def dataarray_coverage(da: xr.DataArray, start: pd.Timestamp, end: pd.Timestamp) -> float:
    expected = slice_expected_hours(start, end)
    if expected == 0:
        return 0.0
    try:
        clipped = da.sel(date=slice(start, end))
    except Exception:
        return 0.0
    valid = int(clipped.notnull().sum().item())
    return valid / expected


def forcing_coverage(ds: xr.Dataset, start: pd.Timestamp, end: pd.Timestamp) -> float:
    coverages: list[float] = []
    for var in FORCING_VARS:
        if var not in ds:
            return 0.0
        coverages.append(dataarray_coverage(ds[var], start, end))
    return float(min(coverages)) if coverages else 0.0


def candidate_target_sources(
    ds: xr.Dataset,
    basin: str,
    hourly2_zip: zipfile.ZipFile,
    *,
    include_hourly2: bool,
    existing_streamflow_only: bool,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if "Streamflow" in ds:
        candidates.append(
            {
                "target_source_selected": "existing_streamflow" if existing_streamflow_only else "timeseries_streamflow",
                "target_member_selected": "",
                "target_variable_selected": "Streamflow",
                "target": ds["Streamflow"].astype("float64"),
                "tie_breaker": 0,
            }
        )
    if not include_hourly2:
        return candidates
    hourly_target, hourly_member = read_hourly2_streamflow(hourly2_zip, basin)
    if hourly_target is not None and hourly_member is not None:
        if not hourly_target["date"].identical(ds["date"]):
            hourly_target = hourly_target.reindex(date=ds["date"])
        candidates.append(
            {
                "target_source_selected": "hourly2_streamflow",
                "target_member_selected": hourly_member,
                "target_variable_selected": "streamflow",
                "target": hourly_target,
                "tie_breaker": 1,
            }
        )
    return candidates


def choose_target_source(
    ds: xr.Dataset,
    basin_events: pd.DataFrame,
    basin: str,
    hourly2_zip: zipfile.ZipFile,
    min_eval_target_coverage: float,
    *,
    include_hourly2: bool,
    existing_streamflow_only: bool,
) -> tuple[dict[str, Any] | None, dict[str, dict[str, float]]]:
    event_coverages_by_source: dict[str, dict[str, float]] = {}
    scored: list[tuple[int, float, int, dict[str, Any]]] = []

    for candidate in candidate_target_sources(
        ds,
        basin,
        hourly2_zip,
        include_hourly2=include_hourly2,
        existing_streamflow_only=existing_streamflow_only,
    ):
        source = candidate["target_source_selected"]
        coverages: dict[str, float] = {}
        for _, event in basin_events.iterrows():
            coverage = dataarray_coverage(candidate["target"], event["eval_start"], event["eval_end"])
            coverages[event["event_id"]] = coverage
        event_coverages_by_source[source] = coverages
        n_ready = sum(value >= min_eval_target_coverage for value in coverages.values())
        mean_coverage = float(np.mean(list(coverages.values()))) if coverages else 0.0
        scored.append((n_ready, mean_coverage, -candidate["tie_breaker"], candidate))

    if not scored:
        return None, event_coverages_by_source
    scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    return scored[0][3], event_coverages_by_source


def write_prepared_netcdf(
    *,
    ds: xr.Dataset,
    target: xr.DataArray,
    target_path: Path,
) -> None:
    output = ds.copy()
    output["Streamflow"] = target.astype("float64")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.with_suffix(".tmp.nc")
    tmp_path.unlink(missing_ok=True)
    output.to_netcdf(tmp_path)
    tmp_path.replace(target_path)


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


def load_existing_dataset(path: Path) -> xr.Dataset:
    ds = xr.open_dataset(path, engine="netcdf4")
    try:
        return standardize_time_coord(ds).load()
    finally:
        ds.close()


def prepare_basin(
    *,
    basin: str,
    basin_events: pd.DataFrame,
    forcing_sources: dict[str, dict[str, str]],
    extracted_forcing_paths: dict[str, Path],
    args: argparse.Namespace,
    hourly2_zip: zipfile.ZipFile,
    time_series_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    target_path = time_series_dir / f"{basin}.nc"
    basin_base = {
        "gauge_id": basin,
        "requested_event_count": int(len(basin_events)),
        "prepared_path": str(target_path),
    }

    if target_path.exists() and not args.force:
        try:
            ds = load_existing_dataset(target_path)
            forcing_source = "existing"
            forcing_member = str(target_path)
            prepared_status = "existing"
            existing_streamflow_only = True
        except Exception as exc:
            return [
                {
                    **event.to_dict(),
                    "prepared_event_status": "except",
                    "exclusion_reason": f"existing_read_failed:{type(exc).__name__}",
                }
                for _, event in basin_events.iterrows()
            ], {**basin_base, "prepared_status": "failed", "error": f"{type(exc).__name__}: {exc}"}
    else:
        forcing_source = next((source for source in ("timeseries", "timeseries_nonobs") if basin in forcing_sources[source]), None)
        if forcing_source is None:
            return [
                {
                    **event.to_dict(),
                    "prepared_event_status": "except",
                    "exclusion_reason": "missing_forcing_archive_member",
                }
                for _, event in basin_events.iterrows()
            ], {**basin_base, "prepared_status": "failed", "error": "missing_forcing_archive_member"}

        forcing_member = forcing_sources[forcing_source][basin]
        try:
            source_path = extracted_forcing_paths[basin]
            ds = load_existing_dataset(source_path)
        except Exception as exc:
            return [
                {
                    **event.to_dict(),
                    "prepared_event_status": "except",
                    "exclusion_reason": f"forcing_extract_failed:{type(exc).__name__}",
                }
                for _, event in basin_events.iterrows()
            ], {**basin_base, "prepared_status": "failed", "error": f"{type(exc).__name__}: {exc}"}
        prepared_status = "prepared"
        existing_streamflow_only = False

    try:
        target_choice, target_coverages_by_source = choose_target_source(
            ds=ds,
            basin_events=basin_events,
            basin=basin,
            hourly2_zip=hourly2_zip,
            min_eval_target_coverage=args.min_eval_target_coverage,
            include_hourly2=not existing_streamflow_only,
            existing_streamflow_only=existing_streamflow_only,
        )
        if target_choice is None:
            return [
                {
                    **event.to_dict(),
                    "forcing_source": forcing_source,
                    "forcing_member": forcing_member,
                    "prepared_event_status": "except",
                    "exclusion_reason": "missing_target_source",
                    "window_forcing_coverage_min": pd.NA,
                    "eval_target_coverage": pd.NA,
                }
                for _, event in basin_events.iterrows()
            ], {**basin_base, "prepared_status": "failed", "error": "missing_target_source"}

        target_source = target_choice["target_source_selected"]
        target_coverages = target_coverages_by_source.get(target_source, {})
        event_rows: list[dict[str, Any]] = []
        ready_event_count = 0

        for _, event in basin_events.iterrows():
            event_dict = event.to_dict()
            event_id = event_dict["event_id"]
            event_forcing_coverage = forcing_coverage(ds, event["window_start"], event["window_end"])
            event_target_coverage = target_coverages.get(event_id, 0.0)
            if event_forcing_coverage < args.min_window_forcing_coverage:
                status = "except"
                reason = "forcing_coverage_below_threshold"
            elif event_target_coverage < args.min_eval_target_coverage:
                status = "except"
                reason = "target_coverage_below_threshold"
            else:
                status = "test"
                reason = "pass"
                ready_event_count += 1

            event_rows.append(
                {
                    **event_dict,
                    "forcing_source": forcing_source,
                    "forcing_member": forcing_member,
                    "target_source_selected": target_choice["target_source_selected"],
                    "target_member_selected": target_choice["target_member_selected"],
                    "target_variable_selected": target_choice["target_variable_selected"],
                    "prepared_path": str(target_path),
                    "prepared_event_status": status,
                    "exclusion_reason": reason,
                    "window_forcing_coverage_min": round(event_forcing_coverage, 4),
                    "eval_target_coverage": round(event_target_coverage, 4),
                }
            )

        if ready_event_count > 0 and (args.force or not target_path.exists()):
            write_prepared_netcdf(ds=ds, target=target_choice["target"], target_path=target_path)

        return event_rows, {
            **basin_base,
            "forcing_source": forcing_source,
            "forcing_member": forcing_member,
            "target_source_selected": target_choice["target_source_selected"],
            "target_member_selected": target_choice["target_member_selected"],
            "target_variable_selected": target_choice["target_variable_selected"],
            "prepared_status": prepared_status if ready_event_count else "no_ready_events",
            "ready_event_count": ready_event_count,
            "error": "",
        }
    finally:
        ds.close()


def to_jsonable(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    return value


def main() -> int:
    args = parse_args()
    if not args.catalog_csv.exists():
        raise SystemExit(f"Missing confirmed flood catalog: {args.catalog_csv}")
    for path in (args.timeseries_archive, args.timeseries_nonobs_archive, args.hourly2_zip):
        if not path.exists():
            raise SystemExit(f"Missing required source file: {path}")

    catalog = pd.read_csv(args.catalog_csv, dtype={"usgs_id": str})
    events = build_event_windows(
        catalog,
        pre_hours=args.pre_hours,
        post_hours=args.post_hours,
        warmup_days=args.warmup_days,
        limit_basins=args.limit_basins,
        limit_events=args.limit_events,
    )
    if events.empty:
        raise SystemExit("Confirmed flood catalog has no events after limits.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    time_series_dir = args.output_dir / "time_series"
    splits_dir = args.output_dir / "splits"
    time_series_dir.mkdir(parents=True, exist_ok=True)
    splits_dir.mkdir(parents=True, exist_ok=True)

    print("Indexing CAMELSH forcing archives ...", flush=True)
    forcing_sources = {
        "timeseries": archive_member_map(args.timeseries_archive),
        "timeseries_nonobs": archive_member_map(args.timeseries_nonobs_archive),
    }
    print(
        "Archive basin counts: "
        f"timeseries={len(forcing_sources['timeseries'])}, "
        f"timeseries_nonobs={len(forcing_sources['timeseries_nonobs'])}",
        flush=True,
    )

    basin_groups = list(events.groupby("basin", sort=True))
    basin_force_sources: dict[str, tuple[str, str]] = {}
    for basin, _ in basin_groups:
        source = next((name for name in ("timeseries", "timeseries_nonobs") if basin in forcing_sources[name]), None)
        if source is not None:
            basin_force_sources[basin] = (source, forcing_sources[source][basin])

    all_event_rows: list[dict[str, Any]] = []
    basin_rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="camelsh_confirmed_flood_batch_") as tmpdir:
        tmpdir_path = Path(tmpdir)
        extracted_forcing_paths: dict[str, Path] = {}
        for source in ("timeseries", "timeseries_nonobs"):
            source_members = [
                member
                for basin, (member_source, member) in basin_force_sources.items()
                if member_source == source and (args.force or not (time_series_dir / f"{basin}.nc").exists())
            ]
            if not source_members:
                continue
            archive_path = archive_for_source(source, args.timeseries_archive, args.timeseries_nonobs_archive)
            print(f"Extracting {len(source_members)} {source} members from {archive_path}", flush=True)
            extract_members(archive_path, source_members, tmpdir_path)
        for basin, (source, member) in basin_force_sources.items():
            extracted = tmpdir_path / member
            if extracted.exists():
                extracted_forcing_paths[basin] = extracted

        with zipfile.ZipFile(args.hourly2_zip) as hourly2_zip:
            for index, (basin, basin_events) in enumerate(basin_groups, start=1):
                print(f"  Preparing {index}/{len(basin_groups)} {basin}: {len(basin_events)} events", flush=True)
                event_rows, basin_row = prepare_basin(
                    basin=basin,
                    basin_events=basin_events.copy(),
                    forcing_sources=forcing_sources,
                    extracted_forcing_paths=extracted_forcing_paths,
                    args=args,
                    hourly2_zip=hourly2_zip,
                    time_series_dir=time_series_dir,
                )
                all_event_rows.extend(event_rows)
                basin_rows.append(basin_row)

    manifest = pd.DataFrame(all_event_rows)
    if manifest.empty:
        raise SystemExit("No event rows were prepared.")
    date_columns = ["peak_time", "window_start", "window_end", "eval_start", "eval_end"]
    for column in date_columns:
        if column in manifest.columns:
            manifest[column] = pd.to_datetime(manifest[column]).map(lambda value: value.isoformat())

    event_manifest_path = splits_dir / "event_window_manifest.csv"
    manifest = manifest.sort_values(["basin", "peak_time", "event_id"]).reset_index(drop=True)
    manifest.to_csv(event_manifest_path, index=False)

    ready = manifest[manifest["prepared_event_status"] == "test"].copy()
    ready_basins = set(ready["basin"].dropna().map(normalize_gauge_id))
    event_windows_path = splits_dir / "event_windows.csv"
    ready.to_csv(event_windows_path, index=False)

    test_path = splits_dir / "test.txt"
    test_path.write_text("\n".join(sorted(ready_basins)) + ("\n" if ready_basins else ""), encoding="utf-8")
    basin_manifest = pd.DataFrame(basin_rows).sort_values("gauge_id").reset_index(drop=True)
    split_manifest_path = splits_dir / "split_manifest.csv"
    basin_manifest.to_csv(split_manifest_path, index=False)

    attributes_path = build_static_attributes(args.output_dir, ready_basins)

    summary = {
        "dataset_name": "drbc_holdout_confirmed_flood_events",
        "description": (
            "Event-level GenericDataset for confirmed flood inference. Events are NWS flood-stage "
            "exceedances from the catalog, with 2000-2013 excluded upstream."
        ),
        "catalog_csv": str(args.catalog_csv),
        "output_dir": str(args.output_dir),
        "time_series_dir": str(time_series_dir),
        "attributes_path": str(attributes_path),
        "test_split_file": str(test_path),
        "event_windows": str(event_windows_path),
        "event_window_manifest": str(event_manifest_path),
        "split_manifest": str(split_manifest_path),
        "requested_event_count": int(len(events)),
        "ready_event_count": int(len(ready)),
        "requested_basin_count": int(events["basin"].nunique()),
        "ready_basin_count": int(len(ready_basins)),
        "min_window_forcing_coverage": args.min_window_forcing_coverage,
        "min_eval_target_coverage": args.min_eval_target_coverage,
        "window_definition": {
            "warmup_days": args.warmup_days,
            "pre_hours": args.pre_hours,
            "post_hours": args.post_hours,
        },
        "event_status_counts": {
            str(key): int(value)
            for key, value in manifest["prepared_event_status"].value_counts().sort_index().to_dict().items()
        },
        "exclusion_reason_counts": {
            str(key): int(value)
            for key, value in manifest["exclusion_reason"].value_counts().sort_index().to_dict().items()
        },
        "forcing_source_counts_ready": {
            str(key): int(value)
            for key, value in ready["forcing_source"].value_counts().sort_index().to_dict().items()
        },
        "target_source_counts_ready": {
            str(key): int(value)
            for key, value in ready["target_source_selected"].value_counts().sort_index().to_dict().items()
        },
    }
    summary_path = args.output_dir / "prepare_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=to_jsonable), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=to_jsonable))
    return 0 if len(ready) else 1


if __name__ == "__main__":
    raise SystemExit(main())
