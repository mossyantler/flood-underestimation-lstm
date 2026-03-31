#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a QGIS GeoPackage that combines defined HUC layers and matched CAMELSH layers."
    )
    parser.add_argument(
        "--defined-dir",
        type=Path,
        default=Path("output/basin/huc8_delware_camelsh/defined_from_mostly_huc10"),
        help="Directory containing defined_huc8/10/12 outputs.",
    )
    parser.add_argument(
        "--camelsh-dir",
        type=Path,
        default=Path("output/basin/huc8_delware_camelsh/camelsh_from_defined_region"),
        help="Directory containing camelsh_outlets.geojson and camelsh_basins.geojson.",
    )
    parser.add_argument(
        "--output-gpkg",
        type=Path,
        default=Path("output/basin/huc8_delware_camelsh/camelsh_from_defined_region/qgis_defined_camelsh_layers.gpkg"),
        help="Output GeoPackage path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_gpkg.parent.mkdir(parents=True, exist_ok=True)
    if args.output_gpkg.exists():
        args.output_gpkg.unlink()

    defined_region = gpd.read_file(args.defined_dir / "defined_region.geojson")
    defined_huc8 = gpd.read_file(args.defined_dir / "defined_huc8.geojson")
    defined_huc10 = gpd.read_file(args.defined_dir / "defined_huc10.geojson")
    defined_huc12 = gpd.read_file(args.defined_dir / "defined_huc12.geojson")
    camelsh_outlets = gpd.read_file(args.camelsh_dir / "camelsh_outlets.geojson")
    camelsh_basins = gpd.read_file(args.camelsh_dir / "camelsh_basins.geojson")
    camelsh_pair_links = gpd.read_file(args.camelsh_dir / "camelsh_pair_links.geojson")

    defined_region.to_file(args.output_gpkg, layer="defined_region", driver="GPKG")
    defined_huc8.to_file(args.output_gpkg, layer="defined_huc8", driver="GPKG")
    defined_huc10.to_file(args.output_gpkg, layer="defined_huc10", driver="GPKG")
    defined_huc12.to_file(args.output_gpkg, layer="defined_huc12", driver="GPKG")
    camelsh_outlets.to_file(args.output_gpkg, layer="camelsh_outlets", driver="GPKG")
    camelsh_basins.to_file(args.output_gpkg, layer="camelsh_basins", driver="GPKG")
    camelsh_pair_links.to_file(args.output_gpkg, layer="camelsh_pair_links", driver="GPKG")

    print(f"Wrote GeoPackage: {args.output_gpkg}")
    print("Layers: defined_region, defined_huc8, defined_huc10, defined_huc12, camelsh_outlets, camelsh_basins, camelsh_pair_links")


if __name__ == "__main__":
    main()
