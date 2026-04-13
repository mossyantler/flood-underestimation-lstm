# Basin Source CSV Guide

## 서술 목적

이 문서는 DRBC + CAMELSH workflow에서 basin 분석 테이블을 구성하는 source CSV와 주요 컬럼의 뜻을 정리한다. 핵심은 분석 테이블의 각 열이 어떤 원본 파일에서 왔고, 어떤 수문학적 의미를 가지는지 빠르게 확인할 수 있게 만드는 것이다.

## 다루는 범위

- basin analysis table을 구성하는 source CSV 목록
- 각 CSV의 대표 컬럼과 해석 방법
- 정적 분석 테이블을 읽는 기본 순서와 주의사항

## 다루지 않는 범위

- basin subset 선택 규칙 자체
- 현재 screening workflow의 진행 상태
- 논문 본문용 공식 screening 수식

## 상세 서술

현재 기준 분석 테이블은 [`drbc_selected_basin_analysis_table.csv`](../../output/basin/drbc_camelsh/analysis/drbc_selected_basin_analysis_table.csv)이며, 아래 8개 source CSV를 병합해 만든다.

| # | Source CSV | 역할 |
|---|---|---|
| 1 | [`camelsh_drbc_selected.csv`](../../output/basin/drbc_camelsh/camelsh_drbc_selected.csv) | basin selection / 행 정의 |
| 2 | [`attributes_gageii_BasinID.csv`](../../basins/CAMELSH_data/attributes/attributes_gageii_BasinID.csv) | basin 식별 메타데이터 |
| 3 | [`attributes_gageii_Topo.csv`](../../basins/CAMELSH_data/attributes/attributes_gageii_Topo.csv) | 지형 특성 |
| 4 | [`attributes_nldas2_climate.csv`](../../basins/CAMELSH_data/attributes/attributes_nldas2_climate.csv) | 기후 요약 |
| 5 | [`attributes_gageii_Hydro.csv`](../../basins/CAMELSH_data/attributes/attributes_gageii_Hydro.csv) | 수문 응답 및 하천망 |
| 6 | [`attributes_gageii_Soils.csv`](../../basins/CAMELSH_data/attributes/attributes_gageii_Soils.csv) | 토양 특성 |
| 7 | [`attributes_gageii_Geology.csv`](../../basins/CAMELSH_data/attributes/attributes_gageii_Geology.csv) | 지질 배경 |
| 8 | [`attributes_gageii_LC06_Basin.csv`](../../basins/CAMELSH_data/attributes/attributes_gageii_LC06_Basin.csv) | 토지피복 (NLCD 2006) |

---

## 분석의 세 층 구조

분석 변수는 세 층으로 읽는다.

| 층 | 담당 CSV | 핵심 질문 |
|---|---|---|
| **Forcing** | Climate | 얼마나 강한 물 공급이 오는가? |
| **Structure** | Topo · Soils · Geology · Land Cover | 그 물을 얼마나 빨리 유출로 전환하는가? |
| **Response** | Hydro | 실제로 하천이 어떻게 반응했는가? |

> Forcing이 강해도 Structure가 완충형이면 flood 성향이 억제될 수 있다. 세 층을 같이 봐야 한다.

---

## 1. Selection / Mapping CSV

[`camelsh_drbc_selected.csv`](../../output/basin/drbc_camelsh/camelsh_drbc_selected.csv)는 attribute 파일이 아니라 분석 테이블의 **행(row)을 결정하는 entry table**이다.

| 컬럼 | 의미 | 해석 방법 |
|---|---|---|
| `gauge_id` | CAMELSH basin ID / gauge ID | 모든 attribute CSV 병합의 기준 키 |
| `gauge_name` | 관측소 이름 | basin 식별용 |
| `state` | 관측소 주(state) | 지역 분포 확인용 |
| `lat_gage`, `lng_gage` | gauge 위경도 | outlet spatial join 및 지도 확인 기준 |
| `drain_sqkm_attr` | BasinID 메타데이터 기준 면적 | 속성 테이블 기준 면적 |
| `basin_area_sqkm_geom` | polygon geometry에서 계산한 면적 | 메타데이터 면적 대비 QC 값 |
| `overlap_ratio_of_basin` | DRBC region과의 polygon overlap 비율 | **현재 selection rule의 핵심 — 0.9 이상만 공식 subset에 포함** |
| `selection_reason` | 선택 근거 | 현재 공식 조건은 `outlet_in_drbc_and_overlap_gte_0.90` |

---

## 2. BasinID CSV

[`attributes_gageii_BasinID.csv`](../../basins/CAMELSH_data/attributes/attributes_gageii_BasinID.csv)는 basin의 식별 정보와 outlet 메타데이터를 담는다. 설명 변수라기보다 **병합 기준 정보**에 가깝다.

| 컬럼 | 의미 | 해석 방법 |
|---|---|---|
| `STAID` | basin/gauge 고유 ID | 모든 CSV 병합 키 |
| `STANAME` | 관측소 이름 | basin 식별용 |
| `DRAIN_SQKM` | 배수면적(km²) | basin 규모의 기본 reference 값 |
| `HUC02` | 상위 hydrologic region 코드 | 지역 grouping용 |
| `LAT_GAGE`, `LNG_GAGE` | gauge 위경도 | outlet 기준 공간 매칭 기준 |
| `STATE` | 주(state) | 주별 분포 확인용 |
| `BOUND_SOURCE` | basin 경계의 출처 | polygon source 추적용 |

`DRAIN_SQKM`는 basin 규모를 나타내므로, slope나 runoff response를 해석할 때 반드시 함께 읽어야 한다. 같은 `high_q_freq`라도 소유역과 대유역의 의미는 다르다.

---

## 3. Topography CSV

[`attributes_gageii_Topo.csv`](../../basins/CAMELSH_data/attributes/attributes_gageii_Topo.csv)는 basin의 지형적 성격을 담는다. 물이 얼마나 빨리 모이는지를 이해할 때 핵심이 되는 파일이다.

| 컬럼 | 의미 | 값이 클 때 | 해석 방법 |
|---|---|---|---|
| `ELEV_MEAN_M_BASIN` | basin 평균 고도 | 산지 성격이 강함 | snow 영향, relief, 낮은 기온 가능성과 함께 읽는다 |
| `ELEV_MAX_M_BASIN` | 최고 고도 | 고도차가 큼 | relief 규모 확인용 |
| `ELEV_MIN_M_BASIN` | 최저 고도 | basin 하부 저지대가 낮음 | relief 계산 보조 값 |
| `ELEV_STD_M_BASIN` | 고도 표준편차 | 지형 기복이 큼 | relief variability의 근사치 |
| `SLOPE_PCT` | 평균 경사(%) | 물이 빠르게 모이기 쉬움 | flashy response 가능성과 직접 연결 |
| `RRMEAN`, `RRMEDIAN` | 상대적 relief 지표 | relief가 큼 | steep mountainous basin 여부 판단 참고용 |

`SLOPE_PCT`는 flood-prone screening에서 가장 직관적인 구조 변수 중 하나다. 다른 조건이 비슷하다면 slope가 큰 basin이 peak response도 더 빠른 경향이 있다.

---

## 4. Climate CSV

[`attributes_nldas2_climate.csv`](../../basins/CAMELSH_data/attributes/attributes_nldas2_climate.csv)는 basin이 놓인 forcing regime을 요약한다. 홍수 위험을 직접 말해주는 파일은 아니지만, 어떤 물 공급이 어떤 패턴으로 들어오는지를 설명한다.

| 컬럼 | 의미 | 값이 클 때 | 해석 방법 |
|---|---|---|---|
| `p_mean` | 장기 평균 강수량 | 전반적으로 물 공급이 많음 | 단독 지표보다 extreme 지표와 함께 봐야 의미가 드러난다 |
| `pet_mean` | 잠재증발산량 | 증발 demand가 큼 | `p_mean`과 함께 건조/습윤 맥락을 파악한다 |
| `aridity_index` | 건조도 지수 | 더 건조한 기후 | 유출 효율과 함께 해석해야 한다 |
| `p_seasonality` | 강수의 계절 편중 정도 | 특정 계절에 강수가 집중 | 특정 season flood regime 가능성을 시사한다 |
| `frac_snow` | 강수 중 snow 비중 | snowmelt / rain-on-snow 영향 가능 | 강우형 flood와 분리해서 읽는 것이 좋다 |
| `high_prec_freq` | 강한 강수의 연간 빈도 | 큰 비가 자주 발생 | **flood screening 핵심 forcing 변수** |
| `high_prec_dur` | 강한 강수 이벤트의 지속시간 | 한 번 내릴 때 오래 지속 | 누적 강수형 event 위험과 연결된다 |
| `low_prec_freq`, `low_prec_dur` | 약한 강수의 빈도/지속 특성 | 잔강수가 자주·길게 발생 | flood 직접 지표는 아니지만 climate texture 보완용 |

실무적으로는 `high_prec_freq`, `high_prec_dur`, `frac_snow`, `p_seasonality`를 우선 확인한다. flood-prone basin은 큰 비가 자주 오거나, snowmelt가 관여하거나, 계절 집중도가 높은 경우가 많다.

---

## 5. Hydro CSV

[`attributes_gageii_Hydro.csv`](../../basins/CAMELSH_data/attributes/attributes_gageii_Hydro.csv)는 실제 basin response와 수문 네트워크 구조를 보여준다. **basin screening에서 가장 직접적인 증거가 되는 파일**이다.

| 컬럼 | 의미 | 값이 클 때 | 해석 방법 |
|---|---|---|---|
| `BFI_AVE` | baseflow index | 지하수성 완충이 큼 | 낮을수록 quick response 가능성이 크다 |
| `RUNAVE7100` | 장기 평균 유출 지표 | 유출 수준이 큼 | climate · area와 함께 읽어야 한다 |
| `STREAMS_KM_SQ_KM` | 하천 밀도 | 배수망이 촘촘함 | runoff concentration이 빠를 수 있다 |
| `STRAHLER_MAX` | 최대 하천 차수 | 하천망이 발달함 | 큰 mainstem basin 여부 판단 보조 지표 |
| `MAINSTEM_SINUOUSITY` | 본류의 사행도 | 하천이 굽이침 | routing 특성 참고용 |
| `ARTIFPATH_PCT` | 인공 수로 비율 | 인공 영향이 큼 | 자연 유역 해석 적용 시 주의 필요 |
| `HIRES_LENTIC_PCT` | 정수역(호소·저수지) 비율 | 저장/완충 요소가 큼 | peak 완충 가능성을 시사한다 |

`BFI_AVE`가 낮고 `STREAMS_KM_SQ_KM`이 높으면 빠른 유출 응답을 의심할 수 있다. 이 두 변수는 hydro 파일에서 가장 먼저 확인하는 지표다.

---

## 6. Soils CSV

[`attributes_gageii_Soils.csv`](../../basins/CAMELSH_data/attributes/attributes_gageii_Soils.csv)는 basin의 저장 및 침투 성격을 보여준다.

| 컬럼 | 의미 | 값이 클 때 | 해석 방법 |
|---|---|---|---|
| `AWCAVE` | available water capacity | 토양 저장 여지가 큼 | 큰 강수 event 전 완충 가능성이 크다 |
| `PERMAVE` | 평균 투수성 | 침투가 쉬움 | direct runoff가 줄 수 있다 |
| `WTDEPAVE` | 지하수면 깊이 | 지하수면이 더 깊음 | saturation overland flow 가능성과 함께 본다 |
| `ROCKDEPAVE` | 암반까지 깊이 | 토양 저장 공간이 큼 | 깊을수록 완충 여지가 커진다 |
| `CLAYAVE` | 점토 비율 | 세립질 토양 비중이 큼 | 침투 제한 가능성 있음 |
| `SILTAVE` | 실트 비율 | 중간 입도 성격 | 토성 해석 보조용 |
| `SANDAVE` | 모래 비율 | 배수가 쉬움 | 빠른 침투 가능성 |
| `KFACT_UP`, `RFACT` | 토양 침식 관련 지표 | 침식 민감성이 큼 | flood 직접 지표는 아니지만 landscape vulnerability 참고용 |

토양은 단일 변수로 해석하면 흔들린다. `PERMAVE`, `AWCAVE`, `CLAYAVE`, `SANDAVE`를 함께 보고 basin이 **저장형인지 직접유출형인지**를 판단하는 것이 좋다.

---

## 7. Geology CSV

[`attributes_gageii_Geology.csv`](../../basins/CAMELSH_data/attributes/attributes_gageii_Geology.csv)는 basin의 지질적 배경을 설명한다.

| 컬럼 | 의미 | 값이 클 때 | 해석 방법 |
|---|---|---|---|
| `GEOL_HUNT_DOM_DESC` | 지배적 지질 유형 설명 | 특정 지질이 basin 대부분을 차지 | basin 성격을 질적으로 이해하는 데 쓴다 |
| `GEOL_HUNT_DOM_PCT` | 지배 지질 비율 | basin이 그 지질로 균질함 | geology 해석의 신뢰도를 높여준다 |
| `GEOL_REEDBUSH_DOM` | Reedbush 분류 기준 지질 코드 | 특정 지질 단위 우세 | 분류 체계 기반 비교용 |
| `GEOL_REEDBUSH_DOM_PCT` | Reedbush 기준 지배 지질 비율 | basin 균질성이 큼 | geology dominance 보조 지표 |

지질은 단독 screening 변수라기보다, **왜 어떤 basin은 baseflow가 크고 어떤 basin은 flashy한가**를 설명하는 배경 변수로 활용한다.

---

## 8. Land Cover CSV

[`attributes_gageii_LC06_Basin.csv`](../../basins/CAMELSH_data/attributes/attributes_gageii_LC06_Basin.csv)는 NLCD 2006 기준 basin-scale 토지피복 조성을 담는다. basin의 표면 특성을 가장 직관적으로 보여주는 파일이다.

| 컬럼 | 의미 | 값이 클 때 | 해석 방법 |
|---|---|---|---|
| `DEVNLCD06` | 전체 개발지 비율 | human disturbance가 큼 | 자연 유역 가정 해석 시 주의 필요 |
| `FORESTNLCD06` | 전체 산림 비율 | 식생 완충이 큼 | flashy flood는 약해지는 경향, 산지 basin은 예외 있음 |
| `CROPSNLCD06` | 농경지 비율 | 농업 영향이 큼 | drainage modification 가능성과 함께 본다 |
| `WOODYWETNLCD06`, `EMERGWETNLCD06` | 습지 비율 | 저류 성격이 큼 | peak 완충 가능성을 시사한다 |
| `DECIDNLCD06`, `EVERGRNLCD06`, `MIXEDFORNLCD06` | 산림 세부 유형 | 산림 타입 다양성이 큼 | forest composition 확인용 |
| `DEVOPENNLCD06` ~ `DEVHINLCD06` | 개발지 강도 등급별 비율 | 개발 강도가 높음 | developed basin 해석에 활용 |

현재 분석 테이블에서는 이 파일로부터 아래 파생 컬럼을 생성한다.

| 파생 컬럼 | source | 의미 |
|---|---|---|
| `forest_pct` | `FORESTNLCD06` | 산림 비율 (%) |
| `forest_frac` | `FORESTNLCD06 / 100` | 산림 비율 (0~1) |
| `developed_pct` | `DEVNLCD06` | 개발지 비율 (%) |
| `developed_frac` | `DEVNLCD06 / 100` | 개발지 비율 (0~1) |
| `crops_pct` | `CROPSNLCD06` | 농경지 비율 (%) |
| `wetland_pct` | `WOODYWETNLCD06 + EMERGWETNLCD06` | 전체 습지 비율 (%) |
| `dom_land_cover` | 세부 컬럼 중 최대값 항목 | 지배적 토지피복 유형 |
| `dom_land_cover_pct` | 세부 컬럼 최대값 | 지배 피복의 점유율 |

---

## 9. 분석 테이블 읽는 법

[`drbc_selected_basin_analysis_table.csv`](../../output/basin/drbc_camelsh/analysis/drbc_selected_basin_analysis_table.csv)는 다음 순서로 읽는다.

1. **Climate** → 어떤 물 공급이 어떤 패턴으로 들어오는가
2. **Topo · Soils · Geology · Land Cover** → 그 물이 얼마나 빨리 유출로 전환되는가
3. **Hydro** → 실제로 basin이 어떤 응답 성격을 보였는가

실무에서 자주 보는 신호 조합은 아래와 같다.

```
high_prec_freq↑ + SLOPE_PCT↑ + BFI_AVE↓
→ 빠른 flood response 후보 가능성
```

```
frac_snow↑ + ELEV_MEAN_M_BASIN↑ + p_seasonality 큼
→ rain-only가 아닌 snowmelt / rain-on-snow 메커니즘 검토 필요
```

```
forest_pct↑ + wetland_pct↑ + AWCAVE↑
→ 저장·완충 성격이 강한 basin, flashy flood 후보와는 거리가 있을 수 있음
```

```
DEVNLCD06↑ 또는 ARTIFPATH_PCT↑
→ 자연 유역 기반 해석만으로 부족할 수 있음, 인공 수문 영향 별도 검토
```

---

## 10. 해석 시 주의사항

**단일 변수로 결론을 내리지 않는다.**
basin의 flood 성향은 forcing, structure, response가 함께 작동한 결과다. 하나의 변수가 강한 신호를 보여도, 나머지 층이 그것을 완충하거나 증폭할 수 있다.

**절댓값보다 후보군 내 상대 순위를 본다.**
예를 들어 `SLOPE_PCT = 8`이 높은지 낮은지는 DRBC-selected 154개 basin 안에서의 분포를 기준으로 판단해야 한다.

**hydro 변수는 검증 역할이다.**
land cover나 slope가 빠른 응답을 시사하더라도, `BFI_AVE`나 streamflow 응답 지표가 뒷받침되지 않으면 flood-prone basin으로 단정해서는 안 된다. 정적 변수는 *설명*, hydro 변수는 *검증*이다.

**현재 테이블은 static 중심이다.**
최종 flood screening은 이 정적 분석 위에 hourly observation availability, record length, missingness, peak/event 지표를 추가로 결합해야 완성된다.

## 문서 정리

이 문서는 basin analysis table의 source와 컬럼 의미를 설명하는 사전이다. basin 자체를 어떻게 고를지보다, 이미 고른 basin을 어떤 변수 조합으로 읽을지 정리하는 역할에 집중한다.

정적 변수는 basin의 구조적 배경과 해석 단서를 제공한다. 최종 flood-prone basin 선정은 이 정적 정보 위에 품질 게이트와 observed-flow 지표를 더해 진행해야 한다.

## 관련 문서

- basin subset과 공간 기준은 [`basin_cohort_definition.md`](basin_cohort_definition.md)에서 고정한다.
- 현재 analysis table과 screening 산출물 상태는 [`basin_analysis.md`](basin_analysis.md)에서 다룬다.
- 논문 본문용 screening 규범은 [`basin_screening_method.md`](basin_screening_method.md)에서 다룬다.
