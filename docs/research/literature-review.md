# 선행연구 정리

## 연구 목표와 문제 정의

현재 프로젝트의 핵심 문제는 `다른 환경의 유역`과 `극한 홍수`에서 수문 AI 모델이 peak를 낮게 예측하는 경향입니다. 따라서 선행연구는 단순히 전체 NSE가 높은 모델을 찾는 것이 아니라, `왜 peak가 눌리는지`, `물리 지식이 실제로 도움이 되는지`, `유역 일반화에 어떤 입력과 구조가 중요한지`를 기준으로 읽어야 합니다.

현재 문서는 최근 hybrid, benchmark, extreme-event 논문 위주로 정리돼 있었고, 그 자체로는 방향성이 나쁘지 않습니다. 다만 실제 논문용 related work로 쓰려면 `CAMELS와 large-sample hydrology`, `LSTM baseline과 multi-basin regionalization`, `ungauged basin 일반화`, `state recovery`, `physics-informed / differentiable model` 축이 함께 들어가야 합니다.

## 먼저 보강해야 하는 기초 선행연구 축

### CAMELS와 large-sample hydrology 기반

`Development of a large-sample watershed-scale hydrometeorological data set for the contiguous USA (2015)`와 `The CAMELS data set: catchment attributes and meteorology for large-sample studies (2017)`는 large-sample hydrology 계열의 출발점입니다. 현재 프로젝트는 운영 데이터셋으로 `CAMELSH hourly`를 쓰지만, CAMELSH가 결국 CAMELS 계열의 확장선 위에 있기 때문에 이 두 논문은 basin selection, forcing/attribute 철학, known limitation을 설명하는 기반 문헌으로 여전히 중요합니다.

여기에 `CAMELSH: A Large-Sample Hourly Hydrometeorological Dataset and Attributes at Watershed-Scale for CONUS (2025)`를 직접 연결해야 합니다. 지금 프로젝트는 DRBC 기준 Delaware River Basin subset 위에서 CAMELSH를 쓰기 때문에, 데이터셋 citation과 경계 정의, hourly forcing/streamflow availability 설명은 CAMELSH 논문이 1차 기준 문헌입니다.

후속 확장을 `CAMELS-GB`나 `Caravan subset`으로 고려한다면 `Caravan: A global community dataset for large-sample hydrology (2023)`와 `Large-sample hydrology – a few camels or a whole caravan? (2024)`도 함께 봐야 합니다. 이 축은 모델 구조 자체보다 `어떤 데이터에서 어떤 일반화를 주장할 수 있는가`를 정당화하는 데 필요합니다.

### LSTM rainfall-runoff baseline과 multi-basin regionalization

`Rainfall-runoff modelling using Long Short-Term Memory (LSTM) networks (2018)`는 rainfall-runoff LSTM baseline의 출발점입니다. 첫 번째 baseline을 deterministic LSTM으로 둘 생각이라면, 이 논문은 단순 선행연구가 아니라 baseline 정당화의 핵심입니다.

그 다음의 `Towards learning universal, regional, and local hydrological behaviors via machine learning applied to large-sample datasets (2019)`는 multi-basin 학습과 static attributes, regionalization 논리를 정리한 대표 연구입니다. 즉, 지금 프로젝트의 `multi-basin LSTM`은 갑자기 튀어나온 설정이 아니라 이 계열의 직접적인 연장선에 있습니다.

### single-basin이 아닌 multi-basin 학습의 정당화

`Never train a Long Short-Term Memory (LSTM) network on a single basin (2024)`는 방법론보다 실험 철학에 중요한 논문입니다. 현재 저장소의 runnable example은 single-basin demo이지만, 실제 논문 질문은 `다른 환경의 유역으로 일반화되는가`에 있기 때문에 최종 실험은 multi-basin 쪽으로 가야 한다는 점을 이 논문이 더 직접적으로 뒷받침합니다.

### 다른 지역과 ungauged basin으로의 일반화

`Benchmarking data-driven rainfall-runoff models in Great Britain: a comparison of long short-term memory (LSTM)-based models with four lumped conceptual models (2021)`은 CAMELS/CAMELSH 밖에서도 LSTM 계열이 강한지 보여주는 외부 벤치마크입니다. `Continuous streamflow prediction in ungauged basins: long short-term memory networks outperform traditional hydrological models in regionalization tests (2023)`는 ungauged basin generalization에 더 직접적인 근거를 제공합니다.

이 두 축은 우리 연구의 `다른 환경의 basin` 문제의 바깥 경계를 잡아줍니다. 즉, DRBC subset 내부 실험만으로는 부족하고, related work에서는 다른 지역과 PUB/PUR 문맥까지 연결해 줘야 논리적으로 더 단단해집니다.

### physics-guided, mass-conserving, interpretable sequence model

`MC-LSTM: Mass-Conserving LSTM (2021)`은 hydrology 전용 논문은 아니지만, mass conservation을 architecture 수준에서 강제하는 대표 사례입니다. 우리가 구상하는 conceptual core가 단순히 bucket shell을 붙이는 것이 아니라 `state update와 물수지 제약`을 실제 구조에 반영하려는 것이라면, 이 계열의 문제의식도 함께 봐야 합니다.

`Toward interpretable LSTM-based modeling of hydrological systems (2024)`는 hidden state와 hydrological concept를 더 직접적으로 맞추려는 시도이고, `The suitability of differentiable, physics-informed machine learning hydrologic models for ungauged regions and climate change impact assessment (2023)`는 differentiable process model이 ungauged region이나 climate shift에서 어떤 가능성과 한계를 갖는지 보여줍니다. 즉, 지금의 `state/flux-constrained conceptual core`는 recent hybrid 비판뿐 아니라 이 축과도 연결돼야 더 설득력이 있습니다.

### lagged observation / state recovery의 직접 선행

`Improving streamflow simulation through machine learning-powered data integration (2025)`는 현재 문서에 이미 들어 있지만, 그 직전 흐름으로 `Data assimilation and autoregression for using near-real-time streamflow observations in long short-term memory networks (2022)`를 함께 보는 편이 좋습니다. 이 계열은 공통적으로 `현재 basin state를 더 잘 복원하면 예측이 좋아진다`는 논리를 갖고 있습니다.

따라서 lagged Q를 후속 ablation으로 둘 계획이라면, 이를 단순 feature engineering이 아니라 `state recovery` 문제의 한 해법으로 서술해야 합니다. 그래야 왜 lagged Q가 강력하지만 기본 모델에서는 일부러 빼 두는지, 그리고 어떤 질문을 분리해서 보려는지가 더 명확해집니다.

## 1. To bucket or not to bucket? (2024)

이 논문은 `LSTM -> dynamic parameter head -> conceptual model(SHM)` 구조의 hybrid를 다룹니다. 핵심 질문은 bucket 구조를 붙이면 성능과 해석 가능성을 동시에 얻을 수 있는가였습니다.

결과는 `LSTM 0.87`, `LSTM+SHM 0.84`, `SHM 0.76`, `LSTM+Bucket 0.86`, `LSTM+NonSense 0.80` 수준이었고, 잘 설계되지 않은 구조를 붙여도 LSTM이 성능을 상당 부분 복구했습니다. 대신 hybrid 내부의 unsaturated zone storage는 ERA5-Land soil moisture와 높은 상관을 보여, 해석 가능성이 완전히 무너진 것은 아니었습니다.

우리 연구에 주는 교훈은 분명합니다. `LSTM이 시점별 θ_t를 내고 conceptual model을 조정하는 naïve dynamic-parameter hybrid`는 성능이 좋아도 physics의 기여를 주장하기 어렵습니다. 따라서 우리의 physics-guided 모델은 파라미터 전체를 흔드는 방식보다 `flux`나 `bounded coefficient`만 제한적으로 조정하는 구조로 가야 합니다.

## 2. When physics gets in the way (2026)

이 논문은 구조적으로는 위 논문과 같은 계열이지만, 초점은 `physics constraint가 정말 LSTM의 일을 줄여주는가`에 있습니다. 이를 보기 위해 hidden state entropy를 비교했습니다.

결과적으로 pure LSTM이 hybrid보다 더 낮은 entropy를 보인 basin이 대부분이었습니다. 이 해석은 물리 제약이 실제로 예측을 돕기보다는, 오히려 LSTM이 그 제약을 보정하느라 더 많이 움직였을 수 있다는 뜻입니다.

우리 연구에 주는 방향은, physics를 넣더라도 `AI가 physics를 덮어쓰는 구조`를 피해야 한다는 점입니다. 따라서 conceptual core를 넣는다면 `state/flux-constrained` 방식으로 두고, 필요하면 이후 단계에서 hidden-state entropy나 flux variability 같은 진단도 함께 봐야 합니다.

## 3. A national-scale hybrid model for enhanced streamflow estimation (2024)

이 논문은 DKM이라는 physically based model과 LSTM을 다섯 방식으로 비교했습니다. `LSTM-rr`은 순수 LSTM, `LSTM-pf`는 DKM 유량으로 pretraining 후 관측으로 fine-tuning, `LSTM-q`는 DKM 상태/출력을 입력 feature로 사용, `LSTM-qr`은 residual correction, `LSTM-qf`는 factor correction입니다.

핵심 결과는 `LSTM-q`가 전체 성능과 high flow, ungauged basin 일반화에서 가장 강했고, `LSTM-qr`은 low flow와 bias correction에서 강했다는 점입니다. 하지만 홍수 이벤트를 따로 봐도 peak magnitude underestimation은 여전히 남아 있었습니다.

이 논문은 우리 연구에 가장 직접적인 연결점을 줍니다. `physics-aware input`은 분명 도움이 되지만, 그것만으로는 flood peak 문제를 끝내지 못했습니다. 따라서 우리는 이 다음 단계로 `probabilistic tail modeling`과 `physics-guided core`의 추가 가치를 비교해야 합니다.

## 4. Improving streamflow simulation through machine learning-powered data integration (2025)

이 논문은 physics hybrid가 아니라 `lagged observation integration`에 초점을 둡니다. `lagged Q`와 `lagged SWE`를 LSTM 입력에 넣어 현재 basin state를 더 잘 복원하려는 접근입니다.

결과는 `lagged Q`가 매우 강했고, daily scale에서 1-day lag를 넣으면 KGE가 크게 향상됐습니다. 반면 `lagged SWE`는 daily에서는 거의 효과가 없고, monthly나 snow-dominated basin에서만 유의미했습니다.

우리 연구에 주는 시사점은, `현재 basin state recovery`가 중요하다는 점입니다. 따라서 첫 논문에서는 필수는 아니더라도, 후속 실험에서는 `lagged Q`를 강력한 입력 후보로 고려할 수 있습니다.

## 5. From RNNs to Transformers (2025 benchmark)

`From RNNs to Transformers: benchmarking deep learning architectures for hydrologic prediction (2025)`는 다양한 sequence model을 수문 예측에 비교한 벤치마크입니다. 전체 회귀 문제에서는 여전히 LSTM 계열이 가장 안정적이고, attention 계열은 high flow나 더 어려운 generalization setting에서 일부 강점을 보였습니다.

우리 연구에 주는 결론은, 첫 논문 backbone으로는 여전히 `multi-basin LSTM`이 가장 안전하다는 점입니다. 즉, 새로운 architecture 경쟁보다 `probabilistic output`과 `physics-guided extension`의 효과를 분리해서 보는 쪽이 더 좋은 연구 전략입니다.

## 6. Extrapolation / extreme-event 한계 연구들 (2024-2025)

이 축에서는 적어도 `On the need for physical constraints in deep learning rainfall-runoff projections under climate change (2024)`와 `Unveiling the limits of deep learning models in hydrological extrapolation tasks (2025)`를 함께 보는 편이 좋습니다. 공통 메시지는 stand-alone LSTM이 training distribution 바깥의 forcing이나 climate shift에서 saturation을 보이고, 큰 peak를 충분히 열지 못할 수 있다는 점입니다.

이 계열은 우리 프로젝트의 `extreme flood underestimation`을 단순 손실 함수 문제로만 보지 않게 해 줍니다. 일부 hybrid나 physical constraint가 hydrologically more plausible한 출력을 만들 수는 있었지만, 그것만으로 극한 peak 과소추정이 완전히 사라지지는 않았다는 점도 중요합니다.

우리 연구에 주는 핵심은 `peak underestimation의 중요한 원인 중 하나가 평균 회귀와 tail suppression`이라는 점입니다. 따라서 첫 번째 비교축은 `deterministic output vs probabilistic output`이 되어야 합니다.

## 현재 프로젝트에 적용해야 할 방향

첫 번째 논문은 다음의 세 모델을 비교하는 설계가 가장 적절합니다.

1. `Deterministic LSTM`
2. `LSTM + probabilistic head`
3. `LSTM + probabilistic head + physics-guided conceptual core`

이 설계의 의미는 두 가지입니다. 먼저 `probabilistic head만으로 extreme flood underestimation이 얼마나 줄어드는지`를 직접 볼 수 있습니다. 그 다음에야 `physics-guided core가 추가로 timing, generalization, peak bias를 더 줄이는가`를 검증할 수 있습니다.

즉, 현재 단계에서 가장 중요한 연구 방향은 `tail-aware output의 순수 효과를 먼저 분리해서 보고`, 그 다음 `physics-guided structure가 남는 오차를 줄이는가`로 이어가는 것입니다.

논문 서술 순서도 이 구조를 그대로 따라가는 편이 좋습니다. 즉, `CAMELS / large-sample hydrology 기반 -> LSTM baseline과 multi-basin regionalization -> physics-guided / interpretable / differentiable 흐름 -> recent hybrid critique -> probabilistic tail modeling과 extreme-event limitation` 순으로 related work를 쓰면, 현재 프로젝트의 세 모델 비교가 훨씬 자연스럽게 읽힙니다.
