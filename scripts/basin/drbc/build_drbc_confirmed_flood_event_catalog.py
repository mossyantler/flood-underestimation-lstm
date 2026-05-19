#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "xarray>=2024.1",
#   "netCDF4>=1.6",
#   "requests>=2.31",
# ]
# ///
"""DRBC confirmed flood event catalog 구축.

NWS flood stage 커버리지가 있는 basin의 CAMELSH 시계열에서
minor stage 초과 구간을 독립 event로 추출한다.

데이터 소스 우선순위:
  1. data/CAMELSH_generic/drbc_holdout_broad/time_series/{id}.nc  (NH 포맷, 전체 변수)
  2. USGS NWIS instantaneous discharge API  (discharge만, forcing_coverage_min=None)
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[3]

DEFAULT_COVERAGE_CSV = ROOT / "output/model_analysis/confirmed_flood/coverage/nws_flood_stage_coverage.csv"
DEFAULT_DATA_DIR = ROOT / "data/CAMELSH_generic/drbc_holdout_broad/time_series"
DEFAULT_OUTPUT_DIR = ROOT / "output/model_analysis/confirmed_flood/catalog"

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
USGS_IV_API = "https://waterservices.usgs.gov/nwis/iv/"
REQUEST_DELAY = 0.3


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--coverage-csv", type=Path, default=DEFAULT_COVERAGE_CSV)
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--limit-basins", type=int, default=None, help="Smoke test용 basin 수 제한")
    p.add_argument("--request-delay", type=float, default=REQUEST_DELAY)
    return p.parse_args()


# ── NC-기반 추출 ──────────────────────────────────────────────────────────────

def _assign_tier(peak_cms: float, minor_cms: float, moderate_cms: float | None, major_cms: float | None) -> str:
    if major_cms is not None and peak_cms >= major_cms:
        return "major"
    if moderate_cms is not None and peak_cms >= moderate_cms:
        return "moderate"
    return "minor"


def _event_forcing_coverage(ds, start: pd.Timestamp, end: pd.Timestamp) -> float:
    """event 구간의 forcing 변수 최소 coverage."""
    n_hours = max(int((end - start).total_seconds() / 3600), 1)
    min_cov = 1.0
    for var in FORCING_VARS:
        if var not in ds:
            return 0.0
        s = ds[var].to_series().loc[start:end]
        s = s[~((s.index >= EXCLUDE_START) & (s.index <= EXCLUDE_END))]
        min_cov = min(min_cov, s.notna().sum() / n_hours)
    return min_cov


def _scan_events(
    q: pd.Series,
    minor_cms: float,
    moderate_cms: float | None,
    major_cms: float | None,
    usgs_id: str,
    ds=None,
    ts_start: pd.Timestamp | None = None,
) -> list[dict]:
    """discharge series에서 minor stage 초과 event 추출."""
    events: list[dict] = []
    above = q >= minor_cms
    in_event = False
    event_start: pd.Timestamp | None = None
    last_above: pd.Timestamp | None = None

    for t, is_above in above.items():
        if is_above:
            if not in_event:
                in_event = True
                event_start = t
            last_above = t
        else:
            if in_event and last_above is not None:
                gap_h = (t - last_above).total_seconds() / 3600
                if gap_h >= EVENT_GAP_HOURS:
                    ev_q = q.loc[event_start:last_above]
                    peak_time = ev_q.idxmax()
                    peak_cms = float(ev_q.max())

                    # warmup 가능 여부
                    series_start = ts_start if ts_start is not None else q.index[0]
                    warmup_start = peak_time - pd.Timedelta(days=WARMUP_DAYS + 1)
                    if warmup_start < series_start:
                        in_event = False
                        continue

                    # forcing coverage 체크 (NC 있을 때만)
                    if ds is not None:
                        ev_cover = _event_forcing_coverage(ds, event_start, last_above)
                        if ev_cover < FORCING_COVERAGE_MIN:
                            in_event = False
                            continue
                    else:
                        ev_cover = None  # USGS NWIS fallback: 미확인

                    tier = _assign_tier(peak_cms, minor_cms, moderate_cms, major_cms)
                    tier_limited = moderate_cms is None
                    pt_naive = peak_time.tz_localize(None) if hasattr(peak_time, "tz_localize") else peak_time
                    period = "pre_2000" if peak_time < EXCLUDE_START else "post_2013"
                    events.append({
                        "usgs_id": usgs_id,
                        "peak_time": pt_naive.isoformat(),
                        "peak_discharge_cms": peak_cms,
                        "flood_tier": tier,
                        "tier_limited": tier_limited,
                        "noaa_corroborated": False,
                        "period": period,
                        "forcing_coverage_min": ev_cover,
                        "data_source": "nc" if ds is not None else "usgs_nwis",
                    })
                    in_event = False

    return events


def extract_events_from_nc(
    usgs_id: str,
    data_dir: Path,
    minor_cms: float,
    moderate_cms: float | None,
    major_cms: float | None,
) -> list[dict]:
    """NH 포맷 NC에서 flood event 추출."""
    try:
        import xarray as xr
    except ImportError:
        return []

    nc_path = data_dir / f"{usgs_id}.nc"
    if not nc_path.exists():
        return []
    try:
        ds = xr.open_dataset(nc_path)
        q = ds["Streamflow"].to_series()
        # UTC timezone 정규화
        if q.index.tz is None:
            q.index = q.index.tz_localize("UTC")
        # 제외 기간 + 유효 범위 마스크
        mask_excl = (q.index >= EXCLUDE_START) & (q.index <= EXCLUDE_END)
        mask_range = (q.index >= DATA_START) & (q.index <= DATA_END)
        q = q[mask_range & ~mask_excl].dropna()
        if q.empty:
            ds.close()
            return []
        ts_start = q.index[0]
        events = _scan_events(q, minor_cms, moderate_cms, major_cms, usgs_id, ds=ds, ts_start=ts_start)
        ds.close()
        return events
    except Exception as e:
        print(f"  [NC error] {usgs_id}: {e}")
        return []


# ── USGS NWIS 폴백 ─────────────────────────────────────────────────────────────

def _fetch_usgs_discharge(usgs_id: str, delay: float) -> pd.Series:
    """USGS NWIS IV API로 hourly discharge(m³/s) 시계열 조회.

    1980-2024 전체 기간을 1년 단위로 분할 요청 (API 제한 대응).
    Returns Series indexed by UTC timestamp.
    """
    CFS_TO_CMS = 0.028316846592
    records: list[tuple[pd.Timestamp, float]] = []

    for year in range(1980, 2025):
        params = {
            "format": "json",
            "sites": usgs_id,
            "parameterCd": "00060",
            "startDT": f"{year}-01-01T00:00:00",
            "endDT": f"{year}-12-31T23:59:59",
            "siteStatus": "all",
        }
        try:
            resp = requests.get(USGS_IV_API, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            ts_list = data.get("value", {}).get("timeSeries", [])
            if not ts_list:
                time.sleep(delay)
                continue
            for ts in ts_list:
                for v in ts.get("values", [{}])[0].get("value", []):
                    try:
                        t = pd.Timestamp(v["dateTime"]).tz_convert("UTC")
                        val = float(v["value"])
                        if val >= 0:
                            records.append((t, val * CFS_TO_CMS))
                    except (ValueError, KeyError):
                        continue
        except Exception:
            pass
        finally:
            time.sleep(delay)

    if not records:
        return pd.Series(dtype=float)
    idx, vals = zip(*records)
    s = pd.Series(vals, index=pd.DatetimeIndex(idx))
    # 1시간 단위로 reindex (중복 제거 + 리샘플)
    s = s[~s.index.duplicated(keep="first")]
    return s.sort_index()


def extract_events_from_nwis(
    usgs_id: str,
    minor_cms: float,
    moderate_cms: float | None,
    major_cms: float | None,
    delay: float,
) -> list[dict]:
    """USGS NWIS IV에서 discharge 다운로드 후 event 추출."""
    print(f"    [NWIS fallback] Fetching {usgs_id} discharge 1980-2024 ...")
    q = _fetch_usgs_discharge(usgs_id, delay)
    if q.empty:
        print(f"    [NWIS] No data for {usgs_id}")
        return []
    # 제외 기간 제거
    mask_excl = (q.index >= EXCLUDE_START) & (q.index <= EXCLUDE_END)
    mask_range = (q.index >= DATA_START) & (q.index <= DATA_END)
    q = q[mask_range & ~mask_excl].dropna()
    if q.empty:
        return []
    ts_start = q.index[0]
    events = _scan_events(q, minor_cms, moderate_cms, major_cms, usgs_id, ds=None, ts_start=ts_start)
    print(f"    [NWIS] {usgs_id}: {len(events)} events found")
    return events


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # NWS 커버리지 있는 basin 로드
    cov = pd.read_csv(args.coverage_csv, dtype={"usgs_id": str})
    cov["usgs_id"] = cov["usgs_id"].str.zfill(8)
    covered = cov[cov["minor_discharge_cms"].notna()].copy()

    if args.limit_basins is not None:
        covered = covered.head(args.limit_basins)
        print(f"[smoke] {args.limit_basins}개 basin으로 제한")

    print(f"Processing {len(covered)} covered basins ...")

    all_events: list[dict] = []
    stats = {"nc": 0, "nwis": 0, "skipped": 0}

    for _, row in covered.iterrows():
        usgs_id = row["usgs_id"]
        minor_cms = float(row["minor_discharge_cms"])
        moderate_cms = float(row["moderate_discharge_cms"]) if pd.notna(row.get("moderate_discharge_cms")) else None
        major_cms = float(row["major_discharge_cms"]) if pd.notna(row.get("major_discharge_cms")) else None

        nc_path = args.data_dir / f"{usgs_id}.nc"
        if nc_path.exists():
            print(f"  [{usgs_id}] NC file → extracting ...")
            events = extract_events_from_nc(usgs_id, args.data_dir, minor_cms, moderate_cms, major_cms)
            stats["nc"] += 1
        else:
            print(f"  [{usgs_id}] No NC → USGS NWIS fallback ...")
            events = extract_events_from_nwis(usgs_id, minor_cms, moderate_cms, major_cms, args.request_delay)
            stats["nwis"] += 1

        print(f"    → {len(events)} events")
        all_events.extend(events)

    df = pd.DataFrame(all_events)
    out_csv = args.output_dir / "drbc_confirmed_flood_event_catalog.csv"
    if df.empty:
        df = pd.DataFrame(columns=[
            "usgs_id", "peak_time", "peak_discharge_cms", "flood_tier",
            "tier_limited", "noaa_corroborated", "period",
            "forcing_coverage_min", "data_source",
        ])
    df.to_csv(out_csv, index=False)

    print(f"\nWrote: {out_csv}")
    print(f"Total events: {len(df)}")
    if not df.empty:
        print(df["flood_tier"].value_counts().to_string())
        print(df["period"].value_counts().to_string())
        print(df["data_source"].value_counts().to_string())
    print(f"Basins — NC: {stats['nc']}, NWIS fallback: {stats['nwis']}")


if __name__ == "__main__":
    main()
