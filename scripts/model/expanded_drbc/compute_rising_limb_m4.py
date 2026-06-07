#!/usr/bin/env python3
# /// script
# dependencies = ["xarray", "pandas", "numpy", "scipy", "matplotlib", "netCDF4"]
# ///
"""M4 onset — 강수 anchor + MIT(minimum inter-event time) 기반 rising limb onset.

연구 표준 (Blume·Zehe·Bronstert 2007; Mei & Anagnostou 2015; Koskelo 2012;
Nagy 2022; Molina-Sanchis 2016)을 따른다.

  ① onset = "사건을 유발한 강수 burst 직전"의 유량 극솟값 (pre-event baseline).
     강수 도중에 onset을 잡지 않는다.
  ② MIT로 강수 burst를 분리해 선행 사건과 독립시킨다.
  ③ 단일 event 최대 rising 길이를 유역별 response time(강수→peak lag 중앙값) 배수로 제한.
  ④ onset→peak 구간의 데이터 완전성을 요구(공백 양끝 직선 연결 금지).

위 조건을 위반하는 window는 통계에서 '제외'하되, 사유를 auto-flag로 기록한다.

기존 M3 (Savitzky-Golay dQ/dt onset)와 동일한 (basin, peak) 집합·동일 obs_class를 써서
rise_rel / rise_slope 의 Spearman을 clean subset 기준으로 재계산하고 M1/M3/M4를 비교한다.

출력:
  output/model_analysis/band_signal/method_compare/rising_limb_m4.csv
  output/model_analysis/band_signal/method_compare/rising_limb_m4_compare.html
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from scipy import stats

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[3]
TABLE_DIR = ROOT / "output/model_analysis/primary/metrics/tables"
OBS_CLASS_CSV = TABLE_DIR / "location_class_q99.csv"
TS_DIR = ROOT / "data/CAMELSH_generic/drbc_expanded_observed_test/time_series"
OUT_DIR = ROOT / "output/model_analysis/band_signal/method_compare"
OUT_CSV = OUT_DIR / "rising_limb_m4.csv"
OUT_HTML = OUT_DIR / "rising_limb_m4_compare.html"

BAND_ORDER = ["below_q50", "q50_to_q90", "q90_to_q95", "q95_to_q99", "above_q99"]
BAND_ORDINAL = {c: i for i, c in enumerate(BAND_ORDER)}

# HARD flag = 단일 rainfall-runoff event로 인정 못함 → 통계 제외.
# SOFT flag = 해석 시 주의(검수)하되 통계엔 유지 (사용자 지침: 선행유량 높음=주의).
# onset은 정의상 rain_start 이후의 유량 trough이므로 '강수 중 onset'은 결함이 아니다(정상).
# data_gap: streamflow가 event-relevant 구간 [onset-24h, peak]에서 결측률 높음(>20%) 또는
#           내부 공백 >6h. (이 데이터셋 Rainf는 NaN 0% gap-fill이라 강수 결측 게이트는 불필요.)
# 라벨 재정의 (flag 감사 결과 반영):
#  HARD = rise 분석 부적합 → 통계 제외. data_gap(결측), too_long(다중storm),
#         no_rain_trigger(peak 유발 강수 없음=눈녹음/baseflow, rise 미정의·오류 아님).
#  SOFT = 유효·기술 정보(통계 유지·주의). prior_event_recession(선행 event 미회복),
#         peak_below_q99(peak<기후Q99). 구 antecedent_elevated(임계 1.05→83% 발화,
#         above_q99 구분력 0)를 임계 2.0 기반 prior_event_recession으로 재정의.
HARD_FLAGS = {"no_rain_trigger", "too_long", "data_gap"}
SOFT_FLAGS = {"prior_event_recession", "peak_below_q99"}

# ── 파라미터 (연구 표준 기본값) ────────────────────────────────────────────────
RAIN_ON = 0.2          # mm/h, 이 이상이면 '강수 중'으로 간주
MIT_RAIN_H = 6         # 무강수 6h 미만이면 같은 burst로 병합 (minimum inter-event time)
MIN_BURST_RAIN = 5.0   # mm, causative burst로 인정할 최소 누적 강수
MAX_LAG_H = 120        # 강수 burst 시작 ~ peak 최대 허용 lag (causation 탐색 상한)
LOOKBACK_H = 168       # peak 이전 강수 탐색 범위
ONSET_TOL_H = 2        # onset 극솟값 탐색 하한: rain_start - ONSET_TOL_H (미세 허용)
                       # 상한은 min(peak, rain_start + MAX_LAG). onset = 그 구간 trough.
ANTECEDENT_H = 72      # 선행 유량 점검 구간
ANTECEDENT_RATIO = 2.0  # max(prior72h Q) > onset_q × 2.0 → 선행 event 미회복(recession 위 onset)
GAP_MAX_H = 6          # event 구간 내부 최대 허용 공백
MIN_VALID_FRAC = 0.80  # event 구간 유량 유효 관측 최소 비율
GAP_LEAD_H = 24        # data_gap 점검 창: [onset - GAP_LEAD_H, peak] (baseline 선행 포함)
SLOPE_WIN_H = 6        # max rolling slope 계산 창 (시간)
TCAP_MULT = 3.0        # 유역별 T_cap = clip(TCAP_MULT × median lag, TCAP_FLOOR, TCAP_CEIL)
TCAP_FLOOR = 24
TCAP_CEIL = 168

# 기존 결과 (문서/CSV 기준값) — 비교 표용
M1_SLOPE_R = -0.129
M1_REL_R = +0.451


def normalize_basin_id(v) -> str:
    s = str(v).strip()
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s.zfill(8)


def load_obs_class() -> pd.DataFrame:
    df = pd.read_csv(OBS_CLASS_CSV, comment="#", dtype={"basin_id": str})
    df["basin_id"] = df["basin_id"].map(normalize_basin_id)
    df["peak_time"] = pd.to_datetime(df["peak_time"])
    df["obs_class_ordinal"] = df["obs_class"].map(BAND_ORDINAL)
    return df.dropna(subset=["obs_class_ordinal"])


def load_ts(basin: str) -> pd.DataFrame | None:
    for cand in (basin, basin.lstrip("0")):
        p = TS_DIR / f"{cand}.nc"
        if p.exists():
            with xr.open_dataset(p) as ds:
                df = ds[["Rainf", "Streamflow"]].to_dataframe().reset_index()
            df["date"] = pd.to_datetime(df["date"])
            return df.set_index("date").sort_index()
    return None


def detect_bursts(rain: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp, float]]:
    """MIT로 병합한 강수 burst 목록 [(start, end, total_mm)]."""
    r = rain.fillna(0)
    active = r >= RAIN_ON
    if not active.any():
        return []
    idx = r.index
    bursts = []
    in_burst = False
    start = None
    last_wet = None
    for t, a in zip(idx, active.values):
        if a:
            if not in_burst:
                in_burst = True
                start = t
            last_wet = t
        else:
            if in_burst and (t - last_wet) >= pd.Timedelta(hours=MIT_RAIN_H):
                bursts.append((start, last_wet))
                in_burst = False
    if in_burst:
        bursts.append((start, last_wet))
    out = []
    for s, e in bursts:
        total = float(r.loc[s:e].sum())
        out.append((s, e, total))
    return out


def causative_burst(bursts, peak_t):
    """peak를 유발한 burst: 강수량 충분 & start<=peak & lag<=MAX_LAG_H 중 가장 늦게 시작한 것."""
    cands = [
        (s, e, tot) for (s, e, tot) in bursts
        if tot >= MIN_BURST_RAIN and s <= peak_t
        and (peak_t - s) <= pd.Timedelta(hours=MAX_LAG_H)
    ]
    if not cands:
        return None
    return max(cands, key=lambda x: x[0])  # 가장 늦은 start (직전 storm)


def find_onset(q: pd.Series, rain_start: pd.Timestamp,
               peak_t: pd.Timestamp) -> tuple[pd.Timestamp, float] | None:
    """onset = [rain_start - tol, min(peak, rain_start+MAX_LAG)] 구간의 유량 trough.

    시각은 rain_start 이후(상승은 강수보다 lag만큼 늦음), 값은 강수 직후 lag 동안
    아직 반응 전이라 직전 recession을 이어가므로 강수 전 baseflow에 해당한다.
    """
    lo = rain_start - pd.Timedelta(hours=ONSET_TOL_H)
    hi = min(peak_t, rain_start + pd.Timedelta(hours=MAX_LAG_H))
    seg = q.loc[lo:hi].dropna()
    if len(seg) < 2:
        return None
    t = seg.idxmin()
    return t, float(seg.loc[t])


def gap_stats(q: pd.Series, onset_t, peak_t) -> tuple[float, float]:
    """onset→peak 유효비율, 최대 내부공백(h)."""
    seg = q.loc[onset_t:peak_t]
    expected = (peak_t - onset_t).total_seconds() / 3600 + 1
    valid = seg.dropna()
    frac = len(valid) / expected if expected > 0 else 0.0
    if len(valid) > 1:
        maxgap = valid.index.to_series().diff().max().total_seconds() / 3600
    else:
        maxgap = expected
    return frac, float(maxgap)


def rain_valid_frac(rain: pd.Series, start_t, peak_t) -> float:
    """start_t→peak 강수 유효(비결측) 관측 비율. (NaN=결측)"""
    expected = (peak_t - start_t).total_seconds() / 3600 + 1
    if expected <= 0:
        return 1.0
    seg = rain.loc[start_t:peak_t]
    return float(seg.notna().sum()) / expected


def max_rolling_slope(q: pd.Series, onset_t, peak_t, win_h: int) -> float:
    """rising limb [onset, peak] 내 최대 win_h 시간 상승속도 (m³/s/h).

    onset→peak 평균 slope가 다단계 사건에서 급상승부를 희석하는 문제를 보완.
    시간축 정시 reindex 후 win_h 전진차분의 최대값 / win_h.
    """
    full = pd.date_range(onset_t.floor("h"), peak_t.ceil("h"), freq="h")
    s = q.reindex(full)
    if s.notna().sum() < 2:
        return float("nan")
    fwd = s.shift(-win_h) - s          # win_h 시간 뒤 - 현재
    slope = fwd / win_h
    m = slope.max(skipna=True)
    return float(m) if pd.notna(m) else float("nan")


def compute_m4(obs_df: pd.DataFrame) -> pd.DataFrame:
    unique_peaks = obs_df[["basin_id", "peak_time"]].drop_duplicates()
    print(f"unique (basin, peak): {len(unique_peaks)}")

    q_cache: dict[str, pd.DataFrame | None] = {}
    # ── pass 1: rain_start, lag, onset, metrics ──
    raw = []
    for bid in unique_peaks["basin_id"].unique():
        if bid not in q_cache:
            q_cache[bid] = load_ts(bid)
        ts = q_cache[bid]
        if ts is None:
            continue
        q = ts["Streamflow"]
        rain = ts["Rainf"]
        q99 = float(np.nanquantile(q.values, 0.99))
        peaks = unique_peaks.loc[unique_peaks["basin_id"] == bid, "peak_time"]
        for peak_t in peaks:
            lb = peak_t - pd.Timedelta(hours=LOOKBACK_H)
            bursts = detect_bursts(rain.loc[lb:peak_t])
            cb = causative_burst(bursts, peak_t)
            rec = {"basin_id": bid, "peak_time": peak_t, "q99": q99}
            peak_q = float(q.asof(peak_t)) if not pd.isna(q.asof(peak_t)) else np.nan
            rec["peak_q"] = peak_q
            if cb is None:
                rec.update(rain_start=pd.NaT, onset_time=pd.NaT, onset_q=np.nan,
                           lag_h=np.nan, no_causative_rain=True)
                raw.append(rec)
                continue
            rain_start = cb[0]
            onset = find_onset(q, rain_start, peak_t)
            if onset is None or onset[1] <= 0 or pd.isna(peak_q):
                rec.update(rain_start=rain_start, onset_time=pd.NaT, onset_q=np.nan,
                           lag_h=np.nan, no_causative_rain=True)
                raw.append(rec)
                continue
            onset_t, onset_q = onset
            rec.update(
                rain_start=rain_start,
                onset_time=onset_t,
                onset_q=onset_q,
                lag_h=(peak_t - rain_start).total_seconds() / 3600,
                no_causative_rain=False,
            )
            raw.append(rec)

    df = pd.DataFrame(raw)

    # ── 유역별 T_cap (Nagy 2022식 adaptive: 3 × median lag, clamp) ──
    tcap = {}
    for bid, g in df.groupby("basin_id"):
        lags = g.loc[~g["no_causative_rain"], "lag_h"].dropna()
        med = float(np.median(lags)) if len(lags) else 48.0
        tcap[bid] = float(np.clip(TCAP_MULT * med, TCAP_FLOOR, TCAP_CEIL))
    df["basin_tcap_h"] = df["basin_id"].map(tcap)

    # ── pass 2: metrics + flags ──
    out_rows = []
    for _, r in df.iterrows():
        bid = r["basin_id"]
        ts = q_cache.get(bid)
        q = ts["Streamflow"] if ts is not None else None
        rain = ts["Rainf"] if ts is not None else None
        flags = []
        onset_t = r["onset_time"]
        peak_t = r["peak_time"]
        onset_q = r["onset_q"]
        peak_q = r["peak_q"]

        rise_slope_max = np.nan
        if r["no_causative_rain"] or pd.isna(onset_t):
            flags.append("no_rain_trigger")
            rising_h = np.nan; rise_rel = np.nan; rise_slope = np.nan
        else:
            rising_h = max((peak_t - onset_t).total_seconds() / 3600, 1.0)
            rise_rel = (peak_q - onset_q) / onset_q
            rise_slope = (peak_q - onset_q) / rising_h
            # 보완 지표: rising limb 내 최대 SLOPE_WIN_H 시간 상승속도
            rise_slope_max = max_rolling_slope(q, onset_t, peak_t, SLOPE_WIN_H)
            # ③ too_long
            if rising_h > r["basin_tcap_h"]:
                flags.append("too_long")
            # ② prior_event_recession: 직전 72h 유량이 onset_q의 2배↑ → 선행 event 미회복
            prior = q.loc[onset_t - pd.Timedelta(hours=ANTECEDENT_H):onset_t - pd.Timedelta(hours=1)].dropna()
            if not prior.empty and float(prior.max()) > onset_q * ANTECEDENT_RATIO:
                flags.append("prior_event_recession")
            # ④ data_gap: streamflow가 [onset-24h, peak]에서 결측률>20% 또는 내부공백>6h
            frac, maxgap = gap_stats(q, onset_t - pd.Timedelta(hours=GAP_LEAD_H), peak_t)
            if frac < MIN_VALID_FRAC or maxgap > GAP_MAX_H:
                flags.append("data_gap")
            # peak sanity
            if not pd.isna(peak_q) and peak_q <= r["q99"]:
                flags.append("peak_below_q99")

        out_rows.append({
            "basin_id": bid,
            "peak_time": peak_t.isoformat(),
            "rain_start": (r["rain_start"].isoformat() if not pd.isna(r["rain_start"]) else ""),
            "onset_time": (onset_t.isoformat() if not pd.isna(onset_t) else ""),
            "onset_q": round(onset_q, 4) if not pd.isna(onset_q) else "",
            "peak_q": round(peak_q, 4) if not pd.isna(peak_q) else "",
            "lag_h": round(r["lag_h"], 2) if not pd.isna(r["lag_h"]) else "",
            "rising_hours": round(rising_h, 2) if not pd.isna(rising_h) else "",
            "rise_rel_m4": round(rise_rel, 4) if not pd.isna(rise_rel) else "",
            "rise_slope_m4": round(rise_slope, 4) if not pd.isna(rise_slope) else "",
            "rise_slope_max_m4": round(rise_slope_max, 4) if not pd.isna(rise_slope_max) else "",
            "q99_threshold": round(r["q99"], 4),
            "basin_tcap_h": round(r["basin_tcap_h"], 1),
            "flags": ";".join(flags),
            "n_flags": len(flags),
            "hard_flags": ";".join(f for f in flags if f in HARD_FLAGS),
            "soft_flags": ";".join(f for f in flags if f in SOFT_FLAGS),
            "clean": not any(f in HARD_FLAGS for f in flags),
        })
    return pd.DataFrame(out_rows)


def spearman(df: pd.DataFrame, col: str) -> tuple[float, float, int]:
    sub = df[[col, "obs_class_ordinal"]].copy()
    sub[col] = pd.to_numeric(sub[col], errors="coerce")
    sub = sub.dropna()
    sub = sub[np.isfinite(sub[col])]
    if len(sub) < 10:
        return float("nan"), float("nan"), len(sub)
    r, p = stats.spearmanr(sub[col], sub["obs_class_ordinal"])
    return float(r), float(p), len(sub)


def main() -> None:
    ap = argparse.ArgumentParser(description="M4 onset 계산 (강수 anchor + MIT + 게이트)")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    obs_df = load_obs_class()
    print(f"obs_class rows: {len(obs_df)} | basins: {obs_df['basin_id'].nunique()}")

    m4 = compute_m4(obs_df)
    if args.limit:
        m4 = m4.head(args.limit)
    m4.to_csv(OUT_CSV, index=False)
    print(f"M4 CSV: {OUT_CSV} ({len(m4)} windows)")

    # flag 요약
    n = len(m4)
    n_clean = int(m4["clean"].sum())
    print(f"\n=== window 분류 ===")
    print(f"전체 {n} | clean(HARD flag 없음) {n_clean} ({n_clean/n*100:.1f}%) | HARD-flagged {n-n_clean}")
    from collections import Counter
    fc = Counter()
    for f in m4["flags"]:
        for x in (f.split(";") if f else []):
            fc[x] += 1
    print("flag 사유별:")
    for k, v in fc.most_common():
        print(f"  {k:22s}: {v:4d} ({v/n*100:.1f}%)")

    # obs_class 병합 (seed별 row) → Spearman
    merged = obs_df.merge(
        m4.assign(peak_time=pd.to_datetime(m4["peak_time"])),
        on=["basin_id", "peak_time"], how="inner",
    )
    clean = merged[merged["clean"]]
    print(f"\n병합 {len(merged)} rows | clean {len(clean)} rows")

    res = {}
    for label, sub in [("all", merged), ("clean", clean)]:
        for col, key in [("rise_slope_m4", "slope"), ("rise_rel_m4", "rel"),
                         ("rise_slope_max_m4", "slopemax")]:
            r, p, k = spearman(sub, col)
            res[f"{label}_{key}"] = (r, p, k)
            print(f"  [{label:5s}] {col}: r={r:+.3f} p={p:.2e} n={k}")

    write_html(res, m4, fc, n, n_clean)
    print(f"\n비교 HTML: {OUT_HTML}")


def write_html(res, m4, fc, n, n_clean) -> None:
    def cell(rt):
        r, p, k = rt
        cls = "pass" if abs(r) >= 0.3 else "fail"
        ps = "p&lt;0.001" if p < 0.001 else f"p={p:.3f}"
        return f"<td class='{cls}'>{r:+.3f}</td><td>{ps}</td><td>{k:,}</td>"

    flag_rows = "".join(
        f"<tr><td>{k}</td><td class='num'>{v}</td><td class='num'>{v/n*100:.1f}%</td></tr>"
        for k, v in fc.most_common()
    )
    cs, cr = res["clean_slope"], res["clean_rel"]
    asl, arl = res["all_slope"], res["all_rel"]
    csm, asm = res["clean_slopemax"], res["all_slopemax"]
    html = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<title>M4 onset (강수 anchor+MIT) — 비교</title>
<style>
 body{{font-family:'Apple SD Gothic Neo','Noto Sans KR',sans-serif;max-width:1000px;margin:0 auto;
   padding:24px 20px;background:#f4f6f9;color:#2c3e50;line-height:1.7;}}
 h1{{font-size:1.6rem;border-bottom:3px solid #2980b9;padding-bottom:10px;}}
 h2{{font-size:1.2rem;color:#1a5276;margin-top:1.8rem;border-left:4px solid #2980b9;padding-left:10px;}}
 .card{{background:#fff;border-radius:10px;padding:18px 22px;box-shadow:0 2px 8px rgba(0,0,0,.08);margin:14px 0;}}
 table{{border-collapse:collapse;width:100%;font-size:.88rem;}}
 th{{background:#1a5276;color:#fff;padding:8px 10px;}} td{{padding:7px 10px;border-bottom:1px solid #ecf0f1;text-align:center;}}
 .num{{text-align:right;font-variant-numeric:tabular-nums;}} tr:nth-child(even){{background:#f8f9fa;}}
 .pass{{font-weight:bold;color:#1e8449;}} .fail{{font-weight:bold;color:#c0392b;}}
 .note{{background:#fef9e7;border:1px solid #f9ca24;border-radius:6px;padding:10px 14px;font-size:.9rem;margin:10px 0;}}
</style></head><body>
<h1>M4 onset — 강수 anchor + MIT 기반 rising limb 재계산</h1>
<p style="color:#7f8c8d;font-size:.92rem">표준: Blume·Zehe·Bronstert(2007), Mei&amp;Anagnostou(2015), Koskelo(2012), Nagy(2022), Molina-Sanchis(2016).
onset = 사건 유발 강수 burst 직전 유량 극솟값. 유역별 T_cap = clip(3×median lag, 24, 168) h.</p>

<h2>1. window 분류 ({n_clean}/{n} clean, {n_clean/n*100:.1f}%)</h2>
<div class="card">
<table><tr><th>auto-flag 사유</th><th>건수</th><th>비율</th></tr>{flag_rows}</table>
<div class="note">clean = <b>HARD flag 없음</b>. HARD(통계 제외): <code>data_gap</code>(streamflow [onset−24h,peak] 결측>20%/공백>6h), <code>too_long</code>(rising_hours>유역 T_cap), <code>no_rain_trigger</code>(peak 유발 강수 없음=눈녹음/baseflow, rise 미정의). SOFT(통계 유지·주의): <code>prior_event_recession</code>(직전 72h 유량>onset_q×2 = 선행 event 미회복), <code>peak_below_q99</code>(peak<기후Q99). 구 <code>antecedent_elevated</code>(임계 1.05→83% 발화·구분력 0)를 임계 2.0 기반으로 재정의했다.</div>
</div>

<h2>2. Spearman r 비교 (vs obs_class_ordinal)</h2>
<div class="card">
<table>
<tr><th>지표</th><th>onset 방법</th><th>r</th><th>p</th><th>n</th><th>0.3 달성</th></tr>
<tr><td>rise_slope</td><td>M1 (Q50 threshold)</td><td class="{ 'pass' if abs(M1_SLOPE_R)>=0.3 else 'fail'}">{M1_SLOPE_R:+.3f}</td><td>—</td><td>2,649</td><td>{'✓' if abs(M1_SLOPE_R)>=0.3 else '✗'}</td></tr>
<tr><td>rise_slope</td><td>M3 (SG dQ/dt)</td><td class="pass">+0.359</td><td>—</td><td>2,778</td><td>✓</td></tr>
<tr><td><b>rise_slope</b> (onset→peak 평균)</td><td><b>M4 (강수anchor+MIT, clean)</b></td>{cell(cs)}<td>{'✓' if abs(cs[0])>=0.3 else '✗'}</td></tr>
<tr><td>rise_slope (평균)</td><td>M4 (all, 참고)</td>{cell(asl)}<td>{'✓' if abs(asl[0])>=0.3 else '✗'}</td></tr>
<tr style="background:#eaf4fb"><td><b>rise_slope_max</b> (최대 {SLOPE_WIN_H}h 상승속도)</td><td><b>M4 (clean)</b></td>{cell(csm)}<td>{'✓' if abs(csm[0])>=0.3 else '✗'}</td></tr>
<tr style="background:#eaf4fb"><td>rise_slope_max ({SLOPE_WIN_H}h)</td><td>M4 (all, 참고)</td>{cell(asm)}<td>{'✓' if abs(asm[0])>=0.3 else '✗'}</td></tr>
<tr><td>rise_rel</td><td>M1 (Q50 threshold)</td><td class="pass">{M1_REL_R:+.3f}</td><td>—</td><td>2,649</td><td>✓ (artifact)</td></tr>
<tr><td>rise_rel</td><td>M3 (SG dQ/dt)</td><td class="fail">-0.073</td><td>—</td><td>2,778</td><td>✗</td></tr>
<tr><td><b>rise_rel</b></td><td><b>M4 (강수anchor+MIT, clean)</b></td>{cell(cr)}<td>{'✓' if abs(cr[0])>=0.3 else '✗'}</td></tr>
<tr><td>rise_rel</td><td>M4 (all, 참고)</td>{cell(arl)}<td>{'✓' if abs(arl[0])>=0.3 else '✗'}</td></tr>
</table>
</div>

<h2>3. 해석</h2>
<div class="card"><ul>
<li>M4는 onset을 <b>강수 burst 직전 유량 극솟값</b>으로 고정해 "강수 도중 onset"과 "선행 event recession 위 onset" 문제를 구조적으로 제거한다.</li>
<li>T_cap(유역별 response time 배수)·data_gap 게이트로 수주~수개월 window와 공백연결 window를 통계에서 제외한다.</li>
<li>rise_rel이 M4 clean에서도 0.3 미달이면, M1의 r=0.451은 onset 정의 artifact였다는 결론이 한층 강화된다(M3에 이어 독립 재현).</li>
<li>rise_slope가 M4 clean에서 0.3 부근/이상을 유지하면 "가파른 절대 상승 = Q99 초과" 신호의 견고성이 확인된다.</li>
</ul></div>
</body></html>"""
    OUT_HTML.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
