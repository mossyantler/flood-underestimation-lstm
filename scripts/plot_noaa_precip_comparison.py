#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.8",
#   "numpy>=2.0",
#   "pandas>=2.2",
# ]
# ///

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


RETURN_PERIODS = (2, 5, 10, 25, 50, 100)
DURATIONS = (1, 6, 24, 72)
NOAA14_DATASETS = ("noaa14_point", "noaa14_gridmean", "noaa14_areal_arf")
DATASET_LABELS = {
    "noaa14_point": "NOAA14 point",
    "noaa14_gridmean": "NOAA14 gridmean",
    "noaa14_areal_arf": "NOAA14 areal ARF",
    "noaa2_gridmean": "NOAA2 gridmean",
    "noaa2_areal_arf": "NOAA2 areal ARF",
}
DATASET_COLORS = {
    "noaa14_point": "#64748b",
    "noaa14_gridmean": "#2563eb",
    "noaa14_areal_arf": "#c2410c",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create NOAA precipitation-frequency comparison charts against CAMELSH prec_ari proxies."
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=Path(
            "output/basin/all/reference_comparison/noaa_prec/tables/reference_views/"
            "comparison_long_all_sources.csv"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/basin/all"),
        help="All-basin output root. Tables, figures, and metadata are written under reference_comparison/noaa_prec.",
    )
    parser.add_argument(
        "--series",
        choices=["ams", "pds"],
        default="ams",
        help="NOAA Atlas 14 time series type to plot. AMS is the primary comparison to CAMELSH annual maxima.",
    )
    return parser.parse_args()


def read_comparison(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"Input CSV not found: {path}")
    frame = pd.read_csv(path, dtype={"gauge_id": str, "huc02": str}, low_memory=False)
    required = {
        "gauge_id",
        "return_period_years",
        "duration_h",
        "noaa_dataset",
        "noaa_series",
        "camelsh_prec_mm",
        "noaa_prec_mm",
        "camelsh_to_noaa",
        "noaa_to_camelsh",
        "camelsh_minus_noaa_relative",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise SystemExit(f"Input CSV missing required columns: {missing}")
    numeric_cols = [
        "return_period_years",
        "duration_h",
        "camelsh_prec_mm",
        "noaa_prec_mm",
        "camelsh_to_noaa",
        "noaa_to_camelsh",
        "camelsh_minus_noaa_relative",
    ]
    for col in numeric_cols:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    valid = (
        frame["return_period_years"].isin(RETURN_PERIODS)
        & frame["duration_h"].isin(DURATIONS)
        & frame["camelsh_prec_mm"].notna()
        & frame["noaa_prec_mm"].notna()
        & (frame["camelsh_prec_mm"] > 0)
        & (frame["noaa_prec_mm"] > 0)
    )
    return frame.loc[valid].copy()


def summarize(long_df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        long_df.groupby(["noaa_dataset", "noaa_series", "return_period_years", "duration_h"], dropna=False)
        .agg(
            matched_count=("gauge_id", "count"),
            camelsh_prec_median_mm=("camelsh_prec_mm", "median"),
            noaa_prec_median_mm=("noaa_prec_mm", "median"),
            median_noaa_to_camelsh_ratio=("noaa_to_camelsh", "median"),
            median_camelsh_to_noaa_ratio=("camelsh_to_noaa", "median"),
            median_relative_difference=("camelsh_minus_noaa_relative", "median"),
            mean_relative_difference=("camelsh_minus_noaa_relative", "mean"),
            p10_relative_difference=("camelsh_minus_noaa_relative", lambda s: s.quantile(0.10)),
            p25_relative_difference=("camelsh_minus_noaa_relative", lambda s: s.quantile(0.25)),
            p75_relative_difference=("camelsh_minus_noaa_relative", lambda s: s.quantile(0.75)),
            p90_relative_difference=("camelsh_minus_noaa_relative", lambda s: s.quantile(0.90)),
            fraction_camelsh_below_noaa=("camelsh_minus_noaa_relative", lambda s: (s < 0).mean()),
            fraction_abs_difference_ge_25pct=("camelsh_minus_noaa_relative", lambda s: (s.abs() >= 0.25).mean()),
            fraction_abs_difference_ge_50pct=("camelsh_minus_noaa_relative", lambda s: (s.abs() >= 0.50).mean()),
        )
        .reset_index()
        .sort_values(["noaa_dataset", "noaa_series", "duration_h", "return_period_years"])
    )
    return summary


def filtered_noaa14(long_df: pd.DataFrame, dataset: str, series: str) -> pd.DataFrame:
    return long_df[(long_df["noaa_dataset"] == dataset) & (long_df["noaa_series"] == series)].copy()


def save_scatter_grid(long_df: pd.DataFrame, dataset: str, series: str, out_path: Path) -> None:
    data = filtered_noaa14(long_df, dataset, series)
    if data.empty:
        return
    fig, axes = plt.subplots(len(DURATIONS), len(RETURN_PERIODS), figsize=(22, 13), constrained_layout=True)
    for row, duration in enumerate(DURATIONS):
        for col, period in enumerate(RETURN_PERIODS):
            ax = axes[row, col]
            group = data[(data["duration_h"] == duration) & (data["return_period_years"] == period)]
            if group.empty:
                ax.set_axis_off()
                continue
            x = group["noaa_prec_mm"].to_numpy(dtype=float)
            y = group["camelsh_prec_mm"].to_numpy(dtype=float)
            lim_min = min(np.nanmin(x), np.nanmin(y)) * 0.75
            lim_max = max(np.nanmax(x), np.nanmax(y)) * 1.25
            ax.scatter(x, y, s=7, alpha=0.24, color=DATASET_COLORS.get(dataset, "#2563eb"), edgecolors="none")
            ax.plot([lim_min, lim_max], [lim_min, lim_max], color="#991b1b", linewidth=0.9, linestyle="--")
            ax.set_xscale("log")
            ax.set_yscale("log")
            ax.set_xlim(lim_min, lim_max)
            ax.set_ylim(lim_min, lim_max)
            ax.grid(True, which="both", linewidth=0.25, alpha=0.30)
            median_ratio = group["camelsh_to_noaa"].median()
            ax.set_title(f"{period}y {duration}h\nn={len(group)}, C/N={median_ratio:.2f}", fontsize=9)
            if row == len(DURATIONS) - 1:
                ax.set_xlabel("NOAA precip depth (mm)", fontsize=8)
            if col == 0:
                ax.set_ylabel("CAMELSH prec_ari (mm)", fontsize=8)
            ax.tick_params(labelsize=7)
    label = DATASET_LABELS.get(dataset, dataset)
    fig.suptitle(f"CAMELSH Precipitation Proxy vs {label} ({series.upper()})", fontsize=15)
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def save_boxplot_grid(long_df: pd.DataFrame, dataset: str, series: str, out_path: Path) -> None:
    data = filtered_noaa14(long_df, dataset, series)
    if data.empty:
        return
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), constrained_layout=True)
    axes = axes.ravel()
    for ax, duration in zip(axes, DURATIONS):
        boxes = []
        labels = []
        for period in RETURN_PERIODS:
            values = data[
                (data["duration_h"] == duration) & (data["return_period_years"] == period)
            ]["camelsh_minus_noaa_relative"].dropna()
            boxes.append(values.to_numpy(dtype=float) * 100)
            labels.append(str(period))
        box = ax.boxplot(boxes, tick_labels=labels, patch_artist=True, showfliers=True)
        for patch in box["boxes"]:
            patch.set_facecolor(DATASET_COLORS.get(dataset, "#8ecae6"))
            patch.set_edgecolor("#334155")
            patch.set_alpha(0.70)
        for median in box["medians"]:
            median.set_color("#111827")
            median.set_linewidth(1.8)
        for flier in box["fliers"]:
            flier.set_marker(".")
            flier.set_markeredgecolor("#64748b")
            flier.set_alpha(0.22)
        ax.axhline(0, color="#1f2937", linewidth=0.9, linestyle="--")
        ax.set_title(f"{duration}h duration")
        ax.set_xlabel("Return period (years)")
        ax.set_ylabel("(CAMELSH - NOAA) / NOAA (%)")
        ax.grid(axis="y", linewidth=0.35, alpha=0.35)
    label = DATASET_LABELS.get(dataset, dataset)
    fig.suptitle(f"Relative Difference Distribution: {label} ({series.upper()})", fontsize=15)
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def save_source_median_trend(summary: pd.DataFrame, series: str, out_path: Path) -> None:
    data = summary[(summary["noaa_series"] == series) & (summary["noaa_dataset"].isin(NOAA14_DATASETS))]
    if data.empty:
        return
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), constrained_layout=True)
    axes = axes.ravel()
    for ax, duration in zip(axes, DURATIONS):
        for dataset in NOAA14_DATASETS:
            group = data[(data["duration_h"] == duration) & (data["noaa_dataset"] == dataset)].sort_values(
                "return_period_years"
            )
            if group.empty:
                continue
            ax.plot(
                group["return_period_years"],
                group["median_relative_difference"] * 100,
                marker="o",
                linewidth=2.0,
                color=DATASET_COLORS.get(dataset, None),
                label=DATASET_LABELS.get(dataset, dataset),
            )
        ax.axhline(0, color="#1f2937", linewidth=0.9, linestyle="--")
        ax.set_xscale("log")
        ax.set_xticks(list(RETURN_PERIODS))
        ax.set_xticklabels([str(period) for period in RETURN_PERIODS])
        ax.set_title(f"{duration}h duration")
        ax.set_xlabel("Return period (years)")
        ax.set_ylabel("Median relative difference (%)")
        ax.grid(True, linewidth=0.35, alpha=0.35)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncols=3, frameon=False, bbox_to_anchor=(0.5, 1.03))
    fig.suptitle(f"Median CAMELSH-vs-NOAA Difference by Duration ({series.upper()})", fontsize=15)
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_margin_median_trend(summary: pd.DataFrame, dataset: str, series: str, out_path: Path) -> None:
    data = summary[(summary["noaa_dataset"] == dataset) & (summary["noaa_series"] == series)]
    if data.empty:
        return
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), constrained_layout=True)
    axes = axes.ravel()
    color = DATASET_COLORS.get(dataset, "#2563eb")
    for ax, duration in zip(axes, DURATIONS):
        group = data[data["duration_h"] == duration].sort_values("return_period_years")
        if group.empty:
            ax.set_axis_off()
            continue
        x = group["return_period_years"].to_numpy(dtype=float)
        median = group["median_relative_difference"].to_numpy(dtype=float) * 100
        p10 = group["p10_relative_difference"].to_numpy(dtype=float) * 100
        p25 = group["p25_relative_difference"].to_numpy(dtype=float) * 100
        p75 = group["p75_relative_difference"].to_numpy(dtype=float) * 100
        p90 = group["p90_relative_difference"].to_numpy(dtype=float) * 100
        ax.fill_between(x, p10, p90, color=color, alpha=0.14, label="P10-P90")
        ax.fill_between(x, p25, p75, color=color, alpha=0.26, label="IQR")
        ax.plot(x, median, marker="o", color=color, linewidth=2.2, label="Median")
        ax.axhline(0, color="#1f2937", linewidth=0.9, linestyle="--")
        ax.set_xscale("log")
        ax.set_xticks(list(RETURN_PERIODS))
        ax.set_xticklabels([str(period) for period in RETURN_PERIODS])
        ax.set_title(f"{duration}h duration")
        ax.set_xlabel("Return period (years)")
        ax.set_ylabel("Relative difference (%)")
        ax.grid(True, linewidth=0.35, alpha=0.35)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncols=3, frameon=False, bbox_to_anchor=(0.5, 1.03))
    label = DATASET_LABELS.get(dataset, dataset)
    fig.suptitle(f"Median Relative Difference with Basin Spread: {label} ({series.upper()})", fontsize=15)
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_heatmap(summary: pd.DataFrame, dataset: str, series: str, out_path: Path) -> None:
    data = summary[(summary["noaa_dataset"] == dataset) & (summary["noaa_series"] == series)]
    if data.empty:
        return
    pivot = data.pivot(index="duration_h", columns="return_period_years", values="median_relative_difference")
    pivot = pivot.reindex(index=list(DURATIONS), columns=list(RETURN_PERIODS))
    values = pivot.to_numpy(dtype=float) * 100
    finite = values[np.isfinite(values)]
    limit = max(20.0, float(np.nanmax(np.abs(finite))) if finite.size else 20.0)
    limit = min(max(limit, 40.0), 90.0)

    fig, ax = plt.subplots(figsize=(10.5, 5.8), constrained_layout=True)
    image = ax.imshow(values, cmap="RdBu", vmin=-limit, vmax=limit, aspect="auto")
    ax.set_xticks(np.arange(len(RETURN_PERIODS)), labels=[str(period) for period in RETURN_PERIODS])
    ax.set_yticks(np.arange(len(DURATIONS)), labels=[f"{duration}h" for duration in DURATIONS])
    ax.set_xlabel("Return period (years)")
    ax.set_ylabel("Duration")
    label = DATASET_LABELS.get(dataset, dataset)
    ax.set_title(f"Median Relative Difference Heatmap: {label} ({series.upper()})")
    for row in range(values.shape[0]):
        for col in range(values.shape[1]):
            value = values[row, col]
            if np.isfinite(value):
                ax.text(col, row, f"{value:.0f}%", ha="center", va="center", fontsize=9, color="#111827")
    cbar = fig.colorbar(image, ax=ax)
    cbar.set_label("(CAMELSH - NOAA) / NOAA (%)")
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def save_atlas2_fallback_chart(summary: pd.DataFrame, out_path: Path) -> None:
    data = summary[
        (summary["noaa_series"] == "atlas2")
        & (summary["noaa_dataset"].isin(["noaa2_gridmean", "noaa2_areal_arf"]))
    ].copy()
    if data.empty:
        return
    data["label"] = (
        data["return_period_years"].astype(int).astype(str)
        + "y "
        + data["duration_h"].astype(int).astype(str)
        + "h"
    )
    labels = ["2y 6h", "2y 24h", "100y 6h", "100y 24h"]
    fig, ax = plt.subplots(figsize=(10.5, 5.8), constrained_layout=True)
    x = np.arange(len(labels))
    width = 0.36
    for offset, dataset in [(-width / 2, "noaa2_gridmean"), (width / 2, "noaa2_areal_arf")]:
        group = data[data["noaa_dataset"] == dataset].set_index("label").reindex(labels)
        ax.bar(
            x + offset,
            group["median_relative_difference"].to_numpy(dtype=float) * 100,
            width=width,
            color=DATASET_COLORS.get("noaa14_areal_arf" if "areal" in dataset else "noaa14_gridmean"),
            alpha=0.80,
            label=DATASET_LABELS[dataset],
        )
    ax.axhline(0, color="#1f2937", linewidth=0.9, linestyle="--")
    ax.set_xticks(x, labels)
    ax.set_ylabel("Median relative difference (%)")
    ax.set_title("NOAA Atlas 2 Fallback Basins: Median CAMELSH-vs-NOAA Difference")
    ax.grid(axis="y", linewidth=0.35, alpha=0.35)
    ax.legend(frameon=False)
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def write_chart_guide(out_dir: Path, series: str) -> None:
    guide = f"""# NOAA Precipitation Comparison Charts

이 폴더는 CAMELSH `prec_ari*` proxy와 NOAA precipitation-frequency reference를 비교하는 chart 묶음이다. 기본 chart series는 `{series.upper()}`다. CAMELSH `prec_ari*`가 annual-maxima Gumbel proxy라서, NOAA Atlas 14 중에서는 `AMS`가 primary comparison이다.

## Chart Types

1. `scatter_grid_{series}_*.png`

각 점은 하나의 basin이다. x축은 NOAA precipitation depth, y축은 CAMELSH `prec_ari`이고 둘 다 log scale이다. 빨간 점선은 1:1 line이다. 점들이 선 아래에 있으면 CAMELSH proxy가 NOAA보다 작고, 선 위에 있으면 CAMELSH proxy가 NOAA보다 크다. 개별 basin outlier와 전체 scale 차이를 보기에 좋다.

2. `relative_difference_boxplot_{series}_*.png`

y축은 `(CAMELSH - NOAA) / NOAA`를 percent로 표시한 값이다. 0보다 아래면 CAMELSH가 NOAA보다 작다. box는 basin별 차이의 분포를 보여주므로, median뿐 아니라 basin 간 spread가 큰지도 확인할 수 있다.

3. `median_relative_difference_trend_by_duration_{series}.png`

duration별 panel 안에서 return period가 커질 때 median 차이가 어떻게 변하는지 보여준다. 한 그림 안에 NOAA point, gridmean, areal-ARF를 같이 그려서 ARF 적용이 차이를 얼마나 줄이는지 비교할 수 있다. 여러 NOAA source를 겹쳐 보여주는 비교 chart라 P10-P90/IQR margin은 일부러 넣지 않았다.

4. `relative_difference_median_trend_with_margin_{series}_*.png`

USGS peak-flow chart처럼 median line 주변에 P10-P90과 IQR band를 넣은 chart다. Band가 겹치지 않도록 NOAA source별로 따로 만든다. median trend와 basin 간 spread를 동시에 볼 때 사용한다.

5. `median_relative_difference_heatmap_{series}_*.png`

duration x return period 표 형태의 heatmap이다. 색과 숫자가 median relative difference를 뜻한다. 여러 return period와 duration을 한눈에 보는 데 가장 빠르다.

6. `atlas2_fallback_median_relative_difference.png`

Atlas 14 project area 밖 Oregon/Washington basin에 대해 NOAA Atlas 2 fallback만 따로 본 chart다. Atlas 2는 2/100-year 6/24h 조합만 제공하므로 chart 축이 제한적이다.

## Interpretation Note

`noaa14_point`는 공식 point estimate, `noaa14_gridmean`은 NOAA GIS grid를 CAMELSH/NLDAS basin mask cell에서 평균한 derived reference, `noaa14_areal_arf`는 HEC-HMS TP-40/TP-49 areal reduction curve를 근사 적용한 supplementary reference다. `noaa14_areal_arf`는 공식 NOAA product가 아니라 sensitivity comparison으로만 해석한다.
"""
    (out_dir / "chart_guide.md").write_text(guide, encoding="utf-8")


def main() -> None:
    args = parse_args()
    table_dir = args.output_dir / "reference_comparison" / "noaa_prec" / "tables"
    figure_dir = args.output_dir / "reference_comparison" / "noaa_prec" / "figures"
    metadata_dir = args.output_dir / "reference_comparison" / "noaa_prec" / "metadata"
    table_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    long_df = read_comparison(args.input_csv)
    summary = summarize(long_df)
    summary_path = table_dir / "noaa_precip_comparison_summary.csv"
    filtered_path = table_dir / "noaa_precip_comparison_long.csv"
    long_df.to_csv(filtered_path, index=False)
    summary.to_csv(summary_path, index=False)

    for dataset in NOAA14_DATASETS:
        save_scatter_grid(
            long_df,
            dataset,
            args.series,
            figure_dir / f"scatter_grid_{args.series}_{dataset}.png",
        )
        save_boxplot_grid(
            long_df,
            dataset,
            args.series,
            figure_dir / f"relative_difference_boxplot_{args.series}_{dataset}.png",
        )
        save_heatmap(
            summary,
            dataset,
            args.series,
            figure_dir / f"median_relative_difference_heatmap_{args.series}_{dataset}.png",
        )
        save_margin_median_trend(
            summary,
            dataset,
            args.series,
            figure_dir / f"relative_difference_median_trend_with_margin_{args.series}_{dataset}.png",
        )
    save_source_median_trend(
        summary,
        args.series,
        figure_dir / f"median_relative_difference_trend_by_duration_{args.series}.png",
    )
    save_atlas2_fallback_chart(summary, figure_dir / "atlas2_fallback_median_relative_difference.png")
    write_chart_guide(metadata_dir, args.series)

    print(f"Wrote long table: {filtered_path}")
    print(f"Wrote summary: {summary_path}")
    print(f"Wrote charts: {figure_dir}")
    preview = summary[
        (summary["noaa_series"] == args.series)
        & (summary["noaa_dataset"].isin(NOAA14_DATASETS))
        & (summary["return_period_years"].isin([2, 100]))
        & (summary["duration_h"].isin([1, 24]))
    ]
    print(preview.to_string(index=False, float_format=lambda value: f"{value:.4f}"))


if __name__ == "__main__":
    main()
