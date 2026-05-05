#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.8",
#   "numpy>=1.26",
#   "pandas>=2.2",
# ]
# ///
from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ATTRIBUTE_ROOT = (
    REPO_ROOT / "output/model_analysis/overall_analysis/main_comparison/attribute_correlations"
)
DEFAULT_OBS_STATS = (
    REPO_ROOT / "output/model_analysis/overall_analysis/result_checks/outlier_checks/test_observed_streamflow_stats.csv"
)
DEFAULT_EVENT_RESPONSE_SUMMARY = (
    REPO_ROOT / "output/basin/drbc/analysis/event_response/tables/event_response_basin_summary.csv"
)
DEFAULT_EVENT_RESPONSE_TABLE = (
    REPO_ROOT / "output/basin/drbc/analysis/event_response/tables/event_response_table.csv"
)
DEFAULT_FLOOD_GENERATION_SUMMARY = (
    REPO_ROOT / "output/basin/all/analysis/flood_generation/tables/flood_generation_basin_summary.csv"
)
DEFAULT_STREAMFLOW_QUALITY = (
    REPO_ROOT / "output/basin/drbc/screening/drbc_streamflow_quality_table.csv"
)
DEFAULT_OUTPUT_DIR = DEFAULT_ATTRIBUTE_ROOT / "median_deviation"

METRICS = ["NSE", "KGE", "FHV"]
MODELS = ["model1", "model2"]
SEEDS = [111, 222, 444]
FAR_THRESHOLD = 1.5
EXTREME_THRESHOLD = 3.0
TIER_ORDER = [
    "near_median_lt_0_5_iqr",
    "shoulder_0_5_to_1_5_iqr",
    "far_1_5_to_3_iqr",
    "extreme_ge_3_iqr",
]
TIER_LABELS = {
    "near_median_lt_0_5_iqr": "<0.5 IQR",
    "shoulder_0_5_to_1_5_iqr": "0.5-1.5 IQR",
    "far_1_5_to_3_iqr": "1.5-3 IQR",
    "extreme_ge_3_iqr": ">=3 IQR",
}
TIER_COLORS = {
    "near_median_lt_0_5_iqr": "#9BD66D",
    "shoulder_0_5_to_1_5_iqr": "#F3D35B",
    "far_1_5_to_3_iqr": "#F29A4A",
    "extreme_ge_3_iqr": "#E65F5C",
}
METRIC_SHORT_LABELS = {"NSE": "N", "KGE": "K", "FHV": "F"}
DRIVER_COLORS = {
    "A. scale/low-flow metric amplification": "#2563eb",
    "B. small flashy event-response amplification": "#dc2626",
    "C. no shared causal driver assigned": "#6b7280",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze basin and flow-regime characteristics of primary NSE/KGE/FHV "
            "points by distance from each model/seed box-plot median."
        )
    )
    parser.add_argument("--attribute-root", type=Path, default=DEFAULT_ATTRIBUTE_ROOT)
    parser.add_argument("--observed-stats", type=Path, default=DEFAULT_OBS_STATS)
    parser.add_argument("--event-response-summary", type=Path, default=DEFAULT_EVENT_RESPONSE_SUMMARY)
    parser.add_argument("--event-response-table", type=Path, default=DEFAULT_EVENT_RESPONSE_TABLE)
    parser.add_argument("--flood-generation-summary", type=Path, default=DEFAULT_FLOOD_GENERATION_SUMMARY)
    parser.add_argument("--streamflow-quality", type=Path, default=DEFAULT_STREAMFLOW_QUALITY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--far-threshold", type=float, default=FAR_THRESHOLD)
    parser.add_argument("--extreme-threshold", type=float, default=EXTREME_THRESHOLD)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def normalize_basin_id(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        return f"{int(float(text)):08d}"
    except (TypeError, ValueError):
        return text.zfill(8)


def numeric_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for column in out.columns:
        if column in {
            "basin",
            "gauge_id",
            "gauge_name",
            "state",
            "huc02",
            "hydromod_risk",
            "dominant_flood_generation_type",
            "dominant_type_if_any",
        }:
            continue
        out[column] = pd.to_numeric(out[column], errors="coerce")
    return out


def read_metric_table(attribute_root: Path, metric: str) -> pd.DataFrame:
    path = attribute_root / metric / "tables" / f"{metric}_basin_metric_attribute_table.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing metric attribute table: {path}")
    frame = pd.read_csv(path, dtype={"basin": str, "gauge_id": str, "huc02": str})
    frame["basin"] = frame["basin"].map(normalize_basin_id)
    frame["gauge_id"] = frame["gauge_id"].map(normalize_basin_id)
    return numeric_columns(frame)


def read_basin_base(attribute_root: Path) -> pd.DataFrame:
    frame = read_metric_table(attribute_root, "NSE")
    keep = [
        "basin",
        "gauge_id",
        "gauge_name",
        "state",
        "huc02",
        "area",
        "slope",
        "aridity",
        "snow_fraction",
        "baseflow_index",
        "forest_fraction",
        "lat_gage",
        "lng_gage",
    ]
    return frame[[col for col in keep if col in frame.columns]].copy()


def read_observed_stats(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"basin": str})
    frame["basin"] = frame["basin"].map(normalize_basin_id)
    keep = [
        "basin",
        "test_valid_hours",
        "obs_mean",
        "obs_std",
        "obs_cv",
        "obs_q50",
        "obs_q95",
        "obs_q99",
        "obs_max",
        "obs_near_zero_fraction",
        "obs_variance_denominator",
    ]
    return numeric_columns(frame[[col for col in keep if col in frame.columns]])


def read_event_response_summary(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"gauge_id": str})
    frame["gauge_id"] = frame["gauge_id"].map(normalize_basin_id)
    keep = [
        "gauge_id",
        "q99_event_count",
        "event_count",
        "annual_peak_years",
        "unit_area_peak_median",
        "unit_area_peak_p90",
        "q99_event_frequency",
        "rbi",
        "rising_time_median_hours",
        "event_duration_median_hours",
        "event_runoff_coefficient_median",
        "annual_peak_unit_area_median",
        "annual_peak_unit_area_p90",
    ]
    return numeric_columns(frame[[col for col in keep if col in frame.columns]])


def read_event_response_table(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"gauge_id": str})
    frame["gauge_id"] = frame["gauge_id"].map(normalize_basin_id)
    frame["cold_season_bool"] = frame["cold_season_flag"].astype(str).str.lower().isin(["true", "1"])
    grouped = (
        frame.groupby("gauge_id", dropna=False)
        .agg(
            event_rows=("event_id", "size"),
            cold_season_event_fraction=("cold_season_bool", "mean"),
            recent_rain_24h_median=("recent_rain_24h", "median"),
            recent_rain_72h_median=("recent_rain_72h", "median"),
            antecedent_rain_7d_median=("antecedent_rain_7d", "median"),
            antecedent_rain_30d_median=("antecedent_rain_30d", "median"),
            peak_rain_intensity_6h_median=("peak_rain_intensity_6h", "median"),
            event_mean_temp_median=("event_mean_temp", "median"),
            rising_rate_median=("rising_rate", "median"),
        )
        .reset_index()
    )
    return numeric_columns(grouped)


def read_flood_generation_summary(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"gauge_id": str, "huc02": str})
    frame["gauge_id"] = frame["gauge_id"].map(normalize_basin_id)
    keep = [
        "gauge_id",
        "dominant_flood_generation_type",
        "dominant_type_if_any",
        "dominant_type_share",
        "recent_precipitation_share",
        "antecedent_precipitation_share",
        "snowmelt_or_rain_on_snow_share",
        "uncertain_high_flow_candidate_share",
        "low_confidence_event_share",
        "mean_recent_precipitation_strength",
        "mean_antecedent_precipitation_strength",
        "mean_snowmelt_or_rain_on_snow_strength",
    ]
    return numeric_columns(frame[[col for col in keep if col in frame.columns]])


def read_streamflow_quality(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"gauge_id": str})
    frame["basin"] = frame["gauge_id"].map(normalize_basin_id)
    keep = [
        "basin",
        "hydromod_risk",
        "FLOW_PCT_EST_VALUES",
        "BASIN_BOUNDARY_CONFIDENCE",
        "NDAMS_2009",
        "STOR_NOR_2009",
        "MAJ_NDAMS_2009",
        "CANALS_PCT",
        "NPDES_MAJ_DENS",
        "POWER_NUM_PTS",
        "FRESHW_WITHDRAWAL",
    ]
    out = frame[[col for col in keep if col in frame.columns]].copy()
    if "hydromod_risk" in out.columns:
        out["hydromod_risk"] = out["hydromod_risk"].astype(str).str.lower().isin(["true", "1", "yes"])
    return numeric_columns(out)


def build_context(args: argparse.Namespace) -> pd.DataFrame:
    base = read_basin_base(resolve(args.attribute_root))
    context = (
        base.merge(read_observed_stats(resolve(args.observed_stats)), on="basin", how="left")
        .merge(read_event_response_summary(resolve(args.event_response_summary)), on="gauge_id", how="left")
        .merge(read_event_response_table(resolve(args.event_response_table)), on="gauge_id", how="left")
        .merge(read_flood_generation_summary(resolve(args.flood_generation_summary)), on="gauge_id", how="left")
        .merge(read_streamflow_quality(resolve(args.streamflow_quality)), on="basin", how="left")
    )
    return context


def distance_tier(distance: float, far_threshold: float, extreme_threshold: float) -> str:
    if pd.isna(distance):
        return "missing"
    if distance < 0.5:
        return "near_median_lt_0_5_iqr"
    if distance < far_threshold:
        return "shoulder_0_5_to_1_5_iqr"
    if distance < extreme_threshold:
        return "far_1_5_to_3_iqr"
    return "extreme_ge_3_iqr"


def build_median_distance_records(
    attribute_root: Path,
    far_threshold: float,
    extreme_threshold: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    record_parts = []
    metric_value_parts = []
    for metric in METRICS:
        table = read_metric_table(attribute_root, metric)
        metric_values = table[["basin", "gauge_id", "gauge_name"]].copy()
        for model in MODELS:
            for seed in SEEDS:
                column = f"{model}_seed{seed}"
                values = pd.to_numeric(table[column], errors="coerce")
                median = float(values.median(skipna=True))
                q1 = float(values.quantile(0.25))
                q3 = float(values.quantile(0.75))
                iqr = q3 - q1
                lower_fence = q1 - 1.5 * iqr
                upper_fence = q3 + 1.5 * iqr

                work = table[["basin", "gauge_id", "gauge_name"]].copy()
                work["metric"] = metric
                work["model"] = model
                work["seed"] = seed
                work["target"] = column
                work["metric_value"] = values
                work["box_median"] = median
                work["box_q1"] = q1
                work["box_q3"] = q3
                work["box_iqr"] = iqr
                work["median_deviation"] = values - median
                work["abs_median_deviation"] = (values - median).abs()
                work["median_distance_iqr"] = np.where(iqr > 0, (values - median).abs() / iqr, np.nan)
                work["median_side"] = np.where(values > median, "high", np.where(values < median, "low", "at_median"))
                work["box_outlier"] = values.lt(lower_fence) | values.gt(upper_fence)
                work["distance_tier"] = work["median_distance_iqr"].map(
                    lambda value: distance_tier(float(value), far_threshold, extreme_threshold)
                    if pd.notna(value)
                    else "missing"
                )
                if metric == "FHV":
                    work["metric_direction"] = np.where(values > 0, "positive_FHV", np.where(values < 0, "negative_FHV", "zero_FHV"))
                else:
                    work["metric_direction"] = np.where(values > median, "above_median_skill", "below_median_skill")
                record_parts.append(work)

                metric_values[f"{metric}_{column}"] = values
        metric_value_parts.append(metric_values)

    records = pd.concat(record_parts, ignore_index=True)
    metric_values = metric_value_parts[0]
    for part in metric_value_parts[1:]:
        metric_values = metric_values.merge(part.drop(columns=["gauge_id", "gauge_name"]), on="basin", how="outer")
    return records, metric_values


def summarize_by_basin(
    records: pd.DataFrame,
    context: pd.DataFrame,
    far_threshold: float,
    extreme_threshold: float,
) -> pd.DataFrame:
    metric_summaries = []
    for metric, group in records.groupby("metric", sort=False):
        summary = (
            group.groupby("basin", dropna=False)
            .agg(
                **{
                    f"{metric}_records": ("metric_value", "size"),
                    f"{metric}_far_records": ("median_distance_iqr", lambda s: int((s >= far_threshold).sum())),
                    f"{metric}_extreme_records": ("median_distance_iqr", lambda s: int((s >= extreme_threshold).sum())),
                    f"{metric}_box_outlier_records": ("box_outlier", "sum"),
                    f"{metric}_max_median_distance_iqr": ("median_distance_iqr", "max"),
                    f"{metric}_mean_median_distance_iqr": ("median_distance_iqr", "mean"),
                    f"{metric}_low_side_records": ("median_side", lambda s: int((s == "low").sum())),
                    f"{metric}_high_side_records": ("median_side", lambda s: int((s == "high").sum())),
                }
            )
            .reset_index()
        )
        metric_summaries.append(summary)

    out = metric_summaries[0]
    for part in metric_summaries[1:]:
        out = out.merge(part, on="basin", how="outer")

    for metric in METRICS:
        far_col = f"{metric}_far_records"
        box_col = f"{metric}_box_outlier_records"
        if far_col not in out.columns:
            out[far_col] = 0
        if box_col not in out.columns:
            out[box_col] = 0

    out["total_far_records"] = out[[f"{metric}_far_records" for metric in METRICS]].sum(axis=1)
    out["total_extreme_records"] = out[[f"{metric}_extreme_records" for metric in METRICS]].sum(axis=1)
    out["total_box_outlier_records"] = out[[f"{metric}_box_outlier_records" for metric in METRICS]].sum(axis=1)
    out["metrics_with_far_records"] = out[[f"{metric}_far_records" for metric in METRICS]].gt(0).sum(axis=1)
    out["distance_class"] = np.select(
        [
            out["total_far_records"].ge(10),
            out["total_far_records"].between(3, 9),
            out["total_far_records"].between(1, 2),
        ],
        ["repeated_multi_metric_far", "limited_or_metric_specific_far", "single_far_record"],
        default="near_median",
    )

    out = context.merge(out, on="basin", how="left")
    count_cols = [col for col in out.columns if col.endswith("_records") or col in {"total_far_records", "total_extreme_records", "total_box_outlier_records", "metrics_with_far_records"}]
    out[count_cols] = out[count_cols].fillna(0)
    return out.sort_values(["total_far_records", "total_box_outlier_records", "area"], ascending=[False, False, True])


def add_metric_seed_medians(basin_summary: pd.DataFrame, attribute_root: Path) -> pd.DataFrame:
    out = basin_summary.copy()
    for metric in METRICS:
        table = read_metric_table(attribute_root, metric)
        keep = ["basin"]
        for model in MODELS:
            source_cols = [f"{model}_seed{seed}" for seed in SEEDS]
            table[f"{metric}_{model}_seed_median"] = table[source_cols].median(axis=1, skipna=True)
            keep.append(f"{metric}_{model}_seed_median")
        table[f"{metric}_delta_seed_median"] = table[f"{metric}_model2_seed_median"] - table[f"{metric}_model1_seed_median"]
        keep.append(f"{metric}_delta_seed_median")
        out = out.merge(table[keep], on="basin", how="left")
    return out


def grouped_regime_rows(far: pd.DataFrame) -> pd.DataFrame:
    # Keep this intentionally conservative: grouped basins must match on the
    # requested ratio-style regime variables, not only on broad geography.
    groups = [
        {
            "group_id": "G1",
            "group_label": "Crum-East White Clay fast recent-rain small basins",
            "basins": ["01475850", "01478120"],
            "basis": (
                "snow fraction 0.049-0.055, cold-season event fraction 0.494-0.508, "
                "recent-precipitation share 0.763-0.799, q99 event frequency 11.1-12.2/year, "
                "and short event duration 8-9 h."
            ),
        }
    ]
    rows = []
    for spec in groups:
        members = far[far["basin"].isin(spec["basins"])].copy()
        if members.empty or members["basin"].nunique() < 2:
            continue
        row = {
            "group_id": spec["group_id"],
            "group_label": spec["group_label"],
            "basins": " ".join(members["basin"].tolist()),
            "n_basins": int(members["basin"].nunique()),
            "basis": spec["basis"],
        }
        for column in [
            "area",
            "snow_fraction",
            "cold_season_event_fraction",
            "recent_precipitation_share",
            "antecedent_precipitation_share",
            "snowmelt_or_rain_on_snow_share",
            "uncertain_high_flow_candidate_share",
            "obs_variance_denominator",
            "obs_cv",
            "q99_event_frequency",
            "rbi",
            "rising_time_median_hours",
            "event_duration_median_hours",
            "annual_peak_unit_area_p90",
            "total_far_records",
        ]:
            values = pd.to_numeric(members[column], errors="coerce")
            row[f"{column}_min"] = float(values.min(skipna=True))
            row[f"{column}_max"] = float(values.max(skipna=True))
            row[f"{column}_median"] = float(values.median(skipna=True))
        rows.append(row)
    return pd.DataFrame(rows)


def non_grouped_far(far: pd.DataFrame, groups: pd.DataFrame) -> pd.DataFrame:
    grouped_basins: set[str] = set()
    if not groups.empty:
        for value in groups["basins"].dropna():
            grouped_basins.update(str(value).split())
    return far[~far["basin"].isin(grouped_basins)].copy()


def compact_far_profiles(far: pd.DataFrame) -> pd.DataFrame:
    keep = [
        "basin",
        "gauge_name",
        "state",
        "distance_class",
        "total_far_records",
        "total_extreme_records",
        "metrics_with_far_records",
        "NSE_far_records",
        "KGE_far_records",
        "FHV_far_records",
        "NSE_low_side_records",
        "KGE_low_side_records",
        "FHV_high_side_records",
        "area",
        "snow_fraction",
        "cold_season_event_fraction",
        "snowmelt_or_rain_on_snow_share",
        "recent_precipitation_share",
        "antecedent_precipitation_share",
        "uncertain_high_flow_candidate_share",
        "obs_variance_denominator",
        "obs_cv",
        "obs_q99",
        "obs_max",
        "q99_event_frequency",
        "rbi",
        "rising_time_median_hours",
        "event_duration_median_hours",
        "annual_peak_unit_area_p90",
        "NSE_model1_seed_median",
        "NSE_model2_seed_median",
        "KGE_model1_seed_median",
        "KGE_model2_seed_median",
        "FHV_model1_seed_median",
        "FHV_model2_seed_median",
    ]
    return far[[col for col in keep if col in far.columns]].copy()


def build_basin_tier_profile(records: pd.DataFrame, basin_summary: pd.DataFrame) -> pd.DataFrame:
    counts = (
        records.pivot_table(
            index="basin",
            columns="distance_tier",
            values="metric_value",
            aggfunc="count",
            fill_value=0,
        )
        .reset_index()
        .rename_axis(columns=None)
    )
    for tier in TIER_ORDER:
        if tier not in counts.columns:
            counts[tier] = 0

    profile = basin_summary.merge(counts[["basin", *TIER_ORDER]], on="basin", how="left")
    profile[TIER_ORDER] = profile[TIER_ORDER].fillna(0).astype(int)
    profile["all_metric_seed_records"] = profile[TIER_ORDER].sum(axis=1)
    for tier in TIER_ORDER:
        profile[f"{tier}_share"] = profile[tier] / profile["all_metric_seed_records"].replace(0, np.nan)

    profile["far_or_extreme_records"] = profile["far_1_5_to_3_iqr"] + profile["extreme_ge_3_iqr"]
    profile["far_or_extreme_share"] = profile["far_or_extreme_records"] / profile["all_metric_seed_records"].replace(0, np.nan)
    profile["dominant_distance_tier"] = profile[TIER_ORDER].idxmax(axis=1)
    profile["dominant_distance_label"] = profile["dominant_distance_tier"].map(TIER_LABELS)
    profile["max_distance_any_metric_seed"] = profile[
        [f"{metric}_max_median_distance_iqr" for metric in METRICS]
    ].max(axis=1)
    profile["mean_distance_any_metric_seed"] = profile[
        [f"{metric}_mean_median_distance_iqr" for metric in METRICS]
    ].mean(axis=1)

    keep = [
        "basin",
        "gauge_name",
        "state",
        "dominant_distance_label",
        "all_metric_seed_records",
        "near_median_lt_0_5_iqr",
        "shoulder_0_5_to_1_5_iqr",
        "far_1_5_to_3_iqr",
        "extreme_ge_3_iqr",
        "far_or_extreme_records",
        "far_or_extreme_share",
        "mean_distance_any_metric_seed",
        "max_distance_any_metric_seed",
        "NSE_mean_median_distance_iqr",
        "KGE_mean_median_distance_iqr",
        "FHV_mean_median_distance_iqr",
        "NSE_max_median_distance_iqr",
        "KGE_max_median_distance_iqr",
        "FHV_max_median_distance_iqr",
        "area",
        "obs_variance_denominator",
        "obs_q99",
        "q99_event_frequency",
        "rbi",
        "snow_fraction",
        "cold_season_event_fraction",
        "recent_precipitation_share",
        "antecedent_precipitation_share",
        "snowmelt_or_rain_on_snow_share",
        "uncertain_high_flow_candidate_share",
    ]
    return (
        profile[[col for col in keep if col in profile.columns]]
        .sort_values(
            ["far_or_extreme_records", "max_distance_any_metric_seed", "mean_distance_any_metric_seed", "area"],
            ascending=[False, False, False, True],
        )
        .reset_index(drop=True)
    )


def build_basin_model_tier_profile(records: pd.DataFrame, basin_summary: pd.DataFrame) -> pd.DataFrame:
    counts = (
        records.pivot_table(
            index=["model", "basin"],
            columns="distance_tier",
            values="metric_value",
            aggfunc="count",
            fill_value=0,
        )
        .reset_index()
        .rename_axis(columns=None)
    )
    for tier in TIER_ORDER:
        if tier not in counts.columns:
            counts[tier] = 0

    metric_summaries = []
    for metric, group in records.groupby("metric", sort=False):
        summary = (
            group.groupby(["model", "basin"], dropna=False)
            .agg(
                **{
                    f"{metric}_mean_median_distance_iqr": ("median_distance_iqr", "mean"),
                    f"{metric}_max_median_distance_iqr": ("median_distance_iqr", "max"),
                }
            )
            .reset_index()
        )
        metric_summaries.append(summary)

    metric_stats = metric_summaries[0]
    for part in metric_summaries[1:]:
        metric_stats = metric_stats.merge(part, on=["model", "basin"], how="outer")

    keep_context = [
        "basin",
        "gauge_name",
        "state",
        "area",
        "obs_variance_denominator",
        "obs_q99",
        "q99_event_frequency",
        "rbi",
        "snow_fraction",
        "cold_season_event_fraction",
        "recent_precipitation_share",
        "antecedent_precipitation_share",
        "snowmelt_or_rain_on_snow_share",
        "uncertain_high_flow_candidate_share",
    ]
    profile = (
        counts[["model", "basin", *TIER_ORDER]]
        .merge(metric_stats, on=["model", "basin"], how="left")
        .merge(basin_summary[[col for col in keep_context if col in basin_summary.columns]], on="basin", how="left")
    )
    profile[TIER_ORDER] = profile[TIER_ORDER].fillna(0).astype(int)
    profile["model_label"] = profile["model"].map({"model1": "Model 1", "model2": "Model 2"}).fillna(profile["model"])
    profile["all_metric_seed_records"] = profile[TIER_ORDER].sum(axis=1)
    for tier in TIER_ORDER:
        profile[f"{tier}_share"] = profile[tier] / profile["all_metric_seed_records"].replace(0, np.nan)

    profile["far_or_extreme_records"] = profile["far_1_5_to_3_iqr"] + profile["extreme_ge_3_iqr"]
    profile["far_or_extreme_share"] = profile["far_or_extreme_records"] / profile["all_metric_seed_records"].replace(0, np.nan)
    profile["dominant_distance_tier"] = profile[TIER_ORDER].idxmax(axis=1)
    profile["dominant_distance_label"] = profile["dominant_distance_tier"].map(TIER_LABELS)
    profile["max_distance_any_metric_seed"] = profile[
        [f"{metric}_max_median_distance_iqr" for metric in METRICS]
    ].max(axis=1)
    profile["mean_distance_any_metric_seed"] = profile[
        [f"{metric}_mean_median_distance_iqr" for metric in METRICS]
    ].mean(axis=1)

    keep = [
        "model",
        "model_label",
        "basin",
        "gauge_name",
        "state",
        "dominant_distance_label",
        "all_metric_seed_records",
        "near_median_lt_0_5_iqr",
        "shoulder_0_5_to_1_5_iqr",
        "far_1_5_to_3_iqr",
        "extreme_ge_3_iqr",
        "far_or_extreme_records",
        "far_or_extreme_share",
        "mean_distance_any_metric_seed",
        "max_distance_any_metric_seed",
        "NSE_mean_median_distance_iqr",
        "KGE_mean_median_distance_iqr",
        "FHV_mean_median_distance_iqr",
        "NSE_max_median_distance_iqr",
        "KGE_max_median_distance_iqr",
        "FHV_max_median_distance_iqr",
        "area",
        "obs_variance_denominator",
        "obs_q99",
        "q99_event_frequency",
        "rbi",
        "snow_fraction",
        "cold_season_event_fraction",
        "recent_precipitation_share",
        "antecedent_precipitation_share",
        "snowmelt_or_rain_on_snow_share",
        "uncertain_high_flow_candidate_share",
    ]
    return (
        profile[[col for col in keep if col in profile.columns]]
        .sort_values(
            ["model", "far_or_extreme_records", "max_distance_any_metric_seed", "mean_distance_any_metric_seed", "area"],
            ascending=[True, False, False, False, True],
        )
        .reset_index(drop=True)
    )


def build_tier_basin_membership(records: pd.DataFrame, basin_summary: pd.DataFrame) -> pd.DataFrame:
    membership = (
        records.groupby(["distance_tier", "metric", "basin"], dropna=False)
        .agg(
            record_count=("metric_value", "size"),
            mean_distance_iqr=("median_distance_iqr", "mean"),
            max_distance_iqr=("median_distance_iqr", "max"),
            low_side_records=("median_side", lambda s: int((s == "low").sum())),
            high_side_records=("median_side", lambda s: int((s == "high").sum())),
        )
        .reset_index()
    )
    keep = [
        "basin",
        "gauge_name",
        "state",
        "area",
        "obs_variance_denominator",
        "obs_q99",
        "q99_event_frequency",
        "rbi",
        "snow_fraction",
        "cold_season_event_fraction",
        "recent_precipitation_share",
        "antecedent_precipitation_share",
        "snowmelt_or_rain_on_snow_share",
        "uncertain_high_flow_candidate_share",
    ]
    membership = membership.merge(basin_summary[[col for col in keep if col in basin_summary.columns]], on="basin", how="left")
    membership["distance_tier_order"] = membership["distance_tier"].map({tier: idx for idx, tier in enumerate(TIER_ORDER)})
    membership["distance_label"] = membership["distance_tier"].map(TIER_LABELS)
    return membership.sort_values(
        ["distance_tier_order", "metric", "record_count", "max_distance_iqr", "area"],
        ascending=[True, True, False, False, True],
    ).reset_index(drop=True)


def build_tier_distribution_summary(records: pd.DataFrame, basin_summary: pd.DataFrame) -> pd.DataFrame:
    basin_counts = (
        records.groupby(["distance_tier", "basin"], dropna=False)
        .agg(
            record_count=("metric_value", "size"),
            mean_distance_iqr=("median_distance_iqr", "mean"),
            max_distance_iqr=("median_distance_iqr", "max"),
        )
        .reset_index()
    )
    rows = []
    for tier in TIER_ORDER:
        tier_counts = basin_counts[basin_counts["distance_tier"].eq(tier)].copy()
        tier_records = records[records["distance_tier"].eq(tier)].copy()
        tier_basins = basin_summary[basin_summary["basin"].isin(tier_counts["basin"])].copy()
        top = (
            tier_counts.merge(basin_summary[["basin", "gauge_name"]], on="basin", how="left")
            .sort_values(["record_count", "max_distance_iqr", "basin"], ascending=[False, False, True])
            .head(8)
        )
        row = {
            "distance_tier": tier,
            "distance_label": TIER_LABELS[tier],
            "record_count": int(len(tier_records)),
            "basin_count": int(tier_counts["basin"].nunique()),
            "top_basins_by_records": "; ".join(
                f"{item.basin} ({int(item.record_count)})" for item in top.itertuples(index=False)
            ),
        }
        for column in [
            "area",
            "obs_variance_denominator",
            "obs_q99",
            "q99_event_frequency",
            "rbi",
            "snow_fraction",
            "cold_season_event_fraction",
            "recent_precipitation_share",
            "antecedent_precipitation_share",
            "snowmelt_or_rain_on_snow_share",
            "uncertain_high_flow_candidate_share",
        ]:
            if column in tier_basins.columns:
                values = pd.to_numeric(tier_basins[column], errors="coerce")
                row[f"{column}_median"] = float(values.median(skipna=True))
        rows.append(row)
    return pd.DataFrame(rows)


def top_far_basin_text(records: pd.DataFrame, n: int = 5) -> str:
    far = records[records["is_far"]].copy()
    if far.empty:
        return ""
    counts = (
        far.groupby("basin", dropna=False)
        .agg(
            record_count=("metric_value", "size"),
            max_distance_iqr=("median_distance_iqr", "max"),
        )
        .reset_index()
        .sort_values(["record_count", "max_distance_iqr", "basin"], ascending=[False, False, True])
        .head(n)
    )
    return "; ".join(f"{row.basin} ({int(row.record_count)})" for row in counts.itertuples(index=False))


def build_model_seed_far_summary(records: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (model, seed), group in records.groupby(["model", "seed"], sort=True):
        far = group[group["is_far"]].copy()
        row = {
            "model": model,
            "seed": int(seed),
            "total_records": int(len(group)),
            "far_records": int(group["is_far"].sum()),
            "extreme_records": int(group["is_extreme"].sum()),
            "far_share": float(group["is_far"].mean()),
            "extreme_share": float(group["is_extreme"].mean()),
            "far_basin_count": int(far["basin"].nunique()),
            "extreme_basin_count": int(group.loc[group["is_extreme"], "basin"].nunique()),
            "mean_distance_iqr": float(pd.to_numeric(group["median_distance_iqr"], errors="coerce").mean()),
            "median_distance_iqr": float(pd.to_numeric(group["median_distance_iqr"], errors="coerce").median()),
            "max_distance_iqr": float(pd.to_numeric(group["median_distance_iqr"], errors="coerce").max()),
            "low_side_far_records": int((far["median_side"] == "low").sum()),
            "high_side_far_records": int((far["median_side"] == "high").sum()),
            "top_far_basins": top_far_basin_text(group),
        }
        for metric in METRICS:
            metric_group = group[group["metric"].eq(metric)]
            row[f"{metric}_far_records"] = int(metric_group["is_far"].sum())
            row[f"{metric}_extreme_records"] = int(metric_group["is_extreme"].sum())
        rows.append(row)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    mean_far = float(out["far_records"].mean())
    q25 = float(out["far_records"].quantile(0.25))
    q75 = float(out["far_records"].quantile(0.75))
    out["far_records_delta_vs_model_seed_mean"] = out["far_records"] - mean_far
    out["far_load_label"] = np.select(
        [out["far_records"].ge(q75), out["far_records"].le(q25)],
        ["higher far-load among model-seeds", "lower far-load among model-seeds"],
        default="middle far-load among model-seeds",
    )
    return out.sort_values(["far_records", "extreme_records", "model", "seed"], ascending=[False, False, True, True]).reset_index(drop=True)


def build_metric_model_seed_far_summary(records: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (metric, model, seed), group in records.groupby(["metric", "model", "seed"], sort=True):
        far = group[group["is_far"]].copy()
        rows.append(
            {
                "metric": metric,
                "model": model,
                "seed": int(seed),
                "total_records": int(len(group)),
                "far_records": int(group["is_far"].sum()),
                "extreme_records": int(group["is_extreme"].sum()),
                "far_share": float(group["is_far"].mean()),
                "extreme_share": float(group["is_extreme"].mean()),
                "far_basin_count": int(far["basin"].nunique()),
                "mean_distance_iqr": float(pd.to_numeric(group["median_distance_iqr"], errors="coerce").mean()),
                "median_distance_iqr": float(pd.to_numeric(group["median_distance_iqr"], errors="coerce").median()),
                "max_distance_iqr": float(pd.to_numeric(group["median_distance_iqr"], errors="coerce").max()),
                "low_side_far_records": int((far["median_side"] == "low").sum()),
                "high_side_far_records": int((far["median_side"] == "high").sum()),
                "top_far_basins": top_far_basin_text(group),
            }
        )
    return (
        pd.DataFrame(rows)
        .sort_values(["far_records", "extreme_records", "metric", "model", "seed"], ascending=[False, False, True, True, True])
        .reset_index(drop=True)
    )


def build_basin_model_seed_far_recurrence(records: pd.DataFrame) -> pd.DataFrame:
    far = records[records["is_far"]].copy()
    if far.empty:
        return pd.DataFrame()
    rows = []
    for basin, group in far.groupby("basin", sort=False):
        target_counts = (
            group.groupby(["model", "seed"], sort=True)
            .agg(
                far_records=("metric_value", "size"),
                extreme_records=("is_extreme", "sum"),
            )
            .reset_index()
        )
        metric_counts = group.groupby("metric").size().to_dict()
        rows.append(
            {
                "basin": normalize_basin_id(basin),
                "gauge_name": str(group["gauge_name"].dropna().iloc[0]) if group["gauge_name"].notna().any() else "",
                "far_model_seed_count": int(len(target_counts)),
                "total_far_records": int(group["is_far"].sum()),
                "total_extreme_records": int(group["is_extreme"].sum()),
                "NSE_far_records": int(metric_counts.get("NSE", 0)),
                "KGE_far_records": int(metric_counts.get("KGE", 0)),
                "FHV_far_records": int(metric_counts.get("FHV", 0)),
                "model_seed_breakdown": "; ".join(
                    f"{row.model} seed{int(row.seed)} ({int(row.far_records)})"
                    for row in target_counts.itertuples(index=False)
                ),
            }
        )
    return (
        pd.DataFrame(rows)
        .sort_values(["far_model_seed_count", "total_far_records", "total_extreme_records", "basin"], ascending=[False, False, False, True])
        .reset_index(drop=True)
    )


def percentile_rank_map(frame: pd.DataFrame, column: str) -> pd.Series:
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.rank(method="average", pct=True) * 100.0


def model2_effect_label(model1_far: float, model2_far: float, model1_mean: float, model2_mean: float) -> str:
    far_delta = model2_far - model1_far
    mean_delta = model2_mean - model1_mean
    if far_delta <= -3 and mean_delta < 0:
        return "Model 2 reduces distance"
    if far_delta >= 3 and mean_delta > 0:
        return "Model 2 increases distance"
    if model1_far >= 6 and model2_far >= 6:
        return "both models unstable"
    if abs(far_delta) <= 1:
        return "similar across models"
    return "mixed model effect"


def classify_flow_response(row: pd.Series) -> tuple[str, str, str]:
    area_p = float(row.get("area_percentile", np.nan))
    q99_p = float(row.get("obs_q99_percentile", np.nan))
    denom_p = float(row.get("obs_variance_denominator_percentile", np.nan))
    q99_freq_p = float(row.get("q99_event_frequency_percentile", np.nan))
    rbi_p = float(row.get("rbi_percentile", np.nan))
    duration_p = float(row.get("event_duration_median_hours_percentile", np.nan))
    recent_p = float(row.get("recent_precipitation_share_percentile", np.nan))
    antecedent_p = float(row.get("antecedent_precipitation_share_percentile", np.nan))
    snow_p = float(row.get("snowmelt_or_rain_on_snow_share_percentile", np.nan))
    uncertain_p = float(row.get("uncertain_high_flow_candidate_share_percentile", np.nan))
    hydromod = bool(row.get("hydromod_risk", False))
    pattern = str(row.get("metric_far_pattern", ""))

    low_scale = area_p <= 25 and q99_p <= 25 and denom_p <= 25
    small = area_p <= 25
    flashy = q99_freq_p >= 75 and rbi_p >= 70 and duration_p <= 30
    low_frequency_long = q99_freq_p <= 25 and rbi_p <= 25 and duration_p >= 75

    if small and flashy:
        return (
            "small_flashy_short_event",
            "supports small-flashy driver",
            "small area/Q99/NSE denominator plus high Q99-event frequency, high RBI, and short event duration",
        )
    if low_scale and antecedent_p >= 90 and uncertain_p >= 90:
        return (
            "low_scale_antecedent_uncertain",
            "supports scale driver; event mix is a caution",
            "low area/Q99/NSE denominator, but recent rainfall share is low and antecedent/uncertain shares are high",
        )
    if low_scale:
        return (
            "low_flow_scale_non_flashy",
            "supports scale driver",
            "low area/Q99/NSE denominator without high-frequency short-event response",
        )
    if "NSE/KGE/FHV=0/3/0" in pattern:
        return (
            "metric_specific_high_variability_snow",
            "individual diagnostic only",
            "KGE-only far pattern with high RBI and high snow/ROS share, but not low-scale or consistently flashy",
        )
    if low_frequency_long and hydromod:
        return (
            "regulated_low_frequency_long_duration",
            "individual diagnostic only",
            "low Q99-event frequency, low RBI, long event duration, and hydromod/storage context",
        )
    if hydromod and pattern.startswith("NSE/KGE/FHV=3/0/0"):
        return (
            "regulated_moderate_nse_only",
            "individual diagnostic only",
            "moderate-to-large basin with NSE-only far pattern and hydromod/canal context",
        )
    return (
        "moderate_or_sparse_isolated",
        "individual diagnostic only",
        "event-response indicators do not support a shared causal driver",
    )


def far_cause_lookup(basin: str) -> tuple[str, str, str]:
    lookup = {
        "01483200": (
            "A. scale/low-flow metric amplification",
            "very small area and lowest observed-flow scale",
            "Area, Q99, and NSE denominator are all at the bottom of the DRBC test distribution. NSE/KGE are low-side and FHV is high-side across all seeds/models, so modest absolute errors become very large normalized errors.",
        ),
        "01480400": (
            "A. scale/low-flow metric amplification",
            "small headwater with low observed-flow scale",
            "Same small/low-flow metric-amplification pattern as Blackbird. PA headwater conditions and storage/hydromod are context, but the supported outlier driver is still the low-flow scale and small metric denominator.",
        ),
        "01480675": (
            "A. scale/low-flow metric amplification",
            "small Marsh Creek upstream low-flow scale",
            "Small area and low Q99 dominate. Snow/ROS share is relatively high, but the repeated NSE/KGE low-side and FHV high-side pattern still points first to small-scale metric sensitivity.",
        ),
        "01480638": (
            "B. small flashy event-response amplification",
            "small basin plus high event frequency and short events",
            "Area and Q99 are low, but q99 event frequency and unit-area peak are high and event duration is short. This is a small-basin case where timing/flashiness likely amplifies the metric distance.",
        ),
        "01480685": (
            "A. scale/low-flow metric amplification",
            "low observed-flow scale with uncertain event context",
            "Area/Q99 and NSE denominator are still low enough to support scale amplification as the main driver. The unusual antecedent/uncertain event mix and hydromod context are kept as cautions, not as a separate causal group.",
        ),
        "01477800": (
            "B. small flashy event-response amplification",
            "highest RBI and highest q99 event frequency",
            "This basin is also small, but size alone is not the distinguishing driver. RBI, q99 event frequency, and unit-area peak are extreme, with very short events and hydromod/urban context. Peak timing and high-flow bias sensitivity are likely central.",
        ),
        "01475850": (
            "B. small flashy event-response amplification",
            "frequent short high-flow events",
            "Q99 event frequency, RBI, and unit-area peak are high with short event duration. The basin is still small enough for metric sensitivity, but the feature that separates it from the low-flow-scale group is flashy event response.",
        ),
        "01478120": (
            "B. small flashy event-response amplification",
            "weaker but related frequent-event response",
            "Dominant bin is still near-median, so this is not a persistent failure basin. The far records align with the same frequent/flashy White Clay style response, making it a weaker member of the flashy group.",
        ),
        "01451800": (
            "C. no shared causal driver assigned",
            "moderate basin with sparse far records; individual review only",
            "Area, Q99, and NSE denominator are mid-range, and far records are sparse across metrics. This should be treated as isolated sensitivity rather than a size-driven group member.",
        ),
        "01460880": (
            "C. no shared causal driver assigned",
            "KGE-only far pattern; individual component check only",
            "The basin is not particularly small and has higher Q99. Far records are KGE-specific; high RBI and snow/ROS are useful diagnostics, but not enough to define a separate causal group.",
        ),
        "01470779": (
            "C. no shared causal driver assigned",
            "NSE-only far pattern; individual regulated-system check only",
            "The basin is moderate-to-large, with no KGE/FHV far records. NSE-only low-side distance plus hydromod/canal context suggests a center-hydrograph/variance issue, but not a shared far-basin driver.",
        ),
        "01469500": (
            "C. no shared causal driver assigned",
            "single KGE far record; weak evidence",
            "Only one far record appears, and the basin has storage/dam influence plus high snow/ROS share. Evidence is too weak for a group; keep as single-metric sensitivity.",
        ),
        "01470960": (
            "C. no shared causal driver assigned",
            "single NSE far record in a large regulated basin; weak evidence",
            "This is the clearest non-size exception: large area, high Q99, high NSE denominator, low event frequency, and major dam/storage context. The single NSE far record should be interpreted as regulated-system sensitivity.",
        ),
    }
    return lookup.get(
        basin,
        (
            "C. no shared causal driver assigned",
            "manual review needed",
            "The basin has far records but does not match the supported shared outlier-driver groups.",
        ),
    )


def build_far_cause_diagnosis(
    basin_summary: pd.DataFrame,
    basin_model_tier_profile: pd.DataFrame,
) -> pd.DataFrame:
    far = basin_summary[basin_summary["total_far_records"].gt(0)].copy()
    percentile_features = [
        "area",
        "obs_variance_denominator",
        "obs_q99",
        "q99_event_frequency",
        "rbi",
        "event_duration_median_hours",
        "annual_peak_unit_area_p90",
        "recent_precipitation_share",
        "antecedent_precipitation_share",
        "snowmelt_or_rain_on_snow_share",
        "uncertain_high_flow_candidate_share",
    ]
    for column in percentile_features:
        if column in basin_summary.columns:
            lookup = percentile_rank_map(basin_summary, column)
            lookup.index = basin_summary["basin"]
            far[f"{column}_percentile"] = far["basin"].map(lookup)

    model = basin_model_tier_profile.pivot(index="basin", columns="model", values=["far_or_extreme_records", "mean_distance_any_metric_seed"])
    model.columns = [f"{name}_{model_name}" for name, model_name in model.columns]
    model = model.reset_index()
    far = far.merge(model, on="basin", how="left")
    far["model2_far_record_delta"] = far["far_or_extreme_records_model2"] - far["far_or_extreme_records_model1"]
    far["model2_mean_distance_delta"] = (
        far["mean_distance_any_metric_seed_model2"] - far["mean_distance_any_metric_seed_model1"]
    )
    far["model_effect"] = far.apply(
        lambda row: model2_effect_label(
            row["far_or_extreme_records_model1"],
            row["far_or_extreme_records_model2"],
            row["mean_distance_any_metric_seed_model1"],
            row["mean_distance_any_metric_seed_model2"],
        ),
        axis=1,
    )

    causes = far["basin"].map(lambda basin: far_cause_lookup(str(basin)))
    far["cause_group"] = causes.map(lambda value: value[0])
    far["primary_cause"] = causes.map(lambda value: value[1])
    far["interpretation_note"] = causes.map(lambda value: value[2])
    far["metric_far_pattern"] = far.apply(
        lambda row: f"NSE/KGE/FHV={int(row['NSE_far_records'])}/{int(row['KGE_far_records'])}/{int(row['FHV_far_records'])}",
        axis=1,
    )
    flow_response = far.apply(lambda row: classify_flow_response(row), axis=1)
    far["flow_response_type"] = flow_response.map(lambda value: value[0])
    far["event_response_support"] = flow_response.map(lambda value: value[1])
    far["event_response_evidence"] = flow_response.map(lambda value: value[2])
    far["side_pattern"] = far.apply(
        lambda row: (
            f"NSE low {int(row['NSE_low_side_records'])}/6; "
            f"KGE low {int(row['KGE_low_side_records'])}/6; "
            f"FHV high {int(row['FHV_high_side_records'])}/6"
        ),
        axis=1,
    )

    keep = [
        "basin",
        "gauge_name",
        "cause_group",
        "primary_cause",
        "interpretation_note",
        "flow_response_type",
        "event_response_support",
        "event_response_evidence",
        "total_far_records",
        "total_extreme_records",
        "NSE_far_records",
        "KGE_far_records",
        "FHV_far_records",
        "NSE_low_side_records",
        "KGE_low_side_records",
        "FHV_high_side_records",
        "metric_far_pattern",
        "side_pattern",
        "model_effect",
        "far_or_extreme_records_model1",
        "far_or_extreme_records_model2",
        "model2_far_record_delta",
        "mean_distance_any_metric_seed_model1",
        "mean_distance_any_metric_seed_model2",
        "model2_mean_distance_delta",
        "area",
        "area_percentile",
        "obs_q99",
        "obs_q99_percentile",
        "obs_variance_denominator",
        "obs_variance_denominator_percentile",
        "q99_event_frequency",
        "q99_event_frequency_percentile",
        "rbi",
        "rbi_percentile",
        "event_duration_median_hours",
        "event_duration_median_hours_percentile",
        "annual_peak_unit_area_p90",
        "annual_peak_unit_area_p90_percentile",
        "recent_precipitation_share",
        "recent_precipitation_share_percentile",
        "antecedent_precipitation_share",
        "antecedent_precipitation_share_percentile",
        "snowmelt_or_rain_on_snow_share",
        "snowmelt_or_rain_on_snow_share_percentile",
        "uncertain_high_flow_candidate_share",
        "uncertain_high_flow_candidate_share_percentile",
        "hydromod_risk",
        "NDAMS_2009",
        "STOR_NOR_2009",
        "MAJ_NDAMS_2009",
        "CANALS_PCT",
        "FRESHW_WITHDRAWAL",
        "FLOW_PCT_EST_VALUES",
    ]
    return (
        far[[col for col in keep if col in far.columns]]
        .sort_values(["cause_group", "total_far_records", "area"], ascending=[True, False, True])
        .reset_index(drop=True)
    )


def build_far_cause_group_summary(far_cause: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cause_group, group in far_cause.groupby("cause_group", sort=True):
        if cause_group == "A. scale/low-flow metric amplification":
            shared_interpretation = (
                "low area/Q99/NSE denominator repeatedly amplifies normalized metric distance"
            )
        elif cause_group == "B. small flashy event-response amplification":
            shared_interpretation = (
                "small basins where high Q99 event frequency/RBI and short events likely amplify timing and high-flow-volume errors"
            )
        elif cause_group == "C. no shared causal driver assigned":
            shared_interpretation = (
                "not treated as a causal subgroup; use individual diagnostics only"
            )
        else:
            shared_interpretation = " / ".join(sorted(group["primary_cause"].unique()))
        rows.append(
            {
                "cause_group": cause_group,
                "basin_count": int(group["basin"].nunique()),
                "basins": " ".join(group["basin"].tolist()),
                "median_area": float(pd.to_numeric(group["area"], errors="coerce").median()),
                "median_obs_q99": float(pd.to_numeric(group["obs_q99"], errors="coerce").median()),
                "median_q99_event_frequency": float(pd.to_numeric(group["q99_event_frequency"], errors="coerce").median()),
                "median_rbi": float(pd.to_numeric(group["rbi"], errors="coerce").median()),
                "median_total_far_records": float(pd.to_numeric(group["total_far_records"], errors="coerce").median()),
                "shared_interpretation": shared_interpretation,
            }
        )
    return pd.DataFrame(rows)


def fmt(value: Any, digits: int = 3) -> str:
    if pd.isna(value):
        return "NA"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(number) >= 1000:
        return f"{number:,.0f}"
    return f"{number:.{digits}f}"


def markdown_table(frame: pd.DataFrame, columns: list[str], labels: dict[str, str] | None = None) -> str:
    if frame.empty:
        return "해당 없음"
    labels = labels or {}
    out = frame[columns].copy()
    out = out.rename(columns=labels)
    lines = [
        "| " + " | ".join(out.columns) + " |",
        "| " + " | ".join(["---"] * len(out.columns)) + " |",
    ]
    for _, row in out.iterrows():
        values = []
        for value in row:
            if isinstance(value, float):
                values.append(fmt(value))
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def basin_interpretation(row: pd.Series) -> str:
    basin = row["basin"]
    name = row["gauge_name"]
    metric_pattern = (
        f"NSE/KGE/FHV far = {int(row['NSE_far_records'])}/"
        f"{int(row['KGE_far_records'])}/{int(row['FHV_far_records'])}"
    )
    regime = (
        f"snow = {fmt(row['snow_fraction'])}, winter-event = {fmt(row['cold_season_event_fraction'])}, "
        f"recent = {fmt(row['recent_precipitation_share'])}, antecedent = {fmt(row['antecedent_precipitation_share'])}, "
        f"snowmelt/ROS = {fmt(row['snowmelt_or_rain_on_snow_share'])}"
    )
    flow = (
        f"area = {fmt(row['area'])} km2, NSE denom = {fmt(row['obs_variance_denominator'])}, "
        f"Q99 = {fmt(row['obs_q99'])}, RBI = {fmt(row['rbi'])}, "
        f"Q99 freq = {fmt(row['q99_event_frequency'])}/yr, duration = {fmt(row['event_duration_median_hours'])} h"
    )

    if basin == "01483200":
        reason = (
            "가장 작은 저유량 DE basin입니다. winter 비율은 중간이지만 snow fraction이 다른 small-basin들과 다르게 매우 낮아서 별도 해석이 맞고, "
            "median에서 멀어진 원인은 regime 전환보다 작은 분모와 낮은 peak scale에 더 가깝습니다."
        )
    elif basin == "01480400":
        reason = (
            "Blackbird와 같은 small/low-variance 문제지만 snow fraction이 더 높고 PA headwater라 같은 regime으로 묶지 않았습니다. "
            "NSE/KGE는 낮은 쪽, FHV는 높은 쪽으로 모든 seed/model에서 반복됩니다."
        )
    elif basin == "01480675":
        reason = (
            "Marsh Creek pair 중 상류 Glenmoore입니다. snow/winter 비율은 Downingtown과 비슷하지만 recent precipitation share가 0.821로 높고 "
            "uncertain share가 낮아 event-generation mix가 달라 별도 해석해야 합니다."
        )
    elif basin == "01480685":
        reason = (
            "Downingtown은 Glenmoore와 static snow/winter는 비슷해도 recent share가 0.170, antecedent share가 0.311, uncertain share가 0.453입니다. "
            "같은 Marsh 계열로 묶으면 중요한 flow-regime 차이를 잃습니다."
        )
    elif basin == "01480638":
        reason = (
            "짧은 event duration, 높은 unit-area peak p90, 높은 q99 event frequency가 같이 있는 flashy small basin입니다. "
            "Crum/White Clay와 snow fraction은 비슷하지만 winter-event fraction이 낮아 별도 처리했습니다."
        )
    elif basin == "01477800":
        reason = (
            "Shellpot은 urban/developed 성격과 매우 높은 RBI가 핵심입니다. snow/winter 비율과 recent/uncertain mix가 Blackbird와 달라 DE small basin으로 단순 묶지 않았습니다."
        )
    elif basin == "01451800":
        reason = (
            "면적과 유량 분모가 small-headwater group보다 크고, far record는 세 metric에서 각각 1개씩만 나타납니다. "
            "snow 비율은 높은 편이지만 winter/event mix가 다른 basin들과 정확히 맞지 않아 개별 moderate case입니다."
        )
    elif basin == "01470779":
        reason = (
            "NSE에서만 median-distance가 생긴 crop-dominant/regulated 영향 basin입니다. KGE/FHV가 같은 방식으로 벌어지지 않으므로 multi-metric regime group에 넣지 않았습니다."
        )
    elif basin == "01460880":
        reason = (
            "KGE 전용 far case입니다. winter-event fraction과 snowmelt/ROS share가 가장 높아 snow/cold signal은 있지만, NSE/FHV far가 반복되지 않아 개별 KGE sensitivity로 보는 편이 안전합니다."
        )
    elif basin == "01470960":
        reason = (
            "NSE single far record입니다. Blue Marsh dam 영향이 크고 basin scale도 중간 이상이라 small-basin group과 다릅니다."
        )
    elif basin == "01469500":
        reason = (
            "KGE single far record입니다. snow/cold 비율과 event-response가 반복 far basin들과 맞지 않아 group evidence가 약합니다."
        )
    else:
        reason = "반복성이나 ratio match가 부족해 개별 basin으로 해석했습니다."

    return (
        f"### {basin} | {name}\n\n"
        f"- `{metric_pattern}`\n"
        f"- `Regime`: {regime}\n"
        f"- `Flow/event scale`: {flow}\n\n"
        f"{reason}"
    )


def detailed_far_note_text(basin: str) -> str:
    notes = {
        "01483200": (
            "이 basin은 far 패턴을 가장 강하게 정의하는 기준점에 가깝습니다. 면적, Q99, NSE denominator가 모두 DRBC test set의 최하위권이라 "
            "유량 scale 자체가 작고, 이 때문에 작은 절대 오차도 NSE/KGE에서는 큰 skill 저하로, FHV에서는 큰 high-flow volume bias로 확대됩니다. "
            "특히 NSE와 KGE는 모든 record에서 median보다 낮은 쪽이고 FHV는 모든 record에서 높은 쪽이라, 단일 seed 문제가 아니라 scale-normalized metric이 "
            "작은 저유량 basin에서 일관되게 민감하게 반응한 사례로 보는 게 맞습니다. Model 2가 평균 거리는 줄이지만 far count는 그대로라, quantile head만으로 "
            "이 basin의 scale 문제를 해소하지는 못합니다."
        ),
        "01480400": (
            "Blackbird와 같은 small/low-flow amplification 그룹이지만, 단순히 같은 DE lowland basin으로 묶으면 안 됩니다. 이 basin은 PA headwater이고 "
            "storage/hydromod flag가 있어 small basin scale과 조절 영향이 함께 걸려 있습니다. NSE/KGE low-side와 FHV high-side가 반복되는 점은 "
            "01483200과 같지만, snow/ROS 비중과 저장시설 맥락이 더 크기 때문에 같은 원인이라기보다 같은 metric 증폭 구조를 공유한다고 해석하는 편이 안전합니다. "
            "Model 2에서 평균 distance는 크게 줄었지만 여전히 모든 model-seed record가 far 이상이라, 구조적 안정화라기보다 정도 완화에 가깝습니다."
        ),
        "01480675": (
            "Marsh Creek 상류 basin으로, 면적과 Q99가 낮은 small-basin 문제가 여전히 1차 원인입니다. 다만 snow/ROS share가 높은 편이라 작은 유역 scale에 "
            "winter 또는 mixed cold-season response가 일부 얹혀 있을 가능성이 있습니다. Glenmoore는 NSE/KGE low-side와 FHV high-side가 동시에 반복되므로 "
            "중심 hydrograph skill과 high-flow volume bias가 같은 방향으로 불안정합니다. Model 2는 far count를 조금 줄이지만 여전히 unstable group에 남기 때문에, "
            "output design 개선만으로는 상류 small-scale response를 충분히 흡수하지 못한 사례입니다."
        ),
        "01480638": (
            "Broad Run은 small-basin 그룹에 속하지만, 원인을 size 하나로 끝내면 중요한 신호를 놓칩니다. area와 Q99는 낮은데 Q99 event frequency, RBI, "
            "annual peak unit-area p90이 모두 높은 편이고 event duration도 매우 짧습니다. 즉 유량 scale은 작고 event는 자주 빠르게 발생하므로, hourly prediction에서 "
            "timing이 조금만 어긋나도 NSE/KGE와 FHV가 함께 멀어질 수 있습니다. Model 2가 far count를 줄이는 점은 output distribution이 일부 도움을 준다는 뜻이지만, "
            "flashy timing 문제까지 해결했다는 뜻은 아닙니다."
        ),
        "01480685": (
            "Downingtown은 같은 Marsh 계열이라 Glenmoore와 묶고 싶지만, event-generation mix가 확연히 다릅니다. recent-rain share는 매우 낮고 antecedent share와 "
            "uncertain share가 최상위권이라, 단기 강우 반응보다는 antecedent storage, 조절 영향, 또는 event classification uncertainty가 더 크게 작동했을 가능성이 큽니다. "
            "면적과 Q99도 낮은 편이므로 small-flow scale 문제가 완전히 사라지는 것은 아니지만, 이 basin의 far pattern은 scale만으로 설명하기 어렵습니다. "
            "Model 2에서 distance가 줄어드는 것은 확인되지만, regime-mix와 hydromod context는 보조 맥락으로만 두고 별도 원인군으로 올리지는 않았습니다."
        ),
        "01477800": (
            "Shellpot은 면적도 작은 편이지만, 단순한 small-flow scale만으로는 설명이 부족한 사례입니다. RBI와 Q99 event frequency가 모두 DRBC test set 최상위이고, event duration도 가장 짧은 축입니다. "
            "이런 basin에서는 peak timing이 몇 시간만 어긋나도 NSE/KGE가 낮아지고 FHV가 과하게 흔들릴 수 있습니다. Model 2에서 far count와 extreme 정도가 크게 줄어드는 것은 "
            "probabilistic output이 peak magnitude bias를 완화했을 가능성을 보여주지만, 도시성/flashy timing 문제 자체는 backbone과 forcing resolution 쪽 한계로 남습니다."
        ),
        "01475850": (
            "Crum Creek은 Shellpot보다는 덜 극단적이지만, 원인 구조는 flashy high-frequency response 쪽에 가깝습니다. Q99 event frequency, RBI, unit-area peak가 모두 높은 편이고 "
            "event duration도 짧아서, 작은 basin scale 위에 빠르고 잦은 event 반응이 성능 거리를 더 키우는 축으로 보입니다. FHV high-side record가 강하므로 peak volume 또는 high-flow volume이 "
            "과대/불안정하게 반응한 가능성이 큽니다. Model 2의 개선은 일부 있지만 크지 않아, quantile head가 모든 event timing/shape 문제를 해결하지는 못한 transitional case로 보입니다."
        ),
        "01478120": (
            "East Branch White Clay는 far basin 목록에 들어오지만 persistent failure basin은 아닙니다. 전체 18개 record 중 near-median record가 가장 많고, far/extreme은 일부 metric/model/seed에 제한됩니다. "
            "다만 Q99 event frequency와 RBI가 높은 편이라 Crum Creek과 같은 frequent/flashy response family에 놓을 수 있습니다. 따라서 이 basin은 '실패 유역'이라기보다, "
            "특정 seed 또는 metric에서 flashy small basin 특성이 드러나는 약한 멤버로 해석하는 게 좋습니다. Model 1/2 차이도 뚜렷하지 않아 output design claim의 핵심 증거로 쓰기에는 약합니다."
        ),
        "01451800": (
            "Jordan Creek은 size-driven far basin이 아닙니다. area, Q99, NSE denominator가 모두 중간권이고 far record도 NSE/KGE/FHV에서 각각 1개씩만 나타납니다. "
            "따라서 이 basin을 small-basin group에 넣으면 오히려 해석이 흐려집니다. Model 2에서는 far record가 사라지므로, 이 basin의 far signal은 구조적 hydrologic regime이라기보다 "
            "Model 1 또는 특정 seed에서 생긴 제한적 sensitivity일 가능성이 큽니다. 본문에서는 robustness check 또는 isolated case로만 다루는 편이 안전합니다."
        ),
        "01460880": (
            "Lockatong은 KGE 전용 far case입니다. NSE와 FHV는 far로 반복되지 않으므로 전체 hydrograph skill이나 high-flow volume bias가 동시에 무너졌다고 보기 어렵습니다. "
            "대신 RBI와 snow/ROS share가 높은 편이라 KGE의 correlation/variability component가 snow/cold-season 또는 flashy variability에 민감하게 반응했을 가능성이 있습니다. "
            "area와 Q99도 small group보다 크기 때문에 size 설명은 약합니다. 따라서 이 신호는 공유 원인군이 아니라 KGE component decomposition 또는 hydrograph variability 진단으로 따로 확인하는 게 맞습니다."
        ),
        "01470779": (
            "Tulpehocken near Bernville은 NSE에서만 far가 반복되는 regulated/moderate basin입니다. 면적은 중상위권이고 Q99도 낮지 않으므로 small-flow metric amplification과는 거리가 있습니다. "
            "KGE와 FHV가 같은 방식으로 멀어지지 않는다는 점은 peak volume 문제가 아니라, NSE denominator와 중심 hydrograph shape 또는 조절 영향이 결합된 문제일 가능성을 시사합니다. "
            "다만 canal/hydromod 자체를 far의 원인군으로 올리기에는 evidence가 부족하므로, 이 basin은 event-scale peak 분석보다 전체 시계열 residual과 regulated release pattern을 개별 확인하는 쪽이 더 적절합니다."
        ),
        "01469500": (
            "Little Schuylkill은 evidence가 가장 약한 single-metric case 중 하나입니다. far record는 KGE 1개뿐이고, Q99 event frequency와 RBI는 낮은 편이며 event duration은 깁니다. "
            "즉 flashy event 실패라기보다 특정 model/seed에서 KGE component가 흔들린 사례에 가깝습니다. 다만 dam/storage와 snow/ROS share가 높아 regulated snow-influenced response의 가능성은 남습니다. "
            "반복성이 약하므로 그룹 결론의 근거로 쓰기보다는 예외 사례로 보조적으로만 언급하는 게 좋습니다."
        ),
        "01470960": (
            "Blue Marsh Damsite는 small-basin 가설을 반대로 검증해 주는 예외입니다. area, Q99, NSE denominator가 모두 큰 편이고 event frequency와 RBI는 낮으며 duration은 매우 깁니다. "
            "그런데도 단일 NSE far record가 생긴 것은 flood peak scale 문제가 아니라 large regulated basin의 storage/release dynamics, antecedent condition, 또는 smooth hydrograph mismatch 쪽으로 봐야 합니다. "
            "Model 2에서만 far record가 나타나는 점도 output design 개선의 대표 사례가 아니라, large regulated system에서 특정 run이 중심 hydrograph를 다르게 맞춘 isolated signal로 보는 편이 안전합니다."
        ),
    }
    return notes.get(basin, "반복성이나 ratio match가 부족해 개별 basin으로 해석했습니다.")


def detailed_far_basin_interpretation(row: pd.Series) -> str:
    basin = str(row["basin"])
    name = row["gauge_name"]
    hydromod = "yes" if bool(row.get("hydromod_risk", False)) else "no"
    storage = fmt(row.get("STOR_NOR_2009", np.nan))
    canals = fmt(row.get("CANALS_PCT", np.nan))
    withdrawal = fmt(row.get("FRESHW_WITHDRAWAL", np.nan))
    estimated = fmt(row.get("FLOW_PCT_EST_VALUES", np.nan))

    return (
        f"### {basin} | {name}\n\n"
        f"- `Far pattern`: {row['metric_far_pattern']}; total far/extreme = {int(row['total_far_records'])}/{int(row['total_extreme_records'])}\n"
        f"- `Metric side`: {row['side_pattern']}\n"
        f"- `Scale percentile`: area = {fmt(row['area_percentile'])}p, Q99 = {fmt(row['obs_q99_percentile'])}p, "
        f"NSE denom = {fmt(row['obs_variance_denominator_percentile'])}p\n"
        f"- `Event/regime percentile`: Q99 freq = {fmt(row['q99_event_frequency_percentile'])}p, RBI = {fmt(row['rbi_percentile'])}p, "
        f"duration = {fmt(row['event_duration_median_hours_percentile'])}p, recent = {fmt(row['recent_precipitation_share_percentile'])}p, "
        f"antecedent = {fmt(row['antecedent_precipitation_share_percentile'])}p, snow/ROS = {fmt(row['snowmelt_or_rain_on_snow_share_percentile'])}p, "
        f"uncertain = {fmt(row['uncertain_high_flow_candidate_share_percentile'])}p\n"
        f"- `Flow response check`: {row['flow_response_type']}; {row['event_response_support']}; {row['event_response_evidence']}\n"
        f"- `Model comparison`: {row['model_effect']}; Model 1 far = {int(row['far_or_extreme_records_model1'])}, "
        f"Model 2 far = {int(row['far_or_extreme_records_model2'])}, mean-distance delta = {fmt(row['model2_mean_distance_delta'])}\n"
        f"- `Hydromod/data`: hydromod = {hydromod}, storage = {storage}, canals = {canals}, withdrawal = {withdrawal}, estimated-flow = {estimated}%\n\n"
        f"{detailed_far_note_text(basin)}"
    )


def korean_cause_label(value: Any) -> str:
    text = str(value)
    labels = {
        "A. scale/low-flow metric amplification": "작은 유량 scale과 metric denominator 증폭",
        "B. small flashy event-response amplification": "small flashy event-response 증폭",
        "C. no shared causal driver assigned": "공유 원인군으로 묶지 않은 개별 검토 대상",
    }
    return labels.get(text, text)


def korean_flow_response_label(value: Any) -> str:
    text = str(value)
    labels = {
        "low_flow_scale_non_flashy": "저유량 scale 지배형",
        "low_scale_antecedent_uncertain": "저유량 scale + antecedent/uncertain event형",
        "small_flashy_short_event": "작은 flashy short-event형",
        "metric_specific_high_variability_snow": "metric-specific high-variability/snow형",
        "regulated_low_frequency_long_duration": "regulated low-frequency long-duration형",
        "regulated_moderate_nse_only": "regulated moderate NSE-only형",
        "moderate_or_sparse_isolated": "중간 scale 또는 sparse isolated형",
    }
    return labels.get(text, text)


def korean_event_response_support_label(value: Any) -> str:
    text = str(value)
    labels = {
        "supports scale driver": "event-response가 scale driver 해석을 지지",
        "supports scale driver; event mix is a caution": "scale driver는 지지하지만 event mix는 주의",
        "supports small-flashy driver": "event-response가 small-flashy driver 해석을 지지",
        "individual diagnostic only": "공유 driver가 아니라 개별 진단 대상으로만 사용",
    }
    return labels.get(text, text)


def korean_event_response_evidence_label(value: Any) -> str:
    text = str(value)
    labels = {
        "small area/Q99/NSE denominator plus high Q99-event frequency, high RBI, and short event duration": "작은 area/Q99/NSE denominator에 높은 Q99 event 빈도, 높은 RBI, 짧은 duration이 함께 나타남",
        "low area/Q99/NSE denominator, but recent rainfall share is low and antecedent/uncertain shares are high": "area/Q99/NSE denominator는 낮지만 recent rain share가 낮고 antecedent/uncertain share가 높음",
        "low area/Q99/NSE denominator without high-frequency short-event response": "area/Q99/NSE denominator는 낮지만 high-frequency short-event 반응은 강하지 않음",
        "KGE-only far pattern with high RBI and high snow/ROS share, but not low-scale or consistently flashy": "KGE-only far이며 RBI와 snow/ROS는 높지만 low-scale 또는 일관된 flashy driver는 아님",
        "low Q99-event frequency, low RBI, long event duration, and hydromod/storage context": "Q99 event 빈도와 RBI가 낮고 duration이 길며 hydromod/storage 맥락이 있음",
        "moderate-to-large basin with NSE-only far pattern and hydromod/canal context": "중대형 basin에서 NSE-only far와 hydromod/canal 맥락이 함께 나타남",
        "event-response indicators do not support a shared causal driver": "event-response 지표만으로는 공유 causal driver를 지지하지 않음",
    }
    return labels.get(text, text)


def flow_response_check_frame(far_cause_diagnosis: pd.DataFrame) -> pd.DataFrame:
    frame = far_cause_diagnosis.copy()
    frame["driver_group_ko"] = frame["cause_group"].map(korean_cause_label)
    frame["flow_response_type_ko"] = frame["flow_response_type"].map(korean_flow_response_label)
    frame["event_response_support_ko"] = frame["event_response_support"].map(korean_event_response_support_label)
    frame["event_response_evidence_ko"] = frame["event_response_evidence"].map(korean_event_response_evidence_label)
    return frame


def driver_short_label(value: Any) -> str:
    text = str(value)
    labels = {
        "A. scale/low-flow metric amplification": "A scale/low-flow",
        "B. small flashy event-response amplification": "B small flashy",
        "C. no shared causal driver assigned": "C individual",
    }
    return labels.get(text, text)


def save_png_svg(fig: plt.Figure, output_base: Path) -> list[Path]:
    output_base.parent.mkdir(parents=True, exist_ok=True)
    paths = [output_base.with_suffix(".png"), output_base.with_suffix(".svg")]
    for path in paths:
        fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return paths


def far_plot_frame(
    basin_tier_profile: pd.DataFrame,
    far_cause_diagnosis: pd.DataFrame,
    seed_metric_changes: pd.DataFrame | None = None,
    basin_metric_model_far_counts: pd.DataFrame | None = None,
) -> pd.DataFrame:
    tier_cols = [
        "near_median_lt_0_5_iqr",
        "shoulder_0_5_to_1_5_iqr",
        "far_1_5_to_3_iqr",
        "extreme_ge_3_iqr",
        "far_or_extreme_records",
        "mean_distance_any_metric_seed",
        "max_distance_any_metric_seed",
    ]
    left = far_cause_diagnosis[
        [
            "basin",
            "gauge_name",
            "cause_group",
            "flow_response_type",
            "event_response_support",
            "total_far_records",
            "total_extreme_records",
            "area_percentile",
            "obs_q99_percentile",
            "obs_variance_denominator_percentile",
            "q99_event_frequency_percentile",
            "rbi_percentile",
            "event_duration_median_hours_percentile",
            "recent_precipitation_share_percentile",
            "antecedent_precipitation_share_percentile",
            "snowmelt_or_rain_on_snow_share_percentile",
            "uncertain_high_flow_candidate_share_percentile",
            "far_or_extreme_records_model1",
            "far_or_extreme_records_model2",
            "NSE_far_records",
            "KGE_far_records",
            "FHV_far_records",
        ]
    ].copy()
    right = basin_tier_profile[["basin", *tier_cols]].copy()
    frame = left.merge(right, on="basin", how="left")
    frame["basin"] = frame["basin"].map(normalize_basin_id)
    if seed_metric_changes is not None and not seed_metric_changes.empty:
        changes = seed_metric_changes.copy()
        changes["basin"] = changes["basin"].map(normalize_basin_id)
        frame = frame.merge(changes, on="basin", how="left")
    if basin_metric_model_far_counts is not None and not basin_metric_model_far_counts.empty:
        metric_model_counts = basin_metric_model_far_counts.copy()
        metric_model_counts["basin"] = metric_model_counts["basin"].map(normalize_basin_id)
        frame = frame.merge(metric_model_counts, on="basin", how="left")
    for seed in SEEDS:
        column = f"seed{seed}_metric_change"
        if column not in frame.columns:
            frame[column] = "="
        frame[column] = frame[column].fillna("=")
    for metric in METRICS:
        for model in MODELS:
            column = f"{metric}_{model}_far_records"
            if column not in frame.columns:
                frame[column] = 0
            frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0).astype(int)
    return frame


def all_basin_tier_plot_frame(basin_tier_profile: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "basin",
        "gauge_name",
        *TIER_ORDER,
        "far_or_extreme_records",
        "mean_distance_any_metric_seed",
        "max_distance_any_metric_seed",
    ]
    frame = basin_tier_profile[[col for col in cols if col in basin_tier_profile.columns]].copy()
    frame["basin"] = frame["basin"].map(normalize_basin_id)
    return frame


def bool_value(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes", "y"}
    return bool(value)


def format_seed_metric_change(
    records: pd.DataFrame,
    seed: int,
) -> str:
    added_far: list[str] = []
    added_extreme: list[str] = []
    dropped_far: list[str] = []
    dropped_extreme: list[str] = []
    tier_up: list[str] = []
    tier_down: list[str] = []
    for metric in METRICS:
        metric_seed = records[records["metric"].eq(metric) & records["seed"].eq(seed)]
        model1 = metric_seed[metric_seed["model"].eq("model1")]
        model2 = metric_seed[metric_seed["model"].eq("model2")]
        if model1.empty or model2.empty:
            continue
        row1 = model1.iloc[0]
        row2 = model2.iloc[0]
        model1_far = bool_value(row1["is_far"])
        model2_far = bool_value(row2["is_far"])
        model1_extreme = bool_value(row1["is_extreme"])
        model2_extreme = bool_value(row2["is_extreme"])
        if model2_far and not model1_far:
            if model2_extreme:
                added_extreme.append(metric)
            else:
                added_far.append(metric)
        elif model1_far and not model2_far:
            if model1_extreme:
                dropped_extreme.append(metric)
            else:
                dropped_far.append(metric)
        elif model1_far and model2_far and str(row1["distance_tier"]) != str(row2["distance_tier"]):
            tier1 = str(row1["distance_tier"])
            tier2 = str(row2["distance_tier"])
            if tier1 == "far_1_5_to_3_iqr" and tier2 == "extreme_ge_3_iqr":
                tier_up.append(metric)
            elif tier1 == "extreme_ge_3_iqr" and tier2 == "far_1_5_to_3_iqr":
                tier_down.append(metric)

    pieces = []
    for prefix, metrics in [
        ("+", added_far),
        ("++", added_extreme),
        ("-", dropped_far),
        ("--", dropped_extreme),
        ("↑", tier_up),
        ("↓", tier_down),
    ]:
        if metrics:
            pieces.append(prefix + "".join(METRIC_SHORT_LABELS[metric] for metric in metrics))
    return " ".join(pieces) if pieces else "="


def build_seed_metric_change_labels(records: pd.DataFrame) -> pd.DataFrame:
    rows = []
    work = records.copy()
    work["basin"] = work["basin"].map(normalize_basin_id)
    for basin, group in work.groupby("basin", sort=False):
        row = {"basin": basin}
        for seed in SEEDS:
            row[f"seed{seed}_metric_change"] = format_seed_metric_change(group, seed)
        rows.append(row)
    return pd.DataFrame(rows)


def build_basin_metric_model_far_counts(records: pd.DataFrame) -> pd.DataFrame:
    work = records.copy()
    work["basin"] = work["basin"].map(normalize_basin_id)
    work["is_far"] = work["is_far"].map(bool_value)
    counts = (
        work[work["is_far"]]
        .groupby(["basin", "metric", "model"], dropna=False)
        .size()
        .rename("far_records")
        .reset_index()
    )
    if counts.empty:
        return pd.DataFrame({"basin": sorted(work["basin"].dropna().unique())})

    wide = counts.pivot_table(
        index="basin",
        columns=["metric", "model"],
        values="far_records",
        fill_value=0,
        aggfunc="sum",
    )
    wide.columns = [f"{metric}_{model}_far_records" for metric, model in wide.columns]
    wide = wide.reset_index()
    basins = pd.DataFrame({"basin": sorted(work["basin"].dropna().unique())})
    out = basins.merge(wide, on="basin", how="left")
    for metric in METRICS:
        for model in MODELS:
            column = f"{metric}_{model}_far_records"
            if column not in out.columns:
                out[column] = 0
            out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0).astype(int)
    ordered_columns = ["basin", *[f"{metric}_{model}_far_records" for metric in METRICS for model in MODELS]]
    return out[ordered_columns]


def seed_metric_change_count_delta(label: Any) -> int:
    text = "" if pd.isna(label) else str(label).strip()
    if not text or text == "=":
        return 0
    delta = 0
    for token in text.split():
        if not token:
            continue
        metric_count = sum(1 for char in token[1:] if char in set(METRIC_SHORT_LABELS.values()))
        if token.startswith("+"):
            delta += metric_count
        elif token.startswith("-"):
            delta -= metric_count
    return delta


def build_seed_metric_change_count_check(
    far_cause_diagnosis: pd.DataFrame,
    seed_metric_changes: pd.DataFrame,
) -> pd.DataFrame:
    frame = far_cause_diagnosis[
        ["basin", "far_or_extreme_records_model1", "far_or_extreme_records_model2"]
    ].copy()
    frame["basin"] = frame["basin"].map(normalize_basin_id)
    for column in ["far_or_extreme_records_model1", "far_or_extreme_records_model2"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0).astype(int)
    changes = seed_metric_changes.copy()
    changes["basin"] = changes["basin"].map(normalize_basin_id)
    frame = frame.merge(changes, on="basin", how="left")
    for seed in SEEDS:
        label_col = f"seed{seed}_metric_change"
        delta_col = f"seed{seed}_count_delta"
        frame[label_col] = frame[label_col].fillna("=")
        frame[delta_col] = frame[label_col].map(seed_metric_change_count_delta)
    seed_delta_cols = [f"seed{seed}_count_delta" for seed in SEEDS]
    frame["label_net_count_delta"] = frame[seed_delta_cols].sum(axis=1)
    frame["model_count_delta"] = frame["far_or_extreme_records_model2"] - frame["far_or_extreme_records_model1"]
    frame["count_delta_matches"] = frame["label_net_count_delta"].eq(frame["model_count_delta"])
    return frame.sort_values(["count_delta_matches", "basin"], ascending=[True, True]).reset_index(drop=True)


def save_distance_tier_stacked_bar(
    frame: pd.DataFrame,
    output_base: Path,
    *,
    title: str,
    xlabel: str,
    figure_width: float,
    x_rotation: int = 45,
    x_tick_fontsize: float = 9.0,
) -> list[Path]:
    fig, ax = plt.subplots(figsize=(figure_width, 6.2))
    x = np.arange(len(frame))
    bottom = np.zeros(len(frame))
    for tier in TIER_ORDER:
        values = pd.to_numeric(frame[tier], errors="coerce").fillna(0).to_numpy()
        bars = ax.bar(
            x,
            values,
            bottom=bottom,
            color=TIER_COLORS[tier],
            edgecolor="#111827",
            linewidth=0.45,
            label=TIER_LABELS[tier],
        )
        for idx, (bar, value) in enumerate(zip(bars, values, strict=True)):
            if value <= 0:
                continue
            text_color = "white" if tier == "extreme_ge_3_iqr" else "#111827"
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bottom[idx] + value / 2,
                f"{int(value)}",
                ha="center",
                va="center",
                fontsize=8,
                color=text_color,
            )
        bottom += values
    ax.axhline(18, color="#111827", linewidth=0.8, linestyle="--", alpha=0.55)
    ax.set_ylim(0, 18.8)
    ax.set_yticks(range(0, 19, 3))
    ax.set_ylabel("Record count (NSE/KGE/FHV x Model 1/2 x seeds = 18)")
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    ax.set_xticks(x)
    ax.set_xticklabels(frame["basin"].tolist(), rotation=x_rotation, ha="right", fontsize=x_tick_fontsize)
    ax.legend(ncol=4, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.13))
    ax.grid(axis="y", color="#e5e7eb", linewidth=0.8)
    ax.set_axisbelow(True)
    fig.tight_layout()
    return save_png_svg(fig, output_base)


def save_far_distance_stacked_bar(frame: pd.DataFrame, output_base: Path) -> list[Path]:
    return save_distance_tier_stacked_bar(
        frame,
        output_base,
        title="Far Basin Median-Distance Tier Counts",
        xlabel="Far basin",
        figure_width=14.8,
        x_rotation=45,
        x_tick_fontsize=9.0,
    )


def save_all_basin_distance_stacked_bar(frame: pd.DataFrame, output_base: Path) -> list[Path]:
    return save_distance_tier_stacked_bar(
        frame,
        output_base,
        title="All DRBC Test Basins Median-Distance Tier Counts",
        xlabel="DRBC test basin",
        figure_width=max(22.0, 0.52 * len(frame) + 5.0),
        x_rotation=90,
        x_tick_fontsize=7.2,
    )


def save_scale_flashiness_scatter(frame: pd.DataFrame, output_base: Path) -> list[Path]:
    fig = plt.figure(figsize=(9.8, 5.9))
    ax = fig.add_axes([0.08, 0.12, 0.73, 0.78])
    legend_ax = fig.add_axes([0.835, 0.56, 0.135, 0.34])
    x_min, x_max = -2, 102
    y_min, y_max = -2, 102
    ax.axvspan(x_min, 25, color="#2563eb", alpha=0.06, zorder=0)
    ax.axhspan(75, y_max, color="#dc2626", alpha=0.06, zorder=0)
    ax.axvline(25, color="#6b7280", linewidth=0.9, linestyle="--")
    ax.axhline(75, color="#6b7280", linewidth=0.9, linestyle="--")
    zone_labels = [
        (12, 91, "small + frequent\nevent response", "#7f1d1d"),
        (12, 42, "small basin /\nlow-flow scale", "#1e3a8a"),
        (62, 91, "frequent events,\nnot small", "#7f1d1d"),
        (66, 42, "moderate/large or\nless frequent", "#374151"),
    ]
    for x, y, label, color in zone_labels:
        ax.text(
            x,
            y,
            label,
            ha="center",
            va="center",
            fontsize=8.4,
            color=color,
            alpha=0.22,
            zorder=0.5,
        )
    for cause_group, group in frame.groupby("cause_group", sort=False):
        size = 65 + pd.to_numeric(group["total_far_records"], errors="coerce").fillna(0) * 15
        ax.scatter(
            group["area_percentile"],
            group["q99_event_frequency_percentile"],
            s=size,
            color=DRIVER_COLORS.get(cause_group, "#6b7280"),
            edgecolor="#111827",
            linewidth=0.6,
            alpha=0.88,
            label=driver_short_label(cause_group),
        )
        for _, row in group.iterrows():
            ax.annotate(
                str(row["basin"]),
                (row["area_percentile"], row["q99_event_frequency_percentile"]),
                xytext=(4, 4),
                textcoords="offset points",
                fontsize=7.5,
            )
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_xlabel("Area percentile (lower = smaller basin)")
    ax.set_ylabel("Q99 event frequency percentile")
    ax.set_title("Scale vs Event-Frequency Signature of Far Basins")
    ax.grid(color="#e5e7eb", linewidth=0.8)
    ax.set_axisbelow(True)

    legend_ax.set_xlim(0, 1)
    legend_ax.set_ylim(0, 1)
    legend_ax.set_xticks([])
    legend_ax.set_yticks([])
    legend_ax.set_facecolor("#ffffff")
    for spine in legend_ax.spines.values():
        spine.set_visible(True)
        spine.set_color("#111827")
        spine.set_linewidth(0.8)
    legend_ax.text(0.09, 0.91, "Driver", fontsize=7.4, fontweight="bold", color="#374151")
    y = 0.78
    present_groups = [group for group in DRIVER_COLORS if group in set(frame["cause_group"])]
    for cause_group in present_groups:
        legend_ax.scatter(
            0.16,
            y,
            s=30,
            color=DRIVER_COLORS.get(cause_group, "#6b7280"),
            edgecolor="#111827",
            linewidth=0.6,
        )
        legend_ax.text(0.29, y, driver_short_label(cause_group), fontsize=6.5, va="center")
        y -= 0.11
    legend_ax.text(0.09, y - 0.015, "Size", fontsize=7.4, fontweight="bold", color="#374151")
    y -= 0.105
    for record_count in [3, 9, 18]:
        legend_ax.scatter(
            0.16,
            y,
            s=24 + record_count * 3.5,
            color="#ffffff",
            edgecolor="#111827",
            linewidth=0.7,
        )
        legend_ax.text(0.29, y, f"{record_count} rec.", fontsize=6.4, va="center")
        y -= 0.105
    return save_png_svg(fig, output_base)


def save_event_response_heatmap(frame: pd.DataFrame, output_base: Path) -> list[Path]:
    columns = [
        "area_percentile",
        "obs_q99_percentile",
        "obs_variance_denominator_percentile",
        "q99_event_frequency_percentile",
        "rbi_percentile",
        "event_duration_median_hours_percentile",
        "recent_precipitation_share_percentile",
        "antecedent_precipitation_share_percentile",
        "snowmelt_or_rain_on_snow_share_percentile",
        "uncertain_high_flow_candidate_share_percentile",
    ]
    labels = [
        "Area",
        "Q99",
        "NSE denom",
        "Q99 freq",
        "RBI",
        "Duration",
        "Recent",
        "Antecedent",
        "Snow/ROS",
        "Uncertain",
    ]
    data = frame[columns].apply(pd.to_numeric, errors="coerce").to_numpy()
    fig, ax = plt.subplots(figsize=(13.2, max(6.5, 0.42 * len(frame))))
    image = ax.imshow(data, aspect="auto", cmap="viridis", vmin=0, vmax=100)
    ax.set_xticks(np.arange(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right")
    y_labels = [f"{row.basin}  {driver_short_label(row.cause_group)}" for row in frame.itertuples(index=False)]
    ax.set_yticks(np.arange(len(frame)))
    ax.set_yticklabels(y_labels)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            if np.isnan(data[i, j]):
                continue
            color = "white" if data[i, j] < 25 or data[i, j] > 70 else "#111827"
            ax.text(j, i, f"{data[i, j]:.0f}", ha="center", va="center", fontsize=7.2, color=color)
    ax.set_title("Far Basin Event-Response and Scale Percentile Heatmap")
    cbar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("Percentile within 38 DRBC test basins")
    fig.tight_layout()
    return save_png_svg(fig, output_base)


def save_model_far_dumbbell(frame: pd.DataFrame, output_base: Path) -> list[Path]:
    fig, (ax, note_ax) = plt.subplots(
        ncols=2,
        sharey=True,
        figsize=(14.4, max(6.2, 0.48 * len(frame))),
        gridspec_kw={"width_ratios": [3.15, 1.55], "wspace": 0.035},
    )
    y = np.arange(len(frame))
    model1 = pd.to_numeric(frame["far_or_extreme_records_model1"], errors="coerce").fillna(0).to_numpy()
    model2 = pd.to_numeric(frame["far_or_extreme_records_model2"], errors="coerce").fillna(0).to_numpy()
    for idx in range(len(frame)):
        ax.plot([model1[idx], model2[idx]], [y[idx], y[idx]], color="#9ca3af", linewidth=1.4, zorder=1)
    ax.scatter(model1, y, s=62, color="#374151", label="Model 1", zorder=2)
    ax.scatter(model2, y, s=62, color="#2563eb", label="Model 2", zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels(frame["basin"].tolist())
    ax.invert_yaxis()
    ax.set_xlim(-0.4, 9.4)
    ax.set_xticks(range(0, 10))
    ax.set_xlabel("Far/extreme records per model (max 9)")
    fig.suptitle("Model 1 vs Model 2 Far-Record Count by Basin", fontsize=15)
    ax.grid(axis="x", color="#e5e7eb", linewidth=0.8)
    for separator in y[:-1] + 0.5:
        ax.axhline(separator, color="#f3f4f6", linewidth=0.7, zorder=0)
    ax.legend(frameon=False, loc="lower right")

    note_ax.set_xlim(0, 1)
    note_ax.set_xticks([])
    note_ax.tick_params(axis="y", which="both", left=False, labelleft=False)
    note_ax.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
    note_ax.set_facecolor("#fafafa")
    note_ax.set_title("Seed-wise metric change (M2 vs M1)", fontsize=9.0, pad=24)
    for spine_name, spine in note_ax.spines.items():
        spine.set_visible(spine_name == "left")
        spine.set_color("#d1d5db")
        spine.set_linewidth(0.8)
    for separator in y[:-1] + 0.5:
        note_ax.axhline(separator, color="#f3f4f6", linewidth=0.7, zorder=0)
    column_x = {111: 0.08, 222: 0.38, 444: 0.68}
    delta_x = 0.93
    for seed, x_value in column_x.items():
        note_ax.text(
            x_value,
            1.015,
            str(seed),
            transform=note_ax.transAxes,
            ha="center",
            va="bottom",
            fontsize=8.0,
            family="monospace",
            color="#111827",
            clip_on=False,
        )
    note_ax.text(
        delta_x,
        1.015,
        "Δ",
        transform=note_ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=8.0,
        family="monospace",
        color="#111827",
        clip_on=False,
    )
    for idx in range(len(frame)):
        for seed, x_value in column_x.items():
            label = str(frame.iloc[idx].get(f"seed{seed}_metric_change", "="))
            note_ax.text(
                x_value,
                y[idx],
                label,
                ha="center",
                va="center",
                fontsize=6.6,
                family="monospace",
                color="#111827",
            )
        count_delta = int(round(model2[idx] - model1[idx]))
        note_ax.text(
            delta_x,
            y[idx],
            f"{count_delta:+d}",
            ha="center",
            va="center",
            fontsize=6.6,
            family="monospace",
            color="#111827",
        )
    note_ax.text(
        0.00,
        -0.100,
        "Criteria: + M2-only far; ++ M2-only extreme; - M1-only far; -- M1-only extreme.",
        transform=note_ax.transAxes,
        ha="left",
        va="top",
        fontsize=6.7,
        color="#4b5563",
    )
    note_ax.text(
        0.00,
        -0.138,
        "↑ far→extreme; ↓ extreme→far; Δ = M2-M1 count; N/K/F = NSE/KGE/FHV.",
        transform=note_ax.transAxes,
        ha="left",
        va="top",
        fontsize=6.7,
        color="#4b5563",
    )
    fig.subplots_adjust(left=0.08, right=0.985, top=0.85, bottom=0.17, wspace=0.035)
    return save_png_svg(fig, output_base)


def save_metric_far_pattern_heatmap(frame: pd.DataFrame, output_base: Path) -> list[Path]:
    columns = [f"{metric}_{model}_far_records" for metric in METRICS for model in MODELS]
    data = frame[columns].apply(pd.to_numeric, errors="coerce").to_numpy()
    fig, ax = plt.subplots(figsize=(7.6, max(5.8, 0.42 * len(frame))))
    image = ax.imshow(data, aspect="auto", cmap="OrRd", vmin=0, vmax=3)
    ax.set_xticks(np.arange(len(columns)))
    ax.set_xticklabels(["M1", "M2"] * len(METRICS), fontsize=8)
    for metric_idx, metric in enumerate(METRICS):
        center = metric_idx * 2 + 0.5
        ax.text(
            center,
            -0.085,
            metric,
            transform=ax.get_xaxis_transform(),
            ha="center",
            va="top",
            fontsize=9,
            fontweight="bold",
            clip_on=False,
        )
    for separator in [1.5, 3.5]:
        ax.axvline(separator, color="#111827", linewidth=0.8, alpha=0.45)
    ax.set_yticks(np.arange(len(frame)))
    ax.set_yticklabels(frame["basin"].tolist())
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            ax.text(j, i, f"{int(data[i, j])}", ha="center", va="center", fontsize=8, color="#111827")
    ax.set_title("Metric-Specific Far-Record Pattern by Model")
    cbar = fig.colorbar(image, ax=ax, fraction=0.055, pad=0.04)
    cbar.set_label("Far records per metric/model (max 3 seeds)")
    fig.tight_layout(rect=[0, 0.035, 1, 1])
    return save_png_svg(fig, output_base)


def build_analysis_figures(
    figures_dir: Path,
    basin_tier_profile: pd.DataFrame,
    far_cause_diagnosis: pd.DataFrame,
    seed_metric_changes: pd.DataFrame,
    basin_metric_model_far_counts: pd.DataFrame,
) -> pd.DataFrame:
    figures_dir.mkdir(parents=True, exist_ok=True)
    frame = far_plot_frame(
        basin_tier_profile,
        far_cause_diagnosis,
        seed_metric_changes,
        basin_metric_model_far_counts,
    )
    all_basin_frame = all_basin_tier_plot_frame(basin_tier_profile)
    chart_specs = [
        (
            "far_distance_tier_stacked_counts",
            "Far 정도별 basin stacked count chart; each bar totals 18 records.",
            save_far_distance_stacked_bar,
            frame,
        ),
        (
            "all_basin_distance_tier_stacked_counts",
            "All 38 DRBC test basin stacked count chart; each bar totals 18 records.",
            save_all_basin_distance_stacked_bar,
            all_basin_frame,
        ),
        (
            "scale_vs_event_frequency_scatter",
            "Scatter chart separating scale/low-flow and small-flashy event-response signatures.",
            save_scale_flashiness_scatter,
            frame,
        ),
        (
            "event_response_percentile_heatmap",
            "Heatmap of scale and event-response percentiles used for flow-type interpretation.",
            save_event_response_heatmap,
            frame,
        ),
        (
            "model_far_record_dumbbell",
            "Dumbbell chart comparing Model 1 and Model 2 far/extreme record counts with seed-wise metric changes.",
            save_model_far_dumbbell,
            frame,
        ),
        (
            "metric_far_pattern_heatmap",
            "Heatmap showing whether far records are multi-metric or metric-specific, split by model.",
            save_metric_far_pattern_heatmap,
            frame,
        ),
    ]
    rows = []
    for key, description, writer, plot_frame in chart_specs:
        base = figures_dir / f"metric_median_deviation_{key}"
        paths = writer(plot_frame, base)
        for path in paths:
            rows.append(
                {
                    "figure_key": key,
                    "description": description,
                    "format": path.suffix.lstrip("."),
                    "path": relative(path),
                }
            )
    manifest = pd.DataFrame(rows)
    manifest.to_csv(figures_dir / "metric_median_deviation_figure_manifest.csv", index=False)
    return manifest


def analysis_figure_section_lines() -> list[str]:
    return [
        "## 분석 차트",
        "",
        "아래 차트들은 far basin 해석에서 바로 사용할 수 있도록 같은 분석 스크립트에서 함께 생성했습니다. 첫 번째 stacked bar는 far basin마다 총 18개 record가 아래에서부터 near-median, shoulder, far, extreme 순서로 쌓이도록 만든 그림입니다.",
        "",
        "![Far distance tier stacked counts](../figures/metric_median_deviation_far_distance_tier_stacked_counts.png)",
        "",
        "Scale과 event-response를 분리해서 보기 위해 면적 percentile과 Q99 event 빈도 percentile을 scatter로 같이 그렸습니다. 점선은 절대 물리 임계값이 아니라 DRBC test basin 안에서 area 하위 25%와 Q99 event 빈도 상위 25%를 가르는 경험적 기준입니다. 색은 현재 해석한 driver group이고, 점 크기는 far/extreme record 수라서 작은 저유량 scale basin과 small flashy basin이 어떻게 갈라지는지 확인할 수 있습니다.",
        "",
        "![Scale vs event frequency scatter](../figures/metric_median_deviation_scale_vs_event_frequency_scatter.png)",
        "",
        "각 far basin의 해석 지표는 percentile heatmap으로 모았습니다. area, Q99, NSE denominator는 scale 축이고, Q99 frequency, RBI, duration, recent/antecedent/snow/uncertain share는 event-response와 발생 조건을 확인하는 축입니다.",
        "",
        "![Event response percentile heatmap](../figures/metric_median_deviation_event_response_percentile_heatmap.png)",
        "",
        "Model 1과 Model 2가 basin별 far/extreme record 수를 얼마나 바꾸는지는 dumbbell chart로 따로 봅니다. 이 그림은 Model 2가 distance를 줄이는 basin과 두 모델 모두 불안정한 basin을 구분하는 데 쓰면 됩니다.",
        "",
        "![Model far record dumbbell](../figures/metric_median_deviation_model_far_record_dumbbell.png)",
        "",
        "마지막으로 metric-specific far pattern은 NSE, KGE, FHV heatmap으로 확인합니다. 여러 metric이 함께 멀어지는 basin은 공통 hydrologic/scale driver 후보이고, 한 metric에만 나타나는 basin은 개별 component 진단으로 낮춰 해석하는 편이 안전합니다.",
        "",
        "![Metric far pattern heatmap](../figures/metric_median_deviation_metric_far_pattern_heatmap.png)",
    ]


def all_basin_distance_profile_figure_lines() -> list[str]:
    return [
        "전체 38개 DRBC test basin에 대해서도 같은 방식의 stacked bar를 만들었습니다. basin-level distance profile의 시각화 버전이며, 각 basin의 18개 record가 near-median에서 extreme까지 어떻게 배분되는지 보여줍니다.",
        "",
        "![All basin distance tier stacked counts](../figures/metric_median_deviation_all_basin_distance_tier_stacked_counts.png)",
    ]


def korean_basin_assignment_sentence(row: pd.Series) -> str:
    label = korean_cause_label(row["cause_group"])
    if str(row["cause_group"]) == "C. no shared causal driver assigned":
        return (
            f"이 유역은 `{label}`입니다. hydromod, snow, metric-specific 신호가 보이더라도 "
            "그 자체를 이상치를 만든 공유 원인으로 보기는 어려워 개별 해석으로만 남겼습니다. "
        )
    return f"이 유역은 `{label}` 원인군으로 해석했습니다. "


def korean_model_effect_label(value: Any) -> str:
    text = str(value)
    labels = {
        "Model 2 reduces distance": "Model 2에서 median-distance가 줄어든 사례",
        "Model 2 increases distance": "Model 2에서 median-distance가 커진 사례",
        "both models unstable": "두 모델 모두 불안정한 사례",
        "similar across models": "Model 1과 Model 2 차이가 크지 않은 사례",
        "mixed model effect": "Model 2 효과가 metric이나 seed에 따라 섞인 사례",
    }
    return labels.get(text, text)


def basin_korean_indicator_list(row: pd.Series) -> str:
    hydromod = "있음" if bool(row.get("hydromod_risk", False)) else "뚜렷하지 않음"
    return "\n".join(
        [
            f"- Far 반복성: {row['metric_far_pattern']}, 전체 far/extreme record = "
            f"{int(row['total_far_records'])}/{int(row['total_extreme_records'])}",
            f"- Metric 방향: {row['side_pattern']}",
            f"- Scale 위치: 면적 {fmt(row['area_percentile'])} percentile, "
            f"Q99 {fmt(row['obs_q99_percentile'])} percentile, "
            f"NSE denominator {fmt(row['obs_variance_denominator_percentile'])} percentile",
            f"- Event 반응: Q99 빈도 {fmt(row['q99_event_frequency_percentile'])} percentile, "
            f"RBI {fmt(row['rbi_percentile'])} percentile, "
            f"event duration {fmt(row['event_duration_median_hours_percentile'])} percentile",
            f"- 발생 조건: recent precipitation {fmt(row['recent_precipitation_share_percentile'])} percentile, "
            f"antecedent precipitation {fmt(row['antecedent_precipitation_share_percentile'])} percentile, "
            f"snow/ROS {fmt(row['snowmelt_or_rain_on_snow_share_percentile'])} percentile, "
            f"uncertain event share {fmt(row['uncertain_high_flow_candidate_share_percentile'])} percentile",
            f"- Flow 유형 확인: {korean_flow_response_label(row['flow_response_type'])}; "
            f"{korean_event_response_support_label(row['event_response_support'])}",
            f"- 모델 차이: {korean_model_effect_label(row['model_effect'])}; "
            f"Model 1 far = {int(row['far_or_extreme_records_model1'])}, "
            f"Model 2 far = {int(row['far_or_extreme_records_model2'])}, "
            f"평균 distance 변화 = {fmt(row['model2_mean_distance_delta'])}",
            f"- Hydromod/data: 조절 영향 {hydromod}, estimated-flow = "
            f"{fmt(row.get('FLOW_PCT_EST_VALUES', np.nan))}%",
        ]
    )


def korean_group_summary_paragraph(far_cause_group_summary: pd.DataFrame) -> str:
    parts = []
    for _, row in far_cause_group_summary.iterrows():
        median_far = float(row["median_total_far_records"])
        if str(row["cause_group"]) == "C. no shared causal driver assigned":
            evidence_sentence = (
                "이 묶음은 원인군이 아니라, 현재 지표만으로는 이상치를 만든 공유 원인을 확정하지 않은 basin 목록입니다. "
                "따라서 hydromod, snow, 특정 metric 신호는 보조 맥락으로만 쓰고 본문에서는 개별 예외로 낮춰 다루는 편이 안전합니다."
            )
        elif median_far >= 10:
            evidence_sentence = (
                f"중앙 far record 수가 {fmt(median_far)}개라서, 단발성 예외가 아니라 "
                "반복적인 basin-level signal이며 이상치를 만든 원인군으로 해석할 수 있습니다."
            )
        elif median_far >= 3:
            evidence_sentence = (
                f"중앙 far record 수가 {fmt(median_far)}개라서, 반복성은 제한적이지만 "
                "특정 조건에서 드러나는 sensitivity로 볼 수 있습니다."
            )
        else:
            evidence_sentence = (
                f"중앙 far record 수가 {fmt(median_far)}개뿐이므로, 그룹 결론의 핵심 근거보다는 "
                "예외 또는 후속 진단 대상으로 낮춰 해석하는 편이 안전합니다."
            )
        if str(row["cause_group"]) == "C. no shared causal driver assigned":
            parts.append(
                f"공유 원인군으로 묶지 않은 개별 검토 목록에는 {int(row['basin_count'])}개 유역"
                f"({row['basins']})이 들어갑니다. 이 목록의 중앙 면적은 {fmt(row['median_area'])} km2이고, "
                f"중앙 Q99는 {fmt(row['median_obs_q99'])}, 중앙 Q99 event 빈도는 "
                f"{fmt(row['median_q99_event_frequency'])}/yr, 중앙 RBI는 {fmt(row['median_rbi'])}입니다. "
                f"{evidence_sentence}"
            )
        else:
            parts.append(
                f"{korean_cause_label(row['cause_group'])} 원인군에는 {int(row['basin_count'])}개 유역"
                f"({row['basins']})이 들어갑니다. 이 원인군의 중앙 면적은 {fmt(row['median_area'])} km2이고, "
                f"중앙 Q99는 {fmt(row['median_obs_q99'])}, 중앙 Q99 event 빈도는 "
                f"{fmt(row['median_q99_event_frequency'])}/yr, 중앙 RBI는 {fmt(row['median_rbi'])}입니다. "
                f"{evidence_sentence}"
            )
    return "\n\n".join(parts)


def interpretation_method_ko_lines() -> list[str]:
    return [
        "## 해석 방법과 선행연구 근거",
        "",
        "1. 지표 정규화 효과를 먼저 확인합니다. 작은 유역은 관측 유량 scale, Q99, NSE denominator가 작기 때문에 같은 절대 오차도 NSE/KGE/FHV에서 더 큰 normalized distance로 나타날 수 있습니다. NSE는 mean-flow benchmark와 관측 변동성에 강하게 의존하고, KGE도 상관, 변동성 비율, bias component로 분해되기 때문에 단일 종합값만 보면 작은 저유량 유역의 오차가 과대해 보일 수 있습니다. 이 해석은 [Knoben et al. (2019)](https://hess.copernicus.org/articles/23/4323/2019/hess-23-4323-2019.html)의 NSE/KGE benchmark 논의와 [Krause et al. (2005)](https://adgeo.copernicus.org/articles/5/89/2005/adgeo-5-89-2005.pdf)의 efficiency metric 민감도 논의에 근거합니다.",
        "",
        "2. 유역 scale 효과를 확인합니다. 선행연구에서는 catchment area가 커질수록 model performance가 안정되고 performance scatter가 줄어드는 경향이 보고되어 있습니다. 이는 큰 유역에서 강우와 유출 반응이 공간적으로 평균화되고, water balance와 routing/storage가 더 완만하게 작동하기 때문입니다. [Merz et al. (2009)](https://doi.org/10.1029/2009WR007872)은 유역 규모가 커질수록 NSE가 증가하고 performance scatter가 감소한다고 보고했고, [Girons Lopez and Seibert (2016)](https://www.sciencedirect.com/science/article/pii/S0022169416305170)도 model performance가 catchment area와 함께 증가한다고 정리했습니다.",
        "",
        "3. event response가 실제로 flashy한지 따로 확인합니다. 작은 유역이라고 모두 같은 유형은 아니므로, `q99_event_frequency`, `RBI`, `event_duration`, `recent/antecedent/snow/uncertain share`를 함께 봅니다. 강우의 spatial variability는 hydrograph timing과 shape에, temporal variability는 flood peak에 영향을 준다는 점이 알려져 있으므로, 작은 유역 중에서도 짧고 잦은 event를 보이는 basin은 timing/high-flow volume 오차가 추가로 증폭될 수 있습니다. 이 판단은 [Zhu et al. (2019)](https://hess.copernicus.org/articles/23/2647/2019/hess-23-2647-2019.html)의 rainfall resolution과 hydrograph response 논의를 따른 것입니다.",
    ]


def model_seed_far_load_section_lines(
    model_seed_far_summary: pd.DataFrame,
    metric_model_seed_far_summary: pd.DataFrame,
    basin_model_seed_far_recurrence: pd.DataFrame,
) -> list[str]:
    if model_seed_far_summary.empty:
        return []
    high = model_seed_far_summary.iloc[0]
    low = model_seed_far_summary.sort_values(["far_records", "extreme_records"], ascending=[True, True]).iloc[0]
    model_totals = (
        model_seed_far_summary.groupby("model", dropna=False)
        .agg(
            far_records=("far_records", "sum"),
            extreme_records=("extreme_records", "sum"),
            mean_far_records_per_seed=("far_records", "mean"),
            mean_extreme_records_per_seed=("extreme_records", "mean"),
        )
        .reset_index()
    )
    top_target = metric_model_seed_far_summary.iloc[0] if not metric_model_seed_far_summary.empty else None
    target_sentence = ""
    if top_target is not None:
        target_sentence = (
            f"metric/model/seed 단위에서는 `{top_target['metric']} {top_target['model']} seed {int(top_target['seed'])}`가 "
            f"far record {int(top_target['far_records'])}개로 가장 큽니다. "
        )
    model1 = model_totals[model_totals["model"].eq("model1")]
    model2 = model_totals[model_totals["model"].eq("model2")]
    model_delta_sentence = ""
    if not model1.empty and not model2.empty:
        model1_far = int(model1.iloc[0]["far_records"])
        model2_far = int(model2.iloc[0]["far_records"])
        model1_extreme = int(model1.iloc[0]["extreme_records"])
        model2_extreme = int(model2.iloc[0]["extreme_records"])
        far_drop = model1_far - model2_far
        extreme_drop = model1_extreme - model2_extreme
        model_delta_sentence = (
            f"Model 1 전체 far/extreme record는 {model1_far}/{model1_extreme}개이고, "
            f"Model 2는 {model2_far}/{model2_extreme}개입니다. 즉 Model 2에서 far record는 {far_drop}개, "
            f"extreme record는 {extreme_drop}개 줄어듭니다. "
        )
    recurrent = basin_model_seed_far_recurrence[basin_model_seed_far_recurrence["far_model_seed_count"].ge(6)].copy()
    isolated = basin_model_seed_far_recurrence[basin_model_seed_far_recurrence["far_model_seed_count"].le(1)].copy()
    recurrent_sentence = ""
    if not recurrent.empty:
        recurrent_sentence = (
            "모든 model-seed 조합에서 far가 반복된 basin은 "
            f"`{'`, `'.join(recurrent['basin'].astype(str).tolist())}`입니다. "
        )
    isolated_sentence = ""
    if not isolated.empty:
        isolated_sentence = (
            "반대로 한 model-seed에서만 far가 나타난 basin은 "
            f"`{'`, `'.join(isolated['basin'].astype(str).tolist())}`라서, "
            "공유 driver의 핵심 증거보다 run-specific sensitivity로 낮춰 해석하는 편이 맞습니다."
        )
    metric_direction = (
        metric_model_seed_far_summary.groupby("metric", dropna=False)
        .agg(
            far_records=("far_records", "sum"),
            low_side_far_records=("low_side_far_records", "sum"),
            high_side_far_records=("high_side_far_records", "sum"),
        )
        .reset_index()
    )
    direction_sentence = ""
    if not metric_direction.empty:
        parts = []
        for row in metric_direction.itertuples(index=False):
            parts.append(
                f"{row.metric}: low {int(row.low_side_far_records)}, high {int(row.high_side_far_records)}"
            )
        direction_sentence = "Metric 방향성 합계는 " + "; ".join(parts) + "입니다. "

    return [
        "## Model/Seed Far-Record Load Check",
        "",
        "이 점검의 목적은 특정 basin이 멀어진 것인지, 아니면 어떤 model/seed run 자체가 전반적으로 median에서 더 많이 벌어지는지 분리하는 것입니다. "
        "각 model-seed는 `38 basin x NSE/KGE/FHV = 114`개 record를 가지므로, 여기서는 model-seed별 far/extreme record 수와 far basin 수를 비교합니다.",
        "",
        f"model-seed별 far record 범위는 `{int(low['far_records'])}`개부터 `{int(high['far_records'])}`개까지입니다. "
        f"가장 큰 run은 `{high['model']} seed {int(high['seed'])}`이고, 가장 작은 run은 `{low['model']} seed {int(low['seed'])}`입니다. "
        f"{target_sentence}"
        "따라서 far basin 해석에서 run-level 편차를 완전히 무시하면 안 됩니다.",
        "",
        f"{model_delta_sentence}Model 2가 전반적으로 far load를 줄이는 것은 맞지만, `model2 seed 444`는 far/extreme record가 23/18개로 Model 1 seed들과 거의 같은 수준입니다. "
        "따라서 Model 2의 개선을 말할 때는 평균적인 완화와 seed별 잔여 불안정성을 같이 써야 합니다. 특히 seed 111/222에서는 완화가 뚜렷하지만, seed 444에서는 취약 basin의 distance가 여전히 크게 남습니다.",
        "",
        "다만 모든 model-seed에서 far basin 수는 대체로 8-9개 수준으로 유지됩니다. 즉 어떤 seed 하나가 전혀 다른 basin population을 만든다기보다는, "
        "비슷한 취약 basin들이 반복적으로 등장하되 run에 따라 멀어지는 강도와 extreme 비율이 달라진 것으로 보는 편이 맞습니다. "
        f"{recurrent_sentence}{isolated_sentence}",
        "",
        markdown_table(
            basin_model_seed_far_recurrence.head(10),
            [
                "basin",
                "gauge_name",
                "far_model_seed_count",
                "total_far_records",
                "total_extreme_records",
                "NSE_far_records",
                "KGE_far_records",
                "FHV_far_records",
                "model_seed_breakdown",
            ],
            {
                "basin": "Basin",
                "gauge_name": "Gauge",
                "far_model_seed_count": "Far model-seeds",
                "total_far_records": "Far records",
                "total_extreme_records": "Extreme records",
                "NSE_far_records": "NSE far",
                "KGE_far_records": "KGE far",
                "FHV_far_records": "FHV far",
                "model_seed_breakdown": "Model-seed breakdown",
            },
        ),
        "",
        markdown_table(
            model_seed_far_summary,
            [
                "model",
                "seed",
                "far_records",
                "extreme_records",
                "far_share",
                "far_basin_count",
                "NSE_far_records",
                "KGE_far_records",
                "FHV_far_records",
                "mean_distance_iqr",
                "max_distance_iqr",
                "far_load_label",
                "top_far_basins",
            ],
            {
                "model": "Model",
                "seed": "Seed",
                "far_records": "Far records",
                "extreme_records": "Extreme records",
                "far_share": "Far share",
                "far_basin_count": "Far basins",
                "NSE_far_records": "NSE far",
                "KGE_far_records": "KGE far",
                "FHV_far_records": "FHV far",
                "mean_distance_iqr": "Mean dist",
                "max_distance_iqr": "Max dist",
                "far_load_label": "Load label",
                "top_far_basins": "Top far basins",
            },
        ),
        "",
        "Model별 합계로 보면 Model 1이 Model 2보다 far/extreme record load가 큽니다. 하지만 Model 2도 seed 444에서는 Model 1 seed들과 비슷한 수준의 far load를 보이므로, "
        "Model 2 개선 효과는 seed에 따라 달라지고 특히 seed 111/222에서 더 강하게 나타난다고 해석하는 편이 안전합니다.",
        "",
        markdown_table(
            model_totals,
            [
                "model",
                "far_records",
                "extreme_records",
                "mean_far_records_per_seed",
                "mean_extreme_records_per_seed",
            ],
            {
                "model": "Model",
                "far_records": "Far records",
                "extreme_records": "Extreme records",
                "mean_far_records_per_seed": "Mean far / seed",
                "mean_extreme_records_per_seed": "Mean extreme / seed",
            },
        ),
        "",
        "아래 표는 far load가 큰 metric/model/seed target을 위에서부터 보여줍니다. 전체 target별 상세 표는 CSV에 따로 저장했습니다.",
        "",
        f"{direction_sentence}NSE와 KGE의 far record는 거의 모두 median보다 낮은 쪽이고, FHV far record는 median보다 높은 쪽입니다. "
        "따라서 model-seed 편차가 있어도 방향성은 무작위가 아니라, 같은 basin에서 skill metric은 낮아지고 high-flow volume bias는 커지는 형태로 반복됩니다. "
        "이 점은 basin-level driver 해석, 특히 small/low-flow scale과 small flashy response 해석을 보조합니다.",
        "",
        markdown_table(
            metric_model_seed_far_summary.head(12),
            [
                "metric",
                "model",
                "seed",
                "far_records",
                "extreme_records",
                "far_basin_count",
                "mean_distance_iqr",
                "max_distance_iqr",
                "low_side_far_records",
                "high_side_far_records",
                "top_far_basins",
            ],
            {
                "metric": "Metric",
                "model": "Model",
                "seed": "Seed",
                "far_records": "Far records",
                "extreme_records": "Extreme records",
                "far_basin_count": "Far basins",
                "mean_distance_iqr": "Mean dist",
                "max_distance_iqr": "Max dist",
                "low_side_far_records": "Low-side far",
                "high_side_far_records": "High-side far",
                "top_far_basins": "Top far basins",
            },
        ),
    ]


def write_korean_interpretation_report(
    output_path: Path,
    basin_tier_profile: pd.DataFrame,
    tier_distribution_summary: pd.DataFrame,
    far_cause_group_summary: pd.DataFrame,
    far_cause_diagnosis: pd.DataFrame,
    model_seed_far_summary: pd.DataFrame,
    metric_model_seed_far_summary: pd.DataFrame,
    basin_model_seed_far_recurrence: pd.DataFrame,
    args: argparse.Namespace,
) -> None:
    far_count = int(far_cause_diagnosis["basin"].nunique())
    n_basins = int(basin_tier_profile["basin"].nunique())
    extreme_row = tier_distribution_summary[
        tier_distribution_summary["distance_tier"].eq("extreme_ge_3_iqr")
    ]
    far_row = tier_distribution_summary[
        tier_distribution_summary["distance_tier"].eq("far_1_5_to_3_iqr")
    ]
    near_row = tier_distribution_summary[
        tier_distribution_summary["distance_tier"].eq("near_median_lt_0_5_iqr")
    ]

    def tier_value(frame: pd.DataFrame, column: str) -> str:
        if frame.empty or column not in frame.columns:
            return "NA"
        return fmt(frame.iloc[0][column])

    repeated = far_cause_diagnosis[far_cause_diagnosis["total_far_records"].ge(10)]
    limited = far_cause_diagnosis[far_cause_diagnosis["total_far_records"].lt(10)]
    flow_check = flow_response_check_frame(far_cause_diagnosis)

    lines = [
        "# DRBC far 유역 한국어 해석 메모",
        "",
        f"생성 시각 UTC: `{datetime.now(UTC).isoformat()}`",
        "",
        "이 문서는 NSE, KGE, FHV의 boxplot median-distance 분석을 표 중심 결과가 아니라 한국어 본문 중심으로 다시 풀어 쓴 해석본입니다. "
        f"분석 단위는 DRBC primary test 유역 {n_basins}개, Model 1과 Model 2, seed 111/222/444의 조합이며, "
        f"`far`는 median에서 {args.far_threshold} IQR 이상, `extreme`은 {args.extreme_threshold} IQR 이상 떨어진 경우로 정의했습니다.",
        "",
        *interpretation_method_ko_lines(),
        "",
        "## 핵심 해석",
        "",
        "가장 강한 신호는 작은 유역과 낮은 observed-flow scale입니다. median에서 3 IQR 이상 떨어진 구간의 중앙 면적은 "
        f"{tier_value(extreme_row, 'area_median')} km2, 중앙 Q99는 {tier_value(extreme_row, 'obs_q99_median')}입니다. "
        "반대로 near-median 구간은 훨씬 큰 중앙 면적과 Q99를 보입니다. 따라서 far basin 전체를 먼저 설명하는 1차 축은 "
        "snow regime이나 계절성이 아니라, 작은 basin에서 metric denominator와 peak scale이 작아지는 구조입니다.",
        "",
        "다만 모든 far basin을 이 하나의 원인으로 묶으면 해석이 과해집니다. Shellpot, Crum Creek, East Branch White Clay처럼 "
        "면적은 여전히 작지만 Q99 event 빈도와 RBI가 높은 basin은 작은 scale만으로 설명하기보다 flashy event timing과 high-flow volume 반응을 함께 봐야 합니다. "
        "반대로 Tulpehocken, Blue Marsh, Little Schuylkill처럼 조절 영향이나 특정 metric에만 나타나는 basin은 "
        "그 맥락이 곧 이상치의 원인이라고 보기 어렵기 때문에 별도 원인군으로 세분하지 않았습니다.",
        "",
        "## 거리 구간별 분포 해석",
        "",
        "outlier만 따로 보면 far basin이 왜 생겼는지 좁게 보게 됩니다. 구간을 `<0.5 IQR`, `0.5-1.5 IQR`, `1.5-3 IQR`, "
        "`>=3 IQR`로 나누면, median에서 멀어질수록 중앙 면적과 중앙 Q99가 작아지는 흐름이 보입니다. "
        f"`1.5-3 IQR` 구간의 중앙 면적은 {tier_value(far_row, 'area_median')} km2, 중앙 Q99는 "
        f"{tier_value(far_row, 'obs_q99_median')}이고, `>=3 IQR` 구간에서는 각각 "
        f"{tier_value(extreme_row, 'area_median')} km2와 {tier_value(extreme_row, 'obs_q99_median')}까지 내려갑니다. "
        f"near-median 구간의 중앙 면적 {tier_value(near_row, 'area_median')} km2와 비교하면, "
        "far/extreme 쪽이 주로 작은 유역으로 기울어져 있다는 점이 분명합니다.",
        "",
        "하지만 거리 구간이 멀어진다고 해서 모두 같은 hydrologic regime은 아닙니다. extreme 구간의 top basin은 Blackbird, Birch Run, "
        "Marsh Creek처럼 작은 headwater 또는 low-flow scale basin이 많습니다. 반면 1.5-3 IQR 구간에서는 Shellpot과 "
        "Crum Creek처럼 여전히 작지만 event 빈도와 RBI가 특히 높은 basin이 두드러집니다. 그래서 본문에서는 이상치를 만든 원인으로 설명 가능한 "
        "`작은 유역/저유량 scale`과 `small flashy event response`만 원인군으로 두고, 나머지는 공유 원인군 없이 개별 검토 대상으로 남겼습니다.",
        "",
        *all_basin_distance_profile_figure_lines(),
        "",
        *model_seed_far_load_section_lines(
            model_seed_far_summary,
            metric_model_seed_far_summary,
            basin_model_seed_far_recurrence,
        ),
        "",
        "## 원인군 요약",
        "",
        korean_group_summary_paragraph(far_cause_group_summary),
        "",
        "반복성이 강하고 원인 지표가 직접 맞물리는 basin은 본문에서 주요 evidence로 쓰고, 반복성이 약하거나 원인 지표가 직접 맞물리지 않는 basin은 예외 또는 robustness check로 낮춰 쓰는 편이 좋습니다. "
        f"여기서는 far record가 10개 이상인 basin {int(repeated['basin'].nunique())}개를 주된 해석 대상으로 보고, "
        f"far record가 10개 미만인 basin {int(limited['basin'].nunique())}개는 원인군이 아니라 isolated case로 구분했습니다.",
        "",
        "## Event Response 기반 Flow 유형 확인",
        "",
        "아래 표는 원인군을 더 세분하려는 목적이 아니라, 현재 해석이 실제 event response 지표와 맞는지 확인하기 위한 표입니다. A군은 작은 area/Q99/NSE denominator가 반복적으로 확인되어 scale driver를 지지합니다. B군은 area가 큰 유역이 아니라, 작은 유역 중에서도 Q99 event 빈도와 RBI가 높고 duration이 짧아 timing/high-flow volume error가 추가로 커질 수 있는 `small flashy` 유형입니다. C군은 hydromod, snow, 특정 metric 신호가 보이더라도 공유 driver로 확정하지 않고 개별 진단으로 남겼습니다.",
        "",
        markdown_table(
            flow_check,
            [
                "basin",
                "gauge_name",
                "driver_group_ko",
                "flow_response_type_ko",
                "event_response_support_ko",
                "area_percentile",
                "obs_q99_percentile",
                "q99_event_frequency_percentile",
                "rbi_percentile",
                "event_duration_median_hours_percentile",
                "event_response_evidence_ko",
            ],
            {
                "basin": "유역",
                "gauge_name": "이름",
                "driver_group_ko": "Driver 해석",
                "flow_response_type_ko": "Flow 유형",
                "event_response_support_ko": "Event-response 확인",
                "area_percentile": "Area pctile",
                "obs_q99_percentile": "Q99 pctile",
                "q99_event_frequency_percentile": "Q99 freq pctile",
                "rbi_percentile": "RBI pctile",
                "event_duration_median_hours_percentile": "Duration pctile",
                "event_response_evidence_ko": "근거",
            },
        ),
        "",
        *analysis_figure_section_lines(),
        "",
        "## 유역별 상세 해석",
        "",
    ]

    for _, row in far_cause_diagnosis.iterrows():
        basin = str(row["basin"])
        name = row["gauge_name"]
        lines.extend(
            [
                f"### {basin} | {name}",
                "",
                basin_korean_indicator_list(row),
                "",
                f"{korean_basin_assignment_sentence(row)}{detailed_far_note_text(basin)}",
                "",
            ]
        )

    lines.extend(
        [
            "## 본문 서술에 반영할 때의 기준",
            "",
            "논문 본문에서는 far basin을 하나의 실패 유형으로 쓰기보다, 먼저 distance gradient에서 작은 유역과 낮은 Q99가 far/extreme 쪽으로 "
            "몰린다는 점을 보여주는 것이 좋습니다. 그 다음 원인 지표가 직접 맞물리는 basin만 원인군으로 나누면, Model 1과 Model 2 차이를 "
            "단순 승패가 아니라 어떤 basin 조건에서 완화되고 어떤 조건에서는 남는지 설명할 수 있습니다.",
            "",
            "특히 Blackbird, Birch Run, Marsh Creek, Broad Run은 scale 또는 flashy small-basin 문제가 강해서 핵심 evidence로 쓸 수 있습니다. "
            "Shellpot과 Crum Creek은 작은 유역이라는 설명만으로는 부족하고, event frequency, RBI, 짧은 duration을 같이 제시해야 합니다. "
            "Jordan Creek, Lockatong, Tulpehocken, Little Schuylkill, Blue Marsh 계열은 반복성이 약하거나 특정 metric에 치우쳐 있으므로 "
            "원인군으로 세분하지 말고 caveat, exception, follow-up diagnostic으로 배치하는 편이 안정적입니다.",
            "",
            "## 참고 산출물",
            "",
            f"- 표 중심 리포트: `{relative(args.output_dir / 'report/metric_median_deviation_regime_report_ko.md')}`",
            f"- far 원인 진단 표: `{relative(args.output_dir / 'tables/metric_median_deviation_far_cause_diagnosis.csv')}`",
            f"- far flow 유형 확인 표: `{relative(args.output_dir / 'tables/metric_median_deviation_far_flow_response_check.csv')}`",
            f"- model-seed far load 표: `{relative(args.output_dir / 'tables/metric_median_deviation_model_seed_far_summary.csv')}`",
            f"- metric/model/seed far load 표: `{relative(args.output_dir / 'tables/metric_median_deviation_metric_model_seed_far_summary.csv')}`",
            f"- basin model-seed recurrence 표: `{relative(args.output_dir / 'tables/metric_median_deviation_basin_model_seed_far_recurrence.csv')}`",
            f"- seed별 metric 변화 label 표: `{relative(args.output_dir / 'tables/metric_median_deviation_seed_metric_change_labels.csv')}`",
            f"- seed별 변화 count 검산 표: `{relative(args.output_dir / 'tables/metric_median_deviation_seed_metric_change_count_check.csv')}`",
            f"- basin/metric/model far count 표: `{relative(args.output_dir / 'tables/metric_median_deviation_basin_metric_model_far_counts.csv')}`",
            f"- 거리 구간별 분포 표: `{relative(args.output_dir / 'tables/metric_median_deviation_tier_distribution_summary.csv')}`",
            f"- basin별 거리 profile: `{relative(args.output_dir / 'tables/metric_median_deviation_basin_tier_profile.csv')}`",
            f"- 분석 figure manifest: `{relative(args.output_dir / 'figures/metric_median_deviation_figure_manifest.csv')}`",
        ]
    )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(
    output_path: Path,
    records: pd.DataFrame,
    basin_summary: pd.DataFrame,
    basin_tier_profile: pd.DataFrame,
    basin_model_tier_profile: pd.DataFrame,
    tier_distribution_summary: pd.DataFrame,
    model_seed_far_summary: pd.DataFrame,
    metric_model_seed_far_summary: pd.DataFrame,
    basin_model_seed_far_recurrence: pd.DataFrame,
    far_cause_group_summary: pd.DataFrame,
    far_cause_diagnosis: pd.DataFrame,
    far: pd.DataFrame,
    groups: pd.DataFrame,
    ungrouped: pd.DataFrame,
    args: argparse.Namespace,
) -> None:
    tier_counts = (
        records.groupby(["metric", "distance_tier"], dropna=False)
        .size()
        .reset_index(name="record_count")
        .sort_values(["metric", "distance_tier"])
    )
    group_members = set()
    if not groups.empty:
        for value in groups["basins"]:
            group_members.update(str(value).split())

    far_table = compact_far_profiles(far).copy()
    flow_check = flow_response_check_frame(far_cause_diagnosis)
    for col in [
        "area",
        "snow_fraction",
        "cold_season_event_fraction",
        "recent_precipitation_share",
        "antecedent_precipitation_share",
        "snowmelt_or_rain_on_snow_share",
        "uncertain_high_flow_candidate_share",
        "obs_variance_denominator",
        "obs_q99",
        "q99_event_frequency",
        "rbi",
        "event_duration_median_hours",
    ]:
        if col in far_table.columns:
            far_table[col] = far_table[col].map(lambda x: fmt(x))

    grouped_lines = []
    if groups.empty:
        grouped_lines.append("ratio 기준을 통과한 multi-basin group은 없습니다.")
    else:
        for _, row in groups.iterrows():
            grouped_lines.append(
                f"- `{row['group_id']}` {row['group_label']} similarity pair: `{row['basins']}`. {row['basis']} "
                f"이 pair는 면적 {fmt(row['area_min'])}-{fmt(row['area_max'])} km2, "
                f"NSE/KGE/FHV far record 합계 median {fmt(row['total_far_records_median'])}입니다."
            )

    lines = [
        "# NSE/KGE/FHV primary boxplot median-distance regime analysis",
        "",
        f"- 생성 시각 UTC: `{datetime.now(UTC).isoformat()}`",
        f"- 기준 metric: `{', '.join(METRICS)}`",
        f"- 거리 기준: 각 `metric/model/seed` box의 median에서 벗어난 절대 거리를 해당 box IQR로 나눈 값입니다. `far`는 `{args.far_threshold}` IQR 이상, `extreme`은 `{args.extreme_threshold}` IQR 이상입니다.",
        f"- 분석 단위: DRBC primary test basin `{int(basin_summary['basin'].nunique())}`개 x Model 1/2 x seed 111/222/444입니다.",
        "",
        "## 핵심 결론",
        "",
        "NSE와 KGE에서 median 아래로 크게 벌어지는 basin은 대부분 작은 유역과 낮은 observed-flow variance를 공유합니다. 같은 basin에서 FHV는 median보다 높은 쪽으로 벌어지는 경우가 많아서, 중심 hydrograph skill 저하와 high-flow bias 불안정이 같은 small/low-variance basin에서 같이 나타납니다.",
        "",
        "다만 이것을 하나의 snow/winter regime으로 묶기는 어렵습니다. 반복 far basin들은 대체로 recent-precipitation dominated이지만 snow fraction, cold-season event fraction, snowmelt/rain-on-snow share, uncertain event share가 서로 다릅니다. 그래서 ratio가 가까운 `01475850-01478120`은 similarity pair로만 기록하고, 이상치를 만든 causal group으로는 쓰지 않았습니다.",
        "",
        *interpretation_method_ko_lines(),
        "",
        "## Distance Tier Count",
        "",
        markdown_table(
            tier_counts,
            ["metric", "distance_tier", "record_count"],
            {"metric": "Metric", "distance_tier": "Median-distance tier", "record_count": "Record count"},
        ),
        "",
        *model_seed_far_load_section_lines(
            model_seed_far_summary,
            metric_model_seed_far_summary,
            basin_model_seed_far_recurrence,
        ),
        "",
        "## Distance Gradient Basin Distribution",
        "",
        "아래 표는 outlier만이 아니라 전체 basin-metric-model-seed record를 median-distance 구간별로 나눈 것입니다. 같은 basin이 여러 metric/model/seed에서 같은 구간에 들어갈 수 있으므로 `Record count`와 `Basin count`는 서로 다른 의미입니다.",
        "",
        markdown_table(
            tier_distribution_summary,
            [
                "distance_label",
                "record_count",
                "basin_count",
                "area_median",
                "obs_variance_denominator_median",
                "obs_q99_median",
                "q99_event_frequency_median",
                "rbi_median",
                "snow_fraction_median",
                "recent_precipitation_share_median",
                "snowmelt_or_rain_on_snow_share_median",
                "top_basins_by_records",
            ],
            {
                "distance_label": "Distance from median",
                "record_count": "Record count",
                "basin_count": "Basin count",
                "area_median": "Median area",
                "obs_variance_denominator_median": "Median NSE denom",
                "obs_q99_median": "Median Q99",
                "q99_event_frequency_median": "Median Q99 freq",
                "rbi_median": "Median RBI",
                "snow_fraction_median": "Median snow frac",
                "recent_precipitation_share_median": "Median recent share",
                "snowmelt_or_rain_on_snow_share_median": "Median snow/ROS share",
                "top_basins_by_records": "Most frequent basins",
            },
        ),
        "",
        "## Basin-Level Distance Profile",
        "",
        "각 basin은 NSE/KGE/FHV x Model 1/2 x seed 111/222/444의 `18`개 record를 가집니다. 표는 이 18개 record가 median-distance 구간에 어떻게 배분되는지 보여줍니다.",
        "",
        *all_basin_distance_profile_figure_lines(),
        "",
        markdown_table(
            basin_tier_profile,
            [
                "basin",
                "gauge_name",
                "dominant_distance_label",
                "near_median_lt_0_5_iqr",
                "shoulder_0_5_to_1_5_iqr",
                "far_1_5_to_3_iqr",
                "extreme_ge_3_iqr",
                "far_or_extreme_records",
                "mean_distance_any_metric_seed",
                "max_distance_any_metric_seed",
                "area",
                "obs_q99",
                "q99_event_frequency",
                "rbi",
            ],
            {
                "basin": "Basin",
                "gauge_name": "Gauge",
                "dominant_distance_label": "Dominant bin",
                "near_median_lt_0_5_iqr": "<0.5",
                "shoulder_0_5_to_1_5_iqr": "0.5-1.5",
                "far_1_5_to_3_iqr": "1.5-3",
                "extreme_ge_3_iqr": ">=3",
                "far_or_extreme_records": ">=1.5",
                "mean_distance_any_metric_seed": "Mean dist",
                "max_distance_any_metric_seed": "Max dist",
                "area": "Area",
                "obs_q99": "Obs Q99",
                "q99_event_frequency": "Q99 freq",
                "rbi": "RBI",
            },
        ),
        "",
        "아래 Model별 재집계는 basin당 NSE/KGE/FHV x seed 111/222/444의 `9`개 record를 기준으로 합니다.",
        "",
        "### Model 1",
        "",
        markdown_table(
            basin_model_tier_profile[basin_model_tier_profile["model"].eq("model1")],
            [
                "basin",
                "gauge_name",
                "dominant_distance_label",
                "near_median_lt_0_5_iqr",
                "shoulder_0_5_to_1_5_iqr",
                "far_1_5_to_3_iqr",
                "extreme_ge_3_iqr",
                "far_or_extreme_records",
                "mean_distance_any_metric_seed",
                "max_distance_any_metric_seed",
                "area",
                "obs_q99",
                "q99_event_frequency",
                "rbi",
            ],
            {
                "basin": "Basin",
                "gauge_name": "Gauge",
                "dominant_distance_label": "Dominant bin",
                "near_median_lt_0_5_iqr": "<0.5",
                "shoulder_0_5_to_1_5_iqr": "0.5-1.5",
                "far_1_5_to_3_iqr": "1.5-3",
                "extreme_ge_3_iqr": ">=3",
                "far_or_extreme_records": ">=1.5",
                "mean_distance_any_metric_seed": "Mean dist",
                "max_distance_any_metric_seed": "Max dist",
                "area": "Area",
                "obs_q99": "Obs Q99",
                "q99_event_frequency": "Q99 freq",
                "rbi": "RBI",
            },
        ),
        "",
        "### Model 2",
        "",
        markdown_table(
            basin_model_tier_profile[basin_model_tier_profile["model"].eq("model2")],
            [
                "basin",
                "gauge_name",
                "dominant_distance_label",
                "near_median_lt_0_5_iqr",
                "shoulder_0_5_to_1_5_iqr",
                "far_1_5_to_3_iqr",
                "extreme_ge_3_iqr",
                "far_or_extreme_records",
                "mean_distance_any_metric_seed",
                "max_distance_any_metric_seed",
                "area",
                "obs_q99",
                "q99_event_frequency",
                "rbi",
            ],
            {
                "basin": "Basin",
                "gauge_name": "Gauge",
                "dominant_distance_label": "Dominant bin",
                "near_median_lt_0_5_iqr": "<0.5",
                "shoulder_0_5_to_1_5_iqr": "0.5-1.5",
                "far_1_5_to_3_iqr": "1.5-3",
                "extreme_ge_3_iqr": ">=3",
                "far_or_extreme_records": ">=1.5",
                "mean_distance_any_metric_seed": "Mean dist",
                "max_distance_any_metric_seed": "Max dist",
                "area": "Area",
                "obs_q99": "Obs Q99",
                "q99_event_frequency": "Q99 freq",
                "rbi": "RBI",
            },
        ),
        "",
        "## Far Basin Driver Diagnosis",
        "",
        "이 섹션은 `>=1.5 IQR` record가 하나라도 있는 basin을 보되, 이상치를 만든 원인으로 직접 해석할 수 있는 구분만 남깁니다. 따라서 `size/low-flow scale`과 `small flashy event response`는 driver group으로 두고, hydromod, snow, metric-specific 신호처럼 원인으로 확정하기 어려운 맥락은 별도 세부 group으로 나누지 않았습니다.",
        "",
        markdown_table(
            far_cause_group_summary,
            [
                "cause_group",
                "basin_count",
                "basins",
                "median_area",
                "median_obs_q99",
                "median_q99_event_frequency",
                "median_rbi",
                "median_total_far_records",
                "shared_interpretation",
            ],
            {
                "cause_group": "Driver group",
                "basin_count": "Basins",
                "basins": "Basin IDs",
                "median_area": "Median area",
                "median_obs_q99": "Median Q99",
                "median_q99_event_frequency": "Median Q99 freq",
                "median_rbi": "Median RBI",
                "median_total_far_records": "Median far records",
                "shared_interpretation": "Shared driver interpretation",
            },
        ),
        "",
        markdown_table(
            far_cause_diagnosis,
            [
                "basin",
                "gauge_name",
                "cause_group",
                "metric_far_pattern",
                "model_effect",
                "area_percentile",
                "obs_q99_percentile",
                "q99_event_frequency_percentile",
                "rbi_percentile",
                "hydromod_risk",
                "primary_cause",
                "interpretation_note",
            ],
            {
                "basin": "Basin",
                "gauge_name": "Gauge",
                "cause_group": "Driver group",
                "metric_far_pattern": "Far pattern",
                "model_effect": "Model effect",
                "area_percentile": "Area pctile",
                "obs_q99_percentile": "Q99 pctile",
                "q99_event_frequency_percentile": "Q99 freq pctile",
                "rbi_percentile": "RBI pctile",
                "hydromod_risk": "Hydromod",
                "primary_cause": "Driver/caution",
                "interpretation_note": "Interpretation note",
            },
        ),
        "",
        "## Event Response Flow-Type Check",
        "",
        "아래 표는 각 far basin의 event response가 driver 해석을 실제로 지지하는지 확인한 것입니다. 특히 B군은 area가 큰 유역이 아니라, 작은 유역 중에서도 Q99 event 빈도, RBI, 짧은 duration이 같이 나타나는 `small flashy` 유형으로 해석합니다.",
        "",
        markdown_table(
            flow_check,
            [
                "basin",
                "gauge_name",
                "driver_group_ko",
                "flow_response_type_ko",
                "event_response_support_ko",
                "area_percentile",
                "obs_q99_percentile",
                "q99_event_frequency_percentile",
                "rbi_percentile",
                "event_duration_median_hours_percentile",
                "recent_precipitation_share_percentile",
                "antecedent_precipitation_share_percentile",
                "snowmelt_or_rain_on_snow_share_percentile",
                "uncertain_high_flow_candidate_share_percentile",
                "event_response_evidence_ko",
            ],
            {
                "basin": "Basin",
                "gauge_name": "Gauge",
                "driver_group_ko": "Driver 해석",
                "flow_response_type_ko": "Flow 유형",
                "event_response_support_ko": "Event-response 확인",
                "area_percentile": "Area pctile",
                "obs_q99_percentile": "Q99 pctile",
                "q99_event_frequency_percentile": "Q99 freq pctile",
                "rbi_percentile": "RBI pctile",
                "event_duration_median_hours_percentile": "Duration pctile",
                "recent_precipitation_share_percentile": "Recent pctile",
                "antecedent_precipitation_share_percentile": "Antecedent pctile",
                "snowmelt_or_rain_on_snow_share_percentile": "Snow/ROS pctile",
                "uncertain_high_flow_candidate_share_percentile": "Uncertain pctile",
                "event_response_evidence_ko": "근거",
            },
        ),
        "",
        *analysis_figure_section_lines(),
        "",
        "## Similarity Check",
        "",
        "아래 similarity check는 ratio가 가까운 basin pair를 기록한 보조 진단일 뿐, 이상치를 만든 causal group으로 쓰지는 않습니다.",
        "",
        "\n".join(grouped_lines),
        "",
        "## Far Basin Compact Table",
        "",
        markdown_table(
            far_table,
            [
                "basin",
                "gauge_name",
                "distance_class",
                "total_far_records",
                "NSE_far_records",
                "KGE_far_records",
                "FHV_far_records",
                "area",
                "snow_fraction",
                "cold_season_event_fraction",
                "recent_precipitation_share",
                "antecedent_precipitation_share",
                "snowmelt_or_rain_on_snow_share",
                "uncertain_high_flow_candidate_share",
                "obs_variance_denominator",
                "obs_q99",
                "q99_event_frequency",
                "rbi",
                "event_duration_median_hours",
            ],
            {
                "basin": "Basin",
                "gauge_name": "Gauge",
                "distance_class": "Class",
                "total_far_records": "Far records",
                "NSE_far_records": "NSE far",
                "KGE_far_records": "KGE far",
                "FHV_far_records": "FHV far",
                "area": "Area",
                "snow_fraction": "Snow frac",
                "cold_season_event_fraction": "Winter-event frac",
                "recent_precipitation_share": "Recent share",
                "antecedent_precipitation_share": "Antecedent share",
                "snowmelt_or_rain_on_snow_share": "Snow/ROS share",
                "uncertain_high_flow_candidate_share": "Uncertain share",
                "obs_variance_denominator": "NSE denom",
                "obs_q99": "Obs Q99",
                "q99_event_frequency": "Q99 freq",
                "rbi": "RBI",
                "event_duration_median_hours": "Duration h",
            },
        ),
        "",
        "## Far Basin Detailed Notes",
        "",
    ]
    for _, row in far_cause_diagnosis.iterrows():
        lines.append(detailed_far_basin_interpretation(row))
        lines.append("")

    lines.extend(
        [
            "## Files",
            "",
            f"- records: `{relative(args.output_dir / 'tables/metric_median_deviation_records.csv')}`",
            f"- basin summary: `{relative(args.output_dir / 'tables/metric_median_deviation_basin_summary.csv')}`",
            f"- basin tier profile: `{relative(args.output_dir / 'tables/metric_median_deviation_basin_tier_profile.csv')}`",
            f"- basin tier profile by model: `{relative(args.output_dir / 'tables/metric_median_deviation_basin_model_tier_profile.csv')}`",
            f"- tier distribution summary: `{relative(args.output_dir / 'tables/metric_median_deviation_tier_distribution_summary.csv')}`",
            f"- tier basin membership: `{relative(args.output_dir / 'tables/metric_median_deviation_tier_basin_membership.csv')}`",
            f"- model-seed far summary: `{relative(args.output_dir / 'tables/metric_median_deviation_model_seed_far_summary.csv')}`",
            f"- metric/model/seed far summary: `{relative(args.output_dir / 'tables/metric_median_deviation_metric_model_seed_far_summary.csv')}`",
            f"- basin model-seed far recurrence: `{relative(args.output_dir / 'tables/metric_median_deviation_basin_model_seed_far_recurrence.csv')}`",
            f"- seed metric change labels: `{relative(args.output_dir / 'tables/metric_median_deviation_seed_metric_change_labels.csv')}`",
            f"- seed metric change count check: `{relative(args.output_dir / 'tables/metric_median_deviation_seed_metric_change_count_check.csv')}`",
            f"- basin metric/model far counts: `{relative(args.output_dir / 'tables/metric_median_deviation_basin_metric_model_far_counts.csv')}`",
            f"- far cause diagnosis: `{relative(args.output_dir / 'tables/metric_median_deviation_far_cause_diagnosis.csv')}`",
            f"- far cause group summary: `{relative(args.output_dir / 'tables/metric_median_deviation_far_cause_group_summary.csv')}`",
            f"- far flow-response check: `{relative(args.output_dir / 'tables/metric_median_deviation_far_flow_response_check.csv')}`",
            f"- far compact profiles: `{relative(args.output_dir / 'tables/metric_median_deviation_far_basin_profiles.csv')}`",
            f"- conservative regime groups: `{relative(args.output_dir / 'tables/metric_median_deviation_regime_groups.csv')}`",
            f"- ungrouped basin profiles: `{relative(args.output_dir / 'tables/metric_median_deviation_ungrouped_profiles.csv')}`",
            f"- figure manifest: `{relative(args.output_dir / 'figures/metric_median_deviation_figure_manifest.csv')}`",
            f"- 한국어 해석 메모: `{relative(args.output_dir / 'report/metric_median_deviation_far_basin_interpretation_ko.md')}`",
        ]
    )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    args.attribute_root = resolve(args.attribute_root)
    args.output_dir = resolve(args.output_dir)
    tables_dir = args.output_dir / "tables"
    metadata_dir = args.output_dir / "metadata"
    report_dir = args.output_dir / "report"
    figures_dir = args.output_dir / "figures"
    for path in [tables_dir, metadata_dir, report_dir, figures_dir]:
        path.mkdir(parents=True, exist_ok=True)

    context = build_context(args)
    records, metric_values = build_median_distance_records(
        args.attribute_root,
        args.far_threshold,
        args.extreme_threshold,
    )
    records["is_far"] = records["median_distance_iqr"].ge(args.far_threshold)
    records["is_extreme"] = records["median_distance_iqr"].ge(args.extreme_threshold)
    basin_summary = summarize_by_basin(records, context, args.far_threshold, args.extreme_threshold)
    basin_summary = add_metric_seed_medians(basin_summary, args.attribute_root)
    basin_tier_profile = build_basin_tier_profile(records, basin_summary)
    basin_model_tier_profile = build_basin_model_tier_profile(records, basin_summary)
    tier_distribution_summary = build_tier_distribution_summary(records, basin_summary)
    tier_basin_membership = build_tier_basin_membership(records, basin_summary)
    model_seed_far_summary = build_model_seed_far_summary(records)
    metric_model_seed_far_summary = build_metric_model_seed_far_summary(records)
    basin_model_seed_far_recurrence = build_basin_model_seed_far_recurrence(records)
    seed_metric_changes = build_seed_metric_change_labels(records)
    basin_metric_model_far_counts = build_basin_metric_model_far_counts(records)
    far_cause_diagnosis = build_far_cause_diagnosis(basin_summary, basin_model_tier_profile)
    seed_metric_change_count_check = build_seed_metric_change_count_check(far_cause_diagnosis, seed_metric_changes)
    far_cause_group_summary = build_far_cause_group_summary(far_cause_diagnosis)

    far = basin_summary[basin_summary["total_far_records"].gt(0)].copy()
    groups = grouped_regime_rows(far)
    ungrouped = non_grouped_far(far, groups)

    records.to_csv(tables_dir / "metric_median_deviation_records.csv", index=False)
    metric_values.to_csv(tables_dir / "metric_primary_model_seed_values.csv", index=False)
    basin_summary.to_csv(tables_dir / "metric_median_deviation_basin_summary.csv", index=False)
    basin_tier_profile.to_csv(tables_dir / "metric_median_deviation_basin_tier_profile.csv", index=False)
    basin_model_tier_profile.to_csv(tables_dir / "metric_median_deviation_basin_model_tier_profile.csv", index=False)
    tier_distribution_summary.to_csv(tables_dir / "metric_median_deviation_tier_distribution_summary.csv", index=False)
    tier_basin_membership.to_csv(tables_dir / "metric_median_deviation_tier_basin_membership.csv", index=False)
    model_seed_far_summary.to_csv(tables_dir / "metric_median_deviation_model_seed_far_summary.csv", index=False)
    metric_model_seed_far_summary.to_csv(
        tables_dir / "metric_median_deviation_metric_model_seed_far_summary.csv",
        index=False,
    )
    basin_model_seed_far_recurrence.to_csv(
        tables_dir / "metric_median_deviation_basin_model_seed_far_recurrence.csv",
        index=False,
    )
    seed_metric_changes.to_csv(tables_dir / "metric_median_deviation_seed_metric_change_labels.csv", index=False)
    seed_metric_change_count_check.to_csv(
        tables_dir / "metric_median_deviation_seed_metric_change_count_check.csv",
        index=False,
    )
    basin_metric_model_far_counts.to_csv(
        tables_dir / "metric_median_deviation_basin_metric_model_far_counts.csv",
        index=False,
    )
    far_cause_diagnosis.to_csv(tables_dir / "metric_median_deviation_far_cause_diagnosis.csv", index=False)
    far_cause_group_summary.to_csv(tables_dir / "metric_median_deviation_far_cause_group_summary.csv", index=False)
    flow_response_check_frame(far_cause_diagnosis).to_csv(
        tables_dir / "metric_median_deviation_far_flow_response_check.csv",
        index=False,
    )
    compact_far_profiles(far).to_csv(tables_dir / "metric_median_deviation_far_basin_profiles.csv", index=False)
    groups.to_csv(tables_dir / "metric_median_deviation_regime_groups.csv", index=False)
    compact_far_profiles(ungrouped).to_csv(tables_dir / "metric_median_deviation_ungrouped_profiles.csv", index=False)
    figure_manifest = build_analysis_figures(
        figures_dir,
        basin_tier_profile,
        far_cause_diagnosis,
        seed_metric_changes,
        basin_metric_model_far_counts,
    )

    metadata = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "attribute_root": relative(args.attribute_root),
        "observed_stats": relative(resolve(args.observed_stats)),
        "event_response_summary": relative(resolve(args.event_response_summary)),
        "event_response_table": relative(resolve(args.event_response_table)),
        "flood_generation_summary": relative(resolve(args.flood_generation_summary)),
        "streamflow_quality": relative(resolve(args.streamflow_quality)),
        "metrics": METRICS,
        "models": MODELS,
        "seeds": SEEDS,
        "far_threshold_iqr": args.far_threshold,
        "extreme_threshold_iqr": args.extreme_threshold,
        "n_basins": int(basin_summary["basin"].nunique()),
        "n_records": int(len(records)),
        "n_far_basins": int(far["basin"].nunique()),
        "n_grouped_far_basins": int(sum(len(str(value).split()) for value in groups["basins"])) if not groups.empty else 0,
        "n_ungrouped_far_basins": int(ungrouped["basin"].nunique()),
        "seed_metric_change_count_mismatches": int((~seed_metric_change_count_check["count_delta_matches"]).sum()),
        "distance_tier_record_counts": {
            str(k): int(v) for k, v in records["distance_tier"].value_counts().reindex(TIER_ORDER).fillna(0).items()
        },
        "model_seed_far_records": {
            f"{row.model}_seed{int(row.seed)}": int(row.far_records)
            for row in model_seed_far_summary.itertuples(index=False)
        },
        "figures": {
            str(row.figure_key): str(row.path)
            for row in figure_manifest[figure_manifest["format"].eq("png")].itertuples(index=False)
        },
    }
    (metadata_dir / "metric_median_deviation_regime_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    write_report(
        report_dir / "metric_median_deviation_regime_report_ko.md",
        records,
        basin_summary,
        basin_tier_profile,
        basin_model_tier_profile,
        tier_distribution_summary,
        model_seed_far_summary,
        metric_model_seed_far_summary,
        basin_model_seed_far_recurrence,
        far_cause_group_summary,
        far_cause_diagnosis,
        far,
        groups,
        ungrouped,
        args,
    )
    write_korean_interpretation_report(
        report_dir / "metric_median_deviation_far_basin_interpretation_ko.md",
        basin_tier_profile,
        tier_distribution_summary,
        far_cause_group_summary,
        far_cause_diagnosis,
        model_seed_far_summary,
        metric_model_seed_far_summary,
        basin_model_seed_far_recurrence,
        args,
    )

    print(f"Wrote median-deviation regime analysis to {args.output_dir}")
    print(f"Far basins: {metadata['n_far_basins']} (grouped {metadata['n_grouped_far_basins']}, ungrouped {metadata['n_ungrouped_far_basins']})")


if __name__ == "__main__":
    main()
