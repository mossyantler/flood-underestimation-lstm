# /// script
# dependencies = ["pandas", "scipy", "numpy"]
# ///
"""
Branch A (CSV 전용, 가벼움): band 지표 + model gap + seed_spread + basin 특성 vs obs_class.
타깃: Q99, NOAA 두 scope.

분류 태그:
  C = 밴드 결합(부분 순환): rel_width, g3_ratio, band levels/widths, tail_jump, q99_q50_ratio
  I = 독립(누수 없음): model1_minus_model2, seed_spread, basin 특성(area/slope/aridity/BFI/...)
  L = obs 누수(기준선): obs_peak

조인 키: (basin_id, seed, peak_time)
"""
import pandas as pd, numpy as np
from scipy.stats import spearmanr
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
T = BASE / "output/model_analysis/primary/metrics/tables"
LOC = BASE / "output/model_analysis/band_signal/band_shape/tables"
OUT = BASE / "output/model_analysis/band_signal/signal_sweep/tables"
OUT.mkdir(parents=True, exist_ok=True)
SEEDS = [111, 222, 444]
EPS = 1e-6

# 정적 특성
attrs = pd.read_csv(BASE / "data/CAMELSH_generic/drbc_expanded_observed_test/attributes/static_attributes.csv")
attrs["basin_id"] = attrs["gauge_id"].astype(str).str.zfill(8)
ATTR_COLS = ["area", "slope", "aridity", "snow_fraction", "soil_depth", "permeability", "baseflow_index", "forest_fraction"]
attrs = attrs[["basin_id"] + ATTR_COLS]

# required_series (peak-time 값 추출용) — datetime indexed per seed
req = {}
for s in SEEDS:
    d = pd.read_csv(BASE / f"output/model_analysis/primary/metrics/data/required_series/seed{s}/required_series.csv")
    d["datetime"] = pd.to_datetime(d["datetime"])
    d["basin"] = d["basin"].astype(str).str.zfill(8)
    d["peak_time"] = d["datetime"].astype(str)
    req[s] = d.set_index(["basin", "peak_time"])

CAT = {}  # metric -> 분류


def peak_features(basin, peak_time_str, seed):
    """peak_time 시점의 band/level/gap 값."""
    try:
        r = req[seed].loc[(basin, peak_time_str)]
    except KeyError:
        return None
    if isinstance(r, pd.DataFrame):
        r = r.iloc[0]
    q50, q90, q95, q99 = r["q50"], r["q90"], r["q95"], r["q99"]
    return {
        "q50_level": q50, "q90_level": q90, "q95_level": q95, "q99_level": q99,
        "w_q90_q50": q90 - q50, "w_q95_q90": q95 - q90, "w_q99_q95": q99 - q95, "w_q99_q50": q99 - q50,
        "rel_width": (q99 - q50) / max(q50, EPS),
        "tail_jump": (q99 - q95) / max(q99 - q50, EPS),
        "q99_q50_ratio": q99 / max(q50, EPS),
        "model1_minus_model2": r.get("model2_q50_minus_model1", np.nan) * -1,
        "obs_peak": r.get("obs", np.nan),
        "q50_for_spread": q50, "q99_for_spread": q99,
    }


def build(target_csv, scope):
    tgt = pd.read_csv(target_csv, comment="#")
    tgt["basin_id"] = tgt["basin_id"].astype(str).str.zfill(8)
    tgt["peak_time"] = pd.to_datetime(tgt["peak_time"]).astype(str)
    OC = {"below_q50": 0, "q50_to_q90": 1, "q90_to_q95": 2, "q95_to_q99": 3, "above_q99": 4}
    tgt["oc"] = tgt["obs_class"].map(OC)
    tgt = tgt.dropna(subset=["oc"])

    rows = []
    # seed_spread: 같은 (basin, peak) across seed 의 q50/q99 표준편차
    for (b, pt), grp in tgt.groupby(["basin_id", "peak_time"]):
        q50s, q99s, feats_per_seed = [], [], []
        for s in SEEDS:
            f = peak_features(b, pt, s)
            if f is None:
                continue
            q50s.append(f["q50_for_spread"]); q99s.append(f["q99_for_spread"])
            feats_per_seed.append(f)
        if not feats_per_seed:
            continue
        # seed 평균 + spread
        rec = {
            "basin_id": b,
            "peak_time": pt,
            "oc": float(grp["oc"].median()),
            "oc_seed_mean": float(grp["oc"].mean()),
            "oc_seed_min": float(grp["oc"].min()),
            "oc_seed_max": float(grp["oc"].max()),
            "oc_seed_std": float(grp["oc"].std(ddof=0)) if len(grp) > 1 else 0.0,
            "oc_seed_n": int(grp["oc"].count()),
        }
        keys = [k for k in feats_per_seed[0] if k not in ("q50_for_spread", "q99_for_spread")]
        for k in keys:
            rec[k] = np.nanmean([f[k] for f in feats_per_seed])
        rec["seed_spread_q50"] = np.std(q50s) if len(q50s) > 1 else np.nan
        rec["seed_spread_q99"] = np.std(q99s) if len(q99s) > 1 else np.nan
        rec["seed_spread_q50_rel"] = rec["seed_spread_q50"] / max(np.nanmean(q50s), EPS) if len(q50s) > 1 else np.nan
        rows.append(rec)

    df = pd.DataFrame(rows).merge(attrs, on="basin_id", how="left")
    df.to_csv(OUT / f"branchA_features_{scope}.csv", index=False)

    # 분류 지정
    band_coupled = ["q50_level", "q90_level", "q95_level", "q99_level", "w_q90_q50", "w_q95_q90",
                    "w_q99_q95", "w_q99_q50", "rel_width", "tail_jump", "q99_q50_ratio"]
    independent = ["model1_minus_model2", "seed_spread_q50", "seed_spread_q99", "seed_spread_q50_rel"] + ATTR_COLS
    leak = ["obs_peak"]
    cat_map = {**{m: "C" for m in band_coupled}, **{m: "I" for m in independent}, **{m: "L" for m in leak}}

    res = []
    for m, cat in cat_map.items():
        if m not in df.columns:
            continue
        sub = df[[m, "oc"]].dropna()
        if len(sub) < 5:
            continue
        r, p = spearmanr(sub[m], sub["oc"])
        res.append({"scope": scope, "metric": m, "category": cat, "spearman_r": r, "p_value": p, "n": len(sub)})
    return pd.DataFrame(res)


print("Branch A 시작...")
all_res = []
for scope, fn in [("q99", "location_class_q99.csv"), ("noaa", "location_class_noaa.csv")]:
    print(f"  scope={scope}")
    all_res.append(build(LOC / fn, scope))
out = pd.concat(all_res, ignore_index=True)
out.to_csv(OUT / "branchA_spearman.csv", index=False)
print("저장:", OUT / "branchA_spearman.csv")
print(f"행수: {len(out)}")
