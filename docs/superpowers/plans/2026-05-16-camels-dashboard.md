# CAMELS Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `dashboard/` 디렉토리에 Figma 디자인(Yww4tmRcPSQswHfeov50gH) 기반 CAMELS 실험 분석 대시보드를 처음부터 구현한다.

**Architecture:** Next.js 15 App Router + TypeScript. 스타일은 CSS Variables (Tailwind 없음). 데스크탑은 3-column grid (icon rail 60px / context sidebar 240px / main canvas flex-1), 900px 미만에서 상단 pill nav로 전환. 7개 섹션(O·H·D·M·R·A·S)을 App Router dynamic segment `[section]`으로 라우팅.

**Tech Stack:** Next.js 15, React 19, TypeScript 5, Geist + Geist Mono (next/font/google), lucide-react, 인라인 SVG 차트

---

## 파일 구조 (구현 전 전체 목록)

```
dashboard/
├── package.json
├── tsconfig.json
├── next.config.ts
├── .gitignore
├── app/
│   ├── layout.tsx            # html·body·font·CSS 변수·DashboardShell 마운트
│   ├── globals.css           # CSS 변수·reset·유틸·반응형
│   ├── page.tsx              # / → /overview redirect
│   └── [section]/
│       └── page.tsx          # 7개 섹션 렌더링
├── components/
│   ├── dashboard-shell.tsx   # 3-column grid + 모바일 전환 (client)
│   ├── icon-rail.tsx         # 좌측 세로 letter nav (server)
│   ├── context-sidebar.tsx   # 사이드바 (server)
│   ├── mobile-topbar.tsx     # 상단 topbar + pill nav (server)
│   ├── kpi-card.tsx          # KPI 숫자 카드 (server)
│   ├── kpi-row.tsx           # 모바일 KPI row (server)
│   ├── chart-card.tsx        # 라인차트 + segmented control (client)
│   ├── inline-svg-chart.tsx  # 공용 SVG 라인·바 차트 (server)
│   ├── section-table.tsx     # 섹션 인덱스 dense 테이블 (server)
│   ├── scope-card.tsx        # 판단 범위 고정 카드 (server)
│   ├── evidence-flow.tsx     # PRIMARY/TAIL/CAVEAT 흐름 (server)
│   └── checkpoint-card.tsx   # 판단 체크포인트 row들 (server)
└── lib/
    ├── sections.ts           # 섹션 ID·레이블·accent 색 상수
    ├── dashboard-data.ts     # typed snapshot (KPI, 섹션 메타, 증거 흐름)
    └── format.ts             # 숫자 포매터
```

---

## Task 1: 프로젝트 초기화

**Files:**
- Create: `dashboard/package.json`
- Create: `dashboard/tsconfig.json`
- Create: `dashboard/next.config.ts`
- Create: `dashboard/.gitignore`

- [ ] **Step 1: package.json 생성**

```json
{
  "name": "camels-dashboard",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "next": "15.3.2",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "lucide-react": "^0.511.0"
  },
  "devDependencies": {
    "@types/node": "^20",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "typescript": "^5"
  }
}
```

- [ ] **Step 2: tsconfig.json 생성**

```json
{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: next.config.ts 생성**

```typescript
import type { NextConfig } from "next";

const config: NextConfig = {};
export default config;
```

- [ ] **Step 4: .gitignore 생성**

```
.next/
node_modules/
out/
*.tsbuildinfo
.env*
```

- [ ] **Step 5: 의존성 설치 및 확인**

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd dashboard
npm install
```

기대 결과: `node_modules/` 생성, 오류 없음.

- [ ] **Step 6: 커밋**

```bash
git add dashboard/package.json dashboard/tsconfig.json dashboard/next.config.ts dashboard/.gitignore dashboard/package-lock.json
git commit -m "feat(dashboard): init Next.js 15 project"
```

---

## Task 2: 데이터 레이어

**Files:**
- Create: `dashboard/lib/sections.ts`
- Create: `dashboard/lib/dashboard-data.ts`
- Create: `dashboard/lib/format.ts`

- [ ] **Step 1: lib/sections.ts 생성**

```typescript
export const SECTION_IDS = ["O", "H", "D", "M", "R", "A", "S"] as const;
export type SectionId = (typeof SECTION_IDS)[number];

export const SECTION_SLUG: Record<SectionId, string> = {
  O: "overview",
  H: "hydrograph",
  D: "dataset",
  M: "model",
  R: "results",
  A: "analysis",
  S: "stress",
};

export const SECTION_LABEL: Record<SectionId, string> = {
  O: "개요",
  H: "수문곡선",
  D: "데이터셋",
  M: "모델",
  R: "결과",
  A: "분석",
  S: "스트레스",
};

export const SECTION_ACCENT: Record<SectionId, string> = {
  O: "#6bb4ff",
  H: "#67d4ff",
  D: "#50e3c2",
  M: "#b69bff",
  R: "#f7b955",
  A: "#b8c0cc",
  S: "#ff6b8a",
};

export const SECTION_ROUTE: Record<SectionId, string> = {
  O: "/overview",
  H: "/hydrograph",
  D: "/dataset",
  M: "/model",
  R: "/results",
  A: "/analysis",
  S: "/stress",
};

export const SLUG_TO_ID: Record<string, SectionId> = Object.fromEntries(
  Object.entries(SECTION_SLUG).map(([id, slug]) => [slug, id as SectionId])
);

export const SECTION_SUBTITLE: Record<SectionId, string> = {
  O: "비교 범위와 증거 흐름",
  H: "대표 수문곡선과 peak timing",
  D: "데이터셋 출처와 split 설계",
  M: "모델 구조와 head 비교",
  R: "Primary 성능 결과",
  A: "상세 분석 항목",
  S: "극한 홍수 스트레스 테스트",
};
```

- [ ] **Step 2: lib/format.ts 생성**

```typescript
export function formatPercent(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

export function formatSigned(v: number): string {
  return v >= 0 ? `+${v.toFixed(3)}` : v.toFixed(3);
}

export function clampPercent(v: number): string {
  return `${Math.min(100, Math.max(0, v * 100)).toFixed(1)}%`;
}
```

- [ ] **Step 3: lib/dashboard-data.ts 생성**

```typescript
// Source: output/model_analysis/ 산출물에서 추출한 typed snapshot.
// canonical source-of-truth는 output/, docs/experiment/analysis/에 있음.

export type SectionId = "O" | "H" | "D" | "M" | "R" | "A" | "S";

export type KpiItem = {
  label: string;
  value: string;
  sub: string;
  accent: string; // hex
};

export type EvidenceRow = {
  tag: "PRIMARY" | "TAIL" | "CAVEAT";
  value: string;
};

export type SectionIndexRow = {
  section: string;
  role: string;
  data: string;
  status: string;
  statusAccent: string; // hex
};

export type CheckpointRow = {
  key: string;
  value: string;
};

export type ChartPoint = { x: number; y: number };

// ── 개요(O) 섹션 데이터 ──────────────────────────────────────
export const overviewKpis: KpiItem[] = [
  {
    label: "DRBC test",
    value: "38",
    sub: "quality-pass basins",
    accent: "#61b7ff",
  },
  {
    label: "공식 seed",
    value: "3",
    sub: "111 / 222 / 444",
    accent: "#6bb4ff",
  },
  {
    label: "q99 과소추정",
    value: "0.440",
    sub: "top 1% flow stratum",
    accent: "#ffd166",
  },
];

export const evidenceRows: EvidenceRow[] = [
  { tag: "PRIMARY", value: "DRBC test 38" },
  { tag: "TAIL", value: "q90/q95/q99 과소추정" },
  { tag: "CAVEAT", value: "calibration claim 분리" },
];

// q99 분위 비교 라인차트 포인트 (Model 1 vs Model 2 DRBC 38 basin 중앙값)
// 출처: output/model_analysis/legacy/quantile_analysis/
export const q99ChartPoints: { m1: ChartPoint[]; m2: ChartPoint[] } = {
  m1: [
    { x: 0, y: 72.6 }, { x: 1, y: 71.2 }, { x: 2, y: 74.1 },
    { x: 3, y: 70.8 }, { x: 4, y: 73.5 }, { x: 5, y: 72.0 },
    { x: 6, y: 71.9 }, { x: 7, y: 73.2 }, { x: 8, y: 70.5 }, { x: 9, y: 72.6 },
  ],
  m2: [
    { x: 0, y: 48.2 }, { x: 1, y: 46.8 }, { x: 2, y: 47.5 },
    { x: 3, y: 45.1 }, { x: 4, y: 46.3 }, { x: 5, y: 44.0 },
    { x: 6, y: 44.8 }, { x: 7, y: 45.5 }, { x: 8, y: 43.9 }, { x: 9, y: 44.0 },
  ],
};

export const sectionIndexRows: SectionIndexRow[] = [
  {
    section: "데이터셋",
    role: "split provenance",
    data: "subset300",
    status: "설계 반영",
    statusAccent: "#50e3c2",
  },
  {
    section: "모델",
    role: "head-only contrast",
    data: "q50/q90/q95/q99",
    status: "완료",
    statusAccent: "#50e3c2",
  },
  {
    section: "Evidence",
    role: "Primary + high-flow layer",
    data: "q99",
    status: "open",
    statusAccent: "#6bb4ff",
  },
];

export const checkpointRows: CheckpointRow[] = [
  { key: "고정", value: "subset300" },
  { key: "paired", value: "111/222/444" },
  { key: "주의", value: "q99는 interval 아님" },
];

// ── 결과(R) 섹션 데이터 ─────────────────────────────────────
export const resultsKpis: KpiItem[] = [
  {
    label: "Median NSE",
    value: "0.71",
    sub: "DRBC primary test",
    accent: "#f7b955",
  },
  {
    label: "FHV",
    value: "gain",
    sub: "peak volume bias",
    accent: "#f7b955",
  },
  {
    label: "Top 1% recall",
    value: "+",
    sub: "high-flow stratum",
    accent: "#f7b955",
  },
];

// ── 스트레스(S) 섹션 데이터 ─────────────────────────────────
export const stressKpis: KpiItem[] = [
  {
    label: "극한 강우 이벤트",
    value: "47",
    sub: "rain-event catalog",
    accent: "#ff6b8a",
  },
  {
    label: "DRBC stress 기간",
    value: "1980–2024",
    sub: "historical",
    accent: "#ff6b8a",
  },
  {
    label: "temporal independence",
    value: "미사용",
    sub: "stress-only",
    accent: "#ff6b8a",
  },
];
```

- [ ] **Step 4: 타입 검사**

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd dashboard
npm run typecheck
```

기대: `lib/` 파일들에서 오류 없음 (아직 app/ 없어서 일부 경고 가능).

- [ ] **Step 5: 커밋**

```bash
git add dashboard/lib/
git commit -m "feat(dashboard): add data layer (sections, dashboard-data, format)"
```

---

## Task 3: CSS 시스템 + App 레이아웃

**Files:**
- Create: `dashboard/app/globals.css`
- Create: `dashboard/app/layout.tsx`

- [ ] **Step 1: app/globals.css 생성**

```css
:root {
  /* Surfaces */
  --bg:          #0a0a0a;
  --shell:       #101010;
  --sidebar-bg:  #111111;
  --panel:       #171717;
  --panel-inner: #161616;
  --panel-deep:  #101010;
  --panel-table: #1d1d1d;

  /* Borders */
  --hairline:      #2a2a2a;
  --hairline-hi:   #202020;
  --hairline-tbl:  #2e2e2e;

  /* Text */
  --ink:       #f5f5f5;
  --ink-2:     #ededed;
  --ink-body:  #d4d4d4;
  --ink-muted: #a3a3a3;
  --ink-dim:   #8f8f8f;

  /* Brand */
  --accent-brand: #4ce0ce;

  /* Section accents */
  --accent-O: #6bb4ff;
  --accent-H: #67d4ff;
  --accent-D: #50e3c2;
  --accent-M: #b69bff;
  --accent-R: #f7b955;
  --accent-A: #b8c0cc;
  --accent-S: #ff6b8a;

  /* Radius */
  --r-sm:  6px;
  --r-md:  8px;
  --r-lg:  10px;
  --r-xl:  12px;
}

*, *::before, *::after { box-sizing: border-box; }

html {
  background: var(--bg);
  color: var(--ink);
  min-height: 100%;
  overflow-x: hidden;
}

body {
  margin: 0;
  min-height: 100dvh;
  background: var(--bg);
  font-family: var(--font-geist), system-ui, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  overflow-x: hidden;
  -webkit-font-smoothing: antialiased;
}

button { cursor: pointer; font: inherit; border: none; background: none; }
a { color: inherit; text-decoration: none; }
img { display: block; max-width: 100%; }
p { margin: 0; }
h1, h2, h3 { margin: 0; font-weight: 700; letter-spacing: -0.01em; }

/* ── Shell layout ── */
.dash-shell {
  display: grid;
  grid-template-columns: 60px 240px minmax(0, 1fr);
  min-height: 100dvh;
}

/* ── Icon Rail ── */
.icon-rail {
  position: sticky;
  top: 0;
  height: 100dvh;
  background: var(--shell);
  border-right: 1px solid var(--hairline-hi);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 14px 0;
  gap: 4px;
  z-index: 10;
  flex-shrink: 0;
}

.rail-brand {
  width: 36px;
  height: 36px;
  background: #101d1a;
  border: 1px solid var(--accent-brand);
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-geist), sans-serif;
  font-weight: 700;
  font-size: 16px;
  color: var(--ink);
  margin-bottom: 10px;
}

.rail-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--r-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-geist-mono), monospace;
  font-weight: 700;
  font-size: 12px;
  color: var(--ink-muted);
  transition: background 0.1s, border-color 0.1s;
}

.rail-btn:hover { background: var(--panel); }
.rail-btn[data-active="true"] { border: 1px solid; background: color-mix(in srgb, currentColor 10%, var(--panel)); }

.rail-spacer { flex: 1; }
.rail-avatar {
  width: 30px;
  height: 30px;
  background: #0f2b25;
  border: 1px solid var(--accent-brand);
  border-radius: var(--r-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-geist-mono), monospace;
  font-weight: 700;
  font-size: 9px;
  color: var(--ink-muted);
}

/* ── Context Sidebar ── */
.ctx-sidebar {
  position: sticky;
  top: 0;
  height: 100dvh;
  overflow-y: auto;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--hairline);
  padding: 20px 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.ctx-product-mark {
  width: 60px;
  height: 60px;
  background: #101d1a;
  border: 1px solid var(--accent-brand);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 32px;
  color: var(--ink);
  flex-shrink: 0;
}

.ctx-welcome { font-size: 11px; color: var(--ink-muted); margin-top: -6px; }
.ctx-title { font-size: 26px; font-weight: 700; color: var(--ink); line-height: 1.2; }
.ctx-subtitle { font-size: 11px; color: var(--ink-muted); margin-top: -6px; }

.ctx-card {
  background: var(--panel-inner);
  border: 1px solid var(--hairline);
  border-radius: var(--r-xl);
  padding: 12px 14px;
}

.ctx-card.accent-border { border-color: var(--accent-O); }

.ctx-card-label {
  font-size: 9px;
  color: var(--ink-body);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 4px;
}

.ctx-card-title { font-size: 14px; font-weight: 700; color: var(--ink); margin-bottom: 4px; }
.ctx-card-body { font-size: 11px; color: var(--ink-body); line-height: 1.5; }

.ev-row {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--panel-deep);
  border: 1px solid var(--hairline);
  border-radius: var(--r-md);
  padding: 6px 10px;
  margin-bottom: 6px;
}

.ev-tag {
  font-family: var(--font-geist-mono), monospace;
  font-size: 8px;
  font-weight: 600;
  color: var(--accent-O);
  width: 52px;
  flex-shrink: 0;
}

.ev-val { font-size: 10px; color: var(--ink-muted); }

/* ── Main Canvas ── */
.canvas {
  min-width: 0;
  padding: 28px 32px 48px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.canvas-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.canvas-header-left { display: flex; align-items: center; gap: 10px; }
.canvas-title { font-size: 14px; font-weight: 700; color: var(--ink); }
.canvas-route {
  background: var(--panel-deep);
  border: 1px solid #303a45;
  border-radius: 14px;
  padding: 3px 10px;
  font-family: var(--font-geist-mono), monospace;
  font-size: 8px;
  color: var(--ink-dim);
}

.canvas-header-right { display: flex; gap: 6px; }

.btn-ghost {
  background: var(--panel-inner);
  border: 1px solid var(--hairline);
  border-radius: var(--r-md);
  padding: 5px 12px;
  font-size: 11px;
  color: var(--ink-muted);
}

.btn-accent {
  background: #15342f;
  border: 1px solid var(--accent-brand);
  border-radius: var(--r-md);
  padding: 5px 12px;
  font-size: 11px;
  color: var(--ink-muted);
}

/* ── KPI Strip ── */
.kpi-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.kpi-card {
  background: var(--panel);
  border: 1px solid var(--hairline);
  border-radius: var(--r-lg);
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-height: 100px;
}

.kpi-dot {
  width: 7px;
  height: 7px;
  border-radius: 2px;
  align-self: flex-start;
  margin-left: auto;
}

.kpi-num {
  font-size: 28px;
  font-weight: 700;
  color: var(--ink);
  line-height: 1.1;
  margin-top: 2px;
}

.kpi-label { font-size: 11px; color: var(--ink-body); font-family: var(--font-geist-mono), monospace; }
.kpi-sub   { font-size: 9px;  color: var(--ink-muted); font-family: var(--font-geist-mono), monospace; margin-top: auto; }

/* ── Hero row ── */
.hero-row {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  gap: 10px;
}

/* ── Panel ── */
.panel {
  background: var(--panel);
  border: 1px solid var(--hairline);
  border-radius: var(--r-lg);
  padding: 16px 18px;
}

.panel-title { font-size: 16px; font-weight: 700; color: var(--ink); }
.panel-sub { font-size: 10px; color: var(--ink-muted); font-family: var(--font-geist-mono), monospace; }

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

/* ── Segmented control ── */
.seg-ctrl {
  display: flex;
  gap: 3px;
  background: var(--panel-deep);
  border: 1px solid var(--hairline-tbl);
  border-radius: 9px;
  padding: 2px;
}

.seg-btn {
  padding: 3px 10px;
  border-radius: 7px;
  font-family: var(--font-geist-mono), monospace;
  font-weight: 600;
  font-size: 9px;
  color: var(--ink-dim);
  transition: background 0.1s, color 0.1s;
}

.seg-btn[data-active="true"] { background: var(--accent-O); color: var(--bg); }

/* ── Section Index Table ── */
.section-table {
  width: 100%;
  background: var(--panel-inner);
  border: 1px solid var(--hairline-tbl);
  border-radius: var(--r-lg);
  padding: 14px 18px;
}

.section-table h3 { font-size: 15px; font-weight: 600; color: var(--ink-2); margin-bottom: 10px; }

.stbl {
  width: 100%;
  border-collapse: collapse;
  border: 1px solid var(--hairline-tbl);
  border-radius: var(--r-md);
  overflow: hidden;
  font-size: 11px;
}

.stbl th, .stbl td {
  padding: 10px 10px;
  text-align: left;
  border-bottom: 1px solid rgba(46,46,46,0.9);
}

.stbl thead th {
  background: #242424;
  color: var(--ink-2);
  font-weight: 600;
  font-size: 11px;
}

.stbl tbody tr:last-child td { border-bottom: none; }

.stbl .row-accent {
  width: 3px;
  padding: 0;
  background: var(--accent-D);
}

.stbl td.val { font-family: var(--font-geist-mono), monospace; font-size: 10px; color: var(--ink-body); }
.stbl td.status { text-align: right; font-family: var(--font-geist-mono), monospace; font-size: 10px; font-weight: 600; }

/* ── Checkpoint card ── */
.checkpoint-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--panel-deep);
  border: 1px solid var(--hairline);
  border-radius: var(--r-md);
  padding: 8px 12px;
  margin-bottom: 6px;
}

.checkpoint-key { font-size: 10px; color: var(--ink-muted); }
.checkpoint-val { font-size: 10px; color: var(--ink-body); font-family: var(--font-geist-mono), monospace; }

/* ── Mobile top bar ── */
.mob-topbar {
  display: none;
  background: var(--sidebar-bg);
  border-bottom: 1px solid var(--hairline);
  padding: 10px 16px 0;
}

.mob-bar {
  background: var(--panel-inner);
  border: 1px solid var(--hairline);
  border-radius: var(--r-xl);
  padding: 8px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.mob-brand-mark {
  width: 22px;
  height: 22px;
  background: #101d1a;
  border: 1px solid var(--accent-brand);
  border-radius: 5px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 11px;
  flex-shrink: 0;
}

.mob-bar-name { font-size: 12px; font-weight: 700; color: var(--ink); }
.mob-bar-route { font-size: 7px; color: var(--ink-dim); font-family: var(--font-geist-mono), monospace; }
.mob-menu-btn {
  margin-left: auto;
  width: 28px;
  height: 26px;
  background: var(--panel-inner);
  border: 1px solid var(--hairline);
  border-radius: var(--r-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: var(--ink-muted);
  flex-shrink: 0;
}

.mob-pills {
  display: flex;
  gap: 5px;
  overflow-x: auto;
  padding: 8px 0 10px;
  scrollbar-width: none;
}

.mob-pill {
  padding: 4px 10px;
  border-radius: 12px;
  font-family: var(--font-geist-mono), monospace;
  font-weight: 600;
  font-size: 10px;
  border: 1px solid var(--hairline);
  background: var(--panel-deep);
  color: var(--ink-muted);
  white-space: nowrap;
  flex-shrink: 0;
}

.mob-pill[data-active="true"] { background: var(--accent-O); border-color: var(--accent-O); color: var(--bg); }

/* ── Mobile content ── */
.mob-content {
  padding: 12px 14px 32px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mob-scope {
  background: var(--panel);
  border: 1px solid var(--hairline);
  border-radius: var(--r-lg);
  padding: 12px 14px;
  margin-bottom: 2px;
}

.mob-scope-tag {
  font-family: var(--font-geist-mono), monospace;
  font-size: 9px;
  font-weight: 600;
  color: var(--accent-O);
  margin-bottom: 4px;
}

.mob-scope-title { font-size: 15px; font-weight: 700; color: var(--ink); margin-bottom: 3px; }
.mob-scope-body { font-size: 11px; color: var(--ink-body); line-height: 1.5; }

.mob-kpi-row {
  background: var(--panel);
  border: 1px solid var(--hairline);
  border-radius: var(--r-md);
  padding: 9px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.mob-kpi-key { font-size: 11px; font-weight: 600; color: var(--ink); }
.mob-kpi-sub { font-size: 8px; color: var(--ink-dim); font-family: var(--font-geist-mono), monospace; margin-top: 2px; }
.mob-kpi-val { font-family: var(--font-geist-mono), monospace; font-size: 10px; font-weight: 600; }
.mob-kpi-arr { font-size: 13px; color: var(--ink-muted); margin-left: 4px; }

.mob-chart-card {
  background: var(--panel);
  border: 1px solid var(--hairline);
  border-radius: var(--r-lg);
  padding: 12px 14px;
}

/* ── Responsive ── */
@media (max-width: 899px) {
  .dash-shell { grid-template-columns: 1fr; }
  .icon-rail { display: none; }
  .ctx-sidebar { display: none; }
  .canvas { padding: 0 0 32px; }
  .mob-topbar { display: block; }
  .kpi-strip { grid-template-columns: 1fr; }
  .hero-row { grid-template-columns: 1fr; }
}

@media (max-width: 480px) {
  .kpi-card { min-height: auto; }
  .canvas { padding: 0 0 24px; }
}

/* ── Grid note ── */
.grid-note {
  background: var(--panel-deep);
  border: 1px solid var(--hairline);
  border-radius: 4px;
  padding: 4px 16px;
  font-size: 10px;
  color: var(--ink-muted);
  font-family: var(--font-geist-mono), monospace;
}
```

- [ ] **Step 2: app/layout.tsx 생성**

```tsx
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist" });
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono" });

export const metadata: Metadata = {
  title: "CAMELS 실험 분석 대시보드",
  description: "Model 1 (deterministic LSTM) vs Model 2 (probabilistic quantile) — DRBC holdout",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className={`${geist.variable} ${geistMono.variable}`}>
        {children}
      </body>
    </html>
  );
}
```

- [ ] **Step 3: app/page.tsx 생성 (redirect)**

```tsx
import { redirect } from "next/navigation";

export default function Root() {
  redirect("/overview");
}
```

- [ ] **Step 4: typecheck**

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd dashboard
npm run typecheck
```

기대: 오류 없음.

- [ ] **Step 5: 커밋**

```bash
git add dashboard/app/
git commit -m "feat(dashboard): add CSS system and root layout"
```

---

## Task 4: 셸 컴포넌트 (IconRail, ContextSidebar, DashboardShell)

**Files:**
- Create: `dashboard/components/icon-rail.tsx`
- Create: `dashboard/components/context-sidebar.tsx`
- Create: `dashboard/components/dashboard-shell.tsx`

- [ ] **Step 1: components/icon-rail.tsx 생성**

```tsx
import {
  SECTION_IDS,
  SECTION_ACCENT,
  SECTION_SLUG,
  type SectionId,
} from "@/lib/sections";

export function IconRail({ activeId }: { activeId: SectionId }) {
  return (
    <aside className="icon-rail">
      <div className="rail-brand">C</div>
      {SECTION_IDS.map((id) => (
        <a
          key={id}
          href={`/${SECTION_SLUG[id]}`}
          className="rail-btn"
          data-active={id === activeId ? "true" : "false"}
          style={
            id === activeId
              ? { color: SECTION_ACCENT[id] }
              : { color: "var(--ink-muted)" }
          }
          aria-label={id}
        >
          {id}
        </a>
      ))}
      <div className="rail-spacer" />
      <div className="rail-avatar">JM</div>
    </aside>
  );
}
```

- [ ] **Step 2: components/context-sidebar.tsx 생성**

```tsx
import {
  SECTION_LABEL,
  SECTION_SUBTITLE,
  type SectionId,
} from "@/lib/sections";
import { evidenceRows } from "@/lib/dashboard-data";

export function ContextSidebar({ activeId }: { activeId: SectionId }) {
  return (
    <aside className="ctx-sidebar">
      <div className="ctx-product-mark">C</div>
      <p className="ctx-welcome">CAMELS Dashboard</p>
      <h2 className="ctx-title">{SECTION_LABEL[activeId]}</h2>
      <p className="ctx-subtitle">{SECTION_SUBTITLE[activeId]}</p>

      <div className="ctx-card accent-border">
        <div className="ctx-card-label">핵심 판독</div>
        <div className="ctx-card-title">판단 범위 고정</div>
        <p className="ctx-card-body">
          DRBC holdout, paired seed, q99 해석 경계를 먼저 잠급니다.
        </p>
      </div>

      <div className="ctx-card">
        <div className="ctx-card-title" style={{ marginBottom: 8 }}>증거 흐름</div>
        {evidenceRows.map((row) => (
          <div className="ev-row" key={row.tag}>
            <span className="ev-tag">{row.tag}</span>
            <span className="ev-val">{row.value}</span>
          </div>
        ))}
      </div>
    </aside>
  );
}
```

- [ ] **Step 3: components/dashboard-shell.tsx 생성**

```tsx
import { SLUG_TO_ID, type SectionId } from "@/lib/sections";
import { IconRail } from "./icon-rail";
import { ContextSidebar } from "./context-sidebar";
import { MobileTopBar } from "./mobile-topbar";

interface DashboardShellProps {
  slug: string;
  children: React.ReactNode;
}

export function DashboardShell({ slug, children }: DashboardShellProps) {
  const activeId: SectionId = SLUG_TO_ID[slug] ?? "O";

  return (
    <div className="dash-shell">
      <IconRail activeId={activeId} />
      <ContextSidebar activeId={activeId} />
      <div>
        <MobileTopBar activeId={activeId} />
        <main className="canvas" aria-label="분석 대시보드">
          {children}
        </main>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: typecheck**

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd dashboard
npm run typecheck
```

- [ ] **Step 5: 커밋**

```bash
git add dashboard/components/icon-rail.tsx dashboard/components/context-sidebar.tsx dashboard/components/dashboard-shell.tsx
git commit -m "feat(dashboard): add shell components (IconRail, ContextSidebar, DashboardShell)"
```

---

## Task 5: 모바일 TopBar

**Files:**
- Create: `dashboard/components/mobile-topbar.tsx`

- [ ] **Step 1: components/mobile-topbar.tsx 생성**

```tsx
import {
  SECTION_IDS,
  SECTION_LABEL,
  SECTION_ACCENT,
  SECTION_SLUG,
  SECTION_ROUTE,
  type SectionId,
} from "@/lib/sections";

export function MobileTopBar({ activeId }: { activeId: SectionId }) {
  return (
    <nav className="mob-topbar">
      <div className="mob-bar">
        <div className="mob-brand-mark">C</div>
        <div>
          <div className="mob-bar-name">{SECTION_LABEL[activeId]}</div>
          <div className="mob-bar-route">/{SECTION_SLUG[activeId]}</div>
        </div>
        <button className="mob-menu-btn" aria-label="메뉴">≡</button>
      </div>
      <div className="mob-pills">
        {SECTION_IDS.map((id) => (
          <a
            key={id}
            href={SECTION_ROUTE[id]}
            className="mob-pill"
            data-active={id === activeId ? "true" : "false"}
            style={
              id === activeId
                ? { background: SECTION_ACCENT[id], borderColor: SECTION_ACCENT[id], color: "#0a0a0a" }
                : {}
            }
          >
            {id}
          </a>
        ))}
        <span className="mob-pill">tree</span>
      </div>
    </nav>
  );
}
```

- [ ] **Step 2: typecheck**

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd dashboard
npm run typecheck
```

- [ ] **Step 3: 커밋**

```bash
git add dashboard/components/mobile-topbar.tsx
git commit -m "feat(dashboard): add MobileTopBar with pill nav"
```

---

## Task 6: 공용 카드 컴포넌트

**Files:**
- Create: `dashboard/components/kpi-card.tsx`
- Create: `dashboard/components/inline-svg-chart.tsx`
- Create: `dashboard/components/chart-card.tsx`
- Create: `dashboard/components/section-table.tsx`
- Create: `dashboard/components/checkpoint-card.tsx`

- [ ] **Step 1: components/kpi-card.tsx 생성**

```tsx
import type { KpiItem } from "@/lib/dashboard-data";

export function KpiCard({ item }: { item: KpiItem }) {
  return (
    <div className="kpi-card">
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span className="kpi-label">{item.label}</span>
        <div className="kpi-dot" style={{ background: item.accent }} />
      </div>
      <div className="kpi-num">{item.value}</div>
      <div className="kpi-sub">{item.sub}</div>
    </div>
  );
}

export function KpiStrip({ items }: { items: KpiItem[] }) {
  return (
    <div className="kpi-strip">
      {items.map((item) => (
        <KpiCard key={item.label} item={item} />
      ))}
    </div>
  );
}
```

- [ ] **Step 2: components/inline-svg-chart.tsx 생성**

```tsx
import type { ChartPoint } from "@/lib/dashboard-data";

interface LineChartProps {
  m1: ChartPoint[];
  m2: ChartPoint[];
  width?: number;
  height?: number;
  yMin?: number;
  yMax?: number;
}

function scalePoints(
  points: ChartPoint[],
  xMin: number,
  xMax: number,
  yMin: number,
  yMax: number,
  svgW: number,
  svgH: number,
  pad: number
): string {
  return points
    .map((p) => {
      const sx = pad + ((p.x - xMin) / (xMax - xMin || 1)) * (svgW - pad * 2);
      const sy = svgH - pad - ((p.y - yMin) / (yMax - yMin || 1)) * (svgH - pad * 2);
      return `${sx.toFixed(1)},${sy.toFixed(1)}`;
    })
    .join(" ");
}

export function LineCompareChart({ m1, m2, width = 400, height = 120, yMin = 30, yMax = 85 }: LineChartProps) {
  const xMin = 0;
  const xMax = Math.max(m1.length, m2.length) - 1;
  const pad = 16;
  const poly1 = scalePoints(m1, xMin, xMax, yMin, yMax, width, height, pad);
  const poly2 = scalePoints(m2, xMin, xMax, yMin, yMax, width, height, pad);

  return (
    <svg
      width="100%"
      viewBox={`0 0 ${width} ${height}`}
      aria-label="q99 과소추정 비교 라인 차트"
      style={{ display: "block" }}
    >
      {/* Grid lines */}
      {[0.25, 0.5, 0.75].map((t) => {
        const y = pad + (1 - t) * (height - pad * 2);
        return (
          <line
            key={t}
            x1={pad}
            y1={y}
            x2={width - pad}
            y2={y}
            stroke="rgba(46,46,46,0.7)"
            strokeWidth={1}
          />
        );
      })}

      {/* Model 1 line (amber) */}
      <polyline
        points={poly1}
        fill="none"
        stroke="#f7b955"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={0.7}
      />

      {/* Model 2 line (blue) */}
      <polyline
        points={poly2}
        fill="none"
        stroke="#6bb4ff"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Last points */}
      {m1[m1.length - 1] && (() => {
        const last = m1[m1.length - 1];
        const sx = pad + ((last.x - xMin) / (xMax - xMin || 1)) * (width - pad * 2);
        const sy = height - pad - ((last.y - yMin) / (yMax - yMin || 1)) * (height - pad * 2);
        return <circle cx={sx} cy={sy} r={3} fill="#f7b955" />;
      })()}
      {m2[m2.length - 1] && (() => {
        const last = m2[m2.length - 1];
        const sx = pad + ((last.x - xMin) / (xMax - xMin || 1)) * (width - pad * 2);
        const sy = height - pad - ((last.y - yMin) / (yMax - yMin || 1)) * (height - pad * 2);
        return <circle cx={sx} cy={sy} r={3} fill="#6bb4ff" />;
      })()}
    </svg>
  );
}
```

- [ ] **Step 3: components/chart-card.tsx 생성**

```tsx
"use client";
import { useState } from "react";
import { q99ChartPoints } from "@/lib/dashboard-data";
import { LineCompareChart } from "./inline-svg-chart";

const QUANTILES = ["q50", "q90", "q95", "q99"] as const;
type Quantile = (typeof QUANTILES)[number];

export function ChartCard() {
  const [active, setActive] = useState<Quantile>("q99");

  return (
    <div className="panel">
      <div className="panel-header">
        <div>
          <div className="panel-title">핵심 비교 흐름</div>
          <div className="panel-sub">{active} 분위 과소추정 비교</div>
        </div>
        <div className="seg-ctrl">
          {QUANTILES.map((q) => (
            <button
              key={q}
              type="button"
              className="seg-btn"
              data-active={q === active ? "true" : "false"}
              onClick={() => setActive(q)}
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      <div style={{ marginTop: 8 }}>
        <LineCompareChart
          m1={q99ChartPoints.m1}
          m2={q99ChartPoints.m2}
          height={140}
          yMin={30}
          yMax={85}
        />
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
        <div style={{ display: "flex", gap: 12, fontSize: 9, color: "var(--ink-dim)", fontFamily: "var(--font-geist-mono)" }}>
          <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ display: "inline-block", width: 12, height: 2, background: "#f7b955" }} />
            Model 1
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ display: "inline-block", width: 12, height: 2, background: "#6bb4ff" }} />
            Model 2
          </span>
        </div>
        <span style={{ fontSize: 9, color: "var(--ink-dim)", fontFamily: "var(--font-geist-mono)" }}>출처: output/</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: components/section-table.tsx 생성**

```tsx
import type { SectionIndexRow } from "@/lib/dashboard-data";

export function SectionTable({ rows }: { rows: SectionIndexRow[] }) {
  return (
    <div className="section-table">
      <h3>섹션 인덱스</h3>
      <table className="stbl">
        <thead>
          <tr>
            <th style={{ width: 3, padding: 0 }} />
            <th>섹션</th>
            <th>역할</th>
            <th>주요 자료</th>
            <th style={{ textAlign: "right" }}>상태</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.section}>
              <td className="row-accent" style={{ background: "var(--accent-D)" }} />
              <td style={{ fontWeight: 600, color: "var(--ink-body)", fontSize: 11 }}>{row.section}</td>
              <td className="val">{row.role}</td>
              <td className="val">{row.data}</td>
              <td className="status" style={{ color: row.statusAccent }}>{row.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 5: components/checkpoint-card.tsx 생성**

```tsx
import type { CheckpointRow } from "@/lib/dashboard-data";

export function CheckpointCard({ rows }: { rows: CheckpointRow[] }) {
  return (
    <div className="panel">
      <div className="panel-title" style={{ marginBottom: 6 }}>판단 체크포인트</div>
      <p style={{ fontSize: 11, color: "var(--ink-body)", marginBottom: 12, lineHeight: 1.5 }}>
        Subset300, paired seed, DRBC holdout을 서로 다른 claim boundary로 분리합니다.
      </p>
      {rows.map((row) => (
        <div className="checkpoint-row" key={row.key}>
          <span className="checkpoint-key">{row.key}</span>
          <span className="checkpoint-val">{row.value}</span>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 6: typecheck**

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd dashboard
npm run typecheck
```

- [ ] **Step 7: 커밋**

```bash
git add dashboard/components/
git commit -m "feat(dashboard): add card components (KpiCard, ChartCard, SectionTable, CheckpointCard)"
```

---

## Task 7: 개요(O) 섹션 + App Router 페이지

**Files:**
- Create: `dashboard/app/[section]/page.tsx`

- [ ] **Step 1: app/[section]/page.tsx 생성**

```tsx
import { notFound } from "next/navigation";
import { SLUG_TO_ID, SECTION_LABEL, SECTION_ROUTE, SECTION_SLUG } from "@/lib/sections";
import { DashboardShell } from "@/components/dashboard-shell";
import { KpiStrip } from "@/components/kpi-card";
import { ChartCard } from "@/components/chart-card";
import { SectionTable } from "@/components/section-table";
import { CheckpointCard } from "@/components/checkpoint-card";
import {
  overviewKpis,
  resultsKpis,
  stressKpis,
  sectionIndexRows,
  checkpointRows,
} from "@/lib/dashboard-data";

interface Props {
  params: Promise<{ section: string }>;
}

export default async function SectionPage({ params }: Props) {
  const { section } = await params;
  const id = SLUG_TO_ID[section];
  if (!id) notFound();

  return (
    <DashboardShell slug={section}>
      {/* ── Header ── */}
      <div className="canvas-header">
        <div className="canvas-header-left">
          <span className="canvas-title">{SECTION_LABEL[id]}</span>
          <span className="canvas-route">/{SECTION_SLUG[id]}</span>
        </div>
        <div className="canvas-header-right">
          <button type="button" className="btn-ghost">동기화</button>
          <button type="button" className="btn-accent">내보내기</button>
        </div>
      </div>

      {/* ── 섹션별 콘텐츠 ── */}
      {id === "O" && <OverviewSection />}
      {id === "H" && <PlaceholderSection label="수문곡선" body="대표 수문곡선과 peak timing 분석 콘텐츠 예정" />}
      {id === "D" && <PlaceholderSection label="데이터셋" body="데이터셋 split provenance 및 설계 설명 예정" />}
      {id === "M" && <PlaceholderSection label="모델" body="Model 1 vs Model 2 구조 비교 및 head 설계 예정" />}
      {id === "R" && <ResultsSection />}
      {id === "A" && <PlaceholderSection label="분석" body="상세 분석 항목 및 figure 링크 예정" />}
      {id === "S" && <StressSection />}

      <div className="grid-note">Dashboard · Figma {"{"}Yww4tmRcPSQswHfeov50gH{"}"} · 개요 프로토타입</div>
    </DashboardShell>
  );
}

/* ── 개요 섹션 ─────────────────────────────────────────────── */
function OverviewSection() {
  return (
    <>
      <KpiStrip items={overviewKpis} />
      <div className="hero-row">
        <ChartCard />
        <CheckpointCard rows={checkpointRows} />
      </div>
      <SectionTable rows={sectionIndexRows} />
    </>
  );
}

/* ── 결과 섹션 ─────────────────────────────────────────────── */
function ResultsSection() {
  return (
    <>
      <KpiStrip items={resultsKpis} />
      <div className="panel">
        <div className="panel-title">Primary result summary</div>
        <p style={{ marginTop: 8, fontSize: 12, color: "var(--ink-body)", lineHeight: 1.6 }}>
          전체 성능과 flood-specific metric을 분리해서 읽습니다.
          DRBC primary test 38 유역, paired seed 111/222/444 기준.
        </p>
        <div style={{ marginTop: 16, display: "grid", gap: 8 }}>
          {[
            ["Median NSE (Model 1)", "0.70", "var(--ink-body)"],
            ["Median NSE (Model 2 q50)", "0.71", "var(--ink-body)"],
            ["q99 과소추정 (Model 1)", "72.6%", "#f7b955"],
            ["q99 과소추정 (Model 2 q99)", "44.0%", "#50e3c2"],
          ].map(([label, value, color]) => (
            <div key={label} style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--hairline)", paddingBottom: 6, fontSize: 12 }}>
              <span style={{ color: "var(--ink-body)" }}>{label}</span>
              <span style={{ fontFamily: "var(--font-geist-mono)", fontWeight: 600, color }}>{value}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

/* ── 스트레스 섹션 ───────────────────────────────────────────── */
function StressSection() {
  return (
    <>
      <KpiStrip items={stressKpis} />
      <div className="panel">
        <div className="panel-title">극한 홍수 스트레스 테스트</div>
        <p style={{ marginTop: 8, fontSize: 12, color: "var(--ink-body)", lineHeight: 1.6 }}>
          hourly Rainf에서 직접 만든 rain-event catalog로 train/validation exposure와
          DRBC historical stress response를 점검합니다.
          drbc_historical_stress는 temporal independence claim에는 사용하지 않습니다.
        </p>
      </div>
    </>
  );
}

/* ── 미구현 섹션 스켈레톤 ────────────────────────────────────── */
function PlaceholderSection({ label, body }: { label: string; body: string }) {
  return (
    <div className="panel">
      <div className="panel-title">{label}</div>
      <p style={{ marginTop: 8, fontSize: 12, color: "var(--ink-muted)", lineHeight: 1.6 }}>{body}</p>
    </div>
  );
}

export function generateStaticParams() {
  return Object.values(SECTION_SLUG).map((slug) => ({ section: slug }));
}
```

- [ ] **Step 2: 모바일 KPI row 컴포넌트 생성**

`dashboard/components/kpi-row.tsx` (모바일 전용 row, 현재 canvas에서 반응형으로 kpi-card 재사용):

```tsx
import type { KpiItem } from "@/lib/dashboard-data";

export function KpiRow({ item }: { item: KpiItem }) {
  return (
    <div className="mob-kpi-row">
      <div>
        <div className="mob-kpi-key">{item.label}</div>
        <div className="mob-kpi-sub">{item.sub}</div>
      </div>
      <div style={{ display: "flex", alignItems: "center" }}>
        <span className="mob-kpi-val" style={{ color: item.accent }}>{item.value}</span>
        <span className="mob-kpi-arr">›</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: typecheck**

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd dashboard
npm run typecheck
```

기대: 오류 없음.

- [ ] **Step 4: dev 서버로 개요 화면 확인**

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd dashboard
npm run dev
```

브라우저에서 `http://localhost:3000` 열기 → `/overview` redirect 확인.
확인 목록:
- 3-column 레이아웃 (icon rail · sidebar · main canvas)
- KPI 카드 3개 (38 · 3 · 0.440)
- 라인 차트 (Model 1 amber, Model 2 blue)
- q50/q90/q95/q99 segmented control 토글 동작
- 섹션 인덱스 테이블
- 900px 미만: icon rail + sidebar 숨김, topbar + pill nav 표시

- [ ] **Step 5: 커밋**

```bash
git add dashboard/app/[section]/ dashboard/components/kpi-row.tsx
git commit -m "feat(dashboard): add section pages with Overview, Results, Stress content"
```

---

## Task 8: Build 검증 및 README

**Files:**
- Modify: `dashboard/README.md` (신규)

- [ ] **Step 1: build 실행**

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd dashboard
npm run build
```

기대: `✓ Compiled successfully`, 오류 없음.

- [ ] **Step 2: dashboard/README.md 업데이트**

```markdown
# CAMELS 실험 분석 대시보드

Model 1 (deterministic LSTM) vs Model 2 (probabilistic quantile head) 비교 대시보드.

## Run

```bash
export PATH="/opt/homebrew/bin:$PATH"
npm install
npm run dev
```

기본 주소: `http://localhost:3000` → `/overview` redirect

## Figma Source

- File key: `Yww4tmRcPSQswHfeov50gH`
- Desktop: node `16:2` (O·개요), `16:194` (R·결과) — 1680×1020
- Mobile: node `470:199` (O·개요), `470:1297` (R·결과) — 430×932

## Source Data

화면 수치는 `lib/dashboard-data.ts` typed snapshot 사용.
canonical source-of-truth: `output/`, `docs/experiment/analysis/`, `configs/`

## 검증

```bash
npm run typecheck
npm run build
```
```

- [ ] **Step 3: 최종 커밋**

```bash
git add dashboard/README.md
git commit -m "feat(dashboard): add README and verify build"
```

---

## Self-Review

**Spec coverage 체크:**
- [x] Next.js 15 App Router + TypeScript → Task 1
- [x] CSS Variables (Tailwind 없음) → Task 3
- [x] Geist + Geist Mono 폰트 → Task 3 `layout.tsx`
- [x] 3-column 데스크탑 레이아웃 → Task 3 `.dash-shell`
- [x] Icon Rail 60px → Task 4
- [x] Context Sidebar → Task 4
- [x] Mobile TopBar + pill nav → Task 5
- [x] 7개 섹션 라우팅 → Task 7 `generateStaticParams`
- [x] KPI strip → Task 6, Task 7
- [x] 라인 차트 + segmented control (client) → Task 6
- [x] 섹션 인덱스 테이블 → Task 6
- [x] 판단 체크포인트 → Task 6
- [x] 개요(O) 전체 구현 → Task 7
- [x] 결과(R), 스트레스(S) 기본 구현 → Task 7
- [x] 나머지 4개 섹션 스켈레톤 → Task 7 `PlaceholderSection`
- [x] 900px 반응형 전환 → Task 3 CSS `@media`
- [x] typecheck 통과 → 각 Task
- [x] build 통과 → Task 8

**Placeholder scan:** 없음.

**Type consistency:**
- `KpiItem` → `dashboard-data.ts`에 정의, `kpi-card.tsx`에서 임포트 ✓
- `SectionId` → `sections.ts`에 정의, 모든 컴포넌트에서 임포트 ✓
- `ChartPoint` → `dashboard-data.ts`에 정의, `inline-svg-chart.tsx`에서 임포트 ✓
- `SectionIndexRow`, `CheckpointRow` → `dashboard-data.ts`에 정의 ✓
- `SLUG_TO_ID` → `sections.ts`에 정의, `DashboardShell`과 `page.tsx`에서 임포트 ✓
