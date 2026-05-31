# 04. 변수와 용어 해설

이 문서는 CAMELS 연구 문서에서 자주 나오는 용어를 풀어 쓴 사전이다. 비전공 대학생이 처음 읽어도 의미를 잡을 수 있도록 정의·직관·비유·해석을 붙였다. 코드 식별자나 고정된 전문 용어(LSTM, quantile 등)는 그대로 두되, 일반 설명어는 한국어로 쓴다.

읽는 방법을 먼저 정리한다.

- **일반 용어**(데이터, 모델, 실험, 유역 특성, event 분석)는 `용어 | 쉬운 설명` 표로 간단히 본다.
- **지표성 용어**(NSE, coverage, calibration, α/β/δ, FAR 등 숫자로 모델 성능을 재는 값)는 먼저 **참조 카드** 표로 한눈에 보고, 표 바로 아래 H3(`###`) 항목에서 정의·직관·비유·해석을 상세히 본다. 참조 카드 표에는 핵심 4개 컬럼만 둔다: `심볼 | 변수명 | 범위 | 최적화 방향`.

여기서 "변수명"은 산출물 표(`output/model_analysis/...`)의 컬럼명이나 분석 스크립트가 출력하는 이름이다. 어떤 분석에서 나온 값인지 추적할 수 있도록 가능한 곳에 출처를 가볍게 적어 둔다.

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
| NSE tier (NSE 3-tier cohort) | Model 1의 NSE 성능을 기준으로 유역을 세 묶음(잘 맞는 유역 / 보통 / 못 맞는 유역)으로 나눈 것이다. 우리말로는 NSE 성능 단계라고 부른다. 같은 결과라도 어느 단계 유역인지에 따라 해석이 달라질 수 있어 묶어서 본다. |

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

## 평가 지표 — 중심·고유량 성능

여기서부터는 모델이 "얼마나 잘 맞췄나"를 숫자로 재는 지표다. 먼저 참조 카드로 범위와 좋은 방향만 잡고, 표 아래 항목에서 자세히 본다.

식에서 쓰는 기호를 먼저 약속한다. $y_t$는 시간 $t$의 실제 관측 유량, $\hat{y}_t$는 모델 예측 유량이다. Model 1에서는 $\hat{y}_t = \hat{Q}_t$이고, Model 2를 한 점짜리 예측처럼 비교할 때는 보통 $\hat{y}_t = q50_t$로 둔다. $T$는 평가에 쓰는 전체 시간 수, $\bar{y}$는 관측 유량 평균이다.

| 심볼 | 변수명 | 범위 | 최적화 방향 |
| --- | --- | --- | --- |
| NSE | `nse` | 1 이하 (1이 완벽, 0이면 평균 예측 수준) | 클수록 좋음 ↑ |
| KGE | `kge` | 1 이하 (1이 완벽) | 클수록 좋음 ↑ |
| NSElog | `nselog` | 1 이하 (1이 완벽) | 클수록 좋음 ↑ |
| FHV | `fhv` (%) | 음수~양수 (0이 최선) | 0에 가깝게 ↕ |
| PRE | `peak_relative_error` (%) | 음수~양수 (0이 최선) | 0에 가깝게 ↕ |
| PTE | `peak_timing_error` (hr) | 음수~양수 (0이 최선) | 0에 가깝게 ↕ |
| Recall₁% | `top1pct_recall` | 0~1 | 클수록 좋음 ↑ |
| RMSEₑ | `event_rmse` | 0 이상 (0이 최선) | 작을수록 좋음 ↓ |

### NSE — 전체 유량 적합도 (Nash–Sutcliffe Efficiency)

**정의.** 전체 유량 시계열을 얼마나 잘 맞췄는지 보는 대표 수문 성능 지표다.

$$
\mathrm{NSE} = 1 - \frac{\sum_{t=1}^{T}(y_t-\hat{y}_t)^2}{\sum_{t=1}^{T}(y_t-\bar{y}_t)^2}
$$

분모는 "관측 평균만 계속 예측하는 가장 게으른 모델"의 오차이고, 분자는 우리 모델의 오차다.

**직관·비유.** 시험 점수를 "반 평균만 찍는 학생"과 비교하는 것과 같다. 1에 가까울수록 거의 완벽, 0이면 평균만 찍는 학생과 비슷, 0보다 작으면 평균만 찍느니만 못하다는 뜻이다.

**해석.** 값이 1에 가까울수록 좋다. RQ-1 분석(`compute_rq1_central_metrics.py`)에서 Model 1은 basin median NSE ≈ −0.03, Model 2 q50은 ≈ +0.23으로, q50이 중심 예측 성능을 오히려 끌어올렸다.

### KGE — 균형 성능 (Kling–Gupta Efficiency)

**정의.** 상관, 변동성, 평균 bias 세 가지를 한 번에 보는 지표다.

$$
\mathrm{KGE} = 1 - \sqrt{(r-1)^2 + (\alpha-1)^2 + (\beta-1)^2}
$$

여기서 $r$은 관측과 예측의 상관계수, $\alpha = \sigma_{\hat{y}} / \sigma_y$는 변동성(표준편차) 비율, $\beta = \mu_{\hat{y}} / \mu_y$는 평균 비율이다. (이 $\alpha, \beta$는 KGE 내부 항이며, 뒤에 나오는 RQ-2의 첨두 지표 α·β와는 다른 값이다.)

**직관·비유.** NSE가 "오차 크기 하나"만 본다면, KGE는 "흐름의 모양은 비슷한가(상관), 출렁임의 크기는 비슷한가(변동성), 평균 수위가 비슷한가(평균)"를 세 항목으로 나눠 채점한다. 셋 다 1에 가까워야 만점이다.

**해석.** 1에 가까울수록 좋다. NSE 하나만 볼 때 놓치는 변동성·평균 bias 문제를 보완한다.

### NSElog — 작은 유량까지 본 적합도

**정의.** 유량에 log를 씌운 뒤 NSE를 계산한다. 작은 유량 구간이 큰 홍수에 묻히지 않게 보려는 지표다.

$$
\mathrm{NSElog} = 1 - \frac{\sum_{t=1}^{T}\left[\log(y_t+\epsilon)-\log(\hat{y}_t+\epsilon)\right]^2}{\sum_{t=1}^{T}\left[\log(y_t+\epsilon)-\overline{\log(y+\epsilon)}\right]^2}
$$

$\epsilon$은 0 유량에서 log가 깨지는 것을 막으려고 더하는 아주 작은 값이다.

**직관·비유.** 보통 NSE는 큰 숫자(홍수)에 점수가 쏠린다. log를 씌우면 1과 2의 차이도, 100과 200의 차이도 비슷한 비중으로 보게 되어, 평소의 작은 유량 적합도를 살펴볼 수 있다.

**해석.** 1에 가까울수록 좋다. 홍수 예측만 좋아지고 평소 유량 예측이 무너졌는지 확인할 때 유용하다.

### FHV — 고유량 총량 편향 (Flow at High Values)

**정의.** high-flow 구간에서 예측 유량 총량이 실제보다 얼마나 높거나 낮은지 백분율로 보는 지표다. 관측 유량이 큰 시간 집합을 $H$(예: 관측 상위 2%)라 하면,

$$
\mathrm{FHV} = 100 \times \frac{\sum_{t \in H}(\hat{y}_t-y_t)}{\sum_{t \in H}y_t}
$$

**직관·비유.** 큰 물이 난 날들만 모아서, 모델이 그 총량을 "전체적으로 적게 본 셈인지(음수) 많게 본 셈인지(양수)"를 비율로 알려 준다. 첨두 한 점이 아니라 고유량 구간 전체의 양적 균형을 본다.

**해석.** 0에 가까울수록 좋다. 음수면 큰 유량을 전반적으로 낮게 예측(과소추정), 양수면 높게 예측한 것이다. RQ-1 분석에서 Model 1은 −12.3%, Model 2 q50은 −36.1%로, 둘 다 고유량을 과소추정하며 q50이 더 심하다. 이 연구가 상위 quantile(q90/q95/q99)을 도입한 동기가 바로 이 과소추정이다.

### PRE — 첨두 상대 오차 (Peak Relative Error)

**정의.** event 단위로 실제 첨두와 예측 첨두의 차이를 백분율로 본다. event $e$의 실제 첨두를 $Q^{\mathrm{peak}}_e$, 예측 첨두를 $\hat{Q}^{\mathrm{peak}}_e$라 하면,

$$
\mathrm{PRE}_e = 100 \times \frac{\hat{Q}^{\mathrm{peak}}_e - Q^{\mathrm{peak}}_e}{Q^{\mathrm{peak}}_e}
$$

**직관·비유.** 홍수 한 번의 "가장 높은 물높이"를 모델이 몇 % 높게/낮게 봤는지 재는 것이다. −30%면 실제 첨두의 70%까지밖에 못 올라갔다는 뜻이다.

**해석.** 0에 가까울수록 좋다. 음수면 첨두를 낮게(과소추정), 양수면 높게 예측한 것이다. 이 연구에서는 특히 음수 방향 bias, 즉 peak underestimation이 핵심 관심사다.

### PTE — 첨두 시점 오차 (Peak Timing Error)

**정의.** event 안에서 실제 첨두 시각과 예측 첨두 시각의 차이다.

$$
\mathrm{PTE}_e = \hat{t}^{\mathrm{peak}}_e - t^{\mathrm{peak}}_e
$$

**직관·비유.** "물이 가장 높이 차는 순간"을 모델이 몇 시간 빠르거나 늦게 맞혔는지 본다. 첨두 높이가 맞아도 시점이 어긋나면 경보로서 가치가 떨어진다.

**해석.** 단위는 보통 hour다. 0에 가까울수록 좋다. 부호를 살리면 예측이 빠른지(음수) 늦은지(양수), 절댓값 $|\mathrm{PTE}_e|$을 쓰면 얼마나 어긋났는지만 본다.

### Recall₁% — 상위 1% 유량 재현율 (top 1% flow recall)

**정의.** 실제로 매우 큰 유량이 나온 시간들을 모델이 얼마나 놓치지 않았는지 본다. 관측 유량의 99% 분위 기준값을 $Q_{0.99}$라 하면,

$$
H_{1\%} = \{t \mid y_t \ge Q_{0.99}\}, \qquad \hat{H}_{1\%} = \{t \mid \hat{y}_t \ge Q_{0.99}\}
$$

$$
\mathrm{Recall}_{1\%} = \frac{|H_{1\%} \cap \hat{H}_{1\%}|}{|H_{1\%}|}
$$

**직관·비유.** "실제로 가장 위험했던 순간 100개 중 모델이 위험하다고 본 것이 몇 개인가"를 비율로 보는 것이다. 화재 경보기가 진짜 화재를 몇 번 잡았는지와 같다.

**해석.** 0~1이며 클수록 좋다(극한 유량 시점을 덜 놓친다). Model 2에서는 $\hat{y}_t$ 자리에 `q50`, `q95`, `q99`를 각각 넣어 비교할 수 있다.

### RMSEₑ — event 전체 모양 오차 (event-level RMSE)

**정의.** 하나의 flood event 전체 모양을 얼마나 잘 따라갔는지 보는 오차다. event $e$의 시간 집합을 $T_e$라 하면,

$$
\mathrm{RMSE}_e = \sqrt{\frac{1}{|T_e|}\sum_{t \in T_e}(y_t-\hat{y}_t)^2}
$$

**직관·비유.** 첨두 한 점만이 아니라, 물이 차오르는 상승부와 빠지는 하강부까지 포함한 hydrograph 곡선 전체를 얼마나 비슷하게 그렸는지 본다.

**해석.** 0 이상이며 작을수록 좋다. 첨두 한 점만 맞췄는지가 아니라 event 전체를 보고 싶을 때 쓴다.

## 평가 지표 — quantile 예측 품질 (calibration·sharpness)

Model 2처럼 여러 quantile을 내는 모델이 "확률 예측으로서" 얼마나 믿을 만한지 재는 지표다. quantile level은 $\tau$(예: 0.95), 그 예측값을 $q_{\tau,t}$로 쓴다.

| 심볼 | 변수명 | 범위 | 최적화 방향 |
| --- | --- | --- | --- |
| L_τ | `pinball` | 0 이상 (0이 최선) | 작을수록 좋음 ↓ |
| Coverage_τ | `coverage_fraction` | 0~1 (목표는 $\tau$값) | $\tau$에 가깝게 ↕ |
| CalErr | `calibration_error` | 0 이상 (0이 최선) | 작을수록 좋음 ↓ |
| Width | `upper_tail_spread` (q99−q50 등) | 0 이상 | 좁되 calibration과 함께 ↕ |

### pinball loss — quantile 학습·평가 손실

**정의.** quantile 예측의 품질을 보는 비대칭 손실이다.

$$
L_{\tau}(y_t, q_{\tau,t}) = \max\left(\tau(y_t-q_{\tau,t}),\ (\tau-1)(y_t-q_{\tau,t})\right)
$$

여러 quantile을 함께 쓰면 시간과 quantile에 대해 (가중)평균을 낸다. 현재 Model 2의 quantile set은 $\mathcal{Q}=\{0.5, 0.9, 0.95, 0.99\}$이고 기본 가중치는 모두 같다.

$$
L_{\mathrm{pinball}} = \frac{1}{T}\sum_{t=1}^{T}\sum_{\tau \in \mathcal{Q}} w_{\tau} L_{\tau}(y_t, q_{\tau,t})
$$

**직관·비유.** 높은 quantile(예: q99)에서는 "실제가 예측보다 위에 있는데 낮게 잡는 실수"를 훨씬 무겁게 벌한다. 위험을 깔보는 쪽에 큰 벌점을 주는 비대칭 채점이다.

**해석.** 0 이상이며 작을수록 좋다. RQ-5 진단(`analyze_expanded_drbc_probabilistic_diagnostics.py`)에서 basin median mean pinball은 q50 4.66 → q99 1.64로, 상위 quantile이 고유량 비대칭 손실 기준에서 유리하게 보인다. 단, 아래 calibration 결과와 함께 읽어야 한다.

### coverage — 포함 비율

**정의.** 예측한 quantile 아래에 실제값이 얼마나 자주 들어오는지 보는 값이다.

$$
\mathrm{Coverage}_{\tau} = \frac{1}{T}\sum_{t=1}^{T}\mathbf{1}(y_t \le q_{\tau,t})
$$

**직관·비유.** "q95라는 선 아래에 실제값이 95번쯤 들어와야 이름값을 한다"는 약속이다. 우산을 95% 확률로 막아 준다고 했으면, 실제로 100번 중 95번쯤 막아야 정직한 우산이다.

**해석.** 0~1이며 목표는 그 quantile의 $\tau$값에 맞는 것이다(q95면 0.95). RQ-5 결과에서 q99의 empirical coverage는 basin median 0.787로 0.99에 한참 못 미친다(undercoverage). 그래서 이 연구는 `q99`를 "calibrated 99% predictive quantile"이라 부르지 않고, 고유량 의사결정용 상위선(upper-tail decision output)으로만 쓴다.

### calibration error — 보정 오차

**정의.** 목표 quantile level과 실제 coverage가 얼마나 가까운지 본다. 간단한 요약값은,

$$
\mathrm{CalErr} = \frac{1}{|\mathcal{Q}|}\sum_{\tau \in \mathcal{Q}}\left|\mathrm{Coverage}_{\tau} - \tau\right|
$$

**직관·비유.** "내가 95%라고 말한 게 실제로 95%였나"를 quantile마다 점검해 평균 낸 어긋남이다. 일기예보가 "비 올 확률 70%"라고 한 날 중 실제로 70%쯤 비가 왔는지 따지는 것과 같다.

**해석.** 0 이상이며 작을수록(말한 확률과 실제 빈도가 잘 맞을수록) 좋다. 다만 coverage만 맞고 예측 폭(width)이 지나치게 넓으면 실용성이 떨어지므로, 아래 sharpness/width와 짝으로 본다. **calibration(보정)과 sharpness(예리함)는 항상 함께 본다**: 폭이 좁아야(sharp) 단정적이고 쓸모 있지만, 좁기만 하고 calibration이 나쁘면 빗나간 자신감일 뿐이다.

### quantile interval width — 예측 폭 (sharpness)

**정의.** Model 2의 상위선이 중심선보다 위쪽 가능성을 얼마나 열어 두는지 보는 폭이다.

$$
\mathrm{Width}_{95,t} = q95_t - q50_t, \qquad \mathrm{Width}_{99,t} = q99_t - q50_t
$$

**직관·비유.** 일기예보가 "내일 기온 20도"라고 콕 집으면 sharp하지만 틀릴 위험이 크고, "15~25도"라고 넓게 말하면 안전하지만 정보가 적다. width는 그 범위의 넓이다. 좁을수록 sharp하다.

**해석.** 0 이상이며, 좁을수록 sharp하지만 calibration이 나쁘면 좁기만 하고 빗나갈 수 있다. RQ-5 결과에서 고유량(Q99 초과) 구간의 `q99 − q50` median spread는 20.836로 관측값의 약 74.6%에 해당한다 — 큰 물일 때 q99이 q50 위로 상당한 보수성을 추가한다는 뜻이다.

## 상위 quantile 이득·비용 측정 지표 (RQ-2 / RQ-3)

Model 2의 상위 예측선(`q90 / q95 / q99`)이 홍수 첨두를 얼마나 잘 잡는지(이득)와 그 대가로 얼마나 헛경보·과대예측을 내는지(비용)를 event·시각 단위로 재는 지표다. 앞 세 개(α, β, δ)는 이득 쪽, 뒤 두 개(FAR, over-prediction magnitude)는 비용 쪽이다.

식에서 $\tau$는 quantile level, $q_\tau$는 그 예측값, `obs`는 관측 유량, `obs_peak`는 event 첨두 관측값, $Q99_{\mathrm{basin}}$은 각 basin의 고유량 기준선(관측 상위 1% 값)이다.

| 심볼 | 변수명 | 범위 | 최적화 방향 |
| --- | --- | --- | --- |
| α | `rq2_alpha_event_peak_deficit` | 0~1 (0이 최선) | 작을수록 좋음 ↓ |
| β | `rq2_beta_window_capture` | 0 이상 (1=딱 맞음, >1=과대) | 1 근처/↑ |
| δ | `rq2_delta_threshold_recall` | 0~1 | 클수록 좋음 ↑ |
| FAR | `rq3_far` | 0~1 (0이 최선) | 작을수록 좋음 ↓ |
| OverPred | `rq3_over_prediction_magnitude` | 0 이상 | 작을수록 좋음 ↓ |

### α — 첨두 부족분 (event peak under-deficit)

**정의.** event 첨두 시각에서 모델 상위선이 실제 첨두를 얼마나 못 따라갔는지를 비율로 본다.

$$
\alpha_\tau = \frac{\left(\mathrm{obs\_peak} - q_{\tau,\,\text{at peak}}\right)_+}{\mathrm{obs\_peak}}
$$

여기서 $(\cdot)_+$는 음수를 0으로 자른다는 뜻이다(즉 예측이 실제보다 높으면 부족분은 0).

**직관·비유.** 홍수 최고 수위가 100일 때 모델이 70까지만 올라갔으면 부족분은 0.3이다. 모델이 100 이상으로 올라갔으면 "못 따라간 양"은 없으니 0이다. 0이 최선이다.

**해석.** 0~1이며 작을수록 좋다. RQ-2 분석(`compute_rq2_alpha_peak_deficit.py`, 산출물 `rq2_alpha_event_peak_deficit_q99.csv`)에서 Q99 scope basin median은 q50 0.657 → q99 0.018로, 첨두 시각에서 q99이 실제 높이를 거의 따라잡는다.

### β — ±6시간 창 포착 (window peak capture)

**정의.** 첨두 시각 앞뒤 6시간 창 안에서 모델 최댓값이 실제 최댓값을 얼마나 잡았는지의 비율이다.

$$
\beta_\tau = \frac{\max\left(q_\tau \text{ in } \pm 6\text{h}\right)}{\max\left(\mathrm{obs} \text{ in } \pm 6\text{h}\right)}
$$

**직관·비유.** 첨두 시각이 한두 시간 어긋날 수 있으니, 좁은 점이 아니라 6시간 창 안에서 "가장 높이 올라간 정도"를 비교한다. 1이면 창 안 실제 최댓값과 똑같이 올라간 것, 1보다 크면 그보다 더 높게(보수적으로) 올라간 것이다.

**해석.** 0 이상이며 1 근처거나 그 이상이 좋다. capture 비율이라 1을 넘을 수 있고 q99에서는 가끔 2를 넘는 것도 자연스럽다. RQ-2 분석(`compute_rq2_beta_window_capture.py`)에서 Q99 scope basin median은 q50 0.444 → q99 1.306으로, q99이 창 안에서 실제의 1.3배까지 overshoot한다(충분한 보수성). 단, β > 1은 over-capture이므로 아래 over-prediction 비용으로 연결된다.

### δ — 기준 초과 재현율 (Q99 threshold recall)

**정의.** 실제로 고유량 기준선 $Q99_{\mathrm{basin}}$을 넘은 시각 중 모델 상위선도 그 기준을 넘는다고 본 비율(재현율)이다.

$$
\delta_\tau = P\left(q_\tau \ge \mathrm{obs} \mid \mathrm{obs} \ge Q99_{\mathrm{basin}}\right)
$$

**직관·비유.** "실제로 위험 수위를 넘은 순간들" 중에서 모델이 "위험하다"고 같이 본 비율이다. δ가 높을수록 극한 시점을 덜 놓친다.

**해석.** 0~1이며 클수록 좋다. RQ-2 분석(`compute_rq2_delta_threshold_recall.py`)에서 Q99 scope basin median recall은 q50 0.069 → q99 0.583으로, q99이 고유량 시각의 약 58%를 잡는다(나머지 42%는 여전히 놓침). RQ-5의 tail hit-rate 0.563과 일치하는 신호다.

### FAR — 헛경보 비율 (false alarm rate)

**정의.** 실제로는 고유량 기준을 넘지 않았는데 모델이 넘는다고 잘못 본 시각의 비율이다.

$$
\mathrm{FAR}_\tau = P\left(q_\tau > Q99_{\mathrm{basin}} \mid \mathrm{obs} < Q99_{\mathrm{basin}}\right)
$$

**직관·비유.** 화재 경보기가 불이 안 났는데 울린 비율과 같다. 상위 quantile을 올려 δ(이득)를 키우면 이 헛경보(비용)도 같이 커진다.

**해석.** 0~1이며 작을수록 좋다. 분모가 전체 시간의 약 99%(기준 미만 시각)라 절댓값은 작게 보인다. RQ-3 분석(`compute_rq3_cost.py`, 산출물 `rq3_far_summary.csv`)에서 basin median FAR은 q50 0.0007 → q99 0.0164다. δ-recall은 q50→q99에서 약 8배 늘지만 FAR은 약 23배 늘어, 이득보다 비용이 더 가파르게 증가하는 비대칭 trade-off를 보인다.

### over-prediction magnitude — 과대예측 크기

**정의.** 모델이 실제보다 높게 낸 경우, 그 초과분이 평균적으로 얼마나 큰지를 본다.

$$
\mathrm{OverPred}_\tau = \mathrm{mean}\left(q_\tau - \mathrm{obs} \mid q_\tau > \mathrm{obs}\right)
$$

**직관·비유.** 헛경보가 "얼마나 자주" 울리는지(FAR)와 달리, 이 값은 "한 번 넘게 예측할 때 얼마나 크게 넘치는지"를 본다. 경보기가 울릴 때마다 얼마나 과하게 울리는지에 해당한다.

**해석.** 0 이상이며(관측 단위, mm/hr) 작을수록 좋다. 첨두를 잡으려 상위 quantile을 올리면 이 값도 같이 커진다. RQ-3 분석(산출물 `rq3_over_prediction_magnitude_summary.csv`)에서 basin median은 q50 1.47 → q99 3.44다. 절댓값은 basin 규모에 종속적이므로 basin 간 비교 시 상대 척도도 함께 본다.

## event 분석 용어

| 용어 | 쉬운 설명 |
| --- | --- |
| flood event | 유량이 일정 기준 이상으로 커지는 하나의 독립 홍수 사건이다. |
| NOAA event type | 미국 기상청(NOAA)이 분류한 홍수 유형이다. 돌발홍수(Flash Flood), 일반홍수(Flood), 해안홍수(Coastal Flood) 등으로 나뉜다. 같은 큰 물이라도 생기는 방식이 달라, 모델이 어떤 유형에서 잘하고 못하는지 볼 때 쓴다. |
| 관측 위치 구간 (band_shape / location class) | 실제 관측 첨두가 모델 예측 밴드 q50~q99 중 어느 칸에 드는지를 나타낸다. q50보다 아래인지, q50~q90 사이인지, q99 위로 삐져나갔는지처럼 관측이 예측 폭의 어디에 떨어졌는지로 구분한다. |
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
