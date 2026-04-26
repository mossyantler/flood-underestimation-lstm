# Documentation Layout

이 디렉토리는 코드와 분리해 관리하는 문서 포털이다. 루트 `README.md`가 프로젝트 개요를 다룬다면, `docs/README.md`는 `docs/` 내부 문서 인덱스 역할을 한다.

현재 공식 공간 기준은 DRBC Delaware River Basin 경계이고, 기본 basin 데이터셋은 `CAMELSH`다. 생성된 출력이나 임시 산출물은 `docs/`에 두지 않는다.

## 폴더 역할

- `workflow/`: basin selection, screening, source CSV 해석, event 분석 설계 같은 작업 흐름 문서
- `research/`: 모델 아키텍처, 실험 설계, 선행연구 정리
- `references/`: 외부 강의나 참고 자료를 프로젝트 맥락에 맞게 정리한 학습 노트
- `archive/`: 현재 canonical 문서가 아닌 과거 proposal 초안과 보존용 계획 문서

## 문서별 서술 목적

문서가 서로 닿더라도 `주 질문`이 다르면 분리한다. 어디에 써야 할지 애매하면 `다루지 않는 것`을 먼저 본다.

| 문서                                     | 주 질문                                                                               | 다루지 않는 것                                                     |
| ---------------------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `workflow/README.md`                   | workflow 문서의 구조와 권장 읽기 순서를 어떻게 빠르게 이해할 것인가                   | basin selection 수식, event spec 상세 규칙, experiment config 전체 |
| `workflow/basin_cohort_definition.md`  | 현재 프로젝트의 global training basin과 DRBC holdout evaluation basin 기준은 무엇인가 | screening score, 품질 게이트 수식, source CSV 컬럼 사전            |
| `workflow/basin_source_csv_guide.md`   | basin analysis table을 구성하는 source CSV와 컬럼은 무엇을 뜻하는가                   | 공식 cohort 선정 규칙, 현재 진행 상태                              |
| `workflow/basin_analysis.md`           | 지금까지 어떤 basin 산출물이 만들어졌고, 다음 단계는 무엇인가                         | 논문용 공식 screening 수식과 최종 규범                             |
| `workflow/basin_screening_method.md`   | 논문 본문에서 basin cohort construction을 어떤 방법으로 설명할 것인가                 | 현재 산출물 inventory, exploratory 메모의 상세 로그                |
| `workflow/event_response_spec.md`      | hourly event table을 어떤 규칙과 스키마로 생성할 것인가                               | event type 해석 규칙, basin cohort ranking                         |
| `workflow/flood_generation_typing.md`  | event와 basin을 어떤 flood generation type으로 해석할 것인가                          | event extraction spec의 기준값, screening entry rule               |
| `research/probabilistic_head_guide.md` | probabilistic head를 학부 수준에서 어떻게 직관적으로 설명할 것인가                    | 공식 config key, built-in metric 매핑                              |
| `research/architecture.md`             | 현재 논문 범위의 두 모델 구조와 future-work core 메모를 어떻게 구분할 것인가          | exact split 규칙, config key, run artifact 규칙                    |
| `research/design.md`                   | 이 연구가 무엇을 묻고 어떤 비교를 왜 하는가                                           | 구현 세부 키 이름, built-in/custom metric 경계                     |
| `research/experiment_protocol.md`      | 실험을 실제로 어떤 split, loss, metric, config key, checkpoint rule로 실행할 것인가    | 개념적 배경의 긴 설명, 학부 수준 직관 가이드                       |
| `research/result_analysis_protocol.md` | 학습과 test 이후 Model 1/2 산출물을 어떤 순서와 기준으로 비교하고 해석할 것인가       | split 생성 규칙, event extraction 구현 세부, quantile head 직관   |
| `research/literature_review.md`        | 어떤 문헌을 어디에 왜 인용할 것인가                                                   | 공식 실험 규칙, 현재 코드 상태                                     |
| `research/defense_playbook.md`         | 교수님/심사 질문에 어떤 논리로 답하고, 어디를 먼저 보강해야 하는가                    | source CSV 세부 사전, 구현 코드 라인별 설명                        |
| `references/*`                         | 외부 자료를 프로젝트 맥락으로 어떻게 소화할 것인가                                    | 프로젝트의 공식 기준 문서 역할                                     |
| `archive/*`                            | 과거 proposal 초안과 planning snapshot을 어디에 보존할 것인가                         | 현재 공식 workflow와 실행 규칙                                     |

## Workflow

- [`workflow/README.md`](workflow/README.md): workflow 문서의 구조와 권장 읽기 순서
- [`workflow/basin_cohort_definition.md`](workflow/basin_cohort_definition.md): 현재 공식 basin 정의, global training / DRBC holdout evaluation 기준, 다음 basin analysis 단계 정리
- [`../output/basin/checklists/camelsh_basin_master_checklist_broad.csv`](../output/basin/checklists/camelsh_basin_master_checklist_broad.csv): CAMELSH 전체 basin에 대한 minimum quality gate와 broad profile `usability_status`를 기록한 공식 checklist
- [`workflow/basin_source_csv_guide.md`](workflow/basin_source_csv_guide.md): basin analysis table에 쓰는 source CSV와 변수 해석 가이드
- [`workflow/basin_analysis.md`](workflow/basin_analysis.md): 현재 완료된 static analysis, quality gate, provisional screening과 앞으로 만들 observed-flow screening의 관계 정리
- [`workflow/basin_screening_method.md`](workflow/basin_screening_method.md): basin 선택 이후 공식 screening method와 observed-flow 중심 final screening 설계
- [`workflow/event_response_spec.md`](workflow/event_response_spec.md): hourly event extraction 규칙, threshold fallback, rainfall window, event/basin summary 출력 스키마를 확정한 구현 기준 문서
- [`workflow/flood_generation_typing.md`](workflow/flood_generation_typing.md): event-first flood generation type 분류 설계와 basin-level dominant/mixture 요약 방법
- [`research/probabilistic_head_guide.md`](research/probabilistic_head_guide.md): probabilistic head 개념, q50/q90/q95/q99 선택 이유, pinball loss와 quantile crossing 설명

## Research

- [`research/architecture.md`](research/architecture.md): 현재 논문 범위의 deterministic / probabilistic 두 모델 구조와 future-work conceptual core 메모
- [`research/design.md`](research/design.md): 연구 질문, split, loss, 평가 지표를 포함한 실험 설계
- [`research/experiment_protocol.md`](research/experiment_protocol.md): split 생성 규칙, config key 대응, built-in/custom metric 경계, run 산출물 규칙, subset300 checkpoint selection, all-epoch test sweep 경계와 scaling pilot의 운영 기준을 한 번에 묶은 실행 프로토콜
- [`research/result_analysis_protocol.md`](research/result_analysis_protocol.md): Model 1 / Model 2 학습과 DRBC test 이후 raw artifact에서 어떤 표와 그림을 만들고, primary validation-best 결과와 all-epoch sensitivity 결과를 어떤 순서로 비교·해석할지 정리한 결과 분석 프로토콜
- [`research/subset300_representativeness_report.md`](research/subset300_representativeness_report.md): adopted `scaling_300` subset이 prepared pool을 얼마나 잘 대표하는지와, 왜 이를 현재 main comparison cohort로 고정하는지를 해석한 보고서
- [`research/literature_review.md`](research/literature_review.md): related work 서술 방향과 보강이 필요한 선행연구 축 정리
- [`research/defense_playbook.md`](research/defense_playbook.md): 설계 디펜드용 예상 질문, 취약점, 권장 설계 변경안 정리

## References

- [`references/README.md`](references/README.md): `references/` 폴더의 역할과 현재 참고 자료 목록
- [`references/river_basin_analysis_study_guide.md`](references/river_basin_analysis_study_guide.md): 유역 형상과 하천망 개념을 CAMELS 연구 맥락으로 번역한 학습 가이드
- [`references/model-hyperparameter-glossary.md`](references/model-hyperparameter-glossary.md): 하이퍼파라미터와 주요 config 파라미터를 한 번에 보는 정리집

## Archive

- [`archive/README.md`](archive/README.md): archive 문서의 역할과 읽는 법
- [`archive/proposals/research-plan-extreme-flood-underestimation.md`](archive/proposals/research-plan-extreme-flood-underestimation.md): 비전공 검토자 기준으로 다시 풀어 쓴 상세 연구계획서 초안과 Markdown 구조도 작성 팁
- [`archive/proposals/research-proposal-submission-draft.md`](archive/proposals/research-proposal-submission-draft.md): 표지, 목차, 본문 구성을 갖춘 제출용 연구계획서 초안

에이전트 작업 맥락은 루트의 [`AGENTS.md`](../AGENTS.md)를 참조한다.
