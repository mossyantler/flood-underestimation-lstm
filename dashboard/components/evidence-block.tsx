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

function coreDataItems(coreData: string) {
  return coreData
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function interpretationNodes(copy: AnalysisModuleCopy) {
  if (copy.moduleId === "foundation/dataset") {
    return [
      { label: "Input", text: "CAMELSH source와 screening logic" },
      { label: "Result", text: "model inference와 raw metric output" },
      { label: "Analysis", text: "chart/table로 가공한 해석 layer" },
    ];
  }

  return [
    { label: "Source", text: copy.coreData },
    { label: "Read", text: copy.interpretationMethod },
    { label: "Judge", text: copy.currentJudgment },
  ];
}

export function EvidenceBlock({ copy, items }: EvidenceBlockProps) {
  const visibleItems = [...items].sort((a, b) => a.priority - b.priority || a.title.localeCompare(b.title));
  const dataItems = coreDataItems(copy.coreData);
  const interpretation = interpretationNodes(copy);

  return (
    <section className="evidence-block">
      <div className="evidence-copy-grid">
        <article className="evidence-copy-card">
          <span>분석 목적</span>
          <p>{copy.analysisPurpose}</p>
        </article>
        <article className="evidence-copy-card">
          <span>핵심 데이터</span>
          <ul className="evidence-data-list">
            {dataItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
        <article className="evidence-copy-card evidence-copy-card-wide">
          <span>해석 방법</span>
          <div className="evidence-flow" aria-label={`${copy.title} 해석 구조`}>
            {interpretation.map((step, index) => (
              <div className="evidence-flow-step" key={step.label}>
                <div>
                  <strong>{step.label}</strong>
                  <p>{step.text}</p>
                </div>
                {index < interpretation.length - 1 && <i aria-hidden="true">→</i>}
              </div>
            ))}
          </div>
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
      <div className="evidence-source">
        <span>Source path</span>
        <code>{displaySourcePath(item.sourcePath)}</code>
      </div>
      {canOpen ? (
        <Link href={path} className="panel-detail-link">열기</Link>
      ) : (
        <span className="panel-detail-link" aria-label={disabledLabel}>{disabledLabel}</span>
      )}
    </article>
  );
}
