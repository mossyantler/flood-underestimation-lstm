#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = (
    REPO_ROOT
    / "output/model_analysis/overall_analysis/epoch_sensitivity/tables/basin_metrics.csv"
)
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "output/model_analysis/overall_analysis/result_checks/outlier_checks"
)
DEFAULT_TIMESERIES_DIR = REPO_ROOT / "data/CAMELSH_generic/drbc_holdout_broad/time_series"
DEFAULT_DRBC_ATTRIBUTES = (
    REPO_ROOT / "output/basin/drbc/analysis/basin_attributes/tables/drbc_selected_basin_analysis_table.csv"
)
DEFAULT_STREAMFLOW_QUALITY = (
    REPO_ROOT / "output/basin/drbc/screening/drbc_streamflow_quality_table.csv"
)
DEFAULT_EVENT_RESPONSE = (
    REPO_ROOT / "output/basin/drbc/analysis/event_response/tables/event_response_basin_summary.csv"
)
OFFICIAL_SEEDS = [111, 222, 444]
TEST_START = "2014-01-01 00:00:00"
TEST_END = "2016-12-31 23:00:00"
METRICS = ["NSE", "KGE", "FHV", "Peak-Timing", "Peak-MAPE", "abs_FHV"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnose basin-level outliers in subset300 epoch metric box plots."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--timeseries-dir", type=Path, default=DEFAULT_TIMESERIES_DIR)
    parser.add_argument("--drbc-attributes", type=Path, default=DEFAULT_DRBC_ATTRIBUTES)
    parser.add_argument("--streamflow-quality", type=Path, default=DEFAULT_STREAMFLOW_QUALITY)
    parser.add_argument("--event-response", type=Path, default=DEFAULT_EVENT_RESPONSE)
    parser.add_argument("--split", default="test", choices=["test", "validation"])
    parser.add_argument("--seeds", type=int, nargs="+", default=OFFICIAL_SEEDS)
    parser.add_argument("--top-n-extremes", type=int, default=10)
    parser.add_argument("--start-date", default=TEST_START)
    parser.add_argument("--end-date", default=TEST_END)
    return parser.parse_args()


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _read_metrics(path: Path, split: str, seeds: list[int]) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"basin": str})
    df["basin"] = df["basin"].astype(str).str.zfill(8)
    df["abs_FHV"] = pd.to_numeric(df["FHV"], errors="coerce").abs()
    for metric in METRICS:
        df[metric] = pd.to_numeric(df[metric], errors="coerce")
    return df[(df["split"] == split) & (df["seed"].isin(seeds))].copy()


def _read_optional_csv(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, dtype={"gauge_id": str})
    df["basin"] = df["gauge_id"].astype(str).str.zfill(8)
    if columns is None:
        return df
    keep = ["basin"] + [col for col in columns if col in df.columns]
    return df[keep].copy()


def _metadata(args: argparse.Namespace) -> pd.DataFrame:
    attrs = _read_optional_csv(
        _resolve(args.drbc_attributes),
        [
            "gauge_id",
            "gauge_name",
            "state",
            "lat_gage",
            "lng_gage",
            "drain_sqkm_attr",
            "basin_area_sqkm_geom",
            "forest_pct",
            "developed_pct",
            "crops_pct",
            "wetland_pct",
            "dom_land_cover",
            "p_mean",
            "pet_mean",
            "aridity",
            "frac_snow",
            "elev_mean_m",
            "slope_pct",
            "baseflow_index_pct",
            "soil_permeability_index",
            "soil_water_table_depth_m",
        ],
    )
    quality = _read_optional_csv(
        _resolve(args.streamflow_quality),
        [
            "obs_years_usable",
            "obs_coverage_ratio_active_span",
            "FLOW_PCT_EST_VALUES",
            "BASIN_BOUNDARY_CONFIDENCE",
            "STOR_NOR_2009",
            "MAJ_NDAMS_2009",
            "CANALS_PCT",
            "FRESHW_WITHDRAWAL",
            "hydromod_risk",
        ],
    )
    events = _read_optional_csv(
        _resolve(args.event_response),
        [
            "selected_threshold_quantile",
            "selected_threshold_value",
            "q99_event_count",
            "event_count",
            "annual_peak_years",
            "unit_area_peak_median",
            "unit_area_peak_p90",
            "q99_event_frequency",
            "rbi",
            "rising_time_median_hours",
            "event_duration_median_hours",
            "annual_peak_unit_area_median",
            "annual_peak_unit_area_p90",
        ],
    )

    meta = attrs
    for frame in (quality, events):
        if frame.empty:
            continue
        meta = frame if meta.empty else meta.merge(frame, on="basin", how="outer")
    return meta


def _observed_streamflow_stats(
    basins: list[str], timeseries_dir: Path, start_date: str, end_date: str
) -> pd.DataFrame:
    rows = []
    for basin in sorted(basins):
        path = timeseries_dir / f"{basin}.nc"
        row: dict[str, object] = {"basin": basin, "timeseries_path": str(path.relative_to(REPO_ROOT)) if path.exists() else ""}
        if not path.exists():
            row["obs_status"] = "missing_timeseries"
            rows.append(row)
            continue

        with xr.open_dataset(path) as ds:
            q = ds["Streamflow"].sel(date=slice(start_date, end_date)).to_series()
        q = pd.to_numeric(q, errors="coerce").dropna()
        row["obs_status"] = "ok"
        row["test_valid_hours"] = int(q.size)
        if q.empty:
            rows.append(row)
            continue

        mean = float(q.mean())
        std = float(q.std(ddof=0))
        row.update(
            {
                "obs_mean": mean,
                "obs_std": std,
                "obs_cv": float(std / mean) if mean != 0 else np.nan,
                "obs_min": float(q.min()),
                "obs_q05": float(q.quantile(0.05)),
                "obs_q50": float(q.quantile(0.50)),
                "obs_q95": float(q.quantile(0.95)),
                "obs_q99": float(q.quantile(0.99)),
                "obs_max": float(q.max()),
                "obs_near_zero_fraction": float((q.abs() < 1e-6).mean()),
                "obs_sum": float(q.sum()),
                "obs_variance_denominator": float(((q - mean) ** 2).sum()),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def _outlier_records(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for metric in METRICS:
        for (model, seed, epoch), group in df.groupby(["model", "seed", "epoch"], sort=True):
            values = group[["basin", metric]].dropna().copy()
            if values.empty:
                continue
            q1 = float(values[metric].quantile(0.25))
            q3 = float(values[metric].quantile(0.75))
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            flagged = values[(values[metric] < lower) | (values[metric] > upper)].copy()
            if flagged.empty:
                continue
            flagged["metric"] = metric
            flagged["value"] = flagged[metric]
            flagged["model"] = model
            flagged["seed"] = int(seed)
            flagged["epoch"] = int(epoch)
            flagged["q25"] = q1
            flagged["q75"] = q3
            flagged["iqr"] = iqr
            flagged["lower_fence"] = lower
            flagged["upper_fence"] = upper
            flagged["outlier_side"] = np.where(flagged["value"] < lower, "low", "high")
            flagged["distance_from_fence"] = np.where(
                flagged["value"] < lower, lower - flagged["value"], flagged["value"] - upper
            )
            flagged["iqr_scaled_distance"] = np.where(
                iqr > 0, flagged["distance_from_fence"] / iqr, np.nan
            )
            rows.append(
                flagged[
                    [
                        "model",
                        "seed",
                        "epoch",
                        "metric",
                        "basin",
                        "value",
                        "outlier_side",
                        "q25",
                        "q75",
                        "iqr",
                        "lower_fence",
                        "upper_fence",
                        "distance_from_fence",
                        "iqr_scaled_distance",
                    ]
                ]
            )
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def _metric_axis_extremes(df: pd.DataFrame, top_n: int) -> pd.DataFrame:
    rows = []
    id_cols = ["model", "seed", "split", "epoch", "basin"]
    for metric in METRICS:
        values = df[id_cols + [metric]].dropna().copy()
        if values.empty:
            continue
        values = values.rename(columns={metric: "value"})
        low = values.sort_values("value", ascending=True).head(top_n).copy()
        high = values.sort_values("value", ascending=False).head(top_n).copy()
        low["axis_side"] = "low"
        high["axis_side"] = "high"
        low["axis_rank"] = range(1, len(low) + 1)
        high["axis_rank"] = range(1, len(high) + 1)
        both = pd.concat([low, high], ignore_index=True)
        both["metric"] = metric
        rows.append(both[["metric", "axis_side", "axis_rank", *id_cols, "value"]])
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _basin_summary(df: pd.DataFrame, outliers: pd.DataFrame) -> pd.DataFrame:
    base = df.groupby("basin").agg(
        n_metric_rows=("basin", "size"),
        n_models=("model", "nunique"),
        n_seeds=("seed", "nunique"),
        n_epochs=("epoch", "nunique"),
        min_NSE=("NSE", "min"),
        median_NSE=("NSE", "median"),
        min_KGE=("KGE", "min"),
        median_KGE=("KGE", "median"),
        min_FHV=("FHV", "min"),
        max_FHV=("FHV", "max"),
        median_abs_FHV=("abs_FHV", "median"),
        max_abs_FHV=("abs_FHV", "max"),
        max_Peak_Timing=("Peak-Timing", "max"),
        median_Peak_Timing=("Peak-Timing", "median"),
        max_Peak_MAPE=("Peak-MAPE", "max"),
        median_Peak_MAPE=("Peak-MAPE", "median"),
    ).reset_index()

    if outliers.empty:
        base["outlier_record_count"] = 0
        base["outlier_metric_count"] = 0
        base["outlier_metrics"] = ""
        base["max_iqr_scaled_distance"] = np.nan
        return base

    counts = outliers.groupby("basin").agg(
        outlier_record_count=("metric", "size"),
        outlier_metric_count=("metric", "nunique"),
        max_iqr_scaled_distance=("iqr_scaled_distance", "max"),
    ).reset_index()
    metric_lists = (
        outliers.groupby("basin")["metric"]
        .apply(lambda x: " ".join(sorted(set(map(str, x)))))
        .rename("outlier_metrics")
        .reset_index()
    )
    metric_counts = (
        outliers.pivot_table(index="basin", columns="metric", values="value", aggfunc="size", fill_value=0)
        .add_prefix("outlier_count_")
        .reset_index()
    )
    summary = base.merge(counts, on="basin", how="left").merge(metric_lists, on="basin", how="left")
    summary = summary.merge(metric_counts, on="basin", how="left")
    for col in summary.columns:
        if col.startswith("outlier_count_") or col in {"outlier_record_count", "outlier_metric_count"}:
            summary[col] = summary[col].fillna(0).astype(int)
    summary["outlier_metrics"] = summary["outlier_metrics"].fillna("")
    return summary


def _metric_basin_summary(outliers: pd.DataFrame) -> pd.DataFrame:
    if outliers.empty:
        return pd.DataFrame()
    return (
        outliers.groupby(["metric", "basin", "outlier_side"])
        .agg(
            outlier_record_count=("value", "size"),
            worst_low_value=("value", "min"),
            worst_high_value=("value", "max"),
            max_iqr_scaled_distance=("iqr_scaled_distance", "max"),
            model_seed_epochs=(
                "value",
                lambda s: "",
            ),
        )
        .reset_index()
        .drop(columns=["model_seed_epochs"])
    )


def _markdown_table(df: pd.DataFrame, index: bool = True) -> str:
    if df.empty:
        return ""
    table = df.copy()
    if index:
        table = table.reset_index()
    table = table.fillna("")
    headers = [str(col) for col in table.columns]
    rows = []
    for _, row in table.iterrows():
        rows.append([str(row[col]) for col in table.columns])

    def fmt(values: list[str]) -> str:
        return "| " + " | ".join(value.replace("\n", " ") for value in values) + " |"

    return "\n".join(
        [
            fmt(headers),
            fmt(["---"] * len(headers)),
            *[fmt(row) for row in rows],
        ]
    )


def _write_report(
    output_dir: Path,
    df: pd.DataFrame,
    outliers: pd.DataFrame,
    basin_summary: pd.DataFrame,
    axis_extremes: pd.DataFrame,
) -> None:
    metric_counts = (
        outliers.groupby("metric")
        .agg(outlier_records=("basin", "size"), unique_basins=("basin", "nunique"))
        .sort_values(["outlier_records", "unique_basins"], ascending=False)
        if not outliers.empty
        else pd.DataFrame(columns=["outlier_records", "unique_basins"])
    )
    top_basins = basin_summary.sort_values(
        ["outlier_record_count", "max_iqr_scaled_distance"], ascending=False
    ).head(12)

    lines = [
        "# Subset300 epoch metric outlier diagnostics",
        "",
        f"- Input rows: `{len(df)}`",
        f"- Split: `{df['split'].iloc[0] if not df.empty else ''}`",
        f"- Seeds: `{', '.join(map(str, sorted(df['seed'].unique())))}`",
        f"- Epochs: `{', '.join(f'{int(e):03d}' for e in sorted(df['epoch'].unique()))}`",
        f"- Outlier rule: per `model/seed/epoch/metric` standard boxplot 1.5 IQR fence",
        "",
        "## Metric outlier counts",
        "",
        _markdown_table(metric_counts) if not metric_counts.empty else "No outliers found.",
        "",
        "## Most repeated outlier basins",
        "",
        _markdown_table(
            top_basins[
                [
                    "basin",
                    "gauge_name",
                    "state",
                    "outlier_record_count",
                    "outlier_metric_count",
                    "outlier_metrics",
                    "min_NSE",
                    "min_KGE",
                    "max_FHV",
                    "max_abs_FHV",
                    "max_Peak_MAPE",
                    "obs_mean",
                    "obs_std",
                    "obs_cv",
                    "hydromod_risk",
                    "STOR_NOR_2009",
                ]
            ],
            index=False,
        ),
        "",
        "## Axis-expanding records",
        "",
        "See `metric_axis_extremes.csv` for the top low/high values per metric. "
        "Large negative `NSE`/`KGE` and large positive `FHV`/`Peak-MAPE` are the values that expand the visible axes.",
    ]
    (output_dir / "outlier_diagnostics_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    input_path = _resolve(args.input)
    output_dir = _resolve(args.output_dir)
    timeseries_dir = _resolve(args.timeseries_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = _read_metrics(input_path, args.split, args.seeds)
    if df.empty:
        raise SystemExit(f"No rows found for split={args.split} seeds={args.seeds} in {input_path}")

    outliers = _outlier_records(df)
    axis_extremes = _metric_axis_extremes(df, args.top_n_extremes)
    basin_summary = _basin_summary(df, outliers)

    metadata = _metadata(args)
    observed_stats = _observed_streamflow_stats(
        sorted(df["basin"].unique()), timeseries_dir, args.start_date, args.end_date
    )
    basin_summary = basin_summary.merge(metadata, on="basin", how="left")
    basin_summary = basin_summary.merge(observed_stats, on="basin", how="left")

    if not outliers.empty:
        outliers = outliers.merge(metadata, on="basin", how="left")
        outliers = outliers.merge(observed_stats, on="basin", how="left")
    if not axis_extremes.empty:
        axis_extremes = axis_extremes.merge(metadata, on="basin", how="left")
        axis_extremes = axis_extremes.merge(observed_stats, on="basin", how="left")

    metric_basin_summary = _metric_basin_summary(outliers)
    if not metric_basin_summary.empty:
        metric_basin_summary = metric_basin_summary.merge(metadata, on="basin", how="left")
        metric_basin_summary = metric_basin_summary.merge(observed_stats, on="basin", how="left")

    outliers.to_csv(output_dir / "outlier_records.csv", index=False)
    axis_extremes.to_csv(output_dir / "metric_axis_extremes.csv", index=False)
    basin_summary.sort_values(
        ["outlier_record_count", "max_iqr_scaled_distance"], ascending=False
    ).to_csv(output_dir / "outlier_basin_summary.csv", index=False)
    metric_basin_summary.to_csv(output_dir / "outlier_metric_basin_summary.csv", index=False)
    observed_stats.to_csv(output_dir / "test_observed_streamflow_stats.csv", index=False)

    metadata_json = {
        "input": str(input_path.relative_to(REPO_ROOT)),
        "output_dir": str(output_dir.relative_to(REPO_ROOT)),
        "split": args.split,
        "seeds": args.seeds,
        "metrics": METRICS,
        "outlier_rule": "Per model/seed/epoch/metric 1.5 IQR boxplot fence.",
        "test_observed_stats_window": [args.start_date, args.end_date],
        "outputs": {
            "outlier_records": "outlier_records.csv",
            "metric_axis_extremes": "metric_axis_extremes.csv",
            "outlier_basin_summary": "outlier_basin_summary.csv",
            "outlier_metric_basin_summary": "outlier_metric_basin_summary.csv",
            "test_observed_streamflow_stats": "test_observed_streamflow_stats.csv",
            "report": "outlier_diagnostics_report.md",
        },
    }
    (output_dir / "outlier_diagnostics_metadata.json").write_text(
        json.dumps(metadata_json, indent=2), encoding="utf-8"
    )
    _write_report(output_dir, df, outliers, basin_summary, axis_extremes)

    print(f"Wrote outlier diagnostics to {output_dir}")
    print(f"Outlier records: {len(outliers)}")
    print(f"Outlier basins: {outliers['basin'].nunique() if not outliers.empty else 0}")


if __name__ == "__main__":
    main()
