# 연구 설계

## 논문 가제

`Reducing Extreme Flood Underestimation with Probabilistic and Physics-Guided Extensions of Multi-Basin LSTM Models`

## 연구 질문

첫 번째 질문은 `deterministic LSTM의 extreme flood underestimation이 probabilistic head만으로 얼마나 줄어드는가`입니다.

두 번째 질문은 `probabilistic LSTM 위에 physics-guided conceptual core를 추가하면 peak magnitude, low-flow bias, peak timing, 유역 일반화가 추가로 개선되는가`입니다.

세 번째 질문은 `이 개선이 같은 유역의 다른 시기뿐 아니라, 다른 유역과 extreme event holdout에서도 유지되는가`입니다.

## 비교 모델

### Model 1. Deterministic LSTM

입력은 forcing + static attributes이고, 출력은 단일 유량 `Q_hat`입니다.  
이 모델은 현재 수문 AI의 가장 기본적인 baseline입니다.

### Model 2. Probabilistic LSTM

backbone은 Model 1과 동일하고, 출력만 `q50, q90, q95, q99` 같은 quantile로 바꿉니다.  
이 모델은 `tail-aware output`의 순수 효과를 보기 위한 비교축입니다.

### Model 3. Physics-guided probabilistic hybrid

LSTM encoder 뒤에 `flux / bounded-coefficient head`를 두고, conceptual storage와 routing core를 통과한 뒤 probabilistic head를 둡니다.  
이 모델은 `physics-guided structure`가 probabilistic output 위에서 추가 가치를 갖는지 확인하기 위한 비교축입니다.

## 데이터셋

첫 번째 논문은 `CAMELS-US multi-basin daily dataset`을 기본 데이터셋으로 사용합니다.  
후속 확장이나 robustness check에서는 `CAMELS-GB` 또는 `Caravan subset`을 부록 수준으로 고려할 수 있습니다.

## 입력 변수

기본 입력은 다음과 같습니다.

- `prcp(mm/day)`
- `tmax(C)`
- `tmin(C)`
- `srad(W/m2)`
- `vp(Pa)`
- 필요 시 `PET`

static attributes는 flood response에 직접 관련된 변수 위주로 고릅니다.

- `area`
- `slope`
- `aridity`
- `snow fraction`
- `soil depth`
- `permeability`
- `baseflow index`

## 데이터 분할

첫 논문에서는 세 종류의 평가 환경을 둡니다.

### 1. Temporal split

같은 유역에서 학습 기간과 테스트 기간을 나눕니다.  
이 실험은 `same-basin / different-time` 일반화를 봅니다.

### 2. PUB/PUR 또는 basin holdout split

학습에 사용하지 않은 유역을 테스트에 둡니다.  
이 실험은 `다른 환경의 유역으로의 일반화`를 봅니다.

### 3. Extreme-event holdout

학습에서 상위 event 일부를 제외하고, 테스트에서만 extreme peak를 평가합니다.  
이 실험은 `training distribution 밖의 flood peak`에 대한 외삽 능력을 봅니다.

## 손실 함수

### Model 1

기본 deterministic loss를 사용합니다.  
예: `MSE` 또는 `NSE-style loss`

### Model 2

중앙 예측을 위한 기본 손실에 더해 quantile마다 `pinball loss`를 더합니다.

```text
L = L_center + λ1 L_q90 + λ2 L_q95 + λ3 L_q99
```

핵심은 평균 회귀뿐 아니라 upper tail을 직접 학습시키는 것입니다.

### Model 3

Model 2의 손실에 physics regularization을 추가합니다.

```text
L = L_prob + λ4 L_mass_balance + λ5 L_nonnegativity + λ6 L_storage_bounds
```

즉, tail modeling과 physics consistency를 동시에 요구합니다.

## 평가 지표

전체 성능과 flood 특화 성능을 분리해서 봅니다.

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

이 비교는 `tail-aware output`의 순수 효과를 보여줍니다.  
만약 Model 2가 peak bias를 크게 줄인다면, 첫 번째 병목은 평균 회귀와 tail suppression이라는 해석이 가능합니다.

### Model 2 vs Model 3

이 비교는 `physics-guided structure의 추가 가치`를 보여줍니다.  
만약 Model 3가 timing이나 ungauged basin에서 더 좋다면, tail-aware output만으로 부족한 부분을 state/routing structure가 보완했다고 해석할 수 있습니다.

## 논문에서 주장할 핵심 contribution

1. deterministic LSTM의 extreme flood underestimation을 probabilistic head가 얼마나 줄이는지 정량화한다.  
2. probabilistic baseline 위에서 physics-guided conceptual core의 추가 이득을 검증한다.  
3. temporal, basin holdout, extreme-event holdout에서 모델별 강점이 어떻게 갈리는지 분해해서 보여준다.
