# 00 연구 질문 ↔ 분석 매핑

## 서술 목적

이 문서는 본 연구의 핵심 주제를 세부 연구 질문(Research Question, RQ)으로 분해하고, 각 RQ가 어떤 분석 문서·스크립트·산출물에 1:1로 대응되는지 정리한다. 분석 결과 자체를 다시 쓰지 않고, "어느 질문을 어떤 분석으로 답하는가"의 지도를 제공한다.

각 분석 문서(`01_*` ~ `10_*`)는 단일 RQ에 한정해 작성되어 있다. 이 문서는 그 위의 한 단계인 "RQ 사이의 논리 구조"를 명시해, 논문 Results 배치와 supplement 분리 결정에서 일관성을 유지하는 용도로 쓴다.

## 다루는 범위

- 핵심 주제와 가설의 한 줄 정의
- RQ-A부터 RQ-G까지의 세부 질문 정의와 역할
- 각 RQ가 어떤 분석 문서·스크립트·산출물에 대응되는지
- RQ 사이의 논리 흐름과 본문/supplement 배치 가이드

## 다루지 않는 범위

- 각 RQ의 수치 결과와 해석 (해당 분석 문서가 다룬다)
- quantile output을 해석하는 framework (`docs/experiment/method/model/quantile_output_interpretation.md`이 다룬다)
- 실험 split, seed, checkpoint 규칙 (`docs/experiment/method/model/experiment_protocol.md`이 다룬다)

## 핵심 주제와 가설

본 연구의 주제는 multi-basin LSTM hourly streamflow 예측에서 **극한 홍수 첨두 과소추정(extreme flood peak underestimation) 완화**다. 공식 비교축은 아래 둘이다.

- Model 1: deterministic LSTM
- Model 2: probabilistic quantile LSTM, output `q50 / q90 / q95 / q99`

핵심 가설은 다음과 같다.

> Model 2의 upper quantile output(`q90 / q95 / q99`)이 Model 1 deterministic 예측의 high-flow / peak underestimation을 줄인다. 이때 Model 2 `q50`은 Model 1의 중앙예측 성능을 큰 손해 없이 유지해야 한다.

이 가설은 단일 질문이 아니라 여러 RQ로 분해된다. 각 RQ는 가설의 한 측면을 검증한다.

## 실험 고정 조건

모든 RQ에 공통으로 적용된다.

- seed: `111 / 222 / 444` (Model 2 seed `333`은 NaN loss로 중단되어 공정성 위해 Model 1 seed `333`도 final aggregate에서 제외)
- basin subset: scaling_300 (non-DRBC training pool 1923개에서 고정 추출한 300개)
- temporal split: train `2000-2010`, validation `2011-2013`, test `2014-2016`
- primary epoch: validation median NSE 기준으로 잠금, test 결과로 재선택 금지

Historical extreme-rain stress test(RQ-D)는 DRBC basin holdout 조건은 유지하지만 `1980-2024` 기간을 포함하므로 temporal independence claim에는 쓰지 않는다.

## RQ 정의와 분석 매핑

### RQ-A. q50가 중앙예측 성능을 유지하는가

Model 2 `q50`이 Model 1 deterministic 대비 전체 hydrograph 성능을 큰 손해 없이 유지하는지 확인한다. 이 RQ는 핵심 가설의 **전제 조건**이다. `q50` 성능이 무너지면 upper quantile의 이득 주장이 의미를 잃는다.

| 항목 | 위치 |
| --- | --- |
| 분석 문서 | [`01_primary_overall_performance.md`](01_primary_overall_performance.md) |
| 주요 스크립트 | `scripts/model/overall/analyze_subset300_epoch_results.py` |
| 산출물 | `output/model_analysis/legacy/overall_analysis/main_comparison/` |
| 해석 단위 | Model 2 `q50` only, seed-paired |

### RQ-B. upper quantile이 peak 과소추정을 줄이는가

본 연구의 **중심 질문**이다. Q-threshold exceedance stratum(Q90 / Q95 / Q99 / Q99.9)과 observed peak hour에서 `q90 / q95 / q99`가 Model 1 대비 peak underestimation을 얼마나 줄이는지, 그리고 그 대가로 over-prediction tradeoff는 어떻게 변하는지 본다.

| 항목 | 위치 |
| --- | --- |
| 분석 문서 | [`02_primary_high_flow_peak_performance.md`](02_primary_high_flow_peak_performance.md) |
| 주요 스크립트 | `scripts/model/hydrograph/analyze_subset300_hydrograph_outputs.py` |
| 산출물 | `output/model_analysis/legacy/quantile_analysis/analysis/` |
| 해석 단위 | `q50 → q90 → q95 → q99` sequence, observed peak hour 비교 |

### RQ-C. 효과가 어떤 event-regime / 조건에서 강한가

upper quantile의 underestimation 완화 효과가 모든 event에서 균일한지, 특정 hydrometeorological regime이나 severity tier 또는 특정 hydromet / static 조건에서 더 강하게 나타나는지 본다. 효과의 일반성과 조건성을 동시에 진단한다.

| sub-RQ | 분석 문서 | 주요 스크립트 |
| --- | --- | --- |
| ML event-regime별 효과 | [`03_event_regime_performance.md`](03_event_regime_performance.md) | `scripts/model/event_regime/analyze_subset300_event_regime_errors.py`, `scripts/model/event_regime/plot_subset300_event_regime_summary.py` |
| flood-relevance proxy tier별 효과 | [`04_extreme_flood_proxy_performance.md`](04_extreme_flood_proxy_performance.md) | event_regime 산출물 재사용 (`flood_relevance_tier_predictor_aggregate.csv`) |
| 어떤 hydromet / static 조건이 효과·tradeoff를 키우나 | [`10_event_surrogate_shap.md`](10_event_surrogate_shap.md) | `scripts/model/event_regime/analyze_subset300_event_surrogate_shap.py` |

flood-relevance proxy의 high-return tier(`ge25yr`, `ge50yr`)는 event 수가 1개로 매우 작다. 본문 headline 대신 supplement / case study로 내려야 한다.

### RQ-D. 외부 극한 강수 stress에서도 효과가 유지되는가

hourly `Rainf` rolling sum으로 직접 추출한 historical extreme-rain event(`1980-2024`)에서 `q90 / q95 / q99`가 streamflow stress response의 peak를 얼마나 잘 따라가는지, 그리고 false-positive tradeoff는 어떤지 본다. Primary DRBC test를 대체하지 않고 robustness/stress evidence로만 쓴다.

| 항목 | 위치 |
| --- | --- |
| 분석 문서 | [`05_extreme_rain_stress_test.md`](05_extreme_rain_stress_test.md) |
| 주요 스크립트 | `scripts/model/extreme_rain/` 디렉터리 (catalog → infer → analyze → plot 체인) |
| 산출물 (primary) | `output/model_analysis/legacy/extreme_rain/primary/` |
| 산출물 (all-epoch) | `output/model_analysis/legacy/extreme_rain/all/` |

### RQ-E. 결론이 checkpoint·cohort 선택에 견고한가

핵심 결론이 validation-best primary checkpoint 하나 또는 DRBC test basin cohort 정의에 우연히 의존하는 것은 아닌지 점검한다. 두 sub-RQ로 나뉜다.

| sub-RQ | 분석 문서 | 주요 스크립트 |
| --- | --- | --- |
| primary 결론이 single checkpoint에만 의존하는가 (all-validation-epoch sweep) | [`06_checkpoint_sensitivity.md`](06_checkpoint_sensitivity.md) | `scripts/model/overall/plot_subset300_checkpoint_sensitivity_compact.py`, epoch sweep 산출물 |
| Natural(low-hydromod) basin에서도 paired-delta 방향이 유지되는가 | [`07_broad_vs_natural_robustness.md`](07_broad_vs_natural_robustness.md) | `scripts/model/overall/analyze_natural_broad_comparison.py` |

primary epoch는 validation 기준으로 이미 잠겨 있다. all-validation-epoch sweep은 checkpoint 재선택이 아니라 sensitivity diagnostic이다. 같은 원칙으로 Natural 8개와 broad non-natural 30개도 재학습 없이 cohort split만 다시 한 것이다.

### RQ-F. quantile output이 probabilistic forecast로서 calibrated인가

`q50 / q90 / q95 / q99`가 quantile forecast로서 얼마나 잘 calibrated되어 있는지, quantile별 pinball / AQS는 어떤지, high-flow 조건부 stratum에서 tail hit-rate는 어떤지, upper-tail spread는 어떻게 변하는지 진단한다. RQ-B의 decision output 해석에 필요한 통계적 근거를 공급한다.

| 항목 | 위치 |
| --- | --- |
| 분석 문서 | [`08_probabilistic_calibration_pinball.md`](08_probabilistic_calibration_pinball.md) |
| 주요 스크립트 | `scripts/model/hydrograph/analyze_subset300_probabilistic_diagnostics.py` |
| 산출물 | `output/model_analysis/legacy/probabilistic_diagnostics/` |

현재 quantile set에는 lower quantile(`q01 / q05 / q10`)이 없다. 따라서 central prediction interval, interval score, Winkler score, 95% PI width는 공식 metric으로 쓰지 않는다. 자세한 해석 규칙은 [`docs/experiment/method/model/quantile_output_interpretation.md`](../../method/model/quantile_output_interpretation.md)을 본다.

### RQ-G. 잔차의 경계 사례를 어떻게 해석할 것인가

extreme-rain stress event 중 강수 forcing은 강한데 관측 유량 response가 낮거나, 반대로 강수 forcing은 약한데 관측 유량만 큰 pulse / plateau를 보이는 case를 어떻게 진단할지 정리한다. 모델 결함과 관측 인공물(reservoir release, diversion, managed-flow signal)을 분리하기 위한 protocol이다. 신규 metric이나 공식 screening rule이 아니다.

| 항목 | 위치 |
| --- | --- |
| 분석 문서 | [`09_event_suppression_diagnosis_protocol.md`](09_event_suppression_diagnosis_protocol.md) |
| 입력 | `output/model_analysis/legacy/extreme_rain/primary/` catalog와 plot manifest, USGS monitoring location note |

## RQ 사이의 논리 흐름

```text
RQ-A (q50 비용 없음 전제)
    │
    └─→ RQ-B (upper quantile이 peak 과소추정 줄임)  ← 중심 결론
            │
            ├─→ RQ-C (효과의 조건화: regime / tier / SHAP)
            ├─→ RQ-D (외부 극한 강수 stress 재현)
            ├─→ RQ-E (checkpoint / cohort 견고성)
            ├─→ RQ-F (quantile calibration 품질)
            └─→ RQ-G (눌린 obs case 진단, 잔차 해석)
```

| 역할 | RQ |
| --- | --- |
| 전제 (premise) | RQ-A |
| 중심 결론 (core claim) | RQ-B |
| 일반화 / 조건화 (generalization) | RQ-C, RQ-D |
| 견고성 (robustness defense) | RQ-E |
| 통계적 품질 (forecast quality) | RQ-F |
| 한계·해석 (caveat / case-level interpretation) | RQ-G |

## 본문 / supplement 배치 가이드

본 매핑을 따라 논문 Results와 supplement를 구성할 때의 권장 배치다. 결과 수치가 아직 변할 수 있는 RQ는 본문에서 제외한다.

| 위치 | RQ |
| --- | --- |
| 본문 headline | RQ-A 요약, RQ-B 전체 |
| 본문 secondary | RQ-C의 ML event-regime, RQ-D의 paired delta, RQ-F의 calibration / pinball 요약 |
| supplement | RQ-C의 flood-proxy tier 중 high-return-period, RQ-E 전체, RQ-G case 사례, RQ-F의 stratum별 세부 표 |

## 해석 framework 연결

본 문서는 "어느 분석이 어느 질문을 답하는지"의 구조만 다룬다. 각 분석에서 `q50 / q90 / q95 / q99`를 어떤 의미로 읽어야 하는지, 어떤 해석이 금지되는지, RQ별로 어떤 해석 layer를 써야 하는지는 [`docs/experiment/method/model/quantile_output_interpretation.md`](../../method/model/quantile_output_interpretation.md)에서 별도로 정한다. 본문 / supplement 작성 시 두 문서를 함께 참조한다.
