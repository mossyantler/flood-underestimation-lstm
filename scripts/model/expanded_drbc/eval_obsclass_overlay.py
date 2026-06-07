#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pandas>=2.2",
#   "numpy>=2.0",
#   "pyarrow>=15",
#   "scikit-learn>=1.4",
# ]
# ///
"""Evaluate obs_class classifier on held-out static and NOAA overlays.

Trains a final model on ALL allrain data, then predicts on static/NOAA
events whose basins did NOT appear in allrain. Basin intersection = 0 asserted.

Feature mismatch handling:
  static  – has S1_STATIC (8 static attrs) but no event forcing cols.
  NOAA     – has forcing cols (renamed from 24h/72h windows) but no static attrs.
  → Each overlay uses the subset of S1_FULL available in that dataset.
  → A allrain model is re-trained on that same subset for fair comparison.

Output (signal_sweep/tables/):
  obsclass_overlay_metrics.csv  – accuracy/F1/confusion per overlay dataset
"""

import pathlib

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, recall_score

TABLES = pathlib.Path("output/model_analysis/band_signal/signal_sweep/tables")
RANDOM_STATE = 42
N_ESTIMATORS = 300

S1_FULL = [
    "area", "baseflow_index", "permeability", "crainf_frac_mean",
    "slope", "aridity", "soil_depth", "snow_fraction", "forest_fraction",
    "rain_sum_event", "rain_max_1h", "cape_max",
]


def _make_clf():
    return RandomForestClassifier(
        n_estimators=N_ESTIMATORS,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )


def _eval_metrics(y_true, y_pred, dataset, n_basins, n_events, features_used):
    acc = accuracy_score(y_true, y_pred)
    wf1 = f1_score(y_true, y_pred, average="weighted", zero_division=0)
    mf1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    rec = recall_score(y_true, y_pred, pos_label=1, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    return {
        "dataset": dataset,
        "n_basins": n_basins,
        "n_events": n_events,
        "features_used": ",".join(features_used),
        "accuracy": round(acc, 4),
        "weighted_f1": round(wf1, 4),
        "macro_f1": round(mf1, 4),
        "above_q99_recall": round(rec, 4),
        "cm_tn": int(cm[0, 0]),
        "cm_fp": int(cm[0, 1]),
        "cm_fn": int(cm[1, 0]),
        "cm_tp": int(cm[1, 1]),
    }


def _overlay(b2, overlay_df, dataset_name, available_feats):
    b2_basins = set(b2["basin_id"].unique())
    held = overlay_df[~overlay_df["basin_id"].isin(b2_basins)].copy()

    assert len(set(held["basin_id"]) & b2_basins) == 0, (
        f"Basin intersection not zero for {dataset_name}: "
        f"{set(held['basin_id']) & b2_basins}"
    )

    if held.empty:
        print(f"  {dataset_name}: all basins overlap with allrain — skip")
        return None

    print(f"  {dataset_name}: {len(held)} events, {held['basin_id'].nunique()} held-out basins")
    print(f"  features: {available_feats}")

    clf = _make_clf()
    clf.fit(b2[available_feats].values, b2["above_q99"].values)
    y_pred = clf.predict(held[available_feats].values)
    y_true = held["above_q99"].values

    result = _eval_metrics(
        y_true, y_pred, dataset_name,
        held["basin_id"].nunique(), len(held), available_feats
    )
    print(f"  acc={result['accuracy']:.3f}  wF1={result['weighted_f1']:.3f}"
          f"  above_q99_recall={result['above_q99_recall']:.3f}")
    return result


def main():
    b2 = pd.read_parquet(TABLES / "obsclass_model_matrix_allrain.parquet")
    ba = pd.read_parquet(TABLES / "obsclass_model_matrix_static.parquet")
    bn = pd.read_parquet(TABLES / "obsclass_model_matrix_noaa.parquet")

    results = []

    print("static overlay...")
    ba_feats = [c for c in S1_FULL if c in ba.columns]
    r = _overlay(b2, ba, "static_q99", ba_feats)
    if r:
        results.append(r)

    print("NOAA overlay...")
    bn_feats = [c for c in S1_FULL if c in bn.columns]
    r = _overlay(b2, bn, "forcing_noaa", bn_feats)
    if r:
        results.append(r)

    if results:
        df = pd.DataFrame(results)
        df.to_csv(TABLES / "obsclass_overlay_metrics.csv", index=False)
        print(f"\nSaved: obsclass_overlay_metrics.csv ({len(results)} rows)")
    else:
        print("No overlay results (all basins overlapped with allrain).")


if __name__ == "__main__":
    main()
