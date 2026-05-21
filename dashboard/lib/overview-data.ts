export type DashboardStatus = "ready" | "in-progress" | "needs-rerun" | "planned";

export type StatusKpi = {
  label: string;
  value: string;
  note: string;
  status: DashboardStatus;
  source: string;
  href: string;
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
    href: "/overview/status",
  },
  {
    label: "Official seeds",
    value: "3",
    note: "111 / 222 / 444 paired comparison",
    status: "ready",
    source: "docs/experiment/method/model/architecture.md",
    href: "/experiment/seed-checkpoint",
  },
  {
    label: "First test",
    value: "expanded rerun",
    note: "primary basin universe mismatch",
    status: "needs-rerun",
    source: "dashboard/lib/evaluation-tests-data.ts",
    href: "/experiment/test-matrix",
  },
  {
    label: "Extreme test",
    value: "expanded rerun",
    note: "stress catalog must match expanded basin universe",
    status: "needs-rerun",
    source: "dashboard/lib/evaluation-tests-data.ts",
    href: "/analysis/stress",
  },
  {
    label: "Confirmed flood",
    value: "ready",
    note: "NWS flood-stage event layer",
    status: "ready",
    source: "output/model_analysis/confirmed_flood/",
    href: "/analysis/confirmed-flood",
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
