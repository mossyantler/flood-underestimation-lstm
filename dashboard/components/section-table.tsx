import type { SectionIndexRow } from "@/lib/dashboard-data";

export function SectionTable({ rows }: { rows: SectionIndexRow[] }) {
  return (
    <div className="section-table">
      <h3>섹션 인덱스</h3>
      <table className="stbl">
        <thead>
          <tr>
            <th style={{ width: 3, padding: 0 }} />
            <th>섹션</th>
            <th>역할</th>
            <th>주요 자료</th>
            <th style={{ textAlign: "right" }}>상태</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.section}>
              <td className="row-accent" style={{ background: "var(--accent-D)" }} />
              <td style={{ fontWeight: 600, color: "var(--ink-body)", fontSize: 11 }}>{row.section}</td>
              <td className="val">{row.role}</td>
              <td className="val">{row.data}</td>
              <td className="status" style={{ color: row.statusAccent }}>{row.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
