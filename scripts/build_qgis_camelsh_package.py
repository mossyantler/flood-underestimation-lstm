#!/usr/bin/env python3

from __future__ import annotations

import argparse
import math
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString


TARGET_CRS = "EPSG:5070"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a QGIS-ready GeoPackage with CAMELSH/HUC overlay layers."
    )
    parser.add_argument(
        "--region-shapefile",
        type=Path,
        default=Path("basins/huc8_delware/huc8_delware.shp"),
        help="Reference HUC8 shapefile.",
    )
    parser.add_argument(
        "--overlay-dir",
        type=Path,
        default=Path("output/basin/huc8_delware_camelsh/overlay"),
        help="Overlay directory created by export_camelsh_huc_overlays.py",
    )
    parser.add_argument(
        "--output-gpkg",
        type=Path,
        default=Path("output/basin/huc8_delware_camelsh/overlay/qgis_camelsh_layers.gpkg"),
        help="Output GeoPackage path.",
    )
    return parser.parse_args()


def rectangle_side_lengths(geom) -> tuple[float, float]:
    mrr = geom.minimum_rotated_rectangle
    coords = list(mrr.exterior.coords)
    sides = []
    for idx in range(4):
        segment = LineString([coords[idx], coords[idx + 1]])
        sides.append(segment.length)
    unique = sorted({round(side, 6) for side in sides})
    if len(unique) == 1:
        return unique[0], unique[0]
    return unique[0], unique[-1]


def add_shape_metrics(gdf: gpd.GeoDataFrame, prefix: str) -> gpd.GeoDataFrame:
    projected = gdf.to_crs(TARGET_CRS)
    out = gdf.copy()

    area_m2 = projected.geometry.area
    perimeter_m = projected.geometry.length
    lengths = []
    widths = []
    form_factors = []
    elongations = []
    aspect_ratios = []

    for geom, area in zip(projected.geometry, area_m2):
        width_m, length_m = rectangle_side_lengths(geom)
        width_km = width_m / 1_000
        length_km = length_m / 1_000
        lengths.append(length_km)
        widths.append(width_km)
        aspect_ratios.append(length_m / width_m if width_m else None)
        form_factors.append(area / (length_m ** 2) if length_m else None)
        elongations.append((2 * math.sqrt(area / math.pi)) / length_m if length_m else None)

    out[f"{prefix}_area_km2_geom"] = area_m2 / 1_000_000
    out[f"{prefix}_perimeter_km_geom"] = perimeter_m / 1_000
    out[f"{prefix}_circularity_ratio"] = (4 * math.pi * area_m2) / (perimeter_m ** 2)
    out[f"{prefix}_mrr_length_km"] = lengths
    out[f"{prefix}_mrr_width_km"] = widths
    out[f"{prefix}_aspect_ratio"] = aspect_ratios
    out[f"{prefix}_form_factor"] = form_factors
    out[f"{prefix}_elongation_ratio"] = elongations
    return out


def main() -> None:
    args = parse_args()
    args.output_gpkg.parent.mkdir(parents=True, exist_ok=True)
    if args.output_gpkg.exists():
        args.output_gpkg.unlink()

    region = gpd.read_file(args.region_shapefile).to_crs("EPSG:4326")
    region = add_shape_metrics(region, prefix="huc8")

    basins = gpd.read_file(args.overlay_dir / "camelsh_region_basins.geojson")
    basins = add_shape_metrics(basins, prefix="camelsh")

    outlets = gpd.read_file(args.overlay_dir / "camelsh_region_outlets.geojson")
    matched_huc8 = gpd.read_file(args.overlay_dir / "matched_huc8.geojson")
    matched_huc8 = add_shape_metrics(matched_huc8, prefix="wbd_huc8")
    matched_huc10 = gpd.read_file(args.overlay_dir / "matched_huc10.geojson")
    matched_huc10 = add_shape_metrics(matched_huc10, prefix="huc10")
    matched_huc12 = gpd.read_file(args.overlay_dir / "matched_huc12.geojson")
    matched_huc12 = add_shape_metrics(matched_huc12, prefix="huc12")

    contained_huc10_path = args.overlay_dir / "contained_huc10.geojson"
    contained_huc12_path = args.overlay_dir / "contained_huc12.geojson"

    region.to_file(args.output_gpkg, layer="huc8_region", driver="GPKG")
    basins.to_file(args.output_gpkg, layer="camelsh_basins", driver="GPKG")
    outlets.to_file(args.output_gpkg, layer="camelsh_outlets", driver="GPKG")
    matched_huc8.to_file(args.output_gpkg, layer="matched_huc8", driver="GPKG")
    matched_huc10.to_file(args.output_gpkg, layer="matched_huc10", driver="GPKG")
    matched_huc12.to_file(args.output_gpkg, layer="matched_huc12", driver="GPKG")

    if contained_huc10_path.exists():
        contained_huc10 = gpd.read_file(contained_huc10_path)
        contained_huc10 = add_shape_metrics(contained_huc10, prefix="contained_huc10")
        contained_huc10.to_file(args.output_gpkg, layer="contained_huc10", driver="GPKG")

    if contained_huc12_path.exists():
        contained_huc12 = gpd.read_file(contained_huc12_path)
        contained_huc12 = add_shape_metrics(contained_huc12, prefix="contained_huc12")
        contained_huc12.to_file(args.output_gpkg, layer="contained_huc12", driver="GPKG")

    print(f"Wrote GeoPackage: {args.output_gpkg}")
    print(
        "Layers: huc8_region, camelsh_basins, camelsh_outlets, "
        "matched_huc8, matched_huc10, matched_huc12, "
        "contained_huc10?, contained_huc12?"
    )


if __name__ == "__main__":
    main()
