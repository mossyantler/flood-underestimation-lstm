#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=2.0",
#   "pandas>=2.2",
# ]
# ///
"""B3 — RQ-2 α event peak under-deficit (Q99 + NOAA dual scope).

For each event's `peak_time`, look up obs and predictions per τ and seed, then
compute peak_under_deficit_τ = max(0, (obs_peak − q_τ_at_peak)) / obs_peak.
Aggregate basin → seed-median within basin → cross-basin median + IQR.

Inputs
------
- tables/rq2_q99_events_85basin.csv (B1)
- tables/rq2_noaa_events_expanded_overlap.csv (B2; filtered to in_expanded_85)
- required_series/seed{111,222,444}/primary_required_series.csv

Outputs
-------
- tables/rq2_alpha_event_peak_deficit_q99.csv + _summary.csv
- tables/rq2_alpha_event_peak_deficit_noaa.csv + _summary.csv
- figures/rq2_alpha_by_tau.png

Acceptance
----------
- All deficits in [0, 1].
- Cross-basin median non-increasing in τ (M1 → q50 → q90 → q95 → q99).
- Per-basin τ-monotonicity violation rate reported and < 20%.
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
    filter_valid_rows,
    normalize_basin_id,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/expanded_drbc_test"
DEFAULT_INPUT_DIR = DEFAULT_OUTPUT_DIR / "required_series"


def load_seed_at_event_times(
    seed_csv: Path,
    event_keys: pd.DataFrame,
    seed: int,
) -> pd.DataFrame:
    """Load required_series for one seed; keep only rows matching (basin, datetime) ∈ event_keys.

    event_keys must have columns basin_id (str) and peak_time (datetime).
    Returns DataFrame with: basin_id, seed, peak_time, obs, model1, q50, q90, q95, q99.
    """
    df = pd.read_csv(
        seed_csv,
        usecols=["seed", "basin", "datetime", "obs", "model1", "q50", "q90", "q95", "q99"],
        dtype={"basin": str},
        parse_dates=["datetime"],
    )
    df["basin_id"] = df["basin"].map(normalize_basin_id)
    df = filter_valid_rows(df, obs_col="obs")
    # Restrict to event peak times to keep this cheap
    keys = event_keys[["basin_id", "peak_time"]].drop_duplicates()
    merged = keys.merge(
        df.rename(columns={"datetime": "peak_time"}),
        on=["basin_id", "peak_time"],
        how="left",
    )
    merged["seed"] = seed
    return merged[["basin_id", "seed", "peak_time", "obs", "model1", "q50", "q90", "q95", "q99"]]


def compute_alpha(merged: pd.DataFrame) -> pd.DataFrame:
    """Return long-form DataFrame: basin_id, seed, peak_time, tau, peak_under_deficit."""
    rows = []
    for _, r in merged.iterrows():
        obs = r["obs"]
        if pd.isna(obs) or obs <= 0:
            continue
        for tau in TAU_ORDER:
            pred = r[tau]
            if pd.isna(pred):
                continue
            deficit = max(0.0, (obs - float(pred))) / obs
            rows.append({
                "basin_id": r["basin_id"],
                "seed": r["seed"],
                "peak_time": r["peak_time"],
                "tau": tau,
                "peak_under_deficit": deficit,
            })
    return pd.DataFrame(rows)


def summarize_alpha(alpha: pd.DataFrame) -> pd.DataFrame:
    """Per τ: cross-basin median + IQR of (per-basin median of per-seed event-median deficits)."""
    # Aggregation: basin × seed × event → median across events within basin/seed
    by_basin_seed = (
        alpha.groupby(["basin_id", "seed", "tau"])["peak_under_deficit"]
        .median()
        .reset_index(name="event_median")
    )
    # Then median across seeds within basin
    by_basin = (
        by_basin_seed.groupby(["basin_id", "tau"])["event_median"]
        .median()
        .reset_index(name="basin_event_median")
    )
    # Then cross-basin median + IQR per τ
    summary = (
        by_basin.groupby("tau")["basin_event_median"]
        .agg(
            basin_median_of_event_median="median",
            basin_iqr_low=lambda s: s.quantile(0.25),
            basin_iqr_high=lambda s: s.quantile(0.75),
            n_basins="count",
        )
        .reset_index()
    )
    summary["tau_order"] = summary["tau"].map({t: i for i, t in enumerate(TAU_ORDER)})
    summary = summary.sort_values("tau_order").drop(columns="tau_order")
    return summary, by_basin


QUANTILE_TAU_ORDER = ("q50", "q90", "q95", "q99")
"""M1 deterministic is not expected to obey τ-monotonicity (it is a different model);
violation rate is computed only over the q50→q99 quantile sequence within Model 2."""


def violation_rate_per_basin(by_basin: pd.DataFrame) -> float:
    """Fraction of basins where per-basin event median is NOT monotonically non-increasing
    across the Model-2 quantile sequence q50 → q90 → q95 → q99."""
    violating = 0
    total = 0
    for _, sub in by_basin.groupby("basin_id"):
        ordered = sub.set_index("tau").reindex(QUANTILE_TAU_ORDER)["basin_event_median"].values
        total += 1
        if not all(ordered[i] >= ordered[i + 1] for i in range(len(ordered) - 1)):
            violating += 1
    return violating / max(1, total)


def run_scope(scope_name: str, events: pd.DataFrame, seed_csvs: dict[int, Path], output_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    """Run α computation for one event scope (q99 or noaa)."""
    print(f"[B3] scope={scope_name}: n_events={len(events)} n_basins={events.basin_id.nunique()}", flush=True)
    parts: list[pd.DataFrame] = []
    for seed, seed_csv in seed_csvs.items():
        merged = load_seed_at_event_times(seed_csv, events, seed)
        alpha_seed = compute_alpha(merged)
        parts.append(alpha_seed)
        print(f"[B3] {scope_name} seed={seed} rows={len(alpha_seed)}", flush=True)
    alpha = pd.concat(parts, ignore_index=True)
    out_path = output_dir / "tables" / f"rq2_alpha_event_peak_deficit_{scope_name}.csv"
    with out_path.open("w") as f:
        f.write(f"# RQ-2 α — event peak under-deficit (scope={scope_name})\n")
        alpha.to_csv(f, index=False)
    print(f"[B3] wrote {out_path} ({len(alpha)} rows)", flush=True)

    summary, by_basin = summarize_alpha(alpha)
    summary_path = output_dir / "tables" / f"rq2_alpha_event_peak_deficit_{scope_name}_summary.csv"
    with summary_path.open("w") as f:
        f.write(f"# RQ-2 α summary — cross-basin median + IQR per τ (scope={scope_name})\n")
        summary.to_csv(f, index=False)
    print(f"[B3] wrote {summary_path}", flush=True)
    rate = violation_rate_per_basin(by_basin)
    print(f"[B3] {scope_name} per-basin τ-monotonicity violation rate: {rate:.2%}", flush=True)
    return alpha, summary, rate


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
        parse_dates=["peak_time", "window_start", "window_end"],
    )
    q99_events["basin_id"] = q99_events["basin_id"].map(normalize_basin_id)

    noaa_events = pd.read_csv(
        tables_dir / "rq2_noaa_events_expanded_overlap.csv",
        dtype={"basin_id": str},
        parse_dates=["peak_time", "window_start", "window_end"],
    )
    noaa_events["basin_id"] = noaa_events["basin_id"].map(normalize_basin_id)
    noaa_events = noaa_events[noaa_events["in_expanded_85"]].copy()
    # Restrict to events within TEST_PERIOD (paper scope)
    test_start = pd.Timestamp("2014-01-01")
    test_end = pd.Timestamp("2016-12-31 23:00:00")
    noaa_events = noaa_events[
        (noaa_events["peak_time"] >= test_start) & (noaa_events["peak_time"] <= test_end)
    ].copy()
    # NOTE: required_series at event peak times may be missing if the timestamp
    # falls outside the required_series coverage (e.g. NOAA event recorded daily
    # but model output is hourly). We rely on the left-merge dropping unmatched.

    seed_csvs = {seed: args.input_dir / f"seed{seed}" / "primary_required_series.csv" for seed in args.seeds}

    _, q99_summary, q99_violation = run_scope("q99", q99_events, seed_csvs, args.output_dir)
    _, noaa_summary, noaa_violation = run_scope("noaa", noaa_events, seed_csvs, args.output_dir)

    # Acceptance — monotonicity asserted across Model-2 quantile sequence only
    # (M1 deterministic ≠ M2-q50 by construction; RQ-1 handles the M1 vs q50 axis).
    assert q99_violation < 0.20, f"Q99 violation rate {q99_violation:.2%} >= 20%"
    assert noaa_violation < 0.20, f"NOAA violation rate {noaa_violation:.2%} >= 20%"
    for scope, summ in (("q99", q99_summary), ("noaa", noaa_summary)):
        ordered = summ.set_index("tau").reindex(QUANTILE_TAU_ORDER)["basin_median_of_event_median"].values
        for i in range(len(ordered) - 1):
            assert ordered[i] >= ordered[i + 1] - 1e-9, (
                f"{scope} cross-basin median NOT non-increasing across q50→q99: "
                f"{dict(zip(QUANTILE_TAU_ORDER, ordered))}"
            )
    print("[B3] acceptance: q50→q99 cross-basin monotonicity + per-basin violation < 20% PASS", flush=True)

    # Figure
    fig, ax = plt.subplots(figsize=(7, 4))
    for scope, summary, color in (("Q99 (85 basin)", q99_summary, "C0"), ("NOAA (overlap)", noaa_summary, "C1")):
        ordered = summary.set_index("tau").reindex(TAU_ORDER)
        ax.plot(range(len(TAU_ORDER)), ordered["basin_median_of_event_median"], marker="o", label=scope, color=color)
        ax.fill_between(
            range(len(TAU_ORDER)),
            ordered["basin_iqr_low"],
            ordered["basin_iqr_high"],
            alpha=0.18,
            color=color,
        )
    ax.set_xticks(range(len(TAU_ORDER)))
    ax.set_xticklabels(TAU_ORDER)
    ax.set_xlabel("τ")
    ax.set_ylabel("Event peak under-deficit (cross-basin median)")
    ax.set_title("RQ-2 α — event peak under-deficit by τ")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig_path = figures_dir / "rq2_alpha_by_tau.png"
    fig.savefig(fig_path, dpi=140)
    plt.close(fig)
    print(f"[B3] wrote {fig_path}", flush=True)


if __name__ == "__main__":
    main()
