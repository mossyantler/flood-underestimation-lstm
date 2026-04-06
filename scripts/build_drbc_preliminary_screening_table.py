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
        description="Build a preliminary flood-prone screening table for DRBC CAMELSH basins."
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
        "--output-dir",
        type=Path,
        default=Path("output/basin/drbc_camelsh/screening"),
    )
    return parser.parse_args()


def scaled_rank(series: pd.Series, ascending: bool) -> pd.Series:
    ranked = series.rank(method="average", ascending=ascending, pct=True)
    return ranked.fillna(0.0)


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    analysis = pd.read_csv(args.analysis_csv, dtype={"gauge_id": str})
    quality = pd.read_csv(args.quality_csv, dtype={"gauge_id": str})

    merged = analysis.merge(
        quality[[
            "gauge_id",
            "passes_streamflow_quality_gate",
            "hydromod_risk",
            "obs_years_with_any_data",
            "obs_years_usable",
            "obs_coverage_ratio_active_span",
            "annual_coverage_mean_usable",
            "FLOW_PCT_EST_VALUES",
            "BASIN_BOUNDARY_CONFIDENCE",
        ]],
        on="gauge_id",
        how="left",
        validate="one_to_one",
    )

    screened = merged[merged["passes_streamflow_quality_gate"]].copy()

    screened["rank_high_prec_freq"] = scaled_rank(screened["high_prec_freq"], ascending=False)
    screened["rank_high_prec_dur"] = scaled_rank(screened["high_prec_dur"], ascending=False)
    screened["rank_slope"] = scaled_rank(screened["slope_pct"], ascending=False)
    screened["rank_stream_density"] = scaled_rank(
        screened["stream_density_km_per_sqkm"], ascending=False
    )
    screened["rank_low_baseflow"] = scaled_rank(
        screened["baseflow_index_pct"], ascending=True
    )
    screened["rank_low_forest"] = scaled_rank(screened["forest_pct"], ascending=True)
    screened["rank_low_storage"] = scaled_rank(
        screened["soil_available_water_capacity"], ascending=True
    )

    screened["preliminary_flood_prone_score"] = (
        0.20 * screened["rank_high_prec_freq"]
        + 0.15 * screened["rank_high_prec_dur"]
        + 0.20 * screened["rank_slope"]
        + 0.10 * screened["rank_stream_density"]
        + 0.15 * screened["rank_low_baseflow"]
        + 0.10 * screened["rank_low_forest"]
        + 0.10 * screened["rank_low_storage"]
    )

    screened["snow_influenced_tag"] = screened["frac_snow"] >= screened["frac_snow"].median()
    screened["steep_fast_response_tag"] = (
        (screened["slope_pct"] >= screened["slope_pct"].median())
        & (screened["baseflow_index_pct"] <= screened["baseflow_index_pct"].median())
    )
    screened["coastal_or_hydromod_risk_tag"] = screened["hydromod_risk"].fillna(False)

    screened = screened.sort_values(
        ["preliminary_flood_prone_score", "obs_years_usable", "gauge_id"],
        ascending=[False, False, True],
    ).reset_index(drop=True)

    output_cols = [
        "gauge_id",
        "gauge_name",
        "state",
        "drain_sqkm_attr",
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
        "p_mean",
        "aridity",
        "p_seasonality",
        "frac_snow",
        "high_prec_freq",
        "high_prec_dur",
        "elev_mean_m",
        "slope_pct",
        "stream_density_km_per_sqkm",
        "baseflow_index_pct",
        "soil_available_water_capacity",
        "soil_permeability_index",
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

    screening_table = screened[output_cols]

    summary = {
        "quality_pass_basin_count": int(len(screening_table)),
        "top10_mean_score": round(float(screening_table.head(10)["preliminary_flood_prone_score"].mean()), 6),
        "snow_influenced_count": int(screening_table["snow_influenced_tag"].sum()),
        "steep_fast_response_count": int(screening_table["steep_fast_response_tag"].sum()),
        "hydromod_risk_count": int(screening_table["coastal_or_hydromod_risk_tag"].sum()),
    }

    out_csv = args.output_dir / "drbc_preliminary_screening_table.csv"
    out_json = args.output_dir / "drbc_preliminary_screening_summary.json"
    screening_table.to_csv(out_csv, index=False)
    out_json.write_text(json.dumps(summary, indent=2))

    print(f"Wrote preliminary screening table: {out_csv}")
    print(f"Wrote summary: {out_json}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
