#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "matplotlib>=3.9",
#   "scipy>=1.13",
# ]
# ///
"""Aggregate Q99 LSTM GradientInput attribution across 3 seeds.

Reads q99_lstm_attribution_seed{111,222,444}.csv and produces:
  - Seed-median feature ranking with min/max range
  - Stable features: all 3 seeds agree on rank order (top-3)
  - Combined feature importance bar (median + seed range)
  - Temporal lag profile (median across seeds)
  - Stratified bar (under vs over, seed median)

Outputs
-------
output/model_analysis/q99_analysis/tables/q99_lstm_attribution_multiseed_summary.csv
output/model_analysis/q99_analysis/figures/q99_lstm_feature_importance_multiseed.png
output/model_analysis/q99_analysis/figures/q99_lstm_temporal_lag_multiseed.png
output/model_analysis/q99_analysis/figures/q99_lstm_attribution_stratified_multiseed.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parents[3]
TABLE_DIR = REPO_ROOT / "output/model_analysis/q99_analysis/tables"
FIG_DIR = REPO_ROOT / "output/model_analysis/q99_analysis/figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

SEEDS = [111, 222, 444]
DYNAMIC_FEATURES = [
    "Rainf", "Tair", "PotEvap", "SWdown", "Qair",
    "PSurf", "Wind_E", "Wind_N", "LWdown", "CAPE", "CRainf_frac",
]
FEAT_LABELS = {
    "Rainf": "Rainfall (Rainf)",
    "Tair": "Air temp (Tair)",
    "PotEvap": "Pot. evap (PotEvap)",
    "SWdown": "SW radiation (SWdown)",
    "Qair": "Specific humidity (Qair)",
    "PSurf": "Surface pressure (PSurf)",
    "Wind_E": "Wind E",
    "Wind_N": "Wind N",
    "LWdown": "LW radiation (LWdown)",
    "CAPE": "CAPE",
    "CRainf_frac": "Conv. rain frac",
}
ATTR_COLS = [f"{f}_attr" for f in DYNAMIC_FEATURES]

C_MAIN = "#1f77b4"
C_UNDER = "#d62728"
C_OVER = "#2ca02c"


def load_seed_dfs() -> dict[int, pd.DataFrame]:
    dfs = {}
    for seed in SEEDS:
        p = TABLE_DIR / f"q99_lstm_attribution_seed{seed}.csv"
        if not p.exists():
            print(f"  [WARN] missing: {p.name}")
            continue
        dfs[seed] = pd.read_csv(p)
    return dfs


def build_feature_summary(dfs: dict[int, pd.DataFrame]) -> pd.DataFrame:
    """Per-seed mean attribution → seed-median summary table."""
    records = []
    for feat in DYNAMIC_FEATURES:
        col = f"{feat}_attr"
        seed_means = {}
        for seed, df in dfs.items():
            if col in df.columns:
                seed_means[seed] = float(df[col].mean())
        if not seed_means:
            continue
        vals = list(seed_means.values())
        records.append({
            "feature": feat,
            "label": FEAT_LABELS[feat],
            "attr_median": float(np.median(vals)),
            "attr_min": float(np.min(vals)),
            "attr_max": float(np.max(vals)),
            **{f"attr_seed{s}": seed_means.get(s, np.nan) for s in SEEDS},
        })
    return pd.DataFrame(records).sort_values("attr_median", ascending=False).reset_index(drop=True)


def plot_feature_importance_multiseed(summary: pd.DataFrame, n_events: dict[int, int]) -> None:
    sub = summary.sort_values("attr_median")  # ascending for barh
    n_str = " / ".join(f"{n_events.get(s, '?')}" for s in SEEDS)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(sub["label"], sub["attr_median"], color=C_MAIN, alpha=0.8, label="Seed median")
    ax.errorbar(
        sub["attr_median"], range(len(sub)),
        xerr=[sub["attr_median"] - sub["attr_min"], sub["attr_max"] - sub["attr_median"]],
        fmt="none", color="gray", linewidth=1.2, capsize=4,
        label="Seed min/max",
    )
    ax.set_xlabel("Mean |gradient × input| (GradientInput)", fontsize=10)
    ax.set_title(
        f"LSTM feature importance for Q99 predictions\n"
        f"(3-seed median ± range, events: {n_str})",
        fontsize=10,
    )
    ax.legend(fontsize=8)
    fig.tight_layout()
    out = FIG_DIR / "q99_lstm_feature_importance_multiseed.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out.name}")


def plot_temporal_lag_multiseed(dfs: dict[int, pd.DataFrame]) -> None:
    lags_h = [0, 24, 48, 72, 96, 120, 168, 240, 336]
    top_feats = ["Rainf", "Qair", "Tair", "PotEvap"]
    colors = plt.cm.tab10(np.linspace(0, 0.5, len(top_feats)))

    fig, ax = plt.subplots(figsize=(8, 5))
    for feat, col in zip(top_feats, colors):
        lag_cols = [f"{feat}_lag{lag}h" for lag in lags_h]
        seed_series = []
        for df in dfs.values():
            avail = [c for c in lag_cols if c in df.columns]
            if avail:
                seed_series.append(df[avail].mean().values)
        if not seed_series:
            continue
        arr = np.array(seed_series)  # [n_seeds, n_lags]
        med = np.median(arr, axis=0)
        lo = arr.min(axis=0)
        hi = arr.max(axis=0)
        n = min(len(med), len(lags_h))
        ax.plot(lags_h[:n], med[:n], marker="o", label=FEAT_LABELS[feat], color=col)
        ax.fill_between(lags_h[:n], lo[:n], hi[:n], color=col, alpha=0.15)

    ax.set_xlabel("Hours before event peak", fontsize=10)
    ax.set_ylabel("Mean |gradient × input|", fontsize=10)
    ax.set_title("Temporal sensitivity: lookback importance for Q99 peak\n(seed median ± range)", fontsize=10)
    ax.legend(fontsize=9)
    ax.invert_xaxis()
    fig.tight_layout()
    out = FIG_DIR / "q99_lstm_temporal_lag_multiseed.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out.name}")


def plot_stratified_multiseed(dfs: dict[int, pd.DataFrame]) -> None:
    labels = [FEAT_LABELS[f] for f in DYNAMIC_FEATURES]

    under_means, over_means = [], []
    for df in dfs.values():
        under = df[df["q99_under_frac_event"] >= 0.5][ATTR_COLS]
        over = df[df["q99_under_frac_event"] < 0.5][ATTR_COLS]
        if not under.empty:
            under_means.append(under.mean().values)
        if not over.empty:
            over_means.append(over.mean().values)

    if not under_means or not over_means:
        return

    under_med = np.median(under_means, axis=0)
    over_med = np.median(over_means, axis=0)
    n_u = sum(len(df[df["q99_under_frac_event"] >= 0.5]) for df in dfs.values())
    n_o = sum(len(df[df["q99_under_frac_event"] < 0.5]) for df in dfs.values())

    x = np.arange(len(DYNAMIC_FEATURES))
    width = 0.35
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x - width/2, under_med, width, label=f"Underest. (n={n_u})", color=C_UNDER, alpha=0.8)
    ax.bar(x + width/2, over_med, width, label=f"Overest. (n={n_o})", color=C_OVER, alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Mean |gradient × input| (seed median)", fontsize=10)
    ax.set_title(
        "LSTM feature attribution: underestimation vs overestimation events\n"
        "(3-seed median, q99_under_frac_event >= 0.5 = underestimation)",
        fontsize=10,
    )
    ax.legend(fontsize=9)
    fig.tight_layout()
    out = FIG_DIR / "q99_lstm_attribution_stratified_multiseed.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out.name}")


def main() -> None:
    print("── Loading per-seed attribution tables …")
    dfs = load_seed_dfs()
    if not dfs:
        print("ERROR: no attribution tables found. Run compute_q99_lstm_attribution.py first.")
        return
    print(f"  Loaded seeds: {list(dfs.keys())}")

    n_events = {s: len(df) for s, df in dfs.items()}

    print("── Building feature summary …")
    summary = build_feature_summary(dfs)
    out_csv = TABLE_DIR / "q99_lstm_attribution_multiseed_summary.csv"
    summary.to_csv(out_csv, index=False)
    print(f"Saved: {out_csv.name}")

    print("\n── Feature ranking (seed median) ──")
    print(summary[["feature", "attr_median", "attr_min", "attr_max"]].to_string(index=False))

    print("\n── Plots …")
    plot_feature_importance_multiseed(summary, n_events)
    plot_temporal_lag_multiseed(dfs)
    plot_stratified_multiseed(dfs)

    print("\nDone.")


if __name__ == "__main__":
    main()
