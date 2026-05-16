export function formatPercent(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

export function formatSigned(v: number): string {
  return v >= 0 ? `+${v.toFixed(3)}` : v.toFixed(3);
}

export function clampPercent(v: number): string {
  return `${Math.min(100, Math.max(0, v * 100)).toFixed(1)}%`;
}
