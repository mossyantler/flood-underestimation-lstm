#!/usr/bin/env python3
# /// script
# dependencies = [
#   "geopandas>=1.0",
#   "pandas>=2.2",
#   "pyogrio>=0.10",
#   "pyshp>=2.3.1",
#   "shapely>=2.0",
# ]
# ///

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd
import shapefile
from shapely.geometry import shape


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a GeoPackage for the DRBC Delaware basin CAMELSH subset."
    )
    parser.add_argument(
        "--drbc-shapefile",
        type=Path,
        default=Path("basins/drbc_boundary/drb_bnd_polygon.shp"),
        help="Path to the official DRBC basin boundary shapefile.",
    )
    parser.add_argument(
        "--camelsh-boundary-shapefile",
        type=Path,
        default=Path("basins/CAMELSH_data/shapefiles/CAMELSH_shapefile.shp"),
        help="Path to the CAMELSH GAGES-II basin boundary shapefile.",
    )
    parser.add_argument(
        "--selected-csv",
        type=Path,
        default=Path("output/basin/drbc/basin_define/camelsh_drbc_selected.csv"),
        help="CSV of selected Delaware CAMELSH basins.",
    )
    parser.add_argument(
        "--intersect-only-csv",
        type=Path,
        default=Path("output/basin/drbc/basin_define/camelsh_drbc_intersect_only.csv"),
        help="CSV of CAMELSH basins whose polygons intersect DRBC but outlets are outside.",
    )
    parser.add_argument(
        "--output-gpkg",
        type=Path,
        default=Path("output/basin/drbc/basin_define/drbc_camelsh_layers.gpkg"),
        help="Output GeoPackage path.",
    )
    return parser.parse_args()


def load_drbc_boundary(path: Path) -> gpd.GeoDataFrame:
    boundary = gpd.read_file(path)
    return boundary.to_crs("EPSG:4326")


def load_csv(path: Path) -> pd.DataFrame:
    table = pd.read_csv(path, dtype={"gauge_id": str})
    return add_gauge_label_fields(table)


def add_gauge_label_fields(table: pd.DataFrame) -> pd.DataFrame:
    table = table.copy()
    table["gauge_id_len"] = table["gauge_id"].str.len()
    table["gauge_id_format"] = table["gauge_id_len"].map(
        lambda n: f"{int(n)}-digit USGS site number"
    )
    table["gauge_id_note"] = (
        "USGS site numbers can be longer than 8 digits in high station-density areas."
    )
    table["gauge_label"] = table["gauge_id"] + " " + table["gauge_name"]
    return table


def load_camelsh_subset(
    shapefile_path: Path,
    gauge_ids: set[str],
    table: pd.DataFrame,
) -> gpd.GeoDataFrame:
    reader = shapefile.Reader(str(shapefile_path))
    field_names = [field[0] for field in reader.fields[1:]]
    table_by_id = table.set_index("gauge_id")

    rows: list[dict] = []
    geometries = []
    for record, shp in zip(reader.iterRecords(), reader.iterShapes()):
        attrs = dict(zip(field_names, record))
        gauge_id = str(attrs["GAGE_ID"]).strip()
        if gauge_id not in gauge_ids:
            continue
        merged = attrs.copy()
        merged["gauge_id"] = gauge_id
        merged.update(table_by_id.loc[gauge_id].to_dict())
        rows.append(merged)
        geometries.append(shape(shp.__geo_interface__))

    gdf = gpd.GeoDataFrame(rows, geometry=geometries, crs="EPSG:4326")
    return gdf.sort_values("gauge_id").reset_index(drop=True)


def build_outlets(table: pd.DataFrame) -> gpd.GeoDataFrame:
    outlets = gpd.GeoDataFrame(
        table.copy(),
        geometry=gpd.points_from_xy(table["lng_gage"], table["lat_gage"]),
        crs="EPSG:4326",
    )
    return outlets.sort_values("gauge_id").reset_index(drop=True)


def build_display_clip(
    basins: gpd.GeoDataFrame,
    boundary: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    clipped = gpd.clip(basins, boundary)
    clipped = clipped.copy()
    clipped["display_geometry_note"] = (
        "Display-only geometry clipped to DRBC boundary; keep original CAMELSH "
        "polygons for hydrologic analysis."
    )
    return clipped.sort_values("gauge_id").reset_index(drop=True)


def main() -> None:
    args = parse_args()
    args.output_gpkg.parent.mkdir(parents=True, exist_ok=True)
    if args.output_gpkg.exists():
        args.output_gpkg.unlink()

    boundary = load_drbc_boundary(args.drbc_shapefile)
    selected = load_csv(args.selected_csv)
    intersect_only = load_csv(args.intersect_only_csv)

    selected_basins = load_camelsh_subset(
        args.camelsh_boundary_shapefile,
        set(selected["gauge_id"]),
        selected,
    )
    selected_basins_display = build_display_clip(selected_basins, boundary)
    selected_outlets = build_outlets(selected)

    intersect_only_basins = load_camelsh_subset(
        args.camelsh_boundary_shapefile,
        set(intersect_only["gauge_id"]),
        intersect_only,
    )
    intersect_only_basins_display = build_display_clip(intersect_only_basins, boundary)
    intersect_only_outlets = build_outlets(intersect_only)

    boundary.to_file(args.output_gpkg, layer="drbc_boundary", driver="GPKG")
    selected_basins.to_file(args.output_gpkg, layer="camelsh_selected_basins", driver="GPKG")
    selected_basins_display.to_file(
        args.output_gpkg,
        layer="camelsh_selected_basins_display_clipped",
        driver="GPKG",
    )
    selected_outlets.to_file(args.output_gpkg, layer="camelsh_selected_outlets", driver="GPKG")
    intersect_only_basins.to_file(
        args.output_gpkg,
        layer="camelsh_intersect_only_basins",
        driver="GPKG",
    )
    intersect_only_basins_display.to_file(
        args.output_gpkg,
        layer="camelsh_intersect_only_basins_display_clipped",
        driver="GPKG",
    )
    intersect_only_outlets.to_file(
        args.output_gpkg,
        layer="camelsh_intersect_only_outlets",
        driver="GPKG",
    )

    print(f"Wrote GeoPackage: {args.output_gpkg}")
    print(
        "Layers: drbc_boundary, camelsh_selected_basins, "
        "camelsh_selected_basins_display_clipped, camelsh_selected_outlets, "
        "camelsh_intersect_only_basins, "
        "camelsh_intersect_only_basins_display_clipped, "
        "camelsh_intersect_only_outlets"
    )


if __name__ == "__main__":
    main()
