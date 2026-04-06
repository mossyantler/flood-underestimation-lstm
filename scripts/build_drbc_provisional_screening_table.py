#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pandas>=2.2",
# ]
# ///

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a provisional DRBC screening table from static analysis, "
            "streamflow quality, and preliminary flood-prone scores."
        )
    )
    parser.add_argument(
        "--analysis-csv",
        type=Path,
        default=Path("output/basin/drbc_camelsh/analysis/drbc_selected_basin_analysis_table.csv"),
    )
    parser.add_argument(
        "--quality-csv",
        type=Path,
        default=Path("output/basin/drbc_camelsh/screening/drbc_streamflow_quality_table.csv"),
    )
    parser.add_argument(
        "--preliminary-csv",
        type=Path,
        default=Path("output/basin/drbc_camelsh/screening/drbc_preliminary_screening_table.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/basin/drbc_camelsh/screening"),
    )
    parser.add_argument("--broad-top-k", type=int, default=15)
    parser.add_argument("--natural-top-k", type=int, default=8)
    parser.add_argument("--event-priority-top-k", type=int, default=20)
    return parser.parse_args()


def build_quality_fail_reason(row: pd.Series) -> str:
    reasons: list[str] = []
    if not bool(row.get("passes_obs_years_gate", False)):
        reasons.append("obs_years_lt_threshold")
    if not bool(row.get("passes_estimated_flow_gate", False)):
        reasons.append("estimated_flow_pct_gt_threshold")
    if not bool(row.get("passes_boundary_conf_gate", False)):
        reasons.append("boundary_conf_lt_threshold")
    return ";".join(reasons) if reasons else ""


def build_notes(row: pd.Series) -> str:
    notes: list[str] = []
    if bool(row.get("hydromod_risk", False)):
        notes.append("hydromod_caution")
    if bool(row.get("snow_influenced_tag", False)):
        notes.append("snow_influenced")
    if bool(row.get("steep_fast_response_tag", False)):
        notes.append("steep_fast_response")
    if row.get("quality_fail_reason"):
        notes.append(f"quality_fail:{row['quality_fail_reason']}")
    return ";".join(notes)


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    analysis = pd.read_csv(args.analysis_csv, dtype={"gauge_id": str})
    quality = pd.read_csv(args.quality_csv, dtype={"gauge_id": str})
    preliminary = pd.read_csv(args.preliminary_csv, dtype={"gauge_id": str})

    quality_cols = [
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
        "FLOW_PCT_EST_VALUES",
        "ACTIVE09",
        "FLOWYRS_1900_2009",
        "FLOWYRS_1950_2009",
        "FLOWYRS_1990_2009",
        "BASIN_BOUNDARY_CONFIDENCE",
        "PCT_DIFF_NWIS",
        "HUC10_CHECK",
        "NDAMS_2009",
        "STOR_NOR_2009",
        "MAJ_NDAMS_2009",
        "DDENS_2009",
        "CANALS_PCT",
        "NPDES_MAJ_DENS",
        "POWER_NUM_PTS",
        "FRESHW_WITHDRAWAL",
        "hydromod_risk",
        "passes_obs_years_gate",
        "passes_estimated_flow_gate",
        "passes_boundary_conf_gate",
        "passes_streamflow_quality_gate",
    ]
    preliminary_cols = [
        "gauge_id",
        "rank_high_prec_freq",
        "rank_high_prec_dur",
        "rank_slope",
        "rank_stream_density",
        "rank_low_baseflow",
        "rank_low_forest",
        "rank_low_storage",
        "preliminary_flood_prone_score",
        "snow_influenced_tag",
        "steep_fast_response_tag",
        "coastal_or_hydromod_risk_tag",
    ]

    merged = (
        analysis.merge(quality[quality_cols], on="gauge_id", how="left", validate="one_to_one")
        .merge(preliminary[preliminary_cols], on="gauge_id", how="left", validate="one_to_one")
    )

    merged["passes_streamflow_quality_gate"] = merged["passes_streamflow_quality_gate"].fillna(False)
    merged["hydromod_risk"] = merged["hydromod_risk"].fillna(False)
    merged["snow_influenced_tag"] = merged["snow_influenced_tag"].fillna(False)
    merged["steep_fast_response_tag"] = merged["steep_fast_response_tag"].fillna(False)
    merged["coastal_or_hydromod_risk_tag"] = merged["coastal_or_hydromod_risk_tag"].fillna(False)

    quality_pass = (
        merged[merged["passes_streamflow_quality_gate"]]
        .sort_values(
            ["preliminary_flood_prone_score", "obs_years_usable", "gauge_id"],
            ascending=[False, False, True],
        )
        .reset_index(drop=True)
        .copy()
    )
    quality_pass["broad_priority_rank"] = range(1, len(quality_pass) + 1)

    natural = (
        quality_pass[~quality_pass["hydromod_risk"]]
        .sort_values(
            ["preliminary_flood_prone_score", "obs_years_usable", "gauge_id"],
            ascending=[False, False, True],
        )
        .reset_index(drop=True)
        .copy()
    )
    natural["natural_priority_rank"] = range(1, len(natural) + 1)

    merged = merged.merge(
        quality_pass[["gauge_id", "broad_priority_rank"]],
        on="gauge_id",
        how="left",
        validate="one_to_one",
    ).merge(
        natural[["gauge_id", "natural_priority_rank"]],
        on="gauge_id",
        how="left",
        validate="one_to_one",
    )

    merged["recommended_broad_cohort"] = merged["broad_priority_rank"] <= args.broad_top_k
    merged["recommended_broad_cohort"] = merged["recommended_broad_cohort"].fillna(False)

    merged["recommended_natural_cohort"] = merged["natural_priority_rank"] <= args.natural_top_k
    merged["recommended_natural_cohort"] = merged["recommended_natural_cohort"].fillna(False)

    merged["recommended_event_priority"] = merged["broad_priority_rank"] <= args.event_priority_top_k
    merged["recommended_event_priority"] = merged["recommended_event_priority"].fillna(False)

    merged["quality_fail_reason"] = merged.apply(build_quality_fail_reason, axis=1)

    merged["provisional_screening_status"] = "retain_for_event_screening"
    merged.loc[~merged["passes_streamflow_quality_gate"], "provisional_screening_status"] = "exclude_quality_gate"
    merged.loc[
        merged["passes_streamflow_quality_gate"] & merged["recommended_broad_cohort"],
        "provisional_screening_status",
    ] = "priority_broad"
    merged.loc[
        merged["passes_streamflow_quality_gate"] & merged["recommended_natural_cohort"],
        "provisional_screening_status",
    ] = "priority_natural"

    merged["screening_notes"] = merged.apply(build_notes, axis=1)

    merged = merged.sort_values(
        [
            "passes_streamflow_quality_gate",
            "recommended_natural_cohort",
            "recommended_broad_cohort",
            "broad_priority_rank",
            "preliminary_flood_prone_score",
            "gauge_id",
        ],
        ascending=[False, False, False, True, False, True],
    ).reset_index(drop=True)

    output_cols = [
        "gauge_id",
        "gauge_name",
        "state",
        "camelsh_huc02",
        "drain_sqkm_attr",
        "basin_area_sqkm_geom",
        "overlap_ratio_of_basin",
        "obs_hours_total",
        "obs_years_with_any_data",
        "obs_years_usable",
        "obs_coverage_ratio_active_span",
        "annual_coverage_mean_usable",
        "FLOW_PCT_EST_VALUES",
        "BASIN_BOUNDARY_CONFIDENCE",
        "hydromod_risk",
        "forest_pct",
        "developed_pct",
        "wetland_pct",
        "dom_land_cover",
        "p_mean",
        "aridity",
        "frac_snow",
        "high_prec_freq",
        "high_prec_dur",
        "elev_mean_m",
        "slope_pct",
        "stream_density_km_per_sqkm",
        "baseflow_index_pct",
        "soil_available_water_capacity",
        "soil_permeability_index",
        "preliminary_flood_prone_score",
        "broad_priority_rank",
        "natural_priority_rank",
        "recommended_broad_cohort",
        "recommended_natural_cohort",
        "recommended_event_priority",
        "snow_influenced_tag",
        "steep_fast_response_tag",
        "coastal_or_hydromod_risk_tag",
        "passes_streamflow_quality_gate",
        "quality_fail_reason",
        "provisional_screening_status",
        "screening_notes",
    ]

    final_table = merged[output_cols]
    final_by_id = final_table.set_index("gauge_id", drop=False)
    broad_ids = quality_pass.sort_values(["broad_priority_rank", "gauge_id"]).head(args.broad_top_k)["gauge_id"]
    natural_ids = natural.sort_values(["natural_priority_rank", "gauge_id"]).head(args.natural_top_k)["gauge_id"]
    broad_top = final_by_id.loc[broad_ids].reset_index(drop=True)
    natural_top = final_by_id.loc[natural_ids].reset_index(drop=True)

    summary = {
        "selected_basin_count": int(len(final_table)),
        "quality_pass_count": int(final_table["passes_streamflow_quality_gate"].sum()),
        "broad_priority_count": int(final_table["recommended_broad_cohort"].sum()),
        "natural_priority_count": int(final_table["recommended_natural_cohort"].sum()),
        "event_priority_count": int(final_table["recommended_event_priority"].sum()),
        "quality_fail_count": int((~final_table["passes_streamflow_quality_gate"]).sum()),
        "hydromod_risk_in_quality_pass_count": int(
            final_table.loc[final_table["passes_streamflow_quality_gate"], "hydromod_risk"].sum()
        ),
        "top_broad_ids": list(broad_ids),
        "top_natural_ids": list(natural_ids),
    }

    out_table = args.output_dir / "drbc_provisional_screening_table.csv"
    out_broad = args.output_dir / "drbc_screening_priority_broad.csv"
    out_natural = args.output_dir / "drbc_screening_priority_natural.csv"
    out_summary = args.output_dir / "drbc_provisional_screening_summary.json"

    final_table.to_csv(out_table, index=False)
    broad_top.to_csv(out_broad, index=False)
    natural_top.to_csv(out_natural, index=False)
    out_summary.write_text(json.dumps(summary, indent=2))

    print(f"Wrote provisional screening table: {out_table}")
    print(f"Wrote broad priority cohort: {out_broad}")
    print(f"Wrote natural priority cohort: {out_natural}")
    print(f"Wrote summary: {out_summary}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
