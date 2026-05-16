import {
  SECTION_LABEL,
  SECTION_SUBTITLE,
  SECTION_ACCENT,
  type SectionId,
} from "@/lib/sections";
import { evidenceRows } from "@/lib/dashboard-data";

export function ContextSidebar({ activeId }: { activeId: SectionId }) {
  const accent = SECTION_ACCENT[activeId];

  return (
    <aside className="ctx-sidebar">
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

      <div className="ctx-card accent-border">
        <div className="ctx-card-label">핵심 판독</div>
        <div className="ctx-card-title">판단 범위 고정</div>
        <p className="ctx-card-body">
          DRBC holdout, paired seed, q99 해석 경계를 먼저 잠급니다.
        </p>
      </div>

      <div className="ctx-card">
        <div className="ctx-card-title" style={{ marginBottom: 8 }}>증거 흐름</div>
        {evidenceRows.map((row) => (
          <div className="ev-row" key={row.tag}>
            <span className="ev-tag">{row.tag}</span>
            <span className="ev-val">{row.value}</span>
          </div>
        ))}
      </div>
    </aside>
  );
}
