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

입력: output/model_analysis/confirmed_flood/performance/drbc_confirmed_flood_performance.csv
출력: output/model_analysis/confirmed_flood/analysis/
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
DEFAULT_PERF_CSV = ROOT / "output/model_analysis/confirmed_flood/performance/drbc_confirmed_flood_performance.csv"
DEFAULT_OUTPUT_DIR = ROOT / "output/model_analysis/confirmed_flood/analysis"
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
        # 정렬: model1 det 먼저, model2 quantile 순
        label_order = (
            ["model1 det"] +
            [f"model2 {q}" for q in QUANTILE_ORDER if q != "det"]
        )
        subset = subset.set_index("label").reindex([l for l in label_order if l in subset.index])
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


if __name__ == "__main__":
    main()
