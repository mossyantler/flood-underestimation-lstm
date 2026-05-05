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

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import matplotlib.lines as mlines
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd
from shapely.geometry import box


DEFAULT_SPLIT_DIR = Path("configs/pilot/basin_splits/scaling_300")
DEFAULT_BASIN_SHAPEFILE = Path("basins/CAMELSH_data/shapefiles/CAMELSH_shapefile.shp")
DEFAULT_STATE_SHAPEFILE = Path("basins/us_boundaries/tl_2024_us_state/tl_2024_us_state.shp")
DEFAULT_DRBC_SHAPEFILE = Path("basins/drbc_boundary/drb_bnd_polygon.shp")
DEFAULT_OUTPUT_DIR = Path("output/basin/all/screening/subset300_spatial_split")
CONUS_EXCLUDED_STATES = {"AK", "HI", "PR", "GU", "VI", "MP", "AS"}
TARGET_CRS = "EPSG:5070"

SPLIT_STYLE = {
    "train": {
        "label": "Train",
        "color": "#8db7ad",
        "edge": "#5f8d83",
        "alpha": 0.56,
        "zorder": 4,
    },
    "validation": {
        "label": "Validation",
        "color": "#d8b46b",
        "edge": "#a77f35",
        "alpha": 0.66,
        "zorder": 5,
    },
    "test": {
        "label": "DRBC test",
        "color": "#cf8e9c",
        "edge": "#9f5866",
        "alpha": 0.74,
        "zorder": 6,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot the fixed subset300 train/validation and DRBC test basins on a CONUS map."
    )
    parser.add_argument("--split-dir", type=Path, default=DEFAULT_SPLIT_DIR)
    parser.add_argument("--basin-shapefile", type=Path, default=DEFAULT_BASIN_SHAPEFILE)
    parser.add_argument("--state-shapefile", type=Path, default=DEFAULT_STATE_SHAPEFILE)
    parser.add_argument("--drbc-shapefile", type=Path, default=DEFAULT_DRBC_SHAPEFILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument(
        "--state-simplify-m",
        type=float,
        default=3000.0,
        help="Display-only simplification tolerance for state boundaries after projection.",
    )
    parser.add_argument(
        "--basin-simplify-m",
        type=float,
        default=600.0,
        help="Display-only simplification tolerance for CAMELSH basin polygons after projection.",
    )
    parser.add_argument(
        "--drbc-simplify-m",
        type=float,
        default=250.0,
        help="Display-only simplification tolerance for the DRBC boundary after projection.",
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        default=["png", "svg"],
        choices=["png", "svg", "pdf"],
        help="Figure formats to write.",
    )
    return parser.parse_args()


def normalize_gauge_id(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(8)


def read_basin_ids(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Missing split file: {path}")
    return [normalize_gauge_id(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_split_table(split_dir: Path) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for split in ("train", "validation", "test"):
        for gauge_id in read_basin_ids(split_dir / f"{split}.txt"):
            rows.append({"gauge_id": gauge_id, "split": split})
    table = pd.DataFrame(rows)
    duplicated = table[table.duplicated("gauge_id", keep=False)].sort_values("gauge_id")
    if not duplicated.empty:
        duplicate_text = ", ".join(duplicated["gauge_id"].unique()[:10])
        raise ValueError(f"Gauge IDs appear in multiple split files: {duplicate_text}")
    return table


def read_states(path: Path) -> gpd.GeoDataFrame:
    states = gpd.read_file(path)
    states = states[~states["STUSPS"].isin(CONUS_EXCLUDED_STATES)].copy()
    return states.to_crs(TARGET_CRS)


def read_basins(path: Path, split_table: pd.DataFrame) -> gpd.GeoDataFrame:
    basins = gpd.read_file(path)
    basins["gauge_id"] = basins["GAGE_ID"].map(normalize_gauge_id)
    if basins.crs is None:
        basins = basins.set_crs("EPSG:4326")
    else:
        basins = basins.to_crs("EPSG:4326")
    basins = basins[["gauge_id", "geometry"]].merge(split_table, on="gauge_id", how="right")
    missing = basins[basins["geometry"].isna()]["gauge_id"].tolist()
    if missing:
        missing_text = ", ".join(missing[:12])
        raise ValueError(f"{len(missing)} split basins are missing from the CAMELSH shapefile: {missing_text}")
    return gpd.GeoDataFrame(basins, geometry="geometry", crs="EPSG:4326").to_crs(TARGET_CRS)


def read_drbc(path: Path) -> gpd.GeoDataFrame:
    return gpd.read_file(path).to_crs(TARGET_CRS)


def simplify_for_display(gdf: gpd.GeoDataFrame, tolerance: float) -> gpd.GeoDataFrame:
    if tolerance <= 0:
        return gdf
    simplified = gdf.copy()
    simplified["geometry"] = simplified.geometry.simplify(tolerance, preserve_topology=True)
    return simplified[~simplified.geometry.is_empty & simplified.geometry.notna()].copy()


def buffered_bounds(bounds: tuple[float, float, float, float], pad_ratio: float) -> tuple[float, float, float, float]:
    minx, miny, maxx, maxy = bounds
    width = maxx - minx
    height = maxy - miny
    pad_x = width * pad_ratio
    pad_y = height * pad_ratio
    return minx - pad_x, miny - pad_y, maxx + pad_x, maxy + pad_y


def draw_base(ax: plt.Axes, states: gpd.GeoDataFrame, *, linewidth: float = 0.35) -> None:
    states.plot(ax=ax, facecolor="#f7f7f4", edgecolor="#c2c2bd", linewidth=linewidth, zorder=1)
    states.boundary.plot(ax=ax, color="#9d9d98", linewidth=linewidth, zorder=8)


def draw_splits(ax: plt.Axes, basins: gpd.GeoDataFrame, *, inset: bool = False) -> None:
    for split in ("train", "validation", "test"):
        subset = basins[basins["split"] == split]
        if subset.empty:
            continue
        style = SPLIT_STYLE[split]
        subset.plot(
            ax=ax,
            facecolor=style["color"],
            edgecolor=style["edge"] if inset else "none",
            linewidth=0.22 if inset else 0.0,
            alpha=style["alpha"],
            rasterized=True,
            zorder=style["zorder"],
        )


def add_legend(ax: plt.Axes, counts: dict[str, int]) -> None:
    handles: list[Any] = []
    for split in ("train", "validation", "test"):
        style = SPLIT_STYLE[split]
        handles.append(
            mpatches.Patch(
                facecolor=style["color"],
                edgecolor=style["edge"],
                alpha=style["alpha"],
                label=f"{style['label']} ({counts.get(split, 0)})",
            )
        )
    handles.append(mlines.Line2D([], [], color="#5a2d35", linewidth=1.8, label="DRBC boundary"))
    ax.legend(
        handles=handles,
        loc="lower left",
        frameon=True,
        framealpha=0.94,
        facecolor="white",
        edgecolor="#d4d4d0",
        fontsize=9.5,
        handlelength=1.8,
    )


def add_scalebar_note(ax: plt.Axes) -> None:
    ax.text(
        0.99,
        0.015,
        "Projection: NAD83 / Conus Albers (EPSG:5070)",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8.5,
        color="#555555",
    )


def plot_map(states: gpd.GeoDataFrame, basins: gpd.GeoDataFrame, drbc: gpd.GeoDataFrame, output_base: Path, formats: list[str], dpi: int) -> list[Path]:
    fig = plt.figure(figsize=(12.8, 7.4))
    ax = fig.add_axes([0.035, 0.070, 0.70, 0.82])
    inset_ax = fig.add_axes([0.725, 0.205, 0.245, 0.44])

    draw_base(ax, states)
    draw_splits(ax, basins, inset=False)
    states.boundary.plot(ax=ax, color="#8d8d87", linewidth=0.36, zorder=9)
    drbc.boundary.plot(ax=ax, color="#5a2d35", linewidth=1.45, zorder=10)

    minx, miny, maxx, maxy = buffered_bounds(tuple(states.total_bounds), 0.035)
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_axis_off()
    ax.set_title(
        "Fixed Subset300 Basin Splits for Model 1 / Model 2",
        fontsize=13.5,
        pad=12,
        color="#222222",
    )
    counts = basins["split"].value_counts().to_dict()
    add_legend(ax, counts)
    add_scalebar_note(ax)

    drbc_test = basins[basins["split"] == "test"]
    inset_focus = pd.concat([drbc[["geometry"]], drbc_test[["geometry"]]], ignore_index=True)
    inset_bounds = buffered_bounds(gpd.GeoDataFrame(inset_focus, geometry="geometry", crs=TARGET_CRS).total_bounds, 0.18)
    focus_box = box(*inset_bounds)
    gpd.GeoSeries([focus_box], crs=TARGET_CRS).boundary.plot(ax=ax, color="#5a2d35", linewidth=0.75, zorder=11)

    draw_base(inset_ax, states, linewidth=0.28)
    draw_splits(inset_ax, basins, inset=True)
    drbc.boundary.plot(ax=inset_ax, color="#5a2d35", linewidth=1.8, zorder=12)
    states.boundary.plot(ax=inset_ax, color="#8d8d87", linewidth=0.28, zorder=11)
    inset_ax.set_xlim(inset_bounds[0], inset_bounds[2])
    inset_ax.set_ylim(inset_bounds[1], inset_bounds[3])
    inset_ax.set_axis_off()
    inset_ax.set_title("DRBC Holdout Region", fontsize=9.5, pad=5, color="#333333")
    for spine in inset_ax.spines.values():
        spine.set_visible(True)
        spine.set_edgecolor("#5a2d35")
        spine.set_linewidth(0.8)

    output_base.parent.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for fmt in formats:
        path = output_base.with_suffix(f".{fmt}")
        save_kwargs: dict[str, Any] = {"bbox_inches": "tight", "facecolor": "white", "dpi": dpi}
        fig.savefig(path, **save_kwargs)
        written.append(path)
    plt.close(fig)
    return written


def write_outputs(
    basins: gpd.GeoDataFrame,
    split_table: pd.DataFrame,
    output_dir: Path,
    written_figures: list[Path],
    args: argparse.Namespace,
) -> None:
    table_dir = output_dir / "tables"
    metadata_dir = output_dir / "metadata"
    table_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    plain = pd.DataFrame(basins.drop(columns="geometry"))
    plain["split"] = pd.Categorical(plain["split"], categories=["train", "validation", "test"], ordered=True)
    plain = plain.sort_values(["split", "gauge_id"])
    plain.to_csv(table_dir / "subset300_spatial_split_basin_labels.csv", index=False)

    counts = split_table["split"].value_counts().reindex(["train", "validation", "test"]).fillna(0).astype(int)
    manifest = {
        "description": "CONUS map of fixed subset300 train/validation basins and DRBC holdout test basins.",
        "split_dir": str(args.split_dir),
        "basin_shapefile": str(args.basin_shapefile),
        "state_shapefile": str(args.state_shapefile),
        "drbc_shapefile": str(args.drbc_shapefile),
        "target_crs": TARGET_CRS,
        "display_simplification_m": {
            "state": args.state_simplify_m,
            "basin": args.basin_simplify_m,
            "drbc": args.drbc_simplify_m,
        },
        "counts": counts.to_dict(),
        "figure_paths": [str(path) for path in written_figures],
        "basin_label_table": str(table_dir / "subset300_spatial_split_basin_labels.csv"),
        "color_notes": {
            split: {
                "label": style["label"],
                "fill": style["color"],
                "edge": style["edge"],
                "alpha": style["alpha"],
            }
            for split, style in SPLIT_STYLE.items()
        },
    }
    (metadata_dir / "subset300_spatial_split_map_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    split_table = read_split_table(args.split_dir)
    states = simplify_for_display(read_states(args.state_shapefile), args.state_simplify_m)
    basins = simplify_for_display(read_basins(args.basin_shapefile, split_table), args.basin_simplify_m)
    drbc = simplify_for_display(read_drbc(args.drbc_shapefile), args.drbc_simplify_m)

    output_base = args.output_dir / "figures" / "subset300_conus_split_map"
    written_figures = plot_map(states, basins, drbc, output_base, args.formats, args.dpi)
    write_outputs(basins, split_table, args.output_dir, written_figures, args)

    for path in written_figures:
        print(f"Wrote figure: {path}")
    print(f"Wrote table: {args.output_dir / 'tables' / 'subset300_spatial_split_basin_labels.csv'}")
    print(f"Wrote manifest: {args.output_dir / 'metadata' / 'subset300_spatial_split_map_manifest.json'}")


if __name__ == "__main__":
    main()
