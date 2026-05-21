#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "pyproj>=3.6",
#   "pyshp>=2.3",
#   "shapely>=2.0",
# ]
# ///
"""Export a compact confirmed-flood snapshot for the React dashboard."""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyproj
import shapefile
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, shape as shapely_shape
from shapely.ops import transform as transform_geometry
from shapely.ops import unary_union
from shapely.validation import make_valid


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PERF_CSV = ROOT / "output/model_analysis/expanded/confirmed_flood/performance/drbc_confirmed_flood_performance.csv"
DEFAULT_EVENT_WINDOWS = ROOT / "output/model_analysis/expanded/confirmed_flood/inference/confirmed_flood_event_windows_used.csv"
DEFAULT_CATALOG_CSV = ROOT / "output/model_analysis/expanded/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv"
DEFAULT_COVERAGE_CSV = ROOT / "output/model_analysis/expanded/confirmed_flood/coverage/nws_flood_stage_coverage.csv"
DEFAULT_DRBC_SELECTED = ROOT / "output/basin/drbc/basin_define/camelsh_drbc_selected.csv"
DEFAULT_STATIC_ATTRIBUTES = ROOT / "data/CAMELSH_generic/drbc_holdout_confirmed_flood_events/attributes/static_attributes.csv"
DEFAULT_SCREENING = ROOT / "output/basin/drbc/screening/drbc_screening_priority_broad.csv"
DEFAULT_CAMELSH_SHAPEFILE = ROOT / "basins/CAMELSH_data/shapefiles/CAMELSH_shapefile.shp"
DEFAULT_DRBC_BOUNDARY = ROOT / "basins/drbc_boundary/drb_bnd_polygon.shp"
DEFAULT_OUTPUT_TS = ROOT / "dashboard/lib/confirmed-flood-data.ts"

TIER_ORDER = ["minor", "moderate", "major"]
PERIOD_ORDER = ["pre_2000", "post_2013"]
QUANTILE_ORDER = ["det", "q50", "q90", "q95", "q99"]
MAP_CRS = "EPSG:5070"
BASIN_FALLBACK_CRS = "EPSG:4326"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--perf-csv", type=Path, default=DEFAULT_PERF_CSV)
    parser.add_argument("--event-windows", type=Path, default=DEFAULT_EVENT_WINDOWS)
    parser.add_argument("--catalog-csv", type=Path, default=DEFAULT_CATALOG_CSV)
    parser.add_argument("--coverage-csv", type=Path, default=DEFAULT_COVERAGE_CSV)
    parser.add_argument("--drbc-selected", type=Path, default=DEFAULT_DRBC_SELECTED)
    parser.add_argument("--static-attributes", type=Path, default=DEFAULT_STATIC_ATTRIBUTES)
    parser.add_argument("--screening-csv", type=Path, default=DEFAULT_SCREENING)
    parser.add_argument("--camelsh-shapefile", type=Path, default=DEFAULT_CAMELSH_SHAPEFILE)
    parser.add_argument("--drbc-boundary", type=Path, default=DEFAULT_DRBC_BOUNDARY)
    parser.add_argument("--svg-width", type=float, default=420)
    parser.add_argument("--svg-height", type=float, default=760)
    parser.add_argument(
        "--simplify-m",
        type=float,
        default=350.0,
        help="Topology-preserving simplification tolerance in projected meters for dashboard SVG paths.",
    )
    parser.add_argument("--output-ts", type=Path, default=DEFAULT_OUTPUT_TS)
    return parser.parse_args()


def normalize_gauge_id(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    if re.fullmatch(r"\d+", text) and len(text) < 8:
        text = text.zfill(8)
    return text


def event_key(usgs_id: Any, peak_time: Any) -> str:
    ts = pd.to_datetime(peak_time)
    return f"{normalize_gauge_id(usgs_id)}_{ts.strftime('%Y%m%dT%H%M%S')}"


def iso_hour(value: Any) -> str:
    return pd.to_datetime(value).strftime("%Y-%m-%dT%H:%M")


def finite_or_none(value: Any, digits: int | None = None) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    if digits is not None:
        return round(out, digits)
    return out


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def parse_noaa_types(annotation: Any) -> list[str]:
    if annotation is None or pd.isna(annotation):
        return []
    text = str(annotation).strip()
    if not text or text == "-":
        return []
    types: list[str] = []
    for part in text.split(";"):
        name = part.strip().split("#", 1)[0].strip()
        if name and name not in types:
            types.append(name)
    return types


def noaa_type_label(types: list[str]) -> str:
    if not types:
        return "No NOAA"
    if len(types) == 1:
        return types[0]
    return "Mixed NOAA"


def performance_type(m1_under: float | None, q99_under: float | None, reduction: float | None) -> str:
    if m1_under is None or q99_under is None or reduction is None:
        return "unknown"
    if q99_under < 0 and m1_under > 0:
        return "q99_over_prediction"
    if reduction > 0:
        return "q99_reduced_under"
    if m1_under <= 0:
        return "m1_not_under"
    return "q99_not_improved"


def performance_label(key: str) -> str:
    return {
        "q99_reduced_under": "q99 reduced underestimation",
        "q99_over_prediction": "q99 crossed to over-prediction",
        "q99_not_improved": "q99 did not reduce underestimation",
        "m1_not_under": "Model 1 already not under",
        "unknown": "unknown",
    }.get(key, key)


def basin_type(row: pd.Series) -> str:
    tags: list[str] = []
    if boolish(row.get("snow_influenced_tag")) or (finite_or_none(row.get("snow_fraction")) or 0) >= 0.1:
        tags.append("snow")
    if boolish(row.get("steep_fast_response_tag")) or (finite_or_none(row.get("slope")) or 0) >= 10:
        tags.append("steep")
    if boolish(row.get("coastal_or_hydromod_risk_tag")) or boolish(row.get("hydromod_risk")):
        tags.append("hydromod")
    forest = finite_or_none(row.get("forest_fraction"))
    if forest is not None and forest >= 0.65:
        tags.append("forested")
    return " / ".join(tags[:3]) if tags else "mixed"


def ordered_count(records: pd.Series, order: list[str] | None = None) -> dict[str, int]:
    counts = records.value_counts(dropna=False).to_dict()
    output: dict[str, int] = {}
    if order:
        for key in order:
            if key in counts:
                output[key] = int(counts.pop(key))
    for key in sorted(counts):
        output[str(key)] = int(counts[key])
    return output


def group_summary(events: pd.DataFrame, group_col: str, order: list[str] | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, grp in events.groupby(group_col, dropna=False):
        rows.append({
            "key": str(key),
            "label": performance_label(str(key)) if group_col == "performanceType" else str(key),
            "events": int(len(grp)),
            "basins": int(grp["usgsId"].nunique()),
            "noaaRate": finite_or_none(grp["noaaCorroborated"].mean() * 100, 1),
            "medianM1Under": finite_or_none(grp["m1Under"].median(), 3),
            "medianQ99Under": finite_or_none(grp["q99Under"].median(), 3),
            "medianQ99Reduction": finite_or_none(grp["q99Reduction"].median(), 3),
            "q99UnderRate": finite_or_none((grp["q99Under"] > 0).mean() * 100, 1),
        })
    if order:
        index = {key: idx for idx, key in enumerate(order)}
        rows = [
            row
            for _, row in sorted(
                enumerate(rows),
                key=lambda item: (index.get(item[1]["key"], len(index)), item[0]),
            )
        ]
    else:
        rows.sort(key=lambda row: (-row["events"], row["label"]))
    return rows


def model_quantile_summary(perf: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for (model, quantile), grp in perf.groupby(["model", "quantile"]):
        key = f"{model}_{quantile}"
        label = "Model 1 det" if key == "model1_det" else f"Model 2 {quantile}"
        rows.append({
            "key": key,
            "label": label,
            "model": model,
            "quantile": quantile,
            "rows": int(len(grp)),
            "events": int(grp["event_id"].nunique()),
            "basins": int(grp["usgs_id"].nunique()),
            "underRate": finite_or_none((grp["peak_under_deficit"] > 0).mean() * 100, 1),
            "medianUnder": finite_or_none(grp["peak_under_deficit"].median(), 3),
            "medianNrmse": finite_or_none(grp["event_nrmse"].median(), 3),
        })
    order = {("model1", "det"): 0, **{("model2", q): i for i, q in enumerate(QUANTILE_ORDER[1:], 1)}}
    rows.sort(key=lambda row: order.get((row["model"], row["quantile"]), 99))
    return rows


def read_optional_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, **kwargs)


def get_field_names(reader: shapefile.Reader) -> list[str]:
    return [field[0] for field in reader.fields[1:]]


def read_shapefile_crs(path: Path, fallback: str) -> pyproj.CRS:
    prj_path = path.with_suffix(".prj")
    if prj_path.exists():
        try:
            return pyproj.CRS.from_wkt(prj_path.read_text(encoding="utf-8"))
        except pyproj.exceptions.CRSError as exc:
            raise RuntimeError(f"Could not parse CRS from {prj_path}") from exc
    return pyproj.CRS.from_user_input(fallback)


def polygonal_rings(geometry: Any) -> list[list[tuple[float, float]]]:
    if geometry.is_empty:
        return []
    rings: list[list[tuple[float, float]]] = []
    if isinstance(geometry, Polygon):
        rings.append([(float(x), float(y)) for x, y in geometry.exterior.coords])
        for interior in geometry.interiors:
            rings.append([(float(x), float(y)) for x, y in interior.coords])
    elif isinstance(geometry, MultiPolygon):
        for polygon in geometry.geoms:
            rings.extend(polygonal_rings(polygon))
    elif isinstance(geometry, GeometryCollection):
        for geom in geometry.geoms:
            rings.extend(polygonal_rings(geom))
    return [ring for ring in rings if len(ring) >= 3]


def simplify_geometry(geometry: Any, tolerance_m: float) -> Any:
    if tolerance_m <= 0:
        return geometry
    return make_valid(geometry.simplify(tolerance_m, preserve_topology=True))


def load_boundary_geometry(boundary_path: Path, simplify_m: float) -> tuple[Any, list[list[tuple[float, float]]]]:
    reader = shapefile.Reader(str(boundary_path))
    source_crs = read_shapefile_crs(boundary_path, fallback=MAP_CRS)
    to_map_crs = pyproj.Transformer.from_crs(source_crs, MAP_CRS, always_xy=True).transform
    geometries = [
        make_valid(transform_geometry(to_map_crs, make_valid(shapely_shape(shape.__geo_interface__))))
        for shape in reader.shapes()
    ]
    if not geometries:
        raise RuntimeError(f"No DRBC boundary geometry found in {boundary_path}")
    boundary = simplify_geometry(make_valid(unary_union(geometries)), simplify_m)
    rings = polygonal_rings(boundary)
    if not rings:
        raise RuntimeError(f"No polygon rings found in DRBC boundary {boundary_path}")
    return boundary, rings


def load_basin_rings(
    shapefile_path: Path,
    gauge_ids: set[str],
    clip_geometry: Any,
    simplify_m: float,
) -> dict[str, list[list[tuple[float, float]]]]:
    reader = shapefile.Reader(str(shapefile_path))
    field_names = get_field_names(reader)
    try:
        gauge_idx = field_names.index("GAGE_ID")
    except ValueError as exc:
        raise RuntimeError(f"GAGE_ID field not found in {shapefile_path}") from exc

    source_crs = read_shapefile_crs(shapefile_path, fallback=BASIN_FALLBACK_CRS)
    to_map_crs = pyproj.Transformer.from_crs(source_crs, MAP_CRS, always_xy=True).transform
    geometries: dict[str, list[list[tuple[float, float]]]] = {}
    for shape_record in reader.iterShapeRecords():
        gauge_id = normalize_gauge_id(shape_record.record[gauge_idx])
        if gauge_id not in gauge_ids:
            continue
        raw_geometry = make_valid(shapely_shape(shape_record.shape.__geo_interface__))
        projected_geometry = make_valid(transform_geometry(to_map_crs, raw_geometry))
        clipped_geometry = make_valid(projected_geometry.intersection(clip_geometry))
        display_geometry = clipped_geometry if not clipped_geometry.is_empty else projected_geometry
        rings = polygonal_rings(simplify_geometry(display_geometry, simplify_m))
        if not rings:
            rings = polygonal_rings(display_geometry)
        geometries[gauge_id] = rings
        if len(geometries) == len(gauge_ids):
            break

    missing = sorted(gauge_ids - set(geometries))
    if missing:
        raise RuntimeError(f"Missing CAMELSH basin geometry for {', '.join(missing[:10])}")
    return geometries


def ring_area(ring: list[tuple[float, float]]) -> float:
    if len(ring) < 3:
        return 0.0
    points = ring if ring[0] == ring[-1] else [*ring, ring[0]]
    area = 0.0
    for (x1, y1), (x2, y2) in zip(points[:-1], points[1:]):
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def rings_area(rings: list[list[tuple[float, float]]]) -> float:
    return sum(ring_area(ring) for ring in rings)


class SvgProjector:
    def __init__(
        self,
        rings: list[list[tuple[float, float]]],
        width: float,
        height: float,
    ) -> None:
        x_values = [x for ring in rings for x, _y in ring]
        y_values = [y for ring in rings for _x, y in ring]
        x_min, x_max = min(x_values), max(x_values)
        y_min, y_max = min(y_values), max(y_values)
        x_pad = max(2_000.0, (x_max - x_min) * 0.04)
        y_pad = max(2_000.0, (y_max - y_min) * 0.04)
        self.x_min = x_min - x_pad
        self.x_max = x_max + x_pad
        self.y_min = y_min - y_pad
        self.y_max = y_max + y_pad
        self.width = width
        self.height = height
        map_width = self.x_max - self.x_min
        map_height = self.y_max - self.y_min
        self.scale = min(width / map_width, height / map_height)
        self.offset_x = (width - map_width * self.scale) / 2.0
        self.offset_y = (height - map_height * self.scale) / 2.0

    def project(self, point: tuple[float, float]) -> tuple[float, float]:
        map_x, map_y = point
        x = self.offset_x + (map_x - self.x_min) * self.scale
        y = self.offset_y + (self.y_max - map_y) * self.scale
        return x, y


def ring_to_path(ring: list[tuple[float, float]], projector: SvgProjector) -> str:
    projected = [projector.project(point) for point in ring]
    if len(projected) >= 2 and projected[0] == projected[-1]:
        projected = projected[:-1]
    if len(projected) < 3:
        return ""
    first_x, first_y = projected[0]
    commands = " ".join(f"L {x:.1f} {y:.1f}" for x, y in projected[1:])
    return f"M {first_x:.1f} {first_y:.1f} {commands} Z"


def rings_to_path(rings: list[list[tuple[float, float]]], projector: SvgProjector) -> str:
    return " ".join(path for path in (ring_to_path(ring, projector) for ring in rings) if path)


def build_map_geometry(args: argparse.Namespace, events: pd.DataFrame) -> tuple[dict[str, Any], dict[str, dict[str, float]]]:
    gauge_ids = set(events["usgs_id"].dropna().map(normalize_gauge_id))
    boundary_geometry, boundary_rings = load_boundary_geometry(args.drbc_boundary, args.simplify_m)
    basin_rings = load_basin_rings(
        args.camelsh_shapefile,
        gauge_ids,
        clip_geometry=boundary_geometry,
        simplify_m=args.simplify_m,
    )
    all_rings = boundary_rings + [ring for rings in basin_rings.values() for ring in rings]
    projector = SvgProjector(all_rings, width=args.svg_width, height=args.svg_height)
    boundary_path = rings_to_path(boundary_rings, projector)

    basin_paths = []
    for gauge_id in sorted(gauge_ids, key=lambda item: (-rings_area(basin_rings[item]), item)):
        basin_paths.append({
            "usgsId": gauge_id,
            "path": rings_to_path(basin_rings[gauge_id], projector),
            "areaRankValue": round(rings_area(basin_rings[gauge_id]), 3),
        })

    to_map_crs = pyproj.Transformer.from_crs("EPSG:4326", MAP_CRS, always_xy=True).transform
    point_by_id: dict[str, dict[str, float]] = {}
    for row in events.drop_duplicates("usgs_id").itertuples(index=False):
        lon = finite_or_none(getattr(row, "lng_gage", None))
        lat = finite_or_none(getattr(row, "lat_gage", None))
        if lon is None or lat is None:
            continue
        x_map, y_map = to_map_crs(lon, lat)
        x_svg, y_svg = projector.project((x_map, y_map))
        point_by_id[row.usgs_id] = {"x": round(x_svg, 2), "y": round(y_svg, 2)}

    map_geometry = {
        "viewBoxWidth": int(args.svg_width),
        "viewBoxHeight": int(args.svg_height),
        "boundaryPath": boundary_path,
        "basinPaths": basin_paths,
        "sourceCrs": {
            "map": MAP_CRS,
            "basins": BASIN_FALLBACK_CRS,
        },
    }
    return map_geometry, point_by_id


def build_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    perf = pd.read_csv(args.perf_csv, dtype={"usgs_id": str})
    perf["usgs_id"] = perf["usgs_id"].map(normalize_gauge_id)
    perf["event_id"] = [event_key(g, t) for g, t in zip(perf["usgs_id"], perf["peak_time"])]
    for col in ["obs_peak_cms", "pred_peak_cms", "peak_under_deficit", "event_nrmse"]:
        perf[col] = pd.to_numeric(perf[col], errors="coerce")

    windows = pd.read_csv(args.event_windows, dtype={"usgs_id": str, "basin": str})
    windows["usgs_id"] = windows["usgs_id"].map(normalize_gauge_id)
    windows["event_id"] = [event_key(g, t) for g, t in zip(windows["usgs_id"], windows["peak_time"])]

    catalog = read_optional_csv(args.catalog_csv, dtype={"usgs_id": str})
    if not catalog.empty:
        catalog["usgs_id"] = catalog["usgs_id"].map(normalize_gauge_id)
        catalog["event_id"] = [event_key(g, t) for g, t in zip(catalog["usgs_id"], catalog["peak_time"])]
        catalog["noaaTypes"] = catalog.get("noaa_annotation", pd.Series(["-"] * len(catalog))).map(parse_noaa_types)
        catalog["noaaType"] = catalog["noaaTypes"].map(noaa_type_label)
        catalog_subset = catalog[["event_id", "noaa_annotation", "noaaTypes", "noaaType"]].drop_duplicates("event_id")
    else:
        catalog_subset = pd.DataFrame(columns=["event_id", "noaa_annotation", "noaaTypes", "noaaType"])

    events = windows.merge(catalog_subset, on="event_id", how="left")
    events["noaaTypes"] = events["noaaTypes"].apply(lambda v: v if isinstance(v, list) else [])
    events["noaaType"] = events["noaaType"].fillna("No NOAA")
    events["noaa_annotation"] = events["noaa_annotation"].fillna("-")

    def select_perf(model: str, quantile: str, prefix: str) -> pd.DataFrame:
        cols = ["event_id", "seed", "pred_peak_cms", "peak_under_deficit", "is_underestimate", "event_nrmse"]
        out = perf[(perf["model"] == model) & (perf["quantile"] == quantile)][cols].copy()
        out = out.rename(columns={
            "pred_peak_cms": f"{prefix}_pred",
            "peak_under_deficit": f"{prefix}_under",
            "is_underestimate": f"{prefix}_is_under",
            "event_nrmse": f"{prefix}_nrmse",
        })
        return out

    paired = select_perf("model1", "det", "m1")
    for quantile in ["q50", "q95", "q99"]:
        paired = paired.merge(select_perf("model2", quantile, quantile), on=["event_id", "seed"], how="left")
    paired["q99_reduction"] = paired["m1_under"] - paired["q99_under"]

    agg_funcs: dict[str, Any] = {
        "m1_under": "median",
        "q50_under": "median",
        "q95_under": "median",
        "q99_under": "median",
        "q99_reduction": "median",
        "m1_nrmse": "median",
        "q99_nrmse": "median",
        "m1_pred": "median",
        "q99_pred": "median",
    }
    event_perf = paired.groupby("event_id").agg(agg_funcs).reset_index()
    event_perf["q99_reduced_seed_frac"] = paired.groupby("event_id")["q99_reduction"].apply(lambda x: (x > 0).mean()).values
    event_perf["q99_under_seed_frac"] = paired.groupby("event_id")["q99_under"].apply(lambda x: (x > 0).mean()).values
    events = events.merge(event_perf, on="event_id", how="left")

    meta = pd.read_csv(args.drbc_selected, dtype={"gauge_id": str})
    meta["gauge_id"] = meta["gauge_id"].map(normalize_gauge_id)
    static = read_optional_csv(args.static_attributes, dtype={"gauge_id": str})
    if not static.empty:
        static["gauge_id"] = static["gauge_id"].map(normalize_gauge_id)
    screening = read_optional_csv(args.screening_csv, dtype={"gauge_id": str})
    if not screening.empty:
        screening["gauge_id"] = screening["gauge_id"].map(normalize_gauge_id)
    basin_meta = meta.merge(static, on="gauge_id", how="left", suffixes=("", "_static"))
    if not screening.empty:
        keep = [
            "gauge_id", "hydromod_risk", "snow_influenced_tag", "steep_fast_response_tag",
            "coastal_or_hydromod_risk_tag", "recommended_event_priority",
        ]
        basin_meta = basin_meta.merge(screening[[c for c in keep if c in screening.columns]], on="gauge_id", how="left")
    basin_meta["basinType"] = basin_meta.apply(basin_type, axis=1)

    coverage = pd.read_csv(args.coverage_csv, dtype={"usgs_id": str})
    coverage["usgs_id"] = coverage["usgs_id"].map(normalize_gauge_id)

    events = events.merge(
        basin_meta[[
            "gauge_id", "gauge_name", "state", "lat_gage", "lng_gage", "drain_sqkm_attr",
            "basin_area_sqkm_geom", "basinType",
        ]].rename(columns={"gauge_id": "usgs_id"}),
        on="usgs_id",
        how="left",
    )
    events = events.rename(columns={
        "m1_under": "m1Under",
        "q50_under": "q50Under",
        "q95_under": "q95Under",
        "q99_under": "q99Under",
        "q99_reduction": "q99Reduction",
        "m1_nrmse": "m1Nrmse",
        "q99_nrmse": "q99Nrmse",
        "m1_pred": "m1PredPeak",
        "q99_pred": "q99PredPeak",
        "q99_reduced_seed_frac": "q99ReducedSeedFraction",
        "q99_under_seed_frac": "q99UnderSeedFraction",
    })
    events["performanceType"] = [
        performance_type(m1, q99, red)
        for m1, q99, red in zip(events["m1Under"], events["q99Under"], events["q99Reduction"])
    ]
    events["peakTime"] = events["peak_time"].map(iso_hour)
    events["floodTier"] = events["flood_tier"].astype(str)
    events["period"] = events["period"].astype(str)
    events["noaaCorroborated"] = events["noaa_corroborated"].map(boolish)
    events["noaaType"] = [
        label if types else ("NOAA match (untyped)" if corroborated else "No NOAA annotation")
        for label, types, corroborated in zip(events["noaaType"], events["noaaTypes"], events["noaaCorroborated"])
    ]
    events["obsPeakCms"] = pd.to_numeric(events["peak_discharge_cms"], errors="coerce")
    map_geometry, point_by_id = build_map_geometry(args, events)
    events["mapX"] = events["usgs_id"].map(lambda gauge_id: point_by_id.get(gauge_id, {}).get("x"))
    events["mapY"] = events["usgs_id"].map(lambda gauge_id: point_by_id.get(gauge_id, {}).get("y"))

    event_rows: list[dict[str, Any]] = []
    for row in events.sort_values(["peak_time", "usgs_id"]).itertuples(index=False):
        event_rows.append({
            "eventId": row.event_id,
            "usgsId": row.usgs_id,
            "gaugeName": row.gauge_name,
            "state": row.state,
            "peakTime": row.peakTime,
            "floodTier": row.floodTier,
            "period": row.period,
            "noaaCorroborated": bool(row.noaaCorroborated),
            "noaaType": row.noaaType,
            "noaaTypes": list(row.noaaTypes),
            "noaaAnnotation": row.noaa_annotation,
            "performanceType": row.performanceType,
            "obsPeakCms": finite_or_none(row.obsPeakCms, 2),
            "m1Under": finite_or_none(row.m1Under, 3),
            "q50Under": finite_or_none(row.q50Under, 3),
            "q95Under": finite_or_none(row.q95Under, 3),
            "q99Under": finite_or_none(row.q99Under, 3),
            "q99Reduction": finite_or_none(row.q99Reduction, 3),
            "m1Nrmse": finite_or_none(row.m1Nrmse, 3),
            "q99Nrmse": finite_or_none(row.q99Nrmse, 3),
            "q99ReducedSeedFraction": finite_or_none(row.q99ReducedSeedFraction * 100, 1),
            "q99UnderSeedFraction": finite_or_none(row.q99UnderSeedFraction * 100, 1),
            "basinType": row.basinType,
            "lat": finite_or_none(row.lat_gage, 5),
            "lng": finite_or_none(row.lng_gage, 5),
            "mapX": finite_or_none(row.mapX, 2),
            "mapY": finite_or_none(row.mapY, 2),
        })

    event_df = pd.DataFrame(event_rows)
    basin_rows: list[dict[str, Any]] = []
    for usgs_id, grp in event_df.groupby("usgsId"):
        first = grp.iloc[0]
        basin_rows.append({
            "usgsId": usgs_id,
            "gaugeName": first["gaugeName"],
            "state": first["state"],
            "basinType": first["basinType"],
            "lat": first["lat"],
            "lng": first["lng"],
            "mapX": first["mapX"],
            "mapY": first["mapY"],
            "events": int(len(grp)),
            "noaaEvents": int(grp["noaaCorroborated"].sum()),
            "noaaRate": finite_or_none(grp["noaaCorroborated"].mean() * 100, 1),
            "majorEvents": int((grp["floodTier"] == "major").sum()),
            "moderateEvents": int((grp["floodTier"] == "moderate").sum()),
            "minorEvents": int((grp["floodTier"] == "minor").sum()),
            "medianM1Under": finite_or_none(grp["m1Under"].median(), 3),
            "medianQ99Under": finite_or_none(grp["q99Under"].median(), 3),
            "medianQ99Reduction": finite_or_none(grp["q99Reduction"].median(), 3),
            "q99UnderRate": finite_or_none((grp["q99Under"] > 0).mean() * 100, 1),
            "dominantNoaaType": str(grp["noaaType"].mode().iloc[0]) if len(grp["noaaType"].mode()) else "No NOAA",
            "dominantPerformanceType": str(grp["performanceType"].mode().iloc[0]) if len(grp["performanceType"].mode()) else "unknown",
            "tierCounts": ordered_count(grp["floodTier"], TIER_ORDER),
            "noaaTypeCounts": ordered_count(grp["noaaType"]),
            "performanceCounts": ordered_count(grp["performanceType"]),
        })
    basin_rows.sort(key=lambda row: (-row["events"], row["usgsId"]))

    summary = {
        "events": int(len(event_df)),
        "basins": int(event_df["usgsId"].nunique()),
        "seeds": sorted([int(v) for v in perf["seed"].dropna().unique()]),
        "noaaEvents": int(event_df["noaaCorroborated"].sum()),
        "noaaRate": finite_or_none(event_df["noaaCorroborated"].mean() * 100, 1),
        "medianM1Under": finite_or_none(event_df["m1Under"].median(), 3),
        "medianQ99Under": finite_or_none(event_df["q99Under"].median(), 3),
        "medianQ99Reduction": finite_or_none(event_df["q99Reduction"].median(), 3),
        "m1UnderRate": finite_or_none((event_df["m1Under"] > 0).mean() * 100, 1),
        "q99UnderRate": finite_or_none((event_df["q99Under"] > 0).mean() * 100, 1),
        "coverageHasFloodStageBasins": int((coverage["coverage_status"] == "has_flood_stage").sum()),
        "coverageTotalDrbcBasins": int(len(coverage)),
    }

    snapshot = {
        "generatedAt": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": {
            "performance": str(args.perf_csv.relative_to(ROOT)),
            "eventWindows": str(args.event_windows.relative_to(ROOT)),
            "catalog": str(args.catalog_csv.relative_to(ROOT)),
            "coverage": str(args.coverage_csv.relative_to(ROOT)),
            "basinMeta": str(args.drbc_selected.relative_to(ROOT)),
            "camelshShapefile": str(args.camelsh_shapefile.relative_to(ROOT)),
            "drbcBoundary": str(args.drbc_boundary.relative_to(ROOT)),
        },
        "summary": summary,
        "filters": {
            "tiers": TIER_ORDER,
            "periods": PERIOD_ORDER,
            "noaaTypes": sorted(event_df["noaaType"].unique().tolist(), key=lambda x: (x == "No NOAA", x)),
            "performanceTypes": [
                "q99_reduced_under",
                "q99_over_prediction",
                "q99_not_improved",
                "m1_not_under",
                "unknown",
            ],
        },
        "tierSummary": group_summary(event_df, "floodTier", TIER_ORDER),
        "noaaTypeSummary": group_summary(event_df, "noaaType"),
        "performanceSummary": group_summary(event_df, "performanceType"),
        "periodSummary": group_summary(event_df, "period", PERIOD_ORDER),
        "modelQuantileSummary": model_quantile_summary(perf),
        "mapGeometry": map_geometry,
        "basins": basin_rows,
        "events": event_rows,
    }
    return snapshot


def clean_for_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: clean_for_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_for_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if not math.isfinite(float(value)):
            return None
        return float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_ts(snapshot: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(clean_for_json(snapshot), ensure_ascii=False, indent=2, allow_nan=False)
    text = "\n".join([
        "// Generated by scripts/model/confirmed_flood/export_confirmed_flood_dashboard_snapshot.py",
        "// Do not edit values by hand. Regenerate from canonical output/model_analysis artifacts.",
        "",
        f"export const confirmedFloodSnapshot = {payload} as const;",
        "",
        "export type ConfirmedFloodSnapshot = typeof confirmedFloodSnapshot;",
        "export type ConfirmedFloodEvent = ConfirmedFloodSnapshot[\"events\"][number];",
        "export type ConfirmedFloodBasin = ConfirmedFloodSnapshot[\"basins\"][number];",
        "",
    ])
    output_path.write_text(text, encoding="utf-8")
    print(f"Wrote {output_path} ({len(snapshot['events'])} events, {len(snapshot['basins'])} basins)")


def main() -> None:
    args = parse_args()
    snapshot = build_snapshot(args)
    write_ts(snapshot, args.output_ts)


if __name__ == "__main__":
    main()
