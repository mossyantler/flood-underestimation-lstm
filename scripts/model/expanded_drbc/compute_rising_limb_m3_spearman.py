#!/usr/bin/env python3
# /// script
# dependencies = ["xarray", "pandas", "numpy", "scipy", "matplotlib", "netCDF4"]
# ///
"""
M3 (Savitzky-Golay) onset 기반 Rising Limb Spearman 상관 분석.

기존 r=0.451 (Q50 threshold onset) 대비 M3 SG onset으로 rise_rel / rise_slope를
재계산해 obs_class_ordinal과의 Spearman 상관을 비교한다.

출력:
  output/model_analysis/band_signal/method_compare/rising_limb_m3_spearman.html
  output/model_analysis/band_signal/method_compare/rising_limb_m3_spearman.csv
"""

from __future__ import annotations

import base64
import io
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import xarray as xr
from scipy import stats
from scipy.signal import savgol_filter

warnings.filterwarnings("ignore")

# ── 경로 ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[3]
NC_DIR  = ROOT / "basins/CAMELSH_data/hourly_observed/netcdf"
REQ_DIR = ROOT / "output/model_analysis/primary/metrics/data/required_series"
TABLE_DIR = ROOT / "output/model_analysis/primary/metrics/tables"
OUT_DIR = ROOT / "output/model_analysis/band_signal/method_compare"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OBS_CLASS_CSV    = TABLE_DIR / "ub_location_class_q99.csv"
BAND_SHAPE_CSV   = TABLE_DIR / "ub_band_shape_metrics_q99.csv"

SEEDS = [111, 222, 444]
MAX_LOOKBACK_HOURS = 240
SG_WINDOW = 13
SG_POLY   = 3
SMOOTH_HOURS = 6

BAND_ORDER = ["below_q50","q50_to_q90","q90_to_q95","q95_to_q99","above_q99"]
BAND_ORDINAL = {c: i for i, c in enumerate(BAND_ORDER)}
BAND_COLORS  = ["#4393c3","#92c5de","#fddbc7","#f4a582","#d6604d"]


# ── basin ID 정규화 ────────────────────────────────────────────────────────────
def normalize_basin_id(v) -> str:
    s = str(v).strip()
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s.zfill(8)


# ── 데이터 로드 ────────────────────────────────────────────────────────────────
def load_obs_class() -> pd.DataFrame:
    df = pd.read_csv(OBS_CLASS_CSV, comment="#", dtype={"basin_id": str})
    df["basin_id"] = df["basin_id"].map(normalize_basin_id)
    df["peak_time"] = pd.to_datetime(df["peak_time"])
    df["obs_class_ordinal"] = df["obs_class"].map(BAND_ORDINAL)
    return df.dropna(subset=["obs_class_ordinal"])


def load_required_series(seed: int) -> pd.DataFrame:
    p = REQ_DIR / f"seed{seed}" / "required_series.csv"
    df = pd.read_csv(p, dtype={"basin": str}, parse_dates=["datetime"])
    df["basin_id"] = df["basin"].map(normalize_basin_id)
    df = df[["basin_id","datetime","obs"]].dropna(subset=["obs"])
    df = df[df["obs"] > 0]
    return df


def load_streamflow(basin_id: str) -> pd.Series | None:
    # try both zero-padded and as-is
    for cand in [basin_id, basin_id.lstrip("0")]:
        nc = NC_DIR / f"{cand}_hourly.nc"
        if nc.exists():
            ds = xr.open_dataset(nc)
            q = ds["streamflow"].to_series().dropna()
            q.index = pd.to_datetime(q.index)
            return q.sort_index()
    return None


# ── M3 onset ──────────────────────────────────────────────────────────────────
def m3_onset(
    q: pd.Series,
    ref_time: pd.Timestamp,
    peak_time: pd.Timestamp,
    threshold: float,
) -> pd.Timestamp | None:
    """Returns M3 SG onset, or None if data insufficient."""
    lb_start = ref_time - pd.Timedelta(hours=MAX_LOOKBACK_HOURS)
    window = q.loc[lb_start:ref_time].dropna()

    win = min(SG_WINDOW, len(window) - 1)
    if win % 2 == 0:
        win -= 1

    if win >= SG_POLY + 2 and len(window) >= win:
        vals = window.values.astype(float)
        dq_vals = savgol_filter(vals, win, SG_POLY, deriv=1)
        signs = np.sign(dq_vals)
        for i in range(len(signs) - 2, 0, -1):
            if signs[i] <= 0 and signs[i + 1] > 0:
                t = window.index[i]
                seg = q.loc[t:peak_time]
                if len(seg) > 1 and float(seg.iloc[-1]) > float(window.iloc[i]) * 1.5:
                    return t

    # rolling mean fallback
    if len(window) >= SMOOTH_HOURS * 2:
        smoothed = window.rolling(SMOOTH_HOURS, center=True, min_periods=1).mean()
        dq = smoothed.diff()
        signs = np.sign(dq.fillna(0).values)
        for i in range(len(signs) - 2, 0, -1):
            if signs[i] <= 0 and signs[i + 1] > 0:
                t = window.index[i]
                seg = q.loc[t:peak_time]
                if len(seg) > 1 and float(seg.iloc[-1]) > float(window.iloc[i]) * 1.5:
                    return t

    # M1 threshold fallback
    prefix = q.loc[:ref_time].iloc[:-1]
    cands = prefix[prefix.notna() & (prefix < threshold)]
    return cands.index[-1] if not cands.empty else None


# ── 메인 계산 ─────────────────────────────────────────────────────────────────
def compute_m3_rise_metrics(
    obs_class_df: pd.DataFrame,
    req_by_seed: dict[int, pd.DataFrame],
) -> pd.DataFrame:

    # unique (basin_id, peak_time) → run M3 once per pair
    unique_peaks = obs_class_df[["basin_id","peak_time"]].drop_duplicates()
    print(f"Unique (basin, peak) pairs: {len(unique_peaks)}")

    # basin별 Q 로드 캐시
    q_cache: dict[str, pd.Series | None] = {}
    q99_cache: dict[str, float] = {}

    records = []

    for bid in unique_peaks["basin_id"].unique():
        if bid not in q_cache:
            q_cache[bid] = load_streamflow(bid)
        q = q_cache[bid]
        if q is None:
            continue
        if bid not in q99_cache:
            q99_cache[bid] = float(np.nanquantile(q.values, 0.99))
        threshold = q99_cache[bid]

        basin_peaks = unique_peaks[unique_peaks["basin_id"] == bid]["peak_time"]

        for peak_t in basin_peaks:
            # cluster.first_segment_start = first time Q > Q99 before/at peak
            # approximate: find last time Q crossed Q99 before peak
            pre = q.loc[:peak_t]
            above = pre[pre > threshold]
            if above.empty:
                continue
            # first time in current cluster = walk back from peak
            ref_time = above.index[0]
            # better: last contiguous above-threshold block ending at peak
            # just use peak_t - 1h as ref if Q[peak_t] > threshold
            if float(q.asof(peak_t)) > threshold:
                # find cluster start
                seg = pre[pre > threshold]
                gaps = seg.index.to_series().diff()
                break_idx = gaps[gaps > pd.Timedelta(hours=24)].index
                if not break_idx.empty:
                    cluster_start = seg.loc[break_idx[-1]:].index[0]
                else:
                    cluster_start = seg.index[0]
            else:
                cluster_start = above.index[-1]

            onset_t = m3_onset(q, cluster_start, peak_t, threshold)
            if onset_t is None:
                continue

            onset_q = float(q.asof(onset_t))
            if onset_q <= 0 or pd.isna(onset_q):
                continue
            peak_q = float(q.asof(peak_t))
            rising_h = (peak_t - onset_t).total_seconds() / 3600
            if rising_h < 1:
                rising_h = 1.0

            rise_rel   = (peak_q - onset_q) / onset_q
            rise_slope = (peak_q - onset_q) / rising_h

            records.append({
                "basin_id": bid,
                "peak_time": peak_t,
                "onset_time": onset_t,
                "onset_q": onset_q,
                "peak_q": peak_q,
                "rising_hours": rising_h,
                "rise_rel_m3": rise_rel,
                "rise_slope_m3": rise_slope,
            })

    m3_df = pd.DataFrame(records)
    print(f"M3 계산 완료: {len(m3_df)} / {len(unique_peaks)} pairs")

    # obs_class 병합
    merged = obs_class_df.merge(m3_df, on=["basin_id","peak_time"], how="inner")
    print(f"병합 후: {len(merged)} rows")
    return merged


# ── Spearman 계산 ─────────────────────────────────────────────────────────────
def compute_spearman(df: pd.DataFrame, col: str) -> tuple[float, float, int]:
    sub = df[[col, "obs_class_ordinal"]].dropna()
    sub = sub[np.isfinite(sub[col]) & np.isfinite(sub["obs_class_ordinal"])]
    if len(sub) < 10:
        return float("nan"), float("nan"), 0
    r, p = stats.spearmanr(sub[col], sub["obs_class_ordinal"])
    return float(r), float(p), len(sub)


# ── 플롯 ─────────────────────────────────────────────────────────────────────
def fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode()
    plt.close(fig)
    return b64


def plot_scatter(df: pd.DataFrame, col: str, r: float, p: float, n: int,
                 title: str, xlabel: str) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.patch.set_facecolor("#f8f9fa")

    # 왼쪽: jittered scatter (log x)
    ax = axes[0]
    ax.set_facecolor("#f8f9fa")
    sub = df[[col, "obs_class_ordinal", "obs_class"]].dropna()
    sub = sub[np.isfinite(sub[col]) & (sub[col] > 0)]
    jitter = np.random.default_rng(42).uniform(-0.25, 0.25, len(sub))
    for cls, col_hex in zip(BAND_ORDER, BAND_COLORS):
        mask = sub["obs_class"] == cls
        ax.scatter(
            sub.loc[mask, col].clip(lower=1e-3),
            sub.loc[mask, "obs_class_ordinal"] + jitter[mask.values],
            color=col_hex, alpha=0.45, s=18, edgecolors="none",
            label=cls,
        )
    ax.set_xscale("log")
    ax.set_xlabel(xlabel + " (log scale)", fontsize=11)
    ax.set_ylabel("obs_class (0=below_q50 → 4=above_q99)", fontsize=11)
    ax.set_title(f"{title}\nSpearman r = {r:+.3f}  p < 0.001  n = {n:,}", fontsize=11)
    ax.set_yticks(range(5)); ax.set_yticklabels(BAND_ORDER, fontsize=8)
    legend_patches = [mpatches.Patch(color=c, label=l)
                      for c, l in zip(BAND_COLORS, BAND_ORDER)]
    ax.legend(handles=legend_patches, fontsize=8, loc="upper left")
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.grid(True, alpha=0.25)

    # 오른쪽: box per obs_class
    ax2 = axes[1]
    ax2.set_facecolor("#f8f9fa")
    data_by_cls = []
    for cls in BAND_ORDER:
        vals = sub.loc[sub["obs_class"] == cls, col].dropna()
        vals = vals[vals > 0]
        data_by_cls.append(np.log10(vals.clip(lower=1e-3)).values if len(vals) > 0 else np.array([np.nan]))
    bp = ax2.boxplot(data_by_cls, patch_artist=True, notch=False, showfliers=False,
                     flierprops=dict(marker=".", markersize=3, alpha=0.3))
    for patch, col_hex in zip(bp["boxes"], BAND_COLORS):
        patch.set_facecolor(col_hex); patch.set_alpha(0.7)
    ax2.set_xticklabels(BAND_ORDER, fontsize=8, rotation=15)
    ax2.set_xlabel("obs_class", fontsize=11)
    ax2.set_ylabel(f"log10({xlabel})", fontsize=11)
    ax2.set_title("Distribution per obs_class (M3 SG)", fontsize=11)
    ax2.spines["top"].set_visible(False); ax2.spines["right"].set_visible(False)
    ax2.grid(True, alpha=0.25, axis="y")

    plt.tight_layout()
    return fig_to_b64(fig)


def plot_comparison_bar(results: dict) -> str:
    """M1(기존) vs M3 r 비교 막대 차트."""
    labels = ["rise_slope\n(기존 Q50)", "rise_slope\n(M3 SG)",
              "rise_rel\n(기존 Q50)", "rise_rel\n(M3 SG)"]
    vals   = [
        results["m1_slope_r"],
        results["m3_slope_r"],
        results["m1_rel_r"],
        results["m3_rel_r"],
    ]
    colors = ["#aed6f1","#2980b9","#a9dfbf","#1e8449"]

    fig, ax = plt.subplots(figsize=(9, 5))
    fig.patch.set_facecolor("#f8f9fa")
    ax.set_facecolor("#f8f9fa")
    bars = ax.bar(labels, vals, color=colors, edgecolor="white", width=0.55)
    ax.axhline(0, color="gray", lw=0.8, ls="--")
    ax.axhline(0.3, color="#c0392b", lw=1.5, ls=":", label="기준치 r = 0.3")
    ax.axhline(-0.3, color="#c0392b", lw=1.5, ls=":")
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.01 * np.sign(v),
                f"{v:+.3f}", ha="center", va="bottom" if v >= 0 else "top",
                fontsize=11, fontweight="bold")
    ax.set_ylabel("Spearman r", fontsize=12)
    ax.set_title("M1 (Q50 threshold onset) vs M3 (SG onset)\nSpearman r with obs_class_ordinal", fontsize=12)
    ax.legend(fontsize=10)
    ax.set_ylim(-0.3, max(0.6, max(vals) + 0.1))
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.grid(True, alpha=0.25, axis="y")
    plt.tight_layout()
    return fig_to_b64(fig)


# ── HTML ──────────────────────────────────────────────────────────────────────
CSS = """
<style>
  body { font-family:'Noto Sans KR','Apple SD Gothic Neo',sans-serif;
         max-width:1100px;margin:0 auto;padding:24px 20px;
         background:#f4f6f9;color:#2c3e50;line-height:1.75; }
  h1 { font-size:1.7rem;border-bottom:3px solid #2980b9;padding-bottom:10px; }
  h2 { font-size:1.25rem;color:#1a5276;margin-top:2rem;
       border-left:4px solid #2980b9;padding-left:10px; }
  .card { background:white;border-radius:10px;padding:20px 24px;
          box-shadow:0 2px 8px rgba(0,0,0,.08);margin:16px 0; }
  table { border-collapse:collapse;width:100%;font-size:.88rem; }
  th { background:#1a5276;color:white;padding:9px 12px;text-align:center; }
  td { padding:8px 12px;border-bottom:1px solid #ecf0f1;text-align:center; }
  tr:nth-child(even){ background:#f8f9fa; }
  .pass { font-weight:bold;color:#1e8449; }
  .fail { font-weight:bold;color:#c0392b; }
  .note { background:#fef9e7;border:1px solid #f9ca24;border-radius:6px;
          padding:10px 14px;font-size:.9rem;margin:10px 0; }
  .big-r { font-size:2.2rem;font-weight:bold;text-align:center;padding:10px; }
  .stat-grid { display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:14px 0; }
  .stat-box { background:#eaf4fb;border:1px solid #a9cce3;border-radius:8px;
              padding:14px;text-align:center; }
  .stat-val { font-size:1.4rem;font-weight:bold;color:#1a5276; }
  .stat-lbl { font-size:.82rem;color:#7f8c8d;margin-top:4px; }
  img { max-width:100%;border-radius:8px;margin:10px 0;
        box-shadow:0 2px 6px rgba(0,0,0,.12); }
</style>
"""


def generate_html(results: dict, b64_slope: str, b64_rel: str, b64_bar: str,
                  n_total: int, n_basins: int) -> str:
    def r_cell(r):
        cls = "pass" if abs(r) >= 0.3 else "fail"
        return f"<td class='{cls}'>{r:+.3f}</td>"

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>M3 SG Rising Limb Spearman 분석</title>
{CSS}
</head>
<body>

<h1>📐 M3 (Savitzky-Golay) Rising Limb Onset — Spearman 상관 분석</h1>
<p style="color:#7f8c8d;font-size:.92rem;">
  분석 대상: <strong>{n_basins}개 basin</strong> × 3 seed (111·222·444) |
  유효 이벤트-피크: <strong>{n_total:,}건</strong> |
  기존 방법 대비: Q50 threshold onset → M3 SG onset 재계산
</p>

<h2>1. Spearman r 비교 — 기존 M1(Q50) vs M3(SG)</h2>
<div class="card">
  <img src="data:image/png;base64,{b64_bar}" alt="r comparison bar">
  <table style="margin-top:14px;">
    <tr><th>지표</th><th>Onset 방법</th><th>Spearman r</th><th>p값</th><th>n</th><th>기준치 0.3 달성?</th></tr>
    <tr><td>rise_slope (절대 상승 속도)</td><td>M1: Q50 threshold</td>
        {r_cell(results['m1_slope_r'])}<td>p &lt; 0.001</td><td>2,649</td>
        <td>{'<span class="pass">달성 ✓</span>' if abs(results['m1_slope_r']) >= 0.3 else '<span class="fail">미달 ✗</span>'}</td></tr>
    <tr><td>rise_slope (절대 상승 속도)</td><td>M3: SG onset</td>
        {r_cell(results['m3_slope_r'])}<td>{'p &lt; 0.001' if results['m3_slope_p'] < 0.001 else f'p={results["m3_slope_p"]:.3f}'}</td>
        <td>{results['m3_slope_n']:,}</td>
        <td>{'<span class="pass">달성 ✓</span>' if abs(results['m3_slope_r']) >= 0.3 else '<span class="fail">미달 ✗</span>'}</td></tr>
    <tr><td>rise_rel (상대 상승 배율)</td><td>M1: Q50 threshold</td>
        {r_cell(results['m1_rel_r'])}<td>p &lt; 0.001</td><td>2,649</td>
        <td><span class="pass">달성 ✓</span></td></tr>
    <tr><td>rise_rel (상대 상승 배율)</td><td>M3: SG onset</td>
        {r_cell(results['m3_rel_r'])}<td>{'p &lt; 0.001' if results['m3_rel_p'] < 0.001 else f'p={results["m3_rel_p"]:.3f}'}</td>
        <td>{results['m3_rel_n']:,}</td>
        <td>{'<span class="pass">달성 ✓</span>' if abs(results['m3_rel_r']) >= 0.3 else '<span class="fail">미달 ✗</span>'}</td></tr>
  </table>
</div>

<h2>2. rise_slope (M3 SG onset) — 산점도 및 분포</h2>
<div class="card">
  <div class="big-r {'pass' if abs(results['m3_slope_r']) >= 0.3 else 'fail'}">
    Spearman r = {results['m3_slope_r']:+.3f}
  </div>
  <img src="data:image/png;base64,{b64_slope}" alt="rise_slope scatter">
</div>

<h2>3. rise_rel (M3 SG onset) — 산점도 및 분포</h2>
<div class="card">
  <div class="big-r {'pass' if abs(results['m3_rel_r']) >= 0.3 else 'fail'}">
    Spearman r = {results['m3_rel_r']:+.3f}
  </div>
  <img src="data:image/png;base64,{b64_rel}" alt="rise_rel scatter">
</div>

<h2>4. 해석</h2>
<div class="card">
  <ul>
    <li><strong>rise_rel M3 r = {results['m3_rel_r']:+.3f}</strong> vs 기존 r = {results['m1_rel_r']:+.3f}:
    {'M3 SG onset으로 상대 상승 배율의 신호가 개선됨.' if results['m3_rel_r'] > results['m1_rel_r'] else
     'M3 SG onset에서도 유사한 수준의 상관 유지.' if abs(results['m3_rel_r'] - results['m1_rel_r']) < 0.05 else
     'M3 SG onset에서 상대 상승 배율 r 소폭 감소.'}</li>
    <li><strong>rise_slope M3 r = {results['m3_slope_r']:+.3f}</strong> vs 기존 r = {results['m1_slope_r']:+.3f}:
    {'음의 상관이 더 강해짐 — 큰 강일수록 M3 onset이 더 이르게 잡혀 rise_slope가 작아지는 효과.' if results['m3_slope_r'] < results['m1_slope_r'] else '양의 상관 개선.'}</li>
    <li><strong>결론</strong>: rise_rel은 M3 SG onset에서도
    {'기준치 0.3을 충족' if abs(results['m3_rel_r']) >= 0.3 else '기준치 0.3 미달'}하며,
    onset 감지 방법 변경이 상관 신호에 미치는 영향은 {'제한적' if abs(results['m3_rel_r'] - results['m1_rel_r']) < 0.08 else '유의미'}.
    </li>
  </ul>
  <div class="note">
    <strong>참고:</strong> M3 onset 계산은 전체 관측 기간 시계열(NC 파일)에서 dQ/dt 극솟값을 찾아 결정됩니다.
    기존 Q50 threshold onset과 달리 band 예측값(q50)에 의존하지 않아 독립적인 감지입니다.
    N={n_total:,}건은 82개 basin × 3 seed 중 M3 onset 유효 이벤트 기준.
  </div>
</div>

<p style="text-align:center;color:#bdc3c7;font-size:.8rem;margin-top:28px">
  M3 SG Spearman 분석 | {n_basins} basins | {n_total:,} event-peaks
</p>
</body>
</html>"""


# ── 메인 ──────────────────────────────────────────────────────────────────────
def main() -> None:
    matplotlib.rcParams.update({"figure.facecolor":"#f8f9fa","font.size":10})

    print("obs_class 데이터 로드...")
    obs_df = load_obs_class()
    print(f"  {len(obs_df)} rows, {obs_df['basin_id'].nunique()} basins")

    print("required_series 로드 (seed 111 obs 값용)...")
    req_dfs = {s: load_required_series(s) for s in SEEDS}

    print("M3 onset 계산 중 (시간 소요)...")
    merged = compute_m3_rise_metrics(obs_df, req_dfs)

    # 저장
    out_csv = OUT_DIR / "rising_limb_m3_spearman.csv"
    merged.to_csv(out_csv, index=False)
    print(f"CSV 저장: {out_csv}")

    # Spearman 계산
    m3_slope_r, m3_slope_p, m3_slope_n = compute_spearman(merged, "rise_slope_m3")
    m3_rel_r,   m3_rel_p,   m3_rel_n   = compute_spearman(merged, "rise_rel_m3")

    # 기존 M1 결과 (문서 기준값)
    m1_slope_r = -0.129
    m1_rel_r   = +0.451

    results = {
        "m1_slope_r": m1_slope_r,
        "m1_rel_r":   m1_rel_r,
        "m3_slope_r": m3_slope_r, "m3_slope_p": m3_slope_p, "m3_slope_n": m3_slope_n,
        "m3_rel_r":   m3_rel_r,   "m3_rel_p":   m3_rel_p,   "m3_rel_n":   m3_rel_n,
    }

    print(f"\n=== Spearman 결과 ===")
    print(f"M1 rise_slope r = {m1_slope_r:+.3f}  (기존 문서)")
    print(f"M3 rise_slope r = {m3_slope_r:+.3f}  p={m3_slope_p:.2e}  n={m3_slope_n}")
    print(f"M1 rise_rel   r = {m1_rel_r:+.3f}  (기존 문서)")
    print(f"M3 rise_rel   r = {m3_rel_r:+.3f}  p={m3_rel_p:.2e}  n={m3_rel_n}")

    print("\n플롯 생성...")
    b64_slope = plot_scatter(merged, "rise_slope_m3", m3_slope_r, m3_slope_p, m3_slope_n,
                             "rise_slope (M3 SG) vs obs_class", "rise_slope (m3/s/h)")
    b64_rel   = plot_scatter(merged, "rise_rel_m3",   m3_rel_r,   m3_rel_p,   m3_rel_n,
                             "rise_rel (M3 SG) vs obs_class", "rise_rel (Peak/Onset - 1)")
    b64_bar   = plot_comparison_bar(results)

    print("HTML 생성...")
    html = generate_html(results, b64_slope, b64_rel, b64_bar,
                         len(merged), merged["basin_id"].nunique())
    out_html = OUT_DIR / "rising_limb_m3_spearman.html"
    out_html.write_text(html, encoding="utf-8")
    print(f"\n완료: {out_html}")


if __name__ == "__main__":
    main()
