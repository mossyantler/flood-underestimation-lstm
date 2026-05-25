#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
# ]
# ///
"""Build IQR-based median-distance tier profile for expanded DRBC test basins (85).

Mirrors the tier computation in analyze_subset300_primary_metric_median_deviation_regimes.py
but uses primary_epoch_basin_deltas.csv from the expanded DRBC test evaluation.

IQR is computed across the full expanded 85-basin cohort (not the primary 38-basin IQR).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]

METRICS = ["NSE", "KGE", "FHV"]
METRIC_COLS = {m: f"{m}_model1" for m in METRICS}

TIER_ORDER = [
    "near_median_lt_0_5_iqr",
    "shoulder_0_5_to_1_5_iqr",
    "far_1_5_to_3_iqr",
    "extreme_ge_3_iqr",
]
TIER_LABELS = {
    "near_median_lt_0_5_iqr": "<0.5 IQR",
    "shoulder_0_5_to_1_5_iqr": "0.5-1.5 IQR",
    "far_1_5_to_3_iqr": "1.5-3 IQR",
    "extreme_ge_3_iqr": ">=3 IQR",
}

DEFAULT_DELTAS = REPO_ROOT / "output/model_analysis/expanded/expanded_drbc_test/tables/primary_epoch_basin_deltas.csv"
DEFAULT_EVENT_RESPONSE_SUMMARY = REPO_ROOT / "output/basin/expanded_drbc/analysis/event_response/tables/event_response_basin_summary.csv"
DEFAULT_SELECTED_CSV = REPO_ROOT / "output/basin/drbc/basin_define/camelsh_drbc_selected.csv"
DEFAULT_OUTPUT_CSV = REPO_ROOT / "output/model_analysis/expanded/expanded_drbc_test/tables/expanded_drbc_tier_profile.csv"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--deltas", type=Path, default=DEFAULT_DELTAS)
    p.add_argument("--event-response-summary", type=Path, default=DEFAULT_EVENT_RESPONSE_SUMMARY)
    p.add_argument("--selected-csv", type=Path, default=DEFAULT_SELECTED_CSV)
    p.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    return p.parse_args()


def assign_tier(distance: float) -> str:
    if distance < 0.5:
        return "near_median_lt_0_5_iqr"
    if distance < 1.5:
        return "shoulder_0_5_to_1_5_iqr"
    if distance < 3.0:
        return "far_1_5_to_3_iqr"
    return "extreme_ge_3_iqr"


def build_records(deltas: pd.DataFrame) -> pd.DataFrame:
    records = []
    for metric, col in METRIC_COLS.items():
        if col not in deltas.columns:
            continue
        values = deltas[col].dropna()
        if values.empty:
            continue
        q1 = float(values.quantile(0.25))
        q3 = float(values.quantile(0.75))
        median = float(values.median())
        iqr = q3 - q1
        for _, row in deltas.iterrows():
            v = row.get(col)
            if pd.isna(v):
                continue
            distance = abs(v - median) / iqr if iqr > 0 else np.nan
            tier = assign_tier(distance) if not np.isnan(distance) else "near_median_lt_0_5_iqr"
            records.append({
                "basin": str(row["basin"]),
                "seed": int(row["seed"]),
                "metric": metric,
                "metric_value": float(v),
                "median_distance_iqr": distance,
                "distance_tier": tier,
            })
    return pd.DataFrame(records)


def aggregate_basin_profile(records: pd.DataFrame) -> pd.DataFrame:
    counts = (
        records.pivot_table(
            index="basin",
            columns="distance_tier",
            values="metric_value",
            aggfunc="count",
            fill_value=0,
        )
        .reset_index()
        .rename_axis(columns=None)
    )
    for tier in TIER_ORDER:
        if tier not in counts.columns:
            counts[tier] = 0

    dist_stats = records.groupby("basin")["median_distance_iqr"].agg(
        mean_distance_any_metric_seed="mean",
        max_distance_any_metric_seed="max",
    ).reset_index()

    per_metric = {}
    for metric in METRICS:
        sub = records[records["metric"] == metric].groupby("basin")["median_distance_iqr"].agg(
            mean="mean", max="max"
        ).reset_index()
        sub = sub.rename(columns={
            "mean": f"{metric}_mean_median_distance_iqr",
            "max": f"{metric}_max_median_distance_iqr",
        })
        per_metric[metric] = sub

    profile = counts[["basin", *TIER_ORDER]].copy()
    profile = profile.merge(dist_stats, on="basin", how="left")
    for sub in per_metric.values():
        profile = profile.merge(sub, on="basin", how="left")

    profile["all_metric_seed_records"] = profile[TIER_ORDER].sum(axis=1)
    profile["far_or_extreme_records"] = profile["far_1_5_to_3_iqr"] + profile["extreme_ge_3_iqr"]
    total = profile["all_metric_seed_records"].replace(0, np.nan)
    profile["far_or_extreme_share"] = profile["far_or_extreme_records"] / total
    profile["dominant_distance_tier"] = profile[TIER_ORDER].idxmax(axis=1)
    profile["dominant_distance_label"] = profile["dominant_distance_tier"].map(TIER_LABELS)
    return profile


def main() -> None:
    args = parse_args()

    deltas = pd.read_csv(args.deltas, dtype={"basin": str})
    print(f"Loaded deltas: {len(deltas)} rows, {deltas['basin'].nunique()} basins")

    selected = pd.read_csv(args.selected_csv, dtype={"gauge_id": str})
    selected = selected.rename(columns={"gauge_id": "basin"})
    basin_meta = selected[["basin", "gauge_name", "state", "drain_sqkm_attr"]].copy()
    basin_meta = basin_meta.rename(columns={"drain_sqkm_attr": "area"})
    basin_meta = basin_meta.drop_duplicates("basin")

    records = build_records(deltas)
    print(f"Records for tier computation: {len(records)}")

    profile = aggregate_basin_profile(records)
    profile = profile.merge(basin_meta, on="basin", how="left")

    if args.event_response_summary.exists():
        er = pd.read_csv(args.event_response_summary, dtype={"gauge_id": str})
        er = er.rename(columns={"gauge_id": "basin"})
        keep_cols = [c for c in ["basin", "obs_q99", "q99_event_frequency", "rbi"] if c in er.columns]
        profile = profile.merge(er[keep_cols], on="basin", how="left")
        print(f"Merged event response summary: {args.event_response_summary}")
    else:
        print(f"Warning: event response summary not found at {args.event_response_summary}, skipping merge.")

    final_cols = [
        "basin", "gauge_name", "state",
        "dominant_distance_label",
        "all_metric_seed_records",
        "near_median_lt_0_5_iqr", "shoulder_0_5_to_1_5_iqr", "far_1_5_to_3_iqr", "extreme_ge_3_iqr",
        "far_or_extreme_records", "far_or_extreme_share",
        "mean_distance_any_metric_seed", "max_distance_any_metric_seed",
        "NSE_mean_median_distance_iqr", "KGE_mean_median_distance_iqr", "FHV_mean_median_distance_iqr",
        "NSE_max_median_distance_iqr", "KGE_max_median_distance_iqr", "FHV_max_median_distance_iqr",
        "area", "obs_q99", "q99_event_frequency", "rbi",
    ]
    profile = profile[[c for c in final_cols if c in profile.columns]]
    profile = profile.sort_values(
        ["far_or_extreme_records", "max_distance_any_metric_seed", "mean_distance_any_metric_seed"],
        ascending=[False, False, False],
    ).reset_index(drop=True)

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    profile.to_csv(args.output_csv, index=False)
    print(f"Wrote {args.output_csv}")
    print(f"Basins: {len(profile)} | tier distribution: {profile['dominant_distance_label'].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
