import Link from "next/link";
import type { AnalysisModuleCopy, EvidenceItem } from "@/lib/evidence-types";

type EvidenceBlockProps = {
  copy: AnalysisModuleCopy;
  items: readonly EvidenceItem[];
};

const ROLE_LABEL: Record<EvidenceItem["role"], string> = {
  canonical: "공식",
  supporting: "보조",
  archive: "보관",
};

const APP_ROUTE_PREFIXES = ["/overview", "/experiment", "/foundation", "/analysis", "/reference"] as const;

function isHttpUrl(path: string) {
  try {
    const url = new URL(path);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

function isAppRoute(path: string) {
  return APP_ROUTE_PREFIXES.some((prefix) => path === prefix || path.startsWith(`${prefix}/`));
}

function isPublicAsset(path: string) {
  return path === "/favicon.svg" || path.startsWith("/figures/");
}

function isLocalAbsolutePath(path: string) {
  return path.startsWith("/") && !path.startsWith("//") && !isAppRoute(path) && !isPublicAsset(path);
}

function isLinkablePath(path: string) {
  return isHttpUrl(path) || isAppRoute(path) || isPublicAsset(path);
}

function displaySourcePath(path: string) {
  return isLocalAbsolutePath(path) ? "local source path" : path;
}

export function EvidenceBlock({ copy, items }: EvidenceBlockProps) {
  const visibleItems = [...items].sort((a, b) => a.priority - b.priority || a.title.localeCompare(b.title));

  return (
    <section className="evidence-block">
      <div className="evidence-copy-grid">
        <article className="evidence-copy-card">
          <span>분석 목적</span>
          <p>{copy.analysisPurpose}</p>
        </article>
        <article className="evidence-copy-card">
          <span>배경 설명</span>
          <p>{copy.background}</p>
        </article>
        <article className="evidence-copy-card">
          <span>핵심 데이터</span>
          <p>{copy.coreData}</p>
        </article>
        <article className="evidence-copy-card">
          <span>해석 방법</span>
          <p>{copy.interpretationMethod}</p>
        </article>
        <article className="evidence-copy-card evidence-copy-card-wide">
          <span>현재 판단</span>
          <p>{copy.currentJudgment}</p>
        </article>
      </div>
      <div className="evidence-list" aria-label={`${copy.title} 근거 경로`}>
        {visibleItems.map((item) => (
          <EvidenceRow key={item.id} item={item} />
        ))}
      </div>
    </section>
  );
}

function EvidenceRow({ item }: { item: EvidenceItem }) {
  const path = item.chartPath ?? item.galleryPath ?? item.docPath ?? item.tablePath ?? item.sourcePath;
  const canOpen = isLinkablePath(path);
  const disabledLabel = isLocalAbsolutePath(path) ? "local source path" : "source";

  return (
    <article className="evidence-row" data-role={item.role}>
      <div>
        <span className="evidence-row-kicker">{ROLE_LABEL[item.role]} · {item.kind}</span>
        <strong>{item.title}</strong>
        {item.shortDescription && <p>{item.shortDescription}</p>}
      </div>
      <code>{displaySourcePath(item.sourcePath)}</code>
      {canOpen ? (
        <Link href={path} className="panel-detail-link">열기</Link>
      ) : (
        <span className="panel-detail-link" aria-label={disabledLabel}>{disabledLabel}</span>
      )}
    </article>
  );
}
