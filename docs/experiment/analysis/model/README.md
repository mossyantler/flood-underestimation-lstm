# Model 1/2 결과 분석 문서 (expanded DRBC rebuild)

본 폴더는 expanded DRBC observed test (85 basin, seed 111/222/444, test 2014-2016) 기반 Model 1 deterministic LSTM과 Model 2 probabilistic quantile LSTM 결과를 3개 연구 질문(RQ-1/2/3)에 매핑해 정리한다. 각 문서는 단일 RQ만 다루며, 논문 Results section의 표·그림을 만들 때 직접 참조하는 것을 목표로 한다.

연구 질문(RQ-1 ~ RQ-3)과 분석 문서의 매핑은 [`00_research_question_analysis_map.md`](00_research_question_analysis_map.md)에서 정한다. 본 표는 분석 문서 단위 인덱스다.

| 순서 | 문서 | 역할 |
| ---: | --- | --- |
| 0 | [`00_research_question_analysis_map.md`](00_research_question_analysis_map.md) | 핵심 주제 → RQ-1/RQ-2/RQ-3 분해와 산출물 매핑 |
| 1 | [`01_rq1_q50_vs_m1.md`](01_rq1_q50_vs_m1.md) | RQ-1 — Model 1 q vs Model 2 q50 base 성능 비교 (NSE +0.149 / RMSE −0.273 / MAE −0.197) |
| 2 | [`02_rq2_model2_detailed.md`](02_rq2_model2_detailed.md) | RQ-2 — Model 2 상세 분석: Q99/NOAA peak underestimation (α/β/δ) · SHAP · Spearman r/band signal · confirmed flood · cost FAR · calibration/sharpness · 이질성 |
| 3 | [`03_rq3_obs_class_interpretation.md`](03_rq3_obs_class_interpretation.md) | RQ-3 — Model 2 해석 방법: 관측 위치 구간(obs_class) · signal sweep · 범위값 한계 |

RQ-3 해석 기법의 규칙과 금지 해석은 [`docs/experiment/method/model/quantile_output_interpretation.md`](../../method/model/quantile_output_interpretation.md)에 둔다. 그 규칙이 실데이터에서 타당한지와 obs_class를 예고하는 신호 상관관계 분석 결과는 [`03_rq3_obs_class_interpretation.md`](03_rq3_obs_class_interpretation.md)에 정리한다.

## 해석 원칙

Primary 결과는 **expanded DRBC observed test 2014-2016**를 기준으로 한다. test split은 `data/CAMELSH_generic/drbc_expanded_observed_test/`에서 산출되며, seed 111/222/444 paired aggregation을 사용한다.

Model 2의 `q50`은 conditional median (M1 deterministic 대응). `q90/q95/q99`는 upper-tail decision output / conservatism level로 별도 해석한다. lower quantile이 없으므로 `q99`를 calibrated 99% prediction interval / return-period estimate로 표기하지 않는다. 자세한 해석 규칙은 [`docs/experiment/method/model/quantile_output_interpretation.md`](../../method/model/quantile_output_interpretation.md).

## 산출물 위치

```text
output/model_analysis/primary/
├── metrics/
│   ├── data/required_series/seed{111,222,444}/required_series.csv
│   ├── data/raw_metrics/
│   ├── tables/
│   │   ├── rq1_central_metrics_*.csv
│   │   ├── rq2_q99_per_basin_thresholds.csv, rq2_q99_events_85basin.csv, rq2_q99_basin_warnings.csv
│   │   ├── rq2_id_normalization_report.csv, rq2_noaa_basin_overlap_summary.csv, rq2_noaa_events_overlap.csv
│   │   ├── rq2_alpha_event_peak_deficit_{q99,noaa}.csv + _summary.csv
│   │   ├── rq2_beta_window_capture_{q99,noaa}.csv + _summary.csv
│   │   ├── rq2_delta_threshold_recall_*.csv
│   │   ├── rq3_far_*.csv, rq3_over_prediction_magnitude_*.csv
│   │   ├── rq4a_nse_tier_*.csv
│   │   ├── rq4b_event_type_metrics.csv, rq4b_event_type_mapping.csv, rq4b_noaa_annotation_unmatched.csv
│   │   └── cross_tab_q99_noaa_sanity_*.csv
│   └── figures/
│       ├── rq1_central_metric_boxplots.png, rq1_paired_delta_scatter.png
│       ├── rq2_alpha_by_tau.png, rq2_beta_by_tau.png, rq2_delta_recall_by_tau.png
│       ├── rq3_cost_recall_tradeoff.png
│       ├── rq4a_tier_metric_heatmap.png
│       └── rq4b_event_type_bar.png
└── calibration/
    ├── tables/
    ├── figures/
    └── report/report.md

output/model_analysis/band_signal/
├── band_shape/
├── signal_sweep/
├── slope_signal/
└── method_compare/
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

구 RQ-0~RQ-5 기반 분석 문서 7개는 [`docs/archive/analysis_legacy/`](../../../archive/analysis_legacy/)로 이동됨. 현재 canonical 인용 범위에서 제외되며, reproducibility·비교를 위해 보존한다.

- `00b_rq0_framework_validation.md` (구 RQ-0)
- `01_q50_central.md` (구 RQ-1)
- `02_upper_quantile_peak_under.md` (구 RQ-2)
- `03_cost.md` (구 RQ-3)
- `04a_basin_cohort.md` (구 RQ-4a)
- `04b_event_type.md` (구 RQ-4b)
- `05_calibration_sharpness.md` (구 RQ-5)
