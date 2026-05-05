# 05 Extreme-Rain Stress Test 분석

## 질문

이 분석은 hourly `Rainf` rolling sum으로 직접 추출한 historical extreme-rain event에서 Model 1과 Model 2가 DRBC streamflow stress response를 얼마나 잘 따라가는지 확인한다. Primary DRBC test를 대체하는 것이 아니라 robustness/stress evidence를 제공하는 보조 분석이다.

## 상태

완료에 가깝다. Catalog, inference, analysis가 실행되어 exposure table, primary checkpoint inference export, stress-error table, paired delta, event plot이 생성되어 있다. 추가로 primary checkpoint 기준 대표 event flow graph diagnostic과 median-distance basin map index도 생성했다.

주요 산출물은 아래에 있다.

```text
output/model_analysis/extreme_rain/primary/
```

Rain event 시간축을 rolling exceedance endpoint가 아니라 실제 wet footprint 기준으로 다시 맞춘 v2 diagnostic은 원본 primary를 덮어쓰지 않고 아래에 별도 보관한다.

```text
output/model_analysis/extreme_rain/primary_time_aligned/
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

Time-aligned v2에서도 event 수는 236개로 유지된다. 다만 wet-footprint로 `rain_start / rain_peak / rain_end`를 다시 잡으면서 cohort 구성이 `prec_ge100` 101개, `prec_ge50` 57개, `prec_ge25` 65개, `near_prec100` 13개로 한 건 이동했고, response class는 `flood_response_ge2_to_lt25` 108개, `flood_response_ge25` 49개, `high_flow_non_flood_q99_only` 54개, `low_response_below_q99` 25개가 됐다. v2 sanity 기준으로 `observed_response_peak_time < rain_start`는 0개이고, 문제 사례였던 `01470779_rain_drbc_historical_stress_0004`는 `rain_start = 2010-09-30 08:00`, `rain_peak = 2010-09-30 15:00`, `rain_end = 2010-10-01 08:00`로 잡힌다.

## 생성된 표와 그림

주요 CSV는 `extreme_rain_stress_error_table_long.csv`, `extreme_rain_stress_error_table_wide.csv`, `cohort_predictor_aggregate.csv`, `paired_delta_aggregate.csv`, `rain_cohort_predictor_aggregate.csv`, `coverage_failure_report.csv`다.

Event plot은 236개가 생성되어 있고, `event_plots/event_plot_index.html`에서 볼 수 있다. 이 plot은 강수와 관측 streamflow response를 확인하는 observed-only diagnostic이다. 같은 236개 event에 대해 Model 1과 Model 2 `q50/q95/q99`를 함께 그린 sim-Q plot은 `event_simq_plots/`에 둔다. Basin별로 볼 때는 `event_plot_median_map_index.html`을 사용한다. 이 HTML은 primary metric median-distance tier를 먼저 고른 뒤 DRBC map에서 basin을 선택해 해당 basin의 sim-Q flow chart를 보여준다.

v2의 동일 산출물은 `primary_time_aligned/event_plots/`, `primary_time_aligned/event_simq_plots/`, `primary_time_aligned/event_plot_median_map_index.html`에 있다. v2 analysis는 기존 primary inference required-series를 재사용하되, v2 catalog에서 새로 필요한 `01478000_block_004`만 보충 inference로 추가해 coverage failure 0건으로 완료했다.

특정 event에서 강한 강수에도 observed flow가 눌려 보이거나, 반대로 약한 강수 조건에서 observed-only pulse/plateau가 생기는 원인을 개별 진단할 때는 [`09_event_suppression_diagnosis_protocol.md`](09_event_suppression_diagnosis_protocol.md)를 따른다. 이 protocol은 먼저 USGS station note를 읽고 [`docs/references/basin/usgs_station_notes/`](../../../references/basin/usgs_station_notes/)에 source summary를 저장한 뒤, `primary_time_aligned` catalog, sim-Q manifest, stress error table, basin metadata, nearby/upstream comparison을 같은 순서로 확인하는 case-level 해석 절차다.

v2 analysis에는 `Local Peak Quantile Bracket` diagnostic도 포함한다. 관측 response peak 값이 peak 시각 주변 `±6h`의 Model 2 local max `q50/q90/q95/q99` ladder 중 어디에 놓이는지를 `<=q50`, `q50-q90`, `q90-q95`, `q95-q99`, `>q99`로 분류하고, `0h` exact-time과 `12h` timing-tolerant sensitivity도 함께 저장한다. 산출물은 `primary_time_aligned/analysis/peak_quantile_bracket_event_table.csv`, `peak_quantile_bracket_summary.csv`, `peak_quantile_bracket_aggregate.csv`, `peak_quantile_bracket_sensitivity.csv`와 `figures/peak_quantile_bracket/` 아래 stacked-bar, `tau_hat` violin, `>q99` overflow severity plot이다. 이 지표는 calibrated exceedance probability가 아니라 extreme-rain 조건부 observed peak가 Model 2 quantile ladder 어디에 놓이는지 보는 diagnostic으로만 해석한다.

Model prediction을 겹친 대표 flow graph diagnostic은 아래에 있다.

```text
output/model_analysis/extreme_rain/primary/flow_graph_diagnostic/
```

이 폴더에는 `figures/`, `tables/`, `metadata/`가 있으며, 각 figure는 같은 event를 seed `111 / 222 / 444` 패널로 나누어 observed flow, Model 1, Model 2 `q50 / q95 / q99`를 함께 보여준다. v2 sim-Q event plot은 seed panel title에 `obs peak bracket: q95-q99` 같은 짧은 annotation을 붙여, 해당 hydrograph의 관측 peak가 Model 2 quantile ladder 중 어느 구간에 놓이는지 바로 확인할 수 있게 했다. 따라서 aggregate table에서 보인 “upper quantile은 under-deficit을 줄이지만 false-positive tradeoff가 있다”는 해석을 실제 hydrograph 모양으로 확인할 수 있다.

## 현재 해석

Positive response event에서 Model 2 `q50`은 Model 1보다 peak underestimation을 개선하지 못한다. `flood_response_ge25`에서 Model 1의 observed-peak underestimation fraction은 0.959이고 median under-deficit은 `72.0%`다. Model 2 `q50`은 underestimation fraction 0.966, median under-deficit `76.6%`로 오히려 더 낮다.

Upper quantile은 stress response에서 under-deficit을 줄인다. `flood_response_ge25`에서 `q95`는 median under-deficit을 `45.8%`, `q99`는 `27.3%`까지 낮춘다. Threshold exceedance recall도 Model 1 0.374에서 `q95` 0.624, `q99` 0.729로 높아진다.

`flood_response_ge2_to_lt25`에서도 같은 방향이다. Model 1 median under-deficit은 `49.1%`이고, Model 2 `q50`은 `66.3%`로 악화된다. 반면 `q95`는 `16.1%`, `q99`는 `0.53%`까지 낮춘다.

Negative control에서는 tradeoff가 보인다. `low_response_below_q99`에서 `q99`의 median predicted window peak to flood ARI100 ratio가 1.249로 올라간다. 이는 upper quantile이 positive-response peak를 더 잘 덮는 대신, low-response event에서 false-positive 위험을 키울 수 있음을 의미한다.

## Primary flow graph diagnostic

대표 event는 stress-error long table에서 자동 선별했다. 선택 기준은 primary metric이 아니라 visual diagnostic용이다. `flood_response_ge25`와 `flood_response_ge2_to_lt25`에서는 세 seed가 모두 있는 event 중 Model 1 대비 `q99`의 observed-peak under-deficit reduction이 큰 사례를 골랐고, `low_response_below_q99`에서는 관측 peak는 낮지만 `q99` predicted window peak가 flood ARI100 proxy를 크게 넘기는 사례를 골랐다.

선택된 세 figure는 아래와 같다.

| case | event | key read |
| --- | --- | --- |
| ARI25+ positive response | `01478000_rain_drbc_historical_stress_0003` | seed-mean Model 1 under-deficit `78.2%`, `q99` under-deficit `7.7%`; `q99` predicted peak / ARI100 `1.03` |
| ARI2-25 positive response | `01476480_rain_drbc_historical_stress_0005` | seed-mean Model 1 under-deficit `69.1%`, `q99` under-deficit `15.6%`; `q99` predicted peak / ARI100 `0.76` |
| low-response negative control | `01483200_rain_drbc_historical_stress_0003` | observed peak / ARI100 `0.07`; seed-mean Model 1 predicted peak / ARI100 `0.43`, `q99` predicted peak / ARI100 `3.00` |

첫 두 사례는 `q50`이 peak magnitude를 충분히 올리지 못하는 반면 `q95/q99`가 observed peak 쪽으로 올라가 underestimation을 줄이는 모양을 보여준다. 세 번째 사례는 관측 유량이 낮은 negative-control event에서도 `q99`가 flood proxy를 넘길 수 있음을 보여주므로, `q99`를 flood forecast처럼 단독 claim하면 안 되고 high-flow underestimation 완화 output으로 제한해서 읽어야 한다.

## 해석 제한

이 분석은 basin-holdout historical stress test다. DRBC basin은 train에 들어가지 않았지만, 기간이 `1980-2024`라서 train/validation/test year와 시간적으로 겹칠 수 있다. 따라서 temporal independence evidence로 쓰면 안 된다.

`prec_ari*`와 `flood_ari*`는 CAMELSH hourly annual-maxima proxy다. official return period나 flood inventory로 과장하지 않는다.

## 논문에서의 위치

이 분석은 Results 후반의 robustness/stress section에 둔다. 본문 메시지는 “upper quantile output은 historical extreme-rain positive-response event에서도 under-deficit을 줄이는 방향을 보이지만, negative-control event에서는 false-positive tradeoff를 같이 평가해야 한다”로 쓰는 것이 안전하다.

## 남은 작업

본문용 대표 사례는 `flow_graph_diagnostic/figures/`에 세 개로 선별해 두었다. 남은 작업은 논문 본문/부록에 세 figure를 모두 넣을지, 본문에는 positive-response 1개와 negative-control 1개만 넣고 나머지는 appendix로 보낼지 결정하는 것이다.
