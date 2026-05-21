#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "torch==2.4.1",
#   "neuralhydrology>=1.13",
# ]
# ///
"""Evaluate existing subset300 checkpoints on the expanded observed DRBC test split."""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
VENDOR_NH = ROOT / "vendor" / "neuralhydrology"
if str(VENDOR_NH) not in sys.path:
    sys.path.insert(0, str(VENDOR_NH))

import numpy as np
import pandas as pd
import torch

from neuralhydrology.evaluation import get_tester
from neuralhydrology.utils.config import Config


RUN_RE = re.compile(r"camelsh_hourly_(model[12])_drbc_holdout_subset300_seed(\d+)_")
PRIMARY_EPOCHS: dict[tuple[str, int], int] = {
    ("model1", 111): 25,
    ("model1", 222): 10,
    ("model1", 444): 15,
    ("model2", 111): 5,
    ("model2", 222): 10,
    ("model2", 444): 10,
}
METRICS = ["NSE", "KGE", "FHV", "Peak-Timing", "Peak-MAPE"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=ROOT / "runs/subset_comparison")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=ROOT / "data/CAMELSH_generic/drbc_expanded_observed_test",
    )
    parser.add_argument(
        "--basin-file",
        type=Path,
        default=ROOT / "data/CAMELSH_generic/drbc_expanded_observed_test/splits/test.txt",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "output/model_analysis/expanded/expanded_drbc_test",
    )
    parser.add_argument("--seeds", type=int, nargs="+", default=[111, 222, 444])
    parser.add_argument("--device", default="auto", help="auto, cpu, mps, or cuda")
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--limit-basins", type=int, default=None, help="Smoke-test only the first N basins.")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


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
    if not run_root.exists():
        raise FileNotFoundError(f"Missing run root: {run_root}")
    runs: dict[tuple[str, int], Path] = {}
    for path in sorted(run_root.iterdir()):
        if not path.is_dir():
            continue
        match = RUN_RE.match(path.name)
        if not match:
            continue
        key = (match.group(1), int(match.group(2)))
        if key not in runs or path.stat().st_mtime > runs[key].stat().st_mtime:
            runs[key] = path
    return runs


def patch_config(
    *,
    cfg: Config,
    run_dir: Path,
    data_dir: Path,
    basin_file: Path,
    device: str,
    batch_size: int | None,
) -> Config:
    split_dir = ROOT / "configs/pilot/basin_splits/scaling_300"
    update = {
        "run_dir": str(run_dir),
        "train_dir": str(run_dir / "train_data"),
        "img_log_dir": str(run_dir / "img_log"),
        "data_dir": str(data_dir),
        "train_basin_file": str(split_dir / "train.txt"),
        "validation_basin_file": str(split_dir / "validation.txt"),
        "test_basin_file": str(basin_file),
        "test_start_date": "01/01/2014",
        "test_end_date": "31/12/2016",
        "device": device,
        "num_workers": 0,
    }
    if batch_size is not None:
        update["batch_size"] = int(batch_size)
    cfg.update_config(update, dev_mode=True)
    return cfg


def metric_rows_from_results(results: dict, *, model: str, seed: int, epoch: int, run_dir: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for basin, freq_results in results.items():
        basin_id = normalize_gauge_id(basin)
        for frequency, values in freq_results.items():
            row: dict[str, Any] = {
                "model": model,
                "seed": seed,
                "split": "expanded_drbc_test",
                "epoch": epoch,
                "run_name": run_dir.name,
                "frequency": frequency,
                "basin": basin_id,
            }
            for key, value in values.items():
                if key == "xr":
                    continue
                row[key] = float(value) if value is not None else math.nan
            rows.append(row)
    return pd.DataFrame(rows)


def evaluate_one(
    *,
    run_dir: Path,
    model: str,
    seed: int,
    epoch: int,
    data_dir: Path,
    basin_file: Path,
    output_csv: Path,
    device: str,
    batch_size: int | None,
    force: bool,
) -> pd.DataFrame:
    if output_csv.exists() and not force:
        return pd.read_csv(output_csv, dtype={"basin": str})
    checkpoint = run_dir / f"model_epoch{epoch:03d}.pt"
    if not checkpoint.exists():
        raise FileNotFoundError(f"Missing checkpoint: {checkpoint}")

    cfg = patch_config(
        cfg=Config(run_dir / "config.yml"),
        run_dir=run_dir,
        data_dir=data_dir,
        basin_file=basin_file,
        device=device,
        batch_size=batch_size,
    )
    print(f"Evaluating {model} seed {seed} epoch {epoch:03d} on {basin_file}", flush=True)
    tester = get_tester(cfg=cfg, run_dir=run_dir, period="test", init_model=True)
    results = tester.evaluate(epoch=epoch, save_results=True, save_all_output=True, metrics=cfg.metrics)
    df = metric_rows_from_results(results, model=model, seed=seed, epoch=epoch, run_dir=run_dir)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False)
    return df


def summarize_metrics(metrics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in metrics.groupby(["model", "seed", "epoch"], dropna=False):
        row = dict(zip(["model", "seed", "epoch"], keys, strict=True))
        row["n_basins"] = int(group["basin"].nunique())
        for metric in METRICS:
            if metric not in group.columns:
                continue
            values = pd.to_numeric(group[metric], errors="coerce").dropna()
            safe_name = metric.replace("-", "_")
            row[f"median_{safe_name}"] = float(values.median()) if not values.empty else math.nan
            row[f"mean_{safe_name}"] = float(values.mean()) if not values.empty else math.nan
            row[f"q25_{safe_name}"] = float(values.quantile(0.25)) if not values.empty else math.nan
            row[f"q75_{safe_name}"] = float(values.quantile(0.75)) if not values.empty else math.nan
        if "NSE" in group.columns:
            row["negative_nse_basins"] = int((pd.to_numeric(group["NSE"], errors="coerce") < 0).sum())
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["model", "seed"]).reset_index(drop=True)


def compute_paired_deltas(metrics: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for seed, seed_df in metrics.groupby("seed", sort=True):
        m1_epoch = PRIMARY_EPOCHS.get(("model1", int(seed)))
        m2_epoch = PRIMARY_EPOCHS.get(("model2", int(seed)))
        left = seed_df[(seed_df["model"] == "model1") & (seed_df["epoch"] == m1_epoch)].copy()
        right = seed_df[(seed_df["model"] == "model2") & (seed_df["epoch"] == m2_epoch)].copy()
        if left.empty or right.empty:
            continue
        keep_cols = ["basin", *[metric for metric in METRICS if metric in seed_df.columns]]
        merged = left[keep_cols].merge(right[keep_cols], on="basin", suffixes=("_model1", "_model2"), how="inner")
        merged.insert(0, "seed", int(seed))
        merged.insert(1, "model1_epoch", int(m1_epoch))
        merged.insert(2, "model2_epoch", int(m2_epoch))
        for metric in METRICS:
            left_col = f"{metric}_model1"
            right_col = f"{metric}_model2"
            if left_col not in merged or right_col not in merged:
                continue
            safe_name = metric.replace("-", "_")
            merged[f"delta_{safe_name}"] = merged[right_col] - merged[left_col]
        if "FHV_model1" in merged and "FHV_model2" in merged:
            merged["abs_FHV_reduction"] = merged["FHV_model1"].abs() - merged["FHV_model2"].abs()
        if "Peak-MAPE_model1" in merged and "Peak-MAPE_model2" in merged:
            merged["Peak_MAPE_reduction"] = merged["Peak-MAPE_model1"] - merged["Peak-MAPE_model2"]
        rows.append(merged)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True).sort_values(["seed", "basin"]).reset_index(drop=True)


def summarize_deltas(deltas: pd.DataFrame) -> pd.DataFrame:
    if deltas.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    metric_cols = [col for col in deltas.columns if col.startswith("delta_") or col.endswith("_reduction")]
    for seed, group in deltas.groupby("seed", sort=True):
        row: dict[str, Any] = {"seed": int(seed), "n_basins": int(group["basin"].nunique())}
        for col in metric_cols:
            values = pd.to_numeric(group[col], errors="coerce").dropna()
            row[f"median_{col}"] = float(values.median()) if not values.empty else math.nan
            row[f"mean_{col}"] = float(values.mean()) if not values.empty else math.nan
            row[f"improved_fraction_{col}"] = float((values > 0).mean()) if not values.empty else math.nan
        rows.append(row)
    return pd.DataFrame(rows).sort_values("seed").reset_index(drop=True)


def main() -> int:
    args = parse_args()
    device = resolve_device(args.device)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = args.output_dir / "raw_metrics"
    tables_dir = args.output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    basins = read_basins(args.basin_file)
    basin_file = args.basin_file
    temp_ctx = None
    if args.limit_basins is not None:
        selected = basins[: args.limit_basins]
        temp_ctx = tempfile.TemporaryDirectory(prefix="expanded_drbc_eval_")
        basin_file = Path(temp_ctx.name) / "test.txt"
        basin_file.write_text("\n".join(selected) + "\n", encoding="utf-8")
        basins = selected

    try:
        runs = run_dirs(args.run_root)
        frames: list[pd.DataFrame] = []
        manifest_rows: list[dict[str, Any]] = []
        for seed in args.seeds:
            for model in ["model1", "model2"]:
                run_dir = runs.get((model, seed))
                epoch = PRIMARY_EPOCHS.get((model, seed))
                if run_dir is None or epoch is None:
                    manifest_rows.append(
                        {"model": model, "seed": seed, "epoch": epoch, "status": "missing_run", "run_dir": ""}
                    )
                    continue
                output_csv = raw_dir / f"{model}_seed{seed}_epoch{epoch:03d}_metrics.csv"
                df = evaluate_one(
                    run_dir=run_dir,
                    model=model,
                    seed=seed,
                    epoch=epoch,
                    data_dir=args.data_dir,
                    basin_file=basin_file,
                    output_csv=output_csv,
                    device=device,
                    batch_size=args.batch_size,
                    force=args.force,
                )
                frames.append(df)
                manifest_rows.append(
                    {
                        "model": model,
                        "seed": seed,
                        "epoch": epoch,
                        "status": "evaluated",
                        "run_dir": str(run_dir),
                        "metrics_csv": str(output_csv),
                    }
                )

        metrics = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        metrics_path = tables_dir / "basin_metrics.csv"
        metrics.to_csv(metrics_path, index=False)
        summary = summarize_metrics(metrics)
        summary_path = tables_dir / "primary_summary_by_seed.csv"
        summary.to_csv(summary_path, index=False)
        deltas = compute_paired_deltas(metrics)
        deltas_path = tables_dir / "paired_model_deltas.csv"
        deltas.to_csv(deltas_path, index=False)
        delta_summary = summarize_deltas(deltas)
        delta_summary_path = tables_dir / "paired_delta_summary_by_seed.csv"
        delta_summary.to_csv(delta_summary_path, index=False)
        manifest = pd.DataFrame(manifest_rows)
        manifest_path = args.output_dir / "evaluation_manifest.csv"
        manifest.to_csv(manifest_path, index=False)

        run_summary = {
            "experiment_name": "expanded_drbc_test",
            "description": (
                "Existing subset300 Model 1/2 checkpoints evaluated on the expanded observed DRBC test split. "
                "No retraining is performed."
            ),
            "device": device,
            "data_dir": str(args.data_dir),
            "basin_file": str(args.basin_file),
            "evaluated_basin_count": int(len(basins)),
            "seeds": args.seeds,
            "primary_epochs": {f"{model}_seed{seed}": epoch for (model, seed), epoch in PRIMARY_EPOCHS.items()},
            "outputs": {
                "manifest": str(manifest_path),
                "basin_metrics": str(metrics_path),
                "primary_summary_by_seed": str(summary_path),
                "paired_model_deltas": str(deltas_path),
                "paired_delta_summary_by_seed": str(delta_summary_path),
                "raw_metrics": str(raw_dir),
            },
        }
        summary_json = args.output_dir / "analysis_summary.json"
        summary_json.write_text(json.dumps(run_summary, indent=2), encoding="utf-8")
        print(json.dumps(run_summary, indent=2))
        return 0
    finally:
        if temp_ctx is not None:
            temp_ctx.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
