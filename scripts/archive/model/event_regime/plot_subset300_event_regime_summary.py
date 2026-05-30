#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = (
    REPO_ROOT
    / "output/model_analysis/legacy/quantile_analysis/event_regime_analysis/paired_delta_aggregate.csv"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/legacy/quantile_analysis/event_regime_analysis"
PREDICTOR_ORDER = ["q50", "q90", "q95", "q99"]
PREDICTOR_LABELS = {
    "q50": "q50",
    "q90": "q90",
    "q95": "q95",
    "q99": "q99",
}
PREDICTOR_COLORS = {
    "q50": "#2563eb",
    "q90": "#16a34a",
    "q95": "#f97316",
    "q99": "#dc2626",
}
REGIME_ORDER = [
    "Recent rainfall",
    "Antecedent / multi-day rain",
    "Weak / low-signal hydromet regime",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create publication-oriented event-regime paired-delta figure."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _read_compact(input_path: Path) -> pd.DataFrame:
    df = pd.read_csv(input_path)
    df = df[df["stratification"].eq("ml_event_regime")].copy()
    df = df[df["predictor"].isin(PREDICTOR_ORDER)].copy()
    df["regime_order"] = df["stratum"].map({name: idx for idx, name in enumerate(REGIME_ORDER)})
    missing = df["regime_order"].isna()
    if missing.any():
        next_order = len(REGIME_ORDER)
        extras = sorted(df.loc[missing, "stratum"].dropna().unique())
        extra_map = {name: idx + next_order for idx, name in enumerate(extras)}
        df.loc[missing, "regime_order"] = df.loc[missing, "stratum"].map(extra_map)
    df["predictor_order"] = df["predictor"].map({name: idx for idx, name in enumerate(PREDICTOR_ORDER)})
    cols = [
        "stratification",
        "stratum",
        "predictor",
        "predictor_label",
        "n_seed_summaries",
        "mean_n_events",
        "seed_mean_median_paired_under_deficit_reduction_pct",
        "seed_sd_median_paired_under_deficit_reduction_pct",
        "seed_mean_mean_threshold_recall_delta",
        "seed_sd_mean_threshold_recall_delta",
        "seed_mean_median_event_nrmse_pct_delta",
        "seed_sd_median_event_nrmse_pct_delta",
        "seed_mean_mean_top_flow_hit_rate_delta",
        "seed_sd_mean_top_flow_hit_rate_delta",
        "regime_order",
        "predictor_order",
    ]
    return df[cols].sort_values(["regime_order", "predictor_order"]).reset_index(drop=True)


def _plot_panel(
    ax: plt.Axes,
    frame: pd.DataFrame,
    metric_col: str,
    sd_col: str,
    title: str,
    xlabel: str,
    zero_line: bool = True,
) -> None:
    regimes = list(frame.sort_values("regime_order")["stratum"].drop_duplicates())
    offsets = {
        "q50": -0.24,
        "q90": -0.08,
        "q95": 0.08,
        "q99": 0.24,
    }
    y_positions = {regime: idx for idx, regime in enumerate(regimes)}
    for predictor in PREDICTOR_ORDER:
        sub = frame[frame["predictor"].eq(predictor)]
        if sub.empty:
            continue
        y = [y_positions[row.stratum] + offsets[predictor] for row in sub.itertuples(index=False)]
        x = sub[metric_col].to_numpy(dtype=float)
        xerr = sub[sd_col].fillna(0.0).to_numpy(dtype=float)
        ax.errorbar(
            x,
            y,
            xerr=xerr,
            fmt="o",
            markersize=4.5,
            linewidth=1.0,
            elinewidth=1.0,
            capsize=2.5,
            color=PREDICTOR_COLORS[predictor],
            label=PREDICTOR_LABELS[predictor],
        )
    if zero_line:
        ax.axvline(0.0, color="#4b5563", linestyle="--", linewidth=0.9)
    ax.set_yticks(list(y_positions.values()))
    ax.set_yticklabels(regimes)
    ax.invert_yaxis()
    ax.set_xlabel(xlabel)
    ax.set_title(title, fontsize=10)
    ax.grid(True, axis="x", color="#e5e7eb", linewidth=0.7)


def _save_figure(compact: pd.DataFrame, output_path: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14.5, 5.2), sharey=True)
    _plot_panel(
        axes[0],
        compact,
        "seed_mean_median_paired_under_deficit_reduction_pct",
        "seed_sd_median_paired_under_deficit_reduction_pct",
        "Peak under-deficit reduction",
        "Percentage points vs Model 1",
    )
    _plot_panel(
        axes[1],
        compact,
        "seed_mean_mean_threshold_recall_delta",
        "seed_sd_mean_threshold_recall_delta",
        "Threshold recall delta",
        "Recall delta vs Model 1",
    )
    _plot_panel(
        axes[2],
        compact,
        "seed_mean_median_event_nrmse_pct_delta",
        "seed_sd_median_event_nrmse_pct_delta",
        "Event NRMSE delta",
        "NRMSE pct delta vs Model 1",
    )
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False)
    fig.suptitle("Event-regime paired deltas for Model 2 quantiles", y=0.98, fontsize=12)
    fig.tight_layout(rect=[0, 0.08, 1, 0.95])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    input_path = _resolve(args.input)
    output_dir = _resolve(args.output_dir)
    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    compact = _read_compact(input_path)
    compact_path = output_dir / "event_regime_paired_delta_compact.csv"
    compact.to_csv(compact_path, index=False)

    figure_path = figures_dir / "event_regime_paired_delta_summary.png"
    _save_figure(compact, figure_path)

    manifest = pd.DataFrame(
        [
            {
                "chart": "event_regime_paired_delta_summary",
                "path": _relative(figure_path),
                "exists": figure_path.exists(),
            }
        ]
    )
    manifest_path = output_dir / "event_regime_chart_manifest.csv"
    manifest.to_csv(manifest_path, index=False)

    metadata = {
        "input": _relative(input_path),
        "compact_table": _relative(compact_path),
        "chart_manifest": _relative(manifest_path),
        "figure": _relative(figure_path),
        "interpretation": (
            "Positive under-deficit reduction and threshold recall delta favor the Model 2 quantile. "
            "Positive event NRMSE delta is a tradeoff, not an improvement."
        ),
    }
    metadata_path = output_dir / "event_regime_chart_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Wrote event-regime compact table: {compact_path}")
    print(f"Wrote event-regime figure: {figure_path}")


if __name__ == "__main__":
    main()
