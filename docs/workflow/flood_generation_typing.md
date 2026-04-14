# Flood Generation Type Classification

## 서술 목적

이 문서는 DRBC + CAMELSH basin cohort 위에서 `홍수 생성 메커니즘`을 어떻게 분류할지 설계한다. 핵심은 basin을 먼저 고정된 타입으로 두지 않고, `event를 먼저 분류한 뒤` basin별로 집계해 `dominant flood generation type` 또는 `mixture basin`으로 요약하는 것이다.

## 다루는 범위

- event-first flood generation typing 철학
- descriptor 기반 mechanism score와 basin-level 요약 구조
- 해석과 stratified evaluation에서의 활용 원칙

## 다루지 않는 범위

- hourly event extraction 규칙 자체
- basin screening의 공식 cohort 선정 규칙
- 모델 학습 loss나 config 설계

## 상세 서술

즉 이 문서의 역할은 `해석과 stratified evaluation`이다. `event extraction 규칙`은 [`event_response_spec.md`](event_response_spec.md), basin cohort screening 규칙은 [`basin_screening_method.md`](basin_screening_method.md)에서 다룬다.

## 1. 왜 event-first가 맞는가

홍수 생성 메커니즘은 basin의 고정 속성만으로 정해지지 않는다. 같은 basin에서도 어떤 해는 짧고 강한 rainfall, 어떤 해는 antecedent wetness, 어떤 해는 snowmelt나 rain-on-snow가 작동할 수 있다.

그래서 분류의 기본 단위는 basin이 아니라 `개별 flood event`다. basin-level label은 event type을 집계한 결과로 붙인다.

## 2. 문헌과의 관계

우리 설계는 Jiang et al. (2022)의 큰 방향을 따른다. 그 논문은 annual maximum discharge event를 대상으로 explainable ML을 이용해 `recent precipitation`, `antecedent precipitation`, `snowmelt` 세 가지 메커니즘을 도출하고, catchment별로 dominant mechanism 또는 mixture를 요약했다.

다만 우리는 그 방법을 그대로 복제하지는 않는다. 이유는 세 가지다.

첫째, 그 논문은 `annual maxima + explainable LSTM + K-means`가 classification의 핵심인데, 우리 연구의 중심은 분류 자체가 아니라 `Model 1 deterministic baseline과 Model 2 probabilistic baseline 비교`다.

둘째, 우리는 `CAMELSH hourly`를 쓰기 때문에 annual maxima만 보는 것보다 threshold-exceeding high-flow event를 더 폭넓게 쓰는 편이 연구 목적에 맞다.

셋째, 우리는 flood generation typing을 `학습 전 강한 필터`가 아니라 `모델 결과 해석과 stratified evaluation`에 쓰려고 한다.

즉, 우리는 `same philosophy, adapted implementation`을 택한다.

## 3. 분류의 기본 구조

분류는 네 단계로 진행한다.

1. `hourly streamflow에서 독립 flood event 추출`
2. `각 event마다 hydrometeorological descriptor 계산`
3. `descriptor를 바탕으로 event type 판정`
4. `basin별로 dominant type 또는 mixture 요약`

basin screening은 어떤 basin을 모델 비교에 넣을지 정하는 단계이고, flood generation typing은 선택된 basin들 안에서 `어떤 event가 주로 발생하는가`를 해석하는 단계다.

## 4. Event extraction

event typing의 입력은 `hourly event table`이다. 각 행은 하나의 독립 flood event가 된다. event를 어떻게 추출하고 어떤 descriptor를 계산할지는 [`event_response_spec.md`](event_response_spec.md)에 고정한다.

현재 권장 설계는 `POT (peaks over threshold)` 기반이다. basin \(i\)에서 hourly discharge의 high-flow threshold를 정한 뒤, 이를 초과하는 독립 event를 추출한다. extreme-focused evaluation과 연계하려면 threshold는 우선 `Q99`를 권장하고, sample 수가 부족하면 `Q95`로 완화할 수 있다.

event \(e\)의 독립성은 최소 inter-event separation 시간 \(\Delta t_{\mathrm{sep}}\)로 정의한다. 예를 들어 두 peak 사이가 72시간 이상 떨어지면 독립 event로 본다. 논문 본문에서는 exact separation 값을 고정하기보다 `hourly hydrograph inspection과 sensitivity check를 통해 선택했다`고 적는 것이 자연스럽다.

## 5. Event table에 들어갈 핵심 변수

각 event에 대해 최소한 아래 변수를 계산하는 것이 좋다.

- `event_start`, `event_end`, `peak_time`
- `peak_discharge`
- `unit_area_peak`
- `rising_time_hours`
- `event_duration_hours`
- `recent_rain_24h`
- `recent_rain_72h`
- `antecedent_rain_7d`
- `antecedent_rain_30d`
- `peak_rain_intensity_6h`
- `event_mean_temp`
- `antecedent_mean_temp_7d`
- `cold_season_flag`

가능하면 추가할 변수는 아래와 같다.

- `snow_related_flag`
- `rain_on_snow_proxy`
- `event_runoff_coefficient`
- `API_7d` 또는 `API_30d`

여기서 핵심은 event마다 `최근 강수`, `선행 습윤 상태`, `온도 / snow 관련 상태`, `hydrograph shape`를 같이 보는 것이다.

## 6. Event type 정의

우리 연구에서는 우선 세 가지 메커니즘 축을 쓴다.

1. `recent_precipitation`
2. `antecedent_precipitation`
3. `snowmelt_or_rain_on_snow`

이 세 가지는 HESS 2022의 큰 틀과 같다. 다만 우리 구현에서는 explainable ML을 쓰지 않고, hourly event descriptor를 기반으로 rule-based 또는 score-based 판정을 우선 적용한다.

### 6.1 Recent precipitation event

이 타입은 `짧고 강한 강수`가 peak를 직접 만든 경우다. 전형적으로 recent rainfall이 크고, peak 직전 강수 intensity가 높고, rising time이 짧다.

대표적 판정 신호는 아래와 같다.

- `recent_rain_24h`가 크다
- `peak_rain_intensity_6h`가 크다
- `rising_time_hours`가 짧다
- `antecedent_rain_30d`의 상대적 기여는 크지 않다
- `event_mean_temp`가 충분히 높아서 snowmelt event로 보기 어렵다

### 6.2 Antecedent precipitation event

이 타입은 최근 비 자체보다 `선행 습윤 상태` 또는 `누적 강수`가 더 중요한 경우다. 강수는 비교적 길게 오고, basin이 이미 젖어 있는 상태에서 runoff efficiency가 커져 peak가 발생한다.

대표적 판정 신호는 아래와 같다.

- `antecedent_rain_7d` 또는 `antecedent_rain_30d`가 크다
- `recent_rain_24h`는 아주 크지 않아도 된다
- `event_duration_hours`가 비교적 길다
- `rising_time_hours`가 recent-rainfall event보다 길 수 있다
- `event_runoff_coefficient`가 높다면 해석을 더 지지한다

### 6.3 Snowmelt or rain-on-snow event

이 타입은 낮은 기온 조건, snow storage, 또는 해빙기에 형성되는 event다. 현재 CAMELSH forcing 변수 가용성을 고려하면 snow-related variable이 제한적일 수 있으므로, 우선은 `temperature + season + static frac_snow`를 조합한 proxy를 사용한다.

대표적 판정 신호는 아래와 같다.

- `cold_season_flag == True`
- `antecedent_mean_temp_7d`가 낮거나, event 기간 중 온도 상승이 뚜렷하다
- basin의 `frac_snow`가 높다
- recent rainfall만으로 설명하기 어렵다

가능하다면 SWE 또는 snowmelt proxy를 나중에 추가한다.

## 7. Event classification 방식

현재 연구 목적에는 `rule-based score classification`이 가장 적절하다. 이유는 해석이 쉽고, 모델 비교 연구의 본 주제를 흐리지 않기 때문이다.

각 event \(e\), basin \(i\)에 대해 세 가지 mechanism score를 정의할 수 있다.

$$
S_{e,i}^{(r)} = a_1\,R^{\uparrow}(\text{recent\_rain\_24h}) + a_2\,R^{\uparrow}(\text{peak\_rain\_intensity\_6h}) + a_3\,R^{\downarrow}(\text{rising\_time\_hours})
$$

$$
S_{e,i}^{(a)} = b_1\,R^{\uparrow}(\text{antecedent\_rain\_7d}) + b_2\,R^{\uparrow}(\text{antecedent\_rain\_30d}) + b_3\,R^{\uparrow}(\text{event\_duration\_hours})
$$

$$
S_{e,i}^{(s)} = c_1\,I(\text{cold\_season}) + c_2\,R^{\uparrow}(\text{frac\_snow}) + c_3\,R^{\downarrow}(\text{antecedent\_mean\_temp\_7d})
$$

여기서 \(R^{\uparrow}\)와 \(R^{\downarrow}\)는 event set 내부 rank 또는 basin-normalized rank를 뜻하고, \(I(\cdot)\)는 indicator function이다.

그다음 event label은

$$
L_{e,i} = \arg\max \left\{ S_{e,i}^{(r)},\; S_{e,i}^{(a)},\; S_{e,i}^{(s)} \right\}
$$

로 정의할 수 있다.

현재 단계에서는 exact coefficient \(a_k, b_k, c_k\)를 고정하는 것보다, 이 구조 자체를 먼저 도입하고 coefficient는 exploratory tuning 대상으로 두는 것이 좋다. classification 자체가 우리 연구의 핵심이 아니기 때문이다.

## 8. Basin-level 요약

basin \(i\)에 대해 event type이 정해지면, basin별로 각 type의 비율을 계산한다.

$$
p_i^{(r)} = \frac{N_i^{(r)}}{N_i}, \qquad
p_i^{(a)} = \frac{N_i^{(a)}}{N_i}, \qquad
p_i^{(s)} = \frac{N_i^{(s)}}{N_i}
$$

여기서 \(N_i\)는 basin \(i\)의 전체 classified event 수이고, \(N_i^{(r)}, N_i^{(a)}, N_i^{(s)}\)는 각각 recent-precipitation, antecedent-precipitation, snowmelt/rain-on-snow event 수다.

그다음 basin-level label은 아래처럼 정의한다.

- 특정 type 비율이 충분히 높으면 `dominant type basin`
- 그렇지 않으면 `mixture basin`

지금 단계에서는 hard threshold를 너무 빡빡하게 두지 않는 것이 좋다. 권장 기준은

$$
\max\left(p_i^{(r)}, p_i^{(a)}, p_i^{(s)}\right) \ge 0.6
$$

이면 dominant basin으로 두고, 그렇지 않으면 mixture basin으로 두는 것이다.

이 방식은 HESS 2022의 `dominant vs mixture` 철학을 유지하면서도, 현재 데이터와 샘플 수에 더 유연하다.

## 9. 이 분류를 연구에서 어디에 쓰는가

이 flood generation typing은 `학습 전 basin filtering`에 쓰지 않는 것이 좋다. 대신 다음 두 용도로 쓰는 것이 적절하다.

첫째, `post-hoc interpretation`이다. 예를 들어 probabilistic head가 recent-precipitation basin에서 peak underestimation을 더 잘 줄였는지, 그 개선이 snowmelt basin이나 mixture basin에서도 유지되는지를 볼 수 있다.

둘째, `stratified evaluation`이다. basin 전체 성능 평균만 보는 대신, dominant type별로 성능을 나누어 보면 모델 구조의 강점과 약점을 훨씬 더 분명하게 설명할 수 있다.

즉 flood generation typing은 screening을 대체하는 것이 아니라, screening 이후 모델 결과 해석을 강화하는 층이다.

## 10. 현재 구현 우선순위

현재 가장 좋은 구현 순서는 아래와 같다.

1. hourly event table 생성
2. event descriptor 계산
3. 간단한 rule-based event typing v1 구현
4. basin별 dominant / mixture 요약
5. 모델 결과를 type별로 stratified evaluation

이 순서를 지키면 classification 모듈이 연구 전체를 잡아먹지 않고, 모델 비교라는 본 주제를 유지할 수 있다.

## 11. 참고 문헌과 링크

- Jiang, S., Bevacqua, E., and Zscheischler, J. (2022): River flooding mechanisms and their changes in Europe revealed by explainable machine learning, HESS, 26, 6339–6359. [https://hess.copernicus.org/articles/26/6339/2022/](https://hess.copernicus.org/articles/26/6339/2022/)
- Stein, L., Pianosi, F., and Woods, R. (2021): How do climate and catchment attributes influence flood generating processes? A large-sample study for 671 catchments across the contiguous USA. [https://research-groups.usask.ca/hydrology/documents/pubs/papers/stein_et_al_2021.pdf](https://research-groups.usask.ca/hydrology/documents/pubs/papers/stein_et_al_2021.pdf)
- Causative classification of river flood events (review). [https://pmc.ncbi.nlm.nih.gov/articles/PMC6686718/](https://pmc.ncbi.nlm.nih.gov/articles/PMC6686718/)

## 문서 정리

이 문서는 basin을 고정형 메커니즘으로 분류하지 않고, event를 먼저 분류한 뒤 basin 수준으로 집계하는 해석 틀을 제안한다. 현재 단계에서는 classification accuracy 자체보다, 모델 비교 결과를 해석하고 stratified evaluation을 가능하게 만드는 것이 더 중요하다.

따라서 typing은 screening의 대체물이 아니다. basin cohort가 정해진 뒤, 어떤 메커니즘에서 어떤 모델이 강하거나 약한지를 읽기 위한 후속 해석 층으로 사용하는 것이 맞다.

## 관련 문서

- event extraction과 descriptor 계산 규칙은 [`event_response_spec.md`](event_response_spec.md)에서 고정한다.
- basin cohort 선정 규칙은 [`basin_screening_method.md`](basin_screening_method.md)에서 다룬다.
- 실험 전체 비교축과 평가 원칙은 [`../research/design.md`](../research/design.md), [`../research/experiment_protocol.md`](../research/experiment_protocol.md)에서 다룬다.
