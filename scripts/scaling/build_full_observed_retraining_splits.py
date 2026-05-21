#!/usr/bin/env python3
# /// script
# dependencies = [
#   "netCDF4>=1.7",
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "py7zr>=0.22",
# ]
# ///

from __future__ import annotations

import argparse
import json
import math
import zipfile
from datetime import datetime
from pathlib import Path

import netCDF4
import numpy as np
import pandas as pd
import py7zr


TRAIN_PERIOD = ("2000-01-01 00:00:00", "2010-12-31 23:00:00")
VALIDATION_PERIOD = ("2011-01-01 00:00:00", "2013-12-31 23:00:00")
TEST_PERIOD = ("2014-01-01 00:00:00", "2016-12-31 23:00:00")
STATIC_ATTRIBUTE_COLUMNS = [
    "area",
    "slope",
    "aridity",
    "snow_fraction",
    "soil_depth",
    "permeability",
    "forest_fraction",
    "baseflow_index",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a fresh full-observed CAMELSH subset300 split for retraining. "
            "Eligibility is checked separately for train, validation, and DRBC test periods."
        )
    )
    parser.add_argument("--hourly2-zip", type=Path, default=Path("basins/CAMELSH_data/hourly_observed/Hourly2.zip"))
    parser.add_argument("--timeseries-archive", type=Path, default=Path("basins/CAMELSH_download/timeseries.7z"))
    parser.add_argument(
        "--timeseries-nonobs-archive",
        type=Path,
        default=Path("basins/CAMELSH_download/timeseries_nonobs.7z"),
    )
    parser.add_argument(
        "--mapping-csv",
        type=Path,
        default=Path("output/basin/drbc/basin_define/camelsh_drbc_mapping.csv"),
    )
    parser.add_argument(
        "--drbc-all-file",
        type=Path,
        default=Path("configs/basin_splits/drbc_holdout_test_drbc_all.txt"),
    )
    parser.add_argument(
        "--attributes-dir",
        type=Path,
        default=Path("basins/CAMELSH_data/attributes"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("configs/pilot/basin_splits/full_observed_subset300"),
    )
    parser.add_argument(
        "--coverage-cache",
        type=Path,
        default=Path("configs/pilot/basin_splits/full_observed_subset300/hourly2_period_coverage.csv"),
    )
    parser.add_argument("--train-count", type=int, default=269)
    parser.add_argument("--validation-count", type=int, default=31)
    parser.add_argument("--min-period-coverage", type=float, default=0.80)
    parser.add_argument("--max-overlap-ratio-tolerance", type=float, default=0.10)
    parser.add_argument("--max-estimated-flow-pct", type=float, default=15.0)
    parser.add_argument("--min-boundary-confidence", type=float, default=7.0)
    parser.add_argument("--seed", type=int, default=20260520)
    parser.add_argument("--stratify-col", type=str, default="camelsh_huc02")
    parser.add_argument("--force-recompute-coverage", action="store_true")
    return parser.parse_args()


def read_ids(path: Path) -> list[str]:
    return [line.strip().zfill(8) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def parse_dt(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def period_slices() -> dict[str, dict[str, object]]:
    origin = datetime(1980, 1, 1)
    periods = {
        "train": TRAIN_PERIOD,
        "validation": VALIDATION_PERIOD,
        "test": TEST_PERIOD,
    }
    result: dict[str, dict[str, object]] = {}
    for split, (start_text, end_text) in periods.items():
        start = parse_dt(start_text)
        end = parse_dt(end_text)
        start_idx = int((start - origin).total_seconds() // 3600)
        end_exclusive = int((end - origin).total_seconds() // 3600) + 1
        result[split] = {
            "start": start_text,
            "end": end_text,
            "start_idx": start_idx,
            "end_exclusive": end_exclusive,
            "expected_hours": end_exclusive - start_idx,
        }
    return result


def list_archive_basin_ids(path: Path, label: str) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    with py7zr.SevenZipFile(path, "r") as archive:
        for name in archive.getnames():
            if not name.lower().endswith((".nc", ".nc4")):
                continue
            gauge_id = Path(name).stem.replace("_hourly", "").zfill(8)
            rows.append({"gauge_id": gauge_id, "forcing_archive": label, "forcing_member": name})
    return pd.DataFrame(rows).drop_duplicates(subset=["gauge_id"]).sort_values("gauge_id").reset_index(drop=True)


def zip_member_gauge_id(member_name: str) -> str:
    return Path(member_name).stem.replace("_hourly", "").zfill(8)


def count_finite(values: np.ndarray) -> int:
    array = np.ma.filled(values, np.nan).astype(float, copy=False)
    return int(np.isfinite(array).sum())


def compute_hourly2_coverage(hourly2_zip: Path, cache_path: Path, force: bool) -> pd.DataFrame:
    if cache_path.exists() and not force:
        return pd.read_csv(cache_path, dtype={"gauge_id": str})

    periods = period_slices()
    rows: list[dict[str, object]] = []
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(hourly2_zip) as zf:
        members = [m for m in zf.namelist() if m.lower().endswith((".nc", ".nc4"))]
        for index, member in enumerate(members, start=1):
            gauge_id = zip_member_gauge_id(member)
            try:
                data = zf.read(member)
                with netCDF4.Dataset("hourly2_in_memory", memory=data) as ds:
                    streamflow = ds.variables["streamflow"]
                    row: dict[str, object] = {"gauge_id": gauge_id, "hourly2_member": member}
                    for split, meta in periods.items():
                        start_idx = int(meta["start_idx"])
                        end_exclusive = int(meta["end_exclusive"])
                        expected_hours = int(meta["expected_hours"])
                        valid_count = count_finite(streamflow[start_idx:end_exclusive])
                        row[f"{split}_valid_target_count"] = valid_count
                        row[f"{split}_expected_hours"] = expected_hours
                        row[f"{split}_coverage_fraction"] = valid_count / expected_hours
                    rows.append(row)
            except Exception as exc:
                rows.append(
                    {
                        "gauge_id": gauge_id,
                        "hourly2_member": member,
                        "coverage_error": f"{type(exc).__name__}: {exc}",
                    }
                )
            if index % 500 == 0:
                print(f"Processed Hourly2 members: {index}/{len(members)}")

    coverage = pd.DataFrame(rows).sort_values("gauge_id").reset_index(drop=True)
    coverage.to_csv(cache_path, index=False)
    return coverage


def load_static_attributes(attributes_dir: Path) -> pd.DataFrame:
    basin_id = pd.read_csv(attributes_dir / "attributes_gageii_BasinID.csv", dtype={"STAID": str})[
        ["STAID", "STANAME", "DRAIN_SQKM", "HUC02", "STATE", "LAT_GAGE", "LNG_GAGE"]
    ].rename(
        columns={
            "STAID": "gauge_id",
            "STANAME": "gauge_name",
            "DRAIN_SQKM": "area",
            "HUC02": "camelsh_huc02",
            "STATE": "state",
            "LAT_GAGE": "lat_gage",
            "LNG_GAGE": "lng_gage",
        }
    )
    topo = pd.read_csv(attributes_dir / "attributes_gageii_Topo.csv", dtype={"STAID": str})[
        ["STAID", "SLOPE_PCT"]
    ].rename(columns={"STAID": "gauge_id", "SLOPE_PCT": "slope"})
    clim = pd.read_csv(attributes_dir / "attributes_nldas2_climate.csv", dtype={"STAID": str})[
        ["STAID", "aridity_index", "frac_snow"]
    ].rename(columns={"STAID": "gauge_id", "aridity_index": "aridity", "frac_snow": "snow_fraction"})
    soil = pd.read_csv(attributes_dir / "attributes_gageii_Soils.csv", dtype={"STAID": str})[
        ["STAID", "ROCKDEPAVE", "PERMAVE"]
    ].rename(columns={"STAID": "gauge_id", "ROCKDEPAVE": "soil_depth", "PERMAVE": "permeability"})
    hydro = pd.read_csv(attributes_dir / "attributes_gageii_Hydro.csv", dtype={"STAID": str})[
        ["STAID", "BFI_AVE"]
    ].rename(columns={"STAID": "gauge_id", "BFI_AVE": "baseflow_index"})
    lc = pd.read_csv(attributes_dir / "attributes_gageii_LC06_Basin.csv", dtype={"STAID": str})[
        ["STAID", "FORESTNLCD06"]
    ].rename(columns={"STAID": "gauge_id"})
    lc["forest_fraction"] = pd.to_numeric(lc["FORESTNLCD06"], errors="coerce") / 100.0
    lc = lc[["gauge_id", "forest_fraction"]]

    static = (
        basin_id.merge(topo, on="gauge_id")
        .merge(clim, on="gauge_id")
        .merge(soil, on="gauge_id")
        .merge(hydro, on="gauge_id")
        .merge(lc, on="gauge_id")
    )
    static["gauge_id"] = static["gauge_id"].astype(str).str.zfill(8)
    static["camelsh_huc02"] = static["camelsh_huc02"].astype(str).str.zfill(2)
    return static


def load_quality_attributes(attributes_dir: Path) -> pd.DataFrame:
    flowrec = pd.read_csv(attributes_dir / "attributes_gageii_FlowRec.csv", dtype={"STAID": str})[
        ["STAID", "FLOW_PCT_EST_VALUES"]
    ].rename(columns={"STAID": "gauge_id"})
    bound = pd.read_csv(attributes_dir / "attributes_gageii_Bound_QA.csv", dtype={"STAID": str})[
        ["STAID", "BASIN_BOUNDARY_CONFIDENCE"]
    ].rename(columns={"STAID": "gauge_id"})
    quality = flowrec.merge(bound, on="gauge_id", how="outer")
    quality["gauge_id"] = quality["gauge_id"].astype(str).str.zfill(8)
    quality["FLOW_PCT_EST_VALUES"] = pd.to_numeric(quality["FLOW_PCT_EST_VALUES"], errors="coerce")
    quality["BASIN_BOUNDARY_CONFIDENCE"] = pd.to_numeric(quality["BASIN_BOUNDARY_CONFIDENCE"], errors="coerce")
    return quality


def largest_remainder_allocation(
    group_sizes: pd.Series,
    target_count: int,
    ensure_min_per_group: bool,
) -> dict[str, int]:
    sizes = group_sizes.astype(int).sort_index()
    if target_count > int(sizes.sum()):
        raise ValueError(f"Requested {target_count} samples but only {int(sizes.sum())} are available.")

    allocation = pd.Series(0, index=sizes.index, dtype=int)
    if ensure_min_per_group and target_count >= len(sizes):
        allocation[:] = 1

    remaining_target = target_count - int(allocation.sum())
    remaining_capacity = sizes - allocation
    if remaining_target < 0:
        raise ValueError("Minimum-per-group allocation exceeded target_count.")
    if remaining_target == 0:
        return {str(group): int(count) for group, count in allocation.items()}

    exact = remaining_capacity / remaining_capacity.sum() * remaining_target
    floors = exact.apply(math.floor).astype(int)
    allocation += floors
    leftovers = remaining_target - int(floors.sum())
    remainders = (exact - floors).sort_values(ascending=False)

    for group in remainders.index:
        if leftovers == 0:
            break
        if allocation[group] < sizes[group]:
            allocation[group] += 1
            leftovers -= 1

    if leftovers:
        for group in sizes.index:
            if leftovers == 0:
                break
            if allocation[group] < sizes[group]:
                allocation[group] += 1
                leftovers -= 1

    if leftovers:
        raise ValueError("Failed to allocate all requested samples.")
    return {str(group): int(count) for group, count in allocation.items()}


def stratified_sample(
    df: pd.DataFrame,
    group_col: str,
    target_count: int,
    seed: int,
    ensure_min_per_group: bool,
) -> pd.DataFrame:
    if target_count > len(df):
        raise ValueError(f"Requested {target_count} samples from {len(df)} candidates.")
    grouped = df.copy()
    grouped[group_col] = grouped[group_col].fillna("NA").astype(str)
    group_sizes = grouped[group_col].value_counts().sort_index()
    allocation = largest_remainder_allocation(group_sizes, target_count, ensure_min_per_group)

    parts: list[pd.DataFrame] = []
    for offset, group in enumerate(sorted(allocation)):
        n_select = allocation[group]
        if n_select == 0:
            continue
        group_df = grouped[grouped[group_col] == group].sample(frac=1.0, random_state=seed + offset)
        sampled = group_df.iloc[:n_select].copy()
        sampled["sampling_seed"] = seed + offset
        sampled["stratum_source_count"] = int(group_sizes[group])
        sampled["stratum_selected_count"] = n_select
        parts.append(sampled)
    sampled_df = pd.concat(parts, ignore_index=True).sort_values("gauge_id").reset_index(drop=True)
    if len(sampled_df) != target_count:
        raise ValueError(f"Expected {target_count} sampled rows but got {len(sampled_df)}.")
    return sampled_df


def write_basin_file(path: Path, gauge_ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(gauge_ids) + ("\n" if gauge_ids else ""), encoding="utf-8")


def value_counts_dict(series: pd.Series) -> dict[str, int]:
    return {str(k): int(v) for k, v in series.fillna("NA").astype(str).value_counts().sort_index().to_dict().items()}


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    file1 = list_archive_basin_ids(args.timeseries_archive, "timeseries")
    file2 = list_archive_basin_ids(args.timeseries_nonobs_archive, "timeseries_nonobs")
    forcing = pd.concat([file1, file2], ignore_index=True).drop_duplicates(subset=["gauge_id"])

    coverage = compute_hourly2_coverage(
        hourly2_zip=args.hourly2_zip,
        cache_path=args.coverage_cache,
        force=args.force_recompute_coverage,
    )
    coverage["gauge_id"] = coverage["gauge_id"].astype(str).str.zfill(8)
    for split in ["train", "validation", "test"]:
        coverage[f"{split}_coverage_fraction"] = pd.to_numeric(
            coverage[f"{split}_coverage_fraction"], errors="coerce"
        ).fillna(0.0)
        coverage[f"{split}_valid_target_count"] = pd.to_numeric(
            coverage[f"{split}_valid_target_count"], errors="coerce"
        ).fillna(0).astype(int)

    mapping = pd.read_csv(args.mapping_csv, dtype={"gauge_id": str})
    mapping["gauge_id"] = mapping["gauge_id"].astype(str).str.zfill(8)
    mapping["camelsh_huc02"] = mapping["camelsh_huc02"].astype(str).str.zfill(2)
    static = load_static_attributes(args.attributes_dir)
    quality = load_quality_attributes(args.attributes_dir)

    base = (
        mapping.merge(forcing, on="gauge_id", how="inner")
        .merge(coverage, on="gauge_id", how="inner")
        .merge(static, on="gauge_id", how="left", suffixes=("", "_static"))
        .merge(quality, on="gauge_id", how="left")
    )
    for col in ["camelsh_huc02", "state", "gauge_name", "lat_gage", "lng_gage"]:
        fallback_col = f"{col}_static"
        if fallback_col in base.columns:
            base[col] = base[col].fillna(base[fallback_col])
            base = base.drop(columns=[fallback_col])
    for col in STATIC_ATTRIBUTE_COLUMNS:
        if base[col].isna().any():
            raise SystemExit(f"Missing static attribute `{col}` for candidate rows.")

    outside_drbc = (
        (~base["outlet_in_drbc"])
        & (
            (~base["basin_intersects_drbc"])
            | (base["overlap_ratio_of_basin"].fillna(0.0) <= args.max_overlap_ratio_tolerance)
        )
    )
    streamflow_quality = (
        (base["FLOW_PCT_EST_VALUES"].fillna(100.0) <= args.max_estimated_flow_pct)
        & (base["BASIN_BOUNDARY_CONFIDENCE"].fillna(0.0) >= args.min_boundary_confidence)
    )
    train_pool = base[
        outside_drbc
        & streamflow_quality
        & (base["train_coverage_fraction"] >= args.min_period_coverage)
    ].copy()
    validation_pool = base[
        outside_drbc
        & streamflow_quality
        & (base["validation_coverage_fraction"] >= args.min_period_coverage)
    ].copy()

    train = stratified_sample(
        train_pool,
        group_col=args.stratify_col,
        target_count=args.train_count,
        seed=args.seed + 1000,
        ensure_min_per_group=True,
    )
    validation_pool = validation_pool[~validation_pool["gauge_id"].isin(set(train["gauge_id"]))].copy()
    validation = stratified_sample(
        validation_pool,
        group_col=args.stratify_col,
        target_count=args.validation_count,
        seed=args.seed + 2000,
        ensure_min_per_group=True,
    )

    train["split"] = "train"
    validation["split"] = "validation"

    drbc_all = set(read_ids(args.drbc_all_file))
    test = base[
        base["gauge_id"].isin(drbc_all)
        & (base["test_coverage_fraction"] >= args.min_period_coverage)
    ].copy()
    test["split"] = "test"
    test = test.sort_values("gauge_id").reset_index(drop=True)

    train_ids = train["gauge_id"].tolist()
    validation_ids = validation["gauge_id"].tolist()
    test_ids = test["gauge_id"].tolist()

    write_basin_file(args.output_dir / "train.txt", train_ids)
    write_basin_file(args.output_dir / "validation.txt", validation_ids)
    write_basin_file(args.output_dir / "test.txt", test_ids)

    manifest_cols = [
        "split",
        "gauge_id",
        "gauge_name",
        "state",
        "camelsh_huc02",
        "lat_gage",
        "lng_gage",
        "area",
        "forcing_archive",
        "forcing_member",
        "hourly2_member",
        "train_valid_target_count",
        "train_expected_hours",
        "train_coverage_fraction",
        "validation_valid_target_count",
        "validation_expected_hours",
        "validation_coverage_fraction",
        "test_valid_target_count",
        "test_expected_hours",
        "test_coverage_fraction",
        "FLOW_PCT_EST_VALUES",
        "BASIN_BOUNDARY_CONFIDENCE",
        "sampling_seed",
        "stratum_source_count",
        "stratum_selected_count",
        *STATIC_ATTRIBUTE_COLUMNS,
    ]
    combined = pd.concat([train, validation, test], ignore_index=True)
    for col in ["sampling_seed", "stratum_source_count", "stratum_selected_count"]:
        if col not in combined.columns:
            combined[col] = pd.NA
    combined[manifest_cols].to_csv(args.output_dir / "manifest.csv", index=False)

    eligible_pool_manifest = base.copy()
    eligible_pool_manifest["outside_drbc_trainable"] = outside_drbc
    eligible_pool_manifest["passes_streamflow_quality_gate"] = streamflow_quality
    eligible_pool_manifest["train_period_eligible"] = outside_drbc & streamflow_quality & (
        base["train_coverage_fraction"] >= args.min_period_coverage
    )
    eligible_pool_manifest["validation_period_eligible"] = outside_drbc & streamflow_quality & (
        base["validation_coverage_fraction"] >= args.min_period_coverage
    )
    eligible_pool_manifest["drbc_test_period_eligible"] = base["gauge_id"].isin(drbc_all) & (
        base["test_coverage_fraction"] >= args.min_period_coverage
    )
    eligible_pool_manifest.to_csv(args.output_dir / "eligible_pool_manifest.csv", index=False)

    periods = period_slices()
    summary = {
        "split_name": "full_observed_subset300",
        "description": (
            "Retraining split built from Hourly2 observed streamflow and both CAMELSH forcing archives. "
            "Train, validation, and test eligibility use period-specific Streamflow coverage."
        ),
        "seed": args.seed,
        "stratify_col": args.stratify_col,
        "train_count": len(train_ids),
        "validation_count": len(validation_ids),
        "test_count": len(test_ids),
        "non_drbc_total_train_validation_count": len(train_ids) + len(validation_ids),
        "min_period_coverage": args.min_period_coverage,
        "periods": periods,
        "source_files": {
            "hourly2_zip": str(args.hourly2_zip),
            "timeseries_archive": str(args.timeseries_archive),
            "timeseries_nonobs_archive": str(args.timeseries_nonobs_archive),
            "mapping_csv": str(args.mapping_csv),
            "drbc_all_file": str(args.drbc_all_file),
            "coverage_cache": str(args.coverage_cache),
        },
        "source_counts": {
            "forcing_file1_count": len(file1),
            "forcing_file2_count": len(file2),
            "hourly2_observed_count": len(coverage),
            "forcing_and_hourly2_overlap_count": int(len(base)),
            "non_drbc_train_period_eligible_count": int(len(train_pool)),
            "non_drbc_validation_period_eligible_count": int(len(validation_pool) + len(validation)),
            "drbc_full_candidate_count": int(len(drbc_all)),
            "drbc_test_period_eligible_count": int(len(test_ids)),
        },
        "huc02_counts": {
            "train": value_counts_dict(train[args.stratify_col]),
            "validation": value_counts_dict(validation[args.stratify_col]),
            "test": value_counts_dict(test[args.stratify_col]),
        },
        "output_files": {
            "train": str(args.output_dir / "train.txt"),
            "validation": str(args.output_dir / "validation.txt"),
            "test": str(args.output_dir / "test.txt"),
            "manifest": str(args.output_dir / "manifest.csv"),
            "eligible_pool_manifest": str(args.output_dir / "eligible_pool_manifest.csv"),
        },
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
