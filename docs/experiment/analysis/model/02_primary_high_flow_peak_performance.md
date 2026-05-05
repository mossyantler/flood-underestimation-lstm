# 02 Primary High-Flow / Peak 성능 분석

## 질문

이 분석은 같은 primary checkpoint에서 Model 2의 upper quantile output인 `q90/q95/q99`가 deterministic Model 1의 high-flow 및 peak underestimation을 줄이는지 확인한다. 이 문서가 현재 연구 가설의 핵심 분석이다.

## 상태

완료에 가깝다. `scripts/model/hydrograph/analyze_subset300_hydrograph_outputs.py`가 실행되어 all-validation-epoch required-series, flow stratum summary, quantile gap, observed peak hour table, chart가 생성되어 있다.

주요 산출물은 아래에 있다.

```text
output/model_analysis/quantile_analysis/analysis/
```

## 분석 단위

분석 대상은 seed `111 / 222 / 444`, epoch `005 / 010 / 015 / 020 / 025 / 030`, DRBC test basin 38개다. 각 required-series CSV는 998,678개 basin-hour row를 가진다. Primary 비교는 validation 기준으로 선택된 Model 1/2 epoch pair를 사용한다.

Flow stratum은 `all`, `basin_top10`, `basin_top5`, `basin_top1`, `basin_top0_1`, `observed_peak_hour`로 나뉜다. 내부 이름은 기존 호환성을 위해 유지하지만, 해석 표기는 threshold 기준으로 통일한다. 즉 `basin_top10 = Q90 exceedance`, `basin_top5 = Q95 exceedance`, `basin_top1 = Q99 exceedance`, `basin_top0_1 = Q99.9 exceedance`다. 핵심 해석 대상은 Q99 exceedance, Q99.9 exceedance, `observed_peak_hour`다.

## 생성된 표와 차트

주요 CSV는 `flow_strata_predictor_aggregate.csv`, `flow_strata_predictor_summary.csv`, `observed_peak_predictions.csv`, `observed_peak_quantile_zone.csv`, `observed_peak_quantile_zone_summary.csv`, `observed_peak_quantile_zone_aggregate.csv`, `primary_q99_exceedance_quantile_zone.csv`, `primary_q99_exceedance_quantile_zone_summary.csv`, `quantile_gap_aggregate.csv`, `quantile_gap_summary.csv`, `required_series_sanity_checks.csv`다.

생성된 chart는 아래 네 개다.

```text
output/model_analysis/quantile_analysis/analysis/charts/q99_exceedance_underestimation_fraction_by_epoch.png
output/model_analysis/quantile_analysis/analysis/charts/primary_peak_relative_bias_by_seed.png
output/model_analysis/quantile_analysis/analysis/charts/primary_q99_and_peak_quantile_zone_by_seed.png
output/model_analysis/quantile_analysis/analysis/charts/q99_exceedance_q99_q50_gap_pct_obs_by_epoch.png
```

Hydrograph plot은 `primary_seed_basin/` 아래에 684개가 생성되어 있다. 이 plot들은 본문용 대표 사례와 supplement용 사례 후보로 쓸 수 있다.

## 현재 해석

Primary epoch의 basin-specific Q99 exceedance에서 Model 1은 71.5%의 시간에서 관측값을 과소추정했고 median relative bias는 `-47.7%`였다. Model 2 `q50`은 85.8% 과소추정, median relative bias `-67.2%`로 더 나빴다. 따라서 Model 2의 중앙선이 high-flow를 개선했다는 주장은 성립하기 어렵다.

반면 upper quantile은 명확히 다른 패턴을 보인다. `q95`는 과소추정률을 61.9%로 낮추고 median relative bias를 `-21.0%`까지 완화했다. `q99`는 과소추정률을 44.9%로 낮추고 median relative bias를 `+12.4%`로 올렸다. 이는 q99가 peak를 더 많이 덮지만, 일부 구간에서는 과대 방향으로 이동할 수 있음을 뜻한다.

Observed peak hour에서도 같은 방향이 나온다. Model 1은 peak hour의 74.6%에서 과소추정했고 median relative bias는 `-36.6%`였다. Model 2 `q50`은 82.5% 과소추정으로 여전히 부족했다. `q95`는 과소추정률 62.3%, median relative bias `-16.2%`이고, `q99`는 과소추정률 50.0%, median relative bias `+10.9%`다.

Quantile-zone diagnostic은 observed high-flow가 실제로 어느 구간에 포함되는지를 직접 보여준다. Primary basin-specific Q99 exceedance 전체 27,978개 row 중 `>q99`가 12,574개, 즉 44.9%였고, `q95-q99`는 4,748개, `q90-q95`는 2,130개, `q50-q90`는 4,566개, `<=q50`는 3,960개였다. Peak 한 시점만 보면 114개 basin-seed peak 중 `>q99`가 57개, `q95-q99`가 14개, `q90-q95`가 7개, `q50-q90`가 16개, `<=q50`가 20개다.

![Primary quantile-zone share by seed](../../../../output/model_analysis/quantile_analysis/analysis/charts/primary_q99_and_peak_quantile_zone_by_seed.png)

Quantile gap도 high-flow에서 커진다. Primary Q99 exceedance(`basin_top1`)에서 평균 median `q99-q50` gap은 `20.9`이고, 관측값 대비 약 `74.1%`다. 이는 Model 2가 high-flow 상황에서 중앙선 위로 upper-tail margin을 열어 둔다는 의미다.

## 논문에서의 위치

이 분석은 Results의 핵심 표와 핵심 그림으로 들어가야 한다. 가장 안전한 메시지는 “probabilistic head가 median forecast를 개선했다”가 아니라, “같은 LSTM backbone에서 upper quantile head가 deterministic point estimate의 peak underestimation을 완화했다”다.

`q99`는 calibrated 99% predictive bound가 아니라 upper-tail decision output으로 써야 한다. 따라서 `q99` 결과는 flood warning 관점의 tail-aware output으로 해석하고, deterministic accuracy 비교에는 `q50`을 사용한다.

## 남은 작업

본문용으로는 Q99 exceedance(`basin_top1`), Q99.9 exceedance(`basin_top0_1`), `observed_peak_hour`만 남기고 표를 줄이는 것이 좋다. 또한 684개 hydrograph plot 중 대표 성공 사례, q99도 실패한 사례, q99가 과도하게 높은 사례를 각각 골라 Figure 5 후보로 정리해야 한다.
