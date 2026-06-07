#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pandas>=2.2",
#   "pyarrow>=15",
# ]
# ///
"""Build obs_class feature matrices from signal_sweep branch CSVs.

Outputs (signal_sweep/tables/):
  obsclass_model_matrix_allrain.parquet  – 16 639 rows, primary training
  obsclass_model_matrix_static.parquet  –    926 rows, Q99-event overlay
  obsclass_model_matrix_noaa.parquet     –     57 rows, NOAA flood overlay
"""

import pathlib
import sys

import pandas as pd

TABLES = pathlib.Path("output/model_analysis/band_signal/signal_sweep/tables")

# S1: 독립 신호 (allrain 컬럼명 기준)
S1_FULL = [
    "area", "baseflow_index", "permeability", "crainf_frac_mean",
    "slope", "aridity", "soil_depth", "snow_fraction", "forest_fraction",
    "rain_sum_event", "rain_max_1h", "cape_max",
]
S1_STATIC = [
    "area", "baseflow_index", "permeability",
    "slope", "aridity", "soil_depth", "snow_fraction", "forest_fraction",
]
# S2: 밴드 결합 허위 신호 (ablation 전용)
S2_BAND = ["rel_width", "q99_q50_ratio"]

# forcing NOAA 컬럼명 → allrain 표기법으로 매핑
NOAA_COL_MAP = {
    "crainf_frac_mean_24h": "crainf_frac_mean",
    "rain_sum_24h": "rain_sum_event",
    "rain_max_1h_72h": "rain_max_1h",
    "cape_max_24h": "cape_max",
}


def _add_labels(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["above_q99"] = (df["oc"].round().astype(int) == 4).astype(int)
    df["oc_ordinal"] = df["oc"].round().astype(int)
    return df


def build_allrain() -> pd.DataFrame:
    src = TABLES / "features_allrain.csv"
    df = pd.read_csv(src, parse_dates=["peak_time"])

    missing = df[S1_FULL].isnull().sum()
    assert (missing == 0).all(), f"Missing values in allrain S1: {missing[missing > 0]}"
    missing_s2 = df[S2_BAND].isnull().sum()
    assert (missing_s2 == 0).all(), f"Missing in allrain S2: {missing_s2[missing_s2 > 0]}"

    forbidden = {"oc", "nws_class", "basin_id", "peak_time"}
    assert forbidden.isdisjoint(set(S1_FULL + S2_BAND)), "Target/ID cols in feature set"

    df = _add_labels(df)
    assert len(df) == 16639, f"Expected 16639 rows, got {len(df)}"

    keep = ["basin_id", "peak_time", "oc", "above_q99", "oc_ordinal"] + S1_FULL + S2_BAND
    return df[keep]


def build_static() -> pd.DataFrame:
    src = TABLES / "static_features_q99.csv"
    df = pd.read_csv(src, parse_dates=["peak_time"])
    df["oc"] = df["oc"].round().astype(int)

    available_s1 = [c for c in S1_FULL if c in df.columns]
    missing_s1 = [c for c in S1_FULL if c not in df.columns]
    available_s2 = [c for c in S2_BAND if c in df.columns]

    if available_s1:
        missing_vals = df[available_s1].isnull().sum()
        assert (missing_vals == 0).all(), f"Missing in static: {missing_vals[missing_vals > 0]}"

    df = _add_labels(df)
    assert len(df) == 926, f"Expected 926 rows, got {len(df)}"

    keep = ["basin_id", "peak_time", "oc", "above_q99", "oc_ordinal"] + available_s1 + available_s2
    result = df[keep].copy()
    result.attrs["available_s1"] = available_s1
    result.attrs["missing_s1"] = missing_s1
    return result


def build_noaa() -> pd.DataFrame:
    src = TABLES / "forcing_features_noaa.csv"
    df = pd.read_csv(src, parse_dates=["peak_time"])
    df = df.rename(columns=NOAA_COL_MAP)
    df["oc"] = df["oc"].round().astype(int)

    available_s1 = [c for c in S1_FULL if c in df.columns]
    missing_s1 = [c for c in S1_FULL if c not in df.columns]
    available_s2 = [c for c in S2_BAND if c in df.columns]

    if available_s1:
        missing_vals = df[available_s1].isnull().sum()
        assert (missing_vals == 0).all(), f"Missing in NOAA: {missing_vals[missing_vals > 0]}"

    df = _add_labels(df)
    assert len(df) == 57, f"Expected 57 rows, got {len(df)}"

    keep = ["basin_id", "peak_time", "oc", "above_q99", "oc_ordinal"] + available_s1 + available_s2
    result = df[keep].copy()
    result.attrs["available_s1"] = available_s1
    result.attrs["missing_s1"] = missing_s1
    return result


def main():
    TABLES.mkdir(parents=True, exist_ok=True)

    print("Building allrain matrix...")
    b2 = build_allrain()
    b2.to_parquet(TABLES / "obsclass_model_matrix_allrain.parquet", index=False)
    print(f"  shape={b2.shape}  above_q99={b2['above_q99'].sum()} ({b2['above_q99'].mean():.1%})")

    print("Building static matrix...")
    ba = build_static()
    ba.to_parquet(TABLES / "obsclass_model_matrix_static.parquet", index=False)
    print(f"  shape={ba.shape}")
    if ba.attrs.get("missing_s1"):
        print(f"  [note] S1 forcing cols absent in static (static only): {ba.attrs['missing_s1']}")

    print("Building NOAA matrix...")
    bn = build_noaa()
    bn.to_parquet(TABLES / "obsclass_model_matrix_noaa.parquet", index=False)
    print(f"  shape={bn.shape}")
    if bn.attrs.get("missing_s1"):
        print(f"  [note] S1 static attrs absent in NOAA (forcing only): {bn.attrs['missing_s1']}")

    print("\nDone: 3 matrices written.")
    return b2, ba, bn


if __name__ == "__main__":
    main()
