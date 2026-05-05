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
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import xarray as xr

LIB_ROOT = Path(__file__).resolve().parents[2] / "_lib"
if str(LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(LIB_ROOT))

import camelsh_flood_analysis_utils as fu


THRESHOLD_LEVELS: list[tuple[str, float]] = [("Q99", 0.99), ("Q98", 0.98), ("Q95", 0.95)]
COLD_SEASON_MONTHS = {11, 12, 1, 2, 3}
INTER_EVENT_SEPARATION_HOURS = 72
MIN_EVENT_COUNT = 5
EVENT_CANDIDATE_LABEL = "observed_high_flow_candidate"
EVENT_DETECTION_BASIS_PREFIX = "observed_streamflow_quantile_threshold"
FLOOD_RELEVANCE_UNRATED = "high_flow_candidate_unrated"
EVENT_COLUMNS = [
    "gauge_id",
    "gauge_name",
    "state",
    "drain_sqkm_attr",
    "selected_threshold_quantile",
    "selected_threshold_value",
    "event_detection_basis",
    "event_candidate_label",
    "flood_relevance_tier",
    "flood_relevance_basis",
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
    *fu.DEGREE_DAY_EVENT_COLUMNS,
    "event_runoff_coefficient",
    "snow_related_flag",
    "rain_on_snow_proxy",
    "api_7d",
    "api_30d",
]
SUMMARY_COLUMNS = [
    "gauge_id",
    "gauge_name",
    "state",
    "drain_sqkm_attr",
    "passes_streamflow_quality_gate",
    "obs_years_usable",
    "processing_status",
    "selected_threshold_quantile",
    "selected_threshold_value",
    "q99_event_count",
    "q98_event_count",
    "q95_event_count",
    "event_count",
    "flood_like_ge_2yr_proxy_event_count",
    "high_flow_below_2yr_proxy_event_count",
    "high_flow_candidate_unrated_event_count",
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


@dataclass(frozen=True)
class PeakCandidate:
    segment_start: pd.Timestamp
    segment_end: pd.Timestamp
    peak_time: pd.Timestamp
    peak_value: float


@dataclass(frozen=True)
class EventCluster:
    first_segment_start: pd.Timestamp
    last_segment_end: pd.Timestamp
    peak_time: pd.Timestamp
    peak_value: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build an observed-flow event response table and basin summary for "
            "the DRBC-selected CAMELSH basins."
        )
    )
    parser.add_argument(
        "--selected-csv",
        type=Path,
        default=Path("output/basin/drbc/basin_define/camelsh_drbc_selected.csv"),
        help="Selected DRBC CAMELSH basin table.",
    )
    parser.add_argument(
        "--quality-csv",
        type=Path,
        default=Path("output/basin/drbc/screening/drbc_streamflow_quality_table.csv"),
        help="Streamflow quality gate table.",
    )
    parser.add_argument(
        "--static-attributes-csv",
        type=Path,
        default=Path("data/CAMELSH_generic/drbc_holdout_broad/attributes/static_attributes.csv"),
        help="Prepared static attribute table used as an area fallback.",
    )
    parser.add_argument(
        "--timeseries-dir",
        type=Path,
        default=Path("data/CAMELSH_generic/drbc_holdout_broad/time_series"),
        help="Directory containing prepared hourly .nc time series files.",
    )
    parser.add_argument(
        "--timeseries-csv-dir",
        type=Path,
        default=Path("data/CAMELSH_generic/drbc_holdout_broad/time_series_csv"),
        help="Optional CSV fallback directory for prepared time series files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/basin/drbc/analysis/event_response"),
        help="DRBC event-response analysis root. Tables and metadata are written under this directory.",
    )
    parser.add_argument(
        "--include-quality-fail",
        action="store_true",
        help="Process all selected basins instead of only the quality-pass subset.",
    )
    parser.add_argument(
        "--gauge-id",
        action="append",
        default=[],
        help="Optional gauge ID filter. Can be passed multiple times.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit for debugging or partial local runs.",
    )
    return parser.parse_args()


def read_csv(path: Path, *, key: str = "gauge_id") -> pd.DataFrame:
    return pd.read_csv(path, dtype={key: str})


def build_basin_table(args: argparse.Namespace) -> pd.DataFrame:
    selected = read_csv(args.selected_csv)
    quality = read_csv(args.quality_csv)
    static = read_csv(args.static_attributes_csv)

    keep_quality = [
        "gauge_id",
        "obs_years_usable",
        "passes_streamflow_quality_gate",
    ]
    keep_static = [
        "gauge_id",
        "area",
        "snow_fraction",
    ]

    basins = (
        selected.merge(quality[keep_quality], on="gauge_id", how="left", validate="one_to_one")
        .merge(static[keep_static], on="gauge_id", how="left", validate="one_to_one")
        .sort_values("gauge_id")
        .reset_index(drop=True)
    )

    basins["passes_streamflow_quality_gate"] = basins["passes_streamflow_quality_gate"].fillna(False)
    basins["obs_years_usable"] = pd.to_numeric(basins["obs_years_usable"], errors="coerce")
    basins["drain_sqkm_attr"] = pd.to_numeric(basins["drain_sqkm_attr"], errors="coerce")
    basins["area"] = pd.to_numeric(basins["area"], errors="coerce")

    if not args.include_quality_fail:
        basins = basins[basins["passes_streamflow_quality_gate"]].copy()

    if args.gauge_id:
        requested = set(args.gauge_id)
        basins = basins[basins["gauge_id"].isin(requested)].copy()

    if args.limit is not None:
        basins = basins.head(args.limit).copy()

    return basins.reset_index(drop=True)


def read_timeseries(
    gauge_id: str,
    *,
    timeseries_dir: Path,
    timeseries_csv_dir: Path,
) -> pd.DataFrame:
    nc_path = timeseries_dir / f"{gauge_id}.nc"
    csv_path = timeseries_csv_dir / f"{gauge_id}.csv"

    if nc_path.exists():
        with xr.open_dataset(nc_path) as ds:
            frame = ds[["Streamflow", "Rainf", "Tair"]].to_dataframe().reset_index()
        frame = frame.rename(columns={"date": "timestamp"})
    elif csv_path.exists():
        frame = pd.read_csv(
            csv_path,
            usecols=["date", "Streamflow", "Rainf", "Tair"],
            parse_dates=["date"],
        ).rename(columns={"date": "timestamp"})
    else:
        raise FileNotFoundError(
            f"Missing prepared time series for gauge {gauge_id}: {nc_path} or {csv_path}"
        )

    frame = frame.sort_values("timestamp").drop_duplicates("timestamp").set_index("timestamp")
    return frame[["Streamflow", "Rainf", "Tair"]]


def water_year(timestamp: pd.Timestamp) -> int:
    return timestamp.year + 1 if timestamp.month >= 10 else timestamp.year


def to_number(value: object) -> float | pd.NA:
    if value is None or pd.isna(value):
        return pd.NA
    return float(value)


def window_sum(series: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> float | pd.NA:
    window = series.loc[start:end]
    if window.empty or window.notna().sum() == 0:
        return pd.NA
    return float(window.sum(min_count=1))


def window_mean(series: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> float | pd.NA:
    window = series.loc[start:end]
    if window.empty or window.notna().sum() == 0:
        return pd.NA
    return float(window.mean())


def window_max(series: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> float | pd.NA:
    window = series.loc[start:end]
    if window.empty or window.notna().sum() == 0:
        return pd.NA
    return float(window.max())


def build_peak_candidates(streamflow: pd.Series, threshold: float) -> list[PeakCandidate]:
    mask = streamflow.notna() & (streamflow > threshold)
    if not bool(mask.any()):
        return []

    starts = streamflow.index[mask & ~mask.shift(1, fill_value=False)]
    ends = streamflow.index[mask & ~mask.shift(-1, fill_value=False)]

    candidates: list[PeakCandidate] = []
    for segment_start, segment_end in zip(starts, ends):
        segment = streamflow.loc[segment_start:segment_end]
        peak_time = segment.idxmax()
        peak_value = float(segment.loc[peak_time])
        candidates.append(
            PeakCandidate(
                segment_start=segment_start,
                segment_end=segment_end,
                peak_time=peak_time,
                peak_value=peak_value,
            )
        )
    return candidates


def cluster_candidates(
    candidates: list[PeakCandidate],
    *,
    separation_hours: int = INTER_EVENT_SEPARATION_HOURS,
) -> list[EventCluster]:
    if not candidates:
        return []

    clusters: list[list[PeakCandidate]] = [[candidates[0]]]
    for candidate in candidates[1:]:
        previous = clusters[-1][-1]
        gap_hours = (candidate.peak_time - previous.peak_time).total_seconds() / 3600
        if gap_hours < separation_hours:
            clusters[-1].append(candidate)
        else:
            clusters.append([candidate])

    merged: list[EventCluster] = []
    for members in clusters:
        representative = max(members, key=lambda item: item.peak_value)
        merged.append(
            EventCluster(
                first_segment_start=members[0].segment_start,
                last_segment_end=members[-1].segment_end,
                peak_time=representative.peak_time,
                peak_value=representative.peak_value,
            )
        )
    return merged


def select_threshold(streamflow: pd.Series) -> tuple[str, float, list[EventCluster], dict[str, int]]:
    valid = streamflow.dropna()
    if valid.empty:
        raise ValueError("Cannot select a threshold from an empty streamflow series.")

    counts: dict[str, int] = {}
    fallback: tuple[str, float, list[EventCluster]] | None = None

    for label, quantile in THRESHOLD_LEVELS:
        threshold = float(valid.quantile(quantile))
        clusters = cluster_candidates(build_peak_candidates(streamflow, threshold))
        counts[label] = len(clusters)
        fallback = (label, threshold, clusters)
        if len(clusters) >= MIN_EVENT_COUNT:
            return label, threshold, clusters, counts

    assert fallback is not None
    return fallback[0], fallback[1], fallback[2], counts


def find_last_below_threshold(
    streamflow: pd.Series,
    reference_time: pd.Timestamp,
    threshold: float,
) -> pd.Timestamp:
    prefix = streamflow.loc[:reference_time].iloc[:-1]
    candidates = prefix[prefix.notna() & (prefix < threshold)]
    if not candidates.empty:
        return candidates.index[-1]
    valid = streamflow.loc[:reference_time].dropna()
    return valid.index[0] if not valid.empty else reference_time


def find_first_below_threshold(
    streamflow: pd.Series,
    reference_time: pd.Timestamp,
    threshold: float,
) -> pd.Timestamp:
    suffix = streamflow.loc[reference_time:].iloc[1:]
    candidates = suffix[suffix.notna() & (suffix < threshold)]
    if not candidates.empty:
        return candidates.index[0]
    valid = streamflow.loc[reference_time:].dropna()
    return valid.index[-1] if not valid.empty else reference_time


def annual_peak_series(streamflow: pd.Series) -> pd.Series:
    valid = streamflow.dropna()
    if valid.empty:
        return pd.Series(dtype=float)
    water_years = pd.Index([water_year(ts) for ts in valid.index], name="water_year")
    return valid.groupby(water_years).max()


def calculate_rbi(streamflow: pd.Series) -> float | pd.NA:
    valid = streamflow.dropna()
    if valid.empty:
        return pd.NA

    deltas = valid.index.to_series().diff().dt.total_seconds().div(3600)
    consecutive = deltas == 1
    numerator = valid.diff().abs()[consecutive].sum(min_count=1)
    denominator = valid.sum(min_count=1)

    if pd.isna(numerator) or pd.isna(denominator) or denominator == 0:
        return pd.NA
    return float(numerator / denominator)


def build_event_row(
    basin: pd.Series,
    frame: pd.DataFrame,
    cluster: EventCluster,
    *,
    event_number: int,
    threshold_label: str,
    threshold_value: float,
    area_sqkm: float | pd.NA,
    degree_day_proxy: pd.DataFrame | None = None,
    degree_day_stats: dict[str, object] | None = None,
) -> dict[str, object]:
    streamflow = frame["Streamflow"]
    rainfall = frame["Rainf"]
    tair = frame["Tair"]

    event_start = find_last_below_threshold(streamflow, cluster.first_segment_start, threshold_value)
    event_end = find_first_below_threshold(streamflow, cluster.last_segment_end, threshold_value)
    peak_time = cluster.peak_time

    rising_time_hours = int((peak_time - event_start).total_seconds() / 3600)
    recession_time_hours = int((event_end - peak_time).total_seconds() / 3600)
    event_duration_hours = int((event_end - event_start).total_seconds() / 3600) + 1

    start_flow = streamflow.loc[event_start]
    area_value = pd.NA
    if not pd.isna(area_sqkm) and float(area_sqkm) > 0:
        area_value = float(area_sqkm)

    unit_area_peak = pd.NA
    if pd.notna(area_value):
        unit_area_peak = float(cluster.peak_value / area_value)

    recent_6h_start = peak_time - pd.Timedelta(hours=5)
    recent_24h_start = peak_time - pd.Timedelta(hours=23)
    recent_72h_start = peak_time - pd.Timedelta(hours=71)
    antecedent_7d_start = peak_time - pd.Timedelta(hours=191)
    antecedent_30d_start = peak_time - pd.Timedelta(hours=743)
    antecedent_end = peak_time - pd.Timedelta(hours=24)

    row = {
        "gauge_id": basin["gauge_id"],
        "gauge_name": basin["gauge_name"],
        "state": basin["state"],
        "drain_sqkm_attr": to_number(basin.get("drain_sqkm_attr")),
        "selected_threshold_quantile": threshold_label,
        "selected_threshold_value": float(threshold_value),
        "event_detection_basis": f"{EVENT_DETECTION_BASIS_PREFIX}_{threshold_label}",
        "event_candidate_label": EVENT_CANDIDATE_LABEL,
        "flood_relevance_tier": FLOOD_RELEVANCE_UNRATED,
        "flood_relevance_basis": "streamflow_quantile_threshold_only",
        "event_id": f"{basin['gauge_id']}_event_{event_number:03d}",
        "event_start": event_start.isoformat(),
        "event_peak": peak_time.isoformat(),
        "event_end": event_end.isoformat(),
        "water_year": water_year(peak_time),
        "peak_month": int(peak_time.month),
        "cold_season_flag": bool(peak_time.month in COLD_SEASON_MONTHS),
        "peak_discharge": float(cluster.peak_value),
        "unit_area_peak": unit_area_peak,
        "rising_time_hours": rising_time_hours,
        "event_duration_hours": event_duration_hours,
        "recession_time_hours": recession_time_hours,
        "rising_rate": float((cluster.peak_value - float(start_flow)) / max(1, rising_time_hours)),
        "recent_rain_6h": window_sum(rainfall, recent_6h_start, peak_time),
        "recent_rain_24h": window_sum(rainfall, recent_24h_start, peak_time),
        "recent_rain_72h": window_sum(rainfall, recent_72h_start, peak_time),
        "antecedent_rain_7d": window_sum(rainfall, antecedent_7d_start, antecedent_end),
        "antecedent_rain_30d": window_sum(rainfall, antecedent_30d_start, antecedent_end),
        "peak_rain_intensity_6h": window_max(rainfall, recent_6h_start, peak_time),
        "event_mean_temp": window_mean(tair, event_start, event_end),
        "antecedent_mean_temp_7d": window_mean(tair, antecedent_7d_start, antecedent_end),
        "peak_temp": to_number(tair.get(peak_time)),
        "event_runoff_coefficient": pd.NA,
        "snow_related_flag": pd.NA,
        "rain_on_snow_proxy": pd.NA,
        "api_7d": pd.NA,
        "api_30d": pd.NA,
    }
    row.update(
        fu.degree_day_event_descriptors(
            peak_time,
            degree_day_proxy=degree_day_proxy,
            degree_day_stats=degree_day_stats,
        )
    )
    return row


def build_basin_summary_row(
    basin: pd.Series,
    *,
    processing_status: str,
    threshold_label: str | None,
    threshold_value: float | None,
    threshold_counts: dict[str, int],
    extracted_events: list[dict[str, object]],
    streamflow: pd.Series | None,
) -> dict[str, object]:
    usable_years = basin.get("obs_years_usable")
    usable_years_value = pd.NA
    if usable_years is not None and not pd.isna(usable_years):
        usable_years_value = float(usable_years)

    base = {
        "gauge_id": basin["gauge_id"],
        "gauge_name": basin["gauge_name"],
        "state": basin["state"],
        "drain_sqkm_attr": to_number(basin.get("drain_sqkm_attr")),
        "passes_streamflow_quality_gate": bool(basin.get("passes_streamflow_quality_gate", False)),
        "obs_years_usable": usable_years_value,
        "processing_status": processing_status,
        "selected_threshold_quantile": threshold_label if threshold_label is not None else pd.NA,
        "selected_threshold_value": float(threshold_value) if threshold_value is not None else pd.NA,
        "q99_event_count": threshold_counts.get("Q99", 0),
        "q98_event_count": threshold_counts.get("Q98", 0),
        "q95_event_count": threshold_counts.get("Q95", 0),
        "event_count": int(len(extracted_events)),
        "flood_like_ge_2yr_proxy_event_count": 0,
        "high_flow_below_2yr_proxy_event_count": 0,
        "high_flow_candidate_unrated_event_count": int(len(extracted_events)),
        "annual_peak_years": 0,
        "unit_area_peak_median": pd.NA,
        "unit_area_peak_p90": pd.NA,
        "q99_event_frequency": pd.NA,
        "rbi": pd.NA,
        "rising_time_median_hours": pd.NA,
        "event_duration_median_hours": pd.NA,
        "event_runoff_coefficient_median": pd.NA,
        "annual_peak_unit_area_median": pd.NA,
        "annual_peak_unit_area_p90": pd.NA,
    }

    if streamflow is None or streamflow.dropna().empty:
        return base

    annual_peaks = annual_peak_series(streamflow)
    base["annual_peak_years"] = int(len(annual_peaks))
    base["rbi"] = calculate_rbi(streamflow)

    denominator = usable_years_value
    if pd.isna(denominator) or denominator <= 0:
        denominator = float(len(annual_peaks)) if len(annual_peaks) > 0 else pd.NA
    if pd.notna(denominator) and denominator > 0:
        base["q99_event_frequency"] = float(threshold_counts.get("Q99", 0) / denominator)

    area_value = pd.to_numeric(pd.Series([basin.get("drain_sqkm_attr"), basin.get("area")]), errors="coerce").dropna()
    if not area_value.empty and len(annual_peaks) > 0:
        annual_unit_area = annual_peaks / float(area_value.iloc[0])
        base["annual_peak_unit_area_median"] = float(annual_unit_area.median())
        base["annual_peak_unit_area_p90"] = float(annual_unit_area.quantile(0.9))

    if extracted_events:
        events = pd.DataFrame(extracted_events)
        base["unit_area_peak_median"] = to_number(events["unit_area_peak"].median())
        base["unit_area_peak_p90"] = to_number(events["unit_area_peak"].quantile(0.9))
        base["rising_time_median_hours"] = to_number(events["rising_time_hours"].median())
        base["event_duration_median_hours"] = to_number(events["event_duration_hours"].median())
        base["event_runoff_coefficient_median"] = to_number(events["event_runoff_coefficient"].median())

    return base


def main() -> None:
    args = parse_args()
    table_dir = args.output_dir / "tables"
    metadata_dir = args.output_dir / "metadata"
    table_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    basins = build_basin_table(args)
    if basins.empty:
        raise ValueError("No basins remain after applying the current filters.")

    event_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    skipped_rows: list[dict[str, object]] = []
    threshold_usage = {label: 0 for label, _ in THRESHOLD_LEVELS}

    for basin in basins.itertuples(index=False):
        basin_series = pd.Series(basin._asdict())
        gauge_id = basin_series["gauge_id"]

        try:
            frame = read_timeseries(
                gauge_id,
                timeseries_dir=args.timeseries_dir,
                timeseries_csv_dir=args.timeseries_csv_dir,
            )
        except FileNotFoundError as exc:
            skipped_rows.append({"gauge_id": gauge_id, "reason": "missing_timeseries", "detail": str(exc)})
            summary_rows.append(
                build_basin_summary_row(
                    basin_series,
                    processing_status="missing_timeseries",
                    threshold_label=None,
                    threshold_value=None,
                    threshold_counts={},
                    extracted_events=[],
                    streamflow=None,
                )
            )
            continue

        streamflow = frame["Streamflow"]
        if streamflow.dropna().empty:
            skipped_rows.append({"gauge_id": gauge_id, "reason": "no_valid_streamflow", "detail": ""})
            summary_rows.append(
                build_basin_summary_row(
                    basin_series,
                    processing_status="no_valid_streamflow",
                    threshold_label=None,
                    threshold_value=None,
                    threshold_counts={},
                    extracted_events=[],
                    streamflow=streamflow,
                )
            )
            continue

        threshold_label, threshold_value, clusters, threshold_counts = select_threshold(streamflow)
        threshold_usage[threshold_label] += 1
        degree_day_proxy, degree_day_stats = fu.build_degree_day_basin_proxy(frame)

        area_candidates = pd.to_numeric(
            pd.Series([basin_series.get("drain_sqkm_attr"), basin_series.get("area")]),
            errors="coerce",
        ).dropna()
        area_sqkm = float(area_candidates.iloc[0]) if not area_candidates.empty else pd.NA

        basin_events: list[dict[str, object]] = []
        for event_number, cluster in enumerate(clusters, start=1):
            event_row = build_event_row(
                basin_series,
                frame,
                cluster,
                event_number=event_number,
                threshold_label=threshold_label,
                threshold_value=threshold_value,
                area_sqkm=area_sqkm,
                degree_day_proxy=degree_day_proxy,
                degree_day_stats=degree_day_stats,
            )
            basin_events.append(event_row)
            event_rows.append(event_row)

        summary_rows.append(
            build_basin_summary_row(
                basin_series,
                processing_status="ok",
                threshold_label=threshold_label,
                threshold_value=threshold_value,
                threshold_counts=threshold_counts,
                extracted_events=basin_events,
                streamflow=streamflow,
            )
        )

    events = pd.DataFrame(event_rows, columns=EVENT_COLUMNS)
    summary = pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS).sort_values("gauge_id").reset_index(drop=True)
    skipped = pd.DataFrame(skipped_rows, columns=SKIPPED_COLUMNS)
    if not skipped.empty:
        skipped = skipped.sort_values("gauge_id").reset_index(drop=True)

    if not events.empty:
        events = events.sort_values(["gauge_id", "event_peak", "event_id"]).reset_index(drop=True)

    events_path = table_dir / "event_response_table.csv"
    summary_path = table_dir / "event_response_basin_summary.csv"
    skipped_path = table_dir / "event_response_skipped_basins.csv"
    json_path = metadata_dir / "event_response_summary.json"

    events.to_csv(events_path, index=False)
    summary.to_csv(summary_path, index=False)
    skipped.to_csv(skipped_path, index=False)

    summary_json = {
        "input_basin_count": int(len(basins)),
        "quality_pass_only": bool(not args.include_quality_fail),
        "processed_basin_count": int((summary["processing_status"] == "ok").sum()),
        "missing_timeseries_count": int((summary["processing_status"] == "missing_timeseries").sum()),
        "no_valid_streamflow_count": int((summary["processing_status"] == "no_valid_streamflow").sum()),
        "total_event_count": int(len(events)),
        "threshold_usage": threshold_usage,
        "degree_day_tcrit_c": fu.DEGREE_DAY_TCRIT_C,
        "degree_day_factor_mm_per_day_c": fu.DEGREE_DAY_FACTOR_MM_PER_DAY_C,
        "degree_day_snow_window_days": fu.DEGREE_DAY_SNOW_WINDOW_DAYS,
        "snowmelt_min_mm": fu.SNOWMELT_MIN_MM,
        "snowmelt_min_valid_window_count": fu.SNOWMELT_MIN_VALID_WINDOW_COUNT,
        "output_files": {
            "event_response_table": str(events_path),
            "event_response_basin_summary": str(summary_path),
            "event_response_skipped_basins": str(skipped_path),
        },
    }
    json_path.write_text(json.dumps(summary_json, indent=2))

    print(f"Wrote event response table: {events_path}")
    print(f"Wrote basin summary: {summary_path}")
    print(f"Wrote skipped-basin table: {skipped_path}")
    print(f"Wrote summary: {json_path}")
    print(json.dumps(summary_json, indent=2))


if __name__ == "__main__":
    main()
