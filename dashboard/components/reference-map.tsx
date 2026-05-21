import Link from "next/link";

const referenceGroups = [
  {
    slug: "experiment",
    label: "Experiment refs",
    question: "PUB/PUR, regional holdout, split fairness를 어떤 선행연구와 연결할지 정리한다.",
    sources: ["docs/references/", "docs/experiment/method/"],
    status: "planned",
  },
  {
    slug: "dataset",
    label: "Dataset refs",
    question: "CAMELS, CAMELSH, forcing, static attribute 정의를 추적한다.",
    sources: ["basins/CAMELSH*", "docs/references/"],
    status: "planned",
  },
  {
    slug: "model",
    label: "Model refs",
    question: "LSTM hydrology, quantile regression, pinball loss 근거를 묶는다.",
    sources: ["docs/experiment/method/model/", "docs/references/"],
    status: "planned",
  },
  {
    slug: "basin",
    label: "Basin refs",
    question: "DRBC, flood-stage, hydrologic controls 관련 근거를 모은다.",
    sources: ["basins/drbc_boundary/", "docs/references/"],
    status: "planned",
  },
  {
    slug: "analysis",
    label: "Analysis refs",
    question: "Flood typing, event regime, SHAP, stress test 해석 문헌을 연결한다.",
    sources: ["docs/references/", "output/model_analysis/"],
    status: "planned",
  },
];

export function ReferenceMap() {
  return (
    <>
      <p className="section-lede">
        Reference는 논문 claim을 직접 새로 만들지 않고, 실험 설계와 분석 해석이 어떤 문헌·문서·source artifact에 기대는지 보여 주는 map이다.
        아직 대부분 planned 상태라서 summary보다 위치와 책임 범위를 먼저 고정한다.
      </p>

      <section className="reference-map">
        {referenceGroups.map((group) => (
          <Link href={`/reference/${group.slug}`} className="reference-node" key={group.slug}>
            <span className="reference-node-top">
              <strong>{group.label}</strong>
              <em>{group.status}</em>
            </span>
            <p>{group.question}</p>
            <span className="reference-source-list">
              {group.sources.map((source) => (
                <code key={source}>{source}</code>
              ))}
            </span>
          </Link>
        ))}
      </section>

      <div className="panel-grid">
        <section className="panel research-panel">
          <div className="panel-sub">Boundary</div>
          <div className="panel-title">Reference가 하는 일</div>
          <p className="panel-body">
            Reference는 official result table이 아니다. Experiment, Foundation, Analysis에서 쓰는 개념의 외부 근거와 내부 문서 위치를 연결한다.
            공식 숫자 판단은 output artifact와 analysis docs를 먼저 본다.
          </p>
        </section>

        <section className="panel research-panel">
          <div className="panel-sub">Next curation</div>
          <div className="panel-title">문헌 정리 우선순위</div>
          <div className="source-list">
            <div className="source-row"><span>01</span><strong>Experiment</strong><code>PUB/PUR · DRBC holdout fairness</code></div>
            <div className="source-row"><span>02</span><strong>Model</strong><code>quantile head · pinball loss · calibration caveat</code></div>
            <div className="source-row"><span>03</span><strong>Analysis</strong><code>flood typing · event-regime · stress-test limitation</code></div>
          </div>
        </section>
      </div>
    </>
  );
}
