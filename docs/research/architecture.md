# 모델 구조와 아키텍처

## 서술 목적

이 문서는 세 모델의 `구성 요소와 연결 방식`을 정리한다. 즉 `head가 무엇을 내는지`, `physics-guided core를 어디에 두는지`, `모델 간 구조 차이`를 설명한다.

## 다루는 범위

- deterministic, probabilistic, physics-guided 세 모델의 구조 비교
- head와 conceptual core의 역할 구분
- 현재 프로젝트의 backbone 고정 원칙

## 다루지 않는 범위

- 연구 질문과 비교 가설
- exact split 규칙과 config key
- quantile head의 학부 수준 직관 설명

## 상세 서술

## 전체 연구 구조

현재 프로젝트는 하나의 모델을 바로 제안하기보다, 세 단계 아키텍처를 비교하는 구조다.

1. `Deterministic multi-basin LSTM`
2. `Probabilistic multi-basin LSTM`
3. `Physics-guided probabilistic hybrid`

이 구조를 택한 이유는 성능 개선이 `출력 head` 때문인지 `physics-guided core` 때문인지 분리해서 보기 위해서다.

## 공통 입력

세 모델의 공통 입력은 아래를 기본으로 씁니다.

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

## 3. Physics-guided probabilistic hybrid

세 번째 모델은 probabilistic LSTM 위에 conceptual core를 추가한다. 다만 `To bucket or not to bucket?`에서 비판받은 naïve dynamic-parameter hybrid를 그대로 쓰지 않는다.

우리가 지향하는 구조는 다음과 같다.

```text
inputs
  -> LSTM encoder
  -> hydromet memory h_t
  -> flux / bounded-coefficient head
  -> conceptual core (storage + routing)
  -> base hydrograph
  -> probabilistic head
  -> final quantiles / Q_hat
```

여기서 중요한 점은 LSTM이 conceptual model의 파라미터 전체 `θ_t`를 시점별로 마음대로 바꾸는 것이 아니라, `melt`, `ET`, `infiltration`, `percolation`, `routing coefficient` 같은 제한된 flux 또는 bounded coefficient만 제안하도록 하는 것이다.

이 구조의 장점은 세 가지다.

- physics의 역할이 단순 장식이 아니라 실제 `state update`와 `routing`에 들어감
- AI가 physics를 덮어쓰는 정도를 줄일 수 있음
- probabilistic head와 결합해 peak magnitude와 tail risk를 동시에 다룰 수 있음

## conceptual core의 기본 상태 변수

첫 논문 수준에서는 복잡도를 과도하게 높이지 않고, 다음과 같은 상태 변수로 시작하는 것이 적절하다.

- `snow storage`
- `soil storage`
- `fast runoff storage`
- `slow/baseflow storage`
- 필요 시 `channel/routing storage`

이 상태들은 물수지와 runoff generation을 표현하는 최소 골격이다.

## head의 역할 구분

현재 아키텍처에서는 head를 명확히 구분해서 이해해야 한다.

- `regression head`: `h_t -> Q_hat`
- `probabilistic head`: `h_t -> q50, q90, q95, q99`
- `flux head`: `h_t -> melt, ET, infiltration, percolation ...`
- `bounded coefficient head`: `h_t -> routing coefficient, partition factor ...`

즉 LSTM의 본래 출력은 hidden state `h_t`이고, 우리가 보는 값은 각 head가 `h_t`를 해석한 결과다.

## 문서 정리

1. backbone은 첫 논문에서 `multi-basin LSTM`으로 고정한다.  
2. probabilistic head를 먼저 넣어 tail modeling 효과를 분리한다.  
3. physics-guided core는 후속 비교축으로 넣되, `dynamic-parameter shell`이 아니라 `state/flux-constrained` 구조로 설계한다.  
4. 첫 논문은 CAMELSH hourly 기반 extreme flood response에 집중하고, sub-hourly flash flood는 후속 연구 주제로 분리한다.

## 관련 문서

- [`design.md`](design.md): 연구 질문과 비교 가설
- [`experiment_protocol.md`](experiment_protocol.md): split, loss, metric, config key
- [`../workflow/prob_head.md`](../workflow/prob_head.md): quantile head의 직관 설명
