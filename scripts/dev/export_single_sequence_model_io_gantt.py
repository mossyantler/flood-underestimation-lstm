#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.8",
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "torch==2.4.1",
#   "xarray>=2024.1",
#   "neuralhydrology>=1.13",
# ]
# ///

from __future__ import annotations

import argparse
import json
import pickle
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
VENDOR_NH = ROOT / "vendor" / "neuralhydrology"
if str(VENDOR_NH) not in sys.path:
    sys.path.insert(0, str(VENDOR_NH))

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import xarray as xr
from torch.utils.data import DataLoader

from neuralhydrology.evaluation import get_tester
from neuralhydrology.utils.config import Config


RUN_RE = re.compile(r"camelsh_hourly_(model[12])_drbc_holdout_subset300_seed(\d+)_")
DEFAULT_RUN_ROOT = Path("runs/subset_comparison")
DEFAULT_SPLIT_DIR = Path("configs/pilot/basin_splits/scaling_300")
DEFAULT_DATA_DIR = Path("data/CAMELSH_generic/drbc_holdout_broad")
DEFAULT_OUTPUT_DIR = Path("output/basin/timeseries/sequence_structure")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export one exact 336-hour subset300 test sequence, its Model 1/2 epoch output, "
            "and a timing Gantt chart."
        )
    )
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--split-dir", type=Path, default=DEFAULT_SPLIT_DIR)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=111)
    parser.add_argument("--epoch", type=int, default=30)
    parser.add_argument(
        "--basin",
        default=None,
        help="Basin id. Defaults to the first basin in configs/pilot/basin_splits/scaling_300/test.txt.",
    )
    parser.add_argument(
        "--sample-index",
        type=int,
        default=0,
        help="Zero-based sample index within the selected basin test dataset.",
    )
    parser.add_argument(
        "--sequence-end",
        default=None,
        help="Optional sequence-end timestamp, e.g. 2014-01-01T23:00:00. Overrides --sample-index.",
    )
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--dpi", type=int, default=180)
    return parser.parse_args()


def normalize_basin(value: Any) -> str:
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(8)


def first_test_basin(split_dir: Path) -> str:
    test_file = split_dir / "test.txt"
    with test_file.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if line:
                return normalize_basin(line)
    raise ValueError(f"No basin id found in {test_file}")


def run_dirs(run_root: Path, seed: int) -> dict[str, Path]:
    runs: dict[str, Path] = {}
    for path in sorted(run_root.iterdir()):
        if not path.is_dir():
            continue
        match = RUN_RE.match(path.name)
        if not match:
            continue
        model, run_seed = match.group(1), int(match.group(2))
        if run_seed != seed:
            continue
        if model not in runs or path.stat().st_mtime > runs[model].stat().st_mtime:
            runs[model] = path
    missing = {"model1", "model2"} - set(runs)
    if missing:
        raise FileNotFoundError(f"Missing run directories for seed {seed}: {sorted(missing)}")
    return runs


def patch_config(cfg: Config, run_dir: Path, split_dir: Path, data_dir: Path, device: str) -> Config:
    cfg.update_config(
        {
            "run_dir": str(run_dir),
            "train_dir": str(run_dir / "train_data"),
            "img_log_dir": str(run_dir / "img_log"),
            "data_dir": str(data_dir),
            "train_basin_file": str(split_dir / "train.txt"),
            "validation_basin_file": str(split_dir / "validation.txt"),
            "test_basin_file": str(split_dir / "test.txt"),
            "device": device,
            "num_workers": 0,
            "batch_size": 1,
            "verbose": 0,
        },
        dev_mode=True,
    )
    return cfg


def make_tester(run_dir: Path, split_dir: Path, data_dir: Path, device: str, epoch: int):
    cfg = patch_config(Config(run_dir / "config.yml"), run_dir, split_dir, data_dir, device)
    checkpoint = run_dir / f"model_epoch{epoch:03d}.pt"
    if not checkpoint.exists():
        raise FileNotFoundError(f"Missing checkpoint: {checkpoint}")
    tester = get_tester(cfg=cfg, run_dir=run_dir, period="test", init_model=True)
    tester._load_weights(epoch=epoch)
    tester.model.eval()
    return tester


def move_batch_to_device(batch: dict[str, Any], device: torch.device) -> dict[str, Any]:
    for key in list(batch.keys()):
        if key.startswith("x_d"):
            batch[key] = {name: value.to(device) for name, value in batch[key].items()}
        elif not key.startswith("date"):
            batch[key] = batch[key].to(device)
    return batch


def scalar_from_xarray_dataset(dataset: Any, feature: str) -> float:
    value = dataset[feature]
    values = value.to_array().values if hasattr(value, "to_array") else value.values
    return float(np.ravel(values)[0])


def scale_and_center(tester, feature: str) -> tuple[float, float]:
    scale = scalar_from_xarray_dataset(tester.scaler["xarray_feature_scale"], feature)
    center = scalar_from_xarray_dataset(tester.scaler["xarray_feature_center"], feature)
    return scale, center


def rescale(values: np.ndarray, tester, feature: str) -> np.ndarray:
    scale, center = scale_and_center(tester, feature)
    return values * scale + center


def get_single_batch(tester, basin: str, sample_index: int, sequence_end: str | None):
    dataset = tester._get_dataset(basin)
    if sequence_end is not None:
        wanted = pd.Timestamp(sequence_end)
        sample_index = None
        for idx, (_, indices) in dataset.lookup_table.items():
            end_date = pd.Timestamp(dataset._dates[basin][dataset.frequencies[0]][indices[0]])
            if end_date == wanted:
                sample_index = idx
                break
        if sample_index is None:
            raise ValueError(f"No sample ending at {wanted.isoformat()} for basin {basin}")
    if sample_index < 0 or sample_index >= len(dataset):
        raise IndexError(f"Sample index {sample_index} is outside dataset length {len(dataset)}")
    sample = dataset[sample_index]
    loader = DataLoader([sample], batch_size=1, num_workers=0, collate_fn=dataset.collate_fn)
    batch = next(iter(loader))
    return dataset, sample_index, batch


def static_attribute_order(tester) -> list[str]:
    means = tester.scaler["attribute_means"]
    if hasattr(means, "index"):
        return list(means.index)
    return sorted(tester.cfg.static_attributes)


def load_raw_timeseries(data_dir: Path, basin: str, dates: pd.DatetimeIndex) -> pd.DataFrame:
    path = data_dir / "time_series" / f"{basin}.nc"
    if not path.exists():
        path = data_dir / "time_series" / f"{basin}.nc4"
    if not path.exists():
        raise FileNotFoundError(f"Missing basin time-series file for {basin}")
    with xr.open_dataset(path) as ds:
        frame = ds.sel(date=dates).to_dataframe()
    frame.index = pd.to_datetime(frame.index)
    return frame


def load_raw_static(data_dir: Path, basin: str, attr_order: list[str]) -> pd.Series:
    attrs = pd.read_csv(data_dir / "attributes" / "static_attributes.csv", dtype={"gauge_id": str})
    attrs["gauge_id"] = attrs["gauge_id"].map(normalize_basin)
    row = attrs.loc[attrs["gauge_id"] == basin]
    if row.empty:
        raise ValueError(f"No static attributes found for basin {basin}")
    return row.iloc[0][attr_order]


def export_input_csv(
    *,
    output_path: Path,
    tester,
    basin: str,
    seed: int,
    epoch: int,
    sample_index: int,
    batch: dict[str, Any],
    data_dir: Path,
) -> tuple[pd.DataFrame, list[str]]:
    dates = pd.to_datetime(batch["date"][0])
    cfg = tester.cfg
    seq_length = int(cfg.seq_length)
    predict_last_n = int(cfg.predict_last_n)
    target = cfg.target_variables[0]
    raw_ts = load_raw_timeseries(data_dir, basin, pd.DatetimeIndex(dates))
    attr_order = static_attribute_order(tester)
    raw_static = load_raw_static(data_dir, basin, attr_order)

    rows: list[dict[str, Any]] = []
    target_norm = batch["y"][0, :, 0].detach().cpu().numpy()
    target_raw_label = rescale(target_norm, tester, target)
    x_s = batch["x_s"][0].detach().cpu().numpy() if "x_s" in batch else np.array([])

    for pos, date in enumerate(dates):
        role = "prediction_window" if pos >= seq_length - predict_last_n else "context"
        row: dict[str, Any] = {
            "basin": basin,
            "seed": seed,
            "epoch": epoch,
            "sample_index": sample_index,
            "sequence_position": pos + 1,
            "relative_hour_from_sequence_end": pos - (seq_length - 1),
            "datetime": pd.Timestamp(date).isoformat(),
            "role": role,
            "is_prediction_window": role == "prediction_window",
            f"{target}_raw_from_netcdf": float(raw_ts.loc[date, target]),
            f"{target}_label_raw_after_period_mask": (
                float(target_raw_label[pos]) if not np.isnan(target_raw_label[pos]) else np.nan
            ),
            f"{target}_label_normalized": float(target_norm[pos]) if not np.isnan(target_norm[pos]) else np.nan,
        }
        for feature in cfg.dynamic_inputs:
            row[f"{feature}_raw"] = float(raw_ts.loc[date, feature])
            row[f"{feature}_normalized"] = float(batch["x_d"][feature][0, pos, 0].detach().cpu())
        for idx, attr in enumerate(attr_order):
            row[f"static_{attr}_raw"] = float(raw_static[attr])
            if idx < len(x_s):
                row[f"static_{attr}_normalized"] = float(x_s[idx])
        rows.append(row)

    frame = pd.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False)
    return frame, attr_order


def model_outputs(tester, batch: dict[str, Any], model_name: str) -> dict[str, np.ndarray]:
    device_batch = move_batch_to_device(batch, tester.device)
    with torch.no_grad():
        device_batch = tester.model.pre_model_hook(device_batch, is_train=False)
        predictions = tester.model(device_batch)

    target = tester.cfg.target_variables[0]
    output: dict[str, np.ndarray] = {}
    y_hat = predictions["y_hat"][0, -int(tester.cfg.predict_last_n) :, 0].detach().cpu().numpy()
    y_hat = rescale(y_hat, tester, target)
    if target in tester.cfg.clip_targets_to_zero:
        y_hat = np.where(y_hat < 0, 0, y_hat)
    output[f"{model_name}_y_hat"] = y_hat

    if model_name == "model2":
        quantiles = tester.cfg.quantiles
        y_quantiles = predictions["y_quantiles"][0, -int(tester.cfg.predict_last_n) :, :]
        y_quantiles = y_quantiles.reshape(y_quantiles.shape[0], len(tester.cfg.target_variables), len(quantiles))
        y_quantiles = y_quantiles[:, 0, :].detach().cpu().numpy()
        y_quantiles = rescale(y_quantiles, tester, target)
        if target in tester.cfg.clip_targets_to_zero:
            y_quantiles = np.where(y_quantiles < 0, 0, y_quantiles)
        for idx, quantile in enumerate(quantiles):
            output[f"q{int(quantile * 100):02d}"] = y_quantiles[:, idx]
    return output


def export_output_csv(
    *,
    output_path: Path,
    tester1,
    tester2,
    basin: str,
    seed: int,
    epoch: int,
    sample_index: int,
    batch1: dict[str, Any],
    batch2: dict[str, Any],
) -> pd.DataFrame:
    predict_last_n = int(tester1.cfg.predict_last_n)
    dates = pd.to_datetime(batch1["date"][0])[-predict_last_n:]
    target = tester1.cfg.target_variables[0]
    obs_norm = batch1["y"][0, -predict_last_n:, 0].detach().cpu().numpy()
    obs_raw = rescale(obs_norm, tester1, target)

    out1 = model_outputs(tester1, batch1, "model1")
    out2 = model_outputs(tester2, batch2, "model2")

    frame = pd.DataFrame(
        {
            "basin": basin,
            "seed": seed,
            "model1_epoch": epoch,
            "model2_epoch": epoch,
            "sample_index": sample_index,
            "output_position": np.arange(1, predict_last_n + 1),
            "relative_hour_from_sequence_end": np.arange(-predict_last_n + 1, 1),
            "datetime": [pd.Timestamp(value).isoformat() for value in dates],
            "obs": obs_raw,
            "model1": out1["model1_y_hat"],
            "model2_q50_result": out2["model2_y_hat"],
            "q50": out2["q50"],
            "q90": out2["q90"],
            "q95": out2["q95"],
            "q99": out2["q99"],
        }
    )
    frame["q90_minus_q50"] = frame["q90"] - frame["q50"]
    frame["q95_minus_q90"] = frame["q95"] - frame["q90"]
    frame["q99_minus_q95"] = frame["q99"] - frame["q95"]
    frame["q99_minus_q50"] = frame["q99"] - frame["q50"]
    frame["model2_q50_minus_model1"] = frame["q50"] - frame["model1"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False)
    return frame


def saved_result_diff(run_dir: Path, epoch: int, basin: str, sequence_end: pd.Timestamp, values: np.ndarray) -> float | None:
    path = run_dir / "test" / f"model_epoch{epoch:03d}" / "test_results.p"
    if not path.exists():
        return None
    with path.open("rb") as fp:
        results = pickle.load(fp)
    ds = results[basin]["1h"]["xr"]
    if np.datetime64(sequence_end.to_datetime64()) not in ds["date"].values:
        return None
    saved = ds.sel(date=sequence_end)["Streamflow_sim"].values.astype(float)
    return float(np.nanmax(np.abs(saved - values)))


def plot_gantt(
    *,
    output_path: Path,
    basin: str,
    seed: int,
    epoch: int,
    sequence_start: pd.Timestamp,
    prediction_start: pd.Timestamp,
    sequence_end_exclusive: pd.Timestamp,
    dpi: int,
) -> None:
    rows = [
        ("Dynamic inputs + static attrs", sequence_start, sequence_end_exclusive, "#4b5563"),
        ("Context consumed by LSTM", sequence_start, prediction_start, "#2563eb"),
        ("Target / evaluation window", prediction_start, sequence_end_exclusive, "#f97316"),
        ("Model 1 regression output", prediction_start, sequence_end_exclusive, "#16a34a"),
        ("Model 2 q50/q90/q95/q99 output", prediction_start, sequence_end_exclusive, "#dc2626"),
    ]

    fig, ax = plt.subplots(figsize=(12.5, 3.8))
    y_positions = np.arange(len(rows))[::-1]
    for y, (label, start, end, color) in zip(y_positions, rows, strict=True):
        left = mdates.date2num(start)
        width = mdates.date2num(end) - left
        ax.broken_barh([(left, width)], (y - 0.34, 0.68), facecolors=color, alpha=0.88)
        ax.text(left + width / 2, y, label, va="center", ha="center", color="white", fontsize=9)

    ax.axvline(mdates.date2num(prediction_start), color="#111827", linestyle="--", linewidth=1.0)
    ax.text(
        mdates.date2num(prediction_start),
        len(rows) - 0.25,
        "output starts",
        rotation=90,
        va="top",
        ha="right",
        fontsize=8,
        color="#111827",
    )
    ax.set_yticks(y_positions)
    ax.set_yticklabels([row[0] for row in rows], fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=8))
    ax.set_title(f"Single 336-hour sequence | basin {basin} | seed {seed} | epoch {epoch:03d}")
    ax.set_xlim(mdates.date2num(sequence_start), mdates.date2num(sequence_end_exclusive))
    ax.grid(axis="x", color="#d1d5db", linewidth=0.8)
    ax.set_axisbelow(True)
    fig.autofmt_xdate()
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)


def write_mermaid_gantt(
    *,
    output_path: Path,
    basin: str,
    seed: int,
    epoch: int,
    sequence_start: pd.Timestamp,
    prediction_start: pd.Timestamp,
    sequence_end_exclusive: pd.Timestamp,
) -> None:
    def fmt(ts: pd.Timestamp) -> str:
        return ts.strftime("%Y-%m-%d %H:%M")

    text = f"""```mermaid
gantt
    title Single 336-hour sequence | basin {basin} | seed {seed} | epoch {epoch:03d}
    dateFormat  YYYY-MM-DD HH:mm
    axisFormat  %m-%d %H:%M
    section Input
    Dynamic inputs + static attrs       :input, {fmt(sequence_start)}, {fmt(sequence_end_exclusive)}
    Context consumed by LSTM            :context, {fmt(sequence_start)}, {fmt(prediction_start)}
    Target / evaluation window          :target, {fmt(prediction_start)}, {fmt(sequence_end_exclusive)}
    section Output
    Model 1 regression output           :m1, {fmt(prediction_start)}, {fmt(sequence_end_exclusive)}
    Model 2 q50/q90/q95/q99 output      :m2, {fmt(prediction_start)}, {fmt(sequence_end_exclusive)}
```
"""
    output_path.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path.cwd()
    run_root = root / args.run_root
    split_dir = root / args.split_dir
    data_dir = root / args.data_dir
    output_dir = root / args.output_dir
    basin = normalize_basin(args.basin) if args.basin else first_test_basin(split_dir)

    runs = run_dirs(run_root, args.seed)
    tester1 = make_tester(runs["model1"], split_dir, data_dir, args.device, args.epoch)
    tester2 = make_tester(runs["model2"], split_dir, data_dir, args.device, args.epoch)

    _, sample_index, batch1 = get_single_batch(tester1, basin, args.sample_index, args.sequence_end)
    _, _, batch2 = get_single_batch(tester2, basin, sample_index, args.sequence_end)

    dates1 = pd.to_datetime(batch1["date"][0])
    dates2 = pd.to_datetime(batch2["date"][0])
    if not np.array_equal(dates1.values, dates2.values):
        raise RuntimeError("Model 1 and Model 2 batches do not share the same datetime sequence.")

    sequence_start = pd.Timestamp(dates1[0])
    sequence_end = pd.Timestamp(dates1[-1])
    sequence_end_exclusive = sequence_end + pd.Timedelta(hours=1)
    predict_last_n = int(tester1.cfg.predict_last_n)
    prediction_start = pd.Timestamp(dates1[-predict_last_n])

    stem = f"basin_{basin}_seed{args.seed}_epoch{args.epoch:03d}_sample{sample_index:05d}"
    input_csv = output_dir / f"{stem}_input_window.csv"
    output_csv = output_dir / f"{stem}_output_window.csv"
    gantt_png = output_dir / f"{stem}_gantt.png"
    gantt_md = output_dir / f"{stem}_gantt.md"
    metadata_json = output_dir / f"{stem}_metadata.json"

    input_df, attr_order = export_input_csv(
        output_path=input_csv,
        tester=tester1,
        basin=basin,
        seed=args.seed,
        epoch=args.epoch,
        sample_index=sample_index,
        batch=batch1,
        data_dir=data_dir,
    )
    output_df = export_output_csv(
        output_path=output_csv,
        tester1=tester1,
        tester2=tester2,
        basin=basin,
        seed=args.seed,
        epoch=args.epoch,
        sample_index=sample_index,
        batch1=batch1,
        batch2=batch2,
    )
    plot_gantt(
        output_path=gantt_png,
        basin=basin,
        seed=args.seed,
        epoch=args.epoch,
        sequence_start=sequence_start,
        prediction_start=prediction_start,
        sequence_end_exclusive=sequence_end_exclusive,
        dpi=args.dpi,
    )
    write_mermaid_gantt(
        output_path=gantt_md,
        basin=basin,
        seed=args.seed,
        epoch=args.epoch,
        sequence_start=sequence_start,
        prediction_start=prediction_start,
        sequence_end_exclusive=sequence_end_exclusive,
    )

    model1_diff = saved_result_diff(
        runs["model1"], args.epoch, basin, sequence_end, output_df["model1"].to_numpy(dtype=float)
    )
    model2_diff = saved_result_diff(
        runs["model2"], args.epoch, basin, sequence_end, output_df["model2_q50_result"].to_numpy(dtype=float)
    )

    metadata = {
        "basin": basin,
        "seed": args.seed,
        "epoch": args.epoch,
        "sample_index": sample_index,
        "model1_run": str(runs["model1"]),
        "model2_run": str(runs["model2"]),
        "seq_length": int(tester1.cfg.seq_length),
        "predict_last_n": predict_last_n,
        "context_hours": int(tester1.cfg.seq_length) - predict_last_n,
        "sequence_start": sequence_start.isoformat(),
        "sequence_end": sequence_end.isoformat(),
        "prediction_start": prediction_start.isoformat(),
        "prediction_end": sequence_end.isoformat(),
        "dynamic_inputs": list(tester1.cfg.dynamic_inputs),
        "target_variable": tester1.cfg.target_variables[0],
        "static_attribute_order": attr_order,
        "note": "Streamflow is the target/label, not a dynamic model input in this run.",
        "input_csv": str(input_csv),
        "output_csv": str(output_csv),
        "gantt_png": str(gantt_png),
        "gantt_mermaid_md": str(gantt_md),
        "input_rows": int(len(input_df)),
        "output_rows": int(len(output_df)),
        "sanity_max_abs_diff_vs_saved_test_results": {
            "model1": model1_diff,
            "model2_q50": model2_diff,
        },
    }
    metadata_json.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Wrote input CSV: {input_csv}")
    print(f"Wrote output CSV: {output_csv}")
    print(f"Wrote Gantt PNG: {gantt_png}")
    print(f"Wrote Mermaid Gantt: {gantt_md}")
    print(f"Wrote metadata: {metadata_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
