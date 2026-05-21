"use client";

import Image from "next/image";
import Link from "next/link";
import type { ComponentType } from "react";
import { useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  BarChart3,
  BookOpenCheck,
  Database,
  Eye,
  Filter,
  FlaskConical,
  Gauge,
  Layers,
  LineChart,
  Sigma,
  Table2,
  Waves
} from "lucide-react";

import type {
  AnalysisItem,
  DashboardData,
  FigurePreview,
  GroupSummary,
  KpiCard,
  QuantileComparison,
  SeedDelta
} from "@/lib/dashboard-data";
import {
  dashboardSections,
  datasetLedger,
  evidenceFlow,
  hydrographQueue,
  modelContractRows,
  overviewReadout,
  stressLedger,
  type DashboardSection,
  type DashboardSectionId
} from "@/lib/dashboard-view-data";
import { clampPercent, formatPercent, formatSigned } from "@/lib/format";
import { ThemeToggle } from "./theme-toggle";

type IconComponent = ComponentType<{
  size?: number;
  strokeWidth?: number;
  className?: string;
}>;

const sectionIcons: Record<DashboardSectionId, IconComponent> = {
  overview: Gauge,
  hydrograph: Waves,
  dataset: Database,
  model: Sigma,
  results: BarChart3,
  analysis: Layers,
  stress: AlertTriangle
};

const groupIcons: Record<string, IconComponent> = {
  "data-foundation": Database,
  "overall-performance": Activity,
  "probabilistic-head": Sigma,
  "event-stress": Waves,
  "basin-robustness": Layers,
  "paper-assets": BookOpenCheck
};

export function ExperimentDashboard({ data }: { data: DashboardData }) {
  const [activeId, setActiveId] = useState<DashboardSectionId>("overview");

  const activeSection =
    dashboardSections.find((section) => section.id === activeId) ??
    dashboardSections[0];

  const groupMap = useMemo(() => {
    return new Map(data.groups.map((group) => [group.id, group]));
  }, [data.groups]);

  const analysesByGroup = useMemo(() => {
    const map = new Map<string, AnalysisItem[]>();
    for (const item of data.analyses) {
      const list = map.get(item.groupId) ?? [];
      list.push(item);
      map.set(item.groupId, list);
    }
    return map;
  }, [data.analyses]);

  const visibleGroups = useMemo(() => {
    return activeSection.groupIds.flatMap((groupId) => {
      const group = groupMap.get(groupId);
      return group ? [group] : [];
    });
  }, [activeSection.groupIds, groupMap]);

  const visibleAnalyses = useMemo(() => {
    return visibleGroups.flatMap((group) => analysesByGroup.get(group.id) ?? []);
  }, [analysesByGroup, visibleGroups]);

  return (
    <div className="dashboard-shell">
      <IconRail activeId={activeId} onSelect={setActiveId} />
      <ContextSidebar
        activeId={activeId}
        data={data}
        groups={visibleGroups}
        onSelect={setActiveId}
      />
      <main className="workbench" aria-label="CAMELS analysis dashboard">
        <DashboardHeader activeSection={activeSection} />
        <MobileScopeCard
          activeId={activeId}
          data={data}
          onSelect={setActiveId}
        />
        {activeId === "results" ? (
          <ResultsWorkbench data={data} />
        ) : activeId === "overview" ? (
          <OverviewWorkbench data={data} groups={visibleGroups} />
        ) : (
          <SectionWorkbench
            activeSection={activeSection}
            analyses={visibleAnalyses}
            data={data}
            groups={visibleGroups}
          />
        )}
      </main>
    </div>
  );
}

function IconRail({
  activeId,
  onSelect
}: {
  activeId: DashboardSectionId;
  onSelect: (section: DashboardSectionId) => void;
}) {
  return (
    <aside className="icon-rail" aria-label="Section rail">
      <div className="rail-mark">
        <FlaskConical size={22} />
      </div>
      <nav className="rail-nav">
        {dashboardSections.map((section) => {
          const Icon = sectionIcons[section.id];
          return (
            <button
              key={section.id}
              type="button"
              className="rail-button"
              data-active={section.id === activeId}
              aria-label={section.label}
              onClick={() => onSelect(section.id)}
            >
              <Icon size={17} />
              <span>{section.key}</span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}

function ContextSidebar({
  activeId,
  data,
  groups,
  onSelect
}: {
  activeId: DashboardSectionId;
  data: DashboardData;
  groups: GroupSummary[];
  onSelect: (section: DashboardSectionId) => void;
}) {
  return (
    <aside className="context-sidebar" aria-label="Dashboard context">
      <div className="brand-lockup">
        <span className="brand-tile">
          <FlaskConical size={18} />
        </span>
        <div>
          <p className="mono-label">CAMELSH / SUBSET300</p>
          <strong>CAMELS 실험 분석</strong>
        </div>
      </div>

      <section className="scope-card">
        <p className="mono-label">Desktop prototype scope</p>
        <div className="scope-metrics">
          {data.kpis.slice(0, 3).map((kpi) => (
            <div key={kpi.label} className="scope-metric">
              <span>{kpi.label.replace(" 유역", "").replace("공식 ", "")}</span>
              <strong>{kpi.value}</strong>
            </div>
          ))}
        </div>
        <p>{data.scope.model1}과 {data.scope.model2}를 같은 subset300에서 비교합니다.</p>
      </section>

      <nav className="section-list" aria-label="Dashboard sections">
        {dashboardSections.map((section) => (
          <button
            key={section.id}
            type="button"
            className="section-row"
            data-active={section.id === activeId}
            onClick={() => onSelect(section.id)}
          >
            <span className="key-pill">{section.key}</span>
            <strong>{section.label}</strong>
            <span>{section.sidebarMeta}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-divider" />

      <section className="sidebar-analysis-list">
        <div className="sidebar-heading">
          <Eye size={15} />
          <span>전체 분석</span>
        </div>
        {groups.map((group) => {
          const Icon = groupIcons[group.id] ?? Table2;
          return (
            <article key={group.id} className="sidebar-group-row">
              <Icon size={15} />
              <div>
                <strong>{group.label}</strong>
                <span>
                  {group.analysisCount} analyses / {group.figureCount} figures
                </span>
              </div>
            </article>
          );
        })}
      </section>
    </aside>
  );
}

function DashboardHeader({ activeSection }: { activeSection: DashboardSection }) {
  return (
    <header className="workbench-header">
      <div className="header-copy">
        <span className="section-chip">
          <span>{activeSection.key}</span>
          {activeSection.label}
        </span>
        <h1>{activeSection.title}</h1>
        <p>{activeSection.subtitle}</p>
      </div>
      <div className="header-actions">
        <ThemeToggle />
        <button type="button" className="icon-button" aria-label="Filter">
          <Filter size={16} />
        </button>
        <Link
          href={`/details/${activeSection.detailSlug}`}
          className="detail-button"
        >
          <ArrowUpRight size={15} />
          <span>Detail</span>
        </Link>
      </div>
    </header>
  );
}

function MobileScopeCard({
  activeId,
  data,
  onSelect
}: {
  activeId: DashboardSectionId;
  data: DashboardData;
  onSelect: (section: DashboardSectionId) => void;
}) {
  return (
    <section className="mobile-scope-card">
      <p className="mono-label">CAMELSH / SUBSET300</p>
      <h2>{data.scope.primaryQuestion}</h2>
      <div className="mobile-section-pills">
        {dashboardSections.map((section) => (
          <button
            key={section.id}
            type="button"
            data-active={section.id === activeId}
            onClick={() => onSelect(section.id)}
          >
            <span>{section.key}</span>
            {section.label}
          </button>
        ))}
      </div>
    </section>
  );
}

function OverviewWorkbench({
  data,
  groups
}: {
  data: DashboardData;
  groups: GroupSummary[];
}) {
  return (
    <div className="workbench-stack">
      <KpiGrid kpis={data.kpis} />
      <div className="overview-grid">
        <PrimaryReadout />
        <EvidenceFlowCard />
      </div>
      <div className="lower-grid">
        <GroupIndexCard groups={groups} />
        <FigureDeck figures={data.figures.slice(0, 3)} />
      </div>
    </div>
  );
}

function ResultsWorkbench({ data }: { data: DashboardData }) {
  return (
    <div className="workbench-stack">
      <KpiGrid kpis={data.kpis} />
      <div className="results-grid">
        <QuantileBars quantiles={data.quantiles} />
        <SeedDeltaTable rows={data.seedDeltas} />
      </div>
      <Q99SummaryStrip />
      <FigureDeck figures={data.figures.slice(0, 3)} />
    </div>
  );
}

function SectionWorkbench({
  activeSection,
  analyses,
  data,
  groups
}: {
  activeSection: DashboardSection;
  analyses: AnalysisItem[];
  data: DashboardData;
  groups: GroupSummary[];
}) {
  return (
    <div className="workbench-stack">
      <KpiGrid kpis={data.kpis} />
      <div className="section-grid">
        <section className="panel-card section-brief">
          <p className="mono-label">
            {activeSection.key} / {activeSection.eyebrow}
          </p>
          <h2>{activeSection.title}</h2>
          <p>{activeSection.subtitle}</p>
          <div className="section-group-strip">
            {groups.map((group) => (
              <span key={group.id}>{group.label}</span>
            ))}
          </div>
          <Link
            href={`/details/${activeSection.detailSlug}`}
            className="panel-link"
          >
            View detail
            <ArrowUpRight size={14} />
          </Link>
        </section>
        <AuxiliaryLedger sectionId={activeSection.id} />
      </div>
      <AnalysisMatrix analyses={analyses} />
      <FigureDeck figures={selectSectionFigures(activeSection.id, data.figures)} />
    </div>
  );
}

function KpiGrid({ kpis }: { kpis: KpiCard[] }) {
  return (
    <section className="kpi-grid" aria-label="Top KPIs">
      {kpis.map((kpi) => (
        <article key={kpi.label} className="kpi-card" data-tone={kpi.tone}>
          <span>{kpi.label}</span>
          <strong>{kpi.value}</strong>
          <p>{kpi.detail}</p>
          {kpi.detailSlug ? (
            <Link href={`/details/${kpi.detailSlug}`}>
              View detail
              <ArrowUpRight size={12} />
            </Link>
          ) : null}
        </article>
      ))}
    </section>
  );
}

function PrimaryReadout() {
  return (
    <section className="panel-card primary-readout">
      <div className="panel-title-row">
        <div>
          <p className="mono-label">O / Overview</p>
          <h2>{overviewReadout.title}</h2>
        </div>
        <Link href="/details/primary-high-flow-quantiles" className="panel-link">
          View detail
          <ArrowUpRight size={14} />
        </Link>
      </div>
      <div className="readout-body">
        <div className="readout-number">
          <span>{overviewReadout.eyebrow}</span>
          <strong>{overviewReadout.value}</strong>
          <em>{overviewReadout.delta}</em>
        </div>
        <ul className="readout-bullets">
          {overviewReadout.bullets.map((bullet) => (
            <li key={bullet}>{bullet}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function EvidenceFlowCard() {
  return (
    <section className="panel-card evidence-flow-card">
      <p className="mono-label">핵심 비교 흐름</p>
      <h2>Dataset → Model → Result → Analysis → Stress 순서로 읽습니다.</h2>
      <div className="flow-grid">
        {evidenceFlow.map((item) => (
          <article key={item.key} className="flow-item">
            <span className="key-pill">{item.key}</span>
            <strong>{item.title}</strong>
            <p>{item.body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function GroupIndexCard({ groups }: { groups: GroupSummary[] }) {
  return (
    <section className="panel-card">
      <p className="mono-label">섹션 인덱스</p>
      <div className="compact-list">
        {groups.map((group) => (
          <article key={group.id} className="compact-row" data-tone={group.status}>
            <div>
              <strong>{group.label}</strong>
              <span>{group.answer}</span>
            </div>
            <em>{group.analysisCount}</em>
          </article>
        ))}
      </div>
    </section>
  );
}

function QuantileBars({ quantiles }: { quantiles: QuantileComparison[] }) {
  return (
    <section className="panel-card quantile-panel">
      <div className="panel-title-row">
        <div>
          <p className="mono-label">R / Results</p>
          <h2>Primary metric과 flood-tail evidence를 같은 카드 안에서 섞지 않습니다.</h2>
        </div>
        <Link href="/details/primary-high-flow-quantiles" className="panel-link">
          View detail
          <ArrowUpRight size={14} />
        </Link>
      </div>
      <div className="quantile-list">
        {quantiles.map((item) => (
          <article key={item.predictor} className="quantile-row">
            <div>
              <strong>{item.predictor}</strong>
              <span>{formatPercent(item.underestimationFraction)}</span>
            </div>
            <span className="quantile-track" aria-hidden="true">
              <span
                className="quantile-fill"
                data-tone={item.tone}
                style={{ width: clampPercent(item.underestimationFraction) }}
              />
            </span>
            <footer>
              <span>편향 {item.medianRelativeBiasPct.toFixed(1)}%</span>
              <span>MAE {item.medianAbsError.toFixed(2)}</span>
            </footer>
          </article>
        ))}
      </div>
    </section>
  );
}

function SeedDeltaTable({ rows }: { rows: SeedDelta[] }) {
  return (
    <section className="panel-card seed-table-card">
      <p className="mono-label">Primary deltas</p>
      <h2>Paired seed별 metric delta입니다.</h2>
      <div className="table-scroll">
        <table className="metric-table">
          <thead>
            <tr>
              <th>Seed</th>
              <th>Median Δ NSE</th>
              <th>NSE 개선 비율</th>
              <th>Median Δ KGE</th>
              <th>KGE 개선 비율</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.seed}>
                <th>seed {row.seed}</th>
                <td>{formatSigned(row.medianDeltaNse)}</td>
                <td>{formatPercent(row.improvedFractionNse)}</td>
                <td>{formatSigned(row.medianDeltaKge)}</td>
                <td>{formatPercent(row.improvedFractionKge)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Q99SummaryStrip() {
  return (
    <section className="panel-card q99-strip">
      <div>
        <p className="mono-label">Q99+ peak underestimation</p>
        <h2>Model 1 72.6% → Model 2 q99 44.0%</h2>
      </div>
      <div className="strip-facts">
        <span>
          <strong>111, 222, 444</strong>
          공식 seed
        </span>
        <span>
          <strong>114</strong>
          primary delta row
        </span>
        <span>
          <strong>72</strong>
          선택 metric file
        </span>
      </div>
      <Link href="/details/primary-high-flow-quantiles" className="panel-link">
        View
        <ArrowUpRight size={14} />
      </Link>
    </section>
  );
}

function AuxiliaryLedger({ sectionId }: { sectionId: DashboardSectionId }) {
  const rows = getAuxiliaryRows(sectionId);
  return (
    <section className="panel-card ledger-card">
      <p className="mono-label">{getAuxiliaryTitle(sectionId)}</p>
      <div className="ledger-list">
        {rows.map(([label, value, note]) => (
          <article key={label} className="ledger-row">
            <span>{label}</span>
            <strong>{value}</strong>
            <em>{note}</em>
          </article>
        ))}
      </div>
    </section>
  );
}

function AnalysisMatrix({ analyses }: { analyses: AnalysisItem[] }) {
  return (
    <section className="panel-card analysis-matrix">
      <div className="panel-title-row">
        <div>
          <p className="mono-label">분석 queue</p>
          <h2>해당 섹션의 분석 단위입니다.</h2>
        </div>
        <span className="count-badge">{analyses.length}</span>
      </div>
      <div className="analysis-grid">
        {analyses.slice(0, 8).map((item) => (
          <article key={item.id} className="analysis-card">
            <div>
              <strong>{item.title}</strong>
              <span>{item.status}</span>
            </div>
            <p>{item.use}</p>
            <dl>
              {item.metrics.slice(0, 2).map(([label, value]) => (
                <div key={`${item.id}-${label}`}>
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
          </article>
        ))}
      </div>
    </section>
  );
}

function FigureDeck({ figures }: { figures: FigurePreview[] }) {
  return (
    <section className="panel-card figure-deck">
      <div className="panel-title-row">
        <div>
          <p className="mono-label">Figure previews</p>
          <h2>기존 public/figures asset을 재사용합니다.</h2>
        </div>
      </div>
      <div className="figure-grid">
        {figures.map((figure) => (
          <Link
            key={figure.src}
            href={`/details/${figure.detailSlug ?? "paper-asset-sources"}`}
            className="figure-card"
          >
            <Image
              src={figure.src}
              alt={figure.title}
              width={640}
              height={360}
              sizes="(max-width: 720px) 100vw, 33vw"
            />
            <span>
              <strong>{figure.title}</strong>
              <em>{figure.caption}</em>
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}

function getAuxiliaryRows(sectionId: DashboardSectionId) {
  if (sectionId === "dataset") {
    return datasetLedger;
  }
  if (sectionId === "model") {
    return modelContractRows;
  }
  if (sectionId === "hydrograph") {
    return hydrographQueue;
  }
  if (sectionId === "stress") {
    return stressLedger;
  }
  return [
    ["Primary", "DRBC 38", "paired seed evidence"],
    ["Tail", "q95/q99", "flood bracket"],
    ["Caveat", "calibration", "claim boundary"],
    ["Asset", "5 PNG", "preview only"]
  ] as const;
}

function getAuxiliaryTitle(sectionId: DashboardSectionId) {
  if (sectionId === "dataset") {
    return "Dataset ledger";
  }
  if (sectionId === "model") {
    return "Model contract";
  }
  if (sectionId === "hydrograph") {
    return "Hydrograph queue";
  }
  if (sectionId === "stress") {
    return "Stress ledger";
  }
  return "Evidence ledger";
}

function selectSectionFigures(
  sectionId: DashboardSectionId,
  figures: FigurePreview[]
) {
  if (sectionId === "stress") {
    return figures.filter((figure) => figure.detailSlug === "stress-supplementary-check");
  }
  if (sectionId === "analysis") {
    return figures.slice(2, 5);
  }
  if (sectionId === "hydrograph") {
    return figures.filter((figure) => figure.detailSlug === "analysis-calibration-robustness");
  }
  return figures.slice(0, 3);
}
