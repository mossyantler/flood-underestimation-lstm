#!/usr/bin/env python3
# /// script
# dependencies = ["xarray", "pandas", "numpy", "matplotlib", "netCDF4"]
# ///
"""M4 onset 기반 rise_h window hydrograph 갤러리 PNG 생성.

rising_limb_m4.csv(강수 anchor + MIT + 게이트)를 읽어 window별 강수+유량 hydrograph를
그린다. M3 대비 개선점:
  · onset = 사건 유발 강수 burst 직전 유량 극솟값 (rain_start 마커 함께 표시)
  · onset→peak 길이는 유역별 T_cap으로 제한 (과도 길이 window는 hard-flag)
  · 데이터 공백 구간은 직선으로 잇지 않는다 (시간축 reindex → 결측은 선 끊김)
  · hard/soft auto-flag 사유를 제목·박스에 표시

출력:
  output/model_analysis/band_signal/method_compare/data/rise_h_windows/{basin}/{window_id}.png
  output/model_analysis/band_signal/method_compare/data/rise_h_windows/rise_h_window_manifest.csv
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[3]
M4_CSV = ROOT / "output/model_analysis/band_signal/method_compare/rising_limb_m4.csv"
OBS_CLASS_CSV = ROOT / "output/model_analysis/primary/metrics/tables/ub_location_class_q99.csv"
TS_DIR = ROOT / "data/CAMELSH_generic/drbc_expanded_observed_test/time_series"
OUT_DIR = ROOT / "output/model_analysis/band_signal/method_compare/data/rise_h_windows"

BAND_ORDER = ["below_q50", "q50_to_q90", "q90_to_q95", "q95_to_q99", "above_q99"]
BAND_COLORS = {
    "below_q50": "#4393c3", "q50_to_q90": "#92c5de", "q90_to_q95": "#fddbc7",
    "q95_to_q99": "#f4a582", "above_q99": "#d6604d",
}
HARD_FLAGS = {"no_rain_trigger", "too_long", "data_gap"}


def normalize_basin_id(v) -> str:
    s = str(v).strip()
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s.zfill(8)


def window_id(basin: str, peak_t: pd.Timestamp) -> str:
    return f"{basin}_{peak_t.strftime('%Y%m%dT%H%M')}"


def load_ts(basin: str) -> pd.DataFrame | None:
    for cand in (basin, basin.lstrip("0")):
        p = TS_DIR / f"{cand}.nc"
        if p.exists():
            with xr.open_dataset(p) as ds:
                df = ds[["Rainf", "Streamflow"]].to_dataframe().reset_index()
            df["date"] = pd.to_datetime(df["date"])
            return df.set_index("date").sort_index()
    return None


def obs_class_summary() -> dict:
    df = pd.read_csv(OBS_CLASS_CSV, comment="#", dtype={"basin_id": str})
    df["basin_id"] = df["basin_id"].map(normalize_basin_id)
    df["peak_time"] = pd.to_datetime(df["peak_time"])
    out = {}
    for (bid, pt), g in df.groupby(["basin_id", "peak_time"]):
        cnt = g.groupby("obs_class").size().to_dict()
        primary = max(cnt.items(), key=lambda kv: (kv[1], BAND_ORDER.index(kv[0])))[0]
        summary = ", ".join(f"{c}×{cnt[c]}" for c in BAND_ORDER if c in cnt)
        out[(bid, pt)] = (primary, summary)
    return out


def plot_window(row, ts, oc_primary, oc_summary, out_path, dpi) -> bool:
    peak_t = pd.to_datetime(row["peak_time"])
    onset_t = pd.to_datetime(row.get("onset_time", ""), errors="coerce")
    rain_start = pd.to_datetime(row.get("rain_start", ""), errors="coerce")
    onset_t = None if pd.isna(onset_t) else onset_t
    rain_start = None if pd.isna(rain_start) else rain_start
    q99 = float(row["q99_threshold"])
    flags = str(row.get("flags", "") or "")
    flag_list = [f for f in flags.split(";") if f]
    hard = [f for f in flag_list if f in HARD_FLAGS]
    soft = [f for f in flag_list if f not in HARD_FLAGS]

    # 플롯 범위: onset 있으면 [onset-pad, peak+pad], 없으면 peak 중심
    if onset_t is not None:
        span_h = max((peak_t - onset_t).total_seconds() / 3600, 1)
        pad = pd.Timedelta(hours=int(round(np.clip(span_h * 0.4, 12, 72))))
        plot_start, plot_end = onset_t - pad, peak_t + pad
    else:
        plot_start, plot_end = peak_t - pd.Timedelta(hours=48), peak_t + pd.Timedelta(hours=24)

    # 시간축 reindex → 결측은 NaN (공백 구간 선 끊김, 직선 연결 금지).
    # 격자를 정시(:00)에 맞춰 원자료(시간단위)와 정렬 (분 단위 어긋남 방지).
    full_idx = pd.date_range(plot_start.floor("h"), plot_end.ceil("h"), freq="h")
    win = ts.reindex(full_idx)
    q = win["Streamflow"]
    rain = win["Rainf"]
    if q.notna().sum() < 2:
        return False

    q50 = float(np.nanquantile(ts["Streamflow"].values, 0.50))
    band_c = BAND_COLORS.get(oc_primary, "#888")

    fig, (ax_r, ax_q) = plt.subplots(
        nrows=2, ncols=1, figsize=(15, 7.5), sharex=True,
        gridspec_kw={"height_ratios": [1, 2.4], "hspace": 0.07},
    )

    rising_h = row.get("rising_hours", "")
    rise_slope = row.get("rise_slope_m4", "")
    rise_slope_max = row.get("rise_slope_max_m4", "")
    rise_rel = row.get("rise_rel_m4", "")
    flag_txt = ""
    if hard:
        flag_txt += f"  ✗HARD: {','.join(hard)}"
    if soft:
        flag_txt += f"  △SOFT: {','.join(soft)}"
    title = (
        f"{row['basin_id']} | M4 rise_h window | peak {peak_t:%Y-%m-%d %H:%M}\n"
        f"rising_hours={rising_h} h | rise_slope(avg)={rise_slope} | rise_slope_max(6h)={rise_slope_max} | "
        f"obs_class={oc_primary}{flag_txt}"
    )
    tcolor = "#c0392b" if hard else ("#b7791f" if soft else "#111827")
    fig.suptitle(title, fontsize=12.5, fontweight="bold", color=tcolor)

    bar_w = max(0.01, (plot_end - plot_start).total_seconds() / 3600 / 24 / 400)
    ax_r.bar(full_idx, rain.fillna(0), width=bar_w, color="#4379e8", edgecolor="none", align="center")
    if rain_start is not None:
        ax_r.axvline(rain_start, color="#1d4ed8", linestyle="-", linewidth=1.4, alpha=0.8)
    if onset_t is not None:
        ax_r.axvspan(onset_t, peak_t, color=band_c, alpha=0.12, lw=0)
        ax_r.axvline(onset_t, color="#16a34a", linestyle="--", linewidth=1.2)
    ax_r.axvline(peak_t, color="#dc2626", linestyle="--", linewidth=1.2)
    ax_r.set_ylabel("강수 Rainf\n(mm/h)", fontsize=11)
    ax_r.grid(axis="y", color="#d9d9d9", linewidth=0.6)
    ax_r.set_ylim(bottom=0)
    ax_r.invert_yaxis()

    ax_q.plot(full_idx, q, color="#111827", linewidth=1.7, label="관측 유량 (obs Streamflow)")
    ax_q.axhline(q99, color="#6b7280", linestyle=":", linewidth=1.3, label=f"Q99 = {q99:.2f}")
    ax_q.axhline(q50, color="#0891b2", linestyle=":", linewidth=1.2, alpha=0.8, label=f"Q50(관측중앙) = {q50:.2f}")
    if rain_start is not None:
        ax_q.axvline(rain_start, color="#1d4ed8", linestyle="-", linewidth=1.4, alpha=0.8,
                     label=f"강수 시작 (rain_start)")
    if onset_t is not None:
        onset_q = float(row["onset_q"]) if row.get("onset_q", "") != "" else np.nan
        peak_q = float(row["peak_q"]) if row.get("peak_q", "") != "" else np.nan
        ax_q.axvspan(onset_t, peak_t, color=band_c, alpha=0.18, lw=0, label="M4 rising limb")
        ax_q.axvline(onset_t, color="#16a34a", linestyle="--", linewidth=1.4)
        if not np.isnan(onset_q):
            ax_q.scatter([onset_t], [onset_q], color="#16a34a", s=70, zorder=6,
                         edgecolors="white", linewidths=1.0, label=f"M4 onset = {onset_q:.2f}")
        if not np.isnan(peak_q):
            ax_q.scatter([peak_t], [peak_q], color="#dc2626", s=80, zorder=6,
                         edgecolors="white", linewidths=1.0, label=f"peak = {peak_q:.2f}")
            if not np.isnan(onset_q):
                ax_q.plot([onset_t, peak_t], [onset_q, peak_q], color="#7c3aed",
                          linewidth=1.2, alpha=0.7, label="rise_slope 기울기")
    ax_q.axvline(peak_t, color="#dc2626", linestyle="--", linewidth=1.4)
    ax_q.set_ylabel("유량 Streamflow\n(m³/s)", fontsize=11)
    ax_q.set_xlabel("시각 (Datetime)", fontsize=11)
    ax_q.grid(axis="y", color="#d9d9d9", linewidth=0.6)
    ax_q.set_ylim(bottom=0)
    ax_q.legend(loc="upper left", frameon=True, fontsize=8.5)

    # flag 박스
    box_lines = [f"obs_class(seed): {oc_summary}"]
    if hard:
        box_lines.append("✗ HARD flag (통계 제외):")
        box_lines += [f"   · {f}" for f in hard]
    if soft:
        box_lines.append("△ SOFT flag (주의):")
        box_lines += [f"   · {f}" for f in soft]
    if not flag_list:
        box_lines.append("✓ clean (단일 event 기준 통과)")
    boxc = "#fff1f2" if hard else ("#fffbeb" if soft else "#f0fdf4")
    edgec = "#fca5a5" if hard else ("#f59e0b" if soft else "#86efac")
    ax_q.text(0.985, 0.97, "\n".join(box_lines), transform=ax_q.transAxes, fontsize=8.5,
              va="top", ha="right",
              bbox=dict(boxstyle="round,pad=0.5", fc=boxc, ec=edgec, alpha=0.96))

    loc = mdates.AutoDateLocator(minticks=5, maxticks=10)
    ax_q.xaxis.set_major_locator(loc)
    ax_q.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="M4 onset rise_h window 갤러리 PNG 생성")
    ap.add_argument("--dpi", type=int, default=110)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    matplotlib.rcParams.update({
        "font.family": ["Apple SD Gothic Neo", "AppleGothic", "DejaVu Sans"],
        "axes.unicode_minus": False,
    })

    m4 = pd.read_csv(M4_CSV, dtype={"basin_id": str})
    m4["basin_id"] = m4["basin_id"].map(normalize_basin_id)
    if args.limit:
        m4 = m4.head(args.limit)
    print(f"M4 window: {len(m4)} | basin: {m4['basin_id'].nunique()}")

    oc = obs_class_summary()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts_cache: dict[str, pd.DataFrame | None] = {}

    rows = []
    ok = miss = fail = 0
    for _, row in m4.iterrows():
        bid = row["basin_id"]
        if bid not in ts_cache:
            ts_cache[bid] = load_ts(bid)
        ts = ts_cache[bid]
        if ts is None:
            miss += 1
            continue
        peak_t = pd.to_datetime(row["peak_time"])
        primary, summary = oc.get((bid, peak_t), ("?", "-"))
        wid = window_id(bid, peak_t)
        rel = f"{bid}/{wid}.png"
        if not plot_window(row, ts, primary, summary, OUT_DIR / rel, args.dpi):
            fail += 1
            continue
        ok += 1
        rows.append({
            "window_id": wid, "basin_id": bid,
            "peak_time": row["peak_time"], "onset_time": row.get("onset_time", ""),
            "rain_start": row.get("rain_start", ""), "lag_h": row.get("lag_h", ""),
            "rising_hours": row.get("rising_hours", ""),
            "rise_slope_m4": row.get("rise_slope_m4", ""),
            "rise_slope_max_m4": row.get("rise_slope_max_m4", ""),
            "rise_rel_m4": row.get("rise_rel_m4", ""),
            "onset_q": row.get("onset_q", ""), "peak_q": row.get("peak_q", ""),
            "q99_threshold": row["q99_threshold"], "basin_tcap_h": row.get("basin_tcap_h", ""),
            "obs_class_primary": primary, "obs_class_summary": summary,
            "flags": row.get("flags", ""), "hard_flags": row.get("hard_flags", ""),
            "soft_flags": row.get("soft_flags", ""), "clean": bool(row["clean"]),
            "plot_path": rel,
        })
        if ok % 100 == 0:
            print(f"  ... {ok}")

    man = pd.DataFrame(rows)
    man_path = OUT_DIR / "rise_h_window_manifest.csv"
    man.to_csv(man_path, index=False)
    print(f"완료: ok={ok} fail={fail} miss={miss}")
    print(f"manifest: {man_path} ({len(man)} rows, clean={man['clean'].sum()})")


if __name__ == "__main__":
    main()
