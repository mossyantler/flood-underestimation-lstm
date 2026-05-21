# CAMELS 실험 도움 대시보드 IA 재설계 스펙

**작성일**: 2026-05-21  
**대상**: `dashboard/` Next.js 대시보드  
**목적**: 기존 결과 중심 dashboard를 실험 진행, 실험 설계, 기반 정보, 분석, reference를 함께 다루는 실험 도움 dashboard로 재구성한다.

## 1. 설계 철학

CAMELS dashboard는 논문 결과를 예쁘게 보여주는 화면이 아니라, 연구 claim의 상태와 근거를 관리하고, headline indicator에서 raw hydrologic evidence까지 내려가는 실험 검토 workbench다.

따라서 화면은 아래 원칙을 따른다.

- `Overview`는 연구 진행 KPI와 다음 행동을 보여주는 control tower다.
- `Experiment`는 실험계획, workflow, test matrix, 재현 가능한 실행 경로를 보여준다.
- `Foundation`은 결과를 읽기 전에 필요한 Dataset, Model, Basin 설명을 묶는다.
- `Analysis`는 분석 type별로 가장 적합한 layout을 허용하는 drilldown workspace다.
- `Reference`는 선행연구와 관련연구를 섹션별로 연결하는 living literature map이다.

대시보드 수치와 chart는 claim source-of-truth가 아니다. 공식 근거는 계속 `output/`, `configs/`, `docs/experiment/analysis/`, `docs/experiment/method/`에 있으며, dashboard는 이를 읽기 쉽게 연결하는 표시 layer다.

## 2. Top-Level Navigation

상위 navigation은 5개 장으로 고정한다.

| Icon | Section | 역할 |
| --- | --- | --- |
| `O` | Overview | 프로젝트 진행 상태, 연구 질문, 핵심 결과, 다음 행동 |
| `E` | Experiment | 실험계획, workflow, split/seed/checkpoint policy, test matrix |
| `F` | Foundation | Dataset / Model / Basin 기반 설명 |
| `A` | Analysis | main result, hydrograph, stress, confirmed flood, event regime, attribute, calibration 분석 |
| `R` | Reference | 선행연구, 관련연구, 섹션별 literature mapping |

기존 `Results`, `Stress`, `Confirmed Flood`, `Hydrograph` top-level 섹션은 제거하거나 `Analysis` 내부 module로 이동한다. `R`은 `Results`가 아니라 `Reference`를 뜻한다.

## 3. Sidebar와 Main Canvas 원칙

화면 구조는 아래처럼 동작한다.

```text
Top nav: 큰 장 선택
Sub sidebar: 현재 장 안의 하위 페이지 / 분석 module 진입점
Main canvas: 선택된 하위 페이지 하나를 깊게 표시
```

Sub sidebar는 더 이상 `핵심 판독`과 `증거 흐름`을 고정으로 보여주지 않는다. 새 sidebar는 현재 섹션의 local table of contents다.

예를 들어 `Foundation`에서 sidebar는 `Dataset`, `Model`, `Basin`을 보여주고, main canvas는 현재 선택한 하나의 page만 표시한다. 세 page를 항상 세로로 모두 나열하지 않는다.

`Analysis`에서도 sidebar는 `Main result`, `Hydrograph`, `Stress test`, `Confirmed flood`, `Event regime`, `Attribute analysis`, `Calibration` 같은 module entrypoint를 보여주고, main canvas는 선택된 module의 layout만 표시한다.

`Overview`는 예외적으로 여러 status card와 roadmap을 한 화면에 요약해서 보여준다.

## 4. Section 설계

### 4.1 Overview

Overview는 project control tower다.

포함 내용:

- 연구 질문과 현재 dashboard 목적
- 프로젝트 진행 상태
- 완료 / 진행중 / 준비중 / rerun 필요 상태
- first / extreme / confirmed flood test readiness
- 간단한 핵심 결과
- 다음에 봐야 할 분석 또는 실행 action

주요 컴포넌트:

- research question banner
- project status KPI strip
- analysis readiness board
- quick result cards
- next-action queue

주요 데이터:

- `dashboard/lib/evaluation-tests-data.ts`
- primary result summary
- confirmed flood status snapshot
- expanded rerun flags
- source path와 `generated_at`

KPI dashboard 원칙에 따라 Overview headline indicator는 5-7개 이하로 제한한다. 각 metric은 계산 정의, source path, 공식값인지 보조값인지, caveat를 함께 가져야 한다.

### 4.2 Experiment

Experiment는 실험계획과 workflow 설명 섹션이다.

포함 내용:

- Model 1 / Model 2 공식 비교 구조
- subset300 선택과 split policy
- paired seed policy
- checkpoint selection 기준
- first / extreme / confirmed flood test matrix
- expanded basin 기준으로 다시 해야 하는 작업
- 재현 가능한 실행 command와 source script

주요 컴포넌트:

- experiment workflow diagram
- official comparison table
- split / seed / checkpoint policy cards
- test matrix
- command/source panel
- rerun status board

주요 데이터:

- `configs/`
- split files
- run records
- dashboard test matrix snapshot
- 관련 script path

### 4.3 Foundation

Foundation은 실험 기반 설명 섹션이다. 상위 page 하나 안에서 `Dataset`, `Model`, `Basin`을 내부 tab 또는 subpage로 나눈다.

#### Dataset

목적:

- 우리가 만든 데이터셋이 무엇이고, 어떤 데이터가 있는지 설명한다.
- input data, result data, analysis data를 분리한다.

분류:

| Layer | 의미 | 예시 |
| --- | --- | --- |
| Input data | 모델과 전처리에 들어가는 원천 및 준비 데이터 | CAMELSH source, forcing, static attributes, target streamflow, screening outputs |
| Result data | model inference와 metric raw result | prediction series, primary metrics, event-level raw outputs |
| Analysis data | result를 해석하기 위해 가공한 table/chart | high-flow summary, calibration summary, event regime table, stress aggregate |

주요 컴포넌트:

- data layer tabs
- data catalog table
- source provenance card
- screening logic explainer
- input variable dictionary
- analysis-ready table links

#### Model

목적:

- LSTM 구조와 Model 1 / Model 2 차이를 설명한다.
- loss function, hyperparameter, checkpoint selection을 보여준다.
- 모델 결과 분석으로 넘어가는 진입점을 제공한다.

주요 컴포넌트:

- model architecture diagram
- Model 1 vs Model 2 comparison table
- loss function explainer
- hyperparameter table
- checkpoint policy card
- model diagnostics link

#### Basin

목적:

- DRBC holdout, expanded basin universe, training pool을 설명한다.
- basin attributes와 hydrologic behavior를 결과 해석 전에 이해하게 한다.

주요 컴포넌트:

- basin map
- DRBC / training pool / expanded universe summary
- basin attribute distribution chart
- hydromod risk and static profile table
- basin detail links

### 4.4 Analysis

Analysis는 결과와 분석을 다루는 drilldown workspace다. Type마다 다른 layout을 허용한다.

공통 contract:

- 이 분석이 답하려는 질문
- source data path
- 핵심 table 또는 chart
- 해석
- caveat
- detail link 또는 raw evidence link

분석 module:

| Module | Layout | 주요 내용 |
| --- | --- | --- |
| Main result | paper figure board | high-flow quantile figure, paired seed table, claim/caveat |
| Hydrograph | gallery layout | 기존 hydrograph HTML 구조, basin/event/predictor/regime filter, selected hydrograph detail |
| Stress test | stress/risk layout | historical stress event, benefit vs false-positive tradeoff |
| Confirmed flood | event audit layout | NWS flood-stage event table, map, selected event evidence, hydrograph |
| Event regime | sortable analysis layout | regime별 effect, chart, interpretation |
| Attribute analysis | sortable analysis layout | basin attribute별 sorting, scatter/correlation chart |
| Calibration | chart + table + note | coverage, pinball, q99 interpretation caveat |

Hydrograph는 기존 HTML 산출물 구조를 참고한다.

- `output/model_analysis/legacy/extreme_rain/primary/observed_q99_hydrograph_gallery_index.html`
- `output/model_analysis/legacy/extreme_rain/primary/event_plot_median_map_index.html`
- `output/model_analysis/legacy/analysis_dashboard/index.html`

### 4.5 Reference

Reference는 선행연구와 관련연구를 섹션별로 묶는 living literature map이다.

포함 내용:

- Experiment 관련 reference
- Dataset 관련 reference
- Model 관련 reference
- Basin 관련 reference
- Analysis 관련 reference

Reference card 필드:

- title / year / authors
- 무엇을 다루는 연구인가
- input / process / output
- 우리 dashboard 어느 섹션과 연결되는가
- 우리 분석에 주는 해석 포인트
- limitation
- local note path

Reference는 해석과 방법론 배경이다. 우리 결과 claim의 source-of-truth는 아니다.

## 5. Data와 Metric Governance

대시보드에 표시되는 주요 수치, chart, table은 아래 metadata를 가져야 한다.

- metric definition
- source path
- generated_at 또는 snapshot 생성 시각
- 공식 결과 / 보조 진단 / 준비중 여부
- caveat
- 관련 detail page 또는 raw evidence link

이 원칙은 Q99, confirmed flood, stress, expanded rerun처럼 서로 다른 data universe가 섞일 때 특히 중요하다.

## 6. 구현 우선순위

1. Top-level navigation을 `O / E / F / A / R`로 재구성한다.
2. Sub sidebar를 section-local table of contents로 바꾼다.
3. Overview를 project status KPI board로 재구성한다.
4. Experiment에 workflow, test matrix, policy cards를 배치한다.
5. Foundation에 Dataset / Model / Basin subpage를 만든다.
6. Analysis에 기존 result, hydrograph, stress, confirmed flood, calibration 등을 module로 이동한다.
7. Reference에 section-tagged literature map을 만든다.

## 7. 제외 범위

- Dashboard 내부에서 canonical result를 새로 계산하지 않는다.
- 대용량 raw output이나 full checkpoint를 dashboard에 복사하지 않는다.
- 모든 analysis module을 동일한 layout에 강제하지 않는다.
- Reference를 결과 claim의 공식 근거로 사용하지 않는다.

## 8. 검증 기준

- `/overview`, `/experiment`, `/foundation`, `/analysis`, `/reference`가 top-level route로 동작한다.
- 각 top-level route에서 sub sidebar가 현재 section의 하위 진입점을 보여준다.
- Main canvas는 선택된 하위 page 하나를 깊게 표시한다.
- 주요 metric과 figure에는 source path와 caveat가 붙는다.
- `npm run typecheck`가 통과한다.
- 3000 dev server에서 각 route가 200을 반환한다.
