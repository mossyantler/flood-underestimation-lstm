#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pandas>=2.2",
#   "pyproj>=3.6",
#   "pyshp>=2.3",
#   "shapely>=2.0",
# ]
# ///
"""Build interactive HTML explorer for 85 expanded DRBC basin performance diagnostics.

Shows: IQR tier map, per-basin static attributes (input forcings + key non-input attrs),
model performance metrics (NSE/KGE/FHV for Model 1/2 per seed), Q99+ simQ event gallery.

Inputs:
  - expanded_drbc_tier_profile.csv (tier + event response summary)
  - primary_epoch_basin_deltas.csv (model metrics per seed)
  - drbc_selected_static_attributes_full.csv (140 static attrs)
  - camelsh_drbc_selected.csv (lat/lon)
  - basin_performance/hydrograph/{gauge_id}/q99_simq_manifest.csv (event plots)

Output:
  basin_performance/gallery_index.html
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import sys as _sys

REPO_ROOT = Path(__file__).resolve().parents[3]
_sys.path.insert(0, str(Path(__file__).parent))
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
    load_basin_rings,
    load_boundary_geometry,
    normalize_gauge_id,
    rel_path,
)

DEFAULT_TIER_PROFILE = REPO_ROOT / "output/model_analysis/expanded/expanded_drbc_test/tables/expanded_drbc_tier_profile.csv"
DEFAULT_DELTAS = REPO_ROOT / "output/model_analysis/expanded/expanded_drbc_test/tables/primary_epoch_basin_deltas.csv"
DEFAULT_STATIC_ATTRS = REPO_ROOT / "output/basin/drbc/analysis/basin_attributes/tables/drbc_selected_static_attributes_full.csv"
DEFAULT_DRBC_SELECTED = REPO_ROOT / "output/basin/drbc/basin_define/camelsh_drbc_selected.csv"
DEFAULT_EVENT_MANIFEST = REPO_ROOT / "output/model_analysis/expanded/extreme_rain/expanded_drbc/event_plots/event_plot_manifest.csv"
DEFAULT_HYDROGRAPH_ROOT = REPO_ROOT / "output/model_analysis/expanded/extreme_rain/expanded_drbc/basin_performance/hydrograph"
DEFAULT_OUTPUT_HTML = REPO_ROOT / "output/model_analysis/expanded/extreme_rain/expanded_drbc/basin_performance/gallery_index.html"
DEFAULT_CAMELSH_SHAPEFILE = REPO_ROOT / "basins/CAMELSH_data/shapefiles/CAMELSH_shapefile.shp"
DEFAULT_DRBC_BOUNDARY = REPO_ROOT / "basins/drbc_boundary/drb_bnd_polygon.shp"

# Static attribute groups for display
# format: (display_label, csv_column, unit_suffix)
INPUT_FORCING_ATTRS: list[tuple[str, str, str]] = [
    ("Area", "drain_sqkm_attr", " km²"),
    ("Aridity", "aridity_index", ""),
    ("Snow fraction", "frac_snow", ""),
    ("Slope", "SLOPE_PCT", " %"),
    ("Soil depth", "ROCKDEPAVE", " m"),
    ("Permeability", "PERMAVE", " μm/s"),
    ("Forest fraction", "FORESTNLCD06", " %"),
    ("Baseflow index", "BFI_AVE", ""),
]
CLIMATE_ATTRS: list[tuple[str, str, str]] = [
    ("P mean", "p_mean", " mm/d"),
    ("PET mean", "pet_mean", " mm/d"),
    ("P seasonality", "p_seasonality", ""),
    ("High prec freq", "high_prec_freq", " d/yr"),
    ("High prec dur", "high_prec_dur", " d"),
    ("Low prec freq", "low_prec_freq", " d/yr"),
    ("Low prec dur", "low_prec_dur", " d"),
]
HYDROLOGY_ATTRS: list[tuple[str, str, str]] = [
    ("Q99 threshold", "obs_q99", " m³/s"),
    ("Q99 event freq", "q99_event_frequency", " /yr"),
    ("RBI", "rbi", ""),
    ("Dunnian pct", "PERDUN", " %"),
    ("Horton pct", "PERHOR", " %"),
    ("Topographic wetness", "TOPWET", ""),
    ("Contact time", "CONTACT", " d"),
    ("Runoff ave", "RUNAVE7100", " mm/yr"),
    ("Stream density", "STREAMS_KM_SQ_KM", " km/km²"),
]
LANDCOVER_ATTRS: list[tuple[str, str, str]] = [
    ("Developed total", "DEVNLCD06", " %"),
    ("Crops", "CROPSNLCD06", " %"),
    ("Pasture", "PASTURENLCD06", " %"),
    ("Forest", "FORESTNLCD06", " %"),
    ("Woody wetland", "WOODYWETNLCD06", " %"),
    ("Emergent wetland", "EMERGWETNLCD06", " %"),
]
SOILS_ATTRS: list[tuple[str, str, str]] = [
    ("AWC", "AWCAVE", " cm/cm"),
    ("Bulk density", "BDAVE", " g/cm³"),
    ("Sand", "SANDAVE", " %"),
    ("Silt", "SILTAVE", " %"),
    ("Clay", "CLAYAVE", " %"),
    ("Permeability", "PERMAVE", " μm/s"),
    ("Soil depth", "ROCKDEPAVE", " m"),
]
GEOLOGY_ATTRS: list[tuple[str, str, str]] = [
    ("Dominant geology", "GEOL_REEDBUSH_DOM", ""),
    ("Dom geology pct", "GEOL_REEDBUSH_DOM_PCT", " %"),
    ("Hunt geology", "GEOL_HUNT_DOM_DESC", ""),
]
HUMAN_USE_ATTRS: list[tuple[str, str, str]] = [
    ("Major dams", "MAJ_NDAMS_2009", ""),
    ("Total dams", "NDAMS_2009", ""),
    ("Dam storage", "STOR_NOR_2009", " ML/km²"),
    ("Canals", "CANALS_PCT", " %"),
    ("Fresh water use", "FRESHW_WITHDRAWAL", " ML/yr/km²"),
    ("NPDES major dens", "NPDES_MAJ_DENS", ""),
    ("Power plants", "POWER_NUM_PTS", ""),
]

ATTR_GROUPS: list[tuple[str, list[tuple[str, str, str]]]] = [
    ("Input forcings (model inputs)", INPUT_FORCING_ATTRS),
    ("Climate", CLIMATE_ATTRS),
    ("Hydrology", HYDROLOGY_ATTRS),
    ("Human use", HUMAN_USE_ATTRS),
    ("Land cover", LANDCOVER_ATTRS),
    ("Soils", SOILS_ATTRS),
    ("Geology", GEOLOGY_ATTRS),
]

PERF_METRICS = ["NSE", "KGE", "FHV"]
SEEDS = [111, 222, 444]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tier-profile", type=Path, default=DEFAULT_TIER_PROFILE)
    p.add_argument("--deltas", type=Path, default=DEFAULT_DELTAS)
    p.add_argument("--static-attrs", type=Path, default=DEFAULT_STATIC_ATTRS)
    p.add_argument("--drbc-selected", type=Path, default=DEFAULT_DRBC_SELECTED)
    p.add_argument("--event-manifest", type=Path, default=DEFAULT_EVENT_MANIFEST)
    p.add_argument("--hydrograph-root", type=Path, default=DEFAULT_HYDROGRAPH_ROOT)
    p.add_argument("--output-html", type=Path, default=DEFAULT_OUTPUT_HTML)
    p.add_argument("--camelsh-shapefile", type=Path, default=DEFAULT_CAMELSH_SHAPEFILE)
    p.add_argument("--drbc-boundary", type=Path, default=DEFAULT_DRBC_BOUNDARY)
    p.add_argument("--allow-missing", action="store_true",
                   help="Build from available manifests even if some basins have no hydrographs.")
    p.add_argument("--svg-width", type=float, default=380)
    p.add_argument("--svg-height", type=float, default=760)
    p.add_argument("--simplify-px", type=float, default=0.0)
    return p.parse_args()


def fmt_area(value: Any) -> str:
    v = finite_or_none(value)
    if v is None:
        return "NA"
    return f"{v:,.0f}" if v >= 100 else f"{v:.1f}"


def fmt_attr(value: Any, unit: str = "", digits: int = 3) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    v = finite_or_none(value)
    if v is None:
        return "NA"
    return f"{v:.{digits}f}{unit}"


def read_tier_profile(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"basin": str})
    df["gauge_id"] = df["basin"].map(normalize_gauge_id)
    df["tier_key"] = df["dominant_distance_label"].map(
        lambda label: TIER_BY_LABEL.get(str(label), TIER_CONFIG[0])["key"]
    )
    return df


def read_deltas(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype={"basin": str})


def read_static_attrs(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"gauge_id": str})
    df["gauge_id"] = df["gauge_id"].map(normalize_gauge_id)
    return df.set_index("gauge_id", drop=False)


def read_drbc_selected(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"gauge_id": str})
    df["gauge_id"] = df["gauge_id"].map(normalize_gauge_id)
    return df.set_index("gauge_id", drop=False)


_HUMAN_USE_COLS = [c for _, c, _ in HUMAN_USE_ATTRS]


def read_human_use_attrs(path: Path) -> pd.DataFrame:
    """Extract per-basin human use attributes from the event manifest (first row per basin)."""
    if not path.exists():
        return pd.DataFrame()
    cols_needed = {"gauge_id"} | set(_HUMAN_USE_COLS)
    df = pd.read_csv(path, dtype={"gauge_id": str}, usecols=lambda c: c in cols_needed)
    df["gauge_id"] = df["gauge_id"].map(normalize_gauge_id)
    # One row per basin (all events share same static basin attrs)
    return df.groupby("gauge_id", sort=False).first().reset_index().set_index("gauge_id", drop=False)


def simq_manifest_paths(root: Path) -> list[Path]:
    return sorted(root.glob("*/q99_simq_manifest.csv"))


def build_metrics_record(deltas: pd.DataFrame, basin: str) -> dict[str, Any]:
    """Returns per-seed + mean model performance for one basin."""
    sub = deltas[deltas["basin"].map(normalize_gauge_id) == basin]
    if sub.empty:
        return {}
    rec: dict[str, Any] = {}
    for metric in PERF_METRICS:
        for model in ["model1", "model2"]:
            col = f"{metric}_{model}"
            if col not in sub.columns:
                continue
            vals = sub[col].dropna().tolist()
            rec[f"{col}_mean"] = f"{sum(vals) / len(vals):.3f}" if vals else "NA"
            for seed_row in sub.itertuples(index=False):
                seed = int(getattr(seed_row, "seed", 0))
                v = getattr(seed_row, col, None)
                if v is not None and not pd.isna(v):
                    rec[f"{col}_seed{seed}"] = f"{v:.3f}"
    return rec


def build_attrs_record(attrs_by_id: pd.DataFrame, basin: str) -> dict[str, Any]:
    """Returns flat dict of attribute label → formatted value."""
    if basin not in attrs_by_id.index:
        return {}
    row = attrs_by_id.loc[basin]
    result: dict[str, Any] = {}
    for _group_label, group_attrs in ATTR_GROUPS:
        for display_label, col, unit in group_attrs:
            v = row.get(col) if hasattr(row, "get") else getattr(row, col, None)
            result[display_label] = fmt_attr(v, unit)
    return result


def build_attr_groups_json(
    attrs_by_id: pd.DataFrame,
    tier_df: pd.DataFrame,
    human_use_by_id: pd.DataFrame,
    basin: str,
) -> list[dict[str, Any]]:
    """Build JSON-serializable attribute group list for one basin."""
    static_row = attrs_by_id.loc[basin] if basin in attrs_by_id.index else None
    tier_row = tier_df.set_index("gauge_id").loc[basin] if basin in tier_df.set_index("gauge_id").index else None
    human_row = human_use_by_id.loc[basin] if not human_use_by_id.empty and basin in human_use_by_id.index else None

    def _get(col: str, row: Any) -> Any:
        if row is None:
            return None
        if hasattr(row, "get"):
            return row.get(col)
        try:
            return getattr(row, col)
        except AttributeError:
            return None

    groups = []
    for group_label, group_attrs in ATTR_GROUPS:
        items = []
        for display_label, col, unit in group_attrs:
            # Priority: tier_row (has obs_q99/q99_event_frequency/rbi) → human_row → static_row
            v = _get(col, tier_row) if tier_row is not None else None
            if v is None or (isinstance(v, float) and pd.isna(v)):
                v = _get(col, human_row)
            if v is None or (isinstance(v, float) and pd.isna(v)):
                v = _get(col, static_row)
            items.append({"label": display_label, "value": fmt_attr(v, unit)})
        groups.append({"groupLabel": group_label, "items": items})
    return groups


def build_basin_records(
    args: argparse.Namespace,
    tier_df: pd.DataFrame,
    deltas: pd.DataFrame,
    attrs_by_id: pd.DataFrame,
    selected_by_id: pd.DataFrame,
    human_use_by_id: pd.DataFrame,
) -> dict[str, dict[str, Any]]:
    manifest_paths = simq_manifest_paths(args.hydrograph_root)
    manifest_by_basin = {
        normalize_gauge_id(p.parent.name): p for p in manifest_paths
    }

    tier_by_id = tier_df.set_index("gauge_id", drop=False)
    all_basins = set(tier_df["gauge_id"].dropna().unique())
    missing = sorted(all_basins - set(manifest_by_basin.keys()))
    if missing and not args.allow_missing:
        preview = ", ".join(missing[:10])
        suffix = f", +{len(missing) - 10} more" if len(missing) > 10 else ""
        print(f"WARNING: Missing hydrograph galleries for {len(missing)} basins: {preview}{suffix}", file=sys.stderr)
        print("Re-run with --allow-missing to build from available data.", file=sys.stderr)
        raise SystemExit(1)

    records: dict[str, dict[str, Any]] = {}

    # Include all basins from tier profile; events will be empty if no manifest yet
    for basin in sorted(all_basins, key=lambda b: -int(tier_by_id.loc[b, "far_or_extreme_records"]) if b in tier_by_id.index else 0):
        if basin not in tier_by_id.index:
            continue
        tier = tier_by_id.loc[basin]
        tier_key = str(tier["tier_key"])
        selected_row = selected_by_id.loc[basin] if basin in selected_by_id.index else {}

        events: list[dict[str, Any]] = []
        max_peak = float("nan")

        manifest_path = manifest_by_basin.get(basin)
        if manifest_path is not None:
            manifest = pd.read_csv(manifest_path, dtype={"gauge_id": str})
            if not manifest.empty:
                manifest["event_peak"] = pd.to_datetime(manifest["event_peak"])
                manifest = manifest.sort_values("event_peak").reset_index(drop=True)
                max_peak_val = manifest["peak_discharge"].map(finite_or_none).dropna().max()
                if max_peak_val is not None:
                    max_peak = float(max_peak_val)
                for _, ev in manifest.iterrows():
                    peak_q = finite_or_none(ev.get("peak_discharge"))
                    events.append({
                        "eventId": str(ev["event_id"]),
                        "eventPeak": pd.Timestamp(ev["event_peak"]).isoformat(),
                        "eventStart": str(ev.get("event_start", "")),
                        "eventEnd": str(ev.get("event_end", "")),
                        "peakDischarge": "NA" if peak_q is None else f"{peak_q:.3f}",
                        "plotPath": rel_path(args.output_html, ev["plot_path"]),
                        "hasModelData": bool(ev.get("has_model_data", False)),
                    })

        attr_groups = build_attr_groups_json(attrs_by_id, tier_df, human_use_by_id, basin)
        metrics = build_metrics_record(deltas, basin)

        counts = {
            "near": int(tier.get("near_median_lt_0_5_iqr", 0)),
            "shoulder": int(tier.get("shoulder_0_5_to_1_5_iqr", 0)),
            "far": int(tier.get("far_1_5_to_3_iqr", 0)),
            "extreme": int(tier.get("extreme_ge_3_iqr", 0)),
        }

        gauge_name = str(tier.get("gauge_name", ""))
        state = str(tier.get("state", ""))
        fallback_legend_row = tier if hasattr(tier, "get") else pd.Series(dtype=object)

        records[basin] = {
            "gaugeId": basin,
            "gaugeName": gauge_name,
            "state": state,
            "tierKey": tier_key,
            "tierLabel": TIER_BY_KEY[tier_key]["label"],
            "tierShortLabel": TIER_BY_KEY[tier_key]["shortLabel"],
            "tierColor": TIER_BY_KEY[tier_key]["color"],
            "eventCount": len(events),
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
            "nseMeanM1": metrics.get("NSE_model1_mean", "NA"),
            "kgeMeanM1": metrics.get("KGE_model1_mean", "NA"),
            "fhvMeanM1": metrics.get("FHV_model1_mean", "NA"),
            "nseMeanM2": metrics.get("NSE_model2_mean", "NA"),
            "kgeMeanM2": metrics.get("KGE_model2_mean", "NA"),
            "fhvMeanM2": metrics.get("FHV_model2_mean", "NA"),
            "maxObservedPeak": "NA" if pd.isna(max_peak) else f"{max_peak:.2f}",
            "legendMetadataLines": basin_legend_metadata_lines(fallback_legend_row),
            "distanceCounts": counts,
            "attrGroups": attr_groups,
            "metrics": metrics,
            "events": events,
        }

    return records


def build_summary(basin_records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_tier: dict[str, dict[str, int]] = {}
    for tier in TIER_CONFIG:
        basins = [r for r in basin_records.values() if r["tierKey"] == tier["key"]]
        by_tier[tier["key"]] = {
            "basins": len(basins),
            "events": sum(r["eventCount"] for r in basins),
        }
    return {
        "basins": len(basin_records),
        "events": sum(r["eventCount"] for r in basin_records.values()),
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

    tier_cards = "\n".join(
        f'<button class="tier-button" type="button" data-tier-key="{html.escape(tier["key"])}">'
        f'<span class="tier-dot" style="background:{html.escape(tier["color"])}"></span>'
        f'<span><strong>{html.escape(tier["label"])}</strong>'
        f'<small>{summary["byTier"][tier["key"]]["basins"]} basins · '
        f'{summary["byTier"][tier["key"]]["events"]} plots</small></span>'
        "</button>"
        for tier in TIER_CONFIG
    )

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>Basin Performance Gallery — Expanded DRBC Q99+</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1f2933; --muted: #5f6b7a; --line: #d7dde5;
      --soft: #f4f6f8; --panel: #ffffff; --active: #1d4ed8;
      --shadow: 0 10px 28px rgba(15,23,42,0.10);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; background: #f8fafc; color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      overflow-x: hidden;
    }}
    header {{ padding: 22px 24px 14px; border-bottom: 1px solid var(--line); background: #fff; }}
    h1 {{ margin: 0 0 6px; font-size: 22px; }}
    .intro {{ max-width: 1180px; color: var(--muted); font-size: 14px; margin: 0; }}
    .layout {{ width: min(100%, 1760px); margin: 0 auto; padding: 16px 24px 24px; }}
    .explorer-grid {{
      display: grid;
      grid-template-columns: minmax(172px, 0.40fr) minmax(340px, 0.80fr) minmax(460px, 1.2fr);
      gap: 14px; align-items: start;
    }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; box-shadow: var(--shadow); min-width: 0; }}
    .explorer-panel {{ padding: 14px; }}
    .tier-rail {{ display: grid; gap: 10px; align-content: start; position: sticky; top: 14px; }}
    .map-column {{ display: grid; gap: 10px; align-content: start; }}
    .list-column {{ display: flex; flex-direction: column; border: 1px solid var(--line); border-radius: 8px; background: #fbfcfd; overflow: hidden; }}
    .detail-panel {{ min-height: min(72vh, 720px); max-height: calc(100vh - 80px); overflow: auto; position: sticky; top: 14px; overscroll-behavior: contain; }}
    .section-head {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 10px; }}
    .section-head h2 {{ margin: 0; font-size: 15px; }}
    .section-head p {{ margin: 3px 0 0; color: var(--muted); font-size: 12px; }}
    .tier-controls {{ display: grid; gap: 6px; }}
    .tier-button, .all-button, .basin-row {{
      appearance: none; border: 1px solid var(--line); background: #fff;
      color: var(--ink); border-radius: 7px; cursor: pointer; font: inherit;
      text-align: left; text-decoration: none;
    }}
    .tier-button {{ display: flex; gap: 6px; align-items: center; padding: 7px 8px; min-height: 40px; width: 100%; }}
    .all-button {{ padding: 7px 8px; min-height: 40px; width: 100%; }}
    .tier-button strong, .all-button strong {{ font-size: 13px; }}
    .tier-button small, .all-button small {{
      display: block; color: var(--muted); margin-top: 1px; font-size: 10px;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }}
    .tier-button.is-active, .all-button.is-active {{ border-color: var(--active); box-shadow: 0 0 0 2px rgba(29,78,216,0.14); }}
    .tier-button:hover, .all-button:hover, .basin-row:hover {{ background: var(--soft); }}
    .tier-dot {{ width: 11px; height: 11px; border-radius: 999px; border: 1px solid rgba(0,0,0,0.18); flex: 0 0 auto; }}
    .map-frame {{
      display: flex; justify-content: center; align-items: center;
      border: 1px solid var(--line); background: #eef4f7; border-radius: 8px; overflow: hidden; min-height: 280px;
    }}
    .drbc-map {{ width: auto; height: min(44vh, 500px); max-width: 100%; display: block; }}
    .map-bg {{ fill: #edf5f7; }}
    .drbc-boundary-fill {{ fill: #f8fbf9; stroke: none; }}
    .drbc-boundary-line {{ fill: none; stroke: #334155; stroke-width: 2.2; pointer-events: none; }}
    .basin-shape {{
      fill: var(--tier-color); fill-opacity: 0.78; fill-rule: evenodd;
      stroke: #ffffff; stroke-width: 1.15; cursor: pointer;
      transition: fill 120ms ease, fill-opacity 120ms ease, stroke 120ms ease;
    }}
    .basin-shape:hover {{ fill-opacity: 0.95; stroke: #111827; stroke-width: 2.2; }}
    .basin-shape.is-muted {{ fill: #d8dee7; fill-opacity: 0.45; stroke: #ffffff; }}
    .basin-shape.is-selected {{ fill-opacity: 1; stroke: #111827; stroke-width: 3; }}
    .legend-row {{ display: grid; gap: 6px; color: var(--muted); font-size: 12px; }}
    .legend-item {{ display: inline-flex; align-items: center; gap: 5px; }}
    .detail-top {{ padding: 14px; border-bottom: 1px solid var(--line); background: #fff; }}
    .selection-title {{ margin: 0; font-size: 15px; }}
    .selection-note {{ margin: 4px 0 0; color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }}
    .basin-list {{ flex: 1; max-height: min(30vh, 340px); overflow: auto; padding: 8px; background: #fbfcfd; overscroll-behavior: contain; }}
    .basin-list-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%,170px),1fr)); gap: 6px; }}
    .basin-row {{
      display: grid; grid-template-columns: 11px minmax(0,1fr);
      gap: 6px; align-items: start; padding: 6px; min-height: 46px;
    }}
    .basin-row.is-active {{ border-color: var(--active); background: #eff6ff; }}
    .basin-row-meta {{ min-width: 0; }}
    .basin-row-id {{ font-size: 12px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .basin-row-name {{ font-size: 10px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .basin-row-counts {{ font-size: 10px; color: var(--muted); white-space: nowrap; }}
    .detail-body {{ padding: 14px; display: grid; gap: 18px; }}
    .detail-section {{ display: grid; gap: 8px; }}
    .detail-section h3 {{ margin: 0 0 6px; font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }}
    .metric-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    .metric-table th, .metric-table td {{ border: 1px solid var(--line); padding: 5px 8px; text-align: left; }}
    .metric-table th {{ background: var(--soft); font-weight: 600; }}
    .metric-table td.val {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .attr-group {{ border: 1px solid var(--line); border-radius: 6px; overflow: hidden; }}
    .attr-group-header {{
      padding: 8px 12px; background: var(--soft); font-size: 12px; font-weight: 600;
      cursor: pointer; user-select: none; display: flex; justify-content: space-between; align-items: center;
    }}
    .attr-group-header .toggle {{ color: var(--muted); font-size: 14px; }}
    .attr-grid {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
      gap: 1px; background: var(--line);
    }}
    .attr-cell {{ background: #fff; padding: 6px 10px; }}
    .attr-label {{ font-size: 10px; color: var(--muted); margin-bottom: 1px; }}
    .attr-value {{ font-size: 12px; font-weight: 500; overflow-wrap: anywhere; }}
    .event-gallery-header {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }}
    .event-gallery-header h3 {{ margin: 0; font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }}
    .event-count {{ font-size: 12px; color: var(--muted); }}
    .event-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 10px; }}
    .event-card {{ border: 1px solid var(--line); border-radius: 6px; overflow: hidden; background: #fff; }}
    .event-card img {{ width: 100%; height: auto; display: block; cursor: zoom-in; }}
    .event-card-body {{ padding: 6px 8px; }}
    .event-card-id {{ font-size: 11px; font-weight: 600; }}
    .event-card-meta {{ font-size: 10px; color: var(--muted); margin-top: 2px; }}
    .no-events {{ color: var(--muted); font-size: 13px; padding: 20px 0; text-align: center; }}
    .placeholder {{ color: var(--muted); font-size: 14px; padding: 40px 20px; text-align: center; }}
    .lightbox[hidden] {{ display: none; }}
    .lightbox {{
      align-items: center; display: flex; inset: 0; justify-content: center;
      padding: 24px; position: fixed; z-index: 20;
    }}
    .lightbox-backdrop {{ background: rgba(24,24,27,0.78); inset: 0; position: absolute; }}
    .lightbox-panel {{
      background: #fff; border-radius: 8px; box-shadow: 0 20px 60px rgba(0,0,0,0.35);
      max-height: calc(100vh - 48px); max-width: min(1200px, calc(100vw - 48px));
      overflow: auto; padding: 14px; position: relative; width: 100%;
    }}
    .lightbox-close {{
      background: #fff; border: 1px solid var(--line); border-radius: 6px;
      color: #3f3f46; cursor: pointer; font-size: 12px; padding: 6px 9px;
      position: absolute; right: 14px; top: 14px; z-index: 1;
    }}
    .lightbox-img {{ width: 100%; height: auto; display: block; }}
    .summary-bar {{ display: flex; gap: 16px; flex-wrap: wrap; font-size: 13px; color: var(--muted); padding: 10px 0 0; }}
    .summary-bar strong {{ color: var(--ink); }}
  </style>
</head>
<body>
<header>
  <h1>Basin Performance Gallery — Expanded DRBC (85 basins) Q99+ Diagnostic</h1>
  <p class="intro">
    IQR-based median-distance tiers (NSE/KGE/FHV × 3 seeds). Select a tier or basin to view
    static attributes (input forcings + key non-input attrs), model performance, and Q99+ simQ event gallery.
  </p>
  <div class="summary-bar">
    <span><strong id="sb-basins">{summary["basins"]}</strong> basins</span>
    <span><strong id="sb-events">{summary["events"]}</strong> Q99+ events with plots</span>
  </div>
</header>
<div class="layout">
<div class="explorer-grid">

  <!-- Col 1: tier filter -->
  <div class="tier-rail">
    <div class="panel explorer-panel">
      <div class="section-head">
        <div><h2>IQR Tier</h2><p>Click to filter basins</p></div>
      </div>
      <div class="tier-controls">
        <button class="all-button is-active" type="button" id="btn-all">
          <strong>All tiers</strong>
          <small>{summary["basins"]} basins · {summary["events"]} plots</small>
        </button>
        {tier_cards}
      </div>
    </div>
  </div>

  <!-- Col 2: map + basin list -->
  <div class="map-column">
    <div class="map-frame">
      {svg}
    </div>
    <div class="panel">
      <div style="padding:10px 14px 6px; border-bottom:1px solid var(--line);">
        <strong style="font-size:13px;">Basins</strong>
        <span id="list-count" style="font-size:12px; color:var(--muted); margin-left:6px;"></span>
      </div>
      <div class="basin-list">
        <div class="basin-list-grid" id="basin-list-grid"></div>
      </div>
    </div>
  </div>

  <!-- Col 3: detail panel -->
  <div class="detail-panel panel" id="detail-panel">
    <div class="placeholder" id="detail-placeholder">
      Select a basin from the map or list to view attributes and event hydrographs.
    </div>
    <div id="detail-content" hidden>
      <div class="detail-top" id="detail-top"></div>
      <div class="detail-body" id="detail-body"></div>
    </div>
  </div>

</div>
</div>

<!-- Lightbox -->
<div class="lightbox" id="lightbox" hidden role="dialog" aria-modal="true" aria-label="Image viewer">
  <div class="lightbox-backdrop" id="lightbox-backdrop"></div>
  <div class="lightbox-panel">
    <button class="lightbox-close" id="lightbox-close" type="button">Close ✕</button>
    <img class="lightbox-img" id="lightbox-img" src="" alt="">
  </div>
</div>

<script>
(function() {{
  const BASINS = {basins_json};
  const TIER_CONFIG = {tiers_json};
  const SUMMARY = {summary_json};
  const tierByKey = new Map(TIER_CONFIG.map(t => [t.key, t]));
  const basinByGaugeId = new Map(BASINS.map(b => [b.gaugeId, b]));

  let activeTierKey = null;
  let selectedGaugeId = null;

  /* ---- Tier filter ---- */
  const btnAll = document.getElementById('btn-all');
  const tierButtons = document.querySelectorAll('.tier-button');

  btnAll.addEventListener('click', () => {{ setTier(null); }});
  tierButtons.forEach(btn => {{
    btn.addEventListener('click', () => setTier(btn.dataset.tierKey));
  }});

  function setTier(key) {{
    activeTierKey = key;
    btnAll.classList.toggle('is-active', key === null);
    tierButtons.forEach(btn => btn.classList.toggle('is-active', btn.dataset.tierKey === key));
    renderBasinList();
    updateMapFilter();
    // Scroll to selected basin if still visible after filter change
    if (selectedGaugeId) {{
      const listEl = document.querySelector('.basin-row[data-gauge-id="' + selectedGaugeId + '"]');
      if (listEl) listEl.scrollIntoView({{ block: 'nearest', behavior: 'smooth' }});
    }}
  }}

  /* ---- Basin list ---- */
  function visibleBasins() {{
    const sorted = BASINS.slice().sort((a, b) => b.farOrExtremeRecords - a.farOrExtremeRecords || b.maxDistance - a.maxDistance);
    return activeTierKey ? sorted.filter(b => b.tierKey === activeTierKey) : sorted;
  }}

  function renderBasinList() {{
    const basins = visibleBasins();
    const grid = document.getElementById('basin-list-grid');
    const countEl = document.getElementById('list-count');
    countEl.textContent = `(${{basins.length}})`;
    grid.innerHTML = basins.map(b => {{
      const tier = tierByKey.get(b.tierKey);
      const isActive = b.gaugeId === selectedGaugeId;
      return `<button class="basin-row${{isActive ? ' is-active' : ''}}" type="button" data-gauge-id="${{b.gaugeId}}">
        <span class="tier-dot" style="background:${{tier?.color || '#aaa'}}"></span>
        <span class="basin-row-meta">
          <span class="basin-row-id">${{b.gaugeId}}</span>
          <span class="basin-row-name">${{b.gaugeName || ''}}</span>
          <span class="basin-row-counts">${{b.eventCount}} plots · dist ${{b.maxDistance}}</span>
        </span>
      </button>`;
    }}).join('');
    grid.querySelectorAll('.basin-row').forEach(btn => {{
      btn.addEventListener('click', () => selectBasin(btn.dataset.gaugeId));
    }});
  }}

  /* ---- Map interaction ---- */
  function updateMapFilter() {{
    document.querySelectorAll('.basin-shape').forEach(el => {{
      const id = el.dataset.gaugeId;
      const basin = basinByGaugeId.get(id);
      if (!activeTierKey || (basin && basin.tierKey === activeTierKey)) {{
        el.classList.remove('is-muted');
      }} else {{
        el.classList.add('is-muted');
      }}
    }});
  }}

  document.querySelectorAll('.basin-shape').forEach(el => {{
    el.addEventListener('click', () => selectBasin(el.dataset.gaugeId));
  }});

  /* ---- Select basin ---- */
  function selectBasin(gaugeId) {{
    selectedGaugeId = gaugeId;
    const basin = basinByGaugeId.get(gaugeId);
    if (!basin) return;

    // If basin not visible under current tier filter, clear filter
    if (activeTierKey && basin.tierKey !== activeTierKey) {{
      activeTierKey = null;
      btnAll.classList.add('is-active');
      tierButtons.forEach(btn => btn.classList.remove('is-active'));
      updateMapFilter();
    }}

    // Re-render list (picks up new selectedGaugeId for is-active state)
    renderBasinList();

    // Scroll selected item into view inside the list container
    const listEl = document.querySelector('.basin-row[data-gauge-id="' + gaugeId + '"]');
    if (listEl) listEl.scrollIntoView({{ block: 'nearest', behavior: 'smooth' }});

    // Update map selected state
    document.querySelectorAll('.basin-shape').forEach(el => {{
      el.classList.toggle('is-selected', el.dataset.gaugeId === gaugeId);
    }});

    renderDetail(basin);
  }}

  /* ---- Detail panel ---- */
  function renderDetail(basin) {{
    document.getElementById('detail-placeholder').hidden = true;
    document.getElementById('detail-content').hidden = false;

    const tier = tierByKey.get(basin.tierKey);
    document.getElementById('detail-top').innerHTML = `
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
        <span class="tier-dot" style="background:${{tier?.color || '#aaa'}};width:14px;height:14px;"></span>
        <h2 class="selection-title">${{basin.gaugeId}} · ${{basin.gaugeName}}</h2>
        <span style="font-size:12px;color:var(--muted);">${{basin.state}} · ${{basin.area}} km² · ${{tier?.label || ''}}</span>
      </div>
      <p class="selection-note">
        Far/extreme records: ${{basin.farOrExtremeRecords}} (${{basin.farOrExtremeShare}}) ·
        Mean dist: ${{basin.meanDistance}} · Max dist: ${{basin.maxDistance}} ·
        Q99: ${{basin.obsQ99}} m³/s · Q99 freq: ${{basin.q99EventFrequency}}/yr · RBI: ${{basin.rbi}}
      </p>`;

    let html = '';

    // Model performance table
    html += `<div class="detail-section">
      <h3>Model Performance (mean across seeds 111/222/444)</h3>
      <table class="metric-table">
        <thead><tr><th>Metric</th><th>Model 1 mean</th><th>Model 2 mean</th></tr></thead>
        <tbody>
          <tr><td>NSE</td><td class="val">${{basin.nseMeanM1}}</td><td class="val">${{basin.nseMeanM2}}</td></tr>
          <tr><td>KGE</td><td class="val">${{basin.kgeMeanM1}}</td><td class="val">${{basin.kgeMeanM2}}</td></tr>
          <tr><td>FHV</td><td class="val">${{basin.fhvMeanM1}}</td><td class="val">${{basin.fhvMeanM2}}</td></tr>
        </tbody>
      </table>
    </div>`;

    // Attribute groups
    if (basin.attrGroups && basin.attrGroups.length > 0) {{
      html += `<div class="detail-section"><h3>Basin Attributes</h3>`;
      basin.attrGroups.forEach((group, gi) => {{
        const isFirst = gi === 0;
        html += `<div class="attr-group">
          <div class="attr-group-header" onclick="this.nextElementSibling.hidden=!this.nextElementSibling.hidden;this.querySelector('.toggle').textContent=this.nextElementSibling.hidden?'▶':'▼'">
            <span>${{group.groupLabel}}</span>
            <span class="toggle">${{isFirst ? '▼' : '▶'}}</span>
          </div>
          <div class="attr-grid"${{isFirst ? '' : ' hidden'}}>
            ${{group.items.map(item => `<div class="attr-cell"><div class="attr-label">${{item.label}}</div><div class="attr-value">${{item.value}}</div></div>`).join('')}}
          </div>
        </div>`;
      }});
      html += '</div>';
    }}

    // Event gallery
    html += `<div class="detail-section">
      <div class="event-gallery-header">
        <h3>Q99+ SimQ Event Gallery</h3>
        <span class="event-count">${{basin.eventCount}} events</span>
      </div>`;
    if (basin.events.length === 0) {{
      html += `<div class="no-events">No hydrograph plots yet. Run inference + plot_q99_simq_gallery.py first.</div>`;
    }} else {{
      html += `<div class="event-grid">` +
        basin.events.map(ev => `
          <div class="event-card">
            <img src="${{ev.plotPath}}" loading="lazy" alt="${{ev.eventId}}"
                 data-lightbox="${{ev.plotPath}}" style="cursor:zoom-in;">
            <div class="event-card-body">
              <div class="event-card-id">${{ev.eventId}}</div>
              <div class="event-card-meta">Peak ${{ev.eventPeak.replace('T',' ').slice(0,16)}} · ${{ev.peakDischarge}} m³/s</div>
            </div>
          </div>`).join('') +
        `</div>`;
    }}
    html += '</div>';

    document.getElementById('detail-body').innerHTML = html;
  }}

  /* ---- Lightbox ---- */
  // Exposed on window so event-card img onclick attrs can reach it
  window.openLightbox = function(src) {{
    const lb = document.getElementById('lightbox');
    document.getElementById('lightbox-img').src = src;
    lb.hidden = false;
    document.body.style.overflow = 'hidden';
  }};
  function closeLightbox() {{
    document.getElementById('lightbox').hidden = true;
    document.getElementById('lightbox-img').src = '';
    document.body.style.overflow = '';
  }}
  document.getElementById('lightbox-close').addEventListener('click', closeLightbox);
  document.getElementById('lightbox-backdrop').addEventListener('click', closeLightbox);
  document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closeLightbox(); }});
  // Event delegation for dynamically rendered event-card images
  document.getElementById('detail-body').addEventListener('click', function(e) {{
    const img = e.target.closest('img[data-lightbox]');
    if (img) window.openLightbox(img.getAttribute('data-lightbox'));
  }});

  /* ---- Init ---- */
  renderBasinList();
}})();
</script>
</body>
</html>"""


def main() -> None:
    args = parse_args()

    tier_df = read_tier_profile(args.tier_profile)
    print(f"Tier profile: {len(tier_df)} basins")

    deltas = read_deltas(args.deltas)
    print(f"Deltas: {len(deltas)} rows, {deltas['basin'].nunique()} basins")

    attrs_by_id = read_static_attrs(args.static_attrs)
    print(f"Static attrs: {len(attrs_by_id)} basins")

    selected_by_id = read_drbc_selected(args.drbc_selected)

    human_use_by_id = read_human_use_attrs(args.event_manifest)
    if not human_use_by_id.empty:
        print(f"Human use attrs: {len(human_use_by_id)} basins (from event manifest)")
    else:
        print(f"WARNING: No human use attrs loaded (event manifest not found: {args.event_manifest})", file=sys.stderr)

    print("Building basin records...", flush=True)
    basin_records = build_basin_records(args, tier_df, deltas, attrs_by_id, selected_by_id, human_use_by_id)
    print(f"Basin records: {len(basin_records)}")

    print("Loading basin rings...", flush=True)
    boundary_geometry: Any = None
    boundary_rings: list[list[tuple[float, float]]] = []
    if args.drbc_boundary.exists():
        boundary_geometry, boundary_rings = load_boundary_geometry(args.drbc_boundary)
    else:
        print(f"WARNING: DRBC boundary not found: {args.drbc_boundary}", file=sys.stderr)

    basin_rings: dict[str, list[list[tuple[float, float]]]] = {}
    if args.camelsh_shapefile.exists() and boundary_geometry is not None:
        basin_rings = load_basin_rings(
            args.camelsh_shapefile,
            set(basin_records.keys()),
            clip_geometry=boundary_geometry,
        )
    elif args.camelsh_shapefile.exists():
        print("WARNING: No boundary geometry; basins will be shown unclipped", file=sys.stderr)

    svg = build_svg(
        basin_rings=basin_rings,
        boundary_rings=boundary_rings,
        basin_rows=basin_records,
        width=args.svg_width,
        height=args.svg_height,
        simplify_px=args.simplify_px,
    )

    summary = build_summary(basin_records)
    html_content = render_html(svg, basin_records, summary, args)

    args.output_html.parent.mkdir(parents=True, exist_ok=True)
    args.output_html.write_text(html_content, encoding="utf-8")
    print(f"Wrote {args.output_html}")
    print(f"Basins: {summary['basins']} | Events: {summary['events']}")
    tier_dist = {t["key"]: summary["byTier"][t["key"]]["basins"] for t in TIER_CONFIG}
    print(f"Tier distribution: {tier_dist}")


if __name__ == "__main__":
    main()
