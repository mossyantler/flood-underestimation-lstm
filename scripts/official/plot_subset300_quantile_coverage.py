#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = (
    REPO_ROOT
    / "output/model_analysis/quantile_analysis/analysis/flow_strata_predictor_summary.csv"
)
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "output/model_analysis/quantile_analysis/analysis/quantile_coverage"
)
Q_RE = re.compile(r"q(?P<level>\d+)")
STRATUM_LABELS = {
    "all": "All",
    "basin_top10": "Top 10%",
    "basin_top5": "Top 5%",
    "basin_top1": "Top 1%",
    "basin_top0_1": "Top 0.1%",
    "observed_peak_hour": "Observed peak",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot Model 2 quantile empirical coverage diagnostics."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _nominal_from_predictor(predictor: str) -> float | None:
    match = Q_RE.search(str(predictor))
    if not match:
        return None
    return int(match.group("level")) / 100


def _read_coverage(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df[df["predictor"].astype(str).str.contains("Model 2 q", na=False)].copy()
    df["nominal_coverage"] = df["predictor"].map(_nominal_from_predictor)
    df = df[df["nominal_coverage"].notna()].copy()
    df["coverage_error"] = df["coverage_fraction"] - df["nominal_coverage"]
    df["abs_coverage_error"] = df["coverage_error"].abs()
    df["quantile_label"] = df["nominal_coverage"].map(lambda x: f"q{int(round(x * 100))}")
    df["stratum_label"] = df["stratum"].map(STRATUM_LABELS).fillna(df["stratum"])
    return df.sort_values(["comparison", "seed", "model2_epoch", "stratum", "nominal_coverage"])


def _aggregate(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    group_cols = ["comparison", "stratum", "stratum_label", "predictor", "quantile_label", "nominal_coverage"]
    for keys, group in df.groupby(group_cols, sort=True):
        row = dict(zip(group_cols, keys, strict=True))
        row.update(
            {
                "n_summaries": int(len(group)),
                "mean_empirical_coverage": float(group["coverage_fraction"].mean()),
                "median_empirical_coverage": float(group["coverage_fraction"].median()),
                "mean_coverage_error": float(group["coverage_error"].mean()),
                "median_coverage_error": float(group["coverage_error"].median()),
                "mean_abs_coverage_error": float(group["abs_coverage_error"].mean()),
                "median_abs_coverage_error": float(group["abs_coverage_error"].median()),
                "mean_underestimation_fraction": float(group["underestimation_fraction"].mean()),
                "median_underestimation_fraction": float(group["underestimation_fraction"].median()),
                "median_median_rel_bias_pct": float(group["median_rel_bias_pct"].median()),
                "median_median_abs_error": float(group["median_abs_error"].median()),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def _save_primary_all_calibration(df: pd.DataFrame, output_path: Path) -> None:
    primary_all = df[(df["comparison"] == "primary") & (df["stratum"] == "all")].copy()
    if primary_all.empty:
        return
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    for seed, group in primary_all.groupby("seed", sort=True):
        group = group.sort_values("nominal_coverage")
        ax.plot(
            group["nominal_coverage"],
            group["coverage_fraction"],
            marker="o",
            linewidth=1.6,
            label=f"seed {int(seed)}",
        )
        for _, row in group.iterrows():
            ax.text(
                row["nominal_coverage"],
                row["coverage_fraction"] + 0.018,
                row["quantile_label"],
                ha="center",
                va="bottom",
                fontsize=8,
            )
    ax.plot([0, 1], [0, 1], color="#555555", linestyle="--", linewidth=1.0, label="nominal")
    ax.set_xlim(0.45, 1.01)
    ax.set_ylim(0.0, 1.01)
    ax.set_xlabel("Nominal quantile level")
    ax.set_ylabel("Empirical coverage: fraction(obs <= q)")
    ax.set_title("Primary all-hour Model 2 quantile coverage")
    ax.grid(True, color="#dddddd", linewidth=0.7, alpha=0.8)
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _save_primary_stratum_coverage(aggregate: pd.DataFrame, output_path: Path) -> None:
    primary = aggregate[aggregate["comparison"] == "primary"].copy()
    if primary.empty:
        return
    order = ["all", "basin_top10", "basin_top5", "basin_top1", "basin_top0_1", "observed_peak_hour"]
    fig, ax = plt.subplots(figsize=(8.5, 5.4))
    for stratum in order:
        group = primary[primary["stratum"] == stratum].sort_values("nominal_coverage")
        if group.empty:
            continue
        ax.plot(
            group["nominal_coverage"],
            group["median_empirical_coverage"],
            marker="o",
            linewidth=1.5,
            label=STRATUM_LABELS.get(stratum, stratum),
        )
    ax.plot([0, 1], [0, 1], color="#555555", linestyle="--", linewidth=1.0, label="nominal")
    ax.set_xlim(0.45, 1.01)
    ax.set_ylim(0.0, 1.01)
    ax.set_xlabel("Nominal quantile level")
    ax.set_ylabel("Median empirical coverage across primary seeds")
    ax.set_title("Primary Model 2 quantile coverage by flow stratum")
    ax.grid(True, color="#dddddd", linewidth=0.7, alpha=0.8)
    ax.legend(frameon=False, ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _save_same_epoch_error_boxplot(df: pd.DataFrame, output_path: Path) -> None:
    same_all = df[(df["comparison"] == "same_epoch") & (df["stratum"] == "all")].copy()
    if same_all.empty:
        return
    quantiles = sorted(same_all["nominal_coverage"].unique())
    data = [
        same_all.loc[same_all["nominal_coverage"].eq(q), "coverage_error"].dropna().to_numpy()
        for q in quantiles
    ]
    labels = [f"q{int(round(q * 100))}" for q in quantiles]
    fig, ax = plt.subplots(figsize=(7.4, 4.8))
    ax.boxplot(
        data,
        tick_labels=labels,
        showmeans=True,
        patch_artist=True,
        medianprops={"color": "#111111", "linewidth": 1.4},
        meanprops={
            "marker": "o",
            "markerfacecolor": "#dc2626",
            "markeredgecolor": "#7f1d1d",
            "markersize": 4.5,
        },
        boxprops={"facecolor": "#dbeafe", "edgecolor": "#1f2937", "linewidth": 0.9},
        whiskerprops={"color": "#1f2937", "linewidth": 0.9},
        capprops={"color": "#1f2937", "linewidth": 0.9},
        flierprops={
            "marker": ".",
            "markerfacecolor": "#6b7280",
            "markeredgecolor": "#6b7280",
            "markersize": 3,
            "alpha": 0.65,
        },
    )
    ax.axhline(0, color="#555555", linewidth=1.0)
    ax.set_xlabel("Quantile")
    ax.set_ylabel("Empirical coverage - nominal coverage")
    ax.set_title("Same-epoch all-hour coverage error across seeds/epochs")
    ax.grid(True, axis="y", color="#dddddd", linewidth=0.7, alpha=0.8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    input_path = _resolve(args.input)
    output_dir = _resolve(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    coverage = _read_coverage(input_path)
    if coverage.empty:
        raise SystemExit(f"No Model 2 quantile rows found in {input_path}")
    aggregate = _aggregate(coverage)

    coverage_path = output_dir / "quantile_coverage_summary.csv"
    aggregate_path = output_dir / "quantile_coverage_aggregate.csv"
    coverage.to_csv(coverage_path, index=False)
    aggregate.to_csv(aggregate_path, index=False)

    charts = [
        ("primary_all_calibration", output_dir / "primary_all_quantile_coverage.png"),
        ("primary_stratum_coverage", output_dir / "primary_stratum_quantile_coverage.png"),
        ("same_epoch_all_coverage_error", output_dir / "same_epoch_all_coverage_error_boxplot.png"),
    ]
    _save_primary_all_calibration(coverage, charts[0][1])
    _save_primary_stratum_coverage(aggregate, charts[1][1])
    _save_same_epoch_error_boxplot(coverage, charts[2][1])

    manifest = pd.DataFrame(
        [{"chart": name, "path": str(path.relative_to(REPO_ROOT))} for name, path in charts]
    )
    manifest_path = output_dir / "quantile_coverage_chart_manifest.csv"
    manifest.to_csv(manifest_path, index=False)

    metadata = {
        "input": str(input_path.relative_to(REPO_ROOT)),
        "output_dir": str(output_dir.relative_to(REPO_ROOT)),
        "coverage_definition": "Empirical one-sided coverage, fraction of rows with obs <= predicted quantile.",
        "calibration_warning": (
            "Nominal 50/90/95/99 coverage is meaningful mainly on unconditional all-hour samples. "
            "High-flow strata are conditional subsets and should be read as tail hit-rate diagnostics."
        ),
        "summary": str(coverage_path.relative_to(REPO_ROOT)),
        "aggregate": str(aggregate_path.relative_to(REPO_ROOT)),
        "manifest": str(manifest_path.relative_to(REPO_ROOT)),
    }
    metadata_path = output_dir / "quantile_coverage_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Wrote quantile coverage diagnostics to {output_dir}")
    print(f"Wrote summary: {coverage_path}")
    print(f"Wrote aggregate: {aggregate_path}")


if __name__ == "__main__":
    main()
