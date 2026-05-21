import Link from "next/link";
import {
  SECTION_LABEL,
  SECTION_SUBTITLE,
  SECTION_ACCENT,
  SECTION_SLUG,
  SECTION_ENTRYPOINTS,
  type SectionId,
} from "@/lib/sections";

const STATUS_LABEL = {
  ready: "ready",
  "in-progress": "in progress",
  "needs-rerun": "needs rerun",
  planned: "planned",
} as const;

export function ContextSidebar({
  activeId,
  activeEntrySlug,
}: {
  activeId: SectionId;
  activeEntrySlug?: string;
}) {
  const accent = SECTION_ACCENT[activeId];
  const entries = SECTION_ENTRYPOINTS[activeId];
  const sectionSlug = SECTION_SLUG[activeId];

  return (
    <aside className="ctx-sidebar" style={{ "--section-accent": accent } as React.CSSProperties}>
      <div
        className="ctx-product-mark"
        style={{
          background: `color-mix(in srgb, ${accent} 14%, #0a0a0a)`,
          border: `1px solid ${accent}`,
          color: accent,
        }}
      >
        {activeId}
      </div>
      <p className="ctx-welcome">CAMELS Dashboard</p>
      <h2 className="ctx-title">{SECTION_LABEL[activeId]}</h2>
      <p className="ctx-subtitle">{SECTION_SUBTITLE[activeId]}</p>

      <nav className="ctx-entry-list" aria-label={`${SECTION_LABEL[activeId]} 하위 메뉴`}>
        {entries.map((entry) => (
          <Link
            aria-current={activeEntrySlug === entry.slug ? "page" : undefined}
            className="ctx-entry"
            href={`/${sectionSlug}/${entry.slug}`}
            key={entry.slug}
          >
            <span className="ctx-entry-top">
              <strong>{entry.label}</strong>
              {entry.status && <em data-status={entry.status}>{STATUS_LABEL[entry.status]}</em>}
            </span>
            <span>{entry.description}</span>
          </Link>
        ))}
      </nav>
    </aside>
  );
}
