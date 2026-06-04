# /// script
# dependencies = ["pandas", "scipy", "numpy"]
# ///
"""
rise_slope_m4 방식을 예측 quantile(q50/q90/q95/q99)에 그대로 적용해 재분석.

rise_slope_m4 공식 (manifest에서 검증됨):
    rise_slope_m4 = (peak_q - onset_q) / rising_hours
    rise_slope_max_m4 = 상승구간 내 1h diff 최대
    rise_rel_m4 = (peak_q - onset_q) / max(onset_q, eps)   # 상대(무차원)

핵심 검증: 같은 방식을 req_series의 'obs' 컬럼에 적용해 manifest rise_slope_m4(r≈0.498)를
재현하는지 확인 → 재현되면 파이프라인 신뢰 가능 → 예측 quantile 결과도 신뢰.

각 시리즈(obs, q50, q90, q95, q99)에 대해:
  - {x}_slope     = (peak값 - onset값) / rising_hours          [m4 raw 방식]
  - {x}_slope_max = 상승구간 1h diff 최대                       [m4 max 방식]
  - {x}_rel       = (peak값 - onset값) / max(onset값, eps)      [m4 rel 방식]
그리고 fanning = q99_slope - q50_slope.
모두 obs_class_ordinal과 Spearman.
"""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
MANIFEST = BASE / "output/model_analysis/band_signal/method_compare/data/rise_h_windows/rise_h_window_manifest.csv"
OUTDIR = BASE / "output/model_analysis/band_signal/slope_signal/tables"
OUTDIR.mkdir(parents=True, exist_ok=True)
SEEDS = [111, 222, 444]
EPS = 1e-6
OC_MAP = {"below_q50": 0, "q50_to_q90": 1, "q90_to_q95": 2, "q95_to_q99": 3, "above_q99": 4}
SERIES = ["obs", "q50", "q90", "q95", "q99"]

print("manifest 로드...")
man = pd.read_csv(MANIFEST)
man = man[man["clean"]].copy()
man["obs_class_ordinal"] = man["obs_class_primary"].map(OC_MAP)
print(f"  clean window {len(man)}")

print("req_series 로드 (seed 111/222/444)...")
req = {}
for s in SEEDS:
    df = pd.read_csv(BASE / f"output/model_analysis/primary/metrics/data/required_series/seed{s}/required_series.csv")
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["basin"] = df["basin"].astype(str).str.zfill(8)
    req[s] = df
    print(f"  seed {s}: {len(df)}행")


def m4_metrics(values, rising_hours):
    """rise_slope_m4 방식 그대로: raw slope, max 1h diff, relative."""
    onset_v = values[0]
    peak_v = values[-1]
    rise = peak_v - onset_v
    slope = rise / rising_hours
    diffs = np.diff(values)
    slope_max = float(np.max(diffs)) if len(diffs) else np.nan
    rel = rise / max(onset_v, EPS)
    return slope, slope_max, rel


rows = []
n_match = {s: 0 for s in SERIES}
for _, w in man.iterrows():
    basin = str(w["basin_id"]).zfill(8)
    onset_t = pd.to_datetime(w["onset_time"])
    peak_t = pd.to_datetime(w["peak_time"])
    rh = w["rising_hours"]
    rec = {"window_id": w["window_id"], "obs_class_ordinal": w["obs_class_ordinal"],
           "rise_slope_m4_manifest": w["rise_slope_m4"]}
    if pd.isna(rh) or rh <= 0:
        rows.append(rec)
        continue

    # 시리즈별: 3 seed 평균. obs는 seed 무관하나 동일 슬라이스 방식 적용.
    per_seed = {f"{x}_slope": [] for x in SERIES}
    per_seed.update({f"{x}_slope_max": [] for x in SERIES})
    per_seed.update({f"{x}_rel": [] for x in SERIES})
    for s in SEEDS:
        df = req[s]
        mask = (df["basin"] == basin) & (df["datetime"] >= onset_t) & (df["datetime"] <= peak_t)
        sub = df[mask]
        if len(sub) < 2:
            continue
        sub = sub.sort_values("datetime")
        for x in SERIES:
            if x not in sub.columns:
                continue
            vals = sub[x].values.astype(float)
            if np.isnan(vals).any() or len(vals) < 2:
                continue
            sl, slm, rl = m4_metrics(vals, rh)
            per_seed[f"{x}_slope"].append(sl)
            per_seed[f"{x}_slope_max"].append(slm)
            per_seed[f"{x}_rel"].append(rl)

    for k, lst in per_seed.items():
        rec[k] = float(np.nanmean(lst)) if lst else np.nan
    for x in SERIES:
        if not np.isnan(rec.get(f"{x}_slope", np.nan)):
            n_match[x] += 1
    # fanning (raw & rel)
    rec["fanning_slope"] = rec.get("q99_slope", np.nan) - rec.get("q50_slope", np.nan)
    rec["fanning_rel"] = rec.get("q99_rel", np.nan) - rec.get("q50_rel", np.nan)
    rows.append(rec)

pw = pd.DataFrame(rows)
pw.to_csv(OUTDIR / "m4method_per_window.csv", index=False)
print(f"\n매칭 window 수: {n_match}")

# 핵심 검증: 내 파이프라인 obs_slope vs manifest rise_slope_m4
chk = pw.dropna(subset=["obs_slope", "rise_slope_m4_manifest"])
diff = (chk["obs_slope"] - chk["rise_slope_m4_manifest"]).abs()
print(f"\n[검증] 내 obs_slope vs manifest rise_slope_m4:")
print(f"  평균 절대차 {diff.mean():.4f}, 최대 {diff.max():.4f}  (0에 가까우면 방식 일치)")
r_chk, _ = spearmanr(chk["obs_slope"], chk["obs_class_ordinal"])
r_man, _ = spearmanr(chk["rise_slope_m4_manifest"], chk["obs_class_ordinal"])
print(f"  내 obs_slope Spearman r={r_chk:+.3f}  vs  manifest r={r_man:+.3f}")

# 전체 Spearman
metrics = []
for x in SERIES:
    metrics += [f"{x}_slope", f"{x}_slope_max", f"{x}_rel"]
metrics += ["fanning_slope", "fanning_rel", "rise_slope_m4_manifest"]

res = []
for m in metrics:
    if m not in pw.columns:
        continue
    sub = pw[[m, "obs_class_ordinal"]].dropna()
    if len(sub) < 3:
        continue
    r, p = spearmanr(sub[m], sub["obs_class_ordinal"])
    res.append({"metric": m, "spearman_r": r, "p_value": p, "n": len(sub)})

rdf = pd.DataFrame(res)
rdf["abs_r"] = rdf["spearman_r"].abs()
rdf = rdf.sort_values("abs_r", ascending=False)
rdf.drop(columns="abs_r").to_csv(OUTDIR / "m4method_spearman.csv", index=False)

print("\n" + "=" * 64)
print("Spearman 결과 (|r| 큰 순) — rise_slope_m4 방식 그대로 적용")
print("=" * 64)
for _, r in rdf.iterrows():
    tag = "  <== obs baseline" if "manifest" in r["metric"] or r["metric"] == "obs_slope" else ""
    print(f"{r['metric']:24s} r={r['spearman_r']:+.3f}  p={r['p_value']:.1e}  n={int(r['n'])}{tag}")
print("\n저장:", OUTDIR / "m4method_spearman.csv")
