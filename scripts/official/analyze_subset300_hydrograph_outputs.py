#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


SERIES_RE = re.compile(r"seed(?P<seed>\d+)/epoch(?P<epoch>\d{3})_required_series\.csv$")
PRIMARY_EPOCHS = {
    111: (25, 5),
    222: (10, 10),
    444: (15, 10),
}
PREDICTORS = [
    ("model1", "Model 1"),
    ("q50", "Model 2 q50"),
    ("q90", "Model 2 q90"),
    ("q95", "Model 2 q95"),
    ("q99", "Model 2 q99"),
]
GAP_COLUMNS = ["q90_minus_q50", "q95_minus_q90", "q99_minus_q95", "q99_minus_q50"]
STRATA = [
    ("all", "All hours"),
    ("basin_top10", "Basin top 10%"),
    ("basin_top5", "Basin top 5%"),
    ("basin_top1", "Basin top 1%"),
    ("basin_top0_1", "Basin top 0.1%"),
]
MODEL_COLORS = {
    "Model 1": "#2563eb",
    "Model 2 q50": "#dc2626",
    "Model 2 q90": "#ef4444",
    "Model 2 q95": "#f97316",
    "Model 2 q99": "#f59e0b",
}


def _series_files(input_dir: Path) -> list[Path]:
    files = sorted((input_dir / "required_series").glob("seed*/epoch*_required_series.csv"))
    if not files:
        raise FileNotFoundError(f"No required-series CSV files found under {input_dir}")
    return files


def _parse_series_file(path: Path) -> tuple[int, int]:
    match = SERIES_RE.search(path.as_posix())
    if not match:
        raise ValueError(f"Unexpected required-series file path: {path}")
    return int(match.group("seed")), int(match.group("epoch"))


def _read_same_epoch(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"basin": str})
    df["basin"] = df["basin"].str.zfill(8)
    df["datetime"] = pd.to_datetime(df["datetime"])
    for col in ["obs", "model1", "q50", "q90", "q95", "q99", *GAP_COLUMNS]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _read_primary_pair(base_dir: Path, seed: int, model1_epoch: int, model2_epoch: int) -> pd.DataFrame:
    m1_path = base_dir / "required_series" / f"seed{seed}" / f"epoch{model1_epoch:03d}_required_series.csv"
    m2_path = base_dir / "required_series" / f"seed{seed}" / f"epoch{model2_epoch:03d}_required_series.csv"

    left = pd.read_csv(
        m1_path,
        usecols=["basin", "datetime", "obs", "model1"],
        dtype={"basin": str},
        parse_dates=["datetime"],
    )
    right = pd.read_csv(
        m2_path,
        usecols=["basin", "datetime", "q50", "q90", "q95", "q99"],
        dtype={"basin": str},
        parse_dates=["datetime"],
    )
    left["basin"] = left["basin"].str.zfill(8)
    right["basin"] = right["basin"].str.zfill(8)
    df = left.merge(right, on=["basin", "datetime"], how="inner", validate="one_to_one")
    for col in ["obs", "model1", "q50", "q90", "q95", "q99"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["q90_minus_q50"] = df["q90"] - df["q50"]
    df["q95_minus_q90"] = df["q95"] - df["q90"]
    df["q99_minus_q95"] = df["q99"] - df["q95"]
    df["q99_minus_q50"] = df["q99"] - df["q50"]
    df["model1_epoch"] = model1_epoch
    df["model2_epoch"] = model2_epoch
    return df


def _stratum_masks(df: pd.DataFrame) -> dict[str, pd.Series]:
    masks: dict[str, pd.Series] = {"all": pd.Series(True, index=df.index)}
    thresholds = df.groupby("basin")["obs"].quantile([0.90, 0.95, 0.99, 0.999]).unstack()
    thresholds.columns = ["q90_obs", "q95_obs", "q99_obs", "q999_obs"]
    joined = df[["basin", "obs"]].join(thresholds, on="basin")
    masks["basin_top10"] = joined["obs"] >= joined["q90_obs"]
    masks["basin_top5"] = joined["obs"] >= joined["q95_obs"]
    masks["basin_top1"] = joined["obs"] >= joined["q99_obs"]
    masks["basin_top0_1"] = joined["obs"] >= joined["q999_obs"]
    return masks


def _safe_rel(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    out = pd.Series(np.nan, index=numerator.index, dtype=float)
    mask = denominator > 0
    out.loc[mask] = numerator.loc[mask] / denominator.loc[mask]
    return out


def _summarize_predictor(
    *,
    frame: pd.DataFrame,
    predictor_col: str,
    predictor_label: str,
    comparison: str,
    seed: int,
    model1_epoch: int,
    model2_epoch: int,
    stratum: str,
) -> dict[str, float | int | str]:
    obs = frame["obs"]
    pred = frame[predictor_col]
    bias = pred - obs
    rel_bias_pct = _safe_rel(bias, obs) * 100.0
    under_deficit_pct = _safe_rel((obs - pred).clip(lower=0), obs) * 100.0
    return {
        "comparison": comparison,
        "seed": seed,
        "model1_epoch": model1_epoch,
        "model2_epoch": model2_epoch,
        "stratum": stratum,
        "predictor": predictor_label,
        "n_rows": int(len(frame)),
        "n_basins": int(frame["basin"].nunique()),
        "mean_obs": float(obs.mean()),
        "median_obs": float(obs.median()),
        "coverage_fraction": float((obs <= pred).mean()),
        "underestimation_fraction": float((pred < obs).mean()),
        "mean_bias": float(bias.mean()),
        "median_bias": float(bias.median()),
        "mean_rel_bias_pct": float(rel_bias_pct.mean(skipna=True)),
        "median_rel_bias_pct": float(rel_bias_pct.median(skipna=True)),
        "median_under_rel_deficit_pct": float(under_deficit_pct.median(skipna=True)),
        "median_abs_error": float((pred - obs).abs().median()),
    }


def _summarize_gaps(
    *,
    frame: pd.DataFrame,
    comparison: str,
    seed: int,
    model1_epoch: int,
    model2_epoch: int,
    stratum: str,
) -> dict[str, float | int | str]:
    row: dict[str, float | int | str] = {
        "comparison": comparison,
        "seed": seed,
        "model1_epoch": model1_epoch,
        "model2_epoch": model2_epoch,
        "stratum": stratum,
        "n_rows": int(len(frame)),
        "n_basins": int(frame["basin"].nunique()),
        "mean_obs": float(frame["obs"].mean()),
        "median_obs": float(frame["obs"].median()),
    }
    for col in GAP_COLUMNS:
        row[f"median_{col}"] = float(frame[col].median())
        row[f"mean_{col}"] = float(frame[col].mean())
        row[f"median_{col}_pct_obs"] = float((_safe_rel(frame[col], frame["obs"]) * 100.0).median(skipna=True))
    return row


def _peak_rows(df: pd.DataFrame, *, comparison: str, seed: int, model1_epoch: int, model2_epoch: int) -> pd.DataFrame:
    peak_idx = df.groupby("basin")["obs"].idxmax()
    peaks = df.loc[peak_idx, ["basin", "datetime", "obs", "model1", "q50", "q90", "q95", "q99", *GAP_COLUMNS]].copy()
    peaks.insert(0, "model2_epoch", model2_epoch)
    peaks.insert(0, "model1_epoch", model1_epoch)
    peaks.insert(0, "seed", seed)
    peaks.insert(0, "comparison", comparison)
    for col, label in PREDICTORS:
        peaks[f"{col}_rel_bias_pct"] = _safe_rel(peaks[col] - peaks["obs"], peaks["obs"]) * 100.0
        peaks[f"{col}_underestimated"] = peaks[col] < peaks["obs"]
    return peaks


def _summarize_frame(
    df: pd.DataFrame,
    *,
    comparison: str,
    seed: int,
    model1_epoch: int,
    model2_epoch: int,
) -> tuple[list[dict], list[dict], pd.DataFrame]:
    masks = _stratum_masks(df)
    predictor_rows: list[dict] = []
    gap_rows: list[dict] = []
    for stratum, _label in STRATA:
        frame = df.loc[masks[stratum]].copy()
        if frame.empty:
            continue
        for col, label in PREDICTORS:
            predictor_rows.append(
                _summarize_predictor(
                    frame=frame,
                    predictor_col=col,
                    predictor_label=label,
                    comparison=comparison,
                    seed=seed,
                    model1_epoch=model1_epoch,
                    model2_epoch=model2_epoch,
                    stratum=stratum,
                )
            )
        gap_rows.append(
            _summarize_gaps(
                frame=frame,
                comparison=comparison,
                seed=seed,
                model1_epoch=model1_epoch,
                model2_epoch=model2_epoch,
                stratum=stratum,
            )
        )

    peaks = _peak_rows(df, comparison=comparison, seed=seed, model1_epoch=model1_epoch, model2_epoch=model2_epoch)
    for col, label in PREDICTORS:
        predictor_rows.append(
            _summarize_predictor(
                frame=peaks,
                predictor_col=col,
                predictor_label=label,
                comparison=comparison,
                seed=seed,
                model1_epoch=model1_epoch,
                model2_epoch=model2_epoch,
                stratum="observed_peak_hour",
            )
        )
    gap_rows.append(
        _summarize_gaps(
            frame=peaks,
            comparison=comparison,
            seed=seed,
            model1_epoch=model1_epoch,
            model2_epoch=model2_epoch,
            stratum="observed_peak_hour",
        )
    )
    return predictor_rows, gap_rows, peaks


def _sanity_row(df: pd.DataFrame, path: Path, *, seed: int, epoch: int) -> dict[str, float | int | str]:
    q50_diff = (df["model2_q50_result"] - df["q50"]).abs()
    return {
        "path": str(path),
        "seed": seed,
        "epoch": epoch,
        "n_rows": int(len(df)),
        "n_basins": int(df["basin"].nunique()),
        "q50_result_max_abs_diff": float(q50_diff.max()),
        "q50_result_median_abs_diff": float(q50_diff.median()),
        "q90_lt_q50_rows": int((df["q90"] < df["q50"]).sum()),
        "q95_lt_q90_rows": int((df["q95"] < df["q90"]).sum()),
        "q99_lt_q95_rows": int((df["q99"] < df["q95"]).sum()),
    }


def _aggregate(summary: pd.DataFrame) -> pd.DataFrame:
    value_cols = [
        "coverage_fraction",
        "underestimation_fraction",
        "median_rel_bias_pct",
        "median_under_rel_deficit_pct",
        "median_abs_error",
    ]
    grouped = summary.groupby(["comparison", "stratum", "predictor"], dropna=False)
    rows = []
    for key, group in grouped:
        row = dict(zip(["comparison", "stratum", "predictor"], key, strict=True))
        row["n_summaries"] = int(len(group))
        for col in value_cols:
            row[f"mean_{col}"] = float(group[col].mean())
            row[f"median_{col}"] = float(group[col].median())
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["comparison", "stratum", "predictor"])


def _aggregate_gaps(gaps: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "median_q90_minus_q50",
        "median_q95_minus_q90",
        "median_q99_minus_q95",
        "median_q99_minus_q50",
        "median_q99_minus_q50_pct_obs",
    ]
    rows = []
    for key, group in gaps.groupby(["comparison", "stratum"], dropna=False):
        row = dict(zip(["comparison", "stratum"], key, strict=True))
        row["n_summaries"] = int(len(group))
        for col in cols:
            row[f"mean_{col}"] = float(group[col].mean())
            row[f"median_{col}"] = float(group[col].median())
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["comparison", "stratum"])


def _plot_top1_underestimation(summary: pd.DataFrame, charts_dir: Path) -> None:
    data = summary[(summary["comparison"] == "same_epoch") & (summary["stratum"] == "basin_top1")]
    fig, axes = plt.subplots(1, 3, figsize=(17, 4.8), sharey=True)
    for ax, seed in zip(axes, sorted(data["seed"].unique()), strict=True):
        seed_data = data[data["seed"] == seed]
        for predictor, group in seed_data.groupby("predictor"):
            ax.plot(
                group["model2_epoch"],
                group["underestimation_fraction"],
                marker="o",
                linewidth=1.6,
                color=MODEL_COLORS.get(predictor),
                label=predictor,
            )
        ax.set_title(f"seed {seed}")
        ax.set_xlabel("Epoch")
        ax.grid(True, alpha=0.35)
    axes[0].set_ylabel("Underestimation fraction on basin top 1% hours")
    axes[-1].legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=8)
    fig.tight_layout()
    fig.savefig(charts_dir / "top1_underestimation_fraction_by_epoch.png", dpi=170)
    plt.close(fig)


def _plot_primary_rel_bias(summary: pd.DataFrame, charts_dir: Path) -> None:
    data = summary[(summary["comparison"] == "primary") & (summary["stratum"].isin(["basin_top1", "observed_peak_hour"]))]
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), sharey=True)
    for ax, stratum in zip(axes, ["basin_top1", "observed_peak_hour"], strict=True):
        subset = data[data["stratum"] == stratum]
        pivot = subset.pivot(index="seed", columns="predictor", values="median_rel_bias_pct")
        pivot = pivot[[label for _col, label in PREDICTORS]]
        x = np.arange(len(pivot.index))
        width = 0.16
        for i, predictor in enumerate(pivot.columns):
            ax.bar(x + (i - 2) * width, pivot[predictor], width=width, color=MODEL_COLORS.get(predictor), label=predictor)
        ax.axhline(0, color="#111111", linewidth=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels(pivot.index)
        ax.set_title(stratum)
        ax.set_xlabel("Seed")
        ax.grid(True, axis="y", alpha=0.3)
    axes[0].set_ylabel("Median relative bias (%)")
    axes[-1].legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=8)
    fig.tight_layout()
    fig.savefig(charts_dir / "primary_peak_relative_bias_by_seed.png", dpi=170)
    plt.close(fig)


def _plot_gap_growth(gaps: pd.DataFrame, charts_dir: Path) -> None:
    data = gaps[(gaps["comparison"] == "same_epoch") & (gaps["stratum"] == "basin_top1")]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    for seed, group in data.groupby("seed"):
        ax.plot(group["model2_epoch"], group["median_q99_minus_q50_pct_obs"], marker="o", linewidth=1.7, label=f"seed {seed}")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Median (q99 - q50) / observed (%) on basin top 1%")
    ax.grid(True, alpha=0.35)
    ax.legend()
    fig.tight_layout()
    fig.savefig(charts_dir / "top1_q99_q50_gap_pct_obs_by_epoch.png", dpi=170)
    plt.close(fig)


def _write_markdown(
    *,
    out_path: Path,
    aggregate: pd.DataFrame,
    gap_aggregate: pd.DataFrame,
    sanity: pd.DataFrame,
) -> None:
    def table(df: pd.DataFrame, cols: list[str]) -> str:
        if df.empty:
            return "_No rows._"
        rendered = df[cols].copy()
        for col in rendered.columns:
            if pd.api.types.is_float_dtype(rendered[col]):
                rendered[col] = rendered[col].map(lambda value: "" if pd.isna(value) else f"{value:.3f}")
            else:
                rendered[col] = rendered[col].astype(str)
        widths = {
            col: max(len(str(col)), *(len(value) for value in rendered[col].astype(str)))
            for col in rendered.columns
        }
        header = "| " + " | ".join(str(col).ljust(widths[col]) for col in rendered.columns) + " |"
        separator = "| " + " | ".join("-" * widths[col] for col in rendered.columns) + " |"
        rows = [
            "| " + " | ".join(str(row[col]).ljust(widths[col]) for col in rendered.columns) + " |"
            for _, row in rendered.iterrows()
        ]
        return "\n".join([header, separator, *rows])

    primary_top1 = aggregate[(aggregate["comparison"] == "primary") & (aggregate["stratum"] == "basin_top1")]
    primary_peak = aggregate[(aggregate["comparison"] == "primary") & (aggregate["stratum"] == "observed_peak_hour")]
    same_top1 = aggregate[(aggregate["comparison"] == "same_epoch") & (aggregate["stratum"] == "basin_top1")]
    gap_top1 = gap_aggregate[(gap_aggregate["comparison"] == "primary") & (gap_aggregate["stratum"] == "basin_top1")]
    max_q50_diff = sanity["q50_result_max_abs_diff"].max()
    q_order_violations = int(sanity[["q90_lt_q50_rows", "q95_lt_q90_rows", "q99_lt_q95_rows"]].sum().sum())

    lines = [
        "# Subset300 Hydrograph Output Analysis",
        "",
        "This report was generated by `scripts/official/analyze_subset300_hydrograph_outputs.py`.",
        "",
        "## Sanity checks",
        "",
        f"- Required-series files checked: {len(sanity)}",
        f"- Maximum absolute difference between stored `model2_q50_result` and regenerated `q50`: {max_q50_diff:.6g}",
        f"- Quantile ordering violations (`q90 < q50`, `q95 < q90`, `q99 < q95`): {q_order_violations}",
        "",
        "## Primary Epoch, Basin Top 1% Hours",
        "",
        table(
            primary_top1,
            [
                "predictor",
                "mean_coverage_fraction",
                "mean_underestimation_fraction",
                "mean_median_rel_bias_pct",
                "mean_median_under_rel_deficit_pct",
            ],
        ),
        "",
        "## Primary Epoch, Observed Peak Hour",
        "",
        table(
            primary_peak,
            [
                "predictor",
                "mean_coverage_fraction",
                "mean_underestimation_fraction",
                "mean_median_rel_bias_pct",
                "mean_median_under_rel_deficit_pct",
            ],
        ),
        "",
        "## Same-Epoch Average, Basin Top 1% Hours",
        "",
        table(
            same_top1,
            [
                "predictor",
                "mean_coverage_fraction",
                "mean_underestimation_fraction",
                "mean_median_rel_bias_pct",
                "mean_median_under_rel_deficit_pct",
            ],
        ),
        "",
        "## Primary Quantile Gap, Basin Top 1% Hours",
        "",
        table(
            gap_top1,
            [
                "mean_median_q90_minus_q50",
                "mean_median_q95_minus_q90",
                "mean_median_q99_minus_q95",
                "mean_median_q99_minus_q50",
                "mean_median_q99_minus_q50_pct_obs",
            ],
        ),
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze subset300 hydrograph required-series outputs.")
    parser.add_argument("--input-dir", type=Path, default=Path("output/model_analysis/quantile_analysis"))
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    input_dir = args.input_dir
    output_dir = args.output_dir or input_dir / "analysis"
    charts_dir = output_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    predictor_rows: list[dict] = []
    gap_rows: list[dict] = []
    peak_frames: list[pd.DataFrame] = []
    sanity_rows: list[dict] = []

    for path in _series_files(input_dir):
        seed, epoch = _parse_series_file(path)
        print(f"Analyzing same-epoch seed {seed} epoch {epoch:03d}: {path}", flush=True)
        df = _read_same_epoch(path)
        rows, gaps, peaks = _summarize_frame(
            df,
            comparison="same_epoch",
            seed=seed,
            model1_epoch=epoch,
            model2_epoch=epoch,
        )
        predictor_rows.extend(rows)
        gap_rows.extend(gaps)
        peak_frames.append(peaks)
        sanity_rows.append(_sanity_row(df, path, seed=seed, epoch=epoch))

    for seed, (model1_epoch, model2_epoch) in PRIMARY_EPOCHS.items():
        print(f"Analyzing primary seed {seed}: Model 1 epoch {model1_epoch:03d}, Model 2 epoch {model2_epoch:03d}", flush=True)
        df = _read_primary_pair(input_dir, seed, model1_epoch, model2_epoch)
        rows, gaps, peaks = _summarize_frame(
            df,
            comparison="primary",
            seed=seed,
            model1_epoch=model1_epoch,
            model2_epoch=model2_epoch,
        )
        predictor_rows.extend(rows)
        gap_rows.extend(gaps)
        peak_frames.append(peaks)

    summary = pd.DataFrame(predictor_rows)
    gaps = pd.DataFrame(gap_rows)
    peaks = pd.concat(peak_frames, ignore_index=True)
    sanity = pd.DataFrame(sanity_rows)
    aggregate = _aggregate(summary)
    gap_aggregate = _aggregate_gaps(gaps)

    output_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_dir / "flow_strata_predictor_summary.csv", index=False)
    aggregate.to_csv(output_dir / "flow_strata_predictor_aggregate.csv", index=False)
    gaps.to_csv(output_dir / "quantile_gap_summary.csv", index=False)
    gap_aggregate.to_csv(output_dir / "quantile_gap_aggregate.csv", index=False)
    peaks.to_csv(output_dir / "observed_peak_predictions.csv", index=False)
    sanity.to_csv(output_dir / "required_series_sanity_checks.csv", index=False)

    _plot_top1_underestimation(summary, charts_dir)
    _plot_primary_rel_bias(summary, charts_dir)
    _plot_gap_growth(gaps, charts_dir)
    _write_markdown(
        out_path=output_dir / "research_interpretation_summary.md",
        aggregate=aggregate,
        gap_aggregate=gap_aggregate,
        sanity=sanity,
    )

    print(f"Wrote analysis outputs to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
