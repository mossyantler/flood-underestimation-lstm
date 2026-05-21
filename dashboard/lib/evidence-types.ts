export const EVIDENCE_SECTIONS = ["overview", "experiment", "foundation", "analysis", "reference"] as const;
export const EVIDENCE_KINDS = ["doc", "report", "chart", "table", "gallery", "script", "data"] as const;
export const EVIDENCE_ROLES = ["canonical", "supporting", "archive"] as const;
export const EVIDENCE_STATUSES = ["ready", "needs-rerun", "planned", "stale", "archive"] as const;

export type EvidenceSection = (typeof EVIDENCE_SECTIONS)[number];
export type EvidenceKind = (typeof EVIDENCE_KINDS)[number];
export type EvidenceRole = (typeof EVIDENCE_ROLES)[number];
export type EvidenceStatus = (typeof EVIDENCE_STATUSES)[number];

export type AnalysisModuleCopy = {
  moduleId: string;
  section: EvidenceSection;
  module: string;
  title: string;
  analysisPurpose: string;
  background: string;
  coreData: string;
  interpretationMethod: string;
  currentJudgment: string;
  status: EvidenceStatus;
};

export type EvidenceItem = {
  id: string;
  moduleId: string;
  title: string;
  section: EvidenceSection;
  module: string;
  kind: EvidenceKind;
  role: EvidenceRole;
  priority: 1 | 2 | 3;
  showInDashboard: boolean;
  sourcePath: string;
  generatorPath?: string;
  docPath?: string;
  chartPath?: string;
  tablePath?: string;
  galleryPath?: string;
  analysisPurpose?: string;
  shortDescription?: string;
  tags: string[];
  status: EvidenceStatus;
  notes?: string;
};
