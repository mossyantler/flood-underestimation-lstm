# Model 1/2 결과 분석 문서 (expanded DRBC rebuild)

본 폴더는 expanded DRBC observed test (85 basin, seed 111/222/444, test 2014-2016) 기반 Model 1 deterministic LSTM과 Model 2 probabilistic quantile LSTM 결과를 7개 연구 질문(RQ)에 1:1 매핑해 정리한다. 각 문서는 단일 RQ만 다루며, 논문 Results section의 표·그림을 만들 때 직접 참조하는 것을 목표로 한다.

연구 질문(RQ-0 ~ RQ-5)과 분석 문서의 1:1 매핑은 [`00_research_question_analysis_map.md`](00_research_question_analysis_map.md)에서 정한다. 본 표는 분석 문서 단위 인덱스다.

| 순서 | 문서 | 역할 |
| ---: | --- | --- |
| 0 | [`00_research_question_analysis_map.md`](00_research_question_analysis_map.md) | 핵심 주제 → RQ-0/1/2/3/4a/4b/5 분해와 산출물 매핑 |
| 0b | [`00b_rq0_framework_validation.md`](00b_rq0_framework_validation.md) | RQ-0 — 분위 출력 해석과 관측 위치(obs_class) 추측: 위치 분포(q99 47%/NOAA 100% above_q99)·신호 상관(유역 면적·대류 성격)·상승 기울기 분석 |
| 1 | [`01_q50_central.md`](01_q50_central.md) | RQ-1 — Model 2 `q50`가 Model 1 deterministic 대비 central 성능을 유지하는가 |
| 2 | [`02_upper_quantile_peak_under.md`](02_upper_quantile_peak_under.md) | RQ-2 — upper quantile (`q90/q95/q99`)이 peak underestimation을 줄이는가 (α + β + δ triplet, Q99 + NOAA dual scope) |
| 3 | [`03_cost.md`](03_cost.md) | RQ-3 — peak under 감소의 cost (FAR + over-prediction magnitude) |
| 4a | [`04a_basin_cohort.md`](04a_basin_cohort.md) | RQ-4a — basin heterogeneity (M1 NSE 3-tier cohort) |
| 4b | [`04b_event_type.md`](04b_event_type.md) | RQ-4b — NOAA event-type heterogeneity (Flash Flood / Flood / Coastal Flood) |
| 5 | [`05_calibration_sharpness.md`](05_calibration_sharpness.md) | RQ-5 — quantile output calibration·sharpness forecast quality |

방법론 RQ-0 (병렬 quantile output 해석 framework) 문서는 [`docs/experiment/method/model/quantile_output_interpretation.md`](../../method/model/quantile_output_interpretation.md)에 둔다. 그 framework가 실데이터에서 타당한지, 그리고 분위 출력으로 관측 위치(obs_class)를 추측하는 신호가 무엇인지(`band_signal/` 상관관계 분석)를 정리한 결과 문서는 [`00b_rq0_framework_validation.md`](00b_rq0_framework_validation.md)다.

## 해석 원칙

Primary 결과는 **expanded DRBC observed test 2014-2016**를 기준으로 한다. test split은 `data/CAMELSH_generic/drbc_expanded_observed_test/`에서 산출되며, seed 111/222/444 paired aggregation을 사용한다.

Model 2의 `q50`은 conditional median (M1 deterministic 대응). `q90/q95/q99`는 upper-tail decision output / conservatism level로 별도 해석한다. lower quantile이 없으므로 `q99`를 calibrated 99% prediction interval / return-period estimate로 표기하지 않는다. 자세한 해석 규칙은 [`docs/experiment/method/model/quantile_output_interpretation.md`](../../method/model/quantile_output_interpretation.md).

## 산출물 위치

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
└── probabilistic_diagnostics/      (RQ-5; analyze_expanded_drbc_probabilistic_diagnostics.py reuse)
```

## 분석 스크립트

```text
scripts/_lib/expanded_drbc.py                                # C0 vocabulary lock + utilities
scripts/model/expanded_drbc/
  compute_rq1_central_metrics.py                              # A1
  build_q99_events.py                                         # B1
  build_noaa_mapping.py                                       # B2
  compute_rq2_alpha_peak_deficit.py                           # B3
  compute_rq2_beta_window_capture.py                          # B4
  compute_rq2_delta_threshold_recall.py                       # B5
  compute_rq3_cost.py                                         # B6
  compute_rq4a_nse_tier_stratify.py                           # B7
  compute_rq4b_event_type_stratify.py                         # B8
  compute_cross_tab_q99_noaa_sanity.py                        # B9
scripts/model/hydrograph/analyze_expanded_drbc_probabilistic_diagnostics.py   # RQ-5 (reuse)
```

## Legacy 보존

pre-expanded DRBC holdout 기반 구식 분석은 [`docs/archive/analysis_legacy/`](../../../archive/analysis_legacy/)로 이동. 현재 paper canonical 기준은 expanded observed DRBC test **85개**이며, legacy 결과는 reproducibility 비교로만 보존한다.
