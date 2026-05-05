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
        description="Build a streamflow quality table for the DRBC-selected CAMELSH basins."
    )
    parser.add_argument(
        "--selected-csv",
        type=Path,
        default=Path("output/basin/drbc/basin_define/camelsh_drbc_selected.csv"),
    )
    parser.add_argument(
        "--info-csv",
        type=Path,
        default=Path("basins/CAMELSH_data/hourly_observed/info.csv"),
    )
    parser.add_argument(
        "--attributes-dir",
        type=Path,
        default=Path("basins/CAMELSH_data/attributes"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/basin/drbc/screening"),
    )
    parser.add_argument("--min-usable-years", dest="min_observed_years", type=int, default=10)
    parser.add_argument("--min-observed-years", dest="min_observed_years", type=int)
    parser.add_argument("--min-annual-coverage", type=float, default=0.8)
    parser.add_argument("--max-estimated-flow-pct", type=float, default=15.0)
    parser.add_argument("--min-boundary-confidence", type=float, default=7.0)
    return parser.parse_args()


def read_csv(path: Path, key: str = "STAID") -> pd.DataFrame:
    return pd.read_csv(path, dtype={key: str})


def build_info_features(info: pd.DataFrame, min_annual_coverage: float) -> pd.DataFrame:
    info = info.rename(columns={"STAID": "gauge_id", "data_availability [hrs]": "obs_hours_total"}).copy()
    year_cols = [c for c in info.columns if c.isdigit()]
    expected_hours = {
        col: (366 if calendar.isleap(int(col)) else 365) * 24
        for col in year_cols
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
    return info[[
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
    ]]


def build_flowrec_features(flowrec: pd.DataFrame) -> pd.DataFrame:
    flowrec = flowrec.rename(columns={"STAID": "gauge_id"}).copy()
    flowrec["FLOW_PCT_EST_VALUES"] = pd.to_numeric(flowrec["FLOW_PCT_EST_VALUES"], errors="coerce")
    return flowrec[[
        "gauge_id",
        "FLOW_PCT_EST_VALUES",
        "ACTIVE09",
        "FLOWYRS_1900_2009",
        "FLOWYRS_1950_2009",
        "FLOWYRS_1990_2009",
    ]]


def build_boundqa_features(boundqa: pd.DataFrame) -> pd.DataFrame:
    boundqa = boundqa.rename(columns={"STAID": "gauge_id"}).copy()
    boundqa["BASIN_BOUNDARY_CONFIDENCE"] = pd.to_numeric(
        boundqa["BASIN_BOUNDARY_CONFIDENCE"], errors="coerce"
    )
    return boundqa[[
        "gauge_id",
        "BASIN_BOUNDARY_CONFIDENCE",
        "PCT_DIFF_NWIS",
        "HUC10_CHECK",
    ]]


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

    selected = pd.read_csv(args.selected_csv, dtype={"gauge_id": str})
    info = build_info_features(read_csv(args.info_csv), min_annual_coverage=args.min_annual_coverage)
    flowrec = build_flowrec_features(read_csv(args.attributes_dir / "attributes_gageii_FlowRec.csv"))
    boundqa = build_boundqa_features(read_csv(args.attributes_dir / "attributes_gageii_Bound_QA.csv"))
    hydromod = build_hydromod_features(
        read_csv(args.attributes_dir / "attributes_gageii_HydroMod_Dams.csv"),
        read_csv(args.attributes_dir / "attributes_gageii_HydroMod_Other.csv"),
    )

    quality = (
        selected[["gauge_id", "gauge_name", "state", "basin_area_sqkm_geom", "overlap_ratio_of_basin"]]
        .merge(info, on="gauge_id", how="left")
        .merge(flowrec, on="gauge_id", how="left")
        .merge(boundqa, on="gauge_id", how="left")
        .merge(hydromod, on="gauge_id", how="left")
    )

    quality["passes_obs_years_gate"] = quality["obs_years_usable"] >= args.min_observed_years
    quality["passes_estimated_flow_gate"] = quality["FLOW_PCT_EST_VALUES"].fillna(100.0) <= args.max_estimated_flow_pct
    quality["passes_boundary_conf_gate"] = quality["BASIN_BOUNDARY_CONFIDENCE"].fillna(0.0) >= args.min_boundary_confidence
    quality["passes_streamflow_quality_gate"] = (
        quality["passes_obs_years_gate"]
        & quality["passes_estimated_flow_gate"]
        & quality["passes_boundary_conf_gate"]
    )

    quality = quality.sort_values(
        ["passes_streamflow_quality_gate", "obs_years_usable", "obs_hours_total", "gauge_id"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)

    summary = {
        "selected_basin_count": int(len(quality)),
        "passes_streamflow_quality_gate_count": int(quality["passes_streamflow_quality_gate"].sum()),
        "hydromod_risk_count": int(quality["hydromod_risk"].sum()),
        "min_annual_coverage_threshold": args.min_annual_coverage,
        "min_usable_years_gate": args.min_observed_years,
        "mean_obs_years_with_any_data": round(float(quality["obs_years_with_any_data"].mean()), 3),
        "median_obs_years_with_any_data": round(float(quality["obs_years_with_any_data"].median()), 3),
        "mean_obs_years_usable": round(float(quality["obs_years_usable"].mean()), 3),
        "median_obs_years_usable": round(float(quality["obs_years_usable"].median()), 3),
        "mean_annual_coverage_mean_any": round(float(quality["annual_coverage_mean_any"].mean()), 3),
        "mean_annual_coverage_mean_usable": round(float(quality["annual_coverage_mean_usable"].mean()), 3),
        "mean_estimated_flow_pct": round(float(quality["FLOW_PCT_EST_VALUES"].fillna(0).mean()), 3),
    }

    quality_path = args.output_dir / "drbc_streamflow_quality_table.csv"
    summary_path = args.output_dir / "drbc_streamflow_quality_summary.json"

    quality.to_csv(quality_path, index=False)
    summary_path.write_text(json.dumps(summary, indent=2))

    print(f"Wrote quality table: {quality_path}")
    print(f"Wrote summary: {summary_path}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
