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

event catalog CSV의 각 event에 대해 [warmup 21d + pre 24h → peak → post 168h]
구간을 추론하고 peak under-deficit, event NRMSE를 계산한다.

실행 전제:
  - NC 시계열 파일: data/CAMELSH_generic/drbc_holdout_broad/time_series/
  - 체크포인트: runs/subset_comparison/camelsh_hourly_model{1,2}_drbc_holdout_subset300_seed{111,222,444}_*/
  - Event catalog: output/model_analysis/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VENDOR_NH = ROOT / "vendor" / "neuralhydrology"
if str(VENDOR_NH) not in sys.path:
    sys.path.insert(0, str(VENDOR_NH))

import numpy as np
import pandas as pd
import torch

from neuralhydrology.evaluation import get_tester
from neuralhydrology.utils.config import Config

DEFAULT_CATALOG_CSV = ROOT / "output/model_analysis/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv"
DEFAULT_RUN_ROOT = ROOT / "runs/subset_comparison"
DEFAULT_OUTPUT_DIR = ROOT / "output/model_analysis/confirmed_flood/performance"

RUN_RE = re.compile(r"camelsh_hourly_(model[12])_drbc_holdout_subset300_seed(\d+)_")
PRIMARY_EPOCHS: dict[tuple[str, int], int] = {
    ("model1", 111): 25, ("model1", 222): 10, ("model1", 444): 15,
    ("model2", 111): 5,  ("model2", 222): 10, ("model2", 444): 10,
}
PRE_HOURS = 24
POST_HOURS = 168
WARMUP_DAYS = 21


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--catalog-csv", type=Path, default=DEFAULT_CATALOG_CSV)
    p.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--seeds", type=int, nargs="+", default=[111, 222, 444])
    p.add_argument("--device", default="cpu")
    p.add_argument("--batch-size", type=int, default=None)
    p.add_argument("--limit-events", type=int, default=None, help="Smoke test용 event 수 제한")
    p.add_argument("--force", action="store_true")
    return p.parse_args()


def run_dirs(run_root: Path) -> dict[tuple[str, int], Path]:
    runs: dict[tuple[str, int], Path] = {}
    for path in sorted(run_root.iterdir()):
        if not path.is_dir():
            continue
        m = RUN_RE.match(path.name)
        if m:
            key = (m.group(1), int(m.group(2)))
            if key not in runs or path.stat().st_mtime > runs[key].stat().st_mtime:
                runs[key] = path
    return runs


def patch_config(
    *, cfg: Config, run_dir: Path, basin_file: Path,
    device: str, start: pd.Timestamp, end: pd.Timestamp,
    batch_size: int | None,
) -> Config:
    split_dir = ROOT / "configs" / "pilot" / "basin_splits" / "scaling_300"
    update = {
        "run_dir": str(run_dir),
        "train_dir": str(run_dir / "train_data"),
        "img_log_dir": str(run_dir / "img_log"),
        "data_dir": str(ROOT / "data" / "CAMELSH_generic" / "drbc_holdout_broad"),
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
            data[key] = {freq: v.to(device) for freq, v in data[key].items()}
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


def infer_basin_events(
    *, tester, basin: str, events: pd.DataFrame,
    model: str, seed: int, epoch: int,
    scale: float, center: float,
    quantile_names: list[str],
) -> list[dict]:
    """하나의 basin에 대해 모든 events를 처리하고 metric rows를 반환."""
    rows: list[dict] = []
    for _, ev in events.iterrows():
        peak_time = pd.Timestamp(ev["peak_time"])
        window_start = (peak_time - pd.Timedelta(days=WARMUP_DAYS, hours=PRE_HOURS)).floor("D")
        window_end = (peak_time + pd.Timedelta(hours=POST_HOURS)).ceil("D") - pd.Timedelta(hours=1)

        # 해당 window로 config 업데이트
        tester.cfg.update_config(
            {
                "test_start_date": window_start.strftime("%d/%m/%Y"),
                "test_end_date": window_end.strftime("%d/%m/%Y"),
            },
            dev_mode=True,
        )
        try:
            dataset = tester._get_dataset(basin)
        except Exception:
            continue
        if dataset is None or len(dataset) == 0:
            continue

        loader = torch.utils.data.DataLoader(dataset, batch_size=len(dataset))
        obs_list, pred_list, q_lists = [], [], {q: [] for q in quantile_names}
        date_list: list[pd.Timestamp] = []

        with torch.no_grad():
            for batch in loader:
                batch = move_batch_to_device(batch, tester.device)
                batch = tester.model.pre_model_hook(batch, is_train=False)
                predictions = tester.model(batch)
                dates = render_dates(batch)
                obs_raw = batch["y"][:, -1, 0].cpu().numpy()
                obs = obs_raw * scale + center

                if model == "model1":
                    pred_raw = predictions["y_hat"][:, -1, 0].cpu().numpy()
                    pred = pred_raw * scale + center
                else:
                    # quantile: y_hat shape [batch, seq, n_quantiles]
                    pred_raw = predictions["y_hat"][:, -1, :].cpu().numpy()
                    pred = pred_raw[:, 0] * scale + center  # q50 as "pred"
                    for qi, qname in enumerate(quantile_names):
                        q_lists[qname].extend((pred_raw[:, qi] * scale + center).tolist())

                obs_list.extend(obs.tolist())
                pred_list.extend(pred.tolist())
                date_list.extend(dates.tolist())

        if not obs_list:
            continue

        series = pd.DataFrame({"datetime": date_list, "obs": obs_list, "pred": pred_list})
        # eval window: pre 24h ~ post 168h (warmup 제외)
        eval_start = peak_time - pd.Timedelta(hours=PRE_HOURS)
        eval_end = peak_time + pd.Timedelta(hours=POST_HOURS)
        mask = (series["datetime"] >= eval_start) & (series["datetime"] <= eval_end)
        ev_series = series[mask]
        if ev_series.empty:
            continue

        obs_peak = float(ev_series["obs"].max())
        pred_peak = float(ev_series["pred"].max())
        under_deficit = (obs_peak - pred_peak) / obs_peak if obs_peak > 0 else None
        nrmse = float(np.sqrt(((ev_series["obs"] - ev_series["pred"]) ** 2).mean())) / (obs_peak if obs_peak > 0 else 1.0)

        row: dict = {
            "usgs_id": basin,
            "peak_time": peak_time.isoformat(),
            "model": model,
            "seed": seed,
            "quantile": "det" if model == "model1" else "q50",
            "obs_peak_cms": obs_peak,
            "pred_peak_cms": pred_peak,
            "peak_under_deficit": under_deficit,
            "is_underestimate": pred_peak < obs_peak,
            "exceeds_minor_stage": True,
            "event_nrmse": nrmse,
            "flood_tier": ev.get("flood_tier"),
            "noaa_corroborated": ev.get("noaa_corroborated"),
        }

        # model2의 quantile별 추가 row
        if model == "model2" and quantile_names:
            for qi, qname in enumerate(quantile_names):
                if qname == "q50":
                    continue  # 위에서 이미 저장
                q_series = pd.Series(q_lists[qname])
                if len(q_series) > len(mask):
                    q_series = q_series[mask.values]
                if q_series.empty:
                    continue
                q_peak = float(q_series.max())
                q_row = row.copy()
                q_row["quantile"] = qname
                q_row["pred_peak_cms"] = q_peak
                q_row["peak_under_deficit"] = (obs_peak - q_peak) / obs_peak if obs_peak > 0 else None
                q_row["is_underestimate"] = q_peak < obs_peak
                rows.append(q_row)

        rows.append(row)

    return rows


def write_basin_file(basins: list[str], output_dir: Path) -> Path:
    basin_file = output_dir / "drbc_confirmed_flood_basins.txt"
    basin_file.parent.mkdir(parents=True, exist_ok=True)
    basin_file.write_text("\n".join(sorted(set(basins))) + "\n")
    return basin_file


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    catalog = pd.read_csv(args.catalog_csv, dtype={"usgs_id": str})
    catalog["usgs_id"] = catalog["usgs_id"].str.zfill(8)
    if args.limit_events:
        catalog = catalog.head(args.limit_events)
        print(f"[smoke] {args.limit_events}개 event로 제한")

    if catalog.empty:
        print("Event catalog 비어 있음. NC 파일 준비 후 event catalog를 먼저 생성하세요.")
        return

    basins = catalog["usgs_id"].unique().tolist()
    basin_file = write_basin_file(basins, args.output_dir)
    print(f"Basins: {len(basins)}, Events: {len(catalog)}")

    runs = run_dirs(args.run_root)
    out_csv = args.output_dir / "drbc_confirmed_flood_performance.csv"
    if out_csv.exists() and not args.force:
        print(f"Output exists, skipping (use --force to overwrite): {out_csv}")
        return

    all_rows: list[dict] = []

    for seed in args.seeds:
        for model in ("model1", "model2"):
            key = (model, seed)
            epoch = PRIMARY_EPOCHS[key]
            run_dir = runs.get(key)
            if run_dir is None:
                print(f"WARN: {model} seed {seed} run dir 없음, 건너뜀")
                continue

            print(f"\n{model} seed {seed} epoch {epoch:03d} ...")
            # 전체 기간 cover (event별로 window 재지정)
            global_start = pd.Timestamp("1980-01-01")
            global_end = pd.Timestamp("2024-12-31")
            cfg = patch_config(
                cfg=Config(run_dir / "config.yml"),
                run_dir=run_dir,
                basin_file=basin_file,
                device=args.device,
                start=global_start,
                end=global_end,
                batch_size=args.batch_size,
            )
            tester = get_tester(cfg=cfg, run_dir=run_dir, period="test", init_model=True)
            tester._load_weights(epoch=epoch)
            tester.model.eval()

            target = cfg.target_variables[0]
            scale, center = target_scale_and_center(tester, target)
            quantiles = getattr(cfg, "quantiles", None) if model == "model2" else None
            quantile_names = [f"q{int(q * 100):02d}" for q in quantiles] if quantiles else []

            run_basins = [b for b in basins if b in tester.basins]
            print(f"  {len(run_basins)}/{len(basins)} basins available in tester")

            for bi, basin in enumerate(run_basins, 1):
                ev_subset = catalog[catalog["usgs_id"] == basin]
                if ev_subset.empty:
                    continue
                print(f"  [{bi}/{len(run_basins)}] {basin}: {len(ev_subset)} events")
                rows = infer_basin_events(
                    tester=tester, basin=basin, events=ev_subset,
                    model=model, seed=seed, epoch=epoch,
                    scale=scale, center=center, quantile_names=quantile_names,
                )
                all_rows.extend(rows)
                print(f"    → {len(rows)} rows")

    df = pd.DataFrame(all_rows)
    df.to_csv(out_csv, index=False)
    print(f"\nWrote: {out_csv}  ({len(df)} rows)")
    if not df.empty:
        print(df.groupby(["model", "quantile"])["peak_under_deficit"].median().to_string())


if __name__ == "__main__":
    main()
