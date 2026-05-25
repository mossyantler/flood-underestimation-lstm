#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "matplotlib>=3.8",
# ]
# ///
"""Plot stratified underestimation figures (relative + absolute) for confirmed flood events."""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
TABLES_DIR = REPO_ROOT / "output/model_analysis/confirmed_flood/tables"
FIGURES_DIR = REPO_ROOT / "output/model_analysis/confirmed_flood/figures"

PRED_COLS = ["model1", "q50", "q90", "q95", "q99"]
PRED_LABELS = {"model1": "Model 1", "q50": "Q50", "q90": "Q90", "q95": "Q95", "q99": "Q99"}
COLORS = {"model1": "#333333", "q50": "#4393c3", "q90": "#2166ac", "q95": "#d6604d", "q99": "#b2182b"}
MARKERS = {"model1": "s", "q50": "o", "q90": "^", "q95": "D", "q99": "*"}

# Left panel: ascending severity (nested plus strata)
SEVERITY_STRATA = ["all", "moderate_plus", "major_plus"]
SEVERITY_LABELS = ["All", "Mod+", "Maj+"]

# Right panel: below-threshold complements + NOAA subset
BELOW_STRATA = ["below_major", "below_moderate", "noaa_corroborated"]
BELOW_LABELS = ["<Major", "<Moderate", "NOAA\ncorroborated"]

# Fixed-tier strata (mutually exclusive)
TIER_STRATA = ["minor_only", "moderate_only", "major_only"]
TIER_LABELS = ["Minor", "Moderate", "Major"]


def _err_bounds(
    df: pd.DataFrame, strata: list[str], col: str
) -> tuple[list, list, list]:
    vals, lo, hi = [], [], []
    for s in strata:
        row = df[df["stratum"] == s].iloc[0]
        v = row[col]
        vals.append(v)
        lo.append(v - row[f"{col}_min"])
        hi.append(row[f"{col}_max"] - v)
    return vals, lo, hi


def plot_panel(
    ax: plt.Axes,
    df: pd.DataFrame,
    strata: list[str],
    xlabels: list[str],
    metric: str,
    ylabel: str,
    title: str,
) -> None:
    x = np.arange(len(strata))
    for pred in PRED_COLS:
        col = f"{pred}_{metric}"
        vals, lo, hi = _err_bounds(df, strata, col)
        ax.errorbar(
            x, vals, yerr=np.array([lo, hi]),
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
        "Confirmed flood events, 48 basins, median across events & seeds",
        fontsize=11,
    )

    plot_panel(
        axes[0], df, SEVERITY_STRATA, SEVERITY_LABELS, metric,
        ylabel, "Ascending flood severity",
    )
    plot_panel(
        axes[1], df, BELOW_STRATA, BELOW_LABELS, metric,
        ylabel, "Below-threshold & NOAA subsets",
    )

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", fontsize=9, framealpha=0.8)
    fig.tight_layout(rect=[0, 0, 0.88, 1])

    out = FIGURES_DIR / filename
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out}")
    return out


def make_tier_figure(df: pd.DataFrame, metric: str, ylabel: str, filename: str) -> Path:
    """Single-panel figure: fixed flood tiers (minor / moderate / major)."""
    fig, ax = plt.subplots(figsize=(7, 5))
    fig.suptitle(
        f"Conditional Underestimation Magnitude — {ylabel}\n"
        "Confirmed flood events by fixed tier, 48 basins, median across events & seeds",
        fontsize=11,
    )
    plot_panel(ax, df, TIER_STRATA, TIER_LABELS, metric, ylabel, "")
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, fontsize=9, framealpha=0.8)
    fig.tight_layout()
    out = FIGURES_DIR / filename
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out}")
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tables-dir", type=Path, default=TABLES_DIR)
    parser.add_argument("--figures-dir", type=Path, default=FIGURES_DIR)
    args = parser.parse_args(argv)

    df = pd.read_csv(args.tables_dir / "confirmed_flood_stratified_underestimation_summary.csv")
    args.figures_dir.mkdir(parents=True, exist_ok=True)

    make_figure(
        df,
        metric="cond_under_magnitude",
        ylabel="Relative magnitude [(obs−pred)/obs]",
        filename="confirmed_flood_stratified_underestimation_relative.png",
    )
    make_figure(
        df,
        metric="cond_under_abs_magnitude",
        ylabel="Absolute magnitude [cms]",
        filename="confirmed_flood_stratified_underestimation_absolute.png",
    )
    make_tier_figure(
        df,
        metric="cond_under_magnitude",
        ylabel="Relative magnitude [(obs−pred)/obs]",
        filename="confirmed_flood_tier_underestimation_relative.png",
    )
    make_tier_figure(
        df,
        metric="cond_under_abs_magnitude",
        ylabel="Absolute magnitude [cms]",
        filename="confirmed_flood_tier_underestimation_absolute.png",
    )
    make_tier_figure(
        df,
        metric="under_frac",
        ylabel="Under-estimation fraction [P(pred < obs)]",
        filename="confirmed_flood_tier_under_fraction.png",
    )
    make_figure(
        df,
        metric="under_frac",
        ylabel="Under-estimation fraction [P(pred < obs)]",
        filename="confirmed_flood_stratified_under_fraction.png",
    )


if __name__ == "__main__":
    main()
