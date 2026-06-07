from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest


def load_direct_shap_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts/model/overall/compute_q99_lstm_direct_shap.py"
    spec = importlib.util.spec_from_file_location("direct_shap_test_module", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["direct_shap_test_module"] = module
    spec.loader.exec_module(module)
    return module


def load_direct_shap_analysis_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts/model/overall/analyze_quantile_lstm_direct_shap.py"
    spec = importlib.util.spec_from_file_location("direct_shap_analysis_test_module", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["direct_shap_analysis_test_module"] = module
    spec.loader.exec_module(module)
    return module


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
        out_dir / "data" / "quantile_lstm_direct_shap_metadata_smoke.json",
        out_dir / "report" / "quantile_lstm_direct_shap_method.html",
    ]
    for path in expected_files:
        assert path.exists(), f"missing expected smoke output: {path}"

    global_table = pd.read_csv(out_dir / "tables" / "quantile_lstm_direct_shap_global_feature_importance_smoke.csv")
    assert set(global_table["quantile"]) == {"q50", "q90", "q95", "q99"}
    static_importance = global_table.loc[global_table["feature_group"].eq("static_attribute"), "mean_abs_shap"]
    assert static_importance.gt(0).any()

    html = (out_dir / "report" / "quantile_lstm_direct_shap_method.html").read_text(encoding="utf-8")
    assert "q50/q90/q95/q99" in html
    assert "모델에 직접 SHAP" in html
    assert "대리 모델" in html
    assert "관측값을 입력으로 넣지 않는다" in html


def test_direct_shap_default_static_source_contains_model_inputs() -> None:
    module = load_direct_shap_module()

    static_frame = module.read_static(module.DEFAULT_STATIC_CSV)

    assert list(static_frame.columns) == ["basin", *module.STATIC_FEATURES]
    assert static_frame[module.STATIC_FEATURES].notna().all().all()


def test_direct_shap_default_output_targets_q99_peak_event_directory() -> None:
    module = load_direct_shap_module()

    assert module.DEFAULT_OUTPUT_DIR.relative_to(module.REPO_ROOT).as_posix() == "output/model_analysis/shap/q99"
    assert module.scope_default_output_dir("q99").relative_to(module.REPO_ROOT).as_posix() == "output/model_analysis/shap/q99"
    assert (
        module.scope_default_output_dir("test_split").relative_to(module.REPO_ROOT).as_posix()
        == "output/model_analysis/shap/test_split"
    )


def test_direct_shap_test_split_scope_uses_flow_stratified_anchor_table() -> None:
    module = load_direct_shap_module()

    event_csv = module.scope_default_event_csv("test_split")

    assert (
        event_csv.relative_to(module.REPO_ROOT).as_posix()
        == "output/model_analysis/shap/test_split/tables/flow_stratified_shap_anchor_samples_test_split.csv"
    )
    assert module.scope_default_max_events("test_split", 120) == 0
    assert module.scope_default_max_events("q99", 120) == 120


def test_direct_shap_analysis_default_input_targets_q99_peak_event_directory() -> None:
    module = load_direct_shap_analysis_module()

    assert module.DEFAULT_INPUT_DIR.relative_to(module.REPO_ROOT).as_posix() == "output/model_analysis/shap/q99"


def test_direct_shap_rejects_static_source_without_model_inputs(tmp_path: Path) -> None:
    module = load_direct_shap_module()
    bad_static = tmp_path / "static_attributes.csv"
    bad_static.write_text("gauge_id,drain_sqkm_attr,SLOPE_PCT\n01400000,10,2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing required model input columns"):
        module.read_static(bad_static)


def test_direct_shap_beeswarm_force_plotter_writes_artifacts(tmp_path: Path) -> None:
    analysis_dir = tmp_path / "direct_shap_analysis"
    tables_dir = analysis_dir / "tables"
    tables_dir.mkdir(parents=True)
    event_table = tables_dir / "quantile_lstm_direct_shap_event_feature_importance_seed111.csv"
    event_table.write_text(
        "\n".join(
            [
                "row_index,basin,event_id,anchor_time,quantile,quantile_prediction_normalized,feature_group,feature,feature_label_ko,mean_abs_shap,mean_signed_shap,max_abs_shap",
                "0,01400000,e0,2016-01-01,q99,1.2,dynamic_forcing,Rainf,강수량(Rainf),0.5,0.4,0.7",
                "0,01400000,e0,2016-01-01,q99,1.2,dynamic_forcing,Tair,기온(Tair),0.2,-0.1,0.3",
                "1,01400000,e1,2016-01-02,q99,0.8,dynamic_forcing,Rainf,강수량(Rainf),0.3,0.2,0.4",
                "1,01400000,e1,2016-01-02,q99,0.8,static_attribute,area,유역 면적(area),0.4,-0.3,0.4",
            ]
        ),
        encoding="utf-8",
    )

    cmd = [
        "uv",
        "run",
        "scripts/model/overall/plot_direct_shap_beeswarm_force.py",
        "--analysis-dir",
        str(analysis_dir),
        "--quantiles",
        "q99",
        "--top-n",
        "3",
    ]
    result = subprocess.run(cmd, cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr

    expected_files = [
        analysis_dir / "figures" / "quantile_lstm_direct_shap_bar_q99.png",
        analysis_dir / "figures" / "quantile_lstm_direct_shap_global_feature_importance_q99.png",
        analysis_dir / "figures" / "quantile_lstm_direct_shap_beeswarm_q99.png",
        analysis_dir / "figures" / "quantile_lstm_direct_shap_force_q99.png",
        analysis_dir / "figures" / "quantile_lstm_direct_shap_waterfall_q99.png",
        analysis_dir / "report" / "quantile_lstm_direct_shap_force_q99.html",
        analysis_dir / "data" / "quantile_lstm_direct_shap_beeswarm_force_manifest.json",
    ]
    for path in expected_files:
        assert path.exists(), f"missing expected beeswarm/force output: {path}"
