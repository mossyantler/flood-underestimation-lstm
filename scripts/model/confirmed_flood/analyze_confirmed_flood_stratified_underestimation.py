#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
# ]
# ///
"""Compute flood-tier stratum underestimation metrics for confirmed flood events.

Strata are defined by NOAA flood tier (minor / moderate / major), using nested
plus-strata (≥ moderate, ≥ major) and their complements, plus a NOAA-corroborated
subset.  Metrics are computed at event-peak level and aggregated basin → seed → final.

Input
-----
output/model_analysis/confirmed_flood/performance/drbc_confirmed_flood_performance.csv

Outputs
-------
tables/confirmed_flood_stratified_underestimation_by_seed.csv
tables/confirmed_flood_stratified_underestimation_summary.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
PERF_CSV = (
    REPO_ROOT
    / "output/model_analysis/confirmed_flood/performance"
    / "drbc_confirmed_flood_performance.csv"
)
OUTPUT_TABLES_DIR = (
    REPO_ROOT / "output/model_analysis/confirmed_flood/tables"
)

OFFICIAL_SEEDS: list[int] = [111, 222, 444]
TIER_ORDER = ["minor", "moderate", "major"]

# quantile column in raw CSV → unified pred_col name
QUANTILE_MAP: dict[str, str] = {
    "det": "model1",
    "q50": "q50",
    "q90": "q90",
    "q95": "q95",
    "q99": "q99",
}
PRED_COLS: list[str] = ["model1", "q50", "q90", "q95", "q99"]

STRATA: list[str] = [
    "all",
    "minor_only",      # tier == minor
    "moderate_only",   # tier == moderate
    "major_only",      # tier == major
    "moderate_plus",   # tier ∈ {moderate, major}
    "below_moderate",  # tier == minor  (alias for minor_only, kept for compat)
    "major_plus",      # tier == major   (alias for major_only, kept for compat)
    "below_major",     # tier ∈ {minor, moderate}
    "noaa_corroborated",
]

_METRIC_COLS: list[str] = [
    f"{c}_{m}" for c in PRED_COLS
    for m in ["under_frac", "med_rel_bias", "cond_under_magnitude", "cond_under_abs_magnitude"]
]


def load_performance(
    path: Path = PERF_CSV,
    seeds: list[int] = OFFICIAL_SEEDS,
) -> pd.DataFrame:
    """Load and pivot raw performance CSV to wide format (one row per event x seed)."""
    df = pd.read_csv(path)
    df = df[df["seed"].isin(seeds)].copy()
    df["pred_col"] = df["quantile"].map(QUANTILE_MAP)

    # obs is identical across quantiles for same event+seed — grab once
    meta = (
        df[df["quantile"] == "det"][
            ["event_id", "usgs_id", "seed", "flood_tier", "noaa_corroborated", "obs_peak_cms"]
        ]
        .rename(columns={"obs_peak_cms": "obs"})
        .reset_index(drop=True)
    )

    # pivot pred_peak_cms by pred_col
    pred_wide = df.pivot_table(
        index=["event_id", "seed"],
        columns="pred_col",
        values="pred_peak_cms",
        aggfunc="first",
    ).reset_index()
    pred_wide.columns.name = None

    result = meta.merge(pred_wide, on=["event_id", "seed"], how="inner")
    return result[["event_id", "usgs_id", "seed", "flood_tier", "noaa_corroborated", "obs"] + PRED_COLS]


def assign_strata(df: pd.DataFrame) -> pd.DataFrame:
    """Return long-form DataFrame with a 'stratum' column (one row per event x stratum)."""
    parts: list[pd.DataFrame] = []
    masks: dict[str, pd.Series] = {
        "all": pd.Series(True, index=df.index),
        "minor_only": df["flood_tier"] == "minor",
        "moderate_only": df["flood_tier"] == "moderate",
        "major_only": df["flood_tier"] == "major",
        "moderate_plus": df["flood_tier"].isin(["moderate", "major"]),
        "below_moderate": df["flood_tier"] == "minor",
        "major_plus": df["flood_tier"] == "major",
        "below_major": df["flood_tier"].isin(["minor", "moderate"]),
        "noaa_corroborated": df["noaa_corroborated"] == True,
    }
    for stratum, mask in masks.items():
        chunk = df[mask].copy()
        chunk["stratum"] = stratum
        parts.append(chunk)
    return pd.concat(parts, ignore_index=True)


def compute_basin_metrics(long_df: pd.DataFrame) -> pd.DataFrame:
    """Per (stratum x basin x seed) → metrics for each pred_col."""
    records: list[dict] = []
    for (stratum, basin, seed), grp in long_df.groupby(["stratum", "usgs_id", "seed"]):
        obs = grp["obs"].values
        row: dict = {
            "stratum": stratum,
            "basin": basin,
            "seed": seed,
            "n_events": len(grp),
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
    """Basin median → per (seed x stratum) summary."""
    records: list[dict] = []
    for (seed, stratum), grp in basin_metrics.groupby(["seed", "stratum"]):
        row: dict = {
            "seed": seed,
            "stratum": stratum,
            "n_basins": len(grp),
            "n_events_median": float(grp["n_events"].median()),
        }
        for col in _METRIC_COLS:
            row[col] = float(grp[col].median())
        records.append(row)
    return pd.DataFrame(records)


def aggregate_to_final_summary(seed_summary: pd.DataFrame) -> pd.DataFrame:
    """Seed median/min/max → final (stratum) summary."""
    records: list[dict] = []
    for stratum, grp in seed_summary.groupby("stratum"):
        row: dict = {
            "stratum": stratum,
            "n_basins": float(grp["n_basins"].median()),
            "n_events_median": float(grp["n_events_median"].median()),
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
    by_seed_path = output_dir / "confirmed_flood_stratified_underestimation_by_seed.csv"
    summary_path = output_dir / "confirmed_flood_stratified_underestimation_summary.csv"
    seed_summary.to_csv(by_seed_path, index=False)
    final_summary.to_csv(summary_path, index=False)
    print(f"Wrote {by_seed_path}")
    print(f"Wrote {summary_path}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--perf-csv", type=Path, default=PERF_CSV)
    parser.add_argument("--seeds", nargs="+", type=int, default=OFFICIAL_SEEDS)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_TABLES_DIR)
    args = parser.parse_args(argv)

    print("Loading confirmed flood performance data ...")
    df = load_performance(args.perf_csv, seeds=args.seeds)
    print(f"  {len(df):,} event×seed rows, {df['usgs_id'].nunique()} basins, "
          f"{df['event_id'].nunique()} events")

    print("Assigning strata ...")
    long_df = assign_strata(df)

    print("Computing per-basin metrics ...")
    basin_metrics = compute_basin_metrics(long_df)

    print("Aggregating ...")
    seed_summary = aggregate_to_seed_summary(basin_metrics)
    final_summary = aggregate_to_final_summary(seed_summary)

    write_outputs(seed_summary, final_summary, output_dir=args.output_dir)
    print("Done.")


if __name__ == "__main__":
    main()
