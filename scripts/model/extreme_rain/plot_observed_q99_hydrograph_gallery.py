#!/usr/bin/env python3
"""Plot observed Q99+ hydrograph gallery for one DRBC basin."""

from __future__ import annotations

import argparse
import html
import warnings
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import xarray as xr


DEFAULT_EVENT_RESPONSE_TABLE = Path(
    "output/basin/drbc/analysis/event_response/tables/event_response_table.csv"
)
DEFAULT_TIMESERIES_DIR = Path("data/CAMELSH_generic/drbc_holdout_broad/time_series")
DEFAULT_OUTPUT_ROOT = Path("output/model_analysis/legacy/extreme_rain/primary/analysis")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create observed Q99+ hydrograph PNGs and an HTML gallery for one basin."
    )
    parser.add_argument(
        "gauge_id",
        nargs="?",
        help="USGS/CAMELSH gauge id, e.g. 01480638. Omit with --all-gauges.",
    )
    parser.add_argument(
        "--all-gauges",
        action="store_true",
        help="Create one hydrograph gallery per gauge_id in the event response table.",
    )
    parser.add_argument(
        "--gauge-list",
        type=Path,
        default=None,
        help="Optional newline-delimited gauge id list for batch mode.",
    )
    parser.add_argument(
        "--event-response-table",
        type=Path,
        default=DEFAULT_EVENT_RESPONSE_TABLE,
        help="Event response table containing event_start/event_peak/event_end.",
    )
    parser.add_argument(
        "--timeseries-dir",
        type=Path,
        default=DEFAULT_TIMESERIES_DIR,
        help="Directory containing basin NetCDF time-series files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory. Defaults to analysis/{gauge_id}_hydrograph.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Batch output root. Each gauge is written to {output_root}/{gauge_id}_hydrograph.",
    )
    parser.add_argument(
        "--padding-hours",
        type=int,
        default=72,
        help="Hours before event_start and after event_end to include in each plot.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="PNG resolution.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Reuse existing PNGs/manifests when the expected files are already present.",
    )
    return parser.parse_args()


def read_basin_events(path: Path, gauge_id: str) -> pd.DataFrame:
    events = pd.read_csv(path, dtype={"gauge_id": str})
    basin_events = events.loc[events["gauge_id"].eq(gauge_id)].copy()
    if basin_events.empty:
        raise RuntimeError(f"No events found for gauge_id={gauge_id} in {path}")

    for col in ["event_start", "event_peak", "event_end"]:
        basin_events[col] = pd.to_datetime(basin_events[col])

    return basin_events.sort_values(["event_peak", "event_id"]).reset_index(drop=True)


def read_timeseries(timeseries_dir: Path, gauge_id: str) -> pd.DataFrame:
    path = timeseries_dir / f"{gauge_id}.nc"
    if not path.exists():
        raise FileNotFoundError(path)

    with xr.open_dataset(path) as ds:
        frame = ds[["Rainf", "Streamflow"]].to_dataframe().reset_index()
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


def format_dt(value: pd.Timestamp) -> str:
    return value.strftime("%Y-%m-%d %H:%M")


def filename_dt(value: pd.Timestamp) -> str:
    return value.strftime("%Y%m%dT%H%M")


def plot_event(
    event: pd.Series,
    ts: pd.DataFrame,
    output_dir: Path,
    index: int,
    padding_hours: int,
    dpi: int,
    skip_existing: bool = False,
) -> dict[str, object]:
    event_start = event["event_start"]
    event_peak = event["event_peak"]
    event_end = event["event_end"]
    plot_start = event_start - pd.Timedelta(hours=padding_hours)
    plot_end = event_end + pd.Timedelta(hours=padding_hours)

    window = ts.loc[(ts["date"] >= plot_start) & (ts["date"] <= plot_end)].copy()
    if window.empty:
        raise RuntimeError(f"No time-series data in plot window for {event['event_id']}")

    q99 = float(event["selected_threshold_value"])
    peak_q = float(event["peak_discharge"])
    gauge_id = str(event["gauge_id"])
    gauge_name = str(event["gauge_name"])
    event_id = str(event["event_id"])
    filename = (
        f"{gauge_id}_q99_hydrograph_{index:03d}_{filename_dt(event_peak)}_{event_id}.png"
    )
    output_path = output_dir / filename

    result = {
        "gauge_id": gauge_id,
        "gauge_name": gauge_name,
        "event_id": event_id,
        "event_start": event_start.isoformat(),
        "event_peak": event_peak.isoformat(),
        "event_end": event_end.isoformat(),
        "plot_start": plot_start.isoformat(),
        "plot_end": plot_end.isoformat(),
        "q99_threshold": q99,
        "peak_discharge": peak_q,
        "event_duration_hours": int(event["event_duration_hours"]),
        "rising_time_hours": int(event["rising_time_hours"]),
        "recession_time_hours": int(event["recession_time_hours"]),
        "recent_rain_6h": event.get("recent_rain_6h"),
        "recent_rain_24h": event.get("recent_rain_24h"),
        "recent_rain_72h": event.get("recent_rain_72h"),
        "antecedent_rain_7d": event.get("antecedent_rain_7d"),
        "antecedent_rain_30d": event.get("antecedent_rain_30d"),
        "plot_path": str(output_path),
    }
    if skip_existing and output_path.exists():
        return result

    fig, (ax_rain, ax_q) = plt.subplots(
        nrows=2,
        ncols=1,
        figsize=(16, 8),
        sharex=True,
        gridspec_kw={"height_ratios": [1, 2.2], "hspace": 0.08},
    )

    title = (
        f"{gauge_id} | {gauge_name} | observed Q99+ hydrograph\n"
        f"{event_id} | span {format_dt(event_start)} to {format_dt(event_end)} "
        f"| peak {format_dt(event_peak)} | duration {int(event['event_duration_hours'])} h"
    )
    fig.suptitle(title, fontsize=15, fontweight="bold")

    ax_rain.bar(
        window["date"],
        window["Rainf"].fillna(0),
        width=0.03,
        color="#4379e8",
        edgecolor="none",
        align="center",
    )
    ax_rain.axvspan(event_start, event_end, color="#f4b183", alpha=0.25, lw=0)
    ax_rain.axvline(event_peak, color="#c45a11", linestyle="--", linewidth=1.2)
    ax_rain.set_ylabel("Rainf\n(mm/h)", fontsize=12)
    ax_rain.grid(axis="y", color="#d9d9d9", linewidth=0.7)
    ax_rain.set_ylim(bottom=0)

    ax_q.plot(
        window["date"],
        window["Streamflow"],
        color="#111827",
        linewidth=1.8,
        label="Observed Streamflow",
    )
    ax_q.axhline(q99, color="#6b7280", linestyle=":", linewidth=1.4, label=f"Q99 = {q99:.3f} m^3/s")
    ax_q.axvspan(event_start, event_end, color="#f4b183", alpha=0.25, lw=0, label="Q99+ event span")
    ax_q.axvline(event_start, color="#ff7f2a", linewidth=1.0)
    ax_q.axvline(event_end, color="#ff7f2a", linewidth=1.0)
    ax_q.axvline(event_peak, color="#c45a11", linestyle="--", linewidth=1.2, label="Event peak time")
    ax_q.scatter(
        [event_peak],
        [peak_q],
        color="#dc2626",
        s=55,
        zorder=5,
        label=f"Peak = {peak_q:.3f} m^3/s",
    )
    ax_q.set_ylabel("Streamflow\n(m^3/s)", fontsize=12)
    ax_q.set_xlabel("Datetime", fontsize=12)
    ax_q.grid(axis="y", color="#d9d9d9", linewidth=0.7)
    ax_q.set_ylim(bottom=0)
    ax_q.legend(loc="upper right", frameon=True, fontsize=10)

    locator = mdates.AutoDateLocator(minticks=5, maxticks=9)
    ax_q.xaxis.set_major_locator(locator)
    ax_q.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="This figure includes Axes that are not compatible with tight_layout.*",
            category=UserWarning,
        )
        fig.tight_layout(rect=[0, 0, 1, 0.93])

    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)

    return result


def write_readme(
    output_dir: Path,
    gauge_id: str,
    gauge_name: str,
    timeseries_path: Path,
    event_response_table: Path,
    q99: float,
    n_events: int,
    padding_hours: int,
) -> None:
    text = f"""# {gauge_id} Q99 Hydrographs

Observed hydrographs for all Q99+ flow events from `{event_response_table}`.

- Gauge: {gauge_id} | {gauge_name}
- Source series: `{timeseries_path}`
- Q99 threshold: {q99:.10f} m^3/s
- Events plotted: {n_events}
- Plot window: `event_start - {padding_hours}h` to `event_end + {padding_hours}h`
- Event span source: `event_start`, `event_peak`, `event_end` from `event_response_table.csv`

See `{gauge_id}_q99_hydrograph_manifest.csv` for event metadata and plot paths.
"""
    (output_dir / "README.md").write_text(text, encoding="utf-8")


def write_index(
    output_dir: Path,
    gauge_id: str,
    gauge_name: str,
    manifest: pd.DataFrame,
    event_response_table: Path = DEFAULT_EVENT_RESPONSE_TABLE,
    padding_hours: int = 72,
) -> None:
    events = []
    for _, row in manifest.reset_index(drop=True).iterrows():
        plot_name = Path(str(row["plot_path"])).name
        events.append(
            {
                "eventId": str(row["event_id"]),
                "eventPeak": str(row["event_peak"]),
                "peakDischarge": f"{float(row['peak_discharge']):.3f}",
                "plot": plot_name,
            }
        )

    rows = "\n".join(
        f'      <tr><td>{html.escape(event["eventId"])}</td>'
        f'<td>{html.escape(event["eventPeak"])}</td>'
        f'<td>{html.escape(event["peakDischarge"])}</td>'
        f'<td><a href="{html.escape(event["plot"])}">PNG</a></td></tr>'
        for event in events
    )

    html_text = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>__TITLE__</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #111827;
      --muted: #5f6b7a;
      --line: #d7dde5;
      --soft: #f4f6f8;
      --panel: #ffffff;
      --active: #1d4ed8;
      --shadow: 0 10px 28px rgba(15, 23, 42, 0.10);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: #f8fafc;
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
      overflow-x: hidden;
      touch-action: manipulation;
      -webkit-tap-highlight-color: rgba(29, 78, 216, 0.16);
    }
    header {
      background: #fff;
      border-bottom: 1px solid var(--line);
      padding: 22px 24px 14px;
    }
    h1 { margin: 0 0 8px; font-size: 22px; line-height: 1.25; overflow-wrap: anywhere; }
    p { line-height: 1.5; }
    .intro {
      max-width: 1180px;
      margin: 0;
      color: var(--muted);
      font-size: 14px;
      overflow-wrap: anywhere;
    }
    .sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }
    .page-shell {
      width: min(100%, 1680px);
      margin: 0 auto;
      padding: 16px 24px 28px;
      display: grid;
      gap: 16px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      min-width: 0;
    }
    .gallery-panel { padding: 14px; }
    .review-workbench {
      display: grid;
      grid-template-columns: minmax(320px, 0.82fr) minmax(360px, 1.18fr);
      gap: 14px;
      align-items: start;
    }
    .section-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
      min-width: 0;
    }
    .section-head h2 {
      margin: 0;
      font-size: 16px;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }
    .section-head p {
      margin: 3px 0 0;
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
    }
    .toolbar, .review-tools {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .review-tools {
      justify-content: flex-start;
      margin-bottom: 12px;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfd;
    }
    .search-input, .select-input {
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      font: inherit;
      font-size: 13px;
      padding: 7px 10px;
    }
    .search-input { flex: 1 1 220px; min-width: min(100%, 220px); }
    .select-input { flex: 0 1 160px; }
    .viewer-button {
      appearance: none;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--ink);
      border-radius: 6px;
      cursor: pointer;
      min-height: 36px;
      padding: 7px 10px;
      font: inherit;
      font-size: 13px;
    }
    .viewer-button:hover, .lightbox-close:hover, .lightbox-nav-button:hover { background: var(--soft); }
    .viewer-button.is-active { border-color: var(--active); box-shadow: 0 0 0 2px rgba(29, 78, 216, 0.14); }
    .viewer-button:focus-visible,
    .plot-button:focus-visible,
    .search-input:focus-visible,
    .select-input:focus-visible,
    .lightbox-close:focus-visible,
    .lightbox-nav-button:focus-visible {
      outline: 2px solid var(--active);
      outline-offset: 2px;
    }
    .event-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(min(100%, 320px), 1fr));
      gap: 10px;
    }
    .event-grid-shell { min-width: 0; }
    .event-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      overflow: hidden;
      min-width: 0;
      content-visibility: auto;
      contain-intrinsic-size: 330px;
    }
    .event-card.is-selected { border-color: var(--active); box-shadow: 0 0 0 2px rgba(29, 78, 216, 0.12); }
    .plot-button {
      appearance: none;
      border: 0;
      border-bottom: 1px solid var(--line);
      background: #eef2f6;
      cursor: zoom-in;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      width: 100%;
      aspect-ratio: 2324 / 1208;
      overflow: hidden;
    }
    .plot-button:hover { background: #e3e9ef; }
    .plot-button img {
      display: block;
      width: 100%;
      height: 100%;
      object-fit: contain;
      background: #f8fafc;
    }
    .event-copy { padding: 8px; }
    .event-copy h3 {
      margin: 0 0 5px;
      font-size: 12px;
      line-height: 1.25;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .event-copy p {
      margin: 3px 0;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.35;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .selected-event {
      position: sticky;
      top: 14px;
      padding: 14px;
      display: grid;
      gap: 10px;
      min-width: 0;
    }
    .selected-event h3 {
      margin: 0;
      font-size: 16px;
      line-height: 1.25;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .selected-caption {
      margin: 4px 0 0;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .selected-event-media {
      width: 100%;
      aspect-ratio: 2324 / 1208;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #eef2f6;
      overflow: hidden;
      cursor: zoom-in;
      padding: 0;
    }
    .selected-event-media img {
      width: 100%;
      height: 100%;
      object-fit: contain;
      display: block;
      background: #f8fafc;
    }
    .selected-meta {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }
    .selected-meta div {
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 8px;
      background: #fbfcfd;
      min-width: 0;
    }
    .selected-meta span {
      display: block;
      color: var(--muted);
      font-size: 11px;
    }
    .selected-meta strong {
      display: block;
      margin-top: 3px;
      font-size: 13px;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .table-panel { overflow: hidden; }
    .table-panel summary {
      list-style: none;
      cursor: pointer;
      padding: 14px;
    }
    .table-panel summary::-webkit-details-marker { display: none; }
    .table-wrap { padding: 0 14px 14px; overflow: auto; }
    table {
      border-collapse: collapse;
      width: 100%;
      min-width: 720px;
    }
    th, td {
      border-bottom: 1px solid #e5e7eb;
      padding: 7px 9px;
      text-align: left;
      font-size: 13px;
    }
    th { background: #f9fafb; }
    td a { color: var(--active); text-decoration-thickness: 1px; text-underline-offset: 2px; }
    body.lightbox-open { overflow: hidden; }
    .lightbox[hidden] { display: none; }
    .lightbox {
      position: fixed;
      inset: 0;
      z-index: 50;
      display: grid;
      place-items: center;
      padding: 24px;
    }
    .lightbox-backdrop {
      position: absolute;
      inset: 0;
      background: rgba(15, 23, 42, 0.78);
    }
    .lightbox-panel {
      position: relative;
      z-index: 1;
      background: #fff;
      border-radius: 8px;
      width: min(1560px, calc(100vw - 32px));
      max-height: calc(100vh - 32px);
      overflow: auto;
      padding: 10px;
      box-shadow: 0 24px 80px rgba(0, 0, 0, 0.36);
    }
    .lightbox-close {
      position: absolute;
      top: 12px;
      right: 12px;
      z-index: 5;
      border: 1px solid var(--line);
      background: #fff;
      border-radius: 6px;
      padding: 6px 9px;
      cursor: pointer;
      font-size: 12px;
      box-shadow: 0 6px 18px rgba(15, 23, 42, 0.16);
    }
    .lightbox-image-shell { position: relative; }
    .lightbox-image-frame {
      display: flex;
      justify-content: center;
      align-items: center;
      background: #f3f6f8;
      border: 1px solid var(--line);
      border-radius: 7px;
      min-height: min(72vh, 780px);
      max-height: calc(100vh - 150px);
      overflow: auto;
      padding: 8px;
    }
    .lightbox-image-frame.is-zoomed {
      align-items: flex-start;
      cursor: grab;
      justify-content: flex-start;
    }
    .lightbox-image-frame.is-dragging { cursor: grabbing; }
    .lightbox-image {
      display: block;
      width: 100%;
      height: min(82vh, 900px);
      object-fit: contain;
      user-select: none;
    }
    .lightbox-caption {
      margin: 8px 86px 8px 0;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .lightbox-nav {
      display: grid;
      grid-template-columns: 44px minmax(0, 1fr) 44px;
      align-items: center;
      gap: 10px;
    }
    .lightbox-position {
      color: var(--muted);
      font-size: 12px;
      text-align: center;
      overflow-wrap: anywhere;
    }
    .lightbox-zoom-controls {
      display: inline-flex;
      gap: 6px;
      position: absolute;
      right: 14px;
      bottom: 14px;
      z-index: 2;
      border: 1px solid rgba(203, 213, 225, 0.92);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.94);
      box-shadow: var(--shadow);
      padding: 6px;
    }
    .lightbox-nav-button {
      border: 1px solid var(--line);
      background: #fff;
      border-radius: 6px;
      cursor: pointer;
      height: 38px;
      font-size: 17px;
    }
    .lightbox-nav-button:disabled {
      color: #9aa7b8;
      cursor: not-allowed;
      opacity: 0.7;
    }
    .lightbox-step-button { width: 44px; }
    .lightbox-zoom-button { width: 38px; }
    .lightbox-zoom-reset {
      min-width: 56px;
      padding: 0 8px;
      font-size: 12px;
    }
    @media (max-width: 720px) {
      header { padding-inline: 16px; }
      .page-shell { padding: 12px 16px 20px; }
      .review-workbench { grid-template-columns: 1fr; }
      .selected-event { position: static; order: -1; }
      .section-head { display: block; }
      .toolbar { justify-content: flex-start; margin-top: 10px; }
      .review-tools { display: grid; grid-template-columns: 1fr; }
      .select-input, .search-input { width: 100%; }
      .selected-meta { grid-template-columns: 1fr; }
      .lightbox { padding: 10px; }
      .lightbox-panel { width: calc(100vw - 20px); max-height: calc(100vh - 20px); }
      .lightbox-image-frame { min-height: min(62vh, 620px); }
    }
  </style>
</head>
<body>
  <header>
    <h1>__HEADING__</h1>
    <p class="intro">__INTRO__</p>
  </header>
  <main class="page-shell">
    <section class="panel gallery-panel" aria-labelledby="galleryHeading">
      <div class="section-head">
        <div>
          <h2 id="galleryHeading">Hydrograph gallery</h2>
          <p id="gallerySummary">__INITIAL_SUMMARY__</p>
        </div>
        <div class="toolbar" aria-label="Gallery controls">
          <button id="openFirst" class="viewer-button" type="button">첫 이미지 열기</button>
          <button id="openPeakMax" class="viewer-button" type="button">최대 peak 열기</button>
          <button id="openLatest" class="viewer-button" type="button">최근 event 열기</button>
        </div>
      </div>
      <div class="review-tools" aria-label="Event review controls">
        <label class="sr-only" for="eventSearch">event 검색</label>
        <input id="eventSearch" class="search-input" type="search" placeholder="event_id, peak, discharge 검색" autocomplete="off">
        <label class="sr-only" for="eventSort">정렬</label>
        <select id="eventSort" class="select-input">
          <option value="date_asc">event date 오름차순</option>
          <option value="date_desc">event date 내림차순</option>
          <option value="peak_desc">peak discharge 큰 순</option>
          <option value="peak_asc">peak discharge 작은 순</option>
        </select>
        <label class="sr-only" for="seasonFilter">season</label>
        <select id="seasonFilter" class="select-input">
          <option value="all">All seasons</option>
          <option value="DJF">DJF</option>
          <option value="MAM">MAM</option>
          <option value="JJA">JJA</option>
          <option value="SON">SON</option>
        </select>
        <button id="resetReview" class="viewer-button" type="button">필터 초기화</button>
      </div>
      <div class="review-workbench">
        <aside id="selectedEvent" class="panel selected-event" aria-live="polite"></aside>
        <div class="event-grid-shell">
          <div id="gallery" class="event-grid" aria-live="polite"></div>
        </div>
      </div>
    </section>
    <details class="panel table-panel" aria-labelledby="eventTableHeading">
      <summary>
        <div class="section-head">
          <div>
            <h2 id="eventTableHeading">Data table</h2>
            <p>Manifest row를 확인하거나 PNG 링크를 같은 viewer로 열 때 펼칩니다.</p>
          </div>
          <span class="viewer-button">열기 / 접기</span>
        </div>
      </summary>
      <div class="table-wrap">
        <table id="eventTable">
          <thead><tr><th>event_id</th><th>event_peak</th><th>peak_discharge m^3/s</th><th>plot</th></tr></thead>
          <tbody>
__ROWS__
          </tbody>
        </table>
      </div>
    </details>
  </main>

  <div id="lightbox" class="lightbox" hidden>
    <div class="lightbox-backdrop" data-close-lightbox></div>
    <div class="lightbox-panel" role="dialog" aria-modal="true" aria-label="Hydrograph preview">
      <button class="lightbox-close" type="button" data-close-lightbox>닫기</button>
      <div class="lightbox-image-shell">
        <div id="lightboxImageFrame" class="lightbox-image-frame">
          <img id="lightboxImage" class="lightbox-image" width="2324" height="1208" draggable="false" alt="">
        </div>
        <div class="lightbox-zoom-controls" aria-label="이미지 확대/축소">
          <button id="lightboxZoomOut" class="lightbox-nav-button lightbox-zoom-button" type="button" aria-label="이미지 축소">-</button>
          <button id="lightboxZoomReset" class="lightbox-nav-button lightbox-zoom-reset" type="button" aria-label="이미지 확대 초기화">100%</button>
          <button id="lightboxZoomIn" class="lightbox-nav-button lightbox-zoom-button" type="button" aria-label="이미지 확대">+</button>
        </div>
      </div>
      <div id="lightboxCaption" class="lightbox-caption"></div>
      <div class="lightbox-nav">
        <button id="lightboxPrev" class="lightbox-nav-button lightbox-step-button" type="button" aria-label="이전 hydrograph">&larr;</button>
        <span id="lightboxPosition" class="lightbox-position"></span>
        <button id="lightboxNext" class="lightbox-nav-button lightbox-step-button" type="button" aria-label="다음 hydrograph">&rarr;</button>
      </div>
    </div>
  </div>

  <script>
    const rows = [...document.querySelectorAll("#eventTable tbody tr")];
    const seasonForMonth = (month) => {
      if ([12, 1, 2].includes(month)) return "DJF";
      if ([3, 4, 5].includes(month)) return "MAM";
      if ([6, 7, 8].includes(month)) return "JJA";
      return "SON";
    };
    const events = rows.map((row, index) => {
      const cells = [...row.children];
      const link = row.querySelector("a");
      const peakDischarge = Number.parseFloat(cells[2]?.textContent ?? "");
      const eventPeak = cells[1]?.textContent.trim() ?? "";
      const peakDate = new Date(eventPeak);
      const month = Number.isNaN(peakDate.getTime()) ? 1 : peakDate.getMonth() + 1;
      const eventId = cells[0]?.textContent.trim() ?? "";
      return {
        index,
        eventId,
        eventPeak,
        peakDate,
        season: seasonForMonth(month),
        peakDischarge: Number.isFinite(peakDischarge) ? peakDischarge : null,
        plotPath: link?.getAttribute("href") ?? "",
        searchText: `${eventId} ${eventPeak} ${cells[2]?.textContent ?? ""}`.toLowerCase(),
      };
    });

    let currentEventIndex = 0;
    let activeEvents = [...events];
    let currentLightboxEvents = [...events];
    let selectedEvent = events.reduce((best, event) => {
      const bestPeak = best?.peakDischarge ?? Number.NEGATIVE_INFINITY;
      const eventPeak = event.peakDischarge ?? Number.NEGATIVE_INFINITY;
      return eventPeak > bestPeak ? event : best;
    }, events[0] ?? null);
    let lightboxZoom = 1;
    let lightboxBaseWidth = 0;
    let lightboxBaseHeight = 0;
    let isLightboxPanning = false;
    let lightboxPanStartX = 0;
    let lightboxPanStartY = 0;
    let lightboxPanStartLeft = 0;
    let lightboxPanStartTop = 0;
    const LIGHTBOX_MIN_ZOOM = 1;
    const LIGHTBOX_MAX_ZOOM = 4;
    const LIGHTBOX_ZOOM_STEP = 0.5;
    const LIGHTBOX_DOUBLE_CLICK_ZOOM = 1.5;

    const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]
    ));
    const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

    function eventCaption(event) {
      const peakValue = event.peakDischarge === null ? "NA" : `${event.peakDischarge.toFixed(3)} m^3/s`;
      return `${event.eventId} · peak ${event.eventPeak} · discharge ${peakValue}`;
    }

    function filteredEvents() {
      const query = document.getElementById("eventSearch").value.trim().toLowerCase();
      const season = document.getElementById("seasonFilter").value;
      const sortMode = document.getElementById("eventSort").value;
      const filtered = events.filter((event) => {
        const matchesQuery = !query || event.searchText.includes(query);
        const matchesSeason = season === "all" || event.season === season;
        return matchesQuery && matchesSeason;
      });
      return filtered.sort((a, b) => {
        if (sortMode === "date_desc") return b.peakDate - a.peakDate || a.eventId.localeCompare(b.eventId);
        if (sortMode === "peak_desc") return (b.peakDischarge ?? -Infinity) - (a.peakDischarge ?? -Infinity) || a.eventId.localeCompare(b.eventId);
        if (sortMode === "peak_asc") return (a.peakDischarge ?? Infinity) - (b.peakDischarge ?? Infinity) || a.eventId.localeCompare(b.eventId);
        return a.peakDate - b.peakDate || a.eventId.localeCompare(b.eventId);
      });
    }

    function renderSelectedEvent() {
      const container = document.getElementById("selectedEvent");
      if (!selectedEvent) {
        container.innerHTML = "<p class='selection-note'>선택된 event가 없습니다.</p>";
        return;
      }
      container.innerHTML = `
        <div>
          <h3>${escapeHtml(selectedEvent.eventId)}</h3>
          <p class="selected-caption">${escapeHtml(eventCaption(selectedEvent))}</p>
        </div>
        <button id="selectedOpen" class="selected-event-media" type="button" aria-label="선택 event hydrograph 확대">
          <img src="${escapeHtml(selectedEvent.plotPath)}" loading="lazy" width="900" height="468" alt="${escapeHtml(eventCaption(selectedEvent))}">
        </button>
        <div class="selected-meta">
          <div><span>event peak</span><strong>${escapeHtml(selectedEvent.eventPeak)}</strong></div>
          <div><span>season</span><strong>${escapeHtml(selectedEvent.season)}</strong></div>
          <div><span>peak discharge</span><strong>${selectedEvent.peakDischarge === null ? "NA" : `${selectedEvent.peakDischarge.toFixed(3)} m^3/s`}</strong></div>
          <div><span>view index</span><strong>${Math.max(1, activeEvents.findIndex((event) => event.index === selectedEvent.index) + 1)} / ${activeEvents.length}</strong></div>
        </div>
      `;
      document.getElementById("selectedOpen")?.addEventListener("click", () => openLightboxForEvent(selectedEvent));
    }

    function selectEvent(event) {
      selectedEvent = event ?? null;
      renderSelectedEvent();
      document.querySelectorAll(".event-card").forEach((card) => {
        card.classList.toggle("is-selected", Number(card.dataset.eventIndex) === selectedEvent?.index);
      });
    }

    function renderGallery() {
      const gallery = document.getElementById("gallery");
      activeEvents = filteredEvents();
      if (!activeEvents.length) {
        gallery.innerHTML = "";
        selectedEvent = null;
        renderSelectedEvent();
        document.getElementById("gallerySummary").textContent = "조건에 맞는 Q99+ hydrograph가 없습니다.";
        return;
      }
      if (!selectedEvent || !activeEvents.some((event) => event.index === selectedEvent.index)) {
        selectedEvent = activeEvents[0];
      }
      gallery.innerHTML = activeEvents.map((event) => `
        <article class="event-card ${event.index === selectedEvent?.index ? "is-selected" : ""}" data-event-index="${event.index}">
          <button class="plot-button" type="button" data-event-index="${event.index}" aria-label="hydrograph 확대: ${escapeHtml(event.eventId)}">
            <img src="${escapeHtml(event.plotPath)}" loading="lazy" width="640" height="333" alt="${escapeHtml(eventCaption(event))}">
          </button>
          <div class="event-copy">
            <h3>${escapeHtml(event.eventId)}</h3>
            <p>peak ${escapeHtml(event.eventPeak)}</p>
            <p>season ${escapeHtml(event.season)}</p>
            <p>peak discharge ${event.peakDischarge === null ? "NA" : `${event.peakDischarge.toFixed(3)} m^3/s`}</p>
          </div>
        </article>
      `).join("");
      gallery.querySelectorAll(".plot-button").forEach((button) => {
        button.addEventListener("click", () => {
          const event = events[Number(button.dataset.eventIndex)];
          selectEvent(event);
          openLightboxForEvent(event);
        });
      });
      renderSelectedEvent();
      document.getElementById("gallerySummary").textContent = `${activeEvents.length} / ${events.length}개 Q99+ hydrograph를 표시합니다. 이미지를 누르면 viewer에서 앞/뒤 이동과 zoom을 사용할 수 있습니다.`;
    }

    function wireTableLinks() {
      rows.forEach((row, index) => {
        const link = row.querySelector("a");
        if (!link) return;
        link.textContent = "viewer";
        link.addEventListener("click", (event) => {
          event.preventDefault();
          selectEvent(events[index]);
          openLightboxForEvent(events[index]);
        });
      });
    }

    function getLightboxNodes() {
      return {
        frame: document.getElementById("lightboxImageFrame"),
        image: document.getElementById("lightboxImage"),
        zoomOut: document.getElementById("lightboxZoomOut"),
        zoomIn: document.getElementById("lightboxZoomIn"),
        zoomReset: document.getElementById("lightboxZoomReset"),
      };
    }

    function updateLightboxZoomControls() {
      const { zoomOut, zoomIn, zoomReset } = getLightboxNodes();
      if (!zoomOut || !zoomIn || !zoomReset) return;
      zoomOut.disabled = lightboxZoom <= LIGHTBOX_MIN_ZOOM;
      zoomIn.disabled = lightboxZoom >= LIGHTBOX_MAX_ZOOM;
      zoomReset.textContent = `${Math.round(lightboxZoom * 100)}%`;
    }

    function resetLightboxZoom() {
      const { frame, image } = getLightboxNodes();
      lightboxZoom = 1;
      lightboxBaseWidth = 0;
      lightboxBaseHeight = 0;
      isLightboxPanning = false;
      if (frame) {
        frame.classList.remove("is-zoomed", "is-dragging");
        frame.scrollLeft = 0;
        frame.scrollTop = 0;
      }
      if (image) {
        image.style.width = "";
        image.style.height = "";
        image.style.maxHeight = "";
      }
      updateLightboxZoomControls();
    }

    function measureLightboxBaseSize() {
      const { image } = getLightboxNodes();
      if (!image) return;
      resetLightboxZoom();
      requestAnimationFrame(() => {
        const rect = image.getBoundingClientRect();
        lightboxBaseWidth = rect.width;
        lightboxBaseHeight = rect.height;
      });
    }

    function setLightboxZoom(nextZoom, clientX, clientY) {
      const { frame, image } = getLightboxNodes();
      if (!frame || !image) return;
      if (!lightboxBaseWidth || !lightboxBaseHeight) {
        const rect = image.getBoundingClientRect();
        lightboxBaseWidth = rect.width;
        lightboxBaseHeight = rect.height;
      }

      const next = clamp(nextZoom, LIGHTBOX_MIN_ZOOM, LIGHTBOX_MAX_ZOOM);
      if (next === lightboxZoom) return;
      if (next <= LIGHTBOX_MIN_ZOOM) {
        resetLightboxZoom();
        return;
      }

      const frameRect = frame.getBoundingClientRect();
      const currentWidth = Math.max(1, lightboxBaseWidth * lightboxZoom);
      const currentHeight = Math.max(1, lightboxBaseHeight * lightboxZoom);
      const focalX = clientX ?? frameRect.left + frameRect.width / 2;
      const focalY = clientY ?? frameRect.top + frameRect.height / 2;
      const ratioX = (frame.scrollLeft + focalX - frameRect.left) / currentWidth;
      const ratioY = (frame.scrollTop + focalY - frameRect.top) / currentHeight;

      lightboxZoom = next;
      frame.classList.add("is-zoomed");
      image.style.maxHeight = "none";
      image.style.width = `${lightboxBaseWidth * lightboxZoom}px`;
      image.style.height = `${lightboxBaseHeight * lightboxZoom}px`;

      requestAnimationFrame(() => {
        const nextWidth = lightboxBaseWidth * lightboxZoom;
        const nextHeight = lightboxBaseHeight * lightboxZoom;
        frame.scrollLeft = ratioX * nextWidth - (focalX - frameRect.left);
        frame.scrollTop = ratioY * nextHeight - (focalY - frameRect.top);
        updateLightboxZoomControls();
      });
    }

    function renderLightbox(index) {
      if (!currentLightboxEvents.length) return;
      currentEventIndex = (index + currentLightboxEvents.length) % currentLightboxEvents.length;
      const event = currentLightboxEvents[currentEventIndex];
      const image = document.getElementById("lightboxImage");
      const caption = document.getElementById("lightboxCaption");
      const position = document.getElementById("lightboxPosition");
      resetLightboxZoom();
      image.onload = measureLightboxBaseSize;
      image.src = event.plotPath;
      image.alt = eventCaption(event);
      if (image.complete) measureLightboxBaseSize();
      caption.textContent = eventCaption(event);
      position.textContent = `${currentEventIndex + 1} / ${currentLightboxEvents.length}`;
    }

    function openLightbox(index) {
      openLightboxForEvent(activeEvents[index] || events[index]);
    }

    function openLightboxForEvent(event) {
      if (!event) return;
      currentLightboxEvents = activeEvents.some((item) => item.index === event.index) ? activeEvents : events;
      const targetIndex = Math.max(0, currentLightboxEvents.findIndex((item) => item.index === event.index));
      const lightbox = document.getElementById("lightbox");
      lightbox.hidden = false;
      document.body.classList.add("lightbox-open");
      renderLightbox(targetIndex);
      document.getElementById("lightboxNext").focus();
    }

    function moveLightbox(delta) {
      const lightbox = document.getElementById("lightbox");
      if (lightbox.hidden) return;
      renderLightbox(currentEventIndex + delta);
    }

    function closeLightbox() {
      const lightbox = document.getElementById("lightbox");
      lightbox.hidden = true;
      resetLightboxZoom();
      document.getElementById("lightboxImage").src = "";
      document.getElementById("lightboxCaption").textContent = "";
      document.getElementById("lightboxPosition").textContent = "";
      document.body.classList.remove("lightbox-open");
    }

    document.querySelectorAll("[data-close-lightbox]").forEach((node) => {
      node.addEventListener("click", closeLightbox);
    });
    document.getElementById("lightboxPrev").addEventListener("click", () => moveLightbox(-1));
    document.getElementById("lightboxNext").addEventListener("click", () => moveLightbox(1));
    document.getElementById("lightboxZoomOut").addEventListener("click", () => setLightboxZoom(lightboxZoom - LIGHTBOX_ZOOM_STEP));
    document.getElementById("lightboxZoomIn").addEventListener("click", () => setLightboxZoom(lightboxZoom + LIGHTBOX_ZOOM_STEP));
    document.getElementById("lightboxZoomReset").addEventListener("click", resetLightboxZoom);
    document.getElementById("openFirst").addEventListener("click", () => {
      selectEvent(activeEvents[0]);
      openLightbox(0);
    });
    document.getElementById("openPeakMax").addEventListener("click", () => {
      const source = activeEvents.length ? activeEvents : events;
      const maxPeak = source.reduce((best, event) => {
        const bestPeak = best.peakDischarge ?? Number.NEGATIVE_INFINITY;
        const eventPeak = event.peakDischarge ?? Number.NEGATIVE_INFINITY;
        return eventPeak > bestPeak ? event : best;
      }, source[0]);
      selectEvent(maxPeak);
      openLightboxForEvent(maxPeak);
    });
    document.getElementById("openLatest").addEventListener("click", () => {
      const source = activeEvents.length ? activeEvents : events;
      const latest = source.reduce((best, event) => event.peakDate > best.peakDate ? event : best, source[0]);
      selectEvent(latest);
      openLightboxForEvent(latest);
    });
    document.getElementById("eventSearch").addEventListener("input", renderGallery);
    document.getElementById("eventSort").addEventListener("change", renderGallery);
    document.getElementById("seasonFilter").addEventListener("change", renderGallery);
    document.getElementById("resetReview").addEventListener("click", () => {
      document.getElementById("eventSearch").value = "";
      document.getElementById("eventSort").value = "date_asc";
      document.getElementById("seasonFilter").value = "all";
      selectedEvent = events[0] ?? null;
      renderGallery();
    });

    const lightboxImageFrame = document.getElementById("lightboxImageFrame");
    lightboxImageFrame.addEventListener("wheel", (event) => {
      if (!event.ctrlKey && !event.metaKey) return;
      event.preventDefault();
      const direction = event.deltaY > 0 ? -1 : 1;
      const wheelStep = clamp(Math.abs(event.deltaY) / 400, 0.05, 0.25);
      setLightboxZoom(lightboxZoom + direction * wheelStep, event.clientX, event.clientY);
    }, { passive: false });
    lightboxImageFrame.addEventListener("dblclick", (event) => {
      setLightboxZoom(lightboxZoom > LIGHTBOX_MIN_ZOOM ? LIGHTBOX_MIN_ZOOM : LIGHTBOX_DOUBLE_CLICK_ZOOM, event.clientX, event.clientY);
    });
    lightboxImageFrame.addEventListener("pointerdown", (event) => {
      if (lightboxZoom <= LIGHTBOX_MIN_ZOOM || (event.pointerType === "mouse" && event.button !== 0)) return;
      isLightboxPanning = true;
      lightboxPanStartX = event.clientX;
      lightboxPanStartY = event.clientY;
      lightboxPanStartLeft = lightboxImageFrame.scrollLeft;
      lightboxPanStartTop = lightboxImageFrame.scrollTop;
      lightboxImageFrame.classList.add("is-dragging");
      lightboxImageFrame.setPointerCapture(event.pointerId);
    });
    lightboxImageFrame.addEventListener("pointermove", (event) => {
      if (!isLightboxPanning) return;
      lightboxImageFrame.scrollLeft = lightboxPanStartLeft - (event.clientX - lightboxPanStartX);
      lightboxImageFrame.scrollTop = lightboxPanStartTop - (event.clientY - lightboxPanStartY);
    });
    ["pointerup", "pointercancel", "pointerleave"].forEach((eventName) => {
      lightboxImageFrame.addEventListener(eventName, (event) => {
        if (!isLightboxPanning) return;
        isLightboxPanning = false;
        lightboxImageFrame.classList.remove("is-dragging");
        if (lightboxImageFrame.hasPointerCapture(event.pointerId)) {
          lightboxImageFrame.releasePointerCapture(event.pointerId);
        }
      });
    });

    document.addEventListener("keydown", (event) => {
      const lightbox = document.getElementById("lightbox");
      if (lightbox.hidden) return;
      if (event.key === "Escape") {
        closeLightbox();
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        moveLightbox(-1);
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        moveLightbox(1);
      } else if (event.key === "+" || event.key === "=") {
        event.preventDefault();
        setLightboxZoom(lightboxZoom + LIGHTBOX_ZOOM_STEP);
      } else if (event.key === "-") {
        event.preventDefault();
        setLightboxZoom(lightboxZoom - LIGHTBOX_ZOOM_STEP);
      } else if (event.key === "0") {
        event.preventDefault();
        resetLightboxZoom();
      }
    });

    renderGallery();
    wireTableLinks();
    updateLightboxZoomControls();
  </script>
</body>
</html>
"""
    replacements = {
        "__TITLE__": html.escape(f"{gauge_id} Q99 Hydrographs"),
        "__HEADING__": html.escape(f"{gauge_id} observed Q99+ hydrographs"),
        "__INTRO__": html.escape(
            f"Source event table: {event_response_table}. "
            f"Plot window: event_start - {padding_hours}h to event_end + {padding_hours}h."
        ),
        "__INITIAL_SUMMARY__": html.escape(f"{len(events)}개 Q99+ hydrograph를 불러오는 중입니다."),
        "__ROWS__": rows,
    }
    for token, value in replacements.items():
        html_text = html_text.replace(token, value)

    (output_dir / "index.html").write_text(html_text, encoding="utf-8")


def read_gauge_ids_from_file(path: Path) -> list[str]:
    ids = []
    for line in path.read_text(encoding="utf-8").splitlines():
        gauge_id = line.strip()
        if gauge_id and not gauge_id.startswith("#"):
            ids.append(gauge_id)
    return ids


def batch_gauge_ids(args: argparse.Namespace) -> list[str]:
    if args.gauge_list:
        return read_gauge_ids_from_file(args.gauge_list)
    events = pd.read_csv(args.event_response_table, dtype={"gauge_id": str})
    return sorted(events["gauge_id"].dropna().astype(str).unique())


def manifest_is_complete(manifest_path: Path, expected_events: pd.DataFrame) -> bool:
    if not manifest_path.exists():
        return False
    try:
        manifest = pd.read_csv(manifest_path, dtype={"gauge_id": str})
    except pd.errors.EmptyDataError:
        return False
    if len(manifest) != len(expected_events):
        return False
    if not {"event_id", "plot_path"}.issubset(manifest.columns):
        return False
    expected_ids = set(expected_events["event_id"].astype(str))
    manifest_ids = set(manifest["event_id"].astype(str))
    if expected_ids != manifest_ids:
        return False
    return all(Path(path).exists() for path in manifest["plot_path"])


def run_one_gauge(args: argparse.Namespace, gauge_id: str, output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)

    events = read_basin_events(args.event_response_table, gauge_id)
    manifest_path = output_dir / f"{gauge_id}_q99_hydrograph_manifest.csv"
    if args.skip_existing and manifest_is_complete(manifest_path, events):
        manifest = pd.read_csv(manifest_path, dtype={"gauge_id": str})
        gauge_name = str(events.iloc[0]["gauge_name"])
        q99 = float(events.iloc[0]["selected_threshold_value"])
        timeseries_path = args.timeseries_dir / f"{gauge_id}.nc"
        write_readme(
            output_dir=output_dir,
            gauge_id=gauge_id,
            gauge_name=gauge_name,
            timeseries_path=timeseries_path,
            event_response_table=args.event_response_table,
            q99=q99,
            n_events=len(events),
            padding_hours=args.padding_hours,
        )
        write_index(
            output_dir,
            gauge_id,
            gauge_name,
            manifest,
            event_response_table=args.event_response_table,
            padding_hours=args.padding_hours,
        )
        print(f"Skipped existing complete gallery: {gauge_id} ({len(events)} hydrographs)", flush=True)
        return len(events)

    ts = read_timeseries(args.timeseries_dir, gauge_id)
    rows = [
        plot_event(
            event=event,
            ts=ts,
            output_dir=output_dir,
            index=index,
            padding_hours=args.padding_hours,
            dpi=args.dpi,
            skip_existing=args.skip_existing,
        )
        for index, (_, event) in enumerate(events.iterrows(), start=1)
    ]

    manifest = pd.DataFrame(rows)
    manifest.to_csv(manifest_path, index=False)

    gauge_name = str(events.iloc[0]["gauge_name"])
    q99 = float(events.iloc[0]["selected_threshold_value"])
    timeseries_path = args.timeseries_dir / f"{gauge_id}.nc"
    write_readme(
        output_dir=output_dir,
        gauge_id=gauge_id,
        gauge_name=gauge_name,
        timeseries_path=timeseries_path,
        event_response_table=args.event_response_table,
        q99=q99,
        n_events=len(events),
        padding_hours=args.padding_hours,
    )
    write_index(
        output_dir,
        gauge_id,
        gauge_name,
        manifest,
        event_response_table=args.event_response_table,
        padding_hours=args.padding_hours,
    )
    print(f"Wrote {len(events)} hydrographs to {output_dir}", flush=True)
    print(f"Manifest: {manifest_path}", flush=True)
    return len(events)


def main() -> None:
    args = parse_args()
    if args.all_gauges:
        if args.output_dir is not None:
            raise SystemExit("--output-dir is only valid for single-gauge mode. Use --output-root for batch mode.")
        gauge_ids = batch_gauge_ids(args)
        if not gauge_ids:
            raise SystemExit("No gauge ids found for batch mode.")
        total = 0
        for position, gauge_id in enumerate(gauge_ids, start=1):
            output_dir = args.output_root / f"{gauge_id}_hydrograph"
            print(f"[{position}/{len(gauge_ids)}] {gauge_id}", flush=True)
            total += run_one_gauge(args, gauge_id, output_dir)
        print(f"Wrote/skipped {total} total hydrographs across {len(gauge_ids)} basins.", flush=True)
        return

    if not args.gauge_id:
        raise SystemExit("Provide gauge_id or use --all-gauges.")
    output_dir = args.output_dir or args.output_root / f"{args.gauge_id}_hydrograph"
    run_one_gauge(args, args.gauge_id, output_dir)


if __name__ == "__main__":
    main()
