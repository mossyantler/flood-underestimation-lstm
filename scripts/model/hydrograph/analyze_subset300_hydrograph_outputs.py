#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


SERIES_RE = re.compile(r"seed(?P<seed>\d+)/epoch(?P<epoch>\d{3})_required_series\.csv$")
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
GAP_COLUMNS = ["q90_minus_q50", "q95_minus_q90", "q99_minus_q95", "q99_minus_q50"]
STRATA = [
    ("all", "All hours"),
    ("basin_top10", "Basin Q90-exceedance"),
    ("basin_top5", "Basin Q95-exceedance"),
    ("basin_top1", "Basin Q99-exceedance"),
    ("basin_top0_1", "Basin Q99.9-exceedance"),
]
STRATUM_DISPLAY_LABELS = {
    **dict(STRATA),
    "observed_peak_hour": "Observed peak hour",
}
MODEL_COLORS = {
    "Model 1": "#2563eb",
    "Model 2 q50": "#dc2626",
    "Model 2 q90": "#ef4444",
    "Model 2 q95": "#f97316",
    "Model 2 q99": "#f59e0b",
}
PEAK_ZONE_ORDER = ["le_q50", "q50_q90", "q90_q95", "q95_q99", "gt_q99"]
PEAK_ZONE_LABELS = {
    "le_q50": "<=q50",
    "q50_q90": "q50-q90",
    "q90_q95": "q90-q95",
    "q95_q99": "q95-q99",
    "gt_q99": ">q99",
    "missing_quantile": "missing quantile",
    "invalid_quantile_order": "invalid quantile order",
}
PEAK_ZONE_INTERVAL_LABELS = {
    "le_q50": "(-inf, q50]",
    "q50_q90": "(q50, q90]",
    "q90_q95": "(q90, q95]",
    "q95_q99": "(q95, q99]",
    "gt_q99": "(q99, inf)",
    "missing_quantile": "missing quantile",
    "invalid_quantile_order": "invalid quantile order",
}
PEAK_ZONE_CODES = {
    "le_q50": 0,
    "q50_q90": 1,
    "q90_q95": 2,
    "q95_q99": 3,
    "gt_q99": 4,
    "missing_quantile": -2,
    "invalid_quantile_order": -1,
}
PEAK_ZONE_COLORS = {
    "le_q50": "#2b6cb0",
    "q50_q90": "#2f855a",
    "q90_q95": "#b7791f",
    "q95_q99": "#c05621",
    "gt_q99": "#c53030",
}
PEAK_ZONE_EPS = 1e-9


def _series_files(input_dir: Path) -> list[Path]:
    files = sorted((input_dir / "required_series").glob("seed*/epoch*_required_series.csv"))
    if not files:
        raise FileNotFoundError(f"No required-series CSV files found under {input_dir}")
    return files


def _parse_series_file(path: Path) -> tuple[int, int]:
    match = SERIES_RE.search(path.as_posix())
    if not match:
        raise ValueError(f"Unexpected required-series file path: {path}")
    return int(match.group("seed")), int(match.group("epoch"))


def _read_same_epoch(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"basin": str})
    df["basin"] = df["basin"].str.zfill(8)
    df["datetime"] = pd.to_datetime(df["datetime"])
    for col in ["obs", "model1", "q50", "q90", "q95", "q99", *GAP_COLUMNS]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _read_primary_pair(base_dir: Path, seed: int, model1_epoch: int, model2_epoch: int) -> pd.DataFrame:
    m1_path = base_dir / "required_series" / f"seed{seed}" / f"epoch{model1_epoch:03d}_required_series.csv"
    m2_path = base_dir / "required_series" / f"seed{seed}" / f"epoch{model2_epoch:03d}_required_series.csv"

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
    left["basin"] = left["basin"].str.zfill(8)
    right["basin"] = right["basin"].str.zfill(8)
    df = left.merge(right, on=["basin", "datetime"], how="inner", validate="one_to_one")
    for col in ["obs", "model1", "q50", "q90", "q95", "q99"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["q90_minus_q50"] = df["q90"] - df["q50"]
    df["q95_minus_q90"] = df["q95"] - df["q90"]
    df["q99_minus_q95"] = df["q99"] - df["q95"]
    df["q99_minus_q50"] = df["q99"] - df["q50"]
    df["model1_epoch"] = model1_epoch
    df["model2_epoch"] = model2_epoch
    return df


def _stratum_masks(df: pd.DataFrame) -> dict[str, pd.Series]:
    masks: dict[str, pd.Series] = {"all": pd.Series(True, index=df.index)}
    thresholds = df.groupby("basin")["obs"].quantile([0.90, 0.95, 0.99, 0.999]).unstack()
    thresholds.columns = ["q90_obs", "q95_obs", "q99_obs", "q999_obs"]
    joined = df[["basin", "obs"]].join(thresholds, on="basin")
    masks["basin_top10"] = joined["obs"] >= joined["q90_obs"]
    masks["basin_top5"] = joined["obs"] >= joined["q95_obs"]
    masks["basin_top1"] = joined["obs"] >= joined["q99_obs"]
    masks["basin_top0_1"] = joined["obs"] >= joined["q999_obs"]
    return masks


def _safe_rel(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    out = pd.Series(np.nan, index=numerator.index, dtype=float)
    mask = denominator > 0
    out.loc[mask] = numerator.loc[mask] / denominator.loc[mask]
    return out


def _safe_log1p(value: float) -> float:
    return float(np.log1p(value)) if np.isfinite(value) and value > -1.0 else np.nan


def _peak_zone(row: pd.Series) -> str:
    values = {col: float(row[col]) for col in ["q50", "q90", "q95", "q99"]}
    if any(not np.isfinite(value) for value in values.values()):
        return "missing_quantile"
    order_valid = all(
        values[left] <= values[right] + PEAK_ZONE_EPS
        for left, right in zip(["q50", "q90", "q95"], ["q90", "q95", "q99"])
    )
    if not order_valid:
        return "invalid_quantile_order"
    obs = float(row["obs"])
    if obs <= values["q50"]:
        return "le_q50"
    if obs <= values["q90"]:
        return "q50_q90"
    if obs <= values["q95"]:
        return "q90_q95"
    if obs <= values["q99"]:
        return "q95_q99"
    return "gt_q99"


def _peak_tau_hat(row: pd.Series, zone: str) -> float:
    if zone in {"missing_quantile", "invalid_quantile_order"}:
        return np.nan
    obs = float(row["obs"])
    if zone == "le_q50":
        return 0.50
    if zone == "gt_q99":
        return 0.99
    intervals = [("q50", "q90", 0.50, 0.90), ("q90", "q95", 0.90, 0.95), ("q95", "q99", 0.95, 0.99)]
    for lower_col, upper_col, lower_tau, upper_tau in intervals:
        lower = float(row[lower_col])
        upper = float(row[upper_col])
        if obs <= upper:
            lower_log = _safe_log1p(lower)
            upper_log = _safe_log1p(upper)
            obs_log = _safe_log1p(obs)
            denom = upper_log - lower_log
            if not np.isfinite(denom) or abs(denom) <= PEAK_ZONE_EPS or not np.isfinite(obs_log):
                return np.nan
            fraction = min(max((obs_log - lower_log) / denom, 0.0), 1.0)
            return float(lower_tau + fraction * (upper_tau - lower_tau))
    return 0.99


def _peak_q50_q99_position(row: pd.Series, zone: str) -> float:
    if zone in {"missing_quantile", "invalid_quantile_order"}:
        return np.nan
    q50_log = _safe_log1p(float(row["q50"]))
    q99_log = _safe_log1p(float(row["q99"]))
    obs_log = _safe_log1p(float(row["obs"]))
    denom = q99_log - q50_log
    if not np.isfinite(denom) or abs(denom) <= PEAK_ZONE_EPS or not np.isfinite(obs_log):
        return np.nan
    return float(min(max((obs_log - q50_log) / denom, 0.0), 1.0))


def _add_peak_quantile_zones(peaks: pd.DataFrame) -> pd.DataFrame:
    peaks = peaks.copy()
    zones = peaks.apply(_peak_zone, axis=1)
    peaks["obs_peak_quantile_zone"] = zones
    peaks["obs_peak_quantile_zone_label"] = zones.map(PEAK_ZONE_LABELS)
    peaks["obs_peak_quantile_interval"] = zones.map(PEAK_ZONE_INTERVAL_LABELS)
    peaks["obs_peak_quantile_zone_code"] = zones.map(PEAK_ZONE_CODES).astype(int)
    peaks["obs_peak_quantile_order_valid"] = zones.isin(PEAK_ZONE_ORDER)
    peaks["obs_peak_tau_hat"] = [
        _peak_tau_hat(row, zone) for zone, (_, row) in zip(zones, peaks.iterrows(), strict=True)
    ]
    peaks["obs_peak_q50_q99_position"] = [
        _peak_q50_q99_position(row, zone) for zone, (_, row) in zip(zones, peaks.iterrows(), strict=True)
    ]
    peaks["obs_peak_above_q99"] = zones.eq("gt_q99")
    peaks["obs_peak_le_q50"] = zones.eq("le_q50")
    peaks["obs_peak_le_q90"] = zones.isin(["le_q50", "q50_q90"])
    peaks["obs_peak_le_q95"] = zones.isin(["le_q50", "q50_q90", "q90_q95"])
    peaks["obs_peak_le_q99"] = zones.isin(["le_q50", "q50_q90", "q90_q95", "q95_q99"])
    return peaks


def _summarize_predictor(
    *,
    frame: pd.DataFrame,
    predictor_col: str,
    predictor_label: str,
    comparison: str,
    seed: int,
    model1_epoch: int,
    model2_epoch: int,
    stratum: str,
) -> dict[str, float | int | str]:
    obs = frame["obs"]
    pred = frame[predictor_col]
    bias = pred - obs
    rel_bias_pct = _safe_rel(bias, obs) * 100.0
    under_deficit_pct = _safe_rel((obs - pred).clip(lower=0), obs) * 100.0
    return {
        "comparison": comparison,
        "seed": seed,
        "model1_epoch": model1_epoch,
        "model2_epoch": model2_epoch,
        "stratum": stratum,
        "predictor": predictor_label,
        "n_rows": int(len(frame)),
        "n_basins": int(frame["basin"].nunique()),
        "mean_obs": float(obs.mean()),
        "median_obs": float(obs.median()),
        "coverage_fraction": float((obs <= pred).mean()),
        "underestimation_fraction": float((pred < obs).mean()),
        "mean_bias": float(bias.mean()),
        "median_bias": float(bias.median()),
        "mean_rel_bias_pct": float(rel_bias_pct.mean(skipna=True)),
        "median_rel_bias_pct": float(rel_bias_pct.median(skipna=True)),
        "median_under_rel_deficit_pct": float(under_deficit_pct.median(skipna=True)),
        "median_abs_error": float((pred - obs).abs().median()),
    }


def _summarize_gaps(
    *,
    frame: pd.DataFrame,
    comparison: str,
    seed: int,
    model1_epoch: int,
    model2_epoch: int,
    stratum: str,
) -> dict[str, float | int | str]:
    row: dict[str, float | int | str] = {
        "comparison": comparison,
        "seed": seed,
        "model1_epoch": model1_epoch,
        "model2_epoch": model2_epoch,
        "stratum": stratum,
        "n_rows": int(len(frame)),
        "n_basins": int(frame["basin"].nunique()),
        "mean_obs": float(frame["obs"].mean()),
        "median_obs": float(frame["obs"].median()),
    }
    for col in GAP_COLUMNS:
        row[f"median_{col}"] = float(frame[col].median())
        row[f"mean_{col}"] = float(frame[col].mean())
        row[f"median_{col}_pct_obs"] = float((_safe_rel(frame[col], frame["obs"]) * 100.0).median(skipna=True))
    return row


def _peak_rows(df: pd.DataFrame, *, comparison: str, seed: int, model1_epoch: int, model2_epoch: int) -> pd.DataFrame:
    peak_idx = df.groupby("basin")["obs"].idxmax()
    peaks = df.loc[peak_idx, ["basin", "datetime", "obs", "model1", "q50", "q90", "q95", "q99", *GAP_COLUMNS]].copy()
    peaks.insert(0, "model2_epoch", model2_epoch)
    peaks.insert(0, "model1_epoch", model1_epoch)
    peaks.insert(0, "seed", seed)
    peaks.insert(0, "comparison", comparison)
    for col, label in PREDICTORS:
        peaks[f"{col}_rel_bias_pct"] = _safe_rel(peaks[col] - peaks["obs"], peaks["obs"]) * 100.0
        peaks[f"{col}_underestimated"] = peaks[col] < peaks["obs"]
    return peaks


def _stratum_zone_rows(
    df: pd.DataFrame,
    *,
    comparison: str,
    stratum: str,
    seed: int,
    model1_epoch: int,
    model2_epoch: int,
) -> pd.DataFrame:
    masks = _stratum_masks(df)
    frame = df.loc[masks[stratum], ["basin", "datetime", "obs", "q50", "q90", "q95", "q99"]].copy()
    frame.insert(0, "stratum", stratum)
    frame.insert(0, "model2_epoch", model2_epoch)
    frame.insert(0, "model1_epoch", model1_epoch)
    frame.insert(0, "seed", seed)
    frame.insert(0, "comparison", comparison)
    return frame


def _summarize_frame(
    df: pd.DataFrame,
    *,
    comparison: str,
    seed: int,
    model1_epoch: int,
    model2_epoch: int,
) -> tuple[list[dict], list[dict], pd.DataFrame]:
    masks = _stratum_masks(df)
    predictor_rows: list[dict] = []
    gap_rows: list[dict] = []
    for stratum, _label in STRATA:
        frame = df.loc[masks[stratum]].copy()
        if frame.empty:
            continue
        for col, label in PREDICTORS:
            predictor_rows.append(
                _summarize_predictor(
                    frame=frame,
                    predictor_col=col,
                    predictor_label=label,
                    comparison=comparison,
                    seed=seed,
                    model1_epoch=model1_epoch,
                    model2_epoch=model2_epoch,
                    stratum=stratum,
                )
            )
        gap_rows.append(
            _summarize_gaps(
                frame=frame,
                comparison=comparison,
                seed=seed,
                model1_epoch=model1_epoch,
                model2_epoch=model2_epoch,
                stratum=stratum,
            )
        )

    peaks = _peak_rows(df, comparison=comparison, seed=seed, model1_epoch=model1_epoch, model2_epoch=model2_epoch)
    for col, label in PREDICTORS:
        predictor_rows.append(
            _summarize_predictor(
                frame=peaks,
                predictor_col=col,
                predictor_label=label,
                comparison=comparison,
                seed=seed,
                model1_epoch=model1_epoch,
                model2_epoch=model2_epoch,
                stratum="observed_peak_hour",
            )
        )
    gap_rows.append(
        _summarize_gaps(
            frame=peaks,
            comparison=comparison,
            seed=seed,
            model1_epoch=model1_epoch,
            model2_epoch=model2_epoch,
            stratum="observed_peak_hour",
        )
    )
    return predictor_rows, gap_rows, peaks


def _sanity_row(df: pd.DataFrame, path: Path, *, seed: int, epoch: int) -> dict[str, float | int | str]:
    q50_diff = (df["model2_q50_result"] - df["q50"]).abs()
    return {
        "path": str(path),
        "seed": seed,
        "epoch": epoch,
        "n_rows": int(len(df)),
        "n_basins": int(df["basin"].nunique()),
        "q50_result_max_abs_diff": float(q50_diff.max()),
        "q50_result_median_abs_diff": float(q50_diff.median()),
        "q90_lt_q50_rows": int((df["q90"] < df["q50"]).sum()),
        "q95_lt_q90_rows": int((df["q95"] < df["q90"]).sum()),
        "q99_lt_q95_rows": int((df["q99"] < df["q95"]).sum()),
    }


def _aggregate(summary: pd.DataFrame) -> pd.DataFrame:
    value_cols = [
        "coverage_fraction",
        "underestimation_fraction",
        "median_rel_bias_pct",
        "median_under_rel_deficit_pct",
        "median_abs_error",
    ]
    grouped = summary.groupby(["comparison", "stratum", "predictor"], dropna=False)
    rows = []
    for key, group in grouped:
        row = dict(zip(["comparison", "stratum", "predictor"], key, strict=True))
        row["n_summaries"] = int(len(group))
        for col in value_cols:
            row[f"mean_{col}"] = float(group[col].mean())
            row[f"median_{col}"] = float(group[col].median())
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["comparison", "stratum", "predictor"])


def _aggregate_gaps(gaps: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "median_q90_minus_q50",
        "median_q95_minus_q90",
        "median_q99_minus_q95",
        "median_q99_minus_q50",
        "median_q99_minus_q50_pct_obs",
    ]
    rows = []
    for key, group in gaps.groupby(["comparison", "stratum"], dropna=False):
        row = dict(zip(["comparison", "stratum"], key, strict=True))
        row["n_summaries"] = int(len(group))
        for col in cols:
            row[f"mean_{col}"] = float(group[col].mean())
            row[f"median_{col}"] = float(group[col].median())
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["comparison", "stratum"])


def _peak_zone_table(peaks: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "comparison",
        "seed",
        "model1_epoch",
        "model2_epoch",
        "basin",
        "datetime",
        "obs",
        "q50",
        "q90",
        "q95",
        "q99",
        "obs_peak_quantile_zone",
        "obs_peak_quantile_zone_label",
        "obs_peak_quantile_interval",
        "obs_peak_quantile_zone_code",
        "obs_peak_tau_hat",
        "obs_peak_q50_q99_position",
        "obs_peak_above_q99",
        "obs_peak_le_q50",
        "obs_peak_le_q90",
        "obs_peak_le_q95",
        "obs_peak_le_q99",
        "obs_peak_quantile_order_valid",
    ]
    return peaks[[col for col in cols if col in peaks.columns]].sort_values(
        ["comparison", "seed", "model1_epoch", "model2_epoch", "basin"]
    )


def _stratum_zone_table(zones: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "comparison",
        "stratum",
        "seed",
        "model1_epoch",
        "model2_epoch",
        "basin",
        "datetime",
        "obs",
        "q50",
        "q90",
        "q95",
        "q99",
        "obs_peak_quantile_zone",
        "obs_peak_quantile_zone_label",
        "obs_peak_quantile_interval",
        "obs_peak_quantile_zone_code",
        "obs_peak_tau_hat",
        "obs_peak_q50_q99_position",
        "obs_peak_above_q99",
        "obs_peak_le_q50",
        "obs_peak_le_q90",
        "obs_peak_le_q95",
        "obs_peak_le_q99",
        "obs_peak_quantile_order_valid",
    ]
    return zones[[col for col in cols if col in zones.columns]].sort_values(
        ["comparison", "stratum", "seed", "model1_epoch", "model2_epoch", "basin", "datetime"]
    )


def _summarize_peak_zones(peaks: pd.DataFrame) -> pd.DataFrame:
    rows = []
    group_cols = ["comparison", "seed", "model1_epoch", "model2_epoch"]
    for keys, group in peaks.groupby(group_cols, dropna=False):
        row_base = dict(zip(group_cols, keys, strict=True))
        total = int(len(group))
        valid = group[group["obs_peak_quantile_zone"].isin(PEAK_ZONE_ORDER)].copy()
        for zone in PEAK_ZONE_ORDER:
            zone_group = valid[valid["obs_peak_quantile_zone"].eq(zone)]
            rows.append(
                {
                    **row_base,
                    "obs_peak_quantile_zone": zone,
                    "obs_peak_quantile_zone_label": PEAK_ZONE_LABELS[zone],
                    "obs_peak_quantile_interval": PEAK_ZONE_INTERVAL_LABELS[zone],
                    "obs_peak_quantile_zone_code": PEAK_ZONE_CODES[zone],
                    "n_peak_rows_total": total,
                    "n_peak_rows_valid": int(len(valid)),
                    "n_basins_total": int(group["basin"].nunique()),
                    "n_basins_valid": int(valid["basin"].nunique()),
                    "n_peaks_in_zone": int(len(zone_group)),
                    "peak_zone_share": float(len(zone_group) / len(valid)) if len(valid) else np.nan,
                    "median_obs": float(zone_group["obs"].median()) if len(zone_group) else np.nan,
                    "median_tau_hat": float(zone_group["obs_peak_tau_hat"].median()) if len(zone_group) else np.nan,
                    "median_q50_q99_position": float(zone_group["obs_peak_q50_q99_position"].median()) if len(zone_group) else np.nan,
                    "invalid_or_missing_quantile_count": int(total - len(valid)),
                }
            )
    return pd.DataFrame(rows).sort_values([*group_cols, "obs_peak_quantile_zone_code"])


def _summarize_stratum_zones(zones: pd.DataFrame) -> pd.DataFrame:
    rows = []
    group_cols = ["comparison", "stratum", "seed", "model1_epoch", "model2_epoch"]
    for keys, group in zones.groupby(group_cols, dropna=False):
        row_base = dict(zip(group_cols, keys, strict=True))
        total = int(len(group))
        valid = group[group["obs_peak_quantile_zone"].isin(PEAK_ZONE_ORDER)].copy()
        for zone in PEAK_ZONE_ORDER:
            zone_group = valid[valid["obs_peak_quantile_zone"].eq(zone)]
            rows.append(
                {
                    **row_base,
                    "obs_quantile_zone": zone,
                    "obs_quantile_zone_label": PEAK_ZONE_LABELS[zone],
                    "obs_quantile_interval": PEAK_ZONE_INTERVAL_LABELS[zone],
                    "obs_quantile_zone_code": PEAK_ZONE_CODES[zone],
                    "n_rows_total": total,
                    "n_rows_valid": int(len(valid)),
                    "n_basins_total": int(group["basin"].nunique()),
                    "n_basins_valid": int(valid["basin"].nunique()),
                    "n_rows_in_zone": int(len(zone_group)),
                    "zone_share": float(len(zone_group) / len(valid)) if len(valid) else np.nan,
                    "median_obs": float(zone_group["obs"].median()) if len(zone_group) else np.nan,
                    "median_tau_hat": float(zone_group["obs_peak_tau_hat"].median()) if len(zone_group) else np.nan,
                    "median_q50_q99_position": float(zone_group["obs_peak_q50_q99_position"].median()) if len(zone_group) else np.nan,
                    "invalid_or_missing_quantile_count": int(total - len(valid)),
                }
            )
    return pd.DataFrame(rows).sort_values([*group_cols, "obs_quantile_zone_code"])


def _aggregate_peak_zones(summary: pd.DataFrame) -> pd.DataFrame:
    group_cols = ["comparison", "obs_peak_quantile_zone", "obs_peak_quantile_zone_label", "obs_peak_quantile_interval", "obs_peak_quantile_zone_code"]
    value_cols = [
        "n_peak_rows_valid",
        "n_basins_valid",
        "n_peaks_in_zone",
        "peak_zone_share",
        "median_obs",
        "median_tau_hat",
        "median_q50_q99_position",
        "invalid_or_missing_quantile_count",
    ]
    rows = []
    for keys, group in summary.groupby(group_cols, dropna=False):
        row = dict(zip(group_cols, keys, strict=True))
        row["n_summaries"] = int(len(group))
        for col in value_cols:
            values = pd.to_numeric(group[col], errors="coerce").dropna()
            row[f"mean_{col}"] = float(values.mean()) if not values.empty else np.nan
            row[f"median_{col}"] = float(values.median()) if not values.empty else np.nan
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["comparison", "obs_peak_quantile_zone_code"])


def _plot_primary_peak_zones(peak_summary: pd.DataFrame, q99_exceedance_summary: pd.DataFrame, charts_dir: Path) -> None:
    panels = [
        (
            "basin_top1",
            q99_exceedance_summary[
                (q99_exceedance_summary["comparison"].eq("primary"))
                & (q99_exceedance_summary["stratum"].eq("basin_top1"))
            ].copy(),
            "Q99-exceedance hours",
            "Q99-exceedance share",
            "obs_quantile_zone",
            "zone_share",
        ),
        (
            "observed_peak_hour",
            peak_summary[peak_summary["comparison"].eq("primary")].copy(),
            "observed_peak_hour",
            "Observed peak share",
            "obs_peak_quantile_zone",
            "peak_zone_share",
        ),
    ]
    if all(panel[1].empty for panel in panels):
        return
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), sharey=True)
    for ax, (_context, data, title, ylabel, zone_col, share_col) in zip(axes, panels, strict=True):
        if data.empty:
            ax.set_title(title)
            ax.text(0.5, 0.5, "No rows", ha="center", va="center", transform=ax.transAxes)
            continue
        pivot = (
            data.pivot_table(
                index="seed",
                columns=zone_col,
                values=share_col,
                aggfunc="first",
            )
            .reindex(columns=PEAK_ZONE_ORDER)
            .fillna(0.0)
            .sort_index()
        )
        bottom = np.zeros(len(pivot))
        x = np.arange(len(pivot))
        for zone in PEAK_ZONE_ORDER:
            values = pivot[zone].to_numpy(dtype=float)
            ax.bar(x, values, bottom=bottom, color=PEAK_ZONE_COLORS[zone], label=PEAK_ZONE_LABELS[zone])
            bottom += values
        ax.set_xticks(x, [str(seed) for seed in pivot.index])
        ax.set_ylim(0, 1)
        ax.set_xlabel("Seed")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(True, axis="y", alpha=0.3)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 0.02), ncol=5, fontsize=8, frameon=False)
    fig.suptitle("Primary Q99/peak quantile-zone share by seed", y=0.98, fontsize=12)
    fig.tight_layout(rect=(0.03, 0.11, 0.98, 0.92))
    fig.savefig(charts_dir / "primary_q99_and_peak_quantile_zone_by_seed.png", dpi=170)
    plt.close(fig)


def _plot_q99_exceedance_underestimation(summary: pd.DataFrame, charts_dir: Path) -> None:
    data = summary[(summary["comparison"] == "same_epoch") & (summary["stratum"] == "basin_top1")]
    fig, axes = plt.subplots(1, 3, figsize=(17, 4.8), sharey=True)
    for ax, seed in zip(axes, sorted(data["seed"].unique()), strict=True):
        seed_data = data[data["seed"] == seed]
        for predictor, group in seed_data.groupby("predictor"):
            ax.plot(
                group["model2_epoch"],
                group["underestimation_fraction"],
                marker="o",
                linewidth=1.6,
                color=MODEL_COLORS.get(predictor),
                label=predictor,
            )
        ax.set_title(f"seed {seed}")
        ax.set_xlabel("Epoch")
        ax.grid(True, alpha=0.35)
    axes[0].set_ylabel("Underestimation fraction on basin Q99-exceedance hours")
    axes[-1].legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=8)
    fig.tight_layout()
    fig.savefig(charts_dir / "q99_exceedance_underestimation_fraction_by_epoch.png", dpi=170)
    fig.savefig(charts_dir / "top1_underestimation_fraction_by_epoch.png", dpi=170)
    plt.close(fig)


def _plot_primary_rel_bias(summary: pd.DataFrame, charts_dir: Path) -> None:
    data = summary[(summary["comparison"] == "primary") & (summary["stratum"].isin(["basin_top1", "observed_peak_hour"]))]
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), sharey=True)
    for ax, stratum in zip(axes, ["basin_top1", "observed_peak_hour"], strict=True):
        subset = data[data["stratum"] == stratum]
        pivot = subset.pivot(index="seed", columns="predictor", values="median_rel_bias_pct")
        pivot = pivot[[label for _col, label in PREDICTORS]]
        x = np.arange(len(pivot.index))
        width = 0.16
        for i, predictor in enumerate(pivot.columns):
            ax.bar(x + (i - 2) * width, pivot[predictor], width=width, color=MODEL_COLORS.get(predictor), label=predictor)
        ax.axhline(0, color="#111111", linewidth=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels(pivot.index)
        ax.set_title(STRATUM_DISPLAY_LABELS.get(stratum, stratum))
        ax.set_xlabel("Seed")
        ax.grid(True, axis="y", alpha=0.3)
    axes[0].set_ylabel("Median relative bias (%)")
    axes[-1].legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=8)
    fig.tight_layout()
    fig.savefig(charts_dir / "primary_peak_relative_bias_by_seed.png", dpi=170)
    plt.close(fig)


def _plot_gap_growth(gaps: pd.DataFrame, charts_dir: Path) -> None:
    data = gaps[(gaps["comparison"] == "same_epoch") & (gaps["stratum"] == "basin_top1")]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    for seed, group in data.groupby("seed"):
        ax.plot(group["model2_epoch"], group["median_q99_minus_q50_pct_obs"], marker="o", linewidth=1.7, label=f"seed {seed}")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Median (q99 - q50) / observed (%) on Q99-exceedance hours")
    ax.grid(True, alpha=0.35)
    ax.legend()
    fig.tight_layout()
    fig.savefig(charts_dir / "q99_exceedance_q99_q50_gap_pct_obs_by_epoch.png", dpi=170)
    fig.savefig(charts_dir / "top1_q99_q50_gap_pct_obs_by_epoch.png", dpi=170)
    plt.close(fig)


def _write_markdown(
    *,
    out_path: Path,
    aggregate: pd.DataFrame,
    gap_aggregate: pd.DataFrame,
    peak_zone_aggregate: pd.DataFrame,
    q99_exceedance_zone_summary: pd.DataFrame,
    sanity: pd.DataFrame,
) -> None:
    def table(df: pd.DataFrame, cols: list[str]) -> str:
        if df.empty:
            return "_No rows._"
        rendered = df[cols].copy()
        for col in rendered.columns:
            if pd.api.types.is_float_dtype(rendered[col]):
                rendered[col] = rendered[col].map(lambda value: "" if pd.isna(value) else f"{value:.3f}")
            else:
                rendered[col] = rendered[col].astype(str)
        widths = {
            col: max(len(str(col)), *(len(value) for value in rendered[col].astype(str)))
            for col in rendered.columns
        }
        header = "| " + " | ".join(str(col).ljust(widths[col]) for col in rendered.columns) + " |"
        separator = "| " + " | ".join("-" * widths[col] for col in rendered.columns) + " |"
        rows = [
            "| " + " | ".join(str(row[col]).ljust(widths[col]) for col in rendered.columns) + " |"
            for _, row in rendered.iterrows()
        ]
        return "\n".join([header, separator, *rows])

    primary_q99_exceedance = aggregate[(aggregate["comparison"] == "primary") & (aggregate["stratum"] == "basin_top1")]
    primary_peak = aggregate[(aggregate["comparison"] == "primary") & (aggregate["stratum"] == "observed_peak_hour")]
    same_q99_exceedance = aggregate[(aggregate["comparison"] == "same_epoch") & (aggregate["stratum"] == "basin_top1")]
    gap_q99_exceedance = gap_aggregate[
        (gap_aggregate["comparison"] == "primary") & (gap_aggregate["stratum"] == "basin_top1")
    ]
    primary_peak_zones = peak_zone_aggregate[peak_zone_aggregate["comparison"].eq("primary")]
    primary_q99_exceedance_zones = q99_exceedance_zone_summary[
        (q99_exceedance_zone_summary["comparison"].eq("primary"))
        & (q99_exceedance_zone_summary["stratum"].eq("basin_top1"))
    ]
    max_q50_diff = sanity["q50_result_max_abs_diff"].max()
    q_order_violations = int(sanity[["q90_lt_q50_rows", "q95_lt_q90_rows", "q99_lt_q95_rows"]].sum().sum())

    lines = [
        "# Subset300 Hydrograph Output Analysis",
        "",
        "This report was generated by `scripts/model/hydrograph/analyze_subset300_hydrograph_outputs.py`.",
        "",
        "## Sanity checks",
        "",
        f"- Required-series files checked: {len(sanity)}",
        f"- Maximum absolute difference between stored `model2_q50_result` and regenerated `q50`: {max_q50_diff:.6g}",
        f"- Quantile ordering violations (`q90 < q50`, `q95 < q90`, `q99 < q95`): {q_order_violations}",
        "",
        "## Primary Epoch, Basin Q99-Exceedance Hours",
        "",
        table(
            primary_q99_exceedance,
            [
                "predictor",
                "mean_coverage_fraction",
                "mean_underestimation_fraction",
                "mean_median_rel_bias_pct",
                "mean_median_under_rel_deficit_pct",
            ],
        ),
        "",
        "## Primary Epoch, Observed Peak Hour",
        "",
        table(
            primary_peak,
            [
                "predictor",
                "mean_coverage_fraction",
                "mean_underestimation_fraction",
                "mean_median_rel_bias_pct",
                "mean_median_under_rel_deficit_pct",
            ],
        ),
        "",
        "## Primary Quantile Zone",
        "",
        "Each observed value is assigned to one of `<=q50`, `q50-q90`, `q90-q95`, `q95-q99`, `>q99` using Model 2 values at the same timestamp. The left panel summarizes basin-specific Q99-exceedance hours (`obs >= Q99`), and the right panel summarizes the exact observed peak hour per basin.",
        "",
        "![Primary quantile-zone share by seed](charts/primary_q99_and_peak_quantile_zone_by_seed.png)",
        "",
        "### Basin Q99-exceedance hours",
        "",
        table(
            primary_q99_exceedance_zones,
            [
                "seed",
                "obs_quantile_zone_label",
                "obs_quantile_interval",
                "n_rows_in_zone",
                "zone_share",
            ],
        ),
        "",
        "### Observed peak hour",
        "",
        table(
            primary_peak_zones,
            [
                "obs_peak_quantile_zone_label",
                "obs_peak_quantile_interval",
                "median_n_peaks_in_zone",
                "median_peak_zone_share",
                "median_median_tau_hat",
                "median_median_q50_q99_position",
            ],
        ),
        "",
        "## Same-Epoch Average, Basin Q99-Exceedance Hours",
        "",
        table(
            same_q99_exceedance,
            [
                "predictor",
                "mean_coverage_fraction",
                "mean_underestimation_fraction",
                "mean_median_rel_bias_pct",
                "mean_median_under_rel_deficit_pct",
            ],
        ),
        "",
        "## Primary Quantile Gap, Basin Q99-Exceedance Hours",
        "",
        table(
            gap_q99_exceedance,
            [
                "mean_median_q90_minus_q50",
                "mean_median_q95_minus_q90",
                "mean_median_q99_minus_q95",
                "mean_median_q99_minus_q50",
                "mean_median_q99_minus_q50_pct_obs",
            ],
        ),
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze subset300 hydrograph required-series outputs.")
    parser.add_argument("--input-dir", type=Path, default=Path("output/model_analysis/quantile_analysis"))
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    input_dir = args.input_dir
    output_dir = args.output_dir or input_dir / "analysis"
    charts_dir = output_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    predictor_rows: list[dict] = []
    gap_rows: list[dict] = []
    peak_frames: list[pd.DataFrame] = []
    q99_exceedance_zone_frames: list[pd.DataFrame] = []
    sanity_rows: list[dict] = []

    for path in _series_files(input_dir):
        seed, epoch = _parse_series_file(path)
        print(f"Analyzing same-epoch seed {seed} epoch {epoch:03d}: {path}", flush=True)
        df = _read_same_epoch(path)
        rows, gaps, peaks = _summarize_frame(
            df,
            comparison="same_epoch",
            seed=seed,
            model1_epoch=epoch,
            model2_epoch=epoch,
        )
        predictor_rows.extend(rows)
        gap_rows.extend(gaps)
        peak_frames.append(peaks)
        sanity_rows.append(_sanity_row(df, path, seed=seed, epoch=epoch))

    for seed, (model1_epoch, model2_epoch) in PRIMARY_EPOCHS.items():
        print(f"Analyzing primary seed {seed}: Model 1 epoch {model1_epoch:03d}, Model 2 epoch {model2_epoch:03d}", flush=True)
        df = _read_primary_pair(input_dir, seed, model1_epoch, model2_epoch)
        rows, gaps, peaks = _summarize_frame(
            df,
            comparison="primary",
            seed=seed,
            model1_epoch=model1_epoch,
            model2_epoch=model2_epoch,
        )
        predictor_rows.extend(rows)
        gap_rows.extend(gaps)
        peak_frames.append(peaks)
        q99_exceedance_zone_frames.append(
            _stratum_zone_rows(
                df,
                comparison="primary",
                stratum="basin_top1",
                seed=seed,
                model1_epoch=model1_epoch,
                model2_epoch=model2_epoch,
            )
        )

    summary = pd.DataFrame(predictor_rows)
    gaps = pd.DataFrame(gap_rows)
    peaks = _add_peak_quantile_zones(pd.concat(peak_frames, ignore_index=True))
    q99_exceedance_zones = _add_peak_quantile_zones(pd.concat(q99_exceedance_zone_frames, ignore_index=True))
    peak_zone_table = _peak_zone_table(peaks)
    peak_zone_summary = _summarize_peak_zones(peaks)
    peak_zone_aggregate = _aggregate_peak_zones(peak_zone_summary)
    q99_exceedance_zone_table = _stratum_zone_table(q99_exceedance_zones)
    q99_exceedance_zone_summary = _summarize_stratum_zones(q99_exceedance_zones)
    sanity = pd.DataFrame(sanity_rows)
    aggregate = _aggregate(summary)
    gap_aggregate = _aggregate_gaps(gaps)

    output_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_dir / "flow_strata_predictor_summary.csv", index=False)
    aggregate.to_csv(output_dir / "flow_strata_predictor_aggregate.csv", index=False)
    gaps.to_csv(output_dir / "quantile_gap_summary.csv", index=False)
    gap_aggregate.to_csv(output_dir / "quantile_gap_aggregate.csv", index=False)
    peaks.to_csv(output_dir / "observed_peak_predictions.csv", index=False)
    peak_zone_table.to_csv(output_dir / "observed_peak_quantile_zone.csv", index=False)
    peak_zone_summary.to_csv(output_dir / "observed_peak_quantile_zone_summary.csv", index=False)
    peak_zone_aggregate.to_csv(output_dir / "observed_peak_quantile_zone_aggregate.csv", index=False)
    q99_exceedance_zone_table.to_csv(output_dir / "primary_q99_exceedance_quantile_zone.csv", index=False)
    q99_exceedance_zone_summary.to_csv(output_dir / "primary_q99_exceedance_quantile_zone_summary.csv", index=False)
    q99_exceedance_zone_table.to_csv(output_dir / "primary_top1_quantile_zone.csv", index=False)
    q99_exceedance_zone_summary.to_csv(output_dir / "primary_top1_quantile_zone_summary.csv", index=False)
    sanity.to_csv(output_dir / "required_series_sanity_checks.csv", index=False)

    _plot_q99_exceedance_underestimation(summary, charts_dir)
    _plot_primary_rel_bias(summary, charts_dir)
    _plot_gap_growth(gaps, charts_dir)
    _plot_primary_peak_zones(peak_zone_summary, q99_exceedance_zone_summary, charts_dir)
    _write_markdown(
        out_path=output_dir / "research_interpretation_summary.md",
        aggregate=aggregate,
        gap_aggregate=gap_aggregate,
        peak_zone_aggregate=peak_zone_aggregate,
        q99_exceedance_zone_summary=q99_exceedance_zone_summary,
        sanity=sanity,
    )

    print(f"Wrote analysis outputs to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
