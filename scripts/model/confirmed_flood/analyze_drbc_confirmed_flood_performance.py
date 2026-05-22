#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "matplotlib>=3.9",
# ]
# ///
"""DRBC confirmed flood event 성능 분석.

inference CSV에서 tier-stratified 집계와 Model 1 vs Model 2 paired delta를 계산한다.

입력: output/model_analysis/expanded/confirmed_flood/performance/drbc_confirmed_flood_performance.csv
출력: output/model_analysis/expanded/confirmed_flood/analysis/
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PERF_CSV = ROOT / "output/model_analysis/expanded/confirmed_flood/performance/drbc_confirmed_flood_performance.csv"
DEFAULT_OUTPUT_DIR = ROOT / "output/model_analysis/expanded/confirmed_flood/analysis"
TIERS = ["minor", "moderate", "major"]
QUANTILE_ORDER = ["det", "q50", "q90", "q95", "q99"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--perf-csv", type=Path, default=DEFAULT_PERF_CSV)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return p.parse_args()


def compute_tier_aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """flood_tier × model × quantile별 지표 집계."""
    records = []
    for (tier, model, quantile), grp in df.groupby(["flood_tier", "model", "quantile"]):
        obs = grp["obs_peak_cms"].dropna()
        under = grp["peak_under_deficit"].dropna()
        records.append({
            "flood_tier": tier,
            "model": model,
            "quantile": quantile,
            "n_events": len(grp),
            "n_basins": int(grp["usgs_id"].nunique()),
            "median_obs_peak_cms": float(obs.median()) if len(obs) else None,
            "underestimation_fraction": float((grp["is_underestimate"] == True).mean()),
            "median_under_deficit": float(under.median()) if len(under) else None,
            "median_event_nrmse": float(grp["event_nrmse"].dropna().median()) if grp["event_nrmse"].notna().any() else None,
            "noaa_corroborated_fraction": float(grp["noaa_corroborated"].mean()) if "noaa_corroborated" in grp.columns else None,
        })
    return pd.DataFrame(records)


def compute_paired_delta(df: pd.DataFrame) -> pd.DataFrame:
    """Model 2 quantile vs Model 1 paired delta (같은 seed × event 기준)."""
    m1 = df[df["model"] == "model1"][
        ["usgs_id", "peak_time", "seed", "peak_under_deficit"]
    ].rename(columns={"peak_under_deficit": "m1_under_deficit"})
    m2 = df[df["model"] == "model2"].copy()
    merged = m2.merge(m1, on=["usgs_id", "peak_time", "seed"])
    merged["under_deficit_reduction"] = merged["m1_under_deficit"] - merged["peak_under_deficit"]
    records = []
    for (tier, quantile), grp in merged.groupby(["flood_tier", "quantile"]):
        records.append({
            "flood_tier": tier,
            "quantile": quantile,
            "n_events": len(grp),
            "median_under_deficit_reduction": float(grp["under_deficit_reduction"].dropna().median()),
            "median_event_nrmse": float(grp["event_nrmse"].dropna().median()) if grp["event_nrmse"].notna().any() else None,
        })
    return pd.DataFrame(records)


def plot_tier_comparison(agg: pd.DataFrame, output_path: Path) -> None:
    """tier별 median peak under-deficit bar chart (model × quantile)."""
    present_tiers = [t for t in TIERS if t in agg["flood_tier"].values]
    if not present_tiers:
        return
    fig, axes = plt.subplots(1, len(present_tiers), figsize=(5 * len(present_tiers), 5), sharey=False)
    if len(present_tiers) == 1:
        axes = [axes]
    for ax, tier in zip(axes, present_tiers):
        subset = agg[agg["flood_tier"] == tier].copy()
        subset["label"] = subset["model"] + " " + subset["quantile"]
        label_order = (
            ["model1 det"] +
            [f"model2 {q}" for q in QUANTILE_ORDER if q != "det"]
        )
        subset = subset.set_index("label")
        subset = subset.reindex([l for l in label_order if l in subset.index])
        vals = subset["median_under_deficit"].fillna(0).values
        colors = ["steelblue" if "model1" in l else "tomato" for l in subset.index]
        ax.bar(range(len(subset)), vals, color=colors, tick_label=list(subset.index))
        ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
        ax.set_title(f"Flood tier: {tier}", fontsize=10)
        ax.set_ylabel("Median peak under-deficit")
        ax.tick_params(axis="x", rotation=45)
    fig.suptitle("Model 1 vs Model 2 — NWS Confirmed Flood Events", fontsize=12)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote figure: {output_path}")


def plot_quantile_coverage_progression(df: pd.DataFrame, output_path: Path) -> None:
    """각 quantile에서 obs_peak <= pred_peak 비율 (coverage rate). tier별로 subplot."""
    quantiles = ["q50", "q90", "q95", "q99"]
    tier_colors = {"minor": "#fbbf24", "moderate": "#f97316", "major": "#dc2626"}
    present_tiers = [t for t in TIERS if t in df["flood_tier"].values]
    seeds = sorted(df["seed"].unique())

    fig, axes = plt.subplots(1, len(present_tiers), figsize=(5 * len(present_tiers), 5), sharey=True)
    if len(present_tiers) == 1:
        axes = [axes]

    for ax, tier in zip(axes, present_tiers):
        for seed in seeds:
            rates = []
            for q in quantiles:
                rows = df[(df["flood_tier"] == tier) & (df["quantile"] == q) & (df["seed"] == seed)]
                if rows.empty:
                    rates.append(float("nan"))
                    continue
                # coverage = not underestimate
                cov = (~(rows["is_underestimate"] == True)).mean()
                rates.append(float(cov))
            ax.plot(range(len(quantiles)), rates, marker="o", label=f"seed {seed}", alpha=0.8)
        ax.set_xticks(range(len(quantiles)), quantiles)
        ax.set_xlabel("Model 2 Quantile")
        ax.set_ylim(0, 1.05)
        ax.axhline(0.5, color="#9ca3af", linestyle=":", linewidth=0.8)
        for q_target, alpha in [(0.9, 0.4), (0.95, 0.3), (0.99, 0.2)]:
            ax.axhline(q_target, color="#374151", linestyle="--", linewidth=0.7, alpha=alpha)
        ax.set_title(f"{tier.capitalize()} Flood")
        ax.grid(True, axis="y", color="#e5e7eb", linewidth=0.7)
        if ax == axes[0]:
            ax.set_ylabel("Coverage Rate (obs ≤ pred peak)")
            ax.legend(fontsize=8)

    fig.suptitle("Confirmed Flood Peak Coverage Rate by Quantile (obs ≤ predicted peak)", fontsize=11)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote figure: {output_path}")


def plot_underestimation_by_tier_seed(df: pd.DataFrame, output_path: Path) -> None:
    """seed별 tier별 과소추정 비율 — Model 1 det vs Model 2 q50."""
    seeds = sorted(df["seed"].unique())
    tier_colors = {"minor": "#fbbf24", "moderate": "#f97316", "major": "#dc2626"}
    present_tiers = [t for t in TIERS if t in df["flood_tier"].values]
    x = np.arange(len(seeds))
    width = 0.22

    fig, axes = plt.subplots(1, len(present_tiers), figsize=(5 * len(present_tiers), 5), sharey=True)
    if len(present_tiers) == 1:
        axes = [axes]

    for ax, tier in zip(axes, present_tiers):
        m1_rates = [
            (df[(df["quantile"] == "det") & (df["seed"] == s) & (df["flood_tier"] == tier)]["is_underestimate"] == True).mean()
            for s in seeds
        ]
        m2_rates = [
            (df[(df["quantile"] == "q50") & (df["seed"] == s) & (df["flood_tier"] == tier)]["is_underestimate"] == True).mean()
            for s in seeds
        ]
        ax.bar(x - width / 2, m1_rates, width, label="Model 1 (det)", color="#fecaca", edgecolor="#dc2626", linewidth=0.9)
        ax.bar(x + width / 2, m2_rates, width, label="Model 2 (q50)", color="#93c5fd", edgecolor="#2563eb", linewidth=0.9)
        ax.axhline(0.5, color="#6b7280", linestyle="--", linewidth=0.8, alpha=0.7)
        for xi, (r1, r2) in enumerate(zip(m1_rates, m2_rates)):
            ax.text(xi - width / 2, r1 + 0.01, f"{r1:.0%}", ha="center", va="bottom", fontsize=8, color="#7f1d1d")
            ax.text(xi + width / 2, r2 + 0.01, f"{r2:.0%}", ha="center", va="bottom", fontsize=8, color="#1e3a8a")
        ax.set_xticks(x, [str(s) for s in seeds])
        ax.set_xlabel("Seed")
        ax.set_ylim(0, 1.2)
        ax.set_title(f"{tier.capitalize()} Flood")
        ax.grid(True, axis="y", color="#e5e7eb", linewidth=0.7)
        if ax == axes[0]:
            ax.set_ylabel("Underestimation Rate")
            ax.legend(fontsize=8)

    fig.suptitle("Confirmed Flood Underestimation Rate by Tier and Seed — Model 1 vs Model 2 q50", fontsize=11)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote figure: {output_path}")


def plot_noaa_robustness(agg_all: pd.DataFrame, agg_noaa: pd.DataFrame, output_path: Path) -> None:
    """NOAA-corroborated 부분집합 vs 전체 비교 figure."""
    both = pd.merge(
        agg_all[["flood_tier", "model", "quantile", "median_under_deficit"]].rename(
            columns={"median_under_deficit": "all_events"}),
        agg_noaa[["flood_tier", "model", "quantile", "median_under_deficit"]].rename(
            columns={"median_under_deficit": "noaa_only"}),
        on=["flood_tier", "model", "quantile"], how="inner",
    )
    if both.empty:
        return
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(both["all_events"], both["noaa_only"], alpha=0.7)
    lim = max(both[["all_events", "noaa_only"]].abs().max().max(), 0.01)
    ax.plot([-lim, lim], [-lim, lim], "k--", linewidth=0.8)
    ax.set_xlabel("All events — median peak under-deficit")
    ax.set_ylabel("NOAA-corroborated only")
    ax.set_title("NOAA Robustness: All vs Corroborated Events")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote figure: {output_path}")


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "figures").mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.perf_csv, dtype={"usgs_id": str})
    df["usgs_id"] = df["usgs_id"].str.zfill(8)
    print(f"Loaded {len(df)} rows from {args.perf_csv}")

    # Tier aggregate — 전체
    agg = compute_tier_aggregate(df)
    agg.to_csv(args.output_dir / "confirmed_flood_tier_aggregate.csv", index=False)
    print("\n=== Tier aggregate ===")
    print(agg[["flood_tier", "model", "quantile", "n_events",
                "underestimation_fraction", "median_under_deficit"]].to_string(index=False))

    # Paired delta
    delta = compute_paired_delta(df)
    delta.to_csv(args.output_dir / "confirmed_flood_paired_delta.csv", index=False)
    print("\n=== Paired delta (Model2 - Model1 under-deficit reduction) ===")
    print(delta.to_string(index=False))

    # NOAA robustness
    if "noaa_corroborated" in df.columns and df["noaa_corroborated"].any():
        noaa_df = df[df["noaa_corroborated"] == True]
        agg_noaa = compute_tier_aggregate(noaa_df)
        agg_noaa.to_csv(args.output_dir / "confirmed_flood_tier_aggregate_noaa.csv", index=False)
        plot_noaa_robustness(
            agg, agg_noaa,
            args.output_dir / "figures" / "confirmed_flood_noaa_robustness.png",
        )

    # Figures
    plot_tier_comparison(agg, args.output_dir / "figures" / "confirmed_flood_tier_comparison.png")
    plot_quantile_coverage_progression(df, args.output_dir / "figures" / "confirmed_flood_quantile_coverage.png")
    plot_underestimation_by_tier_seed(df, args.output_dir / "figures" / "confirmed_flood_underestimation_by_tier_seed.png")


if __name__ == "__main__":
    main()
