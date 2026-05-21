#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.8",
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "scikit-learn>=1.4",
#   "shap>=0.45",
# ]
# ///

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EVENT_TABLE = (
    REPO_ROOT
    / "output/model_analysis/quantile_analysis/event_regime_analysis/event_regime_error_table_wide.csv"
)
DEFAULT_STATIC_ATTRIBUTES = (
    REPO_ROOT / "data/CAMELSH_generic/drbc_holdout_broad/attributes/static_attributes.csv"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/quantile_analysis/event_surrogate_shap"

HYDROMET_FEATURES = [
    "recent_1d_ratio",
    "recent_3d_ratio",
    "antecedent_7d_ratio",
    "antecedent_30d_ratio",
    "snowmelt_ratio",
    "snowmelt_fraction",
    "event_mean_temp",
    "rising_time_hours",
    "event_duration_hours",
    "unit_area_peak",
    "peak_month",
]
STATIC_FEATURES = [
    "area",
    "slope",
    "aridity",
    "snow_fraction",
    "soil_depth",
    "permeability",
    "baseflow_index",
    "forest_fraction",
]
CATEGORICAL_FEATURES = [
    "ml_event_regime",
    "flood_relevance_tier",
    "selected_threshold_quantile",
]
NUMERIC_FEATURES = HYDROMET_FEATURES + STATIC_FEATURES
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

TARGET_COLUMNS = {
    "model1_under_deficit_pct": "Mean Model 1 observed-peak under-deficit (%)",
    "q95_under_deficit_reduction_pct": "Mean q95 under-deficit reduction vs Model 1 (percentage points)",
    "q99_under_deficit_reduction_pct": "Mean q99 under-deficit reduction vs Model 1 (percentage points)",
    "q99_nrmse_tradeoff_pct": "Mean q99 event NRMSE tradeoff vs Model 1 (percentage points)",
    "q99_overprediction_pct": "Mean positive q99 observed-peak relative error (%)",
}
REQUIRED_EVENT_COLUMNS = [
    "gauge_id",
    "event_id",
    "model1_obs_peak_under_deficit_pct",
    "q95_obs_peak_under_deficit_pct",
    "q99_obs_peak_under_deficit_pct",
    "model1_event_nrmse_pct",
    "q99_event_nrmse_pct",
]


@dataclass(frozen=True)
class TargetResult:
    target: str
    model: Any
    preprocessor: Any
    feature_names: list[str]
    shap_values: np.ndarray
    expected_value: float
    diagnostics: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build event-level RandomForest surrogate SHAP analyses for subset300 "
            "Model 1 vs Model 2 quantile high-flow event errors."
        )
    )
    parser.add_argument("--event-table", type=Path, default=DEFAULT_EVENT_TABLE)
    parser.add_argument("--static-attributes", type=Path, default=DEFAULT_STATIC_ATTRIBUTES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--random-state", type=int, default=20260518)
    parser.add_argument("--n-estimators", type=int, default=500)
    parser.add_argument("--min-samples-leaf", type=int, default=5)
    parser.add_argument("--n-splits", type=int, default=5)
    parser.add_argument("--n-repeats", type=int, default=3)
    parser.add_argument("--top-local-events", type=int, default=25)
    parser.add_argument("--top-features", type=int, default=18)
    return parser.parse_args()


def normalize_gauge_id(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(8)


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


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


def require_columns(df: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {', '.join(missing)}")


def read_event_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing event-regime wide table: {path}")
    df = pd.read_csv(path, dtype={"gauge_id": str})
    require_columns(df, REQUIRED_EVENT_COLUMNS, str(path))
    df["gauge_id"] = df["gauge_id"].map(normalize_gauge_id)
    return df


def read_static_attributes(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing static attributes table: {path}")
    attrs = pd.read_csv(path, dtype={"gauge_id": str})
    require_columns(attrs, ["gauge_id", *STATIC_FEATURES], str(path))
    attrs["gauge_id"] = attrs["gauge_id"].map(normalize_gauge_id)
    keep = ["gauge_id", *STATIC_FEATURES]
    attrs = attrs[keep].copy()
    for col in STATIC_FEATURES:
        attrs[col] = pd.to_numeric(attrs[col], errors="coerce")
    if attrs["gauge_id"].duplicated().any():
        duplicated = int(attrs["gauge_id"].duplicated().sum())
        raise ValueError(f"Static attributes contain {duplicated} duplicated gauge_id rows.")
    return attrs


def _first_non_null(series: pd.Series) -> Any:
    values = series.dropna()
    if values.empty:
        return np.nan
    return values.iloc[0]


def _mode_or_first(series: pd.Series) -> Any:
    values = series.dropna()
    if values.empty:
        return "missing"
    modes = values.mode()
    if modes.empty:
        return values.iloc[0]
    return modes.sort_values().iloc[0]


def _mean_positive(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values.clip(lower=0).mean())


def aggregate_to_event_level(seed_rows: pd.DataFrame, static_attrs: pd.DataFrame) -> pd.DataFrame:
    work = seed_rows.copy()
    numeric_source_cols = [
        "model1_obs_peak_under_deficit_pct",
        "q95_obs_peak_under_deficit_pct",
        "q99_obs_peak_under_deficit_pct",
        "model1_event_nrmse_pct",
        "q99_event_nrmse_pct",
        "q99_obs_peak_rel_error_pct",
        *HYDROMET_FEATURES,
    ]
    for col in numeric_source_cols:
        if col in work.columns:
            work[col] = pd.to_numeric(work[col], errors="coerce")

    group_cols = ["gauge_id", "event_id"]
    grouped = work.groupby(group_cols, dropna=False, sort=False)
    base = grouped.size().rename("seed_row_count").reset_index()
    base["seed_count"] = grouped["seed"].nunique().to_numpy() if "seed" in work.columns else base["seed_row_count"]

    first_cols = [
        "gauge_name",
        "state",
        "huc02",
        "event_start",
        "event_peak",
        "event_end",
        "water_year",
        "selected_threshold_value",
        "event_detection_basis",
        "event_candidate_label",
        "flood_relevance_basis",
        "return_period_confidence_flag",
        "rule_label",
        "ml_cluster_id",
        "comparison",
        "model1_epoch",
        "model2_epoch",
    ]
    for col in first_cols:
        if col in work.columns:
            base[col] = grouped[col].agg(_first_non_null).to_numpy()

    for col in CATEGORICAL_FEATURES:
        if col in work.columns:
            base[col] = grouped[col].agg(_mode_or_first).to_numpy()
        else:
            base[col] = "missing"

    for col in HYDROMET_FEATURES:
        if col in work.columns:
            base[col] = grouped[col].median().to_numpy()
        else:
            base[col] = np.nan

    model1_under = grouped["model1_obs_peak_under_deficit_pct"].mean()
    q95_under = grouped["q95_obs_peak_under_deficit_pct"].mean()
    q99_under = grouped["q99_obs_peak_under_deficit_pct"].mean()
    model1_nrmse = grouped["model1_event_nrmse_pct"].mean()
    q99_nrmse = grouped["q99_event_nrmse_pct"].mean()
    base["model1_under_deficit_pct"] = model1_under.to_numpy()
    base["q95_under_deficit_reduction_pct"] = (model1_under - q95_under).to_numpy()
    base["q99_under_deficit_reduction_pct"] = (model1_under - q99_under).to_numpy()
    base["q99_nrmse_tradeoff_pct"] = (q99_nrmse - model1_nrmse).to_numpy()
    if "q99_obs_peak_rel_error_pct" in work.columns:
        base["q99_overprediction_pct"] = grouped["q99_obs_peak_rel_error_pct"].agg(_mean_positive).to_numpy()
    else:
        base["q99_overprediction_pct"] = np.nan

    merged = base.merge(static_attrs, on="gauge_id", how="left", validate="many_to_one")
    missing_static = int(merged[STATIC_FEATURES].isna().all(axis=1).sum())
    if missing_static:
        raise ValueError(f"{missing_static} event rows did not match static attributes by gauge_id.")
    for col in NUMERIC_FEATURES:
        merged[col] = pd.to_numeric(merged[col], errors="coerce")
    for col in CATEGORICAL_FEATURES:
        merged[col] = merged[col].fillna("missing").astype(str)
    return merged


def make_preprocessor():
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, NUMERIC_FEATURES),
            ("cat", categorical_pipeline, CATEGORICAL_FEATURES),
        ],
        verbose_feature_names_out=False,
    )


def transformed_feature_names(preprocessor: Any) -> list[str]:
    names = list(preprocessor.get_feature_names_out())
    return [str(name) for name in names]


def cross_validate_target(
    X: pd.DataFrame,
    y: pd.Series,
    *,
    n_splits: int,
    n_repeats: int,
    random_state: int,
    n_estimators: int,
    min_samples_leaf: int,
) -> pd.DataFrame:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_absolute_error, r2_score
    from sklearn.model_selection import RepeatedKFold

    n_samples = len(y)
    split_count = min(n_splits, n_samples)
    if split_count < 2:
        raise ValueError(f"Need at least 2 samples for surrogate diagnostics, found {n_samples}.")
    rows: list[dict[str, Any]] = []
    cv = RepeatedKFold(n_splits=split_count, n_repeats=n_repeats, random_state=random_state)
    for fold_idx, (train_idx, test_idx) in enumerate(cv.split(X), start=1):
        preprocessor = make_preprocessor()
        X_train = preprocessor.fit_transform(X.iloc[train_idx])
        X_test = preprocessor.transform(X.iloc[test_idx])
        model = RandomForestRegressor(
            n_estimators=n_estimators,
            min_samples_leaf=min_samples_leaf,
            random_state=random_state + fold_idx,
            n_jobs=-1,
        )
        model.fit(X_train, y.iloc[train_idx])
        prediction = model.predict(X_test)
        truth = y.iloc[test_idx].to_numpy(dtype=float)
        rows.append(
            {
                "fold": fold_idx,
                "n_train": int(len(train_idx)),
                "n_test": int(len(test_idx)),
                "r2": float(r2_score(truth, prediction)) if len(test_idx) > 1 else math.nan,
                "mae": float(mean_absolute_error(truth, prediction)),
                "target_mean_test": float(np.mean(truth)),
                "prediction_mean_test": float(np.mean(prediction)),
            }
        )
    return pd.DataFrame(rows)


def fit_target_surrogate(
    event_table: pd.DataFrame,
    target: str,
    *,
    n_splits: int,
    n_repeats: int,
    random_state: int,
    n_estimators: int,
    min_samples_leaf: int,
) -> TargetResult:
    import shap
    from sklearn.ensemble import RandomForestRegressor

    model_frame = event_table[[*FEATURES, target]].copy()
    model_frame[target] = pd.to_numeric(model_frame[target], errors="coerce")
    model_frame = model_frame.dropna(subset=[target]).reset_index(drop=True)
    if len(model_frame) < 10:
        raise ValueError(f"Target {target} has too few non-missing events: {len(model_frame)}")

    X = model_frame[FEATURES]
    y = model_frame[target]
    cv_rows = cross_validate_target(
        X,
        y,
        n_splits=n_splits,
        n_repeats=n_repeats,
        random_state=random_state,
        n_estimators=n_estimators,
        min_samples_leaf=min_samples_leaf,
    )
    preprocessor = make_preprocessor()
    X_transformed = preprocessor.fit_transform(X)
    feature_names = transformed_feature_names(preprocessor)
    model = RandomForestRegressor(
        n_estimators=n_estimators,
        min_samples_leaf=min_samples_leaf,
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(X_transformed, y)
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_transformed)
    expected_value = explainer.expected_value
    if isinstance(expected_value, np.ndarray):
        expected = float(expected_value.ravel()[0])
    else:
        expected = float(expected_value)

    diagnostics = {
        "n_events": int(len(model_frame)),
        "n_features_raw": int(len(FEATURES)),
        "n_features_transformed": int(len(feature_names)),
        "target_mean": float(y.mean()),
        "target_median": float(y.median()),
        "target_sd": float(y.std(ddof=1)),
        "cv_r2_mean": float(cv_rows["r2"].mean(skipna=True)),
        "cv_r2_median": float(cv_rows["r2"].median(skipna=True)),
        "cv_r2_min": float(cv_rows["r2"].min(skipna=True)),
        "cv_r2_max": float(cv_rows["r2"].max(skipna=True)),
        "cv_mae_mean": float(cv_rows["mae"].mean()),
        "cv_mae_median": float(cv_rows["mae"].median()),
        "surrogate_warning": (
            "weak_or_unreliable_surrogate"
            if cv_rows["r2"].mean(skipna=True) < 0.2
            else "surrogate_has_some_predictive_signal"
        ),
        "fold_diagnostics": cv_rows.to_dict(orient="records"),
    }
    return TargetResult(
        target=target,
        model=model,
        preprocessor=preprocessor,
        feature_names=feature_names,
        shap_values=np.asarray(shap_values, dtype=float),
        expected_value=expected,
        diagnostics=diagnostics,
    )


def feature_importance(result: TargetResult) -> pd.DataFrame:
    shap_values = result.shap_values
    rows = []
    for idx, feature in enumerate(result.feature_names):
        values = shap_values[:, idx]
        rows.append(
            {
                "target": result.target,
                "target_label": TARGET_COLUMNS[result.target],
                "feature": feature,
                "mean_abs_shap": float(np.mean(np.abs(values))),
                "mean_shap": float(np.mean(values)),
            }
        )
    return pd.DataFrame(rows).sort_values(["target", "mean_abs_shap"], ascending=[True, False])


def local_top_events(event_table: pd.DataFrame, result: TargetResult, top_n: int) -> pd.DataFrame:
    target = result.target
    model_frame = event_table[[*FEATURES, "gauge_id", "event_id", target]].copy()
    model_frame[target] = pd.to_numeric(model_frame[target], errors="coerce")
    model_frame = model_frame.dropna(subset=[target]).reset_index(drop=True)
    X_transformed = result.preprocessor.transform(model_frame[FEATURES])
    predictions = result.model.predict(X_transformed)
    shap_values = result.shap_values
    abs_total = np.sum(np.abs(shap_values), axis=1)
    selected = np.argsort(abs_total)[::-1][:top_n]
    rows: list[dict[str, Any]] = []
    for rank, row_idx in enumerate(selected, start=1):
        values = shap_values[row_idx]
        feature_order = np.argsort(np.abs(values))[::-1][:5]
        row: dict[str, Any] = {
            "target": target,
            "target_label": TARGET_COLUMNS[target],
            "rank": rank,
            "gauge_id": model_frame.loc[row_idx, "gauge_id"],
            "event_id": model_frame.loc[row_idx, "event_id"],
            "target_value": float(model_frame.loc[row_idx, target]),
            "surrogate_prediction": float(predictions[row_idx]),
            "expected_value": result.expected_value,
            "total_abs_shap": float(abs_total[row_idx]),
            "ml_event_regime": model_frame.loc[row_idx, "ml_event_regime"],
            "flood_relevance_tier": model_frame.loc[row_idx, "flood_relevance_tier"],
        }
        for pos, feature_idx in enumerate(feature_order, start=1):
            row[f"top{pos}_feature"] = result.feature_names[feature_idx]
            row[f"top{pos}_shap"] = float(values[feature_idx])
        rows.append(row)
    return pd.DataFrame(rows)


def save_target_bar_chart(importance: pd.DataFrame, target: str, output_path: Path, top_features: int) -> None:
    frame = importance[importance["target"].eq(target)].head(top_features).iloc[::-1]
    fig_height = max(4.0, 0.28 * len(frame) + 1.2)
    fig, ax = plt.subplots(figsize=(8.5, fig_height))
    ax.barh(frame["feature"], frame["mean_abs_shap"], color="#2563eb")
    ax.set_xlabel("mean(|SHAP value|)")
    ax.set_title(TARGET_COLUMNS[target], fontsize=10)
    ax.grid(True, axis="x", color="#e5e7eb", linewidth=0.7)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def save_target_signed_bar_chart(
    importance: pd.DataFrame, target: str, output_path: Path, top_features: int
) -> None:
    frame = importance[importance["target"].eq(target)].head(top_features).iloc[::-1]
    values = frame["mean_shap"].to_numpy(dtype=float)
    colors = np.where(values >= 0, "#dc2626", "#2563eb")
    limit = max(float(np.nanmax(np.abs(values))) if len(values) else 0.0, 1e-9)

    fig_height = max(4.0, 0.28 * len(frame) + 1.2)
    fig, ax = plt.subplots(figsize=(8.5, fig_height))
    ax.barh(frame["feature"], values, color=colors)
    ax.axvline(0, color="#111827", linewidth=0.9)
    ax.set_xlim(-limit * 1.12, limit * 1.12)
    ax.set_xlabel("mean SHAP value")
    ax.set_title(TARGET_COLUMNS[target], fontsize=10)
    ax.grid(True, axis="x", color="#e5e7eb", linewidth=0.7)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def save_combined_chart(importance: pd.DataFrame, output_path: Path, top_features: int) -> None:
    targets = list(TARGET_COLUMNS)
    fig, axes = plt.subplots(len(targets), 1, figsize=(9.5, 3.1 * len(targets)))
    for ax, target in zip(np.atleast_1d(axes), targets, strict=True):
        frame = importance[importance["target"].eq(target)].head(top_features).iloc[::-1]
        ax.barh(frame["feature"], frame["mean_abs_shap"], color="#2563eb")
        ax.set_title(TARGET_COLUMNS[target], fontsize=9)
        ax.set_xlabel("mean(|SHAP value|)")
        ax.grid(True, axis="x", color="#e5e7eb", linewidth=0.7)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def save_combined_signed_chart(importance: pd.DataFrame, output_path: Path, top_features: int) -> None:
    targets = list(TARGET_COLUMNS)
    fig, axes = plt.subplots(len(targets), 1, figsize=(9.5, 3.1 * len(targets)))
    for ax, target in zip(np.atleast_1d(axes), targets, strict=True):
        frame = importance[importance["target"].eq(target)].head(top_features).iloc[::-1]
        values = frame["mean_shap"].to_numpy(dtype=float)
        colors = np.where(values >= 0, "#dc2626", "#2563eb")
        limit = max(float(np.nanmax(np.abs(values))) if len(values) else 0.0, 1e-9)

        ax.barh(frame["feature"], values, color=colors)
        ax.axvline(0, color="#111827", linewidth=0.9)
        ax.set_xlim(-limit * 1.12, limit * 1.12)
        ax.set_title(TARGET_COLUMNS[target], fontsize=9)
        ax.set_xlabel("mean SHAP value")
        ax.grid(True, axis="x", color="#e5e7eb", linewidth=0.7)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def write_report(
    path: Path,
    *,
    event_table: pd.DataFrame,
    diagnostics: pd.DataFrame,
    importance: pd.DataFrame,
    local: pd.DataFrame,
    output_dir: Path,
) -> None:
    lines = [
        "# Event-Level Surrogate SHAP Analysis",
        "",
        "이 보고서는 Model 1과 Model 2 quantile high-flow event 결과를 event 단위로 접은 뒤, 각 error target을 RandomForest surrogate로 근사하고 그 surrogate에 대한 SHAP 값을 계산한 결과입니다.",
        "",
        "중요한 해석 제한이 있습니다. 여기서 SHAP은 원래 LSTM이나 quantile head의 인과적 설명이 아니라, event-level descriptor와 static attribute로 만든 surrogate error model의 설명입니다. surrogate R2가 낮거나 음수인 target은 feature ranking을 강한 설명으로 읽으면 안 됩니다.",
        "",
        "## Scope",
        "",
        f"- Event-level samples: {len(event_table)} events across {event_table['gauge_id'].nunique()} basins.",
        f"- Output directory: `{relative_path(output_dir)}`.",
        "- Seed rows were aggregated before modeling, so the three seed rows for one event were not treated as independent samples.",
        "",
        "## Surrogate Diagnostics",
        "",
        "| target | n_events | cv_r2_mean | cv_mae_mean | warning |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for row in diagnostics.itertuples(index=False):
        lines.append(
            f"| {row.target} | {row.n_events} | {row.cv_r2_mean:.3f} | "
            f"{row.cv_mae_mean:.3f} | {row.surrogate_warning} |"
        )
    lines.extend(["", "## Top Global SHAP Features", ""])
    for target in TARGET_COLUMNS:
        frame = importance[importance["target"].eq(target)].head(8)
        lines.extend([f"### {target}", ""])
        lines.append("| feature | mean_abs_shap | mean_shap |")
        lines.append("| --- | ---: | ---: |")
        for row in frame.itertuples(index=False):
            lines.append(f"| {row.feature} | {row.mean_abs_shap:.4f} | {row.mean_shap:.4f} |")
        lines.append("")
    lines.extend(
        [
            "## Local Event Explanations",
            "",
            "Local table에는 target별로 SHAP magnitude가 큰 event와 상위 feature contribution이 저장되어 있습니다. 값이 크다는 것은 surrogate가 해당 event를 설명할 때 그 feature들을 많이 사용했다는 뜻이지, 실제 model error의 원인이라고 단정하는 뜻은 아닙니다.",
            "",
            f"- Local explanations table: `{relative_path(output_dir / 'tables' / 'local_top_event_explanations.csv')}`",
            f"- Global importance table: `{relative_path(output_dir / 'tables' / 'global_feature_importance.csv')}`",
            f"- Diagnostics table: `{relative_path(output_dir / 'tables' / 'surrogate_target_diagnostics.csv')}`",
            "",
        ]
    )
    if (diagnostics["cv_r2_mean"] < 0.2).any():
        weak = ", ".join(diagnostics.loc[diagnostics["cv_r2_mean"] < 0.2, "target"].tolist())
        lines.extend(
            [
                "## Caveat",
                "",
                f"다음 target은 평균 CV R2가 0.2 미만이라 surrogate 설명력이 약합니다: {weak}. 이 target들은 exploratory screening 용도로만 보세요.",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_metadata(
    path: Path,
    *,
    args: argparse.Namespace,
    event_table: pd.DataFrame,
    diagnostics: pd.DataFrame,
    figures: list[dict[str, Any]],
) -> None:
    metadata = {
        "script": "scripts/model/event_regime/analyze_subset300_event_surrogate_shap.py",
        "event_table_input": relative_path(resolve_path(args.event_table)),
        "static_attributes_input": relative_path(resolve_path(args.static_attributes)),
        "output_dir": relative_path(resolve_path(args.output_dir)),
        "n_event_rows_after_seed_aggregation": int(len(event_table)),
        "n_basins": int(event_table["gauge_id"].nunique()),
        "targets": TARGET_COLUMNS,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "random_state": int(args.random_state),
        "n_estimators": int(args.n_estimators),
        "min_samples_leaf": int(args.min_samples_leaf),
        "n_splits": int(args.n_splits),
        "n_repeats": int(args.n_repeats),
        "diagnostics": diagnostics.to_dict(orient="records"),
        "figures": figures,
        "interpretation_warning": (
            "SHAP values explain the fitted RandomForest surrogate, not the original LSTM "
            "or quantile model causally."
        ),
    }
    path.write_text(json.dumps(json_safe(metadata), indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    event_path = resolve_path(args.event_table)
    static_path = resolve_path(args.static_attributes)
    output_dir = resolve_path(args.output_dir)
    tables_dir = output_dir / "tables"
    figures_dir = output_dir / "figures"
    metadata_dir = output_dir / "metadata"
    report_dir = output_dir / "report"
    for directory in [tables_dir, figures_dir, metadata_dir, report_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    seed_rows = read_event_table(event_path)
    static_attrs = read_static_attributes(static_path)
    event_table = aggregate_to_event_level(seed_rows, static_attrs)
    event_table.to_csv(tables_dir / "event_surrogate_table.csv", index=False)

    diagnostics_rows: list[dict[str, Any]] = []
    importance_frames: list[pd.DataFrame] = []
    local_frames: list[pd.DataFrame] = []
    figures: list[dict[str, Any]] = []

    for target in TARGET_COLUMNS:
        print(f"Fitting surrogate for {target}", flush=True)
        result = fit_target_surrogate(
            event_table,
            target,
            n_splits=args.n_splits,
            n_repeats=args.n_repeats,
            random_state=args.random_state,
            n_estimators=args.n_estimators,
            min_samples_leaf=args.min_samples_leaf,
        )
        diagnostics_rows.append({"target": target, "target_label": TARGET_COLUMNS[target], **result.diagnostics})
        target_importance = feature_importance(result)
        importance_frames.append(target_importance)
        local_frames.append(local_top_events(event_table, result, args.top_local_events))
        figure_path = figures_dir / f"{target}_mean_abs_shap.png"
        save_target_bar_chart(target_importance, target, figure_path, args.top_features)
        figures.append(
            {
                "target": target,
                "figure_type": "mean_abs_shap",
                "path": relative_path(figure_path),
                "exists": figure_path.exists(),
            }
        )
        signed_figure_path = figures_dir / f"{target}_mean_shap.png"
        save_target_signed_bar_chart(target_importance, target, signed_figure_path, args.top_features)
        figures.append(
            {
                "target": target,
                "figure_type": "mean_shap_signed",
                "path": relative_path(signed_figure_path),
                "exists": signed_figure_path.exists(),
            }
        )

    diagnostics = pd.DataFrame(diagnostics_rows)
    importance = pd.concat(importance_frames, ignore_index=True)
    local = pd.concat(local_frames, ignore_index=True)

    diagnostics_fold_rows: list[dict[str, Any]] = []
    for row in diagnostics_rows:
        for fold in row["fold_diagnostics"]:
            diagnostics_fold_rows.append({"target": row["target"], **fold})
    fold_diagnostics = pd.DataFrame(diagnostics_fold_rows)

    diagnostics.drop(columns=["fold_diagnostics"]).to_csv(
        tables_dir / "surrogate_target_diagnostics.csv", index=False
    )
    fold_diagnostics.to_csv(tables_dir / "surrogate_fold_diagnostics.csv", index=False)
    importance.to_csv(tables_dir / "global_feature_importance.csv", index=False)
    local.to_csv(tables_dir / "local_top_event_explanations.csv", index=False)

    combined_path = figures_dir / "combined_mean_abs_shap_summary.png"
    save_combined_chart(importance, combined_path, args.top_features)
    figures.append(
        {
            "target": "combined",
            "figure_type": "mean_abs_shap",
            "path": relative_path(combined_path),
            "exists": combined_path.exists(),
        }
    )
    combined_signed_path = figures_dir / "combined_mean_shap_signed_summary.png"
    save_combined_signed_chart(importance, combined_signed_path, args.top_features)
    figures.append(
        {
            "target": "combined",
            "figure_type": "mean_shap_signed",
            "path": relative_path(combined_signed_path),
            "exists": combined_signed_path.exists(),
        }
    )

    write_report(
        report_dir / "event_surrogate_shap_report.md",
        event_table=event_table,
        diagnostics=diagnostics.drop(columns=["fold_diagnostics"]),
        importance=importance,
        local=local,
        output_dir=output_dir,
    )
    write_metadata(
        metadata_dir / "event_surrogate_shap_metadata.json",
        args=args,
        event_table=event_table,
        diagnostics=diagnostics.drop(columns=["fold_diagnostics"]),
        figures=figures,
    )

    print(f"Wrote event-level surrogate SHAP outputs to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
