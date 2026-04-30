#!/usr/bin/env python3
"""Timeseries split visualization - train/validation/test periods and basin pools"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "output/basin/timeseries/timeseries_split_overview.png"
os.makedirs(OUTPUT_PATH.parent, exist_ok=True)

C_TRAIN = "#4C72B0"
C_VAL   = "#DD8452"
C_TEST  = "#55A868"
C_BG    = "#F8F9FA"
C_GRID  = "#CED4DA"
C_TEXT  = "#212529"
C_WARM  = "#6C757D"
C_WHITE = "#FFFFFF"

fig = plt.figure(figsize=(17, 9.5), facecolor=C_BG)
fig.patch.set_facecolor(C_BG)

# ─────────────────────────────────────────────
# TITLE
# ─────────────────────────────────────────────
fig.text(0.5, 0.965, "CAMELSH Hourly — Train / Validation / Test Split",
         ha="center", va="top", fontsize=21, fontweight="bold", color=C_TEXT)
fig.text(0.5, 0.930, "DRBC Regional Holdout  |  Multi-Basin LSTM  (Model 1 & 2)",
         ha="center", va="top", fontsize=13, color=C_WARM, style="italic")

# ─────────────────────────────────────────────
# TIMELINE BAR (axes)
# ─────────────────────────────────────────────
ax = fig.add_axes([0.07, 0.60, 0.87, 0.29])
ax.set_facecolor(C_BG)
ax.set_xlim(1991, 2026)
ax.set_ylim(0.4, 3.5)
ax.axis("off")

h = 0.60
y_non  = 2.70
y_drbc = 1.55

# Dashed available-data lines
for y in [y_non, y_drbc]:
    ax.plot([1991, 2025], [y, y], lw=2.0, color=C_WARM,
            alpha=0.45, linestyle="--", zorder=1)

# Non-DRBC bars
ax.barh(y_non, 11, left=2000, height=h, color=C_TRAIN, alpha=0.93, zorder=3, ec="white", lw=0.5)
ax.barh(y_non,  3, left=2011, height=h, color=C_VAL,   alpha=0.93, zorder=3, ec="white", lw=0.5)

# DRBC bar
ax.barh(y_drbc, 3, left=2014, height=h, color=C_TEST, alpha=0.93, zorder=3, ec="white", lw=0.5)

# Bar labels
for (left, width, y, label) in [
    (2000, 11, y_non,  "TRAIN\n2000 - 2010  (11 yr)"),
    (2011,  3, y_non,  "VALIDATION\n2011 - 2013  (3 yr)"),
    (2014,  3, y_drbc, "TEST (DRBC Holdout)\n2014 - 2016  (3 yr)"),
]:
    ax.text(left + width / 2, y, label,
            ha="center", va="center", fontsize=9.5,
            color="white", fontweight="bold", zorder=5)

# Pool labels (left side)
ax.text(1999.5, y_non,
        "Non-DRBC basins\n(~1,923 quality-pass)",
        ha="right", va="center", fontsize=9, color=C_TEXT, fontweight="bold")
ax.text(1999.5, y_drbc,
        "DRBC Delaware basins\n(~154 regional holdout)",
        ha="right", va="center", fontsize=9, color=C_TEXT, fontweight="bold")

# Vertical dividers
for x, ls in [(2000, ":"), (2011, ":"), (2014, ":")]:
    ax.axvline(x, color=C_GRID, lw=1.3, linestyle=ls, zorder=2)

# X-axis ticks
ax.set_xticks(range(1992, 2026, 4))
ax.set_xticklabels(range(1992, 2026, 4), fontsize=9, color=C_WARM)
ax.tick_params(bottom=True, left=False)
ax.spines["bottom"].set_visible(True)
ax.spines["bottom"].set_color(C_GRID)

# ─────────────────────────────────────────────
# DETAIL CARDS (3 columns)
# ─────────────────────────────────────────────
cards = [
    {
        "label":  "TRAIN",
        "color":  C_TRAIN,
        "period": "2000-01-01  -  2010-12-31",
        "basins": "Non-DRBC basins  (~1,923)\nquality-pass training pool",
        "notes":  "NSE loss  |  batch 256  |  30 epochs\nLearning rate decay schedule",
        "ts":     "Hourly streamflow 2000-2010\nAvg ~90k valid obs per basin",
    },
    {
        "label":  "VALIDATION",
        "color":  C_VAL,
        "period": "2011-01-01  -  2013-12-31",
        "basins": "Same non-DRBC basins as Train\n(same space, different time)",
        "notes":  "NSE metric  |  Best-epoch selection\nEarly stopping reference",
        "ts":     "Temporal holdout 2011-2013\n(unseen period for same basins)",
    },
    {
        "label":  "TEST  (DRBC Holdout)",
        "color":  C_TEST,
        "period": "2014-01-01  -  2016-12-31",
        "basins": "DRBC Delaware basins (~154)\nFully excluded from train/val",
        "notes":  "NSE / KGE / FHV / Peak-Timing\nPeak-MAPE  +  Pinball (Model 2)",
        "ts":     "Spatial + temporal holdout\nDRBC region 2014-2016",
    },
]

card_y0     = 0.08
card_height = 0.43
col_starts  = [0.055, 0.370, 0.685]
col_width   = 0.285

row_labels = ["Period", "Basin Pool", "Metrics / Purpose", "Time-series coverage"]
row_rel_y  = [0.82, 0.60, 0.37, 0.14]   # relative y inside card

for ci, card in enumerate(cards):
    x0 = col_starts[ci]

    # Card shadow (subtle)
    shadow = mpatches.FancyBboxPatch(
        (x0 + 0.003, card_y0 - 0.003), col_width, card_height,
        boxstyle="round,pad=0.012",
        facecolor="#D0D0D0", edgecolor="none",
        transform=fig.transFigure, zorder=3, clip_on=False
    )
    fig.add_artist(shadow)

    # Card body
    rect = mpatches.FancyBboxPatch(
        (x0, card_y0), col_width, card_height,
        boxstyle="round,pad=0.012",
        facecolor=C_WHITE, edgecolor=card["color"],
        linewidth=2.8, transform=fig.transFigure, zorder=4, clip_on=False
    )
    fig.add_artist(rect)

    # Colored top strip
    strip = mpatches.FancyBboxPatch(
        (x0, card_y0 + card_height - 0.055), col_width, 0.055,
        boxstyle="round,pad=0.005",
        facecolor=card["color"], edgecolor="none",
        transform=fig.transFigure, zorder=5, clip_on=False
    )
    fig.add_artist(strip)

    # Header label
    fig.text(
        x0 + col_width / 2,
        card_y0 + card_height - 0.027,
        card["label"],
        ha="center", va="center",
        fontsize=11.5, fontweight="bold", color=C_WHITE,
        transform=fig.transFigure, zorder=6
    )

    # Row content
    row_vals = [card["period"], card["basins"], card["notes"], card["ts"]]
    for rl, ry, rv in zip(row_labels, row_rel_y, row_vals):
        abs_y = card_y0 + ry * card_height
        fig.text(x0 + 0.013, abs_y,
                 rl + ":",
                 ha="left", va="bottom",
                 fontsize=7.5, color=C_WARM, style="italic",
                 transform=fig.transFigure, zorder=6)
        fig.text(x0 + 0.013, abs_y - 0.003,
                 rv,
                 ha="left", va="top",
                 fontsize=9, color=C_TEXT,
                 transform=fig.transFigure, zorder=6)

# ─────────────────────────────────────────────
# FOOTNOTE + LEGEND
# ─────────────────────────────────────────────
patches = [
    mpatches.Patch(facecolor=C_TRAIN, label="Train (non-DRBC, 2000-2010)"),
    mpatches.Patch(facecolor=C_VAL,   label="Validation (non-DRBC, 2011-2013)"),
    mpatches.Patch(facecolor=C_TEST,  label="Test — DRBC holdout (2014-2016)"),
]
fig.legend(handles=patches, loc="lower center", ncol=3,
           fontsize=10, frameon=True, fancybox=True,
           bbox_to_anchor=(0.5, 0.012),
           edgecolor=C_GRID, facecolor=C_WHITE)

fig.text(
    0.5, -0.003,
    "* Warm-up: seq_length=336 hr -> predict_last_n=24 hr loss only  |  "
    "DRBC basins: fully excluded from train & val (spatial holdout)",
    ha="center", va="top", fontsize=8, color=C_WARM,
    transform=fig.transFigure
)

plt.savefig(OUTPUT_PATH, dpi=160, bbox_inches="tight",
            facecolor=C_BG, edgecolor="none")
print(f"Saved -> {OUTPUT_PATH}")
