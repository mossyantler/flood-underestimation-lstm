# /// script
# dependencies = ["pandas", "numpy", "matplotlib"]
# ///
"""Branch A signal sweep figure: Spearman r of each feature vs obs_class, by category (C/I/L)."""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
TBL = BASE / "output/model_analysis/band_signal/signal_sweep/tables/static_spearman.csv"
OUTDIR = BASE / "output/model_analysis/band_signal/signal_sweep/figures"
OUTDIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(TBL)

# category colors / labels
CAT_COLOR = {"C": "#f59e0b", "I": "#16a34a", "L": "#dc2626"}
CAT_NAME = {
    "C": "C: band-coupled (partly circular)",
    "I": "I: independent (leakage-free)",
    "L": "L: obs-leakage (baseline)",
}

SCOPES = [("q99", "Q99 exceedance events"), ("noaa", "NOAA confirmed floods")]

fig, axes = plt.subplots(1, 2, figsize=(15, 9))
fig.patch.set_facecolor("#f8fafc")

for ax, (scope, title) in zip(axes, SCOPES):
    sub = df[df["scope"] == scope].copy()
    sub["abs_r"] = sub["spearman_r"].abs()
    sub = sub.sort_values("abs_r", ascending=True)  # bottom→top
    n = int(sub["n"].iloc[0])
    colors = [CAT_COLOR[c] for c in sub["category"]]
    ypos = np.arange(len(sub))
    ax.barh(ypos, sub["spearman_r"], color=colors, alpha=0.88, height=0.66,
            edgecolor="white", linewidth=0.6)
    ax.set_yticks(ypos)
    ax.set_yticklabels(sub["metric"], fontsize=8.5)
    ax.set_xlim(-0.5, 0.55)
    ax.axvline(0, color="#1e293b", linewidth=0.8)
    for thr in (0.3, -0.3):
        ax.axvline(thr, color="#2563eb", linewidth=1.2, linestyle="--", alpha=0.7)
    ax.set_xlabel("Spearman r  vs  obs_class (0=below_q50 ... 4=above_q99)", fontsize=9)
    ax.set_title(f"{title}\n(n={n})", fontsize=11, fontweight="bold")
    ax.set_facecolor("#ffffff")
    ax.grid(axis="x", alpha=0.3, linewidth=0.5)
    ax.spines[["top", "right"]].set_visible(False)
    # value labels
    for y, v, p in zip(ypos, sub["spearman_r"], sub["p_value"]):
        off = 0.012 if v >= 0 else -0.012
        ha = "left" if v >= 0 else "right"
        star = "*" if p < 0.05 else ""
        ax.text(v + off, y, f"{v:+.2f}{star}", va="center", ha=ha,
                fontsize=7.3, fontweight="bold", color="#334155")

handles = [mpatches.Patch(color=CAT_COLOR[c], label=CAT_NAME[c]) for c in ["I", "C", "L"]]
handles.append(plt.Line2D([0], [0], color="#2563eb", ls="--", label="threshold |r|=0.3"))
fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=9,
           bbox_to_anchor=(0.5, -0.02), frameon=False)
fig.suptitle("Branch A  -  Feature vs obs-band-position correlation  (band shape + model gap + seed spread + basin attributes)",
             fontsize=12.5, fontweight="bold", y=1.0)
plt.tight_layout(rect=[0, 0.03, 1, 0.99])
out = OUTDIR / "static_signal_sweep.png"
plt.savefig(out, dpi=145, bbox_inches="tight", facecolor="#f8fafc")
plt.close()
print("saved:", out)
