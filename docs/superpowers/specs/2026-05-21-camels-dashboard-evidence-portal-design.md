# CAMELS Dashboard Evidence Portal 설계 스펙

**작성일**: 2026-05-21  
**대상**: `dashboard/`, `docs/`, `output/`, `database/`  
**상태**: 사용자 검토 대기  
**목적**: CAMELS dashboard를 뒤늦게 합류한 동료와 내부 분석자가 실험 구조, 데이터, 분석 목적, chart/report/source를 쉽게 찾는 onboarding evidence portal로 확장한다.

## 1. 대상 사용자와 dashboard 성격

이 dashboard의 1차 대상은 외부 공개 audience가 아니라 프로젝트 내부 분석자와 뒤늦게 합류한 동료다.

따라서 dashboard는 marketing homepage가 아니라 `project operating homepage`다. 목적은 아래와 같다.

- 실험 구조를 10분 안에 이해한다.
- 현재 실험 상태와 다음 행동을 1분 안에 확인한다.
- 데이터, chart, report, source path를 3-click 안에 찾는다.
- `canonical`, `supporting`, `archive` 성격을 섞지 않는다.
- `input data`, `result data`, `analysis data`, `reference`를 분리해서 보여준다.

Top-level IA는 기존 `Overview / Experiment / Foundation / Analysis / Reference` 구조를 유지한다. 이 스펙은 그 구조 안에 docs/output/report/chart를 어떻게 풍부하게 연결할지 정의한다.

## 2. 사용자 경험 원칙

Dashboard page는 파일 목록이 아니라 실험 안내와 근거 연결을 제공해야 한다.

핵심 흐름:

```text
실험이 뭔가?
→ 어떤 구조로 진행됐나?
→ 어떤 데이터를 썼나?
→ 어떤 모델을 비교했나?
→ 무슨 분석을 봐야 하나?
→ chart/table/report/source는 어디 있나?
```

각 detail page는 아래 7개 블록을 기본 골격으로 쓴다.

| 블록 | 역할 |
| --- | --- |
| 분석 목적 | 이 page/module이 무엇을 확인하려는지 설명 |
| 배경 설명 | 왜 이 분석이 필요하고 어떤 실험 맥락에서 나왔는지 설명 |
| 핵심 데이터 | 이 분석에 쓰이는 input/result/analysis data 요약 |
| 주요 차트 | 먼저 봐야 할 figure, gallery, chart preview |
| 해석 방법 | 지표와 chart/table을 어떻게 읽어야 하는지 설명 |
| 현재 판단 | 지금까지 말할 수 있는 결과와 caveat |
| 근거 경로 | docs/output/csv/html/png/generator path |

`해석 방법`은 단순 chart 사용법이 아니라 연구적으로 어떻게 읽어야 하는지를 설명한다. 예를 들어 `underestimation fraction`은 낮을수록 peak를 덜 놓쳤다는 뜻이지만, `q99`가 calibrated 99% interval이라는 뜻은 아니라고 명시한다.

## 3. Section별 정보 구조

### 3.1 Overview

Overview는 homepage다. 처음 들어온 동료가 프로젝트 목적과 현재 상태를 빠르게 이해해야 한다.

포함 요소:

- 실험 한 줄 소개
- 핵심 가설
- Model 1 vs Model 2 비교 구조
- mini workflow diagram
- 현재 상태 board
- 처음 합류한 동료가 볼 순서
- 핵심 결과 3-5개
- 주요 evidence shortcut

`Start here` 순서는 기본적으로 아래를 따른다.

```text
1. Experiment / comparison
2. Experiment / workflow
3. Foundation / dataset
4. Foundation / model
5. Foundation / basin
6. Analysis / main-result
7. Analysis / hydrograph
8. Analysis / confirmed-flood
```

### 3.2 Experiment

Experiment는 실험 공정성과 workflow를 이해하는 곳이다.

포함 요소:

- 분석 목적: 실험이 공정하게 비교됐는지 이해
- Model 1 / Model 2 공식 비교 구조
- DRBC holdout, subset300, expanded basin universe
- seed/checkpoint policy
- first/extreme/confirmed flood test matrix
- rerun queue
- 관련 command와 generator script

### 3.3 Foundation

Foundation은 결과를 읽기 전 필요한 기반 설명을 제공한다.

Dataset:

- CAMELSH 원천
- input data
- result data
- analysis data
- screening logic
- data source path

Model:

- LSTM 구조
- Model 1 / Model 2 차이
- loss function
- hyperparameter
- checkpoint selection

Basin:

- DRBC boundary
- training pool
- expanded basin universe
- basin attributes
- hydrologic behavior와 analysis 연결

### 3.4 Analysis

Analysis는 workbench다. 각 module은 layout이 달라도 되지만, 7개 설명 블록은 유지한다.

Module:

- Main result
- Hydrograph
- Stress test
- Confirmed flood
- Event regime
- Attribute
- Calibration

예시: `Analysis / Main result`

```text
분석 목적
Model 2 quantile head가 Model 1 대비 extreme peak 과소추정을 줄였는지 확인한다.

배경 설명
Model 1은 하나의 point prediction만 내기 때문에 extreme peak에서 낮게 예측될 수 있다.
Model 2는 같은 LSTM backbone에 quantile head를 붙여 upper-tail prediction을 직접 비교한다.

핵심 데이터
DRBC holdout, paired seed 111/222/444, Q99 exceedance, observed peak hour.

주요 차트
high-flow quantile comparison, peak-hour underestimation chart.

해석 방법
underestimation fraction은 관측값보다 예측값이 낮은 비율이다.
낮을수록 peak를 덜 놓쳤다는 뜻이지만, q99를 calibrated 99% interval로 해석하면 안 된다.

현재 판단
q99는 peak underestimation을 줄이는 방향이 보인다.
다만 calibration과 false-positive tradeoff는 별도 module에서 확인한다.

근거 경로
output/model_analysis/legacy/overall_analysis/main_comparison/
docs/experiment/analysis/model/02_primary_high_flow_peak_performance.md
```

### 3.5 Reference

Reference는 bibliography list가 아니라 section별 근거 map이다.

포함 요소:

- Experiment references
- Dataset references
- Model references
- Basin references
- Analysis references

각 reference item은 어떤 dashboard section/module 판단을 뒷받침하는지 연결해야 한다.

## 4. Evidence Catalog Workflow

Docs/output artifact가 매우 많기 때문에 직접 수동 등록만으로는 유지가 어렵다. 자동 후보 생성과 사람 curation을 분리한다.

```text
docs/output scan
→ candidate artifacts
→ auto classify
→ curation CSV
→ human tag: canonical/supporting/archive
→ dashboard evidence catalog
→ Overview / Foundation / Analysis / Reference
```

### 4.1 생성 파일

```text
dashboard/data/evidence_candidates.csv
dashboard/data/evidence_curation.csv
dashboard/lib/evidence-catalog.ts
dashboard/lib/analysis-copy.ts
```

역할:

- `evidence_candidates.csv`: script가 자동 생성한 전체 후보. 많아도 된다.
- `evidence_curation.csv`: 사람이 수정하는 분류/태깅 table.
- `evidence-catalog.ts`: dashboard runtime에서 쓰는 typed snapshot.
- `analysis-copy.ts`: 각 module의 설명 copy source-of-truth.

긴 설명 문구는 CSV에 넣지 않는다. CSV는 artifact 분류/노출/우선순위 관리에 집중한다.

### 4.2 Scan scope

Scanner는 모든 파일을 같은 우선순위로 후보화하지 않는다. Dashboard는 onboarding/evidence portal이므로 `report`, `summary`, `manifest`, `chart`, `gallery`, `analysis metadata`를 우선한다.

우선 포함:

- `docs/**/*.md`
- `output/**/*report.md`
- `output/**/*.html`
- `output/**/*chart_manifest*.csv`
- `output/**/*manifest*.csv`
- `output/**/*analysis_metadata*.json`
- `output/**/*summary*.json`
- `output/**/*summary*.csv`
- `output/**/*.png`
- `output/**/*.svg`

기본 제외 또는 낮은 우선순위:

- `raw_model_exports/`
- `raw_timeseries/`
- `required_series/`
- epoch별 전체 quantile export CSV
- 아주 큰 event-level CSV

제외된 파일도 완전히 버리지 않는다. 관련 `manifest`, `summary`, `report`가 canonical/supporting evidence로 올라가고, raw file은 필요한 경우 `source_path` 또는 `notes`에서 추적한다.

## 5. CSV Curation Schema

`evidence_curation.csv` column:

```text
id
title
section
module
kind
role
priority
show_in_dashboard
source_path
generator_path
doc_path
chart_path
table_path
gallery_path
analysis_purpose
short_description
tags
status
notes
```

허용값:

```text
section:
overview / experiment / foundation / analysis / reference

kind:
doc / report / chart / table / gallery / script / data

role:
canonical / supporting / archive

priority:
1 = 먼저 보여줌
2 = 관련 근거
3 = 접힘/참고

show_in_dashboard:
true / false

status:
ready / needs-rerun / planned / stale / archive
```

`analysis_purpose`와 `short_description`은 짧은 보조 설명이다. Detail page의 긴 설명은 `analysis-copy.ts`를 기준으로 한다.

## 6. Analysis Copy Source

`dashboard/lib/analysis-copy.ts`를 canonical UI copy source로 둔다.

포함 field:

```ts
type AnalysisModuleCopy = {
  section: "overview" | "experiment" | "foundation" | "analysis" | "reference";
  module: string;
  title: string;
  analysisPurpose: string;
  background: string;
  coreData: string;
  interpretationMethod: string;
  currentJudgment: string;
  status: "ready" | "needs-rerun" | "planned" | "stale" | "archive";
};
```

이 파일은 dashboard 화면 문구의 source-of-truth다. DB는 이 내용을 조회하기 쉽게 mirror할 수 있지만, DB 직접 수정으로 문구를 바꾸지 않는다.

## 7. Database Mirror

DB에도 올린다. 단 DB는 source-of-truth가 아니라 조회/검색/cache mirror다.

Source-of-truth:

- `dashboard/lib/analysis-copy.ts`: module explanation/copy
- `dashboard/data/evidence_curation.csv`: artifact classification
- `docs/`, `output/`, `configs/`: factual source artifact

Generated/mirror:

- `dashboard/lib/evidence-catalog.ts`: dashboard runtime snapshot
- PostgreSQL `analysis_dashboard.*`: DBeaver, typed table, search
- DuckDB view/table: large CSV/output artifact join

DB 직접 `UPDATE`는 금지한다. 값 수정은 TS/CSV/source artifact에서 하고 importer를 다시 실행한다.

### 7.1 PostgreSQL schema

```sql
CREATE SCHEMA IF NOT EXISTS analysis_dashboard;

CREATE TABLE analysis_dashboard.modules (
  module_id text PRIMARY KEY,
  section text NOT NULL,
  module text NOT NULL,
  title text NOT NULL,
  analysis_purpose text NOT NULL,
  background text NOT NULL,
  core_data text NOT NULL,
  interpretation_method text NOT NULL,
  current_judgment text NOT NULL,
  status text NOT NULL,
  updated_at timestamptz NOT NULL
);

CREATE TABLE analysis_dashboard.evidence_items (
  evidence_id text PRIMARY KEY,
  module_id text NOT NULL REFERENCES analysis_dashboard.modules(module_id),
  title text NOT NULL,
  kind text NOT NULL,
  role text NOT NULL,
  priority integer NOT NULL,
  source_path text NOT NULL,
  generator_path text,
  tags text[] NOT NULL,
  status text NOT NULL,
  show_in_dashboard boolean NOT NULL,
  updated_at timestamptz NOT NULL
);
```

### 7.2 DuckDB mirror

DuckDB에도 같은 logical table을 둔다.

용도:

- 큰 output CSV와 evidence catalog join
- artifact coverage 점검
- missing source path, stale artifact, duplicate chart 후보 확인
- DBeaver grid 탐색

## 8. Generator Scripts

초기 script 구조:

```text
scripts/dashboard/scan_evidence_candidates.py
scripts/dashboard/build_evidence_catalog.py
database/postgres/import_dashboard_evidence.py
database/duckdb/build_dashboard_evidence_views.py
```

역할:

- `scan_evidence_candidates.py`: `docs/`와 `output/`를 스캔해 후보 CSV 생성.
- `build_evidence_catalog.py`: curation CSV와 analysis copy를 읽어 final TS snapshot 생성.
- `import_dashboard_evidence.py`: final snapshot 또는 normalized CSV를 PostgreSQL에 import.
- `build_dashboard_evidence_views.py`: DuckDB mirror와 view 생성.

## 9. First Implementation Scope

1차 구현은 전체 artifact를 다 보여주는 것이 아니라 구조를 세우는 데 집중한다.

포함:

- evidence candidate scanner
- CSV curation seed
- `analysis-copy.ts`
- `evidence-catalog.ts`
- PostgreSQL mirror
- DuckDB mirror
- Overview, Foundation/Dataset, Analysis/Main result detail에 catalog block 적용

제외:

- 모든 chart 10,000개 렌더링
- browser 안에서 직접 CSV 편집
- DB를 source-of-truth로 쓰는 방식
- archive artifact를 기본 노출하는 방식

## 10. 검증 기준

- `npm run typecheck` 통과.
- generator script가 `evidence_candidates.csv`, `evidence-catalog.ts`를 재생성한다.
- `evidence_curation.csv`에서 `show_in_dashboard=false`인 item은 dashboard에 보이지 않는다.
- canonical item은 supporting/archive보다 먼저 보인다.
- PostgreSQL과 DuckDB mirror row count가 final catalog와 일치한다.
- missing `source_path`는 generator 검증에서 실패한다.
- `/overview`, `/foundation/dataset`, `/analysis/main-result`가 catalog-backed block을 표시한다.

## 11. 결정 사항

- Dashboard 성격은 `Onboarding Evidence Portal`.
- 대상은 내부 분석자와 뒤늦게 합류한 동료.
- 각 detail page는 7개 블록을 따른다: `분석 목적`, `배경 설명`, `핵심 데이터`, `주요 차트`, `해석 방법`, `현재 판단`, `근거 경로`.
- artifact 후보는 자동 스캔한다.
- curation은 CSV로 한다.
- 긴 UI copy는 `analysis-copy.ts`에서 관리한다.
- DB는 PostgreSQL과 DuckDB 둘 다 만든다.
- DB는 mirror/cache이며 source-of-truth가 아니다.
