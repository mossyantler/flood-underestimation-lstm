#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=2.0",
#   "pandas>=2.2",
# ]
# ///
"""B6 — RQ-3 cost (FAR + over-prediction magnitude).

FAR_τ = P(q_τ > Q99_basin | obs < Q99_basin) per basin per seed per τ.
over_pred_mag_τ = mean(q_τ − obs | q_τ > obs) per basin per seed per τ.

Outputs
-------
- tables/rq3_far_per_basin_seed.csv + _summary.csv
- tables/rq3_over_prediction_magnitude_per_basin_seed.csv + _summary.csv
- figures/rq3_cost_recall_tradeoff.png  (FAR vs δ recall scatter, points by τ; reads B5 summary)
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

from expanded_drbc import (  # noqa: E402
    SEEDS,
    TAU_ORDER,
    TEST_PERIOD,
    filter_valid_rows,
    normalize_basin_id,
)

QUANTILE_TAU_ORDER = ("q50", "q90", "q95", "q99")

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/primary/metrics"
DEFAULT_INPUT_DIR = DEFAULT_OUTPUT_DIR / "required_series"


def load_seed(seed_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(
        seed_csv,
        usecols=["basin", "datetime", "obs", "model1", "q50", "q90", "q95", "q99"],
        dtype={"basin": str},
        parse_dates=["datetime"],
    )
    df["basin_id"] = df["basin"].map(normalize_basin_id)
    df = filter_valid_rows(df, obs_col="obs")
    ts_start = pd.Timestamp(TEST_PERIOD[0])
    ts_end = pd.Timestamp(TEST_PERIOD[1]) + pd.Timedelta(hours=23)
    df = df[(df["datetime"] >= ts_start) & (df["datetime"] <= ts_end)].copy()
    return df


def compute_cost_for_seed(df_seed: pd.DataFrame, thresholds: pd.DataFrame, seed: int) -> pd.DataFrame:
    merged = df_seed.merge(thresholds[["basin_id", "q99_train_value"]], on="basin_id", how="inner")
    rows = []
    for basin, sub in merged.groupby("basin_id"):
        q99 = float(sub["q99_train_value"].iloc[0])
        below = sub[sub["obs"] < q99]
        for tau in TAU_ORDER:
            pred = sub[tau]
            n_below = len(below)
            if n_below == 0:
                far = float("nan")
            else:
                far = float((below[tau] > q99).sum()) / n_below
            over_mask = sub[tau] > sub["obs"]
            if over_mask.sum() == 0:
                over_mag = float("nan")
            else:
                over_mag = float((sub.loc[over_mask, tau] - sub.loc[over_mask, "obs"]).mean())
            rows.append({
                "basin_id": basin,
                "seed": seed,
                "tau": tau,
                "n_below_q99_hours": n_below,
                "far": far,
                "over_pred_magnitude": over_mag,
            })
    return pd.DataFrame(rows)


def summarize(per_basin_seed: pd.DataFrame, col: str) -> pd.DataFrame:
    by_basin = (
        per_basin_seed.groupby(["basin_id", "tau"])[col]
        .median()
        .reset_index(name="basin_seed_median")
    )
    summary = (
        by_basin.groupby("tau")["basin_seed_median"]
        .agg(
            basin_median="median",
            basin_iqr_low=lambda s: s.quantile(0.25),
            basin_iqr_high=lambda s: s.quantile(0.75),
            n_basins="count",
        )
        .reset_index()
    )
    summary["tau_order"] = summary["tau"].map({t: i for i, t in enumerate(TAU_ORDER)})
    summary = summary.sort_values("tau_order").drop(columns="tau_order")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(SEEDS))
    args = parser.parse_args()

    tables_dir = args.output_dir / "tables"
    figures_dir = args.output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    thresholds = pd.read_csv(
        tables_dir / "rq2_q99_per_basin_thresholds.csv",
        comment="#",
        dtype={"basin_id": str},
    )
    thresholds["basin_id"] = thresholds["basin_id"].map(normalize_basin_id)

    parts: list[pd.DataFrame] = []
    for seed in args.seeds:
        seed_csv = args.input_dir / f"seed{seed}" / "required_series.csv"
        print(f"[B6] loading {seed_csv}", flush=True)
        df_seed = load_seed(seed_csv)
        part = compute_cost_for_seed(df_seed, thresholds, seed)
        parts.append(part)
        print(f"[B6] seed={seed} rows={len(part)}", flush=True)
        del df_seed
    cost = pd.concat(parts, ignore_index=True)

    far_path = tables_dir / "rq3_far_per_basin_seed.csv"
    with far_path.open("w") as f:
        f.write("# RQ-3 FAR — per-basin per-seed per τ; FAR = P(q_τ > Q99 | obs < Q99)\n")
        cost[["basin_id", "seed", "tau", "n_below_q99_hours", "far"]].to_csv(f, index=False)
    print(f"[B6] wrote {far_path}", flush=True)

    over_path = tables_dir / "rq3_over_prediction_magnitude_per_basin_seed.csv"
    with over_path.open("w") as f:
        f.write("# RQ-3 over-prediction magnitude — mean(q_τ − obs | q_τ > obs) per basin/seed/τ\n")
        cost[["basin_id", "seed", "tau", "over_pred_magnitude"]].to_csv(f, index=False)
    print(f"[B6] wrote {over_path}", flush=True)

    far_summary = summarize(cost, "far")
    over_summary = summarize(cost, "over_pred_magnitude")

    far_sum_path = tables_dir / "rq3_far_summary.csv"
    with far_sum_path.open("w") as f:
        f.write("# RQ-3 FAR summary — cross-basin median + IQR per τ\n")
        far_summary.to_csv(f, index=False)
    over_sum_path = tables_dir / "rq3_over_prediction_magnitude_summary.csv"
    with over_sum_path.open("w") as f:
        f.write("# RQ-3 over-pred magnitude summary — cross-basin median + IQR per τ\n")
        over_summary.to_csv(f, index=False)
    print(f"[B6] wrote {far_sum_path} and {over_sum_path}", flush=True)

    # Acceptance: FAR monotone non-decreasing q50→q99
    ordered_far = far_summary.set_index("tau").reindex(QUANTILE_TAU_ORDER)["basin_median"].values
    for i in range(len(ordered_far) - 1):
        assert ordered_far[i] <= ordered_far[i + 1] + 1e-9, (
            f"FAR NOT non-decreasing across q50→q99: {dict(zip(QUANTILE_TAU_ORDER, ordered_far))}"
        )
    assert cost["far"].dropna().between(0, 1).all(), "FAR values outside [0, 1]"
    assert (cost["over_pred_magnitude"].dropna() >= 0).all(), "over-prediction magnitude must be >= 0"
    print("[B6] acceptance: FAR q50→q99 non-decreasing + range checks PASS", flush=True)

    # Tradeoff figure (FAR vs recall)
    recall_path = tables_dir / "rq2_delta_threshold_recall_summary.csv"
    if recall_path.exists():
        recall_summary = pd.read_csv(recall_path, comment="#")
        recall_ordered = recall_summary.set_index("tau").reindex(TAU_ORDER)
        far_ordered = far_summary.set_index("tau").reindex(TAU_ORDER)
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.plot(far_ordered["basin_median"], recall_ordered["basin_median_recall"], "-", color="gray", alpha=0.4)
        for tau in TAU_ORDER:
            x = far_ordered.loc[tau, "basin_median"]
            y = recall_ordered.loc[tau, "basin_median_recall"]
            ax.scatter(x, y, s=80)
            ax.annotate(tau, (x, y), textcoords="offset points", xytext=(8, 6), fontsize=10)
        ax.set_xlabel("FAR (cross-basin median)")
        ax.set_ylabel("Q99 recall (cross-basin median)")
        ax.set_title("RQ-2/3 — recall vs FAR tradeoff by τ")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig_path = figures_dir / "rq3_cost_recall_tradeoff.png"
        fig.savefig(fig_path, dpi=140)
        plt.close(fig)
        print(f"[B6] wrote {fig_path}", flush=True)


if __name__ == "__main__":
    main()
