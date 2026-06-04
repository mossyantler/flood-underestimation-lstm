#!/usr/bin/env python3
# /// script
# dependencies = ["xarray", "pandas", "numpy", "matplotlib", "netCDF4"]
# ///
"""M3 (Savitzky-Golay) onset 기반 rise_h window hydrograph 갤러리 PNG 생성.

rising_limb_m3_spearman.csv의 unique (basin_id, peak_time) window마다
강수(Rainf) + 유량(Streamflow) 2단 hydrograph를 그리고
M3 onset / peak / rising limb 음영 / Q99 임계선 / rise 지표 주석을 표시한다.

관측 위치 구간(obs_class)은 seed마다 다를 수 있어 seed별 집합으로 표기한다.

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
M3_CSV = ROOT / "output/model_analysis/band_signal/method_compare/rising_limb_m3_spearman.csv"
TS_DIR = ROOT / "data/CAMELSH_generic/drbc_expanded_observed_test/time_series"
OUT_DIR = ROOT / "output/model_analysis/band_signal/method_compare/data/rise_h_windows"

BAND_ORDER = ["below_q50", "q50_to_q90", "q90_to_q95", "q95_to_q99", "above_q99"]
BAND_COLORS = {
    "below_q50": "#4393c3",
    "q50_to_q90": "#92c5de",
    "q90_to_q95": "#fddbc7",
    "q95_to_q99": "#f4a582",
    "above_q99": "#d6604d",
}


def normalize_basin_id(v) -> str:
    s = str(v).strip()
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s.zfill(8)


def window_id(basin: str, peak_t: pd.Timestamp) -> str:
    return f"{basin}_{peak_t.strftime('%Y%m%dT%H%M')}"


def load_timeseries(basin: str) -> pd.DataFrame | None:
    for cand in (basin, basin.lstrip("0")):
        p = TS_DIR / f"{cand}.nc"
        if p.exists():
            with xr.open_dataset(p) as ds:
                df = ds[["Rainf", "Streamflow"]].to_dataframe().reset_index()
            df["date"] = pd.to_datetime(df["date"])
            return df.sort_values("date").reset_index(drop=True)
    return None


def build_windows(m3: pd.DataFrame) -> pd.DataFrame:
    """(basin_id, peak_time) 단위로 dedupe. obs_class는 seed별 집합으로."""
    rise_cols = ["onset_time", "onset_q", "peak_q", "rising_hours",
                 "rise_rel_m3", "rise_slope_m3"]
    grp = m3.groupby(["basin_id", "peak_time"])
    rows = []
    for (bid, peak_t), g in grp:
        first = g.iloc[0]
        # seed별 obs_class 집계
        oc_counts = g.groupby("obs_class").size().to_dict()
        # 표시용 primary = 최빈 (동률이면 band 순서상 더 위험한 쪽)
        primary = max(
            oc_counts.items(),
            key=lambda kv: (kv[1], BAND_ORDER.index(kv[0])),
        )[0]
        oc_summary = ", ".join(
            f"{c}×{oc_counts[c]}" for c in BAND_ORDER if c in oc_counts
        )
        rec = {
            "basin_id": bid,
            "peak_time": peak_t,
            "obs_class_primary": primary,
            "obs_class_summary": oc_summary,
            "n_seed": int(g["seed"].nunique()),
        }
        for c in rise_cols:
            rec[c] = first[c]
        rows.append(rec)
    out = pd.DataFrame(rows)
    out["peak_time"] = pd.to_datetime(out["peak_time"])
    out["onset_time"] = pd.to_datetime(out["onset_time"])
    return out.sort_values(["basin_id", "peak_time"]).reset_index(drop=True)


def plot_window(
    row: pd.Series,
    ts: pd.DataFrame,
    q99: float,
    q50: float,
    out_path: Path,
    dpi: int,
) -> bool:
    onset_t = row["onset_time"]
    peak_t = row["peak_time"]
    onset_q = float(row["onset_q"])
    peak_q = float(row["peak_q"])
    rising_h = float(row["rising_hours"])
    rise_slope = float(row["rise_slope_m3"])
    rise_rel = float(row["rise_rel_m3"])
    primary = row["obs_class_primary"]

    span = peak_t - onset_t
    pad = pd.Timedelta(hours=float(np.clip(span.total_seconds() / 3600 * 0.15, 12, 120)))
    plot_start = onset_t - pad
    plot_end = peak_t + pad

    win = ts.loc[(ts["date"] >= plot_start) & (ts["date"] <= plot_end)].copy()
    if win.empty or win["Streamflow"].notna().sum() < 2:
        return False

    fig, (ax_r, ax_q) = plt.subplots(
        nrows=2, ncols=1, figsize=(15, 7.5), sharex=True,
        gridspec_kw={"height_ratios": [1, 2.4], "hspace": 0.07},
    )
    band_c = BAND_COLORS.get(primary, "#888")

    long_flag = "  ⚠ 긴 상승구간" if rising_h > 200 else ""
    title = (
        f"{row['basin_id']} | M3 rise_h window | peak {peak_t:%Y-%m-%d %H:%M}\n"
        f"rising_hours = {rising_h:.0f} h | rise_slope = {rise_slope:.3f} m³/s/h | "
        f"rise_rel = {rise_rel:+.2f} | obs_class(primary) = {primary}{long_flag}"
    )
    fig.suptitle(title, fontsize=13, fontweight="bold")

    # ── 강수 (상단, mm/h) ──
    bar_w = max(0.01, (plot_end - plot_start).total_seconds() / 3600 / 24 / 400)
    ax_r.bar(win["date"], win["Rainf"].fillna(0), width=bar_w,
             color="#4379e8", edgecolor="none", align="center")
    ax_r.axvspan(onset_t, peak_t, color=band_c, alpha=0.12, lw=0)
    ax_r.axvline(onset_t, color="#16a34a", linestyle="--", linewidth=1.3)
    ax_r.axvline(peak_t, color="#dc2626", linestyle="--", linewidth=1.3)
    ax_r.set_ylabel("강수 Rainf\n(mm/h)", fontsize=11)
    ax_r.grid(axis="y", color="#d9d9d9", linewidth=0.6)
    ax_r.set_ylim(bottom=0)
    ax_r.invert_yaxis()  # 강수는 위에서 아래로 (관례)

    # ── 유량 (하단, m³/s) ──
    ax_q.plot(win["date"], win["Streamflow"], color="#111827",
              linewidth=1.7, label="관측 유량 (obs Streamflow)")
    ax_q.axhline(q99, color="#6b7280", linestyle=":", linewidth=1.3,
                 label=f"Q99 = {q99:.2f} m³/s")
    ax_q.axhline(q50, color="#0891b2", linestyle=":", linewidth=1.2, alpha=0.8,
                 label=f"Q50 (관측 중앙값) = {q50:.2f} m³/s")
    ax_q.axvspan(onset_t, peak_t, color=band_c, alpha=0.18, lw=0,
                 label="M3 rising limb (onset→peak)")
    # onset
    ax_q.axvline(onset_t, color="#16a34a", linestyle="--", linewidth=1.4)
    ax_q.scatter([onset_t], [onset_q], color="#16a34a", s=70, zorder=6,
                 edgecolors="white", linewidths=1.0,
                 label=f"M3 onset = {onset_q:.2f} m³/s")
    # peak
    ax_q.axvline(peak_t, color="#dc2626", linestyle="--", linewidth=1.4)
    ax_q.scatter([peak_t], [peak_q], color="#dc2626", s=80, zorder=6,
                 edgecolors="white", linewidths=1.0,
                 label=f"peak = {peak_q:.2f} m³/s")
    # rise slope 보조선 (onset→peak 직선)
    ax_q.plot([onset_t, peak_t], [onset_q, peak_q], color="#7c3aed",
              linestyle="-", linewidth=1.2, alpha=0.7, label="rise_slope 기울기")

    ax_q.set_ylabel("유량 Streamflow\n(m³/s)", fontsize=11)
    ax_q.set_xlabel("시각 (Datetime)", fontsize=11)
    ax_q.grid(axis="y", color="#d9d9d9", linewidth=0.6)
    ax_q.set_ylim(bottom=0)
    ax_q.legend(loc="upper left", frameon=True, fontsize=9)

    # 주석 박스
    txt = (
        f"obs_class(seed별): {row['obs_class_summary']}\n"
        f"onset: {onset_t:%Y-%m-%d %H:%M}\n"
        f"peak:  {peak_t:%Y-%m-%d %H:%M}\n"
        f"Δ = {rising_h:.0f} h"
    )
    ax_q.text(0.985, 0.97, txt, transform=ax_q.transAxes, fontsize=9,
              va="top", ha="right",
              bbox=dict(boxstyle="round,pad=0.5", fc="#fffbeb",
                        ec="#f59e0b", alpha=0.95))

    loc = mdates.AutoDateLocator(minticks=5, maxticks=10)
    ax_q.xaxis.set_major_locator(loc)
    ax_q.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="M3 rise_h window hydrograph 갤러리 PNG 생성")
    ap.add_argument("--dpi", type=int, default=110)
    ap.add_argument("--limit", type=int, default=0, help="디버그용 window 수 제한 (0=전체)")
    ap.add_argument("--skip-existing", action="store_true")
    args = ap.parse_args()

    matplotlib.rcParams.update({
        "font.family": ["Apple SD Gothic Neo", "AppleGothic", "NanumGothic",
                        "Noto Sans CJK KR", "DejaVu Sans"],
        "axes.unicode_minus": False,
    })

    print(f"M3 CSV 로드: {M3_CSV}")
    m3 = pd.read_csv(M3_CSV, dtype={"basin_id": str})
    m3["basin_id"] = m3["basin_id"].map(normalize_basin_id)
    windows = build_windows(m3)
    if args.limit:
        windows = windows.head(args.limit)
    print(f"unique window: {len(windows)} | basin: {windows['basin_id'].nunique()}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts_cache: dict[str, pd.DataFrame | None] = {}
    q99_cache: dict[str, float] = {}
    q50_cache: dict[str, float] = {}

    manifest_rows = []
    ok = miss_ts = fail = 0
    for i, row in windows.iterrows():
        bid = row["basin_id"]
        if bid not in ts_cache:
            ts_cache[bid] = load_timeseries(bid)
            ts = ts_cache[bid]
            if ts is not None:
                q99_cache[bid] = float(np.nanquantile(ts["Streamflow"].values, 0.99))
                q50_cache[bid] = float(np.nanquantile(ts["Streamflow"].values, 0.50))
        ts = ts_cache[bid]
        if ts is None:
            miss_ts += 1
            continue

        wid = window_id(bid, row["peak_time"])
        rel_png = f"{bid}/{wid}.png"
        out_path = OUT_DIR / rel_png

        produced = True
        if not (args.skip_existing and out_path.exists()):
            produced = plot_window(row, ts, q99_cache[bid], q50_cache[bid], out_path, args.dpi)
        if not produced:
            fail += 1
            continue

        ok += 1
        manifest_rows.append({
            "window_id": wid,
            "basin_id": bid,
            "peak_time": row["peak_time"].isoformat(),
            "onset_time": row["onset_time"].isoformat(),
            "rising_hours": round(float(row["rising_hours"]), 2),
            "rise_slope_m3": round(float(row["rise_slope_m3"]), 4),
            "rise_rel_m3": round(float(row["rise_rel_m3"]), 4),
            "onset_q": round(float(row["onset_q"]), 4),
            "peak_q": round(float(row["peak_q"]), 4),
            "q99_threshold": round(q99_cache[bid], 4),
            "q50_threshold": round(q50_cache[bid], 4),
            "obs_class_primary": row["obs_class_primary"],
            "obs_class_summary": row["obs_class_summary"],
            "n_seed": int(row["n_seed"]),
            "plot_path": rel_png,
        })
        if ok % 100 == 0:
            print(f"  ... {ok} plotted")

    man = pd.DataFrame(manifest_rows)
    man_path = OUT_DIR / "rise_h_window_manifest.csv"
    man.to_csv(man_path, index=False)
    print(f"\n완료: ok={ok} fail={fail} miss_ts={miss_ts}")
    print(f"manifest: {man_path} ({len(man)} rows)")


if __name__ == "__main__":
    main()
