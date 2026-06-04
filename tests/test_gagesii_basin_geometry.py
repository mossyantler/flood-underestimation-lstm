from __future__ import annotations

import json
import sys
from pathlib import Path

import pyproj
import pytest
from shapely.geometry import Polygon, mapping
from shapely.ops import transform

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "archive" / "model" / "extreme_rain"
sys.path.insert(0, str(SCRIPT_DIR))

from build_extreme_rain_median_map_index import (  # noqa: E402
    MAP_CRS,
    load_gagesii_api_basin_rings,
)


def _project_to_map_crs(geometry):
    transformer = pyproj.Transformer.from_crs("EPSG:4326", MAP_CRS, always_xy=True)
    return transform(transformer.transform, geometry)


def test_load_gagesii_api_basin_rings_uses_cached_crs84_geometry_and_clips_to_5070(tmp_path: Path):
    gauge_id = "01447680"
    lonlat_polygon = Polygon(
        [
            (-75.42, 41.00),
            (-75.30, 41.00),
            (-75.30, 41.12),
            (-75.42, 41.12),
            (-75.42, 41.00),
        ]
    )
    feature_collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": gauge_id,
                "properties": {"gage_id": gauge_id},
                "geometry": mapping(lonlat_polygon),
            }
        ],
    }
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / f"{gauge_id}.geojson").write_text(json.dumps(feature_collection), encoding="utf-8")

    clip_geometry = _project_to_map_crs(
        Polygon(
            [
                (-75.40, 41.02),
                (-75.32, 41.02),
                (-75.32, 41.10),
                (-75.40, 41.10),
                (-75.40, 41.02),
            ]
        )
    )

    rings = load_gagesii_api_basin_rings({gauge_id}, clip_geometry, cache_dir=cache_dir)

    assert set(rings) == {gauge_id}
    assert rings[gauge_id]
    xs = [x for ring in rings[gauge_id] for x, _y in ring]
    ys = [y for ring in rings[gauge_id] for _x, y in ring]
    clip_minx, clip_miny, clip_maxx, clip_maxy = clip_geometry.bounds
    assert min(xs) >= clip_minx - 1.0
    assert max(xs) <= clip_maxx + 1.0
    assert min(ys) >= clip_miny - 1.0
    assert max(ys) <= clip_maxy + 1.0
