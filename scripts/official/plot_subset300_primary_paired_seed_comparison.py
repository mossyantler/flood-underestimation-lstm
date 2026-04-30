#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DELTAS = REPO_ROOT / "output/model_analysis/overall_analysis/primary_epoch_basin_deltas.csv"
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "output/model_analysis/overall_analysis/charts/primary_paired_seed_comparison"
)

BOX_METRICS = [
    ("delta_NSE", "Delta NSE", "positive_better"),
    ("delta_KGE", "Delta KGE", "positive_better"),
    ("delta_FHV", "Delta FHV (%)", "signed_shift"),
    ("abs_FHV_reduction", "|FHV| reduction (%)", "positive_better"),
    ("Peak_Timing_reduction", "Peak timing reduction", "positive_better"),
    ("Peak_MAPE_reduction", "Peak MAPE reduction (%)", "positive_better"),
]
HEATMAP_METRICS = [
    ("delta_NSE", "Delta NSE"),
    ("delta_KGE", "Delta KGE"),
    ("abs_FHV_reduction", "|FHV| reduction"),
    ("Peak_Timing_reduction", "Peak timing reduction"),
    ("Peak_MAPE_reduction", "Peak MAPE reduction"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot primary paired-seed Model 2 q50 minus Model 1 comparison charts."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_DELTAS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _read_deltas(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"basin": str})
    df["basin"] = df["basin"].astype(str).str.zfill(8)
    for metric, _, _ in BOX_METRICS:
        df[metric] = pd.to_numeric(df[metric], errors="coerce")
    return df.sort_values(["seed", "basin"])


def _effect_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for seed, group in df.groupby("seed", sort=True):
        for metric, label, interpretation in BOX_METRICS:
            values = group[metric].dropna()
            rows.append(
                {
                    "seed": int(seed),
                    "metric": metric,
                    "label": label,
                    "interpretation": interpretation,
                    "n_basins": int(values.size),
                    "mean_delta": float(values.mean()) if not values.empty else np.nan,
                    "median_delta": float(values.median()) if not values.empty else np.nan,
                    "q25_delta": float(values.quantile(0.25)) if not values.empty else np.nan,
                    "q75_delta": float(values.quantile(0.75)) if not values.empty else np.nan,
                    "positive_fraction": float((values > 0).mean()) if not values.empty else np.nan,
                }
            )
    return pd.DataFrame(rows)


def _save_delta_boxplot(df: pd.DataFrame, output_path: Path, show_fliers: bool) -> None:
    seeds = sorted(int(seed) for seed in df["seed"].dropna().unique())
    fig, axes = plt.subplots(2, 3, figsize=(14, 8.2))
    axes = axes.ravel()

    for ax, (metric, label, interpretation) in zip(axes, BOX_METRICS, strict=True):
        data = [
            df.loc[df["seed"].eq(seed), metric].dropna().to_numpy()
            for seed in seeds
        ]
        ax.boxplot(
            data,
            tick_labels=[str(seed) for seed in seeds],
            showfliers=show_fliers,
            showmeans=True,
            patch_artist=True,
            medianprops={"color": "#111111", "linewidth": 1.4},
            meanprops={
                "marker": "o",
                "markerfacecolor": "#dc2626",
                "markeredgecolor": "#7f1d1d",
                "markersize": 4.5,
            },
            boxprops={"facecolor": "#dbeafe", "edgecolor": "#1f2937", "linewidth": 0.9},
            whiskerprops={"color": "#1f2937", "linewidth": 0.9},
            capprops={"color": "#1f2937", "linewidth": 0.9},
            flierprops={
                "marker": ".",
                "markerfacecolor": "#6b7280",
                "markeredgecolor": "#6b7280",
                "markersize": 3,
                "alpha": 0.65,
            },
        )
        ax.axhline(0, color="#555555", linewidth=1.0)
        if interpretation == "positive_better":
            ax.text(
                0.02,
                0.96,
                "positive = Model 2 better",
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=8,
                color="#166534",
            )
        else:
            ax.text(
                0.02,
                0.96,
                "signed shift; 0 = no FHV shift",
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=8,
                color="#374151",
            )
        ax.set_title(label)
        ax.set_xlabel("Seed")
        ax.grid(True, axis="y", color="#dddddd", linewidth=0.7, alpha=0.8)

    suffix = "with outliers" if show_fliers else "without outliers"
    fig.suptitle(f"Primary paired basin deltas by seed: Model 2 q50 - Model 1 ({suffix})")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _save_improved_fraction_heatmap(summary: pd.DataFrame, output_path: Path) -> None:
    heat = summary[summary["metric"].isin([metric for metric, _ in HEATMAP_METRICS])].copy()
    fraction_matrix = heat.pivot(index="seed", columns="metric", values="positive_fraction")
    fraction_matrix = fraction_matrix[[metric for metric, _ in HEATMAP_METRICS]]
    median_matrix = heat.pivot(index="seed", columns="metric", values="median_delta")
    median_matrix = median_matrix[[metric for metric, _ in HEATMAP_METRICS]]
    labels = [label for _, label in HEATMAP_METRICS]
    display = fraction_matrix.to_numpy(dtype=float)

    fig, ax = plt.subplots(figsize=(10.8, 4.2))
    image = ax.imshow(display, cmap="RdBu", vmin=0.0, vmax=1.0, aspect="auto")
    ax.set_xticks(range(len(labels)), labels=labels, rotation=25, ha="right")
    ax.set_yticks(range(len(fraction_matrix.index)), labels=[str(seed) for seed in fraction_matrix.index])
    ax.set_xlabel("Metric")
    ax.set_ylabel("Seed")

    for row_idx, seed in enumerate(fraction_matrix.index):
        for col_idx, metric in enumerate(fraction_matrix.columns):
            value = median_matrix.loc[seed, metric]
            fraction = fraction_matrix.loc[seed, metric]
            if pd.isna(value) or pd.isna(fraction):
                text = ""
            else:
                text = f"med {value:.2f}\n{fraction:.0%}+"
            color = "#ffffff" if abs(float(fraction) - 0.5) > 0.32 else "#111111"
            ax.text(col_idx, row_idx, text, ha="center", va="center", fontsize=8, color=color)

    cbar = fig.colorbar(image, ax=ax, shrink=0.9)
    cbar.set_label("Fraction of paired basins favoring Model 2")
    ax.set_title("Primary paired seed improvement fraction (annotation: median delta, positive fraction)")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    input_path = _resolve(args.input)
    output_dir = _resolve(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = _read_deltas(input_path)
    if df.empty:
        raise SystemExit(f"No paired delta rows found in {input_path}")

    summary = _effect_summary(df)
    summary_path = output_dir / "primary_paired_seed_effect_summary.csv"
    summary.to_csv(summary_path, index=False)

    charts = [
        ("delta_boxplot_with_outliers", output_dir / "primary_paired_seed_delta_boxplots_with_outliers.png"),
        (
            "delta_boxplot_without_outliers",
            output_dir / "primary_paired_seed_delta_boxplots_without_outliers.png",
        ),
        ("improved_fraction_heatmap", output_dir / "primary_paired_seed_improved_fraction_heatmap.png"),
    ]
    _save_delta_boxplot(df, charts[0][1], show_fliers=True)
    _save_delta_boxplot(df, charts[1][1], show_fliers=False)
    _save_improved_fraction_heatmap(summary, charts[2][1])

    manifest = pd.DataFrame(
        [
            {
                "chart": name,
                "path": str(path.relative_to(REPO_ROOT)),
            }
            for name, path in charts
        ]
    )
    manifest_path = output_dir / "primary_paired_seed_chart_manifest.csv"
    manifest.to_csv(manifest_path, index=False)

    metadata = {
        "input": str(input_path.relative_to(REPO_ROOT)),
        "output_dir": str(output_dir.relative_to(REPO_ROOT)),
        "comparison": "Primary paired basin deltas, Model 2 q50 minus Model 1.",
        "box_metrics": [metric for metric, _, _ in BOX_METRICS],
        "heatmap_metrics": [metric for metric, _ in HEATMAP_METRICS],
        "heatmap_encoding": (
            "Cell color shows the fraction of paired basins where the metric favors Model 2; "
            "cell text shows median delta and positive fraction."
        ),
        "delta_interpretation": {
            "delta_NSE": "positive means Model 2 q50 has higher NSE.",
            "delta_KGE": "positive means Model 2 q50 has higher KGE.",
            "delta_FHV": "signed FHV shift; positive is not automatically better.",
            "abs_FHV_reduction": "positive means Model 2 q50 is closer to zero FHV.",
            "Peak_Timing_reduction": "positive means Model 2 q50 has lower peak timing error.",
            "Peak_MAPE_reduction": "positive means Model 2 q50 has lower Peak-MAPE.",
        },
        "summary": str(summary_path.relative_to(REPO_ROOT)),
        "manifest": str(manifest_path.relative_to(REPO_ROOT)),
    }
    metadata_path = output_dir / "primary_paired_seed_chart_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Wrote paired seed charts to {output_dir}")
    print(f"Wrote summary: {summary_path}")
    print(f"Wrote manifest: {manifest_path}")


if __name__ == "__main__":
    main()
