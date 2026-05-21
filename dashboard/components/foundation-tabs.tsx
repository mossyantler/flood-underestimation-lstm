"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { datasetRows, nseDeltaSummary, primaryPerformance } from "@/lib/dashboard-data";

type FoundationTab = "dataset" | "model" | "basin";

const tabs: { id: FoundationTab; label: string; source: string }[] = [
  { id: "dataset", label: "Dataset", source: "basins/ · data/ · output/model_analysis/" },
  { id: "model", label: "Model", source: "configs/ · docs/experiment/method/model/" },
  { id: "basin", label: "Basin", source: "basins/drbc_boundary/ · output/basin/drbc/analysis/" },
];

export function FoundationTabs() {
  const [active, setActive] = useState<FoundationTab>("dataset");
  const selected = useMemo(() => tabs.find((tab) => tab.id === active) ?? tabs[0], [active]);

  return (
    <>
      <p className="section-lede">
        Foundation은 분석 결과를 해석하기 전에 고정해야 하는 기반 정보다. Dataset, model, basin universe를 분리해
        어떤 값이 source-of-truth이고 어떤 값이 dashboard snapshot인지 확인한다.
      </p>

      <section className="panel research-panel foundation-shell">
        <div className="foundation-tabbar" role="tablist" aria-label="Foundation tabs">
          {tabs.map((tab) => (
            <button
              aria-selected={active === tab.id}
              className="foundation-tab"
              data-active={active === tab.id}
              key={tab.id}
              onClick={() => setActive(tab.id)}
              role="tab"
              type="button"
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="foundation-tab-panel" role="tabpanel">
          <div>
            <div className="panel-sub">{selected.label}</div>
            <div className="panel-title">{foundationTitle(active)}</div>
          </div>
          {active === "dataset" && <DatasetFoundation />}
          {active === "model" && <ModelFoundation />}
          {active === "basin" && <BasinFoundation />}
          <div className="source-path">{selected.source}</div>
          <Link href={`/foundation/${active}`} className="panel-detail-link">자세히</Link>
        </div>
      </section>
    </>
  );
}

function foundationTitle(tab: FoundationTab): string {
  if (tab === "dataset") return "CAMELSH hourly와 산출물 경계";
  if (tab === "model") return "Head-only contrast";
  return "DRBC holdout와 training pool";
}

function DatasetFoundation() {
  return (
    <div className="foundation-grid">
      <section className="foundation-card">
        <strong>Split 구성</strong>
        <div className="data-block">
          <table className="data-table">
            <thead>
              <tr>
                <th>Split</th>
                <th style={{ textAlign: "right" }}>Basins</th>
                <th>Role</th>
              </tr>
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
      </section>
      <section className="foundation-card">
        <strong>해석 기준</strong>
        <p>
          CAMELSH hourly가 기본 데이터셋이다. Prepared data는 재생성 가능한 산출물이고, 공식 split 정의는 configs 쪽을 기준으로 본다.
          DRBC primary test와 historical stress는 같은 의미의 독립 test가 아니다.
        </p>
      </section>
    </div>
  );
}

function ModelFoundation() {
  return (
    <div className="foundation-grid">
      <section className="foundation-card">
        <strong>Model 1 / Model 2 구조</strong>
        <p>
          Backbone은 동일한 multi-basin LSTM이다. Model 1은 deterministic point output이고, Model 2는 quantile head(q50/q90/q95/q99)만 붙여
          output design 효과를 본다.
        </p>
        <div className="fact-grid">
          <div className="fact-row"><span className="fact-label">Seeds</span><strong>111 / 222 / 444</strong><span>paired comparison</span></div>
          <div className="fact-row"><span className="fact-label">Excluded</span><strong style={{ color: "#ff6b8a" }}>333</strong><span>Model 2 NaN loss</span></div>
        </div>
      </section>
      <section className="foundation-card">
        <strong>Guardrail metric</strong>
        <div className="data-block">
          <table className="data-table">
            <thead>
              <tr>
                <th>Seed</th>
                <th style={{ textAlign: "right" }}>Delta NSE</th>
                <th style={{ textAlign: "right" }}>Improved</th>
              </tr>
            </thead>
            <tbody>
              {nseDeltaSummary.map((row) => (
                <tr key={row.seed}>
                  <td>{row.seed}</td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-geist-mono)", color: "#50e3c2" }}>+{row.nseDelta.toFixed(3)}</td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-geist-mono)" }}>{(row.nseImproved * 100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function BasinFoundation() {
  const drbc = datasetRows.find((row) => row.split === "DRBC holdout");
  const pool = datasetRows.find((row) => row.split === "Training pool");
  const epochs = primaryPerformance.map((row) => `${row.seed}:${row.epoch}`).join(" · ");

  return (
    <div className="foundation-grid">
      <section className="foundation-card">
        <strong>DRBC 기준</strong>
        <p>
          공식 boundary는 <code>basins/drbc_boundary/drb_bnd_polygon.shp</code>다.
          DRBC holdout은 regional evaluation region이고 training pool은 DRBC 밖 quality-pass basin으로 둔다.
        </p>
        <div className="fact-grid">
          <div className="fact-row"><span className="fact-label">DRBC holdout</span><strong>{drbc?.basins ?? 38}</strong><span>quality-pass test</span></div>
          <div className="fact-row"><span className="fact-label">Training pool</span><strong>{pool?.basins.toLocaleString() ?? "1,923"}</strong><span>non-DRBC quality-pass</span></div>
        </div>
      </section>
      <section className="foundation-card">
        <strong>Primary epoch trace</strong>
        <p>
          Basin별 test score로 epoch를 다시 고르지 않는다. Primary epoch는 validation 기준으로 고르고,
          downstream analysis는 그 checkpoint에서 나온 snapshot을 따라간다.
        </p>
        <div className="source-path">{epochs}</div>
      </section>
    </div>
  );
}
