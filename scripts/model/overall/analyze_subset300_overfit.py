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
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OVERALL = REPO_ROOT / "output/model_analysis/overall_analysis"
DEFAULT_MAIN = DEFAULT_OVERALL / "main_comparison"
DEFAULT_EPOCH_SUMMARY = DEFAULT_OVERALL / "epoch_sensitivity/tables/epoch_metric_summary.csv"
DEFAULT_MANIFEST = DEFAULT_OVERALL / "run_records/metric_file_manifest.csv"
DEFAULT_OUTPUT = DEFAULT_OVERALL / "overfit_analysis"
OFFICIAL_SEEDS = [111, 222, 444]
MODEL_LABELS = {"model1": "Model 1", "model2": "Model 2"}
MODEL_COLORS = {"model1": "#fca5a5", "model2": "#93c5fd"}
SPLIT_COLORS = {"validation": "#059669", "test": "#dc2626"}
PREDICTOR_ORDER = ["Model 1", "Model 2 q50", "Model 2 q95", "Model 2 q99"]
PREDICTOR_COLORS = {
    "Model 1": "#374151",
    "Model 2 q50": "#2563eb",
    "Model 2 q95": "#059669",
    "Model 2 q99": "#dc2626",
}
METRIC_SPECS = [
    ("median_NSE", "NSE", "max"),
    ("median_KGE", "KGE", "max"),
    ("median_abs_FHV", "abs(FHV)", "min"),
    ("median_Peak_Timing", "Peak timing", "min"),
    ("median_Peak_MAPE", "Peak MAPE", "min"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze subset300 overfitting diagnostics.")
    parser.add_argument("--overall-dir", type=Path, default=DEFAULT_OVERALL)
    parser.add_argument("--main-comparison-dir", type=Path, default=DEFAULT_MAIN)
    parser.add_argument("--epoch-summary", type=Path, default=DEFAULT_EPOCH_SUMMARY)
    parser.add_argument("--metric-manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def fmt(value: Any, digits: int = 3) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{float(value):.{digits}f}"


def pct(value: Any, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{float(value):.{digits}f}%"


def markdown_image(path: Path, report_path: Path, alt_text: str) -> str:
    rel = os.path.relpath(path, report_path.parent)
    return f"![{alt_text}]({Path(rel).as_posix()})"


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def primary_epoch_map(primary: pd.DataFrame) -> dict[tuple[str, int], int]:
    out: dict[tuple[str, int], int] = {}
    if primary.empty:
        return out
    for row in primary.itertuples(index=False):
        out[(str(row.model), int(row.seed))] = int(row.epoch)
    return out


def run_dirs_from_manifest(manifest: pd.DataFrame) -> pd.DataFrame:
    selected = manifest[
        manifest["selected"].astype(str).str.lower().eq("true")
        & manifest["model"].isin(["model1", "model2"])
        & manifest["seed"].isin(OFFICIAL_SEEDS)
    ].copy()
    rows = []
    for (model, seed, run_name), _ in selected.groupby(["model", "seed", "run_name"]):
        rows.append(
            {
                "model": model,
                "model_label": MODEL_LABELS[model],
                "seed": int(seed),
                "run_name": run_name,
                "run_dir": REPO_ROOT / "runs/subset_comparison" / str(run_name),
            }
        )
    return pd.DataFrame(rows).sort_values(["model", "seed"]).reset_index(drop=True)


TRAIN_RE = re.compile(r"Epoch\s+(\d+)\s+average loss:\s+avg_loss:\s+([0-9.eE+-]+)")
VAL_RE = re.compile(
    r"Epoch\s+(\d+)\s+average validation loss:\s+([0-9.eE+-]+)\s+--\s+"
    r"Median validation metrics:\s+avg_loss:\s+([0-9.eE+-]+),\s+"
    r"NSE:\s+([0-9.eE+-]+),\s+KGE:\s+([0-9.eE+-]+),\s+FHV:\s+([0-9.eE+-]+),\s+"
    r"Peak-Timing:\s+([0-9.eE+-]+),\s+Peak-MAPE:\s+([0-9.eE+-]+)"
)


def parse_loss_logs(run_dirs: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in run_dirs.itertuples(index=False):
        log_paths = [Path(row.run_dir) / "output.log"]
        log_paths.extend(sorted(Path(row.run_dir).glob("continue_training_from_epoch*/output.log")))
        for log_path in log_paths:
            if not log_path.exists():
                continue
            source = "top_level" if log_path.parent == Path(row.run_dir) else log_path.parent.name
            for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                val_match = VAL_RE.search(line)
                if val_match:
                    epoch = int(val_match.group(1))
                    rows.append(
                        {
                            "model": row.model,
                            "model_label": row.model_label,
                            "seed": row.seed,
                            "run_name": row.run_name,
                            "epoch": epoch,
                            "loss_type": "validation",
                            "avg_loss": float(val_match.group(2)),
                            "source_log": str(log_path),
                            "source": source,
                            "median_NSE": float(val_match.group(4)),
                            "median_KGE": float(val_match.group(5)),
                            "median_FHV": float(val_match.group(6)),
                            "median_Peak_Timing": float(val_match.group(7)),
                            "median_Peak_MAPE": float(val_match.group(8)),
                        }
                    )
                    continue
                train_match = TRAIN_RE.search(line)
                if train_match:
                    rows.append(
                        {
                            "model": row.model,
                            "model_label": row.model_label,
                            "seed": row.seed,
                            "run_name": row.run_name,
                            "epoch": int(train_match.group(1)),
                            "loss_type": "train",
                            "avg_loss": float(train_match.group(2)),
                            "source_log": str(log_path),
                            "source": source,
                        }
                    )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    # Continuation logs can duplicate validation files already copied to the top-level run dir.
    df = (
        df.sort_values(["model", "seed", "epoch", "loss_type", "source"])
        .drop_duplicates(["model", "seed", "epoch", "loss_type"], keep="last")
        .sort_values(["model", "seed", "loss_type", "epoch"])
        .reset_index(drop=True)
    )
    return df


def build_loss_diagnostics(losses: pd.DataFrame, primary_epochs: dict[tuple[str, int], int]) -> pd.DataFrame:
    rows = []
    if losses.empty:
        return pd.DataFrame()
    for (model, seed), sub in losses.groupby(["model", "seed"]):
        train = sub[sub["loss_type"].eq("train")].sort_values("epoch")
        val = sub[sub["loss_type"].eq("validation")].sort_values("epoch")
        if train.empty or val.empty:
            continue
        selected_epoch = primary_epochs.get((str(model), int(seed)))
        first_train = float(train["avg_loss"].iloc[0])
        final_train = float(train["avg_loss"].iloc[-1])
        first_val = float(val["avg_loss"].iloc[0])
        final_val = float(val["avg_loss"].iloc[-1])
        min_val_idx = val["avg_loss"].idxmin()
        min_val = float(val.loc[min_val_idx, "avg_loss"])
        best_val_loss_epoch = int(val.loc[min_val_idx, "epoch"])
        primary_val = np.nan
        if selected_epoch in set(val["epoch"]):
            primary_val = float(val[val["epoch"].eq(selected_epoch)]["avg_loss"].iloc[0])
        train_reduction = (first_train - final_train) / first_train if first_train else np.nan
        val_final_vs_min_pct = (final_val / min_val - 1.0) * 100 if min_val else np.nan
        val_primary_vs_min_pct = (primary_val / min_val - 1.0) * 100 if min_val and not pd.isna(primary_val) else np.nan
        if val_final_vs_min_pct >= 10:
            flag = "moderate_loss_overfit_signal"
        elif val_final_vs_min_pct >= 5:
            flag = "mild_loss_overfit_signal"
        else:
            flag = "no_clear_loss_overfit"
        rows.append(
            {
                "model": model,
                "model_label": MODEL_LABELS[str(model)],
                "seed": int(seed),
                "selected_primary_epoch": selected_epoch,
                "first_train_loss": first_train,
                "final_train_loss": final_train,
                "train_loss_reduction_fraction": train_reduction,
                "first_validation_loss": first_val,
                "min_validation_loss": min_val,
                "best_validation_loss_epoch": best_val_loss_epoch,
                "primary_validation_loss": primary_val,
                "final_validation_loss": final_val,
                "final_vs_min_validation_loss_pct": val_final_vs_min_pct,
                "primary_vs_min_validation_loss_pct": val_primary_vs_min_pct,
                "n_train_epochs": int(train["epoch"].nunique()),
                "n_validation_epochs": int(val["epoch"].nunique()),
                "diagnostic_flag": flag,
            }
        )
    return pd.DataFrame(rows).sort_values(["model", "seed"]).reset_index(drop=True)


def rank_selected_epoch(values: pd.DataFrame, metric: str, direction: str, epoch: int | None) -> int | None:
    if epoch is None or values.empty:
        return None
    ascending = direction == "min"
    ranks = values.sort_values(metric, ascending=ascending).reset_index(drop=True)
    matches = ranks.index[ranks["epoch"].eq(epoch)].tolist()
    if not matches:
        return None
    return int(matches[0] + 1)


def metric_gap(selected: float, best: float, direction: str) -> float:
    if direction == "max":
        return float(best - selected)
    return float(selected - best)


def spearman_corr(left: pd.Series, right: pd.Series) -> float:
    valid = pd.concat([left, right], axis=1).dropna()
    if len(valid) < 2:
        return np.nan
    ranks = valid.rank(method="average")
    return float(ranks.iloc[:, 0].corr(ranks.iloc[:, 1], method="pearson"))


def build_epoch_selection_diagnostics(
    epoch_summary: pd.DataFrame, primary_epochs: dict[tuple[str, int], int]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if epoch_summary.empty:
        return pd.DataFrame(), pd.DataFrame()
    epoch_summary = epoch_summary[
        epoch_summary["model"].isin(["model1", "model2"])
        & epoch_summary["seed"].isin(OFFICIAL_SEEDS)
        & epoch_summary["split"].isin(["validation", "test"])
    ].copy()
    rows = []
    corr_rows = []
    for (model, seed), sub in epoch_summary.groupby(["model", "seed"]):
        selected_epoch = primary_epochs.get((str(model), int(seed)))
        val = sub[sub["split"].eq("validation")].sort_values("epoch")
        test = sub[sub["split"].eq("test")].sort_values("epoch")
        for metric, label, direction in METRIC_SPECS:
            if metric not in val.columns or metric not in test.columns:
                continue
            best_val_idx = val[metric].idxmax() if direction == "max" else val[metric].idxmin()
            best_test_idx = test[metric].idxmax() if direction == "max" else test[metric].idxmin()
            best_val_epoch = int(val.loc[best_val_idx, "epoch"])
            best_test_epoch = int(test.loc[best_test_idx, "epoch"])
            selected_val = np.nan
            selected_test = np.nan
            if selected_epoch in set(val["epoch"]):
                selected_val = float(val[val["epoch"].eq(selected_epoch)][metric].iloc[0])
            if selected_epoch in set(test["epoch"]):
                selected_test = float(test[test["epoch"].eq(selected_epoch)][metric].iloc[0])
            best_val = float(val.loc[best_val_idx, metric])
            best_test = float(test.loc[best_test_idx, metric])
            rows.append(
                {
                    "model": model,
                    "model_label": MODEL_LABELS[str(model)],
                    "seed": int(seed),
                    "metric": metric,
                    "metric_label": label,
                    "direction": direction,
                    "selected_primary_epoch": selected_epoch,
                    "best_validation_epoch": best_val_epoch,
                    "best_test_epoch": best_test_epoch,
                    "selected_validation_value": selected_val,
                    "best_validation_value": best_val,
                    "selected_test_value": selected_test,
                    "best_test_value": best_test,
                    "validation_gap_from_best": metric_gap(selected_val, best_val, direction)
                    if not pd.isna(selected_val)
                    else np.nan,
                    "test_oracle_gap": metric_gap(selected_test, best_test, direction)
                    if not pd.isna(selected_test)
                    else np.nan,
                    "selected_validation_rank": rank_selected_epoch(val, metric, direction, selected_epoch),
                    "selected_test_rank": rank_selected_epoch(test, metric, direction, selected_epoch),
                    "selected_equals_validation_best": selected_epoch == best_val_epoch,
                    "selected_equals_test_best": selected_epoch == best_test_epoch,
                }
            )
            paired = val[["epoch", metric]].merge(
                test[["epoch", metric]], on="epoch", suffixes=("_validation", "_test"), how="inner"
            )
            corr = spearman_corr(paired[f"{metric}_validation"], paired[f"{metric}_test"])
            corr_rows.append(
                {
                    "model": model,
                    "model_label": MODEL_LABELS[str(model)],
                    "seed": int(seed),
                    "metric": metric,
                    "metric_label": label,
                    "n_epochs": int(len(paired)),
                    "spearman_validation_test": corr,
                }
            )
    return (
        pd.DataFrame(rows).sort_values(["metric", "model", "seed"]).reset_index(drop=True),
        pd.DataFrame(corr_rows).sort_values(["metric", "model", "seed"]).reset_index(drop=True),
    )


def build_oracle_gap_summary(selection: pd.DataFrame) -> pd.DataFrame:
    if selection.empty:
        return pd.DataFrame()
    rows = []
    for (model, metric), sub in selection.groupby(["model", "metric"]):
        rows.append(
            {
                "model": model,
                "model_label": MODEL_LABELS[str(model)],
                "metric": metric,
                "metric_label": str(sub["metric_label"].iloc[0]),
                "median_test_oracle_gap": float(sub["test_oracle_gap"].median()),
                "max_test_oracle_gap": float(sub["test_oracle_gap"].max()),
                "primary_was_test_best_seed_count": int(sub["selected_equals_test_best"].sum()),
                "primary_was_validation_best_seed_count": int(sub["selected_equals_validation_best"].sum()),
                "n_seeds": int(sub["seed"].nunique()),
            }
        )
    return pd.DataFrame(rows).sort_values(["metric", "model"]).reset_index(drop=True)


def build_quantile_tradeoff(high_flow: pd.DataFrame, stress: pd.DataFrame) -> pd.DataFrame:
    if high_flow.empty or stress.empty:
        return pd.DataFrame()
    h = high_flow.pivot(index="predictor", columns="stratum")
    s = stress.pivot(index="predictor_label", columns="response_class")
    rows = []
    for predictor in PREDICTOR_ORDER:
        if predictor not in h.index or predictor not in s.index:
            continue
        rows.append(
            {
                "predictor": predictor,
                "basin_top1_underestimation_fraction": h.loc[
                    predictor, ("median_underestimation_fraction", "basin_top1")
                ],
                "basin_top1_median_relative_bias_pct": h.loc[
                    predictor, ("median_median_rel_bias_pct", "basin_top1")
                ],
                "observed_peak_underestimation_fraction": h.loc[
                    predictor, ("median_underestimation_fraction", "observed_peak_hour")
                ],
                "observed_peak_median_relative_bias_pct": h.loc[
                    predictor, ("median_median_rel_bias_pct", "observed_peak_hour")
                ],
                "stress_ge25_under_deficit_pct": s.loc[
                    predictor, ("seed_mean_median_obs_peak_under_deficit_pct", "flood_response_ge25")
                ],
                "stress_2_to_25_under_deficit_pct": s.loc[
                    predictor, ("seed_mean_median_obs_peak_under_deficit_pct", "flood_response_ge2_to_lt25")
                ],
                "negative_control_pred_peak_to_ari100": s.loc[
                    predictor, ("seed_mean_median_pred_window_peak_to_flood_ari100", "low_response_below_q99")
                ],
                "inflation_flag": "above_ari100_negative_control"
                if s.loc[
                    predictor, ("seed_mean_median_pred_window_peak_to_flood_ari100", "low_response_below_q99")
                ]
                > 1
                else "below_ari100_negative_control",
            }
        )
    return pd.DataFrame(rows)


def save_loss_trend_chart(losses: pd.DataFrame, diagnostics: pd.DataFrame, output_path: Path) -> None:
    if losses.empty:
        return
    fig, axes = plt.subplots(2, 3, figsize=(15.5, 7.7), squeeze=False, sharex=True)
    ordered = diagnostics.sort_values(["model", "seed"])
    for ax, row in zip(axes.ravel(), ordered.itertuples(index=False), strict=False):
        sub = losses[losses["model"].eq(row.model) & losses["seed"].eq(row.seed)]
        val = sub[sub["loss_type"].eq("validation")].sort_values("epoch").copy()
        if not val.empty:
            val["relative_loss"] = val["avg_loss"] / val["avg_loss"].iloc[0]
            ax.plot(
                val["epoch"],
                val["relative_loss"],
                color="#2563eb",
                marker="o",
                linewidth=1.8,
                label="validation",
            )
            ax.axhline(float(val["relative_loss"].min()), color="#9ca3af", linestyle=":", linewidth=1.0)
        if not pd.isna(row.selected_primary_epoch):
            ax.axvline(row.selected_primary_epoch, color="#dc2626", linestyle="--", linewidth=1.0, alpha=0.75)
        ax.set_title(f"{row.model_label} seed {row.seed}")
        ax.set_ylim(bottom=0.75)
        ax.grid(True, axis="y", color="#e5e7eb", linewidth=0.7)
        ax.set_xlabel("Epoch")
        ax.set_ylabel("Relative validation loss")
    fig.suptitle("Validation loss identifies later-epoch overfit risk")
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def save_nse_epoch_alignment_chart(epoch_summary: pd.DataFrame, primary_epochs: dict[tuple[str, int], int], output_path: Path) -> None:
    if epoch_summary.empty:
        return
    sub = epoch_summary[
        epoch_summary["model"].isin(["model1", "model2"])
        & epoch_summary["seed"].isin(OFFICIAL_SEEDS)
        & epoch_summary["split"].isin(["validation", "test"])
    ].copy()
    fig, axes = plt.subplots(2, 3, figsize=(15.5, 7.7), squeeze=False, sharex=True)
    pairs = [(model, seed) for model in ["model1", "model2"] for seed in OFFICIAL_SEEDS]
    for ax, (model, seed) in zip(axes.ravel(), pairs, strict=True):
        g = sub[sub["model"].eq(model) & sub["seed"].eq(seed)]
        for split in ["validation", "test"]:
            one = g[g["split"].eq(split)].sort_values("epoch")
            ax.plot(
                one["epoch"],
                one["median_NSE"],
                marker="o",
                linewidth=1.8,
                color=SPLIT_COLORS[split],
                label=split,
            )
        selected = primary_epochs.get((model, seed))
        if selected is not None:
            ax.axvline(selected, color="#111827", linestyle="--", linewidth=1.0, alpha=0.75)
        ax.axhline(0, color="#9ca3af", linewidth=0.8)
        ax.set_title(f"{MODEL_LABELS[model]} seed {seed}")
        ax.set_xlabel("Epoch")
        ax.set_ylabel("Median NSE")
        ax.grid(True, axis="y", color="#e5e7eb", linewidth=0.7)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 0.965), frameon=False)
    fig.suptitle("Validation-selected epochs are not equivalent to DRBC test-oracle epochs")
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def save_test_oracle_gap_chart(selection: pd.DataFrame, output_path: Path) -> None:
    if selection.empty:
        return
    metrics = ["median_NSE", "median_KGE", "median_abs_FHV", "median_Peak_Timing", "median_Peak_MAPE"]
    seed_offsets = {111: -0.10, 222: 0.0, 444: 0.10}
    seed_markers = {111: "o", 222: "s", 444: "^"}
    fig, axes = plt.subplots(1, len(metrics), figsize=(17.0, 4.4), squeeze=False)
    for ax, metric in zip(axes.ravel(), metrics, strict=True):
        sub = selection[selection["metric"].eq(metric)].copy()
        for x_pos, model in enumerate(["model1", "model2"]):
            one = sub[sub["model"].eq(model)]
            median_gap = float(one["test_oracle_gap"].median())
            ax.hlines(
                median_gap,
                x_pos - 0.22,
                x_pos + 0.22,
                color=MODEL_COLORS[model],
                linewidth=3.0,
                alpha=0.95,
            )
            for row in one.itertuples(index=False):
                ax.scatter(
                    x_pos + seed_offsets[int(row.seed)],
                    row.test_oracle_gap,
                    s=58,
                    marker=seed_markers[int(row.seed)],
                    color=MODEL_COLORS[model],
                    edgecolor="#111827",
                    linewidth=0.6,
                    zorder=3,
                )
        ax.axhline(0, color="#111827", linewidth=0.9)
        max_gap = float(sub["test_oracle_gap"].max())
        pad = max(max_gap * 0.18, 0.03)
        ax.set_ylim(-pad * 0.35, max_gap + pad)
        ax.set_xticks([0, 1], ["Model 1", "Model 2"])
        ax.set_title(str(sub["metric_label"].iloc[0]))
        ax.set_ylabel("Gap to test-best")
        ax.grid(True, axis="y", color="#e5e7eb", linewidth=0.7)
        ax.tick_params(axis="x", rotation=20)
    handles = [
        plt.Line2D(
            [0],
            [0],
            marker=marker,
            color="w",
            markerfacecolor="#6b7280",
            markeredgecolor="#111827",
            markersize=8,
            label=f"seed {seed}",
        )
        for seed, marker in seed_markers.items()
    ]
    handles.append(plt.Line2D([0], [0], color="#6b7280", linewidth=3, label="median"))
    fig.legend(handles=handles, loc="upper center", ncol=4, bbox_to_anchor=(0.5, 0.955), frameon=False)
    fig.suptitle("DRBC test-oracle gaps by seed; horizontal bars show medians")
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def save_quantile_tradeoff_chart(tradeoff: pd.DataFrame, output_path: Path) -> None:
    if tradeoff.empty:
        return
    tradeoff = tradeoff.set_index("predictor").reindex(PREDICTOR_ORDER).reset_index()
    colors = [PREDICTOR_COLORS[p] for p in tradeoff["predictor"]]
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.8), squeeze=False)
    ax = axes[0, 0]
    ax.bar(tradeoff["predictor"], tradeoff["basin_top1_underestimation_fraction"], color=colors, alpha=0.88)
    ax.set_ylim(0, 1)
    ax.set_title("Primary top 1% underestimation")
    ax.set_ylabel("Fraction")
    ax.grid(True, axis="y", color="#e5e7eb", linewidth=0.7)
    ax.tick_params(axis="x", rotation=20)

    ax = axes[0, 1]
    ax.bar(tradeoff["predictor"], tradeoff["stress_ge25_under_deficit_pct"], color=colors, alpha=0.88)
    ax.set_title("Stress >=25yr under-deficit")
    ax.set_ylabel("Under-deficit (%)")
    ax.grid(True, axis="y", color="#e5e7eb", linewidth=0.7)
    ax.tick_params(axis="x", rotation=20)

    ax = axes[0, 2]
    ax.bar(tradeoff["predictor"], tradeoff["negative_control_pred_peak_to_ari100"], color=colors, alpha=0.88)
    ax.axhline(1, color="#dc2626", linestyle="--", linewidth=1.0)
    ax.set_title("Negative-control predicted peak / ARI100")
    ax.set_ylabel("Ratio")
    ax.grid(True, axis="y", color="#e5e7eb", linewidth=0.7)
    ax.tick_params(axis="x", rotation=20)

    fig.suptitle("Upper quantiles reduce underestimation, but q99 carries inflation risk")
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def write_report(
    report_path: Path,
    figures: dict[str, Path],
    loss_diag: pd.DataFrame,
    selection_diag: pd.DataFrame,
    oracle_summary: pd.DataFrame,
    corr: pd.DataFrame,
    tradeoff: pd.DataFrame,
) -> None:
    mild_or_worse = loss_diag[~loss_diag["diagnostic_flag"].eq("no_clear_loss_overfit")]
    n_loss_flags = int(len(mild_or_worse))
    n_primary_loss_flags = int((loss_diag["primary_vs_min_validation_loss_pct"] >= 5).sum()) if not loss_diag.empty else 0
    n_test_best = int(selection_diag["selected_equals_test_best"].sum()) if not selection_diag.empty else 0
    n_rows = int(len(selection_diag)) if not selection_diag.empty else 0
    n_val_best = int(selection_diag["selected_equals_validation_best"].sum()) if not selection_diag.empty else 0
    q99_ratio = np.nan
    q95_ratio = np.nan
    if not tradeoff.empty:
        q99_ratio = float(
            tradeoff[tradeoff["predictor"].eq("Model 2 q99")]["negative_control_pred_peak_to_ari100"].iloc[0]
        )
        q95_ratio = float(
            tradeoff[tradeoff["predictor"].eq("Model 2 q95")]["negative_control_pred_peak_to_ari100"].iloc[0]
        )
    lines = [
        "# Subset300 overfit analysis",
        "",
        "## 결론",
        "",
        "현재 결과를 과적합 관점에서 보면, `Model 2가 DRBC test에 맞춰 epoch를 고른 결과`라고 보기는 어렵다. "
        "공식 primary epoch는 non-DRBC validation 기준으로 정해져 있고, DRBC test-oracle epoch와도 자주 일치하지 않는다. "
        "다만 late epoch에서는 validation loss가 더 좋아지지 않거나 다시 나빠지는 seed가 있어, classic overfit 신호는 일부 존재한다. "
        "따라서 결론은 `전체적으로 우월한 모델`이 아니라 `validation-selected q50은 central skill guardrail이고, flood 개선은 q95/q99 upper quantile에서 나온다`로 제한해야 한다.",
        "",
        f"Final epoch를 기준으로 보면 {n_loss_flags}/6개 official run에서 mild 이상 validation-loss overfit signal이 있었다. "
        f"하지만 실제 primary epoch 기준으로는 {n_primary_loss_flags}/6개 run만 min validation loss 대비 5% 이상 나빠졌다. "
        f"Metric 기준 primary epoch는 validation-best와 {n_val_best}/{n_rows}번, DRBC test-best와 {n_test_best}/{n_rows}번 일치했다. "
        f"q95 negative-control ratio는 {fmt(q95_ratio)}, q99는 {fmt(q99_ratio)}라서 q99는 inflation risk를 명시해야 한다.",
        "",
        "## Training/validation loss",
        "",
        markdown_image(figures["loss_trends"], report_path, "Training and validation loss trend"),
        "",
        "이 그림은 validation loss가 초반 이후 더 좋아지지 않거나 다시 올라가는 run을 보여준다. "
        "따라서 더 긴 epoch나 test 기준 epoch 선택은 과적합 위험을 키울 수 있지만, 현재 primary epoch는 대체로 min validation loss 근처에 있다.",
        "",
        loss_diag.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## Validation vs DRBC test epoch behavior",
        "",
        markdown_image(figures["nse_epoch_alignment"], report_path, "Validation and test NSE by epoch"),
        "",
        "validation NSE와 DRBC test NSE의 epoch별 움직임은 완전히 같은 방향이 아니다. "
        "이건 test 성능을 보고 epoch를 고르면 쉽게 test-set overfitting이 생길 수 있다는 뜻이고, 동시에 현재 primary epoch가 test-oracle 선택이 아니라는 근거이기도 하다.",
        "",
        selection_diag.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## Test-oracle risk",
        "",
        markdown_image(figures["test_oracle_gap"], report_path, "Test oracle gap by metric"),
        "",
        "이 그림은 만약 DRBC test에서 epoch를 직접 골랐다면 각 metric이 얼마나 더 좋아질 수 있었는지를 seed별 점으로 보여준다. "
        "가로선은 model별 median이고, 점은 seed 111/222/444다. seed가 3개뿐이므로 median만 단독으로 보면 seed-specific risk가 숨겨질 수 있다. "
        "예를 들어 Model 2 peak timing은 median gap이 0이지만 seed 222에서는 추가 개선 여지가 보인다. "
        "따라서 all-epoch sweep은 주장 선택용이 아니라 sensitivity 진단으로만 써야 한다.",
        "",
        "아래 표는 같은 값을 median으로 요약한 보조 표다. 결론 판단은 위 seed-level 점과 함께 읽는다.",
        "",
        oracle_summary.to_markdown(index=False, floatfmt=".4f"),
        "",
        "Validation-test Spearman rho는 아래와 같다. epoch 수가 6개뿐이라 통계 검정보다는 방향성 점검으로만 읽는다.",
        "",
        corr.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Quantile inflation risk",
        "",
        markdown_image(figures["quantile_tradeoff"], report_path, "Quantile inflation tradeoff"),
        "",
        "q95/q99는 high-flow underestimation을 줄이지만, q99는 negative-control low-response event에서 predicted peak / ARI100이 1을 넘는다. "
        "따라서 q99를 calibrated 99% bound처럼 쓰면 안 되고, conservative upper-tail scenario 또는 high-risk screening signal로 해석해야 한다.",
        "",
        tradeoff.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## 논문에 넣을 안전한 표현",
        "",
        "The selected epochs were determined from non-DRBC validation diagnostics rather than DRBC test performance. "
        "Across available checkpoints, DRBC test-oracle epochs often differ from the primary epochs, so all-epoch sweeps are used only as sensitivity diagnostics. "
        "The probabilistic extension should therefore be interpreted as reducing flood underestimation through upper quantiles, while q50 overall gains and q99 inflation are treated as guarded, robustness-qualified results.",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    main_dir = resolve(args.main_comparison_dir)
    output_dir = resolve(args.output_dir)
    tables_dir = output_dir / "tables"
    figures_dir = output_dir / "figures"
    report_dir = output_dir / "report"
    metadata_dir = output_dir / "metadata"
    for directory in [tables_dir, figures_dir, report_dir, metadata_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    manifest = read_csv(resolve(args.metric_manifest))
    epoch_summary = read_csv(resolve(args.epoch_summary))
    primary = read_csv(main_dir / "tables/primary_epoch_summary.csv")
    high_flow = read_csv(main_dir / "tables/overall_performance_high_flow_quantile_summary.csv")
    stress = read_csv(main_dir / "tables/overall_performance_extreme_rain_stress_summary.csv")

    primary_epochs = primary_epoch_map(primary)
    run_dirs = run_dirs_from_manifest(manifest)
    losses = parse_loss_logs(run_dirs)
    loss_diag = build_loss_diagnostics(losses, primary_epochs)
    selection_diag, corr = build_epoch_selection_diagnostics(epoch_summary, primary_epochs)
    oracle_summary = build_oracle_gap_summary(selection_diag)
    tradeoff = build_quantile_tradeoff(high_flow, stress)

    figures = {
        "loss_trends": figures_dir / "overfit_loss_trends.png",
        "nse_epoch_alignment": figures_dir / "overfit_validation_test_nse_alignment.png",
        "test_oracle_gap": figures_dir / "overfit_test_oracle_gap_by_metric.png",
        "quantile_tradeoff": figures_dir / "overfit_quantile_inflation_tradeoff.png",
    }
    save_loss_trend_chart(losses, loss_diag, figures["loss_trends"])
    save_nse_epoch_alignment_chart(epoch_summary, primary_epochs, figures["nse_epoch_alignment"])
    save_test_oracle_gap_chart(selection_diag, figures["test_oracle_gap"])
    save_quantile_tradeoff_chart(tradeoff, figures["quantile_tradeoff"])

    losses.to_csv(tables_dir / "overfit_loss_log_long.csv", index=False)
    loss_diag.to_csv(tables_dir / "overfit_loss_diagnostics.csv", index=False)
    selection_diag.to_csv(tables_dir / "overfit_epoch_selection_diagnostics.csv", index=False)
    oracle_summary.to_csv(tables_dir / "overfit_test_oracle_gap_summary.csv", index=False)
    corr.to_csv(tables_dir / "overfit_validation_test_epoch_correlation.csv", index=False)
    tradeoff.to_csv(tables_dir / "overfit_quantile_inflation_tradeoff.csv", index=False)
    run_dirs.to_csv(tables_dir / "overfit_run_dirs.csv", index=False)

    manifest_rows = [
        {"figure_key": key, "path": str(path), "exists": path.exists()} for key, path in figures.items()
    ]
    pd.DataFrame(manifest_rows).to_csv(figures_dir / "overfit_figure_manifest.csv", index=False)

    report_path = report_dir / "overfit_analysis_report.md"
    write_report(report_path, figures, loss_diag, selection_diag, oracle_summary, corr, tradeoff)

    metadata = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "inputs": {
            "metric_manifest": str(resolve(args.metric_manifest)),
            "epoch_summary": str(resolve(args.epoch_summary)),
            "main_comparison_dir": str(main_dir),
        },
        "outputs": {
            "output_dir": str(output_dir),
            "report": str(report_path),
            "tables_dir": str(tables_dir),
            "figures": {key: str(value) for key, value in figures.items()},
        },
        "official_seeds": OFFICIAL_SEEDS,
        "notes": [
            "Model 2 seed 333 is excluded because official paired comparison excludes it.",
            "All-epoch sweeps are diagnostic only and are not used to choose primary test performance.",
        ],
    }
    (metadata_dir / "overfit_analysis_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    print(f"Wrote report to {report_path}")
    print(f"Wrote tables to {tables_dir}")


if __name__ == "__main__":
    main()
