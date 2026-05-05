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


DEFAULT_INPUT_DIR = Path("output/model_analysis/quantile_analysis")
DEFAULT_EVENT_RESPONSE_CSV = Path("output/basin/all/analysis/event_response/tables/event_response_table.csv")
DEFAULT_EVENT_LABELS_CSV = Path(
    "output/basin/all/analysis/event_regime/tables/selected_variant_event_labels.csv"
)
DEFAULT_LOW_LAT_SNOW_CHECK_CSV = Path(
    "output/basin/all/analysis/event_regime/metadata/diagnostics/low_lat_snow_check_summary.csv"
)
DEFAULT_OUTPUT_DIR = DEFAULT_INPUT_DIR / "event_regime_analysis"

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

HYDROMET_FEATURES = [
    "recent_1d_ratio",
    "recent_3d_ratio",
    "antecedent_7d_ratio",
    "antecedent_30d_ratio",
    "snowmelt_ratio",
    "snowmelt_fraction",
    "event_mean_temp",
]

EVENT_COLUMNS = [
    "gauge_id",
    "gauge_name",
    "state",
    "huc02",
    "area",
    "snow_fraction",
    "selected_threshold_quantile",
    "selected_threshold_value",
    "event_detection_basis",
    "event_candidate_label",
    "flood_relevance_tier",
    "flood_relevance_basis",
    "event_id",
    "event_start",
    "event_peak",
    "event_end",
    "water_year",
    "peak_month",
    "peak_discharge",
    "unit_area_peak",
    "rising_time_hours",
    "event_duration_hours",
    "recent_rain_24h",
    "recent_rain_72h",
    "antecedent_rain_7d",
    "antecedent_rain_30d",
    "event_mean_temp",
    "degree_day_snowmelt_7d",
    "degree_day_snowmelt_fraction_7d",
    "basin_snowmelt_7d_p90",
    "basin_snowmelt_valid_window_count",
    "basin_rain_1d_p90",
    "basin_rain_3d_p90",
    "basin_rain_7d_p90",
    "basin_rain_30d_p90",
    "return_period_confidence_flag",
]

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
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Join subset300 Model 1/2 required-series predictions to observed high-flow "
            "event candidates and summarize errors by ML event regime and rule label."
        )
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--event-response-csv", type=Path, default=DEFAULT_EVENT_RESPONSE_CSV)
    parser.add_argument("--event-labels-csv", type=Path, default=DEFAULT_EVENT_LABELS_CSV)
    parser.add_argument("--low-lat-snow-check-csv", type=Path, default=DEFAULT_LOW_LAT_SNOW_CHECK_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=sorted(PRIMARY_EPOCHS),
        help="Paired seeds to analyze. Defaults to the completed official paired seeds.",
    )
    parser.add_argument(
        "--limit-events",
        type=int,
        default=None,
        help="Optional row limit after filtering to prediction basins/time range for smoke tests.",
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


def _read_primary_pair(input_dir: Path, seed: int, model1_epoch: int, model2_epoch: int) -> pd.DataFrame:
    m1_path = input_dir / "required_series" / f"seed{seed}" / f"epoch{model1_epoch:03d}_required_series.csv"
    m2_path = input_dir / "required_series" / f"seed{seed}" / f"epoch{model2_epoch:03d}_required_series.csv"
    if not m1_path.exists():
        raise FileNotFoundError(f"Missing Model 1 required-series file: {m1_path}")
    if not m2_path.exists():
        raise FileNotFoundError(f"Missing Model 2 required-series file: {m2_path}")

    left = pd.read_csv(
        m1_path,
        usecols=["basin", "datetime", "obs", "model1"],
        dtype={"basin": str},
        parse_dates=["datetime"],
    )
    right = pd.read_csv(
        m2_path,
        usecols=["basin", "datetime", "q50", "q90", "q95", "q99"],
        dtype={"basin": str},
        parse_dates=["datetime"],
    )
    left["basin"] = left["basin"].map(normalize_gauge_id)
    right["basin"] = right["basin"].map(normalize_gauge_id)
    df = left.merge(right, on=["basin", "datetime"], how="inner", validate="one_to_one")
    for col in ["obs", "model1", "q50", "q90", "q95", "q99"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["seed"] = seed
    df["model1_epoch"] = model1_epoch
    df["model2_epoch"] = model2_epoch
    return df.sort_values(["basin", "datetime"]).reset_index(drop=True)


def _safe_ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    ratio = num / den
    ratio = ratio.where(den > 0)
    return ratio.replace([np.inf, -np.inf], np.nan)


def _read_events(event_response_csv: Path, event_labels_csv: Path) -> pd.DataFrame:
    if not event_response_csv.exists():
        raise FileNotFoundError(f"Missing event response CSV: {event_response_csv}")
    if not event_labels_csv.exists():
        raise FileNotFoundError(f"Missing selected ML event labels CSV: {event_labels_csv}")

    header = pd.read_csv(event_response_csv, nrows=0).columns
    usecols = [col for col in EVENT_COLUMNS if col in header]
    events = pd.read_csv(
        event_response_csv,
        usecols=usecols,
        dtype={"gauge_id": str, "huc02": str},
        parse_dates=["event_start", "event_peak", "event_end"],
    )
    events["gauge_id"] = events["gauge_id"].map(normalize_gauge_id)

    labels = pd.read_csv(
        event_labels_csv,
        usecols=["gauge_id", "event_id", "flood_generation_type", "ml_cluster", "ml_cluster_name"],
        dtype={"gauge_id": str},
    )
    labels["gauge_id"] = labels["gauge_id"].map(normalize_gauge_id)
    labels = labels.rename(
        columns={
            "flood_generation_type": "rule_label",
            "ml_cluster": "ml_cluster_id",
            "ml_cluster_name": "ml_event_regime_raw",
        }
    )
    regime_map = {
        "Weak-driver / snow-influenced": "Weak / low-signal hydromet regime",
        "Weak / low-signal hydromet regime": "Weak / low-signal hydromet regime",
        "Antecedent / multi-day rain": "Antecedent / multi-day rain",
        "Recent rainfall": "Recent rainfall",
    }
    labels["ml_event_regime"] = labels["ml_event_regime_raw"].map(regime_map).fillna(
        labels["ml_event_regime_raw"]
    )

    events = events.merge(labels, on=["gauge_id", "event_id"], how="left", validate="one_to_one")
    if events["ml_event_regime"].isna().any():
        missing = int(events["ml_event_regime"].isna().sum())
        raise ValueError(f"{missing} events have no ML event-regime label after merge.")
    if "return_period_confidence_flag" not in events.columns:
        events["return_period_confidence_flag"] = "not_available"

    events = _attach_hydromet_features(events)
    return events


def _numeric(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce")


def _attach_hydromet_features(events: pd.DataFrame) -> pd.DataFrame:
    out = events.copy()
    out["recent_1d_ratio"] = _safe_ratio(_numeric(out, "recent_rain_24h"), _numeric(out, "basin_rain_1d_p90"))
    out["recent_3d_ratio"] = _safe_ratio(_numeric(out, "recent_rain_72h"), _numeric(out, "basin_rain_3d_p90"))
    out["antecedent_7d_ratio"] = _safe_ratio(
        _numeric(out, "antecedent_rain_7d"), _numeric(out, "basin_rain_7d_p90")
    )
    out["antecedent_30d_ratio"] = _safe_ratio(
        _numeric(out, "antecedent_rain_30d"), _numeric(out, "basin_rain_30d_p90")
    )
    out["snowmelt_ratio"] = _safe_ratio(
        _numeric(out, "degree_day_snowmelt_7d"), _numeric(out, "basin_snowmelt_7d_p90")
    )
    snow_valid = (
        (_numeric(out, "basin_snowmelt_valid_window_count") >= 10)
        & (_numeric(out, "basin_snowmelt_7d_p90") > 0)
    )
    out.loc[~snow_valid, "snowmelt_ratio"] = 0.0
    out["snowmelt_fraction"] = _numeric(out, "degree_day_snowmelt_fraction_7d")
    for col in [
        "recent_1d_ratio",
        "recent_3d_ratio",
        "antecedent_7d_ratio",
        "antecedent_30d_ratio",
        "snowmelt_ratio",
    ]:
        out[col] = pd.to_numeric(out[col], errors="coerce").clip(lower=0).fillna(0.0)
    out["snowmelt_fraction"] = out["snowmelt_fraction"].clip(lower=0, upper=1).fillna(0.0)
    out["event_mean_temp"] = _numeric(out, "event_mean_temp")
    return out


def _rel_error(prediction: float, observation: float) -> float:
    if not np.isfinite(observation) or observation <= 0:
        return math.nan
    return float((prediction - observation) / observation * 100.0)


def _under_deficit(prediction: float, observation: float) -> float:
    if not np.isfinite(observation) or observation <= 0:
        return math.nan
    return float(max(observation - prediction, 0.0) / observation * 100.0)


def _hour_delta(left: pd.Timestamp, right: pd.Timestamp) -> float:
    return float((left - right).total_seconds() / 3600.0)


def _event_threshold_mask(frame: pd.DataFrame, threshold: float) -> pd.Series:
    if np.isfinite(threshold) and threshold > 0:
        mask = frame["obs"] >= threshold
        if mask.any():
            return mask
    cutoff = frame["obs"].quantile(0.9)
    return frame["obs"] >= cutoff


def _summarize_event_prediction(event: pd.Series, frame: pd.DataFrame) -> dict[str, Any]:
    obs_peak_idx = frame["obs"].idxmax()
    obs_peak = float(frame.loc[obs_peak_idx, "obs"])
    obs_peak_time = pd.Timestamp(frame.loc[obs_peak_idx, "datetime"])
    threshold = float(pd.to_numeric(pd.Series([event.get("selected_threshold_value")]), errors="coerce").iloc[0])
    top_mask = _event_threshold_mask(frame, threshold)
    row: dict[str, Any] = {
        "event_window_n_hours": int(len(frame)),
        "event_top_flow_n_hours": int(top_mask.sum()),
        "observed_peak_from_series": obs_peak,
        "observed_peak_time_from_series": obs_peak_time,
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
        row[f"{col}_obs_peak_rel_error_pct"] = _rel_error(pred_at_obs_peak, obs_peak)
        row[f"{col}_obs_peak_abs_error"] = float(abs(pred_at_obs_peak - obs_peak))
        row[f"{col}_obs_peak_underestimated"] = bool(pred_at_obs_peak < obs_peak)
        row[f"{col}_obs_peak_under_deficit_pct"] = _under_deficit(pred_at_obs_peak, obs_peak)
        row[f"{col}_window_peak_rel_error_pct"] = _rel_error(pred_peak, obs_peak)
        row[f"{col}_signed_peak_timing_error_hours"] = _hour_delta(pred_peak_time, obs_peak_time)
        row[f"{col}_abs_peak_timing_error_hours"] = abs(row[f"{col}_signed_peak_timing_error_hours"])
        event_rmse = float(np.sqrt(np.nanmean(np.square(error))))
        event_mae = float(np.nanmean(np.abs(error)))
        row[f"{col}_event_rmse"] = event_rmse
        row[f"{col}_event_mae"] = event_mae
        row[f"{col}_event_nrmse_pct"] = _rel_error(event_rmse, obs_peak) + 100.0
        row[f"{col}_event_nmae_pct"] = _rel_error(event_mae, obs_peak) + 100.0
        row[f"{col}_threshold_exceedance_recall"] = threshold_recall
        row[f"{col}_top_flow_hit_rate"] = top_hit_rate

    return row


def _event_rows_for_seed(series: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    basins = set(series["basin"].unique())
    start = series["datetime"].min()
    end = series["datetime"].max()
    candidates = events[
        events["gauge_id"].isin(basins)
        & (events["event_end"] >= start)
        & (events["event_start"] <= end)
    ].copy()
    rows: list[dict[str, Any]] = []
    series_groups = {basin: group.reset_index(drop=True) for basin, group in series.groupby("basin")}

    metadata_cols = [
        "gauge_id",
        "gauge_name",
        "state",
        "huc02",
        "event_id",
        "event_start",
        "event_peak",
        "event_end",
        "water_year",
        "peak_month",
        "selected_threshold_quantile",
        "selected_threshold_value",
        "event_detection_basis",
        "event_candidate_label",
        "flood_relevance_tier",
        "flood_relevance_basis",
        "return_period_confidence_flag",
        "peak_discharge",
        "unit_area_peak",
        "area",
        "snow_fraction",
        "rising_time_hours",
        "event_duration_hours",
        "rule_label",
        "ml_cluster_id",
        "ml_event_regime",
        *HYDROMET_FEATURES,
    ]
    metadata_cols = [col for col in metadata_cols if col in candidates.columns]

    for _, event in candidates.iterrows():
        basin_series = series_groups.get(event["gauge_id"])
        if basin_series is None:
            continue
        frame = basin_series[
            (basin_series["datetime"] >= event["event_start"])
            & (basin_series["datetime"] <= event["event_end"])
        ]
        if frame.empty:
            continue
        row = {col: event[col] for col in metadata_cols}
        row.update(
            {
                "seed": int(series["seed"].iloc[0]),
                "comparison": "primary",
                "model1_epoch": int(series["model1_epoch"].iloc[0]),
                "model2_epoch": int(series["model2_epoch"].iloc[0]),
            }
        )
        row.update(_summarize_event_prediction(event, frame))
        rows.append(row)

    return pd.DataFrame(rows)


def _wide_to_long(events: pd.DataFrame) -> pd.DataFrame:
    base_cols = [
        "comparison",
        "seed",
        "model1_epoch",
        "model2_epoch",
        "gauge_id",
        "event_id",
        "event_start",
        "event_peak",
        "event_end",
        "water_year",
        "peak_month",
        "huc02",
        "state",
        "selected_threshold_quantile",
        "event_detection_basis",
        "event_candidate_label",
        "flood_relevance_tier",
        "return_period_confidence_flag",
        "rule_label",
        "ml_cluster_id",
        "ml_event_regime",
        "event_window_n_hours",
        "event_top_flow_n_hours",
        "observed_peak_from_series",
        "observed_peak_time_from_series",
        *HYDROMET_FEATURES,
    ]
    base_cols = [col for col in base_cols if col in events.columns]
    rows: list[pd.DataFrame] = []
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
    ]
    for predictor, label in PREDICTORS:
        rename = {f"{predictor}_{suffix}": suffix for suffix in metric_suffixes}
        cols = base_cols + [col for col in rename if col in events.columns]
        frame = events[cols].rename(columns=rename).copy()
        frame["predictor"] = predictor
        frame["predictor_label"] = label
        rows.append(frame)
    return pd.concat(rows, ignore_index=True)


def _summarize_long(long_df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
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
        rows.append(row)
    return pd.DataFrame(rows).sort_values(group_cols)


def _aggregate_seed_summaries(summary: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    value_cols = [
        "underestimation_fraction_at_observed_peak",
        "median_obs_peak_rel_error_pct",
        "median_obs_peak_under_deficit_pct",
        "median_window_peak_rel_error_pct",
        "median_abs_peak_timing_error_hours",
        "median_event_rmse",
        "median_event_nrmse_pct",
        "mean_threshold_exceedance_recall",
        "mean_top_flow_hit_rate",
    ]
    rows: list[dict[str, Any]] = []
    for keys, group in summary.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_cols, keys, strict=True))
        row["n_seed_summaries"] = int(group["seed"].nunique()) if "seed" in group.columns else int(len(group))
        row["mean_n_events"] = float(group["n_events"].mean())
        row["min_n_events"] = int(group["n_events"].min())
        for col in value_cols:
            values = pd.to_numeric(group[col], errors="coerce").dropna()
            row[f"seed_mean_{col}"] = float(values.mean()) if not values.empty else math.nan
            row[f"seed_sd_{col}"] = float(values.std(ddof=1)) if len(values) > 1 else math.nan
            row[f"seed_min_{col}"] = float(values.min()) if not values.empty else math.nan
            row[f"seed_max_{col}"] = float(values.max()) if not values.empty else math.nan
        rows.append(row)
    return pd.DataFrame(rows).sort_values(group_cols)


def _paired_delta(long_df: pd.DataFrame, strat_col: str) -> pd.DataFrame:
    metric_cols = [
        "obs_peak_underestimated",
        "obs_peak_under_deficit_pct",
        "obs_peak_abs_error",
        "event_rmse",
        "event_nrmse_pct",
        "abs_peak_timing_error_hours",
        "threshold_exceedance_recall",
        "top_flow_hit_rate",
    ]
    index_cols = ["seed", "gauge_id", "event_id", strat_col]
    wide = long_df[index_cols + ["predictor", *metric_cols]].pivot_table(
        index=index_cols,
        columns="predictor",
        values=metric_cols,
        aggfunc="first",
    )
    rows: list[dict[str, Any]] = []
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
        frame["abs_error_delta"] = frame[("obs_peak_abs_error", predictor)] - frame[("obs_peak_abs_error", "model1")]
        frame["event_rmse_delta"] = frame[("event_rmse", predictor)] - frame[("event_rmse", "model1")]
        frame["event_nrmse_pct_delta"] = (
            frame[("event_nrmse_pct", predictor)] - frame[("event_nrmse_pct", "model1")]
        )
        frame["abs_peak_timing_error_delta"] = (
            frame[("abs_peak_timing_error_hours", predictor)]
            - frame[("abs_peak_timing_error_hours", "model1")]
        )
        frame["threshold_recall_delta"] = (
            frame[("threshold_exceedance_recall", predictor)]
            - frame[("threshold_exceedance_recall", "model1")]
        )
        frame["top_flow_hit_rate_delta"] = (
            frame[("top_flow_hit_rate", predictor)] - frame[("top_flow_hit_rate", "model1")]
        )
        for keys, group in frame.groupby(["seed", strat_col], dropna=False):
            seed, stratum = keys
            rows.append(
                {
                    "stratification": strat_col,
                    "stratum": stratum,
                    "seed": int(seed),
                    "predictor": predictor,
                    "predictor_label": dict(PREDICTORS)[predictor],
                    "n_events": int(len(group)),
                    "n_basins": int(group.reset_index()["gauge_id"].nunique()),
                    "median_paired_under_deficit_reduction_pct": float(
                        group["under_deficit_reduction_pct"].median()
                    ),
                    "mean_underestimation_fraction_delta": float(
                        group["underestimation_fraction_delta"].mean()
                    ),
                    "median_abs_error_delta": float(group["abs_error_delta"].median()),
                    "median_event_rmse_delta": float(group["event_rmse_delta"].median()),
                    "median_event_nrmse_pct_delta": float(group["event_nrmse_pct_delta"].median()),
                    "median_abs_peak_timing_error_delta": float(
                        group["abs_peak_timing_error_delta"].median()
                    ),
                    "mean_threshold_recall_delta": float(group["threshold_recall_delta"].mean()),
                    "mean_top_flow_hit_rate_delta": float(group["top_flow_hit_rate_delta"].mean()),
                }
            )
    return pd.DataFrame(rows).sort_values(["stratification", "stratum", "seed", "predictor"])


def _regime_feature_sanity(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for regime, group in events.groupby("ml_event_regime", dropna=False):
        row: dict[str, Any] = {
            "ml_event_regime": regime,
            "n_events": int(group["event_id"].nunique()),
            "n_basins": int(group["gauge_id"].nunique()),
            "median_snow_fraction": float(pd.to_numeric(group["snow_fraction"], errors="coerce").median()),
            "share_snow_fraction_lt_1pct": float(
                (pd.to_numeric(group["snow_fraction"], errors="coerce") < 0.01).mean()
            ),
        }
        for feature in HYDROMET_FEATURES:
            row[f"median_{feature}"] = float(pd.to_numeric(group[feature], errors="coerce").median())
        rows.append(row)
    return pd.DataFrame(rows).sort_values("ml_event_regime")


def _table(df: pd.DataFrame, cols: list[str]) -> str:
    if df.empty:
        return "_No rows._"
    rendered = df[cols].copy()
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


def _write_report(
    *,
    path: Path,
    event_wide: pd.DataFrame,
    ml_aggregate: pd.DataFrame,
    rule_aggregate: pd.DataFrame,
    tier_aggregate: pd.DataFrame,
    ml_tier_aggregate: pd.DataFrame,
    ml_delta_aggregate: pd.DataFrame,
    sanity: pd.DataFrame,
    low_lat_snow_check: pd.DataFrame | None,
) -> None:
    ml_key = ml_aggregate[
        (ml_aggregate["predictor"].isin(["model1", "q50", "q90", "q95", "q99"]))
    ].copy()
    rule_key = rule_aggregate[
        (rule_aggregate["predictor"].isin(["model1", "q50", "q90", "q95", "q99"]))
    ].copy()
    tier_key = tier_aggregate[
        (tier_aggregate["predictor"].isin(["model1", "q50", "q90", "q95", "q99"]))
    ].copy()
    ml_tier_key = ml_tier_aggregate[
        (ml_tier_aggregate["predictor"].isin(["model1", "q99"]))
    ].copy()
    delta_key = ml_delta_aggregate[ml_delta_aggregate["predictor"].isin(["q50", "q90", "q95", "q99"])].copy()
    unique_events = event_wide.drop_duplicates(["gauge_id", "event_id"])
    tier_counts = unique_events["flood_relevance_tier"].value_counts(dropna=False).to_dict()

    lines = [
        "# Subset300 Event-Regime Model Error Analysis",
        "",
        "This report was generated by `scripts/model/event_regime/analyze_subset300_event_regime_errors.py`.",
        "",
        "## Scope",
        "",
        f"- Event rows analyzed: {event_wide['event_id'].nunique()} unique events across {event_wide['gauge_id'].nunique()} basins.",
        f"- Paired seeds: {', '.join(str(seed) for seed in sorted(event_wide['seed'].unique()))}.",
        f"- Flood relevance tiers: {tier_counts}.",
        "- Primary stratification: ML `hydromet_only_7 + KMeans(k=3)` event regime.",
        "- Sensitivity stratification: rule-based `degree_day_v2` label.",
        "- `Weak / low-signal hydromet regime` is not interpreted as a snow-dominant class.",
        "- Raw `event_rmse` is discharge-scale dependent; use normalized RMSE or paired deltas for cross-regime interpretation.",
        "",
        "## ML Event-Regime Aggregate",
        "",
        _table(
            ml_key,
            [
                "ml_event_regime",
                "predictor_label",
                "n_seed_summaries",
                "mean_n_events",
                "seed_mean_underestimation_fraction_at_observed_peak",
                "seed_mean_median_obs_peak_rel_error_pct",
                "seed_mean_median_obs_peak_under_deficit_pct",
                "seed_mean_mean_threshold_exceedance_recall",
                "seed_mean_median_event_nrmse_pct",
            ],
        ),
        "",
        "## Paired Delta vs Model 1 by ML Event Regime",
        "",
        "Positive under-deficit reduction and threshold-recall delta mean the Model 2 output improved relative to Model 1.",
        "",
        _table(
            delta_key,
            [
                "stratum",
                "predictor_label",
                "n_seed_summaries",
                "seed_mean_median_paired_under_deficit_reduction_pct",
                "seed_mean_mean_underestimation_fraction_delta",
                "seed_mean_mean_threshold_recall_delta",
                "seed_mean_median_event_nrmse_pct_delta",
            ],
        ),
        "",
        "## Flood-Relevance Tier Sensitivity",
        "",
        _table(
            tier_key,
            [
                "flood_relevance_tier",
                "predictor_label",
                "n_seed_summaries",
                "mean_n_events",
                "seed_mean_underestimation_fraction_at_observed_peak",
                "seed_mean_median_obs_peak_rel_error_pct",
                "seed_mean_mean_threshold_exceedance_recall",
            ],
        ),
        "",
        "## ML Event Regime x Flood-Relevance Tier Check",
        "",
        _table(
            ml_tier_key,
            [
                "ml_event_regime",
                "flood_relevance_tier",
                "predictor_label",
                "n_seed_summaries",
                "mean_n_events",
                "seed_mean_underestimation_fraction_at_observed_peak",
                "seed_mean_median_obs_peak_rel_error_pct",
            ],
        ),
        "",
        "## Rule Label Sensitivity",
        "",
        _table(
            rule_key,
            [
                "rule_label",
                "predictor_label",
                "n_seed_summaries",
                "mean_n_events",
                "seed_mean_underestimation_fraction_at_observed_peak",
                "seed_mean_median_obs_peak_rel_error_pct",
                "seed_mean_mean_threshold_exceedance_recall",
            ],
        ),
        "",
        "## Event-Regime Feature Sanity",
        "",
        _table(
            sanity,
            [
                "ml_event_regime",
                "n_events",
                "n_basins",
                "median_recent_1d_ratio",
                "median_antecedent_7d_ratio",
                "median_snowmelt_fraction",
                "median_event_mean_temp",
                "median_snow_fraction",
            ],
        ),
        "",
    ]
    if low_lat_snow_check is not None and not low_lat_snow_check.empty:
        lines.extend(
            [
                "## Low-Latitude Snow Naming Check",
                "",
                "This precomputed check is included only to guard against calling the weak ML regime snow-dominant.",
                "",
                _table(
                    low_lat_snow_check,
                    [
                        "group",
                        "lat_filter",
                        "basin_count",
                        "median_lat",
                        "median_snow_fraction",
                        "snow_fraction_lt_1pct_count",
                        "strong_top1_ge_0_6_count",
                    ],
                ),
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _aggregate_delta(seed_delta: pd.DataFrame) -> pd.DataFrame:
    value_cols = [
        "median_paired_under_deficit_reduction_pct",
        "mean_underestimation_fraction_delta",
        "median_abs_error_delta",
        "median_event_rmse_delta",
        "median_event_nrmse_pct_delta",
        "median_abs_peak_timing_error_delta",
        "mean_threshold_recall_delta",
        "mean_top_flow_hit_rate_delta",
    ]
    rows: list[dict[str, Any]] = []
    group_cols = ["stratification", "stratum", "predictor", "predictor_label"]
    for keys, group in seed_delta.groupby(group_cols, dropna=False):
        row = dict(zip(group_cols, keys, strict=True))
        row["n_seed_summaries"] = int(group["seed"].nunique())
        row["mean_n_events"] = float(group["n_events"].mean())
        for col in value_cols:
            values = pd.to_numeric(group[col], errors="coerce").dropna()
            row[f"seed_mean_{col}"] = float(values.mean()) if not values.empty else math.nan
            row[f"seed_sd_{col}"] = float(values.std(ddof=1)) if len(values) > 1 else math.nan
            row[f"seed_min_{col}"] = float(values.min()) if not values.empty else math.nan
            row[f"seed_max_{col}"] = float(values.max()) if not values.empty else math.nan
        rows.append(row)
    return pd.DataFrame(rows).sort_values(group_cols)


def main() -> int:
    args = parse_args()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    events = _read_events(args.event_response_csv, args.event_labels_csv)
    event_frames: list[pd.DataFrame] = []
    input_manifest: list[dict[str, Any]] = []

    for seed in args.seeds:
        if seed not in PRIMARY_EPOCHS:
            raise ValueError(f"No default primary epoch mapping for seed {seed}")
        model1_epoch, model2_epoch = PRIMARY_EPOCHS[seed]
        print(
            f"Analyzing seed {seed}: Model 1 epoch {model1_epoch:03d}, Model 2 epoch {model2_epoch:03d}",
            flush=True,
        )
        series = _read_primary_pair(args.input_dir, seed, model1_epoch, model2_epoch)
        seed_events = _event_rows_for_seed(series, events)
        if args.limit_events is not None:
            seed_events = seed_events.head(args.limit_events)
        event_frames.append(seed_events)
        input_manifest.append(
            {
                "seed": seed,
                "model1_epoch": model1_epoch,
                "model2_epoch": model2_epoch,
                "series_rows": int(len(series)),
                "series_basins": int(series["basin"].nunique()),
                "event_rows": int(len(seed_events)),
                "event_basins": int(seed_events["gauge_id"].nunique()),
            }
        )

    event_wide = pd.concat(event_frames, ignore_index=True)
    event_long = _wide_to_long(event_wide)

    ml_seed_summary = _summarize_long(
        event_long,
        ["comparison", "seed", "model1_epoch", "model2_epoch", "ml_event_regime", "predictor", "predictor_label"],
    )
    ml_aggregate = _aggregate_seed_summaries(
        ml_seed_summary,
        ["comparison", "ml_event_regime", "predictor", "predictor_label"],
    )
    rule_seed_summary = _summarize_long(
        event_long,
        ["comparison", "seed", "model1_epoch", "model2_epoch", "rule_label", "predictor", "predictor_label"],
    )
    rule_aggregate = _aggregate_seed_summaries(
        rule_seed_summary,
        ["comparison", "rule_label", "predictor", "predictor_label"],
    )
    tier_seed_summary = _summarize_long(
        event_long,
        ["comparison", "seed", "model1_epoch", "model2_epoch", "flood_relevance_tier", "predictor", "predictor_label"],
    )
    tier_aggregate = _aggregate_seed_summaries(
        tier_seed_summary,
        ["comparison", "flood_relevance_tier", "predictor", "predictor_label"],
    )
    ml_tier_seed_summary = _summarize_long(
        event_long,
        [
            "comparison",
            "seed",
            "model1_epoch",
            "model2_epoch",
            "ml_event_regime",
            "flood_relevance_tier",
            "predictor",
            "predictor_label",
        ],
    )
    ml_tier_aggregate = _aggregate_seed_summaries(
        ml_tier_seed_summary,
        ["comparison", "ml_event_regime", "flood_relevance_tier", "predictor", "predictor_label"],
    )

    ml_seed_delta = _paired_delta(event_long, "ml_event_regime")
    rule_seed_delta = _paired_delta(event_long, "rule_label")
    paired_seed_delta = pd.concat([ml_seed_delta, rule_seed_delta], ignore_index=True)
    paired_delta_aggregate = _aggregate_delta(paired_seed_delta)

    sanity = _regime_feature_sanity(event_wide)
    low_lat_snow_check = None
    if args.low_lat_snow_check_csv.exists():
        low_lat_snow_check = pd.read_csv(args.low_lat_snow_check_csv)

    event_wide.to_csv(output_dir / "event_regime_error_table_wide.csv", index=False)
    event_long.to_csv(output_dir / "event_regime_error_table_long.csv", index=False)
    ml_seed_summary.to_csv(output_dir / "ml_event_regime_predictor_summary.csv", index=False)
    ml_aggregate.to_csv(output_dir / "ml_event_regime_predictor_aggregate.csv", index=False)
    rule_seed_summary.to_csv(output_dir / "rule_label_predictor_summary.csv", index=False)
    rule_aggregate.to_csv(output_dir / "rule_label_predictor_aggregate.csv", index=False)
    tier_seed_summary.to_csv(output_dir / "flood_relevance_tier_predictor_summary.csv", index=False)
    tier_aggregate.to_csv(output_dir / "flood_relevance_tier_predictor_aggregate.csv", index=False)
    ml_tier_seed_summary.to_csv(output_dir / "ml_event_regime_by_flood_tier_predictor_summary.csv", index=False)
    ml_tier_aggregate.to_csv(output_dir / "ml_event_regime_by_flood_tier_predictor_aggregate.csv", index=False)
    paired_seed_delta.to_csv(output_dir / "paired_delta_seed_summary.csv", index=False)
    paired_delta_aggregate.to_csv(output_dir / "paired_delta_aggregate.csv", index=False)
    sanity.to_csv(output_dir / "event_regime_feature_sanity.csv", index=False)

    unique_events = event_wide.drop_duplicates(["gauge_id", "event_id"])
    summary = {
        "input_dir": str(args.input_dir),
        "event_response_csv": str(args.event_response_csv),
        "event_labels_csv": str(args.event_labels_csv),
        "output_dir": str(output_dir),
        "primary_epochs": {str(seed): PRIMARY_EPOCHS[seed] for seed in args.seeds},
        "input_manifest": input_manifest,
        "event_count_unique": int(event_wide["event_id"].nunique()),
        "seed_event_rows": int(len(event_wide)),
        "basin_count": int(event_wide["gauge_id"].nunique()),
        "ml_event_regime_counts_unique_events": unique_events["ml_event_regime"].value_counts().to_dict(),
        "rule_label_counts_unique_events": unique_events["rule_label"].value_counts().to_dict(),
        "flood_relevance_tier_counts_unique_events": unique_events["flood_relevance_tier"].value_counts(dropna=False).to_dict(),
        "return_period_confidence_flag_counts_unique_events": unique_events["return_period_confidence_flag"].value_counts(dropna=False).to_dict(),
        "ml_event_regime_counts_seed_rows": event_wide["ml_event_regime"].value_counts().to_dict(),
        "rule_label_counts_seed_rows": event_wide["rule_label"].value_counts().to_dict(),
        "notes": [
            "Events are observed high-flow candidates, not an official flood inventory.",
            "ML labels are descriptor-space event regimes, not confirmed causal mechanisms.",
            "The weak ML regime should not be described as snow-dominant.",
            "Rule labels are degree-day proxy QA/sensitivity labels.",
        ],
    }
    (output_dir / "analysis_summary.json").write_text(
        json.dumps(json_safe(summary), indent=2), encoding="utf-8"
    )

    _write_report(
        path=output_dir / "event_regime_model_error_report.md",
        event_wide=event_wide,
        ml_aggregate=ml_aggregate,
        rule_aggregate=rule_aggregate,
        tier_aggregate=tier_aggregate,
        ml_tier_aggregate=ml_tier_aggregate,
        ml_delta_aggregate=paired_delta_aggregate[
            paired_delta_aggregate["stratification"] == "ml_event_regime"
        ],
        sanity=sanity,
        low_lat_snow_check=low_lat_snow_check,
    )

    print(f"Wrote event-regime model-error outputs to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
