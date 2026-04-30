# 08 Probabilistic Calibration / Pinball 분석

## 질문

이 분석은 Model 2의 `q50/q90/q95/q99`가 quantile forecast로서 얼마나 잘 calibrated되어 있는지, 그리고 quantile별 pinball/AQS가 어떤지 확인하기 위한 probabilistic diagnostic이다.

## 상태

예정이다. 현재 산출물에는 one-sided coverage fraction과 upper-tail spread인 `q95-q50`, `q99-q50`은 계산되어 있다. 하지만 quantile별 pinball/AQS, formal calibration error table, calibration plot은 아직 공식 산출물로 고정하지 않았다. 따라서 이 문서에는 최종 결과 해석을 쓰지 않는다.

이미 있는 관련 산출물은 아래다.

```text
output/model_analysis/quantile_analysis/analysis/flow_strata_predictor_aggregate.csv
output/model_analysis/quantile_analysis/analysis/quantile_gap_aggregate.csv
output/model_analysis/quantile_analysis/analysis/quantile_gap_summary.csv
```

## 예정 산출물

계획된 출력 위치는 아래처럼 둔다.

```text
output/model_analysis/probabilistic_diagnostics/
```

예정 표는 `quantile_pinball_summary.csv`, `quantile_calibration_summary.csv`, `quantile_calibration_by_stratum.csv`, `upper_tail_spread_summary.csv`다. 예정 그림은 calibration plot과 high-flow stratum별 pinball/AQS bar plot이다.

## 해석 기준

현재 quantile set은 `q50/q90/q95/q99`뿐이다. Lower quantile이 없으므로 central prediction interval, interval score, Winkler score, 95% PI width는 공식 metric으로 쓰지 않는다.

`coverage_fraction = mean(obs <= q_tau)`는 전체 test period에서는 empirical one-sided coverage로 읽을 수 있다. 하지만 observed top 1% 같은 조건부 high-flow stratum에서는 formal calibration이라기보다 tail hit-rate로 읽어야 한다. 이미 관측 유량이 큰 시점만 골랐기 때문이다.

## 주의점

`q99`가 peak underestimation을 줄인다고 해서 calibrated 99% predictive quantile이라고 말하면 안 된다. Formal calibration table이 만들어지기 전까지는 `upper-tail decision output`이라는 표현을 유지한다.
