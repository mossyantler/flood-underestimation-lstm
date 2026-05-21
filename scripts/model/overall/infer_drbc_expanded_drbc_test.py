#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "torch==2.4.1",
#   "neuralhydrology>=1.13",
# ]
# ///
"""Model 1/2 timeseries inference on expanded observed DRBC test split (2014-2016).

tester.evaluate() 없이 수동 배치 루프로 시계열을 직접 추출한다.

주요 출력:
  output/model_analysis/expanded_drbc_test/raw_timeseries/model1_seed{S}_epoch{E}.csv
  output/model_analysis/expanded_drbc_test/raw_timeseries/model2_seed{S}_epoch{E}.csv
  output/model_analysis/expanded_drbc_test/required_series/seed{S}/primary_required_series.csv
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


TEST_START = pd.Timestamp("2014-01-01")
TEST_END = pd.Timestamp("2016-12-31")

DEFAULT_RUN_ROOT = ROOT / "runs/subset_comparison"
DEFAULT_DATA_DIR = ROOT / "data/CAMELSH_generic/drbc_expanded_observed_test"
DEFAULT_BASIN_FILE = ROOT / "data/CAMELSH_generic/drbc_expanded_observed_test/splits/test.txt"
DEFAULT_OUTPUT_DIR = ROOT / "output/model_analysis/expanded_drbc_test"

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
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p.add_argument("--basin-file", type=Path, default=DEFAULT_BASIN_FILE)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--seeds", type=int, nargs="+", default=[111, 222, 444])
    p.add_argument("--device", default="auto")
    p.add_argument("--batch-size", type=int, default=None)
    p.add_argument("--limit-basins", type=int, default=None)
    p.add_argument("--force", action="store_true")
    return p.parse_args()


def normalize_gauge_id(value: Any) -> str:
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(8)


def resolve_device(value: str) -> str:
    if value != "auto":
        return value
    if torch.cuda.is_available():
        return "cuda:0"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def read_basins(path: Path) -> list[str]:
    return [normalize_gauge_id(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_dirs(run_root: Path) -> dict[tuple[str, int], Path]:
    runs: dict[tuple[str, int], Path] = {}
    for path in sorted(run_root.iterdir()):
        if not path.is_dir():
            continue
        m = RUN_RE.match(path.name)
        if not m:
            continue
        key = (m.group(1), int(m.group(2)))
        if key not in runs or path.stat().st_mtime > runs[key].stat().st_mtime:
            runs[key] = path
    return runs


def patch_config(*, cfg: Config, run_dir: Path, data_dir: Path, basin_file: Path, device: str, batch_size: int | None) -> Config:
    split_dir = ROOT / "configs/pilot/basin_splits/scaling_300"
    update = {
        "run_dir": str(run_dir),
        "train_dir": str(run_dir / "train_data"),
        "img_log_dir": str(run_dir / "img_log"),
        "data_dir": str(data_dir),
        "train_basin_file": str(split_dir / "train.txt"),
        "validation_basin_file": str(split_dir / "validation.txt"),
        "test_basin_file": str(basin_file),
        "test_start_date": TEST_START.strftime("%d/%m/%Y"),
        "test_end_date": TEST_END.strftime("%d/%m/%Y"),
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


def target_scale_and_center(tester: Any, target: str) -> tuple[float, float]:
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


def export_timeseries(
    *,
    run_dir: Path,
    model: str,
    epoch: int,
    basins: list[str],
    data_dir: Path,
    basin_file: Path,
    output_csv: Path,
    device: str,
    batch_size: int | None,
    force: bool,
) -> Path:
    if output_csv.exists() and not force:
        print(f"  {output_csv.name} already exists, skipping.", flush=True)
        return output_csv

    output_csv.parent.mkdir(parents=True, exist_ok=True)

    cfg = patch_config(
        cfg=Config(run_dir / "config.yml"),
        run_dir=run_dir,
        data_dir=data_dir,
        basin_file=basin_file,
        device=device,
        batch_size=batch_size,
    )
    tester = get_tester(cfg=cfg, run_dir=run_dir, period="test", init_model=True)
    tester._load_weights(epoch=epoch)
    tester.model.eval()

    target = cfg.target_variables[0]
    scale, center = target_scale_and_center(tester, target)
    quantiles = getattr(cfg, "quantiles", None) if model == "model2" else None
    quantile_names = [f"q{int(q * 100):02d}" for q in quantiles] if quantiles else []

    if model == "model1":
        fieldnames = ["basin", "datetime", "obs", "model1"]
    else:
        fieldnames = ["basin", "datetime", "obs", "model2_q50_result", *quantile_names]

    run_basins = [b for b in tester.basins if b in set(basins)]
    print(
        f"Exporting {model} {run_dir.name} epoch {epoch:03d}: {len(run_basins)} basins",
        flush=True,
    )

    tmp_csv = output_csv.with_suffix(output_csv.suffix + ".tmp")
    tmp_csv.unlink(missing_ok=True)

    with tmp_csv.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()

        for basin_idx, basin in enumerate(run_basins, start=1):
            print(f"  {model} basin {basin_idx}/{len(run_basins)}: {basin}", flush=True)
            try:
                dataset = tester._get_dataset(basin)
            except (NoEvaluationDataError, FileNotFoundError) as exc:
                print(f"    skipping {basin}: {exc}", flush=True)
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
                        for date, obs_v, pred_v in zip(dates, obs, y_hat, strict=True):
                            rows.append({"basin": basin, "datetime": pd.Timestamp(date).isoformat(), "obs": float(obs_v), "model1": float(pred_v)})
                    else:
                        y_hat = predictions["y_hat"][:, -1, 0].detach().cpu().numpy() * scale + center
                        y_quantiles = predictions["y_quantiles"][:, -1, :]
                        y_quantiles = y_quantiles.reshape(y_quantiles.shape[0], len(cfg.target_variables), len(quantiles))
                        y_quantiles = y_quantiles[:, 0, :].detach().cpu().numpy() * scale + center
                        if target in getattr(cfg, "clip_targets_to_zero", []):
                            y_hat = np.where(y_hat < 0, 0, y_hat)
                            y_quantiles = np.where(y_quantiles < 0, 0, y_quantiles)
                        for date, obs_v, med_v, quants in zip(dates, obs, y_hat, y_quantiles, strict=True):
                            row: dict[str, Any] = {"basin": basin, "datetime": pd.Timestamp(date).isoformat(), "obs": float(obs_v), "model2_q50_result": float(med_v)}
                            for name, val in zip(quantile_names, quants, strict=True):
                                row[name] = float(val)
                            rows.append(row)

            writer.writerows(rows)

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
    left = pd.read_csv(model1_csv, dtype={"basin": str})
    right = pd.read_csv(model2_csv, dtype={"basin": str})
    left["basin"] = left["basin"].map(normalize_gauge_id)
    right["basin"] = right["basin"].map(normalize_gauge_id)

    df = left.merge(
        right[["basin", "datetime", "model2_q50_result", *QUANTILE_COLUMNS]],
        on=["basin", "datetime"],
        how="inner",
        validate="one_to_one",
    )
    df["q90_minus_q50"] = df["q90"] - df["q50"]
    df["q95_minus_q90"] = df["q95"] - df["q90"]
    df["q99_minus_q95"] = df["q99"] - df["q95"]
    df["q99_minus_q50"] = df["q99"] - df["q50"]
    df["model2_q50_minus_model1"] = df["q50"] - df["model1"]
    df.insert(0, "seed", seed)
    df.insert(2, "model1_epoch", model1_epoch)
    df.insert(3, "model2_epoch", model2_epoch)
    df = df[REQUIRED_SERIES_COLUMNS].sort_values(["basin", "datetime"])

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    tmp_csv = output_csv.with_suffix(output_csv.suffix + ".tmp")
    df.to_csv(tmp_csv, index=False)
    tmp_csv.replace(output_csv)
    return output_csv


def main() -> int:
    args = parse_args()
    device = resolve_device(args.device)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = args.output_dir / "raw_timeseries"
    series_dir = args.output_dir / "required_series"
    raw_dir.mkdir(parents=True, exist_ok=True)

    basins = read_basins(args.basin_file)
    if args.limit_basins is not None:
        basins = basins[: args.limit_basins]

    basin_file = args.basin_file
    import tempfile
    tmp_ctx = None
    if args.limit_basins is not None:
        tmp_ctx = tempfile.TemporaryDirectory(prefix="expanded_drbc_infer_")
        basin_file = Path(tmp_ctx.name) / "test.txt"
        basin_file.write_text("\n".join(basins) + "\n", encoding="utf-8")

    runs = run_dirs(args.run_root)
    series_paths: list[Path] = []

    try:
        for seed in args.seeds:
            m1_epoch = PRIMARY_EPOCHS.get(("model1", seed))
            m2_epoch = PRIMARY_EPOCHS.get(("model2", seed))
            m1_run = runs.get(("model1", seed))
            m2_run = runs.get(("model2", seed))
            if None in (m1_epoch, m2_epoch, m1_run, m2_run):
                print(f"Skipping seed {seed}: missing run or epoch config", flush=True)
                continue

            m1_csv = raw_dir / f"model1_seed{seed}_epoch{m1_epoch:03d}.csv"
            m2_csv = raw_dir / f"model2_seed{seed}_epoch{m2_epoch:03d}.csv"

            export_timeseries(
                run_dir=m1_run, model="model1", epoch=m1_epoch,
                basins=basins, data_dir=args.data_dir, basin_file=basin_file,
                output_csv=m1_csv, device=device, batch_size=args.batch_size, force=args.force,
            )
            export_timeseries(
                run_dir=m2_run, model="model2", epoch=m2_epoch,
                basins=basins, data_dir=args.data_dir, basin_file=basin_file,
                output_csv=m2_csv, device=device, batch_size=args.batch_size, force=args.force,
            )

            series_csv = series_dir / f"seed{seed}" / "primary_required_series.csv"
            merge_seed_series(
                seed=seed, model1_epoch=m1_epoch, model2_epoch=m2_epoch,
                model1_csv=m1_csv, model2_csv=m2_csv, output_csv=series_csv,
            )
            series_paths.append(series_csv)
            print(f"Wrote required_series seed{seed}: {series_csv}", flush=True)

        summary = {
            "experiment_name": "expanded_drbc_test_timeseries",
            "test_period": {"start": TEST_START.isoformat(), "end": TEST_END.isoformat()},
            "basin_count": len(basins),
            "seeds": args.seeds,
            "raw_timeseries_dir": str(raw_dir),
            "required_series_dir": str(series_dir),
            "required_series_files": [str(p) for p in series_paths],
        }
        (args.output_dir / "timeseries_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
    finally:
        if tmp_ctx is not None:
            tmp_ctx.cleanup()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
