# 05 Extreme-Rain Stress Test 분석

## 질문

이 분석은 hourly `Rainf` rolling sum으로 직접 추출한 historical extreme-rain event에서 Model 1과 Model 2가 DRBC streamflow stress response를 얼마나 잘 따라가는지 확인한다. Primary DRBC test를 대체하는 것이 아니라 robustness/stress evidence를 제공하는 보조 분석이다.

## 상태

완료에 가깝다. Catalog, inference, analysis가 실행되어 exposure table, primary checkpoint inference export, stress-error table, paired delta, event plot이 생성되어 있다.

주요 산출물은 아래에 있다.

```text
output/model_analysis/extreme_rain/primary/
```

All-validation-epoch stress sensitivity는 별도 output root에 있다.

```text
output/model_analysis/extreme_rain/all/
```

## 분석 단위

Primary stress analysis는 DRBC historical stress event 236개와 DRBC basin 38개를 사용한다. Paired seed는 `111 / 222 / 444`다.

Rain cohort 분포는 `prec_ge100` 100개, `prec_ge50` 58개, `prec_ge25` 65개, `near_prec100` 13개다. Response class는 positive response와 negative control로 나뉜다.

| response class | events |
| --- | ---: |
| `flood_response_ge25` | 49 |
| `flood_response_ge2_to_lt25` | 107 |
| `high_flow_non_flood_q99_only` | 56 |
| `low_response_below_q99` | 24 |

Positive response event는 156개이고, negative control event는 80개다.

## 생성된 표와 그림

주요 CSV는 `extreme_rain_stress_error_table_long.csv`, `extreme_rain_stress_error_table_wide.csv`, `cohort_predictor_aggregate.csv`, `paired_delta_aggregate.csv`, `rain_cohort_predictor_aggregate.csv`, `coverage_failure_report.csv`다.

Event plot은 236개가 생성되어 있고, `event_plot_index.html`에서 볼 수 있다. 본문에는 이 중 대표 positive-response case와 negative-control case를 소수만 골라야 한다.

## 현재 해석

Positive response event에서 Model 2 `q50`은 Model 1보다 peak underestimation을 개선하지 못한다. `flood_response_ge25`에서 Model 1의 observed-peak underestimation fraction은 0.959이고 median under-deficit은 `72.0%`다. Model 2 `q50`은 underestimation fraction 0.966, median under-deficit `76.6%`로 오히려 더 낮다.

Upper quantile은 stress response에서 under-deficit을 줄인다. `flood_response_ge25`에서 `q95`는 median under-deficit을 `45.8%`, `q99`는 `27.3%`까지 낮춘다. Threshold exceedance recall도 Model 1 0.374에서 `q95` 0.624, `q99` 0.729로 높아진다.

`flood_response_ge2_to_lt25`에서도 같은 방향이다. Model 1 median under-deficit은 `49.1%`이고, Model 2 `q50`은 `66.3%`로 악화된다. 반면 `q95`는 `16.1%`, `q99`는 `0.53%`까지 낮춘다.

Negative control에서는 tradeoff가 보인다. `low_response_below_q99`에서 `q99`의 median predicted window peak to flood ARI100 ratio가 1.249로 올라간다. 이는 upper quantile이 positive-response peak를 더 잘 덮는 대신, low-response event에서 false-positive 위험을 키울 수 있음을 의미한다.

## 해석 제한

이 분석은 basin-holdout historical stress test다. DRBC basin은 train에 들어가지 않았지만, 기간이 `1980-2024`라서 train/validation/test year와 시간적으로 겹칠 수 있다. 따라서 temporal independence evidence로 쓰면 안 된다.

`prec_ari*`와 `flood_ari*`는 CAMELSH hourly annual-maxima proxy다. official return period나 flood inventory로 과장하지 않는다.

## 논문에서의 위치

이 분석은 Results 후반의 robustness/stress section에 둔다. 본문 메시지는 “upper quantile output은 historical extreme-rain positive-response event에서도 under-deficit을 줄이는 방향을 보이지만, negative-control event에서는 false-positive tradeoff를 같이 평가해야 한다”로 쓰는 것이 안전하다.

## 남은 작업

Event plot 236개 중 본문용 대표 사례를 선별해야 한다. 추천 구성은 `flood_response_ge25` 성공 사례 1개, `flood_response_ge2_to_lt25` 사례 1개, `low_response_below_q99` false-positive 후보 1개다.
