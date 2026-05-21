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
DEFAULT_QUANTILE_ANALYSIS = REPO_ROOT / "output/model_analysis/quantile_analysis/analysis"
DEFAULT_STRESS_PRIMARY = REPO_ROOT / "output/model_analysis/extreme_rain/primary/analysis"
DEFAULT_STRESS_ALL = REPO_ROOT / "output/model_analysis/extreme_rain/all/analysis"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/overall_analysis/epoch_sensitivity"
EPOCHS = [5, 10, 15, 20, 25, 30]
POSITIVE_RESPONSE_CLASSES = ["flood_response_ge25", "flood_response_ge2_to_lt25"]
NEGATIVE_CONTROL_CLASS = "low_response_below_q99"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build compact checkpoint-sensitivity figure for subset300 results."
    )
    parser.add_argument("--quantile-analysis-dir", type=Path, default=DEFAULT_QUANTILE_ANALYSIS)
    parser.add_argument("--stress-primary-dir", type=Path, default=DEFAULT_STRESS_PRIMARY)
    parser.add_argument("--stress-all-dir", type=Path, default=DEFAULT_STRESS_ALL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _weighted_mean(frame: pd.DataFrame, value_col: str, weight_col: str) -> float:
    values = pd.to_numeric(frame[value_col], errors="coerce")
    weights = pd.to_numeric(frame[weight_col], errors="coerce")
    valid = values.notna() & weights.notna() & (weights > 0)
    if not valid.any():
        return float("nan")
    return float(np.average(values.loc[valid], weights=weights.loc[valid]))


def _hydrograph_underestimation(quantile_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(quantile_dir / "flow_strata_predictor_summary.csv")
    df = df[(df["stratum"] == "basin_top1") & (df["predictor"] == "Model 2 q99")].copy()
    rows = []
    for row in df.itertuples(index=False):
        source = "primary" if row.comparison == "primary" else "same_epoch"
        category = "Primary" if source == "primary" else f"{int(row.model2_epoch):03d}"
        rows.append(
            {
                "metric_id": "q99_exceedance_underestimation_fraction",
                "metric_label": "Q99-exceedance q99 underestimation fraction",
                "source": source,
                "category": category,
                "epoch": int(row.model2_epoch),
                "seed": int(row.seed),
                "value": float(row.underestimation_fraction),
                "n_rows": int(row.n_rows),
                "n_basins": int(row.n_basins),
                "direction": "lower_is_better",
            }
        )
    return pd.DataFrame(rows)


def _quantile_spread(quantile_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(quantile_dir / "quantile_gap_summary.csv")
    df = df[df["stratum"].eq("basin_top1")].copy()
    rows = []
    for row in df.itertuples(index=False):
        source = "primary" if row.comparison == "primary" else "same_epoch"
        category = "Primary" if source == "primary" else f"{int(row.model2_epoch):03d}"
        rows.append(
            {
                "metric_id": "q99_q50_spread_pct_obs",
                "metric_label": "Q99-exceedance q99-q50 spread (% obs)",
                "source": source,
                "category": category,
                "epoch": int(row.model2_epoch),
                "seed": int(row.seed),
                "value": float(row.median_q99_minus_q50_pct_obs),
                "n_rows": int(row.n_rows),
                "n_basins": int(row.n_basins),
                "direction": "context_metric",
            }
        )
    return pd.DataFrame(rows)


def _positive_response_underdeficit(stress_primary_dir: Path, stress_all_dir: Path) -> pd.DataFrame:
    rows = []
    all_df = pd.read_csv(stress_all_dir / "paired_delta_epoch_aggregate.csv")
    all_df = all_df[
        all_df["stratification"].eq("response_class")
        & all_df["stratum"].isin(POSITIVE_RESPONSE_CLASSES)
        & all_df["predictor"].eq("q99")
    ].copy()
    for epoch, group in all_df.groupby("model2_epoch", sort=True):
        rows.append(
            {
                "metric_id": "positive_response_q99_underdeficit_reduction",
                "metric_label": "Positive-response q99 under-deficit reduction",
                "source": "same_epoch",
                "category": f"{int(epoch):03d}",
                "epoch": int(epoch),
                "seed": -1,
                "value": _weighted_mean(
                    group,
                    "seed_mean_median_paired_under_deficit_reduction_pct",
                    "mean_n_events",
                ),
                "n_rows": int(group["mean_n_events"].sum()),
                "n_basins": -1,
                "direction": "higher_is_better",
            }
        )

    primary = pd.read_csv(stress_primary_dir / "paired_delta_aggregate.csv")
    primary = primary[
        primary["stratification"].eq("response_class")
        & primary["stratum"].isin(POSITIVE_RESPONSE_CLASSES)
        & primary["predictor"].eq("q99")
    ].copy()
    rows.append(
        {
            "metric_id": "positive_response_q99_underdeficit_reduction",
            "metric_label": "Positive-response q99 under-deficit reduction",
            "source": "primary",
            "category": "Primary",
            "epoch": -1,
            "seed": -1,
            "value": _weighted_mean(
                primary,
                "seed_mean_median_paired_under_deficit_reduction_pct",
                "mean_n_events",
            ),
            "n_rows": int(primary["mean_n_events"].sum()),
            "n_basins": -1,
            "direction": "higher_is_better",
        }
    )
    return pd.DataFrame(rows)


def _negative_control_false_positive(stress_primary_dir: Path, stress_all_dir: Path) -> pd.DataFrame:
    rows = []
    all_df = pd.read_csv(stress_all_dir / "cohort_epoch_predictor_aggregate.csv")
    all_df = all_df[
        all_df["response_class"].eq(NEGATIVE_CONTROL_CLASS) & all_df["predictor"].eq("q99")
    ].copy()
    for row in all_df.itertuples(index=False):
        rows.append(
            {
                "metric_id": "negative_control_q99_pred_peak_to_ari100",
                "metric_label": "Negative-control q99 pred peak / ARI100",
                "source": "same_epoch",
                "category": f"{int(row.model2_epoch):03d}",
                "epoch": int(row.model2_epoch),
                "seed": -1,
                "value": float(row.seed_mean_median_pred_window_peak_to_flood_ari100),
                "n_rows": int(row.mean_n_events),
                "n_basins": -1,
                "direction": "lower_is_safer",
            }
        )

    primary = pd.read_csv(stress_primary_dir / "cohort_predictor_aggregate.csv")
    primary = primary[
        primary["response_class"].eq(NEGATIVE_CONTROL_CLASS) & primary["predictor"].eq("q99")
    ].copy()
    if len(primary) != 1:
        raise ValueError(f"Expected one primary negative-control q99 row, found {len(primary)}")
    row = primary.iloc[0]
    rows.append(
        {
            "metric_id": "negative_control_q99_pred_peak_to_ari100",
            "metric_label": "Negative-control q99 pred peak / ARI100",
            "source": "primary",
            "category": "Primary",
            "epoch": -1,
            "seed": -1,
            "value": float(row["seed_mean_median_pred_window_peak_to_flood_ari100"]),
            "n_rows": int(row["mean_n_events"]),
            "n_basins": -1,
            "direction": "lower_is_safer",
        }
    )
    return pd.DataFrame(rows)


def _build_metrics(
    quantile_dir: Path,
    stress_primary_dir: Path,
    stress_all_dir: Path,
) -> pd.DataFrame:
    frames = [
        _hydrograph_underestimation(quantile_dir),
        _quantile_spread(quantile_dir),
        _positive_response_underdeficit(stress_primary_dir, stress_all_dir),
        _negative_control_false_positive(stress_primary_dir, stress_all_dir),
    ]
    return pd.concat(frames, ignore_index=True)


def _summary(metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (metric_id, source), group in metrics.groupby(["metric_id", "source"], sort=True):
        values = group["value"].dropna()
        row = {
            "metric_id": metric_id,
            "metric_label": group["metric_label"].iloc[0],
            "source": source,
            "n_values": int(len(values)),
            "median_value": float(values.median()) if len(values) else float("nan"),
            "min_value": float(values.min()) if len(values) else float("nan"),
            "max_value": float(values.max()) if len(values) else float("nan"),
            "direction": group["direction"].iloc[0],
        }
        rows.append(row)
    return pd.DataFrame(rows)


def _values_by_category(frame: pd.DataFrame, metric_id: str) -> tuple[list[str], list[np.ndarray]]:
    sub = frame[frame["metric_id"].eq(metric_id)].copy()
    categories = [f"{epoch:03d}" for epoch in EPOCHS] + ["Primary"]
    data = []
    for category in categories:
        values = sub.loc[sub["category"].eq(category), "value"].dropna().to_numpy(dtype=float)
        data.append(values)
    return categories, data


def _plot_box_and_points(ax: plt.Axes, metrics: pd.DataFrame, metric_id: str, title: str, ylabel: str) -> None:
    categories, data = _values_by_category(metrics, metric_id)
    positions = np.arange(1, len(categories) + 1)
    box_data = [values if len(values) else np.array([np.nan]) for values in data]
    bp = ax.boxplot(
        box_data,
        positions=positions,
        widths=0.55,
        patch_artist=True,
        showmeans=True,
        medianprops={"color": "#111827", "linewidth": 1.2},
        meanprops={
            "marker": "o",
            "markerfacecolor": "#dc2626",
            "markeredgecolor": "#7f1d1d",
            "markersize": 4,
        },
        boxprops={"facecolor": "#dbeafe", "edgecolor": "#1f2937", "linewidth": 0.8},
        whiskerprops={"color": "#1f2937", "linewidth": 0.8},
        capprops={"color": "#1f2937", "linewidth": 0.8},
        flierprops={"marker": ".", "markersize": 3, "alpha": 0.6},
    )
    for patch, category in zip(bp["boxes"], categories, strict=True):
        if category == "Primary":
            patch.set_facecolor("#fee2e2")
            patch.set_edgecolor("#991b1b")
    for pos, values in zip(positions, data, strict=True):
        if len(values) == 0:
            continue
        jitter = np.linspace(-0.08, 0.08, len(values)) if len(values) > 1 else np.array([0.0])
        color = "#991b1b" if categories[pos - 1] == "Primary" else "#374151"
        ax.scatter(np.full(len(values), pos) + jitter, values, s=13, color=color, alpha=0.75, zorder=3)
    ax.set_xticks(positions)
    ax.set_xticklabels(categories)
    ax.set_title(title, fontsize=10)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", color="#e5e7eb", linewidth=0.7)


def _save_figure(metrics: pd.DataFrame, output_path: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(12.8, 8.4))
    _plot_box_and_points(
        axes[0, 0],
        metrics,
        "q99_exceedance_underestimation_fraction",
        "Q99-exceedance underestimation",
        "Fraction",
    )
    _plot_box_and_points(
        axes[0, 1],
        metrics,
        "q99_q50_spread_pct_obs",
        "Q99-exceedance upper spread",
        "q99-q50 spread (% obs)",
    )
    _plot_box_and_points(
        axes[1, 0],
        metrics,
        "positive_response_q99_underdeficit_reduction",
        "Extreme-rain positive response",
        "Under-deficit reduction (pp)",
    )
    _plot_box_and_points(
        axes[1, 1],
        metrics,
        "negative_control_q99_pred_peak_to_ari100",
        "Extreme-rain negative control",
        "Predicted peak / ARI100",
    )
    fig.suptitle("Primary checkpoint position within same-epoch sensitivity", y=0.98, fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    quantile_dir = _resolve(args.quantile_analysis_dir)
    stress_primary_dir = _resolve(args.stress_primary_dir)
    stress_all_dir = _resolve(args.stress_all_dir)
    output_dir = _resolve(args.output_dir)
    tables_dir = output_dir / "tables"
    figures_dir = output_dir / "figures" / "checkpoint_compact"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    metrics = _build_metrics(quantile_dir, stress_primary_dir, stress_all_dir)
    summary = _summary(metrics)

    metrics_path = tables_dir / "checkpoint_sensitivity_compact_metrics.csv"
    summary_path = tables_dir / "checkpoint_sensitivity_compact_summary.csv"
    figure_path = figures_dir / "checkpoint_sensitivity_compact_summary.png"
    metrics.to_csv(metrics_path, index=False)
    summary.to_csv(summary_path, index=False)
    _save_figure(metrics, figure_path)

    manifest = pd.DataFrame(
        [
            {
                "chart": "checkpoint_sensitivity_compact_summary",
                "path": _relative(figure_path),
                "exists": figure_path.exists(),
            }
        ]
    )
    manifest_path = figures_dir / "checkpoint_sensitivity_compact_manifest.csv"
    manifest.to_csv(manifest_path, index=False)

    metadata = {
        "quantile_analysis_dir": _relative(quantile_dir),
        "stress_primary_dir": _relative(stress_primary_dir),
        "stress_all_dir": _relative(stress_all_dir),
        "metrics": _relative(metrics_path),
        "summary": _relative(summary_path),
        "figure": _relative(figure_path),
        "manifest": _relative(manifest_path),
        "warning": (
            "The hydrograph metrics use primary and same-epoch quantile_analysis outputs. "
            "The stress metrics compare primary/ and all/ extreme-rain outputs and are supporting diagnostics, "
            "not temporal-independence evidence."
        ),
    }
    metadata_path = tables_dir / "checkpoint_sensitivity_compact_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Wrote compact checkpoint metrics: {metrics_path}")
    print(f"Wrote compact checkpoint figure: {figure_path}")


if __name__ == "__main__":
    main()
