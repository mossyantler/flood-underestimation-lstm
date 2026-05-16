"use client";
import { useState } from "react";
import { q99ChartPoints } from "@/lib/dashboard-data";
import { LineCompareChart } from "./inline-svg-chart";

const QUANTILES = ["q50", "q90", "q95", "q99"] as const;
type Quantile = (typeof QUANTILES)[number];

export function ChartCard() {
  const [active, setActive] = useState<Quantile>("q99");

  return (
    <div className="panel">
      <div className="panel-header">
        <div>
          <div className="panel-title">핵심 비교 흐름</div>
          <div className="panel-sub">{active} 분위 과소추정 비교</div>
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

      <div style={{ marginTop: 8 }}>
        <LineCompareChart
          m1={q99ChartPoints.m1}
          m2={q99ChartPoints.m2}
          height={140}
          yMin={30}
          yMax={85}
        />
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
        <div style={{ display: "flex", gap: 12, fontSize: 9, color: "var(--ink-dim)", fontFamily: "var(--font-geist-mono)" }}>
          <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ display: "inline-block", width: 12, height: 2, background: "#f7b955" }} />
            Model 1
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ display: "inline-block", width: 12, height: 2, background: "#6bb4ff" }} />
            Model 2
          </span>
        </div>
        <span style={{ fontSize: 9, color: "var(--ink-dim)", fontFamily: "var(--font-geist-mono)" }}>출처: output/</span>
      </div>
    </div>
  );
}
