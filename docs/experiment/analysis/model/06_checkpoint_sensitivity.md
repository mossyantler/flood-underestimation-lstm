# 06 Checkpoint Sensitivity 분석

## 질문

이 분석은 primary result가 validation-best checkpoint 하나에만 의존하는지 확인한다. Primary epoch는 validation 기준으로 이미 잠겨 있으며, all-validation-epoch sweep은 checkpoint 재선택이 아니라 sensitivity diagnostic이다.

## 상태

완료에 가깝다. 세 종류의 sensitivity 산출물이 있다.

```text
output/model_analysis/overall_analysis/epoch_sensitivity/
output/model_analysis/quantile_analysis/
output/model_analysis/extreme_rain/all/
```

추가로 primary result가 all-validation-epoch distribution 안에서 어디에 위치하는지 보여주는 compact table과 figure를 생성했다.

```text
output/model_analysis/overall_analysis/epoch_sensitivity/tables/checkpoint_sensitivity_compact_metrics.csv
output/model_analysis/overall_analysis/epoch_sensitivity/tables/checkpoint_sensitivity_compact_summary.csv
output/model_analysis/overall_analysis/epoch_sensitivity/figures/checkpoint_compact/checkpoint_sensitivity_compact_summary.png
```

## 분석 단위

Validation checkpoint grid는 epoch `005 / 010 / 015 / 020 / 025 / 030`이다. Seed는 `111 / 222 / 444`를 공식 paired comparison으로 사용한다. Seed `333`은 Model 2 NaN loss 때문에 공식 chart와 aggregate CSV 생성 단계에서 제외한다.

Sensitivity에는 두 종류가 있다. 첫째, same-epoch comparison은 Model 1 epoch N과 Model 2 epoch N을 직접 비교한다. 둘째, primary comparison은 validation 기준 primary epoch mapping을 사용한다. 이 둘을 섞어서 primary epoch를 다시 고르면 안 된다.

## 생성된 표와 차트

Epoch metric sweep에는 `epoch_sensitivity/tables/test_same_epoch_delta_summary.csv`, `epoch_sensitivity/tables/epoch_metric_summary.csv`, `epoch_sensitivity/logs/training_epoch_log.csv`, `epoch_sensitivity/logs/validation_epoch_log.csv`가 있다. Basin-level metric 분포를 직접 보는 box plot은 `epoch_sensitivity/figures/epoch_metric_boxplots/`에 따로 두고, chart manifest와 metadata는 `epoch_sensitivity/metadata/epoch_metric_boxplots/`에 둔다. Hydrograph all-epoch 분석에는 flow stratum summary와 quantile gap summary가 있다. Extreme-rain all-validation-epoch 분석에는 `paired_delta_epoch_aggregate.csv`, `cohort_epoch_predictor_aggregate.csv`, `rain_cohort_epoch_predictor_aggregate.csv`가 있다.

주요 chart는 아래에 있다.

```text
output/model_analysis/overall_analysis/epoch_sensitivity/figures/test_same_epoch_delta_summary.png
output/model_analysis/overall_analysis/epoch_sensitivity/figures/epoch_metric_boxplots/
output/model_analysis/overall_analysis/epoch_sensitivity/metadata/epoch_metric_boxplots/
output/model_analysis/quantile_analysis/analysis/charts/q99_exceedance_underestimation_fraction_by_epoch.png
output/model_analysis/quantile_analysis/analysis/charts/q99_exceedance_q99_q50_gap_pct_obs_by_epoch.png
output/model_analysis/overall_analysis/epoch_sensitivity/figures/checkpoint_compact/checkpoint_sensitivity_compact_summary.png
```

## 현재 해석

Same-epoch test delta summary를 보면 Model 2 `q50`의 중앙예측 성능은 seed와 epoch에 따라 차이가 있다. 예를 들어 seed 222와 seed 444에서는 후반 epoch에서 median NSE delta가 크게 양수로 나타나지만, high-flow bias와 Peak-MAPE 개선은 seed별로 안정적이지 않다. 이는 central metric만으로 flood-tail 결론을 고르면 위험하다는 뜻이다.

Hydrograph all-epoch 분석에서는 q95/q99의 upper-tail 효과가 반복적으로 나타난다. 특히 `q99`는 여러 same-epoch run에서 Model 1 대비 Q99-exceedance underestimation fraction을 낮추는 방향을 보인다. 다만 epoch가 뒤로 갈수록 quantile band가 좁아지는 경향이 있어, tail safety margin이 줄 수 있다.

Extreme-rain all-validation-epoch sensitivity는 18개 seed-epoch 조합을 포함한다. 각 조합은 236개 stress event와 38개 basin을 사용한다. 이 결과는 primary stress result가 특정 checkpoint 하나의 우연인지 확인하는 데 쓸 수 있다.

Compact sensitivity figure 기준으로는 primary Q99-exceedance `q99` underestimation fraction median이 `0.440`이고, same-epoch grid median은 `0.451`이다. 즉 primary high-flow tail result는 all-epoch 분포 안에서 특별히 유리한 outlier로 보이지 않는다. Primary Q99-exceedance `q99-q50` spread median은 `74.6% obs`이고 same-epoch grid median은 `67.3% obs`라, primary는 upper-tail margin이 약간 큰 편이다.

Extreme-rain stress에서는 더 조심해야 한다. Positive-response q99 under-deficit reduction은 primary compact value가 `22.1%p`이고 same-epoch grid median은 `38.5%p`다. 반대로 negative-control q99 predicted peak / ARI100은 primary `1.249`, same-epoch median `1.200`으로, primary가 false-positive proxy 측면에서 특별히 안전한 checkpoint라고 보기도 어렵다.

## 논문에서의 위치

이 분석은 main result 뒤의 sensitivity section으로 둔다. 핵심 문장은 “primary checkpoint는 validation 기준으로 고정했고, all-epoch sweep은 upper-tail underestimation mitigation이 특정 checkpoint 하나에만 의존하는지 확인하는 diagnostic이다”가 되어야 한다.

## 남은 작업

본문에는 compact sensitivity figure를 두고, 상세 all-epoch boxplot과 stress epoch table은 supplement로 보내는 편이 좋다. 해석 문장은 “high-flow upper-tail result는 primary checkpoint 하나의 유리한 우연으로 보이지 않지만, extreme-rain stress magnitude는 checkpoint에 민감하므로 supporting diagnostic으로 제한한다”가 안전하다.
