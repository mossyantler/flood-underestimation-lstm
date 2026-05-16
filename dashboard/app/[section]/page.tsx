import { notFound } from "next/navigation";
import { SLUG_TO_ID, SECTION_LABEL, SECTION_SLUG } from "@/lib/sections";
import { DashboardShell } from "@/components/dashboard-shell";
import { KpiStrip } from "@/components/kpi-card";
import { ChartCard } from "@/components/chart-card";
import { SectionTable } from "@/components/section-table";
import { CheckpointCard } from "@/components/checkpoint-card";
import {
  overviewKpis,
  resultsKpis,
  stressKpis,
  sectionIndexRows,
  checkpointRows,
} from "@/lib/dashboard-data";

interface Props {
  params: Promise<{ section: string }>;
}

export default async function SectionPage({ params }: Props) {
  const { section } = await params;
  const id = SLUG_TO_ID[section];
  if (!id) notFound();

  return (
    <DashboardShell slug={section}>
      {/* ── Header ── */}
      <div className="canvas-header">
        <div className="canvas-header-left">
          <span className="canvas-title">{SECTION_LABEL[id]}</span>
          <span className="canvas-route">/{SECTION_SLUG[id]}</span>
        </div>
        <div className="canvas-header-right">
          <button type="button" className="btn-ghost">동기화</button>
          <button type="button" className="btn-accent">내보내기</button>
        </div>
      </div>

      {/* ── 섹션별 콘텐츠 ── */}
      {id === "O" && <OverviewSection />}
      {id === "H" && <PlaceholderSection label="수문곡선" body="대표 수문곡선과 peak timing 분석 콘텐츠 예정" />}
      {id === "D" && <PlaceholderSection label="데이터셋" body="데이터셋 split provenance 및 설계 설명 예정" />}
      {id === "M" && <PlaceholderSection label="모델" body="Model 1 vs Model 2 구조 비교 및 head 설계 예정" />}
      {id === "R" && <ResultsSection />}
      {id === "A" && <PlaceholderSection label="분석" body="상세 분석 항목 및 figure 링크 예정" />}
      {id === "S" && <StressSection />}

      <div className="grid-note">Dashboard · Figma {"{"}Yww4tmRcPSQswHfeov50gH{"}"} · 개요 프로토타입</div>
    </DashboardShell>
  );
}

/* ── 개요 섹션 ─────────────────────────────────────────────── */
function OverviewSection() {
  return (
    <>
      <KpiStrip items={overviewKpis} />
      <div className="hero-row">
        <ChartCard />
        <CheckpointCard rows={checkpointRows} />
      </div>
      <SectionTable rows={sectionIndexRows} />
    </>
  );
}

/* ── 결과 섹션 ─────────────────────────────────────────────── */
function ResultsSection() {
  return (
    <>
      <KpiStrip items={resultsKpis} />
      <div className="panel">
        <div className="panel-title">Primary result summary</div>
        <p style={{ marginTop: 8, fontSize: 12, color: "var(--ink-body)", lineHeight: 1.6 }}>
          전체 성능과 flood-specific metric을 분리해서 읽습니다.
          DRBC primary test 38 유역, paired seed 111/222/444 기준.
        </p>
        <div style={{ marginTop: 16, display: "grid", gap: 8 }}>
          {[
            ["Median NSE (Model 1)", "0.70", "var(--ink-body)"],
            ["Median NSE (Model 2 q50)", "0.71", "var(--ink-body)"],
            ["q99 과소추정 (Model 1)", "72.6%", "#f7b955"],
            ["q99 과소추정 (Model 2 q99)", "44.0%", "#50e3c2"],
          ].map(([label, value, color]) => (
            <div key={label} style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--hairline)", paddingBottom: 6, fontSize: 12 }}>
              <span style={{ color: "var(--ink-body)" }}>{label}</span>
              <span style={{ fontFamily: "var(--font-geist-mono)", fontWeight: 600, color }}>{value}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

/* ── 스트레스 섹션 ───────────────────────────────────────────── */
function StressSection() {
  return (
    <>
      <KpiStrip items={stressKpis} />
      <div className="panel">
        <div className="panel-title">극한 홍수 스트레스 테스트</div>
        <p style={{ marginTop: 8, fontSize: 12, color: "var(--ink-body)", lineHeight: 1.6 }}>
          hourly Rainf에서 직접 만든 rain-event catalog로 train/validation exposure와
          DRBC historical stress response를 점검합니다.
          drbc_historical_stress는 temporal independence claim에는 사용하지 않습니다.
        </p>
      </div>
    </>
  );
}

/* ── 미구현 섹션 스켈레톤 ────────────────────────────────────── */
function PlaceholderSection({ label, body }: { label: string; body: string }) {
  return (
    <div className="panel">
      <div className="panel-title">{label}</div>
      <p style={{ marginTop: 8, fontSize: 12, color: "var(--ink-muted)", lineHeight: 1.6 }}>{body}</p>
    </div>
  );
}

export function generateStaticParams() {
  return Object.values(SECTION_SLUG).map((slug) => ({ section: slug }));
}
