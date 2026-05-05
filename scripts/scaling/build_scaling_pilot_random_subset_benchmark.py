#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=1.26",
#   "pandas>=2.2",
# ]
# ///

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import build_scaling_pilot_attribute_diagnostics as attrdiag


OBSERVED_METRIC_COLUMNS = [
    "annual_peak_unit_area_median",
    "q99_event_frequency",
    "rbi",
    "unit_area_peak_median",
    "rising_time_median_hours",
    "event_duration_median_hours",
    "event_count",
    "annual_peak_years",
]


STATIC_SUMMARY_RENAME = {
    "attribute_with_max_abs_smd": "feature_with_max_abs_smd",
    "num_attributes_abs_smd_gt_0_10": "num_features_abs_smd_gt_0_10",
    "num_attributes_abs_smd_gt_0_25": "num_features_abs_smd_gt_0_25",
    "num_attributes_abs_smd_gt_0_50": "num_features_abs_smd_gt_0_50",
}

EVENT_SUMMARY_RENAME = {
    "metric_with_max_abs_smd": "feature_with_max_abs_smd",
    "num_metrics_abs_smd_gt_0_10": "num_features_abs_smd_gt_0_10",
    "num_metrics_abs_smd_gt_0_25": "num_features_abs_smd_gt_0_25",
    "num_metrics_abs_smd_gt_0_50": "num_features_abs_smd_gt_0_50",
}

BENCHMARK_STAT_COLUMNS = [
    "max_abs_standardized_mean_diff",
    "mean_abs_standardized_mean_diff",
    "num_features_abs_smd_gt_0_10",
    "num_features_abs_smd_gt_0_25",
    "num_features_abs_smd_gt_0_50",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark the adopted scaling_300 subset against random same-size subsets "
            "drawn from the prepared non-DRBC executable pool."
        )
    )
    parser.add_argument(
        "--prepared-pool-manifest",
        type=Path,
        default=Path("configs/pilot/basin_splits/prepared_pool_manifest.csv"),
        help="Prepared executable non-DRBC pool manifest with static attributes.",
    )
    parser.add_argument(
        "--prepared-event-summary",
        type=Path,
        default=Path("configs/pilot/diagnostics/event_response/prepared_pool_event_response_basin_summary.csv"),
        help="Prepared-pool event-response basin summary CSV.",
    )
    parser.add_argument(
        "--subset-manifest",
        type=Path,
        default=Path("configs/pilot/basin_splits/scaling_300/manifest.csv"),
        help="Adopted subset manifest to benchmark.",
    )
    parser.add_argument(
        "--num-replicates",
        type=int,
        default=200,
        help="Number of random same-size subsets to draw.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=20260421,
        help="Random seed for reproducible subset draws.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("configs/pilot/diagnostics/permutation_benchmark"),
        help="Directory where benchmark outputs will be written.",
    )
    return parser.parse_args()


def load_static_manifest(path: Path) -> pd.DataFrame:
    return attrdiag.read_manifest(path)


def load_event_summary(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"gauge_id": str})
    numeric_cols = [
        "drain_sqkm_attr",
        "obs_years_usable",
        *OBSERVED_METRIC_COLUMNS,
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def build_scope_frames(df: pd.DataFrame, split_col: str) -> dict[str, pd.DataFrame]:
    return {
        "combined": df.copy(),
        "train": df[df[split_col] == "train"].copy(),
        "validation": df[df[split_col] == "validation"].copy(),
    }


def compute_static_scope_summary(
    reference_scopes: dict[str, pd.DataFrame],
    subset_scopes: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    comparison_rows: list[dict[str, object]] = []
    for scope in ["combined", "train", "validation"]:
        comparison_rows.extend(
            attrdiag.build_comparison_rows(
                reference_df=reference_scopes[scope],
                subset_df=subset_scopes[scope],
                subset_size=int(len(subset_scopes["combined"])),
                scope=scope,
            )
        )
    summary_df = pd.DataFrame(attrdiag.build_scope_summary(pd.DataFrame(comparison_rows)))
    summary_df = summary_df.rename(columns=STATIC_SUMMARY_RENAME)
    summary_df["domain"] = "static_attributes"
    return summary_df


def compute_event_scope_summary(
    reference_scopes: dict[str, pd.DataFrame],
    subset_scopes: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    comparison_rows: list[dict[str, object]] = []
    for scope in ["combined", "train", "validation"]:
        comparison_rows.extend(
            build_event_comparison_rows(
                reference_df=reference_scopes[scope],
                subset_df=subset_scopes[scope],
                subset_size=int(len(subset_scopes["combined"])),
                scope=scope,
            )
        )
    summary_df = pd.DataFrame(build_event_scope_summary(pd.DataFrame(comparison_rows)))
    summary_df = summary_df.rename(columns=EVENT_SUMMARY_RENAME)
    summary_df["domain"] = "event_response"
    return summary_df


def sample_subset(
    train_pool: pd.DataFrame,
    validation_pool: pd.DataFrame,
    *,
    train_size: int,
    validation_size: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    train_ids = rng.choice(train_pool["gauge_id"].to_numpy(), size=train_size, replace=False)
    validation_ids = rng.choice(validation_pool["gauge_id"].to_numpy(), size=validation_size, replace=False)

    train_subset = train_pool.set_index("gauge_id").loc[train_ids].reset_index().copy()
    validation_subset = validation_pool.set_index("gauge_id").loc[validation_ids].reset_index().copy()
    train_subset["pilot_split"] = "train"
    validation_subset["pilot_split"] = "validation"
    return pd.concat([train_subset, validation_subset], ignore_index=True)


def benchmark_rows(
    actual_df: pd.DataFrame,
    replicate_df: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (domain, scope), actual_group in actual_df.groupby(["domain", "scope"], sort=True):
        replicate_group = replicate_df[
            (replicate_df["domain"] == domain) & (replicate_df["scope"] == scope)
        ].copy()
        if replicate_group.empty:
            continue

        actual_row = actual_group.iloc[0]
        for stat in BENCHMARK_STAT_COLUMNS:
            random_values = pd.to_numeric(replicate_group[stat], errors="coerce").dropna()
            if random_values.empty:
                continue

            actual_value = float(actual_row[stat])
            lower_tail = float((random_values <= actual_value).mean())
            outperform_fraction = float((random_values >= actual_value).mean())

            rows.append(
                {
                    "domain": domain,
                    "scope": scope,
                    "statistic": stat,
                    "actual_value": actual_value,
                    "random_mean": float(random_values.mean()),
                    "random_std": float(random_values.std(ddof=0)),
                    "random_min": float(random_values.min()),
                    "random_p05": float(random_values.quantile(0.05)),
                    "random_p25": float(random_values.quantile(0.25)),
                    "random_p50": float(random_values.quantile(0.50)),
                    "random_p75": float(random_values.quantile(0.75)),
                    "random_p95": float(random_values.quantile(0.95)),
                    "random_max": float(random_values.max()),
                    "lower_tail_percentile": lower_tail * 100.0,
                    "outperforms_random_fraction": outperform_fraction * 100.0,
                    "is_below_random_median": bool(actual_value <= float(random_values.quantile(0.50))),
                    "is_within_random_p05_p95": bool(
                        float(random_values.quantile(0.05)) <= actual_value <= float(random_values.quantile(0.95))
                    ),
                }
            )
    return pd.DataFrame(rows).sort_values(["domain", "scope", "statistic"]).reset_index(drop=True)


def summarize_event_metric(values: pd.Series) -> dict[str, float | int | None]:
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


def build_event_comparison_rows(
    reference_df: pd.DataFrame,
    subset_df: pd.DataFrame,
    subset_size: int,
    scope: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for metric in OBSERVED_METRIC_COLUMNS:
        ref = summarize_event_metric(reference_df[metric])
        sub = summarize_event_metric(subset_df[metric])

        if ref["mean"] is None or sub["mean"] is None or ref["std"] in (None, 0.0):
            standardized_mean_diff = None
        else:
            standardized_mean_diff = float((sub["mean"] - ref["mean"]) / ref["std"])

        rows.append(
            {
                "subset_size": subset_size,
                "scope": scope,
                "metric": metric,
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


def build_event_scope_summary(comparison_df: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for (subset_size, scope), scope_df in comparison_df.groupby(["subset_size", "scope"], sort=True):
        if scope_df.empty:
            continue

        ranked = scope_df.sort_values("abs_standardized_mean_diff", ascending=False, na_position="last")
        max_row = ranked.iloc[0]
        abs_smd = scope_df["abs_standardized_mean_diff"].dropna()
        rows.append(
            {
                "subset_size": int(subset_size),
                "scope": scope,
                "metric_with_max_abs_smd": str(max_row["metric"]),
                "max_abs_standardized_mean_diff": None
                if pd.isna(max_row["abs_standardized_mean_diff"])
                else float(max_row["abs_standardized_mean_diff"]),
                "mean_abs_standardized_mean_diff": None if abs_smd.empty else float(abs_smd.mean()),
                "num_metrics_abs_smd_gt_0_10": int((abs_smd > 0.10).sum()),
                "num_metrics_abs_smd_gt_0_25": int((abs_smd > 0.25).sum()),
                "num_metrics_abs_smd_gt_0_50": int((abs_smd > 0.50).sum()),
            }
        )
    return rows


def extract_key_findings(benchmark_df: pd.DataFrame) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for _, row in benchmark_df.iterrows():
        if row["statistic"] not in {
            "max_abs_standardized_mean_diff",
            "mean_abs_standardized_mean_diff",
        }:
            continue
        rows.append(
            {
                "domain": row["domain"],
                "scope": row["scope"],
                "statistic": row["statistic"],
                "actual_value": row["actual_value"],
                "random_p50": row["random_p50"],
                "random_p95": row["random_p95"],
                "lower_tail_percentile": row["lower_tail_percentile"],
                "outperforms_random_fraction": row["outperforms_random_fraction"],
            }
        )
    return {"key_benchmark_rows": rows}


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    prepared_static = load_static_manifest(args.prepared_pool_manifest)
    prepared_event = load_event_summary(args.prepared_event_summary)
    subset_manifest = load_static_manifest(args.subset_manifest)

    subset_size = int(len(subset_manifest))
    subset_train_size = int((subset_manifest["pilot_split"] == "train").sum())
    subset_validation_size = int((subset_manifest["pilot_split"] == "validation").sum())

    prepared_static_scopes = build_scope_frames(prepared_static, split_col="original_split")
    prepared_event_scopes = build_scope_frames(prepared_event, split_col="original_split")

    actual_static_summary = compute_static_scope_summary(
        reference_scopes=prepared_static_scopes,
        subset_scopes=build_scope_frames(subset_manifest, split_col="pilot_split"),
    )

    actual_event_manifest = subset_manifest[["gauge_id", "pilot_split"]].merge(
        prepared_event.drop(columns=["pilot_split"], errors="ignore"),
        on="gauge_id",
        how="left",
        validate="one_to_one",
    )
    actual_event_summary = compute_event_scope_summary(
        reference_scopes=prepared_event_scopes,
        subset_scopes=build_scope_frames(actual_event_manifest, split_col="pilot_split"),
    )

    actual_scope_summary = pd.concat([actual_static_summary, actual_event_summary], ignore_index=True)
    actual_scope_summary = actual_scope_summary.sort_values(["domain", "scope"]).reset_index(drop=True)

    train_static_pool = prepared_static[prepared_static["original_split"] == "train"].copy()
    validation_static_pool = prepared_static[prepared_static["original_split"] == "validation"].copy()
    train_event_pool = prepared_event[prepared_event["original_split"] == "train"].copy()
    validation_event_pool = prepared_event[prepared_event["original_split"] == "validation"].copy()

    rng = np.random.default_rng(args.random_seed)
    replicate_rows: list[pd.DataFrame] = []
    for replicate in range(1, args.num_replicates + 1):
        replicate_static = sample_subset(
            train_static_pool,
            validation_static_pool,
            train_size=subset_train_size,
            validation_size=subset_validation_size,
            rng=rng,
        )
        replicate_event = replicate_static[["gauge_id", "pilot_split"]].merge(
            prepared_event.drop(columns=["pilot_split"], errors="ignore"),
            on="gauge_id",
            how="left",
            validate="one_to_one",
        )

        static_summary = compute_static_scope_summary(
            reference_scopes=prepared_static_scopes,
            subset_scopes=build_scope_frames(replicate_static, split_col="pilot_split"),
        )
        event_summary = compute_event_scope_summary(
            reference_scopes=prepared_event_scopes,
            subset_scopes=build_scope_frames(replicate_event, split_col="pilot_split"),
        )

        replicate_df = pd.concat([static_summary, event_summary], ignore_index=True)
        replicate_df["replicate"] = replicate
        replicate_rows.append(replicate_df)

    replicate_scope_summary = (
        pd.concat(replicate_rows, ignore_index=True)
        .sort_values(["replicate", "domain", "scope"])
        .reset_index(drop=True)
    )
    benchmark_df = benchmark_rows(actual_scope_summary, replicate_scope_summary)

    actual_path = args.output_dir / "subset300_actual_scope_summary.csv"
    replicate_path = args.output_dir / "subset300_random_replicate_scope_summary.csv"
    benchmark_path = args.output_dir / "subset300_random_benchmark_summary.csv"

    actual_scope_summary.to_csv(actual_path, index=False)
    replicate_scope_summary.to_csv(replicate_path, index=False)
    benchmark_df.to_csv(benchmark_path, index=False)

    summary = {
        "prepared_pool_manifest": str(args.prepared_pool_manifest),
        "prepared_event_summary": str(args.prepared_event_summary),
        "subset_manifest": str(args.subset_manifest),
        "subset_size": subset_size,
        "subset_train_size": subset_train_size,
        "subset_validation_size": subset_validation_size,
        "num_replicates": int(args.num_replicates),
        "random_seed": int(args.random_seed),
        "outputs": {
            "actual_scope_summary_csv": str(actual_path),
            "replicate_scope_summary_csv": str(replicate_path),
            "benchmark_summary_csv": str(benchmark_path),
        },
        "interpretation_note": (
            "Lower mismatch statistics are better. lower_tail_percentile near 0 means the adopted "
            "subset is unusually well matched to the prepared pool relative to random same-size subsets."
        ),
        **extract_key_findings(benchmark_df),
    }

    summary_path = args.output_dir / "subset300_random_benchmark_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Wrote actual scope summary: {actual_path}")
    print(f"Wrote random replicate scope summary: {replicate_path}")
    print(f"Wrote random benchmark summary: {benchmark_path}")
    print(f"Wrote random benchmark JSON summary: {summary_path}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
