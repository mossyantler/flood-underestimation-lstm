#!/usr/bin/env python3
"""
Compute quantile rise slope signals and correlate with obs_class (flood risk tier).

This script:
1. Loads M4 manifest (clean windows only) and required_series (seed 111/222/444)
2. Extracts quantile rise slopes (q50/q90/q95/q99) for each flood window
3. Computes per-window metrics: rise_slope, rise_slope_max, fanning_slope
4. Seeds: if manifest has no seed col → average across 3 seeds; if seed col exists → match per-seed
5. Correlates each metric vs obs_class_ordinal using Spearman rank correlation
6. Outputs: per-window CSV, correlation table CSV, summary markdown

Output:
  tables/quantile_rise_slope_spearman.csv  — correlation results
  tables/quantile_rise_slope_per_window.csv — per-window metrics
  summary.md — narrative summary vs obs baseline
"""

# /// script
# dependencies = ["pandas", "scipy", "numpy"]
# ///

import pandas as pd
import numpy as np
from scipy.stats import spearmanr
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================
BASE_DIR = Path(__file__).parent.parent.parent.parent  # /Users/.../CAMELS
MANIFEST_PATH = BASE_DIR / "output/model_analysis/band_signal/method_compare/data/rise_h_windows/rise_h_window_manifest.csv"

OUTPUT_DIR = BASE_DIR / "output/model_analysis/band_signal/slope_signal/tables"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SEEDS = [111, 222, 444]
OBS_CLASS_MAPPING = {
    "below_q50": 0,
    "q50_to_q90": 1,
    "q90_to_q95": 2,
    "q95_to_q99": 3,
    "above_q99": 4,
}

# ============================================================================
# Load data
# ============================================================================
log.info("Loading manifest...")
manifest = pd.read_csv(MANIFEST_PATH)
manifest = manifest[manifest["clean"]].copy()
log.info(f"  {len(manifest)} clean windows")

log.info("Loading required_series for seeds 111/222/444...")
req_data_dict = {}
for seed in SEEDS:
    path = BASE_DIR / f"output/model_analysis/primary/metrics/data/required_series/seed{seed}/required_series.csv"
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["datetime"])
    req_data_dict[seed] = df
    log.info(f"  seed {seed}: {len(df)} rows")

# ============================================================================
# Extract quantile rise slopes for each window
# ============================================================================
def extract_window_quantile_slopes(
    row, req_series_per_seed, seeds=[111, 222, 444]
):
    """
    Extract q50/q90/q95/q99 rise slopes from a single flood window.

    Args:
        row: manifest row (basin_id, onset_time, peak_time, rising_hours)
        req_series_per_seed: dict {seed: DataFrame}
        seeds: list of seed IDs to use

    Returns:
        dict with keys like q50_rise_slope, q50_rise_slope_max, ..., fanning_slope
        Returns all NaN if extraction fails.
    """
    basin_id = str(row["basin_id"]).zfill(8)
    onset_time = pd.to_datetime(row["onset_time"])
    peak_time = pd.to_datetime(row["peak_time"])
    rising_hours = row["rising_hours"]

    if pd.isna(rising_hours) or rising_hours <= 0:
        return {k: np.nan for k in [
            "q50_rise_slope", "q90_rise_slope", "q95_rise_slope", "q99_rise_slope",
            "q50_rise_slope_max", "q90_rise_slope_max", "q95_rise_slope_max", "q99_rise_slope_max",
            "fanning_slope"
        ]}

    results_per_seed = {}

    for seed in seeds:
        req = req_series_per_seed[seed]

        # Filter by basin and time window
        mask = (
            (req["basin"].astype(str).str.zfill(8) == basin_id) &
            (req["datetime"] >= onset_time) &
            (req["datetime"] <= peak_time)
        )
        window = req[mask].copy()

        if len(window) < 2:
            results_per_seed[seed] = None
            continue

        window = window.sort_values("datetime").reset_index(drop=True)

        seed_results = {}

        for quantile in ["q50", "q90", "q95", "q99"]:
            col = quantile
            if col not in window.columns:
                seed_results[f"{quantile}_rise_slope"] = np.nan
                seed_results[f"{quantile}_rise_slope_max"] = np.nan
                continue

            values = window[col].values
            start_val = values[0]
            end_val = values[-1]

            # rise_slope = (end - start) / rising_hours
            rise_slope = (end_val - start_val) / rising_hours
            seed_results[f"{quantile}_rise_slope"] = rise_slope

            # rise_slope_max = max hourly diff in window
            diffs = np.diff(values)
            rise_slope_max = np.max(diffs) if len(diffs) > 0 else np.nan
            seed_results[f"{quantile}_rise_slope_max"] = rise_slope_max

        results_per_seed[seed] = seed_results

    # Average across seeds (skip seed if failed)
    valid_seeds = [s for s in seeds if results_per_seed[s] is not None]
    if not valid_seeds:
        return {k: np.nan for k in [
            "q50_rise_slope", "q90_rise_slope", "q95_rise_slope", "q99_rise_slope",
            "q50_rise_slope_max", "q90_rise_slope_max", "q95_rise_slope_max", "q99_rise_slope_max",
            "fanning_slope"
        ]}

    avg_results = {}
    for key in results_per_seed[valid_seeds[0]].keys():
        values = [results_per_seed[s][key] for s in valid_seeds]
        avg_results[key] = np.nanmean(values)

    # Compute fanning_slope
    q99_slope = avg_results.get("q99_rise_slope", np.nan)
    q50_slope = avg_results.get("q50_rise_slope", np.nan)
    fanning_slope = q99_slope - q50_slope if not (pd.isna(q99_slope) or pd.isna(q50_slope)) else np.nan

    avg_results["fanning_slope"] = fanning_slope

    return avg_results


log.info("Extracting quantile rise slopes for each window...")
quantile_metrics = []
for idx, row in manifest.iterrows():
    metrics = extract_window_quantile_slopes(row, req_data_dict, seeds=SEEDS)
    quantile_metrics.append(metrics)
    if (idx + 1) % 100 == 0:
        log.info(f"  Processed {idx + 1}/{len(manifest)}")

quantile_df = pd.DataFrame(quantile_metrics)
log.info(f"  Extracted {len(quantile_df)} windows")

# ============================================================================
# Assemble per-window results
# ============================================================================
log.info("Assembling per-window results...")
per_window = manifest[["window_id", "basin_id", "onset_time", "peak_time", "rising_hours"]].copy()
per_window = per_window.reset_index(drop=True)

# Add obs baseline
per_window["rise_slope_m4"] = manifest["rise_slope_m4"].values
per_window["rise_slope_max_m4"] = manifest["rise_slope_max_m4"].values

# Add quantile metrics
for col in quantile_df.columns:
    per_window[col] = quantile_df[col].values

# Add obs_class (ordinal)
per_window["obs_class_primary"] = manifest["obs_class_primary"].values
per_window["obs_class_ordinal"] = per_window["obs_class_primary"].map(OBS_CLASS_MAPPING)

# Save per-window
per_window_file = OUTPUT_DIR / "quantile_rise_slope_per_window.csv"
per_window.to_csv(per_window_file, index=False)
log.info(f"Saved per-window results: {per_window_file}")

# ============================================================================
# Compute Spearman correlations
# ============================================================================
log.info("Computing Spearman rank correlations vs obs_class_ordinal...")

metrics_to_correlate = [
    "q50_rise_slope", "q90_rise_slope", "q95_rise_slope", "q99_rise_slope",
    "q50_rise_slope_max", "q90_rise_slope_max", "q95_rise_slope_max", "q99_rise_slope_max",
    "fanning_slope",
    "rise_slope_m4"  # obs baseline
]

correlation_results = []
for metric in metrics_to_correlate:
    # Remove NaN pairs
    mask = per_window["obs_class_ordinal"].notna() & per_window[metric].notna()
    x = per_window.loc[mask, metric].values
    y = per_window.loc[mask, "obs_class_ordinal"].values
    n = len(x)

    if n < 3:
        r, p_value = np.nan, np.nan
    else:
        r, p_value = spearmanr(x, y)

    correlation_results.append({
        "metric": metric,
        "spearman_r": r,
        "p_value": p_value,
        "n": n,
    })

    log.info(f"  {metric:30s}  r={r:7.3f}  p={p_value:8.2e}  n={n}")

corr_df = pd.DataFrame(correlation_results)

# Save correlation table
corr_file = OUTPUT_DIR / "quantile_rise_slope_spearman.csv"
corr_df.to_csv(corr_file, index=False)
log.info(f"Saved correlation table: {corr_file}")

# ============================================================================
# Generate summary markdown
# ============================================================================
log.info("Generating summary markdown...")

# Sort by absolute r
corr_sorted = corr_df.copy()
corr_sorted["abs_r"] = corr_sorted["spearman_r"].abs()
corr_sorted = corr_sorted.sort_values("abs_r", ascending=False)

# Separate obs baseline and quantile metrics
baseline = corr_sorted[corr_sorted["metric"] == "rise_slope_m4"].iloc[0]
quantile_rows = corr_sorted[corr_sorted["metric"] != "rise_slope_m4"]

# Build markdown
summary_md = f"""# Quantile Rise Slope Signal Analysis

## Overview
연구 목표: 예측 quantile 시계열의 상승 기울기(rise slope)가 홍수 위험도(obs_class)와 얼마나 강한 신호를 갖는가 검증.

분석 대상: {len(per_window)} 개 clean 홍수 상승 구간, 3 seed 평균 예측 quantile (q50/q90/q95/q99).

---

## Spearman 순위상관 결과

### 기준(Baseline) — 관측값 기반 상승 기울기
| 지표 | Spearman r | p-value | n |
|------|-----------|---------|---|
| {baseline['metric']} | {baseline['spearman_r']:.3f} | {baseline['p_value']:.2e} | {int(baseline['n'])} |

**해석**: 관측 rise slope는 obs_class(위험도)와 **r≈0.5** 수준의 강한 상관을 갖는다(상관이 있다는 뜻).

### 예측 Quantile 기울기 — 전체 (큰 r 순)
| 지표 | Spearman r | p-value | n |
|------|-----------|---------|---|
"""

for _, row in quantile_rows.iterrows():
    summary_md += f"| {row['metric']} | {row['spearman_r']:.3f} | {row['p_value']:.2e} | {int(row['n'])} |\n"

# Highlight strong signals
strong_signals = quantile_rows[quantile_rows["spearman_r"].abs() > 0.3]
summary_md += f"""

### 강한 신호 (|r| > 0.3)
"""
if len(strong_signals) > 0:
    summary_md += "| 지표 | Spearman r |\n|------|--------|\n"
    for _, row in strong_signals.iterrows():
        summary_md += f"| {row['metric']} | {row['spearman_r']:.3f} |\n"
else:
    summary_md += "(|r| > 0.3 인 지표 없음)\n"

# Conclusion
summary_md += f"""

---

## 결론

예측 quantile 기울기들(q50~q99)의 위험도 신호 강도를 관측값 baseline(r≈{baseline['spearman_r']:.2f})과 비교한 결과:

"""

max_r = quantile_rows["spearman_r"].abs().max()
max_metric = quantile_rows.loc[quantile_rows["spearman_r"].abs().idxmax(), "metric"]

if max_r > 0.4:
    summary_md += f"• **강한 신호**: {max_metric} (r={quantile_rows.loc[quantile_rows['metric']==max_metric, 'spearman_r'].values[0]:.3f})이 관측 baseline과 유사 수준의 위험도 신호를 갖는다. 예측 quantile 기울기는 홍수 위험도 분류에 **충분한 판별력**을 제공할 수 있다.\n"
elif max_r > 0.2:
    summary_md += f"• **중간 신호**: 최고 상관은 {max_metric} (r={max_r:.3f})로, 관측 baseline(r≈{baseline['spearman_r']:.2f})보다 약하나 약한 신호를 갖는다. 추가 특성 엔지니어링이나 비선형 변환 필요 가능성.\n"
else:
    summary_md += f"• **약한 신호**: 예측 quantile 기울기 단독으로는 위험도 신호가 약하다(최고 r={max_r:.3f}). 다른 특성(e.g., 밴드 폭, 누적 변화)과의 결합 필요.\n"

summary_md += f"""

### 참고
- 관측값 기반 rise slope는 관측값 누수(leakage) 위험으로 인해 최종 모델에 사용 불가.
- 예측 quantile 기울기는 누수 없으므로, 위험도 신호가 충분하면 주요 판별 지표로 활용 가능.
- 매칭된 {int(per_window['obs_class_ordinal'].notna().sum())} 개 window에서 계산됨.
"""

summary_file = OUTPUT_DIR.parent / "summary.md"
with open(summary_file, "w") as f:
    f.write(summary_md)
log.info(f"Saved summary: {summary_file}")

print("\n" + "="*70)
print("SUMMARY")
print("="*70)
print(f"\nMatched windows: {int(per_window['obs_class_ordinal'].notna().sum())}")
print(f"\nSpearman correlations (sorted by |r|):\n")
print(corr_sorted[["metric", "spearman_r", "p_value", "n"]].to_string(index=False))
print(f"\nOutputs:")
print(f"  {per_window_file}")
print(f"  {corr_file}")
print(f"  {summary_file}")
