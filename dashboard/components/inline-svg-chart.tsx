import type { ChartPoint } from "@/lib/dashboard-data";

interface LineChartProps {
  m1: ChartPoint[];
  m2: ChartPoint[];
  width?: number;
  height?: number;
  yMin?: number;
  yMax?: number;
}

function scalePoints(
  points: ChartPoint[],
  xMin: number,
  xMax: number,
  yMin: number,
  yMax: number,
  svgW: number,
  svgH: number,
  pad: number
): string {
  return points
    .map((p) => {
      const sx = pad + ((p.x - xMin) / (xMax - xMin || 1)) * (svgW - pad * 2);
      const sy = svgH - pad - ((p.y - yMin) / (yMax - yMin || 1)) * (svgH - pad * 2);
      return `${sx.toFixed(1)},${sy.toFixed(1)}`;
    })
    .join(" ");
}

export function LineCompareChart({ m1, m2, width = 400, height = 120, yMin = 30, yMax = 85 }: LineChartProps) {
  const xMin = 0;
  const xMax = Math.max(m1.length, m2.length) - 1;
  const pad = 16;
  const poly1 = scalePoints(m1, xMin, xMax, yMin, yMax, width, height, pad);
  const poly2 = scalePoints(m2, xMin, xMax, yMin, yMax, width, height, pad);

  return (
    <svg
      width="100%"
      viewBox={`0 0 ${width} ${height}`}
      aria-label="q99 과소추정 비교 라인 차트"
      style={{ display: "block" }}
    >
      {/* Grid lines */}
      {[0.25, 0.5, 0.75].map((t) => {
        const y = pad + (1 - t) * (height - pad * 2);
        return (
          <line
            key={t}
            x1={pad}
            y1={y}
            x2={width - pad}
            y2={y}
            stroke="rgba(46,46,46,0.7)"
            strokeWidth={1}
          />
        );
      })}

      {/* Model 1 line (amber) */}
      <polyline
        points={poly1}
        fill="none"
        stroke="#f7b955"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={0.7}
      />

      {/* Model 2 line (blue) */}
      <polyline
        points={poly2}
        fill="none"
        stroke="#6bb4ff"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Last points */}
      {m1[m1.length - 1] && (() => {
        const last = m1[m1.length - 1];
        const sx = pad + ((last.x - xMin) / (xMax - xMin || 1)) * (width - pad * 2);
        const sy = height - pad - ((last.y - yMin) / (yMax - yMin || 1)) * (height - pad * 2);
        return <circle cx={sx} cy={sy} r={3} fill="#f7b955" />;
      })()}
      {m2[m2.length - 1] && (() => {
        const last = m2[m2.length - 1];
        const sx = pad + ((last.x - xMin) / (xMax - xMin || 1)) * (width - pad * 2);
        const sy = height - pad - ((last.y - yMin) / (yMax - yMin || 1)) * (height - pad * 2);
        return <circle cx={sx} cy={sy} r={3} fill="#6bb4ff" />;
      })()}
    </svg>
  );
}
