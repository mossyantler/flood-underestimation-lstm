#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "scipy>=1.13",
# ]
# ///
"""Identify basin characteristics driving Q99 prediction error.

Steps
-----
1. Spearman correlation: each attribute vs target metrics (per seed → stable filter)
2. Quartile comparison: Q1 (worst bias) vs Q4 (best bias) attribute medians

No surrogate model. Pure descriptive attribution.

Targets
-------
q99_med_rel_bias        : median relative bias at obs_q99_plus timesteps
med_rel_bias_delta      : model1_bias - q99_bias (positive = q99 improved)
q99_under_frac          : fraction of obs_q99_plus timesteps q99 underestimates

Outputs
-------
output/model_analysis/q99_analysis/tables/q99_driver_correlation.csv
output/model_analysis/q99_analysis/tables/q99_stable_drivers.csv
output/model_analysis/q99_analysis/tables/q99_quartile_comparison.csv
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = REPO_ROOT / "output/model_analysis/q99_analysis/tables"

TARGET_METRICS = ["q99_med_rel_bias", "med_rel_bias_delta", "q99_under_frac"]

EXCLUDE_COLS = {
    "basin", "seed",
    "n_q99_timesteps", "obs_q99_threshold",
    # other error metrics (not predictors)
    "q99_under_frac", "q99_med_rel_bias",
    "model1_under_frac", "model1_med_rel_bias",
    "under_frac_delta", "med_rel_bias_delta",
}


def spearman_per_seed(
    profile: pd.DataFrame, feature_cols: list[str]
) -> pd.DataFrame:
    records = []
    for seed in sorted(profile["seed"].unique()):
        sub = profile[profile["seed"] == seed]
        for feat in feature_cols:
            x = sub[feat].astype(float)
            if x.notna().sum() < 10:
                continue
            for target in TARGET_METRICS:
                y = sub[target].astype(float)
                valid = x.notna() & y.notna()
                if valid.sum() < 10:
                    continue
                rho, pval = stats.spearmanr(x[valid], y[valid])
                records.append({
                    "attribute": feat,
                    "seed": int(seed),
                    "target": target,
                    "rho": rho,
                    "pval": pval,
                    "n": int(valid.sum()),
                })
    return pd.DataFrame(records)


def find_stable_drivers(corr: pd.DataFrame, min_agree: int = 3) -> pd.DataFrame:
    """Attributes where all seeds agree on direction for a target."""
    records = []
    for (feat, target), grp in corr.groupby(["attribute", "target"]):
        if len(grp) < min_agree:
            continue
        signs = np.sign(grp["rho"].values)
        n_pos = (signs > 0).sum()
        n_neg = (signs < 0).sum()
        n_agree = max(n_pos, n_neg)
        if n_agree >= min_agree:
            records.append({
                "attribute": feat,
                "target": target,
                "rho_median": grp["rho"].median(),
                "rho_min": grp["rho"].min(),
                "rho_max": grp["rho"].max(),
                "pval_median": grp["pval"].median(),
                "n_agree": int(n_agree),
                "direction": "positive" if n_pos >= n_neg else "negative",
            })
    return (
        pd.DataFrame(records)
        .sort_values("rho_median", key=abs, ascending=False)
        .reset_index(drop=True)
    )


def quartile_comparison(
    summary: pd.DataFrame, feature_cols: list[str], target: str
) -> pd.DataFrame:
    y = summary[target]
    q25, q75 = y.quantile(0.25), y.quantile(0.75)
    worst = summary[y <= q25]
    best = summary[y >= q75]

    records = []
    for feat in feature_cols:
        if feat not in summary.columns:
            continue
        w = worst[feat].astype(float)
        b = best[feat].astype(float)
        records.append({
            "attribute": feat,
            "target": target,
            "worst_q1_median": w.median(),
            "best_q4_median": b.median(),
            "diff": b.median() - w.median(),
            "n_worst": int(w.notna().sum()),
            "n_best": int(b.notna().sum()),
        })
    return pd.DataFrame(records).sort_values("diff", key=abs, ascending=False)


def main() -> None:
    profile = pd.read_csv(OUT_DIR / "basin_q99_error_profile.csv")
    summary = pd.read_csv(OUT_DIR / "basin_q99_error_summary.csv")
    summary["basin"] = summary["basin"].astype(str)

    # feature columns: all numeric except targets and identifiers
    feature_cols = [
        c for c in profile.columns
        if c not in EXCLUDE_COLS
        and profile[c].dtype in [float, "float64", int, "int64"]
    ]
    print(f"Feature pool: {len(feature_cols)} attributes")

    # ── Spearman per seed ──────────────────────────────────────────────────
    print("\n── Spearman correlation (per seed) …")
    corr = spearman_per_seed(profile, feature_cols)
    corr.to_csv(OUT_DIR / "q99_driver_correlation.csv", index=False)
    print(f"  Saved: q99_driver_correlation.csv  ({len(corr)} rows)")

    # ── Stable drivers ─────────────────────────────────────────────────────
    print("\n── Stable drivers (3-seed directional agreement) …")
    stable = find_stable_drivers(corr, min_agree=3)
    stable.to_csv(OUT_DIR / "q99_stable_drivers.csv", index=False)
    print(f"  Saved: q99_stable_drivers.csv  ({len(stable)} rows)")

    for target in TARGET_METRICS:
        sub = stable[stable["target"] == target].head(10)
        if sub.empty:
            continue
        print(f"\n  Top-10 stable drivers [{target}]:")
        print(
            sub[["attribute", "rho_median", "pval_median", "direction"]]
            .to_string(index=False)
        )

    # ── Quartile comparison ────────────────────────────────────────────────
    print("\n── Quartile comparison (Q1 worst vs Q4 best) …")
    all_q = []
    for target in TARGET_METRICS:
        all_q.append(quartile_comparison(summary, feature_cols, target))
    qdf = pd.concat(all_q, ignore_index=True)
    qdf.to_csv(OUT_DIR / "q99_quartile_comparison.csv", index=False)
    print("  Saved: q99_quartile_comparison.csv")

    # Print top-5 stable drivers for q99_med_rel_bias with quartile diff
    print("\n── Q1 vs Q4 attribute gap (q99_med_rel_bias, top stable drivers) ──")
    top_stable = stable[stable["target"] == "q99_med_rel_bias"].head(5)["attribute"].tolist()
    qsub = qdf[
        (qdf["target"] == "q99_med_rel_bias") &
        (qdf["attribute"].isin(top_stable))
    ][["attribute", "worst_q1_median", "best_q4_median", "diff"]]
    print(qsub.to_string(index=False))


if __name__ == "__main__":
    main()
