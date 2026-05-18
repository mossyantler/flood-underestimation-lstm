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

SERIES_ROOT  = Path("output/model_analysis/quantile_analysis/required_series")
ATTR_FILE    = Path("output/basin/drbc/analysis/basin_attributes/tables/drbc_selected_basin_analysis_table.csv")
METRICS_FILE = Path("output/model_analysis/overall_analysis/epoch_sensitivity/tables/basin_metrics.csv")
OUTPUT_ROOT  = Path("output/model_analysis/overall_analysis/main_comparison/drbc_basin_report_cards")

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


if __name__ == "__main__":
    basin_ids = _get_basin_ids()
    log.info("basins: %d", len(basin_ids))
