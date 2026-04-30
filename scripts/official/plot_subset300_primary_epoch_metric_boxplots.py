#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = REPO_ROOT / "output/model_analysis/overall_analysis/basin_metrics.csv"
DEFAULT_PRIMARY_SUMMARY = REPO_ROOT / "output/model_analysis/overall_analysis/primary_epoch_summary.csv"
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "output/model_analysis/overall_analysis/charts/primary_epoch_metric_boxplots"
)
OFFICIAL_SEEDS = [111, 222, 444]
MODELS = ["model1", "model2"]
MODEL_LABELS = {"model1": "Model 1", "model2": "Model 2"}
MODEL_COLORS = {
    "model1": {
        "face": "#fecaca",
        "edge": "#dc2626",
        "mean": "#b91c1c",
        "flier": "#991b1b",
    },
    "model2": {
        "face": "#93c5fd",
        "edge": "#2563eb",
        "mean": "#1d4ed8",
        "flier": "#1e40af",
    },
}
METRICS = [
    ("NSE", "NSE"),
    ("KGE", "KGE"),
    ("FHV", "FHV (%)"),
    ("Peak-Timing", "Peak Timing"),
    ("Peak-MAPE", "Peak MAPE (%)"),
    ("abs_FHV", "|FHV| (%)"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Plot basin-level metric box plots for the subset300 primary epochs, "
            "with Model 1 and Model 2 shown side by side for each seed."
        )
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--primary-summary", type=Path, default=DEFAULT_PRIMARY_SUMMARY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--split", default="test", choices=["test", "validation"])
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=OFFICIAL_SEEDS,
        help="Seeds to include. Defaults to official paired seeds 111 222 444.",
    )
    parser.add_argument(
        "--outlier-mode",
        choices=["both", "with", "without"],
        default="both",
        help="Write with_outliers, without_outliers, or both plot variants.",
    )
    return parser.parse_args()


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _read_primary_metric_rows(
    metrics_path: Path,
    primary_summary_path: Path,
    split: str,
    seeds: list[int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    metrics = pd.read_csv(metrics_path, dtype={"basin": str})
    metrics["basin"] = metrics["basin"].astype(str).str.zfill(8)
    metrics["abs_FHV"] = pd.to_numeric(metrics["FHV"], errors="coerce").abs()
    for metric, _ in METRICS:
        metrics[metric] = pd.to_numeric(metrics[metric], errors="coerce")

    primary = pd.read_csv(primary_summary_path)
    primary = primary[
        primary["model"].isin(MODELS)
        & primary["seed"].isin(seeds)
        & primary["split"].eq(split)
    ].copy()
    if primary.empty:
        raise SystemExit(
            f"No primary epoch rows found for split={split!r} seeds={seeds} in {primary_summary_path}"
        )
    primary = primary[["model", "seed", "split", "epoch", "run_name", "n_basins", "status"]]

    rows = metrics.merge(
        primary[["model", "seed", "split", "epoch"]],
        on=["model", "seed", "split", "epoch"],
        how="inner",
    )
    rows = rows[rows["model"].isin(MODELS) & rows["seed"].isin(seeds)].copy()
    rows["model_label"] = rows["model"].map(MODEL_LABELS).fillna(rows["model"])
    if rows.empty:
        raise SystemExit(
            f"No basin metric rows matched primary epochs from {primary_summary_path}"
        )
    return rows.sort_values(["seed", "model", "basin"]), primary.sort_values(["seed", "model"])


def _epoch_label(primary: pd.DataFrame, seed: int, model: str) -> str:
    match = primary[(primary["seed"].eq(seed)) & (primary["model"].eq(model))]
    if match.empty:
        return "---"
    return f"{int(match['epoch'].iloc[0]):03d}"


def _summarize(rows: pd.DataFrame, primary: pd.DataFrame) -> pd.DataFrame:
    summary_rows = []
    for (model, seed), group in rows.groupby(["model", "seed"], sort=True):
        primary_epoch = _epoch_label(primary, int(seed), str(model))
        for metric, label in METRICS:
            values = group[metric].dropna()
            summary_rows.append(
                {
                    "model": model,
                    "model_label": MODEL_LABELS.get(str(model), str(model)),
                    "seed": int(seed),
                    "primary_epoch": primary_epoch,
                    "metric": metric,
                    "label": label,
                    "n_basins": int(values.size),
                    "mean": float(values.mean()) if not values.empty else pd.NA,
                    "median": float(values.median()) if not values.empty else pd.NA,
                    "q25": float(values.quantile(0.25)) if not values.empty else pd.NA,
                    "q75": float(values.quantile(0.75)) if not values.empty else pd.NA,
                    "min": float(values.min()) if not values.empty else pd.NA,
                    "max": float(values.max()) if not values.empty else pd.NA,
                }
            )
    return pd.DataFrame(summary_rows)


def _plot_one_box(
    ax: plt.Axes,
    values,
    position: float,
    model: str,
    show_fliers: bool,
    show_means: bool,
) -> None:
    colors = MODEL_COLORS[model]
    ax.boxplot(
        [values],
        positions=[position],
        widths=0.28,
        showfliers=show_fliers,
        showmeans=show_means,
        patch_artist=True,
        manage_ticks=False,
        medianprops={"color": "#111111", "linewidth": 1.45},
        meanprops={
            "marker": "o",
            "markerfacecolor": colors["mean"],
            "markeredgecolor": "#111111",
            "markeredgewidth": 0.45,
            "markersize": 4.7,
        },
        boxprops={"facecolor": colors["face"], "edgecolor": colors["edge"], "linewidth": 1.15},
        whiskerprops={"color": "#1f2937", "linewidth": 0.9},
        capprops={"color": "#1f2937", "linewidth": 0.9},
        flierprops={
            "marker": ".",
            "markerfacecolor": colors["flier"],
            "markeredgecolor": colors["flier"],
            "markersize": 3,
            "alpha": 0.62,
        },
    )


def _save_boxplot(
    rows: pd.DataFrame,
    primary: pd.DataFrame,
    output_path: Path,
    split: str,
    outlier_mode: str,
    show_fliers: bool,
    show_means: bool,
) -> None:
    seeds = sorted(int(seed) for seed in rows["seed"].dropna().unique())
    fig, axes = plt.subplots(2, 3, figsize=(14.6, 8.4), sharex=False)
    axes = axes.ravel()
    offsets = {"model1": -0.18, "model2": 0.18}
    centers = list(range(1, len(seeds) + 1))
    xtick_labels = [
        f"{seed}\n{_epoch_label(primary, seed, 'model1')} / {_epoch_label(primary, seed, 'model2')}"
        for seed in seeds
    ]

    for ax, (metric, label) in zip(axes, METRICS, strict=True):
        for center, seed in zip(centers, seeds, strict=True):
            for model in MODELS:
                values = rows[
                    rows["seed"].eq(seed)
                    & rows["model"].eq(model)
                ][metric].dropna().to_numpy()
                if len(values) == 0:
                    continue
                _plot_one_box(
                    ax,
                    values,
                    center + offsets[model],
                    model,
                    show_fliers=show_fliers,
                    show_means=show_means,
                )

        if metric in {"NSE", "KGE", "FHV"}:
            ax.axhline(0, color="#777777", linewidth=0.85)
        if metric in {"Peak-Timing", "Peak-MAPE", "abs_FHV"}:
            ax.set_ylim(bottom=0)
        ax.set_title(label)
        ax.set_xticks(centers, xtick_labels)
        ax.set_xlabel("Seed (Model 1 epoch / Model 2 epoch)")
        ax.grid(True, axis="y", color="#dddddd", linewidth=0.7, alpha=0.8)

    legend_handles = [
        Patch(
            facecolor=MODEL_COLORS[model]["face"],
            edgecolor=MODEL_COLORS[model]["edge"],
            label=MODEL_LABELS[model],
        )
        for model in MODELS
    ]
    mode_text = "with outliers" if show_fliers else "without outliers"
    mean_text = "mean markers shown" if show_means else "mean markers hidden"
    fig.suptitle(
        f"Primary epoch {split} basin metrics by seed ({mode_text}, {mean_text})",
        y=0.985,
    )
    fig.legend(
        handles=legend_handles,
        loc="upper center",
        ncol=2,
        frameon=False,
        bbox_to_anchor=(0.5, 0.948),
    )
    fig.tight_layout(rect=[0, 0, 1, 0.91])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    input_path = _resolve(args.input)
    primary_summary_path = _resolve(args.primary_summary)
    output_dir = _resolve(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows, primary = _read_primary_metric_rows(
        input_path,
        primary_summary_path,
        split=args.split,
        seeds=list(dict.fromkeys(args.seeds)),
    )
    summary = _summarize(rows, primary)
    summary_path = output_dir / f"{args.split}_primary_epoch_metric_boxplot_summary.csv"
    summary.to_csv(summary_path, index=False)

    outlier_modes = {
        "with": [("with_outliers", True, True)],
        "without": [("without_outliers", False, False)],
        "both": [("with_outliers", True, True), ("without_outliers", False, False)],
    }[args.outlier_mode]

    manifest_rows = []
    for outlier_mode, show_fliers, show_means in outlier_modes:
        mode_dir = output_dir / args.split / outlier_mode
        mode_dir.mkdir(parents=True, exist_ok=True)
        output_path = (
            mode_dir
            / f"{args.split}_primary_epoch_metric_boxplots_model1_model2_{outlier_mode}.png"
        )
        _save_boxplot(
            rows,
            primary,
            output_path,
            split=args.split,
            outlier_mode=outlier_mode,
            show_fliers=show_fliers,
            show_means=show_means,
        )
        manifest_rows.append(
            {
                "split": args.split,
                "outlier_mode": outlier_mode,
                "show_fliers": show_fliers,
                "show_means": show_means,
                "models": " ".join(MODELS),
                "seeds": " ".join(str(seed) for seed in sorted(rows["seed"].unique())),
                "n_basin_metric_rows": int(len(rows)),
                "n_basins_min_per_model_seed": int(
                    rows.groupby(["model", "seed"])["basin"].nunique().min()
                ),
                "n_basins_max_per_model_seed": int(
                    rows.groupby(["model", "seed"])["basin"].nunique().max()
                ),
                "plot_path": str(output_path.relative_to(REPO_ROOT)),
            }
        )

    manifest = pd.DataFrame(manifest_rows)
    manifest_path = output_dir / f"{args.split}_primary_epoch_metric_boxplot_manifest.csv"
    manifest.to_csv(manifest_path, index=False)
    metadata = {
        "input": str(input_path.relative_to(REPO_ROOT)),
        "primary_summary": str(primary_summary_path.relative_to(REPO_ROOT)),
        "output_dir": str(output_dir.relative_to(REPO_ROOT)),
        "split": args.split,
        "models": MODELS,
        "seeds": sorted(int(seed) for seed in rows["seed"].unique()),
        "metrics": [metric for metric, _ in METRICS],
        "box_definition": (
            "Each box is the basin-level metric distribution for one model/seed at "
            "that model/seed's validation-selected primary epoch."
        ),
        "colors": {
            "model1": "red palette",
            "model2": "blue palette matching the existing epoch metric boxplot family",
        },
        "mean_marker_rule": (
            "Mean markers are shown only in with_outliers plots and hidden in "
            "without_outliers plots."
        ),
        "summary": str(summary_path.relative_to(REPO_ROOT)),
        "manifest": str(manifest_path.relative_to(REPO_ROOT)),
    }
    metadata_path = output_dir / f"{args.split}_primary_epoch_metric_boxplot_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Wrote {len(manifest_rows)} primary epoch boxplot files to {output_dir}")
    print(f"Wrote summary: {summary_path}")
    print(f"Wrote manifest: {manifest_path}")


if __name__ == "__main__":
    main()
