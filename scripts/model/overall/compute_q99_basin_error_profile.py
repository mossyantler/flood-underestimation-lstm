#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "xarray>=2024",
#   "netCDF4>=1.7",
# ]
# ///
"""Compute per-basin Q99 event error metrics and join with basin attributes.

Sources
-------
required_series  : q99 prediction timeseries per block (seed111/222/444)
q99_inference_blocks : block metadata (block_start/end per basin)
NC forcing files  : Rainf, CAPE, Tair for event characteristic computation
static attributes : model 8 + external CAMELS-H attributes
event response    : RBI, rising_time, event_duration, etc.

Outputs
-------
output/model_analysis/q99_analysis/causes/tables/basin_q99_error_profile.csv   (85×3=255 rows, per seed)
output/model_analysis/q99_analysis/causes/tables/basin_q99_error_summary.csv   (85 rows, seed median)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

REPO_ROOT = Path(__file__).resolve().parents[3]

Q99_DIR = REPO_ROOT / "output/model_analysis/q99_analysis/performance"
# Use expanded_drbc_test required_series (all timesteps, all basins)
REQUIRED_DIR = REPO_ROOT / "output/model_analysis/primary/metrics/data/required_series"
NC_DIR = REPO_ROOT / "data/CAMELSH_generic/drbc_expanded_observed_test/time_series"

STATIC_PATH = (
    REPO_ROOT
    / "output/basin/drbc/analysis/basin_attributes/tables"
    / "drbc_selected_static_attributes_full.csv"
)
EVENT_RESPONSE_PATH = (
    REPO_ROOT
    / "output/basin/expanded_drbc/analysis/event_response/tables"
    / "event_response_basin_summary.csv"
)

OUT_DIR = REPO_ROOT / "output/model_analysis/q99_analysis/causes/tables"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OFFICIAL_SEEDS = [111, 222, 444]

# External static attributes to include
STATIC_COLS = [
    "drain_sqkm", "SLOPE_PCT", "ELEV_MEAN_M_BASIN", "RRMEAN",
    "BFI_AVE", "PERDUN", "PERHOR", "TOPWET", "CONTACT", "RUNAVE7100",
    "aridity_index", "p_mean", "p_seasonality", "frac_snow",
    "high_prec_freq", "high_prec_dur", "low_prec_freq", "low_prec_dur",
    "PERMAVE", "AWCAVE", "HGA", "HGB", "HGC", "HGD",
    "DEVNLCD06", "FORESTNLCD06", "PLANTNLCD06",
    "ARTIFPATH_PCT", "ARTIFPATH_MAINSTEM_PCT",
    "STREAMS_KM_SQ_KM", "STRAHLER_MAX", "MAINSTEM_SINUOUSITY",
]

# Dynamic event attributes from event_response_basin_summary
DYNAMIC_COLS = [
    "rbi", "rising_time_median_hours", "event_duration_median_hours",
    "event_runoff_coefficient_median", "q99_event_count", "q99_event_frequency",
    "unit_area_peak_median", "unit_area_peak_p90",
]


def _peak_rel_error(pred: pd.Series, obs: pd.Series) -> float:
    """(pred_at_obs_peak - obs_peak) / obs_peak"""
    if obs.empty or obs.max() <= 0:
        return np.nan
    peak_idx = obs.idxmax()
    return float((pred.loc[peak_idx] - obs.loc[peak_idx]) / obs.loc[peak_idx])


def _under_frac(pred: pd.Series, obs: pd.Series) -> float:
    mask = obs > 0
    if mask.sum() < 2:
        return np.nan
    return float((pred[mask] < obs[mask]).mean())


def _med_rel_bias(pred: pd.Series, obs: pd.Series) -> float:
    mask = obs > 0
    if mask.sum() < 2:
        return np.nan
    return float(np.median((pred[mask] - obs[mask]) / obs[mask]))


def load_forcing_event_stats(
    basin: str,
    block_start: str,
    block_end: str,
) -> dict:
    """Extract event-level forcing statistics from NC file for a given block."""
    nc_path = NC_DIR / f"{basin}.nc"
    if not nc_path.exists():
        return {}
    try:
        ds = xr.open_dataset(nc_path)
        t0 = pd.Timestamp(block_start)
        t1 = pd.Timestamp(block_end)
        # antecedent window: 5 days before event
        t_pre = t0 - pd.Timedelta(days=5)

        sub = ds.sel(date=slice(str(t0), str(t1)))
        pre = ds.sel(date=slice(str(t_pre), str(t0)))

        rainf = sub["Rainf"].values
        cape = sub["CAPE"].values if "CAPE" in ds else np.array([np.nan])
        pre_rain = pre["Rainf"].values

        ds.close()
        return {
            "event_total_rainf": float(np.nansum(rainf)),
            "event_peak_rainf": float(np.nanmax(rainf)) if len(rainf) > 0 else np.nan,
            "event_mean_cape": float(np.nanmean(cape)),
            "antecedent_5d_rainf": float(np.nansum(pre_rain)),
        }
    except Exception:
        return {}


def compute_basin_seed_q99_metrics(series: pd.DataFrame) -> pd.DataFrame:
    """Compute per-basin Q99-stratum error metrics from full required_series.

    Uses basin-specific obs 99th percentile as threshold (obs_q99_plus stratum).
    Also extracts event-level forcing stats from NC files for each high-obs window.
    """
    records = []
    for basin, grp in series.groupby("basin"):
        obs = grp["obs"].astype(float)
        obs_valid = obs[obs > 0]
        if len(obs_valid) < 100:
            continue

        q99_thr = float(obs_valid.quantile(0.99))
        mask = obs >= q99_thr
        if mask.sum() < 3:
            continue

        obs_hi = obs[mask]
        q99_hi = grp["q99"].astype(float)[mask]
        m1_hi = grp["model1"].astype(float)[mask]

        # identify contiguous high-obs windows for forcing stats
        dt = pd.to_datetime(grp["datetime"])
        hi_times = dt[mask].sort_values()
        event_stats_list = []
        if len(hi_times) > 0:
            # group into contiguous windows (gap > 72h = new event)
            gaps = hi_times.diff() > pd.Timedelta(hours=72)
            event_id = gaps.cumsum()
            for eid, ev_times in hi_times.groupby(event_id):
                t0 = ev_times.min() - pd.Timedelta(hours=24)
                t1 = ev_times.max()
                stats = load_forcing_event_stats(basin, str(t0), str(t1))
                if stats:
                    event_stats_list.append(stats)

        row: dict = {
            "basin": basin,
            "n_q99_timesteps": int(mask.sum()),
            "obs_q99_threshold": q99_thr,
            "q99_under_frac": _under_frac(q99_hi, obs_hi),
            "q99_med_rel_bias": _med_rel_bias(q99_hi, obs_hi),
            "model1_under_frac": _under_frac(m1_hi, obs_hi),
            "model1_med_rel_bias": _med_rel_bias(m1_hi, obs_hi),
        }
        row["under_frac_delta"] = row["model1_under_frac"] - row["q99_under_frac"]
        row["med_rel_bias_delta"] = row["model1_med_rel_bias"] - row["q99_med_rel_bias"]

        if event_stats_list:
            stats_df = pd.DataFrame(event_stats_list)
            for col in stats_df.columns:
                row[f"event_{col}_median"] = float(stats_df[col].median())

        records.append(row)

    return pd.DataFrame(records)


def main() -> None:
    # static attributes
    attrs = pd.read_csv(STATIC_PATH).rename(columns={"gauge_id": "basin"})
    attrs["basin"] = attrs["basin"].astype(str)
    avail_static = [c for c in STATIC_COLS if c in attrs.columns]
    attrs = attrs[["basin"] + avail_static]

    # event response
    evr = pd.read_csv(EVENT_RESPONSE_PATH).rename(columns={"gauge_id": "basin"})
    evr["basin"] = evr["basin"].astype(str)
    avail_dyn = [c for c in DYNAMIC_COLS if c in evr.columns]
    evr = evr[["basin"] + avail_dyn]

    all_frames = []
    for seed in OFFICIAL_SEEDS:
        print(f"[seed {seed}] loading required_series …", flush=True)
        series_path = REQUIRED_DIR / f"seed{seed}" / "required_series.csv"
        series = pd.read_csv(series_path)
        series["basin"] = series["basin"].astype(str)

        print(f"[seed {seed}] computing per-basin Q99 event metrics …", flush=True)
        metrics = compute_basin_seed_q99_metrics(series)
        metrics["seed"] = seed
        all_frames.append(metrics)

    profile = pd.concat(all_frames, ignore_index=True)
    profile = profile.merge(attrs, on="basin", how="left")
    profile = profile.merge(evr, on="basin", how="left")

    front = ["basin", "seed"]
    rest = [c for c in profile.columns if c not in front]
    profile = profile[front + rest]

    out_profile = OUT_DIR / "basin_q99_error_profile.csv"
    profile.to_csv(out_profile, index=False)
    print(f"\nSaved: {out_profile}  ({len(profile)} rows)")

    # seed median summary
    numeric = [c for c in profile.select_dtypes("number").columns if c != "seed"]
    summary = profile.groupby("basin")[numeric].median().reset_index()
    out_summary = OUT_DIR / "basin_q99_error_summary.csv"
    summary.to_csv(out_summary, index=False)
    print(f"Saved: {out_summary}  ({len(summary)} rows)")

    print("\n── Q99 med_rel_bias (seed median) ──")
    print(summary["q99_med_rel_bias"].describe())
    print("\n── med_rel_bias_delta (positive = q99 improved) ──")
    print(summary["med_rel_bias_delta"].describe())


if __name__ == "__main__":
    main()
