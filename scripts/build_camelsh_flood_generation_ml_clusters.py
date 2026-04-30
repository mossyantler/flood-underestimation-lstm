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
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
from sklearn.preprocessing import RobustScaler

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import camelsh_flood_analysis_utils as fu


DEFAULT_EVENT_RESPONSE_CSV = Path("output/basin/all/analysis/event_response/tables/event_response_table.csv")
DEFAULT_RULE_TYPING_CSV = Path("output/basin/all/analysis/flood_generation/tables/flood_generation_event_types.csv")
DEFAULT_OUTPUT_DIR = Path("output/basin/all/archive/legacy_ml")

METADATA_COLUMNS = [
    "gauge_id",
    "gauge_name",
    "state",
    "huc02",
    "event_id",
    "event_start",
    "event_peak",
    "event_end",
    "water_year",
    "peak_month",
    "selected_threshold_quantile",
    "event_detection_basis",
    "event_candidate_label",
    "flood_relevance_tier",
    "flood_relevance_basis",
    "return_period_confidence_flag",
]

RATIO_FEATURES = [
    "recent_1d_ratio",
    "recent_3d_ratio",
    "antecedent_7d_ratio",
    "antecedent_30d_ratio",
    "snowmelt_ratio",
]
FRACTION_FEATURES = [
    "snowmelt_fraction",
    "rain_fraction",
    "snow_proxy_available",
]
TEMPERATURE_FEATURES = [
    "event_mean_temp",
    "antecedent_mean_temp_7d",
]
SHAPE_FEATURES = [
    "rising_time_hours",
    "event_duration_hours",
    "event_runoff_coefficient",
]
LOG1P_FEATURES = [*RATIO_FEATURES, *SHAPE_FEATURES]
FEATURE_COLUMNS = [*RATIO_FEATURES, *FRACTION_FEATURES, *TEMPERATURE_FEATURES, *SHAPE_FEATURES]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Cluster CAMELSH observed high-flow event candidates with KMeans for exploratory "
            "flood-generation typing sensitivity analysis."
        )
    )
    parser.add_argument(
        "--event-response-csv",
        type=Path,
        default=DEFAULT_EVENT_RESPONSE_CSV,
        help="Event response table produced by build_camelsh_event_response_table.py.",
    )
    parser.add_argument(
        "--rule-typing-csv",
        type=Path,
        default=DEFAULT_RULE_TYPING_CSV,
        help="Optional rule-based typing CSV for rule-vs-ML comparison.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for exploratory ML clustering outputs.",
    )
    parser.add_argument(
        "--n-clusters",
        type=int,
        default=4,
        help="Number of KMeans clusters. The exploratory default is 4.",
    )
    parser.add_argument("--random-state", type=int, default=111)
    parser.add_argument(
        "--dominance-threshold",
        type=float,
        default=0.6,
        help="Minimum basin event-share required to call a basin dominant rather than mixture.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional row limit for local smoke tests.",
    )
    return parser.parse_args()


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def read_events(path: Path, limit: int | None) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"Event response CSV does not exist: {path}")
    events = pd.read_csv(path, dtype={"gauge_id": str, "huc02": str}, nrows=limit)
    if events.empty:
        raise SystemExit(f"Event response CSV is empty: {path}")
    events["gauge_id"] = events["gauge_id"].map(fu.normalize_gauge_id)
    return events


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
    features["snow_proxy_available"] = snow_valid.astype(float)

    features["snowmelt_fraction"] = numeric_series(events, "degree_day_snowmelt_fraction_7d")
    features["rain_fraction"] = numeric_series(events, "degree_day_rain_fraction_7d")
    features["event_mean_temp"] = numeric_series(events, "event_mean_temp")
    features["antecedent_mean_temp_7d"] = numeric_series(events, "antecedent_mean_temp_7d")
    features["rising_time_hours"] = numeric_series(events, "rising_time_hours")
    features["event_duration_hours"] = numeric_series(events, "event_duration_hours")
    features["event_runoff_coefficient"] = numeric_series(events, "event_runoff_coefficient")

    for col in RATIO_FEATURES:
        features[col] = features[col].clip(lower=0).fillna(0.0)
    for col in FRACTION_FEATURES:
        features[col] = features[col].clip(lower=0, upper=1).fillna(0.0)
    for col in SHAPE_FEATURES:
        features[col] = features[col].clip(lower=0)
        features[col] = features[col].fillna(median_or_zero(features[col]))
    for col in TEMPERATURE_FEATURES:
        features[col] = features[col].fillna(median_or_zero(features[col]))

    return features[FEATURE_COLUMNS].astype(float)


def transform_features(features: pd.DataFrame) -> tuple[pd.DataFrame, RobustScaler, np.ndarray]:
    transformed = features.copy()
    for col in LOG1P_FEATURES:
        transformed[col] = np.log1p(transformed[col].clip(lower=0))

    scaler = RobustScaler()
    matrix = scaler.fit_transform(transformed)
    return transformed, scaler, matrix


def interpret_cluster(row: pd.Series) -> tuple[str, str]:
    recent_strength = max(float(row["recent_1d_ratio_median"]), float(row["recent_3d_ratio_median"]))
    antecedent_strength = max(
        float(row["antecedent_7d_ratio_median"]),
        float(row["antecedent_30d_ratio_median"]),
    )
    snow_upper_strength = max(float(row["snowmelt_ratio_p90"]), float(row["snowmelt_fraction_p90"]) * 3.0)
    duration_median = float(row["event_duration_hours_median"])
    rising_median = float(row["rising_time_hours_median"])

    if antecedent_strength >= 1.0 and (duration_median >= 48.0 or rising_median >= 24.0):
        return (
            "antecedent_precipitation_like",
            "Antecedent rainfall ratios are high and the hydrograph is comparatively long.",
        )
    if snow_upper_strength >= 1.0:
        return (
            "snowmelt_or_rain_on_snow_proxy_like",
            "Upper-tail cluster members have a strong degree-day snowmelt ratio or snowmelt fraction.",
        )
    if recent_strength >= 0.75:
        return (
            "recent_precipitation_like",
            "Recent 1-day or 3-day rainfall ratio is the strongest cluster-level driver.",
        )
    return (
        "uncertain_or_mixed_like",
        "No cluster-level driver median is clearly high; interpret as weak-driver or mixed high-flow candidates.",
    )


def summarize_clusters(events: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    working = pd.concat([events[["ml_cluster"]], features], axis=1)
    for cluster_id, group in working.groupby("ml_cluster", sort=True):
        row: dict[str, Any] = {
            "ml_cluster": int(cluster_id),
            "event_count": int(len(group)),
            "event_share": float(len(group) / len(working)),
        }
        for col in FEATURE_COLUMNS:
            row[f"{col}_mean"] = float(group[col].mean())
            row[f"{col}_median"] = float(group[col].median())
            row[f"{col}_p75"] = float(group[col].quantile(0.75))
            row[f"{col}_p90"] = float(group[col].quantile(0.90))
        label, note = interpret_cluster(pd.Series(row))
        row["interpreted_ml_label"] = label
        row["interpretation_note"] = note
        rows.append(row)
    return pd.DataFrame(rows)


def select_existing_columns(df: pd.DataFrame, columns: list[str]) -> list[str]:
    return [col for col in columns if col in df.columns]


def attach_cluster_labels(events: pd.DataFrame, cluster_summary: pd.DataFrame) -> pd.DataFrame:
    label_lookup = cluster_summary.set_index("ml_cluster")["interpreted_ml_label"].to_dict()
    events = events.copy()
    events["interpreted_ml_label"] = events["ml_cluster"].map(label_lookup)
    return events


def summarize_basins(clustered_events: pd.DataFrame, dominance_threshold: float) -> pd.DataFrame:
    metadata_cols = select_existing_columns(
        clustered_events,
        ["gauge_name", "state", "huc02", "drain_sqkm_attr", "area", "snow_fraction"],
    )
    cluster_ids = sorted(int(item) for item in clustered_events["ml_cluster"].dropna().unique())
    labels = sorted(str(item) for item in clustered_events["interpreted_ml_label"].dropna().unique())
    rows: list[dict[str, Any]] = []

    for gauge_id, group in clustered_events.groupby("gauge_id", sort=True):
        event_count = int(len(group))
        cluster_counts = group["ml_cluster"].value_counts()
        label_counts = group["interpreted_ml_label"].value_counts()
        dominant_cluster = int(cluster_counts.idxmax())
        dominant_cluster_share = float(cluster_counts.max() / event_count)
        dominant_label_if_any = str(label_counts.idxmax())
        dominant_label_share = float(label_counts.max() / event_count)

        row: dict[str, Any] = {
            "gauge_id": gauge_id,
            "event_count": event_count,
            "dominant_ml_cluster": (
                dominant_cluster if dominant_cluster_share >= dominance_threshold else "mixture"
            ),
            "dominant_ml_cluster_if_any": dominant_cluster,
            "dominant_ml_cluster_share": dominant_cluster_share,
            "dominant_ml_label": (
                dominant_label_if_any if dominant_label_share >= dominance_threshold else "mixture"
            ),
            "dominant_ml_label_if_any": dominant_label_if_any,
            "dominant_ml_label_share": dominant_label_share,
        }
        for cluster_id in cluster_ids:
            count = int(cluster_counts.get(cluster_id, 0))
            row[f"cluster_{cluster_id}_count"] = count
            row[f"cluster_{cluster_id}_share"] = float(count / event_count)
        for label in labels:
            safe_label = label.replace("/", "_").replace("-", "_")
            count = int(label_counts.get(label, 0))
            row[f"{safe_label}_count"] = count
            row[f"{safe_label}_share"] = float(count / event_count)

        first = group.iloc[0]
        for col in metadata_cols:
            row[col] = first.get(col, pd.NA)
        rows.append(row)

    leading = ["gauge_id", *metadata_cols, "event_count"]
    remaining = [col for col in rows[0].keys() if col not in leading] if rows else []
    return pd.DataFrame(rows, columns=[*leading, *remaining])


def read_rule_labels(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    header = pd.read_csv(path, nrows=0)
    desired = [
        "gauge_id",
        "event_id",
        "flood_generation_method",
        "flood_generation_type",
        "flood_generation_subtype",
        "low_confidence_type_flag",
    ]
    usecols = [col for col in desired if col in header.columns]
    if "gauge_id" not in usecols or "event_id" not in usecols or "flood_generation_type" not in usecols:
        return None
    rules = pd.read_csv(path, usecols=usecols, dtype={"gauge_id": str})
    rules["gauge_id"] = rules["gauge_id"].map(fu.normalize_gauge_id)
    return rules


def compare_with_rule_labels(clustered_events: pd.DataFrame, rule_typing_csv: Path) -> tuple[pd.DataFrame | None, dict]:
    rules = read_rule_labels(rule_typing_csv)
    if rules is None:
        return None, {"rule_typing_csv": str(rule_typing_csv), "available": False}

    keys = ["gauge_id", "event_id"]
    comparison = clustered_events.merge(rules, on=keys, how="left", validate="one_to_one")
    valid = comparison["flood_generation_type"].notna() & comparison["interpreted_ml_label"].notna()
    metrics: dict[str, Any] = {
        "rule_typing_csv": str(rule_typing_csv),
        "available": True,
        "matched_event_count": int(valid.sum()),
        "unmatched_event_count": int((~valid).sum()),
    }
    if valid.sum() > 1:
        metrics["adjusted_rand_index"] = float(
            adjusted_rand_score(
                comparison.loc[valid, "flood_generation_type"],
                comparison.loc[valid, "ml_cluster"],
            )
        )
        metrics["normalized_mutual_information"] = float(
            normalized_mutual_info_score(
                comparison.loc[valid, "flood_generation_type"],
                comparison.loc[valid, "ml_cluster"],
            )
        )
    return comparison, metrics


def write_rule_crosstab(comparison: pd.DataFrame, path: Path) -> None:
    valid = comparison["flood_generation_type"].notna() & comparison["interpreted_ml_label"].notna()
    if not valid.any():
        pd.DataFrame().to_csv(path, index=False)
        return
    counts = pd.crosstab(
        comparison.loc[valid, "flood_generation_type"],
        comparison.loc[valid, "interpreted_ml_label"],
    )
    shares = pd.crosstab(
        comparison.loc[valid, "flood_generation_type"],
        comparison.loc[valid, "interpreted_ml_label"],
        normalize="index",
    )
    counts = counts.add_prefix("count__")
    shares = shares.add_prefix("row_share__")
    table = pd.concat([counts, shares], axis=1).reset_index()
    table.to_csv(path, index=False)


def main() -> None:
    args = parse_args()
    if args.n_clusters < 2:
        raise SystemExit("--n-clusters must be at least 2.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    events = read_events(args.event_response_csv, args.limit)
    if len(events) < args.n_clusters:
        raise SystemExit(f"Need at least {args.n_clusters} events for KMeans; found {len(events)}.")

    features = build_feature_table(events)
    transformed, scaler, matrix = transform_features(features)
    model = KMeans(n_clusters=args.n_clusters, n_init="auto", random_state=args.random_state)
    events = events.copy()
    events["ml_cluster"] = model.fit_predict(matrix)

    cluster_summary = summarize_clusters(events, features)
    clustered_events = attach_cluster_labels(events, cluster_summary)
    basin_summary = summarize_basins(clustered_events, args.dominance_threshold)

    metadata_cols = select_existing_columns(clustered_events, METADATA_COLUMNS)
    event_feature_output = pd.concat([clustered_events[metadata_cols], features], axis=1)
    event_cluster_output = pd.concat(
        [
            clustered_events[
                [
                    *metadata_cols,
                    "ml_cluster",
                    "interpreted_ml_label",
                ]
            ],
            features,
        ],
        axis=1,
    )

    feature_path = args.output_dir / "event_ml_features.parquet"
    cluster_path = args.output_dir / "event_ml_clusters.csv"
    basin_path = args.output_dir / "basin_ml_cluster_summary.csv"
    centroid_path = args.output_dir / "kmeans_cluster_centroids.csv"
    transformed_path = args.output_dir / "event_ml_transformed_features.csv"
    comparison_path = args.output_dir / "event_rule_vs_ml_comparison.csv"
    crosstab_path = args.output_dir / "rule_vs_ml_crosstab.csv"
    summary_path = args.output_dir / "flood_generation_ml_clustering_summary.json"

    event_feature_output.to_parquet(feature_path, index=False)
    event_cluster_output.to_csv(cluster_path, index=False)
    basin_summary.to_csv(basin_path, index=False)
    cluster_summary.to_csv(centroid_path, index=False)
    pd.concat([clustered_events[metadata_cols + ["ml_cluster"]], transformed], axis=1).to_csv(
        transformed_path,
        index=False,
    )

    comparison, comparison_metrics = compare_with_rule_labels(
        clustered_events[[*metadata_cols, "ml_cluster", "interpreted_ml_label"]],
        args.rule_typing_csv,
    )
    if comparison is not None:
        comparison.to_csv(comparison_path, index=False)
        write_rule_crosstab(comparison, crosstab_path)

    cluster_counts = clustered_events["ml_cluster"].value_counts().sort_index().to_dict()
    label_counts = clustered_events["interpreted_ml_label"].value_counts().to_dict()
    summary = {
        "event_response_csv": str(args.event_response_csv),
        "rule_typing_csv": str(args.rule_typing_csv),
        "method": "kmeans",
        "n_clusters": args.n_clusters,
        "random_state": args.random_state,
        "kmeans_inertia": float(model.inertia_),
        "kmeans_n_iter": int(model.n_iter_),
        "scaler": "RobustScaler",
        "log1p_features": LOG1P_FEATURES,
        "feature_columns": FEATURE_COLUMNS,
        "event_count": int(len(clustered_events)),
        "basin_count": int(len(basin_summary)),
        "dominance_threshold": args.dominance_threshold,
        "cluster_counts": {str(key): int(value) for key, value in cluster_counts.items()},
        "interpreted_label_counts": {str(key): int(value) for key, value in label_counts.items()},
        "comparison_with_rule_typing": comparison_metrics,
        "outputs": {
            "event_ml_features": str(feature_path),
            "event_ml_clusters": str(cluster_path),
            "basin_ml_cluster_summary": str(basin_path),
            "kmeans_cluster_centroids": str(centroid_path),
            "event_ml_transformed_features": str(transformed_path),
            "event_rule_vs_ml_comparison": str(comparison_path) if comparison is not None else None,
            "rule_vs_ml_crosstab": str(crosstab_path) if comparison is not None else None,
        },
        "notes": [
            "This is optional exploratory descriptor-space clustering, not an official flood occurrence label.",
            "Interpreted ML labels are assigned from cluster-level feature medians and snowmelt upper-tail summaries; read them as proxy-like groups.",
        ],
    }
    summary_path.write_text(json.dumps(json_safe(summary), indent=2), encoding="utf-8")

    print(f"Wrote event ML features: {feature_path}")
    print(f"Wrote event ML clusters: {cluster_path}")
    print(f"Wrote basin ML cluster summary: {basin_path}")
    print(f"Wrote KMeans cluster centroids: {centroid_path}")
    if comparison is not None:
        print(f"Wrote rule-vs-ML comparison: {comparison_path}")
        print(f"Wrote rule-vs-ML crosstab: {crosstab_path}")
    print(f"Wrote summary: {summary_path}")


if __name__ == "__main__":
    main()
