#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.9",
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

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
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
MODEL2_QUANTILE_COLUMNS = ["q50", "q90", "q95", "q99"]
MODEL2_QUANTILE_LEVELS = {"q50": 0.50, "q90": 0.90, "q95": 0.95, "q99": 0.99}
PEAK_BRACKET_ORDER = ["le_q50", "q50_q90", "q90_q95", "q95_q99", "gt_q99"]
PEAK_BRACKET_LABELS = {
    "le_q50": "<=q50",
    "q50_q90": "q50-q90",
    "q90_q95": "q90-q95",
    "q95_q99": "q95-q99",
    "gt_q99": ">q99",
    "invalid_quantile_order": "invalid quantile order",
    "missing_quantile": "missing quantile",
}
PEAK_BRACKET_CODES = {
    "le_q50": 0,
    "q50_q90": 1,
    "q90_q95": 2,
    "q95_q99": 3,
    "gt_q99": 4,
    "invalid_quantile_order": -1,
    "missing_quantile": -2,
}
PEAK_BRACKET_COLORS = {
    "le_q50": "#2b6cb0",
    "q50_q90": "#2f855a",
    "q90_q95": "#b7791f",
    "q95_q99": "#c05621",
    "gt_q99": "#c53030",
}
PEAK_BRACKET_EPS = 1e-9

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
    parser.add_argument(
        "--peak-quantile-window-hours",
        type=int,
        default=6,
        help="Primary +/- hour window around the observed response peak for local quantile-bracket diagnostics.",
    )
    parser.add_argument(
        "--peak-quantile-sensitivity-hours",
        type=int,
        nargs="*",
        default=[0, 12],
        help="Additional +/- hour windows for peak quantile-bracket sensitivity diagnostics.",
    )
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


def peak_quantile_windows(primary_window: int, sensitivity_windows: list[int]) -> list[int]:
    windows = sorted({int(primary_window), *(int(value) for value in sensitivity_windows)})
    if any(value < 0 for value in windows):
        raise ValueError(f"Peak quantile window hours must be non-negative: {windows}")
    return windows


def suffixed_peak_col(name: str, window_hours: int) -> str:
    return f"model2_obs_peak_{name}_w{int(window_hours)}h"


def safe_log1p(value: float) -> float:
    return float(np.log1p(value)) if np.isfinite(value) and value > -1.0 else math.nan


def interpolate_tau(obs_peak: float, quantiles: dict[str, float], degenerate: bool) -> float:
    if degenerate:
        return math.nan
    if obs_peak <= quantiles["q50"]:
        return 0.50
    if obs_peak > quantiles["q99"]:
        return 0.99

    log_obs = safe_log1p(obs_peak)
    if not np.isfinite(log_obs):
        return math.nan
    pairs = [("q50", "q90"), ("q90", "q95"), ("q95", "q99")]
    for lower, upper in pairs:
        lower_value = quantiles[lower]
        upper_value = quantiles[upper]
        if obs_peak <= upper_value:
            lower_log = safe_log1p(lower_value)
            upper_log = safe_log1p(upper_value)
            denom = upper_log - lower_log
            if not np.isfinite(denom) or abs(denom) <= PEAK_BRACKET_EPS:
                return math.nan
            fraction = min(max((log_obs - lower_log) / denom, 0.0), 1.0)
            lower_tau = MODEL2_QUANTILE_LEVELS[lower]
            upper_tau = MODEL2_QUANTILE_LEVELS[upper]
            return float(lower_tau + fraction * (upper_tau - lower_tau))
    return 0.99


def peak_quantile_bracket_metrics(
    *,
    frame: pd.DataFrame,
    obs_peak: float,
    obs_peak_time: pd.Timestamp,
    window_hours: int,
) -> dict[str, Any]:
    window_start = obs_peak_time - pd.Timedelta(hours=window_hours)
    window_end = obs_peak_time + pd.Timedelta(hours=window_hours)
    local = frame[frame["datetime"].between(window_start, window_end, inclusive="both")]
    if local.empty:
        local = frame.loc[[frame["datetime"].sub(obs_peak_time).abs().idxmin()]]

    quantiles = {
        col: float(pd.to_numeric(local[col], errors="coerce").max(skipna=True))
        for col in MODEL2_QUANTILE_COLUMNS
    }
    missing = any(not np.isfinite(value) for value in quantiles.values())
    order_valid = (not missing) and all(
        quantiles[left] <= quantiles[right] + PEAK_BRACKET_EPS
        for left, right in zip(MODEL2_QUANTILE_COLUMNS, MODEL2_QUANTILE_COLUMNS[1:])
    )
    if missing:
        bracket = "missing_quantile"
    elif not order_valid:
        bracket = "invalid_quantile_order"
    elif obs_peak <= quantiles["q50"]:
        bracket = "le_q50"
    elif obs_peak <= quantiles["q90"]:
        bracket = "q50_q90"
    elif obs_peak <= quantiles["q95"]:
        bracket = "q90_q95"
    elif obs_peak <= quantiles["q99"]:
        bracket = "q95_q99"
    else:
        bracket = "gt_q99"

    degenerate = (
        order_valid
        and np.isfinite(quantiles["q50"])
        and np.isfinite(quantiles["q99"])
        and abs(safe_log1p(quantiles["q99"]) - safe_log1p(quantiles["q50"])) <= PEAK_BRACKET_EPS
    )
    if order_valid and not degenerate:
        q50_log = safe_log1p(quantiles["q50"])
        q99_log = safe_log1p(quantiles["q99"])
        obs_log = safe_log1p(obs_peak)
        denom = q99_log - q50_log
        q50_q99_position = min(max((obs_log - q50_log) / denom, 0.0), 1.0) if np.isfinite(obs_log) else math.nan
        tau_hat = interpolate_tau(obs_peak, quantiles, degenerate=False)
    else:
        q50_q99_position = math.nan
        tau_hat = math.nan

    q99 = quantiles.get("q99", math.nan)
    q99_overflow_ratio = (
        float(max(obs_peak / q99 - 1.0, 0.0))
        if order_valid and np.isfinite(obs_peak) and np.isfinite(q99) and q99 > 0
        else math.nan
    )
    q99_overflow_log1p = (
        float(max(safe_log1p(obs_peak) - safe_log1p(q99), 0.0))
        if order_valid and np.isfinite(safe_log1p(obs_peak)) and np.isfinite(safe_log1p(q99))
        else math.nan
    )
    row: dict[str, Any] = {
        "quantile_window_hours": int(window_hours),
        "quantile_window_start": window_start,
        "quantile_window_end": window_end,
        "quantile_bracket": bracket,
        "quantile_bracket_label": PEAK_BRACKET_LABELS.get(bracket, bracket),
        "quantile_bracket_code": PEAK_BRACKET_CODES.get(bracket, -9),
        "tau_hat": tau_hat,
        "q50_q99_position": q50_q99_position,
        "q99_overflow_ratio": q99_overflow_ratio,
        "q99_overflow_log1p": q99_overflow_log1p,
        "q99_overflow": bool(bracket == "gt_q99"),
        "quantile_order_valid": bool(order_valid),
        "quantile_spread_degenerate": bool(degenerate),
        "obs_peak_le_q50": bool(order_valid and obs_peak <= quantiles["q50"]),
        "obs_peak_le_q90": bool(order_valid and obs_peak <= quantiles["q90"]),
        "obs_peak_le_q95": bool(order_valid and obs_peak <= quantiles["q95"]),
        "obs_peak_le_q99": bool(order_valid and obs_peak <= quantiles["q99"]),
    }
    for col, value in quantiles.items():
        row[f"local_{col}"] = value
    return row


def add_peak_quantile_bracket_metrics(
    *,
    row: dict[str, Any],
    frame: pd.DataFrame,
    obs_peak: float,
    obs_peak_time: pd.Timestamp,
    peak_quantile_windows: list[int],
    primary_peak_quantile_window: int,
) -> None:
    for window_hours in peak_quantile_windows:
        metrics = peak_quantile_bracket_metrics(
            frame=frame,
            obs_peak=obs_peak,
            obs_peak_time=obs_peak_time,
            window_hours=window_hours,
        )
        for key, value in metrics.items():
            if key == "quantile_window_hours":
                continue
            row[suffixed_peak_col(key, window_hours)] = value
            if window_hours == primary_peak_quantile_window:
                row[f"model2_obs_peak_{key}"] = value


def summarize_event_prediction(
    event: pd.Series,
    frame: pd.DataFrame,
    *,
    peak_quantile_windows: list[int],
    primary_peak_quantile_window: int,
) -> dict[str, Any]:
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
    add_peak_quantile_bracket_metrics(
        row=row,
        frame=frame,
        obs_peak=obs_peak,
        obs_peak_time=obs_peak_time,
        peak_quantile_windows=peak_quantile_windows,
        primary_peak_quantile_window=primary_peak_quantile_window,
    )

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


def event_rows_for_seed(
    series: pd.DataFrame,
    cohort: pd.DataFrame,
    *,
    peak_quantile_windows: list[int],
    primary_peak_quantile_window: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    groups = {basin: group.reset_index(drop=True) for basin, group in series.groupby("basin", sort=False)}
    metadata_cols = [
        "event_id",
        "storm_group_id",
        "gauge_id",
        "split",
        "event_time_mode",
        "rolling_endpoint_start",
        "rolling_endpoint_peak",
        "rolling_severity_peak_time",
        "rolling_endpoint_end",
        "rolling_envelope_start",
        "rolling_envelope_end",
        "rain_cohort",
        "stress_group",
        "response_class",
        "rain_start",
        "rain_peak",
        "rain_end",
        "wet_cluster_total_rain",
        "wet_cluster_peak_rainf",
        "wet_rain_threshold_mm_h",
        "wet_gap_hours",
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
        "response_lag_from_rain_peak_h",
        "response_lag_from_rain_start_h",
        "temporal_alignment_flag",
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
        row.update(
            summarize_event_prediction(
                event,
                frame,
                peak_quantile_windows=peak_quantile_windows,
                primary_peak_quantile_window=primary_peak_quantile_window,
            )
        )
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
        "event_time_mode",
        "rolling_endpoint_start",
        "rolling_endpoint_peak",
        "rolling_severity_peak_time",
        "rolling_endpoint_end",
        "rolling_envelope_start",
        "rolling_envelope_end",
        "rain_cohort",
        "stress_group",
        "response_class",
        "rain_start",
        "rain_peak",
        "rain_end",
        "wet_cluster_total_rain",
        "wet_cluster_peak_rainf",
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
        "response_lag_hours",
        "response_lag_from_rain_peak_h",
        "response_lag_from_rain_start_h",
        "temporal_alignment_flag",
        "temporal_relation",
        "return_period_confidence_flag",
        "precip_reference_flag",
        "event_window_n_hours",
        "event_top_flow_n_hours",
        "observed_peak_from_series",
        "observed_peak_time_from_series",
        "stress_threshold_value",
    ]
    base_cols.extend([col for col in events.columns if col.startswith("model2_obs_peak_") and col not in base_cols])
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


def peak_metric_col(metric: str, window_hours: int, primary_window: int) -> str:
    if int(window_hours) == int(primary_window):
        return f"model2_obs_peak_{metric}"
    return suffixed_peak_col(metric, window_hours)


def peak_quantile_event_table(event_wide: pd.DataFrame, windows: list[int], primary_window: int) -> pd.DataFrame:
    metadata_cols = [
        "comparison",
        "seed",
        "epoch_label",
        "model1_epoch",
        "model2_epoch",
        "gauge_id",
        "event_id",
        "storm_group_id",
        "split",
        "event_time_mode",
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
        "observed_peak_from_series",
        "observed_peak_time_from_series",
        "response_lag_from_rain_peak_h",
        "response_lag_from_rain_start_h",
        "temporal_alignment_flag",
    ]
    cols = [col for col in metadata_cols if col in event_wide.columns]
    peak_metrics = [
        "quantile_window_start",
        "quantile_window_end",
        "quantile_bracket",
        "quantile_bracket_label",
        "quantile_bracket_code",
        "tau_hat",
        "q50_q99_position",
        "q99_overflow_ratio",
        "q99_overflow_log1p",
        "q99_overflow",
        "quantile_order_valid",
        "quantile_spread_degenerate",
        "obs_peak_le_q50",
        "obs_peak_le_q90",
        "obs_peak_le_q95",
        "obs_peak_le_q99",
        "local_q50",
        "local_q90",
        "local_q95",
        "local_q99",
    ]
    for window_hours in windows:
        for metric in peak_metrics:
            col = suffixed_peak_col(metric, window_hours)
            if col in event_wide.columns and col not in cols:
                cols.append(col)
    for metric in peak_metrics:
        col = peak_metric_col(metric, primary_window, primary_window)
        if col in event_wide.columns and col not in cols:
            cols.append(col)
    return event_wide[cols].copy()


def bracket_share_for_group(group: pd.DataFrame, bracket_col: str, valid_col: str, bracket: str) -> tuple[int, int, float, float]:
    valid = group[group[valid_col].astype(bool) & group[bracket_col].isin(PEAK_BRACKET_ORDER)].copy()
    valid_events = int(len(valid))
    bracket_count = int(valid[bracket_col].eq(bracket).sum())
    bracket_share = bracket_count / valid_events if valid_events else math.nan
    basin_shares = []
    for _basin, basin_group in valid.groupby("gauge_id", dropna=False):
        if len(basin_group):
            basin_shares.append(float(basin_group[bracket_col].eq(bracket).mean()))
    basin_equal_share = float(np.mean(basin_shares)) if basin_shares else math.nan
    return valid_events, bracket_count, bracket_share, basin_equal_share


def build_peak_quantile_summary(event_wide: pd.DataFrame, windows: list[int], primary_window: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    stratifications = [
        ("all_events", None),
        ("stress_group", "stress_group"),
        ("response_class", "response_class"),
        ("rain_cohort", "rain_cohort"),
    ]
    seed_cols = ["seed", "epoch_label", "model1_epoch", "model2_epoch"]
    for seed_keys, seed_frame in event_wide.groupby(seed_cols, dropna=False):
        seed, epoch_label, model1_epoch, model2_epoch = seed_keys
        for window_hours in windows:
            bracket_col = peak_metric_col("quantile_bracket", window_hours, primary_window)
            valid_col = peak_metric_col("quantile_order_valid", window_hours, primary_window)
            tau_col = peak_metric_col("tau_hat", window_hours, primary_window)
            position_col = peak_metric_col("q50_q99_position", window_hours, primary_window)
            overflow_ratio_col = peak_metric_col("q99_overflow_ratio", window_hours, primary_window)
            overflow_log_col = peak_metric_col("q99_overflow_log1p", window_hours, primary_window)
            if bracket_col not in seed_frame.columns:
                continue
            for stratification, group_col in stratifications:
                if group_col is None:
                    grouped = [(("all_events",), seed_frame)]
                else:
                    grouped = seed_frame.groupby(group_col, dropna=False)
                for keys, group in grouped:
                    stratum = keys[0] if isinstance(keys, tuple) else keys
                    total_events = int(len(group))
                    invalid_order_events = int(group[bracket_col].eq("invalid_quantile_order").sum())
                    missing_quantile_events = int(group[bracket_col].eq("missing_quantile").sum())
                    valid_mask = group[valid_col].astype(bool) & group[bracket_col].isin(PEAK_BRACKET_ORDER)
                    valid_group = group[valid_mask]
                    tau_values = pd.to_numeric(valid_group.get(tau_col), errors="coerce").dropna()
                    position_values = pd.to_numeric(valid_group.get(position_col), errors="coerce").dropna()
                    overflow_values = pd.to_numeric(valid_group.get(overflow_ratio_col), errors="coerce").dropna()
                    overflow_log_values = pd.to_numeric(valid_group.get(overflow_log_col), errors="coerce").dropna()
                    for bracket in PEAK_BRACKET_ORDER:
                        valid_events, bracket_count, bracket_share, basin_equal_share = bracket_share_for_group(
                            group, bracket_col, valid_col, bracket
                        )
                        rows.append(
                            {
                                "window_hours": int(window_hours),
                                "stratification": stratification,
                                "stratum": str(stratum),
                                "seed": int(seed),
                                "epoch_label": str(epoch_label),
                                "model1_epoch": int(model1_epoch),
                                "model2_epoch": int(model2_epoch),
                                "bracket": bracket,
                                "bracket_label": PEAK_BRACKET_LABELS[bracket],
                                "bracket_order": PEAK_BRACKET_CODES[bracket],
                                "n_events_total": total_events,
                                "n_events_valid": valid_events,
                                "n_events_invalid_quantile_order": invalid_order_events,
                                "n_events_missing_quantile": missing_quantile_events,
                                "invalid_quantile_order_share": invalid_order_events / total_events if total_events else math.nan,
                                "missing_quantile_share": missing_quantile_events / total_events if total_events else math.nan,
                                "bracket_count": bracket_count,
                                "bracket_share": bracket_share,
                                "basin_equal_bracket_share": basin_equal_share,
                                "obs_peak_le_q99_share": float(valid_group[bracket_col].ne("gt_q99").mean()) if len(valid_group) else math.nan,
                                "obs_peak_above_q99_share": float(valid_group[bracket_col].eq("gt_q99").mean()) if len(valid_group) else math.nan,
                                "median_tau_hat": float(tau_values.median()) if not tau_values.empty else math.nan,
                                "median_q50_q99_position": float(position_values.median()) if not position_values.empty else math.nan,
                                "median_q99_overflow_ratio": float(overflow_values.median()) if not overflow_values.empty else math.nan,
                                "median_q99_overflow_log1p": float(overflow_log_values.median()) if not overflow_log_values.empty else math.nan,
                            }
                        )
    return pd.DataFrame(rows).sort_values(["window_hours", "stratification", "stratum", "seed", "bracket_order"])


def aggregate_peak_quantile_summary(summary: pd.DataFrame) -> pd.DataFrame:
    group_cols = ["window_hours", "stratification", "stratum", "bracket", "bracket_label", "bracket_order"]
    value_cols = [
        "n_events_total",
        "n_events_valid",
        "n_events_invalid_quantile_order",
        "n_events_missing_quantile",
        "invalid_quantile_order_share",
        "missing_quantile_share",
        "bracket_count",
        "bracket_share",
        "basin_equal_bracket_share",
        "obs_peak_le_q99_share",
        "obs_peak_above_q99_share",
        "median_tau_hat",
        "median_q50_q99_position",
        "median_q99_overflow_ratio",
        "median_q99_overflow_log1p",
    ]
    rows = []
    for keys, group in summary.groupby(group_cols, dropna=False):
        row = dict(zip(group_cols, keys, strict=True))
        row["n_seed_summaries"] = int(len(group))
        for col in value_cols:
            values = pd.to_numeric(group[col], errors="coerce").dropna()
            row[f"seed_mean_{col}"] = float(values.mean()) if not values.empty else math.nan
            row[f"seed_median_{col}"] = float(values.median()) if not values.empty else math.nan
            row[f"seed_sd_{col}"] = float(values.std(ddof=1)) if len(values) > 1 else math.nan
        rows.append(row)
    return pd.DataFrame(rows).sort_values(group_cols)


def build_peak_quantile_sensitivity(event_wide: pd.DataFrame, windows: list[int], primary_window: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    reference_col = peak_metric_col("quantile_bracket", primary_window, primary_window)
    if reference_col not in event_wide.columns:
        return pd.DataFrame()
    stratifications = [("all_events", None), ("response_class", "response_class")]
    seed_cols = ["seed", "epoch_label", "model1_epoch", "model2_epoch"]
    for seed_keys, seed_frame in event_wide.groupby(seed_cols, dropna=False):
        seed, epoch_label, model1_epoch, model2_epoch = seed_keys
        for window_hours in windows:
            if window_hours == primary_window:
                continue
            compare_col = peak_metric_col("quantile_bracket", window_hours, primary_window)
            if compare_col not in seed_frame.columns:
                continue
            for stratification, group_col in stratifications:
                grouped = [(("all_events",), seed_frame)] if group_col is None else seed_frame.groupby(group_col, dropna=False)
                for keys, group in grouped:
                    stratum = keys[0] if isinstance(keys, tuple) else keys
                    total = int(len(group))
                    for from_bracket in [*PEAK_BRACKET_ORDER, "invalid_quantile_order", "missing_quantile"]:
                        from_group = group[group[reference_col].eq(from_bracket)]
                        from_total = int(len(from_group))
                        if from_total == 0:
                            continue
                        for to_bracket in [*PEAK_BRACKET_ORDER, "invalid_quantile_order", "missing_quantile"]:
                            count = int(from_group[compare_col].eq(to_bracket).sum())
                            if count == 0:
                                continue
                            rows.append(
                                {
                                    "seed": int(seed),
                                    "epoch_label": str(epoch_label),
                                    "model1_epoch": int(model1_epoch),
                                    "model2_epoch": int(model2_epoch),
                                    "stratification": stratification,
                                    "stratum": str(stratum),
                                    "reference_window_hours": int(primary_window),
                                    "sensitivity_window_hours": int(window_hours),
                                    "from_bracket": from_bracket,
                                    "from_bracket_label": PEAK_BRACKET_LABELS.get(from_bracket, from_bracket),
                                    "to_bracket": to_bracket,
                                    "to_bracket_label": PEAK_BRACKET_LABELS.get(to_bracket, to_bracket),
                                    "n_events": count,
                                    "share_of_events": count / total if total else math.nan,
                                    "share_of_reference_bracket": count / from_total if from_total else math.nan,
                                }
                            )
    return pd.DataFrame(rows).sort_values(
        ["sensitivity_window_hours", "stratification", "stratum", "seed", "from_bracket", "to_bracket"]
    )


def save_peak_quantile_figures(
    *,
    output_dir: Path,
    event_table: pd.DataFrame,
    aggregate: pd.DataFrame,
    primary_window: int,
) -> pd.DataFrame:
    figures_dir = output_dir / "figures" / "peak_quantile_bracket"
    figures_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, Any]] = []

    def record(name: str, path: Path, description: str) -> None:
        manifest_rows.append({"figure_key": name, "figure_path": str(path), "description": description})

    response_rows = aggregate[
        aggregate["window_hours"].eq(primary_window)
        & aggregate["stratification"].eq("response_class")
        & aggregate["bracket"].isin(PEAK_BRACKET_ORDER)
    ].copy()
    response_order = ["flood_response_ge25", "flood_response_ge2_to_lt25", "high_flow_non_flood_q99_only", "low_response_below_q99"]
    if not response_rows.empty:
        pivot = (
            response_rows.pivot_table(
                index="stratum",
                columns="bracket",
                values="seed_median_bracket_share",
                aggfunc="first",
            )
            .reindex(response_order)
            .fillna(0.0)
        )
        fig, ax = plt.subplots(figsize=(9.8, 4.8), constrained_layout=True)
        bottom = np.zeros(len(pivot))
        x = np.arange(len(pivot))
        for bracket in PEAK_BRACKET_ORDER:
            values = pivot.get(bracket, pd.Series(0.0, index=pivot.index)).to_numpy(dtype=float)
            ax.bar(x, values, bottom=bottom, color=PEAK_BRACKET_COLORS[bracket], label=PEAK_BRACKET_LABELS[bracket])
            bottom += values
        ax.set_xticks(x, [str(item) for item in pivot.index], rotation=22, ha="right")
        ax.set_ylim(0, 1.0)
        ax.set_ylabel("Seed-median event share")
        ax.set_title(f"Observed response peak location in Model 2 quantile ladder (+/-{primary_window}h)")
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.24), ncol=5, frameon=False, fontsize=8)
        ax.grid(True, axis="y", color="#d4d4d8", linewidth=0.55, alpha=0.85)
        path = figures_dir / "response_class_peak_quantile_bracket_stacked.png"
        fig.savefig(path, dpi=180)
        plt.close(fig)
        record("response_class_peak_quantile_bracket_stacked", path, "Response-class stacked share of observed peaks by Model 2 quantile bracket.")

    bracket_col = peak_metric_col("quantile_bracket", primary_window, primary_window)
    tau_col = peak_metric_col("tau_hat", primary_window, primary_window)
    overflow_col = peak_metric_col("q99_overflow_ratio", primary_window, primary_window)
    valid_col = peak_metric_col("quantile_order_valid", primary_window, primary_window)
    valid_events = event_table[event_table[valid_col].astype(bool) & event_table[bracket_col].isin(PEAK_BRACKET_ORDER)].copy()
    if not valid_events.empty and tau_col in valid_events:
        groups = [valid_events[valid_events["response_class"].eq(label)][tau_col].dropna().to_numpy(dtype=float) for label in response_order]
        fig, ax = plt.subplots(figsize=(9.8, 4.8), constrained_layout=True)
        positions = np.arange(1, len(response_order) + 1)
        non_empty = [(pos, values) for pos, values in zip(positions, groups, strict=True) if len(values)]
        if non_empty:
            ax.violinplot([values for _pos, values in non_empty], positions=[pos for pos, _values in non_empty], widths=0.7, showmeans=False, showmedians=True)
        for pos, values in zip(positions, groups, strict=True):
            if len(values):
                jitter = np.linspace(-0.18, 0.18, len(values)) if len(values) > 1 else np.array([0.0])
                ax.scatter(np.full(len(values), pos) + jitter, values, s=12, color="#111827", alpha=0.25, linewidths=0)
        for level in [0.50, 0.90, 0.95, 0.99]:
            ax.axhline(level, color="#71717a", linewidth=0.7, linestyle="--", alpha=0.65)
        ax.set_xticks(positions, response_order, rotation=22, ha="right")
        ax.set_ylim(0.48, 1.01)
        ax.set_ylabel("Peak implied quantile level (log1p interpolation)")
        ax.set_title(f"Observed peak implied quantile level (+/-{primary_window}h)")
        ax.grid(True, axis="y", color="#d4d4d8", linewidth=0.55, alpha=0.85)
        path = figures_dir / "response_class_peak_tau_hat_violin.png"
        fig.savefig(path, dpi=180)
        plt.close(fig)
        record("response_class_peak_tau_hat_violin", path, "Response-class distribution of censored/interpolated peak implied quantile level.")

    overflow_events = valid_events[pd.to_numeric(valid_events.get(overflow_col), errors="coerce").gt(0)].copy()
    fig, ax = plt.subplots(figsize=(9.8, 4.6), constrained_layout=True)
    if overflow_events.empty:
        ax.text(0.5, 0.5, "No observed peaks above local q99", ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
    else:
        data = [
            pd.to_numeric(overflow_events[overflow_events["response_class"].eq(label)][overflow_col], errors="coerce").dropna().to_numpy(dtype=float)
            for label in response_order
        ]
        positions = np.arange(1, len(response_order) + 1)
        non_empty = [(pos, values) for pos, values in zip(positions, data, strict=True) if len(values)]
        if non_empty:
            ax.boxplot([values for _pos, values in non_empty], positions=[pos for pos, _values in non_empty], widths=0.55, showfliers=False)
        for pos, values in zip(positions, data, strict=True):
            if len(values):
                jitter = np.linspace(-0.16, 0.16, len(values)) if len(values) > 1 else np.array([0.0])
                ax.scatter(np.full(len(values), pos) + jitter, values, s=14, color="#c53030", alpha=0.35, linewidths=0)
        ax.set_xticks(positions, response_order, rotation=22, ha="right")
        ax.set_ylabel("max(obs peak / local q99 - 1, 0)")
        ax.set_title(f"Observed peak overflow above local q99 (+/-{primary_window}h)")
        ax.grid(True, axis="y", color="#d4d4d8", linewidth=0.55, alpha=0.85)
    path = figures_dir / "response_class_q99_overflow_severity.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    record("response_class_q99_overflow_severity", path, "Response-class severity for observed peaks above local q99.")

    manifest = pd.DataFrame(manifest_rows)
    manifest.to_csv(output_dir / "peak_quantile_bracket_chart_manifest.csv", index=False)
    return manifest


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


def write_report(
    path: Path,
    event_wide: pd.DataFrame,
    cohort_aggregate: pd.DataFrame,
    delta_aggregate: pd.DataFrame,
    peak_bracket_aggregate: pd.DataFrame,
    primary_peak_quantile_window: int,
) -> None:
    unique_events = event_wide.drop_duplicates(["gauge_id", "event_id"])
    lines = [
        "# Subset300 Extreme-Rain Stress Test",
        "",
        "This report was generated by `scripts/model/extreme_rain/analyze_subset300_extreme_rain_stress_test.py`.",
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
        "- Peak quantile bracket is a conditional diagnostic: it shows where the observed event peak sits in the Model 2 quantile ladder, not calibrated nominal coverage.",
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
        "## Peak Quantile Bracket",
        "",
        f"`Local Peak Quantile Bracket` uses max Model 2 quantiles within +/-{primary_peak_quantile_window}h of the observed response peak.",
        "Do not read these shares as calibrated exceedance probabilities because the sample is conditioned on extreme-rain events and observed response peaks.",
        "",
        table(
            peak_bracket_aggregate[
                peak_bracket_aggregate["stratification"].eq("response_class")
                & peak_bracket_aggregate["window_hours"].eq(primary_peak_quantile_window)
            ],
            [
                "stratum",
                "bracket_label",
                "n_seed_summaries",
                "seed_median_n_events_valid",
                "seed_median_bracket_count",
                "seed_median_bracket_share",
                "seed_median_basin_equal_bracket_share",
                "seed_median_obs_peak_above_q99_share",
                "seed_median_median_tau_hat",
            ],
        ),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    primary_peak_quantile_window = int(args.peak_quantile_window_hours)
    peak_windows = peak_quantile_windows(primary_peak_quantile_window, args.peak_quantile_sensitivity_hours)

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
        seed_events, missing = event_rows_for_seed(
            series,
            cohort,
            peak_quantile_windows=peak_windows,
            primary_peak_quantile_window=primary_peak_quantile_window,
        )
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
    peak_event_table = peak_quantile_event_table(event_wide, peak_windows, primary_peak_quantile_window)
    peak_bracket_summary = build_peak_quantile_summary(event_wide, peak_windows, primary_peak_quantile_window)
    peak_bracket_aggregate = aggregate_peak_quantile_summary(peak_bracket_summary)
    peak_bracket_sensitivity = build_peak_quantile_sensitivity(event_wide, peak_windows, primary_peak_quantile_window)
    peak_chart_manifest = save_peak_quantile_figures(
        output_dir=output_dir,
        event_table=peak_event_table,
        aggregate=peak_bracket_aggregate,
        primary_window=primary_peak_quantile_window,
    )

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
    peak_event_table.to_csv(output_dir / "peak_quantile_bracket_event_table.csv", index=False)
    peak_bracket_summary.to_csv(output_dir / "peak_quantile_bracket_summary.csv", index=False)
    peak_bracket_aggregate.to_csv(output_dir / "peak_quantile_bracket_aggregate.csv", index=False)
    peak_bracket_sensitivity.to_csv(output_dir / "peak_quantile_bracket_sensitivity.csv", index=False)
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
        "peak_quantile_bracket": {
            "primary_window_hours": primary_peak_quantile_window,
            "sensitivity_window_hours": [int(value) for value in peak_windows if int(value) != primary_peak_quantile_window],
            "event_table": str(output_dir / "peak_quantile_bracket_event_table.csv"),
            "summary": str(output_dir / "peak_quantile_bracket_summary.csv"),
            "aggregate": str(output_dir / "peak_quantile_bracket_aggregate.csv"),
            "sensitivity": str(output_dir / "peak_quantile_bracket_sensitivity.csv"),
            "chart_manifest": str(output_dir / "peak_quantile_bracket_chart_manifest.csv"),
            "chart_count": int(len(peak_chart_manifest)),
            "definition": "Observed response peak compared with max(q50/q90/q95/q99) within +/- window hours around observed peak time.",
            "interpretation_limit": "Conditional extreme-rain diagnostic, not calibrated nominal quantile coverage or return-period evidence.",
        },
        "rain_cohort_counts_unique_events": unique_events["rain_cohort"].value_counts().to_dict(),
        "response_class_counts_unique_events": unique_events["response_class"].value_counts().to_dict(),
        "stress_group_counts_unique_events": unique_events["stress_group"].value_counts().to_dict(),
        "temporal_alignment_counts_unique_events": unique_events["temporal_alignment_flag"].value_counts().to_dict()
        if "temporal_alignment_flag" in unique_events
        else {},
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
        peak_bracket_aggregate=peak_bracket_aggregate,
        primary_peak_quantile_window=primary_peak_quantile_window,
    )
    print(f"Wrote stress-test analysis: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
