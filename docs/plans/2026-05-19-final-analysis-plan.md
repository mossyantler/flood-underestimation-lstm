# Final Analysis Plan: Q1/Q2/Q3 완성

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** M1 극한 홍수 과소추정 특성(Q1), M2 q50과 M1의 사건 단위 직접 비교(Q2), M2 고유량 분위수의 홍수 포착력(Q3)에 대한 분석을 완성한다.

**Architecture:**
기존 `event_peak_errors.csv`(M1 이벤트 1676건)와 `quantile_exports/*.csv`(시계열 M2 분위수)를 사건 첨두 시점에서 join하여 M2 q50 peak ratio를 추출한다. Reliability Diagram은 `quantile_calibration_by_stratum.csv`에 이미 집계된 (nominal_tau, empirical_coverage) 쌍을 시각화한다. 사건별 M2 coverage는 `observed_peak_predictions.csv`의 boolean 컬럼을 집계·시각화한다.

**Tech Stack:** Python(uv), pandas, matplotlib, seaborn

---

## 현황 요약 (착수 전 확인된 사실)

| 파일 | 내용 | 크기 |
|---|---|---|
| `event_peak_errors.csv` | M1 사건별 peak ratio, timing error | 1676행, 38 basin |
| `quantile_exports/model2_seed{seed}_epoch{ep}_quantiles.csv` | 시간별 M2 q50/q90/q95/q99 | 각 ~998K행, 38 basin |
| `observed_peak_predictions.csv` | 각 basin 최대 첨두 시점의 M1·M2 값과 coverage bool | 798행(38×3×7) |
| `quantile_calibration_by_stratum.csv` | nominal τ vs empirical coverage 집계 | 48행(4분위 × 6 stratum) |
| `quantile_coverage_summary.csv` | 분위수별 coverage fraction by stratum | 504행 |
| `primary_q99_exceedance_quantile_zone_summary.csv` | Q99 초과 관측값의 분위 구간 분포 | 15행 |

**epoch 선택 기준:** seed별 primary epoch 사용 (seed111→ep25, seed222→ep25, seed444→ep25). 이미 확정된 checkpoint sensitivity 결과를 따른다.

---

## Task 1: 공용 유틸리티 — event-level M2 peak ratio 추출

**목적:** `event_peak_errors.csv`(M1 이벤트 정의)에 M2 q50/q90/q99 peak 값을 사건 첨두 시점 join으로 추가한다.

**Files:**
- Create: `scripts/model/join_event_m2_peaks.py`
- Output: `output/model_analysis/legacy/overall_analysis/main_comparison/drbc_basin_report_cards/tables/event_peak_errors_with_m2.csv`

**Step 1: 스크립트 작성**

```python
# scripts/model/join_event_m2_peaks.py
"""
event_peak_errors.csv (M1 이벤트 정의, 1676행) + quantile_exports (M2 분위수 시계열)
→ 사건 첨두 시점에서 M2 q50/q90/q95/q99 값 추출하여 join
→ output: event_peak_errors_with_m2.csv
"""
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).parents[2]
EP_PATH = ROOT / "output/model_analysis/legacy/overall_analysis/main_comparison/drbc_basin_report_cards/tables/event_peak_errors.csv"
Q_DIR = ROOT / "output/model_analysis/legacy/quantile_analysis/quantile_exports"
OUT_PATH = ROOT / "output/model_analysis/legacy/overall_analysis/main_comparison/drbc_basin_report_cards/tables/event_peak_errors_with_m2.csv"

# primary epoch: seed → epoch 매핑 (checkpoint sensitivity 결과 기반)
SEED_EPOCH = {"111": "025", "222": "025", "444": "025"}

ep = pd.read_csv(EP_PATH)
ep["peak_dt"] = pd.to_datetime(ep["peak_dt"])

frames = []
for seed, epoch in SEED_EPOCH.items():
    qpath = Q_DIR / f"model2_seed{seed}_epoch{epoch}_quantiles.csv"
    q = pd.read_csv(qpath)
    q["datetime"] = pd.to_datetime(q["datetime"])

    # join: basin + peak_dt
    merged = ep.merge(
        q.rename(columns={"datetime": "peak_dt",
                          "q50": "m2_q50", "q90": "m2_q90",
                          "q95": "m2_q95", "q99": "m2_q99"}),
        on=["basin", "peak_dt"],
        how="left"
    )
    merged["seed"] = int(seed)

    # M2 peak ratio (q50 / obs_peak)
    merged["m2_q50_peak_ratio"] = merged["m2_q50"] / merged["obs_peak"]
    merged["m2_q90_captures"] = merged["obs_peak"] <= merged["m2_q90"]
    merged["m2_q99_captures"] = merged["obs_peak"] <= merged["m2_q99"]

    frames.append(merged)

out = pd.concat(frames, ignore_index=True)
print(f"출력: {len(out)}행, join 성공: {out['m2_q50'].notna().sum()}")
out.to_csv(OUT_PATH, index=False)
print(f"저장 완료: {OUT_PATH}")
```

**Step 2: 실행 및 확인**

```bash
uv run python scripts/model/join_event_m2_peaks.py
```

기대 출력:
```
출력: 5028행 (1676 × 3 seeds), join 성공: ~4500+ (시간 외 이벤트 제외)
저장 완료: ...event_peak_errors_with_m2.csv
```

**Step 3: 데이터 sanity check**

```bash
uv run python3 -c "
import pandas as pd
df = pd.read_csv('output/model_analysis/legacy/overall_analysis/main_comparison/drbc_basin_report_cards/tables/event_peak_errors_with_m2.csv')
print('컬럼:', list(df.columns))
print('join 성공률:', df['m2_q50'].notna().mean().round(3))
print('m1_peak_ratio 통계:', df['m1_peak_ratio'].describe().round(3).to_string())
print('m2_q50_peak_ratio 통계:', df['m2_q50_peak_ratio'].describe().round(3).to_string())
"
```

---

## Task 2: Q1 Figure — M1 과소추정 패턴 시각화 (기존 분석 완성)

**목적:** 이미 충분히 분석된 Q1의 핵심 결과를 논문용 figure 2개로 완성한다.

**Files:**
- Create: `scripts/model/plot_q1_m1_underestimation.py`
- Output dir: `output/model_analysis/legacy/paper_result_assets/figures/q1_m1_underestimation/`

**Step 1: Figure A — 유역별 median M1 peak ratio 분포**

`event_summary_per_basin.csv`의 `median_peak_ratio`를 사용한다.
- X축: median peak ratio (정렬)
- Y축: 유역 ID
- 컬러: `capture_rate` (첨두 포착률)
- 수직선: ratio=1.0 기준선

```python
# plot_q1_m1_underestimation.py (발췌)
import pandas as pd, matplotlib.pyplot as plt

basin_df = pd.read_csv("output/model_analysis/legacy/overall_analysis/main_comparison/"
                        "drbc_basin_report_cards/tables/event_summary_per_basin.csv")

fig, ax = plt.subplots(figsize=(8, 10))
basin_df_sorted = basin_df.sort_values("median_peak_ratio")
sc = ax.barh(range(len(basin_df_sorted)), basin_df_sorted["median_peak_ratio"],
             color=plt.cm.RdYlGn(basin_df_sorted["capture_rate"].values))
ax.axvline(1.0, color="black", linewidth=1.5, linestyle="--", label="Perfect prediction")
ax.set_xlabel("Median M1 Peak Ratio (predicted / observed)")
ax.set_title("M1 Peak Ratio by DRBC Basin")
plt.tight_layout()
plt.savefig(out_dir / "fig_q1a_basin_peak_ratio.pdf", dpi=150)
```

**Step 2: Figure B — Q99+ 구간 MAPE 분포**

`flow_regime_performance.csv`에서 `q_bin == "Q99+"` 필터링 후 M1 MAPE 분포.

**Step 3: 실행 및 확인**

```bash
uv run python scripts/model/plot_q1_m1_underestimation.py
ls output/model_analysis/legacy/paper_result_assets/figures/q1_m1_underestimation/
```

기대 출력: `fig_q1a_basin_peak_ratio.pdf`, `fig_q1b_q99_mape.pdf`

---

## Task 3: Q2 Figure — M1 vs M2 q50 사건별 직접 비교

**목적:** Task 1에서 생성한 `event_peak_errors_with_m2.csv`로 M1 vs M2 q50 첨두 비율 대조.

**Files:**
- Create: `scripts/model/plot_q2_m1_vs_m2q50.py`
- Output dir: `output/model_analysis/legacy/paper_result_assets/figures/q2_m1_vs_m2q50/`

**Step 1: Figure A — Scatter: M1 peak ratio vs M2 q50 peak ratio (사건별)**

```python
# 3 seeds를 평균 집계하거나 seed별로 색 구분
# 핵심 통계: paired Wilcoxon test (M1 peak ratio vs M2 q50 peak ratio)
import pandas as pd
from scipy import stats

df = pd.read_csv("output/.../event_peak_errors_with_m2.csv")
# seed별 평균
df_agg = df.groupby(["basin","event_id"])[["m1_peak_ratio","m2_q50_peak_ratio"]].mean().reset_index()

# 극한 이벤트(obs_peak > basin Q90)만 필터링
stat, p = stats.wilcoxon(df_agg["m1_peak_ratio"], df_agg["m2_q50_peak_ratio"])
print(f"Wilcoxon: stat={stat:.1f}, p={p:.4f}")
```

**Step 2: Figure B — obs_peak 크기 구간별 median peak ratio (M1 vs M2 q50)**

```python
# obs_peak를 Q50/Q75/Q90/Q99 구간으로 bins 분할
# 각 구간에서 median(m1_peak_ratio) vs median(m2_q50_peak_ratio) 비교
# 홍수가 클수록 M2 q50이 얼마나 덜 과소추정하는지 보여주는 핵심 figure
```

**Step 3: 실행 및 확인**

```bash
uv run python scripts/model/plot_q2_m1_vs_m2q50.py
```

기대 결과: 고유량 구간에서 M2 q50 peak ratio가 M1보다 1.0에 가까운 패턴.

---

## Task 4: Q3 Figure A — Reliability Diagram

**목적:** M2 분위수가 실제 보정이 되어 있는지 확인.
`quantile_calibration_by_stratum.csv`에 이미 `nominal_tau` vs `mean_empirical_coverage`가 있다.

**Files:**
- Create: `scripts/model/plot_q3_reliability_diagram.py`
- Output dir: `output/model_analysis/legacy/paper_result_assets/figures/q3_m2_coverage/`

**Step 1: Reliability Diagram 시각화**

```python
import pandas as pd, matplotlib.pyplot as plt
import numpy as np

df = pd.read_csv("output/model_analysis/legacy/probabilistic_diagnostics/quantile_calibration_by_stratum.csv")

fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Panel 1: All hours
ax = axes[0]
all_df = df[df["stratum"] == "all"]
ax.plot([0, 1], [0, 1], "k--", label="Perfect calibration")
ax.errorbar(
    all_df["nominal_tau"],
    all_df["mean_empirical_coverage"],
    yerr=[all_df["mean_empirical_coverage"] - all_df["min_empirical_coverage"],
          all_df["max_empirical_coverage"] - all_df["mean_empirical_coverage"]],
    fmt="o-", color="steelblue", label="M2 (all hours)"
)
ax.set_xlabel("Nominal quantile level τ")
ax.set_ylabel("Empirical coverage")
ax.set_title("Reliability Diagram — All Hours")
ax.legend()

# Panel 2: Peak hours only (stratum="observed_peak_hour")
ax2 = axes[1]
peak_df = df[df["stratum"] == "observed_peak_hour"]
ax2.plot([0, 1], [0, 1], "k--")
ax2.errorbar(peak_df["nominal_tau"], peak_df["mean_empirical_coverage"],
             yerr=[...], fmt="o-", color="crimson", label="M2 (peak hours only)")
ax2.set_title("Reliability Diagram — Peak Hours Only")
...

plt.tight_layout()
plt.savefig(out_dir / "fig_q3a_reliability_diagram.pdf", dpi=150)
```

**해석 포인트:**
- All hours에서 심각한 undercoverage(q50 실제 coverage ≈ 0.28 vs 명목 0.5)는 M2가 전체적으로 과소추정 분포를 학습했음을 의미
- Peak hours에서는 그 패턴이 심화 또는 완화되는지 확인 필요

**Step 2: 실행**

```bash
uv run python scripts/model/plot_q3_reliability_diagram.py
```

---

## Task 5: Q3 Figure B — 사건별 M2 q90/q99 포착률 (홍수 규모별)

**목적:** "이 홍수 사건에서 obs < M2 q99 였는가?" — Task 1 테이블로 직접 계산 가능.

**Files:**
- Create: `scripts/model/plot_q3_event_coverage.py`
- Output dir: 동일

**Step 1: 홍수 크기 구간별 M2 q90/q99 capture rate 계산**

```python
import pandas as pd, matplotlib.pyplot as plt

df = pd.read_csv("output/.../event_peak_errors_with_m2.csv")

# 3 seeds 집계: basin+event 단위 capture rate 평균
agg = df.groupby(["basin","event_id","obs_peak"]).agg(
    m2_q90_captures=("m2_q90_captures","mean"),
    m2_q99_captures=("m2_q99_captures","mean"),
    m1_peak_ratio=("m1_peak_ratio","mean"),
).reset_index()

# obs_peak 구간 분류
# 구간: <Q50, Q50-Q90, Q90-Q99, >Q99 (basin 내 분위수 기준)
agg["obs_pctile"] = agg.groupby("basin")["obs_peak"].rank(pct=True)
bins = [0, 0.5, 0.9, 0.99, 1.0]
labels = ["<Q50", "Q50-Q90", "Q90-Q99", ">Q99"]
agg["flow_bin"] = pd.cut(agg["obs_pctile"], bins=bins, labels=labels)

# 구간별 평균 capture rate
capture_summary = agg.groupby("flow_bin")[["m2_q90_captures","m2_q99_captures"]].mean()
print(capture_summary)

# 바 차트
fig, ax = plt.subplots(figsize=(8, 5))
x = range(len(capture_summary))
ax.bar([i - 0.2 for i in x], capture_summary["m2_q90_captures"], 0.4,
       label="M2 q90 capture rate", color="steelblue")
ax.bar([i + 0.2 for i in x], capture_summary["m2_q99_captures"], 0.4,
       label="M2 q99 capture rate", color="crimson")
ax.axhline(0.9, linestyle="--", color="steelblue", alpha=0.5, label="τ=0.9 target")
ax.axhline(0.99, linestyle="--", color="crimson", alpha=0.5, label="τ=0.99 target")
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.set_ylabel("Capture rate (obs ≤ quantile)")
ax.set_title("M2 Quantile Capture Rate by Flood Magnitude")
ax.legend()
plt.savefig(out_dir / "fig_q3b_event_coverage_by_magnitude.pdf", dpi=150)
```

**Step 2: 실행**

```bash
uv run python scripts/model/plot_q3_event_coverage.py
```

기대 결과: `>Q99` 구간에서 q90/q99 capture rate가 모두 1 이하로 떨어지는 패턴 (홍수가 클수록 분위수가 undercover).

---

## Task 6: 테이블 보완 — paper_result_assets 업데이트

**목적:** 위 그림들을 뒷받침하는 논문용 숫자 테이블 업데이트.

**Files:**
- Modify: `output/model_analysis/legacy/paper_result_assets/tables/primary_high_flow_peak_compact.csv`에 M2 q50 컬럼 추가
- Create: `output/model_analysis/legacy/paper_result_assets/tables/q3_capture_rate_by_magnitude.csv`

**Step 1: M1 vs M2 q50 compact table**

```python
# Task 1 결과 활용, basin당 seed 평균
summary = df.groupby("basin").agg(
    median_m1_peak_ratio=("m1_peak_ratio","median"),
    median_m2_q50_peak_ratio=("m2_q50_peak_ratio","median"),
    m2_q90_capture_rate=("m2_q90_captures","mean"),
    m2_q99_capture_rate=("m2_q99_captures","mean"),
).reset_index()
summary.to_csv("output/.../q2_q3_basin_summary.csv", index=False)
```

---

## 실행 순서

```
Task 1 (join, 필수 전처리) → Task 2 (Q1 figure) → Task 3 (Q2 figure)
                           → Task 4 (Q3 reliability) → Task 5 (Q3 event coverage)
                           → Task 6 (table 업데이트)
```

Task 1은 나머지 모든 Task의 선행 조건이다.

---

## 검증 체크리스트

- [ ] `event_peak_errors_with_m2.csv` join 성공률 > 90%
- [ ] M2 q50 peak ratio가 M1 peak ratio보다 극한 이벤트에서 높은(1에 가까운) 패턴 확인
- [ ] Reliability Diagram에서 all hours vs peak hours 패턴 차이 확인
- [ ] `>Q99` 구간에서 q99 capture rate < 0.99 확인 (undercoverage 문제 드러남)

---

## 부록: 이미 존재하는 분석 (추가 작업 불필요)

| 항목 | 파일 | 상태 |
|---|---|---|
| Q1 feature-metric Spearman | `spearman_correlations.csv` | ✅ 완료 |
| Q1 유역별 M1 peak 통계 | `event_summary_per_basin.csv` | ✅ 완료 |
| Q1 극한 구간 MAPE/bias | `flow_regime_performance.csv` | ✅ 완료 |
| Q1 유량 크기별 bias 상관 | `within_basin_rho_table.csv` | ✅ 완료 |
| Q3 nominal τ vs coverage 집계 | `quantile_calibration_by_stratum.csv` | ✅ 집계 완료, 시각화만 필요 |
| Q3 peak hour coverage bool | `observed_peak_predictions.csv` | ✅ 집계 완료, 시각화만 필요 |
