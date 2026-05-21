#!/usr/bin/env python3
# /// script
# dependencies = [
#   "netCDF4>=1.7",
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "py7zr>=0.22",
# ]
# ///
"""Build the expanded observed DRBC test split.

This is a test-only expansion for the existing subset300 Model 1/2 runs. It
does not change the non-DRBC train/validation split and should not be treated
as a retraining cohort.
"""
from __future__ import annotations

import argparse
import calendar
import json
import zipfile
from datetime import datetime
from pathlib import Path

import netCDF4
import numpy as np
import pandas as pd
import py7zr


TEST_PERIOD = ("2014-01-01 00:00:00", "2016-12-31 23:00:00")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hourly2-zip", type=Path, default=Path("basins/CAMELSH_data/hourly_observed/Hourly2.zip"))
    parser.add_argument("--timeseries-archive", type=Path, default=Path("basins/CAMELSH_download/timeseries.7z"))
    parser.add_argument(
        "--timeseries-nonobs-archive",
        type=Path,
        default=Path("basins/CAMELSH_download/timeseries_nonobs.7z"),
    )
    parser.add_argument("--info-csv", type=Path, default=Path("basins/CAMELSH_data/hourly_observed/info.csv"))
    parser.add_argument("--mapping-csv", type=Path, default=Path("output/basin/drbc/basin_define/camelsh_drbc_mapping.csv"))
    parser.add_argument("--drbc-all-file", type=Path, default=Path("configs/basin_splits/drbc_holdout_test_drbc_all.txt"))
    parser.add_argument("--attributes-dir", type=Path, default=Path("basins/CAMELSH_data/attributes"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("configs/basin_splits/drbc_expanded_observed_test"),
    )
    parser.add_argument(
        "--basin-file",
        type=Path,
        default=Path("configs/basin_splits/drbc_holdout_test_drbc_expanded_observed.txt"),
        help="Flat basin file used by evaluation scripts.",
    )
    parser.add_argument(
        "--hourly2-coverage-cache",
        type=Path,
        default=Path("configs/basin_splits/drbc_expanded_observed_test/hourly2_period_coverage.csv"),
        help="Optional Hourly2 period coverage cache. Recomputed from the zip if missing or --force is passed.",
    )
    parser.add_argument("--min-test-coverage", type=float, default=0.80)
    parser.add_argument("--max-estimated-flow-pct", type=float, default=15.0)
    parser.add_argument("--min-boundary-confidence", type=float, default=7.0)
    parser.add_argument("--force-recompute-hourly2-coverage", action="store_true")
    return parser.parse_args()


def read_ids(path: Path) -> list[str]:
    return [line.strip().zfill(8) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def parse_dt(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def test_period_meta() -> dict[str, object]:
    origin = datetime(1980, 1, 1)
    start = parse_dt(TEST_PERIOD[0])
    end = parse_dt(TEST_PERIOD[1])
    start_idx = int((start - origin).total_seconds() // 3600)
    end_exclusive = int((end - origin).total_seconds() // 3600) + 1
    return {
        "start": TEST_PERIOD[0],
        "end": TEST_PERIOD[1],
        "start_idx": start_idx,
        "end_exclusive": end_exclusive,
        "expected_hours": end_exclusive - start_idx,
        "years": list(range(start.year, end.year + 1)),
    }


def list_archive_basin_ids(path: Path, source: str, priority: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    with py7zr.SevenZipFile(path, "r") as archive:
        for name in archive.getnames():
            if not name.lower().endswith((".nc", ".nc4")):
                continue
            gauge_id = Path(name).stem.replace("_hourly", "").zfill(8)
            rows.append(
                {
                    "gauge_id": gauge_id,
                    "forcing_source": source,
                    "forcing_member": name,
                    "forcing_source_priority": priority,
                }
            )
    return pd.DataFrame(rows).sort_values(["forcing_source_priority", "gauge_id"]).reset_index(drop=True)


def count_finite(values: np.ndarray) -> int:
    array = np.ma.filled(values, np.nan).astype(float, copy=False)
    return int(np.isfinite(array).sum())


def zip_member_gauge_id(member_name: str) -> str:
    return Path(member_name).stem.replace("_hourly", "").zfill(8)


def standardize_hourly2_coverage(coverage: pd.DataFrame) -> pd.DataFrame:
    coverage = coverage.copy()
    coverage["gauge_id"] = coverage["gauge_id"].astype(str).str.zfill(8)
    rename_map = {
        "test_valid_target_count": "hourly2_test_valid_count",
        "test_expected_hours": "hourly2_test_expected_hours",
        "test_coverage_fraction": "hourly2_test_coverage_fraction",
    }
    coverage = coverage.rename(columns=rename_map)
    keep_cols = [
        "gauge_id",
        "hourly2_member",
        "hourly2_test_valid_count",
        "hourly2_test_expected_hours",
        "hourly2_test_coverage_fraction",
    ]
    return coverage[[col for col in keep_cols if col in coverage.columns]]


def compute_hourly2_coverage(hourly2_zip: Path, cache_path: Path, force: bool) -> pd.DataFrame:
    if cache_path.exists() and not force:
        return standardize_hourly2_coverage(pd.read_csv(cache_path, dtype={"gauge_id": str}))

    meta = test_period_meta()
    rows: list[dict[str, object]] = []
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(hourly2_zip) as zf:
        members = [m for m in zf.namelist() if m.lower().endswith((".nc", ".nc4"))]
        for index, member in enumerate(members, start=1):
            gauge_id = zip_member_gauge_id(member)
            row: dict[str, object] = {"gauge_id": gauge_id, "hourly2_member": member}
            try:
                data = zf.read(member)
                with netCDF4.Dataset("hourly2_in_memory", memory=data) as ds:
                    streamflow = ds.variables["streamflow"]
                    start_idx = int(meta["start_idx"])
                    end_exclusive = int(meta["end_exclusive"])
                    expected_hours = int(meta["expected_hours"])
                    valid_count = count_finite(streamflow[start_idx:end_exclusive])
                    row["hourly2_test_valid_count"] = valid_count
                    row["hourly2_test_expected_hours"] = expected_hours
                    row["hourly2_test_coverage_fraction"] = valid_count / expected_hours
            except Exception as exc:
                row["coverage_error"] = f"{type(exc).__name__}: {exc}"
                row["hourly2_test_valid_count"] = 0
                row["hourly2_test_expected_hours"] = int(meta["expected_hours"])
                row["hourly2_test_coverage_fraction"] = 0.0
            rows.append(row)
            if index % 500 == 0:
                print(f"Processed Hourly2 members: {index}/{len(members)}", flush=True)

    coverage = pd.DataFrame(rows).sort_values("gauge_id").reset_index(drop=True)
    cache = coverage.rename(
        columns={
            "hourly2_test_valid_count": "test_valid_target_count",
            "hourly2_test_expected_hours": "test_expected_hours",
            "hourly2_test_coverage_fraction": "test_coverage_fraction",
        }
    )
    cache.to_csv(cache_path, index=False)
    return coverage


def compute_timeseries_coverage(info_csv: Path) -> pd.DataFrame:
    info = pd.read_csv(info_csv, dtype={"STAID": str}).rename(
        columns={"STAID": "gauge_id", "data_availability [hrs]": "timeseries_total_valid_count"}
    )
    info["gauge_id"] = info["gauge_id"].astype(str).str.zfill(8)
    meta = test_period_meta()
    year_cols = [str(year) for year in meta["years"]]
    for col in year_cols:
        info[col] = pd.to_numeric(info[col], errors="coerce").fillna(0).astype(int)

    expected_from_years = sum((366 if calendar.isleap(int(year)) else 365) * 24 for year in year_cols)
    expected_hours = int(meta["expected_hours"])
    if expected_from_years != expected_hours:
        raise ValueError("Test period must align with full-year info.csv counts.")

    out = info[["gauge_id", "timeseries_total_valid_count"]].copy()
    out["timeseries_test_valid_count"] = info[year_cols].sum(axis=1).astype(int)
    out["timeseries_test_expected_hours"] = expected_hours
    out["timeseries_test_coverage_fraction"] = out["timeseries_test_valid_count"] / expected_hours
    return out


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


def choose_target_source(row: pd.Series, min_coverage: float) -> tuple[str, str, str, int, int, float, bool]:
    ts_cov = float(row.get("timeseries_test_coverage_fraction", 0.0) or 0.0)
    h2_cov = float(row.get("hourly2_test_coverage_fraction", 0.0) or 0.0)
    ts_valid = int(row.get("timeseries_test_valid_count", 0) or 0)
    h2_valid = int(row.get("hourly2_test_valid_count", 0) or 0)
    expected = int(row.get("timeseries_test_expected_hours", 0) or row.get("hourly2_test_expected_hours", 0) or 0)

    if row["forcing_source"] == "timeseries" and ts_cov >= min_coverage:
        return "timeseries_streamflow", str(row.get("forcing_member", "")), "Streamflow", ts_valid, expected, ts_cov, True
    if h2_cov >= min_coverage and pd.notna(row.get("hourly2_member")):
        return "hourly2_streamflow", str(row.get("hourly2_member", "")), "streamflow", h2_valid, expected, h2_cov, True
    return "none", "", "", 0, expected, max(ts_cov, h2_cov), False


def write_basin_file(path: Path, gauge_ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(gauge_ids) + ("\n" if gauge_ids else ""), encoding="utf-8")


def value_counts_dict(series: pd.Series) -> dict[str, int]:
    return {str(k): int(v) for k, v in series.fillna("NA").astype(str).value_counts().sort_index().to_dict().items()}


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    file1 = list_archive_basin_ids(args.timeseries_archive, "timeseries", priority=0)
    file2 = list_archive_basin_ids(args.timeseries_nonobs_archive, "timeseries_nonobs", priority=1)
    forcing = (
        pd.concat([file1, file2], ignore_index=True)
        .sort_values(["forcing_source_priority", "gauge_id"])
        .drop_duplicates(subset=["gauge_id"], keep="first")
        .reset_index(drop=True)
    )

    target_coverage = (
        forcing.merge(compute_timeseries_coverage(args.info_csv), on="gauge_id", how="left")
        .merge(
            compute_hourly2_coverage(args.hourly2_zip, args.hourly2_coverage_cache, args.force_recompute_hourly2_coverage),
            on="gauge_id",
            how="left",
        )
        .sort_values("gauge_id")
        .reset_index(drop=True)
    )
    meta = test_period_meta()
    for source in ["timeseries", "hourly2"]:
        count_col = f"{source}_test_valid_count"
        expected_col = f"{source}_test_expected_hours"
        coverage_col = f"{source}_test_coverage_fraction"
        target_coverage[count_col] = pd.to_numeric(target_coverage[count_col], errors="coerce").fillna(0).astype(int)
        target_coverage[expected_col] = pd.to_numeric(target_coverage[expected_col], errors="coerce").fillna(
            int(meta["expected_hours"])
        ).astype(int)
        target_coverage[coverage_col] = pd.to_numeric(target_coverage[coverage_col], errors="coerce").fillna(0.0)

    non_timeseries = target_coverage["forcing_source"] != "timeseries"
    target_coverage.loc[non_timeseries, "timeseries_test_valid_count"] = 0
    target_coverage.loc[non_timeseries, "timeseries_test_coverage_fraction"] = 0.0

    choices = target_coverage.apply(lambda row: choose_target_source(row, args.min_test_coverage), axis=1)
    target_coverage["target_source_selected"] = [choice[0] for choice in choices]
    target_coverage["target_member_selected"] = [choice[1] for choice in choices]
    target_coverage["target_variable_selected"] = [choice[2] for choice in choices]
    target_coverage["selected_valid_target_count"] = [choice[3] for choice in choices]
    target_coverage["selected_expected_hours"] = [choice[4] for choice in choices]
    target_coverage["selected_coverage_fraction"] = [choice[5] for choice in choices]
    target_coverage["target_eligible"] = [choice[6] for choice in choices]
    target_coverage.to_csv(args.output_dir / "target_coverage.csv", index=False)

    mapping = pd.read_csv(args.mapping_csv, dtype={"gauge_id": str})
    mapping["gauge_id"] = mapping["gauge_id"].astype(str).str.zfill(8)
    mapping["camelsh_huc02"] = mapping["camelsh_huc02"].astype(str).str.zfill(2)
    quality = load_quality_attributes(args.attributes_dir)
    drbc_all = set(read_ids(args.drbc_all_file))

    candidates = (
        mapping[mapping["gauge_id"].isin(drbc_all)]
        .merge(target_coverage, on="gauge_id", how="left")
        .merge(quality, on="gauge_id", how="left")
        .sort_values("gauge_id")
        .reset_index(drop=True)
    )

    candidates["passes_estimated_flow_gate"] = candidates["FLOW_PCT_EST_VALUES"].fillna(100.0) <= args.max_estimated_flow_pct
    candidates["passes_boundary_conf_gate"] = (
        candidates["BASIN_BOUNDARY_CONFIDENCE"].fillna(0.0) >= args.min_boundary_confidence
    )
    candidates["passes_metadata_quality_gate"] = (
        candidates["passes_estimated_flow_gate"] & candidates["passes_boundary_conf_gate"]
    )
    candidates["passes_test_coverage_gate"] = candidates["target_eligible"].fillna(False).astype(bool)
    candidates["selected_for_expanded_drbc_test"] = (
        candidates["passes_metadata_quality_gate"] & candidates["passes_test_coverage_gate"]
    )
    candidates["exclusion_reason"] = "pass"
    candidates.loc[~candidates["passes_estimated_flow_gate"], "exclusion_reason"] = "FLOW_PCT_EST_VALUES_gt_15"
    candidates.loc[~candidates["passes_boundary_conf_gate"], "exclusion_reason"] = "BASIN_BOUNDARY_CONFIDENCE_lt_7"
    candidates.loc[
        candidates["passes_metadata_quality_gate"] & ~candidates["passes_test_coverage_gate"],
        "exclusion_reason",
    ] = "target_coverage_lt_80pct"

    selected = candidates[candidates["selected_for_expanded_drbc_test"]].copy().sort_values("gauge_id").reset_index(drop=True)
    selected_ids = selected["gauge_id"].tolist()
    write_basin_file(args.output_dir / "test.txt", selected_ids)
    write_basin_file(args.basin_file, selected_ids)

    manifest_cols = [
        "gauge_id",
        "gauge_name",
        "state",
        "camelsh_huc02",
        "lat_gage",
        "lng_gage",
        "drain_sqkm_attr",
        "forcing_source",
        "forcing_member",
        "target_source_selected",
        "target_member_selected",
        "target_variable_selected",
        "selected_valid_target_count",
        "selected_expected_hours",
        "selected_coverage_fraction",
        "timeseries_test_valid_count",
        "timeseries_test_coverage_fraction",
        "hourly2_test_valid_count",
        "hourly2_test_coverage_fraction",
        "FLOW_PCT_EST_VALUES",
        "BASIN_BOUNDARY_CONFIDENCE",
        "passes_estimated_flow_gate",
        "passes_boundary_conf_gate",
        "passes_metadata_quality_gate",
        "passes_test_coverage_gate",
        "selected_for_expanded_drbc_test",
        "exclusion_reason",
    ]
    candidates[manifest_cols].to_csv(args.output_dir / "candidate_manifest.csv", index=False)
    selected[manifest_cols].to_csv(args.output_dir / "manifest.csv", index=False)

    old_quality = set(read_ids(Path("configs/basin_splits/drbc_holdout_test_drbc_quality.txt")))
    scaling_300 = set(read_ids(Path("configs/pilot/basin_splits/scaling_300/test.txt")))
    summary = {
        "split_name": "drbc_expanded_observed_test",
        "description": (
            "Test-only expanded DRBC evaluation set for existing subset300 models. "
            "It starts from the 154 DRBC holdout candidates and keeps basins that pass "
            "metadata quality gates plus 2014-2016 target coverage >= 80%."
        ),
        "period": meta,
        "min_test_coverage": args.min_test_coverage,
        "source_files": {
            "drbc_all_file": str(args.drbc_all_file),
            "timeseries_archive": str(args.timeseries_archive),
            "timeseries_nonobs_archive": str(args.timeseries_nonobs_archive),
            "hourly2_zip": str(args.hourly2_zip),
            "hourly2_coverage_cache": str(args.hourly2_coverage_cache),
            "info_csv": str(args.info_csv),
            "mapping_csv": str(args.mapping_csv),
        },
        "target_source_policy": {
            "timeseries_forcing": (
                "Use timeseries.Streamflow when 2014-2016 coverage meets the threshold; "
                "otherwise use Hourly2.streamflow if it meets the threshold."
            ),
            "timeseries_nonobs_forcing": "Use Hourly2.streamflow when 2014-2016 coverage meets the threshold.",
            "timestamp_level_mixing": False,
            "selection_scope": "per basin for this test split",
        },
        "quality_policy": {
            "test_target_coverage_gate": f"selected target coverage >= {args.min_test_coverage}",
            "basin_level_estimated_flow_gate": f"FLOW_PCT_EST_VALUES <= {args.max_estimated_flow_pct}",
            "basin_level_boundary_gate": f"BASIN_BOUNDARY_CONFIDENCE >= {args.min_boundary_confidence}",
        },
        "counts": {
            "drbc_candidate_count": int(len(candidates)),
            "selected_count": int(len(selected)),
            "old_quality_test_count": int(len(old_quality)),
            "scaling_300_test_count": int(len(scaling_300)),
            "overlap_with_old_quality_test_count": int(len(set(selected_ids) & old_quality)),
            "new_vs_old_quality_test_count": int(len(set(selected_ids) - old_quality)),
        },
        "forcing_source_counts": value_counts_dict(selected["forcing_source"]),
        "target_source_counts": value_counts_dict(selected["target_source_selected"]),
        "huc02_counts": value_counts_dict(selected["camelsh_huc02"]),
        "exclusion_reason_counts": value_counts_dict(candidates["exclusion_reason"]),
        "output_files": {
            "test": str(args.output_dir / "test.txt"),
            "flat_basin_file": str(args.basin_file),
            "manifest": str(args.output_dir / "manifest.csv"),
            "candidate_manifest": str(args.output_dir / "candidate_manifest.csv"),
            "target_coverage": str(args.output_dir / "target_coverage.csv"),
            "summary": str(args.output_dir / "summary.json"),
        },
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
