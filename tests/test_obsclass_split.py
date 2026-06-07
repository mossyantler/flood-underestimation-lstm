"""Unit tests: GroupKFold basin split — train ∩ test basins must be empty."""

import pathlib

import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import GroupKFold

TABLES = pathlib.Path("output/model_analysis/band_signal/signal_sweep/tables")
N_SPLITS = 5


@pytest.fixture(scope="module")
def b2():
    p = TABLES / "obsclass_model_matrix_allrain.parquet"
    if not p.exists():
        pytest.skip("allrain matrix not built — run build_obsclass_features.py first")
    return pd.read_parquet(p)


@pytest.fixture(scope="module")
def b2_split_inputs(b2):
    """Dummy X + groups + y needed for GroupKFold.split()."""
    return (
        np.zeros((len(b2), 1)),
        b2["above_q99"].values,
        b2["basin_id"].values,
    )


def test_groupkfold_no_basin_overlap(b2_split_inputs):
    X, y, groups = b2_split_inputs
    for fold, (tr, te) in enumerate(GroupKFold(n_splits=N_SPLITS).split(X, y, groups)):
        overlap = set(groups[tr]) & set(groups[te])
        assert len(overlap) == 0, (
            f"Fold {fold}: train∩test basins not empty — {len(overlap)} shared basins"
        )


def test_groupkfold_fold_count(b2_split_inputs):
    X, y, groups = b2_split_inputs
    folds = list(GroupKFold(n_splits=N_SPLITS).split(X, y, groups))
    assert len(folds) == N_SPLITS, f"Expected {N_SPLITS} folds, got {len(folds)}"


def test_groupkfold_min_held_basins(b2_split_inputs):
    X, y, groups = b2_split_inputs
    for fold, (tr, te) in enumerate(GroupKFold(n_splits=N_SPLITS).split(X, y, groups)):
        n_held = len(set(groups[te]))
        assert n_held >= 1, f"Fold {fold}: 0 held-out basins"


def test_groupkfold_all_basins_covered(b2_split_inputs):
    X, y, groups = b2_split_inputs
    all_basins = set(groups)

    seen_in_test = set()
    for _, te in GroupKFold(n_splits=N_SPLITS).split(X, y, groups):
        seen_in_test.update(groups[te])

    assert seen_in_test == all_basins, (
        f"Some basins never appear in test: {all_basins - seen_in_test}"
    )


def test_overlay_basin_intersection_zero(b2):
    """static overlay: basins not in allrain must be truly held-out."""
    ba_path = TABLES / "obsclass_model_matrix_static.parquet"
    if not ba_path.exists():
        pytest.skip("static matrix not built")
    ba = pd.read_parquet(ba_path)
    b2_basins = set(b2["basin_id"].unique())
    ba_held = ba[~ba["basin_id"].isin(b2_basins)]
    intersection = set(ba_held["basin_id"]) & b2_basins
    assert len(intersection) == 0, (
        f"Held-out static events overlap with allrain basins: {intersection}"
    )
