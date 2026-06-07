#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "scipy>=1.13",
# ]
# ///
"""Uncertainty Band — band-shape prospective metrics at Q99/NOAA event peaks.

Computes two obs-free band-shape signals at each event peak:

  rel_width = (q99 - q50) / q50
      Overall relative band spread — how uncertain is the model?

  g3_ratio  = (q99 - q95) / (q99 - q50)
      Extreme-tail weight — what fraction of band uncertainty sits at the top?

These signals are computable without observed flow and are intended as
prospective risk indicators: wide band + high g3_ratio → elevated probability
that obs will exceed q99.

Validation: Spearman r between each signal and above_q99 binary (obs > q99),
pooled across all event × basin × seed rows per scope.  r > 0.3 & p < 0.05
is taken as evidence that the signal has predictive value.

Dual scope: Q99 (85 basin / 926 events) and NOAA confirmed flood (21 basin /
65 events).

Inputs
------
- tables/rq2_q99_events_85basin.csv       (B1)
- tables/rq2_noaa_events_overlap.csv  (B2)
- required_series/seed{111,222,444}/required_series.csv

Outputs
-------
- tables/band_shape_metrics_q99.csv    (event-level, q99 scope)
- tables/band_shape_metrics_noaa.csv   (event-level, noaa scope)
- tables/band_shape_spearman.csv       (r / p_value / n per metric×scope)
- figures/band_shape_scatter.png       (rel_width vs above_q99, 2 panels)

Acceptance
----------
- rel_width > 0 for all rows (q99 > q50 must hold).
- g3_ratio in [0, 1] for all rows.
- Spearman table contains 4 rows (2 metrics × 2 scopes).
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
from scipy.stats import spearmanr

LIB_ROOT = Path(__file__).resolve().parents[2] / "_lib"
if str(LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(LIB_ROOT))

from expanded_drbc import (  # noqa: E402
    SEEDS,
    filter_valid_rows,
    normalize_basin_id,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/band_signal/band_shape"
DEFAULT_INPUT_DIR = REPO_ROOT / "output/model_analysis/primary/metrics/data/required_series"


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


CLASS_ORDINAL = {
    "below_q50": 0,
    "q50_to_q90": 1,
    "q90_to_q95": 2,
    "q95_to_q99": 3,
    "above_q99": 4,
}


def classify_obs(obs: float, q50: float, q90: float, q95: float, q99: float) -> str | None:
    if obs <= q50:
        return "below_q50"
    if obs <= q90:
        return "q50_to_q90"
    if obs <= q95:
        return "q90_to_q95"
    if obs <= q99:
        return "q95_to_q99"
    return "above_q99"


def compute_band_shape(df: pd.DataFrame) -> pd.DataFrame:
    """Add rel_width, g3_ratio, obs_class, obs_class_ordinal; drop invalid rows."""
    out = df.copy()
    q50 = out["q50"].astype(float)
    q99 = out["q99"].astype(float)
    obs = out["obs"].astype(float)

    total_width = q99 - q50
    valid = (q50 > 0) & (total_width > 0) & obs.notna() & obs.gt(0)
    out = out[valid].copy()

    q50_v = out["q50"].astype(float)
    q90_v = out["q90"].astype(float)
    q95_v = out["q95"].astype(float)
    q99_v = out["q99"].astype(float)
    obs_v = out["obs"].astype(float)

    out["rel_width"] = (q99_v - q50_v) / q50_v
    out["g3_ratio"] = (q99_v - q95_v) / (q99_v - q50_v)
    out["obs_class"] = [
        classify_obs(o, q50_, q90_, q95_, q99_)
        for o, q50_, q90_, q95_, q99_ in zip(obs_v, q50_v, q90_v, q95_v, q99_v)
    ]
    out["obs_class_ordinal"] = out["obs_class"].map(CLASS_ORDINAL)
    return out[["basin_id", "seed", "peak_time", "rel_width", "g3_ratio", "obs_class", "obs_class_ordinal"]]


def compute_spearman(metrics_df: pd.DataFrame, scope: str) -> list[dict]:
    rows = []
    for metric in ("rel_width", "g3_ratio"):
        x = metrics_df[metric].values
        y = metrics_df["obs_class_ordinal"].values
        mask = np.isfinite(x) & np.isfinite(y.astype(float))
        n = int(mask.sum())
        if n < 3:
            r, p = float("nan"), float("nan")
        else:
            r, p = spearmanr(x[mask], y[mask])
        rows.append({"scope": scope, "metric": metric, "r": float(r), "p_value": float(p), "n": n})
    return rows


CLASS_COLORS = {
    "below_q50": "#4393c3",
    "q50_to_q90": "#92c5de",
    "q90_to_q95": "#fddbc7",
    "q95_to_q99": "#f4a582",
    "above_q99": "#d6604d",
}
CLASS_ORDER = ["below_q50", "q50_to_q90", "q90_to_q95", "q95_to_q99", "above_q99"]


def plot_scatter(
    q99_df: pd.DataFrame,
    noaa_df: pd.DataFrame,
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    scope_data = [("Q99 scope (85 basin)", q99_df), ("NOAA confirmed flood (21 basin)", noaa_df)]

    rng = np.random.default_rng(42)
    jitter = 0.18

    for ax, (title, df) in zip(axes, scope_data):
        for cls in CLASS_ORDER:
            sub = df[df["obs_class"] == cls]
            if sub.empty:
                continue
            y_base = CLASS_ORDINAL[cls]
            y_jitter = rng.uniform(-jitter, jitter, size=len(sub))
            ax.scatter(
                sub["rel_width"],
                y_base + y_jitter,
                alpha=0.30,
                s=9,
                color=CLASS_COLORS[cls],
                label=cls,
                zorder=2,
            )

        # Annotate Spearman r (vs ordinal)
        x = df["rel_width"].values
        y = df["obs_class_ordinal"].values
        mask = np.isfinite(x)
        if mask.sum() >= 3:
            r, p = spearmanr(x[mask], y[mask])
            ax.text(
                0.97,
                0.97,
                f"Spearman r = {r:.3f}\np = {p:.3f}  n = {int(mask.sum())}",
                transform=ax.transAxes,
                ha="right",
                va="top",
                fontsize=8,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
            )

        ax.set_yticks(list(CLASS_ORDINAL.values()))
        ax.set_yticklabels(list(CLASS_ORDINAL.keys()), fontsize=7.5)
        ax.set_xlabel("rel_width = (q99−q50)/q50", fontsize=9)
        ax.set_title(title, fontsize=9)
        ax.legend(fontsize=7, loc="lower right", markerscale=1.5)
        ax.grid(alpha=0.25, axis="x")

    fig.suptitle(
        "Band relative width vs obs gap class at event peaks\n"
        "(rel_width prospective: computable without obs)",
        fontsize=10,
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


BIN_LABELS = ["low (narrow)", "high (wide)"]
BIN_LABELS_G3 = ["low tail", "high tail"]


def compute_lookup_table(df: pd.DataFrame, scope: str) -> pd.DataFrame:
    """Conditional obs_class distribution per (rel_width_bin, g3_ratio_bin)."""
    work = df.copy()
    work["rw_bin"] = pd.qcut(work["rel_width"], q=2, labels=BIN_LABELS, duplicates="drop")
    work["g3_bin"] = pd.qcut(work["g3_ratio"], q=2, labels=BIN_LABELS_G3, duplicates="drop")

    rows = []
    for dim, bin_col in [("rel_width", "rw_bin"), ("g3_ratio", "g3_bin")]:
        grp = work.groupby([bin_col, "obs_class"], observed=True).size().reset_index(name="n")
        totals = work.groupby(bin_col, observed=True).size().reset_index(name="n_total")
        merged = grp.merge(totals, on=bin_col)
        merged["fraction"] = merged["n"] / merged["n_total"]
        merged["scope"] = scope
        merged["dimension"] = dim
        merged = merged.rename(columns={bin_col: "bin"})
        rows.append(merged[["scope", "dimension", "bin", "obs_class", "fraction", "n", "n_total"]])

    return pd.concat(rows, ignore_index=True)


def plot_lookup(
    q99_df: pd.DataFrame,
    noaa_df: pd.DataFrame,
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(14, 8))
    scope_data = [("Q99 scope", q99_df), ("NOAA confirmed flood", noaa_df)]
    dim_info = [
        ("rel_width", "rw_bin", BIN_LABELS, "rel_width = (q99−q50)/q50"),
        ("g3_ratio", "g3_bin", BIN_LABELS_G3, "g3_ratio = (q99−q95)/(q99−q50)"),
    ]

    for row_idx, (scope_title, df) in enumerate(scope_data):
        work = df.copy()
        work["rw_bin"] = pd.qcut(work["rel_width"], q=2, labels=BIN_LABELS, duplicates="drop")
        work["g3_bin"] = pd.qcut(work["g3_ratio"], q=2, labels=BIN_LABELS_G3, duplicates="drop")

        for col_idx, (dim, bin_col, labels, xlabel) in enumerate(dim_info):
            ax = axes[row_idx][col_idx]
            bottoms = np.zeros(len(labels))
            n_per_bin = work.groupby(bin_col, observed=True).size()

            for cls in CLASS_ORDER:
                fracs = []
                for lbl in labels:
                    sub = work[work[bin_col] == lbl]
                    if len(sub) == 0:
                        fracs.append(0.0)
                    else:
                        fracs.append((sub["obs_class"] == cls).sum() / len(sub))
                fracs = np.array(fracs)
                ax.bar(
                    range(len(labels)),
                    fracs,
                    bottom=bottoms,
                    color=CLASS_COLORS[cls],
                    label=cls,
                    edgecolor="white",
                    linewidth=0.4,
                )
                bottoms += fracs

            # annotate n
            for i, lbl in enumerate(labels):
                n = int(n_per_bin.get(lbl, 0))
                ax.text(i, 1.01, f"n={n}", ha="center", fontsize=7, color="0.4")

            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, fontsize=7.5, rotation=15, ha="right")
            ax.set_ylim(0, 1.12)
            ax.set_ylabel("Fraction of events" if col_idx == 0 else "", fontsize=8)
            ax.set_xlabel(xlabel, fontsize=8)
            ax.set_title(f"{scope_title} | by {dim}", fontsize=8.5)
            ax.grid(axis="y", alpha=0.25)
            if row_idx == 0 and col_idx == 1:
                ax.legend(
                    fontsize=7,
                    loc="upper left",
                    bbox_to_anchor=(1.01, 1),
                    borderaxespad=0,
                )

    fig.suptitle(
        "Obs gap class distribution by band-shape bins\n"
        "(prospective: rel_width + g3_ratio computed without obs)",
        fontsize=10,
        y=1.01,
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
        f"[UB-SHAPE] scope={scope_name}: n_events={len(events)} "
        f"n_basins={events['basin_id'].nunique()}",
        flush=True,
    )
    parts: list[pd.DataFrame] = []
    for seed, csv_path in seed_csvs.items():
        merged = load_seed_at_event_times(csv_path, events, seed)
        shaped = compute_band_shape(merged)
        parts.append(shaped)
        dist = shaped["obs_class"].value_counts().to_dict()
        print(
            f"[UB-SHAPE] {scope_name} seed={seed} rows={len(shaped)} class_dist={dist}",
            flush=True,
        )

    all_df = pd.concat(parts, ignore_index=True)
    tables_dir = output_dir / "tables"

    out_path = tables_dir / f"band_shape_metrics_{scope_name}.csv"
    with out_path.open("w") as f:
        f.write(f"# UB band-shape prospective metrics (scope={scope_name})\n")
        all_df.to_csv(f, index=False)
    print(f"[UB-SHAPE] wrote {out_path} ({len(all_df)} rows)", flush=True)

    # Sanity checks
    bad_width = (all_df["rel_width"] <= 0).sum()
    bad_ratio = ((all_df["g3_ratio"] < 0) | (all_df["g3_ratio"] > 1)).sum()
    if bad_width > 0:
        print(f"[UB-SHAPE] WARNING: {bad_width} rows with rel_width <= 0", flush=True)
    if bad_ratio > 0:
        print(f"[UB-SHAPE] WARNING: {bad_ratio} rows with g3_ratio out of [0,1]", flush=True)

    return all_df


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
        tables_dir / "rq2_noaa_events_overlap.csv",
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
        s: args.input_dir / f"seed{s}" / "required_series.csv" for s in args.seeds
    }

    q99_df = run_scope("q99", q99_events, seed_csvs, args.output_dir)
    noaa_df = run_scope("noaa", noaa_events, seed_csvs, args.output_dir)

    # Spearman r table
    spearman_rows = compute_spearman(q99_df, "q99") + compute_spearman(noaa_df, "noaa")
    spearman_df = pd.DataFrame(spearman_rows)
    sp_path = tables_dir / "band_shape_spearman.csv"
    with sp_path.open("w") as f:
        f.write("# UB band-shape Spearman r: metric vs obs_class_ordinal (per-event pooled)\n")
        spearman_df.to_csv(f, index=False)
    print(f"[UB-SHAPE] wrote {sp_path}", flush=True)
    print(f"[UB-SHAPE] Spearman results:\n{spearman_df.to_string(index=False)}", flush=True)

    # Conditional distribution lookup table
    lookup_q99 = compute_lookup_table(q99_df, "q99")
    lookup_noaa = compute_lookup_table(noaa_df, "noaa")
    lookup_all = pd.concat([lookup_q99, lookup_noaa], ignore_index=True)
    lk_path = tables_dir / "band_shape_lookup.csv"
    with lk_path.open("w") as f:
        f.write("# UB band-shape conditional obs_class distribution per bin (prospective lookup)\n")
        lookup_all.to_csv(f, index=False)
    print(f"[UB-SHAPE] wrote {lk_path} ({len(lookup_all)} rows)", flush=True)

    # Lookup stacked-bar figure
    lk_fig_path = figures_dir / "band_shape_lookup.png"
    plot_lookup(q99_df, noaa_df, lk_fig_path)
    print(f"[UB-SHAPE] wrote {lk_fig_path}", flush=True)

    # Scatter figure
    fig_path = figures_dir / "band_shape_scatter.png"
    plot_scatter(q99_df, noaa_df, fig_path)
    print(f"[UB-SHAPE] wrote {fig_path}", flush=True)


if __name__ == "__main__":
    main()
