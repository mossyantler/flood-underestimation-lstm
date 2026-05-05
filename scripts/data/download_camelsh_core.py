#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import urllib.request
from pathlib import Path


ZENODO_RECORD_ID = "15066778"
ZENODO_API_URL = f"https://zenodo.org/api/records/{ZENODO_RECORD_ID}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download the minimum CAMELSH core files needed for region screening."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tmp/camelsh"),
        help="Directory where CAMELSH files will be downloaded.",
    )
    parser.add_argument(
        "--skip-shapefiles",
        action="store_true",
        help="Skip downloading shapefiles. Useful when only metadata is needed.",
    )
    parser.add_argument(
        "--skip-extract",
        action="store_true",
        help="Download archives but do not extract them.",
    )
    return parser.parse_args()


def fetch_record() -> dict:
    with urllib.request.urlopen(ZENODO_API_URL, timeout=120) as response:
        return json.load(response)


def ensure_bsdtar() -> None:
    if shutil.which("bsdtar") is None:
        raise SystemExit("`bsdtar`가 필요합니다. macOS 기본 제공이 없으면 먼저 설치해 주세요.")


def download_file(url: str, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        print(f"Skip existing file: {target_path}")
        return

    with urllib.request.urlopen(url, timeout=120) as response, target_path.open("wb") as fp:
        shutil.copyfileobj(response, fp)
    print(f"Downloaded: {target_path}")


def extract_archive(archive_path: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["bsdtar", "-xf", str(archive_path), "-C", str(output_dir)],
        check=True,
    )
    print(f"Extracted: {archive_path} -> {output_dir}")


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ensure_bsdtar()

    record = fetch_record()
    file_links = {item["key"]: item["links"]["self"] for item in record["files"]}

    download_targets = {
        "info.csv": args.output_dir / "info.csv",
        "attributes.7z": args.output_dir / "attributes.7z",
    }
    if not args.skip_shapefiles:
        download_targets["shapefiles.7z"] = args.output_dir / "shapefiles.7z"

    for filename, target_path in download_targets.items():
        if filename not in file_links:
            raise SystemExit(f"Zenodo record에 `{filename}`가 없습니다.")
        download_file(file_links[filename], target_path)

    if not args.skip_extract:
        extract_archive(args.output_dir / "attributes.7z", args.output_dir)
        if not args.skip_shapefiles:
            extract_archive(args.output_dir / "shapefiles.7z", args.output_dir)

    print(f"CAMELSH core files are ready under: {args.output_dir}")


if __name__ == "__main__":
    main()
