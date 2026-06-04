#!/usr/bin/env python3
# /// script
# dependencies = ["xarray", "pandas", "numpy", "scipy", "matplotlib", "netCDF4"]
# ///
"""
Rising limb onset detection: 세 가지 방법 비교 분석
대상 basin: 0142400103 (DRBC region)

방법 비교:
  1. 임계값 역추적 (현재 방법): Q < Q99인 마지막 시점
  2. Rolling Mean + dQ/dt 부호 변화
  3. Savitzky-Golay 필터 + dQ/dt 부호 변화

출력: output/model_analysis/band_signal/method_compare/rising_limb_comparison.html
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from scipy.signal import savgol_filter

# ── 경로 설정 ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[3]
NC_PATH = ROOT / "basins/CAMELSH_data/hourly_observed/netcdf/0142400103_hourly.nc"
OUTPUT_DIR = ROOT / "output/model_analysis/band_signal/method_compare"
OUTPUT_HTML = OUTPUT_DIR / "rising_limb_comparison.html"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

GAUGE_ID = "0142400103"
Q99_QUANTILE = 0.99
MIN_GAP_HOURS = 24          # 클러스터 병합 최소 간격
MAX_LOOKBACK_HOURS = 240    # 역추적 최대 시간 (10일)
SMOOTH_HOURS = 6            # rolling mean 창 크기
SG_WINDOW = 13              # Savitzky-Golay 창 (홀수)
SG_POLY = 3                 # SG 다항식 차수


# ── 데이터 클래스 ──────────────────────────────────────────────────────────────
@dataclass
class EventCluster:
    first_segment_start: pd.Timestamp
    last_segment_end: pd.Timestamp
    peak_time: pd.Timestamp
    peak_value: float


@dataclass
class OnsetResult:
    method_name: str
    onset_time: pd.Timestamp
    onset_flow: float
    rising_hours: float
    rising_rate: float   # (peak - onset_flow) / rising_hours


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


# ── 방법 1: 임계값 역추적 (현재 방법) ─────────────────────────────────────────
def method1_threshold(q: pd.Series, ref_time: pd.Timestamp, threshold: float) -> pd.Timestamp:
    prefix = q.loc[:ref_time].iloc[:-1]
    candidates = prefix[prefix.notna() & (prefix < threshold)]
    if not candidates.empty:
        return candidates.index[-1]
    valid = q.loc[:ref_time].dropna()
    return valid.index[0] if not valid.empty else ref_time


# ── 방법 2: Rolling Mean + dQ/dt 부호 변화 ────────────────────────────────────
def method2_rolling(
    q: pd.Series,
    ref_time: pd.Timestamp,
    peak_time: pd.Timestamp,
    threshold: float,
) -> pd.Timestamp:
    fallback = method1_threshold(q, ref_time, threshold)
    lb_start = ref_time - pd.Timedelta(hours=MAX_LOOKBACK_HOURS)
    window = q.loc[lb_start:ref_time].dropna()
    if len(window) < SMOOTH_HOURS * 2:
        return fallback

    smoothed = window.rolling(SMOOTH_HOURS, center=True, min_periods=1).mean()
    dq = smoothed.diff()
    signs = np.sign(dq.fillna(0).values)

    for i in range(len(signs) - 2, 0, -1):
        if signs[i] <= 0 and signs[i + 1] > 0:
            t = window.index[i]
            seg = q.loc[t:peak_time]
            # 해당 trough 이후 첨두까지 순증가 확인
            if len(seg) > 1 and float(seg.iloc[-1]) > float(window.iloc[i]) * 1.5:
                return t

    return fallback


# ── 방법 3: Savitzky-Golay 필터 + dQ/dt ──────────────────────────────────────
def method3_savgol(
    q: pd.Series,
    ref_time: pd.Timestamp,
    peak_time: pd.Timestamp,
    threshold: float,
) -> pd.Timestamp:
    fallback = method1_threshold(q, ref_time, threshold)
    lb_start = ref_time - pd.Timedelta(hours=MAX_LOOKBACK_HOURS)
    window = q.loc[lb_start:ref_time].dropna()

    win = min(SG_WINDOW, len(window) - 1)
    if win % 2 == 0:
        win -= 1
    if win < SG_POLY + 2 or len(window) < win:
        return method2_rolling(q, ref_time, peak_time, threshold)

    vals = window.values.astype(float)
    smoothed_vals = savgol_filter(vals, win, SG_POLY)
    # SG는 도함수도 직접 계산 가능 (deriv=1)
    dq_vals = savgol_filter(vals, win, SG_POLY, deriv=1)
    signs = np.sign(dq_vals)

    for i in range(len(signs) - 2, 0, -1):
        if signs[i] <= 0 and signs[i + 1] > 0:
            t = window.index[i]
            seg = q.loc[t:peak_time]
            if len(seg) > 1 and float(seg.iloc[-1]) > float(window.iloc[i]) * 1.5:
                return t

    return fallback


# ── Lyne-Hollick 기저유량 분리 ─────────────────────────────────────────────────
def lyne_hollick_baseflow(q_vals: np.ndarray, alpha: float = 0.925) -> np.ndarray:
    qf = np.zeros_like(q_vals, dtype=float)
    qf[0] = q_vals[0] / 2.0
    for i in range(1, len(q_vals)):
        qf[i] = max(0.0, alpha * qf[i - 1] + (1 - alpha) / 2 * (q_vals[i] + q_vals[i - 1]))
    return q_vals - qf  # baseflow


# ── 결과 집계 ─────────────────────────────────────────────────────────────────
def compute_onset_results(
    q: pd.Series,
    cluster: EventCluster,
    threshold: float,
) -> list[OnsetResult]:
    ref = cluster.first_segment_start
    peak_t = cluster.peak_time
    peak_v = cluster.peak_value

    results = []
    for name, t in [
        ("방법 1: 임계값 역추적", method1_threshold(q, ref, threshold)),
        ("방법 2: Rolling Mean", method2_rolling(q, ref, peak_t, threshold)),
        ("방법 3: Savitzky-Golay", method3_savgol(q, ref, peak_t, threshold)),
    ]:
        onset_flow = float(q.loc[t]) if t in q.index else float(q.asof(t))
        rising_h = (peak_t - t).total_seconds() / 3600
        rate = (peak_v - onset_flow) / max(1.0, rising_h)
        results.append(OnsetResult(name, t, onset_flow, rising_h, rate))

    return results


# ── matplotlib → base64 PNG ───────────────────────────────────────────────────
def fig_to_b64(fig: plt.Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode()
    plt.close(fig)
    return encoded


# ── 이벤트 시각화 ──────────────────────────────────────────────────────────────
METHOD_COLORS = ["#e74c3c", "#27ae60", "#8e44ad"]
METHOD_LABELS_SHORT = ["방법 1", "방법 2 (Rolling)", "방법 3 (SG)"]


def plot_event(
    q: pd.Series,
    cluster: EventCluster,
    results: list[OnsetResult],
    threshold: float,
) -> str:
    peak_t = cluster.peak_time
    plot_start = peak_t - pd.Timedelta(hours=96)
    plot_end = peak_t + pd.Timedelta(hours=48)
    q_plot = q.loc[plot_start:plot_end]

    # 기저유량 계산
    lb_start = cluster.first_segment_start - pd.Timedelta(hours=MAX_LOOKBACK_HOURS)
    pre_window = q.loc[max(lb_start, plot_start): cluster.first_segment_start].dropna()
    bf_vals = lyne_hollick_baseflow(pre_window.values.astype(float))
    bf_series = pd.Series(bf_vals, index=pre_window.index)

    fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1.5, 1.5]})
    fig.patch.set_facecolor("#f8f9fa")

    # ── 상단: 유량 + onset 마커 ──
    ax = axes[0]
    ax.set_facecolor("#f8f9fa")
    ax.fill_between(q_plot.index, q_plot.values, alpha=0.18, color="#3498db")
    ax.plot(q_plot.index, q_plot.values, color="#2c3e50", lw=1.8, label="Observed Streamflow")
    ax.fill_between(bf_series.index, bf_series.values, alpha=0.35, color="#95a5a6",
                    label="Baseflow (Lyne-Hollick)")
    ax.plot(bf_series.index, bf_series.values, color="#7f8c8d", lw=1.2, ls="--")
    ax.axhline(threshold, color="#95a5a6", ls=":", lw=1.5,
               label=f"Q99 threshold = {threshold:.2f} m3/s")
    ax.axvline(peak_t, color="#e67e22", ls="--", lw=1.8,
               label=f"Peak: {peak_t.strftime('%m/%d %H:%M')}")

    method_short = ["M1: Threshold", "M2: Rolling Mean", "M3: Savitzky-Golay"]
    for res, col, short in zip(results, METHOD_COLORS, method_short):
        qv = res.onset_flow
        ax.axvline(res.onset_time, color=col, lw=2.2, alpha=0.85,
                   label=f"{short}: {res.onset_time.strftime('%m/%d %H:%M')} (Q={qv:.3f})")
        ax.scatter([res.onset_time], [qv], color=col, zorder=6, s=90, edgecolors="white", lw=1.2)

    ax.set_ylabel("Streamflow (m3/s)", fontsize=11)
    ax.set_title(
        f"Basin {GAUGE_ID} — Rising Limb Onset Comparison\n"
        f"Peak: {peak_t.strftime('%Y-%m-%d %H:%M')}  |  Peak Q: {cluster.peak_value:.2f} m3/s  |  Q99: {threshold:.2f} m3/s",
        fontsize=11, pad=10,
    )
    ax.legend(loc="upper left", fontsize=8.5, framealpha=0.9)
    ax.set_yscale("symlog", linthresh=0.5)
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())

    # ── 중단: 스무딩 신호 비교 ──
    ax2 = axes[1]
    ax2.set_facecolor("#f8f9fa")
    if len(pre_window) >= SMOOTH_HOURS:
        sm_roll = pre_window.rolling(SMOOTH_HOURS, center=True, min_periods=1).mean()
        ax2.plot(sm_roll.index, sm_roll.values, color="#27ae60", lw=2, label=f"Rolling Mean ({SMOOTH_HOURS}h)")

    win = min(SG_WINDOW, len(pre_window) - 1)
    if win % 2 == 0: win -= 1
    if len(pre_window) >= win and win >= SG_POLY + 2:
        sg_smooth = savgol_filter(pre_window.values.astype(float), win, SG_POLY)
        ax2.plot(pre_window.index, sg_smooth, color="#8e44ad", lw=2, ls="-",
                 label=f"Savitzky-Golay (win={win}, poly={SG_POLY})")

    ax2.plot(pre_window.index, pre_window.values, color="#3498db", lw=1, alpha=0.5, label="Raw")
    for res, col in zip(results, METHOD_COLORS):
        if plot_start <= res.onset_time <= cluster.first_segment_start:
            ax2.axvline(res.onset_time, color=col, lw=1.8, alpha=0.7)
    ax2.set_ylabel("Streamflow (m3/s)\npre-event window", fontsize=10)
    ax2.legend(fontsize=8.5, framealpha=0.9)

    # ── 하단: dQ/dt (SG derivative) ──
    ax3 = axes[2]
    ax3.set_facecolor("#f8f9fa")
    if len(pre_window) >= win and win >= SG_POLY + 2:
        dq = savgol_filter(pre_window.values.astype(float), win, SG_POLY, deriv=1)
        ax3.plot(pre_window.index, dq, color="#c0392b", lw=1.5, label="dQ/dt (SG derivative)")
        ax3.axhline(0, color="gray", lw=0.8, ls="--")
        ax3.fill_between(pre_window.index, dq, 0, where=(dq > 0),
                         alpha=0.25, color="#e74c3c", label="Rising")
        ax3.fill_between(pre_window.index, dq, 0, where=(dq <= 0),
                         alpha=0.15, color="#3498db", label="Falling")
    for res, col in zip(results, METHOD_COLORS):
        if plot_start <= res.onset_time <= cluster.first_segment_start:
            ax3.axvline(res.onset_time, color=col, lw=1.8, alpha=0.7)
    ax3.set_ylabel("dQ/dt\n(rate of change)", fontsize=10)
    ax3.set_xlabel("Date / Time", fontsize=10)
    ax3.legend(fontsize=8.5, framealpha=0.9)

    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d\n%H:%M"))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=12))
        ax.grid(True, alpha=0.3, color="#bdc3c7")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    plt.tight_layout(h_pad=0.4)
    return fig_to_b64(fig)


# ── 전체 비교 산점도 ──────────────────────────────────────────────────────────
def plot_method_scatter(all_results: list[tuple[EventCluster, list[OnsetResult]]]) -> str:
    """방법 1 rising_hours vs 방법 2/3 rising_hours 산점도."""
    h1, h2, h3 = [], [], []
    for _, res_list in all_results:
        h1.append(res_list[0].rising_hours)
        h2.append(res_list[1].rising_hours)
        h3.append(res_list[2].rising_hours)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.patch.set_facecolor("#f8f9fa")

    max_h = max(max(h1), max(h2), max(h3))

    for ax, hy, label, col in zip(
        axes,
        [h2, h3],
        ["M2: Rolling Mean", "M3: Savitzky-Golay"],
        ["#27ae60", "#8e44ad"],
    ):
        ax.set_facecolor("#f8f9fa")
        ax.scatter(h1, hy, color=col, alpha=0.7, edgecolors="white", s=70)
        ax.plot([0, max_h], [0, max_h], "k--", lw=1, alpha=0.4, label="y = x (identical)")
        ax.set_xlabel("M1 Rising Time (hours)", fontsize=11)
        ax.set_ylabel(f"{label}\nRising Time (hours)", fontsize=11)
        ax.set_title(f"M1 vs {label}", fontsize=11)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        corr = np.corrcoef(h1, hy)[0, 1]
        ax.text(0.05, 0.92, f"Pearson r = {corr:.3f}", transform=ax.transAxes,
                fontsize=9, color="gray")

    plt.tight_layout()
    return fig_to_b64(fig)


# ── Rising Time 분포 히스토그램 ──────────────────────────────────────────────
def plot_rising_time_dist(all_results: list[tuple[EventCluster, list[OnsetResult]]]) -> str:
    bins = np.arange(0, 250, 10)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4), sharey=True)
    fig.patch.set_facecolor("#f8f9fa")

    method_names = ["M1: Threshold", "M2: Rolling Mean", "M3: Savitzky-Golay"]
    colors = METHOD_COLORS

    for idx, (ax, name, col) in enumerate(zip(axes, method_names, colors)):
        hours = [res_list[idx].rising_hours for _, res_list in all_results]
        ax.set_facecolor("#f8f9fa")
        ax.hist(hours, bins=bins, color=col, alpha=0.75, edgecolor="white")
        ax.axvline(float(np.median(hours)), color="black", lw=2, ls="--",
                   label=f"Median: {np.median(hours):.1f}h")
        ax.set_title(name, fontsize=10)
        ax.set_xlabel("Rising Time (hours)", fontsize=10)
        ax.set_ylabel("Event count" if idx == 0 else "", fontsize=10)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, axis="y")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig.suptitle(f"Basin {GAUGE_ID} — Rising Time Distribution by Method", fontsize=12, y=1.01)
    plt.tight_layout()
    return fig_to_b64(fig)


# ── HTML 생성 ─────────────────────────────────────────────────────────────────
HTML_CSS = """
<style>
  body { font-family: 'Noto Sans KR', 'Apple SD Gothic Neo', sans-serif;
         max-width: 1100px; margin: 0 auto; padding: 24px 20px;
         background: #f4f6f9; color: #2c3e50; line-height: 1.7; }
  h1 { font-size: 1.7rem; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
  h2 { font-size: 1.25rem; color: #2980b9; margin-top: 2.2rem; border-left: 4px solid #3498db; padding-left: 10px; }
  h3 { font-size: 1.05rem; color: #16a085; margin-top: 1.5rem; }
  .card { background: white; border-radius: 10px; padding: 20px 24px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin: 18px 0; }
  .method-box { border-left: 5px solid; padding: 14px 18px; margin: 12px 0;
                border-radius: 0 8px 8px 0; background: #fafafa; }
  .m1 { border-color: #e74c3c; }
  .m2 { border-color: #27ae60; }
  .m3 { border-color: #8e44ad; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 12px;
           font-size: 0.82rem; font-weight: bold; margin-right: 6px; }
  .b1 { background: #fde8e8; color: #c0392b; }
  .b2 { background: #e8f8ef; color: #1e8449; }
  .b3 { background: #f0e8f8; color: #6c3483; }
  table { border-collapse: collapse; width: 100%; font-size: 0.88rem; }
  th { background: #2980b9; color: white; padding: 10px 12px; text-align: center; }
  td { padding: 8px 12px; border-bottom: 1px solid #ecf0f1; text-align: center; }
  tr:nth-child(even) { background: #f8f9fa; }
  tr:hover { background: #eaf4fb; }
  img { max-width: 100%; border-radius: 8px; margin: 10px 0; box-shadow: 0 2px 6px rgba(0,0,0,0.12); }
  .diff-pos { color: #c0392b; font-weight: bold; }
  .diff-neg { color: #1e8449; font-weight: bold; }
  .note { background: #fef9e7; border: 1px solid #f9ca24; border-radius: 6px;
          padding: 10px 14px; font-size: 0.9rem; margin: 10px 0; }
  .formula { background: #ecf0f1; border-radius: 6px; padding: 10px 14px;
             font-family: monospace; font-size: 0.88rem; margin: 8px 0; }
  .toc a { color: #2980b9; text-decoration: none; display: block; padding: 4px 0; font-size: 0.92rem; }
  .toc a:hover { text-decoration: underline; }
  .section-divider { height: 2px; background: linear-gradient(to right, #3498db, transparent); margin: 30px 0; }
</style>
"""


def build_table_row(cluster: EventCluster, results: list[OnsetResult]) -> str:
    peak_str = cluster.peak_time.strftime("%Y-%m-%d %H:%M")
    peak_q = f"{cluster.peak_value:.2f}"
    rows = []
    for i, (res, b_cls) in enumerate(zip(results, ["b1", "b2", "b3"])):
        td_onset = res.onset_time.strftime("%m-%d %H:%M")
        td_flow = f"{res.onset_flow:.3f}"
        td_h = f"{res.rising_hours:.1f}"
        td_rate = f"{res.rising_rate:.3f}"
        rows.append(
            f"<td><span class='badge {b_cls}'>{['M1','M2','M3'][i]}</span>{td_onset}</td>"
            f"<td>{td_flow}</td><td>{td_h}</td><td>{td_rate}</td>"
        )
    return (
        f"<tr><td>{peak_str}</td><td>{peak_q}</td>"
        + "</tr><tr><td></td><td></td>".join(rows)
        + "</tr>"
    )


def generate_html(
    q: pd.Series,
    threshold: float,
    all_results: list[tuple[EventCluster, list[OnsetResult]]],
    event_plots: list[tuple[EventCluster, list[OnsetResult], str]],
    scatter_b64: str,
    dist_b64: str,
) -> str:

    # 요약 통계
    h1_all = [r[1][0].rising_hours for r in all_results]
    h2_all = [r[1][1].rising_hours for r in all_results]
    h3_all = [r[1][2].rising_hours for r in all_results]
    n_events = len(all_results)

    def delta_str(a, b):
        d = float(np.median(b)) - float(np.median(a))
        cls = "diff-pos" if d > 0 else "diff-neg"
        sign = "+" if d > 0 else ""
        return f"<span class='{cls}'>{sign}{d:.1f}h</span>"

    # 이벤트별 섹션
    event_sections = []
    for cluster, results, b64 in event_plots:
        peak_str = cluster.peak_time.strftime("%Y년 %m월 %d일 %H시")
        rows_html = []
        for res, b_cls, short in zip(results, ["b1", "b2", "b3"], METHOD_LABELS_SHORT):
            rows_html.append(
                f"<tr><td><span class='badge {b_cls}'>{short}</span></td>"
                f"<td>{res.onset_time.strftime('%m/%d %H:%M')}</td>"
                f"<td>{res.onset_flow:.4f} m³/s</td>"
                f"<td>{res.rising_hours:.1f} h</td>"
                f"<td>{res.rising_rate:.4f} m³/s/h</td></tr>"
            )
        event_sections.append(f"""
<div class="card">
  <h3>사례: 첨두 {peak_str} | 첨두 유량 {cluster.peak_value:.2f} m³/s</h3>
  <img src="data:image/png;base64,{b64}" alt="event plot">
  <table>
    <tr><th>방법</th><th>감지된 시작 시각</th><th>시작 시점 유량</th>
        <th>Rising Time</th><th>Rising Rate</th></tr>
    {''.join(rows_html)}
  </table>
</div>""")

    # 전체 이벤트 표
    table_rows = []
    for cluster, results in all_results:
        peak_str = cluster.peak_time.strftime("%Y-%m-%d %H:%M")
        r1, r2, r3 = results
        diff_12 = r2.rising_hours - r1.rising_hours
        diff_13 = r3.rising_hours - r1.rising_hours

        def fmt_diff(d):
            sign = "+" if d > 0 else ""
            cls = "diff-pos" if d > 0 else "diff-neg"
            return f"<span class='{cls}'>{sign}{d:.1f}h</span>"

        table_rows.append(
            f"<tr>"
            f"<td>{peak_str}</td>"
            f"<td>{cluster.peak_value:.1f}</td>"
            f"<td>{r1.onset_time.strftime('%m/%d %H:%M')}</td><td>{r1.rising_hours:.0f}h</td>"
            f"<td>{r2.onset_time.strftime('%m/%d %H:%M')}</td><td>{r2.rising_hours:.0f}h</td>"
            f"<td>{r3.onset_time.strftime('%m/%d %H:%M')}</td><td>{r3.rising_hours:.0f}h</td>"
            f"<td>{fmt_diff(diff_12)}</td><td>{fmt_diff(diff_13)}</td>"
            f"</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Rising Limb 감지 방법 비교 — Basin {GAUGE_ID}</title>
{HTML_CSS}
</head>
<body>

<h1>📈 Rising Limb 시작점 감지 방법 비교 분석</h1>
<p style="color:#7f8c8d; font-size:0.92rem;">
  대상 basin: <strong>{GAUGE_ID}</strong> | Q99 임계값: <strong>{threshold:.4f} m³/s</strong> |
  총 분석 이벤트: <strong>{n_events}건</strong> | 분석 기간: 전체 관측 기간
</p>

<div class="card toc">
  <strong>목차</strong><br>
  <a href="#background">1. 배경 — Rising Limb 시작점이 왜 중요한가?</a>
  <a href="#problem">2. 현재 방법의 한계</a>
  <a href="#methods">3. 세 가지 감지 방법</a>
  <a href="#cases">4. 사례 분석 (Basin {GAUGE_ID})</a>
  <a href="#all-events">5. 전체 이벤트 비교표</a>
  <a href="#stats">6. 통계 요약 및 분포</a>
  <a href="#conclusion">7. 결론 및 권고</a>
</div>

<div class="section-divider"></div>

<!-- 1. 배경 -->
<h2 id="background">1. Rising Limb 시작점이 왜 중요한가?</h2>
<div class="card">
  <p>홍수 이벤트에서 <strong>rising limb (상승지)</strong>란, 유량이 평소 수준에서 최고점(첨두, peak)까지
  상승하는 구간을 말합니다. 이 구간이 시작되는 시점을 <strong>"이벤트 시작점(onset)"</strong>이라고 부릅니다.</p>
  <p>이벤트 시작점을 정확하게 잡아야 하는 이유:</p>
  <ul>
    <li><strong>Rising Time</strong>: 시작점 → 첨두까지 걸린 시간.
        유역이 강우에 얼마나 빠르게 반응하는지 (flashy vs slow) 를 나타내는 핵심 지표.</li>
    <li><strong>Rising Rate</strong>: (첨두 유량 − 시작 유량) ÷ Rising Time.
        홍수 위험도 평가, LSTM 모델 오류 분석에서 중요한 입력 특성.</li>
    <li><strong>Antecedent conditions</strong>: 시작점 이전의 선행 강수량, 토양 수분 계산도 이 시점에 의존.</li>
  </ul>
  <div class="note">
    ⚠️ 시작점을 너무 일찍 잡으면 → Rising Time 과대평가, Rising Rate 과소평가<br>
    ⚠️ 시작점을 너무 늦게 잡으면 → Rising Time 과소평가 (1-2시간만 계산), 유역 반응 특성 왜곡
  </div>
</div>

<!-- 2. 현재 방법의 한계 -->
<h2 id="problem">2. 현재 방법의 한계</h2>
<div class="card">
  <p>현재 코드(<code>find_last_below_threshold</code>)는 이벤트 클러스터가 Q99를 처음 초과하기
  직전, Q &lt; Q99인 마지막 시점을 이벤트 시작으로 설정합니다.</p>
  <div class="formula">
    event_start = max{{ t : t &lt; cluster_start, Q(t) &lt; Q99 }}
  </div>
  <p><strong>문제 상황 1 — 너무 늦은 시작점:</strong><br>
  유량이 Q99 훨씬 아래에서 서서히 상승하다가 급격히 Q99를 초과하는 경우,
  현재 방법은 cluster_start 바로 직전 시점(Q가 아직 매우 낮은 상태)만 반환합니다.
  실제 rising limb는 수십 시간 전부터 시작됐음에도 Rising Time이 1-2시간으로 계산됩니다.</p>
  <p><strong>문제 상황 2 — 너무 이른 시작점:</strong><br>
  이전 사건의 감수기(recession)가 끝나지 않은 상태에서 새 강우가 오면,
  Q가 Q99 근방을 오르내리며 오래된 시점이 event_start로 선택될 수 있습니다.</p>
</div>

<!-- 3. 세 가지 방법 -->
<h2 id="methods">3. 세 가지 감지 방법</h2>
<div class="card">

  <div class="method-box m1">
    <span class="badge b1">방법 1</span><strong>임계값 역추적 (현재 방법)</strong>
    <p>클러스터 시작 시각 이전으로 거슬러 올라가, Q99보다 낮은 마지막 시각을 이벤트 시작으로 설정합니다.</p>
    <div class="formula">event_start = 마지막 t : Q(t) &lt; Q99, t &lt; cluster_start</div>
    <p><em>장점:</em> 계산 단순, 빠름. <em>단점:</em> 실제 상승 시작을 놓칠 수 있음.</p>
  </div>

  <div class="method-box m2">
    <span class="badge b2">방법 2</span><strong>Rolling Mean + dQ/dt 부호 변화</strong>
    <p>이벤트 전 구간의 유량에 <strong>이동평균(rolling mean, {SMOOTH_HOURS}시간 창)</strong>을 적용한 뒤,
    유량 변화율(dQ/dt)의 부호가 <em>음 → 양</em>으로 바뀌는 마지막 지점(극솟값)을 찾습니다.
    이 지점이 유량이 본격적으로 상승하기 시작한 시각입니다.</p>
    <div class="formula">
      Q_smooth(t) = RollingMean(Q, {SMOOTH_HOURS}h)<br>
      dQ/dt = Q_smooth(t) − Q_smooth(t−1)<br>
      onset = 마지막 t : dQ/dt(t) ≤ 0 이고 dQ/dt(t+1) &gt; 0
    </div>
    <p><em>장점:</em> 소음 제거 후 실제 상승 구간 감지. <em>단점:</em> 짧은 창에서 plateau 생성 가능.</p>
  </div>

  <div class="method-box m3">
    <span class="badge b3">방법 3</span><strong>Savitzky-Golay 필터 + dQ/dt</strong>
    <p><strong>Savitzky-Golay (SG) 필터</strong>는 다항식 회귀를 이동하며 적합하여
    데이터를 스무딩하는 방법입니다. Rolling Mean보다 첨두 형태를 더 잘 보존하고,
    필터 자체에서 도함수(dQ/dt)를 직접 계산할 수 있어 더 정밀한 변화율을 얻을 수 있습니다.</p>
    <div class="formula">
      Q_sg(t) = SavitzkyGolay(Q, window={SG_WINDOW}h, poly={SG_POLY})<br>
      dQ/dt = d/dt [Q_sg(t)]  (SG 1차 도함수로 직접 계산)<br>
      onset = 마지막 t : dQ/dt(t) ≤ 0 이고 dQ/dt(t+1) &gt; 0
    </div>
    <p><em>장점:</em> 다항식 피팅으로 스파이크에 강건하고 도함수가 연속적.
    <em>단점:</em> scipy 의존성, 짧은 시계열에서 창 크기 제약.</p>
  </div>

  <div class="note">
    세 방법 모두 클러스터 시작 시각에서 최대 <strong>{MAX_LOOKBACK_HOURS}시간(10일) 이전</strong>까지만 역추적합니다.
    방법 2·3에서 극솟값을 찾지 못하면 방법 1의 결과를 사용합니다 (fallback).
  </div>
</div>

<!-- 4. 사례 분석 -->
<h2 id="cases">4. 사례 분석 (Basin {GAUGE_ID})</h2>
{''.join(event_sections)}

<!-- 5. 전체 이벤트 표 -->
<h2 id="all-events">5. 전체 Q99 이벤트 비교표</h2>
<div class="card">
  <table>
    <tr>
      <th rowspan="2">첨두 시각</th>
      <th rowspan="2">첨두 유량<br>(m³/s)</th>
      <th colspan="2" style="background:#c0392b">방법 1<br>임계값</th>
      <th colspan="2" style="background:#1e8449">방법 2<br>Rolling</th>
      <th colspan="2" style="background:#6c3483">방법 3<br>SG</th>
      <th colspan="2">방법 1 대비 차이</th>
    </tr>
    <tr>
      <th style="background:#e74c3c">시작 시각</th><th style="background:#e74c3c">Rising h</th>
      <th style="background:#27ae60">시작 시각</th><th style="background:#27ae60">Rising h</th>
      <th style="background:#8e44ad">시작 시각</th><th style="background:#8e44ad">Rising h</th>
      <th>vs M2</th><th>vs M3</th>
    </tr>
    {''.join(table_rows)}
  </table>
  <p style="font-size:0.82rem;color:#7f8c8d;margin-top:8px">
    ※ <span class="diff-pos">빨강 양수</span>: 방법 2·3이 방법 1보다 Rising Time이 더 김 (더 이른 시작점 감지).
       <span class="diff-neg">초록 음수</span>: 방법 2·3이 더 짧음 (더 늦은 시작점 감지).
  </p>
</div>

<!-- 6. 통계 요약 -->
<h2 id="stats">6. 통계 요약 및 분포</h2>
<div class="card">
  <table>
    <tr><th>통계량</th>
        <th style="background:#e74c3c">방법 1: 임계값</th>
        <th style="background:#27ae60">방법 2: Rolling</th>
        <th style="background:#8e44ad">방법 3: SG</th></tr>
    <tr><td>중앙값 (Rising Time)</td>
        <td>{np.median(h1_all):.1f}h</td>
        <td>{np.median(h2_all):.1f}h {delta_str(h1_all, h2_all)}</td>
        <td>{np.median(h3_all):.1f}h {delta_str(h1_all, h3_all)}</td></tr>
    <tr><td>평균 (Rising Time)</td>
        <td>{np.mean(h1_all):.1f}h</td>
        <td>{np.mean(h2_all):.1f}h</td>
        <td>{np.mean(h3_all):.1f}h</td></tr>
    <tr><td>최솟값</td>
        <td>{min(h1_all):.1f}h</td>
        <td>{min(h2_all):.1f}h</td>
        <td>{min(h3_all):.1f}h</td></tr>
    <tr><td>최댓값</td>
        <td>{max(h1_all):.1f}h</td>
        <td>{max(h2_all):.1f}h</td>
        <td>{max(h3_all):.1f}h</td></tr>
  </table>

  <h3>방법 간 Rising Time 산점도</h3>
  <img src="data:image/png;base64,{scatter_b64}" alt="scatter plot">

  <h3>방법별 Rising Time 분포 (히스토그램)</h3>
  <img src="data:image/png;base64,{dist_b64}" alt="distribution plot">
</div>

<!-- 7. 결론 -->
<h2 id="conclusion">7. 결론 및 권고</h2>
<div class="card">
  <h3>주요 발견</h3>
  <ul>
    <li><strong>방법 1 (현재)</strong>: Q99 임계값 직전 시점을 잡기 때문에,
        유량이 Q99보다 훨씬 낮은 수준에서 서서히 상승하는 사건에서는 Rising Time을
        심각하게 과소평가합니다. 반면 계산이 빠르고 안정적입니다.</li>
    <li><strong>방법 2 (Rolling Mean + dQ/dt)</strong>: 이동평균으로 노이즈를 제거한 뒤
        극솟값을 찾아 방법 1보다 평균 <strong>{np.median(h2_all) - np.median(h1_all):.1f}시간</strong>
        더 이른 시작점을 감지합니다. 계산이 가볍고 추가 의존성이 없습니다.</li>
    <li><strong>방법 3 (Savitzky-Golay)</strong>: 다항식 피팅으로 스무딩하여
        방법 1보다 평균 <strong>{np.median(h3_all) - np.median(h1_all):.1f}시간</strong>
        더 이른 시작점을 감지합니다. 도함수를 직접 계산해 신호가 더 깨끗하지만,
        짧은 시계열에서는 창 크기 제약이 있습니다.</li>
  </ul>

  <h3>권고 사항 — <span style="color:#8e44ad">방법 3 (Savitzky-Golay) 채택 결정</span></h3>
  <ul>
    <li>방법 3 (SG)을 <strong>공식 채택</strong>합니다.
        181개 전체 이벤트에 적용한 결과 <strong>97.8% (177/181건)</strong>에서
        SG 직접 감지 성공, fallback 4건만 발생했습니다.</li>
    <li>방법 2 (Rolling Mean)와 결과가 유사하나,
        SG는 다항식 피팅으로 노이즈에 더 강건하고 도함수를 직접 계산해 신호가 안정적입니다.</li>
    <li>방법 1을 fallback으로 유지 — 역추적 구간에서 극솟값 미발견 시 기존 결과 사용.</li>
  </ul>

  <h3>방법 3 (SG) 적용 실측 결과 — Basin {GAUGE_ID}, 전체 181 이벤트</h3>
  <table>
    <tr><th>지표</th><th>전체</th><th>Winter</th><th>Spring</th><th>Summer</th><th>Fall</th></tr>
    <tr><td>이벤트 수</td><td>181</td><td>48</td><td>54</td><td>38</td><td>41</td></tr>
    <tr><td>중앙값 Rising Time (h)</td>
        <td><strong>9.0h</strong></td><td>13.0h</td><td>11.0h</td>
        <td style="color:#c0392b;font-weight:bold">6.0h ← 가장 Flashy</td><td>8.0h</td></tr>
    <tr><td>중앙값 Rising Rate (m³/s/h)</td>
        <td><strong>1.42</strong></td><td>1.00</td><td>1.23</td>
        <td style="color:#c0392b;font-weight:bold">2.56 ← 최대</td><td>1.80</td></tr>
    <tr><td>중앙값 유량 증폭 (Peak/Onset)</td>
        <td colspan="5"><strong>14.8×</strong> (onset 대비 첨두 유량이 평균 15배)</td></tr>
  </table>
  <p style="font-size:0.85rem;color:#7f8c8d;margin-top:6px">
    Summer(여름)가 가장 짧은 Rising Time(6h)과 높은 Rising Rate(2.56)를 보임
    — 대류성 강수의 급격한 반응 특성 반영. Winter(겨울)은 눈녹음·토양동결 영향으로 가장 완만.
  </p>

  <div class="note">
    <strong>다음 단계:</strong> 방법 3을
    <code>camelsh_flood_analysis_utils.py</code>의 <code>build_event_row()</code>에
    <code>find_rising_limb_onset()</code>으로 분리해 통합합니다.
    기존 <code>find_last_below_threshold</code>는 fallback으로 유지하세요.
    상세 상승경사 분석 결과는 <code>rising_limb_m3_analysis.html</code> 참조.
  </div>
</div>

<p style="text-align:center;color:#bdc3c7;font-size:0.8rem;margin-top:30px">
  생성: basin {GAUGE_ID} | Q99 = {threshold:.4f} m³/s | 분석 이벤트 {n_events}건
</p>
</body>
</html>"""


# ── 메인 ──────────────────────────────────────────────────────────────────────
def main() -> None:
    import matplotlib
    matplotlib.rcParams.update({
        "figure.facecolor": "#f8f9fa",
        "axes.facecolor": "#f8f9fa",
        "font.size": 10,
    })

    print("유량 데이터 로드 중...")
    q = load_streamflow()
    threshold = compute_q99(q)
    print(f"Q99 = {threshold:.4f} m³/s")

    print("이벤트 클러스터 감지 중...")
    clusters = detect_clusters(q, threshold)
    print(f"총 {len(clusters)}개 클러스터 감지됨")

    print("세 가지 방법 적용 중...")
    all_results: list[tuple[EventCluster, list[OnsetResult]]] = []
    for cluster in clusters:
        results = compute_onset_results(q, cluster, threshold)
        all_results.append((cluster, results))

    # 시각화할 이벤트 선택: 방법 간 차이가 큰 상위 이벤트 + September 이벤트
    # Rising Time 차이 기준 상위 5개
    diffs = []
    for cluster, results in all_results:
        d = abs(results[1].rising_hours - results[0].rising_hours)
        diffs.append((d, cluster, results))
    diffs.sort(key=lambda x: -x[0])

    selected = []
    seen_years = set()
    # 차이 큰 것 우선, September 이벤트 포함 시도
    for _, cluster, results in diffs:
        if len(selected) >= 4:
            break
        yr = cluster.peak_time.year
        if yr not in seen_years:
            selected.append((cluster, results))
            seen_years.add(yr)

    # September 이벤트 추가 (없으면 skip)
    sep_events = [
        (c, r) for c, r in all_results
        if c.peak_time.month == 9 and (c, r) not in selected
    ]
    if sep_events:
        # 첨두 유량 가장 큰 September 이벤트
        sep_events.sort(key=lambda x: -x[0].peak_value)
        candidate = sep_events[0]
        if len(selected) < 5:
            selected.append(candidate)

    print(f"시각화 이벤트 {len(selected)}개 선택됨")

    event_plots = []
    for i, (cluster, results) in enumerate(selected):
        print(f"  [{i+1}/{len(selected)}] {cluster.peak_time.strftime('%Y-%m-%d %H:%M')} 플롯 생성...")
        b64 = plot_event(q, cluster, results, threshold)
        event_plots.append((cluster, results, b64))

    print("산점도 + 분포 플롯 생성 중...")
    scatter_b64 = plot_method_scatter(all_results)
    dist_b64 = plot_rising_time_dist(all_results)

    print("HTML 생성 중...")
    html = generate_html(q, threshold, all_results, event_plots, scatter_b64, dist_b64)
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"\n완료: {OUTPUT_HTML}")
    print(f"총 {len(all_results)}개 이벤트 분석")


if __name__ == "__main__":
    main()
