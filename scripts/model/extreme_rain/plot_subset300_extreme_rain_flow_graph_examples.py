#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "xarray>=2024.1",
#   "netCDF4>=1.6",
# ]
# ///

from __future__ import annotations

import argparse
import math
import os
import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
import xarray as xr


DEFAULT_COHORT_CSV = Path("output/model_analysis/extreme_rain/primary/exposure/drbc_historical_stress_cohort.csv")
DEFAULT_STRESS_LONG_CSV = Path("output/model_analysis/extreme_rain/primary/analysis/extreme_rain_stress_error_table_long.csv")
DEFAULT_SERIES_DIR = Path("output/model_analysis/extreme_rain/primary/inference/required_series")
DEFAULT_DATA_DIR = Path("data/CAMELSH_generic/drbc_holdout_broad/time_series")
DEFAULT_OUTPUT_DIR = Path("output/model_analysis/extreme_rain/primary/flow_graph_diagnostic")
DEFAULT_RETURN_PERIOD_CSV = Path("output/basin/all/analysis/return_period/tables/return_period_reference_table.csv")
DEFAULT_BASIN_SCREENING_CSV = Path("output/basin/drbc/screening/drbc_provisional_screening_table.csv")
DEFAULT_STREAMFLOW_QUALITY_CSV = Path("output/basin/drbc/screening/drbc_streamflow_quality_table.csv")
DEFAULT_SEEDS = [111, 222, 444]
PRECIP_PERIODS = (25, 50, 100)
PRECIP_DURATIONS = (1, 6, 24, 72)
PRECIP_LINE_STYLES = {
    25: ("#0f766e", "--"),
    50: ("#0891b2", "-."),
    100: ("#4f46e5", ":"),
}

TIME_COLUMNS = [
    "rain_start",
    "rain_peak",
    "rain_end",
    "response_window_start",
    "response_window_end",
    "observed_response_peak_time",
]
PREDICTORS = [
    ("model1", "Model 1"),
    ("q50", "Model 2 q50"),
    ("q95", "Model 2 q95"),
    ("q99", "Model 2 q99"),
]
LINE_STYLES = {
    "obs": {"color": "#111827", "linewidth": 1.35, "linestyle": "-", "label": "Observed"},
    "model1": {"color": "#2563eb", "linewidth": 1.0, "linestyle": "-", "label": "Model 1"},
    "q50": {"color": "#dc2626", "linewidth": 1.05, "linestyle": "-", "label": "Model 2 q50"},
    "q95": {"color": "#f97316", "linewidth": 0.95, "linestyle": "--", "label": "Model 2 q95"},
    "q99": {"color": "#d97706", "linewidth": 0.95, "linestyle": "--", "label": "Model 2 q99"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Select representative primary extreme-rain stress events and plot observed/model flow "
            "graphs with separate seed panels."
        )
    )
    parser.add_argument("--cohort-csv", type=Path, default=DEFAULT_COHORT_CSV)
    parser.add_argument("--stress-long-csv", type=Path, default=DEFAULT_STRESS_LONG_CSV)
    parser.add_argument("--series-dir", type=Path, default=DEFAULT_SERIES_DIR)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--return-period-csv", type=Path, default=DEFAULT_RETURN_PERIOD_CSV)
    parser.add_argument("--basin-screening-csv", type=Path, default=DEFAULT_BASIN_SCREENING_CSV)
    parser.add_argument("--streamflow-quality-csv", type=Path, default=DEFAULT_STREAMFLOW_QUALITY_CSV)
    parser.add_argument("--seeds", type=int, nargs="+", default=DEFAULT_SEEDS)
    parser.add_argument("--padding-hours", type=int, default=24)
    return parser.parse_args()


def normalize_gauge_id(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(8)


def safe_float(value: Any) -> float:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return float(numeric) if pd.notna(numeric) else math.nan


def fmt_float(value: Any, digits: int = 2) -> str:
    numeric = safe_float(value)
    return f"{numeric:.{digits}f}" if np.isfinite(numeric) else "NA"


def safe_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def date_num(value: Any) -> float:
    return mdates.date2num(pd.Timestamp(value).to_pydatetime())


def read_cohort(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing cohort CSV: {path}")
    cohort = pd.read_csv(path, dtype={"gauge_id": str, "event_id": str}, parse_dates=TIME_COLUMNS)
    cohort["gauge_id"] = cohort["gauge_id"].map(normalize_gauge_id)
    return cohort.sort_values(["gauge_id", "rain_start", "event_id"]).reset_index(drop=True)


def read_stress_long(path: Path, seeds: list[int]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing stress long CSV: {path}")
    long_df = pd.read_csv(path, dtype={"gauge_id": str, "event_id": str})
    long_df["gauge_id"] = long_df["gauge_id"].map(normalize_gauge_id)
    long_df = long_df[long_df["seed"].isin(seeds)].copy()
    numeric_cols = [
        "obs_peak_under_deficit_pct",
        "threshold_exceedance_recall",
        "pred_window_peak_to_flood_ari25",
        "pred_window_peak_to_flood_ari100",
        "obs_peak_to_flood_ari25",
        "obs_peak_to_flood_ari100",
    ]
    for col in numeric_cols:
        if col in long_df:
            long_df[col] = pd.to_numeric(long_df[col], errors="coerce")
    return long_df


def build_seed_event_wide(long_df: pd.DataFrame) -> pd.DataFrame:
    index_cols = ["seed", "gauge_id", "event_id", "response_class", "rain_cohort"]
    value_cols = [
        "obs_peak_under_deficit_pct",
        "threshold_exceedance_recall",
        "pred_window_peak_to_flood_ari25",
        "pred_window_peak_to_flood_ari100",
        "obs_peak_to_flood_ari25",
        "obs_peak_to_flood_ari100",
    ]
    wide = long_df[index_cols + ["predictor", *value_cols]].pivot_table(
        index=index_cols,
        columns="predictor",
        values=value_cols,
        aggfunc="first",
    )
    wide.columns = [f"{metric}__{predictor}" for metric, predictor in wide.columns]
    wide = wide.reset_index()
    wide["q95_deficit_reduction"] = (
        wide["obs_peak_under_deficit_pct__model1"] - wide["obs_peak_under_deficit_pct__q95"]
    )
    wide["q99_deficit_reduction"] = (
        wide["obs_peak_under_deficit_pct__model1"] - wide["obs_peak_under_deficit_pct__q99"]
    )
    wide["q99_minus_model1_ari100"] = (
        wide["pred_window_peak_to_flood_ari100__q99"] - wide["pred_window_peak_to_flood_ari100__model1"]
    )
    return wide


def aggregate_event_candidates(seed_wide: pd.DataFrame) -> pd.DataFrame:
    agg = (
        seed_wide.groupby(["gauge_id", "event_id", "response_class", "rain_cohort"], as_index=False)
        .agg(
            seed_count=("seed", "nunique"),
            model1_deficit_mean=("obs_peak_under_deficit_pct__model1", "mean"),
            q50_deficit_mean=("obs_peak_under_deficit_pct__q50", "mean"),
            q95_deficit_mean=("obs_peak_under_deficit_pct__q95", "mean"),
            q99_deficit_mean=("obs_peak_under_deficit_pct__q99", "mean"),
            mean_q95_deficit_reduction=("q95_deficit_reduction", "mean"),
            mean_q99_deficit_reduction=("q99_deficit_reduction", "mean"),
            min_q99_deficit_reduction=("q99_deficit_reduction", "min"),
            model1_recall_mean=("threshold_exceedance_recall__model1", "mean"),
            q99_recall_mean=("threshold_exceedance_recall__q99", "mean"),
            model1_ari100_mean=("pred_window_peak_to_flood_ari100__model1", "mean"),
            q95_ari100_mean=("pred_window_peak_to_flood_ari100__q95", "mean"),
            q99_ari100_mean=("pred_window_peak_to_flood_ari100__q99", "mean"),
            q99_minus_model1_ari100_mean=("q99_minus_model1_ari100", "mean"),
            obs_ari25=("obs_peak_to_flood_ari25__model1", "first"),
            obs_ari100=("obs_peak_to_flood_ari100__model1", "first"),
        )
        .reset_index(drop=True)
    )
    return agg


def first_candidate(frame: pd.DataFrame, *, case_key: str) -> pd.Series:
    if frame.empty:
        raise ValueError(f"No candidate found for {case_key}")
    return frame.iloc[0]


def select_cases(candidates: pd.DataFrame, expected_seed_count: int) -> pd.DataFrame:
    complete = candidates[candidates["seed_count"].eq(expected_seed_count)].copy()
    ge25 = complete[
        complete["response_class"].eq("flood_response_ge25") & complete["model1_deficit_mean"].ge(30.0)
    ].sort_values(["mean_q99_deficit_reduction", "min_q99_deficit_reduction"], ascending=False)

    ge2 = complete[
        complete["response_class"].eq("flood_response_ge2_to_lt25")
        & complete["model1_deficit_mean"].ge(30.0)
        & complete["q99_ari100_mean"].lt(1.0)
    ].sort_values(["mean_q99_deficit_reduction", "min_q99_deficit_reduction"], ascending=False)
    if ge2.empty:
        ge2 = complete[
            complete["response_class"].eq("flood_response_ge2_to_lt25")
            & complete["model1_deficit_mean"].ge(30.0)
        ].sort_values(["mean_q99_deficit_reduction", "min_q99_deficit_reduction"], ascending=False)

    low_response = complete[
        complete["response_class"].eq("low_response_below_q99")
        & complete["model1_ari100_mean"].lt(1.0)
        & complete["q99_ari100_mean"].gt(1.0)
        & complete["obs_ari100"].lt(0.25)
    ].sort_values(["q99_minus_model1_ari100_mean", "q99_ari100_mean"], ascending=False)
    if low_response.empty:
        low_response = complete[complete["response_class"].eq("low_response_below_q99")].sort_values(
            ["q99_minus_model1_ari100_mean", "q99_ari100_mean"], ascending=False
        )

    rows = [
        (
            "positive_ge25_q99_capture",
            "Positive response >=25yr proxy: q99 peak capture",
            "Select the complete-seed ARI25+ positive-response event with the largest mean q99 under-deficit reduction vs Model 1.",
            first_candidate(ge25, case_key="positive_ge25_q99_capture"),
        ),
        (
            "positive_ge2_q99_capture",
            "Positive response 2-25yr proxy: q99 peak capture",
            "Select the complete-seed ARI2-25 positive-response event with strong q99 under-deficit reduction and mean q99/ARI100 below 1 when available.",
            first_candidate(ge2, case_key="positive_ge2_q99_capture"),
        ),
        (
            "negative_low_response_q99_false_positive",
            "Negative control below Q99: q99 false-positive exposure",
            "Select the complete-seed low-response event where q99 increases predicted peak / ARI100 most while Model 1 stays below ARI100 on average.",
            first_candidate(low_response, case_key="negative_low_response_q99_false_positive"),
        ),
    ]
    selected = []
    for case_key, case_label, selection_rule, row in rows:
        item = row.to_dict()
        item["case_key"] = case_key
        item["case_label"] = case_label
        item["selection_rule"] = selection_rule
        selected.append(item)
    return pd.DataFrame(selected)


def read_required_series(series_dir: Path, seed: int) -> pd.DataFrame:
    path = series_dir / f"seed{seed}" / "primary_required_series.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing required-series file: {path}")
    df = pd.read_csv(path, dtype={"basin": str}, parse_dates=["datetime"])
    df["basin"] = df["basin"].map(normalize_gauge_id)
    for col in ["obs", "model1", "q50", "q90", "q95", "q99"]:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values(["basin", "datetime"]).reset_index(drop=True)


def read_rain_series(data_dir: Path, gauge_id: str) -> pd.Series:
    path = data_dir / f"{gauge_id}.nc"
    if not path.exists():
        raise FileNotFoundError(f"Missing basin time-series file: {path}")
    with xr.open_dataset(path) as ds:
        if "Rainf" not in ds:
            raise KeyError(f"{path} must contain Rainf")
        rain = pd.Series(ds["Rainf"].values.astype(float), index=pd.to_datetime(ds["date"].values), name="Rainf")
    return rain.sort_index()


def finite_max(values: list[float]) -> float:
    finite = [value for value in values if np.isfinite(value)]
    return max(finite) if finite else math.nan


def precip_reference_columns() -> list[str]:
    return [
        *(f"prec_ari{period}_{duration}h" for period in PRECIP_PERIODS for duration in PRECIP_DURATIONS),
        "prec_ari_source",
    ]


def precip_event_columns() -> list[str]:
    return [
        *(f"dominant_duration_for_ari{period}h" for period in PRECIP_PERIODS),
        *(f"max_prec_ari{period}_{duration}h_ratio" for period in PRECIP_PERIODS for duration in PRECIP_DURATIONS),
    ]


def add_precip_references(events: pd.DataFrame, return_period_csv: Path) -> pd.DataFrame:
    if not return_period_csv.exists():
        raise FileNotFoundError(f"Missing return-period reference CSV: {return_period_csv}")
    refs = pd.read_csv(return_period_csv, dtype={"gauge_id": str})
    refs["gauge_id"] = refs["gauge_id"].map(normalize_gauge_id)
    merge_cols = [col for col in precip_reference_columns() if col in refs.columns and col not in events.columns]
    if not merge_cols:
        return events
    return events.merge(refs[["gauge_id", *merge_cols]], on="gauge_id", how="left", validate="many_to_one")


def basin_metadata_columns() -> list[str]:
    return [
        "gauge_name",
        "state",
        "drain_sqkm_attr",
        "hydromod_risk",
        "forest_pct",
        "developed_pct",
        "wetland_pct",
        "dom_land_cover",
        "snow_influenced_tag",
        "steep_fast_response_tag",
        "coastal_or_hydromod_risk_tag",
        "screening_notes",
        "NDAMS_2009",
        "STOR_NOR_2009",
        "MAJ_NDAMS_2009",
        "DDENS_2009",
        "CANALS_PCT",
        "NPDES_MAJ_DENS",
        "POWER_NUM_PTS",
        "FRESHW_WITHDRAWAL",
    ]


def add_basin_metadata(
    events: pd.DataFrame,
    basin_screening_csv: Path,
    streamflow_quality_csv: Path,
) -> pd.DataFrame:
    out = events.copy()
    if basin_screening_csv.exists():
        screening = pd.read_csv(basin_screening_csv, dtype={"gauge_id": str})
        screening["gauge_id"] = screening["gauge_id"].map(normalize_gauge_id)
        screening = screening.drop_duplicates("gauge_id")
        screening_cols = [
            col
            for col in [
                "gauge_name",
                "state",
                "drain_sqkm_attr",
                "hydromod_risk",
                "forest_pct",
                "developed_pct",
                "wetland_pct",
                "dom_land_cover",
                "snow_influenced_tag",
                "steep_fast_response_tag",
                "coastal_or_hydromod_risk_tag",
                "screening_notes",
            ]
            if col in screening.columns and col not in out.columns
        ]
        if screening_cols:
            out = out.merge(
                screening[["gauge_id", *screening_cols]],
                on="gauge_id",
                how="left",
                validate="many_to_one",
            )
    if streamflow_quality_csv.exists():
        quality = pd.read_csv(streamflow_quality_csv, dtype={"gauge_id": str})
        quality["gauge_id"] = quality["gauge_id"].map(normalize_gauge_id)
        quality = quality.drop_duplicates("gauge_id")
        quality_cols = [
            col
            for col in [
                "NDAMS_2009",
                "STOR_NOR_2009",
                "MAJ_NDAMS_2009",
                "DDENS_2009",
                "CANALS_PCT",
                "NPDES_MAJ_DENS",
                "POWER_NUM_PTS",
                "FRESHW_WITHDRAWAL",
            ]
            if col in quality.columns and col not in out.columns
        ]
        if quality_cols:
            out = out.merge(
                quality[["gauge_id", *quality_cols]],
                on="gauge_id",
                how="left",
                validate="many_to_one",
            )
    return out


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def shorten_text(value: Any, max_chars: int = 44) -> str:
    if pd.isna(value):
        return ""
    text = re.sub(r"\s+", " ", str(value).strip())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def fmt_area(value: Any) -> str:
    numeric = safe_float(value)
    if not np.isfinite(numeric):
        return "NA"
    if numeric >= 100:
        return f"{numeric:,.0f}"
    return f"{numeric:.1f}"


def fmt_pct(value: Any, digits: int = 0) -> str:
    numeric = safe_float(value)
    return f"{numeric:.{digits}f}%" if np.isfinite(numeric) else "NA"


def compact_items(items: list[str], max_items: int = 4) -> list[str]:
    clean = [item for item in items if item]
    if len(clean) <= max_items:
        return clean
    return [*clean[:max_items], f"+{len(clean) - max_items} more"]


def natural_tag_labels(event: pd.Series) -> list[str]:
    labels: list[str] = []
    hydromod = boolish(event.get("hydromod_risk")) or boolish(event.get("coastal_or_hydromod_risk_tag"))
    labels.append("hydromod caution" if hydromod else "low hydromod proxy")
    if boolish(event.get("snow_influenced_tag")):
        labels.append("snow-influenced")
    if boolish(event.get("steep_fast_response_tag")):
        labels.append("steep-fast")
    forest = safe_float(event.get("forest_pct"))
    developed = safe_float(event.get("developed_pct"))
    wetland = safe_float(event.get("wetland_pct"))
    if np.isfinite(forest) and forest >= 50:
        labels.append("forested")
    if np.isfinite(developed) and developed >= 15:
        labels.append("developed")
    if np.isfinite(wetland) and wetland >= 10:
        labels.append("wetland")
    land_cover = shorten_text(str(event.get("dom_land_cover", "")).replace("_", " "), max_chars=24)
    if land_cover and land_cover.lower() != "nan":
        labels.append(f"landcover {land_cover}")
    return compact_items(labels, max_items=4)


def human_impact_labels(event: pd.Series) -> list[str]:
    labels: list[str] = []
    major_dams = safe_float(event.get("MAJ_NDAMS_2009"))
    dams = safe_float(event.get("NDAMS_2009"))
    storage = safe_float(event.get("STOR_NOR_2009"))
    canals = safe_float(event.get("CANALS_PCT"))
    water_use = safe_float(event.get("FRESHW_WITHDRAWAL"))
    npdes = safe_float(event.get("NPDES_MAJ_DENS"))
    power = safe_float(event.get("POWER_NUM_PTS"))
    if np.isfinite(major_dams) and major_dams > 0:
        labels.append(f"major dams {major_dams:.0f}")
    if np.isfinite(dams) and dams > 0:
        labels.append(f"dams {dams:.0f}")
    if np.isfinite(storage) and storage > 0:
        labels.append(f"storage {storage:.0f} ML/km2")
    if np.isfinite(canals) and canals > 0:
        labels.append(f"canals {canals:.1f}%")
    if np.isfinite(water_use) and water_use > 0:
        labels.append(f"water use {water_use:.0f} ML/yr/km2")
    if np.isfinite(npdes) and npdes > 0:
        labels.append(f"NPDES {npdes:.2f}")
    if np.isfinite(power) and power > 0:
        labels.append(f"power pts {power:.0f}")
    if not labels:
        return ["low hydromod proxy"]
    return compact_items(labels, max_items=4)


def basin_legend_lines(event: pd.Series) -> list[str]:
    gauge_name = shorten_text(event.get("gauge_name"), max_chars=44)
    gauge_line = str(event.get("gauge_id", ""))
    if gauge_name:
        gauge_line = f"{gauge_line} | {gauge_name}"
    area_line = (
        f"area {fmt_area(event.get('drain_sqkm_attr'))} km2 | "
        f"forest {fmt_pct(event.get('forest_pct'))} | developed {fmt_pct(event.get('developed_pct'))}"
    )
    tag_line = "tags: " + "; ".join(natural_tag_labels(event))
    human_line = "human impact: " + "; ".join(human_impact_labels(event))
    return [gauge_line, area_line, tag_line, human_line]


def dominant_precip_duration(event: pd.Series, period: int) -> int | None:
    explicit = safe_float(event.get(f"dominant_duration_for_ari{period}h"))
    if np.isfinite(explicit) and int(explicit) in PRECIP_DURATIONS:
        return int(explicit)
    candidates: list[tuple[float, int]] = []
    for duration in PRECIP_DURATIONS:
        ratio = safe_float(event.get(f"max_prec_ari{period}_{duration}h_ratio"))
        if np.isfinite(ratio):
            candidates.append((ratio, duration))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def precip_ari_items(event: pd.Series) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for period in PRECIP_PERIODS:
        duration = dominant_precip_duration(event, period)
        if duration is None:
            continue
        total = safe_float(event.get(f"prec_ari{period}_{duration}h"))
        if not np.isfinite(total) or total <= 0:
            continue
        color, linestyle = PRECIP_LINE_STYLES[period]
        items.append(
            {
                "period": period,
                "duration": duration,
                "total": total,
                "intensity": total / duration,
                "ratio": safe_float(event.get(f"max_prec_ari{period}_ratio")),
                "color": color,
                "linestyle": linestyle,
                "label": f"prec ARI{period} {duration}h avg",
            }
        )
    return items


def threshold_items(event: pd.Series) -> list[tuple[str, float, str, str]]:
    return [
        ("Q99", safe_float(event.get("streamflow_q99_threshold")), "#71717a", ":"),
        ("flood ARI2", safe_float(event.get("flood_ari2")), "#ea580c", "--"),
        ("flood ARI25", safe_float(event.get("flood_ari25")), "#dc2626", "--"),
        ("flood ARI100", safe_float(event.get("flood_ari100")), "#7f1d1d", "--"),
    ]


def rain_threshold_items(event: pd.Series) -> list[tuple[str, float, str, str]]:
    return [
        ("wet threshold", safe_float(event.get("wet_rain_threshold_mm_h")), "#1d4ed8", ":"),
    ]


def section_handle() -> Line2D:
    return Line2D([], [], linestyle="none", linewidth=0, color="none")


def external_legend_items(event: pd.Series, precip_items: list[dict[str, Any]]) -> tuple[list[Any], list[str]]:
    handles: list[Any] = [
        section_handle(),
        Patch(facecolor="#2563eb", edgecolor="#2563eb", alpha=0.82),
        Patch(facecolor="#1d4ed8", edgecolor="#1d4ed8", alpha=0.16),
        Line2D([], [], color="#1d4ed8", linewidth=1.0, linestyle="-"),
        Line2D([], [], color="#1d4ed8", linewidth=1.0, linestyle="--"),
        Line2D([], [], color="#1d4ed8", linewidth=0.9, linestyle=":"),
    ]
    labels = [
        "Rain",
        "Rainf bars",
        "rain event",
        "rain_start / rain_end",
        "rain_peak",
        f"wet cutoff: {fmt_float(event.get('wet_rain_threshold_mm_h'))} mm/h",
    ]
    for item in precip_items:
        handles.append(Line2D([], [], color=item["color"], linewidth=0.9, linestyle=item["linestyle"]))
        labels.append(
            f"prec ARI{item['period']} {item['duration']}h avg: "
            f"{fmt_float(item['total'], 1)} mm / {fmt_float(item['intensity'])} mm/h, "
            f"ratio {fmt_float(item['ratio'])}"
        )

    handles.extend(
        [
            section_handle(),
            Patch(facecolor="#f97316", edgecolor="#f97316", alpha=0.08),
            Patch(facecolor="#f97316", edgecolor="#f97316", alpha=0.13),
            Patch(facecolor="#f59e0b", edgecolor="#f59e0b", alpha=0.12),
            Line2D([], [], color=LINE_STYLES["model1"]["color"], linewidth=LINE_STYLES["model1"]["linewidth"]),
            Line2D([], [], color=LINE_STYLES["q50"]["color"], linewidth=LINE_STYLES["q50"]["linewidth"]),
            Line2D([], [], color=LINE_STYLES["q95"]["color"], linewidth=LINE_STYLES["q95"]["linewidth"], linestyle="--"),
            Line2D([], [], color=LINE_STYLES["q99"]["color"], linewidth=LINE_STYLES["q99"]["linewidth"], linestyle="--"),
            Line2D([], [], color=LINE_STYLES["obs"]["color"], linewidth=LINE_STYLES["obs"]["linewidth"]),
            Line2D([], [], color="#dc2626", marker="o", linestyle="none", markersize=6),
            Line2D([], [], color="#71717a", linewidth=0.85, linestyle=":"),
            Line2D([], [], color="#ea580c", linewidth=0.85, linestyle="--"),
            Line2D([], [], color="#dc2626", linewidth=0.85, linestyle="--"),
            Line2D([], [], color="#7f1d1d", linewidth=0.85, linestyle="--"),
        ]
    )
    labels.extend(
        [
            "Streamflow",
            "response window",
            "q50-q95 band",
            "q95-q99 band",
            "Model 1",
            "Model 2 q50",
            "Model 2 q95",
            "Model 2 q99",
            "Observed",
            "Observed peak",
            f"Q99: {fmt_float(event.get('streamflow_q99_threshold'))}",
            f"flood ARI2: {fmt_float(event.get('flood_ari2'))}",
            f"flood ARI25: {fmt_float(event.get('flood_ari25'))}",
            f"flood ARI100: {fmt_float(event.get('flood_ari100'))}",
        ]
    )
    handles.append(section_handle())
    labels.append("Basin")
    for line in basin_legend_lines(event):
        handles.append(section_handle())
        labels.append(line)
    return handles, labels


def add_external_legend(fig: Any, top_axis: Any, event: pd.Series, precip_items: list[dict[str, Any]]) -> None:
    handles, labels = external_legend_items(event, precip_items)
    fig.canvas.draw()
    legend_top = top_axis.get_position().y1
    legend = fig.legend(
        handles,
        labels,
        loc="upper left",
        bbox_to_anchor=(1.005, legend_top),
        frameon=True,
        fontsize=7.2,
        handlelength=2.0,
        borderpad=0.8,
        labelspacing=0.5,
    )
    legend.get_frame().set_edgecolor("#a1a1aa")
    legend.get_frame().set_alpha(0.96)
    for text in legend.get_texts():
        if text.get_text() in {"Rain", "Streamflow", "Basin"}:
            text.set_weight("bold")


def seed_metric_lookup(selected_long: pd.DataFrame, event_id: str, seed: int) -> dict[str, pd.Series]:
    frame = selected_long[(selected_long["event_id"].eq(event_id)) & (selected_long["seed"].eq(seed))]
    return {str(row["predictor"]): row for _, row in frame.iterrows()}


def axis_note(metrics: dict[str, pd.Series], response_class: str) -> str:
    model2_metrics = metrics.get("q50")
    bracket = ""
    if model2_metrics is not None and pd.notna(model2_metrics.get("model2_obs_peak_quantile_bracket_label")):
        bracket = f"\nobs peak bracket: {model2_metrics.get('model2_obs_peak_quantile_bracket_label')}"
    if response_class == "low_response_below_q99":
        return (
            "pred peak / ARI100: "
            f"M1 {fmt_float(metrics['model1'].get('pred_window_peak_to_flood_ari100'))}, "
            f"q50 {fmt_float(metrics['q50'].get('pred_window_peak_to_flood_ari100'))}, "
            f"q95 {fmt_float(metrics['q95'].get('pred_window_peak_to_flood_ari100'))}, "
            f"q99 {fmt_float(metrics['q99'].get('pred_window_peak_to_flood_ari100'))}"
            f"{bracket}"
        )
    return (
        "under-deficit: "
        f"M1 {fmt_float(metrics['model1'].get('obs_peak_under_deficit_pct'), 1)}%, "
        f"q50 {fmt_float(metrics['q50'].get('obs_peak_under_deficit_pct'), 1)}%, "
        f"q95 {fmt_float(metrics['q95'].get('obs_peak_under_deficit_pct'), 1)}%, "
        f"q99 {fmt_float(metrics['q99'].get('obs_peak_under_deficit_pct'), 1)}% | "
        "recall "
        f"M1 {fmt_float(metrics['model1'].get('threshold_exceedance_recall'))} -> "
        f"q99 {fmt_float(metrics['q99'].get('threshold_exceedance_recall'))}"
        f"{bracket}"
    )


def plot_case(
    *,
    case: pd.Series,
    event: pd.Series,
    all_series: dict[int, pd.DataFrame],
    rain: pd.Series,
    selected_long: pd.DataFrame,
    seeds: list[int],
    output_path: Path,
    padding_hours: int,
) -> None:
    rain_start = pd.Timestamp(event["rain_start"])
    rain_end = pd.Timestamp(event["rain_end"])
    response_start = pd.Timestamp(event["response_window_start"])
    response_end = pd.Timestamp(event["response_window_end"])
    plot_start = min(rain_start, response_start) - pd.Timedelta(hours=padding_hours)
    plot_end = response_end + pd.Timedelta(hours=padding_hours)

    fig, axes = plt.subplots(
        len(seeds) + 1,
        1,
        figsize=(14.2, 10.8),
        sharex=True,
        gridspec_kw={"height_ratios": [0.95, *([1.9] * len(seeds))]},
        constrained_layout=True,
    )
    ax_rain = axes[0]
    rain_window = rain.loc[plot_start:plot_end]
    rain_x = mdates.date2num(rain_window.index.to_pydatetime())
    ax_rain.bar(rain_x, rain_window.fillna(0.0).to_numpy(dtype=float), width=0.032, color="#2563eb", alpha=0.82)
    ax_rain.axvspan(date_num(rain_start), date_num(rain_end), color="#1d4ed8", alpha=0.16, label="rain event")
    ax_rain.axvline(date_num(rain_start), color="#1d4ed8", linewidth=1.0, linestyle="-", alpha=0.9, label="rain start/end")
    ax_rain.axvline(date_num(rain_end), color="#1d4ed8", linewidth=1.0, linestyle="-", alpha=0.9)
    ax_rain.axvline(date_num(event["rain_peak"]), color="#1d4ed8", linewidth=1.0, linestyle="--", label="rain peak")
    rain_max = safe_float(rain_window.max(skipna=True))
    rain_y_candidates = [rain_max]
    precip_items = precip_ari_items(event)
    for item in precip_items:
        ax_rain.axhline(
            item["intensity"],
            color=item["color"],
            linewidth=0.9,
            linestyle=item["linestyle"],
            alpha=0.78,
            label=item["label"],
        )
        rain_y_candidates.append(item["intensity"])
    for label, value, color, linestyle in rain_threshold_items(event):
        if not np.isfinite(value) or value <= 0:
            continue
        ax_rain.axhline(value, color=color, linewidth=0.9, linestyle=linestyle, alpha=0.78, label=label)
        rain_y_candidates.append(value)
    rain_y_max = finite_max(rain_y_candidates)
    ax_rain.set_ylim(0, rain_y_max * 1.18 if np.isfinite(rain_y_max) and rain_y_max > 0 else 1.0)
    ax_rain.set_ylabel("Rainf")
    ax_rain.grid(True, axis="y", color="#d4d4d8", linewidth=0.55, alpha=0.85)

    threshold_values = threshold_items(event)
    response_class = str(event["response_class"])
    for ax, seed in zip(axes[1:], seeds, strict=True):
        seed_series = all_series[seed]
        frame = seed_series[
            seed_series["basin"].eq(event["gauge_id"])
            & seed_series["datetime"].between(plot_start, plot_end, inclusive="both")
        ].copy()
        if frame.empty:
            raise ValueError(f"No required-series rows for seed {seed}, event {event['event_id']}")

        x = mdates.date2num(frame["datetime"].dt.to_pydatetime())
        ax.axvspan(date_num(response_start), date_num(response_end), color="#f97316", alpha=0.08)
        ax.axvspan(date_num(rain_start), date_num(rain_end), color="#1d4ed8", alpha=0.08)
        ax.fill_between(
            x,
            frame["q50"].to_numpy(dtype=float),
            frame["q95"].to_numpy(dtype=float),
            color="#f97316",
            alpha=0.13,
            linewidth=0,
            label="q50-q95",
        )
        ax.fill_between(
            x,
            frame["q95"].to_numpy(dtype=float),
            frame["q99"].to_numpy(dtype=float),
            color="#f59e0b",
            alpha=0.12,
            linewidth=0,
            label="q95-q99",
        )
        for col, _label in PREDICTORS:
            style = LINE_STYLES[col]
            ax.plot(
                x,
                frame[col].to_numpy(dtype=float),
                color=style["color"],
                linewidth=style["linewidth"],
                linestyle=style["linestyle"],
                label=style["label"],
            )
        obs_style = LINE_STYLES["obs"]
        ax.plot(
            x,
            frame["obs"].to_numpy(dtype=float),
            color=obs_style["color"],
            linewidth=obs_style["linewidth"],
            linestyle=obs_style["linestyle"],
            label=obs_style["label"],
        )

        obs_peak_time = event.get("observed_response_peak_time")
        obs_peak = safe_float(event.get("observed_response_peak"))
        if pd.notna(obs_peak_time) and np.isfinite(obs_peak):
            ax.scatter([date_num(obs_peak_time)], [obs_peak], s=28, color="#dc2626", zorder=5, label="Observed peak")

        data_max = finite_max(
            [
                safe_float(frame[col].max(skipna=True))
                for col in ["obs", "model1", "q50", "q95", "q99"]
                if col in frame
            ]
        )
        y_candidates = [data_max, obs_peak]
        for label, value, color, linestyle in threshold_values:
            if not np.isfinite(value) or value <= 0:
                continue
            if np.isfinite(data_max) and value > data_max * 3.0:
                continue
            ax.axhline(value, color=color, linewidth=0.85, linestyle=linestyle, alpha=0.72, label=label)
            y_candidates.append(value)
        y_max = finite_max(y_candidates)
        ax.set_ylim(0, y_max * 1.14 if np.isfinite(y_max) and y_max > 0 else 1.0)

        model1_epoch = int(frame["model1_epoch"].iloc[0]) if "model1_epoch" in frame else -1
        model2_epoch = int(frame["model2_epoch"].iloc[0]) if "model2_epoch" in frame else -1
        metrics = seed_metric_lookup(selected_long, str(event["event_id"]), seed)
        note = axis_note(metrics, response_class)
        ax.set_title(f"seed {seed} | M1 epoch {model1_epoch:03d} / M2 epoch {model2_epoch:03d}\n{note}", fontsize=8.7)
        ax.set_ylabel("Streamflow")
        ax.grid(True, axis="y", color="#d4d4d8", linewidth=0.55, alpha=0.85)

    axes[-1].xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=9))
    axes[-1].xaxis.set_major_formatter(mdates.ConciseDateFormatter(axes[-1].xaxis.get_major_locator()))
    for ax in axes:
        ax.xaxis_date()

    fig.suptitle(
        f"{case['case_label']}\n"
        f"{event['event_id']} | basin {event['gauge_id']} | rain={event['rain_cohort']} | "
        f"response={event['response_class']} | obs/flood25={fmt_float(event.get('obs_peak_to_flood_ari25'))} | "
        f"obs/flood100={fmt_float(event.get('obs_peak_to_flood_ari100'))}",
        fontsize=10.3,
    )
    add_external_legend(fig, ax_rain, event, precip_items)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def write_markdown_report(
    path: Path,
    *,
    selected_cases: pd.DataFrame,
    manifest: pd.DataFrame,
    tables_dir: Path,
) -> None:
    lines = [
        "# Primary Extreme-Rain Flow Graph Diagnostic",
        "",
        "This diagnostic overlays observed flow, Model 1, Model 2 q50, q95, and q99 for selected primary stress-test events.",
        "Each figure uses one event and separates seed 111, 222, and 444 into separate flow panels so seed-specific behavior stays visible.",
        "",
        "Selection is based on `analysis/extreme_rain_stress_error_table_long.csv`; it is a visual diagnostic, not a new primary metric.",
        "",
        "## Selected Cases",
        "",
    ]
    for _, row in selected_cases.iterrows():
        figure_row = manifest[manifest["case_key"].eq(row["case_key"])].iloc[0]
        rel_figure = os.path.relpath(figure_row["figure_path"], path.parent)
        lines.extend(
            [
                f"### {row['case_label']}",
                "",
                f"- Event: `{row['event_id']}` / basin `{row['gauge_id']}`.",
                f"- Selection rule: {row['selection_rule']}",
                f"- Seed-mean Model 1 under-deficit: {fmt_float(row['model1_deficit_mean'], 1)}%; q99 under-deficit: {fmt_float(row['q99_deficit_mean'], 1)}%.",
                f"- Seed-mean Model 1 predicted peak / ARI100: {fmt_float(row['model1_ari100_mean'])}; q99 predicted peak / ARI100: {fmt_float(row['q99_ari100_mean'])}.",
                f"- Figure: [{Path(rel_figure).as_posix()}]({Path(rel_figure).as_posix()})",
                "",
            ]
        )
    rel_cases = os.path.relpath(tables_dir / "primary_flow_graph_selected_cases.csv", path.parent)
    rel_seed = os.path.relpath(tables_dir / "primary_flow_graph_selected_seed_metrics.csv", path.parent)
    lines.extend(
        [
            "## Tables",
            "",
            f"- Selected case summary: `{Path(rel_cases).as_posix()}`",
            f"- Seed-level predictor metrics for the selected events: `{Path(rel_seed).as_posix()}`",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    output_dir: Path = args.output_dir
    figures_dir = output_dir / "figures"
    tables_dir = output_dir / "tables"
    metadata_dir = output_dir / "metadata"
    figures_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    seeds = sorted(set(args.seeds))
    cohort = read_cohort(args.cohort_csv)
    cohort = add_precip_references(cohort, args.return_period_csv)
    cohort = add_basin_metadata(cohort, args.basin_screening_csv, args.streamflow_quality_csv)
    long_df = read_stress_long(args.stress_long_csv, seeds)
    seed_wide = build_seed_event_wide(long_df)
    candidates = aggregate_event_candidates(seed_wide)
    selected_cases = select_cases(candidates, expected_seed_count=len(seeds))
    selected_cases = selected_cases.merge(
        cohort.drop_duplicates(["gauge_id", "event_id"]),
        on=["gauge_id", "event_id", "response_class", "rain_cohort"],
        how="left",
        validate="one_to_one",
        suffixes=("", "_cohort"),
    )

    selected_ids = selected_cases["event_id"].astype(str).tolist()
    selected_long = long_df[long_df["event_id"].isin(selected_ids)].copy()
    selected_long.to_csv(tables_dir / "primary_flow_graph_selected_seed_metrics.csv", index=False)
    selected_cases.to_csv(tables_dir / "primary_flow_graph_selected_cases.csv", index=False)

    all_series = {seed: read_required_series(args.series_dir, seed) for seed in seeds}
    manifest_rows = []
    for _, case in selected_cases.iterrows():
        event = case
        rain = read_rain_series(args.data_dir, str(event["gauge_id"]))
        filename = f"{case['case_key']}__{safe_slug(str(event['event_id']))}.png"
        figure_path = figures_dir / filename
        plot_case(
            case=case,
            event=event,
            all_series=all_series,
            rain=rain,
            selected_long=selected_long,
            seeds=seeds,
            output_path=figure_path,
            padding_hours=int(args.padding_hours),
        )
        manifest_rows.append(
            {
                "case_key": case["case_key"],
                "case_label": case["case_label"],
                "gauge_id": event["gauge_id"],
                "event_id": event["event_id"],
                "response_class": event["response_class"],
                "rain_cohort": event["rain_cohort"],
                "figure_path": str(figure_path),
            }
        )

    manifest = pd.DataFrame(manifest_rows)
    manifest.to_csv(metadata_dir / "primary_flow_graph_figure_manifest.csv", index=False)
    write_markdown_report(
        metadata_dir / "primary_flow_graph_diagnostic.md",
        selected_cases=selected_cases,
        manifest=manifest,
        tables_dir=tables_dir,
    )
    print(f"Wrote primary extreme-rain flow graph diagnostic: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
