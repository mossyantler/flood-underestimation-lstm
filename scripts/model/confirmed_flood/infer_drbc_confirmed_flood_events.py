#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "torch==2.4.1",
#   "neuralhydrology>=1.13",
# ]
# ///
"""Model 1/2 inference on DRBC confirmed flood events.

Confirmed flood catalog의 각 event에 대해 LSTM warmup을 포함한 event window를
추론하고, primary hydrograph/export 계열과 같은 lean time-series 산출물을 남긴다.

주요 출력:
  - output/model_analysis/confirmed_flood/inference/raw_model_exports/
  - output/model_analysis/confirmed_flood/inference/required_series/
  - output/model_analysis/confirmed_flood/inference/inference_manifest.csv
  - output/model_analysis/confirmed_flood/performance/drbc_confirmed_flood_performance.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
VENDOR_NH = ROOT / "vendor" / "neuralhydrology"
if str(VENDOR_NH) not in sys.path:
    sys.path.insert(0, str(VENDOR_NH))

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

from neuralhydrology.evaluation import get_tester
from neuralhydrology.datasetzoo import genericdataset as nh_genericdataset
from neuralhydrology.utils.config import Config
from neuralhydrology.utils.errors import NoEvaluationDataError


_ORIGINAL_LOAD_TIMESERIES = nh_genericdataset.load_timeseries


def _load_timeseries_with_date_index(data_dir: Path, basin: str) -> pd.DataFrame:
    df = _ORIGINAL_LOAD_TIMESERIES(data_dir, basin)
    if df.index.name != "date":
        df.index.name = "date"
    return df


nh_genericdataset.load_timeseries = _load_timeseries_with_date_index


DEFAULT_CATALOG_CSV = ROOT / "output/model_analysis/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv"
DEFAULT_RUN_ROOT = ROOT / "runs/subset_comparison"
DEFAULT_DATA_DIR = ROOT / "data" / "CAMELSH_generic" / "drbc_holdout_confirmed_flood_events"
DEFAULT_OUTPUT_DIR = ROOT / "output/model_analysis/confirmed_flood/inference"
DEFAULT_PERFORMANCE_DIR = ROOT / "output/model_analysis/confirmed_flood/performance"
DEFAULT_VALIDATION_EPOCHS = [5, 10, 15, 20, 25, 30]

RUN_RE = re.compile(r"camelsh_hourly_(model[12])_drbc_holdout_subset300_seed(\d+)_")
PRIMARY_EPOCHS: dict[tuple[str, int], int] = {
    ("model1", 111): 25,
    ("model1", 222): 10,
    ("model1", 444): 15,
    ("model2", 111): 5,
    ("model2", 222): 10,
    ("model2", 444): 10,
}
QUANTILE_COLUMNS = ["q50", "q90", "q95", "q99"]
REQUIRED_SERIES_COLUMNS = [
    "event_id",
    "seed",
    "basin",
    "model1_epoch",
    "model2_epoch",
    "peak_time",
    "datetime",
    "obs",
    "model1",
    "model2_q50_result",
    "q50",
    "q90",
    "q95",
    "q99",
    "q90_minus_q50",
    "q95_minus_q90",
    "q99_minus_q95",
    "q99_minus_q50",
    "model2_q50_minus_model1",
    "flood_tier",
    "noaa_corroborated",
    "period",
    "in_eval_window",
]
RAW_METADATA_COLUMNS = [
    "event_id",
    "basin",
    "peak_time",
    "window_start",
    "window_end",
    "eval_start",
    "eval_end",
    "flood_tier",
    "tier_limited",
    "noaa_corroborated",
    "period",
    "forcing_coverage_min",
    "peak_discharge_cms",
    "in_eval_window",
]
PRE_HOURS = 24
POST_HOURS = 168
WARMUP_DAYS = 21


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-csv", type=Path, default=DEFAULT_CATALOG_CSV)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="NeuralHydrology GenericDataset dir for confirmed flood inference.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--performance-dir", type=Path, default=DEFAULT_PERFORMANCE_DIR)
    parser.add_argument("--seeds", type=int, nargs="+", default=[111, 222, 444])
    parser.add_argument(
        "--epoch-mode",
        choices=["primary", "validation"],
        default="primary",
        help="Use validation-selected primary checkpoints or every validation checkpoint epoch.",
    )
    parser.add_argument(
        "--validation-epochs",
        type=int,
        nargs="+",
        default=DEFAULT_VALIDATION_EPOCHS,
        help="Epoch grid used with --epoch-mode validation.",
    )
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--limit-events", type=int, default=None, help="Smoke test용 event 수 제한")
    parser.add_argument("--limit-basins", type=int, default=None, help="Smoke test용 basin 수 제한")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def normalize_gauge_id(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(8)


def epoch_pairs_for_seed(seed: int, mode: str, validation_epochs: list[int]) -> list[tuple[int, int, str]]:
    if mode == "primary":
        return [(PRIMARY_EPOCHS[("model1", seed)], PRIMARY_EPOCHS[("model2", seed)], "primary")]
    return [(int(epoch), int(epoch), f"epoch{int(epoch):03d}") for epoch in validation_epochs]


def run_dirs(run_root: Path) -> dict[tuple[str, int], Path]:
    if not run_root.exists():
        raise FileNotFoundError(f"Missing run root: {run_root}")
    runs: dict[tuple[str, int], Path] = {}
    for path in sorted(run_root.iterdir()):
        if not path.is_dir():
            continue
        match = RUN_RE.match(path.name)
        if match:
            key = (match.group(1), int(match.group(2)))
            if key not in runs or path.stat().st_mtime > runs[key].stat().st_mtime:
                runs[key] = path
    return runs


def build_event_windows(
    catalog: pd.DataFrame,
    *,
    available_basins: set[str] | None = None,
    limit_events: int | None = None,
    limit_basins: int | None = None,
) -> pd.DataFrame:
    if catalog.empty:
        return catalog.copy()
    events = catalog.copy()
    events["basin"] = events["usgs_id"].map(normalize_gauge_id)
    events["peak_time"] = pd.to_datetime(events["peak_time"])
    if available_basins is not None:
        events = events[events["basin"].isin(available_basins)].copy()
    if limit_basins is not None:
        selected = sorted(events["basin"].dropna().unique())[:limit_basins]
        events = events[events["basin"].isin(selected)]
    events = events.sort_values(["basin", "peak_time"]).reset_index(drop=True)
    if limit_events is not None:
        events = events.head(limit_events).copy()
    if events.empty:
        return events

    base_ids = events.apply(
        lambda row: f"{row['basin']}_{pd.Timestamp(row['peak_time']).strftime('%Y%m%dT%H%M%S')}",
        axis=1,
    )
    duplicate_seq = base_ids.groupby(base_ids).cumcount()
    duplicate_counts = base_ids.map(base_ids.value_counts())
    events["event_id"] = [
        base if count == 1 else f"{base}_{seq + 1:02d}"
        for base, seq, count in zip(base_ids, duplicate_seq, duplicate_counts, strict=True)
    ]
    events["eval_start"] = events["peak_time"] - pd.Timedelta(hours=PRE_HOURS)
    events["eval_end"] = events["peak_time"] + pd.Timedelta(hours=POST_HOURS)
    events["window_start"] = (
        events["peak_time"] - pd.Timedelta(days=WARMUP_DAYS, hours=PRE_HOURS)
    ).dt.floor("D")
    events["window_end"] = events["eval_end"].dt.ceil("D") - pd.Timedelta(hours=1)
    keep_columns = [
        "event_id",
        "basin",
        "peak_time",
        "window_start",
        "window_end",
        "eval_start",
        "eval_end",
        "peak_discharge_cms",
        "flood_tier",
        "tier_limited",
        "noaa_corroborated",
        "period",
        "forcing_coverage_min",
    ]
    return events[[column for column in keep_columns if column in events.columns]].reset_index(drop=True)


def available_data_basins(data_dir: Path = DEFAULT_DATA_DIR) -> set[str]:
    """Return basins that have both time-series files and static attributes."""
    time_series_dir = data_dir / "time_series"
    attributes_csv = data_dir / "attributes" / "static_attributes.csv"
    if not time_series_dir.exists() or not attributes_csv.exists():
        raise FileNotFoundError(f"Missing prepared data under {data_dir}")

    time_series_basins = {normalize_gauge_id(path.stem) for path in time_series_dir.glob("*.nc")}
    attributes = pd.read_csv(attributes_csv, dtype={"gauge_id": str}, usecols=["gauge_id"])
    attribute_basins = {normalize_gauge_id(value) for value in attributes["gauge_id"].dropna()}
    return time_series_basins & attribute_basins


def write_basin_file(basins: list[str], output_dir: Path) -> Path:
    basin_file = output_dir / "drbc_confirmed_flood_basins.txt"
    basin_file.parent.mkdir(parents=True, exist_ok=True)
    basin_file.write_text("\n".join(sorted(set(basins))) + "\n", encoding="utf-8")
    return basin_file


def patch_config(
    *,
    cfg: Config,
    run_dir: Path,
    data_dir: Path,
    basin_file: Path,
    device: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    batch_size: int | None,
) -> Config:
    split_dir = ROOT / "configs" / "pilot" / "basin_splits" / "scaling_300"
    update = {
        "run_dir": str(run_dir),
        "train_dir": str(run_dir / "train_data"),
        "img_log_dir": str(run_dir / "img_log"),
        "data_dir": str(data_dir),
        "train_basin_file": str(split_dir / "train.txt"),
        "validation_basin_file": str(split_dir / "validation.txt"),
        "test_basin_file": str(basin_file),
        "test_start_date": start.strftime("%d/%m/%Y"),
        "test_end_date": end.strftime("%d/%m/%Y"),
        "device": device,
        "num_workers": 0,
    }
    if batch_size is not None:
        update["batch_size"] = int(batch_size)
    cfg.update_config(update, dev_mode=True)
    return cfg


def move_batch_to_device(data: dict, device: torch.device) -> dict:
    for key in list(data.keys()):
        if key.startswith("x_d"):
            data[key] = {freq: value.to(device) for freq, value in data[key].items()}
        elif not key.startswith("date"):
            data[key] = data[key].to(device)
    return data


def target_scale_and_center(tester, target: str) -> tuple[float, float]:
    scale_obj = tester.scaler["xarray_feature_scale"][target]
    center_obj = tester.scaler["xarray_feature_center"][target]
    scale = scale_obj.to_array().values if hasattr(scale_obj, "to_array") else scale_obj.values
    center = center_obj.to_array().values if hasattr(center_obj, "to_array") else center_obj.values
    return float(np.ravel(scale)[0]), float(np.ravel(center)[0])


def render_dates(batch: dict) -> pd.DatetimeIndex:
    dates = batch["date"]
    if getattr(dates, "ndim", 1) == 2:
        return pd.to_datetime(dates[:, -1])
    return pd.to_datetime(dates)


def raw_fieldnames(model: str, quantile_names: list[str]) -> list[str]:
    if model == "model1":
        return [*RAW_METADATA_COLUMNS, "datetime", "obs", "model1"]
    return [*RAW_METADATA_COLUMNS, "datetime", "obs", "model2_q50_result", *quantile_names]


def render_event_metadata(event: pd.Series, when: pd.Timestamp) -> dict[str, Any]:
    eval_start = pd.Timestamp(event["eval_start"])
    eval_end = pd.Timestamp(event["eval_end"])
    return {
        "event_id": event["event_id"],
        "basin": event["basin"],
        "peak_time": pd.Timestamp(event["peak_time"]).isoformat(),
        "window_start": pd.Timestamp(event["window_start"]).isoformat(),
        "window_end": pd.Timestamp(event["window_end"]).isoformat(),
        "eval_start": eval_start.isoformat(),
        "eval_end": eval_end.isoformat(),
        "flood_tier": event.get("flood_tier"),
        "tier_limited": event.get("tier_limited"),
        "noaa_corroborated": event.get("noaa_corroborated"),
        "period": event.get("period"),
        "forcing_coverage_min": event.get("forcing_coverage_min"),
        "peak_discharge_cms": event.get("peak_discharge_cms"),
        "in_eval_window": bool(eval_start <= when <= eval_end),
    }


def export_predictions_for_model(
    *,
    run_dir: Path,
    model: str,
    epoch: int,
    events: pd.DataFrame,
    data_dir: Path,
    basin_file: Path,
    output_csv: Path,
    device: str,
    batch_size: int | None,
) -> Path:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_csv.unlink(missing_ok=True)

    global_start = pd.to_datetime(events["window_start"]).min().floor("D")
    global_end = pd.to_datetime(events["window_end"]).max().ceil("D") - pd.Timedelta(hours=1)
    cfg = patch_config(
        cfg=Config(run_dir / "config.yml"),
        run_dir=run_dir,
        data_dir=data_dir,
        basin_file=basin_file,
        device=device,
        start=global_start,
        end=global_end,
        batch_size=batch_size,
    )
    tester = get_tester(cfg=cfg, run_dir=run_dir, period="test", init_model=True)
    tester._load_weights(epoch=epoch)
    tester.model.eval()

    target = cfg.target_variables[0]
    scale, center = target_scale_and_center(tester, target)
    quantiles = getattr(cfg, "quantiles", None) if model == "model2" else None
    quantile_names = [f"q{int(q * 100):02d}" for q in quantiles] if quantiles else []
    fieldnames = raw_fieldnames(model, quantile_names)
    basin_events = {
        basin: group.sort_values("peak_time").copy()
        for basin, group in events.groupby("basin", sort=True)
    }
    run_basins = [basin for basin in tester.basins if basin in basin_events]
    print(
        f"Exporting {model} {run_dir.name} epoch {epoch:03d}: "
        f"{len(run_basins)} basins, {len(events)} events",
        flush=True,
    )

    tmp_csv = output_csv.with_suffix(output_csv.suffix + ".tmp")
    tmp_csv.unlink(missing_ok=True)
    with tmp_csv.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()

        for basin_idx, basin in enumerate(run_basins, start=1):
            print(f"  {model} basin {basin_idx}/{len(run_basins)}: {basin}", flush=True)
            for _, event in basin_events[basin].iterrows():
                start = pd.Timestamp(event["window_start"])
                end = pd.Timestamp(event["window_end"])
                cfg.update_config(
                    {
                        "test_start_date": start.floor("D").strftime("%d/%m/%Y"),
                        "test_end_date": (end.ceil("D") - pd.Timedelta(hours=1)).strftime("%d/%m/%Y"),
                    },
                    dev_mode=True,
                )
                try:
                    dataset = tester._get_dataset(basin)
                except (NoEvaluationDataError, FileNotFoundError) as exc:
                    print(f"    skipping {basin} {event['event_id']}: {exc}", flush=True)
                    continue
                if dataset is None or len(dataset) == 0:
                    continue

                loader = DataLoader(dataset, batch_size=cfg.batch_size, num_workers=0, collate_fn=dataset.collate_fn)
                rows: list[dict[str, Any]] = []
                with torch.no_grad():
                    for batch in loader:
                        batch = move_batch_to_device(batch, tester.device)
                        batch = tester.model.pre_model_hook(batch, is_train=False)
                        predictions = tester.model(batch)
                        dates = render_dates(batch)
                        obs = batch["y"][:, -1, 0].detach().cpu().numpy() * scale + center
                        if model == "model1":
                            y_hat = predictions["y_hat"][:, -1, 0].detach().cpu().numpy() * scale + center
                            if target in getattr(cfg, "clip_targets_to_zero", []):
                                y_hat = np.where(y_hat < 0, 0, y_hat)
                            for date, obs_value, pred_value in zip(dates, obs, y_hat, strict=True):
                                when = pd.Timestamp(date)
                                rows.append(
                                    {
                                        **render_event_metadata(event, when),
                                        "datetime": when,
                                        "obs": float(obs_value),
                                        "model1": float(pred_value),
                                    }
                                )
                        else:
                            y_hat = predictions["y_hat"][:, -1, 0].detach().cpu().numpy() * scale + center
                            y_quantiles = predictions["y_quantiles"][:, -1, :]
                            y_quantiles = y_quantiles.reshape(
                                y_quantiles.shape[0], len(cfg.target_variables), len(quantiles)
                            )
                            y_quantiles = y_quantiles[:, 0, :].detach().cpu().numpy() * scale + center
                            if target in getattr(cfg, "clip_targets_to_zero", []):
                                y_hat = np.where(y_hat < 0, 0, y_hat)
                                y_quantiles = np.where(y_quantiles < 0, 0, y_quantiles)
                            for date, obs_value, median_value, values in zip(dates, obs, y_hat, y_quantiles, strict=True):
                                when = pd.Timestamp(date)
                                row = {
                                    **render_event_metadata(event, when),
                                    "datetime": when,
                                    "obs": float(obs_value),
                                    "model2_q50_result": float(median_value),
                                }
                                for name, value in zip(quantile_names, values, strict=True):
                                    row[name] = float(value)
                                rows.append(row)

                if not rows:
                    continue
                frame = pd.DataFrame(rows).drop_duplicates("datetime").sort_values("datetime")
                clipped = frame[(frame["datetime"] >= start) & (frame["datetime"] <= end)].copy()
                if clipped.empty:
                    continue
                clipped["datetime"] = clipped["datetime"].map(lambda value: pd.Timestamp(value).isoformat())
                writer.writerows(clipped[fieldnames].to_dict("records"))

    tmp_csv.replace(output_csv)
    return output_csv


def merge_seed_series(
    *,
    seed: int,
    model1_epoch: int,
    model2_epoch: int,
    model1_csv: Path,
    model2_csv: Path,
    output_csv: Path,
) -> Path:
    left = pd.read_csv(model1_csv, dtype={"basin": str}, parse_dates=["datetime"])
    right = pd.read_csv(model2_csv, dtype={"basin": str}, parse_dates=["datetime"])
    for frame in (left, right):
        frame["basin"] = frame["basin"].map(normalize_gauge_id)
        frame["event_id"] = frame["event_id"].astype(str)
    df = left.merge(
        right[["event_id", "basin", "peak_time", "datetime", "model2_q50_result", *QUANTILE_COLUMNS]],
        on=["event_id", "basin", "peak_time", "datetime"],
        how="inner",
        validate="one_to_one",
    )
    if df.empty:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_csv, index=False)
        return output_csv

    df["q90_minus_q50"] = df["q90"] - df["q50"]
    df["q95_minus_q90"] = df["q95"] - df["q90"]
    df["q99_minus_q95"] = df["q99"] - df["q95"]
    df["q99_minus_q50"] = df["q99"] - df["q50"]
    df["model2_q50_minus_model1"] = df["q50"] - df["model1"]
    df.insert(1, "seed", seed)
    df.insert(3, "model1_epoch", model1_epoch)
    df.insert(4, "model2_epoch", model2_epoch)
    df = df[REQUIRED_SERIES_COLUMNS].sort_values(["basin", "peak_time", "datetime"])
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    tmp_csv = output_csv.with_suffix(output_csv.suffix + ".tmp")
    df.to_csv(tmp_csv, index=False)
    tmp_csv.replace(output_csv)
    return output_csv


def _eval_mask(df: pd.DataFrame) -> pd.Series:
    if "in_eval_window" not in df.columns:
        return pd.Series(True, index=df.index)
    values = df["in_eval_window"]
    if values.dtype == bool:
        return values
    return values.astype(str).str.lower().isin(["true", "1", "yes"])


def _nrmse(obs: pd.Series, pred: pd.Series, obs_peak: float) -> float:
    denom = obs_peak if obs_peak > 0 else 1.0
    return float(np.sqrt(((obs - pred) ** 2).mean()) / denom)


def _row_from_event(
    *,
    event_id: str,
    grp: pd.DataFrame,
    model: str,
    quantile: str,
    pred_col: str,
) -> dict[str, Any]:
    obs_peak = float(grp["obs"].max())
    pred_peak = float(grp[pred_col].max())
    first = grp.iloc[0]
    return {
        "event_id": event_id,
        "usgs_id": normalize_gauge_id(first["basin"]),
        "peak_time": first["peak_time"],
        "model": model,
        "seed": int(first["seed"]),
        "model1_epoch": int(first["model1_epoch"]),
        "model2_epoch": int(first["model2_epoch"]),
        "quantile": quantile,
        "obs_peak_cms": obs_peak,
        "pred_peak_cms": pred_peak,
        "peak_under_deficit": (obs_peak - pred_peak) / obs_peak if obs_peak > 0 else None,
        "is_underestimate": bool(pred_peak < obs_peak),
        "exceeds_minor_stage": True,
        "event_nrmse": _nrmse(grp["obs"], grp[pred_col], obs_peak),
        "flood_tier": first.get("flood_tier"),
        "noaa_corroborated": first.get("noaa_corroborated"),
        "period": first.get("period"),
    }


def compute_performance_rows(series: pd.DataFrame) -> list[dict[str, Any]]:
    if series.empty:
        return []
    df = series.copy()
    df["basin"] = df["basin"].map(normalize_gauge_id)
    df = df[_eval_mask(df)].copy()
    if df.empty:
        return []
    rows: list[dict[str, Any]] = []
    for event_id, grp in df.groupby("event_id", sort=True):
        grp = grp.sort_values("datetime")
        rows.append(_row_from_event(event_id=event_id, grp=grp, model="model1", quantile="det", pred_col="model1"))
        for quantile in QUANTILE_COLUMNS:
            if quantile in grp.columns:
                rows.append(
                    _row_from_event(event_id=event_id, grp=grp, model="model2", quantile=quantile, pred_col=quantile)
                )
    return rows


def write_performance_csv(series_paths: list[Path], output_csv: Path) -> Path:
    rows: list[dict[str, Any]] = []
    for path in series_paths:
        if not path.exists():
            continue
        series = pd.read_csv(path, dtype={"basin": str})
        rows.extend(compute_performance_rows(series))
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(output_csv, index=False)
    return output_csv


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.performance_dir.mkdir(parents=True, exist_ok=True)

    catalog = pd.read_csv(args.catalog_csv, dtype={"usgs_id": str})
    catalog_basins = set(catalog["usgs_id"].map(normalize_gauge_id))
    ready_basins = available_data_basins(args.data_dir)
    events = build_event_windows(
        catalog,
        available_basins=ready_basins,
        limit_events=args.limit_events,
        limit_basins=args.limit_basins,
    )
    if events.empty:
        print("Prepared data와 매칭되는 confirmed flood event가 없습니다.")
        return 0

    basins = events["basin"].dropna().unique().tolist()
    basin_file = write_basin_file(basins, args.output_dir)
    write_basin_file(basins, args.performance_dir)
    skipped_basins = sorted(catalog_basins - ready_basins)
    print(
        f"Data-ready basins: {len(basins)} used, {len(skipped_basins)} skipped "
        f"(missing time_series or static attributes)."
    )
    if skipped_basins:
        print(f"Skipped basin sample: {', '.join(skipped_basins[:20])}")
    print(f"Basins in catalog windows: {len(basins)}, Events: {len(events)}")

    raw_dir = args.output_dir / "raw_model_exports"
    series_dir = args.output_dir / "required_series"
    runs = run_dirs(args.run_root)
    manifest_rows: list[dict[str, Any]] = []
    series_paths: list[Path] = []

    for seed in args.seeds:
        model1_run = runs.get(("model1", seed))
        model2_run = runs.get(("model2", seed))
        if model1_run is None or model2_run is None:
            print(f"Skipping seed {seed}: missing Model 1 or Model 2 run directory.")
            continue

        for model1_epoch, model2_epoch, epoch_label in epoch_pairs_for_seed(
            seed, args.epoch_mode, args.validation_epochs
        ):
            model1_checkpoint = model1_run / f"model_epoch{model1_epoch:03d}.pt"
            model2_checkpoint = model2_run / f"model_epoch{model2_epoch:03d}.pt"
            if not model1_checkpoint.exists() or not model2_checkpoint.exists():
                print(
                    f"Skipping seed {seed} {epoch_label}: missing checkpoint "
                    f"(Model 1 epoch {model1_epoch:03d}, Model 2 epoch {model2_epoch:03d})."
                )
                continue

            model1_csv = raw_dir / f"model1_seed{seed}_epoch{model1_epoch:03d}.csv"
            model2_csv = raw_dir / f"model2_seed{seed}_epoch{model2_epoch:03d}.csv"
            series_csv = series_dir / f"seed{seed}" / f"{epoch_label}_required_series.csv"

            if args.force or not model1_csv.exists():
                export_predictions_for_model(
                    run_dir=model1_run,
                    model="model1",
                    epoch=model1_epoch,
                    events=events,
                    data_dir=args.data_dir,
                    basin_file=basin_file,
                    output_csv=model1_csv,
                    device=args.device,
                    batch_size=args.batch_size,
                )
            if args.force or not model2_csv.exists():
                export_predictions_for_model(
                    run_dir=model2_run,
                    model="model2",
                    epoch=model2_epoch,
                    events=events,
                    data_dir=args.data_dir,
                    basin_file=basin_file,
                    output_csv=model2_csv,
                    device=args.device,
                    batch_size=args.batch_size,
                )
            if args.force or not series_csv.exists():
                merge_seed_series(
                    seed=seed,
                    model1_epoch=model1_epoch,
                    model2_epoch=model2_epoch,
                    model1_csv=model1_csv,
                    model2_csv=model2_csv,
                    output_csv=series_csv,
                )
            series_paths.append(series_csv)
            manifest_rows.append(
                {
                    "seed": seed,
                    "epoch_mode": args.epoch_mode,
                    "epoch_label": epoch_label,
                    "model1_run": str(model1_run),
                    "model2_run": str(model2_run),
                    "model1_epoch": model1_epoch,
                    "model2_epoch": model2_epoch,
                    "model1_csv": str(model1_csv),
                    "model2_csv": str(model2_csv),
                    "required_series_csv": str(series_csv),
                }
            )

    manifest = pd.DataFrame(manifest_rows)
    manifest_path = args.output_dir / "inference_manifest.csv"
    manifest.to_csv(manifest_path, index=False)
    events_path = args.output_dir / "confirmed_flood_event_windows_used.csv"
    events.to_csv(events_path, index=False)
    performance_csv = args.performance_dir / "drbc_confirmed_flood_performance.csv"
    write_performance_csv(series_paths, performance_csv)

    summary = {
        "catalog_csv": str(args.catalog_csv),
        "output_dir": str(args.output_dir),
        "data_dir": str(args.data_dir),
        "performance_csv": str(performance_csv),
        "device": args.device,
        "seeds": args.seeds,
        "epoch_mode": args.epoch_mode,
        "validation_epochs": args.validation_epochs,
        "n_catalog_events": int(len(events)),
        "n_catalog_basins": int(events["basin"].nunique()),
        "manifest": str(manifest_path),
        "event_windows_used": str(events_path),
        "raw_model_exports": str(raw_dir),
        "required_series": str(series_dir),
    }
    summary_path = args.output_dir / "analysis_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote inference manifest: {manifest_path}")
    print(f"Wrote event windows: {events_path}")
    print(f"Wrote required series directory: {series_dir}")
    print(f"Wrote performance CSV: {performance_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
