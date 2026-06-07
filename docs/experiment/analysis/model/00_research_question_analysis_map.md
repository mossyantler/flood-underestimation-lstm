# 00 연구 질문 ↔ 분석 매핑 (3-RQ 구조)

## 서술 목적

본 논문의 핵심 주제를 세 연구 질문(RQ)으로 분해하고, 각 RQ가 어떤 분석 문서·스크립트·산출물에 대응되는지 정리한다. 분석 결과 수치 자체는 다시 쓰지 않고, "어느 질문을 어떤 분석으로 답하는가"의 지도를 제공한다.

본 RQ 매핑은 **expanded DRBC observed test split(85 basin, seed 111/222/444, test 2014-2016)**을 canonical baseline으로 가정한다.

## 핵심 주제와 주장

본 연구는 multi-basin LSTM hourly streamflow 예측에서 **극한 홍수 첨두 과소추정(extreme flood peak underestimation) 완화**를 다룬다.

공식 비교축: **Model 1 (Deterministic LSTM, NSE loss)** vs **Model 2 (Probabilistic quantile LSTM, pinball loss)**.

Model 3 (physics-guided hybrid): 후속 확장, 현재 논문 범위 밖.

## 실험 고정 조건

- seed: `111 / 222 / 444` (paired). Model 2 seed `333`: NaN loss 중단. Model 1 seed `333`: fair comparison 위해 final aggregate 제외.
- basin scope: expanded DRBC observed test (85 basin). NOAA confirmed flood RQ는 49 NOAA basin ∩ 85 expanded = 46 basin (test-period event-bearing ≈ 21 basin) subset.
- temporal split: train `2000-2010`, validation `2011-2013`, test `2014-2016`.
- High-flow threshold: per-basin Q99 (train-period obs 분위). 단일 threshold.

---

## RQ 정의와 분석 매핑

### RQ-1. Model 1 q vs Model 2 q50 — base 성능 비교

Model 2 probabilistic quantile LSTM의 conditional median output `q50`이 Model 1 deterministic LSTM output 대비 중앙예측(central) 성능을 어떻게 유지하는가? 두 모델의 base 성능을 직접 비교하고, RQ-2 상세 분석의 진입 전제를 확립한다.

| 항목 | 위치 |
| --- | --- |
| 분석 문서 | [`01_rq1_q50_vs_m1.md`](01_rq1_q50_vs_m1.md) |
| 주요 스크립트 | `scripts/model/expanded_drbc/compute_rq1_central_metrics.py` |
| 산출물 | `output/model_analysis/primary/metrics/tables/rq1_*` + `primary/metrics/figures/rq1_*` |
| 해석 기준 | 6-metric (NSE, KGE, bias, MAE, RMSE, FHV) + per-basin 이질성 |
| 결과 요약 | NSE +0.149 / RMSE −0.273 / MAE −0.197 (basin-median delta, M2 q50 − M1) |

---

### RQ-2. Model 2 출력 심층 분석

Model 2의 4-quantile 출력(q50/q90/q95/q99)은 어떻게 생겼는가? 입력 특성과 출력 간 상관 구조는? 유량 체제·강우 유형·실제 홍수 상황에서 출력 패턴이 어떻게 달라지는가?

| 하위 분석 | 내용 | 분석 문서 | 산출물 |
| --- | --- | --- | --- |
| **2a. 각 quantile 출력 특성** | τ별 α/β/δ — q50/q90/q95/q99 각각의 출력 형태 기술 (단일 τ 점 추정 진단) | [`02_rq2_model2_detailed.md §2a`](02_rq2_model2_detailed.md) | `primary/metrics/tables/rq2_*` |
| **2b. 입력-출력 상관 (SHAP)** | 정적 vs 동적 기여도, area×soil_depth 게이트, slope 극한 반전, 강우 유형 신호 (CRainf_frac, CAPE) | [`02_rq2_model2_detailed.md §2b`](02_rq2_model2_detailed.md) | `output/model_analysis/shap/` |
| **2c. 밴드 형태 및 gap 구조** | q50~q99 밴드 폭·꼬리·위치, gap trajectory | [`02_rq2_model2_detailed.md §2c`](02_rq2_model2_detailed.md) | `output/model_analysis/band_signal/` |
| **2d. 보정 및 예리도** | 전 τ 경험적 포함률 vs 공칭값, Pinball 손실, climatology 대비 skill score | [`02_rq2_model2_detailed.md §2d`](02_rq2_model2_detailed.md) | `output/model_analysis/primary/calibration/` |
| **2e. 실제 홍수 사건 출력** | NOAA 확인 홍수 65건 21유역 출력 관찰, 홍수 유형별 패턴 (Flash Flood vs Flood) | [`02_rq2_model2_detailed.md §2e`](02_rq2_model2_detailed.md) | `output/model_analysis/confirmed_flood/` |
| **2f. 강우 유형별 출력 패턴** | SHAP의 CRainf_frac·CAPE 강우 유형 구분법 차용, 대류성 vs 전선성 사건에서 τ 출력 분포·α 패턴 신규 분석 | [`02_rq2_model2_detailed.md §2f`](02_rq2_model2_detailed.md) | `primary/metrics/tables/rq2f_*` |

---

### RQ-3. obs_class 해석 방법론 + 모델 평가

Model 2의 4-quantile 출력을 해석하는 obs_class 틀은 무엇이고, 그 틀로 Model 2가 Model 1 대비 과소추정을 실제로 줄이는가? 이 해석 기법 자체가 본 연구의 독립 기여물이다.

| 하위 분석 | 내용 | 분석 문서 | 산출물 |
| --- | --- | --- | --- |
| **3a. obs_class 틀 정의** | 관측 위치 구간 0–4 서수 정의, Q99/NOAA 사건 실제 분포 확인 | [`03_rq3_obs_class_interpretation.md §3a`](03_rq3_obs_class_interpretation.md) | `band_signal/band_shape/tables/` |
| **3b. 독립 신호 분류** | 신호 3분류 (I/C/L), 3-scope Spearman r (Q99/NOAA/전체강우) | [`03_rq3_obs_class_interpretation.md §3b`](03_rq3_obs_class_interpretation.md) | `band_signal/signal_sweep/tables/` |
| **3c. area 사분위 층화 분포** | area Q1~Q4별 above_q99 비율 단조 증가 (Q1 20% → Q4 65%) | [`03_rq3_obs_class_interpretation.md §3c`](03_rq3_obs_class_interpretation.md) | `signal_sweep/figures/rq0_stratified_obsclass.png` |
| **3d. RF obs_class 분류기 훈련** | S1 features → predicted obs_class, Basin GroupKFold + Event upper bound, S1 vs S1+S2 ablation | [`03_rq3_obs_class_interpretation.md §3d`](03_rq3_obs_class_interpretation.md) | `signal_sweep/tables/obsclass_cv_metrics.csv` 외 |
| **3e. 모델 평가 — predicted vs actual** | DIRECT(관측 band-position oc==4 비율 = M2 q99 과소추정, M1 NSE tier별) / surrogate(RF 혼동행렬 = forcing-surrogate predictability, M2 평가 아님) 분리 | [`03_rq3_obs_class_interpretation.md §3e`](03_rq3_obs_class_interpretation.md) | `primary/metrics/tables/rq3e_obsclass_eval_{direct,surrogate}_*.csv`, `rq4a_*` |
| **3f. NOAA overlay 검증** | AllRain으로 훈련 → NOAA 완전 held-out 유역 평가 (basin intersection = 0) | [`03_rq3_obs_class_interpretation.md §3f`](03_rq3_obs_class_interpretation.md) | `signal_sweep/tables/obsclass_overlay_metrics.csv` |

---

## RQ 사이의 논리 흐름

```text
RQ-1 (전제 — M1 vs M2 q50 base 성능 비교)
    │
    └─→ RQ-2 (Model 2 출력 심층 분석)
            │
            ├─→ 2a. 각 quantile 출력 특성 (α/β/δ)
            ├─→ 2b. 입력-출력 상관 (SHAP)
            ├─→ 2c. 밴드 형태 및 gap 구조
            ├─→ 2d. 보정 및 예리도
            ├─→ 2e. 실제 홍수 사건 출력 (NOAA + 홍수 유형)
            └─→ 2f. 강우 유형별 출력 패턴

RQ-3 (obs_class 해석 방법론 + 모델 평가)
    ├─→ 3a. obs_class 틀 정의
    ├─→ 3b. 독립 신호 분류 (3-scope Spearman)
    ├─→ 3c. area 사분위 층화 분포
    ├─→ 3d. RF obs_class 분류기 훈련
    ├─→ 3e. 모델 평가 — predicted vs actual obs_class
    └─→ 3f. static/NOAA overlay 검증
```

| 역할 | RQ |
| --- | --- |
| base 성능 비교 (전제) | RQ-1 |
| Model 2 출력 특성 (중심) | RQ-2 |
| obs_class 해석 + 모델 평가 (기여 + 결론) | RQ-3 |

---

## Cross-tab (sanity)

Q99 event window ∩ NOAA event peak_time 분포 — Q99과 NOAA event 정의가 얼마나 일치하는지.

| 항목 | 위치 |
| --- | --- |
| 주요 스크립트 | `scripts/model/expanded_drbc/compute_cross_tab_q99_noaa_sanity.py` |
| 산출물 | `tables/cross_tab_q99_noaa_sanity_per_basin.csv` + `_pooled.csv` |
| 결과 | overlap 21 basin / 65 NOAA event 모두 Q99 window 안 (frac_noaa_in_q99 = 1.0); Q99 event의 16.7%만 NOAA 보정됨 (Q99 더 inclusive) |

---

## 산출물 위치 요약

```text
output/model_analysis/primary/
├── metrics/
│   ├── data/required_series/seed{111,222,444}/required_series.csv
│   ├── tables/rq1_*, rq2_*, rq3_*, rq4a_*, rq4b_*, cross_tab_*.csv
│   └── figures/rq1_*, rq2_*, rq3_*, rq4a_*, rq4b_*.png
└── calibration/
    ├── tables/
    └── figures/

output/model_analysis/band_signal/
├── band_shape/
├── signal_sweep/
├── slope_signal/
└── method_compare/

output/model_analysis/shap/
├── direction/
├── q99/
└── test_split/

output/model_analysis/confirmed_flood/
├── data/
├── figures/
├── tables/
└── report/
```

## Legacy 보존

구 RQ-0~RQ-5 기반 분석 문서는 `docs/archive/analysis_legacy/`로 이동. reproducibility·비교를 위해 보존하나 canonical 인용 범위에서 제외.

- `00b_rq0_framework_validation.md` (구 RQ-0 framework gate)
- `01_q50_central.md` (구 RQ-1)
- `02_upper_quantile_peak_under.md` (구 RQ-2)
- `03_cost.md` (구 RQ-3)
- `04a_basin_cohort.md` (구 RQ-4a)
- `04b_event_type.md` (구 RQ-4b)
- `05_calibration_sharpness.md` (구 RQ-5)
