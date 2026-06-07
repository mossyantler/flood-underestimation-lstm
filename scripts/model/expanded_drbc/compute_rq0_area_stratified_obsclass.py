# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas", "matplotlib", "numpy"]
# ///
"""
RQ-0 gate: feature 층화(stratified)별 obs_class 분포.

- Q99 scope  : basin area 사분위(Q1~Q4) × obs_class 분포
- NOAA scope : basin area 사분위 × obs_class 분포
- NOAA scope : CRainf_frac 중앙값 이분 × obs_class 분포

입력: static/B feature tables (이미 seed 평균 포함)
출력:
  output/model_analysis/band_signal/signal_sweep/tables/rq0_area_stratified_obsclass_q99.csv
  output/model_analysis/band_signal/signal_sweep/tables/rq0_area_stratified_obsclass_noaa.csv
  output/model_analysis/band_signal/signal_sweep/tables/rq0_crainf_stratified_obsclass_noaa.csv
  output/model_analysis/band_signal/signal_sweep/figures/rq0_stratified_obsclass.png
"""

import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path(__file__).parents[3]

# CRainf median split는 _lib 공용 함수(단일 출처)에서 가져온다 — rq0/rq2f 공유.
_LIB_ROOT = Path(__file__).resolve().parents[2] / "_lib"
if str(_LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(_LIB_ROOT))
from expanded_drbc import crainf_median_split  # noqa: E402

FEAT_Q99  = ROOT / "output/model_analysis/band_signal/signal_sweep/tables/static_features_q99.csv"
FEAT_NOAA_A = ROOT / "output/model_analysis/band_signal/signal_sweep/tables/static_features_noaa.csv"
FEAT_NOAA_B = ROOT / "output/model_analysis/band_signal/signal_sweep/tables/forcing_features_noaa.csv"

OUT_TABLES  = ROOT / "output/model_analysis/band_signal/signal_sweep/tables"
OUT_FIGURES = ROOT / "output/model_analysis/band_signal/signal_sweep/figures"

OC_ORDER  = ["below_q50", "q50_to_q90", "q90_to_q95", "q95_to_q99", "above_q99"]
OC_LABELS = ["< q50", "q50–q90", "q90–q95", "q95–q99", "> q99"]
# blue(과소추정 없음) → red(q99도 과소추정)
OC_COLORS = ["#4575b4", "#91bfdb", "#fee090", "#fc8d59", "#d73027"]

OC_MAP = {i: c for i, c in enumerate(OC_ORDER)}


def oc_mean_to_class(series: pd.Series) -> pd.Series:
    """oc_seed_mean(0~4 float) → obs_class string."""
    return series.round().clip(0, 4).astype(int).map(OC_MAP)


def assign_area_quartile(df: pd.DataFrame) -> pd.DataFrame:
    """basin area 기준 Q1(소)~Q4(대) 사분위 그룹 할당."""
    basin_area = df.groupby("basin_id")["area"].first().reset_index()
    basin_area["area_group"] = pd.qcut(
        basin_area["area"], q=4,
        labels=["Q1 (small)", "Q2", "Q3", "Q4 (large)"]
    )
    return df.merge(basin_area[["basin_id", "area_group"]], on="basin_id", how="left")


def obsclass_dist(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """그룹별 obs_class 비율 테이블 반환 (wide format)."""
    counts = (
        df.groupby([group_col, "obs_class"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=OC_ORDER, fill_value=0)
    )
    n_events = counts.sum(axis=1)
    pct = counts.div(n_events, axis=0) * 100
    pct.insert(0, "n_events", n_events)
    return pct


def plot_stacked_bar(ax, pct_df: pd.DataFrame, title: str):
    groups = list(pct_df.index)
    bottom = np.zeros(len(groups))
    for oc, label, color in zip(OC_ORDER, OC_LABELS, OC_COLORS):
        vals = pct_df[oc].values
        ax.barh(groups, vals, left=bottom, color=color, label=label, height=0.55)
        for j, (v, b) in enumerate(zip(vals, bottom)):
            if v > 7:
                ax.text(b + v / 2, j, f"{v:.0f}%",
                        ha="center", va="center", fontsize=8,
                        color="white", fontweight="bold")
        bottom += vals

    ax.set_xlim(0, 100)
    ax.set_xlabel("Event proportion (%)")
    ax.set_title(title, fontsize=10, pad=6)
    ax.invert_yaxis()
    ax.spines[["top", "right"]].set_visible(False)

    for j, g in enumerate(groups):
        n = int(pct_df.loc[g, "n_events"])
        ax.text(102, j, f"n={n}", va="center", fontsize=8, color="#666")


# ── Q99 scope: area 사분위 ───────────────────────────────────────────────────
feat_q99 = pd.read_csv(FEAT_Q99, dtype={"basin_id": str})
feat_q99["obs_class"] = oc_mean_to_class(feat_q99["oc_seed_mean"])
feat_q99 = assign_area_quartile(feat_q99)

pct_q99_area = obsclass_dist(feat_q99.dropna(subset=["area_group", "obs_class"]), "area_group")
pct_q99_area.to_csv(OUT_TABLES / "rq0_area_stratified_obsclass_q99.csv")

# ── NOAA scope: area 사분위 ──────────────────────────────────────────────────
feat_noaa_a = pd.read_csv(FEAT_NOAA_A, dtype={"basin_id": str})
feat_noaa_a["obs_class"] = oc_mean_to_class(feat_noaa_a["oc_seed_mean"])
feat_noaa_a = assign_area_quartile(feat_noaa_a)

pct_noaa_area = obsclass_dist(feat_noaa_a.dropna(subset=["area_group", "obs_class"]), "area_group")
pct_noaa_area.to_csv(OUT_TABLES / "rq0_area_stratified_obsclass_noaa.csv")

# ── NOAA scope: CRainf 중앙값 이분 ──────────────────────────────────────────
feat_noaa_b = pd.read_csv(FEAT_NOAA_B, dtype={"basin_id": str})
feat_noaa_b["obs_class"] = oc_mean_to_class(feat_noaa_b["oc_seed_mean"])
feat_noaa_b = feat_noaa_b.dropna(subset=["crainf_frac_mean_24h", "obs_class"]).copy()
feat_noaa_b["crainf_group"] = crainf_median_split(feat_noaa_b["crainf_frac_mean_24h"])
pct_noaa_crainf = obsclass_dist(feat_noaa_b.dropna(subset=["crainf_group"]), "crainf_group")
pct_noaa_crainf.to_csv(OUT_TABLES / "rq0_crainf_stratified_obsclass_noaa.csv")

# ── 콘솔 출력 ───────────────────────────────────────────────────────────────
print("=== RQ-0 층화 분석: feature 그룹별 obs_class 분포 ===\n")
print("[Q99 scope — area 사분위]")
print(pct_q99_area.to_string())
print("\n[NOAA scope — area 사분위]")
print(pct_noaa_area.to_string())
print("\n[NOAA scope — CRainf 중앙값 이분]")
print(pct_noaa_crainf.to_string())

# ── Figure (3-panel) ────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))

plot_stacked_bar(axes[0], pct_q99_area,
                 "Area Quartile × Obs Class\n(Q99 scope, 85 basins)")
plot_stacked_bar(axes[1], pct_noaa_area,
                 "Area Quartile × Obs Class\n(NOAA scope)")
plot_stacked_bar(axes[2], pct_noaa_crainf,
                 "CRainf Fraction × Obs Class\n(NOAA scope, median split)")

handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels,
           loc="lower center", ncol=5,
           bbox_to_anchor=(0.5, -0.06),
           title="Obs Class (band position)",
           frameon=False, fontsize=9)

plt.tight_layout(rect=[0, 0.08, 1, 1])
fig_path = OUT_FIGURES / "rq0_stratified_obsclass.png"
plt.savefig(fig_path, dpi=150, bbox_inches="tight")
plt.close()
print(f"\nFigure → {fig_path}")
