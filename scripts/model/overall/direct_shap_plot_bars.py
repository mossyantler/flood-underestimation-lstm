from __future__ import annotations

import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import shap

from direct_shap_plot_common import (
    NEUTRAL,
    PANEL_DPI,
    EventFeatureRow,
    feature_labels,
    seed_rows,
    seed_values,
    shap_matrix,
)
from direct_shap_plot_layout import apply_text_size, recolor_bar_patches, recolor_signed_artists, save_panel_composite


def quantile_explanation(rows: list[EventFeatureRow], quantile: str, features: list[str]) -> shap.Explanation:
    values = shap_matrix(rows, quantile, features)
    if values.size == 0 or values.shape[0] == 0:
        msg = f"No rows available for quantile={quantile}"
        raise ValueError(msg)
    return shap.Explanation(values=values, data=values, feature_names=feature_labels(features, compact=False))


def write_seed_bar_panel(rows: list[EventFeatureRow], quantile: str, features: list[str], seed: str, out: Path) -> None:
    explanation = quantile_explanation(rows, quantile, features)
    with plt.rc_context({"font.size": 7.5, "axes.labelsize": 8, "xtick.labelsize": 7, "ytick.labelsize": 7}):
        plt.figure(figsize=(6.6, max(3.8, 0.28 * len(features))))
        shap.plots.bar(explanation, max_display=len(features), show=False)
    fig = plt.gcf()
    ax = plt.gca()
    recolor_bar_patches(ax, signed=False)
    recolor_signed_artists(fig)
    ax.set_title(f"Seed {seed}", fontsize=10, pad=8)
    ax.set_xlabel("Mean absolute SHAP value")
    ax.tick_params(axis="both", labelsize=7)
    apply_text_size(fig, base=7.5, emphasis=7.5)
    fig.subplots_adjust(left=0.28, right=0.98, bottom=0.16, top=0.9)
    fig.savefig(out, dpi=PANEL_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def save_bar_png(rows: list[EventFeatureRow], quantile: str, features: list[str], figures_dir: Path) -> Path:
    out = figures_dir / f"quantile_lstm_direct_shap_bar_{quantile}.png"
    with tempfile.TemporaryDirectory(prefix="direct_shap_bar_") as tmp_raw:
        tmp_dir = Path(tmp_raw)
        panel_paths: list[Path] = []
        for seed in seed_values(rows):
            panel_path = tmp_dir / f"bar_seed{seed}.png"
            write_seed_bar_panel(seed_rows(rows, seed), quantile, features, seed, panel_path)
            panel_paths.append(panel_path)
        save_panel_composite(panel_paths, out, f"Direct SHAP bar plot for {quantile} by seed", horizontal=True)
    return out


def feature_signed_means(rows: list[EventFeatureRow], quantile: str, features: list[str]) -> list[float]:
    means: list[float] = []
    for feature in features:
        values = [row.signed_value for row in rows if row.quantile == quantile and row.feature == feature]
        means.append(float(np.mean(values)) if values else 0.0)
    return means


def signed_explanation(rows: list[EventFeatureRow], quantile: str, features: list[str]) -> shap.Explanation:
    means = feature_signed_means(rows, quantile, features)
    values = np.asarray(means, dtype=float)
    return shap.Explanation(values=values, data=values, feature_names=feature_labels(features, compact=False))


def write_seed_signed_bar_panel(
    rows: list[EventFeatureRow], quantile: str, features: list[str], seed: str, out: Path
) -> None:
    explanation = signed_explanation(rows, quantile, features)
    with plt.rc_context({"font.size": 7.5, "axes.labelsize": 8, "xtick.labelsize": 7, "ytick.labelsize": 7}):
        plt.figure(figsize=(6.6, max(3.8, 0.28 * len(features))))
        shap.plots.bar(explanation, max_display=len(features), order=np.arange(len(features)), show=False)
    fig = plt.gcf()
    ax = plt.gca()
    recolor_bar_patches(ax, signed=True)
    recolor_signed_artists(fig)
    ax.axvline(0, color=NEUTRAL, linewidth=1.0, linestyle="--")
    ax.set_title(f"Seed {seed}", fontsize=10, pad=8)
    ax.set_xlabel("Mean signed SHAP value")
    ax.tick_params(axis="both", labelsize=7)
    ax.grid(True, axis="x", color="#e5e7eb", linewidth=0.7)
    apply_text_size(fig, base=7.5, emphasis=7.5)
    fig.subplots_adjust(left=0.28, right=0.98, bottom=0.16, top=0.9)
    fig.savefig(out, dpi=PANEL_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def save_signed_bar_png(rows: list[EventFeatureRow], quantile: str, features: list[str], figures_dir: Path) -> Path:
    out = figures_dir / f"quantile_lstm_direct_shap_signed_bar_{quantile}.png"
    with tempfile.TemporaryDirectory(prefix="direct_shap_signed_bar_") as tmp_raw:
        tmp_dir = Path(tmp_raw)
        panel_paths: list[Path] = []
        for seed in seed_values(rows):
            panel_path = tmp_dir / f"signed_bar_seed{seed}.png"
            write_seed_signed_bar_panel(seed_rows(rows, seed), quantile, features, seed, panel_path)
            panel_paths.append(panel_path)
        save_panel_composite(panel_paths, out, f"Direct SHAP signed bar plot for {quantile} by seed", horizontal=True)
    return out
