#!/usr/bin/env python3
# /// script
# dependencies = [
#   "netCDF4>=1.7",
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "scipy>=1.13",
#   "xarray>=2024.1",
# ]
# ///

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import xarray as xr

DRBC_SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "basin" / "drbc"
if str(DRBC_SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(DRBC_SCRIPT_ROOT))

import build_drbc_event_response_table as er


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
SUBSET_EVENT_METADATA_COLUMNS = [
    "pilot_split",
    "original_split",
    "camelsh_huc02",
    "obs_years_usable",
]
DEFAULT_SUBSET_SIZES = [300]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build observed-flow event-response diagnostics for scaling-pilot subsets "
            "relative to the prepared non-DRBC executable pool."
        )
    )
    parser.add_argument(
        "--prepared-pool-manifest",
        type=Path,
        default=Path("configs/pilot/basin_splits/prepared_pool_manifest.csv"),
        help="Prepared executable non-DRBC pool manifest.",
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
        "--timeseries-dir",
        type=Path,
        default=Path("data/CAMELSH_generic/drbc_holdout_broad/time_series"),
        help="Directory containing prepared hourly .nc files.",
    )
    parser.add_argument(
        "--timeseries-csv-dir",
        type=Path,
        default=Path("data/CAMELSH_generic/drbc_holdout_broad/time_series_csv"),
        help="Optional CSV fallback directory for prepared time series.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("configs/pilot/diagnostics/event_response"),
        help="Directory where event-response diagnostics will be written.",
    )
    return parser.parse_args()


def read_manifest(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"gauge_id": str})
    numeric_cols = [
        "drain_sqkm_attr",
        "obs_years_usable",
        "area",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def summarize_metric(values: pd.Series) -> dict[str, float | int | None]:
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
    for metric in OBSERVED_METRIC_COLUMNS:
        summary = summarize_metric(df[metric])
        rows.append(
            {
                "dataset_label": dataset_label,
                "scope": scope,
                "metric": metric,
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
    for metric in OBSERVED_METRIC_COLUMNS:
        ref = summarize_metric(reference_df[metric])
        sub = summarize_metric(subset_df[metric])

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


def build_scope_summary(comparison_df: pd.DataFrame) -> list[dict[str, object]]:
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


def read_streamflow_only(
    gauge_id: str,
    *,
    timeseries_dir: Path,
    timeseries_csv_dir: Path,
) -> pd.Series:
    nc_path = timeseries_dir / f"{gauge_id}.nc"
    csv_path = timeseries_csv_dir / f"{gauge_id}.csv"

    if nc_path.exists():
        with xr.open_dataset(nc_path) as ds:
            streamflow = ds["Streamflow"].to_dataframe().reset_index()
        timestamp_col = "date" if "date" in streamflow.columns else streamflow.columns[0]
        frame = streamflow.rename(columns={timestamp_col: "timestamp"})
    elif csv_path.exists():
        frame = pd.read_csv(
            csv_path,
            usecols=["date", "Streamflow"],
            parse_dates=["date"],
        ).rename(columns={"date": "timestamp"})
    else:
        raise FileNotFoundError(
            f"Missing prepared time series for gauge {gauge_id}: {nc_path} or {csv_path}"
        )

    frame = frame.sort_values("timestamp").drop_duplicates("timestamp").set_index("timestamp")
    return frame["Streamflow"]


def compute_basin_summary(
    basin: pd.Series,
    *,
    timeseries_dir: Path,
    timeseries_csv_dir: Path,
) -> dict[str, object]:
    gauge_id = basin["gauge_id"]

    try:
        streamflow = read_streamflow_only(
            gauge_id,
            timeseries_dir=timeseries_dir,
            timeseries_csv_dir=timeseries_csv_dir,
        )
    except FileNotFoundError as exc:
        return {
            "gauge_id": gauge_id,
            "gauge_name": basin["gauge_name"],
            "state": basin["state"],
            "drain_sqkm_attr": basin.get("drain_sqkm_attr"),
            "original_split": basin.get("original_split"),
            "pilot_split": basin.get("pilot_split"),
            "obs_years_usable": basin.get("obs_years_usable"),
            "processing_status": "missing_timeseries",
            "selected_threshold_quantile": pd.NA,
            "selected_threshold_value": pd.NA,
            "q99_event_count": 0,
            "event_count": 0,
            "annual_peak_years": 0,
            "unit_area_peak_median": pd.NA,
            "unit_area_peak_p90": pd.NA,
            "q99_event_frequency": pd.NA,
            "rbi": pd.NA,
            "rising_time_median_hours": pd.NA,
            "event_duration_median_hours": pd.NA,
            "annual_peak_unit_area_median": pd.NA,
            "annual_peak_unit_area_p90": pd.NA,
            "error_detail": str(exc),
        }

    valid = streamflow.dropna()
    if valid.empty:
        return {
            "gauge_id": gauge_id,
            "gauge_name": basin["gauge_name"],
            "state": basin["state"],
            "drain_sqkm_attr": basin.get("drain_sqkm_attr"),
            "original_split": basin.get("original_split"),
            "pilot_split": basin.get("pilot_split"),
            "obs_years_usable": basin.get("obs_years_usable"),
            "processing_status": "no_valid_streamflow",
            "selected_threshold_quantile": pd.NA,
            "selected_threshold_value": pd.NA,
            "q99_event_count": 0,
            "event_count": 0,
            "annual_peak_years": 0,
            "unit_area_peak_median": pd.NA,
            "unit_area_peak_p90": pd.NA,
            "q99_event_frequency": pd.NA,
            "rbi": pd.NA,
            "rising_time_median_hours": pd.NA,
            "event_duration_median_hours": pd.NA,
            "annual_peak_unit_area_median": pd.NA,
            "annual_peak_unit_area_p90": pd.NA,
            "error_detail": "",
        }

    threshold_label, threshold_value, clusters, threshold_counts = er.select_threshold(streamflow)
    annual_peaks = er.annual_peak_series(streamflow)
    area_values = pd.to_numeric(
        pd.Series([basin.get("drain_sqkm_attr"), basin.get("area")]),
        errors="coerce",
    ).dropna()
    area_sqkm = float(area_values.iloc[0]) if not area_values.empty and float(area_values.iloc[0]) > 0 else pd.NA

    event_unit_peaks: list[float] = []
    rising_times: list[int] = []
    durations: list[int] = []
    for cluster in clusters:
        event_start = er.find_last_below_threshold(streamflow, cluster.first_segment_start, threshold_value)
        event_end = er.find_first_below_threshold(streamflow, cluster.last_segment_end, threshold_value)
        if pd.notna(area_sqkm):
            event_unit_peaks.append(float(cluster.peak_value / area_sqkm))
        rising_times.append(int((cluster.peak_time - event_start).total_seconds() / 3600))
        durations.append(int((event_end - event_start).total_seconds() / 3600) + 1)

    usable_years = pd.to_numeric(pd.Series([basin.get("obs_years_usable")]), errors="coerce").dropna()
    denominator = float(usable_years.iloc[0]) if not usable_years.empty and usable_years.iloc[0] > 0 else float(len(annual_peaks))
    q99_event_frequency = pd.NA if denominator == 0 else float(threshold_counts.get("Q99", 0) / denominator)

    annual_peak_unit_area_median = pd.NA
    annual_peak_unit_area_p90 = pd.NA
    if pd.notna(area_sqkm) and len(annual_peaks) > 0:
        annual_unit_area = annual_peaks / area_sqkm
        annual_peak_unit_area_median = float(annual_unit_area.median())
        annual_peak_unit_area_p90 = float(annual_unit_area.quantile(0.9))

    event_unit_peak_series = pd.Series(event_unit_peaks, dtype=float)
    rising_series = pd.Series(rising_times, dtype=float)
    duration_series = pd.Series(durations, dtype=float)

    return {
        "gauge_id": gauge_id,
        "gauge_name": basin["gauge_name"],
        "state": basin["state"],
        "drain_sqkm_attr": basin.get("drain_sqkm_attr"),
        "original_split": basin.get("original_split"),
        "pilot_split": basin.get("pilot_split"),
        "obs_years_usable": basin.get("obs_years_usable"),
        "processing_status": "ok",
        "selected_threshold_quantile": threshold_label,
        "selected_threshold_value": float(threshold_value),
        "q99_event_count": int(threshold_counts.get("Q99", 0)),
        "event_count": int(len(clusters)),
        "annual_peak_years": int(len(annual_peaks)),
        "unit_area_peak_median": pd.NA if event_unit_peak_series.empty else float(event_unit_peak_series.median()),
        "unit_area_peak_p90": pd.NA if event_unit_peak_series.empty else float(event_unit_peak_series.quantile(0.9)),
        "q99_event_frequency": q99_event_frequency,
        "rbi": er.calculate_rbi(streamflow),
        "rising_time_median_hours": pd.NA if rising_series.empty else float(rising_series.median()),
        "event_duration_median_hours": pd.NA if duration_series.empty else float(duration_series.median()),
        "annual_peak_unit_area_median": annual_peak_unit_area_median,
        "annual_peak_unit_area_p90": annual_peak_unit_area_p90,
        "error_detail": "",
    }


def build_manifest_summary_table(
    manifest: pd.DataFrame,
    *,
    timeseries_dir: Path,
    timeseries_csv_dir: Path,
) -> pd.DataFrame:
    rows = [
        compute_basin_summary(
            pd.Series(row._asdict()),
            timeseries_dir=timeseries_dir,
            timeseries_csv_dir=timeseries_csv_dir,
        )
        for row in manifest.itertuples(index=False)
    ]
    return pd.DataFrame(rows).sort_values("gauge_id").reset_index(drop=True)


def build_subset_event_table(
    subset_manifest: pd.DataFrame,
    *,
    timeseries_dir: Path,
    timeseries_csv_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    event_rows: list[dict[str, object]] = []
    skipped_rows: list[dict[str, object]] = []

    for row in subset_manifest.itertuples(index=False):
        basin = pd.Series(row._asdict())
        gauge_id = basin["gauge_id"]

        try:
            frame = er.read_timeseries(
                gauge_id,
                timeseries_dir=timeseries_dir,
                timeseries_csv_dir=timeseries_csv_dir,
            )
        except FileNotFoundError as exc:
            skipped_rows.append({"gauge_id": gauge_id, "reason": "missing_timeseries", "detail": str(exc)})
            continue

        streamflow = frame["Streamflow"]
        if streamflow.dropna().empty:
            skipped_rows.append({"gauge_id": gauge_id, "reason": "no_valid_streamflow", "detail": ""})
            continue

        threshold_label, threshold_value, clusters, _ = er.select_threshold(streamflow)
        area_values = pd.to_numeric(
            pd.Series([basin.get("drain_sqkm_attr"), basin.get("area")]),
            errors="coerce",
        ).dropna()
        area_sqkm = float(area_values.iloc[0]) if not area_values.empty and float(area_values.iloc[0]) > 0 else pd.NA

        for event_number, cluster in enumerate(clusters, start=1):
            event_rows.append(
                er.build_event_row(
                    basin,
                    frame,
                    cluster,
                    event_number=event_number,
                    threshold_label=threshold_label,
                    threshold_value=threshold_value,
                    area_sqkm=area_sqkm,
                )
            )

    events = pd.DataFrame(event_rows, columns=er.EVENT_COLUMNS)
    events = attach_subset_event_metadata(events, subset_manifest)
    if not events.empty:
        events = events.sort_values(["gauge_id", "event_peak", "event_id"]).reset_index(drop=True)
    skipped = pd.DataFrame(skipped_rows, columns=er.SKIPPED_COLUMNS)
    if not skipped.empty:
        skipped = skipped.sort_values("gauge_id").reset_index(drop=True)
    return events, skipped


def attach_subset_event_metadata(events: pd.DataFrame, subset_manifest: pd.DataFrame) -> pd.DataFrame:
    metadata_cols = [
        col for col in SUBSET_EVENT_METADATA_COLUMNS if col in subset_manifest.columns
    ]
    if not metadata_cols:
        return events

    metadata = subset_manifest[["gauge_id", *metadata_cols]].drop_duplicates("gauge_id")
    if events.empty:
        events = events.copy()
        for col in metadata_cols:
            events[col] = pd.Series(dtype=metadata[col].dtype)
    else:
        events = events.merge(metadata, on="gauge_id", how="left", validate="many_to_one")

    leading_cols = ["gauge_id", *metadata_cols]
    remaining_cols = [col for col in events.columns if col not in leading_cols]
    return events[leading_cols + remaining_cols]


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    prepared_manifest = read_manifest(args.prepared_pool_manifest)
    prepared_summary = build_manifest_summary_table(
        prepared_manifest,
        timeseries_dir=args.timeseries_dir,
        timeseries_csv_dir=args.timeseries_csv_dir,
    )

    prepared_summary_path = args.output_dir / "prepared_pool_event_response_basin_summary.csv"
    prepared_summary.to_csv(prepared_summary_path, index=False)

    stats_rows: list[dict[str, object]] = []
    comparison_rows: list[dict[str, object]] = []

    prepared_scopes = {
        "combined": prepared_summary.copy(),
        "train": prepared_summary[prepared_summary["original_split"] == "train"].copy(),
        "validation": prepared_summary[prepared_summary["original_split"] == "validation"].copy(),
    }
    for scope, scope_df in prepared_scopes.items():
        stats_rows.extend(build_stats_rows(scope_df, dataset_label="prepared_pool", scope=scope))

    subset_summaries: list[dict[str, object]] = []
    for subset_size in sorted(set(args.subset_sizes)):
        subset_manifest_path = args.subset_root / f"scaling_{subset_size}" / "manifest.csv"
        subset_manifest = read_manifest(subset_manifest_path)
        subset_summary = prepared_summary[prepared_summary["gauge_id"].isin(subset_manifest["gauge_id"])].copy()
        subset_summary = subset_manifest[["gauge_id", "pilot_split"]].merge(
            subset_summary.drop(columns=["pilot_split"], errors="ignore"),
            on="gauge_id",
            how="left",
            validate="one_to_one",
        )

        subset_summary_path = args.output_dir / f"scaling_{subset_size}_event_response_basin_summary.csv"
        subset_summary.to_csv(subset_summary_path, index=False)

        subset_scopes = {
            "combined": subset_summary,
            "train": subset_summary[subset_summary["pilot_split"] == "train"].copy(),
            "validation": subset_summary[subset_summary["pilot_split"] == "validation"].copy(),
        }
        for scope, scope_df in subset_scopes.items():
            stats_rows.extend(build_stats_rows(scope_df, dataset_label=f"scaling_{subset_size}", scope=scope))
            comparison_rows.extend(
                build_comparison_rows(
                    reference_df=prepared_scopes[scope],
                    subset_df=scope_df,
                    subset_size=subset_size,
                    scope=scope,
                )
            )

        events, skipped = build_subset_event_table(
            subset_manifest,
            timeseries_dir=args.timeseries_dir,
            timeseries_csv_dir=args.timeseries_csv_dir,
        )
        subset_event_path = args.output_dir / f"scaling_{subset_size}_event_response_table.csv"
        subset_skipped_path = args.output_dir / f"scaling_{subset_size}_event_response_skipped_basins.csv"
        events.to_csv(subset_event_path, index=False)
        skipped.to_csv(subset_skipped_path, index=False)

        split_event_paths: dict[str, str] = {}
        for split in ["train", "validation"]:
            split_event_path = args.output_dir / f"scaling_{subset_size}_{split}_event_response_table.csv"
            events[events["pilot_split"] == split].copy().to_csv(split_event_path, index=False)
            split_event_paths[split] = str(split_event_path)

        subset_summaries.append(
            {
                "subset_size": subset_size,
                "manifest_path": str(subset_manifest_path),
                "combined_count": int(len(subset_summary)),
                "train_count": int((subset_summary["pilot_split"] == "train").sum()),
                "validation_count": int((subset_summary["pilot_split"] == "validation").sum()),
                "subset_event_table_path": str(subset_event_path),
                "subset_split_event_table_paths": split_event_paths,
                "subset_basin_summary_path": str(subset_summary_path),
                "subset_skipped_path": str(subset_skipped_path),
            }
        )

    stats_df = pd.DataFrame(stats_rows).sort_values(["dataset_label", "scope", "metric"]).reset_index(drop=True)
    comparison_df = (
        pd.DataFrame(comparison_rows)
        .sort_values(["subset_size", "scope", "metric"])
        .reset_index(drop=True)
    )
    scope_summary_df = pd.DataFrame(build_scope_summary(comparison_df)).sort_values(["subset_size", "scope"]).reset_index(drop=True)

    stats_path = args.output_dir / "event_response_distribution_stats.csv"
    comparison_path = args.output_dir / "event_response_distribution_comparisons.csv"
    scope_summary_path = args.output_dir / "event_response_scope_summary.csv"

    stats_df.to_csv(stats_path, index=False)
    comparison_df.to_csv(comparison_path, index=False)
    scope_summary_df.to_csv(scope_summary_path, index=False)

    summary = {
        "prepared_pool_manifest": str(args.prepared_pool_manifest),
        "prepared_pool_count": int(len(prepared_manifest)),
        "subset_summaries": subset_summaries,
        "observed_metric_columns": OBSERVED_METRIC_COLUMNS,
        "outputs": {
            "prepared_pool_basin_summary_csv": str(prepared_summary_path),
            "stats_csv": str(stats_path),
            "comparisons_csv": str(comparison_path),
            "scope_summary_csv": str(scope_summary_path),
        },
        "selection_guidance": (
            "Use non-DRBC validation performance together with static-attribute diagnostics, "
            "these observed-flow event-response diagnostics, and compute cost when deciding "
            "whether a fixed scaling subset preserves training-pool representativeness."
        ),
    }
    summary_path = args.output_dir / "event_response_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Wrote prepared-pool basin summary: {prepared_summary_path}")
    print(f"Wrote event-response distribution stats: {stats_path}")
    print(f"Wrote event-response distribution comparisons: {comparison_path}")
    print(f"Wrote event-response scope summary: {scope_summary_path}")
    print(f"Wrote event-response summary: {summary_path}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
