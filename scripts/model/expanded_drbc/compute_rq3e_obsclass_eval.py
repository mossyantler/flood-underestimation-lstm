# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2.2", "numpy>=2.0", "matplotlib>=3.9"]
# ///
"""RQ-3e — obs_class 기반 모델 평가 (DIRECT / surrogate 분리).

category error 방지가 이 스크립트의 핵심이다. 두 가지 서로 다른 평가를 절대
혼동하지 않도록 산출물·헤더·컬럼명에 ``direct`` / ``surrogate`` 를 명시한다.

(a) DIRECT — 관측 band-position 기반 Model 2 평가  [genuine M2 evaluation]
    관측 첨두가 Model 2 예측 밴드(q50~q99) 어디에 드는지(obs_class)를 직접 집계.
    - obs_class == above_q99  → 관측이 q99 천장을 넘음 = **M2 q99 과소추정**
      (predicted band ceiling < actual obs).
    - obs_class == below_q50  → 관측이 중앙 예측보다 낮음 = M2 과대추정.
    헤드라인 = above_q99 비율(= M2 q99 과소추정율).
    M1 NSE tier(top/mid/bottom 1/3) 분할 = compute_rq4a_nse_tier_stratify.py:62의
    tier machinery 산출(rq4a_nse_tier_assignments.csv) 재사용. tier 분할로 "M1이
    가장 약한 유역에서 M2 과소추정이 집중되는가"를 본다 = M1 대비 평가 연결.

(b) surrogate — RF 분류기 forcing-surrogate predictability  [NOT M2 evaluation]
    train_obsclass_classifier 가 낸 RF predicted-vs-actual obs_class 혼동행렬.
    이는 "강제력·정적 속성만으로 밴드 위치를 예측 가능한가"의 진단일 뿐,
    **Model 2 성능 평가가 아니다**(run_obsclass_pipeline.py:141 guardrail 유지).
    혼동행렬의 FN/FP는 분류기 오류율이며 M2 과소추정율로 라벨하지 않는다.

입력
----
  output/model_analysis/primary/metrics/tables/location_class_q99.csv  (DIRECT)
  output/model_analysis/primary/metrics/tables/location_class_noaa.csv (DIRECT)
  output/model_analysis/primary/metrics/tables/rq4a_nse_tier_assignments.csv (tier)
  output/model_analysis/band_signal/signal_sweep/tables/obsclass_confusion_ordinal.csv (surrogate)
  output/model_analysis/band_signal/signal_sweep/tables/obsclass_confusion_binary.csv  (surrogate)

출력
----
  .../primary/metrics/tables/rq3e_obsclass_eval_direct_oc4recall.csv
  .../primary/metrics/tables/rq3e_obsclass_eval_direct_byclass.csv
  .../primary/metrics/tables/rq3e_obsclass_eval_surrogate_confusion.csv
  .../primary/metrics/tables/rq3e_obsclass_eval_surrogate_summary.csv
  .../primary/metrics/figures/rq3e_obsclass_eval_direct.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]

_LIB_ROOT = Path(__file__).resolve().parents[2] / "_lib"
if str(_LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(_LIB_ROOT))
from expanded_drbc import normalize_basin_id  # noqa: E402

DEFAULT_METRICS_DIR = REPO_ROOT / "output/model_analysis/primary/metrics"
DEFAULT_SURROGATE_DIR = (
    REPO_ROOT / "output/model_analysis/band_signal/signal_sweep/tables"
)

# obs_class 서수 정의 (signal_sweep_allrain.py:63-67 과 동일 정의)
OC_ORDER = ["below_q50", "q50_to_q90", "q90_to_q95", "q95_to_q99", "above_q99"]
OC_TO_INT = {c: i for i, c in enumerate(OC_ORDER)}
TIER_ORDER = ["top", "mid", "bottom"]
N_GATE = 10  # tier 셀 사건 수 하한


# ── (a) DIRECT ──────────────────────────────────────────────────────────────
def _direct(metrics_dir: Path):
    tier = pd.read_csv(metrics_dir / "tables/rq4a_nse_tier_assignments.csv",
                       dtype={"basin_id": str})
    tier["basin_id"] = tier["basin_id"].map(normalize_basin_id)
    tier = tier[["basin_id", "tier"]]

    oc4_rows, byclass_rows = [], []
    for scope in ("q99", "noaa"):
        loc = pd.read_csv(metrics_dir / f"tables/location_class_{scope}.csv",
                          comment="#", dtype={"basin_id": str})
        loc["basin_id"] = loc["basin_id"].map(normalize_basin_id)
        loc["oc"] = loc["obs_class"].map(OC_TO_INT)
        loc = loc.merge(tier, on="basin_id", how="left")

        for tname in TIER_ORDER + ["ALL"]:
            g = loc if tname == "ALL" else loc[loc["tier"] == tname]
            if g.empty:
                continue
            n_events = g[["basin_id", "peak_time"]].drop_duplicates().shape[0]
            n_es = len(g)  # (event, seed) pooled pairs
            suppressed = (tname != "ALL") and (n_events < N_GATE)

            rec = {
                "scope": scope, "m1_nse_tier": tname,
                "n_events": n_events, "n_event_seed": n_es,
                "suppressed": suppressed,
            }
            if suppressed:
                for c in ("m2_q99_underestimation_rate", "m2_overprediction_rate",
                          "under_ge_q95_rate"):
                    rec[c] = np.nan
            else:
                rec["m2_q99_underestimation_rate"] = (g["oc"] == 4).mean()  # above_q99
                rec["m2_overprediction_rate"] = (g["oc"] == 0).mean()       # below_q50
                rec["under_ge_q95_rate"] = (g["oc"] >= 3).mean()            # q95+ 초과
            oc4_rows.append(rec)

            # full obs_class distribution per tier
            if not suppressed:
                frac = g["obs_class"].value_counts(normalize=True)
                for oc_name in OC_ORDER:
                    byclass_rows.append({
                        "scope": scope, "m1_nse_tier": tname, "obs_class": oc_name,
                        "fraction": float(frac.get(oc_name, 0.0)),
                        "n_event_seed": n_es,
                    })

    oc4 = pd.DataFrame(oc4_rows)
    byclass = pd.DataFrame(byclass_rows)
    return oc4, byclass


# ── (b) surrogate ───────────────────────────────────────────────────────────
def _surrogate(surrogate_dir: Path):
    ordinal = pd.read_csv(surrogate_dir / "obsclass_confusion_ordinal.csv", index_col=0)
    binary = pd.read_csv(surrogate_dir / "obsclass_confusion_binary.csv", index_col=0)

    # ordinal 혼동행렬 → long form, forcing-surrogate 라벨 명시
    long_rows = []
    for true_lbl, row in ordinal.iterrows():
        for pred_lbl, count in row.items():
            long_rows.append({
                "evaluation_kind": "forcing_surrogate",  # NOT M2 evaluation
                "true_obs_class": str(true_lbl).replace("true_", ""),
                "pred_obs_class": str(pred_lbl).replace("pred_", ""),
                "count": int(count),
            })
    confusion_long = pd.DataFrame(long_rows)

    # binary 혼동 → classifier 오류율(FN/FP). M2 과소추정율로 라벨 금지.
    tn = int(binary.loc["true_other", "pred_other"])
    fp = int(binary.loc["true_other", "pred_above_q99"])
    fn = int(binary.loc["true_above_q99", "pred_other"])
    tp = int(binary.loc["true_above_q99", "pred_above_q99"])
    summary = pd.DataFrame([{
        "evaluation_kind": "forcing_surrogate",
        "note": "RF classifier error rates; NOT M2 underestimation",
        "cm_tn": tn, "cm_fp": fp, "cm_fn": fn, "cm_tp": tp,
        "classifier_fn_rate": fn / (fn + tp) if (fn + tp) else np.nan,
        "classifier_fp_rate": fp / (fp + tn) if (fp + tn) else np.nan,
        "above_q99_recall": tp / (tp + fn) if (tp + fn) else np.nan,
    }])
    return confusion_long, summary


def _plot_direct(oc4: pd.DataFrame, fig_path: Path):
    q = oc4[(oc4["scope"] == "q99") & (~oc4["suppressed"])
            & (oc4["m1_nse_tier"].isin(TIER_ORDER))].copy()
    q["_o"] = q["m1_nse_tier"].map({t: i for i, t in enumerate(TIER_ORDER)})
    q = q.sort_values("_o")
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    x = range(len(q))
    ax.bar(x, q["m2_q99_underestimation_rate"].values, color="#d73027", width=0.6)
    for i, v in zip(x, q["m2_q99_underestimation_rate"].values):
        ax.text(i, v + 0.005, f"{v:.2f}", ha="center", va="bottom", fontsize=9)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{t}\n(n_ev={int(n)})" for t, n in zip(q["m1_nse_tier"], q["n_events"])])
    ax.set_ylabel("M2 q99 underestimation rate\n(obs above q99, pooled event-seed)")
    ax.set_xlabel("M1 deterministic NSE tier")
    ax.set_title("RQ-3e DIRECT — M2 q99 underestimation by M1 NSE tier (Q99 scope)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(fig_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics-dir", type=Path, default=DEFAULT_METRICS_DIR)
    parser.add_argument("--surrogate-dir", type=Path, default=DEFAULT_SURROGATE_DIR)
    args = parser.parse_args(argv)

    tables = args.metrics_dir / "tables"
    figures = args.metrics_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)

    # (a) DIRECT
    oc4, byclass = _direct(args.metrics_dir)
    p_oc4 = tables / "rq3e_obsclass_eval_direct_oc4recall.csv"
    p_byclass = tables / "rq3e_obsclass_eval_direct_byclass.csv"
    with p_oc4.open("w") as f:
        f.write("# RQ-3e DIRECT — 관측 band-position 기반 M2 평가. "
                "above_q99=M2 q99 과소추정, below_q50=과대추정. tier=M1 NSE(rq4a). "
                "n_events<10 tier 셀 suppress.\n")
        oc4.to_csv(f, index=False)
    with p_byclass.open("w") as f:
        f.write("# RQ-3e DIRECT — scope×tier obs_class 분포(관측 band-position).\n")
        byclass.to_csv(f, index=False)

    # n-gate caveat
    sup = oc4[oc4["suppressed"]]
    if len(sup):
        for _, r in sup.iterrows():
            print(f"[n-gate] DIRECT suppressed (n_events={r['n_events']}<{N_GATE}): "
                  f"scope={r['scope']} tier={r['m1_nse_tier']}")
    else:
        print(f"[n-gate] DIRECT: no tier cell below n={N_GATE}.")

    # (b) surrogate
    confusion_long, summary = _surrogate(args.surrogate_dir)
    p_conf = tables / "rq3e_obsclass_eval_surrogate_confusion.csv"
    p_sum = tables / "rq3e_obsclass_eval_surrogate_summary.csv"
    with p_conf.open("w") as f:
        f.write("# RQ-3e SURROGATE — RF forcing-surrogate predictability. "
                "NOT M2 evaluation (run_obsclass_pipeline.py:141 guardrail).\n")
        confusion_long.to_csv(f, index=False)
    with p_sum.open("w") as f:
        f.write("# RQ-3e SURROGATE — RF classifier error rates(FN/FP). "
                "M2 과소추정율로 라벨 금지.\n")
        summary.to_csv(f, index=False)

    fig_path = figures / "rq3e_obsclass_eval_direct.png"
    _plot_direct(oc4, fig_path)

    for p in (p_oc4, p_byclass, p_conf, p_sum, fig_path):
        print(f"[out] {p}")

    print("\n=== DIRECT: M2 q99 과소추정율 (관측 기반) ===")
    print(oc4.to_string(index=False))
    print("\n=== SURROGATE: RF 분류기 오류율 (M2 평가 아님) ===")
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
