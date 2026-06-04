# /// script
# dependencies = ["pandas", "numpy", "xarray", "netcdf4", "scipy"]
# ///
"""
Branch B (입력 강제력, .nc): 강우/CAPE 지표 vs obs_class. 타깃 Q99 + NOAA.
모두 분류 I (독립, 누수 없음 — 입력은 obs_class 정의에 안 들어감).

NWS 강우강도 등급 (mm/h): light<2.5, moderate 2.5-7.6, heavy 7.6-50, violent>50.
각 peak_time 기준 사전 window에서 강우/CAPE 지표 추출. 강제력은 seed 무관하므로 peak당 1값이고, seed별 obs_class ordinal은 중앙값으로 묶어 target을 만든다.

지표:
  rain_sum_24h / rain_sum_72h     peak 전 24/72h 누적 강우
  antecedent_rain_7d              peak 전 7일 누적 (선행 습윤)
  rain_max_1h_72h                 peak 전 72h 시간당 최대 강우 (NWS rate)
  nws_class                       rain_max_1h 의 NWS 등급 서수 (0 light~3 violent)
  cape_max_24h                    peak 전 24h CAPE 최대
  crainf_frac_mean_24h            peak 전 24h 대류성 강수비 평균
"""
import pandas as pd, numpy as np, xarray as xr
from scipy.stats import spearmanr
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
T = BASE / "output/model_analysis/primary/metrics/tables"
LOC = BASE / "output/model_analysis/band_signal/band_shape/tables"
NCDIR = BASE / "data/CAMELSH_generic/drbc_expanded_observed_test/time_series"
OUT = BASE / "output/model_analysis/band_signal/signal_sweep/tables"
OUT.mkdir(parents=True, exist_ok=True)
OC = {"below_q50": 0, "q50_to_q90": 1, "q90_to_q95": 2, "q95_to_q99": 3, "above_q99": 4}


def nws_class(rate_mm_h):
    if np.isnan(rate_mm_h):
        return np.nan
    if rate_mm_h < 2.5:
        return 0  # light
    if rate_mm_h < 7.6:
        return 1  # moderate
    if rate_mm_h < 50:
        return 2  # heavy
    return 3      # violent


_cache = {}
def load_nc(basin):
    if basin not in _cache:
        f = NCDIR / f"{basin}.nc"
        if not f.exists():
            _cache[basin] = None
        else:
            ds = xr.open_dataset(f)
            df = pd.DataFrame({
                "Rainf": ds["Rainf"].values,
                "CAPE": ds["CAPE"].values,
                "CRainf_frac": ds["CRainf_frac"].values,
            }, index=pd.to_datetime(ds["date"].values))
            _cache[basin] = df
    return _cache[basin]


def forcing_features(basin, peak_t):
    df = load_nc(basin)
    if df is None:
        return None
    pt = pd.to_datetime(peak_t)
    w24 = df.loc[pt - pd.Timedelta(hours=24):pt]
    w72 = df.loc[pt - pd.Timedelta(hours=72):pt]
    w7d = df.loc[pt - pd.Timedelta(days=7):pt]
    if len(w72) < 2:
        return None
    rmax = w72["Rainf"].max()
    return {
        "rain_sum_24h": w24["Rainf"].sum(),
        "rain_sum_72h": w72["Rainf"].sum(),
        "antecedent_rain_7d": w7d["Rainf"].sum(),
        "rain_max_1h_72h": rmax,
        "nws_class": nws_class(rmax),
        "cape_max_24h": w24["CAPE"].max(),
        "crainf_frac_mean_24h": w24["CRainf_frac"].mean(),
    }


def build(scope, fn):
    tgt = pd.read_csv(fn, comment="#")
    tgt["basin_id"] = tgt["basin_id"].astype(str).str.zfill(8)
    tgt["peak_time"] = pd.to_datetime(tgt["peak_time"]).astype(str)
    tgt["oc"] = tgt["obs_class"].map(OC)
    tgt = tgt.dropna(subset=["oc"])
    agg = (
        tgt.groupby(["basin_id", "peak_time"])
        .agg(
            oc=("oc", "median"),
            oc_seed_mean=("oc", "mean"),
            oc_seed_min=("oc", "min"),
            oc_seed_max=("oc", "max"),
            oc_seed_std=("oc", lambda s: s.std(ddof=0) if len(s) > 1 else 0.0),
            oc_seed_n=("oc", "count"),
        )
        .reset_index()
    )

    rows = []
    for _, r in agg.iterrows():
        f = forcing_features(r["basin_id"], r["peak_time"])
        if f is None:
            continue
        f.update(
            {
                "basin_id": r["basin_id"],
                "peak_time": r["peak_time"],
                "oc": r["oc"],
                "oc_seed_mean": r["oc_seed_mean"],
                "oc_seed_min": r["oc_seed_min"],
                "oc_seed_max": r["oc_seed_max"],
                "oc_seed_std": r["oc_seed_std"],
                "oc_seed_n": r["oc_seed_n"],
            }
        )
        rows.append(f)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / f"branchB_features_{scope}.csv", index=False)

    metrics = ["rain_sum_24h", "rain_sum_72h", "antecedent_rain_7d", "rain_max_1h_72h",
               "nws_class", "cape_max_24h", "crainf_frac_mean_24h"]
    res = []
    for m in metrics:
        sub = df[[m, "oc"]].dropna()
        if len(sub) < 5:
            continue
        rr, p = spearmanr(sub[m], sub["oc"])
        res.append({"scope": scope, "metric": m, "category": "I", "spearman_r": rr, "p_value": p, "n": len(sub)})
    print(f"  {scope}: {len(df)} peaks")
    return pd.DataFrame(res)


print("Branch B 시작...")
allr = []
for scope, fn in [("q99", "location_class_q99.csv"), ("noaa", "location_class_noaa.csv")]:
    allr.append(build(scope, LOC / fn))
out = pd.concat(allr, ignore_index=True)
out.to_csv(OUT / "branchB_spearman.csv", index=False)
print("저장:", OUT / "branchB_spearman.csv")
print(f"행수: {len(out)}")
