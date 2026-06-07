"""Smoke tests for RQ-3e obs_class model evaluation (DIRECT / surrogate 분리).

검증 항목:
  1. category error 방지: DIRECT/surrogate 산출이 라벨로 명확히 분리.
  2. surrogate 산출이 'forcing_surrogate'로만 라벨되고 'M2' 평가 라벨이 없음.
  3. DIRECT가 M1 NSE tier(top/mid/bottom) 분할을 포함.
  4. n-gate: tier 셀 n_events<10 suppress.
  5. (inputs 존재 시) main() end-to-end 산출물 5개 생성.
"""

import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "scripts/model/expanded_drbc"
LIB_DIR = REPO_ROOT / "scripts/_lib"
for p in (SCRIPT_DIR, LIB_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import compute_rq3e_obsclass_eval as rq3e  # noqa: E402

METRICS_DIR = REPO_ROOT / "output/model_analysis/primary/metrics"
SURROGATE_DIR = REPO_ROOT / "output/model_analysis/band_signal/signal_sweep/tables"

DIRECT_INPUTS = (
    METRICS_DIR / "tables/location_class_q99.csv",
    METRICS_DIR / "tables/location_class_noaa.csv",
    METRICS_DIR / "tables/rq4a_nse_tier_assignments.csv",
)
SURROGATE_INPUTS = (
    SURROGATE_DIR / "obsclass_confusion_ordinal.csv",
    SURROGATE_DIR / "obsclass_confusion_binary.csv",
)


def test_oc_definition_matches_allrain():
    """obs_class 서수 정의가 signal_sweep_allrain.py:63-67 과 일치."""
    assert rq3e.OC_ORDER == [
        "below_q50", "q50_to_q90", "q90_to_q95", "q95_to_q99", "above_q99"
    ]
    assert rq3e.OC_TO_INT["above_q99"] == 4
    assert rq3e.OC_TO_INT["below_q50"] == 0


@pytest.mark.skipif(
    not all(p.exists() for p in SURROGATE_INPUTS),
    reason="surrogate confusion inputs not present — run run_obsclass_pipeline first",
)
def test_surrogate_labeled_not_m2_eval():
    """surrogate 산출은 forcing_surrogate 라벨만, M2 평가 라벨 금지."""
    confusion, summary = rq3e._surrogate(SURROGATE_DIR)
    assert (confusion["evaluation_kind"] == "forcing_surrogate").all()
    assert (summary["evaluation_kind"] == "forcing_surrogate").all()
    # 'M2'/'underestimation' 라벨이 surrogate 컬럼/값에 새지 않아야 함
    joined = " ".join(map(str, summary.columns)) + " " + " ".join(map(str, summary.iloc[0].values))
    assert "m2_q99_underestimation" not in joined.lower()
    # FN/FP는 classifier_ 접두로만 노출
    assert "classifier_fn_rate" in summary.columns
    assert "classifier_fp_rate" in summary.columns


def test_n_gate_suppresses_small_tier(tmp_path, monkeypatch):
    """tier 셀 n_events<10 이면 suppress, 통계 NaN."""
    md = tmp_path / "metrics"
    (md / "tables").mkdir(parents=True)
    # tier: basinA=top(많은 사건), basinB=bottom(사건 8개<10)
    pd.DataFrame({"basin_id": ["00000001", "00000002"], "tier": ["top", "bottom"]}).to_csv(
        md / "tables/rq4a_nse_tier_assignments.csv", index=False)
    rows = []
    for e in range(12):  # top: 12 events
        rows.append(("00000001", 111, f"2014-01-{e+1:02d} 00:00:00", "above_q99"))
    for e in range(8):   # bottom: 8 events (<10 → suppress)
        rows.append(("00000002", 111, f"2015-01-{e+1:02d} 00:00:00", "below_q50"))
    loc = pd.DataFrame(rows, columns=["basin_id", "seed", "peak_time", "obs_class"])
    for scope in ("q99", "noaa"):
        with (md / f"tables/location_class_{scope}.csv").open("w") as f:
            f.write("# test\n")
            loc.to_csv(f, index=False)

    oc4, _ = rq3e._direct(md)
    bottom = oc4[(oc4.scope == "q99") & (oc4.m1_nse_tier == "bottom")].iloc[0]
    top = oc4[(oc4.scope == "q99") & (oc4.m1_nse_tier == "top")].iloc[0]
    assert bottom["n_events"] == 8 and bool(bottom["suppressed"])
    assert np.isnan(bottom["m2_q99_underestimation_rate"])
    assert top["n_events"] == 12 and not top["suppressed"]
    assert top["m2_q99_underestimation_rate"] == 1.0  # 모두 above_q99


@pytest.mark.skipif(
    not all(p.exists() for p in DIRECT_INPUTS + SURROGATE_INPUTS),
    reason="RQ-3e inputs not present — run run_all.py + run_obsclass_pipeline first",
)
def test_main_end_to_end(tmp_path):
    md = tmp_path / "metrics"
    (md / "tables").mkdir(parents=True)
    for p in DIRECT_INPUTS:
        (md / "tables" / p.name).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

    rc = rq3e.main(["--metrics-dir", str(md), "--surrogate-dir", str(SURROGATE_DIR)])
    assert rc == 0

    t = md / "tables"
    for name in ("rq3e_obsclass_eval_direct_oc4recall.csv",
                 "rq3e_obsclass_eval_direct_byclass.csv",
                 "rq3e_obsclass_eval_surrogate_confusion.csv",
                 "rq3e_obsclass_eval_surrogate_summary.csv"):
        assert (t / name).exists(), f"missing {name}"
    assert (md / "figures/rq3e_obsclass_eval_direct.png").exists()

    # DIRECT: M1 tier 분할 존재
    oc4 = pd.read_csv(t / "rq3e_obsclass_eval_direct_oc4recall.csv", comment="#")
    assert set(["top", "mid", "bottom"]).issubset(set(oc4["m1_nse_tier"]))
    # q99 scope ALL tier underestimation rate는 finite
    allrow = oc4[(oc4.scope == "q99") & (oc4.m1_nse_tier == "ALL")].iloc[0]
    assert np.isfinite(allrow["m2_q99_underestimation_rate"])
