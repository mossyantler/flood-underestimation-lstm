#!/usr/bin/env python3

from __future__ import annotations

import json
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SPLITS = ROOT / "data" / "CAMELSH_generic" / "drbc_holdout_broad" / "splits"
OUTPUT_SPLITS = ROOT / "data" / "CAMELSH_generic" / "drbc_holdout_broad" / "splits_m3_safe"
SUMMARY_PATH = OUTPUT_SPLITS / "summary.json"

SEED = 111
TRAIN_COUNT = 256
VALIDATION_COUNT = 64


def read_split(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def write_split(path: Path, basins: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(basins) + "\n", encoding="utf-8")


def sample_split(basins: list[str], count: int, rng: random.Random) -> list[str]:
    if len(basins) < count:
        raise ValueError(f"Requested {count} basins, but only {len(basins)} are available.")
    sampled = sorted(rng.sample(basins, count))
    return sampled


def main() -> None:
    rng = random.Random(SEED)

    train = read_split(SOURCE_SPLITS / "train.txt")
    validation = read_split(SOURCE_SPLITS / "validation.txt")
    test = read_split(SOURCE_SPLITS / "test.txt")

    # SOURCE_SPLITS already reflects the official broad prepared split after the usability gate.
    safe_train = sample_split(train, TRAIN_COUNT, rng)
    safe_validation = sample_split(validation, VALIDATION_COUNT, rng)
    safe_test = test

    write_split(OUTPUT_SPLITS / "train.txt", safe_train)
    write_split(OUTPUT_SPLITS / "validation.txt", safe_validation)
    write_split(OUTPUT_SPLITS / "test.txt", safe_test)

    summary = {
        "source_profile": "broad_prepared_split",
        "random_seed": SEED,
        "source_prepared_counts": {
            "train": len(train),
            "validation": len(validation),
            "test": len(test),
        },
        "sampled_counts": {
            "train": len(safe_train),
            "validation": len(safe_validation),
            "test": len(safe_test),
        },
    }
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"safe_train={len(safe_train)}")
    print(f"safe_validation={len(safe_validation)}")
    print(f"safe_test={len(safe_test)}")
    print(f"summary={SUMMARY_PATH}")


if __name__ == "__main__":
    main()
