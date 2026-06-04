# /// script
# dependencies = ["pandas", "numpy", "matplotlib"]
# ///
"""Combined signal sweep figure: Branch A (band/gap/spread/attrs) + Branch B (forcing) vs obs_class."""
import pandas as pd, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
TD = BASE / "output/model_analysis/band_signal/signal_sweep/tables"
OUTDIR = BASE / "output/model_analysis/band_signal/signal_sweep/figures"
OUTDIR.mkdir(parents=True, exist_ok=True)

a = pd.read_csv(TD / "branchA_spearman.csv")
b = pd.read_csv(TD / "branchB_spearman.csv")
df = pd.concat([a, b], ignore_index=True)

# category: forcing(I from B) gets its own color "F"
b_metrics = set(b["metric"])
df["cat2"] = df.apply(lambda r: "F" if (r["metric"] in b_metrics and r["category"] == "I") else r["category"], axis=1)

COL = {"C": "#f59e0b", "I": "#16a34a", "F": "#0ea5e9", "L": "#dc2626"}
NAME = {
    "I": "I: independent basin attribute (leakage-free)",
    "F": "F: input forcing rain/CAPE (leakage-free)",
    "C": "C: band-coupled (partly circular)",
    "L": "L: obs-leakage (baseline)",
}
SCOPES = [("q99", "Q99 exceedance events"), ("noaa", "NOAA confirmed floods")]

fig, axes = plt.subplots(1, 2, figsize=(16, 11))
fig.patch.set_facecolor("#f8fafc")
for ax, (scope, title) in zip(axes, SCOPES):
    sub = df[df["scope"] == scope].copy()
    sub["abs_r"] = sub["spearman_r"].abs()
    sub = sub.sort_values("abs_r", ascending=True)
    nmax = int(sub["n"].max())
    colors = [COL[c] for c in sub["cat2"]]
    y = np.arange(len(sub))
    ax.barh(y, sub["spearman_r"], color=colors, alpha=0.88, height=0.7, edgecolor="white", linewidth=0.5)
    ax.set_yticks(y)
    ax.set_yticklabels(sub["metric"], fontsize=8)
    ax.set_xlim(-0.5, 0.58)
    ax.axvline(0, color="#1e293b", linewidth=0.8)
    for thr in (0.3, -0.3):
        ax.axvline(thr, color="#2563eb", linewidth=1.1, linestyle="--", alpha=0.7)
    ax.set_xlabel("Spearman r  vs  obs_class (0=below_q50 ... 4=above_q99)", fontsize=9)
    ax.set_title(f"{title}  (n up to {nmax})", fontsize=11, fontweight="bold")
    ax.set_facecolor("#ffffff")
    ax.grid(axis="x", alpha=0.3, linewidth=0.5)
    ax.spines[["top", "right"]].set_visible(False)
    for yi, v, p in zip(y, sub["spearman_r"], sub["p_value"]):
        off = 0.01 if v >= 0 else -0.01
        ha = "left" if v >= 0 else "right"
        star = "*" if p < 0.05 else ""
        ax.text(v + off, yi, f"{v:+.2f}{star}", va="center", ha=ha, fontsize=6.8,
                fontweight="bold", color="#334155")

handles = [mpatches.Patch(color=COL[c], label=NAME[c]) for c in ["I", "F", "C", "L"]]
handles.append(plt.Line2D([0], [0], color="#2563eb", ls="--", label="threshold |r|=0.3"))
fig.legend(handles=handles, loc="lower center", ncol=3, fontsize=9, bbox_to_anchor=(0.5, -0.015), frameon=False)
fig.suptitle("Signal sweep (Branch A + B):  every candidate feature vs obs band-position  -  by leakage category",
             fontsize=13, fontweight="bold", y=1.0)
plt.tight_layout(rect=[0, 0.04, 1, 0.99])
out = OUTDIR / "signal_sweep_combined.png"
plt.savefig(out, dpi=145, bbox_inches="tight", facecolor="#f8fafc")
plt.close()
print("saved:", out)
