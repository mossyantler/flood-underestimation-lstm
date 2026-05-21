export const SECTION_IDS = ["O", "E", "F", "A", "R"] as const;
export type SectionId = (typeof SECTION_IDS)[number];

export const SECTION_SLUG = {
  O: "overview",
  E: "experiment",
  F: "foundation",
  A: "analysis",
  R: "reference",
} as const satisfies Record<SectionId, string>;

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

export type SectionSlug = (typeof SECTION_SLUG)[SectionId];

export const SLUG_TO_ID = Object.fromEntries(
  Object.entries(SECTION_SLUG).map(([id, slug]) => [slug, id as SectionId])
) as Partial<Record<SectionSlug, SectionId>>;

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
