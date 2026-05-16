import {
  SECTION_IDS,
  SECTION_ACCENT,
  SECTION_SLUG,
  type SectionId,
} from "@/lib/sections";

interface IconRailProps {
  activeId: SectionId;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
}

export function IconRail({ activeId, sidebarOpen, onToggleSidebar }: IconRailProps) {
  return (
    <aside className="icon-rail">
      <button
        className="rail-brand"
        onClick={onToggleSidebar}
        aria-label={sidebarOpen ? "사이드바 접기" : "사이드바 펼치기"}
        aria-expanded={sidebarOpen}
      >
        C
      </button>
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
