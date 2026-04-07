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
            "Build a non-DRBC CAMELSH training pool for the Delaware holdout-region design."
        )
    )
    parser.add_argument(
        "--mapping-csv",
        type=Path,
        default=Path("output/basin/drbc_camelsh/camelsh_drbc_mapping.csv"),
        help="Full CAMELSH-to-DRBC mapping table.",
    )
    parser.add_argument(
        "--info-csv",
        type=Path,
        default=Path("basins/CAMELSH_data/hourly_observed/info.csv"),
        help="CAMELSH hourly observation availability table.",
    )
    parser.add_argument(
        "--attributes-dir",
        type=Path,
        default=Path("basins/CAMELSH_data/attributes"),
        help="CAMELSH attributes directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/basin/camelsh_training_non_drbc"),
        help="Directory where training-pool outputs will be written.",
    )
    parser.add_argument("--min-annual-coverage", type=float, default=0.8)
    parser.add_argument("--min-usable-years", type=int, default=10)
    parser.add_argument("--max-estimated-flow-pct", type=float, default=15.0)
    parser.add_argument("--min-boundary-confidence", type=float, default=7.0)
    parser.add_argument(
        "--max-overlap-ratio-tolerance",
        type=float,
        default=0.1,
        help=(
            "Allow basins with outlet outside DRBC but tiny polygon overlap due to "
            "geometry/source mismatch. Use 0.0 for the previous strict rule."
        ),
    )
    return parser.parse_args()


def read_csv(path: Path, key: str = "STAID") -> pd.DataFrame:
    return pd.read_csv(path, dtype={key: str})


def build_info_features(info: pd.DataFrame, min_annual_coverage: float) -> pd.DataFrame:
    info = info.rename(columns={"STAID": "gauge_id", "data_availability [hrs]": "obs_hours_total"}).copy()
    year_cols = [c for c in info.columns if c.isdigit()]
    expected_hours = {
        col: (366 if calendar.isleap(int(col)) else 365) * 24 for col in year_cols
    }
    for col in year_cols:
        info[col] = pd.to_numeric(info[col], errors="coerce").fillna(0)
    info["obs_hours_total"] = pd.to_numeric(info["obs_hours_total"], errors="coerce").fillna(0)

    annual_coverage = pd.DataFrame(
        {col: info[col] / expected_hours[col] for col in year_cols},
        index=info.index,
    )
    has_any_obs = info[year_cols] > 0
    has_usable_obs = annual_coverage >= min_annual_coverage

    info["obs_years_with_any_data"] = has_any_obs.sum(axis=1)
    info["obs_years_usable"] = has_usable_obs.sum(axis=1)

    info["first_obs_year_usable"] = has_usable_obs.idxmax(axis=1)
    no_usable_obs_mask = info["obs_years_usable"] == 0
    info.loc[no_usable_obs_mask, "first_obs_year_usable"] = pd.NA

    reversed_cols = list(reversed(year_cols))
    info["last_obs_year_usable"] = has_usable_obs[reversed_cols].idxmax(axis=1)
    info.loc[no_usable_obs_mask, "last_obs_year_usable"] = pd.NA

    info["active_span_years_usable"] = (
        pd.to_numeric(info["last_obs_year_usable"], errors="coerce")
        - pd.to_numeric(info["first_obs_year_usable"], errors="coerce")
        + 1
    )
    info.loc[no_usable_obs_mask, "active_span_years_usable"] = 0

    total_possible_hours_usable = info["active_span_years_usable"] * 365.25 * 24
    info["obs_coverage_ratio_active_span"] = info["obs_hours_total"] / total_possible_hours_usable.replace(0, pd.NA)
    info.loc[no_usable_obs_mask, "obs_coverage_ratio_active_span"] = 0.0
    info["annual_coverage_mean_usable"] = annual_coverage.where(has_usable_obs).mean(axis=1).fillna(0.0)
    info["min_annual_coverage_threshold"] = min_annual_coverage
    return info[
        [
            "gauge_id",
            "obs_hours_total",
            "obs_years_with_any_data",
            "obs_years_usable",
            "first_obs_year_usable",
            "last_obs_year_usable",
            "active_span_years_usable",
            "obs_coverage_ratio_active_span",
            "annual_coverage_mean_usable",
            "min_annual_coverage_threshold",
        ]
    ]


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
    boundqa["BASIN_BOUNDARY_CONFIDENCE"] = pd.to_numeric(
        boundqa["BASIN_BOUNDARY_CONFIDENCE"], errors="coerce"
    )
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


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    mapping = pd.read_csv(args.mapping_csv, dtype={"gauge_id": str})
    # Holdout-compatible training pool:
    # 1) basin outlet must be outside DRBC
    # 2) allow zero overlap or very small overlap caused by boundary source mismatch
    overlap_tol = args.max_overlap_ratio_tolerance
    outside = mapping[
        (~mapping["outlet_in_drbc"])
        & (
            (~mapping["basin_intersects_drbc"])
            | (mapping["overlap_ratio_of_basin"].fillna(0.0) <= overlap_tol)
        )
    ].copy()
    outside["outside_drbc_holdout_region"] = True
    outside["training_overlap_tolerance"] = overlap_tol
    outside["passes_tolerant_spatial_rule"] = True

    info = build_info_features(read_csv(args.info_csv), min_annual_coverage=args.min_annual_coverage)
    flowrec = build_flowrec_features(read_csv(args.attributes_dir / "attributes_gageii_FlowRec.csv"))
    boundqa = build_boundqa_features(read_csv(args.attributes_dir / "attributes_gageii_Bound_QA.csv"))
    hydromod = build_hydromod_features(
        read_csv(args.attributes_dir / "attributes_gageii_HydroMod_Dams.csv"),
        read_csv(args.attributes_dir / "attributes_gageii_HydroMod_Other.csv"),
    )

    quality = (
        outside[
            [
                "gauge_id",
                "gauge_name",
                "state",
                "camelsh_huc02",
                "lat_gage",
                "lng_gage",
                "drain_sqkm_attr",
                "selection_reason",
                "overlap_ratio_of_basin",
                "overlap_area_sqkm",
                "outside_drbc_holdout_region",
                "training_overlap_tolerance",
                "passes_tolerant_spatial_rule",
            ]
        ]
        .merge(info, on="gauge_id", how="left")
        .merge(flowrec, on="gauge_id", how="left")
        .merge(boundqa, on="gauge_id", how="left")
        .merge(hydromod, on="gauge_id", how="left")
    )

    quality["passes_obs_years_gate"] = quality["obs_years_usable"] >= args.min_usable_years
    quality["passes_estimated_flow_gate"] = (
        quality["FLOW_PCT_EST_VALUES"].fillna(100.0) <= args.max_estimated_flow_pct
    )
    quality["passes_boundary_conf_gate"] = (
        quality["BASIN_BOUNDARY_CONFIDENCE"].fillna(0.0) >= args.min_boundary_confidence
    )
    quality["passes_streamflow_quality_gate"] = (
        quality["passes_obs_years_gate"]
        & quality["passes_estimated_flow_gate"]
        & quality["passes_boundary_conf_gate"]
    )
    quality["training_pool_type"] = "exclude"
    quality.loc[quality["passes_streamflow_quality_gate"], "training_pool_type"] = "broad"
    quality.loc[
        quality["passes_streamflow_quality_gate"] & (~quality["hydromod_risk"]),
        "training_pool_type",
    ] = "natural"

    quality = quality.sort_values(
        ["passes_streamflow_quality_gate", "obs_years_usable", "obs_hours_total", "gauge_id"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)

    selected = quality[quality["passes_streamflow_quality_gate"]].copy()
    natural = selected[~selected["hydromod_risk"]].copy()

    summary = {
        "holdout_region": "DRBC Delaware River Basin",
        "total_camelsh_basins": int(len(mapping)),
        "drbc_touching_or_inside_basins_excluded_from_training": int(len(mapping) - len(outside)),
        "training_overlap_ratio_tolerance": overlap_tol,
        "strictly_or_tolerantly_outside_drbc_basins": int(len(outside)),
        "min_annual_coverage_threshold": args.min_annual_coverage,
        "min_usable_years_gate": args.min_usable_years,
        "max_estimated_flow_pct": args.max_estimated_flow_pct,
        "min_boundary_confidence": args.min_boundary_confidence,
        "quality_pass_training_basin_count": int(len(selected)),
        "quality_pass_natural_training_basin_count": int(len(natural)),
        "tolerant_overlap_training_basin_count": int(
            (
                selected["overlap_ratio_of_basin"].fillna(0.0) > 0.0
            ).sum()
        ),
        "median_obs_years_usable_selected": round(float(selected["obs_years_usable"].median()), 3)
        if not selected.empty
        else 0.0,
        "mean_obs_years_usable_selected": round(float(selected["obs_years_usable"].mean()), 3)
        if not selected.empty
        else 0.0,
        "huc10_check_selected_counts": {
            str(k): int(v)
            for k, v in selected["HUC10_CHECK"].fillna("NA").value_counts().to_dict().items()
        },
    }

    candidates_path = args.output_dir / "camelsh_non_drbc_training_candidates.csv"
    quality_path = args.output_dir / "camelsh_non_drbc_training_quality_table.csv"
    selected_path = args.output_dir / "camelsh_non_drbc_training_selected.csv"
    natural_path = args.output_dir / "camelsh_non_drbc_training_selected_natural.csv"
    selected_ids_path = args.output_dir / "camelsh_non_drbc_training_selected_ids.txt"
    natural_ids_path = args.output_dir / "camelsh_non_drbc_training_selected_natural_ids.txt"
    summary_path = args.output_dir / "camelsh_non_drbc_training_summary.json"

    outside.to_csv(candidates_path, index=False)
    quality.to_csv(quality_path, index=False)
    selected.to_csv(selected_path, index=False)
    natural.to_csv(natural_path, index=False)
    selected_ids_path.write_text(
        "\n".join(selected["gauge_id"].tolist()) + ("\n" if not selected.empty else ""),
        encoding="utf-8",
    )
    natural_ids_path.write_text(
        "\n".join(natural["gauge_id"].tolist()) + ("\n" if not natural.empty else ""),
        encoding="utf-8",
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Wrote training candidates: {candidates_path}")
    print(f"Wrote quality table: {quality_path}")
    print(f"Wrote selected training basins: {selected_path}")
    print(f"Wrote selected natural training basins: {natural_path}")
    print(f"Wrote summary: {summary_path}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
