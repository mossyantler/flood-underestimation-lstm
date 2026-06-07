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

### RQ-2. Model 2 상세 분석

Model 2의 내부 구조, 고유량·극한 홍수 성능, 불확실성 비용, 통계 품질, 이질성을 어떻게 이해할 것인가? `q50→q90→q95→q99` τ-진행이 첨두 과소추정을 체계적으로 줄이는지 확인하고, 이 결과를 SHAP·band signal·calibration·이질성 분석으로 입체적으로 뒷받침한다.

| 하위 분석 | 내용 | 분석 문서 | 산출물 |
| --- | --- | --- | --- |
| **2a. Q99/NOAA peak underestimation** | τ-진행에 따른 첨두 과소추정 완화 (α/β/δ triplet) | [`02_rq2_model2_detailed.md §2a`](02_rq2_model2_detailed.md) | `primary/metrics/tables/rq2_*` |
| **2b. SHAP 분석** | 모델 입력 기여도 — 어떤 특성이 예측에 영향을 미치는가 | [`02_rq2_model2_detailed.md §2b`](02_rq2_model2_detailed.md) | `output/model_analysis/shap/` |
| **2c. Spearman r / band signal** | 예측 밴드와 관측 위치의 상관관계, 밴드 형태 분석 | [`02_rq2_model2_detailed.md §2c`](02_rq2_model2_detailed.md) | `output/model_analysis/band_signal/` |
| **2d. confirmed flood 성능** | NWS flood-stage 확인 홍수에서의 성능 | [`02_rq2_model2_detailed.md §2d`](02_rq2_model2_detailed.md) | `output/model_analysis/confirmed_flood/` |
| **2e. cost: FAR·over-prediction** | 상위 분위 사용 시 false alarm + 과대추정 비용 | [`02_rq2_model2_detailed.md §2e`](02_rq2_model2_detailed.md) | `primary/metrics/tables/rq3_*` |
| **2f. calibration/sharpness** | 분위 출력의 통계 품질 진단 | [`02_rq2_model2_detailed.md §2f`](02_rq2_model2_detailed.md) | `output/model_analysis/primary/calibration/` |
| **2g. 이질성** | basin cohort(M1 NSE tier) + event-type(Flash Flood·Flood) 별 효과 차이 | [`02_rq2_model2_detailed.md §2g`](02_rq2_model2_detailed.md) | `primary/metrics/tables/rq4a_*, rq4b_*` |

---

### RQ-3. Model 2 해석 방법

Model 2의 4-quantile 출력(`q50/q90/q95/q99`)을 어떻게 해석해야 하는가? 관측 첨두가 예측 밴드 어디에 드는지(관측 위치 구간, obs_class)와 그 위치를 예고하는 신호는 무엇인가? 이 해석 기법 자체가 본 연구의 독립 기여물이다.

| 항목 | 위치 |
| --- | --- |
| 분석 문서 | [`03_rq3_obs_class_interpretation.md`](03_rq3_obs_class_interpretation.md) |
| 핵심 도구 | obs_class(관측 위치 구간 0~4) + 신호 3분류(독립/밴드결합/누수) + 3-scope Spearman |
| 산출물 | `output/model_analysis/band_signal/signal_sweep/` + `output/model_analysis/band_signal/band_shape/` |
| 결과 요약 | 유역 면적 r=+0.50, 대류성 강수비(CRainf_frac) r=+0.39 (NOAA scope) |
| 주의 | obs_class 상관관계는 test set 기술(describe) 수준. 운영 사전 선택 주장은 이 연구 범위 밖 |

---

## RQ 사이의 논리 흐름

```text
RQ-1 (base 성능 비교 — M1 q vs M2 q50)
    │
    └─→ RQ-2 (Model 2 상세 분석)
            │
            ├─→ 2a. Q99/NOAA peak underestimation
            ├─→ 2b. SHAP 분석
            ├─→ 2c. Spearman r / band signal
            ├─→ 2d. confirmed flood 성능
            ├─→ 2e. cost (FAR · over-prediction)
            ├─→ 2f. calibration / sharpness
            └─→ 2g. 이질성 (basin cohort · event-type)

RQ-3 (해석 방법 — obs_class · signal sweep · 범위값 한계)
    ↑
    RQ-2의 이해를 심화하는 독립 기여
```

| 역할 | RQ |
| --- | --- |
| base 성능 비교 (전제) | RQ-1 |
| 상세 분석 (중심) | RQ-2 |
| 해석 방법론 (기여) | RQ-3 |

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
