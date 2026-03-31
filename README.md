# CAMELS — Multi-Basin LSTM Flood Prediction

Multi-basin LSTM 기반 수문 예측에서 **극한 홍수 첨두 과소추정**을 줄이기 위한 연구 프로젝트.

Deterministic → Probabilistic → Physics-guided hybrid 세 모델을 단계적으로 비교한다.

## 디렉토리 구조

```text
.
├── agents.md            # 에이전트 작업 맥락
├── basins/
│   ├── drbc_boundary/   # DRBC Delaware River Basin 공식 경계
│   ├── huc8_delware/    # 초기 HUC8 exploratory shapefile
│   └── CAMELSH_data/    # CAMELSH shapefiles / attributes 추출본
├── configs/             # NeuralHydrology 실험 설정
├── data/CAMELS_US/
│   └── camels_attributes_v2.0/  # legacy CAMELS-US 속성 데이터
├── docs/
│   ├── workflow/        # basin 처리 절차와 데이터 준비 워크플로
│   └── research/        # architecture, design, literature-review
├── output/
│   └── basin/           # basin 관련 산출물
├── scripts/             # basin 전처리, download, run 스크립트
└── runs/                # (gitignored) 학습 출력
```

## 대상 유역

현재 basin 조사의 공식 공간 기준은 DRBC Delaware River Basin 공식 경계다.
실무 기준 레이어는 [`drb_bnd_polygon.shp`](/Users/jang-minyeop/Project/CAMELS/basins/drbc_boundary/drb_bnd_polygon.shp)이고, `basins/huc8_delware/`는 초기 exploratory seed로만 둔다.

## 환경

- **패키지 관리**: `uv`
- **실행**: `uv run`으로 재현 가능해야 함

## 현재 workflow

현재 basin screening과 basin cohort 정의의 기본 데이터셋은 CAMELSH이고, 공식 region boundary는 DRBC다.
현재 기준 스크립트와 산출물은 아래 흐름으로 읽는 것이 맞다.

- [`build_drbc_camelsh_tables.py`](/Users/jang-minyeop/Project/CAMELS/scripts/build_drbc_camelsh_tables.py): DRBC boundary 기준으로 CAMELSH 전체를 평가하고 selected subset table을 만든다.
- [`build_drbc_camelsh_gpkg.py`](/Users/jang-minyeop/Project/CAMELS/scripts/build_drbc_camelsh_gpkg.py): DRBC boundary와 selected/intersect-only CAMELSH 레이어를 QGIS용 `GPKG`로 묶는다.
- [`build_drbc_basin_analysis_table.py`](/Users/jang-minyeop/Project/CAMELS/scripts/build_drbc_basin_analysis_table.py): selected 154 basin에 CAMELSH static attributes를 병합해 basin analysis table을 만든다.
- [`camelsh_drbc_mapping.csv`](/Users/jang-minyeop/Project/CAMELS/output/basin/drbc_camelsh/camelsh_drbc_mapping.csv): CAMELSH 전체 9008 basin 평가 결과다.
- [`camelsh_drbc_selected.csv`](/Users/jang-minyeop/Project/CAMELS/output/basin/drbc_camelsh/camelsh_drbc_selected.csv): 현재 공식 basin candidate table이다.
- [`drbc_camelsh_layers.gpkg`](/Users/jang-minyeop/Project/CAMELS/output/basin/drbc_camelsh/drbc_camelsh_layers.gpkg): QGIS 기본 확인 패키지다.
- [`drbc_selected_basin_analysis_table.csv`](/Users/jang-minyeop/Project/CAMELS/output/basin/drbc_camelsh/analysis/drbc_selected_basin_analysis_table.csv): 현재 basin analysis의 시작점이 되는 정적 특성 테이블이다.

현재 공식 basin subset은 `outlet_in_drbc == True` 이고 `overlap_ratio_of_basin >= 0.9`인 CAMELSH `154개`다. outlet가 DRBC 안에 들어오는 basin은 `192개`이고, 그중 polygon overlap 기준으로 최종 selected set이 `154개`다.

현재 기준은 `DRBC boundary + CAMELSH outlets/selected table`이다. CAMELSH polygon은 selection/QC용으로는 쓰지만, DRBC나 HUC와 같은 공식 경계 polygon으로 보지는 않는다.

## 관련 문서

- [`agents.md`](agents.md) — 에이전트 작업 맥락 및 프로젝트 규칙
- [`docs/workflow/basin.md`](docs/workflow/basin.md) — basin 처리 절차, 단계별 목적, 현재 산출물 정리
- [`docs/workflow/basin_explain.md`](docs/workflow/basin_explain.md) — basin analysis source CSV와 변수 해석 가이드
- [`docs/research/architecture.md`](docs/research/architecture.md) — 모델 아키텍처 상세
- [`docs/research/design.md`](docs/research/design.md) — 실험 설계
- [`docs/research/literature-review.md`](docs/research/literature-review.md) — 선행연구 정리
