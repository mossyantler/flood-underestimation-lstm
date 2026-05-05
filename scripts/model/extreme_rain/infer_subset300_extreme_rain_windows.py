#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "torch==2.4.1",
#   "neuralhydrology>=1.13",
# ]
# ///

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
from neuralhydrology.utils.config import Config
from neuralhydrology.utils.errors import NoEvaluationDataError


DEFAULT_BLOCKS_CSV = Path("output/model_analysis/extreme_rain/primary/exposure/inference_blocks.csv")
DEFAULT_RUN_ROOT = Path("runs/subset_comparison")
DEFAULT_OUTPUT_DIR = Path("output/model_analysis/extreme_rain/primary/inference")
DEFAULT_VALIDATION_EPOCHS = [5, 10, 15, 20, 25, 30]

RUN_RE = re.compile(r"camelsh_hourly_(model[12])_drbc_holdout_subset300_seed(\d+)_")
PRIMARY_EPOCHS = {
    ("model1", 111): 25,
    ("model1", 222): 10,
    ("model1", 444): 15,
    ("model2", 111): 5,
    ("model2", 222): 10,
    ("model2", 444): 10,
}
QUANTILE_COLUMNS = ["q50", "q90", "q95", "q99"]
REQUIRED_SERIES_COLUMNS = [
    "seed",
    "basin",
    "model1_epoch",
    "model2_epoch",
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
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run subset300 Model 1/2 checkpoints over DRBC historical extreme-rain inference blocks."
    )
    parser.add_argument("--blocks-csv", type=Path, default=DEFAULT_BLOCKS_CSV)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seeds", type=int, nargs="+", default=[111, 222, 444])
    parser.add_argument(
        "--epoch-mode",
        choices=["primary", "validation"],
        default="primary",
        help="Use the primary validation-selected epoch mapping or every validation checkpoint epoch.",
    )
    parser.add_argument(
        "--validation-epochs",
        type=int,
        nargs="+",
        default=DEFAULT_VALIDATION_EPOCHS,
        help="Epoch grid used with --epoch-mode validation.",
    )
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=None, help="Optional eval batch-size override.")
    parser.add_argument("--limit-events", type=int, default=None, help="Limit blocks for smoke tests.")
    parser.add_argument("--limit-basins", type=int, default=None, help="Limit basins for smoke tests.")
    parser.add_argument("--force", action="store_true", help="Regenerate existing seed exports.")
    return parser.parse_args()


def epoch_pairs_for_seed(seed: int, mode: str, validation_epochs: list[int]) -> list[tuple[int, int, str]]:
    if mode == "primary":
        model1_epoch = PRIMARY_EPOCHS[("model1", seed)]
        model2_epoch = PRIMARY_EPOCHS[("model2", seed)]
        return [(model1_epoch, model2_epoch, "primary")]
    return [(int(epoch), int(epoch), f"epoch{int(epoch):03d}") for epoch in validation_epochs]


def normalize_gauge_id(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(8)


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


def patch_config(
    *,
    cfg: Config,
    root: Path,
    run_dir: Path,
    device: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    batch_size: int | None,
) -> Config:
    split_dir = root / "configs" / "pilot" / "basin_splits" / "scaling_300"
    update = {
        "run_dir": str(run_dir),
        "train_dir": str(run_dir / "train_data"),
        "img_log_dir": str(run_dir / "img_log"),
        "data_dir": str(root / "data" / "CAMELSH_generic" / "drbc_holdout_broad"),
        "train_basin_file": str(split_dir / "train.txt"),
        "validation_basin_file": str(split_dir / "validation.txt"),
        "test_basin_file": str(split_dir / "test.txt"),
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


def export_predictions_for_model(
    *,
    root: Path,
    run_dir: Path,
    model: str,
    epoch: int,
    blocks: pd.DataFrame,
    output_csv: Path,
    device: str,
    batch_size: int | None,
) -> Path:
    if output_csv.exists():
        output_csv.unlink()
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    global_start = pd.to_datetime(blocks["block_start"]).min().floor("D")
    global_end = pd.to_datetime(blocks["block_end"]).max().ceil("D") - pd.Timedelta(hours=1)
    cfg = patch_config(
        cfg=Config(run_dir / "config.yml"),
        root=root,
        run_dir=run_dir,
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
    fieldnames = ["basin", "block_id", "datetime", "obs"]
    if model == "model1":
        fieldnames.append("model1")
    else:
        fieldnames.extend(["model2_q50_result", *quantile_names])

    tmp_csv = output_csv.with_suffix(output_csv.suffix + ".tmp")
    tmp_csv.unlink(missing_ok=True)
    basin_blocks = {
        basin: group.sort_values("block_start").copy()
        for basin, group in blocks.groupby("gauge_id", sort=True)
    }
    run_basins = [basin for basin in tester.basins if basin in basin_blocks]
    print(
        f"Exporting {model} seed run {run_dir.name} epoch {epoch:03d}: "
        f"{len(run_basins)} basins, {len(blocks)} blocks",
        flush=True,
    )

    with tmp_csv.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()

        for basin_idx, basin in enumerate(run_basins, start=1):
            print(f"  {model} basin {basin_idx}/{len(run_basins)}: {basin}", flush=True)
            for _, block in basin_blocks[basin].iterrows():
                start = pd.Timestamp(block["block_start"])
                end = pd.Timestamp(block["block_end"])
                cfg.update_config(
                    {
                        "test_start_date": start.floor("D").strftime("%d/%m/%Y"),
                        "test_end_date": (end.ceil("D") - pd.Timedelta(hours=1)).strftime("%d/%m/%Y"),
                    },
                    dev_mode=True,
                )
                try:
                    dataset = tester._get_dataset(basin)
                except NoEvaluationDataError:
                    continue

                loader = DataLoader(dataset, batch_size=cfg.batch_size, num_workers=0, collate_fn=dataset.collate_fn)
                block_rows: list[dict[str, Any]] = []
                with torch.no_grad():
                    for batch in loader:
                        batch = move_batch_to_device(batch, tester.device)
                        batch = tester.model.pre_model_hook(batch, is_train=False)
                        predictions = tester.model(batch)
                        obs = batch["y"][:, -1, 0].detach().cpu().numpy() * scale + center
                        dates = render_dates(batch)
                        if model == "model1":
                            y_hat = predictions["y_hat"][:, -1, 0].detach().cpu().numpy() * scale + center
                            if target in cfg.clip_targets_to_zero:
                                y_hat = np.where(y_hat < 0, 0, y_hat)
                            for date, obs_value, pred_value in zip(dates, obs, y_hat, strict=True):
                                block_rows.append(
                                    {
                                        "basin": basin,
                                        "datetime": pd.Timestamp(date),
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
                            if target in cfg.clip_targets_to_zero:
                                y_hat = np.where(y_hat < 0, 0, y_hat)
                                y_quantiles = np.where(y_quantiles < 0, 0, y_quantiles)
                            for date, obs_value, median_value, values in zip(dates, obs, y_hat, y_quantiles, strict=True):
                                row = {
                                    "basin": basin,
                                    "datetime": pd.Timestamp(date),
                                    "obs": float(obs_value),
                                    "model2_q50_result": float(median_value),
                                }
                                for name, value in zip(quantile_names, values, strict=True):
                                    row[name] = float(value)
                                block_rows.append(row)

                if not block_rows:
                    continue
                frame = pd.DataFrame(block_rows).drop_duplicates("datetime").sort_values("datetime")
                clipped = frame[(frame["datetime"] >= start) & (frame["datetime"] <= end)].copy()
                if clipped.empty:
                    continue
                clipped.insert(1, "block_id", block["block_id"])
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
    df = left.merge(
        right[["basin", "block_id", "datetime", "model2_q50_result", *QUANTILE_COLUMNS]],
        on=["basin", "block_id", "datetime"],
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
    df.insert(0, "model2_epoch", model2_epoch)
    df.insert(0, "model1_epoch", model1_epoch)
    df.insert(0, "seed", seed)
    df = df[["block_id", *REQUIRED_SERIES_COLUMNS]].sort_values(["basin", "datetime", "block_id"])
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    tmp_csv = output_csv.with_suffix(output_csv.suffix + ".tmp")
    df.to_csv(tmp_csv, index=False)
    tmp_csv.replace(output_csv)
    return output_csv


def load_blocks(path: Path, limit_events: int | None, limit_basins: int | None) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing inference block CSV: {path}")
    blocks = pd.read_csv(path, dtype={"gauge_id": str}, parse_dates=["block_start", "block_end"])
    blocks["gauge_id"] = blocks["gauge_id"].map(normalize_gauge_id)
    if limit_basins is not None:
        selected = sorted(blocks["gauge_id"].unique())[:limit_basins]
        blocks = blocks[blocks["gauge_id"].isin(selected)]
    if limit_events is not None:
        blocks = blocks.head(limit_events)
    if blocks.empty:
        raise ValueError("No inference blocks selected.")
    return blocks.sort_values(["gauge_id", "block_start"]).reset_index(drop=True)


def main() -> int:
    args = parse_args()
    root = Path.cwd()
    blocks = load_blocks(args.blocks_csv, args.limit_events, args.limit_basins)
    output_dir: Path = args.output_dir
    raw_dir = output_dir / "raw_model_exports"
    series_dir = output_dir / "required_series"
    output_dir.mkdir(parents=True, exist_ok=True)
    runs = run_dirs(args.run_root)

    manifest_rows = []
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
                    root=root,
                    run_dir=model1_run,
                    model="model1",
                    epoch=model1_epoch,
                    blocks=blocks,
                    output_csv=model1_csv,
                    device=args.device,
                    batch_size=args.batch_size,
                )
            if args.force or not model2_csv.exists():
                export_predictions_for_model(
                    root=root,
                    run_dir=model2_run,
                    model="model2",
                    epoch=model2_epoch,
                    blocks=blocks,
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
    manifest_path = output_dir / "inference_manifest.csv"
    manifest.to_csv(manifest_path, index=False)
    block_copy_path = output_dir / "inference_blocks_used.csv"
    blocks.to_csv(block_copy_path, index=False)
    summary = {
        "blocks_csv": str(args.blocks_csv),
        "output_dir": str(output_dir),
        "device": args.device,
        "seeds": args.seeds,
        "epoch_mode": args.epoch_mode,
        "validation_epochs": args.validation_epochs,
        "n_blocks": int(len(blocks)),
        "n_basins": int(blocks["gauge_id"].nunique()),
        "manifest": str(manifest_path),
        "inference_blocks_used": str(block_copy_path),
    }
    (output_dir / "analysis_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote inference manifest: {manifest_path}")
    print(f"Wrote required series directory: {series_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
