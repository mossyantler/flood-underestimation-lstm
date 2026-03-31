#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import shapefile
from pyproj import CRS, Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform as shapely_transform, unary_union
from shapely.prepared import prep


CAMELSH_ATTRIBUTE_FILES = {
    "basin_id": "attributes_gageii_BasinID.csv",
    "topo": "attributes_gageii_Topo.csv",
    "nldas2_climate": "attributes_nldas2_climate.csv",
    "hydro": "attributes_gageii_Hydro.csv",
    "soils": "attributes_gageii_Soils.csv",
    "geology": "attributes_gageii_Geology.csv",
    "landcover": "attributes_gageii_LC06_Basin.csv",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build HUC8 inventory and CAMELSH region subset tables."
    )
    parser.add_argument(
        "--region-shapefile",
        type=Path,
        default=Path("basins/huc8_delware/huc8_delware.shp"),
        help="Path to the region HUC8 shapefile.",
    )
    parser.add_argument(
        "--camelsh-dir",
        type=Path,
        default=Path("tmp/camelsh"),
        help="Directory containing extracted CAMELSH core files.",
    )
    parser.add_argument(
        "--camelsh-boundary-shapefile",
        type=Path,
        default=Path("tmp/camelsh/shapefiles/CAMELSH_shapefile.shp"),
        help="Path to the extracted CAMELSH basin boundary shapefile.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/basin/huc8_delware_camelsh"),
        help="Directory where derived CSV files will be written.",
    )
    return parser.parse_args()


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype={"STAID": str})


def clean_value(value):
    if isinstance(value, str):
        return value.strip()
    return value


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
                "huc2": huc_code[:2],
                "huc4": huc_code[:4],
                "geometry": geom,
                "prepared_geometry": prep(geom),
            }
        )

    inventory = pd.DataFrame(inventory_rows).sort_values("huc_code").reset_index(drop=True)
    return inventory, polygons, layer_crs


def load_camelsh_boundaries(
    shapefile_path: Path,
    region_crs: CRS,
) -> dict[str, dict]:
    reader = shapefile.Reader(str(shapefile_path))
    field_names = [field[0] for field in reader.fields[1:]]
    prj_path = shapefile_path.with_suffix(".prj")
    boundary_crs = CRS.from_wkt(prj_path.read_text()) if prj_path.exists() else CRS.from_epsg(4326)
    to_region = Transformer.from_crs(boundary_crs, region_crs, always_xy=True)

    gauge_field = None
    for candidate in ("GAGE_ID", "GAGEID", "STAID", "gage_id"):
        if candidate in field_names:
            gauge_field = candidate
            break
    if gauge_field is None:
        raise ValueError("CAMELSH boundary shapefile에서 gauge ID field를 찾지 못했습니다.")

    basins: dict[str, dict] = {}
    for record, shp in zip(reader.records(), reader.shapes()):
        attrs = dict(zip(field_names, record))
        gauge_id = str(attrs[gauge_field]).strip()
        geom = shape(shp.__geo_interface__)
        geom_region = shapely_transform(to_region.transform, geom)
        basins[gauge_id] = {
            "geometry_region": geom_region,
            "area_km2_geom": geom_region.area / 1_000_000,
            "perimeter_km_geom": geom_region.length / 1_000,
        }
    return basins


def load_camelsh_attributes(camelsh_dir: Path) -> pd.DataFrame:
    basin_id = read_csv(camelsh_dir / "attributes" / CAMELSH_ATTRIBUTE_FILES["basin_id"])
    topo = read_csv(camelsh_dir / "attributes" / CAMELSH_ATTRIBUTE_FILES["topo"])
    climate = read_csv(camelsh_dir / "attributes" / CAMELSH_ATTRIBUTE_FILES["nldas2_climate"])
    hydro = read_csv(camelsh_dir / "attributes" / CAMELSH_ATTRIBUTE_FILES["hydro"])
    soils = read_csv(camelsh_dir / "attributes" / CAMELSH_ATTRIBUTE_FILES["soils"])
    geology = read_csv(camelsh_dir / "attributes" / CAMELSH_ATTRIBUTE_FILES["geology"])
    landcover = read_csv(camelsh_dir / "attributes" / CAMELSH_ATTRIBUTE_FILES["landcover"])
    info = pd.read_csv(camelsh_dir / "info.csv", dtype={"STAID": str}).rename(
        columns={"data_availability [hrs]": "data_availability_hours"}
    )

    merged = basin_id.merge(topo, on="STAID", how="left")
    merged = merged.merge(climate, on="STAID", how="left")
    merged = merged.merge(hydro, on="STAID", how="left")
    merged = merged.merge(soils, on="STAID", how="left")
    merged = merged.merge(geology, on="STAID", how="left")
    merged = merged.merge(landcover, on="STAID", how="left")
    merged = merged.merge(info, on="STAID", how="left")
    return merged


def build_mapping(
    basin_table: pd.DataFrame,
    boundaries: dict[str, dict],
    polygons: list[dict],
    layer_crs: CRS,
) -> pd.DataFrame:
    to_layer = Transformer.from_crs(4326, layer_crs, always_xy=True)
    region_union = unary_union([item["geometry"] for item in polygons])

    rows: list[dict] = []
    for basin in basin_table.itertuples(index=False):
        gauge_id = basin.STAID
        gauge_name = basin.STANAME
        gauge_lon = float(basin.LNG_GAGE)
        gauge_lat = float(basin.LAT_GAGE)
        point_x, point_y = to_layer.transform(gauge_lon, gauge_lat)
        point_region = Point(point_x, point_y)

        outlet_matches = [
            polygon
            for polygon in polygons
            if polygon["prepared_geometry"].covers(point_region)
        ]
        boundary = boundaries.get(gauge_id)
        intersect_matches = []
        if boundary is not None and boundary["geometry_region"].intersects(region_union):
            intersect_matches = [
                polygon
                for polygon in polygons
                if polygon["geometry"].intersects(boundary["geometry_region"])
            ]

        primary_match = outlet_matches[0] if outlet_matches else (intersect_matches[0] if intersect_matches else None)

        data_availability_hours = int(basin._asdict().get("data_availability_hours", 0) or 0)
        rows.append(
            {
                "gauge_id": gauge_id,
                "gauge_name": gauge_name,
                "state": basin.STATE,
                "gauge_lat": gauge_lat,
                "gauge_lon": gauge_lon,
                "drain_sqkm": basin.DRAIN_SQKM,
                "camelsh_huc_02": basin.HUC02,
                "outlet_in_region": bool(outlet_matches),
                "basin_intersects_region": bool(intersect_matches),
                "region_related": bool(outlet_matches or intersect_matches),
                "selection_mode": (
                    "outlet"
                    if outlet_matches
                    else "intersects"
                    if intersect_matches
                    else "outside"
                ),
                "matched_huc_count_outlet": len(outlet_matches),
                "matched_huc_codes_outlet": "|".join(match["huc_code"] for match in outlet_matches),
                "matched_huc_names_outlet": "|".join(match["huc_name"] for match in outlet_matches),
                "matched_huc_count_intersects": len(intersect_matches),
                "matched_huc_codes_intersects": "|".join(match["huc_code"] for match in intersect_matches),
                "matched_huc_names_intersects": "|".join(match["huc_name"] for match in intersect_matches),
                "primary_huc_code": primary_match["huc_code"] if primary_match else pd.NA,
                "primary_huc_name": primary_match["huc_name"] if primary_match else pd.NA,
                "primary_huc2": primary_match["huc2"] if primary_match else pd.NA,
                "primary_huc4": primary_match["huc4"] if primary_match else pd.NA,
                "point_x_layer_crs": round(point_x, 3),
                "point_y_layer_crs": round(point_y, 3),
                "boundary_area_km2_geom": round(boundary["area_km2_geom"], 3) if boundary else pd.NA,
                "boundary_perimeter_km_geom": round(boundary["perimeter_km_geom"], 3) if boundary else pd.NA,
                "data_availability_hours": data_availability_hours,
                "has_hourly_observations": data_availability_hours > 0,
            }
        )

    return pd.DataFrame(rows).sort_values(
        ["region_related", "selection_mode", "primary_huc_code", "gauge_id"],
        ascending=[False, True, True, True],
    ).reset_index(drop=True)


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    inventory, polygons, layer_crs = load_region_layer(args.region_shapefile)
    boundaries = load_camelsh_boundaries(args.camelsh_boundary_shapefile, layer_crs)
    basin_table = load_camelsh_attributes(args.camelsh_dir)
    mapping = build_mapping(basin_table, boundaries, polygons, layer_crs)

    outlet_counts = (
        mapping.loc[mapping["outlet_in_region"]]
        .groupby("primary_huc_code")
        .size()
        .rename("matched_camelsh_basin_count_outlet")
        .reset_index()
    )
    intersect_counts = (
        mapping.loc[mapping["basin_intersects_region"]]
        .groupby("primary_huc_code")
        .size()
        .rename("matched_camelsh_basin_count_intersects")
        .reset_index()
    )
    inventory = inventory.merge(
        outlet_counts,
        left_on="huc_code",
        right_on="primary_huc_code",
        how="left",
    ).drop(columns=["primary_huc_code"])
    inventory = inventory.merge(
        intersect_counts,
        left_on="huc_code",
        right_on="primary_huc_code",
        how="left",
    ).drop(columns=["primary_huc_code"])
    inventory["matched_camelsh_basin_count_outlet"] = inventory["matched_camelsh_basin_count_outlet"].fillna(0).astype(int)
    inventory["matched_camelsh_basin_count_intersects"] = inventory["matched_camelsh_basin_count_intersects"].fillna(0).astype(int)

    outlet_candidates = (
        mapping.loc[mapping["outlet_in_region"]]
        .copy()
        .sort_values(["primary_huc_code", "gauge_id"])
        .reset_index(drop=True)
    )
    expanded_candidates = (
        mapping.loc[mapping["basin_intersects_region"]]
        .copy()
        .sort_values(["primary_huc_code", "gauge_id"])
        .reset_index(drop=True)
    )

    selected_columns = [
        "STAID",
        "STANAME",
        "DRAIN_SQKM",
        "HUC02",
        "LAT_GAGE",
        "LNG_GAGE",
        "STATE",
        "ELEV_MEAN_M_BASIN",
        "SLOPE_PCT",
        "p_mean",
        "pet_mean",
        "aridity_index",
        "p_seasonality",
        "frac_snow",
        "high_prec_freq",
        "high_prec_dur",
        "BFI_AVE",
        "RUNAVE7100",
        "AWCAVE",
        "PERMAVE",
        "ROCKDEPAVE",
        "GEOL_REEDBUSH_DOM",
        "GEOL_REEDBUSH_DOM_PCT",
        "DEVNLCD06",
        "FORESTNLCD06",
        "PLANTNLCD06",
        "WATERNLCD06",
        "WOODYWETNLCD06",
        "EMERGWETNLCD06",
        "data_availability_hours",
    ]
    selected_attributes = basin_table[selected_columns].rename(
        columns={
            "STAID": "gauge_id",
            "STANAME": "gauge_name_attr",
            "DRAIN_SQKM": "drain_sqkm_attr",
            "HUC02": "camelsh_huc_02_attr",
            "LAT_GAGE": "gauge_lat_attr",
            "LNG_GAGE": "gauge_lon_attr",
            "STATE": "state_attr",
            "ELEV_MEAN_M_BASIN": "elev_mean_m_basin",
            "SLOPE_PCT": "slope_pct_basin",
            "BFI_AVE": "bfi_ave",
            "RUNAVE7100": "runave7100",
            "AWCAVE": "awcave",
            "PERMAVE": "permave",
            "ROCKDEPAVE": "rockdepave",
            "GEOL_REEDBUSH_DOM": "geol_reedbush_dom",
            "GEOL_REEDBUSH_DOM_PCT": "geol_reedbush_dom_pct",
            "DEVNLCD06": "devnlcd06",
            "FORESTNLCD06": "forestnlcd06",
            "PLANTNLCD06": "plantnlcd06",
            "WATERNLCD06": "waternlcd06",
            "WOODYWETNLCD06": "woodywetnlcd06",
            "EMERGWETNLCD06": "emergwetnlcd06",
            "data_availability_hours": "data_availability_hours_attr",
        }
    )
    outlet_candidates = outlet_candidates.merge(selected_attributes, on="gauge_id", how="left")
    expanded_candidates = expanded_candidates.merge(selected_attributes, on="gauge_id", how="left")

    inventory.to_csv(args.output_dir / "huc8_inventory.csv", index=False)
    mapping.to_csv(args.output_dir / "camelsh_basin_huc8_mapping.csv", index=False)
    outlet_candidates.to_csv(args.output_dir / "camelsh_region_candidates_outlet.csv", index=False)
    expanded_candidates.to_csv(args.output_dir / "camelsh_region_candidates_intersects.csv", index=False)

    print(f"HUC8 inventory rows: {len(inventory)}")
    print(f"CAMELSH basins with outlet in region: {len(outlet_candidates)} / {len(mapping)}")
    print(f"CAMELSH basins with polygon intersection: {len(expanded_candidates)} / {len(mapping)}")
    print(
        "Hourly-observed candidates (expanded): "
        f"{int(expanded_candidates['has_hourly_observations'].sum())}"
    )
    print(f"Wrote files to: {args.output_dir}")


if __name__ == "__main__":
    main()
