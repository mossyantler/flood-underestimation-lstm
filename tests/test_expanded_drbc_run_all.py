from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.model.expanded_drbc import run_all


def test_expanded_drbc_run_all_locks_canonical_step_order() -> None:
    assert [step.name for step in run_all.STEPS] == [
        "A1 RQ-1 central metrics",
        "B1 Q99 event windows",
        "B2 NOAA mapping",
        "B3 RQ-2 alpha peak deficit",
        "B4 RQ-2 beta window capture",
        "B5 RQ-2 delta threshold recall",
        "B6 RQ-3 cost",
        "B7 RQ-4a NSE tier stratify",
        "B8 RQ-4b event type stratify",
        "B9 Q99 NOAA cross-tab sanity",
        "B10 obs location class",
        "B11 gap trajectory",
        "B12 band-shape prospective",
    ]


def test_expanded_drbc_run_all_builds_uv_commands_with_shared_and_step_inputs() -> None:
    args = run_all.parse_args([
        "--uv-bin",
        "uv-test",
        "--output-dir",
        "tmp/out",
        "--input-dir",
        "tmp/required",
        "--time-series-dir",
        "tmp/time_series",
        "--test-obs-csv",
        "tmp/test_obs.csv",
        "--catalog-csv",
        "tmp/catalog.csv",
        "--basin-dir",
        "tmp/basins",
        "--raw-metrics-dir",
        "tmp/raw_metrics",
    ])

    commands = [run_all.build_command(step, args) for step in run_all.STEPS]

    assert commands[0] == [
        "uv-test",
        "run",
        str(Path("scripts/model/expanded_drbc/compute_rq1_central_metrics.py")),
        "--output-dir",
        "tmp/out",
        "--input-dir",
        "tmp/required",
        "--raw-metrics-dir",
        "tmp/raw_metrics",
    ]
    assert commands[1] == [
        "uv-test",
        "run",
        str(Path("scripts/model/expanded_drbc/build_q99_events.py")),
        "--output-dir",
        "tmp/out",
        "--time-series-dir",
        "tmp/time_series",
        "--test-obs-csv",
        "tmp/test_obs.csv",
    ]
    assert commands[2] == [
        "uv-test",
        "run",
        str(Path("scripts/model/expanded_drbc/build_noaa_mapping.py")),
        "--output-dir",
        "tmp/out",
        "--catalog-csv",
        "tmp/catalog.csv",
        "--basin-dir",
        "tmp/basins",
    ]
    assert commands[9] == [
        "uv-test",
        "run",
        str(Path("scripts/model/expanded_drbc/compute_cross_tab_q99_noaa_sanity.py")),
        "--output-dir",
        "tmp/out",
    ]
    assert commands[-1] == [
        "uv-test",
        "run",
        str(Path("scripts/model/expanded_drbc/compute_band_shape.py")),
        "--output-dir",
        "tmp/out",
        "--input-dir",
        "tmp/required",
    ]


def test_expanded_drbc_run_all_defaults_use_primary_metrics_data_dirs() -> None:
    args = run_all.parse_args([])

    assert args.output_dir == run_all.REPO_ROOT / "output/model_analysis/primary/metrics"
    assert args.input_dir == args.output_dir / "data/required_series"
    assert args.raw_metrics_dir == args.output_dir / "data/raw_metrics"
    assert args.test_obs_csv == args.input_dir / "seed111/required_series.csv"


def test_expanded_drbc_scripts_use_current_noaa_overlap_filename() -> None:
    script_dir = run_all.REPO_ROOT / "scripts/model/expanded_drbc"
    texts = {path: path.read_text() for path in script_dir.rglob("*.py")}

    assert all(
        "rq2_noaa_events_expanded_overlap.csv" not in text
        for text in texts.values()
    )
    assert "rq2_noaa_events_overlap.csv" in (
        script_dir / "build_noaa_mapping.py"
    ).read_text()


def test_expanded_drbc_run_all_returns_first_failed_step(monkeypatch) -> None:
    args = run_all.parse_args(["--uv-bin", "uv-test", "--output-dir", "tmp/out"])
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], *, cwd: Path, check: bool) -> object:
        del cwd, check
        calls.append(cmd)
        return type("Result", (), {"returncode": 7})()

    monkeypatch.setattr(run_all.subprocess, "run", fake_run)

    exit_code = run_all.run_steps(args)

    assert exit_code == 7
    assert len(calls) == 1
    assert calls[0][0:2] == ["uv-test", "run"]
