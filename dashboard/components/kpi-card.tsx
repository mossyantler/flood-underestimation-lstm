import type { KpiItem } from "@/lib/dashboard-data";

export function KpiCard({ item }: { item: KpiItem }) {
  return (
    <div className="kpi-card">
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span className="kpi-label">{item.label}</span>
        <div className="kpi-dot" style={{ background: item.accent }} />
      </div>
      <div className="kpi-num">{item.value}</div>
      <div className="kpi-sub">{item.sub}</div>
    </div>
  );
}

export function KpiStrip({ items }: { items: KpiItem[] }) {
  return (
    <div className="kpi-strip">
      {items.map((item) => (
        <KpiCard key={item.label} item={item} />
      ))}
    </div>
  );
}
