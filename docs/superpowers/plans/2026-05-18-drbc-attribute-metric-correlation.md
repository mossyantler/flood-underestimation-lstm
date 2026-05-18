# DRBC Attribute–Metric Correlation Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 38개 DRBC 유역의 20개 특성과 24개 모델 성능 지표 간 Spearman 상관관계를 계산하고, heatmap·scatter·마크다운 리포트로 출력하는 단일 스크립트를 작성한다.

**Architecture:** 단일 스크립트(`analyze_drbc_basin_attribute_metric_correlations.py`)가 CSV 특성, 결정론적 지표, raw quantile series를 읽어 master table을 구성하고, 480 쌍의 Spearman ρ를 BH FDR 보정 후 테이블·그림·리포트로 저장한다. 분석 단위는 seed 중앙값 집계 기준 38 basins이다.

**Tech Stack:** Python 3.11+, uv, pandas 2.2, numpy 1.26, scipy 1.13, statsmodels 0.14, matplotlib 3.8

---

## 파일 구조

| 역할 | 경로 |
|------|------|
| 신규 생성 | `scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py` |
| 읽기 전용 | `output/basin/drbc/analysis/basin_attributes/tables/drbc_selected_basin_analysis_table.csv` |
| 읽기 전용 | `output/model_analysis/overall_analysis/epoch_sensitivity/tables/basin_metrics.csv` |
| 읽기 전용 | `output/model_analysis/overall_analysis/main_comparison/tables/primary_epoch_basin_deltas.csv` |
| 읽기 전용 | `output/model_analysis/quantile_analysis/required_series/seed{s}/epoch{e}_required_series.csv` |
| 출력 루트 | `output/model_analysis/overall_analysis/main_comparison/drbc_attribute_metric_correlations/` |

---

## Task 1: 스크립트 골격 — 의존성, 상수, argparse

**Files:**
- Create: `scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py`

- [ ] **Step 1: 파일 생성 — 의존성 블록과 import**

```python
#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.8",
#   "numpy>=1.26",
#   "pandas>=2.2",
#   "scipy>=1.13",
#   "statsmodels>=0.14",
# ]
# ///
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests

REPO_ROOT = Path(__file__).resolve().parents[3]
```

- [ ] **Step 2: 도메인 상수 작성**

```python
OFFICIAL_SEEDS = [111, 222, 444]

PRIMARY_EPOCHS = {
    111: {"model1": 25, "model2": 5},
    222: {"model1": 10, "model2": 10},
    444: {"model1": 15, "model2": 10},
}

QUANTILES = ["q50", "q90", "q95", "q99"]
TAUS = {"q50": 0.50, "q90": 0.90, "q95": 0.95, "q99": 0.99}

FEATURE_COLS = [
    "area", "log10_area", "snow_fraction", "seasonal", "latitude",
    "elevation", "slope", "human_use", "land_use", "permeability",
    "aridity", "baseflow_index", "high_prec_freq", "soil_water_capacity",
    "sand_frac", "clay_frac",
    "obs_cv", "obs_fdc_slope", "obs_q99", "obs_mean_flow",
]

FEATURE_LABELS = {
    "area": "Area (km²)",
    "log10_area": "log₁₀(Area)",
    "snow_fraction": "Snow fraction",
    "seasonal": "Precipitation seasonality",
    "latitude": "Latitude",
    "elevation": "Elevation (m)",
    "slope": "Slope (%)",
    "human_use": "Human use (developed frac.)",
    "land_use": "Land use (forest frac.)",
    "permeability": "Permeability",
    "aridity": "Aridity (PET/P)",
    "baseflow_index": "Baseflow index",
    "high_prec_freq": "High prec. frequency",
    "soil_water_capacity": "Soil water capacity",
    "sand_frac": "Sand fraction",
    "clay_frac": "Clay fraction",
    "obs_cv": "Flow CV",
    "obs_fdc_slope": "FDC slope",
    "obs_q99": "Q99 flow (m³/s)",
    "obs_mean_flow": "Mean flow (m³/s)",
}

METRIC_COLS_ALL = (
    [f"m1_{m}" for m in ["NSE", "KGE", "FHV", "Peak_Timing", "Peak_MAPE"]]
    + [f"m2_{m}" for m in ["NSE", "KGE", "FHV", "Peak_Timing", "Peak_MAPE"]]
    + ["delta_NSE", "delta_KGE", "delta_FHV", "Peak_Timing_reduction", "Peak_MAPE_reduction"]
    + [f"pinball_{q}" for q in QUANTILES]
    + [f"coverage_{q}" for q in QUANTILES]
    + ["tail_hit_q99"]
)

METRIC_LABELS = {
    "m1_NSE": "M1 NSE", "m1_KGE": "M1 KGE", "m1_FHV": "M1 FHV",
    "m1_Peak_Timing": "M1 Peak-Timing", "m1_Peak_MAPE": "M1 Peak-MAPE",
    "m2_NSE": "M2 NSE", "m2_KGE": "M2 KGE", "m2_FHV": "M2 FHV",
    "m2_Peak_Timing": "M2 Peak-Timing", "m2_Peak_MAPE": "M2 Peak-MAPE",
    "delta_NSE": "ΔNSE", "delta_KGE": "ΔKGE", "delta_FHV": "ΔFHV",
    "Peak_Timing_reduction": "ΔPeak-Timing", "Peak_MAPE_reduction": "ΔPeak-MAPE",
    "pinball_q50": "Pinball q50", "pinball_q90": "Pinball q90",
    "pinball_q95": "Pinball q95", "pinball_q99": "Pinball q99",
    "coverage_q50": "Coverage q50", "coverage_q90": "Coverage q90",
    "coverage_q95": "Coverage q95", "coverage_q99": "Coverage q99",
    "tail_hit_q99": "Tail hit rate q99",
}

# heatmap 그룹 (그림 4개)
HEATMAP_GROUPS = {
    "model1": ([f"m1_{m}" for m in ["NSE", "KGE", "FHV", "Peak_Timing", "Peak_MAPE"]], "Model 1"),
    "model2_q50": ([f"m2_{m}" for m in ["NSE", "KGE", "FHV", "Peak_Timing", "Peak_MAPE"]], "Model 2 q50"),
    "delta": (["delta_NSE", "delta_KGE", "delta_FHV", "Peak_Timing_reduction", "Peak_MAPE_reduction"], "Paired delta (M2−M1)"),
    "model2_prob": (
        [f"pinball_{q}" for q in QUANTILES] + [f"coverage_{q}" for q in QUANTILES] + ["tail_hit_q99"],
        "Model 2 probabilistic",
    ),
}

DEFAULT_DRBC_ATTRS = REPO_ROOT / "output/basin/drbc/analysis/basin_attributes/tables/drbc_selected_basin_analysis_table.csv"
DEFAULT_BASIN_METRICS = REPO_ROOT / "output/model_analysis/overall_analysis/epoch_sensitivity/tables/basin_metrics.csv"
DEFAULT_BASIN_DELTAS = REPO_ROOT / "output/model_analysis/overall_analysis/main_comparison/tables/primary_epoch_basin_deltas.csv"
DEFAULT_SERIES_DIR = REPO_ROOT / "output/model_analysis/quantile_analysis/required_series"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/overall_analysis/main_comparison/drbc_attribute_metric_correlations"
```

- [ ] **Step 3: argparse 작성**

```python
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="DRBC basin attribute × model metric Spearman correlation")
    p.add_argument("--seeds", nargs="+", type=int, default=OFFICIAL_SEEDS)
    p.add_argument("--top-n", type=int, default=20)
    p.add_argument("--fdr-alpha", type=float, default=0.05)
    p.add_argument("--drbc-attrs", type=Path, default=DEFAULT_DRBC_ATTRS)
    p.add_argument("--basin-metrics", type=Path, default=DEFAULT_BASIN_METRICS)
    p.add_argument("--basin-deltas", type=Path, default=DEFAULT_BASIN_DELTAS)
    p.add_argument("--series-dir", type=Path, default=DEFAULT_SERIES_DIR)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output: {args.output_dir}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 실행 확인 (골격 동작)**

```bash
uv run scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py
```

Expected: `Output: .../drbc_attribute_metric_correlations` 출력 후 정상 종료.

- [ ] **Step 5: 커밋**

```bash
git add scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py
git commit -m "feat: scaffold drbc attribute-metric correlation script"
```

---

## Task 2: `load_basin_features()` — CSV 특성 16개 로딩

**Files:**
- Modify: `scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py`

- [ ] **Step 1: 함수 작성**

```python
def load_basin_features(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"gauge_id": str})
    df["gauge_id"] = df["gauge_id"].str.zfill(8)

    out = pd.DataFrame({"basin": df["gauge_id"]})
    out["area"] = df["drain_sqkm_attr"]
    out["log10_area"] = np.log10(df["drain_sqkm_attr"].clip(lower=1e-6))
    out["snow_fraction"] = df["frac_snow"]
    out["seasonal"] = df["p_seasonality"]
    out["latitude"] = df["lat_gage"]
    out["elevation"] = df["elev_mean_m"]
    out["slope"] = df["slope_pct"]
    out["human_use"] = df["developed_frac"]
    out["land_use"] = df["forest_frac"]
    out["permeability"] = df["soil_permeability_index"]
    out["aridity"] = df["aridity"]
    out["baseflow_index"] = df["baseflow_index_pct"]
    out["high_prec_freq"] = df["high_prec_freq"]
    out["soil_water_capacity"] = df["soil_available_water_capacity"]
    out["sand_frac"] = df["SANDAVE"] / 100.0
    out["clay_frac"] = df["CLAYAVE"] / 100.0

    assert len(out) == 38, f"Expected 38 basins, got {len(out)}"
    assert out["basin"].nunique() == 38
    return out.set_index("basin")
```

- [ ] **Step 2: main()에서 호출 및 출력 확인**

```python
# main() 안에 추가
features = load_basin_features(args.drbc_attrs)
print(f"Features: {features.shape}  columns={list(features.columns)}")
```

- [ ] **Step 3: 실행 확인**

```bash
uv run scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py
```

Expected 출력 예시:
```
Features: (38, 16)  columns=['area', 'log10_area', 'snow_fraction', ...]
```

- [ ] **Step 4: 커밋**

```bash
git add scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py
git commit -m "feat: add load_basin_features with 16 CSV attributes"
```

---

## Task 3: `load_deterministic_metrics()` — M1/M2 절댓값 + delta 로딩

**Files:**
- Modify: `scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py`

- [ ] **Step 1: 함수 작성**

```python
def load_deterministic_metrics(
    metrics_path: Path, deltas_path: Path, seeds: list[int]
) -> pd.DataFrame:
    raw = pd.read_csv(metrics_path, dtype={"basin": str})
    raw["basin"] = raw["basin"].str.zfill(8)
    raw = raw[raw["split"] == "test"]

    rows = []
    for seed in seeds:
        m1_epoch = PRIMARY_EPOCHS[seed]["model1"]
        m2_epoch = PRIMARY_EPOCHS[seed]["model2"]
        m1 = raw[(raw["model"] == "model1") & (raw["seed"] == seed) & (raw["epoch"] == m1_epoch)]
        m2 = raw[(raw["model"] == "model2") & (raw["seed"] == seed) & (raw["epoch"] == m2_epoch)]
        for _, row in m1.iterrows():
            basin = row["basin"]
            m2_row = m2[m2["basin"] == basin]
            if m2_row.empty:
                continue
            m2r = m2_row.iloc[0]
            rows.append({
                "seed": seed, "basin": basin,
                "m1_NSE": row["NSE"], "m1_KGE": row["KGE"], "m1_FHV": row["FHV"],
                "m1_Peak_Timing": row["Peak-Timing"], "m1_Peak_MAPE": row["Peak-MAPE"],
                "m2_NSE": m2r["NSE"], "m2_KGE": m2r["KGE"], "m2_FHV": m2r["FHV"],
                "m2_Peak_Timing": m2r["Peak-Timing"], "m2_Peak_MAPE": m2r["Peak-MAPE"],
            })
    seed_df = pd.DataFrame(rows)

    deltas = pd.read_csv(deltas_path, dtype={"basin": str})
    deltas["basin"] = deltas["basin"].str.zfill(8)
    deltas = deltas[deltas["seed"].isin(seeds)][
        ["seed", "basin", "delta_NSE", "delta_KGE", "delta_FHV",
         "Peak_Timing_reduction", "Peak_MAPE_reduction"]
    ]

    merged = seed_df.merge(deltas, on=["seed", "basin"], how="inner")

    # seed 중앙값 집계 → 38행
    agg = merged.drop(columns=["seed"]).groupby("basin").median()
    assert len(agg) == 38, f"Expected 38 basins after aggregation, got {len(agg)}"
    return agg
```

- [ ] **Step 2: main()에서 호출 및 확인**

```python
det_metrics = load_deterministic_metrics(args.basin_metrics, args.basin_deltas, args.seeds)
print(f"Det metrics: {det_metrics.shape}  columns={list(det_metrics.columns)}")
```

- [ ] **Step 3: 실행 확인**

```bash
uv run scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py
```

Expected:
```
Det metrics: (38, 15)  columns=['m1_NSE', 'm1_KGE', ..., 'Peak_MAPE_reduction']
```

- [ ] **Step 4: 커밋**

```bash
git add scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py
git commit -m "feat: add load_deterministic_metrics for M1/M2/delta"
```

---

## Task 4: `compute_obs_features()` — raw obs에서 CV/FDC/Q99/mean 계산

**Files:**
- Modify: `scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py`

- [ ] **Step 1: 함수 작성**

obs는 모든 seed에서 동일하므로 seed 111 primary series 하나만 읽는다.

```python
def compute_obs_features(series_dir: Path) -> pd.DataFrame:
    seed = 111
    epoch = PRIMARY_EPOCHS[seed]["model2"]  # epoch 5
    path = series_dir / f"seed{seed}" / f"epoch{epoch:03d}_required_series.csv"
    df = pd.read_csv(path, usecols=["basin", "obs"], dtype={"basin": str})
    df["basin"] = df["basin"].str.zfill(8)

    rows = []
    for basin, grp in df.groupby("basin", sort=False):
        obs = grp["obs"].to_numpy(dtype=float)
        mean_flow = float(np.mean(obs))
        cv = float(np.std(obs) / mean_flow) if mean_flow > 0 else float("nan")
        q10 = float(np.percentile(obs, 90))   # exceedance 10% = 90th percentile
        q90 = float(np.percentile(obs, 10))   # exceedance 90% = 10th percentile
        fdc_slope = float(np.log10(q10 / q90)) if q90 > 0 else float("nan")
        q99 = float(np.percentile(obs, 99))
        rows.append({
            "basin": basin,
            "obs_cv": cv,
            "obs_fdc_slope": fdc_slope,
            "obs_q99": q99,
            "obs_mean_flow": mean_flow,
        })

    out = pd.DataFrame(rows).set_index("basin")
    assert len(out) == 38, f"Expected 38 basins, got {len(out)}"
    return out
```

- [ ] **Step 2: main()에서 호출 및 확인**

```python
obs_features = compute_obs_features(args.series_dir)
print(f"Obs features: {obs_features.shape}")
print(obs_features[["obs_cv", "obs_fdc_slope", "obs_q99", "obs_mean_flow"]].describe().round(3))
```

- [ ] **Step 3: 실행 확인 — 통계 정상 범위 점검**

```bash
uv run scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py
```

Expected: obs_cv > 0, obs_fdc_slope > 0, obs_q99 >> obs_mean_flow. NaN 없음.

- [ ] **Step 4: 커밋**

```bash
git add scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py
git commit -m "feat: add compute_obs_features (CV, FDC slope, Q99, mean flow)"
```

---

## Task 5: `compute_probabilistic_metrics()` — pinball/coverage/tail hit 유역별 계산

**Files:**
- Modify: `scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py`

- [ ] **Step 1: 단위 함수 작성**

```python
def pinball_loss(obs: np.ndarray, pred: np.ndarray, tau: float) -> float:
    err = obs - pred
    return float(np.mean(np.where(err >= 0, tau * err, (tau - 1) * err)))


def coverage_fraction(obs: np.ndarray, pred: np.ndarray) -> float:
    return float(np.mean(obs <= pred))


def tail_hit_rate(obs: np.ndarray, q99_pred: np.ndarray) -> float:
    threshold = np.percentile(obs, 99)
    mask = obs >= threshold
    if mask.sum() == 0:
        return float("nan")
    return float(np.mean(obs[mask] <= q99_pred[mask]))
```

- [ ] **Step 2: 단위 함수 동작 검증**

스크립트 내 또는 Python 인터프리터에서:

```python
import numpy as np
obs = np.array([1.0, 2.0, 3.0, 4.0])
pred = np.array([1.5, 1.5, 3.5, 3.5])

# pinball q50: tau=0.5, err=[−0.5, 0.5, −0.5, 0.5], loss=[0.25, 0.25, 0.25, 0.25] → 0.25
assert abs(pinball_loss(obs, pred, 0.5) - 0.25) < 1e-9

# coverage q50: obs<=pred → [True, False, False, False] → 0.25
assert abs(coverage_fraction(obs, pred) - 0.25) < 1e-9
```

- [ ] **Step 3: 메인 계산 함수 작성**

```python
def compute_probabilistic_metrics(series_dir: Path, seeds: list[int]) -> pd.DataFrame:
    seed_results: list[pd.DataFrame] = []

    for seed in seeds:
        epoch = PRIMARY_EPOCHS[seed]["model2"]
        path = series_dir / f"seed{seed}" / f"epoch{epoch:03d}_required_series.csv"
        usecols = ["basin", "obs"] + QUANTILES
        df = pd.read_csv(path, usecols=usecols, dtype={"basin": str})
        df["basin"] = df["basin"].str.zfill(8)

        rows = []
        for basin, grp in df.groupby("basin", sort=False):
            obs = grp["obs"].to_numpy(dtype=float)
            rec: dict[str, object] = {"seed": seed, "basin": basin}
            for q in QUANTILES:
                pred = grp[q].to_numpy(dtype=float)
                tau = TAUS[q]
                rec[f"pinball_{q}"] = pinball_loss(obs, pred, tau)
                rec[f"coverage_{q}"] = coverage_fraction(obs, pred)
            rec["tail_hit_q99"] = tail_hit_rate(obs, grp["q99"].to_numpy(dtype=float))
            rows.append(rec)
        seed_results.append(pd.DataFrame(rows))

    all_seeds = pd.concat(seed_results, ignore_index=True)
    prob_cols = [f"pinball_{q}" for q in QUANTILES] + [f"coverage_{q}" for q in QUANTILES] + ["tail_hit_q99"]
    agg = all_seeds.drop(columns=["seed"]).groupby("basin")[prob_cols].median()
    assert len(agg) == 38, f"Expected 38 basins, got {len(agg)}"
    return agg
```

- [ ] **Step 4: main()에서 호출 및 확인**

```python
prob_metrics = compute_probabilistic_metrics(args.series_dir, args.seeds)
print(f"Prob metrics: {prob_metrics.shape}")
print(prob_metrics.describe().round(4))
```

- [ ] **Step 5: 실행 확인**

```bash
uv run scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py
```

Expected: pinball 값 양수, coverage_q50 ≈ 0.27, coverage_q99 ≈ 0.84 (문서 기준). NaN 없음.

- [ ] **Step 6: 커밋**

```bash
git add scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py
git commit -m "feat: add compute_probabilistic_metrics (pinball, coverage, tail hit)"
```

---

## Task 6: `build_master_table()` — 전체 38행 master table 병합

**Files:**
- Modify: `scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py`

- [ ] **Step 1: 함수 작성**

```python
def build_master_table(
    features: pd.DataFrame,
    det_metrics: pd.DataFrame,
    obs_features: pd.DataFrame,
    prob_metrics: pd.DataFrame,
) -> pd.DataFrame:
    table = features.join(obs_features, how="inner")
    table = table.join(det_metrics, how="inner")
    table = table.join(prob_metrics, how="inner")
    assert table.shape == (38, len(FEATURE_COLS) + len(METRIC_COLS_ALL)), (
        f"Unexpected shape {table.shape}"
    )
    return table
```

- [ ] **Step 2: main()에서 호출 및 확인**

```python
master = build_master_table(features, det_metrics, obs_features, prob_metrics)
print(f"Master table: {master.shape}")
print(f"NaN count:\n{master.isna().sum()[master.isna().sum() > 0]}")
```

- [ ] **Step 3: 실행 확인**

```bash
uv run scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py
```

Expected: `Master table: (38, 44)`. NaN은 가급적 0이어야 하지만, 일부 특성 누락 시 허용.

- [ ] **Step 4: 커밋**

```bash
git add scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py
git commit -m "feat: add build_master_table merging features and metrics"
```

---

## Task 7: `run_spearman_correlations()` — 480쌍 Spearman ρ + BH FDR

**Files:**
- Modify: `scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py`

- [ ] **Step 1: 함수 작성**

```python
def run_spearman_correlations(
    table: pd.DataFrame, fdr_alpha: float
) -> pd.DataFrame:
    rows = []
    for feat in FEATURE_COLS:
        if feat not in table.columns:
            continue
        x = table[feat].to_numpy(dtype=float)
        for metric in METRIC_COLS_ALL:
            if metric not in table.columns:
                continue
            y = table[metric].to_numpy(dtype=float)
            mask = np.isfinite(x) & np.isfinite(y)
            n = int(mask.sum())
            if n < 5:
                rows.append({"feature": feat, "metric": metric, "rho": np.nan, "pval": np.nan, "n": n})
                continue
            rho, pval = stats.spearmanr(x[mask], y[mask])
            rows.append({"feature": feat, "metric": metric, "rho": float(rho), "pval": float(pval), "n": n})

    corr_df = pd.DataFrame(rows)

    # BH FDR 보정
    valid = corr_df["pval"].notna()
    pvals = corr_df.loc[valid, "pval"].to_numpy()
    _, pvals_bh, _, _ = multipletests(pvals, alpha=fdr_alpha, method="fdr_bh")
    corr_df.loc[valid, "pval_bh"] = pvals_bh
    corr_df["significant"] = corr_df["pval_bh"] < fdr_alpha
    corr_df["abs_rho"] = corr_df["rho"].abs()
    corr_df = corr_df.sort_values("abs_rho", ascending=False).reset_index(drop=True)
    return corr_df
```

- [ ] **Step 2: main()에서 호출 및 확인**

```python
corr = run_spearman_correlations(master, args.fdr_alpha)
print(f"Correlation pairs: {len(corr)}")
print(f"Significant (BH p<{args.fdr_alpha}): {corr['significant'].sum()}")
print(corr.head(10)[["feature", "metric", "rho", "pval_bh", "significant"]])
```

- [ ] **Step 3: 실행 확인**

```bash
uv run scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py
```

Expected: 480쌍 생성 (20 features × 24 metrics). 유의미한 쌍 수 확인.

- [ ] **Step 4: 커밋**

```bash
git add scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py
git commit -m "feat: add run_spearman_correlations with BH FDR correction"
```

---

## Task 8: `write_tables()` — CSV 저장

**Files:**
- Modify: `scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py`

- [ ] **Step 1: 함수 작성**

```python
def write_tables(
    master: pd.DataFrame,
    corr: pd.DataFrame,
    obs_features: pd.DataFrame,
    output_dir: Path,
    top_n: int,
) -> dict[str, str]:
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    p_master = tables_dir / "basin_feature_metric_table.csv"
    p_corr = tables_dir / "spearman_correlations.csv"
    p_top = tables_dir / "top_correlations.csv"
    p_obs = tables_dir / "computed_obs_features.csv"

    master.to_csv(p_master)
    corr.to_csv(p_corr, index=False)
    corr.head(top_n).to_csv(p_top, index=False)
    obs_features.to_csv(p_obs)

    print(f"  Saved: {p_master.name}, {p_corr.name}, {p_top.name}, {p_obs.name}")
    return {
        "basin_feature_metric_table": str(p_master.relative_to(REPO_ROOT)),
        "spearman_correlations": str(p_corr.relative_to(REPO_ROOT)),
        "top_correlations": str(p_top.relative_to(REPO_ROOT)),
        "computed_obs_features": str(p_obs.relative_to(REPO_ROOT)),
    }
```

- [ ] **Step 2: main()에서 호출**

```python
table_paths = write_tables(master, corr, obs_features, args.output_dir, args.top_n)
```

- [ ] **Step 3: 실행 후 CSV 존재 확인**

```bash
uv run scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py
ls output/model_analysis/overall_analysis/main_comparison/drbc_attribute_metric_correlations/tables/
```

Expected: 4개 CSV 파일 존재.

- [ ] **Step 4: 커밋**

```bash
git add scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py
git commit -m "feat: add write_tables for master, correlation, top, obs CSVs"
```

---

## Task 9: `write_heatmaps()` — 4개 그룹 heatmap

**Files:**
- Modify: `scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py`

- [ ] **Step 1: 함수 작성**

```python
def _draw_heatmap(
    corr: pd.DataFrame,
    metric_cols: list[str],
    title: str,
    path: Path,
) -> None:
    feat_labels = [FEATURE_LABELS.get(f, f) for f in FEATURE_COLS if f in corr["feature"].values]
    metric_labels = [METRIC_LABELS.get(m, m) for m in metric_cols if m in corr["metric"].values]
    feats = [f for f in FEATURE_COLS if f in corr["feature"].values]
    metrics = [m for m in metric_cols if m in corr["metric"].values]

    rho_matrix = np.full((len(feats), len(metrics)), np.nan)
    sig_matrix = np.zeros((len(feats), len(metrics)), dtype=bool)
    for i, feat in enumerate(feats):
        for j, metric in enumerate(metrics):
            row = corr[(corr["feature"] == feat) & (corr["metric"] == metric)]
            if not row.empty:
                rho_matrix[i, j] = row.iloc[0]["rho"]
                sig_matrix[i, j] = bool(row.iloc[0]["significant"])

    fig, ax = plt.subplots(figsize=(max(6, len(metrics) * 0.9), max(6, len(feats) * 0.5)))
    im = ax.imshow(rho_matrix, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    plt.colorbar(im, ax=ax, label="Spearman ρ")

    # 유의미한 셀에 * 표시
    for i in range(len(feats)):
        for j in range(len(metrics)):
            if sig_matrix[i, j] and np.isfinite(rho_matrix[i, j]):
                ax.text(j, i, "*", ha="center", va="center", fontsize=10, color="white")

    ax.set_xticks(range(len(metrics)))
    ax.set_xticklabels(metric_labels, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(feats)))
    ax.set_yticklabels(feat_labels, fontsize=8)
    ax.set_title(f"{title}\nSpearman ρ (* = BH p < 0.05)", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path.name}")


def write_heatmaps(corr: pd.DataFrame, output_dir: Path) -> dict[str, str]:
    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for key, (metric_cols, title) in HEATMAP_GROUPS.items():
        out_path = figures_dir / f"heatmap_{key}.png"
        _draw_heatmap(corr, metric_cols, title, out_path)
        paths[f"heatmap_{key}"] = str(out_path.relative_to(REPO_ROOT))
    return paths
```

- [ ] **Step 2: main()에서 호출**

```python
heatmap_paths = write_heatmaps(corr, args.output_dir)
```

- [ ] **Step 3: 실행 후 그림 확인**

```bash
uv run scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py
ls output/model_analysis/overall_analysis/main_comparison/drbc_attribute_metric_correlations/figures/
```

Expected: `heatmap_model1.png`, `heatmap_model2_q50.png`, `heatmap_delta.png`, `heatmap_model2_prob.png` 존재.

- [ ] **Step 4: 커밋**

```bash
git add scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py
git commit -m "feat: add write_heatmaps for 4 metric groups"
```

---

## Task 10: `write_scatters()` — BH-significant 쌍 scatter plots

**Files:**
- Modify: `scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py`

- [ ] **Step 1: 함수 작성**

```python
def write_scatters(
    master: pd.DataFrame, corr: pd.DataFrame, output_dir: Path
) -> list[str]:
    scatter_dir = output_dir / "figures" / "scatter"
    scatter_dir.mkdir(parents=True, exist_ok=True)

    sig = corr[corr["significant"] & corr["rho"].notna()]
    saved = []
    for _, row in sig.iterrows():
        feat = row["feature"]
        metric = row["metric"]
        if feat not in master.columns or metric not in master.columns:
            continue
        x = master[feat]
        y = master[metric]
        valid = x.notna() & y.notna()

        fig, ax = plt.subplots(figsize=(5, 4))
        ax.scatter(x[valid], y[valid], s=40, alpha=0.7, color="#2563eb")
        for basin in master.index[valid]:
            ax.annotate(basin[-5:], (x[basin], y[basin]), fontsize=5, alpha=0.5)
        ax.set_xlabel(FEATURE_LABELS.get(feat, feat), fontsize=9)
        ax.set_ylabel(METRIC_LABELS.get(metric, metric), fontsize=9)
        ax.set_title(f"ρ={row['rho']:.2f}  BH p={row['pval_bh']:.3f}", fontsize=9)
        fig.tight_layout()
        safe_feat = feat.replace("/", "_")
        safe_metric = metric.replace("-", "_").replace("/", "_")
        out_path = scatter_dir / f"{safe_feat}_{safe_metric}.png"
        fig.savefig(out_path, dpi=120, bbox_inches="tight")
        plt.close(fig)
        saved.append(str(out_path.relative_to(REPO_ROOT)))

    print(f"  Scatter plots: {len(saved)}")
    return saved
```

- [ ] **Step 2: main()에서 호출**

```python
scatter_paths = write_scatters(master, corr, args.output_dir)
```

- [ ] **Step 3: 실행 후 파일 수 확인**

```bash
uv run scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py
ls output/model_analysis/overall_analysis/main_comparison/drbc_attribute_metric_correlations/figures/scatter/ | wc -l
```

Expected: BH-significant 쌍 수와 동일한 파일 수 출력.

- [ ] **Step 4: 커밋**

```bash
git add scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py
git commit -m "feat: add write_scatters for BH-significant pairs"
```

---

## Task 11: `write_report()` — 마크다운 리포트 자동 생성

**Files:**
- Modify: `scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py`

- [ ] **Step 1: 함수 작성**

```python
def write_report(
    corr: pd.DataFrame,
    heatmap_paths: dict[str, str],
    output_dir: Path,
    seeds: list[int],
    fdr_alpha: float,
    top_n: int,
) -> str:
    report_dir = output_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    out_path = report_dir / "drbc_attribute_metric_correlation_report.md"

    sig = corr[corr["significant"] & corr["rho"].notna()]
    top_sig = corr[corr["rho"].notna()].head(top_n)

    lines = [
        "# DRBC 유역 특성 × 모델 성능 Spearman 상관 분석 리포트",
        "",
        "## 1. 분석 개요",
        "",
        f"- **유역 수**: 38개 DRBC 유역",
        f"- **유역 특성**: {len(FEATURE_COLS)}개",
        f"- **성능 지표**: {len(METRIC_COLS_ALL)}개 (M1 5 + M2-q50 5 + delta 5 + 확률론적 9)",
        f"- **Seeds**: {seeds}",
        f"- **분석 쌍**: {len(corr)}쌍 (Spearman ρ, BH FDR α={fdr_alpha})",
        f"- **유의미한 쌍**: {len(sig)}쌍",
        "",
        "## 2. Top 상관 쌍 (|ρ| 기준)",
        "",
        "| Feature | Metric | ρ | BH p | Significant |",
        "|---------|--------|---|------|-------------|",
    ]
    for _, row in top_sig.iterrows():
        sig_mark = "✓" if row["significant"] else ""
        lines.append(
            f"| {FEATURE_LABELS.get(row['feature'], row['feature'])} "
            f"| {METRIC_LABELS.get(row['metric'], row['metric'])} "
            f"| {row['rho']:.3f} | {row['pval_bh']:.4f} | {sig_mark} |"
        )

    lines += [
        "",
        "## 3. Heatmaps",
        "",
    ]
    for key, title in [
        ("heatmap_model1", "Model 1"),
        ("heatmap_model2_q50", "Model 2 q50"),
        ("heatmap_delta", "Paired delta (M2−M1)"),
        ("heatmap_model2_prob", "Model 2 probabilistic"),
    ]:
        if key in heatmap_paths:
            rel = Path(heatmap_paths[key])
            # 리포트 위치에서 상대 경로 계산
            rel_from_report = Path("../figures") / rel.name
            lines.append(f"### {title}")
            lines.append("")
            lines.append(f"![{title}]({rel_from_report})")
            lines.append("")

    lines += [
        "## 4. 주의사항",
        "",
        "- n=38로 소표본이므로 Spearman ρ 신뢰구간이 넓다.",
        "- 3 seed 중앙값 집계 기준 분석 (seed 333 제외).",
        "- Pinball 값은 유량 단위(m³/s)에 비례하므로 상관 방향에 집중한다.",
        "- Q99-exceedance tail hit rate는 조건부 hit rate로 formal calibration이 아니다.",
    ]

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Saved: {out_path}")
    return str(out_path.relative_to(REPO_ROOT))
```

- [ ] **Step 2: main()에서 호출**

```python
report_path = write_report(corr, heatmap_paths, args.output_dir, args.seeds, args.fdr_alpha, args.top_n)
```

- [ ] **Step 3: 실행 후 리포트 내용 확인**

```bash
uv run scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py
head -40 output/model_analysis/overall_analysis/main_comparison/drbc_attribute_metric_correlations/report/drbc_attribute_metric_correlation_report.md
```

Expected: 헤더, 개요 표, Top 상관 쌍 표 출력.

- [ ] **Step 4: 커밋**

```bash
git add scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py
git commit -m "feat: add write_report for markdown correlation report"
```

---

## Task 12: `write_metadata()` + 최종 main() 정리 + end-to-end 검증

**Files:**
- Modify: `scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py`

- [ ] **Step 1: `write_metadata()` 작성**

```python
def write_metadata(
    args: argparse.Namespace,
    table_paths: dict[str, str],
    heatmap_paths: dict[str, str],
    scatter_paths: list[str],
    report_path: str,
    corr: pd.DataFrame,
) -> None:
    meta_dir = args.output_dir / "metadata"
    meta_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "analysis": "DRBC basin attribute × model metric Spearman correlations",
        "seeds": args.seeds,
        "n_basins": 38,
        "n_features": len(FEATURE_COLS),
        "n_metrics": len(METRIC_COLS_ALL),
        "n_pairs": len(corr),
        "n_significant": int(corr["significant"].sum()),
        "fdr_alpha": args.fdr_alpha,
        "top_n": args.top_n,
        "correlation_method": "Spearman rank, Benjamini-Hochberg FDR within full pair table",
        "primary_epochs": {str(k): v for k, v in PRIMARY_EPOCHS.items()},
        "inputs": {
            "drbc_attrs": str(args.drbc_attrs.relative_to(REPO_ROOT)),
            "basin_metrics": str(args.basin_metrics.relative_to(REPO_ROOT)),
            "basin_deltas": str(args.basin_deltas.relative_to(REPO_ROOT)),
            "series_dir": str(args.series_dir.relative_to(REPO_ROOT)),
        },
        "tables": table_paths,
        "figures": {**heatmap_paths, "scatter": scatter_paths},
        "report": report_path,
    }
    out = args.output_dir / "metadata" / "analysis_metadata.json"
    out.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"  Saved: {out.name}")
```

- [ ] **Step 2: main() 최종 정리 — 모든 함수 순서대로 호출**

```python
def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading basin features...")
    features = load_basin_features(args.drbc_attrs)

    print("Loading deterministic metrics...")
    det_metrics = load_deterministic_metrics(args.basin_metrics, args.basin_deltas, args.seeds)

    print("Computing obs-based features...")
    obs_features = compute_obs_features(args.series_dir)

    print("Computing probabilistic metrics...")
    prob_metrics = compute_probabilistic_metrics(args.series_dir, args.seeds)

    print("Building master table...")
    master = build_master_table(features, det_metrics, obs_features, prob_metrics)

    print("Running Spearman correlations...")
    corr = run_spearman_correlations(master, args.fdr_alpha)
    print(f"  {len(corr)} pairs, {corr['significant'].sum()} significant (BH p<{args.fdr_alpha})")

    print("Writing tables...")
    table_paths = write_tables(master, corr, obs_features, args.output_dir, args.top_n)

    print("Writing heatmaps...")
    heatmap_paths = write_heatmaps(corr, args.output_dir)

    print("Writing scatter plots...")
    scatter_paths = write_scatters(master, corr, args.output_dir)

    print("Writing report...")
    report_path = write_report(corr, heatmap_paths, args.output_dir, args.seeds, args.fdr_alpha, args.top_n)

    print("Writing metadata...")
    write_metadata(args, table_paths, heatmap_paths, scatter_paths, report_path, corr)

    print(f"\nDone. Output: {args.output_dir}")
```

- [ ] **Step 3: 전체 end-to-end 실행**

```bash
uv run scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py
```

Expected 마지막 출력:
```
Done. Output: .../drbc_attribute_metric_correlations
```

- [ ] **Step 4: 출력 파일 구조 최종 검증**

```bash
find output/model_analysis/overall_analysis/main_comparison/drbc_attribute_metric_correlations -type f | sort
```

Expected 파일 목록:
```
.../tables/basin_feature_metric_table.csv
.../tables/computed_obs_features.csv
.../tables/spearman_correlations.csv
.../tables/top_correlations.csv
.../figures/heatmap_delta.png
.../figures/heatmap_model1.png
.../figures/heatmap_model2_prob.png
.../figures/heatmap_model2_q50.png
.../figures/scatter/*.png  (BH-significant 수만큼)
.../metadata/analysis_metadata.json
.../report/drbc_attribute_metric_correlation_report.md
```

- [ ] **Step 5: spearman_correlations.csv top-5 확인**

```bash
python3 -c "
import pandas as pd
df = pd.read_csv('output/model_analysis/overall_analysis/main_comparison/drbc_attribute_metric_correlations/tables/spearman_correlations.csv')
print(df.head(5)[['feature','metric','rho','pval_bh','significant']])
"
```

Expected: |ρ| ≥ 0.3 수준의 쌍이 상위에 위치.

- [ ] **Step 6: 최종 커밋**

```bash
git add scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py
git commit -m "feat: complete drbc attribute-metric correlation analysis script"
```
