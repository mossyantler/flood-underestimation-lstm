#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "matplotlib>=3.9",
#   "scipy>=1.13",
# ]
# ///
"""Per-basin LSTM attribution aggregation and error correlation.

Uses q99_lstm_attribution.csv (event-level) to compute per-basin mean attribution
per forcing feature, then correlates with Q99 error metrics.

Question: do basins where the LSTM relies more on certain forcing features show
systematically higher/lower Q99 bias?

Outputs
-------
output/model_analysis/q99_analysis/tables/q99_lstm_attribution_basin.csv
output/model_analysis/q99_analysis/figures/q99_lstm_attribution_basin_correlation_bar.png
output/model_analysis/q99_analysis/figures/q99_lstm_attribution_basin_scatter.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parents[3]
TABLE_DIR = REPO_ROOT / "output/model_analysis/q99_analysis/tables"
FIG_DIR = REPO_ROOT / "output/model_analysis/q99_analysis/figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

DYNAMIC_FEATURES = [
    "Rainf", "Tair", "PotEvap", "SWdown", "Qair",
    "PSurf", "Wind_E", "Wind_N", "LWdown", "CAPE", "CRainf_frac",
]
FEAT_LABELS = {
    "Rainf": "Rainfall",
    "Tair": "Air temp",
    "PotEvap": "Pot. evap",
    "SWdown": "SW rad",
    "Qair": "Specific humidity",
    "PSurf": "Surface pressure",
    "Wind_E": "Wind E",
    "Wind_N": "Wind N",
    "LWdown": "LW rad",
    "CAPE": "CAPE",
    "CRainf_frac": "Conv. rain frac",
}

ERROR_TARGETS = ["q99_med_rel_bias", "q99_under_frac", "med_rel_bias_delta"]
ERROR_LABELS = {
    "q99_med_rel_bias": "Q99 med rel bias",
    "q99_under_frac": "Q99 under-fraction",
    "med_rel_bias_delta": "Bias delta (m1 − q99)",
}

C_POS = "#1f77b4"
C_NEG = "#d62728"


def build_basin_attribution(attr_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate event-level attribution to per-basin means."""
    attr_cols = [f"{f}_attr" for f in DYNAMIC_FEATURES]
    basin_attr = (
        attr_df.groupby("basin")[attr_cols + ["q99_peak_rel_error", "q99_under_frac_event"]]
        .agg(
            **{c: (c, "mean") for c in attr_cols},
            **{"mean_q99_peak_rel_error": ("q99_peak_rel_error", "mean"),
               "mean_under_frac": ("q99_under_frac_event", "mean"),
               "n_events": ("q99_peak_rel_error", "count")},
        )
        .reset_index()
    )
    # normalize each feature attribution as fraction of total attribution
    total = basin_attr[attr_cols].sum(axis=1)
    for c in attr_cols:
        basin_attr[c.replace("_attr", "_frac")] = basin_attr[c] / total
    return basin_attr


def spearman_attribution_vs_error(
    basin_attr: pd.DataFrame, error_summary: pd.DataFrame
) -> pd.DataFrame:
    merged = basin_attr.merge(error_summary[["basin"] + ERROR_TARGETS], on="basin", how="inner")
    print(f"  Merged basins: {len(merged)}")

    records = []
    for feat in DYNAMIC_FEATURES:
        for frac in [False, True]:
            col = f"{feat}_frac" if frac else f"{feat}_attr"
            if col not in merged.columns:
                continue
            x = merged[col].astype(float)
            for target in ERROR_TARGETS:
                y = merged[target].astype(float)
                valid = x.notna() & y.notna()
                if valid.sum() < 10:
                    continue
                rho, pval = stats.spearmanr(x[valid], y[valid])
                records.append({
                    "feature": feat,
                    "col": col,
                    "target": target,
                    "type": "fraction" if frac else "magnitude",
                    "rho": rho,
                    "pval": pval,
                    "n": int(valid.sum()),
                })
    return pd.DataFrame(records)


def plot_correlation_bar(corr: pd.DataFrame) -> None:
    for target in ERROR_TARGETS:
        sub = corr[(corr["target"] == target) & (corr["type"] == "fraction")]
        sub = sub.sort_values("rho", key=abs, ascending=True)
        if sub.empty:
            continue

        fig, ax = plt.subplots(figsize=(8, 5))
        colors = [C_POS if r > 0 else C_NEG for r in sub["rho"]]
        ax.barh([FEAT_LABELS.get(f, f) for f in sub["feature"]], sub["rho"], color=colors, alpha=0.8)
        ax.axvline(0, color="black", linewidth=0.8)
        for i, (_, row) in enumerate(sub.iterrows()):
            sig = "**" if row["pval"] < 0.01 else ("*" if row["pval"] < 0.05 else "")
            ax.text(row["rho"] + 0.005 * np.sign(row["rho"]), i,
                    f"ρ={row['rho']:.2f}{sig}", va="center", ha="left" if row["rho"] > 0 else "right",
                    fontsize=8)
        ax.set_xlabel("Spearman ρ (per-basin attribution fraction vs error metric)", fontsize=10)
        ax.set_title(
            f"LSTM feature reliance vs {ERROR_LABELS.get(target, target)}\n"
            f"(85 basins, seed111, GradientInput attribution fraction)",
            fontsize=10,
        )
        ax.legend(handles=[
            mpatches.Patch(color=C_POS, label="Higher reliance → higher error"),
            mpatches.Patch(color=C_NEG, label="Higher reliance → lower error"),
        ], fontsize=8)
        fig.tight_layout()
        fname = FIG_DIR / f"q99_lstm_attribution_basin_correlation_{target}.png"
        fig.savefig(fname, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  Saved: {fname.name}")


def plot_top_scatter(
    basin_attr: pd.DataFrame, error_summary: pd.DataFrame, corr: pd.DataFrame
) -> None:
    merged = basin_attr.merge(error_summary[["basin"] + ERROR_TARGETS], on="basin", how="inner")
    target = "q99_med_rel_bias"

    top = (
        corr[(corr["target"] == target) & (corr["type"] == "fraction")]
        .sort_values("rho", key=abs, ascending=False)
        .head(4)
    )
    if top.empty:
        return

    fig, axes = plt.subplots(1, len(top), figsize=(4.5 * len(top), 4.5))
    if len(top) == 1:
        axes = [axes]

    for ax, (_, row) in zip(axes, top.iterrows()):
        feat = row["feature"]
        col = f"{feat}_frac"
        x = merged[col].astype(float)
        y = merged[target].astype(float)
        valid = x.notna() & y.notna()

        ax.scatter(x[valid], y[valid], alpha=0.7, s=50, edgecolors="white", linewidths=0.4, color=C_POS)
        ax.axhline(0, color="gray", linewidth=0.7, linestyle="--")
        rho = row["rho"]
        pval = row["pval"]
        sig = "**" if pval < 0.01 else ("*" if pval < 0.05 else "")
        ax.set_xlabel(f"{FEAT_LABELS.get(feat, feat)} attribution frac", fontsize=9)
        ax.set_ylabel(target if ax is axes[0] else "", fontsize=9)
        ax.set_title(f"ρ={rho:.2f}{sig}", fontsize=10)

        # label worst 3
        worst = merged[valid].nsmallest(3, target)
        for _, wrow in worst.iterrows():
            ax.annotate(str(wrow["basin"]),
                        (x[wrow.name], y[wrow.name]),
                        fontsize=6, xytext=(3, 3), textcoords="offset points")

    fig.suptitle(
        f"Top feature attribution fractions vs {target}\n(85 basins, seed111)",
        fontsize=10
    )
    fig.tight_layout()
    out = FIG_DIR / "q99_lstm_attribution_basin_scatter.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


def main() -> None:
    print("── Loading data …")
    attr_df = pd.read_csv(TABLE_DIR / "q99_lstm_attribution.csv")
    attr_df["basin"] = attr_df["basin"].astype(str)
    error_summary = pd.read_csv(TABLE_DIR / "basin_q99_error_summary.csv")
    error_summary["basin"] = error_summary["basin"].astype(str).str.zfill(8)

    print("── Building per-basin attribution …")
    basin_attr = build_basin_attribution(attr_df)
    basin_attr["basin"] = basin_attr["basin"].astype(str).str.zfill(8)
    print(f"  {len(basin_attr)} basins")

    out_csv = TABLE_DIR / "q99_lstm_attribution_basin.csv"
    basin_attr.to_csv(out_csv, index=False)
    print(f"  Saved: {out_csv.name}")

    # top features by mean attribution
    attr_cols = [f"{f}_attr" for f in DYNAMIC_FEATURES]
    ranking = basin_attr[attr_cols].mean().sort_values(ascending=False)
    print("\n── Mean attribution magnitude per feature (across basins) ──")
    ranking.index = [c.replace("_attr", "") for c in ranking.index]
    print(ranking.to_string())

    print("\n── Spearman: attribution fraction vs Q99 error ──")
    corr = spearman_attribution_vs_error(basin_attr, error_summary)
    corr_csv = TABLE_DIR / "q99_lstm_attribution_basin_correlation.csv"
    corr.to_csv(corr_csv, index=False)
    print(f"  Saved: {corr_csv.name}")

    for target in ERROR_TARGETS:
        sub = corr[(corr["target"] == target) & (corr["type"] == "fraction")].sort_values("rho", key=abs, ascending=False)
        print(f"\n  [{target}]:")
        print(sub[["feature", "rho", "pval"]].head(6).to_string(index=False))

    print("\n── Plots …")
    plot_correlation_bar(corr)
    plot_top_scatter(basin_attr, error_summary, corr)

    print("\nDone.")


if __name__ == "__main__":
    main()
