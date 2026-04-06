#!/usr/bin/env python3
# /// script
# dependencies = []
# ///

from __future__ import annotations

import argparse
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path


OBS_RECORD_ID = "16729675"
CORE_RECORD_ID = "15066778"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download CAMELSH hourly observed data and extract only the selected basin files."
        )
    )
    parser.add_argument(
        "--selected-ids-path",
        type=Path,
        default=Path("output/basin/drbc_camelsh/camelsh_drbc_selected_ids.txt"),
        help="Text file containing selected gauge IDs, one per line.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("basins/CAMELSH_data/hourly_observed"),
        help="Directory where downloaded and extracted files will be stored.",
    )
    parser.add_argument(
        "--keep-zip",
        action="store_true",
        help="Keep Hourly2.zip after extraction.",
    )
    return parser.parse_args()


def fetch_record(record_id: str) -> dict:
    url = f"https://zenodo.org/api/records/{record_id}"
    with urllib.request.urlopen(url, timeout=120) as response:
        return json.load(response)


def get_file_url(record_id: str, key: str) -> str:
    record = fetch_record(record_id)
    for item in record["files"]:
        if item["key"] == key:
            return item["links"]["self"]
    raise SystemExit(f"Zenodo record {record_id}에 `{key}` 파일이 없습니다.")


def download_file(url: str, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        print(f"Skip existing file: {target_path}")
        return
    with urllib.request.urlopen(url, timeout=120) as response, target_path.open("wb") as fp:
        shutil.copyfileobj(response, fp)
    print(f"Downloaded: {target_path}")


def load_selected_ids(path: Path) -> set[str]:
    return {line.strip() for line in path.read_text().splitlines() if line.strip()}


def extract_selected_members(zip_path: Path, target_dir: Path, selected_ids: set[str]) -> int:
    if not zipfile.is_zipfile(zip_path):
        raise SystemExit(f"다운로드된 파일이 정상 zip이 아닙니다: {zip_path}")
    target_dir.mkdir(parents=True, exist_ok=True)
    extracted = 0
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            member_name = Path(member.filename).name
            stem = Path(member_name).stem
            if stem not in selected_ids:
                continue
            output_path = target_dir / member_name
            if output_path.exists():
                extracted += 1
                continue
            with zf.open(member) as src, output_path.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted += 1
            print(f"Extracted: {member_name}")
    return extracted


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    selected_ids = load_selected_ids(args.selected_ids_path)
    if not selected_ids:
        raise SystemExit("Selected gauge ID 목록이 비어 있습니다.")

    info_path = args.output_dir / "info.csv"
    zip_path = args.output_dir / "Hourly2.zip"
    extracted_dir = args.output_dir / "netcdf"

    download_file(get_file_url(CORE_RECORD_ID, "info.csv"), info_path)
    download_file(get_file_url(OBS_RECORD_ID, "Hourly2.zip"), zip_path)

    extracted_count = extract_selected_members(zip_path, extracted_dir, selected_ids)
    print(f"Selected NetCDF files ready: {extracted_count}")

    if not args.keep_zip and zip_path.exists():
        zip_path.unlink()
        print(f"Removed archive: {zip_path}")


if __name__ == "__main__":
    main()
