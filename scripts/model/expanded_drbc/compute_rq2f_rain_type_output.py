# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2.2", "numpy>=2.0", "matplotlib>=3.9"]
# ///
"""RQ-2f — 강우 유형별 Model 2 τ 출력분포 · α 패턴 (신규 분석).

목적
----
SHAP 분석이 발견한 강우 유형 구분법(대류성 CRainf_frac · CAPE)을 *차용*하되,
SHAP value 파일은 전혀 import하지 않고, NOAA 확인 홍수 사건에서 강우 유형별로
Model 2의 τ 출력이 관측 첨두를 어느 정도 포착하는지(출력분포)와 첨두 과소
정도(α = peak_under_deficit)가 어떻게 달라지는지를 새로 계산한다.

설계 제약 (절대 준수)
--------------------
- CRainf 중앙값 이분 임계를 **새로 정의하지 않는다**. ``_lib/expanded_drbc.py``의
  공용 함수 ``crainf_median_split`` 을 import 해 RQ-0(obs_class 층화 분포)과 단일
  출처(SSOT)를 공유한다.
- 산출 단위는 **출력값 차원**(첨두 포착률·α)이며 obs_class 분포가 아니다.
- SHAP value 파일 import 금지(이 스크립트는 shap 결과를 읽지 않는다).
- n-gate: 강우 유형 셀의 사건 수 n_events < 10 이면 통계를 suppress 하고 caveat
  로그를 남긴다(예: NOAA 이벤트타입 Flash Flood n=8 은 자동 제외 대상).
- draft 244행의 고/저 CRainf above_q99 비율(≈68% / ≈24%)이 동일 split에서 나온다는
  사실을 보존한다 — 본 스크립트는 그 split을 공유하고 group 크기·비율을 sanity로
  검증한다(obs_class 분포 자체를 재출력하지는 않는다).

입력
----
  output/model_analysis/primary/metrics/tables/rq2_alpha_event_peak_deficit_noaa.csv
      (basin_id, seed, peak_time, tau, peak_under_deficit) — NOAA-scope α (canonical)
  output/model_analysis/band_signal/signal_sweep/tables/forcing_features_noaa.csv
      (basin_id, peak_time, crainf_frac_mean_24h, cape_max_24h, oc_seed_mean ...)

출력
----
  output/model_analysis/primary/metrics/tables/rq2f_rain_type_tau_output.csv
  output/model_analysis/primary/metrics/tables/rq2f_rain_type_alpha.csv
  output/model_analysis/primary/metrics/tables/rq2f_rain_type_contrast.csv
  output/model_analysis/primary/metrics/figures/rq2f_rain_type_patterns.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]

# _lib 공용 함수(CRainf split SSOT) import
_LIB_ROOT = Path(__file__).resolve().parents[2] / "_lib"
if str(_LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(_LIB_ROOT))
from expanded_drbc import (  # noqa: E402
    TAU_ORDER,
    crainf_median_split,
    normalize_basin_id,
)

DEFAULT_METRICS_DIR = REPO_ROOT / "output/model_analysis/primary/metrics"
DEFAULT_FEAT_NOAA = (
    REPO_ROOT
    / "output/model_analysis/band_signal/signal_sweep/tables/forcing_features_noaa.csv"
)

N_GATE = 10  # 강우 유형 셀 사건 수 하한 (미만이면 suppress)


def _load_inputs(metrics_dir: Path, feat_noaa: Path):
    alpha = pd.read_csv(
        metrics_dir / "tables/rq2_alpha_event_peak_deficit_noaa.csv",
        comment="#",
        dtype={"basin_id": str},
    )
    alpha["basin_id"] = alpha["basin_id"].map(normalize_basin_id)
    alpha["peak_time"] = alpha["peak_time"].astype(str)

    feat = pd.read_csv(feat_noaa, dtype={"basin_id": str})
    feat["basin_id"] = feat["basin_id"].map(normalize_basin_id)
    feat["peak_time"] = feat["peak_time"].astype(str)
    return alpha, feat


def _assign_rain_groups(feat: pd.DataFrame) -> pd.DataFrame:
    """강우 유형 그룹 부여 — CRainf(SSOT) primary + CAPE auxiliary."""
    out = feat[["basin_id", "peak_time", "crainf_frac_mean_24h", "cape_max_24h"]].copy()

    crainf = out.dropna(subset=["crainf_frac_mean_24h"]).copy()
    crainf["rain_type"] = crainf_median_split(crainf["crainf_frac_mean_24h"])
    crainf["split_axis"] = "CRainf (convective fraction)"

    cape = out.dropna(subset=["cape_max_24h"]).copy()
    # CAPE auxiliary axis — CRainf SSOT 임계와 무관한 보조 분할(별도 축)
    cape["rain_type"] = pd.qcut(
        cape["cape_max_24h"], q=2,
        labels=["Low CAPE (bot. 50%)", "High CAPE (top 50%)"],
    )
    cape["split_axis"] = "CAPE (convective energy)"

    keep = ["basin_id", "peak_time", "split_axis", "rain_type"]
    return pd.concat([crainf[keep], cape[keep]], ignore_index=True)


def _sanity_preserve_draft_244(feat: pd.DataFrame) -> None:
    """동일 CRainf split이 draft 244행 68/24 above_q99 비율을 재현하는지 검증.

    obs_class 분포를 재출력하지 않고, split이 RQ-0와 동일함만 확인한다.
    """
    sub = feat.dropna(subset=["crainf_frac_mean_24h", "oc_seed_mean"]).copy()
    sub["crainf_group"] = crainf_median_split(sub["crainf_frac_mean_24h"])
    sub["above_q99"] = (sub["oc_seed_mean"].round().clip(0, 4).astype(int) == 4)
    prop = sub.groupby("crainf_group", observed=True)["above_q99"].mean() * 100
    size = sub.groupby("crainf_group", observed=True).size()
    print("[sanity] CRainf split SSOT 검증 (draft 244행 68/24 보존):")
    for grp in prop.index:
        print(f"  {grp}: n={int(size[grp])}, above_q99={prop[grp]:.2f}%")
    hi = prop.get("High CRainf (top 50%)")
    lo = prop.get("Low CRainf (bot. 50%)")
    if hi is not None and lo is not None:
        assert abs(hi - 67.86) < 1.0, f"High CRainf above_q99 {hi:.2f}% != ~68% (RQ-0 SSOT drift)"
        assert abs(lo - 24.14) < 1.0, f"Low CRainf above_q99 {lo:.2f}% != ~24% (RQ-0 SSOT drift)"
        print("  → RQ-0 SSOT 일치 (split 동일 출처 확인).")


def _aggregate(merged: pd.DataFrame) -> pd.DataFrame:
    """seed-median(사건 단위) → 강우유형×τ 집계 + n-gate suppress."""
    merged = merged.copy()
    # capture fraction = 관측 첨두 중 τ 출력이 포착한 비율 = 1 - 첨두 과소(deficit)
    merged["capture"] = (1.0 - merged["peak_under_deficit"]).clip(0.0, 1.0)

    # 1) 사건 단위 seed-median (이상치 시드에 강건)
    per_event = (
        merged.groupby(["split_axis", "rain_type", "basin_id", "peak_time", "tau"], observed=True)
        .agg(capture=("capture", "median"), deficit=("peak_under_deficit", "median"))
        .reset_index()
    )

    rows = []
    for (axis, rtype, tau), g in per_event.groupby(["split_axis", "rain_type", "tau"], observed=True):
        n_events = g[["basin_id", "peak_time"]].drop_duplicates().shape[0]
        suppressed = n_events < N_GATE
        rec = {
            "split_axis": axis,
            "rain_type": str(rtype),
            "tau": tau,
            "n_events": n_events,
            "suppressed": suppressed,
        }
        if suppressed:
            for c in ("capture_median", "capture_q25", "capture_q75",
                      "capture_mean", "capture_std", "alpha_median"):
                rec[c] = np.nan
        else:
            cap = g["capture"]
            rec.update({
                "capture_median": cap.median(),
                "capture_q25": cap.quantile(0.25),
                "capture_q75": cap.quantile(0.75),
                "capture_mean": cap.mean(),
                "capture_std": cap.std(ddof=1) if len(cap) > 1 else 0.0,
                "alpha_median": g["deficit"].median(),
            })
        rows.append(rec)

    tau_rank = {t: i for i, t in enumerate(TAU_ORDER)}
    df = pd.DataFrame(rows)
    df["_tr"] = df["tau"].map(tau_rank)
    df = df.sort_values(["split_axis", "rain_type", "_tr"]).drop(columns="_tr").reset_index(drop=True)
    return df


def _contrast(agg: pd.DataFrame) -> pd.DataFrame:
    """CRainf 축에서 High(대류성) vs Low(전선성) α 대비 (suppress 셀 제외)."""
    cr = agg[agg["split_axis"].str.startswith("CRainf")].copy()
    cr = cr[~cr["suppressed"]]
    piv = cr.pivot_table(index="tau", columns="rain_type", values="alpha_median", observed=True)
    hi_col = "High CRainf (top 50%)"
    lo_col = "Low CRainf (bot. 50%)"
    rows = []
    for tau in TAU_ORDER:
        if tau not in piv.index:
            continue
        hi = piv.loc[tau].get(hi_col, np.nan)
        lo = piv.loc[tau].get(lo_col, np.nan)
        ratio = (hi / lo) if (pd.notna(hi) and pd.notna(lo) and lo > 0) else np.nan
        rows.append({
            "tau": tau,
            "alpha_high_crainf_convective": hi,
            "alpha_low_crainf_frontal": lo,
            "convective_over_frontal_ratio": ratio,
        })
    return pd.DataFrame(rows)


def _plot(agg: pd.DataFrame, fig_path: Path) -> None:
    cr = agg[agg["split_axis"].str.startswith("CRainf") & ~agg["suppressed"]].copy()
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    colors = {"High CRainf (top 50%)": "#d73027", "Low CRainf (bot. 50%)": "#4575b4"}
    labels = {"High CRainf (top 50%)": "Convective (high CRainf)",
              "Low CRainf (bot. 50%)": "Frontal (low CRainf)"}
    x = list(TAU_ORDER)
    xi = range(len(x))

    for rtype, g in cr.groupby("rain_type", observed=True):
        g = g.set_index("tau").reindex(x)
        c = colors.get(str(rtype), "#444444")
        lbl = labels.get(str(rtype), str(rtype))
        axes[0].plot(xi, g["capture_median"].values, "-o", color=c, label=lbl)
        axes[1].plot(xi, g["alpha_median"].values, "-o", color=c, label=lbl)

    axes[0].set_title("Peak capture fraction by τ")
    axes[0].set_ylabel("Captured fraction of obs peak (median)")
    axes[1].set_title("Peak under-deficit α by τ")
    axes[1].set_ylabel("α = peak under-deficit (median)")
    for ax in axes:
        ax.set_xticks(list(xi))
        ax.set_xticklabels(x, rotation=20)
        ax.set_xlabel("τ (prediction level)")
        ax.grid(alpha=0.3)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(frameon=False, fontsize=9)
    fig.suptitle("RQ-2f — Rain-type τ output & α pattern (NOAA flood events)")
    fig.tight_layout()
    fig.savefig(fig_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics-dir", type=Path, default=DEFAULT_METRICS_DIR)
    parser.add_argument("--feat-noaa", type=Path, default=DEFAULT_FEAT_NOAA)
    args = parser.parse_args(argv)

    tables_dir = args.metrics_dir / "tables"
    figures_dir = args.metrics_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    alpha, feat = _load_inputs(args.metrics_dir, args.feat_noaa)
    print(f"[in] NOAA α rows={len(alpha)}, NOAA features rows={len(feat)}")

    # draft 244 SSOT 보존 검증
    _sanity_preserve_draft_244(feat)

    groups = _assign_rain_groups(feat)
    merged = alpha.merge(groups, on=["basin_id", "peak_time"], how="inner")
    n_ev = merged[["basin_id", "peak_time"]].drop_duplicates().shape[0]
    print(f"[join] α × rain-type inner-join: {len(merged)} rows, {n_ev} unique events")

    agg = _aggregate(merged)

    # n-gate caveat 로그
    sup = agg[agg["suppressed"]]
    if len(sup):
        for axis, g in sup.groupby("split_axis", observed=True):
            cells = sorted(g["rain_type"].unique())
            ns = {r: int(g[g["rain_type"] == r]["n_events"].iloc[0]) for r in cells}
            print(f"[n-gate] suppressed (n<{N_GATE}) on {axis}: {ns}")
    else:
        print(f"[n-gate] no cell below n={N_GATE} (all rain-type groups retained).")

    contrast = _contrast(agg)

    # 출력 테이블 분리: τ 출력분포 vs α 패턴
    out_cols = ["split_axis", "rain_type", "tau", "n_events", "suppressed"]
    tau_output = agg[out_cols + ["capture_median", "capture_q25", "capture_q75",
                                 "capture_mean", "capture_std"]]
    alpha_pattern = agg[out_cols + ["alpha_median"]]

    p_out = tables_dir / "rq2f_rain_type_tau_output.csv"
    p_alpha = tables_dir / "rq2f_rain_type_alpha.csv"
    p_contrast = tables_dir / "rq2f_rain_type_contrast.csv"
    with p_out.open("w") as f:
        f.write("# RQ-2f — rain-type × τ 출력분포(첨두 포착률). n_events<10 셀은 suppress.\n")
        tau_output.to_csv(f, index=False)
    with p_alpha.open("w") as f:
        f.write("# RQ-2f — rain-type × τ α(peak_under_deficit) 패턴. n_events<10 셀은 suppress.\n")
        alpha_pattern.to_csv(f, index=False)
    with p_contrast.open("w") as f:
        f.write("# RQ-2f — CRainf축 대류성(High) vs 전선성(Low) α 대비.\n")
        contrast.to_csv(f, index=False)

    fig_path = figures_dir / "rq2f_rain_type_patterns.png"
    _plot(agg, fig_path)

    print(f"[out] {p_out}")
    print(f"[out] {p_alpha}")
    print(f"[out] {p_contrast}")
    print(f"[out] {fig_path}")
    print("\n=== α 패턴 (CRainf 축) ===")
    print(alpha_pattern[alpha_pattern.split_axis.str.startswith("CRainf")].to_string(index=False))
    print("\n=== 대류성/전선성 α 대비 ===")
    print(contrast.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
