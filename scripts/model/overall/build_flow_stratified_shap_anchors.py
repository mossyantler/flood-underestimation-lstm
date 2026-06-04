#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
# ]
# ///
"""Build test-split flow-regime anchor samples for direct LSTM SHAP.

각 유역의 공식 test split 관측 유량 분포만 사용해 네 구간을 겹치지
않게 정의한다. 현재 canonical test split은 2014-01-01부터
2016-12-31까지다.

- 저유량: 0-33분위
- 중유량: 33-67분위
- 고유량: 67-99분위
- 극유량: 99분위 이상

관측 유량은 구간을 나누는 기준으로만 쓰며, LSTM SHAP 입력으로는
넣지 않는다.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REQUIRED_SERIES = (
    REPO_ROOT / "output/model_analysis/primary/metrics/data/required_series/seed111/required_series.csv"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/shap/test_split"
DEFAULT_SEEDS = [111, 222, 444]
STRATUM_ORDER = ["low", "mid", "high", "extreme_q99"]
STRATUM_KO = {
    "low": "저유량",
    "mid": "중유량",
    "high": "고유량",
    "extreme_q99": "극유량(Q99 이상)",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build flow-stratified SHAP anchor samples.")
    parser.add_argument("--required-series", type=Path, default=DEFAULT_REQUIRED_SERIES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--analysis-start-date", default="2014-01-01")
    parser.add_argument("--analysis-end-date", default="2016-12-31 23:59:59")
    parser.add_argument("--samples-per-stratum", type=int, default=60)
    parser.add_argument("--seeds", type=int, nargs="+", default=DEFAULT_SEEDS)
    parser.add_argument("--random-state", type=int, default=20260530)
    return parser.parse_args()


def assign_strata(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    thresholds = (
        frame.groupby("basin")["obs"]
        .quantile([1 / 3, 2 / 3, 0.99])
        .unstack()
        .rename(columns={1 / 3: "obs_q33", 2 / 3: "obs_q67", 0.99: "obs_q99"})
        .reset_index()
    )
    merged = frame.merge(thresholds, on="basin", how="left")
    merged["flow_stratum"] = np.select(
        [
            merged["obs"].ge(merged["obs_q99"]),
            merged["obs"].le(merged["obs_q33"]),
            merged["obs"].le(merged["obs_q67"]),
        ],
        ["extreme_q99", "low", "mid"],
        default="high",
    )
    merged["flow_stratum_ko"] = merged["flow_stratum"].map(STRATUM_KO)
    return merged, thresholds


def sample_balanced_by_basin(frame: pd.DataFrame, *, samples_per_stratum: int, random_state: int) -> pd.DataFrame:
    rng = np.random.default_rng(random_state)
    sampled_parts: list[pd.DataFrame] = []
    for stratum in STRATUM_ORDER:
        subset = frame[frame["flow_stratum"].eq(stratum)].copy()
        per_basin_rows = []
        for basin, basin_df in subset.groupby("basin", sort=True):
            choice = basin_df.sample(n=1, random_state=int(rng.integers(0, 2**31 - 1)))
            per_basin_rows.append(choice)
        candidates = pd.concat(per_basin_rows, ignore_index=True)
        n = min(samples_per_stratum, len(candidates))
        sampled = candidates.sample(n=n, random_state=int(rng.integers(0, 2**31 - 1))).copy()
        sampled["stratum_sample_rank"] = np.arange(1, len(sampled) + 1)
        sampled_parts.append(sampled)
    return pd.concat(sampled_parts, ignore_index=True)


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    tables_dir = output_dir / "tables"
    metadata_dir = output_dir / "metadata"
    tables_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    usecols = ["basin", "datetime", "obs"]
    frame = pd.read_csv(args.required_series, usecols=usecols)
    frame["basin"] = frame["basin"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(8)
    frame["datetime"] = pd.to_datetime(frame["datetime"], errors="coerce")
    frame["obs"] = pd.to_numeric(frame["obs"], errors="coerce")
    frame = frame.dropna(subset=["datetime", "obs"])
    frame = frame[
        frame["datetime"].between(pd.Timestamp(args.analysis_start_date), pd.Timestamp(args.analysis_end_date))
    ].copy()
    frame = frame[frame["obs"].ge(0)].copy()

    stratified, thresholds = assign_strata(frame)
    sampled = sample_balanced_by_basin(
        stratified,
        samples_per_stratum=args.samples_per_stratum,
        random_state=args.random_state,
    )
    sampled = sampled.sort_values(["flow_stratum", "basin", "datetime"]).reset_index(drop=True)
    sampled["event_end"] = sampled["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
    sampled["event_id_base"] = [
        f"flow_{row.flow_stratum}_{idx + 1:04d}" for idx, row in sampled.reset_index(drop=True).iterrows()
    ]

    replicated = []
    for seed in args.seeds:
        part = sampled.copy()
        part["seed"] = seed
        part["event_id"] = part["event_id_base"]
        replicated.append(part)
    anchors = pd.concat(replicated, ignore_index=True)
    anchors = anchors[
        [
            "seed",
            "basin",
            "event_id",
            "event_end",
            "obs",
            "obs_q33",
            "obs_q67",
            "obs_q99",
            "flow_stratum",
            "flow_stratum_ko",
            "stratum_sample_rank",
        ]
    ]

    anchor_path = tables_dir / "flow_stratified_shap_anchor_samples_test_split.csv"
    thresholds_path = tables_dir / "flow_stratified_obs_thresholds_by_basin_test_split.csv"
    summary_path = tables_dir / "flow_stratified_shap_anchor_summary_test_split.csv"
    anchors.to_csv(anchor_path, index=False)
    thresholds.to_csv(thresholds_path, index=False)
    summary = (
        anchors.groupby(["seed", "flow_stratum", "flow_stratum_ko"], as_index=False)
        .agg(n_rows=("event_id", "count"), n_basins=("basin", "nunique"), obs_min=("obs", "min"), obs_max=("obs", "max"))
        .sort_values(["seed", "flow_stratum"])
    )
    summary.to_csv(summary_path, index=False)

    print("Wrote flow-stratified SHAP anchor samples:")
    for path in [anchor_path, thresholds_path, summary_path]:
        print(f"  - {path.relative_to(REPO_ROOT)}")
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
