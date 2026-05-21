import Link from "next/link";
import {
  checkpointRows,
  datasetRows,
  nseDeltaSummary,
  primaryPerformance,
} from "@/lib/dashboard-data";
import { evaluationTestsSnapshot } from "@/lib/evaluation-tests-data";

const workflowSteps = [
  {
    label: "Split",
    body: "DRBC holdout 밖 quality-pass basin에서 subset300을 고정하고 seed 111/222/444가 같은 train/validation universe를 쓴다.",
    source: "configs/basin_splits/",
  },
  {
    label: "Train",
    body: "Model 1 deterministic LSTM과 Model 2 quantile head를 같은 backbone 조건으로 학습한다.",
    source: "scripts/runs/official/",
  },
  {
    label: "Select",
    body: "Primary epoch는 DRBC test가 아니라 non-DRBC validation median NSE 기준으로 고른다.",
    source: "output/model_analysis/overall_analysis/main_comparison/tables/primary_epoch_summary.csv",
  },
  {
    label: "Evaluate",
    body: "Primary result, extreme-rain stress, confirmed flood layer를 서로 다른 test surface로 분리해 본다.",
    source: "dashboard/lib/evaluation-tests-data.ts",
  },
];

const testRoutes: Record<string, string> = {
  first: "/experiment/test-matrix",
  extreme: "/analysis/stress",
  confirmed: "/analysis/confirmed-flood",
};

const testStatusLabel: Record<string, string> = {
  ready: "ready",
  "needs-expanded-rerun": "expanded rerun 필요",
  missing: "missing",
};

const testStatusTone: Record<string, string> = {
  ready: "#50e3c2",
  "needs-expanded-rerun": "#f7b955",
  missing: "#ff6b8a",
};

function summaryLine(test: (typeof evaluationTestsSnapshot.tests)[number]): string {
  if (test.id === "first") return `rows ${test.summary.rows} · seeds ${test.summary.seeds.join("/") || "none"}`;
  if (test.id === "extreme") return `${test.summary.events} events · predictors ${test.summary.predictorCount}`;
  return `${test.summary.events} events · hydrographs ${test.summary.hydrographs}`;
}

export function WorkflowPanel() {
  const model1 = primaryPerformance.filter((row) => row.model === "Model 1");
  const model2 = primaryPerformance.filter((row) => row.model === "Model 2 q50");

  return (
    <>
      <p className="section-lede">
        Experiment는 논문 공식 비교축을 관리한다. 여기서는 Model 1 vs Model 2의 공정한 paired seed 조건, split 정책, checkpoint 선택 기준,
        test surface 상태를 한 화면에서 확인한다.
      </p>

      <div className="workflow-step-grid">
        {workflowSteps.map((step, index) => (
          <section className="panel research-panel workflow-step" key={step.label}>
            <div className="panel-sub">0{index + 1}</div>
            <div className="panel-title">{step.label}</div>
            <p className="panel-body">{step.body}</p>
            <div className="source-path">{step.source}</div>
          </section>
        ))}
      </div>

      <div className="panel-grid">
        <section className="panel research-panel">
          <div className="panel-sub">Official comparison</div>
          <div className="panel-title">Model 1 vs Model 2 primary epoch</div>
          <div className="data-block">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Seed</th>
                  <th style={{ textAlign: "right" }}>M1 epoch</th>
                  <th style={{ textAlign: "right" }}>M2 epoch</th>
                  <th style={{ textAlign: "right" }}>Delta NSE</th>
                  <th style={{ textAlign: "right" }}>Improved</th>
                </tr>
              </thead>
              <tbody>
                {nseDeltaSummary.map((delta) => {
                  const m1 = model1.find((row) => row.seed === delta.seed);
                  const m2 = model2.find((row) => row.seed === delta.seed);
                  return (
                    <tr key={delta.seed}>
                      <td>{delta.seed}</td>
                      <td style={{ textAlign: "right", fontFamily: "var(--font-geist-mono)" }}>{m1?.epoch ?? "-"}</td>
                      <td style={{ textAlign: "right", fontFamily: "var(--font-geist-mono)" }}>{m2?.epoch ?? "-"}</td>
                      <td style={{ textAlign: "right", fontFamily: "var(--font-geist-mono)", color: "#50e3c2" }}>
                        +{delta.nseDelta.toFixed(3)}
                      </td>
                      <td style={{ textAlign: "right", fontFamily: "var(--font-geist-mono)" }}>
                        {(delta.nseImproved * 100).toFixed(0)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div className="source-path">primary_epoch_delta_summary.csv</div>
          </div>
          <Link href="/experiment/comparison" className="panel-detail-link">자세히</Link>
        </section>

        <section className="panel research-panel">
          <div className="panel-sub">Split policy</div>
          <div className="panel-title">Basin universe guardrail</div>
          <div className="fact-grid">
            {datasetRows.map((row) => (
              <div className="fact-row" key={row.split}>
                <span className="fact-label">{row.split}</span>
                <strong>{row.basins.toLocaleString()}</strong>
                <span>{row.role}</span>
              </div>
            ))}
          </div>
          <div className="source-path">configs/basin_splits/ · data/CAMELSH_generic/</div>
          <Link href="/experiment/split-policy" className="panel-detail-link">자세히</Link>
        </section>
      </div>

      <section className="panel research-panel">
        <div className="panel-sub">Checkpoint contract</div>
        <div className="panel-title">재현성 기준</div>
        <div className="workflow-checkpoint-list">
          {checkpointRows.map((row) => (
            <div className="checkpoint-row" key={row.key}>
              <span className="checkpoint-key">{row.key}</span>
              <span className="checkpoint-val">{row.value}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="panel research-panel evaluation-matrix">
        <div className="panel-sub">Evaluation scope</div>
        <div className="panel-title">First / extreme / confirmed flood test</div>
        <p className="panel-body">
          Dashboard 공식 해석은 세 test 축으로 나눈다. First와 extreme은 expanded DRBC basin 기준 재평가가 끝난 산출만 공식값으로 올리고,
          confirmed flood는 NWS flood-stage event layer로 Analysis에 흡수한다.
        </p>
        <div className="evaluation-grid">
          {evaluationTestsSnapshot.tests.map((test) => (
            <Link key={test.id} href={testRoutes[test.id] ?? "/experiment/test-matrix"} className="evaluation-card">
              <div className="evaluation-card-top">
                <span>{test.label}</span>
                <span style={{ color: testStatusTone[test.status] ?? "var(--ink-muted)" }}>
                  {testStatusLabel[test.status] ?? test.status}
                </span>
              </div>
              <strong>{test.coverage}</strong>
              <p>{test.interpretation}</p>
              <div className="source-path">{summaryLine(test)}</div>
            </Link>
          ))}
        </div>
        <div className="source-path">
          generated {evaluationTestsSnapshot.generatedAt} · source: database/local/duckdb/camels.duckdb + output/model_analysis/
        </div>
      </section>
    </>
  );
}
