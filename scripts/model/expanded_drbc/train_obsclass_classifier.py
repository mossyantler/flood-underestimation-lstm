#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pandas>=2.2",
#   "numpy>=2.0",
#   "pyarrow>=15",
#   "scikit-learn>=1.4",
# ]
# ///
"""Train obs_class RandomForest classifiers on allrain with GroupKFold.

Outputs (signal_sweep/tables/):
  obsclass_cv_metrics.csv            – per-fold metrics, basin vs event split
  obsclass_confusion_binary.csv      – aggregate binary confusion (basin CV)
  obsclass_confusion_ordinal.csv     – aggregate ordinal confusion (basin CV)
  obsclass_feature_importance.csv    – mean ± std importance across folds
  obsclass_ablation_band_signal.csv  – S1 vs S1+S2 comparison
"""

import pathlib

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    recall_score,
)
from sklearn.model_selection import GroupKFold, StratifiedKFold

TABLES = pathlib.Path("output/model_analysis/band_signal/signal_sweep/tables")
RANDOM_STATE = 42
N_SPLITS = 5
N_ESTIMATORS = 300

S1_FULL = [
    "area", "baseflow_index", "permeability", "crainf_frac_mean",
    "slope", "aridity", "soil_depth", "snow_fraction", "forest_fraction",
    "rain_sum_event", "rain_max_1h", "cape_max",
]
S2_BAND = ["rel_width", "q99_q50_ratio"]
S1_PLUS_S2 = S1_FULL + S2_BAND


def _make_clf():
    return RandomForestClassifier(
        n_estimators=N_ESTIMATORS,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )


def run_cv(X, y, groups, n_classes, cv, split_label):
    """Run CV and return (rows, aggregated_cm, importances_per_fold)."""
    rows = []
    cm_agg = np.zeros((n_classes, n_classes), dtype=int)
    importances = []

    for fold, (tr, te) in enumerate(cv.split(X, y, groups)):
        X_tr, X_te = X[tr], X[te]
        y_tr, y_te = y[tr], y[te]

        clf = _make_clf()
        clf.fit(X_tr, y_tr)
        y_pred = clf.predict(X_te)

        acc = accuracy_score(y_te, y_pred)
        wf1 = f1_score(y_te, y_pred, average="weighted", zero_division=0)
        mf1 = f1_score(y_te, y_pred, average="macro", zero_division=0)
        rec = (
            recall_score(y_te, y_pred, pos_label=1, zero_division=0)
            if n_classes == 2
            else float("nan")
        )

        cm = confusion_matrix(y_te, y_pred, labels=list(range(n_classes)))
        cm_agg += cm
        importances.append(clf.feature_importances_)

        held_basins = len(set(groups[te])) if groups is not None else None
        rows.append({
            "split": split_label,
            "fold": fold,
            "accuracy": acc,
            "weighted_f1": wf1,
            "macro_f1": mf1,
            "above_q99_recall": rec,
            "held_basins": held_basins,
            "n_test": len(y_te),
        })

    return rows, cm_agg, np.array(importances)


def main():
    df = pd.read_parquet(TABLES / "obsclass_model_matrix_allrain.parquet")
    X = df[S1_FULL].values
    y_bin = df["above_q99"].values
    y_ord = df["oc_ordinal"].values
    groups = df["basin_id"].values

    print(f"allrain: {len(df)} events, {df['basin_id'].nunique()} basins")
    print(f"above_q99 rate: {y_bin.mean():.1%}")

    # --- Basin GroupKFold headline (binary) ---
    print("\nRunning basin GroupKFold — binary headline...")
    rows_bin, cm_bin, imp = run_cv(
        X, y_bin, groups, 2,
        GroupKFold(n_splits=N_SPLITS), "basin_groupkfold"
    )

    # --- Basin GroupKFold secondary (ordinal 5-class) ---
    print("Running basin GroupKFold — ordinal secondary...")
    rows_ord, cm_ord, _ = run_cv(
        X, y_ord, groups, 5,
        GroupKFold(n_splits=N_SPLITS), "basin_groupkfold_ordinal"
    )

    # --- Event StratifiedKFold upper bound (binary) ---
    print("Running event StratifiedKFold — upper bound...")
    rows_evt, _, _ = run_cv(
        X, y_bin, None, 2,
        StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE),
        "event_level_upper_bound"
    )

    # Save metrics
    df_cv = pd.DataFrame(rows_bin + rows_ord + rows_evt)
    df_cv.to_csv(TABLES / "obsclass_cv_metrics.csv", index=False)

    df_bin = pd.DataFrame(rows_bin)
    df_evt = pd.DataFrame(rows_evt)
    basin_acc = df_bin["accuracy"].mean()
    event_acc = df_evt["accuracy"].mean()
    gap = event_acc - basin_acc
    print(f"\nHeadline (basin GroupKFold, binary):")
    print(f"  accuracy={basin_acc:.3f}  wF1={df_bin['weighted_f1'].mean():.3f}"
          f"  above_q99_recall={df_bin['above_q99_recall'].mean():.3f}")
    print(f"Event upper bound accuracy={event_acc:.3f}  leakage gap={gap:+.3f}")

    # Confusion matrices (rows=true, cols=predicted)
    pd.DataFrame(
        cm_bin,
        index=["true_other", "true_above_q99"],
        columns=["pred_other", "pred_above_q99"],
    ).to_csv(TABLES / "obsclass_confusion_binary.csv")

    pd.DataFrame(
        cm_ord,
        index=[f"true_oc{i}" for i in range(5)],
        columns=[f"pred_oc{i}" for i in range(5)],
    ).to_csv(TABLES / "obsclass_confusion_ordinal.csv")

    # Feature importance
    df_imp = pd.DataFrame({
        "feature": S1_FULL,
        "importance_mean": imp.mean(axis=0),
        "importance_std": imp.std(axis=0),
    }).sort_values("importance_mean", ascending=False)
    df_imp.to_csv(TABLES / "obsclass_feature_importance.csv", index=False)
    print("\nTop 5 features:")
    print(df_imp.head(5).to_string(index=False))

    # Ablation S1 vs S1+S2
    print("\nRunning ablation S1+S2...")
    X_s2 = df[S1_PLUS_S2].values
    rows_s2, _, _ = run_cv(
        X_s2, y_bin, groups, 2,
        GroupKFold(n_splits=N_SPLITS), "basin_groupkfold_s2"
    )
    df_s1 = df_bin
    df_s2 = pd.DataFrame(rows_s2)
    df_abl = pd.DataFrame([
        {
            "feature_set": "S1",
            "mean_accuracy": df_s1["accuracy"].mean(),
            "mean_weighted_f1": df_s1["weighted_f1"].mean(),
            "mean_above_q99_recall": df_s1["above_q99_recall"].mean(),
        },
        {
            "feature_set": "S1+S2(band)",
            "mean_accuracy": df_s2["accuracy"].mean(),
            "mean_weighted_f1": df_s2["weighted_f1"].mean(),
            "mean_above_q99_recall": df_s2["above_q99_recall"].mean(),
        },
    ])
    df_abl.to_csv(TABLES / "obsclass_ablation_band_signal.csv", index=False)
    print("Ablation result:")
    print(df_abl.to_string(index=False))

    print("\nDone: 5 tables written.")


if __name__ == "__main__":
    main()
