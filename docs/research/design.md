# 연구 설계

## 서술 목적

이 문서는 이 연구가 `무엇을 묻고 왜 이 비교를 하는가`를 정리한다. 연구 질문, 비교축, 기대 해석, 핵심 contribution이 중심이다.

## 다루는 범위

- 연구 질문과 비교축
- 데이터셋, 입력 변수, split, loss, metric의 개념 수준 설계
- 모델 간 기대 해석과 논문 contribution

## 다루지 않는 범위

- 실제 config key 이름
- built-in/custom metric 경계
- run 산출물 규칙

## 상세 서술

## 논문 가제

`Reducing Extreme Flood Underestimation with Probabilistic and Physics-Guided Extensions of Multi-Basin LSTM Models`

## 연구 질문

1. `deterministic LSTM의 extreme flood underestimation이 probabilistic head만으로 얼마나 줄어드는가`
2. `이 개선이 same-basin different-time뿐 아니라 다른 basin과 extreme-event holdout에서도 유지되는가`
3. `probabilistic head만으로 남는 한계는 무엇이며, future work에서 어떤 physics-guided 확장이 필요한가`

## 비교 모델

### Model 1. Deterministic LSTM

입력은 forcing + static attributes이고, 출력은 단일 유량 `Q_hat`이다.  
가장 기본적인 baseline이다.

### Model 2. Probabilistic LSTM

backbone은 Model 1과 동일하고, 출력만 `q50, q90, q95, q99` 같은 quantile로 바꿉니다.  
`tail-aware output`의 순수 효과를 보기 위한 비교축이다.

### Future Work. Physics-guided conceptual core

physics-guided conceptual core는 현재 논문의 공식 비교축이 아니다.  
다만 probabilistic head 이후에도 남는 timing, routing, state interpretability 문제를 다루기 위한 후속 확장 방향으로 유지한다.

## 데이터셋

현재 프로젝트의 기본 데이터셋은 `CAMELSH hourly dataset`이다.  
학습은 DRBC와 겹치지 않는 `non-DRBC quality-pass CAMELSH basin`에서 수행하고, DRBC 기준 `Delaware River Basin`은 regional holdout / evaluation region으로 둔다. 즉 이 연구는 Delaware 전용 regional model을 학습하는 것이 아니라, `global multi-basin model`을 학습한 뒤 DRBC에서 regional generalization을 평가하는 구조다. DRBC 내부 basin subset은 DRBC 공식 경계와 CAMELSH basin polygon / outlet을 기준으로 확정한다.

`CAMELS-US`, `CAMELS-GB`, `Caravan subset`은 후속 robustness check나 related work 비교축으로만 둔다.

## 입력 변수

기본 입력은 다음과 같다.

- `prcp`
- `tair` 또는 `tmax/tmin`
- `srad`
- `vp`
- 필요 시 `PET`

세부 변수명과 단위는 CAMELSH forcing source에 맞춰 최종 확정한다.

static attributes는 flood response에 직접 관련된 변수 위주로 고른다.

- `area`
- `slope`
- `aridity`
- `snow fraction`
- `soil depth`
- `permeability`
- `baseflow index`

## 데이터 분할

첫 논문에서는 세 종류의 평가 환경을 둔다.

### 1. Temporal split

같은 유역에서 학습 기간과 테스트 기간을 나눈다.  
이 실험은 `same-basin / different-time` 일반화를 본다.

### 2. PUB/PUR 또는 basin holdout split

학습에 사용하지 않은 유역을 테스트에 둔다.  
현재 기본 regional holdout은 `DRBC basin 전체`이며, 이 실험은 `non-DRBC에서 학습한 global multi-basin model이 Delaware basin으로 얼마나 일반화되는가`를 본다.

### 3. Extreme-event holdout

학습에서 상위 event 일부를 제외하고, 테스트에서만 extreme peak를 평가한다.  
이 실험은 `training distribution 밖의 flood peak`에 대한 외삽 능력을 본다.

## 손실 함수

### Model 1

기본 deterministic loss를 사용한다.  
예: `MSE` 또는 `NSE-style loss`

### Model 2

중앙 예측을 위한 기본 손실에 더해 quantile마다 `pinball loss`를 더한다.

```text
L = L_center + λ1 L_q90 + λ2 L_q95 + λ3 L_q99
```

핵심은 평균 회귀뿐 아니라 upper tail을 직접 학습시키는 것이다.

### Future Work 메모

physics-guided conceptual core를 붙일 경우에는 `Model 2의 probabilistic loss + physics regularization` 구조를 고려할 수 있다. 다만 이 항목은 현재 논문용 공식 실험 규칙이 아니라 후속 설계 메모다.

## 평가 지표

전체 성능과 flood 특화 성능을 분리해서 본다.

### 전체 성능

- `NSE`
- `KGE`
- `NSElog`

### flood / extreme 성능

- `FHV`
- `Peak Relative Error`
- `Peak Timing Error`
- `top 1% flow recall`
- `event-level RMSE`

### probabilistic 성능

- `pinball loss`
- `coverage`
- `calibration`

## 기대되는 해석

### Model 1 vs Model 2

이 비교는 `tail-aware output`의 순수 효과를 보여준다.  
만약 Model 2가 peak bias를 크게 줄인다면, 첫 번째 병목은 평균 회귀와 tail suppression이라는 해석이 가능하다.

### Model 2 이후의 해석

현재 논문은 `Model 1 vs Model 2`의 차이를 `tail-aware output의 순수 효과`로 해석하는 데 집중한다.  
이 비교 뒤에도 timing이나 routing 한계가 남는다면, 그때 `physics-guided state/routing structure`를 후속 연구 질문으로 제기하는 것이 자연스럽다.

## 문서 정리

1. deterministic LSTM의 extreme flood underestimation을 probabilistic head가 얼마나 줄이는지 정량화한다.  
2. temporal, basin holdout, extreme-event holdout에서 `Model 1 vs Model 2` 강점이 어떻게 갈리는지 분해해서 보여준다.  
3. physics-guided conceptual core는 현재 논문 범위 밖의 future work로 둔다.

## 관련 문서

- [`architecture.md`](architecture.md): 현재 논문 범위의 두 모델 구조와 future-work 메모
- [`experiment_protocol.md`](experiment_protocol.md): 실행 규범과 config key
- [`literature_review.md`](literature_review.md): 관련 문헌 배경
