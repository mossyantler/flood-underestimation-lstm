# Dataset Evidence Explorer 설계 스펙

**작성일**: 2026-05-21  
**대상**: `dashboard/` Dataset detail page  
**상태**: 사용자 검토 대기  
**목적**: `Foundation / Dataset` page를 설명 카드 중심 화면에서 Markdown, CSV, chart, database cache를 직접 열람하는 evidence workbench prototype으로 전환한다.

## 1. 문제 정의

현재 Dataset detail은 `분석 목적`, `핵심 데이터`, `해석 방법`, `현재 판단`을 카드로 설명하고, 아래에 source path 목록을 보여준다. 이 구조는 데이터의 성격을 설명하기에는 충분하지만, 실제 동료가 합류해서 자료를 확인하기에는 부족하다.

사용자가 기대한 dashboard는 자료가 어디 있는지 말해주는 목록이 아니라, `docs/`, `configs/`, `output/`, `database/local/`에 흩어진 근거를 화면 안에서 바로 여는 viewer다. Dataset page는 이 viewer 구조를 처음 검증하는 prototype으로 쓴다.

## 2. 설계 원칙

Dashboard는 source-of-truth를 대체하지 않는다. 원본 수정은 계속 `docs/`, `configs/`, `output/`, generator script에서 하고, dashboard는 read-only viewer와 provenance layer 역할을 한다.

Dataset page는 아래 세 가지 질문에 답해야 한다.

| 질문 | 화면에서의 답 |
| --- | --- |
| 어떤 데이터인가? | Input / Result / Analysis layer와 짧은 분석 목적 |
| 실제 파일을 볼 수 있나? | Markdown renderer, CSV preview grid, chart viewer |
| 이 파일을 믿어도 되나? | source path, generator path, row/column count, DB catalog metadata |

큰 CSV는 브라우저에 전체를 넣지 않는다. 먼저 `preview rows + columns + row count + file size`를 보여주고, full scan이나 DB query는 명시적인 다음 동작으로 분리한다.

## 3. 화면 구조

Dataset detail page는 `EvidenceBlock` 중심이 아니라 `EvidenceExplorer` 중심으로 재구성한다.

```text
Dataset detail
├─ Context strip
│  ├─ 분석 목적
│  ├─ 해석 방법
│  └─ source-of-truth 주의
├─ EvidenceExplorer
│  ├─ Artifact rail
│  │  ├─ Input
│  │  ├─ Result
│  │  └─ Analysis
│  ├─ Viewer canvas
│  │  ├─ Markdown renderer
│  │  ├─ CSV preview grid
│  │  ├─ Chart/image viewer
│  │  └─ DB preset shell
│  └─ Provenance panel
│     ├─ source path
│     ├─ generator path
│     ├─ kind / role / status
│     └─ file or DB metadata
└─ Related evidence shortcuts
```

`Context strip`은 짧아야 한다. 긴 설명은 Markdown artifact 자체에서 읽고, 상단 strip은 사용자가 viewer를 어떤 관점으로 봐야 하는지만 알려준다.

## 4. Dataset Prototype Artifact Set

첫 prototype은 Dataset module의 대표 artifact만 다룬다.

| Layer | 기본 artifact | Viewer | 역할 |
| --- | --- | --- | --- |
| Input | `docs/experiment/method/data/data_processing_analysis_guide.md` | Markdown | CAMELSH 원천, input/result/analysis data 경계 설명 |
| Input | `configs/pilot/basin_splits/scaling_300/manifest.csv` | CSV preview | 현재 subset300 basin manifest 확인 |
| Input | `output/basin/timeseries/input_coverage/figures/overview.png` | Chart/image | input coverage figure 확인 |
| Result | `output/model_analysis/expanded/expanded_drbc_test/tables/primary_summary_by_seed.csv` | CSV preview | expanded DRBC first test result snapshot 후보 |
| Analysis | `dashboard/data/evidence_catalog_items.csv` | CSV preview | dashboard가 어떤 evidence를 노출하는지 확인 |
| Database | `database/local/duckdb/camels.duckdb` catalog preset | DB preset shell | DB viewer의 위치와 read-only 성격 표시 |

초기 구현에서 DB preset shell은 실제 SQL editor가 아니다. 먼저 `DuckDB catalog`, `PostgreSQL typed tables`, `CSV catalog`의 진입점과 query preset 이름을 보여주고, 실제 query grid는 다음 단계에서 붙인다.

## 5. 컴포넌트 설계

### 5.1 `EvidenceExplorer`

Dataset page 전용으로 먼저 만든다. 추후 Analysis page에 재사용 가능하면 공통 컴포넌트로 승격한다.

역할:

- artifact를 layer별로 묶어 보여준다.
- 선택된 artifact의 viewer type을 결정한다.
- viewer canvas와 provenance panel에 같은 artifact metadata를 전달한다.

필수 상태:

- selected artifact id
- selected layer filter
- CSV preview row count
- viewer error state

### 5.2 `MarkdownViewer`

역할:

- local markdown file을 HTML로 렌더링한다.
- heading hierarchy가 보이게 하고, source path를 숨기지 않는다.
- raw markdown fallback을 제공한다.

초기 범위:

- server-side에서 markdown 파일을 읽어 renderer에 전달한다.
- Mermaid, LaTeX, footnote 같은 확장은 첫 prototype 범위 밖이다.
- dashboard 내부 link는 나중에 route mapping을 붙인다.

### 5.3 `CsvPreview`

역할:

- CSV header, first N rows, row count, column count, file size를 보여준다.
- column이 많을 때 horizontal scroll과 column list를 제공한다.
- viewer-limit 문제를 dashboard 안에서 피한다.

초기 범위:

- server-side preview helper로 파일을 읽는다.
- 기본 preview는 50 rows다.
- sort/filter는 UI slot만 두고 다음 단계에서 구현한다.

### 5.4 `ArtifactImageViewer`

역할:

- PNG/JPG chart를 화면 안에서 확인한다.
- `open source`와 `copy path` 행동을 분리한다.

초기 범위:

- zoom/pan은 다음 단계다.
- public asset에 복사된 chart 또는 safe route를 통해 표시한다.

### 5.5 `DbPresetShell`

역할:

- database cache가 canonical source가 아니라 read-only query aid임을 명시한다.
- Dataset에서 볼 수 있는 DB preset 목록을 보여준다.

초기 preset 후보:

- CSV catalog: `analysis.csv_files`
- observed timeseries view
- basin attribute views
- selected dataset/split metadata

실제 SQL 실행과 result grid는 prototype 검증 후 구현한다.

## 6. Data Flow

첫 구현은 복잡한 backend API보다 Next.js server component/helper를 우선한다.

```text
evidence catalog metadata
→ dataset explorer artifact config
→ server-side file preview helper
→ viewer component
→ provenance panel
```

CSV와 Markdown 파일은 repo-relative path allowlist를 통해 읽는다. 사용자가 임의 path를 URL query로 넘겨 읽는 방식은 쓰지 않는다.

Chart asset은 브라우저가 직접 접근할 수 있어야 한다. `output/`의 이미지를 그대로 public path처럼 노출하지 말고, prototype에서는 기존 `dashboard/public/figures` 패턴이나 안전한 asset mapping을 쓴다.

## 7. Error Handling

Viewer는 파일이 없거나 너무 클 때 빈 화면으로 실패하면 안 된다.

필수 상태:

- `missing`: source path가 없거나 file stat 실패
- `unsupported`: viewer type이 아직 구현되지 않음
- `too-large`: preview 가능하지만 full render 차단
- `stale`: catalog에는 있지만 source artifact가 현재 checkout과 맞지 않음

각 error state는 source path와 다음 확인 행동을 같이 보여준다.

## 8. 검증 기준

구현 완료 판단은 아래를 모두 통과해야 한다.

- `/foundation/dataset`이 3000번 local server에서 열린다.
- Dataset page 첫 화면에서 Markdown artifact가 렌더링된다.
- CSV preview가 header, rows, row/column metadata를 보여준다.
- Chart artifact가 깨진 이미지 없이 표시된다.
- provenance panel에 source path와 role/status가 보인다.
- `npm run typecheck`가 통과한다.
- 브라우저에서 desktop viewport 기준 layout overlap이 없다.

## 9. 범위 밖

이번 prototype에서는 아래를 구현하지 않는다.

- 자유 SQL editor
- CSV full-table client-side load
- markdown 문서 전체 link rewrite
- chart lightbox zoom/pan
- 모든 section에 viewer 일괄 적용
- database cache rebuild

이 범위를 지켜야 Dataset viewer의 사용성이 먼저 검증된다. Prototype이 맞으면 같은 구조를 `Analysis / Main result`, `Analysis / Hydrograph`, `Reference`로 확장한다.
