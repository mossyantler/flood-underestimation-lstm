#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.8",
#   "pandas>=2.2",
# ]
# ///

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D


SPLIT_COLORS = {
    "train": "#1f77b4",
    "validation": "#ff7f0e",
    "test": "#2ca02c",
    "except": "#7f7f7f",
}

WINDOW_SPANS = [
    ("train window", 2000, 2010, "#dbeafe"),
    ("validation window", 2011, 2013, "#ffedd5"),
    ("test window", 2014, 2016, "#dcfce7"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot basin-level usable-year timelines from a prepared split manifest."
    )
    parser.add_argument(
        "--manifest-csv",
        type=Path,
        default=Path("data/CAMELSH_generic/drbc_holdout_broad/splits/split_manifest.csv"),
        help="Prepared split manifest CSV with usable-year columns.",
    )
    parser.add_argument(
        "--output-png",
        type=Path,
        default=Path("output/basin/checklists/plots/drbc_holdout_broad_usable_year_timeline.png"),
        help="Output PNG path.",
    )
    parser.add_argument(
        "--output-svg",
        type=Path,
        default=Path("output/basin/checklists/plots/drbc_holdout_broad_usable_year_timeline.svg"),
        help="Optional SVG path for vector export.",
    )
    return parser.parse_args()


def load_manifest(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"gauge_id": str})
    required = {
        "gauge_id",
        "original_split",
        "prepared_split_status",
        "first_obs_year_usable",
        "last_obs_year_usable",
        "obs_years_usable",
    }
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Manifest에 필요한 열이 없습니다: {sorted(missing)}")

    for col in ["first_obs_year_usable", "last_obs_year_usable", "obs_years_usable"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["first_obs_year_usable", "last_obs_year_usable"]).copy()
    df["timeline_group"] = df["prepared_split_status"].where(
        df["prepared_split_status"].isin({"train", "validation", "test"}),
        "except",
    )
    df = df.sort_values(
        ["first_obs_year_usable", "last_obs_year_usable", "timeline_group", "gauge_id"],
        ascending=[True, True, True, True],
    ).reset_index(drop=True)
    df["plot_y"] = range(len(df))
    return df


def build_summary_text(df: pd.DataFrame) -> str:
    n = len(df)
    p25 = int(df["first_obs_year_usable"].quantile(0.25))
    median = int(df["first_obs_year_usable"].quantile(0.50))
    p75 = int(df["first_obs_year_usable"].quantile(0.75))
    span_2000_2016 = (
        (df["first_obs_year_usable"] <= 2000) & (df["last_obs_year_usable"] >= 2016)
    ).sum()
    return (
        f"Basins: {n} | "
        f"first usable year p25/median/p75 = {p25}/{median}/{p75} | "
        f"usable span covering 2000-2016: {span_2000_2016}/{n}"
    )


def make_plot(df: pd.DataFrame, output_png: Path, output_svg: Path | None) -> None:
    output_png.parent.mkdir(parents=True, exist_ok=True)
    if output_svg is not None:
        output_svg.parent.mkdir(parents=True, exist_ok=True)

    n_rows = len(df)
    fig_height = max(10, min(30, n_rows / 85))
    fig, ax = plt.subplots(figsize=(16, fig_height))

    for _, start, end, color in WINDOW_SPANS:
        ax.axvspan(start - 0.5, end + 0.5, color=color, alpha=0.75, zorder=0)

    for group, group_df in df.groupby("timeline_group", sort=False):
        ax.hlines(
            y=group_df["plot_y"],
            xmin=group_df["first_obs_year_usable"],
            xmax=group_df["last_obs_year_usable"],
            color=SPLIT_COLORS[group],
            linewidth=1.1 if group != "except" else 0.9,
            alpha=0.85 if group != "except" else 0.55,
            zorder=3,
        )

    for year in range(1980, 2026, 5):
        ax.axvline(year, color="#d4d4d8", linewidth=0.6, alpha=0.7, zorder=1)

    ax.set_xlim(1980, 2025)
    ax.set_ylim(-5, n_rows + 5)
    ax.set_xlabel("Usable year")
    ax.set_ylabel("Basins sorted by first usable year")
    ax.set_title("CAMELSH DRBC Holdout Broad Split: Basin-Level Usable-Year Timelines")
    ax.set_yticks([])
    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)

    summary_text = build_summary_text(df)
    fig.text(0.01, 0.99, summary_text, ha="left", va="top", fontsize=10)

    legend_handles = [
        Line2D([0], [0], color=SPLIT_COLORS["train"], lw=2, label="train basin"),
        Line2D([0], [0], color=SPLIT_COLORS["validation"], lw=2, label="validation basin"),
        Line2D([0], [0], color=SPLIT_COLORS["test"], lw=2, label="test basin"),
        Line2D([0], [0], color=SPLIT_COLORS["except"], lw=2, label="except after usability gate"),
    ]
    ax.legend(handles=legend_handles, loc="lower right", frameon=True)

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(output_png, dpi=200)
    if output_svg is not None:
        fig.savefig(output_svg)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    if not args.manifest_csv.exists():
        raise SystemExit(f"Manifest CSV가 없습니다: {args.manifest_csv}")

    df = load_manifest(args.manifest_csv)
    make_plot(df, args.output_png, args.output_svg)

    print(f"Saved PNG: {args.output_png}")
    if args.output_svg is not None:
        print(f"Saved SVG: {args.output_svg}")


if __name__ == "__main__":
    main()
