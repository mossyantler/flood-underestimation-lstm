#!/usr/bin/env python3
# /// script
# dependencies = [
#   "netCDF4>=1.7",
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "scipy>=1.13",
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

LIB_ROOT = Path(__file__).resolve().parents[2] / "_lib"
if str(LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(LIB_ROOT))

import camelsh_flood_analysis_utils as fu


DEFAULT_METADATA = [
    Path("basins/CAMELSH_data/attributes/attributes_gageii_BasinID.csv"),
    Path("data/CAMELSH_generic/drbc_holdout_broad/attributes/static_attributes.csv"),
    Path("configs/pilot/basin_splits/prepared_pool_manifest.csv"),
]

TYPE_SCORE_COLUMNS = [
    "recent_precipitation_score",
    "antecedent_precipitation_score",
    "snowmelt_or_rain_on_snow_score",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Classify CAMELSH observed high-flow event candidates into rule-based flood generation types "
            "and summarize dominant basin-level typing."
        )
    )
    parser.add_argument(
        "--event-response-csv",
        type=Path,
        default=Path("output/basin/all/analysis/event_response/tables/event_response_table.csv"),
        help="Event response table produced by build_camelsh_event_response_table.py.",
    )
    parser.add_argument("--metadata-csv", type=Path, action="append", default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/basin/all/analysis"),
        help="Analysis root directory. Flood-generation tables and metadata are written under flood_generation/.",
    )
    parser.add_argument(
        "--dominance-threshold",
        type=float,
        default=0.6,
        help="Minimum event-type share required to call a basin dominant rather than mixture.",
    )
    parser.add_argument(
        "--method",
        choices=["degree_day_v2", "rank_score_v1"],
        default="degree_day_v2",
        help="Flood-generation typing method. degree_day_v2 is the current canonical decision tree.",
    )
    parser.add_argument(
        "--score-scope",
        choices=["basin", "global"],
        default="basin",
        help="Rank-score v1 only: rank descriptors within each basin or globally.",
    )
    parser.add_argument(
        "--low-confidence-margin",
        type=float,
        default=0.05,
        help="Rank-score v1 only: top-minus-second score margin below which an event is flagged as low confidence.",
    )
    parser.add_argument(
        "--precip-low-confidence-relative-margin",
        type=float,
        default=0.10,
        help="Degree-day v2 only: relative recent-vs-antecedent strength margin treated as low confidence.",
    )
    return parser.parse_args()


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def read_events(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"Event response CSV does not exist: {path}")
    events = pd.read_csv(path, dtype={"gauge_id": str, "huc02": str})
    events["gauge_id"] = events["gauge_id"].map(fu.normalize_gauge_id)
    return events


def ensure_metadata(events: pd.DataFrame, metadata_paths: list[Path]) -> pd.DataFrame:
    gauge_ids = sorted(events["gauge_id"].dropna().unique())
    metadata = fu.load_basin_metadata(gauge_ids, metadata_paths)
    add_cols = [col for col in metadata.columns if col != "gauge_id" and col not in events.columns]
    if not add_cols:
        return events
    return events.merge(metadata[["gauge_id", *add_cols]], on="gauge_id", how="left", validate="many_to_one")


def numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce")


def rank_score_global(values: pd.Series, *, high_is_good: bool) -> pd.Series:
    clean = pd.to_numeric(values, errors="coerce")
    if clean.notna().sum() <= 1:
        return pd.Series(0.5, index=values.index, dtype=float)
    ranked = clean.rank(pct=True, ascending=high_is_good)
    return ranked.fillna(0.5).astype(float)


def rank_score_basin(df: pd.DataFrame, column: str, *, high_is_good: bool) -> pd.Series:
    values = numeric_series(df, column)

    def score_group(group: pd.Series) -> pd.Series:
        if group.notna().sum() <= 1:
            return pd.Series(0.5, index=group.index, dtype=float)
        return group.rank(pct=True, ascending=high_is_good).fillna(0.5).astype(float)

    return values.groupby(df["gauge_id"], group_keys=False).apply(score_group)


def descriptor_score(df: pd.DataFrame, column: str, *, high_is_good: bool, score_scope: str) -> pd.Series:
    if score_scope == "global":
        return rank_score_global(numeric_series(df, column), high_is_good=high_is_good)
    return rank_score_basin(df, column, high_is_good=high_is_good)


def bool_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(False, index=df.index, dtype=bool)
    raw = df[column]
    numeric = pd.to_numeric(raw, errors="coerce")
    text = raw.astype(str).str.strip().str.lower()
    return (numeric == 1) | text.isin(["true", "t", "yes", "y"])


def threshold_ratio(df: pd.DataFrame, value_column: str, threshold_column: str) -> pd.Series:
    value = numeric_series(df, value_column)
    threshold = numeric_series(df, threshold_column)
    ratio = value / threshold
    ratio = ratio.where(threshold > 0)
    return ratio.replace([np.inf, -np.inf], np.nan)


def classify_events_degree_day(
    events: pd.DataFrame,
    *,
    precip_low_confidence_relative_margin: float,
) -> pd.DataFrame:
    typed = events.copy()

    snowmelt_7d = numeric_series(typed, "degree_day_snowmelt_7d")
    snowmelt_p90 = numeric_series(typed, "basin_snowmelt_7d_p90")
    snowmelt_count = numeric_series(typed, "basin_snowmelt_valid_window_count")
    snowmelt_proxy = (
        snowmelt_7d.notna()
        & snowmelt_p90.notna()
        & snowmelt_count.notna()
        & (snowmelt_7d >= snowmelt_p90)
        & (snowmelt_7d >= fu.SNOWMELT_MIN_MM)
        & (snowmelt_count >= fu.SNOWMELT_MIN_VALID_WINDOW_COUNT)
    )

    water_input_7d = numeric_series(typed, "degree_day_water_input_7d")
    snowmelt_fraction_7d = numeric_series(typed, "degree_day_snowmelt_fraction_7d")
    rain_fraction_7d = numeric_series(typed, "degree_day_rain_fraction_7d")
    rain_snowmelt_proxy = bool_series(typed, "rain_on_snow_proxy") | (
        water_input_7d.notna()
        & (water_input_7d > 0)
        & snowmelt_7d.notna()
        & (snowmelt_7d >= fu.SNOWMELT_MIN_MM)
        & snowmelt_fraction_7d.notna()
        & (snowmelt_fraction_7d >= fu.RAIN_SNOWMELT_MIN_FRACTION)
        & rain_fraction_7d.notna()
        & (rain_fraction_7d >= fu.RAIN_SNOWMELT_MIN_FRACTION)
    )
    snow_related = rain_snowmelt_proxy | snowmelt_proxy

    recent_24h_strength = threshold_ratio(typed, "recent_rain_24h", "basin_rain_1d_p90")
    recent_72h_strength = threshold_ratio(typed, "recent_rain_72h", "basin_rain_3d_p90")
    antecedent_7d_strength = threshold_ratio(typed, "antecedent_rain_7d", "basin_rain_7d_p90")
    antecedent_30d_strength = threshold_ratio(typed, "antecedent_rain_30d", "basin_rain_30d_p90")

    typed["recent_precipitation_strength"] = pd.concat([recent_24h_strength, recent_72h_strength], axis=1).max(axis=1)
    typed["antecedent_precipitation_strength"] = pd.concat(
        [antecedent_7d_strength, antecedent_30d_strength],
        axis=1,
    ).max(axis=1)
    typed["snowmelt_or_rain_on_snow_strength"] = threshold_ratio(
        typed,
        "degree_day_snowmelt_7d",
        "basin_snowmelt_7d_p90",
    )
    typed["degree_day_snowmelt_proxy"] = snowmelt_proxy
    typed["degree_day_rain_snowmelt_proxy"] = rain_snowmelt_proxy

    recent_candidate = typed["recent_precipitation_strength"] >= 1.0
    antecedent_candidate = typed["antecedent_precipitation_strength"] >= 1.0
    non_snow = ~snow_related
    both_precip = non_snow & recent_candidate & antecedent_candidate
    recent_only = non_snow & recent_candidate & ~antecedent_candidate
    antecedent_only = non_snow & antecedent_candidate & ~recent_candidate

    typed["flood_generation_method"] = "degree_day_decision_tree_v2"
    typed["flood_generation_type"] = "uncertain_high_flow_candidate"
    typed["flood_generation_subtype"] = "no_rule_match"
    typed["flood_generation_score_margin"] = np.nan
    typed["low_confidence_type_flag"] = False

    typed.loc[snow_related, "flood_generation_type"] = "snowmelt_or_rain_on_snow"
    typed.loc[snow_related & snowmelt_proxy, "flood_generation_subtype"] = "snowmelt_proxy"
    typed.loc[snow_related & rain_snowmelt_proxy, "flood_generation_subtype"] = "rain_snowmelt_proxy"

    typed.loc[recent_only, "flood_generation_type"] = "recent_precipitation"
    typed.loc[recent_only, "flood_generation_subtype"] = "recent_precipitation_p90_proxy"
    typed.loc[recent_only, "flood_generation_score_margin"] = (
        typed.loc[recent_only, "recent_precipitation_strength"] - 1.0
    )

    typed.loc[antecedent_only, "flood_generation_type"] = "antecedent_precipitation"
    typed.loc[antecedent_only, "flood_generation_subtype"] = "antecedent_precipitation_p90_proxy"
    typed.loc[antecedent_only, "flood_generation_score_margin"] = (
        typed.loc[antecedent_only, "antecedent_precipitation_strength"] - 1.0
    )

    recent_preferred = both_precip & (
        typed["recent_precipitation_strength"] >= typed["antecedent_precipitation_strength"]
    )
    antecedent_preferred = both_precip & ~recent_preferred
    typed.loc[recent_preferred, "flood_generation_type"] = "recent_precipitation"
    typed.loc[recent_preferred, "flood_generation_subtype"] = "recent_over_antecedent_p90_proxy"
    typed.loc[antecedent_preferred, "flood_generation_type"] = "antecedent_precipitation"
    typed.loc[antecedent_preferred, "flood_generation_subtype"] = "antecedent_over_recent_p90_proxy"

    precip_strength_gap = (
        typed["recent_precipitation_strength"] - typed["antecedent_precipitation_strength"]
    ).abs()
    precip_strength_max = pd.concat(
        [typed["recent_precipitation_strength"], typed["antecedent_precipitation_strength"]],
        axis=1,
    ).max(axis=1)
    typed.loc[both_precip, "flood_generation_score_margin"] = precip_strength_gap[both_precip]
    close_precip = (
        both_precip
        & precip_strength_max.notna()
        & (precip_strength_max > 0)
        & ((precip_strength_gap / precip_strength_max) < precip_low_confidence_relative_margin)
    )
    typed.loc[close_precip, "low_confidence_type_flag"] = True
    typed.loc[typed["flood_generation_type"] == "uncertain_high_flow_candidate", "low_confidence_type_flag"] = True
    return typed


def classify_events_rank_score(events: pd.DataFrame, *, score_scope: str, low_confidence_margin: float) -> pd.DataFrame:
    typed = events.copy()
    if "cold_season_flag" in typed.columns:
        typed["cold_season_indicator"] = typed["cold_season_flag"].astype(str).str.lower().isin(["true", "1"])
    else:
        typed["cold_season_indicator"] = False

    recent_rain_24h = descriptor_score(typed, "recent_rain_24h", high_is_good=True, score_scope=score_scope)
    peak_intensity = descriptor_score(typed, "peak_rain_intensity_6h", high_is_good=True, score_scope=score_scope)
    short_rise = descriptor_score(typed, "rising_time_hours", high_is_good=False, score_scope=score_scope)

    antecedent_7d = descriptor_score(typed, "antecedent_rain_7d", high_is_good=True, score_scope=score_scope)
    antecedent_30d = descriptor_score(typed, "antecedent_rain_30d", high_is_good=True, score_scope=score_scope)
    long_duration = descriptor_score(typed, "event_duration_hours", high_is_good=True, score_scope=score_scope)

    snow_fraction_global = rank_score_global(numeric_series(typed, "snow_fraction"), high_is_good=True)
    low_antecedent_temp = descriptor_score(
        typed,
        "antecedent_mean_temp_7d",
        high_is_good=False,
        score_scope=score_scope,
    )

    typed["recent_precipitation_score"] = pd.concat([recent_rain_24h, peak_intensity, short_rise], axis=1).mean(axis=1)
    typed["antecedent_precipitation_score"] = pd.concat(
        [antecedent_7d, antecedent_30d, long_duration],
        axis=1,
    ).mean(axis=1)
    typed["snowmelt_or_rain_on_snow_score"] = pd.concat(
        [typed["cold_season_indicator"].astype(float), snow_fraction_global, low_antecedent_temp],
        axis=1,
    ).mean(axis=1)

    score_to_label = {
        "recent_precipitation_score": "recent_precipitation",
        "antecedent_precipitation_score": "antecedent_precipitation",
        "snowmelt_or_rain_on_snow_score": "snowmelt_or_rain_on_snow",
    }
    score_frame = typed[TYPE_SCORE_COLUMNS].astype(float)
    top_column = score_frame.idxmax(axis=1)
    typed["flood_generation_method"] = "rank_score_v1"
    typed["flood_generation_type"] = top_column.map(score_to_label)
    typed["flood_generation_subtype"] = typed["flood_generation_type"]
    sorted_scores = np.sort(score_frame.to_numpy(dtype=float), axis=1)
    typed["flood_generation_score_margin"] = sorted_scores[:, -1] - sorted_scores[:, -2]
    typed["low_confidence_type_flag"] = typed["flood_generation_score_margin"] < low_confidence_margin
    typed = typed.drop(columns=["cold_season_indicator"])
    return typed


def summarize_basin_types(typed_events: pd.DataFrame, dominance_threshold: float) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    metadata_cols = ["gauge_name", "state", "huc02", "drain_sqkm_attr", "area", "snow_fraction"]

    for gauge_id, group in typed_events.groupby("gauge_id", sort=True):
        counts = group["flood_generation_type"].value_counts()
        event_count = int(len(group))
        proportions = {label: float(counts.get(label, 0) / event_count) for label in fu.FLOOD_TYPES}
        dominant_type = max(proportions, key=proportions.get)
        dominant_share = proportions[dominant_type]
        basin_label = dominant_type if dominant_share >= dominance_threshold else "mixture"

        row: dict[str, object] = {
            "gauge_id": gauge_id,
            "event_count": event_count,
            "dominant_flood_generation_type": basin_label,
            "dominant_type_if_any": dominant_type,
            "dominant_type_share": dominant_share,
            "recent_precipitation_count": int(counts.get("recent_precipitation", 0)),
            "antecedent_precipitation_count": int(counts.get("antecedent_precipitation", 0)),
            "snowmelt_or_rain_on_snow_count": int(counts.get("snowmelt_or_rain_on_snow", 0)),
            "uncertain_high_flow_candidate_count": int(counts.get("uncertain_high_flow_candidate", 0)),
            "recent_precipitation_share": proportions["recent_precipitation"],
            "antecedent_precipitation_share": proportions["antecedent_precipitation"],
            "snowmelt_or_rain_on_snow_share": proportions["snowmelt_or_rain_on_snow"],
            "uncertain_high_flow_candidate_share": proportions["uncertain_high_flow_candidate"],
            "low_confidence_event_share": float(group["low_confidence_type_flag"].mean()),
        }
        for label in ["recent_precipitation", "antecedent_precipitation", "snowmelt_or_rain_on_snow"]:
            score_col = f"{label}_score"
            strength_col = f"{label}_strength"
            if score_col in group.columns:
                row[f"mean_{score_col}"] = float(pd.to_numeric(group[score_col], errors="coerce").mean())
            if strength_col in group.columns:
                row[f"mean_{strength_col}"] = float(pd.to_numeric(group[strength_col], errors="coerce").mean())
        first = group.iloc[0]
        for col in metadata_cols:
            row[col] = first.get(col, pd.NA)
        rows.append(row)

    leading = ["gauge_id", *metadata_cols, "event_count"]
    remaining = [col for col in rows[0].keys() if col not in leading] if rows else []
    return pd.DataFrame(rows, columns=[*leading, *remaining])


def main() -> None:
    args = parse_args()
    table_dir = args.output_dir / "flood_generation" / "tables"
    metadata_dir = args.output_dir / "flood_generation" / "metadata"
    table_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    metadata_paths = args.metadata_csv if args.metadata_csv is not None else DEFAULT_METADATA
    events = read_events(args.event_response_csv)
    events = ensure_metadata(events, metadata_paths)
    if events.empty:
        raise SystemExit("Event response table is empty; no flood generation typing was produced.")

    if args.method == "rank_score_v1":
        typed_events = classify_events_rank_score(
            events,
            score_scope=args.score_scope,
            low_confidence_margin=args.low_confidence_margin,
        )
    else:
        typed_events = classify_events_degree_day(
            events,
            precip_low_confidence_relative_margin=args.precip_low_confidence_relative_margin,
        )
    basin_summary = summarize_basin_types(typed_events, args.dominance_threshold)

    typed_events_path = table_dir / "flood_generation_event_types.csv"
    basin_summary_path = table_dir / "flood_generation_basin_summary.csv"
    summary_path = metadata_dir / "flood_generation_typing_summary.json"

    typed_events.to_csv(typed_events_path, index=False)
    basin_summary.to_csv(basin_summary_path, index=False)

    label_counts = basin_summary["dominant_flood_generation_type"].value_counts(dropna=False).to_dict()
    event_type_counts = typed_events["flood_generation_type"].value_counts(dropna=False).to_dict()
    summary = {
        "event_response_csv": str(args.event_response_csv),
        "event_count": int(len(typed_events)),
        "basin_count": int(len(basin_summary)),
        "method": args.method,
        "score_scope": args.score_scope,
        "dominance_threshold": args.dominance_threshold,
        "low_confidence_margin": args.low_confidence_margin,
        "precip_low_confidence_relative_margin": args.precip_low_confidence_relative_margin,
        "degree_day_tcrit_c": fu.DEGREE_DAY_TCRIT_C,
        "degree_day_factor_mm_per_day_c": fu.DEGREE_DAY_FACTOR_MM_PER_DAY_C,
        "snowmelt_min_mm": fu.SNOWMELT_MIN_MM,
        "snowmelt_min_valid_window_count": fu.SNOWMELT_MIN_VALID_WINDOW_COUNT,
        "event_type_counts": {str(key): int(value) for key, value in event_type_counts.items()},
        "basin_label_counts": {str(key): int(value) for key, value in label_counts.items()},
        "outputs": {
            "flood_generation_event_types": str(typed_events_path),
            "flood_generation_basin_summary": str(basin_summary_path),
        },
    }
    summary_path.write_text(json.dumps(json_safe(summary), indent=2), encoding="utf-8")

    print(f"Wrote event flood-generation typing: {typed_events_path}")
    print(f"Wrote basin flood-generation summary: {basin_summary_path}")
    print(f"Wrote summary: {summary_path}")


if __name__ == "__main__":
    main()
