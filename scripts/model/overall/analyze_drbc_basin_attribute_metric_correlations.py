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
