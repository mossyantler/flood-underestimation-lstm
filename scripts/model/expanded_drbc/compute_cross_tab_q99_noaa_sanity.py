#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
# ]
# ///
"""B9 — Cross-tab Q99 ∩ NOAA event sanity check.

Geometry (locked per plan §5 B9): NOAA peak_time ∈ Q99 event window directly;
no 12h secondary buffer.

Inputs:
- tables/rq2_q99_events_85basin.csv (B1)
- tables/rq2_noaa_events_expanded_overlap.csv (B2; in_expanded_85 True, test period)

Outputs:
- tables/cross_tab_q99_noaa_sanity_per_basin.csv
- tables/cross_tab_q99_noaa_sanity_pooled.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

LIB_ROOT = Path(__file__).resolve().parents[2] / "_lib"
if str(LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(LIB_ROOT))

from expanded_drbc import normalize_basin_id  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/primary/metrics"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    tables_dir = args.output_dir / "tables"

    q99 = pd.read_csv(
        tables_dir / "rq2_q99_events_85basin.csv",
        comment="#",
        dtype={"basin_id": str},
        parse_dates=["peak_time", "window_start", "window_end"],
    )
    q99["basin_id"] = q99["basin_id"].map(normalize_basin_id)

    noaa = pd.read_csv(
        tables_dir / "rq2_noaa_events_expanded_overlap.csv",
        dtype={"basin_id": str},
        parse_dates=["peak_time", "window_start", "window_end"],
    )
    noaa["basin_id"] = noaa["basin_id"].map(normalize_basin_id)
    test_start = pd.Timestamp("2014-01-01")
    test_end = pd.Timestamp("2016-12-31 23:00:00")
    noaa = noaa[
        noaa["in_expanded_85"]
        & (noaa["peak_time"] >= test_start)
        & (noaa["peak_time"] <= test_end)
    ].copy()

    overlap_basins = sorted(set(q99["basin_id"]).intersection(set(noaa["basin_id"])))
    print(f"[B9] overlap basins: {len(overlap_basins)}", flush=True)

    per_basin_rows = []
    for basin in overlap_basins:
        q_sub = q99[q99["basin_id"] == basin]
        n_sub = noaa[noaa["basin_id"] == basin]
        # NOAA peak in any Q99 window?
        noaa_in_q99 = 0
        for _, n_row in n_sub.iterrows():
            t = n_row["peak_time"]
            inside = ((q_sub["window_start"] <= t) & (t <= q_sub["window_end"])).any()
            if inside:
                noaa_in_q99 += 1
        noaa_only = len(n_sub) - noaa_in_q99
        # Q99 event with no NOAA peak inside its window?
        q99_only = 0
        for _, q_row in q_sub.iterrows():
            ws, we = q_row["window_start"], q_row["window_end"]
            has_noaa_inside = ((n_sub["peak_time"] >= ws) & (n_sub["peak_time"] <= we)).any()
            if not has_noaa_inside:
                q99_only += 1
        n_both = noaa_in_q99
        n_q99 = len(q_sub)
        n_noaa = len(n_sub)
        per_basin_rows.append({
            "basin_id": basin,
            "n_q99_events": n_q99,
            "n_noaa_events": n_noaa,
            "n_both": n_both,
            "n_noaa_only": noaa_only,
            "n_q99_only": q99_only,
            "frac_noaa_in_q99": n_both / n_noaa if n_noaa > 0 else float("nan"),
            "frac_q99_in_noaa": (n_q99 - q99_only) / n_q99 if n_q99 > 0 else float("nan"),
        })
    per_basin = pd.DataFrame(per_basin_rows)
    per_basin_path = tables_dir / "cross_tab_q99_noaa_sanity_per_basin.csv"
    per_basin.to_csv(per_basin_path, index=False)
    print(f"[B9] wrote {per_basin_path} ({len(per_basin)} rows)", flush=True)

    pooled = pd.DataFrame([{
        "n_overlap_basins": len(per_basin),
        "total_q99_events": int(per_basin["n_q99_events"].sum()),
        "total_noaa_events": int(per_basin["n_noaa_events"].sum()),
        "total_both": int(per_basin["n_both"].sum()),
        "total_noaa_only": int(per_basin["n_noaa_only"].sum()),
        "total_q99_only": int(per_basin["n_q99_only"].sum()),
        "pooled_frac_noaa_in_q99": per_basin["n_both"].sum() / max(1, per_basin["n_noaa_events"].sum()),
        "pooled_frac_q99_covered_by_noaa": (
            (per_basin["n_q99_events"].sum() - per_basin["n_q99_only"].sum())
            / max(1, per_basin["n_q99_events"].sum())
        ),
    }])
    pooled_path = tables_dir / "cross_tab_q99_noaa_sanity_pooled.csv"
    pooled.to_csv(pooled_path, index=False)
    print(f"[B9] wrote {pooled_path}", flush=True)
    print(pooled.to_string(index=False), flush=True)

    # Sanity: n_both + n_noaa_only = total NOAA events
    sum_check = per_basin["n_both"].sum() + per_basin["n_noaa_only"].sum()
    assert sum_check == per_basin["n_noaa_events"].sum(), "n_both + n_noaa_only != total NOAA"
    print("[B9] sanity: n_both + n_noaa_only = total NOAA OK", flush=True)


if __name__ == "__main__":
    main()
