from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import scripts.model.overall.analyze_expanded_drbc_stratified_underestimation as M


def _make_required_series(
    basins: list[str],
    n_steps: int,
    seed: int = 111,
    obs_values: dict[str, list[float]] | None = None,
) -> pd.DataFrame:
    """Helper: synthetic required_series DataFrame."""
    rows = []
    for basin in basins:
        obs_seq = (obs_values or {}).get(basin, list(range(1, n_steps + 1)))
        for i, obs in enumerate(obs_seq[:n_steps]):
            rows.append({
                "seed": seed,
                "basin": basin,
                "datetime": pd.Timestamp("2014-01-01") + pd.Timedelta(hours=i),
                "obs": float(obs),
                "model1": float(obs) * 0.8,
                "q50": float(obs) * 0.85,
                "q90": float(obs) * 1.0,
                "q95": float(obs) * 1.1,
                "q99": float(obs) * 1.3,
            })
    return pd.DataFrame(rows)


class TestLoadRequiredSeries(unittest.TestCase):
    def test_loads_and_concatenates_seeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for seed in [111, 222]:
                seed_dir = root / f"seed{seed}"
                seed_dir.mkdir(parents=True)
                df = _make_required_series(["01414000"], 10, seed=seed)
                df.to_csv(seed_dir / "primary_required_series.csv", index=False)

            result = M.load_required_series([111, 222], base_dir=root)
            self.assertEqual(len(result), 20)
            self.assertEqual(set(result["seed"].unique()), {111, 222})


class TestBasinThresholds(unittest.TestCase):
    def test_computes_per_basin_quantiles(self) -> None:
        df_a = _make_required_series(["basinA"], 100,
                                     obs_values={"basinA": list(range(1, 101))})
        df_b = _make_required_series(["basinB"], 100,
                                     obs_values={"basinB": list(range(10, 1010, 10))})
        df = pd.concat([df_a, df_b], ignore_index=True)

        thr = M.compute_basin_thresholds(df)
        self.assertIn("basinA", thr["basin"].values)
        self.assertIn("basinB", thr["basin"].values)

        thr_a = thr[thr["basin"] == "basinA"].iloc[0]
        thr_b = thr[thr["basin"] == "basinB"].iloc[0]
        self.assertGreater(thr_a["q90_thr"], 89)
        self.assertGreater(thr_b["q99_thr"], 980)

    def test_excludes_zero_and_nan_obs(self) -> None:
        obs_seq = [0.0, float("nan")] + list(range(1, 99))
        df = _make_required_series(["basinC"], 100,
                                   obs_values={"basinC": obs_seq})
        thr = M.compute_basin_thresholds(df)
        self.assertEqual(len(thr), 1)


class TestAssignStrata(unittest.TestCase):
    def test_all_stratum_excludes_nan_and_zero(self) -> None:
        obs_seq = [0.0, float("nan"), 5.0, 10.0]
        df = _make_required_series(["b1"], 4, obs_values={"b1": obs_seq})
        thr = pd.DataFrame([{"basin": "b1", "q50_thr": 4.0, "q90_thr": 8.0, "q95_thr": 9.0, "q99_thr": 9.5}])
        result = M.assign_strata(df, thr)
        all_rows = result[result["stratum"] == "all"]
        self.assertEqual(len(all_rows), 2)

    def test_q99_plus_stratum_filters_correctly(self) -> None:
        obs_seq = [5.0, 10.0, 20.0]
        df = _make_required_series(["b2"], 3, obs_values={"b2": obs_seq})
        thr = pd.DataFrame([{"basin": "b2", "q50_thr": 4.0, "q90_thr": 8.0, "q95_thr": 9.0, "q99_thr": 15.0}])
        result = M.assign_strata(df, thr)
        q99_rows = result[result["stratum"] == "obs_q99_plus"]
        self.assertEqual(len(q99_rows), 1)
        self.assertAlmostEqual(q99_rows.iloc[0]["obs"], 20.0)


class TestBasinMetrics(unittest.TestCase):
    def test_under_fraction_and_median_rel_bias(self) -> None:
        # obs = [10, 20, 30, 40, 50]
        # model1 = [8, 25, 25, 45, 45]
        # under at obs=10 (8<10), obs=30 (25<30), obs=50 (45<50) → under_frac = 3/5 = 0.6
        # rel_err = [-0.2, 0.25, -0.167, 0.125, -0.1] → sorted: [-0.2, -0.167, -0.1, 0.125, 0.25]
        # → median = -0.1
        obs_seq = [10.0, 20.0, 30.0, 40.0, 50.0]
        df = _make_required_series(["bX"], 5, obs_values={"bX": obs_seq})
        df["model1"] = [8.0, 25.0, 25.0, 45.0, 45.0]
        df["q50"] = df["model1"]
        df["q90"] = df["model1"]
        df["q95"] = df["model1"]
        df["q99"] = df["model1"]

        thr = pd.DataFrame([{"basin": "bX", "q50_thr": 50.0, "q90_thr": 100.0, "q95_thr": 100.0, "q99_thr": 100.0}])
        long_df = M.assign_strata(df, thr)
        metrics = M.compute_basin_metrics(long_df)

        all_m1 = metrics[(metrics["stratum"] == "all") & (metrics["basin"] == "bX")]
        self.assertEqual(len(all_m1), 1)
        row = all_m1.iloc[0]
        self.assertAlmostEqual(row["model1_under_frac"], 0.6, places=5)
        self.assertAlmostEqual(row["model1_med_rel_bias"], -0.1, places=5)

    def test_n_timesteps_recorded(self) -> None:
        df = _make_required_series(["bY"], 20)
        thr = pd.DataFrame([{"basin": "bY", "q50_thr": 500.0, "q90_thr": 1000.0, "q95_thr": 1000.0, "q99_thr": 1000.0}])
        long_df = M.assign_strata(df, thr)
        metrics = M.compute_basin_metrics(long_df)
        all_row = metrics[(metrics["stratum"] == "all") & (metrics["basin"] == "bY")].iloc[0]
        self.assertEqual(all_row["n_timesteps"], 20)


class TestAggregation(unittest.TestCase):
    def _make_basin_metrics(self) -> pd.DataFrame:
        rows = []
        for seed in [111, 222]:
            for basin in ["b1", "b2", "b3"]:
                for stratum in ["all", "obs_q90_plus"]:
                    row = {"stratum": stratum, "basin": basin, "seed": seed, "n_timesteps": 100}
                    for col in M._METRIC_COLS:
                        row[col] = 0.5 if "under_frac" in col else -0.2
                    rows.append(row)
        return pd.DataFrame(rows)

    def test_seed_summary_shape(self) -> None:
        bm = self._make_basin_metrics()
        seed_sum = M.aggregate_to_seed_summary(bm)
        # 2 seeds x 2 strata = 4 rows
        self.assertEqual(len(seed_sum), 4)
        self.assertIn("n_basins", seed_sum.columns)
        self.assertIn("model1_under_frac", seed_sum.columns)

    def test_final_summary_shape(self) -> None:
        bm = self._make_basin_metrics()
        seed_sum = M.aggregate_to_seed_summary(bm)
        final = M.aggregate_to_final_summary(seed_sum)
        # 2 strata = 2 rows
        self.assertEqual(len(final), 2)
        self.assertIn("stratum", final.columns)
        self.assertIn("q99_under_frac", final.columns)

    def test_aggregation_computes_median(self) -> None:
        bm = self._make_basin_metrics()
        seed_sum = M.aggregate_to_seed_summary(bm)
        final = M.aggregate_to_final_summary(seed_sum)
        all_row = final[final["stratum"] == "all"].iloc[0]
        self.assertAlmostEqual(all_row["model1_under_frac"], 0.5, places=5)


if __name__ == "__main__":
    unittest.main()
