#!/usr/bin/env python3
"""Basin-level time-series coverage Gantt chart — coloured by prepared_split_status"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd
import os

MANIFEST = "/Users/jang-minyeop/Project/CAMELS/data/CAMELSH_generic/drbc_holdout_broad/splits/split_manifest.csv"
OUTPUT   = "/Users/jang-minyeop/Project/CAMELS/output/basin_timeseries_coverage.png"
os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)

df = pd.read_csv(MANIFEST, dtype={"gauge_id": str})

# ── colour by prepared_split_status ─────────────────────────
C = {
    "train":      "#4C72B0",   # blue
    "validation": "#DD8452",   # orange
    "test":       "#55A868",   # green
    "except":     "#C44E52",   # red  ← correctly excluded
}
BG  = "#F8F9FA"
GRD = "#CED4DA"
TXT = "#212529"
MUT = "#6C757D"

# ── sort: status order, then by obs start year ───────────────
STATUS_ORDER = {"train": 0, "validation": 1, "test": 2, "except": 3}
df["_ord"] = df["prepared_split_status"].map(STATUS_ORDER)
df = df.sort_values(["_ord", "first_obs_year_usable", "last_obs_year_usable"]).reset_index(drop=True)

N   = len(df)
BAR = 0.72

# ── figure ───────────────────────────────────────────────────
fig_h = max(14, N * 0.115)
fig, ax = plt.subplots(figsize=(18, fig_h), facecolor=BG)
ax.set_facecolor(BG)

for i, row in df.iterrows():
    status = row["prepared_split_status"]
    color  = C.get(status, "#999")
    start  = row["first_obs_year_usable"]
    end    = row["last_obs_year_usable"]

    # Full observation span bar
    ax.barh(i, end - start, left=start, height=BAR,
            color=color, alpha=0.85, zorder=3)

    # Split window overlay (white stripe = actual used period)
    ws = pd.to_datetime(row["split_start_date"]).year
    we = pd.to_datetime(row["split_end_date"]).year
    ax.barh(i, we - ws, left=ws, height=BAR * 0.42,
            color="white", alpha=0.38, zorder=4)

    # actual_valid_target_count annotation for "except" basins
    if status == "except":
        ax.text(end + 0.15, i,
                f"n={int(row['actual_valid_target_count'])}",
                ha="left", va="center", fontsize=3.8,
                color=C["except"], zorder=5)

# ── group dividers & labels ───────────────────────────────────
prev = None
for i, row in df.iterrows():
    sp = row["prepared_split_status"]
    if sp != prev:
        if prev is not None:
            ax.axhline(i - 0.5, color=GRD, lw=0.9, linestyle="--", zorder=2)
        group_rows = df[df["prepared_split_status"] == sp]
        gstart = group_rows.index.min()
        gend   = group_rows.index.max()
        ax.text(2025.5, (gstart + gend) / 2,
                f"{sp.upper()}\n(n={len(group_rows)})",
                ha="left", va="center", fontsize=8.5,
                color=C.get(sp, "#999"), fontweight="bold")
        prev = sp

# ── background period shading ─────────────────────────────────
ax.axvspan(2000, 2011, alpha=0.05, color=C["train"],      zorder=0)
ax.axvspan(2011, 2014, alpha=0.05, color=C["validation"], zorder=0)
ax.axvspan(2014, 2017, alpha=0.05, color=C["test"],       zorder=0)

# ── vertical year grid ────────────────────────────────────────
for x in range(1986, 2026, 2):
    ax.axvline(x, color=GRD, lw=0.4, zorder=1)

# ── axes ─────────────────────────────────────────────────────
ax.set_xlim(1985, 2028)
ax.set_ylim(-0.8, N - 0.2)
ax.set_yticks(range(N))
ax.set_yticklabels(df["gauge_id"].tolist(), fontsize=4.0, color=TXT)
ax.tick_params(axis="y", length=0, pad=2)
ax.set_xticks(range(1986, 2026, 2))
ax.set_xticklabels(range(1986, 2026, 2), fontsize=8.5, color=MUT)
ax.tick_params(axis="x", which="both", color=GRD)
for sp in ax.spines.values():
    sp.set_edgecolor(GRD)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

# ── title & labels ────────────────────────────────────────────
split_n = df["prepared_split_status"].value_counts()
ax.set_title(
    f"Basin Observation Coverage by Prepared Split Status\n"
    f"train={split_n.get('train',0)}  |  validation={split_n.get('validation',0)}  |  "
    f"test(DRBC)={split_n.get('test',0)}  |  excluded={split_n.get('except',0)}",
    fontsize=13, fontweight="bold", color=TXT, pad=12
)
ax.set_xlabel("Year  (bar = first_obs_year ~ last_obs_year,  white stripe = split window)", fontsize=9.5, color=MUT)
ax.set_ylabel("Basin ID (gauge_id)", fontsize=10, color=MUT)

patches = [
    mpatches.Patch(facecolor=C["train"],      label="Train  (non-DRBC, 2000-2010)"),
    mpatches.Patch(facecolor=C["validation"], label="Validation  (non-DRBC, 2011-2013)"),
    mpatches.Patch(facecolor=C["test"],       label="Test — DRBC holdout  (2014-2016)"),
    mpatches.Patch(facecolor=C["except"],     label="Excluded  (< 720 valid targets in split window)"),
]
ax.legend(handles=patches, loc="upper left", fontsize=9,
          frameon=True, fancybox=True, edgecolor=GRD, facecolor="white")

plt.tight_layout()
plt.savefig(OUTPUT, dpi=140, bbox_inches="tight", facecolor=BG)
print(f"Saved -> {OUTPUT}  ({N} basins)")
