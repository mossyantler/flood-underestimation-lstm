# /// script
# dependencies = ["pandas", "numpy", "xarray", "netcdf4", "scipy"]
# ///
"""
Branch B2: 2014-2016 전체 강우 사건(NWS 강우강도 등급) 새로 탐지 → obs_class 전 구간 분석.
목적: Q99/NOAA(극유량 선별)의 범위 제한 보완. 일반 강우 사건까지 포함해 신호 유지 여부 확인.

강우 사건 탐지:
  - Rainf > 0.1 mm/h 시간을 강우시간으로 보고, 6h 이내 끊김은 같은 사건으로 병합.
  - 사건 총강우 >= 2.5 mm 만 유효 사건.
  - 사건 최대 시간강우(mm/h)로 NWS 등급: light<2.5 / moderate 2.5-7.6 / heavy 7.6-50 / violent>50.
유출 반응 첨두:
  - [사건시작, 사건끝+48h] 구간에서 obs 최대 시점 = 반응 첨두.
  - 그 시점의 obs vs 예측밴드(q50/q90/q95/q99, seed 평균)로 obs_class 산출.
지표(독립 신호 위주) vs obs_class Spearman:
  area, baseflow_index, permeability, slope, aridity (정적)
  rain_sum_event, rain_max_1h, nws_class, cape_max, crainf_frac_mean (강제력)
  rel_width, q99_q50_ratio (밴드결합 비교용)
"""
import pandas as pd, numpy as np, xarray as xr
from scipy.stats import spearmanr
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
NCDIR = BASE / "data/CAMELSH_generic/drbc_expanded_observed_test/time_series"
OUT = BASE / "output/model_analysis/band_signal/signal_sweep/tables"
OUT.mkdir(parents=True, exist_ok=True)
SEEDS = [111, 222, 444]
EPS = 1e-6
T0, T1 = pd.Timestamp("2014-01-01"), pd.Timestamp("2016-12-31 23:00")

# 정적 특성
attrs = pd.read_csv(BASE / "data/CAMELSH_generic/drbc_expanded_observed_test/attributes/static_attributes.csv")
attrs["basin_id"] = attrs["gauge_id"].astype(str).str.zfill(8)
ATTR_COLS = ["area", "slope", "aridity", "snow_fraction", "soil_depth", "permeability", "baseflow_index", "forest_fraction"]
attrs = attrs.set_index("basin_id")[ATTR_COLS]

# required_series → (basin, datetime) 인덱스, q50-q99+obs seed 평균
print("required_series 로드+seed평균...")
parts = []
for s in SEEDS:
    d = pd.read_csv(BASE / f"output/model_analysis/primary/metrics/data/required_series/seed{s}/required_series.csv",
                    usecols=["basin", "datetime", "obs", "q50", "q90", "q95", "q99"])
    parts.append(d)
allq = pd.concat(parts, ignore_index=True)
allq["basin"] = allq["basin"].astype(str).str.zfill(8)
allq["datetime"] = pd.to_datetime(allq["datetime"])
qavg = allq.groupby(["basin", "datetime"]).mean().reset_index()
qidx = qavg.set_index(["basin", "datetime"]).sort_index()
print(f"  qavg {len(qavg)} rows")


def obs_class(basin, t):
    try:
        r = qidx.loc[(basin, t)]
    except KeyError:
        return None
    if isinstance(r, pd.DataFrame):
        r = r.iloc[0]
    o, q50, q90, q95, q99 = r["obs"], r["q50"], r["q90"], r["q95"], r["q99"]
    if any(pd.isna(x) for x in (o, q50, q90, q95, q99)):
        return None
    if o <= q50: oc = 0
    elif o <= q90: oc = 1
    elif o <= q95: oc = 2
    elif o <= q99: oc = 3
    else: oc = 4
    return {"oc": oc, "q50": q50, "q99": q99, "obs_peak": o}


def nws(rate):
    if rate < 2.5: return 0
    if rate < 7.6: return 1
    if rate < 50: return 2
    return 3


def detect_events(rain):
    """rain: pd.Series hourly mm/h, 2014-2016. 반환: list of (start,end)."""
    wet = rain > 0.1
    events = []
    in_ev = False
    start = None
    dry = 0
    for t, w in wet.items():
        if w:
            if not in_ev:
                in_ev = True; start = t
            dry = 0
            last = t
        else:
            if in_ev:
                dry += 1
                if dry > 6:  # 6h 끊김 → 사건 종료
                    events.append((start, last)); in_ev = False
    if in_ev:
        events.append((start, last))
    return events


rows = []
ncfiles = sorted(NCDIR.glob("*.nc"))
print(f"basin {len(ncfiles)}개 강우사건 탐지...")
for i, f in enumerate(ncfiles):
    basin = f.stem.zfill(8)
    if basin not in attrs.index:
        continue
    ds = xr.open_dataset(f)
    idx = pd.to_datetime(ds["date"].values)
    rain = pd.Series(ds["Rainf"].values, index=idx)
    cape = pd.Series(ds["CAPE"].values, index=idx)
    cfr = pd.Series(ds["CRainf_frac"].values, index=idx)
    obs = pd.Series(ds["Streamflow"].values, index=idx)
    m = (idx >= T0) & (idx <= T1)
    rain, cape, cfr, obs = rain[m], cape[m], cfr[m], obs[m]

    for (st, en) in detect_events(rain):
        ev_rain = rain.loc[st:en]
        if ev_rain.sum() < 2.5:
            continue
        rmax = ev_rain.max()
        # 반응 첨두: 사건시작~사건끝+48h obs 최대
        resp = obs.loc[st:en + pd.Timedelta(hours=48)]
        if len(resp) == 0 or resp.isna().all():
            continue
        pt = resp.idxmax()
        oc = obs_class(basin, pt)
        if oc is None:
            continue
        capw = cape.loc[st:en + pd.Timedelta(hours=48)]
        cfrw = cfr.loc[st:en]
        rows.append({
            "basin_id": basin, "peak_time": str(pt), "oc": oc["oc"],
            "rain_sum_event": ev_rain.sum(), "rain_max_1h": rmax, "nws_class": nws(rmax),
            "cape_max": capw.max() if len(capw) else np.nan,
            "crainf_frac_mean": cfrw.mean() if len(cfrw) else np.nan,
            "rel_width": (oc["q99"] - oc["q50"]) / max(oc["q50"], EPS),
            "q99_q50_ratio": oc["q99"] / max(oc["q50"], EPS),
        })
    if (i + 1) % 20 == 0:
        print(f"  {i+1}/{len(ncfiles)}  누적사건 {len(rows)}")

df = pd.DataFrame(rows).merge(attrs, left_on="basin_id", right_index=True, how="left")
df.to_csv(OUT / "features_allrain.csv", index=False)
print(f"\n전체 강우사건 {len(df)}개")
print("obs_class 분포:")
print(df["oc"].value_counts().sort_index().to_string())

# Spearman
band_coupled = ["rel_width", "q99_q50_ratio"]
forcing = ["rain_sum_event", "rain_max_1h", "nws_class", "cape_max", "crainf_frac_mean"]
indep = ATTR_COLS
leak = []
cat = {**{m: "C" for m in band_coupled}, **{m: "F" for m in forcing}, **{m: "I" for m in indep}}
res = []
for m, c in cat.items():
    if m not in df.columns: continue
    sub = df[[m, "oc"]].dropna()
    if len(sub) < 10: continue
    r, p = spearmanr(sub[m], sub["oc"])
    res.append({"scope": "allrain", "metric": m, "category": c, "spearman_r": r, "p_value": p, "n": len(sub)})
rd = pd.DataFrame(res)
rd.to_csv(OUT / "allrain_spearman.csv", index=False)
print("\n저장:", OUT / "allrain_spearman.csv")
