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
import re
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

EVENT_BASE_COLUMNS = [
    "gauge_id",
    "gauge_name",
    "state",
    "huc02",
    "drain_sqkm_attr",
    "area",
    "snow_fraction",
    "selected_threshold_quantile",
    "selected_threshold_value",
    "event_id",
    "event_start",
    "event_peak",
    "event_end",
    "water_year",
    "peak_month",
    "cold_season_flag",
    "peak_discharge",
    "unit_area_peak",
    "rising_time_hours",
    "event_duration_hours",
    "recession_time_hours",
    "rising_rate",
    "recent_rain_6h",
    "recent_rain_24h",
    "recent_rain_72h",
    "antecedent_rain_7d",
    "antecedent_rain_30d",
    "peak_rain_intensity_6h",
    "event_mean_temp",
    "antecedent_mean_temp_7d",
    "peak_temp",
    "event_runoff_coefficient",
    "snow_related_flag",
    "rain_on_snow_proxy",
    "api_7d",
    "api_30d",
]

SUMMARY_BASE_COLUMNS = [
    "gauge_id",
    "gauge_name",
    "state",
    "huc02",
    "drain_sqkm_attr",
    "area",
    "snow_fraction",
    "obs_years_usable",
    "processing_status",
    "selected_threshold_quantile",
    "selected_threshold_value",
    "q99_event_count",
    "q98_event_count",
    "q95_event_count",
    "event_count",
    "annual_peak_years",
    "unit_area_peak_median",
    "unit_area_peak_p90",
    "q99_event_frequency",
    "rbi",
    "rising_time_median_hours",
    "event_duration_median_hours",
    "event_runoff_coefficient_median",
    "annual_peak_unit_area_median",
    "annual_peak_unit_area_p90",
]

SKIPPED_COLUMNS = ["gauge_id", "reason", "detail"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build all-basin CAMELSH observed-flow event response tables from hourly "
            "NetCDF files, optionally attaching return-period reference ratios."
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
    parser.add_argument("--metadata-csv", type=Path, action="append", default=None)
    parser.add_argument("--basin-list", type=Path, default=None, help="Optional newline-delimited gauge ID list.")
    parser.add_argument("--gauge-id", action="append", default=[], help="Optional gauge ID filter. Can repeat.")
    parser.add_argument("--limit", type=int, default=None, help="Optional first-N basin limit for smoke tests.")
    parser.add_argument(
        "--return-period-csv",
        type=Path,
        default=Path("output/basin/camelsh_all/flood_analysis/return_period_reference_table.csv"),
        help="Optional return-period reference table produced by build_camelsh_return_period_references.py.",
    )
    parser.add_argument(
        "--no-return-ratios",
        action="store_true",
        help="Do not attach return-period reference values or event ratios, even if the CSV exists.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/basin/camelsh_all/flood_analysis"),
        help="Directory for event-response outputs.",
    )
    parser.add_argument(
        "--min-annual-coverage",
        type=float,
        default=0.8,
        help="Minimum valid hourly coverage for annual peak summary fields.",
    )
    parser.add_argument("--min-event-count", type=int, default=fu.MIN_EVENT_COUNT)
    parser.add_argument("--inter-event-separation-hours", type=int, default=fu.INTER_EVENT_SEPARATION_HOURS)
    parser.add_argument(
        "--workers",
        type=int,
        default=max(1, min(4, os.cpu_count() or 1)),
        help="Number of parallel basin workers.",
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


def ratio_columns(return_periods: list[int], precip_durations: list[int]) -> list[str]:
    columns = [f"peak_to_flood_ari{period}" for period in return_periods]
    for period in return_periods:
        for duration in precip_durations:
            columns.append(f"recent_rain_{duration}h_to_prec_ari{period}_{duration}h")
    return columns


def return_reference_columns(return_period_df: pd.DataFrame | None) -> list[str]:
    if return_period_df is None:
        return []
    duplicate_metadata = {
        "gauge_id",
        "gauge_name",
        "state",
        "huc02",
        "area",
        "drain_sqkm_attr",
        "snow_fraction",
    }
    return [col for col in return_period_df.columns if col not in duplicate_metadata]


def infer_return_periods(return_period_df: pd.DataFrame | None) -> list[int]:
    if return_period_df is None:
        return list(fu.RETURN_PERIODS)
    periods = []
    for col in return_period_df.columns:
        match = re.fullmatch(r"flood_ari(\d+)", col)
        if match:
            periods.append(int(match.group(1)))
    return sorted(set(periods)) or list(fu.RETURN_PERIODS)


def infer_precip_durations(return_period_df: pd.DataFrame | None) -> list[int]:
    if return_period_df is None:
        return list(fu.PRECIP_DURATIONS_HOURS)
    durations = []
    for col in return_period_df.columns:
        match = re.fullmatch(r"prec_ari\d+_(\d+)h", col)
        if match:
            durations.append(int(match.group(1)))
    return sorted(set(durations)) or list(fu.PRECIP_DURATIONS_HOURS)


def load_return_period_refs(path: Path, disabled: bool) -> tuple[pd.DataFrame | None, dict[str, dict[str, object]]]:
    if disabled or not path.exists():
        return None, {}
    refs = pd.read_csv(path, dtype={"gauge_id": str})
    refs["gauge_id"] = refs["gauge_id"].map(fu.normalize_gauge_id)
    ref_by_id = {row["gauge_id"]: row for row in refs.to_dict("records")}
    return refs, ref_by_id


def attach_return_ratios(
    event_row: dict[str, object],
    *,
    return_ref: dict[str, object],
    return_periods: list[int],
    precip_durations: list[int],
) -> dict[str, object]:
    if not return_ref:
        return event_row

    for period in return_periods:
        event_row[f"peak_to_flood_ari{period}"] = fu.safe_ratio(
            event_row.get("peak_discharge"),
            return_ref.get(f"flood_ari{period}"),
        )

    precip_values = {
        1: event_row.get("peak_rain_intensity_6h"),
        6: event_row.get("recent_rain_6h"),
        24: event_row.get("recent_rain_24h"),
        72: event_row.get("recent_rain_72h"),
    }
    for period in return_periods:
        for duration in precip_durations:
            event_row[f"recent_rain_{duration}h_to_prec_ari{period}_{duration}h"] = fu.safe_ratio(
                precip_values.get(duration),
                return_ref.get(f"prec_ari{period}_{duration}h"),
            )

    return event_row


def attach_return_reference_to_summary(summary_row: dict[str, object], return_ref: dict[str, object]) -> dict[str, object]:
    for key, value in return_ref.items():
        if key in {"gauge_id", "gauge_name", "state", "huc02", "area", "drain_sqkm_attr", "snow_fraction"}:
            continue
        summary_row[key] = value
    return summary_row


def process_basin(task: dict[str, Any]) -> tuple[list[dict[str, object]], dict[str, object], dict[str, object] | None]:
    basin = task["basin"]
    gauge_id = basin["gauge_id"]
    return_ref = task["return_ref"]

    try:
        frame = fu.read_timeseries(
            gauge_id,
            timeseries_dir=task["timeseries_dir"],
            timeseries_csv_dir=task["timeseries_csv_dir"],
            variables=("Streamflow", "Rainf", "Tair"),
        )
    except Exception as exc:
        summary = fu.build_basin_event_summary_row(
            basin=basin,
            processing_status="missing_timeseries",
            threshold_label=None,
            threshold_value=None,
            threshold_counts={},
            extracted_events=[],
            streamflow=None,
            min_annual_coverage=task["min_annual_coverage"],
        )
        return [], attach_return_reference_to_summary(summary, return_ref), {
            "gauge_id": gauge_id,
            "reason": type(exc).__name__,
            "detail": str(exc),
        }

    streamflow = pd.to_numeric(frame["Streamflow"], errors="coerce")
    if streamflow.dropna().empty:
        summary = fu.build_basin_event_summary_row(
            basin=basin,
            processing_status="no_valid_streamflow",
            threshold_label=None,
            threshold_value=None,
            threshold_counts={},
            extracted_events=[],
            streamflow=streamflow,
            min_annual_coverage=task["min_annual_coverage"],
        )
        return [], attach_return_reference_to_summary(summary, return_ref), {
            "gauge_id": gauge_id,
            "reason": "no_valid_streamflow",
            "detail": "",
        }

    threshold_label, threshold_value, clusters, threshold_counts = fu.select_threshold(
        streamflow,
        min_event_count=task["min_event_count"],
        separation_hours=task["inter_event_separation_hours"],
    )

    area_candidates = pd.to_numeric(pd.Series([basin.get("drain_sqkm_attr"), basin.get("area")]), errors="coerce").dropna()
    area_sqkm = float(area_candidates.iloc[0]) if not area_candidates.empty and float(area_candidates.iloc[0]) > 0 else pd.NA

    event_rows: list[dict[str, object]] = []
    for event_number, cluster in enumerate(clusters, start=1):
        event_row = fu.build_event_row(
            basin=basin,
            frame=frame,
            cluster=cluster,
            event_number=event_number,
            threshold_label=threshold_label,
            threshold_value=threshold_value,
            area_sqkm=area_sqkm,
        )
        attach_return_ratios(
            event_row,
            return_ref=return_ref,
            return_periods=task["return_periods"],
            precip_durations=task["precip_durations"],
        )
        event_rows.append(event_row)

    summary = fu.build_basin_event_summary_row(
        basin=basin,
        processing_status="ok",
        threshold_label=threshold_label,
        threshold_value=threshold_value,
        threshold_counts=threshold_counts,
        extracted_events=event_rows,
        streamflow=streamflow,
        min_annual_coverage=task["min_annual_coverage"],
    )
    return event_rows, attach_return_reference_to_summary(summary, return_ref), None


def iter_results(tasks: list[dict[str, Any]], workers: int) -> list[tuple[list[dict[str, object]], dict[str, object], dict[str, object] | None]]:
    progress = fu.ProgressReporter(total=len(tasks), label="event-response basins")
    progress.update(0)
    if workers <= 1:
        results = []
        for index, task in enumerate(tasks, start=1):
            results.append(process_basin(task))
            progress.update(index)
        return results

    results = []
    with futures.ProcessPoolExecutor(max_workers=workers) as executor:
        future_to_id = {executor.submit(process_basin, task): task["basin"]["gauge_id"] for task in tasks}
        for index, future in enumerate(futures.as_completed(future_to_id), start=1):
            results.append(future.result())
            progress.update(index)
    return results


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

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
    basins = {row["gauge_id"]: pd.Series(row) for row in metadata.to_dict("records")}
    return_period_df, return_refs = load_return_period_refs(args.return_period_csv, args.no_return_ratios)

    return_periods = infer_return_periods(return_period_df)
    precip_durations = infer_precip_durations(return_period_df)
    tasks = [
        {
            "basin": basins[gauge_id],
            "timeseries_dir": args.timeseries_dir,
            "timeseries_csv_dir": args.timeseries_csv_dir,
            "return_ref": return_refs.get(gauge_id, {}),
            "return_periods": return_periods,
            "precip_durations": precip_durations,
            "min_annual_coverage": args.min_annual_coverage,
            "min_event_count": args.min_event_count,
            "inter_event_separation_hours": args.inter_event_separation_hours,
        }
        for gauge_id in gauge_ids
    ]

    event_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    skipped_rows: list[dict[str, object]] = []
    for events, summary, skipped in iter_results(tasks, workers=args.workers):
        event_rows.extend(events)
        summary_rows.append(summary)
        if skipped is not None:
            skipped_rows.append(skipped)

    ratio_cols = ratio_columns(return_periods, precip_durations) if return_period_df is not None else []
    reference_cols = return_reference_columns(return_period_df)

    events = pd.DataFrame(event_rows)
    event_columns = [*EVENT_BASE_COLUMNS, *ratio_cols]
    if events.empty:
        events = pd.DataFrame(columns=event_columns)
    else:
        extra_cols = [col for col in events.columns if col not in event_columns]
        events = events.reindex(columns=event_columns + extra_cols)
        events = events.sort_values(["gauge_id", "event_peak", "event_id"]).reset_index(drop=True)

    summary = pd.DataFrame(summary_rows)
    summary_columns = [*SUMMARY_BASE_COLUMNS, *reference_cols]
    extra_summary_cols = [col for col in summary.columns if col not in summary_columns]
    summary = summary.reindex(columns=summary_columns + extra_summary_cols).sort_values("gauge_id").reset_index(drop=True)

    skipped = pd.DataFrame(skipped_rows, columns=SKIPPED_COLUMNS)
    if not skipped.empty:
        skipped = skipped.sort_values("gauge_id").reset_index(drop=True)

    events_path = args.output_dir / "event_response_table.csv"
    summary_path = args.output_dir / "event_response_basin_summary.csv"
    skipped_path = args.output_dir / "event_response_skipped_basins.csv"
    json_path = args.output_dir / "event_response_summary.json"

    events.to_csv(events_path, index=False)
    summary.to_csv(summary_path, index=False)
    skipped.to_csv(skipped_path, index=False)

    threshold_usage = summary.loc[summary["processing_status"] == "ok", "selected_threshold_quantile"].value_counts(dropna=True)
    summary_json = {
        "input_basin_count": len(gauge_ids),
        "processed_basin_count": int((summary["processing_status"] == "ok").sum()),
        "skipped_basin_count": int(len(skipped)),
        "total_event_count": int(len(events)),
        "threshold_usage": {str(key): int(value) for key, value in threshold_usage.items()},
        "timeseries_dir": str(args.timeseries_dir),
        "return_period_csv": str(args.return_period_csv) if return_period_df is not None else None,
        "workers": args.workers,
        "outputs": {
            "event_response_table": str(events_path),
            "event_response_basin_summary": str(summary_path),
            "event_response_skipped_basins": str(skipped_path),
        },
    }
    json_path.write_text(json.dumps(json_safe(summary_json), indent=2), encoding="utf-8")

    print(f"Wrote event response table: {events_path}")
    print(f"Wrote basin summary: {summary_path}")
    print(f"Wrote skipped-basin table: {skipped_path}")
    print(f"Wrote summary: {json_path}")


if __name__ == "__main__":
    main()
