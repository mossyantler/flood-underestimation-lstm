#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "requests>=2.31",
#   "scipy>=1.13",
#   "matplotlib>=3.9",
# ]
# ///
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[3]

DEFAULT_DRBC_SELECTED = ROOT / "output/basin/drbc/basin_define/camelsh_drbc_selected.csv"
DEFAULT_STATIC_ATTRS = ROOT / "data/CAMELSH_generic/drbc_holdout_broad/attributes/static_attributes.csv"
DEFAULT_OUTPUT_DIR = ROOT / "output/model_analysis/confirmed_flood/coverage"

USGS_SITE_API = "https://waterservices.usgs.gov/nwis/site/"
NWPS_API = "https://api.water.noaa.gov/nwps/v1/gauges/{lid}"
USGS_RATINGS_API = "https://waterdata.usgs.gov/nwisweb/get_ratings"
CFS_TO_CMS = 0.028316846592
REQUEST_DELAY = 0.5

BIAS_ATTRIBUTES = ["drain_sqkm_attr", "slope_mean", "aridity", "snow_fraction", "baseflow_index"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Check NWS flood stage coverage for DRBC holdout basins.")
    p.add_argument("--drbc-selected", type=Path, default=DEFAULT_DRBC_SELECTED)
    p.add_argument("--static-attrs", type=Path, default=DEFAULT_STATIC_ATTRS)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--limit", type=int, default=None, help="Limit gauge count for smoke test.")
    p.add_argument("--request-delay", type=float, default=REQUEST_DELAY)
    return p.parse_args()


def fetch_usgs_site_info(gauge_ids: list[str], delay: float) -> pd.DataFrame:
    """USGS site API로 nws_id, county_cd, state_cd 조회. 50개씩 배치 처리."""
    records = []
    batch_size = 50
    for i in range(0, len(gauge_ids), batch_size):
        batch = gauge_ids[i : i + batch_size]
        params = {
            "format": "rdb",
            "sites": ",".join(batch),
            "siteOutput": "expanded",
            "siteType": "ST",
        }
        resp = requests.get(USGS_SITE_API, params=params, timeout=30)
        resp.raise_for_status()
        lines = [ln for ln in resp.text.splitlines() if not ln.startswith("#")]
        if len(lines) < 3:
            continue
        headers = lines[0].split("\t")
        for line in lines[2:]:  # line[1]은 형식 행
            if not line.strip():
                continue
            row = dict(zip(headers, line.split("\t")))
            site_no = row.get("site_no", "").strip().zfill(8)
            state_cd = row.get("state_cd", "").strip().zfill(2)
            county_cd = row.get("county_cd", "").strip().zfill(3)
            county_fips = (state_cd + county_cd) if (state_cd and county_cd) else None
            records.append({"usgs_id": site_no, "county_fips": county_fips})
        time.sleep(delay)
    return pd.DataFrame(records).set_index("usgs_id")


def fetch_nwps_flood_stages(identifier: str, delay: float) -> dict[str, float | None | str]:
    """NWPS API로 LID + minor/moderate/major stage(feet) 반환.
    identifier는 NWS LID 또는 USGS ID 모두 사용 가능."""
    url = NWPS_API.format(lid=identifier)
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 404:
            return {"lid": None, "minor": None, "moderate": None, "major": None}
        resp.raise_for_status()
        data = resp.json()
        lid = data.get("lid") or None
        flood = data.get("flood", {})
        cats = flood.get("categories", {})

        def _stage(key: str) -> float | None:
            val = cats.get(key, {}).get("stage") if isinstance(cats.get(key), dict) else cats.get(key)
            # NWPS는 데이터 없음을 -9999로 표기
            if val is None or val == -9999:
                return None
            return float(val)

        return {"lid": lid, "minor": _stage("minor"), "moderate": _stage("moderate"), "major": _stage("major")}
    except Exception:
        return {"lid": None, "minor": None, "moderate": None, "major": None}
    finally:
        time.sleep(delay)


def stage_to_discharge_cms(usgs_id: str, stage_ft: float | None, delay: float) -> float | None:
    """USGS EXSA rating curve 보간으로 stage(ft) → discharge(cms) 변환.
    EXSA 형식: INDEP(stage) + SHIFT = 실효 stage, DEP = discharge(cfs)."""
    if stage_ft is None:
        return None
    params = {"site_no": usgs_id, "file_type": "exsa"}
    try:
        resp = requests.get(USGS_RATINGS_API, params=params, timeout=20)
        resp.raise_for_status()
        lines = [ln for ln in resp.text.splitlines() if not ln.startswith("#") and ln.strip()]
        effective_stages, flows = [], []
        skip_next = False
        for ln in lines:
            if ln.startswith("INDEP"):
                skip_next = True  # 다음 행은 형식 행
                continue
            if skip_next:
                skip_next = False
                continue
            parts = ln.split("\t")
            if len(parts) >= 3:
                try:
                    indep = float(parts[0])
                    shift = float(parts[1])
                    dep = float(parts[2])
                    effective_stages.append(indep + shift)
                    flows.append(dep)
                except ValueError:
                    continue
        if len(effective_stages) < 2:
            return None
        discharge_cfs = float(np.interp(stage_ft, effective_stages, flows))
        return discharge_cfs * CFS_TO_CMS
    except Exception:
        return None
    finally:
        time.sleep(delay)


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Load DRBC selected basins
    drbc = pd.read_csv(args.drbc_selected, dtype={"gauge_id": str})
    drbc = drbc[drbc["selected"] == True].copy()
    gauge_ids = drbc["gauge_id"].str.zfill(8).tolist()

    if args.limit is not None:
        gauge_ids = gauge_ids[: args.limit]
        print(f"[smoke] Limiting to {args.limit} gauges: {gauge_ids}")

    # USGS site API: county_fips 전용 (NOAA Storm Events 매칭에 필요)
    print(f"Fetching USGS site info for {len(gauge_ids)} gauges ...")
    site_info = fetch_usgs_site_info(gauge_ids, args.request_delay)

    # NWPS: USGS ID를 identifier로 직접 호출 (LID 사전 조회 불필요)
    rows = []
    for usgs_id in gauge_ids:
        county_fips = site_info.loc[usgs_id, "county_fips"] if usgs_id in site_info.index else None

        print(f"  [{gauge_ids.index(usgs_id)+1}/{len(gauge_ids)}] NWPS lookup for {usgs_id} ...")
        nwps = fetch_nwps_flood_stages(usgs_id, args.request_delay)
        nws_lid = nwps["lid"]

        row: dict = {
            "usgs_id": usgs_id,
            "nws_lid": nws_lid,
            "county_fips": county_fips,
            "minor_stage_ft": nwps["minor"],
            "moderate_stage_ft": nwps["moderate"],
            "major_stage_ft": nwps["major"],
            "minor_discharge_cms": None,
            "moderate_discharge_cms": None,
            "major_discharge_cms": None,
            "coverage_status": "no_nwps_coverage",
        }

        if any(nwps[k] is not None for k in ("minor", "moderate", "major")):
            row["coverage_status"] = "has_flood_stage"
            for level in ("minor", "moderate", "major"):
                row[f"{level}_discharge_cms"] = stage_to_discharge_cms(
                    usgs_id, nwps[level], args.request_delay
                )
        elif nws_lid is not None:
            # NWPS에 등록됐지만 flood stage 임계값 없음
            row["coverage_status"] = "nwps_registered_no_stage"

        rows.append(row)

    result_df = pd.DataFrame(rows)

    out_csv = args.output_dir / "nws_flood_stage_coverage.csv"
    result_df.to_csv(out_csv, index=False)
    print(f"\nWrote: {out_csv}")
    print(f"Rows: {len(result_df)}")
    print(result_df["coverage_status"].value_counts().to_string())


if __name__ == "__main__":
    main()
