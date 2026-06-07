#!/usr/bin/env python3
"""Core helpers for SHAP direction analysis outputs."""

from __future__ import annotations

from math import log2
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd

STATIC_FEATURES: Final[list[str]] = [
    "area",
    "slope",
    "aridity",
    "forest_fraction",
    "soil_depth",
    "permeability",
    "snow_fraction",
    "baseflow_index",
]
FORCING_COLUMNS: Final[dict[str, str]] = {
    "event_total_rainf": "event_forcing_summary_total_rainf",
    "event_peak_rainf_intensity": "event_forcing_summary_peak_rainf_intensity",
    "event_duration_h": "event_forcing_summary_duration_h",
    "antecedent_rainf_5d": "event_forcing_summary_antecedent_rainf_5d",
    "event_mean_cape": "event_forcing_summary_mean_cape",
    "event_max_cape": "event_forcing_summary_max_cape",
    "antecedent_tair_mean": "event_forcing_summary_antecedent_tair_mean",
}
MATRIX_COLUMNS: Final[list[str]] = [
    "scope",
    "seed",
    "quantile",
    "basin",
    "event_id",
    "anchor_time",
    "event_start",
    "event_end",
    "feature_group",
    "feature",
    "flow_stratum",
    "feature_value",
    "feature_value_source",
    "feature_value_band",
    "mean_abs_shap",
    "mean_signed_shap",
    "max_abs_shap",
    "shap_sign",
    "event_forcing_scope",
    *FORCING_COLUMNS.values(),
]
ISSUE_COLUMNS: Final[list[str]] = ["issue_type", "scope", "seed", "basin", "event_id", "detail"]


def normalize_basin_id(value: object) -> str:
    """Return CAMELS gauge ids as zero-padded 8 digit strings."""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits.zfill(8)


def read_csv(path: Path) -> pd.DataFrame:
    """Read project CSVs while tolerating metadata comments."""
    return pd.read_csv(path, comment="#")


def _prepare_static(static_attributes: pd.DataFrame) -> pd.DataFrame:
    static = static_attributes.copy()
    if "gauge_id" in static.columns:
        static = static.rename(columns={"gauge_id": "basin"})
    static["basin"] = static["basin"].map(normalize_basin_id)
    return static[["basin", *[feature for feature in STATIC_FEATURES if feature in static.columns]]]


def _prepare_forcing(q99_forcing: pd.DataFrame) -> pd.DataFrame:
    forcing = q99_forcing.copy()
    if forcing.empty:
        return pd.DataFrame(columns=["seed", "basin", "event_id", "event_end", *FORCING_COLUMNS.values()])
    forcing["basin"] = forcing["basin"].map(normalize_basin_id)
    forcing = forcing.rename(columns=FORCING_COLUMNS)
    keep = ["seed", "basin", "event_id", "event_end", *FORCING_COLUMNS.values()]
    return forcing[[column for column in keep if column in forcing.columns]].drop_duplicates()


def _shap_sign(value: float) -> str:
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "zero"


def _append_timestamp_issues(frame: pd.DataFrame, issues: list[dict[str, object]]) -> None:
    for column in ["anchor_time", "event_end"]:
        if column in frame.columns:
            missing = frame[column].isna() | frame[column].astype(str).eq("")
        else:
            missing = pd.Series(True, index=frame.index)
        for _, row in frame.loc[missing].iterrows():
            issues.append(
                {
                    "issue_type": "timestamp_fallback_used",
                    "scope": row.get("scope", ""),
                    "seed": row.get("seed", ""),
                    "basin": row.get("basin", ""),
                    "event_id": row.get("event_id", ""),
                    "detail": f"missing {column}",
                }
            )


def build_direction_event_feature_matrix(
    *,
    event_shap: pd.DataFrame,
    static_attributes: pd.DataFrame,
    q99_forcing: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Merge SHAP event rows with static attributes and q99 forcing summaries."""
    issues: list[dict[str, object]] = []
    frame = event_shap.copy()
    frame["basin"] = frame["basin"].map(normalize_basin_id)
    for column in ["event_start", "event_end", "anchor_time"]:
        if column not in frame.columns:
            frame[column] = pd.NA
    _append_timestamp_issues(frame, issues)
    static = _prepare_static(static_attributes)
    frame = frame.merge(static, on="basin", how="left", suffixes=("", "_static"))
    frame["feature_value"] = np.nan
    frame["feature_value_source"] = "not_available_dynamic"
    frame["feature_value_band"] = "not_applicable_dynamic"
    for feature in STATIC_FEATURES:
        mask = frame["feature"].eq(feature) & frame["feature_group"].eq("static_attribute")
        if feature in frame.columns:
            frame.loc[mask, "feature_value"] = frame.loc[mask, feature]
            frame.loc[mask, "feature_value_source"] = "static_attribute"
    frame["shap_sign"] = frame["mean_signed_shap"].map(_shap_sign)
    for (scope, feature), indexes in frame.loc[frame["feature_value_source"].eq("static_attribute")].groupby(["scope", "feature"]).groups.items():
        del scope
        median = frame.loc[indexes, "feature_value"].median()
        frame.loc[indexes, "feature_value_band"] = np.where(frame.loc[indexes, "feature_value"] >= median, "feature_high", "feature_low")
    forcing = _prepare_forcing(q99_forcing)
    q99_mask = frame["scope"].eq("q99")
    merged = frame.loc[q99_mask].merge(forcing, on=["seed", "basin", "event_id", "event_end"], how="left")
    merged["event_forcing_scope"] = np.where(merged["event_forcing_summary_total_rainf"].notna(), "q99_matched", "q99_missing")
    for _, row in merged.loc[merged["event_forcing_scope"].eq("q99_missing")].iterrows():
        issues.append({"issue_type": "missing_forcing", "scope": "q99", "seed": row["seed"], "basin": row["basin"], "event_id": row["event_id"], "detail": "no q99 forcing row for composite key"})
    non_q99 = frame.loc[~q99_mask].copy()
    non_q99["event_forcing_scope"] = "not_applicable_test_split"
    for column in FORCING_COLUMNS.values():
        if column not in merged.columns:
            merged[column] = np.nan
        non_q99[column] = np.nan
    matrix = pd.concat([merged, non_q99], ignore_index=True, sort=False)
    for column in MATRIX_COLUMNS:
        if column not in matrix.columns:
            matrix[column] = pd.NA
    output = matrix[MATRIX_COLUMNS].sort_values(["scope", "seed", "basin", "event_id", "quantile", "feature"]).reset_index(drop=True)
    return output, pd.DataFrame(issues, columns=ISSUE_COLUMNS)


def sign_entropy(series: pd.Series) -> float:
    """Compute binary sign entropy over positive/negative signs."""
    counts = series[series.isin(["positive", "negative"])].value_counts()
    total = counts.sum()
    if total == 0:
        return 0.0
    return float(sum(-count / total * log2(count / total) for count in counts))


def outlier_share(frame: pd.DataFrame) -> float:
    total = frame["mean_abs_shap"].abs().sum()
    if total == 0:
        return 0.0
    by_event = frame.groupby(["basin", "event_id"])["mean_abs_shap"].apply(lambda values: values.abs().sum())
    return float(by_event.max() / total)


def build_quadrant_summary(matrix: pd.DataFrame) -> pd.DataFrame:
    static = matrix[matrix["feature_value_source"].eq("static_attribute")].copy()
    static = static[static["shap_sign"].isin(["positive", "negative"])]
    static["quadrant_label"] = static["feature_value_band"] + "_shap_" + static["shap_sign"]
    event_totals = static.groupby(["scope", "quantile", "feature"])[["basin", "event_id"]].apply(lambda group: group.drop_duplicates().shape[0])
    row_totals = static.groupby(["scope", "quantile", "feature"]).size()
    grouped = []
    for keys, group in static.groupby(["scope", "quantile", "feature", "quadrant_label"], dropna=False):
        base_key = keys[:3]
        n_events = group[["basin", "event_id"]].drop_duplicates().shape[0]
        grouped.append({"scope": keys[0], "quantile": keys[1], "feature": keys[2], "quadrant_label": keys[3], "n_rows": len(group), "n_events": n_events, "n_seeds": group["seed"].nunique(), "row_share": len(group) / row_totals.loc[base_key], "event_share": n_events / event_totals.loc[base_key], "median_abs_shap": group["mean_abs_shap"].median(), "median_signed_shap": group["mean_signed_shap"].median(), "positive_fraction": float(group["shap_sign"].eq("positive").mean()), "negative_fraction": float(group["shap_sign"].eq("negative").mean()), "sign_entropy": sign_entropy(group["shap_sign"]), "abs_shap_outlier_share": outlier_share(group), "insufficient_support": n_events < 20})
    return pd.DataFrame(grouped)


def build_type_candidates(quadrant_summary: pd.DataFrame) -> pd.DataFrame:
    labels = {"area": "큰 유역 scaling형", "slope": "경사 민감형", "soil_depth": "저장·완충형", "permeability": "저장·완충형", "baseflow_index": "저장·완충형", "forest_fraction": "산림/토양 조절형", "snow_fraction": "눈/계절성 영향형"}
    rows = []
    for _, row in quadrant_summary.iterrows():
        insufficient = bool(row.get("n_events", 0) < 20 or row.get("n_seeds", 0) < 2)
        outlier = bool(row.get("abs_shap_outlier_share", 1.0) >= 0.4)
        conflict = bool(row.get("test_split_direction_conflict", False))
        label = "" if insufficient or outlier else labels.get(str(row.get("feature", "")), "")
        rows.append({**row.to_dict(), "candidate_label_ko": label, "insufficient_support": insufficient, "outlier_dominated": outlier, "q99_specific_only": conflict})
    result = pd.DataFrame(rows)
    for column in ["insufficient_support", "outlier_dominated", "q99_specific_only"]:
        if column in result:
            result[column] = result[column].astype(object)
    return result
