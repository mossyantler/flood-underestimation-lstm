#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "pyarrow>=15.0",
#   "scikit-learn>=1.4",
#   "xarray>=2024.1",
# ]
# ///

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    normalized_mutual_info_score,
    silhouette_score,
)
from sklearn.preprocessing import RobustScaler

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import camelsh_flood_analysis_utils as fu


DEFAULT_EVENT_RESPONSE_CSV = Path("output/basin/all/analysis/event_response/tables/event_response_table.csv")
DEFAULT_RULE_TYPING_CSV = Path("output/basin/all/analysis/flood_generation/tables/flood_generation_event_types.csv")
DEFAULT_OUTPUT_DIR = Path("output/basin/all/archive/event_regime_variants")

RANDOM_STATES = (111, 222, 444)
K_VALUES = (3, 4)

BASE_FEATURE_COLUMNS = [
    "recent_1d_ratio",
    "recent_3d_ratio",
    "antecedent_7d_ratio",
    "antecedent_30d_ratio",
    "snowmelt_ratio",
    "snowmelt_fraction",
    "rain_fraction",
    "snow_proxy_available",
    "event_mean_temp",
    "antecedent_mean_temp_7d",
    "rising_time_hours",
    "event_duration_hours",
    "event_runoff_coefficient",
]

FEATURE_SETS = {
    "current_all_13": BASE_FEATURE_COLUMNS,
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
    "compact_process_6": [
        "recent_1d_ratio",
        "recent_3d_ratio",
        "antecedent_7d_ratio",
        "antecedent_30d_ratio",
        "snowmelt_ratio",
        "rising_time_hours",
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
    "intensity_process_9": [
        "recent_1d_ratio",
        "recent_3d_ratio",
        "peak_intensity_6h_ratio",
        "antecedent_7d_ratio",
        "antecedent_30d_ratio",
        "snowmelt_ratio",
        "event_mean_temp",
        "rising_time_hours",
        "event_duration_hours",
    ],
}

LOG1P_FEATURES = {
    "recent_1d_ratio",
    "recent_3d_ratio",
    "peak_intensity_6h_ratio",
    "antecedent_7d_ratio",
    "antecedent_30d_ratio",
    "snowmelt_ratio",
    "rising_time_hours",
    "event_duration_hours",
    "event_runoff_coefficient",
}

SHAPE_FEATURES = {"rising_time_hours", "event_duration_hours"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare exploratory CAMELSH flood-generation event clustering variants."
    )
    parser.add_argument("--event-response-csv", type=Path, default=DEFAULT_EVENT_RESPONSE_CSV)
    parser.add_argument("--rule-typing-csv", type=Path, default=DEFAULT_RULE_TYPING_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--metric-sample-size",
        type=int,
        default=30000,
        help="Sample size for silhouette/CH/DB metrics.",
    )
    parser.add_argument(
        "--gmm-fit-sample-size",
        type=int,
        default=120000,
        help="Maximum rows used to fit GMM variants. Full data are still assigned labels.",
    )
    parser.add_argument(
        "--shape-winsor-quantile",
        type=float,
        default=0.995,
        help="Upper quantile used to winsorize hydrograph shape duration features.",
    )
    parser.add_argument(
        "--dominance-threshold",
        type=float,
        default=0.6,
        help="Top-one basin share threshold for dominant basin counts.",
    )
    parser.add_argument("--random-state", type=int, default=111)
    return parser.parse_args()


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
    if not path.exists():
        raise SystemExit(f"Event response CSV does not exist: {path}")
    events = pd.read_csv(path, dtype={"gauge_id": str, "huc02": str})
    if events.empty:
        raise SystemExit(f"Event response CSV is empty: {path}")
    events["gauge_id"] = events["gauge_id"].map(fu.normalize_gauge_id)
    return events


def build_feature_table(events: pd.DataFrame) -> pd.DataFrame:
    features = pd.DataFrame(index=events.index)
    features["recent_1d_ratio"] = safe_ratio(events, "recent_rain_24h", "basin_rain_1d_p90")
    features["recent_3d_ratio"] = safe_ratio(events, "recent_rain_72h", "basin_rain_3d_p90")
    features["peak_intensity_6h_ratio"] = safe_ratio(events, "peak_rain_intensity_6h", "basin_rain_1d_p90")
    features["antecedent_7d_ratio"] = safe_ratio(events, "antecedent_rain_7d", "basin_rain_7d_p90")
    features["antecedent_30d_ratio"] = safe_ratio(events, "antecedent_rain_30d", "basin_rain_30d_p90")
    features["snowmelt_ratio"] = safe_ratio(events, "degree_day_snowmelt_7d", "basin_snowmelt_7d_p90")

    snow_valid = (
        (numeric_series(events, "basin_snowmelt_valid_window_count") >= fu.SNOWMELT_MIN_VALID_WINDOW_COUNT)
        & (numeric_series(events, "basin_snowmelt_7d_p90") > 0)
    )
    features.loc[~snow_valid, "snowmelt_ratio"] = 0.0
    features["snow_proxy_available"] = snow_valid.astype(float)

    features["snowmelt_fraction"] = numeric_series(events, "degree_day_snowmelt_fraction_7d")
    features["rain_fraction"] = numeric_series(events, "degree_day_rain_fraction_7d")
    features["event_mean_temp"] = numeric_series(events, "event_mean_temp")
    features["antecedent_mean_temp_7d"] = numeric_series(events, "antecedent_mean_temp_7d")
    features["rising_time_hours"] = numeric_series(events, "rising_time_hours")
    features["event_duration_hours"] = numeric_series(events, "event_duration_hours")
    features["event_runoff_coefficient"] = numeric_series(events, "event_runoff_coefficient")

    ratio_like = [
        "recent_1d_ratio",
        "recent_3d_ratio",
        "peak_intensity_6h_ratio",
        "antecedent_7d_ratio",
        "antecedent_30d_ratio",
        "snowmelt_ratio",
    ]
    for col in ratio_like:
        features[col] = features[col].clip(lower=0).fillna(0.0)
    for col in ["snowmelt_fraction", "rain_fraction", "snow_proxy_available"]:
        features[col] = features[col].clip(lower=0, upper=1).fillna(0.0)
    for col in ["rising_time_hours", "event_duration_hours", "event_runoff_coefficient"]:
        features[col] = features[col].clip(lower=0)
        features[col] = features[col].fillna(median_or_zero(features[col]))
    for col in ["event_mean_temp", "antecedent_mean_temp_7d"]:
        features[col] = features[col].fillna(median_or_zero(features[col]))

    return features.astype(float)


def feature_audit(features: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for col in sorted(features.columns):
        series = pd.to_numeric(features[col], errors="coerce")
        rows.append(
            {
                "feature": col,
                "missing_share_after_impute": float(series.isna().mean()),
                "zero_share_after_impute": float((series.fillna(0) == 0).mean()),
                "median": float(series.median(skipna=True)),
                "p90": float(series.quantile(0.90)),
                "p99": float(series.quantile(0.99)),
                "std": float(series.std(skipna=True)),
                "nunique": int(series.nunique(dropna=True)),
                "raw_nonmissing_share": (
                    float(numeric_series(events, col).notna().mean()) if col in events.columns else None
                ),
            }
        )
    return pd.DataFrame(rows)


def transformed_matrix(
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


def read_rule_labels(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"Rule typing CSV does not exist: {path}")
    cols = ["gauge_id", "event_id", "flood_generation_type"]
    rules = pd.read_csv(path, usecols=cols, dtype={"gauge_id": str})
    rules["gauge_id"] = rules["gauge_id"].map(fu.normalize_gauge_id)
    return rules


def event_keys(events: pd.DataFrame) -> pd.DataFrame:
    cols = ["gauge_id", "event_id", "peak_month", "water_year", "huc02"]
    existing = [col for col in cols if col in events.columns]
    return events[existing].copy()


def sampled_metrics(matrix: np.ndarray, labels: np.ndarray, sample_idx: np.ndarray) -> dict[str, float]:
    if len(np.unique(labels[sample_idx])) < 2:
        return {
            "silhouette_sample": np.nan,
            "calinski_sample": np.nan,
            "davies_bouldin_sample": np.nan,
        }
    sampled = matrix[sample_idx]
    sampled_labels = labels[sample_idx]
    return {
        "silhouette_sample": float(silhouette_score(sampled, sampled_labels)),
        "calinski_sample": float(calinski_harabasz_score(sampled, sampled_labels)),
        "davies_bouldin_sample": float(davies_bouldin_score(sampled, sampled_labels)),
    }


def label_stability(labels_by_seed: dict[int, np.ndarray]) -> tuple[float, float]:
    if len(labels_by_seed) < 2:
        return np.nan, np.nan
    aris = [
        adjusted_rand_score(a, b)
        for a, b in itertools.combinations(labels_by_seed.values(), 2)
    ]
    return float(np.mean(aris)), float(np.min(aris))


def cluster_profiles(
    features: pd.DataFrame,
    labels: np.ndarray,
    columns: Iterable[str],
    variant_id: str,
) -> pd.DataFrame:
    work = features[list(columns)].copy()
    work["cluster"] = labels
    rows: list[dict[str, Any]] = []
    for cluster, group in work.groupby("cluster", sort=True):
        row: dict[str, Any] = {
            "variant_id": variant_id,
            "cluster": int(cluster),
            "event_count": int(len(group)),
            "event_share": float(len(group) / len(work)),
        }
        for col in columns:
            values = pd.to_numeric(group[col], errors="coerce")
            row[f"{col}_median"] = float(values.median(skipna=True))
            row[f"{col}_p90"] = float(values.quantile(0.90))
        rows.append(row)
    return pd.DataFrame(rows)


def basin_composition(
    keys: pd.DataFrame,
    labels: np.ndarray,
    variant_id: str,
    dominance_threshold: float,
) -> tuple[pd.DataFrame, dict[str, float]]:
    work = keys[["gauge_id"]].copy()
    work["cluster"] = labels
    rows: list[dict[str, Any]] = []
    for gauge_id, group in work.groupby("gauge_id", sort=True):
        shares = group["cluster"].value_counts(normalize=True).sort_values(ascending=False)
        top1 = float(shares.iloc[0])
        top2 = float(shares.iloc[:2].sum()) if len(shares) > 1 else top1
        entropy = float(-(shares * np.log(shares)).sum() / np.log(len(shares))) if len(shares) > 1 else 0.0
        rows.append(
            {
                "variant_id": variant_id,
                "gauge_id": gauge_id,
                "event_count": int(len(group)),
                "top1_cluster": int(shares.index[0]),
                "top1_share": top1,
                "top2_share": top2,
                "cluster_entropy": entropy,
                "dominant_cluster_at_threshold": (
                    int(shares.index[0]) if top1 >= dominance_threshold else "mixture"
                ),
            }
        )
    basin = pd.DataFrame(rows)
    summary = {
        "basin_top1_share_mean": float(basin["top1_share"].mean()),
        "basin_top1_share_median": float(basin["top1_share"].median()),
        "basin_top1_ge_threshold_share": float((basin["top1_share"] >= dominance_threshold).mean()),
        "basin_top2_ge_0_8_share": float((basin["top2_share"] >= 0.8).mean()),
        "basin_entropy_median": float(basin["cluster_entropy"].median()),
    }
    return basin, summary


def rule_agreement(
    keys: pd.DataFrame,
    labels: np.ndarray,
    rules: pd.DataFrame,
    variant_id: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    work = keys[["gauge_id", "event_id"]].copy()
    work["cluster"] = labels
    merged = work.merge(rules, on=["gauge_id", "event_id"], how="left", validate="one_to_one")
    valid = merged["flood_generation_type"].notna()
    metrics: dict[str, Any] = {
        "rule_matched_event_count": int(valid.sum()),
        "rule_unmatched_event_count": int((~valid).sum()),
        "rule_adjusted_rand_index": np.nan,
        "rule_normalized_mutual_info": np.nan,
        "rule_majority_purity": np.nan,
    }
    if valid.sum() > 1:
        metrics["rule_adjusted_rand_index"] = float(
            adjusted_rand_score(merged.loc[valid, "flood_generation_type"], merged.loc[valid, "cluster"])
        )
        metrics["rule_normalized_mutual_info"] = float(
            normalized_mutual_info_score(merged.loc[valid, "flood_generation_type"], merged.loc[valid, "cluster"])
        )
        counts = pd.crosstab(merged.loc[valid, "cluster"], merged.loc[valid, "flood_generation_type"])
        metrics["rule_majority_purity"] = float(counts.max(axis=1).sum() / counts.to_numpy().sum())
        crosstab = counts.reset_index().melt(
            id_vars="cluster",
            var_name="flood_generation_type",
            value_name="event_count",
        )
        crosstab["variant_id"] = variant_id
    else:
        crosstab = pd.DataFrame(columns=["variant_id", "cluster", "flood_generation_type", "event_count"])
    return crosstab, metrics


def fit_kmeans(matrix: np.ndarray, k: int, random_state: int) -> tuple[np.ndarray, float, dict[str, Any]]:
    model = KMeans(n_clusters=k, n_init=20, random_state=random_state)
    labels = model.fit_predict(matrix)
    return labels, float(model.inertia_), {"model_n_iter": int(model.n_iter_)}


def fit_gmm(
    matrix: np.ndarray,
    k: int,
    random_state: int,
    fit_idx: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    model = GaussianMixture(
        n_components=k,
        covariance_type="diag",
        n_init=3,
        random_state=random_state,
        reg_covar=1e-5,
    )
    model.fit(matrix[fit_idx])
    posterior = model.predict_proba(matrix)
    labels = posterior.argmax(axis=1)
    max_posterior = posterior.max(axis=1)
    metrics = {
        "gmm_lower_bound": float(model.lower_bound_),
        "gmm_fit_converged": bool(model.converged_),
        "gmm_fit_n_iter": int(model.n_iter_),
        "gmm_bic_fit_sample": float(model.bic(matrix[fit_idx])),
        "gmm_aic_fit_sample": float(model.aic(matrix[fit_idx])),
        "event_posterior_max_mean": float(max_posterior.mean()),
        "event_posterior_max_median": float(np.median(max_posterior)),
        "event_posterior_lt_0_7_share": float((max_posterior < 0.7).mean()),
        "event_posterior_lt_0_6_share": float((max_posterior < 0.6).mean()),
    }
    return labels, max_posterior, metrics


def main() -> None:
    args = parse_args()
    table_dir = args.output_dir / "tables"
    metadata_dir = args.output_dir / "metadata"
    transformed_sample_dir = table_dir / "transformed_samples"
    table_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    transformed_sample_dir.mkdir(parents=True, exist_ok=True)

    events = read_events(args.event_response_csv)
    rules = read_rule_labels(args.rule_typing_csv)
    features = build_feature_table(events)
    keys = event_keys(events)

    rng = np.random.default_rng(args.random_state)
    metric_idx = rng.choice(len(events), size=min(args.metric_sample_size, len(events)), replace=False)
    gmm_fit_idx = rng.choice(len(events), size=min(args.gmm_fit_sample_size, len(events)), replace=False)

    metrics_rows: list[dict[str, Any]] = []
    profile_tables: list[pd.DataFrame] = []
    basin_tables: list[pd.DataFrame] = []
    crosstab_tables: list[pd.DataFrame] = []
    labels_for_summary: dict[str, np.ndarray] = {}

    audit = feature_audit(features, events)
    audit.to_csv(table_dir / "feature_audit.csv", index=False)

    for feature_set_name, columns in FEATURE_SETS.items():
        transformed, matrix = transformed_matrix(features, columns, args.shape_winsor_quantile)
        transformed_sample_path = transformed_sample_dir / f"transformed_sample__{feature_set_name}.csv"
        sample_rows = transformed.iloc[metric_idx[: min(5000, len(metric_idx))]].copy()
        sample_rows.to_csv(transformed_sample_path, index=False)

        for k in K_VALUES:
            kmeans_labels_by_seed: dict[int, np.ndarray] = {}
            kmeans_inertias: list[float] = []
            for seed in RANDOM_STATES:
                labels, inertia, _ = fit_kmeans(matrix, k, seed)
                kmeans_labels_by_seed[seed] = labels
                kmeans_inertias.append(inertia)

            labels = kmeans_labels_by_seed[args.random_state]
            variant_id = f"kmeans__{feature_set_name}__k{k}"
            seed_ari_mean, seed_ari_min = label_stability(kmeans_labels_by_seed)
            basin, basin_metrics = basin_composition(keys, labels, variant_id, args.dominance_threshold)
            crosstab, agreement_metrics = rule_agreement(keys, labels, rules, variant_id)
            profile_tables.append(cluster_profiles(features, labels, columns, variant_id))
            basin_tables.append(basin)
            crosstab_tables.append(crosstab)
            labels_for_summary[variant_id] = labels
            counts = np.bincount(labels, minlength=k) / len(labels)
            row = {
                "variant_id": variant_id,
                "method": "kmeans",
                "feature_set": feature_set_name,
                "k": k,
                "feature_count": len(columns),
                "feature_columns": "|".join(columns),
                "inertia_mean": float(np.mean(kmeans_inertias)),
                "inertia_sd": float(np.std(kmeans_inertias)),
                "seed_ari_mean": seed_ari_mean,
                "seed_ari_min": seed_ari_min,
                "min_cluster_share": float(counts.min()),
                "max_cluster_share": float(counts.max()),
                **sampled_metrics(matrix, labels, metric_idx),
                **basin_metrics,
                **agreement_metrics,
            }
            metrics_rows.append(row)

            gmm_labels_by_seed: dict[int, np.ndarray] = {}
            gmm_extra_by_seed: dict[int, dict[str, Any]] = {}
            for seed in RANDOM_STATES:
                gmm_labels, _, gmm_extra = fit_gmm(matrix, k, seed, gmm_fit_idx)
                gmm_labels_by_seed[seed] = gmm_labels
                gmm_extra_by_seed[seed] = gmm_extra

            labels = gmm_labels_by_seed[args.random_state]
            variant_id = f"gmm_diag__{feature_set_name}__k{k}"
            seed_ari_mean, seed_ari_min = label_stability(gmm_labels_by_seed)
            basin, basin_metrics = basin_composition(keys, labels, variant_id, args.dominance_threshold)
            crosstab, agreement_metrics = rule_agreement(keys, labels, rules, variant_id)
            profile_tables.append(cluster_profiles(features, labels, columns, variant_id))
            basin_tables.append(basin)
            crosstab_tables.append(crosstab)
            labels_for_summary[variant_id] = labels
            counts = np.bincount(labels, minlength=k) / len(labels)
            gmm_extra = gmm_extra_by_seed[args.random_state]
            row = {
                "variant_id": variant_id,
                "method": "gmm_diag",
                "feature_set": feature_set_name,
                "k": k,
                "feature_count": len(columns),
                "feature_columns": "|".join(columns),
                "seed_ari_mean": seed_ari_mean,
                "seed_ari_min": seed_ari_min,
                "min_cluster_share": float(counts.min()),
                "max_cluster_share": float(counts.max()),
                **gmm_extra,
                **sampled_metrics(matrix, labels, metric_idx),
                **basin_metrics,
                **agreement_metrics,
            }
            metrics_rows.append(row)

    metrics = pd.DataFrame(metrics_rows)
    metrics.to_csv(table_dir / "variant_metrics.csv", index=False)
    pd.concat(profile_tables, ignore_index=True).to_csv(table_dir / "variant_cluster_profiles.csv", index=False)
    pd.concat(basin_tables, ignore_index=True).to_csv(table_dir / "variant_basin_composition.csv", index=False)
    pd.concat(crosstab_tables, ignore_index=True).to_csv(table_dir / "variant_rule_crosstab_long.csv", index=False)

    # A pragmatic shortlist: avoid tiny clusters, prefer interpretable k=3/4 variants with decent separation,
    # stable seeds, and useful basin top-two composition.
    ranking = metrics.copy()
    ranking["tiny_cluster_penalty"] = (ranking["min_cluster_share"] < 0.08).astype(float)
    ranking["score"] = (
        ranking["silhouette_sample"].rank(pct=True)
        + (-ranking["davies_bouldin_sample"]).rank(pct=True)
        + ranking["seed_ari_mean"].rank(pct=True)
        + ranking["rule_normalized_mutual_info"].rank(pct=True)
        + ranking["basin_top2_ge_0_8_share"].rank(pct=True)
        - ranking["tiny_cluster_penalty"]
    )
    ranking = ranking.sort_values(["score", "silhouette_sample"], ascending=False)
    ranking.to_csv(table_dir / "variant_ranking.csv", index=False)

    summary = {
        "event_response_csv": str(args.event_response_csv),
        "rule_typing_csv": str(args.rule_typing_csv),
        "output_dir": str(args.output_dir),
        "event_count": int(len(events)),
        "basin_count": int(keys["gauge_id"].nunique()),
        "feature_sets": FEATURE_SETS,
        "k_values": K_VALUES,
        "methods": ["kmeans", "gmm_diag"],
        "random_states": RANDOM_STATES,
        "metric_sample_size": int(len(metric_idx)),
        "gmm_fit_sample_size": int(len(gmm_fit_idx)),
        "shape_winsor_quantile": args.shape_winsor_quantile,
        "top_ranked_variants": ranking.head(8)[
            [
                "variant_id",
                "method",
                "feature_set",
                "k",
                "score",
                "silhouette_sample",
                "davies_bouldin_sample",
                "seed_ari_mean",
                "min_cluster_share",
                "rule_normalized_mutual_info",
                "basin_top1_ge_threshold_share",
                "basin_top2_ge_0_8_share",
            ]
        ].to_dict(orient="records"),
        "notes": [
            "This is an exploratory comparison, not a replacement for the canonical degree-day v2 typing.",
            "GMM variants are fit on a sample but assign all events to a posterior-max component.",
            "Hydrograph duration features are winsorized before log1p/RobustScaler to reduce segmentation-tail influence.",
        ],
    }
    (metadata_dir / "comparison_summary.json").write_text(
        json.dumps(json_safe(summary), indent=2),
        encoding="utf-8",
    )

    print(f"Wrote feature audit: {table_dir / 'feature_audit.csv'}")
    print(f"Wrote variant metrics: {table_dir / 'variant_metrics.csv'}")
    print(f"Wrote variant ranking: {table_dir / 'variant_ranking.csv'}")
    print(f"Wrote cluster profiles: {table_dir / 'variant_cluster_profiles.csv'}")
    print(f"Wrote basin composition: {table_dir / 'variant_basin_composition.csv'}")
    print(f"Wrote rule crosstab: {table_dir / 'variant_rule_crosstab_long.csv'}")
    print(f"Wrote summary: {metadata_dir / 'comparison_summary.json'}")


if __name__ == "__main__":
    main()
