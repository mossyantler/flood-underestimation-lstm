# Model 1/2 결과 분석 문서

이 폴더는 subset300 기반 Model 1 deterministic LSTM과 Model 2 probabilistic quantile LSTM 결과를 분석 축별로 나누어 정리한다. 각 문서는 하나의 분석 질문만 다루며, 논문 Results section의 표와 그림을 만들 때 바로 참조하는 것을 목표로 한다.

완료에 가까운 분석부터 먼저 배치했다. 아직 최종 산출물이 없는 분석은 `예정`으로만 표시하고, 결과 해석은 쓰지 않는다.

연구 질문(RQ-A ~ RQ-G)과 아래 분석 문서가 어떻게 1:1 대응되는지는 [`00_research_question_analysis_map.md`](00_research_question_analysis_map.md)에서 별도로 정리한다. 본 표는 분석 문서 단위의 인덱스이고, 그 위 단계의 RQ ↔ 분석 매핑은 `00` 문서를 본다.

| 순서 | 문서 | 상태 | 역할 |
| ---: | --- | --- | --- |
| 0 | [`00_research_question_analysis_map.md`](00_research_question_analysis_map.md) | 완료 | 핵심 주제를 RQ-A ~ RQ-G로 분해하고, 각 RQ가 아래 분석 문서와 어떻게 대응되는지 정리한다. |
| 1 | [`01_primary_overall_performance.md`](01_primary_overall_performance.md) | 완료에 가까움 | primary checkpoint에서 Model 2 `q50`이 전체 hydrograph 성능을 얼마나 유지하는지 본다. |
| 2 | [`02_primary_high_flow_peak_performance.md`](02_primary_high_flow_peak_performance.md) | 완료에 가까움 | Q-threshold exceedance stratum과 observed peak hour에서 `q90/q95/q99`가 peak underestimation을 줄이는지 본다. |
| 3 | [`03_event_regime_performance.md`](03_event_regime_performance.md) | 완료에 가까움 | observed high-flow event를 ML event-regime과 rule label sensitivity로 나누어 model error를 해석한다. |
| 4 | [`04_extreme_flood_proxy_performance.md`](04_extreme_flood_proxy_performance.md) | 부분 완료 | flood-relevance proxy tier별 결과를 보되, extreme proxy event 수가 작다는 한계를 명시한다. |
| 5 | [`05_extreme_rain_stress_test.md`](05_extreme_rain_stress_test.md) | 완료에 가까움 | hourly `Rainf` 기반 historical stress event에서 upper quantile output의 peak tracking과 false-positive tradeoff를 보고, 대표 flow graph diagnostic으로 실제 event 모양을 확인한다. |
| 6 | [`06_checkpoint_sensitivity.md`](06_checkpoint_sensitivity.md) | 완료에 가까움 | primary conclusion이 validation-best checkpoint 하나에만 의존하는지 all-validation-epoch sweep으로 확인한다. |
| 7 | [`07_broad_vs_natural_robustness.md`](07_broad_vs_natural_robustness.md) | 완료에 가까움 | Broad 38개 test basin을 Natural 8개와 broad non-natural 30개로 다시 나누어 upper-tail 결론 방향이 유지되는지 본다. |
| 8 | [`08_probabilistic_calibration_pinball.md`](08_probabilistic_calibration_pinball.md) | 완료에 가까움 | Model 2 quantile별 pinball/AQS, all-hour one-sided calibration, high-flow tail hit-rate, upper-tail spread를 진단한다. |
| 9 | [`09_event_suppression_diagnosis_protocol.md`](09_event_suppression_diagnosis_protocol.md) | 완료 | extreme-rain event에서 observed flow가 눌리거나, 약한 강수 조건에서 managed-flow pulse/plateau가 생기는 case를 유역별로 진단한다. |
| 10 | [`10_event_surrogate_shap.md`](10_event_surrogate_shap.md) | 초기 분석 완료 | event-level surrogate SHAP으로 q95/q99 under-deficit reduction과 q99 tradeoff가 어떤 hydromet/static 조건에서 커지는지 본다. |

## 해석 원칙

Primary 결과는 DRBC holdout `2014-2016` test를 기준으로 한다. Historical extreme-rain stress test는 DRBC basin holdout 조건은 유지하지만 `1980-2024` 기간을 포함하므로 temporal independence claim에는 쓰지 않는다.

Model 2의 `q50`은 중앙예측선이다. Model 1과의 중앙예측 성능 비교에는 `q50`을 쓰고, `q90/q95/q99`는 upper-tail decision output으로 별도 해석한다. 현재 quantile set에는 lower quantile이 없으므로 `q99`를 calibrated 99% prediction interval이나 return-period estimate로 쓰지 않는다.

## 산출물 위치

| 분석 | 주요 산출물 |
| --- | --- |
| Primary 전체 성능 / epoch metric box plot | `output/model_analysis/legacy/overall_analysis/main_comparison/`, `output/model_analysis/legacy/overall_analysis/epoch_sensitivity/figures/epoch_metric_boxplots/` (`metadata/epoch_metric_boxplots/`에 chart manifest) |
| High-flow / peak | `output/model_analysis/legacy/quantile_analysis/analysis/` |
| Event-regime | `output/model_analysis/legacy/quantile_analysis/event_regime_analysis/` |
| Event-level surrogate SHAP | `output/model_analysis/legacy/quantile_analysis/event_surrogate_shap/` |
| Extreme-rain stress | `output/model_analysis/legacy/extreme_rain/primary/` |
| Extreme-rain all-epoch sensitivity | `output/model_analysis/legacy/extreme_rain/all/` |
| Event suppression / managed-flow diagnosis | `docs/experiment/analysis/model/09_event_suppression_diagnosis_protocol.md` |
| Broad vs Natural robustness | `output/model_analysis/legacy/natural_broad_comparison/` |
| Probabilistic calibration / pinball | `output/model_analysis/legacy/probabilistic_diagnostics/` |
