# Subset300 Hydrograph Output Analysis

## 서술 목적

이 문서는 `subset300` Model 1 / Model 2 all-validation-epoch hydrograph 산출물을 연구 질문에 맞게 해석하는 방법을 정리한다. 자세한 raw artifact 설명은 `output/model_analysis/quantile_analysis/analysis/analysis_outputs_guide.md`에 두고, 이 문서는 논문 메시지와 분석 방법의 기준을 남긴다.

## 분석 대상

분석 입력은 아래 디렉터리다.

```text
output/model_analysis/quantile_analysis/
```

이 디렉터리는 `seed 111 / 222 / 444`, validation checkpoint `005 / 010 / 015 / 020 / 025 / 030`, DRBC test basin 38개에 대한 hydrograph plot과 required-series CSV를 담는다. 모델 비교는 `Model 1` deterministic prediction과 `Model 2`의 `q50/q90/q95/q99`를 대상으로 한다.

분석 스크립트는 아래다.

```bash
uv run scripts/model/hydrograph/analyze_subset300_hydrograph_outputs.py
```

생성 위치는 아래다.

```text
output/model_analysis/quantile_analysis/analysis/
```

## 데이터 품질 확인

로컬 기준 산출물은 hydrograph plot 684개, required-series CSV 18개, quantile CSV 18개로 확인했다. 각 required-series CSV는 38개 basin의 2014-2016 hourly test period를 포함하며 998,678개 row를 가진다.

분석 전 sanity check는 세 가지다.

첫째, 모든 seed/epoch 조합에 38개 basin이 들어 있는지 확인한다. 둘째, `q50 <= q90 <= q95 <= q99` 순서가 깨지는 quantile crossing이 있는지 확인한다. 셋째, 기존 `test_results.p`에서 온 `model2_q50_result`와 재생성한 `q50`이 일관적인지 확인한다.

현재 결과에서 quantile ordering 위반은 0건이다. `model2_q50_result`와 재생성 `q50`의 median 차이는 사실상 0이다. 다만 일부 극단 시점에서 최대 차이가 존재하므로, 최종 해석은 재생성된 `q50/q90/q95/q99` 기준으로 통일한다.

## 분석 설계

분석은 두 종류의 비교를 나눈다.

| Comparison | 정의 | 역할 |
| --- | --- | --- |
| `primary` | validation으로 고른 대표 epoch 조합 | 논문 본문에서 우선 해석할 official comparison |
| `same_epoch` | Model 1과 Model 2를 같은 epoch 번호로 맞춘 조합 | checkpoint sensitivity와 epoch robustness 진단 |

현재 primary epoch는 `seed111: Model 1 epoch25 / Model 2 epoch5`, `seed222: epoch10 / epoch10`, `seed444: epoch15 / epoch10`이다.

유량 구간은 관측 유량 `obs` 기준으로 나눈다. `all`은 모든 시간이고, `basin_top10`, `basin_top5`, `basin_top1`, `basin_top0_1`은 각 basin 내부에서 관측 유량이 높은 시간대다. 내부 이름은 기존 호환성을 위해 유지하지만, 해석 표기는 threshold 기준으로 통일한다. 즉 `basin_top10 = Q90 exceedance`, `basin_top5 = Q95 exceedance`, `basin_top1 = Q99 exceedance`, `basin_top0_1 = Q99.9 exceedance`다. `observed_peak_hour`는 각 basin에서 관측 유량이 가장 큰 한 시점이다.

이 방식은 basin마다 유량 규모가 다르다는 점을 고려한다. pooled threshold 하나로 자르면 큰 basin이 분석을 지배할 수 있기 때문에, 연구 해석의 주 표는 basin-relative high-flow stratum을 우선 사용한다.

## 지표 계산

각 predictor를 `p`라고 하면 기본 계산은 아래와 같다.

```text
bias = p - obs
relative bias (%) = (p - obs) / obs * 100
coverage fraction = mean(obs <= p)
underestimation fraction = mean(p < obs)
under-relative deficit (%) = median(max(obs - p, 0) / obs * 100)
```

`Model 1`은 단일 deterministic prediction이고, `Model 2 q50`은 중앙예측선이다. `q90/q95/q99`는 중앙선 비교가 아니라 upper-tail decision output으로 해석한다.

`coverage fraction`은 양방향 예측구간 coverage가 아니라 `obs <= predictor`였던 one-sided hit-rate다. 전체 시계열에서 `q90/q95/q99`의 empirical coverage를 가늠하는 데 쓸 수 있지만, high-flow stratum에서는 formal calibration이 아니라 tail hit-rate에 가깝다. 이미 observed가 큰 시간만 조건부로 선택했기 때문이다.

상대 bias는 평균보다 중앙값을 우선 해석한다. 저유량에서는 분모인 `obs`가 작아 평균 상대 bias가 크게 튈 수 있기 때문이다. 또한 `median_under_rel_deficit_pct`가 0이라고 해서 오차가 사라졌다는 뜻은 아니다. 이 값은 과소추정 부족분만 본 중앙값이므로, 절반 이상이 관측값 이상으로 올라가면 0이 될 수 있다.

## 주요 결과

공식 primary epoch의 basin-specific Q99 exceedance 시간대에서 Model 1은 71.5%를 과소추정했고 median relative bias는 -47.7%였다. Model 2 `q50`은 과소추정률 85.8%, median relative bias -67.2%로 더 나빴다.

반면 upper quantile은 다른 패턴을 보인다. `q95`는 과소추정률을 61.9%, median relative bias를 -21.0%까지 줄였고, `q99`는 과소추정률을 44.9%까지 낮췄다. `q99`의 median relative bias는 +12.4%로 약간 상향된다.

Observed peak hour에서도 같은 결론이 나온다. Model 1은 peak hour의 74.6%를 과소추정했고 median relative bias는 -36.6%였다. Model 2 `q50`은 82.5% 과소추정으로 부족하다. `q95`는 과소추정률 62.3%, median relative bias -16.2%이고, `q99`는 과소추정률 50.0%, median relative bias +10.9%다.

Observed high-flow가 Model 2 quantile ladder의 어느 구간에 들어가는지도 별도 표로 확인한다. Primary basin-specific Q99 exceedance 전체 27,978개 row 중 `>q99`는 12,574개, 즉 44.9%였다. Peak 한 시점만 보면 114개 basin-seed peak 중 `>q99`는 57개, `q95-q99`는 14개, `q90-q95`는 7개, `q50-q90`는 16개, `<=q50`는 20개다. 즉 q99는 calibrated coverage claim에는 부족하지만, Q99 exceedance와 peak 양쪽 모두에서 q50-q99 ladder 안에 들어오는 사례도 함께 확인된다.

![Primary quantile-zone share by seed](../../../../output/model_analysis/quantile_analysis/analysis/charts/primary_q99_and_peak_quantile_zone_by_seed.png)

따라서 현재 결과는 `q50` 중앙선 개선이 아니라 upper-tail output의 가치를 보여준다. 논문 메시지는 “probabilistic head가 median prediction을 개선했다”가 아니라 “같은 LSTM backbone이라도 upper quantile head가 extreme flood underestimation을 줄일 수 있다”로 잡아야 한다.

## Quantile gap 해석

Primary epoch의 basin-specific Q99 exceedance에서 평균 median `q99-q50` gap은 20.9이고, 관측 유량 대비 약 74.1%다. Subagent의 pooled analysis에서도 `q99-q50` 평균 gap은 전체 5.63에서 Q99 exceedance 58.17로 약 10.3배 커졌다.

즉 Model 2는 high-flow에서 upper-tail band를 넓히는 방향을 학습했다. 이 점은 probabilistic head가 홍수 상황을 전혀 구분하지 못하는 것은 아니라는 근거다.

다만 one-sided empirical coverage는 nominal quantile level에 못 미친다. Pooled full-series coverage는 `q99`도 약 0.792였고, observed Q99 exceedance에서는 약 0.365였다. Basin-relative primary Q99 exceedance 기준에서도 `q99` coverage는 평균 0.551이다. 따라서 `q99`를 calibrated 99% predictive quantile로 쓰면 안 된다. 현재는 peak underestimation을 줄이는 upper-tail decision output으로 해석하는 것이 안전하다.

## Epoch와 seed 해석

Same-epoch sweep에서는 early epoch의 `q99-q50` gap과 Q99-exceedance hit-rate가 더 크고, 후반 epoch로 갈수록 band가 좁아지는 경향이 보인다. 이는 일반 validation metric으로 선택한 checkpoint가 flood-tail 관점의 최적 checkpoint와 다를 수 있음을 시사한다.

Seed별로는 `q99` 효과가 완전히 동일하지 않다. Primary Q99 exceedance에서 seed 111과 444는 `q99` median relative bias가 양수로 올라가고, seed 222는 여전히 약간 과소추정이다. 그래도 subagent 분석에서 `q99`는 same-epoch 18개 run 모두에서 Model 1 대비 Q99-exceedance underestimation rate를 줄였다. 따라서 upper quantile 효과는 seed 전반에서 일관적이라고 볼 수 있다.

Aggregate table은 전체 경향을 보여주지만 seed별 실패 사례를 가릴 수 있다. 따라서 논문 표에는 aggregate를 쓰더라도, 보조 분석에서는 `flow_strata_predictor_summary.csv`, `observed_peak_predictions.csv`, `observed_peak_quantile_zone.csv`로 seed별 예외와 basin별 peak failure case를 확인해야 한다.

## Event-regime 분석

Hourly Q99 exceedance 분석은 큰 유량 시간이 여러 시간 이어지는 event를 중복 집계할 수 있다. 이를 보완하기 위해 `scripts/model/event_regime/analyze_subset300_event_regime_errors.py`로 observed high-flow event candidate window 단위 분석을 추가한다.

이 분석은 DRBC test basin 38개, observed high-flow event candidate 570개, paired seed `111 / 222 / 444`를 사용한다. 본문 주 stratification은 `hydromet_only_7 + KMeans(k=3)` ML event-regime이고, `degree_day_v2` rule label은 sensitivity로 둔다.

현재 event-regime 결과에서도 방향은 비슷하다. `q50`은 세 ML regime 모두에서 Model 1보다 observed peak underestimation을 줄이지 못한다. 반면 `q90/q95/q99`는 대체로 paired under-deficit을 줄이고 threshold exceedance recall을 높이며, 특히 `q95/q99`에서 효과가 더 뚜렷하다.

다만 570개 event 중 대부분은 return-period proxy 기준 `high_flow_below_2yr_proxy`다. 따라서 이 결과를 공식 flood inventory나 고재현기간 flood event 전체에 대한 결과로 쓰면 안 된다. 또한 `q99`는 일부 regime에서 normalized event RMSE를 악화시킬 수 있다. 그래서 결론은 “upper quantile이 peak underestimation을 줄인다”이지, “q99가 event hydrograph 전체를 가장 정확히 맞춘다”가 아니다. `Weak / low-signal hydromet regime`도 snow-dominant class가 아니라 혼합/약신호 event regime으로만 해석한다.

## 논문용 해석 문장

현재 결과는 첫 번째 가설을 지지한다. Deterministic LSTM의 extreme flood peak underestimation은 backbone만의 문제가 아니라 output design 문제이기도 하며, probabilistic upper quantile head만으로도 underestimation을 줄일 수 있다.

단, calibration은 아직 약하다. 그러므로 `q99`를 “정확한 99% 예측구간”으로 표현하지 말고, “extreme-tail underestimation을 줄이는 upper-tail output”으로 표현하는 것이 맞다.

## 다음 분석

event-level analysis는 `event_regime_analysis/` 산출물로 1차 구현했지만, 이 event set은 streamflow Q99 candidate에서 출발하기 때문에 대부분 `high_flow_below_2yr_proxy`다. 따라서 hourly `Rainf`에서 ARI25/50/100급 극한호우 event를 직접 뽑아 train/validation exposure와 DRBC historical stress response를 분리해 확인한다.

이 보조 분석의 primary-checkpoint 결과는 `output/model_analysis/extreme_rain/primary/` 아래에 둔다. `exposure` 단계는 “모델이 극한호우 forcing을 배웠는가”를 답하고, `inference/analysis` 단계는 positive-response event에서 peak tracking을, low-response event에서 upper quantile false-positive를 평가한다. 같은 cohort에 대해 validation checkpoint `005 / 010 / 015 / 020 / 025 / 030` 전체를 돌린 sensitivity 결과는 `output/model_analysis/extreme_rain/all/` 아래에 따로 둔다. 이 all-epoch stress result는 primary checkpoint를 다시 고르는 용도가 아니라, upper-tail effect와 false-positive tradeoff가 checkpoint 선택에 얼마나 민감한지 확인하는 보조 진단이다. 이후 basin별 q99 exceedance case와 post-hoc calibration은 이 stress-test 결과를 본 뒤 좁혀서 검토한다.
