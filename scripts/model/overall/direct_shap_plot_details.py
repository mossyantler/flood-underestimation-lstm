from __future__ import annotations

import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import shap

from direct_shap_plot_bars import quantile_explanation
from direct_shap_plot_common import (
    FORCE_CONTRIBUTION_THRESHOLD,
    FORCE_NEGATIVE,
    FORCE_POSITIVE,
    PANEL_DPI,
    EventFeatureRow,
    event_key,
    feature_labels,
    seed_rows,
    seed_values,
)
from direct_shap_plot_layout import (
    apply_text_size,
    legacy_signed_cmap,
    recolor_force_artists,
    recolor_signed_artists,
    save_panel_composite,
)


def save_beeswarm(rows: list[EventFeatureRow], quantile: str, features: list[str], figures_dir: Path) -> Path:
    out = figures_dir / f"quantile_lstm_direct_shap_beeswarm_{quantile}.png"
    with tempfile.TemporaryDirectory(prefix="direct_shap_beeswarm_") as tmp_raw:
        tmp_dir = Path(tmp_raw)
        panel_paths: list[Path] = []
        for seed in seed_values(rows):
            panel_path = tmp_dir / f"beeswarm_seed{seed}.png"
            write_seed_beeswarm_panel(seed_rows(rows, seed), quantile, features, seed, panel_path)
            panel_paths.append(panel_path)
        save_panel_composite(panel_paths, out, f"Direct SHAP beeswarm plot for {quantile} by seed")
    return out


def write_seed_beeswarm_panel(rows: list[EventFeatureRow], quantile: str, features: list[str], seed: str, out: Path) -> None:
    explanation = quantile_explanation(rows, quantile, features)
    with plt.rc_context({"font.size": 7.5, "axes.labelsize": 8, "xtick.labelsize": 7, "ytick.labelsize": 7}):
        plt.figure(figsize=(6.9, max(4.0, 0.28 * len(features))))
        shap.plots.beeswarm(
            explanation,
            max_display=len(features),
            show=False,
            plot_size=None,
            color=legacy_signed_cmap(),
        )
    fig = plt.gcf()
    ax = plt.gca()
    ax.set_title(f"Seed {seed}", fontsize=10, pad=8)
    ax.set_xlabel("Event-level mean signed SHAP value")
    ax.tick_params(axis="both", labelsize=7)
    if len(fig.axes) > 1:
        fig.axes[-1].set_ylabel("Signed contribution")
        fig.axes[-1].tick_params(labelsize=7)
    apply_text_size(fig, base=7.5, emphasis=7.5)
    fig.subplots_adjust(left=0.26, right=0.88, bottom=0.17, top=0.9)
    fig.savefig(out, dpi=PANEL_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def representative_event(rows: list[EventFeatureRow], quantile: str) -> tuple[tuple[str, str, str, str, str], float]:
    predictions: dict[tuple[str, str, str, str, str], float] = {}
    for row in rows:
        if row.quantile == quantile:
            predictions[event_key(row)] = row.prediction
    if not predictions:
        msg = f"No representative event for quantile={quantile}"
        raise ValueError(msg)
    return max(predictions.items(), key=lambda item: item[1])


def representative_feature_values(
    rows: list[EventFeatureRow], quantile: str, features: list[str]
) -> tuple[tuple[str, str, str, str, str], float, np.ndarray]:
    key, prediction = representative_event(rows, quantile)
    by_feature = {row.feature: row.signed_value for row in rows if row.quantile == quantile and event_key(row) == key}
    values = np.asarray([by_feature.get(feature, 0.0) for feature in features], dtype=float)
    return key, prediction, values


def representative_top_features(rows: list[EventFeatureRow], quantile: str, top_n: int) -> list[str]:
    key, _prediction = representative_event(rows, quantile)
    values = {
        row.feature: row.signed_value
        for row in rows
        if row.quantile == quantile and event_key(row) == key and np.isfinite(row.signed_value)
    }
    ranked = sorted(values, key=lambda feature: abs(values[feature]), reverse=True)
    return ranked[:top_n]


def pad_force_axes(fig: plt.Figure) -> None:
    for ax in fig.axes:
        left, right = ax.get_xlim()
        span = right - left
        if span <= 0:
            continue
        ax.set_xlim(left - 0.04 * span, right + 0.09 * span)


def save_force_png(rows: list[EventFeatureRow], quantile: str, figures_dir: Path, event_top_n: int) -> Path:
    out = figures_dir / f"quantile_lstm_direct_shap_force_{quantile}.png"
    with tempfile.TemporaryDirectory(prefix="direct_shap_force_") as tmp_raw:
        tmp_dir = Path(tmp_raw)
        panel_paths: list[Path] = []
        for seed in seed_values(rows):
            seed_subset = seed_rows(rows, seed)
            features = representative_top_features(seed_subset, quantile, event_top_n)
            panel_path = tmp_dir / f"force_seed{seed}.png"
            write_seed_force_panel(seed_subset, quantile, features, seed, panel_path)
            panel_paths.append(panel_path)
        save_panel_composite(panel_paths, out, f"Direct SHAP force plot for {quantile} by seed")
    return out


def write_seed_force_panel(rows: list[EventFeatureRow], quantile: str, features: list[str], seed: str, out: Path) -> None:
    _key, prediction, values = representative_feature_values(rows, quantile, features)
    base_value = float(prediction - np.sum(values))
    with plt.rc_context({"font.size": 7.5, "xtick.labelsize": 7, "ytick.labelsize": 7}):
        shap.plots.force(
            base_value,
            values,
            feature_names=feature_labels(features, compact=True),
            matplotlib=True,
            show=False,
            figsize=(10.5, 2.0),
            contribution_threshold=FORCE_CONTRIBUTION_THRESHOLD,
            plot_cmap=[FORCE_POSITIVE, FORCE_NEGATIVE],
        )
    fig = plt.gcf()
    recolor_force_artists(fig)
    fig.suptitle(f"Seed {seed}", fontsize=10, y=0.98)
    apply_text_size(fig, base=7.5, emphasis=9)
    pad_force_axes(fig)
    fig.subplots_adjust(left=0.03, right=0.95, bottom=0.06, top=0.78)
    fig.savefig(out, dpi=PANEL_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def save_waterfall_png(rows: list[EventFeatureRow], quantile: str, figures_dir: Path, event_top_n: int) -> Path:
    out = figures_dir / f"quantile_lstm_direct_shap_waterfall_{quantile}.png"
    with tempfile.TemporaryDirectory(prefix="direct_shap_waterfall_") as tmp_raw:
        tmp_dir = Path(tmp_raw)
        panel_paths: list[Path] = []
        for seed in seed_values(rows):
            seed_subset = seed_rows(rows, seed)
            features = representative_top_features(seed_subset, quantile, event_top_n)
            panel_path = tmp_dir / f"waterfall_seed{seed}.png"
            write_seed_waterfall_panel(seed_subset, quantile, features, seed, panel_path)
            panel_paths.append(panel_path)
        save_panel_composite(panel_paths, out, f"Direct SHAP waterfall plot for {quantile} by seed")
    return out


def write_seed_waterfall_panel(rows: list[EventFeatureRow], quantile: str, features: list[str], seed: str, out: Path) -> None:
    _key, prediction, values = representative_feature_values(rows, quantile, features)
    base_value = float(prediction - np.sum(values))
    explanation = shap.Explanation(values=values, base_values=base_value, feature_names=feature_labels(features, compact=False))
    with plt.rc_context({"font.size": 7.5, "axes.labelsize": 8, "xtick.labelsize": 7, "ytick.labelsize": 7}):
        plt.figure(figsize=(6.2, max(3.2, 0.4 * len(features))))
        shap.plots.waterfall(explanation, max_display=len(features), show=False)
    fig = plt.gcf()
    ax = plt.gca()
    recolor_signed_artists(fig)
    ax.set_title(f"Seed {seed}", fontsize=10, pad=8)
    apply_text_size(fig, base=7.5, emphasis=8)
    fig.subplots_adjust(left=0.24, right=0.98, bottom=0.18, top=0.84)
    fig.savefig(out, dpi=PANEL_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def save_force_html(rows: list[EventFeatureRow], quantile: str, report_dir: Path, event_top_n: int) -> Path:
    sections: list[str] = []
    for seed in seed_values(rows):
        seed_subset = seed_rows(rows, seed)
        features = representative_top_features(seed_subset, quantile, event_top_n)
        _key, prediction, values = representative_feature_values(seed_subset, quantile, features)
        base_value = float(prediction - np.sum(values))
        force_plot = shap.plots.force(
            base_value,
            values,
            feature_names=feature_labels(features, compact=True),
            matplotlib=False,
            show=False,
            contribution_threshold=FORCE_CONTRIBUTION_THRESHOLD,
            plot_cmap=[FORCE_POSITIVE, FORCE_NEGATIVE],
        )
        sections.append(f"<h2>Seed {seed}</h2>{force_plot.html()}")
    out = report_dir / f"quantile_lstm_direct_shap_force_{quantile}.html"
    body = "\n".join(sections)
    out.write_text(
        f"<!doctype html><html><head><meta charset='utf-8'><title>Direct SHAP force plot for {quantile} by seed</title></head>"
        f"<body><h1>Direct SHAP force plot for {quantile} by seed</h1>{body}</body></html>",
        encoding="utf-8",
    )
    return out
