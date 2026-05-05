#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.8",
#   "numpy>=1.26",
#   "pandas>=2.2",
#   "scipy>=1.13",
#   "tabulate>=0.9",
# ]
# ///
from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ATTRIBUTE_ROOT = (
    REPO_ROOT / "output/model_analysis/overall_analysis/main_comparison/attribute_correlations"
)
DEFAULT_OUTLIER_AUDIT = (
    DEFAULT_ATTRIBUTE_ROOT / "robustness/tables/primary_metric_attribute_iqr_outlier_audit.csv"
)
DEFAULT_EVENT_RESPONSE = (
    REPO_ROOT / "output/basin/drbc/analysis/event_response/tables/event_response_basin_summary.csv"
)
DEFAULT_OBS_STATS = (
    REPO_ROOT / "output/model_analysis/overall_analysis/result_checks/outlier_checks/test_observed_streamflow_stats.csv"
)
DEFAULT_STREAMFLOW_QUALITY = (
    REPO_ROOT / "output/basin/drbc/screening/drbc_streamflow_quality_table.csv"
)
DEFAULT_OUTPUT_DIR = DEFAULT_ATTRIBUTE_ROOT / "robustness"

STATIC_FEATURES = [
    "area",
    "slope",
    "aridity",
    "snow_fraction",
    "soil_depth",
    "permeability",
    "baseflow_index",
    "forest_fraction",
    "centroid_lat",
    "centroid_lng",
]
EVENT_FEATURES = [
    "q99_event_frequency",
    "rbi",
    "rising_time_median_hours",
    "event_duration_median_hours",
    "unit_area_peak_median",
    "unit_area_peak_p90",
    "annual_peak_unit_area_median",
    "annual_peak_unit_area_p90",
]
OBS_FEATURES = [
    "obs_cv",
    "obs_q99",
    "obs_max",
    "obs_variance_denominator",
]
QUALITY_FEATURES = [
    "FLOW_PCT_EST_VALUES",
    "BASIN_BOUNDARY_CONFIDENCE",
    "STOR_NOR_2009",
    "MAJ_NDAMS_2009",
    "CANALS_PCT",
    "FRESHW_WITHDRAWAL",
]
CONTRAST_FEATURES = STATIC_FEATURES + EVENT_FEATURES + OBS_FEATURES + QUALITY_FEATURES
PROFILE_FEATURES = [
    "area",
    "obs_variance_denominator",
    "obs_q99",
    "obs_cv",
    "q99_event_frequency",
    "rbi",
    "rising_time_median_hours",
    "event_duration_median_hours",
    "annual_peak_unit_area_p90",
    "slope",
    "aridity",
    "forest_fraction",
    "STOR_NOR_2009",
    "FRESHW_WITHDRAWAL",
]
FEATURE_LABELS = {
    "area": "Area",
    "slope": "Slope",
    "aridity": "Aridity",
    "snow_fraction": "Snow fraction",
    "soil_depth": "Soil depth",
    "permeability": "Permeability",
    "baseflow_index": "Baseflow index",
    "forest_fraction": "Forest fraction",
    "centroid_lat": "Centroid lat",
    "centroid_lng": "Centroid lng",
    "q99_event_frequency": "Q99 event freq",
    "rbi": "RBI",
    "rising_time_median_hours": "Rising time",
    "event_duration_median_hours": "Event duration",
    "unit_area_peak_median": "Unit-area peak med",
    "unit_area_peak_p90": "Unit-area peak p90",
    "annual_peak_unit_area_median": "Annual peak/unit med",
    "annual_peak_unit_area_p90": "Annual peak/unit p90",
    "obs_cv": "Observed CV",
    "obs_q99": "Observed Q99",
    "obs_max": "Observed max",
    "obs_variance_denominator": "NSE denom.",
    "FLOW_PCT_EST_VALUES": "Estimated flow %",
    "BASIN_BOUNDARY_CONFIDENCE": "Boundary confidence",
    "STOR_NOR_2009": "Storage",
    "MAJ_NDAMS_2009": "Major dams",
    "CANALS_PCT": "Canals %",
    "FRESHW_WITHDRAWAL": "Freshwater withdrawal",
}
FEATURE_GROUPS = {
    "static": STATIC_FEATURES,
    "event_response": EVENT_FEATURES,
    "observed_flow": OBS_FEATURES,
    "quality_hydromod": QUALITY_FEATURES,
}
METRIC_ORDER = ["NSE", "KGE", "FHV", "abs_FHV", "Peak_MAPE", "Peak_Timing"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare static attributes, event response, and observed-flow context for "
            "primary metric IQR outlier basins."
        )
    )
    parser.add_argument("--attribute-root", type=Path, default=DEFAULT_ATTRIBUTE_ROOT)
    parser.add_argument("--outlier-audit", type=Path, default=DEFAULT_OUTLIER_AUDIT)
    parser.add_argument("--event-response", type=Path, default=DEFAULT_EVENT_RESPONSE)
    parser.add_argument("--observed-stats", type=Path, default=DEFAULT_OBS_STATS)
    parser.add_argument("--streamflow-quality", type=Path, default=DEFAULT_STREAMFLOW_QUALITY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--repeated-threshold",
        type=int,
        default=5,
        help="Outlier-record count used to mark repeated outlier basins.",
    )
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


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


def safe_ratio(numerator: float, denominator: float) -> float:
    if pd.isna(numerator) or pd.isna(denominator) or denominator == 0:
        return math.nan
    return numerator / denominator


def percentile_of_score(values: pd.Series, score: float) -> float:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty or pd.isna(score):
        return math.nan
    return float(stats.percentileofscore(clean, score, kind="rank"))


def read_primary_basin_base(attribute_root: Path) -> pd.DataFrame:
    path = attribute_root / "NSE/tables/NSE_basin_metric_attribute_table.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing primary basin attribute table: {path}")
    frame = pd.read_csv(path, dtype={"basin": str, "gauge_id": str})
    frame["basin"] = frame["basin"].map(normalize_basin_id)
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
        "soil_depth",
        "permeability",
        "baseflow_index",
        "forest_fraction",
        "centroid_lat",
        "centroid_lng",
        "lat_gage",
        "lng_gage",
    ]
    frame = frame[[col for col in keep if col in frame.columns]].copy()
    return numeric_columns(frame)


def read_event_response(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"gauge_id": str})
    frame["basin"] = frame["gauge_id"].map(normalize_basin_id)
    keep = [
        "basin",
        "processing_status",
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
    frame = frame[[col for col in keep if col in frame.columns]].copy()
    return numeric_columns(frame)


def read_observed_stats(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"basin": str})
    frame["basin"] = frame["basin"].map(normalize_basin_id)
    keep = [
        "basin",
        "obs_status",
        "test_valid_hours",
        "obs_mean",
        "obs_std",
        "obs_cv",
        "obs_q99",
        "obs_max",
        "obs_near_zero_fraction",
        "obs_variance_denominator",
    ]
    frame = frame[[col for col in keep if col in frame.columns]].copy()
    return numeric_columns(frame)


def read_streamflow_quality(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"gauge_id": str})
    frame["basin"] = frame["gauge_id"].map(normalize_basin_id)
    keep = [
        "basin",
        "FLOW_PCT_EST_VALUES",
        "BASIN_BOUNDARY_CONFIDENCE",
        "STOR_NOR_2009",
        "MAJ_NDAMS_2009",
        "CANALS_PCT",
        "FRESHW_WITHDRAWAL",
        "hydromod_risk",
        "passes_streamflow_quality_gate",
    ]
    frame = frame[[col for col in keep if col in frame.columns]].copy()
    return numeric_columns(frame)


def read_outlier_audit(path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    audit = pd.read_csv(path, dtype={"basin": str})
    audit["basin"] = audit["basin"].map(normalize_basin_id)

    by_basin = (
        audit.groupby("basin", dropna=False)
        .agg(
            outlier_records=("basin", "size"),
            outlier_metric_count=("metric", "nunique"),
            outlier_metrics=("metric", lambda values: " ".join(sorted(set(map(str, values))))),
            outlier_sides=("outlier_side", lambda values: " ".join(sorted(set(map(str, values))))),
            worst_low_value=("target_metric_value", "min"),
            worst_high_value=("target_metric_value", "max"),
        )
        .reset_index()
    )

    metric_basin = (
        audit.groupby(["metric", "basin"], dropna=False)
        .agg(
            outlier_records=("basin", "size"),
            outlier_sides=("outlier_side", lambda values: " ".join(sorted(set(map(str, values))))),
            min_value=("target_metric_value", "min"),
            max_value=("target_metric_value", "max"),
            models=("model", lambda values: " ".join(sorted(set(map(str, values))))),
            seeds=("seed", lambda values: " ".join(map(str, sorted(set(values))))),
        )
        .reset_index()
    )
    return audit, by_basin, metric_basin


def numeric_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    numeric_candidates = set(
        CONTRAST_FEATURES
        + [
            "lat_gage",
            "lng_gage",
            "q99_event_count",
            "event_count",
            "annual_peak_years",
            "event_runoff_coefficient_median",
            "test_valid_hours",
            "obs_mean",
            "obs_std",
            "obs_near_zero_fraction",
            "outlier_records",
            "outlier_metric_count",
            "worst_low_value",
            "worst_high_value",
        ]
    )
    for column in numeric_candidates:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    return out


def build_analysis_frame(
    attribute_root: Path,
    event_response: Path,
    observed_stats: Path,
    streamflow_quality: Path,
    outlier_by_basin: pd.DataFrame,
    repeated_threshold: int,
) -> pd.DataFrame:
    frame = read_primary_basin_base(attribute_root)
    frame = frame.merge(read_event_response(event_response), on="basin", how="left")
    frame = frame.merge(read_observed_stats(observed_stats), on="basin", how="left")
    frame = frame.merge(read_streamflow_quality(streamflow_quality), on="basin", how="left")
    frame = frame.merge(outlier_by_basin, on="basin", how="left")

    frame["outlier_records"] = frame["outlier_records"].fillna(0).astype(int)
    frame["outlier_metric_count"] = frame["outlier_metric_count"].fillna(0).astype(int)
    frame["is_outlier"] = frame["outlier_records"].gt(0)
    frame["is_repeated_outlier"] = frame["outlier_records"].ge(repeated_threshold)
    frame["area_lt_50"] = frame["area"].lt(50)
    frame["outlier_metrics"] = frame["outlier_metrics"].fillna("")
    frame["outlier_sides"] = frame["outlier_sides"].fillna("")
    return numeric_columns(frame)


def summarize_feature_contrasts(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for group_name, features in FEATURE_GROUPS.items():
        for feature in features:
            if feature not in frame.columns:
                continue
            full = pd.to_numeric(frame[feature], errors="coerce").dropna()
            out = pd.to_numeric(frame.loc[frame["is_outlier"], feature], errors="coerce").dropna()
            non = pd.to_numeric(frame.loc[~frame["is_outlier"], feature], errors="coerce").dropna()
            repeated = pd.to_numeric(frame.loc[frame["is_repeated_outlier"], feature], errors="coerce").dropna()
            if full.empty or out.empty or non.empty:
                continue
            out_median = float(out.median())
            non_median = float(non.median())
            repeated_median = float(repeated.median()) if not repeated.empty else math.nan
            p_value = (
                float(stats.mannwhitneyu(out, non, alternative="two-sided").pvalue)
                if len(out) and len(non)
                else math.nan
            )
            rows.append(
                {
                    "feature_group": group_name,
                    "feature": feature,
                    "label": FEATURE_LABELS.get(feature, feature),
                    "n_full": int(full.size),
                    "n_outlier": int(out.size),
                    "n_non_outlier": int(non.size),
                    "n_repeated_outlier": int(repeated.size),
                    "full_median": float(full.median()),
                    "outlier_median": out_median,
                    "non_outlier_median": non_median,
                    "repeated_outlier_median": repeated_median,
                    "outlier_q25": float(out.quantile(0.25)),
                    "outlier_q75": float(out.quantile(0.75)),
                    "non_outlier_q25": float(non.quantile(0.25)),
                    "non_outlier_q75": float(non.quantile(0.75)),
                    "outlier_to_non_median_ratio": safe_ratio(out_median, non_median),
                    "repeated_to_non_median_ratio": safe_ratio(repeated_median, non_median),
                    "outlier_median_percentile": percentile_of_score(full, out_median),
                    "repeated_median_percentile": percentile_of_score(full, repeated_median),
                    "mannwhitney_p": p_value,
                }
            )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["abs_log_outlier_to_non_ratio"] = np.log(
        result["outlier_to_non_median_ratio"].replace(0, np.nan)
    ).abs()
    result = result.sort_values(
        ["feature_group", "abs_log_outlier_to_non_ratio"],
        ascending=[True, False],
    )
    return result


def summarize_metric_feature_contrasts(
    frame: pd.DataFrame,
    metric_basin: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for metric, metric_rows in metric_basin.groupby("metric"):
        metric_outliers = set(metric_rows["basin"])
        for feature in PROFILE_FEATURES:
            if feature not in frame.columns:
                continue
            full = pd.to_numeric(frame[feature], errors="coerce").dropna()
            out = pd.to_numeric(
                frame.loc[frame["basin"].isin(metric_outliers), feature],
                errors="coerce",
            ).dropna()
            non = pd.to_numeric(
                frame.loc[~frame["basin"].isin(metric_outliers), feature],
                errors="coerce",
            ).dropna()
            if full.empty or out.empty or non.empty:
                continue
            out_median = float(out.median())
            non_median = float(non.median())
            rows.append(
                {
                    "metric": metric,
                    "feature": feature,
                    "label": FEATURE_LABELS.get(feature, feature),
                    "n_metric_outlier": int(out.size),
                    "n_metric_non_outlier": int(non.size),
                    "metric_outlier_median": out_median,
                    "metric_non_outlier_median": non_median,
                    "metric_outlier_to_non_ratio": safe_ratio(out_median, non_median),
                    "metric_outlier_median_percentile": percentile_of_score(full, out_median),
                }
            )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["metric"] = pd.Categorical(result["metric"], categories=METRIC_ORDER, ordered=True)
    result = result.sort_values(["metric", "feature"])
    result["metric"] = result["metric"].astype(str)
    return result


def build_top_basin_profiles(frame: pd.DataFrame) -> pd.DataFrame:
    profiles = frame[frame["is_outlier"]].copy()
    percentile_features = sorted(set(PROFILE_FEATURES + STATIC_FEATURES + EVENT_FEATURES + OBS_FEATURES))
    for feature in percentile_features:
        if feature not in profiles.columns or feature not in frame.columns:
            continue
        profiles[f"{feature}_percentile"] = profiles[feature].map(
            lambda value, col=feature: percentile_of_score(frame[col], value)
        )
    keep = [
        "basin",
        "gauge_name",
        "state",
        "outlier_records",
        "outlier_metric_count",
        "outlier_metrics",
        "outlier_sides",
        "is_repeated_outlier",
        "area_lt_50",
        "hydromod_risk",
    ]
    keep += [col for col in CONTRAST_FEATURES if col in profiles.columns]
    keep += [col for col in profiles.columns if col.endswith("_percentile")]
    return profiles[[col for col in keep if col in profiles.columns]].sort_values(
        ["outlier_records", "area"],
        ascending=[False, True],
    )


def classify_basin_profiles(profiles: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in profiles.itertuples(index=False):
        flags = []
        area = getattr(row, "area", math.nan)
        obs_den = getattr(row, "obs_variance_denominator", math.nan)
        q99_freq = getattr(row, "q99_event_frequency", math.nan)
        rbi = getattr(row, "rbi", math.nan)
        duration = getattr(row, "event_duration_median_hours", math.nan)
        annual_peak_p90 = getattr(row, "annual_peak_unit_area_p90", math.nan)
        hydromod = getattr(row, "hydromod_risk", False)
        if pd.notna(area) and area < 50:
            flags.append("small_area")
        if pd.notna(obs_den) and "obs_variance_denominator_percentile" in profiles.columns:
            percentile = getattr(row, "obs_variance_denominator_percentile", math.nan)
            if pd.notna(percentile) and percentile <= 25:
                flags.append("low_observed_variance")
        if (pd.notna(q99_freq) and q99_freq >= 10) or (pd.notna(rbi) and rbi >= 0.08):
            flags.append("frequent_or_flashy_events")
        if pd.notna(duration) and duration <= 9:
            flags.append("short_event_duration")
        if pd.notna(annual_peak_p90) and "annual_peak_unit_area_p90_percentile" in profiles.columns:
            percentile = getattr(row, "annual_peak_unit_area_p90_percentile", math.nan)
            if pd.notna(percentile) and percentile >= 75:
                flags.append("high_unit_area_peak")
        if bool(hydromod):
            flags.append("hydromod_risk")
        rows.append(
            {
                "basin": row.basin,
                "gauge_name": row.gauge_name,
                "outlier_records": row.outlier_records,
                "outlier_metrics": row.outlier_metrics,
                "interpretation_flags": " ".join(flags),
            }
        )
    return pd.DataFrame(rows)


def plot_feature_contrast(contrasts: pd.DataFrame, output_path: Path) -> None:
    if contrasts.empty:
        return
    selected = contrasts[
        contrasts["feature"].isin(
            [
                "area",
                "obs_variance_denominator",
                "obs_q99",
                "obs_cv",
                "q99_event_frequency",
                "rbi",
                "event_duration_median_hours",
                "annual_peak_unit_area_p90",
                "slope",
                "STOR_NOR_2009",
                "FRESHW_WITHDRAWAL",
            ]
        )
    ].copy()
    selected["sort_value"] = selected["outlier_median_percentile"].sub(50).abs()
    selected = selected.sort_values("sort_value", ascending=True)

    y = np.arange(len(selected))
    fig, ax = plt.subplots(figsize=(10.5, max(5.6, 0.48 * len(selected))))
    ax.axvline(50, color="#6b7280", linewidth=1.0)
    ax.barh(
        y,
        selected["outlier_median_percentile"] - 50,
        left=50,
        color=np.where(selected["outlier_median_percentile"] >= 50, "#2563eb", "#dc2626"),
        alpha=0.82,
    )
    for idx, row in enumerate(selected.itertuples(index=False)):
        ax.text(
            row.outlier_median_percentile + (1.2 if row.outlier_median_percentile >= 50 else -1.2),
            idx,
            f"{row.outlier_median_percentile:.0f}p",
            va="center",
            ha="left" if row.outlier_median_percentile >= 50 else "right",
            fontsize=9,
        )
    ax.set_yticks(y, selected["label"])
    ax.set_xlim(0, 100)
    ax.set_xlabel("Outlier-basin median percentile within primary DRBC basins")
    ax.set_title("Where do outlier basins sit in static/event/observed-flow distributions?")
    ax.grid(True, axis="x", color="#e5e7eb", linewidth=0.7)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def plot_top_basin_profile(profiles: pd.DataFrame, output_path: Path) -> None:
    if profiles.empty:
        return
    top = profiles.sort_values("outlier_records", ascending=False).head(12).copy()
    feature_cols = [f"{feature}_percentile" for feature in PROFILE_FEATURES if f"{feature}_percentile" in top.columns]
    if not feature_cols:
        return
    matrix = top[feature_cols].to_numpy(dtype=float)
    labels = [FEATURE_LABELS.get(col.removesuffix("_percentile"), col) for col in feature_cols]
    row_labels = [
        f"{row.basin}\n{int(row.outlier_records)} rec"
        for row in top.itertuples(index=False)
    ]

    fig, ax = plt.subplots(figsize=(14.5, max(5.8, 0.55 * len(top))))
    image = ax.imshow(matrix, aspect="auto", cmap="RdBu_r", vmin=0, vmax=100)
    ax.set_xticks(np.arange(len(labels)), labels, rotation=35, ha="right")
    ax.set_yticks(np.arange(len(row_labels)), row_labels)
    ax.set_title("Top primary outlier basin profiles by percentile rank")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = matrix[i, j]
            if np.isfinite(value):
                ax.text(j, i, f"{value:.0f}", ha="center", va="center", fontsize=7, color="#111827")
    cbar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("Percentile in primary DRBC basin set")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def plot_metric_contrast(metric_contrasts: pd.DataFrame, output_path: Path) -> None:
    if metric_contrasts.empty:
        return
    selected_features = [
        "area",
        "obs_variance_denominator",
        "obs_cv",
        "q99_event_frequency",
        "rbi",
        "event_duration_median_hours",
        "annual_peak_unit_area_p90",
        "slope",
    ]
    pivot = (
        metric_contrasts[metric_contrasts["feature"].isin(selected_features)]
        .pivot(index="metric", columns="feature", values="metric_outlier_median_percentile")
        .reindex(index=[m for m in METRIC_ORDER if m in set(metric_contrasts["metric"])])
        .reindex(columns=selected_features)
    )
    if pivot.empty:
        return
    fig, ax = plt.subplots(figsize=(12.5, max(4.6, 0.55 * len(pivot))))
    image = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap="RdBu_r", vmin=0, vmax=100)
    ax.set_xticks(np.arange(len(pivot.columns)), [FEATURE_LABELS.get(col, col) for col in pivot.columns], rotation=35, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)), pivot.index)
    ax.set_title("Metric-specific outlier basin median percentiles")
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            value = pivot.iloc[i, j]
            if np.isfinite(value):
                ax.text(j, i, f"{value:.0f}", ha="center", va="center", fontsize=8)
    cbar = fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Percentile in primary DRBC basin set")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def plot_event_static_scatter(frame: pd.DataFrame, output_path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13.4, 5.5))
    size = np.where(frame["outlier_records"].gt(0), 35 + 10 * frame["outlier_records"], 34)
    color = np.where(frame["is_outlier"], "#dc2626", "#9ca3af")

    axes[0].scatter(frame["area"], frame["obs_variance_denominator"], s=size, c=color, alpha=0.78, edgecolors="#111827", linewidths=0.35)
    axes[0].set_xscale("log")
    axes[0].set_yscale("log")
    axes[0].set_xlabel("Area (km2, log)")
    axes[0].set_ylabel("NSE denominator (log)")
    axes[0].set_title("Small and low-variance basins dominate repeated outliers")
    axes[0].grid(True, color="#e5e7eb", linewidth=0.7)

    axes[1].scatter(frame["q99_event_frequency"], frame["annual_peak_unit_area_p90"], s=size, c=color, alpha=0.78, edgecolors="#111827", linewidths=0.35)
    axes[1].set_xlabel("Q99 event frequency (events/year)")
    axes[1].set_ylabel("Annual peak / area p90")
    axes[1].set_title("Some outliers also have frequent/high unit-area peaks")
    axes[1].grid(True, color="#e5e7eb", linewidth=0.7)

    for row in frame[frame["outlier_records"].ge(8)].itertuples(index=False):
        axes[0].annotate(row.basin, (row.area, row.obs_variance_denominator), fontsize=8, xytext=(4, 4), textcoords="offset points")
        axes[1].annotate(row.basin, (row.q99_event_frequency, row.annual_peak_unit_area_p90), fontsize=8, xytext=(4, 4), textcoords="offset points")

    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def write_markdown_summary(
    output_path: Path,
    frame: pd.DataFrame,
    contrasts: pd.DataFrame,
    profiles: pd.DataFrame,
    archetypes: pd.DataFrame,
) -> None:
    small_outliers = int(frame.loc[frame["is_outlier"], "area_lt_50"].sum())
    repeated = frame[frame["is_repeated_outlier"]]
    outlier_count = int(frame["is_outlier"].sum())
    repeated_count = int(frame["is_repeated_outlier"].sum())

    def contrast_line(feature: str) -> str:
        row = contrasts[contrasts["feature"].eq(feature)]
        if row.empty:
            return ""
        r = row.iloc[0]
        return (
            f"- {r['label']}: outlier median {r['outlier_median']:.4g}, "
            f"non-outlier median {r['non_outlier_median']:.4g}, "
            f"ratio {r['outlier_to_non_median_ratio']:.3g}, "
            f"percentile {r['outlier_median_percentile']:.0f}."
        )

    lines = [
        "# Primary metric outlier basin characteristics",
        "",
        f"- Primary basin count: {len(frame)}.",
        f"- IQR outlier basins: {outlier_count}; repeated outliers: {repeated_count}.",
        f"- Small outlier basins with area < 50 km2: {small_outliers}/{outlier_count}.",
        "",
        "## Strongest contrasts",
        contrast_line("obs_variance_denominator"),
        contrast_line("area"),
        contrast_line("obs_q99"),
        contrast_line("obs_max"),
        contrast_line("q99_event_frequency"),
        contrast_line("rbi"),
        "",
        "## Repeated outlier basins",
        profiles[
            [
                "basin",
                "gauge_name",
                "outlier_records",
                "outlier_metrics",
                "area",
                "obs_variance_denominator",
                "q99_event_frequency",
                "rbi",
                "annual_peak_unit_area_p90",
            ]
        ]
        .head(12)
        .to_markdown(index=False),
        "",
        "## Interpretation flags",
        archetypes.to_markdown(index=False),
        "",
        "Interpretation: repeated metric outliers are mostly a small-basin/low-observed-variance problem, with a secondary group showing frequent, short, or high unit-area event response. This combination makes NSE/KGE and peak-relative metrics unstable because modest absolute errors become very large normalized errors.",
    ]
    output_path.write_text("\n".join(line for line in lines if line is not None), encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_dir = resolve(args.output_dir)
    tables_dir = output_dir / "tables"
    figures_dir = output_dir / "figures"
    metadata_dir = output_dir / "metadata"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    audit, outlier_by_basin, metric_basin = read_outlier_audit(resolve(args.outlier_audit))
    frame = build_analysis_frame(
        resolve(args.attribute_root),
        resolve(args.event_response),
        resolve(args.observed_stats),
        resolve(args.streamflow_quality),
        outlier_by_basin,
        args.repeated_threshold,
    )
    contrasts = summarize_feature_contrasts(frame)
    metric_contrasts = summarize_metric_feature_contrasts(frame, metric_basin)
    profiles = build_top_basin_profiles(frame)
    archetypes = classify_basin_profiles(profiles)

    frame_path = tables_dir / "primary_metric_attribute_outlier_basin_characteristics.csv"
    contrast_path = tables_dir / "primary_metric_attribute_outlier_feature_contrast.csv"
    metric_contrast_path = tables_dir / "primary_metric_attribute_outlier_metric_feature_contrast.csv"
    profile_path = tables_dir / "primary_metric_attribute_outlier_top_basin_profiles.csv"
    archetype_path = tables_dir / "primary_metric_attribute_outlier_interpretation_flags.csv"
    report_path = output_dir / "primary_metric_attribute_outlier_characteristics_report.md"

    frame.to_csv(frame_path, index=False)
    contrasts.to_csv(contrast_path, index=False)
    metric_contrasts.to_csv(metric_contrast_path, index=False)
    profiles.to_csv(profile_path, index=False)
    archetypes.to_csv(archetype_path, index=False)

    plot_feature_contrast(
        contrasts,
        figures_dir / "outlier_feature_contrast_percentiles.png",
    )
    plot_top_basin_profile(
        profiles,
        figures_dir / "outlier_top_basin_profile_percentiles.png",
    )
    plot_metric_contrast(
        metric_contrasts,
        figures_dir / "outlier_metric_feature_percentiles.png",
    )
    plot_event_static_scatter(
        frame,
        figures_dir / "outlier_event_static_scatter.png",
    )
    write_markdown_summary(report_path, frame, contrasts, profiles, archetypes)

    metadata = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "script": str(Path(__file__).resolve()),
        "inputs": {
            "attribute_root": str(resolve(args.attribute_root)),
            "outlier_audit": str(resolve(args.outlier_audit)),
            "event_response": str(resolve(args.event_response)),
            "observed_stats": str(resolve(args.observed_stats)),
            "streamflow_quality": str(resolve(args.streamflow_quality)),
        },
        "repeated_threshold": args.repeated_threshold,
        "primary_basin_count": int(len(frame)),
        "outlier_basin_count": int(frame["is_outlier"].sum()),
        "repeated_outlier_basin_count": int(frame["is_repeated_outlier"].sum()),
        "outputs": {
            "basin_characteristics": str(frame_path),
            "feature_contrast": str(contrast_path),
            "metric_feature_contrast": str(metric_contrast_path),
            "top_basin_profiles": str(profile_path),
            "interpretation_flags": str(archetype_path),
            "report": str(report_path),
        },
    }
    metadata_path = metadata_dir / "primary_metric_attribute_outlier_characteristics_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Wrote basin characteristics to {frame_path}")
    print(f"Wrote feature contrasts to {contrast_path}")
    print(f"Wrote top basin profiles to {profile_path}")
    print(f"Wrote report to {report_path}")
    print(f"Outlier basins: {metadata['outlier_basin_count']}; repeated: {metadata['repeated_outlier_basin_count']}")


if __name__ == "__main__":
    main()
