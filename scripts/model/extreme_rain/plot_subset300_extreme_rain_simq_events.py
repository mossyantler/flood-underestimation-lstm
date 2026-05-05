#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "xarray>=2024.1",
#   "netCDF4>=1.6",
# ]
# ///

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_EVENT_MANIFEST = Path(
    "output/model_analysis/extreme_rain/primary/event_plots/event_plot_manifest.csv"
)
DEFAULT_COHORT_CSV = Path(
    "output/model_analysis/extreme_rain/primary/exposure/drbc_historical_stress_cohort.csv"
)
DEFAULT_STRESS_LONG_CSV = Path(
    "output/model_analysis/extreme_rain/primary/analysis/extreme_rain_stress_error_table_long.csv"
)
DEFAULT_SERIES_DIR = Path("output/model_analysis/extreme_rain/primary/inference/required_series")
DEFAULT_DATA_DIR = Path("data/CAMELSH_generic/drbc_holdout_broad/time_series")
DEFAULT_OUTPUT_DIR = Path("output/model_analysis/extreme_rain/primary/event_simq_plots")
DEFAULT_SEEDS = [111, 222, 444]
TIME_COLUMNS = [
    "rain_start",
    "rain_peak",
    "rain_end",
    "observed_response_peak_time",
]


def load_flow_examples_module() -> Any:
    module_path = Path(__file__).with_name("plot_subset300_extreme_rain_flow_graph_examples.py")
    spec = importlib.util.spec_from_file_location("extreme_rain_flow_graph_examples", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import plotting helpers from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


flow_examples = load_flow_examples_module()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Plot observed flow and simulated Model 1 / Model 2 quantile flow for every "
            "primary extreme-rain event used by event_plot_index.html."
        )
    )
    parser.add_argument("--event-manifest", type=Path, default=DEFAULT_EVENT_MANIFEST)
    parser.add_argument("--cohort-csv", type=Path, default=DEFAULT_COHORT_CSV)
    parser.add_argument("--stress-long-csv", type=Path, default=DEFAULT_STRESS_LONG_CSV)
    parser.add_argument("--series-dir", type=Path, default=DEFAULT_SERIES_DIR)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--basin-screening-csv", type=Path, default=flow_examples.DEFAULT_BASIN_SCREENING_CSV)
    parser.add_argument("--streamflow-quality-csv", type=Path, default=flow_examples.DEFAULT_STREAMFLOW_QUALITY_CSV)
    parser.add_argument("--seeds", type=int, nargs="+", default=DEFAULT_SEEDS)
    parser.add_argument("--padding-hours", type=int, default=24)
    return parser.parse_args()


def read_event_manifest(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing event plot manifest: {path}")
    manifest = pd.read_csv(path, dtype={"gauge_id": str, "event_id": str}, parse_dates=TIME_COLUMNS)
    manifest["gauge_id"] = manifest["gauge_id"].map(flow_examples.normalize_gauge_id)
    return manifest.sort_values(["rain_cohort", "stress_group", "response_class", "gauge_id", "event_id"])


def build_event_rows(manifest: pd.DataFrame, cohort: pd.DataFrame) -> pd.DataFrame:
    cohort_cols = [
        "gauge_id",
        "event_id",
        "response_window_start",
        "response_window_end",
        "streamflow_q99_threshold",
        "flood_ari2",
        "flood_ari25",
        "flood_ari50",
        "flood_ari100",
        "wet_rain_threshold_mm_h",
        *flow_examples.precip_event_columns(),
        *flow_examples.basin_metadata_columns(),
        "obs_peak_to_flood_ari50",
        "obs_peak_to_flood_ari100",
        "storm_group_id",
    ]
    cohort_merge_cols = [
        "gauge_id",
        "event_id",
        *[col for col in cohort_cols if col not in {"gauge_id", "event_id"} and col not in manifest.columns],
    ]
    events = manifest.merge(
        cohort[cohort_merge_cols],
        on=["gauge_id", "event_id"],
        how="left",
        validate="one_to_one",
    )
    missing = events[events["response_window_start"].isna()]["event_id"].tolist()
    if missing:
        raise RuntimeError(f"Missing cohort rows for {len(missing)} manifest events: {missing[:5]}")
    events["case_label"] = "Extreme-rain event hydrograph with simulated Q"
    events["case_key"] = "event_simq"
    return events.reset_index(drop=True)


def output_path_for_event(output_dir: Path, event: pd.Series) -> Path:
    stress_group = flow_examples.safe_slug(str(event["stress_group"]))
    response_class = flow_examples.safe_slug(str(event["response_class"]))
    filename = f"{flow_examples.safe_slug(str(event['event_id']))}.png"
    return output_dir / stress_group / response_class / filename


def write_readme(output_dir: Path, manifest_path: Path, event_count: int, seeds: list[int]) -> None:
    lines = [
        "# Extreme-Rain Event Sim-Q Plots",
        "",
        "These figures overlay observed streamflow with Model 1 and Model 2 quantile predictions for every primary extreme-rain event.",
        "Each plot has one rainfall panel and one flow panel per seed, matching the representative `flow_graph_diagnostic` figure style.",
        "A single legend box outside the plot groups line and marker meanings under `Rain` and `Streamflow`, then adds a `Basin` section with short basin and human-impact proxy tags.",
        "",
        f"- Events: {event_count}",
        f"- Seeds: {', '.join(str(seed) for seed in seeds)}",
        f"- Manifest: `{manifest_path.name}`",
        "",
        "The median-tier DRBC map index uses this manifest when it is present.",
        "",
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    seeds = sorted(set(args.seeds))
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = read_event_manifest(args.event_manifest)
    cohort = flow_examples.read_cohort(args.cohort_csv)
    cohort = flow_examples.add_basin_metadata(cohort, args.basin_screening_csv, args.streamflow_quality_csv)
    events = build_event_rows(manifest, cohort)
    event_ids = set(events["event_id"].astype(str))

    long_df = flow_examples.read_stress_long(args.stress_long_csv, seeds)
    selected_long = long_df[long_df["event_id"].isin(event_ids)].copy()
    all_series = {seed: flow_examples.read_required_series(args.series_dir, seed) for seed in seeds}
    rain_cache: dict[str, pd.Series] = {}

    manifest_rows: list[dict[str, Any]] = []
    total = len(events)
    for idx, (_, event) in enumerate(events.iterrows(), start=1):
        gauge_id = str(event["gauge_id"])
        if gauge_id not in rain_cache:
            rain_cache[gauge_id] = flow_examples.read_rain_series(args.data_dir, gauge_id)
        figure_path = output_path_for_event(output_dir, event)
        flow_examples.plot_case(
            case=event,
            event=event,
            all_series=all_series,
            rain=rain_cache[gauge_id],
            selected_long=selected_long,
            seeds=seeds,
            output_path=figure_path,
            padding_hours=int(args.padding_hours),
        )
        row = event.to_dict()
        row["plot_path"] = str(figure_path)
        row["plot_kind"] = "sim_q"
        manifest_rows.append(row)
        if idx % 25 == 0 or idx == total:
            print(f"Plotted {idx}/{total} sim-Q event hydrographs")

    manifest_out = pd.DataFrame(manifest_rows)
    manifest_path = output_dir / "event_simq_plot_manifest.csv"
    manifest_out.to_csv(manifest_path, index=False)
    write_readme(output_dir, manifest_path=manifest_path, event_count=total, seeds=seeds)
    print(f"Wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
