#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "torch>=2.0",
#   "xarray>=2024",
#   "netCDF4>=1.7",
#   "matplotlib>=3.9",
#   "scipy>=1.13",
#   "ruamel.yaml>=0.18",
# ]
# ///
"""Gradient-based attribution of Q99 LSTM predictions at extreme flow events.

For each Q99 extreme event (obs >= basin 99th pct, test period 2014-2016):
  - Extract 336h lookback window of forcing from NC files
  - Normalize with training scaler
  - Forward pass through model2 (CudaLSTM + quantile head, epoch005)
  - Compute gradient of q99 output at event peak w.r.t. dynamic inputs
  - Attribute as |gradient| x |input| (GradientInput)

Usage
-----
uv run compute_q99_lstm_attribution.py [--seed SEED]
Defaults to seed 111. Pass --seed 222 or --seed 444 for other seeds.

Outputs
-------
output/model_analysis/q99_analysis/tables/q99_lstm_attribution_seed{SEED}.csv
output/model_analysis/q99_analysis/figures/q99_lstm_feature_importance_seed{SEED}.png
output/model_analysis/q99_analysis/figures/q99_lstm_temporal_lag_seed{SEED}.png
output/model_analysis/q99_analysis/figures/q99_lstm_attribution_stratified_seed{SEED}.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import xarray as xr
from ruamel.yaml import YAML

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "vendor" / "neuralhydrology"))

RUN_DIR = (
    REPO_ROOT
    / "runs/subset_comparison"
    / "camelsh_hourly_model2_drbc_holdout_subset300_seed111_1904_232450"
)
CKPT_PATH = RUN_DIR / "model_epoch005.pt"
SCALER_PATH = RUN_DIR / "train_data" / "train_data_scaler.yml"

STATIC_PATH = (
    REPO_ROOT
    / "output/basin/drbc/analysis/basin_attributes/tables"
    / "drbc_selected_static_attributes_full.csv"
)
NC_DIR = REPO_ROOT / "data/CAMELSH_generic/drbc_expanded_observed_test/time_series"
EVENT_CSV = REPO_ROOT / "output/model_analysis/q99_analysis/tables/q99_event_forcing_drivers.csv"

OUT_TABLES = REPO_ROOT / "output/model_analysis/q99_analysis/tables"
OUT_FIGS = REPO_ROOT / "output/model_analysis/q99_analysis/figures"
OUT_TABLES.mkdir(parents=True, exist_ok=True)
OUT_FIGS.mkdir(parents=True, exist_ok=True)

DYNAMIC_FEATURES = [
    "Rainf", "Tair", "PotEvap", "SWdown", "Qair",
    "PSurf", "Wind_E", "Wind_N", "LWdown", "CAPE", "CRainf_frac",
]
STATIC_FEATURES = [
    "area", "slope", "aridity", "snow_fraction",
    "soil_depth", "permeability", "forest_fraction", "baseflow_index",
]
N_DYN = len(DYNAMIC_FEATURES)   # 11
N_STA = len(STATIC_FEATURES)    # 8
SEQ_LEN = 336
HIDDEN_SIZE = 128
N_QUANTILES = 4   # [0.5, 0.9, 0.95, 0.99]
Q99_IDX = 3       # index of 0.99 quantile in output

_SEED_RUN_DIRS = {
    111: "camelsh_hourly_model2_drbc_holdout_subset300_seed111_1904_232450",
    222: "camelsh_hourly_model2_drbc_holdout_subset300_seed222_2204_160730",
    444: "camelsh_hourly_model2_drbc_holdout_subset300_seed444_2504_065913",
}


def _parse_args() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=111, choices=[111, 222, 444])
    return parser.parse_args().seed

FEAT_LABELS = {
    "Rainf": "Rainfall (Rainf)",
    "Tair": "Air temp (Tair)",
    "PotEvap": "Pot. evap (PotEvap)",
    "SWdown": "SW radiation (SWdown)",
    "Qair": "Specific humidity (Qair)",
    "PSurf": "Surface pressure (PSurf)",
    "Wind_E": "Wind E (Wind_E)",
    "Wind_N": "Wind N (Wind_N)",
    "LWdown": "LW radiation (LWdown)",
    "CAPE": "CAPE",
    "CRainf_frac": "Conv. rain frac (CRainf_frac)",
}

# ── Minimal CudaLSTM reconstruction (no NH dependency beyond torch) ──────────

class QuantileHead(nn.Module):
    def __init__(self, n_in: int, n_quantiles: int):
        super().__init__()
        self._n_quantiles = n_quantiles
        self._projection = nn.Linear(n_in, n_quantiles)
        self._softplus = nn.Softplus()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: [batch, hidden] → quantiles: [batch, n_quantiles]"""
        raw = self._projection(x)                         # [batch, n_q]
        base = raw[..., :1]
        increments = self._softplus(raw[..., 1:])
        quantiles = torch.cat(
            [base, base + torch.cumsum(increments, dim=-1)], dim=-1
        )
        return quantiles


class MinimalQ99LSTM(nn.Module):
    """Stripped CudaLSTM: no embeddings, static appended at each timestep."""

    def __init__(self):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=N_DYN + N_STA,
            hidden_size=HIDDEN_SIZE,
            batch_first=False,
        )
        self.head = QuantileHead(n_in=HIDDEN_SIZE, n_quantiles=N_QUANTILES)

    def load_nh_checkpoint(self, ckpt_path: Path) -> None:
        state = torch.load(ckpt_path, map_location="cpu", weights_only=True)
        self.load_state_dict(state)

    def forward(
        self,
        x_d: torch.Tensor,  # [seq, batch, N_DYN]
        x_s: torch.Tensor,  # [batch, N_STA]
    ) -> torch.Tensor:
        """Returns q99 prediction at final timestep: [batch]"""
        # broadcast static to each timestep
        x_s_exp = x_s.unsqueeze(0).expand(x_d.shape[0], -1, -1)  # [seq, batch, N_STA]
        x = torch.cat([x_d, x_s_exp], dim=-1)                     # [seq, batch, N_DYN+N_STA]

        lstm_out, _ = self.lstm(x)   # [seq, batch, hidden]
        last_h = lstm_out[-1]        # [batch, hidden]
        quantiles = self.head(last_h)  # [batch, N_Q]
        return quantiles[:, Q99_IDX]   # [batch]  q99


# ── Scaler ────────────────────────────────────────────────────────────────────

def load_scaler(path: Path) -> dict:
    yaml = YAML(typ="safe")
    with path.open() as f:
        raw = yaml.load(f)
    attr_mean = pd.Series(raw["attribute_means"])
    attr_std = pd.Series(raw["attribute_stds"])
    # xarray_feature_center / scale store dynamic feature normalization
    center = {k: v["data"] for k, v in raw["xarray_feature_center"]["data_vars"].items()}
    scale = {k: v["data"] for k, v in raw["xarray_feature_scale"]["data_vars"].items()}
    return {"attr_mean": attr_mean, "attr_std": attr_std, "center": center, "scale": scale}


def normalize_dynamic(arr: np.ndarray, feat: str, scaler: dict) -> np.ndarray:
    c = scaler["center"].get(feat, 0.0)
    s = scaler["scale"].get(feat, 1.0)
    if s == 0:
        s = 1.0
    return (arr - c) / s


def normalize_static(val: float, feat: str, scaler: dict) -> float:
    m = scaler["attr_mean"].get(feat, 0.0)
    s = scaler["attr_std"].get(feat, 1.0)
    if s == 0:
        s = 1.0
    return (val - m) / s


# ── NC forcing cache ──────────────────────────────────────────────────────────

_nc_cache: dict[str, xr.Dataset] = {}


def _open_nc(basin: str) -> xr.Dataset | None:
    basin_padded = basin.zfill(8)
    if basin_padded not in _nc_cache:
        p = NC_DIR / f"{basin_padded}.nc"
        if not p.exists():
            return None
        _nc_cache[basin_padded] = xr.open_dataset(p)
    return _nc_cache[basin_padded]


def extract_window(
    basin: str,
    peak_time: pd.Timestamp,
    scaler: dict,
) -> np.ndarray | None:
    """Extract normalized dynamic input window [SEQ_LEN, N_DYN] ending at peak_time."""
    ds = _open_nc(basin)
    if ds is None:
        return None

    t_start = peak_time - pd.Timedelta(hours=SEQ_LEN - 1)
    sub = ds.sel(date=slice(str(t_start), str(peak_time)))
    dates_in = pd.to_datetime(sub["date"].values)

    if len(dates_in) == 0:
        return None

    window = np.full((SEQ_LEN, N_DYN), np.nan, dtype=np.float32)
    # align to the end of the window (peak at SEQ_LEN-1)
    offset = SEQ_LEN - len(dates_in)
    for fi, feat in enumerate(DYNAMIC_FEATURES):
        if feat not in ds:
            continue
        vals = sub[feat].values.astype(np.float32).flatten()
        normed = normalize_dynamic(vals, feat, scaler).astype(np.float32)
        window[offset: offset + len(normed), fi] = normed

    # fill NaN with 0 (same as NH training)
    window = np.nan_to_num(window, nan=0.0)
    return window


# ── Attribution loop ──────────────────────────────────────────────────────────

def run_attribution(
    model: MinimalQ99LSTM,
    events: pd.DataFrame,
    static_df: pd.DataFrame,
    scaler: dict,
) -> pd.DataFrame:
    """Compute GradientInput attribution for each event.

    Returns DataFrame with columns:
        basin, event_id, event_peak, q99_peak_rel_error, q99_under_frac_event,
        {feat}_attr for each dynamic feature,
        {feat}_lag_{i} for lag profiles (sampled every 24h from peak).
    """
    model.eval()
    records = []
    skipped = 0

    # index static by basin
    sta_idx = static_df.set_index("basin")

    total = len(events)
    for idx, row in events.iterrows():
        if idx % 100 == 0:
            print(f"  [{idx}/{total}]", flush=True)

        basin = str(row["basin"])
        event_end = pd.Timestamp(row["event_end"])

        # find peak time from event window (use event_end as proxy for peak)
        peak_time = event_end

        window = extract_window(basin, peak_time, scaler)
        if window is None:
            skipped += 1
            continue

        # static features
        if basin.zfill(8) not in sta_idx.index and basin not in sta_idx.index:
            skipped += 1
            continue

        bkey = basin.zfill(8) if basin.zfill(8) in sta_idx.index else basin
        try:
            sta_row = sta_idx.loc[bkey]
        except KeyError:
            skipped += 1
            continue

        x_s_raw = np.array(
            [float(sta_row.get(f, 0.0)) for f in STATIC_FEATURES], dtype=np.float32
        )
        x_s_norm = np.array(
            [normalize_static(float(sta_row.get(f, scaler["attr_mean"].get(f, 0.0))), f, scaler)
             for f in STATIC_FEATURES],
            dtype=np.float32,
        )
        x_s_norm = np.nan_to_num(x_s_norm, nan=0.0)

        # build tensors
        x_d_full = torch.from_numpy(window).unsqueeze(1)  # [seq, 1, N_DYN]
        x_d_full.requires_grad_(True)
        x_s = torch.from_numpy(x_s_norm).unsqueeze(0)    # [1, N_STA]

        # forward
        q99_out = model(x_d_full, x_s)  # [1]
        q99_scalar = q99_out.squeeze()

        # backward
        q99_scalar.backward()

        with torch.no_grad():
            grad = x_d_full.grad.squeeze(1).numpy()   # [seq, N_DYN]
            inp = window                                # [seq, N_DYN]
            attr = np.abs(grad * inp)                  # GradientInput

        # feature-level: mean over seq
        feat_attr = attr.mean(axis=0)  # [N_DYN]

        rec = {
            "basin": basin,
            "event_id": row.get("event_id", idx),
            "event_end": str(peak_time),
            "q99_peak_rel_error": row.get("q99_peak_rel_error", np.nan),
            "q99_under_frac_event": row.get("q99_under_frac_event", np.nan),
            "obs_peak": row.get("obs_peak", np.nan),
        }
        for fi, feat in enumerate(DYNAMIC_FEATURES):
            rec[f"{feat}_attr"] = float(feat_attr[fi])

        # lag profile: attribution at each 24h lag from peak (lag0 = peak timestep)
        # sample at lags 0, 24, 48, 72, 96, 120, 168 (in hours back from peak)
        lags_h = [0, 24, 48, 72, 96, 120, 168, 240, 336]
        for lag in lags_h:
            t_idx = SEQ_LEN - 1 - lag
            if t_idx < 0:
                for feat in DYNAMIC_FEATURES:
                    rec[f"{feat}_lag{lag}h"] = np.nan
            else:
                for fi, feat in enumerate(DYNAMIC_FEATURES):
                    rec[f"{feat}_lag{lag}h"] = float(attr[t_idx, fi])

        records.append(rec)

    print(f"  Processed {len(records)} events, skipped {skipped}")
    return pd.DataFrame(records)


# ── Plots ─────────────────────────────────────────────────────────────────────

C_MAIN = "#1f77b4"
C_UNDER = "#d62728"
C_OVER = "#2ca02c"


def plot_feature_importance(df: pd.DataFrame, seed: int) -> None:
    attr_cols = [f"{f}_attr" for f in DYNAMIC_FEATURES]
    means = df[attr_cols].mean()
    stds = df[attr_cols].std()
    labels = [FEAT_LABELS[f] for f in DYNAMIC_FEATURES]

    order = means.values.argsort()
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(
        [labels[i] for i in order],
        means.values[order],
        color=C_MAIN, alpha=0.8,
    )
    ax.errorbar(
        means.values[order],
        range(len(order)),
        xerr=stds.values[order],
        fmt="none", color="gray", linewidth=1, capsize=3,
    )
    ax.set_xlabel("Mean |gradient × input| (GradientInput attribution)", fontsize=10)
    ax.set_title(
        f"LSTM input feature importance for Q99 predictions\n"
        f"(seed{seed}, epoch005, {len(df)} events, GradientInput)",
        fontsize=10,
    )
    fig.tight_layout()
    out = OUT_FIGS / f"q99_lstm_feature_importance_seed{seed}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out.name}")


def plot_temporal_lag(df: pd.DataFrame, seed: int) -> None:
    lags_h = [0, 24, 48, 72, 96, 120, 168, 240, 336]
    top_feats = ["Rainf", "CAPE", "Tair", "PotEvap"]

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = plt.cm.tab10(np.linspace(0, 0.6, len(top_feats)))

    for feat, col in zip(top_feats, colors):
        lag_cols = [f"{feat}_lag{lag}h" for lag in lags_h]
        avail = [c for c in lag_cols if c in df.columns]
        means = df[avail].mean().values
        ax.plot(lags_h[:len(means)], means, marker="o", label=FEAT_LABELS[feat], color=col)

    ax.set_xlabel("Hours before event peak", fontsize=10)
    ax.set_ylabel("Mean |gradient × input|", fontsize=10)
    ax.set_title(f"Temporal sensitivity: how far back LSTM looks for Q99 peak (seed{seed})", fontsize=10)
    ax.legend(fontsize=9)
    ax.invert_xaxis()
    fig.tight_layout()
    out = OUT_FIGS / f"q99_lstm_temporal_lag_seed{seed}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out.name}")


def plot_stratified(df: pd.DataFrame, seed: int) -> None:
    """Attribution: underestimation events vs overestimation events."""
    attr_cols = [f"{f}_attr" for f in DYNAMIC_FEATURES]
    labels = [FEAT_LABELS[f] for f in DYNAMIC_FEATURES]

    under = df[df["q99_under_frac_event"] >= 0.5][attr_cols]
    over = df[df["q99_under_frac_event"] < 0.5][attr_cols]

    if under.empty or over.empty:
        print("  [WARN] insufficient events for stratified plot")
        return

    x = np.arange(len(DYNAMIC_FEATURES))
    width = 0.35
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x - width / 2, under.mean().values, width, label=f"Underest. (n={len(under)})", color=C_UNDER, alpha=0.8)
    ax.bar(x + width / 2, over.mean().values, width, label=f"Overest. (n={len(over)})", color=C_OVER, alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Mean |gradient × input|", fontsize=10)
    ax.set_title(
        f"LSTM feature attribution: underestimation vs overestimation events (seed{seed})\n"
        "(q99_under_frac_event >= 0.5 = underestimation)",
        fontsize=10,
    )
    ax.legend(fontsize=9)
    fig.tight_layout()
    out = OUT_FIGS / f"q99_lstm_attribution_stratified_seed{seed}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out.name}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    seed = _parse_args()
    run_dir = REPO_ROOT / "runs/subset_comparison" / _SEED_RUN_DIRS[seed]
    ckpt_path = run_dir / "model_epoch005.pt"
    scaler_path = run_dir / "train_data" / "train_data_scaler.yml"

    # Load model
    print(f"── Loading model (seed{seed}) …")
    model = MinimalQ99LSTM()
    model.load_nh_checkpoint(ckpt_path)
    model.eval()
    print(f"  Checkpoint: {ckpt_path.name}")

    # Load scaler
    print("── Loading scaler …")
    scaler = load_scaler(scaler_path)
    print(f"  Dynamic center keys: {list(scaler['center'].keys())[:4]} …")

    # Load static attributes
    print("── Loading static attributes …")
    static_df = pd.read_csv(STATIC_PATH)
    if "gauge_id" in static_df.columns:
        static_df = static_df.rename(columns={"gauge_id": "basin"})
    static_df["basin"] = static_df["basin"].astype(str).str.zfill(8)

    # Load event table
    print("── Loading event table …")
    events_all = pd.read_csv(EVENT_CSV)
    events = events_all[events_all["seed"] == seed].copy()
    events["basin"] = events["basin"].astype(str)
    print(f"  {len(events)} events (seed{seed})")

    # Attribution
    print(f"── Computing gradient attribution ({len(events)} events) …")
    attr_df = run_attribution(model, events, static_df, scaler)
    out_csv = OUT_TABLES / f"q99_lstm_attribution_seed{seed}.csv"
    attr_df.to_csv(out_csv, index=False)
    print(f"Saved: {out_csv.name}  ({len(attr_df)} rows)")

    # Summary
    attr_cols = [f"{f}_attr" for f in DYNAMIC_FEATURES]
    print("\n── Feature attribution summary (mean |grad×inp|) ──")
    summary = attr_df[attr_cols].mean().sort_values(ascending=False)
    summary.index = [c.replace("_attr", "") for c in summary.index]
    print(summary.to_string())

    # Plots
    print("\n── Plots …")
    plot_feature_importance(attr_df, seed)
    plot_temporal_lag(attr_df, seed)
    plot_stratified(attr_df, seed)

    print("\nDone.")


if __name__ == "__main__":
    main()
