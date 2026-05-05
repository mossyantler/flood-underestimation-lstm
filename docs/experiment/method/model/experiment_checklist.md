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
  기준 문서는 [`experiment_protocol.md`](experiment_protocol.md)다.

- [x] Model 1 vs Model 2의 통제변인, split, metric, seed protocol이 문서화되어 있다.
  첫 논문 범위에서 무엇을 고정하고 무엇만 바꾸는지가 이미 정리돼 있다.

- [x] basin subset과 holdout / training pool 역할이 문서화되어 있다.
  기준 문서는 [`../basin/basin_cohort_definition.md`](../basin/basin_cohort_definition.md)다.

- [x] probabilistic head의 개념 설명 문서가 있다.
  기준 문서는 [`probabilistic_head_guide.md`](probabilistic_head_guide.md)다.

## 2. Basin / split / data 준비 (4.5 / 5 완료, 90%)

- [x] DRBC holdout region과 non-DRBC training pool 규칙이 고정되어 있다.
  관련 설명과 basin 수치는 [`../basin/basin_cohort_definition.md`](../basin/basin_cohort_definition.md), [`../basin/basin_analysis.md`](../basin/basin_analysis.md)에 정리돼 있다.

- [x] raw basin split 파일과 공식 prepared split이 모두 준비되어 있다.
  `configs/basin_splits/` 아래의 원본 membership 파일 기준으로는 broad split이 `1722 / 201 / 38`, natural split이 `213 / 35 / 8` basin으로 나뉘어 있다. prepared broad split은 `data/CAMELSH_generic/drbc_holdout_broad/splits/` 아래의 `1705 / 198 / 38`이고, 현재 compute-constrained main comparison은 이 prepared pool에서 고정한 `configs/pilot/basin_splits/scaling_300/`의 `269 / 31 / 38` split을 직접 사용한다.

- [x] prepared generic dataset이 존재한다.
  [`../../../../data/CAMELSH_generic/drbc_holdout_broad`](../../../../data/CAMELSH_generic/drbc_holdout_broad) 아래에 `attributes/static_attributes.csv`, `prepare_summary.json`, `splits/`, `time_series/`가 있으며 현재 `time_series`에는 `1961`개 `.nc` 파일이 있다.

- [x] prepared split manifest와 NH-style 데이터 구조가 갖춰져 있다.
  `splits/split_manifest.csv`, `train.txt`, `validation.txt`, `test.txt`가 모두 존재한다. 공식 실행과 논문 baseline count는 이 prepared split과 manifest를 기준으로 읽는 것이 맞다.

- [~] basin 분석 / screening 산출물은 대부분 로컬에서 바로 열 수 있다.
  현재 `output/basin/drbc/` 아래에는 selected basin table, streamflow quality table, event response table이 다시 생성돼 있고, `configs/pilot/diagnostics/event_response/` 아래에는 `scaling_300`의 training-pool representativeness 진단도 생성돼 있다. 다만 DRBC 쪽 final screening table과 일부 부가 시각화 산출물은 아직 닫히지 않았다.

## 3. 모델 설정 및 실행 파이프라인 (4 / 5 완료, 80%)

- [x] Model 1 broad config가 있다.
  [`../../../../configs/camelsh_hourly_model1_drbc_holdout_broad.yml`](../../../../configs/camelsh_hourly_model1_drbc_holdout_broad.yml)이 준비되어 있다.

- [x] Model 2 broad config가 있다.
  [`../../../../configs/camelsh_hourly_model2_drbc_holdout_broad.yml`](../../../../configs/camelsh_hourly_model2_drbc_holdout_broad.yml)이 준비되어 있다.

- [x] 실행 셸 스크립트가 있다.
  [`../../../../scripts/runs/official/run_broad_multiseed.sh`](../../../../scripts/runs/official/run_broad_multiseed.sh)로 reference broad run을 multi-seed로 실행할 수 있고, 현재 채택된 `subset300` main comparison은 [`../../../../scripts/runs/official/run_subset300_multiseed.sh`](../../../../scripts/runs/official/run_subset300_multiseed.sh)로 Model 1 / Model 2 seed `111 / 222 / 444`를 같은 basin file로 반복 실행할 수 있다. Model 2 seed `333`은 NaN loss로 실패했고, Model 1 seed `333`도 final aggregate에서 제외한다. [`../../../../scripts/runs/dev/run_local_sanity.sh`](../../../../scripts/runs/dev/run_local_sanity.sh)는 로컬 점검용이다.

- [~] 현재 공식 학습 run 산출물은 paired seed 기준으로 거의 닫혔다.
  `runs/subset_comparison` 아래에 Model 1 seed `111 / 222 / 333 / 444`와 Model 2 seed `111 / 222`의 complete run 산출물이 있다. final aggregate에는 Model 1 seed `111 / 222 / 444`만 쓰고, Model 1 seed `333`은 paired-seed fairness를 위해 제외한다. Model 2 seed `333`은 NaN loss로 중단된 실패 run이다. replacement seed `444`는 같은 subset과 `batch_size=384`로 epoch 15까지 진행한 뒤 epoch 16에서 isolated NaN loss로 멈췄고, `allow_subsequent_nan_losses=3` resume으로 원격 서버에서 epoch 30까지 완료했다. 다만 resume 산출물이 `_resume_archive/continue_training_from_epoch015` 아래에 남아 있을 수 있으므로, epoch `020 / 025 / 030` test 전에 `model_epoch016.pt`부터 `model_epoch030.pt`와 해당 validation folder가 top-level run directory에 있는지 확인한다.

- [~] 비교용 metric / report 산출물이 부분적으로 있다.
  완료된 subset300 run에는 validation metric CSV와 epoch summary가 생성돼 있어 부분 비교는 가능하다. primary reporting checkpoint는 validation median NSE 기준으로 잠그고, DRBC test는 validation이 저장된 epoch `005 / 010 / 015 / 020 / 025 / 030` 전체 sweep을 sensitivity / robustness 결과로 추가한다. 다만 논문 본문 기준의 model별 `3-repeat mean ± std` 결과표와 최종 test aggregate report는 아직 없다.

## 4. Screening / event 분석 (5 / 6 완료, 83%)

- [x] streamflow quality gate 계산 스크립트가 있다.
  [`../../../../scripts/basin/drbc/build_drbc_streamflow_quality_table.py`](../../../../scripts/basin/drbc/build_drbc_streamflow_quality_table.py)가 준비되어 있다.

- [x] preliminary / provisional screening 스크립트가 있다.
  [`../../../../scripts/basin/drbc/build_drbc_preliminary_screening_table.py`](../../../../scripts/basin/drbc/build_drbc_preliminary_screening_table.py), [`../../../../scripts/basin/drbc/build_drbc_provisional_screening_table.py`](../../../../scripts/basin/drbc/build_drbc_provisional_screening_table.py)가 준비되어 있다.

- [x] event response 규칙 문서와 공식 extraction 스크립트가 있다.
  [`../basin/event_response_spec.md`](../basin/event_response_spec.md)에서 threshold, separation, descriptor 규칙을 고정했고, [`../../../../scripts/basin/drbc/build_drbc_event_response_table.py`](../../../../scripts/basin/drbc/build_drbc_event_response_table.py)로 DRBC holdout event table을 실행할 수 있다. 이 table은 official flood inventory가 아니라 observed high-flow event candidate table로 해석한다. 전 유역 서버 분석은 [`../../../../scripts/runs/official/run_camelsh_flood_analysis.sh`](../../../../scripts/runs/official/run_camelsh_flood_analysis.sh)가 return-period reference, event response, flood generation typing을 순서대로 실행한다.

- [x] observed-flow 기반 event response table 생성이 가능하고 현재 로컬 산출물도 있다.
  [`../../../../output/basin/drbc/analysis/event_response/tables/event_response_table.csv`](../../../../output/basin/drbc/analysis/event_response/tables/event_response_table.csv), [`../../../../output/basin/drbc/analysis/event_response/tables/event_response_basin_summary.csv`](../../../../output/basin/drbc/analysis/event_response/tables/event_response_basin_summary.csv), [`../../../../output/basin/drbc/analysis/event_response/metadata/event_response_summary.json`](../../../../output/basin/drbc/analysis/event_response/metadata/event_response_summary.json)이 생성돼 있고, 현재 quality-pass basin 38개에서 총 7137개 event가 추출된 상태다.

- [x] all-basin observed-flow 분석 runner가 준비되어 있다.
  [`../../../../scripts/basin/all/build_camelsh_return_period_references.py`](../../../../scripts/basin/all/build_camelsh_return_period_references.py), [`../../../../scripts/basin/all/build_camelsh_event_response_table.py`](../../../../scripts/basin/all/build_camelsh_event_response_table.py), [`../../../../scripts/basin/all/build_camelsh_flood_generation_typing.py`](../../../../scripts/basin/all/build_camelsh_flood_generation_typing.py)가 준비되어 있고, 서버 runner는 기본 `WORKERS=4`와 progress bar를 사용한다. `degree_day_v2` typing은 1°C degree-day snowmelt proxy 기반 QA/baseline label로 유지한다. 산출물 위치는 `output/basin/all/analysis/`다.

- [x] ML-based event-regime stratification 비교와 figure 생성 스크립트가 있다.
  [`../../../../scripts/basin/event_regime/compare_camelsh_flood_generation_ml_variants.py`](../../../../scripts/basin/event_regime/compare_camelsh_flood_generation_ml_variants.py), [`../../../../scripts/basin/event_regime/plot_camelsh_flood_generation_ml_variant.py`](../../../../scripts/basin/event_regime/plot_camelsh_flood_generation_ml_variant.py), [`../../../../scripts/basin/event_regime/plot_camelsh_basin_group_maps.py`](../../../../scripts/basin/event_regime/plot_camelsh_basin_group_maps.py)가 준비되어 있다. 현재 채택한 variant는 `hydromet_only_7 + KMeans(k=3)`이고, rule-based label은 이 결과를 점검하는 baseline/QA label로 쓴다.

- [ ] final screening table과 최종 flood-relevant cohort는 아직 확정되지 않았다.
  현재 문서 기준으로도 `static analysis -> quality gate -> provisional screening`까지만 완료된 상태다.

- [ ] event-response / event-regime robustness checks는 아직 닫히지 않았다.
  최종 결과표 전에는 `selected_threshold_quantile`, `flood_relevance_tier`, `return_period_confidence_flag`를 포함하고, `Q99-only`와 fallback 포함 전체 결과가 같은 방향인지 확인한다. 본문 stratification은 ML-based event-regime cluster를 우선 쓰되, `degree_day_v2` rule label과 `uncertain_high_flow_candidate` 포함/제외 sensitivity에서 결론 방향이 크게 흔들리지 않는지도 확인한다.

## 지금 바로 다음에 할 일

1. 서버 all-basin observed-flow runner 산출물을 확인하고, 필요한 경우 DRBC holdout final screening에 쓸 subset을 추출한다.
2. `event_response_basin_summary.csv`와 quality / static table을 합쳐 `final screening table`을 만든다.
3. Q99-only, fallback 포함 전체, return-period confidence flag별 sensitivity와 ML-vs-rule stratification sensitivity를 확인한다.
4. final flood-relevant cohort를 확정하고, 그 cohort 기준으로 공식 DRBC evaluation 범위를 잠근다.
5. Model 2 seed `444` resume 산출물을 top-level 원래 run directory로 복구하고, epoch `016-030` checkpoint와 `validation/model_epoch020/025/030`이 보이는지 확인한다.
6. GPU에서 paired seed `111 / 222 / 444`의 Model 1 / Model 2 validation-epoch DRBC test sweep을 돌린다. 이미 완성된 `test_metrics.csv`와 `test_results.p`는 skip하고, 중간에 끊긴 epoch는 다시 돌린다.
7. subset300 기준 model별 `3-repeat mean ± std` primary validation-best 결과표와 all-epoch sensitivity 결과표를 분리해서 만든다.
8. Model 2의 full-period DRBC `q90/q95/q99` coverage/calibration은 모든 epoch에 `test_all_output.p`를 만들기보다 primary checkpoint와 필요한 robustness checkpoint에서 lean export 또는 selected all-output으로 계산한다. 극한호우 stress test의 all-validation-epoch sensitivity는 full-period dump가 아니라 response-window lean export로 수행한다.

## 관련 문서

- 실험 규범: [`experiment_protocol.md`](experiment_protocol.md)
- basin subset 기준: [`../basin/basin_cohort_definition.md`](../basin/basin_cohort_definition.md)
- basin analysis 현재 상태: [`../basin/basin_analysis.md`](../basin/basin_analysis.md)
- event 정의 규칙: [`../basin/event_response_spec.md`](../basin/event_response_spec.md)
- probabilistic head 설명: [`probabilistic_head_guide.md`](probabilistic_head_guide.md)
