#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "scipy>=1.13",
#   "xarray>=2024",
#   "netCDF4>=1.7",
#   "matplotlib>=3.9",
# ]
# ///
"""Event-level forcing characteristic → Q99 prediction error correlation.

For each Q99 event (obs >= basin 99th percentile, 2014-2016 test period):
  - Extract forcing window from NC: Rainf total/peak, antecedent 5d Rainf, CAPE, Tair
  - Compute Q99 peak error and under-fraction
  - Spearman correlation across ~3,600 events (85 basins × ~14 events × 3 seeds)

Outputs
-------
output/model_analysis/q99_analysis/causes/tables/q99_event_forcing_drivers.csv   event-level table
output/model_analysis/q99_analysis/causes/tables/q99_event_forcing_correlation.csv
output/model_analysis/q99_analysis/causes/figures/q99_event_forcing_scatter.png
output/model_analysis/q99_analysis/causes/figures/q99_event_forcing_correlation_bar.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from scipy import stats
import xarray as xr

REPO_ROOT = Path(__file__).resolve().parents[3]
REQUIRED_DIR = REPO_ROOT / "output/model_analysis/primary/metrics/data/required_series"
NC_DIR = REPO_ROOT / "data/CAMELSH_generic/drbc_expanded_observed_test/time_series"
OUT_TABLES = REPO_ROOT / "output/model_analysis/q99_analysis/causes/tables"
OUT_FIGS = REPO_ROOT / "output/model_analysis/q99_analysis/causes/figures"
OUT_TABLES.mkdir(parents=True, exist_ok=True)
OUT_FIGS.mkdir(parents=True, exist_ok=True)

OFFICIAL_SEEDS = [111, 222, 444]
EVENT_GAP_H = 72   # hours gap → new event
ANTECEDENT_DAYS = 5

TARGET_METRICS = ["q99_peak_rel_error", "q99_under_frac_event"]
FORCING_FEATURES = [
    "event_total_rainf", "event_peak_rainf_intensity",
    "event_duration_h", "antecedent_rainf_5d",
    "event_mean_cape", "event_max_cape",
    "antecedent_tair_mean",
]

C_POS, C_NEG = "#1f77b4", "#d62728"

# ── NC forcing cache (avoid re-opening files) ────────────────────────────────
_nc_cache: dict[str, xr.Dataset] = {}


def _open_nc(basin: str) -> xr.Dataset | None:
    # NC files use zero-padded 8-digit IDs (e.g. 01414000)
    basin_padded = basin.zfill(8)
    key = basin_padded
    if key not in _nc_cache:
        p = NC_DIR / f"{basin_padded}.nc"
        if not p.exists():
            return None
        _nc_cache[key] = xr.open_dataset(p)
    return _nc_cache[key]


def extract_forcing(
    basin: str, t0: pd.Timestamp, t1: pd.Timestamp
) -> dict:
    """Extract forcing statistics for event window [t0, t1] + antecedent period."""
    ds = _open_nc(basin)
    if ds is None:
        return {}
    try:
        t_pre = t0 - pd.Timedelta(days=ANTECEDENT_DAYS)
        ev = ds.sel(date=slice(str(t0), str(t1)))
        pre = ds.sel(date=slice(str(t_pre), str(t0 - pd.Timedelta(hours=1))))

        rainf = ev["Rainf"].values.astype(float)
        cape = ev["CAPE"].values.astype(float) if "CAPE" in ds else np.array([np.nan])
        pre_rain = pre["Rainf"].values.astype(float) if len(pre["date"]) > 0 else np.array([0.0])
        pre_tair = pre["Tair"].values.astype(float) if "Tair" in ds and len(pre["date"]) > 0 else np.array([np.nan])

        return {
            "event_total_rainf": float(np.nansum(rainf)),
            "event_peak_rainf_intensity": float(np.nanmax(rainf)) if len(rainf) > 0 else np.nan,
            "event_duration_h": int(len(ev["date"])),
            "antecedent_rainf_5d": float(np.nansum(pre_rain)),
            "event_mean_cape": float(np.nanmean(cape)),
            "event_max_cape": float(np.nanmax(cape)) if len(cape) > 0 else np.nan,
            "antecedent_tair_mean": float(np.nanmean(pre_tair)),
        }
    except Exception:
        return {}


def identify_q99_events(
    grp: pd.DataFrame,
) -> list[tuple[pd.Timestamp, pd.Timestamp, pd.Series, pd.Series, pd.Series]]:
    """Return list of (t0, t1, obs_window, q99_window, m1_window) per event."""
    obs = grp["obs"].astype(float)
    obs_valid = obs[obs > 0]
    if len(obs_valid) < 100:
        return []
    thr = float(obs_valid.quantile(0.99))
    mask = obs >= thr
    if mask.sum() < 2:
        return []

    dt = pd.to_datetime(grp["datetime"]).values
    dt_series = pd.Series(dt, index=grp.index)
    hi_idx = grp.index[mask]
    hi_times = dt_series[hi_idx].sort_values()

    events = []
    gaps = hi_times.diff() > pd.Timedelta(hours=EVENT_GAP_H)
    event_id = gaps.cumsum()

    for eid, ev_hi_times in hi_times.groupby(event_id):
        # expand window: from first to last hi-obs timestep
        t0 = ev_hi_times.min()
        t1 = ev_hi_times.max()
        # select full window rows
        win_mask = (dt_series >= t0) & (dt_series <= t1)
        win = grp[win_mask]
        obs_w = win["obs"].astype(float)
        q99_w = win["q99"].astype(float)
        m1_w = win["model1"].astype(float)
        events.append((t0, t1, obs_w, q99_w, m1_w))

    return events


def compute_event_metrics(
    obs: pd.Series, q99: pd.Series, m1: pd.Series
) -> dict:
    """Compute prediction error metrics for one event window."""
    valid = obs > 0
    if valid.sum() < 2 or obs[valid].max() <= 0:
        return {}
    peak_idx = obs[valid].idxmax()
    obs_peak = float(obs[peak_idx])

    return {
        "obs_peak": obs_peak,
        "q99_peak": float(q99[peak_idx]),
        "model1_peak": float(m1[peak_idx]),
        "q99_peak_rel_error": float((q99[peak_idx] - obs_peak) / obs_peak),
        "model1_peak_rel_error": float((m1[peak_idx] - obs_peak) / obs_peak),
        "q99_under_frac_event": float((q99[valid] < obs[valid]).mean()),
        "model1_under_frac_event": float((m1[valid] < obs[valid]).mean()),
        "n_timesteps_event": int(valid.sum()),
    }


# ── Main pipeline ────────────────────────────────────────────────────────────

def build_event_table() -> pd.DataFrame:
    all_rows = []
    for seed in OFFICIAL_SEEDS:
        print(f"[seed {seed}] loading …", flush=True)
        series = pd.read_csv(
            REQUIRED_DIR / f"seed{seed}" / "required_series.csv"
        )
        series["basin"] = series["basin"].astype(str)

        n_basins = series["basin"].nunique()
        print(f"  {n_basins} basins", flush=True)

        for i, (basin, grp) in enumerate(series.groupby("basin")):
            events = identify_q99_events(grp)
            for ev_id, (t0, t1, obs_w, q99_w, m1_w) in enumerate(events):
                row = {"basin": basin, "seed": seed, "event_id": ev_id + 1,
                       "event_start": str(t0), "event_end": str(t1)}
                row.update(compute_event_metrics(obs_w, q99_w, m1_w))
                forcing = extract_forcing(basin, t0, t1)
                row.update(forcing)
                all_rows.append(row)

        print(f"  done — {sum(1 for r in all_rows if r['seed']==seed)} events so far")

    return pd.DataFrame(all_rows)


def spearman_table(df: pd.DataFrame) -> pd.DataFrame:
    records = []
    for feat in FORCING_FEATURES:
        if feat not in df.columns:
            continue
        for target in TARGET_METRICS:
            for seed in OFFICIAL_SEEDS:
                sub = df[df["seed"] == seed][[feat, target]].dropna()
                if len(sub) < 20:
                    continue
                rho, pval = stats.spearmanr(sub[feat], sub[target])
                records.append({
                    "feature": feat, "target": target, "seed": seed,
                    "rho": rho, "pval": pval, "n": len(sub),
                })
    corr = pd.DataFrame(records)
    # stable = 3 seeds same direction
    stable_rows = []
    for (feat, target), grp in corr.groupby(["feature", "target"]):
        if len(grp) < 3:
            continue
        signs = np.sign(grp["rho"].values)
        n_agree = max((signs > 0).sum(), (signs < 0).sum())
        stable_rows.append({
            "feature": feat, "target": target,
            "rho_median": grp["rho"].median(),
            "rho_min": grp["rho"].min(), "rho_max": grp["rho"].max(),
            "pval_median": grp["pval"].median(),
            "n_agree": int(n_agree),
            "stable": n_agree >= 3,
        })
    return pd.DataFrame(stable_rows).sort_values("rho_median", key=abs, ascending=False)


# ── Plots ────────────────────────────────────────────────────────────────────

FEAT_LABELS = {
    "event_total_rainf": "Event total Rainf (mm/h·h)",
    "event_peak_rainf_intensity": "Peak Rainf intensity (mm/h)",
    "event_duration_h": "Event duration (h)",
    "antecedent_rainf_5d": "Antecedent 5-day Rainf (mm)",
    "event_mean_cape": "Mean CAPE (J/kg)",
    "event_max_cape": "Max CAPE (J/kg)",
    "antecedent_tair_mean": "Antecedent Tair (K)",
}


def plot_correlation_bar(corr: pd.DataFrame) -> None:
    stable = corr[corr["stable"]].copy()
    for target in TARGET_METRICS:
        sub = stable[stable["target"] == target].sort_values("rho_median", key=abs, ascending=True)
        if sub.empty:
            continue
        fig, ax = plt.subplots(figsize=(7, 4))
        colors = [C_POS if r > 0 else C_NEG for r in sub["rho_median"]]
        ax.barh([FEAT_LABELS.get(f, f) for f in sub["feature"]], sub["rho_median"], color=colors)
        ax.errorbar(
            sub["rho_median"], range(len(sub)),
            xerr=[sub["rho_median"] - sub["rho_min"], sub["rho_max"] - sub["rho_median"]],
            fmt="none", color="gray", linewidth=1, capsize=3,
        )
        ax.axvline(0, color="black", linewidth=0.8)
        ax.set_xlabel("Spearman ρ (seed median, 3-seed stable)", fontsize=10)
        ax.set_title(f"Event forcing drivers of {target}\n(~3,600 events, 85 basins)", fontsize=10)
        ax.legend(handles=[
            mpatches.Patch(color=C_POS, label="Higher → larger error"),
            mpatches.Patch(color=C_NEG, label="Higher → smaller error"),
        ], fontsize=8)
        fig.tight_layout()
        fname = f"q99_event_forcing_correlation_bar_{target}.png"
        fig.savefig(OUT_FIGS / fname, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  Saved: {fname}")


def plot_scatter_top(df: pd.DataFrame, corr: pd.DataFrame) -> None:
    # seed111 only for scatter clarity
    sub = df[df["seed"] == 111].copy()
    stable = corr[(corr["stable"]) & (corr["target"] == "q99_peak_rel_error")]
    top_feats = stable.head(4)["feature"].tolist()

    if not top_feats:
        print("  [WARN] no stable features for scatter")
        return

    fig, axes = plt.subplots(1, len(top_feats), figsize=(4.5 * len(top_feats), 4.5))
    if len(top_feats) == 1:
        axes = [axes]

    for ax, feat in zip(axes, top_feats):
        x = sub[feat].astype(float)
        y = sub["q99_peak_rel_error"].astype(float)
        valid = x.notna() & y.notna() & x.between(*np.nanpercentile(x.dropna(), [1, 99]))
        ax.scatter(x[valid], y[valid], alpha=0.3, s=15, color=C_POS)
        ax.axhline(0, color="gray", linewidth=0.7, linestyle="--")
        rho, _ = stats.spearmanr(x[valid], y[valid])
        ax.set_xlabel(FEAT_LABELS.get(feat, feat), fontsize=9)
        ax.set_ylabel("q99_peak_rel_error" if ax is axes[0] else "", fontsize=9)
        ax.set_title(f"ρ = {rho:.3f}", fontsize=10)

    fig.suptitle("Event forcing vs Q99 peak relative error (seed111, 1,222 events)", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT_FIGS / "q99_event_forcing_scatter.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved: q99_event_forcing_scatter.png")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    event_csv = OUT_TABLES / "q99_event_forcing_drivers.csv"
    corr_csv = OUT_TABLES / "q99_event_forcing_correlation.csv"

    print("── Building event-level table …")
    df = build_event_table()
    df.to_csv(event_csv, index=False)
    print(f"Saved: {event_csv}  ({len(df)} rows)")

    print("\n── Spearman correlation …")
    corr = spearman_table(df)
    corr.to_csv(corr_csv, index=False)
    print(f"Saved: {corr_csv}")

    for target in TARGET_METRICS:
        sub = corr[corr["target"] == target].head(7)
        print(f"\n  [{target}]:")
        print(sub[["feature", "rho_median", "pval_median", "stable"]].to_string(index=False))

    print("\n── Plots …")
    plot_correlation_bar(corr)
    plot_scatter_top(df, corr)

    print("\nDone.")


if __name__ == "__main__":
    main()
