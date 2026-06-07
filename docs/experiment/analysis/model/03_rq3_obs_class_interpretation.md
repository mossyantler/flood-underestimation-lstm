# 03 RQ-3 — obs_class 해석 방법론 + 모델 평가

## 질문 (RQ-3)

Model 2는 한 시점마다 네 예측선 `q50 / q90 / q95 / q99`를 동시에 낸다. 이 네 선을 어떻게 읽어야 하는가(관측 위치 구간, obs_class)? 그 위치를 예고하는 신호는 무엇이며, 그 틀로 **Model 2가 Model 1 대비 과소추정을 실제로 줄이는가**?

이 해석 기법 자체가 본 연구의 독립 기여물이다. 관측 첨두가 밴드 최상단 `q99`마저 넘는 경우(`above_q99`)는 모델이 첨두를 과소추정한 사건이며, obs_class 분류가 "모델이 언제 첨두를 놓치는가"를 조건부로 진단하는 틀을 제공한다.

해석 규칙 자체는 [`quantile_output_interpretation.md`](../../method/model/quantile_output_interpretation.md)에 있다.

하위 분석: **3a** obs_class 틀 정의 · **3b** 독립 신호 분류 · **3c** area 사분위 층화 분포 · **3d** RF obs_class 분류기 훈련 · **3e** 모델 평가(predicted vs actual) · **3f** NOAA overlay 검증.

---

## 3a. obs_class 틀 정의 + 실제 분포

관측 첨두가 예측 밴드 안 어디에 드는지를 다섯 서수 구간(obs_class)으로 나눈다. 정의는 `signal_sweep_allrain.py:63-67`을 단일 기준으로 한다. (본문 범위 용어는 AllRain scope / Q99 scope / NOAA scope.)

| obs_class | 정의 | 뜻 |
| ---: | --- | --- |
| 0 | `관측 ≤ q50` | 가운데 예측보다 낮음(과대추정 쪽) |
| 1 | `q50 < 관측 ≤ q90` | 밴드 하부 |
| 2 | `q90 < 관측 ≤ q95` | 밴드 중상부 |
| 3 | `q95 < 관측 ≤ q99` | 밴드 최상부 근접 |
| 4 | `관측 > q99` | **q99도 못 잡음 = 과소추정** |

### 사건 범위 (혼용 금지)

극단 사건만 보면 범위 제한(선택 편향)으로 상관이 왜곡되므로, Q99·NOAA 외에 전체 강우 사건을 대조 범위로 둔다.

| 범위 (브랜치) | 기준 | 사건 수 |
| --- | --- | --- |
| **NOAA** | NWS flood-stage 확인 홍수 catalog (2014-2016 × 85 basin) | 65건 / 21 basin |
| **AllRain** | 2014-2016 강우 반응 전체 탐지 | 16,639건 / 84 basin |

> Q99 초과 사건 범위는 본 문서의 headline 범위에서 제외한다. obs_class 분포·신호의 정식 비교축은 **AllRain**(전체강우 대조)과 **NOAA**(확인 홍수)다.

### 결과 A — 관측 위치 분포 (유역 중앙값)

| obs_class | NOAA 홍수 |
| --- | ---: |
| `q50_to_q90` | 0.0 |
| `q95_to_q99` | 0.0 |
| **`above_q99`** | **1.0** |

NOAA/NWS catalog 홍수 범위는 유역 중앙값 기준 **100%가 `above_q99`** — 확인 홍수 첨두 시각에서 Model 2 q99마저 관측을 못 잡는 비율이 압도적이다.

산출물: `output/model_analysis/primary/metrics/tables/location_class_{q99,noaa}.csv` + `_pooled.csv` + `_summary.csv` (논문 본문 용어는 "관측 위치 구간"); `output/model_analysis/band_signal/band_shape/`.

---

## 3b. 독립 신호 분류 (3-scope Spearman r)

후보 신호를 세 부류로 나눈다:

| 부류 | 의미 | 쓸모 |
| --- | --- | --- |
| **I 독립** | 외부 정보 (유역 정적 특성, 대류 지표) | 진짜 예측 신호 |
| **C 밴드 결합** | obs_class 정의에 이미 들어가 부분 순환 | 예측 신호로 쓸 수 없음 |
| **L 관측 누수** | 관측값 자체 (obs_peak, 관측 상승 기울기) | 기준선 (상한) — 사용 불가 |

### 독립 신호 순위 (Spearman r vs obs_class, 3-scope)

| 신호 | Q99 | NOAA | 전체강우(AllRain) | 해석 |
| --- | ---: | ---: | ---: | --- |
| **유역 면적 area** (I) | +0.50 | +0.50 | +0.27 | 범용 최강. 큰 유역일수록 obs가 밴드 위쪽 |
| **대류성 강수비 CRainf_frac** (I) | +0.05 | **+0.39** | +0.13 | 돌발홍수 특화. NOAA에서 강력 |
| baseflow_index (I) | +0.20 | +0.44 | +0.20 | 유역 반응성 |
| permeability (I) | +0.32 | +0.04 | +0.26 | 투수성 |
| CAPE (I) | +0.03 | +0.22 | +0.13 | 대류 잠재력 |
| 관측 첨두 obs_peak (L) | +0.46 | +0.44 | — | 사용 불가. area(+0.50)가 이에 맞먹음 |

유역 면적의 예측력(+0.50)이 관측값 누수 기준선(+0.46)에 맞먹거나 더 크다 — 외부 정보만으로 과소추정 위험을 관측값만큼 잘 예고할 수 있다. 3-scope(Q99/NOAA/AllRain)에서 살아남는 신호만 진짜 신호로 채택한다.

### 가짜 신호 (선택 편향 · 정의상 결합)

| 신호 | Q99 | NOAA | 전체강우 | 판정 |
| --- | ---: | ---: | ---: | --- |
| rel_width (밴드 폭, C) | −0.14 | −0.16 | **+0.01** | 전 범위 붕괴 → 선택 편향 |
| rain_sum (강우 총량) | −0.24 | +0.08 | **−0.03** | 전 범위 ≈0 |
| seed_spread (앙상블 분산) | −0.02 | — | −0.02 | 크기 나누면 0 |

### 상승 기울기 신호 (참고)

| 지표 | Spearman r | 비고 |
| --- | ---: | --- |
| 관측 상승 기울기 rise_slope_m4 (L) | **0.498** | 강한 신호 — 단 관측값 누수라 사용 불가 |
| 예측 fanning_slope | −0.182 | 누수 없는 예측 기울기 중 최강이나 약함 |

산출물: `output/model_analysis/band_signal/signal_sweep/tables/allrain_spearman.csv` · `forcing_spearman.csv` · `static_spearman.csv`; `band_signal/slope_signal/tables/quantile_rise_slope_spearman.csv` · `m4method_spearman.csv`; `signal_sweep/figures/signal_sweep_3scope.png`. (파일명 앞부분은 신호갈래 — `static`은 정적 유역 속성 신호, `forcing`은 강우·forcing 신호, `allrain`은 전체 강우 사건 탐색. 신호갈래는 신호 종류를, scope(Q99/NOAA/AllRain)는 사건 집합을 가리키며 서로 직교한다. `static`·`forcing` 표는 Q99·NOAA 두 scope를 모두 담는다.)

---

## 3c. area 사분위 층화 분포

area 사분위(Q1=소형 ~ Q4=대형)로 유역을 나눈 뒤 각 그룹의 above_q99 비율 비교:

| area 그룹 | n_events | above_q99 비율 |
| ---: | ---: | ---: |
| Q1 (소형) | 400 | 20% |
| Q2 | 285 | 40% |
| Q3 | 148 | 58% |
| Q4 (대형) | 93 | 65% |

above_q99 비율이 Q1 20% → Q4 65%로 단조 증가한다. NOAA scope에서는 단조가 더 뚜렷하다(Q1 23% → Q4 82%).

**CRainf 이분 (SSOT split)**: 대류성 강수비 중앙값 이분에서 **고 CRainf 그룹의 above_q99 비율(68%)이 저 CRainf(24%)의 약 2.8배**다. 이 split은 `scripts/_lib/expanded_drbc.py`의 `crainf_median_split` 공용 함수가 단일 출처이며, **RQ-2(§2f)의 강우 유형별 출력 분석과 동일한 split**을 공유한다(같은 split에서 고 67.9% / 저 24.1%).

스크립트: `scripts/model/expanded_drbc/compute_rq0_area_stratified_obsclass.py`

산출물:
```text
output/model_analysis/band_signal/signal_sweep/tables/
  rq0_area_stratified_obsclass_q99.csv · rq0_area_stratified_obsclass_noaa.csv
  rq0_crainf_stratified_obsclass_noaa.csv
output/model_analysis/band_signal/signal_sweep/figures/rq0_stratified_obsclass.png
```

---

## 3d. RF obs_class 분류기 훈련

**질문**: 관측 없이 입력 특성(S1: 유역 정적 + 강우 강제력)만으로 obs_class(밴드 위치)를 예측할 수 있는가?

AllRain 전체 강우 사건(16,639행 / 84 basin)으로 RandomForest 분류기를 훈련한다. 이진 headline = `above_q99`(oc==4) vs rest, secondary = ordinal oc 0–4.

- **Split**: 유역 단위 Basin GroupKFold(5) = headline(누수 차단) / 사건 단위 Event StratifiedKFold = 상한 대조.
- **누수 통제**: 정적 속성이 유역 상수이므로 사건 단위 split은 유역 정체성을 test로 누수시킨다. GroupKFold가 이를 구조적으로 차단.

### CV 결과 (mean across folds)

| Split | accuracy | weighted F1 | above_q99 recall |
| --- | --- | --- | --- |
| Basin GroupKFold (headline) | 0.799 | 0.788 | 0.430 |
| Event StratifiedKFold (상한 대조) | 0.784 | 0.789 | 0.602 |

leakage gap이 작다(accuracy 거의 동일) — 강우 forcing이 분류를 지배하므로 event split이 basin split보다 크게 유리하지 않다.

### Feature importance & ablation

- **Event 수준 top feature**: `cape_max`, `rain_sum_event`, `rain_max_1h`, `crainf_frac_mean`, `area` (강우 forcing 계열이 주도, area는 top-5 내).
- **Ablation (밴드 결합 허위 신호)**: S1 accuracy 0.799 / above_q99 recall 0.430 vs **S1+S2(band)** accuracy 0.789 / recall 0.410 — 밴드 결합 신호(rel_width, q99_q50_ratio)는 marginal gain이 음수에 가깝다. §3b의 가짜 신호 판정과 일관.

> area의 between-basin 단변량 상관(§3b r=+0.50)과 event 수준 multivariate RF에서 강우 강도가 더 중요한 점은 상보적이다(전자는 유역 간 경향, 후자는 유역 내 사건 구분).

스크립트: `scripts/model/expanded_drbc/run_obsclass_pipeline.py` (build → train → overlay → plot → report)

산출물:
```text
output/model_analysis/band_signal/signal_sweep/tables/
  obsclass_model_matrix_allrain.parquet (외 static/noaa) — 접미는 신호갈래·사건집합 (allrain=전체 강우, static=정적신호 Q99 overlay, noaa=NOAA overlay)
  obsclass_cv_metrics.csv · obsclass_confusion_binary.csv · obsclass_confusion_ordinal.csv
  obsclass_feature_importance.csv · obsclass_ablation_band_signal.csv
output/model_analysis/band_signal/signal_sweep/report/obsclass_classifier_summary.md
```

---

## 3e. 모델 평가 — predicted vs actual obs_class (DIRECT / surrogate 분리)

**category error 방지가 핵심.** 서로 다른 두 평가를 산출물·라벨로 명확히 분리한다.

### (a) DIRECT — 관측 band-position 기반 Model 2 평가 [genuine M2 evaluation]

관측 첨두가 Model 2 밴드 어디에 드는지(obs_class)를 직접 집계한다. `above_q99`=관측이 q99 천장을 넘음=**M2 q99 과소추정**, `below_q50`=관측이 중앙 예측보다 낮음=과대추정. M1 NSE tier(top/mid/bottom 1/3, `compute_rq4a_nse_tier_stratify.py:62` machinery 재사용)로 분할해 "M1 대비" 평가로 연결한다.

**M2 q99 과소추정율 (above_q99 비율, Q99 scope 관측 기반)**

| M1 NSE tier (n_events) | M2 q99 과소추정율 | M2 과대추정율(below_q50) |
| --- | ---: | ---: |
| top (364) | **0.570** | 0.025 |
| mid (244) | 0.444 | 0.053 |
| bottom (318) | 0.265 | **0.252** |
| ALL (926) | 0.432 | 0.110 |

**핵심**: M2 q99 과소추정은 M1이 가장 약한 유역(bottom)이 아니라 **M1이 잘 맞추는 유역(top)에 집중**된다(0.570 vs 0.265). bottom tier는 반대로 과대추정(below_q50 0.252)이 가장 크다. NOAA scope도 같은 방향(top 0.667, mid 0.429; bottom n=3<10은 n-gate suppress).

### (b) surrogate — RF forcing-surrogate predictability [NOT M2 evaluation]

§3d RF 분류기의 predicted-vs-actual obs_class 혼동행렬은 "강제력·정적 속성만으로 밴드 위치를 예측 가능한가"의 진단일 뿐 **Model 2 성능 평가가 아니다**(`run_obsclass_pipeline.py:141` guardrail 유지). 혼동행렬의 FN/FP는 분류기 오류율이며 M2 과소추정율로 라벨하지 않는다.

| 지표 (RF 분류기, NOT M2) | 값 |
| --- | ---: |
| classifier FN rate | 0.569 |
| classifier FP rate | 0.094 |
| above_q99 recall | 0.431 |

스크립트: `scripts/model/expanded_drbc/compute_rq3e_obsclass_eval.py`

산출물:
```text
output/model_analysis/primary/metrics/tables/
  rq3e_obsclass_eval_direct_oc4recall.csv · rq3e_obsclass_eval_direct_byclass.csv
  rq3e_obsclass_eval_surrogate_confusion.csv · rq3e_obsclass_eval_surrogate_summary.csv
  rq4a_nse_tier_assignments.csv · rq4a_nse_tier_metrics.csv
output/model_analysis/primary/metrics/figures/rq3e_obsclass_eval_direct.png
```

> draft/results_3rq_draft.md(§3.8 부근)와 정합: **DIRECT(oc==4 관측 기반)만 "M2 과소추정"** 으로 서술하고, RF 혼동행렬은 forcing-surrogate predictability로만 라벨한다.

---

## 3f. NOAA overlay 검증

**질문**: AllRain으로 훈련한 RF 분류기가 NOAA 완전 held-out 유역(basin intersection = 0)에 전이되는가?

**결과 — NOAA overlay 평가 불가**: NOAA 확인 홍수 유역이 모두 AllRain 훈련 유역에 포함되어(basin intersection 완전), held-out NOAA 유역 집합이 **공집합**이다. 따라서 NOAA scope의 정직한 전이 갭은 본 데이터에서 측정 불가하다. overlay 산출물에 남는 유일한 held-out 집합은 Q99 초과 사건(1 basin / 24 events)이나, 이는 본 문서 headline 범위(AllRain/NOAA)에서 제외하므로 결론 근거로 쓰지 않는다.

> **한계 명시**: AllRain 훈련 표본이 DRBC 시험 85 유역을 사실상 모두 덮으므로, "완전 held-out 유역 전이"는 현재 split로는 검증할 수 없다. 이 분류기는 §3d/§3e와 같이 **사후 진단 도구**로만 해석하고 운영 예측에 사용하지 않는다.

스크립트: `scripts/model/expanded_drbc/eval_obsclass_overlay.py`

산출물: `output/model_analysis/band_signal/signal_sweep/tables/obsclass_overlay_metrics.csv`

---

## 네 선 읽기 규칙의 타당성

- **예측 폭으로 읽기**: `q99 − q50` 폭이 전체 시각에서 관측의 약 122%, 관측 첨두 시각에서 절대 폭 최대.
- **q50을 가운데 예측으로 읽기**: q50 중앙 성능(NSE +0.149 / RMSE −0.273 / MAE −0.197, vs Model 1) 유지(RQ-1).
- **예측구간·보정성으로 읽지 않기**: 포함률이 모든 τ에서 명목 미달(q99 0.787 vs 0.99)이고 한쪽 → 예측구간·보정성 해석 금지가 데이터로 필요(§2d).

## 범위값 한계

- obs_class 상관관계는 **test set 기술(describe) 수준**이다. "이 상관관계로 새 사건의 분위를 사전 선택한다"는 운영 주장은 동일 test 데이터 검증이 불가하므로 범위 밖이다.
- obs_class는 단일값이 아닌 범위(0~4)이므로 "정확히 몇 번째 분위가 맞다"는 주장 금지.
- 극단 집합(NOAA)만 보면 범위 제한으로 상관이 왜곡된다. 신호 견고성은 반드시 전 강우 범위(AllRain 포함 3-scope)로 확인한다.

## 종합 결론

- **과소추정의 조건부 진단**: 대류성 돌발홍수 + 큰 유역에서 q99마저 넘는 과소추정이 두드러진다. DIRECT 평가상 M2 q99 과소추정은 M1이 잘 맞추는 top-NSE 유역에 집중된다.
- **진짜 예측 신호**: 유역 면적·투수성·기저유출(독립)과 대류성 강수비·CAPE(독립) — 3-scope에서 살아남는다.
- **가짜 신호**: 밴드 폭·강우 총량·모델 불확실성 — 선택 편향 또는 정의상 결합 산물.
- **category error 방지**: DIRECT(관측 기반)만 M2 과소추정으로, RF 혼동행렬은 forcing-surrogate predictability로 분리해 해석한다.

## 주의점

- obs_class는 (관측 − 예측)의 위치라 예측 파생 신호(밴드 폭·분위 수준·예측 기울기)는 구조상 음의 결합을 가진다. 밴드 결합(C) 신호를 예측력으로 오해하지 않는다.
- 포함률은 한쪽 형태 `P(관측 ≤ q_τ)`로 적고, 첨두 구간은 조건부 적중률로 부른다.
- 사건 수 N 혼용 금지: NOAA 전체 **65**(§3a) vs 홍수 유형 subset **40**(§2e) vs CRainf 유형 subset **57**(§2f).
