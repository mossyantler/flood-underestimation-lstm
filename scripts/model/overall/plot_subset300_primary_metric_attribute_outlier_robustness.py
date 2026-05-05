#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.8",
#   "numpy>=1.26",
#   "pandas>=2.2",
# ]
# ///
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT_DIR = (
    REPO_ROOT
    / "output/model_analysis/overall_analysis/main_comparison/attribute_correlations/robustness/tables"
)
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "output/model_analysis/overall_analysis/main_comparison/attribute_correlations/robustness/figures"
)

SCENARIOS = [
    "full",
    "metric_iqr_inliers",
    "area_ge_50",
    "metric_iqr_inliers_and_area_ge_50",
]
SCENARIO_LABELS = {
    "full": "Full",
    "metric_iqr_inliers": "IQR inliers",
    "area_ge_50": "Area >= 50",
    "metric_iqr_inliers_and_area_ge_50": "Both filters",
}
METRIC_ORDER = ["NSE", "KGE", "FHV", "abs_FHV", "Peak_Timing", "Peak_MAPE"]
METRIC_LABELS = {
    "NSE": "NSE",
    "KGE": "KGE",
    "FHV": "FHV",
    "abs_FHV": "|FHV|",
    "Peak_Timing": "Peak Timing",
    "Peak_MAPE": "Peak MAPE",
}
MODEL_LABELS = {"model1": "Model 1", "model2": "Model 2"}
MODEL_COLORS = {"model1": "#2563eb", "model2": "#dc2626"}
SCENARIO_COLORS = {
    "full": "#111827",
    "metric_iqr_inliers": "#2563eb",
    "area_ge_50": "#d97706",
    "metric_iqr_inliers_and_area_ge_50": "#059669",
}
FEATURE_LABELS = {
    "area": "Area",
    "slope": "Slope",
    "aridity": "Aridity",
    "snow_fraction": "Snow fraction",
    "soil_depth": "Soil depth",
    "permeability": "Permeability",
    "baseflow_index": "Baseflow index",
    "forest_fraction": "Forest fraction",
    "centroid_lat": "Area centroid latitude",
    "centroid_lng": "Area centroid longitude",
    "lat_gage": "Gauge latitude",
    "lng_gage": "Gauge longitude",
}
KEY_SIGNAL_FEATURES = {
    "NSE": ["area"],
    "KGE": ["area", "slope", "forest_fraction", "baseflow_index"],
    "FHV": ["area", "permeability", "baseflow_index", "forest_fraction"],
    "abs_FHV": ["area", "centroid_lat", "lat_gage", "snow_fraction"],
    "Peak_Timing": ["aridity", "snow_fraction", "centroid_lat", "lat_gage", "area"],
    "Peak_MAPE": ["area", "centroid_lat", "snow_fraction", "aridity"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot interpretation charts for primary metric-attribute outlier robustness."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--top-outlier-basins", type=int, default=12)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def read_inputs(input_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    robustness = pd.read_csv(input_dir / "primary_metric_attribute_outlier_robustness_spearman.csv")
    summary = pd.read_csv(input_dir / "primary_metric_attribute_outlier_robustness_summary.csv")
    outliers = pd.read_csv(
        input_dir / "primary_metric_attribute_iqr_outlier_basin_summary.csv",
        dtype={"basin": str},
    )
    return robustness, summary, outliers


def save_significance_retention(summary: pd.DataFrame, output_path: Path) -> None:
    full_sig = summary[summary["full_q_fdr"] < 0.05].copy()
    rows = []
    for metric in METRIC_ORDER:
        metric_rows = full_sig[full_sig["metric"].eq(metric)]
        for scenario in SCENARIOS[1:]:
            sub = metric_rows[metric_rows["scenario"].eq(scenario)]
            rows.append(
                {
                    "metric": metric,
                    "scenario": scenario,
                    "kept": int(sub["scenario_significant_q05"].sum()),
                    "lost": int(sub["lost_q05_after_filter"].sum()),
                    "total": int(len(sub)),
                }
            )
    frame = pd.DataFrame(rows)

    fig, axes = plt.subplots(1, 3, figsize=(15.4, 4.8), sharey=True)
    y = np.arange(len(METRIC_ORDER))
    for ax, scenario in zip(axes, SCENARIOS[1:], strict=True):
        sub = frame[frame["scenario"].eq(scenario)].set_index("metric").reindex(METRIC_ORDER)
        kept = sub["kept"].fillna(0).to_numpy()
        lost = sub["lost"].fillna(0).to_numpy()
        ax.barh(y, kept, color="#059669", label="Kept q<0.05")
        ax.barh(y, lost, left=kept, color="#dc2626", label="Lost q<0.05")
        for i, (k, l) in enumerate(zip(kept, lost, strict=True)):
            total = int(k + l)
            if total:
                ax.text(k + l + 0.25, i, f"{int(k)}/{total}", va="center", fontsize=9)
        ax.set_title(SCENARIO_LABELS[scenario])
        ax.set_xlabel("Full-significant model/seed/feature pairs")
        ax.grid(True, axis="x", color="#e5e7eb", linewidth=0.7)
        if ax is axes[0]:
            ax.set_yticks(y, [METRIC_LABELS[m] for m in METRIC_ORDER])
        else:
            ax.set_yticks(y, [])
    axes[0].legend(loc="lower right", frameon=False)
    fig.suptitle("Which full-sample correlations survive robustness filters?")
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def select_key_rows(robustness: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for metric, features in KEY_SIGNAL_FEATURES.items():
        for feature in features:
            sub = robustness[
                robustness["metric"].eq(metric)
                & robustness["feature"].eq(feature)
            ].copy()
            if sub.empty:
                continue
            full = sub[sub["scenario"].eq("full")].copy()
            # Keep the strongest seed/model target for this metric-feature pair.
            selected = full.sort_values(["q_fdr", "abs_rho"], ascending=[True, False]).head(2)
            rows.append(sub.merge(selected[["target"]].drop_duplicates(), on="target", how="inner"))
    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows, ignore_index=True)
    return out.drop_duplicates(["metric", "feature", "target", "scenario"])


def save_key_signal_robustness(robustness: pd.DataFrame, output_path: Path) -> None:
    selected = select_key_rows(robustness)
    if selected.empty:
        return

    panels = []
    for metric in METRIC_ORDER:
        sub = selected[selected["metric"].eq(metric)].copy()
        if not sub.empty:
            panels.append((metric, sub))
    n = len(panels)
    n_cols = 2
    n_rows = math.ceil(n / n_cols)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(14.5, 4.4 * n_rows), squeeze=False)
    axes_flat = axes.ravel()

    x = np.arange(len(SCENARIOS))
    for ax, (metric, sub) in zip(axes_flat, panels, strict=False):
        for (target, feature), group in sub.groupby(["target", "feature"], sort=True):
            group = group.set_index("scenario").reindex(SCENARIOS).reset_index()
            label = f"{target.replace('_seed', ' s')} - {FEATURE_LABELS.get(feature, feature)}"
            ax.plot(
                x,
                group["rho"],
                marker="o",
                linewidth=1.6,
                label=label,
                alpha=0.9,
            )
            for idx, row in group.iterrows():
                if bool(row.get("q_fdr", np.nan) < 0.05):
                    ax.scatter(idx, row["rho"], s=60, facecolors="none", edgecolors="#111827", linewidths=1.2)
        ax.axhline(0, color="#6b7280", linewidth=0.9)
        ax.set_xticks(x, [SCENARIO_LABELS[s] for s in SCENARIOS], rotation=20, ha="right")
        ax.set_ylim(-1, 1)
        ax.set_title(METRIC_LABELS.get(metric, metric))
        ax.set_ylabel("Spearman rho")
        ax.grid(True, axis="y", color="#e5e7eb", linewidth=0.7)
        ax.legend(fontsize=7, frameon=False, loc="best")

    for ax in axes_flat[n:]:
        ax.axis("off")
    fig.suptitle("Key attribute correlations: full sample vs robustness filters")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def save_outlier_basin_records(outliers: pd.DataFrame, output_path: Path, top_n: int) -> None:
    counts = (
        outliers.groupby(["basin", "gauge_name", "area", "area_lt_50", "hydromod_risk"], dropna=False)
        .agg(
            outlier_records=("outlier_records", "sum"),
            metrics=("metric", lambda values: " ".join(sorted(set(map(str, values))))),
            obs_cv=("obs_cv", "first"),
            obs_variance_denominator=("obs_variance_denominator", "first"),
        )
        .reset_index()
        .sort_values(["outlier_records", "area"], ascending=[False, True])
        .head(top_n)
    )
    counts = counts.sort_values("outlier_records", ascending=True)

    colors = np.where(counts["area_lt_50"].astype(bool), "#dc2626", "#2563eb")
    labels = [f"{row.basin}\n{row.gauge_name[:26]}" for row in counts.itertuples()]
    fig, ax = plt.subplots(figsize=(11.8, max(5.2, 0.55 * len(counts))))
    ax.barh(np.arange(len(counts)), counts["outlier_records"], color=colors)
    ax.set_yticks(np.arange(len(counts)), labels)
    ax.set_xlabel("Primary IQR outlier records across metrics/models/seeds")
    ax.set_title("Repeated outlier basins driving metric robustness checks")
    ax.grid(True, axis="x", color="#e5e7eb", linewidth=0.7)
    for i, row in enumerate(counts.itertuples()):
        hyd = "hydromod" if bool(row.hydromod_risk) else "natural-ish"
        ax.text(row.outlier_records + 0.6, i, f"area={row.area:.1f}, {hyd}", va="center", fontsize=8)
    legend_handles = [
        plt.Line2D([0], [0], marker="s", linestyle="", color="#dc2626", markersize=9, label="Area < 50"),
        plt.Line2D([0], [0], marker="s", linestyle="", color="#2563eb", markersize=9, label="Area >= 50"),
    ]
    ax.legend(handles=legend_handles, frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def save_outlier_context(outliers: pd.DataFrame, output_path: Path) -> None:
    counts = (
        outliers.groupby(["basin", "gauge_name", "area", "area_lt_50", "hydromod_risk"], dropna=False)
        .agg(
            outlier_records=("outlier_records", "sum"),
            obs_cv=("obs_cv", "first"),
            obs_variance_denominator=("obs_variance_denominator", "first"),
            q99_event_frequency=("q99_event_frequency", "first"),
            rbi=("rbi", "first"),
        )
        .reset_index()
    )
    counts["log10_area"] = np.log10(pd.to_numeric(counts["area"], errors="coerce"))
    counts["log10_obs_variance_denominator"] = np.log10(
        pd.to_numeric(counts["obs_variance_denominator"], errors="coerce")
    )

    fig, axes = plt.subplots(1, 2, figsize=(13.4, 5.1))
    color = np.where(counts["area_lt_50"].astype(bool), "#dc2626", "#2563eb")
    size = 35 + counts["outlier_records"].to_numpy() * 7

    axes[0].scatter(
        counts["log10_area"],
        counts["log10_obs_variance_denominator"],
        s=size,
        c=color,
        alpha=0.76,
        edgecolors="#111827",
        linewidths=0.35,
    )
    axes[0].set_xlabel("log10(Area)")
    axes[0].set_ylabel("log10(NSE denominator)")
    axes[0].set_title("Outlier basins: area vs observed-flow variance")
    axes[0].grid(True, color="#e5e7eb", linewidth=0.7)

    axes[1].scatter(
        counts["obs_cv"],
        counts["q99_event_frequency"],
        s=size,
        c=color,
        alpha=0.76,
        edgecolors="#111827",
        linewidths=0.35,
    )
    axes[1].set_xlabel("Observed streamflow CV")
    axes[1].set_ylabel("Q99 event frequency")
    axes[1].set_title("Outlier basins: flashy/event-response context")
    axes[1].grid(True, color="#e5e7eb", linewidth=0.7)

    for ax in axes:
        for row in counts.sort_values("outlier_records", ascending=False).head(5).itertuples():
            if ax is axes[0]:
                x, y = row.log10_area, row.log10_obs_variance_denominator
            else:
                x, y = row.obs_cv, row.q99_event_frequency
            ax.annotate(row.basin, (x, y), xytext=(4, 3), textcoords="offset points", fontsize=7)

    legend_handles = [
        plt.Line2D([0], [0], marker="o", linestyle="", color="#dc2626", markersize=8, label="Area < 50"),
        plt.Line2D([0], [0], marker="o", linestyle="", color="#2563eb", markersize=8, label="Area >= 50"),
    ]
    axes[1].legend(handles=legend_handles, frameon=False, loc="best")
    fig.suptitle("Primary outlier basins are mostly small, low-variance or flashy basins")
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    args = parse_args()
    input_dir = resolve(args.input_dir)
    output_dir = resolve(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    robustness, summary, outliers = read_inputs(input_dir)
    charts = {
        "significance_retention": output_dir / "robustness_significance_retention_by_metric.png",
        "key_signal_rho": output_dir / "robustness_key_signal_rho_by_scenario.png",
        "outlier_basin_records": output_dir / "robustness_repeated_outlier_basins.png",
        "outlier_context": output_dir / "robustness_outlier_context.png",
    }

    save_significance_retention(summary, charts["significance_retention"])
    save_key_signal_robustness(robustness, charts["key_signal_rho"])
    save_outlier_basin_records(outliers, charts["outlier_basin_records"], args.top_outlier_basins)
    save_outlier_context(outliers, charts["outlier_context"])

    manifest = pd.DataFrame(
        [{"chart": name, "path": relative(path)} for name, path in charts.items()]
    )
    manifest_path = output_dir / "robustness_chart_manifest.csv"
    manifest.to_csv(manifest_path, index=False)

    metadata = {
        "input_dir": relative(input_dir),
        "output_dir": relative(output_dir),
        "charts": {name: relative(path) for name, path in charts.items()},
        "manifest": relative(manifest_path),
        "notes": {
            "significance_retention": "Counts full-sample q<0.05 model/seed/feature pairs that remain q<0.05 after each filter.",
            "key_signal_rho": "Lines show selected model/seed/feature rho across robustness scenarios; open markers indicate q<0.05.",
            "outlier_records": "Primary IQR outlier records summarized by basin; red bars indicate area < 50.",
            "outlier_context": "Point size is repeated outlier records; red points indicate area < 50.",
        },
    }
    metadata_path = output_dir / "robustness_chart_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Wrote robustness interpretation charts to {output_dir}")
    print(f"Wrote manifest: {manifest_path}")


if __name__ == "__main__":
    main()
