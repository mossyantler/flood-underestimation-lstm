#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DOC_FILES = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
GENERATED_PARTS = {"output", "runs", "tmp", "data"}
SENSITIVE_EXTENSIONS = {".pem"}
OFFICIAL_CONFIGS = [
    ROOT / "configs" / "camelsh_hourly_model1_drbc_holdout_broad.yml",
    ROOT / "configs" / "camelsh_hourly_model2_drbc_holdout_broad.yml",
]
LOCKED_KEYS = [
    "dataset",
    "data_dir",
    "train_basin_file",
    "validation_basin_file",
    "test_basin_file",
    "train_start_date",
    "train_end_date",
    "validation_start_date",
    "validation_end_date",
    "test_start_date",
    "test_end_date",
    "model",
    "hidden_size",
    "initial_forget_bias",
    "output_dropout",
    "optimizer",
    "batch_size",
    "epochs",
    "predict_last_n",
    "seq_length",
    "validate_n_random_basins",
]


def collect_sensitive_files() -> list[Path]:
    results: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.parts or ".venv" in path.parts:
            continue
        if path.suffix.lower() in SENSITIVE_EXTENSIONS:
            results.append(path)
    return sorted(results)


def collect_broken_links() -> list[str]:
    broken: list[str] = []
    pattern = re.compile(r"\]\(([^)#]+)\)")

    for md in DOC_FILES:
        text = md.read_text(encoding="utf-8")
        for target in pattern.findall(text):
            if target.startswith("http") or target.startswith("/Users/"):
                continue
            rel = Path(target)
            if any(part in GENERATED_PARTS for part in rel.parts):
                continue
            resolved = (md.parent / rel).resolve()
            if not resolved.exists():
                broken.append(f"{md.relative_to(ROOT)}: {target}")
    return broken


def parse_simple_yaml(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        if raw_line.startswith(" ") or raw_line.startswith("\t"):
            continue
        key, value = raw_line.split(":", 1)
        values[key.strip()] = value.strip()
    return values


def collect_config_drift() -> list[str]:
    parsed = [parse_simple_yaml(path) for path in OFFICIAL_CONFIGS]
    drift: list[str] = []
    for key in LOCKED_KEYS:
        values = [cfg.get(key) for cfg in parsed]
        if len(set(values)) != 1:
            drift.append(f"{key}: {values}")
    return drift


def main() -> int:
    errors: list[str] = []

    sensitive = collect_sensitive_files()
    if sensitive:
        errors.append("Sensitive files found inside repo:")
        errors.extend(f"  - {path.relative_to(ROOT)}" for path in sensitive)

    broken_links = collect_broken_links()
    if broken_links:
        errors.append("Broken markdown links:")
        errors.extend(f"  - {item}" for item in broken_links)

    config_drift = collect_config_drift()
    if config_drift:
        errors.append("Official broad config drift detected:")
        errors.extend(f"  - {item}" for item in config_drift)

    if errors:
        print("\n".join(errors))
        return 1

    print("Repository integrity check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
