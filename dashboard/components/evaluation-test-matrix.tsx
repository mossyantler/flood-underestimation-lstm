import Link from "next/link";
import { evaluationTestsSnapshot } from "@/lib/evaluation-tests-data";

const statusLabel: Record<string, string> = {
  ready: "ready",
  "needs-expanded-rerun": "expanded rerun 필요",
  missing: "missing",
};

const statusTone: Record<string, string> = {
  ready: "#50e3c2",
  "needs-expanded-rerun": "#f7b955",
  missing: "#ff6b8a",
};

function summaryLine(test: (typeof evaluationTestsSnapshot.tests)[number]): string {
  if (test.id === "first") {
    return `rows ${test.summary.rows} · seeds ${test.summary.seeds.join("/") || "none"}`;
  }
  if (test.id === "extreme") {
    return `${test.summary.events} events · predictors ${test.summary.predictorCount}`;
  }
  return `${test.summary.events} events · hydrographs ${test.summary.hydrographs}`;
}

export function EvaluationTestMatrix() {
  return (
    <section className="panel research-panel evaluation-matrix">
      <div className="panel-sub">Evaluation scope</div>
      <div className="panel-title">First / extreme / confirmed flood test</div>
      <p className="panel-body">
        Dashboard 공식 해석은 세 test 축으로 나눈다. First와 extreme은 expanded DRBC basin 기준 재평가가 끝난 산출만 공식값으로 올리고,
        confirmed flood는 NWS flood-stage event layer로 별도 유지한다.
      </p>

      <div className="evaluation-grid">
        {evaluationTestsSnapshot.tests.map((test) => (
          <Link key={test.id} href={test.route} className="evaluation-card">
            <div className="evaluation-card-top">
              <span>{test.label}</span>
              <span style={{ color: statusTone[test.status] ?? "var(--ink-muted)" }}>
                {statusLabel[test.status] ?? test.status}
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
  );
}
