"""Vocabulary lock + shared utilities for the expanded DRBC RQ analysis pipeline.

This module is the single source of truth for column names, period boundaries,
NOAA event-type lexicon, basin id normalization, and aggregation order across
all RQ-0 through RQ-5 analyses run on the expanded DRBC observed test split.

See `.omc/plans/2026-05-26-expanded-drbc-rebuild-execution.md` §3 (Phase C0)
for the full design rationale.

Phase B scripts MUST import constants and utilities from this module rather
than redefining them inline. The RQ-5 reused script
`scripts/model/hydrograph/analyze_expanded_drbc_probabilistic_diagnostics.py`
imports vocabulary constants from here for cross-RQ consistency.
"""
from __future__ import annotations

import re
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Period / window / sampling constants
# ---------------------------------------------------------------------------

TAU_ORDER: tuple[str, ...] = ("model1", "q50", "q90", "q95", "q99")
"""Canonical τ ordering. M1 deterministic is treated as a τ-baseline at index 0."""

PREDICTION_COLUMNS: dict[str, str] = {
    "model1": "model1",
    "q50": "q50",
    "q90": "q90",
    "q95": "q95",
    "q99": "q99",
}
"""Mapping from canonical τ key → column name in required_series CSVs."""

TRAIN_PERIOD: tuple[str, str] = ("2000-01-01", "2010-12-31")
TEST_PERIOD: tuple[str, str] = ("2014-01-01", "2016-12-31")

EVENT_WINDOW_HOURS: int = 6
"""Half-width (±) of the event window around an observed peak."""

EVENT_MERGE_GAP_HOURS: int = 12
"""Peaks closer than this are merged into one event (peak = max obs)."""

HIGH_FLOW_PERCENTILE: float = 0.99
"""Q99 by definition; used by B1 threshold and B3/B5/B6/B9."""

SEEDS: tuple[int, ...] = (111, 222, 444)

# ---------------------------------------------------------------------------
# NOAA event-type lexicon (Critic-verified against actual catalog)
# ---------------------------------------------------------------------------

NOAA_LABELS: tuple[str, ...] = ("Flash Flood", "Flood", "Coastal Flood", "Other")
"""Empirical lexicon present in
output/model_analysis/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv.
Riverine and Ice Jam labels are absent from the actual catalog and so are NOT
included. "Other" is the residual bucket for any unmatched annotation."""

NOAA_REGEX: dict[str, re.Pattern[str]] = {
    "Flash Flood": re.compile(r"\bFlash Flood\b(?!\s+(?:Watch|Advisory))"),
    "Flood": re.compile(r"(?<!Flash )(?<!Coastal )\bFlood\b(?!\s+(?:Watch|Advisory))"),
    "Coastal Flood": re.compile(r"\bCoastal Flood\b"),
}
"""Patterns are intentionally anchored to avoid matching `Flash Flood Watch`
(non-event NWS bulletin) and to disambiguate `Flash Flood` / `Coastal Flood`
from the bare `Flood` family."""

NOAA_TIE_BREAK: tuple[str, ...] = ("Flash Flood", "Coastal Flood", "Flood", "Other")
"""Tie-breaking order for dominant_event_type when an annotation contains
equal token counts across multiple labels. Most-specific wins."""

# ---------------------------------------------------------------------------
# Basin id normalization (resolves Architect #2 + Critic NOAA usgs_id vs basin_id)
# ---------------------------------------------------------------------------


def normalize_basin_id(raw: object) -> str:
    """Normalize a USGS / CAMELSH basin id to the canonical 8-char zero-padded form.

    Empty / NaN inputs become an empty string so callers can filter explicitly.
    """
    if raw is None:
        return ""
    text = str(raw).strip()
    if not text or text.lower() == "nan":
        return ""
    return text.zfill(8)


# ---------------------------------------------------------------------------
# NaN policy
# ---------------------------------------------------------------------------


def filter_valid_rows(
    df: pd.DataFrame,
    *,
    obs_col: str = "obs",
    pred_cols: Sequence[str] = ("model1", "q50", "q90", "q95", "q99"),
) -> pd.DataFrame:
    """Drop rows where the obs column is NaN.

    Pred-NaN rows are *kept* so that per-τ metrics can drop NaN individually
    rather than penalizing every τ for a missing prediction in one column.
    """
    del pred_cols  # not used directly; kept for caller documentation
    return df.dropna(subset=[obs_col]).copy()


# ---------------------------------------------------------------------------
# Aggregation order (locks Architect #1)
# ---------------------------------------------------------------------------


def per_basin_seed_then_median(
    df: pd.DataFrame,
    *,
    value_col: str,
    basin_col: str = "basin_id",
    seed_col: str = "seed",
) -> pd.Series:
    """Canonical aggregation: per-basin per-seed value → median across seeds within basin.

    Callers must pre-aggregate ``df`` to one row per ``(basin_col, seed_col)`` for
    ``value_col``. The inner ``.first()`` dereferences the scalar; if multiple rows
    exist per ``(basin, seed)``, only the first is used — callers are responsible
    for reducing to scalar before calling this function.

    Returns a Series indexed by ``basin_col`` containing the cross-seed median.
    """
    inner = df.groupby([basin_col, seed_col])[value_col].first()
    return inner.groupby(basin_col).median()


def paired_delta_per_seed(
    df_m1: pd.DataFrame,
    df_m2: pd.DataFrame,
    *,
    value_col: str,
    basin_col: str = "basin_id",
    seed_col: str = "seed",
) -> pd.DataFrame:
    """Compute delta(M2 − M1) per-basin per-seed.

    Returns a DataFrame with columns `[basin_col, seed_col, "delta"]`.
    The downstream caller must median-aggregate across seeds within basin
    via :func:`per_basin_seed_then_median` — do **not** pre-aggregate either side.
    """
    left = df_m1.set_index([basin_col, seed_col])[value_col]
    right = df_m2.set_index([basin_col, seed_col])[value_col]
    delta = (right - left).rename("delta").reset_index()
    return delta


# ---------------------------------------------------------------------------
# NOAA annotation parsing (B2 helpers)
# ---------------------------------------------------------------------------


def parse_dominant_event_type(annotation: str) -> tuple[str, dict[str, int]]:
    """Return ``(dominant_label, hit_counts)`` for a single NOAA annotation.

    ``hit_counts`` records the number of regex matches per label (zero entries
    omitted). If no canonical label matches the annotation, the dominant label
    is ``"Other"`` and ``hit_counts`` is empty so the caller can record the
    raw string in ``rq4b_noaa_annotation_unmatched.csv``.
    Ties are broken by :data:`NOAA_TIE_BREAK` (most-specific first).
    """
    if annotation is None:
        return "Other", {}
    text = str(annotation)
    counts: dict[str, int] = {}
    for label, pattern in NOAA_REGEX.items():
        n = len(pattern.findall(text))
        if n:
            counts[label] = n
    if not counts:
        return "Other", {}
    max_count = max(counts.values())
    candidates = [label for label, count in counts.items() if count == max_count]
    for label in NOAA_TIE_BREAK:
        if label in candidates:
            return label, counts
    return candidates[0], counts


# ---------------------------------------------------------------------------
# Smoke / sanity helpers
# ---------------------------------------------------------------------------


def constants_smoke_test() -> dict[str, object]:
    """Return the canonical constants in a single dict for sanity assertions."""
    return {
        "TAU_ORDER": TAU_ORDER,
        "PREDICTION_COLUMNS": PREDICTION_COLUMNS,
        "TRAIN_PERIOD": TRAIN_PERIOD,
        "TEST_PERIOD": TEST_PERIOD,
        "EVENT_WINDOW_HOURS": EVENT_WINDOW_HOURS,
        "EVENT_MERGE_GAP_HOURS": EVENT_MERGE_GAP_HOURS,
        "HIGH_FLOW_PERCENTILE": HIGH_FLOW_PERCENTILE,
        "SEEDS": SEEDS,
        "NOAA_LABELS": NOAA_LABELS,
        "NOAA_TIE_BREAK": NOAA_TIE_BREAK,
    }


__all__: Iterable[str] = (
    "TAU_ORDER",
    "PREDICTION_COLUMNS",
    "TRAIN_PERIOD",
    "TEST_PERIOD",
    "EVENT_WINDOW_HOURS",
    "EVENT_MERGE_GAP_HOURS",
    "HIGH_FLOW_PERCENTILE",
    "SEEDS",
    "NOAA_LABELS",
    "NOAA_REGEX",
    "NOAA_TIE_BREAK",
    "normalize_basin_id",
    "filter_valid_rows",
    "per_basin_seed_then_median",
    "paired_delta_per_seed",
    "parse_dominant_event_type",
    "constants_smoke_test",
)
