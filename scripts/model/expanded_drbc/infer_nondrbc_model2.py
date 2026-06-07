#!/usr/bin/env python3
"""Model 2 quantile LSTM inference on non-DRBC train/val basins (2014-2016).

GPU 서버 전용 스크립트. drbc_holdout_broad 데이터로 train/val 유역 추론.

출력:
  ~/CAMELS/output/nondrbc_series/seed{S}/series.csv
  컬럼: basin, datetime, obs, q50, q90, q95, q99
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

# vendored NH 우선 사용 (pip v1.13.0은 quantile head 미지원).
# GPU 서버: ~/CAMELS/vendor/neuralhydrology/
# 로컬:     <repo_root>/vendor/neuralhydrology/
_VENDOR_CANDIDATES = [
    Path(__file__).resolve().parents[3] / "vendor" / "neuralhydrology",
    Path.home() / "CAMELS" / "vendor" / "neuralhydrology",
]
for _v in _VENDOR_CANDIDATES:
    if _v.is_dir():
        sys.path.insert(0, str(_v))
        break

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

# GPU 서버 기준 경로
CAMELS_ROOT = Path.home() / "CAMELS"
DEFAULT_RUN_ROOT = CAMELS_ROOT / "runs/subset_comparison"
DEFAULT_DATA_DIR = CAMELS_ROOT / "data/CAMELSH_generic/drbc_holdout_broad"
DEFAULT_SPLIT_DIR = CAMELS_ROOT / "configs/pilot/basin_splits/scaling_300"
DEFAULT_OUTPUT_DIR = CAMELS_ROOT / "output/nondrbc_series"

MODEL2_EPOCHS: dict[int, int] = {111: 5, 222: 5, 444: 5}
RUN_PATTERN = "camelsh_hourly_model2_drbc_holdout_subset300_seed{seed}_"

FIELDNAMES = ["basin", "datetime", "obs", "q50", "q90", "q95", "q99"]


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
    return [normalize_gauge_id(line) for line in path.read_text().splitlines() if line.strip()]


def find_run_dir(run_root: Path, seed: int) -> Path | None:
    prefix = RUN_PATTERN.format(seed=seed)
    for p in sorted(run_root.iterdir()):
        if p.is_dir() and p.name.startswith(prefix):
            return p
    return None


def patch_config(cfg: Config, run_dir: Path, data_dir: Path, basin_file: Path,
                  split_dir: Path, device: str) -> Config:
    cfg.update_config({
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
    }, dev_mode=True)
    return cfg


def move_batch_to_device(data: dict, device: torch.device) -> dict:
    for key in list(data.keys()):
        if key.startswith("x_d"):
            data[key] = {freq: v.to(device) for freq, v in data[key].items()}
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


def infer_seed(seed: int, basins: list[str], basin_file: Path,
               run_root: Path, data_dir: Path, split_dir: Path,
               output_dir: Path, device: str, force: bool) -> Path:
    out_csv = output_dir / f"seed{seed}" / "series.csv"
    if out_csv.exists() and not force:
        print(f"  seed{seed}: already exists, skip")
        return out_csv

    run_dir = find_run_dir(run_root, seed)
    if run_dir is None:
        raise FileNotFoundError(f"No run dir for seed {seed} in {run_root}")
    epoch = MODEL2_EPOCHS[seed]

    cfg = patch_config(
        Config(run_dir / "config.yml"),
        run_dir=run_dir, data_dir=data_dir,
        basin_file=basin_file, split_dir=split_dir, device=device,
    )
    tester = get_tester(cfg=cfg, run_dir=run_dir, period="test", init_model=True)
    tester._load_weights(epoch=epoch)
    tester.model.eval()

    target = cfg.target_variables[0]
    scale, center = target_scale_and_center(tester, target)
    quantiles = cfg.quantiles  # [0.5, 0.9, 0.95, 0.99]
    q_names = [f"q{int(q*100):02d}" for q in quantiles]  # q50 q90 q95 q99

    run_basins = [b for b in tester.basins if b in set(basins)]
    print(f"seed{seed}: {len(run_basins)} basins, epoch {epoch}, device {device}")

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    tmp_csv = out_csv.with_suffix(".csv.tmp")

    with tmp_csv.open("w", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=FIELDNAMES)
        writer.writeheader()

        for i, basin in enumerate(run_basins, 1):
            print(f"  [{i}/{len(run_basins)}] {basin}", flush=True)
            try:
                dataset = tester._get_dataset(basin)
            except (NoEvaluationDataError, FileNotFoundError) as exc:
                print(f"    skip {basin}: {exc}")
                continue
            if dataset is None or len(dataset) == 0:
                continue

            loader = DataLoader(dataset, batch_size=cfg.batch_size,
                                num_workers=0, collate_fn=dataset.collate_fn)
            rows: list[dict] = []
            with torch.no_grad():
                for batch in loader:
                    batch = move_batch_to_device(batch, tester.device)
                    batch = tester.model.pre_model_hook(batch, is_train=False)
                    preds = tester.model(batch)
                    dates = render_dates(batch)
                    obs_arr = batch["y"][:, -1, 0].detach().cpu().numpy() * scale + center

                    y_q = preds["y_quantiles"][:, -1, :]
                    y_q = y_q.reshape(y_q.shape[0], len(cfg.target_variables), len(quantiles))
                    y_q = y_q[:, 0, :].detach().cpu().numpy() * scale + center
                    if target in getattr(cfg, "clip_targets_to_zero", []):
                        y_q = np.where(y_q < 0, 0, y_q)

                    for date, obs_v, quants in zip(dates, obs_arr, y_q):
                        row: dict = {
                            "basin": basin,
                            "datetime": pd.Timestamp(date).isoformat(),
                            "obs": float(obs_v),
                        }
                        for name, val in zip(q_names, quants):
                            row[name] = float(val)
                        rows.append(row)
            writer.writerows(rows)

    tmp_csv.replace(out_csv)
    print(f"  → {out_csv}  ({out_csv.stat().st_size // 1024}KB)")
    return out_csv


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds", type=int, nargs="+", default=[111, 222, 444])
    p.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p.add_argument("--split-dir", type=Path, default=DEFAULT_SPLIT_DIR)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--basins", choices=["train", "val", "all"], default="train")
    p.add_argument("--device", default="auto")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    device = resolve_device(args.device)

    if args.basins == "train":
        basins = read_basins(args.split_dir / "train.txt")
    elif args.basins == "val":
        basins = read_basins(args.split_dir / "validation.txt")
    else:
        basins = (read_basins(args.split_dir / "train.txt")
                  + read_basins(args.split_dir / "validation.txt"))

    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("\n".join(basins) + "\n")
        basin_file = Path(f.name)

    print(f"Running inference: {len(basins)} basins, seeds {args.seeds}, device {device}")
    for seed in args.seeds:
        infer_seed(
            seed=seed, basins=basins, basin_file=basin_file,
            run_root=args.run_root, data_dir=args.data_dir,
            split_dir=args.split_dir, output_dir=args.output_dir,
            device=device, force=args.force,
        )

    basin_file.unlink(missing_ok=True)
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
