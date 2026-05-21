import { notFound } from "next/navigation";
import { SLUG_TO_ID, SECTION_LABEL, SECTION_SLUG, type SectionSlug } from "@/lib/sections";
import { DashboardShell } from "@/components/dashboard-shell";
import { SectionHeader } from "@/components/section-header";
import { StatusBoard } from "@/components/status-board";
import { WorkflowPanel } from "@/components/workflow-panel";
import { FoundationTabs } from "@/components/foundation-tabs";
import { AnalysisModuleIndex } from "@/components/analysis-module-index";
import { ReferenceMap } from "@/components/reference-map";
import { EvidenceBlock } from "@/components/evidence-block";
import { SECTION_CSV } from "@/lib/export";
import { getCopyForModule, getEvidenceForModule } from "@/lib/evidence-catalog";

interface Props { params: Promise<{ section: string }> }

export default async function SectionPage({ params }: Props) {
  const { section } = await params;
  const id = SLUG_TO_ID[section as SectionSlug];
  if (!id) notFound();

  const csvInfo = SECTION_CSV[section] ?? { csv: "", filename: "data.csv" };

  return (
    <DashboardShell slug={section}>
      <SectionHeader
        title={SECTION_LABEL[id]}
        route={`/${SECTION_SLUG[id]}`}
        csvContent={csvInfo.csv}
        csvFilename={csvInfo.filename}
      />

      {id === "O" && <OverviewSection />}
      {id === "E" && <WorkflowPanel />}
      {id === "F" && <FoundationTabs />}
      {id === "A" && <AnalysisModuleIndex />}
      {id === "R" && <ReferenceMap />}

      <div className="grid-note">
        CAMELS Dashboard · DRBC holdout · subset300 · seed 111/222/444
      </div>
    </DashboardShell>
  );
}

function OverviewSection() {
  const copy = getCopyForModule("overview/status");
  const evidence = getEvidenceForModule("overview/status");

  return (
    <>
      <p className="section-lede">
        CAMELS dashboard는 연구 claim의 상태와 근거를 관리하고, headline indicator에서 raw hydrologic evidence까지 내려가는 실험 검토 workbench다.
      </p>
      <StatusBoard />
      {copy && <EvidenceBlock copy={copy} items={evidence} />}
    </>
  );
}

export function generateStaticParams() {
  return Object.values(SECTION_SLUG).map((slug) => ({ section: slug }));
}
