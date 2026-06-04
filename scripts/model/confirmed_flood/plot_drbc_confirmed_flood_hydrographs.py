#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "pyarrow>=16.0",
#   "xarray>=2024.1",
#   "netCDF4>=1.6",
# ]
# ///
"""Plot confirmed-flood event hydrographs with model predictions and NOAA markers."""
from __future__ import annotations

import argparse
import math
import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
import xarray as xr


DEFAULT_EVENT_WINDOWS = Path("output/model_analysis/confirmed_flood/data/inference/confirmed_flood_event_windows_used.csv")
DEFAULT_CATALOG_CSV = Path("output/model_analysis/confirmed_flood/data/catalog/drbc_confirmed_flood_event_catalog.csv")
DEFAULT_COVERAGE_CSV = Path("output/model_analysis/confirmed_flood/data/nws_flood_stage_coverage.csv")
DEFAULT_SERIES_DIR = Path("output/model_analysis/confirmed_flood/data/inference/required_series")
DEFAULT_DATA_DIR = Path("data/CAMELSH_generic/drbc_holdout_confirmed_flood_events/time_series")
DEFAULT_NOAA_CACHE = Path("output/model_analysis/confirmed_flood/data/noaa_cache")
DEFAULT_OUTPUT_DIR = Path("output/model_analysis/confirmed_flood/gallery")
DEFAULT_SEEDS = [111, 222, 444]

PREDICTORS = [
    ("model1", "Model 1"),
    ("q50", "Model 2 q50"),
    ("q95", "Model 2 q95"),
    ("q99", "Model 2 q99"),
]
LINE_STYLES = {
    "obs": {"color": "#111827", "linewidth": 1.35, "linestyle": "-", "label": "Observed"},
    "model1": {"color": "#2563eb", "linewidth": 1.0, "linestyle": "-", "label": "Model 1"},
    "q50": {"color": "#dc2626", "linewidth": 1.05, "linestyle": "-", "label": "Model 2 q50"},
    "q95": {"color": "#f97316", "linewidth": 0.95, "linestyle": "--", "label": "Model 2 q95"},
    "q99": {"color": "#d97706", "linewidth": 0.95, "linestyle": "--", "label": "Model 2 q99"},
}
THRESHOLD_STYLES = {
    "minor": ("#ea580c", "--"),
    "moderate": ("#dc2626", "--"),
    "major": ("#7f1d1d", "--"),
}
NOAA_TYPE_COLORS = {
    "Flash Flood": "#7c3aed",
    "Flood": "#0f766e",
    "Coastal Flood": "#0369a1",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-windows", type=Path, default=DEFAULT_EVENT_WINDOWS)
    parser.add_argument("--catalog-csv", type=Path, default=DEFAULT_CATALOG_CSV)
    parser.add_argument("--coverage-csv", type=Path, default=DEFAULT_COVERAGE_CSV)
    parser.add_argument("--series-dir", type=Path, default=DEFAULT_SERIES_DIR)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--noaa-cache", type=Path, default=DEFAULT_NOAA_CACHE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seeds", type=int, nargs="+", default=DEFAULT_SEEDS)
    parser.add_argument("--limit-events", type=int, default=None, help="Smoke-test only first N events.")
    parser.add_argument("--basins", type=str, nargs="+", default=None, help="Optional basin IDs to plot.")
    parser.add_argument("--padding-hours", type=int, default=24)
    parser.add_argument("--max-noaa-markers", type=int, default=8)
    parser.add_argument("--skip-existing", action="store_true")
    return parser.parse_args()


def normalize_gauge_id(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(8)


def safe_float(value: Any) -> float:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return float(numeric) if pd.notna(numeric) else math.nan


def fmt_float(value: Any, digits: int = 2) -> str:
    numeric = safe_float(value)
    return f"{numeric:.{digits}f}" if np.isfinite(numeric) else "NA"


def safe_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def date_num(value: Any) -> float:
    return mdates.date2num(pd.Timestamp(value).to_pydatetime())


def finite_max(values: list[float]) -> float:
    finite = [value for value in values if np.isfinite(value)]
    return max(finite) if finite else math.nan


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def read_events(path: Path, catalog_csv: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing event windows CSV: {path}")
    events = pd.read_csv(path, dtype={"usgs_id": str, "basin": str})
    events["usgs_id"] = events["usgs_id"].map(normalize_gauge_id)
    events["basin"] = events["basin"].map(normalize_gauge_id)
    for col in ["peak_time", "eval_start", "eval_end", "window_start", "window_end"]:
        events[col] = pd.to_datetime(events[col], errors="coerce")
    events["peak_key"] = events["peak_time"].dt.strftime("%Y-%m-%dT%H:%M:%S")

    if catalog_csv.exists():
        catalog = pd.read_csv(catalog_csv, dtype={"usgs_id": str})
        if "noaa_annotation" in catalog.columns:
            catalog["usgs_id"] = catalog["usgs_id"].map(normalize_gauge_id)
            catalog["peak_key"] = pd.to_datetime(catalog["peak_time"], errors="coerce").dt.strftime(
                "%Y-%m-%dT%H:%M:%S"
            )
            catalog = catalog.drop_duplicates(["usgs_id", "peak_key"])
            events = events.merge(
                catalog[["usgs_id", "peak_key", "noaa_annotation"]],
                on=["usgs_id", "peak_key"],
                how="left",
            )
    if "noaa_annotation" not in events.columns:
        events["noaa_annotation"] = "-"
    events["noaa_annotation"] = events["noaa_annotation"].fillna("-")
    return events.sort_values(["basin", "peak_time", "event_id"]).reset_index(drop=True)


def read_coverage(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing coverage CSV: {path}")
    coverage = pd.read_csv(path, dtype={"usgs_id": str, "county_fips": str})
    coverage["usgs_id"] = coverage["usgs_id"].map(normalize_gauge_id)
    if "county_fips" in coverage:
        coverage["county_fips"] = coverage["county_fips"].map(
            lambda value: str(value).split(".")[0].zfill(5) if pd.notna(value) else None
        )
    return coverage.drop_duplicates("usgs_id").set_index("usgs_id")


def read_required_series(series_dir: Path, seed: int) -> pd.DataFrame:
    path = series_dir / f"seed{seed}" / "required_series.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing required-series file: {path}")
    df = pd.read_csv(path, dtype={"basin": str, "event_id": str}, parse_dates=["datetime"])
    df["basin"] = df["basin"].map(normalize_gauge_id)
    for col in ["obs", "model1", "q50", "q90", "q95", "q99"]:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "in_eval_window" in df:
        df["in_eval_window"] = df["in_eval_window"].map(boolish)
    return df.sort_values(["event_id", "datetime"]).reset_index(drop=True)


def read_rain_series(data_dir: Path, basin: str) -> pd.Series:
    path = data_dir / f"{basin}.nc"
    if not path.exists():
        raise FileNotFoundError(f"Missing basin time-series file: {path}")
    with xr.open_dataset(path) as ds:
        date_coord = "date" if "date" in ds.coords else "DateTime" if "DateTime" in ds.coords else "time"
        if "Rainf" not in ds:
            raise KeyError(f"{path} must contain Rainf")
        rain = pd.Series(ds["Rainf"].values.astype(float), index=pd.to_datetime(ds[date_coord].values), name="Rainf")
    return rain.sort_index()


def load_noaa_cache(cache_dir: Path, years: set[int]) -> pd.DataFrame:
    frames = []
    for year in sorted(years):
        path = cache_dir / f"storm_events_{year}.parquet"
        if not path.exists():
            continue
        frame = pd.read_parquet(path)
        if {"county_fips", "begin_date", "end_date", "event_type", "event_id"}.issubset(frame.columns):
            frame = frame[["county_fips", "begin_date", "end_date", "event_type", "event_id"]].copy()
            frame["county_fips"] = frame["county_fips"].astype(str).str.zfill(5)
            frame["begin_date"] = pd.to_datetime(frame["begin_date"], errors="coerce")
            frame["end_date"] = pd.to_datetime(frame["end_date"], errors="coerce")
            frames.append(frame.dropna(subset=["county_fips", "begin_date", "end_date", "event_type"]))
    if not frames:
        return pd.DataFrame(columns=["county_fips", "begin_date", "end_date", "event_type", "event_id"])
    return pd.concat(frames, ignore_index=True)


def noaa_matches_for_event(event: pd.Series, coverage: pd.DataFrame, noaa_df: pd.DataFrame) -> pd.DataFrame:
    basin = normalize_gauge_id(event["basin"])
    if basin not in coverage.index or noaa_df.empty:
        return noaa_df.iloc[0:0].copy()
    county_fips = coverage.loc[basin].get("county_fips")
    if pd.isna(county_fips):
        return noaa_df.iloc[0:0].copy()
    peak = pd.Timestamp(event["peak_time"])
    window_start = peak - pd.Timedelta(days=2)
    window_end = peak + pd.Timedelta(days=2)
    match = noaa_df[
        (noaa_df["county_fips"].astype(str).str.zfill(5) == str(county_fips).zfill(5))
        & (noaa_df["begin_date"] <= window_end)
        & (noaa_df["end_date"] >= window_start)
    ].copy()
    if match.empty:
        return match
    return match.sort_values(["begin_date", "end_date", "event_type", "event_id"]).drop_duplicates(
        ["event_type", "event_id", "begin_date", "end_date"]
    )


def threshold_items(event: pd.Series, coverage: pd.DataFrame) -> list[tuple[str, float, str, str]]:
    basin = normalize_gauge_id(event["basin"])
    if basin not in coverage.index:
        return []
    row = coverage.loc[basin]
    items = []
    for tier in ["minor", "moderate", "major"]:
        value = safe_float(row.get(f"{tier}_discharge_cms"))
        if np.isfinite(value) and value > 0:
            color, linestyle = THRESHOLD_STYLES[tier]
            items.append((f"NWS {tier}", value, color, linestyle))
    return items


def seed_axis_note(frame: pd.DataFrame) -> str:
    eval_frame = frame[frame["in_eval_window"]] if "in_eval_window" in frame else frame
    if eval_frame.empty:
        eval_frame = frame
    obs_peak = safe_float(eval_frame["obs"].max(skipna=True))
    parts = []
    for col, label in [("model1", "M1"), ("q50", "q50"), ("q95", "q95"), ("q99", "q99")]:
        pred_peak = safe_float(eval_frame[col].max(skipna=True))
        deficit = (obs_peak - pred_peak) / obs_peak * 100.0 if np.isfinite(obs_peak) and obs_peak > 0 else math.nan
        parts.append(f"{label} {fmt_float(deficit, 1)}%")
    return "under-deficit: " + ", ".join(parts)


def draw_noaa_markers(ax: Any, matches: pd.DataFrame, max_markers: int) -> int:
    if matches.empty:
        return 0
    shown = 0
    for _, row in matches.head(max_markers).iterrows():
        event_type = str(row["event_type"])
        color = NOAA_TYPE_COLORS.get(event_type, "#7c3aed")
        begin = pd.Timestamp(row["begin_date"])
        end = pd.Timestamp(row["end_date"])
        marker_time = begin + pd.Timedelta(hours=12)
        if end.date() != begin.date():
            span_end = end + pd.Timedelta(hours=23, minutes=59)
            ax.axvspan(date_num(begin), date_num(span_end), color=color, alpha=0.045, linewidth=0)
        ax.axvline(date_num(marker_time), color=color, linewidth=0.9, linestyle="-.", alpha=0.86)
        short_type = {"Flash Flood": "Flash", "Coastal Flood": "Coastal"}.get(event_type, event_type)
        ax.text(
            date_num(marker_time),
            0.97,
            short_type,
            transform=ax.get_xaxis_transform(),
            rotation=90,
            va="top",
            ha="right",
            fontsize=6.6,
            color=color,
            alpha=0.92,
        )
        shown += 1
    return shown


def add_external_legend(
    fig: Any,
    top_axis: Any,
    event: pd.Series,
    thresholds: list[tuple[str, float, str, str]],
    noaa_matches: pd.DataFrame,
    noaa_shown: int,
) -> None:
    handles: list[Any] = [
        Line2D([], [], linestyle="none", linewidth=0, color="none"),
        Patch(facecolor="#2563eb", edgecolor="#2563eb", alpha=0.82),
        Line2D([], [], color="#4b5563", linewidth=1.0, linestyle="--"),
    ]
    labels = [
        "Rain",
        "Rainf bars",
        "confirmed flood peak",
    ]

    handles.extend(
        [
            Line2D([], [], linestyle="none", linewidth=0, color="none"),
            Patch(facecolor="#f97316", edgecolor="#f97316", alpha=0.08),
            Patch(facecolor="#f97316", edgecolor="#f97316", alpha=0.13),
            Patch(facecolor="#f59e0b", edgecolor="#f59e0b", alpha=0.12),
            Line2D([], [], color=LINE_STYLES["model1"]["color"], linewidth=LINE_STYLES["model1"]["linewidth"]),
            Line2D([], [], color=LINE_STYLES["q50"]["color"], linewidth=LINE_STYLES["q50"]["linewidth"]),
            Line2D([], [], color=LINE_STYLES["q95"]["color"], linewidth=LINE_STYLES["q95"]["linewidth"], linestyle="--"),
            Line2D([], [], color=LINE_STYLES["q99"]["color"], linewidth=LINE_STYLES["q99"]["linewidth"], linestyle="--"),
            Line2D([], [], color=LINE_STYLES["obs"]["color"], linewidth=LINE_STYLES["obs"]["linewidth"]),
            Line2D([], [], color="#dc2626", marker="o", linestyle="none", markersize=6),
        ]
    )
    labels.extend(
        [
            "Streamflow",
            "evaluation window",
            "q50-q95 band",
            "q95-q99 band",
            "Model 1",
            "Model 2 q50",
            "Model 2 q95",
            "Model 2 q99",
            "Observed",
            "Observed peak",
        ]
    )
    for label, value, color, linestyle in thresholds:
        handles.append(Line2D([], [], color=color, linewidth=0.85, linestyle=linestyle))
        labels.append(f"{label}: {fmt_float(value)} cms")

    handles.append(Line2D([], [], linestyle="none", linewidth=0, color="none"))
    labels.append("NOAA")
    if noaa_matches.empty:
        handles.append(Line2D([], [], linestyle="none", linewidth=0, color="none"))
        labels.append("no NOAA Storm Events match")
    else:
        for event_type, count in noaa_matches["event_type"].value_counts().sort_index().items():
            color = NOAA_TYPE_COLORS.get(str(event_type), "#7c3aed")
            handles.append(Line2D([], [], color=color, linewidth=0.9, linestyle="-."))
            labels.append(f"{event_type}: {int(count)} records")
        if len(noaa_matches) > noaa_shown:
            handles.append(Line2D([], [], linestyle="none", linewidth=0, color="none"))
            labels.append(f"markers shown {noaa_shown}/{len(noaa_matches)}")

    handles.append(Line2D([], [], linestyle="none", linewidth=0, color="none"))
    labels.append("Event")
    handles.extend([Line2D([], [], linestyle="none", linewidth=0, color="none") for _ in range(4)])
    labels.extend(
        [
            f"{event['event_id']}",
            f"basin {event['basin']}",
            f"tier {event.get('flood_tier')} | period {event.get('period')}",
            f"peak {fmt_float(event.get('peak_discharge_cms'))} cms",
        ]
    )

    fig.canvas.draw()
    legend_top = top_axis.get_position().y1
    legend = fig.legend(
        handles,
        labels,
        loc="upper left",
        bbox_to_anchor=(1.005, legend_top),
        frameon=True,
        fontsize=7.2,
        handlelength=2.0,
        borderpad=0.8,
        labelspacing=0.5,
    )
    legend.get_frame().set_edgecolor("#a1a1aa")
    legend.get_frame().set_alpha(0.96)
    for text in legend.get_texts():
        if text.get_text() in {"Rain", "Streamflow", "NOAA", "Event"}:
            text.set_weight("bold")


def output_path_for_event(output_dir: Path, event: pd.Series) -> Path:
    tier = safe_slug(str(event.get("flood_tier", "unknown")))
    basin = normalize_gauge_id(event["basin"])
    peak = pd.Timestamp(event["peak_time"]).strftime("%Y%m%dT%H%M%S")
    filename = f"{safe_slug(str(event['event_id']))}.png"
    return output_dir / tier / basin / f"{peak}_{filename}"


def plot_event(
    *,
    event: pd.Series,
    all_series: dict[int, pd.DataFrame],
    rain: pd.Series,
    coverage: pd.DataFrame,
    noaa_df: pd.DataFrame,
    seeds: list[int],
    output_path: Path,
    padding_hours: int,
    max_noaa_markers: int,
) -> dict[str, Any]:
    peak_time = pd.Timestamp(event["peak_time"])
    eval_start = pd.Timestamp(event["eval_start"])
    eval_end = pd.Timestamp(event["eval_end"])
    first_seed_frame = all_series[seeds[0]]
    event_series = first_seed_frame[first_seed_frame["event_id"].eq(event["event_id"])]
    plot_start = event_series["datetime"].min() - pd.Timedelta(hours=padding_hours)
    plot_end = event_series["datetime"].max() + pd.Timedelta(hours=padding_hours)
    thresholds = threshold_items(event, coverage)
    noaa_matches = noaa_matches_for_event(event, coverage, noaa_df)

    fig, axes = plt.subplots(
        len(seeds) + 1,
        1,
        figsize=(14.2, 10.8),
        sharex=True,
        gridspec_kw={"height_ratios": [0.95, *([1.9] * len(seeds))]},
        constrained_layout=True,
    )
    ax_rain = axes[0]
    rain_window = rain.loc[plot_start:plot_end]
    rain_x = mdates.date2num(rain_window.index.to_pydatetime())
    ax_rain.bar(rain_x, rain_window.fillna(0.0).to_numpy(dtype=float), width=0.032, color="#2563eb", alpha=0.82)
    ax_rain.axvline(date_num(peak_time), color="#4b5563", linewidth=1.0, linestyle="--", alpha=0.9)
    rain_max = safe_float(rain_window.max(skipna=True))
    ax_rain.set_ylim(0, rain_max * 1.18 if np.isfinite(rain_max) and rain_max > 0 else 1.0)
    ax_rain.set_ylabel("Rainf")
    ax_rain.grid(True, axis="y", color="#d4d4d8", linewidth=0.55, alpha=0.85)

    noaa_shown = 0
    for ax, seed in zip(axes[1:], seeds, strict=True):
        seed_series = all_series[seed]
        frame = seed_series[seed_series["event_id"].eq(event["event_id"])].copy()
        frame = frame[frame["datetime"].between(plot_start, plot_end, inclusive="both")]
        if frame.empty:
            raise ValueError(f"No required-series rows for seed {seed}, event {event['event_id']}")
        x = mdates.date2num(frame["datetime"].dt.to_pydatetime())
        ax.axvspan(date_num(eval_start), date_num(eval_end), color="#f97316", alpha=0.08)
        ax.fill_between(
            x,
            frame["q50"].to_numpy(dtype=float),
            frame["q95"].to_numpy(dtype=float),
            color="#f97316",
            alpha=0.13,
            linewidth=0,
        )
        ax.fill_between(
            x,
            frame["q95"].to_numpy(dtype=float),
            frame["q99"].to_numpy(dtype=float),
            color="#f59e0b",
            alpha=0.12,
            linewidth=0,
        )
        for col, _label in PREDICTORS:
            style = LINE_STYLES[col]
            ax.plot(
                x,
                frame[col].to_numpy(dtype=float),
                color=style["color"],
                linewidth=style["linewidth"],
                linestyle=style["linestyle"],
            )
        obs_style = LINE_STYLES["obs"]
        ax.plot(
            x,
            frame["obs"].to_numpy(dtype=float),
            color=obs_style["color"],
            linewidth=obs_style["linewidth"],
            linestyle=obs_style["linestyle"],
        )
        obs_peak = safe_float(event.get("peak_discharge_cms"))
        if np.isfinite(obs_peak):
            ax.scatter([date_num(peak_time)], [obs_peak], s=28, color="#dc2626", zorder=5)
        ax.axvline(date_num(peak_time), color="#4b5563", linewidth=1.0, linestyle="--", alpha=0.9)
        noaa_shown = max(noaa_shown, draw_noaa_markers(ax, noaa_matches, max_noaa_markers))

        data_max = finite_max(
            [
                safe_float(frame[col].max(skipna=True))
                for col in ["obs", "model1", "q50", "q95", "q99"]
                if col in frame
            ]
        )
        y_candidates = [data_max, obs_peak]
        for label, value, color, linestyle in thresholds:
            if not np.isfinite(value) or value <= 0:
                continue
            if np.isfinite(data_max) and value > data_max * 3.0:
                continue
            ax.axhline(value, color=color, linewidth=0.85, linestyle=linestyle, alpha=0.72)
            y_candidates.append(value)
        y_max = finite_max(y_candidates)
        ax.set_ylim(0, y_max * 1.14 if np.isfinite(y_max) and y_max > 0 else 1.0)
        model1_epoch = int(frame["model1_epoch"].iloc[0]) if "model1_epoch" in frame else -1
        model2_epoch = int(frame["model2_epoch"].iloc[0]) if "model2_epoch" in frame else -1
        ax.set_title(
            f"seed {seed} | M1 epoch {model1_epoch:03d} / M2 epoch {model2_epoch:03d}\n"
            f"{seed_axis_note(frame)}",
            fontsize=8.7,
        )
        ax.set_ylabel("Streamflow")
        ax.grid(True, axis="y", color="#d4d4d8", linewidth=0.55, alpha=0.85)

    axes[-1].xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=9))
    axes[-1].xaxis.set_major_formatter(mdates.ConciseDateFormatter(axes[-1].xaxis.get_major_locator()))
    for ax in axes:
        ax.xaxis_date()

    noaa_text = "NOAA match: none" if noaa_matches.empty else f"NOAA records: {len(noaa_matches)}"
    fig.suptitle(
        "Confirmed flood event hydrograph with simulated Q\n"
        f"{event['event_id']} | basin {event['basin']} | tier={event.get('flood_tier')} | "
        f"peak={pd.Timestamp(event['peak_time']).strftime('%Y-%m-%d %H:%M')} | {noaa_text}",
        fontsize=10.3,
    )
    add_external_legend(fig, ax_rain, event, thresholds, noaa_matches, noaa_shown)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return {
        "event_id": event["event_id"],
        "basin": event["basin"],
        "peak_time": pd.Timestamp(event["peak_time"]).isoformat(),
        "flood_tier": event.get("flood_tier"),
        "period": event.get("period"),
        "noaa_record_count": int(len(noaa_matches)),
        "noaa_marker_count": int(noaa_shown),
        "plot_path": str(output_path),
    }


def write_readme(output_dir: Path, manifest_path: Path, event_count: int, seeds: list[int]) -> None:
    lines = [
        "# Confirmed Flood Hydrographs",
        "",
        "These figures overlay observed streamflow with Model 1 and Model 2 quantile predictions for confirmed flood events.",
        "The layout follows the extreme-rain sim-Q hydrograph figures: one Rainf panel, then one streamflow panel per seed.",
        "Flow thresholds use NWS flood-stage discharge thresholds, not ARI proxies.",
        "NOAA Storm Events records are drawn as vertical markers only when matched by county FIPS and peak +/- 2 days.",
        "",
        f"- Events plotted: {event_count}",
        f"- Seeds: {', '.join(str(seed) for seed in seeds)}",
        f"- Manifest: `{manifest_path.name}`",
        "",
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    seeds = sorted(set(args.seeds))
    events = read_events(args.event_windows, args.catalog_csv)
    if args.basins:
        selected_basins = {normalize_gauge_id(value) for value in args.basins}
        events = events[events["basin"].isin(selected_basins)].copy()
    if args.limit_events is not None:
        events = events.head(args.limit_events).copy()
    if events.empty:
        raise SystemExit("No events selected.")

    coverage = read_coverage(args.coverage_csv)
    years = {pd.Timestamp(value).year for value in events["peak_time"].dropna()}
    noaa_df = load_noaa_cache(args.noaa_cache, years)
    all_series = {seed: read_required_series(args.series_dir, seed) for seed in seeds}
    rain_cache: dict[str, pd.Series] = {}

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows = []
    total = len(events)
    for idx, (_, event) in enumerate(events.iterrows(), start=1):
        basin = normalize_gauge_id(event["basin"])
        if basin not in rain_cache:
            rain_cache[basin] = read_rain_series(args.data_dir, basin)
        output_path = output_path_for_event(args.output_dir, event)
        if args.skip_existing and output_path.exists():
            row = {
                "event_id": event["event_id"],
                "basin": basin,
                "peak_time": pd.Timestamp(event["peak_time"]).isoformat(),
                "flood_tier": event.get("flood_tier"),
                "period": event.get("period"),
                "noaa_record_count": pd.NA,
                "noaa_marker_count": pd.NA,
                "plot_path": str(output_path),
            }
        else:
            row = plot_event(
                event=event,
                all_series=all_series,
                rain=rain_cache[basin],
                coverage=coverage,
                noaa_df=noaa_df,
                seeds=seeds,
                output_path=output_path,
                padding_hours=int(args.padding_hours),
                max_noaa_markers=int(args.max_noaa_markers),
            )
        manifest_rows.append(row)
        if idx % 25 == 0 or idx == total:
            print(f"Plotted {idx}/{total} confirmed flood hydrographs", flush=True)

    manifest = pd.DataFrame(manifest_rows)
    manifest_path = args.output_dir / "confirmed_flood_hydrograph_manifest.csv"
    manifest.to_csv(manifest_path, index=False)
    write_readme(args.output_dir, manifest_path=manifest_path, event_count=total, seeds=seeds)
    print(f"Wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
