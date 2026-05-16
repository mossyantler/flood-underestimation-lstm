"use client";
import { useState } from "react";
import { highFlowQ99, type QuantileId } from "@/lib/dashboard-data";

const QUANTILES: QuantileId[] = ["q50", "q90", "q95", "q99"];

function seedMedian(vals: [number, number, number]): number {
  const sorted = [...vals].sort((a, b) => a - b);
  return sorted[1];
}

export function ChartCard() {
  const [active, setActive] = useState<QuantileId>("q99");

  const m1Row = highFlowQ99[0];
  const m2Row = highFlowQ99.find((r) => r.predictor === `M2 ${active}`);

  const m1Median = seedMedian(m1Row.undestFrac);
  const m2Median = m2Row ? seedMedian(m2Row.undestFrac) : 0;

  const bars = [
    { label: "Model 1", sub: `median bias ${[m1Row.medRelBias[0], m1Row.medRelBias[1], m1Row.medRelBias[2]].map(v => (v >= 0 ? "+" : "") + v.toFixed(1) + "%").join(" / ")}`, val: m1Median, accent: "#f7b955" },
    { label: `M2 ${active}`, sub: m2Row ? `median bias ${[m2Row.medRelBias[0], m2Row.medRelBias[1], m2Row.medRelBias[2]].map(v => (v >= 0 ? "+" : "") + v.toFixed(1) + "%").join(" / ")}` : "—", val: m2Median, accent: "#6bb4ff" },
  ];

  const seedLabels = ["seed 111", "seed 222", "seed 444"];

  return (
    <div className="panel">
      <div className="panel-header">
        <div>
          <div className="panel-title">Q99 exceedance 과소추정률</div>
          <div className="panel-sub">DRBC 38 · top 1% flow stratum · {active}</div>
        </div>
        <div className="seg-ctrl">
          {QUANTILES.map((q) => (
            <button
              key={q}
              type="button"
              className="seg-btn"
              data-active={q === active ? "true" : "false"}
              onClick={() => setActive(q)}
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      <div className="bar-ladder" aria-label="Q99 exceedance 과소추정률 비교">
        {bars.map((bar) => (
          <div className="bar-row" key={bar.label}>
            <div className="bar-label">
              <strong>{bar.label}</strong>
              <span>{bar.sub}</span>
            </div>
            <div className="bar-track">
              <span
                className="bar-fill"
                style={{ width: `${bar.val}%`, background: bar.accent }}
              />
            </div>
            <span className="bar-value">{bar.val.toFixed(1)}%</span>
          </div>
        ))}

        <div style={{ display: "grid", gap: 4, marginTop: 6 }}>
          {seedLabels.map((sl, i) => {
            const m1v = m1Row.undestFrac[i];
            const m2v = m2Row?.undestFrac[i];
            return (
              <div key={sl} style={{ display: "flex", gap: 8, fontSize: 9, color: "var(--ink-dim)", fontFamily: "var(--font-geist-mono)" }}>
                <span style={{ width: 52, flexShrink: 0 }}>{sl}</span>
                <span style={{ color: "#f7b955" }}>M1 {m1v.toFixed(1)}%</span>
                {m2v !== undefined && (
                  <span style={{ color: "#6bb4ff" }}>{active} {m2v.toFixed(1)}%</span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="chart-footnote">
        <span>값이 낮을수록 과소추정 적음. 출처: flow_strata_predictor_summary.csv</span>
        <span>primary · basin_top1</span>
      </div>
    </div>
  );
}
