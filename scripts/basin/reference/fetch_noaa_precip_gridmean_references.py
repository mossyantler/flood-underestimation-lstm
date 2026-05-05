#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=1.26",
#   "pandas>=2.2",
#   "pyshp>=2.3",
# ]
# ///

from __future__ import annotations

import argparse
import json
import math
import re
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_OUTPUT_DIR = Path("output/basin/all")
DEFAULT_INPUT_CSV = (
    DEFAULT_OUTPUT_DIR
    / "reference_comparison/noaa_prec/tables/return_period_reference_table_with_usgs_noaa14.csv"
)
DEFAULT_SHAPEFILE = Path("basins/CAMELSH_data/shapefiles/CAMELSH_shapefile.shp")
DEFAULT_METADATA_CSV = Path("basins/CAMELSH_data/attributes/attributes_gageii_BasinID.csv")

NOAA_GIS_BASE_URL = "https://hdsc.nws.noaa.gov/pub/hdsc/data"
NOAA_ATLAS14_GIS_URL = "https://hdsc.nws.noaa.gov/pfds/pfds_gis.html"
NOAA_ATLAS2_URL = "https://www.weather.gov/owp/hdsc_noaa_atlas2"

NOAA_SERIES = ("ams", "pds")
RETURN_PERIODS = (2, 5, 10, 25, 50, 100)
DURATIONS = {
    1: "60m",
    6: "06h",
    24: "24h",
    72: "03d",
}
ATLAS14_VOLUMES = ("orb", "ne", "mw", "se", "sw", "tx", "inw")
ATLAS2_STATES = {
    "OR": ("oregon", "or"),
    "WA": ("washington", "wa"),
}
ATLAS2_PERIODS = (2, 100)
ATLAS2_DURATIONS = (6, 24)

NLDAS_LON0 = -124.9375
NLDAS_LAT0 = 25.0625
NLDAS_DX = 0.125
NLDAS_NLON = 464
NLDAS_NLAT = 224

ATLAS14_SCALE_TO_MM = 0.0254
ATLAS2_SCALE_TO_MM = 25.4 / 100000.0


@dataclass(frozen=True)
class RasterGrid:
    values_mm: np.ndarray
    xllcorner: float
    yllcorner: float
    cellsize: float
    nodata: float

    @property
    def nrows(self) -> int:
        return int(self.values_mm.shape[0])

    @property
    def ncols(self) -> int:
        return int(self.values_mm.shape[1])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sample NOAA precipitation-frequency GIS grids at CAMELSH/NLDAS basin-mask cells "
            "and append basin-mean references next to CAMELSH prec_ari proxy columns."
        )
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=None,
        help=(
            "Input reference table. Defaults to "
            "output/basin/all/reference_comparison/noaa_prec/tables/"
            "return_period_reference_table_with_usgs_noaa14.csv."
        ),
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-csv", type=Path, default=None)
    parser.add_argument("--shapefile", type=Path, default=DEFAULT_SHAPEFILE)
    parser.add_argument("--metadata-csv", type=Path, default=DEFAULT_METADATA_CSV)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Defaults to <output-dir>/cache/noaa_gridmean.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional first-N basin limit after gauge filtering.")
    parser.add_argument("--gauge-id", action="append", default=[], help="Optional gauge ID filter. Can repeat.")
    parser.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout in seconds.")
    parser.add_argument("--retries", type=int, default=2, help="Retries for NOAA GIS zip downloads.")
    parser.add_argument("--force-refresh", action="store_true", help="Redownload NOAA GIS zip files.")
    parser.add_argument("--force-mask-refresh", action="store_true", help="Recompute NLDAS mask cells for selected basins.")
    return parser.parse_args()


def normalize_gauge_id(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    if text.isdigit() and len(text) < 8:
        text = text.zfill(8)
    return text


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def resolve_input_csv(args: argparse.Namespace) -> Path:
    if args.input_csv is not None:
        return args.input_csv
    noaa_table_dir = args.output_dir / "reference_comparison" / "noaa_prec" / "tables"
    usgs_table_dir = args.output_dir / "reference_comparison" / "usgs_flood" / "tables"
    return_period_dir = args.output_dir / "analysis" / "return_period" / "tables"
    candidates = [
        noaa_table_dir / "return_period_reference_table_with_usgs_noaa14.csv",
        DEFAULT_INPUT_CSV,
        usgs_table_dir / "return_period_reference_table_with_usgs.csv",
        return_period_dir / "return_period_reference_table.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise SystemExit("No input CSV found. Expected one of: " + ", ".join(str(item) for item in candidates))


def default_output_csv(input_csv: Path) -> Path:
    if input_csv.stem.endswith("_gridmean"):
        return input_csv
    if input_csv.stem.endswith("_noaa14"):
        return input_csv.with_name(f"{input_csv.stem}_gridmean{input_csv.suffix}")
    return input_csv.with_name(f"{input_csv.stem}_with_noaa_gridmean{input_csv.suffix}")


def attach_metadata(reference: pd.DataFrame, metadata_csv: Path) -> pd.DataFrame:
    needed = {"state", "huc02", "lat_gage", "lng_gage"}
    if needed.issubset(reference.columns):
        return reference
    metadata = pd.read_csv(metadata_csv, dtype={"STAID": str, "HUC02": str})
    metadata["gauge_id"] = metadata["STAID"].map(normalize_gauge_id)
    rename = {
        "STATE": "state__metadata",
        "HUC02": "huc02__metadata",
        "LAT_GAGE": "lat_gage__metadata",
        "LNG_GAGE": "lng_gage__metadata",
    }
    cols = ["gauge_id"] + [col for col in rename if col in metadata.columns]
    metadata = metadata[cols].rename(columns=rename)
    merged = reference.merge(metadata, on="gauge_id", how="left")
    for col in ("state", "huc02", "lat_gage", "lng_gage"):
        incoming = f"{col}__metadata"
        if incoming not in merged.columns:
            continue
        if col in merged.columns:
            merged[col] = merged[col].combine_first(merged[incoming])
        else:
            merged[col] = merged[incoming]
        merged = merged.drop(columns=[incoming])
    return merged


def is_pnw_atlas14_gap(row: pd.Series) -> bool:
    state = str(row.get("state", "")).strip().upper()
    huc02 = str(row.get("huc02", "")).strip()
    if huc02.endswith(".0") and huc02[:-2].isdigit():
        huc02 = huc02[:-2]
    if huc02.isdigit():
        huc02 = huc02.zfill(2)
    return state in ATLAS2_STATES and huc02 == "17"


def nldas_grid() -> tuple[np.ndarray, np.ndarray]:
    lon = NLDAS_LON0 + NLDAS_DX * np.arange(NLDAS_NLON)
    lat = NLDAS_LAT0 + NLDAS_DX * np.arange(NLDAS_NLAT)
    return lon, lat


def points_in_ring(x: np.ndarray, y: np.ndarray, ring: list[tuple[float, float]]) -> np.ndarray:
    vertices = np.asarray(ring, dtype=float)
    finite = np.isfinite(vertices).all(axis=1)
    vertices = vertices[finite]
    if len(vertices) < 3:
        return np.zeros(x.shape, dtype=bool)

    xv = vertices[:, 0]
    yv = vertices[:, 1]
    inside = np.zeros(x.shape, dtype=bool)
    j = len(vertices) - 1
    for i in range(len(vertices)):
        xi = xv[i]
        yi = yv[i]
        xj = xv[j]
        yj = yv[j]
        crosses = (yi > y) != (yj > y)
        with np.errstate(divide="ignore", invalid="ignore"):
            x_at_y = (xj - xi) * (y - yi) / (yj - yi) + xi
        inside ^= crosses & (x < x_at_y)
        j = i
    return inside


def points_in_shape(x: np.ndarray, y: np.ndarray, rings: list[list[tuple[float, float]]]) -> np.ndarray:
    inside = np.zeros(x.shape, dtype=bool)
    for ring in rings:
        inside ^= points_in_ring(x, y, ring)
    return inside


def shape_to_rings(shape: Any) -> list[list[tuple[float, float]]]:
    parts = list(shape.parts) + [len(shape.points)]
    rings: list[list[tuple[float, float]]] = []
    for start, end in zip(parts[:-1], parts[1:], strict=True):
        ring = [(float(x), float(y)) for x, y in shape.points[start:end] if math.isfinite(x) and math.isfinite(y)]
        if len(ring) >= 3:
            rings.append(ring)
    return rings


def fallback_nearest_nldas_cell(
    rings: list[list[tuple[float, float]]], nldas_lon: np.ndarray, nldas_lat: np.ndarray
) -> tuple[int, int]:
    vertices = np.asarray([point for ring in rings for point in ring], dtype=float)
    if vertices.size == 0:
        raise ValueError("Basin polygon has no finite vertices.")
    col = np.rint((vertices[:, 0] - NLDAS_LON0) / NLDAS_DX).astype(int)
    row = np.rint((vertices[:, 1] - NLDAS_LAT0) / NLDAS_DX).astype(int)
    col = np.clip(col, 0, len(nldas_lon) - 1)
    row = np.clip(row, 0, len(nldas_lat) - 1)
    distance = (nldas_lon[col] - vertices[:, 0]) ** 2 + (nldas_lat[row] - vertices[:, 1]) ** 2
    index = int(np.nanargmin(distance))
    return int(row[index]), int(col[index])


def compute_mask_for_shape(
    gauge_id: str,
    shape: Any,
    nldas_lon: np.ndarray,
    nldas_lat: np.ndarray,
) -> list[dict[str, Any]]:
    rings = shape_to_rings(shape)
    if not rings:
        return []

    minx, miny, maxx, maxy = [float(item) for item in shape.bbox]
    lon_idx = np.where((nldas_lon >= minx) & (nldas_lon <= maxx))[0]
    lat_idx = np.where((nldas_lat >= miny) & (nldas_lat <= maxy))[0]

    rows: np.ndarray
    cols: np.ndarray
    method: str
    if len(lon_idx) and len(lat_idx):
        lon_mesh, lat_mesh = np.meshgrid(nldas_lon[lon_idx], nldas_lat[lat_idx])
        inside = points_in_shape(lon_mesh.ravel(), lat_mesh.ravel(), rings)
        if inside.any():
            row_mesh, col_mesh = np.meshgrid(lat_idx, lon_idx, indexing="ij")
            rows = row_mesh.ravel()[inside]
            cols = col_mesh.ravel()[inside]
            method = "polygon_contains_nldas_center"
        else:
            row, col = fallback_nearest_nldas_cell(rings, nldas_lon, nldas_lat)
            rows = np.asarray([row])
            cols = np.asarray([col])
            method = "nearest_nldas_center_to_polygon_vertex"
    else:
        row, col = fallback_nearest_nldas_cell(rings, nldas_lon, nldas_lat)
        rows = np.asarray([row])
        cols = np.asarray([col])
        method = "nearest_nldas_center_to_polygon_vertex"

    records = []
    seen: set[tuple[int, int]] = set()
    for row, col in zip(rows, cols, strict=False):
        key = (int(row), int(col))
        if key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "gauge_id": gauge_id,
                "nldas_row": int(row),
                "nldas_col": int(col),
                "nldas_lat": float(nldas_lat[int(row)]),
                "nldas_lon": float(nldas_lon[int(col)]),
                "cell_key": f"{int(row)}:{int(col)}",
                "mask_method": method,
            }
        )
    return records


def read_basin_shapes(shapefile_path: Path, gauge_ids: set[str]) -> dict[str, Any]:
    import shapefile

    shapes: dict[str, Any] = {}
    reader = shapefile.Reader(str(shapefile_path))
    for shape_record in reader.iterShapeRecords():
        record = shape_record.record.as_dict()
        gauge_id = normalize_gauge_id(record.get("GAGE_ID"))
        if gauge_id in gauge_ids:
            shapes[gauge_id] = shape_record.shape
    return shapes


def load_or_build_mask_cells(
    reference: pd.DataFrame,
    shapefile_path: Path,
    cache_dir: Path,
    force_mask_refresh: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cache_path = cache_dir / "nldas_mask_cells.csv"
    requested = set(reference["gauge_id"].map(normalize_gauge_id))
    existing = pd.DataFrame()
    if cache_path.exists() and not force_mask_refresh:
        existing = pd.read_csv(cache_path, dtype={"gauge_id": str, "cell_key": str})
        existing["gauge_id"] = existing["gauge_id"].map(normalize_gauge_id)

    cached = existing[existing["gauge_id"].isin(requested)].copy() if not existing.empty else pd.DataFrame()
    cached_ids = set(cached["gauge_id"].unique()) if not cached.empty else set()
    missing_ids = requested - cached_ids

    new_records: list[dict[str, Any]] = []
    missing_shape_ids: set[str] = set()
    if missing_ids:
        nldas_lon, nldas_lat = nldas_grid()
        shapes = read_basin_shapes(shapefile_path, missing_ids)
        for index, gauge_id in enumerate(sorted(missing_ids), start=1):
            shape = shapes.get(gauge_id)
            if shape is None:
                missing_shape_ids.add(gauge_id)
                continue
            new_records.extend(compute_mask_for_shape(gauge_id, shape, nldas_lon, nldas_lat))
            if index == 1 or index % 100 == 0 or index == len(missing_ids):
                print(f"  built NLDAS masks for {index}/{len(missing_ids)} uncached basins", flush=True)

    new_cells = pd.DataFrame(new_records)
    if force_mask_refresh and not existing.empty:
        existing = existing[~existing["gauge_id"].isin(requested)].copy()
    combined = pd.concat([existing, new_cells], ignore_index=True) if not existing.empty else new_cells
    if not combined.empty:
        combined = combined.drop_duplicates(["gauge_id", "cell_key"]).sort_values(["gauge_id", "nldas_row", "nldas_col"])
        combined.to_csv(cache_path, index=False)
    selected = combined[combined["gauge_id"].isin(requested)].copy() if not combined.empty else pd.DataFrame()

    summary = reference[["gauge_id"]].copy()
    if not selected.empty:
        counts = selected.groupby("gauge_id").size().rename("nldas_mask_cell_count")
        methods = selected.groupby("gauge_id")["mask_method"].agg(lambda values: ";".join(sorted(set(values))))
        summary = summary.merge(counts, on="gauge_id", how="left").merge(methods, on="gauge_id", how="left")
    else:
        summary["nldas_mask_cell_count"] = pd.NA
        summary["mask_method"] = pd.NA
    summary["nldas_mask_status"] = np.where(summary["nldas_mask_cell_count"].fillna(0).astype(float) > 0, "ok", "missing")
    summary.loc[summary["gauge_id"].isin(missing_shape_ids), "nldas_mask_status"] = "missing_shape"
    return selected, summary


def fetch_url(url: str, destination: Path, *, timeout: float, retries: int, force_refresh: bool) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not force_refresh:
        return destination
    headers = {"User-Agent": "CAMELS-flood-frequency-research/1.0 (NOAA GIS grid client)"}
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read()
            with tempfile.NamedTemporaryFile(delete=False, dir=str(destination.parent)) as tmp:
                tmp.write(data)
                tmp_path = Path(tmp.name)
            tmp_path.replace(destination)
            return destination
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.5 * (2**attempt))
                continue
            raise RuntimeError(f"Failed to download {url}: {last_error}") from last_error
    raise RuntimeError(f"Unreachable download retry state for {url}")


def atlas14_filename(volume: str, period: int, duration: int, series: str) -> str:
    duration_code = DURATIONS[duration]
    suffix = "_ams" if series == "ams" else ""
    return f"{volume}{period}yr{duration_code}a{suffix}.zip"


def atlas2_filename(state_abbrev: str, period: int, duration: int) -> str:
    return f"na2_{state_abbrev}_{period}yr{duration}hr.zip"


def read_ascii_grid_from_zip(path: Path, scale_to_mm: float) -> RasterGrid:
    with zipfile.ZipFile(path) as archive:
        asc_names = [name for name in archive.namelist() if name.lower().endswith(".asc")]
        if not asc_names:
            raise ValueError(f"No ArcInfo ASCII grid found in {path}")
        with archive.open(asc_names[0]) as handle:
            header: dict[str, float] = {}
            for _ in range(6):
                pieces = handle.readline().decode("utf-8", errors="replace").split()
                if len(pieces) >= 2:
                    header[pieces[0].lower()] = float(pieces[1])
            required = {"ncols", "nrows", "xllcorner", "yllcorner", "cellsize"}
            missing = required - set(header)
            if missing:
                raise ValueError(f"Missing ASCII grid header keys in {path}: {sorted(missing)}")
            nodata = header.get("nodata_value", header.get("nodata", -9999.0))
            values = np.loadtxt(handle, dtype=np.float32)

    nrows = int(header["nrows"])
    ncols = int(header["ncols"])
    if values.shape != (nrows, ncols):
        values = values.reshape((nrows, ncols))
    values = values.astype(np.float32, copy=False)
    values[np.isclose(values, nodata)] = np.nan
    values *= np.float32(scale_to_mm)
    return RasterGrid(
        values_mm=values,
        xllcorner=float(header["xllcorner"]),
        yllcorner=float(header["yllcorner"]),
        cellsize=float(header["cellsize"]),
        nodata=float(nodata),
    )


def sample_raster(grid: RasterGrid, cells: pd.DataFrame, nearest_valid_radius_cells: int = 0) -> np.ndarray:
    lon = cells["nldas_lon"].to_numpy(dtype=float)
    lat = cells["nldas_lat"].to_numpy(dtype=float)
    col = np.rint((lon - (grid.xllcorner + 0.5 * grid.cellsize)) / grid.cellsize).astype(int)
    row_from_bottom = np.rint((lat - (grid.yllcorner + 0.5 * grid.cellsize)) / grid.cellsize).astype(int)
    row = grid.nrows - 1 - row_from_bottom
    valid = (row >= 0) & (row < grid.nrows) & (col >= 0) & (col < grid.ncols)
    sampled = np.full(len(cells), np.nan, dtype=np.float32)
    if valid.any():
        sampled[valid] = grid.values_mm[row[valid], col[valid]]
    if nearest_valid_radius_cells > 0:
        missing = np.where(valid & np.isnan(sampled))[0]
        for index in missing:
            row0 = max(0, row[index] - nearest_valid_radius_cells)
            row1 = min(grid.nrows, row[index] + nearest_valid_radius_cells + 1)
            col0 = max(0, col[index] - nearest_valid_radius_cells)
            col1 = min(grid.ncols, col[index] + nearest_valid_radius_cells + 1)
            window = grid.values_mm[row0:row1, col0:col1]
            finite = np.isfinite(window)
            if not finite.any():
                continue
            local_rows, local_cols = np.where(finite)
            distance = (local_rows + row0 - row[index]) ** 2 + (local_cols + col0 - col[index]) ** 2
            best = int(np.argmin(distance))
            sampled[index] = window[local_rows[best], local_cols[best]]
    return sampled


def unique_cells(mask_cells: pd.DataFrame) -> pd.DataFrame:
    if mask_cells.empty:
        return pd.DataFrame(columns=["cell_key", "nldas_row", "nldas_col", "nldas_lat", "nldas_lon"])
    return (
        mask_cells[["cell_key", "nldas_row", "nldas_col", "nldas_lat", "nldas_lon"]]
        .drop_duplicates("cell_key")
        .sort_values(["nldas_row", "nldas_col"])
        .reset_index(drop=True)
    )


def sample_atlas14_for_cells(
    cells: pd.DataFrame,
    period: int,
    duration: int,
    series: str,
    *,
    zip_cache_dir: Path,
    timeout: float,
    retries: int,
    force_refresh: bool,
) -> np.ndarray:
    sampled = np.full(len(cells), np.nan, dtype=np.float32)
    for volume in ATLAS14_VOLUMES:
        if np.isfinite(sampled).all():
            break
        filename = atlas14_filename(volume, period, duration, series)
        url = f"{NOAA_GIS_BASE_URL}/{volume}/{filename}"
        zip_path = fetch_url(
            url,
            zip_cache_dir / "atlas14" / volume / filename,
            timeout=timeout,
            retries=retries,
            force_refresh=force_refresh,
        )
        grid = read_ascii_grid_from_zip(zip_path, ATLAS14_SCALE_TO_MM)
        volume_values = sample_raster(grid, cells)
        fill = np.isnan(sampled) & np.isfinite(volume_values)
        sampled[fill] = volume_values[fill]
    return sampled


def sample_atlas2_for_cells(
    cells: pd.DataFrame,
    period: int,
    duration: int,
    *,
    zip_cache_dir: Path,
    timeout: float,
    retries: int,
    force_refresh: bool,
) -> np.ndarray:
    sampled = np.full(len(cells), np.nan, dtype=np.float32)
    for state_name, state_abbrev in ATLAS2_STATES.values():
        if np.isfinite(sampled).all():
            break
        filename = atlas2_filename(state_abbrev, period, duration)
        url = f"{NOAA_GIS_BASE_URL}/{state_name}/{filename}"
        zip_path = fetch_url(
            url,
            zip_cache_dir / "atlas2" / state_name / filename,
            timeout=timeout,
            retries=retries,
            force_refresh=force_refresh,
        )
        grid = read_ascii_grid_from_zip(zip_path, ATLAS2_SCALE_TO_MM)
        state_values = sample_raster(grid, cells, nearest_valid_radius_cells=30)
        fill = np.isnan(sampled) & np.isfinite(state_values)
        sampled[fill] = state_values[fill]
    return sampled


def aggregate_cell_values(mask_cells: pd.DataFrame, cell_values: pd.DataFrame, value_cols: list[str]) -> pd.DataFrame:
    if mask_cells.empty or cell_values.empty:
        return pd.DataFrame(columns=["gauge_id"] + value_cols)
    merged = mask_cells[["gauge_id", "cell_key"]].merge(cell_values, on="cell_key", how="left")
    return merged.groupby("gauge_id", as_index=False)[value_cols].mean()


def add_noaa14_gridmean(reference: pd.DataFrame, mask_cells: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    output = reference.copy()
    pnw_mask = output.apply(is_pnw_atlas14_gap, axis=1)
    atlas14_ids = set(output.loc[~pnw_mask, "gauge_id"])
    atlas14_mask_cells = mask_cells[mask_cells["gauge_id"].isin(atlas14_ids)].copy()
    cells = unique_cells(atlas14_mask_cells)

    value_cols: list[str] = []
    cell_values = cells[["cell_key"]].copy()
    if not cells.empty:
        total = len(NOAA_SERIES) * len(RETURN_PERIODS) * len(DURATIONS)
        done = 0
        for series in NOAA_SERIES:
            for period in RETURN_PERIODS:
                for duration in DURATIONS:
                    done += 1
                    col = f"noaa14_gridmean_{series}_prec_ari{period}_{duration}h"
                    print(f"  sampling NOAA Atlas 14 grid {done}/{total}: {series} {period}y {duration}h", flush=True)
                    cell_values[col] = sample_atlas14_for_cells(
                        cells,
                        period,
                        duration,
                        series,
                        zip_cache_dir=args.cache_dir,
                        timeout=args.timeout,
                        retries=args.retries,
                        force_refresh=args.force_refresh,
                    )
                    value_cols.append(col)
    else:
        for series in NOAA_SERIES:
            for period in RETURN_PERIODS:
                for duration in DURATIONS:
                    value_cols.append(f"noaa14_gridmean_{series}_prec_ari{period}_{duration}h")

    means = aggregate_cell_values(atlas14_mask_cells, cell_values, value_cols)
    output = output.merge(means, on="gauge_id", how="left")

    output["noaa14_gridmean_prec_ari_unit"] = "mm"
    output["noaa14_gridmean_prec_ari_statistic"] = "mean"
    output["noaa14_gridmean_spatial_support"] = "CAMELSH_NLDAS_basin_mask_grid_cell_mean"
    output["noaa14_gridmean_source"] = "NOAA_Atlas_14_PFDS_GIS_precipitation_frequency_grids"
    output["noaa14_gridmean_service_url"] = NOAA_ATLAS14_GIS_URL
    output["noaa14_gridmean_unsupported_reason"] = pd.NA
    output.loc[pnw_mask, "noaa14_gridmean_unsupported_reason"] = (
        "NOAA Atlas 14 PFDS returns outside-project-area for Oregon/Washington HUC02=17; "
        "NOAA Atlas 2 fallback is stored in noaa2_gridmean_* columns where available."
    )

    mask_missing = output["noaa14_gridmean_nldas_cell_count"].fillna(0).astype(float) <= 0
    for series in NOAA_SERIES:
        series_cols = [
            f"noaa14_gridmean_{series}_prec_ari{period}_{duration}h"
            for period in RETURN_PERIODS
            for duration in DURATIONS
        ]
        finite_count = output[series_cols].notna().sum(axis=1)
        status = pd.Series("ok", index=output.index, dtype=object)
        status[finite_count < len(series_cols)] = "partial"
        status[finite_count == 0] = "no_coverage"
        status[pnw_mask] = "outside_atlas14_project_area"
        status[mask_missing] = "missing_mask"
        output[f"noaa14_gridmean_{series}_fetch_status"] = status

    status_cols = [f"noaa14_gridmean_{series}_fetch_status" for series in NOAA_SERIES]
    output["noaa14_gridmean_fetch_status"] = "ok"
    output.loc[output[status_cols].eq("partial").any(axis=1), "noaa14_gridmean_fetch_status"] = "partial"
    output.loc[output[status_cols].eq("no_coverage").all(axis=1), "noaa14_gridmean_fetch_status"] = "no_coverage"
    output.loc[
        output[status_cols].eq("outside_atlas14_project_area").all(axis=1),
        "noaa14_gridmean_fetch_status",
    ] = "outside_atlas14_project_area"
    output.loc[output[status_cols].eq("missing_mask").all(axis=1), "noaa14_gridmean_fetch_status"] = "missing_mask"
    return output


def add_noaa2_gridmean(reference: pd.DataFrame, mask_cells: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    output = reference.copy()
    pnw_mask = output.apply(is_pnw_atlas14_gap, axis=1)
    pnw_ids = set(output.loc[pnw_mask, "gauge_id"])
    pnw_mask_cells = mask_cells[mask_cells["gauge_id"].isin(pnw_ids)].copy()
    cells = unique_cells(pnw_mask_cells)

    value_cols: list[str] = []
    cell_values = cells[["cell_key"]].copy()
    if not cells.empty:
        total = len(ATLAS2_PERIODS) * len(ATLAS2_DURATIONS)
        done = 0
        for period in ATLAS2_PERIODS:
            for duration in ATLAS2_DURATIONS:
                done += 1
                col = f"noaa2_gridmean_prec_ari{period}_{duration}h"
                print(f"  sampling NOAA Atlas 2 fallback grid {done}/{total}: {period}y {duration}h", flush=True)
                cell_values[col] = sample_atlas2_for_cells(
                    cells,
                    period,
                    duration,
                    zip_cache_dir=args.cache_dir,
                    timeout=args.timeout,
                    retries=args.retries,
                    force_refresh=args.force_refresh,
                )
                value_cols.append(col)
    else:
        for period in ATLAS2_PERIODS:
            for duration in ATLAS2_DURATIONS:
                value_cols.append(f"noaa2_gridmean_prec_ari{period}_{duration}h")

    means = aggregate_cell_values(pnw_mask_cells, cell_values, value_cols)
    output = output.merge(means, on="gauge_id", how="left")

    output["noaa2_gridmean_prec_ari_unit"] = "mm"
    output["noaa2_gridmean_spatial_support"] = "CAMELSH_NLDAS_basin_mask_grid_cell_mean"
    output["noaa2_gridmean_source"] = "NOAA_Atlas_2_GIS_precipitation_frequency_grids_OR_WA"
    output["noaa2_gridmean_service_url"] = NOAA_ATLAS2_URL
    output["noaa2_gridmean_unsupported_reason"] = (
        "NOAA Atlas 2 fallback is only populated for Oregon/Washington HUC02=17 and only "
        "for 2/100-year 6/24h combinations; Atlas 14 remains the source elsewhere."
    )
    output.loc[pnw_mask, "noaa2_gridmean_unsupported_reason"] = (
        "NOAA Atlas 2 provides only 2/100-year 6/24h GIS grids for Oregon/Washington; "
        "1h, 72h, and 5/10/25/50-year combinations are not available in this fallback."
    )
    mask_missing = output["noaa14_gridmean_nldas_cell_count"].fillna(0).astype(float) <= 0
    finite_count = output[value_cols].notna().sum(axis=1)
    status = pd.Series("not_applicable", index=output.index, dtype=object)
    status[pnw_mask & (finite_count == len(value_cols))] = "ok"
    status[pnw_mask & (finite_count > 0) & (finite_count < len(value_cols))] = "partial"
    status[pnw_mask & (finite_count == 0)] = "no_coverage"
    status[pnw_mask & mask_missing] = "missing_mask"
    output["noaa2_gridmean_fetch_status"] = status
    return output


def add_comparison_columns(frame: pd.DataFrame) -> pd.DataFrame:
    comparison: dict[str, pd.Series] = {}
    for series in NOAA_SERIES:
        for period in RETURN_PERIODS:
            for duration in DURATIONS:
                camelsh_col = f"prec_ari{period}_{duration}h"
                noaa_col = f"noaa14_gridmean_{series}_prec_ari{period}_{duration}h"
                if camelsh_col not in frame.columns or noaa_col not in frame.columns:
                    continue
                camelsh = pd.to_numeric(frame[camelsh_col], errors="coerce")
                noaa = pd.to_numeric(frame[noaa_col], errors="coerce")
                comparison[f"noaa14_gridmean_{series}_to_camelsh_prec_ari{period}_{duration}h"] = noaa / camelsh
                comparison[f"camelsh_minus_noaa14_gridmean_{series}_prec_ari{period}_{duration}h"] = camelsh - noaa
                comparison[f"camelsh_minus_noaa14_gridmean_{series}_prec_ari{period}_{duration}h_relative"] = (
                    camelsh - noaa
                ) / noaa

    for period in ATLAS2_PERIODS:
        for duration in ATLAS2_DURATIONS:
            camelsh_col = f"prec_ari{period}_{duration}h"
            noaa_col = f"noaa2_gridmean_prec_ari{period}_{duration}h"
            if camelsh_col not in frame.columns or noaa_col not in frame.columns:
                continue
            camelsh = pd.to_numeric(frame[camelsh_col], errors="coerce")
            noaa = pd.to_numeric(frame[noaa_col], errors="coerce")
            comparison[f"noaa2_gridmean_to_camelsh_prec_ari{period}_{duration}h"] = noaa / camelsh
            comparison[f"camelsh_minus_noaa2_gridmean_prec_ari{period}_{duration}h"] = camelsh - noaa
            comparison[f"camelsh_minus_noaa2_gridmean_prec_ari{period}_{duration}h_relative"] = (camelsh - noaa) / noaa

    if not comparison:
        return frame
    return pd.concat([frame, pd.DataFrame(comparison, index=frame.index)], axis=1)


def drop_existing_gridmean_columns(frame: pd.DataFrame) -> pd.DataFrame:
    patterns = (
        "noaa14_gridmean_",
        "noaa2_gridmean_",
        "camelsh_minus_noaa14_gridmean_",
        "camelsh_minus_noaa2_gridmean_",
    )
    drop_cols = [
        col
        for col in frame.columns
        if col.startswith(patterns)
        or col.startswith("noaa14_gridmean")
        or col.startswith("noaa2_gridmean")
        or "_noaa14_gridmean_" in col
        or "_noaa2_gridmean_" in col
    ]
    return frame.drop(columns=drop_cols, errors="ignore")


def insert_gridmean_columns_near_prec_proxy(frame: pd.DataFrame) -> pd.DataFrame:
    desired: list[str] = []
    used: set[str] = set()
    for col in frame.columns:
        if col in used:
            continue
        desired.append(col)
        used.add(col)
        match = re.fullmatch(r"prec_ari(\d+)_(\d+)h", col)
        if not match:
            continue
        period = int(match.group(1))
        duration = int(match.group(2))
        for series in NOAA_SERIES:
            for extra in [
                f"noaa14_gridmean_{series}_prec_ari{period}_{duration}h",
                f"noaa14_gridmean_{series}_to_camelsh_prec_ari{period}_{duration}h",
                f"camelsh_minus_noaa14_gridmean_{series}_prec_ari{period}_{duration}h",
                f"camelsh_minus_noaa14_gridmean_{series}_prec_ari{period}_{duration}h_relative",
            ]:
                if extra in frame.columns and extra not in used:
                    desired.append(extra)
                    used.add(extra)
        if period in ATLAS2_PERIODS and duration in ATLAS2_DURATIONS:
            for extra in [
                f"noaa2_gridmean_prec_ari{period}_{duration}h",
                f"noaa2_gridmean_to_camelsh_prec_ari{period}_{duration}h",
                f"camelsh_minus_noaa2_gridmean_prec_ari{period}_{duration}h",
                f"camelsh_minus_noaa2_gridmean_prec_ari{period}_{duration}h_relative",
            ]:
                if extra in frame.columns and extra not in used:
                    desired.append(extra)
                    used.add(extra)
    desired.extend(col for col in frame.columns if col not in used)
    return frame.reindex(columns=desired)


def write_reports(frame: pd.DataFrame, mask_cells: pd.DataFrame, args: argparse.Namespace, output_csv: Path) -> None:
    metadata_dir = args.output_dir / "reference_comparison" / "noaa_prec" / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    selected_mask_path = args.cache_dir / "nldas_mask_cells_selected.csv"
    if not mask_cells.empty:
        mask_cells.to_csv(selected_mask_path, index=False)

    report_cols = [
        "gauge_id",
        "state",
        "huc02",
        "noaa14_gridmean_fetch_status",
        "noaa14_gridmean_unsupported_reason",
        "noaa2_gridmean_fetch_status",
        "noaa2_gridmean_unsupported_reason",
        "noaa14_gridmean_nldas_cell_count",
        "noaa14_gridmean_mask_method",
    ]
    report_cols = [col for col in report_cols if col in frame.columns]
    report = frame[
        frame.get("noaa14_gridmean_fetch_status", pd.Series(index=frame.index, dtype=object)).ne("ok")
        | frame.get("noaa2_gridmean_fetch_status", pd.Series(index=frame.index, dtype=object)).isin(["ok", "partial"])
    ][report_cols].copy()
    report_path = metadata_dir / "noaa_gridmean_unsupported_fallback_report.csv"
    report.to_csv(report_path, index=False)

    noaa14_cols = [col for col in frame.columns if re.fullmatch(r"noaa14_gridmean_(ams|pds)_prec_ari\d+_\d+h", col)]
    noaa2_cols = [col for col in frame.columns if re.fullmatch(r"noaa2_gridmean_prec_ari\d+_\d+h", col)]
    summary = {
        "input_csv": str(args.input_csv),
        "output_csv": str(output_csv),
        "cache_dir": str(args.cache_dir),
        "shapefile": str(args.shapefile),
        "station_count": int(len(frame)),
        "nldas_mask_cell_table": str(selected_mask_path),
        "unsupported_fallback_report": str(report_path),
        "noaa14_status_counts": frame["noaa14_gridmean_fetch_status"].value_counts(dropna=False).to_dict(),
        "noaa2_status_counts": frame["noaa2_gridmean_fetch_status"].value_counts(dropna=False).to_dict(),
        "noaa14_non_null_counts": {col: int(pd.to_numeric(frame[col], errors="coerce").notna().sum()) for col in noaa14_cols},
        "noaa2_non_null_counts": {col: int(pd.to_numeric(frame[col], errors="coerce").notna().sum()) for col in noaa2_cols},
        "nldas_grid": {
            "lon_count": NLDAS_NLON,
            "lat_count": NLDAS_NLAT,
            "lower_left_center": [NLDAS_LON0, NLDAS_LAT0],
            "upper_right_center": [
                NLDAS_LON0 + NLDAS_DX * (NLDAS_NLON - 1),
                NLDAS_LAT0 + NLDAS_DX * (NLDAS_NLAT - 1),
            ],
            "cellsize_degrees": NLDAS_DX,
        },
        "unit": "mm",
        "atlas14_source": NOAA_ATLAS14_GIS_URL,
        "atlas2_source": NOAA_ATLAS2_URL,
    }
    summary_path = metadata_dir / "noaa_gridmean_precip_reference_summary.json"
    summary_path.write_text(json.dumps(json_safe(summary), indent=2), encoding="utf-8")
    print(f"Wrote summary: {summary_path}", flush=True)
    print(json.dumps(json_safe(summary), indent=2), flush=True)


def main() -> None:
    args = parse_args()
    table_dir = args.output_dir / "reference_comparison" / "noaa_prec" / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)
    args.input_csv = resolve_input_csv(args)
    output_csv = args.output_csv or table_dir / default_output_csv(args.input_csv).name
    args.cache_dir = args.cache_dir or args.output_dir / "cache" / "noaa_gridmean"
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    reference = pd.read_csv(args.input_csv, dtype={"gauge_id": str, "huc02": str})
    reference["gauge_id"] = reference["gauge_id"].map(normalize_gauge_id)
    reference = reference.drop_duplicates("gauge_id").sort_values("gauge_id").reset_index(drop=True)
    if args.gauge_id:
        requested = {normalize_gauge_id(item) for item in args.gauge_id}
        reference = reference[reference["gauge_id"].isin(requested)].copy()
    if args.limit is not None:
        reference = reference.head(args.limit).copy()
    if reference.empty:
        raise SystemExit("No basins matched the requested input/filter options.")
    reference = attach_metadata(reference, args.metadata_csv)
    reference = drop_existing_gridmean_columns(reference)

    print(f"Building/loading CAMELSH NLDAS basin masks for {len(reference)} basins", flush=True)
    mask_cells, mask_summary = load_or_build_mask_cells(
        reference,
        args.shapefile,
        args.cache_dir,
        force_mask_refresh=args.force_mask_refresh,
    )
    reference = reference.merge(mask_summary, on="gauge_id", how="left")
    reference = reference.rename(
        columns={
            "nldas_mask_cell_count": "noaa14_gridmean_nldas_cell_count",
            "mask_method": "noaa14_gridmean_mask_method",
            "nldas_mask_status": "noaa14_gridmean_mask_status",
        }
    )

    print("Sampling NOAA Atlas 14 GIS grids for non-PNW basin-mask cells", flush=True)
    merged = add_noaa14_gridmean(reference, mask_cells, args)
    print("Sampling NOAA Atlas 2 fallback GIS grids for Oregon/Washington Atlas 14 gap basins", flush=True)
    merged = add_noaa2_gridmean(merged, mask_cells, args)
    merged = add_comparison_columns(merged)
    merged = insert_gridmean_columns_near_prec_proxy(merged)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_csv, index=False)
    print(f"Wrote merged table: {output_csv}", flush=True)
    write_reports(merged, mask_cells, args, output_csv)


if __name__ == "__main__":
    main()
