#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.8",
#   "numpy>=1.26",
#   "pandas>=2.2",
#   "tabulate>=0.9",
# ]
# ///
from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MAIN = REPO_ROOT / "output/model_analysis/overall_analysis/main_comparison"
DEFAULT_QUANTILE = REPO_ROOT / "output/model_analysis/quantile_analysis"
DEFAULT_STRESS = REPO_ROOT / "output/model_analysis/extreme_rain/primary/analysis"
DEFAULT_OUTPUT_DIR = DEFAULT_MAIN

POSITIVE_BETTER = {
    "delta_NSE": "NSE",
    "delta_KGE": "KGE",
    "abs_FHV_reduction": "abs(FHV) reduction",
    "Peak_Timing_reduction": "Peak timing reduction",
    "Peak_MAPE_reduction": "Peak MAPE reduction",
}
SIGNED_METRICS = {"delta_FHV": "Signed FHV shift"}
SCENARIOS = [
    ("full", "All primary basins"),
    ("exclude_iqr_outliers", "Exclude IQR outlier basins"),
    ("exclude_repeated_outliers", "Exclude repeated outlier basins"),
    ("area_ge_50", "Area >= 50 km2"),
]
SCENARIO_SHORT_LABELS = {
    "full": "Full",
    "exclude_iqr_outliers": "No IQR\noutliers",
    "exclude_repeated_outliers": "No repeated\noutliers",
    "area_ge_50": "Area >= 50",
}
PREDICTOR_ORDER = ["Model 1", "Model 2 q50", "Model 2 q95", "Model 2 q99"]
PREDICTOR_COLORS = {
    "Model 1": "#374151",
    "Model 2 q50": "#2563eb",
    "Model 2 q95": "#059669",
    "Model 2 q99": "#dc2626",
}
CLAIM_FIGURE_DIRNAME = "overall_conclusion"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize how to conclude subset300 primary overall performance."
    )
    parser.add_argument("--main-comparison-dir", type=Path, default=DEFAULT_MAIN)
    parser.add_argument("--quantile-dir", type=Path, default=DEFAULT_QUANTILE)
    parser.add_argument("--stress-dir", type=Path, default=DEFAULT_STRESS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
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


def fmt(value: float, digits: int = 3) -> str:
    if pd.isna(value):
        return ""
    return f"{value:.{digits}f}"


def read_primary(main_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    epoch_summary = pd.read_csv(main_dir / "tables/primary_epoch_summary.csv")
    delta_summary = pd.read_csv(main_dir / "tables/primary_epoch_delta_summary.csv")
    basin_deltas = pd.read_csv(main_dir / "tables/primary_epoch_basin_deltas.csv", dtype={"basin": str})
    basin_deltas["basin"] = basin_deltas["basin"].map(normalize_basin_id)
    return epoch_summary, delta_summary, basin_deltas


def read_outlier_context(main_dir: Path) -> pd.DataFrame:
    path = (
        main_dir
        / "attribute_correlations/robustness/tables/primary_metric_attribute_outlier_basin_characteristics.csv"
    )
    if not path.exists():
        return pd.DataFrame(columns=["basin", "is_outlier", "is_repeated_outlier", "area_lt_50"])
    frame = pd.read_csv(path, dtype={"basin": str})
    frame["basin"] = frame["basin"].map(normalize_basin_id)
    for column in ["is_outlier", "is_repeated_outlier", "area_lt_50"]:
        if column in frame.columns:
            frame[column] = frame[column].fillna(False).astype(bool)
    return frame


def scenario_mask(frame: pd.DataFrame, scenario: str) -> pd.Series:
    if scenario == "full":
        return pd.Series(True, index=frame.index)
    if scenario == "exclude_iqr_outliers":
        return ~frame["is_outlier"].fillna(False)
    if scenario == "exclude_repeated_outliers":
        return ~frame["is_repeated_outlier"].fillna(False)
    if scenario == "area_ge_50":
        return ~frame["area_lt_50"].fillna(False)
    raise ValueError(scenario)


def summarize_metric(frame: pd.DataFrame, metric: str, positive_better: bool) -> dict[str, Any]:
    values = pd.to_numeric(frame[metric], errors="coerce").dropna()
    if values.empty:
        return {}
    by_seed = (
        frame.groupby("seed", dropna=False)[metric]
        .agg(seed_median="median", positive_fraction=lambda x: float((x > 0).mean()))
        .reset_index()
    )
    if positive_better:
        favorable_fraction = float((values > 0).mean())
        favorable_seed_count = int((by_seed["seed_median"] > 0).sum())
    else:
        favorable_fraction = float("nan")
        favorable_seed_count = int((by_seed["seed_median"] < 0).sum())
    return {
        "pooled_n": int(values.size),
        "pooled_median": float(values.median()),
        "pooled_q25": float(values.quantile(0.25)),
        "pooled_q75": float(values.quantile(0.75)),
        "pooled_mean": float(values.mean()),
        "pooled_positive_fraction": float((values > 0).mean()),
        "favorable_fraction": favorable_fraction,
        "seed_medians": "; ".join(
            f"{int(row.seed)}:{row.seed_median:.3f}" for row in by_seed.itertuples(index=False)
        ),
        "seed_positive_fractions": "; ".join(
            f"{int(row.seed)}:{row.positive_fraction:.2f}" for row in by_seed.itertuples(index=False)
        ),
        "favorable_seed_count": favorable_seed_count,
    }


def build_robust_delta_summary(basin_deltas: pd.DataFrame, outlier_context: pd.DataFrame) -> pd.DataFrame:
    context_cols = ["basin", "is_outlier", "is_repeated_outlier", "area_lt_50"]
    context = outlier_context[[col for col in context_cols if col in outlier_context.columns]].copy()
    frame = basin_deltas.merge(context, on="basin", how="left")
    for column in ["is_outlier", "is_repeated_outlier", "area_lt_50"]:
        if column not in frame.columns:
            frame[column] = False
        frame[column] = frame[column].fillna(False).astype(bool)

    rows: list[dict[str, Any]] = []
    for scenario, scenario_label in SCENARIOS:
        sub = frame.loc[scenario_mask(frame, scenario)].copy()
        for metric, label in POSITIVE_BETTER.items():
            summary = summarize_metric(sub, metric, positive_better=True)
            if not summary:
                continue
            rows.append(
                {
                    "scenario": scenario,
                    "scenario_label": scenario_label,
                    "metric": metric,
                    "label": label,
                    "interpretation": "positive_better",
                    **summary,
                }
            )
        for metric, label in SIGNED_METRICS.items():
            summary = summarize_metric(sub, metric, positive_better=False)
            if not summary:
                continue
            rows.append(
                {
                    "scenario": scenario,
                    "scenario_label": scenario_label,
                    "metric": metric,
                    "label": label,
                    "interpretation": "signed_shift",
                    **summary,
                }
            )
    return pd.DataFrame(rows)


def build_seed_median_table(delta_summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for seed_row in delta_summary.itertuples(index=False):
        rows.extend(
            [
                {
                    "seed": seed_row.seed,
                    "metric": "NSE",
                    "median_delta": seed_row.median_delta_NSE,
                    "improved_fraction": seed_row.improved_fraction_delta_NSE,
                    "interpretation": "positive_better",
                },
                {
                    "seed": seed_row.seed,
                    "metric": "KGE",
                    "median_delta": seed_row.median_delta_KGE,
                    "improved_fraction": seed_row.improved_fraction_delta_KGE,
                    "interpretation": "positive_better",
                },
                {
                    "seed": seed_row.seed,
                    "metric": "Signed FHV",
                    "median_delta": seed_row.median_delta_FHV,
                    "improved_fraction": seed_row.improved_fraction_delta_FHV,
                    "interpretation": "signed_shift",
                },
                {
                    "seed": seed_row.seed,
                    "metric": "abs(FHV) reduction",
                    "median_delta": seed_row.median_abs_FHV_reduction,
                    "improved_fraction": seed_row.improved_fraction_abs_FHV_reduction,
                    "interpretation": "positive_better",
                },
                {
                    "seed": seed_row.seed,
                    "metric": "Peak timing reduction",
                    "median_delta": seed_row.median_Peak_Timing_reduction,
                    "improved_fraction": seed_row.improved_fraction_Peak_Timing_reduction,
                    "interpretation": "positive_better",
                },
                {
                    "seed": seed_row.seed,
                    "metric": "Peak MAPE reduction",
                    "median_delta": seed_row.median_Peak_MAPE_reduction,
                    "improved_fraction": seed_row.improved_fraction_Peak_MAPE_reduction,
                    "interpretation": "positive_better",
                },
            ]
        )
    return pd.DataFrame(rows)


def read_quantile_high_flow(quantile_dir: Path) -> pd.DataFrame:
    path = quantile_dir / "analysis/flow_strata_predictor_aggregate.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    keep = frame[
        frame["comparison"].eq("primary")
        & frame["stratum"].isin(["basin_top1", "observed_peak_hour"])
        & frame["predictor"].isin(["Model 1", "Model 2 q50", "Model 2 q95", "Model 2 q99"])
    ].copy()
    columns = [
        "stratum",
        "predictor",
        "median_underestimation_fraction",
        "median_median_rel_bias_pct",
        "median_median_abs_error",
    ]
    return keep[columns].sort_values(["stratum", "predictor"])


def read_stress_summary(stress_dir: Path) -> pd.DataFrame:
    path = stress_dir / "cohort_predictor_aggregate.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    keep = frame[
        frame["response_class"].isin(["flood_response_ge25", "flood_response_ge2_to_lt25", "low_response_below_q99"])
        & frame["predictor_label"].isin(["Model 1", "Model 2 q50", "Model 2 q95", "Model 2 q99"])
    ].copy()
    columns = [
        "stress_group",
        "response_class",
        "predictor_label",
        "mean_n_events",
        "seed_mean_underestimation_fraction_at_observed_peak",
        "seed_mean_median_obs_peak_under_deficit_pct",
        "seed_mean_mean_threshold_exceedance_recall",
        "seed_mean_median_pred_window_peak_to_flood_ari100",
    ]
    return keep[columns].sort_values(["response_class", "predictor_label"])


def model_seed_snapshot(epoch_summary: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "model_label",
        "seed",
        "epoch",
        "n_basins",
        "negative_nse_basins",
        "median_NSE",
        "median_KGE",
        "median_FHV",
        "median_abs_FHV",
        "median_Peak_Timing",
        "median_Peak_MAPE",
    ]
    return epoch_summary[columns].copy()


def build_claim_table(
    robust: pd.DataFrame,
    quantile: pd.DataFrame,
    stress: pd.DataFrame,
) -> pd.DataFrame:
    full = robust[robust["scenario"].eq("full")].set_index("metric")
    no_out = robust[robust["scenario"].eq("exclude_iqr_outliers")].set_index("metric")

    def full_value(metric: str, column: str) -> float:
        return float(full.loc[metric, column]) if metric in full.index else np.nan

    def no_out_value(metric: str, column: str) -> float:
        return float(no_out.loc[metric, column]) if metric in no_out.index else np.nan

    rows = [
        {
            "axis": "central_hydrograph_skill",
            "analysis": "primary paired seed/basin delta",
            "primary_evidence": (
                f"NSE median delta {fmt(full_value('delta_NSE', 'pooled_median'))}; "
                f"positive fraction {fmt(full_value('delta_NSE', 'pooled_positive_fraction'))}; "
                f"seed medians {full.loc['delta_NSE', 'seed_medians']}"
            ),
            "robustness": (
                f"after IQR outlier removal median {fmt(no_out_value('delta_NSE', 'pooled_median'))}, "
                f"positive fraction {fmt(no_out_value('delta_NSE', 'pooled_positive_fraction'))}"
            ),
            "claim_strength": "moderate_full_weak_robust",
            "safe_conclusion": "Model 2 q50 preserves NSE central skill; full-sample improvement is attenuated after outlier removal.",
        },
        {
            "axis": "balanced_skill_guardrail",
            "analysis": "primary paired KGE delta",
            "primary_evidence": (
                f"KGE median delta {fmt(full_value('delta_KGE', 'pooled_median'))}; "
                f"positive fraction {fmt(full_value('delta_KGE', 'pooled_positive_fraction'))}; "
                f"seed medians {full.loc['delta_KGE', 'seed_medians']}"
            ),
            "robustness": (
                f"after IQR outlier removal median {fmt(no_out_value('delta_KGE', 'pooled_median'))}, "
                f"positive fraction {fmt(no_out_value('delta_KGE', 'pooled_positive_fraction'))}"
            ),
            "claim_strength": "weak_to_moderate",
            "safe_conclusion": "KGE evidence is mixed; use as a guardrail, not as the main improvement claim.",
        },
        {
            "axis": "q50_high_flow_volume",
            "analysis": "signed FHV and abs(FHV) reduction",
            "primary_evidence": (
                f"signed FHV median shift {fmt(full_value('delta_FHV', 'pooled_median'))}; "
                f"abs(FHV) reduction median {fmt(full_value('abs_FHV_reduction', 'pooled_median'))}; "
                f"seed medians {full.loc['abs_FHV_reduction', 'seed_medians']}"
            ),
            "robustness": (
                f"after IQR outlier removal abs(FHV) reduction median "
                f"{fmt(no_out_value('abs_FHV_reduction', 'pooled_median'))}"
            ),
            "claim_strength": "negative_for_q50",
            "safe_conclusion": "Model 2 q50 should not be claimed as improving high-flow volume; it shifts high-flow bias downward.",
        },
        {
            "axis": "peak_timing",
            "analysis": "primary paired peak timing reduction",
            "primary_evidence": (
                f"median reduction {fmt(full_value('Peak_Timing_reduction', 'pooled_median'))} h; "
                f"positive fraction {fmt(full_value('Peak_Timing_reduction', 'pooled_positive_fraction'))}; "
                f"seed medians {full.loc['Peak_Timing_reduction', 'seed_medians']}"
            ),
            "robustness": (
                f"after IQR outlier removal median {fmt(no_out_value('Peak_Timing_reduction', 'pooled_median'))} h"
            ),
            "claim_strength": "moderate",
            "safe_conclusion": "Peak timing is modestly better for Model 2 q50, but it is not a magnitude claim.",
        },
        {
            "axis": "peak_magnitude_q50",
            "analysis": "primary paired Peak-MAPE reduction",
            "primary_evidence": (
                f"median reduction {fmt(full_value('Peak_MAPE_reduction', 'pooled_median'))}; "
                f"positive fraction {fmt(full_value('Peak_MAPE_reduction', 'pooled_positive_fraction'))}; "
                f"seed medians {full.loc['Peak_MAPE_reduction', 'seed_medians']}"
            ),
            "robustness": (
                f"after IQR outlier removal median {fmt(no_out_value('Peak_MAPE_reduction', 'pooled_median'))}"
            ),
            "claim_strength": "mixed",
            "safe_conclusion": "Peak magnitude improvement is not consistent for q50.",
        },
    ]

    top1 = quantile[quantile["stratum"].eq("basin_top1")]
    if not top1.empty:
        values = top1.set_index("predictor")
        rows.append(
            {
                "axis": "upper_quantile_high_flow",
                "analysis": "primary top-1% flow stratum",
                "primary_evidence": (
                    "underestimation fraction / median relative bias: "
                    f"Model 1 {fmt(values.loc['Model 1', 'median_underestimation_fraction'])}/"
                    f"{fmt(values.loc['Model 1', 'median_median_rel_bias_pct'])}%, "
                    f"q95 {fmt(values.loc['Model 2 q95', 'median_underestimation_fraction'])}/"
                    f"{fmt(values.loc['Model 2 q95', 'median_median_rel_bias_pct'])}%, "
                    f"q99 {fmt(values.loc['Model 2 q99', 'median_underestimation_fraction'])}/"
                    f"{fmt(values.loc['Model 2 q99', 'median_median_rel_bias_pct'])}%"
                ),
                "robustness": "same direction also appears at observed peak hour and stress positive-response events.",
                "claim_strength": "strong_for_upper_quantiles",
                "safe_conclusion": "Upper quantiles, not q50, are the evidence for reduced peak underestimation.",
            }
        )

    stress_pos = stress[stress["response_class"].eq("flood_response_ge25")]
    if not stress_pos.empty:
        values = stress_pos.set_index("predictor_label")
        rows.append(
            {
                "axis": "extreme_rain_stress",
                "analysis": "DRBC historical extreme-rain positive-response events",
                "primary_evidence": (
                    "flood_response_ge25 under-deficit: "
                    f"Model 1 {fmt(values.loc['Model 1', 'seed_mean_median_obs_peak_under_deficit_pct'])}%, "
                    f"q50 {fmt(values.loc['Model 2 q50', 'seed_mean_median_obs_peak_under_deficit_pct'])}%, "
                    f"q95 {fmt(values.loc['Model 2 q95', 'seed_mean_median_obs_peak_under_deficit_pct'])}%, "
                    f"q99 {fmt(values.loc['Model 2 q99', 'seed_mean_median_obs_peak_under_deficit_pct'])}%"
                ),
                "robustness": "historical stress test is basin-holdout but not temporally independent; use as supporting evidence.",
                "claim_strength": "supporting",
                "safe_conclusion": "Stress results support upper-quantile under-deficit reduction with false-positive tradeoff checks.",
            }
        )

    return pd.DataFrame(rows)


def ordered_predictors(frame: pd.DataFrame, column: str) -> list[str]:
    present = set(frame[column].dropna())
    return [value for value in PREDICTOR_ORDER if value in present]


def save_q50_seed_delta_chart(seed_table: pd.DataFrame, output_path: Path) -> None:
    metric_order = [
        "NSE",
        "KGE",
        "Signed FHV",
        "abs(FHV) reduction",
        "Peak timing reduction",
        "Peak MAPE reduction",
    ]
    metric_labels = {
        "NSE": "NSE",
        "KGE": "KGE",
        "Signed FHV": "Signed FHV",
        "abs(FHV) reduction": "abs(FHV) reduction",
        "Peak timing reduction": "Peak timing reduction",
        "Peak MAPE reduction": "Peak MAPE reduction",
    }
    fig, axes = plt.subplots(2, 3, figsize=(15.6, 8.2), squeeze=False)
    axes_flat = axes.ravel()
    for ax, metric in zip(axes_flat, metric_order, strict=True):
        sub = seed_table[seed_table["metric"].eq(metric)].sort_values("seed")
        colors = np.where(sub["median_delta"] >= 0, "#2563eb", "#dc2626")
        ax.bar(sub["seed"].astype(str), sub["median_delta"], color=colors, alpha=0.86)
        ax.axhline(0, color="#111827", linewidth=0.9)
        y_min = min(float(sub["median_delta"].min()), 0.0)
        y_max = max(float(sub["median_delta"].max()), 0.0)
        span = y_max - y_min
        pad = max(span * 0.22, 0.08)
        ax.set_ylim(y_min - pad, y_max + pad)
        ax.set_title(metric_labels[metric])
        ax.set_xlabel("Seed")
        ax.set_ylabel("Median paired delta")
        ax.grid(True, axis="y", color="#e5e7eb", linewidth=0.7)
    fig.suptitle("Primary q50 paired deltas by seed: positive is better except signed FHV")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def save_robustness_chart(robust: pd.DataFrame, output_path: Path) -> None:
    metric_order = [
        "delta_NSE",
        "delta_KGE",
        "delta_FHV",
        "abs_FHV_reduction",
        "Peak_Timing_reduction",
        "Peak_MAPE_reduction",
    ]
    fig, axes = plt.subplots(2, 3, figsize=(16.2, 8.4), squeeze=False)
    axes_flat = axes.ravel()
    for ax, metric in zip(axes_flat, metric_order, strict=True):
        sub = robust[robust["metric"].eq(metric)].copy()
        sub["scenario"] = pd.Categorical(
            sub["scenario"],
            categories=[scenario for scenario, _ in SCENARIOS],
            ordered=True,
        )
        sub = sub.sort_values("scenario")
        x = np.arange(len(sub))
        colors = np.where(sub["pooled_median"] >= 0, "#2563eb", "#dc2626")
        ax.bar(x, sub["pooled_median"], color=colors, alpha=0.86)
        ax.axhline(0, color="#111827", linewidth=0.9)
        y_min = min(float(sub["pooled_median"].min()), 0.0)
        y_max = max(float(sub["pooled_median"].max()), 0.0)
        span = y_max - y_min
        pad = max(span * 0.24, 0.08)
        ax.set_ylim(y_min - pad, y_max + pad)
        ax.set_xticks(x, [SCENARIO_SHORT_LABELS[str(s)] for s in sub["scenario"]])
        ax.set_title(str(sub["label"].iloc[0]))
        ax.set_ylabel("Pooled median delta")
        ax.grid(True, axis="y", color="#e5e7eb", linewidth=0.7)
    fig.suptitle("Outlier/area robustness: median q50 paired deltas")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def save_high_flow_quantile_chart(quantile: pd.DataFrame, output_path: Path) -> None:
    if quantile.empty:
        return
    strata = ["basin_top1", "observed_peak_hour"]
    stratum_labels = {"basin_top1": "Basin top 1%", "observed_peak_hour": "Observed peak hour"}
    fig, axes = plt.subplots(2, 2, figsize=(13.8, 8.4), squeeze=False)
    for col, stratum in enumerate(strata):
        sub = quantile[quantile["stratum"].eq(stratum)].copy()
        predictors = ordered_predictors(sub, "predictor")
        sub = sub.set_index("predictor").reindex(predictors).reset_index()
        colors = [PREDICTOR_COLORS[p] for p in predictors]

        ax = axes[0, col]
        ax.bar(predictors, sub["median_underestimation_fraction"], color=colors, alpha=0.86)
        ax.set_ylim(0, 1)
        ax.set_title(f"{stratum_labels[stratum]}: underestimation fraction")
        ax.set_ylabel("Fraction")
        ax.grid(True, axis="y", color="#e5e7eb", linewidth=0.7)
        ax.tick_params(axis="x", rotation=20)

        ax = axes[1, col]
        bias_values = sub["median_median_rel_bias_pct"]
        ax.bar(predictors, bias_values, color=colors, alpha=0.86)
        ax.axhline(0, color="#111827", linewidth=0.9)
        y_min = min(float(bias_values.min()), 0.0)
        y_max = max(float(bias_values.max()), 0.0)
        span = y_max - y_min
        pad = max(span * 0.16, 4.0)
        ax.set_ylim(y_min - pad, y_max + pad)
        ax.set_title(f"{stratum_labels[stratum]}: median relative bias")
        ax.set_ylabel("Relative bias (%)")
        ax.grid(True, axis="y", color="#e5e7eb", linewidth=0.7)
        ax.tick_params(axis="x", rotation=20)
    fig.suptitle("Upper quantiles reduce high-flow underestimation; q50 does not")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def save_stress_tradeoff_chart(stress: pd.DataFrame, output_path: Path) -> None:
    if stress.empty:
        return
    panels = [
        (
            "flood_response_ge25",
            "Positive response >=25yr proxy\nunder-deficit",
            "seed_mean_median_obs_peak_under_deficit_pct",
            "Under-deficit (%)",
        ),
        (
            "flood_response_ge2_to_lt25",
            "Positive response 2-25yr proxy\nunder-deficit",
            "seed_mean_median_obs_peak_under_deficit_pct",
            "Under-deficit (%)",
        ),
        (
            "low_response_below_q99",
            "Negative control low response\npredicted peak / ARI100",
            "seed_mean_median_pred_window_peak_to_flood_ari100",
            "Predicted peak / ARI100",
        ),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.2), squeeze=False)
    for ax, (response_class, title, value_col, ylabel) in zip(axes.ravel(), panels, strict=True):
        sub = stress[stress["response_class"].eq(response_class)].copy()
        predictors = ordered_predictors(sub, "predictor_label")
        sub = sub.set_index("predictor_label").reindex(predictors).reset_index()
        colors = [PREDICTOR_COLORS[p] for p in predictors]
        values = sub[value_col]
        ax.bar(predictors, values, color=colors, alpha=0.86)
        if value_col.endswith("ari100"):
            ax.axhline(1, color="#dc2626", linestyle="--", linewidth=1.0)
        y_max = float(values.max()) if len(values) else 1.0
        ax.set_ylim(0, y_max * 1.16 if y_max > 0 else 1.0)
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.grid(True, axis="y", color="#e5e7eb", linewidth=0.7)
        ax.tick_params(axis="x", rotation=20)
    fig.suptitle("Extreme-rain stress: upper quantiles reduce deficits but raise false-positive exposure")
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def build_conclusion_figures(
    figures_dir: Path,
    seed_table: pd.DataFrame,
    robust: pd.DataFrame,
    quantile: pd.DataFrame,
    stress: pd.DataFrame,
) -> dict[str, Path]:
    figures_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "q50_seed_delta": figures_dir / "overall_conclusion_q50_seed_delta.png",
        "q50_robustness": figures_dir / "overall_conclusion_q50_robustness.png",
        "high_flow_quantiles": figures_dir / "overall_conclusion_high_flow_quantiles.png",
        "stress_tradeoff": figures_dir / "overall_conclusion_stress_tradeoff.png",
    }
    save_q50_seed_delta_chart(seed_table, paths["q50_seed_delta"])
    save_robustness_chart(robust, paths["q50_robustness"])
    save_high_flow_quantile_chart(quantile, paths["high_flow_quantiles"])
    save_stress_tradeoff_chart(stress, paths["stress_tradeoff"])
    manifest = pd.DataFrame(
        [
            {
                "figure_key": key,
                "path": str(path),
                "description": {
                    "q50_seed_delta": "Seed-level primary q50 paired deltas.",
                    "q50_robustness": "Pooled median q50 deltas under outlier and area robustness filters.",
                    "high_flow_quantiles": "Primary high-flow underestimation and relative bias for Model 1/q50/q95/q99.",
                    "stress_tradeoff": "Extreme-rain positive response and negative-control tradeoff summary.",
                }[key],
            }
            for key, path in paths.items()
        ]
    )
    manifest.to_csv(figures_dir / "overall_conclusion_figure_manifest.csv", index=False)
    return paths


def markdown_image(path: Path, report_path: Path, alt_text: str) -> str:
    rel = os.path.relpath(path, report_path.parent)
    return f"![{alt_text}]({Path(rel).as_posix()})"


def write_report(
    path: Path,
    model_snapshot: pd.DataFrame,
    seed_table: pd.DataFrame,
    robust: pd.DataFrame,
    quantile: pd.DataFrame,
    stress: pd.DataFrame,
    claims: pd.DataFrame,
    figure_paths: dict[str, Path],
) -> None:
    full = robust[robust["scenario"].eq("full")].set_index("metric")
    no_out = robust[robust["scenario"].eq("exclude_iqr_outliers")].set_index("metric")
    lines = [
        "# Subset300 overall performance conclusion strategy",
        "",
        "## 결론 프레임",
        "",
        "전체 성능은 하나의 평균 점수로 결론내리면 안 된다. 이 실험의 결론 단위는 "
        "`paired seed x basin`이고, 전체 성능은 q50 central-skill guardrail, flood/peak guardrail, "
        "upper-quantile flood evidence, outlier robustness를 분리해서 읽는다.",
        "",
        "가장 안전한 headline은 다음과 같다.",
        "",
        "> Model 2 q50 preserves or modestly improves central NSE skill, but it does not by itself improve high-flow magnitude. "
        "The flood-underestimation improvement comes from Model 2 upper quantiles, especially q95/q99, with a false-positive tradeoff.",
        "",
        "## Primary q50 paired result",
        "",
        markdown_image(figure_paths["q50_seed_delta"], path, "Primary q50 paired seed delta chart"),
        "",
        "이 차트는 `q50` 기준 Model 2가 어떤 지표에서 seed별로 일관적인지 보여준다. "
        "NSE와 peak timing은 세 seed에서 대체로 양수지만, KGE와 magnitude 계열 지표는 seed별로 엇갈린다. "
        "특히 signed FHV는 음수 방향으로 이동하므로 q50 flood-volume 개선 주장으로 쓰면 안 된다. "
        "정확한 수치는 아래 seed별 paired delta 표에서 확인한다.",
        "",
        model_snapshot.to_markdown(index=False, floatfmt=".3f"),
        "",
        "Seed별 paired delta는 아래처럼 읽는다. Positive-better 지표에서 양수는 Model 2 q50 개선이다.",
        "",
        seed_table.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Robustness after outlier handling",
        "",
        markdown_image(figure_paths["q50_robustness"], path, "Outlier and area robustness chart"),
        "",
        "이 차트는 full sample에서 보이던 q50 delta가 outlier 제거와 small-basin filter 뒤 어떻게 바뀌는지 보여준다. "
        "NSE 개선은 남아도 작아지고, peak timing은 가장 안정적으로 유지되며, FHV/Peak-MAPE는 개선 주장으로 보기 어렵다. "
        "정확한 median delta와 positive fraction은 아래 robustness 표에서 확인한다.",
        "",
        robust[
            robust["metric"].isin(
                [
                    "delta_NSE",
                    "delta_KGE",
                    "delta_FHV",
                    "abs_FHV_reduction",
                    "Peak_Timing_reduction",
                    "Peak_MAPE_reduction",
                ]
            )
        ][
            [
                "scenario_label",
                "label",
                "pooled_n",
                "pooled_median",
                "pooled_q25",
                "pooled_q75",
                "pooled_positive_fraction",
                "favorable_seed_count",
            ]
        ].to_markdown(index=False, floatfmt=".3f"),
        "",
        "Outlier 제거 후에는 NSE 개선 크기와 seed 일관성이 크게 약해진다. "
        "따라서 NSE는 `q50이 central skill을 망가뜨리지 않았다`는 guardrail로 쓰고, "
        "강한 개선 주장은 피하는 편이 안전하다. Peak timing은 outlier 제거 후에도 가장 일관적으로 남는다. "
        "FHV/Peak-MAPE는 q50 개선 주장으로 쓰기 어렵다.",
        "",
        "## Upper-quantile high-flow evidence",
        "",
        markdown_image(figure_paths["high_flow_quantiles"], path, "High-flow quantile underestimation chart"),
        "",
        "이 차트가 flood-specific headline의 핵심 근거다. q50은 high-flow와 observed peak hour에서 Model 1보다 더 낮게 잡지만, "
        "q95/q99는 underestimation fraction과 median relative bias를 완화한다. "
        "정확한 underestimation fraction과 relative bias는 아래 표에 둔다.",
        "",
        quantile.to_markdown(index=False, floatfmt=".3f") if not quantile.empty else "No quantile high-flow table found.",
        "",
        "## Extreme-rain stress evidence",
        "",
        markdown_image(figure_paths["stress_tradeoff"], path, "Extreme-rain stress tradeoff chart"),
        "",
        "이 차트는 historical stress test를 보조 근거로 읽는 방법을 보여준다. Positive-response event에서는 q95/q99가 under-deficit을 줄이지만, "
        "negative-control low-response event에서는 q99의 predicted peak가 커져 false-positive tradeoff가 생긴다. "
        "정확한 event count와 stress metric 값은 아래 표에서 확인한다.",
        "",
        stress.to_markdown(index=False, floatfmt=".3f") if not stress.empty else "No stress table found.",
        "",
        "## Claim table",
        "",
        claims.to_markdown(index=False),
        "",
        "## 논문 결론 문장 후보",
        "",
        "Primary overall metric만 놓고는 Model 2가 모든 면에서 Model 1을 이긴다고 말하면 안 된다. "
        f"NSE는 full paired median delta가 {fmt(float(full.loc['delta_NSE', 'pooled_median']))}이지만 "
        f"outlier 제거 후에는 {fmt(float(no_out.loc['delta_NSE', 'pooled_median']))}로 작아지므로, "
        "central hydrograph skill을 망가뜨리지는 않았지만 강한 개선 주장은 약해진다. "
        f"반면 signed FHV median shift는 {fmt(float(full.loc['delta_FHV', 'pooled_median']))}라서 "
        "q50은 high-flow volume을 더 낮게 잡는 경향이 있다. 따라서 flood 개선의 근거는 q50이 아니라 "
        "q95/q99 upper quantile 분석에서 제시해야 한다.",
        "",
        "## Recommended table order",
        "",
        "1. Primary q50 paired overall table: NSE/KGE/FHV/Peak timing/Peak-MAPE seed별 delta.",
        "2. Robustness note: outlier 제거와 area>=50 filter 후에도 central-skill 결론이 유지되는지.",
        "3. High-flow top 1%/observed peak table: Model 1, q50, q95, q99의 underestimation fraction과 relative bias.",
        "4. Extreme-rain stress table: positive-response와 negative-control을 같이 보여 false-positive tradeoff를 명시.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    main_dir = resolve(args.main_comparison_dir)
    output_dir = resolve(args.output_dir)
    tables_dir = output_dir / "tables"
    figures_dir = output_dir / "figures" / CLAIM_FIGURE_DIRNAME
    report_dir = output_dir / "report"
    metadata_dir = output_dir / "metadata"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    epoch_summary, delta_summary, basin_deltas = read_primary(main_dir)
    outlier_context = read_outlier_context(main_dir)
    robust = build_robust_delta_summary(basin_deltas, outlier_context)
    seed_table = build_seed_median_table(delta_summary)
    quantile = read_quantile_high_flow(resolve(args.quantile_dir))
    stress = read_stress_summary(resolve(args.stress_dir))
    snapshot = model_seed_snapshot(epoch_summary)
    claims = build_claim_table(robust, quantile, stress)
    figure_paths = build_conclusion_figures(figures_dir, seed_table, robust, quantile, stress)

    snapshot_path = tables_dir / "overall_performance_model_seed_snapshot.csv"
    seed_path = tables_dir / "overall_performance_seed_delta_summary_long.csv"
    robust_path = tables_dir / "overall_performance_robust_delta_summary.csv"
    quantile_path = tables_dir / "overall_performance_high_flow_quantile_summary.csv"
    stress_path = tables_dir / "overall_performance_extreme_rain_stress_summary.csv"
    claims_path = tables_dir / "overall_performance_conclusion_claims.csv"
    report_path = report_dir / "overall_performance_conclusion_strategy.md"

    snapshot.to_csv(snapshot_path, index=False)
    seed_table.to_csv(seed_path, index=False)
    robust.to_csv(robust_path, index=False)
    quantile.to_csv(quantile_path, index=False)
    stress.to_csv(stress_path, index=False)
    claims.to_csv(claims_path, index=False)
    write_report(report_path, snapshot, seed_table, robust, quantile, stress, claims, figure_paths)

    metadata = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "script": str(Path(__file__).resolve()),
        "inputs": {
            "main_comparison_dir": str(main_dir),
            "quantile_dir": str(resolve(args.quantile_dir)),
            "stress_dir": str(resolve(args.stress_dir)),
        },
        "outputs": {
            "snapshot": str(snapshot_path),
            "seed_delta_summary_long": str(seed_path),
            "robust_delta_summary": str(robust_path),
            "high_flow_quantile_summary": str(quantile_path),
            "extreme_rain_stress_summary": str(stress_path),
            "conclusion_claims": str(claims_path),
            "figures": {key: str(value) for key, value in figure_paths.items()},
            "figure_manifest": str(figures_dir / "overall_conclusion_figure_manifest.csv"),
            "report": str(report_path),
        },
    }
    metadata_path = metadata_dir / "overall_performance_conclusion_strategy_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Wrote report to {report_path}")
    print(f"Wrote claim table to {claims_path}")


if __name__ == "__main__":
    main()
