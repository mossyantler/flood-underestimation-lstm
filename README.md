# CAMELSH — Multi-Basin LSTM Flood Prediction

Multi-basin LSTM 기반 수문 예측에서 **극한 홍수 첨두 과소추정**을 줄이기 위한 연구 프로젝트.

현재 논문의 공식 비교축은 `Deterministic LSTM -> Probabilistic quantile LSTM` 두 모델이다. `physics-guided hybrid`는 후속 확장 또는 exploratory branch로 둔다.

## 디렉토리 구조

```text
.
├── AGENTS.md            # 에이전트 작업 맥락
├── basins/
│   ├── drbc_boundary/   # DRBC Delaware River Basin 공식 경계
│   ├── huc8_delware/    # 초기 HUC8 exploratory shapefile
│   └── CAMELSH_data/    # CAMELSH shapefiles / attributes 추출본
├── configs/
│   ├── README.md        # canonical/dev config 역할 설명
│   ├── pilot/           # scaling pilot 전용 config / split
│   ├── dev/             # local sanity 등 개발용 설정
│   └── basin_splits/    # raw split membership file
├── data/CAMELS_US/
│   └── camels_attributes_v2.0/  # legacy CAMELS-US 속성 데이터
├── docs/
│   ├── archive/         # 과거 proposal 및 보존용 초안
│   ├── README.md        # 문서 인덱스와 읽기 순서
│   ├── workflow/        # basin 처리 절차와 데이터 준비 워크플로
│   ├── research/        # architecture, design, literature_review
│   └── references/      # 참고 자료와 학습 노트
├── output/
│   └── basin/           # basin 관련 산출물
├── scripts/
│   ├── README.md        # canonical/official/pilot/dev script 역할 설명
│   ├── official/        # 공식 실험 실행 진입점
│   ├── pilot/           # scaling pilot 실행 진입점
│   ├── dev/             # 개발용 실행 진입점
│   └── check_repo_integrity.py  # 간단한 저장소 무결성 검사
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
- [`build_scaling_pilot_splits.py`](/Users/jang-minyeop/Project/CAMELS/scripts/pilot/build_scaling_pilot_splits.py): raw broad non-DRBC pool `1923`을 source-of-truth로 두고, prepared broad train/validation basin에서 HUC02-stratified scaling pilot subset `100 / 300 / 600`을 생성한다.
- [`build_scaling_pilot_attribute_diagnostics.py`](/Users/jang-minyeop/Project/CAMELS/scripts/pilot/build_scaling_pilot_attribute_diagnostics.py): prepared executable pool 대비 pilot subset의 `area`, `slope`, `aridity`, `snow_fraction`, `soil_depth`, `permeability`, `forest_fraction`, `baseflow_index` 분포 보존 정도를 정량 비교한다.
- [`build_scaling_pilot_event_response_diagnostics.py`](/Users/jang-minyeop/Project/CAMELS/scripts/pilot/build_scaling_pilot_event_response_diagnostics.py): prepared executable pool 대비 pilot subset의 `annual peak specific discharge`, `Q99 event frequency`, `RBI`, event peak/shape 요약 같은 observed-flow event-response 분포 보존 정도를 정량 비교한다.
- [`build_camelsh_return_period_references.py`](/Users/jang-minyeop/Project/CAMELS/scripts/build_camelsh_return_period_references.py): rsync가 끝난 hourly `.nc` 전체를 대상으로 basin별 재현기간 강수량(`prec_ari*_*h`)과 홍수량(`flood_ari*`) reference table을 만든다.
- [`build_camelsh_event_response_table.py`](/Users/jang-minyeop/Project/CAMELS/scripts/build_camelsh_event_response_table.py): 전 유역 hourly `.nc`에서 POT 기반 event response table과 basin summary를 만들고, return-period reference가 있으면 event별 ratio를 붙인다.
- [`build_camelsh_flood_generation_typing.py`](/Users/jang-minyeop/Project/CAMELS/scripts/build_camelsh_flood_generation_typing.py): event response descriptor를 이용해 `recent_precipitation`, `antecedent_precipitation`, `snowmelt_or_rain_on_snow` event type과 basin-level dominant/mixture label을 만든다.
- [`build_scaling_pilot_random_subset_benchmark.py`](/Users/jang-minyeop/Project/CAMELS/scripts/pilot/build_scaling_pilot_random_subset_benchmark.py): adopted `scaling_300` subset이 같은 크기의 random subset들보다 얼마나 잘 matched되는지 `200+`회 benchmark로 정량 비교한다.
- [`plot_scaling_pilot_diagnostics.py`](/Users/jang-minyeop/Project/CAMELS/scripts/pilot/plot_scaling_pilot_diagnostics.py): distribution diagnostics CSV를 해석하기 쉬운 summary line chart, attribute heatmap, combined mismatch ranking plot으로 변환한다.
- [`run_deterministic_scaling_pilot.sh`](/Users/jang-minyeop/Project/CAMELS/scripts/pilot/run_deterministic_scaling_pilot.sh): deterministic Model 1 scaling pilot을 size/seed별로 실행한다. pilot run은 `./runs/scaling_pilot` 아래에 저장돼 official broad run과 섞이지 않는다. `NH_RESUME=1`로 checkpoint resume을, `NH_SAVE_ALL_OUTPUT=False`나 `NH_SAVE_VALIDATION_RESULTS=False`로 storage-constrained validation override를 줄 수 있다.
- [`run_subset300_multiseed.sh`](/Users/jang-minyeop/Project/CAMELS/scripts/official/run_subset300_multiseed.sh): 현재 채택된 `scaling_300` subset을 고정하고, Model 1 / Model 2 모두 seed `111 / 222 / 444` main comparison을 같은 basin file로 반복 실행하는 공식 runner다. Model 2 seed `333`은 NaN loss로 실패했고, 공정한 paired-seed 비교를 위해 Model 1 seed `333`도 final aggregate에서 제외한다.
- [`run_camelsh_flood_analysis.sh`](/Users/jang-minyeop/Project/CAMELS/scripts/official/run_camelsh_flood_analysis.sh): 서버에서 `.nc` rsync 완료 후 return-period reference, event response table, flood generation typing을 순서대로 실행하는 all-basin 분석 runner다. 기본 출력은 `output/basin/camelsh_all/flood_analysis/` 아래에 둔다.
- [`camelsh_drbc_mapping.csv`](/Users/jang-minyeop/Project/CAMELS/output/basin/drbc_camelsh/camelsh_drbc_mapping.csv): CAMELSH 전체 9008 basin 평가 결과다.
- [`camelsh_drbc_selected.csv`](/Users/jang-minyeop/Project/CAMELS/output/basin/drbc_camelsh/camelsh_drbc_selected.csv): 현재 공식 basin candidate table이다.
- [`drbc_camelsh_layers.gpkg`](/Users/jang-minyeop/Project/CAMELS/output/basin/drbc_camelsh/drbc_camelsh_layers.gpkg): QGIS 기본 확인 패키지다.
- [`drbc_selected_basin_analysis_table.csv`](/Users/jang-minyeop/Project/CAMELS/output/basin/drbc_camelsh/analysis/drbc_selected_basin_analysis_table.csv): 현재 basin analysis의 시작점이 되는 정적 특성 테이블이다.
- [`drbc_streamflow_quality_table.csv`](/Users/jang-minyeop/Project/CAMELS/output/basin/drbc_camelsh/screening/drbc_streamflow_quality_table.csv): usable year 기반의 streamflow quality gate 결과다.
- [`drbc_provisional_screening_table.csv`](/Users/jang-minyeop/Project/CAMELS/output/basin/drbc_camelsh/screening/drbc_provisional_screening_table.csv): 현재까지 계산된 provisional basin shortlist다.
- [`camelsh_non_drbc_training_selected.csv`](/Users/jang-minyeop/Project/CAMELS/output/basin/camelsh_training_non_drbc/camelsh_non_drbc_training_selected.csv): DRBC holdout 밖에서 quality gate를 통과한 학습용 basin 목록이다.
- [`camelsh_non_drbc_training_summary.json`](/Users/jang-minyeop/Project/CAMELS/output/basin/camelsh_training_non_drbc/camelsh_non_drbc_training_summary.json): global training pool 요약 수치다.
- [`camelsh_basin_master_checklist_broad.csv`](/Users/jang-minyeop/Project/CAMELS/output/basin/checklists/camelsh_basin_master_checklist_broad.csv): CAMELSH 전체 9008 basin에 대해 minimum quality gate와 broad profile `usability_status`를 함께 기록한 공식 checklist다.
- [`camelsh_basin_master_checklist_broad_summary.json`](/Users/jang-minyeop/Project/CAMELS/output/basin/checklists/camelsh_basin_master_checklist_broad_summary.json): broad checklist 집계 요약이다.
- [`drbc_holdout_train_broad.txt`](/Users/jang-minyeop/Project/CAMELS/configs/basin_splits/drbc_holdout_train_broad.txt), [`drbc_holdout_validation_broad.txt`](/Users/jang-minyeop/Project/CAMELS/configs/basin_splits/drbc_holdout_validation_broad.txt), [`drbc_holdout_test_drbc_quality.txt`](/Users/jang-minyeop/Project/CAMELS/configs/basin_splits/drbc_holdout_test_drbc_quality.txt): broad 원본 basin membership file이다. 이 파일은 usability gate 적용 전 단계의 basin 구성을 기록한다.
- [`drbc_holdout_train_natural.txt`](/Users/jang-minyeop/Project/CAMELS/configs/basin_splits/drbc_holdout_train_natural.txt), [`drbc_holdout_validation_natural.txt`](/Users/jang-minyeop/Project/CAMELS/configs/basin_splits/drbc_holdout_validation_natural.txt), [`drbc_holdout_test_drbc_quality_natural.txt`](/Users/jang-minyeop/Project/CAMELS/configs/basin_splits/drbc_holdout_test_drbc_quality_natural.txt): natural 원본 basin membership file이다.
- [`drbc_holdout_split_summary.json`](/Users/jang-minyeop/Project/CAMELS/output/basin/splits/drbc_holdout/drbc_holdout_split_summary.json): global training / regional holdout raw split 요약이다.
- [`split_manifest.csv`](/Users/jang-minyeop/Project/CAMELS/data/CAMELSH_generic/drbc_holdout_broad/splits/split_manifest.csv): broad split 후보 basin의 prepared split 상태와 exclusion reason을 기록한 manifest다. 공식 실행 기준은 이 manifest와 prepared split이다.
- [`configs/pilot/basin_splits/scaling_pilot_summary.json`](/Users/jang-minyeop/Project/CAMELS/configs/pilot/basin_splits/scaling_pilot_summary.json): deterministic scaling pilot subset 생성 요약이다. raw broad pool `1923`과 prepared executable pool `1903`을 함께 기록한다.
- [`configs/pilot/basin_splits/prepared_pool_manifest.csv`](/Users/jang-minyeop/Project/CAMELS/configs/pilot/basin_splits/prepared_pool_manifest.csv): pilot이 실제로 샘플링한 prepared non-DRBC broad pool manifest다. subset manifest와 같은 static attribute 컬럼을 포함한다.
- [`configs/pilot/diagnostics/attribute_distribution_scope_summary.csv`](/Users/jang-minyeop/Project/CAMELS/configs/pilot/diagnostics/attribute_distribution_scope_summary.csv): prepared pool 대비 subset별 static attribute 분포 보존 요약이다.
- [`configs/pilot/diagnostics/event_response/event_response_scope_summary.csv`](/Users/jang-minyeop/Project/CAMELS/configs/pilot/diagnostics/event_response/event_response_scope_summary.csv): prepared pool 대비 subset별 observed-flow event-response 분포 보존 요약이다.
- [`return_period_reference_table.csv`](/Users/jang-minyeop/Project/CAMELS/output/basin/camelsh_all/flood_analysis/return_period_reference_table.csv), [`event_response_table.csv`](/Users/jang-minyeop/Project/CAMELS/output/basin/camelsh_all/flood_analysis/event_response_table.csv), [`flood_generation_basin_summary.csv`](/Users/jang-minyeop/Project/CAMELS/output/basin/camelsh_all/flood_analysis/flood_generation_basin_summary.csv): 서버 all-basin flood analysis runner가 만드는 핵심 산출물이다. `output/` 아래라 git에는 올리지 않는다.
- [`configs/pilot/diagnostics/permutation_benchmark/subset300_random_benchmark_summary.csv`](/Users/jang-minyeop/Project/CAMELS/configs/pilot/diagnostics/permutation_benchmark/subset300_random_benchmark_summary.csv): adopted `scaling_300` subset이 random same-size subset 분포에서 어느 분위에 있는지 요약한 benchmark 결과다.
- [`configs/pilot/diagnostics/plots/plot_manifest.json`](/Users/jang-minyeop/Project/CAMELS/configs/pilot/diagnostics/plots/plot_manifest.json): scaling pilot diagnostics를 빠르게 읽기 위한 SVG plot 목록과 해석 메모다.
- [`configs/pilot/camelsh_hourly_model1_drbc_holdout_scaling_100.yml`](/Users/jang-minyeop/Project/CAMELS/configs/pilot/camelsh_hourly_model1_drbc_holdout_scaling_100.yml), [`configs/pilot/camelsh_hourly_model1_drbc_holdout_scaling_300.yml`](/Users/jang-minyeop/Project/CAMELS/configs/pilot/camelsh_hourly_model1_drbc_holdout_scaling_300.yml), [`configs/pilot/camelsh_hourly_model1_drbc_holdout_scaling_600.yml`](/Users/jang-minyeop/Project/CAMELS/configs/pilot/camelsh_hourly_model1_drbc_holdout_scaling_600.yml): deterministic scaling pilot 전용 config다. broad official config와 별도 경로로 관리한다.

현재 DRBC holdout basin subset은 `outlet_in_drbc == True` 이고 `overlap_ratio_of_basin >= 0.9`인 CAMELSH `154개`다. outlet가 DRBC 안에 들어오는 basin은 `192개`이고, 그중 polygon overlap 기준으로 최종 selected set이 `154개`다.

반대로 학습용 global training pool은 `outlet은 DRBC 밖에 있고`, polygon overlap은 `0.1 이하`까지 허용한 basin으로 잡는다. 이건 CAMELSH polygon과 DRBC 경계 source 차이 때문에 생기는 작은 시각적 겹침을 포함하기 위한 tolerant rule이다. 현재 기준으로 tolerant outside basin은 `8800개`이고, 이 중 quality gate를 통과한 학습 basin은 `1923개`, hydromod risk가 없는 natural training basin은 `248개`다. 실제 tolerant overlap으로 추가된 quality-pass basin은 `3개`뿐이다.

현재 기본 split은 `global training + DRBC regional holdout evaluation` 구조다. 다만 여기서 숫자는 세 층으로 읽어야 한다. `configs/basin_splits/` 아래의 원본 broad basin split은 `train 1722 / validation 201 / DRBC quality-pass test 38`이고, reference pool 역할을 하는 broad prepared split은 `data/CAMELSH_generic/drbc_holdout_broad/splits/` 아래의 `train 1705 / validation 198 / test 38`이다. 현재 compute-constrained main comparison이 직접 사용하는 고정 subset은 `configs/pilot/basin_splits/scaling_300/`의 `train 269 / validation 31 / test 38`이다. 즉 논문과 실행 기준에서 prepared split은 source pool과 checklist 기준으로, subset300은 현재 직접 실행 split으로 읽는 것이 맞다. natural 기준 원본 split은 `train 213 / validation 35 / DRBC natural quality-pass test 8`이다.

compute 제약을 반영한 `scaling pilot`은 main comparison과 역할을 분리하는 운영 결정용 단계였다. pilot은 raw non-DRBC broad pool `1923`을 기준으로 basin 수를 줄일 수 있는지 보고, 실제 실행 가능한 subset은 broad prepared split manifest를 통과한 `1903` basin에서 HUC02-stratified 방식으로 생성했다. tracked subset은 `100 / 300 / 600`이었고 모두 DRBC test `38` basin과 `2000–2010 / 2011–2013 / 2014–2016` 시간 구간을 유지한다. 현재는 pilot 결과를 바탕으로 non-DRBC train/validation basin 수를 `300`으로 고정했고, `configs/pilot/basin_splits/scaling_300/`의 basin file을 Model 1 / Model 2 seed `111 / 222 / 444`에 공통으로 재사용한다. Model 2 seed `333`은 NaN loss로 중단되었고, 공정한 paired-seed 비교를 위해 완료된 Model 1 seed `333`도 final aggregate에서 제외한다. basin-count 선택 근거는 DRBC test metric이 아니라 `non-DRBC validation 성능 + static attribute distribution diagnostics + observed-flow event-response diagnostics + random same-size subset benchmark + compute cost`다. random benchmark 기준으로도 `scaling_300`은 validation split mismatch에서 대체로 random subset보다 더 잘 matched됐고, event-response validation의 경우 random draw `96.5~97.5%`보다 더 좋은 수준이었다.

현재 subset300 DRBC test는 primary checkpoint와 diagnostic sweep을 분리한다. 공식 비교용 checkpoint는 `test`를 보기 전에 validation median NSE 기준으로 고르고, validation이 저장된 epoch `005 / 010 / 015 / 020 / 025 / 030` 전체 test는 checkpoint sensitivity와 epoch30 fixed-budget robustness 확인용으로만 해석한다. Model 2의 `q90/q95/q99` coverage/calibration은 저장 비용 때문에 모든 epoch에 `test_all_output.p`를 만들기보다 selected checkpoint에서 따로 계산한다.

현재 기준은 `DRBC boundary + CAMELSH outlets/selected table`이다. CAMELSH polygon은 selection/QC용으로는 쓰지만, DRBC나 HUC와 같은 공식 경계 polygon으로 보지는 않는다.

현재 screening은 DRBC holdout cohort에 대해 `quality gate + provisional static prioritization`까지 완료된 상태다. 다만 정적 커스텀 점수는 내부 basin shortlist를 빠르게 보는 exploratory 도구로만 쓰고, 최종 flood-prone cohort는 hourly 원시 시계열에서 annual peaks, Q99-level frequency, flashiness, event runoff coefficient를 계산한 뒤 `observed-flow 중심 final screening`으로 확정할 계획이다.

## 관련 문서

- [`docs/workflow/README.md`](docs/workflow/README.md) — basin selection, screening, event workflow의 읽기 순서와 구조 지도
- [`AGENTS.md`](AGENTS.md) — 에이전트 작업 맥락 및 프로젝트 규칙
- [`docs/README.md`](docs/README.md) — `docs/` 전체 문서 인덱스와 카테고리별 읽기 순서
- [`configs/README.md`](configs/README.md) — canonical config, pilot config, raw split, dev config의 역할 구분
- [`scripts/README.md`](scripts/README.md) — official/pilot/dev 실행 진입점과 integrity check 안내
- [`docs/workflow/event_response_spec.md`](docs/workflow/event_response_spec.md) — hourly event extraction 규칙, threshold fallback, rainfall window, 출력 스키마
- [`docs/research/result_analysis_protocol.md`](docs/research/result_analysis_protocol.md) — Model 1 / Model 2 학습과 DRBC test 이후 결과를 어떤 절차와 기준으로 비교·해석할지 정리한 분석 프로토콜
- [`docs/research/defense_playbook.md`](docs/research/defense_playbook.md) — 설계 디펜드용 예상 질문, 취약점, 우선 보강 항목 정리
