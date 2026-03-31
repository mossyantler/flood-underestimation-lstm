# Basin Workflow

이 문서는 현재 프로젝트에서 basin을 어떻게 정의하고, 어떤 subset을 공식 작업 기준으로 쓰고, 다음 basin analysis를 어떤 순서로 진행할지 정리한 기준 문서다.

지금 기준은 예전 `huc8_delware` exploratory workflow가 아니라, DRBC 공식 경계와 CAMELSH subset이다. HUC는 완전히 버린 것이 아니라 보조 spatial scaffold로 남겨두되, basin 후보 선정의 출발점은 더 이상 HUC polygon이 아니다.

## 현재 공식 기준

현재 study region의 공식 경계는 `basins/drbc_boundary/drb_bnd_polygon.shp`이다. Delaware River Basin Commission 기준 Delaware River Basin을 그대로 사용한다.

현재 모델링용 basin 후보는 CAMELSH에서 뽑는다. 즉, basin 정의의 1차 기준은 `DRBC boundary + CAMELSH gauge basin` 조합이다.

## 데이터 역할

현재 basin workflow에서 각 데이터의 역할은 아래처럼 나눈다.

- `basins/drbc_boundary/drb_bnd_polygon.shp`
  현재 공식 study region이다. 공간 포함 여부와 region 면적 계산의 기준이다.

- `basins/CAMELSH_data/attributes/attributes_gageii_BasinID.csv`
  gauge ID, gauge name, 위경도, 유역 면적 등 basin 메타데이터의 기준 테이블이다.

- `basins/CAMELSH_data/shapefiles/CAMELSH_shapefile.shp`
  CAMELSH에서 제공한 원본 basin polygon이다. 다만 HUC나 DRBC 경계와 완전히 같은 geometry라고 보면 안 된다.

- `output/basin/drbc_camelsh/camelsh_drbc_mapping.csv`
  DRBC 기준으로 CAMELSH 전체 9008 basin을 평가한 전체 매핑 테이블이다.

- `output/basin/drbc_camelsh/camelsh_drbc_selected.csv`
  현재 공식 candidate basin table이다. outlet가 DRBC 안에 있고, basin polygon overlap ratio가 `0.9` 이상인 basin만 포함한다.

- `output/basin/drbc_camelsh/camelsh_drbc_intersect_only.csv`
  polygon은 DRBC와 겹치지만 outlet는 DRBC 밖에 있는 edge case table이다. 해석 참고용이지 기본 후보군은 아니다.

- `output/basin/drbc_camelsh/drbc_camelsh_layers.gpkg`
  DRBC boundary, selected basin, selected outlet를 QGIS에서 확인하는 기본 패키지다.

## 현재 selection rule

현재 selection rule은 `outlet_in_drbc == True`와 `overlap_ratio_of_basin >= 0.9`를 동시에 만족하는 CAMELSH basin이다. 이 규칙은 [`build_drbc_camelsh_tables.py`](/Users/jang-minyeop/Project/CAMELS/scripts/build_drbc_camelsh_tables.py)에서 재현 가능하게 구현되어 있다.

현재 summary는 아래와 같다.

- CAMELSH 전체 평가 basin: `9008`
- outlet가 DRBC 안에 들어오는 basin: `192`
- 그중 overlap ratio `>= 0.9`로 최종 선택된 basin: `154`
- polygon은 DRBC와 겹치지만 outlet는 바깥인 basin: `61`

현재 basin 분석은 이 `154개`를 기준으로 진행한다.

## CAMELSH polygon 해석 원칙

중요한 점은 CAMELSH polygon과 HUC polygon, DRBC polygon을 같은 경계 체계로 읽으면 안 된다는 것이다.

좌표계만 맞춰도 경계가 같아지는 것은 아니다. 실제로 현재 selected CAMELSH basin union과 DRBC region을 겹쳐보면, CAMELSH union의 대부분은 DRBC 안에 들어오지만 geometry 자체는 다르다. 따라서 지금 프로젝트에서 공간 anchor는 polygon이 아니라 `gauge outlet`이다.

현재 원칙은 아래처럼 고정한다.

1. 공식 study region은 DRBC boundary다.
2. CAMELSH basin 매칭의 기본 anchor는 outlet point다.
3. CAMELSH polygon overlap은 selection/QC용이다.
4. CAMELSH polygon을 HUC 또는 DRBC 공식 경계 대체재로 쓰지 않는다.

## HUC의 현재 역할

예전 `mostly_contained_huc10` 기반 HUC workflow는 exploratory scaffold로는 유효했지만, 현재 저장소의 공식 basin subset 정의는 아니다.

앞으로 HUC8/HUC10/HUC12는 필요할 때 아래 용도로만 사용한다.

- selected CAMELSH outlet를 HUC에 spatial join해서 basin grouping tag를 붙일 때
- basin 특성을 소유역 계층 관점에서 요약할 때
- 시각화나 설명을 위해 subregion label이 필요할 때

즉 HUC는 지금부터 `region definition`이 아니라 `analysis grouping layer`다.

## 다음 단계: Basin Analysis

이제부터는 polygon 정렬 문제를 더 파고들기보다, selected CAMELSH basin의 특성을 분석하는 단계로 넘어간다. 기본 순서는 아래와 같다.

### 1. 분석 대상 basin table 고정

입력 기준 테이블은 `output/basin/drbc_camelsh/camelsh_drbc_selected.csv`다. 이 파일의 `gauge_id` 목록이 현재 basin analysis의 시작점이다.

### 2. CAMELSH static attributes 병합

selected basin에 아래 CAMELSH attribute 테이블을 병합한다.

- `attributes_gageii_BasinID`
- `attributes_gageii_Topo`
- `attributes_nldas2_climate`
- `attributes_gageii_Hydro`
- `attributes_gageii_Soils`
- `attributes_gageii_Geology`
- `attributes_gageii_LC06_Basin`

이 단계의 결과는 basin별 static profile table이다. 현재 이 단계는 [`build_drbc_basin_analysis_table.py`](/Users/jang-minyeop/Project/CAMELS/scripts/build_drbc_basin_analysis_table.py)로 자동화되어 있다.

### 3. basin analysis table 생성

분석 테이블은 적어도 아래 다섯 묶음으로 읽을 수 있어야 한다.

- land use / vegetation: `frac_forest`, `dom_land_cover`, `dom_land_cover_frac`
- climate summary: `p_mean`, `p_seasonality`, `frac_snow`, `aridity`, `high_prec_freq`, `high_prec_dur`
- topography: `area_gages2`, `elev_mean`, `slope_mean`
- soil / geology: `soil_depth_pelletier`, `soil_conductivity`, `soil_porosity`, `geol_permeability`
- hydrologic response: `runoff_ratio`, `q95`, `high_q_freq`, `high_q_dur`, `baseflow_index`

### 4. 분석 가능성 필터

static attributes를 붙인 뒤 바로 flood-prone screening으로 가면 안 된다. 먼저 연구용으로 해석 가능한 basin인지 걸러야 한다.

현재 우선 확인 항목은 아래와 같다.

- hourly observation availability
- record length
- missingness
- 해석이 모호한 coastal / tidal / strongly regulated basin 여부

### 5. Flood-prone screening

그 다음부터 flood-prone basin을 찾는다. 평균 유량이 큰 basin이 아니라, 극한 forcing이 왔을 때 첨두가 빠르고 크게 나올 가능성이 높은 basin을 찾는 것이 목적이다.

screening 1차는 static + summary attributes로 하고, 2차는 시계열 peak/event 진단으로 검증한다.

### 6. 시계열 기반 basin analysis

selected basin의 forcing/streamflow를 읽어서 아래 항목을 계산한다.

- annual peak flow
- top 1% flow
- event peak magnitude
- peak timing
- rising limb speed
- high-flow event count

이 단계가 끝나야 최종 basin cohort를 고를 수 있다.

### 7. Cohort 선정

최종 모델 비교용 cohort는 basin 하나가 아니라 여러 basin으로 구성한다. 다만 hydrologic mechanism이 한쪽으로만 치우치지 않도록 조정한다.

예를 들면 아래 태그를 붙여 관리하는 것이 좋다.

- `steep-fast-response`
- `snow-influenced`
- `large-mainstem`
- `storage-dominant`
- `coastal-or-tidal-risk`

## 현재 기준 스크립트

현재 기준 workflow에서 핵심 스크립트는 아래 둘이다.

- [`build_drbc_camelsh_tables.py`](/Users/jang-minyeop/Project/CAMELS/scripts/build_drbc_camelsh_tables.py)
- [`build_drbc_camelsh_gpkg.py`](/Users/jang-minyeop/Project/CAMELS/scripts/build_drbc_camelsh_gpkg.py)
- [`build_drbc_basin_analysis_table.py`](/Users/jang-minyeop/Project/CAMELS/scripts/build_drbc_basin_analysis_table.py)

HUC exploratory 스크립트들은 필요하면 다시 사용할 수 있지만, 현재 basin analysis의 공식 시작점은 아니다.

## 현재 상태 한 줄 요약

현재 프로젝트의 basin 기준은 `DRBC boundary 안에 outlet가 들어오고 polygon overlap이 0.9 이상인 CAMELSH 154 basin`이다. 현재 static basin analysis 산출물은 아래 경로에 있다.

- `output/basin/drbc_camelsh/analysis/drbc_selected_static_attributes_full.csv`
- `output/basin/drbc_camelsh/analysis/drbc_selected_basin_analysis_table.csv`
- `output/basin/drbc_camelsh/analysis/drbc_selected_basin_analysis_summary.json`

다음 작업은 이 분석 테이블 위에 forcing/streamflow 품질 정보와 event-level 지표를 붙여 flood-prone screening 단계로 넘어가는 것이다.
