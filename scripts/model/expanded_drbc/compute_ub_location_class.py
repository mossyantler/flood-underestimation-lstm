#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=2.0",
#   "pandas>=2.2",
# ]
# ///
"""Uncertainty Band — obs location classification at Q99/NOAA event peaks.

For each event peak, classify observed flow relative to the q50~q99 band
into one of five classes:

  Class        | Condition
  below_q50    | obs <= q50          (overestimation even at central)
  q50_to_q90   | q50 < obs <= q90
  q90_to_q95   | q90 < obs <= q95
  q95_to_q99   | q95 < obs <= q99
  above_q99    | obs > q99           (band failed; q99 still underestimates)

A good result is obs landing inside the band with above_q99 fraction small.
This analysis complements RQ-2 (peak deficit α) by showing where obs sits
within the full q50~q99 band, not just whether q_τ ≥ obs at one τ.

Dual scope: Q99 (85 basin / 926 events) and NOAA confirmed flood (21 basin / 65 events).

Aggregation: per-event class → per-basin-seed class fraction →
  per-basin median fraction (across seeds) → cross-basin median + IQR.

Inputs
------
- tables/rq2_q99_events_85basin.csv (B1)
- tables/rq2_noaa_events_expanded_overlap.csv (B2)
- required_series/seed{111,222,444}/primary_required_series.csv

Outputs
-------
- tables/ub_location_class_q99.csv + _summary.csv
- tables/ub_location_class_noaa.csv + _summary.csv
- figures/ub_location_class_bar.png

Acceptance
----------
- Class fractions sum to 1.0 per basin/seed (within float tolerance).
- above_q99 fraction < 0.50 cross-basin median (band useful at all).
- No negative fractions.
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
    filter_valid_rows,
    normalize_basin_id,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/expanded_drbc_test"
DEFAULT_INPUT_DIR = DEFAULT_OUTPUT_DIR / "required_series"

BAND_CLASSES = ("below_q50", "q50_to_q90", "q90_to_q95", "q95_to_q99", "above_q99")
BAND_COLORS = ("#4393c3", "#92c5de", "#fddbc7", "#f4a582", "#d6604d")


def load_seed_at_event_times(
    seed_csv: Path,
    event_keys: pd.DataFrame,
    seed: int,
) -> pd.DataFrame:
    df = pd.read_csv(
        seed_csv,
        usecols=["basin", "datetime", "obs", "q50", "q90", "q95", "q99"],
        dtype={"basin": str},
        parse_dates=["datetime"],
    )
    df["basin_id"] = df["basin"].map(normalize_basin_id)
    df = filter_valid_rows(df, obs_col="obs")
    keys = event_keys[["basin_id", "peak_time"]].drop_duplicates()
    merged = keys.merge(
        df.rename(columns={"datetime": "peak_time"}),
        on=["basin_id", "peak_time"],
        how="left",
    )
    merged["seed"] = seed
    return merged[["basin_id", "seed", "peak_time", "obs", "q50", "q90", "q95", "q99"]]


def classify_obs(r: pd.Series) -> str | None:
    obs = r["obs"]
    if pd.isna(obs) or obs <= 0:
        return None
    q50, q90, q95, q99 = float(r["q50"]), float(r["q90"]), float(r["q95"]), float(r["q99"])
    if any(np.isnan(x) for x in (q50, q90, q95, q99)):
        return None
    if obs <= q50:
        return "below_q50"
    if obs <= q90:
        return "q50_to_q90"
    if obs <= q95:
        return "q90_to_q95"
    if obs <= q99:
        return "q95_to_q99"
    return "above_q99"


def compute_location_classes(merged: pd.DataFrame) -> pd.DataFrame:
    records = []
    for _, r in merged.iterrows():
        cls = classify_obs(r)
        if cls is None:
            continue
        records.append(
            {
                "basin_id": r["basin_id"],
                "seed": r["seed"],
                "peak_time": r["peak_time"],
                "obs_class": cls,
            }
        )
    return pd.DataFrame(records)


def summarize_location(loc: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    basin_seed_n = loc.groupby(["basin_id", "seed"]).size().rename("n_events")
    basin_seed_class = loc.groupby(["basin_id", "seed", "obs_class"]).size().rename("n")
    fracs = (basin_seed_class / basin_seed_n).rename("fraction").reset_index()

    wide = fracs.pivot_table(
        index=["basin_id", "seed"], columns="obs_class", values="fraction", fill_value=0.0
    ).reset_index()
    for cls in BAND_CLASSES:
        if cls not in wide.columns:
            wide[cls] = 0.0

    by_basin = wide.groupby("basin_id")[list(BAND_CLASSES)].median().reset_index()

    rows = []
    for cls in BAND_CLASSES:
        s = by_basin[cls]
        rows.append(
            {
                "obs_class": cls,
                "basin_median": s.median(),
                "basin_iqr_low": s.quantile(0.25),
                "basin_iqr_high": s.quantile(0.75),
                "n_basins": len(s),
            }
        )
    return pd.DataFrame(rows), by_basin


def summarize_location_pooled(loc: pd.DataFrame) -> pd.DataFrame:
    """Event-pooled fraction: pool all (event, seed) rows, count per class.

    Each event is counted once per seed (3x total), preserving the sum=1
    property that componentwise median breaks.  Interpretation: 'of all
    (event, seed) evaluations, X% land in class C.'
    """
    total = len(loc)
    rows = []
    for cls in BAND_CLASSES:
        n = int((loc["obs_class"] == cls).sum())
        rows.append(
            {
                "obs_class": cls,
                "pooled_fraction": n / total if total > 0 else 0.0,
                "n_event_seed_pairs": n,
            }
        )
    return pd.DataFrame(rows)


def plot_location_bar(
    q99_pooled: pd.DataFrame,
    noaa_pooled: pd.DataFrame,
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, pooled, title in zip(
        axes,
        [q99_pooled, noaa_pooled],
        ["Q99 scope (85 basin, 926 events)", "NOAA confirmed flood (21 basin, 65 events)"],
    ):
        fracs = [
            float(pooled.set_index("obs_class").loc[c, "pooled_fraction"])
            for c in BAND_CLASSES
        ]
        bars = ax.bar(BAND_CLASSES, fracs, color=BAND_COLORS, edgecolor="0.3", linewidth=0.6)
        ax.set_ylim(0, 1.0)
        ax.set_ylabel("Event-pooled fraction (sums to 1.0)")
        ax.set_title(title)
        ax.set_xticks(range(len(BAND_CLASSES)))
        ax.set_xticklabels(BAND_CLASSES, rotation=30, ha="right", fontsize=8)
        for bar, val in zip(bars, fracs):
            if val > 0.01:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.015,
                    f"{val:.2f}",
                    ha="center",
                    fontsize=8,
                )
        ax.grid(axis="y", alpha=0.3)
        total = sum(fracs)
        ax.text(0.98, 0.97, f"sum={total:.3f}", transform=ax.transAxes,
                ha="right", va="top", fontsize=7, color="0.5")
    fig.suptitle(
        "Obs location within q50–q99 uncertainty band at event peaks (event-pooled)\n"
        "(above_q99 = band failed; below_q50 = overestimation; band = q50 to q99)",
        fontsize=10,
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def run_scope(
    scope_name: str,
    events: pd.DataFrame,
    seed_csvs: dict[int, Path],
    output_dir: Path,
) -> pd.DataFrame:
    print(
        f"[UB-LOC] scope={scope_name}: n_events={len(events)} n_basins={events['basin_id'].nunique()}",
        flush=True,
    )
    parts: list[pd.DataFrame] = []
    for seed, csv_path in seed_csvs.items():
        merged = load_seed_at_event_times(csv_path, events, seed)
        loc = compute_location_classes(merged)
        parts.append(loc)
        print(f"[UB-LOC] {scope_name} seed={seed} classified={len(loc)}", flush=True)

    all_loc = pd.concat(parts, ignore_index=True)
    tables_dir = output_dir / "tables"

    out_path = tables_dir / f"ub_location_class_{scope_name}.csv"
    with out_path.open("w") as f:
        f.write(f"# Uncertainty Band obs location class (scope={scope_name})\n")
        all_loc.to_csv(f, index=False)
    print(f"[UB-LOC] wrote {out_path} ({len(all_loc)} rows)", flush=True)

    summary, by_basin = summarize_location(all_loc)
    summary_path = tables_dir / f"ub_location_class_{scope_name}_summary.csv"
    with summary_path.open("w") as f:
        f.write(
            f"# UB location class — cross-basin median fraction per class (scope={scope_name})\n"
        )
        summary.to_csv(f, index=False)
    print(f"[UB-LOC] wrote {summary_path}", flush=True)
    print(f"[UB-LOC] {scope_name} summary:\n{summary.to_string(index=False)}", flush=True)

    pooled = summarize_location_pooled(all_loc)
    pooled_path = tables_dir / f"ub_location_class_{scope_name}_pooled.csv"
    with pooled_path.open("w") as f:
        f.write(
            f"# UB location class — event-pooled fraction per class (scope={scope_name})\n"
            f"# Pools all (event, seed) pairs; sums to 1.0. Use for bar chart.\n"
        )
        pooled.to_csv(f, index=False)
    print(f"[UB-LOC] wrote {pooled_path}", flush=True)
    print(f"[UB-LOC] {scope_name} pooled:\n{pooled.to_string(index=False)}", flush=True)

    above_q99_pooled = float(pooled.set_index("obs_class").loc["above_q99", "pooled_fraction"])
    print(
        f"[UB-LOC] {scope_name} above_q99 event-pooled={above_q99_pooled:.3f}",
        flush=True,
    )

    return pooled


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(SEEDS))
    args = parser.parse_args()

    tables_dir = args.output_dir / "tables"
    figures_dir = args.output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    q99_events = pd.read_csv(
        tables_dir / "rq2_q99_events_85basin.csv",
        comment="#",
        dtype={"basin_id": str},
        parse_dates=["peak_time"],
    )
    q99_events["basin_id"] = q99_events["basin_id"].map(normalize_basin_id)

    noaa_events = pd.read_csv(
        tables_dir / "rq2_noaa_events_expanded_overlap.csv",
        dtype={"basin_id": str},
        parse_dates=["peak_time"],
    )
    noaa_events["basin_id"] = noaa_events["basin_id"].map(normalize_basin_id)
    noaa_events = noaa_events[noaa_events["in_expanded_85"]].copy()
    test_start = pd.Timestamp("2014-01-01")
    test_end = pd.Timestamp("2016-12-31 23:00:00")
    noaa_events = noaa_events[
        (noaa_events["peak_time"] >= test_start) & (noaa_events["peak_time"] <= test_end)
    ].copy()

    seed_csvs = {
        s: args.input_dir / f"seed{s}" / "primary_required_series.csv" for s in args.seeds
    }

    q99_summary = run_scope("q99", q99_events, seed_csvs, args.output_dir)
    noaa_summary = run_scope("noaa", noaa_events, seed_csvs, args.output_dir)

    fig_path = figures_dir / "ub_location_class_bar.png"
    plot_location_bar(q99_summary, noaa_summary, fig_path)
    print(f"[UB-LOC] wrote {fig_path}", flush=True)


if __name__ == "__main__":
    main()
