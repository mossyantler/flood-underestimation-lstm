# Event Response Table Specification

## 서술 목적

이 문서는 DRBC + CAMELSH selected basin의 `hourly event table` 생성 규칙을 고정한다. 목적은 basin screening과 flood generation typing이 같은 event definition을 쓰게 만드는 데 있다.

## 다루는 범위

- hourly flood event 추출 규칙
- threshold, separation, boundary, descriptor 계산 규칙
- basin summary table의 최소 출력 스키마

## 다루지 않는 범위

- event type 판정 규칙 자체
- basin cohort의 최종 scoring 수식
- 모델 평가 지표 계산 규칙 전체

## 상세 서술

기본 원칙은 두 가지다. event table은 `screening`과 `typing`의 공통 입력이고, 현재 단계에서는 `설명 가능하고 재현 가능한 규칙 기반 spec`을 우선 채택한다.

`event를 어떤 메커니즘 타입으로 분류할지`는 [`flood_generation_typing.md`](flood_generation_typing.md), basin cohort를 어떤 점수로 최종 선정할지는 [`basin_screening_method.md`](basin_screening_method.md)에서 다룬다.

## 1. 적용 범위

이 spec은 현재 DRBC 기준으로 선택된 CAMELSH basin 154개 중, quality gate를 통과한 basin에 우선 적용한다. 다만 구현은 전체 selected basin에 대해 돌릴 수 있게 만들어두고, 최종 screening에서는 quality-pass basin만 사용해도 된다.

시간 해상도는 `hourly`이고, streamflow는 event extraction의 기준 시계열, precipitation과 temperature는 event descriptor 계산용 시계열이다.

## 2. Event 정의의 기본 철학

이벤트는 `streamflow peak`를 중심으로 정의한다. 즉 강수로 event를 먼저 자르는 것이 아니라, 유량에서 의미 있는 high-flow peak를 찾고, 그 peak를 설명하는 forcing window를 붙이는 구조다.

우리 연구의 관심이 `홍수 첨두 과소추정`에 있기 때문에, event table도 peak-centered여야 모델 평가와 바로 연결된다.

## 3. Threshold 규칙

### 3.1 1차 threshold

각 basin \(i\)에 대해 기본 high-flow threshold는 hourly discharge의 `Q99`로 둔다.

$$
T_i^{(1)} = Q_{0.99}(Q_{i,t})
$$

여기서 \(Q_{i,t}\)는 basin \(i\)의 hourly discharge series다.

### 3.2 fallback threshold

일부 basin에서는 Q99 기준 event 수가 너무 적을 수 있다. 따라서 아래 fallback 규칙을 둔다.

1. 기본은 `Q99`
2. 만약 Q99 event 수가 `5개 미만`이면 `Q98`
3. 그래도 event 수가 `5개 미만`이면 `Q95`

즉 basin \(i\)의 최종 threshold \(T_i\)는 아래 중 가장 높은 threshold로 정한다.

$$
T_i =
\begin{cases}
Q_{0.99}, & N_i(Q_{0.99}) \ge 5 \\
Q_{0.98}, & N_i(Q_{0.99}) < 5 \text{ and } N_i(Q_{0.98}) \ge 5 \\
Q_{0.95}, & \text{otherwise}
\end{cases}
$$

여기서 \(N_i(Q_p)\)는 해당 threshold에서 얻어지는 독립 event 수다.

이 규칙의 목적은 extreme event를 유지하면서 basin별 샘플 수가 너무 적어지는 상황을 피하는 데 있다.

## 4. Peak candidate 추출 규칙

각 basin에서 threshold \(T_i\)를 초과하는 시간대 중 local maximum를 peak candidate로 잡는다. 구현은 다음 규칙을 따른다.

1. \(Q_{i,t} > T_i\) 인 시간대를 찾는다.
2. threshold 초과 구간마다 최대 유량 시점을 peak candidate로 둔다.
3. 인접 candidate가 너무 가까우면 inter-event separation 규칙으로 병합한다.

## 5. Inter-event separation 규칙

두 peak candidate가 독립 event인지 여부는 시간 간격으로 판단한다. 기본 separation 시간은

$$
\Delta t_{\mathrm{sep}} = 72 \text{ hours}
$$

로 둔다.

즉 두 peak 시간 \(t_a, t_b\)가

$$
|t_b - t_a| < \Delta t_{\mathrm{sep}}
$$

이면 하나의 event cluster로 합치고, 그 안에서 가장 큰 peak를 대표 peak로 둔다.

72시간을 기본으로 두는 이유는 hourly flood hydrograph를 다루면서도 nearby peaks를 지나치게 많이 따로 세지 않기 위해서다. 민감도 분석에서는 48시간과 96시간도 시험할 수 있다.

## 6. Event 시작과 종료 정의

대표 peak 시간이 정해지면 event boundary를 다음처럼 잡는다.

### 6.1 Event start

peak 이전으로 거슬러 올라가면서 discharge가 threshold 아래로 내려간 마지막 시점을 기본 start로 둔다.

보다 안정적으로는 아래 둘 중 더 늦은 시점을 선택한다.

1. \(Q_{i,t} < T_i\)가 마지막으로 성립한 시점
2. peak 직전 rising limb 시작점으로 보이는 국소 최소 시점

현재 구현 단순화를 위해 1번을 기본 규칙으로 하고, 나중에 필요하면 2번을 refinement로 넣는다.

### 6.2 Event end

peak 이후로 진행하면서 discharge가 threshold 아래로 다시 내려간 첫 시점을 end로 둔다.

즉 event \(e\)의 시간 구간은

$$
[t_{e,\mathrm{start}},\; t_{e,\mathrm{end}}]
$$

가 되고, peak time은

$$
t_{e,\mathrm{peak}} \in [t_{e,\mathrm{start}},\; t_{e,\mathrm{end}}]
$$

이다.

## 7. Rainfall and antecedent windows

event descriptor 계산을 위해 강수와 온도 window를 고정한다.

### 7.1 Recent rainfall windows

event peak를 기준으로 아래 recent rainfall 누적을 계산한다.

- `recent_rain_6h`
- `recent_rain_24h`
- `recent_rain_72h`

예를 들어

$$
P_{e,i}^{(24h)} = \sum_{t=t_{e,\mathrm{peak}}-23}^{t_{e,\mathrm{peak}}} P_{i,t}
$$

처럼 계산한다.

### 7.2 Antecedent rainfall windows

peak 이전의 basin wetness proxy로 아래를 계산한다.

- `antecedent_rain_7d`
- `antecedent_rain_30d`

여기서는 recent-rainfall과 겹치지 않게 `peak 직전 24h`를 제외한 antecedent window를 권장한다. 즉

$$
P_{e,i}^{(7d,\mathrm{ant})}
=
\sum_{t=t_{e,\mathrm{peak}}-24-7\times24+1}^{t_{e,\mathrm{peak}}-24} P_{i,t}
$$

처럼 계산한다.

30일도 같은 방식으로 정의한다.

### 7.3 Temperature windows

snow-related event typing을 위해 아래를 계산한다.

- `event_mean_temp`
- `antecedent_mean_temp_7d`
- `peak_temp`

event_mean_temp는 event start부터 event end까지 평균 온도, antecedent_mean_temp_7d는 peak 직전 7일 평균 온도다.

### 7.4 Season flags

`cold_season_flag`는 peak month가 `11, 12, 1, 2, 3` 중 하나이면 True로 둔다. 이건 초기 proxy 규칙이고, 나중에 SWE 자료가 확보되면 snow-related flag를 더 직접적으로 계산할 수 있다.

## 8. Event response descriptor 정의

각 event에 대해 아래 response 변수를 계산한다.

### 8.1 Peak magnitude

- `peak_discharge`
- `unit_area_peak`

unit-area peak는

$$
q_{e,i}^{\mathrm{peak}} = \frac{Q_{e,i}^{\max}}{A_i}
$$

로 정의한다.

### 8.2 Timing and shape

- `rising_time_hours = t_{e,\mathrm{peak}} - t_{e,\mathrm{start}}`
- `event_duration_hours = t_{e,\mathrm{end}} - t_{e,\mathrm{start}} + 1`
- `recession_time_hours = t_{e,\mathrm{end}} - t_{e,\mathrm{peak}}`

### 8.3 Rising rate

기본 rising rate는

$$
\mathrm{rising\_rate}_{e,i}
=
\frac{Q_{e,i}^{\max} - Q_{i,t_{e,\mathrm{start}}}}{\max(1,\; t_{e,\mathrm{peak}} - t_{e,\mathrm{start}})}
$$

로 계산한다.

### 8.4 Event runoff coefficient

가능하면 direct runoff volume을 계산해 event runoff coefficient를 넣는다. 현재 1차 구현에서는 baseflow separation이 들어가야 하므로 optional field로 두고, 없으면 `NaN`을 허용한다.

## 9. Event table 출력 스키마

출력 파일은 `event_response_table.csv`를 기본으로 하고, 한 행이 한 event다. 최소 스키마는 아래와 같다.

### 9.1 Basin and threshold metadata

- `gauge_id`
- `gauge_name`
- `state`
- `drain_sqkm_attr`
- `selected_threshold_quantile`
- `selected_threshold_value`
- `event_id`

### 9.2 Event timing

- `event_start`
- `event_peak`
- `event_end`
- `water_year`
- `peak_month`
- `cold_season_flag`

### 9.3 Streamflow response

- `peak_discharge`
- `unit_area_peak`
- `rising_time_hours`
- `event_duration_hours`
- `recession_time_hours`
- `rising_rate`

### 9.4 Rainfall and temperature descriptors

- `recent_rain_6h`
- `recent_rain_24h`
- `recent_rain_72h`
- `antecedent_rain_7d`
- `antecedent_rain_30d`
- `peak_rain_intensity_6h`
- `event_mean_temp`
- `antecedent_mean_temp_7d`
- `peak_temp`

### 9.5 Optional hydrologic descriptors

- `event_runoff_coefficient`
- `snow_related_flag`
- `rain_on_snow_proxy`
- `api_7d`
- `api_30d`

## 10. Basin-level aggregation table

event_response_table가 만들어지면 basin별 요약 table도 같이 만든다. 이 table은 final screening과 typing 둘 다에 쓰인다.

권장 이름은 `event_response_basin_summary.csv`다.

최소 포함 컬럼은 아래와 같다.

- `gauge_id`
- `event_count`
- `annual_peak_years`
- `unit_area_peak_median`
- `unit_area_peak_p90`
- `q99_event_frequency`
- `rbi`
- `rising_time_median_hours`
- `event_duration_median_hours`
- `event_runoff_coefficient_median`

## 11. Flood generation typing과의 연결

이 spec은 [`flood_generation_typing.md`](flood_generation_typing.md)의 직접 입력 문서다. typing 문서에서 말하는 `recent_precipitation`, `antecedent_precipitation`, `snowmelt_or_rain_on_snow` 분류는 여기서 정의한 descriptor를 사용한다.

즉 역할 분담은 이렇게 본다.

- `event_response_spec.md`: event를 어떻게 자르고 어떤 숫자를 계산할지 고정
- `flood_generation_typing.md`: 계산된 숫자로 event type과 basin type을 어떻게 부여할지 정의
- `basin_screening_method.md`: basin screening 본문에서 어떤 observed-flow metric을 공식적으로 쓸지 정의

## 12. 현재 권장 구현 순서

지금 구현 순서는 아래가 가장 안정적이다.

1. threshold selection 함수 구현
2. peak candidate 추출
3. inter-event separation 적용
4. event boundary 계산
5. rainfall / temperature window 계산
6. event_response_table.csv 출력
7. basin summary table 출력
8. flood generation typing v1 적용

이 순서대로 가면 event extraction logic과 typing logic이 섞이지 않아서 디버깅이 훨씬 쉽다.

## 문서 정리

이 문서는 event를 어떻게 자르고 어떤 descriptor를 계산할지 고정하는 specification이다. basin screening과 flood generation typing은 모두 이 문서의 event definition을 공통 입력으로 써야 한다.

현재 단계에서는 규칙 기반 구현이 우선이다. 나중에 threshold나 snow proxy를 정교화하더라도, 먼저 재현 가능한 event table을 안정적으로 만드는 것이 더 중요하다.

## 관련 문서

- event descriptor를 이용한 mechanism typing은 [`flood_generation_typing.md`](flood_generation_typing.md)에서 다룬다.
- basin screening 본문에서 쓸 observed-flow metric은 [`basin_screening_method.md`](basin_screening_method.md)에서 다룬다.
- 현재 screening workflow 상태는 [`basin_analysis.md`](basin_analysis.md)에서 본다.
- 실험 전체 실행 규범은 [`../research/experiment_protocol.md`](../research/experiment_protocol.md)에서 다룬다.
