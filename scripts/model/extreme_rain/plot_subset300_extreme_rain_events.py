#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "xarray>=2024.1",
#   "netCDF4>=1.6",
# ]
# ///

from __future__ import annotations

import argparse
import html
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


DEFAULT_COHORT_CSV = Path("output/model_analysis/extreme_rain/primary/exposure/drbc_historical_stress_cohort.csv")
DEFAULT_DATA_DIR = Path("data/CAMELSH_generic/drbc_holdout_broad/time_series")
DEFAULT_OUTPUT_DIR = Path("output/model_analysis/extreme_rain/primary/event_plots")
DEFAULT_RETURN_PERIOD_CSV = Path("output/basin/all/analysis/return_period/tables/return_period_reference_table.csv")
DEFAULT_BASIN_SCREENING_CSV = Path("output/basin/drbc/screening/drbc_provisional_screening_table.csv")
DEFAULT_STREAMFLOW_QUALITY_CSV = Path("output/basin/drbc/screening/drbc_streamflow_quality_table.csv")
PRECIP_PERIODS = (25, 50, 100)
PRECIP_DURATIONS = (1, 6, 24, 72)
PRECIP_LINE_STYLES = {
    25: ("#0f766e", "--"),
    50: ("#0891b2", "-."),
    100: ("#4f46e5", ":"),
}

REQUIRED_TIME_COLUMNS = [
    "rain_start",
    "rain_peak",
    "rain_end",
    "response_window_start",
    "response_window_end",
    "observed_response_peak_time",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot hourly Rainf and observed Streamflow for subset300 extreme-rain stress events."
    )
    parser.add_argument("--cohort-csv", type=Path, default=DEFAULT_COHORT_CSV)
    parser.add_argument("--return-period-csv", type=Path, default=DEFAULT_RETURN_PERIOD_CSV)
    parser.add_argument("--basin-screening-csv", type=Path, default=DEFAULT_BASIN_SCREENING_CSV)
    parser.add_argument("--streamflow-quality-csv", type=Path, default=DEFAULT_STREAMFLOW_QUALITY_CSV)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--limit-events", type=int, default=None, help="Optional smoke-test limit.")
    parser.add_argument("--rain-padding-hours", type=int, default=12)
    parser.add_argument("--response-padding-hours", type=int, default=12)
    parser.add_argument(
        "--include-unrated",
        action="store_true",
        help="Include response_unrated_coverage events if they are present in the cohort CSV.",
    )
    parser.add_argument(
        "--index-only",
        action="store_true",
        help="Regenerate event_plot_index.html and README.md from the existing manifest without redrawing PNGs.",
    )
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


def safe_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def stress_group(response_class: str) -> str:
    if response_class in {"flood_response_ge25", "flood_response_ge2_to_lt25"}:
        return "positive_response"
    if response_class == "response_unrated_coverage":
        return "unrated"
    return "negative_control"


def fmt_ratio(value: Any) -> str:
    numeric = safe_float(value)
    return f"{numeric:.2f}" if np.isfinite(numeric) else "NA"


def inclusion_reason(row: pd.Series) -> str:
    rain_cohort = str(row.get("rain_cohort", ""))
    if rain_cohort == "prec_ge100":
        return "entered by rainfall: ARI100+"
    if rain_cohort == "prec_ge50":
        return "entered by rainfall: ARI50+"
    if rain_cohort == "prec_ge25":
        return "entered by rainfall: ARI25+"
    if rain_cohort == "near_prec100":
        return "entered by rainfall: near ARI100"
    return "entered by rainfall screen"


def relative_plot_path(output_dir: Path, plot_path: Any) -> str:
    path = Path(str(plot_path))
    try:
        return str(path.relative_to(output_dir))
    except ValueError:
        try:
            return str(path.resolve().relative_to(output_dir.resolve()))
        except ValueError:
            return str(path)


def read_cohort(path: Path, include_unrated: bool) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing cohort CSV: {path}")
    df = pd.read_csv(path, dtype={"gauge_id": str, "event_id": str})
    df["gauge_id"] = df["gauge_id"].map(normalize_gauge_id)
    for col in REQUIRED_TIME_COLUMNS:
        if col in df:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    if not include_unrated and "response_class" in df:
        df = df[~df["response_class"].eq("response_unrated_coverage")].copy()
    df["stress_group"] = df["response_class"].map(stress_group)
    return df.sort_values(["stress_group", "response_class", "gauge_id", "rain_start", "event_id"]).reset_index(drop=True)


def load_basin_series(data_dir: Path, gauge_id: str) -> pd.DataFrame:
    path = data_dir / f"{gauge_id}.nc"
    if not path.exists():
        raise FileNotFoundError(f"Missing time-series file: {path}")
    with xr.open_dataset(path) as ds:
        if "Rainf" not in ds or "Streamflow" not in ds:
            raise KeyError(f"{path} must contain Rainf and Streamflow")
        frame = pd.DataFrame(
            {
                "datetime": pd.to_datetime(ds["date"].values),
                "Rainf": ds["Rainf"].values.astype(float),
                "Streamflow": ds["Streamflow"].values.astype(float),
            }
        )
    return frame.set_index("datetime").sort_index()


def precip_reference_columns() -> list[str]:
    return [
        *(f"prec_ari{period}_{duration}h" for period in PRECIP_PERIODS for duration in PRECIP_DURATIONS),
        "prec_ari_source",
    ]


def precip_event_columns() -> list[str]:
    return [
        *(f"dominant_duration_for_ari{period}h" for period in PRECIP_PERIODS),
        *(f"max_prec_ari{period}_{duration}h_ratio" for period in PRECIP_PERIODS for duration in PRECIP_DURATIONS),
    ]


def add_precip_references(events: pd.DataFrame, return_period_csv: Path) -> pd.DataFrame:
    if not return_period_csv.exists():
        raise FileNotFoundError(f"Missing return-period reference CSV: {return_period_csv}")
    refs = pd.read_csv(return_period_csv, dtype={"gauge_id": str})
    refs["gauge_id"] = refs["gauge_id"].map(normalize_gauge_id)
    merge_cols = [col for col in precip_reference_columns() if col in refs.columns and col not in events.columns]
    if not merge_cols:
        return events
    return events.merge(refs[["gauge_id", *merge_cols]], on="gauge_id", how="left", validate="many_to_one")


def finite_max(series: pd.Series) -> float:
    if series.notna().any():
        return float(series.max(skipna=True))
    return math.nan


def fmt_value(value: Any, digits: int = 2) -> str:
    numeric = safe_float(value)
    return f"{numeric:.{digits}f}" if np.isfinite(numeric) else "NA"


def basin_metadata_columns() -> list[str]:
    return [
        "gauge_name",
        "state",
        "drain_sqkm_attr",
        "hydromod_risk",
        "forest_pct",
        "developed_pct",
        "wetland_pct",
        "dom_land_cover",
        "snow_influenced_tag",
        "steep_fast_response_tag",
        "coastal_or_hydromod_risk_tag",
        "screening_notes",
        "NDAMS_2009",
        "STOR_NOR_2009",
        "MAJ_NDAMS_2009",
        "DDENS_2009",
        "CANALS_PCT",
        "NPDES_MAJ_DENS",
        "POWER_NUM_PTS",
        "FRESHW_WITHDRAWAL",
    ]


def add_basin_metadata(
    events: pd.DataFrame,
    basin_screening_csv: Path,
    streamflow_quality_csv: Path,
) -> pd.DataFrame:
    out = events.copy()
    if basin_screening_csv.exists():
        screening = pd.read_csv(basin_screening_csv, dtype={"gauge_id": str})
        screening["gauge_id"] = screening["gauge_id"].map(normalize_gauge_id)
        screening = screening.drop_duplicates("gauge_id")
        screening_cols = [
            col
            for col in [
                "gauge_name",
                "state",
                "drain_sqkm_attr",
                "hydromod_risk",
                "forest_pct",
                "developed_pct",
                "wetland_pct",
                "dom_land_cover",
                "snow_influenced_tag",
                "steep_fast_response_tag",
                "coastal_or_hydromod_risk_tag",
                "screening_notes",
            ]
            if col in screening.columns and col not in out.columns
        ]
        if screening_cols:
            out = out.merge(
                screening[["gauge_id", *screening_cols]],
                on="gauge_id",
                how="left",
                validate="many_to_one",
            )
    if streamflow_quality_csv.exists():
        quality = pd.read_csv(streamflow_quality_csv, dtype={"gauge_id": str})
        quality["gauge_id"] = quality["gauge_id"].map(normalize_gauge_id)
        quality = quality.drop_duplicates("gauge_id")
        quality_cols = [
            col
            for col in [
                "NDAMS_2009",
                "STOR_NOR_2009",
                "MAJ_NDAMS_2009",
                "DDENS_2009",
                "CANALS_PCT",
                "NPDES_MAJ_DENS",
                "POWER_NUM_PTS",
                "FRESHW_WITHDRAWAL",
            ]
            if col in quality.columns and col not in out.columns
        ]
        if quality_cols:
            out = out.merge(
                quality[["gauge_id", *quality_cols]],
                on="gauge_id",
                how="left",
                validate="many_to_one",
            )
    return out


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def shorten_text(value: Any, max_chars: int = 44) -> str:
    if pd.isna(value):
        return ""
    text = re.sub(r"\s+", " ", str(value).strip())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def fmt_area(value: Any) -> str:
    numeric = safe_float(value)
    if not np.isfinite(numeric):
        return "NA"
    if numeric >= 100:
        return f"{numeric:,.0f}"
    return f"{numeric:.1f}"


def fmt_pct(value: Any, digits: int = 0) -> str:
    numeric = safe_float(value)
    return f"{numeric:.{digits}f}%" if np.isfinite(numeric) else "NA"


def compact_items(items: list[str], max_items: int = 4) -> list[str]:
    clean = [item for item in items if item]
    if len(clean) <= max_items:
        return clean
    return [*clean[:max_items], f"+{len(clean) - max_items} more"]


def natural_tag_labels(event: pd.Series) -> list[str]:
    labels: list[str] = []
    hydromod = boolish(event.get("hydromod_risk")) or boolish(event.get("coastal_or_hydromod_risk_tag"))
    labels.append("hydromod caution" if hydromod else "low hydromod proxy")
    if boolish(event.get("snow_influenced_tag")):
        labels.append("snow-influenced")
    if boolish(event.get("steep_fast_response_tag")):
        labels.append("steep-fast")
    forest = safe_float(event.get("forest_pct"))
    developed = safe_float(event.get("developed_pct"))
    wetland = safe_float(event.get("wetland_pct"))
    if np.isfinite(forest) and forest >= 50:
        labels.append("forested")
    if np.isfinite(developed) and developed >= 15:
        labels.append("developed")
    if np.isfinite(wetland) and wetland >= 10:
        labels.append("wetland")
    land_cover = shorten_text(str(event.get("dom_land_cover", "")).replace("_", " "), max_chars=24)
    if land_cover and land_cover.lower() != "nan":
        labels.append(f"landcover {land_cover}")
    return compact_items(labels, max_items=4)


def human_impact_labels(event: pd.Series) -> list[str]:
    labels: list[str] = []
    major_dams = safe_float(event.get("MAJ_NDAMS_2009"))
    dams = safe_float(event.get("NDAMS_2009"))
    storage = safe_float(event.get("STOR_NOR_2009"))
    canals = safe_float(event.get("CANALS_PCT"))
    water_use = safe_float(event.get("FRESHW_WITHDRAWAL"))
    npdes = safe_float(event.get("NPDES_MAJ_DENS"))
    power = safe_float(event.get("POWER_NUM_PTS"))
    if np.isfinite(major_dams) and major_dams > 0:
        labels.append(f"major dams {major_dams:.0f}")
    if np.isfinite(dams) and dams > 0:
        labels.append(f"dams {dams:.0f}")
    if np.isfinite(storage) and storage > 0:
        labels.append(f"storage {storage:.0f} ML/km2")
    if np.isfinite(canals) and canals > 0:
        labels.append(f"canals {canals:.1f}%")
    if np.isfinite(water_use) and water_use > 0:
        labels.append(f"water use {water_use:.0f} ML/yr/km2")
    if np.isfinite(npdes) and npdes > 0:
        labels.append(f"NPDES {npdes:.2f}")
    if np.isfinite(power) and power > 0:
        labels.append(f"power pts {power:.0f}")
    if not labels:
        return ["low hydromod proxy"]
    return compact_items(labels, max_items=4)


def basin_legend_lines(event: pd.Series) -> list[str]:
    gauge_name = shorten_text(event.get("gauge_name"), max_chars=44)
    gauge_line = str(event.get("gauge_id", ""))
    if gauge_name:
        gauge_line = f"{gauge_line} | {gauge_name}"
    area_line = (
        f"area {fmt_area(event.get('drain_sqkm_attr'))} km2 | "
        f"forest {fmt_pct(event.get('forest_pct'))} | developed {fmt_pct(event.get('developed_pct'))}"
    )
    tag_line = "tags: " + "; ".join(natural_tag_labels(event))
    human_line = "human impact: " + "; ".join(human_impact_labels(event))
    return [gauge_line, area_line, tag_line, human_line]


def dominant_precip_duration(event: pd.Series, period: int) -> int | None:
    explicit = safe_float(event.get(f"dominant_duration_for_ari{period}h"))
    if np.isfinite(explicit) and int(explicit) in PRECIP_DURATIONS:
        return int(explicit)
    candidates: list[tuple[float, int]] = []
    for duration in PRECIP_DURATIONS:
        ratio = safe_float(event.get(f"max_prec_ari{period}_{duration}h_ratio"))
        if np.isfinite(ratio):
            candidates.append((ratio, duration))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def precip_ari_items(event: pd.Series) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for period in PRECIP_PERIODS:
        duration = dominant_precip_duration(event, period)
        if duration is None:
            continue
        total = safe_float(event.get(f"prec_ari{period}_{duration}h"))
        if not np.isfinite(total) or total <= 0:
            continue
        color, linestyle = PRECIP_LINE_STYLES[period]
        items.append(
            {
                "period": period,
                "duration": duration,
                "total": total,
                "intensity": total / duration,
                "ratio": safe_float(event.get(f"max_prec_ari{period}_ratio")),
                "color": color,
                "linestyle": linestyle,
                "label": f"prec ARI{period} {duration}h avg",
            }
        )
    return items


def rain_threshold_items(event: pd.Series) -> list[tuple[str, float, str, str]]:
    return [
        ("wet threshold", safe_float(event.get("wet_rain_threshold_mm_h")), "#1d4ed8", ":"),
    ]


def section_handle() -> Line2D:
    return Line2D([], [], linestyle="none", linewidth=0, color="none")


def external_legend_items(event: pd.Series, precip_items: list[dict[str, Any]]) -> tuple[list[Any], list[str]]:
    handles: list[Any] = [
        section_handle(),
        Patch(facecolor="#2563eb", edgecolor="#2563eb", alpha=0.82),
        Patch(facecolor="#1d4ed8", edgecolor="#1d4ed8", alpha=0.08),
        Patch(facecolor="#1d4ed8", edgecolor="#1d4ed8", alpha=0.13),
        Line2D([], [], color="#1d4ed8", linewidth=1.0, linestyle="-"),
        Line2D([], [], color="#1d4ed8", linewidth=1.0, linestyle="--"),
        Line2D([], [], color="#1d4ed8", linewidth=0.9, linestyle=":"),
    ]
    labels = [
        "Rain",
        "Rainf bars",
        "rain event +/- padding",
        "rain event",
        "rain_start / rain_end",
        "rain_peak",
        f"wet cutoff: {fmt_value(event.get('wet_rain_threshold_mm_h'))} mm/h",
    ]
    for item in precip_items:
        handles.append(
            Line2D([], [], color=item["color"], linewidth=0.9, linestyle=item["linestyle"])
        )
        labels.append(
            f"prec ARI{item['period']} {item['duration']}h avg: "
            f"{fmt_value(item['total'], 1)} mm / {fmt_value(item['intensity'])} mm/h, "
            f"ratio {fmt_value(item['ratio'])}"
        )

    handles.extend(
        [
            section_handle(),
            Line2D([], [], color="#111827", linewidth=1.35, linestyle="-"),
            Patch(facecolor="#f97316", edgecolor="#f97316", alpha=0.08),
            Line2D([], [], color="#dc2626", marker="o", linestyle="none", markersize=6),
            Line2D([], [], color="#71717a", linewidth=0.9, linestyle=":"),
            Line2D([], [], color="#ea580c", linewidth=0.9, linestyle="--"),
            Line2D([], [], color="#dc2626", linewidth=0.9, linestyle="--"),
            Line2D([], [], color="#7f1d1d", linewidth=0.9, linestyle="--"),
        ]
    )
    labels.extend(
        [
            "Streamflow",
            "Observed Streamflow",
            "response window",
            "Observed peak",
            f"Q99: {fmt_value(event.get('streamflow_q99_threshold'))}",
            f"flood ARI2: {fmt_value(event.get('flood_ari2'))}",
            f"flood ARI25: {fmt_value(event.get('flood_ari25'))}",
            f"flood ARI100: {fmt_value(event.get('flood_ari100'))}",
        ]
    )
    handles.append(section_handle())
    labels.append("Basin")
    for line in basin_legend_lines(event):
        handles.append(section_handle())
        labels.append(line)
    return handles, labels


def add_external_legend(fig: Any, top_axis: Any, event: pd.Series, precip_items: list[dict[str, Any]]) -> None:
    handles, labels = external_legend_items(event, precip_items)
    fig.canvas.draw()
    legend_top = top_axis.get_position().y1
    legend = fig.legend(
        handles,
        labels,
        loc="upper left",
        bbox_to_anchor=(1.005, legend_top),
        frameon=True,
        fontsize=7.5,
        handlelength=2.0,
        borderpad=0.8,
        labelspacing=0.55,
    )
    legend.get_frame().set_edgecolor("#a1a1aa")
    legend.get_frame().set_alpha(0.96)
    for text in legend.get_texts():
        if text.get_text() in {"Rain", "Streamflow", "Basin"}:
            text.set_weight("bold")


def plot_event(
    event: pd.Series,
    series: pd.DataFrame,
    output_path: Path,
    *,
    rain_padding_hours: int,
    response_padding_hours: int,
) -> None:
    rain_start = pd.Timestamp(event["rain_start"])
    rain_end = pd.Timestamp(event["rain_end"])
    response_start = pd.Timestamp(event["response_window_start"])
    response_end = pd.Timestamp(event["response_window_end"])
    plot_start = response_start - pd.Timedelta(hours=response_padding_hours)
    plot_end = response_end + pd.Timedelta(hours=response_padding_hours)

    window = series.loc[plot_start:plot_end].copy()
    if window.empty:
        raise ValueError(f"No data in plot window for {event['event_id']}")

    fig, (ax_rain, ax_flow) = plt.subplots(
        2,
        1,
        figsize=(13.5, 7.2),
        sharex=True,
        gridspec_kw={"height_ratios": [1.0, 2.2]},
        constrained_layout=True,
    )

    rain = window["Rainf"]
    flow = window["Streamflow"]
    bar_width_days = 0.032
    ax_rain.bar(window.index, rain.fillna(0.0), width=bar_width_days, color="#2563eb", alpha=0.82, linewidth=0)
    ax_rain.set_ylabel("Rainf")
    ax_rain.grid(True, axis="y", color="#d4d4d8", linewidth=0.55, alpha=0.85)
    ax_rain.axvspan(
        rain_start - pd.Timedelta(hours=rain_padding_hours),
        rain_end + pd.Timedelta(hours=rain_padding_hours),
        color="#1d4ed8",
        alpha=0.08,
        label="rain event +/- padding",
    )
    ax_rain.axvspan(rain_start, rain_end, color="#1d4ed8", alpha=0.13, label="rain event")
    ax_rain.axvline(rain_start, color="#1d4ed8", linewidth=1.0, linestyle="-", alpha=0.9, label="rain start/end")
    ax_rain.axvline(rain_end, color="#1d4ed8", linewidth=1.0, linestyle="-", alpha=0.9)
    ax_rain.axvline(pd.Timestamp(event["rain_peak"]), color="#1d4ed8", linewidth=1.0, linestyle="--", label="rain peak")
    rain_y_candidates = [finite_max(rain)]
    precip_items = precip_ari_items(event)
    for item in precip_items:
        ax_rain.axhline(
            item["intensity"],
            color=item["color"],
            linewidth=0.9,
            linestyle=item["linestyle"],
            alpha=0.78,
            label=item["label"],
        )
        rain_y_candidates.append(item["intensity"])
    for label, value, color, linestyle in rain_threshold_items(event):
        if not np.isfinite(value) or value <= 0:
            continue
        ax_rain.axhline(value, color=color, linewidth=0.9, linestyle=linestyle, alpha=0.78, label=label)
        rain_y_candidates.append(value)
    rain_y_max = max([value for value in rain_y_candidates if np.isfinite(value)] or [1.0])
    rain_ylim = rain_y_max * 1.18 if rain_y_max > 0 else 1.0
    ax_rain.set_ylim(0, rain_ylim)

    ax_flow.plot(window.index, flow, color="#111827", linewidth=1.35, label="Observed Streamflow")
    ax_flow.axvspan(response_start, response_end, color="#f97316", alpha=0.08, label="response window")
    ax_flow.axvspan(rain_start, rain_end, color="#1d4ed8", alpha=0.10)

    obs_peak_time = event.get("observed_response_peak_time")
    obs_peak = safe_float(event.get("observed_response_peak"))
    if pd.notna(obs_peak_time) and np.isfinite(obs_peak):
        ax_flow.scatter([pd.Timestamp(obs_peak_time)], [obs_peak], s=34, color="#dc2626", zorder=4, label="Observed peak")

    thresholds = [
        ("Q99", safe_float(event.get("streamflow_q99_threshold")), "#71717a", ":"),
        ("flood ARI2", safe_float(event.get("flood_ari2")), "#ea580c", "--"),
        ("flood ARI25", safe_float(event.get("flood_ari25")), "#dc2626", "--"),
        ("flood ARI100", safe_float(event.get("flood_ari100")), "#7f1d1d", "--"),
    ]
    flow_max = finite_max(flow)
    flow_reference = max([v for v in [flow_max, obs_peak] if np.isfinite(v)] or [1.0])
    for label, value, color, linestyle in thresholds:
        if not np.isfinite(value) or value <= 0:
            continue
        if value > flow_reference * 3.0:
            continue
        ax_flow.axhline(value, color=color, linewidth=0.9, linestyle=linestyle, alpha=0.72, label=label)
    y_candidates = [flow_max, obs_peak]
    for _, value, _, _ in thresholds:
        if np.isfinite(value) and value <= flow_reference * 3.0:
            y_candidates.append(value)
    y_max = max([v for v in y_candidates if np.isfinite(v)] or [1.0])
    ax_flow.set_ylim(bottom=0, top=y_max * 1.14 if y_max > 0 else 1.0)
    ax_flow.set_ylabel("Streamflow")
    ax_flow.grid(True, axis="y", color="#d4d4d8", linewidth=0.55, alpha=0.85)

    rain_lines = [
        f"rain={event.get('rain_cohort')}",
        f"response={event.get('response_class')}",
        f"max ARI100 ratio={safe_float(event.get('max_prec_ari100_ratio')):.2f}",
        f"obs/flood2={safe_float(event.get('obs_peak_to_flood_ari2')):.2f}",
        f"obs/flood25={safe_float(event.get('obs_peak_to_flood_ari25')):.2f}",
    ]
    fig.suptitle(
        f"{event['event_id']} | basin {event['gauge_id']}\n{' | '.join(rain_lines)}",
        fontsize=9.4,
    )

    ax_flow.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=9))
    ax_flow.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax_flow.xaxis.get_major_locator()))

    add_external_legend(fig, ax_rain, event, precip_items)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def write_html_index(output_dir: Path, manifest: pd.DataFrame) -> Path:
    index_path = output_dir / "event_plot_index.html"
    mode_values = manifest["event_time_mode"].dropna().astype(str).unique().tolist() if "event_time_mode" in manifest else []
    is_wet_footprint = mode_values == ["wet_footprint"]
    page_title = (
        "Subset300 time-aligned extreme-rain event plots"
        if is_wet_footprint
        else "Subset300 extreme-rain event plots"
    )
    time_axis_note = (
        "이 v2 index는 primary event plot index와 같은 구조를 쓰되, rolling exceedance endpoint 대신 "
        "wet-footprint 기준 rain_start / rain_peak / rain_end를 사용합니다."
        if is_wet_footprint
        else "이 index는 후보 진입 이유인 rainfall severity 기준으로 먼저 묶고, 그 안에서 observed streamflow response class를 나눕니다."
    )
    rain_order = ["prec_ge100", "prec_ge50", "prec_ge25", "near_prec100"]
    response_order = [
        "flood_response_ge25",
        "flood_response_ge2_to_lt25",
        "high_flow_non_flood_q99_only",
        "low_response_below_q99",
    ]
    sorted_manifest = manifest.copy()
    sorted_manifest["rain_order"] = sorted_manifest["rain_cohort"].map(
        {name: idx for idx, name in enumerate(rain_order)}
    ).fillna(len(rain_order))
    sorted_manifest["response_order"] = sorted_manifest["response_class"].map(
        {name: idx for idx, name in enumerate(response_order)}
    ).fillna(len(response_order))
    sorted_manifest = sorted_manifest.sort_values(
        ["rain_order", "stress_group", "response_order", "gauge_id", "rain_start", "event_id"]
    )

    summary = (
        sorted_manifest.groupby(["rain_cohort", "stress_group", "response_class"], dropna=False)
        .size()
        .reset_index(name="n_events")
    )
    summary["rain_order"] = summary["rain_cohort"].map({name: idx for idx, name in enumerate(rain_order)}).fillna(
        len(rain_order)
    )
    summary["response_order"] = summary["response_class"].map(
        {name: idx for idx, name in enumerate(response_order)}
    ).fillna(len(response_order))
    summary = summary.sort_values(["rain_order", "stress_group", "response_order", "response_class"])
    summary_rows = "\n".join(
        [
            f"<tr><td>{html.escape(str(row.rain_cohort))}</td><td>{html.escape(str(row.stress_group))}</td>"
            f"<td>{html.escape(str(row.response_class))}</td><td>{int(row.n_events)}</td></tr>"
            for row in summary.itertuples(index=False)
        ]
    )

    sections: list[str] = []
    for rain_cohort, rain_group in sorted_manifest.groupby("rain_cohort", sort=False):
        rain_count = len(rain_group)
        section_parts = [
            f'<section class="rain-section" id="{html.escape(str(rain_cohort))}">',
            f"<h2>{html.escape(str(rain_cohort))} <span>{rain_count} events</span></h2>",
            "<p class=\"section-note\">이 묶음은 후보 진입 이유가 강수인 event들입니다. "
            "아래 response class는 같은 강수 후보가 실제 유량에서 positive였는지 negative였는지를 보여줍니다.</p>",
        ]
        for (stress, response), group in rain_group.groupby(["stress_group", "response_class"], sort=False):
            cards = []
            for _, row in group.iterrows():
                rel = relative_plot_path(output_dir, row["plot_path"])
                cards.append(
                    "\n".join(
                        [
                            '<article class="card">',
                            f'<a class="image-link" href="{html.escape(rel)}"><img src="{html.escape(rel)}" loading="lazy" alt="{html.escape(str(row["event_id"]))}"></a>',
                            f'<h3>{html.escape(str(row["event_id"]))}</h3>',
                            f'<p class="classline">{html.escape(str(stress))} · {html.escape(str(response))}</p>',
                            f'<p>{html.escape(inclusion_reason(row))} · max ARI100 ratio {html.escape(fmt_ratio(row.get("max_prec_ari100_ratio")))}</p>',
                            f'<p>max ARI25 ratio {html.escape(fmt_ratio(row.get("max_prec_ari25_ratio")))} · max ARI50 ratio {html.escape(fmt_ratio(row.get("max_prec_ari50_ratio")))}</p>',
                            f'<p>obs/flood2 {html.escape(fmt_ratio(row.get("obs_peak_to_flood_ari2")))} · obs/flood25 {html.escape(fmt_ratio(row.get("obs_peak_to_flood_ari25")))}</p>',
                            f'<p>rain peak {html.escape(str(row["rain_peak"]))} · obs peak {html.escape(str(row["observed_response_peak_time"]))}</p>',
                            "</article>",
                        ]
                    )
                )
            section_parts.extend(
                [
                    '<details class="condition-details">',
                    "<summary>"
                    f'<span class="condition-label">{html.escape(str(stress))} / {html.escape(str(response))}</span>'
                    f'<span class="condition-count">{len(group)} events</span>'
                    "</summary>",
                    '<section class="grid">',
                    "\n".join(cards),
                    "</section>",
                    "</details>",
                ]
            )
        section_parts.append("</section>")
        sections.append("\n".join(section_parts))

    body = "\n".join(sections)
    legend_html = """
  <details class="legend" open>
    <summary>표 열 설명</summary>
    <div class="legend-body">
      <div class="legend-col">
        <h4>rain cohort - 강수 ARI proxy 기준 그룹</h4>
        <dl>
          <dt>prec_ge100</dt><dd>1h/6h/24h/72h rolling precipitation 중 하나 이상이 basin별 <code>prec_ari100</code> proxy 이상인 event.</dd>
          <dt>prec_ge50</dt><dd><code>prec_ari100</code>은 넘지 않았지만, 하나 이상의 duration에서 <code>prec_ari50</code> proxy 이상인 event.</dd>
          <dt>prec_ge25</dt><dd><code>prec_ari50</code>은 넘지 않았지만, 하나 이상의 duration에서 <code>prec_ari25</code> proxy 이상인 event.</dd>
          <dt>near_prec100</dt><dd><code>prec_ari25/50/100</code> proxy는 넘지 않았지만 <code>max_prec_ari100_ratio >= 0.8</code>인 near-ARI100 event.</dd>
        </dl>
      </div>
      <div class="legend-col">
        <h4>stress group - 유량 반응 유무</h4>
        <dl>
          <dt>positive_response</dt><dd>강수 이후 observed streamflow가 <code>flood_ari2</code> proxy 이상으로 오른 event. 모델이 포착해야 할 response group.</dd>
          <dt>negative_control</dt><dd>강수 후보였지만 observed streamflow가 flood proxy까지 오르지 않은 event. upper quantile false-positive를 점검하는 대조군.</dd>
        </dl>
      </div>
      <div class="legend-col">
        <h4>response class - 유량 반응 세기</h4>
        <dl>
          <dt>flood_response_ge25</dt><dd>observed peak가 CAMELSH annual-maxima 기반 <code>flood_ari25</code> proxy 이상인 event.</dd>
          <dt>flood_response_ge2_to_lt25</dt><dd>observed peak가 <code>flood_ari2</code> proxy 이상이고 <code>flood_ari25</code> proxy 미만인 event.</dd>
          <dt>high_flow_non_flood_q99_only</dt><dd>observed peak가 basin별 <code>Q99</code> 이상이지만 <code>flood_ari2</code> proxy에는 못 미친 high-flow non-flood event.</dd>
          <dt>low_response_below_q99</dt><dd>observed peak가 basin별 <code>Q99</code>에도 못 미친 low-response event.</dd>
        </dl>
      </div>
    </div>
  </details>
"""
    lightbox_html = """
  <div class="lightbox" id="lightbox" hidden role="dialog" aria-modal="true" aria-labelledby="lightbox-title">
    <div class="lightbox-backdrop" data-lightbox-close></div>
    <div class="lightbox-panel">
      <button class="lightbox-close" type="button" data-lightbox-close aria-label="Close large image">Close</button>
      <div class="lightbox-image-frame">
        <img id="lightbox-image" src="" alt="">
      </div>
      <div class="lightbox-copy" id="lightbox-copy"></div>
      <div class="lightbox-nav">
        <button class="lightbox-nav-button" id="lightbox-prev" type="button" aria-label="Previous image">&larr;</button>
        <h3 id="lightbox-title"></h3>
        <button class="lightbox-nav-button" id="lightbox-next" type="button" aria-label="Next image">&rarr;</button>
      </div>
    </div>
  </div>
"""
    lightbox_script = """
  <script>
    (() => {
      const cards = Array.from(document.querySelectorAll(".card"));
      const items = cards.map((card, index) => {
        const link = card.querySelector(".image-link");
        const image = link ? link.querySelector("img") : null;
        const title = card.querySelector("h3");
        const paragraphs = Array.from(card.querySelectorAll("p")).map((node) => node.textContent.trim());
        if (link) {
          link.dataset.lightboxIndex = String(index);
        }
        return {
          href: link ? link.getAttribute("href") : "",
          alt: image ? image.getAttribute("alt") || "" : "",
          title: title ? title.textContent.trim() : "",
          paragraphs
        };
      });

      const lightbox = document.getElementById("lightbox");
      const lightboxImage = document.getElementById("lightbox-image");
      const lightboxCopy = document.getElementById("lightbox-copy");
      const lightboxTitle = document.getElementById("lightbox-title");
      const prevButton = document.getElementById("lightbox-prev");
      const nextButton = document.getElementById("lightbox-next");
      let activeIndex = 0;

      function render(index) {
        if (!items.length) {
          return;
        }
        activeIndex = (index + items.length) % items.length;
        const item = items[activeIndex];
        lightboxImage.src = item.href;
        lightboxImage.alt = item.alt || item.title;
        lightboxTitle.textContent = item.title;
        lightboxCopy.replaceChildren(
          ...item.paragraphs.map((text) => {
            const p = document.createElement("p");
            p.textContent = text;
            return p;
          })
        );
      }

      function openLightbox(index) {
        render(index);
        lightbox.hidden = false;
        document.body.classList.add("lightbox-open");
        nextButton.focus();
      }

      function closeLightbox() {
        lightbox.hidden = true;
        document.body.classList.remove("lightbox-open");
        lightboxImage.removeAttribute("src");
      }

      function move(delta) {
        render(activeIndex + delta);
      }

      document.addEventListener("click", (event) => {
        const link = event.target.closest(".image-link");
        if (!link) {
          return;
        }
        event.preventDefault();
        openLightbox(Number(link.dataset.lightboxIndex || 0));
      });

      document.querySelectorAll("[data-lightbox-close]").forEach((node) => {
        node.addEventListener("click", closeLightbox);
      });
      prevButton.addEventListener("click", () => move(-1));
      nextButton.addEventListener("click", () => move(1));

      document.addEventListener("keydown", (event) => {
        if (lightbox.hidden) {
          return;
        }
        if (event.key === "Escape") {
          closeLightbox();
        } else if (event.key === "ArrowLeft") {
          move(-1);
        } else if (event.key === "ArrowRight") {
          move(1);
        }
      });
    })();
  </script>
"""
    html_text = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>{html.escape(page_title)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; color: #18181b; }}
    h1 {{ font-size: 22px; margin: 0 0 8px; }}
    h2 {{ font-size: 20px; margin: 30px 0 6px; border-top: 1px solid #d4d4d8; padding-top: 18px; }}
    h2 span, h3 span {{ color: #71717a; font-weight: 500; }}
    h3 {{ font-size: 15px; margin: 18px 0 10px; }}
    .meta, .section-note {{ color: #52525b; margin: 0 0 18px; max-width: 980px; line-height: 1.45; }}
    table {{ border-collapse: collapse; margin: 14px 0 24px; font-size: 13px; }}
    th, td {{ border: 1px solid #d4d4d8; padding: 6px 8px; text-align: left; }}
    th {{ background: #f4f4f5; }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.95em; }}
    .legend {{ border: 1px solid #d4d4d8; border-radius: 8px; margin: 0 0 28px; padding: 0; background: #fafafa; }}
    .legend summary {{ padding: 10px 14px; font-weight: 600; font-size: 13px; cursor: pointer; color: #3f3f46; }}
    .legend-body {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); border-top: 1px solid #e4e4e7; }}
    .legend-col {{ padding: 14px 16px; border-right: 1px solid #e4e4e7; }}
    .legend-col:last-child {{ border-right: none; }}
    .legend-col h4 {{ font-size: 12px; font-weight: 700; margin: 0 0 10px; color: #18181b; text-transform: uppercase; letter-spacing: 0.04em; }}
    .legend-col dl {{ margin: 0; }}
    .legend-col dt {{ font-size: 12px; font-weight: 600; color: #18181b; margin-top: 8px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    .legend-col dd {{ font-size: 12px; color: #52525b; margin: 2px 0 0 0; line-height: 1.4; }}
    .condition-details {{ border: 1px solid #d4d4d8; border-radius: 8px; margin: 14px 0; background: #fff; }}
    .condition-details summary {{ align-items: center; cursor: pointer; display: flex; gap: 12px; justify-content: space-between; list-style: none; padding: 10px 12px; }}
    .condition-details summary::-webkit-details-marker {{ display: none; }}
    .condition-details summary::before {{ color: #71717a; content: "+"; flex: 0 0 auto; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-weight: 700; }}
    .condition-details[open] > summary::before {{ content: "-"; }}
    .condition-details summary:hover {{ background: #f4f4f5; }}
    .condition-label {{ color: #18181b; flex: 1 1 auto; font-size: 14px; font-weight: 650; }}
    .condition-count {{ color: #71717a; font-size: 13px; white-space: nowrap; }}
    .condition-details .grid {{ padding: 12px; border-top: 1px solid #e4e4e7; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 18px; }}
    .card {{ border: 1px solid #d4d4d8; border-radius: 8px; padding: 10px; background: #fff; }}
    .card .image-link {{ cursor: zoom-in; display: block; }}
    .card img {{ width: 100%; height: auto; display: block; border: 1px solid #e4e4e7; }}
    .card h3 {{ font-size: 13px; margin: 10px 0 4px; }}
    .card p {{ font-size: 12px; margin: 3px 0; color: #52525b; }}
    .card .classline {{ color: #18181b; font-weight: 600; }}
    body.lightbox-open {{ overflow: hidden; }}
    .lightbox[hidden] {{ display: none; }}
    .lightbox {{ align-items: center; display: flex; inset: 0; justify-content: center; padding: 24px; position: fixed; z-index: 20; }}
    .lightbox-backdrop {{ background: rgba(24, 24, 27, 0.74); inset: 0; position: absolute; }}
    .lightbox-panel {{ background: #fff; border-radius: 8px; box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35); max-height: calc(100vh - 48px); max-width: min(1200px, calc(100vw - 48px)); overflow: auto; padding: 14px; position: relative; width: 100%; }}
    .lightbox-close {{ background: #fff; border: 1px solid #d4d4d8; border-radius: 6px; color: #3f3f46; cursor: pointer; font-size: 12px; padding: 6px 9px; position: absolute; right: 14px; top: 14px; z-index: 1; }}
    .lightbox-close:hover, .lightbox-nav-button:hover {{ background: #f4f4f5; }}
    .lightbox-image-frame {{ align-items: center; background: #f4f4f5; border: 1px solid #e4e4e7; border-radius: 6px; display: flex; justify-content: center; min-height: 240px; padding: 10px; }}
    .lightbox-image-frame img {{ display: block; height: auto; max-height: min(70vh, 860px); max-width: 100%; object-fit: contain; }}
    .lightbox-copy {{ color: #52525b; display: grid; gap: 4px; font-size: 12px; line-height: 1.45; margin: 10px 0 12px; }}
    .lightbox-copy p {{ margin: 0; }}
    .lightbox-copy p:first-child {{ color: #18181b; font-weight: 650; }}
    .lightbox-nav {{ align-items: center; display: grid; gap: 12px; grid-template-columns: 48px minmax(0, 1fr) 48px; }}
    .lightbox-nav h3 {{ color: #3f3f46; font-size: 12px; font-weight: 600; line-height: 1.35; margin: 0; overflow-wrap: anywhere; text-align: center; }}
    .lightbox-nav-button {{ background: #fff; border: 1px solid #d4d4d8; border-radius: 6px; color: #18181b; cursor: pointer; font-size: 18px; height: 40px; line-height: 1; }}
  </style>
</head>
<body>
  <h1>{html.escape(page_title)}</h1>
  <p class="meta">{len(manifest)} event plots. {html.escape(time_axis_note)} Top panel: hourly Rainf. Bottom panel: observed Streamflow and response reference lines.</p>
  <table>
    <thead><tr><th>rain cohort</th><th>stress group</th><th>response class</th><th>events</th></tr></thead>
    <tbody>
{summary_rows}
    </tbody>
  </table>
{legend_html}
{body}
{lightbox_html}
{lightbox_script}
</body>
</html>
"""
    index_path.write_text(html_text, encoding="utf-8")
    return index_path


def write_readme(output_dir: Path, manifest: pd.DataFrame) -> Path:
    counts = manifest.groupby(["stress_group", "response_class"]).size().reset_index(name="n_events")
    count_lines = [
        f"| `{row.stress_group}` | `{row.response_class}` | {int(row.n_events)} |"
        for row in counts.itertuples(index=False)
    ]
    mode_values = manifest["event_time_mode"].dropna().astype(str).unique().tolist() if "event_time_mode" in manifest else []
    wet_mode = "wet_footprint" in mode_values
    event_definition = (
        "이 산출물의 `rain_start/rain_peak/rain_end`는 rolling precipitation exceedance window 안에서 실제 비가 집중된 wet footprint 기준이다."
        if wet_mode
        else "이 산출물의 `rain_start/rain_peak/rain_end`는 rolling precipitation exceedance endpoint 기준이다."
    )
    response_window_text = "response window = rain_start  ~  rain_end + 168h" if wet_mode else "response window = rain_start - 24h  ~  rain_end + 168h"
    readme = f"""# Extreme-Rain Event Plot Guide

이 폴더는 DRBC holdout basin의 historical extreme-rain stress event를 눈으로 확인하기 위한 관측 강우-유량 plot 모음이다. 총 event 수는 `{len(manifest)}`개이며, 각 PNG는 하나의 rain event와 그 뒤의 observed streamflow response를 보여준다.

{event_definition}

## 먼저 열 파일

- `event_plot_index.html`: 전체 plot을 썸네일로 훑어보는 index다. 후보 진입 이유인 `rain_cohort` 기준으로 먼저 묶고, 그 안에서 positive/negative response를 나눠 보여준다.
- `event_plot_manifest.csv`: event id, basin, rain cohort, response class, observed peak, plot path를 표로 정리한 manifest다.
- 하위 PNG 파일: 개별 event plot이다.

## 폴더 분류

폴더는 강수량이 아니라 **관측 유량 response** 기준으로 나뉜다. 모든 event는 먼저 hourly `Rainf`에서 극한호우 후보로 잡고, 그 뒤 response window 안의 observed `Streamflow` peak가 얼마나 올라갔는지로 positive/negative를 나눈다.

```text
event_plots/
├── positive_response/
│   ├── flood_response_ge25/
│   └── flood_response_ge2_to_lt25/
└── negative_control/
    ├── high_flow_non_flood_q99_only/
    └── low_response_below_q99/
```

| 큰 폴더 | 하위 폴더 | 의미 |
| --- | --- | --- |
| `positive_response` | `flood_response_ge25` | 극한호우 뒤 observed streamflow peak가 basin별 `flood_ari25` 이상까지 오른 event다. 가장 강한 홍수 response 그룹이다. |
| `positive_response` | `flood_response_ge2_to_lt25` | observed peak가 `flood_ari2` 이상이지만 `flood_ari25` 미만인 event다. 홍수성 반응은 있지만 25년급까지는 가지 않은 그룹이다. |
| `negative_control` | `high_flow_non_flood_q99_only` | observed peak가 평소 상위 1% 유량인 `Q99` 이상까지는 올랐지만 `flood_ari2`에는 못 미친 event다. 큰 비 뒤 high flow는 있었지만 flood proxy는 넘지 않은 경우다. |
| `negative_control` | `low_response_below_q99` | observed peak가 `Q99`에도 못 미친 event다. 극한호우 후보였지만 관측 유량 response는 낮았던 경우다. |

현재 생성된 event 수는 다음과 같다.

| stress group | response class | n events |
| --- | --- | ---: |
{chr(10).join(count_lines)}

## positive와 negative를 가르는 기준

핵심 기준은 response window 안의 observed streamflow peak다.

```text
{response_window_text}
```

이 구간에서 관측 유량 최대값을 찾고, basin별 flood proxy와 비교한다.

```text
observed_response_peak >= flood_ari25
  -> flood_response_ge25
  -> positive_response

flood_ari2 <= observed_response_peak < flood_ari25
  -> flood_response_ge2_to_lt25
  -> positive_response

observed_response_peak < flood_ari2 이고 observed_response_peak >= Q99
  -> high_flow_non_flood_q99_only
  -> negative_control

observed_response_peak < Q99
  -> low_response_below_q99
  -> negative_control
```

따라서 한 줄로 정리하면, **2년 홍수량 proxy인 `flood_ari2` 이상까지 관측 유량이 올랐으면 positive, 그보다 낮으면 negative**다.

## plot 읽는 방법

각 PNG의 위쪽 panel은 hourly `Rainf`다. 파란 막대가 시간별 강수량이고, 진한 파란 음영은 rain event 본 구간, 옅은 파란 음영은 rain event 주변 padding이다. 파란 실선은 `rain_start`/`rain_end`, 파란 점선은 `rain_peak`, 파란 가로 점선은 v2 wet-footprint를 잡을 때 쓴 `wet_rain_threshold_mm_h`다. 녹색/청록/보라 계열 가로선은 event별 dominant duration에 맞춘 `prec_ari25/50/100` 누적 강수량을 시간당 평균강도(mm/h)로 바꾼 참고선이다. Plot 바깥 오른쪽의 단일 legend 박스에서 **Rain** 아래에 표시 의미와 관련 index 값을 세로로 정리했다.

아래쪽 panel은 observed `Streamflow`다. 검은 선이 관측 유량이고, 빨간 점이 response window 안에서 찾은 observed peak다. 연한 주황색 음영은 response window다. 회색 점선은 `Q99`, 주황 점선은 `flood_ari2`, 빨간 점선은 `flood_ari25`, 짙은 적갈색 점선은 `flood_ari100`이다. 같은 바깥 legend 박스에서 **Streamflow** 아래에 표시 의미와 관련 index 값을 세로로 정리했다. 남는 legend 공간에는 **Basin** 섹션을 넣어 유역명, 면적, forest/developed 비율, hydromod proxy, dam/storage/canal/water use 같은 human-impact proxy를 짧게 표시한다. `storage` 값은 `STOR_NOR_2009`이며 단위는 `ML/km2`이고, `water use` 값은 `FRESHW_WITHDRAWAL`이며 단위는 `ML/yr/km2`다. 이 섹션은 `broad`/`natural` 라벨을 그대로 쓰지 않고, 실제 판단 근거가 되는 속성만 보여준다.

제목에는 해당 event를 빠르게 판단할 수 있는 값이 들어 있다.

```text
rain=prec_ge100
response=flood_response_ge25
max ARI100 ratio=1.57
obs/flood2=2.62
obs/flood25=1.26
```

여기서 `rain=...`은 강수 severity이고, `response=...`는 유량 response class다. 둘은 다른 축이다. 예를 들어 `rain=prec_ge100`인데도 `response=low_response_below_q99`일 수 있다. 이 경우는 100년급 강수 proxy가 잡혔지만 관측 유량은 flood-like하게 오르지 않은 negative-control event다.

## rain cohort 의미

`rain_cohort`는 강수 event의 강도를 나타낸다. 이것은 positive/negative를 직접 결정하지 않는다.

| rain cohort | 의미 |
| --- | --- |
| `prec_ge100` | 1h, 6h, 24h, 72h rolling precipitation 중 하나 이상이 `prec_ari100` 이상이다. |
| `prec_ge50` | ARI100은 넘지 않았지만 ARI50 이상이다. |
| `prec_ge25` | ARI50은 넘지 않았지만 ARI25 이상이다. |
| `near_prec100` | ARI25는 못 넘었더라도 ARI100의 80% 이상인 near-100 event다. |

HTML index는 이 `rain_cohort` 기준으로 먼저 묶는다. 따라서 `low_response_below_q99` 같은 유량 response가 낮은 event도 `prec_ge100`, `prec_ge50`, `prec_ge25`, `near_prec100` 중 하나에 들어가 있으면 극한호우 stress 후보가 된 이유를 바로 확인할 수 있다.

## 이 plot으로 확인할 질문

첫째, positive-response folder에서는 실제 유량 peak가 flood threshold를 넘는 시점과 강우 peak 사이의 lag를 본다. 이 그룹이 모델 stress test의 핵심 대상이다.

둘째, negative-control folder에서는 큰 비가 있었는데도 유량이 flood threshold까지 안 오른 이유를 눈으로 본다. 이 그룹은 모델이 괜히 홍수를 예측하는지 확인하는 false-positive 진단용이다.

셋째, `prec_ge100`이 항상 `flood_response_ge25`로 가지 않는다는 점을 확인한다. 같은 강수량이라도 antecedent condition, basin response, storm footprint 때문에 streamflow response는 달라질 수 있다.

## 주의할 점

`prec_ari*`와 `flood_ari*`는 공식 NOAA/USGS frequency product가 아니라 CAMELSH hourly annual-maxima 기반 proxy다. 그래서 이 plot은 “공식 100년 홍수 인증”이 아니라, 현재 데이터셋 안에서 극한호우와 유량 response를 비교하는 stress-test 진단으로 읽어야 한다.
"""
    readme_path = output_dir / "README.md"
    readme_path.write_text(readme, encoding="utf-8")
    return readme_path


def enrich_manifest_from_cohort(manifest: pd.DataFrame, cohort: pd.DataFrame) -> pd.DataFrame:
    out = manifest.copy()
    cohort_by_event = cohort.set_index("event_id", drop=False)
    for col in [
        "gauge_id",
        "stress_group",
        "rain_cohort",
        "response_class",
        "rain_start",
        "rain_peak",
        "rain_end",
        "observed_response_peak_time",
        "observed_response_peak",
        "max_prec_ari25_ratio",
        "max_prec_ari50_ratio",
        "max_prec_ari100_ratio",
        "obs_peak_to_flood_ari2",
        "obs_peak_to_flood_ari25",
        "event_time_mode",
        "rolling_endpoint_start",
        "rolling_endpoint_peak",
        "rolling_severity_peak_time",
        "rolling_endpoint_end",
        "rolling_envelope_start",
        "rolling_envelope_end",
        "wet_cluster_total_rain",
        "wet_cluster_peak_rainf",
        "wet_rain_threshold_mm_h",
        "response_lag_from_rain_peak_h",
        "response_lag_from_rain_start_h",
        "temporal_alignment_flag",
        *precip_event_columns(),
        *precip_reference_columns(),
        *basin_metadata_columns(),
    ]:
        if col not in out.columns and col in cohort_by_event.columns:
            out[col] = out["event_id"].map(cohort_by_event[col])
    if "stress_group" not in out.columns:
        out["stress_group"] = out["response_class"].map(stress_group)
    return out


def main() -> int:
    args = parse_args()
    cohort = read_cohort(args.cohort_csv, args.include_unrated)
    cohort = add_precip_references(cohort, args.return_period_csv)
    cohort = add_basin_metadata(cohort, args.basin_screening_csv, args.streamflow_quality_csv)
    if args.limit_events is not None:
        cohort = cohort.head(args.limit_events).copy()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.index_only:
        manifest_path = args.output_dir / "event_plot_manifest.csv"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Missing existing manifest for --index-only: {manifest_path}")
        manifest = pd.read_csv(manifest_path, dtype={"gauge_id": str, "event_id": str})
        manifest["gauge_id"] = manifest["gauge_id"].map(normalize_gauge_id)
        manifest = enrich_manifest_from_cohort(manifest, cohort)
        manifest.to_csv(manifest_path, index=False)
        index_path = write_html_index(args.output_dir, manifest)
        readme_path = write_readme(args.output_dir, manifest)
        print(f"Wrote event plot manifest: {manifest_path}")
        print(f"Wrote event plot index: {index_path}")
        print(f"Wrote event plot guide: {readme_path}")
        return 0

    basin_cache: dict[str, pd.DataFrame] = {}
    rows: list[dict[str, Any]] = []
    for idx, event in cohort.iterrows():
        gauge_id = normalize_gauge_id(event["gauge_id"])
        if gauge_id not in basin_cache:
            basin_cache[gauge_id] = load_basin_series(args.data_dir, gauge_id)
        group = event["stress_group"]
        response = safe_slug(str(event["response_class"]))
        filename = safe_slug(str(event["event_id"])) + ".png"
        plot_path = args.output_dir / group / response / filename
        plot_event(
            event,
            basin_cache[gauge_id],
            plot_path,
            rain_padding_hours=args.rain_padding_hours,
            response_padding_hours=args.response_padding_hours,
        )
        row = {
            "event_id": event["event_id"],
            "gauge_id": gauge_id,
            "stress_group": group,
            "rain_cohort": event["rain_cohort"],
            "response_class": event["response_class"],
            "rain_start": event["rain_start"],
            "rain_peak": event["rain_peak"],
            "rain_end": event["rain_end"],
            "observed_response_peak_time": event["observed_response_peak_time"],
            "observed_response_peak": event["observed_response_peak"],
            "max_prec_ari25_ratio": event["max_prec_ari25_ratio"],
            "max_prec_ari50_ratio": event["max_prec_ari50_ratio"],
            "max_prec_ari100_ratio": event["max_prec_ari100_ratio"],
            "obs_peak_to_flood_ari2": event["obs_peak_to_flood_ari2"],
            "obs_peak_to_flood_ari25": event["obs_peak_to_flood_ari25"],
            "plot_path": str(plot_path),
        }
        for col in [
            "event_time_mode",
            "rolling_endpoint_start",
            "rolling_endpoint_peak",
            "rolling_severity_peak_time",
            "rolling_endpoint_end",
            "rolling_envelope_start",
            "rolling_envelope_end",
            "wet_cluster_total_rain",
            "wet_cluster_peak_rainf",
            "wet_rain_threshold_mm_h",
            "response_lag_from_rain_peak_h",
            "response_lag_from_rain_start_h",
            "temporal_alignment_flag",
            *precip_event_columns(),
            *precip_reference_columns(),
            *basin_metadata_columns(),
        ]:
            if col in event:
                row[col] = event[col]
        rows.append(row)
        if (idx + 1) % 25 == 0 or idx == 0 or idx + 1 == len(cohort):
            print(f"Plotted {idx + 1}/{len(cohort)} events", flush=True)

    manifest = pd.DataFrame(rows)
    manifest_path = args.output_dir / "event_plot_manifest.csv"
    manifest.to_csv(manifest_path, index=False)
    index_path = write_html_index(args.output_dir, manifest)
    readme_path = write_readme(args.output_dir, manifest)
    print(f"Wrote event plot manifest: {manifest_path}")
    print(f"Wrote event plot index: {index_path}")
    print(f"Wrote event plot guide: {readme_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
