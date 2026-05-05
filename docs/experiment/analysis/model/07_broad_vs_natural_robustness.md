# 07 Broad vs Natural Robustness 분석

## 질문

이 분석은 hydromodification risk가 적은 Natural subset에서도 Model 2 upper quantile의 paired-delta 방향이 Broad main result와 유사하게 유지되는지 확인하기 위한 robustness check다.

## 상태

완료에 가깝다. 기존 subset300 DRBC test 결과를 재학습 없이 cohort로 다시 나누어 계산했다.

Natural DRBC test basin은 8개이고, Broad DRBC test basin 38개 안에 모두 포함된다. 따라서 이번 산출물은 세 cohort를 함께 둔다.

```text
broad_all_38
natural_8
broad_non_natural_30
```

`broad_all_38`은 공식 main result와 직접 연결되는 전체 DRBC test set이고, `broad_non_natural_30`은 Natural 8개를 제외한 나머지 basin이다. Natural과 독립적인 contrast를 볼 때는 `natural_8` 대 `broad_non_natural_30`으로 읽는다.

## 산출물

기본 출력 위치는 아래다.

```text
output/model_analysis/natural_broad_comparison/
```

핵심 파일은 아래와 같다.

```text
output/model_analysis/natural_broad_comparison/report/natural_broad_comparison_report.md
output/model_analysis/natural_broad_comparison/tables/primary_overall_delta_by_cohort_aggregate.csv
output/model_analysis/natural_broad_comparison/tables/primary_high_flow_predictor_by_cohort_aggregate.csv
output/model_analysis/natural_broad_comparison/tables/event_regime_delta_by_cohort_aggregate.csv
output/model_analysis/natural_broad_comparison/tables/extreme_rain_delta_by_cohort_aggregate.csv
```

재현 스크립트는 아래다.

```bash
uv run scripts/model/overall/analyze_natural_broad_comparison.py
```

## 핵심 결과

Primary overall metric에서는 Natural 8개에서 Model 2 `q50`의 paired delta가 Broad 전체보다 더 좋게 보인다. seed-median aggregate 기준 `mean_median_delta_NSE`는 Broad 38개 `0.185`, Natural 8개 `3.118`, broad non-natural 30개 `0.126`이다. 다만 Natural basin 수가 작고 basin composition 효과가 크므로, 이 값만으로 Natural subset에서 일반 성능이 더 좋다고 강하게 주장하지 않는다.

High-flow Q99 exceedance에서는 Natural subset에서도 upper quantile의 underestimation 완화 방향이 유지된다. `q99` underestimation fraction은 Broad 38개 `0.449`, Natural 8개 `0.194`, broad non-natural 30개 `0.515`다. Natural의 `q99` median relative bias는 `+146.756%`로 크게 양수라서, 이 결과는 calibrated q99라기보다 aggressive upper-tail decision output으로 해석해야 한다.

Observed high-flow event window에서도 같은 방향이다. 전체 event 기준 `q99`의 median under-deficit reduction은 Broad 38개 `33.287`, Natural 8개 `26.505`, broad non-natural 30개 `35.437` percentage points다. `q50`은 세 cohort 모두에서 peak under-deficit reduction이 음수라 tail 보정 출력으로 쓰기 어렵다.

Extreme-rain historical stress에서도 `q95/q99`의 방향은 대체로 유지된다. 다만 이 stress test는 `1980-2024` historical window를 포함하므로 independent temporal test claim에는 사용하지 않는다.

## 해석

결론은 Broad 38개에서 보인 upper quantile의 peak underestimation 완화가 Natural 8개로 필터링해도 사라지지 않는다는 것이다. Natural 표본은 8개뿐이라 p-value나 강한 일반화 주장을 붙이기에는 부족하고, 논문에서는 hydromodification-risk filtering에 대한 robustness check로 제한해서 쓰는 것이 안전하다.
