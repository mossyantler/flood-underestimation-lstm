#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import geopandas as gpd
import pandas as pd


WBD_BASE_URL = "https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Define the working hydrologic region from mostly-contained HUC10 polygons, "
            "fetch matching official HUC8 polygons, and keep only HUC12 polygons nested "
            "inside the selected HUC10 set."
        )
    )
    parser.add_argument(
        "--overlay-dir",
        type=Path,
        default=Path("output/basin/huc8_delware_camelsh/overlay"),
        help="Directory containing mostly_contained_huc10.geojson and mostly_contained_huc12.geojson.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/basin/huc8_delware_camelsh/defined_from_mostly_huc10"),
        help="Directory where the defined HUC outputs will be written.",
    )
    return parser.parse_args()


def fetch_exact_wbd_features(layer_id: int, code_field: str, codes: list[str]) -> list[dict]:
    features: list[dict] = []
    for code in codes:
        payload = None
        last_error = None
        for attempt in range(3):
            try:
                params = {
                    "where": f"{code_field} = '{code}'",
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
                f"WBD layer {layer_id} code {code} 조회 실패"
            ) from last_error

        matched = payload.get("features", [])
        if not matched:
            raise RuntimeError(f"WBD layer {layer_id} code {code} 결과가 없습니다.")
        features.extend(matched)

    return features


def add_parent_codes(huc10_gdf: gpd.GeoDataFrame, huc12_gdf: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    huc10 = huc10_gdf.copy()
    huc12 = huc12_gdf.copy()

    huc10["huc10"] = huc10["huc10"].astype(str)
    huc10["parent_huc8"] = huc10["huc10"].str[:8]

    huc12["huc12"] = huc12["huc12"].astype(str)
    huc12["parent_huc10"] = huc12["huc12"].str[:10]
    huc12["parent_huc8"] = huc12["huc12"].str[:8]
    return huc10, huc12


def build_defined_region_layer(huc10_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "region_id": ["defined_from_mostly_huc10"],
            "source_huc10_count": [len(huc10_gdf)],
            "source_huc8_count": [huc10_gdf["parent_huc8"].nunique()],
        },
        geometry=[huc10_gdf.union_all()],
        crs=huc10_gdf.crs,
    )


def add_layer_labels(
    huc8_gdf: gpd.GeoDataFrame,
    huc10_gdf: gpd.GeoDataFrame,
    huc12_gdf: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    huc8 = huc8_gdf.copy()
    huc10 = huc10_gdf.copy()
    huc12 = huc12_gdf.copy()

    huc8["huc8_label"] = huc8["huc8"].astype(str) + " " + huc8["name"].astype(str)
    huc10["huc10_label"] = huc10["huc10"].astype(str) + " " + huc10["name"].astype(str)
    huc12["huc12_label"] = huc12["huc12"].astype(str) + " " + huc12["name"].astype(str)
    return huc8, huc10, huc12


def build_huc8_summary(
    huc8_gdf: gpd.GeoDataFrame,
    huc10_gdf: gpd.GeoDataFrame,
    huc12_gdf: gpd.GeoDataFrame,
) -> pd.DataFrame:
    huc10_counts = huc10_gdf.groupby("parent_huc8").size().rename("child_huc10_count")
    huc12_counts = huc12_gdf.groupby("parent_huc8").size().rename("child_huc12_count")

    summary = huc8_gdf.drop(columns="geometry").copy()
    summary["huc8"] = summary["huc8"].astype(str)
    summary = summary.merge(
        huc10_counts,
        how="left",
        left_on="huc8",
        right_index=True,
    )
    summary = summary.merge(
        huc12_counts,
        how="left",
        left_on="huc8",
        right_index=True,
    )
    summary["child_huc10_count"] = summary["child_huc10_count"].fillna(0).astype(int)
    summary["child_huc12_count"] = summary["child_huc12_count"].fillna(0).astype(int)
    return summary.sort_values("huc8").reset_index(drop=True)


def write_geojson(gdf: gpd.GeoDataFrame, path: Path) -> None:
    gdf.to_file(path, driver="GeoJSON")


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    mostly_huc10 = gpd.read_file(args.overlay_dir / "mostly_contained_huc10.geojson")
    mostly_huc12 = gpd.read_file(args.overlay_dir / "mostly_contained_huc12.geojson")
    mostly_huc10, mostly_huc12 = add_parent_codes(mostly_huc10, mostly_huc12)

    selected_huc10_codes = sorted(mostly_huc10["huc10"].unique())
    selected_huc8_codes = sorted({code[:8] for code in selected_huc10_codes})

    defined_huc12 = mostly_huc12[
        mostly_huc12["parent_huc10"].isin(selected_huc10_codes)
    ].copy()

    huc8_features = fetch_exact_wbd_features(layer_id=4, code_field="huc8", codes=selected_huc8_codes)
    defined_huc8 = gpd.GeoDataFrame.from_features(huc8_features, crs="EPSG:4326")
    defined_huc8["huc8"] = defined_huc8["huc8"].astype(str)
    defined_huc8 = defined_huc8.sort_values("huc8").reset_index(drop=True)

    defined_huc10 = mostly_huc10.sort_values("huc10").reset_index(drop=True)
    defined_huc12 = defined_huc12.sort_values("huc12").reset_index(drop=True)
    defined_huc8, defined_huc10, defined_huc12 = add_layer_labels(
        defined_huc8,
        defined_huc10,
        defined_huc12,
    )
    defined_region = build_defined_region_layer(defined_huc10)

    huc8_summary = build_huc8_summary(defined_huc8, defined_huc10, defined_huc12)

    write_geojson(defined_region, args.output_dir / "defined_region.geojson")
    write_geojson(defined_huc8, args.output_dir / "defined_huc8.geojson")
    write_geojson(defined_huc10, args.output_dir / "defined_huc10.geojson")
    write_geojson(defined_huc12, args.output_dir / "defined_huc12.geojson")
    huc8_summary.to_csv(args.output_dir / "defined_huc8_summary.csv", index=False)

    print(f"Defined HUC8 polygons: {len(defined_huc8)}")
    print(f"Defined HUC10 polygons: {len(defined_huc10)}")
    print(f"Defined HUC12 polygons: {len(defined_huc12)}")
    print(f"Wrote files to: {args.output_dir}")


if __name__ == "__main__":
    main()
