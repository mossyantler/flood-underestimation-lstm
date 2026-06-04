#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=2.0",
#   "pandas>=2.2",
# ]
# ///
"""B8 — RQ-4b NOAA event-type cohort stratify (Flash Flood / Flood / Coastal Flood / Other / NoNOAA).

Groups with < 5 events are merged into "Other". Per group: α (B3-NOAA) median, β (B4-NOAA) median.
FAR and over-pred basin-subset medians use the basin set that contributed events of that type.

Inputs:
- tables/rq2_noaa_events_expanded_overlap.csv (B2; in_expanded_85 True only)
- tables/rq2_alpha_event_peak_deficit_noaa.csv (B3 NOAA scope)
- tables/rq2_beta_window_capture_noaa.csv (B4 NOAA scope)
- tables/rq3_far_per_basin_seed.csv, rq3_over_prediction_magnitude_per_basin_seed.csv

Outputs:
- tables/rq4b_event_type_metrics.csv
- figures/rq4b_event_type_bar.png
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
MIN_GROUP_EVENTS = 5


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    tables_dir = args.output_dir / "tables"
    figures_dir = args.output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    events = pd.read_csv(tables_dir / "rq2_noaa_events_expanded_overlap.csv", dtype={"basin_id": str}, parse_dates=["peak_time"])
    events["basin_id"] = events["basin_id"].map(normalize_basin_id)
    test_start = pd.Timestamp("2014-01-01")
    test_end = pd.Timestamp("2016-12-31 23:00:00")
    events = events[events["in_expanded_85"] & (events["peak_time"] >= test_start) & (events["peak_time"] <= test_end)].copy()

    # Lump small groups → "Other"
    type_counts = events.groupby("dominant_event_type").size()
    small_types = set(type_counts[type_counts < MIN_GROUP_EVENTS].index)
    events["group"] = events["dominant_event_type"].where(~events["dominant_event_type"].isin(small_types), "Other")

    alpha = pd.read_csv(tables_dir / "rq2_alpha_event_peak_deficit_noaa.csv", comment="#", dtype={"basin_id": str}, parse_dates=["peak_time"])
    alpha["basin_id"] = alpha["basin_id"].map(normalize_basin_id)
    alpha = alpha.merge(events[["basin_id", "peak_time", "group"]], on=["basin_id", "peak_time"], how="inner")

    beta = pd.read_csv(tables_dir / "rq2_beta_window_capture_noaa.csv", comment="#", dtype={"basin_id": str}, parse_dates=["peak_time"])
    beta["basin_id"] = beta["basin_id"].map(normalize_basin_id)
    beta = beta.merge(events[["basin_id", "peak_time", "group"]], on=["basin_id", "peak_time"], how="inner")

    far = pd.read_csv(tables_dir / "rq3_far_per_basin_seed.csv", comment="#", dtype={"basin_id": str})
    far["basin_id"] = far["basin_id"].map(normalize_basin_id)
    over = pd.read_csv(tables_dir / "rq3_over_prediction_magnitude_per_basin_seed.csv", comment="#", dtype={"basin_id": str})
    over["basin_id"] = over["basin_id"].map(normalize_basin_id)

    rows = []
    groups_present = sorted(events["group"].unique())
    for grp in groups_present:
        grp_events = events[events["group"] == grp]
        grp_basins = grp_events["basin_id"].unique()
        for tau in TAU_ORDER:
            alpha_sub = alpha[(alpha["group"] == grp) & (alpha["tau"] == tau)]
            beta_sub = beta[(beta["group"] == grp) & (beta["tau"] == tau)]
            far_sub = far[far["basin_id"].isin(grp_basins) & (far["tau"] == tau)]
            over_sub = over[over["basin_id"].isin(grp_basins) & (over["tau"] == tau)]
            rows.append({
                "event_type": grp,
                "tau": tau,
                "n_events": int(grp_events.shape[0]),
                "n_basins": int(len(grp_basins)),
                "alpha_median": float(alpha_sub["peak_under_deficit"].median()) if not alpha_sub.empty else float("nan"),
                "beta_median": float(beta_sub["window_capture"].median()) if not beta_sub.empty else float("nan"),
                "far_median_basin_subset": float(far_sub["far"].median()) if not far_sub.empty else float("nan"),
                "over_pred_median_basin_subset": float(over_sub["over_pred_magnitude"].median()) if not over_sub.empty else float("nan"),
            })
    metrics = pd.DataFrame(rows)
    metrics["tau_order"] = metrics["tau"].map({t: i for i, t in enumerate(TAU_ORDER)})
    metrics = metrics.sort_values(["event_type", "tau_order"]).drop(columns="tau_order")

    metrics_path = tables_dir / "rq4b_event_type_metrics.csv"
    with metrics_path.open("w") as f:
        f.write(f"# RQ-4b — event-type × τ aggregated; groups <{MIN_GROUP_EVENTS} events lumped to Other\n")
        metrics.to_csv(f, index=False)
    print(f"[B8] wrote {metrics_path}", flush=True)
    print(metrics.to_string(index=False), flush=True)

    # Bar plot: α median by event_type × τ
    fig, axes = plt.subplots(1, 4, figsize=(18, 4))
    for ax, col, title in zip(
        axes,
        ["alpha_median", "beta_median", "far_median_basin_subset", "over_pred_median_basin_subset"],
        ["α (peak deficit)", "β (window capture)", "FAR (basin subset)", "over-pred mag (basin subset)"],
    ):
        pivot = metrics.pivot(index="event_type", columns="tau", values=col).reindex(columns=TAU_ORDER)
        pivot.plot.bar(ax=ax, legend=False)
        ax.set_title(title)
        ax.set_ylabel(col)
        ax.tick_params(axis="x", rotation=30)
        ax.grid(alpha=0.3)
    fig.suptitle("RQ-4b — NOAA event-type cohort metrics by τ")
    fig.tight_layout()
    fig_path = figures_dir / "rq4b_event_type_bar.png"
    fig.savefig(fig_path, dpi=140)
    plt.close(fig)
    print(f"[B8] wrote {fig_path}", flush=True)


if __name__ == "__main__":
    main()
