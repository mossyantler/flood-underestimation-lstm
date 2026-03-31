#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import shapefile
from pyproj import CRS, Transformer
from shapely.geometry import Point, mapping, shape
from shapely.ops import transform as shapely_transform
from shapely.prepared import prep


WBD_BASE_URL = "https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export CAMELS candidate basin overlays and matched HUC layers."
    )
    parser.add_argument(
        "--candidates-csv",
        type=Path,
        default=Path("output/basin/huc8_delware_camels/camels_region_candidates.csv"),
        help="Candidate CAMELS basin CSV created by build_huc8_camels_tables.py",
    )
    parser.add_argument(
        "--camels-boundary-zip",
        type=Path,
        default=Path("tmp/camels_boundaries/basin_set_full_res.zip"),
        help="Zip file containing the full-resolution CAMELS basin boundaries.",
    )
    parser.add_argument(
        "--extract-dir",
        type=Path,
        default=Path("tmp/camels_boundaries/full_res"),
        help="Directory where the CAMELS boundary zip should be extracted.",
    )
    parser.add_argument(
        "--region-shapefile",
        type=Path,
        default=Path("basins/huc8_delware/huc8_delware.shp"),
        help="Reference HUC8 layer used for overlay coordinates.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/basin/huc8_delware_camels/overlay"),
        help="Output directory for overlay-ready files.",
    )
    return parser.parse_args()


def ensure_extracted(zip_path: Path, extract_dir: Path) -> Path:
    shp_path = extract_dir / "HCDN_nhru_final_671.shp"
    if shp_path.exists():
        return shp_path

    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    return shp_path


def read_candidates(path: Path) -> list[dict]:
    with path.open(newline="") as fp:
        return list(csv.DictReader(fp))


def load_region_transformers(region_shapefile: Path) -> tuple[Transformer, Transformer]:
    region_crs = CRS.from_wkt(region_shapefile.with_suffix(".prj").read_text())
    to_region = Transformer.from_crs(4326, region_crs, always_xy=True)
    return to_region, Transformer.from_crs(region_crs, 4326, always_xy=True)


def load_camels_boundaries(boundary_shapefile: Path) -> tuple[dict[str, dict], CRS]:
    reader = shapefile.Reader(str(boundary_shapefile))
    fields = [field[0] for field in reader.fields[1:]]
    boundary_crs = CRS.from_wkt(boundary_shapefile.with_suffix(".prj").read_text())
    to_wgs84 = Transformer.from_crs(boundary_crs, 4326, always_xy=True)

    basins: dict[str, dict] = {}
    for record, shp in zip(reader.records(), reader.shapes()):
        attrs = dict(zip(fields, record))
        gauge_id = f"{int(attrs['hru_id']):08d}"
        geom = shape(shp.__geo_interface__)
        geom_wgs84 = shapely_transform(to_wgs84.transform, geom)
        basins[gauge_id] = {
            "geometry_wgs84": geom_wgs84,
            "centroid_lon": float(attrs["lon_cen"]),
            "centroid_lat": float(attrs["lat_cen"]),
            "boundary_area_km2": float(attrs["AREA"]) / 1_000_000,
            "boundary_perimeter_km": float(attrs["Perimeter"]) / 1_000,
        }
    return basins, boundary_crs


def fetch_wbd_geojson(layer_id: int, field_name: str, prefixes: list[str]) -> dict:
    clauses = [f"{field_name} LIKE '{prefix}%'" for prefix in prefixes]
    where = " OR ".join(clauses)
    params = {
        "where": where,
        "outFields": f"{field_name},name,areasqkm,states",
        "returnGeometry": "true",
        "f": "geojson",
    }
    url = f"{WBD_BASE_URL}/{layer_id}/query?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=120) as response:
        return json.load(response)


def build_huc_lookup(features: list[dict], code_field: str) -> tuple[list[dict], dict[str, dict]]:
    polygons = []
    code_to_feature = {}
    for feature in features:
        props = feature["properties"]
        geom = shape(feature["geometry"])
        code = props[code_field]
        prepared = prep(geom)
        item = {
            "code": code,
            "name": props["name"],
            "areasqkm": props["areasqkm"],
            "states": props.get("states"),
            "geometry": geom,
            "prepared": prepared,
            "feature": feature,
        }
        polygons.append(item)
        code_to_feature[code] = item
    return polygons, code_to_feature


def find_containing_huc(point_wgs84: Point, polygons: list[dict]) -> dict | None:
    for polygon in polygons:
        if polygon["prepared"].covers(point_wgs84):
            return polygon
    return None


def feature_collection(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    candidates = read_candidates(args.candidates_csv)
    candidate_ids = {row["gauge_id"] for row in candidates}
    candidate_huc8 = sorted({row["primary_huc_code"] for row in candidates})

    boundary_shp = ensure_extracted(args.camels_boundary_zip, args.extract_dir)
    camels_basins, _ = load_camels_boundaries(boundary_shp)
    to_region, _ = load_region_transformers(args.region_shapefile)

    huc10_geojson = fetch_wbd_geojson(layer_id=5, field_name="huc10", prefixes=candidate_huc8)
    huc12_geojson = fetch_wbd_geojson(layer_id=6, field_name="huc12", prefixes=candidate_huc8)
    huc10_polygons, huc10_by_code = build_huc_lookup(huc10_geojson["features"], "huc10")
    huc12_polygons, huc12_by_code = build_huc_lookup(huc12_geojson["features"], "huc12")

    point_features = []
    basin_features = []
    overlay_rows = []
    used_huc10_codes: set[str] = set()
    used_huc12_codes: set[str] = set()

    for row in candidates:
        gauge_id = row["gauge_id"]
        if gauge_id not in camels_basins:
            continue

        basin = camels_basins[gauge_id]
        gauge_lon = float(row["gauge_lon"])
        gauge_lat = float(row["gauge_lat"])
        point_wgs84 = Point(gauge_lon, gauge_lat)
        point_x_region, point_y_region = to_region.transform(gauge_lon, gauge_lat)

        matched_huc10 = find_containing_huc(point_wgs84, huc10_polygons)
        matched_huc12 = find_containing_huc(point_wgs84, huc12_polygons)

        if matched_huc10:
            used_huc10_codes.add(matched_huc10["code"])
        if matched_huc12:
            used_huc12_codes.add(matched_huc12["code"])

        attrs = {
            "gauge_id": gauge_id,
            "gauge_name": row["gauge_name"],
            "gauge_lat": gauge_lat,
            "gauge_lon": gauge_lon,
            "x_huc8_layer_crs": round(point_x_region, 3),
            "y_huc8_layer_crs": round(point_y_region, 3),
            "camels_area_gages2_km2": float(row["area_gages2"]),
            "camels_boundary_area_km2": round(basin["boundary_area_km2"], 3),
            "camels_boundary_perimeter_km": round(basin["boundary_perimeter_km"], 3),
            "camels_centroid_lat": round(basin["centroid_lat"], 6),
            "camels_centroid_lon": round(basin["centroid_lon"], 6),
            "primary_huc8_code": row["primary_huc_code"],
            "primary_huc8_name": row["primary_huc_name"],
            "matched_huc10_code": matched_huc10["code"] if matched_huc10 else None,
            "matched_huc10_name": matched_huc10["name"] if matched_huc10 else None,
            "matched_huc10_area_km2": matched_huc10["areasqkm"] if matched_huc10 else None,
            "matched_huc12_code": matched_huc12["code"] if matched_huc12 else None,
            "matched_huc12_name": matched_huc12["name"] if matched_huc12 else None,
            "matched_huc12_area_km2": matched_huc12["areasqkm"] if matched_huc12 else None,
        }

        overlay_rows.append(attrs)
        point_features.append(
            {
                "type": "Feature",
                "geometry": mapping(point_wgs84),
                "properties": attrs,
            }
        )
        basin_features.append(
            {
                "type": "Feature",
                "geometry": mapping(basin["geometry_wgs84"]),
                "properties": attrs,
            }
        )

    huc10_features = [
        huc10_by_code[code]["feature"]
        for code in sorted(used_huc10_codes)
        if code in huc10_by_code
    ]
    huc12_features = [
        huc12_by_code[code]["feature"]
        for code in sorted(used_huc12_codes)
        if code in huc12_by_code
    ]

    overlay_rows.sort(key=lambda row: row["gauge_id"])
    csv_path = args.output_dir / "camels_region_points_with_huc_matches.csv"
    with csv_path.open("w", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(overlay_rows[0].keys()))
        writer.writeheader()
        writer.writerows(overlay_rows)

    (args.output_dir / "camels_region_outlets.geojson").write_text(
        json.dumps(feature_collection(point_features))
    )
    (args.output_dir / "camels_region_basins.geojson").write_text(
        json.dumps(feature_collection(basin_features))
    )
    (args.output_dir / "matched_huc10.geojson").write_text(
        json.dumps(feature_collection(huc10_features))
    )
    (args.output_dir / "matched_huc12.geojson").write_text(
        json.dumps(feature_collection(huc12_features))
    )

    print(f"Candidate CAMELS basins exported: {len(point_features)}")
    print(f"Matched HUC10 polygons exported: {len(huc10_features)}")
    print(f"Matched HUC12 polygons exported: {len(huc12_features)}")
    print(f"Overlay files written to: {args.output_dir}")


if __name__ == "__main__":
    main()
