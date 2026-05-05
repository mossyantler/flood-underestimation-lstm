#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


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
QUANTILE_PREDICTORS = [
    ("q50", "Model 2 q50"),
    ("q90", "Model 2 q90"),
    ("q95", "Model 2 q95"),
    ("q99", "Model 2 q99"),
]
COHORT_ORDER = ["broad_all_38", "natural_8", "broad_non_natural_30"]
COHORT_LABELS = {
    "broad_all_38": "Broad all (38)",
    "natural_8": "Natural (8)",
    "broad_non_natural_30": "Broad non-natural (30)",
}
MODEL_LABELS = {"model1": "Model 1", "model2": "Model 2 q50"}


def _read_basin_file(path: Path) -> list[str]:
    return [line.strip().zfill(8) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _normalize_basin(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(8)


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    out = pd.Series(np.nan, index=numerator.index, dtype=float)
    mask = denominator > 0
    out.loc[mask] = numerator.loc[mask] / denominator.loc[mask]
    return out


def _q25(values: pd.Series) -> float:
    return float(values.quantile(0.25))


def _q75(values: pd.Series) -> float:
    return float(values.quantile(0.75))


def _fmt(value: object, digits: int = 3) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.{digits}f}"
    return str(value)


def _markdown_table(df: pd.DataFrame, columns: list[str], *, digits: int = 3) -> str:
    if df.empty:
        return "_No rows._"
    rendered = df.loc[:, columns].copy()
    for col in rendered.columns:
        rendered[col] = rendered[col].map(lambda value: _fmt(value, digits=digits))
    widths = {
        col: max(len(str(col)), *(len(str(value)) for value in rendered[col].astype(str)))
        for col in rendered.columns
    }
    header = "| " + " | ".join(str(col).ljust(widths[col]) for col in rendered.columns) + " |"
    separator = "| " + " | ".join("-" * widths[col] for col in rendered.columns) + " |"
    rows = [
        "| " + " | ".join(str(row[col]).ljust(widths[col]) for col in rendered.columns) + " |"
        for _, row in rendered.iterrows()
    ]
    return "\n".join([header, separator, *rows])


@dataclass(frozen=True)
class Inputs:
    broad_test_file: Path
    natural_test_file: Path
    basin_metrics_csv: Path
    primary_delta_csv: Path
    required_series_dir: Path
    event_regime_long_csv: Path
    extreme_rain_long_csv: Path


def _membership(inputs: Inputs) -> pd.DataFrame:
    broad = _read_basin_file(inputs.broad_test_file)
    natural = set(_read_basin_file(inputs.natural_test_file))
    rows = []
    for basin in broad:
        rows.append(
            {
                "basin": basin,
                "in_broad_test": True,
                "in_natural_test": basin in natural,
                "exclusive_cohort": "natural_8" if basin in natural else "broad_non_natural_30",
            }
        )
    membership = pd.DataFrame(rows)
    missing = sorted(natural.difference(set(broad)))
    if missing:
        raise ValueError(f"Natural test basins are not all in broad test: {missing}")
    return membership


def _expand_cohorts(df: pd.DataFrame, membership: pd.DataFrame, basin_col: str = "basin") -> pd.DataFrame:
    joined = df.copy()
    joined[basin_col] = _normalize_basin(joined[basin_col])
    member = membership[["basin", "exclusive_cohort", "in_natural_test"]].rename(columns={"basin": "_membership_basin"})
    joined = joined.merge(member, left_on=basin_col, right_on="_membership_basin", how="inner")
    joined = joined.drop(columns=["_membership_basin"])

    broad_all = joined.copy()
    broad_all["cohort"] = "broad_all_38"
    exclusive = joined.copy()
    exclusive["cohort"] = exclusive["exclusive_cohort"]
    out = pd.concat([broad_all, exclusive], ignore_index=True)
    out["cohort_label"] = out["cohort"].map(COHORT_LABELS)
    return out


def _aggregate_seed_rows(df: pd.DataFrame, group_cols: list[str], value_cols: Iterable[str]) -> pd.DataFrame:
    rows = []
    for keys, group in df.groupby(group_cols, dropna=False):
        row = dict(zip(group_cols, keys, strict=True))
        row["n_seed_summaries"] = int(len(group))
        for col in value_cols:
            values = pd.to_numeric(group[col], errors="coerce").dropna()
            row[f"mean_{col}"] = float(values.mean()) if not values.empty else math.nan
            row[f"median_{col}"] = float(values.median()) if not values.empty else math.nan
            row[f"min_{col}"] = float(values.min()) if not values.empty else math.nan
            row[f"max_{col}"] = float(values.max()) if not values.empty else math.nan
        rows.append(row)
    return pd.DataFrame(rows)


def _sort_cohort(df: pd.DataFrame, extra_cols: list[str] | None = None) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["_cohort_order"] = pd.Categorical(out["cohort"], COHORT_ORDER, ordered=True)
    sort_cols = ["_cohort_order", *(extra_cols or [])]
    out = out.sort_values(sort_cols).drop(columns=["_cohort_order"])
    return out.reset_index(drop=True)


def _overall_model_metrics(inputs: Inputs, membership: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    metrics = pd.read_csv(inputs.basin_metrics_csv, dtype={"basin": str})
    metrics["basin"] = _normalize_basin(metrics["basin"])

    primary_rows = []
    for seed, (model1_epoch, model2_epoch) in PRIMARY_EPOCHS.items():
        for model, epoch in [("model1", model1_epoch), ("model2", model2_epoch)]:
            selected = metrics[
                (metrics["split"] == "test")
                & (metrics["model"] == model)
                & (metrics["seed"] == seed)
                & (metrics["epoch"] == epoch)
            ].copy()
            selected["model_label"] = MODEL_LABELS[model]
            primary_rows.append(selected)
    primary = pd.concat(primary_rows, ignore_index=True)
    primary = _expand_cohorts(primary, membership)

    rows = []
    metric_cols = ["NSE", "KGE", "FHV", "Peak-Timing", "Peak-MAPE"]
    for keys, group in primary.groupby(["cohort", "cohort_label", "model", "model_label", "seed", "epoch"], dropna=False):
        row = dict(zip(["cohort", "cohort_label", "model", "model_label", "seed", "epoch"], keys, strict=True))
        row["n_basins"] = int(group["basin"].nunique())
        row["negative_nse_fraction"] = float((group["NSE"] < 0).mean())
        for col in metric_cols:
            out = col.replace("-", "_")
            values = pd.to_numeric(group[col], errors="coerce").dropna()
            row[f"median_{out}"] = float(values.median()) if not values.empty else math.nan
            row[f"mean_{out}"] = float(values.mean()) if not values.empty else math.nan
            row[f"q25_{out}"] = _q25(values) if not values.empty else math.nan
            row[f"q75_{out}"] = _q75(values) if not values.empty else math.nan
        fhv_abs = group["FHV"].abs().dropna()
        row["median_abs_FHV"] = float(fhv_abs.median()) if not fhv_abs.empty else math.nan
        rows.append(row)

    by_seed = _sort_cohort(pd.DataFrame(rows), ["model", "seed"])
    aggregate = _aggregate_seed_rows(
        by_seed,
        ["cohort", "cohort_label", "model", "model_label"],
        [
            "median_NSE",
            "median_KGE",
            "median_FHV",
            "median_abs_FHV",
            "median_Peak_Timing",
            "median_Peak_MAPE",
            "negative_nse_fraction",
        ],
    )
    n_basins = (
        by_seed.groupby(["cohort", "model"], dropna=False)["n_basins"]
        .mean()
        .rename("mean_n_basins")
        .reset_index()
    )
    aggregate = aggregate.merge(n_basins, on=["cohort", "model"], how="left")
    aggregate = _sort_cohort(aggregate, ["model"])
    return by_seed, aggregate


def _overall_deltas(inputs: Inputs, membership: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    deltas = pd.read_csv(inputs.primary_delta_csv, dtype={"basin": str})
    deltas["basin"] = _normalize_basin(deltas["basin"])
    deltas = _expand_cohorts(deltas, membership)
    delta_cols = [
        "delta_NSE",
        "delta_KGE",
        "delta_FHV",
        "abs_FHV_reduction",
        "Peak_Timing_reduction",
        "Peak_MAPE_reduction",
    ]

    rows = []
    for keys, group in deltas.groupby(["cohort", "cohort_label", "seed", "model1_epoch", "model2_epoch"], dropna=False):
        row = dict(zip(["cohort", "cohort_label", "seed", "model1_epoch", "model2_epoch"], keys, strict=True))
        row["n_basins"] = int(group["basin"].nunique())
        for col in delta_cols:
            values = pd.to_numeric(group[col], errors="coerce").dropna()
            row[f"mean_{col}"] = float(values.mean()) if not values.empty else math.nan
            row[f"median_{col}"] = float(values.median()) if not values.empty else math.nan
            row[f"q25_{col}"] = _q25(values) if not values.empty else math.nan
            row[f"q75_{col}"] = _q75(values) if not values.empty else math.nan
            row[f"improved_fraction_{col}"] = float((values > 0).mean()) if not values.empty else math.nan
        rows.append(row)

    by_seed = _sort_cohort(pd.DataFrame(rows), ["seed"])
    aggregate = _aggregate_seed_rows(
        by_seed,
        ["cohort", "cohort_label"],
        [
            "median_delta_NSE",
            "median_delta_KGE",
            "median_delta_FHV",
            "median_abs_FHV_reduction",
            "median_Peak_Timing_reduction",
            "median_Peak_MAPE_reduction",
            "improved_fraction_delta_NSE",
            "improved_fraction_abs_FHV_reduction",
        ],
    )
    n_basins = by_seed.groupby("cohort", dropna=False)["n_basins"].mean().rename("mean_n_basins").reset_index()
    aggregate = aggregate.merge(n_basins, on="cohort", how="left")
    aggregate = _sort_cohort(aggregate)
    return by_seed, aggregate


def _read_primary_pair(required_series_dir: Path, seed: int, model1_epoch: int, model2_epoch: int) -> pd.DataFrame:
    m1_path = required_series_dir / f"seed{seed}" / f"epoch{model1_epoch:03d}_required_series.csv"
    m2_path = required_series_dir / f"seed{seed}" / f"epoch{model2_epoch:03d}_required_series.csv"
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
    left["basin"] = _normalize_basin(left["basin"])
    right["basin"] = _normalize_basin(right["basin"])
    df = left.merge(right, on=["basin", "datetime"], how="inner", validate="one_to_one")
    for col in ["obs", "model1", "q50", "q90", "q95", "q99"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["q99_minus_q50"] = df["q99"] - df["q50"]
    return df


def _predictor_summary(frame: pd.DataFrame, predictor_col: str, predictor_label: str) -> dict[str, float | int | str]:
    obs = frame["obs"]
    pred = frame[predictor_col]
    bias = pred - obs
    rel_bias_pct = _safe_ratio(bias, obs) * 100.0
    under_deficit_pct = _safe_ratio((obs - pred).clip(lower=0), obs) * 100.0
    return {
        "predictor": predictor_col,
        "predictor_label": predictor_label,
        "n_rows": int(len(frame)),
        "n_basins": int(frame["basin"].nunique()),
        "coverage_fraction": float((obs <= pred).mean()),
        "underestimation_fraction": float((pred < obs).mean()),
        "median_rel_bias_pct": float(rel_bias_pct.median(skipna=True)),
        "median_under_rel_deficit_pct": float(under_deficit_pct.median(skipna=True)),
        "median_abs_error": float((pred - obs).abs().median()),
    }


def _high_flow_outputs(inputs: Inputs, membership: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    predictor_rows = []
    gap_rows = []
    for seed, (model1_epoch, model2_epoch) in PRIMARY_EPOCHS.items():
        df = _read_primary_pair(inputs.required_series_dir, seed, model1_epoch, model2_epoch)
        thresholds = df.groupby("basin")["obs"].quantile([0.99, 0.999]).unstack()
        thresholds.columns = ["obs_q99", "obs_q999"]
        df = df.join(thresholds, on="basin")
        df = _expand_cohorts(df, membership)

        for keys, group in df.groupby(["cohort", "cohort_label"], dropna=False):
            cohort, cohort_label = keys
            strata = {
                "basin_top1": group[group["obs"] >= group["obs_q99"]],
                "basin_top0_1": group[group["obs"] >= group["obs_q999"]],
                "observed_peak_hour": group.loc[group.groupby("basin")["obs"].idxmax()],
            }
            for stratum, frame in strata.items():
                if frame.empty:
                    continue
                for predictor, label in PREDICTORS:
                    row = _predictor_summary(frame, predictor, label)
                    row.update(
                        {
                            "cohort": cohort,
                            "cohort_label": cohort_label,
                            "seed": seed,
                            "model1_epoch": model1_epoch,
                            "model2_epoch": model2_epoch,
                            "stratum": stratum,
                        }
                    )
                    predictor_rows.append(row)
                gap_rows.append(
                    {
                        "cohort": cohort,
                        "cohort_label": cohort_label,
                        "seed": seed,
                        "model1_epoch": model1_epoch,
                        "model2_epoch": model2_epoch,
                        "stratum": stratum,
                        "n_rows": int(len(frame)),
                        "n_basins": int(frame["basin"].nunique()),
                        "median_q99_minus_q50": float(frame["q99_minus_q50"].median()),
                        "median_q99_minus_q50_pct_obs": float(
                            (_safe_ratio(frame["q99_minus_q50"], frame["obs"]) * 100.0).median(skipna=True)
                        ),
                    }
                )

    predictor_by_seed = _sort_cohort(pd.DataFrame(predictor_rows), ["stratum", "predictor", "seed"])
    gap_by_seed = _sort_cohort(pd.DataFrame(gap_rows), ["stratum", "seed"])
    predictor_aggregate = _aggregate_seed_rows(
        predictor_by_seed,
        ["cohort", "cohort_label", "stratum", "predictor", "predictor_label"],
        [
            "coverage_fraction",
            "underestimation_fraction",
            "median_rel_bias_pct",
            "median_under_rel_deficit_pct",
            "median_abs_error",
        ],
    )
    gap_aggregate = _aggregate_seed_rows(
        gap_by_seed,
        ["cohort", "cohort_label", "stratum"],
        ["median_q99_minus_q50", "median_q99_minus_q50_pct_obs"],
    )
    predictor_aggregate = _sort_cohort(predictor_aggregate, ["stratum", "predictor"])
    gap_aggregate = _sort_cohort(gap_aggregate, ["stratum"])
    return predictor_by_seed, predictor_aggregate, gap_by_seed, gap_aggregate


def _severity_group(values: pd.Series) -> pd.Series:
    out = pd.Series("other", index=values.index, dtype=object)
    out.loc[values == "high_flow_below_2yr_proxy"] = "high_flow_below_2yr_proxy"
    out.loc[values.astype(str).str.startswith("flood_like_ge_")] = "flood_like_ge2_plus"
    out.loc[values.isin(["flood_like_ge_10yr_proxy", "flood_like_ge_25yr_proxy", "flood_like_ge_50yr_proxy"])] = (
        "flood_like_ge10_plus"
    )
    return out


def _rain_response_group(df: pd.DataFrame) -> pd.Series:
    out = pd.Series("all_events", index=df.index, dtype=object)
    out.loc[df["stress_group"] == "negative_control"] = "negative_control"
    out.loc[df["stress_group"] == "positive_response"] = "positive_response"
    out.loc[df["response_class"].isin(["flood_response_ge2_to_lt25", "flood_response_ge25"])] = "flood_response_ge2_plus"
    out.loc[df["response_class"] == "flood_response_ge25"] = "flood_response_ge25"
    return out


def _paired_event_deltas(
    df: pd.DataFrame,
    *,
    group_col: str,
    metric_prefix: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    id_cols = ["cohort", "cohort_label", "seed", "gauge_id", "event_id"]
    base_cols = [
        *id_cols,
        group_col,
        "obs_peak_underestimated",
        "obs_peak_under_deficit_pct",
        "obs_peak_abs_error",
        "event_nrmse_pct",
        "threshold_exceedance_recall",
        "top_flow_hit_rate",
        "abs_peak_timing_error_hours",
    ]
    base = df[df["predictor"] == "model1"][base_cols].copy()
    base = base.rename(
        columns={
            "obs_peak_underestimated": "model1_underestimated",
            "obs_peak_under_deficit_pct": "model1_under_deficit_pct",
            "obs_peak_abs_error": "model1_abs_error",
            "event_nrmse_pct": "model1_event_nrmse_pct",
            "threshold_exceedance_recall": "model1_threshold_recall",
            "top_flow_hit_rate": "model1_top_flow_hit_rate",
            "abs_peak_timing_error_hours": "model1_abs_peak_timing_error_hours",
        }
    )
    others = df[df["predictor"].isin([name for name, _ in QUANTILE_PREDICTORS])].copy()
    paired = others.merge(base, on=[*id_cols, group_col], how="inner", validate="many_to_one")
    paired["under_deficit_reduction_pct"] = (
        paired["model1_under_deficit_pct"] - paired["obs_peak_under_deficit_pct"]
    )
    paired["underestimation_delta"] = (
        paired["obs_peak_underestimated"].astype(float) - paired["model1_underestimated"].astype(float)
    )
    paired["abs_error_delta"] = paired["obs_peak_abs_error"] - paired["model1_abs_error"]
    paired["event_nrmse_pct_delta"] = paired["event_nrmse_pct"] - paired["model1_event_nrmse_pct"]
    paired["threshold_recall_delta"] = paired["threshold_exceedance_recall"] - paired["model1_threshold_recall"]
    paired["top_flow_hit_rate_delta"] = paired["top_flow_hit_rate"] - paired["model1_top_flow_hit_rate"]
    paired["abs_peak_timing_error_delta"] = (
        paired["abs_peak_timing_error_hours"] - paired["model1_abs_peak_timing_error_hours"]
    )

    rows = []
    for keys, group in paired.groupby(["cohort", "cohort_label", "seed", group_col, "predictor", "predictor_label"], dropna=False):
        cohort, cohort_label, seed, stratum, predictor, predictor_label = keys
        row = {
            "cohort": cohort,
            "cohort_label": cohort_label,
            "seed": seed,
            "stratification": metric_prefix,
            "stratum": stratum,
            "predictor": predictor,
            "predictor_label": predictor_label,
            "n_events": int(group["event_id"].nunique()),
            "n_basins": int(group["gauge_id"].nunique()),
            "median_under_deficit_reduction_pct": float(group["under_deficit_reduction_pct"].median()),
            "mean_underestimation_fraction_delta": float(group["underestimation_delta"].mean()),
            "median_abs_error_delta": float(group["abs_error_delta"].median()),
            "median_event_nrmse_pct_delta": float(group["event_nrmse_pct_delta"].median()),
            "mean_threshold_recall_delta": float(group["threshold_recall_delta"].mean()),
            "mean_top_flow_hit_rate_delta": float(group["top_flow_hit_rate_delta"].mean()),
            "median_abs_peak_timing_error_delta": float(group["abs_peak_timing_error_delta"].median()),
        }
        rows.append(row)

    by_seed = _sort_cohort(pd.DataFrame(rows), ["stratum", "predictor", "seed"])
    aggregate = _aggregate_seed_rows(
        by_seed,
        ["cohort", "cohort_label", "stratification", "stratum", "predictor", "predictor_label"],
        [
            "median_under_deficit_reduction_pct",
            "mean_underestimation_fraction_delta",
            "median_abs_error_delta",
            "median_event_nrmse_pct_delta",
            "mean_threshold_recall_delta",
            "mean_top_flow_hit_rate_delta",
            "median_abs_peak_timing_error_delta",
        ],
    )
    aggregate["mean_n_events"] = (
        by_seed.groupby(["cohort", "stratum", "predictor"])["n_events"]
        .mean()
        .reindex(pd.MultiIndex.from_frame(aggregate[["cohort", "stratum", "predictor"]]))
        .to_numpy()
    )
    aggregate = _sort_cohort(aggregate, ["stratum", "predictor"])
    return by_seed, aggregate


def _event_regime_outputs(inputs: Inputs, membership: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(inputs.event_regime_long_csv, dtype={"gauge_id": str})
    df["gauge_id"] = _normalize_basin(df["gauge_id"])
    df = _expand_cohorts(df, membership, basin_col="gauge_id")
    df["event_severity_group"] = _severity_group(df["flood_relevance_tier"])
    all_events = df.copy()
    all_events["event_severity_group"] = "all_events"
    grouped = pd.concat([all_events, df], ignore_index=True)
    return _paired_event_deltas(grouped, group_col="event_severity_group", metric_prefix="event_severity")


def _extreme_rain_outputs(inputs: Inputs, membership: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(inputs.extreme_rain_long_csv, dtype={"gauge_id": str})
    df["gauge_id"] = _normalize_basin(df["gauge_id"])
    df = _expand_cohorts(df, membership, basin_col="gauge_id")
    df["rain_response_group"] = _rain_response_group(df)
    all_events = df.copy()
    all_events["rain_response_group"] = "all_events"
    grouped = pd.concat([all_events, df], ignore_index=True)
    return _paired_event_deltas(grouped, group_col="rain_response_group", metric_prefix="rain_response")


def _plot_overall_delta(aggregate: pd.DataFrame, output_path: Path) -> None:
    data = aggregate.set_index("cohort").reindex(COHORT_ORDER).reset_index()
    metrics = [
        ("mean_median_delta_NSE", "NSE delta"),
        ("mean_median_abs_FHV_reduction", "|FHV| reduction"),
        ("mean_median_Peak_Timing_reduction", "Peak timing reduction"),
        ("mean_median_Peak_MAPE_reduction", "Peak MAPE reduction"),
    ]
    fig, axes = plt.subplots(1, 4, figsize=(15, 4.2))
    colors = ["#4f6f52", "#c4512d", "#5b6f95"]
    for ax, (col, title) in zip(axes, metrics, strict=True):
        ax.bar(data["cohort"].map(COHORT_LABELS), data[col], color=colors)
        ax.axhline(0, color="#333333", linewidth=0.8)
        ax.set_title(title)
        ax.tick_params(axis="x", labelrotation=25)
        ax.grid(True, axis="y", alpha=0.25)
    fig.suptitle("Primary epoch Model 2 q50 vs Model 1, seed-median aggregate")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _plot_high_flow(aggregate: pd.DataFrame, output_path: Path) -> None:
    data = aggregate[
        (aggregate["stratum"] == "basin_top1")
        & (aggregate["predictor_label"].isin(["Model 1", "Model 2 q50", "Model 2 q95", "Model 2 q99"]))
    ].copy()
    data["_cohort_order"] = pd.Categorical(data["cohort"], COHORT_ORDER, ordered=True)
    data = data.sort_values(["_cohort_order", "predictor"])
    predictors = ["Model 1", "Model 2 q50", "Model 2 q95", "Model 2 q99"]
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), sharex=True)
    width = 0.18
    x = np.arange(len(COHORT_ORDER))
    palette = {
        "Model 1": "#2563eb",
        "Model 2 q50": "#b91c1c",
        "Model 2 q95": "#e97316",
        "Model 2 q99": "#c08400",
    }
    for i, predictor in enumerate(predictors):
        subset = data[data["predictor_label"] == predictor].set_index("cohort").reindex(COHORT_ORDER)
        axes[0].bar(x + (i - 1.5) * width, subset["mean_underestimation_fraction"], width, label=predictor, color=palette[predictor])
        axes[1].bar(x + (i - 1.5) * width, subset["mean_median_rel_bias_pct"], width, label=predictor, color=palette[predictor])
    axes[0].set_ylabel("Underestimation fraction")
    axes[1].set_ylabel("Median relative bias (%)")
    axes[1].axhline(0, color="#333333", linewidth=0.8)
    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels([COHORT_LABELS[c] for c in COHORT_ORDER], rotation=20, ha="right")
        ax.grid(True, axis="y", alpha=0.25)
    axes[1].legend(loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False)
    fig.suptitle("Primary basin top 1% hours")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _plot_event_delta(aggregate: pd.DataFrame, output_path: Path, *, stratum: str, title: str) -> None:
    data = aggregate[
        (aggregate["stratum"] == stratum)
        & (aggregate["predictor_label"].isin(["Model 2 q50", "Model 2 q95", "Model 2 q99"]))
    ].copy()
    predictors = ["Model 2 q50", "Model 2 q95", "Model 2 q99"]
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    x = np.arange(len(COHORT_ORDER))
    width = 0.22
    palette = {"Model 2 q50": "#b91c1c", "Model 2 q95": "#e97316", "Model 2 q99": "#c08400"}
    for i, predictor in enumerate(predictors):
        subset = data[data["predictor_label"] == predictor].set_index("cohort").reindex(COHORT_ORDER)
        ax.bar(
            x + (i - 1) * width,
            subset["mean_median_under_deficit_reduction_pct"],
            width,
            label=predictor,
            color=palette[predictor],
        )
    ax.axhline(0, color="#333333", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([COHORT_LABELS[c] for c in COHORT_ORDER], rotation=20, ha="right")
    ax.set_ylabel("Median under-deficit reduction (percentage points)")
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _write_report(
    report_path: Path,
    membership: pd.DataFrame,
    overall_delta: pd.DataFrame,
    high_flow: pd.DataFrame,
    gaps: pd.DataFrame,
    event_delta: pd.DataFrame,
    rain_delta: pd.DataFrame,
) -> None:
    basin_counts = (
        pd.DataFrame(
            [
                {"cohort": "broad_all_38", "cohort_label": COHORT_LABELS["broad_all_38"], "n_basins": 38},
                {
                    "cohort": "natural_8",
                    "cohort_label": COHORT_LABELS["natural_8"],
                    "n_basins": int(membership["in_natural_test"].sum()),
                },
                {
                    "cohort": "broad_non_natural_30",
                    "cohort_label": COHORT_LABELS["broad_non_natural_30"],
                    "n_basins": int((~membership["in_natural_test"]).sum()),
                },
            ]
        )
    )
    top1 = high_flow[
        (high_flow["stratum"] == "basin_top1")
        & (high_flow["predictor_label"].isin(["Model 1", "Model 2 q50", "Model 2 q95", "Model 2 q99"]))
    ].copy()
    event_all = event_delta[
        (event_delta["stratum"] == "all_events")
        & (event_delta["predictor_label"].isin(["Model 2 q50", "Model 2 q95", "Model 2 q99"]))
    ].copy()
    rain_response = rain_delta[
        (rain_delta["stratum"] == "flood_response_ge2_plus")
        & (rain_delta["predictor_label"].isin(["Model 2 q50", "Model 2 q95", "Model 2 q99"]))
    ].copy()
    top1_q99 = top1[top1["predictor_label"] == "Model 2 q99"].set_index("cohort")
    natural_q99_under = top1_q99.loc["natural_8", "mean_underestimation_fraction"]
    broad_q99_under = top1_q99.loc["broad_all_38", "mean_underestimation_fraction"]
    non_q99_under = top1_q99.loc["broad_non_natural_30", "mean_underestimation_fraction"]
    gap_top1 = gaps[gaps["stratum"] == "basin_top1"].copy()

    lines = [
        "# Natural vs Broad Comparison",
        "",
        "이 분석은 기존 subset300 DRBC test 결과 38개 basin을 재학습 없이 cohort로 다시 나누어 계산했다.",
        "Natural 8개 basin은 Broad 38개의 부분집합이므로, 표에는 `broad_all_38`, `natural_8`, `broad_non_natural_30`을 함께 둔다. Natural과 독립적인 비교를 볼 때는 `broad_non_natural_30`을 기준으로 읽는 것이 더 직접적이다.",
        "",
        "## Basin Counts",
        "",
        _markdown_table(basin_counts, ["cohort_label", "n_basins"], digits=0),
        "",
        "## Primary Overall Delta",
        "",
        "아래 값은 validation으로 고른 primary checkpoint에서 seed별 basin-median delta를 먼저 계산한 뒤, seed 111/222/444 평균으로 집계한 것이다. NSE/KGE는 `Model 2 q50 - Model 1`, error reduction 계열은 양수일수록 Model 2 q50이 좋다.",
        "",
        _markdown_table(
            overall_delta,
            [
                "cohort_label",
                "mean_median_delta_NSE",
                "mean_median_delta_KGE",
                "mean_median_abs_FHV_reduction",
                "mean_median_Peak_Timing_reduction",
                "mean_median_Peak_MAPE_reduction",
                "mean_improved_fraction_delta_NSE",
            ],
        ),
        "",
        "## Primary Top 1% Flow",
        "",
        "상위 1% 유량 시간대에서는 Natural 8개에서도 upper quantile의 underestimation 완화 방향이 유지된다. `q99`의 underestimation fraction은 Broad 전체에서 "
        f"{broad_q99_under:.3f}, Natural에서 {natural_q99_under:.3f}, Natural을 제외한 Broad 30개에서 {non_q99_under:.3f}이다.",
        "",
        _markdown_table(
            top1,
            [
                "cohort_label",
                "predictor_label",
                "mean_underestimation_fraction",
                "mean_median_rel_bias_pct",
                "mean_median_under_rel_deficit_pct",
            ],
        ),
        "",
        "## Quantile Gap",
        "",
        "Natural subset에서도 `q99 - q50` gap은 high-flow에서 충분히 열린다. 다만 Natural은 8개 basin이라 basin composition에 민감하므로 calibration 주장보다는 upper-tail decision output의 robustness 신호로 읽는 편이 안전하다.",
        "",
        _markdown_table(
            gap_top1,
            [
                "cohort_label",
                "mean_median_q99_minus_q50",
                "mean_median_q99_minus_q50_pct_obs",
            ],
        ),
        "",
        "## Event Windows",
        "",
        "Observed high-flow event window 기준으로도 `q95/q99`는 Natural subset에서 Model 1 대비 peak under-deficit을 줄이는 방향이다. `q50`은 Natural과 Broad 모두에서 tail 보정 출력으로 쓰기 어렵다.",
        "",
        _markdown_table(
            event_all,
            [
                "cohort_label",
                "predictor_label",
                "mean_n_events",
                "mean_median_under_deficit_reduction_pct",
                "mean_mean_underestimation_fraction_delta",
                "mean_mean_threshold_recall_delta",
            ],
        ),
        "",
        "## Extreme-Rain Stress",
        "",
        "`drbc_historical_stress`는 1980-2024 historical window를 포함하므로 independent test claim에는 쓰지 않는다. 여기서는 Natural subset에서 stress response 방향이 크게 뒤집히는지 보는 보조 진단으로만 사용한다.",
        "",
        _markdown_table(
            rain_response,
            [
                "cohort_label",
                "predictor_label",
                "mean_n_events",
                "mean_median_under_deficit_reduction_pct",
                "mean_mean_underestimation_fraction_delta",
                "mean_mean_threshold_recall_delta",
            ],
        ),
        "",
        "## Interpretation",
        "",
        "핵심 결론은 Broad 38개에서 보인 upper quantile의 peak underestimation 완화가 Natural 8개로 필터링해도 사라지지 않는다는 것이다. 다만 Natural 표본은 작아서 p-value나 강한 일반화 주장을 붙이기에는 부족하고, 본문에서는 robustness check로 제한해서 쓰는 것이 맞다.",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def _write_readme(output_dir: Path) -> None:
    readme = output_dir / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# Natural Broad Comparison",
                "",
                "기존 subset300 DRBC test 결과 38개 basin을 `natural_8`, `broad_non_natural_30`, `broad_all_38` cohort로 다시 집계한 model-analysis 산출물이다.",
                "",
                "- `tables/`: cohort별 primary overall metric, high-flow quantile, event-window, extreme-rain stress 집계표",
                "- `figures/`: 주요 delta와 high-flow underestimation 비교 chart",
                "- `report/`: 해석용 markdown report",
                "- `metadata/`: 입력 경로와 basin count provenance",
                "",
                "Natural은 Broad 38개의 부분집합이다. 따라서 Natural과 독립적인 contrast를 볼 때는 `broad_non_natural_30`을 사용하고, main result와의 연결은 `broad_all_38`을 사용한다.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def analyze(inputs: Inputs, output_dir: Path) -> dict[str, str]:
    tables_dir = output_dir / "tables"
    figures_dir = output_dir / "figures"
    report_dir = output_dir / "report"
    metadata_dir = output_dir / "metadata"
    for directory in [tables_dir, figures_dir, report_dir, metadata_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    membership = _membership(inputs)
    model_by_seed, model_aggregate = _overall_model_metrics(inputs, membership)
    delta_by_seed, delta_aggregate = _overall_deltas(inputs, membership)
    high_by_seed, high_aggregate, gap_by_seed, gap_aggregate = _high_flow_outputs(inputs, membership)
    event_by_seed, event_aggregate = _event_regime_outputs(inputs, membership)
    rain_by_seed, rain_aggregate = _extreme_rain_outputs(inputs, membership)

    paths = {
        "readme": output_dir / "README.md",
        "basin_membership": tables_dir / "basin_membership.csv",
        "primary_model_metric_by_cohort_seed": tables_dir / "primary_model_metric_by_cohort_seed.csv",
        "primary_model_metric_by_cohort_aggregate": tables_dir / "primary_model_metric_by_cohort_aggregate.csv",
        "primary_overall_delta_by_cohort_seed": tables_dir / "primary_overall_delta_by_cohort_seed.csv",
        "primary_overall_delta_by_cohort_aggregate": tables_dir / "primary_overall_delta_by_cohort_aggregate.csv",
        "primary_high_flow_predictor_by_cohort_seed": tables_dir / "primary_high_flow_predictor_by_cohort_seed.csv",
        "primary_high_flow_predictor_by_cohort_aggregate": tables_dir / "primary_high_flow_predictor_by_cohort_aggregate.csv",
        "primary_quantile_gap_by_cohort_seed": tables_dir / "primary_quantile_gap_by_cohort_seed.csv",
        "primary_quantile_gap_by_cohort_aggregate": tables_dir / "primary_quantile_gap_by_cohort_aggregate.csv",
        "event_regime_delta_by_cohort_seed": tables_dir / "event_regime_delta_by_cohort_seed.csv",
        "event_regime_delta_by_cohort_aggregate": tables_dir / "event_regime_delta_by_cohort_aggregate.csv",
        "extreme_rain_delta_by_cohort_seed": tables_dir / "extreme_rain_delta_by_cohort_seed.csv",
        "extreme_rain_delta_by_cohort_aggregate": tables_dir / "extreme_rain_delta_by_cohort_aggregate.csv",
        "overall_delta_figure": figures_dir / "primary_overall_delta_by_cohort.png",
        "high_flow_figure": figures_dir / "primary_top1_underestimation_by_cohort.png",
        "event_figure": figures_dir / "event_under_deficit_reduction_by_cohort.png",
        "rain_figure": figures_dir / "extreme_rain_under_deficit_reduction_by_cohort.png",
        "report": report_dir / "natural_broad_comparison_report.md",
        "metadata": metadata_dir / "analysis_metadata.json",
    }

    membership.to_csv(paths["basin_membership"], index=False)
    model_by_seed.to_csv(paths["primary_model_metric_by_cohort_seed"], index=False)
    model_aggregate.to_csv(paths["primary_model_metric_by_cohort_aggregate"], index=False)
    delta_by_seed.to_csv(paths["primary_overall_delta_by_cohort_seed"], index=False)
    delta_aggregate.to_csv(paths["primary_overall_delta_by_cohort_aggregate"], index=False)
    high_by_seed.to_csv(paths["primary_high_flow_predictor_by_cohort_seed"], index=False)
    high_aggregate.to_csv(paths["primary_high_flow_predictor_by_cohort_aggregate"], index=False)
    gap_by_seed.to_csv(paths["primary_quantile_gap_by_cohort_seed"], index=False)
    gap_aggregate.to_csv(paths["primary_quantile_gap_by_cohort_aggregate"], index=False)
    event_by_seed.to_csv(paths["event_regime_delta_by_cohort_seed"], index=False)
    event_aggregate.to_csv(paths["event_regime_delta_by_cohort_aggregate"], index=False)
    rain_by_seed.to_csv(paths["extreme_rain_delta_by_cohort_seed"], index=False)
    rain_aggregate.to_csv(paths["extreme_rain_delta_by_cohort_aggregate"], index=False)

    _plot_overall_delta(delta_aggregate, paths["overall_delta_figure"])
    _plot_high_flow(high_aggregate, paths["high_flow_figure"])
    _plot_event_delta(
        event_aggregate,
        paths["event_figure"],
        stratum="all_events",
        title="Observed high-flow events, all event windows",
    )
    _plot_event_delta(
        rain_aggregate,
        paths["rain_figure"],
        stratum="flood_response_ge2_plus",
        title="Extreme-rain historical stress, flood-response events",
    )
    _write_report(
        paths["report"],
        membership,
        delta_aggregate,
        high_aggregate,
        gap_aggregate,
        event_aggregate,
        rain_aggregate,
    )
    _write_readme(output_dir)

    metadata = {
        "analysis": "natural_broad_comparison",
        "output_dir": str(output_dir),
        "inputs": {key: str(value) for key, value in inputs.__dict__.items()},
        "cohorts": {
            "broad_all_38": int(len(membership)),
            "natural_8": int(membership["in_natural_test"].sum()),
            "broad_non_natural_30": int((~membership["in_natural_test"]).sum()),
        },
        "primary_epochs": {
            f"seed{seed}": {"model1_epoch": m1, "model2_epoch": m2}
            for seed, (m1, m2) in PRIMARY_EPOCHS.items()
        },
        "outputs": {key: str(path) for key, path in paths.items()},
        "notes": [
            "Natural test basins are a subset of the broad 38 DRBC test basins.",
            "broad_non_natural_30 is provided for an exclusive Natural-vs-rest comparison.",
            "Extreme-rain stress rows use historical 1980-2024 windows and are not an independent temporal test claim.",
        ],
    }
    paths["metadata"].write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return {key: str(path) for key, path in paths.items()}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare Natural and Broad DRBC test cohorts using existing subset300 Model 1/2 analysis outputs."
    )
    parser.add_argument("--broad-test-file", type=Path, default=Path("configs/basin_splits/drbc_holdout_test_drbc_quality.txt"))
    parser.add_argument(
        "--natural-test-file",
        type=Path,
        default=Path("configs/basin_splits/drbc_holdout_test_drbc_quality_natural.txt"),
    )
    parser.add_argument(
        "--basin-metrics-csv",
        type=Path,
        default=Path("output/model_analysis/overall_analysis/epoch_sensitivity/tables/basin_metrics.csv"),
    )
    parser.add_argument(
        "--primary-delta-csv",
        type=Path,
        default=Path("output/model_analysis/overall_analysis/main_comparison/tables/primary_epoch_basin_deltas.csv"),
    )
    parser.add_argument(
        "--required-series-dir",
        type=Path,
        default=Path("output/model_analysis/quantile_analysis/required_series"),
    )
    parser.add_argument(
        "--event-regime-long-csv",
        type=Path,
        default=Path("output/model_analysis/quantile_analysis/event_regime_analysis/event_regime_error_table_long.csv"),
    )
    parser.add_argument(
        "--extreme-rain-long-csv",
        type=Path,
        default=Path("output/model_analysis/extreme_rain/primary/analysis/extreme_rain_stress_error_table_long.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/model_analysis/natural_broad_comparison"),
    )
    args = parser.parse_args()

    inputs = Inputs(
        broad_test_file=args.broad_test_file,
        natural_test_file=args.natural_test_file,
        basin_metrics_csv=args.basin_metrics_csv,
        primary_delta_csv=args.primary_delta_csv,
        required_series_dir=args.required_series_dir,
        event_regime_long_csv=args.event_regime_long_csv,
        extreme_rain_long_csv=args.extreme_rain_long_csv,
    )
    paths = analyze(inputs, args.output_dir)
    print("Wrote natural/broad comparison outputs:")
    for key, path in paths.items():
        print(f"- {key}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
