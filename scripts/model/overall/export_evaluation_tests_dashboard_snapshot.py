#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "duckdb>=1.1",
#   "pandas>=2.2",
# ]
# ///
"""Export dashboard snapshot for first, extreme-rain, and confirmed-flood tests."""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
OUT_TS = ROOT / "dashboard/lib/evaluation-tests-data.ts"
DUCKDB_PATH = ROOT / "database/local/duckdb/camels.duckdb"

SOURCES = {
    "expandedManifest": "configs/basin_splits/drbc_expanded_observed_test/manifest.csv",
    "expandedFirstSummary": "output/model_analysis/expanded/expanded_drbc_test/tables/primary_summary_by_seed.csv",
    "expandedFirstRunner": "scripts/runs/official/run_expanded_drbc_test_evaluation.sh",
    "extremeRainPrimaryLong": "output/model_analysis/legacy/extreme_rain/primary/analysis/extreme_rain_stress_error_table_long.csv",
    "extremeRainRunner": "scripts/runs/official/run_subset300_extreme_rain_stress_test.sh",
    "confirmedFloodPerformance": "output/model_analysis/expanded/confirmed_flood/performance/drbc_confirmed_flood_performance.csv",
    "confirmedFloodCatalog": "output/model_analysis/expanded/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv",
    "confirmedFloodHydrographs": "output/model_analysis/expanded/confirmed_flood/hydrographs/confirmed_flood_hydrograph_manifest.csv",
}


def rel_path(key: str) -> Path:
    return ROOT / SOURCES[key]


def read_csv(key: str, **kwargs: Any) -> pd.DataFrame:
    path = rel_path(key)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, **kwargs)


def query_duckdb(sql: str) -> pd.DataFrame:
    if not DUCKDB_PATH.exists():
        return pd.DataFrame()
    try:
        with duckdb.connect(str(DUCKDB_PATH), read_only=True) as con:
            return con.execute(sql).fetchdf()
    except Exception:
        return pd.DataFrame()


def clean_number(value: Any, digits: int | None = None) -> float | int | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    if digits is not None:
        return round(number, digits)
    return number


def clean_records(df: pd.DataFrame, columns: list[str], *, max_rows: int | None = None) -> list[dict[str, Any]]:
    if df.empty:
        return []
    out = df.loc[:, [col for col in columns if col in df.columns]].copy()
    if max_rows is not None:
        out = out.head(max_rows)
    return json.loads(out.to_json(orient="records", force_ascii=False))


def selected_expanded_basin_count() -> int:
    manifest = read_csv("expandedManifest")
    if manifest.empty or "selected_for_expanded_drbc_test" not in manifest.columns:
        return 0
    return int(manifest["selected_for_expanded_drbc_test"].astype(bool).sum())


def first_test(expanded_basins: int) -> dict[str, Any]:
    summary = query_duckdb("SELECT * FROM camels_csv.expanded_drbc_primary_summary")
    if summary.empty:
        summary = read_csv("expandedFirstSummary")
    seeds = sorted(int(seed) for seed in summary.get("seed", pd.Series(dtype=int)).dropna().unique())
    models = sorted(str(model) for model in summary.get("model", pd.Series(dtype=str)).dropna().unique())
    evaluated_basins = int(summary["n_basins"].max()) if "n_basins" in summary and not summary.empty else 0
    expected_rows = 2 * 3
    is_complete = (
        expanded_basins > 0
        and evaluated_basins >= expanded_basins
        and len(seeds) >= 3
        and {"model1", "model2"}.issubset(set(models))
        and len(summary) >= expected_rows
    )
    if not summary.empty:
        summary = summary.sort_values(["model", "seed"])
    return {
        "id": "first",
        "label": "First test",
        "route": "/experiment/test-matrix",
        "status": "ready" if is_complete else "needs-expanded-rerun",
        "basis": "expanded DRBC observed test",
        "coverage": f"{evaluated_basins}/{expanded_basins} basins" if expanded_basins else f"{evaluated_basins} basins",
        "primarySource": SOURCES["expandedFirstSummary"],
        "runner": SOURCES["expandedFirstRunner"],
        "summary": {
            "expandedBasins": expanded_basins,
            "evaluatedBasins": evaluated_basins,
            "seeds": seeds,
            "models": models,
            "rows": int(len(summary)),
        },
        "rows": clean_records(
            summary,
            ["model", "seed", "epoch", "n_basins", "median_NSE", "median_KGE", "median_FHV", "median_Peak_MAPE"],
        ),
        "interpretation": (
            "Expanded observed DRBC split으로 다시 평가해야 primary claim과 basin universe가 맞는다."
            if not is_complete
            else "Expanded observed DRBC split 기준 first test summary가 준비됐다."
        ),
    }


def extreme_test(expanded_basins: int) -> dict[str, Any]:
    long_df = query_duckdb("SELECT * FROM camels_csv.extreme_rain_stress_long_primary")
    if long_df.empty:
        long_df = read_csv("extremeRainPrimaryLong")
    events = int(long_df["event_id"].nunique()) if "event_id" in long_df else 0
    basins = int(long_df["gauge_id"].nunique()) if "gauge_id" in long_df else 0
    seeds = sorted(int(seed) for seed in long_df.get("seed", pd.Series(dtype=int)).dropna().unique())
    predictor_count = int(long_df["predictor"].nunique()) if "predictor" in long_df else 0
    expanded_complete = expanded_basins > 0 and basins >= expanded_basins
    return {
        "id": "extreme",
        "label": "Extreme test",
        "route": "/analysis/stress",
        "status": "needs-expanded-rerun" if not expanded_complete else "ready",
        "basis": "expanded DRBC extreme-rain stress",
        "coverage": f"{basins}/{expanded_basins} basins" if expanded_basins else f"{basins} basins",
        "primarySource": SOURCES["extremeRainPrimaryLong"],
        "runner": SOURCES["extremeRainRunner"],
        "summary": {
            "expandedBasins": expanded_basins,
            "currentBasins": basins,
            "events": events,
            "seeds": seeds,
            "predictorCount": predictor_count,
        },
        "rows": [],
        "interpretation": (
            "현재 stress table은 기존 primary/all 계열이다. Expanded basin universe로 stress catalog와 inference를 다시 만든 뒤 dashboard 공식값으로 승격한다."
            if not expanded_complete
            else "Expanded basin universe 기준 extreme-rain stress result가 준비됐다."
        ),
    }


def confirmed_test() -> dict[str, Any]:
    perf = query_duckdb("SELECT * FROM camels_csv.drbc_confirmed_flood_performance")
    if perf.empty:
        perf = read_csv("confirmedFloodPerformance")
    catalog = read_csv("confirmedFloodCatalog")
    hydro = read_csv("confirmedFloodHydrographs")
    events = int(perf["event_id"].nunique()) if "event_id" in perf else 0
    basins = int(perf["usgs_id"].nunique()) if "usgs_id" in perf else 0
    seeds = sorted(int(seed) for seed in perf.get("seed", pd.Series(dtype=int)).dropna().unique())
    m1 = perf[(perf.get("model") == "model1") & (perf.get("quantile") == "det")] if not perf.empty else pd.DataFrame()
    q99 = perf[(perf.get("model") == "model2") & (perf.get("quantile") == "q99")] if not perf.empty else pd.DataFrame()
    return {
        "id": "confirmed",
        "label": "Confirmed flood test",
        "route": "/analysis/confirmed-flood",
        "status": "ready" if events and basins else "missing",
        "basis": "NWS flood-stage confirmed events",
        "coverage": f"{events} events / {basins} basins",
        "primarySource": SOURCES["confirmedFloodPerformance"],
        "runner": "scripts/model/confirmed_flood/export_confirmed_flood_dashboard_snapshot.py",
        "summary": {
            "events": events,
            "basins": basins,
            "catalogEvents": int(catalog["event_id"].nunique()) if "event_id" in catalog else int(len(catalog)),
            "hydrographs": int(len(hydro)) if not hydro.empty else 0,
            "seeds": seeds,
            "m1MedianUnder": clean_number(m1["peak_under_deficit"].median(), 3) if "peak_under_deficit" in m1 else None,
            "q99MedianUnder": clean_number(q99["peak_under_deficit"].median(), 3) if "peak_under_deficit" in q99 else None,
        },
        "rows": [],
        "interpretation": "NWS flood-stage 초과 event 기준. First/extreme와 달리 이미 expanded DRBC flood-stage universe에서 독립 test layer로 사용한다.",
    }


def main() -> None:
    expanded_basins = selected_expanded_basin_count()
    snapshot = {
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "sources": SOURCES,
        "tests": [first_test(expanded_basins), extreme_test(expanded_basins), confirmed_test()],
    }
    OUT_TS.parent.mkdir(parents=True, exist_ok=True)
    OUT_TS.write_text(
        "// Generated by scripts/model/overall/export_evaluation_tests_dashboard_snapshot.py\n"
        "// Do not edit values by hand. Regenerate after expanded first/extreme reruns.\n\n"
        "export const evaluationTestsSnapshot = "
        + json.dumps(snapshot, ensure_ascii=False, indent=2)
        + " as const;\n\n"
        "export type EvaluationTest = (typeof evaluationTestsSnapshot.tests)[number];\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_TS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
