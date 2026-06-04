#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "matplotlib>=3.8",
# ]
# ///
"""Plot stratified underestimation figures (relative + absolute) for expanded DRBC test."""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
TABLES_DIR = REPO_ROOT / "output/model_analysis/primary/metrics/tables"
FIGURES_DIR = REPO_ROOT / "output/model_analysis/primary/metrics/figures"

PRED_COLS = ["model1", "q50", "q90", "q95", "q99"]
PRED_LABELS = {"model1": "Model 1", "q50": "Q50", "q90": "Q90", "q95": "Q95", "q99": "Q99"}
COLORS = {"model1": "#333333", "q50": "#4393c3", "q90": "#2166ac", "q95": "#d6604d", "q99": "#b2182b"}
MARKERS = {"model1": "s", "q50": "o", "q90": "^", "q95": "D", "q99": "*"}

PLUS_STRATA = ["all", "obs_q50_plus", "obs_q90_plus", "obs_q95_plus", "obs_q99_plus"]
PLUS_LABELS = ["All", "Q50+", "Q90+", "Q95+", "Q99+"]
MINUS_STRATA = ["obs_q50_minus", "obs_q90_minus", "obs_q95_minus", "obs_q99_minus"]
MINUS_LABELS = ["Q50−", "Q90−", "Q95−", "Q99−"]


def _err_bounds(df: pd.DataFrame, strata: list[str], col: str) -> tuple[list, list, list]:
    vals, lo, hi = [], [], []
    for s in strata:
        row = df[df["stratum"] == s].iloc[0]
        v = row[col]
        vals.append(v)
        lo.append(v - row[f"{col}_min"])
        hi.append(row[f"{col}_max"] - v)
    return vals, lo, hi


def plot_magnitude_panel(
    ax: plt.Axes,
    df: pd.DataFrame,
    strata: list[str],
    xlabels: list[str],
    metric: str,
    ylabel: str,
    title: str,
    show_errbar: bool = True,
) -> None:
    x = np.arange(len(strata))
    for pred in PRED_COLS:
        col = f"{pred}_{metric}"
        vals, lo, hi = _err_bounds(df, strata, col)
        yerr = np.array([lo, hi]) if show_errbar else None
        ax.errorbar(
            x, vals, yerr=yerr,
            label=PRED_LABELS[pred],
            color=COLORS[pred],
            marker=MARKERS[pred],
            markersize=7,
            linewidth=1.5,
            capsize=3,
            capthick=1.2,
        )
    ax.set_xticks(x)
    ax.set_xticklabels(xlabels, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def make_figure(df: pd.DataFrame, metric: str, ylabel: str, filename: str) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=False)
    fig.suptitle(
        f"Conditional Underestimation Magnitude — {ylabel}\n"
        "85-basin expanded DRBC test (2014–2016), median across basins & seeds",
        fontsize=11,
    )

    plot_magnitude_panel(
        axes[0], df, PLUS_STRATA, PLUS_LABELS, metric,
        ylabel, "High-flow strata (obs > threshold)",
    )
    plot_magnitude_panel(
        axes[1], df, MINUS_STRATA, MINUS_LABELS, metric,
        ylabel, "Low-flow strata (obs ≤ threshold)",
    )

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", fontsize=9, framealpha=0.8)
    fig.tight_layout(rect=[0, 0, 0.88, 1])

    out = FIGURES_DIR / filename
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out}")
    return out


def print_table(df: pd.DataFrame) -> None:
    all_strata = ["all", "obs_q50_plus", "obs_q50_minus",
                  "obs_q90_plus", "obs_q90_minus",
                  "obs_q95_plus", "obs_q95_minus",
                  "obs_q99_plus", "obs_q99_minus"]
    stratum_short = {
        "all": "All", "obs_q50_plus": "Q50+", "obs_q50_minus": "Q50−",
        "obs_q90_plus": "Q90+", "obs_q90_minus": "Q90−",
        "obs_q95_plus": "Q95+", "obs_q95_minus": "Q95−",
        "obs_q99_plus": "Q99+", "obs_q99_minus": "Q99−",
    }
    for metric_suffix, unit, header in [
        ("cond_under_magnitude", "%", "Conditional relative underestimation magnitude [median (obs−pred)/obs]"),
        ("cond_under_abs_magnitude", "cms", "Conditional absolute underestimation magnitude [median obs−pred, cms]"),
        ("under_frac", "", "Underestimation fraction [P(pred < obs)]"),
    ]:
        print(f"\n{'='*80}")
        print(header)
        print('='*80)
        header_row = f"{'Stratum':<12}" + "".join(f"{PRED_LABELS[p]:>10}" for p in PRED_COLS)
        print(header_row)
        print("-" * len(header_row))
        for s in all_strata:
            row = df[df["stratum"] == s].iloc[0]
            fmt = f"{'%':<12}" if metric_suffix == "cond_under_magnitude" else f"{'':12}"
            vals = []
            for p in PRED_COLS:
                col = f"{p}_{metric_suffix}"
                v = row[col]
                if metric_suffix == "cond_under_magnitude":
                    vals.append(f"{v*100:>9.1f}%")
                elif metric_suffix == "under_frac":
                    vals.append(f"{v:>9.3f}")
                else:
                    vals.append(f"{v:>9.2f}")
            print(f"{stratum_short[s]:<12}" + "".join(vals))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tables-dir", type=Path, default=TABLES_DIR)
    parser.add_argument("--figures-dir", type=Path, default=FIGURES_DIR)
    args = parser.parse_args(argv)

    df = pd.read_csv(args.tables_dir / "stratified_underestimation_summary.csv")
    args.figures_dir.mkdir(parents=True, exist_ok=True)

    make_figure(
        df,
        metric="cond_under_magnitude",
        ylabel="Relative magnitude [(obs−pred)/obs]",
        filename="stratified_underestimation_relative.png",
    )
    make_figure(
        df,
        metric="cond_under_abs_magnitude",
        ylabel="Absolute magnitude [cms]",
        filename="stratified_underestimation_absolute.png",
    )

    print_table(df)


if __name__ == "__main__":
    main()
