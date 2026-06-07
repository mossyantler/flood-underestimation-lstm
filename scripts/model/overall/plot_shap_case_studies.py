# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pandas",
#   "numpy",
#   "matplotlib",
# ]
# ///
"""
SHAP case-study figures for q99 direction analysis.

Generates:
  1. Waterfall plots — 3 representative events (max underestimation,
     max overestimation, best match)
  2. Dependence scatter — area, slope, soil_depth vs mean signed SHAP
     (all q99 events, seed 111, colored by secondary feature)

Output → output/model_analysis/shap/direction/figures/
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO = Path(__file__).resolve().parents[3]
SHAP_DIR = REPO / "output" / "model_analysis" / "shap"
MATRIX_CSV = SHAP_DIR / "direction" / "tables" / "direction_event_feature_matrix.csv"
OUT_DIR = SHAP_DIR / "direction" / "figures"

SEED_CSVS = {
    111: SHAP_DIR / "q99" / "tables" / "quantile_lstm_direct_shap_event_feature_importance_seed111.csv",
    222: SHAP_DIR / "q99" / "tables" / "quantile_lstm_direct_shap_event_feature_importance_seed222.csv",
    444: SHAP_DIR / "q99" / "tables" / "quantile_lstm_direct_shap_event_feature_importance_seed444.csv",
}

# Representative events per seed (top by q99_peak_rel_error)
CASES_BY_SEED = {
    111: [
        {"event_id": "12", "basin": 1446776, "label": "Max Underestimation", "slug": "max_underestimation", "description": "obs=109.9 m³/s, q99=2.8 m³/s (−97.5%)"},
        {"event_id": "2",  "basin": 1443900, "label": "Max Overestimation",  "slug": "max_overestimation",  "description": "obs=3.7 m³/s, q99=145.8 m³/s (+3801%)"},
        {"event_id": "5",  "basin": 1480870, "label": "Best Match",          "slug": "best_match",          "description": "obs=35.0 m³/s, q99=35.1 m³/s (+0.06%)"},
    ],
    222: [
        {"event_id": "7",  "basin": 1470779, "label": "Max Underestimation", "slug": "max_underestimation", "description": "obs=19.8 m³/s, q99=0.6 m³/s (−97.2%)"},
        {"event_id": "7",  "basin": 1443900, "label": "Max Overestimation",  "slug": "max_overestimation",  "description": "obs=2.9 m³/s, q99=157.4 m³/s (+5245%)"},
        {"event_id": "3",  "basin": 1452000, "label": "Best Match",          "slug": "best_match",          "description": "obs=86.6 m³/s, q99=86.5 m³/s (−0.13%)"},
    ],
    444: [
        {"event_id": "6",  "basin": 1433500, "label": "Max Underestimation", "slug": "max_underestimation", "description": "obs=57.5 m³/s, q99=0.9 m³/s (−98.4%)"},
        {"event_id": "7",  "basin": 1443900, "label": "Max Overestimation",  "slug": "max_overestimation",  "description": "obs=2.9 m³/s, q99=177.6 m³/s (+5930%)"},
        {"event_id": "7",  "basin": 1451650, "label": "Best Match",          "slug": "best_match",          "description": "obs=26.1 m³/s, q99=26.1 m³/s (−0.04%)"},
    ],
}

# Keep CASES for dependence/beeswarm (seed 111 only)
CASES = CASES_BY_SEED[111]

DEPENDENCE_FEATURES = [
    ("area",       "slope"),
    ("slope",      "area"),
    ("soil_depth", "permeability"),
]

POS_COLOR = "#d62728"
NEG_COLOR = "#1f77b4"
BASE_COLOR = "#555555"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _feature_label(f: str) -> str:
    return {
        "area": "Drainage area",
        "slope": "Channel slope",
        "soil_depth": "Soil depth",
        "aridity": "Aridity index",
        "baseflow_index": "Baseflow index",
        "forest_fraction": "Forest fraction",
        "permeability": "Permeability",
        "snow_fraction": "Snow fraction",
    }.get(f, f)


def _load_matrix_event(mat: pd.DataFrame, seed: int, event_id: str, basin: int) -> pd.DataFrame:
    return mat[
        (mat["scope"] == "q99")
        & (mat["seed"] == seed)
        & (mat["quantile"] == "q99")
        & (mat["event_id"].astype(str) == str(event_id))
        & (mat["basin"] == basin)
    ].copy()


# ---------------------------------------------------------------------------
# 1. Waterfall plots
# ---------------------------------------------------------------------------
def plot_waterfall(
    mat: pd.DataFrame,
    q99_meta: pd.DataFrame,
    base_value: float,
    case: dict,
    out: Path,
    seed: int = 111,
) -> None:
    eid, basin = case["event_id"], case["basin"]
    ev = _load_matrix_event(mat, seed, eid, basin)

    if ev.empty:
        print(f"  [WARN] event {eid}/{basin} not found in matrix; skipping waterfall.")
        return

    # Separate static and dynamic
    static = ev[ev["feature_group"] == "static_attribute"].copy()
    dynamic = ev[ev["feature_group"] == "dynamic_forcing"].copy()
    dynamic_sum = dynamic["mean_signed_shap"].sum()

    # Sort static by absolute SHAP descending
    static = static.sort_values("mean_abs_shap", ascending=False)

    # Build waterfall rows: static features + one aggregated dynamic row
    features = list(static["feature"].values) + ["Dynamic (sum)"]
    shap_vals = list(static["mean_signed_shap"].values) + [dynamic_sum]
    n = len(features)

    # Running cumulative from base
    lefts = []
    running = base_value
    for v in shap_vals:
        if v >= 0:
            lefts.append(running)
        else:
            lefts.append(running + v)
        running += v
    pred_val = running

    colors = [POS_COLOR if v >= 0 else NEG_COLOR for v in shap_vals]

    fig, ax = plt.subplots(figsize=(7, 0.45 * n + 2.6))
    y = np.arange(n)
    ax.barh(y, np.abs(shap_vals), left=lefts, color=colors, alpha=0.88,
            edgecolor="white", linewidth=0.5)

    # Base value line
    ax.axvline(base_value, color=BASE_COLOR, linewidth=1.2, linestyle="--", label=f"Base ({base_value:+.3f})")
    # Prediction line
    ax.axvline(pred_val, color="#2ca02c", linewidth=1.2, linestyle=":",
               label=f"Prediction ({pred_val:+.3f})")

    ax.set_yticks(y)
    ax.set_yticklabels([_feature_label(f) if f != "Dynamic (sum)" else "Dynamic (sum)" for f in features],
                       fontsize=9)
    ax.set_xlabel("SHAP contribution (normalized)", fontsize=9)
    ax.set_title(
        f"SHAP Waterfall — {case['label']}\n"
        f"Basin {basin}, Event {eid}   {case['description']}",
        fontsize=10,
    )

    # Legend
    pos_patch = mpatches.Patch(color=POS_COLOR, label="Raises q99")
    neg_patch = mpatches.Patch(color=NEG_COLOR, label="Lowers q99")
    base_line = plt.Line2D([0], [0], color=BASE_COLOR, linestyle="--", label=f"Base ({base_value:+.3f})")
    pred_line = plt.Line2D([0], [0], color="#2ca02c", linestyle=":", label=f"Prediction ({pred_val:+.3f})")
    ax.legend(handles=[pos_patch, neg_patch, base_line, pred_line], fontsize=7.5,
              loc="lower right", framealpha=0.9)
    ax.grid(axis="x", alpha=0.3, linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out, dpi=220, facecolor="white")
    plt.close(fig)
    print(f"  Saved {out.name}")


# ---------------------------------------------------------------------------
# 2. Dependence scatter plots
# ---------------------------------------------------------------------------
def plot_dependence(
    mat: pd.DataFrame,
    feat: str,
    color_feat: str,
    cases_meta: pd.DataFrame,
    out: Path,
) -> None:
    # All q99 events, all seeds, q99 quantile, static features only
    static = mat[
        (mat["scope"] == "q99")
        & (mat["quantile"] == "q99")
        & (mat["feature_group"] == "static_attribute")
    ].copy()

    feat_df = static[static["feature"] == feat][["seed", "basin", "event_id", "feature_value", "mean_signed_shap"]].copy()
    color_df = static[static["feature"] == color_feat][["seed", "basin", "event_id", "feature_value"]].rename(
        columns={"feature_value": "color_value"}
    )
    merged = feat_df.merge(color_df, on=["seed", "basin", "event_id"], how="left")

    if merged.empty:
        print(f"  [WARN] no data for {feat}; skipping dependence.")
        return

    # One point per (basin, seed) — static values are constant per basin
    # use seed 111 only to avoid triple-density overplot
    df = merged[merged["seed"] == 111].dropna(subset=["feature_value", "color_value"])

    fig, ax = plt.subplots(figsize=(6, 4.5))
    sc = ax.scatter(
        df["feature_value"], df["mean_signed_shap"],
        c=df["color_value"], cmap="RdYlBu_r",
        alpha=0.65, s=35, linewidths=0.3, edgecolors="white",
    )
    plt.colorbar(sc, ax=ax, label=_feature_label(color_feat), fraction=0.035, pad=0.02)
    ax.axhline(0, color="#333333", linewidth=0.8, linestyle="--")

    # Highlight representative cases
    for case in CASES:
        sub = df[df["basin"] == case["basin"]]
        if sub.empty:
            continue
        ax.scatter(
            sub["feature_value"], sub["mean_signed_shap"],
            s=90, marker="*", color="#ff7f0e", zorder=5,
            linewidths=0.5, edgecolors="#333333",
        )
        # label only best_match to avoid clutter
        if case["slug"] == "best_match" and not sub.empty:
            row = sub.iloc[0]
            ax.annotate(
                case["label"], (row["feature_value"], row["mean_signed_shap"]),
                xytext=(5, 5), textcoords="offset points", fontsize=7,
                color="#ff7f0e",
            )

    star = plt.Line2D([0], [0], marker="*", color="#ff7f0e", linestyle="none",
                      markersize=9, label="Representative events")
    ax.legend(handles=[star], fontsize=8, framealpha=0.9)

    ax.set_xlabel(_feature_label(feat), fontsize=9)
    ax.set_ylabel("Mean signed SHAP (q99 quantile)", fontsize=9)
    ax.set_title(f"SHAP Dependence — {_feature_label(feat)} (seed 111)", fontsize=10)
    ax.grid(alpha=0.25, linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out, dpi=220, facecolor="white")
    plt.close(fig)
    print(f"  Saved {out.name}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def plot_beeswarm(mat: pd.DataFrame, out: Path, *, scope: str = "q99", n_features: int = 10) -> None:
    """True SHAP beeswarm: one dot per (basin, event, seed), x=SHAP, y=feature, color=feature_value."""
    static = mat[
        (mat["scope"] == scope)
        & (mat["quantile"] == "q99")
        & (mat["feature_group"] == "static_attribute")
    ].copy()

    # Rank features by mean |SHAP|
    ranked = (
        static.groupby("feature")["mean_abs_shap"]
        .mean()
        .sort_values(ascending=False)
        .head(n_features)
    )
    features = ranked.index.tolist()
    static = static[static["feature"].isin(features)].copy()

    # Normalize feature_value per feature to [0, 1] for coloring
    def _norm(x: pd.Series) -> pd.Series:
        lo, hi = x.min(), x.max()
        return (x - lo) / (hi - lo + 1e-12)

    static["fv_norm"] = static.groupby("feature")["feature_value"].transform(_norm)

    # Assign y-position: feature rank + jitter to avoid overlap (beeswarm-style)
    feat_rank = {f: i for i, f in enumerate(reversed(features))}  # bottom = lowest importance
    rng = np.random.default_rng(42)

    rows = []
    for feat in features:
        sub = static[static["feature"] == feat].copy()
        # Bin SHAP values → stack dots vertically within each bin
        bins = np.linspace(sub["mean_signed_shap"].min() - 1e-6,
                           sub["mean_signed_shap"].max() + 1e-6, 40)
        sub["bin"] = np.digitize(sub["mean_signed_shap"], bins)
        jitter_scale = 0.30
        jitters = []
        for _, grp in sub.groupby("bin"):
            n = len(grp)
            if n == 1:
                jitters.extend([0.0])
            else:
                spread = np.linspace(-jitter_scale / 2, jitter_scale / 2, n)
                jitters.extend(spread.tolist())
        sub = sub.copy()
        sub["jitter"] = jitters
        sub["y"] = feat_rank[feat] + sub["jitter"]
        rows.append(sub)

    df = pd.concat(rows, ignore_index=True)

    fig, ax = plt.subplots(figsize=(8, 0.5 * n_features + 2.5))
    sc = ax.scatter(
        df["mean_signed_shap"], df["y"],
        c=df["fv_norm"], cmap="RdBu_r",
        s=12, alpha=0.55, linewidths=0,
    )
    cbar = plt.colorbar(sc, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("Feature value\n(low → high)", fontsize=8)
    cbar.set_ticks([0, 1])
    cbar.set_ticklabels(["Low", "High"], fontsize=8)

    ax.axvline(0, color="#333333", linewidth=0.8, linestyle="--")
    ax.set_yticks(list(feat_rank.values()))
    ax.set_yticklabels([_feature_label(f) for f in reversed(features)], fontsize=9)
    ax.set_xlabel("Mean signed SHAP value (q99 quantile)", fontsize=9)
    scope_label = "q99 events" if scope == "q99" else "Full test period"
    ax.set_title(f"SHAP Beeswarm — {scope_label}", fontsize=10)
    ax.grid(axis="x", alpha=0.25, linewidth=0.5)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out, dpi=220, facecolor="white")
    plt.close(fig)
    print(f"  Saved {out.name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading data...")
    mat = pd.read_csv(MATRIX_CSV, low_memory=False)
    mat["event_id"] = mat["event_id"].astype(str)

    # Per-seed base values and q99 meta
    seed_q99_ev: dict[int, pd.DataFrame] = {}
    seed_base: dict[int, float] = {}
    for seed, csv_path in SEED_CSVS.items():
        df_all = pd.read_csv(csv_path, low_memory=False)
        df_ev = df_all[df_all["quantile"] == "q99"].drop_duplicates(["event_id", "basin"])
        seed_q99_ev[seed] = df_ev
        seed_base[seed] = float(df_ev["quantile_prediction_normalized"].mean())
        print(f"  Base value (seed {seed}): {seed_base[seed]:.4f}")

    # 1. Waterfall plots — 9 total (3 seeds × 3 cases)
    print("\n[1/3] Waterfall plots")
    for seed, cases in CASES_BY_SEED.items():
        for case in cases:
            fname = f"waterfall_seed{seed}_{case['slug']}.png"
            plot_waterfall(mat, seed_q99_ev[seed], seed_base[seed], case, out_dir / fname, seed=seed)

    # 2. Beeswarm plots
    print("\n[2/3] Beeswarm plots")
    for scope in ["q99", "test_split"]:
        fname = f"beeswarm_true_{scope}.png"
        plot_beeswarm(mat, out_dir / fname, scope=scope)

    # 3. Dependence scatter plots
    print("\n[3/3] Dependence scatter plots")
    for feat, color_feat in DEPENDENCE_FEATURES:
        fname = f"dependence_{feat}.png"
        plot_dependence(mat, feat, color_feat, seed_q99_ev[111], out_dir / fname)

    print("\nDone.")


if __name__ == "__main__":
    main()
