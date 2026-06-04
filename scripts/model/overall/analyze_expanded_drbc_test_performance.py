#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "matplotlib>=3.9",
# ]
# ///
"""Generate analysis tables and figures for the expanded DRBC test (85-basin holdout).

Reads existing tables from output/model_analysis/primary/metrics/tables/
and produces:
  tables/primary_epoch_summary.csv       — per-model/seed stats (legacy-compatible)
  tables/primary_epoch_basin_deltas.csv  — per-basin Model2-Model1 deltas
  tables/primary_epoch_delta_summary.csv — pooled + per-seed delta stats
  figures/metric_boxplots/               — NSE/KGE/FHV/Peak-Timing/Peak-MAPE/|FHV| boxplots
  figures/paired_seed_comparison/        — delta boxplots + improved-fraction heatmap
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TABLES_DIR = REPO_ROOT / "output/model_analysis/primary/metrics/tables"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/primary/metrics"

PRIMARY_EPOCHS: dict[tuple[str, int], int] = {
    ("model1", 111): 25,
    ("model1", 222): 10,
    ("model1", 444): 15,
    ("model2", 111): 5,
    ("model2", 222): 10,
    ("model2", 444): 10,
}
OFFICIAL_SEEDS = [111, 222, 444]
MODELS = ["model1", "model2"]
MODEL_LABELS = {"model1": "Model 1", "model2": "Model 2"}
MODEL_COLORS = {
    "model1": {"face": "#fecaca", "edge": "#dc2626", "mean": "#b91c1c", "flier": "#991b1b"},
    "model2": {"face": "#93c5fd", "edge": "#2563eb", "mean": "#1d4ed8", "flier": "#1e40af"},
}
METRICS = [
    ("NSE", "NSE"),
    ("KGE", "KGE"),
    ("FHV", "FHV (%)"),
    ("Peak-Timing", "Peak Timing"),
    ("Peak-MAPE", "Peak MAPE (%)"),
    ("abs_FHV", "|FHV| (%)"),
]
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
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tables-dir", type=Path, default=DEFAULT_TABLES_DIR)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--force", action="store_true")
    return p.parse_args()


# ── table builders ────────────────────────────────────────────────────────────

def build_primary_epoch_summary(metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (model, seed), g in metrics.groupby(["model", "seed"], sort=True):
        epoch = PRIMARY_EPOCHS.get((str(model), int(seed)))
        subset = g[g["epoch"] == epoch]
        run_name = subset["run_name"].iloc[0] if not subset.empty else ""
        n = int(subset["basin"].nunique())
        row: dict = {
            "model": model,
            "seed": int(seed),
            "split": "expanded_drbc_test",
            "epoch": epoch,
            "run_name": run_name,
            "source": "top_level",
            "model_label": MODEL_LABELS.get(str(model), str(model)),
            "n_basins": n,
            "status": "available",
        }
        for col in ["NSE", "KGE", "FHV", "Peak-Timing", "Peak-MAPE", "abs_FHV"]:
            if col not in subset.columns:
                continue
            vals = pd.to_numeric(subset[col], errors="coerce").dropna()
            safe = col.replace("-", "_")
            row[f"mean_{safe}"] = float(vals.mean()) if not vals.empty else math.nan
            row[f"median_{safe}"] = float(vals.median()) if not vals.empty else math.nan
            row[f"std_{safe}"] = float(vals.std()) if not vals.empty else math.nan
            row[f"q25_{safe}"] = float(vals.quantile(0.25)) if not vals.empty else math.nan
            row[f"q75_{safe}"] = float(vals.quantile(0.75)) if not vals.empty else math.nan
        if "NSE" in subset.columns:
            row["negative_nse_basins"] = int((pd.to_numeric(subset["NSE"], errors="coerce") < 0).sum())
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["model", "seed"]).reset_index(drop=True)


def build_primary_epoch_basin_deltas(metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for seed in OFFICIAL_SEEDS:
        m1_epoch = PRIMARY_EPOCHS.get(("model1", seed))
        m2_epoch = PRIMARY_EPOCHS.get(("model2", seed))
        left = metrics[(metrics["model"] == "model1") & (metrics["seed"] == seed) & (metrics["epoch"] == m1_epoch)].copy()
        right = metrics[(metrics["model"] == "model2") & (metrics["seed"] == seed) & (metrics["epoch"] == m2_epoch)].copy()
        if left.empty or right.empty:
            continue
        base_cols = ["basin", "NSE", "KGE", "FHV", "Peak-Timing", "Peak-MAPE", "abs_FHV"]
        keep = [c for c in base_cols if c in left.columns and c in right.columns]
        merged = left[keep].merge(right[keep], on="basin", suffixes=("_model1", "_model2"), how="inner")
        merged.insert(0, "seed", int(seed))
        merged.insert(1, "model1_epoch", int(m1_epoch))
        merged.insert(2, "model2_epoch", int(m2_epoch))
        for metric in ["NSE", "KGE", "FHV", "Peak-Timing", "Peak-MAPE"]:
            lc, rc = f"{metric}_model1", f"{metric}_model2"
            if lc in merged and rc in merged:
                safe = metric.replace("-", "_")
                merged[f"delta_{safe}"] = merged[rc] - merged[lc]
        if "FHV_model1" in merged and "FHV_model2" in merged:
            merged["abs_FHV_reduction"] = merged["FHV_model1"].abs() - merged["FHV_model2"].abs()
        if "Peak-MAPE_model1" in merged and "Peak-MAPE_model2" in merged:
            merged["Peak_MAPE_reduction"] = merged["Peak-MAPE_model1"] - merged["Peak-MAPE_model2"]
        # Peak_Timing_reduction = positive means model2 is better (lower timing error)
        if "Peak-Timing_model1" in merged and "Peak-Timing_model2" in merged:
            merged["Peak_Timing_reduction"] = merged["Peak-Timing_model1"] - merged["Peak-Timing_model2"]
        rows.append(merged)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True).sort_values(["seed", "basin"]).reset_index(drop=True)


def build_delta_summary(deltas: pd.DataFrame) -> pd.DataFrame:
    if deltas.empty:
        return pd.DataFrame()
    delta_cols = [col for col in deltas.columns if col.startswith("delta_") or col.endswith("_reduction")]
    rows = []
    for seed, g in deltas.groupby("seed", sort=True):
        row: dict = {"seed": int(seed), "n_basins": int(g["basin"].nunique())}
        for col in delta_cols:
            vals = pd.to_numeric(g[col], errors="coerce").dropna()
            row[f"median_{col}"] = float(vals.median()) if not vals.empty else math.nan
            row[f"mean_{col}"] = float(vals.mean()) if not vals.empty else math.nan
            row[f"q25_{col}"] = float(vals.quantile(0.25)) if not vals.empty else math.nan
            row[f"q75_{col}"] = float(vals.quantile(0.75)) if not vals.empty else math.nan
            row[f"improved_fraction_{col}"] = float((vals > 0).mean()) if not vals.empty else math.nan
        rows.append(row)
    return pd.DataFrame(rows).sort_values("seed").reset_index(drop=True)


# ── figure builders ────────────────────────────────────────────────────────────

def _plot_one_box(ax: plt.Axes, values, position: float, model: str, show_fliers: bool, show_means: bool) -> None:
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


def _epoch_label(summary: pd.DataFrame, seed: int, model: str) -> str:
    row = summary[(summary["seed"] == seed) & (summary["model"] == model)]
    return f"{int(row['epoch'].iloc[0]):03d}" if not row.empty else "---"


def save_metric_boxplots(rows: pd.DataFrame, summary: pd.DataFrame, output_dir: Path) -> list[dict]:
    seeds = sorted(int(s) for s in rows["seed"].dropna().unique())
    centers = list(range(1, len(seeds) + 1))
    offsets = {"model1": -0.18, "model2": 0.18}
    xtick_labels = [
        f"{seed}\n{_epoch_label(summary, seed, 'model1')} / {_epoch_label(summary, seed, 'model2')}"
        for seed in seeds
    ]
    legend_handles = [
        Patch(facecolor=MODEL_COLORS[m]["face"], edgecolor=MODEL_COLORS[m]["edge"], label=MODEL_LABELS[m])
        for m in MODELS
    ]
    manifest = []
    for suffix, show_fliers, show_means in [("with_outliers", True, True), ("without_outliers", False, False)]:
        mode_dir = output_dir / "test" / suffix
        mode_dir.mkdir(parents=True, exist_ok=True)
        out_path = mode_dir / f"test_primary_epoch_metric_boxplots_model1_model2_{suffix}.png"
        fig, axes = plt.subplots(2, 3, figsize=(14.6, 8.4))
        for ax, (metric, label) in zip(axes.ravel(), METRICS, strict=True):
            for center, seed in zip(centers, seeds, strict=True):
                for model in MODELS:
                    vals = rows[(rows["seed"] == seed) & (rows["model"] == model)][metric].dropna().to_numpy()
                    if len(vals) == 0:
                        continue
                    _plot_one_box(ax, vals, center + offsets[model], model, show_fliers, show_means)
            if metric in {"NSE", "KGE", "FHV"}:
                ax.axhline(0, color="#777777", linewidth=0.85)
            if metric in {"Peak-Timing", "Peak-MAPE", "abs_FHV"}:
                ax.set_ylim(bottom=0)
            ax.set_title(label)
            ax.set_xticks(centers, xtick_labels)
            ax.set_xlabel("Seed (Model 1 epoch / Model 2 epoch)")
            ax.grid(True, axis="y", color="#dddddd", linewidth=0.7, alpha=0.8)
        mode_text = "with outliers" if show_fliers else "without outliers"
        fig.suptitle(f"Expanded DRBC test basin metrics by seed ({mode_text})", y=0.985)
        fig.legend(handles=legend_handles, loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 0.948))
        fig.tight_layout(rect=[0, 0, 1, 0.91])
        fig.savefig(out_path, dpi=180)
        plt.close(fig)
        manifest.append({"outlier_mode": suffix, "path": str(out_path.relative_to(REPO_ROOT))})
    return manifest


def save_delta_boxplot(deltas: pd.DataFrame, output_path: Path, show_fliers: bool) -> None:
    seeds = sorted(int(s) for s in deltas["seed"].dropna().unique())
    fig, axes = plt.subplots(2, 3, figsize=(14, 8.2))
    for ax, (metric, label, interpretation) in zip(axes.ravel(), BOX_METRICS, strict=True):
        if metric not in deltas.columns:
            ax.set_visible(False)
            continue
        data = [deltas.loc[deltas["seed"] == seed, metric].dropna().to_numpy() for seed in seeds]
        ax.boxplot(
            data,
            tick_labels=[str(s) for s in seeds],
            showfliers=show_fliers,
            showmeans=True,
            patch_artist=True,
            medianprops={"color": "#111111", "linewidth": 1.4},
            meanprops={"marker": "o", "markerfacecolor": "#dc2626", "markeredgecolor": "#7f1d1d", "markersize": 4.5},
            boxprops={"facecolor": "#dbeafe", "edgecolor": "#1f2937", "linewidth": 0.9},
            whiskerprops={"color": "#1f2937", "linewidth": 0.9},
            capprops={"color": "#1f2937", "linewidth": 0.9},
            flierprops={"marker": ".", "markerfacecolor": "#6b7280", "markeredgecolor": "#6b7280", "markersize": 3, "alpha": 0.65},
        )
        ax.axhline(0, color="#555555", linewidth=1.0)
        note = "positive = Model 2 better" if interpretation == "positive_better" else "signed shift; 0 = no FHV shift"
        color = "#166534" if interpretation == "positive_better" else "#374151"
        ax.text(0.02, 0.96, note, transform=ax.transAxes, ha="left", va="top", fontsize=8, color=color)
        ax.set_title(label)
        ax.set_xlabel("Seed")
        ax.grid(True, axis="y", color="#dddddd", linewidth=0.7, alpha=0.8)
    suffix = "with outliers" if show_fliers else "without outliers"
    fig.suptitle(f"Expanded DRBC primary paired basin deltas by seed: Model 2 q50 – Model 1 ({suffix})")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def save_improved_fraction_heatmap(deltas: pd.DataFrame, output_path: Path) -> None:
    rows = []
    for seed, g in deltas.groupby("seed", sort=True):
        for metric, label in HEATMAP_METRICS:
            if metric not in g.columns:
                continue
            vals = g[metric].dropna()
            rows.append({
                "seed": int(seed),
                "metric": metric,
                "label": label,
                "positive_fraction": float((vals > 0).mean()) if not vals.empty else np.nan,
                "median_delta": float(vals.median()) if not vals.empty else np.nan,
            })
    summary = pd.DataFrame(rows)
    if summary.empty:
        return
    heat = summary[summary["metric"].isin([m for m, _ in HEATMAP_METRICS])]
    frac = heat.pivot(index="seed", columns="metric", values="positive_fraction")
    med = heat.pivot(index="seed", columns="metric", values="median_delta")
    cols_ordered = [m for m, _ in HEATMAP_METRICS if m in frac.columns]
    frac = frac[cols_ordered]
    med = med[cols_ordered]
    labels = [lbl for m, lbl in HEATMAP_METRICS if m in frac.columns]

    fig, ax = plt.subplots(figsize=(10.8, 4.2))
    im = ax.imshow(frac.to_numpy(dtype=float), cmap="RdBu", vmin=0.0, vmax=1.0, aspect="auto")
    ax.set_xticks(range(len(labels)), labels=labels, rotation=25, ha="right")
    ax.set_yticks(range(len(frac.index)), labels=[str(s) for s in frac.index])
    ax.set_xlabel("Metric")
    ax.set_ylabel("Seed")
    for ri, seed in enumerate(frac.index):
        for ci, metric in enumerate(frac.columns):
            v = med.loc[seed, metric]
            f = frac.loc[seed, metric]
            if pd.isna(v) or pd.isna(f):
                continue
            color = "#ffffff" if abs(float(f) - 0.5) > 0.32 else "#111111"
            ax.text(ci, ri, f"med {v:.2f}\n{f:.0%}+", ha="center", va="center", fontsize=8, color=color)
    cbar = fig.colorbar(im, ax=ax, shrink=0.9)
    cbar.set_label("Fraction of paired basins favoring Model 2")
    ax.set_title("Expanded DRBC: primary paired seed improvement fraction (annotation: median delta, positive fraction)")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    args = parse_args()
    tables_dir: Path = args.tables_dir
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = output_dir / "figures"
    out_tables = output_dir / "tables"
    out_tables.mkdir(parents=True, exist_ok=True)

    # Read basin_metrics
    bm_path = tables_dir / "basin_metrics.csv"
    if not bm_path.exists():
        raise FileNotFoundError(f"Missing: {bm_path}")
    metrics = pd.read_csv(bm_path, dtype={"basin": str})
    metrics["basin"] = metrics["basin"].astype(str).str.zfill(8)
    metrics["abs_FHV"] = pd.to_numeric(metrics["FHV"], errors="coerce").abs()
    for col in ["NSE", "KGE", "FHV", "Peak-Timing", "Peak-MAPE", "abs_FHV"]:
        metrics[col] = pd.to_numeric(metrics[col], errors="coerce")

    # Filter to primary epochs only
    primary_rows = []
    for (model, seed), epoch in PRIMARY_EPOCHS.items():
        subset = metrics[(metrics["model"] == model) & (metrics["seed"] == seed) & (metrics["epoch"] == epoch)]
        primary_rows.append(subset)
    primary_metrics = pd.concat(primary_rows, ignore_index=True)

    # ── tables ────────────────────────────────────────────────────────────────
    summary = build_primary_epoch_summary(metrics)
    summary_path = out_tables / "primary_epoch_summary.csv"
    summary.to_csv(summary_path, index=False)
    print(f"Wrote: {summary_path.relative_to(REPO_ROOT)}")

    deltas = build_primary_epoch_basin_deltas(primary_metrics)
    deltas_path = out_tables / "primary_epoch_basin_deltas.csv"
    deltas.to_csv(deltas_path, index=False)
    print(f"Wrote: {deltas_path.relative_to(REPO_ROOT)}")

    delta_summary = build_delta_summary(deltas)
    delta_summary_path = out_tables / "primary_epoch_delta_summary.csv"
    delta_summary.to_csv(delta_summary_path, index=False)
    print(f"Wrote: {delta_summary_path.relative_to(REPO_ROOT)}")

    # ── metric boxplots ────────────────────────────────────────────────────────
    boxplot_dir = figures_dir / "metric_boxplots"
    boxplot_dir.mkdir(parents=True, exist_ok=True)
    bp_manifest = save_metric_boxplots(primary_metrics, summary, boxplot_dir)
    # save per-model/seed metric summary csv alongside figures
    metric_summary_rows = []
    for (model, seed), g in primary_metrics.groupby(["model", "seed"], sort=True):
        for metric, label in METRICS:
            if metric not in g.columns:
                continue
            vals = g[metric].dropna()
            metric_summary_rows.append({
                "model": model, "model_label": MODEL_LABELS.get(str(model), str(model)),
                "seed": int(seed), "metric": metric, "label": label,
                "n_basins": int(vals.size),
                "mean": float(vals.mean()) if not vals.empty else math.nan,
                "median": float(vals.median()) if not vals.empty else math.nan,
                "q25": float(vals.quantile(0.25)) if not vals.empty else math.nan,
                "q75": float(vals.quantile(0.75)) if not vals.empty else math.nan,
            })
    pd.DataFrame(metric_summary_rows).to_csv(boxplot_dir / "test_primary_epoch_metric_boxplot_summary.csv", index=False)
    pd.DataFrame(bp_manifest).to_csv(boxplot_dir / "test_primary_epoch_metric_boxplot_manifest.csv", index=False)
    print(f"Wrote metric boxplots to {boxplot_dir.relative_to(REPO_ROOT)}")

    # ── paired seed comparison ─────────────────────────────────────────────────
    paired_dir = figures_dir / "paired_seed_comparison"
    paired_dir.mkdir(parents=True, exist_ok=True)
    paired_charts = [
        ("delta_boxplot_with_outliers", paired_dir / "primary_paired_seed_delta_boxplots_with_outliers.png"),
        ("delta_boxplot_without_outliers", paired_dir / "primary_paired_seed_delta_boxplots_without_outliers.png"),
        ("improved_fraction_heatmap", paired_dir / "primary_paired_seed_improved_fraction_heatmap.png"),
    ]
    if not deltas.empty:
        save_delta_boxplot(deltas, paired_charts[0][1], show_fliers=True)
        save_delta_boxplot(deltas, paired_charts[1][1], show_fliers=False)
        save_improved_fraction_heatmap(deltas, paired_charts[2][1])
        # per-seed effect summary
        effect_rows = []
        for seed, g in deltas.groupby("seed", sort=True):
            for metric, label, interp in BOX_METRICS:
                if metric not in g.columns:
                    continue
                vals = g[metric].dropna()
                effect_rows.append({
                    "seed": int(seed), "metric": metric, "label": label, "interpretation": interp,
                    "n_basins": int(vals.size),
                    "mean_delta": float(vals.mean()) if not vals.empty else np.nan,
                    "median_delta": float(vals.median()) if not vals.empty else np.nan,
                    "q25_delta": float(vals.quantile(0.25)) if not vals.empty else np.nan,
                    "q75_delta": float(vals.quantile(0.75)) if not vals.empty else np.nan,
                    "positive_fraction": float((vals > 0).mean()) if not vals.empty else np.nan,
                })
        pd.DataFrame(effect_rows).to_csv(paired_dir / "primary_paired_seed_effect_summary.csv", index=False)
        pd.DataFrame([{"chart": n, "path": str(p.relative_to(REPO_ROOT))} for n, p in paired_charts]).to_csv(
            paired_dir / "primary_paired_seed_chart_manifest.csv", index=False
        )
        print(f"Wrote paired seed comparison charts to {paired_dir.relative_to(REPO_ROOT)}")
    else:
        print("No delta rows — skipping paired seed charts")

    # ── manifest json ─────────────────────────────────────────────────────────
    run_summary = {
        "experiment": "expanded_drbc_test",
        "n_basins": int(primary_metrics["basin"].nunique()),
        "n_basin_metric_rows": int(len(primary_metrics)),
        "tables": {
            "primary_epoch_summary": str(summary_path.relative_to(REPO_ROOT)),
            "primary_epoch_basin_deltas": str(deltas_path.relative_to(REPO_ROOT)),
            "primary_epoch_delta_summary": str(delta_summary_path.relative_to(REPO_ROOT)),
        },
        "figures": {
            "metric_boxplots": str(boxplot_dir.relative_to(REPO_ROOT)),
            "paired_seed_comparison": str(paired_dir.relative_to(REPO_ROOT)),
        },
    }
    manifest_path = output_dir / "performance_analysis_summary.json"
    manifest_path.write_text(json.dumps(run_summary, indent=2), encoding="utf-8")
    print(json.dumps(run_summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
