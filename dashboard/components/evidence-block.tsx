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

const LOCAL_ABSOLUTE_PATH = /^\/(?:Users|Volumes|private|tmp|var|opt|home)\//;

function isLinkablePath(path: string) {
  if (/^https?:\/\//.test(path)) return true;
  return path.startsWith("/") && !path.startsWith("//") && !LOCAL_ABSOLUTE_PATH.test(path);
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

  return (
    <article className="evidence-row" data-role={item.role}>
      <div>
        <span className="evidence-row-kicker">{ROLE_LABEL[item.role]} · {item.kind}</span>
        <strong>{item.title}</strong>
        {item.shortDescription && <p>{item.shortDescription}</p>}
      </div>
      <code>{item.sourcePath}</code>
      {canOpen ? (
        <Link href={path} className="panel-detail-link">열기</Link>
      ) : (
        <span className="panel-detail-link" aria-label="local source path">source</span>
      )}
    </article>
  );
}
