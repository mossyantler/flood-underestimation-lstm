#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from statistics import mean, median


SUMMARY_FIELDS = [
    "epoch",
    "n_basins",
    "negative_nse_basins",
    "median_NSE",
    "mean_NSE",
    "median_KGE",
    "mean_KGE",
    "median_FHV",
    "mean_FHV",
    "median_Peak_Timing",
    "mean_Peak_Timing",
    "median_Peak_MAPE",
    "mean_Peak_MAPE",
    "worst_basin_NSE",
    "worst_basin_NSE_value",
]


def _epoch_from_dirname(name: str) -> int:
    if not name.startswith("model_epoch"):
        raise ValueError(f"Unexpected validation directory name: {name}")
    return int(name.replace("model_epoch", ""))


def _read_validation_metrics(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8", newline="") as fp:
        return list(csv.DictReader(fp))


def _to_float(rows: list[dict[str, str]], key: str) -> list[float]:
    return [float(row[key]) for row in rows]


def _format_metric(value: float) -> str:
    if isinstance(value, int):
        return str(value)
    if math.isnan(value):
        return "nan"
    return f"{value:.6f}"


def _summarize_validation_epoch(csv_path: Path) -> dict[str, float | int | str]:
    rows = _read_validation_metrics(csv_path)
    if not rows:
        raise ValueError(f"Validation metrics file is empty: {csv_path}")

    nse_values = _to_float(rows, "NSE")
    kge_values = _to_float(rows, "KGE")
    fhv_values = _to_float(rows, "FHV")
    peak_timing_values = _to_float(rows, "Peak-Timing")
    peak_mape_values = _to_float(rows, "Peak-MAPE")

    worst_nse_idx = min(range(len(rows)), key=lambda idx: nse_values[idx])

    return {
        "epoch": _epoch_from_dirname(csv_path.parent.name),
        "n_basins": len(rows),
        "negative_nse_basins": sum(1 for value in nse_values if value < 0),
        "median_NSE": median(nse_values),
        "mean_NSE": mean(nse_values),
        "median_KGE": median(kge_values),
        "mean_KGE": mean(kge_values),
        "median_FHV": median(fhv_values),
        "mean_FHV": mean(fhv_values),
        "median_Peak_Timing": median(peak_timing_values),
        "mean_Peak_Timing": mean(peak_timing_values),
        "median_Peak_MAPE": median(peak_mape_values),
        "mean_Peak_MAPE": mean(peak_mape_values),
        "worst_basin_NSE": rows[worst_nse_idx]["basin"].zfill(8),
        "worst_basin_NSE_value": nse_values[worst_nse_idx],
    }


def _best_epoch(rows: list[dict[str, float | int | str]], field: str, reverse: bool) -> dict[str, float | int | str]:
    return sorted(rows, key=lambda row: float(row[field]), reverse=reverse)[0]


def _best_abs_epoch(rows: list[dict[str, float | int | str]], field: str) -> dict[str, float | int | str]:
    return sorted(rows, key=lambda row: abs(float(row[field])))[0]


def summarize_run(run_dir: Path, output_dir: Path | None = None) -> tuple[Path, Path]:
    run_dir = run_dir.resolve()
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    validation_paths = sorted(
        run_dir.glob("validation/model_epoch*/validation_metrics.csv"),
        key=lambda path: _epoch_from_dirname(path.parent.name),
    )
    if not validation_paths:
        raise FileNotFoundError(f"No validation metrics found under {run_dir}")

    output_dir = output_dir.resolve() if output_dir else run_dir / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = [_summarize_validation_epoch(path) for path in validation_paths]

    summary_path = output_dir / "validation_epoch_summary.csv"
    with summary_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(summary_rows)

    best_lines = []
    final_row = summary_rows[-1]
    best_lines.append(f"run_dir: {run_dir}")
    best_lines.append(f"final_available_epoch: {final_row['epoch']}")
    best_lines.append(
        f"best_median_NSE: epoch {_best_epoch(summary_rows, 'median_NSE', reverse=True)['epoch']} "
        f"({_format_metric(float(_best_epoch(summary_rows, 'median_NSE', reverse=True)['median_NSE']))})"
    )
    best_lines.append(
        f"best_median_KGE: epoch {_best_epoch(summary_rows, 'median_KGE', reverse=True)['epoch']} "
        f"({_format_metric(float(_best_epoch(summary_rows, 'median_KGE', reverse=True)['median_KGE']))})"
    )
    best_lines.append(
        f"best_abs_median_FHV: epoch {_best_abs_epoch(summary_rows, 'median_FHV')['epoch']} "
        f"({_format_metric(float(_best_abs_epoch(summary_rows, 'median_FHV')['median_FHV']))})"
    )
    best_lines.append(
        f"best_median_Peak_Timing: epoch {_best_epoch(summary_rows, 'median_Peak_Timing', reverse=False)['epoch']} "
        f"({_format_metric(float(_best_epoch(summary_rows, 'median_Peak_Timing', reverse=False)['median_Peak_Timing']))})"
    )
    best_lines.append(
        f"best_median_Peak_MAPE: epoch {_best_epoch(summary_rows, 'median_Peak_MAPE', reverse=False)['epoch']} "
        f"({_format_metric(float(_best_epoch(summary_rows, 'median_Peak_MAPE', reverse=False)['median_Peak_MAPE']))})"
    )
    best_lines.append(
        f"fewest_negative_NSE_basins: epoch {_best_epoch(summary_rows, 'negative_nse_basins', reverse=False)['epoch']} "
        f"({int(_best_epoch(summary_rows, 'negative_nse_basins', reverse=False)['negative_nse_basins'])})"
    )
    best_lines.append(
        f"final_epoch_median_NSE: {_format_metric(float(final_row['median_NSE']))}"
    )
    best_lines.append(
        f"final_epoch_median_KGE: {_format_metric(float(final_row['median_KGE']))}"
    )
    best_lines.append(
        f"final_epoch_median_FHV: {_format_metric(float(final_row['median_FHV']))}"
    )
    best_lines.append(
        f"final_epoch_median_Peak_Timing: {_format_metric(float(final_row['median_Peak_Timing']))}"
    )
    best_lines.append(
        f"final_epoch_median_Peak_MAPE: {_format_metric(float(final_row['median_Peak_MAPE']))}"
    )

    best_path = output_dir / "validation_epoch_best_epochs.txt"
    best_path.write_text("\n".join(best_lines) + "\n", encoding="utf-8")

    return summary_path, best_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize NeuralHydrology validation metric CSVs across epochs."
    )
    parser.add_argument("--run-dir", required=True, help="NH run directory containing validation/model_epoch* folders")
    parser.add_argument(
        "--output-dir",
        help="Optional output directory. Defaults to <run-dir>/analysis",
    )
    args = parser.parse_args()

    summary_path, best_path = summarize_run(
        run_dir=Path(args.run_dir),
        output_dir=Path(args.output_dir) if args.output_dir else None,
    )
    print(f"Wrote validation epoch summary: {summary_path}")
    print(f"Wrote best-epoch notes: {best_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
