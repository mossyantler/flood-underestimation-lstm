#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.8",
#   "pandas>=2.2",
#   "pyyaml>=6.0",
#   "xarray>=2024.1",
#   "netcdf4>=1.7",
# ]
# ///
"""Plot train/validation/test time-series coverage for the fixed main split.

Each split gets its own chart. Daily color intensity follows the fraction of
valid Streamflow hours on that day. Blank cells indicate no valid target data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "configs/pilot/camelsh_hourly_model1_drbc_holdout_scaling_300.yml"
DEFAULT_PREPARED_MANIFEST = (
    REPO_ROOT / "data/CAMELSH_generic/drbc_holdout_broad/splits/split_manifest.csv"
)
DEFAULT_SCALING_MANIFEST = REPO_ROOT / "configs/pilot/basin_splits/scaling_300/manifest.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/basin/timeseries"

SPLIT_ORDER = ("train", "validation", "test")
SPLIT_LABELS = {
    "train": "Train",
    "validation": "Validation",
    "test": "Test",
}
COVERAGE_DIR_NAMES = {
    "input": "input_coverage",
    "target": "target_coverage",
}
COLORS = {
    "train": "#2F6BAA",
    "validation": "#C96E2C",
    "test": "#3B8C59",
}
BG = "#F7F8FA"
GRID = "#D2D6DC"
TEXT = "#20242A"
MUTED = "#6A717A"


def hex_to_rgb(color: str) -> tuple[float, float, float]:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) / 255 for i in (0, 2, 4))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create basin-level time-series coverage charts for the current "
            "fixed Model 1/2 experiment split."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="NeuralHydrology config whose split files and dates should be visualized.",
    )
    parser.add_argument(
        "--prepared-manifest",
        type=Path,
        default=DEFAULT_PREPARED_MANIFEST,
        help="Prepared broad split manifest with official split membership metadata.",
    )
    parser.add_argument(
        "--scaling-manifest",
        type=Path,
        default=DEFAULT_SCALING_MANIFEST,
        help="Fixed 300-basin train/validation manifest with basin names and attributes.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where charts and span tables will be written.",
    )
    parser.add_argument(
        "--target-variable",
        default="Streamflow",
        help="Target variable used to compute available and used spans.",
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        default=["png", "svg"],
        choices=["png", "svg", "pdf"],
        help="Figure formats to save.",
    )
    parser.add_argument(
        "--chart-kind",
        choices=["target", "input", "both"],
        default="target",
        help=(
            "Which charts to write. `target` writes target_coverage outputs; "
            "`input` writes input_coverage outputs without overwriting target charts."
        ),
    )
    parser.add_argument(
        "--overview-only",
        action="store_true",
        help="Only rewrite the compact overview chart; leave split charts, span CSVs, and manifests untouched.",
    )
    return parser.parse_args()


def resolve_path(path_like: str | Path, base: Path = REPO_ROOT) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    return base / path


def coverage_output_dirs(output_dir: Path, chart_kind: str) -> dict[str, Path]:
    kind_root = output_dir / COVERAGE_DIR_NAMES[chart_kind]
    return {
        "root": kind_root,
        "figures": kind_root / "figures",
        "tables": kind_root / "tables",
        "metadata": kind_root / "metadata",
    }


def read_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fp:
        config = yaml.safe_load(fp)
    if not isinstance(config, dict):
        raise ValueError(f"Config did not parse as a mapping: {path}")
    return config


def parse_config_date(value: str) -> pd.Timestamp:
    return pd.to_datetime(value, dayfirst=True)


def read_basin_file(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def split_periods_from_config(config: dict[str, Any]) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    periods: dict[str, tuple[pd.Timestamp, pd.Timestamp]] = {}
    for split in SPLIT_ORDER:
        start_key = f"{split}_start_date"
        end_key = f"{split}_end_date"
        periods[split] = (
            parse_config_date(config[start_key]),
            parse_config_date(config[end_key]),
        )
    return periods


def split_files_from_config(config: dict[str, Any]) -> dict[str, Path]:
    return {
        "train": resolve_path(config["train_basin_file"]),
        "validation": resolve_path(config["validation_basin_file"]),
        "test": resolve_path(config["test_basin_file"]),
    }


def load_base_manifest(
    prepared_manifest_path: Path,
    scaling_manifest_path: Path,
    split_files: dict[str, Path],
    periods: dict[str, tuple[pd.Timestamp, pd.Timestamp]],
) -> pd.DataFrame:
    prepared = pd.read_csv(prepared_manifest_path, dtype={"gauge_id": str})
    scaling = pd.read_csv(scaling_manifest_path, dtype={"gauge_id": str})

    optional_cols = [
        "gauge_id",
        "state",
        "gauge_name",
        "camelsh_huc02",
        "drain_sqkm_attr",
        "area",
        "slope",
        "aridity",
        "snow_fraction",
        "soil_depth",
        "permeability",
        "forest_fraction",
        "baseflow_index",
    ]
    optional_cols = [col for col in optional_cols if col in scaling.columns]
    scaling = scaling[optional_cols].drop_duplicates("gauge_id")

    rows: list[pd.DataFrame] = []
    for split in SPLIT_ORDER:
        basin_ids = read_basin_file(split_files[split])
        selected = prepared[prepared["gauge_id"].isin(basin_ids)].copy()
        missing = sorted(set(basin_ids) - set(selected["gauge_id"]))
        if missing:
            raise ValueError(f"{split} basin ids missing from prepared manifest: {missing[:10]}")

        selected["split"] = split
        selected["configured_start"] = periods[split][0]
        selected["configured_end"] = periods[split][1]
        selected["_order"] = selected["gauge_id"].map({gid: i for i, gid in enumerate(basin_ids)})
        selected = selected.merge(scaling, on="gauge_id", how="left")
        rows.append(selected)

    return pd.concat(rows, ignore_index=True)


def get_timeseries_dir(config: dict[str, Any]) -> Path:
    return resolve_path(config["data_dir"]) / "time_series"


def compute_streamflow_spans(
    manifest: pd.DataFrame,
    timeseries_dir: Path,
    target_variable: str,
    dynamic_inputs: list[str],
    seq_length: int,
    predict_last_n: int,
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for row in manifest.itertuples(index=False):
        gauge_id = row.gauge_id
        split = row.split
        start = pd.Timestamp(row.configured_start)
        end = pd.Timestamp(row.configured_end)
        path = timeseries_dir / f"{gauge_id}.nc"
        if not path.exists():
            raise FileNotFoundError(f"Missing time-series file for {gauge_id}: {path}")

        ds = xr.open_dataset(path)
        try:
            if target_variable not in ds:
                raise KeyError(f"{target_variable!r} not found in {path}")
            missing_dynamic = [var for var in dynamic_inputs if var not in ds]
            if missing_dynamic:
                raise KeyError(f"Dynamic inputs missing from {path}: {missing_dynamic}")
            target = ds[target_variable]
            date_values = target["date"].values
            target_values = np.asarray(target.values)
            valid_mask = np.isfinite(target_values)
            dynamic_values = np.column_stack([np.asarray(ds[var].values) for var in dynamic_inputs])
            dynamic_nan_mask = np.isnan(dynamic_values).any(axis=1)
            overall_valid_count = int(valid_mask.sum())
            if overall_valid_count == 0:
                overall_start = pd.NaT
                overall_end = pd.NaT
                used_start = pd.NaT
                used_end = pd.NaT
                used_valid_count = 0
                window_mask = (date_values >= np.datetime64(start)) & (date_values <= np.datetime64(end))
                used_possible_count = int(window_mask.sum())
            else:
                valid_dates = date_values[valid_mask]
                overall_start = pd.Timestamp(valid_dates[0])
                overall_end = pd.Timestamp(valid_dates[-1])

                window_mask = (date_values >= np.datetime64(start)) & (date_values <= np.datetime64(end))
                used_possible_count = int(window_mask.sum())
                used_mask = valid_mask & window_mask
                used_valid_count = int(used_mask.sum())
                if used_valid_count:
                    used_dates = date_values[used_mask]
                    used_start = pd.Timestamp(used_dates[0])
                    used_end = pd.Timestamp(used_dates[-1])
                else:
                    used_start = pd.NaT
                    used_end = pd.NaT
            daily_coverage = compute_daily_coverage(date_values, valid_mask)
            input_used_mask, valid_model_sample_count = compute_model_input_used_mask(
                date_values=date_values,
                dynamic_nan_mask=dynamic_nan_mask,
                target_valid_mask=valid_mask,
                start=start,
                end=end,
                split=split,
                seq_length=seq_length,
                predict_last_n=predict_last_n,
            )
            daily_model_input_coverage = compute_daily_coverage(date_values, input_used_mask)
            input_dates = date_values[input_used_mask]
            if len(input_dates) > 0:
                model_input_start = pd.Timestamp(input_dates[0])
                model_input_end = pd.Timestamp(input_dates[-1])
            else:
                model_input_start = pd.NaT
                model_input_end = pd.NaT
        finally:
            ds.close()

        records.append(
            {
                "gauge_id": gauge_id,
                "split": split,
                "target_variable": target_variable,
                "timeseries_path": str(path.relative_to(REPO_ROOT)),
                "overall_start": overall_start,
                "overall_end": overall_end,
                "overall_valid_target_count": overall_valid_count,
                "used_start": used_start,
                "used_end": used_end,
                "used_valid_target_count": used_valid_count,
                "used_possible_target_count": used_possible_count,
                "used_coverage_fraction": (
                    used_valid_count / used_possible_count if used_possible_count else 0.0
                ),
                "daily_coverage": daily_coverage,
                "model_input_start": model_input_start,
                "model_input_end": model_input_end,
                "model_input_hour_count": int(input_used_mask.sum()),
                "valid_model_sample_count": int(valid_model_sample_count),
                "daily_model_input_coverage": daily_model_input_coverage,
            }
        )

    spans = pd.DataFrame.from_records(records)
    return manifest.merge(spans, on=["gauge_id", "split"], how="left")


def rolling_sum(mask: np.ndarray, window: int) -> np.ndarray:
    values = mask.astype(np.int64)
    cumsum = np.concatenate(([0], np.cumsum(values)))
    out = np.full(len(values), -1, dtype=np.int64)
    if window <= len(values):
        out[window - 1 :] = cumsum[window:] - cumsum[:-window]
    return out


def compute_model_input_used_mask(
    date_values: np.ndarray,
    dynamic_nan_mask: np.ndarray,
    target_valid_mask: np.ndarray,
    start: pd.Timestamp,
    end: pd.Timestamp,
    split: str,
    seq_length: int,
    predict_last_n: int,
) -> tuple[np.ndarray, int]:
    period_mask = (date_values >= np.datetime64(start)) & (date_values <= np.datetime64(end))
    positions = np.arange(len(date_values))
    enough_history = positions >= seq_length - 1

    if split == "train":
        dynamic_nan_count = rolling_sum(dynamic_nan_mask, seq_length)
        target_valid_count = rolling_sum(target_valid_mask, predict_last_n)
        sample_mask = (
            period_mask
            & enough_history
            & (dynamic_nan_count == 0)
            & (target_valid_count > 0)
        )
    else:
        # During validation/test, NeuralHydrology builds evaluation samples for all
        # timesteps with sufficient history. Target NaNs are masked later in metrics.
        sample_mask = period_mask & enough_history

    sample_positions = np.flatnonzero(sample_mask)
    input_used_mask = np.zeros(len(date_values), dtype=bool)
    if len(sample_positions) == 0:
        return input_used_mask, 0

    diff = np.zeros(len(date_values) + 1, dtype=np.int64)
    starts = sample_positions - seq_length + 1
    ends = sample_positions + 1
    np.add.at(diff, starts, 1)
    np.add.at(diff, ends, -1)
    input_used_mask = np.cumsum(diff[:-1]) > 0
    return input_used_mask, int(len(sample_positions))


def compute_daily_coverage(date_values: np.ndarray, valid_mask: np.ndarray) -> pd.Series:
    day_values = date_values.astype("datetime64[D]")

    # CAMELSH prepared files are regular hourly series from midnight, so this
    # fast path avoids a costly xarray resample for every basin.
    if len(day_values) % 24 == 0:
        first_hours = date_values[::24].astype("datetime64[h]")
        expected_hours = (
            first_hours[0]
            + np.arange(len(first_hours), dtype="timedelta64[D]")
        ).astype("datetime64[h]")
        if np.array_equal(first_hours, expected_hours):
            coverage = valid_mask.reshape(-1, 24).mean(axis=1)
            return pd.Series(coverage, index=pd.DatetimeIndex(day_values[::24]))

    unique_days, inverse = np.unique(day_values, return_inverse=True)
    valid_counts = np.bincount(inverse, weights=valid_mask.astype(float))
    total_counts = np.bincount(inverse)
    coverage = valid_counts / total_counts
    return pd.Series(coverage, index=pd.DatetimeIndex(unique_days))


def date_num(value: pd.Timestamp) -> float:
    return mdates.date2num(value.to_pydatetime())


def draw_daily_coverage_image(
    ax: plt.Axes,
    split_df: pd.DataFrame,
    color: str,
    configured_start: pd.Timestamp,
    configured_end: pd.Timestamp,
    x_start: pd.Timestamp,
    x_end: pd.Timestamp,
    *,
    inside_alpha_range: tuple[float, float] = (0.22, 0.96),
    outside_alpha_range: tuple[float, float] = (0.08, 0.34),
    row_pixels: int = 8,
    active_pixels: int = 5,
    coverage_col: str = "daily_coverage",
) -> None:
    date_index = pd.date_range(x_start.normalize(), x_end.normalize(), freq="D")
    if len(date_index) == 0:
        return

    rgb = hex_to_rgb(color)
    n_rows = len(split_df) * row_pixels
    row_pad_before = (row_pixels - active_pixels) // 2
    image = np.zeros((n_rows, len(date_index), 4), dtype=float)
    image[:, :, 0] = rgb[0]
    image[:, :, 1] = rgb[1]
    image[:, :, 2] = rgb[2]

    inside_mask = (date_index >= configured_start.normalize()) & (
        date_index <= configured_end.normalize()
    )
    outside_min, outside_max = outside_alpha_range
    inside_min, inside_max = inside_alpha_range

    for row_idx, row in enumerate(split_df.itertuples(index=False)):
        coverage = getattr(row, coverage_col).reindex(date_index, fill_value=0.0).to_numpy()
        coverage = coverage.clip(0.0, 1.0)
        alpha = np.zeros_like(coverage, dtype=float)
        outside = (coverage > 0) & ~inside_mask
        inside = (coverage > 0) & inside_mask
        alpha[outside] = outside_min + (outside_max - outside_min) * coverage[outside]
        alpha[inside] = inside_min + (inside_max - inside_min) * coverage[inside]
        y0 = row_idx * row_pixels + row_pad_before
        y1 = y0 + active_pixels
        image[y0:y1, :, 3] = alpha

    ax.imshow(
        image,
        aspect="auto",
        interpolation="none",
        extent=(
            date_num(date_index[0]),
            date_num(date_index[-1] + pd.Timedelta(days=1)),
            len(split_df) - 0.5,
            -0.5,
        ),
        zorder=2,
    )


def plot_split(
    df: pd.DataFrame,
    split: str,
    output_dir: Path,
    formats: list[str],
    *,
    chart_kind: str = "target",
) -> dict[str, str]:
    split_df = df[df["split"] == split].copy()
    split_df = split_df.sort_values(
        ["overall_start", "overall_end", "_order", "gauge_id"],
        na_position="last",
    ).reset_index(drop=True)

    n = len(split_df)
    color = COLORS[split]
    label = SPLIT_LABELS[split]
    height = max(8.5, n * 0.17 + 3.2)
    fig, ax = plt.subplots(figsize=(28, height), facecolor=BG)
    ax.set_facecolor(BG)

    configured_start = pd.Timestamp(split_df["configured_start"].iloc[0])
    configured_end = pd.Timestamp(split_df["configured_end"].iloc[0])

    ax.axvspan(
        configured_start,
        configured_end,
        color=color,
        alpha=0.075,
        zorder=0,
        label="Configured split window",
    )
    ax.axvline(configured_start, color=color, alpha=0.45, lw=1.0, linestyle="--", zorder=1)
    ax.axvline(configured_end, color=color, alpha=0.45, lw=1.0, linestyle="--", zorder=1)

    for idx in range(n):
        if idx % 2 == 0:
            ax.axhspan(idx - 0.5, idx + 0.5, color="white", alpha=0.34, zorder=0.2)

    if chart_kind == "input":
        x_start = pd.Timestamp(split_df["model_input_start"].min()).floor("D") - pd.Timedelta(days=3)
        x_end = pd.Timestamp(split_df["model_input_end"].max()).ceil("D") + pd.Timedelta(days=3)
    else:
        x_start = pd.Timestamp(split_df["overall_start"].min()).floor("D") - pd.Timedelta(days=180)
        x_end = pd.Timestamp(split_df["overall_end"].max()).ceil("D") + pd.Timedelta(days=180)
    draw_daily_coverage_image(
        ax=ax,
        split_df=split_df,
        color=color,
        configured_start=configured_start,
        configured_end=configured_end,
        x_start=x_start,
        x_end=x_end,
        coverage_col="daily_model_input_coverage" if chart_kind == "input" else "daily_coverage",
    )

    no_used = split_df["used_valid_target_count"] == 0
    if no_used.any():
        ax.scatter(
            [configured_start] * int(no_used.sum()),
            split_df.index[no_used],
            s=11,
            color="#B33A3A",
            zorder=4,
        )

    ax.set_xlim(x_start, x_end)
    ax.set_ylim(-0.8, n - 0.2)
    ax.invert_yaxis()

    for idx in range(n + 1):
        ax.axhline(idx - 0.5, color="#E5E8ED", lw=0.35, zorder=1.5)

    ax.xaxis.set_major_locator(mdates.YearLocator(base=5))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_minor_locator(mdates.YearLocator(base=1))
    ax.grid(axis="x", which="major", color=GRID, lw=0.8, alpha=0.8)
    ax.grid(axis="x", which="minor", color=GRID, lw=0.35, alpha=0.45)
    ax.tick_params(axis="x", labelsize=9, colors=MUTED)
    ax.tick_params(axis="y", length=0, pad=6)

    y_fontsize = 6.2 if n > 80 else 7.4
    y_labels = split_df["gauge_id"].tolist()
    ax.set_yticks(range(n))
    ax.set_yticklabels(y_labels, fontsize=y_fontsize, color=TEXT)

    for spine in ax.spines.values():
        spine.set_edgecolor(GRID)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    full_start = split_df["overall_start"].min()
    full_end = split_df["overall_end"].max()
    if chart_kind == "input":
        total_hours = int(split_df["model_input_hour_count"].sum())
        valid_samples = int(split_df["valid_model_sample_count"].sum())
        input_start = split_df["model_input_start"].min()
        input_end = split_df["model_input_end"].max()
        title = f"{label} Split Input Coverage"
        subtitle = (
            f"n={n} basins | model input union: "
            f"{input_start:%Y-%m-%d %H:%M} to {input_end:%Y-%m-%d %H:%M} | "
            f"configured target window: {configured_start:%Y-%m-%d} to {configured_end:%Y-%m-%d} | "
            f"input hours in valid/evaluated sequences: {total_hours:,} | samples: {valid_samples:,}"
        )
    else:
        total_hours = int(split_df["used_valid_target_count"].sum())
        possible_hours = int(split_df["used_possible_target_count"].sum())
        coverage_pct = total_hours / possible_hours * 100 if possible_hours else 0.0
        title = f"{label} Split Target Coverage"
        subtitle = (
            f"n={n} basins | available Streamflow span: "
            f"{full_start:%Y-%m-%d} to {full_end:%Y-%m-%d} | "
            f"configured window: {configured_start:%Y-%m-%d} to {configured_end:%Y-%m-%d} | "
            f"used target hours: {total_hours:,}/{possible_hours:,} ({coverage_pct:.1f}%)"
        )
    top_margin = 1.12
    fig.suptitle(
        title,
        y=1 - 0.08 / height,
        fontsize=15,
        fontweight="bold",
        color=TEXT,
    )
    fig.text(
        0.5,
        1 - 0.34 / height,
        subtitle,
        ha="center",
        va="center",
        fontsize=9,
        color=MUTED,
    )
    ax.set_xlabel("Calendar year", fontsize=10, color=MUTED)
    ax.set_ylabel("Basin gauge_id", fontsize=10, color=MUTED)

    if chart_kind == "input":
        handles = [
            mpatches.Patch(facecolor=color, alpha=0.34, label="Dynamic input day used as warm-up/history"),
            mpatches.Patch(facecolor=color, alpha=0.96, label="Dynamic input day inside configured target window"),
            mpatches.Patch(facecolor=color, alpha=0.075, label="Configured target split window background"),
            mpatches.Patch(facecolor=BG, edgecolor=GRID, label="Not used as model input that day"),
        ]
    else:
        handles = [
            mpatches.Patch(facecolor=color, alpha=0.34, label="Valid Streamflow day outside this split window"),
            mpatches.Patch(facecolor=color, alpha=0.96, label="Valid Streamflow day inside this split window"),
            mpatches.Patch(facecolor=color, alpha=0.075, label="Configured split window background"),
            mpatches.Patch(facecolor=BG, edgecolor=GRID, label="No valid Streamflow that day"),
        ]
    fig.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 1 - 0.86 / height),
        ncol=4,
        fontsize=8.2,
        frameon=True,
        fancybox=False,
        edgecolor=GRID,
        facecolor="white",
        borderpad=0.25,
        handlelength=1.2,
        columnspacing=1.1,
    )

    fig.tight_layout(rect=(0.03, 0, 1, 1 - top_margin / height))

    output_paths: dict[str, str] = {}
    for fmt in formats:
        out = output_dir / f"{split}.{fmt}"
        save_kwargs: dict[str, Any] = {"bbox_inches": "tight", "facecolor": BG}
        if fmt == "png":
            save_kwargs["dpi"] = 180
        fig.savefig(out, **save_kwargs)
        output_paths[fmt] = str(out.relative_to(REPO_ROOT))
    plt.close(fig)
    return output_paths


def plot_compact_overview(
    df: pd.DataFrame,
    output_dir: Path,
    formats: list[str],
    *,
    chart_kind: str = "target",
) -> dict[str, str]:
    fig, axes = plt.subplots(3, 1, figsize=(28, 11), facecolor=BG)
    fig.patch.set_facecolor(BG)
    if chart_kind == "input":
        overview_x_start = pd.Timestamp(df["model_input_start"].min()).floor("D") - pd.Timedelta(days=3)
        overview_x_end = pd.Timestamp(df["model_input_end"].max()).ceil("D") + pd.Timedelta(days=3)
    else:
        overview_x_start = pd.Timestamp(df["overall_start"].min()).floor("D") - pd.Timedelta(days=180)
        overview_x_end = pd.Timestamp(df["overall_end"].max()).ceil("D") + pd.Timedelta(days=180)

    for ax, split in zip(axes, SPLIT_ORDER):
        split_df = df[df["split"] == split].copy()
        split_df = split_df.sort_values(
            ["overall_start", "overall_end", "_order", "gauge_id"],
            na_position="last",
        ).reset_index(drop=True)
        color = COLORS[split]
        configured_start = pd.Timestamp(split_df["configured_start"].iloc[0])
        configured_end = pd.Timestamp(split_df["configured_end"].iloc[0])
        ax.set_facecolor(BG)
        ax.axvspan(configured_start, configured_end, color=color, alpha=0.075, zorder=0)
        ax.axvline(configured_start, color=color, alpha=0.45, lw=0.9, linestyle="--", zorder=1)
        ax.axvline(configured_end, color=color, alpha=0.45, lw=0.9, linestyle="--", zorder=1)

        draw_daily_coverage_image(
            ax=ax,
            split_df=split_df,
            color=color,
            configured_start=configured_start,
            configured_end=configured_end,
            x_start=overview_x_start,
            x_end=overview_x_end,
            inside_alpha_range=(0.22, 0.96),
            outside_alpha_range=(0.06, 0.28),
            row_pixels=6,
            active_pixels=4,
            coverage_col="daily_model_input_coverage" if chart_kind == "input" else "daily_coverage",
        )
        ax.set_xlim(overview_x_start, overview_x_end)
        ax.set_ylim(-0.8, len(split_df) - 0.2)
        ax.invert_yaxis()
        ax.set_yticks([])
        ax.xaxis.set_major_locator(mdates.YearLocator(base=5))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.xaxis.set_minor_locator(mdates.YearLocator(base=1))
        ax.grid(axis="x", which="major", color=GRID, lw=0.8, alpha=0.8)
        ax.grid(axis="x", which="minor", color=GRID, lw=0.35, alpha=0.45)
        ax.tick_params(axis="x", labelsize=8.5, colors=MUTED)
        for spine in ax.spines.values():
            spine.set_edgecolor(GRID)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.set_title(
            f"{SPLIT_LABELS[split]} (n={len(split_df)}, configured {configured_start:%Y-%m-%d} to {configured_end:%Y-%m-%d})",
            loc="left",
            fontsize=11,
            fontweight="bold",
            color=TEXT,
        )

    fig.suptitle(
        (
            "Train / Validation / Test Input Coverage"
            if chart_kind == "input"
            else "Train / Validation / Test Target Coverage"
        ),
        fontsize=16,
        fontweight="bold",
        color=TEXT,
        y=0.992,
    )
    fig.text(
        0.5,
        0.965,
        (
            "Panels share the same calendar-year axis. Daily color intensity follows model-input use; blank cells indicate days not fed as dynamic input."
            if chart_kind == "input"
            else "Panels share the same calendar-year axis. Daily color intensity follows valid Streamflow coverage; blank cells indicate missing target data."
        ),
        ha="center",
        fontsize=9,
        color=MUTED,
    )
    fig.tight_layout(rect=(0.02, 0.02, 0.98, 0.95))

    output_paths: dict[str, str] = {}
    for fmt in formats:
        out = output_dir / f"overview.{fmt}"
        save_kwargs: dict[str, Any] = {"bbox_inches": "tight", "facecolor": BG}
        if fmt == "png":
            save_kwargs["dpi"] = 180
        fig.savefig(out, **save_kwargs)
        output_paths[fmt] = str(out.relative_to(REPO_ROOT))
    plt.close(fig)
    return output_paths


def write_overview_only(
    df: pd.DataFrame,
    output_dir: Path,
    formats: list[str],
    *,
    chart_kind: str,
) -> None:
    dirs = coverage_output_dirs(output_dir, chart_kind)
    dirs["figures"].mkdir(parents=True, exist_ok=True)
    overview_outputs = plot_compact_overview(df, dirs["figures"], formats, chart_kind=chart_kind)
    print(f"Wrote overview chart: {', '.join(overview_outputs.values())}")


def write_outputs(
    df: pd.DataFrame,
    output_dir: Path,
    formats: list[str],
    *,
    chart_kind: str,
) -> None:
    dirs = coverage_output_dirs(output_dir, chart_kind)
    for directory in dirs.values():
        directory.mkdir(parents=True, exist_ok=True)

    if chart_kind == "input":
        span_csv = dirs["tables"] / "spans.csv"
        csv_cols = [
            "gauge_id",
            "split",
            "target_variable",
            "model_input_start",
            "model_input_end",
            "model_input_hour_count",
            "valid_model_sample_count",
            "configured_start",
            "configured_end",
            "overall_start",
            "overall_end",
            "prepared_split_status",
            "original_split",
            "state",
            "gauge_name",
            "camelsh_huc02",
            "timeseries_path",
        ]
    else:
        span_csv = dirs["tables"] / "spans.csv"
        csv_cols = [
            "gauge_id",
            "split",
            "target_variable",
            "overall_start",
            "overall_end",
            "overall_valid_target_count",
            "used_start",
            "used_end",
            "used_valid_target_count",
            "used_possible_target_count",
            "used_coverage_fraction",
            "configured_start",
            "configured_end",
            "prepared_split_status",
            "original_split",
            "actual_valid_target_count",
            "state",
            "gauge_name",
            "camelsh_huc02",
            "timeseries_path",
        ]
    csv_cols = [col for col in csv_cols if col in df.columns]
    sort_cols = (
        ["split", "model_input_start", "model_input_end", "gauge_id"]
        if chart_kind == "input"
        else ["split", "overall_start", "overall_end", "gauge_id"]
    )
    df[csv_cols].sort_values(sort_cols).to_csv(
        span_csv,
        index=False,
    )

    split_outputs = {
        split: plot_split(df, split, dirs["figures"], formats, chart_kind=chart_kind)
        for split in SPLIT_ORDER
    }
    overview_outputs = plot_compact_overview(df, dirs["figures"], formats, chart_kind=chart_kind)

    summary: dict[str, Any] = {
        "coverage_dir": str(dirs["root"].relative_to(REPO_ROOT)),
        "figures_dir": str(dirs["figures"].relative_to(REPO_ROOT)),
        "tables_dir": str(dirs["tables"].relative_to(REPO_ROOT)),
        "metadata_dir": str(dirs["metadata"].relative_to(REPO_ROOT)),
        "span_csv": str(span_csv.relative_to(REPO_ROOT)),
        "chart_kind": chart_kind,
        "overview_outputs": overview_outputs,
        "split_outputs": split_outputs,
        "splits": {},
    }
    for split in SPLIT_ORDER:
        split_df = df[df["split"] == split]
        split_summary = {
            "basin_count": int(len(split_df)),
            "configured_start": pd.Timestamp(split_df["configured_start"].iloc[0]).strftime("%Y-%m-%d"),
            "configured_end": pd.Timestamp(split_df["configured_end"].iloc[0]).strftime("%Y-%m-%d"),
            "available_start_min": pd.Timestamp(split_df["overall_start"].min()).strftime("%Y-%m-%d %H:%M:%S"),
            "available_end_max": pd.Timestamp(split_df["overall_end"].max()).strftime("%Y-%m-%d %H:%M:%S"),
        }
        if chart_kind == "input":
            split_summary.update(
                {
                    "model_input_start_min": pd.Timestamp(split_df["model_input_start"].min()).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "model_input_end_max": pd.Timestamp(split_df["model_input_end"].max()).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "model_input_hours": int(split_df["model_input_hour_count"].sum()),
                    "valid_or_evaluated_model_samples": int(split_df["valid_model_sample_count"].sum()),
                }
            )
        else:
            split_summary.update(
                {
                    "used_start_min": pd.Timestamp(split_df["used_start"].min()).strftime("%Y-%m-%d %H:%M:%S"),
                    "used_end_max": pd.Timestamp(split_df["used_end"].max()).strftime("%Y-%m-%d %H:%M:%S"),
                    "used_valid_target_hours": int(split_df["used_valid_target_count"].sum()),
                    "used_possible_target_hours": int(split_df["used_possible_target_count"].sum()),
                    "used_coverage_fraction": float(
                        split_df["used_valid_target_count"].sum()
                        / split_df["used_possible_target_count"].sum()
                    ),
                }
            )
        summary["splits"][split] = split_summary

    manifest_path = dirs["metadata"] / "manifest.json"
    manifest_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote span table: {span_csv}")
    print(f"Wrote plot manifest: {manifest_path}")
    for split, paths in split_outputs.items():
        print(f"Wrote {split} chart: {', '.join(paths.values())}")
    print(f"Wrote overview chart: {', '.join(overview_outputs.values())}")


def main() -> None:
    args = parse_args()
    config = read_config(resolve_path(args.config))
    split_files = split_files_from_config(config)
    periods = split_periods_from_config(config)
    manifest = load_base_manifest(
        prepared_manifest_path=resolve_path(args.prepared_manifest),
        scaling_manifest_path=resolve_path(args.scaling_manifest),
        split_files=split_files,
        periods=periods,
    )
    timeseries_dir = get_timeseries_dir(config)
    spans = compute_streamflow_spans(
        manifest=manifest,
        timeseries_dir=timeseries_dir,
        target_variable=args.target_variable,
        dynamic_inputs=list(config["dynamic_inputs"]),
        seq_length=int(config["seq_length"]),
        predict_last_n=int(config["predict_last_n"]),
    )
    output_dir = resolve_path(args.output_dir)
    if args.chart_kind in {"target", "both"}:
        if args.overview_only:
            write_overview_only(spans, output_dir, args.formats, chart_kind="target")
        else:
            write_outputs(spans, output_dir, args.formats, chart_kind="target")
    if args.chart_kind in {"input", "both"}:
        if args.overview_only:
            write_overview_only(spans, output_dir, args.formats, chart_kind="input")
        else:
            write_outputs(spans, output_dir, args.formats, chart_kind="input")


if __name__ == "__main__":
    main()
