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
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd


GAGESTATS_STATION_URL = "https://streamstats.usgs.gov/gagestatsservices/Stations/{site_id}"
CFS_TO_CMS = 0.028316846592
RETURN_PERIOD_TO_PFS_CODE = {
    2: "PK50AEP",
    5: "PK20AEP",
    10: "PK10AEP",
    25: "PK4AEP",
    50: "PK2AEP",
    100: "PK1AEP",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch USGS StreamStats/GageStats peak-flow frequency statistics and "
            "append them next to CAMELSH flood_ari proxy columns."
        )
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=Path("output/basin/all/analysis/return_period/tables/return_period_reference_table.csv"),
        help="Existing return-period reference table with CAMELSH flood_ari columns.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/basin/all"),
        help="All-basin output root for reference-comparison tables, metadata, and cache.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=None,
        help="Merged CSV path. Defaults to <output-dir>/reference_comparison/usgs_flood/tables/return_period_reference_table_with_usgs.csv.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Raw GageStats response cache. Defaults to <output-dir>/cache/usgs_streamstats.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional first-N basin limit for smoke tests.")
    parser.add_argument("--workers", type=int, default=4, help="Number of concurrent HTTP workers.")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds.")
    parser.add_argument("--retries", type=int, default=2, help="Retries per station after transient failures.")
    parser.add_argument("--force-refresh", action="store_true", help="Ignore cached station responses.")
    return parser.parse_args()


def normalize_site_id(value: object) -> str:
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


def request_json(url: str, timeout: float, retries: int) -> dict[str, Any]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "CAMELS-flood-frequency-research/1.0 (USGS StreamStats GageStats client)",
    }
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read().decode("utf-8")
            data = json.loads(payload)
            if not isinstance(data, dict):
                raise ValueError("GageStats response was not a JSON object.")
            return data
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.5 * (2**attempt))
                continue
            raise RuntimeError(str(last_error)) from last_error
    raise RuntimeError("Unreachable request retry state.")


def load_station(site_id: str, *, cache_dir: Path, timeout: float, retries: int, force_refresh: bool) -> dict[str, Any]:
    cache_path = cache_dir / f"{site_id}.json"
    if cache_path.exists() and not force_refresh:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    data = request_json(GAGESTATS_STATION_URL.format(site_id=site_id), timeout=timeout, retries=retries)
    cache_path.write_text(json.dumps(json_safe(data), indent=2), encoding="utf-8")
    return data


def citation_year(stat: dict[str, Any]) -> int:
    citation = stat.get("citation") or {}
    text = str(citation.get("title") or "")
    match = re.search(r"\b(19|20)\d{2}\b", text)
    return int(match.group(0)) if match else -1


def choose_preferred_stat(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda item: (
            bool(item.get("isPreferred")),
            citation_year(item),
            float(item.get("yearsofRecord") or -1),
            int(item.get("id") or -1),
        ),
        reverse=True,
    )[0]


def parse_peak_flow_stats(site_id: str, station: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if station.get("code") in (400, 404) or "statistics" not in station:
        return (
            {
                "gauge_id": site_id,
                "usgs_station_code": pd.NA,
                "usgs_peak_flow_fetch_status": "station_not_found",
                "usgs_peak_flow_available_count": 0,
                "usgs_peak_flow_selected_count": 0,
                "usgs_peak_flow_missing_periods": ",".join(str(period) for period in RETURN_PERIOD_TO_PFS_CODE),
            },
            [],
        )

    stats = station.get("statistics") or []
    peak_stats = [
        stat
        for stat in stats
        if ((stat.get("statisticGroupType") or {}).get("code") == "PFS")
        and ((stat.get("regressionType") or {}).get("code") in set(RETURN_PERIOD_TO_PFS_CODE.values()))
    ]
    row: dict[str, Any] = {
        "gauge_id": site_id,
        "usgs_station_code": station.get("code"),
        "usgs_station_name": station.get("name"),
        "usgs_station_region": (station.get("region") or {}).get("code"),
        "usgs_station_is_regulated": station.get("isRegulated"),
        "usgs_flood_ari_source": "USGS_StreamStats_GageStats_Peak-Flow_Statistics",
        "usgs_flood_ari_unit": "m3/s",
        "usgs_peak_flow_fetch_status": "ok",
        "usgs_peak_flow_available_count": len(peak_stats),
    }
    citation_rows: list[dict[str, Any]] = []
    selected_count = 0
    missing_periods = []

    for period, code in RETURN_PERIOD_TO_PFS_CODE.items():
        candidates = [stat for stat in peak_stats if (stat.get("regressionType") or {}).get("code") == code]
        selected = choose_preferred_stat(candidates)
        if selected is None:
            missing_periods.append(str(period))
            row[f"usgs_flood_ari{period}"] = pd.NA
            row[f"usgs_flood_ari{period}_cfs"] = pd.NA
            row[f"usgs_flood_ari{period}_years_of_record"] = pd.NA
            row[f"usgs_flood_ari{period}_citation_id"] = pd.NA
            continue

        value_cfs = pd.to_numeric(pd.Series([selected.get("value")]), errors="coerce").iloc[0]
        value_cms = float(value_cfs) * CFS_TO_CMS if pd.notna(value_cfs) else pd.NA
        citation = selected.get("citation") or {}
        regression = selected.get("regressionType") or {}
        unit_type = selected.get("unitType") or {}
        selected_count += 1

        row[f"usgs_flood_ari{period}"] = value_cms
        row[f"usgs_flood_ari{period}_cfs"] = float(value_cfs) if pd.notna(value_cfs) else pd.NA
        row[f"usgs_flood_ari{period}_years_of_record"] = selected.get("yearsofRecord", pd.NA)
        row[f"usgs_flood_ari{period}_citation_id"] = citation.get("id", selected.get("citationID", pd.NA))
        citation_rows.append(
            {
                "gauge_id": site_id,
                "return_period_years": period,
                "usgs_pfs_code": code,
                "usgs_pfs_name": regression.get("name"),
                "usgs_pfs_value_cfs": float(value_cfs) if pd.notna(value_cfs) else pd.NA,
                "usgs_pfs_unit": unit_type.get("abbreviation"),
                "usgs_pfs_years_of_record": selected.get("yearsofRecord", pd.NA),
                "usgs_pfs_is_preferred": selected.get("isPreferred"),
                "usgs_pfs_comments": selected.get("comments"),
                "usgs_pfs_citation_id": citation.get("id", selected.get("citationID", pd.NA)),
                "usgs_pfs_citation_title": citation.get("title"),
                "usgs_pfs_citation_url": citation.get("citationURL"),
            }
        )

    row["usgs_peak_flow_selected_count"] = selected_count
    row["usgs_peak_flow_missing_periods"] = ",".join(missing_periods)
    if selected_count == 0:
        row["usgs_peak_flow_fetch_status"] = "no_peak_flow_statistics"
    elif missing_periods:
        row["usgs_peak_flow_fetch_status"] = "partial_peak_flow_statistics"
    return row, citation_rows


def fetch_one(task: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    site_id = task["site_id"]
    try:
        station = load_station(
            site_id,
            cache_dir=task["cache_dir"],
            timeout=task["timeout"],
            retries=task["retries"],
            force_refresh=task["force_refresh"],
        )
        return parse_peak_flow_stats(site_id, station)
    except Exception as exc:
        return (
            {
                "gauge_id": site_id,
                "usgs_peak_flow_fetch_status": "fetch_error",
                "usgs_peak_flow_error": f"{type(exc).__name__}: {exc}",
                "usgs_peak_flow_available_count": 0,
                "usgs_peak_flow_selected_count": 0,
                "usgs_peak_flow_missing_periods": ",".join(str(period) for period in RETURN_PERIOD_TO_PFS_CODE),
            },
            [],
        )


def run_fetches(tasks: list[dict[str, Any]], workers: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    citation_rows: list[dict[str, Any]] = []
    total = len(tasks)
    print(f"Fetching USGS StreamStats peak-flow statistics for {total} stations with {workers} workers", flush=True)
    if workers <= 1:
        for index, task in enumerate(tasks, start=1):
            row, citations = fetch_one(task)
            rows.append(row)
            citation_rows.extend(citations)
            if index == 1 or index % 50 == 0 or index == total:
                print(f"  processed {index}/{total}", flush=True)
        return rows, citation_rows

    with futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_site = {executor.submit(fetch_one, task): task["site_id"] for task in tasks}
        for index, future in enumerate(futures.as_completed(future_to_site), start=1):
            row, citations = future.result()
            rows.append(row)
            citation_rows.extend(citations)
            if index == 1 or index % 50 == 0 or index == total:
                print(f"  processed {index}/{total}", flush=True)
    return rows, citation_rows


def insert_usgs_columns_near_flood_proxy(frame: pd.DataFrame) -> pd.DataFrame:
    desired: list[str] = []
    used: set[str] = set()
    for col in frame.columns:
        if col in used:
            continue
        desired.append(col)
        used.add(col)
        match = re.fullmatch(r"flood_ari(\d+)", col)
        if not match:
            continue
        period = int(match.group(1))
        for extra in [
            f"usgs_flood_ari{period}",
            f"usgs_flood_ari{period}_cfs",
            f"usgs_to_camelsh_flood_ari{period}",
            f"camelsh_minus_usgs_flood_ari{period}",
            f"camelsh_minus_usgs_flood_ari{period}_relative",
            f"usgs_flood_ari{period}_years_of_record",
            f"usgs_flood_ari{period}_citation_id",
        ]:
            if extra in frame.columns and extra not in used:
                desired.append(extra)
                used.add(extra)
    desired.extend(col for col in frame.columns if col not in used)
    return frame.reindex(columns=desired)


def main() -> None:
    args = parse_args()
    table_dir = args.output_dir / "reference_comparison" / "usgs_flood" / "tables"
    metadata_dir = args.output_dir / "reference_comparison" / "usgs_flood" / "metadata"
    table_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = args.cache_dir or args.output_dir / "cache" / "usgs_streamstats"
    cache_dir.mkdir(parents=True, exist_ok=True)
    output_csv = args.output_csv or table_dir / "return_period_reference_table_with_usgs.csv"

    reference = pd.read_csv(args.input_csv, dtype={"gauge_id": str})
    reference["gauge_id"] = reference["gauge_id"].map(normalize_site_id)
    reference = reference.drop_duplicates("gauge_id").sort_values("gauge_id").reset_index(drop=True)
    if args.limit is not None:
        reference = reference.head(args.limit).copy()

    tasks = [
        {
            "site_id": gauge_id,
            "cache_dir": cache_dir,
            "timeout": args.timeout,
            "retries": args.retries,
            "force_refresh": args.force_refresh,
        }
        for gauge_id in reference["gauge_id"].tolist()
    ]
    rows, citation_rows = run_fetches(tasks, workers=max(1, args.workers))

    usgs = pd.DataFrame(rows)
    citations = pd.DataFrame(citation_rows)
    merged = reference.merge(usgs, on="gauge_id", how="left")
    for period in RETURN_PERIOD_TO_PFS_CODE:
        if f"usgs_flood_ari{period}" not in merged.columns:
            continue
        camelsh = pd.to_numeric(merged.get(f"flood_ari{period}"), errors="coerce")
        usgs_values = pd.to_numeric(merged[f"usgs_flood_ari{period}"], errors="coerce")
        merged[f"usgs_to_camelsh_flood_ari{period}"] = usgs_values / camelsh
        merged[f"camelsh_minus_usgs_flood_ari{period}"] = camelsh - usgs_values
        merged[f"camelsh_minus_usgs_flood_ari{period}_relative"] = (camelsh - usgs_values) / usgs_values
    merged = insert_usgs_columns_near_flood_proxy(merged)

    citation_path = metadata_dir / "usgs_streamstats_peak_flow_citations.csv"
    summary_path = metadata_dir / "usgs_streamstats_peak_flow_summary.json"
    merged.to_csv(output_csv, index=False)
    citations.to_csv(citation_path, index=False)

    status_counts = usgs["usgs_peak_flow_fetch_status"].value_counts(dropna=False).to_dict()
    selected_period_counts = {
        str(period): int(pd.to_numeric(usgs.get(f"usgs_flood_ari{period}"), errors="coerce").notna().sum())
        for period in RETURN_PERIOD_TO_PFS_CODE
    }
    summary = {
        "input_csv": str(args.input_csv),
        "output_csv": str(output_csv),
        "citation_csv": str(citation_path),
        "cache_dir": str(cache_dir),
        "station_count": int(len(reference)),
        "status_counts": status_counts,
        "selected_period_counts": selected_period_counts,
        "source": "USGS StreamStats GageStats Services station Peak-Flow Statistics (PFS)",
        "service_url_template": GAGESTATS_STATION_URL,
        "unit_conversion": {"ft3_per_s_to_m3_per_s": CFS_TO_CMS},
        "return_period_to_usgs_pfs_code": RETURN_PERIOD_TO_PFS_CODE,
    }
    summary_path.write_text(json.dumps(json_safe(summary), indent=2), encoding="utf-8")

    print(f"Wrote merged table: {output_csv}", flush=True)
    print(f"Wrote citation table: {citation_path}", flush=True)
    print(f"Wrote summary: {summary_path}", flush=True)
    print(json.dumps(json_safe(summary), indent=2), flush=True)


if __name__ == "__main__":
    main()
