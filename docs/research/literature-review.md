# 선행연구 정리

## 서술 목적

현재 프로젝트의 핵심 문제는 `다른 환경의 유역`과 `극한 홍수`에서 수문 AI 모델이 peak를 낮게 예측하는 경향이다. 그래서 선행연구도 `누가 NSE가 높은가`보다 `왜 peak가 눌리는가`, `physics가 실제로 도움이 되는가`, `유역 일반화와 extreme-event extrapolation에 무엇이 중요한가`를 중심으로 읽어야 한다.

이 문서는 related work 초안이 아니라, `어떤 문헌을 어디에 왜 쓰는지`를 빠르게 찾기 위한 압축 메모다.

## 다루는 범위

- 데이터셋, baseline, regionalization, physics-guided modeling 관련 대표 문헌
- 현재 프로젝트에 직접 연결되는 문헌 축 정리
- related work 서술 순서의 방향

## 다루지 않는 범위

- 공식 실험 규칙
- 현재 코드 구현 상태
- 논문 본문 전체 초안

## 상세 서술

## 논문 작성용 quick map

| 문헌 축 | 대표 문헌 | 핵심 용도 | 쓰는 위치 |
|---|---|---|---|
| 데이터셋 기반 | `Large-sample watershed-scale hydrometeorological data set` (2015), `CAMELS` (2017), `CAMELSH` (2025) | large-sample hydrology와 현재 DRBC + CAMELSH subset의 정당화 | Introduction 후반, Data section |
| LSTM baseline | `Rainfall-runoff modelling using LSTM networks` (2018) | deterministic LSTM baseline의 직접 출발점 | Related work, Baseline rationale |
| multi-basin regionalization | `Towards learning universal, regional, and local hydrological behaviors` (2019), `Never train a Long Short-Term Memory network on a single basin` (2024) | multi-basin 학습과 static attributes 사용의 정당화 | Method 배경, split 설계 소개 앞 |
| training budget / optimization | Kratzert et al. (2018), Frame et al. (2022), Kratzert et al. (2024), Feng et al. (2024) | epoch 수는 절대값보다 update 규모와 sampling unit과 함께 읽어야 한다는 점 정리 | Method의 hyperparameter rationale, Discussion |
| PUB/PUR 일반화 | GB benchmark (2021), ungauged basin regionalization (2023) | temporal split만으로 부족하고 basin holdout이 필요하다는 근거 | Evaluation setting |
| physics-guided modeling | `MC-LSTM` (2021), interpretable LSTM hydrology (2024), differentiable hydrologic models (2023) | physics-guided core를 state/flux-constrained 방향으로 설계할 근거 | Related work의 physics-guided 문단 |
| hybrid critique | `To bucket or not to bucket?` (2024), `When physics gets in the way` (2026) | naive dynamic-parameter hybrid의 한계와 `AI가 physics를 덮어쓸 수 있음`을 보여줌 | Model 3 설계 철학, Discussion |
| state recovery | `Data assimilation and autoregression...` (2022), `Improving streamflow simulation through machine learning-powered data integration` (2025) | lagged Q를 feature engineering이 아니라 state recovery 축으로 해석 | Future work, ablation |
| architecture scope | `From RNNs to Transformers` (2025) | 첫 논문에서는 backbone 경쟁보다 LSTM 고정이 타당함을 뒷받침 | Introduction 후반, scope delimitation |
| extreme / extrapolation | climate-shift physical constraints (2024), hydrologic extrapolation limits (2025) | peak underestimation을 tail suppression과 extrapolation 한계로 해석 | Problem statement, extreme-event holdout 필요성 |

## 축별 요약

### 1. 데이터셋과 large-sample hydrology

`CAMELS` 계열 문헌은 현재 프로젝트의 데이터 철학을 정리하는 기준이다. `CAMELSH`는 hourly forcing과 streamflow availability의 1차 citation이고, `CAMELS` 2015/2017은 attribute 체계와 large-sample hydrology 문맥을 받쳐 준다. `Caravan`은 후속 일반화 범위를 넓힐 때 유용하다.

### 2. deterministic LSTM과 multi-basin 학습

`LSTM rainfall-runoff` (2018)은 baseline의 출발점이고, `universal/regional/local behaviors` (2019)는 multi-basin 학습과 static attributes 결합의 대표 근거다. `Never train ... on a single basin` (2024)은 single-basin demo를 최종 실험으로 삼으면 안 된다는 점을 더 직접적으로 보여준다.

### 2.1 training budget과 epoch 해석

epoch 수만 보고 모델이 `많이 학습됐다` 또는 `적게 학습됐다`고 판단하면 오해가 생기기 쉽다. 수문 딥러닝 문헌에서는 같은 30 epoch라도 학습 basin 수, sequence 길이, minibatch 구성, sequence-to-one인지 sequence-to-sequence인지에 따라 실제 weight update 수와 학습 난도가 크게 달라진다. 따라서 선행연구의 epoch는 `절대값`이라기보다 `어떤 데이터 규모와 sampling 규칙에서 쓰였는가`와 함께 읽어야 한다.

| 문헌 | 설정 | 보고된 training budget | 현재 프로젝트에 주는 함의 |
|---|---|---|---|
| Kratzert et al. (2018) | single-basin LSTM, 241개 basin 각각 별도 학습 | 예비 실험에서 basin별로 200 epoch까지 돌려 validation NSE를 확인했고, 최종 single-basin 모델은 50 epoch를 사용했다 | single-basin은 basin당 데이터가 적어서 epoch 수가 더 크게 잡힐 수 있다 |
| Kratzert et al. (2018) | HUC별 regional LSTM | regional model은 20 epoch를 사용했다. 다만 저자들은 single-basin보다 epoch 수는 작아도 weight update는 훨씬 많다고 직접 설명한다 | regional 또는 multi-basin에서는 epoch 수가 작아 보여도 실제 학습량은 더 클 수 있다 |
| Kratzert et al. (2018) | regional pretraining 후 basin별 fine-tuning | fine-tuning epoch는 basin별로 다르게 선택했고 범위는 0에서 20, 중앙값은 10이었다 | pretraining이 있을 때는 추가 epoch 수가 작아도 충분할 수 있다 |
| Frame et al. (2022) | CAMELS 531 basin, extreme-event 비교, standard LSTM vs MC-LSTM | 두 모델 모두 30 epoch를 사용했다. minibatch size는 256, standard LSTM hidden size는 128, sequence length는 365일이었다 | flood-focused multi-basin baseline에서 30 epoch는 충분히 관행적인 선택이다 |
| Kratzert et al. (2024) | CAMELS 531 basin regional LSTM baseline | regional LSTM은 30 epoch, hidden size 256, output dropout 0.4, validation-best epoch selection으로 보고됐다 | 최근 large-sample LSTM baseline에서도 30 epoch 안팎이 자주 쓰인다 |
| Kratzert et al. (2024) | single-basin tuned LSTM | per-basin hyperparameter 탐색에서는 각 설정을 100 epoch까지 돌려 validation epoch를 고르는 방식이었다 | single-basin 실험은 공정 비교를 위해서도 계산 예산이 더 커질 수 있다 |
| Feng et al. (2024) | global daily LSTM, global differentiable HBV hybrid | global LSTM은 300 epoch까지 학습해 수렴시켰고, differentiable 모델도 같은 mini-batch 체계에서 학습했다 | global-scale이나 daily large-sample 실험에서는 30보다 훨씬 큰 epoch budget도 흔하다 |

정리하면 선행연구는 `항상 30 epoch` 같은 규칙을 보여주지 않는다. 대신 single-basin은 50 또는 100 epoch 이상도 흔하고, regional multi-basin baseline은 20에서 30 epoch가 자주 보이며, global-scale 실험은 300 epoch처럼 더 길게 가기도 한다. 따라서 현재 프로젝트의 `30 epoch`은 이상한 값이 아니라 `multi-basin LSTM baseline으로는 충분히 흔한 초기 budget`으로 볼 수 있다. 다만 최종적으로 충분한지는 validation convergence로 다시 확인해야 한다.

현재 프로젝트 문맥에서 더 중요한 점은, 우리는 Model 1과 Model 2의 비교에서 `output design` 효과를 분리하고 싶다는 것이다. 그래서 첫 공식 비교에서는 선행연구와 크게 어긋나지 않는 fixed budget인 30 epoch를 공통으로 두고, 이후 필요하면 `30 vs 50 epoch` 또는 early stopping 민감도 분석으로 충분성만 별도로 점검하는 설계가 가장 타당하다.

### 3. ungauged basin 일반화

GB benchmark와 ungauged basin regionalization 연구는 LSTM 계열이 다른 지역과 PUB/PUR setting에서도 경쟁력이 있음을 보여준다. 따라서 현재 연구도 `same-basin / different-time`만이 아니라 `basin holdout`을 명시적으로 포함해야 한다.

### 4. physics-guided와 interpretable sequence model

`MC-LSTM`, interpretable LSTM, differentiable hydrologic model 연구는 `physics를 구조 안에 실제로 넣는 방식`을 고민하게 만든다. 우리 프로젝트에서는 이를 `dynamic-parameter shell`이 아니라 `state/flux-constrained conceptual core` 방향으로 번역하는 것이 핵심이다.

### 5. state recovery와 lagged observation

data assimilation과 lagged-input 연구는 `현재 basin state를 더 잘 복원하면 예측이 좋아진다`는 점을 보여준다. 그래서 `lagged Q`는 강한 입력 후보지만, 기본 모델에서 일부러 빼는 이유도 분명해야 한다. 우리는 `output design 효과`를 먼저 분리해서 보고, lagged Q는 후속 ablation으로 남기는 편이 맞다.

### 6. extreme-event와 extrapolation

최근 extrapolation 연구들은 stand-alone LSTM이 training distribution 바깥의 forcing이나 climate shift에서 큰 peak를 충분히 열지 못할 수 있음을 보여준다. 이 점은 현재 문제를 단순 손실 함수 문제가 아니라 `tail suppression + extrapolation 한계`로 읽게 해 준다.

## 대표 논문 메모

| 문헌 | 핵심 포인트 | 우리 프로젝트에 주는 함의 |
|---|---|---|
| `To bucket or not to bucket?` (2024) | naive dynamic-parameter hybrid는 성능이나 해석 모두 애매할 수 있다 | Model 3는 파라미터 전체를 흔들지 말고 flux / bounded coefficient만 제한적으로 다루는 쪽이 낫다 |
| `When physics gets in the way` (2026) | physics constraint가 LSTM의 부담을 줄이기보다 오히려 보정 부담을 늘릴 수 있다 | physics를 넣더라도 `AI가 physics를 덮어쓰는 구조`를 피해야 한다 |
| `A national-scale hybrid model for enhanced streamflow estimation` (2024) | physics-aware input은 도움이 되지만 peak underestimation을 끝내지는 못한다 | Model 2와 Model 3 비교를 정당화하는 직접 근거다 |
| `Improving streamflow simulation through machine learning-powered data integration` (2025) | lagged Q는 매우 강하고, state recovery가 성능 개선의 핵심 축일 수 있다 | lagged Q는 강력한 후속 ablation이지만 baseline 설계와는 분리해서 해석해야 한다 |
| `From RNNs to Transformers` (2025) | 전체적으로는 여전히 LSTM이 안정적인 baseline이다 | 첫 논문에서는 backbone을 고정하고 output/core 효과를 분리하는 전략이 안전하다 |
| climate-shift / hydrologic extrapolation 연구 (2024-2025) | extreme event와 distribution shift에서 DL 모델의 한계가 드러난다 | `extreme-event holdout`과 probabilistic tail modeling의 필요성을 강화한다 |

## 문서 정리

1. 첫 번째 비교축은 `deterministic output vs probabilistic output`이어야 한다. peak underestimation의 중요한 원인 중 하나가 평균 회귀와 tail suppression이기 때문이다.
2. 그다음 비교축으로 `physics-guided conceptual core`를 넣어야 한다. 다만 설계는 naive hybrid가 아니라 `state/flux-constrained` 구조가 적절하다.
3. 실험은 `temporal split`만으로 끝내지 말고 `basin holdout`과 `extreme-event holdout`을 함께 둬야 한다.
4. 첫 논문에서는 backbone을 `multi-basin LSTM`으로 고정하고, output design과 physics-guided extension의 incremental gain을 분리해서 보는 편이 가장 설득력 있다.

related work 서술 순서는 `CAMELS / large-sample hydrology -> LSTM baseline과 multi-basin regionalization -> physics-guided / interpretable modeling -> hybrid critique -> probabilistic tail modeling과 extrapolation 한계` 정도로 두면 현재 프로젝트 질문과 가장 자연스럽게 이어진다.

## 관련 문서

- [`design.md`](design.md): 현재 연구 질문과 비교축
- [`architecture.md`](architecture.md): Model 3 구조 철학
- [`experiment_protocol.md`](experiment_protocol.md): 실제 실험 규칙
