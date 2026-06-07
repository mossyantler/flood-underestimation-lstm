from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np

REPO_ROOT: Final = Path(__file__).resolve().parents[3]
QUANTILES: Final = ("q50", "q90", "q95", "q99")
POSITIVE: Final = "#dc2626"
NEGATIVE: Final = "#2563eb"
NEUTRAL: Final = "#64748b"
FORCE_POSITIVE: Final = "#C44536"
FORCE_NEGATIVE: Final = "#2F6F9F"
FORCE_POSITIVE_LIGHT: Final = "#F0A092"
FORCE_NEGATIVE_LIGHT: Final = "#8EB7D4"
FORCE_CONTRIBUTION_THRESHOLD: Final = 0.04
PANEL_DPI: Final = 240
PUBLICATION_FEATURE_LABELS: Final = {
    "area": "Area",
    "slope": "Slope",
    "forest_fraction": "Forest fraction",
    "soil_depth": "Soil depth",
    "permeability": "Permeability",
    "snow_fraction": "Snow fraction",
    "baseflow_index": "Baseflow index",
    "aridity": "Aridity",
    "Rainf": "Precipitation",
    "Tair": "Air temperature",
    "Qair": "Specific humidity",
    "SWdown": "Shortwave radiation",
}
COMPACT_FEATURE_LABELS: Final = {
    "area": "Area",
    "slope": "Slope",
    "forest_fraction": "Forest",
    "soil_depth": "Soil depth",
    "permeability": "Perm.",
    "snow_fraction": "Snow",
    "baseflow_index": "Baseflow",
    "aridity": "Aridity",
    "Rainf": "Precip.",
    "Tair": "Temp.",
    "Qair": "Humidity",
    "SWdown": "Radiation",
}


@dataclass(frozen=True, slots=True)
class EventFeatureRow:
    seed: str
    row_index: str
    basin: str
    event_id: str
    anchor_time: str
    quantile: str
    feature: str
    feature_label: str
    feature_group: str
    signed_value: float
    abs_value: float
    prediction: float


@dataclass(frozen=True, slots=True)
class PlotResult:
    figures: list[Path]
    reports: list[Path]
    manifest: Path


def parse_float(raw: str, *, fallback: float = 0.0) -> float:
    if raw == "":
        return fallback
    value = float(raw)
    if not np.isfinite(value):
        return fallback
    return value


def seed_from_path(path: Path) -> str:
    token = path.stem.rsplit("seed", 1)[-1]
    return token if token.isdigit() else "unknown"


def read_event_rows(analysis_dir: Path) -> list[EventFeatureRow]:
    rows: list[EventFeatureRow] = []
    pattern = "quantile_lstm_direct_shap_event_feature_importance_seed*.csv"
    for path in sorted((analysis_dir / "tables").glob(pattern)):
        seed = seed_from_path(path)
        with path.open(newline="", encoding="utf-8") as handle:
            for raw in csv.DictReader(handle):
                rows.append(
                    EventFeatureRow(
                        seed=seed,
                        row_index=raw.get("row_index", ""),
                        basin=raw.get("basin", ""),
                        event_id=raw.get("event_id", ""),
                        anchor_time=raw.get("anchor_time", ""),
                        quantile=raw["quantile"],
                        feature=raw["feature"],
                        feature_label=raw.get("feature_label_ko") or raw["feature"],
                        feature_group=raw.get("feature_group", ""),
                        signed_value=parse_float(raw.get("mean_signed_shap", "")),
                        abs_value=parse_float(raw.get("mean_abs_shap", "")),
                        prediction=parse_float(raw.get("quantile_prediction_normalized", "")),
                    )
                )
    if not rows:
        msg = f"No direct-SHAP event tables found under {analysis_dir / 'tables'}"
        raise FileNotFoundError(msg)
    return rows


def top_features(rows: list[EventFeatureRow], quantile: str, top_n: int) -> list[str]:
    grouped: dict[str, list[float]] = {}
    for row in rows:
        if row.quantile == quantile:
            grouped.setdefault(row.feature, []).append(row.abs_value)
    ranked = sorted(grouped, key=lambda feature: float(np.mean(grouped[feature])), reverse=True)
    return ranked[:top_n]


def seed_values(rows: list[EventFeatureRow]) -> list[str]:
    return sorted({row.seed for row in rows if row.seed != "unknown"})


def seed_rows(rows: list[EventFeatureRow], seed: str) -> list[EventFeatureRow]:
    return [row for row in rows if row.seed == seed]


def feature_labels(features: list[str], *, compact: bool) -> list[str]:
    label_map = COMPACT_FEATURE_LABELS if compact else PUBLICATION_FEATURE_LABELS
    return [label_map.get(feature, feature.replace("_", " ")) for feature in features]


def event_key(row: EventFeatureRow) -> tuple[str, str, str, str, str]:
    return (row.seed, row.row_index, row.basin, row.event_id, row.anchor_time)


def shap_matrix(rows: list[EventFeatureRow], quantile: str, features: list[str]) -> np.ndarray:
    selected = [row for row in rows if row.quantile == quantile]
    event_order = list(dict.fromkeys(event_key(row) for row in selected))
    by_event_feature = {(event_key(row), row.feature): row.signed_value for row in selected}
    matrix = np.zeros((len(event_order), len(features)), dtype=float)
    for event_idx, key in enumerate(event_order):
        for feature_idx, feature in enumerate(features):
            matrix[event_idx, feature_idx] = by_event_feature.get((key, feature), 0.0)
    return matrix
