# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas", "numpy", "matplotlib", "scipy", "xarray", "netCDF4"]
# ///
"""
M3 SG onset 기반 rising limb figure 2종 생성.
  1. rising_limb_scatter.png  — rise_slope vs obs_class scatter + boxplot
  2. rising_limb_example.png  — 대조 수문곡선 (long vs short rising limb)
출력: output/model_analysis/primary/metrics/figures/
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import xarray as xr
from scipy import stats
from scipy.signal import savgol_filter

matplotlib.rcParams.update({
    "figure.facecolor": "#f8f9fa",
    "font.size": 10,
    "font.family": "DejaVu Sans",
})

ROOT = Path(__file__).resolve().parents[3]
CSV  = ROOT / "output/model_analysis/band_signal/method_compare/rising_limb_m3_spearman.csv"
NC   = ROOT / "basins/CAMELSH_data/hourly_observed/netcdf/0142400103_hourly.nc"
OUT  = ROOT / "output/model_analysis/primary/metrics/figures"
OUT.mkdir(parents=True, exist_ok=True)

BAND_ORDER  = ["below_q50", "q50_to_q90", "q90_to_q95", "q95_to_q99", "above_q99"]
BAND_COLORS = ["#3498db", "#2ecc71", "#f39c12", "#e74c3c", "#8e44ad"]


def load_obs(basin_id: str = "0142400103") -> pd.Series:
    nc_path = ROOT / f"basins/CAMELSH_data/hourly_observed/netcdf/{basin_id}_hourly.nc"
    ds = xr.open_dataset(nc_path)
    q  = ds["streamflow"].to_series().squeeze()
    if isinstance(q.index, pd.MultiIndex):
        q = q.reset_index(level=0, drop=True)
    q.index = pd.to_datetime(q.index)
    ds.close()
    return q.sort_index()


# ── Figure 1: scatter + boxplot ───────────────────────────────────────────────
def make_scatter_png(df: pd.DataFrame):
    col = "rise_slope_m3"
    sub = df[[col, "obs_class_ordinal", "obs_class"]].dropna()
    sub = sub[np.isfinite(sub[col]) & (sub[col] > 0)]
    r, p = stats.spearmanr(sub[col], sub["obs_class_ordinal"])
    n    = len(sub)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.patch.set_facecolor("#f8f9fa")

    # 왼쪽: jittered scatter (log x)
    ax = axes[0]
    ax.set_facecolor("#f8f9fa")
    rng    = np.random.default_rng(42)
    jitter = rng.uniform(-0.25, 0.25, len(sub))
    for cls, col_hex in zip(BAND_ORDER, BAND_COLORS):
        mask = sub["obs_class"] == cls
        ax.scatter(
            sub.loc[mask, col].clip(lower=1e-3),
            sub.loc[mask, "obs_class_ordinal"] + jitter[mask.values],
            color=col_hex, alpha=0.45, s=18, edgecolors="none", label=cls,
        )
    ax.set_xscale("log")
    ax.set_xlabel("Rise slope [m³/s/h] (log scale)", fontsize=11)
    ax.set_ylabel("obs_class (0=below_q50 → 4=above_q99)", fontsize=11)
    ax.set_title(
        f"Rise slope vs obs_class  (M3 SG onset)\n"
        f"Spearman r = {r:+.3f}   p < 0.001   n = {n:,}",
        fontsize=11,
    )
    ax.set_yticks(range(5))
    ax.set_yticklabels(BAND_ORDER, fontsize=8)
    legend_patches = [mpatches.Patch(color=c, label=l) for c, l in zip(BAND_COLORS, BAND_ORDER)]
    ax.legend(handles=legend_patches, fontsize=8, loc="upper left")
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.grid(True, alpha=0.25)

    # 오른쪽: boxplot per obs_class
    ax2 = axes[1]
    ax2.set_facecolor("#f8f9fa")
    data_by_cls = []
    for cls in BAND_ORDER:
        vals = sub.loc[sub["obs_class"] == cls, col].dropna()
        vals = vals[vals > 0]
        data_by_cls.append(
            np.log10(vals.clip(lower=1e-3)).values if len(vals) > 0 else np.array([np.nan])
        )
    bp = ax2.boxplot(
        data_by_cls, patch_artist=True, notch=False, showfliers=False,
        flierprops=dict(marker=".", markersize=3, alpha=0.3),
    )
    for patch, col_hex in zip(bp["boxes"], BAND_COLORS):
        patch.set_facecolor(col_hex); patch.set_alpha(0.7)
    ax2.set_xticklabels(BAND_ORDER, fontsize=8, rotation=15)
    ax2.set_xlabel("obs_class", fontsize=11)
    ax2.set_ylabel("log10(rise slope [m³/s/h])", fontsize=11)
    ax2.set_title("Rise slope distribution per obs_class  (M3 SG onset)", fontsize=11)
    ax2.spines["top"].set_visible(False); ax2.spines["right"].set_visible(False)
    ax2.grid(True, alpha=0.25, axis="y")

    plt.tight_layout()
    out = OUT / "rising_limb_scatter.png"
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


# ── Figure 2: example hydrographs ────────────────────────────────────────────
def m3_onset_time(q: pd.Series, ref_time: pd.Timestamp, peak_time: pd.Timestamp,
                  window: int = 13, poly: int = 3) -> pd.Timestamp:
    """M3 SG onset: sign-change in smoothed dQ/dt (negative → positive)."""
    search = q[ref_time:peak_time]
    if len(search) < window + 2:
        return ref_time
    sg = savgol_filter(search.values, window_length=min(window, len(search) | 1),
                       polyorder=poly, deriv=1)
    for i in range(len(sg) - 1, 0, -1):
        if sg[i] > 0 and sg[i - 1] <= 0:
            return search.index[i]
    return ref_time


def plot_event(ax, q: pd.Series, onset: pd.Timestamp, peak: pd.Timestamp,
               obs_class: str, color: str, window_h: int = 72):
    t0  = onset - pd.Timedelta(hours=12)
    t1  = peak  + pd.Timedelta(hours=12)
    seg = q[t0:t1]
    rising_h = (peak - onset).total_seconds() / 3600

    ax.fill_between(seg.index, seg.values, alpha=0.12, color=color)
    ax.plot(seg.index, seg.values, color=color, lw=1.8, label="Observed streamflow")
    ax.axvline(onset, color="#e74c3c", lw=1.6, ls="--", label=f"M3 onset (RT={rising_h:.0f}h)")
    ax.axvline(peak,  color="#2c3e50", lw=1.4, ls=":",  label="Peak")
    ax.scatter([onset], [q.loc[onset]], color="#e74c3c", zorder=5, s=60)
    ax.scatter([peak],  [q.loc[peak]],  color="#2c3e50", zorder=5, s=60)

    ax.set_ylabel("Streamflow [m³/s]", fontsize=10)
    ax.set_title(
        f"{obs_class}  |  Peak: {peak.strftime('%Y-%m-%d %H:%M')}\n"
        f"Rising time: {rising_h:.0f} h   Peak Q: {q.loc[peak]:.1f} m³/s",
        fontsize=10,
    )
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%m/%d\n%Hh"))
    ax.legend(fontsize=8, loc="upper left")
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.grid(True, alpha=0.2)


def make_example_png(df: pd.DataFrame, q: pd.Series):
    # 대조 이벤트 선택: basin 0142400103, seed=111
    sub = df[(df["basin_id"] == "0142400103") & (df["seed"] == 111)].copy()
    sub["peak_time"]  = pd.to_datetime(sub["peak_time"])
    sub["onset_time"] = pd.to_datetime(sub["onset_time"])

    # 긴 상승 경사 (above_q99, 최대 rising_hours)
    long_row  = sub[sub["obs_class"] == "above_q99"].sort_values("rising_hours").iloc[-1]
    # 짧은 상승 경사 (above_q99, 최소 rising_hours, 최소 5h)
    short_row = sub[(sub["obs_class"] == "above_q99") & (sub["rising_hours"] >= 5)] \
                    .sort_values("rising_hours").iloc[0]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.patch.set_facecolor("#f8f9fa")
    fig.suptitle(
        "Rising limb example: M3 SG onset  |  Basin 0142400103 (above_q99 events)",
        fontsize=12, fontweight="bold",
    )

    for ax, row, color in zip(
        axes,
        [long_row, short_row],
        ["#8e44ad", "#e67e22"],
    ):
        ax.set_facecolor("#f8f9fa")
        plot_event(ax, q,
                   onset=row["onset_time"], peak=row["peak_time"],
                   obs_class=row["obs_class"], color=color)

    axes[0].set_title("Long rising limb\n" + axes[0].get_title(), fontsize=10)
    axes[1].set_title("Short rising limb\n" + axes[1].get_title(), fontsize=10)

    plt.tight_layout()
    out = OUT / "rising_limb_example.png"
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


if __name__ == "__main__":
    df = pd.read_csv(CSV)
    df["basin_id"] = df["basin_id"].astype(str).str.zfill(10)

    q  = load_obs("0142400103")

    make_scatter_png(df)
    make_example_png(df, q)
    print("Done.")
