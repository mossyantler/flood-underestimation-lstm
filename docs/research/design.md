# 연구 설계

## 서술 목적

이 문서는 이 연구가 `무엇을 묻고 왜 이 비교를 하는가`를 정리한다. 현재 논문의 공식 비교축은 Model 1과 Model 2이며, Model 3는 후속 연구 방향으로만 다룬다.

## 다루는 범위

- 현재 논문의 연구 질문과 비교축
- 데이터셋, 입력 변수, split, loss, metric의 개념 수준 설계
- Model 1 vs Model 2에서 기대하는 해석과 논문 contribution
- Model 3를 후속 연구로 남겨 두는 이유

## 다루지 않는 범위

- 실제 config key 이름
- built-in/custom metric 경계
- run 산출물 규칙

## 상세 서술

## 논문 가제

`Reducing Extreme Flood Underestimation with Probabilistic Extensions of Multi-Basin LSTM Models`

## 연구 질문

1. `deterministic LSTM의 extreme flood underestimation이 probabilistic head만으로 얼마나 줄어드는가`
2. `이 개선이 same-basin different-time뿐 아니라 DRBC regional holdout과 extreme-event holdout에서도 유지되는가`
3. `probabilistic baseline이 전체 성능을 크게 해치지 않으면서 upper-tail 진단과 calibration 정보를 얼마나 더 제공하는가`

## 현재 논문 비교 모델

### Model 1. Deterministic LSTM

입력은 forcing + static attributes이고, 출력은 단일 유량 `Q_hat`이다.  
가장 기본적인 baseline이다.

### Model 2. Probabilistic LSTM

backbone은 Model 1과 동일하고, 출력만 `q50, q90, q95, q99` 같은 quantile로 바꾼다.  
`tail-aware output`의 순수 효과를 보기 위한 현재 논문의 핵심 비교축이다.

현재 논문의 공식 비교는 Model 1과 Model 2로 제한한다. 즉 이 논문은 `physics-guided extension까지 한 번에 증명하는 구조`가 아니라, `output design 변화만으로 peak underestimation을 얼마나 줄일 수 있는가`를 먼저 검증하는 구조다.

## 후속 연구 방향: Model 3

Model 3는 LSTM encoder 뒤에 `flux / bounded-coefficient head`를 두고, conceptual storage와 routing core를 통과한 뒤 probabilistic head를 두는 physics-guided probabilistic hybrid를 뜻한다. 이 구조는 저장소와 문서에 계속 남겨 두지만, 현재 논문의 비교 대상은 아니다.

이 방향은 Model 1 vs Model 2 결과를 해석한 뒤에도 peak timing, basin generalization, state consistency 문제가 크게 남을 때 follow-up research로 다루는 것이 맞다.

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

$$
L = L_{\text{center}} + \lambda_1 L_{q_{90}} + \lambda_2 L_{q_{95}} + \lambda_3 L_{q_{99}}
$$

핵심은 평균 회귀뿐 아니라 upper tail을 직접 학습시키는 것이다.

## 후속 확장 메모

Model 3를 후속으로 확장한다면, Model 2의 probabilistic loss 위에 physics regularization을 추가하는 방향이 자연스럽다.

$$
L = L_{\text{prob}} + \lambda_4 L_{\text{mass\_balance}} + \lambda_5 L_{\text{nonnegativity}} + \lambda_6 L_{\text{storage\_bounds}}
$$

다만 이 식은 현재 논문의 공식 실험 규약이 아니라, 이후 physics-guided hybrid를 설계할 때 참고할 개념 메모다.

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

또한 같은 backbone과 같은 split을 유지한 채 개선이 나타난다면, 현재 논문의 핵심 메시지는 `physics-guided structure까지 가지 않아도 output design만으로 의미 있는 홍수 성능 개선이 가능하다`가 된다.

### 현재 논문 이후의 해석

반대로 Model 1 vs Model 2 비교 뒤에도 peak timing, ungauged basin generalization, state consistency 문제가 크게 남는다면, 그때 physics-guided conceptual core를 후속 연구 질문으로 꺼내는 것이 자연스럽다.

## 문서 정리

1. deterministic LSTM의 extreme flood underestimation을 probabilistic head가 얼마나 줄이는지 정량화한다.  
2. temporal, basin holdout, extreme-event holdout에서 Model 1과 Model 2의 차이가 어떻게 유지되는지 분해해서 보여준다.  
3. Model 3 physics-guided hybrid는 현재 논문 밖의 follow-up direction으로만 남겨 둔다.

## 관련 문서

- [`architecture.md`](architecture.md): 현재 논문 공식 구조와 Model 3 follow-up 개념
- [`experiment_protocol.md`](experiment_protocol.md): 실행 규범과 config key
- [`literature_review.md`](literature_review.md): 관련 문헌 배경
