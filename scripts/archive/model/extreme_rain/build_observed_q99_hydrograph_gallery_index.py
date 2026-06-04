#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pandas>=2.2",
#   "pyproj>=3.6",
#   "pyshp>=2.3",
#   "shapely>=2.0",
# ]
# ///
"""Build a DRBC map index for observed Q99+ hydrograph galleries."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

import pandas as pd

from build_extreme_rain_median_map_index import (
    BASIN_FALLBACK_CRS,
    MAP_CRS,
    TIER_BY_KEY,
    TIER_BY_LABEL,
    TIER_CONFIG,
    basin_legend_metadata_lines,
    build_svg,
    finite_or_none,
    fmt_float,
    load_boundary_geometry,
    load_map_basin_rings,
    normalize_gauge_id,
    rel_path,
)


DEFAULT_HYDROGRAPH_ROOT = Path(
    "output/model_analysis/legacy/extreme_rain/primary/analysis"
)
DEFAULT_EVENT_RESPONSE_TABLE = Path(
    "output/basin/drbc/analysis/event_response/tables/event_response_table.csv"
)
DEFAULT_METADATA_MANIFEST = Path(
    "output/model_analysis/legacy/extreme_rain/primary/event_simq_plots/event_simq_plot_manifest.csv"
)
DEFAULT_TIER_PROFILE = Path(
    "output/model_analysis/legacy/overall_analysis/main_comparison/"
    "attribute_correlations/median_deviation/tables/"
    "metric_median_deviation_basin_tier_profile.csv"
)
DEFAULT_DRBC_SELECTED = Path("output/basin/drbc/basin_define/camelsh_drbc_selected.csv")
DEFAULT_CAMELSH_SHAPEFILE = Path("basins/CAMELSH_data/shapefiles/CAMELSH_shapefile.shp")
DEFAULT_DRBC_BOUNDARY = Path("basins/drbc_boundary/drb_bnd_polygon.shp")
DEFAULT_OUTPUT_HTML = Path(
    "output/model_analysis/legacy/extreme_rain/primary/"
    "observed_q99_hydrograph_gallery_index.html"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an interactive map index for observed Q99+ hydrograph galleries."
    )
    parser.add_argument("--hydrograph-root", type=Path, default=DEFAULT_HYDROGRAPH_ROOT)
    parser.add_argument("--event-response-table", type=Path, default=DEFAULT_EVENT_RESPONSE_TABLE)
    parser.add_argument("--metadata-manifest", type=Path, default=DEFAULT_METADATA_MANIFEST)
    parser.add_argument("--tier-profile", type=Path, default=DEFAULT_TIER_PROFILE)
    parser.add_argument("--drbc-selected", type=Path, default=DEFAULT_DRBC_SELECTED)
    parser.add_argument("--camelsh-shapefile", type=Path, default=DEFAULT_CAMELSH_SHAPEFILE)
    parser.add_argument("--drbc-boundary", type=Path, default=DEFAULT_DRBC_BOUNDARY)
    parser.add_argument(
        "--basin-geometry-source",
        choices=("camelsh", "gagesii-api"),
        default="camelsh",
        help=(
            "Basin geometry source for the map. 'camelsh' reads --camelsh-shapefile. "
            "'gagesii-api' fetches CRS-tagged USGS GAGES-II basin features and caches them."
        ),
    )
    parser.add_argument(
        "--gagesii-cache-dir",
        type=Path,
        default=None,
        help=(
            "Directory for cached USGS GAGES-II basin GeoJSON features. Defaults to "
            "<output-html-parent>/map_geometry/gagesii_basins."
        ),
    )
    parser.add_argument(
        "--gagesii-api-url",
        default="https://api.water.usgs.gov/fabric/pygeoapi/collections/gagesii-basins/items",
        help="USGS pygeoapi item endpoint used when --basin-geometry-source gagesii-api.",
    )
    parser.add_argument("--output-html", type=Path, default=DEFAULT_OUTPUT_HTML)
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Build the index from available hydrograph manifests even if some DRBC basins are missing.",
    )
    parser.add_argument("--svg-width", type=float, default=380)
    parser.add_argument("--svg-height", type=float, default=760)
    parser.add_argument("--simplify-px", type=float, default=0.0)
    return parser.parse_args()


def read_expected_events(path: Path) -> pd.DataFrame:
    events = pd.read_csv(path, dtype={"gauge_id": str})
    events["gauge_id"] = events["gauge_id"].map(normalize_gauge_id)
    return events


def read_tiers(path: Path) -> pd.DataFrame:
    tiers = pd.read_csv(path, dtype={"basin": str})
    tiers["gauge_id"] = tiers["basin"].map(normalize_gauge_id)
    tiers["tier_key"] = tiers["dominant_distance_label"].map(
        lambda label: TIER_BY_LABEL.get(str(label), TIER_CONFIG[0])["key"]
    )
    return tiers


def read_selected(path: Path) -> pd.DataFrame:
    selected = pd.read_csv(path, dtype={"gauge_id": str})
    selected["gauge_id"] = selected["gauge_id"].map(normalize_gauge_id)
    return selected


def read_metadata(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    metadata = pd.read_csv(path, dtype={"gauge_id": str})
    metadata["gauge_id"] = metadata["gauge_id"].map(normalize_gauge_id)
    return metadata


def hydrograph_manifest_paths(root: Path) -> list[Path]:
    return sorted(root.glob("*_hydrograph/*_q99_hydrograph_manifest.csv"))


def resolve_plot_path(manifest_path: Path, raw_plot_path: Any) -> Path:
    """Return an existing plot path for a manifest row.

    Older gallery manifests may contain the output directory used when the PNGs
    were first generated. When that gallery directory is moved or regenerated
    under a different analysis root, the PNG basename remains colocated with the
    manifest while the stored path becomes stale. Prefer the stored path when it
    still exists, but fall back to the local file next to the manifest before
    failing loudly.
    """
    raw_text = str(raw_plot_path)
    stored = Path(raw_text)
    if stored.exists():
        return stored

    local = manifest_path.parent / stored.name
    if local.exists():
        return local

    raise FileNotFoundError(
        f"Hydrograph PNG not found for manifest row: stored={raw_text}; "
        f"also tried local={local}"
    )


def fmt_area(value: Any) -> str:
    out = finite_or_none(value)
    if out is None:
        return "NA"
    if out >= 100:
        return f"{out:,.0f}"
    return f"{out:.1f}"


def build_basin_records(
    args: argparse.Namespace,
    expected_events: pd.DataFrame,
    tiers: pd.DataFrame,
    selected: pd.DataFrame,
    metadata: pd.DataFrame,
) -> dict[str, dict[str, Any]]:
    manifest_paths = hydrograph_manifest_paths(args.hydrograph_root)
    expected_gauge_ids = set(expected_events["gauge_id"].dropna().unique())
    manifest_gauge_ids = {
        normalize_gauge_id(path.parent.name.replace("_hydrograph", "")) for path in manifest_paths
    }
    missing = sorted(expected_gauge_ids - manifest_gauge_ids)
    if missing and not args.allow_missing:
        preview = ", ".join(missing[:12])
        suffix = "" if len(missing) <= 12 else f", +{len(missing) - 12} more"
        raise RuntimeError(f"Missing hydrograph galleries for {preview}{suffix}")

    tiers_by_id = tiers.set_index("gauge_id", drop=False)
    selected_by_id = selected.set_index("gauge_id", drop=False)
    expected_by_id = {
        gauge_id: group.copy()
        for gauge_id, group in expected_events.groupby("gauge_id", sort=True)
    }
    if metadata.empty:
        metadata_by_id = {}
    else:
        metadata_by_id = {
            gauge_id: group.iloc[0]
            for gauge_id, group in metadata.groupby("gauge_id", sort=True)
        }

    records: dict[str, dict[str, Any]] = {}
    for manifest_path in manifest_paths:
        gauge_id = normalize_gauge_id(manifest_path.parent.name.replace("_hydrograph", ""))
        if gauge_id not in expected_gauge_ids:
            continue
        if gauge_id not in tiers_by_id.index:
            raise RuntimeError(f"Missing median-distance tier profile for {gauge_id}")

        manifest = pd.read_csv(manifest_path, dtype={"gauge_id": str})
        if manifest.empty:
            continue
        manifest["event_peak"] = pd.to_datetime(manifest["event_peak"])
        manifest = manifest.sort_values(["event_peak", "event_id"]).reset_index(drop=True)
        tier = tiers_by_id.loc[gauge_id]
        selected_row = selected_by_id.loc[gauge_id] if gauge_id in selected_by_id.index else {}
        metadata_row = metadata_by_id.get(gauge_id)
        fallback_event_row = expected_by_id[gauge_id].iloc[0]
        legend_row = metadata_row if metadata_row is not None else fallback_event_row
        tier_key = str(tier["tier_key"])
        gallery_path = manifest_path.parent / "index.html"

        events = []
        for _, event in manifest.iterrows():
            peak_q = finite_or_none(event.get("peak_discharge"))
            plot_path = resolve_plot_path(manifest_path, event["plot_path"])
            events.append(
                {
                    "eventId": str(event["event_id"]),
                    "eventPeak": pd.Timestamp(event["event_peak"]).isoformat(),
                    "eventStart": str(event.get("event_start", "")),
                    "eventEnd": str(event.get("event_end", "")),
                    "peakDischarge": "NA" if peak_q is None else f"{peak_q:.3f}",
                    "plotPath": rel_path(args.output_html, plot_path),
                }
            )

        max_peak = manifest["peak_discharge"].map(finite_or_none).dropna().max()
        counts = {
            "near": int(tier.get("near_median_lt_0_5_iqr", 0)),
            "shoulder": int(tier.get("shoulder_0_5_to_1_5_iqr", 0)),
            "far": int(tier.get("far_1_5_to_3_iqr", 0)),
            "extreme": int(tier.get("extreme_ge_3_iqr", 0)),
        }
        records[gauge_id] = {
            "gaugeId": gauge_id,
            "gaugeName": str(tier.get("gauge_name", fallback_event_row.get("gauge_name", ""))),
            "state": str(tier.get("state", fallback_event_row.get("state", ""))),
            "tierKey": tier_key,
            "tierLabel": TIER_BY_KEY[tier_key]["label"],
            "tierShortLabel": TIER_BY_KEY[tier_key]["shortLabel"],
            "tierColor": TIER_BY_KEY[tier_key]["color"],
            "eventCount": int(len(events)),
            "lat": finite_or_none(selected_row.get("lat_gage") if hasattr(selected_row, "get") else None),
            "lon": finite_or_none(selected_row.get("lng_gage") if hasattr(selected_row, "get") else None),
            "area": fmt_area(tier.get("area")),
            "obsQ99": fmt_float(tier.get("obs_q99"), 2),
            "q99EventFrequency": fmt_float(tier.get("q99_event_frequency"), 2),
            "rbi": fmt_float(tier.get("rbi"), 3),
            "farOrExtremeRecords": int(tier.get("far_or_extreme_records", 0)),
            "farOrExtremeShare": fmt_float(tier.get("far_or_extreme_share"), 2),
            "meanDistance": fmt_float(tier.get("mean_distance_any_metric_seed"), 2),
            "maxDistance": fmt_float(tier.get("max_distance_any_metric_seed"), 2),
            "maxObservedPeak": "NA" if pd.isna(max_peak) else f"{float(max_peak):.2f}",
            "galleryPath": rel_path(args.output_html, gallery_path),
            "legendMetadataLines": basin_legend_metadata_lines(legend_row),
            "distanceCounts": counts,
            "events": events,
        }

    return records


def build_summary(basin_records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_tier = {}
    for tier in TIER_CONFIG:
        basins = [record for record in basin_records.values() if record["tierKey"] == tier["key"]]
        by_tier[tier["key"]] = {
            "basins": len(basins),
            "events": sum(record["eventCount"] for record in basins),
        }
    return {
        "basins": len(basin_records),
        "events": sum(record["eventCount"] for record in basin_records.values()),
        "byTier": by_tier,
    }


def render_html(
    svg: str,
    basin_records: dict[str, dict[str, Any]],
    summary: dict[str, Any],
    args: argparse.Namespace,
) -> str:
    basins_json = json.dumps(list(basin_records.values()), ensure_ascii=False, allow_nan=False)
    tiers_json = json.dumps(TIER_CONFIG, ensure_ascii=False, allow_nan=False)
    summary_json = json.dumps(summary, ensure_ascii=False, allow_nan=False)
    source_json = json.dumps(
        {
            "hydrographRoot": str(args.hydrograph_root),
            "eventResponseTable": str(args.event_response_table),
            "metadataManifest": str(args.metadata_manifest),
            "tierProfile": str(args.tier_profile),
            "drbcSelected": str(args.drbc_selected),
            "camelshShapefile": str(args.camelsh_shapefile),
            "drbcBoundary": str(args.drbc_boundary),
            "basinGeometrySource": str(args.basin_geometry_source),
            "gagesiiCacheDir": (
                None
                if getattr(args, "resolved_gagesii_cache_dir", None) is None
                else str(args.resolved_gagesii_cache_dir)
            ),
            "gagesiiApiUrl": str(args.gagesii_api_url),
            "mapCrs": MAP_CRS,
            "basinFallbackCrs": BASIN_FALLBACK_CRS,
        },
        ensure_ascii=False,
        allow_nan=False,
    )
    tier_cards = "\n".join(
        (
            f'<button class="tier-button" type="button" data-tier-key="{html.escape(tier["key"])}">'
            f'<span class="tier-dot" style="background:{html.escape(tier["color"])}"></span>'
            f'<span><strong>{html.escape(tier["label"])}</strong>'
            f'<small>{summary["byTier"][tier["key"]]["basins"]} basins · '
            f'{summary["byTier"][tier["key"]]["events"]} hydrographs</small></span>'
            "</button>"
        )
        for tier in TIER_CONFIG
    )
    if args.basin_geometry_source == "gagesii-api":
        map_geometry_source = (
            f'<code>{html.escape(str(args.gagesii_api_url))}</code> '
            f'(USGS GAGES-II basin geometry cache: '
            f'<code>{html.escape(str(getattr(args, "resolved_gagesii_cache_dir", "")))}</code>)'
        )
    else:
        map_geometry_source = f"<code>{html.escape(str(args.camelsh_shapefile))}</code>"

    template = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>Observed Q99+ hydrograph gallery explorer</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #1f2933;
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
    header { padding: 22px 24px 14px; border-bottom: 1px solid var(--line); background: #fff; }
    h1 { margin: 0 0 8px; font-size: 22px; line-height: 1.25; overflow-wrap: anywhere; }
    p { line-height: 1.5; }
    h1, h2, h3, h4, p, small, strong, span { min-width: 0; }
    .intro { max-width: 1180px; margin: 0; color: var(--muted); font-size: 14px; overflow-wrap: anywhere; }
    .layout {
      display: grid;
      gap: 16px;
      width: min(100%, 1680px);
      margin: 0 auto;
      padding: 16px 24px 24px;
    }
    .explorer-grid {
      display: grid;
      grid-template-columns: minmax(172px, 0.42fr) minmax(360px, 0.86fr) minmax(430px, 1.12fr);
      gap: 14px;
      align-items: start;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      min-width: 0;
    }
    .explorer-panel { padding: 14px; }
    .tier-rail {
      display: grid;
      gap: 12px;
      align-content: start;
      position: sticky;
      top: 14px;
      min-width: 0;
    }
    .map-column { display: grid; gap: 10px; align-content: start; min-width: 0; }
    .list-column {
      display: flex;
      flex-direction: column;
      min-height: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfd;
      overflow: hidden;
    }
    .detail-panel {
      min-height: min(72vh, 740px);
      max-height: calc(100vh - 112px);
      min-width: 0;
      overflow: auto;
      position: sticky;
      top: 14px;
      overscroll-behavior: contain;
    }
    .section-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
    }
    .section-head h2 { margin: 0; font-size: 16px; line-height: 1.25; overflow-wrap: anywhere; }
    .section-head p { margin: 3px 0 0; color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }
    .tier-controls { display: grid; gap: 7px; overflow: visible; }
    .tier-button, .all-button, .basin-row, .viewer-button {
      appearance: none;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--ink);
      border-radius: 7px;
      cursor: pointer;
      font: inherit;
      text-align: left;
      text-decoration: none;
    }
    .tier-button { display: flex; gap: 6px; align-items: center; padding: 7px 8px; min-height: 42px; width: 100%; }
    .all-button { padding: 7px 8px; min-height: 42px; width: 100%; }
    .tier-button strong, .all-button strong { font-size: 13px; line-height: 1.1; }
    .tier-button small, .all-button small {
      display: block;
      color: var(--muted);
      margin-top: 1px;
      font-size: 10px;
      line-height: 1.15;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .tier-button.is-active, .all-button.is-active { border-color: var(--active); box-shadow: 0 0 0 2px rgba(29, 78, 216, 0.14); }
    .tier-button:hover, .all-button:hover, .basin-row:hover, .viewer-button:hover, .lightbox-close:hover, .lightbox-nav-button:hover { background: var(--soft); }
    .tier-button:focus-visible, .all-button:focus-visible, .basin-row:focus-visible,
    .plot-button:focus-visible, .viewer-button:focus-visible, .lightbox-close:focus-visible, .lightbox-nav-button:focus-visible {
      outline: 2px solid var(--active);
      outline-offset: 2px;
    }
    .tier-dot { width: 11px; height: 11px; border-radius: 999px; border: 1px solid rgba(0, 0, 0, 0.18); flex: 0 0 auto; }
    .map-frame {
      display: flex;
      justify-content: center;
      align-items: center;
      border: 1px solid var(--line);
      background: #eef4f7;
      border-radius: 8px;
      overflow: hidden;
      min-height: 320px;
    }
    .drbc-map { width: auto; height: min(46vh, 520px); max-width: 100%; display: block; }
    .map-bg { fill: #edf5f7; }
    .drbc-boundary-fill { fill: #f8fbf9; stroke: none; }
    .drbc-boundary-line { fill: none; stroke: #334155; stroke-width: 2.2; pointer-events: none; }
    .basin-shape {
      fill: var(--tier-color);
      fill-opacity: 0.82;
      fill-rule: evenodd;
      stroke: #243244;
      stroke-opacity: 0.62;
      stroke-width: 1.45;
      vector-effect: non-scaling-stroke;
      paint-order: stroke fill;
      cursor: pointer;
      transition: fill 130ms ease, fill-opacity 130ms ease, opacity 130ms ease, stroke 130ms ease, stroke-width 130ms ease;
    }
    .basin-shape:focus { outline: none; }
    .basin-shape:hover, .basin-shape:focus-visible {
      fill: #2563eb;
      fill-opacity: 0.96;
      stroke: #0f172a;
      stroke-opacity: 1;
      stroke-width: 3.2;
    }
    .basin-shape.is-muted { fill: #d8dee7; fill-opacity: 0.34; stroke: #64748b; stroke-opacity: 0.38; }
    .basin-shape.is-selected {
      fill: #2563eb;
      fill-opacity: 1;
      stroke: #0f172a;
      stroke-opacity: 1;
      stroke-width: 3.6;
    }
    .legend-row { display: grid; gap: 7px; color: var(--muted); font-size: 12px; }
    .legend-item { display: inline-flex; align-items: center; gap: 5px; }
    .detail-top { padding: 14px; border-bottom: 1px solid var(--line); background: #fff; }
    .selection-title { margin: 0; font-size: 16px; }
    .selection-note { margin: 4px 0 0; color: var(--muted); font-size: 12px; overflow-wrap: anywhere; word-break: break-word; }
    .basin-list { flex: 1; max-height: min(32vh, 360px); overflow: auto; padding: 10px; background: #fbfcfd; overscroll-behavior: contain; }
    .basin-list-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 180px), 1fr)); gap: 7px; }
    .basin-row {
      display: grid;
      grid-template-columns: 11px minmax(0, 1fr);
      gap: 7px;
      align-items: start;
      padding: 7px;
      min-height: 50px;
      width: 100%;
      min-width: 0;
      overflow: hidden;
    }
    .basin-row.is-selected { border-color: #111827; background: #f3f4f6; }
    .basin-row strong { display: block; font-size: 12px; line-height: 1.25; overflow-wrap: anywhere; word-break: break-word; }
    .basin-row small { color: var(--muted); display: block; font-size: 11px; margin-top: 2px; line-height: 1.25; overflow-wrap: anywhere; word-break: break-word; }
    .basin-detail { padding: 14px; }
    .basin-title-row { display: flex; flex-wrap: wrap; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 10px; min-width: 0; }
    .basin-title-row h2 { margin: 0; font-size: 18px; overflow-wrap: anywhere; word-break: break-word; }
    .basin-legend-meta { display: grid; gap: 3px; margin-top: 6px; color: var(--muted); font-size: 12px; line-height: 1.35; overflow-wrap: anywhere; word-break: break-word; }
    .badge { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--line); border-radius: 999px; padding: 4px 8px; background: #fff; font-size: 12px; }
    .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 122px), 1fr)); gap: 8px; margin: 10px 0 14px; }
    .metric-card { border: 1px solid var(--line); border-radius: 7px; padding: 8px; background: #fff; min-height: 58px; min-width: 0; }
    .metric-card span { display: block; color: var(--muted); font-size: 11px; }
    .metric-card strong { display: block; margin-top: 4px; font-size: 14px; overflow-wrap: anywhere; word-break: break-word; }
    .stack {
      height: 11px;
      display: grid;
      grid-template-columns: var(--near, 0fr) var(--shoulder, 0fr) var(--far, 0fr) var(--extreme, 0fr);
      border-radius: 999px;
      overflow: hidden;
      border: 1px solid var(--line);
      background: #f1f5f9;
      margin: 8px 0 12px;
    }
    .stack div:nth-child(1) { background: #2f855a; }
    .stack div:nth-child(2) { background: #b7791f; }
    .stack div:nth-child(3) { background: #c05621; }
    .stack div:nth-child(4) { background: #c53030; }
    .event-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin: 14px 0 8px; min-width: 0; }
    .event-toolbar h3 { margin: 0; font-size: 14px; overflow-wrap: anywhere; word-break: break-word; }
    .event-toolbar small { color: var(--muted); overflow-wrap: anywhere; word-break: break-word; }
    .viewer-button { display: inline-flex; align-items: center; min-height: 34px; padding: 7px 10px; font-size: 13px; }
    .event-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 260px), 1fr)); gap: 10px; }
    .event-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      overflow: hidden;
      min-width: 0;
      content-visibility: auto;
      contain-intrinsic-size: 300px;
    }
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
    .plot-button img { display: block; width: 100%; height: 100%; object-fit: contain; background: #f8fafc; }
    .event-copy { padding: 8px; }
    .event-copy h4 { margin: 0 0 5px; font-size: 12px; line-height: 1.25; overflow-wrap: anywhere; word-break: break-word; }
    .event-copy p { margin: 3px 0; color: var(--muted); font-size: 11px; line-height: 1.35; overflow-wrap: anywhere; word-break: break-word; }
    .sources { padding: 0 24px 24px; color: var(--muted); font-size: 11px; width: min(100%, 1680px); margin: 0 auto; }
    .sources code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    body.lightbox-open { overflow: hidden; }
    .lightbox[hidden] { display: none; }
    .lightbox { position: fixed; inset: 0; z-index: 50; display: grid; place-items: center; padding: 24px; }
    .lightbox-backdrop { position: absolute; inset: 0; background: rgba(15, 23, 42, 0.78); }
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
    .lightbox-close { position: absolute; top: 12px; right: 12px; z-index: 5; border: 1px solid var(--line); background: #fff; border-radius: 6px; padding: 6px 9px; cursor: pointer; font-size: 12px; }
    .lightbox-image-frame { display: flex; justify-content: center; align-items: center; background: #f3f6f8; border: 1px solid var(--line); border-radius: 7px; min-height: min(72vh, 780px); padding: 8px; }
    .lightbox-image { display: block; max-width: 100%; max-height: min(82vh, 900px); object-fit: contain; }
    .lightbox-caption { margin: 8px 86px 8px 0; color: var(--muted); font-size: 12px; line-height: 1.4; overflow-wrap: anywhere; word-break: break-word; }
    .lightbox-nav { display: grid; grid-template-columns: 44px minmax(0, 1fr) 44px; align-items: center; gap: 10px; }
    .lightbox-position { color: var(--muted); font-size: 12px; text-align: center; overflow-wrap: anywhere; }
    .lightbox-nav-button { border: 1px solid var(--line); background: #fff; border-radius: 6px; cursor: pointer; height: 38px; font-size: 17px; }
    .lightbox-step-button { width: 44px; }
    @media (max-width: 1180px) {
      .explorer-grid { grid-template-columns: 1fr; }
      .tier-rail, .detail-panel { position: static; top: auto; }
      .tier-controls { display: flex; overflow-x: auto; padding-bottom: 2px; }
      .tier-button { min-width: 132px; flex: 1 0 132px; width: auto; }
      .all-button { min-width: 174px; flex: 1.1 0 174px; width: auto; }
      .legend-row { display: flex; flex-wrap: wrap; gap: 10px; }
      .drbc-map { height: auto; }
      .detail-panel { min-height: 0; max-height: none; overflow: visible; }
      .basin-list { max-height: min(46vh, 520px); }
    }
    @media (max-width: 720px) {
      header { padding-inline: 16px; }
      .layout { padding: 12px 16px 20px; }
      .section-head { display: block; }
      .lightbox { padding: 10px; }
      .lightbox-panel { width: calc(100vw - 20px); max-height: calc(100vh - 20px); }
      .lightbox-image-frame { min-height: min(62vh, 620px); }
    }
  </style>
</head>
<body>
  <header>
    <h1>Observed Q99+ hydrograph gallery explorer</h1>
    <p class="intro">
      DRBC __SUMMARY_BASINS__개 basin의 observed Q99+ hydrograph gallery를 median-distance basin tier와 map으로 탐색합니다.
      각 basin을 누르면 해당 basin의 Q99+ event hydrograph를 바로 볼 수 있고, full gallery도 열 수 있습니다.
    </p>
  </header>
  <main class="layout">
    <section class="panel explorer-panel" aria-label="DRBC basin selector">
      <div class="section-head">
        <div>
          <h2>DRBC basin map</h2>
          <p>Median tier와 basin shape를 왼쪽에서 고르면 같은 화면의 detail panel이 바로 바뀝니다.</p>
        </div>
      </div>
      <div class="explorer-grid">
        <aside class="tier-rail" aria-label="Median tier selector">
          <div class="tier-controls">
            <button class="all-button is-active" type="button" data-tier-key="all">
              <strong>All median tiers</strong>
              <small>__SUMMARY_BASINS__ basins · __SUMMARY_EVENTS__ hydrographs</small>
            </button>
            __TIER_CARDS__
          </div>
          <div class="legend-row">
            __LEGEND__
          </div>
        </aside>
        <div class="map-column">
          <div class="map-frame">
            __SVG__
          </div>
          <div class="list-column">
            <div class="detail-top">
              <h2 id="selectionTitle" class="selection-title">All median tiers</h2>
              <p id="selectionNote" class="selection-note"></p>
            </div>
            <div class="basin-list">
              <div id="basinList" class="basin-list-grid"></div>
            </div>
          </div>
        </div>
        <section class="panel detail-panel" aria-label="선택된 유역의 Q99 hydrographs">
          <div id="basinDetail" class="basin-detail"></div>
        </section>
      </div>
    </section>
  </main>

  <section class="sources">
    <p>
      Sources:
      <code>__HYDROGRAPH_ROOT__</code>,
      <code>__EVENT_RESPONSE_TABLE__</code>,
      <code>__TIER_PROFILE__</code>,
      <code>__DRBC_BOUNDARY__</code>,
      __MAP_GEOMETRY_SOURCE__.
    </p>
  </section>

  <div id="lightbox" class="lightbox" hidden>
    <div class="lightbox-backdrop" data-close-lightbox></div>
    <div class="lightbox-panel" role="dialog" aria-modal="true" aria-label="Hydrograph preview">
      <button class="lightbox-close" type="button" data-close-lightbox>닫기</button>
      <div class="lightbox-image-frame">
        <img id="lightboxImage" class="lightbox-image" alt="">
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
    const TIER_CONFIG = __TIERS_JSON__;
    const BASINS = __BASINS_JSON__;
    const SUMMARY = __SUMMARY_JSON__;
    const SOURCES = __SOURCE_JSON__;
    const basinById = new Map(BASINS.map((basin) => [basin.gaugeId, basin]));
    const tierByKey = new Map(TIER_CONFIG.map((tier) => [tier.key, tier]));
    let activeTier = "all";
    let selectedGaugeId = null;
    let currentEvents = [];
    let currentEventIndex = 0;

    const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]
    ));

    const visibleBasins = () => BASINS
      .filter((basin) => activeTier === "all" || basin.tierKey === activeTier)
      .sort((a, b) => {
        const tierA = TIER_CONFIG.findIndex((tier) => tier.key === a.tierKey);
        const tierB = TIER_CONFIG.findIndex((tier) => tier.key === b.tierKey);
        if (tierA !== tierB) return tierB - tierA;
        return Number(b.farOrExtremeRecords) - Number(a.farOrExtremeRecords)
          || Number(b.eventCount) - Number(a.eventCount)
          || a.gaugeId.localeCompare(b.gaugeId);
      });

    function replaceHash(hash) {
      if (window.location.hash === hash) return;
      history.replaceState(null, "", `${window.location.pathname}${window.location.search}${hash}`);
    }

    function isDesktopExplorer() {
      return window.matchMedia("(min-width: 1181px)").matches;
    }

    function setActiveTier(tierKey, updateHash = true) {
      activeTier = tierKey;
      document.querySelectorAll(".tier-button, .all-button").forEach((button) => {
        button.classList.toggle("is-active", button.dataset.tierKey === tierKey);
      });
      const tier = tierByKey.get(tierKey);
      const title = tierKey === "all" ? "All median tiers" : `${tier.label} · ${tier.shortLabel}`;
      const note = tierKey === "all"
        ? `${SUMMARY.basins} basins · ${SUMMARY.events} Q99+ hydrographs. 모든 median-distance tier를 색으로 함께 표시합니다.`
        : `${SUMMARY.byTier[tierKey].basins} basins · ${SUMMARY.byTier[tierKey].events} Q99+ hydrographs. ${tier.description}.`;
      document.getElementById("selectionTitle").textContent = title;
      document.getElementById("selectionNote").textContent = note;
      updateMapStyles();
      renderBasinList();
      const visible = visibleBasins();
      if (!selectedGaugeId || !visible.some((basin) => basin.gaugeId === selectedGaugeId)) {
        selectedGaugeId = visible.length ? visible[0].gaugeId : null;
      }
      renderBasinDetail();
      updateMapStyles();
      if (updateHash) replaceHash(tierKey === "all" ? "#tier-all" : `#tier-${tierKey}`);
    }

    function updateMapStyles() {
      document.querySelectorAll(".basin-shape").forEach((shape) => {
        const basin = basinById.get(shape.dataset.gaugeId);
        const isVisible = activeTier === "all" || basin.tierKey === activeTier;
        shape.classList.toggle("is-muted", !isVisible);
        shape.classList.toggle("is-selected", shape.dataset.gaugeId === selectedGaugeId);
        shape.style.setProperty("--tier-color", basin.tierColor);
      });
    }

    function renderBasinList() {
      const container = document.getElementById("basinList");
      const basins = visibleBasins();
      container.innerHTML = basins.map((basin) => `
        <button class="basin-row ${basin.gaugeId === selectedGaugeId ? "is-selected" : ""}" type="button" data-gauge-id="${escapeHtml(basin.gaugeId)}">
          <span class="tier-dot" style="background:${escapeHtml(basin.tierColor)}"></span>
          <span>
            <strong>${escapeHtml(basin.gaugeId)} · ${escapeHtml(basin.gaugeName)}</strong>
            <small>${escapeHtml(basin.tierLabel)} · ${basin.eventCount} Q99+ hydrographs</small>
          </span>
        </button>
      `).join("");
      container.querySelectorAll(".basin-row").forEach((button) => {
        button.addEventListener("click", () => selectBasin(button.dataset.gaugeId));
      });
    }

    function selectBasin(gaugeId, updateHash = true, scrollDetail = true) {
      const basin = basinById.get(gaugeId);
      if (!basin) return;
      selectedGaugeId = gaugeId;
      if (activeTier !== "all" && activeTier !== basin.tierKey) {
        activeTier = basin.tierKey;
        setActiveTier(activeTier, false);
        selectedGaugeId = gaugeId;
      }
      renderBasinList();
      renderBasinDetail();
      updateMapStyles();
      if (updateHash) replaceHash(`#basin-${gaugeId}`);
      if (scrollDetail && !isDesktopExplorer()) {
        document.getElementById("basinDetail").scrollIntoView({ block: "nearest" });
      }
    }

    function stackStyle(counts) {
      const near = Math.max(0, counts.near || 0);
      const shoulder = Math.max(0, counts.shoulder || 0);
      const far = Math.max(0, counts.far || 0);
      const extreme = Math.max(0, counts.extreme || 0);
      return `--near:${near}fr;--shoulder:${shoulder}fr;--far:${far}fr;--extreme:${extreme}fr;`;
    }

    function renderBasinDetail() {
      const container = document.getElementById("basinDetail");
      const basin = selectedGaugeId ? basinById.get(selectedGaugeId) : null;
      if (!basin) {
        container.innerHTML = "<p class='selection-note'>선택된 basin이 없습니다.</p>";
        return;
      }
      currentEvents = basin.events;
      container.innerHTML = `
        <div class="basin-title-row">
          <div>
            <h2>${escapeHtml(basin.gaugeId)} · ${escapeHtml(basin.gaugeName)}</h2>
            <p class="selection-note">${escapeHtml(basin.state)} · area ${basin.area} km² · Q99 ${basin.obsQ99} · Q99 events ${basin.q99EventFrequency}/yr</p>
            <div class="basin-legend-meta">
              ${basin.legendMetadataLines.map((line) => `<span>${escapeHtml(line)}</span>`).join("")}
            </div>
          </div>
          <span class="badge"><span class="tier-dot" style="background:${escapeHtml(basin.tierColor)}"></span>${escapeHtml(basin.tierLabel)}</span>
        </div>
        <div class="metric-grid">
          <div class="metric-card"><span>Q99+ hydrographs</span><strong>${basin.eventCount}</strong></div>
          <div class="metric-card"><span>max observed peak</span><strong>${basin.maxObservedPeak} m³/s</strong></div>
          <div class="metric-card"><span>mean distance</span><strong>${basin.meanDistance} IQR</strong></div>
          <div class="metric-card"><span>far/extreme records</span><strong>${basin.farOrExtremeRecords} / 18</strong></div>
        </div>
        <div class="stack" style="${stackStyle(basin.distanceCounts)}" title="near / shoulder / far / extreme record counts">
          <div></div><div></div><div></div><div></div>
        </div>
        <div class="event-toolbar">
          <div>
            <h3>Observed Q99+ hydrographs</h3>
            <small>${basin.eventCount} event windows from event_start - 72h to event_end + 72h</small>
          </div>
          <a class="viewer-button" href="${escapeHtml(basin.galleryPath)}">Full gallery 열기</a>
        </div>
        <div class="event-grid">
          ${basin.events.map((event, index) => renderEventCard(event, index)).join("")}
        </div>
      `;
      container.querySelectorAll(".plot-button").forEach((button) => {
        button.addEventListener("click", () => openLightbox(Number(button.dataset.eventIndex)));
      });
    }

    function renderEventCard(event, index) {
      return `
        <article class="event-card">
          <button class="plot-button" type="button" data-event-index="${index}" aria-label="hydrograph 확대: ${escapeHtml(event.eventId)}">
            <img src="${escapeHtml(event.plotPath)}" loading="lazy" width="640" height="333" alt="${escapeHtml(eventCaption(event))}">
          </button>
          <div class="event-copy">
            <h4>${escapeHtml(event.eventId)}</h4>
            <p>peak ${escapeHtml(event.eventPeak)}</p>
            <p>peak discharge ${escapeHtml(event.peakDischarge)} m³/s</p>
          </div>
        </article>
      `;
    }

    function eventCaption(event) {
      return `${event.eventId} · peak ${event.eventPeak} · discharge ${event.peakDischarge} m³/s`;
    }

    function renderLightbox(index) {
      if (!currentEvents.length) return;
      currentEventIndex = (index + currentEvents.length) % currentEvents.length;
      const event = currentEvents[currentEventIndex];
      const image = document.getElementById("lightboxImage");
      const caption = document.getElementById("lightboxCaption");
      const position = document.getElementById("lightboxPosition");
      image.src = event.plotPath;
      image.alt = eventCaption(event);
      caption.textContent = eventCaption(event);
      position.textContent = `${currentEventIndex + 1} / ${currentEvents.length}`;
    }

    function openLightbox(index) {
      const event = currentEvents[index];
      if (!event) return;
      const lightbox = document.getElementById("lightbox");
      lightbox.hidden = false;
      document.body.classList.add("lightbox-open");
      renderLightbox(index);
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
      document.getElementById("lightboxImage").src = "";
      document.getElementById("lightboxCaption").textContent = "";
      document.getElementById("lightboxPosition").textContent = "";
      document.body.classList.remove("lightbox-open");
    }

    function applyHashState() {
      const hash = window.location.hash.replace(/^#/, "");
      if (hash.startsWith("basin-")) {
        const gaugeId = hash.replace(/^basin-/, "");
        if (basinById.has(gaugeId)) {
          selectBasin(gaugeId, false, false);
          return true;
        }
      }
      if (hash.startsWith("tier-")) {
        const tierKey = hash.replace(/^tier-/, "");
        if (tierKey === "all" || tierByKey.has(tierKey)) {
          setActiveTier(tierKey, false);
          return true;
        }
      }
      return false;
    }

    document.querySelectorAll(".tier-button, .all-button").forEach((button) => {
      button.addEventListener("click", () => setActiveTier(button.dataset.tierKey));
    });
    document.querySelectorAll(".basin-shape").forEach((shape) => {
      shape.addEventListener("click", () => selectBasin(shape.dataset.gaugeId));
      shape.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          selectBasin(shape.dataset.gaugeId);
        }
      });
    });
    document.querySelectorAll("[data-close-lightbox]").forEach((node) => {
      node.addEventListener("click", closeLightbox);
    });
    document.getElementById("lightboxPrev").addEventListener("click", () => moveLightbox(-1));
    document.getElementById("lightboxNext").addEventListener("click", () => moveLightbox(1));
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
      }
    });

    setActiveTier("all", false);
    applyHashState();
    window.addEventListener("hashchange", applyHashState);
  </script>
</body>
</html>
"""
    replacements = {
        "__SUMMARY_BASINS__": str(summary["basins"]),
        "__SUMMARY_EVENTS__": str(summary["events"]),
        "__TIER_CARDS__": tier_cards,
        "__SVG__": svg,
        "__LEGEND__": "".join(
            f'<span class="legend-item"><span class="tier-dot" style="background:{html.escape(tier["color"])}"></span>{html.escape(tier["label"])}</span>'
            for tier in TIER_CONFIG
        ),
        "__HYDROGRAPH_ROOT__": html.escape(str(args.hydrograph_root)),
        "__EVENT_RESPONSE_TABLE__": html.escape(str(args.event_response_table)),
        "__TIER_PROFILE__": html.escape(str(args.tier_profile)),
        "__DRBC_BOUNDARY__": html.escape(str(args.drbc_boundary)),
        "__MAP_GEOMETRY_SOURCE__": map_geometry_source,
        "__TIERS_JSON__": tiers_json,
        "__BASINS_JSON__": basins_json,
        "__SUMMARY_JSON__": summary_json,
        "__SOURCE_JSON__": source_json,
    }
    for token, value in replacements.items():
        template = template.replace(token, value)
    return template


def main() -> None:
    args = parse_args()
    args.output_html.parent.mkdir(parents=True, exist_ok=True)
    expected_events = read_expected_events(args.event_response_table)
    tiers = read_tiers(args.tier_profile)
    selected = read_selected(args.drbc_selected)
    metadata = read_metadata(args.metadata_manifest)
    basin_records = build_basin_records(args, expected_events, tiers, selected, metadata)
    boundary_geometry, boundary_rings = load_boundary_geometry(args.drbc_boundary)
    basin_rings = load_map_basin_rings(
        args,
        set(basin_records),
        clip_geometry=boundary_geometry,
    )
    svg = build_svg(
        basin_rings=basin_rings,
        boundary_rings=boundary_rings,
        basin_rows=basin_records,
        width=args.svg_width,
        height=args.svg_height,
        simplify_px=args.simplify_px,
    )
    summary = build_summary(basin_records)
    page = render_html(svg=svg, basin_records=basin_records, summary=summary, args=args)
    args.output_html.write_text(page, encoding="utf-8")
    print(f"Wrote {args.output_html}")
    print(f"Basins: {summary['basins']} | hydrographs: {summary['events']}")


if __name__ == "__main__":
    main()
