# Flood Generation Typing Literature

이 폴더는 flood generation type과 event 분류법을 검토하기 위한 공개 PDF와 citation index를 모아 둔 참고 자료 폴더다. 공식 방법론의 source of truth는 [`../../../experiment/method/basin/flood_generation_typing.md`](../../../experiment/method/basin/flood_generation_typing.md)와 [`../../../experiment/method/basin/event_response_spec.md`](../../../experiment/method/basin/event_response_spec.md)를 기준으로 본다.

## Downloaded PDFs

| 파일 | 문헌 | 분류법에서 중요한 점 | Source |
| --- | --- | --- | --- |
| [`jiang_2022_hess_river_flooding_mechanisms_explainable_ml.pdf`](jiang_2022_hess_river_flooding_mechanisms_explainable_ml.pdf) | Jiang, Bevacqua, and Zscheischler (2022), HESS | `recent precipitation`, `antecedent precipitation`, `snowmelt` 세 mechanism을 explainable ML과 clustering으로 식별한다. 현재 CAMELSH typing의 3분류 이름과 가장 직접적으로 연결된다. 상세 해설은 [`jiang_2022_hess_explainable_ml_study_notes.md`](jiang_2022_hess_explainable_ml_study_notes.md)를 본다. | [HESS PDF](https://hess.copernicus.org/articles/26/6339/2022/hess-26-6339-2022.pdf) |
| [`tarasova_2019_wires_causative_classification_river_flood_events.pdf`](tarasova_2019_wires_causative_classification_river_flood_events.pdf) | Tarasova et al. (2019), WIREs Water | flood event causative classification review다. hydroclimatic, hydrological, hydrograph-based 관점을 정리해 flood typing의 이론적 배경으로 쓴다. | [Author PDF](https://hannesmueller.eu/downloads/TarasovaEtAl%282019%29-WIREs.pdf) |
| [`stein_2020_hyp_event_based_classification_global_flood_generating_processes.pdf`](stein_2020_hyp_event_based_classification_global_flood_generating_processes.pdf) | Stein, Pianosi, and Woods (2020), Hydrological Processes | precipitation, simple soil moisture, snowmelt 기반 decision tree로 `short rain`, `long rain`, `excess rainfall`, `snowmelt`, `rain/snow`를 분류한다. | [Bristol PDF](https://research-information.bris.ac.uk/ws/files/220895815/Stein_et_al_2020_Hydrological_Processes.pdf) |
| [`tarasova_2020_wrr_event_typology_germany.pdf`](tarasova_2020_wrr_event_typology_germany.pdf) | Tarasova et al. (2020), Water Resources Research | precipitation의 space-time dynamics와 antecedent state를 dimensionless indicator로 표현해 process-based event typology를 만든다. | [GFZ PDF](https://gfzpublic.gfz.de/pubman/item/item_5001918_4/component/file_5001936/5001918.pdf) |
| [`stein_2021_wrr_climate_catchment_attributes_conus.pdf`](stein_2021_wrr_climate_catchment_attributes_conus.pdf) | Stein et al. (2021), Water Resources Research | CONUS 671개 유역에서 climate/catchment attributes와 flood generating process의 관계를 분석한다. CAMELSH 미국 유역 해석에 특히 관련 있다. 상세 해설은 [`stein_2021_wrr_climate_catchment_attributes_conus_study_notes.md`](stein_2021_wrr_climate_catchment_attributes_conus_study_notes.md), 학부생용 해설은 [`stein_2021_wrr_climate_catchment_attributes_conus_undergrad_notes.md`](stein_2021_wrr_climate_catchment_attributes_conus_undergrad_notes.md)를 본다. | [Bristol PDF](https://research-information.bris.ac.uk/ws/portalfiles/portal/299812236/Full_text_PDF_final_published_version_.pdf) |
| [`1-s2.0-S0022169417301476-main.pdf`](1-s2.0-S0022169417301476-main.pdf) | Saharia et al. (2017), Journal of Hydrology | NWS action stage 초과 flood archive로 CONUS flood의 `unit peak discharge`, `flooding rise time`, seasonality를 climate/physiography별로 특성화한다. CAMELSH에서는 mechanism typing보다 high-flow response descriptor와 screening 근거로 쓴다. 상세 해설은 [`saharia_2017_jhydrol_characterization_floods_us_study_notes.md`](saharia_2017_jhydrol_characterization_floods_us_study_notes.md)를 본다. | [DOI](https://doi.org/10.1016/j.jhydrol.2017.03.010) |
| [`berghuijs_2016_grl_dominant_flood_generating_mechanisms_us.pdf`](berghuijs_2016_grl_dominant_flood_generating_mechanisms_us.pdf) | Berghuijs, Woods, Hutton, and Sivapalan (2016), Geophysical Research Letters | 미국 전역에서 rainfall-only 설명이 부족하고 soil moisture, snowmelt, rain-on-snow가 flood response 설명에 중요함을 보인다. | [Bristol PDF](https://research-information.bris.ac.uk/ws/portalfiles/portal/65553459/Wouter_785405_1_merged_1456314410.pdf) |
| [`berghuijs_2019_wrr_relative_importance_flood_generating_mechanisms_europe.pdf`](berghuijs_2019_wrr_relative_importance_flood_generating_mechanisms_europe.pdf) | Berghuijs et al. (2019), Water Resources Research | Europe에서 extreme precipitation, soil moisture excess, snowmelt의 상대적 중요도를 추정한다. basin-level dominant mechanism 해석에 참고한다. | [WSL PDF](https://www.dora.lib4ri.ch/wsl/islandora/object/wsl%3A21998/datastream/PDF/Berghuijs-2019-The_relative_importance_of_different-%28published_version%29.pdf) |
| [`tramblay_2022_scirep_classification_flood_generating_processes_africa.pdf`](tramblay_2022_scirep_classification_flood_generating_processes_africa.pdf) | Tramblay et al. (2022), Scientific Reports | Africa large-sample 환경에서 `excess rain`, `long rain`, `short rain`으로 단순화한다. 데이터 불확실성이 큰 경우 단순하고 robust한 분류가 필요하다는 근거로 쓴다. | [Nature PDF](https://www.nature.com/articles/s41598-022-23725-5.pdf) |

## Link-Only Reference

| 문헌 | 이유 | Link |
| --- | --- | --- |
| Merz and Blöschl (2003), *A process typology of regional floods*, Water Resources Research | 고전적인 5분류(`long-rain`, `short-rain`, `flash`, `rain-on-snow`, `snowmelt`) 문헌이지만, 공개 PDF 경로를 확인하지 못했다. 출판사 권한이 애매하므로 PDF를 저장하지 않고 citation과 DOI만 남긴다. | [EarthRef abstract](https://earthref.org/ERR/70377/), [DOI](https://doi.org/10.1029/2002WR001952) |

## Mapping To Current CAMELSH Typing

| 현재 label | 주요 선행연구 표현 | CAMELSH 구현에서의 해석 |
| --- | --- | --- |
| `recent_precipitation` | recent precipitation, short rain, flash flood | peak 직전 6-24시간 강수가 크고 rising time이 짧은 event다. |
| `antecedent_precipitation` | antecedent precipitation, soil moisture excess, excess rainfall, long rain | 7-30일 선행강수와 긴 duration이 중요한 event다. 관측 soil moisture가 없으므로 antecedent rainfall을 proxy로 쓴다. |
| `snowmelt_or_rain_on_snow` | snowmelt, rain-on-snow, rain/snowmelt | event peak 포함 7일 window의 `Rainf`와 `Tair`로 계산한 1°C degree-day snowmelt proxy가 있는 event다. CAMELSH hourly forcing에 SWE가 없으므로 보수적 통합 label로 둔다. |
| `uncertain_high_flow_candidate` | unclassified or mixed high-flow candidate | high-flow event candidate는 맞지만 현재 forcing proxy만으로 recent, antecedent, snow-related mechanism을 방어 가능하게 특정하지 못한 event다. |

## Defense Logic

논문 defense에서는 `우리 typing은 새로운 flood typology 제안이 아니라, 선행연구 절차를 CAMELSH hourly data에 맞춘 해석용 proxy`라고 설명하는 편이 안전하다.

| 선행연구에서 한 일 | 우리도 한 일 | 왜 이렇게 단순화했는가 |
| --- | --- | --- |
| flood event 또는 high-flow event candidate를 먼저 분리했다. | hourly `Streamflow`에서 basin별 high-flow threshold를 넘는 독립 candidate를 먼저 추출했다. | 같은 basin에서도 event마다 생성 메커니즘이 달라질 수 있으므로 basin-first typing보다 event-first typing이 안전하다. |
| event 전후의 driver를 계산했다. | recent rainfall, antecedent rainfall, temperature 기반 degree-day snowmelt proxy를 계산했다. | CAMELSH hourly `.nc`에서 안정적으로 공통 계산 가능한 변수만 사용해야 전 유역에 적용할 수 있다. |
| driver를 process label로 바꿨다. | 1°C degree-day snowmelt proxy와 basin별 positive rainfall p90 decision rule로 `recent_precipitation`, `antecedent_precipitation`, `snowmelt_or_rain_on_snow`, `uncertain_high_flow_candidate`를 부여했다. | classification 자체가 main contribution이 아니므로 explainable하고 재현 가능한 lightweight proxy를 택했다. |
| basin은 event label의 비율로 요약했다. | dominant type share가 `0.6` 이상이면 dominant basin, 아니면 `mixture` basin으로 둔다. | 많은 유역은 하나의 고정 메커니즘이 아니라 여러 mechanism이 섞이므로 mixture를 허용해야 한다. |

권장 defense 문장은 아래와 같다.

```text
Following event-based flood-generating-process studies, we first define independent observed high-flow event candidates, calculate hydrometeorological descriptors around each event, assign an event-level process label, and then summarize the event labels at the basin level. Because our main contribution is not a new flood typology, we use a transparent proxy classification based on recent rainfall, antecedent rainfall, and a degree-day snowmelt proxy derived from event-window precipitation and temperature.
```

## Analysis Caveats

| 항목 | 방어 가능한 표현 | 피해야 할 표현 |
| --- | --- | --- |
| Q99/Q98/Q95 event | observed high-flow event candidate | official flood event |
| return-period ratio | CAMELSH hourly annual-maxima proxy 기준 relative severity | NOAA/USGS confirmed return period |
| `flood_relevance_tier` | flood-like severity proxy | flood occurrence certification |
| current typing | hydrometeorological proxy typing for observed high-flow candidates | confirmed causal attribution |
| snow-related type | degree-day snowmelt/rain-on-snow proxy class | confirmed snowmelt event |

최소 robustness check는 세 가지다.

1. `Q99-only` candidate와 fallback 포함 전체 candidate에서 main model-comparison conclusion이 유지되는지 확인한다.
2. `selected_threshold_quantile`, `flood_relevance_tier`, `return_period_confidence_flag`를 결과표에 항상 포함한다.
3. type별 해석을 쓰려면 `uncertain_high_flow_candidate` 포함/제외와 Q99-only/fallback 포함 결과에서 main conclusion이 유지되는지 비교한다.
