#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=2.0",
#   "pandas>=2.2",
# ]
# ///
"""Uncertainty Band — gap trajectory across quantile levels at event peaks.

For each event peak and τ ∈ (q50, q90, q95, q99):
  under_gap     = max(obs − q_τ, 0)       [residual underestimation]
  over_gap      = max(q_τ − obs, 0)       [residual overestimation]
  rel_under_gap = under_gap / obs          [relative; obs > 0]
  rel_over_gap  = over_gap / obs           [relative; obs > 0]

τ ↑ → under_gap ↓ + over_gap ↑ tradeoff supports the band framing:
q99 is the upper safety envelope, not a single "correct" prediction.
This analysis provides the gap-trajectory evidence for that claim.

Dual scope: Q99 (85 basin) and NOAA confirmed flood (21 basin / 65 events).

Aggregation: per-event per-τ → per-basin-seed median (across events) →
  per-basin median (across seeds) → cross-basin median + IQR.

Inputs
------
- tables/rq2_q99_events_85basin.csv (B1)
- tables/rq2_noaa_events_expanded_overlap.csv (B2)
- required_series/seed{111,222,444}/primary_required_series.csv

Outputs
-------
- tables/ub_gap_trajectory_q99.csv + _summary.csv
- tables/ub_gap_trajectory_noaa.csv + _summary.csv
- figures/ub_gap_trajectory.png

Acceptance
----------
- All gap values >= 0.
- Cross-basin median under_gap non-increasing q50→q99.
- Cross-basin median over_gap non-decreasing q50→q99.
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

QUANTILE_TAU_ORDER = ("q50", "q90", "q95", "q99")
TAU_LABELS = {"q50": "q50", "q90": "q90", "q95": "q95", "q99": "q99"}


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


def compute_gaps(merged: pd.DataFrame) -> pd.DataFrame:
    records = []
    for _, r in merged.iterrows():
        obs = r["obs"]
        if pd.isna(obs) or obs <= 0:
            continue
        obs = float(obs)
        for tau in QUANTILE_TAU_ORDER:
            pred = r[tau]
            if pd.isna(pred):
                continue
            pred = float(pred)
            under_gap = max(0.0, obs - pred)
            over_gap = max(0.0, pred - obs)
            records.append(
                {
                    "basin_id": r["basin_id"],
                    "seed": r["seed"],
                    "peak_time": r["peak_time"],
                    "tau": tau,
                    "under_gap": under_gap,
                    "over_gap": over_gap,
                    "rel_under_gap": under_gap / obs,
                    "rel_over_gap": over_gap / obs,
                }
            )
    return pd.DataFrame(records)


def summarize_gaps(gaps: pd.DataFrame) -> pd.DataFrame:
    # per-basin per-seed per-τ: median across events
    by_bst = (
        gaps.groupby(["basin_id", "seed", "tau"])[
            ["under_gap", "over_gap", "rel_under_gap", "rel_over_gap"]
        ]
        .median()
        .reset_index()
    )
    # per-basin per-τ: median across seeds
    by_basin = (
        by_bst.groupby(["basin_id", "tau"])[
            ["under_gap", "over_gap", "rel_under_gap", "rel_over_gap"]
        ]
        .median()
        .reset_index()
    )
    # cross-basin per-τ: median + IQR
    rows = []
    for tau in QUANTILE_TAU_ORDER:
        sub = by_basin[by_basin["tau"] == tau]
        for col in ("under_gap", "over_gap", "rel_under_gap", "rel_over_gap"):
            rows.append(
                {
                    "tau": tau,
                    "metric": col,
                    "basin_median": sub[col].median(),
                    "basin_iqr_low": sub[col].quantile(0.25),
                    "basin_iqr_high": sub[col].quantile(0.75),
                    "n_basins": len(sub),
                }
            )
    return pd.DataFrame(rows), by_basin


def check_monotonicity(summary: pd.DataFrame) -> None:
    tau_idx = {t: i for i, t in enumerate(QUANTILE_TAU_ORDER)}
    for metric, direction in (
        ("under_gap", "non-increasing"),
        ("over_gap", "non-decreasing"),
    ):
        sub = (
            summary[summary["metric"] == metric]
            .sort_values("tau", key=lambda s: s.map(tau_idx))
        )
        vals = sub["basin_median"].values
        if direction == "non-increasing":
            ok = all(vals[i] >= vals[i + 1] - 1e-9 for i in range(len(vals) - 1))
        else:
            ok = all(vals[i] <= vals[i + 1] + 1e-9 for i in range(len(vals) - 1))
        status = "PASS" if ok else "WARN"
        print(
            f"[UB-GAP] cross-basin median {metric} {direction}: {status} "
            f"{dict(zip(QUANTILE_TAU_ORDER, vals.round(4)))}",
            flush=True,
        )


def plot_gap_trajectory(
    q99_summary: pd.DataFrame,
    noaa_summary: pd.DataFrame,
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    tau_x = list(range(len(QUANTILE_TAU_ORDER)))
    tau_idx = {t: i for i, t in enumerate(QUANTILE_TAU_ORDER)}

    for ax, summary, title in zip(
        axes,
        [q99_summary, noaa_summary],
        ["Q99 scope (85 basin)", "NOAA confirmed flood (21 basin)"],
    ):
        for metric, color, label, ls in (
            ("rel_under_gap", "#d6604d", "Relative under-gap  max(obs−qτ,0)/obs", "-"),
            ("rel_over_gap", "#4393c3", "Relative over-gap  max(qτ−obs,0)/obs", "--"),
        ):
            sub = summary[summary["metric"] == metric].sort_values(
                "tau", key=lambda s: s.map(tau_idx)
            )
            ax.plot(tau_x, sub["basin_median"].values, marker="o", color=color, label=label, ls=ls)
            ax.fill_between(
                tau_x,
                sub["basin_iqr_low"].values,
                sub["basin_iqr_high"].values,
                alpha=0.15,
                color=color,
            )
        ax.set_xticks(tau_x)
        ax.set_xticklabels(QUANTILE_TAU_ORDER)
        ax.set_xlabel("τ")
        ax.set_ylabel("Relative gap (cross-basin median)")
        ax.set_title(title)
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
        ax.axhline(0, color="0.5", linewidth=0.8, linestyle=":")

    fig.suptitle(
        "Uncertainty Band gap trajectory: τ ↑ → under-gap ↓, over-gap ↑\n"
        "(q99 = upper envelope, not single correct prediction)",
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
        f"[UB-GAP] scope={scope_name}: n_events={len(events)} n_basins={events['basin_id'].nunique()}",
        flush=True,
    )
    parts: list[pd.DataFrame] = []
    for seed, csv_path in seed_csvs.items():
        merged = load_seed_at_event_times(csv_path, events, seed)
        gaps = compute_gaps(merged)
        parts.append(gaps)
        print(f"[UB-GAP] {scope_name} seed={seed} rows={len(gaps)}", flush=True)

    all_gaps = pd.concat(parts, ignore_index=True)
    tables_dir = output_dir / "tables"

    out_path = tables_dir / f"ub_gap_trajectory_{scope_name}.csv"
    with out_path.open("w") as f:
        f.write(f"# Uncertainty Band gap trajectory per event per τ (scope={scope_name})\n")
        all_gaps.to_csv(f, index=False)
    print(f"[UB-GAP] wrote {out_path} ({len(all_gaps)} rows)", flush=True)

    summary, _ = summarize_gaps(all_gaps)
    summary_path = tables_dir / f"ub_gap_trajectory_{scope_name}_summary.csv"
    with summary_path.open("w") as f:
        f.write(
            f"# UB gap trajectory summary — cross-basin median per τ (scope={scope_name})\n"
        )
        summary.to_csv(f, index=False)
    print(f"[UB-GAP] wrote {summary_path}", flush=True)

    check_monotonicity(summary)
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

    fig_path = figures_dir / "ub_gap_trajectory.png"
    plot_gap_trajectory(q99_summary, noaa_summary, fig_path)
    print(f"[UB-GAP] wrote {fig_path}", flush=True)


if __name__ == "__main__":
    main()
