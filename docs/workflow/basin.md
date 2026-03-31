# Basin Workflow

이 문서는 현재 프로젝트에서 basin을 어떻게 조사하고, 어떤 순서로 후보 유역을 추리고, 최종적으로 모델 비교용 basin cohort를 만들 것인지 정리한 작업 기준 문서다.
현재 기준 권역은 DRBC의 `Delaware River Basin` 공식 경계이며, 기준 레이어는 `basins/drbc_boundary/drb_bnd_polygon.shp`다.
예전 `basins/huc8_delware`와 HUC8/WBD 기반 산출물은 exploratory 기록으로 유지하지만, 현재 프로젝트의 공식 basin 기준은 아니다.

## 목적

이 프로젝트에서 basin 조사의 목적은 단순한 지도 정리가 아니다.
핵심 목적은 다음 세 가지다.

1. DRBC Delaware River Basin 안에서 실제로 분석 가능한 CAMELSH basin 후보를 찾는다.
2. 그 후보들 중 flood-prone한 basin을 선별한다.
3. 선별된 basin들로 deterministic LSTM, probabilistic LSTM, physics-guided hybrid를 비교할 수 있는 cohort를 만든다.

즉, basin 조사는 모델 학습 전에 끝내야 하는 독립적인 전처리 단계이면서, 이후 실험 설계의 기준이 된다.

## 입력 데이터의 역할

`basins/drbc_boundary/drb_bnd_polygon.shp`는 DRBC가 제공한 Delaware River Basin 공식 경계다.
이 레이어가 현재 프로젝트의 공간 필터링 기준이며, flood-prone basin 판정 자체는 CAMELSH basin, outlet, streamflow, static attributes를 결합해서 수행한다.

현재 basin 조사에서 입력 데이터의 역할은 아래처럼 나눈다.

- `basins/drbc_boundary/drb_bnd_polygon.shp`: 현재 프로젝트의 공식 권역 정의 레이어.
- `basins/CAMELSH_data/attributes/*`: basin별 static attributes 테이블.
- `basins/CAMELSH_data/shapefiles/CAMELSH_shapefile.shp`: CAMELSH GAGES-II basin boundary shapefile.
- `basins/CAMELSH_data/shapefiles/CAMELSH_shapefile_hydroATLAS.shp`: CAMELSH HydroATLAS 비교용 basin boundary shapefile.
- `timeseries.7z` 또는 `Hourly2.zip`: 이후 forcing/streamflow 시계열 확보 단계에서 사용할 CAMELSH 시계열 아카이브.

요약하면 DRBC 경계는 `어디를 볼지`를 정하고, CAMELSH는 `무엇을 분석할지`를 제공한다.

## 작업 원칙

유역 조사와 후보 소유역 선정 전처리는 Python으로 수행한다.
실행 환경과 의존성 관리는 `uv`를 표준으로 사용한다.
새 분석 코드는 `uv run ...`으로 재현 가능해야 한다.

또 하나 중요한 점은 DRBC 경계와 CAMELSH basin polygon을 `동일한 basin definition`으로 혼동하지 않는 것이다.
DRBC 경계는 study region 정의용이고, hydrologic basin geometry 자체는 CAMELSH GAGES-II polygon을 기준으로 해석한다.

## 전체 절차

### 1. DRBC 기준 권역 테이블 작성

먼저 DRBC 공식 경계 레이어를 기준으로 study region을 고정한다.
기본 컬럼은 권역 이름, CRS, geometry 기준 면적, 그리고 이후 subset 선택에 사용한 overlap 기준 같은 메타데이터다.

이 단계의 목적은 우리가 어떤 공간 범위를 조사하는지 명확히 고정하는 것이다.
이 메타데이터는 이후 모든 basin screening의 기준 마스터 정보가 된다.

### 2. DRBC 경계 안에 들어오는 CAMELSH basin 매핑

CAMELSH basin의 outlet 또는 gauge 좌표를 DRBC polygon과 spatial matching한다.
기본 기준은 gauge outlet point가 DRBC 경계 내부에 들어오는지 여부다. 추가로 basin polygon과 DRBC 경계의 overlap ratio를 계산해 strict subset을 만든다.

이 단계의 목적은 권역 전체 안에서 실제로 분석 가능한 CAMELSH basin을 찾는 것이다.
이 작업이 끝나면 CAMELSH 전체 중 어떤 basin이 현재 권역과 관련 있는지 확정된다.

### 3. CAMELSH candidate subset 작성

2단계에서 DRBC 내부로 판정된 CAMELSH basin만 따로 추려 candidate table을 만든다.
기본 컬럼은 `gauge_id`, `gauge_name`, 좌표, 면적, outlet-in-DRBC 여부, overlap ratio 등이다.

이 표는 이후 flood-prone screening과 품질 검토의 출발점이다.
즉, basin 조사에서 실제 작업 대상이 되는 1차 후보군이라고 보면 된다.

### 4. Static attributes 병합

candidate basin에 CAMELSH static attributes를 병합한다.
현재 우선 병합 대상은 다음 파일들이다.

- `attributes_gageii_BasinID`
- `attributes_gageii_Topo`
- `attributes_nldas2_climate`
- `attributes_gageii_Hydro`
- `attributes_gageii_Soils`
- `attributes_gageii_Geology`
- `attributes_gageii_LC06_Basin`
- `info.csv`

이 단계가 끝나면 basin별로 기후, 지형, 토양, 지질, 식생, 유출 특성을 한 번에 볼 수 있는 basin profile table이 완성된다.

### 5. 분석 가능성 필터

이제부터는 basin이 flood-prone한지 보기 전에, 연구용으로 쓸 수 있는 basin인지 먼저 걸러야 한다.
기록 길이가 너무 짧거나, 결측이 심하거나, 극한 이벤트가 너무 적은 basin은 초기에 제외하는 것이 좋다.

필요하면 regulation, tidal/backwater 영향, 해석이 모호한 basin도 별도 태그를 달아 관리한다.
이 단계의 목적은 데이터 품질 문제 때문에 모델 비교가 흔들리지 않게 하는 것이다.

### 6. Flood-prone screening 지표 설계

flood-prone basin을 찾기 위해 screening 지표를 정의한다.
현재 우선 후보 지표는 다음과 같다.

- climate/forcing 계열: `high_prec_freq`, `high_prec_dur`, `p_seasonality`, `frac_snow`
- response 계열: `runoff_ratio`, `q95`, `high_q_freq`, `high_q_dur`, `baseflow_index`
- basin structure 계열: `slope_mean`, `soil_depth`, `soil_conductivity`, `geol_permeability`, `frac_forest`

핵심은 평균 유량이 큰 basin을 찾는 것이 아니라, 극한 forcing이 왔을 때 빠르고 크게 반응할 가능성이 높은 basin을 찾는 것이다.

### 7. Streamflow 기반 event 진단

static attributes만으로 flood-prone basin을 확정하면 부족하다.
그래서 일별 streamflow에서 annual peak, 상위 quantile flow, event peak magnitude, rising limb 속도, 이벤트 개수 같은 항목을 basin별로 계산해 screening 결과를 검증해야 한다.

이 단계에서 `홍수가 날 것 같은 basin`과 `실제로 첨두 응답이 큰 basin`을 구분한다.

### 8. Basin 유형 태깅

선별된 basin에는 hydrologic mechanism 태그를 붙인다.
예를 들면 `steep-fast-response`, `snow-influenced`, `large-mainstem`, `storage-dominant` 같은 식이다.

이 분류는 나중에 어떤 모델이 어떤 basin 유형에서 개선되는지 해석할 때 필요하다.

### 9. 최종 실험 cohort 선정

최종 실험은 basin 하나만으로 끝내지 않는다.
대표 basin 하나는 디버깅과 파이프라인 확인용으로 두되, 본실험은 flood-prone basin 여러 개로 cohort를 구성하는 것이 프로젝트 목표와 더 잘 맞는다.

cohort는 flood-prone basin만 많이 모으는 것이 아니라, basin 유형이 한쪽으로 지나치게 쏠리지 않도록 구성하는 것이 좋다.

### 10. 모델 비교용 데이터셋 구성

최종 선정된 basin cohort에 대해 forcing, streamflow, static attributes를 모델 입력 형식으로 정리한다.
이후 train/validation/test split과 evaluation protocol을 확정한다.

이 단계부터 basin 조사는 끝나고, 모델 실험 준비 단계로 넘어간다.

## 현재까지 완료된 단계

현재 저장소에서는 DRBC boundary + CAMELSH 기준 subset을 자동 수행하는 스크립트를 만들었다.

- 다운로드 스크립트: `scripts/download_camelsh_core.py`
- 실행 예시:

```bash
uv run python scripts/download_camelsh_core.py
```

- subset 스크립트: `scripts/build_drbc_camelsh_tables.py`
- 실행 예시:

```bash
uv run scripts/build_drbc_camelsh_tables.py --min-overlap-ratio 0.9
```

- 출력 디렉토리: `output/basin/drbc_camelsh`

현재 생성되는 파일은 아래와 같다.

- `camelsh_drbc_mapping.csv`: CAMELSH 전체 basin의 DRBC 매핑 결과
- `camelsh_drbc_selected.csv`: strict 기준인 `outlet_in_drbc + overlap >= threshold` 후보군
- `camelsh_drbc_intersect_only.csv`: basin polygon은 DRBC에 닿지만 outlet은 바깥인 참고 레이어
- `drbc_boundary_summary.json`: 기준 경계와 선택 기준 요약

현재 기준 수치는 아래와 같다.

- CAMELSH 전체 basin: `9,008`
- outlet-in-DRBC: `192`
- strict `outlet-in-DRBC + overlap >= 0.9`: `154`
- intersect-only basin: `61`

현재 프로젝트의 공식 basin geometry 기준은 `CAMELSH_shapefile.shp`다.
`CAMELSH_shapefile_hydroATLAS.shp`는 비교나 진단용 레이어로만 두고, subset 정의와 후속 모델링 기준은 GAGES-II 버전 shapefile을 사용한다.

DRBC boundary와 strict subset을 GIS에 바로 얹어보기 위한 `GPKG` 생성 스크립트도 추가되었다.

- 스크립트: `scripts/build_drbc_camelsh_gpkg.py`
- 실행 예시:

```bash
uv run scripts/build_drbc_camelsh_gpkg.py
```

- 출력 파일: `output/basin/drbc_camelsh/drbc_camelsh_layers.gpkg`

현재 생성되는 overlay 파일은 아래와 같다.

- `drbc_boundary`: DRBC Delaware River Basin 공식 경계
- `camelsh_selected_basins`: strict subset으로 선택된 CAMELSH basin polygon
- `camelsh_selected_outlets`: strict subset의 outlet point
- `camelsh_intersect_only_basins`: polygon만 DRBC 경계에 걸치는 참고 basin
- `camelsh_intersect_only_outlets`: 위 참고 basin의 outlet point

현재 overlay 기준 수치는 아래와 같다.

- exported strict CAMELSH basin polygon: `154`
- intersect-only basin polygon: `61`

QGIS에서 바로 열 수 있도록 `GeoPackage` 패키지 출력도 추가되었다.

- 스크립트: `scripts/build_drbc_camelsh_gpkg.py`
- 실행 예시:

```bash
uv run scripts/build_drbc_camelsh_gpkg.py
```

- 출력 파일: `output/basin/drbc_camelsh/drbc_camelsh_layers.gpkg`

이 파일 안에는 아래 레이어가 함께 들어 있다.

- `drbc_boundary`
- `camelsh_selected_basins`
- `camelsh_selected_outlets`
- `camelsh_intersect_only_basins`
- `camelsh_intersect_only_outlets`

이 레이어들은 모두 현재 기준 CRS인 `EPSG:4326`으로 저장되어 있다.

## 현재 상태 요약

현재 기준으로 CAMELSH 전체 basin 9,008개 중 DRBC Delaware River Basin과 관련 있는 basin은 outlet 기준 `192개`이고, strict 기준 `154개`다.
즉, 다음 작업은 이 `154개 strict subset`을 기준으로 품질 필터와 flood response screening을 적용하는 것이다.

## 레이어 해석 원칙

현재 QGIS에 올린 레이어들은 같은 의미의 계층 분할도가 아니다.
그래서 `drbc_boundary`와 `camelsh_selected_basins` 경계가 완전히 일치해야 한다고 보면 해석이 틀어진다.

각 레이어는 아래처럼 따로 읽는 것이 맞다.

- `drbc_boundary`: DRBC가 정의한 study region 경계다.
  이것은 hydrologic basin 자체가 아니라 project scope를 자르는 공식 외곽선이다.

- `camelsh_selected_basins`: gauge 기반 upstream basin polygon 레이어다.
  DRBC 경계와 다른 출처로 delineation되었기 때문에 일부 basin은 경계 밖으로 조금 나갈 수 있다.

- `camelsh_intersect_only_basins`: polygon은 DRBC에 닿지만 outlet은 바깥인 참고 레이어다.
  selection 기준을 설명하거나 경계 사례를 검토할 때만 켠다.

실무적으로는 아래처럼 분리해서 보는 것이 가장 안정적이다.

1. `권역 범위 확인`
   `drbc_boundary`만 켜고 본다.

2. `strict subset 확인`
   `drbc_boundary`, `camelsh_selected_basins`, `camelsh_selected_outlets`를 같이 켜고 본다.

3. `경계 사례 진단`
   `camelsh_intersect_only_basins`를 추가로 켜서 왜 제외됐는지 확인한다.

## 현재 표준 유역 정의

현재 프로젝트의 기준 유역은 `basins/drbc_boundary/drb_bnd_polygon.shp`가 정의하는 DRBC Delaware River Basin이다.
즉 이제부터 유역 조사, 속성 병합, screening, 모델링용 basin cohort 정의는 모두 DRBC boundary + CAMELSH strict subset을 기준으로 해석한다.

## 다음 단계

다음 구현 우선순위는 아래 두 가지다.

1. 현재 확정된 `154개 DRBC strict subset`에 CAMELSH static attributes와 이후 확보할 forcing / streamflow 시계열을 안정적으로 결합한다.
2. 이 strict subset 위에서 streamflow 기반 flood-prone screening 지표를 계산하고, 최종 실험 cohort를 선정한다.
