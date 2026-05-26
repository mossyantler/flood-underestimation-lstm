#!/usr/bin/env python3
# /// script
# dependencies = [
#   "netCDF4>=1.7",
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "xarray>=2024.1",
# ]
# ///
"""B1 — per-basin Q99 threshold from train-period obs + Q99 exceedance event windows.

Inputs
------
- data/CAMELSH_generic/drbc_expanded_observed_test/time_series/<basin>.nc
  (per-basin NetCDF; uses `Streamflow` variable over TRAIN_PERIOD for Q99)
- output/model_analysis/expanded_drbc_test/required_series/seed111/primary_required_series.csv
  (test-period obs; obs is identical across seeds — seed111 used as canonical source)

Outputs
-------
- tables/rq2_q99_per_basin_thresholds.csv
    basin_id, q99_train_value, train_n_hours, n_test_exceedance_events
- tables/rq2_q99_events_85basin.csv
    basin_id, event_id, peak_time, peak_obs, window_start, window_end, window_truncated
- tables/rq2_q99_basin_warnings.csv
    basin_id, warning_kind, detail   (WARN-only, not failure)

Algorithm:
  1. Q99 = 99th percentile of train-period (TRAIN_PERIOD from C0) Streamflow per basin.
  2. In test period (TEST_PERIOD), find timesteps where obs >= Q99.
  3. Cluster contiguous (and within EVENT_MERGE_GAP_HOURS) exceedances; event peak = max obs.
  4. Event window = [peak - EVENT_WINDOW_HOURS, peak + EVENT_WINDOW_HOURS].
     Window truncated if it extends past TEST_PERIOD; `window_truncated` flag.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

LIB_ROOT = Path(__file__).resolve().parents[2] / "_lib"
if str(LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(LIB_ROOT))

from expanded_drbc import (  # noqa: E402
    EVENT_MERGE_GAP_HOURS,
    EVENT_WINDOW_HOURS,
    HIGH_FLOW_PERCENTILE,
    TEST_PERIOD,
    TRAIN_PERIOD,
    normalize_basin_id,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TS_DIR = REPO_ROOT / "data/CAMELSH_generic/drbc_expanded_observed_test/time_series"
DEFAULT_TEST_OBS_CSV = (
    REPO_ROOT
    / "output/model_analysis/expanded_drbc_test/required_series/seed111/primary_required_series.csv"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/expanded_drbc_test"

# Soft warning thresholds (acceptance does not fail; warnings emitted)
WARN_TOO_FEW_EVENTS = 3
WARN_TOO_MANY_EVENTS = 300


def basin_q99_from_netcdf(nc_path: Path) -> tuple[float, int]:
    """Return (Q99, n_train_hours_used) computed over TRAIN_PERIOD Streamflow."""
    with xr.open_dataset(nc_path) as ds:
        flow = ds["Streamflow"].sel(date=slice(*TRAIN_PERIOD)).values
    valid = flow[~np.isnan(flow)]
    if valid.size == 0:
        return float("nan"), 0
    return float(np.quantile(valid, HIGH_FLOW_PERCENTILE)), int(valid.size)


def find_events_for_basin(
    obs_series: pd.Series,
    *,
    threshold: float,
    merge_gap_hours: int,
    window_hours: int,
    test_start: pd.Timestamp,
    test_end: pd.Timestamp,
) -> list[dict[str, object]]:
    """Cluster timestamps where obs >= threshold into events; return event dicts."""
    if obs_series.empty or np.isnan(threshold):
        return []
    obs = obs_series.dropna()
    above = obs[obs >= threshold]
    if above.empty:
        return []
    times = above.index.to_list()
    clusters: list[list[pd.Timestamp]] = []
    current = [times[0]]
    for t in times[1:]:
        gap_h = (t - current[-1]).total_seconds() / 3600.0
        if gap_h <= merge_gap_hours:
            current.append(t)
        else:
            clusters.append(current)
            current = [t]
    clusters.append(current)

    events: list[dict[str, object]] = []
    for event_id, cluster in enumerate(clusters):
        cluster_obs = above.loc[cluster]
        peak_time = cluster_obs.idxmax()
        peak_value = float(cluster_obs.max())
        win_start = peak_time - pd.Timedelta(hours=window_hours)
        win_end = peak_time + pd.Timedelta(hours=window_hours)
        truncated = False
        if win_start < test_start:
            win_start = test_start
            truncated = True
        if win_end > test_end:
            win_end = test_end
            truncated = True
        events.append({
            "event_id": event_id,
            "peak_time": peak_time,
            "peak_obs": peak_value,
            "window_start": win_start,
            "window_end": win_end,
            "window_truncated": truncated,
        })
    return events


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--time-series-dir", type=Path, default=DEFAULT_TS_DIR)
    parser.add_argument("--test-obs-csv", type=Path, default=DEFAULT_TEST_OBS_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    tables_dir = args.output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    # Discover basins from NetCDF directory
    nc_files = sorted(args.time_series_dir.glob("*.nc"))
    if not nc_files:
        raise FileNotFoundError(args.time_series_dir)
    basin_ids = [normalize_basin_id(p.stem) for p in nc_files]
    print(f"[B1] discovered {len(basin_ids)} basins in {args.time_series_dir}", flush=True)

    # Q99 thresholds
    thresholds: list[dict[str, object]] = []
    q99_by_basin: dict[str, float] = {}
    for nc_path in nc_files:
        basin = normalize_basin_id(nc_path.stem)
        q99, n = basin_q99_from_netcdf(nc_path)
        q99_by_basin[basin] = q99
        thresholds.append({
            "basin_id": basin,
            "q99_train_value": q99,
            "train_n_hours": n,
            "n_test_exceedance_events": 0,  # filled after event extraction
        })
    print(f"[B1] Q99 thresholds computed for {len(thresholds)} basins", flush=True)

    # Load test-period obs (seed111 canonical)
    print(f"[B1] loading test obs from {args.test_obs_csv}", flush=True)
    test_obs = pd.read_csv(
        args.test_obs_csv,
        usecols=["basin", "datetime", "obs"],
        dtype={"basin": str},
        parse_dates=["datetime"],
    )
    test_obs["basin_id"] = test_obs["basin"].map(normalize_basin_id)
    test_obs = test_obs.dropna(subset=["obs"])
    test_start = pd.Timestamp(TEST_PERIOD[0])
    test_end = pd.Timestamp(TEST_PERIOD[1]) + pd.Timedelta(hours=23)

    # Find events per basin
    event_rows: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    for thr_row in thresholds:
        basin = thr_row["basin_id"]
        q99 = thr_row["q99_train_value"]
        sub = test_obs[test_obs.basin_id == basin].set_index("datetime")["obs"].sort_index()
        events = find_events_for_basin(
            sub,
            threshold=q99,
            merge_gap_hours=EVENT_MERGE_GAP_HOURS,
            window_hours=EVENT_WINDOW_HOURS,
            test_start=test_start,
            test_end=test_end,
        )
        thr_row["n_test_exceedance_events"] = len(events)
        for e in events:
            event_rows.append({"basin_id": basin, **e})
        if len(events) < WARN_TOO_FEW_EVENTS:
            warnings.append({"basin_id": basin, "warning_kind": "few_events", "detail": f"n_events={len(events)} < {WARN_TOO_FEW_EVENTS}"})
        elif len(events) > WARN_TOO_MANY_EVENTS:
            warnings.append({"basin_id": basin, "warning_kind": "many_events", "detail": f"n_events={len(events)} > {WARN_TOO_MANY_EVENTS}"})

    thresholds_df = pd.DataFrame(thresholds)
    events_df = pd.DataFrame(event_rows)
    warnings_df = pd.DataFrame(warnings) if warnings else pd.DataFrame(
        columns=["basin_id", "warning_kind", "detail"]
    )

    # Write outputs
    thr_path = tables_dir / "rq2_q99_per_basin_thresholds.csv"
    with thr_path.open("w") as f:
        f.write("# B1 — per-basin Q99 from train period (2000-2010) + test event count\n")
        f.write(f"# train period: {TRAIN_PERIOD}; test period: {TEST_PERIOD}; percentile={HIGH_FLOW_PERCENTILE}\n")
        thresholds_df.to_csv(f, index=False)
    print(f"[B1] wrote {thr_path} ({len(thresholds_df)} rows)", flush=True)

    events_path = tables_dir / "rq2_q99_events_85basin.csv"
    with events_path.open("w") as f:
        f.write("# B1 — Q99 exceedance events with ±6h windows (truncated at test boundary)\n")
        f.write(f"# merge gap: {EVENT_MERGE_GAP_HOURS}h; window: ±{EVENT_WINDOW_HOURS}h\n")
        events_df.to_csv(f, index=False)
    print(f"[B1] wrote {events_path} ({len(events_df)} rows)", flush=True)

    warn_path = tables_dir / "rq2_q99_basin_warnings.csv"
    with warn_path.open("w") as f:
        f.write(f"# B1 — soft warnings: n_events < {WARN_TOO_FEW_EVENTS} or > {WARN_TOO_MANY_EVENTS}\n")
        warnings_df.to_csv(f, index=False)
    print(f"[B1] wrote {warn_path} ({len(warnings_df)} rows)", flush=True)

    # Sanity counters
    assert len(thresholds_df) == 85, f"expected 85 thresholds, got {len(thresholds_df)}"
    assert thresholds_df["n_test_exceedance_events"].sum() == len(events_df)
    print(f"[B1] sanity OK: 85 thresholds, events sum = {len(events_df)}", flush=True)


if __name__ == "__main__":
    main()
