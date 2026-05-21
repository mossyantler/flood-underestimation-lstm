import Link from "next/link";
import { overviewStatusKpis, readinessItems, type DashboardStatus } from "@/lib/overview-data";

const STATUS_TEXT: Record<DashboardStatus, string> = {
  ready: "완료",
  "in-progress": "진행중",
  "needs-rerun": "rerun 필요",
  planned: "준비중",
};

export function StatusBoard() {
  return (
    <section className="status-board">
      <div className="status-kpi-grid">
        {overviewStatusKpis.map((item) => (
          <Link
            aria-label={`${item.label}: ${STATUS_TEXT[item.status]}`}
            className="status-kpi"
            data-status={item.status}
            href={item.href}
            key={item.label}
          >
            <span className="status-kpi-top">
              <span>{item.label}</span>
              <em>{STATUS_TEXT[item.status]}</em>
            </span>
            <strong>{item.value}</strong>
            <p>{item.note}</p>
            <code>{item.source}</code>
          </Link>
        ))}
      </div>

      <div className="panel research-panel">
        <div className="panel-sub">Analysis readiness</div>
        <div className="panel-title">다음에 봐야 할 작업</div>
        <div className="readiness-list">
          {readinessItems.map((item) => (
            <Link href={item.href} className="readiness-row" data-status={item.status} key={item.name}>
              <span>
                <strong>{item.name}</strong>
                <em>{STATUS_TEXT[item.status]}</em>
              </span>
              <p>{item.question}</p>
              <small>{item.currentEvidence}</small>
              <small>{item.nextAction}</small>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
