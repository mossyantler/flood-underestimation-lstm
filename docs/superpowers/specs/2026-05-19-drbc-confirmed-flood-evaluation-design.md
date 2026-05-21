# DRBC Confirmed Flood Event Evaluation — Design Spec

**Date:** 2026-05-19
**Status:** Approved

---

## 목적

기존 primary evaluation(Q99 high-flow candidate 기반)과 별도로, NWS 공식 flood stage를 초과한 "confirmed flood event"에서 Model 1 vs Model 2를 비교한다. 모델이 통계적 임계값이 아닌 실제 홍수 상황에서 어떻게 동작하는지 평가하는 것이 목적이다.

---

## 분석 구조 전체

기존 primary evaluation은 변경하지 않는다. 이 설계는 독립적으로 추가되는 분석 레이어다.

```
[기존] Primary evaluation
  38 DRBC test basins × 2014-2016 × Q99 high-flow candidates
  → 변경 없음

[신규] Confirmed Flood Event Evaluation
  154 DRBC holdout basins × (1980-1999 + 2014-2024) × NWS minor stage 초과 구간
```

| | Primary | Confirmed Flood |
|---|---|---|
| Basin | 38개 (test.txt) | 154개 (전체 DRBC holdout) |
| 기간 | 2014-2016 | 1980-1999 + 2014-2024 |
| Event 정의 | Q99 high-flow candidate | NWS minor stage 초과 |
| 목적 | 전반적 모델 비교 | 실제 홍수 상황 집중 평가 |

두 분석은 별도 테이블과 figure로 유지하고, 논문에서는 "Primary results hold under a stricter confirmed-flood filter"로 연결한다.

---

## 스크립트 구성

| 단계 | 스크립트 | 역할 |
|------|---------|------|
| 1 | `scripts/basin/drbc/check_drbc_nws_flood_stage_coverage.py` | 154개 gauge NWS flood stage 커버리지 확인 |
| 2 | `scripts/basin/drbc/build_drbc_confirmed_flood_event_catalog.py` | stage 초과 event 추출 + NOAA annotation |
| 3 | `scripts/data/prepare_drbc_confirmed_flood_event_dataset.py` | confirmed flood catalog 기준 event-level GenericDataset 준비 |
| 4 | `scripts/model/confirmed_flood/infer_drbc_confirmed_flood_events.py` | Model 1/2 inference |
| 5 | `scripts/model/confirmed_flood/analyze_drbc_confirmed_flood_performance.py` | Model 1 vs 2 비교 분석 |

산출물 경로: `output/model_analysis/confirmed_flood/`

---

## Section 1: NWS Flood Stage 커버리지 확인

### API 흐름

1. CAMELSH DRBC holdout 154개 basin의 USGS gauge ID 목록을 로드한다.
2. USGS site 정보 API(`waterservices.usgs.gov/nwis/site/`)로 USGS gauge ID → NWS location ID 매핑 테이블을 만든다. 매핑 실패 gauge는 `no_nws_mapping`으로 표기한다.
3. NWPS API(`api.water.noaa.gov/nwps/v1/gauges/{nws_id}`)로 minor / moderate / major flood stage 임계값(단위: feet)을 조회한다.
4. USGS rating curve API(`waterservices.usgs.gov/nwis/ratings/`)로 각 gauge의 stage-discharge lookup table을 받아 보간하여 stage → discharge(m³/s) 변환값을 계산한다.

### 커버리지 판단 기준

| 커버리지 | 대응 |
|---------|------|
| ≥ 120개 (≥78%) | Approach 1 단독 진행 |
| 70-119개 | 경고 출력 후 진행, 논문에서 limitation 명시 |
| < 70개 | USGS annual peak 기반 hybrid로 전환 |

### 출력물

**커버리지 테이블**
`output/model_analysis/confirmed_flood/coverage/nws_flood_stage_coverage.csv`

컬럼: `usgs_id`, `nws_location_id`, `minor_stage_ft`, `moderate_stage_ft`, `major_stage_ft`, `minor_discharge_cms`, `moderate_discharge_cms`, `major_discharge_cms`, `coverage_status`

**누락 basin 속성 편향 분석**

커버된 basin과 누락된 basin의 static attribute 분포를 비교해 선택 편향을 정량화한다.

비교 대상 속성: `area`, `slope`, `aridity`, `snow_fraction`, `baseflow_index`

출력물:
- `output/model_analysis/confirmed_flood/coverage/coverage_bias_report.csv` — 속성별 covered/missing 그룹의 median, mean, KS-test p-value
- `output/model_analysis/confirmed_flood/coverage/figures/coverage_bias_distributions.png` — 속성별 분포 비교 boxplot (covered vs. missing)

이 figure를 보고 누락 basin이 소규모 headwater에 집중되어 있으면 논문에 "analysis is representative of mid-to-large basins; headwater flash-flood dynamics may be underrepresented" 문장을 limitation으로 추가한다.

---

## Section 2: Confirmed Flood Event Catalog 구축

### 기간 필터

- **포함:** 1980-01-01 ~ 1999-12-31 (pre-training), 2014-01-01 ~ 2024-12-31 (post-validation)
- **제외:** 2000-01-01 ~ 2013-12-31 (training + validation 기간)

### Event 추출 규칙

CAMELSH 관측 discharge 시계열에서 NWS minor stage discharge를 초과하는 구간을 스캔한다. 기존 `build_subset300_extreme_rain_event_catalog.py`의 event extraction 로직과 동일한 구조를 사용한다.

| 파라미터 | 값 |
|---------|---|
| Primary threshold | NWS minor stage discharge (gauge별 상이) |
| 독립 event 분리 gap | ≥ 72h |
| 관측값 coverage 최소치 | 90% (discharge + 11개 forcing 변수 모두 적용) |
| Warmup 시작 지점 | CAMELSH 시계열 시작보다 앞이면 event drop |

### Forcing 변수 coverage 확인

11개 dynamic input 변수 전체(`Rainf`, `Tair`, `PotEvap`, `SWdown`, `Qair`, `PSurf`, `Wind_E`, `Wind_N`, `LWdown`, `CAPE`, `CRainf_frac`)에 대해 event 구간 coverage를 확인한다. 90% 미만이면 해당 event를 제외한다. 1980년대 구간에서 `CAPE`, `CRainf_frac` 누락이 집중될 수 있으므로 연대별 drop 비율을 coverage report에 포함한다.

### Flood severity tier 부여

각 event에 peak discharge를 기준으로 tier를 부여한다.

| Tier | 조건 |
|------|------|
| `minor` | minor stage ≤ peak < moderate stage |
| `moderate` | moderate stage ≤ peak < major stage |
| `major` | peak ≥ major stage |

moderate / major stage 데이터가 없는 gauge는 `minor` tier만 부여하고 `tier_limited = True` 플래그를 기록한다.

### NOAA Storm Events annotation

gauge가 속한 county FIPS + event peak 날짜 ±2일 기준으로 NOAA NCEI Storm Events(event type: Flood, Flash Flood)와 매칭한다. Hard filter가 아니라 boolean flag(`noaa_corroborated`)로 기록한다.

### 출력물

`output/model_analysis/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv`

컬럼: `usgs_id`, `peak_time`, `peak_discharge_cms`, `flood_tier`, `tier_limited`, `noaa_corroborated`, `period` (pre_2000 / post_2013), `forcing_coverage_min`

---

## Section 3: Model Inference

### Event-level GenericDataset 준비

Inference는 expanded observed test dataset을 그대로 쓰지 않는다. `drbc_confirmed_flood_event_catalog.csv`를 입력으로 받아 `data/CAMELSH_generic/drbc_holdout_confirmed_flood_events/`를 별도로 만든다. 이 dataset은 catalog event가 있는 basin만 포함하고, `splits/event_windows.csv`에 `event_id`, `peak_time`, `window_start`, `window_end`, `eval_start`, `eval_end`, forcing/target coverage와 source provenance를 기록한다.

Forcing은 `timeseries.7z`와 `timeseries_nonobs.7z`에서 찾고, target `Streamflow`는 forcing archive 안의 observed streamflow 또는 `Hourly2.zip`의 `hourly2_streamflow` 중 event evaluation window coverage가 더 좋은 쪽을 사용한다. Ready event 기준은 warmup+evaluation window의 11개 forcing coverage `>= 0.90`, evaluation window의 observed target coverage `>= 0.90`이다. Inference script는 `data_dir/splits/event_windows.csv`가 있으면 이 prepared event window를 우선 사용한다.

### Inference 윈도우

```
[warmup 21일] → [pre 24h] → [peak] → [post 168h]
     └─ LSTM state 초기화용, 평가 제외
```

warmup 시작 지점이 CAMELSH 시계열 시작보다 앞이면 해당 event drop.

### Inference 대상

| 항목 | 내용 |
|------|------|
| 모델 | Model 1 (deterministic), Model 2 (q10/q50/q90/q95/q99) |
| Seed | 111 / 222 / 444 (paired) |
| Basin | NWS coverage 있는 DRBC holdout basin 전체 |
| Dynamic inputs | `Rainf`, `Tair`, `PotEvap`, `SWdown`, `Qair`, `PSurf`, `Wind_E`, `Wind_N`, `LWdown`, `CAPE`, `CRainf_frac` |
| Static attributes | `area`, `slope`, `aridity`, `snow_fraction`, `soil_depth`, `permeability`, `forest_fraction`, `baseflow_index` |
| Checkpoint | 기존 공식 checkpoint 그대로 사용 |

### Primary evaluation과의 중복 처리

38개 test basin의 2014-2016 구간에서 NWS stage를 초과하는 event는 이 catalog에도 들어온다. 의도적 중복이며, 두 분석은 별도 테이블로 유지한다.

---

## Section 4: 평가 지표와 분석 구조

### 지표

기존 event-regime 분석과 동일한 지표를 사용한다.

| 지표 | 설명 |
|------|------|
| Peak under-deficit | `(obs_peak - pred_peak) / obs_peak`, 양수 = 과소추정 |
| Underestimation fraction | event 중 pred < obs인 비율 |
| Threshold recall | obs peak ≥ minor stage인 event 중 pred도 초과한 비율 |
| Event NRMSE | event 구간 전체 hydrograph error |

### Stratification

**축 1: Flood severity tier**
- Minor stage 초과 전체
- Moderate 이상
- Major 이상

**축 2: NOAA corroboration**
- `noaa_corroborated = True` 부분집합 vs 전체
- "NOAA에도 기록된 event만 봐도 결론이 바뀌지 않는다"는 robustness 확인용

### 논문 연결 문장

> "We additionally evaluated model performance on confirmed flood events defined by exceedance of NWS operational flood stage thresholds across all 154 DRBC holdout basins (excluding the 2000–2013 training and validation period). Results are consistent with the primary evaluation: Model 2 upper quantiles reduce peak under-deficit across all severity tiers, while the q50 does not outperform Model 1."

---

## Database 저장 규칙

CSV는 file-system source-of-truth로 유지하고, PostgreSQL과 DuckDB는 조회·join 편의를 위한 cache 계층이다. 기존 `database/postgres/init_camels_analysis_db.sql` 및 `database/duckdb/camels_duckdb_tool.py` 패턴을 그대로 따른다.

### PostgreSQL (`analysis` schema)

| 테이블 | 원천 CSV | 주요 컬럼 |
|--------|---------|---------|
| `analysis.nws_flood_stage_coverage` | `coverage/nws_flood_stage_coverage.csv` | `usgs_id`, `nws_location_id`, `minor_discharge_cms`, `moderate_discharge_cms`, `major_discharge_cms`, `coverage_status` |
| `analysis.nws_coverage_bias` | `coverage/coverage_bias_report.csv` | `attribute`, `covered_median`, `missing_median`, `ks_stat`, `ks_pvalue` |
| `analysis.drbc_confirmed_flood_events` | `catalog/drbc_confirmed_flood_event_catalog.csv` | `usgs_id`, `peak_time`, `peak_discharge_cms`, `flood_tier`, `tier_limited`, `noaa_corroborated`, `period`, `forcing_coverage_min` |
| `analysis.drbc_confirmed_flood_performance` | `performance/*.csv` | `usgs_id`, `peak_time`, `model`, `seed`, `quantile`, `obs_peak`, `pred_peak`, `peak_under_deficit`, `threshold_recall`, `event_nrmse`, `flood_tier`, `noaa_corroborated` |

각 테이블에 `source_path text`, `imported_at timestamptz DEFAULT now()` 컬럼을 표준으로 포함한다.

`init_camels_analysis_db.sql`에 위 4개 테이블 DDL을 추가하고, `import_camels_csvs.py`에 import 로직을 추가한다.

### DuckDB view

기존 `camels_duckdb_tool.py`의 `views` 명령에 아래 view를 등록한다.

| View | 설명 |
|------|------|
| `confirmed_flood_events` | `drbc_confirmed_flood_events` CSV glob 직독 또는 Parquet |
| `confirmed_flood_performance` | `drbc_confirmed_flood_performance` CSV glob |
| `confirmed_flood_coverage` | `nws_flood_stage_coverage` + `nws_coverage_bias` join |

DBeaver에서 `analysis.drbc_confirmed_flood_events`로 직접 조회하거나, DuckDB view를 통해 ad hoc 탐색이 가능하도록 한다.

---

## 커버리지 리스크 대응

NWS flood stage 커버리지가 70개 미만으로 낮게 나올 경우, USGS NWIS annual peak flow를 anchor로 쓰는 hybrid 방식으로 전환한다. 이 경우 각 연도의 annual peak 발생 시점 중 return period ≥ 2yr인 event를 confirmed flood로 정의하고, NOAA annotation을 primary corroboration으로 올린다. 이 전환 여부는 커버리지 확인 스크립트 실행 결과에 따라 결정한다.
