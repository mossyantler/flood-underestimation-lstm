# /// script
# dependencies = ["pandas", "numpy", "matplotlib"]
# ///
"""seed_spread(앙상블 분산) 3-scope: 절대형 vs 상대형 의 obs_class 상관. 인식적 불확실성 가설 검정 시각화."""
import pandas as pd, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
TD = BASE / "output/model_analysis/band_signal/signal_sweep/tables"
OUTDIR = BASE / "output/model_analysis/band_signal/signal_sweep/figures"

a = pd.read_csv(TD / "branchA_spearman.csv")            # q99, noaa
b2 = pd.read_csv(TD / "branchB2_seed_spread_spearman.csv")  # allrain
df = pd.concat([a[a["metric"].str.startswith("seed_spread")], b2], ignore_index=True)

METRICS = [
    ("seed_spread_q50", "seed spread q50\n(absolute)"),
    ("seed_spread_q99", "seed spread q99\n(absolute)"),
    ("seed_spread_q50_rel", "seed spread q50\n(relative, size-removed)"),
]
SCOPES = [("q99", "Q99 (extreme)", "#dc2626"), ("noaa", "NOAA (extreme)", "#ea580c"),
          ("allrain", "ALL-RAIN (full range)", "#16a34a")]


def getr(metric, scope):
    row = df[(df["scope"] == scope) & (df["metric"] == metric)]
    return row["spearman_r"].iloc[0] if len(row) else np.nan


fig, ax = plt.subplots(figsize=(11, 6.5))
fig.patch.set_facecolor("#f8fafc")
ax.set_facecolor("#ffffff")
x = np.arange(len(METRICS))
w = 0.26
for i, (sc, name, col) in enumerate(SCOPES):
    vals = [getr(m, sc) for m, _ in METRICS]
    ax.bar(x + (i - 1) * w, vals, w, label=name, color=col, alpha=0.88, edgecolor="white", linewidth=0.5)
    for xi, v in zip(x + (i - 1) * w, vals):
        if not np.isnan(v):
            ax.text(xi, v - 0.006, f"{v:+.3f}", ha="center", va="top",
                    fontsize=8, fontweight="bold", color="#334155")
ax.axhline(0, color="#1e293b", linewidth=0.9)
ax.axhline(0.3, color="#2563eb", linewidth=1.0, linestyle="--", alpha=0.5)
ax.axhline(-0.3, color="#2563eb", linewidth=1.0, linestyle="--", alpha=0.5)
ax.set_xticks(x)
ax.set_xticklabels([lbl for _, lbl in METRICS], fontsize=9.5)
ax.set_ylabel("Spearman r  vs  obs_class", fontsize=10)
ax.set_ylim(-0.22, 0.12)
ax.set_title("Ensemble seed-spread vs obs band-position  -  epistemic-uncertainty hypothesis fails\n"
             "absolute spread is weakly NEGATIVE (magnitude artifact); relative spread collapses to ~0",
             fontsize=11.5, fontweight="bold")
ax.grid(axis="y", alpha=0.3)
ax.spines[["top", "right"]].set_visible(False)
ax.legend(fontsize=9.5, loc="lower left", framealpha=0.9)
plt.tight_layout()
out = OUTDIR / "seed_spread_3scope.png"
plt.savefig(out, dpi=150, bbox_inches="tight", facecolor="#f8fafc")
plt.close()
print("saved:", out)
