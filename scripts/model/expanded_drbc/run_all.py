#!/usr/bin/env python3
"""Run the expanded DRBC RQ analysis scripts in the canonical rebuild order.

This wrapper intentionally executes the scripts sequentially. Phase B outputs
have lightweight dependencies among B1/B2 and the downstream RQ scripts, so a
single deterministic rebuild entry point is more useful than partial parallel
execution for reproducibility.
"""
from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/primary/metrics"
DEFAULT_INPUT_DIR = DEFAULT_OUTPUT_DIR / "required_series"
DEFAULT_RAW_METRICS_DIR = DEFAULT_OUTPUT_DIR / "raw_metrics"
DEFAULT_TS_DIR = (
    REPO_ROOT / "data/CAMELSH_generic/drbc_expanded_observed_test/time_series"
)
DEFAULT_TEST_OBS_CSV = DEFAULT_INPUT_DIR / "seed111/required_series.csv"
DEFAULT_CATALOG = (
    REPO_ROOT / "output/model_analysis/confirmed_flood/data/catalog/drbc_confirmed_flood_event_catalog.csv"
)
DEFAULT_BASIN_DIR = DEFAULT_TS_DIR


@dataclass(frozen=True)
class Step:
    name: str
    script: Path
    option_attrs: tuple[tuple[str, str], ...] = ()


STEPS: tuple[Step, ...] = (
    Step(
        "A1 RQ-1 central metrics",
        Path("scripts/model/expanded_drbc/compute_rq1_central_metrics.py"),
        (("--input-dir", "input_dir"), ("--raw-metrics-dir", "raw_metrics_dir")),
    ),
    Step(
        "B1 Q99 event windows",
        Path("scripts/model/expanded_drbc/build_q99_events.py"),
        (("--time-series-dir", "time_series_dir"), ("--test-obs-csv", "test_obs_csv")),
    ),
    Step(
        "B2 NOAA mapping",
        Path("scripts/model/expanded_drbc/build_noaa_mapping.py"),
        (("--catalog-csv", "catalog_csv"), ("--basin-dir", "basin_dir")),
    ),
    Step(
        "B3 RQ-2 alpha peak deficit",
        Path("scripts/model/expanded_drbc/compute_rq2_alpha_peak_deficit.py"),
        (("--input-dir", "input_dir"),),
    ),
    Step(
        "B4 RQ-2 beta window capture",
        Path("scripts/model/expanded_drbc/compute_rq2_beta_window_capture.py"),
        (("--input-dir", "input_dir"),),
    ),
    Step(
        "B5 RQ-2 delta threshold recall",
        Path("scripts/model/expanded_drbc/compute_rq2_delta_threshold_recall.py"),
        (("--input-dir", "input_dir"),),
    ),
    Step(
        "B6 RQ-3 cost",
        Path("scripts/model/expanded_drbc/compute_rq3_cost.py"),
        (("--input-dir", "input_dir"),),
    ),
    Step(
        "B7 RQ-4a NSE tier stratify",
        Path("scripts/model/expanded_drbc/compute_rq4a_nse_tier_stratify.py"),
    ),
    Step(
        "B8 RQ-4b event type stratify",
        Path("scripts/model/expanded_drbc/compute_rq4b_event_type_stratify.py"),
    ),
    Step(
        "B9 Q99 NOAA cross-tab sanity",
        Path("scripts/model/expanded_drbc/compute_cross_tab_q99_noaa_sanity.py"),
    ),
    Step(
        "B10 UB obs location class",
        Path("scripts/model/expanded_drbc/compute_ub_location_class.py"),
        (("--input-dir", "input_dir"),),
    ),
    Step(
        "B11 UB gap trajectory",
        Path("scripts/model/expanded_drbc/compute_ub_gap_trajectory.py"),
        (("--input-dir", "input_dir"),),
    ),
    Step(
        "B12 UB band-shape prospective",
        Path("scripts/model/expanded_drbc/compute_ub_band_shape.py"),
        (("--input-dir", "input_dir"),),
    ),
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--uv-bin",
        default="uv",
        help="uv executable used to run each child script.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--raw-metrics-dir", type=Path, default=DEFAULT_RAW_METRICS_DIR)
    parser.add_argument("--time-series-dir", type=Path, default=DEFAULT_TS_DIR)
    parser.add_argument("--test-obs-csv", type=Path, default=DEFAULT_TEST_OBS_CSV)
    parser.add_argument("--catalog-csv", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--basin-dir", type=Path, default=DEFAULT_BASIN_DIR)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the child commands without executing them.",
    )
    return parser.parse_args(argv)


def build_command(step: Step, args: argparse.Namespace) -> list[str]:
    cmd = [args.uv_bin, "run", str(step.script), "--output-dir", str(args.output_dir)]
    for flag, attr in step.option_attrs:
        cmd.extend([flag, str(getattr(args, attr))])
    return cmd


def run_steps(args: argparse.Namespace) -> int:
    for index, step in enumerate(STEPS, start=1):
        cmd = build_command(step, args)
        label = f"[{index:02d}/{len(STEPS):02d}] {step.name}"
        if args.dry_run:
            print(f"{label}: {shlex.join(cmd)}", flush=True)
            continue

        print(f"{label}: {shlex.join(cmd)}", flush=True)
        result = subprocess.run(cmd, cwd=REPO_ROOT, check=False)
        if result.returncode != 0:
            print(f"{label}: FAILED returncode={result.returncode}", file=sys.stderr, flush=True)
            return int(result.returncode)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    return run_steps(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
