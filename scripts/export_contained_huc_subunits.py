#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import shapefile
from pyproj import CRS, Transformer
from shapely.geometry import shape
from shapely.ops import transform as shapely_transform
from shapely.ops import unary_union


WBD_BASE_URL = "https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export official HUC10/HUC12 polygons fully contained in the local region polygon."
    )
    parser.add_argument(
        "--region-shapefile",
        type=Path,
        default=Path("basins/huc8_delware/huc8_delware.shp"),
        help="Local region shapefile used as the containment mask.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/basin/huc8_delware_camelsh/overlay"),
        help="Output directory for contained HUC layers.",
    )
    parser.add_argument(
        "--min-overlap-ratio",
        type=float,
        default=0.8,
        help="Minimum overlap ratio used for relaxed subunit export.",
    )
    return parser.parse_args()


def load_region_union_wgs84(region_shapefile: Path):
    reader = shapefile.Reader(str(region_shapefile))
    field_names = [field[0] for field in reader.fields[1:]]
    region_crs = CRS.from_wkt(region_shapefile.with_suffix(".prj").read_text())
    to_wgs84 = Transformer.from_crs(region_crs, 4326, always_xy=True)

    geoms = []
    huc4s = set()
    huc_code_idx = field_names.index("HUC_CODE")
    for record, shp in zip(reader.records(), reader.shapes()):
        huc_code = record[huc_code_idx]
        huc_code = huc_code.strip() if isinstance(huc_code, str) else str(huc_code)
        huc4s.add(huc_code[:4])
        geom = shape(shp.__geo_interface__)
        geoms.append(shapely_transform(to_wgs84.transform, geom))

    return unary_union(geoms), sorted(huc4s)


def fetch_wbd_features(layer_id: int, code_field: str, prefixes: list[str]) -> list[dict]:
    features: list[dict] = []
    seen_codes: set[str] = set()
    for prefix in prefixes:
        payload = None
        last_error = None
        for attempt in range(3):
            try:
                params = {
                    "where": f"{code_field} LIKE '{prefix}%'",
                    "outFields": f"{code_field},name,areasqkm,states",
                    "returnGeometry": "true",
                    "f": "geojson",
                }
                url = f"{WBD_BASE_URL}/{layer_id}/query?{urllib.parse.urlencode(params)}"
                request = urllib.request.Request(url, headers={"User-Agent": "codex-camels"})
                with urllib.request.urlopen(request, timeout=120) as response:
                    payload = json.load(response)
                break
            except Exception as exc:
                last_error = exc
                time.sleep(1 + attempt)
        if payload is None:
            raise RuntimeError(
                f"WBD layer {layer_id} prefix {prefix} 조회 실패"
            ) from last_error
        for feature in payload.get("features", []):
            code = feature["properties"][code_field]
            if code in seen_codes:
                continue
            seen_codes.add(code)
            features.append(feature)
    return features


def filter_contained(features: list[dict], region_union) -> list[dict]:
    contained = []
    for feature in features:
        geom = shape(feature["geometry"])
        if geom.within(region_union):
            contained.append(feature)
    return contained


def filter_mostly_contained(features: list[dict], region_union, min_overlap_ratio: float) -> list[dict]:
    selected = []
    for feature in features:
        geom = shape(feature["geometry"])
        area = geom.area
        overlap_ratio = (geom.intersection(region_union).area / area) if area else 0.0
        if overlap_ratio >= min_overlap_ratio:
            feature = {
                "type": feature["type"],
                "geometry": feature["geometry"],
                "properties": {
                    **feature["properties"],
                    "overlap_ratio_with_region": round(overlap_ratio, 6),
                },
            }
            selected.append(feature)
    return selected


def write_feature_collection(path: Path, features: list[dict]) -> None:
    payload = {"type": "FeatureCollection", "features": features}
    path.write_text(json.dumps(payload))


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    region_union, huc4s = load_region_union_wgs84(args.region_shapefile)
    huc10_all = fetch_wbd_features(layer_id=5, code_field="huc10", prefixes=huc4s)
    huc12_all = fetch_wbd_features(layer_id=6, code_field="huc12", prefixes=huc4s)

    huc10_contained = filter_contained(huc10_all, region_union)
    huc12_contained = filter_contained(huc12_all, region_union)
    huc10_relaxed = filter_mostly_contained(huc10_all, region_union, args.min_overlap_ratio)
    huc12_relaxed = filter_mostly_contained(huc12_all, region_union, args.min_overlap_ratio)

    write_feature_collection(args.output_dir / "contained_huc10.geojson", huc10_contained)
    write_feature_collection(args.output_dir / "contained_huc12.geojson", huc12_contained)
    write_feature_collection(args.output_dir / "mostly_contained_huc10.geojson", huc10_relaxed)
    write_feature_collection(args.output_dir / "mostly_contained_huc12.geojson", huc12_relaxed)

    print(f"HUC4 prefixes scanned: {', '.join(huc4s)}")
    print(f"Contained HUC10 polygons: {len(huc10_contained)}")
    print(f"Contained HUC12 polygons: {len(huc12_contained)}")
    print(f"Mostly-contained HUC10 polygons (ratio>={args.min_overlap_ratio}): {len(huc10_relaxed)}")
    print(f"Mostly-contained HUC12 polygons (ratio>={args.min_overlap_ratio}): {len(huc12_relaxed)}")
    print(f"Wrote files to: {args.output_dir}")


if __name__ == "__main__":
    main()
