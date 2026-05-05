#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pandas>=2.2",
# ]
# ///

from __future__ import annotations

import argparse
import concurrent.futures as futures
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd


NOAA_PFDS_URL = "https://hdsc.nws.noaa.gov/cgi-bin/hdsc/new/fe_text_mean.csv"
DEFAULT_OUTPUT_DIR = Path("output/basin/all")
DEFAULT_METADATA_CSV = Path("basins/CAMELSH_data/attributes/attributes_gageii_BasinID.csv")
DEFAULT_RETURN_PERIODS = (2, 5, 10, 25, 50, 100)
DEFAULT_DURATIONS = {
    1: "60-min",
    6: "6-hr",
    24: "24-hr",
    72: "3-day",
}
NOAA_SERIES = ("ams", "pds")


class NoaaOutsideProjectArea(ValueError):
    """Raised when PFDS returns the Atlas 14 outside-project-area response."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch NOAA Atlas 14 PFDS precipitation-frequency estimates at CAMELSH "
            "gauge coordinates and append them next to CAMELSH prec_ari proxy columns."
        )
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=None,
        help=(
            "Existing return-period reference table. Defaults to "
            "<output-dir>/reference_comparison/usgs_flood/tables/return_period_reference_table_with_usgs.csv "
            "if present, otherwise <output-dir>/analysis/return_period/tables/return_period_reference_table.csv."
        ),
    )
    parser.add_argument(
        "--metadata-csv",
        type=Path,
        default=DEFAULT_METADATA_CSV,
        help="CAMELSH BasinID metadata CSV containing STAID, LAT_GAGE, and LNG_GAGE.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="All-basin output root for reference-comparison tables, metadata, and cache.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=None,
        help=(
            "Merged CSV path. Defaults to input stem plus _noaa14.csv when the input "
            "already ends in _with_usgs, otherwise input stem plus _with_noaa14.csv."
        ),
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Raw NOAA PFDS response cache. Defaults to <output-dir>/cache/noaa_atlas14.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional first-N basin limit for smoke tests.")
    parser.add_argument("--gauge-id", action="append", default=[], help="Optional gauge ID filter. Can repeat.")
    parser.add_argument("--workers", type=int, default=4, help="Number of concurrent HTTP workers.")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds.")
    parser.add_argument("--retries", type=int, default=2, help="Retries per station/series after transient failures.")
    parser.add_argument("--force-refresh", action="store_true", help="Ignore cached NOAA PFDS responses.")
    return parser.parse_args()


def normalize_gauge_id(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    if text.isdigit() and len(text) < 8:
        text = text.zfill(8)
    return text


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def resolve_input_csv(args: argparse.Namespace) -> Path:
    if args.input_csv is not None:
        return args.input_csv
    table_dir = args.output_dir / "reference_comparison" / "usgs_flood" / "tables"
    return_period_dir = args.output_dir / "analysis" / "return_period" / "tables"
    candidates = [
        table_dir / "return_period_reference_table_with_usgs.csv",
        return_period_dir / "return_period_reference_table.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise SystemExit(
        "No default input CSV found. Expected one of: "
        + ", ".join(str(candidate) for candidate in candidates)
    )


def default_output_csv(input_csv: Path) -> Path:
    if input_csv.stem.endswith("_with_usgs"):
        return input_csv.with_name(f"{input_csv.stem}_noaa14{input_csv.suffix}")
    return input_csv.with_name(f"{input_csv.stem}_with_noaa14{input_csv.suffix}")


def load_coordinates(path: Path) -> pd.DataFrame:
    coords = pd.read_csv(path, dtype={"STAID": str})
    required = {"STAID", "LAT_GAGE", "LNG_GAGE"}
    missing = required - set(coords.columns)
    if missing:
        raise ValueError(f"Missing required coordinate columns in {path}: {sorted(missing)}")
    coords = coords[["STAID", "LAT_GAGE", "LNG_GAGE"]].copy()
    coords["gauge_id"] = coords["STAID"].map(normalize_gauge_id)
    coords["lat_gage"] = pd.to_numeric(coords["LAT_GAGE"], errors="coerce")
    coords["lng_gage"] = pd.to_numeric(coords["LNG_GAGE"], errors="coerce")
    return coords[["gauge_id", "lat_gage", "lng_gage"]].drop_duplicates("gauge_id")


def attach_coordinates(reference: pd.DataFrame, coords: pd.DataFrame) -> pd.DataFrame:
    merged = reference.merge(coords, on="gauge_id", how="left", suffixes=("", "__coord"))
    for col in ("lat_gage", "lng_gage"):
        incoming = f"{col}__coord"
        if incoming in merged.columns:
            if col in merged.columns:
                merged[col] = pd.to_numeric(merged[col], errors="coerce").combine_first(
                    pd.to_numeric(merged[incoming], errors="coerce")
                )
            else:
                merged[col] = pd.to_numeric(merged[incoming], errors="coerce")
            merged = merged.drop(columns=[incoming])
    for col in ("lat_gage", "lng_gage"):
        if col not in merged.columns:
            merged[col] = pd.NA
        merged[col] = pd.to_numeric(merged[col], errors="coerce")
    return merged


def request_noaa_text(lat: float, lon: float, series: str, timeout: float, retries: int) -> str:
    params = {
        "lat": float(lat),
        "lon": float(lon),
        "data": "depth",
        "series": series,
        "units": "metric",
    }
    url = f"{NOAA_PFDS_URL}?{urllib.parse.urlencode(params)}"
    headers = {
        "Accept": "text/csv,text/plain",
        "User-Agent": "CAMELS-flood-frequency-research/1.0 (NOAA Atlas 14 PFDS client)",
    }
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, UnicodeDecodeError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.5 * (2**attempt))
                continue
            raise RuntimeError(str(last_error)) from last_error
    raise RuntimeError("Unreachable request retry state.")


def load_noaa_text(
    gauge_id: str,
    lat: float,
    lon: float,
    series: str,
    *,
    cache_dir: Path,
    timeout: float,
    retries: int,
    force_refresh: bool,
) -> tuple[str, Path, bool]:
    cache_path = cache_dir / f"{gauge_id}_{series}.csv"
    if cache_path.exists() and not force_refresh:
        return cache_path.read_text(encoding="utf-8"), cache_path, True
    text = request_noaa_text(lat, lon, series, timeout=timeout, retries=retries)
    cache_path.write_text(text, encoding="utf-8")
    return text, cache_path, False


def parse_key_value_line(line: str) -> tuple[str, str] | None:
    if ":" not in line:
        return None
    key, value = line.split(":", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None
    return key, value


def extract_noaa_metadata(text: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == "PRECIPITATION FREQUENCY ESTIMATES":
            break
        if stripped.startswith("NOAA Atlas 14"):
            metadata["atlas_version"] = stripped
            continue
        key_value = parse_key_value_line(stripped)
        if key_value is None:
            continue
        key, value = key_value
        normalized_key = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
        metadata[normalized_key] = value
    return metadata


def parse_header_periods(line: str, series: str) -> list[int]:
    pieces = [piece.strip().strip("'") for piece in line.split(",")[1:]]
    periods: list[int] = []
    for piece in pieces:
        if not piece:
            continue
        if series == "ams":
            match = re.fullmatch(r"1/(\d+)", piece)
            if not match:
                continue
            periods.append(int(match.group(1)))
        else:
            try:
                periods.append(int(float(piece)))
            except ValueError:
                continue
    return periods


def parse_duration_row(line: str) -> tuple[str, list[float | pd.NA]] | None:
    pieces = [piece.strip() for piece in line.split(",")]
    if len(pieces) < 2:
        return None
    label = pieces[0].rstrip(":").strip()
    values: list[float | pd.NA] = []
    for piece in pieces[1:]:
        value = pd.to_numeric(pd.Series([piece]), errors="coerce").iloc[0]
        values.append(float(value) if pd.notna(value) else pd.NA)
    return label, values


def parse_noaa_estimates(text: str, series: str) -> tuple[dict[tuple[int, int], float | pd.NA], dict[str, str]]:
    if "Selected location is not within a project area" in text:
        raise NoaaOutsideProjectArea("Selected location is not within a NOAA Atlas 14 project area.")

    metadata = extract_noaa_metadata(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    header_index = None
    for index, line in enumerate(lines):
        if line.startswith("by duration for "):
            header_index = index
            break
    if header_index is None:
        raise ValueError("Could not find NOAA PFDS duration/ARI header.")

    periods = parse_header_periods(lines[header_index], series)
    if not periods:
        raise ValueError("Could not parse NOAA PFDS return periods.")

    wanted_labels = {label: duration for duration, label in DEFAULT_DURATIONS.items()}
    estimates: dict[tuple[int, int], float | pd.NA] = {}
    for line in lines[header_index + 1 :]:
        if line.startswith("Date/time"):
            break
        parsed = parse_duration_row(line)
        if parsed is None:
            continue
        label, values = parsed
        if label not in wanted_labels:
            continue
        duration = wanted_labels[label]
        by_period = dict(zip(periods, values, strict=False))
        for period in DEFAULT_RETURN_PERIODS:
            estimates[(period, duration)] = by_period.get(period, pd.NA)

    missing = [
        f"{period}y/{duration}h"
        for duration in DEFAULT_DURATIONS
        for period in DEFAULT_RETURN_PERIODS
        if (period, duration) not in estimates
    ]
    if missing:
        raise ValueError("NOAA PFDS response did not include required estimates: " + ",".join(missing))
    return estimates, metadata


def blank_noaa_row(gauge_id: str, status: str, detail: str | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "gauge_id": gauge_id,
        "noaa14_fetch_status": status,
        "noaa14_prec_ari_unit": "mm",
        "noaa14_prec_ari_source": "NOAA_Atlas_14_PFDS_point_precipitation_frequency_estimates",
    }
    if detail:
        row["noaa14_fetch_error"] = detail
    for series in NOAA_SERIES:
        row[f"noaa14_{series}_fetch_status"] = status
        for period in DEFAULT_RETURN_PERIODS:
            for duration in DEFAULT_DURATIONS:
                row[f"noaa14_{series}_prec_ari{period}_{duration}h"] = pd.NA
    return row


def fetch_one(task: dict[str, Any]) -> dict[str, Any]:
    gauge_id = task["gauge_id"]
    lat = task["lat"]
    lon = task["lon"]
    if not (math.isfinite(lat) and math.isfinite(lon)):
        return blank_noaa_row(gauge_id, "missing_coordinates")

    row: dict[str, Any] = {
        "gauge_id": gauge_id,
        "noaa14_lat_gage": lat,
        "noaa14_lng_gage": lon,
        "noaa14_prec_ari_unit": "mm",
        "noaa14_prec_ari_statistic": "mean",
        "noaa14_prec_ari_source": "NOAA_Atlas_14_PFDS_point_precipitation_frequency_estimates",
        "noaa14_service_url": NOAA_PFDS_URL,
    }
    series_statuses = []
    atlas_versions = set()
    project_areas = set()
    time_series_types = []

    for series in NOAA_SERIES:
        try:
            text, cache_path, from_cache = load_noaa_text(
                gauge_id,
                lat,
                lon,
                series,
                cache_dir=task["cache_dir"],
                timeout=task["timeout"],
                retries=task["retries"],
                force_refresh=task["force_refresh"],
            )
            estimates, metadata = parse_noaa_estimates(text, series)
            for period in DEFAULT_RETURN_PERIODS:
                for duration in DEFAULT_DURATIONS:
                    row[f"noaa14_{series}_prec_ari{period}_{duration}h"] = estimates[(period, duration)]
            row[f"noaa14_{series}_fetch_status"] = "cached" if from_cache else "ok"
            row[f"noaa14_{series}_cache_path"] = str(cache_path)
            row[f"noaa14_{series}_atlas_version"] = metadata.get("atlas_version", pd.NA)
            row[f"noaa14_{series}_project_area"] = metadata.get("project_area", pd.NA)
            row[f"noaa14_{series}_time_series_type"] = metadata.get("time_series_type", pd.NA)
            series_statuses.append("ok")
            if metadata.get("atlas_version"):
                atlas_versions.add(metadata["atlas_version"])
            if metadata.get("project_area"):
                project_areas.add(metadata["project_area"])
            if metadata.get("time_series_type"):
                time_series_types.append(f"{series}:{metadata['time_series_type']}")
        except NoaaOutsideProjectArea as exc:
            row[f"noaa14_{series}_fetch_status"] = "outside_atlas14_project_area"
            row[f"noaa14_{series}_fetch_error"] = f"{type(exc).__name__}: {exc}"
            for period in DEFAULT_RETURN_PERIODS:
                for duration in DEFAULT_DURATIONS:
                    row[f"noaa14_{series}_prec_ari{period}_{duration}h"] = pd.NA
            series_statuses.append("outside_atlas14_project_area")
        except Exception as exc:
            row[f"noaa14_{series}_fetch_status"] = "fetch_error"
            row[f"noaa14_{series}_fetch_error"] = f"{type(exc).__name__}: {exc}"
            for period in DEFAULT_RETURN_PERIODS:
                for duration in DEFAULT_DURATIONS:
                    row[f"noaa14_{series}_prec_ari{period}_{duration}h"] = pd.NA
            series_statuses.append("fetch_error")

    if all(status == "ok" for status in series_statuses):
        row["noaa14_fetch_status"] = "ok"
    elif any(status == "ok" for status in series_statuses):
        row["noaa14_fetch_status"] = "partial"
    elif all(status == "outside_atlas14_project_area" for status in series_statuses):
        row["noaa14_fetch_status"] = "outside_atlas14_project_area"
    else:
        row["noaa14_fetch_status"] = "fetch_error"
    row["noaa14_atlas_versions"] = "; ".join(sorted(atlas_versions))
    row["noaa14_project_areas"] = "; ".join(sorted(project_areas))
    row["noaa14_time_series_types"] = "; ".join(time_series_types)
    return row


def run_fetches(tasks: list[dict[str, Any]], workers: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    total = len(tasks)
    print(f"Fetching NOAA Atlas 14 precipitation-frequency estimates for {total} stations with {workers} workers", flush=True)
    if workers <= 1:
        for index, task in enumerate(tasks, start=1):
            rows.append(fetch_one(task))
            if index == 1 or index % 50 == 0 or index == total:
                print(f"  processed {index}/{total}", flush=True)
        return rows

    with futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_site = {executor.submit(fetch_one, task): task["gauge_id"] for task in tasks}
        for index, future in enumerate(futures.as_completed(future_to_site), start=1):
            rows.append(future.result())
            if index == 1 or index % 50 == 0 or index == total:
                print(f"  processed {index}/{total}", flush=True)
    return rows


def add_comparison_columns(frame: pd.DataFrame) -> pd.DataFrame:
    comparison_columns: dict[str, pd.Series] = {}
    for series in NOAA_SERIES:
        for period in DEFAULT_RETURN_PERIODS:
            for duration in DEFAULT_DURATIONS:
                camelsh_col = f"prec_ari{period}_{duration}h"
                noaa_col = f"noaa14_{series}_prec_ari{period}_{duration}h"
                if camelsh_col not in frame.columns or noaa_col not in frame.columns:
                    continue
                camelsh = pd.to_numeric(frame[camelsh_col], errors="coerce")
                noaa = pd.to_numeric(frame[noaa_col], errors="coerce")
                comparison_columns[f"noaa14_{series}_to_camelsh_prec_ari{period}_{duration}h"] = noaa / camelsh
                comparison_columns[f"camelsh_minus_noaa14_{series}_prec_ari{period}_{duration}h"] = camelsh - noaa
                comparison_columns[f"camelsh_minus_noaa14_{series}_prec_ari{period}_{duration}h_relative"] = (
                    camelsh - noaa
                ) / noaa
    if not comparison_columns:
        return frame
    return pd.concat([frame, pd.DataFrame(comparison_columns, index=frame.index)], axis=1)


def insert_noaa_columns_near_prec_proxy(frame: pd.DataFrame) -> pd.DataFrame:
    desired: list[str] = []
    used: set[str] = set()
    for col in frame.columns:
        if col in used:
            continue
        desired.append(col)
        used.add(col)
        match = re.fullmatch(r"prec_ari(\d+)_(\d+)h", col)
        if not match:
            continue
        period = int(match.group(1))
        duration = int(match.group(2))
        for series in NOAA_SERIES:
            for extra in [
                f"noaa14_{series}_prec_ari{period}_{duration}h",
                f"noaa14_{series}_to_camelsh_prec_ari{period}_{duration}h",
                f"camelsh_minus_noaa14_{series}_prec_ari{period}_{duration}h",
                f"camelsh_minus_noaa14_{series}_prec_ari{period}_{duration}h_relative",
            ]:
                if extra in frame.columns and extra not in used:
                    desired.append(extra)
                    used.add(extra)
    desired.extend(col for col in frame.columns if col not in used)
    return frame.reindex(columns=desired)


def main() -> None:
    args = parse_args()
    table_dir = args.output_dir / "reference_comparison" / "noaa_prec" / "tables"
    metadata_dir = args.output_dir / "reference_comparison" / "noaa_prec" / "metadata"
    table_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    input_csv = resolve_input_csv(args)
    output_csv = args.output_csv or table_dir / default_output_csv(input_csv).name
    cache_dir = args.cache_dir or args.output_dir / "cache" / "noaa_atlas14"
    cache_dir.mkdir(parents=True, exist_ok=True)

    reference = pd.read_csv(input_csv, dtype={"gauge_id": str})
    reference["gauge_id"] = reference["gauge_id"].map(normalize_gauge_id)
    reference = reference.drop_duplicates("gauge_id").sort_values("gauge_id").reset_index(drop=True)
    if args.gauge_id:
        requested = {normalize_gauge_id(item) for item in args.gauge_id}
        reference = reference[reference["gauge_id"].isin(requested)].copy()
    if args.limit is not None:
        reference = reference.head(args.limit).copy()
    if reference.empty:
        raise SystemExit("No basins matched the requested input/filter options.")

    coords = load_coordinates(args.metadata_csv)
    reference = attach_coordinates(reference, coords)
    missing_coords = int(reference[["lat_gage", "lng_gage"]].isna().any(axis=1).sum())

    tasks = [
        {
            "gauge_id": row["gauge_id"],
            "lat": float(row["lat_gage"]) if pd.notna(row["lat_gage"]) else math.nan,
            "lon": float(row["lng_gage"]) if pd.notna(row["lng_gage"]) else math.nan,
            "cache_dir": cache_dir,
            "timeout": args.timeout,
            "retries": args.retries,
            "force_refresh": args.force_refresh,
        }
        for row in reference[["gauge_id", "lat_gage", "lng_gage"]].to_dict("records")
    ]
    noaa_rows = run_fetches(tasks, workers=max(1, args.workers))
    noaa = pd.DataFrame(noaa_rows)
    merged = reference.merge(noaa, on="gauge_id", how="left")
    merged = add_comparison_columns(merged)
    merged = insert_noaa_columns_near_prec_proxy(merged)

    summary_path = metadata_dir / "noaa_atlas14_precip_reference_summary.json"
    merged.to_csv(output_csv, index=False)

    status_counts = noaa["noaa14_fetch_status"].value_counts(dropna=False).to_dict()
    selected_period_counts = {
        f"{series}_{period}_{duration}h": int(
            pd.to_numeric(noaa.get(f"noaa14_{series}_prec_ari{period}_{duration}h"), errors="coerce")
            .notna()
            .sum()
        )
        for series in NOAA_SERIES
        for period in DEFAULT_RETURN_PERIODS
        for duration in DEFAULT_DURATIONS
    }
    summary = {
        "input_csv": str(input_csv),
        "output_csv": str(output_csv),
        "metadata_csv": str(args.metadata_csv),
        "cache_dir": str(cache_dir),
        "station_count": int(len(reference)),
        "missing_coordinate_count": missing_coords,
        "status_counts": status_counts,
        "selected_period_counts": selected_period_counts,
        "source": "NOAA Atlas 14 PFDS point precipitation-frequency estimates",
        "service_url": NOAA_PFDS_URL,
        "query": {"data": "depth", "units": "metric", "series": list(NOAA_SERIES), "statistic": "mean"},
        "return_periods": list(DEFAULT_RETURN_PERIODS),
        "duration_mapping": {str(duration): label for duration, label in DEFAULT_DURATIONS.items()},
        "unit": "mm",
    }
    summary_path.write_text(json.dumps(json_safe(summary), indent=2), encoding="utf-8")

    print(f"Wrote merged table: {output_csv}", flush=True)
    print(f"Wrote summary: {summary_path}", flush=True)
    print(json.dumps(json_safe(summary), indent=2), flush=True)


if __name__ == "__main__":
    main()
