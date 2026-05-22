from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

import scripts.model.confirmed_flood.analyze_confirmed_flood_stratified_underestimation as M


def _make_perf_df(
    events: list[dict],
    seeds: list[int] = (111,),
) -> pd.DataFrame:
    """Build a raw performance-style DataFrame for testing."""
    rows = []
    for ev in events:
        for seed in seeds:
            for q, pred_col in M.QUANTILE_MAP.items():
                rows.append({
                    "event_id": ev["event_id"],
                    "usgs_id": ev["usgs_id"],
                    "seed": seed,
                    "flood_tier": ev["flood_tier"],
                    "noaa_corroborated": ev.get("noaa_corroborated", False),
                    "quantile": q,
                    "obs_peak_cms": ev["obs"],
                    "pred_peak_cms": ev["preds"][pred_col],
                })
    return pd.DataFrame(rows)


class TestLoadPerformance(unittest.TestCase):
    def test_pivot_shape(self) -> None:
        events = [
            {"event_id": "e1", "usgs_id": "b1", "flood_tier": "minor",
             "obs": 100.0, "preds": {p: 80.0 for p in M.PRED_COLS}},
            {"event_id": "e2", "usgs_id": "b1", "flood_tier": "major",
             "obs": 200.0, "preds": {p: 150.0 for p in M.PRED_COLS}},
        ]
        raw = _make_perf_df(events, seeds=[111, 222])
        result = M.load_performance.__wrapped__(raw, seeds=[111, 222]) if hasattr(
            M.load_performance, "__wrapped__") else None

        # Test via the full pipeline instead
        import tempfile, pathlib, csv
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, newline="") as f:
            raw.to_csv(f, index=False)
            tmp_path = pathlib.Path(f.name)
        result = M.load_performance(tmp_path, seeds=[111, 222])
        # 2 events x 2 seeds = 4 rows
        self.assertEqual(len(result), 4)
        for col in M.PRED_COLS:
            self.assertIn(col, result.columns)
        self.assertIn("obs", result.columns)


class TestAssignStrata(unittest.TestCase):
    def _make_wide(self) -> pd.DataFrame:
        rows = [
            {"event_id": "e1", "usgs_id": "b1", "seed": 111,
             "flood_tier": "minor", "noaa_corroborated": False,
             "obs": 100.0, **{p: 80.0 for p in M.PRED_COLS}},
            {"event_id": "e2", "usgs_id": "b1", "seed": 111,
             "flood_tier": "moderate", "noaa_corroborated": True,
             "obs": 200.0, **{p: 150.0 for p in M.PRED_COLS}},
            {"event_id": "e3", "usgs_id": "b1", "seed": 111,
             "flood_tier": "major", "noaa_corroborated": True,
             "obs": 500.0, **{p: 400.0 for p in M.PRED_COLS}},
        ]
        return pd.DataFrame(rows)

    def test_all_stratum_has_all_events(self) -> None:
        df = self._make_wide()
        long = M.assign_strata(df)
        self.assertEqual(len(long[long["stratum"] == "all"]), 3)

    def test_major_plus_has_one_event(self) -> None:
        df = self._make_wide()
        long = M.assign_strata(df)
        self.assertEqual(len(long[long["stratum"] == "major_plus"]), 1)

    def test_moderate_plus_has_two_events(self) -> None:
        df = self._make_wide()
        long = M.assign_strata(df)
        self.assertEqual(len(long[long["stratum"] == "moderate_plus"]), 2)

    def test_noaa_corroborated_has_two_events(self) -> None:
        df = self._make_wide()
        long = M.assign_strata(df)
        self.assertEqual(len(long[long["stratum"] == "noaa_corroborated"]), 2)


class TestBasinMetrics(unittest.TestCase):
    def test_under_frac_and_magnitudes(self) -> None:
        # obs = [100, 200], model1 pred = [80, 250]
        # under at obs=100 (80<100) → under_frac = 0.5
        # rel_bias for model1: [(80-100)/100, (250-200)/200] = [-0.2, 0.25] → median = 0.025
        # cond_under_magnitude: (100-80)/100 = 0.20 (only 1 event)
        # cond_under_abs_magnitude: 100-80 = 20 cms
        rows = [
            {"event_id": "e1", "usgs_id": "b1", "seed": 111,
             "flood_tier": "minor", "noaa_corroborated": False,
             "obs": 100.0, "model1": 80.0, "q50": 80.0, "q90": 80.0, "q95": 80.0, "q99": 80.0},
            {"event_id": "e2", "usgs_id": "b1", "seed": 111,
             "flood_tier": "major", "noaa_corroborated": False,
             "obs": 200.0, "model1": 250.0, "q50": 250.0, "q90": 250.0, "q95": 250.0, "q99": 250.0},
        ]
        df = pd.DataFrame(rows)
        long = M.assign_strata(df)
        metrics = M.compute_basin_metrics(long)
        all_row = metrics[(metrics["stratum"] == "all") & (metrics["basin"] == "b1")].iloc[0]
        self.assertAlmostEqual(all_row["model1_under_frac"], 0.5, places=5)
        self.assertAlmostEqual(all_row["model1_cond_under_magnitude"], 0.20, places=5)
        self.assertAlmostEqual(all_row["model1_cond_under_abs_magnitude"], 20.0, places=5)


class TestAggregation(unittest.TestCase):
    def _make_basin_metrics(self) -> pd.DataFrame:
        rows = []
        for seed in [111, 222]:
            for basin in ["b1", "b2"]:
                for stratum in ["all", "major_plus"]:
                    row = {"stratum": stratum, "basin": basin, "seed": seed, "n_events": 10}
                    for col in M._METRIC_COLS:
                        row[col] = 0.6 if "under_frac" in col else 50.0
                    rows.append(row)
        return pd.DataFrame(rows)

    def test_seed_summary_shape(self) -> None:
        bm = self._make_basin_metrics()
        ss = M.aggregate_to_seed_summary(bm)
        # 2 seeds x 2 strata = 4 rows
        self.assertEqual(len(ss), 4)

    def test_final_summary_strata_order(self) -> None:
        bm = self._make_basin_metrics()
        ss = M.aggregate_to_seed_summary(bm)
        final = M.aggregate_to_final_summary(ss)
        strata = list(final["stratum"])
        self.assertEqual(strata[0], "all")
        self.assertIn("major_plus", strata)


if __name__ == "__main__":
    unittest.main()
