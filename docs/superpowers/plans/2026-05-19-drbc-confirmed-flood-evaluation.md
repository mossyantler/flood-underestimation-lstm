# DRBC Confirmed Flood Event Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** NWS flood stage 초과 기준으로 DRBC holdout 154개 basin 전체에서 confirmed flood event를 추출하고, Model 1 vs Model 2를 실제 홍수 상황에서 비교 평가한다.

**Architecture:** 4개 스크립트의 순차 파이프라인 — (1) NWS 커버리지 확인, (2) confirmed flood event catalog 구축, (3) Model 1/2 inference, (4) 성능 분석. PostgreSQL `analysis` schema에 typed table, DuckDB에 view로 모든 산출물을 등록한다.

**Tech Stack:** Python 3.11+, uv run (PEP 723 inline deps), requests, pandas, numpy, xarray, scipy, matplotlib, neuralhydrology (vendored), psycopg2 (via psql subprocess), duckdb

**Spec:** `docs/superpowers/specs/2026-05-19-drbc-confirmed-flood-evaluation-design.md`

---

## File Structure

| 파일 | 역할 |
|------|------|
| CREATE `scripts/basin/drbc/check_drbc_nws_flood_stage_coverage.py` | USGS→NWS 매핑, flood stage fetch, rating curve 변환, 편향 분석 |
| CREATE `scripts/basin/drbc/build_drbc_confirmed_flood_event_catalog.py` | CAMELSH 시계열에서 flood event 추출, NOAA annotation |
| CREATE `scripts/model/confirmed_flood/infer_drbc_confirmed_flood_events.py` | Model 1/2 inference on confirmed flood events |
| CREATE `scripts/model/confirmed_flood/analyze_drbc_confirmed_flood_performance.py` | peak under-deficit, threshold recall, tier-stratified 분석 |
| MODIFY `database/postgres/init_camels_analysis_db.sql` | 4개 신규 테이블 DDL 추가 |
| MODIFY `database/postgres/import_camels_csvs.py` | 4개 import 함수 + routing 추가 |
| MODIFY `database/duckdb/camels_duckdb_tool.py` | 3개 view 등록 추가 |

---

## Task 1: PostgreSQL DDL — 4개 신규 테이블

**Files:**
- Modify: `database/postgres/init_camels_analysis_db.sql`

- [ ] **Step 1: 파일 끝에 4개 테이블 DDL 추가**

`init_camels_analysis_db.sql` 맨 끝(기존 VIEW 정의 위)에 추가:

```sql
-- ── Confirmed Flood Evaluation ────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS analysis.nws_flood_stage_coverage (
    usgs_id text PRIMARY KEY,
    nws_lid text,
    county_fips text,
    minor_stage_ft double precision,
    moderate_stage_ft double precision,
    major_stage_ft double precision,
    minor_discharge_cms double precision,
    moderate_discharge_cms double precision,
    major_discharge_cms double precision,
    coverage_status text NOT NULL,
    source_path text NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS analysis.nws_coverage_bias (
    attribute text NOT NULL,
    covered_n integer,
    missing_n integer,
    covered_median double precision,
    missing_median double precision,
    ks_stat double precision,
    ks_pvalue double precision,
    source_path text NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (attribute)
);

CREATE TABLE IF NOT EXISTS analysis.drbc_confirmed_flood_events (
    usgs_id text NOT NULL,
    peak_time timestamptz NOT NULL,
    peak_discharge_cms double precision,
    flood_tier text NOT NULL,
    tier_limited boolean NOT NULL DEFAULT false,
    noaa_corroborated boolean NOT NULL DEFAULT false,
    period text NOT NULL,
    forcing_coverage_min double precision,
    source_path text NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (usgs_id, peak_time)
);

CREATE INDEX IF NOT EXISTS drbc_confirmed_flood_events_usgs_id_idx
    ON analysis.drbc_confirmed_flood_events (usgs_id);

CREATE INDEX IF NOT EXISTS drbc_confirmed_flood_events_flood_tier_idx
    ON analysis.drbc_confirmed_flood_events (flood_tier);

CREATE TABLE IF NOT EXISTS analysis.drbc_confirmed_flood_performance (
    usgs_id text NOT NULL,
    peak_time timestamptz NOT NULL,
    model text NOT NULL,
    seed integer NOT NULL,
    quantile text NOT NULL,
    obs_peak_cms double precision,
    pred_peak_cms double precision,
    peak_under_deficit double precision,
    is_underestimate boolean,
    exceeds_minor_stage boolean,
    event_nrmse double precision,
    flood_tier text,
    noaa_corroborated boolean,
    source_path text NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (usgs_id, peak_time, model, seed, quantile)
);

CREATE INDEX IF NOT EXISTS drbc_confirmed_flood_performance_model_seed_idx
    ON analysis.drbc_confirmed_flood_performance (model, seed);

CREATE INDEX IF NOT EXISTS drbc_confirmed_flood_performance_flood_tier_idx
    ON analysis.drbc_confirmed_flood_performance (flood_tier);
```

- [ ] **Step 2: psql로 DDL 적용**

```bash
psql -d camels -v ON_ERROR_STOP=1 -f database/postgres/init_camels_analysis_db.sql
```

Expected: 에러 없이 완료. `CREATE TABLE` 또는 `NOTICE: ... already exists` 메시지.

- [ ] **Step 3: 테이블 존재 확인**

```bash
psql -d camels -c "\dt analysis.nws*" && psql -d camels -c "\dt analysis.drbc*"
```

Expected: 4개 테이블 모두 표시됨.

- [ ] **Step 4: 커밋**

```bash
git add database/postgres/init_camels_analysis_db.sql
git commit -m "feat: add confirmed flood evaluation DDL to postgres schema"
```

---

## Task 2: Coverage Check 스크립트 — USGS→NWS 매핑 + Flood Stage Fetch

**Files:**
- Create: `scripts/basin/drbc/check_drbc_nws_flood_stage_coverage.py`

- [ ] **Step 1: 스크립트 골격 작성 (의존성 + 상수 + argparse)**

```python
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
from scipy import stats

ROOT = Path(__file__).resolve().parents[3]

DEFAULT_DRBC_SELECTED = ROOT / "output/basin/drbc/basin_define/camelsh_drbc_selected.csv"
DEFAULT_STATIC_ATTRS = ROOT / "data/CAMELSH_generic/drbc_holdout_broad/attributes/static_attributes.csv"
DEFAULT_OUTPUT_DIR = ROOT / "output/model_analysis/confirmed_flood/coverage"

USGS_SITE_API = "https://waterservices.usgs.gov/nwis/site/"
NWPS_API = "https://api.water.noaa.gov/nwps/v1/gauges/{lid}"
USGS_RATINGS_API = "https://waterservices.usgs.gov/nwis/ratings/"
CFS_TO_CMS = 0.028316846592
REQUEST_DELAY = 0.5  # USGS rate limit 대응

BIAS_ATTRIBUTES = ["drain_sqkm_attr", "slope_mean", "aridity", "snow_fraction", "baseflow_index"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Check NWS flood stage coverage for DRBC holdout basins.")
    p.add_argument("--drbc-selected", type=Path, default=DEFAULT_DRBC_SELECTED)
    p.add_argument("--static-attrs", type=Path, default=DEFAULT_STATIC_ATTRS)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--limit", type=int, default=None, help="Limit gauge count for smoke test.")
    p.add_argument("--request-delay", type=float, default=REQUEST_DELAY)
    return p.parse_args()
```

- [ ] **Step 2: USGS site API로 NWS LID + county FIPS 조회 함수 작성**

```python
def fetch_usgs_site_info(gauge_ids: list[str], delay: float) -> pd.DataFrame:
    """USGS site API로 nws_id, county_cd, state_cd 조회. 154개 분할 배치 처리."""
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
        for line in lines[2:]:  # line[1] is format row
            if not line.strip():
                continue
            row = dict(zip(headers, line.split("\t")))
            site_no = row.get("site_no", "").strip().zfill(8)
            nws_id = row.get("nws_id", "").strip() or None
            state_cd = row.get("state_cd", "").strip().zfill(2)
            county_cd = row.get("county_cd", "").strip().zfill(3)
            county_fips = (state_cd + county_cd) if (state_cd and county_cd) else None
            records.append({"usgs_id": site_no, "nws_lid": nws_id, "county_fips": county_fips})
        time.sleep(delay)
    return pd.DataFrame(records).set_index("usgs_id")
```

- [ ] **Step 3: NWPS API로 flood stage 조회 함수 작성**

```python
def fetch_nwps_flood_stages(nws_lid: str, delay: float) -> dict[str, float | None]:
    """minor/moderate/major stage(feet) 반환. 없으면 None."""
    url = NWPS_API.format(lid=nws_lid)
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 404:
            return {"minor": None, "moderate": None, "major": None}
        resp.raise_for_status()
        data = resp.json()
        flood = data.get("flood", {})
        cats = flood.get("categories", {})
        return {
            "minor": cats.get("minor", {}).get("stage") if isinstance(cats.get("minor"), dict) else cats.get("minor"),
            "moderate": cats.get("moderate", {}).get("stage") if isinstance(cats.get("moderate"), dict) else cats.get("moderate"),
            "major": cats.get("major", {}).get("stage") if isinstance(cats.get("major"), dict) else cats.get("major"),
        }
    except Exception:
        return {"minor": None, "moderate": None, "major": None}
    finally:
        time.sleep(delay)
```

- [ ] **Step 4: USGS rating curve로 stage→discharge 변환 함수 작성**

```python
def stage_to_discharge_cms(usgs_id: str, stage_ft: float | None, delay: float) -> float | None:
    """rating curve 보간으로 stage(ft) → discharge(cms) 변환."""
    if stage_ft is None:
        return None
    url = USGS_RATINGS_API
    params = {"site": usgs_id, "format": "rdb"}
    try:
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        lines = [ln for ln in resp.text.splitlines() if not ln.startswith("#") and ln.strip()]
        # 헤더 행과 형식 행 스킵 후 데이터 파싱
        data_lines = [ln for ln in lines if not ln.startswith("INDEP") and not ln.startswith("//")]
        stages, flows = [], []
        for ln in data_lines:
            parts = ln.split("\t")
            if len(parts) >= 2:
                try:
                    stages.append(float(parts[0]))
                    flows.append(float(parts[1]))
                except ValueError:
                    continue
        if len(stages) < 2:
            return None
        discharge_cfs = float(np.interp(stage_ft, stages, flows))
        return discharge_cfs * CFS_TO_CMS
    except Exception:
        return None
    finally:
        time.sleep(delay)
```

- [ ] **Step 5: 스모크 테스트 — 알려진 gauge 1개로 함수 검증**

```bash
# 01470960 (Schuylkill River at Reading PA) — NWS forecast point 있는 것으로 알려진 gauge
python3 -c "
import sys; sys.path.insert(0, 'scripts/basin/drbc')
# 직접 함수 호출 테스트는 uv run으로 실행
"
uv run scripts/basin/drbc/check_drbc_nws_flood_stage_coverage.py --limit 3
```

Expected: `output/model_analysis/confirmed_flood/coverage/nws_flood_stage_coverage.csv` 생성, 3개 row.

- [ ] **Step 6: 커밋 (WIP)**

```bash
git add scripts/basin/drbc/check_drbc_nws_flood_stage_coverage.py
git commit -m "feat: add NWS flood stage coverage check script (API fetch)"
```

---

## Task 3: Coverage Check — 편향 분석 + 전체 출력

**Files:**
- Modify: `scripts/basin/drbc/check_drbc_nws_flood_stage_coverage.py`

- [ ] **Step 1: 커버리지 편향 분석 함수 작성**

```python
def compute_coverage_bias(
    coverage_df: pd.DataFrame,
    static_attrs: pd.DataFrame,
    attributes: list[str],
) -> pd.DataFrame:
    """covered vs missing basin의 static attribute KS-test 비교."""
    covered = coverage_df[coverage_df["coverage_status"] == "covered"]["usgs_id"].tolist()
    missing = coverage_df[coverage_df["coverage_status"] != "covered"]["usgs_id"].tolist()
    records = []
    for attr in attributes:
        if attr not in static_attrs.columns:
            continue
        a = static_attrs.loc[static_attrs.index.isin(covered), attr].dropna().values
        b = static_attrs.loc[static_attrs.index.isin(missing), attr].dropna().values
        if len(a) == 0 or len(b) == 0:
            continue
        ks_stat, ks_pvalue = stats.ks_2samp(a, b)
        records.append({
            "attribute": attr,
            "covered_n": len(a),
            "missing_n": len(b),
            "covered_median": float(np.median(a)),
            "missing_median": float(np.median(b)),
            "ks_stat": float(ks_stat),
            "ks_pvalue": float(ks_pvalue),
        })
    return pd.DataFrame(records)
```

- [ ] **Step 2: 편향 분석 figure 생성 함수 작성**

```python
import matplotlib.pyplot as plt

def plot_coverage_bias(
    coverage_df: pd.DataFrame,
    static_attrs: pd.DataFrame,
    attributes: list[str],
    output_path: Path,
) -> None:
    covered_ids = coverage_df[coverage_df["coverage_status"] == "covered"]["usgs_id"].tolist()
    missing_ids = coverage_df[coverage_df["coverage_status"] != "covered"]["usgs_id"].tolist()

    fig, axes = plt.subplots(1, len(attributes), figsize=(4 * len(attributes), 4))
    for ax, attr in zip(axes, attributes):
        if attr not in static_attrs.columns:
            continue
        a = static_attrs.loc[static_attrs.index.isin(covered_ids), attr].dropna().values
        b = static_attrs.loc[static_attrs.index.isin(missing_ids), attr].dropna().values
        ax.boxplot([a, b], labels=["covered", "missing"])
        ax.set_title(attr, fontsize=9)
        ax.set_xlabel("")
    fig.suptitle("NWS Coverage Bias: Covered vs Missing Basins", fontsize=11)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
```

- [ ] **Step 3: main() 함수 작성 — 전체 흐름 연결**

```python
def main() -> None:
    args = parse_args()
    drbc = pd.read_csv(args.drbc_selected)
    drbc = drbc[drbc["selected"] == True].copy()
    gauge_ids = drbc["gauge_id"].astype(str).str.zfill(8).tolist()
    if args.limit:
        gauge_ids = gauge_ids[: args.limit]

    print(f"[1/4] Fetching USGS site info for {len(gauge_ids)} gauges...")
    site_info = fetch_usgs_site_info(gauge_ids, args.request_delay)

    print("[2/4] Fetching NWPS flood stages...")
    rows = []
    for usgs_id in gauge_ids:
        info = site_info.loc[usgs_id] if usgs_id in site_info.index else {}
        nws_lid = info.get("nws_lid") if hasattr(info, "get") else None
        county_fips = info.get("county_fips") if hasattr(info, "get") else None
        stages = fetch_nwps_flood_stages(nws_lid, args.request_delay) if nws_lid else {"minor": None, "moderate": None, "major": None}

        minor_cms = stage_to_discharge_cms(usgs_id, stages["minor"], args.request_delay)
        moderate_cms = stage_to_discharge_cms(usgs_id, stages["moderate"], args.request_delay)
        major_cms = stage_to_discharge_cms(usgs_id, stages["major"], args.request_delay)

        status = "covered" if minor_cms is not None else ("no_rating_curve" if stages["minor"] is not None else ("no_nws_lid" if nws_lid is None else "no_flood_stage"))
        rows.append({
            "usgs_id": usgs_id,
            "nws_lid": nws_lid,
            "county_fips": county_fips,
            "minor_stage_ft": stages["minor"],
            "moderate_stage_ft": stages["moderate"],
            "major_stage_ft": stages["major"],
            "minor_discharge_cms": minor_cms,
            "moderate_discharge_cms": moderate_cms,
            "major_discharge_cms": major_cms,
            "coverage_status": status,
        })

    coverage_df = pd.DataFrame(rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    coverage_csv = args.output_dir / "nws_flood_stage_coverage.csv"
    coverage_df.to_csv(coverage_csv, index=False)

    n_covered = (coverage_df["coverage_status"] == "covered").sum()
    print(f"[3/4] Coverage: {n_covered}/{len(gauge_ids)} gauges have minor stage discharge")
    if n_covered < 70:
        print("WARNING: coverage < 70 — consider hybrid fallback (see spec)")

    print("[4/4] Computing coverage bias analysis...")
    static_attrs = pd.read_csv(args.static_attrs, index_col=0)
    static_attrs.index = static_attrs.index.astype(str).str.zfill(8)
    bias_df = compute_coverage_bias(coverage_df, static_attrs, BIAS_ATTRIBUTES)
    bias_csv = args.output_dir / "coverage_bias_report.csv"
    bias_df.to_csv(bias_csv, index=False)
    plot_coverage_bias(
        coverage_df, static_attrs, BIAS_ATTRIBUTES,
        args.output_dir / "figures" / "coverage_bias_distributions.png",
    )
    print(f"Done. Coverage CSV: {coverage_csv}")
    print(f"       Bias CSV:    {bias_csv}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 전체 스크립트 실행 (전체 154개)**

```bash
uv run scripts/basin/drbc/check_drbc_nws_flood_stage_coverage.py
```

Expected:
- `output/model_analysis/confirmed_flood/coverage/nws_flood_stage_coverage.csv` — 154 rows
- `output/model_analysis/confirmed_flood/coverage/coverage_bias_report.csv` — 5 rows (attribute별)
- `output/model_analysis/confirmed_flood/coverage/figures/coverage_bias_distributions.png`
- 콘솔에 커버리지 count 출력

- [ ] **Step 5: 커버리지 count 확인 및 hybrid 여부 결정**

```bash
python3 -c "
import pandas as pd
df = pd.read_csv('output/model_analysis/confirmed_flood/coverage/nws_flood_stage_coverage.csv')
print(df['coverage_status'].value_counts())
print(f'Covered: {(df.coverage_status == \"covered\").sum()} / {len(df)}')
"
```

결과에 따라: covered ≥ 120이면 다음 Task로, 70-119이면 limitation 메모, < 70이면 hybrid 방식으로 전환.

- [ ] **Step 6: 커밋**

```bash
git add scripts/basin/drbc/check_drbc_nws_flood_stage_coverage.py
git commit -m "feat: complete NWS flood stage coverage check with bias analysis"
```

---

## Task 4: PostgreSQL Import + DuckDB View — Coverage

**Files:**
- Modify: `database/postgres/import_camels_csvs.py`
- Modify: `database/duckdb/camels_duckdb_tool.py`

- [ ] **Step 1: import_camels_csvs.py에 상수 경로 추가**

파일 상단 기존 경로 상수들 아래에 추가:

```python
NWS_FLOOD_STAGE_COVERAGE = Path("output/model_analysis/confirmed_flood/coverage/nws_flood_stage_coverage.csv")
NWS_COVERAGE_BIAS = Path("output/model_analysis/confirmed_flood/coverage/coverage_bias_report.csv")
DRBC_CONFIRMED_FLOOD_EVENTS = Path("output/model_analysis/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv")
DRBC_CONFIRMED_FLOOD_PERFORMANCE = Path("output/model_analysis/confirmed_flood/performance/drbc_confirmed_flood_performance.csv")
```

기존 `DEFAULT_CSVS` 리스트에도 4개 추가:

```python
DEFAULT_CSVS = [
    # ... 기존 항목들 ...
    NWS_FLOOD_STAGE_COVERAGE,
    NWS_COVERAGE_BIAS,
    DRBC_CONFIRMED_FLOOD_EVENTS,
    DRBC_CONFIRMED_FLOOD_PERFORMANCE,
]
```

- [ ] **Step 2: coverage import 함수 2개 추가**

기존 `import_probabilistic_tail_spread` 함수 아래에 추가:

```python
def import_nws_flood_stage_coverage(database: str, relative_path: Path, rows: list[dict[str, str]]) -> None:
    source_path = str(REPO_ROOT / relative_path)
    copy_rows = [
        [
            to_text(r.get("usgs_id")),
            to_text(r.get("nws_lid")),
            to_text(r.get("county_fips")),
            to_float(r.get("minor_stage_ft")),
            to_float(r.get("moderate_stage_ft")),
            to_float(r.get("major_stage_ft")),
            to_float(r.get("minor_discharge_cms")),
            to_float(r.get("moderate_discharge_cms")),
            to_float(r.get("major_discharge_cms")),
            to_text(r.get("coverage_status")),
            source_path,
        ]
        for r in rows
    ]
    import_mapped_table(
        database,
        "analysis.nws_flood_stage_coverage",
        ["usgs_id","nws_lid","county_fips","minor_stage_ft","moderate_stage_ft","major_stage_ft",
         "minor_discharge_cms","moderate_discharge_cms","major_discharge_cms","coverage_status","source_path"],
        copy_rows,
        conflict_target="(usgs_id)",
        conflict_action="DO UPDATE SET minor_discharge_cms=EXCLUDED.minor_discharge_cms, coverage_status=EXCLUDED.coverage_status, imported_at=now()",
    )


def import_nws_coverage_bias(database: str, relative_path: Path, rows: list[dict[str, str]]) -> None:
    source_path = str(REPO_ROOT / relative_path)
    copy_rows = [
        [
            to_text(r.get("attribute")),
            to_int(r.get("covered_n")),
            to_int(r.get("missing_n")),
            to_float(r.get("covered_median")),
            to_float(r.get("missing_median")),
            to_float(r.get("ks_stat")),
            to_float(r.get("ks_pvalue")),
            source_path,
        ]
        for r in rows
    ]
    import_mapped_table(
        database,
        "analysis.nws_coverage_bias",
        ["attribute","covered_n","missing_n","covered_median","missing_median","ks_stat","ks_pvalue","source_path"],
        copy_rows,
        conflict_target="(attribute)",
        conflict_action="DO UPDATE SET ks_stat=EXCLUDED.ks_stat, ks_pvalue=EXCLUDED.ks_pvalue, imported_at=now()",
    )
```

- [ ] **Step 3: import_csv 라우팅에 2개 추가**

기존 `import_csv` 함수 내 `if relative_path == XXX:` 분기 패턴 아래에 추가:

```python
    elif relative_path == NWS_FLOOD_STAGE_COVERAGE:
        import_nws_flood_stage_coverage(database, relative_path, rows)
    elif relative_path == NWS_COVERAGE_BIAS:
        import_nws_coverage_bias(database, relative_path, rows)
```

- [ ] **Step 4: DuckDB view 추가 — camels_duckdb_tool.py**

기존 `CORE_VIEWS` dict에 추가:

```python
CORE_VIEWS = {
    # ... 기존 항목들 ...
    "nws_flood_stage_coverage": "output/model_analysis/confirmed_flood/coverage/nws_flood_stage_coverage.csv",
    "nws_coverage_bias": "output/model_analysis/confirmed_flood/coverage/coverage_bias_report.csv",
    "drbc_confirmed_flood_events": "output/model_analysis/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv",
    "drbc_confirmed_flood_performance": "output/model_analysis/confirmed_flood/performance/drbc_confirmed_flood_performance.csv",
}
```

- [ ] **Step 5: import 실행 및 확인**

```bash
uv run database/postgres/import_camels_csvs.py \
  output/model_analysis/confirmed_flood/coverage/nws_flood_stage_coverage.csv \
  output/model_analysis/confirmed_flood/coverage/coverage_bias_report.csv
```

```bash
psql -d camels -c "SELECT coverage_status, count(*) FROM analysis.nws_flood_stage_coverage GROUP BY 1;"
psql -d camels -c "SELECT attribute, ks_pvalue FROM analysis.nws_coverage_bias ORDER BY ks_pvalue;"
```

Expected: coverage_status별 count, 5개 attribute의 ks_pvalue.

- [ ] **Step 6: 커밋**

```bash
git add database/postgres/import_camels_csvs.py database/duckdb/camels_duckdb_tool.py
git commit -m "feat: add postgres import and duckdb views for NWS coverage data"
```

---

## Task 5: Event Catalog 스크립트 — Flood Event 추출

**Files:**
- Create: `scripts/basin/drbc/build_drbc_confirmed_flood_event_catalog.py`

- [ ] **Step 1: 스크립트 골격 + 상수 작성**

```python
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
from __future__ import annotations

import argparse
import gzip
import io
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

EXCLUDE_START = pd.Timestamp("2000-01-01")
EXCLUDE_END = pd.Timestamp("2013-12-31")
EVENT_GAP_HOURS = 72
FORCING_COVERAGE_MIN = 0.90
FORCING_VARS = ["Rainf","Tair","PotEvap","SWdown","Qair","PSurf","Wind_E","Wind_N","LWdown","CAPE","CRainf_frac"]
WARMUP_DAYS = 21
NOAA_BASE_URL = "https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/"
NOAA_FLOOD_TYPES = {"Flood", "Flash Flood", "Coastal Flood"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--coverage-csv", type=Path, default=DEFAULT_COVERAGE_CSV)
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--noaa-cache", type=Path, default=DEFAULT_NOAA_CACHE)
    p.add_argument("--limit-basins", type=int, default=None)
    return p.parse_args()
```

- [ ] **Step 2: CAMELSH nc 파일에서 flood event 추출 함수 작성**

```python
def extract_flood_events(
    usgs_id: str,
    data_dir: Path,
    minor_cms: float,
    moderate_cms: float | None,
    major_cms: float | None,
) -> list[dict]:
    """관측 Streamflow에서 minor stage 초과 구간을 독립 event로 추출."""
    nc_path = data_dir / f"{usgs_id}.nc"
    if not nc_path.exists():
        return []
    ds = xr.open_dataset(nc_path)
    q = ds["Streamflow"].to_series()
    # 제외 기간 마스크
    mask_exclude = (q.index >= EXCLUDE_START) & (q.index <= EXCLUDE_END)
    q = q[~mask_exclude]
    q = q.dropna()
    if q.empty:
        return []

    # forcing coverage 확인
    forcing_coverage = 1.0
    for var in FORCING_VARS:
        if var in ds:
            s = ds[var].to_series()
            s = s[~mask_exclude].dropna()
            if len(q) > 0:
                forcing_coverage = min(forcing_coverage, len(s) / max(len(q), 1))

    # minor stage 초과 구간 탐지
    above = q >= minor_cms
    events = []
    in_event = False
    event_start = None
    last_above = None

    for t, is_above in above.items():
        if is_above:
            if not in_event:
                in_event = True
                event_start = t
            last_above = t
        else:
            if in_event:
                gap = (t - last_above).total_seconds() / 3600
                if gap >= EVENT_GAP_HOURS:
                    # event 종료
                    event_q = q.loc[event_start:last_above]
                    peak_time = event_q.idxmax()
                    peak_cms = float(event_q.max())
                    # forcing coverage 체크 (event 구간)
                    ev_cover = _event_forcing_coverage(ds, event_start, last_above, mask_exclude)
                    if ev_cover < FORCING_COVERAGE_MIN:
                        in_event = False
                        continue
                    # warmup 가능 여부 체크
                    warmup_start = peak_time - pd.Timedelta(days=WARMUP_DAYS + 1)
                    if warmup_start < q.index[0]:
                        in_event = False
                        continue
                    tier = _assign_tier(peak_cms, minor_cms, moderate_cms, major_cms)
                    tier_limited = moderate_cms is None
                    period = "pre_2000" if peak_time < EXCLUDE_START else "post_2013"
                    events.append({
                        "usgs_id": usgs_id,
                        "peak_time": peak_time.isoformat(),
                        "peak_discharge_cms": peak_cms,
                        "flood_tier": tier,
                        "tier_limited": tier_limited,
                        "noaa_corroborated": False,  # NOAA annotation은 다음 단계
                        "period": period,
                        "forcing_coverage_min": ev_cover,
                    })
                    in_event = False
    ds.close()
    return events


def _event_forcing_coverage(ds: xr.Dataset, start, end, mask_exclude) -> float:
    """event 구간의 forcing 변수 최소 coverage."""
    min_cov = 1.0
    n_hours = max(int((end - start).total_seconds() / 3600), 1)
    for var in FORCING_VARS:
        if var not in ds:
            return 0.0
        s = ds[var].to_series().loc[start:end]
        s = s[~mask_exclude.reindex(s.index, fill_value=False)]
        min_cov = min(min_cov, s.notna().sum() / n_hours)
    return min_cov


def _assign_tier(peak_cms, minor_cms, moderate_cms, major_cms) -> str:
    if major_cms is not None and peak_cms >= major_cms:
        return "major"
    if moderate_cms is not None and peak_cms >= moderate_cms:
        return "moderate"
    return "minor"
```

- [ ] **Step 3: 스모크 테스트 — 3개 basin으로 검증**

```bash
uv run scripts/basin/drbc/build_drbc_confirmed_flood_event_catalog.py --limit-basins 3
```

Expected:
- `output/model_analysis/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv` 생성
- 최소 1개 이상의 event row (covered basin에 flood event가 없을 수도 있으므로 0도 OK)
- 모든 row의 `flood_tier`가 minor/moderate/major 중 하나

- [ ] **Step 4: 커밋 (WIP)**

```bash
git add scripts/basin/drbc/build_drbc_confirmed_flood_event_catalog.py
git commit -m "feat: add confirmed flood event extraction from CAMELSH timeseries"
```

---

## Task 6: Event Catalog — NOAA Annotation + 전체 출력

**Files:**
- Modify: `scripts/basin/drbc/build_drbc_confirmed_flood_event_catalog.py`

- [ ] **Step 1: NOAA Storm Events 다운로드 + 캐시 함수 작성**

```python
def load_noaa_storm_events(years: list[int], cache_dir: Path) -> pd.DataFrame:
    """NOAA NCEI Storm Events CSV를 연도별 다운로드/캐시 후 Flood 유형만 반환."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for year in years:
        cache_path = cache_dir / f"storm_events_{year}.parquet"
        if cache_path.exists():
            frames.append(pd.read_parquet(cache_path))
            continue
        # 파일명 패턴 조회 (인덱스 페이지에서 해당 연도 파일 찾기)
        index_url = NOAA_BASE_URL
        resp = requests.get(index_url, timeout=30)
        resp.raise_for_status()
        # 연도별 파일명 추출
        import re
        pattern = rf"StormEvents_details-ftp_v1\.0_d{year}_c\d+\.csv\.gz"
        matches = re.findall(pattern, resp.text)
        if not matches:
            continue
        filename = sorted(matches)[-1]  # 가장 최신 버전
        file_url = NOAA_BASE_URL + filename
        gz_resp = requests.get(file_url, timeout=60)
        gz_resp.raise_for_status()
        df = pd.read_csv(
            io.StringIO(gzip.decompress(gz_resp.content).decode("latin-1")),
            usecols=["BEGIN_YEARMONTH","BEGIN_DAY","END_YEARMONTH","END_DAY",
                     "STATE_FIPS","CZ_FIPS","EVENT_TYPE"],
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
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["county_fips","begin_date","end_date"])
```

- [ ] **Step 2: NOAA annotation 함수 작성**

```python
def annotate_noaa(
    events: list[dict],
    coverage_df: pd.DataFrame,
    noaa_df: pd.DataFrame,
) -> list[dict]:
    """각 event에 noaa_corroborated boolean 부여."""
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
```

- [ ] **Step 3: main() 작성 — 전체 흐름 연결**

```python
def main() -> None:
    args = parse_args()
    coverage_df = pd.read_csv(args.coverage_csv)
    covered = coverage_df[coverage_df["coverage_status"] == "covered"].copy()
    if args.limit_basins:
        covered = covered.head(args.limit_basins)

    print(f"Processing {len(covered)} covered basins...")
    all_events: list[dict] = []
    for _, row in covered.iterrows():
        events = extract_flood_events(
            usgs_id=str(row["usgs_id"]).zfill(8),
            data_dir=args.data_dir,
            minor_cms=row["minor_discharge_cms"],
            moderate_cms=row.get("moderate_discharge_cms"),
            major_cms=row.get("major_discharge_cms"),
        )
        all_events.extend(events)
    print(f"Extracted {len(all_events)} flood events.")

    if all_events:
        peak_years = sorted({pd.Timestamp(ev["peak_time"]).year for ev in all_events})
        noaa_df = load_noaa_storm_events(peak_years, args.noaa_cache)
        all_events = annotate_noaa(all_events, coverage_df, noaa_df)
        n_corr = sum(ev["noaa_corroborated"] for ev in all_events)
        print(f"NOAA corroborated: {n_corr}/{len(all_events)} ({100*n_corr/max(len(all_events),1):.1f}%)")

    catalog_df = pd.DataFrame(all_events)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out_csv = args.output_dir / "drbc_confirmed_flood_event_catalog.csv"
    catalog_df.to_csv(out_csv, index=False)
    print(f"Saved: {out_csv}")
    print(catalog_df["flood_tier"].value_counts())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 전체 실행**

```bash
uv run scripts/basin/drbc/build_drbc_confirmed_flood_event_catalog.py
```

Expected:
- `output/model_analysis/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv`
- 콘솔에 tier별 event 수 출력 (minor/moderate/major 분포)
- NOAA corroborated 비율 출력

- [ ] **Step 5: 검증**

```bash
python3 -c "
import pandas as pd
df = pd.read_csv('output/model_analysis/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv')
print(f'Total events: {len(df)}')
print(df['flood_tier'].value_counts())
print(f'NOAA corroborated: {df.noaa_corroborated.sum()} ({100*df.noaa_corroborated.mean():.1f}%)')
print(f'Period: {df.period.value_counts().to_dict()}')
assert 'peak_time' in df.columns
assert df['flood_tier'].isin(['minor','moderate','major']).all()
print('All checks passed.')
"
```

- [ ] **Step 6: PostgreSQL import**

```bash
uv run database/postgres/import_camels_csvs.py \
  output/model_analysis/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv
psql -d camels -c "SELECT flood_tier, count(*) FROM analysis.drbc_confirmed_flood_events GROUP BY 1;"
```

- [ ] **Step 7: 커밋**

```bash
git add scripts/basin/drbc/build_drbc_confirmed_flood_event_catalog.py
git commit -m "feat: complete confirmed flood event catalog with NOAA annotation"
```

---

## Task 7: Model Inference 스크립트

**Files:**
- Create: `scripts/model/confirmed_flood/infer_drbc_confirmed_flood_events.py`

기존 `scripts/model/extreme_rain/infer_subset300_extreme_rain_windows.py` 패턴을 따르되, inference 대상 basin을 154개 전체로 확장하고 event window를 catalog CSV에서 읽는다.

- [ ] **Step 1: 스크립트 골격 + 상수 작성**

```python
#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "torch==2.4.1",
#   "neuralhydrology>=1.13",
# ]
# ///
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
VENDOR_NH = ROOT / "vendor" / "neuralhydrology"
if str(VENDOR_NH) not in sys.path:
    sys.path.insert(0, str(VENDOR_NH))

import numpy as np
import pandas as pd
import torch
from neuralhydrology.evaluation import get_tester
from neuralhydrology.utils.config import Config

DEFAULT_CATALOG_CSV = ROOT / "output/model_analysis/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv"
DEFAULT_RUN_ROOT = ROOT / "runs/subset_comparison"
DEFAULT_OUTPUT_DIR = ROOT / "output/model_analysis/confirmed_flood/inference"

RUN_RE = re.compile(r"camelsh_hourly_(model[12])_drbc_holdout_subset300_seed(\d+)_")
PRIMARY_EPOCHS = {
    ("model1", 111): 25, ("model1", 222): 10, ("model1", 444): 15,
    ("model2", 111): 5,  ("model2", 222): 10, ("model2", 444): 10,
}
QUANTILE_COLUMNS = ["q50", "q90", "q95", "q99"]
PRE_HOURS = 24
POST_HOURS = 168
WARMUP_DAYS = 21
CFS_TO_CMS = 0.028316846592


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--catalog-csv", type=Path, default=DEFAULT_CATALOG_CSV)
    p.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--seeds", type=int, nargs="+", default=[111, 222, 444])
    p.add_argument("--device", default="cpu")
    p.add_argument("--batch-size", type=int, default=None)
    p.add_argument("--limit-events", type=int, default=None)
    p.add_argument("--force", action="store_true")
    return p.parse_args()
```

- [ ] **Step 2: run_dirs / patch_config — 기존 함수 복사 + 154 basin 대응**

```python
def run_dirs(run_root: Path) -> dict[tuple[str, int], Path]:
    runs: dict[tuple[str, int], Path] = {}
    for path in sorted(run_root.iterdir()):
        if not path.is_dir():
            continue
        match = RUN_RE.match(path.name)
        if match:
            key = (match.group(1), int(match.group(2)))
            if key not in runs or path.stat().st_mtime > runs[key].stat().st_mtime:
                runs[key] = path
    return runs


def patch_config(*, cfg: Config, root: Path, run_dir: Path, basin_file: Path,
                 device: str, start: pd.Timestamp, end: pd.Timestamp,
                 batch_size: int | None) -> Config:
    update = {
        "run_dir": str(run_dir),
        "train_dir": str(run_dir / "train_data"),
        "img_log_dir": str(run_dir / "img_log"),
        "data_dir": str(root / "data" / "CAMELSH_generic" / "drbc_holdout_broad"),
        "train_basin_file": str(root / "configs/pilot/basin_splits/scaling_300/train.txt"),
        "validation_basin_file": str(root / "configs/pilot/basin_splits/scaling_300/validation.txt"),
        "test_basin_file": str(basin_file),  # 154개 전체 basin file
        "test_start_date": start.strftime("%d/%m/%Y"),
        "test_end_date": end.strftime("%d/%m/%Y"),
        "device": device,
        "num_workers": 0,
    }
    if batch_size is not None:
        update["batch_size"] = int(batch_size)
    cfg.update_config(update, dev_mode=True)
    return cfg
```

- [ ] **Step 3: 154개 basin file 생성 헬퍼**

```python
def write_all_drbc_basin_file(catalog_df: pd.DataFrame, output_dir: Path) -> Path:
    """catalog에 있는 모든 고유 basin을 하나의 txt로 기록."""
    basins = sorted(catalog_df["usgs_id"].astype(str).str.zfill(8).unique())
    basin_file = output_dir / "drbc_confirmed_flood_basins.txt"
    basin_file.parent.mkdir(parents=True, exist_ok=True)
    basin_file.write_text("\n".join(basins) + "\n")
    return basin_file
```

- [ ] **Step 4: inference 실행 루프 작성 (기존 export_predictions_for_model 패턴 적용)**

```python
def infer_event_window(
    *, tester, basin: str, peak_time: pd.Timestamp,
    scale: float, center: float,
) -> dict | None:
    """단일 event window의 obs/pred 시계열 반환."""
    start = peak_time - pd.Timedelta(hours=PRE_HOURS)
    end = peak_time + pd.Timedelta(hours=POST_HOURS)
    try:
        ds = tester._get_dataset_for_period(basin=basin, start=start, end=end)
    except Exception:
        return None
    if ds is None:
        return None
    loader = torch.utils.data.DataLoader(ds, batch_size=len(ds))
    records = []
    with torch.no_grad():
        for batch in loader:
            batch = {k: (v.to(tester.device) if isinstance(v, torch.Tensor) else v) for k, v in batch.items()}
            pred = tester.model(batch)
            dates = pd.to_datetime(batch["date"][:, -1])
            obs_raw = batch["y"][:, -1, 0].cpu().numpy()
            obs = obs_raw * scale + center
            streamflow_pred = pred["y_hat"][:, -1, 0].cpu().numpy() * scale + center
            for i, dt in enumerate(dates):
                records.append({"datetime": dt, "obs": obs[i], "pred": streamflow_pred[i]})
    return {"basin": basin, "peak_time": peak_time, "series": pd.DataFrame(records)}
```

- [ ] **Step 5: main() 작성**

```python
def main() -> None:
    args = parse_args()
    catalog = pd.read_csv(args.catalog_csv, parse_dates=["peak_time"])
    if args.limit_events:
        catalog = catalog.head(args.limit_events)

    basin_file = write_all_drbc_basin_file(catalog, args.output_dir)
    runs = run_dirs(args.run_root)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    all_rows = []
    for seed in args.seeds:
        for model in ("model1", "model2"):
            epoch = PRIMARY_EPOCHS[(model, seed)]
            run_dir = runs.get((model, seed))
            if run_dir is None:
                print(f"WARN: no run dir for {model} seed {seed}")
                continue
            cfg = Config(run_dir / "config.yml")
            # 전체 기간으로 패치 (event별로 date range 재조정)
            cfg = patch_config(cfg=cfg, root=ROOT, run_dir=run_dir,
                               basin_file=basin_file, device=args.device,
                               start=pd.Timestamp("1980-01-01"),
                               end=pd.Timestamp("2024-12-31"),
                               batch_size=args.batch_size)
            tester = get_tester(cfg=cfg, run_dir=run_dir, epoch=epoch, period="test")
            tester.model.eval()

            for _, ev in catalog.iterrows():
                basin = str(ev["usgs_id"]).zfill(8)
                peak_time = pd.Timestamp(ev["peak_time"])
                result = infer_event_window(tester=tester, basin=basin,
                                           peak_time=peak_time,
                                           scale=1.0, center=0.0)
                # NOTE: neuralhydrology tester가 inverse scaling을 내부에서 처리하는지
                # 확인 필요. 만약 raw output이면 target_scale_and_center()로 변환 추가.
                if result is None:
                    continue
                series = result["series"]
                obs_peak = series["obs"].max()
                pred_peak = series["pred"].max()
                under_deficit = (obs_peak - pred_peak) / obs_peak if obs_peak > 0 else None
                nrmse = float(np.sqrt(((series["obs"] - series["pred"]) ** 2).mean())) / (obs_peak if obs_peak > 0 else 1)
                all_rows.append({
                    "usgs_id": basin,
                    "peak_time": peak_time.isoformat(),
                    "model": model,
                    "seed": seed,
                    "quantile": "det" if model == "model1" else "q50",
                    "obs_peak_cms": obs_peak,
                    "pred_peak_cms": pred_peak,
                    "peak_under_deficit": under_deficit,
                    "is_underestimate": pred_peak < obs_peak,
                    "exceeds_minor_stage": True,  # catalog에 있으면 항상 True
                    "event_nrmse": nrmse,
                    "flood_tier": ev.get("flood_tier"),
                    "noaa_corroborated": ev.get("noaa_corroborated"),
                })

    pd.DataFrame(all_rows).to_csv(args.output_dir / "drbc_confirmed_flood_performance.csv", index=False)
    print(f"Done. {len(all_rows)} rows written.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: 스모크 테스트**

```bash
uv run scripts/model/confirmed_flood/infer_drbc_confirmed_flood_events.py \
  --limit-events 5 --device cpu
```

Expected: `output/model_analysis/confirmed_flood/inference/drbc_confirmed_flood_performance.csv` 생성, `obs_peak_cms` 값이 `None`이 아님.

- [ ] **Step 7: 커밋**

```bash
git add scripts/model/confirmed_flood/infer_drbc_confirmed_flood_events.py
git commit -m "feat: add model inference script for confirmed flood events"
```

---

## Task 8: Performance Analysis 스크립트

**Files:**
- Create: `scripts/model/confirmed_flood/analyze_drbc_confirmed_flood_performance.py`

- [ ] **Step 1: 스크립트 골격**

```python
#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "matplotlib>=3.9",
# ]
# ///
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PERF_CSV = ROOT / "output/model_analysis/confirmed_flood/inference/drbc_confirmed_flood_performance.csv"
DEFAULT_OUTPUT_DIR = ROOT / "output/model_analysis/confirmed_flood/analysis"
QUANTILE_ORDER = ["det", "q50", "q90", "q95", "q99"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--perf-csv", type=Path, default=DEFAULT_PERF_CSV)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return p.parse_args()
```

- [ ] **Step 2: tier-stratified 집계 함수 작성**

```python
def compute_tier_aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """flood_tier × model × quantile별 지표 집계."""
    records = []
    for (tier, model, quantile), grp in df.groupby(["flood_tier", "model", "quantile"]):
        obs = grp["obs_peak_cms"].dropna()
        under = grp["peak_under_deficit"].dropna()
        records.append({
            "flood_tier": tier,
            "model": model,
            "quantile": quantile,
            "n_events": len(grp),
            "n_basins": grp["usgs_id"].nunique(),
            "median_obs_peak_cms": float(obs.median()) if len(obs) else None,
            "underestimation_fraction": float((grp["is_underestimate"] == True).mean()),
            "median_under_deficit": float(under.median()) if len(under) else None,
            "median_event_nrmse": float(grp["event_nrmse"].median()),
            "noaa_corroborated_fraction": float(grp["noaa_corroborated"].mean()) if "noaa_corroborated" in grp else None,
        })
    return pd.DataFrame(records)


def compute_paired_delta(df: pd.DataFrame) -> pd.DataFrame:
    """Model 2 quantile vs Model 1 paired delta (같은 seed×event 기준)."""
    m1 = df[df["model"] == "model1"][["usgs_id","peak_time","seed","peak_under_deficit","flood_tier","noaa_corroborated"]].rename(
        columns={"peak_under_deficit": "m1_under_deficit"})
    m2 = df[df["model"] == "model2"].copy()
    merged = m2.merge(m1, on=["usgs_id","peak_time","seed"], suffixes=("","_m1"))
    merged["under_deficit_reduction"] = merged["m1_under_deficit"] - merged["peak_under_deficit"]
    records = []
    for (tier, quantile), grp in merged.groupby(["flood_tier", "quantile"]):
        records.append({
            "flood_tier": tier,
            "quantile": quantile,
            "n_events": len(grp),
            "median_under_deficit_reduction": float(grp["under_deficit_reduction"].median()),
            "median_event_nrmse": float(grp["event_nrmse"].median()),
        })
    return pd.DataFrame(records)
```

- [ ] **Step 3: figure 생성 함수 작성**

```python
def plot_tier_comparison(agg: pd.DataFrame, output_path: Path) -> None:
    tiers = ["minor", "moderate", "major"]
    quantiles = ["det", "q50", "q90", "q95", "q99"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=False)
    for ax, tier in zip(axes, tiers):
        subset = agg[agg["flood_tier"] == tier]
        for _, row in subset.iterrows():
            label = f"{row['model']} {row['quantile']}"
            ax.bar(label, row["median_under_deficit"], label=label)
        ax.set_title(f"Flood tier: {tier}")
        ax.set_ylabel("Median peak under-deficit")
        ax.tick_params(axis="x", rotation=45)
    fig.suptitle("Model 1 vs Model 2 — Confirmed Flood Events (by NWS Tier)")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
```

- [ ] **Step 4: main() 작성**

```python
def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.perf_csv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    agg = compute_tier_aggregate(df)
    agg.to_csv(args.output_dir / "confirmed_flood_tier_aggregate.csv", index=False)

    delta = compute_paired_delta(df)
    delta.to_csv(args.output_dir / "confirmed_flood_paired_delta.csv", index=False)

    plot_tier_comparison(agg, args.output_dir / "figures" / "confirmed_flood_tier_comparison.png")
    print("=== Tier aggregate ===")
    print(agg[["flood_tier","model","quantile","n_events","underestimation_fraction","median_under_deficit"]].to_string())
    print("\n=== Paired delta (Model2 - Model1 under-deficit reduction) ===")
    print(delta.to_string())


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 실행 및 검증**

```bash
uv run scripts/model/confirmed_flood/analyze_drbc_confirmed_flood_performance.py
```

Expected:
- `output/model_analysis/confirmed_flood/analysis/confirmed_flood_tier_aggregate.csv`
- `output/model_analysis/confirmed_flood/analysis/confirmed_flood_paired_delta.csv`
- `output/model_analysis/confirmed_flood/analysis/figures/confirmed_flood_tier_comparison.png`

- [ ] **Step 6: 커밋**

```bash
git add scripts/model/confirmed_flood/analyze_drbc_confirmed_flood_performance.py
git commit -m "feat: add confirmed flood performance analysis script"
```

---

## Task 9: PostgreSQL Import + DuckDB View — Performance

**Files:**
- Modify: `database/postgres/import_camels_csvs.py`

- [ ] **Step 1: import_drbc_confirmed_flood_events 함수 추가**

```python
def import_drbc_confirmed_flood_events(database: str, relative_path: Path, rows: list[dict[str, str]]) -> None:
    source_path = str(REPO_ROOT / relative_path)
    copy_rows = [
        [
            to_text(r.get("usgs_id")),
            to_text(r.get("peak_time")),
            to_float(r.get("peak_discharge_cms")),
            to_text(r.get("flood_tier")),
            to_bool(r.get("tier_limited")),
            to_bool(r.get("noaa_corroborated")),
            to_text(r.get("period")),
            to_float(r.get("forcing_coverage_min")),
            source_path,
        ]
        for r in rows
    ]
    import_mapped_table(
        database,
        "analysis.drbc_confirmed_flood_events",
        ["usgs_id","peak_time","peak_discharge_cms","flood_tier","tier_limited",
         "noaa_corroborated","period","forcing_coverage_min","source_path"],
        copy_rows,
        conflict_target="(usgs_id, peak_time)",
        conflict_action="DO UPDATE SET flood_tier=EXCLUDED.flood_tier, noaa_corroborated=EXCLUDED.noaa_corroborated, imported_at=now()",
    )
```

`to_bool` 헬퍼가 없으면 추가:
```python
def to_bool(value: str | None) -> str:
    if value is None or str(value).strip().lower() in ("", "none", "nan"):
        return "NULL"
    return "TRUE" if str(value).strip().lower() in ("true", "1", "yes") else "FALSE"
```

- [ ] **Step 2: import_drbc_confirmed_flood_performance 함수 추가**

```python
def import_drbc_confirmed_flood_performance(database: str, relative_path: Path, rows: list[dict[str, str]]) -> None:
    source_path = str(REPO_ROOT / relative_path)
    copy_rows = [
        [
            to_text(r.get("usgs_id")),
            to_text(r.get("peak_time")),
            to_text(r.get("model")),
            to_int(r.get("seed")),
            to_text(r.get("quantile")),
            to_float(r.get("obs_peak_cms")),
            to_float(r.get("pred_peak_cms")),
            to_float(r.get("peak_under_deficit")),
            to_bool(r.get("is_underestimate")),
            to_bool(r.get("exceeds_minor_stage")),
            to_float(r.get("event_nrmse")),
            to_text(r.get("flood_tier")),
            to_bool(r.get("noaa_corroborated")),
            source_path,
        ]
        for r in rows
    ]
    import_mapped_table(
        database,
        "analysis.drbc_confirmed_flood_performance",
        ["usgs_id","peak_time","model","seed","quantile","obs_peak_cms","pred_peak_cms",
         "peak_under_deficit","is_underestimate","exceeds_minor_stage","event_nrmse",
         "flood_tier","noaa_corroborated","source_path"],
        copy_rows,
        conflict_target="(usgs_id, peak_time, model, seed, quantile)",
        conflict_action="DO UPDATE SET peak_under_deficit=EXCLUDED.peak_under_deficit, imported_at=now()",
    )
```

- [ ] **Step 3: routing 추가**

```python
    elif relative_path == DRBC_CONFIRMED_FLOOD_EVENTS:
        import_drbc_confirmed_flood_events(database, relative_path, rows)
    elif relative_path == DRBC_CONFIRMED_FLOOD_PERFORMANCE:
        import_drbc_confirmed_flood_performance(database, relative_path, rows)
```

- [ ] **Step 4: import 실행 및 확인**

```bash
uv run database/postgres/import_camels_csvs.py \
  output/model_analysis/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv \
  output/model_analysis/confirmed_flood/inference/drbc_confirmed_flood_performance.csv
```

```bash
psql -d camels -c "SELECT flood_tier, count(*) FROM analysis.drbc_confirmed_flood_events GROUP BY 1;"
psql -d camels -c "SELECT model, quantile, count(*) FROM analysis.drbc_confirmed_flood_performance GROUP BY 1,2 ORDER BY 1,2;"
```

- [ ] **Step 5: DuckDB views 확인**

```bash
uv run database/duckdb/camels_duckdb_tool.py views
```

```bash
python3 -c "
import duckdb
con = duckdb.connect('database/local/duckdb/camels.duckdb')
print(con.execute('SELECT count(*) FROM camels_csv.drbc_confirmed_flood_events').fetchone())
print(con.execute('SELECT count(*) FROM camels_csv.drbc_confirmed_flood_performance').fetchone())
"
```

- [ ] **Step 6: 최종 커밋**

```bash
git add database/postgres/import_camels_csvs.py database/duckdb/camels_duckdb_tool.py \
        scripts/model/confirmed_flood/
git commit -m "feat: add postgres import and duckdb views for confirmed flood performance"
```

---

## 실행 순서 요약

```bash
# 1. PostgreSQL DDL 적용
psql -d camels -f database/postgres/init_camels_analysis_db.sql

# 2. NWS 커버리지 확인 → 커버리지 수 확인 후 진행 여부 결정
uv run scripts/basin/drbc/check_drbc_nws_flood_stage_coverage.py

# 3. Event catalog 구축
uv run scripts/basin/drbc/build_drbc_confirmed_flood_event_catalog.py

# 4. Model inference (GPU 서버에서 실행 권장)
DEVICE=cuda:0 uv run scripts/model/confirmed_flood/infer_drbc_confirmed_flood_events.py --device cuda:0

# 5. Performance 분석
uv run scripts/model/confirmed_flood/analyze_drbc_confirmed_flood_performance.py

# 6. DB import
uv run database/postgres/import_camels_csvs.py \
  output/model_analysis/confirmed_flood/coverage/nws_flood_stage_coverage.csv \
  output/model_analysis/confirmed_flood/coverage/coverage_bias_report.csv \
  output/model_analysis/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv \
  output/model_analysis/confirmed_flood/inference/drbc_confirmed_flood_performance.csv
```
