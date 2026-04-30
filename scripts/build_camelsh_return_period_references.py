#!/usr/bin/env python3
# /// script
# dependencies = [
#   "netCDF4>=1.7",
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "scipy>=1.13",
#   "xarray>=2024.1",
# ]
# ///

from __future__ import annotations

import argparse
import concurrent.futures as futures
import json
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import camelsh_flood_analysis_utils as fu


DEFAULT_METADATA = [
    Path("basins/CAMELSH_data/attributes/attributes_gageii_BasinID.csv"),
    Path("data/CAMELSH_generic/drbc_holdout_broad/attributes/static_attributes.csv"),
    Path("configs/pilot/basin_splits/prepared_pool_manifest.csv"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build basin-level CAMELSH precipitation and flood return-period reference "
            "tables from hourly NetCDF files."
        )
    )
    parser.add_argument(
        "--timeseries-dir",
        type=Path,
        default=Path("data/CAMELSH_generic/drbc_holdout_broad/time_series"),
        help="Directory containing one hourly NetCDF file per basin.",
    )
    parser.add_argument(
        "--timeseries-csv-dir",
        type=Path,
        default=Path("data/CAMELSH_generic/drbc_holdout_broad/time_series_csv"),
        help="Optional CSV fallback directory.",
    )
    parser.add_argument(
        "--metadata-csv",
        type=Path,
        action="append",
        default=None,
        help="Optional metadata CSV. Can be passed multiple times; defaults cover CAMELSH BasinID and prepared attrs.",
    )
    parser.add_argument("--basin-list", type=Path, default=None, help="Optional newline-delimited gauge ID list.")
    parser.add_argument("--gauge-id", action="append", default=[], help="Optional gauge ID filter. Can repeat.")
    parser.add_argument("--limit", type=int, default=None, help="Optional first-N basin limit for smoke tests.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/basin/all/analysis"),
        help="Analysis root directory. Return-period tables and metadata are written under return_period/.",
    )
    parser.add_argument(
        "--return-periods",
        type=int,
        nargs="+",
        default=list(fu.RETURN_PERIODS),
        help="Return periods, in years, to estimate.",
    )
    parser.add_argument(
        "--precip-durations",
        type=int,
        nargs="+",
        default=list(fu.PRECIP_DURATIONS_HOURS),
        help="Rolling precipitation durations, in hours.",
    )
    parser.add_argument(
        "--distribution",
        choices=["gumbel", "gev", "empirical"],
        default="gumbel",
        help="Annual-maxima frequency method. Gumbel is the stable default for all-basin batch runs.",
    )
    parser.add_argument(
        "--min-annual-coverage",
        type=float,
        default=0.8,
        help="Minimum valid hourly coverage required for a water year to enter annual maxima.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=max(1, min(4, os.cpu_count() or 1)),
        help="Number of parallel basin workers.",
    )
    parser.add_argument(
        "--write-annual-maxima",
        action="store_true",
        help="Also write long-form annual maxima used for the frequency estimates.",
    )
    return parser.parse_args()


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def process_basin(task: dict[str, Any]) -> tuple[dict[str, object] | None, list[dict[str, object]], dict[str, object] | None]:
    gauge_id = task["gauge_id"]
    try:
        frame = fu.read_timeseries(
            gauge_id,
            timeseries_dir=task["timeseries_dir"],
            timeseries_csv_dir=task["timeseries_csv_dir"],
            variables=("Streamflow", "Rainf"),
        )
        row, annual_rows = fu.build_return_period_reference_row(
            gauge_id=gauge_id,
            frame=frame,
            metadata=task["metadata"],
            return_periods=task["return_periods"],
            precip_durations=task["precip_durations"],
            method=task["distribution"],
            min_annual_coverage=task["min_annual_coverage"],
        )
        return row, annual_rows, None
    except Exception as exc:
        return None, [], {"gauge_id": gauge_id, "reason": type(exc).__name__, "detail": str(exc)}


def iter_results(tasks: list[dict[str, Any]], workers: int) -> list[tuple[dict[str, object] | None, list[dict[str, object]], dict[str, object] | None]]:
    progress = fu.ProgressReporter(total=len(tasks), label="return-period basins")
    progress.update(0)
    if workers <= 1:
        results = []
        for index, task in enumerate(tasks, start=1):
            results.append(process_basin(task))
            progress.update(index)
        return results

    results = []
    with futures.ProcessPoolExecutor(max_workers=workers) as executor:
        future_to_id = {executor.submit(process_basin, task): task["gauge_id"] for task in tasks}
        for index, future in enumerate(futures.as_completed(future_to_id), start=1):
            results.append(future.result())
            progress.update(index)
    return results


def main() -> None:
    args = parse_args()
    table_dir = args.output_dir / "return_period" / "tables"
    metadata_dir = args.output_dir / "return_period" / "metadata"
    table_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    if not args.timeseries_dir.exists():
        raise SystemExit(f"Time-series directory does not exist: {args.timeseries_dir}")

    metadata_paths = args.metadata_csv if args.metadata_csv is not None else DEFAULT_METADATA
    gauge_ids = fu.discover_gauge_ids(
        timeseries_dir=args.timeseries_dir,
        timeseries_csv_dir=args.timeseries_csv_dir,
        basin_list=args.basin_list,
        gauge_ids=args.gauge_id,
        limit=args.limit,
    )
    if not gauge_ids:
        raise SystemExit("No basins were found to process.")

    metadata = fu.load_basin_metadata(gauge_ids, metadata_paths)
    metadata_by_id = {row["gauge_id"]: pd.Series(row) for row in metadata.to_dict("records")}

    tasks = [
        {
            "gauge_id": gauge_id,
            "timeseries_dir": args.timeseries_dir,
            "timeseries_csv_dir": args.timeseries_csv_dir,
            "metadata": metadata_by_id[gauge_id],
            "return_periods": args.return_periods,
            "precip_durations": args.precip_durations,
            "distribution": args.distribution,
            "min_annual_coverage": args.min_annual_coverage,
        }
        for gauge_id in gauge_ids
    ]

    rows: list[dict[str, object]] = []
    annual_rows: list[dict[str, object]] = []
    skipped_rows: list[dict[str, object]] = []
    for row, annual, skipped in iter_results(tasks, workers=args.workers):
        if row is not None:
            rows.append(row)
        if args.write_annual_maxima:
            annual_rows.extend(annual)
        if skipped is not None:
            skipped_rows.append(skipped)

    reference = pd.DataFrame(rows).sort_values("gauge_id").reset_index(drop=True)
    skipped = pd.DataFrame(skipped_rows, columns=["gauge_id", "reason", "detail"])
    if not skipped.empty:
        skipped = skipped.sort_values("gauge_id").reset_index(drop=True)

    reference_path = table_dir / "return_period_reference_table.csv"
    skipped_path = table_dir / "return_period_skipped_basins.csv"
    summary_path = metadata_dir / "return_period_summary.json"
    annual_path = table_dir / "return_period_annual_maxima.csv"

    reference.to_csv(reference_path, index=False)
    skipped.to_csv(skipped_path, index=False)
    if args.write_annual_maxima:
        pd.DataFrame(annual_rows).sort_values(["gauge_id", "variable", "duration_hours", "water_year"]).to_csv(
            annual_path,
            index=False,
        )

    summary = {
        "input_basin_count": len(gauge_ids),
        "processed_basin_count": int(len(reference)),
        "skipped_basin_count": int(len(skipped)),
        "timeseries_dir": str(args.timeseries_dir),
        "metadata_csv": [str(path) for path in metadata_paths if path.exists()],
        "return_periods": args.return_periods,
        "precip_durations": args.precip_durations,
        "distribution": args.distribution,
        "min_annual_coverage": args.min_annual_coverage,
        "workers": args.workers,
        "outputs": {
            "return_period_reference_table": str(reference_path),
            "return_period_skipped_basins": str(skipped_path),
            "return_period_annual_maxima": str(annual_path) if args.write_annual_maxima else None,
        },
    }
    summary_path.write_text(json.dumps(json_safe(summary), indent=2), encoding="utf-8")

    print(f"Wrote return-period reference table: {reference_path}")
    print(f"Wrote skipped-basin table: {skipped_path}")
    if args.write_annual_maxima:
        print(f"Wrote annual maxima table: {annual_path}")
    print(f"Wrote summary: {summary_path}")


if __name__ == "__main__":
    main()
