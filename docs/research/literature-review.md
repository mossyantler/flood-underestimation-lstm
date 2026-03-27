# 선행연구 정리

## 연구 목표와 문제 정의

현재 프로젝트의 핵심 문제는 `다른 환경의 유역`과 `극한 홍수`에서 수문 AI 모델이 peak를 낮게 예측하는 경향입니다. 따라서 선행연구는 단순히 전체 NSE가 높은 모델을 찾는 것이 아니라, `왜 peak가 눌리는지`, `물리 지식이 실제로 도움이 되는지`, `유역 일반화에 어떤 입력과 구조가 중요한지`를 기준으로 읽어야 합니다.

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

이 논문은 다양한 sequence model을 수문 예측에 비교한 벤치마크입니다. 전체 회귀 문제에서는 여전히 LSTM 계열이 가장 안정적이고, attention 계열은 high flow나 더 어려운 generalization setting에서 일부 강점을 보였습니다.

우리 연구에 주는 결론은, 첫 논문 backbone으로는 여전히 `multi-basin LSTM`이 가장 안전하다는 점입니다. 즉, 새로운 architecture 경쟁보다 `probabilistic output`과 `physics-guided extension`의 효과를 분리해서 보는 쪽이 더 좋은 연구 전략입니다.

## 6. Extrapolation / extreme-event 한계 연구들 (2025)

이 계열 논문들은 공통적으로 stand-alone LSTM이 training distribution 바깥의 extreme forcing에서 saturation을 보이고, 큰 peak를 충분히 열지 못할 수 있다고 지적합니다. 일부 hybrid는 더 hydrologically plausible했지만, 그것만으로도 극한 peak 과소추정이 완전히 사라지지는 않았습니다.

우리 연구에 주는 핵심은 `peak underestimation의 중요한 원인 중 하나가 평균 회귀와 tail suppression`이라는 점입니다. 따라서 첫 번째 비교축은 `deterministic output vs probabilistic output`이 되어야 합니다.

## 현재 프로젝트에 적용해야 할 방향

첫 번째 논문은 다음의 세 모델을 비교하는 설계가 가장 적절합니다.

1. `Deterministic LSTM`
2. `LSTM + probabilistic head`
3. `LSTM + probabilistic head + physics-guided conceptual core`

이 설계의 의미는 두 가지입니다. 먼저 `probabilistic head만으로 extreme flood underestimation이 얼마나 줄어드는지`를 직접 볼 수 있습니다. 그 다음에야 `physics-guided core가 추가로 timing, generalization, peak bias를 더 줄이는가`를 검증할 수 있습니다.

즉, 현재 단계에서 가장 중요한 연구 방향은 `tail-aware output의 순수 효과를 먼저 분리해서 보고`, 그 다음 `physics-guided structure가 남는 오차를 줄이는가`로 이어가는 것입니다.
