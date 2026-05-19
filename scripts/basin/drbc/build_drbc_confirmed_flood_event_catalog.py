#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "pyarrow>=16.0",
#   "requests>=2.31",
#   "xarray>=2024.1",
#   "netCDF4>=1.6",
# ]
# ///
"""DRBC confirmed flood event catalog 구축.

NWS flood stage 커버리지가 있는 basin의 CAMELSH NC 시계열에서
minor stage 초과 구간을 독립 event로 추출한다.

NC 파일 위치: data/CAMELSH_generic/drbc_holdout_broad/time_series/{usgs_id}.nc
NC 파일이 없는 basin은 건너뛴다. NC 파일 준비:
  uv run scripts/data/prepare_camelsh_generic_dataset.py \\
    --profile broad_all_drbc --download-if-missing
"""
from __future__ import annotations

import argparse
import gzip
import io
import re
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import xarray as xr

ROOT = Path(__file__).resolve().parents[3]

DEFAULT_COVERAGE_CSV = ROOT / "output/model_analysis/confirmed_flood/coverage/nws_flood_stage_coverage.csv"
DEFAULT_DATA_DIR = ROOT / "data/CAMELSH_generic/drbc_holdout_broad/time_series"
DEFAULT_OUTPUT_DIR = ROOT / "output/model_analysis/confirmed_flood/catalog"
DEFAULT_NOAA_CACHE = ROOT / "output/model_analysis/confirmed_flood/noaa_cache"

NOAA_BASE_URL = "https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/"
NOAA_FLOOD_TYPES = {"Flood", "Flash Flood", "Coastal Flood"}

EXCLUDE_START = pd.Timestamp("2000-01-01", tz="UTC")
EXCLUDE_END = pd.Timestamp("2013-12-31 23:59:59", tz="UTC")
DATA_START = pd.Timestamp("1980-01-01", tz="UTC")
DATA_END = pd.Timestamp("2024-12-31 23:59:59", tz="UTC")
EVENT_GAP_HOURS = 72
FORCING_COVERAGE_MIN = 0.90
WARMUP_DAYS = 21
FORCING_VARS = [
    "Rainf", "Tair", "PotEvap", "SWdown", "Qair",
    "PSurf", "Wind_E", "Wind_N", "LWdown", "CAPE", "CRainf_frac",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--coverage-csv", type=Path, default=DEFAULT_COVERAGE_CSV)
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--limit-basins", type=int, default=None, help="Smoke test용 basin 수 제한")
    p.add_argument("--noaa-cache", type=Path, default=DEFAULT_NOAA_CACHE)
    p.add_argument("--skip-noaa", action="store_true", help="NOAA annotation 건너뜀")
    return p.parse_args()


def _get_time_index(ds: xr.Dataset) -> pd.DatetimeIndex:
    """NC 파일의 시간 좌표를 UTC DatetimeIndex로 반환."""
    time_coord = None
    for name in ("time", "date", "datetime"):
        if name in ds.coords or name in ds.dims:
            time_coord = ds[name]
            break
    if time_coord is None:
        # 첫 번째 dim을 time으로 가정
        first_dim = list(ds.dims)[0]
        time_coord = ds[first_dim]
    idx = pd.DatetimeIndex(time_coord.values)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    return idx


def _event_forcing_coverage(ds: xr.Dataset, time_idx: pd.DatetimeIndex,
                             start: pd.Timestamp, end: pd.Timestamp) -> float:
    """event 구간의 forcing 변수 최소 coverage."""
    n_hours = max(int((end - start).total_seconds() / 3600), 1)
    min_cov = 1.0
    mask_event = (time_idx >= start) & (time_idx <= end)
    for var in FORCING_VARS:
        if var not in ds:
            return 0.0
        vals = ds[var].values[mask_event]
        n_valid = int(np.sum(~np.isnan(vals)))
        min_cov = min(min_cov, n_valid / n_hours)
    return min_cov


def _assign_tier(peak_cms: float, moderate_cms: float | None, major_cms: float | None) -> str:
    if major_cms is not None and peak_cms >= major_cms:
        return "major"
    if moderate_cms is not None and peak_cms >= moderate_cms:
        return "moderate"
    return "minor"


def load_noaa_storm_events(years: list[int], cache_dir: Path) -> pd.DataFrame:
    """NOAA NCEI Storm Events CSV를 연도별 다운로드/캐시 후 Flood 유형만 반환."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    index_html: str | None = None

    for year in years:
        cache_path = cache_dir / f"storm_events_{year}.parquet"
        if cache_path.exists():
            frames.append(pd.read_parquet(cache_path))
            continue
        if index_html is None:
            resp = requests.get(NOAA_BASE_URL, timeout=30)
            resp.raise_for_status()
            index_html = resp.text

        pattern = rf"StormEvents_details-ftp_v1\.0_d{year}_c\d+\.csv\.gz"
        matches = re.findall(pattern, index_html)
        if not matches:
            print(f"  [NOAA] {year}: 파일 없음")
            continue
        filename = sorted(matches)[-1]
        print(f"  [NOAA] Downloading {filename} ...")
        gz_resp = requests.get(NOAA_BASE_URL + filename, timeout=120)
        gz_resp.raise_for_status()
        df = pd.read_csv(
            io.StringIO(gzip.decompress(gz_resp.content).decode("latin-1")),
            usecols=["BEGIN_YEARMONTH", "BEGIN_DAY", "END_YEARMONTH", "END_DAY",
                     "STATE_FIPS", "CZ_FIPS", "EVENT_TYPE"],
            dtype=str,
            low_memory=False,
        )
        df = df[df["EVENT_TYPE"].isin(NOAA_FLOOD_TYPES)].copy()
        df["county_fips"] = df["STATE_FIPS"].str.zfill(2) + df["CZ_FIPS"].str.zfill(3)
        df["begin_date"] = pd.to_datetime(
            df["BEGIN_YEARMONTH"].str[:4] + "-" + df["BEGIN_YEARMONTH"].str[4:] + "-" + df["BEGIN_DAY"].str.zfill(2),
            errors="coerce",
        )
        df["end_date"] = pd.to_datetime(
            df["END_YEARMONTH"].str[:4] + "-" + df["END_YEARMONTH"].str[4:] + "-" + df["END_DAY"].str.zfill(2),
            errors="coerce",
        )
        df = df[["county_fips", "begin_date", "end_date"]].dropna()
        df.to_parquet(cache_path, index=False)
        frames.append(df)

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["county_fips", "begin_date", "end_date"]
    )


def annotate_noaa(
    events: list[dict],
    coverage_df: pd.DataFrame,
    noaa_df: pd.DataFrame,
) -> list[dict]:
    """각 event에 noaa_corroborated boolean 부여 (county FIPS + peak ±2일 매칭)."""
    fips_map = coverage_df.set_index("usgs_id")["county_fips"].to_dict()
    for ev in events:
        county_fips = fips_map.get(ev["usgs_id"])
        if county_fips is None or noaa_df.empty:
            ev["noaa_corroborated"] = False
            continue
        peak = pd.Timestamp(ev["peak_time"])
        window_start = peak - pd.Timedelta(days=2)
        window_end = peak + pd.Timedelta(days=2)
        match = noaa_df[
            (noaa_df["county_fips"] == county_fips) &
            (noaa_df["begin_date"] <= window_end) &
            (noaa_df["end_date"] >= window_start)
        ]
        ev["noaa_corroborated"] = len(match) > 0
    return events


def extract_events_from_nc(
    usgs_id: str,
    nc_path: Path,
    minor_cms: float,
    moderate_cms: float | None,
    major_cms: float | None,
) -> list[dict]:
    """NH 포맷 NC에서 minor stage 초과 event 추출."""
    try:
        ds = xr.open_dataset(nc_path)
    except Exception as e:
        print(f"  [error] {usgs_id}: {e}")
        return []

    try:
        time_idx = _get_time_index(ds)
        q_vals = ds["Streamflow"].values.flatten()

        # 제외 기간 + 유효 범위 마스크
        mask_excl = (time_idx >= EXCLUDE_START) & (time_idx <= EXCLUDE_END)
        mask_range = (time_idx >= DATA_START) & (time_idx <= DATA_END)
        mask_valid = mask_range & ~mask_excl

        time_valid = time_idx[mask_valid]
        q_valid = q_vals[mask_valid]

        if len(q_valid) == 0:
            return []

        ts_start = time_valid[0]

        # event 스캔
        above = q_valid >= minor_cms
        events: list[dict] = []
        in_event = False
        ev_start_idx: int = 0
        last_above_idx: int = 0

        for i, is_above in enumerate(above):
            if is_above:
                if not in_event:
                    in_event = True
                    ev_start_idx = i
                last_above_idx = i
            else:
                if in_event:
                    gap_h = (time_valid[i] - time_valid[last_above_idx]).total_seconds() / 3600
                    if gap_h >= EVENT_GAP_HOURS:
                        # event 종료 처리
                        ev_q = q_valid[ev_start_idx:last_above_idx + 1]
                        peak_rel = int(np.nanargmax(ev_q))
                        peak_idx = ev_start_idx + peak_rel
                        peak_time = time_valid[peak_idx]
                        peak_cms = float(ev_q[peak_rel])

                        # warmup 가능 여부
                        warmup_start = peak_time - pd.Timedelta(days=WARMUP_DAYS + 1)
                        if warmup_start < ts_start:
                            in_event = False
                            continue

                        # forcing coverage
                        ev_cover = _event_forcing_coverage(
                            ds, time_idx,
                            time_valid[ev_start_idx], time_valid[last_above_idx]
                        )
                        if ev_cover < FORCING_COVERAGE_MIN:
                            in_event = False
                            continue

                        tier = _assign_tier(peak_cms, moderate_cms, major_cms)
                        period = "pre_2000" if peak_time < EXCLUDE_START else "post_2013"
                        pt_naive = peak_time.tz_localize(None) if hasattr(peak_time, "tz_localize") else peak_time
                        events.append({
                            "usgs_id": usgs_id,
                            "peak_time": pt_naive.isoformat(),
                            "peak_discharge_cms": peak_cms,
                            "flood_tier": tier,
                            "tier_limited": moderate_cms is None,
                            "noaa_corroborated": False,
                            "period": period,
                            "forcing_coverage_min": round(ev_cover, 4),
                        })
                        in_event = False
    finally:
        ds.close()

    return events


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    cov = pd.read_csv(args.coverage_csv, dtype={"usgs_id": str})
    cov["usgs_id"] = cov["usgs_id"].str.zfill(8)
    covered = cov[cov["minor_discharge_cms"].notna()].copy()

    if args.limit_basins is not None:
        covered = covered.head(args.limit_basins)
        print(f"[smoke] {args.limit_basins}개 basin으로 제한")

    n_total = len(covered)
    print(f"Covered basins: {n_total}")

    all_events: list[dict] = []
    skipped = 0

    for i, (_, row) in enumerate(covered.iterrows(), 1):
        usgs_id = row["usgs_id"]
        minor_cms = float(row["minor_discharge_cms"])
        moderate_cms = float(row["moderate_discharge_cms"]) if pd.notna(row.get("moderate_discharge_cms")) else None
        major_cms = float(row["major_discharge_cms"]) if pd.notna(row.get("major_discharge_cms")) else None

        nc_path = args.data_dir / f"{usgs_id}.nc"
        if not nc_path.exists():
            print(f"  [{i}/{n_total}] {usgs_id}: NC 없음, 건너뜀")
            skipped += 1
            continue

        print(f"  [{i}/{n_total}] {usgs_id}: 추출 중 ...")
        events = extract_events_from_nc(usgs_id, nc_path, minor_cms, moderate_cms, major_cms)
        print(f"    → {len(events)} events")
        all_events.extend(events)

    if all_events and not args.skip_noaa:
        peak_years = sorted({pd.Timestamp(ev["peak_time"]).year for ev in all_events})
        print(f"\nDownloading NOAA Storm Events for {len(peak_years)} years ...")
        noaa_df = load_noaa_storm_events(peak_years, args.noaa_cache)
        all_events = annotate_noaa(all_events, cov, noaa_df)
        n_corr = sum(ev["noaa_corroborated"] for ev in all_events)
        print(f"NOAA corroborated: {n_corr}/{len(all_events)} ({100*n_corr/max(len(all_events),1):.1f}%)")

    df = pd.DataFrame(all_events) if all_events else pd.DataFrame(columns=[
        "usgs_id", "peak_time", "peak_discharge_cms", "flood_tier",
        "tier_limited", "noaa_corroborated", "period", "forcing_coverage_min",
    ])
    out_csv = args.output_dir / "drbc_confirmed_flood_event_catalog.csv"
    df.to_csv(out_csv, index=False)

    print(f"\nWrote: {out_csv}")
    print(f"Total events: {len(df)}")
    print(f"Skipped (no NC): {skipped}/{n_total}")
    if not df.empty:
        print(df["flood_tier"].value_counts().to_string())
        print(df["period"].value_counts().to_string())


if __name__ == "__main__":
    main()
