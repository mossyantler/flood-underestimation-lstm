#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT_DIR = REPO_ROOT / "output/model_analysis/quantile_analysis"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/probabilistic_diagnostics"
SERIES_RE = re.compile(r"seed(?P<seed>\d+)/epoch(?P<epoch>\d{3})_required_series\.csv$")
PRIMARY_EPOCHS = {
    111: (25, 5),
    222: (10, 10),
    444: (15, 10),
}
QUANTILES = {
    "q50": 0.50,
    "q90": 0.90,
    "q95": 0.95,
    "q99": 0.99,
}
STRATA = [
    ("all", "All hours"),
    ("basin_top10", "Basin Q90-exceedance"),
    ("basin_top5", "Basin Q95-exceedance"),
    ("basin_top1", "Basin Q99-exceedance"),
    ("basin_top0_1", "Basin Q99.9-exceedance"),
    ("observed_peak_hour", "Observed peak hour"),
]
STRATUM_LABELS = dict(STRATA)
SPREADS = {
    "q90_minus_q50": ("q90", "q50"),
    "q95_minus_q90": ("q95", "q90"),
    "q99_minus_q95": ("q99", "q95"),
    "q99_minus_q50": ("q99", "q50"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute Model 2 probabilistic diagnostics from subset300 required-series outputs."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=sorted(PRIMARY_EPOCHS),
        help="Official paired seeds to analyze.",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        nargs="+",
        default=[5, 10, 15, 20, 25, 30],
        help="Validation epoch grid for same-epoch sensitivity.",
    )
    return parser.parse_args()


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _series_path(input_dir: Path, seed: int, epoch: int) -> Path:
    return input_dir / "required_series" / f"seed{seed}" / f"epoch{epoch:03d}_required_series.csv"


def _parse_series_file(path: Path) -> tuple[int, int]:
    match = SERIES_RE.search(path.as_posix())
    if not match:
        raise ValueError(f"Unexpected required-series path: {path}")
    return int(match.group("seed")), int(match.group("epoch"))


def _read_series(path: Path) -> pd.DataFrame:
    usecols = ["seed", "basin", "model1_epoch", "model2_epoch", "obs", *QUANTILES]
    df = pd.read_csv(path, usecols=usecols, dtype={"basin": str})
    df["basin"] = df["basin"].str.zfill(8)
    for col in ["obs", *QUANTILES]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _stratum_masks(df: pd.DataFrame) -> dict[str, pd.Series]:
    masks: dict[str, pd.Series] = {"all": pd.Series(True, index=df.index)}
    thresholds = df.groupby("basin", observed=True)["obs"].quantile([0.90, 0.95, 0.99, 0.999]).unstack()
    thresholds.columns = ["q90_obs", "q95_obs", "q99_obs", "q999_obs"]
    joined = df[["basin", "obs"]].join(thresholds, on="basin")
    masks["basin_top10"] = joined["obs"] >= joined["q90_obs"]
    masks["basin_top5"] = joined["obs"] >= joined["q95_obs"]
    masks["basin_top1"] = joined["obs"] >= joined["q99_obs"]
    masks["basin_top0_1"] = joined["obs"] >= joined["q999_obs"]
    peak_idx = df.groupby("basin", observed=True)["obs"].idxmax()
    peak_mask = pd.Series(False, index=df.index)
    peak_mask.loc[peak_idx] = True
    masks["observed_peak_hour"] = peak_mask
    return masks


def _safe_pct(numerator: float, denominator: float) -> float:
    if not np.isfinite(numerator) or not np.isfinite(denominator) or denominator <= 0:
        return math.nan
    return float(numerator / denominator * 100.0)


def _pinball(obs: pd.Series, pred: pd.Series, tau: float) -> pd.Series:
    diff = obs - pred
    return pd.Series(np.maximum(tau * diff, (tau - 1.0) * diff), index=obs.index)


def _quantile_order_flags(frame: pd.DataFrame) -> dict[str, int]:
    return {
        "q90_lt_q50_rows": int((frame["q90"] < frame["q50"]).sum()),
        "q95_lt_q90_rows": int((frame["q95"] < frame["q90"]).sum()),
        "q99_lt_q95_rows": int((frame["q99"] < frame["q95"]).sum()),
    }


def _summarize_quantile(
    *,
    frame: pd.DataFrame,
    comparison: str,
    seed: int,
    model1_epoch: int,
    model2_epoch: int,
    stratum: str,
    quantile_col: str,
    tau: float,
) -> tuple[dict[str, object], dict[str, object]]:
    obs = frame["obs"]
    pred = frame[quantile_col]
    valid = obs.notna() & pred.notna()
    obs = obs.loc[valid]
    pred = pred.loc[valid]
    loss = _pinball(obs, pred, tau)
    mean_obs = float(obs.mean()) if len(obs) else math.nan
    median_obs = float(obs.median()) if len(obs) else math.nan
    mean_pinball = float(loss.mean()) if len(loss) else math.nan
    median_pinball = float(loss.median()) if len(loss) else math.nan
    empirical_coverage = float((obs <= pred).mean()) if len(obs) else math.nan
    coverage_error = empirical_coverage - tau if np.isfinite(empirical_coverage) else math.nan
    base = {
        "comparison": comparison,
        "seed": seed,
        "model1_epoch": model1_epoch,
        "model2_epoch": model2_epoch,
        "stratum": stratum,
        "stratum_label": STRATUM_LABELS.get(stratum, stratum),
        "quantile": quantile_col,
        "nominal_tau": tau,
        "n_rows": int(len(obs)),
        "n_basins": int(frame.loc[valid, "basin"].nunique()),
        "mean_obs": mean_obs,
        "median_obs": median_obs,
    }
    pinball_row = {
        **base,
        "mean_pinball": mean_pinball,
        "median_pinball": median_pinball,
        "mean_aqs": mean_pinball * 2.0 if np.isfinite(mean_pinball) else math.nan,
        "median_aqs": median_pinball * 2.0 if np.isfinite(median_pinball) else math.nan,
        "mean_pinball_pct_mean_obs": _safe_pct(mean_pinball, mean_obs),
        "median_pinball_pct_median_obs": _safe_pct(median_pinball, median_obs),
    }
    calibration_context = "empirical_one_sided_calibration" if stratum == "all" else "conditional_tail_hit_rate"
    calibration_row = {
        **base,
        "empirical_coverage": empirical_coverage,
        "coverage_error": coverage_error,
        "abs_coverage_error": abs(coverage_error) if np.isfinite(coverage_error) else math.nan,
        "undercoverage_error": max(tau - empirical_coverage, 0.0)
        if np.isfinite(empirical_coverage)
        else math.nan,
        "overcoverage_error": max(empirical_coverage - tau, 0.0)
        if np.isfinite(empirical_coverage)
        else math.nan,
        "underestimation_fraction": float((pred < obs).mean()) if len(obs) else math.nan,
        "calibration_context": calibration_context,
    }
    return pinball_row, calibration_row


def _summarize_spread(
    *,
    frame: pd.DataFrame,
    comparison: str,
    seed: int,
    model1_epoch: int,
    model2_epoch: int,
    stratum: str,
) -> dict[str, object]:
    obs = frame["obs"]
    row: dict[str, object] = {
        "comparison": comparison,
        "seed": seed,
        "model1_epoch": model1_epoch,
        "model2_epoch": model2_epoch,
        "stratum": stratum,
        "stratum_label": STRATUM_LABELS.get(stratum, stratum),
        "n_rows": int(len(frame)),
        "n_basins": int(frame["basin"].nunique()),
        "mean_obs": float(obs.mean()),
        "median_obs": float(obs.median()),
    }
    for spread_col, (upper, lower) in SPREADS.items():
        spread = frame[upper] - frame[lower]
        rel = spread.where(obs > 0) / obs.where(obs > 0) * 100.0
        row[f"mean_{spread_col}"] = float(spread.mean())
        row[f"median_{spread_col}"] = float(spread.median())
        row[f"mean_{spread_col}_pct_obs"] = float(rel.mean(skipna=True))
        row[f"median_{spread_col}_pct_obs"] = float(rel.median(skipna=True))
    row.update(_quantile_order_flags(frame))
    return row


def _summarize_series(
    df: pd.DataFrame,
    *,
    comparison: str,
    seed: int,
    model1_epoch: int,
    model2_epoch: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    masks = _stratum_masks(df)
    pinball_rows: list[dict[str, object]] = []
    calibration_rows: list[dict[str, object]] = []
    spread_rows: list[dict[str, object]] = []
    for stratum, _label in STRATA:
        frame = df.loc[masks[stratum]].copy()
        if frame.empty:
            continue
        for quantile_col, tau in QUANTILES.items():
            pinball_row, calibration_row = _summarize_quantile(
                frame=frame,
                comparison=comparison,
                seed=seed,
                model1_epoch=model1_epoch,
                model2_epoch=model2_epoch,
                stratum=stratum,
                quantile_col=quantile_col,
                tau=tau,
            )
            pinball_rows.append(pinball_row)
            calibration_rows.append(calibration_row)
        spread_rows.append(
            _summarize_spread(
                frame=frame,
                comparison=comparison,
                seed=seed,
                model1_epoch=model1_epoch,
                model2_epoch=model2_epoch,
                stratum=stratum,
            )
        )
    return pinball_rows, calibration_rows, spread_rows


def _aggregate_pinball(pinball: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "mean_pinball",
        "median_pinball",
        "mean_aqs",
        "median_aqs",
        "mean_pinball_pct_mean_obs",
        "median_pinball_pct_median_obs",
    ]
    group_cols = ["comparison", "stratum", "stratum_label", "quantile", "nominal_tau"]
    rows = []
    for keys, group in pinball.groupby(group_cols, dropna=False, sort=True):
        row = dict(zip(group_cols, keys, strict=True))
        row["n_summaries"] = int(len(group))
        row["mean_n_rows"] = float(group["n_rows"].mean())
        for col in cols:
            row[f"mean_{col}"] = float(group[col].mean())
            row[f"median_{col}"] = float(group[col].median())
            row[f"min_{col}"] = float(group[col].min())
            row[f"max_{col}"] = float(group[col].max())
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["comparison", "stratum", "nominal_tau"])


def _aggregate_calibration(calibration: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "empirical_coverage",
        "coverage_error",
        "abs_coverage_error",
        "undercoverage_error",
        "overcoverage_error",
        "underestimation_fraction",
    ]
    group_cols = [
        "comparison",
        "stratum",
        "stratum_label",
        "quantile",
        "nominal_tau",
        "calibration_context",
    ]
    rows = []
    for keys, group in calibration.groupby(group_cols, dropna=False, sort=True):
        row = dict(zip(group_cols, keys, strict=True))
        row["n_summaries"] = int(len(group))
        row["mean_n_rows"] = float(group["n_rows"].mean())
        for col in cols:
            row[f"mean_{col}"] = float(group[col].mean())
            row[f"median_{col}"] = float(group[col].median())
            row[f"min_{col}"] = float(group[col].min())
            row[f"max_{col}"] = float(group[col].max())
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["comparison", "stratum", "nominal_tau"])


def _aggregate_spread(spread: pd.DataFrame) -> pd.DataFrame:
    value_cols = [
        "median_q90_minus_q50",
        "median_q95_minus_q90",
        "median_q99_minus_q95",
        "median_q99_minus_q50",
        "median_q99_minus_q50_pct_obs",
    ]
    rows = []
    group_cols = ["comparison", "stratum", "stratum_label"]
    for keys, group in spread.groupby(group_cols, dropna=False, sort=True):
        row = dict(zip(group_cols, keys, strict=True))
        row["n_summaries"] = int(len(group))
        row["mean_n_rows"] = float(group["n_rows"].mean())
        for col in value_cols:
            row[f"mean_{col}"] = float(group[col].mean())
            row[f"median_{col}"] = float(group[col].median())
            row[f"min_{col}"] = float(group[col].min())
            row[f"max_{col}"] = float(group[col].max())
        order_cols = ["q90_lt_q50_rows", "q95_lt_q90_rows", "q99_lt_q95_rows"]
        for col in order_cols:
            row[f"sum_{col}"] = int(group[col].sum())
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["comparison", "stratum"])


def _save_primary_calibration_plot(calibration: pd.DataFrame, path: Path) -> None:
    primary_all = calibration[(calibration["comparison"] == "primary") & (calibration["stratum"] == "all")]
    if primary_all.empty:
        return
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    for seed, group in primary_all.groupby("seed", sort=True):
        group = group.sort_values("nominal_tau")
        ax.plot(
            group["nominal_tau"],
            group["empirical_coverage"],
            marker="o",
            linewidth=1.6,
            label=f"seed {int(seed)}",
        )
        for _, row in group.iterrows():
            ax.text(
                row["nominal_tau"],
                row["empirical_coverage"] + 0.018,
                row["quantile"],
                ha="center",
                va="bottom",
                fontsize=8,
            )
    ax.plot([0, 1], [0, 1], color="#4b5563", linestyle="--", linewidth=1.0, label="nominal")
    ax.set_xlim(0.45, 1.01)
    ax.set_ylim(0.0, 1.01)
    ax.set_xlabel("Nominal quantile level")
    ax.set_ylabel("Empirical coverage: fraction(obs <= q)")
    ax.set_title("Primary all-hour Model 2 calibration")
    ax.grid(True, color="#d1d5db", linewidth=0.7, alpha=0.8)
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _save_pinball_stratum_plot(pinball_agg: pd.DataFrame, path: Path) -> None:
    primary = pinball_agg[pinball_agg["comparison"] == "primary"].copy()
    strata = ["all", "basin_top1", "basin_top0_1", "observed_peak_hour"]
    quantiles = list(QUANTILES)
    primary = primary[primary["stratum"].isin(strata)]
    if primary.empty:
        return
    fig, axes = plt.subplots(1, len(strata), figsize=(13.5, 4.3), sharey=False)
    colors = {"q50": "#2563eb", "q90": "#16a34a", "q95": "#f97316", "q99": "#dc2626"}
    for ax, stratum in zip(axes, strata, strict=True):
        group = primary[primary["stratum"] == stratum].set_index("quantile")
        values = [group.loc[q, "median_mean_pinball_pct_mean_obs"] if q in group.index else math.nan for q in quantiles]
        ax.bar(quantiles, values, color=[colors[q] for q in quantiles])
        ax.set_title(STRATUM_LABELS.get(stratum, stratum), fontsize=10)
        ax.set_xlabel("Quantile")
        ax.grid(True, axis="y", color="#e5e7eb", linewidth=0.7)
    axes[0].set_ylabel("Median mean pinball loss (% of mean obs)")
    fig.suptitle("Primary Model 2 pinball loss by flow stratum", y=1.02, fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _save_spread_plot(spread_agg: pd.DataFrame, path: Path) -> None:
    primary = spread_agg[spread_agg["comparison"] == "primary"].copy()
    order = ["all", "basin_top10", "basin_top5", "basin_top1", "basin_top0_1", "observed_peak_hour"]
    primary = primary[primary["stratum"].isin(order)].copy()
    if primary.empty:
        return
    primary["stratum"] = pd.Categorical(primary["stratum"], categories=order, ordered=True)
    primary = primary.sort_values("stratum")
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    ax.plot(
        primary["stratum_label"],
        primary["median_median_q99_minus_q50_pct_obs"],
        marker="o",
        linewidth=1.8,
        color="#b45309",
    )
    ax.set_ylabel("Median q99-q50 spread (% of obs)")
    ax.set_xlabel("")
    ax.set_title("Primary upper-tail spread by flow stratum")
    ax.grid(True, axis="y", color="#e5e7eb", linewidth=0.7)
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _save_same_epoch_calibration_error_plot(calibration: pd.DataFrame, path: Path) -> None:
    same_all = calibration[(calibration["comparison"] == "same_epoch") & (calibration["stratum"] == "all")]
    if same_all.empty:
        return
    quantiles = list(QUANTILES)
    data = [
        same_all.loc[same_all["quantile"].eq(q), "coverage_error"].dropna().to_numpy()
        for q in quantiles
    ]
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    ax.boxplot(
        data,
        tick_labels=quantiles,
        showmeans=True,
        patch_artist=True,
        medianprops={"color": "#111827", "linewidth": 1.4},
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
    ax.axhline(0.0, color="#4b5563", linestyle="--", linewidth=1.0)
    ax.set_xlabel("Quantile")
    ax.set_ylabel("Empirical coverage - nominal")
    ax.set_title("Same-epoch all-hour calibration error")
    ax.grid(True, axis="y", color="#e5e7eb", linewidth=0.7)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _write_report(
    *,
    output_dir: Path,
    pinball_by_stratum: pd.DataFrame,
    calibration_by_stratum: pd.DataFrame,
    spread_by_stratum: pd.DataFrame,
) -> Path:
    report_dir = output_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "probabilistic_diagnostics_report.md"

    primary_all_cal = calibration_by_stratum[
        (calibration_by_stratum["comparison"] == "primary") & (calibration_by_stratum["stratum"] == "all")
    ].copy()
    primary_top1_cal = calibration_by_stratum[
        (calibration_by_stratum["comparison"] == "primary") & (calibration_by_stratum["stratum"] == "basin_top1")
    ].copy()
    primary_all_pinball = pinball_by_stratum[
        (pinball_by_stratum["comparison"] == "primary") & (pinball_by_stratum["stratum"] == "all")
    ].copy()
    primary_top1_spread = spread_by_stratum[
        (spread_by_stratum["comparison"] == "primary") & (spread_by_stratum["stratum"] == "basin_top1")
    ].copy()

    def _fmt_table(df: pd.DataFrame, cols: list[str]) -> str:
        if df.empty:
            return "_No rows._"
        table = df[cols].copy()
        for col in table.select_dtypes(include=["float", "float64"]).columns:
            table[col] = table[col].map(lambda x: f"{x:.3f}" if pd.notna(x) else "")
        headers = list(table.columns)
        lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
        ]
        for _, row in table.iterrows():
            values = [str(row[col]) for col in headers]
            lines.append("| " + " | ".join(values) + " |")
        return "\n".join(lines)

    lines = [
        "# Probabilistic Diagnostics",
        "",
        "This report summarizes Model 2 `q50/q90/q95/q99` as quantile outputs.",
        "All-hour coverage is the formal one-sided calibration diagnostic; high-flow strata are conditional tail hit-rate diagnostics.",
        "",
        "## Primary All-Hour Calibration",
        "",
        _fmt_table(
            primary_all_cal,
            [
                "quantile",
                "nominal_tau",
                "median_empirical_coverage",
                "median_coverage_error",
                "median_abs_coverage_error",
                "median_underestimation_fraction",
            ],
        ),
        "",
        "## Primary All-Hour Pinball",
        "",
        _fmt_table(
            primary_all_pinball,
            [
                "quantile",
                "nominal_tau",
                "median_mean_pinball",
                "median_mean_aqs",
                "median_mean_pinball_pct_mean_obs",
            ],
        ),
        "",
        "## Primary Q99-Exceedance Tail Hit Rate",
        "",
        _fmt_table(
            primary_top1_cal,
            [
                "quantile",
                "nominal_tau",
                "median_empirical_coverage",
                "median_coverage_error",
                "median_underestimation_fraction",
            ],
        ),
        "",
        "## Primary Q99-Exceedance Upper-Tail Spread",
        "",
        _fmt_table(
            primary_top1_spread,
            [
                "stratum_label",
                "median_median_q99_minus_q50",
                "median_median_q99_minus_q50_pct_obs",
                "sum_q90_lt_q50_rows",
                "sum_q95_lt_q90_rows",
                "sum_q99_lt_q95_rows",
            ],
        ),
        "",
        "## Interpretation Limits",
        "",
        "- The quantile set has no lower tail, so interval scores and central prediction intervals are not computed.",
        "- `q99` should not be described as a calibrated 99% prediction interval bound unless the all-hour calibration result supports that wording.",
        "- Conditional high-flow strata are intentionally selected on observed flow, so their coverage values are tail hit rates rather than formal calibration.",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> None:
    args = parse_args()
    input_dir = _resolve(args.input_dir)
    output_dir = _resolve(args.output_dir)
    figures_dir = output_dir / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    pinball_rows: list[dict[str, object]] = []
    calibration_rows: list[dict[str, object]] = []
    spread_rows: list[dict[str, object]] = []
    manifest_rows: list[dict[str, object]] = []

    for seed in args.seeds:
        if seed not in PRIMARY_EPOCHS:
            raise ValueError(f"No primary epoch mapping for seed {seed}")
        model1_epoch, model2_epoch = PRIMARY_EPOCHS[seed]
        path = _series_path(input_dir, seed, model2_epoch)
        if not path.exists():
            raise FileNotFoundError(path)
        df = _read_series(path)
        rows = _summarize_series(
            df,
            comparison="primary",
            seed=seed,
            model1_epoch=model1_epoch,
            model2_epoch=model2_epoch,
        )
        pinball_rows.extend(rows[0])
        calibration_rows.extend(rows[1])
        spread_rows.extend(rows[2])
        manifest_rows.append(
            {
                "comparison": "primary",
                "seed": seed,
                "model1_epoch": model1_epoch,
                "model2_epoch": model2_epoch,
                "path": _relative(path),
                "n_rows": int(len(df)),
                "n_basins": int(df["basin"].nunique()),
            }
        )

    for seed in args.seeds:
        for epoch in args.epochs:
            path = _series_path(input_dir, seed, epoch)
            if not path.exists():
                raise FileNotFoundError(path)
            parsed_seed, parsed_epoch = _parse_series_file(path)
            df = _read_series(path)
            rows = _summarize_series(
                df,
                comparison="same_epoch",
                seed=parsed_seed,
                model1_epoch=parsed_epoch,
                model2_epoch=parsed_epoch,
            )
            pinball_rows.extend(rows[0])
            calibration_rows.extend(rows[1])
            spread_rows.extend(rows[2])
            manifest_rows.append(
                {
                    "comparison": "same_epoch",
                    "seed": parsed_seed,
                    "model1_epoch": parsed_epoch,
                    "model2_epoch": parsed_epoch,
                    "path": _relative(path),
                    "n_rows": int(len(df)),
                    "n_basins": int(df["basin"].nunique()),
                }
            )

    pinball = pd.DataFrame(pinball_rows)
    calibration = pd.DataFrame(calibration_rows)
    spread = pd.DataFrame(spread_rows)
    pinball_by_stratum = _aggregate_pinball(pinball)
    calibration_by_stratum = _aggregate_calibration(calibration)
    spread_by_stratum = _aggregate_spread(spread)
    manifest = pd.DataFrame(manifest_rows)

    pinball_path = output_dir / "quantile_pinball_summary.csv"
    pinball_by_stratum_path = output_dir / "quantile_pinball_by_stratum.csv"
    calibration_path = output_dir / "quantile_calibration_summary.csv"
    calibration_by_stratum_path = output_dir / "quantile_calibration_by_stratum.csv"
    spread_path = output_dir / "upper_tail_spread_summary.csv"
    spread_by_stratum_path = output_dir / "upper_tail_spread_by_stratum.csv"
    manifest_path = output_dir / "input_manifest.csv"

    pinball.to_csv(pinball_path, index=False)
    pinball_by_stratum.to_csv(pinball_by_stratum_path, index=False)
    calibration.to_csv(calibration_path, index=False)
    calibration_by_stratum.to_csv(calibration_by_stratum_path, index=False)
    spread.to_csv(spread_path, index=False)
    spread_by_stratum.to_csv(spread_by_stratum_path, index=False)
    manifest.to_csv(manifest_path, index=False)

    chart_specs = [
        ("primary_all_calibration", figures_dir / "primary_all_quantile_calibration.png"),
        ("primary_pinball_by_stratum", figures_dir / "primary_pinball_by_stratum.png"),
        ("primary_q99_q50_spread_by_stratum", figures_dir / "primary_q99_q50_spread_by_stratum.png"),
        ("same_epoch_all_calibration_error", figures_dir / "same_epoch_all_calibration_error.png"),
    ]
    _save_primary_calibration_plot(calibration, chart_specs[0][1])
    _save_pinball_stratum_plot(pinball_by_stratum, chart_specs[1][1])
    _save_spread_plot(spread_by_stratum, chart_specs[2][1])
    _save_same_epoch_calibration_error_plot(calibration, chart_specs[3][1])
    chart_manifest = pd.DataFrame(
        [{"chart": name, "path": _relative(path), "exists": path.exists()} for name, path in chart_specs]
    )
    chart_manifest_path = output_dir / "chart_manifest.csv"
    chart_manifest.to_csv(chart_manifest_path, index=False)

    report_path = _write_report(
        output_dir=output_dir,
        pinball_by_stratum=pinball_by_stratum,
        calibration_by_stratum=calibration_by_stratum,
        spread_by_stratum=spread_by_stratum,
    )

    metadata = {
        "input_dir": _relative(input_dir),
        "output_dir": _relative(output_dir),
        "primary_epochs": {str(seed): PRIMARY_EPOCHS[seed] for seed in args.seeds},
        "same_epoch_grid": args.epochs,
        "quantiles": QUANTILES,
        "strata": {key: label for key, label in STRATA},
        "pinball_definition": "mean(max(tau * (obs - q), (tau - 1) * (obs - q)))",
        "aqs_definition": "2 * pinball loss",
        "calibration_definition": "empirical one-sided coverage fraction mean(obs <= q_tau)",
        "calibration_warning": (
            "All-hour coverage is the formal calibration diagnostic. Observed-flow strata are conditional "
            "tail hit-rate diagnostics and should not be described as unconditional nominal coverage."
        ),
        "outputs": {
            "quantile_pinball_summary": _relative(pinball_path),
            "quantile_pinball_by_stratum": _relative(pinball_by_stratum_path),
            "quantile_calibration_summary": _relative(calibration_path),
            "quantile_calibration_by_stratum": _relative(calibration_by_stratum_path),
            "upper_tail_spread_summary": _relative(spread_path),
            "upper_tail_spread_by_stratum": _relative(spread_by_stratum_path),
            "input_manifest": _relative(manifest_path),
            "chart_manifest": _relative(chart_manifest_path),
            "report": _relative(report_path),
        },
    }
    metadata_path = output_dir / "analysis_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Wrote probabilistic diagnostics to {output_dir}")
    print(f"Rows: pinball={len(pinball)}, calibration={len(calibration)}, spread={len(spread)}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
