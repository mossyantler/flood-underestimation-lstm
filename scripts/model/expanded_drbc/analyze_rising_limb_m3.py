#!/usr/bin/env python3
# /// script
# dependencies = ["xarray", "pandas", "numpy", "scipy", "matplotlib", "netCDF4"]
# ///
"""
Basin 0142400103 — Method 3 (Savitzky-Golay) 기준 Rising Limb 상승경사 분석

출력: output/model_analysis/band_signal/method_compare/rising_limb_m3_analysis.html
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import xarray as xr
from scipy.signal import savgol_filter
from scipy import stats

# ── 경로 ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[3]
NC_PATH = ROOT / "basins/CAMELSH_data/hourly_observed/netcdf/0142400103_hourly.nc"
OUTPUT_DIR = ROOT / "output/model_analysis/band_signal/method_compare"
OUTPUT_HTML = OUTPUT_DIR / "rising_limb_m3_analysis.html"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

GAUGE_ID = "0142400103"
Q99_QUANTILE = 0.99
MIN_GAP_HOURS = 24
MAX_LOOKBACK_HOURS = 240
SG_WINDOW = 13
SG_POLY = 3
SMOOTH_HOURS = 6   # fallback rolling

MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun",
               "Jul","Aug","Sep","Oct","Nov","Dec"]
SEASON_MAP = {12:"Winter",1:"Winter",2:"Winter",
              3:"Spring",4:"Spring",5:"Spring",
              6:"Summer",7:"Summer",8:"Summer",
              9:"Fall",10:"Fall",11:"Fall"}
SEASON_COLORS = {"Winter":"#3498db","Spring":"#2ecc71",
                 "Summer":"#e74c3c","Fall":"#e67e22"}


# ── 데이터 클래스 ──────────────────────────────────────────────────────────────
@dataclass
class EventCluster:
    first_segment_start: pd.Timestamp
    last_segment_end: pd.Timestamp
    peak_time: pd.Timestamp
    peak_value: float


@dataclass
class RisingLimbMetrics:
    event_id: int
    peak_time: pd.Timestamp
    peak_q: float
    onset_time: pd.Timestamp
    onset_q: float
    rising_hours: float
    rising_rate: float          # (peak_q - onset_q) / rising_hours
    log_rising_rate: float
    q_ratio: float              # peak_q / onset_q
    month: int
    season: str
    year: int
    fallback_used: bool         # M3이 fallback(M1)으로 갔는지


# ── 데이터 로드 ────────────────────────────────────────────────────────────────
def load_streamflow() -> pd.Series:
    ds = xr.open_dataset(NC_PATH)
    q = ds["streamflow"].to_series().dropna()
    q.index = pd.to_datetime(q.index)
    return q.sort_index()


def compute_q99(q: pd.Series) -> float:
    return float(np.nanquantile(q.values, Q99_QUANTILE))


# ── 클러스터 감지 ─────────────────────────────────────────────────────────────
def detect_clusters(q: pd.Series, threshold: float) -> list[EventCluster]:
    above = q[q > threshold]
    if above.empty:
        return []
    clusters: list[EventCluster] = []
    seg_start = above.index[0]
    seg_end = above.index[0]
    peak_t = above.index[0]
    peak_v = float(above.iloc[0])
    for i in range(1, len(above)):
        gap_h = (above.index[i] - seg_end).total_seconds() / 3600
        if gap_h <= MIN_GAP_HOURS:
            seg_end = above.index[i]
            if float(above.iloc[i]) > peak_v:
                peak_v = float(above.iloc[i])
                peak_t = above.index[i]
        else:
            clusters.append(EventCluster(seg_start, seg_end, peak_t, peak_v))
            seg_start = above.index[i]
            seg_end = above.index[i]
            peak_t = above.index[i]
            peak_v = float(above.iloc[i])
    clusters.append(EventCluster(seg_start, seg_end, peak_t, peak_v))
    return clusters


# ── M1 fallback ───────────────────────────────────────────────────────────────
def method1_threshold(q: pd.Series, ref_time: pd.Timestamp, threshold: float) -> pd.Timestamp:
    prefix = q.loc[:ref_time].iloc[:-1]
    candidates = prefix[prefix.notna() & (prefix < threshold)]
    if not candidates.empty:
        return candidates.index[-1]
    valid = q.loc[:ref_time].dropna()
    return valid.index[0] if not valid.empty else ref_time


# ── M3: Savitzky-Golay onset ─────────────────────────────────────────────────
def method3_onset(
    q: pd.Series,
    ref_time: pd.Timestamp,
    peak_time: pd.Timestamp,
    threshold: float,
) -> tuple[pd.Timestamp, bool]:
    """Returns (onset_time, fallback_used)."""
    fallback = method1_threshold(q, ref_time, threshold)
    lb_start = ref_time - pd.Timedelta(hours=MAX_LOOKBACK_HOURS)
    window = q.loc[lb_start:ref_time].dropna()

    win = min(SG_WINDOW, len(window) - 1)
    if win % 2 == 0:
        win -= 1
    if win < SG_POLY + 2 or len(window) < win:
        # try rolling mean fallback before M1
        if len(window) >= SMOOTH_HOURS * 2:
            smoothed = window.rolling(SMOOTH_HOURS, center=True, min_periods=1).mean()
            dq = smoothed.diff()
            signs = np.sign(dq.fillna(0).values)
            for i in range(len(signs) - 2, 0, -1):
                if signs[i] <= 0 and signs[i + 1] > 0:
                    t = window.index[i]
                    seg = q.loc[t:peak_time]
                    if len(seg) > 1 and float(seg.iloc[-1]) > float(window.iloc[i]) * 1.5:
                        return t, True   # rolling fallback (marked)
        return fallback, True

    vals = window.values.astype(float)
    dq_vals = savgol_filter(vals, win, SG_POLY, deriv=1)
    signs = np.sign(dq_vals)

    for i in range(len(signs) - 2, 0, -1):
        if signs[i] <= 0 and signs[i + 1] > 0:
            t = window.index[i]
            seg = q.loc[t:peak_time]
            if len(seg) > 1 and float(seg.iloc[-1]) > float(window.iloc[i]) * 1.5:
                return t, False

    return fallback, True


# ── 메트릭 계산 ───────────────────────────────────────────────────────────────
def compute_metrics(
    q: pd.Series,
    clusters: list[EventCluster],
    threshold: float,
) -> list[RisingLimbMetrics]:
    metrics = []
    for idx, cluster in enumerate(clusters):
        onset_t, fallback = method3_onset(q, cluster.first_segment_start, cluster.peak_time, threshold)
        onset_q_raw = float(q.loc[onset_t]) if onset_t in q.index else float(q.asof(onset_t))
        onset_q = max(onset_q_raw, 1e-6)
        peak_q = cluster.peak_value
        rising_h = (cluster.peak_time - onset_t).total_seconds() / 3600
        if rising_h < 1:
            rising_h = 1.0
        rate = (peak_q - onset_q) / rising_h
        log_rate = float(np.log10(max(rate, 1e-9)))
        q_ratio = peak_q / onset_q

        metrics.append(RisingLimbMetrics(
            event_id=idx + 1,
            peak_time=cluster.peak_time,
            peak_q=peak_q,
            onset_time=onset_t,
            onset_q=onset_q,
            rising_hours=rising_h,
            rising_rate=rate,
            log_rising_rate=log_rate,
            q_ratio=q_ratio,
            month=cluster.peak_time.month,
            season=SEASON_MAP[cluster.peak_time.month],
            year=cluster.peak_time.year,
            fallback_used=fallback,
        ))
    return metrics


def metrics_to_df(metrics: list[RisingLimbMetrics]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "event_id": m.event_id,
            "peak_time": m.peak_time,
            "peak_q": m.peak_q,
            "onset_time": m.onset_time,
            "onset_q": m.onset_q,
            "rising_hours": m.rising_hours,
            "rising_rate": m.rising_rate,
            "log_rising_rate": m.log_rising_rate,
            "q_ratio": m.q_ratio,
            "month": m.month,
            "season": m.season,
            "year": m.year,
            "fallback_used": m.fallback_used,
        }
        for m in metrics
    ])


# ── plot utils ────────────────────────────────────────────────────────────────
def fig_to_b64(fig: plt.Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode()
    plt.close(fig)
    return b64


def style_ax(ax):
    ax.set_facecolor("#f8f9fa")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, alpha=0.3, color="#bdc3c7")


# ── 분석 플롯 1: 분포 3종 ─────────────────────────────────────────────────────
def plot_distributions(df: pd.DataFrame) -> str:
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    fig.patch.set_facecolor("#f8f9fa")

    # Rising Time 분포
    ax = axes[0]
    style_ax(ax)
    ax.hist(df["rising_hours"], bins=25, color="#3498db", edgecolor="white", alpha=0.8)
    med = df["rising_hours"].median()
    ax.axvline(med, color="#c0392b", lw=2, ls="--", label=f"Median: {med:.1f}h")
    ax.set_xlabel("Rising Time (hours)", fontsize=11)
    ax.set_ylabel("Event count", fontsize=11)
    ax.set_title("Rising Time Distribution", fontsize=12)
    ax.legend(fontsize=9)

    # Rising Rate 분포 (log scale)
    ax = axes[1]
    style_ax(ax)
    log_rates = df["log_rising_rate"].dropna()
    ax.hist(log_rates, bins=25, color="#27ae60", edgecolor="white", alpha=0.8)
    med_lr = log_rates.median()
    ax.axvline(med_lr, color="#c0392b", lw=2, ls="--",
               label=f"Median: 10^{med_lr:.2f} = {10**med_lr:.3f}")
    ax.set_xlabel("log10(Rising Rate)  [log(m3/s/h)]", fontsize=11)
    ax.set_ylabel("Event count", fontsize=11)
    ax.set_title("Rising Rate Distribution (log10)", fontsize=12)
    ax.legend(fontsize=9)

    # Q ratio 분포
    ax = axes[2]
    style_ax(ax)
    qr = np.log10(df["q_ratio"].clip(lower=1.01))
    ax.hist(qr, bins=25, color="#8e44ad", edgecolor="white", alpha=0.8)
    med_qr = qr.median()
    ax.axvline(med_qr, color="#c0392b", lw=2, ls="--",
               label=f"Median: 10^{med_qr:.2f}x")
    ax.set_xlabel("log10(Peak Q / Onset Q)  [amplification]", fontsize=11)
    ax.set_ylabel("Event count", fontsize=11)
    ax.set_title("Flow Amplification (Peak/Onset)", fontsize=12)
    ax.legend(fontsize=9)

    plt.tight_layout()
    return fig_to_b64(fig)


# ── 분석 플롯 2: Peak Q vs Rising Rate 산점도 ────────────────────────────────
def plot_peak_vs_rate(df: pd.DataFrame) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.patch.set_facecolor("#f8f9fa")

    seasons = ["Winter", "Spring", "Summer", "Fall"]

    # 왼쪽: Peak Q vs Rising Rate (log-log)
    ax = axes[0]
    style_ax(ax)
    for season in seasons:
        sub = df[df["season"] == season]
        ax.scatter(
            sub["peak_q"], sub["rising_rate"],
            color=SEASON_COLORS[season], label=season,
            alpha=0.75, s=60, edgecolors="white", lw=0.5,
        )
    # 전체 회귀선
    log_pq = np.log10(df["peak_q"].clip(lower=0.01))
    log_rr = df["log_rising_rate"]
    mask = np.isfinite(log_pq) & np.isfinite(log_rr)
    if mask.sum() > 5:
        slope, intercept, r, p, _ = stats.linregress(log_pq[mask], log_rr[mask])
        x_fit = np.linspace(log_pq[mask].min(), log_pq[mask].max(), 100)
        y_fit = slope * x_fit + intercept
        ax.plot(10**x_fit, 10**y_fit, "k--", lw=1.5, alpha=0.6,
                label=f"OLS: slope={slope:.2f}, r={r:.3f}")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Peak Discharge (m3/s)", fontsize=11)
    ax.set_ylabel("Rising Rate (m3/s/h)", fontsize=11)
    ax.set_title("Peak Q vs Rising Rate  [log-log]", fontsize=12)
    ax.legend(fontsize=9, loc="upper left")

    # 오른쪽: Rising Time vs Peak Q (log-log)
    ax = axes[1]
    style_ax(ax)
    for season in seasons:
        sub = df[df["season"] == season]
        ax.scatter(
            sub["rising_hours"], sub["peak_q"],
            color=SEASON_COLORS[season], label=season,
            alpha=0.75, s=60, edgecolors="white", lw=0.5,
        )
    log_rh = np.log10(df["rising_hours"].clip(lower=0.5))
    log_pq2 = np.log10(df["peak_q"].clip(lower=0.01))
    mask2 = np.isfinite(log_rh) & np.isfinite(log_pq2)
    if mask2.sum() > 5:
        slope2, intercept2, r2, p2, _ = stats.linregress(log_rh[mask2], log_pq2[mask2])
        x_fit2 = np.linspace(log_rh[mask2].min(), log_rh[mask2].max(), 100)
        y_fit2 = slope2 * x_fit2 + intercept2
        ax.plot(10**x_fit2, 10**y_fit2, "k--", lw=1.5, alpha=0.6,
                label=f"OLS: slope={slope2:.2f}, r={r2:.3f}")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Rising Time (hours)", fontsize=11)
    ax.set_ylabel("Peak Discharge (m3/s)", fontsize=11)
    ax.set_title("Rising Time vs Peak Q  [log-log]", fontsize=12)
    ax.legend(fontsize=9, loc="upper left")

    plt.tight_layout()
    return fig_to_b64(fig)


# ── 분석 플롯 3: 계절별 박스플롯 ─────────────────────────────────────────────
def plot_seasonal(df: pd.DataFrame) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.patch.set_facecolor("#f8f9fa")
    seasons_order = ["Winter", "Spring", "Summer", "Fall"]
    colors_list = [SEASON_COLORS[s] for s in seasons_order]

    # Rising Time
    ax = axes[0]
    style_ax(ax)
    data_rt = [df[df["season"] == s]["rising_hours"].dropna().values for s in seasons_order]
    bp = ax.boxplot(data_rt, patch_artist=True, notch=False, showfliers=True,
                    flierprops=dict(marker="o", markersize=3, alpha=0.4))
    for patch, col in zip(bp["boxes"], colors_list):
        patch.set_facecolor(col); patch.set_alpha(0.7)
    ax.set_xticklabels(seasons_order, fontsize=10)
    ax.set_ylabel("Rising Time (hours)", fontsize=11)
    ax.set_title("Rising Time by Season", fontsize=12)
    for i, data in enumerate(data_rt):
        if len(data) > 0:
            ax.text(i + 1, float(np.median(data)) * 1.05,
                    f"n={len(data)}", ha="center", fontsize=8, color="gray")

    # Rising Rate
    ax = axes[1]
    style_ax(ax)
    data_rr = [np.log10(df[df["season"] == s]["rising_rate"].clip(lower=1e-9)).dropna().values
               for s in seasons_order]
    bp2 = ax.boxplot(data_rr, patch_artist=True, notch=False, showfliers=True,
                     flierprops=dict(marker="o", markersize=3, alpha=0.4))
    for patch, col in zip(bp2["boxes"], colors_list):
        patch.set_facecolor(col); patch.set_alpha(0.7)
    ax.set_xticklabels(seasons_order, fontsize=10)
    ax.set_ylabel("log10(Rising Rate)  [log(m3/s/h)]", fontsize=11)
    ax.set_title("Rising Rate by Season", fontsize=12)
    for i, data in enumerate(data_rr):
        if len(data) > 0:
            ax.text(i + 1, float(np.median(data)) + 0.05,
                    f"n={len(data)}", ha="center", fontsize=8, color="gray")

    plt.tight_layout()
    return fig_to_b64(fig)


# ── 분석 플롯 4: 월별 패턴 ───────────────────────────────────────────────────
def plot_monthly(df: pd.DataFrame) -> str:
    fig, axes = plt.subplots(2, 1, figsize=(12, 8))
    fig.patch.set_facecolor("#f8f9fa")

    months = list(range(1, 13))
    monthly_rt_med = [df[df["month"] == m]["rising_hours"].median() for m in months]
    monthly_rt_cnt = [len(df[df["month"] == m]) for m in months]
    monthly_rr_med = [np.log10(max(df[df["month"] == m]["rising_rate"].median(), 1e-9))
                      for m in months]

    bar_colors = [SEASON_COLORS[SEASON_MAP[m]] for m in months]

    # 월별 Rising Time 중앙값
    ax = axes[0]
    style_ax(ax)
    bars = ax.bar(months, monthly_rt_med, color=bar_colors, edgecolor="white", alpha=0.8)
    ax2 = ax.twinx()
    ax2.plot(months, monthly_rt_cnt, "k--o", ms=5, lw=1.5, alpha=0.5, label="Event count")
    ax2.set_ylabel("Event count", fontsize=10, color="gray")
    ax2.tick_params(axis="y", colors="gray")
    ax.set_xticks(months)
    ax.set_xticklabels(MONTH_NAMES, fontsize=9)
    ax.set_ylabel("Median Rising Time (hours)", fontsize=11)
    ax.set_title("Monthly Median Rising Time (M3: SG onset)", fontsize=12)

    # season 범례
    legend_patches = [
        matplotlib.patches.Patch(color=SEASON_COLORS[s], label=s)
        for s in ["Winter","Spring","Summer","Fall"]
    ]
    ax.legend(handles=legend_patches, loc="upper right", fontsize=9)

    # 월별 Rising Rate 중앙값
    ax = axes[1]
    style_ax(ax)
    ax.bar(months, monthly_rr_med, color=bar_colors, edgecolor="white", alpha=0.8)
    ax.set_xticks(months)
    ax.set_xticklabels(MONTH_NAMES, fontsize=9)
    ax.set_ylabel("Median log10(Rising Rate)  [log(m3/s/h)]", fontsize=11)
    ax.set_title("Monthly Median Rising Rate (M3: SG onset)", fontsize=12)
    ax.legend(handles=legend_patches, loc="upper right", fontsize=9)

    plt.tight_layout()
    return fig_to_b64(fig)


# ── 분석 플롯 5: Rising Time vs Rising Rate 관계 ─────────────────────────────
def plot_rt_vs_rr(df: pd.DataFrame) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.patch.set_facecolor("#f8f9fa")

    seasons = ["Winter", "Spring", "Summer", "Fall"]

    # Rising Time vs Rising Rate
    ax = axes[0]
    style_ax(ax)
    for season in seasons:
        sub = df[df["season"] == season]
        ax.scatter(sub["rising_hours"], sub["rising_rate"],
                   color=SEASON_COLORS[season], label=season,
                   alpha=0.75, s=60, edgecolors="white", lw=0.5)
    log_rh = np.log10(df["rising_hours"].clip(lower=0.5))
    log_rr = df["log_rising_rate"]
    mask = np.isfinite(log_rh) & np.isfinite(log_rr)
    if mask.sum() > 5:
        slope, intercept, r, _, _ = stats.linregress(log_rh[mask], log_rr[mask])
        x_fit = np.linspace(log_rh[mask].min(), log_rh[mask].max(), 100)
        y_fit = slope * x_fit + intercept
        ax.plot(10**x_fit, 10**y_fit, "k--", lw=1.5, alpha=0.6,
                label=f"OLS: slope={slope:.2f}, r={r:.3f}")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Rising Time (hours)", fontsize=11)
    ax.set_ylabel("Rising Rate (m3/s/h)", fontsize=11)
    ax.set_title("Rising Time vs Rising Rate  [log-log]", fontsize=12)
    ax.legend(fontsize=9)

    # 연도별 추세: Peak Q top-10 강조
    ax = axes[1]
    style_ax(ax)
    df_sorted = df.sort_values("peak_q", ascending=False)
    top10 = df_sorted.head(10)
    rest = df_sorted.iloc[10:]
    ax.scatter(rest["rising_hours"], rest["rising_rate"],
               color="#95a5a6", alpha=0.5, s=40, label="Other events")
    sc = ax.scatter(top10["rising_hours"], top10["rising_rate"],
                    c=top10["peak_q"], cmap="YlOrRd", s=120,
                    edgecolors="#2c3e50", lw=1, zorder=5, label="Top-10 peak Q")
    for _, row in top10.iterrows():
        ax.annotate(f"{row['peak_q']:.0f}",
                    (row["rising_hours"], row["rising_rate"]),
                    textcoords="offset points", xytext=(4, 4), fontsize=7.5, color="#2c3e50")
    plt.colorbar(sc, ax=ax, label="Peak Q (m3/s)")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Rising Time (hours)", fontsize=11)
    ax.set_ylabel("Rising Rate (m3/s/h)", fontsize=11)
    ax.set_title("Top-10 Peak Events Highlighted", fontsize=12)
    ax.legend(fontsize=9)

    plt.tight_layout()
    return fig_to_b64(fig)


# ── 분석 플롯 6: 연도별 추세 ─────────────────────────────────────────────────
def plot_yearly(df: pd.DataFrame) -> str:
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    fig.patch.set_facecolor("#f8f9fa")

    years = sorted(df["year"].unique())
    yr_rt = df.groupby("year")["rising_hours"].median()
    yr_rr = df.groupby("year")["log_rising_rate"].median()
    yr_cnt = df.groupby("year").size()
    yr_peak = df.groupby("year")["peak_q"].max()

    ax = axes[0]
    style_ax(ax)
    ax.bar(yr_rt.index, yr_rt.values, color="#3498db", alpha=0.7, label="Median Rising Time")
    ax.set_ylabel("Median Rising Time (hours)", fontsize=11)
    ax.set_title(f"Basin {GAUGE_ID} — Annual Rising Limb Statistics (M3: SG)", fontsize=12)
    ax2 = ax.twinx()
    ax2.plot(yr_cnt.index, yr_cnt.values, "k--o", ms=4, lw=1.2, alpha=0.5)
    ax2.set_ylabel("Event count", fontsize=10, color="gray")
    ax2.tick_params(axis="y", colors="gray")
    ax.legend(fontsize=9)

    ax = axes[1]
    style_ax(ax)
    ax.bar(yr_rr.index, yr_rr.values, color="#27ae60", alpha=0.7, label="Median log10(Rising Rate)")
    ax.set_ylabel("Median log10(Rising Rate)  [log(m3/s/h)]", fontsize=11)
    ax.set_xlabel("Year", fontsize=11)
    ax3 = ax.twinx()
    ax3.plot(yr_peak.index, yr_peak.values, "rs--", ms=4, lw=1.2, alpha=0.6)
    ax3.set_ylabel("Max Peak Q (m3/s)", fontsize=10, color="#c0392b")
    ax3.tick_params(axis="y", colors="#c0392b")
    ax.legend(fontsize=9)

    plt.tight_layout()
    return fig_to_b64(fig)


# ── HTML ──────────────────────────────────────────────────────────────────────
CSS = """
<style>
  body { font-family: 'Noto Sans KR','Apple SD Gothic Neo',sans-serif;
         max-width:1100px; margin:0 auto; padding:24px 20px;
         background:#f4f6f9; color:#2c3e50; line-height:1.75; }
  h1 { font-size:1.7rem; border-bottom:3px solid #27ae60; padding-bottom:10px; }
  h2 { font-size:1.25rem; color:#1a7a4a; margin-top:2.2rem;
       border-left:4px solid #27ae60; padding-left:10px; }
  h3 { font-size:1.05rem; color:#117a65; margin-top:1.4rem; }
  .card { background:white; border-radius:10px; padding:20px 24px;
          box-shadow:0 2px 8px rgba(0,0,0,.08); margin:18px 0; }
  table { border-collapse:collapse; width:100%; font-size:0.86rem; }
  th { background:#1e8449; color:white; padding:9px 12px; text-align:center; }
  td { padding:7px 12px; border-bottom:1px solid #ecf0f1; text-align:center; }
  tr:nth-child(even) { background:#f8fafb; }
  tr:hover { background:#e8f8ef; }
  img { max-width:100%; border-radius:8px; margin:10px 0;
        box-shadow:0 2px 6px rgba(0,0,0,.12); }
  .stat-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:16px 0; }
  .stat-box { background:#f0faf4; border:1px solid #a9dfbf; border-radius:8px;
              padding:14px; text-align:center; }
  .stat-val { font-size:1.5rem; font-weight:bold; color:#1e8449; }
  .stat-lbl { font-size:0.82rem; color:#7f8c8d; margin-top:4px; }
  .badge { display:inline-block; padding:2px 9px; border-radius:10px;
           font-size:0.8rem; font-weight:bold; }
  .b-fb { background:#fde8e8; color:#c0392b; }
  .b-ok { background:#e8f8ef; color:#1e8449; }
  .note { background:#fef9e7; border:1px solid #f9ca24; border-radius:6px;
          padding:10px 14px; font-size:0.9rem; margin:10px 0; }
  .toc a { color:#1a7a4a; text-decoration:none; display:block;
           padding:3px 0; font-size:0.92rem; }
  .toc a:hover { text-decoration:underline; }
</style>
"""


def build_stat_box(val: str, label: str) -> str:
    return f"""<div class="stat-box"><div class="stat-val">{val}</div>
               <div class="stat-lbl">{label}</div></div>"""


def generate_html(
    df: pd.DataFrame,
    threshold: float,
    b64_dist: str,
    b64_peak: str,
    b64_season: str,
    b64_monthly: str,
    b64_rtvsrr: str,
    b64_yearly: str,
) -> str:
    n_total = len(df)
    n_fallback = df["fallback_used"].sum()
    rt_med = df["rising_hours"].median()
    rt_mean = df["rising_hours"].mean()
    rr_med = df["rising_rate"].median()
    amp_med = df["q_ratio"].median()

    # 계절별 통계
    season_rows = []
    for s in ["Winter","Spring","Summer","Fall"]:
        sub = df[df["season"] == s]
        if len(sub) == 0:
            continue
        season_rows.append(
            f"<tr><td>{s}</td><td>{len(sub)}</td>"
            f"<td>{sub['rising_hours'].median():.1f}h</td>"
            f"<td>{sub['rising_hours'].mean():.1f}h</td>"
            f"<td>{sub['rising_rate'].median():.4f}</td>"
            f"<td>{sub['q_ratio'].median():.1f}x</td></tr>"
        )

    # 이벤트 테이블 (상위 20: peak Q 내림차순)
    top20 = df.nlargest(20, "peak_q")
    event_rows = []
    for _, row in top20.iterrows():
        fb_badge = f"<span class='badge b-fb'>fallback</span>" if row["fallback_used"] \
                   else f"<span class='badge b-ok'>SG</span>"
        event_rows.append(
            f"<tr>"
            f"<td>{row['peak_time'].strftime('%Y-%m-%d %H:%M')}</td>"
            f"<td>{row['peak_q']:.2f}</td>"
            f"<td>{row['onset_time'].strftime('%m-%d %H:%M')}</td>"
            f"<td>{row['onset_q']:.4f}</td>"
            f"<td>{row['rising_hours']:.1f}</td>"
            f"<td>{row['rising_rate']:.4f}</td>"
            f"<td>{row['q_ratio']:.1f}x</td>"
            f"<td>{row['season']}</td>"
            f"<td>{fb_badge}</td>"
            f"</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Rising Limb M3 분석 — Basin {GAUGE_ID}</title>
{CSS}
</head>
<body>

<h1>📊 Rising Limb 상승경사 분석 — Method 3 (Savitzky-Golay)</h1>
<p style="color:#7f8c8d;font-size:.92rem;">
  대상 basin: <strong>{GAUGE_ID}</strong> | Q99 임계값: <strong>{threshold:.4f} m³/s</strong> |
  분석 이벤트: <strong>{n_total}건</strong> | SG 직접 감지: <strong>{n_total - n_fallback}건</strong>
  ({100*(n_total-n_fallback)/n_total:.0f}%) | Fallback: <strong>{n_fallback}건</strong>
</p>

<div class="card toc">
  <strong>목차</strong>
  <a href="#summary">1. 핵심 통계 요약</a>
  <a href="#dist">2. Rising Time / Rate / 증폭 분포</a>
  <a href="#peak">3. 첨두 유량 vs 상승경사 관계</a>
  <a href="#rtvsrr">4. Rising Time vs Rising Rate 관계</a>
  <a href="#season">5. 계절별 패턴</a>
  <a href="#monthly">6. 월별 패턴</a>
  <a href="#yearly">7. 연도별 추세</a>
  <a href="#top20">8. 상위 20 이벤트 표</a>
</div>

<!-- 1. 요약 -->
<h2 id="summary">1. 핵심 통계 요약</h2>
<div class="card">
  <div class="stat-grid">
    {build_stat_box(f"{rt_med:.1f}h", "중앙값 Rising Time")}
    {build_stat_box(f"{rt_mean:.1f}h", "평균 Rising Time")}
    {build_stat_box(f"{rr_med:.4f}", "중앙값 Rising Rate (m³/s/h)")}
    {build_stat_box(f"{amp_med:.1f}x", "중앙값 유량 증폭 (Peak/Onset)")}
  </div>
  <div class="note">
    ⚙️ <strong>방법 3 (SG) 감지율: {100*(n_total-n_fallback)/n_total:.0f}%</strong>
    ({n_total-n_fallback}/{n_total}건) — 나머지 {n_fallback}건은 창 크기 부족 또는
    극솟값 미발견으로 임계값 역추적(M1) fallback 적용.
  </div>

  <h3>계절별 통계</h3>
  <table>
    <tr><th>계절</th><th>이벤트 수</th><th>중앙값 Rising Time</th>
        <th>평균 Rising Time</th><th>중앙값 Rising Rate (m³/s/h)</th>
        <th>중앙값 유량 증폭</th></tr>
    {''.join(season_rows)}
  </table>
</div>

<!-- 2. 분포 -->
<h2 id="dist">2. Rising Time / Rate / 증폭 분포</h2>
<div class="card">
  <p>
    <strong>Rising Time</strong>: SG onset에서 첨두까지 걸린 시간 (시간 단위).
    짧을수록 flashy(급격한) 유역 반응.<br>
    <strong>Rising Rate</strong>: (첨두 유량 − onset 유량) ÷ Rising Time. 상승 가파름.<br>
    <strong>유량 증폭</strong>: 첨두 유량 ÷ onset 유량. 몇 배로 불어났는지.
  </p>
  <img src="data:image/png;base64,{b64_dist}" alt="distribution plots">
</div>

<!-- 3. Peak vs Rate -->
<h2 id="peak">3. 첨두 유량 vs 상승경사 관계</h2>
<div class="card">
  <p>log-log 산점도에서 OLS 회귀선의 기울기가 양수이면
  "더 큰 홍수일수록 더 가파르게 상승" 패턴을 의미합니다.
  기울기 ≈ 1이면 비례 관계, > 1이면 초과 비례(suplinear).</p>
  <img src="data:image/png;base64,{b64_peak}" alt="peak vs rate">
</div>

<!-- 4. RT vs RR -->
<h2 id="rtvsrr">4. Rising Time vs Rising Rate 관계</h2>
<div class="card">
  <p>Rising Time이 짧을수록 Rising Rate가 높은 음의 상관이 일반적입니다.
  오른쪽 패널은 첨두 유량 상위 10개 이벤트를 색상 강조하여
  어떤 사건이 "빠르고 강한" 유형인지 보여줍니다.</p>
  <img src="data:image/png;base64,{b64_rtvsrr}" alt="rising time vs rate">
</div>

<!-- 5. 계절 -->
<h2 id="season">5. 계절별 패턴</h2>
<div class="card">
  <p>계절별 박스플롯. 상자 안 선 = 중앙값, 박스 = IQR (25–75 백분위),
  수염 = 1.5×IQR, 점 = 이상값.</p>
  <img src="data:image/png;base64,{b64_season}" alt="seasonal boxplot">
</div>

<!-- 6. 월별 -->
<h2 id="monthly">6. 월별 패턴</h2>
<div class="card">
  <p>막대: 월별 중앙값. 점선: 이벤트 수 또는 최대 첨두 유량.
  색상은 계절 구분 (파랑=겨울, 초록=봄, 빨강=여름, 주황=가을).</p>
  <img src="data:image/png;base64,{b64_monthly}" alt="monthly pattern">
</div>

<!-- 7. 연도별 -->
<h2 id="yearly">7. 연도별 추세</h2>
<div class="card">
  <img src="data:image/png;base64,{b64_yearly}" alt="yearly trend">
</div>

<!-- 8. Top-20 -->
<h2 id="top20">8. 첨두 유량 상위 20 이벤트</h2>
<div class="card">
  <table>
    <tr><th>첨두 시각</th><th>첨두 Q (m³/s)</th>
        <th>Onset 시각</th><th>Onset Q (m³/s)</th>
        <th>Rising Time (h)</th><th>Rising Rate (m³/s/h)</th>
        <th>증폭</th><th>계절</th><th>감지</th></tr>
    {''.join(event_rows)}
  </table>
</div>

<p style="text-align:center;color:#bdc3c7;font-size:.8rem;margin-top:30px">
  Basin {GAUGE_ID} | Q99 = {threshold:.4f} m³/s | {n_total}개 이벤트 | M3 Savitzky-Golay onset
</p>
</body>
</html>"""


# ── 메인 ──────────────────────────────────────────────────────────────────────
def main() -> None:
    matplotlib.rcParams.update({
        "figure.facecolor": "#f8f9fa",
        "axes.facecolor": "#f8f9fa",
        "font.size": 10,
    })

    print("데이터 로드...")
    q = load_streamflow()
    threshold = compute_q99(q)
    print(f"Q99 = {threshold:.4f} m³/s")

    print("클러스터 감지...")
    clusters = detect_clusters(q, threshold)
    print(f"총 {len(clusters)}개")

    print("M3 onset 계산...")
    metrics = compute_metrics(q, clusters, threshold)
    df = metrics_to_df(metrics)
    print(f"Fallback 사용: {df['fallback_used'].sum()}건 / {len(df)}건")

    print("플롯 생성...")
    b64_dist    = plot_distributions(df)
    b64_peak    = plot_peak_vs_rate(df)
    b64_season  = plot_seasonal(df)
    b64_monthly = plot_monthly(df)
    b64_rtvsrr  = plot_rt_vs_rr(df)
    b64_yearly  = plot_yearly(df)

    print("HTML 생성...")
    html = generate_html(df, threshold, b64_dist, b64_peak,
                         b64_season, b64_monthly, b64_rtvsrr, b64_yearly)
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"\n완료: {OUTPUT_HTML}")

    # 요약 출력
    print(f"\n=== 요약 (M3 SG onset 기준) ===")
    print(f"중앙값 Rising Time : {df['rising_hours'].median():.1f}h")
    print(f"평균  Rising Time  : {df['rising_hours'].mean():.1f}h")
    print(f"중앙값 Rising Rate : {df['rising_rate'].median():.4f} m³/s/h")
    print(f"중앙값 유량 증폭   : {df['q_ratio'].median():.1f}x")
    print()
    for s in ["Winter","Spring","Summer","Fall"]:
        sub = df[df["season"] == s]
        print(f"  {s:6s} n={len(sub):3d} | RT_med={sub['rising_hours'].median():.1f}h | "
              f"RR_med={sub['rising_rate'].median():.4f}")


if __name__ == "__main__":
    main()
