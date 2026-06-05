#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=2.0",
#   "pandas>=2.2",
# ]
# ///
"""B4 — RQ-2 β ±6h window peak capture (Q99 + NOAA dual scope).

For each event window [peak − 6h, peak + 6h], compute
window_capture_τ = max(q_τ in window) / max(obs in window).
Events with max(obs in window) ≤ 0 are dropped (regulated/zero-obs).

Aggregation order (C0): per-basin per-seed event median → seed-median within basin
→ cross-basin median + IQR.

Inputs / Outputs / Acceptance mirror B3 with the β metric.
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
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/primary/metrics"
DEFAULT_INPUT_DIR = DEFAULT_OUTPUT_DIR / "required_series"

CAPTURE_FLAG_THRESHOLD = 2.0  # flag if max(q_τ)/max(obs) > this


def compute_window_capture(
    df_seed: pd.DataFrame,
    events: pd.DataFrame,
    seed: int,
) -> tuple[pd.DataFrame, int]:
    """For each event window, compute max(q_τ) / max(obs) per τ.

    Returns (long-form DataFrame, n_dropped_zero_obs).
    """
    df_indexed = df_seed.set_index(["basin_id", "datetime"]).sort_index()
    rows = []
    dropped = 0
    for _, ev in events.iterrows():
        basin = ev["basin_id"]
        start = ev["window_start"]
        end = ev["window_end"]
        try:
            sub = df_indexed.loc[basin].loc[start:end]
        except KeyError:
            continue
        if sub.empty:
            continue
        obs_max = sub["obs"].max(skipna=True)
        if pd.isna(obs_max) or obs_max <= 0:
            dropped += 1
            continue
        for tau in TAU_ORDER:
            pred_max = sub[tau].max(skipna=True)
            if pd.isna(pred_max):
                continue
            ratio = float(pred_max) / float(obs_max)
            rows.append({
                "basin_id": basin,
                "seed": seed,
                "peak_time": ev["peak_time"],
                "tau": tau,
                "window_capture": ratio,
                "flagged_gt_2x": ratio > CAPTURE_FLAG_THRESHOLD,
            })
    return pd.DataFrame(rows), dropped


def summarize_beta(beta: pd.DataFrame) -> pd.DataFrame:
    by_basin_seed = beta.groupby(["basin_id", "seed", "tau"])["window_capture"].median().reset_index(name="event_median")
    by_basin = by_basin_seed.groupby(["basin_id", "tau"])["event_median"].median().reset_index(name="basin_event_median")
    summary = (
        by_basin.groupby("tau")["basin_event_median"]
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


def load_seed_required_series(seed_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(
        seed_csv,
        usecols=["basin", "datetime", "obs", "model1", "q50", "q90", "q95", "q99"],
        dtype={"basin": str},
        parse_dates=["datetime"],
    )
    df["basin_id"] = df["basin"].map(normalize_basin_id)
    df = filter_valid_rows(df, obs_col="obs")
    return df


def run_scope(scope_name: str, events: pd.DataFrame, seed_csvs: dict[int, Path], output_dir: Path) -> tuple[pd.DataFrame, int]:
    print(f"[B4] scope={scope_name}: n_events={len(events)} n_basins={events.basin_id.nunique()}", flush=True)
    parts: list[pd.DataFrame] = []
    total_dropped = 0
    for seed, seed_csv in seed_csvs.items():
        df_seed = load_seed_required_series(seed_csv)
        part, dropped = compute_window_capture(df_seed, events, seed)
        parts.append(part)
        total_dropped += dropped
        print(f"[B4] {scope_name} seed={seed} rows={len(part)} dropped_zero_obs={dropped}", flush=True)
        del df_seed
    beta = pd.concat(parts, ignore_index=True)
    out_path = output_dir / "tables" / f"rq2_beta_window_capture_{scope_name}.csv"
    with out_path.open("w") as f:
        f.write(f"# RQ-2 β — ±6h window peak capture (scope={scope_name}); dropped zero-obs events: {total_dropped}\n")
        beta.to_csv(f, index=False)
    print(f"[B4] wrote {out_path} ({len(beta)} rows; dropped {total_dropped})", flush=True)

    summary = summarize_beta(beta)
    summary_path = output_dir / "tables" / f"rq2_beta_window_capture_{scope_name}_summary.csv"
    with summary_path.open("w") as f:
        f.write(f"# RQ-2 β summary — cross-basin median + IQR per τ (scope={scope_name})\n")
        summary.to_csv(f, index=False)
    print(f"[B4] wrote {summary_path}", flush=True)
    return summary, total_dropped


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
        tables_dir / "rq2_noaa_events_overlap.csv",
        dtype={"basin_id": str},
        parse_dates=["peak_time", "window_start", "window_end"],
    )
    noaa_events["basin_id"] = noaa_events["basin_id"].map(normalize_basin_id)
    noaa_events = noaa_events[noaa_events["in_expanded_85"]].copy()
    test_start = pd.Timestamp("2014-01-01")
    test_end = pd.Timestamp("2016-12-31 23:00:00")
    noaa_events = noaa_events[
        (noaa_events["peak_time"] >= test_start) & (noaa_events["peak_time"] <= test_end)
    ].copy()

    seed_csvs = {seed: args.input_dir / f"seed{seed}" / "required_series.csv" for seed in args.seeds}

    q99_summary, q99_dropped = run_scope("q99", q99_events, seed_csvs, args.output_dir)
    noaa_summary, noaa_dropped = run_scope("noaa", noaa_events, seed_csvs, args.output_dir)

    # Figure
    fig, ax = plt.subplots(figsize=(7, 4))
    for scope, summary, color in (("Q99 (85 basin)", q99_summary, "C0"), ("NOAA (overlap)", noaa_summary, "C1")):
        ordered = summary.set_index("tau").reindex(TAU_ORDER)
        ax.plot(range(len(TAU_ORDER)), ordered["basin_median"], marker="o", label=scope, color=color)
        ax.fill_between(range(len(TAU_ORDER)), ordered["basin_iqr_low"], ordered["basin_iqr_high"], alpha=0.18, color=color)
    ax.axhline(1.0, color="gray", linestyle=":", linewidth=0.8)
    ax.set_xticks(range(len(TAU_ORDER)))
    ax.set_xticklabels(TAU_ORDER)
    ax.set_xlabel("τ")
    ax.set_ylabel("Window peak capture (cross-basin median)")
    ax.set_title("RQ-2 β — ±6h window peak capture by τ")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig_path = figures_dir / "rq2_beta_by_tau.png"
    fig.savefig(fig_path, dpi=140)
    plt.close(fig)
    print(f"[B4] wrote {fig_path}", flush=True)


if __name__ == "__main__":
    main()
