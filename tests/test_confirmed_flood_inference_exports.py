from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts.model.confirmed_flood import infer_drbc_confirmed_flood_events as infer


class ConfirmedFloodInferenceExportTests(unittest.TestCase):
    def test_merge_seed_series_writes_primary_like_required_series(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model1_csv = root / "model1.csv"
            model2_csv = root / "model2.csv"
            output_csv = root / "required_series.csv"

            pd.DataFrame(
                [
                    {
                        "event_id": "01432110_20160225T200000",
                        "basin": "01432110",
                        "peak_time": "2016-02-25T20:00:00",
                        "datetime": "2016-02-24T20:00:00",
                        "obs": 999.0,
                        "model1": 1.0,
                        "flood_tier": "minor",
                        "noaa_corroborated": True,
                        "period": "post_2013",
                        "in_eval_window": False,
                    },
                    {
                        "event_id": "01432110_20160225T200000",
                        "basin": "01432110",
                        "peak_time": "2016-02-25T20:00:00",
                        "datetime": "2016-02-25T20:00:00",
                        "obs": 100.0,
                        "model1": 80.0,
                        "flood_tier": "minor",
                        "noaa_corroborated": True,
                        "period": "post_2013",
                        "in_eval_window": True,
                    },
                ]
            ).to_csv(model1_csv, index=False)

            pd.DataFrame(
                [
                    {
                        "event_id": "01432110_20160225T200000",
                        "basin": "01432110",
                        "peak_time": "2016-02-25T20:00:00",
                        "datetime": "2016-02-24T20:00:00",
                        "obs": 999.0,
                        "model2_q50_result": 2.0,
                        "q50": 2.0,
                        "q90": 3.0,
                        "q95": 4.0,
                        "q99": 5.0,
                        "in_eval_window": False,
                    },
                    {
                        "event_id": "01432110_20160225T200000",
                        "basin": "01432110",
                        "peak_time": "2016-02-25T20:00:00",
                        "datetime": "2016-02-25T20:00:00",
                        "obs": 100.0,
                        "model2_q50_result": 90.0,
                        "q50": 90.0,
                        "q90": 110.0,
                        "q95": 120.0,
                        "q99": 130.0,
                        "in_eval_window": True,
                    },
                ]
            ).to_csv(model2_csv, index=False)

            infer.merge_seed_series(
                seed=111,
                model1_epoch=25,
                model2_epoch=5,
                model1_csv=model1_csv,
                model2_csv=model2_csv,
                output_csv=output_csv,
            )

            exported = pd.read_csv(output_csv)
            self.assertEqual(len(exported), 2)
            self.assertEqual(
                list(exported.columns),
                [
                    "event_id",
                    "seed",
                    "basin",
                    "model1_epoch",
                    "model2_epoch",
                    "peak_time",
                    "datetime",
                    "obs",
                    "model1",
                    "model2_q50_result",
                    "q50",
                    "q90",
                    "q95",
                    "q99",
                    "q90_minus_q50",
                    "q95_minus_q90",
                    "q99_minus_q95",
                    "q99_minus_q50",
                    "model2_q50_minus_model1",
                    "flood_tier",
                    "noaa_corroborated",
                    "period",
                    "in_eval_window",
                ],
            )
            self.assertEqual(exported.loc[1, "q99_minus_q50"], 40.0)
            self.assertEqual(exported.loc[1, "model2_q50_minus_model1"], 10.0)

    def test_performance_rows_use_eval_window_only(self) -> None:
        series = pd.DataFrame(
            [
                {
                    "event_id": "01432110_20160225T200000",
                    "seed": 111,
                    "basin": "01432110",
                    "model1_epoch": 25,
                    "model2_epoch": 5,
                    "peak_time": "2016-02-25T20:00:00",
                    "datetime": "2016-02-24T20:00:00",
                    "obs": 999.0,
                    "model1": 1.0,
                    "q50": 2.0,
                    "q90": 3.0,
                    "q95": 4.0,
                    "q99": 5.0,
                    "flood_tier": "minor",
                    "noaa_corroborated": True,
                    "period": "post_2013",
                    "in_eval_window": False,
                },
                {
                    "event_id": "01432110_20160225T200000",
                    "seed": 111,
                    "basin": "01432110",
                    "model1_epoch": 25,
                    "model2_epoch": 5,
                    "peak_time": "2016-02-25T20:00:00",
                    "datetime": "2016-02-25T20:00:00",
                    "obs": 100.0,
                    "model1": 80.0,
                    "q50": 90.0,
                    "q90": 110.0,
                    "q95": 120.0,
                    "q99": 130.0,
                    "flood_tier": "minor",
                    "noaa_corroborated": True,
                    "period": "post_2013",
                    "in_eval_window": True,
                },
            ]
        )

        rows = infer.compute_performance_rows(series)

        self.assertEqual(len(rows), 5)
        by_quantile = {row["quantile"]: row for row in rows}
        self.assertEqual(by_quantile["det"]["obs_peak_cms"], 100.0)
        self.assertAlmostEqual(by_quantile["det"]["peak_under_deficit"], 0.2)
        self.assertAlmostEqual(by_quantile["q99"]["peak_under_deficit"], -0.3)
        self.assertFalse(by_quantile["q99"]["is_underestimate"])


if __name__ == "__main__":
    unittest.main()
