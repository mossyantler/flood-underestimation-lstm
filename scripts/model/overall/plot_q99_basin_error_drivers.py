#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "matplotlib>=3.9",
#   "scipy>=1.13",
# ]
# ///
"""Visualize Q99 basin error driver analysis.

Figures
-------
q99_driver_correlation_bar.png   Spearman ρ bar (stable drivers, seed median)
q99_driver_scatter_top4.png      Top-4 physical drivers scatter vs q99_med_rel_bias
q99_quartile_radar.png           Q1 vs Q4 basin profile (top-5 stable physical drivers)
q99_delta_drivers_bar.png        Stable drivers for med_rel_bias_delta
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
TABLE_DIR = REPO_ROOT / "output/model_analysis/q99_analysis/tables"
FIG_DIR = REPO_ROOT / "output/model_analysis/q99_analysis/figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

TARGET_BIAS = "q99_med_rel_bias"
TARGET_DELTA = "med_rel_bias_delta"

C_WORST = "#d62728"
C_BEST = "#1f77b4"
C_NEG = "#d62728"
C_POS = "#1f77b4"

ATTR_LABELS = {
    "STRAHLER_MAX": "Strahler order",
    "PERMAVE": "Soil permeability",
    "MAINSTEM_SINUOUSITY": "Sinuosity",
    "unit_area_peak_p90": "Unit-area peak P90",
    "RUNAVE7100": "Runoff avg (7100)",
    "unit_area_peak_median": "Unit-area peak med",
    "event_duration_median_hours": "Event duration (h)",
    "HGA": "Soil group A frac",
    "q99_event_frequency": "Q99 event freq",
    "ARTIFPATH_PCT": "Artifpath %",
    "ARTIFPATH_MAINSTEM_PCT": "Artifpath mainstem %",
    "rbi": "RBI (flashiness)",
    "rising_time_median_hours": "Rising time (h)",
    "RRMEAN": "Relief ratio mean",
    "SLOPE_PCT": "Slope %",
    "drain_sqkm": "Drainage area",
    "BFI_AVE": "BFI",
    "aridity_index": "Aridity",
}


def label(attr: str) -> str:
    return ATTR_LABELS.get(attr, attr)


# ── Fig 1: Spearman ρ bar (q99_med_rel_bias) ──────────────────────────────────

def plot_correlation_bar(stable: pd.DataFrame) -> None:
    sub = stable[stable["target"] == TARGET_BIAS].head(15)
    sub = sub.sort_values("rho_median", key=abs, ascending=True)

    fig, ax = plt.subplots(figsize=(8, 6))
    colors = [C_POS if r > 0 else C_NEG for r in sub["rho_median"]]
    ax.barh([label(a) for a in sub["attribute"]], sub["rho_median"], color=colors)
    ax.errorbar(
        sub["rho_median"], range(len(sub)),
        xerr=[sub["rho_median"] - sub["rho_min"], sub["rho_max"] - sub["rho_median"]],
        fmt="none", color="gray", linewidth=1, capsize=3,
    )
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Spearman ρ (seed median, 3-seed stable)", fontsize=11)
    ax.set_title(f"Basin attribute drivers of {TARGET_BIAS}\n(85 expanded DRBC basins)", fontsize=11)
    ax.set_xlim(-0.75, 0.75)
    ax.legend(
        handles=[
            mpatches.Patch(color=C_POS, label="Higher attr → higher q99 bias"),
            mpatches.Patch(color=C_NEG, label="Higher attr → lower q99 bias"),
        ],
        fontsize=9, loc="lower right",
    )
    fig.tight_layout()
    out = FIG_DIR / "q99_driver_correlation_bar.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


# ── Fig 2: Scatter top-4 physical drivers ────────────────────────────────────

def plot_scatter_top4(stable: pd.DataFrame, summary: pd.DataFrame) -> None:
    # skip model-performance metrics — only physical basin attributes
    model_cols = {"model1_NSE", "model1_KGE", "model1_FHV", "model2_FHV",
                  "model1_med_rel_bias", "model1_Peak-MAPE", "model2_Peak-Timing"}
    physical = stable[
        (stable["target"] == TARGET_BIAS) &
        (~stable["attribute"].isin(model_cols))
    ].head(4)["attribute"].tolist()

    if not physical:
        print("  [WARN] no physical drivers found for scatter, skipping")
        return

    fig, axes = plt.subplots(1, len(physical), figsize=(4 * len(physical), 4.5))
    if len(physical) == 1:
        axes = [axes]

    for ax, attr in zip(axes, physical):
        x = summary[attr].astype(float)
        y = summary[TARGET_BIAS].astype(float)
        valid = x.notna() & y.notna()

        ax.scatter(x[valid], y[valid], alpha=0.7, s=45,
                   edgecolors="white", linewidths=0.4, color=C_POS)

        # label top-3 worst (lowest y)
        worst_idx = summary[valid][TARGET_BIAS].nsmallest(3).index
        for idx in worst_idx:
            ax.annotate(summary.loc[idx, "basin"], (x[idx], y[idx]),
                        fontsize=6, textcoords="offset points", xytext=(3, 3))

        ax.axhline(0, color="gray", linewidth=0.7, linestyle="--")
        rho = x[valid].corr(y[valid], method="spearman")
        ax.set_xlabel(label(attr), fontsize=10)
        ax.set_ylabel(TARGET_BIAS if ax is axes[0] else "", fontsize=10)
        ax.set_title(f"{label(attr)}\nρ = {rho:.3f}", fontsize=10)

    fig.suptitle(f"Physical basin attribute drivers vs {TARGET_BIAS}\n(seed median, 85 basins)", fontsize=11)
    fig.tight_layout()
    out = FIG_DIR / "q99_driver_scatter_top4.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


# ── Fig 3: Quartile radar (top-5 physical stable drivers) ────────────────────

def plot_quartile_radar(stable: pd.DataFrame, summary: pd.DataFrame) -> None:
    model_cols = {"model1_NSE", "model1_KGE", "model1_FHV", "model2_FHV",
                  "model1_med_rel_bias", "model1_Peak-MAPE", "model2_Peak-Timing"}
    top5 = stable[
        (stable["target"] == TARGET_BIAS) &
        (~stable["attribute"].isin(model_cols))
    ].head(5)["attribute"].tolist()
    top5 = [f for f in top5 if f in summary.columns]

    if len(top5) < 3:
        print("  [WARN] too few physical drivers for radar")
        return

    y = summary[TARGET_BIAS]
    worst = summary[y <= y.quantile(0.25)]
    best = summary[y >= y.quantile(0.75)]

    def norm(vals: pd.Series, feat: str) -> float:
        mn, mx = summary[feat].min(), summary[feat].max()
        if mx == mn:
            return 0.5
        return float((vals.median() - mn) / (mx - mn))

    N = len(top5)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]

    w_vals = [norm(worst[f], f) for f in top5] + [norm(worst[top5[0]], top5[0])]
    b_vals = [norm(best[f], f) for f in top5] + [norm(best[top5[0]], top5[0])]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.plot(angles, w_vals, color=C_WORST, linewidth=2, label=f"Q1 worst (n={len(worst)})")
    ax.fill(angles, w_vals, color=C_WORST, alpha=0.2)
    ax.plot(angles, b_vals, color=C_BEST, linewidth=2, label=f"Q4 best (n={len(best)})")
    ax.fill(angles, b_vals, color=C_BEST, alpha=0.2)
    ax.set_thetagrids(np.degrees(angles[:-1]), [label(f) for f in top5], fontsize=9)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75])
    ax.set_yticklabels(["25%", "50%", "75%"], fontsize=7)
    ax.set_title(f"Q1 vs Q4 basin profile\n(physical drivers of {TARGET_BIAS})", fontsize=11, pad=15)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1), fontsize=9)
    fig.tight_layout()
    out = FIG_DIR / "q99_quartile_radar.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


# ── Fig 4: Delta drivers bar (med_rel_bias_delta) ────────────────────────────

def plot_delta_drivers_bar(stable: pd.DataFrame) -> None:
    sub = stable[stable["target"] == TARGET_DELTA].head(12)
    sub = sub.sort_values("rho_median", key=abs, ascending=True)

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = [C_POS if r > 0 else C_NEG for r in sub["rho_median"]]
    ax.barh([label(a) for a in sub["attribute"]], sub["rho_median"], color=colors)
    ax.errorbar(
        sub["rho_median"], range(len(sub)),
        xerr=[sub["rho_median"] - sub["rho_min"], sub["rho_max"] - sub["rho_median"]],
        fmt="none", color="gray", linewidth=1, capsize=3,
    )
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Spearman ρ (seed median)", fontsize=11)
    ax.set_title(
        "Basin drivers of q99 improvement over model1\n"
        "(positive ρ → attr associated with more q99 improvement)",
        fontsize=11,
    )
    ax.set_xlim(-0.75, 0.75)
    fig.tight_layout()
    out = FIG_DIR / "q99_delta_drivers_bar.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    stable = pd.read_csv(TABLE_DIR / "q99_stable_drivers.csv")
    summary = pd.read_csv(TABLE_DIR / "basin_q99_error_summary.csv")
    summary["basin"] = summary["basin"].astype(str)

    print("── Fig 1: Spearman ρ bar …")
    plot_correlation_bar(stable)

    print("── Fig 2: Scatter top-4 physical drivers …")
    plot_scatter_top4(stable, summary)

    print("── Fig 3: Quartile radar …")
    plot_quartile_radar(stable, summary)

    print("── Fig 4: Delta drivers bar …")
    plot_delta_drivers_bar(stable)

    print("\nDone.")


if __name__ == "__main__":
    main()
