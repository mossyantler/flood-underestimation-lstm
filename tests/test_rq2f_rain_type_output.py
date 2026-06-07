"""Smoke tests for RQ-2f rain-type τ-output / α analysis.

검증 항목:
  1. SSOT 함수 ``crainf_median_split`` 호출(rq0/rq2f 단일 출처) — 2 그룹 분할.
  2. n-gate: 사건 수 n<10 셀이 suppress 되는지.
  3. 스크립트 소스에 SHAP value import가 없는지(결과 미사용 보장).
  4. (inputs 존재 시) main() end-to-end 산출물 생성.
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

import compute_rq2f_rain_type_output as rq2f  # noqa: E402
from expanded_drbc import CRAINF_SPLIT_LABELS, crainf_median_split  # noqa: E402

METRICS_DIR = REPO_ROOT / "output/model_analysis/primary/metrics"
FEAT_NOAA = (
    REPO_ROOT
    / "output/model_analysis/band_signal/signal_sweep/tables/forcing_features_noaa.csv"
)


def test_ssot_split_two_groups():
    """공용 함수가 중앙값 이분으로 두 라벨을 부여한다 (SSOT)."""
    s = pd.Series([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
    grp = crainf_median_split(s)
    assert list(pd.Categorical(grp).categories) == list(CRAINF_SPLIT_LABELS)
    counts = pd.Series(grp).value_counts()
    assert counts[CRAINF_SPLIT_LABELS[0]] == 3
    assert counts[CRAINF_SPLIT_LABELS[1]] == 3


def test_rq2f_imports_ssot_not_redefining():
    """rq2f가 _lib SSOT 함수를 그대로 참조한다."""
    assert rq2f.crainf_median_split is crainf_median_split


def test_n_gate_suppresses_small_cell():
    """n_events<10 셀은 suppress=True, 통계는 NaN."""
    rows = []
    # big cell: 12 events × 3 seeds (retained)
    for e in range(12):
        for seed in (111, 222, 444):
            rows.append(("CRainf (convective fraction)", "High CRainf (top 50%)",
                         f"080000{e:02d}", "2014-01-01 00:00:00", seed, "q99", 0.2))
    # small cell: 8 events × 3 seeds (suppressed — Flash-Flood-style n=8)
    for e in range(8):
        for seed in (111, 222, 444):
            rows.append(("CRainf (convective fraction)", "Low CRainf (bot. 50%)",
                         f"090000{e:02d}", "2014-01-01 00:00:00", seed, "q99", 0.5))
    merged = pd.DataFrame(rows, columns=[
        "split_axis", "rain_type", "basin_id", "peak_time", "seed", "tau",
        "peak_under_deficit"])
    agg = rq2f._aggregate(merged)

    big = agg[agg.rain_type == "High CRainf (top 50%)"].iloc[0]
    small = agg[agg.rain_type == "Low CRainf (bot. 50%)"].iloc[0]
    assert big["n_events"] == 12 and not big["suppressed"]
    assert np.isfinite(big["capture_median"]) and np.isfinite(big["alpha_median"])
    assert small["n_events"] == 8 and bool(small["suppressed"])
    assert np.isnan(small["capture_median"]) and np.isnan(small["alpha_median"])


def test_no_shap_import_in_source():
    """SHAP value 파일/모듈 import 금지 보장."""
    src = (SCRIPT_DIR / "compute_rq2f_rain_type_output.py").read_text(encoding="utf-8")
    code_lines = [ln for ln in src.splitlines() if not ln.lstrip().startswith("#")]
    code = "\n".join(code_lines)
    assert "import shap" not in code
    assert "shap_" not in code


@pytest.mark.skipif(
    not (METRICS_DIR / "tables/rq2_alpha_event_peak_deficit_noaa.csv").exists()
    or not FEAT_NOAA.exists(),
    reason="RQ-2f inputs not present — run run_all.py + signal_sweep first",
)
def test_main_end_to_end(tmp_path):
    """실제 입력으로 main() 실행 → 산출물 3개 + figure 생성, suppress 일관성."""
    out_metrics = tmp_path / "metrics"
    (out_metrics / "tables").mkdir(parents=True)
    # 입력 테이블 복사 (canonical alpha)
    src_alpha = METRICS_DIR / "tables/rq2_alpha_event_peak_deficit_noaa.csv"
    (out_metrics / "tables/rq2_alpha_event_peak_deficit_noaa.csv").write_text(
        src_alpha.read_text(encoding="utf-8"), encoding="utf-8")

    rc = rq2f.main(["--metrics-dir", str(out_metrics), "--feat-noaa", str(FEAT_NOAA)])
    assert rc == 0

    t = out_metrics / "tables"
    for name in ("rq2f_rain_type_tau_output.csv",
                 "rq2f_rain_type_alpha.csv",
                 "rq2f_rain_type_contrast.csv"):
        assert (t / name).exists(), f"missing output {name}"
    assert (out_metrics / "figures/rq2f_rain_type_patterns.png").exists()

    alpha = pd.read_csv(t / "rq2f_rain_type_alpha.csv", comment="#")
    # suppress된 행은 alpha_median NaN, 아닌 행은 finite
    assert ((alpha["suppressed"]) == (alpha["alpha_median"].isna())).all()
    # CRainf 축 두 그룹(High/Low) 모두 n>=10 → suppress 없어야 함
    cr = alpha[alpha.split_axis.str.startswith("CRainf")]
    assert (~cr["suppressed"]).all(), "CRainf 그룹(28/29)은 n-gate 통과해야 함"
