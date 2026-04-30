#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, mapping
from shapely.ops import nearest_points


TARGET_CRS = "EPSG:5070"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build one-to-one CAMELSH pair layers so each outlet and basin can be "
            "inspected as a matched pair in QGIS."
        )
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("output/basin/drbc/archive/huc8_delaware_camelsh/camelsh_from_defined_region"),
        help="Directory containing camelsh_outlets.geojson and camelsh_basins.geojson.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/basin/drbc/archive/huc8_delaware_camelsh/camelsh_from_defined_region"),
        help="Directory where pair layers will be written.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    outlets = gpd.read_file(args.input_dir / "camelsh_outlets.geojson")
    basins = gpd.read_file(args.input_dir / "camelsh_basins.geojson")

    basins = basins.rename(columns={"GAGE_ID": "pair_id"})
    outlets = outlets.rename(columns={"STAID": "pair_id"})

    pair_outlets = outlets.copy()
    pair_basins = basins.copy()

    merged = pair_basins[["pair_id", "STANAME", "geometry"]].merge(
        pair_outlets[["pair_id", "geometry"]],
        on="pair_id",
        suffixes=("_basin", "_outlet"),
        how="inner",
    )

    basin_proj = gpd.GeoSeries(merged["geometry_basin"], crs=pair_basins.crs).to_crs(TARGET_CRS)
    outlet_proj = gpd.GeoSeries(merged["geometry_outlet"], crs=pair_outlets.crs).to_crs(TARGET_CRS)

    within_flags = []
    gap_distances = []
    basin_areas = []
    link_features = []
    gap_features = []

    for row, basin_geom_proj, outlet_geom_proj in zip(
        merged.itertuples(index=False),
        basin_proj,
        outlet_proj,
    ):
        within = basin_geom_proj.covers(outlet_geom_proj)
        within_flags.append(within)
        basin_areas.append(basin_geom_proj.area / 1_000_000)

        if within:
            gap_distances.append(0.0)
            nearest_on_basin_proj = outlet_geom_proj
        else:
            nearest_on_basin_proj = nearest_points(outlet_geom_proj, basin_geom_proj)[1]
            gap_distances.append(outlet_geom_proj.distance(nearest_on_basin_proj))

        basin_rep_point = row.geometry_basin.representative_point()
        link_features.append(
            {
                "pair_id": row.pair_id,
                "pair_label": f"{row.pair_id} {row.STANAME}",
                "outlet_within_own_basin": within,
                "outlet_to_own_basin_m": round(gap_distances[-1], 3),
                "geometry": LineString([row.geometry_outlet, basin_rep_point]),
            }
        )

        if not within:
            nearest_on_basin = gpd.GeoSeries([nearest_on_basin_proj], crs=TARGET_CRS).to_crs(pair_basins.crs).iloc[0]
            gap_features.append(
                {
                    "pair_id": row.pair_id,
                    "pair_label": f"{row.pair_id} {row.STANAME}",
                    "outlet_to_own_basin_m": round(gap_distances[-1], 3),
                    "geometry": LineString([row.geometry_outlet, nearest_on_basin]),
                }
            )

    diagnostics = pd.DataFrame(
        {
            "pair_id": merged["pair_id"],
            "pair_label": [f"{pair_id} {name}" for pair_id, name in zip(merged["pair_id"], merged["STANAME"])],
            "outlet_within_own_basin": within_flags,
            "outlet_to_own_basin_m": [round(value, 3) for value in gap_distances],
            "own_basin_area_km2_geom": [round(value, 3) for value in basin_areas],
        }
    )

    pair_outlets = pair_outlets.merge(diagnostics, on="pair_id", how="left")
    pair_basins = pair_basins.merge(diagnostics, on="pair_id", how="left")

    pair_outlets.to_file(args.output_dir / "camelsh_pair_outlets.geojson", driver="GeoJSON")
    pair_basins.to_file(args.output_dir / "camelsh_pair_basins.geojson", driver="GeoJSON")
    gpd.GeoDataFrame(link_features, crs=pair_basins.crs).to_file(
        args.output_dir / "camelsh_pair_links.geojson",
        driver="GeoJSON",
    )
    gpd.GeoDataFrame(gap_features, crs=pair_basins.crs).to_file(
        args.output_dir / "camelsh_pair_gap_lines.geojson",
        driver="GeoJSON",
    )
    diagnostics.sort_values("pair_id").to_csv(args.output_dir / "camelsh_pair_diagnostics.csv", index=False)

    print(f"Pair outlets: {len(pair_outlets)}")
    print(f"Pair basins: {len(pair_basins)}")
    print(f"Outlet within own basin: {int(sum(within_flags))}")
    print(f"Outlet outside own basin: {int((~pd.Series(within_flags)).sum())}")
    print(f"Wrote files to: {args.output_dir}")


if __name__ == "__main__":
    main()
