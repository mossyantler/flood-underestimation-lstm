from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


def load_direction_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts/model/overall/analyze_shap_direction_patterns.py"
    assert module_path.exists(), f"missing implementation module: {module_path}"
    spec = importlib.util.spec_from_file_location("shap_direction_analysis_test_module", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["shap_direction_analysis_test_module"] = module
    spec.loader.exec_module(module)
    return module


def base_event_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "scope": "q99",
                "seed": 111,
                "event_id": "dup-event",
                "event_start": "2016-01-01 00:00:00",
                "event_end": "2016-01-02 00:00:00",
                "row_index": 0,
                "basin": "1414000",
                "anchor_time": "2016-01-02 00:00:00",
                "quantile": "q99",
                "feature_group": "static_attribute",
                "feature": "area",
                "feature_label_ko": "유역 면적(area)",
                "mean_abs_shap": 0.5,
                "mean_signed_shap": 0.3,
                "max_abs_shap": 0.6,
                "flow_stratum": "extreme_q99",
            },
            {
                "scope": "q99",
                "seed": 222,
                "event_id": "dup-event",
                "event_start": "2016-01-03 00:00:00",
                "event_end": "2016-01-04 00:00:00",
                "row_index": 1,
                "basin": "01415000",
                "anchor_time": "2016-01-04 00:00:00",
                "quantile": "q99",
                "feature_group": "static_attribute",
                "feature": "area",
                "feature_label_ko": "유역 면적(area)",
                "mean_abs_shap": 0.4,
                "mean_signed_shap": -0.2,
                "max_abs_shap": 0.5,
                "flow_stratum": "extreme_q99",
            },
        ]
    )


def static_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"gauge_id": "01414000", "area": 10.0, "slope": 1.0, "aridity": 0.7, "snow_fraction": 0.0, "soil_depth": 1.0, "permeability": 2.0, "baseflow_index": 0.4, "forest_fraction": 0.5},
            {"gauge_id": "01415000", "area": 30.0, "slope": 3.0, "aridity": 0.9, "snow_fraction": 0.1, "soil_depth": 2.0, "permeability": 4.0, "baseflow_index": 0.6, "forest_fraction": 0.7},
        ]
    )


def forcing_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "basin": "1414000",
                "seed": 111,
                "event_id": "dup-event",
                "event_start": "2016-01-01 00:00:00",
                "event_end": "2016-01-02 00:00:00",
                "event_total_rainf": 10.0,
                "event_peak_rainf_intensity": 2.0,
                "event_duration_h": 12,
                "antecedent_rainf_5d": 4.0,
                "event_mean_cape": 50.0,
                "event_max_cape": 120.0,
                "antecedent_tair_mean": 2.5,
            }
        ]
    )


def test_normalizes_basin_ids_for_static_join() -> None:
    module = load_direction_module()

    assert module.normalize_basin_id(1414000) == "01414000"
    assert module.normalize_basin_id("01415000") == "01415000"


def test_uses_composite_event_key_not_event_id_only() -> None:
    module = load_direction_module()

    matrix, issues = module.build_direction_event_feature_matrix(
        event_shap=base_event_rows(),
        static_attributes=static_rows(),
        q99_forcing=forcing_rows(),
    )

    assert len(matrix) == 2
    matched = matrix.loc[matrix["seed"].eq(111)].iloc[0]
    unmatched = matrix.loc[matrix["seed"].eq(222)].iloc[0]
    assert matched["event_forcing_scope"] == "q99_matched"
    assert matched["event_forcing_summary_total_rainf"] == 10.0
    assert unmatched["event_forcing_scope"] == "q99_missing"
    assert pd.isna(unmatched["event_forcing_summary_total_rainf"])
    assert "duplicate_composite_key" in set(issues["issue_type"]) or not issues["issue_type"].eq("event_id_only_join_used").any()


def test_assigns_feature_value_signed_shap_quadrants() -> None:
    module = load_direction_module()

    matrix, _issues = module.build_direction_event_feature_matrix(
        event_shap=base_event_rows(),
        static_attributes=static_rows(),
        q99_forcing=forcing_rows(),
    )
    summary = module.build_quadrant_summary(matrix)

    labels = set(summary["quadrant_label"])
    assert "feature_low_shap_positive" in labels
    assert "feature_high_shap_negative" in labels


def test_blocks_type_label_when_support_is_low() -> None:
    module = load_direction_module()
    weak_summary = pd.DataFrame(
        [
            {
                "scope": "q99",
                "feature": "area",
                "quadrant_label": "feature_high_shap_positive",
                "n_events": 3,
                "n_seeds": 1,
                "abs_shap_outlier_share": 0.1,
                "test_split_direction_conflict": False,
            }
        ]
    )

    candidates = module.build_type_candidates(weak_summary)

    assert candidates.loc[0, "candidate_label_ko"] == ""
    assert candidates.loc[0, "insufficient_support"] is True


def test_separates_input_shap_from_event_forcing_summary() -> None:
    module = load_direction_module()
    event_shap = pd.concat(
        [
            base_event_rows().head(1),
            pd.DataFrame(
                [
                    {
                        "scope": "test_split",
                        "seed": 111,
                        "event_id": "ts-event",
                        "event_end": "2016-02-01 00:00:00",
                        "row_index": 3,
                        "basin": "1414000",
                        "anchor_time": "2016-02-01 00:00:00",
                        "quantile": "q99",
                        "feature_group": "dynamic_forcing",
                        "feature": "Rainf",
                        "feature_label_ko": "강수량(Rainf)",
                        "mean_abs_shap": 0.7,
                        "mean_signed_shap": -0.4,
                        "max_abs_shap": 0.8,
                        "flow_stratum": "high",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    matrix, _issues = module.build_direction_event_feature_matrix(
        event_shap=event_shap,
        static_attributes=static_rows(),
        q99_forcing=forcing_rows(),
    )
    test_split_row = matrix.loc[matrix["scope"].eq("test_split")].iloc[0]
    q99_row = matrix.loc[matrix["scope"].eq("q99")].iloc[0]

    assert test_split_row["event_forcing_scope"] == "not_applicable_test_split"
    assert pd.isna(test_split_row["event_forcing_summary_total_rainf"])
    assert test_split_row["feature_value_source"] == "not_available_dynamic"
    assert test_split_row["feature_value_band"] == "not_applicable_dynamic"
    assert q99_row["event_forcing_scope"] == "q99_matched"
    assert set(matrix.columns).isdisjoint({"input_feature_shap_mean_abs", "event_total_rainf"})


def test_records_timestamp_fallback_when_event_end_missing() -> None:
    module = load_direction_module()
    event_shap = base_event_rows().head(1).copy()
    event_shap.loc[0, "event_end"] = pd.NA

    _matrix, issues = module.build_direction_event_feature_matrix(
        event_shap=event_shap,
        static_attributes=static_rows(),
        q99_forcing=forcing_rows(),
    )

    assert "timestamp_fallback_used" in set(issues["issue_type"])


def test_quadrant_summary_exposes_nonzero_share_for_heatmap() -> None:
    module = load_direction_module()

    matrix, _issues = module.build_direction_event_feature_matrix(
        event_shap=base_event_rows(),
        static_attributes=static_rows(),
        q99_forcing=forcing_rows(),
    )
    summary = module.build_quadrant_summary(matrix)

    assert "event_share" in summary.columns
    assert summary["event_share"].between(0.0, 1.0).all()
    assert summary["event_share"].gt(0.0).any()


def test_rainfall_summary_has_feature_centered_delta() -> None:
    module = load_direction_module()
    repeated = pd.concat([base_event_rows(), base_event_rows()], ignore_index=True)
    repeated.loc[2, "feature"] = "Rainf"
    repeated.loc[2, "feature_group"] = "dynamic_forcing"
    repeated.loc[2, "mean_signed_shap"] = 0.01
    repeated.loc[3, "feature"] = "Rainf"
    repeated.loc[3, "feature_group"] = "dynamic_forcing"
    repeated.loc[3, "mean_signed_shap"] = 0.07
    forcing = forcing_rows()
    forcing = pd.concat(
        [
            forcing,
            forcing.assign(
                basin="01415000",
                seed=222,
                event_start="2016-01-03 00:00:00",
                event_end="2016-01-04 00:00:00",
                event_duration_h=48,
                event_peak_rainf_intensity=0.5,
                event_total_rainf=20.0,
            ),
        ],
        ignore_index=True,
    )
    matrix, _issues = module.build_direction_event_feature_matrix(
        event_shap=repeated,
        static_attributes=static_rows(),
        q99_forcing=forcing,
    )

    summary = module.build_rainfall_regime_summary(matrix)

    assert "median_signed_shap_delta_from_feature_median" in summary.columns
    assert summary["median_signed_shap_delta_from_feature_median"].abs().gt(0.0).any()


def test_report_includes_figures_and_interpretation(tmp_path: Path) -> None:
    module = load_direction_module()
    out_dir = tmp_path / "direction"
    for subdir in ["report", "figures"]:
        (out_dir / subdir).mkdir(parents=True)
    scope_summary = pd.DataFrame(
        [
            {"scope": "q99", "quantile": "q99", "feature_group": "static_attribute", "feature": "area", "mean_abs_shap_mean": 0.15, "mean_signed_shap_mean": -0.02},
            {"scope": "test_split", "quantile": "q99", "feature_group": "static_attribute", "feature": "area", "mean_abs_shap_mean": 0.54, "mean_signed_shap_mean": 0.02},
        ]
    )
    quadrant = pd.DataFrame(
        [
            {"scope": "q99", "quantile": "q99", "feature": "area", "quadrant_label": "feature_high_shap_negative", "event_share": 0.43, "median_signed_shap": -0.08, "n_events": 42, "abs_shap_outlier_share": 0.07},
            {"scope": "q99", "quantile": "q99", "feature": "area", "quadrant_label": "feature_high_shap_positive", "event_share": 0.39, "median_signed_shap": 0.11, "n_events": 38, "abs_shap_outlier_share": 0.10},
        ]
    )
    rainfall = pd.DataFrame(
        [
            {"rainfall_regime": "convective_cape", "quantile": "q99", "feature": "area", "median_signed_shap": -0.19, "median_signed_shap_delta_scaled": -1.0, "n_rows": 3},
            {"rainfall_regime": "convective_cape", "quantile": "q99", "feature": "Rainf", "median_signed_shap": 0.001, "median_signed_shap_delta_scaled": 1.0, "n_rows": 3},
        ]
    )
    seed = pd.DataFrame(
        [
            {"scope": "q99", "quantile": "q99", "feature": "area", "seed": 111, "dominant_sign": "negative"},
            {"scope": "q99", "quantile": "q99", "feature": "area", "seed": 222, "dominant_sign": "negative"},
        ]
    )

    module.write_report(out_dir, scope_summary, quadrant, rainfall, seed)

    report = (out_dir / "report" / "direction_analysis_report.md").read_text(encoding="utf-8")
    assert "![q99 범위별 중요도]" in report
    assert "![q99 사분면별 사건 비율]" in report
    assert "q99에서는 정적 유역 속성이 대부분의 설명력을 차지" in report
    assert "지표끼리 절대 크기를 비교하는 그림이 아니라 강우 양상 안에서 방향이 달라지는지" in report
    assert "정적 유역 속성별 상세 해석" in report
    assert "유역 면적(area)" in report
    assert "강우 양상별 상세 해석" in report
    assert "대류 가능성 큼" in report
    assert "종합 해석" in report
    assert "이 결과는 q99 출력이 단순히 비가 많이 온 시점을 따라간다기보다" in report
    assert "논문에서 바로 주장해도 되는 것" in report
    assert "아직 주장하면 안 되는 것" in report
    assert "Bar chart:" not in report
    assert "Rainfall regime:" not in report
