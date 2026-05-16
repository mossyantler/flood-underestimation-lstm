import {
  SECTION_IDS,
  SECTION_LABEL,
  SECTION_ACCENT,
  SECTION_SLUG,
  SECTION_ROUTE,
  type SectionId,
} from "@/lib/sections";

export function MobileTopBar({ activeId }: { activeId: SectionId }) {
  return (
    <nav className="mob-topbar">
      <div className="mob-bar">
        <div className="mob-brand-mark">C</div>
        <div>
          <div className="mob-bar-name">{SECTION_LABEL[activeId]}</div>
          <div className="mob-bar-route">/{SECTION_SLUG[activeId]}</div>
        </div>
        <button className="mob-menu-btn" aria-label="메뉴">≡</button>
      </div>
      <div className="mob-pills">
        {SECTION_IDS.map((id) => (
          <a
            key={id}
            href={SECTION_ROUTE[id]}
            className="mob-pill"
            data-active={id === activeId ? "true" : "false"}
            style={
              id === activeId
                ? { background: SECTION_ACCENT[id], borderColor: SECTION_ACCENT[id], color: "#0a0a0a" }
                : {}
            }
          >
            {id}
          </a>
        ))}
        <span className="mob-pill">tree</span>
      </div>
    </nav>
  );
}
