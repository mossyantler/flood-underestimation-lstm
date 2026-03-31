#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pandas>=2.2",
#   "pyproj>=3.7",
#   "pyshp>=2.3.1",
#   "shapely>=2.0",
# ]
# ///

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import shapefile
from pyproj import CRS, Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform as shapely_transform
from shapely.prepared import prep


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Delaware River Basin subset table for CAMELSH basins using the "
            "official DRBC basin boundary."
        )
    )
    parser.add_argument(
        "--drbc-shapefile",
        type=Path,
        default=Path("basins/drbc_boundary/drb_bnd_polygon.shp"),
        help="Path to the DRBC basin boundary polygon shapefile.",
    )
    parser.add_argument(
        "--camelsh-boundary-shapefile",
        type=Path,
        default=Path("basins/CAMELSH_data/shapefiles/CAMELSH_shapefile.shp"),
        help="Path to the CAMELSH GAGES-II basin boundary shapefile.",
    )
    parser.add_argument(
        "--camelsh-basin-id-csv",
        type=Path,
        default=Path("basins/CAMELSH_data/attributes/attributes_gageii_BasinID.csv"),
        help="Path to CAMELSH BasinID metadata CSV with outlet coordinates.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/basin/drbc_camelsh"),
        help="Directory where output tables will be written.",
    )
    parser.add_argument(
        "--min-overlap-ratio",
        type=float,
        default=0.0,
        help="Minimum basin overlap ratio required in addition to outlet_in_drbc.",
    )
    return parser.parse_args()


def read_single_polygon(shapefile_path: Path) -> tuple[dict, CRS]:
    reader = shapefile.Reader(str(shapefile_path))
    field_names = [field[0] for field in reader.fields[1:]]
    records = list(reader.records())
    shapes = list(reader.shapes())
    if len(records) != 1:
        raise ValueError(
            f"{shapefile_path} should contain exactly one polygon, found {len(records)}."
        )

    attrs = dict(zip(field_names, records[0]))
    geom = shape(shapes[0].__geo_interface__)
    crs = CRS.from_wkt(shapefile_path.with_suffix(".prj").read_text())
    return {"attributes": attrs, "geometry": geom}, crs


def load_camelsh_metadata(csv_path: Path) -> pd.DataFrame:
    metadata = pd.read_csv(csv_path, dtype={"STAID": str})
    metadata["LAT_GAGE"] = metadata["LAT_GAGE"].astype(float)
    metadata["LNG_GAGE"] = metadata["LNG_GAGE"].astype(float)
    metadata["DRAIN_SQKM"] = metadata["DRAIN_SQKM"].astype(float)
    return metadata


def load_camelsh_basins(
    shapefile_path: Path,
    area_transformer: Transformer,
) -> tuple[shapefile.Reader, list[str], str]:
    reader = shapefile.Reader(str(shapefile_path))
    field_names = [field[0] for field in reader.fields[1:]]

    gauge_field = None
    for candidate in ("GAGE_ID", "GAGEID", "STAID", "gage_id"):
        if candidate in field_names:
            gauge_field = candidate
            break
    if gauge_field is None:
        raise ValueError("CAMELSH shapefile에서 gauge ID 필드를 찾지 못했습니다.")
    return reader, field_names, gauge_field


def build_mapping(
    region_attrs: dict,
    region_geom_region_crs,
    region_geom_wgs84,
    region_geom_area_crs,
    region_crs: CRS,
    metadata: pd.DataFrame,
    basin_reader: shapefile.Reader,
    basin_field_names: list[str],
    basin_gauge_field: str,
    min_overlap_ratio: float,
) -> tuple[pd.DataFrame, dict]:
    outlet_transformer = Transformer.from_crs(4326, region_crs, always_xy=True)
    area_transformer = Transformer.from_crs(4326, 5070, always_xy=True)

    prepared_region = prep(region_geom_region_crs)
    region_area_sqkm = region_geom_area_crs.area / 1_000_000
    region_bbox_wgs84 = region_geom_wgs84.bounds

    rows_by_id: dict[str, dict] = {}

    for basin in metadata.itertuples(index=False):
        gauge_id = basin.STAID
        outlet_x, outlet_y = outlet_transformer.transform(basin.LNG_GAGE, basin.LAT_GAGE)
        outlet_point = Point(outlet_x, outlet_y)
        outlet_in_region = bool(prepared_region.covers(outlet_point))
        rows_by_id[gauge_id] = {
            "gauge_id": gauge_id,
            "gauge_name": basin.STANAME,
            "state": basin.STATE,
            "camelsh_huc02": basin.HUC02,
            "lat_gage": basin.LAT_GAGE,
            "lng_gage": basin.LNG_GAGE,
            "drain_sqkm_attr": basin.DRAIN_SQKM,
            "outlet_in_drbc": outlet_in_region,
            "basin_intersects_drbc": False,
            "basin_within_drbc": False,
            "basin_area_sqkm_geom": pd.NA,
            "overlap_area_sqkm": 0.0,
            "overlap_ratio_of_basin": 0.0,
            "selected": False,
            "selection_reason": "outside_drbc",
        }

    minx, miny, maxx, maxy = region_bbox_wgs84

    for record, shp in zip(basin_reader.iterRecords(), basin_reader.iterShapes()):
        attrs = dict(zip(basin_field_names, record))
        gauge_id = str(attrs[basin_gauge_field]).strip()
        if gauge_id not in rows_by_id:
            continue

        shape_minx, shape_miny, shape_maxx, shape_maxy = shp.bbox
        bbox_intersects = not (
            shape_maxx < minx
            or shape_minx > maxx
            or shape_maxy < miny
            or shape_miny > maxy
        )
        if not bbox_intersects and not rows_by_id[gauge_id]["outlet_in_drbc"]:
            continue

        geom_wgs84 = shape(shp.__geo_interface__)
        geom_area = shapely_transform(area_transformer.transform, geom_wgs84)
        basin_area_sqkm = geom_area.area / 1_000_000
        overlap_geom = geom_area.intersection(region_geom_area_crs)
        overlap_area_sqkm = overlap_geom.area / 1_000_000
        overlap_ratio_of_basin = overlap_area_sqkm / basin_area_sqkm if basin_area_sqkm else 0.0
        basin_intersects_region = overlap_area_sqkm > 0
        basin_within_region = bool(geom_area.within(region_geom_area_crs))

        rows_by_id[gauge_id].update(
            {
                "basin_intersects_drbc": basin_intersects_region,
                "basin_within_drbc": basin_within_region,
                "basin_area_sqkm_geom": round(basin_area_sqkm, 3),
                "overlap_area_sqkm": round(overlap_area_sqkm, 3),
                "overlap_ratio_of_basin": round(overlap_ratio_of_basin, 6),
            }
        )

    threshold_label = f"{min_overlap_ratio:.2f}"
    for row in rows_by_id.values():
        outlet_in_region = bool(row["outlet_in_drbc"])
        overlap_ratio = float(row["overlap_ratio_of_basin"])
        selected = outlet_in_region and overlap_ratio >= min_overlap_ratio
        if selected:
            reason = f"outlet_in_drbc_and_overlap_gte_{threshold_label}"
        elif outlet_in_region:
            reason = f"outlet_in_drbc_but_overlap_lt_{threshold_label}"
        else:
            reason = "outside_drbc"
        row["selected"] = selected
        row["selection_reason"] = reason

    mapping = pd.DataFrame(rows_by_id.values()).sort_values(
        ["selected", "outlet_in_drbc", "overlap_ratio_of_basin", "gauge_id"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)

    selected = mapping[mapping["selected"]].copy()
    outlet_only = mapping[mapping["outlet_in_drbc"]].copy()
    edge_cases = mapping[
        mapping["basin_intersects_drbc"] & ~mapping["outlet_in_drbc"]
    ].copy()

    summary = {
        "drbc_name": region_attrs.get("NAME", "Delaware River Basin"),
        "drbc_crs_epsg": region_crs.to_epsg(),
        "drbc_area_sqkm_geom": round(region_area_sqkm, 3),
        "min_overlap_ratio_for_selection": min_overlap_ratio,
        "camelsh_total_basins_evaluated": int(len(mapping)),
        "camelsh_outlet_in_drbc_count": int(len(outlet_only)),
        "camelsh_selected_count": int(len(selected)),
        "camelsh_intersect_only_count": int(len(edge_cases)),
        "camelsh_selected_mean_overlap_ratio": (
            round(float(selected["overlap_ratio_of_basin"].mean()), 6)
            if not selected.empty
            else 0.0
        ),
        "camelsh_selected_min_overlap_ratio": (
            round(float(selected["overlap_ratio_of_basin"].min()), 6)
            if not selected.empty
            else 0.0
        ),
    }
    return mapping, summary


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    region_record, region_crs = read_single_polygon(args.drbc_shapefile)
    area_crs = CRS.from_epsg(5070)
    region_to_wgs84 = Transformer.from_crs(region_crs, 4326, always_xy=True)
    region_to_area = Transformer.from_crs(region_crs, area_crs, always_xy=True)
    region_geom_wgs84 = shapely_transform(region_to_wgs84.transform, region_record["geometry"])
    region_geom_area_crs = shapely_transform(region_to_area.transform, region_record["geometry"])

    metadata = load_camelsh_metadata(args.camelsh_basin_id_csv)
    camelsh_to_area = Transformer.from_crs(4326, area_crs, always_xy=True)
    basin_reader, basin_field_names, basin_gauge_field = load_camelsh_basins(
        args.camelsh_boundary_shapefile,
        camelsh_to_area,
    )

    mapping, summary = build_mapping(
        region_record["attributes"],
        region_record["geometry"],
        region_geom_wgs84,
        region_geom_area_crs,
        region_crs,
        metadata,
        basin_reader,
        basin_field_names,
        basin_gauge_field,
        args.min_overlap_ratio,
    )

    selected = mapping[mapping["selected"]].copy()
    edge_cases = mapping[
        mapping["basin_intersects_drbc"] & ~mapping["outlet_in_drbc"]
    ].copy()

    mapping.to_csv(args.output_dir / "camelsh_drbc_mapping.csv", index=False)
    selected.to_csv(args.output_dir / "camelsh_drbc_selected.csv", index=False)
    edge_cases.to_csv(args.output_dir / "camelsh_drbc_intersect_only.csv", index=False)
    (args.output_dir / "camelsh_drbc_selected_ids.txt").write_text(
        "\n".join(selected["gauge_id"].tolist()) + ("\n" if not selected.empty else ""),
        encoding="utf-8",
    )
    (args.output_dir / "drbc_boundary_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print(
        f"DRBC selected CAMELSH basins (outlet_in_drbc + overlap>={args.min_overlap_ratio:.2f}): "
        f"{len(selected)}"
    )
    print(f"DRBC intersect-only CAMELSH basins: {len(edge_cases)}")
    print(f"Outputs written to: {args.output_dir}")


if __name__ == "__main__":
    main()
