from __future__ import annotations

import subprocess
from pathlib import Path

import pandas as pd


def test_direct_shap_smoke_writes_quantile_ladder_outputs(tmp_path: Path) -> None:
    out_dir = tmp_path / "direct_shap_smoke"
    cmd = [
        "uv",
        "run",
        "scripts/model/overall/compute_q99_lstm_direct_shap.py",
        "--smoke",
        "--output-dir",
        str(out_dir),
        "--max-events",
        "2",
        "--background-events",
        "2",
        "--shap-samples",
        "4",
    ]
    result = subprocess.run(cmd, cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr

    expected_files = [
        out_dir / "tables" / "quantile_lstm_direct_shap_global_feature_importance_smoke.csv",
        out_dir / "tables" / "quantile_lstm_direct_shap_event_feature_importance_smoke.csv",
        out_dir / "tables" / "quantile_lstm_direct_shap_temporal_lag_smoke.csv",
        out_dir / "metadata" / "quantile_lstm_direct_shap_metadata_smoke.json",
        out_dir / "report" / "quantile_lstm_direct_shap_method.html",
    ]
    for path in expected_files:
        assert path.exists(), f"missing expected smoke output: {path}"

    global_table = pd.read_csv(out_dir / "tables" / "quantile_lstm_direct_shap_global_feature_importance_smoke.csv")
    assert set(global_table["quantile"]) == {"q50", "q90", "q95", "q99"}

    html = (out_dir / "report" / "quantile_lstm_direct_shap_method.html").read_text(encoding="utf-8")
    assert "q50/q90/q95/q99" in html
    assert "모델에 직접 SHAP" in html
    assert "대리 모델" in html
    assert "관측값을 입력으로 넣지 않는다" in html
