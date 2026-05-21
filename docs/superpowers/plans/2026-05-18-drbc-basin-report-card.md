# DRBC 유역별 진단 리포트 카드 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 38개 DRBC 유역 각각에 대해 유량 구간별 성능, 홍수 사건 진단, 선행 조건 효과, 상승/하강 비대칭을 포함한 8-패널 리포트 카드와 cross-basin 요약 그림을 생성한다.

**Architecture:** 두 스크립트 분리 — `compute_drbc_basin_report_card_data.py`가 모든 중간 테이블을 산출하고, `plot_drbc_basin_report_cards.py`가 테이블만 읽어 모든 그림을 생성한다. 각 스크립트는 독립 실행 가능하다.

**Tech Stack:** Python 3.11+, uv run (PEP 723 inline deps), pandas 2.2, numpy 1.26, scipy 1.13, statsmodels 0.14, matplotlib 3.8

---

## 파일 구조

```
scripts/model/overall/
├── compute_drbc_basin_report_card_data.py   (신규)
└── plot_drbc_basin_report_cards.py          (신규)

output/model_analysis/legacy/overall_analysis/main_comparison/drbc_basin_report_cards/
├── tables/
│   ├── flow_regime_performance.csv
│   ├── seasonal_performance.csv
│   ├── event_peak_errors.csv
│   ├── event_summary_per_basin.csv
│   ├── antecedent_condition_perf.csv
│   ├── rising_falling_bias.csv
│   └── feature_regime_correlations.csv
└── figures/
    ├── report_cards/
    │   ├── {basin_id}_report_card.png      (38개)
    │   └── panels/
    │       └── {basin_id}_p{1-8}_*.png     (38×8 = 304개)
    └── cross_basin/
        ├── heatmap_regime_Q0Q50.png
        ├── heatmap_regime_Q50Q90.png
        ├── heatmap_regime_Q90Q99.png
        ├── heatmap_regime_Q99plus.png
        ├── event_capture_rate_ranking.png
        └── antecedent_effect_distribution.png
```

---

## 입력 데이터 (참고)

| 파일 | 내용 |
|------|------|
| `output/model_analysis/legacy/quantile_analysis/required_series/seed{s}/epoch{e}_required_series.csv` | columns: seed, basin, model1_epoch, model2_epoch, datetime, obs, model1, q50, q90, q95, q99 |
| `output/basin/drbc/analysis/basin_attributes/tables/drbc_selected_basin_analysis_table.csv` | columns: gauge_id, gauge_name, drain_sqkm_attr, lat_gage, ... (154행, 38개만 사용) |
| `output/model_analysis/legacy/overall_analysis/epoch_sensitivity/tables/basin_metrics.csv` | columns: basin, model, seed, epoch, NSE, KGE, ... (basin ID 추출용) |
| `output/model_analysis/legacy/overall_analysis/main_comparison/drbc_attribute_metric_correlations/within_basin/tables/within_basin_rho_table.csv` | columns: basin, within_m1_bias_rho, ... (그림 제목용) |

Primary epochs: seed111→(m1:25, m2:5), seed222→(m1:10, m2:10), seed444→(m1:15, m2:10)

---

## Task 1: compute 스크립트 — 상수·헬퍼 함수

**Files:**
- Create: `scripts/model/overall/compute_drbc_basin_report_card_data.py`

- [ ] **Step 1: 파일 생성 및 상수/헬퍼 작성**

```python
#!/usr/bin/env python3
"""DRBC 유역별 진단 리포트 카드 데이터 계산."""
# /// script
# dependencies = [
#   "matplotlib>=3.8",
#   "numpy>=1.26",
#   "pandas>=2.2",
#   "scipy>=1.13",
#   "statsmodels>=0.14",
# ]
# ///

import logging
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from statsmodels.stats.multitest import multipletests

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

OFFICIAL_SEEDS = [111, 222, 444]
PRIMARY_EPOCHS = {
    111: {"model1": 25, "model2": 5},
    222: {"model1": 10, "model2": 10},
    444: {"model1": 15, "model2": 10},
}
Q_BIN_LABELS = ["Q0-Q50", "Q50-Q90", "Q90-Q99", "Q99+"]
SEASONS = {"DJF": [12, 1, 2], "MAM": [3, 4, 5],
           "JJA": [6, 7, 8], "SON": [9, 10, 11]}

SERIES_ROOT  = Path("output/model_analysis/legacy/quantile_analysis/required_series")
ATTR_FILE    = Path("output/basin/drbc/analysis/basin_attributes/tables/drbc_selected_basin_analysis_table.csv")
METRICS_FILE = Path("output/model_analysis/legacy/overall_analysis/epoch_sensitivity/tables/basin_metrics.csv")
OUTPUT_ROOT  = Path("output/model_analysis/legacy/overall_analysis/main_comparison/drbc_basin_report_cards")

FEATURE_COLS = [
    "drain_sqkm_attr", "log10_area", "frac_snow", "p_seasonality",
    "lat_gage", "elev_mean_m", "slope_pct", "developed_frac",
    "forest_frac", "soil_permeability_index", "aridity",
    "baseflow_index_pct", "high_prec_freq", "soil_available_water_capacity",
    "SANDAVE", "CLAYAVE",
]

def _get_basin_ids() -> list[str]:
    df = pd.read_csv(METRICS_FILE, dtype={"basin": str})
    return sorted(df["basin"].str.zfill(8).unique().tolist())

def _season_of(month: int) -> str:
    for s, months in SEASONS.items():
        if month in months:
            return s
    return "UNK"

def load_series_one_seed(seed: int) -> pd.DataFrame:
    """한 seed의 primary epoch 시리즈 로드. datetime 파싱 포함."""
    epoch = PRIMARY_EPOCHS[seed]["model2"]
    path = SERIES_ROOT / f"seed{seed}" / f"epoch{epoch:03d}_required_series.csv"
    log.info("  loading %s", path)
    df = pd.read_csv(path, dtype={"basin": str}, parse_dates=["datetime"])
    df["basin"] = df["basin"].str.zfill(8)
    df = df.dropna(subset=["obs"])
    df = df[df["obs"] > 0].copy()
    return df

def compute_q_bin_boundaries(obs: np.ndarray) -> dict[str, tuple[float, float]]:
    """유역별 Q-bin 경계값 반환. obs는 test period 전체 obs 배열."""
    p50 = np.percentile(obs, 50)
    p90 = np.percentile(obs, 90)
    p99 = np.percentile(obs, 99)
    return {
        "Q0-Q50":  (0.0,  p50),
        "Q50-Q90": (p50,  p90),
        "Q90-Q99": (p90,  p99),
        "Q99+":    (p99,  np.inf),
    }

def assign_q_bin(obs: np.ndarray, boundaries: dict) -> np.ndarray:
    """각 obs 값에 Q-bin 레이블 할당."""
    labels = np.full(len(obs), "", dtype=object)
    for label, (lo, hi) in boundaries.items():
        mask = (obs > lo) & (obs <= hi)
        if label == "Q0-Q50":
            mask = obs <= hi
        labels[mask] = label
    return labels
```

- [ ] **Step 2: 스크립트 실행 가능 확인**

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run scripts/model/overall/compute_drbc_basin_report_card_data.py --help 2>&1 | head -5
```
Expected: `usage:` 또는 에러 없이 종료 (argparse 없으면 그냥 종료)

- [ ] **Step 3: 커밋**

```bash
git add scripts/model/overall/compute_drbc_basin_report_card_data.py
git commit -m "feat: add compute_drbc_basin_report_card_data scaffolding"
```

---

## Task 2: 유량 구간별 성능 계산

**Files:**
- Modify: `scripts/model/overall/compute_drbc_basin_report_card_data.py`

- [ ] **Step 1: `compute_flow_regime_perf_one_seed` 함수 추가**

```python
def compute_flow_regime_perf_one_seed(df: pd.DataFrame) -> pd.DataFrame:
    """한 seed의 시리즈에서 유역별 Q-bin별 성능 계산."""
    records = []
    for basin, grp in df.groupby("basin"):
        obs  = grp["obs"].values
        m1   = grp["model1"].values
        q50  = grp["q50"].values
        q90  = grp["q90"].values
        q99  = grp["q99"].values
        bounds = compute_q_bin_boundaries(obs)
        bins   = assign_q_bin(obs, bounds)

        for label in Q_BIN_LABELS:
            mask = bins == label
            if mask.sum() < 5:
                continue
            o  = obs[mask]; p1 = m1[mask]
            p50 = q50[mask]; p90 = q90[mask]; p99b = q99[mask]

            m1_mape   = float(np.mean(np.abs(o - p1) / o) * 100)
            m2_mape   = float(np.mean(np.abs(o - p50) / o) * 100)
            m1_bias   = float((np.mean(p1) - np.mean(o)) / np.mean(o) * 100)
            m2_bias   = float((np.mean(p50) - np.mean(o)) / np.mean(o) * 100)
            cov_q90   = float(np.mean(o <= p90))
            cov_q99   = float(np.mean(o <= p99b))
            width_rat = float(np.mean((p99b - p50) / o))

            records.append({
                "basin": basin, "q_bin": label,
                "m1_mape": m1_mape, "m2_q50_mape": m2_mape,
                "m1_bias": m1_bias, "m2_q50_bias": m2_bias,
                "m2_q90_coverage": cov_q90, "m2_q99_coverage": cov_q99,
                "m2_interval_width_ratio": width_rat,
                "n_hours": int(mask.sum()),
            })
    return pd.DataFrame(records)
```

- [ ] **Step 2: 3 seed 중앙값 집계 함수 추가**

```python
def aggregate_flow_regime_perf(basin_ids: list[str]) -> pd.DataFrame:
    """3 seed 각각 계산 후 중앙값 집계."""
    frames = []
    for seed in OFFICIAL_SEEDS:
        df = load_series_one_seed(seed)
        frames.append(compute_flow_regime_perf_one_seed(df))
    stacked = pd.concat(frames)
    metric_cols = ["m1_mape", "m2_q50_mape", "m1_bias", "m2_q50_bias",
                   "m2_q90_coverage", "m2_q99_coverage", "m2_interval_width_ratio", "n_hours"]
    result = stacked.groupby(["basin", "q_bin"])[metric_cols].median().reset_index()
    return result
```

- [ ] **Step 3: 스크립트에 임시 main 추가 후 실행 검증**

```python
if __name__ == "__main__":
    basin_ids = _get_basin_ids()
    log.info("basins: %d", len(basin_ids))
    regime = aggregate_flow_regime_perf(basin_ids)
    log.info("flow_regime shape: %s", regime.shape)
    log.info(regime.head(8).to_string())
```

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run scripts/model/overall/compute_drbc_basin_report_card_data.py 2>&1 | tail -20
```
Expected: `flow_regime shape: (152, 10)` (38 basins × 4 bins = 152), 값 범위 MAPE > 0, coverage 0~1

- [ ] **Step 4: 커밋**

```bash
git add scripts/model/overall/compute_drbc_basin_report_card_data.py
git commit -m "feat: add flow regime performance computation"
```

---

## Task 3: 계절별 성능 계산

**Files:**
- Modify: `scripts/model/overall/compute_drbc_basin_report_card_data.py`

- [ ] **Step 1: `compute_seasonal_perf_one_seed` 추가**

```python
def compute_seasonal_perf_one_seed(df: pd.DataFrame) -> pd.DataFrame:
    """유역별 계절별 MAPE / Bias + Q99+ 계절 분포."""
    df = df.copy()
    df["month"]  = df["datetime"].dt.month
    df["season"] = df["month"].map(_season_of)

    records = []
    for basin, grp in df.groupby("basin"):
        obs = grp["obs"].values
        p99_thresh = np.percentile(obs, 99)

        for season in SEASONS:
            mask = grp["season"] == season
            if mask.sum() < 5:
                continue
            o  = grp.loc[mask, "obs"].values
            p1 = grp.loc[mask, "model1"].values

            m1_mape = float(np.mean(np.abs(o - p1) / o) * 100)
            m1_bias = float((np.mean(p1) - np.mean(o)) / np.mean(o) * 100)

            # Q99+ 시간 중 이 계절 비율
            q99_mask = grp["obs"] > p99_thresh
            q99_season_cnt = int((q99_mask & mask).sum())

            records.append({
                "basin": basin, "season": season,
                "m1_mape": m1_mape, "m1_bias": m1_bias,
                "q99_hour_count": q99_season_cnt,
                "n_hours": int(mask.sum()),
            })
    return pd.DataFrame(records)

def aggregate_seasonal_perf(basin_ids: list[str]) -> pd.DataFrame:
    frames = []
    for seed in OFFICIAL_SEEDS:
        df = load_series_one_seed(seed)
        frames.append(compute_seasonal_perf_one_seed(df))
    stacked = pd.concat(frames)
    metric_cols = ["m1_mape", "m1_bias", "q99_hour_count", "n_hours"]
    return stacked.groupby(["basin", "season"])[metric_cols].median().reset_index()
```

- [ ] **Step 2: 실행 검증**

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run scripts/model/overall/compute_drbc_basin_report_card_data.py 2>&1 | grep -E "seasonal|shape"
```
Expected: `seasonal shape: (152, 6)` (38 × 4 seasons)

- [ ] **Step 3: 커밋**

```bash
git add scripts/model/overall/compute_drbc_basin_report_card_data.py
git commit -m "feat: add seasonal performance computation"
```

---

## Task 4: 홍수 사건 식별

**Files:**
- Modify: `scripts/model/overall/compute_drbc_basin_report_card_data.py`

- [ ] **Step 1: `detect_flood_events` 추가**

```python
def detect_flood_events(obs_series: pd.Series, datetime_series: pd.Series,
                        q95_thresh: float) -> list[dict]:
    """
    Q95 초과 이산 홍수 사건 목록 반환.
    - 24시간 미만 갭은 동일 사건으로 병합
    - 최소 3시간 지속 사건만 포함
    반환: list of dict with keys: start_idx, end_idx, peak_idx, start_dt, end_dt, peak_dt
    """
    obs = obs_series.values
    dts = datetime_series.values
    above = obs > q95_thresh

    # 연속 구간 찾기
    events_raw = []
    in_event = False
    start = 0
    for i in range(len(obs)):
        if above[i] and not in_event:
            in_event = True
            start = i
        elif not above[i] and in_event:
            in_event = False
            events_raw.append((start, i - 1))
    if in_event:
        events_raw.append((start, len(obs) - 1))

    # 24h 갭 병합 (hourly data → 24 steps)
    merged = []
    for ev in events_raw:
        if merged and (ev[0] - merged[-1][1]) <= 24:
            merged[-1] = (merged[-1][0], ev[1])
        else:
            merged.append(list(ev))

    # 최소 3시간 필터 + 첨두 찾기
    result = []
    for s, e in merged:
        if (e - s + 1) < 3:
            continue
        peak_idx = s + int(np.argmax(obs[s:e+1]))
        result.append({
            "start_idx": s, "end_idx": e, "peak_idx": peak_idx,
            "start_dt": dts[s], "end_dt": dts[e], "peak_dt": dts[peak_idx],
        })
    return result
```

- [ ] **Step 2: 단위 검증 (인라인 print)**

main에 추가:
```python
# 임시 검증: seed111에서 첫 번째 유역의 사건 수 확인
df111 = load_series_one_seed(111)
first_basin = df111["basin"].iloc[0]
grp = df111[df111["basin"] == first_basin].reset_index(drop=True)
q95 = float(np.percentile(grp["obs"].values, 95))
events = detect_flood_events(grp["obs"], grp["datetime"], q95)
log.info("basin %s: q95=%.2f, n_events=%d", first_basin, q95, len(events))
```

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run scripts/model/overall/compute_drbc_basin_report_card_data.py 2>&1 | grep "n_events"
```
Expected: `n_events=` 숫자 (20–80 범위 예상)

- [ ] **Step 3: 커밋**

```bash
git add scripts/model/overall/compute_drbc_basin_report_card_data.py
git commit -m "feat: add flood event detection algorithm"
```

---

## Task 5: 사건 단위 첨두 오차 계산

**Files:**
- Modify: `scripts/model/overall/compute_drbc_basin_report_card_data.py`

- [ ] **Step 1: `compute_event_peak_errors_one_seed` 추가**

```python
def compute_event_peak_errors_one_seed(df: pd.DataFrame) -> pd.DataFrame:
    """사건별 peak_ratio, timing_error, volume_error 계산."""
    records = []
    for basin, grp in df.groupby("basin"):
        grp = grp.reset_index(drop=True)
        obs  = grp["obs"].values
        m1   = grp["model1"].values
        dts  = grp["datetime"].values
        q95  = float(np.percentile(obs, 95))
        events = detect_flood_events(grp["obs"], grp["datetime"], q95)

        for i, ev in enumerate(events):
            s, e, pi = ev["start_idx"], ev["end_idx"], ev["peak_idx"]
            obs_seg = obs[s:e+1]; m1_seg = m1[s:e+1]
            obs_peak = float(obs[pi])
            m1_peak  = float(m1[pi])

            # 타이밍 오차: M1 첨두 시각 - obs 첨두 시각 (양수=M1이 늦음)
            m1_peak_idx_local = int(np.argmax(m1_seg))
            m1_peak_dt = dts[s + m1_peak_idx_local]
            obs_peak_dt = dts[pi]
            timing_err_h = float(
                (pd.Timestamp(m1_peak_dt) - pd.Timestamp(obs_peak_dt))
                .total_seconds() / 3600
            )

            # 부피 오차
            vol_err_pct = float(
                (np.sum(m1_seg) - np.sum(obs_seg)) / np.sum(obs_seg) * 100
            )

            # 계절
            peak_month = pd.Timestamp(obs_peak_dt).month
            season = _season_of(peak_month)

            records.append({
                "basin": basin,
                "event_id": i,
                "peak_dt": str(obs_peak_dt),
                "obs_peak": obs_peak,
                "m1_peak": m1_peak,
                "m1_peak_ratio": m1_peak / obs_peak if obs_peak > 0 else np.nan,
                "m1_timing_error_h": timing_err_h,
                "m1_volume_error_pct": vol_err_pct,
                "season": season,
                "n_hours": e - s + 1,
            })
    return pd.DataFrame(records)

def aggregate_event_peak_errors(basin_ids: list[str]) -> pd.DataFrame:
    """3 seed 중앙값 집계. 사건 식별은 obs 기준이므로 동일."""
    frames = []
    for seed in OFFICIAL_SEEDS:
        df = load_series_one_seed(seed)
        f = compute_event_peak_errors_one_seed(df)
        f["seed"] = seed
        frames.append(f)
    stacked = pd.concat(frames)
    metric_cols = ["m1_peak_ratio", "m1_timing_error_h", "m1_volume_error_pct"]
    # season / obs_peak은 seed에 무관 → seed 111 값 사용
    base = stacked[stacked["seed"] == 111][["basin", "event_id", "peak_dt",
                                             "obs_peak", "season", "n_hours"]]
    agg = stacked.groupby(["basin", "event_id"])[metric_cols].median().reset_index()
    return base.merge(agg, on=["basin", "event_id"], how="inner")

def compute_event_summary(event_df: pd.DataFrame) -> pd.DataFrame:
    """유역별 사건 요약 통계."""
    records = []
    for basin, grp in event_df.groupby("basin"):
        capture_rate = float((grp["m1_peak_ratio"] >= 0.7).mean() * 100)
        records.append({
            "basin": basin,
            "n_events": len(grp),
            "capture_rate_pct": capture_rate,
            "median_peak_ratio": float(grp["m1_peak_ratio"].median()),
            "median_timing_error_h": float(grp["m1_timing_error_h"].median()),
        })
    return pd.DataFrame(records)
```

- [ ] **Step 2: 실행 검증**

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run scripts/model/overall/compute_drbc_basin_report_card_data.py 2>&1 | grep -E "event|shape"
```
Expected: `event_peak shape: (N, 10)` N은 전체 사건 수 (예상 500–2000)

- [ ] **Step 3: 커밋**

```bash
git add scripts/model/overall/compute_drbc_basin_report_card_data.py
git commit -m "feat: add event peak error computation"
```

---

## Task 6: 선행 조건 효과 계산

**Files:**
- Modify: `scripts/model/overall/compute_drbc_basin_report_card_data.py`

- [ ] **Step 1: `compute_antecedent_perf_one_seed` 추가**

```python
def compute_antecedent_perf_one_seed(df: pd.DataFrame) -> pd.DataFrame:
    """사건별 선행 조건 분류 후 조건별 M1 MAPE / Bias 계산."""
    records = []
    for basin, grp in df.groupby("basin"):
        grp = grp.reset_index(drop=True)
        obs = grp["obs"].values
        m1  = grp["model1"].values
        dts = pd.DatetimeIndex(grp["datetime"])
        q95 = float(np.percentile(obs, 95))
        events = detect_flood_events(grp["obs"], grp["datetime"], q95)
        if len(events) < 3:
            continue

        # 각 사건의 선행 7일 평균 유량 계산
        ante_means = []
        for ev in events:
            s = ev["start_idx"]
            start_dt = pd.Timestamp(dts[s])
            lookback_start = start_dt - pd.Timedelta(days=7)
            ante_mask = (dts >= lookback_start) & (dts < start_dt)
            if ante_mask.sum() < 24:
                ante_means.append(np.nan)
            else:
                ante_means.append(float(np.mean(obs[ante_mask.values])))

        ante_arr = np.array(ante_means)
        valid = np.isfinite(ante_arr)
        if valid.sum() < 3:
            continue

        p33 = np.percentile(ante_arr[valid], 33)
        p67 = np.percentile(ante_arr[valid], 67)

        def classify(v):
            if np.isnan(v): return None
            if v <= p33: return "dry"
            if v <= p67: return "normal"
            return "wet"

        for condition in ["dry", "normal", "wet"]:
            # 해당 조건의 사건들의 모든 시간대를 모아 MAPE 계산
            all_obs_list, all_m1_list = [], []
            for ev, ante in zip(events, ante_arr):
                if classify(ante) != condition:
                    continue
                s, e = ev["start_idx"], ev["end_idx"]
                all_obs_list.append(obs[s:e+1])
                all_m1_list.append(m1[s:e+1])

            if not all_obs_list:
                continue
            o_all = np.concatenate(all_obs_list)
            p_all = np.concatenate(all_m1_list)
            mask = o_all > 0
            if mask.sum() < 5:
                continue
            records.append({
                "basin": basin, "condition": condition,
                "n_events": len(all_obs_list),
                "m1_mape": float(np.mean(np.abs(o_all[mask] - p_all[mask]) / o_all[mask]) * 100),
                "m1_bias": float((np.mean(p_all[mask]) - np.mean(o_all[mask])) / np.mean(o_all[mask]) * 100),
            })
    return pd.DataFrame(records)

def aggregate_antecedent_perf(basin_ids: list[str]) -> pd.DataFrame:
    frames = []
    for seed in OFFICIAL_SEEDS:
        df = load_series_one_seed(seed)
        frames.append(compute_antecedent_perf_one_seed(df))
    stacked = pd.concat(frames)
    return stacked.groupby(["basin", "condition"])[
        ["n_events", "m1_mape", "m1_bias"]].median().reset_index()
```

- [ ] **Step 2: 실행 검증**

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run scripts/model/overall/compute_drbc_basin_report_card_data.py 2>&1 | grep "antecedent"
```
Expected: `antecedent shape: (N, 5)` N ≈ 38×3 = 114 (일부 유역 NaN 제외하면 더 적을 수 있음)

- [ ] **Step 3: 커밋**

```bash
git add scripts/model/overall/compute_drbc_basin_report_card_data.py
git commit -m "feat: add antecedent condition performance computation"
```

---

## Task 7: 상승/하강 구간 비대칭 계산

**Files:**
- Modify: `scripts/model/overall/compute_drbc_basin_report_card_data.py`

- [ ] **Step 1: `compute_rising_falling_one_seed` 추가**

```python
def compute_rising_falling_one_seed(df: pd.DataFrame) -> pd.DataFrame:
    """유역별 rising / falling limb M1 Bias 계산."""
    records = []
    for basin, grp in df.groupby("basin"):
        grp = grp.reset_index(drop=True)
        obs = grp["obs"].values
        m1  = grp["model1"].values
        q50 = grp["q50"].values
        q95 = float(np.percentile(obs, 95))
        events = detect_flood_events(grp["obs"], grp["datetime"], q95)
        if len(events) < 3:
            continue

        rising_obs, rising_m1, rising_q50 = [], [], []
        falling_obs, falling_m1, falling_q50 = [], [], []

        for ev in events:
            s, e, pi = ev["start_idx"], ev["end_idx"], ev["peak_idx"]
            # rising: s ~ pi-1 (최소 3 steps)
            if pi - s >= 3:
                rising_obs.extend(obs[s:pi].tolist())
                rising_m1.extend(m1[s:pi].tolist())
                rising_q50.extend(q50[s:pi].tolist())
            # falling: pi+1 ~ e (최소 3 steps)
            if e - pi >= 3:
                falling_obs.extend(obs[pi+1:e+1].tolist())
                falling_m1.extend(m1[pi+1:e+1].tolist())
                falling_q50.extend(q50[pi+1:e+1].tolist())

        for phase, o_list, m1_list, q50_list in [
            ("rising",  rising_obs,  rising_m1,  rising_q50),
            ("falling", falling_obs, falling_m1, falling_q50),
        ]:
            if len(o_list) < 5:
                continue
            o  = np.array(o_list); p1 = np.array(m1_list); p50 = np.array(q50_list)
            mask = o > 0
            records.append({
                "basin": basin, "phase": phase,
                "m1_bias": float((np.mean(p1[mask]) - np.mean(o[mask])) / np.mean(o[mask]) * 100),
                "m2_q50_bias": float((np.mean(p50[mask]) - np.mean(o[mask])) / np.mean(o[mask]) * 100),
                "n_timesteps": int(mask.sum()),
            })
    return pd.DataFrame(records)

def aggregate_rising_falling(basin_ids: list[str]) -> pd.DataFrame:
    frames = []
    for seed in OFFICIAL_SEEDS:
        df = load_series_one_seed(seed)
        frames.append(compute_rising_falling_one_seed(df))
    stacked = pd.concat(frames)
    return stacked.groupby(["basin", "phase"])[
        ["m1_bias", "m2_q50_bias", "n_timesteps"]].median().reset_index()
```

- [ ] **Step 2: 커밋**

```bash
git add scripts/model/overall/compute_drbc_basin_report_card_data.py
git commit -m "feat: add rising/falling limb asymmetry computation"
```

---

## Task 8: Feature-regime 상관계수 계산

**Files:**
- Modify: `scripts/model/overall/compute_drbc_basin_report_card_data.py`

- [ ] **Step 1: `compute_feature_regime_corr` 추가**

```python
def load_basin_features() -> pd.DataFrame:
    raw = pd.read_csv(ATTR_FILE, dtype={"gauge_id": str})
    raw["gauge_id"] = raw["gauge_id"].str.zfill(8)
    raw = raw.rename(columns={"gauge_id": "basin"})
    raw["log10_area"] = np.log10(raw["drain_sqkm_attr"].clip(lower=1e-3))
    return raw.set_index("basin")

def compute_feature_regime_corr(regime_df: pd.DataFrame,
                                 feat_df: pd.DataFrame,
                                 fdr_alpha: float = 0.05) -> pd.DataFrame:
    """Q-bin별 feature × {m1_mape, m1_bias, m2_q50_mape, m2_q99_coverage} 상관."""
    metric_cols = ["m1_mape", "m1_bias", "m2_q50_mape", "m2_q99_coverage"]
    rows = []
    for q_bin in Q_BIN_LABELS:
        sub = regime_df[regime_df["q_bin"] == q_bin].set_index("basin")
        for feat in FEATURE_COLS:
            if feat not in feat_df.columns:
                continue
            for metric in metric_cols:
                if metric not in sub.columns:
                    continue
                x = feat_df[feat]
                y = sub[metric]
                common = x.index.intersection(y.index)
                valid = x[common].notna() & y[common].notna()
                if valid.sum() < 5:
                    continue
                r = spearmanr(x[common][valid], y[common][valid])
                rows.append({
                    "q_bin": q_bin, "feature": feat, "metric": metric,
                    "rho": r.statistic, "pval": r.pvalue, "n": int(valid.sum()),
                })

    corr_df = pd.DataFrame(rows)
    if corr_df.empty:
        return corr_df
    _, padj, _, _ = multipletests(corr_df["pval"], alpha=fdr_alpha, method="fdr_bh")
    corr_df["pval_bh"] = padj
    corr_df["significant"] = padj < fdr_alpha
    return corr_df.sort_values("rho", key=abs, ascending=False)
```

- [ ] **Step 2: 커밋**

```bash
git add scripts/model/overall/compute_drbc_basin_report_card_data.py
git commit -m "feat: add feature-regime Spearman correlation computation"
```

---

## Task 9: compute 스크립트 main() 완성 및 테이블 저장

**Files:**
- Modify: `scripts/model/overall/compute_drbc_basin_report_card_data.py`

- [ ] **Step 1: main() 함수로 통합**

```python
def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--fdr-alpha", type=float, default=0.05)
    args = parser.parse_args()

    tbl = OUTPUT_ROOT / "tables"
    tbl.mkdir(parents=True, exist_ok=True)

    basin_ids = _get_basin_ids()
    log.info("basins: %d", len(basin_ids))

    log.info("=== flow regime performance ===")
    regime = aggregate_flow_regime_perf(basin_ids)
    regime.to_csv(tbl / "flow_regime_performance.csv", index=False)
    log.info("  shape: %s", regime.shape)

    log.info("=== seasonal performance ===")
    seasonal = aggregate_seasonal_perf(basin_ids)
    seasonal.to_csv(tbl / "seasonal_performance.csv", index=False)
    log.info("  shape: %s", seasonal.shape)

    log.info("=== event peak errors ===")
    event_df = aggregate_event_peak_errors(basin_ids)
    event_df.to_csv(tbl / "event_peak_errors.csv", index=False)
    log.info("  shape: %s", event_df.shape)
    summary_df = compute_event_summary(event_df)
    summary_df.to_csv(tbl / "event_summary_per_basin.csv", index=False)

    log.info("=== antecedent conditions ===")
    ante = aggregate_antecedent_perf(basin_ids)
    ante.to_csv(tbl / "antecedent_condition_perf.csv", index=False)
    log.info("  shape: %s", ante.shape)

    log.info("=== rising/falling asymmetry ===")
    rf = aggregate_rising_falling(basin_ids)
    rf.to_csv(tbl / "rising_falling_bias.csv", index=False)
    log.info("  shape: %s", rf.shape)

    log.info("=== feature-regime correlations ===")
    feat_df = load_basin_features()
    corr = compute_feature_regime_corr(regime, feat_df, args.fdr_alpha)
    corr.to_csv(tbl / "feature_regime_correlations.csv", index=False)
    log.info("  pairs: %d, significant: %d", len(corr), corr["significant"].sum())

    log.info("=== done: %s ===", tbl)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 전체 실행 (3–10분 소요)**

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run scripts/model/overall/compute_drbc_basin_report_card_data.py 2>&1 | tee /tmp/compute_log.txt
tail -20 /tmp/compute_log.txt
```
Expected: 에러 없이 완료, 7개 CSV 파일 생성 확인

```bash
ls -lh output/model_analysis/legacy/overall_analysis/main_comparison/drbc_basin_report_cards/tables/
```
Expected: 7개 파일 모두 존재, 각각 > 1KB

- [ ] **Step 3: 커밋**

```bash
git add scripts/model/overall/compute_drbc_basin_report_card_data.py
git commit -m "feat: complete compute_drbc_basin_report_card_data script"
```

---

## Task 10: plot 스크립트 — 스캐폴딩·데이터 로드·스타일

**Files:**
- Create: `scripts/model/overall/plot_drbc_basin_report_cards.py`

- [ ] **Step 1: 파일 생성**

```python
#!/usr/bin/env python3
"""DRBC 유역별 진단 리포트 카드 그림 생성."""
# /// script
# dependencies = [
#   "matplotlib>=3.8",
#   "numpy>=1.26",
#   "pandas>=2.2",
#   "scipy>=1.13",
#   "statsmodels>=0.14",
# ]
# ///

import logging
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

DATA_ROOT   = Path("output/model_analysis/legacy/overall_analysis/main_comparison/drbc_basin_report_cards")
SERIES_ROOT = Path("output/model_analysis/legacy/quantile_analysis/required_series")
ATTR_FILE   = Path("output/basin/drbc/analysis/basin_attributes/tables/drbc_selected_basin_analysis_table.csv")
WITHIN_FILE = Path("output/model_analysis/legacy/overall_analysis/main_comparison"
                   "/drbc_attribute_metric_correlations/within_basin/tables/within_basin_rho_table.csv")
METRICS_FILE= Path("output/model_analysis/legacy/overall_analysis/epoch_sensitivity/tables/basin_metrics.csv")

Q_BIN_LABELS = ["Q0-Q50", "Q50-Q90", "Q90-Q99", "Q99+"]
SEASON_ORDER = ["DJF", "MAM", "JJA", "SON"]
SEASON_COLORS= {"DJF": "#4477AA", "MAM": "#66BB6A", "JJA": "#EF5350", "SON": "#FF9800"}

# 색상 팔레트
M1_COLOR   = "#2277BB"
M2_COLOR   = "#EE7722"
OBS_COLOR  = "#222222"
RISE_COLOR = "#1976D2"
FALL_COLOR = "#E53935"

def load_tables() -> dict:
    tbl = DATA_ROOT / "tables"
    return {
        "regime":    pd.read_csv(tbl / "flow_regime_performance.csv", dtype={"basin": str}),
        "seasonal":  pd.read_csv(tbl / "seasonal_performance.csv",    dtype={"basin": str}),
        "events":    pd.read_csv(tbl / "event_peak_errors.csv",        dtype={"basin": str}),
        "summary":   pd.read_csv(tbl / "event_summary_per_basin.csv",  dtype={"basin": str}),
        "ante":      pd.read_csv(tbl / "antecedent_condition_perf.csv",dtype={"basin": str}),
        "rf":        pd.read_csv(tbl / "rising_falling_bias.csv",      dtype={"basin": str}),
        "feat_corr": pd.read_csv(tbl / "feature_regime_correlations.csv"),
    }

def load_basin_metadata() -> pd.DataFrame:
    attrs = pd.read_csv(ATTR_FILE, dtype={"gauge_id": str})
    attrs["gauge_id"] = attrs["gauge_id"].str.zfill(8)
    attrs = attrs.rename(columns={"gauge_id": "basin"}).set_index("basin")

    within = pd.read_csv(WITHIN_FILE, dtype={"basin": str}).set_index("basin")

    metrics = pd.read_csv(METRICS_FILE, dtype={"basin": str})
    basin_ids = sorted(metrics["basin"].str.zfill(8).unique())

    result = []
    for b in basin_ids:
        name = attrs.loc[b, "gauge_name"] if b in attrs.index else b
        area = attrs.loc[b, "drain_sqkm_attr"] if b in attrs.index else np.nan
        rho  = within.loc[b, "within_m1_bias_rho"] if b in within.index else np.nan
        result.append({"basin": b, "name": name, "area": area, "within_bias_rho": rho})
    return pd.DataFrame(result).set_index("basin")

def load_fdc_series(basin: str) -> dict:
    """FDC 계산용 seed111 primary series 로드."""
    path = SERIES_ROOT / "seed111" / "epoch005_required_series.csv"
    df = pd.read_csv(path, dtype={"basin": str})
    df["basin"] = df["basin"].str.zfill(8)
    grp = df[df["basin"] == basin].dropna(subset=["obs"])
    grp = grp[grp["obs"] > 0]
    return {
        "obs":   np.sort(grp["obs"].values)[::-1],
        "model1":np.sort(grp["model1"].values)[::-1],
        "q50":   np.sort(grp["q50"].values)[::-1],
    }
```

- [ ] **Step 2: 커밋**

```bash
git add scripts/model/overall/plot_drbc_basin_report_cards.py
git commit -m "feat: add plot_drbc_basin_report_cards scaffolding"
```

---

## Task 11: 패널 P1–P4 함수

**Files:**
- Modify: `scripts/model/overall/plot_drbc_basin_report_cards.py`

- [ ] **Step 1: P1 FDC 패널**

```python
def plot_p1_fdc(ax: plt.Axes, basin: str) -> None:
    """P1: Flow Duration Curve (log-log)."""
    series = load_fdc_series(basin)
    n = len(series["obs"])
    ep = np.arange(1, n + 1) / n * 100  # exceedance probability %
    ax.semilogy(ep, series["obs"],    color=OBS_COLOR, lw=1.5, label="Obs")
    ax.semilogy(ep, series["model1"], color=M1_COLOR,  lw=1.2, label="M1",  alpha=0.8)
    ax.semilogy(ep, series["q50"],    color=M2_COLOR,  lw=1.2, label="M2 q50", alpha=0.8, ls="--")
    ax.set_xlabel("Exceedance prob. (%)", fontsize=7)
    ax.set_ylabel("Flow (m³/s)", fontsize=7)
    ax.set_title("FDC", fontsize=8, fontweight="bold")
    ax.legend(fontsize=6, loc="upper right")
    ax.tick_params(labelsize=6)
    ax.set_xlim(0, 100)
```

- [ ] **Step 2: P2 구간별 MAPE 패널**

```python
def plot_p2_regime_mape(ax: plt.Axes, basin: str, regime_df: pd.DataFrame) -> None:
    """P2: Q-bin별 MAPE bar (M1 vs M2 q50)."""
    sub = regime_df[regime_df["basin"] == basin].set_index("q_bin")
    bins = [b for b in Q_BIN_LABELS if b in sub.index]
    x = np.arange(len(bins)); w = 0.35
    ax.bar(x - w/2, [sub.loc[b, "m1_mape"] for b in bins],
           w, color=M1_COLOR, label="M1", alpha=0.85)
    ax.bar(x + w/2, [sub.loc[b, "m2_q50_mape"] for b in bins],
           w, color=M2_COLOR, label="M2 q50", alpha=0.85)
    ax.set_xticks(x); ax.set_xticklabels(bins, fontsize=6, rotation=20)
    ax.set_ylabel("MAPE (%)", fontsize=7)
    ax.set_title("MAPE by flow regime", fontsize=8, fontweight="bold")
    ax.legend(fontsize=6); ax.tick_params(labelsize=6)
```

- [ ] **Step 3: P3 구간별 Bias 패널**

```python
def plot_p3_regime_bias(ax: plt.Axes, basin: str, regime_df: pd.DataFrame) -> None:
    """P3: Q-bin별 Bias % (M1 vs M2 q50), 0 기준선 포함."""
    sub = regime_df[regime_df["basin"] == basin].set_index("q_bin")
    bins = [b for b in Q_BIN_LABELS if b in sub.index]
    x = np.arange(len(bins)); w = 0.35
    ax.bar(x - w/2, [sub.loc[b, "m1_bias"] for b in bins],
           w, color=M1_COLOR, label="M1", alpha=0.85)
    ax.bar(x + w/2, [sub.loc[b, "m2_q50_bias"] for b in bins],
           w, color=M2_COLOR, label="M2 q50", alpha=0.85)
    ax.axhline(0, color="black", lw=0.8, ls="--")
    ax.set_xticks(x); ax.set_xticklabels(bins, fontsize=6, rotation=20)
    ax.set_ylabel("Bias (%)", fontsize=7)
    ax.set_title("Bias by flow regime", fontsize=8, fontweight="bold")
    ax.legend(fontsize=6); ax.tick_params(labelsize=6)
```

- [ ] **Step 4: P4 M2 구간폭 + Coverage 패널**

```python
def plot_p4_m2_interval(ax: plt.Axes, basin: str, regime_df: pd.DataFrame) -> None:
    """P4: M2 [q50–q99] 폭/obs 비율 (bar) + q90/q99 coverage (line)."""
    sub = regime_df[regime_df["basin"] == basin].set_index("q_bin")
    bins = [b for b in Q_BIN_LABELS if b in sub.index]
    x = np.arange(len(bins))

    ax2 = ax.twinx()
    ax.bar(x, [sub.loc[b, "m2_interval_width_ratio"] for b in bins],
           0.6, color="#9C27B0", alpha=0.6, label="Width/obs")
    ax2.plot(x, [sub.loc[b, "m2_q90_coverage"] for b in bins],
             "o--", color="#00BCD4", lw=1.2, ms=4, label="Coverage q90")
    ax2.plot(x, [sub.loc[b, "m2_q99_coverage"] for b in bins],
             "s-",  color="#F44336", lw=1.2, ms=4, label="Coverage q99")
    ax2.axhline(0.99, color="#F44336", lw=0.6, ls=":", alpha=0.5)
    ax2.axhline(0.90, color="#00BCD4", lw=0.6, ls=":", alpha=0.5)
    ax2.set_ylim(0, 1.1); ax2.set_ylabel("Coverage", fontsize=7)
    ax.set_xticks(x); ax.set_xticklabels(bins, fontsize=6, rotation=20)
    ax.set_ylabel("Interval width / obs", fontsize=7)
    ax.set_title("M2 interval width & coverage", fontsize=8, fontweight="bold")
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=6, loc="upper left")
    ax.tick_params(labelsize=6); ax2.tick_params(labelsize=6)
```

- [ ] **Step 5: 커밋**

```bash
git add scripts/model/overall/plot_drbc_basin_report_cards.py
git commit -m "feat: add panel P1-P4 plot functions"
```

---

## Task 12: 패널 P5–P8 함수

**Files:**
- Modify: `scripts/model/overall/plot_drbc_basin_report_cards.py`

- [ ] **Step 1: P5 계절 패턴 패널**

```python
def plot_p5_seasonal(ax: plt.Axes, basin: str, seasonal_df: pd.DataFrame) -> None:
    """P5: Q99+ 계절 분포 (막대) + 계절별 M1 MAPE (선, 이중 축)."""
    sub = seasonal_df[seasonal_df["basin"] == basin].set_index("season")
    seasons = [s for s in SEASON_ORDER if s in sub.index]
    x = np.arange(len(seasons))

    # Q99+ 분포 비율
    q99_counts = [sub.loc[s, "q99_hour_count"] for s in seasons]
    total = sum(q99_counts) if sum(q99_counts) > 0 else 1
    q99_fracs = [c / total * 100 for c in q99_counts]

    ax2 = ax.twinx()
    bars = ax.bar(x, q99_fracs, 0.6,
                  color=[SEASON_COLORS[s] for s in seasons], alpha=0.75)
    ax2.plot(x, [sub.loc[s, "m1_mape"] for s in seasons],
             "ko-", lw=1.5, ms=5, label="M1 MAPE")
    ax.set_xticks(x); ax.set_xticklabels(seasons, fontsize=7)
    ax.set_ylabel("Q99+ occurrence (%)", fontsize=7)
    ax2.set_ylabel("M1 MAPE (%)", fontsize=7)
    ax.set_title("Seasonal pattern (Q99+ & MAPE)", fontsize=8, fontweight="bold")
    ax2.legend(fontsize=6); ax.tick_params(labelsize=6); ax2.tick_params(labelsize=6)
```

- [ ] **Step 2: P6 사건 첨두 산점 패널**

```python
def plot_p6_event_peak(ax: plt.Axes, basin: str, event_df: pd.DataFrame) -> None:
    """P6: 홍수 사건 obs_peak vs M1 peak_ratio, 계절 색상 코딩."""
    sub = event_df[event_df["basin"] == basin].dropna(subset=["m1_peak_ratio"])
    if sub.empty:
        ax.text(0.5, 0.5, "No events", ha="center", va="center", transform=ax.transAxes)
        return
    for season in SEASON_ORDER:
        mask = sub["season"] == season
        if mask.sum() == 0:
            continue
        ax.scatter(sub.loc[mask, "obs_peak"], sub.loc[mask, "m1_peak_ratio"],
                   s=25, color=SEASON_COLORS[season], label=season, alpha=0.8, edgecolors="white", lw=0.3)
    ax.axhline(1.0, color="black", lw=0.8, ls="-",  alpha=0.6, label="Ratio=1.0")
    ax.axhline(0.7, color="red",   lw=0.8, ls="--", alpha=0.5, label="Ratio=0.7")
    ax.set_xscale("log")
    ax.set_xlabel("Obs peak (m³/s)", fontsize=7)
    ax.set_ylabel("M1 peak / obs peak", fontsize=7)
    ax.set_title("Event peak ratio", fontsize=8, fontweight="bold")
    ax.legend(fontsize=5, ncol=2); ax.tick_params(labelsize=6)
```

- [ ] **Step 3: P7 선행 조건 패널**

```python
def plot_p7_antecedent(ax: plt.Axes, basin: str, ante_df: pd.DataFrame) -> None:
    """P7: dry/normal/wet 조건별 M1 MAPE bar."""
    sub = ante_df[ante_df["basin"] == basin].set_index("condition")
    conditions = [c for c in ["dry", "normal", "wet"] if c in sub.index]
    colors = {"dry": "#FF9800", "normal": "#4CAF50", "wet": "#2196F3"}
    if not conditions:
        ax.text(0.5, 0.5, "Insufficient events", ha="center", va="center",
                transform=ax.transAxes, fontsize=7)
        return
    x = np.arange(len(conditions))
    vals = [sub.loc[c, "m1_mape"] for c in conditions]
    ax.bar(x, vals, 0.6, color=[colors[c] for c in conditions], alpha=0.85)
    ax.set_xticks(x); ax.set_xticklabels(conditions, fontsize=7)
    ax.set_ylabel("M1 MAPE (%)", fontsize=7)
    ax.set_title("Antecedent condition effect", fontsize=8, fontweight="bold")
    ax.tick_params(labelsize=6)
    # n_events 표시
    for xi, c in enumerate(conditions):
        n = int(sub.loc[c, "n_events"])
        ax.text(xi, vals[xi] * 1.02, f"n={n}", ha="center", fontsize=5.5)
```

- [ ] **Step 4: P8 상승/하강 비대칭 패널**

```python
def plot_p8_rising_falling(ax: plt.Axes, basin: str, rf_df: pd.DataFrame) -> None:
    """P8: Rising vs Falling limb M1 / M2 q50 Bias %."""
    sub = rf_df[rf_df["basin"] == basin].set_index("phase")
    phases = [p for p in ["rising", "falling"] if p in sub.index]
    if not phases:
        ax.text(0.5, 0.5, "Insufficient events", ha="center", va="center",
                transform=ax.transAxes, fontsize=7)
        return
    x = np.arange(len(phases)); w = 0.35
    ax.bar(x - w/2, [sub.loc[p, "m1_bias"]     for p in phases],
           w, color=M1_COLOR, label="M1", alpha=0.85)
    ax.bar(x + w/2, [sub.loc[p, "m2_q50_bias"] for p in phases],
           w, color=M2_COLOR, label="M2 q50", alpha=0.85)
    ax.axhline(0, color="black", lw=0.8, ls="--")
    ax.set_xticks(x); ax.set_xticklabels(phases, fontsize=7)
    ax.set_ylabel("Bias (%)", fontsize=7)
    ax.set_title("Rising vs Falling limb bias", fontsize=8, fontweight="bold")
    ax.legend(fontsize=6); ax.tick_params(labelsize=6)
```

- [ ] **Step 5: 커밋**

```bash
git add scripts/model/overall/plot_drbc_basin_report_cards.py
git commit -m "feat: add panel P5-P8 plot functions"
```

---

## Task 13: 리포트 카드 조립 (통합 + 개별 패널)

**Files:**
- Modify: `scripts/model/overall/plot_drbc_basin_report_cards.py`

- [ ] **Step 1: `assemble_report_card` 함수 추가**

```python
def assemble_report_card(basin: str, meta: pd.Series, tables: dict,
                         out_dir: Path, panel_dir: Path, dpi_combined: int = 300,
                         dpi_panel: int = 150) -> None:
    """8-패널 통합 그림 + 개별 패널 PNG 생성."""
    name = str(meta.get("name", basin))[:40]
    area = meta.get("area", np.nan)
    rho  = meta.get("within_bias_rho", np.nan)
    title = (f"Basin {basin} — {name}  "
             f"(Area={area:.0f} km²  |  within_bias_ρ={rho:.3f})")

    panel_funcs = [
        ("p1_fdc",            lambda ax: plot_p1_fdc(ax, basin)),
        ("p2_regime_mape",    lambda ax: plot_p2_regime_mape(ax, basin, tables["regime"])),
        ("p3_regime_bias",    lambda ax: plot_p3_regime_bias(ax, basin, tables["regime"])),
        ("p4_m2_interval",    lambda ax: plot_p4_m2_interval(ax, basin, tables["regime"])),
        ("p5_seasonal",       lambda ax: plot_p5_seasonal(ax, basin, tables["seasonal"])),
        ("p6_event_peak",     lambda ax: plot_p6_event_peak(ax, basin, tables["events"])),
        ("p7_antecedent",     lambda ax: plot_p7_antecedent(ax, basin, tables["ante"])),
        ("p8_rising_falling", lambda ax: plot_p8_rising_falling(ax, basin, tables["rf"])),
    ]

    # 개별 패널 저장
    panel_dir.mkdir(parents=True, exist_ok=True)
    for pname, pfunc in panel_funcs:
        fig_p, ax_p = plt.subplots(figsize=(5, 4))
        pfunc(ax_p)
        fig_p.tight_layout()
        fig_p.savefig(panel_dir / f"{basin}_{pname}.png", dpi=dpi_panel, bbox_inches="tight")
        plt.close(fig_p)

    # 통합 8-패널
    fig = plt.figure(figsize=(14, 9))
    fig.suptitle(title, fontsize=9, y=1.01)
    gs = gridspec.GridSpec(2, 4, figure=fig, hspace=0.45, wspace=0.38)
    axes = [fig.add_subplot(gs[r, c]) for r in range(2) for c in range(4)]
    for ax, (_, pfunc) in zip(axes, panel_funcs):
        pfunc(ax)
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{basin}_report_card.png", dpi=dpi_combined, bbox_inches="tight")
    plt.close(fig)
```

- [ ] **Step 2: 첫 번째 유역으로 테스트**

```python
# plot 스크립트에 임시 main 추가
if __name__ == "__main__":
    tables = load_tables()
    meta   = load_basin_metadata()
    basin_ids = meta.index.tolist()

    # 첫 번째 유역만 테스트
    test_basin = basin_ids[0]
    out_dir    = DATA_ROOT / "figures" / "report_cards"
    panel_dir  = out_dir / "panels"
    assemble_report_card(test_basin, meta.loc[test_basin], tables, out_dir, panel_dir)
    log.info("test report card saved for %s", test_basin)
```

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run scripts/model/overall/plot_drbc_basin_report_cards.py 2>&1
ls output/model_analysis/legacy/overall_analysis/main_comparison/drbc_basin_report_cards/figures/report_cards/
```
Expected: `{basin_id}_report_card.png` 1개 + panels/ 디렉토리에 8개 PNG

- [ ] **Step 3: 커밋**

```bash
git add scripts/model/overall/plot_drbc_basin_report_cards.py
git commit -m "feat: add report card assembly (combined + individual panels)"
```

---

## Task 14: Cross-basin 요약 그림

**Files:**
- Modify: `scripts/model/overall/plot_drbc_basin_report_cards.py`

- [ ] **Step 1: `plot_regime_heatmaps` 추가**

```python
FEATURE_LABELS = {
    "drain_sqkm_attr": "Area (km²)", "log10_area": "log10(Area)",
    "frac_snow": "Snow frac.", "p_seasonality": "Seasonality",
    "lat_gage": "Latitude", "elev_mean_m": "Elevation",
    "slope_pct": "Slope (%)", "developed_frac": "Developed",
    "forest_frac": "Forest", "soil_permeability_index": "Permeability",
    "aridity": "Aridity", "baseflow_index_pct": "Baseflow idx",
    "high_prec_freq": "High prec. freq.", "soil_available_water_capacity": "Soil AWC",
    "SANDAVE": "Sand", "CLAYAVE": "Clay",
}
METRIC_LABELS = {
    "m1_mape": "M1 MAPE", "m1_bias": "M1 Bias",
    "m2_q50_mape": "M2 MAPE", "m2_q99_coverage": "M2 q99 cov.",
}

def plot_regime_heatmaps(feat_corr_df: pd.DataFrame, out_dir: Path) -> None:
    """Q-bin별 feature × metric 상관 heatmap 4개."""
    out_dir.mkdir(parents=True, exist_ok=True)
    feats   = list(FEATURE_LABELS.keys())
    metrics = list(METRIC_LABELS.keys())
    fname_map = {
        "Q0-Q50": "heatmap_regime_Q0Q50.png",
        "Q50-Q90": "heatmap_regime_Q50Q90.png",
        "Q90-Q99": "heatmap_regime_Q90Q99.png",
        "Q99+": "heatmap_regime_Q99plus.png",
    }
    for q_bin in Q_BIN_LABELS:
        sub = feat_corr_df[feat_corr_df["q_bin"] == q_bin]
        rho_mat = np.full((len(feats), len(metrics)), np.nan)
        sig_mat = np.zeros_like(rho_mat, dtype=bool)
        for row in sub.itertuples():
            fi = feats.index(row.feature)   if row.feature in feats   else -1
            mi = metrics.index(row.metric)  if row.metric  in metrics else -1
            if fi >= 0 and mi >= 0:
                rho_mat[fi, mi] = row.rho
                sig_mat[fi, mi] = row.significant

        fig, ax = plt.subplots(figsize=(8, 9))
        im = ax.imshow(rho_mat, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
        plt.colorbar(im, ax=ax, label="Spearman ρ", shrink=0.6)
        ax.set_xticks(range(len(metrics)))
        ax.set_xticklabels([METRIC_LABELS[m] for m in metrics], fontsize=8, rotation=20, ha="right")
        ax.set_yticks(range(len(feats)))
        ax.set_yticklabels([FEATURE_LABELS.get(f, f) for f in feats], fontsize=8)
        ax.set_title(f"Feature × Performance Correlation  [{q_bin}]\n(* = BH FDR p<0.05)", fontsize=9)
        for fi in range(len(feats)):
            for mi in range(len(metrics)):
                if not np.isnan(rho_mat[fi, mi]):
                    marker = "*" if sig_mat[fi, mi] else ""
                    v = rho_mat[fi, mi]
                    c = "white" if abs(v) > 0.5 else "black"
                    ax.text(mi, fi, f"{v:.2f}{marker}", ha="center", va="center",
                            fontsize=6, color=c)
        plt.tight_layout()
        fig.savefig(out_dir / fname_map[q_bin], dpi=150, bbox_inches="tight")
        plt.close(fig)
        log.info("heatmap saved: %s", fname_map[q_bin])
```

- [ ] **Step 2: `plot_event_capture_ranking` 추가**

```python
def plot_event_capture_ranking(summary_df: pd.DataFrame, meta: pd.DataFrame,
                                out_dir: Path) -> None:
    """38유역 포착률 수평 bar chart, 면적 색상 코딩."""
    df = summary_df.copy()
    df["area"] = df["basin"].map(meta["area"])
    df = df.sort_values("capture_rate_pct", ascending=True)

    fig, ax = plt.subplots(figsize=(8, 10))
    colors = plt.cm.viridis(
        (np.log10(df["area"].clip(lower=1)) - np.log10(df["area"].clip(lower=1)).min()) /
        (np.log10(df["area"].clip(lower=1)).max() - np.log10(df["area"].clip(lower=1)).min() + 1e-6)
    )
    bars = ax.barh(range(len(df)), df["capture_rate_pct"], color=colors, alpha=0.85)
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(df["basin"].tolist(), fontsize=6)
    ax.axvline(70, color="red", lw=1, ls="--", label="70% threshold")
    ax.set_xlabel("Event capture rate (peak_ratio ≥ 0.7, %)", fontsize=9)
    ax.set_title("Event Capture Rate Ranking — 38 DRBC Basins\n(color = log10 area)", fontsize=9)
    ax.legend(fontsize=8)
    sm = plt.cm.ScalarMappable(cmap="viridis")
    sm.set_array([]); plt.colorbar(sm, ax=ax, label="log10(Area km²)", shrink=0.4)
    plt.tight_layout()
    fig.savefig(out_dir / "event_capture_rate_ranking.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("event capture ranking saved")
```

- [ ] **Step 3: `plot_antecedent_effect_dist` 추가**

```python
def plot_antecedent_effect_dist(ante_df: pd.DataFrame, out_dir: Path) -> None:
    """dry vs wet MAPE 차이 분포 (38유역)."""
    dry_mape = ante_df[ante_df["condition"] == "dry"].set_index("basin")["m1_mape"]
    wet_mape = ante_df[ante_df["condition"] == "wet"].set_index("basin")["m1_mape"]
    common = dry_mape.index.intersection(wet_mape.index)
    diff = dry_mape[common] - wet_mape[common]  # 양수 = dry 조건이 더 나쁨

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.hist(diff.values, bins=12, color="#5C6BC0", edgecolor="white", alpha=0.85)
    ax.axvline(0, color="black", lw=1.2, ls="--", label="No difference")
    ax.axvline(float(diff.median()), color="red", lw=1.5,
               label=f"Median={diff.median():.1f}%")
    ax.set_xlabel("MAPE(dry) − MAPE(wet) (%)", fontsize=9)
    ax.set_ylabel("Basin count", fontsize=9)
    ax.set_title("Antecedent Condition Effect\n(positive = dry events harder to predict)", fontsize=9)
    ax.legend(fontsize=8)
    plt.tight_layout()
    fig.savefig(out_dir / "antecedent_effect_distribution.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("antecedent effect distribution saved")
```

- [ ] **Step 4: 커밋**

```bash
git add scripts/model/overall/plot_drbc_basin_report_cards.py
git commit -m "feat: add cross-basin summary figures"
```

---

## Task 15: plot 스크립트 main() 완성 + 요약 리포트

**Files:**
- Modify: `scripts/model/overall/plot_drbc_basin_report_cards.py`

- [ ] **Step 1: main() 완성**

```python
def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--basins", nargs="*", default=None,
                        help="특정 유역만 처리 (기본: 전체 38개)")
    parser.add_argument("--dpi-combined", type=int, default=300)
    parser.add_argument("--dpi-panel",    type=int, default=150)
    args = parser.parse_args()

    tables   = load_tables()
    meta     = load_basin_metadata()
    all_ids  = meta.index.tolist()
    basin_ids = args.basins if args.basins else all_ids

    card_dir  = DATA_ROOT / "figures" / "report_cards"
    panel_dir = card_dir / "panels"
    cross_dir = DATA_ROOT / "figures" / "cross_basin"

    log.info("=== generating %d report cards ===", len(basin_ids))
    for i, basin in enumerate(basin_ids):
        log.info("  [%d/%d] %s", i + 1, len(basin_ids), basin)
        if basin not in meta.index:
            log.warning("  basin %s not in metadata, skipping", basin)
            continue
        assemble_report_card(basin, meta.loc[basin], tables,
                             card_dir, panel_dir,
                             args.dpi_combined, args.dpi_panel)

    log.info("=== cross-basin figures ===")
    plot_regime_heatmaps(tables["feat_corr"], cross_dir)
    plot_event_capture_ranking(tables["summary"], meta, cross_dir)
    plot_antecedent_effect_dist(tables["ante"], cross_dir)

    log.info("=== done ===")
    log.info("report cards: %s", card_dir)
    log.info("cross basin:  %s", cross_dir)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 전체 실행**

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run scripts/model/overall/plot_drbc_basin_report_cards.py 2>&1 | tee /tmp/plot_log.txt
tail -10 /tmp/plot_log.txt
```
Expected: 에러 없이 완료

```bash
ls output/model_analysis/legacy/overall_analysis/main_comparison/drbc_basin_report_cards/figures/report_cards/ | wc -l
ls output/model_analysis/legacy/overall_analysis/main_comparison/drbc_basin_report_cards/figures/report_cards/panels/ | wc -l
ls output/model_analysis/legacy/overall_analysis/main_comparison/drbc_basin_report_cards/figures/cross_basin/
```
Expected: report_cards/ 38개, panels/ 304개(38×8), cross_basin/ 6개

- [ ] **Step 3: 최종 커밋**

```bash
git add scripts/model/overall/plot_drbc_basin_report_cards.py
git commit -m "feat: complete plot_drbc_basin_report_cards script"
```
