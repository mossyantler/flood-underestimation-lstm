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
    REPO_ROOT / "output/model_analysis/expanded/expanded_drbc_test/required_series"
)
OUTPUT_TABLES_DIR = (
    REPO_ROOT / "output/model_analysis/expanded/expanded_drbc_test/tables"
)

OFFICIAL_SEEDS: list[int] = [111, 222, 444]
PRED_COLS: list[str] = ["model1", "q50", "q90", "q95", "q99"]
STRATA: list[str] = ["all", "obs_q90_plus", "obs_q95_plus", "obs_q99_plus"]
STRATUM_QUANTILE: dict[str, float] = {
    "obs_q90_plus": 0.90,
    "obs_q95_plus": 0.95,
    "obs_q99_plus": 0.99,
}


def load_required_series(
    seeds: list[int] = OFFICIAL_SEEDS,
    base_dir: Path = REQUIRED_SERIES_DIR,
) -> pd.DataFrame:
    """Load and concatenate required_series CSVs for given seeds."""
    dfs: list[pd.DataFrame] = []
    for seed in seeds:
        path = base_dir / f"seed{seed}" / "primary_required_series.csv"
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
        else:
            thr_col = stratum.replace("obs_", "").replace("_plus", "_thr")
            mask = valid["obs"] > valid[thr_col]
        chunk = valid[mask].copy()
        chunk["stratum"] = stratum
        parts.append(chunk)

    return pd.concat(parts, ignore_index=True)


_METRIC_COLS: list[str] = [
    f"{c}_{m}" for c in PRED_COLS for m in ["under_frac", "med_rel_bias"]
]


def compute_basin_metrics(long_df: pd.DataFrame) -> pd.DataFrame:
    """Per (stratum x basin x seed) -> under_fraction and median_rel_bias for each pred_col.

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
            row[f"{col}_under_frac"] = float((pred < obs).mean())
            rel_err = (pred - obs) / obs
            row[f"{col}_med_rel_bias"] = float(np.median(rel_err))
        records.append(row)
    return pd.DataFrame(records)
