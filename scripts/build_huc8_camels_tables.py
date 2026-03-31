#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import shapefile
from pyproj import CRS, Transformer
from shapely.geometry import Point, shape
from shapely.prepared import prep


CAMELS_ATTRIBUTE_FILES = {
    "camels_topo": "camels_topo.txt",
    "camels_name": "camels_name.txt",
    "camels_clim": "camels_clim.txt",
    "camels_hydro": "camels_hydro.txt",
    "camels_soil": "camels_soil.txt",
    "camels_geol": "camels_geol.txt",
    "camels_vege": "camels_vege.txt",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build HUC8 inventory and CAMELS basin subset tables for a region layer."
    )
    parser.add_argument(
        "--region-shapefile",
        type=Path,
        default=Path("basins/huc8_delware/huc8_delware.shp"),
        help="Path to the region HUC8 shapefile.",
    )
    parser.add_argument(
        "--camels-attributes-dir",
        type=Path,
        default=Path("data/CAMELS_US/camels_attributes_v2.0"),
        help="Directory with CAMELS attribute text files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/basin/huc8_delware_camels"),
        help="Directory where derived CSV files will be written.",
    )
    return parser.parse_args()


def clean_value(value):
    if isinstance(value, str):
        return value.strip()
    return value


def read_camels_table(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep=";", dtype={"gauge_id": str})


def load_region_layer(shapefile_path: Path) -> tuple[pd.DataFrame, list[dict], CRS]:
    reader = shapefile.Reader(str(shapefile_path))
    field_names = [field[0] for field in reader.fields[1:]]
    layer_crs = CRS.from_wkt(shapefile_path.with_suffix(".prj").read_text())
    to_wgs84 = Transformer.from_crs(layer_crs, 4326, always_xy=True)

    inventory_rows: list[dict] = []
    polygons: list[dict] = []

    for record, shp in zip(reader.records(), reader.shapes()):
        attrs = {
            field_name: clean_value(value)
            for field_name, value in zip(field_names, record)
        }
        geom = shape(shp.__geo_interface__)
        centroid_lon, centroid_lat = to_wgs84.transform(geom.centroid.x, geom.centroid.y)
        huc_code = attrs["HUC_CODE"]

        inventory_rows.append(
            {
                "huc_code": huc_code,
                "huc_name": attrs["HUC_NAME"],
                "reg": attrs["REG"],
                "huc2": huc_code[:2],
                "huc4": huc_code[:4],
                "layer_area_km2": round(geom.area / 1_000_000, 3),
                "centroid_lat": round(centroid_lat, 6),
                "centroid_lon": round(centroid_lon, 6),
                "shape_parts": len(shp.parts),
                "shape_points": len(shp.points),
            }
        )
        polygons.append(
            {
                "huc_code": huc_code,
                "huc_name": attrs["HUC_NAME"],
                "reg": attrs["REG"],
                "huc2": huc_code[:2],
                "huc4": huc_code[:4],
                "geometry": geom,
                "prepared_geometry": prep(geom),
            }
        )

    inventory = pd.DataFrame(inventory_rows).sort_values("huc_code").reset_index(drop=True)
    return inventory, polygons, layer_crs


def build_camels_mapping(
    polygons: list[dict],
    layer_crs: CRS,
    camels_attributes_dir: Path,
) -> pd.DataFrame:
    topo = read_camels_table(camels_attributes_dir / CAMELS_ATTRIBUTE_FILES["camels_topo"])
    names = read_camels_table(camels_attributes_dir / CAMELS_ATTRIBUTE_FILES["camels_name"])

    basins = topo.merge(names, on="gauge_id", how="left")
    to_layer = Transformer.from_crs(4326, layer_crs, always_xy=True)

    rows: list[dict] = []
    for basin in basins.itertuples(index=False):
        point_x, point_y = to_layer.transform(float(basin.gauge_lon), float(basin.gauge_lat))
        point = Point(point_x, point_y)
        matches = [
            polygon
            for polygon in polygons
            if polygon["prepared_geometry"].covers(point)
        ]

        matched_codes = "|".join(match["huc_code"] for match in matches)
        matched_names = "|".join(match["huc_name"] for match in matches)
        primary_match = matches[0] if matches else None

        rows.append(
            {
                "gauge_id": basin.gauge_id,
                "gauge_name": basin.gauge_name,
                "gauge_lat": basin.gauge_lat,
                "gauge_lon": basin.gauge_lon,
                "area_gages2": basin.area_gages2,
                "elev_mean": basin.elev_mean,
                "slope_mean": basin.slope_mean,
                "camels_huc_02": basin.huc_02,
                "in_region": bool(matches),
                "matched_huc_count": len(matches),
                "matched_huc_codes": matched_codes,
                "matched_huc_names": matched_names,
                "primary_huc_code": primary_match["huc_code"] if primary_match else pd.NA,
                "primary_huc_name": primary_match["huc_name"] if primary_match else pd.NA,
                "primary_huc2": primary_match["huc2"] if primary_match else pd.NA,
                "primary_huc4": primary_match["huc4"] if primary_match else pd.NA,
                "point_x_layer_crs": round(point_x, 3),
                "point_y_layer_crs": round(point_y, 3),
            }
        )

    return pd.DataFrame(rows).sort_values(["in_region", "primary_huc_code", "gauge_id"], ascending=[False, True, True]).reset_index(drop=True)


def merge_static_attributes(
    candidate_basins: pd.DataFrame,
    camels_attributes_dir: Path,
) -> pd.DataFrame:
    merged = candidate_basins.copy()
    for key, filename in CAMELS_ATTRIBUTE_FILES.items():
        if key in {"camels_topo", "camels_name"}:
            continue
        table = read_camels_table(camels_attributes_dir / filename)
        merged = merged.merge(table, on="gauge_id", how="left")
    return merged


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    inventory, polygons, layer_crs = load_region_layer(args.region_shapefile)
    mapping = build_camels_mapping(polygons, layer_crs, args.camels_attributes_dir)

    huc_counts = (
        mapping.loc[mapping["in_region"]]
        .groupby("primary_huc_code")
        .size()
        .rename("matched_camels_basin_count")
        .reset_index()
    )
    inventory = inventory.merge(
        huc_counts,
        left_on="huc_code",
        right_on="primary_huc_code",
        how="left",
    ).drop(columns=["primary_huc_code"])
    inventory["matched_camels_basin_count"] = inventory["matched_camels_basin_count"].fillna(0).astype(int)

    candidates = (
        mapping.loc[mapping["in_region"]]
        .copy()
        .sort_values(["primary_huc_code", "gauge_id"])
        .reset_index(drop=True)
    )
    merged_attributes = merge_static_attributes(candidates, args.camels_attributes_dir)

    inventory.to_csv(args.output_dir / "huc8_inventory.csv", index=False)
    mapping.to_csv(args.output_dir / "camels_basin_huc8_mapping.csv", index=False)
    candidates.to_csv(args.output_dir / "camels_region_candidates.csv", index=False)
    merged_attributes.to_csv(
        args.output_dir / "camels_region_candidates_with_static_attributes.csv",
        index=False,
    )

    print(f"HUC8 inventory rows: {len(inventory)}")
    print(f"CAMELS basins mapped inside region: {len(candidates)} / {len(mapping)}")
    print(f"Wrote files to: {args.output_dir}")
    print("Top HUC8 counts:")
    print(
        inventory.loc[inventory["matched_camels_basin_count"] > 0, ["huc_code", "huc_name", "matched_camels_basin_count"]]
        .sort_values(["matched_camels_basin_count", "huc_code"], ascending=[False, True])
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
