#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.8",
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "pyarrow>=15.0",
#   "scikit-learn>=1.4",
# ]
# ///

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import RobustScaler


DEFAULT_ALL_DIR = Path("output/basin/all")
DEFAULT_ANALYSIS_DIR = DEFAULT_ALL_DIR / "analysis"
DEFAULT_EVENT_RESPONSE_CSV = DEFAULT_ANALYSIS_DIR / "event_response/tables/event_response_table.csv"
DEFAULT_RULE_TYPING_CSV = DEFAULT_ANALYSIS_DIR / "flood_generation/tables/flood_generation_event_types.csv"
DEFAULT_RULE_BASIN_CSV = DEFAULT_ANALYSIS_DIR / "flood_generation/tables/flood_generation_basin_summary.csv"
DEFAULT_DRBC_EVENT_BASIN_CSV = Path("output/basin/drbc/analysis/event_response/tables/event_response_basin_summary.csv")
DEFAULT_EXPERIMENT_DIR = DEFAULT_ALL_DIR / "archive/event_regime_variants"
DEFAULT_OUTPUT_DIR = DEFAULT_ANALYSIS_DIR / "event_regime/figures"
DEFAULT_TABLE_DIR = DEFAULT_ANALYSIS_DIR / "event_regime/tables"
DEFAULT_METADATA_DIR = DEFAULT_ANALYSIS_DIR / "event_regime/metadata"
DEFAULT_VARIANT_FIGURE_DIR = DEFAULT_ALL_DIR / "archive/event_regime_variants/figures"

FEATURE_COLUMNS = [
    "recent_1d_ratio",
    "recent_3d_ratio",
    "antecedent_7d_ratio",
    "antecedent_30d_ratio",
    "snowmelt_ratio",
    "snowmelt_fraction",
    "event_mean_temp",
]
LOG1P_FEATURES = {
    "recent_1d_ratio",
    "recent_3d_ratio",
    "antecedent_7d_ratio",
    "antecedent_30d_ratio",
    "snowmelt_ratio",
}
SNOWMELT_MIN_VALID_WINDOW_COUNT = 10

CLUSTER_NAMES = {
    0: "Antecedent / multi-day rain",
    1: "Weak-driver / snow-influenced",
    2: "Recent rainfall",
}
CLUSTER_COLORS = {
    0: "#3f6fb5",
    1: "#8f5ca8",
    2: "#d78a2a",
}
RULE_COLORS = {
    "recent_precipitation": "#d78a2a",
    "antecedent_precipitation": "#3f6fb5",
    "snowmelt_or_rain_on_snow": "#8f5ca8",
    "uncertain_high_flow_candidate": "#777777",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot exploratory CAMELSH flood-generation ML variant diagnostics."
    )
    parser.add_argument("--event-response-csv", type=Path, default=DEFAULT_EVENT_RESPONSE_CSV)
    parser.add_argument("--rule-typing-csv", type=Path, default=DEFAULT_RULE_TYPING_CSV)
    parser.add_argument("--rule-basin-csv", type=Path, default=DEFAULT_RULE_BASIN_CSV)
    parser.add_argument("--drbc-event-basin-csv", type=Path, default=DEFAULT_DRBC_EVENT_BASIN_CSV)
    parser.add_argument("--experiment-dir", type=Path, default=DEFAULT_EXPERIMENT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--table-dir", type=Path, default=DEFAULT_TABLE_DIR)
    parser.add_argument("--metadata-dir", type=Path, default=DEFAULT_METADATA_DIR)
    parser.add_argument("--variant-figure-dir", type=Path, default=DEFAULT_VARIANT_FIGURE_DIR)
    parser.add_argument("--random-state", type=int, default=111)
    parser.add_argument("--n-clusters", type=int, default=3)
    parser.add_argument("--scatter-sample-size", type=int, default=60000)
    return parser.parse_args()


def normalize_gauge_id(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(8)


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
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
    events["gauge_id"] = events["gauge_id"].map(normalize_gauge_id)
    return events


def build_features(events: pd.DataFrame) -> pd.DataFrame:
    features = pd.DataFrame(index=events.index)
    features["recent_1d_ratio"] = safe_ratio(events, "recent_rain_24h", "basin_rain_1d_p90")
    features["recent_3d_ratio"] = safe_ratio(events, "recent_rain_72h", "basin_rain_3d_p90")
    features["antecedent_7d_ratio"] = safe_ratio(events, "antecedent_rain_7d", "basin_rain_7d_p90")
    features["antecedent_30d_ratio"] = safe_ratio(events, "antecedent_rain_30d", "basin_rain_30d_p90")
    features["snowmelt_ratio"] = safe_ratio(events, "degree_day_snowmelt_7d", "basin_snowmelt_7d_p90")
    snow_valid = (
        (numeric_series(events, "basin_snowmelt_valid_window_count") >= SNOWMELT_MIN_VALID_WINDOW_COUNT)
        & (numeric_series(events, "basin_snowmelt_7d_p90") > 0)
    )
    features.loc[~snow_valid, "snowmelt_ratio"] = 0.0
    features["snowmelt_fraction"] = numeric_series(events, "degree_day_snowmelt_fraction_7d")
    features["event_mean_temp"] = numeric_series(events, "event_mean_temp")

    for col in [
        "recent_1d_ratio",
        "recent_3d_ratio",
        "antecedent_7d_ratio",
        "antecedent_30d_ratio",
        "snowmelt_ratio",
    ]:
        features[col] = features[col].clip(lower=0).fillna(0.0)
    features["snowmelt_fraction"] = features["snowmelt_fraction"].clip(lower=0, upper=1).fillna(0.0)
    features["event_mean_temp"] = features["event_mean_temp"].fillna(median_or_zero(features["event_mean_temp"]))
    return features[FEATURE_COLUMNS].astype(float)


def transform_features(features: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    transformed = features.copy()
    for col in LOG1P_FEATURES:
        transformed[col] = np.log1p(transformed[col].clip(lower=0))
    matrix = RobustScaler().fit_transform(transformed)
    return transformed, matrix


def fit_variant(matrix: np.ndarray, n_clusters: int, random_state: int) -> np.ndarray:
    model = KMeans(n_clusters=n_clusters, n_init=20, random_state=random_state)
    return model.fit_predict(matrix)


def read_rule_events(path: Path) -> pd.DataFrame:
    cols = ["gauge_id", "event_id", "flood_generation_type"]
    rules = pd.read_csv(path, usecols=cols, dtype={"gauge_id": str})
    rules["gauge_id"] = rules["gauge_id"].map(normalize_gauge_id)
    return rules


def add_cluster_name(labels: pd.Series | np.ndarray) -> list[str]:
    return [CLUSTER_NAMES.get(int(label), f"Cluster {label}") for label in labels]


def savefig(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=220, bbox_inches="tight")
    plt.close()


def plot_pca_scatter(
    coords: np.ndarray,
    values: pd.Series,
    colors: dict[Any, str],
    title: str,
    path: Path,
    sample_idx: np.ndarray,
    explained: np.ndarray,
) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 6.5))
    sampled_values = values.iloc[sample_idx].astype(str)
    for value in sorted(sampled_values.unique()):
        mask = sampled_values.eq(value).to_numpy()
        ax.scatter(
            coords[sample_idx][mask, 0],
            coords[sample_idx][mask, 1],
            s=5,
            alpha=0.35,
            c=colors.get(value, "#777777"),
            label=value,
            linewidths=0,
        )
    ax.set_title(title)
    ax.set_xlabel(f"PC1 ({explained[0] * 100:.1f}% var.)")
    ax.set_ylabel(f"PC2 ({explained[1] * 100:.1f}% var.)")
    ax.legend(markerscale=2.5, frameon=False, loc="best")
    ax.grid(alpha=0.18)
    savefig(path)


def resolve_experiment_table_dir(experiment_dir: Path) -> Path:
    table_dir = experiment_dir / "tables"
    return table_dir if table_dir.exists() else experiment_dir


def plot_metric_ranking(experiment_dir: Path, path: Path) -> None:
    table_dir = resolve_experiment_table_dir(experiment_dir)
    ranking = pd.read_csv(table_dir / "variant_ranking.csv").head(10).copy()
    ranking = ranking.iloc[::-1]
    fig, ax = plt.subplots(figsize=(10, 6))
    labels = ranking["variant_id"].str.replace("__", "\n", regex=False)
    ax.barh(labels, ranking["score"], color="#506d84")
    ax.set_xlabel("Composite exploratory score")
    ax.set_title("Top ML Clustering Variants")
    ax.grid(axis="x", alpha=0.2)
    savefig(path)


def plot_variant_metric_heatmap(experiment_dir: Path, path: Path) -> None:
    table_dir = resolve_experiment_table_dir(experiment_dir)
    metrics = pd.read_csv(table_dir / "variant_ranking.csv").head(10).copy()
    metric_cols = [
        "silhouette_sample",
        "davies_bouldin_sample",
        "seed_ari_mean",
        "rule_normalized_mutual_info",
        "min_cluster_share",
        "basin_top1_ge_threshold_share",
        "basin_top2_ge_0_8_share",
    ]
    display = metrics[["variant_id", *metric_cols]].copy()
    scaled = display[metric_cols].copy()
    scaled["davies_bouldin_sample"] = -scaled["davies_bouldin_sample"]
    for col in metric_cols:
        values = scaled[col]
        denom = values.max() - values.min()
        scaled[col] = 0.5 if denom == 0 else (values - values.min()) / denom

    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    labels = display["variant_id"].str.replace("__", "\n", regex=False)
    im = ax.imshow(scaled.to_numpy(), cmap="viridis", vmin=0, vmax=1)
    ax.set_yticks(range(len(labels)), labels=labels, fontsize=8)
    ax.set_xticks(
        range(len(metric_cols)),
        labels=[
            "silhouette",
            "DB inverse",
            "seed ARI",
            "rule NMI",
            "min cluster",
            "top1 >= .6",
            "top2 >= .8",
        ],
        rotation=30,
        ha="right",
    )
    ax.set_title("Top Variant Metric Balance (Column-Normalized)")
    fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02, label="Relative score")
    savefig(path)


def plot_variant_tradeoff(experiment_dir: Path, path: Path) -> None:
    table_dir = resolve_experiment_table_dir(experiment_dir)
    metrics = pd.read_csv(table_dir / "variant_metrics.csv").copy()
    fig, ax = plt.subplots(figsize=(8, 5.5))
    colors = {"kmeans": "#3f6fb5", "gmm_diag": "#8f5ca8"}
    markers = {3: "o", 4: "s"}
    for (method, k), group in metrics.groupby(["method", "k"]):
        ax.scatter(
            group["silhouette_sample"],
            group["davies_bouldin_sample"],
            s=70 + 180 * group["seed_ari_mean"].fillna(0),
            c=colors.get(method, "#777777"),
            marker=markers.get(int(k), "o"),
            alpha=0.78,
            edgecolors="white",
            linewidths=0.8,
            label=f"{method}, k={k}",
        )
    best = metrics.sort_values("silhouette_sample", ascending=False).head(3)
    for _, row in best.iterrows():
        ax.annotate(
            row["feature_set"],
            (row["silhouette_sample"], row["davies_bouldin_sample"]),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8,
        )
    ax.set_xlabel("Silhouette sample (higher is better)")
    ax.set_ylabel("Davies-Bouldin sample (lower is better)")
    ax.set_title("Variant Separation Trade-Off")
    ax.legend(frameon=False, fontsize=8)
    ax.grid(alpha=0.18)
    savefig(path)


def plot_rule_heatmap(crosstab: pd.DataFrame, path: Path) -> None:
    order = [0, 1, 2]
    rule_order = [
        "recent_precipitation",
        "antecedent_precipitation",
        "snowmelt_or_rain_on_snow",
        "uncertain_high_flow_candidate",
    ]
    counts = pd.crosstab(crosstab["ml_cluster"], crosstab["flood_generation_type"])
    counts = counts.reindex(index=order, columns=rule_order, fill_value=0)
    shares = counts.div(counts.sum(axis=1), axis=0).fillna(0)

    fig, ax = plt.subplots(figsize=(9.5, 4.2))
    cmap = LinearSegmentedColormap.from_list("soft_blues", ["#f5f7f8", "#47739f"])
    im = ax.imshow(shares.to_numpy(), cmap=cmap, vmin=0, vmax=max(0.75, shares.to_numpy().max()))
    ax.set_xticks(range(len(rule_order)), labels=rule_order, rotation=25, ha="right")
    ax.set_yticks(range(len(order)), labels=[CLUSTER_NAMES[item] for item in order])
    ax.set_title("Rule-Based Event Type Share Within Each ML Cluster")
    for i in range(shares.shape[0]):
        for j in range(shares.shape[1]):
            ax.text(j, i, f"{shares.iat[i, j]:.2f}", ha="center", va="center", fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02, label="Row share")
    savefig(path)


def plot_feature_profile(features: pd.DataFrame, labels: np.ndarray, path: Path) -> pd.DataFrame:
    profile = features.copy()
    profile["ml_cluster"] = labels
    medians = profile.groupby("ml_cluster")[FEATURE_COLUMNS].median().reindex([0, 1, 2])
    global_median = features[FEATURE_COLUMNS].median()
    global_iqr = features[FEATURE_COLUMNS].quantile(0.75) - features[FEATURE_COLUMNS].quantile(0.25)
    scaled = (medians - global_median) / global_iqr.replace(0, np.nan)
    scaled = scaled.clip(-2, 2).fillna(0)

    fig, ax = plt.subplots(figsize=(9.5, 4.2))
    im = ax.imshow(scaled.to_numpy(), cmap="RdBu_r", vmin=-2, vmax=2)
    ax.set_yticks(range(len(scaled.index)), labels=[CLUSTER_NAMES[int(item)] for item in scaled.index])
    ax.set_xticks(range(len(FEATURE_COLUMNS)), labels=FEATURE_COLUMNS, rotation=35, ha="right")
    ax.set_title("Cluster Feature Profile (Median, Robust-Scaled Against Global IQR)")
    for i in range(scaled.shape[0]):
        for j in range(scaled.shape[1]):
            ax.text(j, i, f"{scaled.iat[i, j]:.1f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02, label="Robust median contrast")
    savefig(path)
    return medians.reset_index()


def basin_cluster_shares(keys: pd.DataFrame, labels: np.ndarray) -> pd.DataFrame:
    work = keys[["gauge_id"]].copy()
    work["ml_cluster"] = labels
    shares = pd.crosstab(work["gauge_id"], work["ml_cluster"], normalize="index")
    shares = shares.reindex(columns=[0, 1, 2], fill_value=0.0)
    shares.columns = [f"cluster_{col}_share" for col in shares.columns]
    shares["event_count"] = work.groupby("gauge_id").size()
    share_cols = ["cluster_0_share", "cluster_1_share", "cluster_2_share"]
    sorted_shares = np.sort(shares[share_cols].to_numpy(), axis=1)[:, ::-1]
    shares["top1_share"] = sorted_shares[:, 0]
    shares["top2_share"] = sorted_shares[:, :2].sum(axis=1)
    entropy = []
    for row in shares[share_cols].to_numpy():
        positive = row[row > 0]
        entropy.append(float(-(positive * np.log(positive)).sum() / np.log(len(row))))
    shares["cluster_entropy"] = entropy
    return shares.reset_index()


def plot_basin_triangle(basin: pd.DataFrame, rule_basin: pd.DataFrame, path: Path) -> None:
    merged = basin.merge(rule_basin, on="gauge_id", how="left")
    a = merged["cluster_0_share"].to_numpy()
    b = merged["cluster_1_share"].to_numpy()
    c = merged["cluster_2_share"].to_numpy()
    x = c + 0.5 * b
    y = (math.sqrt(3) / 2.0) * b
    colors = merged["dominant_flood_generation_type"].map(RULE_COLORS).fillna("#999999")

    fig, ax = plt.subplots(figsize=(7.3, 6.4))
    ax.plot([0, 1, 0.5, 0], [0, 0, math.sqrt(3) / 2, 0], color="#444444", lw=1.1)
    ax.scatter(x, y, s=13, alpha=0.55, c=colors, linewidths=0)
    ax.text(-0.03, -0.04, CLUSTER_NAMES[0], ha="left", va="top", fontsize=10)
    ax.text(1.03, -0.04, CLUSTER_NAMES[2], ha="right", va="top", fontsize=10)
    ax.text(0.5, math.sqrt(3) / 2 - 0.045, CLUSTER_NAMES[1], ha="center", va="top", fontsize=10)
    ax.set_title("Basin-Level ML Cluster Composition (All Basins)", pad=24)
    ax.set_axis_off()
    legend_handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=color, markersize=7, label=label)
        for label, color in RULE_COLORS.items()
    ]
    ax.legend(handles=legend_handles, frameon=False, loc="lower center", bbox_to_anchor=(0.5, -0.18), ncol=2)
    savefig(path)


def plot_basin_share_histogram(basin: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.8))
    bins = np.linspace(0, 1, 26)
    ax.hist(basin["top1_share"], bins=bins, alpha=0.72, color="#506d84", label="Top-1 share")
    ax.hist(basin["top2_share"], bins=bins, alpha=0.48, color="#d78a2a", label="Top-2 share")
    ax.axvline(0.6, color="#222222", lw=1, ls="--", label="Dominance threshold 0.6")
    ax.axvline(0.8, color="#777777", lw=1, ls=":", label="Top-2 0.8")
    ax.set_xlabel("Basin event-share")
    ax.set_ylabel("Basin count")
    ax.set_title("Basin Composition Is Often Better Captured by Top-2 Shares")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.18)
    savefig(path)


def plot_drbc_stacked_bars(basin: pd.DataFrame, drbc_path: Path, path: Path) -> None:
    if not drbc_path.exists():
        return
    drbc = pd.read_csv(drbc_path, dtype={"gauge_id": str})
    drbc["gauge_id"] = drbc["gauge_id"].map(normalize_gauge_id)
    merged = basin.merge(drbc[["gauge_id", "gauge_name", "event_count"]], on="gauge_id", how="inner")
    if merged.empty:
        return
    merged = merged.sort_values("top1_share", ascending=False)
    labels = merged["gauge_id"]
    fig, ax = plt.subplots(figsize=(max(10, len(merged) * 0.28), 5.4))
    bottom = np.zeros(len(merged))
    for cluster in [0, 1, 2]:
        values = merged[f"cluster_{cluster}_share"].to_numpy()
        ax.bar(
            range(len(merged)),
            values,
            bottom=bottom,
            color=CLUSTER_COLORS[cluster],
            label=CLUSTER_NAMES[cluster],
            width=0.86,
        )
        bottom += values
    ax.set_xticks(range(len(merged)), labels=labels, rotation=90, fontsize=7)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Event share")
    ax.set_title("DRBC Event-Response Basins: ML Cluster Composition")
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.15))
    ax.grid(axis="y", alpha=0.16)
    savefig(path)


def plot_monthly_composition(keys: pd.DataFrame, labels: np.ndarray, path: Path) -> None:
    work = keys[["peak_month"]].copy()
    work["ml_cluster"] = labels
    monthly = pd.crosstab(work["peak_month"], work["ml_cluster"], normalize="index")
    monthly = monthly.reindex(index=range(1, 13), columns=[0, 1, 2], fill_value=0.0)

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    bottom = np.zeros(len(monthly))
    for cluster in [0, 1, 2]:
        values = monthly[cluster].to_numpy()
        ax.bar(monthly.index, values, bottom=bottom, color=CLUSTER_COLORS[cluster], label=CLUSTER_NAMES[cluster])
        bottom += values
    ax.set_xticks(range(1, 13))
    ax.set_ylim(0, 1)
    ax.set_xlabel("Peak month")
    ax.set_ylabel("Event share")
    ax.set_title("Seasonal Composition of ML Event Clusters")
    ax.legend(frameon=False, ncol=1, loc="upper right")
    ax.grid(axis="y", alpha=0.16)
    savefig(path)


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.table_dir.mkdir(parents=True, exist_ok=True)
    args.metadata_dir.mkdir(parents=True, exist_ok=True)
    args.variant_figure_dir.mkdir(parents=True, exist_ok=True)

    events = read_events(args.event_response_csv)
    rules = read_rule_events(args.rule_typing_csv)
    features = build_features(events)
    transformed, matrix = transform_features(features)
    labels = fit_variant(matrix, args.n_clusters, args.random_state)

    keys = events[["gauge_id", "event_id", "peak_month", "water_year", "huc02"]].copy()
    event_labels = keys.merge(rules, on=["gauge_id", "event_id"], how="left")
    event_labels["ml_cluster"] = labels
    event_labels["ml_cluster_name"] = add_cluster_name(labels)

    pca = PCA(n_components=2, random_state=args.random_state)
    coords = pca.fit_transform(matrix)
    rng = np.random.default_rng(args.random_state)
    sample_idx = rng.choice(
        len(events),
        size=min(args.scatter_sample_size, len(events)),
        replace=False,
    )

    cluster_name_colors = {CLUSTER_NAMES[key]: value for key, value in CLUSTER_COLORS.items()}
    plot_pca_scatter(
        coords,
        event_labels["ml_cluster_name"],
        cluster_name_colors,
        "Event Descriptor PCA by Improved ML Cluster",
        args.output_dir / "event_descriptor_pca_by_ml_cluster.png",
        sample_idx,
        pca.explained_variance_ratio_,
    )
    plot_pca_scatter(
        coords,
        event_labels["flood_generation_type"].fillna("unmatched"),
        RULE_COLORS,
        "Same Event Descriptor PCA by Rule-Based Type",
        args.output_dir / "event_descriptor_pca_by_rule_type.png",
        sample_idx,
        pca.explained_variance_ratio_,
    )

    plot_metric_ranking(args.experiment_dir, args.variant_figure_dir / "variant_ranking_bar.png")
    plot_variant_metric_heatmap(args.experiment_dir, args.variant_figure_dir / "variant_metric_heatmap.png")
    plot_variant_tradeoff(args.experiment_dir, args.variant_figure_dir / "variant_tradeoff_scatter.png")
    plot_rule_heatmap(event_labels, args.output_dir / "rule_vs_ml_cluster_heatmap.png")
    profile_medians = plot_feature_profile(
        features,
        labels,
        args.output_dir / "ml_cluster_feature_profile_heatmap.png",
    )
    basin = basin_cluster_shares(keys, labels)
    basin_path = args.table_dir / "selected_variant_basin_cluster_composition.csv"
    event_labels_path = args.table_dir / "selected_variant_event_labels.csv"
    profile_medians_path = args.table_dir / "selected_variant_cluster_feature_medians.csv"
    basin.to_csv(basin_path, index=False)
    event_labels.to_csv(event_labels_path, index=False)
    profile_medians.to_csv(profile_medians_path, index=False)

    rule_basin = pd.read_csv(args.rule_basin_csv, dtype={"gauge_id": str})
    rule_basin["gauge_id"] = rule_basin["gauge_id"].map(normalize_gauge_id)
    plot_basin_triangle(basin, rule_basin, args.output_dir / "basin_cluster_composition_triangle.png")
    plot_basin_share_histogram(basin, args.output_dir / "basin_top1_top2_share_histogram.png")
    plot_drbc_stacked_bars(basin, args.drbc_event_basin_csv, args.output_dir / "drbc_basin_cluster_stacked_bar.png")
    plot_monthly_composition(keys, labels, args.output_dir / "monthly_ml_cluster_composition.png")

    counts = event_labels["ml_cluster_name"].value_counts().to_dict()
    crosstab = pd.crosstab(event_labels["ml_cluster_name"], event_labels["flood_generation_type"], normalize="index")
    summary = {
        "variant": "kmeans__hydromet_only_7__k3",
        "event_count": int(len(events)),
        "basin_count": int(basin["gauge_id"].nunique()),
        "feature_columns": FEATURE_COLUMNS,
        "pca_explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
        "cluster_event_counts": counts,
        "rule_share_within_ml_cluster": crosstab.round(4).to_dict(orient="index"),
        "basin_top1_ge_0_6_share": float((basin["top1_share"] >= 0.6).mean()),
        "basin_top2_ge_0_8_share": float((basin["top2_share"] >= 0.8).mean()),
        "figures": [
            *sorted(str(path) for path in args.output_dir.glob("*.png")),
            *sorted(str(path) for path in args.variant_figure_dir.glob("*.png")),
        ],
        "tables": [
            str(basin_path),
            str(event_labels_path),
            str(profile_medians_path),
        ],
    }
    summary_path = args.metadata_dir / "selected_variant_visual_summary.json"
    summary_path.write_text(
        json.dumps(json_safe(summary), indent=2),
        encoding="utf-8",
    )

    print(f"Wrote figures to: {args.output_dir}")
    print(f"Wrote event labels: {event_labels_path}")
    print(f"Wrote basin composition: {basin_path}")
    print(f"Wrote summary: {summary_path}")


if __name__ == "__main__":
    main()
