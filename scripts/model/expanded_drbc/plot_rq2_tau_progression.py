# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas", "matplotlib", "numpy"]
# ///
"""
RQ-2 τ 진행 figure: Model 2 내부 비교 (q50→q90→q95→q99).
Model 1은 수평 점선 reference (RQ-1 결과, 직접 비교 아님).

출력:
  output/model_analysis/primary/metrics/figures/rq2_tau_progression.png
  output/model_analysis/primary/metrics/tables/rq2_miss_rate_summary.csv
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path(__file__).parents[3]
TABLES = ROOT / "output/model_analysis/primary/metrics/tables"
FIGURES = ROOT / "output/model_analysis/primary/metrics/figures"

ALPHA_Q99  = TABLES / "rq2_alpha_event_peak_deficit_q99_summary.csv"
ALPHA_NOAA = TABLES / "rq2_alpha_event_peak_deficit_noaa_summary.csv"
DELTA_Q99  = TABLES / "rq2_delta_threshold_recall_summary.csv"

TAU_ORDER = ["q50", "q90", "q95", "q99"]
TAU_LABELS = ["q50", "q90", "q95", "q99"]

# ── 데이터 로드 ──────────────────────────────────────────────────────────────
def load_summary(path):
    return pd.read_csv(path, comment="#").set_index("tau")

alpha_q99  = load_summary(ALPHA_Q99)
alpha_noaa = load_summary(ALPHA_NOAA)
delta_q99  = load_summary(DELTA_Q99)

# miss rate = 1 - delta recall
miss_q99 = delta_q99.copy()
miss_q99["miss_rate"] = (1 - miss_q99["basin_median_recall"]) * 100
miss_q99["miss_iqr_low"]  = (1 - miss_q99["basin_iqr_high"]) * 100
miss_q99["miss_iqr_high"] = (1 - miss_q99["basin_iqr_low"]) * 100

# ── miss rate 테이블 저장 ────────────────────────────────────────────────────
miss_table = miss_q99.loc[TAU_ORDER + ["model1"], ["miss_rate", "miss_iqr_low", "miss_iqr_high"]].copy()
miss_table.index.name = "tau"
miss_table.columns = ["miss_rate_pct", "miss_iqr_low_pct", "miss_iqr_high_pct"]
miss_table.to_csv(TABLES / "rq2_miss_rate_summary.csv")
print("=== RQ-2 miss rate (1 − δ recall, Q99 scope) ===")
print(miss_table.to_string(float_format="%.1f"))

# ── Figure ───────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=False)

BLUE   = "#2166ac"
ORANGE = "#d6604d"
REF_COLOR = "#888888"

def plot_tau_panel(ax, alpha_df, miss_df_or_none, scope_label, n_basins,
                   show_ylabel=True, show_miss=False):
    x = np.arange(len(TAU_ORDER))

    medians = alpha_df.loc[TAU_ORDER, "basin_median_of_event_median"].values
    iqr_lo  = alpha_df.loc[TAU_ORDER, "basin_iqr_low"].values
    iqr_hi  = alpha_df.loc[TAU_ORDER, "basin_iqr_high"].values

    # Model 1 reference line
    m1_alpha = alpha_df.loc["model1", "basin_median_of_event_median"]
    ax.axhline(m1_alpha, color=REF_COLOR, linewidth=1.2, linestyle="--",
               label=f"Model 1 ref. (α={m1_alpha:.3f})")

    # τ-progression
    ax.fill_between(x, iqr_lo, iqr_hi, alpha=0.18, color=BLUE)
    ax.plot(x, medians, "o-", color=BLUE, linewidth=2, markersize=7,
            label="Model 2 (α, cross-basin median)")

    for xi, m in zip(x, medians):
        ax.text(xi, m + 0.025, f"{m:.3f}", ha="center", va="bottom",
                fontsize=8.5, color=BLUE)

    ax.set_xticks(x)
    ax.set_xticklabels(TAU_LABELS, fontsize=10)
    ax.set_xlabel("τ (quantile level)", fontsize=10)
    if show_ylabel:
        ax.set_ylabel("α  (event peak under-deficit, median)", fontsize=10)
    ax.set_ylim(-0.05, 1.05)
    ax.set_title(f"α progression — {scope_label}  (n={n_basins})", fontsize=11)
    ax.legend(fontsize=8.5, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", linewidth=0.4, color="#ddd")


plot_tau_panel(axes[0], alpha_q99,  miss_q99, "Q99 scope", n_basins=82, show_ylabel=True)
plot_tau_panel(axes[1], alpha_noaa, None,     "NOAA scope", n_basins=21, show_ylabel=False)

plt.tight_layout()
out_fig = FIGURES / "rq2_tau_progression.png"
plt.savefig(out_fig, dpi=150, bbox_inches="tight")
plt.close()
print(f"\nFigure → {out_fig}")

# ── 콘솔: miss rate + alpha 병기 ─────────────────────────────────────────────
print("\n=== RQ-2 τ 진행 요약 (Q99 scope, 82 basins) ===")
summary_rows = []
for tau in TAU_ORDER:
    alpha = alpha_q99.loc[tau, "basin_median_of_event_median"]
    miss  = miss_q99.loc[tau, "miss_rate"]
    summary_rows.append({"τ": tau, "alpha (median)": f"{alpha:.3f}",
                          "miss rate (%)": f"{miss:.1f}"})
m1_alpha = alpha_q99.loc["model1", "basin_median_of_event_median"]
m1_miss  = miss_q99.loc["model1", "miss_rate"]
summary_rows.insert(0, {"τ": "model1 (ref)", "alpha (median)": f"{m1_alpha:.3f}",
                         "miss rate (%)": f"{m1_miss:.1f}"})
print(pd.DataFrame(summary_rows).to_string(index=False))
