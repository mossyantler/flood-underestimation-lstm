# /// script
# dependencies = ["pandas", "numpy", "scipy"]
# ///
"""
ALL-RAIN(전 범위) scope에 seed_spread(앙상블 분산) 신호 추가.
기존 branchB2_features_allrain.csv 의 (basin_id, peak_time, oc) 를 재사용하고,
seed 111/222/444 의 q50/q99 를 그 시점에서 뽑아 표준편차(seed_spread) 산출 → obs_class 와 Spearman.

목적: Branch A(Q99/NOAA)에서만 본 seed_spread 를 전 범위 scope 에서도 측정해 3-scope 완성.
"""
import pandas as pd, numpy as np
from scipy.stats import spearmanr
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
TBL = BASE / "output/model_analysis/band_signal/signal_sweep/tables"
SEEDS = [111, 222, 444]
EPS = 1e-6

# 사건 첨두 시점 (B2 산출물). (basin, peak_time) 당 seed 행이 중복 → 첫 행만.
b2 = pd.read_csv(TBL / "branchB2_features_allrain.csv",
                 usecols=["basin_id", "peak_time", "oc"])
b2["basin_id"] = b2["basin_id"].astype(str).str.zfill(8)
b2["peak_time"] = pd.to_datetime(b2["peak_time"])
b2 = b2.drop_duplicates(["basin_id", "peak_time"]).reset_index(drop=True)
print(f"고유 (basin, peak) {len(b2)}개")

# seed별 q50/q99 (basin, datetime) 인덱스
print("seed별 required_series 로드...")
seed_idx = {}
for s in SEEDS:
    d = pd.read_csv(BASE / f"output/model_analysis/primary/metrics/data/required_series/seed{s}/required_series.csv",
                    usecols=["basin", "datetime", "q50", "q99"])
    d["basin"] = d["basin"].astype(str).str.zfill(8)
    d["datetime"] = pd.to_datetime(d["datetime"])
    seed_idx[s] = d.set_index(["basin", "datetime"]).sort_index()

# 빠른 조인: seed별 q50/q99 를 long → wide merge
merged = b2.copy()
for s in SEEDS:
    sub = seed_idx[s][["q50", "q99"]].rename(
        columns={"q50": f"q50_{s}", "q99": f"q99_{s}"}).reset_index()
    sub = sub.rename(columns={"basin": "basin_id", "datetime": "peak_time"})
    merged = merged.merge(sub, on=["basin_id", "peak_time"], how="left")

q50cols = [f"q50_{s}" for s in SEEDS]
q99cols = [f"q99_{s}" for s in SEEDS]
merged["seed_spread_q50"] = merged[q50cols].std(axis=1, ddof=0)
merged["seed_spread_q99"] = merged[q99cols].std(axis=1, ddof=0)
merged["seed_spread_q50_rel"] = merged["seed_spread_q50"] / merged[q50cols].mean(axis=1).clip(lower=EPS)

# 3 seed 모두 있는 행만
ok = merged[q50cols + q99cols].notna().all(axis=1)
m = merged[ok].copy()
print(f"3 seed 매칭 {len(m)} / {len(merged)}")

res = []
for metric in ["seed_spread_q50", "seed_spread_q99", "seed_spread_q50_rel"]:
    sub = m[[metric, "oc"]].dropna()
    r, p = spearmanr(sub[metric], sub["oc"])
    res.append({"scope": "allrain", "metric": metric, "category": "I",
                "spearman_r": r, "p_value": p, "n": len(sub)})
    print(f"  {metric:22s} r={r:+.4f}  p={p:.2e}  n={len(sub)}")

rd = pd.DataFrame(res)
out = TBL / "branchB2_seed_spread_spearman.csv"
rd.to_csv(out, index=False)
print("저장:", out)

# 3-scope 통합표 (q99/noaa from branchA + allrain)
a = pd.read_csv(TBL / "branchA_spearman.csv")
ss = a[a["metric"].str.startswith("seed_spread")][["scope", "metric", "spearman_r", "n"]]
combo = pd.concat([ss, rd[["scope", "metric", "spearman_r", "n"]]], ignore_index=True)
piv = combo.pivot_table(index="metric", columns="scope", values="spearman_r")
print("\n=== seed_spread 3-scope (Spearman r vs obs_class) ===")
print(piv.round(4).to_string())
