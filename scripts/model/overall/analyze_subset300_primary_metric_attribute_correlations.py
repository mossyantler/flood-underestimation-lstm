#!/usr/bin/env python3
# /// script
# dependencies = [
#   "geopandas>=0.14",
#   "matplotlib>=3.8",
#   "numpy>=1.26",
#   "pandas>=2.2",
#   "scipy>=1.13",
# ]
# ///
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_METRICS = (
    REPO_ROOT / "output/model_analysis/overall_analysis/epoch_sensitivity/tables/basin_metrics.csv"
)
DEFAULT_PRIMARY_SUMMARY = (
    REPO_ROOT / "output/model_analysis/overall_analysis/main_comparison/tables/primary_epoch_summary.csv"
)
DEFAULT_STATIC_ATTRIBUTES = (
    REPO_ROOT / "data/CAMELSH_generic/drbc_holdout_broad/attributes/static_attributes.csv"
)
DEFAULT_DRBC_ATTRIBUTES = (
    REPO_ROOT / "output/basin/drbc/analysis/basin_attributes/tables/drbc_selected_basin_analysis_table.csv"
)
DEFAULT_BASIN_SHAPEFILE = REPO_ROOT / "basins/CAMELSH_data/shapefiles/CAMELSH_shapefile.shp"
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "output/model_analysis/overall_analysis/main_comparison/attribute_correlations"
)

OFFICIAL_SEEDS = [111, 222, 444]
MODELS = ["model1", "model2"]
MODEL_LABELS = {"model1": "Model 1", "model2": "Model 2"}
MODEL_SHORT_LABELS = {"model1": "M1", "model2": "M2"}
MODEL_COLORS = {"model1": "#2563eb", "model2": "#dc2626"}
SEED_MARKERS = {111: "o", 222: "s", 444: "^"}

BASE_METRICS = ["NSE", "KGE", "FHV", "Peak-Timing", "Peak-MAPE"]
CORE_FEATURES = [
    "area",
    "slope",
    "aridity",
    "snow_fraction",
    "soil_depth",
    "permeability",
    "baseflow_index",
    "forest_fraction",
    "centroid_lat",
    "centroid_lng",
    "lat_gage",
    "lng_gage",
]
FEATURE_LABELS = {
    "area": "Area",
    "log10_area": "log10(Area)",
    "slope": "Slope",
    "log10_slope": "log10(Slope)",
    "aridity": "Aridity",
    "snow_fraction": "Snow fraction",
    "soil_depth": "Soil depth",
    "log10_soil_depth": "log10(Soil depth)",
    "permeability": "Permeability",
    "log10_permeability": "log10(Permeability)",
    "baseflow_index": "Baseflow index",
    "forest_fraction": "Forest fraction",
    "centroid_lat": "Area centroid latitude",
    "centroid_lng": "Area centroid longitude",
    "lat_gage": "Gauge latitude",
    "lng_gage": "Gauge longitude",
}


@dataclass(frozen=True)
class MetricSpec:
    column: str
    folder: str
    label: str
    delta_mode: str
    delta_label: str


METRIC_SPECS = [
    MetricSpec("NSE", "NSE", "NSE", "higher_better", "Model 2 - Model 1"),
    MetricSpec("KGE", "KGE", "KGE", "higher_better", "Model 2 - Model 1"),
    MetricSpec("FHV", "FHV", "FHV", "signed_shift", "Model 2 - Model 1 signed shift"),
    MetricSpec("Peak-Timing", "Peak_Timing", "Peak Timing", "lower_better", "Model 1 - Model 2 reduction"),
    MetricSpec("Peak-MAPE", "Peak_MAPE", "Peak MAPE", "lower_better", "Model 1 - Model 2 reduction"),
    MetricSpec("abs_FHV", "abs_FHV", "|FHV|", "lower_better", "Model 1 - Model 2 reduction"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze basin-level Spearman correlations between primary checkpoint metrics "
            "and core static/spatial basin attributes."
        )
    )
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--primary-summary", type=Path, default=DEFAULT_PRIMARY_SUMMARY)
    parser.add_argument("--static-attributes", type=Path, default=DEFAULT_STATIC_ATTRIBUTES)
    parser.add_argument("--drbc-attributes", type=Path, default=DEFAULT_DRBC_ATTRIBUTES)
    parser.add_argument("--basin-shapefile", type=Path, default=DEFAULT_BASIN_SHAPEFILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--split", default="test", choices=["test", "validation"])
    parser.add_argument("--seeds", type=int, nargs="+", default=OFFICIAL_SEEDS)
    parser.add_argument("--top-n", type=int, default=6)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def normalize_basin_id(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        return f"{int(float(text)):08d}"
    except (TypeError, ValueError):
        return text.zfill(8)


def normalize_huc02(value: Any) -> Any:
    if pd.isna(value):
        return value
    text = str(value).strip()
    if not text:
        return pd.NA
    try:
        return f"{int(float(text)):02d}"
    except (TypeError, ValueError):
        return text.zfill(2)


def _to_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def read_primary_metric_rows(
    metrics_path: Path,
    primary_summary_path: Path,
    split: str,
    seeds: list[int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    metrics = pd.read_csv(metrics_path, dtype={"basin": str})
    metrics["basin"] = metrics["basin"].map(normalize_basin_id)
    metrics = _to_numeric(metrics, BASE_METRICS)
    metrics["abs_FHV"] = metrics["FHV"].abs()

    primary = pd.read_csv(primary_summary_path)
    primary = primary[
        primary["model"].isin(MODELS)
        & primary["seed"].isin(seeds)
        & primary["split"].eq(split)
        & primary["status"].eq("available")
    ].copy()
    if primary.empty:
        raise SystemExit(f"No available primary rows for split={split!r} seeds={seeds}")

    primary = primary[["model", "seed", "split", "epoch", "run_name", "n_basins", "status"]]
    rows = metrics.merge(
        primary[["model", "seed", "split", "epoch"]],
        on=["model", "seed", "split", "epoch"],
        how="inner",
        validate="many_to_one",
    )
    if rows.empty:
        raise SystemExit("No basin metric rows matched the primary epoch summary.")

    rows["model_label"] = rows["model"].map(MODEL_LABELS).fillna(rows["model"])
    return rows.sort_values(["model", "seed", "basin"]).reset_index(drop=True), primary


def read_centroids(shapefile_path: Path) -> pd.DataFrame:
    shapes = gpd.read_file(shapefile_path)
    if "GAGE_ID" not in shapes.columns:
        raise ValueError(f"Missing GAGE_ID column in {shapefile_path}")
    shapes = shapes[["GAGE_ID", "geometry"]].copy()
    shapes["basin"] = shapes["GAGE_ID"].map(normalize_basin_id)
    shapes = shapes[~shapes["geometry"].isna()].copy()
    if shapes.crs is None:
        shapes = shapes.set_crs("EPSG:4326")
    centroids = shapes.to_crs("EPSG:5070").centroid
    centroid_points = gpd.GeoSeries(centroids, crs="EPSG:5070").to_crs("EPSG:4326")
    out = pd.DataFrame(
        {
            "basin": shapes["basin"].to_numpy(),
            "centroid_lng": centroid_points.x.to_numpy(),
            "centroid_lat": centroid_points.y.to_numpy(),
        }
    )
    return out.drop_duplicates("basin")


def read_attributes(
    static_path: Path,
    drbc_path: Path,
    shapefile_path: Path,
) -> pd.DataFrame:
    static = pd.read_csv(static_path, dtype={"gauge_id": str, "HUC02": str, "STATE": str})
    static["basin"] = static["gauge_id"].map(normalize_basin_id)
    static = static.rename(columns={"HUC02": "static_huc02", "STATE": "static_state"})
    static_keep = [
        "basin",
        "static_huc02",
        "static_state",
        "area",
        "slope",
        "aridity",
        "snow_fraction",
        "soil_depth",
        "permeability",
        "baseflow_index",
        "forest_fraction",
    ]
    static = static[[col for col in static_keep if col in static.columns]].copy()
    static = _to_numeric(
        static,
        [
            "area",
            "slope",
            "aridity",
            "snow_fraction",
            "soil_depth",
            "permeability",
            "baseflow_index",
            "forest_fraction",
        ],
    )

    drbc = pd.read_csv(drbc_path, dtype={"gauge_id": str, "camelsh_huc02": str})
    drbc["basin"] = drbc["gauge_id"].map(normalize_basin_id)
    drbc_keep = [
        "basin",
        "gauge_id",
        "gauge_name",
        "state",
        "camelsh_huc02",
        "lat_gage",
        "lng_gage",
        "drain_sqkm_attr",
        "basin_area_sqkm_geom",
        "overlap_ratio_of_basin",
    ]
    drbc = drbc[[col for col in drbc_keep if col in drbc.columns]].copy()
    drbc = drbc.rename(columns={"state": "drbc_state", "camelsh_huc02": "drbc_huc02"})
    drbc = _to_numeric(
        drbc,
        ["lat_gage", "lng_gage", "drain_sqkm_attr", "basin_area_sqkm_geom", "overlap_ratio_of_basin"],
    )

    centroids = read_centroids(shapefile_path)
    attrs = static.merge(drbc, on="basin", how="outer").merge(centroids, on="basin", how="left")
    attrs["state"] = attrs.get("drbc_state", pd.Series(index=attrs.index, dtype=object)).combine_first(
        attrs.get("static_state", pd.Series(index=attrs.index, dtype=object))
    )
    attrs["huc02"] = attrs.get("drbc_huc02", pd.Series(index=attrs.index, dtype=object)).combine_first(
        attrs.get("static_huc02", pd.Series(index=attrs.index, dtype=object))
    )
    for col in ["static_huc02", "drbc_huc02", "huc02"]:
        if col in attrs.columns:
            attrs[col] = attrs[col].map(normalize_huc02)

    for col in ["area", "slope", "soil_depth", "permeability"]:
        if col in attrs.columns:
            values = pd.to_numeric(attrs[col], errors="coerce")
            transformed = pd.Series(np.nan, index=attrs.index, dtype=float)
            positive = values > 0
            transformed.loc[positive] = np.log10(values.loc[positive])
            attrs[f"log10_{col}"] = transformed

    return attrs.drop_duplicates("basin")


def delta_values(model1: pd.Series, model2: pd.Series, mode: str) -> pd.Series:
    if mode == "higher_better":
        return model2 - model1
    if mode == "lower_better":
        return model1 - model2
    if mode == "signed_shift":
        return model2 - model1
    raise ValueError(f"Unknown delta mode: {mode}")


def build_metric_table(
    metric_rows: pd.DataFrame,
    attributes: pd.DataFrame,
    spec: MetricSpec,
    seeds: list[int],
) -> tuple[pd.DataFrame, list[str], list[str]]:
    basin_index = sorted(metric_rows["basin"].dropna().unique())
    table = pd.DataFrame({"basin": basin_index})
    model_seed_cols: dict[str, list[str]] = {}

    for model in MODELS:
        pivot = (
            metric_rows[metric_rows["model"].eq(model)]
            .pivot_table(index="basin", columns="seed", values=spec.column, aggfunc="first")
            .reindex(columns=seeds)
        )
        renamed = {seed: f"{model}_seed{seed}" for seed in seeds}
        pivot = pivot.rename(columns=renamed).reset_index()
        table = table.merge(pivot, on="basin", how="left")
        cols = [renamed[seed] for seed in seeds]
        model_seed_cols[model] = cols
        table[f"{model}_seed_median"] = table[cols].median(axis=1, skipna=True)
        table[f"{model}_seed_mean"] = table[cols].mean(axis=1, skipna=True)
        table[f"{model}_seed_std"] = table[cols].std(axis=1, skipna=True)

    delta_cols = []
    for seed in seeds:
        left = f"model1_seed{seed}"
        right = f"model2_seed{seed}"
        out_col = f"delta_seed{seed}"
        table[out_col] = delta_values(table[left], table[right], spec.delta_mode)
        delta_cols.append(out_col)

    table["delta_seed_median"] = table[delta_cols].median(axis=1, skipna=True)
    table["delta_seed_mean"] = table[delta_cols].mean(axis=1, skipna=True)
    table["delta_seed_std"] = table[delta_cols].std(axis=1, skipna=True)

    table = attributes.merge(table, on="basin", how="inner")
    aggregate_targets = ["model1_seed_median", "model2_seed_median", "delta_seed_median"]
    seed_targets = model_seed_cols["model1"] + model_seed_cols["model2"] + delta_cols
    return table.sort_values("basin").reset_index(drop=True), aggregate_targets, seed_targets


def bh_fdr(p_values: pd.Series) -> pd.Series:
    q_values = pd.Series(np.nan, index=p_values.index, dtype=float)
    valid = p_values.dropna().astype(float)
    if valid.empty:
        return q_values
    order = valid.sort_values().index
    ranked = valid.loc[order].to_numpy()
    n = len(ranked)
    adjusted = ranked * n / np.arange(1, n + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    adjusted = np.clip(adjusted, 0.0, 1.0)
    q_values.loc[order] = adjusted
    return q_values


def spearman_correlations(
    table: pd.DataFrame,
    metric: str,
    targets: list[str],
    features: list[str],
    target_scope: str,
) -> pd.DataFrame:
    rows = []
    for target in targets:
        for feature in features:
            if target not in table.columns or feature not in table.columns:
                continue
            subset = table[[target, feature]].replace([np.inf, -np.inf], np.nan).dropna()
            row = {
                "metric": metric,
                "target_scope": target_scope,
                "target": target,
                "feature": feature,
                "feature_label": FEATURE_LABELS.get(feature, feature),
                "n": int(len(subset)),
                "rho": math.nan,
                "p_value": math.nan,
                "abs_rho": math.nan,
            }
            if (
                len(subset) >= 4
                and subset[target].nunique(dropna=True) > 1
                and subset[feature].nunique(dropna=True) > 1
            ):
                result = stats.spearmanr(subset[feature], subset[target], nan_policy="omit")
                row["rho"] = float(result.statistic)
                row["p_value"] = float(result.pvalue)
                row["abs_rho"] = abs(row["rho"])
            rows.append(row)

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["q_fdr"] = bh_fdr(out["p_value"])
    return out.sort_values(["abs_rho", "target", "feature"], ascending=[False, True, True])


def target_label(target: str, spec: MetricSpec) -> str:
    if target == "model1_seed_median":
        return f"Model 1 median {spec.label}"
    if target == "model2_seed_median":
        return f"Model 2 median {spec.label}"
    if target == "delta_seed_median":
        return f"Median delta ({spec.delta_label})"
    if target.startswith("model1_seed"):
        return f"Model 1 seed {target.replace('model1_seed', '')}"
    if target.startswith("model2_seed"):
        return f"Model 2 seed {target.replace('model2_seed', '')}"
    if target.startswith("delta_seed"):
        return f"Delta seed {target.replace('delta_seed', '')}"
    return target


def write_heatmap(corr: pd.DataFrame, spec: MetricSpec, output_path: Path) -> bool:
    if corr.empty:
        return False
    heat = corr.pivot(index="target", columns="feature", values="rho")
    ordered_targets = [target for target in ["model1_seed_median", "model2_seed_median", "delta_seed_median"] if target in heat.index]
    ordered_features = [feature for feature in CORE_FEATURES if feature in heat.columns]
    heat = heat.loc[ordered_targets, ordered_features]
    if heat.empty:
        return False

    values = heat.to_numpy(dtype=float)
    fig_width = max(10.5, 0.62 * len(ordered_features))
    fig_height = max(3.8, 0.82 * len(ordered_targets) + 1.8)
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    image = ax.imshow(values, cmap="RdBu_r", vmin=-1.0, vmax=1.0, aspect="auto")
    ax.set_xticks(range(len(ordered_features)), [FEATURE_LABELS.get(col, col) for col in ordered_features], rotation=35, ha="right")
    ax.set_yticks(range(len(ordered_targets)), [target_label(t, spec) for t in ordered_targets])
    ax.set_title(f"{spec.label}: Spearman correlation with core basin attributes")

    for row_idx in range(values.shape[0]):
        for col_idx in range(values.shape[1]):
            value = values[row_idx, col_idx]
            if np.isfinite(value):
                ax.text(
                    col_idx,
                    row_idx,
                    f"{value:.2f}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="#ffffff" if abs(value) >= 0.55 else "#111111",
                )

    cbar = fig.colorbar(image, ax=ax, shrink=0.88)
    cbar.set_label("Spearman rho")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return True


def write_top_scatter(
    table: pd.DataFrame,
    corr: pd.DataFrame,
    spec: MetricSpec,
    output_path: Path,
    top_n: int,
) -> bool:
    top = corr.dropna(subset=["rho"]).sort_values("abs_rho", ascending=False).head(top_n)
    if top.empty:
        return False

    n_plots = len(top)
    n_cols = min(3, n_plots)
    n_rows = math.ceil(n_plots / n_cols)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5.2 * n_cols, 4.0 * n_rows), squeeze=False)
    axes_flat = axes.ravel()

    for ax, (_, row) in zip(axes_flat, top.iterrows(), strict=False):
        target = str(row["target"])
        feature = str(row["feature"])
        subset = table[["basin", target, feature]].replace([np.inf, -np.inf], np.nan).dropna()
        ax.scatter(subset[feature], subset[target], s=34, color="#2563eb", alpha=0.82, edgecolors="#172554", linewidths=0.35)
        ax.set_xlabel(FEATURE_LABELS.get(feature, feature))
        ax.set_ylabel(target_label(target, spec))
        ax.set_title(f"rho={row['rho']:.2f}, q={row['q_fdr']:.3g}, n={int(row['n'])}")
        ax.grid(True, color="#e5e7eb", linewidth=0.7)

    for ax in axes_flat[n_plots:]:
        ax.axis("off")

    fig.suptitle(f"{spec.label}: strongest primary attribute correlations")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return True


def clear_png_files(figures_dir: Path) -> None:
    if not figures_dir.exists():
        return
    for path in figures_dir.rglob("*.png"):
        path.unlink()


def top_correlations_by_target(corr: pd.DataFrame, top_n: int) -> pd.DataFrame:
    rows = []
    valid = corr.dropna(subset=["rho"]).copy()
    if valid.empty:
        return valid
    for target, group in valid.groupby("target", sort=True):
        rows.append(group.sort_values("abs_rho", ascending=False).head(top_n).copy())
    if not rows:
        return pd.DataFrame(columns=valid.columns)
    return pd.concat(rows, ignore_index=True)


def write_target_heatmap(
    corr: pd.DataFrame,
    spec: MetricSpec,
    output_path: Path,
    ordered_targets: list[str],
    title: str,
) -> bool:
    if corr.empty:
        return False
    heat = corr.pivot(index="target", columns="feature", values="rho")
    ordered_targets = [target for target in ordered_targets if target in heat.index]
    ordered_features = [feature for feature in CORE_FEATURES if feature in heat.columns]
    if not ordered_targets or not ordered_features:
        return False
    heat = heat.loc[ordered_targets, ordered_features]

    values = heat.to_numpy(dtype=float)
    fig_width = max(10.5, 0.62 * len(ordered_features))
    fig_height = max(3.8, 0.72 * len(ordered_targets) + 1.8)
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    image = ax.imshow(values, cmap="RdBu_r", vmin=-1.0, vmax=1.0, aspect="auto")
    ax.set_xticks(
        range(len(ordered_features)),
        [FEATURE_LABELS.get(col, col) for col in ordered_features],
        rotation=35,
        ha="right",
    )
    ax.set_yticks(range(len(ordered_targets)), [target_label(t, spec) for t in ordered_targets])
    ax.set_title(title)

    for row_idx in range(values.shape[0]):
        for col_idx in range(values.shape[1]):
            value = values[row_idx, col_idx]
            if np.isfinite(value):
                ax.text(
                    col_idx,
                    row_idx,
                    f"{value:.2f}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="#ffffff" if abs(value) >= 0.55 else "#111111",
                )

    cbar = fig.colorbar(image, ax=ax, shrink=0.88)
    cbar.set_label("Spearman rho")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return True


def write_target_top_scatter(
    table: pd.DataFrame,
    corr: pd.DataFrame,
    spec: MetricSpec,
    output_path: Path,
    top_n: int,
) -> bool:
    top = corr.dropna(subset=["rho"]).sort_values("abs_rho", ascending=False).head(top_n)
    if top.empty:
        return False

    n_plots = len(top)
    n_cols = min(3, n_plots)
    n_rows = math.ceil(n_plots / n_cols)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5.2 * n_cols, 4.0 * n_rows), squeeze=False)
    axes_flat = axes.ravel()
    target = str(top["target"].iloc[0])

    for ax, (_, row) in zip(axes_flat, top.iterrows(), strict=False):
        feature = str(row["feature"])
        x_col, x_label = _display_feature(table, feature)
        subset = table[[target, x_col]].replace([np.inf, -np.inf], np.nan).dropna()
        ax.scatter(
            subset[x_col],
            subset[target],
            s=34,
            color="#2563eb",
            alpha=0.82,
            edgecolors="#172554",
            linewidths=0.35,
        )
        if spec.column in {"NSE", "KGE", "FHV"}:
            ax.axhline(0, color="#6b7280", linewidth=0.85)
        ax.set_xlabel(x_label)
        ax.set_ylabel(target_label(target, spec))
        ax.set_title(f"{FEATURE_LABELS.get(feature, feature)} | rho={row['rho']:.2f}, q={row['q_fdr']:.3g}")
        ax.grid(True, color="#e5e7eb", linewidth=0.7)

    for ax in axes_flat[n_plots:]:
        ax.axis("off")

    fig.suptitle(f"{spec.label}: {target_label(target, spec)} top attribute correlations")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return True


def _unique_top_features(corr: pd.DataFrame, max_features: int) -> list[str]:
    features = []
    if corr.empty:
        return features
    for feature in corr.dropna(subset=["rho"]).sort_values("abs_rho", ascending=False)["feature"]:
        feature = str(feature)
        if feature not in features:
            features.append(feature)
        if len(features) >= max_features:
            break
    return features


def _display_feature(table: pd.DataFrame, feature: str) -> tuple[str, str]:
    if feature == "area" and "log10_area" in table.columns:
        return "log10_area", "log10(Area)"
    if feature == "slope" and "log10_slope" in table.columns:
        return "log10_slope", "log10(Slope)"
    return feature, FEATURE_LABELS.get(feature, feature)


def write_model_seed_scatter_grid(
    table: pd.DataFrame,
    corr: pd.DataFrame,
    spec: MetricSpec,
    output_path: Path,
    seeds: list[int],
    max_features: int,
) -> bool:
    features = _unique_top_features(corr, max_features)
    if not features:
        return False

    n_plots = len(features)
    n_cols = min(3, n_plots)
    n_rows = math.ceil(n_plots / n_cols)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5.6 * n_cols, 4.3 * n_rows), squeeze=False)
    axes_flat = axes.ravel()

    handles = []
    labels = []
    for ax, feature in zip(axes_flat, features, strict=False):
        x_col, x_label = _display_feature(table, feature)
        if x_col not in table.columns:
            ax.axis("off")
            continue
        x = pd.to_numeric(table[x_col], errors="coerce")
        for model in MODELS:
            for seed in seeds:
                y_col = f"{model}_seed{seed}"
                if y_col not in table.columns:
                    continue
                y = pd.to_numeric(table[y_col], errors="coerce")
                valid = x.notna() & y.notna()
                if not valid.any():
                    continue
                scatter = ax.scatter(
                    x.loc[valid],
                    y.loc[valid],
                    s=34,
                    marker=SEED_MARKERS.get(seed, "o"),
                    facecolor=MODEL_COLORS[model],
                    edgecolor="#111827",
                    linewidth=0.35,
                    alpha=0.72,
                    label=f"{MODEL_SHORT_LABELS[model]} seed {seed}",
                )
                label = f"{MODEL_SHORT_LABELS[model]} seed {seed}"
                if label not in labels:
                    labels.append(label)
                    handles.append(scatter)
        if spec.column in {"NSE", "KGE", "FHV"}:
            ax.axhline(0, color="#6b7280", linewidth=0.85)
        ax.set_xlabel(x_label)
        ax.set_ylabel(spec.label)
        ax.set_title(FEATURE_LABELS.get(feature, feature))
        ax.grid(True, color="#e5e7eb", linewidth=0.7)

    for ax in axes_flat[n_plots:]:
        ax.axis("off")

    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.995),
        ncol=min(6, len(labels)),
        frameon=False,
    )
    fig.suptitle(f"{spec.label}: model/seed metric values by top attributes", y=0.945)
    fig.tight_layout(rect=[0, 0, 1, 0.88])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return True


def write_model_seed_pair_matrix(
    table: pd.DataFrame,
    corr: pd.DataFrame,
    spec: MetricSpec,
    output_path: Path,
    seeds: list[int],
    max_features: int = 3,
) -> bool:
    features = _unique_top_features(corr, max_features)
    columns: list[tuple[str, str]] = []
    for feature in features:
        x_col, x_label = _display_feature(table, feature)
        if x_col in table.columns and x_col not in [col for col, _ in columns]:
            columns.append((x_col, x_label))
    for model in MODELS:
        for seed in seeds:
            col = f"{model}_seed{seed}"
            if col in table.columns:
                columns.append((col, f"{MODEL_SHORT_LABELS[model]} s{seed}"))
    if len(columns) < 2:
        return False

    data = table[[col for col, _ in columns]].apply(pd.to_numeric, errors="coerce")
    labels = [label for _, label in columns]
    n = len(columns)
    fig, axes = plt.subplots(n, n, figsize=(2.35 * n, 2.35 * n))

    for row_idx, (y_col, y_label) in enumerate(columns):
        for col_idx, (x_col, x_label) in enumerate(columns):
            ax = axes[row_idx, col_idx]
            if row_idx == col_idx:
                ax.text(0.5, 0.5, y_label, ha="center", va="center", fontsize=11, transform=ax.transAxes)
                ax.set_xticks([])
                ax.set_yticks([])
            else:
                subset = data[[x_col, y_col]].dropna()
                ax.scatter(
                    subset[x_col],
                    subset[y_col],
                    s=16,
                    facecolors="none",
                    edgecolors="#374151",
                    linewidths=0.7,
                    alpha=0.88,
                )
            if row_idx < n - 1:
                ax.set_xticklabels([])
            else:
                ax.tick_params(axis="x", labelsize=7, rotation=35)
            if col_idx > 0:
                ax.set_yticklabels([])
            else:
                ax.tick_params(axis="y", labelsize=7)
            ax.grid(False)

    fig.suptitle(f"{spec.label}: selected attributes and model/seed metric matrix")
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return True


def build_metric_rank_tables(
    table: pd.DataFrame,
    spec: MetricSpec,
    seeds: list[int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    meta_cols = [
        "basin",
        "gauge_name",
        "state",
        "huc02",
        "area",
        "slope",
        "aridity",
        "snow_fraction",
        "centroid_lat",
        "centroid_lng",
        "lat_gage",
        "lng_gage",
    ]
    meta_cols = [col for col in meta_cols if col in table.columns]
    for model in MODELS:
        for seed in seeds:
            value_col = f"{model}_seed{seed}"
            if value_col not in table.columns:
                continue
            work = table[meta_cols + [value_col]].copy()
            work = work.rename(columns={value_col: "metric_value"})
            work["metric_value"] = pd.to_numeric(work["metric_value"], errors="coerce")
            if spec.column in {"NSE", "KGE"}:
                work["rank_basis"] = work["metric_value"]
                work["rank_rule"] = "higher_metric_value_is_better"
                ascending = False
            elif spec.column == "FHV":
                work["rank_basis"] = work["metric_value"].abs()
                work["rank_rule"] = "lower_absolute_FHV_is_better"
                ascending = True
            else:
                work["rank_basis"] = work["metric_value"]
                work["rank_rule"] = "lower_metric_value_is_better"
                ascending = True

            valid = work["rank_basis"].notna()
            work["performance_rank"] = pd.NA
            work.loc[valid, "performance_rank"] = (
                work.loc[valid, "rank_basis"].rank(method="min", ascending=ascending).astype("Int64")
            )
            n_ranked = int(valid.sum())
            work["n_ranked_basins"] = n_ranked
            if n_ranked > 1:
                work["performance_percentile"] = 1.0 - (
                    pd.to_numeric(work["performance_rank"], errors="coerce") - 1.0
                ) / (n_ranked - 1.0)
            else:
                work["performance_percentile"] = np.nan
            work.insert(0, "metric", spec.column)
            work.insert(1, "metric_label", spec.label)
            work.insert(2, "model", model)
            work.insert(3, "model_label", MODEL_LABELS.get(model, model))
            work.insert(4, "seed", seed)
            rows.append(work)

    if rows:
        long = pd.concat(rows, ignore_index=True)
    else:
        long = pd.DataFrame()
    if long.empty:
        return long, pd.DataFrame()

    long["performance_rank"] = long["performance_rank"].astype("Int64")
    long = long.sort_values(["metric", "model", "seed", "performance_rank", "basin"])

    wide = table[meta_cols].copy()
    for model in MODELS:
        for seed in seeds:
            sub = long[(long["model"].eq(model)) & (long["seed"].eq(seed))][
                ["basin", "metric_value", "rank_basis", "performance_rank", "performance_percentile"]
            ].copy()
            prefix = f"{model}_seed{seed}"
            sub = sub.rename(
                columns={
                    "metric_value": f"{prefix}_value",
                    "rank_basis": f"{prefix}_rank_basis",
                    "performance_rank": f"{prefix}_rank",
                    "performance_percentile": f"{prefix}_percentile",
                }
            )
            wide = wide.merge(sub, on="basin", how="left")
    return long, wide


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def write_metric_outputs(
    table: pd.DataFrame,
    aggregate_corr: pd.DataFrame,
    seed_corr: pd.DataFrame,
    spec: MetricSpec,
    metric_dir: Path,
    args: argparse.Namespace,
) -> tuple[list[dict[str, str]], pd.DataFrame, pd.DataFrame]:
    tables_dir = metric_dir / "tables"
    figures_dir = metric_dir / "figures"
    metadata_dir = metric_dir / "metadata"
    for path in [tables_dir, figures_dir, metadata_dir]:
        path.mkdir(parents=True, exist_ok=True)
    clear_png_files(figures_dir)

    safe = spec.folder
    table_path = tables_dir / f"{safe}_basin_metric_attribute_table.csv"
    aggregate_path = tables_dir / f"{safe}_spearman_correlations.csv"
    seed_path = tables_dir / f"{safe}_spearman_seed_correlations.csv"
    model_seed_path = tables_dir / f"{safe}_model_seed_spearman_correlations.csv"
    delta_seed_path = tables_dir / f"{safe}_paired_delta_seed_spearman_correlations.csv"
    top_path = tables_dir / f"{safe}_top_correlations.csv"
    model_seed_top_path = tables_dir / f"{safe}_model_seed_top_correlations.csv"
    delta_seed_top_path = tables_dir / f"{safe}_paired_delta_seed_top_correlations.csv"
    rank_long_path = tables_dir / f"{safe}_model_seed_rank_table.csv"
    rank_wide_path = tables_dir / f"{safe}_model_seed_rank_wide.csv"
    model1_heatmap_path = figures_dir / f"{safe}_model1_seed_spearman_heatmap.png"
    model2_heatmap_path = figures_dir / f"{safe}_model2_seed_spearman_heatmap.png"
    scatter_dir = figures_dir / "model_seed"
    scatter_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = metadata_dir / f"{safe}_metadata.json"

    table.to_csv(table_path, index=False)
    aggregate_corr.to_csv(aggregate_path, index=False)
    seed_corr.to_csv(seed_path, index=False)
    model_seed_corr = seed_corr[
        seed_corr["target"].astype(str).str.startswith("model1_seed")
        | seed_corr["target"].astype(str).str.startswith("model2_seed")
    ].copy()
    delta_seed_corr = seed_corr[seed_corr["target"].astype(str).str.startswith("delta_seed")].copy()
    model_seed_corr.to_csv(model_seed_path, index=False)
    delta_seed_corr.to_csv(delta_seed_path, index=False)
    top = aggregate_corr.dropna(subset=["rho"]).sort_values("abs_rho", ascending=False).head(args.top_n)
    top.to_csv(top_path, index=False)
    model_seed_top = top_correlations_by_target(model_seed_corr, args.top_n)
    delta_seed_top = top_correlations_by_target(delta_seed_corr, args.top_n)
    model_seed_top.to_csv(model_seed_top_path, index=False)
    delta_seed_top.to_csv(delta_seed_top_path, index=False)
    rank_long, rank_wide = build_metric_rank_tables(table, spec, args.seeds)
    rank_long.to_csv(rank_long_path, index=False)
    rank_wide.to_csv(rank_wide_path, index=False)
    model1_targets = [f"model1_seed{seed}" for seed in args.seeds]
    model2_targets = [f"model2_seed{seed}" for seed in args.seeds]
    wrote_model1_heatmap = write_target_heatmap(
        model_seed_corr,
        spec,
        model1_heatmap_path,
        model1_targets,
        f"{spec.label}: Model 1 seed-level Spearman correlations",
    )
    wrote_model2_heatmap = write_target_heatmap(
        model_seed_corr,
        spec,
        model2_heatmap_path,
        model2_targets,
        f"{spec.label}: Model 2 seed-level Spearman correlations",
    )
    scatter_paths: dict[str, str] = {}
    for target in model1_targets + model2_targets:
        target_corr = model_seed_corr[model_seed_corr["target"].eq(target)].copy()
        if target_corr.empty:
            continue
        target_path = scatter_dir / f"{safe}_{target}_top_scatter.png"
        if write_target_top_scatter(table, target_corr, spec, target_path, args.top_n):
            scatter_paths[target] = relative(target_path)

    metadata = {
        "metric": spec.column,
        "label": spec.label,
        "delta_mode": spec.delta_mode,
        "delta_label": spec.delta_label,
        "split": args.split,
        "seeds": args.seeds,
        "n_basins": int(table["basin"].nunique()),
        "features": CORE_FEATURES,
        "targets": model1_targets + model2_targets,
        "aggregate_targets_retained_as_tables_only": [
            "model1_seed_median",
            "model2_seed_median",
            "delta_seed_median",
        ],
        "tables": {
            "basin_metric_attribute_table": relative(table_path),
            "spearman_correlations": relative(aggregate_path),
            "spearman_seed_correlations": relative(seed_path),
            "model_seed_spearman_correlations": relative(model_seed_path),
            "paired_delta_seed_spearman_correlations": relative(delta_seed_path),
            "top_correlations": relative(top_path),
            "model_seed_top_correlations": relative(model_seed_top_path),
            "paired_delta_seed_top_correlations": relative(delta_seed_top_path),
            "model_seed_rank_table": relative(rank_long_path),
            "model_seed_rank_wide": relative(rank_wide_path),
        },
        "figures": {
            "model1_seed_spearman_heatmap": relative(model1_heatmap_path) if wrote_model1_heatmap else "",
            "model2_seed_spearman_heatmap": relative(model2_heatmap_path) if wrote_model2_heatmap else "",
            "model_seed_top_scatter": scatter_paths,
        },
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    rows = [
        {"metric": spec.column, "artifact": "basin_metric_attribute_table", "path": relative(table_path)},
        {"metric": spec.column, "artifact": "spearman_correlations", "path": relative(aggregate_path)},
        {"metric": spec.column, "artifact": "spearman_seed_correlations", "path": relative(seed_path)},
        {"metric": spec.column, "artifact": "model_seed_spearman_correlations", "path": relative(model_seed_path)},
        {"metric": spec.column, "artifact": "paired_delta_seed_spearman_correlations", "path": relative(delta_seed_path)},
        {"metric": spec.column, "artifact": "top_correlations", "path": relative(top_path)},
        {"metric": spec.column, "artifact": "model_seed_top_correlations", "path": relative(model_seed_top_path)},
        {"metric": spec.column, "artifact": "paired_delta_seed_top_correlations", "path": relative(delta_seed_top_path)},
        {"metric": spec.column, "artifact": "model_seed_rank_table", "path": relative(rank_long_path)},
        {"metric": spec.column, "artifact": "model_seed_rank_wide", "path": relative(rank_wide_path)},
        {"metric": spec.column, "artifact": "metadata", "path": relative(metadata_path)},
    ]
    if wrote_model1_heatmap:
        rows.append({"metric": spec.column, "artifact": "model1_seed_spearman_heatmap", "path": relative(model1_heatmap_path)})
    if wrote_model2_heatmap:
        rows.append({"metric": spec.column, "artifact": "model2_seed_spearman_heatmap", "path": relative(model2_heatmap_path)})
    for target, path in scatter_paths.items():
        rows.append({"metric": spec.column, "artifact": f"{target}_top_scatter", "path": path})
    return rows, rank_long, model_seed_top


def write_root_outputs(
    manifest_rows: list[dict[str, str]],
    top_rows: list[pd.DataFrame],
    rank_rows: list[pd.DataFrame],
    primary: pd.DataFrame,
    output_dir: Path,
    args: argparse.Namespace,
) -> None:
    tables_dir = output_dir / "tables"
    metadata_dir = output_dir / "metadata"
    tables_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    manifest = pd.DataFrame(manifest_rows)
    manifest_path = tables_dir / "primary_metric_attribute_correlation_manifest.csv"
    manifest.to_csv(manifest_path, index=False)

    if top_rows:
        all_top = pd.concat(top_rows, ignore_index=True)
    else:
        all_top = pd.DataFrame()
    all_top_path = tables_dir / "primary_metric_attribute_top_correlations.csv"
    all_top.to_csv(all_top_path, index=False)

    if rank_rows:
        all_ranks = pd.concat(rank_rows, ignore_index=True)
    else:
        all_ranks = pd.DataFrame()
    all_ranks_path = tables_dir / "primary_metric_model_seed_rank_table.csv"
    all_ranks.to_csv(all_ranks_path, index=False)

    primary_path = tables_dir / "primary_epochs_used.csv"
    primary.to_csv(primary_path, index=False)

    metadata = {
        "analysis": "subset300 primary metric vs core static/spatial basin attribute correlations",
        "split": args.split,
        "seeds": args.seeds,
        "metrics_input": relative(resolve(args.metrics)),
        "primary_summary_input": relative(resolve(args.primary_summary)),
        "static_attributes_input": relative(resolve(args.static_attributes)),
        "drbc_attributes_input": relative(resolve(args.drbc_attributes)),
        "basin_shapefile_input": relative(resolve(args.basin_shapefile)),
        "output_dir": relative(output_dir),
        "correlation_method": "Spearman rank correlation, Benjamini-Hochberg FDR within each metric table.",
        "included_sources": [
            "NeuralHydrology static_attributes.csv core basin attributes",
            "DRBC selected basin table gauge coordinates",
            "CAMELSH basin polygon area centroids computed in EPSG:5070 then transformed to EPSG:4326",
        ],
        "excluded_from_primary_pass": {
            "prec_flood_usgs_noaa_reference_variables": (
                "Not included in this core-static pass. These are derived event/reference products "
                "or external reference enrichments and should be analyzed as supplementary "
                "sensitivity/provenance-aware features, not mixed into the first primary static-correlation table."
            )
        },
        "manifest": relative(manifest_path),
        "top_correlations": relative(all_top_path),
        "model_seed_rank_table": relative(all_ranks_path),
        "primary_epochs_used": relative(primary_path),
    }
    metadata_path = metadata_dir / "primary_metric_attribute_correlation_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    args.metrics = resolve(args.metrics)
    args.primary_summary = resolve(args.primary_summary)
    args.static_attributes = resolve(args.static_attributes)
    args.drbc_attributes = resolve(args.drbc_attributes)
    args.basin_shapefile = resolve(args.basin_shapefile)
    args.output_dir = resolve(args.output_dir)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    metric_rows, primary = read_primary_metric_rows(args.metrics, args.primary_summary, args.split, args.seeds)
    attributes = read_attributes(args.static_attributes, args.drbc_attributes, args.basin_shapefile)

    manifest_rows: list[dict[str, str]] = []
    top_rows: list[pd.DataFrame] = []
    rank_rows: list[pd.DataFrame] = []
    for spec in METRIC_SPECS:
        table, aggregate_targets, seed_targets = build_metric_table(metric_rows, attributes, spec, args.seeds)
        features = [feature for feature in CORE_FEATURES if feature in table.columns]
        aggregate_corr = spearman_correlations(table, spec.column, aggregate_targets, features, "seed_median")
        seed_corr = spearman_correlations(table, spec.column, seed_targets, features, "seed_level")
        metric_dir = args.output_dir / spec.folder
        metric_manifest_rows, rank_long, model_seed_top = write_metric_outputs(
            table, aggregate_corr, seed_corr, spec, metric_dir, args
        )
        manifest_rows.extend(metric_manifest_rows)
        if not rank_long.empty:
            rank_rows.append(rank_long)
        if not model_seed_top.empty:
            model_seed_top = model_seed_top.copy()
            model_seed_top["metric_folder"] = spec.folder
            top_rows.append(model_seed_top)

    write_root_outputs(manifest_rows, top_rows, rank_rows, primary, args.output_dir, args)
    print(f"Wrote primary metric-attribute correlation outputs to {args.output_dir}")


if __name__ == "__main__":
    main()
