# 00 연구 질문 ↔ 분석 매핑 (expanded DRBC rebuild)

## 서술 목적

본 논문의 핵심 주제를 세부 연구 질문(Research Question, RQ)으로 분해하고, 각 RQ가 어떤 분석 문서·스크립트·산출물에 1:1로 대응되는지 정리한다. 분석 결과 수치 자체는 다시 쓰지 않고, "어느 질문을 어떤 분석으로 답하는가"의 지도를 제공한다.

본 RQ 매핑은 **expanded DRBC observed test split(85 basin, seed 111/222/444, test 2014-2016)**을 canonical baseline으로 가정한다. scaling_300 / DRBC-38 holdout 매핑은 폐기(`docs/archive/analysis_legacy/` 보존).

## 핵심 주제와 주장

본 연구는 multi-basin LSTM hourly streamflow 예측에서 **극한 홍수 첨두 과소추정(extreme flood peak underestimation) 완화**를 다룬다.

핵심 주장은 **이중 deliverable**이다:
1. **(방법) 병렬 quantile output `q50/q90/q95/q99` 동시 해석 framework** — RQ-0에서 정의한다.
2. **(실증) 그 framework 위에서 Model 2 probabilistic quantile LSTM이 Model 1 deterministic LSTM 대비 expanded DRBC peak underestimation을 줄이는가** — RQ-1 ~ RQ-5에서 검증한다.

## 실험 고정 조건

- seed: `111 / 222 / 444` (paired). 학습·inference 재생성 없음 (Elice GPU 산출물 디스크 보유).
- basin scope: expanded DRBC observed test (85 basin). NOAA confirmed flood RQ는 49 NOAA basin ∩ 85 expanded = 46 basin (test-period event-bearing ≈ 21 basin) subset.
- temporal split: train `2000-2010`, validation `2011-2013`, test `2014-2016`.
- High-flow threshold: per-basin Q99 (train-period obs 분위). 단일 threshold.

## RQ 정의와 분석 매핑

### RQ-0. 병렬 quantile output을 어떻게 동시 해석하는가 (방법론)

해석 framework는 본 연구의 별도 deliverable이다. `q50`은 conditional median (M1 deterministic 대응), `q90/q95/q99`은 conservatism level. PI / return-period / 양방향 calibration 해석 금지.

| 항목 | 위치 |
| --- | --- |
| 분석 문서 | [`docs/experiment/method/model/quantile_output_interpretation.md`](../../method/model/quantile_output_interpretation.md) |
| 핵심 도구 | L1-L4 해석 layer + Pairwise/Sequence/Spread reading + 6 prohibited interpretations |
| Phase B 자물쇠 | `scripts/_lib/expanded_drbc.py` 의 vocabulary constants (TAU_ORDER, NOAA_LABELS, NOAA_REGEX 등) |

### RQ-1. q50가 중앙예측 성능을 유지하는가 (전제)

Model 2 `q50`이 Model 1 deterministic 대비 central performance를 큰 손해 없이 유지하는지 확인한다. RQ-2 주장의 전제 조건.

| 항목 | 위치 |
| --- | --- |
| 분석 문서 | [`01_q50_central.md`](01_q50_central.md) |
| 주요 스크립트 | `scripts/model/expanded_drbc/compute_rq1_central_metrics.py` |
| 산출물 | `output/model_analysis/expanded_drbc_test/tables/rq1_central_*` + `figures/rq1_*` |
| 해석 layer | L3 (운영 decision output) + Pairwise reading (q50 vs M1) |
| 결과 요약 | NSE +0.149 / RMSE −0.273 / MAE −0.197 (basin-median delta, M2 q50 − M1) |

### RQ-2. upper quantile이 peak underestimation을 줄이는가 (중심 주장)

obs Q99 exceedance event + NOAA confirmed flood event에서 `q90/q95/q99`가 peak underestimation을 줄이는지 본다.

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
| 산출물 | `output/model_analysis/expanded_drbc_test/probabilistic_diagnostics/` |
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
output/model_analysis/expanded_drbc_test/
├── tables/
│   ├── rq1_central_metrics_*.csv
│   ├── rq2_q99_per_basin_thresholds.csv, rq2_q99_events_85basin.csv, rq2_q99_basin_warnings.csv
│   ├── rq2_id_normalization_report.csv, rq2_noaa_basin_overlap_summary.csv, rq2_noaa_events_expanded_overlap.csv
│   ├── rq2_alpha_event_peak_deficit_{q99,noaa}.csv + _summary.csv
│   ├── rq2_beta_window_capture_{q99,noaa}.csv + _summary.csv
│   ├── rq2_delta_threshold_recall_*.csv
│   ├── rq3_far_*.csv, rq3_over_prediction_magnitude_*.csv
│   ├── rq4a_nse_tier_*.csv
│   ├── rq4b_event_type_metrics.csv, rq4b_event_type_mapping.csv, rq4b_noaa_annotation_unmatched.csv
│   └── cross_tab_q99_noaa_sanity_*.csv
├── figures/
│   ├── rq1_central_metric_boxplots.png, rq1_paired_delta_scatter.png
│   ├── rq2_alpha_by_tau.png, rq2_beta_by_tau.png, rq2_delta_recall_by_tau.png
│   ├── rq3_cost_recall_tradeoff.png
│   ├── rq4a_tier_metric_heatmap.png
│   └── rq4b_event_type_bar.png
└── probabilistic_diagnostics/      (RQ-5 — reuse)
```

## 해석 framework 연결

본 문서는 "어느 분석이 어느 질문을 답하는지"의 구조만 다룬다. 각 분석에서 `q50/q90/q95/q99`를 어떤 의미로 읽어야 하는지, 어떤 해석이 금지되는지, RQ별로 어떤 해석 layer를 써야 하는지는 [`docs/experiment/method/model/quantile_output_interpretation.md`](../../method/model/quantile_output_interpretation.md)에서 정한다. paper 작성 시 두 문서를 함께 참조한다.

## Legacy 보존

scaling_300 / DRBC-38 holdout 기반 구식 분석 문서는 `docs/archive/analysis_legacy/`로 이동:

- `03_event_regime_performance.md`
- `04_extreme_flood_proxy_performance.md`
- `05_extreme_rain_stress_test.md`
- `06_checkpoint_sensitivity.md`
- `07_broad_vs_natural_robustness.md`
- `09_event_suppression_diagnosis_protocol.md`
- `10_event_surrogate_shap.md`
- `subset300_hydrograph_interpretation_report.md`

본 paper canonical 인용 범위에서 제외하지만 reproducibility / 비교를 위해 보존.
