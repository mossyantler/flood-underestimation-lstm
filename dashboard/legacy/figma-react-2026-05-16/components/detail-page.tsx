import Image from "next/image";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowUpRight,
  BarChart3,
  FileText,
  FlaskConical,
  Link2,
  ShieldCheck,
  Table2
} from "lucide-react";

import type { DetailPageSpec, EvidenceLevel } from "@/lib/dashboard-data";

const evidenceLabels: Record<EvidenceLevel, string> = {
  Primary: "Primary evidence",
  Stress: "Stress supplement",
  Diagnostic: "Diagnostic"
};

export function DetailPage({ detail }: { detail: DetailPageSpec }) {
  return (
    <main className="detail-shell">
      <aside className="detail-sidebar">
        <Link href="/" className="detail-brand">
          <span className="brand-tile">
            <FlaskConical size={18} />
          </span>
          <span>
            <small>CAMELSH / detail</small>
            <strong>{detail.sectionLabel}</strong>
          </span>
        </Link>
        <nav className="detail-anchor-list" aria-label="Detail anchors">
          <a href="#readout">Readout</a>
          <a href="#figure">Figure</a>
          <a href="#table">Table</a>
          <a href="#sources">Sources</a>
        </nav>
      </aside>

      <article className="detail-workbench" id="readout">
        <Link href="/" className="back-link">
          <ArrowLeft size={15} />
          Dashboard
        </Link>
        <header className="detail-header-card">
          <span className="section-chip">
            <span>{detail.sectionLabel.slice(0, 1)}</span>
            {detail.sectionLabel}
          </span>
          <h1>{detail.title}</h1>
          <p>{detail.summary}</p>
          <div className="detail-chip-row">
            <EvidenceChip level={detail.evidenceLevel} />
            <span>{detail.figurePreview.title}</span>
          </div>
        </header>

        <section className="detail-grid">
          <div className="panel-card detail-claim-card">
            <div className="detail-section-heading">
              <ShieldCheck size={17} />
              <h2>Claim boundary</h2>
            </div>
            <p>{detail.caveat}</p>
            <p>{detail.readingRule}</p>
          </div>
          <div className="panel-card detail-chart-card">
            <div className="detail-section-heading">
              <BarChart3 size={17} />
              <h2>{detail.chartPreview.title}</h2>
            </div>
            <p>{detail.chartPreview.caption}</p>
            <div className="detail-bars">
              {detail.chartPreview.values.map((item) => (
                <div key={item.label} className="detail-bar-row" data-tone={item.tone}>
                  <span>{item.label}</span>
                  <strong>{formatDetailValue(item.value)}</strong>
                  <em style={{ width: `${Math.max(Math.min(item.value, 100), 4)}%` }} />
                </div>
              ))}
            </div>
          </div>
        </section>

        <figure className="panel-card detail-figure" id="figure">
          <Image
            src={detail.figurePreview.src}
            alt={detail.figurePreview.title}
            width={1400}
            height={840}
            sizes="(max-width: 900px) 100vw, 74vw"
            priority
          />
          <figcaption>
            <strong>{detail.figurePreview.title}</strong>
            <span>{detail.figurePreview.caption}</span>
          </figcaption>
        </figure>

        <section className="detail-grid">
          <div className="panel-card" id="table">
            <div className="detail-section-heading">
              <Table2 size={17} />
              <h2>{detail.tablePreview.title}</h2>
            </div>
            <div className="table-scroll">
              <table className="metric-table">
                <thead>
                  <tr>
                    {detail.tablePreview.columns.map((column) => (
                      <th key={column}>{column}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {detail.tablePreview.rows.map((row) => (
                    <tr key={row.join("|")}>
                      {row.map((cell, index) =>
                        index === 0 ? (
                          <th key={cell}>{cell}</th>
                        ) : (
                          <td key={`${row[0]}-${cell}`}>{cell}</td>
                        )
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="source-note">{detail.tablePreview.sourcePath}</p>
          </div>
          <div className="panel-card" id="sources">
            <div className="detail-section-heading">
              <Link2 size={17} />
              <h2>Source paths</h2>
            </div>
            <ul className="source-list">
              {detail.sourcePaths.map((path) => (
                <li key={path}>{path}</li>
              ))}
            </ul>
            <div className="source-note-block">
              <FileText size={15} />
              <span>{detail.figurePreview.sourcePath}</span>
            </div>
          </div>
        </section>

        <Link href="/" className="detail-return-link">
          Dashboard로 돌아가기
          <ArrowUpRight size={14} />
        </Link>
      </article>
    </main>
  );
}

function EvidenceChip({ level }: { level: EvidenceLevel }) {
  return (
    <span className="evidence-chip" data-level={level.toLowerCase()}>
      {evidenceLabels[level]}
    </span>
  );
}

function formatDetailValue(value: number) {
  if (value >= 100) {
    return Math.round(value).toLocaleString("en-US");
  }
  if (Number.isInteger(value)) {
    return String(value);
  }
  return value.toFixed(1);
}
