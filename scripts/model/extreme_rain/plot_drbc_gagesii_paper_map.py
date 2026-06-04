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
"""Create a publication-style DRBC basin map from cached USGS GAGES-II geometry."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import geopandas as gpd
import matplotlib.lines as mlines
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd
from shapely.geometry import shape
from shapely.ops import unary_union

TARGET_CRS = "EPSG:5070"
DEFAULT_CACHE_DIR = Path("output/model_analysis/q99_analysis/performance/map_geometry/gagesii_basins")
DEFAULT_TIER_PROFILE = Path("output/model_analysis/primary/metrics/tables/expanded_drbc_tier_profile.csv")
DEFAULT_DRBC_BOUNDARY = Path("basins/drbc_boundary/drb_bnd_polygon.shp")
DEFAULT_STATE_SHAPEFILE = Path("basins/us_boundaries/tl_2024_us_state/tl_2024_us_state.shp")
DEFAULT_OUTPUT_DIR = Path("output/draft/figure/drbc_map")
CONUS_EXCLUDED_STATES = {"AK", "HI", "PR", "GU", "VI", "MP", "AS"}

TIER_STYLE = {
    "near_median_lt_0_5_iqr": {
        "label": "Near median (<0.5 IQR)",
        "color": "#3B8B6A",
        "edge": "#1F4F3F",
        "order": 0,
    },
    "shoulder_0_5_to_1_5_iqr": {
        "label": "Shoulder (0.5-1.5 IQR)",
        "color": "#D6A64A",
        "edge": "#7A551A",
        "order": 1,
    },
    "far_1_5_to_3_iqr": {
        "label": "Far (1.5-3 IQR)",
        "color": "#D96C3F",
        "edge": "#7B2E18",
        "order": 2,
    },
    "extreme_ge_3_iqr": {
        "label": "Extreme (>=3 IQR)",
        "color": "#C83E4D",
        "edge": "#6E1D2A",
        "order": 3,
    },
}
TIER_BY_LABEL = {
    "<0.5 IQR": "near_median_lt_0_5_iqr",
    "0.5-1.5 IQR": "shoulder_0_5_to_1_5_iqr",
    "1.5-3 IQR": "far_1_5_to_3_iqr",
    ">=3 IQR": "extreme_ge_3_iqr",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gagesii-cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--tier-profile", type=Path, default=DEFAULT_TIER_PROFILE)
    parser.add_argument("--drbc-boundary", type=Path, default=DEFAULT_DRBC_BOUNDARY)
    parser.add_argument("--state-shapefile", type=Path, default=DEFAULT_STATE_SHAPEFILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-stem", default="drbc_gagesii_basin_paper_map")
    parser.add_argument("--dpi", type=int, default=450)
    parser.add_argument("--basin-simplify-m", type=float, default=80.0)
    parser.add_argument("--state-simplify-m", type=float, default=800.0)
    parser.add_argument("--formats", nargs="+", default=["png", "pdf", "svg"], choices=["png", "pdf", "svg"])
    return parser.parse_args()


def normalize_gauge_id(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(8) if text.isdigit() and len(text) < 8 else text


def read_tiers(path: Path) -> pd.DataFrame:
    tiers = pd.read_csv(path, dtype={"basin": str})
    tiers["gauge_id"] = tiers["basin"].map(normalize_gauge_id)
    tiers["tier_key"] = tiers["dominant_distance_label"].map(lambda label: TIER_BY_LABEL.get(str(label)))
    missing = tiers[tiers["tier_key"].isna()]
    if not missing.empty:
        labels = sorted(missing["dominant_distance_label"].dropna().astype(str).unique())
        raise ValueError(f"Unknown tier labels in {path}: {labels}")
    return tiers[["gauge_id", "tier_key", "dominant_distance_label", "gauge_name", "state"]]


def read_cached_gagesii_basins(cache_dir: Path, tiers: pd.DataFrame) -> gpd.GeoDataFrame:
    rows: list[dict[str, Any]] = []
    for geojson_path in sorted(cache_dir.glob("*.geojson")):
        payload = json.loads(geojson_path.read_text(encoding="utf-8"))
        features = payload.get("features") or []
        if not features:
            continue
        feature = features[0]
        props = feature.get("properties") or {}
        gauge_id = normalize_gauge_id(props.get("gage_id") or feature.get("id") or geojson_path.stem)
        rows.append({"gauge_id": gauge_id, "geometry": shape(feature["geometry"])})
    if not rows:
        raise FileNotFoundError(f"No cached GAGES-II basin GeoJSON files found in {cache_dir}")
    basins = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326").to_crs(TARGET_CRS)
    basins = basins.merge(tiers, on="gauge_id", how="left")
    missing = basins[basins["tier_key"].isna()]["gauge_id"].tolist()
    if missing:
        raise ValueError(f"Tier profile missing for cached basins: {', '.join(missing[:10])}")
    return basins


def read_drbc(path: Path) -> gpd.GeoDataFrame:
    return gpd.read_file(path).to_crs(TARGET_CRS)


def read_states(path: Path) -> gpd.GeoDataFrame:
    states = gpd.read_file(path)
    states = states[~states["STUSPS"].isin(CONUS_EXCLUDED_STATES)].copy()
    return states.to_crs(TARGET_CRS)


def simplify(gdf: gpd.GeoDataFrame, tolerance: float) -> gpd.GeoDataFrame:
    if tolerance <= 0:
        return gdf
    out = gdf.copy()
    out["geometry"] = out.geometry.simplify(tolerance, preserve_topology=True)
    return out[~out.geometry.is_empty & out.geometry.notna()].copy()


def buffered_bounds(bounds: tuple[float, float, float, float], pad_ratio: float) -> tuple[float, float, float, float]:
    minx, miny, maxx, maxy = bounds
    width = maxx - minx
    height = maxy - miny
    return (
        minx - width * pad_ratio,
        miny - height * pad_ratio,
        maxx + width * pad_ratio,
        maxy + height * pad_ratio,
    )


def add_scale_bar(ax: plt.Axes, *, length_km: int = 50) -> None:
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    length_m = length_km * 1000
    start_x = x0 + 0.085 * (x1 - x0)
    start_y = y0 + 0.055 * (y1 - y0)
    ax.plot([start_x, start_x + length_m], [start_y, start_y], color="#222222", linewidth=1.8, solid_capstyle="butt", zorder=20)
    tick_h = 0.012 * (y1 - y0)
    ax.plot([start_x, start_x], [start_y - tick_h / 2, start_y + tick_h / 2], color="#222222", linewidth=1.2, zorder=20)
    ax.plot([start_x + length_m, start_x + length_m], [start_y - tick_h / 2, start_y + tick_h / 2], color="#222222", linewidth=1.2, zorder=20)
    ax.text(start_x + length_m / 2, start_y + 0.016 * (y1 - y0), f"{length_km} km", ha="center", va="bottom", fontsize=7.8, color="#222222")


def add_north_arrow(ax: plt.Axes) -> None:
    ax.annotate(
        "N",
        xy=(0.935, 0.935),
        xytext=(0.935, 0.86),
        xycoords="axes fraction",
        ha="center",
        va="center",
        fontsize=10,
        fontweight="bold",
        arrowprops={"arrowstyle": "-|>", "linewidth": 1.0, "color": "#222222"},
    )


def draw_tier_basins(ax: plt.Axes, basins: gpd.GeoDataFrame) -> None:
    for tier_key, style in sorted(TIER_STYLE.items(), key=lambda item: item[1]["order"]):
        subset = basins[basins["tier_key"] == tier_key]
        if subset.empty:
            continue
        subset.plot(
            ax=ax,
            facecolor=style["color"],
            edgecolor=style["edge"],
            linewidth=0.28,
            alpha=0.88,
            zorder=6 + style["order"],
        )


def add_legend(fig: plt.Figure, basins: gpd.GeoDataFrame) -> None:
    counts = basins["tier_key"].value_counts().to_dict()
    handles: list[Any] = []
    for tier_key, style in sorted(TIER_STYLE.items(), key=lambda item: item[1]["order"]):
        handles.append(
            mpatches.Patch(
                facecolor=style["color"],
                edgecolor=style["edge"],
                linewidth=0.6,
                alpha=0.88,
                label=f"{style['label']} (n={counts.get(tier_key, 0)})",
            )
        )
    handles.append(mlines.Line2D([], [], color="#111827", linewidth=1.25, label="DRBC boundary"))
    legend = fig.legend(
        handles=handles,
        loc="center left",
        bbox_to_anchor=(0.68, 0.48),
        frameon=True,
        framealpha=0.96,
        facecolor="white",
        edgecolor="#d0d4d9",
        fontsize=8.0,
        title="Basin median-distance tier",
        title_fontsize=8.2,
        handlelength=1.5,
        labelspacing=0.45,
        borderpad=0.7,
    )
    legend.set_zorder(30)


def add_inset(fig: plt.Figure, states: gpd.GeoDataFrame, drbc: gpd.GeoDataFrame) -> None:
    inset = fig.add_axes([0.68, 0.68, 0.245, 0.215])
    states_s = simplify(states, 3500)
    states_s.plot(ax=inset, facecolor="#f6f6f1", edgecolor="#bab8ae", linewidth=0.28, zorder=1)
    drbc.boundary.plot(ax=inset, color="#111827", linewidth=1.0, zorder=4)
    drbc_area = drbc.dissolve().geometry.iloc[0]
    focus_bounds = buffered_bounds(tuple(drbc_area.bounds), 2.4)
    inset.set_xlim(focus_bounds[0], focus_bounds[2])
    inset.set_ylim(focus_bounds[1], focus_bounds[3])
    inset.set_axis_off()
    inset.set_title("Northeastern U.S.", fontsize=7.4, pad=1.5)
    for spine in inset.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(0.5)
        spine.set_edgecolor("#9ca3af")


def plot_map(basins: gpd.GeoDataFrame, drbc: gpd.GeoDataFrame, states: gpd.GeoDataFrame, args: argparse.Namespace) -> list[Path]:
    clipped = basins.copy()
    drbc_union = drbc.dissolve().geometry.iloc[0]
    clipped["geometry"] = clipped.geometry.intersection(drbc_union)
    clipped = clipped[~clipped.geometry.is_empty & clipped.geometry.notna()].copy()
    clipped = simplify(clipped, args.basin_simplify_m)
    drbc_plot = simplify(drbc, 120.0)
    states_plot = simplify(states, args.state_simplify_m)

    fig = plt.figure(figsize=(6.8, 7.2))
    fig.patch.set_facecolor("white")
    ax = fig.add_axes([0.045, 0.035, 0.60, 0.93])
    ax.set_facecolor("#F5F8FA")

    states_focus = gpd.clip(states_plot, drbc_plot.buffer(60_000))
    states_focus.plot(ax=ax, facecolor="#F1F0EA", edgecolor="#C8C7BE", linewidth=0.36, zorder=1)
    drbc_plot.plot(ax=ax, facecolor="#FBFCFB", edgecolor="none", zorder=2)
    draw_tier_basins(ax, clipped)
    drbc_plot.boundary.plot(ax=ax, color="#111827", linewidth=1.15, zorder=15)

    minx, miny, maxx, maxy = buffered_bounds(tuple(drbc_plot.total_bounds), 0.08)
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_aspect("equal")
    ax.set_axis_off()

    add_legend(fig, clipped)
    add_scale_bar(ax, length_km=50)
    add_north_arrow(ax)
    add_inset(fig, states, drbc_plot)
    fig.text(
        0.68,
        0.155,
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
        save_kwargs = {"bbox_inches": "tight", "facecolor": "white"}
        if fmt == "png":
            save_kwargs["dpi"] = args.dpi
        fig.savefig(path, **save_kwargs)
        written.append(path)
    plt.close(fig)
    return written


def write_manifest(args: argparse.Namespace, basins: gpd.GeoDataFrame, written: list[Path]) -> Path:
    counts = basins["tier_key"].value_counts().sort_index().to_dict()
    manifest = {
        "figure": "DRBC GAGES-II basin paper map",
        "outputs": [str(path) for path in written],
        "basin_count": int(len(basins)),
        "tier_counts": {key: int(value) for key, value in counts.items()},
        "projection": TARGET_CRS,
        "geometry_source": "USGS gagesii-basins cached GeoJSON",
        "gagesii_cache_dir": str(args.gagesii_cache_dir),
        "tier_profile": str(args.tier_profile),
        "drbc_boundary": str(args.drbc_boundary),
        "state_shapefile": str(args.state_shapefile),
    }
    path = args.output_dir / f"{args.output_stem}_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main() -> None:
    args = parse_args()
    tiers = read_tiers(args.tier_profile)
    basins = read_cached_gagesii_basins(args.gagesii_cache_dir, tiers)
    drbc = read_drbc(args.drbc_boundary)
    states = read_states(args.state_shapefile)
    written = plot_map(basins, drbc, states, args)
    manifest = write_manifest(args, basins, written)
    print("Wrote:")
    for path in written:
        print(f"  {path}")
    print(f"  {manifest}")
    print(f"Basins: {len(basins)}")


if __name__ == "__main__":
    main()
