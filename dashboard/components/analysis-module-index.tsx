import Link from "next/link";
import { ConfirmedFloodDashboard } from "@/components/confirmed-flood-dashboard";
import { FigurePreviewGrid } from "@/components/figure-preview-grid";
import { KpiStrip } from "@/components/kpi-card";
import {
  calibrationRows,
  eventRegimeRows,
  highFlowQ99,
  peakHourRows,
  resultsKpis,
  stressKpis,
  stressRows,
} from "@/lib/dashboard-data";
import {
  figureAssets,
} from "@/lib/figure-assets";
import { confirmedFloodSnapshot } from "@/lib/confirmed-flood-data";

function median(values: readonly number[]): number {
  return [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)] ?? 0;
}

export function AnalysisModuleIndex() {
  const m1Q99 = highFlowQ99.find((row) => row.predictor === "Model 1");
  const m2Q99 = highFlowQ99.find((row) => row.predictor === "M2 q99");
  const peakQ99 = peakHourRows.find((row) => row.predictor === "M2 q99");
  const confirmed = confirmedFloodSnapshot.summary;

  return (
    <>
      <p className="section-lede">
        Analysis는 이전 Results & Analysis 축을 통합한 공간이다. Main result, hydrograph, stress, confirmed flood, event-regime,
        calibration처럼 분석 type마다 다른 layout을 허용하되, top-level section 이름은 Analysis로 고정한다.
      </p>

      <KpiStrip items={resultsKpis} />

      <section className="analysis-module-grid" aria-label="Analysis modules">
        <Link href="/analysis/main-result" className="analysis-module-card" data-tone="main">
          <span>Main result</span>
          <strong>{m2Q99 ? `${median(m2Q99.undestFrac).toFixed(1)}%` : "44.9%"}</strong>
          <p>
            Q99 exceedance에서 Model 1 {m1Q99 ? `${median(m1Q99.undestFrac).toFixed(1)}%` : "71.5%"} 과소추정이
            M2 q99 기준으로 낮아지는지 본다.
          </p>
          <code>overall_analysis/main_comparison/</code>
        </Link>

        <Link href="/analysis/hydrograph" className="analysis-module-card">
          <span>Hydrograph</span>
          <strong>{peakQ99 ? `${median(peakQ99.undestFrac).toFixed(1)}%` : "55.3%"}</strong>
          <p>Observed peak hour와 representative hydrograph gallery를 연결해 peak timing과 magnitude evidence를 본다.</p>
          <code>observed_q99_hydrograph_gallery_index.html</code>
        </Link>

        <Link href="/analysis/stress" className="analysis-module-card" data-tone="warn">
          <span>Stress test</span>
          <strong>{stressRows[0]?.q99UnderDeficit.toFixed(1) ?? "27.3"}%</strong>
          <p>Extreme-rain historical stress는 supporting diagnostic이며 temporal independence claim에는 쓰지 않는다.</p>
          <code>output/model_analysis/extreme_rain/primary/</code>
        </Link>

        <Link href="/analysis/confirmed-flood" className="analysis-module-card" data-tone="flood">
          <span>Confirmed flood</span>
          <strong>{confirmed.events}</strong>
          <p>NWS flood-stage event layer다. Old confirmed flood top-level F는 여기로 흡수한다.</p>
          <code>output/model_analysis/confirmed_flood/</code>
        </Link>

        <Link href="/analysis/event-regime" className="analysis-module-card">
          <span>Event regime</span>
          <strong>{eventRegimeRows.reduce((sum, row) => sum + row.nEvents, 0)}</strong>
          <p>570개 high-flow event를 regime별로 나눠 q99 effect의 조건부 강도를 본다.</p>
          <code>event_regime_paired_delta_compact.csv</code>
        </Link>

        <Link href="/analysis/calibration" className="analysis-module-card" data-tone="calibration">
          <span>Calibration</span>
          <strong>{calibrationRows.find((row) => row.quantile === "q99")?.allHourCoverage.toFixed(3) ?? "0.835"}</strong>
          <p>q99가 peak bias 완화에는 유효해도 calibrated 99% interval이 아님을 분리해 표시한다.</p>
          <code>probabilistic_diagnostics_report.md</code>
        </Link>
      </section>

      <section className="panel research-panel">
        <div className="panel-sub">Paper figure board</div>
        <div className="panel-title">Main result / event regime / stress figure</div>
        <FigurePreviewGrid
          figures={[
            figureAssets.highFlowQuantiles,
            figureAssets.eventRegimeDelta,
            figureAssets.quantileCalibration,
            figureAssets.stressTradeoff,
            figureAssets.checkpointSensitivity,
          ]}
          compact
        />
      </section>

      <div className="panel-grid">
        <section className="panel research-panel">
          <div className="panel-sub">Q99 exceedance · seed median</div>
          <div className="panel-title">Top 1% flow underestimation</div>
          <div className="data-block">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Predictor</th>
                  <th style={{ textAlign: "right" }}>111</th>
                  <th style={{ textAlign: "right" }}>222</th>
                  <th style={{ textAlign: "right" }}>444</th>
                  <th style={{ textAlign: "right" }}>Median</th>
                </tr>
              </thead>
              <tbody>
                {highFlowQ99.map((row) => (
                  <tr key={row.predictor}>
                    <td style={{ color: row.predictor === "M2 q99" ? "#6bb4ff" : "var(--ink-body)", fontWeight: row.predictor === "Model 1" ? 700 : 500 }}>
                      {row.predictor}
                    </td>
                    {row.undestFrac.map((value, index) => (
                      <td key={index} style={{ textAlign: "right", fontFamily: "var(--font-geist-mono)" }}>{value.toFixed(1)}%</td>
                    ))}
                    <td style={{ textAlign: "right", fontFamily: "var(--font-geist-mono)", color: row.predictor === "M2 q99" ? "#50e3c2" : "var(--ink)" }}>
                      {median(row.undestFrac).toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="source-path">flow_strata_predictor_summary.csv · primary · basin_top1</div>
          </div>
        </section>

        <section className="panel research-panel">
          <div className="panel-sub">Stress guardrail</div>
          <div className="panel-title">Historical stress cohort</div>
          <KpiStrip items={stressKpis} />
          <div className="data-block">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Cohort</th>
                  <th style={{ textAlign: "right" }}>M1</th>
                  <th style={{ textAlign: "right" }}>q99</th>
                  <th>Note</th>
                </tr>
              </thead>
              <tbody>
                {stressRows.map((row) => (
                  <tr key={row.cohort}>
                    <td>{row.cohort}</td>
                    <td style={{ textAlign: "right", fontFamily: "var(--font-geist-mono)", color: "#f7b955" }}>{row.m1UnderDeficit.toFixed(1)}%</td>
                    <td style={{ textAlign: "right", fontFamily: "var(--font-geist-mono)", color: "#50e3c2" }}>{row.q99UnderDeficit.toFixed(1)}%</td>
                    <td>{row.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <section className="panel research-panel">
        <div className="panel-sub">Confirmed flood workbench</div>
        <div className="panel-title">NWS flood-stage event audit</div>
        <p className="panel-body">
          Confirmed flood old top-level은 Analysis 안의 독립 module로 유지한다. Event-level audit, map, filter, hydrograph manifest는 기존 component를 그대로 사용한다.
        </p>
      </section>
      <ConfirmedFloodDashboard />
    </>
  );
}
