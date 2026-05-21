import Image from "next/image";
import Link from "next/link";
import {
  ArrowLeft,
  BarChart3,
  BookOpenCheck,
  FileText,
  FlaskConical,
  Link2,
  ShieldCheck,
  Table2
} from "lucide-react";

import {
  dashboardData,
  type DetailPageSpec,
  type EvidenceLevel
} from "@/lib/dashboard-data";

const evidenceLabels: Record<EvidenceLevel, string> = {
  Primary: "Primary evidence",
  Stress: "Stress supplement",
  Diagnostic: "Diagnostic"
};

const articleAnchors = [
  { href: "#overview", label: "Overview" },
  { href: "#figure", label: "Figure" },
  { href: "#reading", label: "Reading" },
  { href: "#boundary", label: "Boundary" }
];

export function DetailPage({ detail }: { detail: DetailPageSpec }) {
  const currentIndex = dashboardData.details.findIndex((item) => item.slug === detail.slug);
  const nextDetail =
    currentIndex >= 0
      ? dashboardData.details[(currentIndex + 1) % dashboardData.details.length]
      : undefined;

  return (
    <main className="detail-shell">
      <DetailSidebar activeSlug={detail.slug} />

      <article className="detail-article" id="overview">
        <div className="detail-article-inner">
          <Link href="/" className="detail-back-link">
            <ArrowLeft size={15} />
            Dashboard
          </Link>

          <header className="detail-article-header">
            <p className="mono-label">{detail.sectionLabel} detail</p>
            <h1>{detail.title}</h1>
            <p>{detail.summary}</p>
            <div className="detail-chip-row" aria-label="Detail metadata">
              <EvidenceChip level={detail.evidenceLevel} />
              <span>{detail.sectionLabel}</span>
              <span>{detail.figurePreview.title}</span>
            </div>
          </header>

          <div className="detail-inline-boundary">
            <ShieldCheck size={17} />
            <div>
              <span>Boundary</span>
              <p>{detail.caveat}</p>
            </div>
          </div>

          <figure className="detail-article-figure" id="figure">
            <div className="detail-figure-shell">
              <Image
                src={detail.figurePreview.src}
                alt={detail.figurePreview.title}
                width={1400}
                height={840}
                sizes="(max-width: 900px) 100vw, (max-width: 1280px) 68vw, 860px"
                priority
              />
            </div>
            <figcaption>
              <strong>{detail.figurePreview.title}</strong>
              <span>{detail.figurePreview.caption}</span>
            </figcaption>
          </figure>

          <section className="detail-article-section" id="reading">
            <p className="mono-label">reading rule</p>
            <h2>이 페이지를 읽는 기준</h2>
            <p>{detail.readingRule}</p>
          </section>

          <section className="detail-article-section" id="boundary">
            <p className="mono-label">comparison context</p>
            <h2>주장을 제한하는 실험 경계</h2>
            <p>{detail.comparisonContext}</p>
          </section>

          {nextDetail ? (
            <Link href={`/details/${nextDetail.slug}`} className="detail-next-link">
              <span>Next detail</span>
              <strong>{nextDetail.title}</strong>
            </Link>
          ) : null}
        </div>
      </article>

      <DetailRail detail={detail} />
    </main>
  );
}

function DetailSidebar({ activeSlug }: { activeSlug: string }) {
  return (
    <aside className="detail-sidebar" aria-label="Detail navigation">
      <Link href="/" className="detail-brand-link">
        <div className="brand-mark" aria-hidden="true">
          <FlaskConical size={16} />
        </div>
        <span>
          <small>CAMELSH / detail</small>
          <strong>Analysis article</strong>
        </span>
      </Link>

      <nav className="detail-anchor-nav" aria-label="Article sections">
        {articleAnchors.map((anchor) => (
          <a key={anchor.href} href={anchor.href}>
            {anchor.label}
          </a>
        ))}
      </nav>

      <div className="detail-sidebar-divider" />

      <nav className="detail-route-list" aria-label="Detail pages">
        {dashboardData.details.map((item) => (
          <Link
            key={item.slug}
            href={`/details/${item.slug}`}
            data-active={item.slug === activeSlug}
          >
            <span>{item.sectionLabel}</span>
            <strong>{item.title}</strong>
          </Link>
        ))}
      </nav>
    </aside>
  );
}

function DetailRail({ detail }: { detail: DetailPageSpec }) {
  return (
    <aside className="detail-rail" aria-label="Source and claim rail">
      <div className="detail-rail-inner">
        <section className="detail-rail-section detail-claim-rail">
          <div className="detail-rail-heading">
            <BookOpenCheck size={16} />
            <h2>Claim</h2>
          </div>
          <EvidenceChip level={detail.evidenceLevel} />
          <p>{detail.comparisonContext}</p>
        </section>

        <section className="detail-rail-section">
          <div className="detail-rail-heading">
            <BarChart3 size={16} />
            <h2>{detail.chartPreview.title}</h2>
          </div>
          <p className="detail-rail-note">{detail.chartPreview.caption}</p>
          <CompactMetricList values={detail.chartPreview.values} />
        </section>

        <section className="detail-rail-section">
          <div className="detail-rail-heading">
            <Table2 size={16} />
            <h2>{detail.tablePreview.title}</h2>
          </div>
          <p className="detail-rail-source">{detail.tablePreview.sourcePath}</p>
          <ul className="detail-row-list">
            {detail.tablePreview.rows.slice(0, 4).map((row) => (
              <li key={row.join("|")}>
                <span>{row[0]}</span>
                <strong>{formatRowSummary(row)}</strong>
              </li>
            ))}
          </ul>
        </section>

        <section className="detail-rail-section">
          <div className="detail-rail-heading">
            <Link2 size={16} />
            <h2>Sources</h2>
          </div>
          <ul className="detail-source-list">
            {detail.sourcePaths.map((path) => (
              <li key={path}>{path}</li>
            ))}
          </ul>
        </section>

        <section className="detail-rail-section">
          <div className="detail-rail-heading">
            <FileText size={16} />
            <h2>Figure source</h2>
          </div>
          <p className="detail-rail-source">{detail.figurePreview.sourcePath}</p>
        </section>
      </div>
    </aside>
  );
}

function EvidenceChip({ level }: { level: EvidenceLevel }) {
  return (
    <span className="evidence-chip" data-level={level.toLowerCase()}>
      {evidenceLabels[level]}
    </span>
  );
}

function CompactMetricList({
  values
}: {
  values: DetailPageSpec["chartPreview"]["values"];
}) {
  const maxValue = Math.max(...values.map((item) => item.value), 1);

  return (
    <ul className="detail-metric-list">
      {values.map((item) => (
        <li key={item.label} data-tone={item.tone}>
          <div>
            <span>{item.label}</span>
            <strong>{formatChartValue(item.value)}</strong>
          </div>
          <span className="detail-metric-track" aria-hidden="true">
            <span style={{ width: `${Math.max((item.value / maxValue) * 100, 4)}%` }} />
          </span>
        </li>
      ))}
    </ul>
  );
}

function formatRowSummary(row: string[]) {
  return row.slice(1).join(" · ");
}

function formatChartValue(value: number) {
  if (value >= 100) {
    return Math.round(value).toLocaleString("en-US");
  }
  if (value % 1 === 0) {
    return String(value);
  }
  return value.toFixed(1);
}
