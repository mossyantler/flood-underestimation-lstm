# Flood Generation / Event-Regime Typing

## 서술 목적

이 문서는 DRBC + CAMELSH basin cohort 위에서 high-flow event를 어떻게 해석하고, 그 결과를 모델 성능 분석에 어떻게 쓸지 정리한다. 핵심은 basin을 먼저 고정된 타입으로 두지 않고, `event를 먼저 분류한 뒤` basin별로 집계해 dominant 또는 mixture 구조로 요약하는 것이다.

현재 결론은 두 층으로 둔다. `degree_day_v2` rule-based typing은 해석 가능한 QA/baseline label로 유지하고, 모델의 peak underestimation이나 regional heterogeneity를 나누어 볼 때는 `hydromet_only_7 + KMeans(k=3)` ML-based event-regime clustering을 주 stratification으로 쓴다. 다만 ML cluster는 causal flood mechanism을 확정하는 label이 아니라, event descriptor 공간에서 비슷한 hydrometeorological response를 묶은 `event regime`으로 표현한다.

## 다루는 범위

- event-first flood generation typing 철학
- rule-based `degree_day_v2` QA/baseline label의 역할
- ML-based event-regime clustering의 역할과 해석 한계
- basin-level dominant / top-2 mixture 요약 구조
- 모델 결과 해석과 stratified evaluation에서의 활용 원칙

## 다루지 않는 범위

- hourly event extraction 규칙 자체
- basin screening의 공식 cohort 선정 규칙
- 모델 학습 loss나 config 설계

## 상세 서술

즉 이 문서의 역할은 `해석과 stratified evaluation`이다. `event extraction 규칙`은 [`event_response_spec.md`](event_response_spec.md), basin cohort screening 규칙은 [`basin_screening_method.md`](basin_screening_method.md)에서 다룬다. 본문에서 `flood generation type`이라고 부를 때도, 현재 자료만으로 실제 원인을 확정했다는 뜻은 아니다. 관측 high-flow event 주변의 rainfall, antecedent rainfall, snowmelt proxy, temperature 정보를 바탕으로 만든 해석 층이다.

## 1. 왜 event-first가 맞는가

홍수 생성 메커니즘은 basin의 고정 속성만으로 정해지지 않는다. 같은 basin에서도 어떤 해는 짧고 강한 rainfall, 어떤 해는 antecedent wetness, 어떤 해는 snowmelt나 rain-on-snow가 작동할 수 있다.

그래서 분류의 기본 단위는 basin이 아니라 `개별 observed high-flow event candidate`다. basin-level label은 event type을 집계한 결과로 붙인다. Q99/Q98/Q95 threshold로 잡힌 candidate를 곧바로 official flood라고 부르지 않고, `flood_relevance_tier`와 return-period proxy ratio를 함께 보면서 flood-like severity를 해석한다.

## 2. 문헌과의 관계

우리 설계는 Jiang et al. (2022)의 큰 방향을 따른다. 그 논문은 annual maximum discharge event를 대상으로 explainable ML을 이용해 `recent precipitation`, `antecedent precipitation`, `snowmelt` 세 가지 메커니즘을 도출하고, catchment별로 dominant mechanism 또는 mixture를 요약했다.

방어 논리는 아래처럼 잡는 것이 가장 안전하다. 선행연구들은 세부 알고리즘은 서로 다르지만, 공통적으로 `event를 먼저 정의하고`, `event 주변의 강수·선행습윤·snow/temperature 상태를 계산하고`, `그 지표로 event type을 부여한 뒤`, `basin 수준에서는 type 비율이나 dominant process로 요약`한다. 우리는 이 절차를 CAMELSH hourly `.nc`에서 안정적으로 얻을 수 있는 변수에 맞춰 단순화했다.

| 선행연구의 공통 단계                                   | 대표 문헌                                                                                                                                                  | 우리 구현에서의 대응                                                                                                                                                                          |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. high-flow event candidate를 먼저 정의한다. | Merz and Blöschl (2003), Stein et al. (2020), Jiang et al. (2022) | `build_camelsh_event_response_table.py`에서 basin별 observed streamflow high-flow threshold를 넘는 독립 candidate를 추출한다. basin을 먼저 고정 type으로 나누지 않는다. |
| 2. event 주변의 hydrometeorological driver를 계산한다. | Stein et al. (2020)은 precipitation, soil moisture, snowmelt를 쓰고, Tarasova et al. (2020)은 precipitation space-time dynamics와 antecedent state를 쓴다. | `recent_rain_6h/24h/72h`, `antecedent_rain_7d/30d`, `event_duration_hours`, `rising_time_hours`, `event_mean_temp`, `antecedent_mean_temp_7d`, basin `frac_snow`를 계산한다.    |
| 3. driver를 process 또는 event regime으로 변환한다.       | Merz and Blöschl (2003)은 expert/process typology, Stein et al. (2020)은 decision tree, Jiang et al. (2022)은 explainable ML + clustering을 쓴다.         | `degree_day_v2` rule은 해석 가능한 QA/baseline label로 두고, 모델 성능을 나눠 볼 때는 `hydromet_only_7` descriptor의 KMeans `k=3` cluster를 primary event-regime stratification으로 쓴다. |
| 4. basin 수준에서는 dominant 또는 mixture로 요약한다.  | Jiang et al. (2022), Stein et al. (2020, 2021)                                                                                                             | rule은 최다 type 비율 `0.6` 이상이면 dominant, 아니면 mixture로 둔다. ML은 top-1 share와 top-2 share를 함께 보고, 단일 basin type보다 regime composition으로 해석한다.                                                                                 |

따라서 우리 방법은 새로운 flood typology를 주장하는 것이 아니라, 선행연구의 `event-first process classification` 절차를 모델 평가 해석용으로 축약 적용한 것이다. rule-based label은 사람이 방어하기 쉬운 기준선이고, ML-based label은 event/basin 구조를 더 세밀하게 나누는 분석 도구다.

다만 우리는 그 방법을 그대로 복제하지는 않는다. 이유는 세 가지다.

첫째, 그 논문은 `annual maxima + explainable LSTM + K-means`가 classification의 핵심인데, 우리 연구의 중심은 분류 자체가 아니라 `deterministic / probabilistic 모델 비교`다.

둘째, 우리는 `CAMELSH hourly`를 쓰기 때문에 annual maxima만 보는 것보다 threshold-exceeding high-flow event candidate를 더 폭넓게 쓰는 편이 연구 목적에 맞다.

셋째, 우리는 flood generation typing을 `학습 전 강한 필터`가 아니라 `모델 결과 해석과 stratified evaluation`에 쓰려고 한다.

즉, 우리는 `same philosophy, adapted implementation`을 택한다. defense에서는 “we follow the event-first flood-generating-process literature, but use a lightweight rule-based label for QA and a data-driven event-regime clustering for model-error stratification, because our primary research question is model comparison rather than developing a new flood classification algorithm”이라고 설명하면 된다.

## 3. 분류의 기본 구조

분류는 네 단계로 진행한다.

1. `hourly streamflow에서 독립 observed high-flow event candidate 추출`
2. `각 event마다 hydrometeorological descriptor 계산`
3. `descriptor를 바탕으로 rule QA label과 ML event-regime cluster 생성`
4. `basin별로 dominant type, top-1 regime, top-2 regime composition 요약`

basin screening은 어떤 basin을 모델 비교에 넣을지 정하는 단계이고, flood generation typing은 선택된 basin들 안에서 `어떤 event가 주로 발생하는가`를 해석하는 단계다.

## 4. Event extraction

event typing의 입력은 `hourly event table`이다. 각 행은 하나의 독립 observed high-flow event candidate가 된다. event를 어떻게 추출하고 어떤 descriptor를 계산할지는 [`event_response_spec.md`](event_response_spec.md)에 고정한다.

현재 권장 설계는 `POT (peaks over threshold)` 기반이다. basin \(i\)에서 hourly discharge의 high-flow threshold를 정한 뒤, 이를 초과하는 독립 event candidate를 추출한다. extreme-focused evaluation과 연계하려면 threshold는 우선 `Q99`를 권장하고, sample 수가 부족하면 `Q95`로 완화할 수 있다. 여기서 Q-threshold는 공식 flood 판정선이 아니라 observed streamflow high-flow candidate를 잡기 위한 1차 기준이다.

event \(e\)의 독립성은 최소 inter-event separation 시간 \(\Delta t_{\mathrm{sep}}\)로 정의한다. 예를 들어 두 peak 사이가 72시간 이상 떨어지면 독립 event로 본다. 논문 본문에서는 exact separation 값을 고정하기보다 `hourly hydrograph inspection과 sensitivity check를 통해 선택했다`고 적는 것이 자연스럽다.

## 5. Event table에 들어갈 핵심 변수

각 event에 대해 최소한 아래 변수를 계산하는 것이 좋다.

- `event_start`, `event_end`, `event_peak`
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

v2 typing은 process label을 부여할 때 관측 hydrograph shape를 직접 score로 쓰지 않는다. 다만 event 자체는 관측 유량 peak에서 출발하므로, 여전히 `observed high-flow event candidate에 대한 hydrometeorological proxy typing`이지 confirmed causal attribution은 아니다.

## 6. Event type 정의

우리 연구에서는 우선 세 가지 메커니즘 축을 쓴다.

1. `recent_precipitation`
2. `antecedent_precipitation`
3. `snowmelt_or_rain_on_snow`

이 세 가지는 rule-based `degree_day_v2` label의 축이고, HESS 2022의 큰 틀과 같다. 다만 이 label은 최종 주 분석 classifier라기보다, ML event-regime 결과가 물리적으로 말이 되는지 비교하는 baseline/QA label이다.

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

이 타입은 낮은 기온 조건, snow storage, 또는 해빙기에 형성되는 event다. v2 구현에서는 `cold_season`만으로 snow event를 찍지 않고, hourly `Rainf`와 `Tair`를 daily로 집계한 뒤 1°C degree-day snow routine으로 `snow accumulation`과 `snowmelt water input`을 계산한다.

대표적 판정 신호는 아래와 같다.

- event peak date 포함 7일 동안 `degree_day_snowmelt_7d`가 basin 내부의 큰 snowmelt window에 해당한다
- 같은 7일 window 안에서 rain과 snowmelt가 모두 의미 있는 비율을 차지한다
- `degree_day_snowmelt_7d >= 1 mm`라서 작은 수치 noise가 아니다
- basin별 snowmelt p90을 계산할 valid melt window가 최소 10개 이상이다

1°C 기준은 큰 눈이 1°C에서 온다는 뜻이 아니다. Jennings et al. 계열 rain/snow partition threshold와 Stein et al., Berghuijs et al.의 large-sample snow routine 관행에 맞춘 near-freezing transition 기준이다. 따라서 `Tair <= 1°C`이면 precipitation을 snow storage로 넣고, `Tair > 1°C`이면 rain과 degree-day melt가 가능하다고 본다.

현재 `snowmelt_or_rain_on_snow`는 SWE나 snow depth를 직접 확인한 label이 아니다. `temperature + precipitation`으로 만든 degree-day snowmelt proxy class다. 따라서 본문에서는 `snowmelt/rain-on-snow proxy class`라고 쓰고, 강한 snowmelt detection claim은 피한다.

## 7. Event classification 방식

현재 rule-based 구현은 `--method degree_day_v2` decision rule이다. 과거 rank-score v1은 `--method rank_score_v1`로 남겨 둘 수 있지만, QA/baseline label의 기본값은 v2다.

첫 번째 branch는 snow-related condition이다. `rain_snowmelt_proxy`는 아래 조건을 모두 만족할 때 True다.

```text
degree_day_water_input_7d > 0
AND degree_day_snowmelt_7d >= 1 mm
AND degree_day_snowmelt_fraction_7d >= 1/3
AND degree_day_rain_fraction_7d >= 1/3
```

`snowmelt_proxy`도 AND 조건이다.

```text
degree_day_snowmelt_7d >= basin_snowmelt_7d_p90
AND degree_day_snowmelt_7d >= 1 mm
AND basin_snowmelt_valid_window_count >= 10
```

snow branch 전체는 OR다. 즉 `rain_snowmelt_proxy OR snowmelt_proxy`이면 event type은 `snowmelt_or_rain_on_snow`가 되고, 세부 subtype은 `rain_snowmelt_proxy` 또는 `snowmelt_proxy`로 남긴다.

snow branch에 걸리지 않으면 precipitation branch를 본다. `recent_rain_24h` 또는 `recent_rain_72h`가 basin별 positive rainfall rolling-window p90 이상이면 `recent_precipitation` 후보가 되고, `antecedent_rain_7d` 또는 `antecedent_rain_30d`가 basin별 p90 이상이면 `antecedent_precipitation` 후보가 된다. 두 후보가 동시에 True이면 각 ratio strength를 비교해 큰 쪽을 선택하고, strength 차이가 10% 미만이면 `low_confidence_type_flag=True`를 남긴다.

어느 branch도 만족하지 않으면 `uncertain_high_flow_candidate`로 둔다. 이 label은 event가 high-flow candidate가 아니라는 뜻이 아니라, 현재 CAMELSH forcing proxy만으로 생성 메커니즘을 방어 가능하게 특정하지 못했다는 뜻이다.

## 8. Basin-level 요약

basin \(i\)에 대해 event type 또는 event regime이 정해지면, basin별로 각 type/regime의 비율을 계산한다. rule-based label은 아래처럼 dominant/mixture hard label을 만들고, ML-based cluster는 top-1 share와 top-2 share를 함께 남긴다.

$$
p_i^{(r)} = \frac{N_i^{(r)}}{N_i}, \qquad
p_i^{(a)} = \frac{N_i^{(a)}}{N_i}, \qquad
p_i^{(s)} = \frac{N_i^{(s)}}{N_i}, \qquad
p_i^{(u)} = \frac{N_i^{(u)}}{N_i}
$$

여기서 \(N_i\)는 basin \(i\)의 전체 classified event 수이고, \(N_i^{(r)}, N_i^{(a)}, N_i^{(s)}, N_i^{(u)}\)는 각각 recent-precipitation, antecedent-precipitation, snowmelt/rain-on-snow, uncertain event 수다.

rule-based basin-level label은 아래처럼 정의한다.

- 특정 type 비율이 충분히 높으면 `dominant type basin`
- 그렇지 않으면 `mixture basin`

지금 단계에서는 hard threshold를 너무 빡빡하게 두지 않는 것이 좋다. 권장 기준은

$$
\max\left(p_i^{(r)}, p_i^{(a)}, p_i^{(s)}, p_i^{(u)}\right) \ge 0.6
$$

이면 dominant basin으로 두고, 그렇지 않으면 mixture basin으로 두는 것이다.

이 방식은 HESS 2022의 `dominant vs mixture` 철학을 유지하면서도, 현재 데이터와 샘플 수에 더 유연하다. ML-based 결과는 같은 hard threshold만 보지 말고, top-2 cluster share를 같이 본다. 현재 결과에서는 top-1 share가 `0.6` 이상인 basin은 약 절반이지만, top-2 share가 `0.8` 이상인 basin은 대부분이라서 basin을 단일 type보다 두 주요 regime의 혼합으로 설명하는 편이 더 자연스럽다.

## 9. 이 분류를 연구에서 어디에 쓰는가

이 typing은 `학습 전 basin filtering`에 쓰지 않는다. screening을 대체하는 층이 아니라, screening 이후 모델 결과 해석을 강화하는 층이다.

논문 분석에서는 ML-based event-regime cluster를 주 stratification으로 쓴다. 이유는 같은 `hydromet_only_7` feature 공간에서 ML cluster가 rule label보다 event/basin 구조를 더 잘 나누기 때문이다. 현재 선택된 `kmeans__hydromet_only_7__k3`는 silhouette `0.215`, Davies-Bouldin `1.401`, Calinski-Harabasz `9655`였고, rule label은 uncertain 포함 시 silhouette `0.127`, uncertain 제외 시 `0.146` 수준이었다. feature geometry 기준으로는 ML cluster가 더 자연스럽게 갈라진다.

반대로 rule-based label은 hard label/QA 기준으로 남긴다. rule은 basin별 top label share 평균이 `0.712`로 ML의 `0.618`보다 높고, top label share가 `0.6` 이상인 basin도 rule `74.9%`, ML `51.6%`로 rule 쪽이 더 선명하다. 그래서 “이 basin에 대표 label 하나를 붙여야 한다”는 운영 목적에는 rule이 더 방어 가능하다.

따라서 논문 문장은 아래처럼 정리한다. 모델 성능 차이, peak underestimation, regional heterogeneity를 설명할 때는 ML-based event-regime stratification을 쓴다. 단, canonical flood-generation label을 완전히 대체한다고 쓰지 않고, rule-based `degree_day_v2`를 interpretable baseline/QA label로 함께 제시한다.

결과표에서는 cluster/type별 성능을 보여줄 때 `selected_threshold_quantile`, `flood_relevance_tier`, `return_period_confidence_flag`를 함께 control한다. 예를 들어 특정 cluster에서 Model 2가 좋아 보이더라도, 그 cluster가 대부분 Q95 fallback candidate이거나 low-confidence return-period basin에 몰려 있으면 강한 결론으로 쓰지 않는다.

## 10. 현재 구현 우선순위

현재 가장 좋은 구현 순서는 아래와 같다.

1. hourly event table 생성
2. event descriptor 계산
3. `degree_day_v2` rule-based QA/baseline label 생성
4. `hydromet_only_7` feature 기반 ML event-regime clustering 적용
5. basin별 top-1 / top-2 regime composition 요약
6. 모델 결과를 ML regime별로 stratified evaluation하고, rule label로 QA/sensitivity 확인

이 순서를 지키면 classification 모듈이 연구 전체를 잡아먹지 않고, 모델 비교라는 본 주제를 유지할 수 있다. rule을 먼저 만드는 이유는 ML cluster 이름을 붙일 때 물리적 sanity check가 필요하기 때문이다. ML을 주 분석 축으로 쓰더라도, rule과 충돌하는 부분을 보면 cluster가 무엇을 뜻하는지 더 조심스럽게 해석할 수 있다.

rule-based 구현 진입점은 `scripts/build_camelsh_flood_generation_typing.py`다. 입력은 `event_response_table.csv`이고, event별 label은 `flood_generation_event_types.csv`, basin별 dominant/mixture summary는 `flood_generation_basin_summary.csv`로 쓴다. 기본 method는 `degree_day_v2`이고, `dominant_flood_generation_type`은 특정 type share가 `0.6` 이상일 때만 dominant로 두며 그보다 낮으면 `mixture`로 둔다.

## 10.1 Adopted ML event-regime clustering

현재 채택할 ML-based stratification은 `hydromet_only_7` feature set에 KMeans `k=3`을 적용한 결과다. feature는 아래 7개다.

- `recent_1d_ratio`
- `recent_3d_ratio`
- `antecedent_7d_ratio`
- `antecedent_30d_ratio`
- `snowmelt_ratio`
- `snowmelt_fraction`
- `event_mean_temp`

여기서는 hydrograph shape descriptor를 일부러 빼는 것이 좋다. 나중에 모델 오차를 설명할 때, observed hydrograph shape와 너무 직접적으로 연결된 feature가 cluster를 만들면 “모델이 어려워한 수문곡선 모양”과 “사전 hydromet driver”가 섞일 수 있기 때문이다. `hydromet_only_7`은 rainfall/snow/temperature driver 중심이라 stratified evaluation 설명이 더 깔끔하다.

cluster 이름은 현재 다음처럼 쓴다.

| ML cluster name | 해석 |
| --- | --- |
| `Recent rainfall` | rule 기준 recent precipitation과도 잘 맞는, peak 직전 rainfall signal이 뚜렷한 event regime |
| `Antecedent / multi-day rain` | rule이 recent로 크게 묶었던 event 중 일부를 누적강수·multi-day 성격으로 다시 나누는 regime |
| `Weak / low-signal hydromet regime` | 강수·snowmelt proxy signal이 모두 약하거나 혼합된 event regime. snowmelt median이 0에 가까우므로 snow-dominant라고 부르지 않는다. |

특히 세 번째 cluster는 과거 임시명처럼 `Weak-driver / snow-influenced`라고 부르면 오해가 생긴다. 저위도 basin 조사에서도 rule-based `snowmelt_or_rain_on_snow` dominant basin 자체는 실제로 산악·고위 snow fraction과 잘 맞았지만, ML weak cluster에는 낮은 snow_fraction의 저위도 basin도 많이 섞였다. 따라서 이 cluster는 `Weak / low-signal hydromet regime`처럼 보수적으로 부른다.

현재 dev 분석 진입점은 아래 스크립트들이다.

```bash
uv run scripts/dev/compare_camelsh_flood_generation_ml_variants.py
uv run scripts/dev/plot_camelsh_flood_generation_ml_variant.py
uv run scripts/dev/plot_camelsh_basin_group_maps.py
```

산출물은 `output/basin/all/archive/event_regime_variants/` 아래에 둔다. 논문용 production entry point로 승격할 때는 위 dev 스크립트의 선택값, 즉 `kmeans__hydromet_only_7__k3`와 cluster naming을 고정해서 official script로 정리한다.

## 10.2 최소 robustness checks

typing 결과를 논문에 쓰기 전에는 아래 확인을 최소로 한다.

1. `Q99-only` candidate만 사용했을 때 ML regime별 model comparison 결론이 유지되는가
2. `Q99/Q98/Q95 fallback` 전체를 사용했을 때도 결론이 유지되는가
3. rule-based `degree_day_v2` label로 같은 분석을 반복했을 때 결론 방향이 크게 충돌하지 않는가
4. `uncertain_high_flow_candidate`를 제외하거나 포함해도 rule-based sensitivity 결과가 크게 달라지지 않는가
5. ML basin summary에서 top-1만 볼 때와 top-2 composition을 볼 때 해석이 일관적인가

이 checks는 typing 자체의 절대적 정확도를 증명하는 절차가 아니다. ML event-regime stratification을 써도 main model-comparison conclusion이 특정 threshold, fallback, low-confidence event에만 의존하지 않는지 확인하는 절차다.

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
- 실험 전체 비교축과 평가 원칙은 [`../model/design.md`](../model/design.md), [`../model/experiment_protocol.md`](../model/experiment_protocol.md)에서 다룬다.
