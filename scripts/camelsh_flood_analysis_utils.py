from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
import time
from typing import Iterable

import numpy as np
import pandas as pd
import xarray as xr
from scipy import stats


RETURN_PERIODS = (2, 5, 10, 25, 50, 100)
PRECIP_DURATIONS_HOURS = (1, 6, 24, 72)
THRESHOLD_LEVELS = (("Q99", 0.99), ("Q98", 0.98), ("Q95", 0.95))
COLD_SEASON_MONTHS = {11, 12, 1, 2, 3}
INTER_EVENT_SEPARATION_HOURS = 72
MIN_EVENT_COUNT = 5
EVENT_CANDIDATE_LABEL = "observed_high_flow_candidate"
EVENT_DETECTION_BASIS_PREFIX = "observed_streamflow_quantile_threshold"
FLOOD_RELEVANCE_UNRATED = "high_flow_candidate_unrated"
FLOOD_RELEVANCE_BELOW_2YR = "high_flow_below_2yr_proxy"
DEGREE_DAY_TCRIT_C = 1.0
DEGREE_DAY_FACTOR_MM_PER_DAY_C = 2.0
DEGREE_DAY_SNOW_WINDOW_DAYS = 7
SNOWMELT_MIN_MM = 1.0
SNOWMELT_MIN_VALID_WINDOW_COUNT = 10
RAIN_SNOWMELT_MIN_FRACTION = 1.0 / 3.0
PRECIP_THRESHOLD_QUANTILE = 0.9
PRECIP_THRESHOLD_MIN_VALID_WINDOW_COUNT = 10

FLOOD_TYPES = (
    "recent_precipitation",
    "antecedent_precipitation",
    "snowmelt_or_rain_on_snow",
    "uncertain_high_flow_candidate",
)

DEGREE_DAY_EVENT_COLUMNS = (
    "degree_day_rain_7d",
    "degree_day_snowmelt_7d",
    "degree_day_water_input_7d",
    "degree_day_snowmelt_fraction_7d",
    "degree_day_rain_fraction_7d",
    "basin_snowmelt_7d_p90",
    "basin_snowmelt_valid_window_count",
    "basin_rain_1d_p90",
    "basin_rain_3d_p90",
    "basin_rain_7d_p90",
    "basin_rain_30d_p90",
)


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


def normalize_gauge_id(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def read_id_file(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def discover_gauge_ids(
    *,
    timeseries_dir: Path,
    timeseries_csv_dir: Path | None = None,
    basin_list: Path | None = None,
    gauge_ids: Iterable[str] | None = None,
    limit: int | None = None,
) -> list[str]:
    ids: set[str] = set()
    if basin_list is not None:
        ids.update(read_id_file(basin_list))
    if gauge_ids:
        ids.update(normalize_gauge_id(item) for item in gauge_ids)
    if not ids:
        ids.update(path.stem for path in timeseries_dir.glob("*.nc"))
        if timeseries_csv_dir is not None and timeseries_csv_dir.exists():
            ids.update(path.stem for path in timeseries_csv_dir.glob("*.csv"))

    ordered = sorted(item for item in ids if item)
    if limit is not None:
        ordered = ordered[:limit]
    return ordered


def detect_time_coord(ds: xr.Dataset) -> str:
    for name in ("date", "time", "DateTime"):
        if name in ds.coords or name in ds.dims:
            return name
    for name, coord in ds.coords.items():
        if np.issubdtype(coord.dtype, np.datetime64):
            return name
    raise ValueError("No datetime coordinate found in NetCDF dataset.")


def read_timeseries(
    gauge_id: str,
    *,
    timeseries_dir: Path,
    timeseries_csv_dir: Path | None = None,
    variables: Iterable[str] = ("Streamflow", "Rainf", "Tair"),
) -> pd.DataFrame:
    nc_path = timeseries_dir / f"{gauge_id}.nc"
    csv_path = timeseries_csv_dir / f"{gauge_id}.csv" if timeseries_csv_dir is not None else None
    requested = list(variables)

    if nc_path.exists():
        with xr.open_dataset(nc_path) as ds:
            time_coord = detect_time_coord(ds)
            available = [name for name in requested if name in ds.data_vars]
            missing = [name for name in requested if name not in ds.data_vars]
            if not available:
                raise ValueError(f"No requested variables found in {nc_path}: {requested}")
            frame = ds[available].to_dataframe().reset_index()
        frame = frame.rename(columns={time_coord: "timestamp"})
        for name in missing:
            frame[name] = pd.NA
    elif csv_path is not None and csv_path.exists():
        header = pd.read_csv(csv_path, nrows=0)
        time_col = "date" if "date" in header.columns else "timestamp"
        usecols = [time_col, *[name for name in requested if name in header.columns]]
        frame = pd.read_csv(csv_path, usecols=usecols, parse_dates=[time_col])
        frame = frame.rename(columns={time_col: "timestamp"})
        for name in requested:
            if name not in frame.columns:
                frame[name] = pd.NA
    else:
        raise FileNotFoundError(f"Missing time series for gauge {gauge_id}: {nc_path}")

    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    frame = frame.sort_values("timestamp").drop_duplicates("timestamp").set_index("timestamp")
    return frame[requested]


def normalize_metadata_frame(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str)
    rename_map = {
        "STAID": "gauge_id",
        "GAGE_ID": "gauge_id",
        "GAGEID": "gauge_id",
        "STANAME": "gauge_name",
        "STATE": "state",
        "HUC02": "huc02",
        "camelsh_huc02": "huc02",
        "DRAIN_SQKM": "drain_sqkm_attr",
        "frac_snow": "snow_fraction",
    }
    df = df.rename(columns={key: value for key, value in rename_map.items() if key in df.columns})
    if "gauge_id" not in df.columns:
        raise ValueError(f"Metadata file has no gauge ID column: {path}")

    df["gauge_id"] = df["gauge_id"].map(normalize_gauge_id)
    df = df[df["gauge_id"] != ""].drop_duplicates("gauge_id").copy()

    numeric_cols = [
        "area",
        "drain_sqkm_attr",
        "snow_fraction",
        "slope",
        "aridity",
        "soil_depth",
        "permeability",
        "forest_fraction",
        "baseflow_index",
        "obs_years_usable",
        "actual_valid_target_count",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_basin_metadata(gauge_ids: Iterable[str], metadata_paths: Iterable[Path]) -> pd.DataFrame:
    base = pd.DataFrame({"gauge_id": [normalize_gauge_id(item) for item in gauge_ids]})
    base = base[base["gauge_id"] != ""].drop_duplicates("gauge_id").sort_values("gauge_id")

    for path in metadata_paths:
        if not path.exists():
            continue
        incoming = normalize_metadata_frame(path)
        base = base.merge(incoming, on="gauge_id", how="left", suffixes=("", "__incoming"))
        incoming_cols = [col for col in base.columns if col.endswith("__incoming")]
        for incoming_col in incoming_cols:
            target_col = incoming_col.removesuffix("__incoming")
            if target_col in base.columns:
                base[target_col] = base[target_col].combine_first(base[incoming_col])
            else:
                base[target_col] = base[incoming_col]
            base = base.drop(columns=[incoming_col])

    for col in ["gauge_name", "state", "huc02", "area", "drain_sqkm_attr", "snow_fraction", "obs_years_usable"]:
        if col not in base.columns:
            base[col] = pd.NA

    for col in ["area", "drain_sqkm_attr", "snow_fraction", "obs_years_usable"]:
        base[col] = pd.to_numeric(base[col], errors="coerce")

    return base.sort_values("gauge_id").reset_index(drop=True)


def to_float(value: object) -> float | pd.NA:
    if value is None or pd.isna(value):
        return pd.NA
    return float(value)


def water_year(timestamp: pd.Timestamp) -> int:
    return int(timestamp.year + 1 if timestamp.month >= 10 else timestamp.year)


def expected_water_year_hours(water_year_value: int) -> int:
    start = pd.Timestamp(year=int(water_year_value) - 1, month=10, day=1)
    end = pd.Timestamp(year=int(water_year_value), month=10, day=1)
    return int((end - start).total_seconds() // 3600)


def series_water_years(index: pd.DatetimeIndex) -> pd.Index:
    return pd.Index([water_year(ts) for ts in index], name="water_year")


def annual_maxima_with_coverage(series: pd.Series, min_annual_coverage: float) -> pd.DataFrame:
    valid_series = pd.to_numeric(series, errors="coerce")
    if valid_series.empty:
        return pd.DataFrame(
            columns=["water_year", "annual_max", "valid_count", "expected_hours", "annual_coverage"]
        )

    water_year_index = series_water_years(pd.DatetimeIndex(valid_series.index))
    grouped = valid_series.groupby(water_year_index)
    maxima = grouped.max()
    valid_counts = grouped.count()
    rows = []
    for wy, annual_max in maxima.items():
        expected = expected_water_year_hours(int(wy))
        valid_count = int(valid_counts.loc[wy])
        coverage = valid_count / expected if expected > 0 else np.nan
        if valid_count > 0 and coverage >= min_annual_coverage and pd.notna(annual_max):
            rows.append(
                {
                    "water_year": int(wy),
                    "annual_max": float(annual_max),
                    "valid_count": valid_count,
                    "expected_hours": expected,
                    "annual_coverage": float(coverage),
                }
            )
    return pd.DataFrame(rows)


def rolling_precipitation(rainfall: pd.Series, duration_hours: int) -> pd.Series:
    rain = pd.to_numeric(rainfall, errors="coerce")
    if duration_hours <= 1:
        return rain
    return rain.rolling(window=duration_hours, min_periods=duration_hours).sum()


def fit_return_levels(
    values: pd.Series | np.ndarray | list[float],
    *,
    return_periods: Iterable[int],
    method: str,
) -> dict[int, float | pd.NA]:
    clean = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
    clean = clean[np.isfinite(clean)]
    if len(clean) < 2:
        return {int(period): pd.NA for period in return_periods}

    periods = [int(period) for period in return_periods]
    probs = np.asarray([1.0 - 1.0 / period for period in periods], dtype=float)
    data = clean.to_numpy(dtype=float)

    try:
        if method == "gumbel":
            loc, scale = stats.gumbel_r.fit(data)
            if not np.isfinite(scale) or scale <= 0:
                raise ValueError("Invalid Gumbel scale.")
            fitted = stats.gumbel_r.ppf(probs, loc=loc, scale=scale)
        elif method == "gev":
            shape, loc, scale = stats.genextreme.fit(data)
            if not np.isfinite(scale) or scale <= 0:
                raise ValueError("Invalid GEV scale.")
            fitted = stats.genextreme.ppf(probs, shape, loc=loc, scale=scale)
        elif method == "empirical":
            fitted = np.quantile(data, probs, method="linear")
        else:
            raise ValueError(f"Unsupported return-period method: {method}")
    except Exception:
        fitted = np.full(len(periods), np.nan)

    result: dict[int, float | pd.NA] = {}
    for period, value in zip(periods, fitted):
        if not np.isfinite(value):
            result[period] = pd.NA
        else:
            result[period] = float(max(0.0, value))
    return result


def return_period_confidence_flag(record_years: int, max_return_period: int) -> str:
    if record_years < 10:
        return "low_record_lt10"
    if max_return_period > record_years * 2:
        return "extrapolated_gt_2x_record"
    if max_return_period > record_years:
        return "extrapolated_gt_record"
    return "ok"


def build_return_period_reference_row(
    *,
    gauge_id: str,
    frame: pd.DataFrame,
    metadata: pd.Series,
    return_periods: Iterable[int],
    precip_durations: Iterable[int],
    method: str,
    min_annual_coverage: float,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    periods = [int(item) for item in return_periods]
    durations = [int(item) for item in precip_durations]

    row: dict[str, object] = {
        "gauge_id": gauge_id,
        "gauge_name": metadata.get("gauge_name", pd.NA),
        "state": metadata.get("state", pd.NA),
        "huc02": metadata.get("huc02", pd.NA),
        "area": to_float(metadata.get("area")),
        "drain_sqkm_attr": to_float(metadata.get("drain_sqkm_attr")),
        "snow_fraction": to_float(metadata.get("snow_fraction")),
        "return_period_method": method,
        "min_annual_coverage": float(min_annual_coverage),
        "flood_ari_source": f"CAMELSH_hourly_annual_max_{method}",
        "prec_ari_source": f"CAMELSH_hourly_annual_max_rolling_precip_{method}",
    }
    annual_rows: list[dict[str, object]] = []

    flood_annual = annual_maxima_with_coverage(frame["Streamflow"], min_annual_coverage)
    row["flood_record_years"] = int(len(flood_annual))
    row["return_period_record_years"] = int(len(flood_annual))
    row["return_period_confidence_flag"] = return_period_confidence_flag(
        int(len(flood_annual)), max(periods)
    )
    flood_levels = fit_return_levels(flood_annual["annual_max"], return_periods=periods, method=method)
    for period in periods:
        row[f"flood_ari{period}"] = flood_levels[period]
    for annual in flood_annual.to_dict("records"):
        annual_rows.append(
            {
                "gauge_id": gauge_id,
                "variable": "Streamflow",
                "duration_hours": 1,
                **annual,
            }
        )

    rainfall = frame["Rainf"]
    for duration in durations:
        precip_series = rolling_precipitation(rainfall, duration)
        precip_annual = annual_maxima_with_coverage(precip_series, min_annual_coverage)
        row[f"prec_record_years_{duration}h"] = int(len(precip_annual))
        levels = fit_return_levels(precip_annual["annual_max"], return_periods=periods, method=method)
        for period in periods:
            row[f"prec_ari{period}_{duration}h"] = levels[period]
        for annual in precip_annual.to_dict("records"):
            annual_rows.append(
                {
                    "gauge_id": gauge_id,
                    "variable": "Rainf",
                    "duration_hours": duration,
                    **annual,
                }
            )

    return row, annual_rows


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


def select_threshold(
    streamflow: pd.Series,
    *,
    threshold_levels: Iterable[tuple[str, float]] = THRESHOLD_LEVELS,
    min_event_count: int = MIN_EVENT_COUNT,
    separation_hours: int = INTER_EVENT_SEPARATION_HOURS,
) -> tuple[str, float, list[EventCluster], dict[str, int]]:
    valid = pd.to_numeric(streamflow, errors="coerce").dropna()
    if valid.empty:
        raise ValueError("Cannot select a threshold from an empty streamflow series.")

    counts: dict[str, int] = {}
    fallback: tuple[str, float, list[EventCluster]] | None = None

    for label, quantile in threshold_levels:
        threshold = float(valid.quantile(quantile))
        clusters = cluster_candidates(
            build_peak_candidates(streamflow, threshold),
            separation_hours=separation_hours,
        )
        counts[label] = len(clusters)
        fallback = (label, threshold, clusters)
        if len(clusters) >= min_event_count:
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


def annual_peak_series(streamflow: pd.Series, min_annual_coverage: float = 0.8) -> pd.Series:
    annual = annual_maxima_with_coverage(streamflow, min_annual_coverage)
    if annual.empty:
        return pd.Series(dtype=float)
    return annual.set_index("water_year")["annual_max"]


def calculate_rbi(streamflow: pd.Series) -> float | pd.NA:
    valid = pd.to_numeric(streamflow, errors="coerce").dropna()
    if valid.empty:
        return pd.NA

    deltas = valid.index.to_series().diff().dt.total_seconds().div(3600)
    consecutive = deltas == 1
    numerator = valid.diff().abs()[consecutive].sum(min_count=1)
    denominator = valid.sum(min_count=1)

    if pd.isna(numerator) or pd.isna(denominator) or denominator == 0:
        return pd.NA
    return float(numerator / denominator)


def quantile_from_positive_windows(
    values: pd.Series,
    *,
    quantile: float = PRECIP_THRESHOLD_QUANTILE,
    min_value: float = 0.0,
    min_count: int = PRECIP_THRESHOLD_MIN_VALID_WINDOW_COUNT,
) -> tuple[float | pd.NA, int]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    clean = clean[np.isfinite(clean)]
    clean = clean[clean > min_value]
    count = int(len(clean))
    if count < min_count:
        return pd.NA, count
    return float(clean.quantile(quantile)), count


def build_degree_day_basin_proxy(
    frame: pd.DataFrame,
    *,
    tcrit_c: float = DEGREE_DAY_TCRIT_C,
    degree_day_factor: float = DEGREE_DAY_FACTOR_MM_PER_DAY_C,
) -> tuple[pd.DataFrame, dict[str, object]]:
    rainfall = pd.to_numeric(frame["Rainf"], errors="coerce").clip(lower=0)
    tair = pd.to_numeric(frame["Tair"], errors="coerce")

    daily_precip = rainfall.resample("D").sum(min_count=1)
    daily_temp = tair.resample("D").mean()
    daily = pd.DataFrame({"precip_mm": daily_precip, "temp_c": daily_temp})

    rows: list[dict[str, object]] = []
    snowpack = 0.0
    for timestamp, row in daily.iterrows():
        precip = row["precip_mm"]
        temp = row["temp_c"]
        snowpack_start = snowpack

        if pd.isna(precip) or pd.isna(temp):
            rows.append(
                {
                    "date": timestamp,
                    "degree_day_rain_1d": pd.NA,
                    "degree_day_snowfall_1d": pd.NA,
                    "degree_day_snowmelt_1d": pd.NA,
                    "degree_day_water_input_1d": pd.NA,
                    "degree_day_snowpack_swe_start": snowpack_start,
                    "degree_day_snowpack_swe_end": snowpack,
                }
            )
            continue

        precip = max(0.0, float(precip))
        temp = float(temp)
        if temp <= tcrit_c:
            rain = 0.0
            snowfall = precip
            snowmelt = 0.0
            snowpack += snowfall
        else:
            rain = precip
            snowfall = 0.0
            melt_potential = max(0.0, degree_day_factor * (temp - tcrit_c))
            snowmelt = min(snowpack, melt_potential)
            snowpack -= snowmelt

        rows.append(
            {
                "date": timestamp,
                "degree_day_rain_1d": rain,
                "degree_day_snowfall_1d": snowfall,
                "degree_day_snowmelt_1d": snowmelt,
                "degree_day_water_input_1d": rain + snowmelt,
                "degree_day_snowpack_swe_start": snowpack_start,
                "degree_day_snowpack_swe_end": snowpack,
            }
        )

    proxy = pd.DataFrame(rows)
    if proxy.empty:
        empty_stats = {column: pd.NA for column in DEGREE_DAY_EVENT_COLUMNS}
        empty_stats["basin_snowmelt_valid_window_count"] = 0
        return pd.DataFrame(), empty_stats

    proxy = proxy.set_index("date")
    proxy["degree_day_rain_3d"] = proxy["degree_day_rain_1d"].rolling(window=3, min_periods=3).sum()
    proxy["degree_day_rain_7d"] = proxy["degree_day_rain_1d"].rolling(
        window=DEGREE_DAY_SNOW_WINDOW_DAYS,
        min_periods=DEGREE_DAY_SNOW_WINDOW_DAYS,
    ).sum()
    proxy["degree_day_rain_30d"] = proxy["degree_day_rain_1d"].rolling(window=30, min_periods=30).sum()
    proxy["degree_day_snowmelt_7d"] = proxy["degree_day_snowmelt_1d"].rolling(
        window=DEGREE_DAY_SNOW_WINDOW_DAYS,
        min_periods=DEGREE_DAY_SNOW_WINDOW_DAYS,
    ).sum()
    proxy["degree_day_water_input_7d"] = proxy["degree_day_water_input_1d"].rolling(
        window=DEGREE_DAY_SNOW_WINDOW_DAYS,
        min_periods=DEGREE_DAY_SNOW_WINDOW_DAYS,
    ).sum()

    snowmelt_p90, snowmelt_count = quantile_from_positive_windows(
        proxy["degree_day_snowmelt_7d"],
        min_value=SNOWMELT_MIN_MM - 1e-12,
        min_count=SNOWMELT_MIN_VALID_WINDOW_COUNT,
    )
    rain_1d_p90, _ = quantile_from_positive_windows(proxy["degree_day_rain_1d"])
    rain_3d_p90, _ = quantile_from_positive_windows(proxy["degree_day_rain_3d"])
    rain_7d_p90, _ = quantile_from_positive_windows(proxy["degree_day_rain_7d"])
    rain_30d_p90, _ = quantile_from_positive_windows(proxy["degree_day_rain_30d"])

    stats = {
        "basin_snowmelt_7d_p90": snowmelt_p90,
        "basin_snowmelt_valid_window_count": snowmelt_count,
        "basin_rain_1d_p90": rain_1d_p90,
        "basin_rain_3d_p90": rain_3d_p90,
        "basin_rain_7d_p90": rain_7d_p90,
        "basin_rain_30d_p90": rain_30d_p90,
    }
    return proxy, stats


def degree_day_event_descriptors(
    peak_time: pd.Timestamp,
    *,
    degree_day_proxy: pd.DataFrame | None,
    degree_day_stats: dict[str, object] | None,
) -> dict[str, object]:
    result = {column: pd.NA for column in DEGREE_DAY_EVENT_COLUMNS}
    result["snow_related_flag"] = pd.NA
    result["rain_on_snow_proxy"] = pd.NA

    if degree_day_stats:
        for key, value in degree_day_stats.items():
            if key in result:
                result[key] = value

    if degree_day_proxy is None or degree_day_proxy.empty:
        return result

    peak_day = pd.Timestamp(peak_time).normalize()
    if peak_day not in degree_day_proxy.index:
        return result

    row = degree_day_proxy.loc[peak_day]
    rain_7d = row.get("degree_day_rain_7d", pd.NA)
    snowmelt_7d = row.get("degree_day_snowmelt_7d", pd.NA)
    water_input_7d = row.get("degree_day_water_input_7d", pd.NA)

    result["degree_day_rain_7d"] = to_float(rain_7d)
    result["degree_day_snowmelt_7d"] = to_float(snowmelt_7d)
    result["degree_day_water_input_7d"] = to_float(water_input_7d)

    water_value = pd.to_numeric(pd.Series([water_input_7d]), errors="coerce").iloc[0]
    rain_value = pd.to_numeric(pd.Series([rain_7d]), errors="coerce").iloc[0]
    snowmelt_value = pd.to_numeric(pd.Series([snowmelt_7d]), errors="coerce").iloc[0]
    if pd.notna(water_value) and float(water_value) > 0:
        result["degree_day_snowmelt_fraction_7d"] = float(snowmelt_value / water_value)
        result["degree_day_rain_fraction_7d"] = float(rain_value / water_value)

    snowmelt_p90 = pd.to_numeric(pd.Series([result.get("basin_snowmelt_7d_p90")]), errors="coerce").iloc[0]
    valid_count = pd.to_numeric(
        pd.Series([result.get("basin_snowmelt_valid_window_count")]),
        errors="coerce",
    ).iloc[0]
    snowmelt_proxy = (
        pd.notna(snowmelt_value)
        and pd.notna(snowmelt_p90)
        and pd.notna(valid_count)
        and float(snowmelt_value) >= float(snowmelt_p90)
        and float(snowmelt_value) >= SNOWMELT_MIN_MM
        and int(valid_count) >= SNOWMELT_MIN_VALID_WINDOW_COUNT
    )

    snow_fraction = pd.to_numeric(
        pd.Series([result.get("degree_day_snowmelt_fraction_7d")]),
        errors="coerce",
    ).iloc[0]
    rain_fraction = pd.to_numeric(
        pd.Series([result.get("degree_day_rain_fraction_7d")]),
        errors="coerce",
    ).iloc[0]
    rain_on_snow = (
        pd.notna(water_value)
        and float(water_value) > 0
        and pd.notna(snowmelt_value)
        and float(snowmelt_value) >= SNOWMELT_MIN_MM
        and pd.notna(snow_fraction)
        and float(snow_fraction) >= RAIN_SNOWMELT_MIN_FRACTION
        and pd.notna(rain_fraction)
        and float(rain_fraction) >= RAIN_SNOWMELT_MIN_FRACTION
    )

    result["rain_on_snow_proxy"] = bool(rain_on_snow)
    result["snow_related_flag"] = bool(rain_on_snow or snowmelt_proxy)
    return result


def build_event_row(
    *,
    basin: pd.Series,
    frame: pd.DataFrame,
    cluster: EventCluster,
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
        "gauge_name": basin.get("gauge_name", pd.NA),
        "state": basin.get("state", pd.NA),
        "huc02": basin.get("huc02", pd.NA),
        "drain_sqkm_attr": to_float(basin.get("drain_sqkm_attr")),
        "area": to_float(basin.get("area")),
        "snow_fraction": to_float(basin.get("snow_fraction")),
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
        "peak_temp": to_float(tair.get(peak_time)),
        "event_runoff_coefficient": pd.NA,
        "snow_related_flag": pd.NA,
        "rain_on_snow_proxy": pd.NA,
        "api_7d": pd.NA,
        "api_30d": pd.NA,
    }
    row.update(
        degree_day_event_descriptors(
            peak_time,
            degree_day_proxy=degree_day_proxy,
            degree_day_stats=degree_day_stats,
        )
    )
    return row


def build_basin_event_summary_row(
    *,
    basin: pd.Series,
    processing_status: str,
    threshold_label: str | None,
    threshold_value: float | None,
    threshold_counts: dict[str, int],
    extracted_events: list[dict[str, object]],
    streamflow: pd.Series | None,
    min_annual_coverage: float = 0.8,
) -> dict[str, object]:
    usable_years = pd.to_numeric(pd.Series([basin.get("obs_years_usable")]), errors="coerce").dropna()
    usable_years_value = float(usable_years.iloc[0]) if not usable_years.empty else pd.NA

    base = {
        "gauge_id": basin["gauge_id"],
        "gauge_name": basin.get("gauge_name", pd.NA),
        "state": basin.get("state", pd.NA),
        "huc02": basin.get("huc02", pd.NA),
        "drain_sqkm_attr": to_float(basin.get("drain_sqkm_attr")),
        "area": to_float(basin.get("area")),
        "snow_fraction": to_float(basin.get("snow_fraction")),
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

    if streamflow is None or pd.to_numeric(streamflow, errors="coerce").dropna().empty:
        return base

    annual_peaks = annual_peak_series(streamflow, min_annual_coverage=min_annual_coverage)
    base["annual_peak_years"] = int(len(annual_peaks))
    base["rbi"] = calculate_rbi(streamflow)

    denominator = usable_years_value
    if pd.isna(denominator) or denominator <= 0:
        denominator = float(len(annual_peaks)) if len(annual_peaks) > 0 else pd.NA
    if pd.notna(denominator) and denominator > 0:
        base["q99_event_frequency"] = float(threshold_counts.get("Q99", 0) / denominator)

    area_value = pd.to_numeric(pd.Series([basin.get("drain_sqkm_attr"), basin.get("area")]), errors="coerce").dropna()
    if not area_value.empty and len(annual_peaks) > 0 and float(area_value.iloc[0]) > 0:
        annual_unit_area = annual_peaks / float(area_value.iloc[0])
        base["annual_peak_unit_area_median"] = float(annual_unit_area.median())
        base["annual_peak_unit_area_p90"] = float(annual_unit_area.quantile(0.9))

    if extracted_events:
        events = pd.DataFrame(extracted_events)
        if "flood_relevance_tier" in events.columns:
            tiers = events["flood_relevance_tier"].value_counts(dropna=False)
            base["flood_like_ge_2yr_proxy_event_count"] = int(
                events["flood_relevance_tier"].astype(str).str.startswith("flood_like_ge_").sum()
            )
            base["high_flow_below_2yr_proxy_event_count"] = int(tiers.get(FLOOD_RELEVANCE_BELOW_2YR, 0))
            base["high_flow_candidate_unrated_event_count"] = int(tiers.get(FLOOD_RELEVANCE_UNRATED, 0))
        base["unit_area_peak_median"] = to_float(pd.to_numeric(events["unit_area_peak"], errors="coerce").median())
        base["unit_area_peak_p90"] = to_float(pd.to_numeric(events["unit_area_peak"], errors="coerce").quantile(0.9))
        base["rising_time_median_hours"] = to_float(pd.to_numeric(events["rising_time_hours"], errors="coerce").median())
        base["event_duration_median_hours"] = to_float(
            pd.to_numeric(events["event_duration_hours"], errors="coerce").median()
        )
        base["event_runoff_coefficient_median"] = to_float(
            pd.to_numeric(events["event_runoff_coefficient"], errors="coerce").median()
        )

    return base


def safe_ratio(numerator: object, denominator: object) -> float | pd.NA:
    num = pd.to_numeric(pd.Series([numerator]), errors="coerce").iloc[0]
    den = pd.to_numeric(pd.Series([denominator]), errors="coerce").iloc[0]
    if pd.isna(num) or pd.isna(den) or den == 0:
        return pd.NA
    return float(num / den)


def classify_flood_relevance_tier(event_row: dict[str, object], return_periods: Iterable[int]) -> str:
    qualifying_periods: list[int] = []
    has_valid_reference_ratio = False

    for period in sorted(int(item) for item in return_periods):
        ratio = pd.to_numeric(pd.Series([event_row.get(f"peak_to_flood_ari{period}")]), errors="coerce").iloc[0]
        if pd.isna(ratio):
            continue
        has_valid_reference_ratio = True
        if float(ratio) >= 1.0:
            qualifying_periods.append(period)

    if qualifying_periods:
        return f"flood_like_ge_{max(qualifying_periods)}yr_proxy"
    if has_valid_reference_ratio:
        return FLOOD_RELEVANCE_BELOW_2YR
    return FLOOD_RELEVANCE_UNRATED


class ProgressReporter:
    def __init__(self, *, total: int, label: str, width: int = 28, log_every: int = 25) -> None:
        self.total = max(0, int(total))
        self.label = label
        self.width = width
        self.log_every = max(1, int(log_every))
        self.started_at = time.monotonic()
        self.last_count = 0
        self.is_tty = sys.stdout.isatty()

    def update(self, count: int) -> None:
        count = min(max(0, int(count)), self.total)
        self.last_count = count

        if self.is_tty:
            print(f"\r{self._line(count)}", end="", flush=True)
            if count >= self.total:
                print()
        elif count == self.total or count == 1 or count % self.log_every == 0:
            print(self._line(count), flush=True)

    def _line(self, count: int) -> str:
        if self.total == 0:
            percent = 100.0
            filled = self.width
        else:
            percent = count / self.total * 100
            filled = int(round(self.width * count / self.total))
        bar = "#" * filled + "-" * (self.width - filled)
        elapsed = time.monotonic() - self.started_at
        rate = count / elapsed if elapsed > 0 else 0.0
        eta = (self.total - count) / rate if rate > 0 and count < self.total else 0.0
        return (
            f"{self.label}: [{bar}] {count}/{self.total} "
            f"({percent:5.1f}%) elapsed={format_seconds(elapsed)} eta={format_seconds(eta)}"
        )


def format_seconds(seconds: float) -> str:
    seconds = int(max(0, round(seconds)))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}h{minutes:02d}m{secs:02d}s"
    if minutes:
        return f"{minutes:d}m{secs:02d}s"
    return f"{secs:d}s"
