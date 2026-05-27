#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=2.0",
#   "pandas>=2.2",
# ]
# ///
"""Uncertainty Band — representative hydrograph fan plots.

Three panels showing q50~q99 prediction fan around Q99 event peaks:
  Panel A: obs lands inside band (q95~q99 class) — band captures obs
  Panel B: obs exceeds q99 (above_q99 class)     — band fails at peak
  Panel C: NOAA confirmed extreme flood            — massive peak, q99 insufficient

Each panel shows:
  - Observed flow (thick black)
  - Model 1 deterministic (dashed gray)
  - q50 line (blue)
  - Shaded bands: q50–q90 (lightest), q90–q95, q95–q99 (orange), above-q99 zone (red)
  - Vertical marker at event peak_time

Output
------
- figures/ub_hydrograph_fan.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

LIB_ROOT = Path(__file__).resolve().parents[2] / "_lib"
if str(LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(LIB_ROOT))

from expanded_drbc import normalize_basin_id, filter_valid_rows  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/expanded_drbc_test"
DEFAULT_INPUT_DIR = DEFAULT_OUTPUT_DIR / "required_series"

WINDOW_HOURS = 48

PANELS = [
    {
        "label": "(a) Band captures obs (q95–q99)",
        "basin_id": "01472000",
        "peak_time": "2016-02-04 22:00:00",
        "obs_class": "q95_to_q99",
        "scope": "Q99 event",
    },
    {
        "label": "(b) Band fails — obs > q99",
        "basin_id": "01446775",
        "peak_time": "2016-02-25 07:00:00",
        "obs_class": "above_q99",
        "scope": "Q99 event",
    },
    {
        "label": "(c) NOAA confirmed flood (extreme)",
        "basin_id": "01473500",
        "peak_time": "2014-05-01 06:00:00",
        "obs_class": "above_q99",
        "scope": "NOAA Flood",
    },
]

BAND_COLORS = {
    "q50_to_q90": "#c6dbef",
    "q90_to_q95": "#9ecae1",
    "q95_to_q99": "#fdae6b",
    "above_q99":  "#fee0d2",
}


def load_basin_window(seed_csv: Path, basin_id: str, peak_time: pd.Timestamp) -> pd.DataFrame:
    df = pd.read_csv(
        seed_csv,
        usecols=["basin", "datetime", "obs", "model1", "q50", "q90", "q95", "q99"],
        dtype={"basin": str},
        parse_dates=["datetime"],
    )
    df["basin_id"] = df["basin"].map(normalize_basin_id)
    df = df[df["basin_id"] == basin_id].copy()
    t_start = peak_time - pd.Timedelta(hours=WINDOW_HOURS)
    t_end = peak_time + pd.Timedelta(hours=WINDOW_HOURS)
    df = df[(df["datetime"] >= t_start) & (df["datetime"] <= t_end)].copy()
    df = df.sort_values("datetime").reset_index(drop=True)
    return df


def plot_fan_panel(ax: plt.Axes, df: pd.DataFrame, peak_time: pd.Timestamp, panel: dict) -> None:
    t = df["datetime"]

    # Shaded bands
    ax.fill_between(t, df["q50"], df["q90"], alpha=0.55, color=BAND_COLORS["q50_to_q90"], label="q50–q90")
    ax.fill_between(t, df["q90"], df["q95"], alpha=0.55, color=BAND_COLORS["q90_to_q95"], label="q90–q95")
    ax.fill_between(t, df["q95"], df["q99"], alpha=0.55, color=BAND_COLORS["q95_to_q99"], label="q95–q99")

    # Shade above-q99 region (fixed height: max obs or max q99 + 20%)
    y_top = max(df["obs"].max(), df["q99"].max()) * 1.25
    ax.fill_between(t, df["q99"], y_top, alpha=0.20, color=BAND_COLORS["above_q99"], label="above q99 zone")

    # q50 line
    ax.plot(t, df["q50"], color="#2166ac", linewidth=1.0, linestyle="-", label="q50", zorder=3)

    # q99 boundary line
    ax.plot(t, df["q99"], color="#d94801", linewidth=0.8, linestyle="--", label="q99", zorder=3)

    # Model 1
    ax.plot(t, df["model1"], color="0.55", linewidth=1.0, linestyle=":", label="Model 1", zorder=4)

    # Observed (on top)
    ax.plot(t, df["obs"], color="black", linewidth=1.8, label="Observed", zorder=5)

    # Peak marker
    ax.axvline(peak_time, color="0.3", linewidth=0.9, linestyle="--", alpha=0.7)

    # Obs class annotation at peak
    obs_at_peak = df.loc[df["datetime"] == peak_time, "obs"]
    if not obs_at_peak.empty:
        ax.annotate(
            f"peak\n{obs_at_peak.iloc[0]:.0f} m³/s",
            xy=(peak_time, obs_at_peak.iloc[0]),
            xytext=(10, 8),
            textcoords="offset points",
            fontsize=7.5,
            color="black",
        )

    ax.set_title(f"{panel['label']}\nbasin {panel['basin_id']} · {panel['scope']}", fontsize=9)
    ax.set_ylabel("Streamflow (m³/s)", fontsize=8)
    ax.set_xlim(t.iloc[0], t.iloc[-1])
    ax.set_ylim(bottom=0)
    ax.tick_params(axis="x", labelsize=7, rotation=20)
    ax.tick_params(axis="y", labelsize=7)
    ax.grid(alpha=0.25)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--seed", type=int, default=111)
    args = parser.parse_args()

    seed_csv = args.input_dir / f"seed{args.seed}" / "primary_required_series.csv"
    figures_dir = args.output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))

    for ax, panel in zip(axes, PANELS):
        basin_id = normalize_basin_id(panel["basin_id"])
        peak_time = pd.Timestamp(panel["peak_time"])
        df = load_basin_window(seed_csv, basin_id, peak_time)
        if df.empty:
            print(f"[UB-FAN] WARNING: no data for basin {basin_id} around {peak_time}", flush=True)
            ax.set_title(f"No data — {panel['label']}")
            continue
        print(
            f"[UB-FAN] panel {panel['label'][:3]}: basin={basin_id} rows={len(df)} "
            f"peak_obs={df.loc[df['datetime']==peak_time, 'obs'].values}",
            flush=True,
        )
        plot_fan_panel(ax, df, peak_time, panel)

    # Shared legend from last axis
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="lower center",
        ncol=7,
        fontsize=8,
        bbox_to_anchor=(0.5, -0.04),
        framealpha=0.9,
    )
    fig.suptitle(
        "q50–q99 uncertainty band at Q99/NOAA event peaks  "
        "(obs inside band = band useful; obs > q99 = band insufficient at peak)",
        fontsize=10,
        y=1.01,
    )
    fig.tight_layout()

    out_path = figures_dir / "ub_hydrograph_fan.png"
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"[UB-FAN] wrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
