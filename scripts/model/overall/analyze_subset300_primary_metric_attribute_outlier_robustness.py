#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=1.26",
#   "pandas>=2.2",
#   "scipy>=1.13",
# ]
# ///
from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT_ROOT = (
    REPO_ROOT / "output/model_analysis/overall_analysis/main_comparison/attribute_correlations"
)
DEFAULT_OUTPUT_DIR = DEFAULT_INPUT_ROOT / "robustness"
DEFAULT_EXISTING_OUTLIER_SUMMARY = (
    REPO_ROOT / "output/model_analysis/overall_analysis/result_checks/outlier_checks/outlier_basin_summary.csv"
)
DEFAULT_STREAMFLOW_QUALITY = (
    REPO_ROOT / "output/basin/drbc/screening/drbc_streamflow_quality_table.csv"
)
DEFAULT_EVENT_RESPONSE = (
    REPO_ROOT / "output/basin/drbc/analysis/event_response/tables/event_response_basin_summary.csv"
)

DEFAULT_METRICS = ["NSE", "KGE", "FHV", "Peak_Timing", "Peak_MAPE", "abs_FHV"]
MODELS = ["model1", "model2"]
OFFICIAL_SEEDS = [111, 222, 444]
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
CONTEXT_COLUMNS = [
    "basin",
    "gauge_id",
    "gauge_name",
    "state",
    "huc02",
    "static_huc02",
    "static_state",
    "drbc_state",
    "drbc_huc02",
]
SCENARIO_ORDER = [
    "full",
    "metric_iqr_inliers",
    "area_ge_50",
    "metric_iqr_inliers_and_area_ge_50",
]
METRIC_ALIASES = {
    "Peak-Timing": "Peak_Timing",
    "Peak-MAPE": "Peak_MAPE",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Recompute primary metric-attribute Spearman correlations under simple "
            "outlier-robustness scenarios using existing basin metric attribute tables."
        )
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        default=DEFAULT_INPUT_ROOT,
        help="Root containing <metric>/tables/<metric>_basin_metric_attribute_table.csv.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where robustness/tables and robustness/metadata will be written.",
    )
    parser.add_argument("--metrics", nargs="+", default=DEFAULT_METRICS)
    parser.add_argument("--seeds", type=int, nargs="+", default=OFFICIAL_SEEDS)
    parser.add_argument("--area-threshold", type=float, default=50.0)
    parser.add_argument("--existing-outlier-summary", type=Path, default=DEFAULT_EXISTING_OUTLIER_SUMMARY)
    parser.add_argument("--streamflow-quality", type=Path, default=DEFAULT_STREAMFLOW_QUALITY)
    parser.add_argument("--event-response", type=Path, default=DEFAULT_EVENT_RESPONSE)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def normalize_metric(metric: str) -> str:
    return METRIC_ALIASES.get(metric, metric)


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


def target_columns(seeds: list[int]) -> list[str]:
    return [f"{model}_seed{seed}" for model in MODELS for seed in seeds]


def parse_target(target: str) -> tuple[str, int]:
    for model in MODELS:
        prefix = f"{model}_seed"
        if target.startswith(prefix):
            return model, int(target.removeprefix(prefix))
    raise ValueError(f"Unsupported target column: {target}")


def read_metric_table(input_root: Path, metric: str, seeds: list[int]) -> pd.DataFrame:
    metric = normalize_metric(metric)
    path = input_root / metric / "tables" / f"{metric}_basin_metric_attribute_table.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing metric attribute table: {path}")

    dtype = {"basin": str, "gauge_id": str, "huc02": str, "static_huc02": str, "drbc_huc02": str}
    table = pd.read_csv(path, dtype={key: value for key, value in dtype.items() if key})
    if "basin" not in table.columns:
        raise ValueError(f"Missing basin column in {path}")
    table["basin"] = table["basin"].map(normalize_basin_id)

    required = set(CORE_FEATURES) | set(target_columns(seeds))
    missing = sorted(required.difference(table.columns))
    if missing:
        raise ValueError(f"{path} is missing required columns: {missing}")

    numeric_columns = sorted(required | {"area"})
    for column in numeric_columns:
        if column in table.columns:
            table[column] = pd.to_numeric(table[column], errors="coerce")
    return table


def read_basin_context(
    existing_outlier_summary: Path,
    streamflow_quality: Path,
    event_response: Path,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []

    if existing_outlier_summary.exists():
        summary_cols = [
            "basin",
            "outlier_record_count",
            "outlier_metric_count",
            "outlier_metrics",
            "max_iqr_scaled_distance",
            "obs_mean",
            "obs_std",
            "obs_cv",
            "obs_q99",
            "obs_max",
            "obs_variance_denominator",
            "obs_near_zero_fraction",
            "hydromod_risk",
            "STOR_NOR_2009",
            "MAJ_NDAMS_2009",
            "FLOW_PCT_EST_VALUES",
            "BASIN_BOUNDARY_CONFIDENCE",
            "q99_event_frequency",
            "rbi",
            "rising_time_median_hours",
            "event_duration_median_hours",
            "annual_peak_unit_area_median",
            "annual_peak_unit_area_p90",
        ]
        summary = pd.read_csv(existing_outlier_summary, dtype={"basin": str})
        summary["basin"] = summary["basin"].map(normalize_basin_id)
        keep = [col for col in summary_cols if col in summary.columns]
        frames.append(summary[keep].copy())

    if streamflow_quality.exists():
        quality_cols = [
            "gauge_id",
            "passes_obs_years_gate",
            "passes_estimated_flow_gate",
            "passes_boundary_conf_gate",
            "passes_streamflow_quality_gate",
            "obs_years_usable",
            "obs_coverage_ratio_active_span",
            "FLOW_PCT_EST_VALUES",
            "BASIN_BOUNDARY_CONFIDENCE",
            "hydromod_risk",
            "STOR_NOR_2009",
            "MAJ_NDAMS_2009",
            "CANALS_PCT",
            "FRESHW_WITHDRAWAL",
        ]
        quality = pd.read_csv(streamflow_quality, dtype={"gauge_id": str})
        quality["basin"] = quality["gauge_id"].map(normalize_basin_id)
        keep = ["basin"] + [col for col in quality_cols if col in quality.columns and col != "gauge_id"]
        quality = quality[keep].copy()
        quality = quality.rename(
            columns={
                col: f"quality_{col}"
                for col in keep
                if col not in {"basin"}
                and col
                in {
                    "FLOW_PCT_EST_VALUES",
                    "BASIN_BOUNDARY_CONFIDENCE",
                    "hydromod_risk",
                    "STOR_NOR_2009",
                    "MAJ_NDAMS_2009",
                }
            }
        )
        frames.append(quality)

    if event_response.exists():
        event_cols = [
            "gauge_id",
            "processing_status",
            "selected_threshold_quantile",
            "q99_event_count",
            "q98_event_count",
            "q95_event_count",
            "event_count",
            "annual_peak_years",
            "unit_area_peak_median",
            "unit_area_peak_p90",
            "q99_event_frequency",
            "rbi",
            "rising_time_median_hours",
            "event_duration_median_hours",
            "event_runoff_coefficient_median",
            "annual_peak_unit_area_median",
            "annual_peak_unit_area_p90",
        ]
        events = pd.read_csv(event_response, dtype={"gauge_id": str})
        events["basin"] = events["gauge_id"].map(normalize_basin_id)
        keep = ["basin"] + [col for col in event_cols if col in events.columns and col != "gauge_id"]
        events = events[keep].copy()
        events = events.rename(
            columns={col: f"event_{col}" for col in keep if col != "basin" and col in {"q99_event_frequency", "rbi"}}
        )
        frames.append(events)

    if not frames:
        return pd.DataFrame(columns=["basin"])

    context = frames[0].copy()
    for frame in frames[1:]:
        overlap = [col for col in frame.columns if col in context.columns and col != "basin"]
        frame = frame.rename(columns={col: f"{col}_context" for col in overlap})
        context = context.merge(frame, on="basin", how="outer")
    return context.drop_duplicates("basin")


def iqr_fence(values: pd.Series) -> dict[str, float]:
    finite = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if finite.empty:
        return {"q1": math.nan, "q3": math.nan, "iqr": math.nan, "lower": math.nan, "upper": math.nan}
    q1 = float(finite.quantile(0.25))
    q3 = float(finite.quantile(0.75))
    iqr = q3 - q1
    return {
        "q1": q1,
        "q3": q3,
        "iqr": float(iqr),
        "lower": float(q1 - 1.5 * iqr),
        "upper": float(q3 + 1.5 * iqr),
    }


def finite_mask(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    return values.notna() & np.isfinite(values)


def scenario_masks(
    table: pd.DataFrame,
    target: str,
    area_threshold: float,
    fence: dict[str, float],
) -> dict[str, pd.Series]:
    target_valid = finite_mask(table[target])
    area_ge = finite_mask(table["area"]) & table["area"].ge(area_threshold)

    if math.isfinite(fence["lower"]) and math.isfinite(fence["upper"]):
        iqr_inlier = target_valid & table[target].between(fence["lower"], fence["upper"], inclusive="both")
    else:
        iqr_inlier = pd.Series(False, index=table.index)

    return {
        "full": target_valid,
        "metric_iqr_inliers": iqr_inlier,
        "area_ge_50": target_valid & area_ge,
        "metric_iqr_inliers_and_area_ge_50": iqr_inlier & area_ge,
    }


def removed_basin_ids(table: pd.DataFrame, base_mask: pd.Series, scenario_mask: pd.Series) -> list[str]:
    removed = table.loc[base_mask & ~scenario_mask, "basin"].dropna().map(normalize_basin_id)
    return sorted(removed.unique().tolist())


def spearman_row(subset: pd.DataFrame, target: str, feature: str) -> tuple[int, float, float, float]:
    pair = subset[[target, feature]].replace([np.inf, -np.inf], np.nan).dropna()
    n = int(len(pair))
    if n < 4 or pair[target].nunique(dropna=True) <= 1 or pair[feature].nunique(dropna=True) <= 1:
        return n, math.nan, math.nan, math.nan
    result = stats.spearmanr(pair[feature], pair[target], nan_policy="omit")
    rho = float(result.statistic)
    p_value = float(result.pvalue)
    return n, rho, p_value, abs(rho)


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


def build_correlation_rows(
    metric: str,
    table: pd.DataFrame,
    seeds: list[int],
    area_threshold: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for target in target_columns(seeds):
        model, seed = parse_target(target)
        fence = iqr_fence(table[target])
        masks = scenario_masks(table, target, area_threshold, fence)
        base_mask = masks["full"]

        for scenario in SCENARIO_ORDER:
            scenario_mask = masks[scenario]
            removed_ids = removed_basin_ids(table, base_mask, scenario_mask)
            scenario_subset = table.loc[scenario_mask].copy()

            for feature in CORE_FEATURES:
                n, rho, p_value, abs_rho = spearman_row(scenario_subset, target, feature)
                rows.append(
                    {
                        "metric": metric,
                        "scenario": scenario,
                        "model": model,
                        "seed": seed,
                        "target": target,
                        "feature": feature,
                        "n": n,
                        "rho": rho,
                        "p_value": p_value,
                        "q_fdr": math.nan,
                        "abs_rho": abs_rho,
                        "removed_basin_count": len(removed_ids),
                        "removed_basin_ids": ";".join(removed_ids),
                        "target_non_missing_n": int(base_mask.sum()),
                        "scenario_candidate_n": int(scenario_mask.sum()),
                        "iqr_q1": fence["q1"],
                        "iqr_q3": fence["q3"],
                        "iqr": fence["iqr"],
                        "lower_fence": fence["lower"],
                        "upper_fence": fence["upper"],
                        "area_threshold": area_threshold,
                    }
                )

    out = pd.DataFrame(rows)
    if out.empty:
        return out

    for (_metric, scenario), index in out.groupby(["metric", "scenario"], sort=False).groups.items():
        out.loc[index, "q_fdr"] = bh_fdr(out.loc[index, "p_value"])

    out["scenario"] = pd.Categorical(out["scenario"], categories=SCENARIO_ORDER, ordered=True)
    out = out.sort_values(
        ["metric", "scenario", "model", "seed", "abs_rho", "feature"],
        ascending=[True, True, True, True, False, True],
    ).reset_index(drop=True)
    out["scenario"] = out["scenario"].astype(str)
    return out


def area_lt_50_value(value: Any, threshold: float) -> bool | None:
    if pd.isna(value) or not np.isfinite(float(value)):
        return None
    return bool(float(value) < threshold)


def build_outlier_audit_rows(
    metric: str,
    table: pd.DataFrame,
    seeds: list[int],
    area_threshold: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    available_context = [column for column in CONTEXT_COLUMNS if column in table.columns]

    for target in target_columns(seeds):
        model, seed = parse_target(target)
        fence = iqr_fence(table[target])
        if not math.isfinite(fence["lower"]) or not math.isfinite(fence["upper"]):
            continue

        target_values = pd.to_numeric(table[target], errors="coerce")
        outlier_mask = target_values.lt(fence["lower"]) | target_values.gt(fence["upper"])
        for _, basin_row in table.loc[outlier_mask].sort_values("basin").iterrows():
            target_value = float(basin_row[target])
            audit_row: dict[str, Any] = {
                "metric": metric,
                "model": model,
                "seed": seed,
                "target": target,
                "basin": normalize_basin_id(basin_row["basin"]),
                "target_metric_value": target_value,
                "iqr_q1": fence["q1"],
                "iqr_q3": fence["q3"],
                "iqr": fence["iqr"],
                "lower_fence": fence["lower"],
                "upper_fence": fence["upper"],
                "outlier_side": "low" if target_value < fence["lower"] else "high",
                "area_lt_50": area_lt_50_value(basin_row.get("area"), area_threshold),
                "area_threshold": area_threshold,
            }
            for column in available_context:
                if column not in audit_row:
                    audit_row[column] = basin_row[column]
            for feature in CORE_FEATURES:
                audit_row[feature] = basin_row[feature]
            rows.append(audit_row)

    columns = [
        "metric",
        "model",
        "seed",
        "target",
        "basin",
        "target_metric_value",
        "iqr_q1",
        "iqr_q3",
        "iqr",
        "lower_fence",
        "upper_fence",
        "outlier_side",
        "area_lt_50",
        "area_threshold",
        *[column for column in CONTEXT_COLUMNS if column != "basin"],
        *CORE_FEATURES,
    ]
    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=columns)
    ordered = [column for column in columns if column in out.columns]
    extras = [column for column in out.columns if column not in ordered]
    return out[ordered + extras].sort_values(["metric", "model", "seed", "basin"]).reset_index(drop=True)


def build_robustness_summary(correlations: pd.DataFrame) -> pd.DataFrame:
    if correlations.empty:
        return pd.DataFrame()

    index_cols = ["metric", "model", "seed", "target", "feature"]
    full = correlations[correlations["scenario"].eq("full")][
        [*index_cols, "n", "rho", "p_value", "q_fdr", "abs_rho"]
    ].copy()
    full = full.rename(
        columns={
            "n": "full_n",
            "rho": "full_rho",
            "p_value": "full_p_value",
            "q_fdr": "full_q_fdr",
            "abs_rho": "full_abs_rho",
        }
    )
    scenario_rows = correlations[~correlations["scenario"].eq("full")].copy()
    merged = scenario_rows.merge(full, on=index_cols, how="left", validate="many_to_one")
    merged["rho_change_from_full"] = merged["rho"] - merged["full_rho"]
    merged["abs_rho_change_from_full"] = merged["abs_rho"] - merged["full_abs_rho"]
    valid_sign = merged["rho"].notna() & merged["full_rho"].notna()
    merged["rho_sign_changed_from_full"] = pd.Series(pd.NA, index=merged.index, dtype="boolean")
    merged.loc[valid_sign, "rho_sign_changed_from_full"] = (
        np.sign(merged.loc[valid_sign, "rho"]) != np.sign(merged.loc[valid_sign, "full_rho"])
    ).astype(bool)
    merged["full_significant_q05"] = merged["full_q_fdr"] < 0.05
    merged["scenario_significant_q05"] = merged["q_fdr"] < 0.05
    merged["lost_q05_after_filter"] = merged["full_significant_q05"] & ~merged["scenario_significant_q05"]
    merged["gained_q05_after_filter"] = ~merged["full_significant_q05"] & merged["scenario_significant_q05"]
    return merged.sort_values(
        ["metric", "model", "seed", "feature", "scenario"]
    ).reset_index(drop=True)


def build_outlier_basin_summary(outlier_audit: pd.DataFrame) -> pd.DataFrame:
    if outlier_audit.empty:
        return pd.DataFrame()
    summary = (
        outlier_audit.groupby(["metric", "basin"], dropna=False)
        .agg(
            outlier_records=("target_metric_value", "size"),
            models=("model", lambda values: " ".join(sorted(set(map(str, values))))),
            seeds=("seed", lambda values: " ".join(str(int(v)) for v in sorted(set(values)))),
            outlier_sides=("outlier_side", lambda values: " ".join(sorted(set(map(str, values))))),
            worst_low_value=("target_metric_value", "min"),
            worst_high_value=("target_metric_value", "max"),
            area_lt_50=("area_lt_50", "max"),
            area=("area", "first"),
            gauge_name=("gauge_name", "first"),
            state=("state", "first"),
            obs_variance_denominator=("obs_variance_denominator", "first"),
            obs_cv=("obs_cv", "first"),
            hydromod_risk=("hydromod_risk", "first"),
            passes_streamflow_quality_gate=("passes_streamflow_quality_gate", "first"),
            q99_event_frequency=("q99_event_frequency", "first"),
            rbi=("rbi", "first"),
        )
        .reset_index()
    )
    return summary.sort_values(
        ["metric", "outlier_records", "basin"], ascending=[True, False, True]
    ).reset_index(drop=True)


def write_metadata(
    path: Path,
    args: argparse.Namespace,
    inputs: list[dict[str, Any]],
    outputs: dict[str, str],
) -> None:
    metadata = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "script": str(Path(__file__).resolve()),
        "input_root": str(resolve(args.input_root)),
        "output_dir": str(resolve(args.output_dir)),
        "existing_outlier_summary": str(resolve(args.existing_outlier_summary)),
        "streamflow_quality": str(resolve(args.streamflow_quality)),
        "event_response": str(resolve(args.event_response)),
        "metrics": [normalize_metric(metric) for metric in args.metrics],
        "models": MODELS,
        "seeds": args.seeds,
        "core_features": CORE_FEATURES,
        "scenarios": SCENARIO_ORDER,
        "area_threshold": args.area_threshold,
        "fdr": "Benjamini-Hochberg within each metric+scenario group.",
        "inputs": inputs,
        "outputs": outputs,
    }
    path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    input_root = resolve(args.input_root)
    output_dir = resolve(args.output_dir)
    tables_dir = output_dir / "tables"
    metadata_dir = output_dir / "metadata"
    tables_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    metrics = [normalize_metric(metric) for metric in args.metrics]
    basin_context = read_basin_context(
        resolve(args.existing_outlier_summary),
        resolve(args.streamflow_quality),
        resolve(args.event_response),
    )
    correlation_parts: list[pd.DataFrame] = []
    audit_parts: list[pd.DataFrame] = []
    input_metadata: list[dict[str, Any]] = []

    for metric in metrics:
        table = read_metric_table(input_root, metric, args.seeds)
        input_path = input_root / metric / "tables" / f"{metric}_basin_metric_attribute_table.csv"
        input_metadata.append(
            {
                "metric": metric,
                "path": str(input_path),
                "rows": int(len(table)),
                "target_columns": target_columns(args.seeds),
            }
        )
        correlation_parts.append(build_correlation_rows(metric, table, args.seeds, args.area_threshold))
        audit_parts.append(build_outlier_audit_rows(metric, table, args.seeds, args.area_threshold))

    correlations = pd.concat(correlation_parts, ignore_index=True)
    outlier_audit = pd.concat(audit_parts, ignore_index=True)
    if not basin_context.empty and not outlier_audit.empty:
        outlier_audit = outlier_audit.merge(basin_context, on="basin", how="left", suffixes=("", "_context"))
    robustness_summary = build_robustness_summary(correlations)
    outlier_basin_summary = build_outlier_basin_summary(outlier_audit)

    correlations_path = tables_dir / "primary_metric_attribute_outlier_robustness_spearman.csv"
    summary_path = tables_dir / "primary_metric_attribute_outlier_robustness_summary.csv"
    audit_path = tables_dir / "primary_metric_attribute_iqr_outlier_audit.csv"
    outlier_basin_summary_path = tables_dir / "primary_metric_attribute_iqr_outlier_basin_summary.csv"
    metadata_path = metadata_dir / "primary_metric_attribute_outlier_robustness_metadata.json"

    correlations.to_csv(correlations_path, index=False)
    robustness_summary.to_csv(summary_path, index=False)
    outlier_audit.to_csv(audit_path, index=False)
    outlier_basin_summary.to_csv(outlier_basin_summary_path, index=False)

    outputs = {
        "correlations": str(correlations_path),
        "robustness_summary": str(summary_path),
        "outlier_audit": str(audit_path),
        "outlier_basin_summary": str(outlier_basin_summary_path),
        "metadata": str(metadata_path),
    }
    write_metadata(metadata_path, args, input_metadata, outputs)

    print(f"Wrote {len(correlations):,} robustness correlation rows to {correlations_path}")
    print(f"Wrote {len(robustness_summary):,} robustness comparison rows to {summary_path}")
    print(f"Wrote {len(outlier_audit):,} IQR outlier audit rows to {audit_path}")
    print(f"Wrote {len(outlier_basin_summary):,} IQR outlier basin summary rows to {outlier_basin_summary_path}")
    print(f"Wrote metadata to {metadata_path}")


if __name__ == "__main__":
    main()
