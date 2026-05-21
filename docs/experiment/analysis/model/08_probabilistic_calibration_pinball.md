# 08 Probabilistic Calibration / Pinball 분석

## 질문

이 분석은 Model 2의 `q50/q90/q95/q99`가 quantile forecast로서 얼마나 잘 calibrated되어 있는지, 그리고 quantile별 pinball/AQS가 어떤지 확인하기 위한 probabilistic diagnostic이다.

## 상태

완료에 가깝다. `scripts/model/hydrograph/analyze_subset300_probabilistic_diagnostics.py`가 실행되어 quantile별 pinball/AQS, one-sided calibration, high-flow 조건부 tail hit-rate, upper-tail spread table과 figure가 생성되어 있다.

주요 산출물은 아래에 있다.

```text
output/model_analysis/probabilistic_diagnostics/
```

## 생성된 표와 그림

주요 CSV는 `quantile_pinball_summary.csv`, `quantile_pinball_by_stratum.csv`, `quantile_calibration_summary.csv`, `quantile_calibration_by_stratum.csv`, `upper_tail_spread_summary.csv`, `upper_tail_spread_by_stratum.csv`, `input_manifest.csv`, `chart_manifest.csv`다. 요약 report는 아래에 있다.

```text
output/model_analysis/probabilistic_diagnostics/report/probabilistic_diagnostics_report.md
```

생성된 주요 그림은 아래 네 개다.

```text
output/model_analysis/probabilistic_diagnostics/figures/primary_all_quantile_calibration.png
output/model_analysis/probabilistic_diagnostics/figures/primary_pinball_by_stratum.png
output/model_analysis/probabilistic_diagnostics/figures/primary_q99_q50_spread_by_stratum.png
output/model_analysis/probabilistic_diagnostics/figures/same_epoch_all_calibration_error.png
```

## 해석 기준

현재 quantile set은 `q50/q90/q95/q99`뿐이다. Lower quantile이 없으므로 central prediction interval, interval score, Winkler score, 95% PI width는 공식 metric으로 쓰지 않는다.

`coverage_fraction = mean(obs <= q_tau)`는 전체 test period에서는 empirical one-sided coverage로 읽을 수 있다. 하지만 observed Q99 exceedance 같은 조건부 high-flow stratum에서는 formal calibration이라기보다 tail hit-rate로 읽어야 한다. 이미 관측 유량이 큰 시점만 골랐기 때문이다.

## 현재 해석

Primary all-hour calibration은 Model 2 quantile이 nominal level보다 낮게 잡혀 있음을 보여준다. Median empirical coverage는 `q50 = 0.272`, `q90 = 0.500`, `q95 = 0.658`, `q99 = 0.835`다. 따라서 `q99`는 peak underestimation을 줄이는 upper-tail output이지만, calibrated 99% predictive quantile이라고 쓰면 안 된다.

Pinball/AQS 관점에서는 all-hour 기준 `q99`의 mean pinball loss가 가장 낮다. Primary seed median 기준 mean pinball은 `q50 = 2.135`, `q90 = 2.267`, `q95 = 1.919`, `q99 = 1.243`이고, AQS는 각각 `4.270`, `4.535`, `3.838`, `2.486`이다. 이는 현재 test distribution에서 높은 quantile output이 asymmetric loss 기준으로 유리하게 보인다는 뜻이지만, nominal calibration 부족과 함께 읽어야 한다.

Observed Q99-exceedance stratum에서는 calibration이 아니라 tail hit-rate로 읽는다. 이 조건부 stratum에서 median empirical coverage는 `q50 = 0.133`, `q90 = 0.288`, `q95 = 0.374`, `q99 = 0.560`이다. 즉 `q99`도 Q99-exceedance hour의 약 44%는 여전히 넘지 못하지만, `q50/q95`보다 underestimation을 줄인다.

Upper-tail spread는 Model 2가 high-flow에서 central line 위로 얼마나 여유를 두는지 보여준다. Primary Q99-exceedance에서 median `q99-q50` spread는 `20.836`이고 관측값 대비 `74.581%`다. Quantile crossing sanity check는 `q90<q50`, `q95<q90`, `q99<q95` 모두 0 row로 통과했다.

## 주의점

`q99`가 peak underestimation을 줄인다고 해서 calibrated 99% predictive quantile이라고 말하면 안 된다. 현재 calibration table은 오히려 nominal undercoverage를 보여주므로, 논문에서는 `upper-tail decision output` 또는 `tail-aware output`이라는 표현을 유지한다.

## 남은 작업

본문에는 all-hour calibration plot과 Q99-exceedance tail hit-rate/pinball compact table만 넣고, same-epoch calibration error와 stratum별 상세 table은 supplement로 보내는 편이 좋다. 이 분석은 Model 2가 probabilistic forecast로 완전히 calibrated되었음을 주장하기 위한 근거가 아니라, upper quantile improvement claim의 calibration caveat를 명확히 하는 방어용 분석으로 쓰는 것이 안전하다.
