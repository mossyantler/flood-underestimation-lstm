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

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

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
            "Classify CAMELSH flood events into rule-based flood generation types "
            "and summarize dominant basin-level typing."
        )
    )
    parser.add_argument(
        "--event-response-csv",
        type=Path,
        default=Path("output/basin/camelsh_all/flood_analysis/event_response_table.csv"),
        help="Event response table produced by build_camelsh_event_response_table.py.",
    )
    parser.add_argument("--metadata-csv", type=Path, action="append", default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/basin/camelsh_all/flood_analysis"),
        help="Directory for flood-generation typing outputs.",
    )
    parser.add_argument(
        "--dominance-threshold",
        type=float,
        default=0.6,
        help="Minimum event-type share required to call a basin dominant rather than mixture.",
    )
    parser.add_argument(
        "--score-scope",
        choices=["basin", "global"],
        default="basin",
        help="Rank recent/antecedent/temperature descriptors within each basin or globally.",
    )
    parser.add_argument(
        "--low-confidence-margin",
        type=float,
        default=0.05,
        help="Top-minus-second score margin below which an event is flagged as low confidence.",
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


def classify_events(events: pd.DataFrame, *, score_scope: str, low_confidence_margin: float) -> pd.DataFrame:
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
    typed["flood_generation_type"] = top_column.map(score_to_label)
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
            "recent_precipitation_share": proportions["recent_precipitation"],
            "antecedent_precipitation_share": proportions["antecedent_precipitation"],
            "snowmelt_or_rain_on_snow_share": proportions["snowmelt_or_rain_on_snow"],
            "mean_recent_precipitation_score": float(group["recent_precipitation_score"].mean()),
            "mean_antecedent_precipitation_score": float(group["antecedent_precipitation_score"].mean()),
            "mean_snowmelt_or_rain_on_snow_score": float(group["snowmelt_or_rain_on_snow_score"].mean()),
            "low_confidence_event_share": float(group["low_confidence_type_flag"].mean()),
        }
        first = group.iloc[0]
        for col in metadata_cols:
            row[col] = first.get(col, pd.NA)
        rows.append(row)

    leading = ["gauge_id", *metadata_cols, "event_count"]
    remaining = [col for col in rows[0].keys() if col not in leading] if rows else []
    return pd.DataFrame(rows, columns=[*leading, *remaining])


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    metadata_paths = args.metadata_csv if args.metadata_csv is not None else DEFAULT_METADATA
    events = read_events(args.event_response_csv)
    events = ensure_metadata(events, metadata_paths)
    if events.empty:
        raise SystemExit("Event response table is empty; no flood generation typing was produced.")

    typed_events = classify_events(
        events,
        score_scope=args.score_scope,
        low_confidence_margin=args.low_confidence_margin,
    )
    basin_summary = summarize_basin_types(typed_events, args.dominance_threshold)

    typed_events_path = args.output_dir / "flood_generation_event_types.csv"
    basin_summary_path = args.output_dir / "flood_generation_basin_summary.csv"
    summary_path = args.output_dir / "flood_generation_typing_summary.json"

    typed_events.to_csv(typed_events_path, index=False)
    basin_summary.to_csv(basin_summary_path, index=False)

    label_counts = basin_summary["dominant_flood_generation_type"].value_counts(dropna=False).to_dict()
    event_type_counts = typed_events["flood_generation_type"].value_counts(dropna=False).to_dict()
    summary = {
        "event_response_csv": str(args.event_response_csv),
        "event_count": int(len(typed_events)),
        "basin_count": int(len(basin_summary)),
        "score_scope": args.score_scope,
        "dominance_threshold": args.dominance_threshold,
        "low_confidence_margin": args.low_confidence_margin,
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
