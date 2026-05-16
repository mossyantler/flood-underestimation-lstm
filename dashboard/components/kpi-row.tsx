import type { KpiItem } from "@/lib/dashboard-data";

export function KpiRow({ item }: { item: KpiItem }) {
  return (
    <div className="mob-kpi-row">
      <div>
        <div className="mob-kpi-key">{item.label}</div>
        <div className="mob-kpi-sub">{item.sub}</div>
      </div>
      <div style={{ display: "flex", alignItems: "center" }}>
        <span className="mob-kpi-val" style={{ color: item.accent }}>{item.value}</span>
        <span className="mob-kpi-arr">›</span>
      </div>
    </div>
  );
}
