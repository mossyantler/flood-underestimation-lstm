# CAMELS 실험 분석 대시보드 설계 스펙

**날짜**: 2026-05-16  
**Figma**: `Yww4tmRcPSQswHfeov50gH` (dashboard node `11:29`, mobile node `470:2`)  
**구현 경로**: `dashboard/` (Next.js App Router, TypeScript, CSS Variables)  
**방식**: B — Figma 디자인 기반 처음부터 구현

---

## 1. 목적

DRBC holdout에서 Model 1 (deterministic LSTM) vs Model 2 (probabilistic quantile head)를 비교하는 연구 분석 대시보드를 구현한다. 화면은 dense analytic surface로 유지하며, 마케팅 landing page처럼 만들지 않는다.

---

## 2. 기술 스택

| 항목 | 선택 | 근거 |
|--|--|--|
| 프레임워크 | Next.js 15 App Router | dashboard/AGENTS.md 기준 |
| 언어 | TypeScript | dashboard/AGENTS.md 기준 |
| 스타일 | CSS Variables (Tailwind 없음) | legacy 검증, Figma 디자인 번역 |
| 폰트 | Geist, Geist Mono, Noto Sans KR | Figma 디자인 기준 |
| 아이콘 | lucide-react | dashboard/AGENTS.md 기준 |
| 차트 | 인라인 SVG | 경량, 라이브러리 불필요, 정적 데이터 |
| 패키지 관리 | npm + package-lock.json | dashboard/AGENTS.md 기준 |

---

## 3. 섹션 구조

7개 섹션, 각자 고유 accent 색상:

| ID | 한글 | 영문 경로 | Accent 색 |
|----|------|-----------|-----------|
| O | 개요 | `/overview` | `#6bb4ff` (blue) |
| H | 수문곡선 | `/hydrograph` | `#67d4ff` (cyan) |
| D | 데이터셋 | `/dataset` | `#50e3c2` (teal) |
| M | 모델 | `/model` | `#b69bff` (purple) |
| R | 결과 | `/results` | `#f7b955` (amber) |
| A | 분석 | `/analysis` | `#b8c0cc` (gray-blue) |
| S | 스트레스 | `/stress` | `#ff6b8a` (pink) |

---

## 4. 색상 시스템 (CSS Variables)

```css
:root {
  /* Surfaces */
  --bg:          #0a0a0a;   /* 메인 배경 */
  --shell:       #101010;   /* 아이콘 레일 */
  --sidebar-bg:  #111111;   /* 컨텍스트 사이드바 */
  --panel:       #171717;   /* 카드 배경 */
  --panel-inner: #161616;   /* 사이드바 카드 */
  --panel-deep:  #101010;   /* 내부 row */
  --panel-table: #1d1d1d;   /* 테이블 배경 */

  /* Borders */
  --hairline:    #2a2a2a;
  --hairline-hi: #202020;
  --hairline-tbl:#2e2e2e;

  /* Text */
  --ink:         #f5f5f5;
  --ink-2:       #ededed;
  --ink-body:    #d4d4d4;
  --ink-muted:   #a3a3a3;
  --ink-dim:     #8f8f8f;
  --ink-faint:   #555555;

  /* Brand accent */
  --accent-brand:#4ce0ce;

  /* Section accents */
  --accent-O:    #6bb4ff;
  --accent-H:    #67d4ff;
  --accent-D:    #50e3c2;
  --accent-M:    #b69bff;
  --accent-R:    #f7b955;
  --accent-A:    #b8c0cc;
  --accent-S:    #ff6b8a;

  /* Status */
  --status-good: #50e3c2;
  --status-warn: #ffd166;
  --status-rose: #ff6b8a;

  /* Radius */
  --r-sm:  6px;
  --r-md:  8px;
  --r-lg:  10px;
  --r-xl:  12px;
  --r-2xl: 14px;
}
```

---

## 5. 레이아웃

### 5.1 데스크탑 (≥ 900px)

```
┌─────────┬──────────────────────┬──────────────────────────────┐
│Icon Rail│ Context Sidebar      │ Main Canvas                  │
│  60px   │      240px           │        flex-1                │
│         │                      │                              │
│ C [브랜드]│ [제품 마크 82×82]    │ [Header: 제목 + 버튼]        │
│         │ CAMELS Dashboard     │                              │
│ O (active)│ [섹션 제목 32px]    │ [KPI Strip: 3열]             │
│ H       │ [섹션 부제]           │                              │
│ D       │ [판단 범위 고정 카드]  │ [Hero Row: 차트 2/3 + 체크 1/3]│
│ M       │ [증거 흐름 카드]       │                              │
│ R       │ [분석 진행 미니차트]   │ [섹션 인덱스 테이블]          │
│ A       │                      │                              │
│ S       │                      │                              │
│ ? (도움)│                      │                              │
│ [JM아바타]│                    │                              │
└─────────┴──────────────────────┴──────────────────────────────┘
```

**실제 Figma 치수**: Icon Rail 84px, Sidebar 389px, Canvas 1207px (총 1680px)  
**구현**: `grid-template-columns: 60px minmax(200px, 240px) 1fr`

### 5.2 모바일 (< 900px)

```
┌──────────────────────────────┐
│ [Topbar: C + 섹션명 + ≡ 메뉴] │  50px
├──────────────────────────────┤
│ [Pill Nav: O H D M R A S tree] │  scroll
├──────────────────────────────┤
│ [Scope Lock 카드]             │  88px
│ [KPI Row 1]                  │  52px
│ [KPI Row 2]                  │  52px
│ [KPI Row 3]                  │  52px
│ [Chart 카드]                  │  210px
│ [섹션 인덱스 row]              │  52px × n
└──────────────────────────────┘
```

**Figma 기준**: 430×932, 18px inset, card padding 18px, table rows as cards

---

## 6. 컴포넌트 목록

### 6.1 셸 컴포넌트

| 컴포넌트 | 파일 | 역할 |
|--|--|--|
| `DashboardShell` | `components/dashboard-shell.tsx` | 3-column grid, 반응형 전환 |
| `IconRail` | `components/icon-rail.tsx` | 세로 섹션 nav, 아바타 |
| `ContextSidebar` | `components/context-sidebar.tsx` | 제품 마크, 스코프 카드, 증거 흐름 |
| `MobileTopBar` | `components/mobile-topbar.tsx` | 탑바 + pill nav |
| `ThemeToggle` | `components/theme-toggle.tsx` | light/dark (미래 확장용) |

### 6.2 카드/블록 컴포넌트

| 컴포넌트 | 파일 | 역할 |
|--|--|--|
| `KpiCard` | `components/kpi-card.tsx` | 숫자 + 레이블 + 스파크라인 |
| `KpiRow` | `components/kpi-row.tsx` | 모바일 전용 row |
| `ChartCard` | `components/chart-card.tsx` | 라인 차트 + segmented control |
| `SectionTable` | `components/section-table.tsx` | 섹션 인덱스 dense 테이블 |
| `ScopeCard` | `components/scope-card.tsx` | 판단 범위 고정 |
| `EvidenceFlow` | `components/evidence-flow.tsx` | PRIMARY/TAIL/CAVEAT 흐름 |
| `CheckpointCard` | `components/checkpoint-card.tsx` | 판단 체크포인트 row들 |
| `InlineSvgChart` | `components/inline-svg-chart.tsx` | 공용 SVG 라인/바 차트 |

### 6.3 섹션 페이지 (Next.js App Router)

```
dashboard/
├── app/
│   ├── layout.tsx          # html, body, font, CSS 변수
│   ├── globals.css         # CSS 변수, reset, 유틸
│   ├── page.tsx            # / → /overview redirect
│   └── [section]/
│       └── page.tsx        # overview|hydrograph|dataset|model|results|analysis|stress
├── components/             # 위 컴포넌트 목록
├── lib/
│   ├── dashboard-data.ts   # typed snapshot (KPI, 섹션 메타, 증거 흐름)
│   ├── sections.ts         # 섹션 ID, 레이블, accent 색 상수
│   └── format.ts           # 숫자 포매터
└── public/
    └── figures/            # output/에서 복사한 figure PNG
```

---

## 7. 데이터 레이어

`lib/dashboard-data.ts`에 typed snapshot으로 관리. 실제 실험 수치 사용:

**KPI (개요 섹션)**:
- DRBC test: 38 유역
- 공식 seed: 111 / 222 / 444
- q99 과소추정: Model 2 q99 44.0% (Model 1 72.6% 대비)

**섹션 인덱스 rows** (섹션명, 역할, 주요 자료, 상태):
- 데이터셋: split provenance, subset300, 설계 반영
- 모델: head-only contrast, q50/q90/q95/q99, 완료
- Evidence: Primary + high-flow layer, q99, open

**증거 흐름**:
- PRIMARY: DRBC test 38
- TAIL: q90/q95/q99 과소추정
- CAVEAT: calibration claim 분리

차트 데이터는 `output/model_analysis/` 산출물에서 snapshot 추출하거나, figure PNG를 `public/figures/`에 복사해 `<img>`로 표시한다.

---

## 8. 반응형 전환점

```css
/* 데스크탑: icon rail + sidebar + canvas */
@media (min-width: 900px) { ... }

/* 태블릿/모바일: topbar + pill nav + 스크롤 콘텐츠 */
@media (max-width: 899px) { ... }

/* 소형 폰: 패딩 축소 */
@media (max-width: 480px) { ... }
```

데스크탑에서 sidebar는 토글 가능 (≡ 버튼으로 접기/펼치기).

---

## 9. 구현 범위

### In scope (이번 구현)
- Next.js 프로젝트 세팅 (package.json, tsconfig, next.config)
- CSS Variables 시스템 (globals.css)
- DashboardShell (3-column 데스크탑 + 모바일 적응형)
- IconRail + ContextSidebar
- MobileTopBar + pill nav
- 7개 섹션 라우트 (App Router dynamic segment)
- 개요(O) 섹션 전체 구현 (KPI strip + 차트 + 섹션 인덱스)
- 나머지 6개 섹션 기본 뼈대
- `lib/dashboard-data.ts` snapshot
- `npm run typecheck` + `npm run build` 통과

### Out of scope (후속)
- Light 테마 (CSS 변수 준비만)
- figure gallery / hydrograph 이미지 전체 연동
- 상세 페이지 (`/details/[slug]`)
- 인터랙티브 차트 (recharts 등)

---

## 10. 검증 기준

1. `npm run typecheck` 오류 없음
2. `npm run build` 성공
3. 데스크탑 900px 이상에서 3-column 레이아웃 표시
4. 모바일 430px에서 pill nav + row 레이아웃 표시
5. 7개 섹션 경로 (`/overview`, `/results` 등) 라우팅 동작
6. 개요 섹션: KPI 3개, 차트 카드, 섹션 인덱스 테이블 표시
