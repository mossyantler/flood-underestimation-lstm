# /// script
# dependencies = ["pandas", "numpy", "matplotlib"]
# ///
"""3-scope 비교: Q99 / NOAA(극단) vs ALL-RAIN(전 범위). 핵심 신호의 범위제한 효과 시각화."""
import pandas as pd, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
TD = BASE / "output/model_analysis/band_signal/signal_sweep/tables"
OUTDIR = BASE / "output/model_analysis/band_signal/signal_sweep/figures"

a = pd.read_csv(TD / "branchA_spearman.csv")
b = pd.read_csv(TD / "branchB_spearman.csv")
b2 = pd.read_csv(TD / "branchB2_spearman.csv")
df = pd.concat([a, b, b2], ignore_index=True)

# 공통 신호 라벨 매핑 (scope별 metric명 차이 흡수)
CANON = {
    "area": {"q99": "area", "noaa": "area", "allrain": "area"},
    "rel_width": {"q99": "rel_width", "noaa": "rel_width", "allrain": "rel_width"},
    "rain_sum": {"q99": "rain_sum_24h", "noaa": "rain_sum_24h", "allrain": "rain_sum_event"},
    "rain_max_1h": {"q99": "rain_max_1h_72h", "noaa": "rain_max_1h_72h", "allrain": "rain_max_1h"},
    "nws_class": {"q99": "nws_class", "noaa": "nws_class", "allrain": "nws_class"},
    "cape_max": {"q99": "cape_max_24h", "noaa": "cape_max_24h", "allrain": "cape_max"},
    "crainf_frac": {"q99": "crainf_frac_mean_24h", "noaa": "crainf_frac_mean_24h", "allrain": "crainf_frac_mean"},
    "baseflow_index": {"q99": "baseflow_index", "noaa": "baseflow_index", "allrain": "baseflow_index"},
}
ORDER = ["area", "baseflow_index", "rain_sum", "rain_max_1h", "nws_class", "cape_max", "crainf_frac", "rel_width"]
SCOPES = [("q99", "Q99 (extreme)", "#dc2626"), ("noaa", "NOAA (extreme)", "#ea580c"), ("allrain", "ALL-RAIN (full range)", "#16a34a")]


def getr(label, scope):
    m = CANON[label][scope]
    row = df[(df["scope"] == scope) & (df["metric"] == m)]
    return row["spearman_r"].iloc[0] if len(row) else np.nan


fig, ax = plt.subplots(figsize=(14, 7))
fig.patch.set_facecolor("#f8fafc")
ax.set_facecolor("#ffffff")
x = np.arange(len(ORDER))
w = 0.26
for i, (sc, name, col) in enumerate(SCOPES):
    vals = [getr(lbl, sc) for lbl in ORDER]
    ax.bar(x + (i - 1) * w, vals, w, label=name, color=col, alpha=0.88, edgecolor="white", linewidth=0.5)
    for xi, v in zip(x + (i - 1) * w, vals):
        if not np.isnan(v):
            ax.text(xi, v + (0.012 if v >= 0 else -0.012), f"{v:+.2f}", ha="center",
                    va="bottom" if v >= 0 else "top", fontsize=6.8, fontweight="bold", color="#334155")
ax.axhline(0, color="#1e293b", linewidth=0.9)
for thr in (0.3, -0.3):
    ax.axhline(thr, color="#2563eb", linewidth=1.0, linestyle="--", alpha=0.6)
ax.set_xticks(x)
ax.set_xticklabels(ORDER, fontsize=9.5, rotation=20, ha="right")
ax.set_ylabel("Spearman r  vs  obs_class", fontsize=10)
ax.set_ylim(-0.45, 0.55)
ax.set_title("Range-restriction effect:  signal vs obs band-position across event scopes\n"
             "extreme-only (Q99/NOAA) vs full rain-event range  -  area collapses, rainfall flips positive",
             fontsize=12, fontweight="bold")
ax.grid(axis="y", alpha=0.3)
ax.spines[["top", "right"]].set_visible(False)
ax.legend(fontsize=10, loc="upper right", framealpha=0.9)
plt.tight_layout()
out = OUTDIR / "signal_sweep_3scope.png"
plt.savefig(out, dpi=150, bbox_inches="tight", facecolor="#f8fafc")
plt.close()
print("saved:", out)
