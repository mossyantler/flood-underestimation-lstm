#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=2.0",
#   "pandas>=2.2",
# ]
# ///
"""B5 — RQ-2 δ Q99 threshold recall (pooled).

For each basin/seed/τ: recall_τ = P(q_τ ≥ obs | obs ≥ Q99_basin),
denominator counts test-period (2014-2016) hours only where obs ≥ Q99.

Inputs
------
- tables/rq2_q99_per_basin_thresholds.csv (B1)
- required_series/seed{111,222,444}/primary_required_series.csv

Outputs
-------
- tables/rq2_delta_threshold_recall_per_basin_seed.csv
- tables/rq2_delta_threshold_recall_summary.csv
- figures/rq2_delta_recall_by_tau.png

Acceptance
----------
- recall ∈ [0, 1]
- n_q99_hours identical across seeds for each basin (assertion)
- cross-basin median recall monotonically increases across q50→q90→q95→q99
  (higher τ = larger predictions = more likely to clear the Q99 threshold).
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
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/expanded_drbc_test"
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


def compute_recall_for_seed(df_seed: pd.DataFrame, thresholds: pd.DataFrame, seed: int) -> pd.DataFrame:
    merged = df_seed.merge(thresholds[["basin_id", "q99_train_value"]], on="basin_id", how="inner")
    high = merged[merged["obs"] >= merged["q99_train_value"]].copy()
    rows = []
    for basin, sub in high.groupby("basin_id"):
        n_hours = len(sub)
        for tau in TAU_ORDER:
            hits = int((sub[tau] >= sub["obs"]).sum())
            recall = hits / n_hours if n_hours > 0 else float("nan")
            rows.append({
                "basin_id": basin,
                "seed": seed,
                "tau": tau,
                "n_q99_hours": n_hours,
                "n_hits": hits,
                "recall": recall,
            })
    return pd.DataFrame(rows)


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
        seed_csv = args.input_dir / f"seed{seed}" / "primary_required_series.csv"
        print(f"[B5] loading {seed_csv}", flush=True)
        df_seed = load_seed(seed_csv)
        part = compute_recall_for_seed(df_seed, thresholds, seed)
        parts.append(part)
        print(f"[B5] seed={seed} rows={len(part)}", flush=True)
        del df_seed
    recall = pd.concat(parts, ignore_index=True)

    # Assertion: n_q99_hours identical across seeds within (basin, tau)
    nq = recall.pivot_table(index=["basin_id", "tau"], columns="seed", values="n_q99_hours")
    for col_pair in [(args.seeds[0], args.seeds[1]), (args.seeds[1], args.seeds[2])]:
        if (nq[col_pair[0]] != nq[col_pair[1]]).any():
            raise AssertionError("n_q99_hours differs across seeds for some basin")
    print("[B5] assertion: n_q99_hours identical across seeds OK", flush=True)

    out_path = tables_dir / "rq2_delta_threshold_recall_per_basin_seed.csv"
    with out_path.open("w") as f:
        f.write("# RQ-2 δ — per-basin per-seed Q99 threshold recall\n")
        recall.to_csv(f, index=False)
    print(f"[B5] wrote {out_path} ({len(recall)} rows)", flush=True)

    # Summary: median across seeds within basin, then cross-basin median + IQR
    by_basin = (
        recall.groupby(["basin_id", "tau"])["recall"]
        .median()
        .reset_index(name="basin_seed_median")
    )
    summary = (
        by_basin.groupby("tau")["basin_seed_median"]
        .agg(
            basin_median_recall="median",
            basin_iqr_low=lambda s: s.quantile(0.25),
            basin_iqr_high=lambda s: s.quantile(0.75),
            n_basins="count",
        )
        .reset_index()
    )
    total_hours = int(recall.groupby("seed").apply(lambda g: g.iloc[0]["n_q99_hours"] if not g.empty else 0).sum() // 1) if False else int(recall[recall["tau"] == TAU_ORDER[0]]["n_q99_hours"].sum())
    summary["total_q99_hours"] = total_hours
    summary["tau_order"] = summary["tau"].map({t: i for i, t in enumerate(TAU_ORDER)})
    summary = summary.sort_values("tau_order").drop(columns="tau_order")

    summary_path = tables_dir / "rq2_delta_threshold_recall_summary.csv"
    with summary_path.open("w") as f:
        f.write("# RQ-2 δ summary — cross-basin median + IQR; total_q99_hours pooled across basins×seeds\n")
        summary.to_csv(f, index=False)
    print(f"[B5] wrote {summary_path}", flush=True)

    # Acceptance: monotone INCREASE in τ across q50→q99
    ordered = summary.set_index("tau").reindex(QUANTILE_TAU_ORDER)["basin_median_recall"].values
    for i in range(len(ordered) - 1):
        assert ordered[i] <= ordered[i + 1] + 1e-9, (
            f"recall NOT non-decreasing across q50→q99: {dict(zip(QUANTILE_TAU_ORDER, ordered))}"
        )
    assert recall["recall"].between(0, 1).all(), "recall values outside [0, 1]"
    print("[B5] acceptance: q50→q99 monotone increase + recall ∈ [0,1] PASS", flush=True)

    # Figure
    fig, ax = plt.subplots(figsize=(7, 4))
    ordered_all = summary.set_index("tau").reindex(TAU_ORDER)
    ax.plot(range(len(TAU_ORDER)), ordered_all["basin_median_recall"], marker="o", color="C2", label="recall (basin median)")
    ax.fill_between(range(len(TAU_ORDER)), ordered_all["basin_iqr_low"], ordered_all["basin_iqr_high"], alpha=0.18, color="C2")
    ax.set_xticks(range(len(TAU_ORDER)))
    ax.set_xticklabels(TAU_ORDER)
    ax.set_xlabel("τ")
    ax.set_ylabel("Q99 threshold recall")
    ax.set_title("RQ-2 δ — pooled Q99 exceedance recall by τ")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig_path = figures_dir / "rq2_delta_recall_by_tau.png"
    fig.savefig(fig_path, dpi=140)
    plt.close(fig)
    print(f"[B5] wrote {fig_path}", flush=True)


if __name__ == "__main__":
    main()
