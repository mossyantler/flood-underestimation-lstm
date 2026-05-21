import Link from "next/link";
import { notFound } from "next/navigation";
import { SLUG_TO_ID, SECTION_LABEL, SECTION_ACCENT, type SectionSlug } from "@/lib/sections";
import { DashboardShell } from "@/components/dashboard-shell";
import { SectionHeader } from "@/components/section-header";
import {
  primaryPerformance, nseDeltaSummary,
  highFlowQ99, peakHourRows,
  eventRegimeRows, calibrationRows,
  stressRows, datasetRows,
} from "@/lib/dashboard-data";
import { evaluationTestsSnapshot } from "@/lib/evaluation-tests-data";
import { SECTION_CSV, NSE_DELTA_CSV, PEAK_HOUR_CSV } from "@/lib/export";

interface Props { params: Promise<{ section: string; detail: string }> }

// 전체 static params (section + detail 조합)
export function generateStaticParams() {
  return [
    { section: "overview",    detail: "status" },
    { section: "overview",    detail: "roadmap" },
    { section: "overview",    detail: "quick-results" },
    { section: "overview",    detail: "next-actions" },
    { section: "experiment",  detail: "comparison" },
    { section: "experiment",  detail: "split-policy" },
    { section: "experiment",  detail: "seed-checkpoint" },
    { section: "experiment",  detail: "test-matrix" },
    { section: "experiment",  detail: "workflow" },
    { section: "foundation",  detail: "dataset" },
    { section: "foundation",  detail: "model" },
    { section: "foundation",  detail: "basin" },
    { section: "analysis",    detail: "main-result" },
    { section: "analysis",    detail: "hydrograph" },
    { section: "analysis",    detail: "stress" },
    { section: "analysis",    detail: "confirmed-flood" },
    { section: "analysis",    detail: "event-regime" },
    { section: "analysis",    detail: "attribute" },
    { section: "analysis",    detail: "calibration" },
    { section: "reference",   detail: "experiment" },
    { section: "reference",   detail: "dataset" },
    { section: "reference",   detail: "model" },
    { section: "reference",   detail: "basin" },
    { section: "reference",   detail: "analysis" },
  ];
}

export default async function DetailPage({ params }: Props) {
  const { section, detail } = await params;
  const id = SLUG_TO_ID[section as SectionSlug];
  if (!id) notFound();

  const accent = SECTION_ACCENT[id];
  const sectionLabel = SECTION_LABEL[id];
  const csvInfo = SECTION_CSV[section] ?? { csv: "", filename: "data.csv" };

  const content = getDetailContent(section, detail);
  if (!content) notFound();

  return (
    <DashboardShell slug={section} activeEntrySlug={detail}>
      <SectionHeader
        title={content.title}
        route={`/${section}/${detail}`}
        csvContent={content.csvContent ?? csvInfo.csv}
        csvFilename={content.csvFilename ?? csvInfo.filename}
      />

      {/* breadcrumb */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, color: "var(--ink-muted)" }}>
        <Link href={`/${section}`} style={{ color: accent, fontFamily: "var(--font-geist-mono)", fontSize: 10 }}>
          ← {sectionLabel}
        </Link>
        <span>/</span>
        <span style={{ fontFamily: "var(--font-geist-mono)", fontSize: 10 }}>{detail}</span>
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

// ── 각 detail 콘텐츠 정의 ─────────────────────────────────────────

interface DetailContent {
  title: string;
  lede: string;
  panels: React.ReactNode;
  sourcePath: string;
  csvContent?: string;
  csvFilename?: string;
}

function simpleDetail(title: string, lede: string, sourcePath: string): DetailContent {
  return {
    title,
    lede,
    sourcePath,
    panels: (
      <section className="panel research-panel">
        <div className="panel-sub">Detail page</div>
        <div className="panel-title">{title}</div>
        <p className="panel-body">{lede}</p>
        <div className="source-path">{sourcePath}</div>
      </section>
    ),
  };
}

function getDetailContent(section: string, detail: string): DetailContent | null {
  const key = `${section}/${detail}`;

  switch (key) {
    case "overview/status":
      return simpleDetail("Overview status", "프로젝트 진행 상태, 완료/진행중/준비중/rerun 필요 항목을 한 곳에서 본다.", "dashboard/lib/evaluation-tests-data.ts");
    case "overview/roadmap":
      return simpleDetail("Analysis roadmap", "논문 목적을 위해 어떤 분석을 먼저 확인해야 하는지 roadmap으로 정리한다.", "docs/superpowers/specs/2026-05-21-camels-dashboard-ia-redesign.md");
    case "overview/quick-results":
      return simpleDetail("Quick results", "현재 claim에 쓸 수 있는 간단한 결과와 caveat를 빠르게 확인한다.", "output/model_analysis/overall_analysis/main_comparison/");
    case "overview/next-actions":
      return simpleDetail("Next actions", "expanded rerun과 후속 검증 queue를 관리한다.", "dashboard/lib/evaluation-tests-data.ts");
    case "experiment/comparison":
      return simpleDetail("Official comparison", "Model 1 deterministic LSTM과 Model 2 quantile head 비교축을 고정한다.", "docs/experiment/method/model/architecture.md");
    case "experiment/split-policy":
      return simpleDetail("Split policy", "subset300, DRBC holdout, expanded basin universe의 경계를 설명한다.", "configs/basin_splits/");
    case "experiment/seed-checkpoint":
      return simpleDetail("Seed & checkpoint", "paired seed와 primary epoch 선택 기준을 설명한다.", "output/model_analysis/overall_analysis/main_comparison/tables/primary_epoch_summary.csv");
    case "experiment/test-matrix":
      return simpleDetail("Test matrix", "first, extreme, confirmed flood test의 준비 상태와 rerun 필요 여부를 본다.", "dashboard/lib/evaluation-tests-data.ts");
    case "experiment/workflow":
      return simpleDetail("Workflow", "split, train, inference, analysis로 이어지는 재현 workflow와 command를 정리한다.", "scripts/model/");
    case "foundation/dataset":
      return simpleDetail("Dataset", "input data, result data, analysis data를 분리해 source와 성격을 설명한다.", "basins/ · data/ · output/model_analysis/");
    case "foundation/model":
      return simpleDetail("Model", "LSTM 구조, Model 1/2 head 차이, loss function, hyperparameter를 설명한다.", "configs/ · docs/experiment/method/model/");
    case "foundation/basin":
      return simpleDetail("Basin", "DRBC holdout, training pool, expanded universe, basin attributes를 설명한다.", "basins/drbc_boundary/ · output/basin/drbc/analysis/");
    case "analysis/main-result":
      return simpleDetail("Main result", "Q99 exceedance와 observed peak hour에서 Model 2 q99가 peak underestimation을 줄였는지 검토한다.", "output/model_analysis/overall_analysis/main_comparison/");
    case "analysis/hydrograph":
      return simpleDetail("Hydrograph", "기존 hydrograph gallery 구조로 basin/event/predictor별 visual evidence를 본다.", "output/model_analysis/extreme_rain/primary/observed_q99_hydrograph_gallery_index.html");
    case "analysis/stress":
      return simpleDetail("Stress test", "Historical stress에서 benefit과 false-positive tradeoff를 보조 분석으로 점검한다.", "output/model_analysis/extreme_rain/primary/");
    case "analysis/confirmed-flood":
      return simpleDetail("Confirmed flood", "NWS flood-stage event layer를 기준으로 event audit과 hydrograph evidence를 본다.", "output/model_analysis/confirmed_flood/");
    case "analysis/attribute":
      return simpleDetail("Attribute analysis", "Basin attribute별로 model effect와 failure mode를 sorting한다.", "output/model_analysis/overall_analysis/main_comparison/drbc_attribute_metric_correlations/");
    case "reference/experiment":
      return simpleDetail("Experiment references", "PUB/PUR, split, fairness 관련 선행연구를 묶는다.", "docs/references/");
    case "reference/dataset":
      return simpleDetail("Dataset references", "CAMELS, CAMELSH, forcing, basin attribute 관련 문헌을 묶는다.", "docs/references/");
    case "reference/model":
      return simpleDetail("Model references", "LSTM hydrology, quantile regression, pinball loss 문헌을 묶는다.", "docs/references/");
    case "reference/basin":
      return simpleDetail("Basin references", "DRBC, flood hydrology, hydromodification 관련 문헌을 묶는다.", "docs/references/");
    case "reference/analysis":
      return simpleDetail("Analysis references", "flood typing, event regime, SHAP, stress testing 관련 문헌을 묶는다.", "docs/references/");

    /* ── overview/chart ──────────────────────────────────────── */
    case "overview/chart":
      return {
        title: "Q99 exceedance 과소추정률 상세",
        lede: "Q99 exceedance stratum(basin 상위 1% 유량 구간)에서 각 predictor가 관측값을 얼마나 자주 과소추정하는지 seed별로 정리한다.",
        sourcePath: "output/model_analysis/quantile_analysis/analysis/flow_strata_predictor_summary.csv · primary · basin_top1",
        panels: (
          <>
            <section className="panel research-panel">
              <div className="panel-sub">분석 맥락</div>
              <div className="panel-title">Q99 Exceedance stratum이란</div>
              <p className="panel-body">
                각 basin의 test period 관측 유량 분위를 계산하고, 상위 1%(Q99 초과) 시간대만 추출한다.
                이 구간에서 predictor가 관측값 아래로 내려가는 비율이 underestimation fraction이다.
                Primary 비교는 seed별 validation-best primary epoch를 사용한다.
              </p>
              <div className="fact-grid">
                <div className="fact-row"><span className="fact-label">총 row 수</span><strong>27,978</strong><span>Q99 exceedance hours</span></div>
                <div className="fact-row"><span className="fact-label">basin × seed</span><strong>38 × 3</strong><span>DRBC · 111/222/444</span></div>
                <div className="fact-row"><span className="fact-label">비교 기준</span><strong>primary epoch</strong><span>non-DRBC val. median NSE</span></div>
              </div>
            </section>
            <section className="panel research-panel">
              <div className="panel-sub">Quantile-zone 분포</div>
              <div className="panel-title">관측 peak가 어느 구간에 포함되나</div>
              <div className="data-block" style={{ marginTop: 12 }}>
                <table className="data-table">
                  <thead><tr><th>Zone</th><th style={{textAlign:"right"}}>Count</th><th style={{textAlign:"right"}}>비율</th><th>해석</th></tr></thead>
                  <tbody>
                    {[
                      ["> q99", 12574, 44.9, "관측이 q99를 넘음 (q99가 덮음)"],
                      ["q95–q99", 4748, 17.0, "q99 아래지만 q95 이상"],
                      ["q90–q95", 2130, 7.6, ""],
                      ["q50–q90", 4566, 16.3, ""],
                      ["≤ q50", 3960, 14.2, "중앙선 아래 — 과소추정"],
                    ].map(([zone, cnt, frac, note]) => (
                      <tr key={String(zone)}>
                        <td style={{fontFamily:"var(--font-geist-mono)", color: zone === "> q99" ? "#50e3c2" : "var(--ink-body)"}}>{zone}</td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)"}}>{cnt.toLocaleString()}</td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color: Number(frac) > 20 ? "#6bb4ff" : "var(--ink-body)"}}>{frac}%</td>
                        <td style={{fontSize:10, color:"var(--ink-muted)"}}>{note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="source-path">primary_q99_exceedance_quantile_zone_summary.csv</div>
              </div>
            </section>
          </>
        ),
      };

    /* ── results/q99-exceedance ──────────────────────────────── */
    case "results/q99-exceedance":
      return {
        title: "Q99 Exceedance 과소추정 상세 분석",
        lede: "Primary checkpoint에서 각 quantile predictor가 top 1% flow stratum의 관측값을 과소추정하는 비율과 median relative bias를 seed별로 확인한다. 이 분석이 연구 가설의 핵심 증거다.",
        sourcePath: "flow_strata_predictor_summary.csv · primary · basin_top1",
        csvContent: SECTION_CSV["results"].csv,
        csvFilename: "camels_results_q99_exceedance.csv",
        panels: (
          <>
            <section className="panel research-panel">
              <div className="panel-sub">Q99 exceedance · 전체 seed 상세</div>
              <div className="panel-title">Predictor별 과소추정률 및 Bias</div>
              <div className="data-block" style={{marginTop:12}}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Predictor</th>
                      <th style={{textAlign:"right"}}>Seed 111</th><th style={{textAlign:"right"}}>Seed 222</th><th style={{textAlign:"right"}}>Seed 444</th>
                      <th style={{textAlign:"right"}}>Seed Median</th>
                      <th style={{textAlign:"right"}}>Med.Bias 111</th><th style={{textAlign:"right"}}>Med.Bias 222</th><th style={{textAlign:"right"}}>Med.Bias 444</th>
                    </tr>
                  </thead>
                  <tbody>
                    {highFlowQ99.map((r) => {
                      const med = [...r.undestFrac].sort((a,b)=>a-b)[1];
                      const isQ99 = r.predictor === "M2 q99";
                      const isM1  = r.predictor === "Model 1";
                      return (
                        <tr key={r.predictor} style={isQ99 ? {background:"rgba(107,180,255,0.05)"} : undefined}>
                          <td style={{fontWeight: isM1 ? 700 : 400, color: isQ99 ? "#6bb4ff" : isM1 ? "var(--ink)" : "var(--ink-body)"}}>{r.predictor}</td>
                          {r.undestFrac.map((v, i) => (
                            <td key={i} style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color: v < 50 ? "#50e3c2" : v > 80 ? "#ff6b8a" : "var(--ink-body)"}}>{v.toFixed(1)}%</td>
                          ))}
                          <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", fontWeight:700, color: isQ99 ? "#50e3c2" : "var(--ink)"}}>{med.toFixed(1)}%</td>
                          {r.medRelBias.map((v, i) => (
                            <td key={i} style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", fontSize:10, color: v >= 0 ? "#50e3c2" : "#f7b955"}}>{v >= 0 ? "+" : ""}{v.toFixed(1)}%</td>
                          ))}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                <div className="source-path">flow_strata_predictor_summary.csv · primary · stratum=basin_top1</div>
              </div>
            </section>
            <section className="panel research-panel">
              <div className="panel-sub">해석 및 주의사항</div>
              <div className="panel-title">핵심 판단</div>
              <p className="panel-body">
                Model 1은 Q99 exceedance의 약 71.5%(seed median)를 과소추정한다.
                M2 q50은 85.9%로 더 나빠진다 — q50으로 high-flow 개선을 주장할 수 없다.
                M2 q99는 44.9%로 줄어들며, median relative bias가 +12%(과대 방향)로 이동한다.
                이는 q99가 peak를 더 많이 덮지만 일부 구간에서 과대 추정으로 이동함을 의미한다.
              </p>
              <div className="fact-grid">
                <div className="fact-row"><span className="fact-label">Model 1 seed median</span><strong style={{color:"#f7b955"}}>71.5%</strong><span>Q99 exceedance 과소추정</span></div>
                <div className="fact-row"><span className="fact-label">M2 q99 seed median</span><strong style={{color:"#50e3c2"}}>44.9%</strong><span>26.6%p 개선</span></div>
                <div className="fact-row"><span className="fact-label">q99 spread</span><strong>74.6%</strong><span>q99−q50 gap / obs (Q99 exceedance)</span></div>
                <div className="fact-row"><span className="fact-label">주의</span><strong style={{color:"#ff6b8a"}}>q99 ≠ 99% interval</strong><span>nominal undercoverage 존재</span></div>
              </div>
            </section>
          </>
        ),
      };

    case "results/expanded-first": {
      const first = evaluationTestsSnapshot.tests[0];
      const firstStatus: string = first.status;
      return {
        title: "Expanded First Test 상태",
        lede: "First test는 기존 38 basin primary summary가 아니라 expanded DRBC observed test split 기준으로 다시 평가한 산출을 공식값으로 써야 한다.",
        sourcePath: `${first.primarySource} · runner: ${first.runner}`,
        csvFilename: "camels_expanded_first_test_status.csv",
        csvContent: [
          ["model", "seed", "epoch", "n_basins", "median_NSE", "median_KGE", "median_FHV", "median_Peak_MAPE"].join(","),
          ...first.rows.map((row) => [
            row.model,
            row.seed,
            row.epoch,
            row.n_basins,
            row.median_NSE,
            row.median_KGE,
            row.median_FHV,
            row.median_Peak_MAPE,
          ].join(",")),
        ].join("\n"),
        panels: (
          <>
            <section className="panel research-panel">
              <div className="panel-sub">Expanded first test</div>
              <div className="panel-title">현재 평가 커버리지</div>
              <p className="panel-body">{first.interpretation}</p>
              <div className="fact-grid">
                <div className="fact-row"><span className="fact-label">status</span><strong style={{color:firstStatus === "ready" ? "#50e3c2" : "#f7b955"}}>{first.status}</strong><span>{first.basis}</span></div>
                <div className="fact-row"><span className="fact-label">coverage</span><strong>{first.coverage}</strong><span>evaluated / expanded selected</span></div>
                <div className="fact-row"><span className="fact-label">seeds</span><strong>{first.summary.seeds.join(" / ") || "none"}</strong><span>expected 111 / 222 / 444</span></div>
                <div className="fact-row"><span className="fact-label">models</span><strong>{first.summary.models.join(" / ") || "none"}</strong><span>expected model1 / model2</span></div>
              </div>
            </section>
            <section className="panel research-panel">
              <div className="panel-sub">Available rows</div>
              <div className="panel-title">현재 산출 요약</div>
              <div className="data-block" style={{marginTop:12}}>
                <table className="data-table">
                  <thead>
                    <tr><th>Model</th><th>Seed</th><th style={{textAlign:"right"}}>Basins</th><th style={{textAlign:"right"}}>NSE</th><th style={{textAlign:"right"}}>KGE</th><th style={{textAlign:"right"}}>Peak MAPE</th></tr>
                  </thead>
                  <tbody>
                    {first.rows.map((row) => (
                      <tr key={`${row.model}-${row.seed}`}>
                        <td style={{fontFamily:"var(--font-geist-mono)", fontWeight:700}}>{row.model}</td>
                        <td style={{fontFamily:"var(--font-geist-mono)"}}>{row.seed}</td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)"}}>{row.n_basins}</td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color: Number(row.median_NSE) < 0 ? "#ff6b8a" : "#50e3c2"}}>{Number(row.median_NSE).toFixed(3)}</td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)"}}>{Number(row.median_KGE).toFixed(3)}</td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)"}}>{Number(row.median_Peak_MAPE).toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="source-path">{first.primarySource}</div>
              </div>
            </section>
          </>
        ),
      };
    }

    /* ── results/peak-hour ───────────────────────────────────── */
    case "results/peak-hour":
      return {
        title: "Observed Peak Hour 과소추정 상세",
        lede: "Test period 중 관측된 유량 peak가 발생한 정확한 시간(basin별 1시간)에서 각 predictor가 얼마나 과소추정하는지 확인한다. Q99 exceedance 분석의 보완적 진단이다.",
        sourcePath: "flow_strata_predictor_summary.csv · primary · observed_peak_hour",
        csvContent: PEAK_HOUR_CSV,
        csvFilename: "camels_results_peak_hour.csv",
        panels: (
          <>
            <section className="panel research-panel">
              <div className="panel-sub">observed_peak_hour stratum · seed별 상세</div>
              <div className="panel-title">Peak Hour 과소추정률 및 Bias</div>
              <div className="data-block" style={{marginTop:12}}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Predictor</th>
                      <th style={{textAlign:"right"}}>Seed 111</th><th style={{textAlign:"right"}}>Seed 222</th><th style={{textAlign:"right"}}>Seed 444</th>
                      <th style={{textAlign:"right"}}>Median</th>
                      <th style={{textAlign:"right"}}>Bias 111</th><th style={{textAlign:"right"}}>Bias 222</th><th style={{textAlign:"right"}}>Bias 444</th>
                    </tr>
                  </thead>
                  <tbody>
                    {peakHourRows.map((r) => {
                      const med = [...r.undestFrac].sort((a,b)=>a-b)[1];
                      const isQ99 = r.predictor === "M2 q99";
                      const isM1  = r.predictor === "Model 1";
                      return (
                        <tr key={r.predictor} style={isQ99 ? {background:"rgba(107,180,255,0.05)"} : undefined}>
                          <td style={{fontWeight: isM1 ? 700 : 400, color: isQ99 ? "#6bb4ff" : "var(--ink-body)"}}>{r.predictor}</td>
                          {r.undestFrac.map((v, i) => (
                            <td key={i} style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color: v < 50 ? "#50e3c2" : v > 80 ? "#ff6b8a" : "var(--ink-body)"}}>{v.toFixed(1)}%</td>
                          ))}
                          <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", fontWeight:700, color: isQ99 ? "#50e3c2" : "var(--ink)"}}>{med.toFixed(1)}%</td>
                          {r.medRelBias.map((v, i) => (
                            <td key={i} style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", fontSize:10, color: v >= 0 ? "#50e3c2" : "#f7b955"}}>{v >= 0 ? "+" : ""}{v.toFixed(1)}%</td>
                          ))}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                <div className="source-path">flow_strata_predictor_summary.csv · primary · stratum=observed_peak_hour</div>
              </div>
              <p className="panel-body" style={{marginTop:10}}>
                Seed 444에서 q99가 peak hour의 31.6%만 과소추정 — 뚜렷한 개선.
                Seed 222는 63.2%로 개선폭이 작다. Headline claim은 seed median(55.3%)을 기준으로 써야 한다.
                Q99 exceedance stratum 결과(44.9%)보다 peak hour 결과가 높은 것은 peak hour가 더 좁은 단일 시점이기 때문이다.
              </p>
            </section>
            <section className="panel research-panel">
              <div className="panel-sub">분석 단위 설명</div>
              <div className="panel-title">Peak Hour stratum이란</div>
              <p className="panel-body">
                각 basin × seed 조합에서 test period 관측 유량이 최대인 시간 1개를 추출한다.
                DRBC 38 basin × 3 seed = 114개 peak 시점을 분석한다.
                이 stratum은 Q99 exceedance보다 더 극한적인 단일 시점에 집중하는 진단이다.
              </p>
              <div className="fact-grid">
                <div className="fact-row"><span className="fact-label">분석 대상</span><strong>114</strong><span>basin × seed peak 시점</span></div>
                <div className="fact-row"><span className="fact-label">M1 seed median</span><strong style={{color:"#f7b955"}}>76.3%</strong><span>과소추정</span></div>
                <div className="fact-row"><span className="fact-label">M2 q99 seed median</span><strong style={{color:"#50e3c2"}}>55.3%</strong><span>21.0%p 개선</span></div>
              </div>
            </section>
          </>
        ),
      };

    /* ── model/performance ───────────────────────────────────── */
    case "model/performance":
      return {
        title: "Primary 성능 표 상세",
        lede: "Primary checkpoint(non-DRBC validation median NSE 기준으로 선택)에서 Model 1과 Model 2 q50의 DRBC test 38 basin 성능을 seed별로 정리한다.",
        sourcePath: "output/model_analysis/overall_analysis/main_comparison/tables/primary_epoch_summary.csv",
        csvContent: SECTION_CSV["model"].csv,
        csvFilename: "camels_model_primary_performance.csv",
        panels: (
          <>
            <section className="panel research-panel">
              <div className="panel-sub">Primary epoch 매핑</div>
              <div className="panel-title">모델별 Validation-best Epoch</div>
              <div className="data-block" style={{marginTop:12}}>
                <table className="data-table">
                  <thead><tr><th>모델</th><th>Seed</th><th style={{textAlign:"right"}}>Primary epoch</th><th>비교</th></tr></thead>
                  <tbody>
                    {primaryPerformance.map((r) => (
                      <tr key={`${r.model}-${r.seed}`}>
                        <td style={{fontWeight: r.model === "Model 1" ? 600 : 400, color: r.model.startsWith("Model 2") ? "#6bb4ff" : "var(--ink)"}}>{r.model}</td>
                        <td style={{fontFamily:"var(--font-geist-mono)"}}>{r.seed}</td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color:"var(--ink-muted)"}}>{r.epoch}</td>
                        <td style={{fontSize:10, color:"var(--ink-muted)"}}>
                          {r.model === "Model 1" && r.seed === "111" && "M1 epoch 25 ↔ M2 epoch 5 (same seed)"}
                          {r.model === "Model 2 q50" && r.seed === "111" && "paired with M1 seed 111 epoch 25"}
                          {r.model === "Model 1" && r.seed === "222" && "M1 epoch 10 ↔ M2 epoch 10"}
                          {r.model === "Model 2 q50" && r.seed === "222" && "paired with M1 seed 222 epoch 10"}
                          {r.model === "Model 1" && r.seed === "444" && "M1 epoch 15 ↔ M2 epoch 10"}
                          {r.model === "Model 2 q50" && r.seed === "444" && "paired with M1 seed 444 epoch 15"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
            <section className="panel research-panel">
              <div className="panel-sub">DRBC test 38 basin · median metrics</div>
              <div className="panel-title">전체 성능 지표 상세</div>
              <div className="data-block" style={{marginTop:12}}>
                <table className="data-table">
                  <thead>
                    <tr><th>모델</th><th>Seed</th><th style={{textAlign:"right"}}>NSE</th><th style={{textAlign:"right"}}>KGE</th><th style={{textAlign:"right"}}>FHV</th><th style={{textAlign:"right"}}>Peak-MAPE</th><th style={{textAlign:"right"}}>neg-NSE 수</th></tr>
                  </thead>
                  <tbody>
                    {primaryPerformance.map((r) => (
                      <tr key={`${r.model}-${r.seed}-detail`}>
                        <td style={{fontWeight: r.model === "Model 1" ? 600 : 400, color: r.model.startsWith("Model 2") ? "#6bb4ff" : "var(--ink)"}}>{r.model}</td>
                        <td style={{fontFamily:"var(--font-geist-mono)"}}>{r.seed}</td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color: r.nse >= 0 ? "var(--ink)" : "#ff6b8a"}}>{r.nse.toFixed(3)}</td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)"}}>{r.kge.toFixed(3)}</td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color: Math.abs(r.fhv) > 30 ? "#f7b955" : "var(--ink-body)"}}>{r.fhv.toFixed(1)}</td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)"}}>{r.peakMape.toFixed(1)}</td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color: r.negNseCnt > 15 ? "#ff6b8a" : "var(--ink-body)"}}>{r.negNseCnt}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="source-path">primary_epoch_summary.csv</div>
              </div>
              <p className="panel-body" style={{marginTop:10}}>
                FHV(high-flow volume bias)는 부호에 주의. 음수는 high-flow 과소추정, 양수는 과대추정이다.
                Model 2 q50의 FHV는 seed별로 -51.7/-49.9/-27.5로 모두 음수 방향이 강하다 — q50으로 flood peak를 개선했다고 주장하면 안 된다.
                NSE 기준으로는 Model 2 q50이 guardrail을 통과했으나, KGE는 seed 111에서 하락.
              </p>
            </section>
          </>
        ),
      };

    /* ── model/nse-delta ─────────────────────────────────────── */
    case "model/nse-delta":
      return {
        title: "NSE Paired Delta 상세",
        lede: "같은 seed, 같은 basin에서 Model 2 q50 − Model 1 NSE 차이(paired delta)를 계산한다. Seed별 방향 일관성이 판정 강도의 핵심이다.",
        sourcePath: "primary_epoch_delta_summary.csv · primary_epoch_basin_deltas.csv",
        csvContent: NSE_DELTA_CSV,
        csvFilename: "camels_model_nse_delta.csv",
        panels: (
          <>
            <section className="panel research-panel">
              <div className="panel-sub">Seed별 Paired Delta 요약</div>
              <div className="panel-title">Model 2 q50 − Model 1 ΔNSE</div>
              <div className="data-block" style={{marginTop:12}}>
                <table className="data-table">
                  <thead><tr><th>Seed</th><th style={{textAlign:"right"}}>Median ΔNSE</th><th style={{textAlign:"right"}}>개선 fraction</th><th style={{textAlign:"right"}}>Median ΔKGE</th><th>NSE 판정</th></tr></thead>
                  <tbody>
                    {nseDeltaSummary.map((r) => (
                      <tr key={r.seed}>
                        <td style={{fontFamily:"var(--font-geist-mono)"}}>{r.seed}</td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color:"#50e3c2"}}>+{r.nseDelta.toFixed(3)}</td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)"}}>{(r.nseImproved * 100).toFixed(0)}%</td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color: r.kgeDelta >= 0 ? "#50e3c2" : "#ff6b8a"}}>{r.kgeDelta >= 0 ? "+" : ""}{r.kgeDelta.toFixed(3)}</td>
                        <td style={{fontSize:10, color:"var(--ink-muted)"}}>
                          {r.nseImproved > 0.6 ? "강함" : r.nseImproved > 0.5 ? "중간" : "약함"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="source-path">primary_epoch_delta_summary.csv</div>
              </div>
              <p className="panel-body" style={{marginTop:10}}>
                3개 seed 모두 median ΔNSE 양수, improvement fraction 0.61–0.68.
                판정 기준: 강함 = 3개 seed 모두 양수 + fraction &gt; 0.5 + 해석 가능한 크기.
                NSE improvement는 강한 방향이지만, KGE는 seed 111에서 −0.072로 혼합적.
                논문에서는 "Model 2 q50 preserves central NSE guardrail"로 표현하고, flood-peak claim은 q90/q95/q99로 별도 제시한다.
              </p>
            </section>
            <section className="panel research-panel">
              <div className="panel-sub">해석 한계</div>
              <div className="panel-title">FHV와 Peak-MAPE Delta 주의</div>
              <p className="panel-body">
                FHV delta의 seed median은 111: −16.1, 222: +0.3, 444: +16.6으로 혼합적이다.
                abs(FHV) reduction은 seed 111에서 오히려 나빠진다. 따라서 q50이 high-flow volume bias를 개선했다는 주장은 지지되지 않는다.
                Peak-MAPE reduction의 seed median은 111: −2.99, 222: +0.03, 444: +7.99로 방향이 엇갈린다.
                Primary overall 결론: q50은 central-skill guardrail을 통과했지만, flood-specific improvement는 upper quantile로만 주장할 수 있다.
              </p>
            </section>
          </>
        ),
      };

    /* ── analysis/event-regime ───────────────────────────────── */
    case "analysis/event-regime":
      return {
        title: "Event-Regime 상세 분석",
        lede: "570개 observed high-flow event를 ML event-regime(KMeans k=3, hydromet_only_7 features)으로 분류하고 각 regime에서 q99 under-deficit 감소를 확인한다.",
        sourcePath: "event_regime_paired_delta_compact.csv · ml_event_regime",
        panels: (
          <>
            <section className="panel research-panel">
              <div className="panel-sub">ML Event-Regime별 · q99 paired delta vs Model 1</div>
              <div className="panel-title">전체 Regime 분석</div>
              <div className="data-block" style={{marginTop:12}}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Regime</th>
                      <th style={{textAlign:"right"}}>Events</th>
                      <th style={{textAlign:"right"}}>q99 Δunder-deficit</th>
                      <th style={{textAlign:"right"}}>q99 ΔRecall</th>
                      <th style={{textAlign:"right"}}>q95 Δunder-deficit</th>
                      <th>q99 NRMSE 신호</th>
                    </tr>
                  </thead>
                  <tbody>
                    {eventRegimeRows.map((r) => (
                      <tr key={r.regime}>
                        <td style={{color:"var(--ink-body)"}}>{r.regime}</td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)"}}>{r.nEvents}</td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color:"#50e3c2"}}>+{r.q99UnderDeficitReduction.toFixed(1)}%p</td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color:"#6bb4ff"}}>+{r.q99RecallDelta.toFixed(3)}</td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color:"#b8c0cc"}}>
                          {r.regime === "Recent rainfall" ? "+17.2%p" : r.regime === "Antecedent / multi-day rain" ? "+19.4%p" : "+17.5%p"}
                        </td>
                        <td style={{fontFamily:"var(--font-geist-mono)", fontSize:10, color:"var(--ink-dim)"}}>{r.q99NrmseNote}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="source-path">event_regime_paired_delta_compact.csv</div>
              </div>
              <p className="panel-body" style={{marginTop:10}}>
                세 ML event-regime 전반에서 q99 under-deficit 감소 방향이 일관된다.
                q99의 NRMSE tradeoff는 Recent rainfall regime에서 가장 명확하게 나타난다 — under-deficit을 줄이지만 event hydrograph shape 측면에서 과대/불안정 가능성이 있다.
              </p>
            </section>
            <section className="panel research-panel">
              <div className="panel-sub">해석 제한</div>
              <div className="panel-title">Event set과 Regime 해석 주의</div>
              <p className="panel-body">
                570개 event는 모두 Q99 observed high-flow candidate이지만, flood relevance proxy 기준으로 대부분이 high_flow_below_2yr_proxy다.
                공식 flood inventory나 큰 return-period flood 전체에 대한 결과로 과장하면 안 된다.
              </p>
              <div className="fact-grid">
                <div className="fact-row"><span className="fact-label">Primary stratification</span><strong>KMeans k=3</strong><span>hydromet_only_7 features</span></div>
                <div className="fact-row"><span className="fact-label">Weak regime</span><strong>snow-dominant 아님</strong><span>낮은 snow_fraction 포함</span></div>
                <div className="fact-row"><span className="fact-label">Rule-label 검증</span><strong>degree_day_v2</strong><span>QA 및 sensitivity 전용</span></div>
              </div>
            </section>
          </>
        ),
      };

    /* ── analysis/calibration ────────────────────────────────── */
    case "analysis/calibration":
      return {
        title: "Calibration / Pinball 상세 진단",
        lede: "Model 2의 q50/q90/q95/q99가 quantile forecast로서 얼마나 calibrated되어 있는지 진단한다. q99를 calibrated 99% interval로 해석하는 것이 타당한지 확인하는 방어용 분석이다.",
        sourcePath: "output/model_analysis/probabilistic_diagnostics/report/probabilistic_diagnostics_report.md",
        panels: (
          <>
            <section className="panel research-panel">
              <div className="panel-sub">All-hour one-sided coverage · primary</div>
              <div className="panel-title">Calibration 전체 상세</div>
              <div className="data-block" style={{marginTop:12}}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Quantile</th>
                      <th style={{textAlign:"right"}}>Nominal τ</th>
                      <th style={{textAlign:"right"}}>All-hour coverage</th>
                      <th style={{textAlign:"right"}}>Coverage error</th>
                      <th style={{textAlign:"right"}}>Q99 tail hit-rate</th>
                      <th style={{textAlign:"right"}}>Pinball</th>
                      <th style={{textAlign:"right"}}>AQS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {calibrationRows.map((r) => {
                      const err = r.allHourCoverage - r.nominalTau;
                      const isQ99 = r.quantile === "q99";
                      return (
                        <tr key={r.quantile} style={isQ99 ? {background:"rgba(107,180,255,0.05)"} : undefined}>
                          <td style={{fontFamily:"var(--font-geist-mono)", fontWeight:700, color: isQ99 ? "#6bb4ff" : "var(--ink)"}}>{r.quantile}</td>
                          <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color:"var(--ink-muted)"}}>{r.nominalTau.toFixed(3)}</td>
                          <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color: err < -0.2 ? "#f7b955" : "var(--ink-body)"}}>{r.allHourCoverage.toFixed(3)}</td>
                          <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color:"#f7b955"}}>{err.toFixed(3)}</td>
                          <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color: r.q99ExceedanceCoverage >= 0.5 ? "#50e3c2" : "var(--ink-body)"}}>{r.q99ExceedanceCoverage.toFixed(3)}</td>
                          <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color: r.pinball < 1.5 ? "#50e3c2" : "var(--ink-body)"}}>{r.pinball.toFixed(3)}</td>
                          <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color:"var(--ink-muted)"}}>{(r.pinball * 2).toFixed(3)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                <div className="source-path">probabilistic_diagnostics_report.md · primary</div>
              </div>
              <p className="panel-body" style={{marginTop:10}}>
                All-hour coverage error가 모든 분위에서 음수 — 모든 quantile이 undercoverage다.
                q99 all-hour coverage 0.835 (nominal 0.990) → q99는 calibrated 99% predictive quantile이 아니다.
                Q99-exceedance tail hit-rate는 formal calibration이 아니라 조건부 hit-rate로 읽어야 한다.
              </p>
            </section>
            <section className="panel research-panel">
              <div className="panel-sub">논문에서의 사용 방침</div>
              <div className="panel-title">Calibration claim 분리</div>
              <p className="panel-body">
                이 분석은 Model 2가 probabilistic forecast로 fully calibrated되었음을 주장하기 위한 근거가 아니다.
                upper quantile improvement claim의 calibration caveat를 명확히 하는 방어용 분석으로 사용한다.
              </p>
              <div className="fact-grid">
                <div className="fact-row"><span className="fact-label">q50 coverage</span><strong style={{color:"#f7b955"}}>0.272</strong><span>nominal 0.500 → 크게 undercoverage</span></div>
                <div className="fact-row"><span className="fact-label">q99 coverage</span><strong style={{color:"#f7b955"}}>0.835</strong><span>nominal 0.990 → −0.155</span></div>
                <div className="fact-row"><span className="fact-label">q99 tail hit-rate</span><strong style={{color:"#6bb4ff"}}>0.560</strong><span>Q99 exceedance 중 56% 덮음</span></div>
                <div className="fact-row"><span className="fact-label">권장 표현</span><strong>"tail-aware output"</strong><span>calibrated interval 표현 지양</span></div>
              </div>
            </section>
          </>
        ),
      };

    /* ── stress/cohort ───────────────────────────────────────── */
    case "stress/cohort":
      return {
        title: "Stress Cohort 상세",
        lede: "hourly Rainf 기반 rain-event catalog로 DRBC historical stress(1980–2024) 이벤트를 cohort별로 나눠 q99의 under-deficit 감소와 false-positive tradeoff를 확인한다.",
        sourcePath: "output/model_analysis/extreme_rain/primary/",
        panels: (
          <>
            <section className="panel research-panel">
              <div className="panel-sub">Stress cohort · wet-footprint primary</div>
              <div className="panel-title">Cohort별 Under-deficit 비교</div>
              <div className="data-block" style={{marginTop:12}}>
                <table className="data-table">
                  <thead>
                    <tr><th>Cohort</th><th style={{textAlign:"right"}}>M1 under-deficit</th><th style={{textAlign:"right"}}>M2 q50</th><th style={{textAlign:"right"}}>M2 q99</th><th>비고</th></tr>
                  </thead>
                  <tbody>
                    {stressRows.map((r) => (
                      <tr key={r.cohort}>
                        <td style={{fontFamily:"var(--font-geist-mono)", fontSize:10}}>{r.cohort}</td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color:"#f7b955"}}>{r.m1UnderDeficit.toFixed(1)}%</td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color:"#b8c0cc"}}>
                          {r.cohort === "flood_response_ge25" ? "76.6%" : r.cohort === "flood_response_lt25" ? "68.0%" : "55.0%"}
                        </td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color: r.q99UnderDeficit < 35 ? "#50e3c2" : "var(--ink-body)"}}>{r.q99UnderDeficit.toFixed(1)}%</td>
                        <td style={{fontSize:10, color:"var(--ink-muted)"}}>{r.note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="source-path">extreme_rain/primary/ · paired_delta_aggregate.csv</div>
              </div>
              <p className="panel-body" style={{marginTop:10}}>
                flood_response_ge25(강한 flood response) cohort에서 q99 under-deficit이 72.0% → 27.3%으로 가장 큰 감소.
                negative_control cohort는 under-deficit 자체가 낮지만, q99 predicted peak / ARI100 = 1.25×로 false-positive 가능성 존재.
              </p>
            </section>
            <section className="panel research-panel">
              <div className="panel-sub">사용 제한</div>
              <div className="panel-title">Temporal Independence 주의사항</div>
              <p className="panel-body">
                drbc_historical_stress는 DRBC basin holdout 조건은 유지하지만 1980–2024 기간을 포함한다.
                따라서 temporal independence claim에는 사용하지 않는다. Primary DRBC test(2014–2016)를 대체하지 않는다.
                이 분석은 primary result의 supporting diagnostic으로만 쓰는 것이 안전하다.
              </p>
              <div className="fact-grid">
                <div className="fact-row"><span className="fact-label">stress 이벤트</span><strong>236</strong><span>historical 1980–2024</span></div>
                <div className="fact-row"><span className="fact-label">q99 under-deficit 감소</span><strong style={{color:"#50e3c2"}}>22.1%p</strong><span>flood_response_ge25 기준</span></div>
                <div className="fact-row"><span className="fact-label">false-positive proxy</span><strong style={{color:"#f7b955"}}>1.25×</strong><span>q99 / ARI100 · negative_control</span></div>
              </div>
            </section>
          </>
        ),
      };

    case "stress/expanded-extreme": {
      const extreme = evaluationTestsSnapshot.tests[1];
      const extremeStatus: string = extreme.status;
      return {
        title: "Expanded Extreme Test 상태",
        lede: "Extreme-rain stress test는 first test와 같은 expanded DRBC basin universe로 다시 만들어야 dashboard 공식 stress 축과 basin coverage가 일치한다.",
        sourcePath: `${extreme.primarySource} · runner: ${extreme.runner}`,
        panels: (
          <>
            <section className="panel research-panel">
              <div className="panel-sub">Expanded extreme test</div>
              <div className="panel-title">현재 산출 상태</div>
              <p className="panel-body">{extreme.interpretation}</p>
              <div className="fact-grid">
                <div className="fact-row"><span className="fact-label">status</span><strong style={{color:extremeStatus === "ready" ? "#50e3c2" : "#f7b955"}}>{extreme.status}</strong><span>{extreme.basis}</span></div>
                <div className="fact-row"><span className="fact-label">coverage</span><strong>{extreme.coverage}</strong><span>current / expanded selected</span></div>
                <div className="fact-row"><span className="fact-label">events</span><strong>{extreme.summary.events}</strong><span>current stress table</span></div>
                <div className="fact-row"><span className="fact-label">seeds</span><strong>{extreme.summary.seeds.join(" / ") || "none"}</strong><span>expected 111 / 222 / 444</span></div>
              </div>
            </section>
            <section className="panel research-panel">
              <div className="panel-sub">해석 경계</div>
              <div className="panel-title">왜 expanded rerun이 먼저인가</div>
              <p className="panel-body">
                기존 extreme-rain stress 결과는 primary 38 basin 해석을 보조하는 진단으로 만들어졌다.
                이제 dashboard의 main test frame을 expanded basin 기준으로 바꾸면, stress event catalog와 model inference도 같은 basin universe에서 다시 만들어야 한다.
                그래야 first test, extreme test, confirmed flood test를 같은 화면에서 비교할 때 coverage 차이가 결론처럼 섞이지 않는다.
              </p>
              <div className="source-path">{extreme.runner}</div>
            </section>
          </>
        ),
      };
    }

    /* ── stress/checkpoint ───────────────────────────────────── */
    case "stress/checkpoint":
      return {
        title: "Checkpoint Sensitivity 상세",
        lede: "Primary result가 validation-best checkpoint 하나에만 의존하는지 all-validation-epoch sweep(6 epochs × 3 seeds = 18 combinations)으로 확인하는 diagnostic이다.",
        sourcePath: "output/model_analysis/overall_analysis/epoch_sensitivity/tables/checkpoint_sensitivity_compact_summary.csv",
        panels: (
          <>
            <section className="panel research-panel">
              <div className="panel-sub">Primary vs Same-epoch grid · Q99 exceedance q99</div>
              <div className="panel-title">Checkpoint Sensitivity 핵심 수치</div>
              <div className="fact-grid" style={{marginTop:12}}>
                <div className="fact-row"><span className="fact-label">Primary q99 undest. fraction</span><strong style={{color:"#50e3c2"}}>0.440</strong><span>seed 111 (best seed)</span></div>
                <div className="fact-row"><span className="fact-label">Same-epoch grid median</span><strong>0.451</strong><span>18개 조합 중앙값</span></div>
                <div className="fact-row"><span className="fact-label">Primary q99–q50 spread</span><strong>74.6%</strong><span>obs 대비 · Q99 exceedance</span></div>
                <div className="fact-row"><span className="fact-label">Same-epoch spread median</span><strong>67.3%</strong><span>primary는 약간 넓은 편</span></div>
                <div className="fact-row"><span className="fact-label">Stress under-deficit (primary)</span><strong style={{color:"#f7b955"}}>22.1%p</strong><span>flood_response_ge25</span></div>
                <div className="fact-row"><span className="fact-label">Stress (same-epoch median)</span><strong>38.5%p</strong><span>checkpoint에 민감함</span></div>
              </div>
              <p className="panel-body" style={{marginTop:10}}>
                Q99 exceedance q99 underestimation fraction은 primary(0.440)와 same-epoch median(0.451)이 유사하다 — primary는 특별히 유리한 outlier가 아니다.
                Stress under-deficit magnitude는 checkpoint에 민감하므로 supporting diagnostic으로만 사용한다.
              </p>
            </section>
            <section className="panel research-panel">
              <div className="panel-sub">Sensitivity 설계</div>
              <div className="panel-title">All-epoch sweep 방법론</div>
              <p className="panel-body">
                Epoch grid: 005/010/015/020/025/030. Seed: 111/222/444. 총 18개 seed-epoch 조합.
                Sensitivity는 checkpoint 재선택을 위한 것이 아니라, primary result의 robustness 확인용 diagnostic이다.
                Primary epoch는 이미 non-DRBC validation median NSE 기준으로 잠겨 있다.
              </p>
              <div className="fact-grid">
                <div className="fact-row"><span className="fact-label">Epoch grid</span><strong>6개</strong><span>5/10/15/20/25/30</span></div>
                <div className="fact-row"><span className="fact-label">Seed</span><strong>3개</strong><span>111/222/444</span></div>
                <div className="fact-row"><span className="fact-label">조합 수</span><strong>18</strong><span>seed × epoch</span></div>
                <div className="fact-row"><span className="fact-label">목적</span><strong>robustness 확인</strong><span>재선택 아님</span></div>
              </div>
            </section>
          </>
        ),
      };

    /* ── dataset/split ───────────────────────────────────────── */
    case "dataset/split":
      return {
        title: "Basin Split 상세",
        lede: "DRBC Delaware Basin을 regional holdout으로 설정하고 non-DRBC CAMELSH basin으로 global multi-basin model을 학습하는 split 구조를 정리한다.",
        sourcePath: "configs/basin_splits/ · basins/drbc_boundary/drb_bnd_polygon.shp",
        csvContent: SECTION_CSV["dataset"].csv,
        csvFilename: "camels_dataset_split.csv",
        panels: (
          <>
            <section className="panel research-panel">
              <div className="panel-sub">Basin Split 전체</div>
              <div className="panel-title">Split 구성 및 기준</div>
              <div className="data-block" style={{marginTop:12}}>
                <table className="data-table">
                  <thead><tr><th>Split</th><th style={{textAlign:"right"}}>유역 수</th><th>선정 기준</th><th>역할</th></tr></thead>
                  <tbody>
                    {datasetRows.map((r) => (
                      <tr key={r.split}>
                        <td style={{fontWeight:600}}>{r.split}</td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color:"var(--ink)"}}>{r.basins.toLocaleString()}</td>
                        <td style={{fontFamily:"var(--font-geist-mono)", fontSize:9, color:"var(--ink-muted)"}}>{r.criteria}</td>
                        <td style={{color:"var(--ink-body)"}}>{r.role}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="source-path">configs/basin_splits/ · basins/CAMELSH/</div>
              </div>
            </section>
            <section className="panel research-panel">
              <div className="panel-sub">설계 결정 원칙</div>
              <div className="panel-title">Subset300 고정 배경</div>
              <p className="panel-body">
                Scaling pilot에서 deterministic Model 1으로 100/300/600 basin을 비교했다.
                Non-DRBC validation 성능 + static attribute distribution + observed-flow event-response diagnostics + random same-size subset benchmark + compute cost를 함께 고려해 300으로 고정했다.
                <strong> DRBC holdout test metric으로 pilot basin 수를 고르지 않았다.</strong>
              </p>
              <div className="fact-grid">
                <div className="fact-row"><span className="fact-label">시간 해상도</span><strong>Hourly</strong><span>CAMELSH hourly</span></div>
                <div className="fact-row"><span className="fact-label">Test 기간</span><strong>2014–2016</strong><span>temporal holdout</span></div>
                <div className="fact-row"><span className="fact-label">DRBC 기준 레이어</span><strong>drb_bnd_polygon.shp</strong><span>basins/drbc_boundary/</span></div>
                <div className="fact-row"><span className="fact-label">Model 2 seed 333</span><strong style={{color:"#ff6b8a"}}>제외</strong><span>NaN loss · Model 1 333도 동반 제외</span></div>
              </div>
            </section>
          </>
        ),
      };

    /* ── hydrograph/quantile-zone ────────────────────────────── */
    case "hydrograph/quantile-zone":
      return {
        title: "Quantile-Zone 진단 상세",
        lede: "Q99 exceedance 시간대에서 관측 유량이 어느 quantile 구간에 포함되는지 분포를 확인한다. Model 2가 upper-tail margin을 얼마나 열어두는지 직접 보여주는 진단이다.",
        sourcePath: "primary_q99_exceedance_quantile_zone_summary.csv · primary_top1_quantile_zone_summary.csv",
        panels: (
          <>
            <section className="panel research-panel">
              <div className="panel-sub">Q99 exceedance 27,978 rows · zone 분포</div>
              <div className="panel-title">Quantile Zone 분포</div>
              <div className="data-block" style={{marginTop:12}}>
                <table className="data-table">
                  <thead><tr><th>Zone</th><th style={{textAlign:"right"}}>Count</th><th style={{textAlign:"right"}}>비율</th><th>해석</th></tr></thead>
                  <tbody>
                    {[
                      ["> q99", 12574, 44.9, "관측이 q99를 넘음 — q99가 커버함", "#50e3c2"],
                      ["q95–q99", 4748, 17.0, "", "#6bb4ff"],
                      ["q90–q95", 2130, 7.6, "", "var(--ink-body)"],
                      ["q50–q90", 4566, 16.3, "", "var(--ink-body)"],
                      ["≤ q50", 3960, 14.2, "q50도 넘지 못함 — 과소추정", "#f7b955"],
                    ].map(([zone, cnt, frac, note, color]) => (
                      <tr key={String(zone)}>
                        <td style={{fontFamily:"var(--font-geist-mono)", color: String(color)}}>{zone}</td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)"}}>{Number(cnt).toLocaleString()}</td>
                        <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color: String(color)}}>{frac}%</td>
                        <td style={{fontSize:10, color:"var(--ink-muted)"}}>{note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="source-path">primary_q99_exceedance_quantile_zone_summary.csv</div>
              </div>
            </section>
            <section className="panel research-panel">
              <div className="panel-sub">114개 basin-seed peak 시점 zone</div>
              <div className="panel-title">Peak 한 시점 Zone 분포</div>
              <div className="fact-grid" style={{marginTop:12}}>
                <div className="fact-row"><span className="fact-label">&gt; q99</span><strong style={{color:"#50e3c2"}}>57개 (50.0%)</strong><span>peak가 q99 이상</span></div>
                <div className="fact-row"><span className="fact-label">q95–q99</span><strong style={{color:"#6bb4ff"}}>14개 (12.3%)</strong><span></span></div>
                <div className="fact-row"><span className="fact-label">q90–q95</span><strong>7개 (6.1%)</strong><span></span></div>
                <div className="fact-row"><span className="fact-label">q50–q90</span><strong>16개 (14.0%)</strong><span></span></div>
                <div className="fact-row"><span className="fact-label">≤ q50</span><strong style={{color:"#f7b955"}}>20개 (17.5%)</strong><span>여전히 과소추정</span></div>
              </div>
              <p className="panel-body" style={{marginTop:10}}>
                114개 peak 중 57개(50%)는 q99가 커버하고 20개(17.5%)는 q50도 못 넘는다.
                Q99 exceedance 전체(27,978 row)에서 median q99−q50 spread는 관측값의 74.6% — Model 2가 high-flow에서 중앙선 위로 충분한 여유를 두고 있음을 나타낸다.
                Quantile crossing sanity check: q90&lt;q50, q95&lt;q90, q99&lt;q95 모두 0 row로 통과.
              </p>
            </section>
          </>
        ),
      };

    default:
      return null;
  }
}
