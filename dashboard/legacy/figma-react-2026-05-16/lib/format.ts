export function formatPercent(value: number, digits = 1) {
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatSigned(value: number, digits = 3) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}`;
}

export function formatCompactNumber(value: number) {
  return new Intl.NumberFormat("en-US").format(value);
}

export function clampPercent(value: number) {
  const bounded = Math.max(0, Math.min(1, value));
  return `${(bounded * 100).toFixed(1)}%`;
}
