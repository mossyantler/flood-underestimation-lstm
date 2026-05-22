#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
# ]
# ///
"""Compute obs-based stratum underestimation metrics for 85-basin expanded DRBC test.

Strata are defined by basin-specific percentiles of observed discharge (NOT model quantiles).
For each (stratum x prediction column), computes:
  under_fraction   -- P(pred < obs)
  median_rel_bias  -- median((pred - obs) / obs)

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
    REPO_ROOT / "output/model_analysis/expanded/expanded_drbc_test/required_series"
)
OUTPUT_TABLES_DIR = (
    REPO_ROOT / "output/model_analysis/expanded/expanded_drbc_test/tables"
)

OFFICIAL_SEEDS: list[int] = [111, 222, 444]
PRED_COLS: list[str] = ["model1", "q50", "q90", "q95", "q99"]
STRATA: list[str] = ["all", "obs_q90_plus", "obs_q95_plus", "obs_q99_plus"]
STRATUM_QUANTILE: dict[str, float] = {
    "obs_q90_plus": 0.90,
    "obs_q95_plus": 0.95,
    "obs_q99_plus": 0.99,
}
