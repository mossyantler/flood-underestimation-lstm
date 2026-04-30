#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
# ]
# ///

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_INPUT_DIR = Path("output/model_analysis/extreme_rain/primary/inference")
DEFAULT_COHORT_CSV = Path("output/model_analysis/extreme_rain/primary/exposure/drbc_historical_stress_cohort.csv")
DEFAULT_OUTPUT_DIR = Path("output/model_analysis/extreme_rain/primary/analysis")

PRIMARY_EPOCHS = {
    111: (25, 5),
    222: (10, 10),
    444: (15, 10),
}
PREDICTORS = [
    ("model1", "Model 1"),
    ("q50", "Model 2 q50"),
    ("q90", "Model 2 q90"),
    ("q95", "Model 2 q95"),
    ("q99", "Model 2 q99"),
]
MODEL2_PREDICTORS = ["q50", "q90", "q95", "q99"]

SUMMARY_VALUE_COLUMNS = [
    "obs_peak_rel_error_pct",
    "obs_peak_under_deficit_pct",
    "window_peak_rel_error_pct",
    "abs_peak_timing_error_hours",
    "event_rmse",
    "event_nrmse_pct",
    "event_mae",
    "event_nmae_pct",
    "threshold_exceedance_recall",
    "top_flow_hit_rate",
    "pred_window_peak_to_flood_ari25",
    "pred_window_peak_to_flood_ari50",
    "pred_window_peak_to_flood_ari100",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze subset300 Model 1/2 predictions on DRBC historical extreme-rain stress events."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--cohort-csv", type=Path, default=DEFAULT_COHORT_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seeds", type=int, nargs="+", default=sorted(PRIMARY_EPOCHS))
    parser.add_argument(
        "--epoch-labels",
        nargs="+",
        default=None,
        help="Optional manifest epoch_label filter, for example primary or epoch005 epoch010.",
    )
    parser.add_argument("--limit-events", type=int, default=None)
    return parser.parse_args()


def normalize_gauge_id(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(8)


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer, np.floating)):
        if pd.isna(value):
            return None
        return value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if pd.isna(value):
        return None
    return value


def numeric_scalar(value: Any) -> float:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return float(numeric) if pd.notna(numeric) else math.nan


def read_cohort(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing stress cohort CSV: {path}")
    cohort = pd.read_csv(
        path,
        dtype={"gauge_id": str},
        parse_dates=[
            "rain_start",
            "rain_peak",
            "rain_end",
            "response_window_start",
            "response_window_end",
            "observed_response_peak_time",
        ],
    )
    cohort["gauge_id"] = cohort["gauge_id"].map(normalize_gauge_id)
    if "stress_group" not in cohort.columns:
        cohort["stress_group"] = np.where(
            cohort["response_class"].isin(["flood_response_ge25", "flood_response_ge2_to_lt25"]),
            "positive_response",
            "negative_control",
        )
    return cohort.sort_values(["gauge_id", "rain_start", "event_id"]).reset_index(drop=True)


def read_inference_manifest(input_dir: Path, seeds: list[int], epoch_labels: list[str] | None) -> pd.DataFrame:
    path = input_dir / "inference_manifest.csv"
    if path.exists():
        manifest = pd.read_csv(path)
        if "epoch_label" not in manifest.columns:
            manifest["epoch_label"] = "primary"
        manifest = manifest[manifest["seed"].isin(seeds)].copy()
        if epoch_labels is not None:
            manifest = manifest[manifest["epoch_label"].isin(epoch_labels)].copy()
        if manifest.empty:
            raise ValueError(f"No inference manifest rows selected from {path}")
        return manifest.sort_values(["seed", "model1_epoch", "model2_epoch", "epoch_label"]).reset_index(drop=True)

    rows = []
    for seed in seeds:
        model1_epoch, model2_epoch = PRIMARY_EPOCHS[seed]
        rows.append(
            {
                "seed": seed,
                "epoch_label": "primary",
                "model1_epoch": model1_epoch,
                "model2_epoch": model2_epoch,
                "required_series_csv": str(input_dir / "required_series" / f"seed{seed}" / "primary_required_series.csv"),
            }
        )
    return pd.DataFrame(rows)


def read_required_series(path: Path, seed: int, epoch_label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing stress-test required-series file: {path}")
    df = pd.read_csv(path, dtype={"basin": str}, parse_dates=["datetime"])
    df["basin"] = df["basin"].map(normalize_gauge_id)
    for col in ["obs", "model1", "q50", "q90", "q95", "q99"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["seed"] = seed
    df["epoch_label"] = epoch_label
    return df.sort_values(["basin", "datetime"]).reset_index(drop=True)


def rel_error(prediction: float, observation: float) -> float:
    if not np.isfinite(observation) or observation <= 0:
        return math.nan
    return float((prediction - observation) / observation * 100.0)


def under_deficit(prediction: float, observation: float) -> float:
    if not np.isfinite(observation) or observation <= 0:
        return math.nan
    return float(max(observation - prediction, 0.0) / observation * 100.0)


def hour_delta(left: pd.Timestamp, right: pd.Timestamp) -> float:
    return float((left - right).total_seconds() / 3600.0)


def event_threshold_mask(frame: pd.DataFrame, threshold: float) -> pd.Series:
    if np.isfinite(threshold) and threshold > 0:
        mask = frame["obs"] >= threshold
        if mask.any():
            return mask
    cutoff = frame["obs"].quantile(0.9)
    return frame["obs"] >= cutoff


def summarize_event_prediction(event: pd.Series, frame: pd.DataFrame) -> dict[str, Any]:
    obs_peak_idx = frame["obs"].idxmax()
    obs_peak = float(frame.loc[obs_peak_idx, "obs"])
    obs_peak_time = pd.Timestamp(frame.loc[obs_peak_idx, "datetime"])
    flood_ari2 = numeric_scalar(event.get("flood_ari2"))
    threshold = flood_ari2 if np.isfinite(flood_ari2) and flood_ari2 > 0 else numeric_scalar(event.get("streamflow_q99_threshold"))
    top_mask = event_threshold_mask(frame, threshold)
    row: dict[str, Any] = {
        "event_window_n_hours": int(len(frame)),
        "event_top_flow_n_hours": int(top_mask.sum()),
        "observed_peak_from_series": obs_peak,
        "observed_peak_time_from_series": obs_peak_time,
        "stress_threshold_value": threshold,
    }

    for col, _label in PREDICTORS:
        pred_at_obs_peak = float(frame.loc[obs_peak_idx, col])
        pred_peak_idx = frame[col].idxmax()
        pred_peak = float(frame.loc[pred_peak_idx, col])
        pred_peak_time = pd.Timestamp(frame.loc[pred_peak_idx, "datetime"])
        error = frame[col] - frame["obs"]
        top_frame = frame.loc[top_mask]
        threshold_recall = float((top_frame[col] >= threshold).mean()) if len(top_frame) else math.nan
        top_hit_rate = float((top_frame[col] >= top_frame["obs"]).mean()) if len(top_frame) else math.nan

        row[f"{col}_at_observed_peak"] = pred_at_obs_peak
        row[f"{col}_window_peak"] = pred_peak
        row[f"{col}_window_peak_time"] = pred_peak_time
        row[f"{col}_obs_peak_rel_error_pct"] = rel_error(pred_at_obs_peak, obs_peak)
        row[f"{col}_obs_peak_abs_error"] = float(abs(pred_at_obs_peak - obs_peak))
        row[f"{col}_obs_peak_underestimated"] = bool(pred_at_obs_peak < obs_peak)
        row[f"{col}_obs_peak_under_deficit_pct"] = under_deficit(pred_at_obs_peak, obs_peak)
        row[f"{col}_window_peak_rel_error_pct"] = rel_error(pred_peak, obs_peak)
        row[f"{col}_signed_peak_timing_error_hours"] = hour_delta(pred_peak_time, obs_peak_time)
        row[f"{col}_abs_peak_timing_error_hours"] = abs(row[f"{col}_signed_peak_timing_error_hours"])
        event_rmse = float(np.sqrt(np.nanmean(np.square(error))))
        event_mae = float(np.nanmean(np.abs(error)))
        row[f"{col}_event_rmse"] = event_rmse
        row[f"{col}_event_mae"] = event_mae
        row[f"{col}_event_nrmse_pct"] = rel_error(event_rmse, obs_peak) + 100.0
        row[f"{col}_event_nmae_pct"] = rel_error(event_mae, obs_peak) + 100.0
        row[f"{col}_threshold_exceedance_recall"] = threshold_recall
        row[f"{col}_top_flow_hit_rate"] = top_hit_rate
        for period in [25, 50, 100]:
            flood_level = numeric_scalar(event.get(f"flood_ari{period}"))
            ratio = pred_peak / flood_level if np.isfinite(flood_level) and flood_level > 0 else math.nan
            row[f"{col}_pred_window_peak_to_flood_ari{period}"] = ratio
            row[f"{col}_pred_crosses_flood_ari{period}"] = bool(ratio >= 1.0) if np.isfinite(ratio) else False

    return row


def event_rows_for_seed(series: pd.DataFrame, cohort: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    groups = {basin: group.reset_index(drop=True) for basin, group in series.groupby("basin", sort=False)}
    metadata_cols = [
        "event_id",
        "storm_group_id",
        "gauge_id",
        "split",
        "rain_cohort",
        "stress_group",
        "response_class",
        "rain_start",
        "rain_peak",
        "rain_end",
        "response_window_start",
        "response_window_end",
        "observed_response_peak",
        "observed_response_peak_time",
        "water_year",
        "peak_month",
        "max_prec_ari25_ratio",
        "max_prec_ari50_ratio",
        "max_prec_ari100_ratio",
        "dominant_duration_for_ari25h",
        "dominant_duration_for_ari50h",
        "dominant_duration_for_ari100h",
        "streamflow_q99_threshold",
        "obs_peak_to_flood_ari2",
        "obs_peak_to_flood_ari25",
        "obs_peak_to_flood_ari50",
        "obs_peak_to_flood_ari100",
        "flood_ari2",
        "flood_ari25",
        "flood_ari50",
        "flood_ari100",
        "response_lag_hours",
        "temporal_relation",
        "return_period_confidence_flag",
        "precip_reference_flag",
    ]
    metadata_cols = [col for col in metadata_cols if col in cohort.columns]

    for _, event in cohort.iterrows():
        basin = event["gauge_id"]
        basin_series = groups.get(basin)
        if basin_series is None:
            missing_rows.append(
                {
                    "seed": int(series["seed"].iloc[0]),
                    "epoch_label": str(series["epoch_label"].iloc[0]) if "epoch_label" in series else "primary",
                    "model1_epoch": int(series["model1_epoch"].iloc[0]),
                    "model2_epoch": int(series["model2_epoch"].iloc[0]),
                    "event_id": event["event_id"],
                    "gauge_id": basin,
                    "missing_reason": "no_basin_series",
                }
            )
            continue
        frame = basin_series[
            (basin_series["datetime"] >= event["response_window_start"])
            & (basin_series["datetime"] <= event["response_window_end"])
        ].copy()
        if frame.empty:
            missing_rows.append(
                {
                    "seed": int(series["seed"].iloc[0]),
                    "epoch_label": str(series["epoch_label"].iloc[0]) if "epoch_label" in series else "primary",
                    "model1_epoch": int(series["model1_epoch"].iloc[0]),
                    "model2_epoch": int(series["model2_epoch"].iloc[0]),
                    "event_id": event["event_id"],
                    "gauge_id": basin,
                    "missing_reason": "no_rows_in_response_window",
                }
            )
            continue
        row = {col: event[col] for col in metadata_cols}
        row.update(
            {
                "seed": int(series["seed"].iloc[0]),
                "epoch_label": str(series["epoch_label"].iloc[0]) if "epoch_label" in series else "primary",
                "comparison": "extreme_rain_stress",
                "model1_epoch": int(series["model1_epoch"].iloc[0]),
                "model2_epoch": int(series["model2_epoch"].iloc[0]),
            }
        )
        row.update(summarize_event_prediction(event, frame))
        rows.append(row)
    return pd.DataFrame(rows), pd.DataFrame(missing_rows)


def wide_to_long(events: pd.DataFrame) -> pd.DataFrame:
    base_cols = [
        "comparison",
        "seed",
        "epoch_label",
        "model1_epoch",
        "model2_epoch",
        "gauge_id",
        "event_id",
        "storm_group_id",
        "split",
        "rain_cohort",
        "stress_group",
        "response_class",
        "rain_start",
        "rain_peak",
        "rain_end",
        "response_window_start",
        "response_window_end",
        "observed_response_peak",
        "observed_response_peak_time",
        "water_year",
        "peak_month",
        "max_prec_ari25_ratio",
        "max_prec_ari50_ratio",
        "max_prec_ari100_ratio",
        "obs_peak_to_flood_ari2",
        "obs_peak_to_flood_ari25",
        "obs_peak_to_flood_ari50",
        "obs_peak_to_flood_ari100",
        "temporal_relation",
        "return_period_confidence_flag",
        "precip_reference_flag",
        "event_window_n_hours",
        "event_top_flow_n_hours",
        "observed_peak_from_series",
        "observed_peak_time_from_series",
        "stress_threshold_value",
    ]
    base_cols = [col for col in base_cols if col in events.columns]
    metric_suffixes = [
        "at_observed_peak",
        "window_peak",
        "window_peak_time",
        "obs_peak_rel_error_pct",
        "obs_peak_abs_error",
        "obs_peak_underestimated",
        "obs_peak_under_deficit_pct",
        "window_peak_rel_error_pct",
        "signed_peak_timing_error_hours",
        "abs_peak_timing_error_hours",
        "event_rmse",
        "event_nrmse_pct",
        "event_mae",
        "event_nmae_pct",
        "threshold_exceedance_recall",
        "top_flow_hit_rate",
        "pred_window_peak_to_flood_ari25",
        "pred_crosses_flood_ari25",
        "pred_window_peak_to_flood_ari50",
        "pred_crosses_flood_ari50",
        "pred_window_peak_to_flood_ari100",
        "pred_crosses_flood_ari100",
    ]
    frames = []
    for predictor, label in PREDICTORS:
        rename = {f"{predictor}_{suffix}": suffix for suffix in metric_suffixes}
        cols = base_cols + [col for col in rename if col in events.columns]
        frame = events[cols].rename(columns=rename).copy()
        frame["predictor"] = predictor
        frame["predictor_label"] = label
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def summarize_long(long_df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows = []
    for keys, group in long_df.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_cols, keys, strict=True))
        row["n_events"] = int(group["event_id"].nunique())
        row["n_basins"] = int(group["gauge_id"].nunique())
        row["median_observed_peak"] = float(group["observed_peak_from_series"].median())
        row["underestimation_fraction_at_observed_peak"] = float(group["obs_peak_underestimated"].mean())
        for col in SUMMARY_VALUE_COLUMNS:
            values = pd.to_numeric(group[col], errors="coerce").dropna()
            row[f"mean_{col}"] = float(values.mean()) if not values.empty else math.nan
            row[f"median_{col}"] = float(values.median()) if not values.empty else math.nan
        for period in [25, 50, 100]:
            col = f"pred_crosses_flood_ari{period}"
            if col in group:
                row[f"fraction_{col}"] = float(group[col].astype(bool).mean())
        rows.append(row)
    return pd.DataFrame(rows).sort_values(group_cols)


def aggregate_seed_summaries(summary: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    value_cols = [
        "underestimation_fraction_at_observed_peak",
        "median_obs_peak_rel_error_pct",
        "median_obs_peak_under_deficit_pct",
        "median_window_peak_rel_error_pct",
        "median_abs_peak_timing_error_hours",
        "median_event_nrmse_pct",
        "mean_threshold_exceedance_recall",
        "mean_top_flow_hit_rate",
        "median_pred_window_peak_to_flood_ari25",
        "median_pred_window_peak_to_flood_ari50",
        "median_pred_window_peak_to_flood_ari100",
        "fraction_pred_crosses_flood_ari25",
        "fraction_pred_crosses_flood_ari50",
        "fraction_pred_crosses_flood_ari100",
    ]
    rows = []
    for keys, group in summary.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_cols, keys, strict=True))
        row["n_seed_epoch_summaries"] = int(len(group))
        row["n_seed_summaries"] = int(group["seed"].nunique()) if "seed" in group else int(len(group))
        row["n_epoch_pairs"] = (
            int(group[["model1_epoch", "model2_epoch"]].drop_duplicates().shape[0])
            if {"model1_epoch", "model2_epoch"}.issubset(group.columns)
            else 1
        )
        row["mean_n_events"] = float(group["n_events"].mean())
        row["min_n_events"] = int(group["n_events"].min())
        for col in value_cols:
            if col not in group:
                continue
            values = pd.to_numeric(group[col], errors="coerce").dropna()
            row[f"seed_mean_{col}"] = float(values.mean()) if not values.empty else math.nan
            row[f"seed_sd_{col}"] = float(values.std(ddof=1)) if len(values) > 1 else math.nan
        rows.append(row)
    return pd.DataFrame(rows).sort_values(group_cols)


def paired_delta(long_df: pd.DataFrame, strat_col: str) -> pd.DataFrame:
    metric_cols = [
        "obs_peak_underestimated",
        "obs_peak_under_deficit_pct",
        "obs_peak_abs_error",
        "event_nrmse_pct",
        "abs_peak_timing_error_hours",
        "threshold_exceedance_recall",
        "top_flow_hit_rate",
        "pred_window_peak_to_flood_ari25",
        "pred_window_peak_to_flood_ari50",
        "pred_window_peak_to_flood_ari100",
    ]
    index_cols = ["seed", "epoch_label", "model1_epoch", "model2_epoch", "gauge_id", "event_id", strat_col]
    wide = long_df[index_cols + ["predictor", *metric_cols]].pivot_table(
        index=index_cols,
        columns="predictor",
        values=metric_cols,
        aggfunc="first",
    )
    rows = []
    for predictor in MODEL2_PREDICTORS:
        required = [("obs_peak_under_deficit_pct", "model1"), ("obs_peak_under_deficit_pct", predictor)]
        if any(col not in wide.columns for col in required):
            continue
        frame = wide.dropna(subset=required).copy()
        frame["under_deficit_reduction_pct"] = (
            frame[("obs_peak_under_deficit_pct", "model1")]
            - frame[("obs_peak_under_deficit_pct", predictor)]
        )
        frame["underestimation_fraction_delta"] = (
            frame[("obs_peak_underestimated", predictor)].astype(float)
            - frame[("obs_peak_underestimated", "model1")].astype(float)
        )
        frame["event_nrmse_pct_delta"] = frame[("event_nrmse_pct", predictor)] - frame[("event_nrmse_pct", "model1")]
        frame["threshold_recall_delta"] = (
            frame[("threshold_exceedance_recall", predictor)] - frame[("threshold_exceedance_recall", "model1")]
        )
        for period in [25, 50, 100]:
            frame[f"pred_peak_to_flood_ari{period}_delta"] = (
                frame[(f"pred_window_peak_to_flood_ari{period}", predictor)]
                - frame[(f"pred_window_peak_to_flood_ari{period}", "model1")]
            )
        for keys, group in frame.groupby(["seed", "epoch_label", "model1_epoch", "model2_epoch", strat_col], dropna=False):
            seed, epoch_label, model1_epoch, model2_epoch, stratum = keys
            row = {
                "stratification": strat_col,
                "stratum": stratum,
                "seed": int(seed),
                "epoch_label": epoch_label,
                "model1_epoch": int(model1_epoch),
                "model2_epoch": int(model2_epoch),
                "predictor": predictor,
                "predictor_label": dict(PREDICTORS)[predictor],
                "n_events": int(len(group)),
                "n_basins": int(group.reset_index()["gauge_id"].nunique()),
                "median_paired_under_deficit_reduction_pct": float(group["under_deficit_reduction_pct"].median()),
                "mean_underestimation_fraction_delta": float(group["underestimation_fraction_delta"].mean()),
                "median_event_nrmse_pct_delta": float(group["event_nrmse_pct_delta"].median()),
                "mean_threshold_recall_delta": float(group["threshold_recall_delta"].mean()),
            }
            for period in [25, 50, 100]:
                row[f"median_pred_peak_to_flood_ari{period}_delta"] = float(
                    group[f"pred_peak_to_flood_ari{period}_delta"].median()
                )
            rows.append(row)
    return pd.DataFrame(rows).sort_values(["stratification", "stratum", "seed", "predictor"])


def aggregate_delta(seed_delta: pd.DataFrame, extra_group_cols: list[str] | None = None) -> pd.DataFrame:
    group_cols = ["stratification", "stratum", *(extra_group_cols or []), "predictor", "predictor_label"]
    value_cols = [
        "median_paired_under_deficit_reduction_pct",
        "mean_underestimation_fraction_delta",
        "median_event_nrmse_pct_delta",
        "mean_threshold_recall_delta",
        "median_pred_peak_to_flood_ari25_delta",
        "median_pred_peak_to_flood_ari50_delta",
        "median_pred_peak_to_flood_ari100_delta",
    ]
    rows = []
    for keys, group in seed_delta.groupby(group_cols, dropna=False):
        row = dict(zip(group_cols, keys, strict=True))
        row["n_seed_epoch_summaries"] = int(len(group))
        row["n_seed_summaries"] = int(group["seed"].nunique())
        row["n_epoch_pairs"] = (
            int(group[["model1_epoch", "model2_epoch"]].drop_duplicates().shape[0])
            if {"model1_epoch", "model2_epoch"}.issubset(group.columns)
            else 1
        )
        row["mean_n_events"] = float(group["n_events"].mean())
        for col in value_cols:
            values = pd.to_numeric(group[col], errors="coerce").dropna()
            row[f"seed_mean_{col}"] = float(values.mean()) if not values.empty else math.nan
            row[f"seed_sd_{col}"] = float(values.std(ddof=1)) if len(values) > 1 else math.nan
        rows.append(row)
    return pd.DataFrame(rows).sort_values(group_cols)


def table(df: pd.DataFrame, cols: list[str]) -> str:
    if df.empty:
        return "_No rows._"
    rendered = df[[col for col in cols if col in df.columns]].copy()
    for col in rendered.columns:
        if pd.api.types.is_float_dtype(rendered[col]):
            rendered[col] = rendered[col].map(lambda value: "" if pd.isna(value) else f"{value:.3f}")
        else:
            rendered[col] = rendered[col].astype(str)
    widths = {col: max(len(str(col)), *(len(value) for value in rendered[col].astype(str))) for col in rendered.columns}
    header = "| " + " | ".join(str(col).ljust(widths[col]) for col in rendered.columns) + " |"
    separator = "| " + " | ".join("-" * widths[col] for col in rendered.columns) + " |"
    rows = [
        "| " + " | ".join(str(row[col]).ljust(widths[col]) for col in rendered.columns) + " |"
        for _, row in rendered.iterrows()
    ]
    return "\n".join([header, separator, *rows])


def write_report(path: Path, event_wide: pd.DataFrame, cohort_aggregate: pd.DataFrame, delta_aggregate: pd.DataFrame) -> None:
    unique_events = event_wide.drop_duplicates(["gauge_id", "event_id"])
    lines = [
        "# Subset300 Extreme-Rain Stress Test",
        "",
        "This report was generated by `scripts/official/analyze_subset300_extreme_rain_stress_test.py`.",
        "",
        "## Scope",
        "",
        f"- Unique stress events: {unique_events['event_id'].nunique()} across {unique_events['gauge_id'].nunique()} DRBC basins.",
        f"- Paired seeds: {', '.join(str(seed) for seed in sorted(event_wide['seed'].unique()))}.",
        f"- Epoch labels: {', '.join(str(label) for label in sorted(event_wide['epoch_label'].astype(str).unique()))}.",
        f"- Rain cohorts: {unique_events['rain_cohort'].value_counts().to_dict()}.",
        f"- Response classes: {unique_events['response_class'].value_counts().to_dict()}.",
        "- This is a basin-holdout historical stress test, not the primary temporally isolated test.",
        "- `prec_ari*` and `flood_ari*` are CAMELSH hourly annual-maxima proxy references.",
        "",
        "## Cohort Aggregate",
        "",
        table(
            cohort_aggregate,
            [
                "stress_group",
                "response_class",
                "predictor_label",
                "n_seed_epoch_summaries",
                "n_seed_summaries",
                "n_epoch_pairs",
                "mean_n_events",
                "seed_mean_underestimation_fraction_at_observed_peak",
                "seed_mean_median_obs_peak_under_deficit_pct",
                "seed_mean_mean_threshold_exceedance_recall",
                "seed_mean_median_pred_window_peak_to_flood_ari100",
            ],
        ),
        "",
        "## Paired Delta vs Model 1",
        "",
        "Positive under-deficit reduction and threshold-recall delta mean the Model 2 output improved relative to Model 1.",
        "",
        table(
            delta_aggregate,
            [
                "stratum",
                "predictor_label",
                "n_seed_epoch_summaries",
                "n_seed_summaries",
                "n_epoch_pairs",
                "mean_n_events",
                "seed_mean_median_paired_under_deficit_reduction_pct",
                "seed_mean_mean_underestimation_fraction_delta",
                "seed_mean_mean_threshold_recall_delta",
                "seed_mean_median_pred_peak_to_flood_ari100_delta",
            ],
        ),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    cohort = read_cohort(args.cohort_csv)
    if args.limit_events is not None:
        cohort = cohort.head(args.limit_events)

    manifest = read_inference_manifest(args.input_dir, args.seeds, args.epoch_labels)
    event_frames = []
    missing_frames = []
    input_manifest = []
    for _, manifest_row in manifest.iterrows():
        seed = int(manifest_row["seed"])
        epoch_label = str(manifest_row.get("epoch_label", "primary"))
        model1_epoch = int(manifest_row["model1_epoch"])
        model2_epoch = int(manifest_row["model2_epoch"])
        series_path = Path(manifest_row["required_series_csv"])
        if not series_path.is_absolute():
            series_path = Path.cwd() / series_path
        series = read_required_series(series_path, seed, epoch_label)
        seed_events, missing = event_rows_for_seed(series, cohort)
        event_frames.append(seed_events)
        if not missing.empty:
            missing_frames.append(missing)
        input_manifest.append(
            {
                "seed": seed,
                "epoch_label": epoch_label,
                "model1_epoch": model1_epoch,
                "model2_epoch": model2_epoch,
                "required_series_csv": str(series_path),
                "series_rows": int(len(series)),
                "series_basins": int(series["basin"].nunique()),
                "event_rows": int(len(seed_events)),
                "event_basins": int(seed_events["gauge_id"].nunique()) if not seed_events.empty else 0,
            }
        )

    event_wide = pd.concat(event_frames, ignore_index=True) if event_frames else pd.DataFrame()
    if event_wide.empty:
        raise ValueError("No event rows were produced from stress-test series.")
    event_long = wide_to_long(event_wide)

    cohort_seed_summary = summarize_long(
        event_long,
        [
            "comparison",
            "seed",
            "epoch_label",
            "model1_epoch",
            "model2_epoch",
            "stress_group",
            "response_class",
            "predictor",
            "predictor_label",
        ],
    )
    cohort_aggregate = aggregate_seed_summaries(
        cohort_seed_summary,
        ["comparison", "stress_group", "response_class", "predictor", "predictor_label"],
    )
    cohort_epoch_aggregate = aggregate_seed_summaries(
        cohort_seed_summary,
        [
            "comparison",
            "model1_epoch",
            "model2_epoch",
            "stress_group",
            "response_class",
            "predictor",
            "predictor_label",
        ],
    )
    rain_seed_summary = summarize_long(
        event_long,
        ["comparison", "seed", "epoch_label", "model1_epoch", "model2_epoch", "rain_cohort", "predictor", "predictor_label"],
    )
    rain_aggregate = aggregate_seed_summaries(
        rain_seed_summary,
        ["comparison", "rain_cohort", "predictor", "predictor_label"],
    )
    rain_epoch_aggregate = aggregate_seed_summaries(
        rain_seed_summary,
        ["comparison", "model1_epoch", "model2_epoch", "rain_cohort", "predictor", "predictor_label"],
    )
    stress_delta_seed = paired_delta(event_long, "stress_group")
    response_delta_seed = paired_delta(event_long, "response_class")
    paired_seed_delta = pd.concat([stress_delta_seed, response_delta_seed], ignore_index=True)
    paired_delta_aggregate = aggregate_delta(paired_seed_delta)
    paired_delta_epoch_aggregate = aggregate_delta(paired_seed_delta, ["model1_epoch", "model2_epoch"])

    event_wide.to_csv(output_dir / "extreme_rain_stress_error_table_wide.csv", index=False)
    event_long.to_csv(output_dir / "extreme_rain_stress_error_table_long.csv", index=False)
    cohort_seed_summary.to_csv(output_dir / "cohort_predictor_summary.csv", index=False)
    cohort_aggregate.to_csv(output_dir / "cohort_predictor_aggregate.csv", index=False)
    cohort_epoch_aggregate.to_csv(output_dir / "cohort_epoch_predictor_aggregate.csv", index=False)
    rain_seed_summary.to_csv(output_dir / "rain_cohort_predictor_summary.csv", index=False)
    rain_aggregate.to_csv(output_dir / "rain_cohort_predictor_aggregate.csv", index=False)
    rain_epoch_aggregate.to_csv(output_dir / "rain_cohort_epoch_predictor_aggregate.csv", index=False)
    paired_seed_delta.to_csv(output_dir / "paired_delta_seed_summary.csv", index=False)
    paired_delta_aggregate.to_csv(output_dir / "paired_delta_aggregate.csv", index=False)
    paired_delta_epoch_aggregate.to_csv(output_dir / "paired_delta_epoch_aggregate.csv", index=False)
    if missing_frames:
        pd.concat(missing_frames, ignore_index=True).to_csv(output_dir / "coverage_failure_report.csv", index=False)
    else:
        pd.DataFrame(
            columns=["seed", "epoch_label", "model1_epoch", "model2_epoch", "event_id", "gauge_id", "missing_reason"]
        ).to_csv(
            output_dir / "coverage_failure_report.csv", index=False
        )

    unique_events = event_wide.drop_duplicates(["gauge_id", "event_id"])
    summary = {
        "input_dir": str(args.input_dir),
        "cohort_csv": str(args.cohort_csv),
        "output_dir": str(output_dir),
        "input_manifest": input_manifest,
        "n_manifest_rows": int(len(manifest)),
        "epoch_labels": sorted(manifest["epoch_label"].astype(str).unique().tolist()),
        "epoch_pairs": (
            manifest[["model1_epoch", "model2_epoch"]].drop_duplicates().sort_values(["model1_epoch", "model2_epoch"]).to_dict("records")
        ),
        "event_count_unique": int(unique_events["event_id"].nunique()),
        "seed_event_rows": int(len(event_wide)),
        "basin_count": int(unique_events["gauge_id"].nunique()),
        "rain_cohort_counts_unique_events": unique_events["rain_cohort"].value_counts().to_dict(),
        "response_class_counts_unique_events": unique_events["response_class"].value_counts().to_dict(),
        "stress_group_counts_unique_events": unique_events["stress_group"].value_counts().to_dict(),
        "temporal_relation_counts_unique_events": unique_events["temporal_relation"].value_counts().to_dict()
        if "temporal_relation" in unique_events
        else {},
        "notes": [
            "This is a basin-holdout historical extreme-rain stress test, not the primary temporally isolated test.",
            "Extreme rain events without observed flood-like streamflow response are negative controls.",
            "prec_ari* and flood_ari* are CAMELSH hourly annual-maxima proxy references.",
        ],
    }
    (output_dir / "analysis_summary.json").write_text(json.dumps(json_safe(summary), indent=2), encoding="utf-8")
    write_report(
        output_dir / "extreme_rain_stress_test_report.md",
        event_wide=event_wide,
        cohort_aggregate=cohort_aggregate,
        delta_aggregate=paired_delta_aggregate[paired_delta_aggregate["stratification"] == "stress_group"],
    )
    print(f"Wrote stress-test analysis: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
