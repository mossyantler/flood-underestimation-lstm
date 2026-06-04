#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
# ]
# ///
"""Compute obs-based stratum underestimation metrics for 85-basin expanded DRBC test.

Strata are defined by basin-specific percentiles of observed discharge (NOT model quantiles).
For each (stratum x prediction column), computes:
  under_fraction   -- P(pred < obs)
  median_rel_bias  -- median((pred - obs) / obs)

Outputs
-------
tables/stratified_underestimation_summary.csv   paper Table 1 (seed-median across 85 basins)
tables/stratified_underestimation_by_seed.csv   per-seed basin medians (robustness check)
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
REQUIRED_SERIES_DIR = (
    REPO_ROOT / "output/model_analysis/primary/metrics/data/required_series"
)
OUTPUT_TABLES_DIR = (
    REPO_ROOT / "output/model_analysis/primary/metrics/tables"
)

OFFICIAL_SEEDS: list[int] = [111, 222, 444]
PRED_COLS: list[str] = ["model1", "q50", "q90", "q95", "q99"]
STRATA: list[str] = [
    "all",
    "obs_q50_plus", "obs_q50_minus",
    "obs_q90_plus", "obs_q90_minus",
    "obs_q95_plus", "obs_q95_minus",
    "obs_q99_plus", "obs_q99_minus",
]
STRATUM_QUANTILE: dict[str, float] = {
    "obs_q50_plus": 0.50, "obs_q50_minus": 0.50,
    "obs_q90_plus": 0.90, "obs_q90_minus": 0.90,
    "obs_q95_plus": 0.95, "obs_q95_minus": 0.95,
    "obs_q99_plus": 0.99, "obs_q99_minus": 0.99,
}


def load_required_series(
    seeds: list[int] = OFFICIAL_SEEDS,
    base_dir: Path = REQUIRED_SERIES_DIR,
) -> pd.DataFrame:
    """Load and concatenate required_series CSVs for given seeds."""
    dfs: list[pd.DataFrame] = []
    for seed in seeds:
        path = base_dir / f"seed{seed}" / "required_series.csv"
        df = pd.read_csv(path, parse_dates=["datetime"])
        dfs.append(df)
    combined = pd.concat(dfs, ignore_index=True)
    keep = ["seed", "basin", "datetime", "obs"] + PRED_COLS
    return combined[keep]


def compute_basin_thresholds(df: pd.DataFrame) -> pd.DataFrame:
    """Compute Q90/Q95/Q99 of observed discharge per basin from valid obs rows."""
    valid = df[df["obs"].notna() & (df["obs"] > 0)]
    records = []
    for basin, grp in valid.groupby("basin"):
        obs = grp["obs"]
        records.append({
            "basin": basin,
            "q50_thr": float(obs.quantile(0.50)),
            "q90_thr": float(obs.quantile(0.90)),
            "q95_thr": float(obs.quantile(0.95)),
            "q99_thr": float(obs.quantile(0.99)),
        })
    return pd.DataFrame(records)


def assign_strata(df: pd.DataFrame, thresholds: pd.DataFrame) -> pd.DataFrame:
    """Return long-form DataFrame with a 'stratum' column.

    Filters to obs > 0 and obs not NaN. Each valid row appears once per stratum
    it belongs to (nested: q99_plus subset q95_plus subset q90_plus subset all).
    """
    valid = df.merge(thresholds, on="basin", how="left")
    valid = valid[valid["obs"].notna() & (valid["obs"] > 0)].copy()

    parts: list[pd.DataFrame] = []
    for stratum in STRATA:
        if stratum == "all":
            mask = pd.Series(True, index=valid.index)
        elif stratum.endswith("_plus"):
            thr_col = stratum.replace("obs_", "").replace("_plus", "_thr")
            mask = valid["obs"] > valid[thr_col]
        else:  # _minus: complement (obs <= threshold)
            thr_col = stratum.replace("obs_", "").replace("_minus", "_thr")
            mask = valid["obs"] <= valid[thr_col]
        chunk = valid[mask].copy()
        chunk["stratum"] = stratum
        parts.append(chunk)

    return pd.concat(parts, ignore_index=True)


_METRIC_COLS: list[str] = [
    f"{c}_{m}" for c in PRED_COLS
    for m in ["under_frac", "med_rel_bias", "cond_under_magnitude", "cond_under_abs_magnitude"]
]


def compute_basin_metrics(long_df: pd.DataFrame) -> pd.DataFrame:
    """Per (stratum x basin x seed) -> metrics for each pred_col.

    Metrics:
      under_frac           -- P(pred < obs)
      med_rel_bias         -- median((pred - obs) / obs) over all timesteps
      cond_under_magnitude -- median((obs - pred) / obs) where pred < obs only
                              (how large is the underestimation when it occurs)

    Input: long-form DataFrame from assign_strata (has 'stratum' column).
    """
    records: list[dict] = []
    for (stratum, basin, seed), grp in long_df.groupby(["stratum", "basin", "seed"]):
        obs = grp["obs"].values
        row: dict = {
            "stratum": stratum,
            "basin": basin,
            "seed": seed,
            "n_timesteps": len(grp),
        }
        for col in PRED_COLS:
            pred = grp[col].values
            under_mask = pred < obs
            row[f"{col}_under_frac"] = float(under_mask.mean())
            row[f"{col}_med_rel_bias"] = float(np.median((pred - obs) / obs))
            if under_mask.any():
                row[f"{col}_cond_under_magnitude"] = float(
                    np.median((obs[under_mask] - pred[under_mask]) / obs[under_mask])
                )
                row[f"{col}_cond_under_abs_magnitude"] = float(
                    np.median(obs[under_mask] - pred[under_mask])
                )
            else:
                row[f"{col}_cond_under_magnitude"] = float("nan")
                row[f"{col}_cond_under_abs_magnitude"] = float("nan")
        records.append(row)
    return pd.DataFrame(records)


def aggregate_to_seed_summary(basin_metrics: pd.DataFrame) -> pd.DataFrame:
    """Basin median -> per (seed x stratum) summary."""
    records: list[dict] = []
    for (seed, stratum), grp in basin_metrics.groupby(["seed", "stratum"]):
        row: dict = {
            "seed": seed,
            "stratum": stratum,
            "n_basins": len(grp),
            "n_timesteps_median": float(grp["n_timesteps"].median()),
        }
        for col in _METRIC_COLS:
            row[col] = float(grp[col].median())
        records.append(row)
    return pd.DataFrame(records)


def aggregate_to_final_summary(seed_summary: pd.DataFrame) -> pd.DataFrame:
    """Seed median/min/max -> final (stratum) summary."""
    records: list[dict] = []
    for stratum, grp in seed_summary.groupby("stratum"):
        row: dict = {
            "stratum": stratum,
            "n_basins": float(grp["n_basins"].median()),
            "n_timesteps_median": float(grp["n_timesteps_median"].median()),
        }
        for col in _METRIC_COLS:
            row[col] = float(grp[col].median())
            row[f"{col}_min"] = float(grp[col].min())
            row[f"{col}_max"] = float(grp[col].max())
        records.append(row)
    order = {s: i for i, s in enumerate(STRATA)}
    result = pd.DataFrame(records)
    result["_order"] = result["stratum"].map(order)
    return result.sort_values("_order").drop(columns=["_order"]).reset_index(drop=True)


def write_outputs(
    seed_summary: pd.DataFrame,
    final_summary: pd.DataFrame,
    output_dir: Path = OUTPUT_TABLES_DIR,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    by_seed_path = output_dir / "stratified_underestimation_by_seed.csv"
    summary_path = output_dir / "stratified_underestimation_summary.csv"
    seed_summary.to_csv(by_seed_path, index=False)
    final_summary.to_csv(summary_path, index=False)
    print(f"Wrote {by_seed_path}")
    print(f"Wrote {summary_path}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seeds",
        nargs="+",
        type=int,
        default=OFFICIAL_SEEDS,
        help="Seeds to process (default: 111 222 444)",
    )
    parser.add_argument(
        "--required-series-dir",
        type=Path,
        default=REQUIRED_SERIES_DIR,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_TABLES_DIR,
    )
    args = parser.parse_args(argv)

    print(f"Loading required_series for seeds {args.seeds} ...")
    df = load_required_series(args.seeds, base_dir=args.required_series_dir)
    print(f"  Loaded {len(df):,} rows, {df['basin'].nunique()} basins")

    print("Computing basin-specific Q90/Q95/Q99 thresholds ...")
    thresholds = compute_basin_thresholds(df)

    print("Assigning strata ...")
    long_df = assign_strata(df, thresholds)

    print("Computing per-basin metrics ...")
    basin_metrics = compute_basin_metrics(long_df)

    print("Aggregating ...")
    seed_summary = aggregate_to_seed_summary(basin_metrics)
    final_summary = aggregate_to_final_summary(seed_summary)

    write_outputs(seed_summary, final_summary, output_dir=args.output_dir)
    print("Done.")


if __name__ == "__main__":
    main()
