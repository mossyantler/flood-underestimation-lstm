# 01 Primary 전체 성능 분석

## 질문

이 분석은 validation으로 고른 primary checkpoint에서 Model 2 `q50`이 deterministic Model 1 대비 전체 hydrograph 성능을 얼마나 유지하는지 확인한다. 여기서 Model 2의 대표값은 `q50`이고, `q90/q95/q99`는 이 문서의 주 비교 대상이 아니다.

이 문서의 목적은 “어느 seed 하나가 좋아 보인다”를 고르는 것이 아니라, primary checkpoint로 고정된 Model 1과 Model 2를 seed-paired 구조로 읽는 방법을 정리하는 것이다. 즉 각 seed를 독립적인 training replicate로 보고, 같은 seed의 Model 1과 Model 2를 같은 DRBC test basin 38개 위에서 짝지어 비교한다.

## 상태

완료에 가깝다. `scripts/official/analyze_subset300_epoch_results.py`가 실행되어 validation/test metric, primary epoch summary, basin-level paired delta, chart가 생성되어 있다.

주요 산출물은 아래에 있다.

```text
output/model_analysis/overall_analysis/
```

## 사용한 기준

공식 paired seed는 `111 / 222 / 444`다. Model 2 seed `333`은 NaN loss로 중단되었고, 공정한 paired-seed 비교를 위해 Model 1 seed `333`도 final aggregate에서 제외한다. 따라서 이 분석의 aggregate CSV와 chart는 seed `333`을 포함하지 않도록 생성한다.

Primary epoch는 test 결과가 아니라 non-DRBC validation median NSE 기준으로 선택했다.

| model | seed | primary epoch |
| --- | ---: | ---: |
| Model 1 | 111 | 25 |
| Model 1 | 222 | 10 |
| Model 1 | 444 | 15 |
| Model 2 | 111 | 5 |
| Model 2 | 222 | 10 |
| Model 2 | 444 | 10 |

따라서 paired comparison은 아래처럼 읽는다.

| paired seed | 비교 |
| ---: | --- |
| 111 | Model 1 epoch 25 vs Model 2 epoch 5 |
| 222 | Model 1 epoch 10 vs Model 2 epoch 10 |
| 444 | Model 1 epoch 15 vs Model 2 epoch 10 |

Epoch 번호가 서로 달라도 문제는 아니다. 두 모델 모두 test를 보기 전에 validation 기준으로 primary checkpoint를 잠갔기 때문이다. 같은 epoch끼리의 비교는 primary 분석이 아니라 checkpoint sensitivity 분석에서 다룬다.

## 어떤 파일을 어떻게 읽을지

`primary_epoch_summary.csv`는 model/seed별 primary 성능표다. 각 row는 DRBC test basin 38개를 요약한다. 이 표는 “각 모델의 primary 성능이 어느 정도인가”를 설명할 때 쓴다.

`primary_epoch_basin_deltas.csv`는 가장 중요한 paired raw table이다. 각 row는 같은 seed와 같은 basin에서 `Model 2 q50 - Model 1` 또는 `Model 1 error - Model 2 q50 error`를 계산한 값이다. Model 비교 결론은 가능하면 이 basin-level paired delta에서 출발해야 한다.

`primary_epoch_delta_summary.csv`는 seed별 paired delta 요약이다. 논문 본문에서는 이 표를 우선 사용해 seed별 median delta, IQR, improvement fraction을 보여주는 것이 좋다.

`epoch_metric_summary.csv`와 `test_same_epoch_delta_summary.csv`는 checkpoint sensitivity 맥락에서 보조적으로 읽는다. Primary 결론을 바꾸거나 primary epoch를 다시 고르는 용도로 쓰지 않는다.

## 차트로 확인하는 방법

아래 chart들은 문서에서 직접 참조할 수 있다. 다만 모든 chart의 해석 지위가 같은 것은 아니다. `primary_epoch_basin_deltas.png`가 primary paired comparison을 가장 직접적으로 보여주고, 나머지는 training/checkpoint/sensitivity 맥락을 설명하는 보조 chart다.

![Training loss by epoch](../../../../output/model_analysis/overall_analysis/charts/training_loss_by_epoch.png)

Figure 01a. `training_loss_by_epoch.png`는 seed와 model별 training loss 흐름을 확인하는 QA chart다. 이 그림은 모델이 학습 중 비정상적으로 튀었는지, 특정 seed가 다른 seed와 완전히 다른 loss trajectory를 보이는지 확인하는 데 쓴다. 논문 성능 주장의 직접 근거는 아니며, primary checkpoint 성능은 validation/test metric과 paired delta로 판단한다.

![Validation epoch median metrics](../../../../output/model_analysis/overall_analysis/charts/validation_epoch_median_metrics.png)

Figure 01b. `validation_epoch_median_metrics.png`는 primary epoch가 test 결과가 아니라 validation metric을 기준으로 선택되었다는 점을 설명할 때 사용한다. 여기서 핵심은 validation median NSE를 기준으로 checkpoint를 잠갔다는 절차적 정당성이다. Validation chart를 보고 test 성능이 좋은 epoch를 새로 고르는 방식으로 해석하면 안 된다.

![Test epoch median metrics](../../../../output/model_analysis/overall_analysis/charts/test_epoch_median_metrics.png)

Figure 01c. `test_epoch_median_metrics.png`는 test set에서 epoch별 median metric이 어떻게 움직이는지 보여주는 descriptive chart다. Primary epoch가 test metric 곡선의 최고점인지 확인하는 용도가 아니라, primary 결과가 test epoch sweep 안에서 극단적으로 특이한지 확인하는 보조 진단으로 읽는다. 이 chart에서 Model 2 `q50`의 NSE가 어느 정도 유지되어도, FHV나 Peak-MAPE가 같이 좋아졌다는 뜻은 아니다.

![Test same-epoch delta summary](../../../../output/model_analysis/overall_analysis/charts/test_same_epoch_delta_summary.png)

Figure 01d. `test_same_epoch_delta_summary.png`는 같은 epoch 번호에서 Model 2 `q50`과 Model 1을 비교한 sensitivity chart다. 공식 primary comparison은 모델별 validation-best epoch를 쓰기 때문에 이 그림과 완전히 같은 비교 구조가 아니다. 따라서 이 chart는 “결론이 특정 primary checkpoint에만 의존하는가”를 보는 보조 근거로 사용하고, primary conclusion을 대체하지 않는다.

![Primary epoch basin deltas](../../../../output/model_analysis/overall_analysis/charts/primary_epoch_basin_deltas.png)

Figure 01e. `primary_epoch_basin_deltas.png`가 이 문서에서 가장 중요한 comparison chart다. 각 metric의 basin-level paired delta 분포를 보여주므로, Model 2 `q50`이 같은 seed와 같은 basin에서 Model 1보다 어느 방향으로 움직였는지 확인할 수 있다. 다만 이 그림의 점들은 38개 DRBC basin이 3개 seed에 반복된 구조이므로, 114개 완전 독립 표본처럼 해석하지 않는다. 최종 문장은 seed별 `primary_epoch_delta_summary.csv`와 함께 읽어야 한다.

## 지표별 해석 방법

`NSE`는 전체 hydrograph의 오차를 관측 평균 대비 얼마나 줄였는지 보는 지표다. 1에 가까울수록 좋고, 0은 관측 평균을 예측하는 것과 비슷하며, 음수는 관측 평균보다 못하다는 뜻이다. DRBC test처럼 basin 간 난이도 차이와 outlier가 큰 경우에는 mean NSE보다 median NSE와 negative NSE basin 수를 우선 본다.

`KGE`는 correlation, bias, variability를 함께 보는 효율 지표다. 1에 가까울수록 좋고, 음수도 가능하다. NSE가 좋아도 KGE가 나쁘면 hydrograph shape, 평균 bias, 변동폭 중 일부가 맞지 않는다는 신호일 수 있다. 현재 산출물에는 KGE 구성요소가 따로 들어 있지 않으므로, KGE는 전체 균형성 guardrail로 해석한다.

`FHV`는 high-flow volume bias다. 0에 가까울수록 좋고, 음수는 high-flow volume을 과소추정한다는 뜻이며, 양수는 과대추정한다는 뜻이다. 따라서 FHV는 “값이 클수록 좋다”가 아니다. 반드시 signed `median_FHV`와 `abs_FHV`를 같이 읽어야 한다. `abs_FHV_reduction`이 양수면 Model 2 `q50`이 Model 1보다 0에 가까워졌다는 뜻이지만, signed FHV가 더 음수로 이동했다면 high-flow underestimation은 여전히 나빠졌거나 남아 있을 수 있다.

`Peak_Timing`은 관측 peak와 예측 peak 사이의 시간 차이를 본다. 현재 summary에서는 작을수록 좋게 해석한다. Delta table의 `Peak_Timing_reduction`은 `Model 1 error - Model 2 q50 error`이므로 양수면 Model 2 `q50`의 peak timing error가 더 작다는 뜻이다. 다만 이 지표는 peak magnitude가 틀려도 timing만 따로 좋아질 수 있으므로, Peak-MAPE나 high-flow 분석과 함께 읽어야 한다.

`Peak-MAPE`는 peak magnitude 오차의 절대 비율이다. 작을수록 좋지만, underprediction과 overprediction 방향을 알려주지 않는다. 따라서 Peak-MAPE가 줄었다고 해서 peak underestimation이 줄었다고 바로 말하면 안 된다. Underestimation 주장은 다음 분석의 high-flow stratum, observed peak hour, event-level under-deficit에서 확인해야 한다.

`negative_nse_basins`는 NSE가 0보다 작은 basin 수다. 모델이 일부 basin에서 완전히 실패하는지를 보는 실패 부담 지표로 유용하다. 다만 이것은 paired delta가 아니라 model/seed별 count이므로, Model 1과 Model 2를 비교할 때는 seed별로 나란히 제시하는 보조 지표로 쓰는 것이 좋다.

`mean`, `std`, `q25`, `q75`는 분포의 모양을 설명하는 보조값이다. 이 실험에서는 일부 basin의 NSE/KGE outlier가 매우 크기 때문에 mean과 std는 outlier 진단에는 유용하지만 대표 성능으로는 median과 IQR을 우선한다.

## Seed 3개를 통합해 해석하는 방법

Primary 모델은 Model 1과 Model 2 각각 seed `111 / 222 / 444`의 3개 checkpoint로 구성된다. 이것을 단순히 6개 model row의 평균으로 합치면 안 된다. 올바른 해석 단위는 “같은 seed, 같은 basin에서의 paired delta”다.

분석 순서는 아래처럼 둔다.

1. 먼저 `primary_epoch_summary.csv`에서 model/seed별 median metric을 확인한다. 이 단계는 각 모델이 primary checkpoint에서 무너지지 않았는지 보는 descriptive check다.
2. 다음으로 `primary_epoch_basin_deltas.csv`에서 같은 seed와 basin의 paired delta를 만든다. 이 단계가 Model 1 vs Model 2 비교의 핵심이다.
3. 그다음 `primary_epoch_delta_summary.csv`에서 seed별 median delta와 improvement fraction을 확인한다. 세 seed가 같은 방향인지, 한 seed만 결과를 끌고 가는지 본다.
4. 마지막으로 세 seed의 median delta를 다시 요약한다. 본문에는 seed별 값을 모두 보여주고, 필요하면 “seed-level median of medians”와 range를 함께 쓴다.

판정 강도는 다음 기준으로 두는 것이 좋다.

| 판정 | 기준 |
| --- | --- |
| 강함 | 3개 seed 모두 같은 방향이고, seed별 improvement fraction도 대체로 0.5를 넘으며, median delta가 해석 가능한 크기다. |
| 중간 | 2개 seed는 같은 방향이고 1개 seed는 약하거나 반대지만, 전체 방향이 논리적으로 일관된다. |
| 약함/혼합 | seed별 방향이 엇갈리거나, median delta가 0 근처이고 improvement fraction도 0.5 근처다. |

Pooled 114개 값, 즉 38개 basin x 3개 seed를 한꺼번에 그린 box plot은 시각적으로 유용하다. 하지만 같은 basin이 seed별로 반복되므로 완전히 독립적인 114개 표본처럼 해석하면 안 된다. 본문 결론은 seed별 paired summary를 우선하고, pooled distribution은 보조 그림으로 쓰는 편이 안전하다.

## 현재 primary 결과 해석

현재 primary test row는 모든 공식 seed에서 DRBC test basin 38개를 포함한다.

| model | seed | median NSE | median KGE | median FHV | median Peak Timing | median Peak-MAPE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Model 1 | 111 | 0.264 | 0.323 | -10.1 | 3.47 | 64.6 |
| Model 1 | 222 | -0.045 | 0.288 | 9.5 | 3.71 | 65.9 |
| Model 1 | 444 | 0.075 | 0.030 | -16.6 | 3.33 | 75.1 |
| Model 2 q50 | 111 | 0.292 | 0.119 | -51.7 | 3.15 | 74.7 |
| Model 2 q50 | 222 | 0.229 | 0.112 | -49.9 | 3.36 | 71.6 |
| Model 2 q50 | 444 | 0.264 | 0.394 | -27.5 | 3.13 | 70.3 |

NSE 기준으로는 Model 2 `q50`이 무너졌다고 보기 어렵다. Seed별 median delta NSE는 `0.109`, `0.201`, `0.246`으로 모두 양수이고, basin별 improvement fraction도 약 `0.61-0.68`이다. 따라서 primary overall analysis에서는 “Model 2 `q50`은 central NSE guardrail을 대체로 유지하거나 개선했다”고 쓸 수 있다.

KGE는 더 조심스럽다. Seed `111`에서는 median delta KGE가 `-0.072`로 음수이고, seed `222`와 `444`에서는 각각 `0.042`, `0.268`로 양수다. 즉 KGE는 2/3 seed에서 개선이지만 완전히 일관된 결과는 아니다. 논문에서는 “KGE improvement is mixed across seeds” 또는 “KGE는 seed별 변동이 있어 강한 개선 주장에는 쓰지 않는다” 정도가 안전하다.

FHV는 Model 2 `q50`의 약점이다. Model 2 primary의 median FHV는 seed별로 `-51.7`, `-49.9`, `-27.5`로 모두 음수 쪽이 강하다. Paired signed delta FHV도 세 seed 모두 음수이므로, Model 2 `q50`은 high-flow volume을 더 낮게 잡는 방향으로 이동했다. `abs_FHV_reduction`은 seed별로 `-16.1`, `0.3`, `16.6`이라 혼합적이다. 따라서 `q50`을 flood peak를 더 잘 맞추는 deterministic forecast라고 주장하면 안 된다.

Peak timing은 Model 2 `q50`이 약간 유리한 쪽이다. `Peak_Timing_reduction`의 seed별 median은 `0.877`, `0.259`, `0.075`이고 improvement fraction도 모두 0.5를 넘는다. 다만 magnitude가 크지 않고 peak 크기 오류와 분리된 지표이므로, headline이 아니라 guardrail 또는 보조 결과로 둔다.

Peak-MAPE는 혼합적이다. Seed별 median reduction은 `-2.99`, `0.03`, `7.99`로 한 seed에서는 나빠지고, 한 seed는 거의 차이가 없고, 한 seed는 좋아진다. 따라서 primary overall 문서에서는 “Model 2 `q50`이 peak magnitude absolute error를 일관되게 줄였다고 보기 어렵다”고 해석한다.

## 논문에서의 위치

이 분석은 Results 첫 번째 표로 들어간다. 목적은 Model 2의 probabilistic head가 중앙예측선 성능을 완전히 망가뜨리지 않았는지 확인하는 guardrail이다. 논문 headline은 여기서 만들지 않는다. Headline은 다음 분석에서 `q90/q95/q99`가 high-flow와 event peak underestimation을 줄였는지에 둔다.

본문 문장은 아래 정도가 안전하다.

```text
Across the three paired primary seeds, Model 2 q50 preserved or improved median NSE relative to the deterministic baseline, but KGE gains were mixed and q50 shifted high-flow volume bias toward stronger underestimation. Therefore, the primary overall metrics support q50 as a central-skill guardrail, not as evidence that the probabilistic model improves deterministic flood-peak prediction. The flood-specific claim must be evaluated using upper quantiles in the high-flow and event-level analyses.
```

한국어로는 아래처럼 쓰면 된다.

```text
세 개의 paired primary seed에서 Model 2 q50은 median NSE 기준 중심 예측 성능을 유지하거나 개선했다. 그러나 KGE 개선은 seed별로 혼합적이고, FHV는 q50이 high-flow volume을 더 낮게 잡는 방향을 보였다. 따라서 primary overall 결과는 q50이 central-skill guardrail을 통과했다는 근거이지, probabilistic model이 deterministic flood-peak 예측을 개선했다는 직접 근거는 아니다. Flood-specific 주장은 다음 high-flow 및 event-level 분석에서 q90/q95/q99를 중심으로 평가해야 한다.
```

## 남은 작업

`primary_epoch_summary.csv`와 `primary_epoch_delta_summary.csv`를 논문용 compact table로 다시 정리해야 한다. 표에는 metric별 improvement direction을 명시해야 한다. 특히 `FHV`는 signed value와 `abs_FHV_reduction`을 함께 넣고, `Peak-MAPE`와 `Peak-Timing`은 reduction 값이 양수일 때 개선이라는 점을 표 주석에 써야 한다.

추가로, pooled basin-seed box plot을 본문 그림으로 쓸 경우 caption에 “38 DRBC basins repeated across three paired seeds”라고 명시해야 한다. 이렇게 해야 114개 점을 완전히 독립 표본처럼 보이게 만드는 오해를 줄일 수 있다.
