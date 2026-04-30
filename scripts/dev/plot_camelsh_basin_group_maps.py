#!/usr/bin/env python3
# /// script
# dependencies = [
#   "geopandas>=0.14",
#   "matplotlib>=3.8",
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "pyogrio>=0.7",
# ]
# ///

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DEFAULT_BASIN_SHAPEFILE = Path("basins/CAMELSH_data/shapefiles/CAMELSH_shapefile.shp")
DEFAULT_STATE_SHAPEFILE = Path("basins/us_boundaries/tl_2024_us_state/tl_2024_us_state.shp")
DEFAULT_ML_BASIN_CSV = Path(
    "output/basin/all/analysis/event_regime/tables/selected_variant_basin_cluster_composition.csv"
)
DEFAULT_RULE_BASIN_CSV = Path("output/basin/all/analysis/flood_generation/tables/flood_generation_basin_summary.csv")
DEFAULT_EVENT_BASIN_CSV = Path("output/basin/all/analysis/event_response/tables/event_response_basin_summary.csv")
DEFAULT_OUTPUT_DIR = Path("output/basin/all/analysis/event_regime/figures")
DEFAULT_TABLE_DIR = Path("output/basin/all/analysis/event_regime/tables")

CLUSTER_LABELS = {
    0: "Antecedent / multi-day rain",
    1: "Weak-driver / snow-influenced",
    2: "Recent rainfall",
}
CLUSTER_COLORS = {
    0: "#3f6fb5",
    1: "#8f5ca8",
    2: "#d78a2a",
}
RULE_COLORS = {
    "recent_precipitation": "#d78a2a",
    "antecedent_precipitation": "#3f6fb5",
    "snowmelt_or_rain_on_snow": "#8f5ca8",
    "uncertain_high_flow_candidate": "#777777",
    "mixture": "#b8b8b8",
}
HUC02_NAMES = {
    "01": "New England",
    "02": "Mid-Atlantic",
    "03": "South Atlantic-Gulf",
    "04": "Great Lakes",
    "05": "Ohio",
    "06": "Tennessee",
    "07": "Upper Mississippi",
    "08": "Lower Mississippi",
    "09": "Souris-Red-Rainy",
    "10": "Missouri",
    "10U": "Upper Missouri",
    "10L": "Lower Missouri",
    "11": "Arkansas-White-Red",
    "12": "Texas-Gulf",
    "13": "Rio Grande",
    "14": "Upper Colorado",
    "15": "Lower Colorado",
    "16": "Great Basin",
    "17": "Pacific Northwest",
    "18": "California",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot CAMELSH basin group maps for ML and rule-based labels.")
    parser.add_argument("--basin-shapefile", type=Path, default=DEFAULT_BASIN_SHAPEFILE)
    parser.add_argument("--state-shapefile", type=Path, default=DEFAULT_STATE_SHAPEFILE)
    parser.add_argument("--ml-basin-csv", type=Path, default=DEFAULT_ML_BASIN_CSV)
    parser.add_argument("--rule-basin-csv", type=Path, default=DEFAULT_RULE_BASIN_CSV)
    parser.add_argument("--event-basin-csv", type=Path, default=DEFAULT_EVENT_BASIN_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--table-dir", type=Path, default=DEFAULT_TABLE_DIR)
    parser.add_argument("--dominance-threshold", type=float, default=0.6)
    return parser.parse_args()


def normalize_gauge_id(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(8)


def normalize_huc02(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    if text.isdigit():
        return text.zfill(2)
    return text.upper()


def read_state_layer(path: Path) -> gpd.GeoDataFrame:
    states = gpd.read_file(path)
    states = states[~states["STUSPS"].isin(["AK", "HI", "PR", "GU", "VI", "MP", "AS"])].copy()
    states = states.to_crs("EPSG:4326")
    return states


def read_basin_layer(path: Path) -> gpd.GeoDataFrame:
    basins = gpd.read_file(path)
    basins["gauge_id"] = basins["GAGE_ID"].map(normalize_gauge_id)
    if basins.crs is None:
        basins = basins.set_crs("EPSG:4326")
    else:
        basins = basins.to_crs("EPSG:4326")
    return basins[["gauge_id", "geometry"]]


def read_ml_table(path: Path, threshold: float) -> pd.DataFrame:
    ml = pd.read_csv(path, dtype={"gauge_id": str})
    ml["gauge_id"] = ml["gauge_id"].map(normalize_gauge_id)
    if "top1_cluster" not in ml.columns:
        share_cols = [col for col in ml.columns if col.startswith("cluster_") and col.endswith("_share")]
        if not share_cols:
            raise SystemExit(f"No cluster share columns found in {path}")
        cluster_ids = [int(col.removeprefix("cluster_").removesuffix("_share")) for col in share_cols]
        shares = ml[share_cols].to_numpy()
        ml["top1_cluster"] = [cluster_ids[index] for index in shares.argmax(axis=1)]
    ml["top1_cluster"] = pd.to_numeric(ml["top1_cluster"], errors="coerce").astype("Int64")
    ml["ml_dominant_label"] = ml["top1_cluster"].map(CLUSTER_LABELS)
    ml["ml_map_label"] = np.where(
        ml["top1_share"] >= threshold,
        ml["ml_dominant_label"],
        ml["ml_dominant_label"] + " (mixed)",
    )
    return ml


def read_rule_table(path: Path) -> pd.DataFrame:
    rule = pd.read_csv(path, dtype={"gauge_id": str})
    rule["gauge_id"] = rule["gauge_id"].map(normalize_gauge_id)
    return rule


def add_metadata(table: pd.DataFrame, event_basin_csv: Path) -> pd.DataFrame:
    if not event_basin_csv.exists():
        return table
    meta = pd.read_csv(event_basin_csv, dtype={"gauge_id": str})
    meta["gauge_id"] = meta["gauge_id"].map(normalize_gauge_id)
    keep = [
        col
        for col in ["gauge_id", "gauge_name", "state", "huc02", "drain_sqkm_attr", "event_count"]
        if col in meta.columns
    ]
    merged = table.merge(meta[keep], on="gauge_id", how="left", suffixes=("", "_event"))
    if "huc02" in merged.columns:
        merged["huc02"] = merged["huc02"].map(normalize_huc02)
    return merged


def legend_handles(color_map: dict[str | int, str], labels: dict[int, str] | None = None) -> list[mpatches.Patch]:
    if labels:
        return [mpatches.Patch(facecolor=color_map[key], label=labels[key]) for key in labels]
    return [mpatches.Patch(facecolor=color, label=str(label)) for label, color in color_map.items()]


def plot_ml_map(states: gpd.GeoDataFrame, basins: gpd.GeoDataFrame, path: Path, threshold: float) -> None:
    fig, ax = plt.subplots(figsize=(13, 7.5))
    states.plot(ax=ax, facecolor="#f6f6f3", edgecolor="#c8c8c8", linewidth=0.45)
    for cluster, label in CLUSTER_LABELS.items():
        strong = basins[(basins["top1_cluster"] == cluster) & (basins["top1_share"] >= threshold)]
        weak = basins[(basins["top1_cluster"] == cluster) & (basins["top1_share"] < threshold)]
        if not weak.empty:
            weak.plot(ax=ax, color=CLUSTER_COLORS[cluster], alpha=0.28, linewidth=0)
        if not strong.empty:
            strong.plot(ax=ax, color=CLUSTER_COLORS[cluster], alpha=0.78, linewidth=0)
    ax.set_xlim(-125.5, -66.0)
    ax.set_ylim(24.0, 50.0)
    ax.set_axis_off()
    ax.set_title("CAMELSH Basins by Improved ML Event-Regime Composition", pad=16)
    handles = legend_handles(CLUSTER_COLORS, CLUSTER_LABELS)
    handles.append(mpatches.Patch(facecolor="#888888", alpha=0.28, label=f"Mixed top-1 < {threshold:.1f}"))
    ax.legend(handles=handles, frameon=True, loc="lower left", fontsize=10)
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=240, bbox_inches="tight")
    plt.close()


def plot_rule_map(states: gpd.GeoDataFrame, basins: gpd.GeoDataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(13, 7.5))
    states.plot(ax=ax, facecolor="#f6f6f3", edgecolor="#c8c8c8", linewidth=0.45)
    for label, color in RULE_COLORS.items():
        subset = basins[basins["dominant_flood_generation_type"] == label]
        if not subset.empty:
            subset.plot(ax=ax, color=color, alpha=0.76, linewidth=0)
    ax.set_xlim(-125.5, -66.0)
    ax.set_ylim(24.0, 50.0)
    ax.set_axis_off()
    ax.set_title("CAMELSH Basins by Rule-Based Dominant Flood-Generation Type", pad=16)
    ax.legend(handles=legend_handles(RULE_COLORS), frameon=True, loc="lower left", fontsize=9)
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=240, bbox_inches="tight")
    plt.close()


def plot_side_by_side(states: gpd.GeoDataFrame, basins: gpd.GeoDataFrame, path: Path, threshold: float) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(16, 6.2))
    for ax in axes:
        states.plot(ax=ax, facecolor="#f6f6f3", edgecolor="#d0d0d0", linewidth=0.35)
        ax.set_xlim(-125.5, -66.0)
        ax.set_ylim(24.0, 50.0)
        ax.set_axis_off()

    for cluster in CLUSTER_LABELS:
        strong = basins[(basins["top1_cluster"] == cluster) & (basins["top1_share"] >= threshold)]
        weak = basins[(basins["top1_cluster"] == cluster) & (basins["top1_share"] < threshold)]
        if not weak.empty:
            weak.plot(ax=axes[0], color=CLUSTER_COLORS[cluster], alpha=0.26, linewidth=0)
        if not strong.empty:
            strong.plot(ax=axes[0], color=CLUSTER_COLORS[cluster], alpha=0.8, linewidth=0)
    for label, color in RULE_COLORS.items():
        subset = basins[basins["dominant_flood_generation_type"] == label]
        if not subset.empty:
            subset.plot(ax=axes[1], color=color, alpha=0.78, linewidth=0)

    axes[0].set_title("Improved ML event-regime top cluster")
    axes[1].set_title("Rule-based dominant type")
    axes[0].legend(handles=legend_handles(CLUSTER_COLORS, CLUSTER_LABELS), frameon=True, loc="lower left", fontsize=8)
    axes[1].legend(handles=legend_handles(RULE_COLORS), frameon=True, loc="lower left", fontsize=8)
    fig.suptitle("CAMELSH Basin Grouping Comparison Across the Contiguous U.S.", y=0.98)
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=240, bbox_inches="tight")
    plt.close()


def write_summary_tables(merged: gpd.GeoDataFrame, table_dir: Path, threshold: float) -> None:
    plain = pd.DataFrame(merged.drop(columns="geometry"))
    plain["huc02_name"] = plain["huc02"].map(HUC02_NAMES) if "huc02" in plain.columns else pd.NA
    plain.to_csv(table_dir / "selected_variant_basin_map_labels.csv", index=False)

    if "huc02" in plain.columns:
        rows: list[dict[str, Any]] = []
        for huc02, group in plain.groupby("huc02", dropna=False):
            ml_counts = group["ml_dominant_label"].value_counts(normalize=True)
            rule_counts = group["dominant_flood_generation_type"].value_counts(normalize=True)
            rows.append(
                {
                    "huc02": huc02,
                    "huc02_name": HUC02_NAMES.get(str(huc02).zfill(2), ""),
                    "basin_count": int(len(group)),
                    "ml_top_label": ml_counts.index[0] if len(ml_counts) else pd.NA,
                    "ml_top_label_share": float(ml_counts.iloc[0]) if len(ml_counts) else pd.NA,
                    "ml_top1_ge_threshold_share": float((group["top1_share"] >= threshold).mean()),
                    "ml_top2_ge_0_8_share": float((group["top2_share"] >= 0.8).mean()),
                    "rule_top_label": rule_counts.index[0] if len(rule_counts) else pd.NA,
                    "rule_top_label_share": float(rule_counts.iloc[0]) if len(rule_counts) else pd.NA,
                    "recent_rainfall_share": float((group["ml_dominant_label"] == CLUSTER_LABELS[2]).mean()),
                    "antecedent_multiday_share": float((group["ml_dominant_label"] == CLUSTER_LABELS[0]).mean()),
                    "weak_snow_influenced_share": float((group["ml_dominant_label"] == CLUSTER_LABELS[1]).mean()),
                }
            )
        pd.DataFrame(rows).sort_values("huc02").to_csv(
            table_dir / "selected_variant_huc02_regional_summary.csv",
            index=False,
        )


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.table_dir.mkdir(parents=True, exist_ok=True)

    states = read_state_layer(args.state_shapefile)
    basin_shapes = read_basin_layer(args.basin_shapefile)
    ml = read_ml_table(args.ml_basin_csv, args.dominance_threshold)
    rule = read_rule_table(args.rule_basin_csv)
    ml = add_metadata(ml, args.event_basin_csv)

    merged = basin_shapes.merge(ml, on="gauge_id", how="inner")
    merged = merged.merge(
        rule[["gauge_id", "dominant_flood_generation_type", "dominant_type_share"]],
        on="gauge_id",
        how="left",
    )
    if "huc02" not in merged.columns:
        merged["huc02"] = merged["gauge_id"].str[:2]
    else:
        merged["huc02"] = merged["huc02"].map(normalize_huc02)

    plot_ml_map(
        states,
        merged,
        args.output_dir / "us_map_improved_ml_dominant_basins.png",
        args.dominance_threshold,
    )
    plot_rule_map(states, merged, args.output_dir / "us_map_rule_based_dominant_basins.png")
    plot_side_by_side(
        states,
        merged,
        args.output_dir / "us_map_ml_vs_rule_side_by_side.png",
        args.dominance_threshold,
    )
    write_summary_tables(merged, args.table_dir, args.dominance_threshold)

    print(f"Wrote ML map: {args.output_dir / 'us_map_improved_ml_dominant_basins.png'}")
    print(f"Wrote rule map: {args.output_dir / 'us_map_rule_based_dominant_basins.png'}")
    print(f"Wrote side-by-side map: {args.output_dir / 'us_map_ml_vs_rule_side_by_side.png'}")
    print(f"Wrote basin labels: {args.table_dir / 'selected_variant_basin_map_labels.csv'}")
    print(f"Wrote HUC02 summary: {args.table_dir / 'selected_variant_huc02_regional_summary.csv'}")


if __name__ == "__main__":
    main()
