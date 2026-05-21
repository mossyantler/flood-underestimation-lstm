#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/paper_result_assets"
PREDICTOR_ORDER = ["q50", "q90", "q95", "q99"]
PREDICTOR_LABELS = {
    "q50": "Model 2 q50",
    "q90": "Model 2 q90",
    "q95": "Model 2 q95",
    "q99": "Model 2 q99",
}
STRATUM_LABELS = {
    "basin_top1": "Q99 exceedance",
    "basin_top0_1": "Q99.9 exceedance",
    "observed_peak_hour": "Observed peak hour",
}
REGIME_ORDER = ["Recent rainfall", "Antecedent / multi-day rain", "Weak / low-signal hydromet regime"]
REGIME_COLORS = {
    "Recent rainfall": "#2563eb",
    "Antecedent / multi-day rain": "#059669",
    "Weak / low-signal hydromet regime": "#d97706",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build compact paper-ready tables and figures from existing subset300 analysis outputs."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _write_markdown_table(df: pd.DataFrame, path: Path) -> None:
    path.write_text(_to_markdown(df) + "\n", encoding="utf-8")


def _to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    table = df.copy()
    for col in table.columns:
        if pd.api.types.is_float_dtype(table[col]):
            table[col] = table[col].map(lambda value: "" if pd.isna(value) else f"{value:.3f}")
        else:
            table[col] = table[col].map(lambda value: "" if pd.isna(value) else str(value))
    headers = [str(col) for col in table.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for _, row in table.iterrows():
        lines.append("| " + " | ".join(str(row[col]) for col in table.columns) + " |")
    return "\n".join(lines)


def build_high_flow_compact_table(output_dir: Path) -> pd.DataFrame:
    source = REPO_ROOT / "output/model_analysis/quantile_analysis/analysis/flow_strata_predictor_aggregate.csv"
    df = pd.read_csv(source)
    keep_predictors = ["Model 1", "Model 2 q50", "Model 2 q95", "Model 2 q99"]
    table = df[
        df["comparison"].eq("primary")
        & df["stratum"].isin(STRATUM_LABELS)
        & df["predictor"].isin(keep_predictors)
    ].copy()
    table["stratum_label"] = table["stratum"].map(STRATUM_LABELS)
    table["predictor_order"] = table["predictor"].map({name: idx for idx, name in enumerate(keep_predictors)})
    table["stratum_order"] = table["stratum"].map({name: idx for idx, name in enumerate(STRATUM_LABELS)})
    table = table.sort_values(["stratum_order", "predictor_order"])
    compact = table[
        [
            "stratum_label",
            "predictor",
            "n_summaries",
            "median_underestimation_fraction",
            "median_median_rel_bias_pct",
            "median_median_abs_error",
        ]
    ].rename(
        columns={
            "stratum_label": "stratum",
            "median_underestimation_fraction": "median_underestimation_fraction",
            "median_median_rel_bias_pct": "median_relative_bias_pct",
            "median_median_abs_error": "median_absolute_error",
        }
    )
    path = output_dir / "tables" / "primary_high_flow_peak_compact.csv"
    compact.to_csv(path, index=False)
    _write_markdown_table(compact.round(3), path.with_suffix(".md"))
    return compact


def save_event_regime_figure(output_dir: Path) -> pd.DataFrame:
    source = REPO_ROOT / "output/model_analysis/quantile_analysis/event_regime_analysis/paired_delta_aggregate.csv"
    df = pd.read_csv(source)
    data = df[df["stratification"].eq("ml_event_regime") & df["predictor"].isin(PREDICTOR_ORDER)].copy()
    data["predictor"] = pd.Categorical(data["predictor"], categories=PREDICTOR_ORDER, ordered=True)
    data["stratum"] = pd.Categorical(data["stratum"], categories=REGIME_ORDER, ordered=True)
    data = data.sort_values(["stratum", "predictor"])

    metrics = [
        (
            "seed_mean_median_paired_under_deficit_reduction_pct",
            "Peak under-deficit reduction (pp)",
            "Higher is better",
        ),
        ("seed_mean_mean_threshold_recall_delta", "Threshold recall delta", "Higher is better"),
        ("seed_mean_median_event_nrmse_pct_delta", "Event NRMSE delta (%)", "Lower is better"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.4))
    x = np.arange(len(PREDICTOR_ORDER))
    for ax, (col, ylabel, subtitle) in zip(axes, metrics, strict=True):
        for regime in REGIME_ORDER:
            group = data[data["stratum"].eq(regime)].sort_values("predictor")
            if group.empty:
                continue
            ax.plot(
                x,
                group[col],
                marker="o",
                linewidth=1.8,
                color=REGIME_COLORS.get(regime),
                label=regime,
            )
        ax.axhline(0, color="#4b5563", linestyle="--", linewidth=1.0)
        ax.set_xticks(x)
        ax.set_xticklabels(PREDICTOR_ORDER)
        ax.set_ylabel(ylabel)
        ax.set_title(subtitle, fontsize=10)
        ax.grid(True, axis="y", color="#e5e7eb", linewidth=0.7)
    axes[0].legend(frameon=False, fontsize=8, loc="best")
    fig.suptitle("Event-regime paired deltas relative to Model 1", y=1.03, fontsize=12)
    fig.tight_layout()
    path = output_dir / "figures" / "event_regime_paired_delta_compact.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    data.to_csv(output_dir / "tables" / "event_regime_paired_delta_compact.csv", index=False)
    return data


def _box_primary_panel(ax: plt.Axes, values: pd.Series, primary_value: float, title: str, ylabel: str) -> None:
    clean = values.dropna().to_numpy()
    ax.boxplot(
        [clean],
        widths=0.42,
        showmeans=True,
        patch_artist=True,
        medianprops={"color": "#111827", "linewidth": 1.5},
        meanprops={
            "marker": "o",
            "markerfacecolor": "#2563eb",
            "markeredgecolor": "#1e3a8a",
            "markersize": 4.8,
        },
        boxprops={"facecolor": "#dbeafe", "edgecolor": "#1f2937", "linewidth": 0.9},
        whiskerprops={"color": "#1f2937", "linewidth": 0.9},
        capprops={"color": "#1f2937", "linewidth": 0.9},
        flierprops={"marker": ".", "markerfacecolor": "#6b7280", "markeredgecolor": "#6b7280", "markersize": 3},
    )
    if np.isfinite(primary_value):
        ax.scatter([1], [primary_value], marker="D", s=46, color="#dc2626", label="primary")
    ax.set_xticks([1])
    ax.set_xticklabels(["all epochs"])
    ax.set_title(title, fontsize=10)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", color="#e5e7eb", linewidth=0.7)


def save_checkpoint_sensitivity_figure(output_dir: Path) -> pd.DataFrame:
    flow = pd.read_csv(REPO_ROOT / "output/model_analysis/quantile_analysis/analysis/flow_strata_predictor_summary.csv")
    gap = pd.read_csv(REPO_ROOT / "output/model_analysis/quantile_analysis/analysis/quantile_gap_summary.csv")
    stress_delta_epoch = pd.read_csv(
        REPO_ROOT / "output/model_analysis/extreme_rain/all/analysis/paired_delta_epoch_aggregate.csv"
    )
    stress_delta_primary = pd.read_csv(
        REPO_ROOT / "output/model_analysis/extreme_rain/primary/analysis/paired_delta_aggregate.csv"
    )
    stress_cohort_epoch = pd.read_csv(
        REPO_ROOT / "output/model_analysis/extreme_rain/all/analysis/cohort_epoch_predictor_aggregate.csv"
    )
    stress_cohort_primary = pd.read_csv(
        REPO_ROOT / "output/model_analysis/extreme_rain/primary/analysis/cohort_predictor_aggregate.csv"
    )

    flow_same = flow[
        flow["comparison"].eq("same_epoch")
        & flow["stratum"].eq("basin_top1")
        & flow["predictor"].eq("Model 2 q99")
    ]["underestimation_fraction"]
    flow_primary = flow[
        flow["comparison"].eq("primary")
        & flow["stratum"].eq("basin_top1")
        & flow["predictor"].eq("Model 2 q99")
    ]["underestimation_fraction"].median()

    gap_same = gap[gap["comparison"].eq("same_epoch") & gap["stratum"].eq("basin_top1")][
        "median_q99_minus_q50_pct_obs"
    ]
    gap_primary = gap[gap["comparison"].eq("primary") & gap["stratum"].eq("basin_top1")][
        "median_q99_minus_q50_pct_obs"
    ].median()

    pos_same = stress_delta_epoch[
        stress_delta_epoch["stratum"].eq("flood_response_ge25") & stress_delta_epoch["predictor"].eq("q99")
    ]["seed_mean_median_paired_under_deficit_reduction_pct"]
    pos_primary = stress_delta_primary[
        stress_delta_primary["stratum"].eq("flood_response_ge25") & stress_delta_primary["predictor"].eq("q99")
    ]["seed_mean_median_paired_under_deficit_reduction_pct"].median()

    neg_same = stress_cohort_epoch[
        stress_cohort_epoch["response_class"].eq("low_response_below_q99")
        & stress_cohort_epoch["predictor"].eq("q99")
    ]["seed_mean_median_pred_window_peak_to_flood_ari100"]
    neg_primary = stress_cohort_primary[
        stress_cohort_primary["response_class"].eq("low_response_below_q99")
        & stress_cohort_primary["predictor"].eq("q99")
    ]["seed_mean_median_pred_window_peak_to_flood_ari100"].median()

    rows = []
    specs = [
        (
            "q99_underestimation_fraction_at_q99_exceedance",
            flow_same,
            flow_primary,
            "Q99 hours underestimation",
            "Fraction",
        ),
        (
            "q99_q50_spread_pct_obs_at_q99_exceedance",
            gap_same,
            gap_primary,
            "Q99-q50 spread",
            "% of observed flow",
        ),
        (
            "stress_ge25_under_deficit_reduction_q99",
            pos_same,
            pos_primary,
            "ARI25+ stress under-deficit reduction",
            "Percentage points",
        ),
        (
            "low_response_q99_pred_peak_to_ari100",
            neg_same,
            neg_primary,
            "Low-response q99 peak / ARI100",
            "Ratio",
        ),
    ]
    for metric, values, primary, _title, _ylabel in specs:
        clean = values.dropna()
        rows.append(
            {
                "metric": metric,
                "all_epoch_n": int(len(clean)),
                "all_epoch_median": float(clean.median()),
                "all_epoch_q25": float(clean.quantile(0.25)),
                "all_epoch_q75": float(clean.quantile(0.75)),
                "all_epoch_min": float(clean.min()),
                "all_epoch_max": float(clean.max()),
                "primary_value": float(primary),
            }
        )

    fig, axes = plt.subplots(1, 4, figsize=(14.0, 4.5))
    for ax, (_metric, values, primary, title, ylabel) in zip(axes, specs, strict=True):
        _box_primary_panel(ax, values, float(primary), title, ylabel)
    axes[0].legend(frameon=False, fontsize=8, loc="best")
    fig.suptitle("Primary result relative to validation-epoch sensitivity", y=1.03, fontsize=12)
    fig.tight_layout()
    path = output_dir / "figures" / "checkpoint_sensitivity_compact.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)

    table = pd.DataFrame(rows)
    table.to_csv(output_dir / "tables" / "checkpoint_sensitivity_compact.csv", index=False)
    _write_markdown_table(table.round(3), output_dir / "tables" / "checkpoint_sensitivity_compact.md")
    return table


def select_representative_hydrograph_candidates(output_dir: Path) -> pd.DataFrame:
    peaks = pd.read_csv(REPO_ROOT / "output/model_analysis/quantile_analysis/analysis/observed_peak_predictions.csv")
    peaks = peaks[peaks["comparison"].eq("primary")].copy()
    peaks["basin"] = peaks["basin"].astype(str).str.zfill(8)
    manifest = pd.read_csv(REPO_ROOT / "output/model_analysis/quantile_analysis/hydrograph_plot_manifest.csv")
    manifest["basin"] = manifest["basin"].astype(str).str.zfill(8)
    manifest = manifest[["seed", "basin", "model2_epoch", "plot_path"]].drop_duplicates()
    peaks = peaks.merge(manifest, on=["seed", "basin", "model2_epoch"], how="left")
    peaks["q99_abs_rel_bias_pct"] = peaks["q99_rel_bias_pct"].abs()
    peaks["model1_under_deficit_pct"] = (-peaks["model1_rel_bias_pct"]).clip(lower=0)
    peaks["q99_under_deficit_pct"] = (-peaks["q99_rel_bias_pct"]).clip(lower=0)
    peaks["under_deficit_reduction_pct"] = peaks["model1_under_deficit_pct"] - peaks["q99_under_deficit_pct"]

    categories = []
    success = peaks[
        peaks["model1_underestimated"]
        & (~peaks["q99_underestimated"])
        & peaks["q99_rel_bias_pct"].between(-5, 35)
    ].copy()
    if success.empty:
        success = peaks[peaks["model1_underestimated"] & (~peaks["q99_underestimated"])].copy()
    success = success.sort_values(["q99_abs_rel_bias_pct", "under_deficit_reduction_pct"], ascending=[True, False]).head(5)
    success["candidate_type"] = "q99_success_near_peak"
    categories.append(success)

    failure = peaks[peaks["q99_underestimated"]].copy()
    failure = failure.sort_values("q99_rel_bias_pct").head(5)
    failure["candidate_type"] = "q99_still_underestimates"
    categories.append(failure)

    over = peaks[~peaks["q99_underestimated"]].copy()
    over = over.sort_values("q99_rel_bias_pct", ascending=False).head(5)
    over["candidate_type"] = "q99_overpredicts"
    categories.append(over)

    out = pd.concat(categories, ignore_index=True)
    cols = [
        "candidate_type",
        "seed",
        "basin",
        "model1_epoch",
        "model2_epoch",
        "datetime",
        "obs",
        "model1",
        "q50",
        "q95",
        "q99",
        "model1_rel_bias_pct",
        "q50_rel_bias_pct",
        "q95_rel_bias_pct",
        "q99_rel_bias_pct",
        "under_deficit_reduction_pct",
        "obs_peak_quantile_zone_label",
        "plot_path",
    ]
    out = out[cols]
    out.to_csv(output_dir / "tables" / "representative_hydrograph_candidates.csv", index=False)
    _write_markdown_table(out.round(3), output_dir / "tables" / "representative_hydrograph_candidates.md")
    return out


def write_report(
    output_dir: Path,
    high_flow: pd.DataFrame,
    checkpoint: pd.DataFrame,
    candidates: pd.DataFrame,
) -> Path:
    report_dir = output_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "paper_result_assets_report.md"
    lines = [
        "# Paper Result Assets",
        "",
        "This folder contains compact tables and figures derived from existing subset300 analysis outputs.",
        "",
        "## High-flow compact table",
        "",
        _to_markdown(high_flow.round(3)),
        "",
        "## Checkpoint sensitivity compact table",
        "",
        _to_markdown(checkpoint.round(3)),
        "",
        "## Representative hydrograph candidate counts",
        "",
        _to_markdown(candidates["candidate_type"].value_counts().rename_axis("candidate_type").reset_index(name="n")),
        "",
        "Candidate rows are starting points for figure selection; final inclusion still needs visual inspection of the linked hydrograph PNGs.",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> None:
    args = parse_args()
    output_dir = _resolve(args.output_dir)
    for child in ["figures", "tables", "report"]:
        (output_dir / child).mkdir(parents=True, exist_ok=True)

    high_flow = build_high_flow_compact_table(output_dir)
    event_regime = save_event_regime_figure(output_dir)
    checkpoint = save_checkpoint_sensitivity_figure(output_dir)
    candidates = select_representative_hydrograph_candidates(output_dir)
    report_path = write_report(output_dir, high_flow, checkpoint, candidates)

    chart_manifest = pd.DataFrame(
        [
            {
                "chart": "event_regime_paired_delta_compact",
                "path": _relative(output_dir / "figures/event_regime_paired_delta_compact.png"),
            },
            {
                "chart": "checkpoint_sensitivity_compact",
                "path": _relative(output_dir / "figures/checkpoint_sensitivity_compact.png"),
            },
        ]
    )
    chart_manifest.to_csv(output_dir / "chart_manifest.csv", index=False)

    metadata = {
        "output_dir": _relative(output_dir),
        "sources": {
            "flow_strata_predictor_aggregate": "output/model_analysis/quantile_analysis/analysis/flow_strata_predictor_aggregate.csv",
            "flow_strata_predictor_summary": "output/model_analysis/quantile_analysis/analysis/flow_strata_predictor_summary.csv",
            "quantile_gap_summary": "output/model_analysis/quantile_analysis/analysis/quantile_gap_summary.csv",
            "event_regime_paired_delta": "output/model_analysis/quantile_analysis/event_regime_analysis/paired_delta_aggregate.csv",
            "extreme_rain_all_delta_epoch": "output/model_analysis/extreme_rain/all/analysis/paired_delta_epoch_aggregate.csv",
            "extreme_rain_primary_delta": "output/model_analysis/extreme_rain/primary/analysis/paired_delta_aggregate.csv",
            "observed_peak_predictions": "output/model_analysis/quantile_analysis/analysis/observed_peak_predictions.csv",
        },
        "outputs": {
            "high_flow_compact": _relative(output_dir / "tables/primary_high_flow_peak_compact.csv"),
            "event_regime_compact": _relative(output_dir / "tables/event_regime_paired_delta_compact.csv"),
            "checkpoint_compact": _relative(output_dir / "tables/checkpoint_sensitivity_compact.csv"),
            "hydrograph_candidates": _relative(output_dir / "tables/representative_hydrograph_candidates.csv"),
            "chart_manifest": _relative(output_dir / "chart_manifest.csv"),
            "report": _relative(report_path),
        },
        "notes": [
            "Extreme-rain checkpoint sensitivity uses the original primary/all stress roots for apples-to-apples checkpoint comparison.",
            "Representative hydrograph candidates are ranked automatically and still require visual inspection before paper use.",
        ],
    }
    (output_dir / "analysis_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Wrote paper result assets to {output_dir}")
    print(f"High-flow compact rows: {len(high_flow)}")
    print(f"Event-regime rows: {len(event_regime)}")
    print(f"Hydrograph candidates: {len(candidates)}")


if __name__ == "__main__":
    main()
