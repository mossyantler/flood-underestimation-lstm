#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pandas>=2.2",
# ]
# ///

from __future__ import annotations

import argparse
import calendar
import json
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a master CAMELSH basin checklist for the broad profile by combining "
            "full-basin mapping, minimum quality gate results, and split-level usability status."
        )
    )
    parser.add_argument(
        "--mapping-csv",
        type=Path,
        default=Path("output/basin/drbc/basin_define/camelsh_drbc_mapping.csv"),
        help="Full CAMELSH-to-DRBC mapping table covering all basins.",
    )
    parser.add_argument(
        "--info-csv",
        type=Path,
        default=Path("basins/CAMELSH_data/hourly_observed/info.csv"),
        help="Hourly observation availability table.",
    )
    parser.add_argument(
        "--attributes-dir",
        type=Path,
        default=Path("basins/CAMELSH_data/attributes"),
        help="Directory containing CAMELSH attribute CSV files.",
    )
    parser.add_argument(
        "--train-basin-file",
        type=Path,
        default=Path("configs/basin_splits/drbc_holdout_train_broad.txt"),
    )
    parser.add_argument(
        "--validation-basin-file",
        type=Path,
        default=Path("configs/basin_splits/drbc_holdout_validation_broad.txt"),
    )
    parser.add_argument(
        "--test-basin-file",
        type=Path,
        default=Path("configs/basin_splits/drbc_holdout_test_drbc_quality.txt"),
    )
    parser.add_argument(
        "--prepared-split-manifest",
        type=Path,
        default=Path("data/CAMELSH_generic/drbc_holdout_broad/splits/split_manifest.csv"),
        help="Prepared broad split manifest produced by prepare_camelsh_generic_dataset.py.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/basin/all/screening"),
        help="Directory where the master checklist and summary will be written.",
    )
    parser.add_argument("--min-annual-coverage", type=float, default=0.8)
    parser.add_argument("--min-usable-years", type=int, default=10)
    parser.add_argument("--max-estimated-flow-pct", type=float, default=15.0)
    parser.add_argument("--min-boundary-confidence", type=float, default=7.0)
    return parser.parse_args()


def read_csv(path: Path, key: str = "STAID") -> pd.DataFrame:
    return pd.read_csv(path, dtype={key: str})


def read_split(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def build_info_features(info: pd.DataFrame, min_annual_coverage: float) -> pd.DataFrame:
    info = info.rename(columns={"STAID": "gauge_id", "data_availability [hrs]": "obs_hours_total"}).copy()
    year_cols = [c for c in info.columns if c.isdigit()]
    expected_hours = {col: (366 if calendar.isleap(int(col)) else 365) * 24 for col in year_cols}

    for col in year_cols:
        info[col] = pd.to_numeric(info[col], errors="coerce").fillna(0)
    info["obs_hours_total"] = pd.to_numeric(info["obs_hours_total"], errors="coerce").fillna(0)

    annual_coverage = pd.DataFrame({col: info[col] / expected_hours[col] for col in year_cols}, index=info.index)
    has_any_obs = info[year_cols] > 0
    has_usable_obs = annual_coverage >= min_annual_coverage

    info["obs_years_with_any_data"] = has_any_obs.sum(axis=1)
    info["obs_years_usable"] = has_usable_obs.sum(axis=1)

    info["first_obs_year_any"] = has_any_obs.idxmax(axis=1)
    no_any_obs_mask = info["obs_years_with_any_data"] == 0
    info.loc[no_any_obs_mask, "first_obs_year_any"] = pd.NA

    reversed_cols = list(reversed(year_cols))
    info["last_obs_year_any"] = has_any_obs[reversed_cols].idxmax(axis=1)
    info.loc[no_any_obs_mask, "last_obs_year_any"] = pd.NA

    info["active_span_years_any"] = (
        pd.to_numeric(info["last_obs_year_any"], errors="coerce")
        - pd.to_numeric(info["first_obs_year_any"], errors="coerce")
        + 1
    )
    info.loc[no_any_obs_mask, "active_span_years_any"] = 0

    info["first_obs_year_usable"] = has_usable_obs.idxmax(axis=1)
    no_usable_obs_mask = info["obs_years_usable"] == 0
    info.loc[no_usable_obs_mask, "first_obs_year_usable"] = pd.NA

    info["last_obs_year_usable"] = has_usable_obs[reversed_cols].idxmax(axis=1)
    info.loc[no_usable_obs_mask, "last_obs_year_usable"] = pd.NA

    info["active_span_years_usable"] = (
        pd.to_numeric(info["last_obs_year_usable"], errors="coerce")
        - pd.to_numeric(info["first_obs_year_usable"], errors="coerce")
        + 1
    )
    info.loc[no_usable_obs_mask, "active_span_years_usable"] = 0

    total_possible_hours_any = info["active_span_years_any"] * 365.25 * 24
    info["obs_coverage_ratio_active_span"] = info["obs_hours_total"] / total_possible_hours_any.replace(0, pd.NA)
    info.loc[no_any_obs_mask, "obs_coverage_ratio_active_span"] = 0.0
    info["annual_coverage_mean_any"] = annual_coverage.where(has_any_obs).mean(axis=1).fillna(0.0)
    info["annual_coverage_mean_usable"] = annual_coverage.where(has_usable_obs).mean(axis=1).fillna(0.0)
    info["min_annual_coverage_threshold"] = min_annual_coverage

    keep_cols = [
        "gauge_id",
        "obs_hours_total",
        "obs_years_with_any_data",
        "obs_years_usable",
        "first_obs_year_any",
        "last_obs_year_any",
        "active_span_years_any",
        "first_obs_year_usable",
        "last_obs_year_usable",
        "active_span_years_usable",
        "obs_coverage_ratio_active_span",
        "annual_coverage_mean_any",
        "annual_coverage_mean_usable",
        "min_annual_coverage_threshold",
    ]
    return info[keep_cols]


def build_flowrec_features(flowrec: pd.DataFrame) -> pd.DataFrame:
    flowrec = flowrec.rename(columns={"STAID": "gauge_id"}).copy()
    flowrec["FLOW_PCT_EST_VALUES"] = pd.to_numeric(flowrec["FLOW_PCT_EST_VALUES"], errors="coerce")
    return flowrec[
        [
            "gauge_id",
            "FLOW_PCT_EST_VALUES",
            "ACTIVE09",
            "FLOWYRS_1900_2009",
            "FLOWYRS_1950_2009",
            "FLOWYRS_1990_2009",
        ]
    ]


def build_boundqa_features(boundqa: pd.DataFrame) -> pd.DataFrame:
    boundqa = boundqa.rename(columns={"STAID": "gauge_id"}).copy()
    boundqa["BASIN_BOUNDARY_CONFIDENCE"] = pd.to_numeric(boundqa["BASIN_BOUNDARY_CONFIDENCE"], errors="coerce")
    boundqa["PCT_DIFF_NWIS"] = pd.to_numeric(boundqa["PCT_DIFF_NWIS"], errors="coerce")
    return boundqa[
        [
            "gauge_id",
            "BASIN_BOUNDARY_CONFIDENCE",
            "PCT_DIFF_NWIS",
            "HUC10_CHECK",
        ]
    ]


def build_hydromod_features(dams: pd.DataFrame, other: pd.DataFrame) -> pd.DataFrame:
    dams = dams.rename(columns={"STAID": "gauge_id"}).copy()
    other = other.rename(columns={"STAID": "gauge_id"}).copy()
    keep_dams = ["gauge_id", "NDAMS_2009", "STOR_NOR_2009", "MAJ_NDAMS_2009", "DDENS_2009"]
    keep_other = ["gauge_id", "CANALS_PCT", "NPDES_MAJ_DENS", "POWER_NUM_PTS", "FRESHW_WITHDRAWAL"]

    merged = dams[keep_dams].merge(other[keep_other], on="gauge_id", how="outer")
    numeric_cols = [c for c in merged.columns if c != "gauge_id"]
    for col in numeric_cols:
        merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0.0)

    merged["hydromod_risk"] = (
        (merged["NDAMS_2009"] > 0)
        | (merged["CANALS_PCT"] > 0)
        | (merged["NPDES_MAJ_DENS"] > 0)
        | (merged["POWER_NUM_PTS"] > 0)
    )
    return merged


def load_original_split_membership(args: argparse.Namespace) -> pd.DataFrame:
    split_members: list[tuple[str, str]] = []
    for split_name, split_path in [
        ("train", args.train_basin_file),
        ("validation", args.validation_basin_file),
        ("test", args.test_basin_file),
    ]:
        split_members.extend((gauge_id, split_name) for gauge_id in read_split(split_path))

    original_split_df = pd.DataFrame(split_members, columns=["gauge_id", "original_split"])
    duplicates = original_split_df["gauge_id"].duplicated(keep=False)
    if duplicates.any():
        duplicated_ids = sorted(original_split_df.loc[duplicates, "gauge_id"].unique().tolist())
        raise SystemExit(f"Broad split file 사이에 중복 basin이 있습니다: {duplicated_ids[:10]}")

    return original_split_df


def minimum_quality_reason(row: pd.Series) -> str:
    if bool(row["minimum_quality_gate_pass"]):
        return "pass"

    failed_reasons = [
        reason
        for passed, reason in [
            (row["passes_obs_years_gate"], "fails_obs_years_gate"),
            (row["passes_estimated_flow_gate"], "fails_estimated_flow_gate"),
            (row["passes_boundary_conf_gate"], "fails_boundary_conf_gate"),
        ]
        if not bool(passed)
    ]
    if len(failed_reasons) == 1:
        return failed_reasons[0]
    return "fails_multiple_quality_gates"


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if not args.prepared_split_manifest.exists():
        raise SystemExit(
            "Prepared split manifest가 없습니다. 먼저 "
            "`scripts/data/prepare_camelsh_generic_dataset.py --profile broad`를 실행하세요."
        )

    mapping = pd.read_csv(args.mapping_csv, dtype={"gauge_id": str})
    info = build_info_features(read_csv(args.info_csv), min_annual_coverage=args.min_annual_coverage)
    flowrec = build_flowrec_features(read_csv(args.attributes_dir / "attributes_gageii_FlowRec.csv"))
    boundqa = build_boundqa_features(read_csv(args.attributes_dir / "attributes_gageii_Bound_QA.csv"))
    hydromod = build_hydromod_features(
        read_csv(args.attributes_dir / "attributes_gageii_HydroMod_Dams.csv"),
        read_csv(args.attributes_dir / "attributes_gageii_HydroMod_Other.csv"),
    )
    original_split_df = load_original_split_membership(args)
    prepared_manifest = pd.read_csv(args.prepared_split_manifest, dtype={"gauge_id": str})

    manifest_expected = set(original_split_df["gauge_id"])
    manifest_found = set(prepared_manifest["gauge_id"])
    if manifest_expected != manifest_found:
        missing_in_manifest = sorted(manifest_expected - manifest_found)
        extra_in_manifest = sorted(manifest_found - manifest_expected)
        raise SystemExit(
            "Prepared split manifest와 broad original split membership가 일치하지 않습니다.\n"
            f"missing_in_manifest={missing_in_manifest[:10]}\n"
            f"extra_in_manifest={extra_in_manifest[:10]}"
        )

    checklist = (
        mapping.merge(info, on="gauge_id", how="left")
        .merge(flowrec, on="gauge_id", how="left")
        .merge(boundqa, on="gauge_id", how="left")
        .merge(hydromod, on="gauge_id", how="left")
        .merge(original_split_df, on="gauge_id", how="left")
    )

    checklist["original_split"] = checklist["original_split"].fillna("not_applicable")
    checklist["broad_split_candidate_scope"] = "not_in_broad_split_scope"
    checklist.loc[
        checklist["original_split"].isin(["train", "validation"]),
        "broad_split_candidate_scope",
    ] = "train_validation_candidate"
    checklist.loc[checklist["original_split"] == "test", "broad_split_candidate_scope"] = "test_candidate"

    checklist["passes_obs_years_gate"] = checklist["obs_years_usable"].fillna(0) >= args.min_usable_years
    checklist["passes_estimated_flow_gate"] = checklist["FLOW_PCT_EST_VALUES"].fillna(100.0) <= args.max_estimated_flow_pct
    checklist["passes_boundary_conf_gate"] = (
        checklist["BASIN_BOUNDARY_CONFIDENCE"].fillna(0.0) >= args.min_boundary_confidence
    )
    checklist["minimum_quality_gate_pass"] = (
        checklist["passes_obs_years_gate"]
        & checklist["passes_estimated_flow_gate"]
        & checklist["passes_boundary_conf_gate"]
    )
    checklist["minimum_quality_gate_reason"] = checklist.apply(minimum_quality_reason, axis=1)

    prepared_manifest = prepared_manifest.rename(
        columns={
            "prepared_split_status": "manifest_prepared_split_status",
            "actual_valid_target_count": "manifest_actual_valid_target_count",
            "excluded_by_usability_gate": "manifest_excluded_by_usability_gate",
            "exclusion_reason": "manifest_exclusion_reason",
            "target_variable": "manifest_target_variable",
            "split_start_date": "manifest_split_start_date",
            "split_end_date": "manifest_split_end_date",
            "min_valid_target_count": "manifest_min_valid_target_count",
        }
    )
    checklist = checklist.merge(
        prepared_manifest[
            [
                "gauge_id",
                "manifest_prepared_split_status",
                "manifest_actual_valid_target_count",
                "manifest_excluded_by_usability_gate",
                "manifest_exclusion_reason",
                "manifest_target_variable",
                "manifest_split_start_date",
                "manifest_split_end_date",
                "manifest_min_valid_target_count",
            ]
        ],
        on="gauge_id",
        how="left",
    )

    checklist["target_variable"] = pd.NA
    checklist["split_start_date"] = pd.NA
    checklist["split_end_date"] = pd.NA
    checklist["min_valid_target_count"] = pd.NA
    checklist["actual_valid_target_count"] = pd.NA
    checklist["usability_status"] = "not_applicable"
    checklist["usability_reason"] = "not_in_broad_split_scope"

    quality_fail_mask = ~checklist["minimum_quality_gate_pass"]
    checklist.loc[quality_fail_mask, "usability_reason"] = "minimum_quality_gate_fail"

    candidate_mask = checklist["original_split"].isin(["train", "validation", "test"])
    candidate_quality_pass_mask = candidate_mask & checklist["minimum_quality_gate_pass"]

    checklist.loc[candidate_quality_pass_mask, "target_variable"] = checklist.loc[
        candidate_quality_pass_mask, "manifest_target_variable"
    ]
    checklist.loc[candidate_quality_pass_mask, "split_start_date"] = checklist.loc[
        candidate_quality_pass_mask, "manifest_split_start_date"
    ]
    checklist.loc[candidate_quality_pass_mask, "split_end_date"] = checklist.loc[
        candidate_quality_pass_mask, "manifest_split_end_date"
    ]
    checklist.loc[candidate_quality_pass_mask, "min_valid_target_count"] = checklist.loc[
        candidate_quality_pass_mask, "manifest_min_valid_target_count"
    ]
    checklist.loc[candidate_quality_pass_mask, "actual_valid_target_count"] = checklist.loc[
        candidate_quality_pass_mask, "manifest_actual_valid_target_count"
    ]
    checklist.loc[candidate_quality_pass_mask, "usability_status"] = checklist.loc[
        candidate_quality_pass_mask, "manifest_prepared_split_status"
    ].fillna("except")
    checklist.loc[candidate_quality_pass_mask, "usability_reason"] = checklist.loc[
        candidate_quality_pass_mask, "manifest_exclusion_reason"
    ].fillna("missing_split_manifest_entry")

    output_path = args.output_dir / "camelsh_basin_master_checklist_broad.csv"
    summary_path = args.output_dir / "camelsh_basin_master_checklist_broad_summary.json"

    checklist = checklist.sort_values(["gauge_id"]).reset_index(drop=True)
    checklist.to_csv(output_path, index=False)

    summary = {
        "profile": "broad",
        "dataset": "CAMELSH hourly",
        "total_basin_count": int(len(checklist)),
        "broad_split_candidate_scope_counts": {
            str(k): int(v)
            for k, v in checklist["broad_split_candidate_scope"].value_counts().sort_index().to_dict().items()
        },
        "minimum_quality_gate_pass_count": int(checklist["minimum_quality_gate_pass"].sum()),
        "minimum_quality_gate_reason_counts": {
            str(k): int(v)
            for k, v in checklist["minimum_quality_gate_reason"].value_counts().sort_index().to_dict().items()
        },
        "usability_status_counts": {
            str(k): int(v)
            for k, v in checklist["usability_status"].value_counts().sort_index().to_dict().items()
        },
        "usability_reason_counts": {
            str(k): int(v)
            for k, v in checklist["usability_reason"].value_counts().sort_index().to_dict().items()
        },
        "source_files": {
            "mapping_csv": str(args.mapping_csv),
            "prepared_split_manifest": str(args.prepared_split_manifest),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Wrote master checklist: {output_path}")
    print(f"Wrote checklist summary: {summary_path}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
