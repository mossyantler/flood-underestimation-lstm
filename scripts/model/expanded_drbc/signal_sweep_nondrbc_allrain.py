# /// script
# dependencies = ["pandas", "numpy", "xarray", "netcdf4", "scipy"]
# ///
"""non-DRBC train 유역: 2014-2016 전체 강우 사건 탐지 → obs_class 신호 탐색.

allrain(DRBC 유역)와 달리:
  - seed 집계: 중앙값(median) — 이상치 시드 1개에 강건
  - area 피처: log(area) 사용 — 수문학적 관계가 log 스케일
  - 데이터: drbc_holdout_broad non-DRBC train 유역
  - 시계열: output/model_analysis/band_signal/signal_sweep/tables/nondrbc_series/

출력:
  output/model_analysis/band_signal/signal_sweep/tables/nondrbc_features_allrain.csv
  output/model_analysis/band_signal/signal_sweep/tables/nondrbc_allrain_spearman.csv
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from scipy.stats import spearmanr

BASE = Path(__file__).resolve().parents[3]
# --series-dir 로 override 가능 (GPU 서버: ~/CAMELS/output/nondrbc_series/)
_DEFAULT_SERIES_DIR = BASE / "output/model_analysis/band_signal/signal_sweep/tables/nondrbc_series"
OUT = BASE / "output/model_analysis/band_signal/signal_sweep/tables"
OUT.mkdir(parents=True, exist_ok=True)

SEEDS = [111, 222, 444]
EPS = 1e-6
T0, T1 = pd.Timestamp("2014-01-01"), pd.Timestamp("2016-12-31 23:00")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--ncdir",
        type=Path,
        default=Path("/Volumes/free/CAMELSH/CAMELSH_generic/drbc_holdout_broad/time_series"),
        help="non-DRBC 유역 NetCDF 시계열 디렉토리",
    )
    p.add_argument(
        "--attrfile",
        type=Path,
        default=Path("/Volumes/free/CAMELSH/CAMELSH_generic/drbc_holdout_broad/attributes/static_attributes.csv"),
        help="정적 속성 CSV",
    )
    p.add_argument(
        "--series-dir",
        type=Path,
        default=_DEFAULT_SERIES_DIR,
        help="seed{111,222,444}/series.csv가 있는 디렉토리 (GPU 서버용 override)",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=OUT,
        help="출력 CSV 저장 디렉토리",
    )
    return p.parse_args()


ATTR_COLS = ["area", "slope", "aridity", "snow_fraction", "soil_depth",
             "permeability", "baseflow_index", "forest_fraction"]


def load_attrs(attrfile: Path) -> pd.DataFrame:
    attrs = pd.read_csv(attrfile)
    attrs["basin_id"] = attrs["gauge_id"].astype(str).str.zfill(8)
    attrs = attrs.set_index("basin_id")[ATTR_COLS].copy()
    attrs["log_area"] = np.log(attrs["area"].clip(lower=1e-3))
    return attrs


def load_series_median(series_dir: Path) -> pd.DataFrame:
    """seed 111/222/444 series.csv 로드 → median 집계."""
    parts = []
    for s in SEEDS:
        csv = series_dir / f"seed{s}" / "series.csv"
        if not csv.exists():
            raise FileNotFoundError(f"시계열 없음: {csv}\n  GPU 서버에서 infer_nondrbc_model2.py 실행 후 로컬로 전송 필요")
        d = pd.read_csv(csv, usecols=["basin", "datetime", "obs", "q50", "q90", "q95", "q99"])
        d["seed"] = s
        parts.append(d)
    allq = pd.concat(parts, ignore_index=True)
    allq["basin"] = allq["basin"].astype(str).str.zfill(8)
    allq["datetime"] = pd.to_datetime(allq["datetime"])
    # MEDIAN 집계 (allrain는 mean 사용, 여기서는 median)
    qmed = allq.groupby(["basin", "datetime"])[["obs", "q50", "q90", "q95", "q99"]].median().reset_index()
    print(f"  시계열 로드 완료 (median 집계): {len(qmed)} rows")
    return qmed.set_index(["basin", "datetime"]).sort_index()


def obs_class(qidx: pd.DataFrame, basin: str, t: pd.Timestamp):
    try:
        r = qidx.loc[(basin, t)]
    except KeyError:
        return None
    if isinstance(r, pd.DataFrame):
        r = r.iloc[0]
    o, q50, q90, q95, q99 = r["obs"], r["q50"], r["q90"], r["q95"], r["q99"]
    if any(pd.isna(x) for x in (o, q50, q90, q95, q99)):
        return None
    if o <= q50:
        oc = 0
    elif o <= q90:
        oc = 1
    elif o <= q95:
        oc = 2
    elif o <= q99:
        oc = 3
    else:
        oc = 4
    return {"oc": oc, "q50": q50, "q99": q99, "obs_peak": o}


def nws(rate: float) -> int:
    if rate < 2.5:
        return 0
    if rate < 7.6:
        return 1
    if rate < 50:
        return 2
    return 3


def detect_events(rain: pd.Series) -> list:
    wet = rain > 0.1
    events = []
    in_ev = False
    start = last = None
    dry = 0
    for t, w in wet.items():
        if w:
            if not in_ev:
                in_ev = True
                start = t
            dry = 0
            last = t
        else:
            if in_ev:
                dry += 1
                if dry > 6:
                    events.append((start, last))
                    in_ev = False
    if in_ev:
        events.append((start, last))
    return events


def main():
    args = parse_args()
    series_dir = args.series_dir
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.ncdir.exists():
        raise FileNotFoundError(f"NetCDF 디렉토리 없음: {args.ncdir}")
    if not args.attrfile.exists():
        raise FileNotFoundError(f"정적 속성 파일 없음: {args.attrfile}")

    print("정적 속성 로드...")
    attrs = load_attrs(args.attrfile)

    print("시계열 로드 (seed median)...")
    qidx = load_series_median(series_dir)

    avail_basins = set(qidx.index.get_level_values("basin").unique())
    ncfiles = sorted(args.ncdir.glob("*.nc"))
    print(f"\n{len(ncfiles)}개 유역 강우사건 탐지...")

    rows = []
    for i, f in enumerate(ncfiles):
        basin = f.stem.zfill(8)
        if basin not in attrs.index:
            continue
        if basin not in avail_basins:
            continue

        ds = xr.open_dataset(f)
        idx = pd.to_datetime(ds["date"].values)
        rain = pd.Series(ds["Rainf"].values, index=idx)
        cape = pd.Series(ds["CAPE"].values, index=idx)
        cfr = pd.Series(ds["CRainf_frac"].values, index=idx)
        obs_nc = pd.Series(ds["Streamflow"].values, index=idx)
        ds.close()

        m = (idx >= T0) & (idx <= T1)
        rain, cape, cfr, obs_nc = rain[m], cape[m], cfr[m], obs_nc[m]

        for st, en in detect_events(rain):
            ev_rain = rain.loc[st:en]
            if ev_rain.sum() < 2.5:
                continue
            rmax = ev_rain.max()
            resp = obs_nc.loc[st:en + pd.Timedelta(hours=48)]
            if len(resp) == 0 or resp.isna().all():
                continue
            pt = resp.idxmax()
            oc = obs_class(qidx, basin, pt)
            if oc is None:
                continue
            capw = cape.loc[st:en + pd.Timedelta(hours=48)]
            cfrw = cfr.loc[st:en]
            rows.append({
                "basin_id": basin,
                "peak_time": str(pt),
                "oc": oc["oc"],
                "rain_sum_event": ev_rain.sum(),
                "rain_max_1h": rmax,
                "nws_class": nws(rmax),
                "cape_max": capw.max() if len(capw) else np.nan,
                "crainf_frac_mean": cfrw.mean() if len(cfrw) else np.nan,
                "rel_width": (oc["q99"] - oc["q50"]) / max(oc["q50"], EPS),
                "q99_q50_ratio": oc["q99"] / max(oc["q50"], EPS),
            })

        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(ncfiles)}  누적사건 {len(rows)}")

    df = pd.DataFrame(rows).merge(attrs, left_on="basin_id", right_index=True, how="left")
    out_csv = out_dir / "nondrbc_features_allrain.csv"
    df.to_csv(out_csv, index=False)
    print(f"\n전체 강우사건 {len(df)}개 → {out_csv}")
    print("obs_class 분포:")
    print(df["oc"].value_counts().sort_index().to_string())

    # Spearman 분석
    band_coupled = ["rel_width", "q99_q50_ratio"]
    forcing = ["rain_sum_event", "rain_max_1h", "nws_class", "cape_max", "crainf_frac_mean"]
    indep = ATTR_COLS + ["log_area"]
    cat = {
        **{m: "C" for m in band_coupled},
        **{m: "F" for m in forcing},
        **{m: "I" for m in indep},
    }
    res = []
    for m, c in cat.items():
        if m not in df.columns:
            continue
        sub = df[[m, "oc"]].dropna()
        if len(sub) < 10:
            continue
        r, p = spearmanr(sub[m], sub["oc"])
        res.append({"scope": "nondrbc_allrain", "metric": m, "category": c,
                    "spearman_r": r, "p_value": p, "n": len(sub)})

    sp_csv = out_dir / "nondrbc_allrain_spearman.csv"
    pd.DataFrame(res).to_csv(sp_csv, index=False)
    print(f"\nSpearman 결과 → {sp_csv}")
    print(pd.DataFrame(res).sort_values("spearman_r", key=abs, ascending=False).head(10).to_string(index=False))


if __name__ == "__main__":
    main()
