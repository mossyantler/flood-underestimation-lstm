#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "xarray>=2024.1",
#   "netCDF4>=1.6",
# ]
# ///

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr


DEFAULT_DATA_DIR = Path("data/CAMELSH_generic/drbc_holdout_broad/time_series")
DEFAULT_SPLIT_DIR = Path("configs/pilot/basin_splits/scaling_300")
DEFAULT_RETURN_PERIOD_CSV = Path("output/basin/all/analysis/return_period/tables/return_period_reference_table.csv")
DEFAULT_OUTPUT_DIR = Path("output/model_analysis/extreme_rain/primary/exposure")

PRECIP_DURATIONS = (1, 6, 24, 72)
PRECIP_PERIODS = (25, 50, 100)
FLOOD_PERIODS = (2, 25, 50, 100)

SPLIT_DEFINITIONS = {
    "train": ("train.txt", "2000-01-01", "2010-12-31"),
    "validation": ("validation.txt", "2011-01-01", "2013-12-31"),
    "official_test": ("test.txt", "2014-01-01", "2016-12-31"),
    "drbc_historical_stress": ("test.txt", "1980-01-01", "2024-12-31"),
}


@dataclass(frozen=True)
class SplitDefinition:
    name: str
    basin_file: Path
    start: pd.Timestamp
    end: pd.Timestamp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build direct precipitation-based extreme-rain cohorts for subset300 exposure "
            "and DRBC historical stress-test inference."
        )
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--split-dir", type=Path, default=DEFAULT_SPLIT_DIR)
    parser.add_argument("--return-period-csv", type=Path, default=DEFAULT_RETURN_PERIOD_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--rain-coverage-min", type=float, default=0.95)
    parser.add_argument("--streamflow-coverage-min", type=float, default=0.90)
    parser.add_argument("--min-prec-record-years", type=int, default=20)
    parser.add_argument("--event-gap-hours", type=int, default=72)
    parser.add_argument("--response-pre-hours", type=int, default=24)
    parser.add_argument("--response-post-hours", type=int, default=168)
    parser.add_argument("--inference-warmup-days", type=int, default=21)
    parser.add_argument("--inference-post-days", type=int, default=8)
    parser.add_argument("--block-merge-gap-days", type=int, default=7)
    parser.add_argument("--near-ari100-ratio", type=float, default=0.80)
    parser.add_argument("--limit-basins", type=int, default=None, help="Optional per-split basin limit for smoke tests.")
    parser.add_argument(
        "--splits",
        nargs="+",
        choices=sorted(SPLIT_DEFINITIONS),
        default=sorted(SPLIT_DEFINITIONS),
        help="Split definitions to process.",
    )
    return parser.parse_args()


def normalize_gauge_id(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(8)


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer, np.floating)):
        if pd.isna(value):
            return None
        return value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if pd.isna(value):
        return None
    return value


def read_basin_file(path: Path) -> list[str]:
    return [normalize_gauge_id(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_split_definitions(split_dir: Path, names: list[str]) -> list[SplitDefinition]:
    definitions = []
    for name in names:
        file_name, start, end = SPLIT_DEFINITIONS[name]
        basin_file = split_dir / file_name
        if not basin_file.exists():
            raise FileNotFoundError(f"Missing split basin file: {basin_file}")
        definitions.append(
            SplitDefinition(
                name=name,
                basin_file=basin_file,
                start=pd.Timestamp(start),
                end=pd.Timestamp(end) + pd.Timedelta(hours=23),
            )
        )
    return definitions


def load_return_periods(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing return-period reference CSV: {path}")
    refs = pd.read_csv(path, dtype={"gauge_id": str})
    refs["gauge_id"] = refs["gauge_id"].map(normalize_gauge_id)
    return refs.set_index("gauge_id", drop=False)


def finite_ratio(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0
    return float(series.notna().mean())


def safe_float(value: Any) -> float:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return float(numeric) if pd.notna(numeric) else math.nan


def valid_reference(ref: pd.Series, min_prec_record_years: int) -> tuple[bool, str]:
    missing = []
    low_record = []
    for period in PRECIP_PERIODS:
        for duration in PRECIP_DURATIONS:
            value = safe_float(ref.get(f"prec_ari{period}_{duration}h"))
            if not np.isfinite(value) or value <= 0:
                missing.append(f"prec_ari{period}_{duration}h")
    for duration in PRECIP_DURATIONS:
        years = safe_float(ref.get(f"prec_record_years_{duration}h"))
        if not np.isfinite(years) or years < min_prec_record_years:
            low_record.append(f"prec_record_years_{duration}h")
    if missing:
        return False, "missing_or_invalid_precip_reference:" + ",".join(missing)
    if low_record:
        return True, "low_prec_record:" + ",".join(low_record)
    return True, "ok"


def rolling_ratio_frame(rain: pd.Series, ref: pd.Series) -> tuple[pd.DataFrame, dict[int, dict[int, pd.Series]]]:
    ratio_by_period_duration: dict[int, dict[int, pd.Series]] = {period: {} for period in PRECIP_PERIODS}
    out = pd.DataFrame(index=rain.index)
    for period in PRECIP_PERIODS:
        duration_ratios = []
        for duration in PRECIP_DURATIONS:
            threshold = safe_float(ref.get(f"prec_ari{period}_{duration}h"))
            rolling = rain.rolling(window=duration, min_periods=duration).sum()
            ratio = rolling / threshold
            ratio_by_period_duration[period][duration] = ratio
            duration_ratios.append(ratio.rename(str(duration)))
        ratios = pd.concat(duration_ratios, axis=1)
        out[f"max_prec_ari{period}_ratio"] = ratios.max(axis=1, skipna=True)
        out[f"dominant_duration_for_ari{period}h"] = pd.to_numeric(ratios.idxmax(axis=1), errors="coerce")
    return out, ratio_by_period_duration


def iter_active_events(active: pd.Series, gap_hours: int) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    times = list(pd.to_datetime(active.index[active.fillna(False)]))
    if not times:
        return []
    events: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    start = previous = times[0]
    for time in times[1:]:
        gap = (time - previous).total_seconds() / 3600.0
        if gap <= gap_hours:
            previous = time
            continue
        events.append((start, previous))
        start = previous = time
    events.append((start, previous))
    return events


def water_year(timestamp: pd.Timestamp) -> int:
    return int(timestamp.year + 1 if timestamp.month >= 10 else timestamp.year)


def rain_cohort(row: dict[str, Any], near_ari100_ratio: float) -> str:
    if row["max_prec_ari100_ratio"] >= 1.0:
        return "prec_ge100"
    if row["max_prec_ari50_ratio"] >= 1.0:
        return "prec_ge50"
    if row["max_prec_ari25_ratio"] >= 1.0:
        return "prec_ge25"
    if row["max_prec_ari100_ratio"] >= near_ari100_ratio:
        return "near_prec100"
    return "not_selected"


def response_class(obs_peak: float, q99: float, ratios: dict[int, float]) -> str:
    if not np.isfinite(obs_peak):
        return "response_unrated_coverage"
    if ratios.get(25, math.nan) >= 1.0:
        return "flood_response_ge25"
    if ratios.get(2, math.nan) >= 1.0:
        return "flood_response_ge2_to_lt25"
    if np.isfinite(q99) and obs_peak >= q99:
        return "high_flow_non_flood_q99_only"
    return "low_response_below_q99"


def temporal_relation(split_name: str, peak: pd.Timestamp) -> str:
    if split_name != "drbc_historical_stress":
        return split_name
    if pd.Timestamp("2000-01-01") <= peak <= pd.Timestamp("2010-12-31 23:00"):
        return "overlaps_train_period"
    if pd.Timestamp("2011-01-01") <= peak <= pd.Timestamp("2013-12-31 23:00"):
        return "overlaps_validation_period"
    if pd.Timestamp("2014-01-01") <= peak <= pd.Timestamp("2016-12-31 23:00"):
        return "overlaps_official_test_period"
    return "outside_official_split_periods"


def summarize_response(
    *,
    streamflow: pd.Series,
    ref: pd.Series,
    response_start: pd.Timestamp,
    response_end: pd.Timestamp,
    streamflow_coverage_min: float,
) -> dict[str, Any]:
    response = streamflow.loc[response_start:response_end]
    coverage = finite_ratio(response)
    all_flow = streamflow.dropna()
    q99 = float(all_flow.quantile(0.99)) if len(all_flow) else math.nan
    row: dict[str, Any] = {
        "response_window_start": response_start,
        "response_window_end": response_end,
        "response_window_n_hours": int(len(response)),
        "streamflow_response_coverage": coverage,
        "streamflow_q99_threshold": q99,
    }
    if coverage < streamflow_coverage_min or response.dropna().empty:
        row.update(
            {
                "observed_response_peak": math.nan,
                "observed_response_peak_time": pd.NaT,
                "response_lag_hours": math.nan,
                "response_class": "response_unrated_coverage",
                "response_skipped_reason": "streamflow_response_coverage_below_min",
            }
        )
        for period in FLOOD_PERIODS:
            row[f"obs_peak_to_flood_ari{period}"] = math.nan
        return row

    peak_time = pd.Timestamp(response.idxmax())
    peak = float(response.loc[peak_time])
    ratios = {}
    for period in FLOOD_PERIODS:
        ratio = peak / safe_float(ref.get(f"flood_ari{period}"))
        ratios[period] = ratio if np.isfinite(ratio) else math.nan
        row[f"obs_peak_to_flood_ari{period}"] = ratios[period]

    row.update(
        {
            "observed_response_peak": peak,
            "observed_response_peak_time": peak_time,
            "response_lag_hours": math.nan,
            "response_class": response_class(peak, q99, ratios),
            "response_skipped_reason": "",
        }
    )
    return row


def build_events_for_basin(
    *,
    split: SplitDefinition,
    basin: str,
    data_dir: Path,
    ref: pd.Series,
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    path = data_dir / f"{basin}.nc"
    if not path.exists():
        return [], [{"split": split.name, "gauge_id": basin, "skipped_reason": "missing_timeseries_file"}]

    reference_ok, reference_flag = valid_reference(ref, args.min_prec_record_years)
    if not reference_ok:
        return [], [{"split": split.name, "gauge_id": basin, "skipped_reason": reference_flag}]

    with xr.open_dataset(path) as ds:
        if "Rainf" not in ds or "Streamflow" not in ds:
            return [], [{"split": split.name, "gauge_id": basin, "skipped_reason": "missing_required_variables"}]
        rain = ds["Rainf"].sel(date=slice(split.start, split.end)).to_pandas().astype(float)
        streamflow = ds["Streamflow"].to_pandas().astype(float)

    rain_coverage = finite_ratio(rain)
    if rain_coverage < args.rain_coverage_min:
        return [], [
            {
                "split": split.name,
                "gauge_id": basin,
                "skipped_reason": "rain_coverage_below_min",
                "rain_coverage": rain_coverage,
            }
        ]

    ratio_frame, ratio_by_period_duration = rolling_ratio_frame(rain, ref)
    active = (ratio_frame["max_prec_ari25_ratio"] >= 1.0) | (
        ratio_frame["max_prec_ari100_ratio"] >= args.near_ari100_ratio
    )
    active_events = iter_active_events(active, args.event_gap_hours)
    rows: list[dict[str, Any]] = []
    skips: list[dict[str, Any]] = []

    for event_index, (event_start, event_end) in enumerate(active_events, start=1):
        event_slice = ratio_frame.loc[event_start:event_end]
        if event_slice.empty:
            continue
        peak_metric = event_slice["max_prec_ari100_ratio"]
        if peak_metric.notna().any():
            rain_peak = pd.Timestamp(peak_metric.idxmax())
        else:
            rain_peak = pd.Timestamp(event_slice["max_prec_ari25_ratio"].idxmax())

        row: dict[str, Any] = {
            "split": split.name,
            "gauge_id": basin,
            "event_id": f"{basin}_rain_{split.name}_{event_index:04d}",
            "rain_start": event_start,
            "rain_peak": rain_peak,
            "rain_end": event_end,
            "water_year": water_year(rain_peak),
            "peak_month": int(rain_peak.month),
            "rain_event_n_hours": int(len(event_slice)),
            "rain_coverage": rain_coverage,
            "precip_reference_flag": reference_flag,
            "return_period_confidence_flag": ref.get("return_period_confidence_flag", pd.NA),
            "flood_record_years": ref.get("flood_record_years", pd.NA),
            "return_period_record_years": ref.get("return_period_record_years", pd.NA),
            "temporal_relation": temporal_relation(split.name, rain_peak),
        }
        for period in PRECIP_PERIODS:
            ratio_col = f"max_prec_ari{period}_ratio"
            duration_col = f"dominant_duration_for_ari{period}h"
            peak_ratio = float(event_slice[ratio_col].max(skipna=True))
            peak_time = pd.Timestamp(event_slice[ratio_col].idxmax())
            row[ratio_col] = peak_ratio
            row[f"peak_time_for_ari{period}_ratio"] = peak_time
            row[duration_col] = event_slice.loc[peak_time, duration_col]
            for duration in PRECIP_DURATIONS:
                duration_ratio = ratio_by_period_duration[period][duration].loc[event_start:event_end]
                row[f"max_prec_ari{period}_{duration}h_ratio"] = float(duration_ratio.max(skipna=True))

        row["rain_cohort"] = rain_cohort(row, args.near_ari100_ratio)
        if row["rain_cohort"] == "not_selected":
            continue

        response_start = event_start - pd.Timedelta(hours=args.response_pre_hours)
        response_end = event_end + pd.Timedelta(hours=args.response_post_hours)
        response_row = summarize_response(
            streamflow=streamflow,
            ref=ref,
            response_start=response_start,
            response_end=response_end,
            streamflow_coverage_min=args.streamflow_coverage_min,
        )
        if pd.notna(response_row.get("observed_response_peak_time")):
            response_row["response_lag_hours"] = (
                pd.Timestamp(response_row["observed_response_peak_time"]) - rain_peak
            ).total_seconds() / 3600.0
        row.update(response_row)
        for period in FLOOD_PERIODS:
            row[f"flood_ari{period}"] = safe_float(ref.get(f"flood_ari{period}"))
        rows.append(row)

        if response_row.get("response_skipped_reason"):
            skips.append(
                {
                    "split": split.name,
                    "gauge_id": basin,
                    "event_id": row["event_id"],
                    "skipped_reason": response_row["response_skipped_reason"],
                    "streamflow_response_coverage": response_row["streamflow_response_coverage"],
                }
            )

    return rows, skips


def assign_storm_groups(events: pd.DataFrame, gap_hours: int) -> pd.DataFrame:
    if events.empty:
        events["storm_group_id"] = pd.Series(dtype=str)
        return events
    out = events.sort_values(["split", "rain_peak", "gauge_id"]).copy()
    group_ids = pd.Series(index=out.index, dtype=object)
    for split, group in out.groupby("split", sort=False):
        current_group = 0
        previous_peak: pd.Timestamp | None = None
        for idx, row in group.iterrows():
            peak = pd.Timestamp(row["rain_peak"])
            if previous_peak is None or (peak - previous_peak).total_seconds() / 3600.0 > gap_hours:
                current_group += 1
            group_ids.loc[idx] = f"{split}_storm_{current_group:04d}"
            previous_peak = peak
    out["storm_group_id"] = group_ids
    return out.sort_values(["split", "gauge_id", "rain_start"]).reset_index(drop=True)


def build_inference_blocks(
    events: pd.DataFrame,
    *,
    warmup_days: int,
    post_days: int,
    merge_gap_days: int,
) -> pd.DataFrame:
    stress = events[
        events["split"].eq("drbc_historical_stress")
        & ~events["response_class"].eq("response_unrated_coverage")
    ].copy()
    if stress.empty:
        return pd.DataFrame(
            columns=[
                "gauge_id",
                "block_id",
                "block_start",
                "block_end",
                "n_events",
                "event_ids",
                "rain_cohorts",
                "response_classes",
            ]
        )
    stress["candidate_block_start"] = pd.to_datetime(stress["rain_start"]) - pd.Timedelta(days=warmup_days)
    stress["candidate_block_end"] = pd.to_datetime(stress["rain_end"]) + pd.Timedelta(days=post_days)
    rows: list[dict[str, Any]] = []
    for basin, group in stress.sort_values(["gauge_id", "candidate_block_start"]).groupby("gauge_id"):
        block_start: pd.Timestamp | None = None
        block_end: pd.Timestamp | None = None
        block_events: list[pd.Series] = []
        block_index = 0
        for _, row in group.iterrows():
            start = pd.Timestamp(row["candidate_block_start"]).floor("D")
            end = pd.Timestamp(row["candidate_block_end"]).ceil("D") - pd.Timedelta(hours=1)
            if block_start is None:
                block_start, block_end = start, end
                block_events = [row]
                continue
            assert block_end is not None
            if start <= block_end + pd.Timedelta(days=merge_gap_days):
                block_end = max(block_end, end)
                block_events.append(row)
                continue
            block_index += 1
            rows.append(render_block_row(basin, block_index, block_start, block_end, block_events))
            block_start, block_end = start, end
            block_events = [row]
        if block_start is not None and block_end is not None:
            block_index += 1
            rows.append(render_block_row(basin, block_index, block_start, block_end, block_events))
    return pd.DataFrame(rows)


def render_block_row(
    basin: str,
    block_index: int,
    block_start: pd.Timestamp,
    block_end: pd.Timestamp,
    events: list[pd.Series],
) -> dict[str, Any]:
    return {
        "gauge_id": basin,
        "block_id": f"{basin}_block_{block_index:03d}",
        "block_start": block_start,
        "block_end": block_end,
        "n_events": len(events),
        "event_ids": ";".join(str(row["event_id"]) for row in events),
        "rain_cohorts": ";".join(sorted({str(row["rain_cohort"]) for row in events})),
        "response_classes": ";".join(sorted({str(row["response_class"]) for row in events})),
    }


def exposure_summary(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    rows = []
    for split, group in events.groupby("split", dropna=False):
        row: dict[str, Any] = {
            "split": split,
            "n_events": int(len(group)),
            "n_basins": int(group["gauge_id"].nunique()),
            "n_storm_groups": int(group["storm_group_id"].nunique()) if "storm_group_id" in group else 0,
            "prec_ge25_event_count": int((group["max_prec_ari25_ratio"] >= 1.0).sum()),
            "prec_ge50_event_count": int((group["max_prec_ari50_ratio"] >= 1.0).sum()),
            "prec_ge100_event_count": int((group["max_prec_ari100_ratio"] >= 1.0).sum()),
            "near_prec100_event_count": int(
                ((group["max_prec_ari100_ratio"] >= 0.8) & (group["max_prec_ari100_ratio"] < 1.0)).sum()
            ),
            "positive_response_event_count": int(
                group["response_class"].isin(["flood_response_ge25", "flood_response_ge2_to_lt25"]).sum()
            ),
            "negative_control_event_count": int(
                group["response_class"].isin(["high_flow_non_flood_q99_only", "low_response_below_q99"]).sum()
            ),
            "median_max_prec_ari100_ratio": float(group["max_prec_ari100_ratio"].median()),
            "max_max_prec_ari100_ratio": float(group["max_prec_ari100_ratio"].max()),
        }
        rows.append(row)
    return pd.DataFrame(rows).sort_values("split")


def main() -> int:
    args = parse_args()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    refs = load_return_periods(args.return_period_csv)
    split_defs = build_split_definitions(args.split_dir, args.splits)
    event_rows: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []
    processed_manifest: list[dict[str, Any]] = []

    for split in split_defs:
        basins = read_basin_file(split.basin_file)
        if args.limit_basins is not None:
            basins = basins[: args.limit_basins]
        print(f"Processing split {split.name}: {len(basins)} basins ({split.start} to {split.end})", flush=True)
        for idx, basin in enumerate(basins, start=1):
            if basin not in refs.index:
                skipped_rows.append({"split": split.name, "gauge_id": basin, "skipped_reason": "missing_reference"})
                continue
            if idx % 25 == 0 or idx == 1 or idx == len(basins):
                print(f"  basin {idx}/{len(basins)}: {basin}", flush=True)
            rows, skips = build_events_for_basin(split=split, basin=basin, data_dir=args.data_dir, ref=refs.loc[basin], args=args)
            event_rows.extend(rows)
            skipped_rows.extend(skips)
            processed_manifest.append({"split": split.name, "gauge_id": basin, "event_count": len(rows)})

    events = pd.DataFrame(event_rows)
    if not events.empty:
        events = assign_storm_groups(events, args.event_gap_hours)
    skipped = pd.DataFrame(skipped_rows)
    manifest = pd.DataFrame(processed_manifest)
    blocks = build_inference_blocks(
        events,
        warmup_days=args.inference_warmup_days,
        post_days=args.inference_post_days,
        merge_gap_days=args.block_merge_gap_days,
    )
    summary = exposure_summary(events)

    catalog_path = output_dir / "extreme_rain_event_catalog.csv"
    stress_path = output_dir / "drbc_historical_stress_cohort.csv"
    blocks_path = output_dir / "inference_blocks.csv"
    summary_path = output_dir / "exposure_summary_by_split.csv"
    skipped_path = output_dir / "coverage_failure_report.csv"
    manifest_path = output_dir / "processed_basin_manifest.csv"

    events.to_csv(catalog_path, index=False)
    if events.empty:
        events.to_csv(stress_path, index=False)
    else:
        stress_events = events[
            events["split"].eq("drbc_historical_stress")
            & ~events["response_class"].eq("response_unrated_coverage")
        ].copy()
        stress_events.to_csv(stress_path, index=False)
    blocks.to_csv(blocks_path, index=False)
    summary.to_csv(summary_path, index=False)
    skipped.to_csv(skipped_path, index=False)
    manifest.to_csv(manifest_path, index=False)

    summary_json = {
        "data_dir": str(args.data_dir),
        "return_period_csv": str(args.return_period_csv),
        "split_dir": str(args.split_dir),
        "output_dir": str(output_dir),
        "rain_coverage_min": args.rain_coverage_min,
        "streamflow_coverage_min": args.streamflow_coverage_min,
        "min_prec_record_years": args.min_prec_record_years,
        "event_gap_hours": args.event_gap_hours,
        "event_count": int(len(events)),
        "skipped_count": int(len(skipped)),
        "inference_block_count": int(len(blocks)),
        "event_counts_by_split": events["split"].value_counts().to_dict() if not events.empty else {},
        "rain_cohort_counts": events["rain_cohort"].value_counts().to_dict() if not events.empty else {},
        "response_class_counts": events["response_class"].value_counts().to_dict() if not events.empty else {},
        "outputs": {
            "extreme_rain_event_catalog": str(catalog_path),
            "drbc_historical_stress_cohort": str(stress_path),
            "inference_blocks": str(blocks_path),
            "exposure_summary_by_split": str(summary_path),
            "coverage_failure_report": str(skipped_path),
            "processed_basin_manifest": str(manifest_path),
        },
    }
    (output_dir / "analysis_summary.json").write_text(json.dumps(json_safe(summary_json), indent=2), encoding="utf-8")

    print(f"Wrote event catalog: {catalog_path}")
    print(f"Wrote inference blocks: {blocks_path}")
    print(f"Wrote exposure summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
