# Results Draft: Expanded DRBC Observed Test

> 사용 목적: 이 문서는 expanded DRBC observed test 결과를 논문 Results section으로 옮기기 위한 한국어 초안이다. 최종 manuscript에서는 문장 길이, figure/table 번호, 영어 표현을 별도 조정한다.

## 1. Expanded DRBC test setting

본 분석은 기존 subset300 학습 checkpoint를 그대로 사용하여, DRBC 내부 관측 유량 support가 더 넓은 `drbc_expanded_observed_test` split에서 Model 1 deterministic LSTM과 Model 2 probabilistic quantile LSTM을 비교하였다. 평가 대상은 quality gate와 2014--2016 target coverage 조건을 통과한 DRBC 85개 basin이며, paired seed `111 / 222 / 444`를 사용하였다. 현재 RQ-0--5 Results 구성에서는 이 expanded DRBC observed test를 canonical analysis baseline으로 사용하고, 레거시 DRBC-38 holdout 기반 분석은 archive 비교 맥락으로만 둔다.

결과 집계는 모든 RQ에서 동일한 원칙을 따랐다. 먼저 basin과 seed 단위로 metric을 계산하고, seed median을 basin 안에서 취한 뒤, cross-basin median과 IQR을 보고하였다. Model 1과 Model 2 `q50`의 paired delta는 seed level에서 먼저 계산하였다. High-flow event는 basin별 train-period 관측 Q99 threshold를 기준으로 추출하였고, confirmed flood 분석은 NOAA/NWS catalog가 expanded basin과 겹치는 test-period event subset에서 별도로 수행하였다.

## 2. Model 2 q50 preserves central performance

Model 2의 central output인 `q50`은 Model 1 deterministic output 대비 중앙예측 성능을 유지하거나 개선하였다. Basin-median NSE는 Model 1에서 -0.031, Model 2 `q50`에서 0.225였고, paired median delta는 +0.149였다. RMSE와 MAE도 각각 -0.273, -0.197만큼 감소하였다. KGE 역시 +0.041 증가하였다.

다만 mean bias는 Model 2 `q50`에서 더 negative하게 나타났다. Model 1의 basin-median bias는 -0.459였고, `q50`은 -0.948이었다. 이는 `q50`이 conditional median을 추정하는 output이고, skewed streamflow distribution에서 mean-tracking deterministic output과 median-tracking quantile output이 다르게 동작할 수 있음을 보여준다. 따라서 RQ-1의 결론은 `q50`이 central skill을 무너뜨리지 않는다는 것이며, high-flow peak를 잡기 위해서는 `q90 / q95 / q99` upper quantile output을 함께 해석해야 한다.

| Metric | Model 1 median | Model 2 q50 median | Paired delta |
| --- | ---: | ---: | ---: |
| NSE | -0.031 | 0.225 | +0.149 |
| KGE | 0.082 | 0.158 | +0.041 |
| Bias | -0.459 | -0.948 | -0.437 |
| MAE | 2.584 | 2.509 | -0.197 |
| RMSE | 4.850 | 4.393 | -0.273 |

## 3. Upper quantiles reduce peak underestimation in Q99 events

Observed Q99 exceedance event를 기준으로 보면, Model 2의 upper quantile output은 peak underestimation을 tau가 커질수록 단조롭게 줄였다. Q99 event set은 82개 active basin에서 926개 event로 구성되었다. Event peak under-deficit alpha는 Model 1에서 0.588, `q50`에서 0.657이었으나, `q90`, `q95`, `q99`로 올라갈수록 각각 0.376, 0.272, 0.018로 감소하였다. 즉 `q99`에서는 cross-basin median 기준으로 event peak under-deficit이 거의 0에 가까웠다.

Window capture beta도 같은 방향을 보였다. Q99 event의 ±6h window 안에서 `q99`의 basin-median capture ratio는 1.306으로, observed peak를 넘는 보수적 output을 제공하였다. Threshold recall delta는 `q50`의 0.069에서 `q99`의 0.583으로 증가하였다. 이는 `q99`가 Q99 이상 관측 시각의 약 58%를 threshold 이상으로 포착한다는 뜻이다. 따라서 expanded DRBC test에서도 Model 2의 upper quantile branch는 deterministic baseline과 `q50`이 놓치는 peak magnitude를 의미 있게 보완하였다.

| Output | Alpha peak under-deficit | Beta window capture | Delta Q99 recall |
| --- | ---: | ---: | ---: |
| Model 1 | 0.588 | 0.519 | 0.143 |
| q50 | 0.657 | 0.444 | 0.069 |
| q90 | 0.376 | 0.733 | 0.280 |
| q95 | 0.272 | 0.920 | 0.379 |
| q99 | 0.018 | 1.306 | 0.583 |

이 결과를 q50~q99 uncertainty band 관점에서 재해석하면 다음과 같다. Event peak 시각에서 관측 유량이 q50~q99 band 안에 들어오는 경우(q50_to_q90 + q90_to_q95 + q95_to_q99 class 합산)는 cross-basin median 기준 약 16%였고, q99도 초과하는 경우(above_q99)는 약 47%였다. 즉 Q99 event peak의 절반에 가까운 경우 q99이 여전히 obs를 추종하지 못한다. 이는 alpha-median ≈ 0.018이 "q99이 peak를 정확히 맞춘다"는 의미가 아니라, cross-basin median 관점에서 under-deficit이 거의 0에 수렴했다는 뜻임을 명확히 한다 — basin별로는 여전히 분포 편차가 크다(IQR 0.000~0.283).

Gap trajectory 관점에서는 under-gap(절대값)이 q50 23.7 → q90 13.0 → q95 8.7 → q99 0.87 cms로 단조 감소하였다. Over-gap은 q50~q95에서 0이다가 q99에서 처음으로 3.58 cms가 등장한다. 즉 over-prediction cost는 q99에서 비로소 시작되며, under-gap의 27× 감소와 over-gap의 새 등장이 q99에서 동시에 발생하는 tradeoff 구조다. `q99`를 "더 나은 단일 예측"이 아니라 q50~q99 band의 upper envelope로 해석해야 하는 근거가 여기에 있다.

## 4. NOAA confirmed flood subset supports the same direction

NOAA/NWS confirmed flood catalog와 expanded DRBC basin의 overlap은 전체 catalog 49개 basin 중 46개 basin이었고, 2014--2016 test-period에서 실제 event-bearing overlap은 21개 basin, 65개 event였다. 이 subset은 Q99 event set보다 작지만, event source가 독립적인 확인 자료라는 점에서 중요한 sanity check다.

NOAA scope에서도 upper quantile의 방향성은 Q99 scope와 일치하였다. `q50`의 alpha는 0.788이었고, `q99`에서는 0.172로 감소하였다. Beta window capture는 `q50` 0.282에서 `q99` 0.977로 증가하였다. 즉 confirmed flood event에서도 `q99`는 median output보다 훨씬 보수적으로 peak window를 포착하였다. 다만 NOAA subset의 basin과 event 수가 제한적이므로, 본문에서는 Q99 event 결과를 headline으로 두고 NOAA 결과는 independent event-source confirmation으로 해석하는 것이 적절하다.

Band 관점에서 보면 NOAA confirmed flood event는 더 극단적인 패턴을 보였다. Event peak 시각에서 관측 유량이 q99를 초과하는 비율(above_q99)은 cross-basin median 기준 1.0이었다 — NOAA scope 21개 basin 전부에서 확인 홍수 peak가 q99를 초과하였다. 이는 alpha-NOAA = 0.172와 일치하며, NOAA confirmed flood event는 Q99 exceedance threshold를 사용한 Q99 scope보다 더 극단적이어서 q99 band 조차 충분하지 않은 사례임을 보여준다. Gap trajectory에서도 NOAA scope under_gap은 q99에서 21.2 cms로 여전히 잔류하였고, over_gap은 모든 τ에서 0이었다 — obs가 q99를 항상 초과하므로 overshoot이 발생할 여지가 없었다.

Q99와 NOAA event 정의의 관계도 확인하였다. NOAA overlap 21개 basin에서 65개 NOAA event는 모두 Q99 event window 안에 포함되었다. 반대로 Q99 event 389개 중 NOAA로 보정된 것은 65개, 즉 16.7%였다. 이는 Q99 event definition이 NOAA confirmed flood보다 더 inclusive하며, 두 event source를 같은 모집단으로 취급하면 안 된다는 점을 보여준다.

## 5. Peak protection comes with false-alarm and over-prediction cost

Upper quantile output의 이득은 cost와 함께 나타났다. Q99 threshold 기준 FAR은 `q50`에서 0.0007, `q90`에서 0.0042, `q95`에서 0.0063, `q99`에서 0.0164로 증가하였다. Over-prediction magnitude 역시 `q50` 1.47에서 `q99` 3.44로 증가하였다.

따라서 `q99`는 high-flow recall을 크게 높이는 대신 false-positive와 over-prediction을 증가시키는 가장 보수적인 decision output으로 해석해야 한다. `q50` 대비 `q99`의 Q99 recall은 약 8배 증가했지만, FAR은 약 23배 증가하였다. 이 비대칭은 Model 2를 "항상 더 좋은 단일 예측"으로 해석하기보다, 사용자가 flood alert 목적에 따라 tau를 선택할 수 있는 multi-level decision output으로 해석해야 함을 의미한다.

| Output | Q99 recall | FAR | Over-prediction magnitude |
| --- | ---: | ---: | ---: |
| q50 | 0.069 | 0.0007 | 1.47 |
| q90 | 0.280 | 0.0042 | 2.19 |
| q95 | 0.379 | 0.0063 | 2.29 |
| q99 | 0.583 | 0.0164 | 3.44 |

Gap trajectory 관점에서 이 tradeoff를 구체화하면 다음과 같다. Q99 event peak에서의 절대 under-gap은 q50 23.7 → q90 13.0 → q95 8.7 → q99 0.87 cms로 단조 감소한다. Over-gap은 q50~q95 구간에서 0이며 q99에서 처음 3.58 cms가 등장한다. 즉 τ를 q95에서 q99로 올리는 구간에서 under-gap 감소(8.7 → 0.87)와 over-gap 등장(0 → 3.58)이 동시에 일어난다. 이 비대칭 tradeoff는 q99를 "가장 정확한 단일 출력"으로 보는 해석을 지지하지 않는다. q99는 under-gap을 최소화하는 upper envelope로서 유용하지만, 그 대가로 비로소 나타나는 over-prediction cost를 항상 함께 보고해야 한다.

## 6. Benefits and costs vary across basin and event cohorts

Model 1 NSE 기준 basin tier로 나누면, upper quantile의 효과는 basin cohort에 따라 다르게 나타났다. Bottom tier에서는 `q99` alpha가 0.00, recall이 0.95로, Model 1이 약한 basin에서 peak underestimation 완화 효과가 가장 컸다. 그러나 같은 tier의 FAR도 0.060으로 가장 높았다. Mid tier도 `q99` alpha 0.00, recall 0.62로 강한 improvement를 보였고 FAR은 0.0115였다. Top tier에서는 `q99` alpha가 0.22로 일부 underestimation이 남았고, recall은 0.39였다.

이 결과는 Model 2 upper quantile output이 특히 deterministic baseline이 약한 basin에서 큰 peak-protection benefit을 줄 수 있음을 시사한다. 동시에 poor-fit basin에서는 false alarm cost도 더 커질 수 있으므로, basin별 threshold 또는 tau 선택 전략이 필요할 수 있다. Top tier의 over-prediction magnitude가 큰 것은 basin scale과 high-flow magnitude 자체가 반영된 결과이므로, 단순히 "top tier가 더 나쁘다"는 의미로 해석하면 안 된다.

NOAA event-type 기준으로는 Flash Flood가 가장 어려운 event type이었다. Flash Flood event에서는 `q99`에서도 alpha가 0.42로 남았고 beta도 0.88에 머물렀다. 반면 Flood event에서는 `q99` alpha가 0.06, beta가 1.09로 개선되었다. NoNOAA category는 `q99` alpha 0.00, beta 1.20으로 Flood와 유사한 동작을 보였지만, NOAA Storm Events corroboration이 없는 NWS-only event이므로 본문 headline보다는 supplement 또는 caveat 문맥에서 다루는 편이 안전하다.

## 7. Quantile outputs are useful decision levels but not calibrated 99% predictive quantiles

Calibration and sharpness diagnostics는 Model 2 output의 한계를 명확히 보여준다. All-hour one-sided empirical coverage는 모든 tau에서 nominal보다 낮았다. 특히 `q99`의 empirical coverage는 0.787로, nominal 0.99보다 크게 낮았다. 따라서 `q99`를 "calibrated 99% predictive quantile" 또는 100-year flood 수준으로 표현해서는 안 된다.

그럼에도 pinball/AQS 관점에서는 upper quantile이 high-flow decision output으로 유용한 신호를 제공하였다. All-hour mean pinball은 `q50` 4.656에서 `q99` 1.638로 감소하였고, Q99-exceedance tail hit-rate는 `q99`에서 0.563이었다. 이는 RQ-2의 Q99 recall 0.583과 같은 방향의 결과다. Peak event capture도 `q99`에서 peak hour 0.522, ±6h window 0.643으로 가장 높았다.

다만 climatology baseline 대비 pinball skill score는 `q99`에서 -0.271로 음수였다. 즉 가장 극단적인 quantile output은 high-flow peak protection에는 도움이 되지만, climatology-aware sharpness 관점에서는 손해가 있다. 본 연구의 주장은 Model 2가 완전히 calibrated 된 probabilistic forecast를 제공한다는 것이 아니라, upper-tail decision output이 deterministic LSTM의 peak underestimation을 줄이는 실용적 보완 신호를 제공한다는 데에 있다.

## 8. Prospective band-shape prediction: exploratory analysis

q50~q99 band의 정적 형태(static geometry)와 rising limb 가파름을 obs 없이 계산 가능한 사전(prospective) 지표로 활용할 수 있는지 탐색하였다.

**Band-shape 지표** (obs-free): rel_width = `(q99 − q50) / q50`(전체 band 상대 폭)과 g3_ratio = `(q99 − q95) / (q99 − q50)`(극단 꼬리 비중)를 각 event peak에서 계산하고, obs_class_ordinal(below_q50=0 ~ above_q99=4)과의 Spearman r을 Q99/NOAA scope별로 계산하였다(per-event pooled, Q99 n=2770, NOAA n=194). g3_ratio는 Q99 scope r = +0.137, NOAA scope r = +0.173으로 유의(p < 0.05)하였으나 r < 0.2 수준이었다. rel_width는 Q99 scope에서 r = −0.015(n.s.)였다.

**Rising limb steepness**: peak 전 유량 급상승 시점을 obs 시계열에서 복수의 방법(final continuous rise onset, local minimum 기반)으로 탐지하고 rise_h를 산출하였으나, obs_class_ordinal과의 Spearman r은 모두 |r| < 0.05 수준으로 유의한 상관이 없었다.

두 탐색 모두 obs gap class를 사전 예측하는 데 충분한 신호를 제공하지 못하였다. q50~q99 band의 정적 형태와 rising limb 가파름만으로는 obs가 어느 gap에 위치할지를 사전에 구별하기 어렵다. 이는 obs gap class가 band shape이 아니라 사건별 강우 강도·선행 토양 수분 등 관측이 필요한 요소에 주로 결정된다는 해석과 일치하며, prospective 활용 가능성은 현 분석 범위에서 확인되지 않았다.

## 9. Results summary

Expanded DRBC observed test는 Model 2 quantile head가 단순한 probabilistic decoration이 아니라, deterministic LSTM의 flood peak underestimation 문제를 완화하는 별도 output design임을 보여준다. `q50`은 central performance를 유지하면서, `q90/q95/q99`는 Q99 event와 NOAA confirmed flood event에서 peak under-deficit을 단조롭게 줄였다. 특히 `q99`는 Q99 event에서 alpha를 0.018까지 낮추고 threshold recall을 0.583까지 높였으며, under-gap은 q50의 23.7 cms에서 q99의 0.87 cms로 감소하였다.

그러나 이 개선은 cost-free가 아니며, `q99`를 단일 "정답 예측"으로 해석해서는 안 된다. Q99 event peak의 약 47%는 q99도 초과하고(above_q99 class), NOAA confirmed flood peak의 경우 전부 q99를 초과한다. Over-gap은 q99에서 처음 등장(3.58 cms)하며, FAR은 q50 대비 23배 증가한다. `q99`의 all-hour empirical coverage(0.787)도 nominal 0.99에 미치지 못한다.

따라서 본 결과는 `q50~q99`를 uncertainty band로 해석하는 framework 위에서 제시된다. `q99`는 upper-tail protection을 위한 band의 상단 envelope이며, "q99가 좋다"는 주장 대신 "q50에서 q99까지 band가 올라갈수록 under-gap이 줄고 over-gap과 FAR cost가 증가한다"는 tradeoff 구조로 기술한다. Model 2는 "더 정확한 단일 hydrograph"가 아니라, central estimate `q50`와 upper-tail decision levels `q90/q95/q99`를 함께 제공하는 multi-level flood protection framework이다.

## Figure / table candidates

- Main Figure 1: RQ-2 alpha/beta/delta by tau (`rq2_alpha_by_tau.png`, `rq2_beta_by_tau.png`, `rq2_delta_recall_by_tau.png`)
- Main Figure 2: recall-cost tradeoff (`rq3_cost_recall_tradeoff.png`)
- Main Figure 3 or Supplement: UB gap trajectory (`ub_gap_trajectory.png`) — under-gap/over-gap by τ
- Main Table 1: central performance + peak metrics compact table
- Main Table 2 or Supplement: basin tier heterogeneity
- Supplement: UB location class bar (`ub_location_class_bar.png`), NOAA event-type stratification, Q99-NOAA cross-tab, RQ-5 calibration/sharpness diagnostics

## Evidence notes

- Primary analysis map: `docs/experiment/analysis/model/00_research_question_analysis_map.md`
- RQ-specific docs: `docs/experiment/analysis/model/01_q50_central.md` through `05_calibration_sharpness.md`
- Regenerated tables: `output/model_analysis/expanded_drbc_test/tables/`
- Probabilistic diagnostics: `output/model_analysis/expanded_drbc_test/probabilistic_diagnostics/`
- Rebuild command for RQ-1~4: `uv run scripts/model/expanded_drbc/run_all.py`
