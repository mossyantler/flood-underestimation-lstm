#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a QGIS GeoPackage for one-to-one CAMELSH pair inspection."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("output/basin/huc8_delware_camelsh/camelsh_from_defined_region"),
        help="Directory containing pair GeoJSON files.",
    )
    parser.add_argument(
        "--defined-dir",
        type=Path,
        default=Path("output/basin/huc8_delware_camelsh/defined_from_mostly_huc10"),
        help="Directory containing defined region and HUC layers.",
    )
    parser.add_argument(
        "--output-gpkg",
        type=Path,
        default=Path("output/basin/huc8_delware_camelsh/camelsh_from_defined_region/qgis_camelsh_pairs.gpkg"),
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
    pair_outlets = gpd.read_file(args.input_dir / "camelsh_pair_outlets.geojson")
    pair_basins = gpd.read_file(args.input_dir / "camelsh_pair_basins.geojson")
    pair_links = gpd.read_file(args.input_dir / "camelsh_pair_links.geojson")
    pair_gap_lines = gpd.read_file(args.input_dir / "camelsh_pair_gap_lines.geojson")

    defined_region.to_file(args.output_gpkg, layer="defined_region", driver="GPKG")
    defined_huc8.to_file(args.output_gpkg, layer="defined_huc8", driver="GPKG")
    defined_huc10.to_file(args.output_gpkg, layer="defined_huc10", driver="GPKG")
    defined_huc12.to_file(args.output_gpkg, layer="defined_huc12", driver="GPKG")
    pair_outlets.to_file(args.output_gpkg, layer="camelsh_pair_outlets", driver="GPKG")
    pair_basins.to_file(args.output_gpkg, layer="camelsh_pair_basins", driver="GPKG")
    pair_links.to_file(args.output_gpkg, layer="camelsh_pair_links", driver="GPKG")
    pair_gap_lines.to_file(args.output_gpkg, layer="camelsh_pair_gap_lines", driver="GPKG")

    print(f"Wrote GeoPackage: {args.output_gpkg}")
    print(
        "Layers: defined_region, defined_huc8, defined_huc10, defined_huc12, "
        "camelsh_pair_outlets, camelsh_pair_basins, camelsh_pair_links, camelsh_pair_gap_lines"
    )


if __name__ == "__main__":
    main()
