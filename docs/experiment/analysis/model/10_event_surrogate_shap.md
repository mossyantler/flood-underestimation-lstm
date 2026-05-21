# 10 Event-Level Surrogate SHAP 분석

## 질문

이 분석은 `Model 2 q95/q99`가 `Model 1`의 observed-peak underestimation을 줄이는 효과가 어떤 event descriptor와 basin static attribute 조건에서 커지는지 확인한다. 직접 LSTM 내부를 설명하는 분석이 아니라, event-level error target을 설명하는 surrogate model에 SHAP을 적용한 post-hoc 진단이다.

## 상태

초기 분석 완료. `scripts/model/event_regime/analyze_subset300_event_surrogate_shap.py`가 실행되어 event-level table, surrogate diagnostic, global SHAP importance, local event explanation, figure, metadata, markdown report가 생성되어 있다.

주요 산출물은 아래에 있다.

```text
output/model_analysis/quantile_analysis/event_surrogate_shap/
```

## 분석 단위

입력은 `event_regime_error_table_wide.csv`의 1,710개 seed-event row이며, 같은 event의 seed `111 / 222 / 444` row를 먼저 평균해 570개 event row로 접는다. 이렇게 해야 seed row를 독립 표본처럼 취급하는 pseudo-replication을 피할 수 있다.

Surrogate target은 아래 다섯 개다.

| target | 의미 |
| --- | --- |
| `model1_under_deficit_pct` | Model 1 observed-peak under-deficit 평균 |
| `q95_under_deficit_reduction_pct` | Model 1 대비 Model 2 q95 under-deficit 감소량 |
| `q99_under_deficit_reduction_pct` | Model 1 대비 Model 2 q99 under-deficit 감소량 |
| `q99_nrmse_tradeoff_pct` | Model 1 대비 Model 2 q99 event NRMSE 증가량 |
| `q99_overprediction_pct` | q99 observed-peak relative error의 positive part 평균 |

설명 변수는 event hydromet descriptor, hydrograph shape descriptor, basin static attributes, 그리고 최소한의 categorical context를 사용한다. 주요 변수는 `recent_1d_ratio`, `recent_3d_ratio`, `antecedent_7d_ratio`, `snowmelt_fraction`, `event_mean_temp`, `rising_time_hours`, `event_duration_hours`, `unit_area_peak`, `area`, `slope`, `aridity`, `snow_fraction`, `baseflow_index`, `forest_fraction`, `ml_event_regime`, `flood_relevance_tier`, `selected_threshold_quantile`이다.

## 생성된 표와 차트

주요 표는 아래와 같다.

```text
output/model_analysis/quantile_analysis/event_surrogate_shap/tables/event_surrogate_table.csv
output/model_analysis/quantile_analysis/event_surrogate_shap/tables/surrogate_target_diagnostics.csv
output/model_analysis/quantile_analysis/event_surrogate_shap/tables/surrogate_fold_diagnostics.csv
output/model_analysis/quantile_analysis/event_surrogate_shap/tables/global_feature_importance.csv
output/model_analysis/quantile_analysis/event_surrogate_shap/tables/local_top_event_explanations.csv
```

주요 figure는 아래와 같다.

```text
output/model_analysis/quantile_analysis/event_surrogate_shap/figures/combined_mean_abs_shap_summary.png
output/model_analysis/quantile_analysis/event_surrogate_shap/figures/model1_under_deficit_pct_mean_abs_shap.png
output/model_analysis/quantile_analysis/event_surrogate_shap/figures/q95_under_deficit_reduction_pct_mean_abs_shap.png
output/model_analysis/quantile_analysis/event_surrogate_shap/figures/q99_under_deficit_reduction_pct_mean_abs_shap.png
output/model_analysis/quantile_analysis/event_surrogate_shap/figures/q99_nrmse_tradeoff_pct_mean_abs_shap.png
output/model_analysis/quantile_analysis/event_surrogate_shap/figures/q99_overprediction_pct_mean_abs_shap.png
```

요약 report와 metadata는 아래에 둔다.

```text
output/model_analysis/quantile_analysis/event_surrogate_shap/report/event_surrogate_shap_report.md
output/model_analysis/quantile_analysis/event_surrogate_shap/metadata/event_surrogate_shap_metadata.json
```

## 현재 해석

RandomForest surrogate의 평균 cross-validation R2는 `model1_under_deficit_pct`가 0.736, `q95_under_deficit_reduction_pct`가 0.502, `q99_under_deficit_reduction_pct`가 0.588, `q99_nrmse_tradeoff_pct`가 0.560, `q99_overprediction_pct`가 0.648이다. 따라서 event descriptor와 basin attribute만으로도 under-deficit과 q99 tradeoff의 상당한 분산을 설명할 수 있다.

Global SHAP 기준으로 Model 1 under-deficit에는 `area`, `event_mean_temp`, `recent_3d_ratio`, `aridity`가 크게 나타났다. q95 reduction은 `recent_1d_ratio`, `area`, `aridity`, `slope`가 상위에 있고, q99 reduction은 `area`, `aridity`, `event_mean_temp`, `recent_1d_ratio`가 상위에 있다. q99의 NRMSE tradeoff와 overprediction은 특히 `area`, `recent_1d_ratio`, `unit_area_peak`에 크게 반응한다.

현재 결과의 안전한 문장은 “upper quantile의 underestimation mitigation과 q99 tradeoff는 event rainfall intensity뿐 아니라 basin scale/static context와 함께 변한다”이다. 반대로 “SHAP이 LSTM이 내부적으로 어떤 물리 과정을 배웠는지 증명했다”는 식의 표현은 피해야 한다.

## 해석 제한

이 분석의 SHAP 값은 원래 LSTM 또는 quantile head의 SHAP 값이 아니다. Event-level descriptor로 만든 surrogate error model의 SHAP 값이다. 따라서 causal flood mechanism이나 원 모델 내부 attention/gradient 해석으로 쓰면 안 된다.

또한 `area` 중요도가 매우 크게 나온다. 이것은 basin scale이 event error와 q99 tradeoff를 강하게 구분한다는 유용한 신호지만, DRBC 38개 basin의 event 표본 구조와 event count imbalance가 함께 반영된 결과일 수 있다. 논문에서는 basin-block robustness나 대표 event hydrograph 확인과 함께 읽는 것이 안전하다.

## 논문에서의 위치

이 분석은 Results 본문 핵심 claim보다 supplement 또는 Discussion 보조 분석에 더 적합하다. 본문에서는 event-regime 결과를 먼저 제시하고, surrogate SHAP은 “어떤 descriptor가 under-deficit reduction과 q99 tradeoff를 동반하는지”를 설명하는 후속 진단으로 배치하는 것이 좋다.
