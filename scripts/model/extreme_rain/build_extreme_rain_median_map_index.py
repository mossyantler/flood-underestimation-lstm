#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pandas>=2.2",
#   "pyproj>=3.6",
#   "pyshp>=2.3",
#   "shapely>=2.0",
# ]
# ///

from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
from pathlib import Path
from typing import Any

import pandas as pd
import pyproj
import shapefile
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, shape as shapely_shape
from shapely.ops import transform as transform_geometry
from shapely.ops import unary_union
from shapely.validation import make_valid


DEFAULT_EVENT_MANIFEST = Path(
    "output/model_analysis/extreme_rain/primary/event_plots/event_plot_manifest.csv"
)
DEFAULT_SIMQ_EVENT_MANIFEST = Path(
    "output/model_analysis/extreme_rain/primary/event_simq_plots/event_simq_plot_manifest.csv"
)
DEFAULT_TIER_PROFILE = Path(
    "output/model_analysis/overall_analysis/main_comparison/"
    "attribute_correlations/median_deviation/tables/"
    "metric_median_deviation_basin_tier_profile.csv"
)
DEFAULT_DRBC_SELECTED = Path("output/basin/drbc/basin_define/camelsh_drbc_selected.csv")
DEFAULT_CAMELSH_SHAPEFILE = Path("basins/CAMELSH_data/shapefiles/CAMELSH_shapefile.shp")
DEFAULT_DRBC_BOUNDARY = Path("basins/drbc_boundary/drb_bnd_polygon.shp")
DEFAULT_OUTPUT_HTML = Path(
    "output/model_analysis/extreme_rain/primary/event_plot_median_map_index.html"
)
MAP_CRS = "EPSG:5070"
BASIN_FALLBACK_CRS = "EPSG:4326"


TIER_CONFIG: list[dict[str, str]] = [
    {
        "key": "near_median_lt_0_5_iqr",
        "label": "<0.5 IQR",
        "shortLabel": "Near median",
        "description": "18개 metric/model/seed record의 dominant bin이 median 0.5 IQR 안쪽인 basin",
        "color": "#2f855a",
    },
    {
        "key": "shoulder_0_5_to_1_5_iqr",
        "label": "0.5-1.5 IQR",
        "shortLabel": "Shoulder",
        "description": "median 주변이지만 0.5 IQR 밖 record가 dominant한 basin",
        "color": "#b7791f",
    },
    {
        "key": "far_1_5_to_3_iqr",
        "label": "1.5-3 IQR",
        "shortLabel": "Far",
        "description": "1.5 IQR 이상 far record가 basin profile에서 많이 나타나는 basin",
        "color": "#c05621",
    },
    {
        "key": "extreme_ge_3_iqr",
        "label": ">=3 IQR",
        "shortLabel": "Extreme",
        "description": "3 IQR 이상 extreme record가 basin profile의 dominant bin인 basin",
        "color": "#c53030",
    },
]
TIER_BY_LABEL = {item["label"]: item for item in TIER_CONFIG}
TIER_BY_KEY = {item["key"]: item for item in TIER_CONFIG}
RAIN_ORDER = {"prec_ge100": 0, "prec_ge50": 1, "prec_ge25": 2, "near_prec100": 3}
RESPONSE_ORDER = {
    "flood_response_ge25": 0,
    "flood_response_ge2_to_lt25": 1,
    "high_flow_non_flood_q99_only": 2,
    "low_response_below_q99": 3,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build an interactive DRBC map index that groups primary extreme-rain "
            "event plots by primary median-distance basin tier."
        )
    )
    parser.add_argument("--event-manifest", type=Path, default=DEFAULT_EVENT_MANIFEST)
    parser.add_argument("--simq-event-manifest", type=Path, default=DEFAULT_SIMQ_EVENT_MANIFEST)
    parser.add_argument(
        "--prefer-simq-plots",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use event_simq_plot_manifest.csv when it exists, falling back to the observed-only event manifest.",
    )
    parser.add_argument("--tier-profile", type=Path, default=DEFAULT_TIER_PROFILE)
    parser.add_argument("--drbc-selected", type=Path, default=DEFAULT_DRBC_SELECTED)
    parser.add_argument("--camelsh-shapefile", type=Path, default=DEFAULT_CAMELSH_SHAPEFILE)
    parser.add_argument("--drbc-boundary", type=Path, default=DEFAULT_DRBC_BOUNDARY)
    parser.add_argument("--output-html", type=Path, default=DEFAULT_OUTPUT_HTML)
    parser.add_argument(
        "--svg-width",
        type=float,
        default=380,
        help="SVG viewBox width in CSS-independent units. The default follows the DRBC basin's tall map aspect.",
    )
    parser.add_argument(
        "--svg-height",
        type=float,
        default=760,
        help="SVG viewBox height in CSS-independent units.",
    )
    parser.add_argument(
        "--simplify-px",
        type=float,
        default=0.0,
        help=(
            "Ramer-Douglas-Peucker tolerance after projected geometry is mapped to SVG pixels. "
            "The default keeps shared basin/DRBC boundary edges unsimplified for tighter overlay."
        ),
    )
    return parser.parse_args()


def normalize_gauge_id(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    if re.fullmatch(r"\d+", text) and len(text) < 8:
        text = text.zfill(8)
    return text


def finite_or_none(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def fmt_float(value: Any, digits: int = 2) -> str:
    out = finite_or_none(value)
    if out is None:
        return "NA"
    return f"{out:.{digits}f}"


def fmt_area(value: Any) -> str:
    out = finite_or_none(value)
    if out is None:
        return "NA"
    if out >= 100:
        return f"{out:,.0f}"
    return f"{out:.1f}"


def fmt_pct(value: Any, digits: int = 0) -> str:
    out = finite_or_none(value)
    if out is None:
        return "NA"
    return f"{out:.{digits}f}%"


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def shorten_text(value: Any, max_chars: int = 44) -> str:
    if pd.isna(value):
        return ""
    text = re.sub(r"\s+", " ", str(value).strip())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def compact_items(items: list[str], max_items: int = 4) -> list[str]:
    clean = [item for item in items if item]
    if len(clean) <= max_items:
        return clean
    return [*clean[:max_items], f"+{len(clean) - max_items} more"]


def natural_tag_labels(row: pd.Series) -> list[str]:
    labels: list[str] = []
    hydromod = boolish(row.get("hydromod_risk")) or boolish(row.get("coastal_or_hydromod_risk_tag"))
    labels.append("hydromod caution" if hydromod else "low hydromod proxy")
    if boolish(row.get("snow_influenced_tag")):
        labels.append("snow-influenced")
    if boolish(row.get("steep_fast_response_tag")):
        labels.append("steep-fast")
    forest = finite_or_none(row.get("forest_pct"))
    developed = finite_or_none(row.get("developed_pct"))
    wetland = finite_or_none(row.get("wetland_pct"))
    if forest is not None and forest >= 50:
        labels.append("forested")
    if developed is not None and developed >= 15:
        labels.append("developed")
    if wetland is not None and wetland >= 10:
        labels.append("wetland")
    land_cover = shorten_text(str(row.get("dom_land_cover", "")).replace("_", " "), max_chars=24)
    if land_cover and land_cover.lower() != "nan":
        labels.append(f"landcover {land_cover}")
    return compact_items(labels, max_items=4)


def human_impact_labels(row: pd.Series) -> list[str]:
    labels: list[str] = []
    major_dams = finite_or_none(row.get("MAJ_NDAMS_2009"))
    dams = finite_or_none(row.get("NDAMS_2009"))
    storage = finite_or_none(row.get("STOR_NOR_2009"))
    canals = finite_or_none(row.get("CANALS_PCT"))
    water_use = finite_or_none(row.get("FRESHW_WITHDRAWAL"))
    npdes = finite_or_none(row.get("NPDES_MAJ_DENS"))
    power = finite_or_none(row.get("POWER_NUM_PTS"))
    if major_dams is not None and major_dams > 0:
        labels.append(f"major dams {major_dams:.0f}")
    if dams is not None and dams > 0:
        labels.append(f"dams {dams:.0f}")
    if storage is not None and storage > 0:
        labels.append(f"storage {storage:.0f} ML/km2")
    if canals is not None and canals > 0:
        labels.append(f"canals {canals:.1f}%")
    if water_use is not None and water_use > 0:
        labels.append(f"water use {water_use:.0f} ML/yr/km2")
    if npdes is not None and npdes > 0:
        labels.append(f"NPDES {npdes:.2f}")
    if power is not None and power > 0:
        labels.append(f"power pts {power:.0f}")
    if not labels:
        return ["low hydromod proxy"]
    return compact_items(labels, max_items=4)


def basin_legend_metadata_lines(row: pd.Series) -> list[str]:
    return [
        (
            f"area {fmt_area(row.get('drain_sqkm_attr'))} km2 | "
            f"forest {fmt_pct(row.get('forest_pct'))} | developed {fmt_pct(row.get('developed_pct'))}"
        ),
        "tags: " + "; ".join(natural_tag_labels(row)),
        "human impact: " + "; ".join(human_impact_labels(row)),
    ]


def rel_path(from_file: Path, target: Path | str) -> str:
    target_path = Path(str(target))
    rel = os.path.relpath(target_path, from_file.parent)
    return rel.replace(os.sep, "/")


def read_inputs(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    resolved_event_manifest = args.event_manifest
    event_plot_kind = "observed"
    if args.prefer_simq_plots and args.simq_event_manifest.exists():
        resolved_event_manifest = args.simq_event_manifest
        event_plot_kind = "sim_q"

    args.resolved_event_manifest = resolved_event_manifest
    args.event_plot_kind = event_plot_kind

    events = pd.read_csv(resolved_event_manifest, dtype={"gauge_id": str})
    events["gauge_id"] = events["gauge_id"].map(normalize_gauge_id)
    events["plot_path_rel"] = events["plot_path"].map(lambda p: rel_path(args.output_html, p))
    events["plot_kind"] = event_plot_kind

    tiers = pd.read_csv(args.tier_profile, dtype={"basin": str})
    tiers["gauge_id"] = tiers["basin"].map(normalize_gauge_id)
    tiers["tier_key"] = tiers["dominant_distance_label"].map(
        lambda label: TIER_BY_LABEL.get(str(label), TIER_CONFIG[0])["key"]
    )
    tiers["tier_label"] = tiers["tier_key"].map(lambda key: TIER_BY_KEY[key]["label"])

    selected = pd.read_csv(args.drbc_selected, dtype={"gauge_id": str})
    selected["gauge_id"] = selected["gauge_id"].map(normalize_gauge_id)
    return events, tiers, selected


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


def load_boundary_geometry(boundary_path: Path) -> tuple[Any, list[list[tuple[float, float]]]]:
    reader = shapefile.Reader(str(boundary_path))
    source_crs = read_shapefile_crs(boundary_path, fallback=MAP_CRS)
    to_map_crs = pyproj.Transformer.from_crs(source_crs, MAP_CRS, always_xy=True).transform
    geometries = [
        make_valid(transform_geometry(to_map_crs, make_valid(shapely_shape(shape.__geo_interface__))))
        for shape in reader.shapes()
    ]
    if not geometries:
        raise RuntimeError(f"No DRBC boundary geometry found in {boundary_path}")
    boundary = make_valid(unary_union(geometries))
    rings = polygonal_rings(boundary)
    if not rings:
        raise RuntimeError(f"No polygon rings found in DRBC boundary {boundary_path}")
    return boundary, rings


def load_basin_rings(
    shapefile_path: Path,
    gauge_ids: set[str],
    clip_geometry: Any,
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
        rings = polygonal_rings(clipped_geometry)
        if not rings:
            rings = polygonal_rings(projected_geometry)
        geometries[gauge_id] = rings
        if len(geometries) == len(gauge_ids):
            break

    missing = sorted(gauge_ids - set(geometries))
    if missing:
        raise RuntimeError(f"Missing CAMELSH basin geometry for {', '.join(missing[:10])}")
    return geometries


def point_line_distance(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]) -> float:
    px, py = point
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def rdp(points: list[tuple[float, float]], epsilon: float) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return points
    max_dist = -1.0
    max_idx = 0
    for idx in range(1, len(points) - 1):
        dist = point_line_distance(points[idx], points[0], points[-1])
        if dist > max_dist:
            max_dist = dist
            max_idx = idx
    if max_dist > epsilon:
        left = rdp(points[: max_idx + 1], epsilon)
        right = rdp(points[max_idx:], epsilon)
        return left[:-1] + right
    return [points[0], points[-1]]


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


def ring_to_path(
    ring: list[tuple[float, float]],
    projector: SvgProjector,
    simplify_px: float,
) -> str:
    projected = [projector.project(point) for point in ring]
    if len(projected) >= 2 and projected[0] == projected[-1]:
        projected = projected[:-1]
    if len(projected) < 3:
        return ""
    simplified = projected if simplify_px <= 0 else rdp(projected, simplify_px)
    if len(simplified) < 3:
        simplified = projected
    commands = " ".join(f"L {x:.1f} {y:.1f}" for x, y in simplified[1:])
    first_x, first_y = simplified[0]
    return f"M {first_x:.1f} {first_y:.1f} {commands} Z"


def rings_to_path(
    rings: list[list[tuple[float, float]]],
    projector: SvgProjector,
    simplify_px: float,
) -> str:
    return " ".join(
        path
        for path in (ring_to_path(ring, projector, simplify_px) for ring in rings)
        if path
    )


def ring_area(ring: list[tuple[float, float]]) -> float:
    if len(ring) < 3:
        return 0.0
    area = 0.0
    points = ring
    if points[0] != points[-1]:
        points = points + [points[0]]
    for (x1, y1), (x2, y2) in zip(points[:-1], points[1:]):
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def rings_area(rings: list[list[tuple[float, float]]]) -> float:
    return sum(ring_area(ring) for ring in rings)


def build_svg(
    basin_rings: dict[str, list[list[tuple[float, float]]]],
    boundary_rings: list[list[tuple[float, float]]],
    basin_rows: dict[str, dict[str, Any]],
    width: float,
    height: float,
    simplify_px: float,
) -> str:
    all_rings = boundary_rings + [ring for rings in basin_rings.values() for ring in rings]
    projector = SvgProjector(all_rings, width=width, height=height)
    boundary_path = rings_to_path(boundary_rings, projector, simplify_px)

    basin_paths: list[str] = []
    draw_order = sorted(
        basin_rows,
        key=lambda gauge_id: (-rings_area(basin_rings[gauge_id]), gauge_id),
    )
    for gauge_id in draw_order:
        row = basin_rows[gauge_id]
        tier_key = row["tierKey"]
        color = TIER_BY_KEY[tier_key]["color"]
        d_attr = rings_to_path(basin_rings[gauge_id], projector, simplify_px)
        title = html.escape(
            f"{gauge_id} {row['gaugeName']} | {row['tierLabel']} | {row['eventCount']} events"
        )
        basin_paths.append(
            "\n".join(
                [
                    (
                        f'<path class="basin-shape" data-gauge-id="{html.escape(gauge_id)}" '
                        f'data-tier-key="{html.escape(tier_key)}" '
                        f'd="{html.escape(d_attr, quote=True)}" '
                        f'style="--tier-color:{html.escape(color)}" tabindex="0">'
                    ),
                    f"<title>{title}</title>",
                    "</path>",
                ]
            )
        )

    return f"""
<svg id="drbcMap" class="drbc-map" viewBox="0 0 {width:.0f} {height:.0f}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="DRBC primary test basin map">
  <rect class="map-bg" x="0" y="0" width="{width:.0f}" height="{height:.0f}" rx="10"></rect>
  <path class="drbc-boundary-fill" d="{html.escape(boundary_path, quote=True)}"></path>
  {"".join(basin_paths)}
  <path class="drbc-boundary-line" d="{html.escape(boundary_path, quote=True)}"></path>
</svg>
""".strip()


def build_basin_records(
    events: pd.DataFrame,
    tiers: pd.DataFrame,
    selected: pd.DataFrame,
) -> dict[str, dict[str, Any]]:
    selected_by_id = selected.set_index("gauge_id", drop=False)
    tier_by_id = tiers.set_index("gauge_id", drop=False)
    records: dict[str, dict[str, Any]] = {}

    for gauge_id, event_group in events.groupby("gauge_id", sort=True):
        if gauge_id not in tier_by_id.index:
            raise RuntimeError(f"Missing median-distance tier profile for {gauge_id}")
        tier = tier_by_id.loc[gauge_id]
        selected_row = selected_by_id.loc[gauge_id] if gauge_id in selected_by_id.index else {}
        event_group = event_group.copy()
        event_group["rain_order"] = event_group["rain_cohort"].map(RAIN_ORDER).fillna(99)
        event_group["response_order"] = event_group["response_class"].map(RESPONSE_ORDER).fillna(99)
        event_group = event_group.sort_values(
            ["rain_order", "stress_group", "response_order", "rain_start", "event_id"]
        )
        basin_metadata_row = event_group.iloc[0]
        event_records = []
        for _, event in event_group.iterrows():
            event_records.append(
                {
                    "eventId": str(event["event_id"]),
                    "stressGroup": str(event["stress_group"]),
                    "rainCohort": str(event["rain_cohort"]),
                    "responseClass": str(event["response_class"]),
                    "rainStart": str(event["rain_start"]),
                    "rainPeak": str(event["rain_peak"]),
                    "rainEnd": str(event["rain_end"]),
                    "observedPeakTime": str(event["observed_response_peak_time"]),
                    "observedPeak": fmt_float(event.get("observed_response_peak"), 2),
                    "maxPrecAri25": fmt_float(event.get("max_prec_ari25_ratio"), 2),
                    "maxPrecAri50": fmt_float(event.get("max_prec_ari50_ratio"), 2),
                    "maxPrecAri100": fmt_float(event.get("max_prec_ari100_ratio"), 2),
                    "obsToFlood2": fmt_float(event.get("obs_peak_to_flood_ari2"), 2),
                    "obsToFlood25": fmt_float(event.get("obs_peak_to_flood_ari25"), 2),
                    "plotPath": str(event["plot_path_rel"]),
                    "plotKind": str(event.get("plot_kind", "observed")),
                }
            )

        counts = {
            "near": int(tier.get("near_median_lt_0_5_iqr", 0)),
            "shoulder": int(tier.get("shoulder_0_5_to_1_5_iqr", 0)),
            "far": int(tier.get("far_1_5_to_3_iqr", 0)),
            "extreme": int(tier.get("extreme_ge_3_iqr", 0)),
        }
        tier_key = str(tier["tier_key"])
        records[gauge_id] = {
            "gaugeId": gauge_id,
            "gaugeName": str(tier.get("gauge_name", selected_row.get("gauge_name", ""))),
            "state": str(tier.get("state", selected_row.get("state", ""))),
            "tierKey": tier_key,
            "tierLabel": TIER_BY_KEY[tier_key]["label"],
            "tierShortLabel": TIER_BY_KEY[tier_key]["shortLabel"],
            "tierColor": TIER_BY_KEY[tier_key]["color"],
            "eventCount": int(len(event_group)),
            "lat": finite_or_none(selected_row.get("lat_gage") if hasattr(selected_row, "get") else None),
            "lon": finite_or_none(selected_row.get("lng_gage") if hasattr(selected_row, "get") else None),
            "area": fmt_float(tier.get("area"), 1),
            "obsQ99": fmt_float(tier.get("obs_q99"), 2),
            "q99EventFrequency": fmt_float(tier.get("q99_event_frequency"), 2),
            "rbi": fmt_float(tier.get("rbi"), 3),
            "farOrExtremeRecords": int(tier.get("far_or_extreme_records", 0)),
            "farOrExtremeShare": fmt_float(tier.get("far_or_extreme_share"), 2),
            "meanDistance": fmt_float(tier.get("mean_distance_any_metric_seed"), 2),
            "maxDistance": fmt_float(tier.get("max_distance_any_metric_seed"), 2),
            "nseMeanDistance": fmt_float(tier.get("NSE_mean_median_distance_iqr"), 2),
            "kgeMeanDistance": fmt_float(tier.get("KGE_mean_median_distance_iqr"), 2),
            "fhvMeanDistance": fmt_float(tier.get("FHV_mean_median_distance_iqr"), 2),
            "legendMetadataLines": basin_legend_metadata_lines(basin_metadata_row),
            "distanceCounts": counts,
            "events": event_records,
        }
    return records


def build_summary(basin_records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_tier: dict[str, dict[str, int]] = {}
    for tier in TIER_CONFIG:
        basins = [record for record in basin_records.values() if record["tierKey"] == tier["key"]]
        by_tier[tier["key"]] = {
            "basins": len(basins),
            "events": sum(record["eventCount"] for record in basins),
        }
    return {
        "basins": len(basin_records),
        "events": sum(record["eventCount"] for record in basin_records.values()),
        "byTier": by_tier,
    }


def render_html(
    svg: str,
    basin_records: dict[str, dict[str, Any]],
    summary: dict[str, Any],
    args: argparse.Namespace,
) -> str:
    basins_json = json.dumps(list(basin_records.values()), ensure_ascii=False, allow_nan=False)
    tiers_json = json.dumps(TIER_CONFIG, ensure_ascii=False, allow_nan=False)
    summary_json = json.dumps(summary, ensure_ascii=False, allow_nan=False)
    event_manifest = getattr(args, "resolved_event_manifest", args.event_manifest)
    event_plot_kind = getattr(args, "event_plot_kind", "observed")
    plot_heading = "Sim-Q event hydrographs" if event_plot_kind == "sim_q" else "Observed event hydrographs"
    plot_count_label = (
        "observed + Model 1 + Model 2 q50/q95/q99 plots"
        if event_plot_kind == "sim_q"
        else "observed-only event plots"
    )
    source_info = {
        "eventManifest": str(event_manifest),
        "observedEventManifest": str(args.event_manifest),
        "simqEventManifest": str(args.simq_event_manifest),
        "eventPlotKind": event_plot_kind,
        "tierProfile": str(args.tier_profile),
        "drbcSelected": str(args.drbc_selected),
        "camelshShapefile": str(args.camelsh_shapefile),
        "drbcBoundary": str(args.drbc_boundary),
        "mapCrs": MAP_CRS,
        "basinFallbackCrs": BASIN_FALLBACK_CRS,
    }
    source_json = json.dumps(source_info, ensure_ascii=False, allow_nan=False)

    tier_cards = "\n".join(
        [
            (
                f'<button class="tier-button" type="button" data-tier-key="{html.escape(tier["key"])}">'
                f'<span class="tier-dot" style="background:{html.escape(tier["color"])}"></span>'
                f'<span><strong>{html.escape(tier["label"])}</strong>'
                f'<small>{summary["byTier"][tier["key"]]["basins"]} basins · '
                f'{summary["byTier"][tier["key"]]["events"]} events</small></span>'
                "</button>"
            )
            for tier in TIER_CONFIG
        ]
    )

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Extreme-rain event plots by median-distance basin tier</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1f2933;
      --muted: #5f6b7a;
      --line: #d7dde5;
      --soft: #f4f6f8;
      --panel: #ffffff;
      --active: #1d4ed8;
      --shadow: 0 10px 28px rgba(15, 23, 42, 0.10);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: #f8fafc;
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }}
    header {{
      padding: 22px 24px 14px;
      border-bottom: 1px solid var(--line);
      background: #fff;
    }}
    h1 {{ margin: 0 0 8px; font-size: 22px; line-height: 1.25; }}
    p {{ line-height: 1.5; }}
    h1, h2, h3, h4, p, small, strong, span {{ min-width: 0; }}
    .intro {{ max-width: 1180px; margin: 0; color: var(--muted); font-size: 14px; }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(300px, 0.72fr) minmax(0, 1.28fr);
      gap: 16px;
      padding: 16px;
      align-items: start;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      min-width: 0;
    }}
    .map-panel {{ padding: 12px; }}
    .detail-panel {{ min-height: 720px; min-width: 0; overflow: hidden; }}
    .panel-head {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
    }}
    .panel-head h2 {{ margin: 0; font-size: 16px; }}
    .panel-head p {{ margin: 3px 0 0; color: var(--muted); font-size: 12px; }}
    .tier-controls {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 7px;
      margin-bottom: 10px;
    }}
    .tier-button, .all-button, .basin-row {{
      appearance: none;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--ink);
      border-radius: 7px;
      cursor: pointer;
      font: inherit;
      text-align: left;
    }}
    .tier-button {{
      display: flex;
      gap: 7px;
      align-items: center;
      padding: 7px 8px;
      min-height: 46px;
      min-width: 0;
    }}
    .all-button {{
      padding: 7px 8px;
      min-height: 46px;
    }}
    .tier-button small, .all-button small {{
      display: block;
      color: var(--muted);
      margin-top: 2px;
      font-size: 11px;
      overflow-wrap: anywhere;
      white-space: normal;
    }}
    .tier-button.is-active, .all-button.is-active {{
      border-color: var(--active);
      box-shadow: 0 0 0 2px rgba(29, 78, 216, 0.14);
    }}
    .tier-dot {{
      width: 13px;
      height: 13px;
      border-radius: 999px;
      border: 1px solid rgba(0, 0, 0, 0.18);
      flex: 0 0 auto;
    }}
    .map-frame {{
      display: flex;
      justify-content: center;
      border: 1px solid var(--line);
      background: #eef4f7;
      border-radius: 8px;
      overflow: hidden;
    }}
    .drbc-map {{ width: auto; height: min(64vh, 700px); max-width: 100%; display: block; }}
    .map-bg {{ fill: #edf5f7; }}
    .drbc-boundary-fill {{ fill: #f8fbf9; stroke: none; }}
    .drbc-boundary-line {{ fill: none; stroke: #334155; stroke-width: 2.2; pointer-events: none; }}
    .basin-shape {{
      fill: var(--tier-color);
      fill-opacity: 0.78;
      fill-rule: evenodd;
      stroke: #ffffff;
      stroke-width: 1.15;
      cursor: pointer;
      transition: fill 130ms ease, fill-opacity 130ms ease, opacity 130ms ease, stroke 130ms ease, stroke-width 130ms ease;
      outline: none;
    }}
    .basin-shape:hover, .basin-shape:focus {{
      fill-opacity: 0.95;
      stroke: #111827;
      stroke-width: 2.2;
    }}
    .basin-shape.is-muted {{ fill: #d8dee7; fill-opacity: 0.45; stroke: #ffffff; }}
    .basin-shape.is-selected {{ fill-opacity: 1; stroke: #111827; stroke-width: 3; }}
    .legend-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 10px;
      color: var(--muted);
      font-size: 12px;
    }}
    .legend-item {{ display: inline-flex; align-items: center; gap: 5px; }}
    .detail-top {{
      padding: 14px;
      border-bottom: 1px solid var(--line);
      background: #fff;
    }}
    .selection-title {{ margin: 0; font-size: 16px; }}
    .selection-note {{ margin: 4px 0 0; color: var(--muted); font-size: 12px; }}
    .basin-list {{
      max-height: 230px;
      overflow: auto;
      padding: 10px 14px;
      border-bottom: 1px solid var(--line);
      background: #fbfcfd;
    }}
    .basin-list-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 185px), 1fr)); gap: 7px; }}
    .basin-row {{
      display: grid;
      grid-template-columns: 11px minmax(0, 1fr);
      gap: 7px;
      align-items: start;
      padding: 7px;
      min-height: 50px;
      min-width: 0;
      overflow: hidden;
      width: 100%;
    }}
    .basin-row.is-selected {{ border-color: #111827; background: #f3f4f6; }}
    .basin-row > span:last-child {{ min-width: 0; max-width: 100%; overflow: hidden; }}
    .basin-row strong {{
      display: block;
      font-size: 12px;
      line-height: 1.25;
      max-width: 100%;
      overflow-wrap: anywhere;
      word-break: break-word;
      white-space: normal;
    }}
    .basin-row small {{
      color: var(--muted);
      display: block;
      font-size: 11px;
      margin-top: 2px;
      line-height: 1.25;
      max-width: 100%;
      overflow-wrap: anywhere;
      word-break: break-word;
      white-space: normal;
    }}
    .basin-detail {{ padding: 14px; }}
    .basin-title-row {{
      display: flex;
      flex-wrap: wrap;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
      min-width: 0;
    }}
    .basin-title-row > div {{ min-width: 0; max-width: 100%; }}
    .basin-title-row h2 {{ margin: 0; font-size: 18px; overflow-wrap: anywhere; word-break: break-word; }}
    .selection-note {{ overflow-wrap: anywhere; word-break: break-word; }}
    .basin-legend-meta {{
      display: grid;
      gap: 3px;
      margin-top: 6px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 8px;
      color: var(--ink);
      background: #fff;
      font-size: 12px;
      max-width: 100%;
      overflow-wrap: anywhere;
      white-space: normal;
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(min(100%, 122px), 1fr));
      gap: 8px;
      margin: 10px 0 14px;
    }}
    .metric-card {{
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 8px;
      background: #fff;
      min-height: 58px;
      min-width: 0;
    }}
    .metric-card span {{ display: block; color: var(--muted); font-size: 11px; }}
    .metric-card strong {{ display: block; margin-top: 4px; font-size: 14px; overflow-wrap: anywhere; word-break: break-word; }}
    .stack {{
      height: 11px;
      display: grid;
      grid-template-columns:
        var(--near, 0fr)
        var(--shoulder, 0fr)
        var(--far, 0fr)
        var(--extreme, 0fr);
      border-radius: 999px;
      overflow: hidden;
      border: 1px solid var(--line);
      background: #f1f5f9;
      margin: 8px 0 12px;
    }}
    .stack div:nth-child(1) {{ background: #2f855a; }}
    .stack div:nth-child(2) {{ background: #b7791f; }}
    .stack div:nth-child(3) {{ background: #c05621; }}
    .stack div:nth-child(4) {{ background: #c53030; }}
    .event-toolbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin: 14px 0 8px;
      min-width: 0;
    }}
    .event-toolbar h3 {{ margin: 0; font-size: 14px; overflow-wrap: anywhere; word-break: break-word; }}
    .event-toolbar small {{ color: var(--muted); overflow-wrap: anywhere; word-break: break-word; }}
    .event-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(min(100%, 230px), 1fr));
      gap: 10px;
    }}
    .event-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      overflow: hidden;
      min-width: 0;
    }}
    .plot-button {{
      appearance: none;
      border: 0;
      background: #f3f6f8;
      cursor: zoom-in;
      display: block;
      padding: 0;
      width: 100%;
    }}
    .plot-button img {{
      display: block;
      width: 100%;
      aspect-ratio: 1.45 / 1;
      object-fit: cover;
      border-bottom: 1px solid var(--line);
    }}
    .event-copy {{ padding: 8px; }}
    .event-copy h4 {{ margin: 0 0 5px; font-size: 12px; overflow-wrap: anywhere; word-break: break-word; }}
    .event-copy p {{ margin: 3px 0; color: var(--muted); font-size: 11px; line-height: 1.35; overflow-wrap: anywhere; word-break: break-word; }}
    .sources {{
      padding: 0 16px 18px;
      color: var(--muted);
      font-size: 11px;
    }}
    .sources code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    body.lightbox-open {{ overflow: hidden; }}
    .lightbox[hidden] {{ display: none; }}
    .lightbox {{
      position: fixed;
      inset: 0;
      z-index: 50;
      display: grid;
      place-items: center;
      padding: 24px;
    }}
    .lightbox-backdrop {{ position: absolute; inset: 0; background: rgba(15, 23, 42, 0.78); }}
    .lightbox-panel {{
      position: relative;
      z-index: 1;
      background: #fff;
      border-radius: 8px;
      max-width: min(1180px, calc(100vw - 48px));
      max-height: calc(100vh - 48px);
      overflow: auto;
      padding: 12px;
      box-shadow: 0 24px 80px rgba(0, 0, 0, 0.36);
    }}
    .lightbox-close {{
      position: absolute;
      top: 12px;
      right: 12px;
      border: 1px solid var(--line);
      background: #fff;
      border-radius: 6px;
      padding: 6px 9px;
      cursor: pointer;
      font-size: 12px;
    }}
    .lightbox-image-frame {{
      display: flex;
      justify-content: center;
      align-items: center;
      background: #f3f6f8;
      border: 1px solid var(--line);
      border-radius: 7px;
      min-height: 240px;
      padding: 8px;
    }}
    .lightbox-image {{ display: block; max-width: 100%; max-height: 72vh; object-fit: contain; }}
    .lightbox-caption {{ margin: 8px 86px 8px 0; color: var(--muted); font-size: 12px; line-height: 1.4; overflow-wrap: anywhere; word-break: break-word; }}
    .lightbox-nav {{
      display: grid;
      grid-template-columns: 44px minmax(0, 1fr) 44px;
      align-items: center;
      gap: 10px;
    }}
    .lightbox-position {{ color: var(--muted); font-size: 12px; text-align: center; overflow-wrap: anywhere; }}
    .lightbox-nav-button {{
      border: 1px solid var(--line);
      background: #fff;
      border-radius: 6px;
      cursor: pointer;
      height: 38px;
      font-size: 17px;
    }}
    .lightbox-nav-button:hover, .lightbox-close:hover {{ background: #f4f6f8; }}
    @media (max-width: 980px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .drbc-map {{ height: auto; }}
      .metric-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 520px) {{
      .tier-controls {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Extreme-rain event plots by median-distance basin tier</h1>
    <p class="intro">
      DRBC primary 38개 basin을 primary metric boxplot median-distance 기준으로 먼저 나누고,
      각 basin을 누르면 해당 basin의 extreme-rain event flow chart를 바로 확인하는 index입니다.
      Median-distance는 NSE/KGE/FHV x Model 1/2 x seed 111/222/444의 18개 record를 기준으로 합니다.
    </p>
  </header>
  <main class="layout">
    <section class="panel map-panel">
      <div class="panel-head">
        <div>
          <h2>DRBC basin map</h2>
          <p>Median tier를 누르면 해당 tier basin만 강조되고, map의 basin을 누르면 오른쪽에 flow chart가 열립니다.</p>
        </div>
      </div>
      <div class="tier-controls">
        <button class="all-button is-active" type="button" data-tier-key="all">
          <strong>All median tiers</strong>
          <small>{summary["basins"]} basins · {summary["events"]} events</small>
        </button>
        {tier_cards}
      </div>
      <div class="map-frame">
        {svg}
      </div>
      <div class="legend-row">
        {''.join(f'<span class="legend-item"><span class="tier-dot" style="background:{html.escape(tier["color"])}"></span>{html.escape(tier["label"])}</span>' for tier in TIER_CONFIG)}
      </div>
    </section>

    <aside class="panel detail-panel">
      <div class="detail-top">
        <h2 id="selectionTitle" class="selection-title">All median tiers</h2>
        <p id="selectionNote" class="selection-note"></p>
      </div>
      <div class="basin-list">
        <div id="basinList" class="basin-list-grid"></div>
      </div>
      <div id="basinDetail" class="basin-detail"></div>
    </aside>
  </main>

  <section class="sources">
    <p>
      Sources:
      <code>{html.escape(str(event_manifest))}</code>,
      <code>{html.escape(str(args.tier_profile))}</code>,
      <code>{html.escape(str(args.drbc_boundary))}</code>,
      <code>{html.escape(str(args.camelsh_shapefile))}</code>.
    </p>
  </section>

  <div id="lightbox" class="lightbox" hidden>
    <div class="lightbox-backdrop" data-close-lightbox></div>
    <div class="lightbox-panel" role="dialog" aria-modal="true" aria-label="Event plot preview">
      <button class="lightbox-close" type="button" data-close-lightbox>닫기</button>
      <div class="lightbox-image-frame">
        <img id="lightboxImage" class="lightbox-image" alt="">
      </div>
      <div id="lightboxCaption" class="lightbox-caption"></div>
      <div class="lightbox-nav">
        <button id="lightboxPrev" class="lightbox-nav-button" type="button" aria-label="이전 hydrograph">&larr;</button>
        <span id="lightboxPosition" class="lightbox-position"></span>
        <button id="lightboxNext" class="lightbox-nav-button" type="button" aria-label="다음 hydrograph">&rarr;</button>
      </div>
    </div>
  </div>

  <script>
    const TIER_CONFIG = {tiers_json};
    const BASINS = {basins_json};
    const SUMMARY = {summary_json};
    const SOURCES = {source_json};
    const basinById = new Map(BASINS.map((basin) => [basin.gaugeId, basin]));
    const tierByKey = new Map(TIER_CONFIG.map((tier) => [tier.key, tier]));
    let activeTier = "all";
    let selectedGaugeId = null;
    let currentEvents = [];
    let currentEventIndex = 0;

    const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => (
      {{ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }}[char]
    ));

    const visibleBasins = () => BASINS
      .filter((basin) => activeTier === "all" || basin.tierKey === activeTier)
      .sort((a, b) => {{
        const tierA = TIER_CONFIG.findIndex((tier) => tier.key === a.tierKey);
        const tierB = TIER_CONFIG.findIndex((tier) => tier.key === b.tierKey);
        if (tierA !== tierB) return tierB - tierA;
        return Number(b.farOrExtremeRecords) - Number(a.farOrExtremeRecords)
          || Number(b.eventCount) - Number(a.eventCount)
          || a.gaugeId.localeCompare(b.gaugeId);
      }});

    function setActiveTier(tierKey) {{
      activeTier = tierKey;
      document.querySelectorAll(".tier-button, .all-button").forEach((button) => {{
        button.classList.toggle("is-active", button.dataset.tierKey === tierKey);
      }});
      const tier = tierByKey.get(tierKey);
      const title = tierKey === "all" ? "All median tiers" : `${{tier.label}} · ${{tier.shortLabel}}`;
      const note = tierKey === "all"
        ? `${{SUMMARY.basins}} basins · ${{SUMMARY.events}} events. 모든 median-distance tier를 색으로 함께 표시합니다.`
        : `${{SUMMARY.byTier[tierKey].basins}} basins · ${{SUMMARY.byTier[tierKey].events}} events. ${{tier.description}}.`;
      document.getElementById("selectionTitle").textContent = title;
      document.getElementById("selectionNote").textContent = note;
      updateMapStyles();
      renderBasinList();
      const visible = visibleBasins();
      if (!selectedGaugeId || !visible.some((basin) => basin.gaugeId === selectedGaugeId)) {{
        selectedGaugeId = visible.length ? visible[0].gaugeId : null;
      }}
      renderBasinDetail();
      updateMapStyles();
    }}

    function updateMapStyles() {{
      document.querySelectorAll(".basin-shape").forEach((shape) => {{
        const basin = basinById.get(shape.dataset.gaugeId);
        const isVisible = activeTier === "all" || basin.tierKey === activeTier;
        shape.classList.toggle("is-muted", !isVisible);
        shape.classList.toggle("is-selected", shape.dataset.gaugeId === selectedGaugeId);
        shape.style.setProperty("--tier-color", basin.tierColor);
      }});
    }}

    function renderBasinList() {{
      const container = document.getElementById("basinList");
      const basins = visibleBasins();
      container.innerHTML = basins.map((basin) => `
        <button class="basin-row ${{basin.gaugeId === selectedGaugeId ? "is-selected" : ""}}" type="button" data-gauge-id="${{escapeHtml(basin.gaugeId)}}">
          <span class="tier-dot" style="background:${{escapeHtml(basin.tierColor)}}"></span>
          <span>
            <strong>${{escapeHtml(basin.gaugeId)}} · ${{escapeHtml(basin.gaugeName)}}</strong>
            <small>${{escapeHtml(basin.tierLabel)}} · ${{basin.eventCount}} events</small>
          </span>
        </button>
      `).join("");
      container.querySelectorAll(".basin-row").forEach((button) => {{
        button.addEventListener("click", () => selectBasin(button.dataset.gaugeId));
      }});
    }}

    function selectBasin(gaugeId) {{
      const basin = basinById.get(gaugeId);
      if (!basin) return;
      selectedGaugeId = gaugeId;
      if (activeTier !== "all" && activeTier !== basin.tierKey) {{
        activeTier = basin.tierKey;
        setActiveTier(activeTier);
        selectedGaugeId = gaugeId;
      }}
      renderBasinList();
      renderBasinDetail();
      updateMapStyles();
      document.getElementById("basinDetail").scrollIntoView({{ block: "nearest" }});
    }}

    function stackStyle(counts) {{
      const near = Math.max(0, counts.near || 0);
      const shoulder = Math.max(0, counts.shoulder || 0);
      const far = Math.max(0, counts.far || 0);
      const extreme = Math.max(0, counts.extreme || 0);
      return `--near:${{near}}fr;--shoulder:${{shoulder}}fr;--far:${{far}}fr;--extreme:${{extreme}}fr;`;
    }}

    function renderBasinDetail() {{
      const container = document.getElementById("basinDetail");
      const basin = selectedGaugeId ? basinById.get(selectedGaugeId) : null;
      if (!basin) {{
        container.innerHTML = "<p class='selection-note'>선택된 basin이 없습니다.</p>";
        return;
      }}
      currentEvents = basin.events;
      container.innerHTML = `
        <div class="basin-title-row">
          <div>
            <h2>${{escapeHtml(basin.gaugeId)}} · ${{escapeHtml(basin.gaugeName)}}</h2>
            <p class="selection-note">${{escapeHtml(basin.state)}} · area ${{basin.area}} km² · Q99 ${{basin.obsQ99}} · Q99 events ${{basin.q99EventFrequency}}/yr</p>
            <div class="basin-legend-meta">
              ${{basin.legendMetadataLines.map((line) => `<span>${{escapeHtml(line)}}</span>`).join("")}}
            </div>
          </div>
          <span class="badge"><span class="tier-dot" style="background:${{escapeHtml(basin.tierColor)}}"></span>${{escapeHtml(basin.tierLabel)}}</span>
        </div>
        <div class="metric-grid">
          <div class="metric-card"><span>far/extreme records</span><strong>${{basin.farOrExtremeRecords}} / 18</strong></div>
          <div class="metric-card"><span>mean distance</span><strong>${{basin.meanDistance}} IQR</strong></div>
          <div class="metric-card"><span>max distance</span><strong>${{basin.maxDistance}} IQR</strong></div>
          <div class="metric-card"><span>RBI</span><strong>${{basin.rbi}}</strong></div>
        </div>
        <div class="stack" style="${{stackStyle(basin.distanceCounts)}}" title="near / shoulder / far / extreme record counts">
          <div></div><div></div><div></div><div></div>
        </div>
        <div class="metric-grid">
          <div class="metric-card"><span>NSE mean dist</span><strong>${{basin.nseMeanDistance}}</strong></div>
          <div class="metric-card"><span>KGE mean dist</span><strong>${{basin.kgeMeanDistance}}</strong></div>
          <div class="metric-card"><span>FHV mean dist</span><strong>${{basin.fhvMeanDistance}}</strong></div>
          <div class="metric-card"><span>{html.escape(plot_heading)}</span><strong>${{basin.eventCount}}</strong></div>
        </div>
        <div class="event-toolbar">
          <h3>{html.escape(plot_heading)}</h3>
          <small>${{basin.eventCount}} {html.escape(plot_count_label)}</small>
        </div>
        <div class="event-grid">
          ${{basin.events.map((event, index) => renderEventCard(event, index)).join("")}}
        </div>
      `;
      container.querySelectorAll(".plot-button").forEach((button) => {{
        button.addEventListener("click", () => openLightbox(Number(button.dataset.eventIndex)));
      }});
    }}

    function renderEventCard(event, index) {{
      return `
        <article class="event-card">
          <button class="plot-button" type="button" data-event-index="${{index}}">
            <img src="${{escapeHtml(event.plotPath)}}" loading="lazy" alt="${{escapeHtml(event.eventId)}}">
          </button>
          <div class="event-copy">
            <h4>${{escapeHtml(event.eventId)}}</h4>
            <p>${{escapeHtml(event.rainCohort)}} · ${{escapeHtml(event.stressGroup)}} · ${{escapeHtml(event.responseClass)}}</p>
            <p>ARI100 ratio ${{event.maxPrecAri100}} · obs/flood2 ${{event.obsToFlood2}} · obs/flood25 ${{event.obsToFlood25}}</p>
            <p>rain peak ${{escapeHtml(event.rainPeak)}} · obs peak ${{escapeHtml(event.observedPeakTime)}}</p>
          </div>
        </article>
      `;
    }}

    function renderLightbox(index) {{
      if (!currentEvents.length) return;
      currentEventIndex = (index + currentEvents.length) % currentEvents.length;
      const event = currentEvents[currentEventIndex];
      const image = document.getElementById("lightboxImage");
      const caption = document.getElementById("lightboxCaption");
      const position = document.getElementById("lightboxPosition");
      const prevButton = document.getElementById("lightboxPrev");
      const nextButton = document.getElementById("lightboxNext");
      image.src = event.plotPath;
      image.alt = event.eventId;
      caption.textContent = `${{event.eventId}} · ${{event.rainCohort}} · ${{event.stressGroup}} · ${{event.responseClass}}`;
      position.textContent = `${{currentEventIndex + 1}} / ${{currentEvents.length}}`;
      const hideNav = currentEvents.length <= 1;
      prevButton.hidden = hideNav;
      nextButton.hidden = hideNav;
    }}

    function openLightbox(index) {{
      const event = currentEvents[index];
      if (!event) return;
      const lightbox = document.getElementById("lightbox");
      lightbox.hidden = false;
      document.body.classList.add("lightbox-open");
      renderLightbox(index);
      const nextButton = document.getElementById("lightboxNext");
      if (!nextButton.hidden) nextButton.focus();
    }}

    function moveLightbox(delta) {{
      const lightbox = document.getElementById("lightbox");
      if (lightbox.hidden) return;
      renderLightbox(currentEventIndex + delta);
    }}

    function closeLightbox() {{
      const lightbox = document.getElementById("lightbox");
      lightbox.hidden = true;
      document.getElementById("lightboxImage").src = "";
      document.getElementById("lightboxCaption").textContent = "";
      document.getElementById("lightboxPosition").textContent = "";
      document.body.classList.remove("lightbox-open");
    }}

    document.querySelectorAll(".tier-button, .all-button").forEach((button) => {{
      button.addEventListener("click", () => setActiveTier(button.dataset.tierKey));
    }});
    document.querySelectorAll(".basin-shape").forEach((shape) => {{
      shape.addEventListener("click", () => selectBasin(shape.dataset.gaugeId));
      shape.addEventListener("keydown", (event) => {{
        if (event.key === "Enter" || event.key === " ") {{
          event.preventDefault();
          selectBasin(shape.dataset.gaugeId);
        }}
      }});
    }});
    document.querySelectorAll("[data-close-lightbox]").forEach((node) => {{
      node.addEventListener("click", closeLightbox);
    }});
    document.getElementById("lightboxPrev").addEventListener("click", () => moveLightbox(-1));
    document.getElementById("lightboxNext").addEventListener("click", () => moveLightbox(1));
    document.addEventListener("keydown", (event) => {{
      const lightbox = document.getElementById("lightbox");
      if (lightbox.hidden) return;
      if (event.key === "Escape") {{
        closeLightbox();
      }} else if (event.key === "ArrowLeft") {{
        event.preventDefault();
        moveLightbox(-1);
      }} else if (event.key === "ArrowRight") {{
        event.preventDefault();
        moveLightbox(1);
      }}
    }});

    setActiveTier("all");
  </script>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    args.output_html.parent.mkdir(parents=True, exist_ok=True)
    events, tiers, selected = read_inputs(args)
    basin_records = build_basin_records(events, tiers, selected)
    boundary_geometry, boundary_rings = load_boundary_geometry(args.drbc_boundary)
    basin_rings = load_basin_rings(
        args.camelsh_shapefile,
        set(basin_records),
        clip_geometry=boundary_geometry,
    )
    svg = build_svg(
        basin_rings=basin_rings,
        boundary_rings=boundary_rings,
        basin_rows=basin_records,
        width=args.svg_width,
        height=args.svg_height,
        simplify_px=args.simplify_px,
    )
    summary = build_summary(basin_records)
    page = render_html(svg=svg, basin_records=basin_records, summary=summary, args=args)
    args.output_html.write_text(page, encoding="utf-8")
    print(f"Wrote {args.output_html}")
    print(f"Basins: {summary['basins']} | events: {summary['events']}")


if __name__ == "__main__":
    main()
