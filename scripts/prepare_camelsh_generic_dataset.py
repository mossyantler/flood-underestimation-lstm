#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pandas>=2.2",
#   "xarray>=2024.1",
#   "netcdf4>=1.7",
#   "py7zr>=0.22",
# ]
# ///

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd
import py7zr
import xarray as xr


RECORD_ID = "15066778"
ARCHIVE_KEY = "timeseries.7z"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare a CAMELSH GenericDataset for NeuralHydrology by extracting selected hourly basin NetCDF files "
            "and creating a curated static-attributes CSV."
        )
    )
    parser.add_argument(
        "--profile",
        choices=["broad", "natural"],
        default="broad",
        help="Which DRBC holdout profile to prepare.",
    )
    parser.add_argument(
        "--archive-path",
        type=Path,
        default=Path("basins/CAMELSH_download/timeseries.7z"),
        help="Path to the CAMELSH timeseries archive.",
    )
    parser.add_argument(
        "--download-if-missing",
        action="store_true",
        help="Download the archive from Zenodo if it does not exist locally.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/CAMELSH_generic"),
        help="Root directory where the prepared GenericDataset will be written.",
    )
    parser.add_argument(
        "--force-reextract",
        action="store_true",
        help="Re-extract basin NetCDF files even if they already exist in the output directory.",
    )
    return parser.parse_args()


def basin_split_paths(profile: str) -> dict[str, Path]:
    splits_dir = Path("configs/basin_splits")
    if profile == "broad":
        return {
            "train": splits_dir / "drbc_holdout_train_broad.txt",
            "validation": splits_dir / "drbc_holdout_validation_broad.txt",
            "test": splits_dir / "drbc_holdout_test_drbc_quality.txt",
        }
    return {
        "train": splits_dir / "drbc_holdout_train_natural.txt",
        "validation": splits_dir / "drbc_holdout_validation_natural.txt",
        "test": splits_dir / "drbc_holdout_test_drbc_quality_natural.txt",
    }


def load_split_basins(paths: dict[str, Path]) -> dict[str, list[str]]:
    split_basins: dict[str, list[str]] = {}
    for split, path in paths.items():
        split_basins[split] = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    return split_basins


def flatten_split_basins(split_basins: dict[str, list[str]]) -> set[str]:
    basin_ids: set[str] = set()
    for basins in split_basins.values():
        basin_ids.update(basins)
    return basin_ids


def fetch_record(record_id: str) -> dict:
    with urllib.request.urlopen(f"https://zenodo.org/api/records/{record_id}", timeout=120) as response:
        return json.load(response)


def get_archive_file_info(record: dict[str, Any]) -> dict[str, Any]:
    for file_info in record["files"]:
        if file_info["key"] == ARCHIVE_KEY:
            return file_info
    raise SystemExit(f"Zenodo record {RECORD_ID}에 `{ARCHIVE_KEY}` 파일이 없습니다.")


def format_bytes(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024.0 or unit == "TB":
            return f"{value:.1f}{unit}"
        value /= 1024.0
    return f"{num_bytes}B"


def ensure_archive(archive_path: Path, download_if_missing: bool) -> None:
    if archive_path.name != ARCHIVE_KEY:
        if archive_path.exists():
            print(f"Using local archive: {archive_path}")
            return
        raise SystemExit(
            f"지정한 로컬 아카이브가 없습니다: {archive_path}\n"
            "로컬 ZIP/7z 파일 경로를 확인하거나 기본 `timeseries.7z`를 사용하세요."
        )

    record = fetch_record(RECORD_ID)
    file_info = get_archive_file_info(record)
    expected_size = int(file_info["size"])
    url = file_info["links"]["self"]

    if archive_path.exists():
        current_size = archive_path.stat().st_size
        if current_size == expected_size:
            print(
                f"Archive already available: {archive_path} "
                f"({format_bytes(current_size)} / {format_bytes(expected_size)})"
            )
            return
        if current_size > expected_size:
            print(
                f"Archive size exceeds expected size. Re-downloading: "
                f"{format_bytes(current_size)} > {format_bytes(expected_size)}"
            )
            archive_path.unlink()
            current_size = 0
        elif not download_if_missing:
            raise SystemExit(
                f"아카이브가 부분 다운로드 상태입니다: {archive_path}\n"
                f"현재 {format_bytes(current_size)} / 예상 {format_bytes(expected_size)}\n"
                "이어받으려면 `--download-if-missing` 옵션을 사용하세요."
            )
        else:
            print(
                f"Resuming archive download: {archive_path} "
                f"({format_bytes(current_size)} / {format_bytes(expected_size)})"
            )
    else:
        if not download_if_missing:
            raise SystemExit(
                f"아카이브가 없습니다: {archive_path}\n"
                "필요하면 `--download-if-missing` 옵션으로 Zenodo에서 자동 다운로드할 수 있습니다."
            )
        current_size = 0
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading archive: {archive_path} ({format_bytes(expected_size)})")

    headers = {}
    mode = "wb"
    if current_size > 0:
        headers["Range"] = f"bytes={current_size}-"
        mode = "ab"

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        if current_size > 0 and getattr(response, "status", None) != 206:
            print("Range 요청을 지원하지 않아 처음부터 다시 다운로드합니다.")
            current_size = 0
            mode = "wb"

        downloaded = current_size
        next_report = downloaded + 512 * 1024 * 1024
        with archive_path.open(mode) as fp:
            while True:
                chunk = response.read(8 * 1024 * 1024)
                if not chunk:
                    break
                fp.write(chunk)
                downloaded += len(chunk)
                if downloaded >= next_report or downloaded == expected_size:
                    percent = downloaded / expected_size * 100
                    print(
                        f"Download progress: {format_bytes(downloaded)} / "
                        f"{format_bytes(expected_size)} ({percent:.1f}%)"
                    )
                    next_report = downloaded + 512 * 1024 * 1024

    final_size = archive_path.stat().st_size
    if final_size != expected_size:
        raise SystemExit(
            f"다운로드가 완료되지 않았습니다: {format_bytes(final_size)} / {format_bytes(expected_size)}"
        )


def standardize_netcdf(source_path: Path, target_path: Path) -> None:
    ds = xr.open_dataset(source_path)

    if "date" not in ds.coords:
        if "DateTime" in ds.coords:
            ds = ds.rename({"DateTime": "date"})
        elif "time" in ds.coords:
            ds = ds.rename({"time": "date"})
        elif "DateTime" in ds.dims:
            ds = ds.rename({"DateTime": "date"})
        elif "time" in ds.dims:
            ds = ds.rename({"time": "date"})
        else:
            raise ValueError(f"`date` coordinate를 찾지 못했습니다: {source_path}")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(target_path)
    ds.close()


def list_archive_members(archive_path: Path) -> list[str]:
    suffix = archive_path.suffix.lower()
    if suffix == ".7z":
        with py7zr.SevenZipFile(archive_path, mode="r") as archive:
            return archive.getnames()
    if suffix == ".zip":
        result = subprocess.run(
            ["bsdtar", "-tf", str(archive_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    raise SystemExit(f"지원하지 않는 아카이브 형식입니다: {archive_path}")


def extract_archive_batch(archive_path: Path, targets: list[str], output_dir: Path) -> None:
    suffix = archive_path.suffix.lower()
    if suffix == ".7z":
        with py7zr.SevenZipFile(archive_path, mode="r") as archive:
            archive.extract(path=output_dir, targets=targets)
        return
    if suffix == ".zip":
        subprocess.run(
            ["bsdtar", "-xf", str(archive_path), "-C", str(output_dir), *targets],
            capture_output=True,
            text=True,
            check=False,
        )
        return
    raise SystemExit(f"지원하지 않는 아카이브 형식입니다: {archive_path}")


def select_available_members(archive_names: list[str], basin_ids: set[str]) -> tuple[list[str], set[str], list[str]]:
    selected_names = []
    found_ids = set()
    for name in archive_names:
        path = Path(name)
        if path.suffix.lower() not in {".nc", ".nc4"}:
            continue
        basin_id = path.stem.replace("_hourly", "")
        if basin_id in basin_ids:
            selected_names.append(name)
            found_ids.add(basin_id)
    not_found = sorted(basin_ids - found_ids)
    return selected_names, found_ids, not_found


def write_filtered_splits(output_dir: Path, split_basins: dict[str, list[str]], available_ids: set[str]) -> dict[str, Path]:
    splits_dir = output_dir / "splits"
    splits_dir.mkdir(parents=True, exist_ok=True)
    output_paths: dict[str, Path] = {}
    for split, basins in split_basins.items():
        filtered = [basin for basin in basins if basin in available_ids]
        path = splits_dir / f"{split}.txt"
        path.write_text("\n".join(filtered) + ("\n" if filtered else ""), encoding="utf-8")
        output_paths[split] = path
    return output_paths


def extract_selected_timeseries(
    archive_path: Path,
    basin_ids: set[str],
    time_series_dir: Path,
    force_reextract: bool,
) -> tuple[int, set[str], list[str]]:
    existing = {p.stem for p in time_series_dir.glob("*.nc")} | {p.stem for p in time_series_dir.glob("*.nc4")}
    missing_ids = basin_ids if force_reextract else {b for b in basin_ids if b not in existing}
    if not missing_ids:
        return 0, existing & basin_ids, []

    archive_names = list_archive_members(archive_path)
    selected_names, listed_found_ids, not_found = select_available_members(archive_names, missing_ids)
    extracted_ids: set[str] = set()
    extraction_failed_ids: set[str] = set()

    if selected_names:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            batch_size = 32
            for start in range(0, len(selected_names), batch_size):
                batch_names = selected_names[start:start + batch_size]
                extract_archive_batch(archive_path, batch_names, tmpdir_path)
                for name in batch_names:
                    extracted_path = tmpdir_path / name
                    basin_id = Path(name).stem.replace("_hourly", "")
                    if not extracted_path.exists():
                        extraction_failed_ids.add(basin_id)
                        continue
                    target_path = time_series_dir / f"{basin_id}.nc"
                    try:
                        standardize_netcdf(extracted_path, target_path)
                    except Exception:
                        extraction_failed_ids.add(basin_id)
                        target_path.unlink(missing_ok=True)
                        extracted_path.unlink(missing_ok=True)
                        continue
                    extracted_path.unlink(missing_ok=True)
                    extracted_ids.add(basin_id)

    available_ids = extracted_ids | (existing & basin_ids)
    final_not_found = sorted((set(not_found) | extraction_failed_ids) - available_ids)
    return len(extracted_ids), available_ids, final_not_found


def build_static_attributes(output_dir: Path, basin_ids: set[str]) -> Path:
    attrs_dir = Path("basins/CAMELSH_data/attributes")

    basin_id = pd.read_csv(attrs_dir / "attributes_gageii_BasinID.csv", dtype={"STAID": str})[
        ["STAID", "DRAIN_SQKM", "HUC02", "STATE"]
    ].rename(columns={"STAID": "gauge_id", "DRAIN_SQKM": "area"})
    topo = pd.read_csv(attrs_dir / "attributes_gageii_Topo.csv", dtype={"STAID": str})[
        ["STAID", "SLOPE_PCT"]
    ].rename(columns={"STAID": "gauge_id", "SLOPE_PCT": "slope"})
    clim = pd.read_csv(attrs_dir / "attributes_nldas2_climate.csv", dtype={"STAID": str})[
        ["STAID", "aridity_index", "frac_snow"]
    ].rename(columns={"STAID": "gauge_id", "aridity_index": "aridity", "frac_snow": "snow_fraction"})
    soil = pd.read_csv(attrs_dir / "attributes_gageii_Soils.csv", dtype={"STAID": str})[
        ["STAID", "ROCKDEPAVE", "PERMAVE"]
    ].rename(columns={"STAID": "gauge_id", "ROCKDEPAVE": "soil_depth", "PERMAVE": "permeability"})
    hydro = pd.read_csv(attrs_dir / "attributes_gageii_Hydro.csv", dtype={"STAID": str})[
        ["STAID", "BFI_AVE"]
    ].rename(columns={"STAID": "gauge_id", "BFI_AVE": "baseflow_index"})
    lc = pd.read_csv(attrs_dir / "attributes_gageii_LC06_Basin.csv", dtype={"STAID": str})[
        ["STAID", "FORESTNLCD06"]
    ].rename(columns={"STAID": "gauge_id"})
    lc["forest_fraction"] = pd.to_numeric(lc["FORESTNLCD06"], errors="coerce") / 100.0
    lc = lc[["gauge_id", "forest_fraction"]]

    static_df = basin_id.merge(topo, on="gauge_id").merge(clim, on="gauge_id").merge(soil, on="gauge_id").merge(
        hydro, on="gauge_id"
    ).merge(lc, on="gauge_id")

    static_df = static_df[static_df["gauge_id"].isin(basin_ids)].sort_values("gauge_id").reset_index(drop=True)
    out_path = output_dir / "attributes" / "static_attributes.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    static_df.to_csv(out_path, index=False)
    return out_path


def main() -> None:
    args = parse_args()
    split_paths = basin_split_paths(args.profile)
    split_basins = load_split_basins(split_paths)
    basin_ids = flatten_split_basins(split_basins)

    profile_dir = args.output_dir / f"drbc_holdout_{args.profile}"
    time_series_dir = profile_dir / "time_series"
    time_series_dir.mkdir(parents=True, exist_ok=True)

    ensure_archive(args.archive_path, download_if_missing=args.download_if_missing)

    extracted_count, available_ids, not_found = extract_selected_timeseries(
        archive_path=args.archive_path,
        basin_ids=basin_ids,
        time_series_dir=time_series_dir,
        force_reextract=args.force_reextract,
    )

    filtered_split_paths = write_filtered_splits(profile_dir, split_basins, available_ids)
    attributes_path = build_static_attributes(profile_dir, available_ids)

    summary = {
        "profile": args.profile,
        "requested_basin_count": len(basin_ids),
        "available_basin_count": len(available_ids),
        "extracted_or_updated_timeseries_count": extracted_count,
        "timeseries_dir": str(time_series_dir),
        "attributes_path": str(attributes_path),
        "missing_in_archive": not_found,
        "requested_split_files": {k: str(v) for k, v in split_paths.items()},
        "prepared_split_files": {k: str(v) for k, v in filtered_split_paths.items()},
        "prepared_split_counts": {k: sum(1 for _ in v.read_text().splitlines() if _) for k, v in filtered_split_paths.items()},
    }
    summary_path = profile_dir / "prepare_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
