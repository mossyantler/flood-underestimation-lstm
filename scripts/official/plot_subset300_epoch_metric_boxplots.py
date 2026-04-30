#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = REPO_ROOT / "output/model_analysis/overall_analysis/basin_metrics.csv"
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "output/model_analysis/overall_analysis/charts/epoch_metric_boxplots"
)
DEFAULT_PRIMARY_SUMMARY = REPO_ROOT / "output/model_analysis/overall_analysis/primary_epoch_summary.csv"
OFFICIAL_SEEDS = [111, 222, 444]
MODEL_LABELS = {"model1": "Model 1", "model2": "Model 2"}
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
            "Plot epoch-wise basin metric box plots for each subset300 model/seed pair."
        )
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--primary-summary", type=Path, default=DEFAULT_PRIMARY_SUMMARY)
    parser.add_argument("--split", default="both", choices=["test", "validation", "both"])
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=OFFICIAL_SEEDS,
        help="Seeds to include. Defaults to official paired seeds 111 222 444.",
    )
    parser.add_argument(
        "--include-seed333",
        action="store_true",
        help="Include seed 333 diagnostic rows in addition to --seeds if present.",
    )
    parser.add_argument(
        "--outlier-mode",
        choices=["both", "with", "without"],
        default="both",
        help=(
            "Outlier display mode. Default 'both' writes separate with_outliers and "
            "without_outliers plot sets."
        ),
    )
    return parser.parse_args()


def _read_metrics(path: Path, splits: list[str], seeds: list[int]) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"basin": str})
    df["basin"] = df["basin"].astype(str).str.zfill(8)
    df["abs_FHV"] = pd.to_numeric(df["FHV"], errors="coerce").abs()
    for metric, _ in METRICS:
        df[metric] = pd.to_numeric(df[metric], errors="coerce")
    df = df[(df["split"].isin(splits)) & (df["seed"].isin(seeds))].copy()
    return df.sort_values(["model", "seed", "epoch", "basin"])


def _read_primary_epochs(path: Path, seeds: list[int]) -> dict[tuple[str, int], int]:
    if not path.exists():
        return {}
    df = pd.read_csv(path)
    df = df[df["seed"].isin(seeds)].copy()
    primary_epochs: dict[tuple[str, int], int] = {}
    for _, row in df.iterrows():
        primary_epochs[(str(row["model"]), int(row["seed"]))] = int(row["epoch"])
    return primary_epochs


def _boxplot_for_group(
    group: pd.DataFrame,
    output_path: Path,
    outlier_mode: str,
    show_fliers: bool,
    primary_epoch: int | None,
) -> dict[str, object]:
    model = str(group["model"].iloc[0])
    seed = int(group["seed"].iloc[0])
    epochs = sorted(int(epoch) for epoch in group["epoch"].dropna().unique())

    fig, axes = plt.subplots(2, 3, figsize=(14, 8), sharex=False)
    axes = axes.ravel()

    for ax, (metric, label) in zip(axes, METRICS, strict=True):
        data = [
            group.loc[group["epoch"].eq(epoch), metric].dropna().to_numpy()
            for epoch in epochs
        ]
        plot = ax.boxplot(
            data,
            tick_labels=[f"{epoch:03d}" for epoch in epochs],
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
        if primary_epoch in epochs:
            primary_index = epochs.index(primary_epoch)
            plot["boxes"][primary_index].set_facecolor("#93c5fd")
            plot["boxes"][primary_index].set_edgecolor("#2563eb")
            plot["boxes"][primary_index].set_linewidth(1.3)
            plot["medians"][primary_index].set_color("#111111")
            plot["medians"][primary_index].set_linewidth(1.6)
            for line in plot["whiskers"][primary_index * 2 : primary_index * 2 + 2]:
                line.set_color("#2563eb")
                line.set_linewidth(1.05)
            for line in plot["caps"][primary_index * 2 : primary_index * 2 + 2]:
                line.set_color("#2563eb")
                line.set_linewidth(1.05)

        if metric in {"NSE", "KGE", "FHV"}:
            ax.axhline(0, color="#777777", linewidth=0.8)
        if metric in {"Peak-Timing", "Peak-MAPE", "abs_FHV"}:
            ax.set_ylim(bottom=0)
        ax.set_title(label)
        ax.set_xlabel("Epoch")
        ax.grid(True, axis="y", color="#dddddd", linewidth=0.7, alpha=0.8)
        if primary_epoch in epochs:
            for tick, epoch in zip(ax.get_xticklabels(), epochs, strict=True):
                if epoch == primary_epoch:
                    tick.set_fontweight("bold")
                    tick.set_color("#2563eb")

    primary_text = f", primary epoch {primary_epoch:03d}" if primary_epoch in epochs else ""
    fig.suptitle(
        f"{MODEL_LABELS.get(model, model)} seed {seed} {group['split'].iloc[0]} basin metrics{primary_text}"
    )
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)

    return {
        "model": model,
        "model_label": MODEL_LABELS.get(model, model),
        "seed": seed,
        "split": str(group["split"].iloc[0]),
        "outlier_mode": outlier_mode,
        "primary_epoch": f"{primary_epoch:03d}" if primary_epoch in epochs else "",
        "primary_highlighted": bool(primary_epoch in epochs),
        "epochs": " ".join(f"{epoch:03d}" for epoch in epochs),
        "n_epochs": len(epochs),
        "n_basin_epoch_rows": int(len(group)),
        "n_basins_min_per_epoch": int(group.groupby("epoch")["basin"].nunique().min()),
        "n_basins_max_per_epoch": int(group.groupby("epoch")["basin"].nunique().max()),
        "plot_path": str(output_path.relative_to(REPO_ROOT)),
    }


def main() -> None:
    args = parse_args()
    seeds = list(dict.fromkeys(args.seeds + ([333] if args.include_seed333 else [])))
    splits = ["test", "validation"] if args.split == "both" else [args.split]
    input_path = args.input if args.input.is_absolute() else REPO_ROOT / args.input
    output_dir = args.output_dir if args.output_dir.is_absolute() else REPO_ROOT / args.output_dir
    primary_summary_path = (
        args.primary_summary if args.primary_summary.is_absolute() else REPO_ROOT / args.primary_summary
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    df = _read_metrics(input_path, splits, seeds)
    if df.empty:
        raise SystemExit(f"No rows found for splits={splits} seeds={seeds} in {input_path}")
    primary_epochs = _read_primary_epochs(primary_summary_path, seeds)

    outlier_modes = {
        "with": [("with_outliers", True)],
        "without": [("without_outliers", False)],
        "both": [("with_outliers", True), ("without_outliers", False)],
    }[args.outlier_mode]

    manifest_rows = []
    for split in splits:
        split_df = df[df["split"] == split].copy()
        if split_df.empty:
            continue
        for outlier_mode, show_fliers in outlier_modes:
            mode_output_dir = output_dir / split / outlier_mode
            mode_output_dir.mkdir(parents=True, exist_ok=True)
            for (model, seed), group in split_df.groupby(["model", "seed"], sort=True):
                output_path = (
                    mode_output_dir
                    / f"{split}_epoch_metric_boxplots_{model}_seed{int(seed)}_{outlier_mode}.png"
                )
                manifest_rows.append(
                    _boxplot_for_group(
                        group,
                        output_path,
                        outlier_mode,
                        show_fliers,
                        primary_epochs.get((str(model), int(seed))),
                    )
                )

    manifest = pd.DataFrame(manifest_rows).sort_values(["split", "outlier_mode", "model", "seed"])
    manifest_path = output_dir / "epoch_metric_boxplot_manifest.csv"
    manifest.to_csv(manifest_path, index=False)
    for split, split_manifest in manifest.groupby("split", sort=True):
        split_manifest.to_csv(output_dir / f"{split}_epoch_metric_boxplot_manifest.csv", index=False)

    metadata = {
        "input": str(input_path.relative_to(REPO_ROOT)),
        "primary_summary": str(primary_summary_path.relative_to(REPO_ROOT))
        if primary_summary_path.exists()
        else "",
        "output_dir": str(output_dir.relative_to(REPO_ROOT)),
        "splits": splits,
        "seeds": seeds,
        "metrics": [metric for metric, _ in METRICS],
        "box_definition": "Each box is the basin-level metric distribution within one model/seed/epoch.",
        "primary_highlight": "The validation-selected primary epoch box is rendered in medium blue with a bold tick label.",
        "mean_marker": "Red dot in each box marks the basin-level mean for that model/seed/epoch.",
        "outlier_modes": {
            "with_outliers": "Small gray points show fliers using the standard 1.5 IQR boxplot rule.",
            "without_outliers": "Fliers are hidden for a compact median/IQR-focused view.",
        },
        "manifest": str(manifest_path.relative_to(REPO_ROOT)),
    }
    metadata_path = output_dir / "epoch_metric_boxplot_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    for split in splits:
        split_metadata = {**metadata, "splits": [split]}
        (output_dir / f"{split}_epoch_metric_boxplot_metadata.json").write_text(
            json.dumps(split_metadata, indent=2), encoding="utf-8"
        )

    print(f"Wrote {len(manifest_rows)} boxplot files to {output_dir}")
    print(f"Wrote manifest: {manifest_path}")


if __name__ == "__main__":
    main()
