# 04 Extreme Flood Proxy 성능 분석

## 질문

이 분석은 observed high-flow event 중 flood-relevance proxy tier가 높은 event에서 Model 2 upper quantile이 Model 1보다 peak underestimation을 줄이는지 확인한다. 단, 여기서 `flood_like_ge_*yr_proxy`는 CAMELSH hourly annual-maxima proxy에 기반한 참고 분류이지 official flood inventory가 아니다.

## 상태

부분 완료다. Event-regime 분석 산출물 안에 flood relevance tier별 aggregate와 summary가 생성되어 있다. 그러나 high-return-period proxy event 수가 매우 작아서 본문 headline보다는 sensitivity 또는 supplement로 쓰는 것이 안전하다.

주요 산출물은 아래에 있다.

```text
output/model_analysis/quantile_analysis/event_regime_analysis/flood_relevance_tier_predictor_aggregate.csv
output/model_analysis/quantile_analysis/event_regime_analysis/ml_event_regime_by_flood_tier_predictor_aggregate.csv
```

## Event 수

분석된 event는 총 570개지만, flood relevance tier 분포는 불균형하다.

| tier | unique events |
| --- | ---: |
| `high_flow_below_2yr_proxy` | 523 |
| `flood_like_ge_2yr_proxy` | 30 |
| `flood_like_ge_5yr_proxy` | 6 |
| `flood_like_ge_10yr_proxy` | 9 |
| `flood_like_ge_25yr_proxy` | 1 |
| `flood_like_ge_50yr_proxy` | 1 |

따라서 `ge25yr`와 `ge50yr` 결과는 사실상 사례 분석에 가깝다. 통계적 generalization을 주장하면 안 된다.

## 현재 해석

`flood_like_ge_2yr_proxy` 30개 event에서는 Model 1의 observed-peak underestimation fraction이 0.700이고 median observed-peak relative error는 `-34.9%`다. Model 2 `q50`은 underestimation fraction 0.867, median error `-63.5%`로 더 낮게 잡는다. 반면 `q95`는 underestimation fraction 0.667, median error `-22.9%`로 완화하고, `q99`는 underestimation fraction 0.489, median error `+2.35%`까지 올라간다.

`flood_like_ge_10yr_proxy` 9개 event에서도 비슷한 방향이다. Model 1 median observed-peak relative error는 `-35.0%`, Model 2 `q50`은 `-55.3%`, `q95`는 `-5.15%`, `q99`는 `+28.6%`다. 이 결과는 upper quantile이 큰 flood-like event에서도 underestimation을 줄인다는 신호를 준다.

그러나 event 수가 작기 때문에 결과의 신뢰도는 제한적이다. 특히 `ge25yr`와 `ge50yr`는 각 1개 event뿐이므로 표에 넣더라도 case-study 또는 supplement로 내려야 한다.

## 논문에서의 위치

이 분석은 Results의 main headline보다는 extreme-event sensitivity로 두는 것이 좋다. 본문에서는 `ge2yr`와 `ge10yr` 정도만 조심스럽게 언급하고, 나머지 high-return tier는 supplement table로 분리하는 편이 안전하다.

## 남은 작업

Extreme flood proxy 결과를 본문에 넣으려면 tier별 event 수를 표에 반드시 같이 넣어야 한다. 또한 `ge25yr/ge50yr`는 pooled metric처럼 보이지 않도록 “case-level evidence”로 표시해야 한다.
