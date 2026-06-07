#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pandas>=2.2",
#   "numpy>=2.0",
#   "pyarrow>=15",
#   "scikit-learn>=1.4",
# ]
# ///
"""non-DRBC 유역으로 학습 → DRBC 유역(allrain/static)으로 검증.

설계:
  - 학습: nondrbc_features_allrain.csv (train 유역, 완전 새 도메인)
  - 테스트: features_allrain.csv + static_features_q99.csv (DRBC 유역)
  - 피처: S1_LOG (area → log_area 교체) 또는 S1_RAW (raw area)
  - 비교: 이전 allrain GroupKFold 결과와 above_q99_recall 비교

출력 (signal_sweep/tables/):
  obsclass_nondrbc_metrics.csv        — 기본 (log_area) 학습/테스트 요약
  obsclass_nondrbc_metrics_area.csv   — raw area 버전 (--feature-set area|both)
  obsclass_nondrbc_compare.csv        — area vs log_area 비교 (--feature-set both)
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import GroupKFold

TABLES = Path("output/model_analysis/band_signal/signal_sweep/tables")
RANDOM_STATE = 42
N_ESTIMATORS = 300

# allrain와 동일한 S1 피처 (area → log_area 교체)
S1_LOG = [
    "log_area",        # log(area) — 수문학적 scale 관계
    "baseflow_index",
    "permeability",
    "crainf_frac_mean",
    "slope",
    "aridity",
    "soil_depth",
    "snow_fraction",
    "forest_fraction",
    "rain_sum_event",
    "rain_max_1h",
    "cape_max",
]

# raw area 버전 (log_area → area)
S1_RAW = [
    "area",
    "baseflow_index",
    "permeability",
    "crainf_frac_mean",
    "slope",
    "aridity",
    "soil_depth",
    "snow_fraction",
    "forest_fraction",
    "rain_sum_event",
    "rain_max_1h",
    "cape_max",
]

# 비교용: allrain GroupKFold 기존 결과 (train_obsclass_classifier.py 산출물)
PREV_METRICS_CSV = TABLES / "obsclass_cv_metrics.csv"


def make_clf():
    return RandomForestClassifier(
        n_estimators=N_ESTIMATORS,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )


def eval_metrics(y_true, y_pred, dataset, n_basins, n_events, features_used):
    acc = accuracy_score(y_true, y_pred)
    wf1 = f1_score(y_true, y_pred, average="weighted", zero_division=0)
    mf1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    rec = recall_score(y_true, y_pred, pos_label=1, zero_division=0)
    prec_q99 = precision_score(y_true, y_pred, pos_label=1, zero_division=0)
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
        "above_q99_precision": round(prec_q99, 4),
        "cm_tn": int(cm[0, 0]),
        "cm_fp": int(cm[0, 1]),
        "cm_fn": int(cm[1, 0]),
        "cm_tp": int(cm[1, 1]),
    }


def add_log_area(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "log_area" not in df.columns:
        df["log_area"] = np.log(df["area"].clip(lower=1e-3))
    return df


def load_nondrbc(tables: Path) -> pd.DataFrame:
    csv = tables / "nondrbc_features_allrain.csv"
    if not csv.exists():
        raise FileNotFoundError(
            f"non-DRBC 피처 없음: {csv}\n"
            "  signal_sweep_nondrbc_allrain.py 먼저 실행 필요"
        )
    df = pd.read_csv(csv)
    df["above_q99"] = (df["oc"].round().astype(int) == 4).astype(int)
    return add_log_area(df)


def load_test(tables: Path) -> pd.DataFrame:
    """allrain 전체 강우 사건 (DRBC test split)."""
    csv = tables / "features_allrain.csv"
    df = pd.read_csv(csv)
    df["above_q99"] = (df["oc"].round().astype(int) == 4).astype(int)
    return add_log_area(df)


def load_q99(tables: Path) -> pd.DataFrame | None:
    """Q99 사건 static(static) + forcing(forcing) merge."""
    csv_a = tables / "static_features_q99.csv"
    csv_b = tables / "forcing_features_q99.csv"
    if not csv_a.exists() or not csv_b.exists():
        return None
    df_a = pd.read_csv(csv_a)
    df_b = pd.read_csv(csv_b)
    df = pd.merge(df_a, df_b, on=["basin_id", "peak_time", "oc"], how="inner")
    df["above_q99"] = (df["oc"].round().astype(int) == 4).astype(int)
    return add_log_area(df)


def available_features(df: pd.DataFrame, feat_list: list[str]) -> list[str]:
    return [f for f in feat_list if f in df.columns]


def run_groupkfold(df: pd.DataFrame, feat_list: list[str], n_splits: int = 5) -> pd.DataFrame:
    """non-DRBC 유역 내부 Basin GroupKFold CV."""
    feats = available_features(df, feat_list)
    X = df[feats].values
    y = df["above_q99"].values
    groups = df["basin_id"].values

    gkf = GroupKFold(n_splits=n_splits)
    rows = []
    cm_agg = np.zeros((2, 2), dtype=int)

    for fold, (tr_idx, te_idx) in enumerate(gkf.split(X, y, groups)):
        clf = make_clf()
        clf.fit(X[tr_idx], y[tr_idx])
        y_pred = clf.predict(X[te_idx])
        y_true = y[te_idx]

        acc = accuracy_score(y_true, y_pred)
        wf1 = f1_score(y_true, y_pred, average="weighted", zero_division=0)
        mf1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
        rec = recall_score(y_true, y_pred, pos_label=1, zero_division=0)
        cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
        cm_agg += cm

        held = len(np.unique(groups[te_idx]))
        rows.append({
            "split": "nondrbc_basin_groupkfold",
            "fold": fold,
            "accuracy": round(acc, 4),
            "weighted_f1": round(wf1, 4),
            "macro_f1": round(mf1, 4),
            "above_q99_recall": round(rec, 4),
            "held_basins": held,
            "n_test": len(te_idx),
        })
        print(f"  fold {fold}: recall={rec:.3f}  acc={acc:.3f}  held={held}개 유역")

    print(f"\n  평균 recall: {np.mean([r['above_q99_recall'] for r in rows]):.3f}")
    print(f"  혼동행렬 집계: TN={cm_agg[0,0]} FP={cm_agg[0,1]} FN={cm_agg[1,0]} TP={cm_agg[1,1]}")
    return pd.DataFrame(rows)


def run_experiment(train_df, test_df, q99_df, feat_list, label, prev_recall):
    """단일 피처셋으로 실험 실행 후 (results, imp) 반환."""
    train_feats = available_features(train_df, feat_list)
    test_feats = available_features(test_df, feat_list)
    common_feats = [f for f in train_feats if f in test_feats]

    print(f"\n[{label}] 피처({len(common_feats)}개): {common_feats}")

    clf = make_clf()
    clf.fit(train_df[common_feats].values, train_df["above_q99"].values)

    results = []

    # test (전체 강우, allrain)
    y_pred_test = clf.predict(test_df[common_feats].values)
    r_test = eval_metrics(
        test_df["above_q99"].values, y_pred_test,
        "test",
        test_df["basin_id"].nunique(), len(test_df), common_feats,
    )
    r_test["feature_set"] = label
    results.append(r_test)
    print(f"  test:  acc={r_test['accuracy']:.3f}  recall={r_test['above_q99_recall']:.3f}"
          f"  prec={r_test['above_q99_precision']:.3f}")

    # q99 (Q99 사건, forcing forcing 포함)
    if q99_df is not None:
        q99_feats = available_features(q99_df, feat_list)
        q99_common = [f for f in common_feats if f in q99_feats]
        if q99_common:
            if q99_common != common_feats:
                clf_q99 = make_clf()
                clf_q99.fit(train_df[q99_common].values, train_df["above_q99"].values)
            else:
                clf_q99 = clf
            y_pred_q99 = clf_q99.predict(q99_df[q99_common].values)
            r_q99 = eval_metrics(
                q99_df["above_q99"].values, y_pred_q99,
                "q99",
                q99_df["basin_id"].nunique(), len(q99_df), q99_common,
            )
            r_q99["feature_set"] = label
            results.append(r_q99)
            print(f"  q99:   acc={r_q99['accuracy']:.3f}  recall={r_q99['above_q99_recall']:.3f}")

    if not np.isnan(prev_recall):
        delta = r_test["above_q99_recall"] - prev_recall
        print(f"  Δrecall vs GroupKFold({prev_recall:.3f}) = {delta:+.3f}")

    imp = pd.DataFrame({
        "feature": common_feats,
        "importance": clf.feature_importances_,
        "feature_set": label,
    }).sort_values("importance", ascending=False)

    return results, imp


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--feature-set", choices=["log_area", "area", "both"], default="log_area",
                   help="피처셋 선택 (default: log_area)")
    p.add_argument("--groupkfold", action="store_true",
                   help="non-DRBC 내부 Basin GroupKFold CV 실행")
    args = p.parse_args()

    print("non-DRBC → DRBC 분류기 실험")
    print("=" * 50)

    train_df = load_nondrbc(TABLES)
    test_df = load_test(TABLES)
    q99_df = load_q99(TABLES)

    print(f"\n학습 유역: {train_df['basin_id'].nunique()}개 유역, {len(train_df)} 사건")
    print(f"above_q99 비율 (train): {train_df['above_q99'].mean():.1%}")

    if args.groupkfold:
        print("\n[non-DRBC 내부 Basin GroupKFold CV]")
        print("-" * 40)
        cv_rows = run_groupkfold(train_df, S1_LOG)
        cv_out = TABLES / "obsclass_nondrbc_cv_metrics.csv"
        cv_rows.to_csv(cv_out, index=False)
        print(f"→ {cv_out}")
        return

    # GroupKFold baseline recall
    prev_recall = float("nan")
    if PREV_METRICS_CSV.exists():
        prev = pd.read_csv(PREV_METRICS_CSV)
        basin_cv = prev[prev["split"] == "basin_groupkfold"]
        if len(basin_cv):
            prev_recall = basin_cv["above_q99_recall"].mean()

    sets_to_run = {
        "log_area": S1_LOG,
        "area": S1_RAW,
    }
    if args.feature_set == "both":
        run_keys = ["log_area", "area"]
    else:
        run_keys = [args.feature_set]

    all_results = []
    all_imp = []
    for key in run_keys:
        res, imp = run_experiment(train_df, test_df, q99_df, sets_to_run[key], key, prev_recall)
        all_results.extend(res)
        all_imp.append(imp)

    results_df = pd.DataFrame(all_results)
    results_df["prev_allrain_groupkfold_recall"] = prev_recall
    imp_df = pd.concat(all_imp, ignore_index=True)

    # 기본 출력 (log_area 또는 단일 실행)
    out_csv = TABLES / "obsclass_nondrbc_metrics.csv"
    if args.feature_set == "both":
        # both: 비교 CSV 별도 저장, log_area 결과를 기본 파일에도 저장
        log_rows = results_df[results_df["feature_set"] == "log_area"].copy()
        log_rows.to_csv(out_csv, index=False)
        compare_out = TABLES / "obsclass_nondrbc_compare.csv"
        results_df.to_csv(compare_out, index=False)
        print(f"\n→ {compare_out}  (area vs log_area 비교)")
        # area 버전 별도 저장
        area_rows = results_df[results_df["feature_set"] == "area"].copy()
        area_out = TABLES / "obsclass_nondrbc_metrics_area.csv"
        area_rows.to_csv(area_out, index=False)
        print(f"→ {area_out}")
    elif args.feature_set == "area":
        area_out = TABLES / "obsclass_nondrbc_metrics_area.csv"
        results_df.to_csv(area_out, index=False)
        print(f"\n→ {area_out}")
    else:
        results_df.to_csv(out_csv, index=False)

    print(f"→ {out_csv}")

    imp_out = TABLES / "obsclass_nondrbc_feature_importance.csv"
    imp_df[imp_df["feature_set"] == run_keys[0]].drop(columns="feature_set").to_csv(imp_out, index=False)
    print(f"→ {imp_out}")


if __name__ == "__main__":
    main()
