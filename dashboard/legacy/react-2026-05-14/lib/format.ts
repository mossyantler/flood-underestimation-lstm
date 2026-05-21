export function formatPercent(value: number, digits = 0) {
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatSigned(value: number, digits = 3) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}`;
}

export function clampPercent(value: number) {
  return `${Math.max(0, Math.min(100, value * 100)).toFixed(1)}%`;
}
