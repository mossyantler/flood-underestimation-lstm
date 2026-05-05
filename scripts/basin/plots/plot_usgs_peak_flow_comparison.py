#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.8",
#   "numpy>=2.0",
#   "pandas>=2.2",
# ]
# ///

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


RETURN_PERIODS = (2, 5, 10, 25, 50, 100)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare CAMELSH hourly flood_ari proxy values against USGS StreamStats peak-flow references."
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=Path("output/basin/all/reference_comparison/usgs_flood/tables/return_period_reference_table_with_usgs.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/basin/all"),
        help="All-basin output root. Tables and figures are written under reference_comparison/usgs_flood.",
    )
    return parser.parse_args()


def build_long_table(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for period in RETURN_PERIODS:
        camelsh = pd.to_numeric(frame[f"flood_ari{period}"], errors="coerce")
        usgs = pd.to_numeric(frame[f"usgs_flood_ari{period}"], errors="coerce")
        valid = camelsh.notna() & usgs.notna() & (camelsh > 0) & (usgs > 0)
        sub = frame.loc[valid, ["gauge_id", "gauge_name", "state", "huc02"]].copy()
        sub["return_period"] = period
        sub["camelsh_flood_ari"] = camelsh.loc[valid].to_numpy()
        sub["usgs_flood_ari"] = usgs.loc[valid].to_numpy()
        sub["camelsh_to_usgs_ratio"] = sub["camelsh_flood_ari"] / sub["usgs_flood_ari"]
        sub["relative_difference"] = (sub["camelsh_flood_ari"] - sub["usgs_flood_ari"]) / sub["usgs_flood_ari"]
        rows.append(sub)
    return pd.concat(rows, ignore_index=True)


def summarize(long_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for period, group in long_df.groupby("return_period"):
        rel = group["relative_difference"]
        ratio = group["camelsh_to_usgs_ratio"]
        rows.append(
            {
                "return_period": int(period),
                "matched_count": int(len(group)),
                "median_camelsh_to_usgs_ratio": float(ratio.median()),
                "median_relative_difference": float(rel.median()),
                "mean_relative_difference": float(rel.mean()),
                "p10_relative_difference": float(rel.quantile(0.10)),
                "p25_relative_difference": float(rel.quantile(0.25)),
                "p75_relative_difference": float(rel.quantile(0.75)),
                "p90_relative_difference": float(rel.quantile(0.90)),
                "fraction_camelsh_below_usgs": float((rel < 0).mean()),
                "fraction_abs_difference_ge_25pct": float((rel.abs() >= 0.25).mean()),
                "fraction_abs_difference_ge_50pct": float((rel.abs() >= 0.50).mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("return_period")


def save_scatter_grid(long_df: pd.DataFrame, summary: pd.DataFrame, out_path: Path) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(15, 9), constrained_layout=True)
    axes = axes.ravel()
    for ax, period in zip(axes, RETURN_PERIODS):
        group = long_df[long_df["return_period"] == period]
        stat = summary[summary["return_period"] == period].iloc[0]
        x = group["usgs_flood_ari"]
        y = group["camelsh_flood_ari"]
        lim_min = min(x.min(), y.min()) * 0.75
        lim_max = max(x.max(), y.max()) * 1.35
        ax.scatter(x, y, s=12, alpha=0.32, color="#2563a6", edgecolors="none")
        ax.plot([lim_min, lim_max], [lim_min, lim_max], color="#b23a48", linewidth=1.4, linestyle="--")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlim(lim_min, lim_max)
        ax.set_ylim(lim_min, lim_max)
        ax.grid(True, which="both", linewidth=0.35, alpha=0.35)
        ax.set_title(
            f"{period}-year: n={len(group)}, median ratio={stat['median_camelsh_to_usgs_ratio']:.2f}",
            fontsize=11,
        )
        ax.set_xlabel("USGS peak-flow reference (m3/s)")
        ax.set_ylabel("CAMELSH hourly proxy (m3/s)")
    fig.suptitle("CAMELSH Proxy vs USGS StreamStats Peak-Flow Reference", fontsize=15)
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def save_relative_boxplot(long_df: pd.DataFrame, out_path: Path) -> None:
    data = [
        long_df.loc[long_df["return_period"] == period, "relative_difference"].dropna().to_numpy() * 100
        for period in RETURN_PERIODS
    ]
    fig, ax = plt.subplots(figsize=(11, 6), constrained_layout=True)
    box = ax.boxplot(data, tick_labels=[str(period) for period in RETURN_PERIODS], patch_artist=True, showfliers=True)
    for patch in box["boxes"]:
        patch.set_facecolor("#8ecae6")
        patch.set_edgecolor("#2f4858")
        patch.set_alpha(0.85)
    for median in box["medians"]:
        median.set_color("#b23a48")
        median.set_linewidth(1.8)
    for flier in box["fliers"]:
        flier.set_marker(".")
        flier.set_markeredgecolor("#6b7280")
        flier.set_alpha(0.25)
    ax.axhline(0, color="#1f2937", linewidth=1.0, linestyle="--")
    ax.set_xlabel("Return period (years)")
    ax.set_ylabel("Relative difference: (CAMELSH - USGS) / USGS (%)")
    ax.set_title("Relative Difference by Return Period")
    ax.grid(axis="y", linewidth=0.4, alpha=0.35)
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def save_median_trend(summary: pd.DataFrame, out_path: Path) -> None:
    x = summary["return_period"].to_numpy(dtype=float)
    median = summary["median_relative_difference"].to_numpy(dtype=float) * 100
    p25 = summary["p25_relative_difference"].to_numpy(dtype=float) * 100
    p75 = summary["p75_relative_difference"].to_numpy(dtype=float) * 100
    p10 = summary["p10_relative_difference"].to_numpy(dtype=float) * 100
    p90 = summary["p90_relative_difference"].to_numpy(dtype=float) * 100

    fig, ax = plt.subplots(figsize=(11, 6), constrained_layout=True)
    ax.fill_between(x, p10, p90, color="#b8c0ff", alpha=0.25, label="P10-P90")
    ax.fill_between(x, p25, p75, color="#3a86ff", alpha=0.25, label="IQR")
    ax.plot(x, median, marker="o", color="#1d4ed8", linewidth=2.2, label="Median")
    ax.axhline(0, color="#1f2937", linewidth=1.0, linestyle="--")
    ax.set_xscale("log")
    ax.set_xticks(list(RETURN_PERIODS))
    ax.set_xticklabels([str(period) for period in RETURN_PERIODS])
    ax.set_xlabel("Return period (years)")
    ax.set_ylabel("Relative difference (%)")
    ax.set_title("CAMELSH Proxy Bias Increases Toward Rarer Floods")
    ax.grid(True, linewidth=0.4, alpha=0.35)
    ax.legend(frameon=False)
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    table_dir = args.output_dir / "reference_comparison" / "usgs_flood" / "tables"
    figure_dir = args.output_dir / "reference_comparison" / "usgs_flood" / "figures"
    table_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    frame = pd.read_csv(args.input_csv, dtype={"gauge_id": str})
    long_df = build_long_table(frame)
    summary = summarize(long_df)

    long_path = table_dir / "usgs_vs_camelsh_flood_ari_long.csv"
    summary_path = table_dir / "usgs_vs_camelsh_flood_ari_summary.csv"
    long_df.to_csv(long_path, index=False)
    summary.to_csv(summary_path, index=False)

    save_scatter_grid(long_df, summary, figure_dir / "usgs_vs_camelsh_scatter_grid.png")
    save_relative_boxplot(long_df, figure_dir / "relative_difference_boxplot.png")
    save_median_trend(summary, figure_dir / "relative_difference_median_trend.png")

    print(f"Wrote long table: {long_path}")
    print(f"Wrote summary: {summary_path}")
    print(f"Wrote charts: {figure_dir}")
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.4f}"))


if __name__ == "__main__":
    main()
