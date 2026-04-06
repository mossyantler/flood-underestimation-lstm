#!/usr/bin/env python3

from __future__ import annotations

import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SPLITS = ROOT / "data" / "CAMELSH_generic" / "drbc_holdout_broad" / "splits"
OUTPUT_SPLITS = ROOT / "data" / "CAMELSH_generic" / "drbc_holdout_broad" / "splits_m3_safe"

SEED = 111
TRAIN_COUNT = 256
VALIDATION_COUNT = 64

# These basins were reported by NeuralHydrology as having no valid target values in the train period.
INVALID_TRAIN_BASINS = {
    "01191000",
    "02407000",
    "03017500",
    "03126000",
    "03127000",
    "03141500",
    "03190000",
    "03198000",
    "03466500",
    "06824500",
    "06847000",
    "06864000",
    "07029270",
    "07229300",
    "08183900",
}


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

    filtered_train = [basin for basin in train if basin not in INVALID_TRAIN_BASINS]

    safe_train = sample_split(filtered_train, TRAIN_COUNT, rng)
    safe_validation = sample_split(validation, VALIDATION_COUNT, rng)
    safe_test = test

    write_split(OUTPUT_SPLITS / "train.txt", safe_train)
    write_split(OUTPUT_SPLITS / "validation.txt", safe_validation)
    write_split(OUTPUT_SPLITS / "test.txt", safe_test)

    print(f"safe_train={len(safe_train)}")
    print(f"safe_validation={len(safe_validation)}")
    print(f"safe_test={len(safe_test)}")


if __name__ == "__main__":
    main()
