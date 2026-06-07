# 00 연구 질문 ↔ 분석 매핑 (expanded DRBC rebuild)

## 서술 목적

본 논문의 핵심 주제를 세부 연구 질문(Research Question, RQ)으로 분해하고, 각 RQ가 어떤 분석 문서·스크립트·산출물에 1:1로 대응되는지 정리한다. 분석 결과 수치 자체는 다시 쓰지 않고, "어느 질문을 어떤 분석으로 답하는가"의 지도를 제공한다.

본 RQ 매핑은 **expanded DRBC observed test split(85 basin, seed 111/222/444, test 2014-2016)**을 canonical baseline으로 가정한다. 레거시 300-basin / pre-expanded DRBC holdout 매핑은 폐기(`docs/archive/analysis_legacy/` 보존).

## 핵심 주제와 주장

본 연구는 multi-basin LSTM hourly streamflow 예측에서 **극한 홍수 첨두 과소추정(extreme flood peak underestimation) 완화**를 다룬다.

핵심 주장은 **이중 deliverable**이다:
1. **(방법·분기) 4-quantile 출력 구조에서 관측 첨두(obs)가 예측 밴드 어디에 위치하는지(obs_class), 그 위치와 유역·기상 특성의 상관관계가 존재하는가** — RQ-0에서 읽기 규칙 + 해석 가능성(gate)을 함께 확인한다. 해석 가능성이 확인되면 RQ-1~5로 진행하고, 확인되지 않으면 출력 구조 분석과 한계 서술로 논문을 닫는다.
2. **(실증) RQ-0 해석 틀 위에서 Model 2 probabilistic quantile LSTM(pinball loss)이 Model 1 deterministic LSTM(NSE loss) 대비 expanded DRBC peak underestimation을 줄이는가** — RQ-1 ~ RQ-5에서 검증한다.

## 실험 고정 조건

- seed: `111 / 222 / 444` (paired). 학습·inference 재생성 없음 (Elice GPU 산출물 디스크 보유).
- basin scope: expanded DRBC observed test (85 basin). NOAA confirmed flood RQ는 49 NOAA basin ∩ 85 expanded = 46 basin (test-period event-bearing ≈ 21 basin) subset.
- temporal split: train `2000-2010`, validation `2011-2013`, test `2014-2016`.
- High-flow threshold: per-basin Q99 (train-period obs 분위). 단일 threshold.

## RQ 정의와 분석 매핑

### RQ-0. 4-quantile 출력 구조에서 obs 위치를 해석할 수 있는가 (방법론 + 분기)

해석 framework는 본 연구의 별도 deliverable이다. 두 갈래 질문을 동시에 답한다.

**Q-0a 읽기 규칙**: `q50`은 conditional median (M1 deterministic 대응), `q90/q95/q99`은 conservatism level. PI / return-period / 양방향 calibration 해석 금지.

**Q-0b 해석 가능성 gate**: obs가 예측 밴드(`q50`~`q99`) 어디에 드는지(obs_class 0~4)와 그 위치를 예고하는 신호(유역 정적 특성·대류 성격)의 상관관계가 존재하는가. 상관관계가 존재하면 → RQ-1~5 진행. 존재하지 않으면 → 출력 구조 분석과 한계 서술로 논문을 닫는다.

주장 수위: obs_class 상관관계는 test set 기술(describe) 수준이다. "이 상관관계를 이용해 새 사건의 분위를 사전 선택한다"는 운영 주장은 동일 test 데이터 검증이 불가하므로 이 연구 범위 밖이다.

| 항목 | 위치 |
| --- | --- |
| framework 문서 (방법) | [`docs/experiment/method/model/quantile_output_interpretation.md`](../../method/model/quantile_output_interpretation.md) |
| 검증·분석 문서 | [`00b_rq0_framework_validation.md`](00b_rq0_framework_validation.md) — 관측 위치(obs_class) 분포 + 위치 예측 신호 상관관계(유역 면적·대류 성격) + 상승 기울기 + 읽기 규칙 타당성 |
| 핵심 도구 | obs_class(관측 위치 구간 0~4) + 신호 3분류(독립/밴드결합/누수) + 3-scope Spearman + L1-L4 해석 layer + 6 prohibited interpretations |
| 산출물 | `output/model_analysis/band_signal/{band_shape,signal_sweep,slope_signal}/` + `primary/calibration/tables/` |
| Phase B 자물쇠 | `scripts/_lib/expanded_drbc.py` 의 vocabulary constants (TAU_ORDER, NOAA_LABELS, NOAA_REGEX 등) |

### RQ-1. q50가 중앙예측 성능을 유지하는가 (전제)

Model 2 `q50`이 Model 1 deterministic 대비 central performance를 큰 손해 없이 유지하는지 확인한다. RQ-2 주장의 전제 조건.

| 항목 | 위치 |
| --- | --- |
| 분석 문서 | [`01_q50_central.md`](01_q50_central.md) |
| 주요 스크립트 | `scripts/model/expanded_drbc/compute_rq1_central_metrics.py` |
| 산출물 | `output/model_analysis/primary/metrics/tables/rq1_central_*` + `primary/metrics/figures/rq1_*` |
| 해석 layer | L3 (운영 decision output) + Pairwise reading (q50 vs M1) |
| 결과 요약 | NSE +0.149 / RMSE −0.273 / MAE −0.197 (basin-median delta, M2 q50 − M1) |

### RQ-2. RQ-0 해석 틀 위에서 Model 2 q99가 Model 1 대비 peak underestimation을 줄이는가 (중심 주장)

RQ-0에서 obs_class 해석 가능성이 확인됐을 때, obs Q99 exceedance event + NOAA confirmed flood event에서 Model 2 `q90/q95/q99`(pinball loss 훈련)이 Model 1 deterministic(NSE loss 훈련) 대비 peak underestimation을 줄이는지 본다.

비자명성 근거: "q99 출력값이 q50보다 높다"는 자명하지만, "pinball loss로 훈련한 Model 2가 NSE로 훈련한 Model 1보다 극한 유량을 통계적으로 더 잘 표현한다"는 실증이 필요하다. RQ-1(q50도 함께 개선)이 이 non-trivial 학습 효과를 뒷받침한다.

| 항목 | 위치 |
| --- | --- |
| 분석 문서 | [`02_upper_quantile_peak_under.md`](02_upper_quantile_peak_under.md) |
| 주요 스크립트 | `build_q99_events.py`, `build_noaa_mapping.py`, `compute_rq2_alpha_peak_deficit.py`, `compute_rq2_beta_window_capture.py`, `compute_rq2_delta_threshold_recall.py` (모두 `scripts/model/expanded_drbc/`) |
| 산출물 | `tables/rq2_*` + `figures/rq2_alpha_by_tau.png`, `rq2_beta_by_tau.png`, `rq2_delta_recall_by_tau.png` |
| Metric triplet | α (per-event peak deficit), β (±6h window capture), δ (pooled Q99 threshold recall) |
| 해석 layer | L3 + L4 + Sequence reading (τ = 50 → 90 → 95 → 99) |
| 결과 요약 | q99 cross-basin α median = 0.018 (Q99) / 0.172 (NOAA); δ recall median = 0.583 |

### RQ-3. peak under 감소의 cost는 어떠한가

RQ-2 이득의 false-positive / over-prediction tradeoff를 정량화한다.

| 항목 | 위치 |
| --- | --- |
| 분석 문서 | [`03_cost.md`](03_cost.md) |
| 주요 스크립트 | `scripts/model/expanded_drbc/compute_rq3_cost.py` |
| 산출물 | `tables/rq3_far_*` + `rq3_over_prediction_*` + `figures/rq3_cost_recall_tradeoff.png` |
| Metric | FAR = P(q_τ > Q99 \| obs < Q99) + over-pred magnitude = mean(q_τ − obs \| q_τ > obs) |
| 해석 layer | L3 + Sequence reading |
| 결과 요약 | q99 FAR median = 0.016, over-pred median = 3.44 (basin median). recall +8× vs FAR +23× 비대칭 |

### RQ-4. heterogeneity (basin / event-type)

RQ-2 / RQ-3 효과가 basin이나 event-type에 따라 어떻게 다른가.

| sub-RQ | 분석 문서 | 주요 스크립트 | 핵심 결과 |
| --- | --- | --- | --- |
| RQ-4a basin cohort (M1 NSE 3-tier) | [`04a_basin_cohort.md`](04a_basin_cohort.md) | `compute_rq4a_nse_tier_stratify.py` | bottom tier에서 q99 α ≈ 0 (peak 완전 회복) — 단 FAR ≈ 0.06 |
| RQ-4b NOAA event-type | [`04b_event_type.md`](04b_event_type.md) | `compute_rq4b_event_type_stratify.py` (+ B2 매핑) | Flash Flood: q99 α = 0.42 잔존 (어려운 event-type) / Flood: q99 α = 0.06 |

### RQ-5. quantile output의 calibration·sharpness 품질

`q50/q90/q95/q99`가 quantile forecast로서 얼마나 calibrated·sharp한가. RQ-2 / RQ-3 decision output을 statistical foundation 위에 둔다.

| 항목 | 위치 |
| --- | --- |
| 분석 문서 | [`05_calibration_sharpness.md`](05_calibration_sharpness.md) |
| 주요 스크립트 | `scripts/model/hydrograph/analyze_expanded_drbc_probabilistic_diagnostics.py` (reuse) |
| 산출물 | `output/model_analysis/primary/calibration/` |
| 해석 layer | L1 + L2 + 일부 L3 |
| 결과 요약 | q99 empirical coverage = 0.787 (nominal 0.99, undercoverage) / q99 mean pinball = 1.638 (가장 낮음) / Q99-exceedance tail hit-rate q99 = 0.563 |

### Cross-tab (sanity)

Q99 event window ∩ NOAA event peak_time 분포 — Q99과 NOAA event 정의가 얼마나 일치하는지.

| 항목 | 위치 |
| --- | --- |
| 주요 스크립트 | `scripts/model/expanded_drbc/compute_cross_tab_q99_noaa_sanity.py` |
| 산출물 | `tables/cross_tab_q99_noaa_sanity_per_basin.csv` + `_pooled.csv` |
| 결과 | overlap 21 basin / 65 NOAA event 모두 Q99 window 안 (frac_noaa_in_q99 = 1.0); Q99 event의 16.7%만 NOAA 보정됨 (Q99 더 inclusive) |

## RQ 사이의 논리 흐름

```text
RQ-0 (framework, methodology)
    │
    ├─→ RQ-1 (q50 central 유지 전제)
    │       │
    │       └─→ RQ-2 (upper quantile peak under 감소)  ← 중심 결론
    │               │
    │               ├─→ RQ-3 (cost: FAR + over-prediction)
    │               ├─→ RQ-4a (basin cohort heterogeneity, M1 NSE tier)
    │               ├─→ RQ-4b (event-type heterogeneity, NOAA dominant label)
    │               └─→ RQ-5 (calibration·sharpness 통계 품질)
    │
    └─→ Cross-tab (Q99 ∩ NOAA sanity)
```

| 역할 | RQ |
| --- | --- |
| 방법 (framework) | RQ-0 |
| 전제 (premise) | RQ-1 |
| 중심 결론 (core claim) | RQ-2 |
| 비용 (cost) | RQ-3 |
| 일반화·조건화 (generalization) | RQ-4a, RQ-4b |
| 통계 품질 (forecast quality) | RQ-5 |
| sanity | Cross-tab |

## 본문 / supplement 배치 가이드

| 위치 | RQ |
| --- | --- |
| 본문 headline | RQ-0 framework 핵심, RQ-1 q50 central preservation, RQ-2 peak alleviation, RQ-3 cost tradeoff |
| 본문 secondary | RQ-4a basin cohort key panels, RQ-5 calibration / pinball 요약 |
| supplement | RQ-4b NOAA event-type 세부, RQ-5 IQR-distance tier (circular caveat), Cross-tab sanity 표, RQ-4a top tier over-pred 절대값 |
| archived (paper 범위 밖) | event-regime ML clustering, hydromet SHAP, extreme-rain stress, checkpoint sensitivity, broad-vs-natural, suppression diagnosis (`docs/archive/analysis_legacy/`) |

## 산출물 위치 요약

```text
output/model_analysis/primary/
├── metrics/
│   ├── data/required_series/seed{111,222,444}/required_series.csv
│   ├── data/raw_metrics/
│   ├── tables/rq1_*, rq2_*, rq3_*, rq4a_*, rq4b_*, cross_tab_*.csv
│   └── figures/rq1_*, rq2_*, rq3_*, rq4a_*, rq4b_*.png
└── calibration/
    ├── tables/quantile_*, upper_tail_*, tier_*, comparability_manifest.json
    ├── figures/
    └── report/report.md

output/model_analysis/band_signal/
├── band_shape/
├── signal_sweep/
├── slope_signal/
└── method_compare/
```

## 해석 framework 연결

본 문서는 "어느 분석이 어느 질문을 답하는지"의 구조만 다룬다. 각 분석에서 `q50/q90/q95/q99`를 어떤 의미로 읽어야 하는지, 어떤 해석이 금지되는지, RQ별로 어떤 해석 layer를 써야 하는지는 [`docs/experiment/method/model/quantile_output_interpretation.md`](../../method/model/quantile_output_interpretation.md)에서 정한다. paper 작성 시 두 문서를 함께 참조한다.

## Legacy 보존

레거시 300-basin / pre-expanded DRBC holdout 기반 구식 분석 문서는 `docs/archive/analysis_legacy/`로 이동:

- `03_event_regime_performance.md`
- `04_extreme_flood_proxy_performance.md`
- `05_extreme_rain_stress_test.md`
- `06_checkpoint_sensitivity.md`
- `07_broad_vs_natural_robustness.md`
- `09_event_suppression_diagnosis_protocol.md`
- `10_event_surrogate_shap.md`
- 300-basin subset hydrograph 해석 보고서

본 paper canonical 인용 범위에서 제외하지만 reproducibility / 비교를 위해 보존.
