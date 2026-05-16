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
// 출처: output/model_analysis/quantile_analysis/
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
