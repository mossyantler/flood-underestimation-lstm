# CAMELS 모델 하이퍼파라미터 정리집

## 문서 목적

이 문서는 현재 CAMELS 프로젝트에서 사용하는 모델 하이퍼파라미터와 주요 config 파라미터를 한곳에 모아 설명한다. 목적은 각 값이 `무엇을 뜻하는지`, `왜 필요한지`, `값이 커지거나 작아지면 어떤 영향이 있는지`, `현재 프로젝트에서는 어떻게 읽어야 하는지`를 빠르게 확인할 수 있게 만드는 데 있다.

이 문서는 공식 실험 규칙을 대체하지 않는다. 공식 비교축과 실행 기준은 [`../research/experiment_protocol.md`](../research/experiment_protocol.md)를 우선한다. 다만 실험을 설계하거나 설명할 때, parameter의 의미를 정리한 참고 사전으로 쓸 수 있다.

## 다루는 범위

- 현재 Model 1, Model 2 config에 실제로 등장하는 주요 하이퍼파라미터
- 현재 broad config를 읽을 때 필요한 해석
- numeric hyperparameter와 design/config parameter의 구분
- 각 parameter가 성능, 안정성, 메모리 사용량에 주는 영향

## 다루지 않는 범위

- future-work conceptual core의 미구현 세부 하이퍼파라미터 최종값
- 최종 튜닝 결과표
- 모든 NeuralHydrology key의 전체 사전

## 상세 서술

## 1. 먼저, 하이퍼파라미터와 config 파라미터를 구분해야 한다

실무에서는 `config에 들어가는 값`을 모두 하이퍼파라미터라고 부르기도 하지만, 엄밀하게 보면 약간 나눠서 보는 편이 좋다.

첫째, `하이퍼파라미터`는 모델의 용량, 학습 속도, regularization, 입력 길이처럼 성능과 학습 동작에 직접 영향을 주는 값이다. 예를 들면 `hidden_size`, `learning_rate`, `batch_size`, `epochs`, `seq_length`가 여기에 속한다.

둘째, `설계 파라미터` 또는 `실험 조건 파라미터`는 모델이 어떤 문제를 풀고 어떤 비교를 하는지 정하는 값이다. 예를 들면 `model`, `head`, `loss`, `dynamic_inputs`, `train_basin_file`이 여기에 속한다. 이 값들도 넓게는 하이퍼파라미터처럼 취급될 수 있지만, 보통은 “튜닝”보다는 “실험 설계”의 일부로 보는 편이 자연스럽다.

이 문서에서는 두 부류를 모두 다루되, `자주 튜닝하는 값`과 `실험 조건을 고정하는 값`을 구분해서 설명한다.

---

## 2. 현재 프로젝트에서 가장 중요한 핵심 하이퍼파라미터

현재 broad config를 기준으로 보면, 우선순위가 높은 핵심 하이퍼파라미터는 아래 정도다.

| 항목 | 현재 broad 값 | 역할 |
| --- | --- | --- |
| `seed` | `111` | 실험 재현성 |
| `hidden_size` | `128` | LSTM 내부 표현 용량 |
| `initial_forget_bias` | `3` | 초기 memory retention |
| `output_dropout` | `0.3` | regularization |
| `learning_rate` | `10^{-3} \to 5 \times 10^{-4} \to 10^{-4}` | optimizer step 크기 |
| `batch_size` | `256` | 한 번에 처리하는 샘플 수 |
| `epochs` | `30` | 전체 학습 반복 수 |
| `clip_gradient_norm` | `1` | gradient explosion 방지 |
| `seq_length` | `336` | 입력 문맥 길이 |
| `predict_last_n` | `24` | supervision 구간 길이 |
| `quantiles` | `[0.5, 0.9, 0.95, 0.99]` | probabilistic output 정의 |
| `quantile_loss_weights` | `[1.0, 1.0, 1.0, 1.0]` | quantile별 loss 비중 |

이 값들은 모델의 기억 용량, 최적화 속도, 메모리 사용량, regularization 강도, flood-tail 학습 방식에 직접 영향을 준다.

---

## 3. 재현성과 실험 안정성 관련 파라미터

### 3.1 `seed`

`seed`는 난수 생성의 시작값이다. 가중치 초기화, mini-batch 순서, dropout mask 같은 랜덤 요소가 모두 이 값의 영향을 받는다.

현재 config에서는 `seed: 111`을 사용한다. 여기서 `111`이라는 숫자 자체에 특별한 의미는 없다. 중요한 것은 `같은 실험을 다시 돌렸을 때 가능한 한 비슷한 시작 조건`을 재현하도록 고정해 둔다는 점이다.

실험적으로는 seed 하나만으로 결론을 내리기보다 여러 seed를 써서 평균과 분산을 함께 보는 것이 더 바람직하다. 같은 모델이라도 seed에 따라 validation NSE나 flood metric이 조금씩 달라질 수 있기 때문이다.

### 3.2 `device`

`device`는 계산 장치를 뜻한다. 현재 broad config는 `cuda` 환경을 공식 기준으로 두고 읽는 것이 적절하다.

이 값은 성능 그 자체를 바꾸는 하이퍼파라미터는 아니지만, 실제로는 batch size, num_workers, cache 설정과 함께 실험 가능 범위를 크게 바꾸기 때문에 실험 조건 파라미터로 중요하다.

### 3.3 `num_workers`

`num_workers`는 DataLoader가 데이터를 병렬로 준비할 worker process 수다. broad config는 `4`다.

이 값이 커지면 데이터 로딩이 빨라질 수 있지만, 운영체제나 backend 조합에 따라 메모리 사용량이 급격히 커지거나 serialization overhead가 생길 수 있다. 따라서 broad 실험에서는 하드웨어와 backend에 맞게 조정하되, 공식 비교에서는 두 모델에 같은 조건을 적용하는 것이 중요하다.

---

## 4. 모델 용량과 memory 관련 하이퍼파라미터

### 4.1 `hidden_size`

`hidden_size`는 LSTM hidden state의 차원 수다. 가장 쉬운 비유로는 `LSTM이 내부적으로 쓰는 메모장의 크기`라고 보면 된다.

현재 broad config는 `128`을 쓴다. 값이 커지면 모델이 더 복잡한 시계열 패턴과 basin-dependent interaction을 담을 수 있지만, 그만큼 파라미터 수와 메모리 사용량도 증가한다. 값이 작아지면 계산은 가벼워지지만, 표현력이 부족해져 underfitting이 생길 수 있다.

수문학적으로는 antecedent wetness, snow/soil memory, routing memory, static attribute와 dynamic forcing의 상호작용을 hidden state 안에 얼마나 풍부하게 담을 수 있느냐와 연결된다.

### 4.2 `initial_forget_bias`

`initial_forget_bias`는 LSTM forget gate bias의 초기값이다. 현재 프로젝트에서는 `3`을 쓴다.

forget gate는 대략

$$
f_t = \sigma(z_t)
$$

형태로 계산되며, 초기 bias가 $3$이면

$$
\sigma(3) \approx 0.95
$$

라서 학습 초기에 이전 memory를 꽤 강하게 유지하는 방향으로 시작하게 된다.

이 값이 중요한 이유는 현재 시계열 길이가 $336$시간으로 길기 때문이다. antecedent wetness나 storage memory 같은 장기 문맥을 잡으려면, 모델이 초기에 과거 정보를 너무 빨리 버리지 않는 편이 유리할 수 있다.

값을 더 크게 주면 초기에 memory retention이 더 강해질 수 있지만, 너무 크면 오래된 정보에 과하게 매달릴 위험도 있다. 반대로 `0`에 가깝게 두면 일반적인 초기화와 비슷해지지만, 긴 시계열에서 gradient flow와 long-memory 학습이 다소 불리할 수 있다.

현재 프로젝트에서 이 값 `3`은 “이론적으로 유일한 정답”이라기보다, vendored NeuralHydrology 예제들이 폭넓게 쓰는 경험적 안전값을 따른 것이다.

### 4.3 `output_dropout`

`output_dropout`은 head 앞에 적용하는 dropout 비율이다. broad config는 `0.3`이다.

이 값은 학습 중 일부 hidden representation을 랜덤하게 꺼서, 모델이 특정 feature나 hidden unit에 과도하게 의존하지 않도록 한다. 값이 너무 작으면 regularization 효과가 약하고, 너무 크면 필요한 정보까지 너무 많이 지워서 성능이 떨어질 수 있다.

현재 broad config에서 `0.3`을 쓰는 것은 `hidden_size = 128` 수준의 모델 용량에 맞춰 regularization을 함께 주는 선택으로 읽을 수 있다.

---

## 5. 최적화 관련 하이퍼파라미터

### 5.1 `optimizer`

`optimizer`는 gradient를 이용해 가중치를 갱신하는 방법이다. 현재 프로젝트는 `Adam`을 사용한다.

이 값은 숫자형 하이퍼파라미터는 아니지만, 학습 동작을 크게 바꾸는 설계 선택이다. Adam은 일반적으로 시계열 예측과 deep learning에서 안정적으로 많이 쓰이는 optimizer다.

### 5.2 `learning_rate`

`learning_rate`는 한 번의 update에서 가중치를 얼마나 크게 움직일지를 정하는 값이다. broad config는 아래 schedule을 쓴다.

$$
10^{-3} \rightarrow 5 \times 10^{-4} \rightarrow 10^{-4}
$$

즉 학습 초반에는 큰 보폭으로 빠르게 방향을 잡고, 후반에는 더 작은 보폭으로 세밀하게 조정한다.

learning rate가 너무 크면 loss가 튀거나 발산할 수 있다. 반대로 너무 작으면 학습이 지나치게 느려지고 local optimum 근처에서 답답하게 움직일 수 있다. 현재처럼 단계적으로 줄이는 schedule은 수문 시계열 학습에서 비교적 무난한 선택이다.

### 5.3 `batch_size`

`batch_size`는 한 번의 optimizer update 전에 몇 개의 학습 샘플을 묶어서 처리할지를 뜻한다. broad config는 `256`이다.

여기서 중요한 점은 이 값이 “256개 basin”을 뜻하는 것이 아니라, “256개 학습 window”를 뜻한다는 점이다. 현재 모델은 basin 전체를 한 번에 넣는 것이 아니라 `seq_length = 336` 형태의 시계열 샘플들을 잘라 학습한다.

값이 커지면 gradient가 더 안정적이고 GPU 활용이 좋아질 수 있지만, 메모리 사용량이 증가한다. 값이 작아지면 메모리는 절약되지만 gradient noise가 커질 수 있다.

### 5.4 `epochs`

`epochs`는 학습 데이터를 몇 번 반복해서 볼지를 정하는 값이다. broad config는 `30`이다.

값이 너무 작으면 충분히 학습하지 못해 underfitting이 날 수 있고, 너무 크면 training set에 과하게 맞춰져 overfitting 위험이 커진다. 따라서 epoch 수는 validation metric과 함께 해석해야 한다.

### 5.5 `clip_gradient_norm`

`clip_gradient_norm`은 gradient explosion을 막기 위한 안전장치다. 현재 broad config는 `1`을 쓴다.

LSTM은 긴 시퀀스를 다룰 때 gradient가 커질 수 있는데, 이 값을 주면 gradient norm이 특정 크기를 넘을 때 잘라서 학습을 더 안정화한다. 값이 너무 작으면 학습이 과도하게 보수적이 될 수 있고, 너무 크면 clipping 효과가 약해질 수 있다.

---

## 6. 입력 문맥과 예측 horizon 관련 하이퍼파라미터

### 6.1 `seq_length`

`seq_length`는 모델이 한 샘플에서 읽는 입력 시계열 길이다. 현재 값은 `336`이다.

즉 모델은 최근 $336$시간, 약 14일의 forcing과 basin 문맥을 보고 예측한다. 이 값이 중요한 이유는 홍수 반응이 직전 몇 시간 강수만으로 결정되지 않기 때문이다. antecedent wetness, soil storage, snow memory, routing memory가 모두 영향을 준다.

값을 더 늘리면 더 긴 기억을 볼 수 있지만, 메모리 사용량과 계산량도 커진다. 너무 줄이면 장기 문맥을 놓칠 수 있다.

### 6.2 `predict_last_n`

`predict_last_n`은 입력 시퀀스 중 마지막 몇 시간에 대해 loss와 metric을 계산할지를 정한다. 현재 값은 `24`다.

즉 현재 모델은 사실상 “최근 14일을 보고 마지막 24시간의 유량 시계열을 맞히는 구조”라고 이해하면 된다. 값이 커지면 더 긴 horizon을 직접 supervision하게 되지만, 문제 난이도도 커질 수 있다.

### 6.3 `dynamic_inputs`, `static_attributes`, `target_variables`

이 셋은 strict한 의미의 numeric hyperparameter는 아니지만, 입력과 출력 문제 정의를 정하는 매우 중요한 설계 파라미터다.

- `dynamic_inputs`: 어떤 forcing 변수를 모델에 넣을지 정한다.
- `static_attributes`: basin 구조를 나타내는 정적 속성을 정한다.
- `target_variables`: 무엇을 예측할지를 정한다.

이 값들을 바꾸면 사실상 “다른 문제를 푸는 모델”이 되므로, 비교 실험에서는 가급적 고정하는 것이 중요하다.

### 6.4 `clip_targets_to_zero`

`clip_targets_to_zero`는 특정 target이 음수가 되지 않도록 제한하는 설정이다. 현재는 `Streamflow`에 적용한다.

유량은 물리적으로 음수가 될 수 없기 때문에, 이 설정은 수문학적 일관성을 유지하는 간단한 안전장치다.

---

## 7. probabilistic model 전용 하이퍼파라미터

### 7.1 `head`

`head`는 출력층의 종류를 정한다. 현재는 `regression`과 `quantile`을 사용한다.

이 값은 단순한 구현 옵션이 아니라 연구 질문 자체를 바꾸는 설계 파라미터다. `regression`은 point estimate 하나를 내고, `quantile`은 여러 분위수를 동시에 낸다.

### 7.2 `loss`

현재 baseline은 `nse`, probabilistic model은 `pinball`을 사용한다.

`loss`는 모델이 무엇을 잘하도록 학습할지를 직접 정하는 값이다. 같은 모델 구조라도 loss를 바꾸면 학습 목표 자체가 달라진다.

### 7.3 `quantiles`

`quantiles`는 어떤 분위수를 예측할지 정한다. 현재 값은

$$
[0.5,\; 0.9,\; 0.95,\; 0.99]
$$

다.

$q_{0.50}$은 중심선, $q_{0.90}$, $q_{0.95}$, $q_{0.99}$는 upper tail 응답을 본다. quantile 개수를 더 늘리면 분포를 더 촘촘하게 볼 수 있지만, 학습과 해석이 복잡해질 수 있다.

### 7.4 `quantile_loss_weights`

현재 값은

$$
[1.0,\; 1.0,\; 1.0,\; 1.0]
$$

이다.

이는 각 quantile의 pinball loss를 같은 비중으로 합친다는 뜻이다. tail quantile에 더 큰 가중치를 줄 수도 있지만, 현재 프로젝트는 first comparison에서 `head 구조 효과`를 먼저 분리하고 싶기 때문에 equal weight를 쓴다.

이 값을 바꾸면 “같은 quantile model”이라도 학습이 어느 분위수에 더 집중하는지가 달라진다.

---

## 8. 검증과 평가 관련 파라미터

### 8.1 `validate_every`

`validate_every`는 몇 epoch마다 validation을 돌릴지 정한다. 현재 값은 `1`이다.

즉 매 epoch마다 validation metric을 확인한다는 뜻이다. 값이 커지면 validation 비용은 줄지만, 학습 상태를 촘촘히 보기는 어려워진다.

### 8.2 `validate_n_random_basins`

이 값은 validation 시 몇 개 basin을 랜덤하게 뽑아 평가할지를 정한다. broad config는 `200`이다.

validation 전체를 다 돌리면 시간이 오래 걸릴 수 있으므로, 일부 basin만 샘플링해 빠르게 상태를 보는 용도로 쓴다. 값이 작으면 validation noise가 커질 수 있고, 값이 크면 더 안정적이지만 평가 비용이 증가한다.

### 8.3 `metrics`

`metrics`는 validation/test에서 framework가 직접 계산할 built-in metric 목록이다. 현재는 `NSE`, `KGE`, `FHV`, `Peak-Timing`, `Peak-MAPE`를 쓴다.

이 값은 튜닝 하이퍼파라미터라기보다 보고와 모니터링 파라미터다. 다만 어떤 metric을 모니터링하느냐에 따라 실험 해석 방향이 달라질 수 있으므로 중요하다.

### 8.4 `cache_validation_data`

validation 데이터를 메모리에 캐시할지 여부다. broad config는 `True`다.

값을 `True`로 두면 validation이 빨라질 수 있지만 메모리 사용량이 증가한다. 따라서 이 설정은 broad 실험을 돌릴 하드웨어 메모리와 함께 해석해야 한다.

---

## 9. 로깅과 산출물 관련 파라미터

### 9.1 `experiment_name`

실험 이름이다. 성능 자체를 바꾸는 값은 아니지만, run artifact를 관리하는 데 중요하다.

### 9.2 `run_dir`

실험 출력이 저장되는 경로다. 현재는 `./runs`를 사용한다.

### 9.3 `log_interval`

학습 로그를 몇 step마다 찍을지 정한다. 현재 값은 `20`이다.

### 9.4 `log_tensorboard`

TensorBoard 로그를 남길지 여부다. broad config는 `True`다.

### 9.5 `log_n_figures`

로그로 저장할 figure 개수다. 현재는 `0`이다.

### 9.6 `save_all_output`

test 시점의 full output을 저장할지 여부다. broad config는 `True`다.

probabilistic model에서는 coverage나 calibration을 계산하려면 full output이 필요하므로, Model 2 broad 실험에서는 이 값을 `True`로 두는 것이 자연스럽다.

### 9.7 `save_weights_every`

몇 epoch마다 가중치를 저장할지 정한다. broad config는 `1`이다.

값이 작으면 checkpoint를 더 자주 남길 수 있지만 저장 공간을 더 쓴다.

### 9.8 `save_validation_results`, `save_train_data`

validation 예측 결과나 train data를 별도로 저장할지 여부다. 현재는 대부분 `False`다. 디버깅이나 상세 분석에는 유용할 수 있지만, 저장공간과 I/O 부담이 커질 수 있다.

---

## 10. 이 프로젝트에서 우선적으로 튜닝할 만한 값

모든 parameter를 한꺼번에 튜닝하면 해석이 어려워진다. 현재 프로젝트 기준으로 우선순위를 나누면 아래처럼 보는 것이 합리적이다.

### 10.1 먼저 고정해야 하는 값

비교 실험에서는 “어떤 값을 튜닝할 수 있는가”보다 “어떤 값을 절대 바꾸면 안 되는가”를 먼저 정해야 한다. 현재 프로젝트의 공식 규칙은 [`../research/experiment_protocol.md`](../research/experiment_protocol.md)의 `Model 1 vs Model 2 공식 통제변인` 섹션을 따른다.

핵심은 아래와 같다.

- `dataset`, `data_dir`, basin split file, time split 날짜 경계는 고정한다.
- `dynamic_inputs`, `static_attributes`, `target_variables`는 고정한다.
- `model`, `hidden_size`, `initial_forget_bias`, `output_dropout`, `optimizer`, `learning_rate`, `batch_size`, `epochs`, `seq_length`, `predict_last_n`은 고정한다.
- 공식 보고는 single seed가 아니라 `seeds = [111, 222, 333]`의 다중 seed 평균을 기준으로 한다.

즉 Model 1과 Model 2 비교에서 바뀌는 값은 원칙적으로 `head`, `loss`, `quantiles`, `quantile_loss_weights`뿐이다. 나머지까지 함께 바꾸면 probabilistic head의 순수 효과를 해석하기 어려워진다.

### 10.2 baseline 안정화에 가장 중요한 값

- `seed`
- `learning_rate`
- `batch_size`
- `epochs`
- `hidden_size`
- `seq_length`
- `clip_gradient_norm`

이 값들은 학습 안정성과 일반화 성능에 가장 직접적으로 영향을 준다.

### 10.3 probabilistic model에서 추가로 중요한 값

- `quantiles`
- `quantile_loss_weights`
- `save_all_output`

이 값들은 tail modeling과 uncertainty evaluation에 직접 연결된다.

### 10.4 로컬 안전 실행에서 특히 중요한 값

- `num_workers`
- `cache_validation_data`
- `max_updates_per_epoch`
- `batch_size`

이 값들은 성능 그 자체보다도, 현재 하드웨어에서 `실험이 끝까지 도는가`를 크게 좌우한다.

---

## 11. 빠른 해석 메모

아래는 자주 헷갈리는 값을 한 줄씩 빠르게 읽는 메모다.

| 키 | 한 줄 해석 |
| --- | --- |
| `seed` | 랜덤 시작점이다. 재현성을 위해 고정한다. |
| `hidden_size` | LSTM 메모장의 크기다. |
| `initial_forget_bias` | 처음부터 과거 정보를 얼마나 오래 붙잡게 할지 정한다. |
| `output_dropout` | overfitting을 막기 위해 일부 표현을 랜덤하게 끈다. |
| `learning_rate` | 가중치를 한 번에 얼마나 움직일지 정한다. |
| `batch_size` | 한 번 업데이트 전에 몇 샘플을 묶을지 정한다. |
| `epochs` | 전체 데이터를 몇 바퀴 반복해서 볼지 정한다. |
| `seq_length` | 과거를 몇 시간까지 문맥으로 볼지 정한다. |
| `predict_last_n` | 마지막 몇 시간을 실제 예측 구간으로 삼을지 정한다. |
| `quantiles` | 어떤 분위수들을 출력할지 정한다. |
| `quantile_loss_weights` | 어느 quantile에 더 집중해서 학습할지 정한다. |

---

## 12. 문서형 설명으로 옮길 때의 권장 표현

발표나 계획서에서 parameter를 설명할 때는 값만 말하지 말고, 아래처럼 `역할 + 이유`를 같이 말하는 편이 좋다.

- `hidden_size = 128`은 LSTM의 내부 표현 용량을 정하는 값이며, 현재는 충분한 표현력과 과도한 메모리 사용 사이의 타협값으로 둔다.
- `seq_length = 336`은 약 14일 문맥을 사용한다는 뜻이며, antecedent wetness와 storage memory를 반영하기 위한 설정이다.
- `predict_last_n = 24`는 마지막 24시간을 supervision 대상으로 삼는다는 뜻이며, 결과적으로 최근 14일을 보고 다음 24시간을 맞히는 구조로 이해할 수 있다.
- `initial_forget_bias = 3`은 학습 초기에 과거 정보를 너무 빨리 잊지 않게 해 long-memory 학습과 gradient flow를 돕기 위한 값이다.

즉 parameter 설명에서는 `숫자 자체`보다 `그 숫자가 어떤 학습 행동을 유도하는가`를 먼저 말하는 것이 중요하다.

## 문서 정리

이 문서는 현재 CAMELS 프로젝트에서 자주 등장하는 하이퍼파라미터와 config 파라미터를 한 번에 정리한 참고 사전이다. 핵심은 `이 값이 무엇을 뜻하는가`, `왜 필요한가`, `값이 바뀌면 어떤 영향이 생기는가`를 실험 문맥 안에서 연결해 이해하는 데 있다.

현재 프로젝트에서 가장 중요한 값은 `hidden_size`, `learning_rate`, `batch_size`, `epochs`, `seq_length`, `predict_last_n`, `quantiles`, `quantile_loss_weights`다. 반면 `model`, `head`, `loss`, split file 같은 값은 단순 튜닝 항목이 아니라, 비교 실험의 설계 조건으로 더 엄격하게 다뤄야 한다.

## 관련 문서

- [`../research/experiment_protocol.md`](../research/experiment_protocol.md): 공식 config key 대응과 실행 규칙
- [`research-plan-extreme-flood-underestimation.md`](research-plan-extreme-flood-underestimation.md): 현재 연구계획서 초안
- [`research-proposal-submission-draft.md`](research-proposal-submission-draft.md): 제출용 연구계획서 초안
