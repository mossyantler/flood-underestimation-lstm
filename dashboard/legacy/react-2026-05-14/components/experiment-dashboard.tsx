"use client";

import Image from "next/image";
import Link from "next/link";
import type { ComponentType } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  BarChart3,
  BookOpenCheck,
  ChevronDown,
  ChevronRight,
  Database,
  Download,
  Eye,
  Filter,
  FlaskConical,
  Gauge,
  Layers,
  Search,
  Sigma,
  Table2,
  Waves
} from "lucide-react";
import {
  startTransition,
  useDeferredValue,
  useMemo,
  useState
} from "react";

import type {
  AnalysisItem,
  DashboardData,
  GroupSummary,
  KpiCard
} from "@/lib/dashboard-data";
import { clampPercent, formatPercent, formatSigned } from "@/lib/format";
import { ThemeToggle } from "./theme-toggle";

type IconComponent = ComponentType<{
  size?: number;
  strokeWidth?: number;
  className?: string;
}>;

type DashboardSection =
  | "overview"
  | "hydrograph"
  | "dataset"
  | "model"
  | "results"
  | "analysis"
  | "stress";

type SectionConfig = {
  id: DashboardSection;
  key: string;
  label: string;
  title: string;
  description: string;
  icon: IconComponent;
  groupIds: string[];
  detailSlug?: string;
};

const sectionNav: SectionConfig[] = [
  {
    id: "overview",
    key: "O",
    label: "Overview",
    title: "DRBC holdout 실험은 결과 통합 단계입니다.",
    description:
      "Model 1과 Model 2의 paired seed 비교는 완료됐고, 현재는 primary 성능, high-flow evidence, 산출물 프로토콜을 연결해 논문용 근거 체계를 정리하고 있습니다.",
    icon: Gauge,
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
    label: "실험 가설",
    title: "Output design 가설과 판정 기준",
    description:
      "극한 홍수 첨두 과소추정이 output design 문제인지 판정합니다. Model 3 제외, stress test 보조, checkpoint sensitivity 비재선택 원칙을 guardrail로 함께 고정합니다.",
    icon: Waves,
    groupIds: ["event-stress"],
    detailSlug: "hydrograph-review"
  },
  {
    id: "dataset",
    key: "D",
    label: "데이터셋",
    title: "DRBC Holdout과 Subset300 구성",
    description:
      "DRBC 정의와 quality gate, non-DRBC training pool, fixed subset300 선택 이유를 한 페이지에서 확인합니다.",
    icon: Database,
    groupIds: ["data-foundation"],
    detailSlug: "dataset-split-boundary"
  },
  {
    id: "model",
    key: "M",
    label: "실험 방법",
    title: "Model 1 vs Model 2 비교 설계",
    description:
      "동일 backbone, 다른 output head라는 비교 조건을 고정하고 paired seed, primary/stress/sensitivity 평가 축을 분리합니다.",
    icon: Sigma,
    groupIds: ["overall-performance", "probabilistic-head"],
    detailSlug: "model-comparison-contract"
  },
  {
    id: "results",
    key: "R",
    label: "결과",
    title: "Primary metric과 high-flow evidence",
    description:
      "q50 guardrail과 q99 tail signal을 같이 보되, primary metric delta와 flood-tail evidence를 다른 증거층으로 읽습니다.",
    icon: BarChart3,
    groupIds: ["overall-performance", "probabilistic-head"],
    detailSlug: "primary-results-guardrail"
  },
  {
    id: "analysis",
    key: "A",
    label: "세부 분석",
    title: "Artifact index와 robustness queue",
    description: "Evidence matrix, cohort robustness, flags/open task를 한 곳에 모읍니다.",
    icon: Layers,
    groupIds: ["basin-robustness", "paper-assets", "probabilistic-head"],
    detailSlug: "analysis-calibration-robustness"
  },
  {
    id: "stress",
    key: "S",
    label: "스트레스",
    title: "Historical 보조 test",
    description: "Extreme-rain stress는 primary claim과 분리된 supplementary check로 둡니다.",
    icon: AlertTriangle,
    groupIds: ["event-stress"],
    detailSlug: "stress-supplementary-check"
  }
];

const groupIcons: Record<string, IconComponent> = {
  "data-foundation": Database,
  "overall-performance": Activity,
  "probabilistic-head": Sigma,
  "event-stress": Waves,
  "basin-robustness": Layers,
  "paper-assets": BookOpenCheck
};

const overviewCheckpoints = [
  "Model 1 deterministic baseline 대비 Model 2 quantile head만 비교",
  "DRBC test 38개 유역과 official paired seed 111 / 222 / 444 고정",
  "q99 과소추정 0.440은 flood-tail bracket evidence로 해석",
  "Stress 1980-2024는 historical supplementary check로 primary claim과 분리"
];

const hydrographQueue = [
  ["window", "336h"],
  ["series", "6"],
  ["대표 후보", "15"],
  ["gallery", "7,137 PNG"]
];

const datasetLedger = [
  ["DRBC holdout", "38", "primary test region"],
  ["fixed subset", "300", "training/validation subset"],
  ["official seeds", "3", "111 / 222 / 444"],
  ["stress period", "1980-2024", "historical supplementary"]
];

const modelRows = [
  ["Model 1", "Deterministic multi-basin LSTM", "baseline"],
  ["Model 2 q50", "same backbone + median quantile", "central guardrail"],
  ["Model 2 q90/q95", "upper quantile head", "flood-tail bracket"],
  ["Model 2 q99", "upper-tail readout", "peak underestimation evidence"]
];

const stressRows = [
  ["Stress event", "236", "historical rain-event catalog"],
  ["DRBC basin", "38", "regional holdout condition kept"],
  ["Positive response", "157", "supplementary response check"],
  ["Claim boundary", "separate", "not temporal independence evidence"]
];

const sectionRoutes: Record<DashboardSection, string> = {
  overview: "/overview",
  hydrograph: "/hypotheses/output-design-hypothesis",
  dataset: "/dataset/drbc-holdout-subset300",
  model: "/method/model-comparison-design",
  results: "/results/primary-high-flow",
  analysis: "/analysis/evidence-index",
  stress: "/stress"
};

const topNavSections = sectionNav.filter((section) => section.id !== "stress");

const sectionEyebrows: Record<DashboardSection, string> = {
  overview: "실험 개요",
  hydrograph: "실험 가설",
  dataset: "데이터셋",
  model: "실험 방법",
  results: "결과",
  analysis: "세부 분석",
  stress: "스트레스"
};

const sectionBreadcrumbs: Record<DashboardSection, string> = {
  overview: "CAMELSH / SUBSET300",
  hydrograph: "실험 가설 > Output design 가설과 판정 기준",
  dataset: "데이터셋 > DRBC Holdout과 Subset300 구성",
  model: "실험 방법 > Model 1 vs Model 2 비교 설계",
  results: "결과 > Primary metric과 high-flow evidence",
  analysis: "세부 분석 > Evidence matrix와 robustness queue",
  stress: "스트레스 > Extreme-rain runoff-ratio 진단"
};

const sectionSidebarCopy: Record<
  DashboardSection,
  {
    subtitle: string;
    insightTitle: string;
    insightBody: string;
    flowTitle: string;
    flowItems: Array<[string, string]>;
    progressTitle: string;
    progressCaption: string;
  }
> = {
  overview: {
    subtitle: "비교 범위와 증거 흐름",
    insightTitle: "판단 범위 고정",
    insightBody: "DRBC holdout, paired seed, q99 해석 경계를 먼저 잠급니다.",
    flowTitle: "증거 흐름",
    flowItems: [
      ["PRIMARY", "DRBC test 38"],
      ["TAIL", "q90/q95/q99 과소추정"],
      ["CAVEAT", "calibration claim 분리"]
    ],
    progressTitle: "분석 진행",
    progressCaption: "섹션 연결 상태"
  },
  hydrograph: {
    subtitle: "event shape와 timing drift 확인",
    insightTitle: "첨두 형상 판독",
    insightBody: "선택 flood event에서 peak underestimation과 timing drift를 직접 확인합니다.",
    flowTitle: "이벤트 경로",
    flowItems: [
      ["WINDOW", "336h sequence"],
      ["PEAK", "top event compare"],
      ["TIMING", "hour offset check"]
    ],
    progressTitle: "이벤트 범위",
    progressCaption: "hydrograph samples"
  },
  dataset: {
    subtitle: "DRBC holdout과 subset300 provenance",
    insightTitle: "분할 근거 우선",
    insightBody: "결과보다 먼저 CAMELSH hourly, DRBC holdout, non-DRBC subset300의 경계를 보여줍니다.",
    flowTitle: "데이터 경로",
    flowItems: [
      ["SPLIT", "DRBC 38 / subset300"],
      ["COVERAGE", "train 269 / val 31 / test 38"],
      ["STRESS", "1980-2024 보조 증거"]
    ],
    progressTitle: "Coverage 상태",
    progressCaption: "source path 연결"
  },
  model: {
    subtitle: "동일 backbone, head만 비교",
    insightTitle: "backbone 고정",
    insightBody: "두 모델은 LSTM backbone을 공유하고 output head만 비교 대상으로 둡니다.",
    flowTitle: "모델 경로",
    flowItems: [
      ["MODEL 1", "deterministic baseline"],
      ["MODEL 2", "quantile head"],
      ["SEEDS", "111 / 222 / 444"]
    ],
    progressTitle: "실행 범위",
    progressCaption: "paired completion"
  },
  results: {
    subtitle: "primary metric과 flood-tail evidence 분리",
    insightTitle: "q99는 evidence layer",
    insightBody: "q99 tail evidence는 성능 주장보다 peak underestimation 해석에 붙입니다.",
    flowTitle: "결과 페이지",
    flowItems: [
      ["PRIMARY", "NSE / KGE / NSElog"],
      ["TAIL", "q90/q95/q99 peak under"],
      ["SENS", "checkpoint sensitivity"]
    ],
    progressTitle: "근거 강도",
    progressCaption: "metric agreement"
  },
  analysis: {
    subtitle: "artifact index와 robustness queue",
    insightTitle: "반복하지 않는 index",
    insightBody: "analysis page는 설명 문서가 아니라 artifact와 next action의 index로 씁니다.",
    flowTitle: "분석 그룹",
    flowItems: [
      ["REGIME", "event-regime"],
      ["ROBUST", "cohort robustness"],
      ["HYDRO", "event hydrographs"]
    ],
    progressTitle: "코호트 범위",
    progressCaption: "analysis groups"
  },
  stress: {
    subtitle: "historical 보조 test와 falsification",
    insightTitle: "primary claim 분리",
    insightBody: "stress 결과는 DRBC historical response를 확인하지만 temporal independence claim에는 쓰지 않습니다.",
    flowTitle: "Stress checks",
    flowItems: [
      ["RAIN", "extreme-rain catalog"],
      ["RESPONSE", "positive event response"],
      ["BOUNDARY", "supplementary only"]
    ],
    progressTitle: "Stress 범위",
    progressCaption: "supplementary check"
  }
};

const overviewRows = [
  ["데이터셋", "split provenance", "subset300", "설계 반영"],
  ["모델", "head-only contrast", "q50/q90/q95/q99", "완료"],
  ["Evidence", "Primary + high-flow layer", "q99", "open"]
];

export function ExperimentDashboard({ data }: { data: DashboardData }) {
  const [activeSection, setActiveSection] = useState<DashboardSection>("overview");
  const [activeGroupId, setActiveGroupId] = useState(data.groups[0]?.id ?? "");
  const [selectedAnalysisId, setSelectedAnalysisId] = useState(
    data.analyses[0]?.id ?? ""
  );
  const [collapsedGroupIds, setCollapsedGroupIds] = useState<Set<string>>(
    () => new Set()
  );
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const deferredGroupId = useDeferredValue(activeGroupId);

  const analysesByGroup = useMemo(() => {
    const grouped = new Map<string, AnalysisItem[]>();
    for (const analysis of data.analyses) {
      const next = grouped.get(analysis.groupId) ?? [];
      next.push(analysis);
      grouped.set(analysis.groupId, next);
    }
    return grouped;
  }, [data.analyses]);

  const activeSectionConfig = useMemo(
    () => sectionNav.find((section) => section.id === activeSection) ?? sectionNav[0],
    [activeSection]
  );

  const activeSectionAnalyses = useMemo(() => {
    const groupSet = new Set(activeSectionConfig.groupIds);
    const rows = data.analyses.filter((analysis) => groupSet.has(analysis.groupId));

    if (activeSectionConfig.id === "hydrograph") {
      return rows.filter((analysis) =>
        [analysis.id, analysis.title, ...analysis.tags]
          .join(" ")
          .toLowerCase()
          .includes("hydrograph")
      );
    }

    if (activeSectionConfig.id === "stress") {
      return rows.filter((analysis) =>
        [analysis.id, analysis.title, ...analysis.tags]
          .join(" ")
          .toLowerCase()
          .includes("stress")
      );
    }

    return rows;
  }, [activeSectionConfig, data.analyses]);

  const filteredAnalyses = useMemo(() => {
    const lowered = deferredQuery.trim().toLowerCase();

    return data.analyses.filter((analysis) => {
      const inGroup =
        deferredGroupId === "all" || analysis.groupId === deferredGroupId;
      const inText =
        lowered.length === 0 ||
        [
          analysis.title,
          analysis.status,
          analysis.purpose,
          analysis.use,
          ...analysis.tags
        ]
          .join(" ")
          .toLowerCase()
          .includes(lowered);

      return inGroup && inText;
    });
  }, [data.analyses, deferredGroupId, deferredQuery]);

  const selectedAnalysis = useMemo(
    () => data.analyses.find((analysis) => analysis.id === selectedAnalysisId),
    [data.analyses, selectedAnalysisId]
  );

  const quantileReadout = useMemo(() => {
    const model1 = data.quantiles.find((row) => row.predictor === "Model 1");
    const q99 = data.quantiles.find((row) => row.predictor === "Model 2 q99");
    const reductionPoints =
      model1 && q99
        ? (model1.underestimationFraction - q99.underestimationFraction) * 100
        : null;

    return { model1, q99, reductionPoints };
  }, [data.quantiles]);

  function changeSection(sectionId: DashboardSection) {
    startTransition(() => {
      const next = sectionNav.find((section) => section.id === sectionId);
      setActiveSection(sectionId);
      if (next?.groupIds.length === 1) {
        setActiveGroupId(next.groupIds[0]);
      }
    });
  }

  function showAllAnalyses() {
    startTransition(() => {
      setActiveGroupId("all");
      setActiveSection("analysis");
    });
  }

  function toggleGroup(groupId: string) {
    startTransition(() => {
      setActiveGroupId(groupId);
      setCollapsedGroupIds((current) => {
        const next = new Set(current);
        if (next.has(groupId)) {
          next.delete(groupId);
        } else {
          next.add(groupId);
        }
        return next;
      });
    });
  }

  function selectAnalysis(analysisId: string) {
    startTransition(() => {
      const next = data.analyses.find((analysis) => analysis.id === analysisId);
      if (next) {
        setActiveGroupId(next.groupId);
      }
      setSelectedAnalysisId(analysisId);
      setActiveSection("analysis");
    });
  }

  return (
    <main className="dashboard-shell">
      <PenGlobalHeader
        activeSection={activeSection}
        onSectionChange={changeSection}
      />

      <section className="main-canvas">
        <PenPageHero
          section={activeSectionConfig}
          data={data}
          quantileReadout={quantileReadout}
        />

        <section className="tab-surface" aria-live="polite">
          {activeSection === "overview" ? (
            <DashboardSectionContent
              section={activeSectionConfig}
              data={data}
              sectionAnalyses={activeSectionAnalyses}
              filteredAnalyses={filteredAnalyses}
              selectedAnalysis={selectedAnalysis}
              selectedAnalysisId={selectedAnalysisId}
              query={query}
              quantileReadout={quantileReadout}
              onQueryChange={setQuery}
              onSelectAnalysis={selectAnalysis}
            />
          ) : (
            <div className="pen-detail-layout">
              <div className="pen-main-column">
                <DashboardSectionContent
                  section={activeSectionConfig}
                  data={data}
                  sectionAnalyses={activeSectionAnalyses}
                  filteredAnalyses={filteredAnalyses}
                  selectedAnalysis={selectedAnalysis}
                  selectedAnalysisId={selectedAnalysisId}
                  query={query}
                  quantileReadout={quantileReadout}
                  onQueryChange={setQuery}
                  onSelectAnalysis={selectAnalysis}
                />
              </div>
              <PenDetailRail
                section={activeSectionConfig}
                data={data}
                quantileReadout={quantileReadout}
                onSectionChange={changeSection}
              />
            </div>
          )}
        </section>
      </section>
    </main>
  );
}

function PenGlobalHeader({
  activeSection,
  onSectionChange
}: {
  activeSection: DashboardSection;
  onSectionChange: (sectionId: DashboardSection) => void;
}) {
  return (
    <header className="pen-global-header">
      <div className="pen-brand">
        <span>C</span>
        <div>
          <p>CAMELSH / SUBSET300</p>
          <strong>실험 대시보드</strong>
        </div>
      </div>
      <nav className="pen-top-nav" aria-label="주요 대시보드 섹션">
        {topNavSections.map((section) => (
          <button
            key={section.id}
            type="button"
            data-active={
              activeSection === section.id ||
              (activeSection === "stress" && section.id === "analysis")
            }
            onClick={() => onSectionChange(section.id)}
          >
            {section.label}
          </button>
        ))}
      </nav>
      <span className="pen-route-pill">{sectionRoutes[activeSection]}</span>
    </header>
  );
}

function PenPageHero({
  section,
  data,
  quantileReadout
}: {
  section: SectionConfig;
  data: DashboardData;
  quantileReadout: QuantileReadout;
}) {
  const description =
    section.id === "overview" && quantileReadout.reductionPoints !== null
      ? `${section.description} q99 과소추정은 Model 1 대비 ${quantileReadout.reductionPoints.toFixed(
          1
        )}%p 낮게 관측됩니다.`
      : section.description;

  return (
    <header className="pen-page-hero" data-section={section.id}>
      <p className="pen-breadcrumb">{sectionBreadcrumbs[section.id]}</p>
      {section.id === "overview" ? (
        <div className="pen-overview-hero-grid">
          <div>
            <p className="pen-section-label">{sectionEyebrows[section.id]}</p>
            <h1>{section.title}</h1>
            <p>{description}</p>
          </div>
          <PenCurrentStage data={data} />
        </div>
      ) : (
        <>
          <p className="pen-section-label">{sectionEyebrows[section.id]}</p>
          <h1>{section.title}</h1>
          <p>{description}</p>
        </>
      )}
    </header>
  );
}

function PenCurrentStage({ data }: { data: DashboardData }) {
  return (
    <section className="panel pen-current-stage">
      <p>현재 단계</p>
      <h2>결과 통합</h2>
      <span>
        모델 학습과 primary comparison은 완료됐고, 지금은 증거 수준, calibration caveat,
        paper-facing asset을 한 흐름으로 정리하고 있습니다.
      </span>
      <dl>
        <div>
          <dt>공식 seed</dt>
          <dd>{data.scope.officialSeeds.join(" / ")}</dd>
        </div>
        <div>
          <dt>검증 유역</dt>
          <dd>DRBC {data.kpis.find((kpi) => kpi.label.includes("DRBC"))?.value ?? "38"}</dd>
        </div>
      </dl>
    </section>
  );
}

function PenDetailRail({
  section,
  data,
  quantileReadout,
  onSectionChange
}: {
  section: SectionConfig;
  data: DashboardData;
  quantileReadout: QuantileReadout;
  onSectionChange: (sectionId: DashboardSection) => void;
}) {
  const q99 = quantileReadout.q99
    ? quantileReadout.q99.underestimationFraction.toFixed(3)
    : "0.440";

  return (
    <aside className="pen-detail-rail" aria-label="섹션 판단 기준">
      <section className="pen-rail-card pen-rail-highlight">
        <p>핵심 판단</p>
        <h2>{getRailJudgement(section.id, q99)}</h2>
        <span>{getRailCaption(section.id)}</span>
      </section>

      <section className="pen-rail-card pen-method-card">
        <button type="button">
          <span>방법 메모</span>
          <strong>접기</strong>
        </button>
        <h3>{getRailMemo(section.id)}</h3>
        <p>
          왼쪽 main chart는 결과 자체보다 source-of-truth와 판정 기준을 먼저 확인하도록
          구성했습니다.
        </p>
        <div className="tag-row">
          <span>Q99+</span>
          <span>event</span>
          <span>tail</span>
        </div>
      </section>

      <section className="pen-rail-card">
        <p>참조 산출물</p>
        <SourceList sources={data.sources.slice(0, 2)} />
      </section>

      <section className="pen-rail-card">
        <p>다음 보기</p>
        <button
          type="button"
          className="pen-next-row"
          onClick={() => onSectionChange(section.id === "stress" ? "analysis" : "stress")}
        >
          Extreme-rain runoff-ratio 진단
        </button>
        <button
          type="button"
          className="pen-next-row"
          onClick={() => onSectionChange("analysis")}
        >
          Basin dissect report
        </button>
      </section>
    </aside>
  );
}

function getRailJudgement(section: DashboardSection, q99: string) {
  if (section === "hydrograph") {
    return "첫 논문의 공식 비교축은 Model 1과 Model 2입니다.";
  }
  if (section === "dataset") {
    return "DRBC 154 → 38, subset300 300";
  }
  if (section === "model") {
    return "동일 backbone + output head 비교";
  }
  if (section === "results") {
    return `q99 peak underestimation ${q99}`;
  }
  if (section === "analysis") {
    return "docs는 설명 기준, output은 표와 그림 기준입니다.";
  }
  if (section === "stress") {
    return "historical stress는 supplementary evidence입니다.";
  }
  return "docs는 설명의 기준, output은 표와 그림의 기준입니다.";
}

function getRailCaption(section: DashboardSection) {
  if (section === "dataset") {
    return "training pool은 DRBC 밖 tolerant non-DRBC basin에서 구성합니다.";
  }
  if (section === "model") {
    return "구조 차이를 output design 실험으로 고정합니다.";
  }
  if (section === "results") {
    return "primary metric과 tail evidence를 분리해서 읽습니다.";
  }
  if (section === "stress") {
    return "primary temporal independence claim에는 사용하지 않습니다.";
  }
  return "dashboard/public/figures는 표시용 복사본으로만 둡니다.";
}

function getRailMemo(section: DashboardSection) {
  if (section === "hydrograph") {
    return "왼쪽 가설 matrix를 읽는 기준입니다.";
  }
  if (section === "dataset") {
    return "왼쪽 basin split funnel을 읽는 기준입니다.";
  }
  if (section === "model") {
    return "왼쪽 architecture chart를 읽는 기준입니다.";
  }
  if (section === "results") {
    return "왼쪽 metric table과 quantile chart를 읽는 기준입니다.";
  }
  if (section === "analysis") {
    return "왼쪽 evidence matrix를 읽는 기준입니다.";
  }
  return "왼쪽 stress check를 읽는 기준입니다.";
}

function IconRail({
  activeSection,
  onSectionChange
}: {
  activeSection: DashboardSection;
  onSectionChange: (sectionId: DashboardSection) => void;
}) {
  return (
    <aside className="icon-rail" aria-label="대시보드 섹션 바로가기">
      <div className="rail-brand" aria-hidden="true">
        C
      </div>
      <nav className="rail-nav">
        {sectionNav.map((section) => {
          return (
            <button
              key={section.id}
              type="button"
              className="rail-button"
              data-active={activeSection === section.id}
              aria-label={`${section.key} ${section.label}`}
              title={`${section.key} ${section.label}`}
              onClick={() => onSectionChange(section.id)}
            >
              <span>{section.key}</span>
            </button>
          );
        })}
      </nav>
      <div className="rail-avatar" aria-hidden="true">
        JM
      </div>
    </aside>
  );
}

function FigmaContextSidebar({ section }: { section: SectionConfig }) {
  const copy = sectionSidebarCopy[section.id];

  return (
    <>
      <div className="figma-product-mark" aria-hidden="true">
        C
      </div>
      <p className="figma-welcome">CAMELS Dashboard</p>
      <h2 className="figma-sidebar-title">{section.label}</h2>
      <p className="figma-sidebar-subtitle">{copy.subtitle}</p>

      <section className="figma-highlight-card">
        <p>핵심 판독</p>
        <h3>{copy.insightTitle}</h3>
        <span>{copy.insightBody}</span>
      </section>

      <section className="figma-flow-card">
        <h3>{copy.flowTitle}</h3>
        {copy.flowItems.map(([meta, text]) => (
          <div key={meta}>
            <strong>{meta}</strong>
            <span>{text}</span>
          </div>
        ))}
      </section>

      <section className="figma-progress-card">
        <div>
          <h3>{copy.progressTitle}</h3>
          <span>진행</span>
          <strong>{copy.progressCaption}</strong>
        </div>
        <MiniBars />
      </section>
    </>
  );
}

function MiniBars() {
  return (
    <div className="mini-bars" aria-hidden="true">
      {[29, 42, 25, 55, 36, 62, 31, 50, 46, 64].map((height, index) => (
        <span key={`${height}-${index}`} style={{ height }} />
      ))}
    </div>
  );
}

function getSectionKpis(section: DashboardSection, data: DashboardData): KpiCard[] {
  if (section === "overview") {
    return data.kpis.slice(0, 3);
  }

  if (section === "results") {
    return [
      {
        label: "중앙 성능",
        value: "q50",
        detail: "overall guardrail",
        tone: "good",
        detailSlug: "primary-results-guardrail"
      },
      {
        label: "tail onset",
        value: "q90",
        detail: "transition check",
        tone: "good",
        detailSlug: "primary-high-flow-quantiles"
      },
      {
        label: "tail bias",
        value: "q95",
        detail: "under-deficit check",
        tone: "near",
        detailSlug: "primary-high-flow-quantiles"
      },
      {
        label: "q99 under",
        value: data.kpis.find((kpi) => kpi.label.includes("Q99"))?.value ?? "0.440",
        detail: "lower is better",
        tone: "warn",
        detailSlug: "primary-high-flow-quantiles"
      }
    ];
  }

  if (section === "model") {
    return [
      { label: "기준선", value: "M1", detail: "deterministic head", tone: "neutral" },
      { label: "분위수", value: "M2", detail: "q50/q90/q95/q99 head", tone: "near" },
      { label: "Subset", value: "300", detail: "fixed train basins", tone: "good" }
    ];
  }

  if (section === "dataset") {
    return [
      data.kpis[0],
      { label: "fixed subset", value: "300", detail: "non-DRBC train/val", tone: "good" },
      { label: "stress 기간", value: "1980-2024", detail: "primary claim 아님", tone: "neutral" }
    ];
  }

  if (section === "hydrograph") {
    return [
      { label: "Window", value: "336h", detail: "input/output sequence", tone: "good" },
      { label: "Series", value: "6개", detail: "obs / M1 / q50/q90/q95/q99", tone: "near" },
      { label: "대표 후보", value: "15", detail: "modal preload", tone: "neutral" }
    ];
  }

  if (section === "stress") {
    return [
      data.kpis[3],
      { label: "DRBC basin", value: "38", detail: "holdout condition kept", tone: "good" },
      { label: "Boundary", value: "supp.", detail: "not primary claim", tone: "warn" }
    ];
  }

  return [
    { label: "Evidence", value: "matrix", detail: "artifact index", tone: "good" },
    { label: "Cohort", value: "3", detail: "Broad / Natural / non-natural", tone: "near" },
    { label: "Open task", value: "4", detail: "paper-facing queue", tone: "neutral" }
  ];
}

function DashboardBrand({ title }: { title: string }) {
  return (
    <div className="brand-lockup">
      <div className="brand-mark" aria-hidden="true">
        <FlaskConical size={16} />
      </div>
      <div>
        <p className="mono-label">CAMELSH / SUBSET300</p>
        <h2>{title}</h2>
      </div>
    </div>
  );
}

function ContextSnapshot({
  data,
  quantileReadout
}: {
  data: DashboardData;
  quantileReadout: QuantileReadout;
}) {
  return (
    <section className="context-card" aria-label="실험 snapshot">
      <p className="mono-label">desktop prototype scope</p>
      <dl className="context-metrics">
        <div>
          <dt>DRBC test</dt>
          <dd>{data.kpis.find((kpi) => kpi.label.includes("DRBC"))?.value ?? "38"}</dd>
        </div>
        <div>
          <dt>official seed</dt>
          <dd>{data.scope.officialSeeds.length}</dd>
        </div>
        <div>
          <dt>q99 under</dt>
          <dd>
            {quantileReadout.q99
              ? quantileReadout.q99.underestimationFraction.toFixed(3)
              : "0.440"}
          </dd>
        </div>
      </dl>
      <p className="context-note">
        {data.scope.model1}과 {data.scope.model2}를 같은 subset300에서 비교합니다.
      </p>
    </section>
  );
}

function SectionIndex({
  activeSection,
  onSectionChange
}: {
  activeSection: DashboardSection;
  onSectionChange: (sectionId: DashboardSection) => void;
}) {
  return (
    <nav className="section-index" aria-label="O/H/D/M/R/A/S 섹션">
      {sectionNav.map((section) => (
        <button
          key={section.id}
          type="button"
          className="section-index-row"
          data-active={activeSection === section.id}
          onClick={() => onSectionChange(section.id)}
        >
          <span>{section.key}</span>
          <strong>{section.label}</strong>
          <small>{section.title}</small>
        </button>
      ))}
    </nav>
  );
}

function MobileContext({
  data,
  activeSection,
  onSectionChange
}: {
  data: DashboardData;
  activeSection: DashboardSection;
  onSectionChange: (sectionId: DashboardSection) => void;
}) {
  return (
    <section className="mobile-context" aria-label="모바일 컨텍스트">
      <div>
        <p className="mono-label">CAMELSH / SUBSET300</p>
        <strong>{data.scope.primaryQuestion}</strong>
      </div>
      <nav className="mobile-section-nav" aria-label="대시보드 섹션">
        {sectionNav.map((section) => (
          <button
            key={section.id}
            type="button"
            data-active={activeSection === section.id}
            onClick={() => onSectionChange(section.id)}
          >
            <span>{section.key}</span>
            {section.label}
          </button>
        ))}
      </nav>
    </section>
  );
}

function KpiStrip({ kpis }: { kpis: KpiCard[] }) {
  return (
    <section className="kpi-strip" aria-label="실험 요약 KPI">
      {kpis.map((kpi) => (
        <Kpi key={kpi.label} kpi={kpi} />
      ))}
    </section>
  );
}

type QuantileReadout = {
  model1?: DashboardData["quantiles"][number];
  q99?: DashboardData["quantiles"][number];
  reductionPoints: number | null;
};

function DashboardSectionContent({
  section,
  data,
  sectionAnalyses,
  filteredAnalyses,
  selectedAnalysis,
  selectedAnalysisId,
  query,
  quantileReadout,
  onQueryChange,
  onSelectAnalysis
}: {
  section: SectionConfig;
  data: DashboardData;
  sectionAnalyses: AnalysisItem[];
  filteredAnalyses: AnalysisItem[];
  selectedAnalysis?: AnalysisItem;
  selectedAnalysisId: string;
  query: string;
  quantileReadout: QuantileReadout;
  onQueryChange: (value: string) => void;
  onSelectAnalysis: (analysisId: string) => void;
}) {
  if (section.id === "hydrograph") {
    return (
      <HydrographSection data={data} sectionAnalyses={sectionAnalyses} />
    );
  }

  if (section.id === "dataset") {
    return <DatasetSection data={data} sectionAnalyses={sectionAnalyses} />;
  }

  if (section.id === "model") {
    return <ModelSection data={data} sectionAnalyses={sectionAnalyses} />;
  }

  if (section.id === "results") {
    return (
      <ResultsSection
        data={data}
        sectionAnalyses={sectionAnalyses}
        quantileReadout={quantileReadout}
      />
    );
  }

  if (section.id === "analysis") {
    return (
      <AnalysisSection
        data={data}
        filteredAnalyses={filteredAnalyses}
        selectedAnalysis={selectedAnalysis}
        selectedAnalysisId={selectedAnalysisId}
        query={query}
        onQueryChange={onQueryChange}
        onSelectAnalysis={onSelectAnalysis}
      />
    );
  }

  if (section.id === "stress") {
    return <StressSection data={data} sectionAnalyses={sectionAnalyses} />;
  }

  return (
    <OverviewSection
      data={data}
      sectionAnalyses={sectionAnalyses}
      quantileReadout={quantileReadout}
    />
  );
}

function SidebarAnalysisTree({
  groups,
  analysesByGroup,
  activeGroupId,
  selectedAnalysisId,
  collapsedGroupIds,
  onToggleGroup,
  onSelectAnalysis
}: {
  groups: GroupSummary[];
  analysesByGroup: Map<string, AnalysisItem[]>;
  activeGroupId: string;
  selectedAnalysisId: string;
  collapsedGroupIds: Set<string>;
  onToggleGroup: (groupId: string) => void;
  onSelectAnalysis: (analysisId: string) => void;
}) {
  return (
    <div className="sidebar-analysis-tree">
      {groups.map((group) => {
        const Icon = groupIcons[group.id] ?? Layers;
        const analyses = analysesByGroup.get(group.id) ?? [];
        const isCollapsed = collapsedGroupIds.has(group.id);

        return (
          <div key={group.id} className="sidebar-analysis-group">
            <button
              type="button"
              className="sidebar-group-trigger"
              data-active={activeGroupId === group.id}
              data-collapsed={isCollapsed}
              onClick={() => onToggleGroup(group.id)}
              aria-expanded={!isCollapsed}
              aria-controls={`sidebar-group-${group.id}`}
            >
              <Icon size={15} />
              <span>{group.label}</span>
              <small>{analyses.length}</small>
              <ChevronDown size={14} />
            </button>
            <div
              id={`sidebar-group-${group.id}`}
              className="sidebar-analysis-list"
              data-collapsed={isCollapsed}
            >
              {analyses.map((analysis) => (
                <button
                  key={analysis.id}
                  type="button"
                  className="sidebar-analysis-row"
                  data-active={analysis.id === selectedAnalysisId}
                  onClick={() => onSelectAnalysis(analysis.id)}
                >
                  <span>
                    <strong>{analysis.title}</strong>
                    <small>{analysis.status}</small>
                  </span>
                  <ChevronRight size={13} />
                </button>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function OverviewSection({
  data,
  sectionAnalyses,
  quantileReadout
}: {
  data: DashboardData;
  sectionAnalyses: AnalysisItem[];
  quantileReadout: QuantileReadout;
}) {
  return (
    <div className="pen-overview-grid">
      <section className="panel pen-model-structure">
        <PanelHeader eyebrow="모델 구조" title="같은 backbone, 다른 output head" />
        <p>
          같은 LSTM backbone에서 deterministic head와 quantile head만 분리합니다. 상세 loss와
          output surface는 모델 구조 페이지로 연결합니다.
        </p>
        <ModelFlowDiagram />
        <Link href="/details/model-comparison-contract" className="pen-fat-button">
          모델 구조 상세 보기
          <ArrowUpRight size={15} />
        </Link>
      </section>

      <section className="panel pen-progress-card">
        <PanelHeader eyebrow="분석 진행" title="주요 실험은 완료됐고, 해석과 논문 산출물 연결을 정리 중입니다." />
        <ProgressRows />
      </section>

      <section className="panel pen-route-card">
        <PanelHeader eyebrow="이동 규칙" title="어느 페이지에서도 메인 섹션으로 돌아가고, detail에서는 관련 섹션으로 건너갑니다." />
        <div className="pen-route-flow" aria-label="대시보드 이동 규칙">
          <span>global nav</span>
          <ArrowUpRight size={16} />
          <span>section index</span>
          <ArrowUpRight size={16} />
          <span>detail rail</span>
        </div>
      </section>

      <section className="panel pen-section-map">
        <PanelHeader eyebrow="메인 섹션" title="메인에서 섹션으로, 섹션에서 detail로 들어갑니다." />
        <SectionCards />
      </section>

      <section className="panel pen-analysis-queue">
        <PanelHeader
          eyebrow="analysis queue"
          title={`q99 peak underestimation ${quantileReadout.q99 ? quantileReadout.q99.underestimationFraction.toFixed(3) : "0.440"} 관련 행입니다.`}
        />
        <CompactAnalysisList analyses={sectionAnalyses.slice(0, 3)} groups={data.groups} />
      </section>
    </div>
  );
}

function ModelFlowDiagram() {
  return (
    <div className="pen-model-flow" aria-label="Model comparison architecture">
      <article>
        <Database size={18} />
        <strong>Inputs</strong>
      </article>
      <ArrowUpRight size={20} />
      <article className="active">
        <Layers size={20} />
        <strong>LSTM</strong>
      </article>
      <ArrowUpRight size={20} />
      <div className="pen-head-stack">
        <article>
          <span>Model 1</span>
          <strong>Qhat</strong>
        </article>
        <article className="quantile">
          <span>Model 2</span>
          <strong>q50 / q95 / q99</strong>
        </article>
      </div>
    </div>
  );
}

function ProgressRows() {
  const rows = [
    ["데이터/학습", "완료", 0.92, "good"],
    ["성능 분석", "거의 완료", 0.84, "near"],
    ["논문 산출물", "진행 중", 0.42, "warn"]
  ] as const;

  return (
    <div className="pen-progress-rows">
      {rows.map(([label, state, progress, tone]) => (
        <div key={label} data-tone={tone}>
          <span>{label}</span>
          <div>
            <i style={{ width: clampPercent(progress) }} />
          </div>
          <strong>{state}</strong>
        </div>
      ))}
    </div>
  );
}

function HydrographSection({
  data
}: {
  data: DashboardData;
  sectionAnalyses: AnalysisItem[];
}) {
  return (
    <div className="dashboard-grid two-column-grid pen-detail-stack">
      <section className="panel pen-hypothesis-matrix">
        <PanelHeader
          eyebrow="가설 matrix"
          title="Model 2 - Model 1"
        />
        <div className="pen-matrix-table">
          <span>가설</span>
          <span>판정 기준</span>
          <span>대시보드 위치</span>
          {[
            ["H1", "peak bias 완화", "결과 > High-flow"],
            ["H2", "generalization", "세부 분석 > robustness"],
            ["H3", "future work", "실험 방법 > 모델 구조"]
          ].map(([hypothesis, signal, route], index) => (
            <div key={hypothesis} data-active={index === 2}>
              <strong>{hypothesis}</strong>
              <span>{signal}</span>
              <span>{route}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="panel full-span">
        <PanelHeader eyebrow="가설 판정 흐름" title="각 가설을 어떤 evidence와 claim level로 묶어 볼지 정리" />
        <div className="pen-decision-flow">
          <article className="active">
            <span>H1 · 논문 중심</span>
            <strong>Output design 효과</strong>
            <p>Model 2가 peak underestimation을 줄이면 주장 가능</p>
          </article>
          <article>
            <span>H2 · 후속 확장</span>
            <strong>Physics-guided core</strong>
            <p>현재 공식 비교축에는 넣지 않고 future work로 분리</p>
          </article>
          <article>
            <span>H3 · 조건부</span>
            <strong>Basin mechanism</strong>
            <p>snow / groundwater 영향 유역에서 후속 이득 가능성 탐색</p>
          </article>
        </div>
        <div className="pen-warning-strip">
          공식 claim과 exploratory claim을 분리
        </div>
        <CompactAnalysisList analyses={data.analyses.slice(0, 2)} groups={data.groups} />
      </section>
    </div>
  );
}

function DatasetSection({
  data,
  sectionAnalyses
}: {
  data: DashboardData;
  sectionAnalyses: AnalysisItem[];
}) {
  return (
    <div className="dashboard-grid two-column-grid pen-dataset-stack">
      <section className="panel pen-dataset-funnel">
        <PanelHeader
          eyebrow="D / dataset"
          title="DRBC holdout과 subset300 구성"
          actionHref="/details/dataset-split-boundary"
          actionLabel="split map"
        />
        <p>평가 region과 학습 pool을 분리한 뒤, fixed scaling_300 subset을 공통으로 사용</p>
        <BasinSplitFunnel />
        <div className="pen-funnel-note">
          DRBC는 regional holdout test이고, historical stress는 같은 region의 과거 반응을 보는
          보조 진단입니다.
        </div>
      </section>

      <section className="pen-warning-strip full-span">
        <strong>독립성 주의</strong>
        <span>
          drbc_historical_stress는 1980-2024 기간을 쓰므로 primary temporal independence claim에는
          사용하지 않습니다.
        </span>
      </section>

      <section className="pen-dataset-card-grid full-span">
        <article>
          <span>map</span>
          <strong>DRBC boundary map</strong>
          <p>outlet 기준과 overlap 기준을 함께 확인</p>
        </article>
        <article>
          <span>table</span>
          <strong>coverage table</strong>
          <p>usable years와 estimated-flow fraction 점검</p>
        </article>
        <article>
          <span>rain</span>
          <strong>rain-event catalog</strong>
          <p>hourly Rainf 기반 extreme-rain 보조 test</p>
        </article>
      </section>

      <section className="panel full-span">
        <PanelHeader eyebrow="dataset analysis" title="split, coverage, event catalog 분석입니다." />
        <CompactAnalysisList analyses={sectionAnalyses.slice(0, 3)} groups={data.groups} />
      </section>
    </div>
  );
}

function BasinSplitFunnel() {
  const rows = [
    {
      type: "EVALUATION",
      sourceLabel: "DRBC",
      sourceValue: "154",
      sourceText: "DRBC selected basins",
      gate: "quality gate",
      gateText: "usable year / estimated-flow / boundary confidence",
      targetValue: "38",
      targetText: "primary DRBC test basins"
    },
    {
      type: "TRAINING",
      sourceLabel: "non-DRBC",
      sourceValue: "1923",
      sourceText: "quality-pass training pool",
      gate: "scaling pilot",
      gateText: "100 / 300 / 600 비교 후 compute-aware 선택",
      targetValue: "300",
      targetText: "fixed subset reused by Model 1/2"
    }
  ];

  return (
    <div className="pen-funnel">
      {rows.map((row) => (
        <div className="pen-funnel-row" key={row.type}>
          <div className="pen-funnel-lane">
            <span>{row.type}</span>
            <strong>{row.sourceLabel}</strong>
          </div>
          <div className="pen-funnel-box">
            <strong>{row.sourceValue}</strong>
            <span>{row.sourceText}</span>
          </div>
          <b aria-hidden="true">→</b>
          <div className="pen-funnel-gate">
            <span>{row.gate}</span>
            <p>{row.gateText}</p>
          </div>
          <b aria-hidden="true">→</b>
          <div className="pen-funnel-target">
            <strong>{row.targetValue}</strong>
            <span>{row.targetText}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function ModelSection({
  data,
  sectionAnalyses
}: {
  data: DashboardData;
  sectionAnalyses: AnalysisItem[];
}) {
  return (
    <div className="dashboard-grid two-column-grid">
      <section className="panel hero-panel">
        <PanelHeader
          eyebrow="M / model"
          title="동일 backbone에서 output head만 바뀌는 비교입니다."
          actionHref="/details/model-comparison-contract"
          actionLabel="View detail"
        />
        <ModelContractTable />
      </section>

      <section className="panel">
        <PanelHeader eyebrow="paired seed" title="Seed 333은 final aggregate에서 제외합니다." />
        <SeedCards data={data} />
      </section>

      <section className="panel full-span">
        <PanelHeader eyebrow="model analysis" title="backbone 비교 계약과 sensitivity 분석입니다." />
        <CompactAnalysisList analyses={sectionAnalyses} groups={data.groups} />
      </section>
    </div>
  );
}

function ResultsSection({
  data,
  sectionAnalyses,
  quantileReadout
}: {
  data: DashboardData;
  sectionAnalyses: AnalysisItem[];
  quantileReadout: QuantileReadout;
}) {
  return (
    <div className="dashboard-grid two-column-grid">
      <section className="panel hero-panel">
        <PanelHeader
          eyebrow="R / results"
          title="Primary metric과 flood-tail evidence를 같은 카드 안에서 섞지 않습니다."
          actionHref="/details/primary-results-guardrail"
          actionLabel="View detail"
        />
        <QuantileBars data={data.quantiles} />
      </section>

      <section className="panel">
        <PanelHeader eyebrow="primary deltas" title="Paired seed별 metric delta입니다." />
        <SeedDeltaTable data={data} />
      </section>

      <section className="panel full-span">
        <PanelHeader
          eyebrow="Q99+ peak underestimation"
          title={`Model 1 ${quantileReadout.model1 ? formatPercent(quantileReadout.model1.underestimationFraction, 1) : "n/a"} → Model 2 q99 ${quantileReadout.q99 ? formatPercent(quantileReadout.q99.underestimationFraction, 1) : "n/a"}`}
          actionHref="/details/primary-high-flow-quantiles"
          actionLabel="View detail"
        />
        <CompactAnalysisList analyses={sectionAnalyses} groups={data.groups} />
      </section>
    </div>
  );
}

function AnalysisSection({
  data,
  filteredAnalyses,
  selectedAnalysis,
  selectedAnalysisId,
  query,
  onQueryChange,
  onSelectAnalysis
}: {
  data: DashboardData;
  filteredAnalyses: AnalysisItem[];
  selectedAnalysis?: AnalysisItem;
  selectedAnalysisId: string;
  query: string;
  onQueryChange: (value: string) => void;
  onSelectAnalysis: (analysisId: string) => void;
}) {
  return (
    <div className="dashboard-grid analysis-grid">
      <section className="panel">
        <PanelHeader
          eyebrow="A / artifact index"
          title="분석 행을 먼저 훑고 필요한 항목만 drilldown합니다."
          actionHref="/details/paper-asset-sources"
          actionLabel="View detail"
        />
        <div className="search-box compact">
          <Search size={15} />
          <input
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Evidence matrix 필터"
          />
        </div>
        <AnalysisMatrix
          data={data}
          analyses={filteredAnalyses}
          selectedAnalysisId={selectedAnalysisId}
          onSelectAnalysis={onSelectAnalysis}
        />
      </section>

      <section className="panel">
        <PanelHeader eyebrow="selected row" title={selectedAnalysis?.title ?? "분석 행을 선택하세요."} />
        {selectedAnalysis ? (
          <SelectedAnalysisCard analysis={selectedAnalysis} groups={data.groups} />
        ) : null}
      </section>
    </div>
  );
}

function StressSection({
  data,
  sectionAnalyses
}: {
  data: DashboardData;
  sectionAnalyses: AnalysisItem[];
}) {
  return (
    <div className="dashboard-grid two-column-grid">
      <section className="panel hero-panel warning-panel">
        <PanelHeader
          eyebrow="S / stress"
          title="Historical stress는 primary claim과 분리해서 읽습니다."
          actionHref="/details/stress-supplementary-check"
          actionLabel="View detail"
        />
        <MetricTiles rows={stressRows} />
        <div className="timeline-block">
          <span>boundary</span>
          <strong>DRBC basin holdout은 유지하지만 historical 1980-2024 기간입니다.</strong>
          <p>
            따라서 stress 결과는 response plausibility를 보조하는 자료이고, temporal
            independence claim의 근거로 쓰지 않습니다.
          </p>
        </div>
      </section>

      <section className="panel">
        <PanelHeader eyebrow="stress figure" title="Stress tradeoff snapshot입니다." />
        <FigureRail
          figures={data.figures.filter((figure) =>
            [figure.title, figure.caption].join(" ").toLowerCase().includes("stress")
          )}
        />
      </section>

      <section className="panel full-span">
        <PanelHeader eyebrow="stress rows" title="관련 stress diagnostic 분석입니다." />
        <CompactAnalysisList analyses={sectionAnalyses} groups={data.groups} />
      </section>
    </div>
  );
}

function PanelHeader({
  eyebrow,
  title,
  actionHref,
  actionLabel
}: {
  eyebrow: string;
  title: string;
  actionHref?: string;
  actionLabel?: string;
}) {
  return (
    <div className="panel-header">
      <div>
        <p className="mono-label">{eyebrow}</p>
        <h3>{title}</h3>
      </div>
      {actionHref && actionLabel ? (
        <Link href={actionHref} className="ghost-button">
          {actionLabel}
          <ArrowUpRight size={14} />
        </Link>
      ) : null}
    </div>
  );
}

function SectionFlow() {
  return (
    <div className="section-flow">
      {sectionNav.slice(2).map((section) => (
        <article key={section.id}>
          <span>{section.key}</span>
          <strong>{section.label}</strong>
          <small>{section.description}</small>
        </article>
      ))}
    </div>
  );
}

function SectionCards() {
  return (
    <div className="section-card-grid">
      {topNavSections.map((section) => {
        const Icon = section.icon;
        return (
          <article key={section.id} data-emphasis={section.id === "results"}>
            <span>{section.key}</span>
            <Icon size={16} />
            <strong>{section.label}</strong>
            <small>{section.title}</small>
            <i aria-hidden="true" />
            <em>{sectionRoutes[section.id]}</em>
          </article>
        );
      })}
    </div>
  );
}

function CompactAnalysisList({
  analyses,
  groups
}: {
  analyses: AnalysisItem[];
  groups: GroupSummary[];
}) {
  return (
    <div className="compact-analysis-list">
      {analyses.length === 0 ? (
        <p className="empty-state">현재 섹션에 표시할 분석 행이 없습니다.</p>
      ) : null}
      {analyses.map((analysis) => {
        const group = groups.find((item) => item.id === analysis.groupId);
        const detailSlug = analysis.detailSlug ?? group?.detailSlug;
        return (
          <article key={analysis.id} className="analysis-card-row">
            <div>
              <span>{group?.label ?? analysis.groupId}</span>
              <strong>{analysis.title}</strong>
              <p>{analysis.use}</p>
            </div>
            <dl>
              {analysis.metrics.slice(0, 3).map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
            {detailSlug ? (
              <Link href={`/details/${detailSlug}`} className="table-detail-link">
                View
                <ArrowUpRight size={12} />
              </Link>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}

function MetricTiles({ rows }: { rows: string[][] }) {
  return (
    <div className="metric-tile-grid">
      {rows.map(([label, value, detail]) => (
        <article key={label}>
          <span>{label}</span>
          <strong>{value}</strong>
          {detail ? <small>{detail}</small> : null}
        </article>
      ))}
    </div>
  );
}

function ModelContractTable() {
  return (
    <div className="contract-table">
      {modelRows.map(([name, design, role]) => (
        <article key={name}>
          <span>{name}</span>
          <strong>{design}</strong>
          <small>{role}</small>
        </article>
      ))}
    </div>
  );
}

function SeedCards({ data }: { data: DashboardData }) {
  return (
    <div className="seed-grid">
      {data.seedDeltas.map((seed) => (
        <article key={seed.seed} className="seed-card">
          <p className="mono-label">seed {seed.seed}</p>
          <h4>{formatSigned(seed.medianDeltaNse)}</h4>
          <span>median Δ NSE</span>
          <div className="mini-meter">
            <span style={{ width: clampPercent(seed.improvedFractionNse) }} />
          </div>
          <small>유역 {formatPercent(seed.improvedFractionNse)}에서 NSE 개선</small>
        </article>
      ))}
    </div>
  );
}

function SeedDeltaTable({ data }: { data: DashboardData }) {
  return (
    <div className="data-table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Seed</th>
            <th>median Δ NSE</th>
            <th>NSE 개선 비율</th>
            <th>median Δ KGE</th>
            <th>KGE 개선 비율</th>
          </tr>
        </thead>
        <tbody>
          {data.seedDeltas.map((seed) => (
            <tr key={seed.seed}>
              <td>seed {seed.seed}</td>
              <td>{formatSigned(seed.medianDeltaNse)}</td>
              <td>{formatPercent(seed.improvedFractionNse, 1)}</td>
              <td>{formatSigned(seed.medianDeltaKge)}</td>
              <td>{formatPercent(seed.improvedFractionKge, 1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Kpi({ kpi }: { kpi: KpiCard }) {
  const content = (
    <article className="kpi-card" data-tone={kpi.tone}>
      <p>{kpi.label}</p>
      <strong>{kpi.value}</strong>
      <span>{kpi.detail}</span>
      {kpi.detailSlug ? (
        <small className="detail-affordance">
          View detail
          <ArrowUpRight size={12} />
        </small>
      ) : null}
    </article>
  );

  if (!kpi.detailSlug) {
    return content;
  }

  return (
    <Link href={`/details/${kpi.detailSlug}`} className="kpi-card-link">
      {content}
    </Link>
  );
}

function QuantileBars({ data }: { data: DashboardData["quantiles"] }) {
  return (
    <div className="quantile-bars">
      {data.map((row) => (
        <div key={row.predictor} className="quantile-row" data-tone={row.tone}>
          <div className="quantile-label">
            <span>{row.predictor}</span>
            <strong>{formatPercent(row.underestimationFraction, 1)}</strong>
          </div>
          <div
            className="bar-track"
            aria-label={`${row.predictor} 과소추정 ${formatPercent(
              row.underestimationFraction,
              1
            )}`}
          >
            <span style={{ width: clampPercent(row.underestimationFraction) }} />
          </div>
          <div className="quantile-meta">
            <span>편향 {row.medianRelativeBiasPct.toFixed(1)}%</span>
            <span>MAE {row.medianAbsError.toFixed(2)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function FigureRail({ figures }: { figures: DashboardData["figures"] }) {
  return (
    <div className="figure-rail">
      {figures.length === 0 ? <p className="empty-state">표시할 figure가 없습니다.</p> : null}
      {figures.map((figure) => (
        <article key={figure.src}>
          <Image src={figure.src} alt="" width={900} height={520} sizes="360px" />
          <div>
            <strong>{figure.title}</strong>
            <p>{figure.caption}</p>
            {figure.detailSlug ? (
              <Link href={`/details/${figure.detailSlug}`} className="inline-detail-link">
                View detail
                <ArrowUpRight size={13} />
              </Link>
            ) : null}
          </div>
        </article>
      ))}
    </div>
  );
}

function SourceList({ sources }: { sources: DashboardData["sources"] }) {
  return (
    <div className="source-list">
      {sources.map((source) => (
        <a key={source.href} href={source.href}>
          <span>
            <strong>{source.label}</strong>
            <small>{source.kind}</small>
          </span>
          <ArrowUpRight size={14} />
        </a>
      ))}
    </div>
  );
}

function AnalysisMatrix({
  data,
  analyses,
  selectedAnalysisId,
  onSelectAnalysis
}: {
  data: DashboardData;
  analyses: AnalysisItem[];
  selectedAnalysisId?: string;
  onSelectAnalysis: (analysisId: string) => void;
}) {
  return (
    <div className="data-table-wrap large">
      <table className="data-table matrix-table">
        <thead>
          <tr>
            <th>분석</th>
            <th>그룹</th>
            <th>상태</th>
            <th>지표 1</th>
            <th>지표 2</th>
            <th>지표 3</th>
            <th>Detail</th>
          </tr>
        </thead>
        <tbody>
          {analyses.length === 0 ? (
            <tr>
              <td colSpan={7} className="empty-cell">
                현재 범위에 맞는 분석이 없습니다. 필터를 지우거나 전체 분석으로 전환하세요.
              </td>
            </tr>
          ) : null}
          {analyses.map((analysis) => {
            const group = data.groups.find((item) => item.id === analysis.groupId);
            const detailSlug = analysis.detailSlug ?? group?.detailSlug;
            return (
              <tr
                key={analysis.id}
                data-active={analysis.id === selectedAnalysisId}
                onClick={() => onSelectAnalysis(analysis.id)}
              >
                <td>{analysis.title}</td>
                <td>{group?.label ?? analysis.groupId}</td>
                <td>{analysis.status}</td>
                {analysis.metrics.slice(0, 3).map(([label, value]) => (
                  <td key={label}>
                    <small>{label}</small>
                    <strong>{value}</strong>
                  </td>
                ))}
                <td>
                  {detailSlug ? (
                    <Link
                      href={`/details/${detailSlug}`}
                      className="table-detail-link"
                      onClick={(event) => event.stopPropagation()}
                    >
                      View
                      <ArrowUpRight size={12} />
                    </Link>
                  ) : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function SelectedAnalysisCard({
  analysis,
  groups
}: {
  analysis: AnalysisItem;
  groups: GroupSummary[];
}) {
  const group = groups.find((item) => item.id === analysis.groupId);
  const detailSlug = analysis.detailSlug ?? group?.detailSlug;

  return (
    <article className="selected-analysis-card">
      <p className="status-chip">{analysis.status}</p>
      <h4>{analysis.title}</h4>
      <p>{analysis.purpose}</p>
      <p>{analysis.use}</p>
      <dl>
        {analysis.metrics.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <div className="tag-row">
        {analysis.tags.map((tag) => (
          <span key={tag}>{tag}</span>
        ))}
      </div>
      {detailSlug ? (
        <Link href={`/details/${detailSlug}`} className="primary-button">
          <ArrowUpRight size={14} />
          Detail
        </Link>
      ) : null}
    </article>
  );
}
