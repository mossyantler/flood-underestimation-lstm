export type DashboardSectionId =
  | "overview"
  | "hydrograph"
  | "dataset"
  | "model"
  | "results"
  | "analysis"
  | "stress";

export type DashboardSection = {
  id: DashboardSectionId;
  key: string;
  label: string;
  eyebrow: string;
  title: string;
  subtitle: string;
  sidebarMeta: string;
  groupIds: string[];
  detailSlug: string;
};

export const dashboardSections: DashboardSection[] = [
  {
    id: "overview",
    key: "O",
    label: "개요",
    eyebrow: "비교 범위",
    title: "비교 범위와 증거 흐름",
    subtitle:
      "DRBC holdout, paired seed, q99 peak-bias evidence를 한 화면에서 고정합니다.",
    sidebarMeta: "비교 범위와 증거 흐름",
    groupIds: [
      "data-foundation",
      "overall-performance",
      "probabilistic-head",
      "event-stress",
      "basin-robustness",
      "paper-assets"
    ],
    detailSlug: "primary-high-flow-quantiles"
  },
  {
    id: "hydrograph",
    key: "H",
    label: "수문곡선",
    eyebrow: "event shape",
    title: "첨두 형상과 timing drift",
    subtitle:
      "Observed Q99+ hydrograph gallery와 대표 후보를 통해 peak magnitude, timing, managed-flow artifact를 분리합니다.",
    sidebarMeta: "event shape와 timing drift 확인",
    groupIds: ["event-stress", "probabilistic-head"],
    detailSlug: "hydrograph-review"
  },
  {
    id: "dataset",
    key: "D",
    label: "데이터셋",
    eyebrow: "DRBC holdout",
    title: "DRBC Holdout과 Subset300 구성",
    subtitle:
      "non-DRBC fixed subset300으로 학습하고 DRBC 38개 quality-pass basin에서 일반화를 평가합니다.",
    sidebarMeta: "DRBC holdout과 subset300 provenance",
    groupIds: ["data-foundation"],
    detailSlug: "dataset-split-boundary"
  },
  {
    id: "model",
    key: "M",
    label: "모델",
    eyebrow: "head-only comparison",
    title: "Model 1 vs Model 2 비교 계약",
    subtitle:
      "동일 LSTM backbone에서 deterministic head와 quantile head만 바꾼 paired seed 비교입니다.",
    sidebarMeta: "동일 backbone, head만 비교",
    groupIds: ["overall-performance", "probabilistic-head"],
    detailSlug: "model-comparison-contract"
  },
  {
    id: "results",
    key: "R",
    label: "결과",
    eyebrow: "primary readout",
    title: "Primary metric과 flood-tail evidence 분리",
    subtitle:
      "q50/q90/q95/q99 KPI와 primary metric delta를 서로 다른 증거층으로 읽습니다.",
    sidebarMeta: "primary metric과 flood-tail evidence 분리",
    groupIds: ["overall-performance", "probabilistic-head"],
    detailSlug: "primary-results-guardrail"
  },
  {
    id: "analysis",
    key: "A",
    label: "분석",
    eyebrow: "robustness queue",
    title: "Artifact index와 robustness queue",
    subtitle:
      "Calibration, Natural/Broad robustness, event-regime, paper asset source를 한 곳에서 추적합니다.",
    sidebarMeta: "artifact index와 robustness queue",
    groupIds: ["basin-robustness", "paper-assets", "probabilistic-head"],
    detailSlug: "analysis-calibration-robustness"
  },
  {
    id: "stress",
    key: "S",
    label: "스트레스",
    eyebrow: "historical supplement",
    title: "Extreme-rain historical stress check",
    subtitle:
      "DRBC holdout 조건은 유지하지만 1980-2024 historical period를 쓰는 보조 test로 분리합니다.",
    sidebarMeta: "historical 보조 test",
    groupIds: ["event-stress"],
    detailSlug: "stress-supplementary-check"
  }
];

export const overviewReadout = {
  eyebrow: "Q99 peak underestimation",
  value: "0.440",
  delta: "28.6%p lower than Model 1",
  title: "비교 범위와 증거 흐름을 먼저 잠급니다.",
  bullets: [
    "Model 1 deterministic baseline 대비 Model 2 quantile head만 비교",
    "DRBC test 38개 유역과 official paired seed 111 / 222 / 444 고정",
    "q99 과소추정 0.440은 flood-tail bracket evidence로 해석",
    "Stress 1980-2024는 historical supplementary check로 primary claim과 분리"
  ]
};

export const evidenceFlow = [
  {
    key: "D",
    title: "데이터셋",
    body: "DRBC 38, fixed subset300, stress 1980-2024의 역할을 분리합니다."
  },
  {
    key: "M",
    title: "모델",
    body: "M1 deterministic과 M2 q50/q90/q95/q99의 비교 계약을 고정합니다."
  },
  {
    key: "R",
    title: "결과",
    body: "q50/q90/q95/q99 KPI와 primary metric delta를 서로 다른 증거층으로 읽습니다."
  },
  {
    key: "A",
    title: "분석",
    body: "Evidence matrix, cohort robustness, flags/open task를 한 곳에 모읍니다."
  },
  {
    key: "S",
    title: "스트레스",
    body: "Extreme-rain stress는 primary claim과 분리된 supplementary check로 둡니다."
  }
];

export const datasetLedger = [
  ["DRBC holdout", "38", "primary test region"],
  ["fixed subset", "300", "training/validation subset"],
  ["official seeds", "3", "111 / 222 / 444"],
  ["stress period", "1980-2024", "historical supplementary"]
] as const;

export const modelContractRows = [
  ["Model 1", "Deterministic multi-basin LSTM", "baseline"],
  ["Model 2 q50", "same backbone + median quantile", "central guardrail"],
  ["Model 2 q90/q95", "upper quantile head", "flood-tail bracket"],
  ["Model 2 q99", "upper-tail readout", "peak underestimation evidence"]
] as const;

export const hydrographQueue = [
  ["window", "336h"],
  ["series", "6"],
  ["대표 후보", "15"],
  ["gallery", "7,137 PNG"]
] as const;

export const stressLedger = [
  ["Stress event", "236", "historical rain-event catalog"],
  ["DRBC basin", "38", "regional holdout condition kept"],
  ["Positive response", "157", "supplementary response check"],
  ["Claim boundary", "separate", "not temporal independence evidence"]
] as const;
