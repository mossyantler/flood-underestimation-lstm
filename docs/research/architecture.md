# 모델 구조와 아키텍처

## 서술 목적

이 문서는 현재 논문 범위의 모델 `구성 요소와 연결 방식`을 정리한다. 즉 `head가 무엇을 내는지`, `Model 1과 Model 2가 어떻게 다른지`, `Model 3 메모를 어디까지 future work로 둘지`를 설명한다.

## 다루는 범위

- deterministic baseline과 probabilistic baseline의 구조 비교
- head의 역할 구분과 backbone 고정 원칙
- physics-guided conceptual core를 future work로 다루는 경계

## 다루지 않는 범위

- 연구 질문과 비교 가설
- exact split 규칙과 config key
- quantile head의 학부 수준 직관 설명

## 상세 서술

## 전체 연구 구조

현재 논문의 공식 비교축은 두 단계다.

1. `Deterministic multi-basin LSTM`
2. `Probabilistic multi-basin LSTM`

이 구조를 택한 이유는 성능 개선이 `출력 head` 때문인지 먼저 분리해서 보기 위해서다. `physics-guided conceptual core`는 현재 논문 범위 밖의 후속 확장으로 둔다.

## 공통 입력

현재 논문 범위의 두 모델 공통 입력은 아래를 기본으로 쓴다.

- dynamic forcing: `prcp`, `tmax`, `tmin`, `srad`, `vp`, 필요 시 `PET`
- static attributes: 면적, 평균 경사, aridity, snow fraction, soil depth, permeability, baseflow index 등
- 선택적 lagged obs: 후속 실험에서 `lagged Q`를 넣을 수 있음

현재 설계의 기본 단위는 `non-DRBC CAMELSH global training -> DRBC holdout basin evaluation` 구조 위의 multi-basin hourly streamflow prediction이다. 따라서 현재 backbone은 특정 지역에 맞춘 regional model이 아니라, 다양한 basin에서 공통 표현을 학습하는 `global multi-basin model`로 이해해야 한다.

## 1. Deterministic LSTM

가장 단순한 baseline이다.

```text
inputs
  -> LSTM encoder
  -> regression head
  -> Q_hat
```

LSTM은 hidden state `h_t`를 만들고, regression head는 이를 최종 유량 `Q_hat`으로 바꾼다. 이 모델은 평균적인 수문곡선을 맞추는 기준선이다.

## 2. Probabilistic LSTM

두 번째 모델은 backbone은 그대로 두고 출력층만 바꿉니다.

```text
inputs
  -> LSTM encoder
  -> probabilistic head
  -> q50, q90, q95, q99
```

핵심은 point estimate 대신 `upper-tail quantiles`를 직접 예측하게 만드는 것이다. 이렇게 해야 평균 회귀로 생기는 `peak underestimation`을 더 직접적으로 줄일 수 있다.

이 단계에서의 핵심 질문은 이것이다. `physics guidance 없이 probabilistic output만으로도 extreme flood peak bias를 얼마나 줄일 수 있는가?`

## 3. Physics-guided conceptual core 메모

`Model 3`는 현재 논문의 공식 비교축이 아니다. 다만 후속 연구를 위해 `bounded flux/coefficient head + conceptual core + residual quantile head` 방향의 설계 메모를 유지한다.

현재 단계에서 이 메모를 남겨 두는 이유는 두 가지다.

- probabilistic head만으로도 해결되지 않는 timing / routing 문제를 나중에 어디서 보완할지 정리하기 위해서
- future work 문단에서 `naive dynamic-parameter hybrid`가 아니라 `state/flux-constrained core`를 지향한다고 분명히 말하기 위해서

세부 설계는 [`conceptual_core_design.md`](conceptual_core_design.md)에 두고, 본문 비교와 구현 규범에서는 제외한다.

## head의 역할 구분

현재 아키텍처에서는 head를 명확히 구분해서 이해해야 한다.

- `regression head`: `h_t -> Q_hat`
- `probabilistic head`: `h_t -> q50, q90, q95, q99`
- `flux head`와 `bounded coefficient head`: future work의 conceptual core 메모에서만 다룸

즉 LSTM의 본래 출력은 hidden state `h_t`이고, 우리가 보는 값은 각 head가 `h_t`를 해석한 결과다.

## 문서 정리

1. backbone은 첫 논문에서 `multi-basin LSTM`으로 고정한다.  
2. 공식 비교축은 `Model 1 vs Model 2`다.  
3. probabilistic head를 먼저 넣어 tail modeling 효과를 분리한다.  
4. physics-guided core는 future work 메모로만 유지하고, 현재 논문의 메인 claim에서는 제외한다.  
5. 첫 논문은 CAMELSH hourly 기반 extreme flood response에 집중하고, sub-hourly flash flood는 후속 연구 주제로 분리한다.

## 관련 문서

- [`design.md`](design.md): 연구 질문과 비교 가설
- [`experiment_protocol.md`](experiment_protocol.md): split, loss, metric, config key
- [`../workflow/prob_head.md`](../workflow/prob_head.md): quantile head의 직관 설명
- [`conceptual_core_design.md`](conceptual_core_design.md): future-work conceptual core 메모
