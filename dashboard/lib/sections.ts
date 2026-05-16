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
