import type { CheckpointRow } from "@/lib/dashboard-data";

export function CheckpointCard({ rows }: { rows: CheckpointRow[] }) {
  return (
    <div className="panel">
      <div className="panel-title" style={{ marginBottom: 6 }}>판단 체크포인트</div>
      <p style={{ fontSize: 11, color: "var(--ink-body)", marginBottom: 12, lineHeight: 1.5 }}>
        Subset300, paired seed, DRBC holdout을 서로 다른 claim boundary로 분리합니다.
      </p>
      {rows.map((row) => (
        <div className="checkpoint-row" key={row.key}>
          <span className="checkpoint-key">{row.key}</span>
          <span className="checkpoint-val">{row.value}</span>
        </div>
      ))}
    </div>
  );
}
