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


def load_basin_features(path: Path, basin_ids: set[str] | None = None) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"gauge_id": str})
    df["gauge_id"] = df["gauge_id"].str.zfill(8)
    if basin_ids is not None:
        df = df[df["gauge_id"].isin(basin_ids)].reset_index(drop=True)

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

    agg = merged.drop(columns=["seed"]).groupby("basin").median()
    assert len(agg) == 38, f"Expected 38 basins after aggregation, got {len(agg)}"
    return agg


def compute_obs_features(series_dir: Path) -> pd.DataFrame:
    seed = 111
    epoch = PRIMARY_EPOCHS[seed]["model2"]  # epoch 5
    path = series_dir / f"seed{seed}" / f"epoch{epoch:03d}_required_series.csv"
    df = pd.read_csv(path, usecols=["basin", "obs"], dtype={"basin": str})
    df["basin"] = df["basin"].str.zfill(8)

    rows = []
    for basin, grp in df.groupby("basin", sort=False):
        obs = grp["obs"].dropna().to_numpy(dtype=float)
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
            grp = grp.dropna(subset=["obs"])
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

    print("Loading basin features...")
    _raw_metrics = pd.read_csv(args.basin_metrics, dtype={"basin": str})
    _raw_metrics["basin"] = _raw_metrics["basin"].str.zfill(8)
    _model_basin_ids: set[str] = set(_raw_metrics[_raw_metrics["split"] == "test"]["basin"].unique())
    features = load_basin_features(args.drbc_attrs, basin_ids=_model_basin_ids)
    print(f"Features: {features.shape}  columns={list(features.columns)}")

    print("Loading deterministic metrics...")
    det_metrics = load_deterministic_metrics(args.basin_metrics, args.basin_deltas, args.seeds)
    print(f"Det metrics: {det_metrics.shape}  columns={list(det_metrics.columns)}")

    print("Computing obs-based features...")
    obs_features = compute_obs_features(args.series_dir)
    print(f"Obs features: {obs_features.shape}")
    print(obs_features[["obs_cv", "obs_fdc_slope", "obs_q99", "obs_mean_flow"]].describe().round(3))

    print("Computing probabilistic metrics...")
    prob_metrics = compute_probabilistic_metrics(args.series_dir, args.seeds)
    print(f"Prob metrics: {prob_metrics.shape}")
    print(prob_metrics.describe().round(4))


if __name__ == "__main__":
    main()
