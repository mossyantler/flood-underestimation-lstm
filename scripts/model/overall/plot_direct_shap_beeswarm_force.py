#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=2.0",
#   "shap>=0.46",
# ]
# ///
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from direct_shap_plot_bars import save_bar_png, save_signed_bar_png
from direct_shap_plot_common import QUANTILES, REPO_ROOT, PlotResult, read_event_rows, top_features
from direct_shap_plot_details import save_beeswarm, save_force_html, save_force_png, save_waterfall_png

DEFAULT_ANALYSIS_DIR = REPO_ROOT / "output/model_analysis/shap/test_split"


def run(analysis_dir: Path, quantiles: tuple[str, ...], top_n: int, event_top_n: int) -> PlotResult:
    analysis_dir = analysis_dir.resolve()
    figures_dir = analysis_dir / "figures"
    report_dir = analysis_dir / "report"
    data_dir = analysis_dir / "data"
    for directory in (figures_dir, report_dir, data_dir):
        directory.mkdir(parents=True, exist_ok=True)
    rows = read_event_rows(analysis_dir)
    figures: list[Path] = []
    reports: list[Path] = []
    for quantile in quantiles:
        features = top_features(rows, quantile, top_n)
        bar_path = save_bar_png(rows, quantile, features, figures_dir)
        figures.append(bar_path)
        global_alias = figures_dir / f"quantile_lstm_direct_shap_global_feature_importance_{quantile}.png"
        shutil.copyfile(bar_path, global_alias)
        figures.append(global_alias)
        figures.append(save_signed_bar_png(rows, quantile, features, figures_dir))
        figures.append(save_beeswarm(rows, quantile, features, figures_dir))
        figures.append(save_force_png(rows, quantile, figures_dir, event_top_n))
        figures.append(save_waterfall_png(rows, quantile, figures_dir, event_top_n))
        reports.append(save_force_html(rows, quantile, report_dir, event_top_n))
    manifest = data_dir / "quantile_lstm_direct_shap_beeswarm_force_manifest.json"
    payload = {
        "script": "scripts/model/overall/plot_direct_shap_beeswarm_force.py",
        "analysis_dir": str(analysis_dir.relative_to(REPO_ROOT)) if analysis_dir.is_relative_to(REPO_ROOT) else str(analysis_dir),
        "quantiles": list(quantiles),
        "beeswarm_top_n": top_n,
        "event_plot_top_n": event_top_n,
        "figures": [str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path) for path in figures],
        "reports": [str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path) for path in reports],
        "note": "Bar, signed bar, beeswarm, force, and waterfall plots are generated as one titled image per quantile, with separate panels for each available seed.",
        "waterfall_boundary": "Waterfall plots use the representative event prediction minus the displayed aggregate SHAP contributions as the plotted base value because raw timestep-level SHAP additivity terms are not stored in the event feature tables.",
    }
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return PlotResult(figures=figures, reports=reports, manifest=manifest)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create bar, signed bar, beeswarm, and force-style plots from direct SHAP event tables.")
    parser.add_argument("--analysis-dir", type=Path, default=DEFAULT_ANALYSIS_DIR)
    parser.add_argument("--quantiles", nargs="+", choices=QUANTILES, default=list(QUANTILES))
    parser.add_argument("--top-n", type=int, default=12)
    parser.add_argument(
        "--event-top-n",
        type=int,
        default=6,
        help="Number of representative-event features shown in force and waterfall plots.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run(args.analysis_dir, tuple(args.quantiles), args.top_n, args.event_top_n)
    print("Wrote direct SHAP beeswarm/force plots:")
    for path in [*result.figures, *result.reports, result.manifest]:
        print(f"- {path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
