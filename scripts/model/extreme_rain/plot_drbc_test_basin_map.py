#!/usr/bin/env python3
# /// script
# dependencies = [
#   "geopandas>=1.0",
#   "matplotlib>=3.9",
#   "pandas>=2.2",
#   "pyogrio>=0.10",
#   "pyproj>=3.7",
#   "shapely>=2.0",
# ]
# ///
"""Create a clean publication map explaining the DRBC test basin set."""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import geopandas as gpd
import matplotlib.lines as mlines
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd
from shapely.geometry import shape

TARGET_CRS = "EPSG:5070"
DEFAULT_DRBC_SELECTED = Path("configs/basin_splits/drbc_expanded_observed_test/manifest.csv")
DEFAULT_DRBC_BOUNDARY = Path("basins/drbc_boundary/drb_bnd_polygon.shp")
DEFAULT_STATE_SHAPEFILE = Path("basins/us_boundaries/tl_2024_us_state/tl_2024_us_state.shp")
DEFAULT_CACHE_DIR = Path("output/model_analysis/q99_analysis/performance/map_geometry/gagesii_basins")
DEFAULT_OUTPUT_DIR = Path("output/draft/figure/drbc_map")
DEFAULT_GAGESII_API_URL = "https://api.water.usgs.gov/fabric/pygeoapi/collections/gagesii-basins/items"
CONUS_EXCLUDED_STATES = {"AK", "HI", "PR", "GU", "VI", "MP", "AS"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drbc-selected", type=Path, default=DEFAULT_DRBC_SELECTED)
    parser.add_argument("--drbc-boundary", type=Path, default=DEFAULT_DRBC_BOUNDARY)
    parser.add_argument("--state-shapefile", type=Path, default=DEFAULT_STATE_SHAPEFILE)
    parser.add_argument("--gagesii-cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--gagesii-api-url", default=DEFAULT_GAGESII_API_URL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-stem", default="drbc_test_basin_map")
    parser.add_argument("--dpi", type=int, default=450)
    parser.add_argument("--formats", nargs="+", default=["png", "pdf", "svg"], choices=["png", "pdf", "svg"])
    parser.add_argument("--basin-simplify-m", type=float, default=90.0)
    return parser.parse_args()


def normalize_gauge_id(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(8) if text.isdigit() and len(text) < 8 else text


def fetch_gagesii_feature(gauge_id: str, cache_dir: Path, api_url: str) -> dict[str, Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{gauge_id}.geojson"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    url = f"{api_url}?{urllib.parse.urlencode({'gage_id': gauge_id, 'f': 'json', 'limit': 1})}"
    with urllib.request.urlopen(url, timeout=45) as response:
        payload = json.load(response)
    if not payload.get("features"):
        raise RuntimeError(f"No USGS GAGES-II basin geometry for {gauge_id}")
    cache_path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def read_selected_ids(path: Path) -> list[str]:
    selected = pd.read_csv(path, dtype={"gauge_id": str})
    if "selected_for_expanded_drbc_test" in selected.columns:
        selected = selected[selected["selected_for_expanded_drbc_test"].astype(str).str.lower().isin(["true", "1", "yes"])]
    return sorted(selected["gauge_id"].map(normalize_gauge_id).dropna().unique())


def read_gagesii_basins(gauge_ids: list[str], cache_dir: Path, api_url: str) -> gpd.GeoDataFrame:
    rows: list[dict[str, Any]] = []
    for gauge_id in gauge_ids:
        payload = fetch_gagesii_feature(gauge_id, cache_dir, api_url)
        feature = payload["features"][0]
        rows.append({"gauge_id": gauge_id, "geometry": shape(feature["geometry"])})
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326").to_crs(TARGET_CRS)


def read_drbc(path: Path) -> gpd.GeoDataFrame:
    return gpd.read_file(path).to_crs(TARGET_CRS)


def read_states(path: Path) -> gpd.GeoDataFrame:
    states = gpd.read_file(path)
    states = states[~states["STUSPS"].isin(CONUS_EXCLUDED_STATES)].copy()
    return states.to_crs(TARGET_CRS)


def buffered_bounds(bounds: tuple[float, float, float, float], pad_ratio: float) -> tuple[float, float, float, float]:
    minx, miny, maxx, maxy = bounds
    width = maxx - minx
    height = maxy - miny
    return minx - width * pad_ratio, miny - height * pad_ratio, maxx + width * pad_ratio, maxy + height * pad_ratio


def add_scale_bar(ax: plt.Axes, length_km: int = 50) -> None:
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    length_m = length_km * 1000
    start_x = x0 + 0.08 * (x1 - x0)
    start_y = y0 + 0.055 * (y1 - y0)
    ax.plot([start_x, start_x + length_m], [start_y, start_y], color="#222222", linewidth=1.8, solid_capstyle="butt", zorder=20)
    tick_h = 0.012 * (y1 - y0)
    ax.plot([start_x, start_x], [start_y - tick_h / 2, start_y + tick_h / 2], color="#222222", linewidth=1.2, zorder=20)
    ax.plot([start_x + length_m, start_x + length_m], [start_y - tick_h / 2, start_y + tick_h / 2], color="#222222", linewidth=1.2, zorder=20)
    ax.text(start_x + length_m / 2, start_y + 0.016 * (y1 - y0), f"{length_km} km", ha="center", va="bottom", fontsize=7.8, color="#222222")


def add_north_arrow(ax: plt.Axes) -> None:
    ax.annotate(
        "N",
        xy=(0.92, 0.93),
        xytext=(0.92, 0.86),
        xycoords="axes fraction",
        ha="center",
        va="center",
        fontsize=10,
        fontweight="bold",
        arrowprops={"arrowstyle": "-|>", "linewidth": 1.0, "color": "#222222"},
    )


def add_inset(fig: plt.Figure, states: gpd.GeoDataFrame, drbc: gpd.GeoDataFrame) -> None:
    inset = fig.add_axes([0.69, 0.68, 0.225, 0.205])
    states.plot(ax=inset, facecolor="#f6f6f1", edgecolor="#bab8ae", linewidth=0.24, zorder=1)
    drbc.boundary.plot(ax=inset, color="#111827", linewidth=1.0, zorder=4)
    focus_bounds = buffered_bounds(tuple(drbc.total_bounds), 2.4)
    inset.set_xlim(focus_bounds[0], focus_bounds[2])
    inset.set_ylim(focus_bounds[1], focus_bounds[3])
    inset.set_axis_off()
    inset.set_title("Northeastern U.S.", fontsize=7.4, pad=1.5)


def plot_map(basins: gpd.GeoDataFrame, drbc: gpd.GeoDataFrame, states: gpd.GeoDataFrame, args: argparse.Namespace) -> list[Path]:
    drbc_union = drbc.dissolve().geometry.iloc[0]
    clipped = basins.copy()
    clipped["geometry"] = clipped.geometry.intersection(drbc_union)
    clipped = clipped[~clipped.geometry.is_empty & clipped.geometry.notna()].copy()
    if args.basin_simplify_m > 0:
        clipped["geometry"] = clipped.geometry.simplify(args.basin_simplify_m, preserve_topology=True)

    fig = plt.figure(figsize=(6.6, 7.2))
    ax = fig.add_axes([0.045, 0.035, 0.60, 0.93])
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#F5F8FA")

    states_focus = gpd.clip(states, drbc.buffer(60_000))
    states_focus.plot(ax=ax, facecolor="#F1F0EA", edgecolor="#C8C7BE", linewidth=0.36, zorder=1)
    drbc.plot(ax=ax, facecolor="#FBFCFB", edgecolor="none", zorder=2)
    clipped.plot(ax=ax, facecolor="#4B9A82", edgecolor="#1F4F46", linewidth=0.32, alpha=0.86, zorder=6)
    drbc.boundary.plot(ax=ax, color="#111827", linewidth=1.18, zorder=10)

    minx, miny, maxx, maxy = buffered_bounds(tuple(drbc.total_bounds), 0.08)
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_aspect("equal")
    ax.set_axis_off()
    add_scale_bar(ax)
    add_north_arrow(ax)
    add_inset(fig, states, drbc)

    handles = [
        mpatches.Patch(facecolor="#4B9A82", edgecolor="#1F4F46", alpha=0.86, label=f"DRBC test basins (n={len(clipped)})"),
        mlines.Line2D([], [], color="#111827", linewidth=1.25, label="DRBC boundary"),
    ]
    fig.legend(handles=handles, loc="center left", bbox_to_anchor=(0.68, 0.50), frameon=True, framealpha=0.96, facecolor="white", edgecolor="#d0d4d9", fontsize=8.4, borderpad=0.75)
    fig.text(
        0.68,
        0.18,
        "Geometry: USGS GAGES-II basins\nProjection: EPSG:5070\nBasins clipped to DRBC boundary",
        ha="left",
        va="top",
        fontsize=7.1,
        color="#4b5563",
        linespacing=1.35,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for fmt in args.formats:
        path = args.output_dir / f"{args.output_stem}.{fmt}"
        kwargs: dict[str, Any] = {"bbox_inches": "tight", "facecolor": "white"}
        if fmt == "png":
            kwargs["dpi"] = args.dpi
        fig.savefig(path, **kwargs)
        written.append(path)
    plt.close(fig)
    return written


def write_manifest(args: argparse.Namespace, basin_count: int, written: list[Path]) -> Path:
    manifest = {
        "figure": "Clean DRBC test basin map",
        "outputs": [str(path) for path in written],
        "basin_count": basin_count,
        "projection": TARGET_CRS,
        "geometry_source": "USGS gagesii-basins cached GeoJSON",
        "gagesii_cache_dir": str(args.gagesii_cache_dir),
        "drbc_selected": str(args.drbc_selected),
        "drbc_boundary": str(args.drbc_boundary),
        "state_shapefile": str(args.state_shapefile),
    }
    path = args.output_dir / f"{args.output_stem}_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main() -> None:
    args = parse_args()
    gauge_ids = read_selected_ids(args.drbc_selected)
    basins = read_gagesii_basins(gauge_ids, args.gagesii_cache_dir, args.gagesii_api_url)
    drbc = read_drbc(args.drbc_boundary)
    states = read_states(args.state_shapefile)
    written = plot_map(basins, drbc, states, args)
    manifest = write_manifest(args, len(basins), written)
    print("Wrote:")
    for path in written:
        print(f"  {path}")
    print(f"  {manifest}")
    print(f"Basins: {len(basins)}")


if __name__ == "__main__":
    main()
