# Experiment Execution Checklist

## 목적

이 문서는 첫 논문 범위의 CAMELSH 실험 절차를 `실행 체크리스트` 형태로 정리하고, 현재 저장소 기준으로 어디까지 완료되었는지 추적하기 위한 문서다.

현재 상태 평가는 `2026-04-07` 로컬 워크트리를 기준으로 한다. 특히 `runs/`, `output/`, `tmp/` 같은 생성 산출물은 정리해 둔 상태이므로, `코드/설정은 준비되어 있어도 로컬 산출물이 현재 없는 단계`는 완료로 세지지 않는다.

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
| 2. Basin / split / data 준비 | 4.0 / 5.0 | 80% |
| 3. 모델 설정 및 실행 파이프라인 | 3.0 / 5.0 | 60% |
| 4. Screening / event 분석 | 2.5 / 5.0 | 50% |
| 전체 | 13.5 / 19.0 | 71% |

## 1. 실험 설계 고정 (4 / 4 완료, 100%)

- [x] 실험 비교축이 `Model 1 vs Model 2` 구조로 고정되어 있다.
  기준 문서는 [`../research/experiment_protocol.md`](../research/experiment_protocol.md)다.

- [x] Model 1 vs Model 2의 통제변인, split, metric, seed protocol이 문서화되어 있다.
  첫 논문 범위에서 무엇을 고정하고 무엇만 바꾸는지가 이미 정리돼 있다.

- [x] basin subset과 holdout / training pool 역할이 문서화되어 있다.
  기준 문서는 [`basin.md`](basin.md)다.

- [x] probabilistic head의 개념 설명 문서가 있다.
  기준 문서는 [`prob_head.md`](prob_head.md)다.

## 2. Basin / split / data 준비 (4 / 5 완료, 80%)

- [x] DRBC holdout region과 non-DRBC training pool 규칙이 고정되어 있다.
  관련 설명과 basin 수치는 [`basin.md`](basin.md), [`basin_analysis.md`](basin_analysis.md)에 정리돼 있다.

- [x] broad / natural basin split 파일이 준비되어 있다.
  현재 `configs/basin_splits/` 아래에 train / validation / test 텍스트 파일이 있고, broad split은 `1722 / 201 / 38`, natural split은 `213 / 35 / 8` basin으로 나뉘어 있다.

- [x] prepared generic dataset이 존재한다.
  [`../../data/CAMELSH_generic/drbc_holdout_broad`](../../data/CAMELSH_generic/drbc_holdout_broad) 아래에 `attributes/static_attributes.csv`, `prepare_summary.json`, `splits/`, `time_series/`가 있으며 현재 `time_series`에는 `1961`개 `.nc` 파일이 있다.

- [x] prepared split manifest와 NH-style 데이터 구조가 갖춰져 있다.
  `splits/split_manifest.csv`, `train.txt`, `validation.txt`, `test.txt`가 모두 존재한다.

- [ ] basin 분석 / screening 산출물을 로컬에서 바로 열 수 있는 상태는 아니다.
  관련 스크립트와 문서는 있지만, 현재 `output/` 디렉터리는 정리돼 있어서 공식 CSV / JSON / GPKG 산출물은 다시 생성해야 한다.

## 3. 모델 설정 및 실행 파이프라인 (3 / 5 완료, 60%)

- [x] Model 1 broad config가 있다.
  [`../../configs/camelsh_hourly_model1_drbc_holdout_broad.yml`](../../configs/camelsh_hourly_model1_drbc_holdout_broad.yml)이 준비되어 있다.

- [x] Model 2 broad config가 있다.
  [`../../configs/camelsh_hourly_model2_drbc_holdout_broad.yml`](../../configs/camelsh_hourly_model2_drbc_holdout_broad.yml)이 준비되어 있다.

- [x] 실행 셸 스크립트가 있다.
  [`../../scripts/run_camelsh_model1_broad.sh`](../../scripts/run_camelsh_model1_broad.sh), [`../../scripts/run_camelsh_model2_broad.sh`](../../scripts/run_camelsh_model2_broad.sh)이 준비되어 있다. 현재 논문 범위에서 공식 실행 대상은 Model 1과 Model 2 broad run이다.

- [ ] 현재 로컬에 공식 학습 run 산출물은 없다.
  `runs/`를 정리한 상태이므로 checkpoint, TensorBoard log, `output.log` 같은 결과물은 다시 생성해야 한다.

- [ ] 비교용 metric / report 산출물이 현재 로컬에 없다.
  config와 실행 스크립트는 있어도, 현재 상태만으로는 Model 1 vs Model 2 결과표를 바로 열어 볼 수 없다.

## 4. Screening / event 분석 (2.5 / 5 완료, 50%)

- [x] streamflow quality gate 계산 스크립트가 있다.
  [`../../scripts/build_drbc_streamflow_quality_table.py`](../../scripts/build_drbc_streamflow_quality_table.py)가 준비되어 있다.

- [x] preliminary / provisional screening 스크립트가 있다.
  [`../../scripts/build_drbc_preliminary_screening_table.py`](../../scripts/build_drbc_preliminary_screening_table.py), [`../../scripts/build_drbc_provisional_screening_table.py`](../../scripts/build_drbc_provisional_screening_table.py)가 준비되어 있다.

- [~] event response 규칙 문서는 있다.
  [`event_response_spec.md`](event_response_spec.md)에서 threshold, separation, descriptor 규칙은 고정했지만, 현재 저장소에는 그 spec을 실행하는 공식 event extraction 스크립트가 아직 없다.

- [ ] observed-flow 기반 event response table 생성은 아직 미구현 상태다.
  현재는 spec만 있고, basin별 annual peak / Q99 event / RBI / runoff coefficient를 실제로 만드는 공식 스크립트가 없다.

- [ ] final screening table과 최종 flood-prone cohort는 아직 확정되지 않았다.
  현재 문서 기준으로도 `static analysis -> quality gate -> provisional screening`까지만 완료된 상태다.

## 지금 바로 다음에 할 일

1. `output/`을 다시 생성하면서 basin analysis, quality table, provisional screening 산출물을 복구한다.
2. `event_response_spec.md`를 실행하는 event extraction 스크립트를 구현한다.
3. Model 1 / Model 2 broad run을 다시 실행해 공식 비교 run 산출물을 복구한다.
4. observed-flow 기반 `event response table`과 `final screening table`을 만들어 논문용 cohort를 확정한다.

## 관련 문서

- 실험 규범: [`../research/experiment_protocol.md`](../research/experiment_protocol.md)
- basin subset 기준: [`basin.md`](basin.md)
- basin analysis 현재 상태: [`basin_analysis.md`](basin_analysis.md)
- event 정의 규칙: [`event_response_spec.md`](event_response_spec.md)
- probabilistic head 설명: [`prob_head.md`](prob_head.md)
