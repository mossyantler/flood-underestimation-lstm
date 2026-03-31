#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString
from shapely.ops import nearest_points


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export CAMELSH basins and outlets matched to the hydrologic region defined "
            "from mostly-contained HUC10 polygons."
        )
    )
    parser.add_argument(
        "--defined-dir",
        type=Path,
        default=Path("output/basin/huc8_delware_camelsh/defined_from_mostly_huc10"),
        help="Directory containing defined_region.geojson and defined_huc8/10/12.geojson.",
    )
    parser.add_argument(
        "--camelsh-dir",
        type=Path,
        default=Path("tmp/camelsh"),
        help="Directory containing extracted CAMELSH files.",
    )
    parser.add_argument(
        "--camelsh-boundary-shapefile",
        type=Path,
        default=Path("tmp/camelsh/shapefiles/CAMELSH_shapefile_hydroATLAS.shp"),
        help="Path to the CAMELSH basin boundary shapefile used for overlay work.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/basin/huc8_delware_camelsh/camelsh_from_defined_region"),
        help="Directory where matched CAMELSH outputs will be written.",
    )
    parser.add_argument(
        "--min-overlap-ratio",
        type=float,
        default=0.9,
        help="Minimum basin-area overlap ratio with the defined region required to keep a CAMELSH basin.",
    )
    return parser.parse_args()


def load_camelsh_metadata(camelsh_dir: Path) -> pd.DataFrame:
    basin_id = pd.read_csv(
        camelsh_dir / "attributes" / "attributes_gageii_BasinID.csv",
        dtype={"STAID": str},
    )
    info = pd.read_csv(
        camelsh_dir / "info.csv",
        dtype={"STAID": str},
    ).rename(columns={"data_availability [hrs]": "data_availability_hours"})

    merged = basin_id.merge(info[["STAID", "data_availability_hours"]], on="STAID", how="left")
    merged["data_availability_hours"] = merged["data_availability_hours"].fillna(0).astype(int)
    merged["has_hourly_observations"] = merged["data_availability_hours"] > 0
    return merged


def prepare_camelsh_layers(
    camelsh_boundary_shapefile: Path,
    metadata: pd.DataFrame,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    basins = gpd.read_file(camelsh_boundary_shapefile)
    if basins.crs is None:
        basins = basins.set_crs("EPSG:4326")
    basins["GAGE_ID"] = basins["GAGE_ID"].astype(str)
    basins = basins.merge(metadata, how="left", left_on="GAGE_ID", right_on="STAID")

    outlet_df = metadata.copy()
    outlet_geometry = gpd.points_from_xy(outlet_df["LNG_GAGE"], outlet_df["LAT_GAGE"])
    outlets = gpd.GeoDataFrame(outlet_df, geometry=outlet_geometry, crs="EPSG:4326")
    return basins, outlets


def spatially_match_defined_hucs(
    outlets: gpd.GeoDataFrame,
    defined_huc8: gpd.GeoDataFrame,
    defined_huc10: gpd.GeoDataFrame,
    defined_huc12: gpd.GeoDataFrame,
) -> pd.DataFrame:
    matched_huc8 = gpd.sjoin(
        outlets[["STAID", "geometry"]],
        defined_huc8[["huc8", "name", "huc8_label", "geometry"]],
        how="left",
        predicate="within",
    ).drop(columns="index_right")
    matched_huc8 = matched_huc8.rename(
        columns={
            "huc8": "matched_huc8",
            "name": "matched_huc8_name",
            "huc8_label": "matched_huc8_label",
        }
    )

    matched_huc10 = gpd.sjoin(
        outlets[["STAID", "geometry"]],
        defined_huc10[["huc10", "name", "huc10_label", "geometry"]],
        how="left",
        predicate="within",
    ).drop(columns="index_right")
    matched_huc10 = matched_huc10.rename(
        columns={
            "huc10": "matched_huc10",
            "name": "matched_huc10_name",
            "huc10_label": "matched_huc10_label",
        }
    )

    matched_huc12 = gpd.sjoin(
        outlets[["STAID", "geometry"]],
        defined_huc12[["huc12", "name", "huc12_label", "geometry"]],
        how="left",
        predicate="within",
    ).drop(columns="index_right")
    matched_huc12 = matched_huc12.rename(
        columns={
            "huc12": "matched_huc12",
            "name": "matched_huc12_name",
            "huc12_label": "matched_huc12_label",
        }
    )

    matched = matched_huc8.merge(
        matched_huc10.drop(columns="geometry"),
        on="STAID",
        how="left",
    ).merge(
        matched_huc12.drop(columns="geometry"),
        on="STAID",
        how="left",
    )
    return pd.DataFrame(matched.drop(columns="geometry"))


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    defined_region = gpd.read_file(args.defined_dir / "defined_region.geojson")
    defined_huc8 = gpd.read_file(args.defined_dir / "defined_huc8.geojson")
    defined_huc10 = gpd.read_file(args.defined_dir / "defined_huc10.geojson")
    defined_huc12 = gpd.read_file(args.defined_dir / "defined_huc12.geojson")

    metadata = load_camelsh_metadata(args.camelsh_dir)
    basins, outlets = prepare_camelsh_layers(args.camelsh_boundary_shapefile, metadata)

    region_union = defined_region.union_all()
    outlets["outlet_in_defined_region"] = outlets.geometry.within(region_union)
    basins["basin_intersects_defined_region"] = basins.geometry.intersects(region_union)
    projected_region_union = defined_region.to_crs("EPSG:5070").union_all()
    projected_basins = basins.to_crs("EPSG:5070")
    basin_area = projected_basins.geometry.area
    overlap_area = projected_basins.geometry.intersection(projected_region_union).area
    basins["overlap_ratio_with_defined_region"] = overlap_area.where(
        basin_area > 0,
        0,
    ) / basin_area.where(basin_area > 0, 1)

    matched_table = spatially_match_defined_hucs(outlets, defined_huc8, defined_huc10, defined_huc12)
    outlets = outlets.merge(matched_table, on="STAID", how="left")
    basins = basins.merge(matched_table, left_on="GAGE_ID", right_on="STAID", how="left")

    # Keep only CAMELSH basins whose basin polygon mostly belongs to the defined region.
    selected_ids = sorted(
        set(
            basins.loc[
                basins["overlap_ratio_with_defined_region"] >= args.min_overlap_ratio,
                "GAGE_ID",
            ]
        )
    )

    selected_outlets = outlets[outlets["STAID"].isin(selected_ids)].copy()
    selected_basins = basins[basins["GAGE_ID"].isin(selected_ids)].copy()
    selected_outlets = selected_outlets.merge(
        selected_basins[["GAGE_ID", "overlap_ratio_with_defined_region"]].rename(
            columns={"GAGE_ID": "STAID"}
        ),
        on="STAID",
        how="left",
    )

    selected_outlets["selection_mode"] = f"overlap_ge_{args.min_overlap_ratio:.2f}"
    selected_basins = selected_basins.merge(
        selected_outlets[["STAID", "selection_mode", "outlet_in_defined_region"]],
        left_on="GAGE_ID",
        right_on="STAID",
        how="left",
    )
    if "STAID_x" in selected_basins.columns:
        selected_basins = selected_basins.rename(columns={"STAID_x": "STAID"})
    if "STAID_y" in selected_basins.columns:
        selected_basins = selected_basins.drop(columns=["STAID_y"])
    selected_basins = selected_basins.loc[:, ~selected_basins.columns.duplicated()].copy()

    pair_table = selected_basins[["GAGE_ID", "STANAME", "geometry"]].merge(
        selected_outlets[["STAID", "geometry"]],
        left_on="GAGE_ID",
        right_on="STAID",
        suffixes=("_basin", "_outlet"),
        how="inner",
    )
    basin_geom_proj = gpd.GeoSeries(pair_table["geometry_basin"], crs=selected_basins.crs).to_crs("EPSG:5070")
    outlet_geom_proj = gpd.GeoSeries(pair_table["geometry_outlet"], crs=selected_outlets.crs).to_crs("EPSG:5070")

    outlet_inside_flags = []
    outlet_distance_m = []
    link_geoms_proj = []
    for basin_geom, outlet_geom in zip(basin_geom_proj, outlet_geom_proj):
        inside = basin_geom.covers(outlet_geom)
        outlet_inside_flags.append(bool(inside))
        if inside:
            outlet_distance_m.append(0.0)
            link_geoms_proj.append(LineString([outlet_geom, outlet_geom]))
        else:
            _, nearest_on_basin = nearest_points(outlet_geom, basin_geom)
            outlet_distance_m.append(float(outlet_geom.distance(basin_geom)))
            link_geoms_proj.append(LineString([outlet_geom, nearest_on_basin]))

    pair_table["pair_id"] = pair_table["GAGE_ID"].astype(str)
    pair_table["pair_label"] = pair_table["GAGE_ID"].astype(str) + " " + pair_table["STANAME"].astype(str)
    pair_table["outlet_inside_own_basin"] = outlet_inside_flags
    pair_table["outlet_to_basin_distance_m"] = outlet_distance_m
    pair_links = gpd.GeoDataFrame(
        pair_table[["pair_id", "pair_label", "outlet_inside_own_basin", "outlet_to_basin_distance_m"]].copy(),
        geometry=gpd.GeoSeries(link_geoms_proj, crs="EPSG:5070").to_crs(selected_basins.crs),
        crs=selected_basins.crs,
    )

    pair_attrs = pair_table[["pair_id", "pair_label", "outlet_inside_own_basin", "outlet_to_basin_distance_m"]].copy()
    selected_outlets = selected_outlets.merge(
        pair_attrs.rename(columns={"pair_id": "STAID"}),
        on="STAID",
        how="left",
    )
    selected_basins = selected_basins.merge(
        pair_attrs.rename(columns={"pair_id": "GAGE_ID"}),
        on="GAGE_ID",
        how="left",
    )

    output_columns = [
        "STAID",
        "STANAME",
        "STATE",
        "DRAIN_SQKM",
        "LAT_GAGE",
        "LNG_GAGE",
        "data_availability_hours",
        "has_hourly_observations",
        "selection_mode",
        "outlet_in_defined_region",
        "overlap_ratio_with_defined_region",
        "pair_label",
        "outlet_inside_own_basin",
        "outlet_to_basin_distance_m",
        "matched_huc8",
        "matched_huc8_name",
        "matched_huc8_label",
        "matched_huc10",
        "matched_huc10_name",
        "matched_huc10_label",
        "matched_huc12",
        "matched_huc12_name",
        "matched_huc12_label",
    ]
    summary = (
        selected_outlets[output_columns]
        .sort_values(["selection_mode", "matched_huc10", "STAID"], na_position="last")
        .reset_index(drop=True)
    )

    summary.to_csv(args.output_dir / "camelsh_matches.csv", index=False)
    selected_outlets.to_file(args.output_dir / "camelsh_outlets.geojson", driver="GeoJSON")
    selected_basins.to_file(args.output_dir / "camelsh_basins.geojson", driver="GeoJSON")
    pair_links.to_file(args.output_dir / "camelsh_pair_links.geojson", driver="GeoJSON")

    print(
        "Matched CAMELSH basins with overlap ratio "
        f">= {args.min_overlap_ratio}: {len(selected_ids)}"
    )
    print(f"Outlet-in-defined-region: {int(selected_outlets['outlet_in_defined_region'].sum())}")
    print(
        "Basin-intersects-defined-region: "
        f"{int(selected_basins['basin_intersects_defined_region'].sum())}"
    )
    print(
        "Matched CAMELSH basins with hourly observations: "
        f"{int(selected_outlets['has_hourly_observations'].sum())}"
    )
    print(
        "Own outlet outside own basin polygons: "
        f"{int((~selected_outlets['outlet_inside_own_basin']).sum())}"
    )
    print(f"Wrote files to: {args.output_dir}")


if __name__ == "__main__":
    main()
