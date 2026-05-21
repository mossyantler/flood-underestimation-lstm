import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import {
  SECTION_ACCENT,
  SECTION_ENTRYPOINTS,
  SECTION_IDS,
  SECTION_LABEL,
  SECTION_SLUG,
  SLUG_TO_ID,
  type SectionSlug,
} from "@/lib/sections";
import { DashboardShell } from "@/components/dashboard-shell";
import { SectionHeader } from "@/components/section-header";
import {
  calibrationRows,
  datasetRows,
  eventRegimeRows,
  highFlowQ99,
  nseDeltaSummary,
  peakHourRows,
  primaryPerformance,
  stressRows,
} from "@/lib/dashboard-data";
import { confirmedFloodSnapshot } from "@/lib/confirmed-flood-data";
import { evaluationTestsSnapshot } from "@/lib/evaluation-tests-data";
import { NSE_DELTA_CSV, PEAK_HOUR_CSV, SECTION_CSV } from "@/lib/export";

interface Props { params: Promise<{ section: string; detail: string }> }

type DetailContent = {
  title: string;
  lede: string;
  panels: ReactNode;
  sourcePath: string;
  csvContent?: string;
  csvFilename?: string;
};

export function generateStaticParams() {
  return SECTION_IDS.flatMap((id) =>
    SECTION_ENTRYPOINTS[id].map((entry) => ({
      section: SECTION_SLUG[id],
      detail: entry.slug,
    }))
  );
}

export default async function DetailPage({ params }: Props) {
  const { section, detail } = await params;
  const id = SLUG_TO_ID[section as SectionSlug];
  if (!id) notFound();

  const entry = SECTION_ENTRYPOINTS[id].find((item) => item.slug === detail);
  if (!entry) notFound();

  const content = DETAIL_CONTENT[`${section}/${detail}`];
  if (!content) notFound();

  const csvInfo = SECTION_CSV[section] ?? { csv: "", filename: "data.csv" };

  return (
    <DashboardShell slug={section} activeEntrySlug={detail}>
      <SectionHeader
        title={content.title}
        route={`/${section}/${detail}`}
        csvContent={content.csvContent ?? csvInfo.csv}
        csvFilename={content.csvFilename ?? csvInfo.filename}
      />

      <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, color: "var(--ink-muted)" }}>
        <Link href={`/${section}`} style={{ color: SECTION_ACCENT[id], fontFamily: "var(--font-geist-mono)", fontSize: 10 }}>
          ← {SECTION_LABEL[id]}
        </Link>
        <span>/</span>
        <span style={{ fontFamily: "var(--font-geist-mono)", fontSize: 10 }}>{entry.label}</span>
      </div>

      <p className="section-lede">{content.lede}</p>

      <div className="panel-grid">
        {content.panels}
      </div>

      <div className="grid-note">
        {content.sourcePath}
      </div>
    </DashboardShell>
  );
}

function median(values: readonly number[]) {
  return [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)] ?? 0;
}

function Panel({
  kicker,
  title,
  children,
}: {
  kicker: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="panel research-panel">
      <div className="panel-sub">{kicker}</div>
      <div className="panel-title">{title}</div>
      {children}
    </section>
  );
}

function Source({ children }: { children: ReactNode }) {
  return <div className="source-path">{children}</div>;
}

function TestMatrixPanel() {
  return (
    <>
      {evaluationTestsSnapshot.tests.map((test) => (
        <Panel key={test.id} kicker={test.basis} title={test.label}>
          <div className="fact-grid">
            <div className="fact-row"><span className="fact-label">status</span><strong>{test.status}</strong><span>{test.coverage}</span></div>
            <div className="fact-row"><span className="fact-label">runner</span><strong>{test.runner.split("/").at(-1)}</strong><span>{test.primarySource}</span></div>
          </div>
          <p className="panel-body">{test.interpretation}</p>
          <Link href={test.route} className="panel-detail-link">module 보기</Link>
        </Panel>
      ))}
    </>
  );
}

function ModelDeltaTable() {
  return (
    <div className="data-block">
      <table className="data-table">
        <thead>
          <tr><th>Seed</th><th style={{ textAlign: "right" }}>Delta NSE</th><th style={{ textAlign: "right" }}>Improved</th><th style={{ textAlign: "right" }}>Delta KGE</th></tr>
        </thead>
        <tbody>
          {nseDeltaSummary.map((row) => (
            <tr key={row.seed}>
              <td>{row.seed}</td>
              <td style={{ textAlign: "right", fontFamily: "var(--font-geist-mono)", color: "#50e3c2" }}>+{row.nseDelta.toFixed(3)}</td>
              <td style={{ textAlign: "right", fontFamily: "var(--font-geist-mono)" }}>{(row.nseImproved * 100).toFixed(0)}%</td>
              <td style={{ textAlign: "right", fontFamily: "var(--font-geist-mono)" }}>{row.kgeDelta >= 0 ? "+" : ""}{row.kgeDelta.toFixed(3)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PredictorTable({ rows }: { rows: typeof highFlowQ99 }) {
  return (
    <div className="data-block">
      <table className="data-table">
        <thead>
          <tr><th>Predictor</th><th style={{ textAlign: "right" }}>111</th><th style={{ textAlign: "right" }}>222</th><th style={{ textAlign: "right" }}>444</th><th style={{ textAlign: "right" }}>Median</th></tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.predictor}>
              <td style={{ fontWeight: row.predictor === "Model 1" ? 700 : 500, color: row.predictor === "M2 q99" ? "#6bb4ff" : "var(--ink-body)" }}>{row.predictor}</td>
              {row.undestFrac.map((value, index) => (
                <td key={index} style={{ textAlign: "right", fontFamily: "var(--font-geist-mono)" }}>{value.toFixed(1)}%</td>
              ))}
              <td style={{ textAlign: "right", fontFamily: "var(--font-geist-mono)", color: row.predictor === "M2 q99" ? "#50e3c2" : "var(--ink)" }}>{median(row.undestFrac).toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DatasetTable() {
  return (
    <div className="data-block">
      <table className="data-table">
        <thead>
          <tr><th>Split</th><th style={{ textAlign: "right" }}>Basins</th><th>Role</th></tr>
        </thead>
        <tbody>
          {datasetRows.map((row) => (
            <tr key={row.split}>
              <td>{row.split}</td>
              <td style={{ textAlign: "right", fontFamily: "var(--font-geist-mono)" }}>{row.basins.toLocaleString()}</td>
              <td>{row.role}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const confirmedSummary = confirmedFloodSnapshot.summary;

const DETAIL_CONTENT: Record<string, DetailContent> = {
  "overview/status": {
    title: "Overview status",
    lede: "프로젝트 진행 상태를 완료, 진행중, 준비중, rerun 필요로 나눠 본다. 상태 자체가 결론이 아니라 다음 분석 행동을 정하는 queue다.",
    sourcePath: "dashboard/lib/overview-data.ts · dashboard/lib/evaluation-tests-data.ts",
    panels: (
      <>
        <Panel kicker="Current state" title="공식 비교축은 고정, 일부 test는 rerun 필요">
          <div className="fact-grid">
            <div className="fact-row"><span className="fact-label">top-level IA</span><strong>5 sections</strong><span>O/E/F/A/R</span></div>
            <div className="fact-row"><span className="fact-label">paired seeds</span><strong>111/222/444</strong><span>seed 333 제외</span></div>
            <div className="fact-row"><span className="fact-label">confirmed flood</span><strong>{confirmedSummary.events}</strong><span>NWS flood-stage events</span></div>
          </div>
        </Panel>
        <TestMatrixPanel />
      </>
    ),
  },
  "overview/roadmap": {
    title: "Analysis roadmap",
    lede: "논문 목적은 output design 변경만으로 extreme flood peak underestimation이 줄어드는지 확인하는 것이다. Roadmap은 그 claim에 직접 필요한 증거와 보조 진단을 분리한다.",
    sourcePath: "docs/superpowers/specs/2026-05-21-camels-dashboard-ia-redesign.md",
    panels: (
      <>
        <Panel kicker="Primary claim" title="Model 1 vs Model 2">
          <p className="panel-body">먼저 paired seed 기준 Model 1 deterministic과 Model 2 quantile head를 비교한다. DRBC test 성능으로 checkpoint를 다시 고르지 않는다.</p>
          <Link href="/experiment/comparison" className="panel-detail-link">comparison 보기</Link>
        </Panel>
        <Panel kicker="Evidence path" title="headline → chart → event evidence">
          <p className="panel-body">Overview는 상태와 headline을 보여주고, Analysis는 Q99 exceedance, hydrograph, stress, confirmed flood로 내려간다.</p>
          <Link href="/analysis/main-result" className="panel-detail-link">main result 보기</Link>
        </Panel>
      </>
    ),
  },
  "overview/quick-results": {
    title: "Quick results",
    lede: "현재 dashboard에서 바로 확인할 수 있는 핵심 결과만 빠르게 묶는다. 공식 문장으로 쓰기 전에는 각 module의 source artifact를 다시 확인한다.",
    sourcePath: "output/model_analysis/overall_analysis/main_comparison/",
    panels: (
      <>
        <Panel kicker="Q99 exceedance" title="Quantile 과소추정률 seed median">
          <PredictorTable rows={highFlowQ99} />
        </Panel>
        <Panel kicker="Confirmed flood" title="NWS flood-stage event layer">
          <div className="fact-grid">
            <div className="fact-row"><span className="fact-label">events</span><strong>{confirmedSummary.events}</strong><span>{confirmedSummary.basins} basins</span></div>
            <div className="fact-row"><span className="fact-label">M1 under-rate</span><strong>{confirmedSummary.m1UnderRate}%</strong><span>event median layer</span></div>
            <div className="fact-row"><span className="fact-label">q99 under-rate</span><strong>{confirmedSummary.q99UnderRate}%</strong><span>reduced but not gone</span></div>
          </div>
        </Panel>
      </>
    ),
  },
  "overview/next-actions": {
    title: "Next actions",
    lede: "다음 행동은 새 그래프를 더 만드는 것이 아니라, 어떤 결과가 official claim에 올라갈 수 있는지 상태를 정리하는 것이다.",
    sourcePath: "dashboard/lib/evaluation-tests-data.ts",
    panels: <TestMatrixPanel />,
  },
  "experiment/comparison": {
    title: "Official comparison",
    lede: "공식 비교는 Model 1 deterministic multi-basin LSTM과 Model 2 probabilistic quantile head다. Backbone 차이가 아니라 output design 차이를 보는 구조다.",
    sourcePath: "docs/experiment/method/model/architecture.md",
    csvContent: NSE_DELTA_CSV,
    csvFilename: "camels_model_delta.csv",
    panels: (
      <>
        <Panel kicker="Paired delta" title="Model 2 q50 - Model 1">
          <ModelDeltaTable />
        </Panel>
        <Panel kicker="Boundary" title="Model 3는 current official comparison 밖">
          <p className="panel-body">Physics-guided core는 후속 확장이다. 현재 dashboard의 공식 실험 도움 구조에서는 Model 1/2 claim과 섞지 않는다.</p>
        </Panel>
      </>
    ),
  },
  "experiment/split-policy": {
    title: "Split policy",
    lede: "Split policy는 DRBC holdout, subset300, expanded basin universe가 서로 어떤 역할인지 분리한다.",
    sourcePath: "configs/basin_splits/ · basins/drbc_boundary/drb_bnd_polygon.shp",
    panels: (
      <>
        <Panel kicker="Basin split" title="Dataset row count">
          <DatasetTable />
        </Panel>
        <Panel kicker="Guardrail" title="Pilot selection rule">
          <p className="panel-body">Scaling pilot basin 수는 non-DRBC validation 성능, attribute distribution, observed-flow diagnostics, random benchmark, compute cost로 결정한다. DRBC holdout metric으로 pilot 크기를 고르지 않는다.</p>
        </Panel>
      </>
    ),
  },
  "experiment/seed-checkpoint": {
    title: "Seed & checkpoint",
    lede: "Seed와 checkpoint는 실험 공정성의 핵심이다. 완료된 paired seed만 공식 aggregate에 올리고, primary epoch는 validation 기준으로 고른다.",
    sourcePath: "output/model_analysis/overall_analysis/main_comparison/tables/primary_epoch_summary.csv",
    panels: (
      <>
        <Panel kicker="Primary epochs" title="Model / seed checkpoint trace">
          <div className="data-block">
            <table className="data-table">
              <thead><tr><th>Model</th><th>Seed</th><th style={{ textAlign: "right" }}>Epoch</th><th style={{ textAlign: "right" }}>NSE</th><th style={{ textAlign: "right" }}>KGE</th></tr></thead>
              <tbody>
                {primaryPerformance.map((row) => (
                  <tr key={`${row.model}-${row.seed}`}><td>{row.model}</td><td>{row.seed}</td><td style={{ textAlign: "right" }}>{row.epoch}</td><td style={{ textAlign: "right" }}>{row.nse.toFixed(3)}</td><td style={{ textAlign: "right" }}>{row.kge.toFixed(3)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
        <Panel kicker="Excluded" title="Seed 333">
          <p className="panel-body">Model 2 seed 333은 NaN loss로 중단됐기 때문에, 공정한 paired-seed 비교를 위해 완료된 Model 1 seed 333도 final aggregate에서 제외한다.</p>
        </Panel>
      </>
    ),
  },
  "experiment/test-matrix": {
    title: "Test matrix",
    lede: "First, extreme, confirmed flood test는 같은 목적의 반복이 아니다. 각각 basin universe, event source, claim 가능 범위가 다르다.",
    sourcePath: "dashboard/lib/evaluation-tests-data.ts",
    panels: <TestMatrixPanel />,
  },
  "experiment/workflow": {
    title: "Workflow",
    lede: "Workflow detail은 split, train, inference, analysis, dashboard export의 재현 경로를 보여준다.",
    sourcePath: "scripts/runs/official/ · scripts/model/",
    panels: (
      <>
        <Panel kicker="01 split" title="Basin universe 고정">
          <p className="panel-body"><code>configs/basin_splits/</code>가 공식 split source다. Dashboard는 이 설정을 대체하지 않는다.</p>
        </Panel>
        <Panel kicker="02 export" title="Dashboard snapshot 생성">
          <p className="panel-body">반복 조회가 필요한 결과는 generated TypeScript snapshot으로 export한다. 값 변경은 generator와 원본 artifact를 먼저 고친다.</p>
          <Source>scripts/model/overall/export_evaluation_tests_dashboard_snapshot.py</Source>
        </Panel>
      </>
    ),
  },
  "foundation/dataset": {
    title: "Dataset",
    lede: "Dataset detail은 CAMELSH 원천, model input, raw result, analysis data를 섞지 않도록 경계를 잡는다.",
    sourcePath: "basins/ · data/CAMELSH_generic/ · output/model_analysis/",
    panels: (
      <>
        <Panel kicker="Input" title="CAMELSH hourly">
          <p className="panel-body">Dynamic forcing과 static attributes를 NeuralHydrology generic format으로 준비한다. Prepared data는 재생성 가능한 산출물이다.</p>
        </Panel>
        <Panel kicker="Split" title="현재 dashboard split snapshot">
          <DatasetTable />
        </Panel>
      </>
    ),
  },
  "foundation/model": {
    title: "Model",
    lede: "Model detail은 LSTM backbone, Model 1/2 head 차이, loss와 hyperparameter 해석을 위한 진입점이다.",
    sourcePath: "configs/ · docs/experiment/method/model/",
    panels: (
      <>
        <Panel kicker="Architecture" title="동일 backbone, 다른 output head">
          <p className="panel-body">Model 1은 deterministic point output, Model 2는 q50/q90/q95/q99 quantile head다. 핵심 질문은 head 변경만으로 peak bias가 줄어드는지다.</p>
        </Panel>
        <Panel kicker="Result guardrail" title="Paired-seed delta">
          <ModelDeltaTable />
        </Panel>
      </>
    ),
  },
  "foundation/basin": {
    title: "Basin",
    lede: "Basin detail은 DRBC holdout, non-DRBC training pool, expanded basin universe, attribute sorting의 해석 기준을 둔다.",
    sourcePath: "basins/drbc_boundary/ · output/basin/drbc/analysis/",
    panels: (
      <>
        <Panel kicker="DRBC boundary" title="Official region 기준">
          <p className="panel-body">공식 기준 레이어는 <code>basins/drbc_boundary/drb_bnd_polygon.shp</code>다. Outlet와 polygon overlap 기준을 혼동하지 않는다.</p>
        </Panel>
        <Panel kicker="Attribute analysis" title="후속 sorting surface">
          <p className="panel-body">Attribute별 sorting은 Analysis의 attribute module에서 이어진다. Basin 설명은 source와 universe 경계를 고정하는 역할이다.</p>
          <Link href="/analysis/attribute" className="panel-detail-link">attribute module 보기</Link>
        </Panel>
      </>
    ),
  },
  "analysis/main-result": {
    title: "Main result",
    lede: "Main result는 Q99 exceedance와 observed peak hour에서 upper quantile이 deterministic peak underestimation을 줄이는지 본다.",
    sourcePath: "output/model_analysis/overall_analysis/main_comparison/",
    csvContent: SECTION_CSV.results.csv,
    csvFilename: "camels_analysis_main_result.csv",
    panels: (
      <>
        <Panel kicker="Q99 exceedance" title="Quantile 과소추정률">
          <PredictorTable rows={highFlowQ99} />
        </Panel>
        <Panel kicker="Observed peak hour" title="Peak hour 과소추정률">
          <PredictorTable rows={peakHourRows} />
        </Panel>
      </>
    ),
  },
  "analysis/hydrograph": {
    title: "Hydrograph",
    lede: "Hydrograph detail은 기존 HTML gallery 구조를 따라 basin/event/predictor evidence로 내려가는 진입점이다.",
    sourcePath: "output/model_analysis/extreme_rain/primary/observed_q99_hydrograph_gallery_index.html",
    panels: (
      <>
        <Panel kicker="Gallery" title="Representative hydrograph evidence">
          <p className="panel-body">Top-level chart에서 이상한 basin이나 event를 발견하면 이 detail에서 gallery와 manifest로 내려간다.</p>
          <Source>observed_q99_hydrograph_gallery_index.html</Source>
        </Panel>
        <Panel kicker="Peak zone" title="Peak가 quantile band 어디에 있는가">
          <p className="panel-body">Observed peak hour의 q99 초과, q50 이하 비율은 peak magnitude 해석의 핵심 보조 증거다.</p>
          <Source>{PEAK_HOUR_CSV.split("\n")[0]}</Source>
        </Panel>
      </>
    ),
  },
  "analysis/stress": {
    title: "Stress test",
    lede: "Stress test는 historical extreme-rain response를 보는 supporting diagnostic이다. Temporal independence claim의 primary test로 쓰지 않는다.",
    sourcePath: "output/model_analysis/extreme_rain/primary/",
    panels: (
      <>
        <Panel kicker="Cohort" title="Historical stress under-deficit">
          <div className="data-block">
            <table className="data-table">
              <thead><tr><th>Cohort</th><th style={{ textAlign: "right" }}>M1</th><th style={{ textAlign: "right" }}>q99</th><th>Note</th></tr></thead>
              <tbody>{stressRows.map((row) => <tr key={row.cohort}><td>{row.cohort}</td><td style={{ textAlign: "right" }}>{row.m1UnderDeficit.toFixed(1)}%</td><td style={{ textAlign: "right" }}>{row.q99UnderDeficit.toFixed(1)}%</td><td>{row.note}</td></tr>)}</tbody>
            </table>
          </div>
        </Panel>
        <Panel kicker="Rerun state" title="Expanded basin universe 필요">
          <p className="panel-body">현재 stress table은 기존 primary/all 계열이다. Expanded basin universe로 stress catalog와 inference를 다시 만든 뒤 official value로 승격한다.</p>
        </Panel>
      </>
    ),
  },
  "analysis/confirmed-flood": {
    title: "Confirmed flood",
    lede: "Confirmed flood detail은 NWS flood-stage 초과 event만 대상으로 event audit과 hydrograph evidence를 본다.",
    sourcePath: "output/model_analysis/confirmed_flood/",
    csvContent: SECTION_CSV["confirmed-flood"].csv,
    csvFilename: SECTION_CSV["confirmed-flood"].filename,
    panels: (
      <>
        <Panel kicker="NWS flood-stage layer" title="Confirmed event snapshot">
          <div className="fact-grid">
            <div className="fact-row"><span className="fact-label">events</span><strong>{confirmedSummary.events}</strong><span>{confirmedSummary.basins} basins</span></div>
            <div className="fact-row"><span className="fact-label">NOAA matched</span><strong>{confirmedSummary.noaaRate}%</strong><span>{confirmedSummary.noaaEvents} events</span></div>
            <div className="fact-row"><span className="fact-label">median reduction</span><strong>{confirmedSummary.medianQ99Reduction}</strong><span>peak under-deficit</span></div>
          </div>
        </Panel>
        <Panel kicker="Interpretation" title="First/extreme와 다른 test layer">
          <p className="panel-body">Confirmed flood는 flood-stage threshold 기준의 event audit이다. First/extreme rerun 상태와 섞지 않고 Analysis 안의 독립 module로 해석한다.</p>
        </Panel>
      </>
    ),
  },
  "analysis/event-regime": {
    title: "Event regime",
    lede: "Event-regime detail은 570개 high-flow event를 regime으로 나눠 q99 effect가 어떤 조건에서 강한지 본다.",
    sourcePath: "event_regime_paired_delta_compact.csv",
    panels: (
      <Panel kicker="Regime delta" title="q99 paired delta">
        <div className="data-block">
          <table className="data-table">
            <thead><tr><th>Regime</th><th style={{ textAlign: "right" }}>Events</th><th style={{ textAlign: "right" }}>Under-deficit reduction</th><th style={{ textAlign: "right" }}>Recall delta</th></tr></thead>
            <tbody>{eventRegimeRows.map((row) => <tr key={row.regime}><td>{row.regime}</td><td style={{ textAlign: "right" }}>{row.nEvents}</td><td style={{ textAlign: "right" }}>+{row.q99UnderDeficitReduction.toFixed(1)}%p</td><td style={{ textAlign: "right" }}>+{row.q99RecallDelta.toFixed(3)}</td></tr>)}</tbody>
          </table>
        </div>
      </Panel>
    ),
  },
  "analysis/attribute": {
    title: "Attribute analysis",
    lede: "Attribute detail은 basin별 static attribute로 model effect와 failure mode를 sorting하기 위한 planned surface다.",
    sourcePath: "output/model_analysis/overall_analysis/main_comparison/drbc_attribute_metric_correlations/",
    panels: (
      <>
        <Panel kicker="Planned" title="Basin attribute sorting">
          <p className="panel-body">Snow fraction, aridity, slope, soil depth, permeability, forest fraction, baseflow index 기준으로 model delta를 정렬한다.</p>
        </Panel>
        <Panel kicker="Boundary" title="Aggregate summary만으로 끝내지 않기">
          <p className="panel-body">개별 basin의 hydrograph evidence와 연결되어야 한다. Attribute는 원인 단정이 아니라 failure mode 탐색 축이다.</p>
        </Panel>
      </>
    ),
  },
  "analysis/calibration": {
    title: "Calibration",
    lede: "Calibration detail은 q99가 peak bias 완화에는 유용해도 calibrated 99% interval이라는 뜻은 아님을 분리한다.",
    sourcePath: "output/model_analysis/probabilistic_diagnostics/",
    panels: (
      <Panel kicker="Quantile diagnostics" title="Coverage / pinball">
        <div className="data-block">
          <table className="data-table">
            <thead><tr><th>Quantile</th><th style={{ textAlign: "right" }}>Nominal</th><th style={{ textAlign: "right" }}>All-hour coverage</th><th style={{ textAlign: "right" }}>Q99 tail hit-rate</th><th style={{ textAlign: "right" }}>Pinball</th></tr></thead>
            <tbody>{calibrationRows.map((row) => <tr key={row.quantile}><td>{row.quantile}</td><td style={{ textAlign: "right" }}>{row.nominalTau.toFixed(2)}</td><td style={{ textAlign: "right" }}>{row.allHourCoverage.toFixed(3)}</td><td style={{ textAlign: "right" }}>{row.q99ExceedanceCoverage.toFixed(3)}</td><td style={{ textAlign: "right" }}>{row.pinball.toFixed(3)}</td></tr>)}</tbody>
          </table>
        </div>
      </Panel>
    ),
  },
  "reference/experiment": referenceDetail("Experiment references", "PUB/PUR, regional holdout, split fairness 문헌과 내부 method 문서를 연결한다.", "PUB/PUR · DRBC holdout fairness"),
  "reference/dataset": referenceDetail("Dataset references", "CAMELS, CAMELSH, forcing, static attribute 정의 문헌을 연결한다.", "CAMELS/CAMELSH · forcing · basin attributes"),
  "reference/model": referenceDetail("Model references", "LSTM hydrology, quantile regression, pinball loss, calibration caveat 근거를 연결한다.", "LSTM · quantile regression · pinball loss"),
  "reference/basin": referenceDetail("Basin references", "DRBC boundary, flood-stage threshold, hydrologic controls 관련 근거를 연결한다.", "DRBC · flood-stage · hydrologic controls"),
  "reference/analysis": referenceDetail("Analysis references", "Flood typing, event regime, SHAP, stress-test limitation 문헌을 연결한다.", "flood typing · event regime · stress limitation"),
};

function referenceDetail(title: string, lede: string, focus: string): DetailContent {
  return {
    title,
    lede,
    sourcePath: "docs/references/",
    panels: (
      <>
        <Panel kicker="Reference scope" title={focus}>
          <p className="panel-body">Reference page는 official result table이 아니다. 해당 section에서 쓰는 개념의 외부 근거와 내부 문서 위치를 연결한다.</p>
          <Source>docs/references/</Source>
        </Panel>
        <Panel kicker="Next curation" title="업데이트 방식">
          <p className="panel-body">문헌을 추가할 때는 관련 dashboard section, input/process/output, limitation을 함께 적어야 나중에 claim 근거로 재사용할 수 있다.</p>
        </Panel>
      </>
    ),
  };
}
