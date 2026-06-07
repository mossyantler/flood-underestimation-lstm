#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=2.0",
# ]
# ///
"""Plot signed direct-SHAP diagnostics from existing Model 2 SHAP tables."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT: Final = Path(__file__).resolve().parents[3]
DEFAULT_ANALYSIS_DIR: Final = REPO_ROOT / "output/model_analysis/shap/test_split"
QUANTILE_ORDER: Final = ("q50", "q90", "q95", "q99")
BLUE: Final = "#2563eb"
RED: Final = "#dc2626"
ZERO: Final = "#475569"


@dataclass(frozen=True, slots=True)
class FeatureKey:
    """Feature identity used across direct-SHAP tables."""

    quantile: str
    feature: str


@dataclass(frozen=True, slots=True)
class FeatureSummary:
    """Seed-mean feature attribution summary."""

    quantile: str
    feature: str
    mean_abs: float
    mean_signed: float


@dataclass(frozen=True, slots=True)
class EventSignedValue:
    """Event-level signed SHAP value for one feature and quantile."""

    quantile: str
    feature: str
    signed_value: float


def parse_float(raw: str) -> float:
    """Parse a required finite float from CSV text."""
    value = float(raw)
    if not np.isfinite(value):
        msg = f"non-finite numeric value: {raw}"
        raise ValueError(msg)
    return value


def read_global_summary(path: Path) -> list[FeatureSummary]:
    """Read seed-mean global SHAP summary rows."""
    rows: list[FeatureSummary] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                FeatureSummary(
                    quantile=row["quantile"],
                    feature=row["feature"],
                    mean_abs=parse_float(row["mean_abs_shap_mean"]),
                    mean_signed=parse_float(row["mean_signed_shap_mean"]),
                )
            )
    return rows


def read_event_values(paths: list[Path]) -> list[EventSignedValue]:
    """Read event-level signed SHAP values from all seed tables."""
    rows: list[EventSignedValue] = []
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                rows.append(
                    EventSignedValue(
                        quantile=row["quantile"],
                        feature=row["feature"],
                        signed_value=parse_float(row["mean_signed_shap"]),
                    )
                )
    return rows


def top_features(summary: list[FeatureSummary], quantile: str, top_n: int) -> list[str]:
    """Select top features by mean absolute SHAP for a quantile."""
    selected = [row for row in summary if row.quantile == quantile]
    selected.sort(key=lambda row: row.mean_abs, reverse=True)
    return [row.feature for row in selected[:top_n]]


def signed_matrix(summary: list[FeatureSummary], features: list[str]) -> np.ndarray:
    """Build feature x quantile signed SHAP matrix."""
    by_key = {FeatureKey(row.quantile, row.feature): row.mean_signed for row in summary}
    data: list[list[float]] = []
    for feature in features:
        data.append([by_key.get(FeatureKey(quantile, feature), np.nan) for quantile in QUANTILE_ORDER])
    return np.asarray(data, dtype=float)


def save_signed_ladder_heatmap(summary: list[FeatureSummary], features: list[str], figures_dir: Path) -> list[Path]:
    """Save quantile ladder heatmap for mean signed SHAP."""
    matrix = signed_matrix(summary, features)
    vmax = float(np.nanmax(np.abs(matrix))) if matrix.size else 1.0
    vmax = max(vmax, 1e-9)
    fig, ax = plt.subplots(figsize=(8.8, 5.8))
    image = ax.imshow(matrix, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_xticks(np.arange(len(QUANTILE_ORDER)), labels=QUANTILE_ORDER)
    ax.set_yticks(np.arange(len(features)), labels=features)
    ax.set_title("Mean signed direct SHAP by quantile")
    ax.set_xlabel("Model 2 quantile output")
    ax.set_ylabel("Top q99 features by mean |SHAP|")
    for row_idx, feature in enumerate(features):
        for col_idx, _quantile in enumerate(QUANTILE_ORDER):
            value = matrix[row_idx, col_idx]
            text_color = "white" if abs(value) > vmax * 0.55 else "#111827"
            ax.text(col_idx, row_idx, f"{value:+.3g}", ha="center", va="center", color=text_color, fontsize=8)
    cbar = fig.colorbar(image, ax=ax, shrink=0.84)
    cbar.set_label("Mean signed SHAP")
    fig.tight_layout()
    return save_figure(fig, figures_dir / "quantile_lstm_direct_shap_signed_ladder_heatmap")


def grouped_signed_values(events: list[EventSignedValue], features: list[str], quantile: str) -> list[np.ndarray]:
    """Collect event-level signed SHAP arrays in feature order."""
    grouped: list[np.ndarray] = []
    for feature in features:
        values = [row.signed_value for row in events if row.quantile == quantile and row.feature == feature]
        grouped.append(np.asarray(values, dtype=float))
    return grouped


def save_q99_signed_bar(
    events: list[EventSignedValue], features: list[str], figures_dir: Path
) -> list[Path]:
    values = grouped_signed_values(events, features, "q99")
    means = [float(np.mean(arr)) if arr.size else np.nan for arr in values]
    ordered = sorted(zip(features, means, strict=True), key=lambda item: abs(item[1]))
    sorted_features = [item[0] for item in ordered]
    sorted_means = [item[1] for item in ordered]
    colors = [RED if value > 0 else BLUE for value in sorted_means]
    max_abs = max([abs(value) for value in sorted_means], default=1e-9)
    x_limit = max(max_abs * 1.08, 1e-9)
    fig, ax = plt.subplots(figsize=(8, 5.8))
    ax.barh(sorted_features, sorted_means, color=colors, alpha=0.86)
    ax.axvline(0, color=ZERO, linewidth=1.0, linestyle="--")
    ax.set_xlim(-x_limit, x_limit)
    ax.set_xlabel("Mean signed SHAP")
    ax.set_ylabel("Top q99 features by mean |SHAP|")
    ax.set_title("q99 direct SHAP signed effect")
    ax.grid(True, axis="x", color="#e5e7eb", linewidth=0.7)
    fig.tight_layout()
    return save_figure(fig, figures_dir / "quantile_lstm_direct_shap_signed_q99_bar")


def save_figure(fig: plt.Figure, stem: Path) -> list[Path]:
    """Save PNG and PDF versions of a figure."""
    outputs = [stem.with_suffix(".png"), stem.with_suffix(".pdf")]
    for path in outputs:
        fig.savefig(path, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot signed direct-SHAP diagnostics from existing CSV outputs.")
    parser.add_argument("--analysis-dir", type=Path, default=DEFAULT_ANALYSIS_DIR)
    parser.add_argument("--top-n", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    analysis_dir = args.analysis_dir.resolve()
    tables_dir = analysis_dir / "tables"
    figures_dir = analysis_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    summary = read_global_summary(tables_dir / "quantile_lstm_direct_shap_global_feature_importance_seed_mean.csv")
    event_paths = sorted(tables_dir.glob("quantile_lstm_direct_shap_event_feature_importance_seed*.csv"))
    events = read_event_values(event_paths)
    features = top_features(summary, "q99", args.top_n)
    outputs = [
        *save_signed_ladder_heatmap(summary, features, figures_dir),
        *save_q99_signed_bar(events, features, figures_dir),
    ]
    print("Wrote signed SHAP figures:")
    for path in outputs:
        print(f"- {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
