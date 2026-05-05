# 03 Event-Regime 성능 분석

## 질문

이 분석은 Model 2 upper quantile의 peak-underestimation 완화 효과가 어떤 observed high-flow event-regime에서 강하게 나타나는지 확인한다. 여기서 flood type은 causal mechanism 확정이 아니라 hydrometeorological descriptor-space grouping이다.

## 상태

표 분석은 완료에 가깝고, 논문용 그림은 아직 보강이 필요하다. `scripts/model/event_regime/analyze_subset300_event_regime_errors.py`가 실행되어 event-level long/wide table, ML event-regime aggregate, flood relevance tier sensitivity, rule-label sensitivity가 생성되어 있다.

주요 산출물은 아래에 있다.

```text
output/model_analysis/quantile_analysis/event_regime_analysis/
```

## 분석 단위

분석 대상은 DRBC test basin 38개에서 추출한 observed high-flow event candidate 570개다. 같은 event set을 paired seed `111 / 222 / 444`에 공통으로 사용한다.

Primary stratification은 `hydromet_only_7 + KMeans(k=3)`으로 만든 ML event-regime이다. Regime은 `Recent rainfall`, `Antecedent / multi-day rain`, `Weak / low-signal hydromet regime`으로 해석한다. Rule-based `degree_day_v2` label은 QA와 sensitivity로만 사용한다.

## 생성된 표

주요 CSV는 `event_regime_error_table_long.csv`, `event_regime_error_table_wide.csv`, `ml_event_regime_predictor_aggregate.csv`, `paired_delta_aggregate.csv`, `rule_label_predictor_aggregate.csv`, `flood_relevance_tier_predictor_aggregate.csv`, `event_regime_feature_sanity.csv`다.

현재 별도 논문용 event-regime chart는 아직 부족하다. 본문에는 regime별 paired under-deficit reduction과 threshold recall delta를 한 장의 point/interval plot으로 만드는 것이 좋다.

## 현재 해석

모든 ML event-regime에서 Model 2 `q50`은 Model 1보다 observed peak underestimation을 줄이지 못한다. `Recent rainfall` regime에서 Model 1의 peak underestimation fraction은 0.735이고 median observed-peak relative error는 `-48.0%`인데, Model 2 `q50`은 underestimation fraction 0.898, median error `-73.8%`로 악화된다. `Antecedent / multi-day rain`과 `Weak / low-signal hydromet regime`에서도 같은 방향이다.

Upper quantile은 일관되게 under-deficit을 줄인다. `Recent rainfall`에서 `q95`는 median peak under-deficit을 Model 1 대비 약 `17.2%p` 줄이고, threshold recall을 약 `0.205` 높인다. `q99`는 under-deficit reduction이 약 `30.0%p`, threshold recall delta가 약 `0.366`이다.

`Antecedent / multi-day rain`에서도 `q95`는 under-deficit을 약 `19.4%p`, `q99`는 약 `38.5%p` 줄인다. `Weak / low-signal hydromet regime`에서는 `q95`가 약 `17.5%p`, `q99`가 약 `35.4%p` under-deficit을 줄인다.

다만 q99는 항상 더 좋은 single prediction이라고 볼 수 없다. `Recent rainfall`에서 q99의 normalized event RMSE delta는 양수로 나타나며, 이는 underestimation은 줄이지만 event hydrograph shape 또는 magnitude 측면에서는 과대/불안정 tradeoff가 있을 수 있음을 뜻한다.

## 해석 제한

570개 event는 모두 Q99 observed high-flow candidate지만, flood relevance proxy 기준으로 대부분이 `high_flow_below_2yr_proxy`다. 따라서 이 결과를 공식 flood inventory나 큰 return-period flood 전체에 대한 결과로 과장하면 안 된다.

`Weak / low-signal hydromet regime`은 snow-dominant class가 아니다. Feature sanity check에서도 이 regime은 낮은 snow_fraction basin을 포함하므로, causal snowmelt claim은 피해야 한다.

## 논문에서의 위치

이 분석은 Results 세 번째 블록, 즉 heterogeneity 분석으로 두는 것이 좋다. 핵심 문장은 “upper quantile의 underestimation mitigation은 특정 regime에만 국한되지 않고 세 ML event-regime 전반에서 반복되지만, q99는 recall과 overprediction tradeoff가 있다” 정도가 안전하다.

## 남은 작업

`paired_delta_aggregate.csv`를 이용해 regime별 `q50/q90/q95/q99`의 under-deficit reduction, threshold recall delta, normalized event RMSE delta를 한 장의 figure로 만들어야 한다. 또한 small tier와 rule-label sensitivity는 supplement로 분리하는 편이 좋다.
