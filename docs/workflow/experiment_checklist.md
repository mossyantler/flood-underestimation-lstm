# Experiment Execution Checklist

## 목적

이 문서는 첫 논문 범위의 CAMELSH 실험 절차를 `실행 체크리스트` 형태로 정리하고, 현재 저장소 기준으로 어디까지 완료되었는지 추적하기 위한 문서다.

현재 상태 평가는 `2026-04-25` 로컬 워크트리와 Elice 서버 실행 준비 상태를 기준으로 한다. 특히 `runs/`, `output/`, `tmp/` 같은 생성 산출물은 수시로 정리하거나 다시 생성하므로, `코드/설정은 준비되어 있어도 로컬 산출물이 현재 없는 단계`는 완료로 세지지 않는다.

## 상태 표기 규칙

- `[x]` 완료: 코드, 설정, 또는 문서가 실제로 준비되어 있고 현재 기준으로 바로 재사용 가능함
- `[~]` 부분 완료: 설계나 스캐폴드까지는 준비됐지만, 본 논문용 최종 구현이나 공식 산출물은 아직 부족함
- `[ ]` 미완료: 아직 구현되지 않았거나, 현재 로컬에 공식 산출물이 없음

진행률 계산은 아래처럼 둔다.

- `[x] = 1.0`
- `[~] = 0.5`
- `[ ] = 0.0`

## 현재 총괄 진행률

| 구간 | 점수 | 진행률 |
| --- | ---: | ---: |
| 1. 실험 설계 고정 | 4.0 / 4.0 | 100% |
| 2. Basin / split / data 준비 | 4.5 / 5.0 | 90% |
| 3. 모델 설정 및 실행 파이프라인 | 4.0 / 5.0 | 80% |
| 4. Screening / event 분석 | 5.0 / 6.0 | 83% |
| 전체 | 17.5 / 20.0 | 88% |

## 1. 실험 설계 고정 (4 / 4 완료, 100%)

- [x] 실험 비교축이 `Model 1 vs Model 2` 구조로 고정되어 있다.
  기준 문서는 [`../research/experiment_protocol.md`](../research/experiment_protocol.md)다.

- [x] Model 1 vs Model 2의 통제변인, split, metric, seed protocol이 문서화되어 있다.
  첫 논문 범위에서 무엇을 고정하고 무엇만 바꾸는지가 이미 정리돼 있다.

- [x] basin subset과 holdout / training pool 역할이 문서화되어 있다.
  기준 문서는 [`basin_cohort_definition.md`](basin_cohort_definition.md)다.

- [x] probabilistic head의 개념 설명 문서가 있다.
  기준 문서는 [`../research/probabilistic_head_guide.md`](../research/probabilistic_head_guide.md)다.

## 2. Basin / split / data 준비 (4.5 / 5 완료, 90%)

- [x] DRBC holdout region과 non-DRBC training pool 규칙이 고정되어 있다.
  관련 설명과 basin 수치는 [`basin_cohort_definition.md`](basin_cohort_definition.md), [`basin_analysis.md`](basin_analysis.md)에 정리돼 있다.

- [x] raw basin split 파일과 공식 prepared split이 모두 준비되어 있다.
  `configs/basin_splits/` 아래의 원본 membership 파일 기준으로는 broad split이 `1722 / 201 / 38`, natural split이 `213 / 35 / 8` basin으로 나뉘어 있다. prepared broad split은 `data/CAMELSH_generic/drbc_holdout_broad/splits/` 아래의 `1705 / 198 / 38`이고, 현재 compute-constrained main comparison은 이 prepared pool에서 고정한 `configs/pilot/basin_splits/scaling_300/`의 `269 / 31 / 38` split을 직접 사용한다.

- [x] prepared generic dataset이 존재한다.
  [`../../data/CAMELSH_generic/drbc_holdout_broad`](../../data/CAMELSH_generic/drbc_holdout_broad) 아래에 `attributes/static_attributes.csv`, `prepare_summary.json`, `splits/`, `time_series/`가 있으며 현재 `time_series`에는 `1961`개 `.nc` 파일이 있다.

- [x] prepared split manifest와 NH-style 데이터 구조가 갖춰져 있다.
  `splits/split_manifest.csv`, `train.txt`, `validation.txt`, `test.txt`가 모두 존재한다. 공식 실행과 논문 baseline count는 이 prepared split과 manifest를 기준으로 읽는 것이 맞다.

- [~] basin 분석 / screening 산출물은 대부분 로컬에서 바로 열 수 있다.
  현재 `output/basin/drbc_camelsh/` 아래에는 selected basin table, streamflow quality table, event response table이 다시 생성돼 있고, `configs/pilot/diagnostics/event_response/` 아래에는 `scaling_300`의 training-pool representativeness 진단도 생성돼 있다. 다만 DRBC 쪽 final screening table과 일부 부가 시각화 산출물은 아직 닫히지 않았다.

## 3. 모델 설정 및 실행 파이프라인 (4 / 5 완료, 80%)

- [x] Model 1 broad config가 있다.
  [`../../configs/camelsh_hourly_model1_drbc_holdout_broad.yml`](../../configs/camelsh_hourly_model1_drbc_holdout_broad.yml)이 준비되어 있다.

- [x] Model 2 broad config가 있다.
  [`../../configs/camelsh_hourly_model2_drbc_holdout_broad.yml`](../../configs/camelsh_hourly_model2_drbc_holdout_broad.yml)이 준비되어 있다.

- [x] 실행 셸 스크립트가 있다.
  [`../../scripts/official/run_broad_multiseed.sh`](../../scripts/official/run_broad_multiseed.sh)로 reference broad run을 multi-seed로 실행할 수 있고, 현재 채택된 `subset300` main comparison은 [`../../scripts/official/run_subset300_multiseed.sh`](../../scripts/official/run_subset300_multiseed.sh)로 Model 1 / Model 2 seed `111 / 222 / 444`를 같은 basin file로 반복 실행할 수 있다. Model 2 seed `333`은 NaN loss로 실패했고, Model 1 seed `333`도 final aggregate에서 제외한다. [`../../scripts/dev/run_local_sanity.sh`](../../scripts/dev/run_local_sanity.sh)는 로컬 점검용이다.

- [~] 현재 로컬에 공식 학습 run 산출물이 일부 있다.
  `runs/subset_comparison` 아래에 Model 1 seed `111 / 222 / 333 / 444`와 Model 2 seed `111 / 222`의 complete run 산출물이 있다. final aggregate에는 Model 1 seed `111 / 222 / 444`만 쓰고, Model 1 seed `333`은 paired-seed fairness를 위해 제외한다. Model 2 seed `333`은 NaN loss로 중단된 실패 run이고, replacement seed `444`는 같은 subset과 `batch_size=384`로 시작되어 현재 local artifact 기준 epoch `001`까지만 동기화되어 있다.

- [~] 비교용 metric / report 산출물이 부분적으로 있다.
  완료된 subset300 run에는 validation metric CSV와 epoch summary가 생성돼 있어 부분 비교는 가능하다. 다만 논문 본문 기준의 model별 `3-repeat mean ± std` 결과표와 최종 test aggregate report는 아직 없다.

## 4. Screening / event 분석 (5 / 6 완료, 83%)

- [x] streamflow quality gate 계산 스크립트가 있다.
  [`../../scripts/build_drbc_streamflow_quality_table.py`](../../scripts/build_drbc_streamflow_quality_table.py)가 준비되어 있다.

- [x] preliminary / provisional screening 스크립트가 있다.
  [`../../scripts/build_drbc_preliminary_screening_table.py`](../../scripts/build_drbc_preliminary_screening_table.py), [`../../scripts/build_drbc_provisional_screening_table.py`](../../scripts/build_drbc_provisional_screening_table.py)가 준비되어 있다.

- [x] event response 규칙 문서와 공식 extraction 스크립트가 있다.
  [`event_response_spec.md`](event_response_spec.md)에서 threshold, separation, descriptor 규칙을 고정했고, [`../../scripts/build_drbc_event_response_table.py`](../../scripts/build_drbc_event_response_table.py)로 DRBC holdout event table을 실행할 수 있다. 전 유역 서버 분석은 [`../../scripts/official/run_camelsh_flood_analysis.sh`](../../scripts/official/run_camelsh_flood_analysis.sh)가 return-period reference, event response, flood generation typing을 순서대로 실행한다.

- [x] observed-flow 기반 event response table 생성이 가능하고 현재 로컬 산출물도 있다.
  [`../../output/basin/drbc_camelsh/screening/event_response_table.csv`](../../output/basin/drbc_camelsh/screening/event_response_table.csv), [`../../output/basin/drbc_camelsh/screening/event_response_basin_summary.csv`](../../output/basin/drbc_camelsh/screening/event_response_basin_summary.csv), [`../../output/basin/drbc_camelsh/screening/event_response_summary.json`](../../output/basin/drbc_camelsh/screening/event_response_summary.json)이 생성돼 있고, 현재 quality-pass basin 38개에서 총 7137개 event가 추출된 상태다.

- [x] all-basin observed-flow 분석 runner가 준비되어 있다.
  [`../../scripts/build_camelsh_return_period_references.py`](../../scripts/build_camelsh_return_period_references.py), [`../../scripts/build_camelsh_event_response_table.py`](../../scripts/build_camelsh_event_response_table.py), [`../../scripts/build_camelsh_flood_generation_typing.py`](../../scripts/build_camelsh_flood_generation_typing.py)가 준비되어 있고, 서버 runner는 기본 `WORKERS=2`와 progress bar를 사용한다. 산출물 위치는 `output/basin/camelsh_all/flood_analysis/`다.

- [ ] final screening table과 최종 flood-prone cohort는 아직 확정되지 않았다.
  현재 문서 기준으로도 `static analysis -> quality gate -> provisional screening`까지만 완료된 상태다.

## 지금 바로 다음에 할 일

1. 서버 all-basin observed-flow runner 산출물을 확인하고, 필요한 경우 DRBC holdout final screening에 쓸 subset을 추출한다.
2. `event_response_basin_summary.csv`와 quality / static table을 합쳐 `final screening table`을 만든다.
3. final flood-prone cohort를 확정하고, 그 cohort 기준으로 공식 DRBC evaluation 범위를 잠근다.
4. [`../../scripts/official/run_subset300_multiseed.sh`](../../scripts/official/run_subset300_multiseed.sh)로 Model 2 replacement seed `444`를 현재 고정한 `scaling_300` subset에서 완료한다.
5. subset300 기준 model별 `3-repeat mean ± std` validation/test 결과표를 만들고, 필요하면 broad reference run은 별도 보강 실험으로 분리한다.

## 관련 문서

- 실험 규범: [`../research/experiment_protocol.md`](../research/experiment_protocol.md)
- basin subset 기준: [`basin_cohort_definition.md`](basin_cohort_definition.md)
- basin analysis 현재 상태: [`basin_analysis.md`](basin_analysis.md)
- event 정의 규칙: [`event_response_spec.md`](event_response_spec.md)
- probabilistic head 설명: [`../research/probabilistic_head_guide.md`](../research/probabilistic_head_guide.md)
