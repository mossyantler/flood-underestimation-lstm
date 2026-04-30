#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pandas>=2.2",
# ]
# ///

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


ATTRIBUTE_FILES = {
    "BasinID": "attributes_gageii_BasinID.csv",
    "Topo": "attributes_gageii_Topo.csv",
    "Climate": "attributes_nldas2_climate.csv",
    "Hydro": "attributes_gageii_Hydro.csv",
    "Soils": "attributes_gageii_Soils.csv",
    "Geology": "attributes_gageii_Geology.csv",
    "LandCover": "attributes_gageii_LC06_Basin.csv",
}

LAND_COVER_MAP = {
    "developed_open": "DEVOPENNLCD06",
    "developed_low": "DEVLOWNLCD06",
    "developed_medium": "DEVMEDNLCD06",
    "developed_high": "DEVHINLCD06",
    "barren": "BARRENNLCD06",
    "deciduous_forest": "DECIDNLCD06",
    "evergreen_forest": "EVERGRNLCD06",
    "mixed_forest": "MIXEDFORNLCD06",
    "shrub": "SHRUBNLCD06",
    "grass": "GRASSNLCD06",
    "pasture": "PASTURENLCD06",
    "crops": "CROPSNLCD06",
    "woody_wetland": "WOODYWETNLCD06",
    "emergent_wetland": "EMERGWETNLCD06",
    "water": "WATERNLCD06",
    "snow_ice": "SNOWICENLCD06",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a static basin analysis table for the DRBC-selected CAMELSH subset."
        )
    )
    parser.add_argument(
        "--selected-csv",
        type=Path,
        default=Path("output/basin/drbc/basin_define/camelsh_drbc_selected.csv"),
        help="Selected DRBC CAMELSH basin table.",
    )
    parser.add_argument(
        "--attributes-dir",
        type=Path,
        default=Path("basins/CAMELSH_data/attributes"),
        help="Directory containing CAMELSH attribute CSV files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/basin/drbc/analysis/basin_attributes"),
        help="Basin-attributes analysis root. Tables and metadata are written under this directory.",
    )
    return parser.parse_args()


def read_selected(path: Path) -> pd.DataFrame:
    selected = pd.read_csv(path, dtype={"gauge_id": str})
    return selected.sort_values("gauge_id").reset_index(drop=True)


def read_attribute_table(path: Path) -> pd.DataFrame:
    table = pd.read_csv(path, dtype={"STAID": str})
    table = table.rename(columns={"STAID": "gauge_id"})
    if table["gauge_id"].duplicated().any():
        raise ValueError(f"{path} contains duplicated gauge IDs.")
    return table


def merge_attributes(selected: pd.DataFrame, attributes_dir: Path) -> pd.DataFrame:
    merged = selected.copy()
    flags: dict[str, pd.Series] = {}
    for label, filename in ATTRIBUTE_FILES.items():
        table = read_attribute_table(attributes_dir / filename)
        merged = merged.merge(table, on="gauge_id", how="left", validate="one_to_one")
        flags[f"_has_{label.lower()}"] = merged["gauge_id"].isin(table["gauge_id"])
    if flags:
        merged = pd.concat([merged, pd.DataFrame(flags)], axis=1)
    return merged


def add_land_cover_derivatives(df: pd.DataFrame) -> pd.DataFrame:
    missing = [col for col in LAND_COVER_MAP.values() if col not in df.columns]
    if missing:
        raise ValueError(f"Land cover columns missing from merged table: {missing}")

    dom_col_names = list(LAND_COVER_MAP.values())
    dom_labels = pd.Series(LAND_COVER_MAP)
    dominant_col = df[dom_col_names].idxmax(axis=1)
    df["dom_land_cover"] = dominant_col.map(
        {value: key for key, value in LAND_COVER_MAP.items()}
    )
    df["dom_land_cover_pct"] = df[dom_col_names].max(axis=1)

    df["forest_pct"] = df["FORESTNLCD06"]
    df["forest_frac"] = df["FORESTNLCD06"] / 100.0
    df["developed_pct"] = df["DEVNLCD06"]
    df["developed_frac"] = df["DEVNLCD06"] / 100.0
    df["crops_pct"] = df["CROPSNLCD06"]
    df["wetland_pct"] = df["WOODYWETNLCD06"] + df["EMERGWETNLCD06"]
    return df


def build_analysis_table(df: pd.DataFrame) -> pd.DataFrame:
    df = add_land_cover_derivatives(df.copy())
    df["aridity"] = df["aridity_index"]
    df["elev_mean_m"] = df["ELEV_MEAN_M_BASIN"]
    df["slope_pct"] = df["SLOPE_PCT"]
    df["baseflow_index_pct"] = df["BFI_AVE"]
    df["stream_density_km_per_sqkm"] = df["STREAMS_KM_SQ_KM"]
    df["soil_permeability_index"] = df["PERMAVE"]
    df["soil_available_water_capacity"] = df["AWCAVE"]
    df["soil_water_table_depth_m"] = df["WTDEPAVE"]
    df["soil_rock_depth_cm"] = df["ROCKDEPAVE"]
    df["geology_dom_pct"] = df["GEOL_HUNT_DOM_PCT"]
    df["geology_dom_desc"] = df["GEOL_HUNT_DOM_DESC"]

    key_columns = [
        "gauge_id",
        "gauge_name",
        "state",
        "camelsh_huc02",
        "lat_gage",
        "lng_gage",
        "drain_sqkm_attr",
        "basin_area_sqkm_geom",
        "overlap_ratio_of_basin",
        "selection_reason",
        "forest_pct",
        "forest_frac",
        "developed_pct",
        "developed_frac",
        "crops_pct",
        "wetland_pct",
        "dom_land_cover",
        "dom_land_cover_pct",
        "p_mean",
        "pet_mean",
        "aridity",
        "p_seasonality",
        "frac_snow",
        "high_prec_freq",
        "high_prec_dur",
        "elev_mean_m",
        "slope_pct",
        "stream_density_km_per_sqkm",
        "baseflow_index_pct",
        "RUNAVE7100",
        "soil_available_water_capacity",
        "soil_permeability_index",
        "soil_water_table_depth_m",
        "soil_rock_depth_cm",
        "CLAYAVE",
        "SILTAVE",
        "SANDAVE",
        "geology_dom_desc",
        "geology_dom_pct",
    ]
    return df[key_columns].sort_values("gauge_id").reset_index(drop=True)


def build_summary(df: pd.DataFrame, analysis_df: pd.DataFrame) -> dict:
    return {
        "selected_basin_count": int(len(df)),
        "state_count": int(df["state"].nunique()),
        "mean_overlap_ratio": round(float(df["overlap_ratio_of_basin"].mean()), 6),
        "min_overlap_ratio": round(float(df["overlap_ratio_of_basin"].min()), 6),
        "mean_basin_area_sqkm_geom": round(float(df["basin_area_sqkm_geom"].mean()), 3),
        "median_basin_area_sqkm_geom": round(float(df["basin_area_sqkm_geom"].median()), 3),
        "mean_p_mean": round(float(analysis_df["p_mean"].mean()), 3),
        "mean_slope_pct": round(float(analysis_df["slope_pct"].mean()), 3),
        "mean_forest_pct": round(float(analysis_df["forest_pct"].mean()), 3),
        "mean_baseflow_index_pct": round(
            float(analysis_df["baseflow_index_pct"].mean()), 3
        ),
    }


def main() -> None:
    args = parse_args()
    table_dir = args.output_dir / "tables"
    metadata_dir = args.output_dir / "metadata"
    table_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    selected = read_selected(args.selected_csv)
    merged = merge_attributes(selected, args.attributes_dir)
    analysis = build_analysis_table(merged)
    summary = build_summary(merged, analysis)

    merged_path = table_dir / "drbc_selected_static_attributes_full.csv"
    analysis_path = table_dir / "drbc_selected_basin_analysis_table.csv"
    summary_path = metadata_dir / "drbc_selected_basin_analysis_summary.json"

    merged.to_csv(merged_path, index=False)
    analysis.to_csv(analysis_path, index=False)
    summary_path.write_text(json.dumps(summary, indent=2))

    print(f"Wrote merged attributes: {merged_path}")
    print(f"Wrote basin analysis table: {analysis_path}")
    print(f"Wrote summary: {summary_path}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
