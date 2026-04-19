#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pandas>=2.2",
# ]
# ///

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


ATTRIBUTE_COLUMNS = [
    "area",
    "slope",
    "aridity",
    "snow_fraction",
    "soil_depth",
    "permeability",
    "forest_fraction",
    "baseflow_index",
]

DEFAULT_SUBSET_SIZES = [100, 300, 600]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build static-attribute distribution diagnostics for scaling-pilot subsets "
            "relative to the prepared broad non-DRBC pool."
        )
    )
    parser.add_argument(
        "--prepared-pool-manifest",
        type=Path,
        default=Path("configs/pilot/basin_splits/prepared_pool_manifest.csv"),
        help="Prepared executable non-DRBC pool manifest with static attributes.",
    )
    parser.add_argument(
        "--subset-root",
        type=Path,
        default=Path("configs/pilot/basin_splits"),
        help="Root directory containing scaling_<size>/manifest.csv files.",
    )
    parser.add_argument(
        "--subset-sizes",
        type=int,
        nargs="+",
        default=DEFAULT_SUBSET_SIZES,
        help="Subset sizes to analyze.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("configs/pilot/diagnostics"),
        help="Directory where diagnostic summaries will be written.",
    )
    return parser.parse_args()


def read_manifest(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"gauge_id": str})
    for col in ATTRIBUTE_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def summarize_attribute(values: pd.Series) -> dict[str, float | int | None]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return {
            "count": 0,
            "mean": None,
            "std": None,
            "min": None,
            "p10": None,
            "p25": None,
            "median": None,
            "p75": None,
            "p90": None,
            "max": None,
        }

    return {
        "count": int(clean.count()),
        "mean": float(clean.mean()),
        "std": float(clean.std(ddof=0)),
        "min": float(clean.min()),
        "p10": float(clean.quantile(0.10)),
        "p25": float(clean.quantile(0.25)),
        "median": float(clean.quantile(0.50)),
        "p75": float(clean.quantile(0.75)),
        "p90": float(clean.quantile(0.90)),
        "max": float(clean.max()),
    }


def build_stats_rows(df: pd.DataFrame, dataset_label: str, scope: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for attribute in ATTRIBUTE_COLUMNS:
        summary = summarize_attribute(df[attribute])
        rows.append(
            {
                "dataset_label": dataset_label,
                "scope": scope,
                "attribute": attribute,
                **summary,
            }
        )
    return rows


def build_comparison_rows(
    reference_df: pd.DataFrame,
    subset_df: pd.DataFrame,
    subset_size: int,
    scope: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for attribute in ATTRIBUTE_COLUMNS:
        ref = summarize_attribute(reference_df[attribute])
        sub = summarize_attribute(subset_df[attribute])

        if ref["mean"] is None or sub["mean"] is None:
            standardized_mean_diff = None
        elif ref["std"] in (None, 0.0):
            standardized_mean_diff = None
        else:
            standardized_mean_diff = float((sub["mean"] - ref["mean"]) / ref["std"])

        rows.append(
            {
                "subset_size": subset_size,
                "scope": scope,
                "attribute": attribute,
                "reference_count": ref["count"],
                "subset_count": sub["count"],
                "reference_mean": ref["mean"],
                "subset_mean": sub["mean"],
                "mean_diff": None if ref["mean"] is None or sub["mean"] is None else float(sub["mean"] - ref["mean"]),
                "abs_mean_diff": None
                if ref["mean"] is None or sub["mean"] is None
                else float(abs(sub["mean"] - ref["mean"])),
                "standardized_mean_diff": standardized_mean_diff,
                "abs_standardized_mean_diff": None
                if standardized_mean_diff is None
                else float(abs(standardized_mean_diff)),
                "reference_median": ref["median"],
                "subset_median": sub["median"],
                "median_diff": None
                if ref["median"] is None or sub["median"] is None
                else float(sub["median"] - ref["median"]),
                "reference_p25": ref["p25"],
                "subset_p25": sub["p25"],
                "p25_diff": None if ref["p25"] is None or sub["p25"] is None else float(sub["p25"] - ref["p25"]),
                "reference_p75": ref["p75"],
                "subset_p75": sub["p75"],
                "p75_diff": None if ref["p75"] is None or sub["p75"] is None else float(sub["p75"] - ref["p75"]),
            }
        )
    return rows


def build_scope_summary(comparison_df: pd.DataFrame) -> list[dict[str, object]]:
    summary_rows: list[dict[str, object]] = []
    for (subset_size, scope), scope_df in comparison_df.groupby(["subset_size", "scope"], sort=True):
        if scope_df.empty:
            continue

        ranked = scope_df.sort_values("abs_standardized_mean_diff", ascending=False, na_position="last")
        max_row = ranked.iloc[0]
        abs_smd = scope_df["abs_standardized_mean_diff"].dropna()
        summary_rows.append(
            {
                "subset_size": int(subset_size),
                "scope": scope,
                "attribute_with_max_abs_smd": str(max_row["attribute"]),
                "max_abs_standardized_mean_diff": None if pd.isna(max_row["abs_standardized_mean_diff"]) else float(max_row["abs_standardized_mean_diff"]),
                "mean_abs_standardized_mean_diff": None if abs_smd.empty else float(abs_smd.mean()),
                "num_attributes_abs_smd_gt_0_10": int((abs_smd > 0.10).sum()),
                "num_attributes_abs_smd_gt_0_25": int((abs_smd > 0.25).sum()),
                "num_attributes_abs_smd_gt_0_50": int((abs_smd > 0.50).sum()),
            }
        )
    return summary_rows


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    prepared_pool = read_manifest(args.prepared_pool_manifest)
    stats_rows: list[dict[str, object]] = []
    comparison_rows: list[dict[str, object]] = []

    reference_scopes = {
        "combined": prepared_pool,
        "train": prepared_pool[prepared_pool["original_split"] == "train"].copy(),
        "validation": prepared_pool[prepared_pool["original_split"] == "validation"].copy(),
    }

    for scope, scope_df in reference_scopes.items():
        stats_rows.extend(build_stats_rows(scope_df, dataset_label="prepared_pool", scope=scope))

    subset_summaries: list[dict[str, object]] = []
    for subset_size in sorted(set(args.subset_sizes)):
        manifest_path = args.subset_root / f"scaling_{subset_size}" / "manifest.csv"
        subset_df = read_manifest(manifest_path)
        subset_scopes = {
            "combined": subset_df,
            "train": subset_df[subset_df["pilot_split"] == "train"].copy(),
            "validation": subset_df[subset_df["pilot_split"] == "validation"].copy(),
        }

        for scope, scope_df in subset_scopes.items():
            stats_rows.extend(
                build_stats_rows(
                    scope_df,
                    dataset_label=f"scaling_{subset_size}",
                    scope=scope,
                )
            )
            comparison_rows.extend(
                build_comparison_rows(
                    reference_df=reference_scopes[scope],
                    subset_df=scope_df,
                    subset_size=subset_size,
                    scope=scope,
                )
            )

        subset_summaries.append(
            {
                "subset_size": subset_size,
                "manifest_path": str(manifest_path),
                "combined_count": int(len(subset_df)),
                "train_count": int(len(subset_scopes["train"])),
                "validation_count": int(len(subset_scopes["validation"])),
            }
        )

    stats_df = pd.DataFrame(stats_rows).sort_values(["dataset_label", "scope", "attribute"]).reset_index(drop=True)
    comparison_df = (
        pd.DataFrame(comparison_rows)
        .sort_values(["subset_size", "scope", "attribute"])
        .reset_index(drop=True)
    )
    scope_summary_df = pd.DataFrame(build_scope_summary(comparison_df)).sort_values(["subset_size", "scope"]).reset_index(drop=True)

    stats_path = args.output_dir / "attribute_distribution_stats.csv"
    comparison_path = args.output_dir / "attribute_distribution_comparisons.csv"
    scope_summary_path = args.output_dir / "attribute_distribution_scope_summary.csv"

    stats_df.to_csv(stats_path, index=False)
    comparison_df.to_csv(comparison_path, index=False)
    scope_summary_df.to_csv(scope_summary_path, index=False)

    summary = {
        "prepared_pool_manifest": str(args.prepared_pool_manifest),
        "attribute_columns": ATTRIBUTE_COLUMNS,
        "subset_summaries": subset_summaries,
        "outputs": {
            "stats_csv": str(stats_path),
            "comparisons_csv": str(comparison_path),
            "scope_summary_csv": str(scope_summary_path),
        },
        "selection_guidance": (
            "Use non-DRBC validation performance together with these attribute-preservation diagnostics "
            "and compute cost when choosing the final basin count. Do not choose the pilot basin count "
            "from the DRBC holdout test metrics."
        ),
    }

    summary_path = args.output_dir / "attribute_distribution_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Wrote attribute distribution stats: {stats_path}")
    print(f"Wrote attribute distribution comparisons: {comparison_path}")
    print(f"Wrote attribute distribution scope summary: {scope_summary_path}")
    print(f"Wrote attribute distribution summary: {summary_path}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
