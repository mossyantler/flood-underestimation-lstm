# CAMELS Dashboard IA Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the dashboard information architecture around `Overview / Experiment / Foundation / Analysis / Reference`, with section-local sidebars and selected-page main content.

**Architecture:** Keep the existing Next.js App Router shell, but replace the section registry and sidebar model. Use focused data registries for navigation metadata, section entrypoints, status cards, and analysis modules so page components stay small. Preserve existing result/figure components by moving them under the new `Analysis` section instead of deleting them.

**Tech Stack:** Next.js 15 App Router, React 19, TypeScript, CSS variables in `dashboard/app/globals.css`, local typed snapshots under `dashboard/lib/`.

---

## File Structure

Create or modify these files:

- Modify `dashboard/lib/sections.ts`: replace old `O/H/D/M/R/A/S/F` registry with `O/E/F/A/R`, add section-local entrypoints.
- Create `dashboard/lib/overview-data.ts`: status KPI, readiness, quick result, next-action typed data.
- Create `dashboard/lib/experiment-data.ts`: workflow, policy cards, test matrix links, command/source panel data.
- Create `dashboard/lib/foundation-data.ts`: Dataset / Model / Basin tabs, catalogs, model explainer, basin summary data.
- Create `dashboard/lib/analysis-modules.ts`: module registry for Main result, Hydrograph, Stress test, Confirmed flood, Event regime, Attribute analysis, Calibration.
- Create `dashboard/lib/reference-data.ts`: section-tagged reference card seed data from existing local notes.
- Modify `dashboard/components/context-sidebar.tsx`: remove fixed `핵심 판독` / `증거 흐름`; render current section entrypoints.
- Modify `dashboard/components/mobile-topbar.tsx`: render new top-level sections and expose section entrypoints on mobile.
- Modify `dashboard/components/icon-rail.tsx`: new top-level rail order and labels.
- Create `dashboard/components/status-board.tsx`: Overview status cards and next-action queue.
- Create `dashboard/components/workflow-panel.tsx`: Experiment workflow and policy cards.
- Create `dashboard/components/foundation-tabs.tsx`: Dataset / Model / Basin selected subpage renderer.
- Create `dashboard/components/analysis-module-index.tsx`: Analysis module index and selected module renderer.
- Create `dashboard/components/reference-map.tsx`: Reference cards grouped by dashboard section.
- Modify `dashboard/app/[section]/page.tsx`: route the five top-level sections to their new section components.
- Modify `dashboard/app/[section]/[detail]/page.tsx`: accept new detail slugs and redirect or preserve old detail content under Analysis.
- Modify `dashboard/app/globals.css`: add sidebar entrypoint, status board, workflow, foundation, analysis module, reference card styles.
- Modify `dashboard/README.md`: document new IA, routes, source-data governance, and 3000 dev-server caveat.

## Task 1: Replace Section Registry

**Files:**
- Modify: `dashboard/lib/sections.ts`

- [ ] **Step 1: Replace section IDs and labels**

Use this complete registry:

```ts
export const SECTION_IDS = ["O", "E", "F", "A", "R"] as const;
export type SectionId = (typeof SECTION_IDS)[number];

export const SECTION_SLUG: Record<SectionId, string> = {
  O: "overview",
  E: "experiment",
  F: "foundation",
  A: "analysis",
  R: "reference",
};

export const SECTION_LABEL: Record<SectionId, string> = {
  O: "Overview",
  E: "Experiment",
  F: "Foundation",
  A: "Analysis",
  R: "Reference",
};

export const SECTION_ACCENT: Record<SectionId, string> = {
  O: "#6bb4ff",
  E: "#f7b955",
  F: "#50e3c2",
  A: "#ff6b8a",
  R: "#b69bff",
};

export const SECTION_ROUTE: Record<SectionId, string> = {
  O: "/overview",
  E: "/experiment",
  F: "/foundation",
  A: "/analysis",
  R: "/reference",
};

export const SLUG_TO_ID: Record<string, SectionId> = Object.fromEntries(
  Object.entries(SECTION_SLUG).map(([id, slug]) => [slug, id as SectionId])
);

export const SECTION_SUBTITLE: Record<SectionId, string> = {
  O: "프로젝트 상태와 다음 행동",
  E: "실험계획과 실행 workflow",
  F: "Dataset, Model, Basin 기반 설명",
  A: "결과와 분석 module",
  R: "선행연구와 관련연구 map",
};

export type SidebarEntry = {
  slug: string;
  label: string;
  description: string;
  status?: "ready" | "in-progress" | "needs-rerun" | "planned";
};

export const SECTION_ENTRYPOINTS: Record<SectionId, SidebarEntry[]> = {
  O: [
    { slug: "status", label: "Status", description: "완료/진행/준비 상태", status: "ready" },
    { slug: "roadmap", label: "Roadmap", description: "논문 목적별 분석 경로", status: "ready" },
    { slug: "quick-results", label: "Quick results", description: "현재 핵심 결과", status: "ready" },
    { slug: "next-actions", label: "Next actions", description: "rerun 및 검토 queue", status: "in-progress" },
  ],
  E: [
    { slug: "comparison", label: "Official comparison", description: "Model 1 vs Model 2 비교축", status: "ready" },
    { slug: "split-policy", label: "Split policy", description: "subset300, DRBC holdout", status: "ready" },
    { slug: "seed-checkpoint", label: "Seed & checkpoint", description: "paired seed와 primary epoch", status: "ready" },
    { slug: "test-matrix", label: "Test matrix", description: "first/extreme/confirmed flood", status: "in-progress" },
    { slug: "workflow", label: "Workflow", description: "재현 command와 script", status: "planned" },
  ],
  F: [
    { slug: "dataset", label: "Dataset", description: "input/result/analysis data", status: "ready" },
    { slug: "model", label: "Model", description: "LSTM, head, loss, hyperparameter", status: "ready" },
    { slug: "basin", label: "Basin", description: "DRBC, training pool, attributes", status: "in-progress" },
  ],
  A: [
    { slug: "main-result", label: "Main result", description: "paper figure board", status: "ready" },
    { slug: "hydrograph", label: "Hydrograph", description: "gallery와 event detail", status: "in-progress" },
    { slug: "stress", label: "Stress test", description: "historical stress와 tradeoff", status: "needs-rerun" },
    { slug: "confirmed-flood", label: "Confirmed flood", description: "NWS flood-stage audit", status: "ready" },
    { slug: "event-regime", label: "Event regime", description: "regime별 effect", status: "ready" },
    { slug: "attribute", label: "Attribute", description: "basin attribute sorting", status: "planned" },
    { slug: "calibration", label: "Calibration", description: "coverage, pinball, q99 caveat", status: "ready" },
  ],
  R: [
    { slug: "experiment", label: "Experiment refs", description: "PUB/PUR, split, fairness", status: "planned" },
    { slug: "dataset", label: "Dataset refs", description: "CAMELS/CAMELSH", status: "planned" },
    { slug: "model", label: "Model refs", description: "LSTM, quantile, pinball", status: "planned" },
    { slug: "basin", label: "Basin refs", description: "DRBC, hydrologic controls", status: "planned" },
    { slug: "analysis", label: "Analysis refs", description: "flood typing, SHAP, stress", status: "planned" },
  ],
};
```

- [ ] **Step 2: Run typecheck and capture expected failures**

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd dashboard
npm run typecheck
```

Expected: TypeScript fails in files still referencing old section IDs like `H`, `D`, `M`, `S`, `F`. Do not fix by adding old sections back.

- [ ] **Step 3: Commit**

```bash
git add dashboard/lib/sections.ts
git commit -m "refactor: define dashboard top-level sections"
```

## Task 2: Convert Sidebar to Section Entrypoints

**Files:**
- Modify: `dashboard/components/context-sidebar.tsx`
- Modify: `dashboard/app/globals.css`

- [ ] **Step 1: Replace context sidebar content**

Replace fixed evidence cards with entrypoint rendering:

```tsx
import Link from "next/link";
import {
  SECTION_LABEL,
  SECTION_SUBTITLE,
  SECTION_ACCENT,
  SECTION_SLUG,
  SECTION_ENTRYPOINTS,
  type SectionId,
} from "@/lib/sections";

const STATUS_LABEL = {
  ready: "ready",
  "in-progress": "in progress",
  "needs-rerun": "needs rerun",
  planned: "planned",
} as const;

export function ContextSidebar({ activeId }: { activeId: SectionId }) {
  const accent = SECTION_ACCENT[activeId];
  const entries = SECTION_ENTRYPOINTS[activeId];
  const sectionSlug = SECTION_SLUG[activeId];

  return (
    <aside className="ctx-sidebar" style={{ "--section-accent": accent } as React.CSSProperties}>
      <div
        className="ctx-product-mark"
        style={{
          background: `color-mix(in srgb, ${accent} 14%, #0a0a0a)`,
          border: `1px solid ${accent}`,
          color: accent,
        }}
      >
        {activeId}
      </div>
      <p className="ctx-welcome">CAMELS Dashboard</p>
      <h2 className="ctx-title">{SECTION_LABEL[activeId]}</h2>
      <p className="ctx-subtitle">{SECTION_SUBTITLE[activeId]}</p>

      <nav className="ctx-entry-list" aria-label={`${SECTION_LABEL[activeId]} 하위 메뉴`}>
        {entries.map((entry) => (
          <Link
            className="ctx-entry"
            href={`/${sectionSlug}/${entry.slug}`}
            key={entry.slug}
          >
            <span className="ctx-entry-top">
              <strong>{entry.label}</strong>
              {entry.status && <em data-status={entry.status}>{STATUS_LABEL[entry.status]}</em>}
            </span>
            <span>{entry.description}</span>
          </Link>
        ))}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 2: Add sidebar styles**

Append after existing `.ev-val` styles or replace old evidence styles with:

```css
.ctx-entry-list {
  display: grid;
  gap: 8px;
  margin-top: 4px;
}

.ctx-entry {
  border: 1px solid var(--hairline);
  border-radius: var(--r-md);
  color: inherit;
  display: grid;
  gap: 5px;
  padding: 10px;
  text-decoration: none;
}

.ctx-entry:hover {
  background: var(--panel-deep);
  border-color: var(--section-accent, var(--accent-O));
}

.ctx-entry-top {
  align-items: center;
  display: flex;
  gap: 8px;
  justify-content: space-between;
}

.ctx-entry strong {
  color: var(--ink-body);
  font-size: 11px;
  font-weight: 650;
}

.ctx-entry span:last-child {
  color: var(--ink-muted);
  font-size: 10px;
  line-height: 1.45;
}

.ctx-entry em {
  border: 1px solid var(--hairline-tbl);
  border-radius: 999px;
  color: var(--ink-dim);
  font-family: var(--font-geist-mono), monospace;
  font-size: 8px;
  font-style: normal;
  padding: 2px 6px;
  white-space: nowrap;
}

.ctx-entry em[data-status="ready"] { color: #50e3c2; }
.ctx-entry em[data-status="in-progress"] { color: #f7b955; }
.ctx-entry em[data-status="needs-rerun"] { color: #ff6b8a; }
```

- [ ] **Step 3: Run typecheck**

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd dashboard
npm run typecheck
```

Expected: Any remaining errors should be from old route/page assumptions, not `context-sidebar.tsx`.

- [ ] **Step 4: Commit**

```bash
git add dashboard/components/context-sidebar.tsx dashboard/app/globals.css
git commit -m "refactor: turn dashboard sidebar into section entrypoints"
```

## Task 3: Add Overview Data and Status Board

**Files:**
- Create: `dashboard/lib/overview-data.ts`
- Create: `dashboard/components/status-board.tsx`
- Modify: `dashboard/app/[section]/page.tsx`

- [ ] **Step 1: Add typed overview data**

Create `dashboard/lib/overview-data.ts`:

```ts
export type DashboardStatus = "ready" | "in-progress" | "needs-rerun" | "planned";

export type StatusKpi = {
  label: string;
  value: string;
  note: string;
  status: DashboardStatus;
  source: string;
};

export type ReadinessItem = {
  name: string;
  status: DashboardStatus;
  question: string;
  currentEvidence: string;
  nextAction: string;
  href: string;
};

export const overviewStatusKpis: StatusKpi[] = [
  {
    label: "Top-level IA",
    value: "5 sections",
    note: "O / E / F / A / R",
    status: "ready",
    source: "docs/superpowers/specs/2026-05-21-camels-dashboard-ia-redesign.md",
  },
  {
    label: "Official seeds",
    value: "3",
    note: "111 / 222 / 444 paired comparison",
    status: "ready",
    source: "docs/experiment/method/model/architecture.md",
  },
  {
    label: "First test",
    value: "expanded rerun",
    note: "primary basin universe mismatch",
    status: "needs-rerun",
    source: "dashboard/lib/evaluation-tests-data.ts",
  },
  {
    label: "Extreme test",
    value: "expanded rerun",
    note: "stress catalog must match expanded basin universe",
    status: "needs-rerun",
    source: "dashboard/lib/evaluation-tests-data.ts",
  },
  {
    label: "Confirmed flood",
    value: "ready",
    note: "NWS flood-stage event layer",
    status: "ready",
    source: "output/model_analysis/confirmed_flood/",
  },
];

export const readinessItems: ReadinessItem[] = [
  {
    name: "Experiment workflow",
    status: "in-progress",
    question: "실험계획과 실행 경로가 재현 가능하게 보이는가?",
    currentEvidence: "Model 1/2, subset300, paired seed rule은 문서화됨",
    nextAction: "workflow diagram과 command panel을 Experiment에 배치",
    href: "/experiment/workflow",
  },
  {
    name: "Foundation",
    status: "planned",
    question: "Dataset / Model / Basin 기반 설명이 결과와 분리되어 있는가?",
    currentEvidence: "spec에서 Foundation으로 통합 결정",
    nextAction: "Dataset, Model, Basin subpage skeleton 생성",
    href: "/foundation/dataset",
  },
  {
    name: "Analysis modules",
    status: "in-progress",
    question: "분석 type마다 맞는 layout으로 raw evidence까지 내려가는가?",
    currentEvidence: "기존 chart preview와 confirmed flood dashboard 일부 존재",
    nextAction: "기존 Results/Hydrograph/Stress/Flood를 Analysis module로 이동",
    href: "/analysis/main-result",
  },
  {
    name: "Reference map",
    status: "planned",
    question: "선행연구가 dashboard 섹션과 연결되어 있는가?",
    currentEvidence: "docs/references에 local literature notes 존재",
    nextAction: "section-tagged reference card seed data 작성",
    href: "/reference/experiment",
  },
];
```

- [ ] **Step 2: Create status board component**

Create `dashboard/components/status-board.tsx`:

```tsx
import Link from "next/link";
import { overviewStatusKpis, readinessItems, type DashboardStatus } from "@/lib/overview-data";

const STATUS_TEXT: Record<DashboardStatus, string> = {
  ready: "완료",
  "in-progress": "진행중",
  "needs-rerun": "rerun 필요",
  planned: "준비중",
};

export function StatusBoard() {
  return (
    <section className="status-board">
      <div className="status-kpi-grid">
        {overviewStatusKpis.map((item) => (
          <article className="status-kpi" data-status={item.status} key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <p>{item.note}</p>
            <code>{item.source}</code>
          </article>
        ))}
      </div>

      <div className="panel research-panel">
        <div className="panel-sub">Analysis readiness</div>
        <div className="panel-title">다음에 봐야 할 작업</div>
        <div className="readiness-list">
          {readinessItems.map((item) => (
            <Link href={item.href} className="readiness-row" data-status={item.status} key={item.name}>
              <span>
                <strong>{item.name}</strong>
                <em>{STATUS_TEXT[item.status]}</em>
              </span>
              <p>{item.question}</p>
              <small>{item.currentEvidence}</small>
              <small>{item.nextAction}</small>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Add minimal styles**

Append to `dashboard/app/globals.css`:

```css
.status-board {
  display: grid;
  gap: 14px;
}

.status-kpi-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.status-kpi {
  background: var(--panel);
  border: 1px solid var(--hairline);
  border-radius: var(--r-lg);
  display: grid;
  gap: 6px;
  min-width: 0;
  padding: 13px;
}

.status-kpi span,
.status-kpi code {
  color: var(--ink-dim);
  font-family: var(--font-geist-mono), monospace;
  font-size: 9px;
  overflow-wrap: anywhere;
}

.status-kpi strong {
  color: var(--ink);
  font-size: 19px;
}

.status-kpi p {
  color: var(--ink-muted);
  font-size: 11px;
  line-height: 1.45;
  margin: 0;
}

.status-kpi[data-status="ready"] { border-color: color-mix(in srgb, #50e3c2 45%, var(--hairline)); }
.status-kpi[data-status="in-progress"] { border-color: color-mix(in srgb, #f7b955 45%, var(--hairline)); }
.status-kpi[data-status="needs-rerun"] { border-color: color-mix(in srgb, #ff6b8a 45%, var(--hairline)); }

.readiness-list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.readiness-row {
  border: 1px solid var(--hairline);
  border-radius: var(--r-md);
  color: inherit;
  display: grid;
  gap: 5px;
  padding: 11px;
  text-decoration: none;
}

.readiness-row span {
  align-items: center;
  display: flex;
  gap: 8px;
  justify-content: space-between;
}

.readiness-row strong { color: var(--ink-body); }
.readiness-row em {
  color: var(--ink-dim);
  font-family: var(--font-geist-mono), monospace;
  font-size: 9px;
  font-style: normal;
}
.readiness-row p,
.readiness-row small {
  color: var(--ink-muted);
  font-size: 10px;
  line-height: 1.45;
  margin: 0;
}

@media (max-width: 899px) {
  .status-kpi-grid { grid-template-columns: 1fr; }
}
```

- [ ] **Step 4: Use StatusBoard in overview**

In `dashboard/app/[section]/page.tsx`, import `StatusBoard` and make `OverviewSection` render it:

```tsx
import { StatusBoard } from "@/components/status-board";

function OverviewSection() {
  return (
    <>
      <p className="section-lede">
        CAMELS dashboard는 연구 claim의 상태와 근거를 관리하고, headline indicator에서 raw hydrologic evidence까지 내려가는 실험 검토 workbench다.
      </p>
      <StatusBoard />
    </>
  );
}
```

- [ ] **Step 5: Run typecheck**

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd dashboard
npm run typecheck
```

Expected: Overview files pass; old route errors may remain until Task 4.

- [ ] **Step 6: Commit**

```bash
git add dashboard/lib/overview-data.ts dashboard/components/status-board.tsx dashboard/app/[section]/page.tsx dashboard/app/globals.css
git commit -m "feat: add dashboard overview status board"
```

## Task 4: Rebuild Top-Level Page Routing

**Files:**
- Modify: `dashboard/app/[section]/page.tsx`
- Create: `dashboard/components/workflow-panel.tsx`
- Create: `dashboard/components/foundation-tabs.tsx`
- Create: `dashboard/components/analysis-module-index.tsx`
- Create: `dashboard/components/reference-map.tsx`

- [ ] **Step 1: Create placeholder section components with real content**

Create `workflow-panel.tsx`:

```tsx
export function WorkflowPanel() {
  return (
    <section className="panel-grid">
      <article className="panel research-panel">
        <div className="panel-sub">Official comparison</div>
        <div className="panel-title">Model 1 vs Model 2</div>
        <p className="panel-body">
          Model 1은 deterministic multi-basin LSTM이고, Model 2는 같은 backbone에 quantile head만 추가한다.
          비교의 핵심은 output design 변경만으로 extreme flood peak underestimation이 줄어드는지 확인하는 것이다.
        </p>
        <div className="source-path">docs/experiment/method/model/architecture.md</div>
      </article>
      <article className="panel research-panel">
        <div className="panel-sub">Workflow</div>
        <div className="panel-title">Split → train → infer → analyze</div>
        <p className="panel-body">
          subset300 train/validation split과 DRBC holdout을 고정한 뒤 paired seed 111/222/444로 Model 1과 Model 2를 비교한다.
          First와 extreme test는 expanded basin 기준으로 재생성해야 한다.
        </p>
        <div className="source-path">configs/ · scripts/model/ · output/model_analysis/</div>
      </article>
    </section>
  );
}
```

Create `foundation-tabs.tsx`:

```tsx
export function FoundationTabs() {
  return (
    <section className="panel-grid">
      <article className="panel research-panel">
        <div className="panel-sub">Dataset</div>
        <div className="panel-title">Input / Result / Analysis data</div>
        <p className="panel-body">
          Input data는 CAMELSH source, forcing, static attributes, target streamflow, screening output이다.
          Result data는 prediction series와 raw metric이고, Analysis data는 chart와 해석을 위해 가공한 derived table이다.
        </p>
        <div className="source-path">basins/ · data/ · output/model_analysis/</div>
      </article>
      <article className="panel research-panel">
        <div className="panel-sub">Model</div>
        <div className="panel-title">LSTM backbone and quantile head</div>
        <p className="panel-body">
          Model page는 dynamic/static input, LSTM hidden state, deterministic output, quantile output,
          pinball loss와 hyperparameter를 설명한다.
        </p>
        <div className="source-path">configs/ · docs/experiment/method/model/</div>
      </article>
      <article className="panel research-panel">
        <div className="panel-sub">Basin</div>
        <div className="panel-title">DRBC and training pool</div>
        <p className="panel-body">
          Basin page는 DRBC holdout, expanded basin universe, non-DRBC training pool, basin attributes,
          hydromod risk를 결과 해석 전에 설명한다.
        </p>
        <div className="source-path">basins/drbc_boundary/ · output/basin/drbc/analysis/</div>
      </article>
    </section>
  );
}
```

Create `analysis-module-index.tsx`:

```tsx
import { FigurePreviewGrid } from "@/components/figure-preview-grid";
import { overviewFigureDeck } from "@/lib/figure-assets";

const modules = [
  ["Main result", "paper figure board와 paired seed table"],
  ["Hydrograph", "기존 HTML gallery 기반 visual inspection"],
  ["Stress test", "historical stress와 false-positive tradeoff"],
  ["Confirmed flood", "NWS flood-stage event audit"],
  ["Event regime", "regime별 effect와 recall"],
  ["Attribute analysis", "basin attribute sorting과 chart"],
  ["Calibration", "coverage, pinball, q99 caveat"],
] as const;

export function AnalysisModuleIndex() {
  return (
    <>
      <FigurePreviewGrid figures={overviewFigureDeck} compact />
      <section className="panel-grid">
        {modules.map(([title, body]) => (
          <article className="panel research-panel" key={title}>
            <div className="panel-sub">Analysis module</div>
            <div className="panel-title">{title}</div>
            <p className="panel-body">{body}</p>
          </article>
        ))}
      </section>
    </>
  );
}
```

Create `reference-map.tsx`:

```tsx
const referenceGroups = [
  ["Experiment", "PUB/PUR split, regional holdout, paired model comparison"],
  ["Dataset", "CAMELS, CAMELSH, hourly forcing, basin attributes"],
  ["Model", "LSTM hydrology, quantile regression, pinball loss"],
  ["Basin", "DRBC hydrology, flood controls, hydromodification"],
  ["Analysis", "flood typing, event regime, stress testing, explainable hydrology"],
] as const;

export function ReferenceMap() {
  return (
    <section className="panel-grid">
      {referenceGroups.map(([title, body]) => (
        <article className="panel research-panel" key={title}>
          <div className="panel-sub">Reference group</div>
          <div className="panel-title">{title}</div>
          <p className="panel-body">{body}</p>
          <div className="source-path">docs/references/</div>
        </article>
      ))}
    </section>
  );
}
```

- [ ] **Step 2: Simplify page.tsx routing to five sections**

In `dashboard/app/[section]/page.tsx`, replace old section conditional block with:

```tsx
{id === "O" && <OverviewSection />}
{id === "E" && <ExperimentSection />}
{id === "F" && <FoundationSection />}
{id === "A" && <AnalysisSection />}
{id === "R" && <ReferenceSection />}
```

Add wrappers:

```tsx
function ExperimentSection() {
  return (
    <>
      <p className="section-lede">
        실험계획은 공식 비교축, split, seed, checkpoint, test matrix, 재현 command를 한 곳에 묶는다.
      </p>
      <WorkflowPanel />
    </>
  );
}

function FoundationSection() {
  return (
    <>
      <p className="section-lede">
        Foundation은 Dataset, Model, Basin을 결과 해석 전에 필요한 실험 기반 설명으로 묶는다.
      </p>
      <FoundationTabs />
    </>
  );
}

function AnalysisSection() {
  return (
    <>
      <p className="section-lede">
        Analysis는 type마다 다른 layout을 허용하되 질문, source, chart/table, 해석, caveat, raw evidence link를 공통 contract로 둔다.
      </p>
      <AnalysisModuleIndex />
    </>
  );
}

function ReferenceSection() {
  return (
    <>
      <p className="section-lede">
        Reference는 선행연구와 관련연구를 dashboard 섹션별로 연결하는 living literature map이다.
      </p>
      <ReferenceMap />
    </>
  );
}
```

- [ ] **Step 3: Update static params**

At the bottom of `page.tsx`, keep:

```tsx
export function generateStaticParams() {
  return Object.values(SECTION_SLUG).map((slug) => ({ section: slug }));
}
```

- [ ] **Step 4: Run typecheck**

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd dashboard
npm run typecheck
```

Expected: top-level page compiles. Detail route may still need old slug migration.

- [ ] **Step 5: Commit**

```bash
git add dashboard/components/workflow-panel.tsx dashboard/components/foundation-tabs.tsx dashboard/components/analysis-module-index.tsx dashboard/components/reference-map.tsx dashboard/app/[section]/page.tsx
git commit -m "feat: add dashboard IA section shells"
```

## Task 5: Migrate Detail Routes Under Analysis

**Files:**
- Modify: `dashboard/app/[section]/[detail]/page.tsx`

- [ ] **Step 1: Replace static params**

Use these params:

```tsx
export function generateStaticParams() {
  return [
    { section: "overview", detail: "status" },
    { section: "overview", detail: "roadmap" },
    { section: "experiment", detail: "workflow" },
    { section: "experiment", detail: "test-matrix" },
    { section: "foundation", detail: "dataset" },
    { section: "foundation", detail: "model" },
    { section: "foundation", detail: "basin" },
    { section: "analysis", detail: "main-result" },
    { section: "analysis", detail: "hydrograph" },
    { section: "analysis", detail: "stress" },
    { section: "analysis", detail: "confirmed-flood" },
    { section: "analysis", detail: "event-regime" },
    { section: "analysis", detail: "attribute" },
    { section: "analysis", detail: "calibration" },
    { section: "reference", detail: "experiment" },
    { section: "reference", detail: "dataset" },
    { section: "reference", detail: "model" },
    { section: "reference", detail: "basin" },
    { section: "reference", detail: "analysis" },
  ];
}
```

- [ ] **Step 2: Add redirect map for old routes**

At the top:

```tsx
import { redirect } from "next/navigation";
```

Before `const id = SLUG_TO_ID[section];`, add:

```tsx
const legacyRedirects: Record<string, string> = {
  "results/q99-exceedance": "/analysis/main-result",
  "results/peak-hour": "/analysis/main-result",
  "results/expanded-first": "/experiment/test-matrix",
  "hydrograph/quantile-zone": "/analysis/hydrograph",
  "stress/cohort": "/analysis/stress",
  "stress/expanded-extreme": "/experiment/test-matrix",
  "stress/checkpoint": "/analysis/stress",
  "model/performance": "/foundation/model",
  "model/nse-delta": "/analysis/main-result",
  "dataset/split": "/foundation/dataset",
};

const legacyTarget = legacyRedirects[`${section}/${detail}`];
if (legacyTarget) redirect(legacyTarget);
```

- [ ] **Step 3: Add minimal content for new detail slugs**

For now, add a `defaultDetail` helper:

```tsx
function simpleDetail(title: string, lede: string, sourcePath: string): DetailContent {
  return {
    title,
    lede,
    sourcePath,
    panels: (
      <section className="panel research-panel">
        <div className="panel-sub">Detail page</div>
        <div className="panel-title">{title}</div>
        <p className="panel-body">{lede}</p>
        <div className="source-path">{sourcePath}</div>
      </section>
    ),
  };
}
```

In `getDetailContent`, include cases for each new route, reusing existing detailed cases where available:

```tsx
case "analysis/main-result":
  return simpleDetail("Main result", "Q99 exceedance와 observed peak hour에서 Model 2 q99가 peak underestimation을 줄였는지 검토한다.", "output/model_analysis/legacy/overall_analysis/main_comparison/");
case "analysis/hydrograph":
  return simpleDetail("Hydrograph", "기존 hydrograph gallery 구조를 dashboard 안으로 가져와 basin/event/predictor별 visual evidence를 본다.", "output/model_analysis/legacy/extreme_rain/primary/observed_q99_hydrograph_gallery_index.html");
case "analysis/stress":
  return simpleDetail("Stress test", "Historical stress는 primary claim이 아니라 benefit과 false-positive tradeoff를 점검하는 보조 분석이다.", "output/model_analysis/legacy/extreme_rain/primary/");
case "analysis/confirmed-flood":
  return simpleDetail("Confirmed flood", "NWS flood-stage confirmed event layer를 기준으로 event audit과 hydrograph evidence를 본다.", "output/model_analysis/confirmed_flood/");
case "analysis/event-regime":
  return simpleDetail("Event regime", "Event regime별 q99 effect, recall, under-deficit reduction을 비교한다.", "output/model_analysis/legacy/paper_result_assets/");
case "analysis/attribute":
  return simpleDetail("Attribute analysis", "Basin attribute별로 model effect와 failure mode를 sorting한다.", "output/model_analysis/legacy/overall_analysis/main_comparison/drbc_attribute_metric_correlations/");
case "analysis/calibration":
  return simpleDetail("Calibration", "Coverage, pinball, q99 caveat를 함께 검토한다.", "output/model_analysis/legacy/probabilistic_diagnostics/");
```

- [ ] **Step 4: Run route checks**

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
for route in /overview/status /experiment/workflow /foundation/dataset /analysis/main-result /analysis/hydrograph /reference/experiment; do
  curl -s -o /dev/null -w "$route %{http_code}\n" "http://localhost:3000$route"
done
```

Expected: every listed route returns `200` after dev server rebuilds.

- [ ] **Step 5: Commit**

```bash
git add dashboard/app/[section]/[detail]/page.tsx
git commit -m "refactor: migrate detail pages to new dashboard IA"
```

## Task 6: Update README and Verify

**Files:**
- Modify: `dashboard/README.md`

- [ ] **Step 1: Update README IA section**

Add this section after the opening paragraph:

```md
## Information Architecture

Top-level sections:

- `O / Overview`: project status, research question, readiness, quick results, next actions
- `E / Experiment`: official comparison, split policy, seed/checkpoint policy, test matrix, workflow
- `F / Foundation`: Dataset, Model, Basin background
- `A / Analysis`: main result, hydrograph, stress, confirmed flood, event regime, attribute, calibration modules
- `R / Reference`: section-tagged literature map

The sub sidebar is a section-local table of contents. It no longer shows fixed `핵심 판독` and `증거 흐름` cards. The main canvas shows one selected subpage or analysis module at a time, except Overview, which summarizes status and roadmap cards on one page.
```

- [ ] **Step 2: Add build caveat**

Add this note under `Run`:

```md
Do not run `npm run build` against the same `.next` directory while the launchd dev server is serving port 3000. Stop the dev server or use a separate verification flow first, otherwise dev chunks can be invalidated and routes can return 500 until `.next` is cleaned and the service restarts.
```

- [ ] **Step 3: Run final checks**

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd dashboard
npm run typecheck
```

Expected: `tsc --noEmit` exits 0.

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
for route in /overview /experiment /foundation /analysis /reference /analysis/main-result /reference/experiment; do
  curl -s -o /dev/null -w "$route %{http_code}\n" "http://localhost:3000$route"
done
```

Expected: every route returns `200`.

- [ ] **Step 4: Commit**

```bash
git add dashboard/README.md
git commit -m "docs: document dashboard IA routes"
```

## Self-Review

Spec coverage:

- Top-level `O/E/F/A/R`: Task 1 and Task 4.
- Sub sidebar as local table of contents: Task 2.
- Main canvas selected page principle: Task 4 and Task 5.
- Overview KPI/status board: Task 3.
- Experiment workflow and test matrix shell: Task 4.
- Foundation Dataset/Model/Basin shell: Task 4.
- Analysis module registry and flexible layouts: Task 4 and Task 5.
- Reference literature map shell: Task 4 and Task 6.
- Metric/source/caveat governance: Task 3 data fields, Task 6 docs, and Task 5 source paths.

Placeholder scan:

- This plan intentionally uses first-pass shell content for new pages, but every shell includes concrete text, source paths, and routes.
- No step contains unresolved placeholders or undefined function names.

Type consistency:

- `SectionId` is consistently `O | E | F | A | R`.
- `DashboardStatus` status strings match sidebar `SidebarEntry.status`.
- Route slugs match `SECTION_SLUG` and `generateStaticParams`.
