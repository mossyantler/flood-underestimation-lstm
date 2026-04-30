#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pandas>=2.2",
# ]
# ///

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build regional holdout basin split files: non-DRBC train/validation and "
            "DRBC test files."
        )
    )
    parser.add_argument(
        "--training-selected-csv",
        type=Path,
        default=Path("output/basin/all/screening/training_non_drbc/camelsh_non_drbc_training_selected.csv"),
    )
    parser.add_argument(
        "--drbc-selected-csv",
        type=Path,
        default=Path("output/basin/drbc/basin_define/camelsh_drbc_selected.csv"),
    )
    parser.add_argument(
        "--drbc-quality-csv",
        type=Path,
        default=Path("output/basin/drbc/screening/drbc_streamflow_quality_table.csv"),
    )
    parser.add_argument(
        "--splits-dir",
        type=Path,
        default=Path("configs/basin_splits"),
    )
    parser.add_argument(
        "--summary-dir",
        type=Path,
        default=Path("output/basin/all/screening/splits/drbc_holdout"),
    )
    parser.add_argument("--validation-fraction", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=20260404)
    return parser.parse_args()


def write_basin_file(path: Path, gauge_ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(gauge_ids) + ("\n" if gauge_ids else ""), encoding="utf-8")


def stratified_split(
    df: pd.DataFrame,
    group_col: str,
    validation_fraction: float,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_parts: list[pd.DataFrame] = []
    val_parts: list[pd.DataFrame] = []

    for idx, (group_name, group_df) in enumerate(df.groupby(group_col, sort=True)):
        group_df = group_df.sample(frac=1.0, random_state=seed + idx).reset_index(drop=True)
        n = len(group_df)
        if n <= 1:
            n_val = 0
        else:
            n_val = max(1, int(math.ceil(n * validation_fraction)))
            n_val = min(n_val, n - 1)
        val_parts.append(group_df.iloc[:n_val])
        train_parts.append(group_df.iloc[n_val:])

    train_df = pd.concat(train_parts, ignore_index=True).sort_values("gauge_id").reset_index(drop=True)
    val_df = pd.concat(val_parts, ignore_index=True).sort_values("gauge_id").reset_index(drop=True)
    return train_df, val_df


def value_counts_dict(series: pd.Series) -> dict[str, int]:
    return {str(k): int(v) for k, v in series.value_counts(dropna=False).sort_index().to_dict().items()}


def main() -> None:
    args = parse_args()
    args.splits_dir.mkdir(parents=True, exist_ok=True)
    args.summary_dir.mkdir(parents=True, exist_ok=True)

    training = pd.read_csv(args.training_selected_csv, dtype={"gauge_id": str})
    drbc_selected = pd.read_csv(args.drbc_selected_csv, dtype={"gauge_id": str})
    drbc_quality = pd.read_csv(args.drbc_quality_csv, dtype={"gauge_id": str})

    broad_train_pool = training.copy()
    natural_train_pool = training[~training["hydromod_risk"]].copy()

    train_broad, val_broad = stratified_split(
        broad_train_pool,
        group_col="camelsh_huc02",
        validation_fraction=args.validation_fraction,
        seed=args.seed,
    )
    train_natural, val_natural = stratified_split(
        natural_train_pool,
        group_col="camelsh_huc02",
        validation_fraction=args.validation_fraction,
        seed=args.seed + 1000,
    )

    drbc_quality_pass = drbc_quality[drbc_quality["passes_streamflow_quality_gate"]].copy()
    drbc_quality_pass_natural = drbc_quality_pass[~drbc_quality_pass["hydromod_risk"]].copy()

    files = {
        "train_broad": args.splits_dir / "drbc_holdout_train_broad.txt",
        "validation_broad": args.splits_dir / "drbc_holdout_validation_broad.txt",
        "test_drbc_all": args.splits_dir / "drbc_holdout_test_drbc_all.txt",
        "test_drbc_quality": args.splits_dir / "drbc_holdout_test_drbc_quality.txt",
        "train_natural": args.splits_dir / "drbc_holdout_train_natural.txt",
        "validation_natural": args.splits_dir / "drbc_holdout_validation_natural.txt",
        "test_drbc_quality_natural": args.splits_dir / "drbc_holdout_test_drbc_quality_natural.txt",
    }

    write_basin_file(files["train_broad"], train_broad["gauge_id"].tolist())
    write_basin_file(files["validation_broad"], val_broad["gauge_id"].tolist())
    write_basin_file(files["test_drbc_all"], drbc_selected["gauge_id"].tolist())
    write_basin_file(files["test_drbc_quality"], drbc_quality_pass["gauge_id"].tolist())
    write_basin_file(files["train_natural"], train_natural["gauge_id"].tolist())
    write_basin_file(files["validation_natural"], val_natural["gauge_id"].tolist())
    write_basin_file(files["test_drbc_quality_natural"], drbc_quality_pass_natural["gauge_id"].tolist())

    summary = {
        "split_design": "regional_holdout_drbc",
        "validation_fraction": args.validation_fraction,
        "random_seed": args.seed,
        "broad": {
            "train_count": int(len(train_broad)),
            "validation_count": int(len(val_broad)),
            "test_drbc_all_count": int(len(drbc_selected)),
            "test_drbc_quality_count": int(len(drbc_quality_pass)),
            "train_huc02_counts": value_counts_dict(train_broad["camelsh_huc02"]),
            "validation_huc02_counts": value_counts_dict(val_broad["camelsh_huc02"]),
        },
        "natural": {
            "train_count": int(len(train_natural)),
            "validation_count": int(len(val_natural)),
            "test_drbc_quality_natural_count": int(len(drbc_quality_pass_natural)),
            "train_huc02_counts": value_counts_dict(train_natural["camelsh_huc02"]),
            "validation_huc02_counts": value_counts_dict(val_natural["camelsh_huc02"]),
        },
    }

    summary_path = args.summary_dir / "drbc_holdout_split_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Wrote split files under: {args.splits_dir}")
    print(f"Wrote split summary: {summary_path}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
