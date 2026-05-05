#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.9",
#   "pandas>=2.2",
# ]
# ///

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import colors


SCOPE_ORDER = ["combined", "train", "validation"]
SUBSET_ORDER = [100, 300, 600]
ATTRIBUTE_ORDER = [
    "area",
    "slope",
    "aridity",
    "snow_fraction",
    "soil_depth",
    "permeability",
    "forest_fraction",
    "baseflow_index",
]
ATTRIBUTE_LABELS = {
    "area": "Area",
    "slope": "Slope",
    "aridity": "Aridity",
    "snow_fraction": "Snow Fraction",
    "soil_depth": "Soil Depth",
    "permeability": "Permeability",
    "forest_fraction": "Forest Fraction",
    "baseflow_index": "Baseflow Index",
}
SCOPE_LABELS = {
    "combined": "Combined",
    "train": "Train",
    "validation": "Validation",
}
SUBSET_COLORS = {
    100: "#c84c24",
    300: "#2f6ea0",
    600: "#3f8f55",
}
SCOPE_COLORS = {
    "combined": "#1f4e79",
    "train": "#4f772d",
    "validation": "#c84c24",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create interpretation plots for scaling-pilot static-attribute diagnostics."
        )
    )
    parser.add_argument(
        "--comparisons-csv",
        type=Path,
        default=Path("configs/pilot/diagnostics/attribute_distribution_comparisons.csv"),
        help="Comparison table produced by build_scaling_pilot_attribute_diagnostics.py",
    )
    parser.add_argument(
        "--scope-summary-csv",
        type=Path,
        default=Path("configs/pilot/diagnostics/attribute_distribution_scope_summary.csv"),
        help="Scope summary table produced by build_scaling_pilot_attribute_diagnostics.py",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("configs/pilot/diagnostics/plots"),
        help="Directory where SVG plots and a plot manifest will be written.",
    )
    return parser.parse_args()


def ordered_scope(scope: str) -> int:
    try:
        return SCOPE_ORDER.index(scope)
    except ValueError:
        return len(SCOPE_ORDER)


def ordered_attribute(attribute: str) -> int:
    try:
        return ATTRIBUTE_ORDER.index(attribute)
    except ValueError:
        return len(ATTRIBUTE_ORDER)


def plot_scope_summary(scope_summary_df: pd.DataFrame, output_path: Path) -> None:
    ordered = scope_summary_df.copy()
    ordered["scope_order"] = ordered["scope"].map(ordered_scope)
    ordered = ordered.sort_values(["scope_order", "subset_size"]).reset_index(drop=True)

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.5), constrained_layout=True)
    metric_specs = [
        ("max_abs_standardized_mean_diff", "Max abs SMD"),
        ("mean_abs_standardized_mean_diff", "Mean abs SMD"),
    ]
    threshold_lines = [
        (0.10, "#7a7a7a", "0.10"),
        (0.25, "#a35c00", "0.25"),
        (0.50, "#9c2f2f", "0.50"),
    ]

    for ax, (metric, title) in zip(axes, metric_specs):
        for scope in SCOPE_ORDER:
            scope_df = ordered[ordered["scope"] == scope]
            if scope_df.empty:
                continue
            ax.plot(
                scope_df["subset_size"],
                scope_df[metric],
                marker="o",
                linewidth=2.2,
                color=SCOPE_COLORS[scope],
                label=SCOPE_LABELS[scope],
            )
        for value, color, label in threshold_lines:
            ax.axhline(value, linestyle="--", linewidth=1, color=color, alpha=0.7)
            ax.text(
                SUBSET_ORDER[-1] + 22,
                value,
                label,
                va="center",
                ha="left",
                fontsize=8.5,
                color=color,
            )
        ax.set_title(title)
        ax.set_xlabel("Subset Size")
        ax.set_ylabel("Standardized difference")
        ax.set_xticks(SUBSET_ORDER)
        ax.grid(axis="y", alpha=0.25)
        ax.set_xlim(min(SUBSET_ORDER) - 20, max(SUBSET_ORDER) + 60)

    axes[0].legend(frameon=False, loc="upper right")
    fig.suptitle("Scaling Pilot Representativeness Summary", fontsize=14, y=1.03)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def plot_smd_heatmaps(comparisons_df: pd.DataFrame, output_path: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.4), constrained_layout=True)
    max_abs = comparisons_df["abs_standardized_mean_diff"].dropna().max()
    vmax = max(0.25, float(max_abs))
    cmap = plt.get_cmap("RdBu_r")
    norm = colors.TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
    image = None

    for ax, scope in zip(axes, SCOPE_ORDER):
        scope_df = comparisons_df[comparisons_df["scope"] == scope].copy()
        scope_df["attribute_order"] = scope_df["attribute"].map(ordered_attribute)
        scope_df = scope_df.sort_values(["attribute_order", "subset_size"]).reset_index(drop=True)
        pivot = scope_df.pivot(index="attribute", columns="subset_size", values="standardized_mean_diff")
        pivot = pivot.reindex(index=ATTRIBUTE_ORDER, columns=SUBSET_ORDER)
        image = ax.imshow(pivot.values, cmap=cmap, norm=norm, aspect="auto")

        ax.set_title(SCOPE_LABELS[scope])
        ax.set_xticks(range(len(SUBSET_ORDER)))
        ax.set_xticklabels([str(size) for size in SUBSET_ORDER])
        ax.set_yticks(range(len(ATTRIBUTE_ORDER)))
        ax.set_yticklabels([ATTRIBUTE_LABELS[attr] for attr in ATTRIBUTE_ORDER], fontsize=9)
        ax.set_xlabel("Subset Size")
        if scope == SCOPE_ORDER[0]:
            ax.set_ylabel("Static Attribute")

        for row_idx, attribute in enumerate(ATTRIBUTE_ORDER):
            for col_idx, subset_size in enumerate(SUBSET_ORDER):
                value = pivot.loc[attribute, subset_size]
                if pd.isna(value):
                    text = "NA"
                    text_color = "#111111"
                else:
                    text = f"{value:+.2f}"
                    text_color = "white" if abs(value) > vmax * 0.45 else "#111111"
                ax.text(col_idx, row_idx, text, ha="center", va="center", fontsize=8.2, color=text_color)

    cbar = fig.colorbar(image, ax=axes, shrink=0.9, pad=0.02)
    cbar.set_label("Standardized mean diff\n(subset mean - reference mean) / reference std")
    fig.suptitle("Attribute-Level Bias by Scope", fontsize=14, y=1.04)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def plot_combined_attribute_ranking(comparisons_df: pd.DataFrame, output_path: Path) -> None:
    combined = comparisons_df[comparisons_df["scope"] == "combined"].copy()
    ranking = (
        combined.groupby("attribute", as_index=False)["abs_standardized_mean_diff"]
        .max()
        .sort_values("abs_standardized_mean_diff", ascending=False)
    )
    ordered_attributes = ranking["attribute"].tolist()
    positions = list(range(len(ordered_attributes)))
    width = 0.22

    fig, ax = plt.subplots(figsize=(10.5, 5.2), constrained_layout=True)
    for idx, subset_size in enumerate(SUBSET_ORDER):
        subset_df = combined[combined["subset_size"] == subset_size].set_index("attribute")
        values = [float(subset_df.loc[attr, "abs_standardized_mean_diff"]) for attr in ordered_attributes]
        offsets = [pos + (idx - 1) * width for pos in positions]
        ax.barh(
            offsets,
            values,
            height=width,
            color=SUBSET_COLORS[subset_size],
            label=f"{subset_size} basins",
        )

    ax.axvline(0.10, linestyle="--", color="#7a7a7a", linewidth=1.2)
    ax.axvline(0.25, linestyle="--", color="#a35c00", linewidth=1.2)
    ax.set_yticks(positions)
    ax.set_yticklabels([ATTRIBUTE_LABELS[attr] for attr in ordered_attributes])
    ax.invert_yaxis()
    ax.set_xlabel("Absolute standardized mean diff")
    ax.set_title("Combined-Scope Attribute Mismatch Ranking")
    ax.grid(axis="x", alpha=0.25)
    ax.legend(frameon=False, loc="lower right")
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def write_manifest(output_dir: Path, plot_paths: list[Path]) -> Path:
    manifest = {
        "output_dir": str(output_dir),
        "plots": [
            {
                "name": path.stem,
                "path": str(path),
            }
            for path in plot_paths
        ],
        "interpretation_notes": [
            "scope_summary_metrics: subset size별 max/mean abs standardized mean diff를 비교한다.",
            "smd_heatmaps: 속성별 standardized mean diff의 방향과 크기를 scope별로 본다.",
            "combined_attribute_ranking: combined scope에서 어떤 속성이 subset mismatch를 주도하는지 본다.",
        ],
    }
    manifest_path = output_dir / "plot_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest_path


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    comparisons_df = pd.read_csv(args.comparisons_csv)
    scope_summary_df = pd.read_csv(args.scope_summary_csv)

    plot_paths = [
        args.output_dir / "scope_summary_metrics.svg",
        args.output_dir / "smd_heatmaps.svg",
        args.output_dir / "combined_attribute_ranking.svg",
    ]

    plot_scope_summary(scope_summary_df, plot_paths[0])
    plot_smd_heatmaps(comparisons_df, plot_paths[1])
    plot_combined_attribute_ranking(comparisons_df, plot_paths[2])
    manifest_path = write_manifest(args.output_dir, plot_paths)

    for path in plot_paths:
        print(f"Wrote plot: {path}")
    print(f"Wrote plot manifest: {manifest_path}")


if __name__ == "__main__":
    main()
