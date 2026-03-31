#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import urllib.parse
import urllib.request
from pathlib import Path

import shapefile
from pyproj import CRS, Transformer
from shapely.geometry import Point, mapping, shape
from shapely.ops import transform as shapely_transform
from shapely.prepared import prep


WBD_BASE_URL = "https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export CAMELSH region overlays and matched HUC layers."
    )
    parser.add_argument(
        "--candidates-csv",
        type=Path,
        default=Path("output/basin/huc8_delware_camelsh/camelsh_region_candidates_intersects.csv"),
        help="Candidate CAMELSH CSV created by build_huc8_camelsh_tables.py",
    )
    parser.add_argument(
        "--camelsh-boundary-shapefile",
        type=Path,
        default=Path("tmp/camelsh/shapefiles/CAMELSH_shapefile.shp"),
        help="Path to the extracted CAMELSH basin boundary shapefile.",
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
        default=Path("output/basin/huc8_delware_camelsh/overlay"),
        help="Output directory for overlay-ready files.",
    )
    return parser.parse_args()


def read_candidates(path: Path) -> list[dict]:
    with path.open(newline="") as fp:
        return list(csv.DictReader(fp))


def load_region_huc8_codes(region_shapefile: Path) -> list[str]:
    reader = shapefile.Reader(str(region_shapefile))
    field_names = [field[0] for field in reader.fields[1:]]
    code_idx = field_names.index("HUC_CODE")
    codes = []
    for record in reader.records():
        value = record[code_idx]
        code = value.strip() if isinstance(value, str) else str(value)
        codes.append(code)
    return sorted(set(codes))


def load_region_transformers(region_shapefile: Path) -> tuple[Transformer, Transformer]:
    region_crs = CRS.from_wkt(region_shapefile.with_suffix(".prj").read_text())
    to_region = Transformer.from_crs(4326, region_crs, always_xy=True)
    return to_region, Transformer.from_crs(region_crs, 4326, always_xy=True)


def load_camelsh_boundaries(boundary_shapefile: Path) -> dict[str, dict]:
    reader = shapefile.Reader(str(boundary_shapefile))
    fields = [field[0] for field in reader.fields[1:]]
    prj_path = boundary_shapefile.with_suffix(".prj")
    boundary_crs = CRS.from_wkt(prj_path.read_text()) if prj_path.exists() else CRS.from_epsg(4326)
    to_wgs84 = Transformer.from_crs(boundary_crs, 4326, always_xy=True)

    gauge_field = None
    for candidate in ("GAGE_ID", "GAGEID", "STAID", "gage_id"):
        if candidate in fields:
            gauge_field = candidate
            break
    if gauge_field is None:
        raise ValueError("CAMELSH boundary shapefile에서 gauge ID field를 찾지 못했습니다.")

    basins: dict[str, dict] = {}
    for record, shp in zip(reader.records(), reader.shapes()):
        attrs = dict(zip(fields, record))
        gauge_id = str(attrs[gauge_field]).strip()
        geom = shape(shp.__geo_interface__)
        geom_wgs84 = shapely_transform(to_wgs84.transform, geom)
        basins[gauge_id] = {"geometry_wgs84": geom_wgs84}
    return basins


def fetch_wbd_geojson(layer_id: int, code_field: str, prefixes: list[str]) -> dict:
    features: list[dict] = []
    seen_codes: set[str] = set()
    for prefix in prefixes:
        params = {
            "where": f"{code_field} LIKE '{prefix}%'",
            "outFields": f"{code_field},name,areasqkm,states",
            "returnGeometry": "true",
            "f": "geojson",
        }
        url = f"{WBD_BASE_URL}/{layer_id}/query?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(url, timeout=120) as response:
            payload = json.load(response)
        for feature in payload.get("features", []):
            code = feature["properties"][code_field]
            if code in seen_codes:
                continue
            seen_codes.add(code)
            features.append(feature)
    return {"type": "FeatureCollection", "features": features}


def fetch_wbd_geojson_by_codes(layer_id: int, code_field: str, codes: list[str]) -> dict:
    features: list[dict] = []
    seen_codes: set[str] = set()
    for code in codes:
        params = {
            "where": f"{code_field} = '{code}'",
            "outFields": f"{code_field},name,areasqkm,states",
            "returnGeometry": "true",
            "f": "geojson",
        }
        url = f"{WBD_BASE_URL}/{layer_id}/query?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(url, timeout=120) as response:
            payload = json.load(response)
        for feature in payload.get("features", []):
            current_code = feature["properties"][code_field]
            if current_code in seen_codes:
                continue
            seen_codes.add(current_code)
            features.append(feature)
    return {"type": "FeatureCollection", "features": features}


def build_huc_lookup(features: list[dict], code_field: str) -> tuple[list[dict], dict[str, dict]]:
    polygons = []
    code_to_feature = {}
    for feature in features:
        geom = shape(feature["geometry"])
        code = feature["properties"][code_field]
        item = {
            "code": code,
            "feature": feature,
            "prepared": prep(geom),
            "name": feature["properties"]["name"],
            "areasqkm": feature["properties"]["areasqkm"],
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
    basins = load_camelsh_boundaries(args.camelsh_boundary_shapefile)
    to_region, _ = load_region_transformers(args.region_shapefile)
    region_huc8_codes = load_region_huc8_codes(args.region_shapefile)
    huc4_prefixes = sorted({row["primary_huc4"] for row in candidates if row.get("primary_huc4")})

    huc8_geojson = fetch_wbd_geojson_by_codes(layer_id=4, code_field="huc8", codes=region_huc8_codes)
    huc10_geojson = fetch_wbd_geojson(layer_id=5, code_field="huc10", prefixes=huc4_prefixes)
    huc12_geojson = fetch_wbd_geojson(layer_id=6, code_field="huc12", prefixes=huc4_prefixes)
    huc10_polygons, _ = build_huc_lookup(huc10_geojson["features"], "huc10")
    huc12_polygons, _ = build_huc_lookup(huc12_geojson["features"], "huc12")

    point_features = []
    basin_features = []
    overlay_rows = []
    huc10_features: dict[str, dict] = {}
    huc12_features: dict[str, dict] = {}

    for row in candidates:
        gauge_id = row["gauge_id"]
        if gauge_id not in basins:
            continue

        gauge_lon = float(row["gauge_lon"])
        gauge_lat = float(row["gauge_lat"])
        point_wgs84 = Point(gauge_lon, gauge_lat)
        point_x_region, point_y_region = to_region.transform(gauge_lon, gauge_lat)

        matched_huc10 = find_containing_huc(point_wgs84, huc10_polygons)
        matched_huc12 = find_containing_huc(point_wgs84, huc12_polygons)

        if matched_huc10:
            huc10_features[matched_huc10["code"]] = matched_huc10["feature"]
        if matched_huc12:
            huc12_features[matched_huc12["code"]] = matched_huc12["feature"]

        attrs = {
            "gauge_id": gauge_id,
            "gauge_name": row["gauge_name"],
            "selection_mode": row["selection_mode"],
            "state": row["state"],
            "gauge_lat": gauge_lat,
            "gauge_lon": gauge_lon,
            "x_huc8_layer_crs": round(point_x_region, 3),
            "y_huc8_layer_crs": round(point_y_region, 3),
            "drain_sqkm": row["drain_sqkm"],
            "boundary_area_km2_geom": row["boundary_area_km2_geom"],
            "boundary_perimeter_km_geom": row["boundary_perimeter_km_geom"],
            "primary_huc8_code": row["primary_huc_code"],
            "primary_huc8_name": row["primary_huc_name"],
            "matched_huc10_code": matched_huc10["code"] if matched_huc10 else None,
            "matched_huc10_name": matched_huc10["name"] if matched_huc10 else None,
            "matched_huc10_area_km2": matched_huc10["areasqkm"] if matched_huc10 else None,
            "matched_huc12_code": matched_huc12["code"] if matched_huc12 else None,
            "matched_huc12_name": matched_huc12["name"] if matched_huc12 else None,
            "matched_huc12_area_km2": matched_huc12["areasqkm"] if matched_huc12 else None,
            "data_availability_hours": row["data_availability_hours"],
            "has_hourly_observations": row["has_hourly_observations"],
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
                "geometry": mapping(basins[gauge_id]["geometry_wgs84"]),
                "properties": attrs,
            }
        )

    overlay_rows.sort(key=lambda row: row["gauge_id"])
    csv_path = args.output_dir / "camelsh_region_points_with_huc_matches.csv"
    with csv_path.open("w", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(overlay_rows[0].keys()))
        writer.writeheader()
        writer.writerows(overlay_rows)

    (args.output_dir / "camelsh_region_outlets.geojson").write_text(
        json.dumps(feature_collection(point_features))
    )
    (args.output_dir / "camelsh_region_basins.geojson").write_text(
        json.dumps(feature_collection(basin_features))
    )
    (args.output_dir / "matched_huc8.geojson").write_text(
        json.dumps(feature_collection(huc8_geojson["features"]))
    )
    (args.output_dir / "matched_huc10.geojson").write_text(
        json.dumps(feature_collection([huc10_features[key] for key in sorted(huc10_features)]))
    )
    (args.output_dir / "matched_huc12.geojson").write_text(
        json.dumps(feature_collection([huc12_features[key] for key in sorted(huc12_features)]))
    )

    print(f"Candidate CAMELSH basins exported: {len(point_features)}")
    print(f"Matched HUC8 polygons exported: {len(huc8_geojson['features'])}")
    print(f"Matched HUC10 polygons exported: {len(huc10_features)}")
    print(f"Matched HUC12 polygons exported: {len(huc12_features)}")
    print(f"Overlay files written to: {args.output_dir}")


if __name__ == "__main__":
    main()
