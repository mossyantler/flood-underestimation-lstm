#!/usr/bin/env python3
"""DRBC 유역별 진단 리포트 카드 데이터 계산."""
# /// script
# dependencies = [
#   "matplotlib>=3.8",
#   "numpy>=1.26",
#   "pandas>=2.2",
#   "scipy>=1.13",
#   "statsmodels>=0.14",
# ]
# ///

import logging
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from statsmodels.stats.multitest import multipletests

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

OFFICIAL_SEEDS = [111, 222, 444]
PRIMARY_EPOCHS = {
    111: {"model1": 25, "model2": 5},
    222: {"model1": 10, "model2": 10},
    444: {"model1": 15, "model2": 10},
}
Q_BIN_LABELS = ["Q0-Q50", "Q50-Q90", "Q90-Q99", "Q99+"]
SEASONS = {"DJF": [12, 1, 2], "MAM": [3, 4, 5],
           "JJA": [6, 7, 8], "SON": [9, 10, 11]}

SERIES_ROOT  = Path("output/model_analysis/legacy/quantile_analysis/required_series")
ATTR_FILE    = Path("output/basin/drbc/analysis/basin_attributes/tables/drbc_selected_basin_analysis_table.csv")
METRICS_FILE = Path("output/model_analysis/legacy/overall_analysis/epoch_sensitivity/tables/basin_metrics.csv")
OUTPUT_ROOT  = Path("output/model_analysis/legacy/overall_analysis/main_comparison/drbc_basin_report_cards")

FEATURE_COLS = [
    "drain_sqkm_attr", "log10_area", "frac_snow", "p_seasonality",
    "lat_gage", "elev_mean_m", "slope_pct", "developed_frac",
    "forest_frac", "soil_permeability_index", "aridity",
    "baseflow_index_pct", "high_prec_freq", "soil_available_water_capacity",
    "SANDAVE", "CLAYAVE",
]

def _get_basin_ids() -> list[str]:
    df = pd.read_csv(METRICS_FILE, dtype={"basin": str})
    return sorted(df["basin"].str.zfill(8).unique().tolist())

def _season_of(month: int) -> str:
    for s, months in SEASONS.items():
        if month in months:
            return s
    return "UNK"

def load_series_one_seed(seed: int) -> pd.DataFrame:
    """한 seed의 primary epoch 시리즈 로드. datetime 파싱 포함."""
    epoch = PRIMARY_EPOCHS[seed]["model2"]
    path = SERIES_ROOT / f"seed{seed}" / f"epoch{epoch:03d}_required_series.csv"
    log.info("  loading %s", path)
    df = pd.read_csv(path, dtype={"basin": str}, parse_dates=["datetime"])
    df["basin"] = df["basin"].str.zfill(8)
    df = df.dropna(subset=["obs"])
    df = df[df["obs"] > 0].copy()
    return df

def compute_q_bin_boundaries(obs: np.ndarray) -> dict[str, tuple[float, float]]:
    """유역별 Q-bin 경계값 반환. obs는 test period 전체 obs 배열."""
    p50 = np.percentile(obs, 50)
    p90 = np.percentile(obs, 90)
    p99 = np.percentile(obs, 99)
    return {
        "Q0-Q50":  (0.0,  p50),
        "Q50-Q90": (p50,  p90),
        "Q90-Q99": (p90,  p99),
        "Q99+":    (p99,  np.inf),
    }

def assign_q_bin(obs: np.ndarray, boundaries: dict) -> np.ndarray:
    """각 obs 값에 Q-bin 레이블 할당."""
    labels = np.full(len(obs), "", dtype=object)
    for label, (lo, hi) in boundaries.items():
        mask = (obs > lo) & (obs <= hi)
        if label == "Q0-Q50":
            mask = obs <= hi
        labels[mask] = label
    return labels


def compute_flow_regime_perf_one_seed(df: pd.DataFrame) -> pd.DataFrame:
    """한 seed의 시리즈에서 유역별 Q-bin별 성능 계산."""
    records = []
    for basin, grp in df.groupby("basin"):
        obs  = grp["obs"].values
        m1   = grp["model1"].values
        q50  = grp["q50"].values
        q90  = grp["q90"].values
        q99  = grp["q99"].values
        bounds = compute_q_bin_boundaries(obs)
        bins   = assign_q_bin(obs, bounds)

        for label in Q_BIN_LABELS:
            mask = bins == label
            if mask.sum() < 5:
                continue
            o  = obs[mask]; p1 = m1[mask]
            p50b = q50[mask]; p90b = q90[mask]; p99b = q99[mask]

            m1_mape   = float(np.mean(np.abs(o - p1) / o) * 100)
            m2_mape   = float(np.mean(np.abs(o - p50b) / o) * 100)
            m1_bias   = float((np.mean(p1) - np.mean(o)) / np.mean(o) * 100)
            m2_bias   = float((np.mean(p50b) - np.mean(o)) / np.mean(o) * 100)
            cov_q90   = float(np.mean(o <= p90b))
            cov_q99   = float(np.mean(o <= p99b))
            width_rat = float(np.mean((p99b - p50b) / o))

            records.append({
                "basin": basin, "q_bin": label,
                "m1_mape": m1_mape, "m2_q50_mape": m2_mape,
                "m1_bias": m1_bias, "m2_q50_bias": m2_bias,
                "m2_q90_coverage": cov_q90, "m2_q99_coverage": cov_q99,
                "m2_interval_width_ratio": width_rat,
                "n_hours": int(mask.sum()),
            })
    return pd.DataFrame(records)


def aggregate_flow_regime_perf(basin_ids: list[str]) -> pd.DataFrame:
    """3 seed 각각 계산 후 중앙값 집계."""
    frames = []
    for seed in OFFICIAL_SEEDS:
        df = load_series_one_seed(seed)
        frames.append(compute_flow_regime_perf_one_seed(df))
    stacked = pd.concat(frames)
    metric_cols = ["m1_mape", "m2_q50_mape", "m1_bias", "m2_q50_bias",
                   "m2_q90_coverage", "m2_q99_coverage", "m2_interval_width_ratio", "n_hours"]
    return stacked.groupby(["basin", "q_bin"])[metric_cols].median().reset_index()


def compute_seasonal_perf_one_seed(df: pd.DataFrame) -> pd.DataFrame:
    """유역별 계절별 MAPE / Bias + Q99+ 계절 분포."""
    df = df.copy()
    df["month"]  = df["datetime"].dt.month
    df["season"] = df["month"].map(_season_of)

    records = []
    for basin, grp in df.groupby("basin"):
        obs = grp["obs"].values
        p99_thresh = np.percentile(obs, 99)

        for season in SEASONS:
            mask = grp["season"] == season
            if mask.sum() < 5:
                continue
            o  = grp.loc[mask, "obs"].values
            p1 = grp.loc[mask, "model1"].values

            m1_mape = float(np.mean(np.abs(o - p1) / o) * 100)
            m1_bias = float((np.mean(p1) - np.mean(o)) / np.mean(o) * 100)

            q99_mask = grp["obs"] > p99_thresh
            q99_season_cnt = int((q99_mask & mask).sum())

            records.append({
                "basin": basin, "season": season,
                "m1_mape": m1_mape, "m1_bias": m1_bias,
                "q99_hour_count": q99_season_cnt,
                "n_hours": int(mask.sum()),
            })
    return pd.DataFrame(records)


def aggregate_seasonal_perf(basin_ids: list[str]) -> pd.DataFrame:
    frames = []
    for seed in OFFICIAL_SEEDS:
        df = load_series_one_seed(seed)
        frames.append(compute_seasonal_perf_one_seed(df))
    stacked = pd.concat(frames)
    metric_cols = ["m1_mape", "m1_bias", "q99_hour_count", "n_hours"]
    return stacked.groupby(["basin", "season"])[metric_cols].median().reset_index()


def detect_flood_events(obs_series: pd.Series, datetime_series: pd.Series,
                        q95_thresh: float) -> list[dict]:
    """
    Q95 초과 이산 홍수 사건 목록 반환.
    - 24시간 미만 갭은 동일 사건으로 병합
    - 최소 3시간 지속 사건만 포함
    """
    obs = obs_series.values
    dts = datetime_series.values
    above = obs > q95_thresh

    events_raw = []
    in_event = False
    start = 0
    for i in range(len(obs)):
        if above[i] and not in_event:
            in_event = True
            start = i
        elif not above[i] and in_event:
            in_event = False
            events_raw.append((start, i - 1))
    if in_event:
        events_raw.append((start, len(obs) - 1))

    merged = []
    for ev in events_raw:
        if merged and (ev[0] - merged[-1][1]) <= 24:
            merged[-1] = (merged[-1][0], ev[1])
        else:
            merged.append(list(ev))

    result = []
    for s, e in merged:
        if (e - s + 1) < 3:
            continue
        peak_idx = s + int(np.argmax(obs[s:e+1]))
        result.append({
            "start_idx": s, "end_idx": e, "peak_idx": peak_idx,
            "start_dt": dts[s], "end_dt": dts[e], "peak_dt": dts[peak_idx],
        })
    return result


def compute_event_peak_errors_one_seed(df: pd.DataFrame) -> pd.DataFrame:
    """사건별 peak_ratio, timing_error, volume_error 계산."""
    records = []
    for basin, grp in df.groupby("basin"):
        grp = grp.reset_index(drop=True)
        obs  = grp["obs"].values
        m1   = grp["model1"].values
        dts  = grp["datetime"].values
        q95  = float(np.percentile(obs, 95))
        events = detect_flood_events(grp["obs"], grp["datetime"], q95)

        for i, ev in enumerate(events):
            s, e, pi = ev["start_idx"], ev["end_idx"], ev["peak_idx"]
            obs_seg = obs[s:e+1]; m1_seg = m1[s:e+1]
            obs_peak = float(obs[pi])
            m1_peak  = float(m1[pi])

            m1_peak_idx_local = int(np.argmax(m1_seg))
            m1_peak_dt = dts[s + m1_peak_idx_local]
            obs_peak_dt = dts[pi]
            timing_err_h = float(
                (pd.Timestamp(m1_peak_dt) - pd.Timestamp(obs_peak_dt))
                .total_seconds() / 3600
            )

            vol_err_pct = float(
                (np.sum(m1_seg) - np.sum(obs_seg)) / np.sum(obs_seg) * 100
            ) if np.sum(obs_seg) > 0 else np.nan

            peak_month = pd.Timestamp(obs_peak_dt).month
            season = _season_of(peak_month)

            records.append({
                "basin": basin,
                "event_id": i,
                "peak_dt": str(obs_peak_dt),
                "obs_peak": obs_peak,
                "m1_peak": m1_peak,
                "m1_peak_ratio": m1_peak / obs_peak if obs_peak > 0 else np.nan,
                "m1_timing_error_h": timing_err_h,
                "m1_volume_error_pct": vol_err_pct,
                "season": season,
                "n_hours": e - s + 1,
            })
    return pd.DataFrame(records)


def aggregate_event_peak_errors(basin_ids: list[str]) -> pd.DataFrame:
    """3 seed 중앙값 집계."""
    frames = []
    for seed in OFFICIAL_SEEDS:
        df = load_series_one_seed(seed)
        f = compute_event_peak_errors_one_seed(df)
        f["seed"] = seed
        frames.append(f)
    stacked = pd.concat(frames)
    metric_cols = ["m1_peak_ratio", "m1_timing_error_h", "m1_volume_error_pct"]
    base = stacked[stacked["seed"] == 111][["basin", "event_id", "peak_dt",
                                             "obs_peak", "season", "n_hours"]].copy()
    agg = stacked.groupby(["basin", "event_id"])[metric_cols].median().reset_index()
    return base.merge(agg, on=["basin", "event_id"], how="inner")


def compute_event_summary(event_df: pd.DataFrame) -> pd.DataFrame:
    """유역별 사건 요약 통계."""
    records = []
    for basin, grp in event_df.groupby("basin"):
        capture_rate = float((grp["m1_peak_ratio"] >= 0.7).mean() * 100)
        records.append({
            "basin": basin,
            "n_events": len(grp),
            "capture_rate_pct": capture_rate,
            "median_peak_ratio": float(grp["m1_peak_ratio"].median()),
            "median_timing_error_h": float(grp["m1_timing_error_h"].median()),
        })
    return pd.DataFrame(records)


def compute_antecedent_perf_one_seed(df: pd.DataFrame) -> pd.DataFrame:
    """사건별 선행 조건 분류 후 조건별 M1 MAPE / Bias 계산."""
    records = []
    for basin, grp in df.groupby("basin"):
        grp = grp.reset_index(drop=True)
        obs = grp["obs"].values
        m1  = grp["model1"].values
        dts = pd.DatetimeIndex(grp["datetime"])
        q95 = float(np.percentile(obs, 95))
        events = detect_flood_events(grp["obs"], grp["datetime"], q95)
        if len(events) < 3:
            continue

        ante_means = []
        for ev in events:
            s = ev["start_idx"]
            start_dt = pd.Timestamp(dts[s])
            lookback_start = start_dt - pd.Timedelta(days=7)
            ante_mask = (dts >= lookback_start) & (dts < start_dt)
            if ante_mask.sum() < 24:
                ante_means.append(np.nan)
            else:
                ante_means.append(float(np.mean(obs[np.array(ante_mask)])))

        ante_arr = np.array(ante_means)
        valid = np.isfinite(ante_arr)
        if valid.sum() < 3:
            continue

        p33 = np.percentile(ante_arr[valid], 33)
        p67 = np.percentile(ante_arr[valid], 67)

        def classify(v):
            if np.isnan(v): return None
            if v <= p33: return "dry"
            if v <= p67: return "normal"
            return "wet"

        for condition in ["dry", "normal", "wet"]:
            all_obs_list, all_m1_list = [], []
            for ev, ante in zip(events, ante_arr):
                if classify(ante) != condition:
                    continue
                s2, e2 = ev["start_idx"], ev["end_idx"]
                all_obs_list.append(obs[s2:e2+1])
                all_m1_list.append(m1[s2:e2+1])

            if not all_obs_list:
                continue
            o_all = np.concatenate(all_obs_list)
            p_all = np.concatenate(all_m1_list)
            mask = o_all > 0
            if mask.sum() < 5:
                continue
            records.append({
                "basin": basin, "condition": condition,
                "n_events": len(all_obs_list),
                "m1_mape": float(np.mean(np.abs(o_all[mask] - p_all[mask]) / o_all[mask]) * 100),
                "m1_bias": float((np.mean(p_all[mask]) - np.mean(o_all[mask])) / np.mean(o_all[mask]) * 100),
            })
    return pd.DataFrame(records)


def aggregate_antecedent_perf(basin_ids: list[str]) -> pd.DataFrame:
    frames = []
    for seed in OFFICIAL_SEEDS:
        df = load_series_one_seed(seed)
        frames.append(compute_antecedent_perf_one_seed(df))
    stacked = pd.concat(frames)
    return stacked.groupby(["basin", "condition"])[
        ["n_events", "m1_mape", "m1_bias"]].median().reset_index()


def compute_rising_falling_one_seed(df: pd.DataFrame) -> pd.DataFrame:
    """유역별 rising / falling limb M1 Bias 계산."""
    records = []
    for basin, grp in df.groupby("basin"):
        grp = grp.reset_index(drop=True)
        obs = grp["obs"].values
        m1  = grp["model1"].values
        q50 = grp["q50"].values
        q95 = float(np.percentile(obs, 95))
        events = detect_flood_events(grp["obs"], grp["datetime"], q95)
        if len(events) < 3:
            continue

        rising_obs, rising_m1, rising_q50 = [], [], []
        falling_obs, falling_m1, falling_q50 = [], [], []

        for ev in events:
            s, e, pi = ev["start_idx"], ev["end_idx"], ev["peak_idx"]
            if pi - s >= 3:
                rising_obs.extend(obs[s:pi].tolist())
                rising_m1.extend(m1[s:pi].tolist())
                rising_q50.extend(q50[s:pi].tolist())
            if e - pi >= 3:
                falling_obs.extend(obs[pi+1:e+1].tolist())
                falling_m1.extend(m1[pi+1:e+1].tolist())
                falling_q50.extend(q50[pi+1:e+1].tolist())

        for phase, o_list, m1_list, q50_list in [
            ("rising",  rising_obs,  rising_m1,  rising_q50),
            ("falling", falling_obs, falling_m1, falling_q50),
        ]:
            if len(o_list) < 5:
                continue
            o  = np.array(o_list); p1 = np.array(m1_list); p50 = np.array(q50_list)
            mask = o > 0
            if mask.sum() < 5:
                continue
            records.append({
                "basin": basin, "phase": phase,
                "m1_bias": float((np.mean(p1[mask]) - np.mean(o[mask])) / np.mean(o[mask]) * 100),
                "m2_q50_bias": float((np.mean(p50[mask]) - np.mean(o[mask])) / np.mean(o[mask]) * 100),
                "n_timesteps": int(mask.sum()),
            })
    return pd.DataFrame(records)


def aggregate_rising_falling(basin_ids: list[str]) -> pd.DataFrame:
    frames = []
    for seed in OFFICIAL_SEEDS:
        df = load_series_one_seed(seed)
        frames.append(compute_rising_falling_one_seed(df))
    stacked = pd.concat(frames)
    return stacked.groupby(["basin", "phase"])[
        ["m1_bias", "m2_q50_bias", "n_timesteps"]].median().reset_index()


def load_basin_features() -> pd.DataFrame:
    raw = pd.read_csv(ATTR_FILE, dtype={"gauge_id": str})
    raw["gauge_id"] = raw["gauge_id"].str.zfill(8)
    raw = raw.rename(columns={"gauge_id": "basin"})
    raw["log10_area"] = np.log10(raw["drain_sqkm_attr"].clip(lower=1e-3))
    return raw.set_index("basin")


def compute_feature_regime_corr(regime_df: pd.DataFrame,
                                 feat_df: pd.DataFrame,
                                 fdr_alpha: float = 0.05) -> pd.DataFrame:
    """Q-bin별 feature × {m1_mape, m1_bias, m2_q50_mape, m2_q99_coverage} 상관."""
    metric_cols = ["m1_mape", "m1_bias", "m2_q50_mape", "m2_q99_coverage"]
    rows = []
    for q_bin in Q_BIN_LABELS:
        sub = regime_df[regime_df["q_bin"] == q_bin].set_index("basin")
        for feat in FEATURE_COLS:
            if feat not in feat_df.columns:
                continue
            for metric in metric_cols:
                if metric not in sub.columns:
                    continue
                x = feat_df[feat]
                y = sub[metric]
                common = x.index.intersection(y.index)
                valid = x[common].notna() & y[common].notna()
                if valid.sum() < 5:
                    continue
                r = spearmanr(x[common][valid], y[common][valid])
                rows.append({
                    "q_bin": q_bin, "feature": feat, "metric": metric,
                    "rho": r.statistic, "pval": r.pvalue, "n": int(valid.sum()),
                })

    if not rows:
        return pd.DataFrame()
    corr_df = pd.DataFrame(rows)
    _, padj, _, _ = multipletests(corr_df["pval"], alpha=fdr_alpha, method="fdr_bh")
    corr_df["pval_bh"] = padj
    corr_df["significant"] = padj < fdr_alpha
    return corr_df.sort_values("rho", key=abs, ascending=False)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--fdr-alpha", type=float, default=0.05)
    args = parser.parse_args()

    tbl = OUTPUT_ROOT / "tables"
    tbl.mkdir(parents=True, exist_ok=True)

    basin_ids = _get_basin_ids()
    log.info("basins: %d", len(basin_ids))

    log.info("=== flow regime performance ===")
    regime = aggregate_flow_regime_perf(basin_ids)
    regime.to_csv(tbl / "flow_regime_performance.csv", index=False)
    log.info("  shape: %s", regime.shape)

    log.info("=== seasonal performance ===")
    seasonal = aggregate_seasonal_perf(basin_ids)
    seasonal.to_csv(tbl / "seasonal_performance.csv", index=False)
    log.info("  shape: %s", seasonal.shape)

    log.info("=== event peak errors ===")
    event_df = aggregate_event_peak_errors(basin_ids)
    event_df.to_csv(tbl / "event_peak_errors.csv", index=False)
    log.info("  shape: %s", event_df.shape)
    summary_df = compute_event_summary(event_df)
    summary_df.to_csv(tbl / "event_summary_per_basin.csv", index=False)
    log.info("  summary shape: %s", summary_df.shape)

    log.info("=== antecedent conditions ===")
    ante = aggregate_antecedent_perf(basin_ids)
    ante.to_csv(tbl / "antecedent_condition_perf.csv", index=False)
    log.info("  shape: %s", ante.shape)

    log.info("=== rising/falling asymmetry ===")
    rf = aggregate_rising_falling(basin_ids)
    rf.to_csv(tbl / "rising_falling_bias.csv", index=False)
    log.info("  shape: %s", rf.shape)

    log.info("=== feature-regime correlations ===")
    feat_df = load_basin_features()
    corr = compute_feature_regime_corr(regime, feat_df, args.fdr_alpha)
    corr.to_csv(tbl / "feature_regime_correlations.csv", index=False)
    log.info("  pairs: %d, significant: %d", len(corr), int(corr["significant"].sum()))

    log.info("=== done: %s ===", tbl)


if __name__ == "__main__":
    main()
