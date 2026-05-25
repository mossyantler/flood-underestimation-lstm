#!/usr/bin/env python3
# /// script
# dependencies = ["pandas>=2.2"]
# ///
"""Convert Q99+ event response table to inference blocks CSV.

Reads the expanded DRBC event response table and builds per-basin inference
blocks by padding each event with a warmup/post window, then merging events
whose padded windows overlap or are within merge_gap_days.

Output matches the inference_blocks.csv schema used by
infer_subset300_extreme_rain_windows.py:
  gauge_id, block_id, block_start, block_end, n_events, event_ids,
  rain_cohorts, response_classes
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_EVENT_RESPONSE = REPO_ROOT / "output/basin/expanded_drbc/analysis/event_response/tables/event_response_table.csv"
DEFAULT_OUTPUT_CSV = REPO_ROOT / "output/model_analysis/expanded/extreme_rain/expanded_drbc/basin_performance/q99_inference_blocks.csv"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--event-response", type=Path, default=DEFAULT_EVENT_RESPONSE)
    p.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    p.add_argument("--warmup-days", type=int, default=5,
                   help="Days before event_start for model warmup.")
    p.add_argument("--post-days", type=int, default=3,
                   help="Days after event_end to include in block.")
    p.add_argument("--merge-gap-days", type=int, default=7,
                   help="Merge events whose padded windows are within this many days.")
    p.add_argument("--basin", action="append", dest="basins",
                   help="Restrict to specific gauge_id(s).")
    return p.parse_args()


def build_blocks(
    events: pd.DataFrame,
    *,
    warmup_days: int,
    post_days: int,
    merge_gap_days: int,
) -> pd.DataFrame:
    events = events.copy()
    events["candidate_start"] = pd.to_datetime(events["event_start"]) - pd.Timedelta(days=warmup_days)
    events["candidate_end"] = pd.to_datetime(events["event_end"]) + pd.Timedelta(days=post_days)

    rows: list[dict[str, Any]] = []
    for basin, group in events.sort_values(["gauge_id", "candidate_start"]).groupby("gauge_id"):
        block_start: pd.Timestamp | None = None
        block_end: pd.Timestamp | None = None
        block_events: list[pd.Series] = []
        block_index = 0

        for _, row in group.iterrows():
            start = pd.Timestamp(row["candidate_start"]).floor("D")
            end = pd.Timestamp(row["candidate_end"]).ceil("D") - pd.Timedelta(hours=1)

            if block_start is None:
                block_start, block_end = start, end
                block_events = [row]
                continue

            if start <= block_end + pd.Timedelta(days=merge_gap_days):
                block_end = max(block_end, end)
                block_events.append(row)
                continue

            block_index += 1
            rows.append(_render_row(str(basin), block_index, block_start, block_end, block_events))
            block_start, block_end = start, end
            block_events = [row]

        if block_start is not None and block_end is not None:
            block_index += 1
            rows.append(_render_row(str(basin), block_index, block_start, block_end, block_events))

    return pd.DataFrame(rows)


def _render_row(
    basin: str,
    block_index: int,
    block_start: pd.Timestamp,
    block_end: pd.Timestamp,
    events: list[pd.Series],
) -> dict[str, Any]:
    return {
        "gauge_id": basin,
        "block_id": f"{basin}_q99_block_{block_index:03d}",
        "block_start": block_start,
        "block_end": block_end,
        "n_events": len(events),
        "event_ids": ";".join(str(row["event_id"]) for row in events),
        "rain_cohorts": "q99_event",
        "response_classes": "q99_ge_threshold",
    }


def main() -> None:
    args = parse_args()
    events = pd.read_csv(args.event_response, dtype={"gauge_id": str})
    print(f"Loaded {len(events)} Q99+ events for {events['gauge_id'].nunique()} basins")

    if args.basins:
        events = events[events["gauge_id"].isin(args.basins)].copy()
        print(f"Filtered to {events['gauge_id'].nunique()} basins")

    blocks = build_blocks(
        events,
        warmup_days=args.warmup_days,
        post_days=args.post_days,
        merge_gap_days=args.merge_gap_days,
    )

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    blocks.to_csv(args.output_csv, index=False)
    print(f"Wrote {args.output_csv}")
    print(f"Blocks: {len(blocks)} | Basins: {blocks['gauge_id'].nunique()}")
    print(f"Block size: min={blocks['n_events'].min()}, max={blocks['n_events'].max()}, mean={blocks['n_events'].mean():.1f}")
    print(f"Date range: {blocks['block_start'].min()} → {blocks['block_end'].max()}")


if __name__ == "__main__":
    main()
