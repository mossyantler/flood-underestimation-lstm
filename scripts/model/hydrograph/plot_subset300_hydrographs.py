#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import pickle
import re
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[3]
VENDOR_NH = ROOT / "vendor" / "neuralhydrology"
if str(VENDOR_NH) not in sys.path:
    sys.path.insert(0, str(VENDOR_NH))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

from neuralhydrology.evaluation import get_tester
from neuralhydrology.utils.config import Config
from neuralhydrology.utils.errors import NoEvaluationDataError


RUN_RE = re.compile(r"camelsh_hourly_(model[12])_drbc_holdout_subset300_seed(\d+)_")
PRIMARY_EPOCHS = {
    ("model1", 111): 25,
    ("model1", 222): 10,
    ("model1", 444): 15,
    ("model2", 111): 5,
    ("model2", 222): 10,
    ("model2", 444): 10,
}
VALIDATION_EPOCHS = [5, 10, 15, 20, 25, 30]
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


def _run_dirs(run_root: Path) -> dict[tuple[str, int], Path]:
    runs: dict[tuple[str, int], Path] = {}
    for path in sorted(run_root.iterdir()):
        if not path.is_dir():
            continue
        match = RUN_RE.match(path.name)
        if match:
            runs[(match.group(1), int(match.group(2)))] = path
    return runs


def _load_results(path: Path) -> dict:
    with path.open("rb") as fp:
        return pickle.load(fp)


def _series_from_results(results: dict, basin: str, sim_name: str) -> pd.DataFrame:
    ds = results[basin]["1h"]["xr"].sel(time_step=0)
    frame = pd.DataFrame(
        {
            "datetime": pd.to_datetime(ds["date"].values),
            "obs": ds["Streamflow_obs"].values.astype(float),
            sim_name: ds["Streamflow_sim"].values.astype(float),
        }
    )
    return frame.drop_duplicates("datetime").sort_values("datetime")


def _patch_config_for_root(cfg: Config, root: Path, run_dir: Path, device: str) -> Config:
    split_dir = root / "configs" / "pilot" / "basin_splits" / "scaling_300"
    cfg.update_config(
        {
            "run_dir": str(run_dir),
            "train_dir": str(run_dir / "train_data"),
            "img_log_dir": str(run_dir / "img_log"),
            "data_dir": str(root / "data" / "CAMELSH_generic" / "drbc_holdout_broad"),
            "train_basin_file": str(split_dir / "train.txt"),
            "validation_basin_file": str(split_dir / "validation.txt"),
            "test_basin_file": str(split_dir / "test.txt"),
            "device": device,
            "num_workers": 0,
        },
        dev_mode=True,
    )
    return cfg


def _move_batch_to_device(data: dict, device: torch.device) -> dict:
    for key in list(data.keys()):
        if key.startswith("x_d"):
            data[key] = {freq: value.to(device) for freq, value in data[key].items()}
        elif not key.startswith("date"):
            data[key] = data[key].to(device)
    return data


def _target_scale_and_center(tester, target: str) -> tuple[float, float]:
    scale_obj = tester.scaler["xarray_feature_scale"][target]
    center_obj = tester.scaler["xarray_feature_center"][target]
    scale = scale_obj.to_array().values if hasattr(scale_obj, "to_array") else scale_obj.values
    center = center_obj.to_array().values if hasattr(center_obj, "to_array") else center_obj.values
    return float(np.ravel(scale)[0]), float(np.ravel(center)[0])


def _export_model2_quantiles(
    *,
    root: Path,
    run_dir: Path,
    epoch: int,
    output_csv: Path,
    device: str,
    basins: Iterable[str] | None,
) -> Path:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    expected_basins = sorted(set(basins)) if basins else None

    if output_csv.exists() and expected_basins is not None:
        try:
            existing = pd.read_csv(output_csv, usecols=["basin"], dtype={"basin": str})
            existing_basins = set(existing["basin"].str.zfill(8).unique())
            if set(expected_basins).issubset(existing_basins):
                return output_csv
            print(
                f"Regenerating incomplete quantile export: {output_csv} "
                f"({len(existing_basins)}/{len(expected_basins)} basins)"
            )
        except Exception as exc:
            print(f"Regenerating unreadable quantile export: {output_csv} ({exc})")
        output_csv.unlink(missing_ok=True)
    elif output_csv.exists():
        return output_csv

    cfg = _patch_config_for_root(Config(run_dir / "config.yml"), root, run_dir, device)
    tester = get_tester(cfg=cfg, run_dir=run_dir, period="test", init_model=True)
    tester._load_weights(epoch=epoch)
    tester.model.eval()

    target = cfg.target_variables[0]
    scale, center = _target_scale_and_center(tester, target)
    quantiles = cfg.quantiles
    wanted_basins = set(basins) if basins else None
    run_basins = [basin for basin in tester.basins if wanted_basins is None or basin in wanted_basins]
    tmp_csv = output_csv.with_suffix(output_csv.suffix + ".tmp")
    tmp_csv.unlink(missing_ok=True)

    print(f"Exporting Model 2 quantiles: {run_dir.name} epoch {epoch:03d} ({len(run_basins)} basins)")
    with tmp_csv.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=["basin", "datetime", *QUANTILE_COLUMNS])
        writer.writeheader()

        for basin_idx, basin in enumerate(run_basins, start=1):
            print(f"  quantiles basin {basin_idx}/{len(run_basins)}: {basin}", flush=True)
            try:
                dataset = tester._get_dataset(basin)
            except NoEvaluationDataError:
                continue

            loader = DataLoader(dataset, batch_size=cfg.batch_size, num_workers=0, collate_fn=dataset.collate_fn)
            rows: list[dict[str, str | float]] = []

            with torch.no_grad():
                for batch in loader:
                    batch = _move_batch_to_device(batch, tester.device)
                    batch = tester.model.pre_model_hook(batch, is_train=False)
                    predictions = tester.model(batch)
                    y_quantiles = predictions["y_quantiles"][:, -1, :]
                    y_quantiles = y_quantiles.reshape(y_quantiles.shape[0], len(cfg.target_variables), len(quantiles))
                    y_quantiles = y_quantiles[:, 0, :].detach().cpu().numpy()
                    y_quantiles = y_quantiles * scale + center
                    if target in cfg.clip_targets_to_zero:
                        y_quantiles = np.where(y_quantiles < 0, 0, y_quantiles)

                    dates = pd.to_datetime(batch["date"][:, -1])
                    for date, values in zip(dates, y_quantiles, strict=True):
                        rendered = {f"q{int(q * 100):02d}": float(value) for q, value in zip(quantiles, values)}
                        rows.append(
                            {
                                "basin": basin,
                                "datetime": date.isoformat(),
                                "q50": rendered["q50"],
                                "q90": rendered["q90"],
                                "q95": rendered["q95"],
                                "q99": rendered["q99"],
                            }
                        )

            writer.writerows(rows)

    tmp_csv.replace(output_csv)
    return output_csv


def _load_quantile_groups(path: Path) -> dict[str, pd.DataFrame]:
    df = pd.read_csv(path, dtype={"basin": str}, parse_dates=["datetime"])
    df["basin"] = df["basin"].str.zfill(8)
    return {
        basin: group.drop_duplicates("datetime").sort_values("datetime")
        for basin, group in df.groupby("basin", sort=True)
    }


def _merge_required_series(
    *,
    basin: str,
    seed: int,
    model1_epoch: int,
    model2_epoch: int,
    model1: pd.DataFrame,
    model2: pd.DataFrame,
    quantiles: pd.DataFrame,
) -> pd.DataFrame:
    df = model1.merge(model2[["datetime", "model2_q50_result"]], on="datetime", how="inner")
    df = df.merge(quantiles[["datetime", *QUANTILE_COLUMNS]], on="datetime", how="inner")
    if df.empty:
        return df

    df["q90_minus_q50"] = df["q90"] - df["q50"]
    df["q95_minus_q90"] = df["q95"] - df["q90"]
    df["q99_minus_q95"] = df["q99"] - df["q95"]
    df["q99_minus_q50"] = df["q99"] - df["q50"]
    df["model2_q50_minus_model1"] = df["q50"] - df["model1"]
    df.insert(0, "model2_epoch", model2_epoch)
    df.insert(0, "model1_epoch", model1_epoch)
    df.insert(0, "basin", basin)
    df.insert(0, "seed", seed)
    return df[REQUIRED_SERIES_COLUMNS]


def _plot_basin(
    *,
    basin: str,
    seed: int,
    model1_epoch: int,
    model2_epoch: int,
    df: pd.DataFrame,
    output_path: Path,
    fig_width: float,
    fig_height: float,
    dpi: int,
) -> None:
    if df.empty:
        return

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    x = df["datetime"]

    ax.fill_between(x, df["q50"], df["q90"], color="#ef4444", alpha=0.28, linewidth=0, label="q50-q90")
    ax.fill_between(x, df["q90"], df["q95"], color="#f97316", alpha=0.22, linewidth=0, label="q90-q95")
    ax.fill_between(x, df["q95"], df["q99"], color="#f59e0b", alpha=0.16, linewidth=0, label="q95-q99")

    ax.plot(x, df["obs"], color="#111111", linewidth=0.75, label="Observed")
    ax.plot(x, df["model1"], color="#2563eb", linewidth=0.65, alpha=0.9, label=f"Model 1 epoch {model1_epoch}")
    ax.plot(x, df["q50"], color="#dc2626", linewidth=0.75, label=f"Model 2 q50 epoch {model2_epoch}")
    ax.plot(x, df["q90"], color="#ef4444", linewidth=0.55, alpha=0.75, linestyle="--", label="Model 2 q90")
    ax.plot(x, df["q95"], color="#f97316", linewidth=0.55, alpha=0.75, linestyle="--", label="Model 2 q95")
    ax.plot(x, df["q99"], color="#f59e0b", linewidth=0.55, alpha=0.75, linestyle="--", label="Model 2 q99")

    ax.set_title(f"Basin {basin} | seed {seed} | DRBC test period")
    ax.set_xlabel("Datetime")
    ax.set_ylabel("Streamflow")
    ax.grid(True, color="#dddddd", linewidth=0.7, alpha=0.8)
    ax.margins(x=0)
    ax.legend(loc="upper right", ncol=3, fontsize=8, frameon=True)
    fig.autofmt_xdate()
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)


def _parse_basin_list(values: list[str] | None, default_basins: list[str]) -> list[str]:
    if not values:
        return default_basins
    if len(values) == 1 and values[0].lower() == "all":
        return default_basins
    return [value.zfill(8) for value in values]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plot subset300 primary test hydrographs with Model 1, Model 2 q50, and Model 2 upper quantiles."
    )
    parser.add_argument("--run-root", type=Path, default=Path("runs/subset_comparison"))
    parser.add_argument("--output-dir", type=Path, default=Path("output/model_analysis/quantile_analysis"))
    parser.add_argument("--seeds", type=int, nargs="+", default=[111, 222, 444])
    parser.add_argument("--basins", nargs="+", default=["all"], help="Basin ids or 'all'.")
    parser.add_argument(
        "--epochs",
        choices=["primary", "all"],
        default="primary",
        help="Use validation-selected primary epochs or all validation checkpoints.",
    )
    parser.add_argument(
        "--validation-epochs",
        type=int,
        nargs="+",
        default=VALIDATION_EPOCHS,
        help="Epochs used when --epochs all is selected.",
    )
    parser.add_argument("--device", default="cpu", help="Use 'cpu', 'mps', or 'cuda:0'.")
    parser.add_argument("--fig-width", type=float, default=26.0, help="Figure width in inches.")
    parser.add_argument("--fig-height", type=float, default=6.4, help="Figure height in inches.")
    parser.add_argument("--dpi", type=int, default=170, help="Output image DPI.")
    parser.add_argument(
        "--no-series-csv",
        action="store_true",
        help="Only create plots and Model 2 quantile exports; skip merged required time-series CSV files.",
    )
    args = parser.parse_args()

    root = Path.cwd()
    run_root = args.run_root
    output_dir = args.output_dir
    plot_dir = output_dir / "primary_seed_basin"
    quantile_dir = output_dir / "quantile_exports"
    series_dir = output_dir / "required_series"
    runs = _run_dirs(run_root)

    manifest_rows = []

    for seed in args.seeds:
        model1_run = runs.get(("model1", seed))
        model2_run = runs.get(("model2", seed))
        if model1_run is None or model2_run is None:
            print(f"Skipping seed {seed}: missing Model 1 or Model 2 run directory.")
            continue

        if args.epochs == "primary":
            epoch_pairs = [(PRIMARY_EPOCHS[("model1", seed)], PRIMARY_EPOCHS[("model2", seed)], "primary")]
        else:
            epoch_pairs = [(epoch, epoch, f"epoch{epoch:03d}") for epoch in args.validation_epochs]

        for model1_epoch, model2_epoch, epoch_label in epoch_pairs:
            series_frames: list[pd.DataFrame] = []
            series_csv = series_dir / f"seed{seed}" / f"{epoch_label}_required_series.csv"
            model1_results_path = model1_run / "test" / f"model_epoch{model1_epoch:03d}" / "test_results.p"
            model2_results_path = model2_run / "test" / f"model_epoch{model2_epoch:03d}" / "test_results.p"
            if not model1_results_path.exists() or not model2_results_path.exists():
                print(
                    f"Skipping seed {seed} {epoch_label}: missing test result pickle "
                    f"(Model 1 epoch {model1_epoch:03d}, Model 2 epoch {model2_epoch:03d})."
                )
                continue

            model1_results = _load_results(model1_results_path)
            model2_results = _load_results(model2_results_path)
            common_basins = sorted(set(model1_results) & set(model2_results))
            basins = _parse_basin_list(args.basins, common_basins)

            quantile_csv = quantile_dir / f"model2_seed{seed}_epoch{model2_epoch:03d}_quantiles.csv"
            _export_model2_quantiles(
                root=root,
                run_dir=model2_run,
                epoch=model2_epoch,
                output_csv=quantile_csv,
                device=args.device,
                basins=basins,
            )
            quantile_groups = _load_quantile_groups(quantile_csv)

            for basin_idx, basin in enumerate(basins, start=1):
                if basin not in model1_results or basin not in model2_results:
                    continue
                if basin not in quantile_groups:
                    print(f"Skipping seed {seed} {epoch_label} basin {basin}: no quantile rows.")
                    continue
                print(f"Plotting seed {seed} {epoch_label} basin {basin_idx}/{len(basins)}: {basin}", flush=True)
                model1_df = _series_from_results(model1_results, basin, "model1")
                model2_df = _series_from_results(model2_results, basin, "model2_q50_result")
                quantile_df = quantile_groups[basin]
                required_series = _merge_required_series(
                    basin=basin,
                    seed=seed,
                    model1_epoch=model1_epoch,
                    model2_epoch=model2_epoch,
                    model1=model1_df,
                    model2=model2_df,
                    quantiles=quantile_df,
                )
                if required_series.empty:
                    print(f"Skipping seed {seed} {epoch_label} basin {basin}: no overlapping time steps.")
                    continue
                if not args.no_series_csv:
                    series_frames.append(required_series)
                plot_path = (
                    plot_dir
                    / f"seed{seed}"
                    / epoch_label
                    / f"basin_{basin}_seed{seed}_{epoch_label}.png"
                )
                _plot_basin(
                    basin=basin,
                    seed=seed,
                    model1_epoch=model1_epoch,
                    model2_epoch=model2_epoch,
                    df=required_series,
                    output_path=plot_path,
                    fig_width=args.fig_width,
                    fig_height=args.fig_height,
                    dpi=args.dpi,
                )
                manifest_rows.append(
                    {
                        "seed": seed,
                        "basin": basin,
                        "model1_epoch": model1_epoch,
                        "model2_epoch": model2_epoch,
                        "plot_path": str(plot_path),
                        "quantile_csv": str(quantile_csv),
                        "series_csv": "" if args.no_series_csv else str(series_csv),
                    }
                )

            if series_frames:
                series_csv.parent.mkdir(parents=True, exist_ok=True)
                tmp_csv = series_csv.with_suffix(series_csv.suffix + ".tmp")
                pd.concat(series_frames, ignore_index=True).to_csv(tmp_csv, index=False)
                tmp_csv.replace(series_csv)
                print(f"Wrote required series: {series_csv}", flush=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "hydrograph_plot_manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=["seed", "basin", "model1_epoch", "model2_epoch", "plot_path", "quantile_csv", "series_csv"],
        )
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(f"Wrote {len(manifest_rows)} hydrograph plots.")
    print(f"Manifest: {manifest_path}")
    print(f"Plot directory: {plot_dir}")
    print(f"Quantile exports: {quantile_dir}")
    if not args.no_series_csv:
        print(f"Required series exports: {series_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
