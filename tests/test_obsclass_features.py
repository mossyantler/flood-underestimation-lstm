"""Unit tests: feature matrix construction for obs_class classifier."""

import pathlib

import pandas as pd
import pytest

TABLES = pathlib.Path("output/model_analysis/band_signal/signal_sweep/tables")

S1_FULL = [
    "area", "baseflow_index", "permeability", "crainf_frac_mean",
    "slope", "aridity", "soil_depth", "snow_fraction", "forest_fraction",
    "rain_sum_event", "rain_max_1h", "cape_max",
]
FORBIDDEN_COLS = {"basin_id", "oc", "nws_class", "peak_time"}


@pytest.fixture(scope="module")
def b2():
    p = TABLES / "obsclass_model_matrix_allrain.parquet"
    if not p.exists():
        pytest.skip("allrain matrix not built — run build_obsclass_features.py first")
    return pd.read_parquet(p)


@pytest.fixture(scope="module")
def ba():
    p = TABLES / "obsclass_model_matrix_static.parquet"
    if not p.exists():
        pytest.skip("static matrix not built")
    return pd.read_parquet(p)


@pytest.fixture(scope="module")
def bn():
    p = TABLES / "obsclass_model_matrix_noaa.parquet"
    if not p.exists():
        pytest.skip("NOAA matrix not built")
    return pd.read_parquet(p)


def test_b2_row_count(b2):
    assert len(b2) == 16639, f"Expected 16639, got {len(b2)}"


def test_ba_row_count(ba):
    assert len(ba) == 926, f"Expected 926, got {len(ba)}"


def test_bn_row_count(bn):
    assert len(bn) == 57, f"Expected 57, got {len(bn)}"


def test_b2_s1_no_missing(b2):
    avail = [c for c in S1_FULL if c in b2.columns]
    missing = b2[avail].isnull().sum()
    assert (missing == 0).all(), f"Missing values in allrain S1: {missing[missing > 0]}"


def test_b2_no_target_leakage(b2):
    feature_cols = set(c for c in S1_FULL if c in b2.columns)
    leaked = feature_cols & FORBIDDEN_COLS
    assert len(leaked) == 0, f"Target/ID cols in feature set: {leaked}"


def test_binary_label_values(b2):
    assert set(b2["above_q99"].unique()).issubset({0, 1}), \
        f"above_q99 has unexpected values: {b2['above_q99'].unique()}"


def test_ordinal_label_values(b2):
    assert set(b2["oc_ordinal"].unique()).issubset({0, 1, 2, 3, 4}), \
        f"oc_ordinal out of range: {b2['oc_ordinal'].unique()}"


def test_binary_label_consistency(b2):
    expected = (b2["oc_ordinal"] == 4).astype(int)
    assert (b2["above_q99"] == expected).all(), \
        "above_q99 label does not match oc_ordinal == 4"


def test_ba_has_static_features(ba):
    static = ["area", "slope", "aridity", "baseflow_index"]
    for col in static:
        assert col in ba.columns, f"static missing static feature: {col}"


def test_basin_id_present_as_group_key(b2):
    assert "basin_id" in b2.columns, "basin_id must be kept as group key"
    assert b2["basin_id"].nunique() > 1, "Expected multiple basins in allrain"
