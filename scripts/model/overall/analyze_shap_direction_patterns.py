#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=2.0",
#   "pandas>=2.2",
# ]
# ///
"""Build direction-focused SHAP analysis tables, figures, and report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from shap_direction_core import (
    FORCING_COLUMNS,
    MATRIX_COLUMNS,
    STATIC_FEATURES,
    build_direction_event_feature_matrix,
    build_quadrant_summary,
    build_type_candidates,
    normalize_basin_id,
    read_csv,
    sign_entropy,
    outlier_share,
)
from shap_direction_report import write_report

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/shap/direction"
SCOPE_DIRS = {
    "q99": REPO_ROOT / "output/model_analysis/shap/q99",
    "test_split": REPO_ROOT / "output/model_analysis/shap/test_split",
}
STATIC_CSV = REPO_ROOT / "data/CAMELSH_generic/drbc_expanded_observed_test/attributes/static_attributes.csv"
FORCING_CSV = REPO_ROOT / "output/model_analysis/q99_analysis/causes/tables/q99_event_forcing_drivers.csv"
QUANTILES = ["q50", "q90", "q95", "q99"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build SHAP direction analysis outputs.")
    parser.add_argument("--scope", choices=["q99", "test_split", "both"], default="both")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--top-n", type=int, default=10)
    return parser.parse_args()


def selected_scopes(scope: str) -> list[str]:
    return ["q99", "test_split"] if scope == "both" else [scope]


def read_event_shap(scopes: list[str]) -> pd.DataFrame:
    frames = []
    for scope in scopes:
        for path in sorted((SCOPE_DIRS[scope] / "tables").glob("quantile_lstm_direct_shap_event_feature_importance_seed*.csv")):
            suffix = path.stem.rsplit("seed", 1)[-1]
            if not suffix.isdigit():
                continue
            frame = read_csv(path)
            frame["scope"] = scope
            frames.append(frame)
    if not frames:
        raise FileNotFoundError("No event SHAP seed tables found")
    return pd.concat(frames, ignore_index=True)


def dry_run(scopes: list[str]) -> None:
    event = read_event_shap(scopes)
    print("scope rows events seeds quantiles")
    for scope, group in event.groupby("scope"):
        events = group[["seed", "basin", "event_id"]].drop_duplicates().shape[0]
        print(scope, len(group), events, sorted(group["seed"].unique()), sorted(group["quantile"].unique()))
    print("static", len(read_csv(STATIC_CSV)), STATIC_CSV.relative_to(REPO_ROOT))
    print("forcing", len(read_csv(FORCING_CSV)), FORCING_CSV.relative_to(REPO_ROOT))


def build_scope_summary(matrix: pd.DataFrame) -> pd.DataFrame:
    summary = matrix.groupby(["scope", "quantile", "feature_group", "feature"], as_index=False).agg(
        mean_abs_shap_mean=("mean_abs_shap", "mean"),
        mean_signed_shap_mean=("mean_signed_shap", "mean"),
        max_abs_shap_max=("max_abs_shap", "max"),
        n_seeds=("seed", "nunique"),
    )
    summary["source_sample_definition"] = np.where(summary["scope"].eq("q99"), "q99 extreme peak events", "test split flow-stratified anchors")
    return summary.sort_values(["scope", "quantile", "mean_abs_shap_mean"], ascending=[True, True, False])


def build_flow_summary(matrix: pd.DataFrame) -> pd.DataFrame:
    flow = matrix.copy()
    if "flow_stratum" not in flow.columns:
        flow["flow_stratum"] = "not_available"
    return flow.groupby(["scope", "flow_stratum", "quantile", "feature"], as_index=False).agg(
        n_rows=("feature", "size"),
        n_seeds=("seed", "nunique"),
        median_abs_shap=("mean_abs_shap", "median"),
        median_signed_shap=("mean_signed_shap", "median"),
    )


def _rainfall_regime(row: pd.Series, medians: pd.Series) -> str:
    total = row.get("event_forcing_summary_total_rainf", np.nan)
    peak = row.get("event_forcing_summary_peak_rainf_intensity", np.nan)
    duration = row.get("event_forcing_summary_duration_h", np.nan)
    antecedent = row.get("event_forcing_summary_antecedent_rainf_5d", np.nan)
    cape = row.get("event_forcing_summary_max_cape", np.nan)
    tair = row.get("event_forcing_summary_antecedent_tair_mean", np.nan)
    if pd.notna(duration) and duration >= max(24, medians.get("event_forcing_summary_duration_h", 24)):
        return "long_duration"
    if pd.notna(total) and total > 0 and pd.notna(peak) and peak / total >= 0.2:
        return "short_intense"
    if pd.notna(antecedent) and antecedent >= medians.get("event_forcing_summary_antecedent_rainf_5d", np.inf):
        return "antecedent_wet"
    if pd.notna(cape) and cape >= medians.get("event_forcing_summary_max_cape", np.inf):
        return "convective_cape"
    if pd.notna(tair) and tair <= 1.0:
        return "cold_or_snow_sensitive"
    return "unclassified"


def build_rainfall_regime_summary(matrix: pd.DataFrame) -> pd.DataFrame:
    q99 = matrix[matrix["scope"].eq("q99") & matrix["event_forcing_scope"].eq("q99_matched")].copy()
    if q99.empty:
        return pd.DataFrame(columns=["scope", "rainfall_regime", "quantile", "feature", "n_rows", "n_seeds", "median_abs_shap", "median_signed_shap", "median_signed_shap_delta_from_feature_median", "median_signed_shap_delta_scaled"])
    medians = q99[list(FORCING_COLUMNS.values())].median(numeric_only=True)
    q99["rainfall_regime"] = q99.apply(lambda row: _rainfall_regime(row, medians), axis=1)
    summary = q99.groupby(["scope", "rainfall_regime", "quantile", "feature"], as_index=False).agg(
        n_rows=("feature", "size"),
        n_seeds=("seed", "nunique"),
        median_abs_shap=("mean_abs_shap", "median"),
        median_signed_shap=("mean_signed_shap", "median"),
    )
    feature_median = summary.groupby(["scope", "quantile", "feature"])["median_signed_shap"].transform("median")
    summary["median_signed_shap_delta_from_feature_median"] = summary["median_signed_shap"] - feature_median
    max_abs_delta = summary.groupby(["scope", "quantile", "feature"])["median_signed_shap_delta_from_feature_median"].transform(lambda values: values.abs().max())
    summary["median_signed_shap_delta_scaled"] = np.where(max_abs_delta.gt(0), summary["median_signed_shap_delta_from_feature_median"] / max_abs_delta, 0.0)
    return summary


def build_seed_stability(matrix: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for keys, group in matrix.groupby(["scope", "quantile", "feature", "seed"]):
        pos = float(group["shap_sign"].eq("positive").mean())
        neg = float(group["shap_sign"].eq("negative").mean())
        rows.append({"scope": keys[0], "quantile": keys[1], "feature": keys[2], "seed": keys[3], "positive_fraction": pos, "negative_fraction": neg, "dominant_sign": "positive" if pos >= neg else "negative"})
    return pd.DataFrame(rows)


def plot_bar(summary: pd.DataFrame, out: Path, *, signed: bool) -> None:
    df = summary[summary["quantile"].eq("q99")].copy()
    if signed:
        q99_df = df[df["scope"].eq("q99")].sort_values("mean_abs_shap_mean", ascending=False).head(12)
        features = q99_df["feature"].tolist()
        ts_df = df[df["scope"].eq("test_split")].set_index("feature")
        q99_vals = q99_df["mean_signed_shap_mean"].values
        ts_vals = np.array([float(ts_df.loc[f, "mean_signed_shap_mean"]) if f in ts_df.index else 0.0 for f in features])

        y = np.arange(len(features))
        h = 0.35
        fig, ax = plt.subplots(figsize=(8, 5.5))

        for i, (qv, tv) in enumerate(zip(q99_vals, ts_vals)):
            ax.barh(y[i] + h / 2, qv, height=h,
                    color="#d62728" if qv >= 0 else "#1f77b4",
                    alpha=0.92, edgecolor="white", linewidth=0.5)
            ax.barh(y[i] - h / 2, tv, height=h,
                    color="#ff9896" if tv >= 0 else "#aec7e8",
                    alpha=0.92, edgecolor="white", linewidth=0.5)

        ax.set_yticks(y)
        ax.set_yticklabels(features)
        ax.axvline(0, color="#333333", linewidth=0.8)
        ax.set_xlabel("Mean signed SHAP value")
        ax.set_title("Signed SHAP direction — q99 events vs full test period")
        legend_handles = [
            Patch(facecolor="#d62728", label="q99 — positive (raises q99)"),
            Patch(facecolor="#1f77b4", label="q99 — negative (lowers q99)"),
            Patch(facecolor="#ff9896", label="test_split — positive"),
            Patch(facecolor="#aec7e8", label="test_split — negative"),
        ]
        ax.legend(handles=legend_handles, loc="upper right", fontsize=7.5, framealpha=0.9)
    else:
        q99_df = df[df["scope"].eq("q99")].sort_values("mean_abs_shap_mean", ascending=False).head(10)
        features = q99_df["feature"].tolist()
        ts_df = df[df["scope"].eq("test_split")].set_index("feature")
        q99_vals = q99_df["mean_abs_shap_mean"].values
        ts_vals = np.array([float(ts_df.loc[f, "mean_abs_shap_mean"]) if f in ts_df.index else 0.0 for f in features])
        y = np.arange(len(features))
        h = 0.35
        fig, ax = plt.subplots(figsize=(8, 5.2))
        ax.barh(y + h / 2, q99_vals, height=h, color="#1f77b4", alpha=0.88, label="q99 events", edgecolor="white", linewidth=0.5)
        ax.barh(y - h / 2, ts_vals, height=h, color="#aec7e8", alpha=0.88, label="test_split", edgecolor="white", linewidth=0.5)
        ax.set_yticks(y, features)
        ax.set_xlabel("Mean |SHAP|")
        ax.set_title("Feature importance: q99 events vs full test period")
        ax.legend(loc="lower right", fontsize=9, framealpha=0.9)
    ax.grid(axis="x", alpha=0.3, linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out, dpi=220, facecolor="white")
    plt.close(fig)


def plot_heatmap(table: pd.DataFrame, out: Path, value: str, title: str, index: str, *, cmap: str = "coolwarm", center_zero: bool = True) -> None:
    if table.empty:
        table = pd.DataFrame({index: ["none"], "feature": ["none"], value: [0.0]})
    pivot = table.pivot_table(index=index, columns="feature", values=value, aggfunc="median", fill_value=0.0)
    fig, ax = plt.subplots(figsize=(max(7, 0.45 * len(pivot.columns)), max(3.8, 0.45 * len(pivot.index))))
    values = pivot.to_numpy(dtype=float)
    norm = None
    if center_zero:
        vmax = float(np.nanmax(np.abs(values))) if values.size else 1.0
        vmax = vmax if vmax > 0 else 1.0
        norm = mcolors.TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
    im = ax.imshow(values, aspect="auto", cmap=cmap, norm=norm)
    ax.set_xticks(range(len(pivot.columns)), pivot.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(pivot.index)), pivot.index)
    ax.set_title(title)
    fig.colorbar(im, ax=ax, label=value)
    fig.tight_layout()
    fig.savefig(out, dpi=220)
    plt.close(fig)


def plot_heatmap_seeds(
    matrix: pd.DataFrame,
    out: Path,
    *,
    plot_type: str,
    value: str,
    title_prefix: str,
    index: str,
    cmap: str = "coolwarm",
    center_zero: bool = True,
    features: list[str] | None = None,
) -> None:
    """Generate a per-seed facet heatmap (one column per seed, shared color scale).

    features: if given, restrict pivot columns to this ordered list.
    """
    seeds = sorted(matrix["seed"].unique())
    n_cols = len(features) if features else matrix["feature"].nunique()
    fig_w = max(4.0, 0.55 * n_cols + 1.5)
    fig_h = max(3.8, 0.45 * 6)
    fig, axes = plt.subplots(1, len(seeds), figsize=(fig_w * len(seeds), fig_h), sharey=True, layout="constrained")
    if len(seeds) == 1:
        axes = [axes]

    pivots: list[pd.DataFrame] = []
    for seed in seeds:
        seed_matrix = matrix[matrix["seed"].eq(seed)]
        if plot_type == "quadrant":
            summary = build_quadrant_summary(seed_matrix)
            table = summary[summary["quantile"].eq("q99")]
        else:
            summary = build_rainfall_regime_summary(seed_matrix)
            table = summary[summary["quantile"].astype(str).eq("q99")]
        pivot = table.pivot_table(index=index, columns="feature", values=value, aggfunc="median", fill_value=0.0)
        if features:
            keep = [f for f in features if f in pivot.columns]
            pivot = pivot[keep]
        pivots.append(pivot)

    all_values = [p.to_numpy(dtype=float) for p in pivots if p.size]
    if center_zero:
        vmax = max((float(np.nanmax(np.abs(v))) for v in all_values), default=1.0)
        vmax = vmax if vmax > 0 else 1.0
        norm = mcolors.TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
    else:
        vmin = min((float(np.nanmin(v)) for v in all_values), default=0.0)
        vmax = max((float(np.nanmax(v)) for v in all_values), default=1.0)
        norm = plt.Normalize(vmin=vmin, vmax=vmax)

    im = None
    for ax, seed, pivot in zip(axes, seeds, pivots):
        values = pivot.to_numpy(dtype=float)
        im = ax.imshow(values, aspect="auto", cmap=cmap, norm=norm)
        ax.set_xticks(range(len(pivot.columns)), list(pivot.columns), rotation=45, ha="right", fontsize=7)
        ax.set_yticks(range(len(pivot.index)), list(pivot.index), fontsize=7)
        ax.set_title(f"seed {int(seed)}", fontsize=9)

    fig.suptitle(title_prefix, fontsize=10)
    if im is not None:
        fig.colorbar(im, ax=axes, label=value, fraction=0.02, pad=0.02)
    fig.savefig(out, dpi=220)
    plt.close(fig)


def write_readmes(out_dir: Path) -> None:
    (out_dir / "README.md").write_text(
        "# SHAP 방향성 분석\n\n`test_split`과 `q99` SHAP bar/signed bar/beeswarm 해석을 분리하고, q99 중심의 static attribute 방향성·강우 regime·seed 안정성을 요약한다.\n\nSource paths are recorded in `data/direction_manifest.json`.\n",
        encoding="utf-8",
    )


def write_manifest(out_dir: Path, matrix: pd.DataFrame, issues: pd.DataFrame, args: argparse.Namespace) -> None:
    manifest = {"sources": {"static": str(STATIC_CSV.relative_to(REPO_ROOT)), "forcing": str(FORCING_CSV.relative_to(REPO_ROOT)), "shap_scopes": {key: str(value.relative_to(REPO_ROOT)) for key, value in SCOPE_DIRS.items()}}, "row_counts": {"matrix": int(len(matrix)), "merge_issues": int(len(issues))}, "columns": MATRIX_COLUMNS, "thresholds": {"min_events_for_type": 20, "max_outlier_share": 0.4}, "interpretation_boundary": "SHAP explains model outputs, not observed causal mechanisms.", "args": {key: str(value) for key, value in vars(args).items()}}
    (out_dir / "data" / "direction_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    scopes = selected_scopes(args.scope)
    if args.dry_run:
        dry_run(scopes)
        return 0
    out_dir = args.output_dir
    for sub in ["tables", "figures", "report", "data"]:
        (out_dir / sub).mkdir(parents=True, exist_ok=True)
    event = read_event_shap(scopes)
    matrix, issues = build_direction_event_feature_matrix(event_shap=event, static_attributes=read_csv(STATIC_CSV), q99_forcing=read_csv(FORCING_CSV))
    scope_summary = build_scope_summary(matrix)
    quadrant = build_quadrant_summary(matrix)
    flow = build_flow_summary(matrix)
    rainfall = build_rainfall_regime_summary(matrix)
    seed = build_seed_stability(matrix)
    candidates = build_type_candidates(quadrant[quadrant["scope"].eq("q99") & quadrant["quantile"].eq("q99")])
    outputs = {"direction_event_feature_matrix.csv": matrix, "direction_merge_issues.csv": issues, "direction_scope_summary.csv": scope_summary, "direction_quadrant_summary.csv": quadrant, "direction_by_flow_stratum.csv": flow, "direction_by_rainfall_regime.csv": rainfall, "direction_seed_stability.csv": seed, "direction_type_candidates.csv": candidates}
    for name, frame in outputs.items():
        frame.to_csv(out_dir / "tables" / name, index=False)
    plot_bar(scope_summary, out_dir / "figures" / "bar_importance_scope_compare.png", signed=False)
    plot_bar(scope_summary, out_dir / "figures" / "signed_bar_direction_scope_compare.png", signed=True)
    plot_heatmap(quadrant[quadrant["quantile"].eq("q99")], out_dir / "figures" / "quadrant_heatmap_q99.png", "median_signed_shap", "q99 Quadrant Signed SHAP", "quadrant_label")
    plot_heatmap(rainfall[rainfall["quantile"].eq("q99")], out_dir / "figures" / "rainfall_regime_direction_heatmap_q99.png", "median_signed_shap_delta_scaled", "q99 Rainfall Regime Signed SHAP Deviation", "rainfall_regime")
    plot_heatmap(quadrant[quadrant["quantile"].eq("q99")], out_dir / "figures" / "beeswarm_interpretation_grid_q99.png", "event_share", "q99 Quadrant Event Share", "quadrant_label", cmap="viridis", center_zero=False)
    _quad_features = ["area", "slope", "forest_fraction", "soil_depth", "permeability", "snow_fraction", "baseflow_index"]
    _rain_features = ["area", "slope", "soil_depth", "permeability", "forest_fraction", "Rainf"]
    plot_heatmap_seeds(matrix, out_dir / "figures" / "beeswarm_interpretation_grid_q99_by_seed.png", plot_type="quadrant", value="event_share", title_prefix="q99 Quadrant Event Share (per seed)", index="quadrant_label", cmap="viridis", center_zero=False, features=_quad_features)
    plot_heatmap_seeds(matrix, out_dir / "figures" / "quadrant_heatmap_q99_by_seed.png", plot_type="quadrant", value="median_signed_shap", title_prefix="q99 Quadrant Signed SHAP (per seed)", index="quadrant_label", features=_quad_features)
    plot_heatmap_seeds(matrix, out_dir / "figures" / "rainfall_regime_direction_heatmap_q99_by_seed.png", plot_type="rainfall", value="median_signed_shap_delta_scaled", title_prefix="q99 Rainfall Regime SHAP Deviation (per seed)", index="rainfall_regime", features=_rain_features)
    write_report(out_dir, scope_summary, quadrant, rainfall, seed, matrix, issues)
    write_readmes(out_dir)
    write_manifest(out_dir, matrix, issues, args)
    print(f"wrote SHAP direction analysis to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
