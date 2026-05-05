# Event Response Table Specification

## 서술 목적

이 문서는 DRBC + CAMELSH selected basin의 `hourly event table` 생성 규칙을 고정한다. 여기서 event는 곧바로 공식 홍수를 뜻하지 않고, 관측 유량 기준 `high-flow event candidate`를 뜻한다. 목적은 basin screening과 flood generation typing이 같은 event definition을 쓰게 만드는 데 있다.

## 다루는 범위

- hourly observed high-flow event candidate 추출 규칙
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

이벤트는 `streamflow peak`를 중심으로 정의한다. 즉 강수로 event를 먼저 자르는 것이 아니라, 관측 유량에서 의미 있는 high-flow peak candidate를 찾고, 그 peak를 설명하는 forcing window를 붙이는 구조다.

우리 연구의 관심이 `홍수 첨두 과소추정`에 있기 때문에, event table도 peak-centered여야 모델 평가와 바로 연결된다.

중요한 해석 원칙은 `Q99 exceedance`만으로는 공식 flood라고 부르지 않는다는 점이다. Q99는 precipitation threshold가 아니라 basin별 observed streamflow threshold이므로, 비가 많이 왔지만 유량이 오르지 않은 경우는 event로 잡히지 않는다. 하지만 상위 1% 유량이라고 해서 반드시 flood damage 또는 official flood stage를 의미하지도 않는다. 따라서 1차 산출물은 `Q99/Q98/Q95 observed high-flow event candidate`로 부르고, flood-like severity는 `unit_area_peak`, annual peak relevance, return-period proxy ratio, hydrograph shape를 이용해 별도로 해석한다.

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

이 규칙의 목적은 extreme event를 유지하면서 basin별 샘플 수가 너무 적어지는 상황을 피하는 데 있다. 선택된 threshold가 `Q99`면 가장 엄격한 high-flow candidate이고, `Q98` 또는 `Q95` fallback이면 event sample 확보를 위해 완화된 high-flow candidate다. 이 차이는 `selected_threshold_quantile`에 남기며, 이후 결과 해석에서 함께 본다.

### 3.3 해석과 sensitivity 원칙

`selected_threshold_quantile`은 단순한 처리 로그가 아니라 해석 변수다. Q99로 잡힌 candidate와 Q95 fallback으로 잡힌 candidate는 같은 강도의 event sample이라고 보면 안 된다. 따라서 결과표와 그림에서는 가능하면 아래 세 가지를 같이 확인한다.

- 전체 `Q99/Q98/Q95 fallback` candidate 기준 결과
- `Q99-only` candidate 기준 결과
- `selected_threshold_quantile`을 control 또는 stratification 변수로 둔 결과

이 세 결과에서 Model 1 / Model 2의 핵심 결론이 크게 달라지지 않으면, Q-threshold 선택에 대한 defense가 훨씬 강해진다.

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
- `degree_day_rain_7d`
- `degree_day_snowmelt_7d`
- `degree_day_water_input_7d`
- `degree_day_snowmelt_fraction_7d`
- `degree_day_rain_fraction_7d`
- `basin_snowmelt_7d_p90`
- `basin_snowmelt_valid_window_count`
- `basin_rain_1d_p90`
- `basin_rain_3d_p90`
- `basin_rain_7d_p90`
- `basin_rain_30d_p90`

event_mean_temp는 event start부터 event end까지 평균 온도, antecedent_mean_temp_7d는 peak 직전 7일 평균 온도다.

`peak_rain_intensity_6h`는 현재 1차 구현에서는 `peak 포함 직전 6시간 window` 안에서의 최대 hourly rainfall 값으로 둔다. 즉 recent-rain window와 같은 시간 범위를 보되, 총량이 아니라 짧은 고강도 forcing proxy를 따로 기록하는 용도다.

### 7.4 Season flags

`cold_season_flag`는 peak month가 `11, 12, 1, 2, 3` 중 하나이면 True로 둔다. 이 값은 해석용 metadata로 남기되, v2 snow-related typing의 직접 판정 기준은 아래 degree-day snowmelt proxy다.

`water_year`는 미국 수문학 관례를 따라 `10월~다음 해 9월`을 한 해로 본다. 즉 `10, 11, 12월` peak는 다음 calendar year의 water year로 기록한다.

### 7.5 Degree-day snowmelt proxy

snow-related event를 유량이나 계절만으로 찍지 않기 위해, CAMELSH hourly `Rainf`와 `Tair`에서 daily degree-day snow routine을 계산한다. 기본값은 `Tcrit = 1°C`, degree-day factor `2.0 mm/day/°C`다.

daily 평균 기온이 `1°C` 이하이면 그날 precipitation은 snow storage에 더하고, `1°C`보다 높으면 precipitation은 rain으로 보고 snowpack에서 `2.0 * (Tair_daily - 1°C)`만큼 melt potential을 계산한다. 실제 snowmelt는 남아 있는 snowpack을 넘지 못한다.

event table에는 peak date를 포함한 7일 window 기준으로 아래 값을 남긴다.

- `degree_day_rain_7d`
- `degree_day_snowmelt_7d`
- `degree_day_water_input_7d`
- `degree_day_snowmelt_fraction_7d`
- `degree_day_rain_fraction_7d`
- `basin_snowmelt_7d_p90`
- `basin_snowmelt_valid_window_count`
- `basin_rain_1d_p90`, `basin_rain_3d_p90`, `basin_rain_7d_p90`, `basin_rain_30d_p90`

`basin_snowmelt_7d_p90`는 `degree_day_snowmelt_7d >= 1 mm`인 rolling window가 최소 10개 이상 있을 때만 신뢰한다. rainfall p90 값도 positive rolling rainfall window를 기준으로 계산해, rainfall이 거의 없는 basin에서 0 threshold가 생기는 것을 피한다.

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

### 8.5 Recurrence-period reference ratios and flood-like severity tier

재현기간별 강수량과 홍수량은 event extraction threshold가 아니라 event 해석용 reference descriptor다. basin-level table에 `prec_ari*`와 `flood_ari*`가 준비되어 있으면, event table에는 event가 해당 basin의 reference extreme scale에 비해 어느 정도였는지를 나타내는 ratio를 추가할 수 있다.

권장 ratio는 아래와 같다.

- `peak_to_flood_ari2`, `peak_to_flood_ari5`, `peak_to_flood_ari10`, `peak_to_flood_ari25`, `peak_to_flood_ari50`, `peak_to_flood_ari100`
- `recent_rain_1h_to_prec_ari100_1h`
- `recent_rain_6h_to_prec_ari100_6h`
- `recent_rain_24h_to_prec_ari100_24h`
- `recent_rain_72h_to_prec_ari100_72h`

강수 reference duration은 `1h / 6h / 24h / 72h`로 고정한다. `1h`는 `peak_rain_intensity_6h`에서 쓰는 최대 hourly intensity와 연결하고, 나머지 duration은 recent rainfall descriptor인 `recent_rain_6h`, `recent_rain_24h`, `recent_rain_72h`와 맞춘다. 즉 `24h`는 설명하기 쉬운 대표 duration일 뿐이며, event response 해석에서는 네 duration을 같이 사용한다.

여기서 `flood_ari*`는 가능하면 USGS annual peak / Bulletin 17C 계열 reference를 쓰고, 없으면 CAMELSH hourly annual maximum 기반 proxy로 둔다. `prec_ari*`도 장기적으로는 NOAA Atlas 14 / PFDS duration별 precipitation frequency estimate를 붙이는 것이 가장 좋지만, 현재 서버 구현은 CAMELSH hourly forcing에서 duration별 rolling annual maximum 기반 proxy를 먼저 만든다. 이 값들은 `Q99` threshold나 Model 2의 `q99`와 다른 개념이므로, column name에는 `flood_ari`와 `prec_ari`를 명시하고 `*_source`, `return_period_confidence_flag`를 함께 남겨 혼동을 줄인다.

return-period ratio가 있으면 `flood_relevance_tier`도 함께 기록한다. 이 값은 공식 flood 인증이 아니라, Q-threshold candidate가 flood-like scale에 얼마나 가까운지를 읽기 위한 보조 label이다.

| `flood_relevance_tier` | 의미 |
| --- | --- |
| `high_flow_candidate_unrated` | return-period reference가 없거나 ratio를 계산할 수 없어 Q-threshold high-flow candidate로만 해석한다. |
| `high_flow_below_2yr_proxy` | Q-threshold event이지만 CAMELSH hourly proxy 기준 2년 홍수량에는 못 미친다. flood-like severity가 약할 수 있으므로 조심해서 해석한다. |
| `flood_like_ge_2yr_proxy`, `flood_like_ge_5yr_proxy`, ... | 해당 return-period proxy 이상인 event다. 이때도 공식 NOAA/USGS flood frequency가 아니라 CAMELSH hourly annual-maxima proxy임을 함께 적는다. |

논문 문장에서는 `2-year flood event`처럼 단정하지 않고, `CAMELSH hourly annual-maxima proxy 기준 2-year scale 이상`처럼 쓴다. 같은 CAMELSH record로 reference와 event ratio를 모두 만들기 때문에, 이 값은 independent validation이 아니라 in-sample scale comparison이다. `return_period_confidence_flag`, `flood_ari_source`, `prec_ari_source`를 항상 같이 보고해야 한다.

## 9. Event table 출력 스키마

출력 파일은 `event_response_table.csv`를 기본으로 하고, 한 행이 한 observed high-flow event candidate다. 최소 스키마는 아래와 같다.

### 9.1 Basin and threshold metadata

- `gauge_id`
- `gauge_name`
- `state`
- `drain_sqkm_attr`
- `selected_threshold_quantile`
- `selected_threshold_value`
- `event_detection_basis`
- `event_candidate_label`
- `flood_relevance_tier`
- `flood_relevance_basis`
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

### 9.6 Optional recurrence-period descriptors

- `peak_to_flood_ari2`
- `peak_to_flood_ari5`
- `peak_to_flood_ari10`
- `peak_to_flood_ari25`
- `peak_to_flood_ari50`
- `peak_to_flood_ari100`
- `recent_rain_1h_to_prec_ari100_1h`
- `recent_rain_6h_to_prec_ari100_6h`
- `recent_rain_24h_to_prec_ari100_24h`
- `recent_rain_72h_to_prec_ari100_72h`

## 10. Basin-level aggregation table

event_response_table가 만들어지면 basin별 요약 table도 같이 만든다. 이 table은 final screening과 typing 둘 다에 쓰인다.

권장 이름은 `event_response_basin_summary.csv`다.

최소 포함 컬럼은 아래와 같다.

- `gauge_id`
- `event_count`
- `flood_like_ge_2yr_proxy_event_count`
- `high_flow_below_2yr_proxy_event_count`
- `high_flow_candidate_unrated_event_count`
- `annual_peak_years`
- `unit_area_peak_median`
- `unit_area_peak_p90`
- `q99_event_frequency`
- `rbi`
- `rising_time_median_hours`
- `event_duration_median_hours`
- `event_runoff_coefficient_median`

재현기간별 reference descriptor가 준비되어 있으면 아래 컬럼을 basin-level aggregation table에 optional로 붙인다.

- `prec_ari2_1h`, `prec_ari5_1h`, `prec_ari10_1h`, `prec_ari25_1h`, `prec_ari50_1h`, `prec_ari100_1h`
- `prec_ari2_6h`, `prec_ari5_6h`, `prec_ari10_6h`, `prec_ari25_6h`, `prec_ari50_6h`, `prec_ari100_6h`
- `prec_ari2_24h`, `prec_ari5_24h`, `prec_ari10_24h`, `prec_ari25_24h`, `prec_ari50_24h`, `prec_ari100_24h`
- `prec_ari2_72h`, `prec_ari5_72h`, `prec_ari10_72h`, `prec_ari25_72h`, `prec_ari50_72h`, `prec_ari100_72h`
- `flood_ari2`, `flood_ari5`, `flood_ari10`, `flood_ari25`, `flood_ari50`, `flood_ari100`
- `flood_ari_source`
- `prec_ari_source`
- `return_period_record_years`
- `return_period_confidence_flag`

현재 서버용 구현에서는 `scripts/basin/all/build_camelsh_return_period_references.py`가 hourly `.nc` 전체를 읽어 이 reference descriptor를 먼저 만든다. 기본 방법은 water-year annual maxima에 대한 `gumbel` frequency estimate이고, 강수 duration은 `1h / 6h / 24h / 72h`, return period는 `2 / 5 / 10 / 25 / 50 / 100년`이다. 이 값은 공식 NOAA/USGS frequency product가 아니라 CAMELSH hourly record 기반 proxy이므로, 산출물에는 `flood_ari_source`, `prec_ari_source`, `return_period_confidence_flag`를 함께 남긴다.

USGS 기준 peak-flow reference는 `scripts/basin/reference/fetch_usgs_streamstats_peak_flow_references.py`로 StreamStats/GageStats `Peak-Flow Statistics`를 가져와 `return_period_reference_table_with_usgs.csv`에 `usgs_flood_ari*` 컬럼으로 붙인다. 이 값은 기존 CAMELSH proxy를 지우는 replacement가 아니라 side-by-side reference이며, citation provenance는 `usgs_streamstats_peak_flow_citations.csv`에 보관한다.

NOAA 기준 precipitation-frequency point reference는 `scripts/basin/reference/fetch_noaa_atlas14_precip_references.py`로 PFDS point estimate를 CAMELSH gauge/outlet 좌표에서 가져와 `noaa14_ams_prec_ari*_*h`와 `noaa14_pds_prec_ari*_*h` 컬럼으로 붙인다. `AMS`는 기존 annual-maxima proxy와 직접 비교하는 primary reference이고, `PDS`는 supplementary/design reference다. 이 값도 기존 `prec_ari*`를 자동 대체하지 않고 side-by-side로 둔다.

CAMELSH forcing과 공간 기준을 맞춘 비교에는 `scripts/basin/reference/fetch_noaa_precip_gridmean_references.py`가 만든 `noaa14_gridmean_*` 컬럼을 사용한다. 이 값은 CAMELSH shapefile로 NLDAS basin mask cell을 재구성한 뒤 NOAA Atlas 14 GIS grid를 cell 좌표에서 샘플링해 평균한 것이다. Oregon/Washington HUC02=17처럼 Atlas 14 project area 밖인 basin은 `outside_atlas14_project_area`로 기록하고, NOAA Atlas 2가 제공하는 `2/100-year 6/24h` 조합만 `noaa2_gridmean_*` fallback으로 둔다.

`scripts/basin/reference/apply_noaa_areal_reduction_references.py`는 gridmean NOAA reference에 duration별 basin-area areal reduction factor를 적용해 `noaa14_areal_arf_*`와 `noaa2_areal_arf_*` 컬럼을 추가한다. 이 값은 point/grid precipitation-frequency depth를 basin-average storm depth 쪽으로 낮춰 보는 supplementary comparison이며, HEC-HMS TP-40/TP-49 curve를 근사 적용한 것이므로 공식 NOAA product로 쓰지 않는다.

이때 `prec_ari*`와 `noaa14_gridmean_*`, `noaa14_areal_arf_*`가 같은 basin mask를 쓰더라도 같은 물리량은 아니다. CAMELSH `prec_ari*`는 NLDAS hourly grid를 먼저 basin 평균한 뒤 그 평균 시계열의 rolling annual maxima에 Gumbel을 맞춘 값이고, NOAA 계열 컬럼은 NOAA가 이미 frequency analysis를 끝낸 point/grid precipitation-frequency depth를 basin mask 위치에서 평균하거나 areal factor로 낮춘 값이다. 평균과 return-level 계산은 교환되지 않으므로, event table의 `recent_rain_*_to_prec_ari*`는 모델 입력 forcing 기준 severity ratio로 해석하고, NOAA 컬럼은 공식 설계강우 reference와의 side-by-side 비교나 sensitivity reference로만 사용한다.

`scripts/basin/all/build_camelsh_event_response_table.py`는 reference table이 있으면 flood peak ratio와 precipitation ratio를 모든 configured return period에 대해 붙인다. 즉 spec의 `ari100` precipitation ratio는 최소 해석용 컬럼이고, 서버 산출물에는 `recent_rain_{duration}h_to_prec_ari{period}_{duration}h` 형식의 전체 return-period ratio가 함께 들어갈 수 있다.

## 10.1 필수 해석 컬럼

event-response 산출물을 모델 결과와 결합할 때는 아래 컬럼을 항상 같이 남긴다.

- `selected_threshold_quantile`: Q99-only 결과와 fallback 포함 결과를 구분하기 위한 기준
- `event_candidate_label`: official flood inventory가 아니라 observed high-flow candidate임을 명시
- `flood_relevance_tier`: candidate의 flood-like severity proxy
- `return_period_confidence_flag`: return-period proxy의 record-length 신뢰도
- `flood_ari_source`, `prec_ari_source`: official product인지 CAMELSH proxy인지 구분

이 컬럼들이 빠진 summary table은 논문용 최종표가 아니라 중간 분석표로만 취급한다.

## 11. Flood generation typing과의 연결

이 spec은 [`flood_generation_typing.md`](flood_generation_typing.md)의 직접 입력 문서다. typing 문서에서 말하는 `recent_precipitation`, `antecedent_precipitation`, `snowmelt_or_rain_on_snow` 분류는 여기서 정의한 descriptor를 사용한다.

즉 역할 분담은 이렇게 본다.

- `event_response_spec.md`: event를 어떻게 자르고 어떤 숫자를 계산할지 고정
- `flood_generation_typing.md`: 계산된 숫자로 event type과 basin type을 어떻게 부여할지 정의
- `basin_screening_method.md`: basin screening 본문에서 어떤 observed-flow metric을 공식적으로 쓸지 정의

## 12. 현재 권장 구현 순서

지금 구현 순서는 아래가 가장 안정적이다.

1. `scripts/basin/all/build_camelsh_return_period_references.py`로 `return_period_reference_table.csv` 생성
2. threshold selection 함수 구현
3. peak candidate 추출
4. inter-event separation 적용
5. event boundary 계산
6. rainfall / temperature window 계산
7. `scripts/basin/all/build_camelsh_event_response_table.py`로 `event_response_table.csv`와 basin summary 출력
8. `scripts/basin/all/build_camelsh_flood_generation_typing.py`로 degree-day 기반 rule QA/baseline typing v2 적용
9. 모델 결과 해석 단계에서는 `hydromet_only_7 + KMeans(k=3)` ML event-regime stratification을 별도로 붙이고, rule label은 sanity check로 함께 확인

이 순서대로 가면 event extraction logic과 typing logic이 섞이지 않아서 디버깅이 훨씬 쉽다.

서버에서는 `.nc` rsync 완료 뒤 `scripts/runs/official/run_camelsh_flood_analysis.sh`를 실행하면 위 세 Python 단계를 순서대로 돌린다. 기본 산출물 위치는 `output/basin/all/analysis/`이고, 기본 worker 수는 `WORKERS=4`다. `TIMESERIES_DIR`, `OUTPUT_DIR`, `WORKERS`, `BASIN_LIST`, `LIMIT` 환경변수로 실행 범위를 조절할 수 있고, 이미 만들어 둔 return-period reference를 재사용할 때는 `RUN_RETURN_PERIOD=0`으로 event response와 typing만 다시 돌릴 수 있다.

## 문서 정리

이 문서는 event를 어떻게 자르고 어떤 descriptor를 계산할지 고정하는 specification이다. basin screening과 flood generation typing은 모두 이 문서의 event definition을 공통 입력으로 써야 한다.

현재 단계에서는 재현 가능한 event table을 안정적으로 만드는 것이 우선이다. rule-based typing과 ML-based event-regime clustering은 모두 이 event table을 공통 입력으로 쓰므로, 나중에 threshold나 snow proxy를 정교화하더라도 event extraction logic과 해석 logic은 분리해서 유지한다.

## 관련 문서

- event descriptor를 이용한 mechanism typing은 [`flood_generation_typing.md`](flood_generation_typing.md)에서 다룬다.
- basin screening 본문에서 쓸 observed-flow metric은 [`basin_screening_method.md`](basin_screening_method.md)에서 다룬다.
- 현재 screening workflow 상태는 [`basin_analysis.md`](basin_analysis.md)에서 본다.
- 실험 전체 실행 규범은 [`../model/experiment_protocol.md`](../model/experiment_protocol.md)에서 다룬다.
