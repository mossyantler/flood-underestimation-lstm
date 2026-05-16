import {
  SECTION_IDS,
  SECTION_ACCENT,
  SECTION_SLUG,
  type SectionId,
} from "@/lib/sections";

export function IconRail({ activeId }: { activeId: SectionId }) {
  return (
    <aside className="icon-rail">
      <div className="rail-brand">C</div>
      {SECTION_IDS.map((id) => (
        <a
          key={id}
          href={`/${SECTION_SLUG[id]}`}
          className="rail-btn"
          data-active={id === activeId ? "true" : "false"}
          style={
            id === activeId
              ? { color: SECTION_ACCENT[id] }
              : { color: "var(--ink-muted)" }
          }
          aria-label={id}
        >
          {id}
        </a>
      ))}
      <div className="rail-spacer" />
      <div className="rail-avatar">JM</div>
    </aside>
  );
}
