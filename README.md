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
│   ├── README.md        # 문서 인덱스와 읽기 순서
│   ├── workflow/        # basin 처리 절차와 데이터 준비 워크플로
│   ├── research/        # architecture, design, literature-review
│   └── references/      # 참고 자료와 학습 노트
├── output/
│   └── basin/           # basin 관련 산출물
├── scripts/             # basin 전처리, download, run 스크립트
└── runs/                # (gitignored) 학습 출력
```

## 대상 유역

현재 공식 evaluation holdout region은 DRBC Delaware River Basin 공식 경계다.
실무 기준 레이어는 [`drb_bnd_polygon.shp`](/Users/jang-minyeop/Project/CAMELS/basins/drbc_boundary/drb_bnd_polygon.shp)이고, `basins/huc8_delware/`는 초기 exploratory seed로만 둔다.

## 환경

- **패키지 관리**: `uv`
- **실행**: `uv run`으로 재현 가능해야 함

## 현재 workflow

현재 basin workflow는 `global training pool`과 `DRBC holdout evaluation cohort`를 분리해서 본다.
기본 데이터셋은 CAMELSH이고, DRBC는 학습용 region이 아니라 평가용 holdout region이다.
즉 현재 프로젝트가 학습하는 것은 `Delaware regional model`이 아니라, `non-DRBC basin에서 학습한 global multi-basin model`이다. DRBC는 그 global model의 regional generalization을 확인하는 시험장 역할을 한다.
현재 기준 스크립트와 산출물은 아래 흐름으로 읽는 것이 맞다.

- [`build_drbc_camelsh_tables.py`](/Users/jang-minyeop/Project/CAMELS/scripts/build_drbc_camelsh_tables.py): DRBC boundary 기준으로 CAMELSH 전체를 평가하고 selected subset table을 만든다.
- [`build_drbc_camelsh_gpkg.py`](/Users/jang-minyeop/Project/CAMELS/scripts/build_drbc_camelsh_gpkg.py): DRBC boundary와 selected/intersect-only CAMELSH 레이어를 QGIS용 `GPKG`로 묶는다.
- [`build_drbc_basin_analysis_table.py`](/Users/jang-minyeop/Project/CAMELS/scripts/build_drbc_basin_analysis_table.py): selected 154 basin에 CAMELSH static attributes를 병합해 basin analysis table을 만든다.
- [`build_camelsh_non_drbc_training_pool.py`](/Users/jang-minyeop/Project/CAMELS/scripts/build_camelsh_non_drbc_training_pool.py): DRBC 밖의 CAMELSH basin을 quality gate로 다시 걸러 학습용 global training pool을 만든다. 좌표/경계 source 차이로 인한 작은 overlap은 `overlap_ratio <= 0.1`까지 허용한다.
- [`build_drbc_holdout_split_files.py`](/Users/jang-minyeop/Project/CAMELS/scripts/build_drbc_holdout_split_files.py): non-DRBC training pool을 train/validation으로 나누고, DRBC holdout test basin file을 만든다.
- [`camelsh_drbc_mapping.csv`](/Users/jang-minyeop/Project/CAMELS/output/basin/drbc_camelsh/camelsh_drbc_mapping.csv): CAMELSH 전체 9008 basin 평가 결과다.
- [`camelsh_drbc_selected.csv`](/Users/jang-minyeop/Project/CAMELS/output/basin/drbc_camelsh/camelsh_drbc_selected.csv): 현재 공식 basin candidate table이다.
- [`drbc_camelsh_layers.gpkg`](/Users/jang-minyeop/Project/CAMELS/output/basin/drbc_camelsh/drbc_camelsh_layers.gpkg): QGIS 기본 확인 패키지다.
- [`drbc_selected_basin_analysis_table.csv`](/Users/jang-minyeop/Project/CAMELS/output/basin/drbc_camelsh/analysis/drbc_selected_basin_analysis_table.csv): 현재 basin analysis의 시작점이 되는 정적 특성 테이블이다.
- [`drbc_streamflow_quality_table.csv`](/Users/jang-minyeop/Project/CAMELS/output/basin/drbc_camelsh/screening/drbc_streamflow_quality_table.csv): usable year 기반의 streamflow quality gate 결과다.
- [`drbc_provisional_screening_table.csv`](/Users/jang-minyeop/Project/CAMELS/output/basin/drbc_camelsh/screening/drbc_provisional_screening_table.csv): 현재까지 계산된 provisional basin shortlist다.
- [`camelsh_non_drbc_training_selected.csv`](/Users/jang-minyeop/Project/CAMELS/output/basin/camelsh_training_non_drbc/camelsh_non_drbc_training_selected.csv): DRBC holdout 밖에서 quality gate를 통과한 학습용 basin 목록이다.
- [`camelsh_non_drbc_training_summary.json`](/Users/jang-minyeop/Project/CAMELS/output/basin/camelsh_training_non_drbc/camelsh_non_drbc_training_summary.json): global training pool 요약 수치다.
- [`drbc_holdout_train_broad.txt`](/Users/jang-minyeop/Project/CAMELS/configs/basin_splits/drbc_holdout_train_broad.txt), [`drbc_holdout_validation_broad.txt`](/Users/jang-minyeop/Project/CAMELS/configs/basin_splits/drbc_holdout_validation_broad.txt), [`drbc_holdout_test_drbc_quality.txt`](/Users/jang-minyeop/Project/CAMELS/configs/basin_splits/drbc_holdout_test_drbc_quality.txt): 기본 broad split basin file이다.
- [`drbc_holdout_train_natural.txt`](/Users/jang-minyeop/Project/CAMELS/configs/basin_splits/drbc_holdout_train_natural.txt), [`drbc_holdout_validation_natural.txt`](/Users/jang-minyeop/Project/CAMELS/configs/basin_splits/drbc_holdout_validation_natural.txt), [`drbc_holdout_test_drbc_quality_natural.txt`](/Users/jang-minyeop/Project/CAMELS/configs/basin_splits/drbc_holdout_test_drbc_quality_natural.txt): natural split basin file이다.
- [`drbc_holdout_split_summary.json`](/Users/jang-minyeop/Project/CAMELS/output/basin/splits/drbc_holdout/drbc_holdout_split_summary.json): global training / regional holdout split 요약이다.

현재 DRBC holdout basin subset은 `outlet_in_drbc == True` 이고 `overlap_ratio_of_basin >= 0.9`인 CAMELSH `154개`다. outlet가 DRBC 안에 들어오는 basin은 `192개`이고, 그중 polygon overlap 기준으로 최종 selected set이 `154개`다.

반대로 학습용 global training pool은 `outlet은 DRBC 밖에 있고`, polygon overlap은 `0.1 이하`까지 허용한 basin으로 잡는다. 이건 CAMELSH polygon과 DRBC 경계 source 차이 때문에 생기는 작은 시각적 겹침을 포함하기 위한 tolerant rule이다. 현재 기준으로 tolerant outside basin은 `8800개`이고, 이 중 quality gate를 통과한 학습 basin은 `1923개`, hydromod risk가 없는 natural training basin은 `248개`다. 실제 tolerant overlap으로 추가된 quality-pass basin은 `3개`뿐이다.

현재 기본 split은 `global training + DRBC regional holdout evaluation` 구조다. broad 기준으로 `train 1722 / validation 201 / DRBC quality-pass test 38`이고, natural 기준으로는 `train 213 / validation 35 / DRBC natural quality-pass test 8`이다.

현재 기준은 `DRBC boundary + CAMELSH outlets/selected table`이다. CAMELSH polygon은 selection/QC용으로는 쓰지만, DRBC나 HUC와 같은 공식 경계 polygon으로 보지는 않는다.

현재 screening은 DRBC holdout cohort에 대해 `quality gate + provisional static prioritization`까지 완료된 상태다. 다만 정적 커스텀 점수는 내부 basin shortlist를 빠르게 보는 exploratory 도구로만 쓰고, 최종 flood-prone cohort는 hourly 원시 시계열에서 annual peaks, Q99-level frequency, flashiness, event runoff coefficient를 계산한 뒤 `observed-flow 중심 final screening`으로 확정할 계획이다.

## 관련 문서

- [`agents.md`](agents.md) — 에이전트 작업 맥락 및 프로젝트 규칙
- [`docs/README.md`](docs/README.md) — `docs/` 전체 문서 인덱스와 카테고리별 읽기 순서
- [`docs/workflow/event_response_spec.md`](docs/workflow/event_response_spec.md) — hourly event extraction 규칙, threshold fallback, rainfall window, 출력 스키마
- [`docs/research/defense_playbook.md`](docs/research/defense_playbook.md) — 설계 디펜드용 예상 질문, 취약점, 우선 보강 항목 정리
