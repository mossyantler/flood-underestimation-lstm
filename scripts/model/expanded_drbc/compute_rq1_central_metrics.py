#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "matplotlib>=3.9",
# ]
# ///
"""RQ-1 — q50 central performance metrics on expanded DRBC observed test (85 basins).

Inputs
------
- output/model_analysis/expanded_drbc_test/required_series/seed{111,222,444}/primary_required_series.csv
- output/model_analysis/expanded_drbc_test/raw_metrics/model{1,2}_seed{111,222,444}_epoch*_metrics.csv
  (NSE/KGE cross-check only; bias/MAE/RMSE/FHV are computed fresh here)

Outputs
-------
- tables/rq1_central_metrics_per_basin_seed.csv     (wide form: 85 × 3 × 2 = 510 rows)
- tables/rq1_central_metrics_seed_median.csv        (long form: 85 × 6 = 510 rows)
- tables/rq1_central_metrics_pooled_summary.csv
- figures/rq1_central_metric_boxplots.png
- figures/rq1_paired_delta_scatter.png

Metrics: NSE, KGE, bias = mean(pred − obs), MAE = mean(|pred − obs|),
RMSE = sqrt(mean((pred − obs)^2)),
FHV = sum(sim_top2% − obs_top2%) / sum(obs_top2%) × 100  (Yilmaz 2008).
NaN-obs rows dropped per :func:`scripts._lib.expanded_drbc.filter_valid_rows`.

Aggregation order (canonical from C0):
per-basin per-seed compute → median across seeds within basin → cross-basin summary.
Paired delta computed at per-seed level (`metric(M2_q50, seed) − metric(M1, seed)`),
then median-aggregated across seeds within basin.

Expected runtime on MacBook M-series: ~5 min, peak ~1.5 GB RAM (one seed at a time).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

LIB_ROOT = Path(__file__).resolve().parents[2] / "_lib"
if str(LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(LIB_ROOT))

from expanded_drbc import (  # noqa: E402  (sys.path setup must precede import)
    SEEDS,
    filter_valid_rows,
    normalize_basin_id,
    paired_delta_per_seed,
    per_basin_seed_then_median,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT_DIR = REPO_ROOT / "output/model_analysis/expanded_drbc_test/required_series"
DEFAULT_RAW_METRICS_DIR = REPO_ROOT / "output/model_analysis/expanded_drbc_test/raw_metrics"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/expanded_drbc_test"

REQUIRED_COLS = ("seed", "basin", "obs", "model1", "q50")
METRIC_ORDER = ("nse", "kge", "bias", "mae", "rmse", "fhv")
_FHV_H = 0.02  # top 2% of FDC (Yilmaz 2008)


def _compute_fhv(obs: np.ndarray, pred: np.ndarray) -> float:
    """FHV: top-2% FDC volume bias (Yilmaz 2008). obs/sim sorted independently."""
    obs_sorted = np.sort(obs)[::-1]
    pred_sorted = np.sort(pred)[::-1]
    n = max(1, round(_FHV_H * len(obs_sorted)))
    obs_top = obs_sorted[:n]
    pred_top = pred_sorted[:n]
    denom = obs_top.sum()
    if denom == 0:
        return float("nan")
    return float((pred_top.sum() - denom) / denom * 100)


def compute_metrics(obs: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    """Return NSE / KGE / bias / MAE / RMSE / FHV for a single (obs, pred) array pair.

    NaN-obs entries are assumed already filtered. Pred-NaN entries are
    masked out for this metric pair only.
    """
    mask = ~(np.isnan(obs) | np.isnan(pred))
    obs = obs[mask]
    pred = pred[mask]
    if obs.size == 0:
        return {m: float("nan") for m in METRIC_ORDER}
    residual = pred - obs
    obs_mean = obs.mean()
    denom = ((obs - obs_mean) ** 2).sum()
    nse = 1.0 - ((residual ** 2).sum() / denom) if denom > 0 else float("nan")

    # KGE via Gupta 2009: 1 - sqrt((r-1)^2 + (alpha-1)^2 + (beta-1)^2)
    if obs.std() == 0 or pred.std() == 0:
        kge = float("nan")
    else:
        r = np.corrcoef(obs, pred)[0, 1]
        alpha = pred.std() / obs.std()
        beta = pred.mean() / obs_mean if obs_mean != 0 else float("nan")
        if np.isnan(beta):
            kge = float("nan")
        else:
            kge = 1.0 - float(np.sqrt((r - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2))

    bias = float(residual.mean())
    mae = float(np.abs(residual).mean())
    rmse = float(np.sqrt((residual ** 2).mean()))
    fhv = _compute_fhv(obs, pred)
    return {"nse": float(nse), "kge": float(kge), "bias": bias, "mae": mae, "rmse": rmse, "fhv": fhv}


def load_seed_csv(path: Path) -> pd.DataFrame:
    """Load required_series CSV for one seed; keep only the columns we need."""
    df = pd.read_csv(path, usecols=list(REQUIRED_COLS), dtype={"basin": str})
    df["basin"] = df["basin"].map(normalize_basin_id)
    df = filter_valid_rows(df, obs_col="obs")
    return df


def per_basin_metrics_for_seed(df_seed: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Compute per-basin per-model NSE/KGE/bias/MAE/RMSE for one seed."""
    rows = []
    for basin, group in df_seed.groupby("basin", sort=True):
        obs = group["obs"].to_numpy(dtype=float)
        for model_name, pred_col in (("model1", "model1"), ("model2_q50", "q50")):
            pred = group[pred_col].to_numpy(dtype=float)
            metrics = compute_metrics(obs, pred)
            rows.append({
                "basin_id": basin,
                "seed": seed,
                "model": model_name,
                **metrics,
            })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--raw-metrics-dir", type=Path, default=DEFAULT_RAW_METRICS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(SEEDS))
    args = parser.parse_args()

    output_dir = args.output_dir
    tables_dir = output_dir / "tables"
    figures_dir = output_dir / "figures"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    per_seed_frames: list[pd.DataFrame] = []
    for seed in args.seeds:
        seed_csv = args.input_dir / f"seed{seed}" / "primary_required_series.csv"
        if not seed_csv.exists():
            raise FileNotFoundError(seed_csv)
        print(f"[A1] loading {seed_csv}", flush=True)
        df_seed = load_seed_csv(seed_csv)
        print(f"[A1] seed={seed} obs-rows={len(df_seed)} basins={df_seed['basin'].nunique()}", flush=True)
        per_seed_frames.append(per_basin_metrics_for_seed(df_seed, seed))
        # Release the large frame before loading the next seed
        del df_seed

    wide = pd.concat(per_seed_frames, ignore_index=True)
    wide = wide.sort_values(["basin_id", "seed", "model"]).reset_index(drop=True)
    wide_path = tables_dir / "rq1_central_metrics_per_basin_seed.csv"
    header = (
        "# RQ-1 central metrics — wide form per (basin × seed × model)\n"
        "# sign: bias = mean(pred - obs); MAE/RMSE always >= 0\n"
        "# aggregation: per-basin per-seed; downstream median-across-seeds in seed_median table\n"
        "# nan policy: rows with NaN obs dropped (see scripts/_lib/expanded_drbc.filter_valid_rows)\n"
    )
    with wide_path.open("w") as f:
        f.write(header)
        wide.to_csv(f, index=False)
    print(f"[A1] wrote {wide_path} ({len(wide)} rows)", flush=True)

    # Long-form seed_median per (basin × metric) with model1/model2_q50/delta columns
    long_rows: list[dict[str, object]] = []
    for basin, basin_group in wide.groupby("basin_id"):
        for metric in METRIC_ORDER:
            m1_series = basin_group.loc[basin_group["model"] == "model1", ["seed", metric]]
            m2_series = basin_group.loc[basin_group["model"] == "model2_q50", ["seed", metric]]
            m1_med = float(m1_series[metric].median())
            m2_med = float(m2_series[metric].median())
            # Paired delta at per-seed level then median
            m1_df = m1_series.rename(columns={metric: "value"}).assign(basin_id=basin)
            m2_df = m2_series.rename(columns={metric: "value"}).assign(basin_id=basin)
            delta_df = paired_delta_per_seed(
                m1_df,
                m2_df,
                value_col="value",
                basin_col="basin_id",
                seed_col="seed",
            )
            delta_median = float(per_basin_seed_then_median(
                delta_df, value_col="delta"
            ).loc[basin])
            long_rows.append({
                "basin_id": basin,
                "metric": metric,
                "model1": m1_med,
                "model2_q50": m2_med,
                "delta_m2_minus_m1": delta_median,
            })
    long = pd.DataFrame(long_rows)
    long_path = tables_dir / "rq1_central_metrics_seed_median.csv"
    with long_path.open("w") as f:
        f.write("# RQ-1 central metrics — seed-median per (basin × metric)\n")
        f.write("# delta_m2_minus_m1 computed at per-seed level then median across seeds\n")
        long.to_csv(f, index=False)
    print(f"[A1] wrote {long_path} ({len(long)} rows)", flush=True)

    # Pooled summary
    pooled_rows: list[dict[str, object]] = []
    for metric in METRIC_ORDER:
        sub = long[long["metric"] == metric]
        delta = sub["delta_m2_minus_m1"]
        pooled_rows.append({
            "metric": metric,
            "model1_basin_median": float(sub["model1"].median()),
            "model2_q50_basin_median": float(sub["model2_q50"].median()),
            "delta_basin_median": float(delta.median()),
            "delta_basin_iqr_low": float(delta.quantile(0.25)),
            "delta_basin_iqr_high": float(delta.quantile(0.75)),
        })
    pooled = pd.DataFrame(pooled_rows)
    pooled_path = tables_dir / "rq1_central_metrics_pooled_summary.csv"
    with pooled_path.open("w") as f:
        f.write("# RQ-1 central metrics — pooled summary across basins\n")
        pooled.to_csv(f, index=False)
    print(f"[A1] wrote {pooled_path}", flush=True)

    # Figures
    fig, axes = plt.subplots(1, len(METRIC_ORDER), figsize=(4 * len(METRIC_ORDER), 4), sharey=False)
    for ax, metric in zip(axes, METRIC_ORDER):
        sub = long[long["metric"] == metric]
        ax.boxplot([sub["model1"], sub["model2_q50"]], labels=["M1", "M2 q50"])
        ax.set_title(metric)
        ax.grid(alpha=0.3)
    fig.suptitle("RQ-1 central metrics — basin-median across seeds")
    fig.tight_layout()
    box_path = figures_dir / "rq1_central_metric_boxplots.png"
    fig.savefig(box_path, dpi=140)
    plt.close(fig)
    print(f"[A1] wrote {box_path}", flush=True)

    fig2, axes2 = plt.subplots(1, len(METRIC_ORDER), figsize=(4 * len(METRIC_ORDER), 4))
    for ax, metric in zip(axes2, METRIC_ORDER):
        sub = long[long["metric"] == metric]
        ax.scatter(sub["model1"], sub["model2_q50"], s=15, alpha=0.6)
        lo = min(sub["model1"].min(), sub["model2_q50"].min())
        hi = max(sub["model1"].max(), sub["model2_q50"].max())
        ax.plot([lo, hi], [lo, hi], "k--", linewidth=0.8)
        ax.set_xlabel("M1")
        ax.set_ylabel("M2 q50")
        ax.set_title(metric)
        ax.grid(alpha=0.3)
    fig2.suptitle("RQ-1 paired delta — basin-median scatter")
    fig2.tight_layout()
    scatter_path = figures_dir / "rq1_paired_delta_scatter.png"
    fig2.savefig(scatter_path, dpi=140)
    plt.close(fig2)
    print(f"[A1] wrote {scatter_path}", flush=True)


if __name__ == "__main__":
    main()
