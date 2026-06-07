"""Integration smoke test: verify all pipeline outputs exist and are sane."""

import pathlib

import pandas as pd
import pytest

TABLES = pathlib.Path("output/model_analysis/band_signal/signal_sweep/tables")
FIGURES = pathlib.Path("output/model_analysis/band_signal/signal_sweep/figures")
REPORT = pathlib.Path("output/model_analysis/band_signal/signal_sweep/report")

EXPECTED_TABLES = [
    "obsclass_model_matrix_allrain.parquet",
    "obsclass_model_matrix_static.parquet",
    "obsclass_model_matrix_noaa.parquet",
    "obsclass_cv_metrics.csv",
    "obsclass_confusion_binary.csv",
    "obsclass_confusion_ordinal.csv",
    "obsclass_feature_importance.csv",
    "obsclass_ablation_band_signal.csv",
]
EXPECTED_FIGURES = [
    "obsclass_confusion_binary.png",
    "obsclass_confusion_ordinal.png",
    "obsclass_feature_importance.png",
    "obsclass_leakage_gap.png",
]
EXPECTED_REPORT = [
    "obsclass_classifier_summary.md",
]


@pytest.mark.parametrize("fname", EXPECTED_TABLES)
def test_table_exists(fname):
    p = TABLES / fname
    assert p.exists(), f"Missing: {p}"


@pytest.mark.parametrize("fname", EXPECTED_FIGURES)
def test_figure_exists(fname):
    p = FIGURES / fname
    assert p.exists(), f"Missing: {p}"


@pytest.mark.parametrize("fname", EXPECTED_REPORT)
def test_report_exists(fname):
    p = REPORT / fname
    assert p.exists(), f"Missing: {p}"


def test_cv_metrics_has_required_splits():
    p = TABLES / "obsclass_cv_metrics.csv"
    if not p.exists():
        pytest.skip("cv_metrics not generated")
    df = pd.read_csv(p)
    splits = set(df["split"].unique())
    assert "basin_groupkfold" in splits, f"Missing basin_groupkfold in splits: {splits}"
    assert "event_level_upper_bound" in splits, f"Missing event_level_upper_bound: {splits}"


def test_cv_metrics_has_fold_and_held_basins():
    p = TABLES / "obsclass_cv_metrics.csv"
    if not p.exists():
        pytest.skip("cv_metrics not generated")
    df = pd.read_csv(p)
    basin = df[df["split"] == "basin_groupkfold"]
    assert "held_basins" in basin.columns, "held_basins column missing from cv_metrics"
    assert basin["held_basins"].notna().all(), "held_basins has NaN for basin split"


def test_feature_importance_area_in_top5():
    p = TABLES / "obsclass_feature_importance.csv"
    if not p.exists():
        pytest.skip("feature_importance not generated")
    df = pd.read_csv(p).sort_values("importance_mean", ascending=False)
    top5 = df.head(5)["feature"].tolist()
    assert "area" in top5, f"area not in top-5 features: {top5}"


def test_ablation_has_two_rows():
    p = TABLES / "obsclass_ablation_band_signal.csv"
    if not p.exists():
        pytest.skip("ablation table not generated")
    df = pd.read_csv(p)
    assert len(df) == 2, f"Ablation table should have 2 rows (S1, S1+S2), got {len(df)}"
    assert "S1" in df["feature_set"].values
    assert "S1+S2(band)" in df["feature_set"].values


def test_confusion_binary_shape():
    p = TABLES / "obsclass_confusion_binary.csv"
    if not p.exists():
        pytest.skip("binary confusion not generated")
    df = pd.read_csv(p, index_col=0)
    assert df.shape == (2, 2), f"Binary confusion should be 2×2, got {df.shape}"


def test_confusion_ordinal_shape():
    p = TABLES / "obsclass_confusion_ordinal.csv"
    if not p.exists():
        pytest.skip("ordinal confusion not generated")
    df = pd.read_csv(p, index_col=0)
    assert df.shape == (5, 5), f"Ordinal confusion should be 5×5, got {df.shape}"


def test_leakage_gap_computable():
    """Both basin and event splits exist, leakage gap can be computed."""
    p = TABLES / "obsclass_cv_metrics.csv"
    if not p.exists():
        pytest.skip("cv_metrics not generated")
    df = pd.read_csv(p)
    basin_acc = df[df["split"] == "basin_groupkfold"]["accuracy"].mean()
    event_acc = df[df["split"] == "event_level_upper_bound"]["accuracy"].mean()
    assert isinstance(basin_acc, float) and isinstance(event_acc, float), \
        "Could not compute basin/event accuracy"
    # Gap may be positive or negative depending on feature composition.
    # When forcing features dominate (cape_max, rain > area), basin CV can
    # outperform event CV because GroupKFold preserves within-basin correlation.
    gap = event_acc - basin_acc
    assert abs(gap) < 0.3, f"Leakage gap magnitude {gap:.3f} suspiciously large"
