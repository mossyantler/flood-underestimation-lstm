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


if __name__ == "__main__":
    unittest.main()
