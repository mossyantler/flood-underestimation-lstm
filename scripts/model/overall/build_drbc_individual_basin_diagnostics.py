#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=1.26",
#   "pandas>=2.2",
# ]
# ///
from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_CORRELATION_DIR = (
    REPO_ROOT
    / "output/model_analysis/legacy/overall_analysis/main_comparison/drbc_attribute_metric_correlations"
)
DEFAULT_MEDIAN_DEVIATION_DIR = (
    REPO_ROOT
    / "output/model_analysis/legacy/overall_analysis/main_comparison/attribute_correlations/median_deviation"
)
DEFAULT_EVENT_RESPONSE_SUMMARY = (
    REPO_ROOT / "output/basin/drbc/analysis/event_response/tables/event_response_basin_summary.csv"
)
DEFAULT_EVENT_RESPONSE_TABLE = (
    REPO_ROOT / "output/basin/drbc/analysis/event_response/tables/event_response_table.csv"
)
DEFAULT_STRESS_ERROR_TABLE = (
    REPO_ROOT
    / "output/model_analysis/legacy/extreme_rain/primary/analysis/extreme_rain_stress_error_table_wide.csv"
)
DEFAULT_STRESS_MANIFEST = (
    REPO_ROOT / "output/model_analysis/legacy/extreme_rain/primary/event_simq_plots/event_simq_plot_manifest.csv"
)
DEFAULT_USGS_NOTE_DIR = REPO_ROOT / "docs/references/basin/usgs_station_notes"
DEFAULT_BASIN_DISSECT_DIR = REPO_ROOT / "output/model_analysis/legacy/extreme_rain/primary/basin_dissect"
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "output/model_analysis/legacy/overall_analysis/main_comparison/individual_basin_diagnostics"
)

FEATURE_LABELS = {
    "area": "Area",
    "log10_area": "log10(area)",
    "snow_fraction": "Snow fraction",
    "seasonal": "Precipitation seasonality",
    "latitude": "Latitude",
    "elevation": "Elevation",
    "slope": "Slope",
    "human_use": "Developed fraction",
    "land_use": "Forest fraction",
    "permeability": "Permeability",
    "aridity": "Aridity",
    "baseflow_index": "Baseflow index",
    "high_prec_freq": "High-precip frequency",
    "soil_water_capacity": "Soil water capacity",
    "sand_frac": "Sand fraction",
    "clay_frac": "Clay fraction",
    "obs_cv": "Observed flow CV",
    "obs_fdc_slope": "Observed FDC slope",
    "obs_q99": "Observed Q99",
    "obs_mean_flow": "Observed mean flow",
}

CORE_FEATURES = [
    "area",
    "obs_mean_flow",
    "obs_q99",
    "obs_cv",
    "obs_fdc_slope",
    "slope",
    "snow_fraction",
    "human_use",
    "land_use",
    "permeability",
    "baseflow_index",
    "high_prec_freq",
    "aridity",
]

CORE_CORRELATION_METRICS = [
    "m1_NSE",
    "m1_KGE",
    "m1_FHV",
    "m1_Peak_MAPE",
    "m2_NSE",
    "m2_KGE",
    "m2_FHV",
    "m2_Peak_MAPE",
    "delta_NSE",
    "delta_KGE",
    "delta_FHV",
    "Peak_MAPE_reduction",
    "coverage_q99",
    "tail_hit_q99",
    "pinball_q99",
]

METRIC_LABELS = {
    "m1_NSE": "Model 1 NSE",
    "m1_KGE": "Model 1 KGE",
    "m1_FHV": "Model 1 FHV",
    "m1_Peak_Timing": "Model 1 Peak timing",
    "m1_Peak_MAPE": "Model 1 Peak MAPE",
    "m2_NSE": "Model 2 q50 NSE",
    "m2_KGE": "Model 2 q50 KGE",
    "m2_FHV": "Model 2 q50 FHV",
    "m2_Peak_Timing": "Model 2 q50 Peak timing",
    "m2_Peak_MAPE": "Model 2 q50 Peak MAPE",
    "delta_NSE": "Delta NSE",
    "delta_KGE": "Delta KGE",
    "delta_FHV": "Delta FHV",
    "Peak_Timing_reduction": "Peak timing reduction",
    "Peak_MAPE_reduction": "Peak MAPE reduction",
    "coverage_q99": "Coverage q99",
    "tail_hit_q99": "Tail hit q99",
    "pinball_q99": "Pinball q99",
}

TIER_LABELS = {
    "near_median_lt_0_5_iqr": "<0.5 IQR",
    "shoulder_0_5_to_1_5_iqr": "0.5-1.5 IQR",
    "far_1_5_to_3_iqr": "1.5-3 IQR",
    "extreme_ge_3_iqr": ">=3 IQR",
    "<0.5 IQR": "<0.5 IQR",
    "0.5-1.5 IQR": "0.5-1.5 IQR",
    "1.5-3 IQR": "1.5-3 IQR",
    ">=3 IQR": ">=3 IQR",
}

USGS_CATEGORY_KEYWORDS = {
    "regulated_storage": [
        "regulated",
        "regulation",
        "reservoir",
        "dam",
        "lake",
        "hydroelectric",
        "hydropower",
        "storage",
        "release",
        "control",
    ],
    "coastal_plain_storage": [
        "coastal plain",
        "wetland",
        "low-gradient",
        "low gradient",
        "storage-related",
        "tidal",
        "swamp",
    ],
    "urban_withdrawal_or_effluent": [
        "urban",
        "developed",
        "withdrawal",
        "npdes",
        "wastewater",
        "diversion",
        "canal",
        "water use",
    ],
    "rating_or_record_caveat": [
        "rating",
        "estimated",
        "poor",
        "fair",
        "missing record",
        "extended above",
        "ice",
    ],
    "snow_or_cold_season": [
        "snow",
        "winter",
        "cold",
        "ice",
        "rain-on-snow",
        "rain on snow",
    ],
}


@dataclass(frozen=True)
class TextArtifact:
    path: Path | None
    title: str
    text: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build per-basin DRBC diagnostic reports by joining basin attributes, "
            "performance metrics, metric-correlation context, USGS station notes, "
            "and existing extreme-rain basin_dissect reports."
        )
    )
    parser.add_argument("--correlation-dir", type=Path, default=DEFAULT_CORRELATION_DIR)
    parser.add_argument("--median-deviation-dir", type=Path, default=DEFAULT_MEDIAN_DEVIATION_DIR)
    parser.add_argument("--event-response-summary", type=Path, default=DEFAULT_EVENT_RESPONSE_SUMMARY)
    parser.add_argument("--event-response-table", type=Path, default=DEFAULT_EVENT_RESPONSE_TABLE)
    parser.add_argument("--stress-error-table", type=Path, default=DEFAULT_STRESS_ERROR_TABLE)
    parser.add_argument("--stress-manifest", type=Path, default=DEFAULT_STRESS_MANIFEST)
    parser.add_argument("--usgs-note-dir", type=Path, default=DEFAULT_USGS_NOTE_DIR)
    parser.add_argument("--basin-dissect-dir", type=Path, default=DEFAULT_BASIN_DISSECT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


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


def fmt(value: Any, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "NA"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(number):
        return "NA"
    return f"{number:.{digits}f}{suffix}"


def fmt_pct(value: Any, digits: int = 0) -> str:
    if value is None:
        return "NA"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "NA"
    if not math.isfinite(number):
        return "NA"
    return f"{number * 100:.{digits}f}%"


def rank_percentile(series: pd.Series) -> pd.Series:
    return series.rank(method="average", pct=True)


def percentile_label(pct: float) -> str:
    if not math.isfinite(pct):
        return "NA"
    if pct <= 0.15:
        return "하위권"
    if pct >= 0.85:
        return "상위권"
    if pct <= 0.35:
        return "중하위권"
    if pct >= 0.65:
        return "중상위권"
    return "중간권"


def read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required input: {path}")
    return pd.read_csv(path, **kwargs)


def load_feature_metric_table(correlation_dir: Path) -> pd.DataFrame:
    path = correlation_dir / "tables" / "basin_feature_metric_table.csv"
    frame = read_csv(path, dtype={"basin": str})
    frame["basin"] = frame["basin"].map(normalize_basin_id)
    return frame.set_index("basin", drop=False).sort_index()


def load_correlations(correlation_dir: Path) -> pd.DataFrame:
    path = correlation_dir / "tables" / "spearman_correlations.csv"
    return read_csv(path)


def load_median_deviation(median_deviation_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    basin_path = median_deviation_dir / "tables" / "metric_median_deviation_basin_tier_profile.csv"
    model_path = median_deviation_dir / "tables" / "metric_median_deviation_basin_model_tier_profile.csv"
    basin = read_csv(basin_path, dtype={"basin": str})
    model = read_csv(model_path, dtype={"basin": str})
    basin["basin"] = basin["basin"].map(normalize_basin_id)
    model["basin"] = model["basin"].map(normalize_basin_id)
    return basin.set_index("basin", drop=False).sort_index(), model


def load_median_deviation_detail(median_deviation_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_path = median_deviation_dir / "tables" / "metric_median_deviation_basin_summary.csv"
    cause_path = median_deviation_dir / "tables" / "metric_median_deviation_far_flow_response_check.csv"
    summary = read_csv(summary_path, dtype={"basin": str, "gauge_id": str})
    cause = read_csv(cause_path, dtype={"basin": str})
    summary["basin"] = summary["basin"].map(normalize_basin_id)
    summary["gauge_id"] = summary["gauge_id"].map(normalize_basin_id)
    cause["basin"] = cause["basin"].map(normalize_basin_id)
    return summary.set_index("basin", drop=False).sort_index(), cause.set_index("basin", drop=False).sort_index()


def load_event_response(summary_path: Path, table_path: Path) -> pd.DataFrame:
    summary = read_csv(summary_path, dtype={"gauge_id": str})
    summary["basin"] = summary["gauge_id"].map(normalize_basin_id)
    summary = summary.set_index("basin", drop=False)

    events = read_csv(table_path, dtype={"gauge_id": str})
    events["basin"] = events["gauge_id"].map(normalize_basin_id)
    events["cold_season_bool"] = events["cold_season_flag"].astype(str).str.lower().isin(["true", "1"])
    grouped = (
        events.groupby("basin", dropna=False)
        .agg(
            event_response_rows=("event_id", "size"),
            cold_season_event_fraction=("cold_season_bool", "mean"),
            median_recent_rain_24h=("recent_rain_24h", "median"),
            median_recent_rain_72h=("recent_rain_72h", "median"),
            median_antecedent_rain_7d=("antecedent_rain_7d", "median"),
            median_rising_time_hours=("rising_time_hours", "median"),
            median_event_duration_hours=("event_duration_hours", "median"),
        )
        .reset_index()
        .set_index("basin", drop=False)
    )
    return summary.join(grouped.drop(columns=["basin"]), how="left", rsuffix="_event")


def load_manifest(manifest_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    manifest = read_csv(manifest_path, dtype={"gauge_id": str})
    manifest["basin"] = manifest["gauge_id"].map(normalize_basin_id)
    first_cols = [
        "basin",
        "gauge_name",
        "state",
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
        "MAJ_NDAMS_2009",
        "STOR_NOR_2009",
        "DDENS_2009",
        "CANALS_PCT",
        "NPDES_MAJ_DENS",
        "POWER_NUM_PTS",
        "FRESHW_WITHDRAWAL",
    ]
    first = manifest[[col for col in first_cols if col in manifest.columns]].drop_duplicates("basin")
    class_counts = (
        manifest.pivot_table(index="basin", columns="response_class", values="event_id", aggfunc="count", fill_value=0)
        .reset_index()
    )
    class_counts.columns = [str(col) for col in class_counts.columns]
    return first.set_index("basin", drop=False).sort_index(), class_counts.set_index("basin", drop=False)


def load_stress_aggregate(stress_path: Path) -> pd.DataFrame:
    stress_raw = read_csv(stress_path, dtype={"gauge_id": str})
    basin_col = stress_raw["gauge_id"].map(normalize_basin_id)
    stress = pd.concat([pd.DataFrame({"basin": basin_col}), stress_raw.copy()], axis=1)
    rows: list[dict[str, Any]] = []
    for basin, group in stress.groupby("basin", sort=True):
        rec: dict[str, Any] = {
            "basin": basin,
            "stress_seed_event_records": int(len(group)),
            "stress_event_count": int(group["event_id"].nunique()),
        }
        for predictor in ["model1", "q50", "q95", "q99"]:
            for metric, func in [
                (f"{predictor}_obs_peak_rel_error_pct", "median"),
                (f"{predictor}_window_peak_rel_error_pct", "median"),
                (f"{predictor}_obs_peak_underestimated", "mean"),
                (f"{predictor}_obs_peak_under_deficit_pct", "median"),
                (f"{predictor}_abs_peak_timing_error_hours", "median"),
                (f"{predictor}_top_flow_hit_rate", "median"),
            ]:
                if metric not in group.columns:
                    continue
                values = pd.to_numeric(group[metric], errors="coerce")
                rec[metric] = float(values.mean()) if func == "mean" else float(values.median())
        rows.append(rec)
    return pd.DataFrame(rows).set_index("basin", drop=False)


def load_stress_event_examples(stress_path: Path) -> dict[str, pd.DataFrame]:
    stress_raw = read_csv(stress_path, dtype={"gauge_id": str})
    basin_col = stress_raw["gauge_id"].map(normalize_basin_id)
    stress = pd.concat([pd.DataFrame({"basin": basin_col}), stress_raw.copy()], axis=1)

    event_cols = [
        "event_id",
        "rain_cohort",
        "response_class",
        "wet_cluster_total_rain",
        "wet_cluster_peak_rainf",
        "observed_response_peak",
        "streamflow_q99_threshold",
        "obs_peak_to_flood_ari2",
        "obs_peak_to_flood_ari25",
        "response_lag_from_rain_peak_h",
        "max_prec_ari100_ratio",
        "return_period_confidence_flag",
    ]
    metric_cols = [
        "model1_window_peak_rel_error_pct",
        "q50_window_peak_rel_error_pct",
        "q95_window_peak_rel_error_pct",
        "q99_window_peak_rel_error_pct",
        "model1_obs_peak_underestimated",
        "q50_obs_peak_underestimated",
        "q99_obs_peak_underestimated",
        "q99_top_flow_hit_rate",
        "model2_obs_peak_quantile_bracket",
    ]

    examples: dict[str, pd.DataFrame] = {}
    class_priority = {
        "flood_response_ge25": 0,
        "flood_response_ge2_to_lt25": 1,
        "high_flow_non_flood_q99_only": 2,
        "low_response_below_q99": 3,
    }
    for basin, basin_group in stress.groupby("basin", sort=True):
        rows = []
        for event_id, group in basin_group.groupby("event_id", sort=False):
            first = group.iloc[0]
            rec: dict[str, Any] = {"event_id": event_id}
            for col in event_cols:
                if col in group.columns:
                    rec[col] = first[col]
            for col in metric_cols:
                if col not in group.columns:
                    continue
                if col == "model2_obs_peak_quantile_bracket":
                    mode = group[col].dropna().astype(str).mode()
                    rec[col] = mode.iloc[0] if not mode.empty else ""
                elif col.endswith("_underestimated"):
                    rec[col] = float(pd.to_numeric(group[col], errors="coerce").mean())
                else:
                    rec[col] = float(pd.to_numeric(group[col], errors="coerce").median())
            rows.append(rec)
        frame = pd.DataFrame(rows)
        if frame.empty:
            examples[basin] = frame
            continue
        frame["response_priority"] = frame["response_class"].map(class_priority).fillna(9)
        frame["abs_q50_window_peak_error"] = pd.to_numeric(
            frame.get("q50_window_peak_rel_error_pct"), errors="coerce"
        ).abs()
        frame["abs_model1_window_peak_error"] = pd.to_numeric(
            frame.get("model1_window_peak_rel_error_pct"), errors="coerce"
        ).abs()
        frame = frame.sort_values(
            ["response_priority", "abs_q50_window_peak_error", "abs_model1_window_peak_error"],
            ascending=[True, False, False],
        ).head(5)
        examples[basin] = frame.reset_index(drop=True)
    return examples


def find_note(note_dir: Path, basin: str) -> TextArtifact:
    matches = sorted(note_dir.glob(f"{basin}_*.md"))
    if not matches:
        return TextArtifact(None, "", "")
    path = matches[0]
    text = path.read_text(encoding="utf-8")
    title = next((line.strip("# ").strip() for line in text.splitlines() if line.startswith("# ")), basin)
    return TextArtifact(path, title, text)


def find_basin_dissect(dissect_dir: Path, basin: str) -> TextArtifact:
    matches = sorted(path for path in dissect_dir.glob(f"**/{basin}.md") if path.is_file())
    if not matches:
        return TextArtifact(None, "", "")
    path = matches[0]
    text = path.read_text(encoding="utf-8")
    title = next((line.strip("# ").strip() for line in text.splitlines() if line.startswith("# ")), basin)
    return TextArtifact(path, title, text)


def extract_section(text: str, heading: str) -> str:
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.IGNORECASE | re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    start = match.end()
    next_heading = re.search(r"^##\s+", text[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end].strip()


def first_paragraph(text: str, max_chars: int = 620) -> str:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return ""
    paragraph = paragraphs[0].replace("\n", " ")
    if len(paragraph) <= max_chars:
        return paragraph
    return paragraph[: max_chars - 3].rstrip() + "..."


def detect_usgs_categories(text: str) -> list[str]:
    lowered = text.lower()
    categories = []
    for category, keywords in USGS_CATEGORY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            categories.append(category)
    return categories


def category_labels(categories: list[str]) -> str:
    labels = {
        "regulated_storage": "regulation/storage",
        "coastal_plain_storage": "coastal plain/wetland/storage",
        "urban_withdrawal_or_effluent": "urban/withdrawal/effluent",
        "rating_or_record_caveat": "rating/record caveat",
        "snow_or_cold_season": "snow/cold-season",
    }
    return ", ".join(labels.get(cat, cat) for cat in categories) if categories else "none detected"


def booleanish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "y"}


def metric_error_mode(row: pd.Series) -> str:
    m1_fhv = float(row.get("m1_FHV", np.nan))
    m2_fhv = float(row.get("m2_FHV", np.nan))
    m1_peak = float(row.get("m1_Peak_MAPE", np.nan))
    m2_peak = float(row.get("m2_Peak_MAPE", np.nan))
    parts = []
    for label, fhv in [("M1", m1_fhv), ("M2 q50", m2_fhv)]:
        if not math.isfinite(fhv):
            continue
        if fhv >= 20:
            parts.append(f"{label} high-flow volume 과대(+FHV)")
        elif fhv <= -20:
            parts.append(f"{label} high-flow volume 과소(-FHV)")
        else:
            parts.append(f"{label} FHV near-zero/moderate")
    if math.isfinite(m1_peak) and math.isfinite(m2_peak):
        if m2_peak < m1_peak:
            parts.append("q50 peak error는 M2에서 감소")
        elif m2_peak > m1_peak:
            parts.append("q50 peak error는 M2에서 증가")
    return "; ".join(parts)


def stress_error_mode(stress_row: pd.Series | None) -> str:
    if stress_row is None or stress_row.empty:
        return "stress table 없음"
    m1_rel = float(stress_row.get("model1_window_peak_rel_error_pct", np.nan))
    q50_rel = float(stress_row.get("q50_window_peak_rel_error_pct", np.nan))
    q99_rel = float(stress_row.get("q99_window_peak_rel_error_pct", np.nan))
    m1_under = float(stress_row.get("model1_obs_peak_underestimated", np.nan))
    q50_under = float(stress_row.get("q50_obs_peak_underestimated", np.nan))
    q99_under = float(stress_row.get("q99_obs_peak_underestimated", np.nan))
    pieces = []
    if math.isfinite(m1_rel):
        if m1_rel > 20:
            pieces.append(f"M1 event-window peak 과대 경향({fmt(m1_rel, 1, '%')})")
        elif m1_rel < -20:
            pieces.append(f"M1 event-window peak 과소 경향({fmt(m1_rel, 1, '%')})")
        else:
            pieces.append(f"M1 event-window peak near-balanced({fmt(m1_rel, 1, '%')})")
    if math.isfinite(q50_rel):
        if q50_rel > 20:
            pieces.append(f"q50 과대({fmt(q50_rel, 1, '%')})")
        elif q50_rel < -20:
            pieces.append(f"q50 과소({fmt(q50_rel, 1, '%')})")
        else:
            pieces.append(f"q50 near-balanced({fmt(q50_rel, 1, '%')})")
    if math.isfinite(q99_rel):
        if q99_rel > 20:
            pieces.append(f"q99 upper-tail은 over-bracketing 가능({fmt(q99_rel, 1, '%')})")
        elif q99_rel < -20:
            pieces.append(f"q99도 과소({fmt(q99_rel, 1, '%')})")
        else:
            pieces.append(f"q99 near-balanced({fmt(q99_rel, 1, '%')})")
    if math.isfinite(m1_under) and math.isfinite(q50_under) and math.isfinite(q99_under):
        pieces.append(
            "obs-peak underestimation fraction "
            f"M1/q50/q99={fmt_pct(m1_under)}/{fmt_pct(q50_under)}/{fmt_pct(q99_under)}"
        )
    return "; ".join(pieces)


def select_notable_features(table: pd.DataFrame, basin: str) -> pd.DataFrame:
    rows = []
    for feature in CORE_FEATURES:
        if feature not in table.columns:
            continue
        values = pd.to_numeric(table[feature], errors="coerce")
        pct = rank_percentile(values).loc[basin]
        value = values.loc[basin]
        if not math.isfinite(float(value)):
            continue
        extremeness = abs(float(pct) - 0.5)
        rows.append(
            {
                "feature": feature,
                "label": FEATURE_LABELS.get(feature, feature),
                "value": value,
                "percentile": pct,
                "percentile_label": percentile_label(float(pct)),
                "extremeness": extremeness,
            }
        )
    out = pd.DataFrame(rows).sort_values("extremeness", ascending=False)
    return out.head(8).reset_index(drop=True)


def select_correlation_context(
    corr: pd.DataFrame, notable_features: pd.DataFrame, min_abs_rho: float = 0.35
) -> pd.DataFrame:
    features = set(notable_features["feature"].tolist())
    work = corr[
        corr["feature"].isin(features)
        & corr["metric"].isin(CORE_CORRELATION_METRICS)
        & corr["rho"].notna()
        & (corr["abs_rho"] >= min_abs_rho)
    ].copy()
    if work.empty:
        return work
    work = work.sort_values(["significant", "abs_rho"], ascending=[False, False])
    keep = ["feature", "metric", "rho", "pval_bh", "significant", "abs_rho"]
    return work[keep].head(10).reset_index(drop=True)


def markdown_table(frame: pd.DataFrame, columns: list[str], labels: dict[str, str] | None = None) -> list[str]:
    labels = labels or {}
    if frame.empty:
        return ["_표시할 행이 없습니다._"]
    header = [labels.get(col, col) for col in columns]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in frame.iterrows():
        vals = []
        for col in columns:
            value = row.get(col, "")
            if isinstance(value, float):
                if "percentile" in col:
                    vals.append(fmt_pct(value))
                elif col in {"rho", "pval_bh", "abs_rho"}:
                    vals.append(fmt(value, 3))
                else:
                    vals.append(fmt(value, 3))
            else:
                vals.append(str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return lines


def driver_diagnosis(
    feature_row: pd.Series,
    tier_row: pd.Series,
    cause_row: pd.Series | None,
    event_row: pd.Series | None,
    manifest_row: pd.Series | None,
    stress_row: pd.Series | None,
    usgs_categories: list[str],
    usgs_text: str,
) -> tuple[str, str, str]:
    area = float(feature_row.get("area", np.nan))
    obs_q99 = float(feature_row.get("obs_q99", np.nan))
    obs_mean = float(feature_row.get("obs_mean_flow", np.nan))
    obs_cv = float(feature_row.get("obs_cv", np.nan))
    tier = str(tier_row.get("dominant_distance_label", ""))
    hydromod = bool(manifest_row is not None and booleanish(manifest_row.get("hydromod_risk", False)))
    lowered_note = usgs_text.lower()
    weak_regulation_note = any(
        phrase in lowered_note
        for phrase in [
            "do not diagnose high-flow reservoir suppression",
            "not the same as documented high-flow flood control",
            "low/medium-flow regulation caveat",
            "low and medium flow",
            "low/medium flow",
            "isregulated = false",
        ]
    )
    regulated = "regulated_storage" in usgs_categories and not weak_regulation_note
    regulation_caveat = "regulated_storage" in usgs_categories and weak_regulation_note
    coastal_storage = "coastal_plain_storage" in usgs_categories
    urban = "urban_withdrawal_or_effluent" in usgs_categories
    rating_caveat = "rating_or_record_caveat" in usgs_categories
    snow = "snow_or_cold_season" in usgs_categories

    m1_rel = float(stress_row.get("model1_window_peak_rel_error_pct", np.nan)) if stress_row is not None else np.nan
    q50_rel = float(stress_row.get("q50_window_peak_rel_error_pct", np.nan)) if stress_row is not None else np.nan
    q99_rel = float(stress_row.get("q99_window_peak_rel_error_pct", np.nan)) if stress_row is not None else np.nan
    far_share = float(tier_row.get("far_or_extreme_share", np.nan))

    small_scale = math.isfinite(area) and area < 50
    low_flow_scale = (
        (math.isfinite(obs_q99) and obs_q99 < 5)
        or (math.isfinite(obs_mean) and obs_mean < 1.5)
    )
    flashy = math.isfinite(obs_cv) and obs_cv > 1.4
    stable_outlier = math.isfinite(far_share) and far_share >= 0.75
    over_events = math.isfinite(m1_rel) and m1_rel > 20 and (not math.isfinite(q50_rel) or q50_rel > 10)
    under_events = math.isfinite(m1_rel) and m1_rel < -20
    q99_over = math.isfinite(q99_rel) and q99_rel > 40

    candidates: list[str] = []
    if cause_row is not None and not cause_row.empty:
        cause_group = str(cause_row.get("cause_group", ""))
        primary_cause = str(cause_row.get("primary_cause", ""))
        interpretation_note = str(cause_row.get("interpretation_note", ""))
        if cause_group.startswith("A.") and (small_scale or low_flow_scale):
            candidates.append(
                f"기존 far-cause 진단은 `{primary_cause}`로, 작은 면적/낮은 관측 유량 scale 때문에 metric denominator가 증폭되는 case로 분류합니다."
            )
            if interpretation_note:
                candidates.append(interpretation_note)
        elif cause_group.startswith("B."):
            candidates.append(
                f"기존 far-cause 진단은 `{primary_cause}`로, 빠르거나 짧은 event-response가 timing/high-flow-volume error를 키우는 case로 분류합니다."
            )
            if interpretation_note:
                candidates.append(interpretation_note)
        elif cause_group.startswith("C."):
            candidates.append(
                f"기존 far-cause 진단은 `{primary_cause}`로, 단일 공유 원인보다 metric-specific sensitivity로 낮춰 해석합니다."
            )

    if regulated and over_events:
        candidates.append("USGS regulation/storage와 event-scale obs<sim overprediction이 함께 보여, 조절/저류에 의한 peak attenuation 후보가 가장 강합니다.")
    elif regulated and under_events:
        candidates.append("USGS regulation/storage가 있고 M1은 stress event에서 과소입니다. 단순 attenuation보다 release/timing 또는 recession mass를 놓친 case로 보는 편이 안전합니다.")
    elif regulated or hydromod:
        candidates.append("USGS/local hydromod evidence가 있어 자연유역 학습 모델과 station outlet 조건의 불일치가 핵심 후보입니다.")
    elif regulation_caveat:
        candidates.append("USGS note에는 regulation/storage 단서가 있지만 high-flow flood-control 근거는 약하므로, 이를 주원인보다 보조 caveat로 둡니다.")

    if small_scale and low_flow_scale and stable_outlier:
        candidates.append("면적과 관측 유량 scale이 작고 median-distance outlier가 안정적이라, 작은 절대 오차가 NSE/KGE/FHV에서 크게 증폭되는 metric-scale 효과가 큽니다.")
    elif small_scale and low_flow_scale:
        candidates.append("작은 basin/낮은 Q99 조건 때문에 normalized metric과 peak percent error가 민감하게 흔들릴 수 있습니다.")

    if coastal_storage:
        candidates.append("USGS note의 coastal plain/wetland/storage 맥락은 낮은 기울기와 긴 저류/완만한 recession을 설명하는 보조 근거입니다.")
    if urban:
        candidates.append("urban, withdrawal, effluent, canal 계열 근거가 있어 forcing-response 관계가 자연유역 평균 패턴과 달라질 수 있습니다.")
    if snow:
        candidates.append("snow/cold-season 단서가 있어 겨울 event timing과 rain-on-snow 가능성은 별도 caveat로 남겨야 합니다.")
    if rating_caveat:
        candidates.append("USGS note의 rating/record caveat는 일부 peak magnitude 해석의 불확실성을 키웁니다.")
    if flashy and not candidates:
        candidates.append("flow CV가 높아 빠른 event shape/timing error가 성능 저하를 키운 후보입니다.")
    if q99_over and not over_events:
        candidates.append("q99 upper quantile은 flood underestimation을 줄일 수 있지만 이 basin에서는 event-window 과대 bracketing tradeoff가 큽니다.")

    if not candidates:
        if tier in {"<0.5 IQR", "near_median_lt_0_5_iqr"}:
            candidates.append("median-distance 기준으로는 문제 basin이 아니며, USGS note는 해석 caveat로 쓰는 것이 맞습니다.")
        else:
            candidates.append("단일 강한 driver보다 metric별/seed별 혼합 신호가 커서 basin-specific caveat 중심으로 해석해야 합니다.")

    if regulated and (hydromod or over_events or under_events):
        confidence = "high" if stable_outlier or over_events or under_events else "medium-high"
    elif stable_outlier and (small_scale or low_flow_scale or coastal_storage):
        confidence = "medium-high"
    elif len(candidates) >= 2:
        confidence = "medium"
    else:
        confidence = "low-medium"

    if regulated and over_events:
        primary = "USGS regulation/storage와 event-scale obs<sim overprediction이 함께 보여, 조절/저류에 의한 peak attenuation 후보가 가장 강합니다."
    else:
        primary = candidates[0]
    explanation = " ".join(candidates)
    return primary, explanation, confidence


def write_basin_report(
    basin: str,
    output_path: Path,
    feature_row: pd.Series,
    tier_row: pd.Series,
    detail_row: pd.Series | None,
    cause_row: pd.Series | None,
    model_tiers: pd.DataFrame,
    event_row: pd.Series | None,
    manifest_row: pd.Series | None,
    stress_row: pd.Series | None,
    stress_examples: pd.DataFrame,
    notable_features: pd.DataFrame,
    corr_context: pd.DataFrame,
    note: TextArtifact,
    dissect: TextArtifact,
    usgs_categories: list[str],
    primary_driver: str,
    driver_explanation: str,
    confidence: str,
) -> None:
    gauge_name = str(tier_row.get("gauge_name") or feature_row.get("gauge_name") or "")
    state = str(tier_row.get("state") or (manifest_row.get("state") if manifest_row is not None else ""))
    tier_label = TIER_LABELS.get(str(tier_row.get("dominant_distance_label", "")), str(tier_row.get("dominant_distance_label", "")))

    model_rows = []
    for _, row in model_tiers[model_tiers["basin"] == basin].iterrows():
        model_rows.append(
            {
                "model": row.get("model_label", row.get("model", "")),
                "tier": TIER_LABELS.get(str(row.get("dominant_distance_label", "")), str(row.get("dominant_distance_label", ""))),
                "near": int(row.get("near_median_lt_0_5_iqr", 0)),
                "shoulder": int(row.get("shoulder_0_5_to_1_5_iqr", 0)),
                "far": int(row.get("far_1_5_to_3_iqr", 0)),
                "extreme": int(row.get("extreme_ge_3_iqr", 0)),
                "mean_distance": row.get("mean_distance_any_metric_seed", np.nan),
                "max_distance": row.get("max_distance_any_metric_seed", np.nan),
            }
        )
    model_tier_table = pd.DataFrame(model_rows)

    perf_rows = pd.DataFrame(
        [
            {"metric": "NSE", "Model 1": feature_row.get("m1_NSE"), "Model 2 q50": feature_row.get("m2_NSE"), "M2-M1": feature_row.get("delta_NSE")},
            {"metric": "KGE", "Model 1": feature_row.get("m1_KGE"), "Model 2 q50": feature_row.get("m2_KGE"), "M2-M1": feature_row.get("delta_KGE")},
            {"metric": "FHV (%)", "Model 1": feature_row.get("m1_FHV"), "Model 2 q50": feature_row.get("m2_FHV"), "M2-M1": feature_row.get("delta_FHV")},
            {
                "metric": "Peak timing (h)",
                "Model 1": feature_row.get("m1_Peak_Timing"),
                "Model 2 q50": feature_row.get("m2_Peak_Timing"),
                "M2-M1": feature_row.get("Peak_Timing_reduction"),
            },
            {
                "metric": "Peak MAPE (%)",
                "Model 1": feature_row.get("m1_Peak_MAPE"),
                "Model 2 q50": feature_row.get("m2_Peak_MAPE"),
                "M2-M1": feature_row.get("Peak_MAPE_reduction"),
            },
        ]
    )

    prob_rows = pd.DataFrame(
        [
            {"metric": "pinball q50/q90/q95/q99", "value": f"{fmt(feature_row.get('pinball_q50'))} / {fmt(feature_row.get('pinball_q90'))} / {fmt(feature_row.get('pinball_q95'))} / {fmt(feature_row.get('pinball_q99'))}"},
            {"metric": "coverage q50/q90/q95/q99", "value": f"{fmt_pct(feature_row.get('coverage_q50'))} / {fmt_pct(feature_row.get('coverage_q90'))} / {fmt_pct(feature_row.get('coverage_q95'))} / {fmt_pct(feature_row.get('coverage_q99'))}"},
            {"metric": "Q99 tail hit", "value": fmt_pct(feature_row.get("tail_hit_q99"))},
        ]
    )

    stress_rows = []
    if stress_row is not None and not stress_row.empty:
        for predictor, label in [("model1", "Model 1"), ("q50", "Model 2 q50"), ("q95", "Model 2 q95"), ("q99", "Model 2 q99")]:
            stress_rows.append(
                {
                    "predictor": label,
                    "obs_peak_under_frac": stress_row.get(f"{predictor}_obs_peak_underestimated", np.nan),
                    "obs_peak_rel_error_pct": stress_row.get(f"{predictor}_obs_peak_rel_error_pct", np.nan),
                    "window_peak_rel_error_pct": stress_row.get(f"{predictor}_window_peak_rel_error_pct", np.nan),
                    "abs_timing_h": stress_row.get(f"{predictor}_abs_peak_timing_error_hours", np.nan),
                    "top_flow_hit": stress_row.get(f"{predictor}_top_flow_hit_rate", np.nan),
                }
            )
    stress_table = pd.DataFrame(stress_rows)

    if detail_row is not None and not detail_row.empty:
        metric_pattern_rows = pd.DataFrame(
            [
                {
                    "metric": "NSE",
                    "far": detail_row.get("NSE_far_records", np.nan),
                    "extreme": detail_row.get("NSE_extreme_records", np.nan),
                    "low": detail_row.get("NSE_low_side_records", np.nan),
                    "high": detail_row.get("NSE_high_side_records", np.nan),
                    "m1_seed_median": detail_row.get("NSE_model1_seed_median", np.nan),
                    "m2_seed_median": detail_row.get("NSE_model2_seed_median", np.nan),
                    "delta": detail_row.get("NSE_delta_seed_median", np.nan),
                },
                {
                    "metric": "KGE",
                    "far": detail_row.get("KGE_far_records", np.nan),
                    "extreme": detail_row.get("KGE_extreme_records", np.nan),
                    "low": detail_row.get("KGE_low_side_records", np.nan),
                    "high": detail_row.get("KGE_high_side_records", np.nan),
                    "m1_seed_median": detail_row.get("KGE_model1_seed_median", np.nan),
                    "m2_seed_median": detail_row.get("KGE_model2_seed_median", np.nan),
                    "delta": detail_row.get("KGE_delta_seed_median", np.nan),
                },
                {
                    "metric": "FHV",
                    "far": detail_row.get("FHV_far_records", np.nan),
                    "extreme": detail_row.get("FHV_extreme_records", np.nan),
                    "low": detail_row.get("FHV_low_side_records", np.nan),
                    "high": detail_row.get("FHV_high_side_records", np.nan),
                    "m1_seed_median": detail_row.get("FHV_model1_seed_median", np.nan),
                    "m2_seed_median": detail_row.get("FHV_model2_seed_median", np.nan),
                    "delta": detail_row.get("FHV_delta_seed_median", np.nan),
                },
            ]
        )
    else:
        metric_pattern_rows = pd.DataFrame()

    cause_lines: list[str] = []
    if cause_row is not None and not cause_row.empty:
        cause_lines = [
            f"- Existing cause group: `{cause_row.get('cause_group', '')}`",
            f"- Primary cause label: `{cause_row.get('primary_cause', '')}`",
            f"- Flow-response type: `{cause_row.get('flow_response_type_ko', cause_row.get('flow_response_type', ''))}`",
            f"- Event-response support: `{cause_row.get('event_response_support_ko', cause_row.get('event_response_support', ''))}`",
            f"- Evidence note: {cause_row.get('event_response_evidence_ko', cause_row.get('event_response_evidence', ''))}",
            f"- Interpretation note: {cause_row.get('interpretation_note', '')}",
            f"- Model effect: `{cause_row.get('model_effect', '')}`, Model2 far-record delta `{fmt(cause_row.get('model2_far_record_delta'), 1)}`, mean-distance delta `{fmt(cause_row.get('model2_mean_distance_delta'), 2)}`.",
        ]
    else:
        cause_lines = [
            "이 basin은 기존 far-cause diagnosis table에 포함되지 않았습니다. 즉 median-distance 기준으로는 far basin 13개 안에 들지 않거나, 특정 원인 label을 붙일 만큼 반복적인 outlier pattern이 강하지 않습니다."
        ]

    event_bits = []
    if event_row is not None and not event_row.empty:
        event_bits.append(f"Q99 event frequency {fmt(event_row.get('q99_event_frequency'), 2)}/yr")
        event_bits.append(f"RBI {fmt(event_row.get('rbi'), 3)}")
        event_bits.append(f"median rising time {fmt(event_row.get('rising_time_median_hours'), 1)} h")
        event_bits.append(f"median event duration {fmt(event_row.get('event_duration_median_hours'), 1)} h")

    manifest_bits = []
    if manifest_row is not None and not manifest_row.empty:
        manifest_bits.append(f"hydromod_risk={manifest_row.get('hydromod_risk')}")
        manifest_bits.append(f"forest={fmt(manifest_row.get('forest_pct'), 1, '%')}")
        manifest_bits.append(f"developed={fmt(manifest_row.get('developed_pct'), 1, '%')}")
        manifest_bits.append(f"wetland={fmt(manifest_row.get('wetland_pct'), 1, '%')}")
        if pd.notna(manifest_row.get("screening_notes", np.nan)):
            manifest_bits.append(f"screening_notes={manifest_row.get('screening_notes')}")

    usgs_summary = extract_section(note.text, "Diagnosis implication")
    if not usgs_summary:
        usgs_summary = extract_section(note.text, "Station facts")
    if not usgs_summary and "Use in basin diagnosis:" in note.text:
        usgs_summary = note.text.split("Use in basin diagnosis:", 1)[1].strip()
    usgs_summary = first_paragraph(usgs_summary or note.text)

    final_diagnosis = extract_section(dissect.text, "Final diagnosis")
    hydrograph_interpretation = extract_section(dissect.text, "Hydrograph interpretation")

    lines = [
        f"# {basin} - {gauge_name}",
        "",
        f"한 줄 진단: {primary_driver}",
        "",
        f"신뢰도는 `{confidence}`로 두었습니다. 이유는 {driver_explanation}",
        "",
        "## 1. 성능 지표와 과소/과대추정 방향",
        "",
        f"Median-distance tier는 `{tier_label}`입니다. 18개 record(NSE/KGE/FHV x Model 1/2 x seed 111/222/444) 중 far-or-extreme share는 `{fmt(tier_row.get('far_or_extreme_share'), 2)}`이고, 평균/최대 median-distance는 `{fmt(tier_row.get('mean_distance_any_metric_seed'), 2)} / {fmt(tier_row.get('max_distance_any_metric_seed'), 2)} IQR`입니다.",
        "",
        *markdown_table(perf_rows, ["metric", "Model 1", "Model 2 q50", "M2-M1"]),
        "",
        "FHV는 `(sim - obs) / obs` 기반 high-flow volume bias라서 양수는 high-flow volume 과대, 음수는 과소로 읽습니다. NSE/KGE는 높을수록 좋고, Peak timing과 Peak MAPE는 낮을수록 좋습니다. `Peak_Timing_reduction`과 `Peak_MAPE_reduction`은 양수일수록 Model 2 q50이 Model 1보다 줄인 값입니다.",
        "",
        f"요약하면 {metric_error_mode(feature_row)}.",
        "",
        "Metric별 median-distance 반복성은 아래처럼 확인됩니다. `far/extreme`은 6개 record(metric x Model 1/2 x seed 3 중 해당 metric 기준) 안에서의 반복 횟수이고, `low/high`는 각 metric box median 대비 어느 쪽으로 벗어났는지를 뜻합니다.",
        "",
        *markdown_table(
            metric_pattern_rows,
            ["metric", "far", "extreme", "low", "high", "m1_seed_median", "m2_seed_median", "delta"],
            {
                "metric": "Metric",
                "far": "Far",
                "extreme": "Extreme",
                "low": "Low side",
                "high": "High side",
                "m1_seed_median": "M1 seed median",
                "m2_seed_median": "M2 seed median",
                "delta": "M2-M1",
            },
        ),
        "",
        "확률론적 head는 아래처럼 보입니다.",
        "",
        *markdown_table(prob_rows, ["metric", "value"], {"metric": "지표", "value": "값"}),
        "",
        "## 2. 유역/streamflow 특성",
        "",
        f"핵심 event-response 요약은 {', '.join(event_bits) if event_bits else '입력 요약 없음'}입니다. Local manifest/attribute 쪽에서는 {', '.join(manifest_bits) if manifest_bits else '추가 hydromod manifest 없음'}입니다.",
        "",
        *markdown_table(
            notable_features.assign(
                value=notable_features["value"].map(lambda value: fmt(value, 3)),
                percentile=notable_features["percentile"].map(lambda value: fmt_pct(value)),
            ),
            ["label", "value", "percentile", "percentile_label"],
            {"label": "특성", "value": "값", "percentile": "DRBC 내 분위", "percentile_label": "해석"},
        ),
        "",
        "## 3. 전체 상관관계 안에서 이 basin을 읽는 법",
        "",
        "아래 표는 이 basin에서 상대적으로 극단적인 특성과, 전체 38개 basin Spearman 분석에서 그 특성이 성능지표와 연결된 쌍만 추린 것입니다. 상관은 원인 증명이 아니라, 이 basin의 개별 해석을 어디까지 일반 패턴과 맞춰 읽을 수 있는지 확인하는 용도입니다.",
        "",
        *markdown_table(
            corr_context.assign(
                feature=corr_context["feature"].map(lambda x: FEATURE_LABELS.get(x, x)) if not corr_context.empty else corr_context.get("feature", pd.Series(dtype=str)),
                metric=corr_context["metric"].map(lambda x: METRIC_LABELS.get(x, x)) if not corr_context.empty else corr_context.get("metric", pd.Series(dtype=str)),
                significant=corr_context["significant"].map(lambda x: "yes" if bool(x) else "no") if not corr_context.empty else corr_context.get("significant", pd.Series(dtype=str)),
            ),
            ["feature", "metric", "rho", "pval_bh", "significant"],
            {"feature": "특성", "metric": "지표", "rho": "rho", "pval_bh": "BH p", "significant": "유의"},
        ),
        "",
        "기존 median-deviation far-cause table과 비교하면 다음과 같습니다.",
        "",
        *cause_lines,
        "",
        "## 4. USGS station note와 비교",
        "",
        f"- USGS note: `{rel(note.path) or 'missing'}`",
        f"- 감지된 station-context category: {category_labels(usgs_categories)}",
        f"- 기존 basin_dissect report: `{rel(dissect.path) or 'missing'}`",
        "",
        f"USGS note 핵심 문맥: {usgs_summary}",
        "",
        "상관관계만 보면 basin scale, observed-flow scale, slope, snow, developed/forest fraction 같은 순위 신호를 말할 수 있습니다. USGS note는 여기에 station-specific 조건을 붙입니다. regulation/storage가 명시된 경우에는 모델 과대가 단순한 LSTM 실패라기보다 outlet 관측값이 자연 runoff와 다르게 완화된 결과일 수 있고, rating/record caveat가 있는 경우에는 peak magnitude 자체의 불확실성을 분리해 읽어야 합니다.",
        "",
        "## 5. Extreme-rain stress event 방향",
        "",
        f"Stress table 기준 rated event 수는 `{int(stress_row.get('stress_event_count', 0)) if stress_row is not None and not stress_row.empty else 0}`개, seed-event record 수는 `{int(stress_row.get('stress_seed_event_records', 0)) if stress_row is not None and not stress_row.empty else 0}`개입니다. 방향성 요약은 {stress_error_mode(stress_row)}입니다.",
        "",
        *markdown_table(
            stress_table,
            ["predictor", "obs_peak_under_frac", "obs_peak_rel_error_pct", "window_peak_rel_error_pct", "abs_timing_h", "top_flow_hit"],
            {
                "predictor": "predictor",
                "obs_peak_under_frac": "obs-peak 과소비율",
                "obs_peak_rel_error_pct": "obs-peak error %",
                "window_peak_rel_error_pct": "window-peak error %",
                "abs_timing_h": "abs timing h",
                "top_flow_hit": "top-flow hit",
            },
        ),
        "",
        "대표 stress event는 flood-response case를 먼저 두고, 그 안에서 q50 window-peak error가 큰 순서로 골랐습니다. 같은 event의 seed 3개는 median으로 접었습니다.",
        "",
        *markdown_table(
            stress_examples,
            [
                "event_id",
                "rain_cohort",
                "response_class",
                "wet_cluster_total_rain",
                "observed_response_peak",
                "obs_peak_to_flood_ari2",
                "response_lag_from_rain_peak_h",
                "model1_window_peak_rel_error_pct",
                "q50_window_peak_rel_error_pct",
                "q99_window_peak_rel_error_pct",
                "model2_obs_peak_quantile_bracket",
            ],
            {
                "event_id": "Event",
                "rain_cohort": "Rain cohort",
                "response_class": "Response",
                "wet_cluster_total_rain": "Rain mm",
                "observed_response_peak": "Obs peak",
                "obs_peak_to_flood_ari2": "Obs/ARI2",
                "response_lag_from_rain_peak_h": "Lag h",
                "model1_window_peak_rel_error_pct": "M1 win err %",
                "q50_window_peak_rel_error_pct": "q50 win err %",
                "q99_window_peak_rel_error_pct": "q99 win err %",
                "model2_obs_peak_quantile_bracket": "Obs peak bracket",
            },
        ),
        "",
        "## 6. 기존 hydrograph diagnosis와 최종 판단",
        "",
        f"기존 hydrograph interpretation 요약: {first_paragraph(hydrograph_interpretation)}",
        "",
        f"기존 final diagnosis 요약: {first_paragraph(final_diagnosis)}",
        "",
        "최종 판단: " + driver_explanation,
        "",
        "해석 caveat: 이 문서는 기존 산출물의 join 기반 진단입니다. USGS note의 station context, 상관관계의 순위 신호, stress-event error direction이 서로 같은 방향일 때만 강한 설명으로 읽고, 서로 어긋날 때는 event별 혼합 신호로 남기는 편이 안전합니다.",
        "",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_index_report(summary: pd.DataFrame, output_dir: Path) -> Path:
    report_dir = output_dir / "report"
    out = report_dir / "individual_basin_diagnostic_report.md"
    report_dir.mkdir(parents=True, exist_ok=True)

    display = summary[
        [
            "basin",
            "gauge_name",
            "state",
            "dominant_distance_label",
            "primary_driver",
            "confidence",
            "metric_error_mode",
            "stress_error_mode",
            "usgs_categories",
            "report_path",
        ]
    ].copy()
    report_root = (output_dir / "report").resolve()

    def report_link(path_text: str) -> str:
        path = resolve(Path(path_text)).resolve()
        try:
            target = path.relative_to(report_root)
        except ValueError:
            target = Path(path_text)
        return f"[report]({target})"

    display["report_path"] = display["report_path"].map(report_link)

    lines = [
        "# DRBC 개별 basin 성능 진단 리포트",
        "",
        "이 산출물은 기존 `drbc_attribute_metric_correlations`, `median_deviation`, `event_response`, `extreme_rain stress`, `docs/references/basin/usgs_station_notes`를 basin 단위로 join한 해석본입니다.",
        "",
        "해석 순서는 `성능지표 방향 -> 유역/streamflow 특성 -> 전체 Spearman 상관 맥락 -> USGS station note -> extreme-rain stress event`입니다. 상관관계는 원인 증명이 아니며, USGS station note와 stress-event 방향이 같은 쪽을 가리킬 때만 원인 후보 신뢰도를 높였습니다.",
        "",
        "## 산출물",
        "",
        "- `tables/individual_basin_diagnostic_summary.csv`: 38개 basin 요약표",
        "- `report/basins/{gauge_id}.md`: basin별 상세 진단",
        "- `metadata/analysis_metadata.json`: 입력 경로와 생성 시각",
        "",
        "## 38개 basin 요약",
        "",
        *markdown_table(
            display,
            [
                "basin",
                "gauge_name",
                "state",
                "dominant_distance_label",
                "primary_driver",
                "confidence",
                "metric_error_mode",
                "stress_error_mode",
                "usgs_categories",
                "report_path",
            ],
            {
                "basin": "Gauge",
                "gauge_name": "Station",
                "state": "State",
                "dominant_distance_label": "IQR tier",
                "primary_driver": "Primary diagnosis",
                "confidence": "Confidence",
                "metric_error_mode": "Primary metric direction",
                "stress_error_mode": "Stress-event direction",
                "usgs_categories": "USGS context",
                "report_path": "Detail",
            },
        ),
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def write_metadata(args: argparse.Namespace, output_dir: Path, summary: pd.DataFrame) -> Path:
    meta_dir = output_dir / "metadata"
    meta_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "analysis": "DRBC individual basin diagnostic reports",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "n_basins": int(len(summary)),
        "inputs": {
            "correlation_dir": rel(args.correlation_dir),
            "median_deviation_dir": rel(args.median_deviation_dir),
            "event_response_summary": rel(args.event_response_summary),
            "event_response_table": rel(args.event_response_table),
            "stress_error_table": rel(args.stress_error_table),
            "stress_manifest": rel(args.stress_manifest),
            "usgs_note_dir": rel(args.usgs_note_dir),
            "basin_dissect_dir": rel(args.basin_dissect_dir),
        },
        "outputs": {
            "summary_table": rel(output_dir / "tables/individual_basin_diagnostic_summary.csv"),
            "index_report": rel(output_dir / "report/individual_basin_diagnostic_report.md"),
            "basin_reports_dir": rel(output_dir / "report/basins"),
        },
        "interpretation_rules": {
            "fhv_sign": "positive FHV means simulated high-flow volume exceeds observed high-flow volume; negative means underestimation",
            "causal_language": "correlation is treated as context, not proof; USGS station evidence and stress-event direction raise confidence",
        },
    }
    path = meta_dir / "analysis_metadata.json"
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main() -> None:
    args = parse_args()
    args.correlation_dir = resolve(args.correlation_dir)
    args.median_deviation_dir = resolve(args.median_deviation_dir)
    args.event_response_summary = resolve(args.event_response_summary)
    args.event_response_table = resolve(args.event_response_table)
    args.stress_error_table = resolve(args.stress_error_table)
    args.stress_manifest = resolve(args.stress_manifest)
    args.usgs_note_dir = resolve(args.usgs_note_dir)
    args.basin_dissect_dir = resolve(args.basin_dissect_dir)
    args.output_dir = resolve(args.output_dir)

    feature_metric = load_feature_metric_table(args.correlation_dir)
    correlations = load_correlations(args.correlation_dir)
    tier_profile, model_tiers = load_median_deviation(args.median_deviation_dir)
    detail_profile, far_cause = load_median_deviation_detail(args.median_deviation_dir)
    event_response = load_event_response(args.event_response_summary, args.event_response_table)
    manifest, response_class_counts = load_manifest(args.stress_manifest)
    stress = load_stress_aggregate(args.stress_error_table)
    stress_examples_by_basin = load_stress_event_examples(args.stress_error_table)

    basins = sorted(set(feature_metric.index) & set(tier_profile.index))
    if len(basins) != 38:
        raise ValueError(f"Expected 38 shared basins, got {len(basins)}")

    report_dir = args.output_dir / "report" / "basins"
    rows: list[dict[str, Any]] = []
    for basin in basins:
        feature_row = feature_metric.loc[basin]
        tier_row = tier_profile.loc[basin]
        detail_row = detail_profile.loc[basin] if basin in detail_profile.index else None
        cause_row = far_cause.loc[basin] if basin in far_cause.index else None
        event_row = event_response.loc[basin] if basin in event_response.index else None
        manifest_row = manifest.loc[basin] if basin in manifest.index else None
        stress_row = stress.loc[basin] if basin in stress.index else None
        stress_examples = stress_examples_by_basin.get(basin, pd.DataFrame())

        note = find_note(args.usgs_note_dir, basin)
        dissect = find_basin_dissect(args.basin_dissect_dir, basin)
        usgs_categories = detect_usgs_categories(note.text)
        notable = select_notable_features(feature_metric, basin)
        corr_context = select_correlation_context(correlations, notable)

        primary_driver, driver_explanation, confidence = driver_diagnosis(
            feature_row,
            tier_row,
            cause_row,
            event_row,
            manifest_row,
            stress_row,
            usgs_categories,
            note.text,
        )

        report_path = report_dir / f"{basin}.md"
        write_basin_report(
            basin=basin,
            output_path=report_path,
            feature_row=feature_row,
            tier_row=tier_row,
            detail_row=detail_row,
            cause_row=cause_row,
            model_tiers=model_tiers,
            event_row=event_row,
            manifest_row=manifest_row,
            stress_row=stress_row,
            stress_examples=stress_examples,
            notable_features=notable,
            corr_context=corr_context,
            note=note,
            dissect=dissect,
            usgs_categories=usgs_categories,
            primary_driver=primary_driver,
            driver_explanation=driver_explanation,
            confidence=confidence,
        )

        counts = response_class_counts.loc[basin].to_dict() if basin in response_class_counts.index else {}
        rows.append(
            {
                "basin": basin,
                "gauge_name": tier_row.get("gauge_name") or feature_row.get("gauge_name", ""),
                "state": tier_row.get("state") or (manifest_row.get("state") if manifest_row is not None else ""),
                "dominant_distance_label": TIER_LABELS.get(
                    str(tier_row.get("dominant_distance_label", "")),
                    str(tier_row.get("dominant_distance_label", "")),
                ),
                "far_or_extreme_share": tier_row.get("far_or_extreme_share", np.nan),
                "mean_distance_any_metric_seed": tier_row.get("mean_distance_any_metric_seed", np.nan),
                "max_distance_any_metric_seed": tier_row.get("max_distance_any_metric_seed", np.nan),
                "m1_NSE": feature_row.get("m1_NSE", np.nan),
                "m2_NSE": feature_row.get("m2_NSE", np.nan),
                "m1_KGE": feature_row.get("m1_KGE", np.nan),
                "m2_KGE": feature_row.get("m2_KGE", np.nan),
                "m1_FHV": feature_row.get("m1_FHV", np.nan),
                "m2_FHV": feature_row.get("m2_FHV", np.nan),
                "m1_Peak_MAPE": feature_row.get("m1_Peak_MAPE", np.nan),
                "m2_Peak_MAPE": feature_row.get("m2_Peak_MAPE", np.nan),
                "tail_hit_q99": feature_row.get("tail_hit_q99", np.nan),
                "area": feature_row.get("area", np.nan),
                "obs_mean_flow": feature_row.get("obs_mean_flow", np.nan),
                "obs_q99": feature_row.get("obs_q99", np.nan),
                "obs_cv": feature_row.get("obs_cv", np.nan),
                "snow_fraction": feature_row.get("snow_fraction", np.nan),
                "human_use": feature_row.get("human_use", np.nan),
                "land_use": feature_row.get("land_use", np.nan),
                "hydromod_risk": manifest_row.get("hydromod_risk", np.nan) if manifest_row is not None else np.nan,
                "stress_event_count": stress_row.get("stress_event_count", np.nan) if stress_row is not None else np.nan,
                "model1_window_peak_rel_error_pct": stress_row.get("model1_window_peak_rel_error_pct", np.nan) if stress_row is not None else np.nan,
                "q50_window_peak_rel_error_pct": stress_row.get("q50_window_peak_rel_error_pct", np.nan) if stress_row is not None else np.nan,
                "q99_window_peak_rel_error_pct": stress_row.get("q99_window_peak_rel_error_pct", np.nan) if stress_row is not None else np.nan,
                "primary_driver": primary_driver,
                "driver_explanation": driver_explanation,
                "existing_cause_group": cause_row.get("cause_group", "") if cause_row is not None else "",
                "existing_primary_cause": cause_row.get("primary_cause", "") if cause_row is not None else "",
                "existing_flow_response_type": cause_row.get("flow_response_type", "") if cause_row is not None else "",
                "existing_event_response_support": cause_row.get("event_response_support", "") if cause_row is not None else "",
                "confidence": confidence,
                "metric_error_mode": metric_error_mode(feature_row),
                "stress_error_mode": stress_error_mode(stress_row),
                "usgs_categories": category_labels(usgs_categories),
                "usgs_note_path": rel(note.path),
                "basin_dissect_path": rel(dissect.path),
                "report_path": rel(report_path),
                "flood_response_ge2_to_lt25": counts.get("flood_response_ge2_to_lt25", 0),
                "flood_response_ge25": counts.get("flood_response_ge25", 0),
                "high_flow_non_flood_q99_only": counts.get("high_flow_non_flood_q99_only", 0),
                "low_response_below_q99": counts.get("low_response_below_q99", 0),
            }
        )

    tier_sort = {">=3 IQR": 0, "1.5-3 IQR": 1, "0.5-1.5 IQR": 2, "<0.5 IQR": 3}
    summary = pd.DataFrame(rows)
    summary["_tier_sort"] = summary["dominant_distance_label"].map(tier_sort).fillna(9)
    summary = summary.sort_values(["_tier_sort", "basin"]).drop(columns=["_tier_sort"]).reset_index(drop=True)
    tables_dir = args.output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    summary_path = tables_dir / "individual_basin_diagnostic_summary.csv"
    summary.to_csv(summary_path, index=False)

    index_path = write_index_report(summary, args.output_dir)
    meta_path = write_metadata(args, args.output_dir, summary)

    print(f"Wrote {len(summary)} basin reports")
    print(f"Summary: {summary_path.relative_to(REPO_ROOT)}")
    print(f"Index: {index_path.relative_to(REPO_ROOT)}")
    print(f"Metadata: {meta_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
