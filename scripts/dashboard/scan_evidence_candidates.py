#!/usr/bin/env python3
"""Scan docs/output artifacts into dashboard evidence candidate CSV."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.dashboard.evidence_common import Candidate, classify_path, write_candidates_csv


DEFAULT_OUTPUT = REPO_ROOT / "dashboard/data/evidence_candidates.csv"
SCAN_ROOTS = [Path("docs"), Path("output")]
INCLUDE_SUFFIXES = {".md", ".html", ".png", ".svg", ".csv", ".json"}
EXCLUDED_PARTS = {"raw_model_exports", "raw_timeseries", "required_series", "quantile_exports"}


def should_include(path: Path) -> bool:
    lower_parts = {part.lower() for part in path.parts}
    if lower_parts & EXCLUDED_PARTS:
        return False
    suffix = path.suffix.lower()
    if suffix not in INCLUDE_SUFFIXES:
        return False
    text = str(path).lower()
    if suffix in {".csv", ".json"}:
        return any(
            token in text
            for token in ["summary", "manifest", "metadata", "chart_manifest", "coverage", "primary_epoch"]
        )
    return True


def scan_paths(root: Path) -> list[Candidate]:
    root = root.resolve()
    rows: list[Candidate] = []
    for scan_root in SCAN_ROOTS:
        absolute_root = root / scan_root
        if not absolute_root.exists():
            continue
        for path in sorted(absolute_root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            if should_include(rel):
                rows.append(classify_path(rel, title_path=path))
    return rows


def output_label(output: Path, repo_root: Path) -> str:
    try:
        return str(output.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(output if output.is_absolute() else output.resolve())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    rows = scan_paths(args.repo_root)
    write_candidates_csv(args.output, rows)
    print(f"wrote {output_label(args.output, args.repo_root)} rows={len(rows)}")


if __name__ == "__main__":
    main()
