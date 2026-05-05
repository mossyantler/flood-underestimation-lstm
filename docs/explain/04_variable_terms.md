# 04. 변수와 용어 해설

이 문서는 CAMELS 연구 문서에서 자주 나오는 용어를 짧게 풀어 쓴 사전이다. technical term은 그대로 두되, 처음 보는 사람이 의미를 잡을 수 있도록 설명을 붙였다.

## 연구와 데이터 용어

| 용어 | 쉬운 설명 |
| --- | --- |
| basin | 비가 내려 한 하천 출구로 모이는 땅의 범위다. 한국어로는 유역이라고 부른다. |
| outlet | 유역의 물이 관측소로 모여 나가는 지점이다. 이 연구에서는 DRBC 안팎을 판단하는 중요한 기준점이다. |
| DRBC | Delaware River Basin Commission 기준 Delaware River Basin이다. 현재 연구의 holdout 평가 지역이다. |
| CAMELSH | 시간 단위 수문·기상·유역 특성을 제공하는 large-sample hydrology dataset이다. |
| hourly | 자료 간격이 1시간이라는 뜻이다. 이 연구는 daily가 아니라 hourly 예측을 기본으로 한다. |
| streamflow | 하천 유량이다. 모델이 최종적으로 맞히려는 target이다. |
| forcing | 유역에 작용하는 외부 조건이다. 이 연구에서는 주로 강수, 기온, 복사, 습도 같은 기상 입력을 뜻한다. |
| static attributes | 유역 면적, 경사, 토양, 산림 비율처럼 시간에 따라 거의 고정된 유역 특성이다. |
| dynamic inputs | 시간마다 달라지는 입력 변수다. 강수와 기온 같은 forcing이 여기에 들어간다. |
| target variable | 모델이 예측해야 하는 값이다. 여기서는 `Streamflow`다. |
| return period | 평균적으로 몇 년에 한 번 넘을 정도의 크기인지를 나타내는 표현이다. 예를 들어 100-year event는 매년 초과확률이 약 1%인 event를 뜻한다. |
| AEP | Annual Exceedance Probability의 약자다. 100년 빈도 event는 보통 1% AEP event라고 부른다. |
| ARI | Average Recurrence Interval의 약자다. return period와 비슷한 뜻으로 쓰이며, NOAA Atlas 14에서는 average recurrence interval 표현을 자주 쓴다. |
| prec_ari100_24h | 24시간 기준 100년 빈도 강수량이다. `prec`는 precipitation의 짧은 표기다. `P100_24h`라고 쓸 수도 있지만, 이 프로젝트에서는 `Q99/q99`와 헷갈리지 않게 `prec_ari100_24h` 표기를 권장한다. |
| flood_ari100 | 100년 빈도 홍수량 또는 1% AEP flood magnitude다. `Q100`이라고 쓸 수도 있지만, 이 프로젝트에서는 `flood_ari100` 표기를 권장한다. |
| return-period proxy | 공식 NOAA/USGS 재현기간 자료가 아니라, 현재 가진 CAMELSH hourly record에서 임시로 추정한 참고값이다. 공식값처럼 주장하지 않기 위해 source와 confidence flag를 같이 남긴다. |
| Gumbel annual-maxima proxy | water year마다 최대값을 하나씩 뽑고 Gumbel 극값분포를 맞춰 재현기간 값을 추정하는 간단한 방법이다. 현재 서버 all-basin 분석의 기본 reference 계산법이다. |

## 모델 용어

| 용어 | 쉬운 설명 |
| --- | --- |
| LSTM | 과거 정보를 기억하면서 시간 순서 자료를 읽는 neural network다. |
| backbone | 모델의 공통 몸통이다. 이 연구에서는 두 모델 모두 LSTM backbone을 공유한다. |
| head | backbone이 만든 정보를 실제 예측값으로 바꾸는 마지막 출력층이다. |
| deterministic model | 한 시점에 유량 하나만 예측하는 모델이다. Model 1이 여기에 해당한다. |
| probabilistic model | 가능한 범위나 불확실성을 함께 표현하는 모델이다. Model 2는 quantile 방식으로 이를 구현한다. |
| regression head | 유량 하나를 출력하는 head다. |
| quantile head | `q50`, `q90`, `q95`, `q99`처럼 여러 quantile을 출력하는 head다. |
| q50 | 중앙값에 가까운 예측선이다. Model 2의 대표 중앙 예측으로 쓴다. |
| q90, q95, q99 | 더 높은 쪽의 유량 가능성을 나타내는 예측선이다. 홍수 첨두를 감싸는지 볼 때 중요하다. |
| quantile crossing | 예를 들어 `q95`가 `q90`보다 낮아지는 문제다. 현재 구현은 이런 일이 생기지 않게 설계한다. |
| pinball loss | quantile을 학습할 때 쓰는 loss다. 상위 quantile에서는 실제 큰 값을 너무 낮게 예측하면 더 크게 벌을 준다. |
| NSE loss | 수문 모델에서 자주 쓰는 성능 기준인 NSE를 학습 목표로 쓰는 방식이다. |

## 실험 용어

| 용어 | 쉬운 설명 |
| --- | --- |
| train | 모델이 실제로 배우는 자료 구간 또는 유역 집합이다. |
| validation | 학습 중 어느 epoch를 선택할지 판단하는 점검 구간이다. test 대신 validation으로 모델 선택을 해야 공정하다. |
| test | 최종 성능을 보고하는 평가 구간이다. 모델 선택에 쓰면 안 된다. |
| holdout | 일부 자료나 지역을 학습에서 빼고 마지막 평가에만 쓰는 방식이다. |
| regional holdout | 특정 지역 전체를 학습에서 빼고 평가하는 방식이다. 이 연구에서는 DRBC가 regional holdout이다. |
| temporal split | 같은 유역에서 기간을 나눠 학습과 평가를 하는 방식이다. |
| basin holdout | 학습에 쓰지 않은 유역에서 평가하는 방식이다. |
| extreme-event holdout | 큰 홍수 event 일부를 학습에서 제외하고, 모델이 그 event를 얼마나 잘 예측하는지 보는 방식이다. |
| seed | 난수 시작값이다. seed가 다르면 같은 설정에서도 결과가 조금 달라질 수 있다. 현재 paired final comparison은 `111`, `222`, `444`를 기준으로 한다. Model 2 seed `333`은 NaN loss로 실패했고, 공정한 비교를 위해 Model 1 seed `333`도 final aggregate에서 제외한다. |
| scaling pilot | basin 수를 100, 300, 600으로 줄여 보며 계산 비용과 대표성을 확인한 운영 실험이다. 현재 main comparison은 300개 subset을 쓴다. |

## 유역 특성 변수

| 변수 | 쉬운 설명 |
| --- | --- |
| area | 유역 면적이다. 같은 유량이라도 큰 유역과 작은 유역에서 의미가 다르므로 중요하다. |
| slope | 유역 평균 경사다. 클수록 물이 빨리 모일 가능성이 커진다. |
| aridity | 건조도를 나타낸다. 강수와 증발산의 균형을 이해하는 데 쓴다. |
| snow_fraction 또는 frac_snow | 강수 중 snow와 관련된 비중이다. snowmelt나 rain-on-snow 가능성을 볼 때 중요하다. |
| soil_depth | 토양 깊이다. 깊을수록 물을 저장할 공간이 커질 수 있다. |
| permeability | 물이 토양이나 지층으로 스며드는 쉬운 정도다. 클수록 직접유출이 줄 수 있다. |
| forest_fraction | 산림 비율이다. 식생과 토양 저장 효과를 통해 홍수 반응을 완충할 수 있다. |
| baseflow_index | 전체 유량 중 지하수성 흐름의 비중을 나타내는 지표다. 낮으면 빠른 반응 유역일 가능성이 있다. |
| stream_density | 단위 면적당 하천 길이다. 높으면 물이 하천망으로 빨리 연결될 수 있다. |
| high_prec_freq | 강한 강수가 얼마나 자주 나타나는지 나타낸다. |
| high_prec_dur | 강한 강수가 한 번 올 때 얼마나 오래 지속되는지 나타낸다. |

## 평가 지표

| 지표 | 쉬운 설명 |
| --- | --- |
| NSE | 전체 유량 시계열을 얼마나 잘 맞췄는지 보는 대표 수문 성능 지표다. 값이 클수록 좋다. |
| KGE | 상관, 평균, 변동성을 함께 보는 지표다. NSE 하나만 볼 때 놓치는 부분을 보완한다. |
| NSElog | 작은 유량 구간까지 포함해 안정적으로 보는 지표다. 홍수만 좋아지고 평소 유량이 무너졌는지 확인하는 데 쓴다. |
| FHV | 큰 유량 구간을 전반적으로 높게 또는 낮게 예측했는지 보는 지표다. |
| Peak Relative Error | 홍수 첨두를 실제보다 얼마나 높게 또는 낮게 예측했는지 본다. 이 연구의 핵심 지표다. |
| Peak Timing Error | 홍수 첨두가 나타나는 시간을 얼마나 잘 맞췄는지 본다. |
| top 1% flow recall | 실제로 가장 큰 1% 유량 시점을 모델이 얼마나 놓치지 않았는지 본다. |
| event-level RMSE | 홍수 event 전체 모양을 얼마나 잘 따라갔는지 보는 오차다. |
| coverage | 예를 들어 `q95` 아래에 실제값이 약 95% 들어오는지 보는 지표다. |
| calibration | 모델이 말한 확률 수준과 실제 빈도가 잘 맞는지 보는 진단이다. |
| pinball loss | quantile 예측의 품질을 보는 loss다. 작을수록 좋다. |

## 식으로 보는 평가지표

아래 식에서 \(y_t\)는 시간 \(t\)의 실제 관측 유량이고, \(\hat{y}_t\)는 모델 예측 유량이다. Model 1에서는 \(\hat{y}_t = \hat{Q}_t\)이고, Model 2를 point prediction처럼 비교할 때는 보통 \(\hat{y}_t = q50_t\)로 둔다. \(T\)는 평가에 쓰는 전체 시간 수, \(\bar{y}\)는 관측 유량 평균이다.

### NSE

NSE는 관측 평균만 계속 예측하는 단순한 기준보다 모델이 얼마나 나은지 보는 지표다.

$$
\mathrm{NSE}
= 1 -
\frac{\sum_{t=1}^{T}(y_t-\hat{y}_t)^2}
{\sum_{t=1}^{T}(y_t-\bar{y})^2}
$$

값이 1에 가까울수록 좋다. 0이면 관측 평균만 쓰는 것과 비슷하고, 0보다 작으면 그보다도 못하다는 뜻이다.

### KGE

KGE는 상관, 변동성, 평균 bias를 한 번에 보는 지표다.

$$
\mathrm{KGE}
= 1 -
\sqrt{(r-1)^2 + (\alpha-1)^2 + (\beta-1)^2}
$$

여기서 \(r\)은 관측과 예측의 상관계수, \(\alpha\)는 표준편차 비율, \(\beta\)는 평균 비율이다.

$$
\alpha = \frac{\sigma_{\hat{y}}}{\sigma_y},
\qquad
\beta = \frac{\mu_{\hat{y}}}{\mu_y}
$$

KGE도 1에 가까울수록 좋다. NSE가 전체 오차 크기에 민감하다면, KGE는 "흐름의 모양, 변동성, 평균 수준이 같이 맞는가"를 더 균형 있게 본다.

### NSElog

NSElog는 유량에 log를 씌운 뒤 NSE를 계산한다. 작은 유량 구간도 너무 묻히지 않게 보려는 지표다.

$$
\mathrm{NSElog}
= 1 -
\frac{\sum_{t=1}^{T}\left[\log(y_t+\epsilon)-\log(\hat{y}_t+\epsilon)\right]^2}
{\sum_{t=1}^{T}\left[\log(y_t+\epsilon)-\overline{\log(y+\epsilon)}\right]^2}
$$

\(\epsilon\)은 0 유량에서 log가 깨지는 것을 막기 위해 더하는 아주 작은 값이다. 이 지표는 홍수 예측이 좋아지는 대신 평소 유량 예측이 무너지는지 확인할 때 유용하다.

### FHV

FHV는 high-flow 구간에서 예측 유량 총량이 실제보다 얼마나 높거나 낮은지 보는 지표다. \(H\)를 관측 유량이 큰 시간들의 집합이라고 두면, 예를 들어 관측 상위 2% 또는 분석에서 정한 high-flow set을 쓸 수 있다.

$$
\mathrm{FHV}
=
100 \times
\frac{\sum_{t \in H}(\hat{y}_t-y_t)}
{\sum_{t \in H}y_t}
$$

FHV가 음수이면 큰 유량을 전반적으로 낮게 예측했다는 뜻이고, 양수이면 크게 예측했다는 뜻이다.

### Peak Relative Error

Peak Relative Error는 event 단위로 실제 첨두와 예측 첨두의 차이를 보는 지표다. event \(e\) 안에서 실제 첨두를 \(Q^{\mathrm{peak}}_e\), 예측 첨두를 \(\hat{Q}^{\mathrm{peak}}_e\)라고 두면 다음과 같다.

$$
\mathrm{PRE}_e
=
100 \times
\frac{\hat{Q}^{\mathrm{peak}}_e - Q^{\mathrm{peak}}_e}
{Q^{\mathrm{peak}}_e}
$$

값이 음수이면 첨두를 낮게 예측한 것이고, 양수이면 높게 예측한 것이다. 이 연구에서는 음수 방향의 bias, 즉 peak underestimation이 특히 중요하다.

### Peak Timing Error

Peak Timing Error는 event 안에서 실제 첨두가 발생한 시간과 예측 첨두가 발생한 시간의 차이다.

$$
\mathrm{PTE}_e
=
\hat{t}^{\mathrm{peak}}_e - t^{\mathrm{peak}}_e
$$

단위는 보통 hour다. 부호를 유지하면 예측이 실제보다 빠른지 늦은지 볼 수 있고, 절댓값 \(|\mathrm{PTE}_e|\)을 쓰면 얼마나 어긋났는지만 볼 수 있다.

### top 1% flow recall

top 1% flow recall은 실제로 매우 큰 유량이 나온 시간들을 모델이 얼마나 놓치지 않았는지 보는 지표다. 관측 유량의 99% 분위 기준값을 \(Q_{0.99}\)라고 두면,

$$
H_{1\%} = \{t \mid y_t \ge Q_{0.99}\}
$$

이고, 같은 기준 이상으로 예측한 시간 집합을

$$
\hat{H}_{1\%} = \{t \mid \hat{y}_t \ge Q_{0.99}\}
$$

라고 둘 수 있다. 그러면 recall은 다음과 같다.

$$
\mathrm{Recall}_{1\%}
=
\frac{|H_{1\%} \cap \hat{H}_{1\%}|}
{|H_{1\%}|}
$$

값이 클수록 실제 극한 유량 시점을 덜 놓친다는 뜻이다. Model 2에서는 \(\hat{y}_t\) 자리에 `q50`, `q95`, `q99`를 각각 넣어 비교할 수 있다.

### event-level RMSE

event-level RMSE는 하나의 flood event 전체 모양을 얼마나 잘 따라갔는지 보는 오차다. event \(e\)에 포함된 시간 집합을 \(T_e\)라고 두면,

$$
\mathrm{RMSE}_e
=
\sqrt{
\frac{1}{|T_e|}
\sum_{t \in T_e}(y_t-\hat{y}_t)^2
}
$$

첨두 한 점만 맞췄는지가 아니라, rising limb와 recession까지 포함한 event 전체 hydrograph를 보는 데 유용하다.

### pinball loss

Pinball loss는 quantile 예측에 쓰는 loss다. quantile level을 \(\tau\), 그 quantile 예측값을 \(q_{\tau,t}\)라고 두면,

$$
L_{\tau}(y_t, q_{\tau,t})
=
\max\left(
\tau (y_t-q_{\tau,t}),
(\tau-1)(y_t-q_{\tau,t})
\right)
$$

여러 quantile을 함께 쓰면 시간과 quantile에 대해 평균 또는 가중평균을 낸다.

$$
L_{\mathrm{pinball}}
=
\frac{1}{T}
\sum_{t=1}^{T}
\sum_{\tau \in \mathcal{Q}}
w_{\tau} L_{\tau}(y_t, q_{\tau,t})
$$

현재 Model 2의 quantile set은 \(\mathcal{Q}=\{0.5, 0.9, 0.95, 0.99\}\)이고, 기본 가중치 \(w_{\tau}\)는 모두 같다.

### coverage

Coverage는 예측한 quantile 아래에 실제값이 얼마나 자주 들어오는지 보는 값이다.

$$
\mathrm{Coverage}_{\tau}
=
\frac{1}{T}
\sum_{t=1}^{T}
\mathbf{1}(y_t \le q_{\tau,t})
$$

예를 들어 `q95`의 coverage가 0.95에 가까우면, `q95`라는 이름에 맞게 실제값의 약 95%를 그 아래에 담고 있다는 뜻이다.

### calibration error

Calibration은 목표 quantile level과 실제 coverage가 얼마나 가까운지 본다. 간단한 요약값은 다음처럼 쓸 수 있다.

$$
\mathrm{CalibrationError}
=
\frac{1}{|\mathcal{Q}|}
\sum_{\tau \in \mathcal{Q}}
\left|
\mathrm{Coverage}_{\tau} - \tau
\right|
$$

값이 작을수록 모델이 말한 확률 수준과 실제 빈도가 잘 맞는다. 다만 coverage만 좋고 `q99-q50` 같은 예측 폭이 너무 넓으면 실용성이 떨어질 수 있으므로, interval width도 함께 봐야 한다.

### quantile interval width

Model 2의 upper-tail 폭은 중심선보다 위쪽 가능성을 얼마나 열어 두는지 보여준다.

$$
\mathrm{Width}_{95,t} = q95_t - q50_t,
\qquad
\mathrm{Width}_{99,t} = q99_t - q50_t
$$

홍수 구간에서 이 폭이 커지면 모델이 큰 유량 상황에서 상방 불확실성을 더 크게 보고 있다는 뜻이다. 하지만 폭이 크기만 하고 calibration이 나쁘면 좋은 예측이라고 보기 어렵다.

## event 분석 용어

| 용어 | 쉬운 설명 |
| --- | --- |
| flood event | 유량이 일정 기준 이상으로 커지는 하나의 독립 홍수 사건이다. |
| Q99 | 한 basin의 시간별 유량 중 상위 1%에 해당하는 기준값이다. |
| inter-event separation | 두 peak를 독립 event로 볼지 판단하는 최소 시간 간격이다. 현재 기본값은 72시간이다. |
| rain event | 유량이 아니라 강수량 기준으로 잡은 event다. 극한호우 stress test에서는 hourly `Rainf`의 rolling sum이 ARI 기준을 넘는 시간을 먼저 찾는다. |
| rolling precipitation | 1시간, 6시간, 24시간, 72시간처럼 움직이는 시간창 안의 누적 강수량이다. 같은 비라도 짧게 몰아서 오면 1시간/6시간 값이 커지고, 오래 이어지면 24시간/72시간 값이 커진다. |
| annual peak | 한 해에서 가장 큰 유량이다. |
| unit-area peak | peak discharge를 유역 면적으로 나눈 값이다. 서로 다른 면적의 유역을 비교하기 위해 쓴다. |
| RBI | hydrograph가 얼마나 급격하게 오르내리는지 나타내는 flashiness 지표다. |
| event runoff coefficient | event 동안 내린 비 중 얼마나 유출로 나타났는지를 나타내는 비율이다. |
| recent rainfall | event peak 직전 6시간, 24시간, 72시간 같은 짧은 기간의 강수량이다. |
| antecedent rainfall | event보다 앞선 7일 또는 30일 동안의 누적 강수다. 유역이 이미 젖어 있었는지 보는 proxy다. |
| flood generation typing | event를 recent precipitation, antecedent precipitation, snowmelt or rain-on-snow 같은 생성 메커니즘으로 분류하고, basin별로 dominant type 또는 mixture를 요약하는 과정이다. |
| response window | rain event 뒤에 실제 유량이 얼마나 반응했는지 보는 시간 구간이다. 극한호우 stress test에서는 rain 시작 24시간 전부터 rain 종료 168시간 뒤까지 본다. |
| inference block | LSTM이 충분한 이전 정보를 보게 하기 위해 response window보다 넓게 잘라낸 입력 구간이다. 현재는 rain 시작 21일 전부터 rain 종료 8일 뒤까지 둔다. |
| positive-response event | 극한호우 뒤에 관측 유량도 flood-like하게 오른 event다. 모델이 peak를 따라가는지 보는 주 test 대상이다. |
| negative-control event | 비는 극단적이었지만 관측 유량은 크게 오르지 않은 event다. 이런 경우 모델이 괜히 큰 홍수를 예측하지 않는지도 봐야 한다. |
| primary checkpoint | validation 기준으로 고른 대표 epoch의 model checkpoint다. 논문 본문에서는 이 결과를 우선 읽는다. |
| validation checkpoint grid | validation 결과가 저장된 여러 epoch 묶음이다. 현재는 `005 / 010 / 015 / 020 / 025 / 030`이고, primary 결과가 특정 epoch 하나에만 의존하는지 확인하는 sensitivity 용도다. |
| progress bar | 긴 서버 분석에서 몇 개 basin을 처리했는지 보여주는 진행 표시다. 현재 all-basin return-period 단계와 event-response 단계에서 `0/N`, elapsed, ETA가 출력된다. |

## 재현기간 지표와 Q99/q99의 차이

`prec_ari100_24h`, `flood_ari100`, `Q99`, Model 2의 `q99`는 서로 다른 값이다. 문헌에서는 `P100`, `Q100` 같은 표기도 보이지만, 이 프로젝트의 설명 문서와 산출물 컬럼명에서는 `Q99/q99`와 헷갈리지 않게 `prec_ari*`, `flood_ari*`를 권장한다.

| 값 | 계산 대상 | 쉬운 해석 |
| --- | --- | --- |
| `prec_ari100_24h` | 24시간 rolling precipitation의 annual maximum series에 맞춘 CAMELSH hourly proxy. 별도 비교용으로 NOAA Atlas 14 point/gridmean/areal-ARF reference도 둔다. | 24시간 강수량 기준 100년 빈도 강수 |
| `flood_ari100` | annual maximum streamflow series에 맞춘 CAMELSH hourly proxy. 별도 비교용으로 USGS StreamStats/GageStats peak-flow reference도 둔다. | 100년 빈도 홍수량 또는 1% AEP flood |
| hourly `Q99` | 한 basin의 전체 hourly streamflow 시계열 | 전체 시간 중 상위 1% 유량 기준 |
| Model `q99` | 모델이 각 시점마다 출력하는 conditional quantile | 해당 시점 조건에서의 상위 예측선 |

이 연구에서 `Q99`는 event extraction threshold로 쓰고, Model `q99`는 probabilistic output으로 쓴다. 반면 `prec_ari100_24h`와 `flood_ari100`은 basin과 event의 규모를 해석하기 위한 참고지표다.

예를 들어 어떤 event의 peak가 `flood_ari100`의 80% 수준이라면, 그 event가 해당 basin에서 꽤 큰 홍수였다고 설명할 수 있다. 어떤 event의 24시간 강수량이 `prec_ari100_24h`에 가까우면, 강수 forcing 자체도 매우 극단적이었다고 볼 수 있다. 다만 100년 빈도 강수가 곧 100년 빈도 홍수를 만든다는 뜻은 아니다. 유역의 젖은 정도, snowmelt, 토양 저장, 저수지 영향에 따라 강수와 유량의 관계가 달라진다.

현재 서버 all-basin 분석에서 만드는 재현기간 값은 CAMELSH hourly record 기반 proxy다. 그래서 산출물에는 `flood_ari_source`, `prec_ari_source`, `return_period_confidence_flag`를 같이 남긴다. record 길이가 짧은 basin에서 100년 값을 추정하면 외삽이 커지므로, 이 flag를 보고 해석 강도를 낮춰야 한다.
