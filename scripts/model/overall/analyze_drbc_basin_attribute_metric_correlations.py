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

    seed_dfs = []
    for seed in seeds:
        m1_epoch = PRIMARY_EPOCHS[seed]["model1"]
        m2_epoch = PRIMARY_EPOCHS[seed]["model2"]
        m1 = raw[(raw["model"] == "model1") & (raw["seed"] == seed) & (raw["epoch"] == m1_epoch)][
            ["basin", "NSE", "KGE", "FHV", "Peak-Timing", "Peak-MAPE"]
        ].rename(columns={"NSE": "m1_NSE", "KGE": "m1_KGE", "FHV": "m1_FHV",
                           "Peak-Timing": "m1_Peak_Timing", "Peak-MAPE": "m1_Peak_MAPE"})
        m2 = raw[(raw["model"] == "model2") & (raw["seed"] == seed) & (raw["epoch"] == m2_epoch)][
            ["basin", "NSE", "KGE", "FHV", "Peak-Timing", "Peak-MAPE"]
        ].rename(columns={"NSE": "m2_NSE", "KGE": "m2_KGE", "FHV": "m2_FHV",
                           "Peak-Timing": "m2_Peak_Timing", "Peak-MAPE": "m2_Peak_MAPE"})
        merged_seed = m1.merge(m2, on="basin", how="inner")
        merged_seed["seed"] = seed
        seed_dfs.append(merged_seed)
    seed_df = pd.concat(seed_dfs, ignore_index=True)

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
    mask = np.isfinite(obs) & np.isfinite(pred)
    if mask.sum() == 0:
        return float("nan")
    err = obs[mask] - pred[mask]
    return float(np.mean(np.where(err >= 0, tau * err, (tau - 1) * err)))


def coverage_fraction(obs: np.ndarray, pred: np.ndarray) -> float:
    mask = np.isfinite(obs) & np.isfinite(pred)
    if mask.sum() == 0:
        return float("nan")
    return float(np.mean(obs[mask] <= pred[mask]))


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

    # BH FDR correction
    valid = corr_df["pval"].notna()
    pvals = corr_df.loc[valid, "pval"].to_numpy()
    _, pvals_bh, _, _ = multipletests(pvals, alpha=fdr_alpha, method="fdr_bh")
    corr_df.loc[valid, "pval_bh"] = pvals_bh
    corr_df["significant"] = corr_df["pval_bh"] < fdr_alpha
    corr_df["abs_rho"] = corr_df["rho"].abs()
    corr_df = corr_df.sort_values("abs_rho", ascending=False).reset_index(drop=True)
    return corr_df


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


def _draw_heatmap(
    corr: pd.DataFrame,
    metric_cols: list[str],
    title: str,
    path: Path,
) -> None:
    feats = [f for f in FEATURE_COLS if f in corr["feature"].values]
    metrics = [m for m in metric_cols if m in corr["metric"].values]
    feat_labels = [FEATURE_LABELS.get(f, f) for f in feats]
    metric_labels = [METRIC_LABELS.get(m, m) for m in metrics]

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


def _get_basin_ids(basin_metrics_path: Path, seeds: list[int]) -> set[str]:
    raw = pd.read_csv(basin_metrics_path, dtype={"basin": str})
    raw["basin"] = raw["basin"].str.zfill(8)
    return set(raw[raw["split"] == "test"]["basin"].unique())


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading basin features...")
    basin_ids = _get_basin_ids(args.basin_metrics, args.seeds)
    features = load_basin_features(args.drbc_attrs, basin_ids)
    print(f"  Features: {features.shape}")

    print("Loading deterministic metrics...")
    det_metrics = load_deterministic_metrics(args.basin_metrics, args.basin_deltas, args.seeds)
    print(f"  Det metrics: {det_metrics.shape}")

    print("Computing obs-based features...")
    obs_features = compute_obs_features(args.series_dir)
    print(f"  Obs features: {obs_features.shape}")

    print("Computing probabilistic metrics...")
    prob_metrics = compute_probabilistic_metrics(args.series_dir, args.seeds)
    print(f"  Prob metrics: {prob_metrics.shape}")

    print("Building master table...")
    master = build_master_table(features, det_metrics, obs_features, prob_metrics)
    print(f"  Master table: {master.shape}")
    print(f"  NaN count:\n{master.isna().sum()[master.isna().sum() > 0]}")

    print("Running Spearman correlations...")
    corr = run_spearman_correlations(master, args.fdr_alpha)
    print(f"  {len(corr)} pairs, {corr['significant'].sum()} significant (BH p<{args.fdr_alpha})")
    print(corr.head(10)[["feature", "metric", "rho", "pval_bh", "significant"]])

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


if __name__ == "__main__":
    main()
