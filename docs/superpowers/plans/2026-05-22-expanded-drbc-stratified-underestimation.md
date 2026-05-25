# Expanded DRBC Stratified Underestimation Analysis — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `analyze_expanded_drbc_stratified_underestimation.py` 스크립트 작성 — 85-basin expanded DRBC test에서 관측 유량 기반 Q90+/Q95+/Q99+ stratum별 under_fraction + median_rel_bias 계산, 논문 Table 1용 CSV 두 개 생성.

**Architecture:** `required_series/seed{111,222,444}/primary_required_series.csv` 로드 → basin-specific obs 백분위수로 stratum 정의 → (stratum × pred_col × basin × seed) 지표 계산 → basin median → seed median 순서로 집계 → 두 CSV 출력.

**Tech Stack:** Python, pandas, numpy. `uv run` 실행. unittest (기존 패턴 유지).

---

## File Map

| 역할 | 경로 |
|------|------|
| 신규 스크립트 | `scripts/model/overall/analyze_expanded_drbc_stratified_underestimation.py` |
| 신규 테스트 | `tests/test_stratified_underestimation.py` |
| 출력 1 (논문 Table) | `output/model_analysis/expanded_drbc_test/tables/stratified_underestimation_summary.csv` |
| 출력 2 (seed별 robustness) | `output/model_analysis/expanded_drbc_test/tables/stratified_underestimation_by_seed.csv` |
| 입력 | `output/model_analysis/expanded_drbc_test/required_series/seed{111,222,444}/primary_required_series.csv` |

입력 CSV 컬럼: `seed, basin, model1_epoch, model2_epoch, datetime, obs, model1, model2_q50_result, q50, q90, q95, q99, ...`

---

## Task 1: 스크립트 skeleton + 상수 정의

**Files:**
- Create: `scripts/model/overall/analyze_expanded_drbc_stratified_underestimation.py`

- [ ] **Step 1: 파일 생성**

```python
#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
# ]
# ///
"""Compute obs-based stratum underestimation metrics for 85-basin expanded DRBC test.

Strata are defined by basin-specific percentiles of observed discharge (NOT model quantiles).
For each (stratum × prediction column), computes:
  under_fraction   — P(pred < obs)
  median_rel_bias  — median((pred - obs) / obs)

Outputs
-------
tables/stratified_underestimation_summary.csv   paper Table 1 (seed-median across 85 basins)
tables/stratified_underestimation_by_seed.csv   per-seed basin medians (robustness check)
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
REQUIRED_SERIES_DIR = (
    REPO_ROOT / "output/model_analysis/expanded_drbc_test/required_series"
)
OUTPUT_TABLES_DIR = (
    REPO_ROOT / "output/model_analysis/expanded_drbc_test/tables"
)

OFFICIAL_SEEDS: list[int] = [111, 222, 444]
PRED_COLS: list[str] = ["model1", "q50", "q90", "q95", "q99"]
STRATA: list[str] = ["all", "obs_q90_plus", "obs_q95_plus", "obs_q99_plus"]
STRATUM_QUANTILE: dict[str, float] = {
    "obs_q90_plus": 0.90,
    "obs_q95_plus": 0.95,
    "obs_q99_plus": 0.99,
}
```

- [ ] **Step 2: commit skeleton**

```bash
git add scripts/model/overall/analyze_expanded_drbc_stratified_underestimation.py
git commit -m "feat: add stratified underestimation script skeleton"
```

---

## Task 2: 테스트 파일 skeleton + load 함수 TDD

**Files:**
- Create: `tests/test_stratified_underestimation.py`
- Modify: `scripts/model/overall/analyze_expanded_drbc_stratified_underestimation.py`

- [ ] **Step 1: 테스트 파일 생성**

```python
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import scripts.model.overall.analyze_expanded_drbc_stratified_underestimation as M


def _make_required_series(
    basins: list[str],
    n_steps: int,
    seed: int = 111,
    obs_values: dict[str, list[float]] | None = None,
) -> pd.DataFrame:
    """Helper: synthetic required_series DataFrame."""
    rows = []
    for basin in basins:
        obs_seq = (obs_values or {}).get(basin, list(range(1, n_steps + 1)))
        for i, obs in enumerate(obs_seq[:n_steps]):
            rows.append({
                "seed": seed,
                "basin": basin,
                "datetime": pd.Timestamp("2014-01-01") + pd.Timedelta(hours=i),
                "obs": float(obs),
                "model1": float(obs) * 0.8,
                "q50": float(obs) * 0.85,
                "q90": float(obs) * 1.0,
                "q95": float(obs) * 1.1,
                "q99": float(obs) * 1.3,
            })
    return pd.DataFrame(rows)


class TestLoadRequiredSeries(unittest.TestCase):
    def test_loads_and_concatenates_seeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for seed in [111, 222]:
                seed_dir = root / f"seed{seed}"
                seed_dir.mkdir(parents=True)
                df = _make_required_series(["01414000"], 10, seed=seed)
                df.to_csv(seed_dir / "primary_required_series.csv", index=False)

            result = M.load_required_series([111, 222], base_dir=root)
            self.assertEqual(len(result), 20)
            self.assertEqual(set(result["seed"].unique()), {111, 222})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 테스트 실행 — FAIL 확인**

```bash
uv run python -m pytest tests/test_stratified_underestimation.py::TestLoadRequiredSeries -v
```
Expected: `AttributeError: module ... has no attribute 'load_required_series'`

- [ ] **Step 3: `load_required_series` 구현**

스크립트에 추가:

```python
def load_required_series(
    seeds: list[int] = OFFICIAL_SEEDS,
    base_dir: Path = REQUIRED_SERIES_DIR,
) -> pd.DataFrame:
    """Load and concatenate required_series CSVs for given seeds."""
    dfs: list[pd.DataFrame] = []
    for seed in seeds:
        path = base_dir / f"seed{seed}" / "primary_required_series.csv"
        df = pd.read_csv(path, parse_dates=["datetime"])
        dfs.append(df)
    combined = pd.concat(dfs, ignore_index=True)
    # keep only columns we need
    keep = ["seed", "basin", "datetime", "obs"] + PRED_COLS
    return combined[keep]
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run python -m pytest tests/test_stratified_underestimation.py::TestLoadRequiredSeries -v
```
Expected: `PASSED`

- [ ] **Step 5: commit**

```bash
git add scripts/model/overall/analyze_expanded_drbc_stratified_underestimation.py \
        tests/test_stratified_underestimation.py
git commit -m "feat: add load_required_series with tests"
```

---

## Task 3: basin threshold 계산 + stratum 할당 TDD

**Files:**
- Modify: `scripts/model/overall/analyze_expanded_drbc_stratified_underestimation.py`
- Modify: `tests/test_stratified_underestimation.py`

- [ ] **Step 1: threshold 테스트 추가**

`tests/test_stratified_underestimation.py`에 추가:

```python
class TestBasinThresholds(unittest.TestCase):
    def test_computes_per_basin_quantiles(self) -> None:
        # basin A: obs = 1..100, basin B: obs = 10..1000 (step 10)
        df_a = _make_required_series(["basinA"], 100,
                                     obs_values={"basinA": list(range(1, 101))})
        df_b = _make_required_series(["basinB"], 100,
                                     obs_values={"basinB": list(range(10, 1010, 10))})
        df = pd.concat([df_a, df_b], ignore_index=True)

        thr = M.compute_basin_thresholds(df)
        self.assertIn("basinA", thr["basin"].values)
        self.assertIn("basinB", thr["basin"].values)

        thr_a = thr[thr["basin"] == "basinA"].iloc[0]
        thr_b = thr[thr["basin"] == "basinB"].iloc[0]
        # Q90 of 1..100 ≈ 90.1 → check > 89
        self.assertGreater(thr_a["q90_thr"], 89)
        # Q99 of 10..1000 (step 10) ≈ 990.1 → check > 980
        self.assertGreater(thr_b["q99_thr"], 980)

    def test_excludes_zero_and_nan_obs(self) -> None:
        obs_seq = [0.0, float("nan")] + list(range(1, 99))
        df = _make_required_series(["basinC"], 100,
                                   obs_values={"basinC": obs_seq})
        thr = M.compute_basin_thresholds(df)
        # should not raise; thresholds computed from valid 98 values
        self.assertEqual(len(thr), 1)
```

- [ ] **Step 2: FAIL 확인**

```bash
uv run python -m pytest tests/test_stratified_underestimation.py::TestBasinThresholds -v
```
Expected: `AttributeError: ... 'compute_basin_thresholds'`

- [ ] **Step 3: threshold 함수 구현**

스크립트에 추가:

```python
def compute_basin_thresholds(df: pd.DataFrame) -> pd.DataFrame:
    """Compute Q90/Q95/Q99 of observed discharge per basin from valid obs rows."""
    valid = df[df["obs"].notna() & (df["obs"] > 0)]
    records = []
    for basin, grp in valid.groupby("basin"):
        obs = grp["obs"]
        records.append({
            "basin": basin,
            "q90_thr": float(obs.quantile(0.90)),
            "q95_thr": float(obs.quantile(0.95)),
            "q99_thr": float(obs.quantile(0.99)),
        })
    return pd.DataFrame(records)
```

- [ ] **Step 4: stratum 할당 테스트 추가**

```python
class TestAssignStrata(unittest.TestCase):
    def test_all_stratum_excludes_nan_and_zero(self) -> None:
        obs_seq = [0.0, float("nan"), 5.0, 10.0]
        df = _make_required_series(["b1"], 4, obs_values={"b1": obs_seq})
        thr = pd.DataFrame([{"basin": "b1", "q90_thr": 8.0, "q95_thr": 9.0, "q99_thr": 9.5}])
        result = M.assign_strata(df, thr)
        all_rows = result[result["stratum"] == "all"]
        self.assertEqual(len(all_rows), 2)  # only obs=5.0 and obs=10.0

    def test_q99_plus_stratum_filters_correctly(self) -> None:
        obs_seq = [5.0, 10.0, 20.0]
        df = _make_required_series(["b2"], 3, obs_values={"b2": obs_seq})
        thr = pd.DataFrame([{"basin": "b2", "q90_thr": 8.0, "q95_thr": 9.0, "q99_thr": 15.0}])
        result = M.assign_strata(df, thr)
        q99_rows = result[result["stratum"] == "obs_q99_plus"]
        self.assertEqual(len(q99_rows), 1)
        self.assertAlmostEqual(q99_rows.iloc[0]["obs"], 20.0)
```

- [ ] **Step 5: FAIL 확인**

```bash
uv run python -m pytest tests/test_stratified_underestimation.py::TestAssignStrata -v
```

- [ ] **Step 6: assign_strata 구현**

스크립트에 추가:

```python
def assign_strata(df: pd.DataFrame, thresholds: pd.DataFrame) -> pd.DataFrame:
    """Return long-form DataFrame with a 'stratum' column.

    Filters to obs > 0 and obs not NaN. Each valid row appears once per stratum
    it belongs to (nested: q99_plus ⊂ q95_plus ⊂ q90_plus ⊂ all).
    """
    valid = df.merge(thresholds, on="basin", how="left")
    valid = valid[valid["obs"].notna() & (valid["obs"] > 0)].copy()

    parts: list[pd.DataFrame] = []
    for stratum in STRATA:
        if stratum == "all":
            mask = pd.Series(True, index=valid.index)
        else:
            thr_col = stratum.replace("obs_", "").replace("_plus", "_thr")
            mask = valid["obs"] > valid[thr_col]
        chunk = valid[mask].copy()
        chunk["stratum"] = stratum
        parts.append(chunk)

    return pd.concat(parts, ignore_index=True)
```

- [ ] **Step 7: 테스트 통과 확인**

```bash
uv run python -m pytest tests/test_stratified_underestimation.py -v
```
Expected: 모든 테스트 PASSED

- [ ] **Step 8: commit**

```bash
git add scripts/model/overall/analyze_expanded_drbc_stratified_underestimation.py \
        tests/test_stratified_underestimation.py
git commit -m "feat: add basin threshold computation and stratum assignment"
```

---

## Task 4: basin-level 지표 계산 TDD

**Files:**
- Modify: `scripts/model/overall/analyze_expanded_drbc_stratified_underestimation.py`
- Modify: `tests/test_stratified_underestimation.py`

- [ ] **Step 1: 테스트 추가**

```python
class TestBasinMetrics(unittest.TestCase):
    def test_under_fraction_and_median_rel_bias(self) -> None:
        # obs = [10, 20, 30, 40, 50]
        # model1 = [8, 25, 25, 45, 45]  → under at 10,30 → under_frac=0.4
        # rel_bias = [-0.2, 0.25, -0.167, 0.125, -0.1] → median = -0.1
        obs_seq = [10.0, 20.0, 30.0, 40.0, 50.0]
        df = _make_required_series(["bX"], 5, obs_values={"bX": obs_seq})
        # override model1 predictions
        df["model1"] = [8.0, 25.0, 25.0, 45.0, 45.0]
        df["q50"] = df["model1"]
        df["q90"] = df["model1"]
        df["q95"] = df["model1"]
        df["q99"] = df["model1"]

        thr = pd.DataFrame([{"basin": "bX", "q90_thr": 100.0, "q95_thr": 100.0, "q99_thr": 100.0}])
        long_df = M.assign_strata(df, thr)
        metrics = M.compute_basin_metrics(long_df)

        all_m1 = metrics[(metrics["stratum"] == "all") & (metrics["basin"] == "bX")]
        self.assertEqual(len(all_m1), 1)
        row = all_m1.iloc[0]
        self.assertAlmostEqual(row["model1_under_frac"], 0.4, places=5)
        self.assertAlmostEqual(row["model1_med_rel_bias"], -0.1, places=5)

    def test_n_timesteps_recorded(self) -> None:
        df = _make_required_series(["bY"], 20)
        thr = pd.DataFrame([{"basin": "bY", "q90_thr": 1000.0, "q95_thr": 1000.0, "q99_thr": 1000.0}])
        long_df = M.assign_strata(df, thr)
        metrics = M.compute_basin_metrics(long_df)
        all_row = metrics[(metrics["stratum"] == "all") & (metrics["basin"] == "bY")].iloc[0]
        self.assertEqual(all_row["n_timesteps"], 20)
```

- [ ] **Step 2: FAIL 확인**

```bash
uv run python -m pytest tests/test_stratified_underestimation.py::TestBasinMetrics -v
```

- [ ] **Step 3: compute_basin_metrics 구현**

스크립트에 추가:

```python
def compute_basin_metrics(long_df: pd.DataFrame) -> pd.DataFrame:
    """Per (stratum × basin × seed) → under_fraction and median_rel_bias for each pred_col.

    Input: long-form DataFrame from assign_strata (has 'stratum' column).
    """
    records: list[dict] = []
    for (stratum, basin, seed), grp in long_df.groupby(["stratum", "basin", "seed"]):
        obs = grp["obs"].values
        row: dict = {
            "stratum": stratum,
            "basin": basin,
            "seed": seed,
            "n_timesteps": len(grp),
        }
        for col in PRED_COLS:
            pred = grp[col].values
            row[f"{col}_under_frac"] = float((pred < obs).mean())
            rel_err = (pred - obs) / obs
            row[f"{col}_med_rel_bias"] = float(np.median(rel_err))
        records.append(row)
    return pd.DataFrame(records)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run python -m pytest tests/test_stratified_underestimation.py -v
```
Expected: 모든 PASSED

- [ ] **Step 5: commit**

```bash
git add scripts/model/overall/analyze_expanded_drbc_stratified_underestimation.py \
        tests/test_stratified_underestimation.py
git commit -m "feat: add compute_basin_metrics with under_fraction and median_rel_bias"
```

---

## Task 5: 집계 함수 (seed summary + final summary) TDD

**Files:**
- Modify: `scripts/model/overall/analyze_expanded_drbc_stratified_underestimation.py`
- Modify: `tests/test_stratified_underestimation.py`

- [ ] **Step 1: 집계 테스트 추가**

```python
class TestAggregation(unittest.TestCase):
    def _make_basin_metrics(self) -> pd.DataFrame:
        metric_cols = [f"{c}_{m}" for c in M.PRED_COLS for m in ["under_frac", "med_rel_bias"]]
        rows = []
        for seed in [111, 222]:
            for basin in ["b1", "b2", "b3"]:
                for stratum in ["all", "obs_q90_plus"]:
                    row = {"stratum": stratum, "basin": basin, "seed": seed, "n_timesteps": 100}
                    for col in metric_cols:
                        row[col] = 0.5 if "under_frac" in col else -0.2
                    rows.append(row)
        return pd.DataFrame(rows)

    def test_seed_summary_shape(self) -> None:
        bm = self._make_basin_metrics()
        seed_sum = M.aggregate_to_seed_summary(bm)
        # 2 seeds × 2 strata = 4 rows
        self.assertEqual(len(seed_sum), 4)
        self.assertIn("n_basins", seed_sum.columns)
        self.assertIn("model1_under_frac", seed_sum.columns)

    def test_final_summary_shape(self) -> None:
        bm = self._make_basin_metrics()
        seed_sum = M.aggregate_to_seed_summary(bm)
        final = M.aggregate_to_final_summary(seed_sum)
        # 2 strata = 2 rows
        self.assertEqual(len(final), 2)
        self.assertIn("stratum", final.columns)
        self.assertIn("q99_under_frac", final.columns)

    def test_aggregation_computes_median(self) -> None:
        # all values are 0.5 → median should be 0.5
        bm = self._make_basin_metrics()
        seed_sum = M.aggregate_to_seed_summary(bm)
        final = M.aggregate_to_final_summary(seed_sum)
        all_row = final[final["stratum"] == "all"].iloc[0]
        self.assertAlmostEqual(all_row["model1_under_frac"], 0.5, places=5)
```

- [ ] **Step 2: FAIL 확인**

```bash
uv run python -m pytest tests/test_stratified_underestimation.py::TestAggregation -v
```

- [ ] **Step 3: 집계 함수 구현**

스크립트에 추가:

```python
_METRIC_COLS = [f"{c}_{m}" for c in PRED_COLS for m in ["under_frac", "med_rel_bias"]]


def aggregate_to_seed_summary(basin_metrics: pd.DataFrame) -> pd.DataFrame:
    """Basin median → per (seed × stratum) summary."""
    records: list[dict] = []
    for (seed, stratum), grp in basin_metrics.groupby(["seed", "stratum"]):
        row: dict = {
            "seed": seed,
            "stratum": stratum,
            "n_basins": len(grp),
            "n_timesteps_median": float(grp["n_timesteps"].median()),
        }
        for col in _METRIC_COLS:
            row[col] = float(grp[col].median())
        records.append(row)
    return pd.DataFrame(records)


def aggregate_to_final_summary(seed_summary: pd.DataFrame) -> pd.DataFrame:
    """Seed median → final (stratum) summary."""
    records: list[dict] = []
    for stratum, grp in seed_summary.groupby("stratum"):
        row: dict = {
            "stratum": stratum,
            "n_basins": float(grp["n_basins"].median()),
            "n_timesteps_median": float(grp["n_timesteps_median"].median()),
        }
        for col in _METRIC_COLS:
            row[col] = float(grp[col].median())
        records.append(row)
    # sort by stratum order
    order = {s: i for i, s in enumerate(STRATA)}
    result = pd.DataFrame(records)
    result["_order"] = result["stratum"].map(order)
    return result.sort_values("_order").drop(columns=["_order"]).reset_index(drop=True)
```

- [ ] **Step 4: 전체 테스트 통과 확인**

```bash
uv run python -m pytest tests/test_stratified_underestimation.py -v
```
Expected: 모든 PASSED

- [ ] **Step 5: commit**

```bash
git add scripts/model/overall/analyze_expanded_drbc_stratified_underestimation.py \
        tests/test_stratified_underestimation.py
git commit -m "feat: add seed-level and final aggregation functions"
```

---

## Task 6: main() + CLI 진입점 + 출력 함수

**Files:**
- Modify: `scripts/model/overall/analyze_expanded_drbc_stratified_underestimation.py`

- [ ] **Step 1: write_outputs + main 구현**

스크립트에 추가:

```python
def write_outputs(
    seed_summary: pd.DataFrame,
    final_summary: pd.DataFrame,
    output_dir: Path = OUTPUT_TABLES_DIR,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    by_seed_path = output_dir / "stratified_underestimation_by_seed.csv"
    summary_path = output_dir / "stratified_underestimation_summary.csv"
    seed_summary.to_csv(by_seed_path, index=False)
    final_summary.to_csv(summary_path, index=False)
    print(f"Wrote {by_seed_path}")
    print(f"Wrote {summary_path}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seeds",
        nargs="+",
        type=int,
        default=OFFICIAL_SEEDS,
        help="Seeds to process (default: 111 222 444)",
    )
    parser.add_argument(
        "--required-series-dir",
        type=Path,
        default=REQUIRED_SERIES_DIR,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_TABLES_DIR,
    )
    args = parser.parse_args(argv)

    print(f"Loading required_series for seeds {args.seeds} ...")
    df = load_required_series(args.seeds, base_dir=args.required_series_dir)
    print(f"  Loaded {len(df):,} rows, {df['basin'].nunique()} basins")

    print("Computing basin-specific Q90/Q95/Q99 thresholds ...")
    thresholds = compute_basin_thresholds(df)

    print("Assigning strata ...")
    long_df = assign_strata(df, thresholds)

    print("Computing per-basin metrics ...")
    basin_metrics = compute_basin_metrics(long_df)

    print("Aggregating ...")
    seed_summary = aggregate_to_seed_summary(basin_metrics)
    final_summary = aggregate_to_final_summary(seed_summary)

    write_outputs(seed_summary, final_summary, output_dir=args.output_dir)
    print("Done.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 전체 테스트 재실행 확인**

```bash
uv run python -m pytest tests/test_stratified_underestimation.py -v
```
Expected: 모든 PASSED

- [ ] **Step 3: commit**

```bash
git add scripts/model/overall/analyze_expanded_drbc_stratified_underestimation.py
git commit -m "feat: add main() entry point and write_outputs"
```

---

## Task 7: 실제 데이터로 smoke test 실행 + 출력 검증

**Files:**
- Read: `output/model_analysis/expanded_drbc_test/tables/stratified_underestimation_summary.csv`

- [ ] **Step 1: 스크립트 실행**

```bash
uv run scripts/model/overall/analyze_expanded_drbc_stratified_underestimation.py
```

Expected output:
```
Loading required_series for seeds [111, 222, 444] ...
  Loaded X rows, 85 basins
Computing basin-specific Q90/Q95/Q99 thresholds ...
Assigning strata ...
Computing per-basin metrics ...
Aggregating ...
Wrote output/model_analysis/expanded_drbc_test/tables/stratified_underestimation_by_seed.csv
Wrote output/model_analysis/expanded_drbc_test/tables/stratified_underestimation_summary.csv
Done.
```

- [ ] **Step 2: 출력 내용 sanity check**

```bash
uv run python3 -c "
import pandas as pd
df = pd.read_csv('output/model_analysis/expanded_drbc_test/tables/stratified_underestimation_summary.csv')
print(df[['stratum','model1_under_frac','q50_under_frac','q90_under_frac','q95_under_frac','q99_under_frac']].to_string())
"
```

기대 패턴 확인:
- `all` stratum: model1 under_frac ≈ 0.5~0.7 (전 구간 포함)
- `obs_q90_plus`: model1 under_frac > `all` (고유량에서 더 자주 과소추정)
- `obs_q99_plus`: q99 under_frac이 model1보다 낮아야 연구 claim 성립
- 각 stratum에서 under_frac: q99 < q95 < q90 순서

- [ ] **Step 3: seed별 robustness 확인**

```bash
uv run python3 -c "
import pandas as pd
df = pd.read_csv('output/model_analysis/expanded_drbc_test/tables/stratified_underestimation_by_seed.csv')
print(df[['seed','stratum','model1_under_frac','q99_under_frac']].to_string())
"
```

3개 seed에서 같은 방향(q99 under_frac < model1 under_frac at obs_q99_plus) 확인.

- [ ] **Step 4: final commit**

```bash
git add output/model_analysis/expanded_drbc_test/tables/stratified_underestimation_summary.csv \
        output/model_analysis/expanded_drbc_test/tables/stratified_underestimation_by_seed.csv
git commit -m "feat: generate stratified underestimation tables for 85-basin expanded DRBC test"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] `all / obs_q90_plus / obs_q95_plus / obs_q99_plus` 4개 stratum
- [x] `under_fraction` + `median_rel_bias` per (stratum × pred_col)
- [x] model1 / q50 / q90 / q95 / q99 전부 평가
- [x] basin-specific obs 백분위수 (모델 output quantile 아님)
- [x] seed 333 제외 (OFFICIAL_SEEDS = [111, 222, 444])
- [x] obs=0 / NaN 제외
- [x] basin median → seed median 집계 순서
- [x] 출력 두 CSV: summary + by_seed
- [x] test period obs만 사용 (required_series는 2014-2016 기간)

**Type consistency:**
- `load_required_series(seeds, base_dir)` → Task 2 정의, Task 6 main()에서 동일하게 호출
- `assign_strata(df, thresholds)` → Task 3 정의, Task 4/5에서 동일 시그니처
- `_METRIC_COLS` → Task 5에서 정의, aggregate 함수 두 곳에서 공유
