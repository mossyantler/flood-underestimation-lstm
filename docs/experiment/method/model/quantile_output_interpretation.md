# Quantile Output Interpretation Guide

## 서술 목적

이 문서는 Model 2 probabilistic quantile LSTM이 매 시점 출력하는 네 개의 quantile `q50 / q90 / q95 / q99`를 어떻게 해석해야 하고 어떻게 해석하면 안 되는지를 정한다. 해석 framework를 명시적으로 두는 이유는, 같은 숫자가 RQ마다 다른 의미로 읽히는 위험을 막고, 본 연구에서 흔히 빠지는 오용을 사전에 차단하기 위해서다.

분석 결과 수치 자체는 다루지 않는다. 해석 규칙과 RQ별 적용 방식만 정의한다.

## 다루는 범위

- 네 개 quantile 각각이 통계적·수문학적·운영적으로 무엇을 의미하는지
- 학습 손실(pinball loss)과 quantile output의 연결
- lower quantile이 없는 현재 구성의 제약
- 4개 output을 함께 읽는 세 가지 방식 (Pairwise / Sequence / Spread)
- 자주 빠지는 오해석 6가지와 금지 표현
- RQ-A부터 RQ-G까지에서 어떤 해석 layer를 어떻게 적용할지
- 표·그림·논문 본문에서의 표기 규칙

## 다루지 않는 범위

- quantile head의 구조와 pinball loss의 정의 자체 → [`probabilistic_head_guide.md`](probabilistic_head_guide.md)이 다룬다
- 어떤 분석 문서가 어떤 RQ에 대응되는지 → [`docs/experiment/analysis/model/00_research_question_analysis_map.md`](../../analysis/model/00_research_question_analysis_map.md)이 다룬다
- 실험 split, seed, primary epoch 규칙 → [`experiment_protocol.md`](experiment_protocol.md)이 다룬다
- physics-guided hybrid(Model 3)의 출력 해석

## 한 줄 요약

`q50`은 중앙예측이고 Model 1 deterministic의 대응물이다. `q90 / q95 / q99`는 한쪽(upper-tail)만 가지는 conservatism level이다. 현재 구성에는 lower quantile이 없으므로 prediction interval, return period, 양방향 calibration 표현은 쓰지 않는다.

## 4개 quantile의 본질

| output | 본질 | 적법한 해석 | 자주 발생하는 오용 |
| --- | --- | --- | --- |
| `q50` | conditional median, central prediction | Model 1 deterministic과 직접 비교되는 중앙예측선. bias / NSE 등 central performance 지표의 대상 | conditional mean으로 해석 (skewed flow에서 둘은 다르다) |
| `q90` | one-sided 90% upper level | "이 시점에서 약 90% 확률로 obs ≤ `q90`이라 모델이 추정" | 80% prediction interval의 상한 |
| `q95` | one-sided 95% upper level | 보수적 peak alert threshold | 90% prediction interval의 상한 |
| `q99` | one-sided 99% upper level | 가장 보수적 peak protection output | return period(100-year flood), 98% PI 상한 |

### lower quantile 부재의 핵심 제약

현재 quantile set은 `q50 / q90 / q95 / q99`뿐이다. `q01 / q05 / q10` 같은 lower quantile이 없으므로 다음을 **공식 metric으로 쓰지 않는다**.

- central prediction interval (예: 90% PI, 95% PI)
- interval score, Winkler score
- 95% PI width 같은 양방향 spread
- 양방향 calibration(empirical PI coverage)

가능한 것은 다음 둘뿐이다.

- one-sided empirical coverage: `P(obs ≤ q_τ)` ≈ `τ`인지
- one-sided upper-tail spread: 예를 들어 `q99 − q50`의 폭

## 학습이 강제한 것과 강제하지 않은 것

quantile regression은 각 τ에 대해 pinball loss `E[(obs − q_τ)(τ − 1{obs<q_τ})]`를 최소화한다. 이 손실이 강제하는 것과 강제하지 않는 것을 구분해 둔다.

| 강제하는 것 | 강제하지 않는 것 |
| --- | --- |
| 각 τ에서 one-sided 분위 추정이 average sense로 일치하도록 학습됨 | quantile monotonicity (`q50 ≤ q90 ≤ q95 ≤ q99`) |
| 큰 obs 시점에서의 underestimation에 대해 τ가 클수록 더 큰 penalty | 양방향 PI calibration |
| τ별 sharpness와 calibration이 함께 영향을 받음 (단일 score) | high-flow 조건부 stratum에서의 정식 calibration |

따라서 분석 단계에서 다음 두 진단이 필요하다.

1. **quantile crossing 진단**: 학습 후 `q50 > q90` 등이 발생할 수 있다. crossing rate를 한 번은 측정하고, 그 뒤의 해석에서 monotonicity가 어느 수준에서 성립한다고 가정할지 정한다.
2. **calibration과 sharpness 분리**: pinball loss가 낮다는 것만으로 calibration이 좋다고 말하지 않는다. coverage·reliability를 별도로 확인한다.

## 해석 layer 4단계

같은 quantile output을 네 가지 추상화 수준으로 읽을 수 있다. 어느 RQ에서 어느 layer를 쓰는지가 다르므로 구분해 둔다.

### L1. 통계적 layer — 학습이 무엇을 강제했나

- pinball loss와 quantile regression theory
- monotonicity 가정 여부와 crossing 진단
- sharpness와 calibration의 결합 효과

### L2. 확률예측 layer — calibration과 sharpness

- empirical one-sided coverage `P(obs ≤ q_τ) ≈ τ` (all-hour)
- 조건부 hit-rate (high-flow stratum 등 obs를 이미 선택한 경우)
- one-sided upper-tail spread (`q99 − q50` 폭, half-width)

### L3. 수문 운영 layer — decision output

- `q50` = best-estimate hydrograph (Model 1 대응)
- `q90 / q95 / q99` = 점점 보수적인 alert level
- τ가 클수록 recall이 오르고 precision이 떨어지는 tradeoff
- 본 연구의 핵심: under-deficit reduction(τ↑) vs over-prediction cost(τ↑) 동시 평가

### L4. 가설 매핑 layer — 연구 주장과의 연결

Model 2의 가치 주장은 τ에 따라 다르게 표현된다.

| τ | 주장 형태 | 어느 RQ |
| --- | --- | --- |
| `q50` | 중앙예측 성능을 큰 손해 없이 유지 | RQ-A |
| `q90 / q95` | observed peak underestimation을 의미 있게 완화 | RQ-B 본문 |
| `q99` | 극단 peak protection이 가능하나 false-positive 비용이 동시에 커짐 | RQ-B / RQ-D supplement |

## 4개 output을 함께 읽는 세 방식

각 분석에서 어느 방식을 쓰는지 명시한다. 섞으면 해석이 흔들린다.

### (1) Pairwise — `q50` vs Model 1

용도: RQ-A, RQ-E의 central 성능 비교. `q90 / q95 / q99`는 끌고 들어오지 않는다.

| 비교 | 메트릭 |
| --- | --- |
| Model 1 vs Model 2 `q50` | NSE, KGE, observed mean bias, paired delta |

### (2) Sequence — `q50 → q90 → q95 → q99` 단조 증가폭

용도: RQ-B, RQ-C, RQ-D. peak를 잡는 정도가 τ에 따라 어떻게 변하는가.

| 측정 | 의미 |
| --- | --- |
| τ별 under-deficit reduction | 같은 obs peak 대비 각 τ가 underestimation을 얼마나 줄였나 |
| τ별 threshold recall delta | 같은 threshold(예: Q99 exceedance)에서 hit 비율 |
| `q99 − q50 gap pct obs` | observed peak hour에서 추가 보수성의 폭 |

### (3) Spread — `q99 − q50` 폭

용도: RQ-F, RQ-G. one-sided uncertainty proxy.

| 사용 | 주의 |
| --- | --- |
| event / stratum별 spread 비교 | spread가 클수록 모델 자신감이 낮다는 신호 |
| 부르는 이름 | "one-sided upper-tail spread"라 부른다. "uncertainty"는 양방향 분포 가정을 포함하므로 단독으로 쓰지 않는다 |

## 금지 해석 6가지

다음 표현은 본 연구의 모든 분석 문서, 표, 그림, 논문 본문에서 사용을 금지한다.

1. **`q99` = 100-year flood**
   quantile은 conditional one-step distribution의 99th percentile이다. return period는 annual maxima 분포에서 정의된다. 둘은 다른 객체다.
2. **`q90 / q99` = 80% prediction interval**
   prediction interval은 양측 quantile 쌍이 있어야 정의된다. lower quantile이 없는 현재 구성에서는 interval이라는 단어를 쓰지 않는다.
3. **observed Q99 exceedance stratum의 coverage = calibration**
   조건부 추출(obs가 이미 큰 시점만)이므로 nominal τ와 비교되는 정식 calibration이 아니다. "conditional hit-rate" 또는 "high-flow tail hit-rate"로 부른다.
4. **pinball loss가 낮음 = good calibration**
   pinball은 sharpness와 calibration이 결합된 proper score다. calibration 주장은 coverage / reliability diagram으로 따로 확인한다.
5. **`q99` peak가 obs를 초과하면 "맞춘 것"**
   over-prediction도 운영 비용이다. recall과 precision(또는 false alarm rate)을 함께 보고하지 않은 채 "맞췄다"고 쓰지 않는다.
6. **monotonicity 가정으로 시작**
   학습이 monotonicity를 강제하지 않으므로 crossing이 가능하다. crossing rate를 한 번 측정한 뒤, 어느 수준에서 가정할지 명시하고 사용한다.

## RQ별 해석 layer 매핑

| RQ | 사용하는 묶음 방식 | 주된 layer | 표기·금지 사항 |
| --- | --- | --- | --- |
| RQ-A (전체 성능) | Pairwise | L3 | `q50`만 사용. `q90 / q95 / q99`를 끌고 들어오지 않는다 |
| RQ-B (peak 핵심) | Sequence | L3 + L4 | recall과 precision(또는 false alarm rate)을 같은 표에서 보고 |
| RQ-C (regime / tier / SHAP) | Sequence + Spread | L3 | regime별 spread 차이를 함께 보고. high-return tier는 본문에 올리지 않는다 |
| RQ-D (extreme rain stress) | Sequence | L3 | peak tracking 이득과 false-positive cost를 같은 figure에서 보여준다 |
| RQ-E (견고성) | Pairwise + Sequence | L3 | RQ-A와 RQ-B에서 쓴 해석축을 그대로 유지 |
| RQ-F (calibration) | 전부 | L1 + L2 | one-sided임을 본문·캡션에 명시. lower quantile 부재 한계를 캡션에 한 줄 둔다 |
| RQ-G (managed-flow 진단) | `q95 / q99` + obs | L3 | over-prediction이 모델 결함인지 obs 인공물인지 분리. case-by-case |

## 표·그림·본문 표기 규칙

논문과 분석 문서 사이의 표기를 일관되게 유지하기 위한 최소 규칙이다.

- 표기: `q_τ`를 기본형으로 쓴다. 예: `q_0.90`, `q_0.95`, `q_0.99`. 본문 첫 등장 시 "Model 2의 quantile output `q90 / q95 / q99` (τ = 0.90, 0.95, 0.99)" 형태로 정의를 명시한다.
- 용어: "prediction interval", "PI width", "interval score", "Winkler score", "100-year flood quantile"은 본 연구 산출물에서 사용하지 않는다.
- coverage 보고: `P(obs ≤ q_τ)` 형태로 one-sided임을 식별 가능하게 적는다. high-flow stratum에서는 "conditional hit-rate"라 부른다.
- 시각화: `q99`를 envelope fill로 그리지 않는다. line만 그린다. fill로 그리면 양방향 PI로 오해된다. 굳이 쓸 때는 캡션에 "one-sided upper-tail band, lower bound is not modeled"라 명시한다.
- spread: "uncertainty"라 단독으로 쓰지 않고 "one-sided upper-tail spread (`q_τ − q_0.50`)"으로 적는다.

## 연결 문서

- 출력 head 자체의 정의와 학습 손실의 직관 → [`probabilistic_head_guide.md`](probabilistic_head_guide.md)
- RQ ↔ 분석 매핑 → [`docs/experiment/analysis/model/00_research_question_analysis_map.md`](../../analysis/model/00_research_question_analysis_map.md)
- calibration·pinball 실제 산출물과 표·그림 → [`docs/experiment/analysis/model/08_probabilistic_calibration_pinball.md`](../../analysis/model/08_probabilistic_calibration_pinball.md)
- 실험 split·seed·primary epoch 규칙 → [`experiment_protocol.md`](experiment_protocol.md)
