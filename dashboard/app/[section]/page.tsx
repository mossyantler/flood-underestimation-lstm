import Link from "next/link";
import { notFound } from "next/navigation";
import { SLUG_TO_ID, SECTION_LABEL, SECTION_SLUG } from "@/lib/sections";
import { DashboardShell } from "@/components/dashboard-shell";
import { SectionHeader } from "@/components/section-header";
import { KpiStrip } from "@/components/kpi-card";
import { ChartCard } from "@/components/chart-card";
import { SectionTable } from "@/components/section-table";
import { CheckpointCard } from "@/components/checkpoint-card";
import { ConfirmedFloodDashboard } from "@/components/confirmed-flood-dashboard";
import { EvaluationTestMatrix } from "@/components/evaluation-test-matrix";
import { FigurePreviewGrid } from "@/components/figure-preview-grid";
import { StatusBoard } from "@/components/status-board";
import {
  overviewKpis, sectionIndexRows, checkpointRows,
  resultsKpis, stressKpis,
  primaryPerformance, nseDeltaSummary,
  highFlowQ99, peakHourRows,
  eventRegimeRows, calibrationRows,
  stressRows, datasetRows,
} from "@/lib/dashboard-data";
import {
  analysisFigureDeck,
  overviewFigureDeck,
  resultFigureDeck,
  stressFigureDeck,
} from "@/lib/figure-assets";
import { SECTION_CSV, NSE_DELTA_CSV, PEAK_HOUR_CSV } from "@/lib/export";

interface Props { params: Promise<{ section: string }> }

export default async function SectionPage({ params }: Props) {
  const { section } = await params;
  const id = SLUG_TO_ID[section];
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
      {id === "H" && <HydrographSection />}
      {id === "D" && <DatasetSection />}
      {id === "M" && <ModelSection />}
      {id === "R" && <ResultsSection />}
      {id === "A" && <AnalysisSection />}
      {id === "S" && <StressSection />}
      {id === "F" && <ConfirmedFloodSection />}

      <div className="grid-note">
        CAMELS Dashboard · DRBC holdout · subset300 · seed 111/222/444
      </div>
    </DashboardShell>
  );
}

/* ── 공통: 패널 내 "자세히 →" 링크 ────────────────────────────── */
function DetailLink({ href }: { href: string }) {
  return (
    <Link href={href} className="panel-detail-link">
      자세히 →
    </Link>
  );
}

/* ── 개요(O) ──────────────────────────────────────────────────── */
function OverviewSection() {
  return (
    <>
      <p className="section-lede">
        CAMELS dashboard는 연구 claim의 상태와 근거를 관리하고, headline indicator에서 raw hydrologic evidence까지 내려가는 실험 검토 workbench다.
      </p>
      <StatusBoard />
    </>
  );
}

/* ── 수문곡선(H) ─────────────────────────────────────────────── */
function HydrographSection() {
  return (
    <>
      <p className="section-lede">
        DRBC test basin 38개, seed별 primary epoch 대표 수문곡선과 peak timing 분석.
        figure PNG는 <code>output/model_analysis/quantile_analysis/primary_seed_basin/</code> (684개)에 있다.
      </p>
      <div className="panel-grid">
        <section className="panel research-panel">
          <div className="panel-sub">산출물 위치</div>
          <div className="panel-title">대표 수문곡선 후보</div>
          <p className="panel-body">
            <code>output/model_analysis/paper_result_assets/tables/representative_hydrograph_candidates.csv</code>에서
            성공 사례와 tradeoff 사례 후보를 선별한다.
          </p>
          <div className="fact-grid">
            <div className="fact-row"><span className="fact-label">총 hydrograph</span><strong>684</strong><span>seed × basin</span></div>
            <div className="fact-row"><span className="fact-label">DRBC test 기간</span><strong>2014–2016</strong><span>temporal holdout</span></div>
          </div>
        </section>
        <section className="panel research-panel">
          <div className="panel-sub">Quantile-zone 진단</div>
          <div className="panel-title">Peak 시간 포함 구간</div>
          <p className="panel-body">
            Primary Q99 exceedance 전체 27,978 row 중 q99 이상 포함 44.9%, q50 이하 14.2%.
            Peak 한 시점 114개 중 q99 초과 57개(50%), q50 이하 20개(17.5%).
          </p>
          <div className="fact-grid">
            <div className="fact-row"><span className="fact-label">&gt; q99</span><strong style={{color:"#6bb4ff"}}>44.9%</strong><span>of Q99 exceedance rows</span></div>
            <div className="fact-row"><span className="fact-label">peak &gt; q99</span><strong style={{color:"#6bb4ff"}}>50.0%</strong><span>of 114 basin-seed peaks</span></div>
            <div className="fact-row"><span className="fact-label">peak ≤ q50</span><strong style={{color:"#f7b955"}}>17.5%</strong><span>still underestimated</span></div>
          </div>
          <DetailLink href="/hydrograph/quantile-zone" />
        </section>
      </div>
    </>
  );
}

/* ── 데이터셋(D) ─────────────────────────────────────────────── */
function DatasetSection() {
  return (
    <>
      <p className="section-lede">
        CAMELSH hourly를 기반으로 DRBC Delaware Basin을 regional holdout으로 설정한다.
        Scaling pilot에서 결정된 subset300으로 train/val을 고정하고, seed 111/222/444가 동일 subset을 재사용한다.
      </p>
      <div className="panel-grid">
        <section className="panel research-panel">
          <div className="panel-sub">Basin split</div>
          <div className="panel-title">Split 구성</div>
          <div className="data-block" style={{marginTop: 12}}>
            <table className="data-table">
              <thead>
                <tr><th>Split</th><th style={{textAlign:"right"}}>유역 수</th><th>역할</th></tr>
              </thead>
              <tbody>
                {datasetRows.map((r) => (
                  <tr key={r.split}>
                    <td style={{fontWeight:600}}>{r.split}</td>
                    <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color:"var(--ink)"}}>{r.basins.toLocaleString()}</td>
                    <td style={{color:"var(--ink-muted)"}}>{r.role}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <DetailLink href="/dataset/split" />
        </section>
        <section className="panel research-panel">
          <div className="panel-sub">설계 원칙</div>
          <div className="panel-title">Subset300 고정 이유</div>
          <p className="panel-body">
            Scaling pilot에서 100/300/600 basin 비교 후 non-DRBC validation 성능 + compute cost를 함께 고려해 300으로 고정.
            DRBC holdout test metric으로 pilot basin 수를 고르지 않았다.
          </p>
          <div className="fact-grid">
            <div className="fact-row"><span className="fact-label">시간 해상도</span><strong>Hourly</strong><span>CAMELSH</span></div>
            <div className="fact-row"><span className="fact-label">Test 기간</span><strong>2014–2016</strong><span>temporal holdout</span></div>
            <div className="fact-row"><span className="fact-label">Seed 333</span><strong style={{color:"#ff6b8a"}}>제외</strong><span>Model 2 NaN loss</span></div>
          </div>
        </section>
      </div>
    </>
  );
}

/* ── 모델(M) ─────────────────────────────────────────────────── */
function ModelSection() {
  const m1Rows = primaryPerformance.filter((r) => r.model === "Model 1");
  const m2Rows = primaryPerformance.filter((r) => r.model === "Model 2 q50");

  return (
    <>
      <p className="section-lede">
        Backbone은 동일한 multi-basin LSTM. Model 1은 deterministic point output,
        Model 2는 backbone 고정 + quantile head(q50/q90/q95/q99)만 교체.
        Primary epoch는 non-DRBC validation median NSE 기준으로 선택했다.
      </p>
      <div className="panel-grid">
        <section className="panel research-panel">
          <div className="panel-sub">Primary epoch 성능 · DRBC test 38 basin median</div>
          <div className="panel-title">Model 1 vs Model 2 q50</div>
          <div className="data-block" style={{marginTop:12}}>
            <table className="data-table">
              <thead>
                <tr><th>모델</th><th>Seed</th><th style={{textAlign:"right"}}>NSE</th><th style={{textAlign:"right"}}>KGE</th><th style={{textAlign:"right"}}>FHV</th><th style={{textAlign:"right"}}>neg-NSE</th></tr>
              </thead>
              <tbody>
                {m1Rows.map((r) => (
                  <tr key={`m1-${r.seed}`}>
                    <td style={{fontWeight:600}}>Model 1</td>
                    <td style={{fontFamily:"var(--font-geist-mono)"}}>{r.seed}</td>
                    <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color: r.nse >= 0 ? "var(--ink)" : "#ff6b8a"}}>{r.nse.toFixed(3)}</td>
                    <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)"}}>{r.kge.toFixed(3)}</td>
                    <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color: Math.abs(r.fhv) > 20 ? "#f7b955" : "var(--ink-body)"}}>{r.fhv.toFixed(1)}</td>
                    <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color:"#ff6b8a"}}>{r.negNseCnt}</td>
                  </tr>
                ))}
                <tr><td colSpan={6} style={{height:4, border:"none"}} /></tr>
                {m2Rows.map((r) => (
                  <tr key={`m2-${r.seed}`}>
                    <td style={{fontWeight:600, color:"#6bb4ff"}}>Model 2 q50</td>
                    <td style={{fontFamily:"var(--font-geist-mono)"}}>{r.seed}</td>
                    <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color: r.nse >= 0 ? "var(--ink)" : "#ff6b8a"}}>{r.nse.toFixed(3)}</td>
                    <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)"}}>{r.kge.toFixed(3)}</td>
                    <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color:"#f7b955"}}>{r.fhv.toFixed(1)}</td>
                    <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color:"#50e3c2"}}>{r.negNseCnt}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="source-path">primary_epoch_summary.csv</div>
          </div>
          <DetailLink href="/model/performance" />
        </section>
        <section className="panel research-panel">
          <div className="panel-sub">Paired delta · Model 2 q50 − Model 1</div>
          <div className="panel-title">NSE 개선 요약</div>
          <div className="data-block" style={{marginTop:12}}>
            <table className="data-table">
              <thead><tr><th>Seed</th><th style={{textAlign:"right"}}>ΔNSE</th><th style={{textAlign:"right"}}>개선 fraction</th><th style={{textAlign:"right"}}>ΔKGE</th></tr></thead>
              <tbody>
                {nseDeltaSummary.map((r) => (
                  <tr key={r.seed}>
                    <td style={{fontFamily:"var(--font-geist-mono)"}}>{r.seed}</td>
                    <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color:"#50e3c2"}}>+{r.nseDelta.toFixed(3)}</td>
                    <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)"}}>{(r.nseImproved * 100).toFixed(0)}%</td>
                    <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color: r.kgeDelta >= 0 ? "#50e3c2" : "#ff6b8a"}}>{r.kgeDelta >= 0 ? "+" : ""}{r.kgeDelta.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <DetailLink href="/model/nse-delta" />
        </section>
      </div>
    </>
  );
}

/* ── 결과(R) ─────────────────────────────────────────────────── */
function ResultsSection() {
  return (
    <>
      <KpiStrip items={resultsKpis} />
      <p className="section-lede">
        Upper quantile head(q90/q95/q99)가 Q99 exceedance stratum과 observed peak hour에서
        deterministic Model 1의 peak underestimation을 얼마나 줄이는지 확인한다. 이 분석이 연구 가설의 핵심이다.
      </p>
      <FigurePreviewGrid figures={resultFigureDeck} />
      <div className="panel-grid">
        <section className="panel research-panel">
          <div className="panel-sub">top 1% flow stratum (basin Q99 exceedance)</div>
          <div className="panel-title">Q99 exceedance 과소추정률 — seed별</div>
          <div className="data-block" style={{marginTop:12}}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Predictor</th>
                  <th style={{textAlign:"right"}}>111</th><th style={{textAlign:"right"}}>222</th><th style={{textAlign:"right"}}>444</th>
                  <th style={{textAlign:"right"}}>Median</th>
                </tr>
              </thead>
              <tbody>
                {highFlowQ99.map((r) => {
                  const med = [...r.undestFrac].sort((a,b)=>a-b)[1];
                  const isM2q99 = r.predictor === "M2 q99";
                  const isM1 = r.predictor === "Model 1";
                  return (
                    <tr key={r.predictor}>
                      <td style={{fontWeight: isM1 ? 600 : 400, color: isM2q99 ? "#6bb4ff" : isM1 ? "var(--ink)" : "var(--ink-body)"}}>{r.predictor}</td>
                      {r.undestFrac.map((v, i) => (
                        <td key={i} style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color: v < 50 ? "#50e3c2" : v > 80 ? "#ff6b8a" : "var(--ink-body)"}}>{v.toFixed(1)}%</td>
                      ))}
                      <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", fontWeight:700, color: isM2q99 ? "#50e3c2" : "var(--ink)"}}>{med.toFixed(1)}%</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div className="source-path">flow_strata_predictor_summary.csv · primary · basin_top1</div>
          </div>
          <DetailLink href="/results/q99-exceedance" />
        </section>

        <section className="panel research-panel">
          <div className="panel-sub">observed_peak_hour stratum</div>
          <div className="panel-title">Peak hour 과소추정률 — seed별</div>
          <div className="data-block" style={{marginTop:12}}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Predictor</th>
                  <th style={{textAlign:"right"}}>111</th><th style={{textAlign:"right"}}>222</th><th style={{textAlign:"right"}}>444</th>
                  <th style={{textAlign:"right"}}>Median</th>
                </tr>
              </thead>
              <tbody>
                {peakHourRows.map((r) => {
                  const med = [...r.undestFrac].sort((a,b)=>a-b)[1];
                  const isM2q99 = r.predictor === "M2 q99";
                  const isM1 = r.predictor === "Model 1";
                  return (
                    <tr key={r.predictor}>
                      <td style={{fontWeight: isM1 ? 600 : 400, color: isM2q99 ? "#6bb4ff" : isM1 ? "var(--ink)" : "var(--ink-body)"}}>{r.predictor}</td>
                      {r.undestFrac.map((v, i) => (
                        <td key={i} style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color: v < 50 ? "#50e3c2" : v > 80 ? "#ff6b8a" : "var(--ink-body)"}}>{v.toFixed(1)}%</td>
                      ))}
                      <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", fontWeight:700, color: isM2q99 ? "#50e3c2" : "var(--ink)"}}>{med.toFixed(1)}%</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div className="source-path">flow_strata_predictor_summary.csv · primary · observed_peak_hour</div>
          </div>
          <DetailLink href="/results/peak-hour" />
        </section>
      </div>
    </>
  );
}

/* ── 분석(A) ─────────────────────────────────────────────────── */
function AnalysisSection() {
  return (
    <>
      <p className="section-lede">
        570개 observed high-flow event를 ML event-regime(KMeans k=3)으로 분류해 상위 분위 효과를 검증하고,
        Model 2 calibration(pinball/AQS, coverage)을 진단한다.
      </p>
      <FigurePreviewGrid figures={analysisFigureDeck} />
      <div className="panel-grid">
        <section className="panel research-panel">
          <div className="panel-sub">ML event-regime · q99 paired delta vs Model 1</div>
          <div className="panel-title">Event-Regime별 Under-deficit 감소</div>
          <div className="data-block" style={{marginTop:12}}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Regime</th><th style={{textAlign:"right"}}>Events</th>
                  <th style={{textAlign:"right"}}>q99 Δunder-deficit</th>
                  <th style={{textAlign:"right"}}>q99 ΔRecall</th>
                </tr>
              </thead>
              <tbody>
                {eventRegimeRows.map((r) => (
                  <tr key={r.regime}>
                    <td style={{color:"var(--ink-body)"}}>{r.regime}</td>
                    <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)"}}>{r.nEvents}</td>
                    <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color:"#50e3c2"}}>+{r.q99UnderDeficitReduction.toFixed(1)}%p</td>
                    <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color:"#6bb4ff"}}>+{r.q99RecallDelta.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="source-path">event_regime_paired_delta_compact.csv</div>
          </div>
          <DetailLink href="/analysis/event-regime" />
        </section>

        <section className="panel research-panel">
          <div className="panel-sub">Model 2 quantile calibration · primary</div>
          <div className="panel-title">Calibration / Pinball 진단</div>
          <div className="data-block" style={{marginTop:12}}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Quantile</th><th style={{textAlign:"right"}}>All-hour coverage</th>
                  <th style={{textAlign:"right"}}>Q99 tail hit-rate</th>
                  <th style={{textAlign:"right"}}>Pinball</th>
                </tr>
              </thead>
              <tbody>
                {calibrationRows.map((r) => (
                  <tr key={r.quantile}>
                    <td style={{fontFamily:"var(--font-geist-mono)", fontWeight:700, color: r.quantile === "q99" ? "#6bb4ff" : "var(--ink)"}}>{r.quantile}</td>
                    <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color: r.allHourCoverage - r.nominalTau < -0.2 ? "#f7b955" : "var(--ink-body)"}}>{r.allHourCoverage.toFixed(3)}</td>
                    <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color: r.q99ExceedanceCoverage >= 0.5 ? "#50e3c2" : "var(--ink-body)"}}>{r.q99ExceedanceCoverage.toFixed(3)}</td>
                    <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color: r.pinball < 1.5 ? "#50e3c2" : "var(--ink-body)"}}>{r.pinball.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="source-path">probabilistic_diagnostics_report.md</div>
          </div>
          <DetailLink href="/analysis/calibration" />
        </section>
      </div>
    </>
  );
}

/* ── 스트레스(S) ─────────────────────────────────────────────── */
function StressSection() {
  return (
    <>
      <KpiStrip items={stressKpis} />
      <p className="section-lede">
        hourly Rainf에서 만든 rain-event catalog로 DRBC historical stress(1980–2024)에서
        upper quantile의 peak tracking과 false-positive tradeoff를 점검한다.
        <strong> drbc_historical_stress는 temporal independence claim에 사용하지 않는다.</strong>
      </p>
      <FigurePreviewGrid figures={stressFigureDeck} />
      <div className="panel-grid">
        <section className="panel research-panel">
          <div className="panel-sub">stress cohort · q99 under-deficit</div>
          <div className="panel-title">Cohort별 Under-deficit 감소</div>
          <div className="data-block" style={{marginTop:12}}>
            <table className="data-table">
              <thead>
                <tr><th>Cohort</th><th style={{textAlign:"right"}}>M1</th><th style={{textAlign:"right"}}>q99</th><th>비고</th></tr>
              </thead>
              <tbody>
                {stressRows.map((r) => (
                  <tr key={r.cohort}>
                    <td style={{fontFamily:"var(--font-geist-mono)", fontSize:10}}>{r.cohort}</td>
                    <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color:"#f7b955"}}>{r.m1UnderDeficit.toFixed(1)}%</td>
                    <td style={{textAlign:"right", fontFamily:"var(--font-geist-mono)", color: r.q99UnderDeficit < 35 ? "#50e3c2" : "var(--ink)"}}>{r.q99UnderDeficit.toFixed(1)}%</td>
                    <td style={{fontSize:10, color:"var(--ink-muted)"}}>{r.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="source-path">extreme_rain/primary/</div>
          </div>
          <DetailLink href="/stress/cohort" />
        </section>
        <section className="panel research-panel">
          <div className="panel-sub">Checkpoint sensitivity</div>
          <div className="panel-title">Primary vs All-epoch grid</div>
          <p className="panel-body">
            Primary Q99-exceedance q99 underestimation fraction: <strong>0.440</strong> · Same-epoch grid median: <strong>0.451</strong>.
            Primary는 all-epoch 분포 안에서 유리한 outlier 아님. Stress magnitude는 checkpoint에 민감하므로 supporting diagnostic으로만 사용한다.
          </p>
          <div className="fact-grid">
            <div className="fact-row"><span className="fact-label">primary q99</span><strong style={{color:"#50e3c2"}}>0.440</strong><span>seed 111</span></div>
            <div className="fact-row"><span className="fact-label">epoch grid median</span><strong>0.451</strong><span>18개 조합</span></div>
            <div className="fact-row"><span className="fact-label">false-pos proxy</span><strong style={{color:"#f7b955"}}>1.25×</strong><span>q99 / ARI100</span></div>
          </div>
          <DetailLink href="/stress/checkpoint" />
        </section>
      </div>
    </>
  );
}

/* ── 확정홍수(F) ─────────────────────────────────────────────── */
function ConfirmedFloodSection() {
  return (
    <>
      <p className="section-lede">
        Confirmed flood dashboard는 NWS flood-stage discharge 초과 event만 대상으로 한다.
        성능 구분은 Model 1 peak under-deficit과 Model 2 q99 peak under-deficit의 paired-seed median 차이를 기준으로 보며,
        NOAA Storm Events annotation은 event type 보조 정보로만 사용한다.
      </p>
      <ConfirmedFloodDashboard />
    </>
  );
}

export function generateStaticParams() {
  return Object.values(SECTION_SLUG).map((slug) => ({ section: slug }));
}
