# 00b RQ-0 — 분위 출력 해석과 관측 위치(obs_class) 추측

## 질문 (RQ-0)

Model 2는 한 시점마다 네 예측선 `q50 / q90 / q95 / q99`를 동시에 낸다. 각 선은 분위(quantile, 관측이 그 값 아래에 들 확률 수준)다. RQ-0의 질문은 두 갈래다.

1. **이 네 선을 어떻게 읽어야 하는가** — 가운데 예측·보수성 단계·예측 폭으로서의 읽기 규칙과 하면 안 되는 해석.
2. **이 네 선으로 관측을 어떻게 추측하는가** — 관측 첨두가 예측 밴드(`q50`~`q99`) 어디에 드는지(관측 위치 구간, obs_class)와, 그 위치를 미리 예고하는 신호가 무엇인지.

특히 관측이 밴드 최상단 `q99`마저 넘는 경우(`above_q99`)는 **모델이 첨두를 과소추정한 사건**이며, 본 연구의 핵심 주제다. RQ-0은 "모델이 언제 첨두를 놓치는가"를 조건부로 진단하는 틀을 만든다.

해석 규칙 자체는 [`quantile_output_interpretation.md`](../../method/model/quantile_output_interpretation.md)에 있고, 이 문서는 그 규칙이 실데이터에서 타당함과, 관측 위치를 예측하는 신호의 상관관계 분석 결과를 정리한다.

## 핵심 구조 — 관측 위치 구간 (obs_class)

관측 첨두가 예측 밴드 안 어디에 드는지를 다섯 서수 구간으로 나눈다.

| obs_class | 정의 | 뜻 |
| ---: | --- | --- |
| 0 | `관측 ≤ q50` | 가운데 예측보다 낮음(과대추정 쪽) |
| 1 | `q50 < 관측 ≤ q90` | 밴드 하부 |
| 2 | `q90 < 관측 ≤ q95` | 밴드 중상부 |
| 3 | `q95 < 관측 ≤ q99` | 밴드 최상부 근접 |
| 4 | `관측 > q99` | **q99도 못 잡음 = 과소추정** |

obs_class가 클수록 모델이 첨두를 더 심하게 놓친 것이다. 이 서수 변수가 RQ-0 진단의 중심 축이며, 모든 신호 분석의 타깃(target)이 된다.

## 데이터와 사건 범위 생성 절차

이 문서의 상관관계 분석은 같은 DRBC 관측 시험 split 위에서 서로 다른 세 사건 범위를 만든 뒤 비교한다. 세 범위를 따로 둔 이유는, 극단 사건만 보면 이미 관측값이 큰 시점만 모은 **범위 제한(선택 편향)** 때문에 상관관계가 왜곡될 수 있기 때문이다. 따라서 Q99 사건과 NOAA 사건은 “어려운 홍수 첨두에서 모델이 어디서 실패하는가”를 보는 범위이고, 전체 강우 사건은 “그 신호가 일반 강우 반응 전체에서도 남는가”를 확인하는 대조 범위다.

### 공통 기준

| 항목 | 기준 | 근거 파일 |
| --- | --- | --- |
| 평가 유역 | DRBC 관측 시험 유역 85개 | `data/CAMELSH_generic/drbc_expanded_observed_test/time_series/*.nc` |
| 시험 기간 | 2014-01-01 00:00 ~ 2016-12-31 23:00 | `scripts/_lib/expanded_drbc.py`의 `TEST_PERIOD` |
| Q99 임계 산정 기간 | 2000-01-01 ~ 2010-12-31 | `scripts/_lib/expanded_drbc.py`의 `TRAIN_PERIOD` |
| 난수 seed | `111 / 222 / 444` | `scripts/_lib/expanded_drbc.py`의 `SEEDS` |
| 예측선 순서 | `model1 → q50 → q90 → q95 → q99` | `scripts/_lib/expanded_drbc.py`의 `TAU_ORDER` |
| 사건 창 | 관측 첨두 기준 ±6시간 | `EVENT_WINDOW_HOURS = 6` |
| 가까운 Q99 초과 병합 | 초과 시각 사이 간격 12시간 이하이면 같은 사건 | `EVENT_MERGE_GAP_HOURS = 12` |

`basin_id`는 모든 단계에서 8자리 문자열로 맞춘다(`normalize_basin_id`, 예: `1414000` → `01414000`). 이렇게 해야 CAMELSH NetCDF 파일명, `required_series.csv`의 `basin`, NOAA catalog의 `usgs_id`가 같은 유역으로 조인된다.

관측 위치 구간(`obs_class`)은 사건 첨두 시각의 관측 유량이 Model 2의 `q50/q90/q95/q99` 예측 사다리 어디에 놓이는지로 계산한다. Q99 사건과 NOAA 사건은 seed별 예측선이 다르므로 `(basin_id, seed, peak_time)`마다 `obs_class`를 계산한다. 전체 강우 사건은 세 seed의 `obs/q50/q90/q95/q99`를 먼저 `(basin_id, datetime)` 단위로 평균한 뒤 한 사건당 하나의 `obs_class`를 만든다.

### 1) Q99 사건: 학습기간 관측 Q99를 넘은 시험기간 고유량 사건

Q99 사건은 **모델의 `q99` 예측값으로 고른 사건이 아니다.** 유역별 과거 관측 유량에서 99번째 백분위 임계를 먼저 만들고, 시험기간 관측 유량이 그 임계를 넘는 시점을 사건으로 묶는다. 따라서 이 범위는 “각 유역에서 과거 기준으로 매우 큰 관측 유량이 나온 사건”이다.

생성 스크립트는 `scripts/model/expanded_drbc/build_q99_events.py`다. 절차는 다음과 같다.

1. `data/CAMELSH_generic/drbc_expanded_observed_test/time_series/{basin}.nc`에서 학습기간(2000–2010)의 `Streamflow`를 읽는다.
2. NaN을 제외하고 유역별 `Streamflow`의 0.99 quantile을 계산해 `q99_train_value`로 저장한다.
3. 시험기간 관측값은 `output/model_analysis/primary/metrics/data/required_series/seed111/required_series.csv`에서 읽는다. 관측값은 seed와 무관하므로 seed 111 파일을 canonical 관측 source로 쓴다.
4. 시험기간 중 `obs >= q99_train_value`인 모든 시간값을 찾는다.
5. 초과 시각 사이 간격이 12시간 이하이면 같은 사건으로 병합한다. 같은 사건 안에서는 관측 유량이 가장 큰 시각을 `peak_time`, 그 값을 `peak_obs`로 둔다.
6. `peak_time ± 6h`를 사건 창으로 만들고, 창이 시험기간 밖으로 나가면 경계에서 자르고 `window_truncated=True`를 표시한다.
7. 유역별 사건 수가 너무 적거나 많은 경우는 `rq2_q99_basin_warnings.csv`에 경고만 남긴다. 경고는 분석 실패 조건이 아니라 sanity check다.

현재 산출물 기준으로 Q99 임계는 85개 유역 모두에서 계산됐고, 시험기간 Q99 초과 사건은 **926건 / 82개 유역**이다. 85개 유역 중 23개 유역은 시험기간 Q99 초과 사건이 3건 미만이라 경고가 붙지만, 임계값 자체는 85개 모두 존재한다.

| 산출물 | 내용 |
| --- | --- |
| `output/model_analysis/primary/metrics/tables/rq2_q99_per_basin_thresholds.csv` | 유역별 학습기간 Q99 임계, 사용 시간 수, 시험기간 사건 수 |
| `output/model_analysis/primary/metrics/tables/rq2_q99_events_85basin.csv` | Q99 초과 사건의 `basin_id/event_id/peak_time/peak_obs/window_start/window_end` |
| `output/model_analysis/primary/metrics/tables/rq2_q99_basin_warnings.csv` | 사건 수가 매우 적거나 많은 유역에 대한 경고 |

이후 `compute_ub_location_class.py`가 Q99 사건의 `peak_time`을 각 seed의 `required_series.csv`와 붙여 `obs_class`를 만든다. Q99 사건 926건은 seed 3개와 결합되므로 원래 위치 구간 표는 2,778개 `(event, seed)` 행을 갖는다. `signal_sweep_branchA_csv.py`와 `signal_sweep_branchB_forcing.py`는 이 위치 구간을 상관관계 분석의 타깃으로 사용한다.

### 2) NOAA 사건: NWS flood-stage catalog를 DRBC 85개 시험 유역에 맞춘 사건

NOAA 사건 범위는 이름 때문에 혼동하기 쉽다. 실제 입력은 `output/model_analysis/confirmed_flood/data/catalog/drbc_confirmed_flood_event_catalog.csv`에 저장된 **NWS flood-stage 기준 확인 홍수 catalog**다. 이 catalog에는 각 사건이 NOAA Storm Events 문구와 매칭됐는지(`noaa_corroborated`)와, 매칭 문구(`noaa_annotation`)가 함께 들어 있다. RQ-0에서 “NOAA 사건”이라고 부르는 65건은 이 catalog를 DRBC 85개 시험 유역과 2014–2016 시험기간으로 자른 사건 범위다. 즉 “사회적으로 확인된 홍수 첨두”를 보는 보조 극단 범위이며, Q99 임계로 직접 고른 사건은 아니다.

생성 스크립트는 `scripts/model/expanded_drbc/build_noaa_mapping.py`다. 절차는 다음과 같다.

1. catalog의 `usgs_id`를 8자리 `basin_id`로 정규화한다.
2. `data/CAMELSH_generic/drbc_expanded_observed_test/time_series/*.nc`에서 DRBC 시험 split 85개 유역 목록을 만들고, catalog 유역과의 교집합을 표시한다(`in_expanded_85`).
3. 각 catalog row의 `peak_time`과 `peak_discharge_cms`를 사건 첨두 시각·첨두 유량으로 사용한다. 창은 Q99 사건과 같이 `peak_time ± 6h`로 만들고, 2014–2016 시험기간 경계에서 자른다.
4. NOAA Storm Events 문구가 `-`이면 `NoNOAA`로 둔다. 문구가 있으면 `NOAA_REGEX`로 `Flash Flood`, `Flood`, `Coastal Flood`를 찾고, 여러 유형이 같은 횟수로 걸리면 `Flash Flood > Coastal Flood > Flood > Other` 순서로 대표 유형을 고른다. `Flash Flood Watch`나 `Coastal Flood`가 단순 `Flood`로 잘못 잡히지 않도록 정규식이 분리돼 있다.
5. 최종 분석에서는 `in_expanded_85=True`이고 `peak_time`이 2014–2016 시험기간 안에 들어오는 사건만 쓴다. 이 필터 뒤 사건 수는 **65건 / 21개 유역**이다.

중요한 구분은 다음이다. catalog 전체 664건에는 `noaa_corroborated=True`가 325건, `False`가 339건 섞여 있다. 반면 RQ-0의 2014–2016 DRBC 85개 교집합 65건은 `Flood` 32건, `Flash Flood` 8건, `NoNOAA` 25건으로 나뉜다. 즉 40건은 NOAA Storm Events 문구가 붙은 사건이고, 25건은 NWS flood-stage는 넘었지만 NOAA 문구가 없는 사건이다. 그래서 RQ-4b처럼 event-type 차이를 볼 때는 `Flash Flood/Flood/NoNOAA`를 분리해서 해석하고, `NoNOAA`는 논문 주장용 홍수 유형이 아니라 데이터 품질 카테고리로 둔다.

| 산출물 | 내용 |
| --- | --- |
| `output/model_analysis/primary/metrics/tables/rq2_id_normalization_report.csv` | NOAA `usgs_id`와 expanded basin id 정규화·매칭 확인 |
| `output/model_analysis/primary/metrics/tables/rq2_noaa_basin_overlap_summary.csv` | NOAA catalog 유역과 DRBC 85개 유역의 교집합 요약 |
| `output/model_analysis/primary/metrics/tables/rq2_noaa_events_expanded_overlap.csv` | catalog row에 `in_expanded_85`, 사건 창, 대표 event type을 붙인 표 |
| `output/model_analysis/primary/metrics/tables/rq4b_event_type_mapping.csv` | 대표 event type별 사건 수·유역 수 |
| `output/model_analysis/primary/metrics/tables/rq4b_noaa_annotation_unmatched.csv` | NOAA 문구가 있으나 정규식 유형에 걸리지 않은 문구 목록 |

이후 Q99 사건과 동일하게 `compute_ub_location_class.py`가 각 seed의 `required_series.csv`에서 사건 첨두 시각의 `obs/q50/q90/q95/q99`를 가져와 `obs_class`를 계산한다. NOAA 범위 65건은 seed 3개와 결합돼 원래 위치 구간 표가 195개 `(event, seed)` 행을 갖고, 상관관계 표에서는 사건 단위로 seed를 묶어 사용한다.

### 3) 전체 강우 사건: 2014–2016 모든 강우 반응을 새로 탐지한 대조 범위

전체 강우 사건은 Q99나 NOAA처럼 “이미 큰 홍수”를 고른 범위가 아니다. `scripts/model/expanded_drbc/signal_sweep_branchB2_allrain.py`가 2014–2016 시험기간 전체에서 강우 사건을 새로 탐지하고, 그 뒤에 이어진 유량 반응 첨두를 찾는다. 목적은 극단 subset에서 보인 상관관계가 전체 강우 반응에서도 유지되는지 확인하는 것이다.

생성 절차는 다음과 같다.

1. 각 유역 NetCDF의 `Rainf`를 시험기간(2014–2016)으로 자른다.
2. `Rainf > 0.1 mm/h`인 시간을 강우 시간으로 본다.
3. 강우가 잠시 끊겨도 건조 공백이 6시간 이하이면 같은 강우 사건으로 유지한다. 건조 공백이 6시간을 넘으면 사건을 종료한다.
4. 사건 총강우량이 2.5 mm 미만이면 너무 작은 사건으로 보고 제외한다.
5. 사건의 최대 시간강우(`rain_max_1h`)로 NWS 강우강도 등급을 만든다: `light < 2.5`, `moderate 2.5–7.6`, `heavy 7.6–50`, `violent ≥ 50 mm/h`. 코드에서는 이를 `nws_class = 0/1/2/3` 서수값으로 저장한다.
6. 유량 반응 첨두는 강우 시작부터 강우 종료 후 48시간까지의 `Streamflow` 최대 시각으로 잡는다. 이 시각이 전체 강우 사건의 `peak_time`이다.
7. 세 seed의 `required_series.csv`를 합쳐 `(basin, datetime)`별 평균 `obs/q50/q90/q95/q99`를 만든다. 그 평균 예측 사다리에서 반응 첨두 시각의 `obs_class`를 계산한다.
8. 같은 사건에 대해 강우·대류·밴드·유역 특성을 함께 저장한다. 강우 특성은 `rain_sum_event`, `rain_max_1h`, `nws_class`; 대류 특성은 `cape_max`, `crainf_frac_mean`; 밴드 결합 비교용 값은 `rel_width`, `q99_q50_ratio`; 유역 특성은 `area/slope/aridity/snow_fraction/soil_depth/permeability/baseflow_index/forest_fraction`이다.

현재 산출물 기준 전체 강우 사건 표는 **16,639개 행 / 84개 유역**이다. 같은 반응 첨두 시각을 공유하는 강우 사건이 일부 있어 고유 `(basin_id, peak_time)`은 14,904개다. 관측 위치 구간은 다섯 칸에 비교적 넓게 퍼져 있다: `below_q50` 4,446건, `q50_to_q90` 3,615건, `q90_to_q95` 1,866건, `q95_to_q99` 2,970건, `above_q99` 3,742건. 이 분포가 Q99/NOAA보다 덜 한쪽으로 몰려 있어 선택 편향 점검에 적합하다.

| 산출물 | 내용 |
| --- | --- |
| `output/model_analysis/band_signal/signal_sweep/tables/branchB2_features_allrain.csv` | 전체 강우 사건별 `obs_class`, 강우·대류·밴드·유역 특성 |
| `output/model_analysis/band_signal/signal_sweep/tables/branchB2_spearman.csv` | 전체 강우 범위에서 후보 신호와 `obs_class`의 Spearman 상관 |
| `output/model_analysis/band_signal/signal_sweep/tables/branchB2_seed_spread_spearman.csv` | 전체 강우 범위에서 seed spread와 `obs_class`의 상관 |

### 4) 상관관계 표가 만들어지는 방식

상관관계 분석은 세 범위를 같은 축으로 비교하지만, feature를 만드는 경로는 다르다.

| 범위 | 타깃 생성 | feature 생성 스크립트 | 핵심 feature |
| --- | --- | --- | --- |
| Q99 사건 | `compute_ub_location_class.py`가 seed별 `obs_class` 계산 | `signal_sweep_branchA_csv.py`, `signal_sweep_branchB_forcing.py` | 예측 밴드 폭·수준, seed spread, 유역 특성, 첨두 전 24/72시간 강우·CAPE·대류성 강수비 |
| NOAA 사건 | Q99와 동일하되 NOAA catalog 사건 첨두 사용 | `signal_sweep_branchA_csv.py`, `signal_sweep_branchB_forcing.py` | Q99와 동일 |
| 전체 강우 사건 | `signal_sweep_branchB2_allrain.py`가 강우 탐지부터 `obs_class`까지 한 번에 생성 | `signal_sweep_branchB2_allrain.py`, `signal_sweep_seed_spread_allrain.py` | 사건 총강우, 최대 시간강우, NWS 등급, CAPE, 대류성 강수비, 유역 특성, seed spread |

Spearman 순위상관 `r`은 각 신호값과 관측 위치 구간 번호(`below_q50=0` … `above_q99=4`) 사이에서 계산한다. `r > 0`이면 신호가 클수록 관측 첨두가 예측 사다리 위쪽으로 올라가는 경향이고, `r < 0`이면 신호가 클수록 관측 첨두가 예측 사다리 안쪽이나 아래쪽으로 내려가는 경향이다. 단, 밴드 폭·분위 수준처럼 `obs_class` 정의에 들어간 예측선에서 파생된 값은 구조적 결합이 있으므로 예측 신호로 채택하지 않는다.

주요 상관관계 산출물은 다음이다.

```text
output/model_analysis/band_signal/signal_sweep/tables/
  branchA_features_q99.csv, branchA_features_noaa.csv
  branchB_features_q99.csv, branchB_features_noaa.csv
  branchB2_features_allrain.csv
  branchA_spearman.csv, branchB_spearman.csv, branchB2_spearman.csv
  branchB2_seed_spread_spearman.csv
```

## 결과 A — 관측 위치 분포: q99마저 넘는 첨두

obs_class의 유역 중앙값 분포(관측 위치 구간별 사건 비율):

| obs_class | Q99 사건 (유역 중앙값) | NOAA 홍수 (유역 중앙값) |
| --- | ---: | ---: |
| `q50_to_q90` | 0.09 | 0.0 |
| `q95_to_q99` | 0.07 | 0.0 |
| **`above_q99`** | **0.469** | **1.0** |

- Q99 초과 사건의 약 **47%에서 관측이 q99마저 초과**한다(유역 중앙값). 가장 보수적인 예측선조차 절반 가까운 극단 첨두를 덮지 못한다.
- NOAA/NWS catalog 홍수 범위는 유역 중앙값 기준 **100%가 `above_q99`**다. 사회적으로 확인된 홍수 첨두에서는 모델이 매우 일관되게 과소추정한다.

밴드 안에서 τ를 올릴수록 과소추정 폭(under_gap)은 줄지만 과대추정 폭(over_gap)이 커지는 맞교환이 보인다(Q99 사건, 유역 중앙값):

| τ | 상대 under_gap | 상대 over_gap |
| --- | ---: | ---: |
| q50 | 0.657 | 0.0 |
| q90 | 0.376 | 0.0 |
| q95 | 0.272 | 0.0 |
| q99 | 0.018 | 0.122 |

q99에서 전형적 사건의 과소추정 폭은 거의 닫히지만(0.018), `above_q99` 비율 47%가 말해 주듯 꼬리의 극단 첨두는 여전히 놓친다. 이것이 **RQ-2(위쪽 분위로 첨두 과소추정 완화)의 정량적 문제 정의**다.

## 결과 B — 관측 위치를 예측하는 신호 (상관관계 분석)

"모델이 언제 첨두를 놓치는가"를 예고하는 신호를 찾는다. 후보 신호를 세 부류로 나눈다.

| 부류 | 의미 | 쓸모 |
| --- | --- | --- |
| **C 밴드 결합** | 예측 밴드에서 파생된 값(밴드 폭·분위 수준·꼬리). obs_class 정의에 이미 들어가 부분 순환 | 예측 신호로 쓸 수 없음 |
| **I 독립** | obs_class 정의에 안 들어가는 외부 정보(유역 정적 특성, 대류 지표) | 진짜 예측 신호 |
| **L 관측 누수** | 관측값 자체(관측 첨두·관측 상승 기울기). 강하지만 사후 진단만 | 기준선(상한) |

### 독립 신호 순위 (Spearman r vs obs_class)

| 신호 | Q99 | NOAA | 전체강우 | 해석 |
| --- | ---: | ---: | ---: | --- |
| **유역 면적 area** | **+0.43** | **+0.43** | +0.27 | 범용 최강. 큰 유역일수록 obs가 밴드 위쪽 |
| **대류성 강수비 CRainf_frac** | +0.07 | **+0.38** | +0.13 | 돌발홍수에서 강력. 대류성 폭우를 모델이 못 잡음 |
| baseflow_index | +0.11 | +0.41 | +0.20 | 유역 반응성 |
| permeability | +0.27 | +0.03 | +0.26 | 투수성 |
| **CAPE** | +0.05 | **+0.29** | +0.13 | 대류 잠재력. 모든 체제 양수 |
| 관측 첨두 obs_peak (누수 기준선 L) | +0.45 | — | — | 사용 불가. area(+0.43)가 이에 맞먹음 |

유역 면적의 예측력(+0.43)이 관측값 누수 기준선(+0.45)에 거의 맞먹는다 — 외부 정보만으로 과소추정 위험을 관측값만큼 잘 예고할 수 있다는 뜻이다.

### 함정: 밴드 결합·강우 총량은 선택 편향 산물

극단 집합(Q99/NOAA)에서 음의 상관처럼 보이던 신호들이 전 범위에서 0으로 붕괴한다.

| 신호 | Q99 | NOAA | 전체강우 | 판정 |
| --- | ---: | ---: | ---: | --- |
| rel_width(밴드 폭) | −0.25 | −0.30 | **+0.01** | 전 범위 붕괴 → 선택 편향 |
| q99_q50_ratio | −0.25 | −0.30 | +0.01 | 전 범위 붕괴 |
| rain_sum(강우 총량) | −0.29 | −0.27 | **−0.03** | 전 범위 ≈0 |
| rain_max_1h·NWS 등급 | −0.24 | −0.07 | ≈0 | 전 범위 ≈0 |

- 밴드 폭이 넓을수록 obs가 그 안에 잡힐 확률이 높아 obs_class가 낮아지는 것은 **정의상 음의 결합**이지 예측력이 아니다.
- 강우 총량은 비가 많으면 LSTM이 예측·밴드를 올려 상단이 높아지고, 그래서 obs가 넘기 어려워지는 **모델 반응을 통한 간접 결합**이다. 극단만 보면 음수지만 전 범위에선 신호가 거의 없다.

### 모델 불확실성 신호는 전부 기각

"모델이 스스로 헷갈리면 과소추정 위험이 크다"는 가설(양의 상관 기대)을 세 신호로 검정했으나 모두 기각됐다.

| 신호 | 결과 | 해석 |
| --- | --- | --- |
| seed_spread(앙상블 분산, 상대형) | −0.02 (전체강우) | 크기로 나누면 0 붕괴 — 절대형 음수는 유량 크기 착시 |
| model1−model2 gap | −0.04 (유의성 없음) | 신호 없음 |
| band fanning rate(밴드 벌어짐 속도) | −0.182 | obs_class가 (관측−예측)이라 예측 기울기는 구조상 음수 |

## 결과 C — 상승 기울기 신호 (slope_signal)

홍수 상승부의 기울기가 위험도(obs_class)를 예고하는지 검정했다(clean 상승 구간 813개, 3 seed 평균 예측 분위).

| 지표 | Spearman r | 비고 |
| --- | ---: | --- |
| **관측 상승 기울기 rise_slope_m4** | **0.498** | 강한 신호 — 단 관측값 누수라 모델에 사용 불가(L) |
| 예측 fanning_slope | −0.182 | 예측 분위 기울기 중 최강이나 약함 |
| 예측 q99_rise_slope | −0.143 | — |
| 예측 q50_rise_slope | −0.074 | — |

관측 상승 기울기는 위험도와 `r≈0.5`로 강하게 연결되지만 관측값 누수라 쓸 수 없다. 누수 없는 **예측 분위 기울기는 단독으로는 신호가 약하다**(최대 |r|=0.182). 예측 기울기만으로 과소추정을 예고하기엔 부족하며, 유역 정적 특성·대류 지표와 결합해야 한다.

## 결과 D — 네 선 읽기 규칙의 타당성 (요약)

신호 분석과 별개로, 네 선의 기본 읽기 규칙도 데이터로 뒷받침된다.

- **예측 폭으로 읽기**: `q99 − q50` 폭이 전체 시각에서 관측의 약 122%, 관측 첨두 시각에서 절대 폭 최대 → 위쪽 예측 폭을 한쪽 불확실성 대용값으로 읽는 규칙 성립.
- **q50을 가운데 예측으로 읽기**: q50 가운데 예측 성능(RQ-1: NSE +0.149 / RMSE −0.273 / MAE −0.197, vs Model 1) 유지 → q50과 Model 1 짝비교 정당.
- **예측구간·보정성으로 읽지 않기**: 포함률 `P(관측 ≤ q_τ)`이 모든 τ에서 명목 미달(q99 0.787 vs 0.99)이고 한쪽이며, q99 pinball 최저(0.050)인데 포함률은 명목에 못 미친다 → 예측구간·보정성 해석 금지가 데이터로 필요(상세 [`05_calibration_sharpness.md`](05_calibration_sharpness.md)).

## 종합 해석 및 결론

- **과소추정의 정량 규모**: 가장 보수적인 `q99`조차 Q99 사건의 약 47%, NOAA/NWS catalog 홍수의 100%를 덮지 못한다. 위쪽 분위는 과소추정을 줄이되 극단 꼬리는 여전히 놓친다(RQ-2 문제 정의).
- **누수 없이 견고한 예측 신호 = 유역 정적 특성 + 대류 성격**: 유역 면적·투수성·기저유출 지표(baseflow_index)는 극단에서 전 범위까지 살아남고, 대류성 강수비·CAPE는 모든 체제에서 양수다. 같은 "강우"라도 **총량은 모델이 반응해 밴드를 올리는 입력(간접 결합, 쓸모 작음)**이지만 **대류성 성격은 모델이 구조적으로 못 잡는 부분(진짜 신호)**이다.
- **밴드 결합·강우 총량·모델 불확실성 신호는 모두 가짜**: 극단 집합에서의 음의 상관은 선택 편향(범위 제한) 또는 정의상 결합의 산물이며 전 범위에서 0으로 붕괴한다. 모델 진단은 반드시 전 강우 범위에서 검증해야 한다.
- **핵심 결론**: Model 2의 첨두 과소추정은 **대류성 돌발홍수 + 큰 유역**에서 두드러진다. 이 조건부 진단 틀이 RQ-0의 실질 deliverable이며, RQ-1~5가 같은 분위 출력을 일관되게 해석할 토대를 제공한다.

## 산출물

```text
output/model_analysis/band_signal/
├── band_shape/tables/   location_class_{q99,noaa}_summary.csv, gap_trajectory_q99_summary.csv,
│                        band_shape_spearman.csv
├── signal_sweep/tables/ branchA_spearman.csv, branchB2_spearman.csv,
│                        branchB2_seed_spread_spearman.csv
├── slope_signal/tables/ quantile_rise_slope_spearman.csv, m4method_spearman.csv
├── signal_sweep/figures/ signal_sweep_3scope.png, seed_spread_3scope.png
├── band_shape/figures/   location_class_bar.png, gap_trajectory.png, hydrograph_fan.png
└── (보정성·포함률 결과 D는 primary/calibration/tables/)
```

(사람이 읽는 결과·분석·결론 요약: `output/audit/rq0_results.html`)

## 주의점

- obs_class는 (관측 − 예측)의 위치라, 예측에서 파생된 신호(밴드 폭·분위 수준·예측 기울기)는 구조상 음의 결합을 가진다. 이런 밴드 결합(C) 신호를 예측력으로 오해하지 않는다.
- 극단 집합(Q99/NOAA)만 보면 범위 제한으로 상관이 왜곡된다. 신호의 견고성은 반드시 전 강우 범위(3-scope)로 확인한다.
- 관측 기반 신호(obs_peak·관측 상승 기울기)는 강하지만 누수라 사후 진단 기준선으로만 쓰고 모델 입력으로 쓰지 않는다.
- 포함률은 한쪽 형태 `P(관측 ≤ q_τ)`로 적고, 첨두 구간은 조건부 적중률로 부른다.
