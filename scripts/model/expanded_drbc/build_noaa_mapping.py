#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
# ]
# ///
"""B2 — NOAA confirmed flood event → expanded DRBC 85-basin mapping + event-type parsing.

Inputs
------
- output/model_analysis/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv
- data/CAMELSH_generic/drbc_expanded_observed_test/time_series/<basin>.nc
  (canonical 85-basin id list from directory listing)

Outputs
-------
- tables/rq2_id_normalization_report.csv
- tables/rq2_noaa_basin_overlap_summary.csv
- tables/rq2_noaa_events_expanded_overlap.csv
- tables/rq4b_event_type_mapping.csv
- tables/rq4b_noaa_annotation_unmatched.csv

Algorithm:
  0. Normalize both NOAA `usgs_id` and expanded basin ids via normalize_basin_id (zfill 8).
  1. Compute intersection NOAA ∩ expanded.
  2. Parse `noaa_annotation` per event using NOAA_REGEX → dominant_event_type with
     NOAA_TIE_BREAK (most-specific wins). Unmatched annotations → "Other" + listed in
     rq4b_noaa_annotation_unmatched.csv.
  3. Acceptance: unmatched / total annotation rows < 5%.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

LIB_ROOT = Path(__file__).resolve().parents[2] / "_lib"
if str(LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(LIB_ROOT))

from expanded_drbc import (  # noqa: E402
    EVENT_WINDOW_HOURS,
    TEST_PERIOD,
    normalize_basin_id,
    parse_dominant_event_type,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CATALOG = REPO_ROOT / "output/model_analysis/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv"
DEFAULT_BASIN_DIR = REPO_ROOT / "data/CAMELSH_generic/drbc_expanded_observed_test/time_series"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/expanded_drbc_test"

UNMATCHED_THRESHOLD = 0.05  # acceptance gate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-csv", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--basin-dir", type=Path, default=DEFAULT_BASIN_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    tables_dir = args.output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    # Sub-step 0: normalize ids on both sides
    catalog = pd.read_csv(args.catalog_csv, dtype={"usgs_id": str})
    catalog["basin_id"] = catalog["usgs_id"].map(normalize_basin_id)

    expanded_basins = sorted(normalize_basin_id(p.stem) for p in args.basin_dir.glob("*.nc"))
    expanded_set = set(expanded_basins)
    noaa_set = set(catalog["basin_id"].unique())

    id_report_rows: list[dict[str, object]] = []
    for raw in catalog["usgs_id"].unique():
        norm = normalize_basin_id(raw)
        id_report_rows.append({
            "source": "noaa",
            "raw_id": raw,
            "normalized_id": norm,
            "matched": norm in expanded_set,
        })
    for b in expanded_basins:
        id_report_rows.append({
            "source": "expanded",
            "raw_id": b,
            "normalized_id": b,
            "matched": b in noaa_set,
        })
    id_report = pd.DataFrame(id_report_rows)
    id_report_path = tables_dir / "rq2_id_normalization_report.csv"
    id_report.to_csv(id_report_path, index=False)
    print(f"[B2] wrote {id_report_path} ({len(id_report)} rows)", flush=True)

    # Sub-step 1: overlap summary
    overlap = noaa_set & expanded_set
    summary = pd.DataFrame([{
        "n_noaa_basins": len(noaa_set),
        "n_expanded_basins": len(expanded_set),
        "n_overlap": len(overlap),
        "n_noaa_only": len(noaa_set - expanded_set),
        "n_expanded_only": len(expanded_set - noaa_set),
    }])
    summary_path = tables_dir / "rq2_noaa_basin_overlap_summary.csv"
    summary.to_csv(summary_path, index=False)
    print(f"[B2] overlap: NOAA={len(noaa_set)} expanded={len(expanded_set)} both={len(overlap)}", flush=True)

    # Sub-step 2: parse annotations
    catalog["in_expanded_85"] = catalog["basin_id"].isin(expanded_set)
    # Catalog row is NWS-flood-stage exceedance. `noaa_annotation == "-"` means no NOAA
    # Storm Events corroboration (annotation column placeholder). Distinguish these
    # ("NoNOAA") from rows with annotation text that nonetheless failed the regex match
    # ("Other"). Acceptance gate applies only to the latter denominator.
    has_annotation = catalog["noaa_annotation"].fillna("-").astype(str).str.strip() != "-"

    def _parse(row_annotation: str) -> tuple[str, int]:
        """Return (dominant_label, total_regex_hits)."""
        label, counts = parse_dominant_event_type(row_annotation)
        return label, sum(counts.values())

    dominant_labels: list[str] = []
    total_hits: list[int] = []
    for ann, ha_flag in zip(catalog["noaa_annotation"], has_annotation):
        if not ha_flag:
            dominant_labels.append("NoNOAA")
            total_hits.append(0)
            continue
        label, n_hits = _parse(ann)
        dominant_labels.append(label)
        total_hits.append(n_hits)
    catalog["dominant_event_type"] = dominant_labels
    catalog["regex_total_hits"] = total_hits
    catalog["peak_time"] = pd.to_datetime(catalog["peak_time"], errors="coerce")
    catalog["window_start"] = catalog["peak_time"] - pd.Timedelta(hours=EVENT_WINDOW_HOURS)
    catalog["window_end"] = catalog["peak_time"] + pd.Timedelta(hours=EVENT_WINDOW_HOURS)

    # Truncate at TEST_PERIOD boundary
    test_start = pd.Timestamp(TEST_PERIOD[0])
    test_end = pd.Timestamp(TEST_PERIOD[1]) + pd.Timedelta(hours=23)
    catalog["window_truncated"] = (
        (catalog["window_start"] < test_start) | (catalog["window_end"] > test_end)
    )
    catalog.loc[catalog["window_start"] < test_start, "window_start"] = test_start
    catalog.loc[catalog["window_end"] > test_end, "window_end"] = test_end

    # Assign event_id per basin
    catalog = catalog.sort_values(["basin_id", "peak_time"]).reset_index(drop=True)
    catalog["event_id"] = catalog.groupby("basin_id").cumcount()

    keep_cols = [
        "basin_id", "event_id", "peak_time", "peak_discharge_cms",
        "window_start", "window_end", "window_truncated",
        "in_expanded_85", "noaa_annotation", "dominant_event_type",
        "flood_tier", "noaa_corroborated", "period",
    ]
    events_overlap = catalog[keep_cols].rename(columns={"peak_discharge_cms": "peak_obs"})
    events_overlap_path = tables_dir / "rq2_noaa_events_expanded_overlap.csv"
    events_overlap.to_csv(events_overlap_path, index=False)
    print(f"[B2] wrote {events_overlap_path} ({len(events_overlap)} rows)", flush=True)

    # Sub-step 3: event-type mapping + unmatched artifact
    event_type_map = (
        events_overlap[events_overlap["in_expanded_85"]]
        .groupby("dominant_event_type")
        .agg(n_events=("event_id", "count"), n_basins=("basin_id", "nunique"))
        .reset_index()
    )
    event_type_path = tables_dir / "rq4b_event_type_mapping.csv"
    event_type_map.to_csv(event_type_path, index=False)
    print(f"[B2] wrote {event_type_path}", flush=True)
    print(event_type_map.to_string(index=False), flush=True)

    # Unmatched = has annotation text but zero regex hits. Acceptance gate runs only
    # on the annotation-bearing subset (NoNOAA rows are NWS-only without NOAA Storm Events
    # corroboration and are not a regex failure case). Mask uses dominant_event_type
    # rather than the original has_annotation Series because catalog has been sorted
    # and reset_index above.
    annotated = catalog[catalog["dominant_event_type"] != "NoNOAA"]
    unmatched = annotated[annotated["regex_total_hits"] == 0]
    unmatched_keep = ["basin_id", "event_id", "peak_time", "noaa_annotation"]
    unmatched_path = tables_dir / "rq4b_noaa_annotation_unmatched.csv"
    unmatched[unmatched_keep].to_csv(unmatched_path, index=False)
    pct_unmatched = len(unmatched) / max(1, len(annotated))
    print(
        f"[B2] annotation-bearing rows: {len(annotated)} / {len(catalog)}; "
        f"unmatched among those: {len(unmatched)} = {pct_unmatched:.2%}",
        flush=True,
    )

    # Acceptance gate (corroborated denominator)
    assert pct_unmatched < UNMATCHED_THRESHOLD, (
        f"unmatched fraction {pct_unmatched:.3%} >= {UNMATCHED_THRESHOLD:.0%} acceptance gate"
    )
    print("[B2] acceptance: unmatched among corroborated < 5% PASS", flush=True)


if __name__ == "__main__":
    main()
