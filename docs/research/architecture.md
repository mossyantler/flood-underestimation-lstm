# 모델 구조와 아키텍처

## 전체 연구 구조

현재 프로젝트는 하나의 모델을 바로 제안하는 방식이 아니라, 세 단계 아키텍처를 비교하는 구조입니다.

1. `Deterministic multi-basin LSTM`
2. `Probabilistic multi-basin LSTM`
3. `Physics-guided probabilistic hybrid`

이 비교 구조를 택한 이유는, 성능 개선이 `출력 head` 때문인지, `physics-guided core` 때문인지 분리해서 해석하기 위해서입니다.

## 공통 입력

세 모델의 공통 입력은 기본적으로 다음을 사용합니다.

- dynamic forcing: `prcp`, `tmax`, `tmin`, `srad`, `vp`, 필요 시 `PET`
- static attributes: 면적, 평균 경사, aridity, snow fraction, soil depth, permeability, baseflow index 등
- 선택적 lagged obs: 후속 실험에서 `lagged Q`를 넣을 수 있음

현재 설계의 기본 단위는 `multi-basin daily streamflow prediction`입니다.

## 1. Deterministic LSTM

가장 단순한 baseline입니다.

```text
inputs
  -> LSTM encoder
  -> regression head
  -> Q_hat
```

여기서 LSTM은 hidden state `h_t`를 만들고, regression head는 그 `h_t`를 최종 유량 `Q_hat`으로 바꿉니다. 이 모델은 평균적인 수문곡선을 잘 맞추는 기준선 역할을 합니다.

## 2. Probabilistic LSTM

두 번째 모델은 backbone은 그대로 두고 출력층만 바꿉니다.

```text
inputs
  -> LSTM encoder
  -> probabilistic head
  -> q50, q90, q95, q99
```

핵심은 deterministic point estimate 대신 `upper-tail quantiles`를 직접 예측하게 만드는 것입니다. 이렇게 하면 평균 회귀 때문에 발생하는 `peak underestimation`을 더 직접적으로 줄일 수 있습니다.

이 단계에서의 핵심 질문은 이것입니다. `physics guidance 없이 probabilistic output만으로도 extreme flood peak bias를 얼마나 줄일 수 있는가?`

## 3. Physics-guided probabilistic hybrid

세 번째 모델은 probabilistic LSTM 위에 conceptual core를 추가합니다. 다만 `To bucket or not to bucket?`에서 비판받은 naïve dynamic-parameter hybrid를 그대로 쓰지 않습니다.

우리가 지향하는 구조는 다음과 같습니다.

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

여기서 중요한 점은 LSTM이 conceptual model의 파라미터 전체 `θ_t`를 시점별로 마음대로 바꾸는 것이 아니라, `melt`, `ET`, `infiltration`, `percolation`, `routing coefficient` 같은 제한된 flux 또는 bounded coefficient만 제안하도록 하는 것입니다.

이 구조의 장점은 세 가지입니다.

- physics의 역할이 단순 장식이 아니라 실제 `state update`와 `routing`에 들어감
- AI가 physics를 덮어쓰는 정도를 줄일 수 있음
- probabilistic head와 결합해 peak magnitude와 tail risk를 동시에 다룰 수 있음

## conceptual core의 기본 상태 변수

첫 논문 수준에서는 복잡도를 과도하게 높이지 않고, 다음과 같은 상태 변수로 시작하는 것이 적절합니다.

- `snow storage`
- `soil storage`
- `fast runoff storage`
- `slow/baseflow storage`
- 필요 시 `channel/routing storage`

이 상태들은 물수지와 runoff generation을 더 명시적으로 표현하기 위한 최소 골격입니다.

## head의 역할 구분

현재 아키텍처에서는 head를 명확히 구분해서 이해해야 합니다.

- `regression head`: `h_t -> Q_hat`
- `probabilistic head`: `h_t -> q50, q90, q95, q99`
- `flux head`: `h_t -> melt, ET, infiltration, percolation ...`
- `bounded coefficient head`: `h_t -> routing coefficient, partition factor ...`

즉, LSTM의 본래 출력은 hidden state `h_t`이고, 실제 우리가 보는 값은 각 head가 `h_t`를 해석해서 만든 결과입니다.

## 현재 프로젝트에서의 아키텍처 원칙

1. backbone은 첫 논문에서 `multi-basin LSTM`으로 고정한다.  
2. probabilistic head를 먼저 넣어 tail modeling 효과를 분리한다.  
3. physics-guided core는 후속 비교축으로 넣되, `dynamic-parameter shell`이 아니라 `state/flux-constrained` 구조로 설계한다.  
4. flash flood처럼 더 짧은 시간 해상도 문제는 후속 연구 주제로 분리하고, 첫 논문은 daily extreme flood underestimation에 집중한다.
