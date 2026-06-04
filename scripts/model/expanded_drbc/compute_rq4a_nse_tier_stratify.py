#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=2.0",
#   "pandas>=2.2",
# ]
# ///
"""B7 — RQ-4a M1 NSE 3-tier cohort stratify.

Cohort: top/mid/bottom 1/3 by M1 deterministic seed-median NSE (from A1).
Aggregate α (B3 Q99), β (B4 Q99), δ (B5), FAR + over-pred (B6) per tier per τ.

Inputs (all per-basin or per-basin-seed tables produced upstream):
- tables/rq1_central_metrics_seed_median.csv  (A1; M1 NSE per basin)
- tables/rq2_alpha_event_peak_deficit_q99.csv
- tables/rq2_beta_window_capture_q99.csv
- tables/rq2_delta_threshold_recall_per_basin_seed.csv
- tables/rq3_far_per_basin_seed.csv
- tables/rq3_over_prediction_magnitude_per_basin_seed.csv

Outputs:
- tables/rq4a_nse_tier_assignments.csv
- tables/rq4a_nse_tier_metrics.csv
- figures/rq4a_tier_metric_heatmap.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

LIB_ROOT = Path(__file__).resolve().parents[2] / "_lib"
if str(LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(LIB_ROOT))

from expanded_drbc import TAU_ORDER, normalize_basin_id  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/primary/metrics"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    tables_dir = args.output_dir / "tables"
    figures_dir = args.output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    central = pd.read_csv(tables_dir / "rq1_central_metrics_seed_median.csv", comment="#", dtype={"basin_id": str})
    central["basin_id"] = central["basin_id"].map(normalize_basin_id)
    m1_nse = central[central["metric"] == "nse"][["basin_id", "model1"]].rename(columns={"model1": "m1_nse_seed_median"})

    # Tier via pd.qcut on M1 NSE — top/mid/bottom 1/3
    m1_nse["tier"] = pd.qcut(
        m1_nse["m1_nse_seed_median"],
        q=3,
        labels=["bottom", "mid", "top"],
    )
    assignments_path = tables_dir / "rq4a_nse_tier_assignments.csv"
    m1_nse.to_csv(assignments_path, index=False)
    print(f"[B7] wrote {assignments_path}", flush=True)
    print(m1_nse.groupby("tier").size().to_dict(), flush=True)

    # Aggregate metrics by tier × τ
    # α: long form CSV — basin_id, seed, peak_time, tau, peak_under_deficit
    alpha = pd.read_csv(tables_dir / "rq2_alpha_event_peak_deficit_q99.csv", comment="#", dtype={"basin_id": str})
    alpha["basin_id"] = alpha["basin_id"].map(normalize_basin_id)
    alpha_by_basin = (
        alpha.groupby(["basin_id", "seed", "tau"])["peak_under_deficit"].median().reset_index()
        .groupby(["basin_id", "tau"])["peak_under_deficit"].median().reset_index(name="alpha_basin_median")
    )

    beta = pd.read_csv(tables_dir / "rq2_beta_window_capture_q99.csv", comment="#", dtype={"basin_id": str})
    beta["basin_id"] = beta["basin_id"].map(normalize_basin_id)
    beta_by_basin = (
        beta.groupby(["basin_id", "seed", "tau"])["window_capture"].median().reset_index()
        .groupby(["basin_id", "tau"])["window_capture"].median().reset_index(name="beta_basin_median")
    )

    delta = pd.read_csv(tables_dir / "rq2_delta_threshold_recall_per_basin_seed.csv", comment="#", dtype={"basin_id": str})
    delta["basin_id"] = delta["basin_id"].map(normalize_basin_id)
    delta_by_basin = (
        delta.groupby(["basin_id", "tau"])["recall"].median().reset_index(name="delta_basin_median")
    )

    far = pd.read_csv(tables_dir / "rq3_far_per_basin_seed.csv", comment="#", dtype={"basin_id": str})
    far["basin_id"] = far["basin_id"].map(normalize_basin_id)
    far_by_basin = far.groupby(["basin_id", "tau"])["far"].median().reset_index(name="far_basin_median")

    over = pd.read_csv(tables_dir / "rq3_over_prediction_magnitude_per_basin_seed.csv", comment="#", dtype={"basin_id": str})
    over["basin_id"] = over["basin_id"].map(normalize_basin_id)
    over_by_basin = over.groupby(["basin_id", "tau"])["over_pred_magnitude"].median().reset_index(name="over_pred_basin_median")

    # Merge into one per-basin frame
    per_basin = alpha_by_basin
    for other in (beta_by_basin, delta_by_basin, far_by_basin, over_by_basin):
        per_basin = per_basin.merge(other, on=["basin_id", "tau"], how="outer")
    per_basin = per_basin.merge(m1_nse[["basin_id", "tier"]], on="basin_id", how="left")

    # Tier × τ aggregation
    tier_metrics = (
        per_basin.groupby(["tier", "tau"], observed=True)
        .agg(
            alpha_median=("alpha_basin_median", "median"),
            beta_median=("beta_basin_median", "median"),
            delta_median=("delta_basin_median", "median"),
            far_median=("far_basin_median", "median"),
            over_pred_median=("over_pred_basin_median", "median"),
            n_basins=("basin_id", "nunique"),
        )
        .reset_index()
    )
    tier_metrics["tau_order"] = tier_metrics["tau"].map({t: i for i, t in enumerate(TAU_ORDER)})
    tier_metrics["tier_order"] = tier_metrics["tier"].map({"bottom": 0, "mid": 1, "top": 2})
    tier_metrics = tier_metrics.sort_values(["tier_order", "tau_order"]).drop(columns=["tau_order", "tier_order"])

    metrics_path = tables_dir / "rq4a_nse_tier_metrics.csv"
    with metrics_path.open("w") as f:
        f.write("# RQ-4a — tier (M1 NSE top/mid/bottom 1/3) × τ aggregated metrics\n")
        tier_metrics.to_csv(f, index=False)
    print(f"[B7] wrote {metrics_path}", flush=True)
    print(tier_metrics.to_string(index=False), flush=True)

    # Heatmap: rows = tier, cols = τ, panel per metric
    metrics_to_plot = ["alpha_median", "beta_median", "delta_median", "far_median", "over_pred_median"]
    fig, axes = plt.subplots(1, len(metrics_to_plot), figsize=(4 * len(metrics_to_plot), 3.5))
    for ax, metric in zip(axes, metrics_to_plot):
        pivot = tier_metrics.pivot(index="tier", columns="tau", values=metric)
        pivot = pivot.reindex(index=["top", "mid", "bottom"], columns=TAU_ORDER)
        im = ax.imshow(pivot.values, aspect="auto", cmap="viridis")
        ax.set_xticks(range(len(TAU_ORDER)))
        ax.set_xticklabels(TAU_ORDER, rotation=30)
        ax.set_yticks(range(3))
        ax.set_yticklabels(["top", "mid", "bottom"])
        ax.set_title(metric)
        for (i, j), v in np.ndenumerate(pivot.values):
            if pd.notna(v):
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", color="white", fontsize=8)
        plt.colorbar(im, ax=ax, fraction=0.04)
    fig.suptitle("RQ-4a — M1-NSE tier × τ aggregated metrics")
    fig.tight_layout()
    fig_path = figures_dir / "rq4a_tier_metric_heatmap.png"
    fig.savefig(fig_path, dpi=140)
    plt.close(fig)
    print(f"[B7] wrote {fig_path}", flush=True)


if __name__ == "__main__":
    main()
