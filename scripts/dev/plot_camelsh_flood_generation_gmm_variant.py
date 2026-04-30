#!/usr/bin/env python3
# /// script
# dependencies = [
#   "geopandas>=0.14",
#   "matplotlib>=3.8",
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "pyogrio>=0.7",
#   "scikit-learn>=1.4",
#   "xarray>=2024.1",
# ]
# ///

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.metrics import (
    calinski_harabasz_score,
    davies_bouldin_score,
    normalized_mutual_info_score,
    silhouette_score,
)
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import RobustScaler

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import camelsh_flood_analysis_utils as fu


DEFAULT_EVENT_RESPONSE_CSV = Path("output/basin/all/analysis/event_response/tables/event_response_table.csv")
DEFAULT_RULE_TYPING_CSV = Path("output/basin/all/analysis/flood_generation/tables/flood_generation_event_types.csv")
DEFAULT_RULE_BASIN_CSV = Path("output/basin/all/analysis/flood_generation/tables/flood_generation_basin_summary.csv")
DEFAULT_EVENT_BASIN_CSV = Path("output/basin/all/analysis/event_response/tables/event_response_basin_summary.csv")
DEFAULT_BASIN_SHAPEFILE = Path("basins/CAMELSH_data/shapefiles/CAMELSH_shapefile.shp")
DEFAULT_STATE_SHAPEFILE = Path("basins/us_boundaries/tl_2024_us_state/tl_2024_us_state.shp")
DEFAULT_OUTPUT_DIR = Path("output/basin/all/archive/event_regime_variants/gaussian_clean_process_8_k3")

FEATURE_SETS = {
    "clean_process_8": [
        "recent_1d_ratio",
        "recent_3d_ratio",
        "antecedent_7d_ratio",
        "antecedent_30d_ratio",
        "snowmelt_ratio",
        "event_mean_temp",
        "rising_time_hours",
        "event_duration_hours",
    ],
    "hydromet_only_7": [
        "recent_1d_ratio",
        "recent_3d_ratio",
        "antecedent_7d_ratio",
        "antecedent_30d_ratio",
        "snowmelt_ratio",
        "snowmelt_fraction",
        "event_mean_temp",
    ],
    "compact_process_6": [
        "recent_1d_ratio",
        "recent_3d_ratio",
        "antecedent_7d_ratio",
        "antecedent_30d_ratio",
        "snowmelt_ratio",
        "rising_time_hours",
    ],
}
LOG1P_FEATURES = {
    "recent_1d_ratio",
    "recent_3d_ratio",
    "antecedent_7d_ratio",
    "antecedent_30d_ratio",
    "snowmelt_ratio",
    "rising_time_hours",
    "event_duration_hours",
}
SHAPE_FEATURES = {"rising_time_hours", "event_duration_hours"}

CLUSTER_COLORS = {
    0: "#3f6fb5",
    1: "#8f5ca8",
    2: "#d78a2a",
    3: "#4b8f68",
    4: "#8a6d3b",
}
RULE_COLORS = {
    "recent_precipitation": "#d78a2a",
    "antecedent_precipitation": "#3f6fb5",
    "snowmelt_or_rain_on_snow": "#8f5ca8",
    "uncertain_high_flow_candidate": "#777777",
    "mixture": "#b8b8b8",
}
HUC02_NAMES = {
    "01": "New England",
    "02": "Mid-Atlantic",
    "03": "South Atlantic-Gulf",
    "04": "Great Lakes",
    "05": "Ohio",
    "06": "Tennessee",
    "07": "Upper Mississippi",
    "08": "Lower Mississippi",
    "09": "Souris-Red-Rainy",
    "10U": "Upper Missouri",
    "10L": "Lower Missouri",
    "11": "Arkansas-White-Red",
    "12": "Texas-Gulf",
    "13": "Rio Grande",
    "14": "Upper Colorado",
    "15": "Lower Colorado",
    "16": "Great Basin",
    "17": "Pacific Northwest",
    "18": "California",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fit a Gaussian mixture flood-regime variant and plot basin-level CAMELSH diagnostics."
    )
    parser.add_argument("--event-response-csv", type=Path, default=DEFAULT_EVENT_RESPONSE_CSV)
    parser.add_argument("--rule-typing-csv", type=Path, default=DEFAULT_RULE_TYPING_CSV)
    parser.add_argument("--rule-basin-csv", type=Path, default=DEFAULT_RULE_BASIN_CSV)
    parser.add_argument("--event-basin-csv", type=Path, default=DEFAULT_EVENT_BASIN_CSV)
    parser.add_argument("--basin-shapefile", type=Path, default=DEFAULT_BASIN_SHAPEFILE)
    parser.add_argument("--state-shapefile", type=Path, default=DEFAULT_STATE_SHAPEFILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--feature-set", choices=sorted(FEATURE_SETS), default="clean_process_8")
    parser.add_argument("--n-components", type=int, default=3)
    parser.add_argument("--covariance-type", choices=["diag", "full", "tied", "spherical"], default="diag")
    parser.add_argument("--random-state", type=int, default=111)
    parser.add_argument("--fit-sample-size", type=int, default=120000)
    parser.add_argument("--metric-sample-size", type=int, default=30000)
    parser.add_argument("--scatter-sample-size", type=int, default=60000)
    parser.add_argument("--dominance-threshold", type=float, default=0.6)
    parser.add_argument("--shape-winsor-quantile", type=float, default=0.995)
    return parser.parse_args()


def normalize_huc02(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    if text.isdigit():
        return text.zfill(2)
    return text.upper()


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer, np.floating)):
        if pd.isna(value):
            return None
        return value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if pd.isna(value):
        return None
    return value


def numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce")


def safe_ratio(df: pd.DataFrame, numerator: str, denominator: str) -> pd.Series:
    num = numeric_series(df, numerator)
    den = numeric_series(df, denominator)
    ratio = num / den
    ratio = ratio.where(den > 0)
    return ratio.replace([np.inf, -np.inf], np.nan)


def median_or_zero(values: pd.Series) -> float:
    clean = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return 0.0
    return float(clean.median())


def read_events(path: Path) -> pd.DataFrame:
    events = pd.read_csv(path, dtype={"gauge_id": str, "huc02": str})
    if events.empty:
        raise SystemExit(f"Event response CSV is empty: {path}")
    events["gauge_id"] = events["gauge_id"].map(fu.normalize_gauge_id)
    events["huc02"] = events["huc02"].map(normalize_huc02)
    return events


def read_rules(path: Path) -> pd.DataFrame:
    cols = ["gauge_id", "event_id", "flood_generation_type"]
    rules = pd.read_csv(path, usecols=cols, dtype={"gauge_id": str})
    rules["gauge_id"] = rules["gauge_id"].map(fu.normalize_gauge_id)
    return rules


def build_feature_table(events: pd.DataFrame) -> pd.DataFrame:
    features = pd.DataFrame(index=events.index)
    features["recent_1d_ratio"] = safe_ratio(events, "recent_rain_24h", "basin_rain_1d_p90")
    features["recent_3d_ratio"] = safe_ratio(events, "recent_rain_72h", "basin_rain_3d_p90")
    features["antecedent_7d_ratio"] = safe_ratio(events, "antecedent_rain_7d", "basin_rain_7d_p90")
    features["antecedent_30d_ratio"] = safe_ratio(events, "antecedent_rain_30d", "basin_rain_30d_p90")
    features["snowmelt_ratio"] = safe_ratio(events, "degree_day_snowmelt_7d", "basin_snowmelt_7d_p90")
    snow_valid = (
        (numeric_series(events, "basin_snowmelt_valid_window_count") >= fu.SNOWMELT_MIN_VALID_WINDOW_COUNT)
        & (numeric_series(events, "basin_snowmelt_7d_p90") > 0)
    )
    features.loc[~snow_valid, "snowmelt_ratio"] = 0.0
    features["snowmelt_fraction"] = numeric_series(events, "degree_day_snowmelt_fraction_7d")
    features["event_mean_temp"] = numeric_series(events, "event_mean_temp")
    features["rising_time_hours"] = numeric_series(events, "rising_time_hours")
    features["event_duration_hours"] = numeric_series(events, "event_duration_hours")

    for col in [
        "recent_1d_ratio",
        "recent_3d_ratio",
        "antecedent_7d_ratio",
        "antecedent_30d_ratio",
        "snowmelt_ratio",
    ]:
        features[col] = features[col].clip(lower=0).fillna(0.0)
    features["snowmelt_fraction"] = features["snowmelt_fraction"].clip(lower=0, upper=1).fillna(0.0)
    for col in ["rising_time_hours", "event_duration_hours"]:
        features[col] = features[col].clip(lower=0)
        features[col] = features[col].fillna(median_or_zero(features[col]))
    features["event_mean_temp"] = features["event_mean_temp"].fillna(median_or_zero(features["event_mean_temp"]))
    return features.astype(float)


def transform_features(
    features: pd.DataFrame,
    columns: list[str],
    shape_winsor_quantile: float,
) -> tuple[pd.DataFrame, np.ndarray]:
    transformed = features[columns].copy()
    for col in columns:
        transformed[col] = pd.to_numeric(transformed[col], errors="coerce").fillna(0.0)
        if col in SHAPE_FEATURES:
            cap = float(transformed[col].quantile(shape_winsor_quantile))
            transformed[col] = transformed[col].clip(lower=0, upper=cap)
        elif col in LOG1P_FEATURES:
            transformed[col] = transformed[col].clip(lower=0)
    for col in set(columns) & LOG1P_FEATURES:
        transformed[col] = np.log1p(transformed[col])
    matrix = RobustScaler().fit_transform(transformed)
    return transformed, matrix


def fit_gmm(args: argparse.Namespace, matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray, GaussianMixture]:
    rng = np.random.default_rng(args.random_state)
    fit_idx = rng.choice(
        len(matrix),
        size=min(args.fit_sample_size, len(matrix)),
        replace=False,
    )
    model = GaussianMixture(
        n_components=args.n_components,
        covariance_type=args.covariance_type,
        n_init=3,
        random_state=args.random_state,
        reg_covar=1e-5,
    )
    model.fit(matrix[fit_idx])
    posterior = model.predict_proba(matrix)
    return posterior.argmax(axis=1), posterior.max(axis=1), model


def cluster_profiles(features: pd.DataFrame, labels: np.ndarray, columns: list[str]) -> pd.DataFrame:
    work = features[columns].copy()
    work["cluster"] = labels
    rows: list[dict[str, Any]] = []
    for cluster, group in work.groupby("cluster", sort=True):
        row: dict[str, Any] = {
            "cluster": int(cluster),
            "event_count": int(len(group)),
            "event_share": float(len(group) / len(work)),
        }
        for col in columns:
            values = pd.to_numeric(group[col], errors="coerce")
            row[f"{col}_median"] = float(values.median(skipna=True))
            row[f"{col}_p90"] = float(values.quantile(0.90))
        rows.append(row)
    profiles = pd.DataFrame(rows)
    profiles["cluster_name"] = profiles.apply(interpret_cluster, axis=1)
    return profiles


def interpret_cluster(row: pd.Series) -> str:
    recent = max(float(row.get("recent_1d_ratio_median", 0.0)), float(row.get("recent_3d_ratio_median", 0.0)))
    antecedent = max(
        float(row.get("antecedent_7d_ratio_median", 0.0)),
        float(row.get("antecedent_30d_ratio_median", 0.0)),
    )
    snow = max(float(row.get("snowmelt_ratio_median", 0.0)), float(row.get("snowmelt_ratio_p90", 0.0)) * 0.7)
    temp = float(row.get("event_mean_temp_median", 99.0))
    duration = float(row.get("event_duration_hours_median", 0.0))
    rising = float(row.get("rising_time_hours_median", 0.0))
    if snow >= 0.5 and temp <= 8.0:
        return "Cold snow-proxy mix"
    if antecedent >= 0.85 and (duration >= 24.0 or rising >= 8.0):
        return "Long wet rainfall"
    if recent >= 1.0 and duration <= 12.0:
        return "Short rainfall / weak-driver"
    if recent >= 1.0:
        return "Rainfall-dominant mix"
    return "Mixed / weak-driver"


def label_lookup(profiles: pd.DataFrame) -> dict[int, str]:
    counts = profiles["cluster_name"].value_counts()
    lookup: dict[int, str] = {}
    for row in profiles.itertuples(index=False):
        name = str(row.cluster_name)
        if counts[name] > 1:
            name = f"{name} (c{int(row.cluster)})"
        lookup[int(row.cluster)] = name
    return lookup


def basin_cluster_shares(keys: pd.DataFrame, labels: np.ndarray, names: dict[int, str]) -> pd.DataFrame:
    work = keys[["gauge_id"]].copy()
    work["cluster"] = labels
    shares = pd.crosstab(work["gauge_id"], work["cluster"], normalize="index")
    for cluster in sorted(names):
        if cluster not in shares.columns:
            shares[cluster] = 0.0
    shares = shares[sorted(names)]
    shares.columns = [f"cluster_{col}_share" for col in shares.columns]
    shares["event_count"] = work.groupby("gauge_id").size()
    share_cols = [f"cluster_{col}_share" for col in sorted(names)]
    sorted_shares = np.sort(shares[share_cols].to_numpy(), axis=1)[:, ::-1]
    top_index = shares[share_cols].to_numpy().argmax(axis=1)
    clusters = sorted(names)
    shares["top1_cluster"] = [clusters[index] for index in top_index]
    shares["top1_cluster_name"] = shares["top1_cluster"].map(names)
    shares["top1_share"] = sorted_shares[:, 0]
    shares["top2_share"] = sorted_shares[:, : min(2, len(share_cols))].sum(axis=1)
    entropy = []
    for row in shares[share_cols].to_numpy():
        positive = row[row > 0]
        entropy.append(float(-(positive * np.log(positive)).sum() / np.log(len(row))) if len(row) > 1 else 0.0)
    shares["cluster_entropy"] = entropy
    return shares.reset_index()


def event_labels(keys: pd.DataFrame, rules: pd.DataFrame, labels: np.ndarray, posterior_max: np.ndarray, names: dict[int, str]) -> pd.DataFrame:
    out = keys.merge(rules, on=["gauge_id", "event_id"], how="left")
    out["gmm_cluster"] = labels
    out["gmm_cluster_name"] = out["gmm_cluster"].map(names)
    out["gmm_posterior_max"] = posterior_max
    return out


def sampled_metrics(matrix: np.ndarray, labels: np.ndarray, sample_size: int, random_state: int) -> dict[str, float]:
    rng = np.random.default_rng(random_state)
    idx = rng.choice(len(matrix), size=min(sample_size, len(matrix)), replace=False)
    sampled_labels = labels[idx]
    if len(np.unique(sampled_labels)) < 2:
        return {"silhouette_sample": np.nan, "davies_bouldin_sample": np.nan, "calinski_sample": np.nan}
    sampled = matrix[idx]
    return {
        "silhouette_sample": float(silhouette_score(sampled, sampled_labels)),
        "davies_bouldin_sample": float(davies_bouldin_score(sampled, sampled_labels)),
        "calinski_sample": float(calinski_harabasz_score(sampled, sampled_labels)),
    }


def savefig(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=220, bbox_inches="tight")
    plt.close()


def plot_pca(matrix: np.ndarray, labels: pd.Series, colors: dict[str, str], path: Path, title: str, sample_size: int, random_state: int) -> list[float]:
    pca = PCA(n_components=2, random_state=random_state)
    coords = pca.fit_transform(matrix)
    rng = np.random.default_rng(random_state)
    idx = rng.choice(len(matrix), size=min(sample_size, len(matrix)), replace=False)
    sampled_labels = labels.iloc[idx].astype(str)
    fig, ax = plt.subplots(figsize=(8.5, 6.5))
    for label in sorted(sampled_labels.unique()):
        mask = sampled_labels.eq(label).to_numpy()
        ax.scatter(
            coords[idx][mask, 0],
            coords[idx][mask, 1],
            s=5,
            alpha=0.35,
            c=colors.get(label, "#777777"),
            label=label,
            linewidths=0,
        )
    ax.set_title(title)
    ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0] * 100:.1f}% var.)")
    ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1] * 100:.1f}% var.)")
    ax.legend(markerscale=2.5, frameon=False, loc="best")
    ax.grid(alpha=0.18)
    savefig(path)
    return pca.explained_variance_ratio_.tolist()


def plot_rule_heatmap(events: pd.DataFrame, path: Path) -> None:
    counts = pd.crosstab(events["gmm_cluster_name"], events["flood_generation_type"])
    shares = counts.div(counts.sum(axis=1), axis=0).fillna(0.0)
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    image = ax.imshow(shares.to_numpy(), cmap="YlGnBu", vmin=0, vmax=max(0.01, float(shares.to_numpy().max())))
    ax.set_xticks(range(len(shares.columns)), labels=shares.columns, rotation=30, ha="right")
    ax.set_yticks(range(len(shares.index)), labels=shares.index)
    for i in range(shares.shape[0]):
        for j in range(shares.shape[1]):
            ax.text(j, i, f"{shares.iloc[i, j] * 100:.1f}%", ha="center", va="center", fontsize=8)
    ax.set_title("Rule Type Share Within Gaussian Mixture Clusters")
    fig.colorbar(image, ax=ax, fraction=0.035, pad=0.02)
    savefig(path)


def plot_feature_profile(profiles: pd.DataFrame, columns: list[str], path: Path) -> None:
    med = profiles.set_index("cluster_name")[[f"{col}_median" for col in columns]]
    med.columns = columns
    scaled = (med - med.mean(axis=0)) / med.std(axis=0).replace(0, np.nan)
    scaled = scaled.fillna(0.0)
    fig, ax = plt.subplots(figsize=(max(8.5, len(columns) * 0.75), 3.8))
    image = ax.imshow(scaled.to_numpy(), cmap="RdBu_r", vmin=-2.0, vmax=2.0, aspect="auto")
    ax.set_xticks(range(len(columns)), labels=columns, rotation=35, ha="right")
    ax.set_yticks(range(len(scaled.index)), labels=scaled.index)
    ax.set_title("Gaussian Cluster Median Feature Profile")
    fig.colorbar(image, ax=ax, fraction=0.035, pad=0.02, label="within-feature z-score")
    savefig(path)


def plot_basin_share_histogram(basin: pd.DataFrame, path: Path, threshold: float) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.8))
    bins = np.linspace(0, 1, 26)
    ax.hist(basin["top1_share"], bins=bins, alpha=0.72, color="#506d84", label="Top-1 share")
    ax.hist(basin["top2_share"], bins=bins, alpha=0.48, color="#d78a2a", label="Top-2 share")
    ax.axvline(threshold, color="#222222", lw=1, ls="--", label=f"Dominance threshold {threshold:.1f}")
    ax.axvline(0.8, color="#777777", lw=1, ls=":", label="Top-2 0.8")
    ax.set_xlabel("Basin event-share")
    ax.set_ylabel("Basin count")
    ax.set_title("Basin Composition Under Gaussian Mixture Clustering")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.18)
    savefig(path)


def plot_monthly_composition(events: pd.DataFrame, names: dict[int, str], path: Path) -> None:
    monthly = pd.crosstab(events["peak_month"], events["gmm_cluster"], normalize="index")
    clusters = sorted(names)
    monthly = monthly.reindex(index=range(1, 13), columns=clusters, fill_value=0.0)
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    bottom = np.zeros(len(monthly))
    for cluster in clusters:
        values = monthly[cluster].to_numpy()
        ax.bar(
            monthly.index,
            values,
            bottom=bottom,
            color=CLUSTER_COLORS.get(cluster, "#777777"),
            label=names[cluster],
        )
        bottom += values
    ax.set_xticks(range(1, 13))
    ax.set_ylim(0, 1)
    ax.set_xlabel("Peak month")
    ax.set_ylabel("Event share")
    ax.set_title("Seasonal Composition of Gaussian Mixture Clusters")
    ax.legend(frameon=False, loc="upper right")
    ax.grid(axis="y", alpha=0.16)
    savefig(path)


def read_state_layer(path: Path) -> gpd.GeoDataFrame:
    states = gpd.read_file(path)
    states = states[~states["STUSPS"].isin(["AK", "HI", "PR", "GU", "VI", "MP", "AS"])].copy()
    return states.to_crs("EPSG:4326")


def read_basin_layer(path: Path) -> gpd.GeoDataFrame:
    basins = gpd.read_file(path)
    basins["gauge_id"] = basins["GAGE_ID"].map(fu.normalize_gauge_id)
    if basins.crs is None:
        basins = basins.set_crs("EPSG:4326")
    else:
        basins = basins.to_crs("EPSG:4326")
    return basins[["gauge_id", "geometry"]]


def legend_handles(colors: dict[Any, str], labels: dict[int, str] | None = None) -> list[mpatches.Patch]:
    if labels is None:
        return [mpatches.Patch(facecolor=color, label=str(label)) for label, color in colors.items()]
    return [mpatches.Patch(facecolor=colors[key], label=labels[key]) for key in sorted(labels)]


def add_basin_metadata(basin: pd.DataFrame, event_basin_csv: Path, rule_basin_csv: Path) -> pd.DataFrame:
    meta = pd.read_csv(event_basin_csv, dtype={"gauge_id": str})
    meta["gauge_id"] = meta["gauge_id"].map(fu.normalize_gauge_id)
    keep = [
        col
        for col in ["gauge_id", "gauge_name", "state", "huc02", "drain_sqkm_attr", "event_count"]
        if col in meta.columns
    ]
    out = basin.merge(meta[keep], on="gauge_id", how="left", suffixes=("", "_event"))
    rule = pd.read_csv(rule_basin_csv, dtype={"gauge_id": str})
    rule["gauge_id"] = rule["gauge_id"].map(fu.normalize_gauge_id)
    out = out.merge(
        rule[["gauge_id", "dominant_flood_generation_type", "dominant_type_share"]],
        on="gauge_id",
        how="left",
    )
    out["huc02"] = out["huc02"].map(normalize_huc02)
    return out


def plot_gmm_map(states: gpd.GeoDataFrame, basins: gpd.GeoDataFrame, names: dict[int, str], path: Path, threshold: float) -> None:
    fig, ax = plt.subplots(figsize=(13, 7.5))
    states.plot(ax=ax, facecolor="#f6f6f3", edgecolor="#c8c8c8", linewidth=0.45)
    for cluster, name in names.items():
        strong = basins[(basins["top1_cluster"] == cluster) & (basins["top1_share"] >= threshold)]
        weak = basins[(basins["top1_cluster"] == cluster) & (basins["top1_share"] < threshold)]
        if not weak.empty:
            weak.plot(ax=ax, color=CLUSTER_COLORS.get(cluster, "#777777"), alpha=0.28, linewidth=0)
        if not strong.empty:
            strong.plot(ax=ax, color=CLUSTER_COLORS.get(cluster, "#777777"), alpha=0.78, linewidth=0)
    ax.set_xlim(-125.5, -66.0)
    ax.set_ylim(24.0, 50.0)
    ax.set_axis_off()
    ax.set_title("CAMELSH Basins by Gaussian Mixture Event-Regime Composition", pad=16)
    handles = legend_handles(CLUSTER_COLORS, names)
    handles.append(mpatches.Patch(facecolor="#888888", alpha=0.28, label=f"Mixed top-1 < {threshold:.1f}"))
    ax.legend(handles=handles, frameon=True, loc="lower left", fontsize=9)
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=240, bbox_inches="tight")
    plt.close()


def plot_rule_map(states: gpd.GeoDataFrame, basins: gpd.GeoDataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(13, 7.5))
    states.plot(ax=ax, facecolor="#f6f6f3", edgecolor="#c8c8c8", linewidth=0.45)
    for label, color in RULE_COLORS.items():
        subset = basins[basins["dominant_flood_generation_type"] == label]
        if not subset.empty:
            subset.plot(ax=ax, color=color, alpha=0.76, linewidth=0)
    ax.set_xlim(-125.5, -66.0)
    ax.set_ylim(24.0, 50.0)
    ax.set_axis_off()
    ax.set_title("Rule-Based Dominant Flood-Generation Type", pad=16)
    ax.legend(handles=legend_handles(RULE_COLORS), frameon=True, loc="lower left", fontsize=8)
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=240, bbox_inches="tight")
    plt.close()


def plot_huc02_summary(basin: pd.DataFrame, names: dict[int, str], path: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for huc02, group in basin.groupby("huc02", dropna=False):
        row: dict[str, Any] = {
            "huc02": huc02,
            "huc02_name": HUC02_NAMES.get(str(huc02), ""),
            "basin_count": int(len(group)),
            "top1_ge_0_6_share": float((group["top1_share"] >= 0.6).mean()),
            "top2_ge_0_8_share": float((group["top2_share"] >= 0.8).mean()),
        }
        for cluster, name in names.items():
            row[f"{name}_share"] = float((group["top1_cluster"] == cluster).mean())
        rows.append(row)
    summary = pd.DataFrame(rows).sort_values("huc02")

    plot = summary.set_index("huc02")[[f"{name}_share" for name in names.values()]]
    fig, ax = plt.subplots(figsize=(11, 5.2))
    bottom = np.zeros(len(plot))
    for cluster, name in names.items():
        col = f"{name}_share"
        ax.bar(
            plot.index,
            plot[col].to_numpy(),
            bottom=bottom,
            color=CLUSTER_COLORS.get(cluster, "#777777"),
            label=name,
        )
        bottom += plot[col].to_numpy()
    ax.set_ylim(0, 1)
    ax.set_xlabel("HUC02")
    ax.set_ylabel("Basin share by top Gaussian component")
    ax.set_title("Regional Basin Composition by Gaussian Mixture Cluster")
    ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    ax.grid(axis="y", alpha=0.16)
    savefig(path)
    return summary


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = args.output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    columns = FEATURE_SETS[args.feature_set]
    events = read_events(args.event_response_csv)
    rules = read_rules(args.rule_typing_csv)
    features = build_feature_table(events)
    transformed, matrix = transform_features(features, columns, args.shape_winsor_quantile)
    labels, posterior_max, model = fit_gmm(args, matrix)
    profiles = cluster_profiles(features, labels, columns)
    names = label_lookup(profiles)

    keys = events[["gauge_id", "event_id", "peak_month", "water_year", "huc02"]].copy()
    labels_table = event_labels(keys, rules, labels, posterior_max, names)
    basin = basin_cluster_shares(keys, labels, names)
    basin = add_basin_metadata(basin, args.event_basin_csv, args.rule_basin_csv)

    labels_table.to_csv(args.output_dir / "gaussian_selected_event_labels.csv", index=False)
    basin.to_csv(args.output_dir / "gaussian_selected_basin_map_labels.csv", index=False)
    profiles.to_csv(args.output_dir / "gaussian_selected_cluster_feature_profiles.csv", index=False)
    transformed.sample(n=min(5000, len(transformed)), random_state=args.random_state).to_csv(
        args.output_dir / "gaussian_transformed_sample.csv",
        index=False,
    )

    cluster_name_colors = {names[key]: CLUSTER_COLORS.get(key, "#777777") for key in names}
    pca_var = plot_pca(
        matrix,
        labels_table["gmm_cluster_name"],
        cluster_name_colors,
        figures_dir / "event_descriptor_pca_by_gaussian_cluster.png",
        "Event Descriptor PCA by Gaussian Mixture Cluster",
        args.scatter_sample_size,
        args.random_state,
    )
    plot_rule_heatmap(labels_table, figures_dir / "rule_vs_gaussian_cluster_heatmap.png")
    plot_feature_profile(profiles, columns, figures_dir / "gaussian_cluster_feature_profile_heatmap.png")
    plot_basin_share_histogram(basin, figures_dir / "gaussian_basin_top1_top2_share_histogram.png", args.dominance_threshold)
    plot_monthly_composition(labels_table, names, figures_dir / "monthly_gaussian_cluster_composition.png")

    states = read_state_layer(args.state_shapefile)
    shapes = read_basin_layer(args.basin_shapefile)
    mapped = shapes.merge(basin, on="gauge_id", how="inner")
    plot_gmm_map(states, mapped, names, figures_dir / "us_map_gaussian_dominant_basins.png", args.dominance_threshold)
    plot_rule_map(states, mapped, figures_dir / "us_map_rule_based_for_gaussian_comparison.png")
    huc02_summary = plot_huc02_summary(
        basin,
        names,
        figures_dir / "huc02_gaussian_basin_composition.png",
    )
    huc02_summary.to_csv(args.output_dir / "gaussian_selected_huc02_regional_summary.csv", index=False)

    metrics = sampled_metrics(matrix, labels, args.metric_sample_size, args.random_state)
    crosstab = pd.crosstab(labels_table["gmm_cluster_name"], labels_table["flood_generation_type"], normalize="index")
    summary = {
        "variant": f"gmm_{args.covariance_type}__{args.feature_set}__k{args.n_components}",
        "event_count": int(len(events)),
        "basin_count": int(basin["gauge_id"].nunique()),
        "feature_columns": columns,
        "cluster_event_counts": labels_table["gmm_cluster_name"].value_counts().to_dict(),
        "cluster_profiles_csv": str(args.output_dir / "gaussian_selected_cluster_feature_profiles.csv"),
        "basin_top1_ge_0_6_share": float((basin["top1_share"] >= args.dominance_threshold).mean()),
        "basin_top2_ge_0_8_share": float((basin["top2_share"] >= 0.8).mean()),
        "posterior_max_mean": float(labels_table["gmm_posterior_max"].mean()),
        "posterior_lt_0_7_share": float((labels_table["gmm_posterior_max"] < 0.7).mean()),
        "rule_normalized_mutual_info": float(
            normalized_mutual_info_score(labels_table["flood_generation_type"], labels_table["gmm_cluster"])
        ),
        "pca_explained_variance_ratio": pca_var,
        "sampled_metrics": metrics,
        "gmm_converged": bool(model.converged_),
        "gmm_n_iter": int(model.n_iter_),
        "rule_share_within_gaussian_cluster": crosstab.round(4).to_dict(orient="index"),
        "figures": sorted(str(path) for path in figures_dir.glob("*.png")),
    }
    (args.output_dir / "gaussian_selected_summary.json").write_text(
        json.dumps(json_safe(summary), indent=2),
        encoding="utf-8",
    )

    print(f"Wrote Gaussian event labels: {args.output_dir / 'gaussian_selected_event_labels.csv'}")
    print(f"Wrote Gaussian basin labels: {args.output_dir / 'gaussian_selected_basin_map_labels.csv'}")
    print(f"Wrote figures: {figures_dir}")
    print(f"Wrote summary: {args.output_dir / 'gaussian_selected_summary.json'}")


if __name__ == "__main__":
    main()
