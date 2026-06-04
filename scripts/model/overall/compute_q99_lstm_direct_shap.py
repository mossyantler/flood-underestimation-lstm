#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "ruamel.yaml>=0.18",
#   "shap>=0.46",
#   "torch>=2.0",
#   "xarray>=2024",
#   "netCDF4>=1.7",
# ]
# ///
"""Direct SHAP analysis for Model 2 quantile LSTM predictions.

This script is intentionally separate from the existing GradientInput script.
It applies ``shap.GradientExplainer`` to the reconstructed quantile LSTM itself,
not to an event-level RandomForest surrogate.

Typical GPU-server run
----------------------
uv run scripts/model/overall/compute_q99_lstm_direct_shap.py \
  --seed 111 --device cuda --quantiles q50 q90 q95 q99 \
  --max-events 120 --background-events 32 --shap-samples 64

Local smoke test
----------------
uv run scripts/model/overall/compute_q99_lstm_direct_shap.py \
  --smoke --output-dir tmp/q99_lstm_direct_shap_smoke --max-events 3 \
  --background-events 2 --shap-samples 8
"""
from __future__ import annotations

import argparse
import html
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager


def configure_plot_fonts() -> None:
    """Use a Korean-capable font when the local machine provides one."""
    preferred = ["AppleGothic", "NanumGothic", "Noto Sans CJK KR", "Noto Sans KR", "Malgun Gothic"]
    installed = {font.name for font in font_manager.fontManager.ttflist}
    for name in preferred:
        if name in installed:
            matplotlib.rcParams["font.family"] = [name]
            matplotlib.rcParams["axes.unicode_minus"] = False
            return


configure_plot_fonts()
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import xarray as xr
from ruamel.yaml import YAML

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "vendor" / "neuralhydrology"))

DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/shap/test_split"
DEFAULT_EVENT_CSV = REPO_ROOT / "output/model_analysis/q99_analysis/causes/tables/q99_event_forcing_drivers.csv"
DEFAULT_STATIC_CSV = (
    REPO_ROOT / "output/basin/drbc/analysis/basin_attributes/tables/drbc_selected_static_attributes_full.csv"
)
DEFAULT_NC_DIR = REPO_ROOT / "data/CAMELSH_generic/drbc_expanded_observed_test/time_series"

_SEED_RUN_DIRS = {
    111: "camelsh_hourly_model2_drbc_holdout_subset300_seed111_1904_232450",
    222: "camelsh_hourly_model2_drbc_holdout_subset300_seed222_2204_160730",
    444: "camelsh_hourly_model2_drbc_holdout_subset300_seed444_2504_065913",
}

DYNAMIC_FEATURES = [
    "Rainf",
    "Tair",
    "PotEvap",
    "SWdown",
    "Qair",
    "PSurf",
    "Wind_E",
    "Wind_N",
    "LWdown",
    "CAPE",
    "CRainf_frac",
]
STATIC_FEATURES = [
    "area",
    "slope",
    "aridity",
    "snow_fraction",
    "soil_depth",
    "permeability",
    "forest_fraction",
    "baseflow_index",
]
FEATURE_LABEL_KO = {
    "Rainf": "강수량(Rainf)",
    "Tair": "기온(Tair)",
    "PotEvap": "잠재 증발산(PotEvap)",
    "SWdown": "단파 복사(SWdown)",
    "Qair": "비습도(Qair)",
    "PSurf": "지표 기압(PSurf)",
    "Wind_E": "동서 바람(Wind_E)",
    "Wind_N": "남북 바람(Wind_N)",
    "LWdown": "장파 복사(LWdown)",
    "CAPE": "대류 가능 에너지(CAPE)",
    "CRainf_frac": "대류성 강수 비율(CRainf_frac)",
    "area": "유역 면적(area)",
    "slope": "유역 경사(slope)",
    "aridity": "건조도(aridity)",
    "snow_fraction": "눈 영향 비율(snow_fraction)",
    "soil_depth": "토양 깊이(soil_depth)",
    "permeability": "투수성(permeability)",
    "forest_fraction": "산림 비율(forest_fraction)",
    "baseflow_index": "기저유량 지수(baseflow_index)",
}
SEQ_LEN = 336
HIDDEN_SIZE = 128
N_QUANTILES = 4
QUANTILE_INDEX = {"q50": 0, "q90": 1, "q95": 2, "q99": 3}
DEFAULT_QUANTILES = ["q50", "q90", "q95", "q99"]
LAG_HOURS = [0, 24, 48, 72, 96, 120, 168, 240, 336]


@dataclass(frozen=True)
class PreparedInputs:
    records: list[dict[str, Any]]
    dynamic: torch.Tensor  # [batch, seq, dyn]
    static: torch.Tensor  # [batch, static]


class QuantileHead(nn.Module):
    def __init__(self, n_in: int, n_quantiles: int):
        super().__init__()
        self._projection = nn.Linear(n_in, n_quantiles)
        self._softplus = nn.Softplus()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        raw = self._projection(x)
        base = raw[..., :1]
        increments = self._softplus(raw[..., 1:])
        return torch.cat([base, base + torch.cumsum(increments, dim=-1)], dim=-1)


class MinimalQ99LSTM(nn.Module):
    """Minimal reconstruction of the Model 2 CudaLSTM + monotone quantile head."""

    def __init__(self, *, seq_first: bool = True, hidden_size: int = HIDDEN_SIZE):
        super().__init__()
        self.seq_first = seq_first
        self.lstm = nn.LSTM(
            input_size=len(DYNAMIC_FEATURES) + len(STATIC_FEATURES),
            hidden_size=hidden_size,
            batch_first=not seq_first,
        )
        self.head = QuantileHead(n_in=hidden_size, n_quantiles=N_QUANTILES)

    def load_nh_checkpoint(self, ckpt_path: Path) -> None:
        state = torch.load(ckpt_path, map_location="cpu", weights_only=True)
        self.load_state_dict(state)

    def forward_quantiles(self, x_d: torch.Tensor, x_s: torch.Tensor) -> torch.Tensor:
        if self.seq_first:
            # x_d: [seq, batch, dynamic], x_s: [batch, static]
            x_s_exp = x_s.unsqueeze(0).expand(x_d.shape[0], -1, -1)
            x = torch.cat([x_d, x_s_exp], dim=-1)
            lstm_out, _ = self.lstm(x)
            last_h = lstm_out[-1]
        else:
            # x_d: [batch, seq, dynamic], x_s: [batch, static]
            x_s_exp = x_s.unsqueeze(1).expand(-1, x_d.shape[1], -1)
            x = torch.cat([x_d, x_s_exp], dim=-1)
            lstm_out, _ = self.lstm(x)
            last_h = lstm_out[:, -1]
        return self.head(last_h)

    def forward(self, x_d: torch.Tensor, x_s: torch.Tensor) -> torch.Tensor:
        return self.forward_quantiles(x_d, x_s)


class ShapQ99Wrapper(nn.Module):
    """Batch-first wrapper expected by SHAP's PyTorch GradientExplainer."""

    def __init__(self, model: MinimalQ99LSTM, *, quantile: str):
        super().__init__()
        self.model = model
        self.quantile = quantile
        self.quantile_idx = QUANTILE_INDEX[quantile]

    def forward(self, x_d_batch_first: torch.Tensor, x_s: torch.Tensor) -> torch.Tensor:
        if self.model.seq_first:
            quantiles = self.model.forward_quantiles(x_d_batch_first.transpose(0, 1), x_s)
        else:
            quantiles = self.model.forward_quantiles(x_d_batch_first, x_s)
        # SHAP's PyTorch GradientExplainer expects a 2-D output: [batch, output_dim].
        return quantiles[:, self.quantile_idx].unsqueeze(-1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Direct SHAP analysis for Model 2 q50/q90/q95/q99 LSTM predictions.")
    parser.add_argument("--seed", type=int, default=111, choices=[111, 222, 444])
    parser.add_argument("--smoke", action="store_true", help="Run a tiny synthetic CPU example for local validation.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--event-csv", type=Path, default=DEFAULT_EVENT_CSV)
    parser.add_argument("--static-csv", type=Path, default=DEFAULT_STATIC_CSV)
    parser.add_argument("--nc-dir", type=Path, default=DEFAULT_NC_DIR)
    parser.add_argument("--run-dir", type=Path, default=None, help="Override seed run directory containing checkpoint/scaler.")
    parser.add_argument("--checkpoint", type=Path, default=None)
    parser.add_argument("--scaler", type=Path, default=None)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda", "mps"], default="auto")
    parser.add_argument(
        "--analysis-start-date",
        default="2014-01-01",
        help="Earliest event anchor date included in real-data SHAP. Default: 2014-01-01.",
    )
    parser.add_argument(
        "--analysis-end-date",
        default="2016-12-31 23:59:59",
        help="Latest event anchor date included in real-data SHAP. Default: 2016-12-31 23:59:59.",
    )
    parser.add_argument("--max-events", type=int, default=120)
    parser.add_argument("--background-events", type=int, default=32)
    parser.add_argument("--shap-samples", type=int, default=64)
    parser.add_argument(
        "--quantiles",
        nargs="+",
        choices=list(QUANTILE_INDEX),
        default=DEFAULT_QUANTILES,
        help="Quantile outputs to explain. Default: q50 q90 q95 q99.",
    )
    parser.add_argument("--random-state", type=int, default=20260530)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def choose_device(requested: str) -> torch.device:
    if requested == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("--device cuda was requested, but CUDA is not available in this environment.")
    if requested == "mps" and not (hasattr(torch.backends, "mps") and torch.backends.mps.is_available()):
        raise RuntimeError("--device mps was requested, but MPS is not available in this environment.")
    return torch.device(requested)


def load_scaler(path: Path) -> dict[str, Any]:
    yaml = YAML(typ="safe")
    with path.open(encoding="utf-8") as f:
        raw = yaml.load(f)
    attr_mean = pd.Series(raw["attribute_means"])
    attr_std = pd.Series(raw["attribute_stds"])
    center = {k: v["data"] for k, v in raw["xarray_feature_center"]["data_vars"].items()}
    scale = {k: v["data"] for k, v in raw["xarray_feature_scale"]["data_vars"].items()}
    return {"attr_mean": attr_mean, "attr_std": attr_std, "center": center, "scale": scale}


def normalize_dynamic(arr: np.ndarray, feat: str, scaler: dict[str, Any]) -> np.ndarray:
    center = scaler["center"].get(feat, 0.0)
    scale = scaler["scale"].get(feat, 1.0) or 1.0
    return (arr - center) / scale


def normalize_static(value: float, feat: str, scaler: dict[str, Any]) -> float:
    mean = scaler["attr_mean"].get(feat, 0.0)
    std = scaler["attr_std"].get(feat, 1.0) or 1.0
    return float((value - mean) / std)


def read_static(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "gauge_id" in frame.columns and "basin" not in frame.columns:
        frame = frame.rename(columns={"gauge_id": "basin"})
    if "basin" not in frame.columns:
        raise ValueError(f"Static attribute table must contain basin or gauge_id: {path}")
    frame["basin"] = frame["basin"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(8)
    for feat in STATIC_FEATURES:
        if feat not in frame.columns:
            frame[feat] = np.nan
        frame[feat] = pd.to_numeric(frame[feat], errors="coerce")
    return frame[["basin", *STATIC_FEATURES]].drop_duplicates("basin")


def read_events(path: Path, seed: int, max_events: int, *, start_date: str | None, end_date: str | None) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "seed" in frame.columns:
        frame = frame[pd.to_numeric(frame["seed"], errors="coerce").eq(seed)].copy()
    basin_col = "basin" if "basin" in frame.columns else "gauge_id"
    if basin_col not in frame.columns:
        raise ValueError(f"Event table must contain basin or gauge_id: {path}")
    frame["basin"] = frame[basin_col].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(8)
    time_col = "event_peak" if "event_peak" in frame.columns else "event_end"
    if time_col not in frame.columns:
        raise ValueError(f"Event table must contain event_peak or event_end: {path}")
    frame["shap_anchor_time"] = pd.to_datetime(frame[time_col], errors="coerce")
    frame = frame.dropna(subset=["shap_anchor_time"]).reset_index(drop=True)
    if start_date:
        start = pd.Timestamp(start_date)
        frame = frame[frame["shap_anchor_time"].ge(start)].copy()
    if end_date:
        end = pd.Timestamp(end_date)
        frame = frame[frame["shap_anchor_time"].le(end)].copy()
    frame = frame.reset_index(drop=True)
    if max_events > 0:
        frame = frame.head(max_events).copy()
    return frame


_nc_cache: dict[tuple[str, str], xr.Dataset] = {}


def open_nc(nc_dir: Path, basin: str) -> xr.Dataset | None:
    key = (str(nc_dir), basin.zfill(8))
    if key not in _nc_cache:
        path = nc_dir / f"{basin.zfill(8)}.nc"
        if not path.exists():
            return None
        _nc_cache[key] = xr.open_dataset(path)
    return _nc_cache[key]


def extract_window(nc_dir: Path, basin: str, anchor_time: pd.Timestamp, scaler: dict[str, Any]) -> np.ndarray | None:
    ds = open_nc(nc_dir, basin)
    if ds is None:
        return None
    start = anchor_time - pd.Timedelta(hours=SEQ_LEN - 1)
    sub = ds.sel(date=slice(str(start), str(anchor_time)))
    dates = pd.to_datetime(sub["date"].values) if "date" in sub.coords else []
    if len(dates) == 0:
        return None
    window = np.zeros((SEQ_LEN, len(DYNAMIC_FEATURES)), dtype=np.float32)
    offset = max(SEQ_LEN - len(dates), 0)
    for idx, feat in enumerate(DYNAMIC_FEATURES):
        if feat not in sub:
            continue
        values = sub[feat].values.astype(np.float32).reshape(-1)
        values = values[-SEQ_LEN:]
        normed = normalize_dynamic(values, feat, scaler).astype(np.float32)
        start_idx = max(SEQ_LEN - len(normed), 0)
        window[start_idx : start_idx + len(normed), idx] = normed
    return np.nan_to_num(window, nan=0.0, posinf=0.0, neginf=0.0)


def prepare_real_inputs(
    events: pd.DataFrame,
    static_df: pd.DataFrame,
    scaler: dict[str, Any],
    nc_dir: Path,
    *,
    device: torch.device,
) -> PreparedInputs:
    static_by_basin = static_df.set_index("basin")
    dyn_rows: list[np.ndarray] = []
    static_rows: list[np.ndarray] = []
    records: list[dict[str, Any]] = []
    skipped = 0
    for idx, row in events.iterrows():
        basin = str(row["basin"]).zfill(8)
        if basin not in static_by_basin.index:
            skipped += 1
            continue
        window = extract_window(nc_dir, basin, pd.Timestamp(row["shap_anchor_time"]), scaler)
        if window is None:
            skipped += 1
            continue
        static_values = []
        sta = static_by_basin.loc[basin]
        for feat in STATIC_FEATURES:
            raw = sta.get(feat, scaler["attr_mean"].get(feat, 0.0))
            if pd.isna(raw):
                raw = scaler["attr_mean"].get(feat, 0.0)
            static_values.append(normalize_static(float(raw), feat, scaler))
        dyn_rows.append(window)
        static_rows.append(np.asarray(static_values, dtype=np.float32))
        records.append(
            {
                **{
                    str(key): value
                    for key, value in row.to_dict().items()
                    if key not in {"shap_anchor_time"}
                    and isinstance(key, str)
                    and key not in {"basin"}
                    and not isinstance(value, (list, dict, tuple, set))
                },
                "row_index": int(idx),
                "basin": basin,
                "event_id": row.get("event_id", idx),
                "anchor_time": str(row["shap_anchor_time"]),
            }
        )
    if not records:
        raise RuntimeError(f"No valid events for SHAP input preparation. Skipped rows: {skipped}")
    dynamic = torch.tensor(np.stack(dyn_rows), dtype=torch.float32, device=device)
    static = torch.tensor(np.stack(static_rows), dtype=torch.float32, device=device)
    print(f"Prepared {len(records)} events for direct SHAP; skipped {skipped} rows.")
    return PreparedInputs(records=records, dynamic=dynamic, static=static)


def prepare_smoke_inputs(max_events: int, background_events: int, *, device: torch.device, seed: int) -> tuple[MinimalQ99LSTM, PreparedInputs, PreparedInputs]:
    rng = np.random.default_rng(seed)
    seq_len = 36
    n_background = max(1, background_events)
    n_samples = max(1, max_events)
    # Smoke model uses the same input/output contract but a shorter sequence and smaller hidden state.
    model = MinimalQ99LSTM(seq_first=False, hidden_size=12).to(device)
    model.eval()
    background_dyn = rng.normal(size=(n_background, seq_len, len(DYNAMIC_FEATURES))).astype(np.float32)
    sample_dyn = rng.normal(size=(n_samples, seq_len, len(DYNAMIC_FEATURES))).astype(np.float32)
    background_static = rng.normal(size=(n_background, len(STATIC_FEATURES))).astype(np.float32)
    sample_static = rng.normal(size=(n_samples, len(STATIC_FEATURES))).astype(np.float32)
    records = [
        {"row_index": i, "basin": f"smoke_{i:03d}", "event_id": f"smoke_event_{i}", "anchor_time": "synthetic"}
        for i in range(n_samples)
    ]
    background_records = [
        {"row_index": i, "basin": f"background_{i:03d}", "event_id": f"background_{i}", "anchor_time": "synthetic"}
        for i in range(n_background)
    ]
    samples = PreparedInputs(
        records=records,
        dynamic=torch.tensor(sample_dyn, dtype=torch.float32, device=device),
        static=torch.tensor(sample_static, dtype=torch.float32, device=device),
    )
    background = PreparedInputs(
        records=background_records,
        dynamic=torch.tensor(background_dyn, dtype=torch.float32, device=device),
        static=torch.tensor(background_static, dtype=torch.float32, device=device),
    )
    return model, background, samples


def compute_shap_values(
    model: MinimalQ99LSTM,
    background: PreparedInputs,
    samples: PreparedInputs,
    *,
    quantile: str,
    shap_samples: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    import shap

    wrapper = ShapQ99Wrapper(model, quantile=quantile).to(samples.dynamic.device)
    # CUDA/cuDNN의 LSTM은 기울기 기반 설명을 계산할 때 RNN backward가
    # training mode에서만 허용된다. 이 모델은 dropout이 없는 단층 LSTM이라
    # train/eval 전환이 예측식을 바꾸지 않으며, SHAP 기울기 구간에만
    # train mode를 사용한다. 다만 shap.GradientExplainer 내부에서 모델을
    # eval mode로 되돌리는 버전이 있어, CUDA에서는 SHAP 계산 구간에만
    # cuDNN RNN 경로를 끄고 일반 PyTorch backward로 계산한다.
    wrapper.train()
    explainer = shap.GradientExplainer(wrapper, [background.dynamic, background.static])
    if samples.dynamic.device.type == "cuda":
        with torch.backends.cudnn.flags(enabled=False):
            raw_values = explainer.shap_values([samples.dynamic, samples.static], nsamples=shap_samples)
    else:
        raw_values = explainer.shap_values([samples.dynamic, samples.static], nsamples=shap_samples)
    dyn_values, static_values = split_shap_values(raw_values)
    wrapper.eval()
    with torch.no_grad():
        predictions = wrapper(samples.dynamic, samples.static).detach().cpu().numpy().reshape(-1)
    return dyn_values, static_values, predictions


def split_shap_values(raw_values: Any) -> tuple[np.ndarray, np.ndarray]:
    """Normalize SHAP's several PyTorch return shapes into dynamic/static arrays."""
    values = raw_values
    if isinstance(values, tuple):
        values = list(values)
    if isinstance(values, list) and len(values) == 1 and isinstance(values[0], (list, tuple)):
        values = list(values[0])
    if not (isinstance(values, list) and len(values) == 2):
        raise TypeError(f"Expected SHAP values for two model inputs, got {type(raw_values)!r}: {raw_values!r}")
    dyn = np.asarray(values[0], dtype=float)
    sta = np.asarray(values[1], dtype=float)
    if dyn.ndim == 4 and dyn.shape[-1] == 1:
        dyn = dyn[..., 0]
    if sta.ndim == 3 and sta.shape[-1] == 1:
        sta = sta[..., 0]
    return dyn, sta


def build_event_feature_table(
    quantile: str,
    records: list[dict[str, Any]],
    dyn_values: np.ndarray,
    static_values: np.ndarray,
    predictions: np.ndarray,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for event_idx, record in enumerate(records):
        base = dict(record)
        base["quantile"] = quantile
        base["quantile_prediction_normalized"] = float(predictions[event_idx])
        for feat_idx, feat in enumerate(DYNAMIC_FEATURES):
            values = dyn_values[event_idx, :, feat_idx]
            rows.append(
                {
                    **base,
                    "feature_group": "dynamic_forcing",
                    "feature": feat,
                    "feature_label_ko": FEATURE_LABEL_KO.get(feat, feat),
                    "mean_abs_shap": float(np.mean(np.abs(values))),
                    "mean_signed_shap": float(np.mean(values)),
                    "max_abs_shap": float(np.max(np.abs(values))),
                }
            )
        for feat_idx, feat in enumerate(STATIC_FEATURES):
            value = static_values[event_idx, feat_idx]
            rows.append(
                {
                    **base,
                    "feature_group": "static_attribute",
                    "feature": feat,
                    "feature_label_ko": FEATURE_LABEL_KO.get(feat, feat),
                    "mean_abs_shap": float(abs(value)),
                    "mean_signed_shap": float(value),
                    "max_abs_shap": float(abs(value)),
                }
            )
    return pd.DataFrame(rows)


def build_global_feature_table(event_feature: pd.DataFrame) -> pd.DataFrame:
    frame = (
        event_feature.groupby(["quantile", "feature_group", "feature", "feature_label_ko"], as_index=False)
        .agg(
            mean_abs_shap=("mean_abs_shap", "mean"),
            median_abs_shap=("mean_abs_shap", "median"),
            mean_signed_shap=("mean_signed_shap", "mean"),
            max_abs_shap=("max_abs_shap", "max"),
            n_events=("event_id", "nunique"),
        )
        .sort_values("mean_abs_shap", ascending=False)
        .reset_index(drop=True)
    )
    frame["rank"] = frame.groupby("quantile")["mean_abs_shap"].rank(method="first", ascending=False).astype(int)
    frame = frame.sort_values(["quantile", "rank"]).reset_index(drop=True)
    first_cols = ["quantile", "rank"]
    frame = frame[first_cols + [col for col in frame.columns if col not in first_cols]]
    return frame


def build_temporal_lag_table(quantile: str, dyn_values: np.ndarray) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    seq_len = dyn_values.shape[1]
    for lag in LAG_HOURS:
        t_idx = seq_len - 1 - lag
        if t_idx < 0:
            continue
        for feat_idx, feat in enumerate(DYNAMIC_FEATURES):
            values = dyn_values[:, t_idx, feat_idx]
            rows.append(
                {
                    "quantile": quantile,
                    "lag_hours_before_anchor": lag,
                    "feature": feat,
                    "feature_label_ko": FEATURE_LABEL_KO.get(feat, feat),
                    "mean_abs_shap": float(np.mean(np.abs(values))),
                    "mean_signed_shap": float(np.mean(values)),
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["quantile", "lag_hours_before_anchor", "mean_abs_shap"], ascending=[True, True, False]
    )


def save_global_bar(global_table: pd.DataFrame, path: Path, quantile: str, title_suffix: str) -> None:
    sub = global_table.head(14).sort_values("mean_abs_shap")
    fig, ax = plt.subplots(figsize=(8, 5.8))
    colors = ["#2563eb" if g == "dynamic_forcing" else "#7c3aed" for g in sub["feature_group"]]
    ax.barh(sub["feature_label_ko"], sub["mean_abs_shap"], color=colors, alpha=0.86)
    ax.set_xlabel("평균 |SHAP 값|")
    ax.set_title(f"{quantile} LSTM 직접 SHAP 입력 중요도{title_suffix}")
    ax.grid(True, axis="x", color="#e5e7eb", linewidth=0.7)
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


def save_temporal_plot(lag_table: pd.DataFrame, path: Path, quantile: str, title_suffix: str) -> None:
    if lag_table.empty:
        return
    top_features = (
        lag_table.groupby("feature", as_index=False)["mean_abs_shap"].mean().sort_values("mean_abs_shap", ascending=False).head(4)["feature"].tolist()
    )
    fig, ax = plt.subplots(figsize=(8, 5))
    for feat in top_features:
        sub = lag_table[lag_table["feature"].eq(feat)].sort_values("lag_hours_before_anchor")
        ax.plot(
            sub["lag_hours_before_anchor"],
            sub["mean_abs_shap"],
            marker="o",
            label=FEATURE_LABEL_KO.get(feat, feat),
        )
    ax.invert_xaxis()
    ax.set_xlabel("예측 기준 시점으로부터 몇 시간 전인가")
    ax.set_ylabel("평균 |SHAP 값|")
    ax.set_title(f"{quantile} 시간별 직접 SHAP 민감도{title_suffix}")
    ax.legend(fontsize=8)
    ax.grid(True, color="#e5e7eb", linewidth=0.7)
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


def method_html() -> str:
    return """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>q50/q90/q95/q99 LSTM 직접 SHAP 분석 방법</title>
<style>
:root { color-scheme: light; --ink:#172033; --muted:#5b6475; --line:#d8dee9; --blue:#1d4ed8; --bg:#f6f8fb; --card:#ffffff; --warn:#fff7ed; --warnline:#fed7aa; }
body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",Segoe UI,sans-serif; background:var(--bg); color:var(--ink); line-height:1.68; }
main { max-width:980px; margin:0 auto; padding:32px 18px 52px; }
.hero, section { background:var(--card); border:1px solid var(--line); border-radius:18px; padding:24px; margin:16px 0; box-shadow:0 10px 28px rgba(15,23,42,.05); }
h1 { font-size:30px; margin:0 0 8px; } h2 { font-size:22px; margin:0 0 12px; } h3 { font-size:17px; margin:18px 0 8px; }
.lead { font-size:18px; color:var(--muted); margin:0; } .tag { display:inline-block; padding:4px 10px; border-radius:999px; background:#dbeafe; color:#1e40af; font-weight:700; font-size:13px; margin-bottom:10px; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; }
.card { border:1px solid var(--line); border-radius:14px; padding:14px; background:#fbfdff; }
.warn { background:var(--warn); border-color:var(--warnline); }
code { background:#eef2ff; padding:2px 6px; border-radius:6px; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }
pre { overflow:auto; background:#111827; color:#e5e7eb; border-radius:14px; padding:16px; font-size:13px; }
table { width:100%; border-collapse:collapse; margin-top:10px; } th,td { border-bottom:1px solid var(--line); padding:10px; text-align:left; vertical-align:top; } th { background:#f1f5f9; }
.step { display:flex; gap:12px; align-items:flex-start; margin:12px 0; } .num { flex:0 0 30px; height:30px; border-radius:50%; background:var(--blue); color:white; display:flex; align-items:center; justify-content:center; font-weight:800; }
.small { color:var(--muted); font-size:14px; }
</style>
</head>
<body>
<main>
  <div class="hero">
    <div class="tag">비전공자용 설명</div>
    <h1>q50/q90/q95/q99 모델에 직접 SHAP 분석</h1>
    <p class="lead">이번 분석은 대리 모델을 새로 만들어 설명하는 방식이 아니라, 이미 학습된 LSTM의 네 개 quantile 예측값을 직접 놓고 “어떤 입력이 각 예측을 움직였는가”를 계산하는 방식이다.</p>
  </div>

  <section>
    <h2>1. 왜 q99 하나만 보지 않는가</h2>
    <p><strong>모델에 직접 SHAP</strong>은 LSTM 예측값 자체를 대상으로 입력 기여도를 나누어 보는 방법이다. 이번에는 q99만 보지 않고 <strong>q50/q90/q95/q99</strong>를 모두 본다.</p>
    <div class="grid">
      <div class="card"><h3>q50</h3><p>모델의 중심 예측이 어떤 입력을 보는지 확인한다.</p></div>
      <div class="card"><h3>q90</h3><p>상단부 예측이 시작될 때 어떤 입력이 중요해지는지 본다.</p></div>
      <div class="card"><h3>q95</h3><p>홍수 첨두 쪽으로 갈수록 민감도가 어떻게 바뀌는지 본다.</p></div>
      <div class="card"><h3>q99</h3><p>극단 상단 예측이 특별히 다른 입력에 의존하는지 본다.</p></div>
    </div>
    <p>핵심 질문은 “q99가 무엇을 봤나?”가 아니라 “q50에서 q99로 올라갈수록 모델이 보는 입력 신호가 어떻게 달라지나?”이다.</p>
  </section>

  <section>
    <h2>2. 기존 대리 모델 SHAP과 무엇이 다른가</h2>
    <table>
      <thead><tr><th>구분</th><th>기존 event-level 대리 모델 SHAP</th><th>이번 LSTM 직접 SHAP</th></tr></thead>
      <tbody>
        <tr><td>무엇을 설명하나</td><td>event별 오차나 개선량을 설명하는 RandomForest</td><td>학습된 LSTM의 q50/q90/q95/q99 예측값 자체</td></tr>
        <tr><td>입력</td><td>event 요약값, 유역 속성</td><td>336시간 기상 시계열 + 유역 속성</td></tr>
        <tr><td>알 수 있는 것</td><td>어떤 조건에서 오차가 커지거나 개선되는지</td><td>quantile 단계가 올라갈수록 LSTM이 어느 변수와 어느 시점에 민감해지는지</td></tr>
        <tr><td>주의점</td><td>LSTM 내부 설명이 아님</td><td>모델 민감도 설명이지 현실의 인과 증명은 아님</td></tr>
      </tbody>
    </table>
  </section>

  <section>
    <h2>3. 분석 절차</h2>
    <div class="step"><div class="num">1</div><div><strong>event 선택</strong><br/>DRBC test의 high-flow event를 고른다. smoke test에서는 가짜 작은 데이터를 사용한다.</div></div>
    <div class="step"><div class="num">2</div><div><strong>입력 창 만들기</strong><br/>각 event의 기준 시점까지 과거 336시간 기상 입력을 자른다. 유역 속성은 같은 event 전체에 붙인다.</div></div>
    <div class="step"><div class="num">3</div><div><strong>학습된 LSTM 불러오기</strong><br/>Model 2 checkpoint와 학습 scaler를 불러와 학습 때와 같은 단위로 입력을 맞춘다.</div></div>
    <div class="step"><div class="num">4</div><div><strong>SHAP 계산</strong><br/><code>shap.GradientExplainer</code>로 q50, q90, q95, q99 각각의 출력값에 대한 입력별 기여도를 계산한다.</div></div>
    <div class="step"><div class="num">5</div><div><strong>ladder 비교</strong><br/>변수별 중요도, event별 중요도, 시간 lag별 중요도를 quantile 컬럼과 함께 저장해 단계별 차이를 비교한다.</div></div>
  </section>

  <section class="warn">
    <h2>4. 관측값 누수 방지</h2>
    <p><strong>관측값을 입력으로 넣지 않는다.</strong> 관측 유량은 event를 고르거나 나중에 결과를 검증할 때만 쓴다. LSTM 직접 SHAP 계산에 들어가는 것은 기상 입력과 유역 속성이다.</p>
    <p>즉 “정답을 보고 설명하는 분석”이 아니라, 모델이 예측할 때 사용한 입력 신호를 보는 분석으로 둔다.</p>
  </section>

  <section>
    <h2>5. GPU 서버에서 실행할 명령 예시</h2>
    <pre><code>uv run scripts/model/overall/compute_q99_lstm_direct_shap.py \
  --seed 111 \
  --device cuda \
  --quantiles q50 q90 q95 q99 \
  --max-events 120 \
  --background-events 32 \
  --shap-samples 64</code></pre>
    <p class="small">처음에는 seed 111과 작은 event 수로 확인한 뒤, seed 222/444로 확장하는 것이 안전하다.</p>
  </section>

  <section>
    <h2>6. 결과를 어떻게 읽어야 하나</h2>
    <div class="grid">
      <div class="card"><h3>전역 중요도</h3><p>전체 event를 평균했을 때 각 quantile 예측을 많이 움직인 변수를 본다.</p></div>
      <div class="card"><h3>quantile ladder 비교</h3><p>q50에서 q99로 올라갈수록 강수, 습도, 유역 속성의 중요도가 커지는지 비교한다.</p></div>
      <div class="card"><h3>시간 lag 중요도</h3><p>첨두 직전 입력이 중요한지, 며칠 전 누적 조건이 중요한지 quantile별로 확인한다.</p></div>
    </div>
    <p>중요한 제한은 하나다. SHAP 값이 크다는 것은 “모델이 그 입력에 민감했다”는 뜻이지, “현실에서 그 변수가 홍수의 유일한 원인이다”라는 뜻은 아니다.</p>
  </section>
</main>
</body>
</html>
"""

def write_method_html(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(method_html(), encoding="utf-8")


def write_metadata(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Path]:
    output_dir = resolve(args.output_dir)
    tables_dir = output_dir / "tables"
    figures_dir = output_dir / "figures"
    metadata_dir = output_dir / "metadata"
    report_dir = output_dir / "report"
    for path in [tables_dir, figures_dir, metadata_dir, report_dir]:
        path.mkdir(parents=True, exist_ok=True)

    device = torch.device("cpu") if args.smoke else choose_device(args.device)
    tag = "smoke" if args.smoke else f"seed{args.seed}"
    title_suffix = " (smoke test)" if args.smoke else f" (seed {args.seed})"

    if args.smoke:
        model, background, samples = prepare_smoke_inputs(
            args.max_events,
            args.background_events,
            device=device,
            seed=args.random_state,
        )
        run_context = {"mode": "smoke", "model_source": "synthetic_random_model"}
    else:
        run_dir = resolve(args.run_dir) if args.run_dir else REPO_ROOT / "runs/subset_comparison" / _SEED_RUN_DIRS[args.seed]
        checkpoint = resolve(args.checkpoint) if args.checkpoint else run_dir / "model_epoch005.pt"
        scaler_path = resolve(args.scaler) if args.scaler else run_dir / "train_data" / "train_data_scaler.yml"
        if not checkpoint.exists():
            raise FileNotFoundError(f"Model checkpoint not found: {checkpoint}")
        if not scaler_path.exists():
            raise FileNotFoundError(f"Training scaler not found: {scaler_path}")
        model = MinimalQ99LSTM(seq_first=True).to(device)
        model.load_nh_checkpoint(checkpoint)
        model.eval()
        scaler = load_scaler(scaler_path)
        static_df = read_static(resolve(args.static_csv))
        events = read_events(
            resolve(args.event_csv),
            args.seed,
            args.max_events,
            start_date=args.analysis_start_date,
            end_date=args.analysis_end_date,
        )
        samples = prepare_real_inputs(events, static_df, scaler, resolve(args.nc_dir), device=device)
        background_count = min(max(1, args.background_events), samples.dynamic.shape[0])
        rng = np.random.default_rng(args.random_state + int(args.seed))
        if background_count < samples.dynamic.shape[0]:
            background_indices = np.sort(rng.choice(samples.dynamic.shape[0], size=background_count, replace=False))
        else:
            background_indices = np.arange(samples.dynamic.shape[0])
        background = PreparedInputs(
            records=[samples.records[int(idx)] for idx in background_indices],
            dynamic=samples.dynamic[background_indices].clone(),
            static=samples.static[background_indices].clone(),
        )
        run_context = {
            "mode": "real",
            "seed": args.seed,
            "run_dir": relative(run_dir),
            "checkpoint": relative(checkpoint),
            "scaler": relative(scaler_path),
            "event_csv": relative(resolve(args.event_csv)),
            "analysis_start_date": args.analysis_start_date,
            "analysis_end_date": args.analysis_end_date,
            "static_csv": relative(resolve(args.static_csv)),
            "nc_dir": relative(resolve(args.nc_dir)),
        }

    quantiles = list(dict.fromkeys(args.quantiles))
    print(f"Computing direct LSTM SHAP on {device} ({tag}) for {', '.join(quantiles)} …")
    event_frames: list[pd.DataFrame] = []
    lag_frames: list[pd.DataFrame] = []
    figure_outputs: dict[str, str] = {}
    for quantile in quantiles:
        print(f"  - {quantile}", flush=True)
        dyn_values, static_values, predictions = compute_shap_values(
            model,
            background,
            samples,
            quantile=quantile,
            shap_samples=max(1, args.shap_samples),
        )
        event_frames.append(
            build_event_feature_table(quantile, samples.records, dyn_values, static_values, predictions)
        )
        lag_frames.append(build_temporal_lag_table(quantile, dyn_values))

    event_feature = pd.concat(event_frames, ignore_index=True)
    global_feature = build_global_feature_table(event_feature)
    temporal_lag = pd.concat(lag_frames, ignore_index=True)

    event_path = tables_dir / f"quantile_lstm_direct_shap_event_feature_importance_{tag}.csv"
    global_path = tables_dir / f"quantile_lstm_direct_shap_global_feature_importance_{tag}.csv"
    lag_path = tables_dir / f"quantile_lstm_direct_shap_temporal_lag_{tag}.csv"
    event_feature.to_csv(event_path, index=False)
    global_feature.to_csv(global_path, index=False)
    temporal_lag.to_csv(lag_path, index=False)

    for quantile in quantiles:
        global_fig = figures_dir / f"quantile_lstm_direct_shap_global_feature_importance_{quantile}_{tag}.png"
        lag_fig = figures_dir / f"quantile_lstm_direct_shap_temporal_lag_{quantile}_{tag}.png"
        save_global_bar(global_feature[global_feature["quantile"].eq(quantile)], global_fig, quantile, title_suffix)
        save_temporal_plot(temporal_lag[temporal_lag["quantile"].eq(quantile)], lag_fig, quantile, title_suffix)
        figure_outputs[f"global_figure_{quantile}"] = relative(global_fig)
        figure_outputs[f"temporal_figure_{quantile}"] = relative(lag_fig)

    method_path = report_dir / "quantile_lstm_direct_shap_method.html"
    write_method_html(method_path)

    metadata = {
        "script": "scripts/model/overall/compute_q99_lstm_direct_shap.py",
        "interpretation_boundary": "SHAP values explain the trained q50/q90/q95/q99 LSTM outputs, not observed causal flood mechanisms.",
        "leakage_boundary_ko": "관측 유량은 SHAP 입력으로 넣지 않고, event 선택과 사후 검증에만 사용한다.",
        "device": str(device),
        "quantiles": quantiles,
        "max_events_requested": int(args.max_events),
        "analysis_start_date": None if args.smoke else args.analysis_start_date,
        "analysis_end_date": None if args.smoke else args.analysis_end_date,
        "n_sample_events": int(samples.dynamic.shape[0]),
        "n_background_events": int(background.dynamic.shape[0]),
        "shap_samples": int(args.shap_samples),
        "dynamic_features": DYNAMIC_FEATURES,
        "static_features": STATIC_FEATURES,
        "outputs": {
            "event_feature_importance": relative(event_path),
            "global_feature_importance": relative(global_path),
            "temporal_lag": relative(lag_path),
            "method_html": relative(method_path),
            **figure_outputs,
        },
        **run_context,
    }
    metadata_path = metadata_dir / f"quantile_lstm_direct_shap_metadata_{tag}.json"
    write_metadata(metadata_path, metadata)

    print("Wrote direct LSTM SHAP outputs:")
    for label, path in metadata["outputs"].items():
        print(f"  - {label}: {path}")
    return {
        "event": event_path,
        "global": global_path,
        "lag": lag_path,
        "metadata": metadata_path,
        "method_html": method_path,
    }


def main() -> int:
    args = parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
