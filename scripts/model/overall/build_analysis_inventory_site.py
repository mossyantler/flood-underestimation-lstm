#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/analysis_dashboard"

ANALYSIS_GROUPS: list[dict[str, Any]] = [
    {
        "id": "data-foundation",
        "label": "데이터·실험 기반",
        "description": "DRBC holdout, subset300, coverage, event label처럼 모델 비교 전에 고정해야 하는 분석 기반입니다.",
        "analysis_ids": [
            "drbc-definition",
            "drbc-screening",
            "subset300-representativeness",
            "timeseries-coverage",
            "return-period-proxy",
            "all-event-response",
            "flood-generation-typing",
            "ml-event-regime",
        ],
    },
    {
        "id": "overall-performance",
        "label": "전체 모델 성능",
        "description": "Model 2가 q50 중심 예측을 무너뜨리지 않는지, checkpoint와 overfit risk까지 함께 확인합니다.",
        "analysis_ids": ["primary-overall", "checkpoint-sensitivity", "overfit-risk"],
    },
    {
        "id": "probabilistic-head",
        "label": "Quantile / Probabilistic Head",
        "description": "q90/q95/q99 output이 high-flow와 peak underestimation을 어떻게 바꾸는지 보는 핵심 그룹입니다.",
        "analysis_ids": [
            "high-flow-quantile",
            "probabilistic-diagnostics",
            "peak-quantile-bracket",
            "extreme-flood-proxy",
        ],
    },
    {
        "id": "event-stress",
        "label": "Event / Stress 응답",
        "description": "event-regime, extreme-rain, runoff-ratio, hydrograph를 통해 aggregate metric 뒤의 사건별 반응을 봅니다.",
        "analysis_ids": [
            "event-regime-errors",
            "extreme-rain-stress",
            "runoff-ratio",
            "hydrograph-galleries",
        ],
    },
    {
        "id": "basin-robustness",
        "label": "Basin-level 해석·Robustness",
        "description": "유역별 outlier, Natural/Broad robustness, basin dissect, managed-flow protocol을 묶은 해석 그룹입니다.",
        "analysis_ids": [
            "median-deviation",
            "outlier-mechanism",
            "natural-broad",
            "basin-dissect",
            "event-suppression-protocol",
        ],
    },
    {
        "id": "paper-assets",
        "label": "논문용 산출물",
        "description": "본문 표와 그림 후보를 고르기 위한 paper-facing staging area입니다.",
        "analysis_ids": ["paper-assets"],
    },
]

GROUP_NARRATIVES: dict[str, dict[str, str]] = {
    "data-foundation": {
        "question": "비교 조건이 고정돼 있나?",
        "answer": "DRBC holdout, subset300, event label 기준은 재현 가능한 상태로 묶여 있어요.",
        "evidence": "split map, coverage table, event catalog",
        "caution": "drbc_historical_stress는 holdout basin 조건만 유지하므로 temporal independence 근거로 쓰면 안 됩니다.",
    },
    "overall-performance": {
        "question": "Model 2가 전체 성능을 무너뜨리나?",
        "answer": "q50 guardrail과 checkpoint sensitivity를 함께 보면 큰 손상 없이 비교축을 유지합니다.",
        "evidence": "primary metric table, checkpoint sensitivity, overfit diagnostic",
        "caution": "전체 metric만으로 high-flow 개선을 결론내리면 event-level 차이를 놓칩니다.",
    },
    "probabilistic-head": {
        "question": "Quantile head가 peak underestimation을 줄이나?",
        "answer": "q95/q99 계열에서 high-flow underestimation 완화 신호를 직접 확인합니다.",
        "evidence": "high-flow quantile chart, peak bracket table, flood proxy",
        "caution": "tail quantile은 coverage와 함께 읽어야 과한 calibration claim을 피할 수 있습니다.",
    },
    "event-stress": {
        "question": "평균 개선이 실제 event에서도 보이나?",
        "answer": "extreme-rain, runoff-ratio, hydrograph를 나눠 사건별 반응 차이를 추적합니다.",
        "evidence": "stress tables, runoff-ratio tiers, Q99+ hydrograph gallery",
        "caution": "negative-control rain event와 flood-producing event를 같은 의미로 읽으면 안 됩니다.",
    },
    "basin-robustness": {
        "question": "몇 개 유역이 결론을 끌고 가나?",
        "answer": "Natural/Broad, outlier mechanism, basin dissect로 유역별 편향과 예외를 분리합니다.",
        "evidence": "median-deviation tiers, outlier reports, basin dissect notes",
        "caution": "managed-flow나 hydromod risk가 있는 유역은 자연 반응 해석과 분리해야 합니다.",
    },
    "paper-assets": {
        "question": "논문 본문으로 옮길 근거는 어디인가?",
        "answer": "본문 후보 표와 figure를 따로 staging해서 분석 산출물에서 바로 추적할 수 있습니다.",
        "evidence": "compact tables, figure candidates, case galleries",
        "caution": "staging asset은 최종 논문 claim이 아니라 후보 묶음으로 관리해야 합니다.",
    },
}

GROUP_BY_ANALYSIS_ID = {
    analysis_id: group
    for group in ANALYSIS_GROUPS
    for analysis_id in group["analysis_ids"]
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a browser-facing inventory of CAMELS analysis outputs."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--publish-dir",
        type=Path,
        default=None,
        help=(
            "Optional static-posting bundle directory. The dashboard is written there "
            "with copied preview images and direct linked artifacts under assets/."
        ),
    )
    parser.add_argument(
        "--max-linked-asset-mb",
        type=float,
        default=25.0,
        help="Maximum size for a linked artifact copied into --publish-dir. Preview images are always copied.",
    )
    return parser.parse_args()


def read_json(path: str | Path) -> dict[str, Any]:
    file_path = REPO_ROOT / path
    if not file_path.exists():
        return {}
    return json.loads(file_path.read_text(encoding="utf-8"))


def count_files(path: str | Path, pattern: str = "*") -> int:
    root = REPO_ROOT / path
    if not root.exists():
        return 0
    return sum(1 for item in root.rglob(pattern) if item.is_file())


def count_csv_rows(path: str | Path) -> int:
    file_path = REPO_ROOT / path
    if not file_path.exists():
        return 0
    with file_path.open("r", encoding="utf-8", newline="") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def csv_col_counts(path: str | Path, column: str) -> dict[str, int]:
    file_path = REPO_ROOT / path
    if not file_path.exists():
        return {}
    counts: dict[str, int] = {}
    with file_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            key = str(row.get(column, "")).strip() or "unknown"
            counts[key] = counts.get(key, 0) + 1
    return counts


def page_href(path: str | Path, output_dir: Path) -> str:
    target = (REPO_ROOT / path).resolve()
    relative = os.path.relpath(target, start=output_dir.resolve())
    return html.escape(relative.replace(os.sep, "/"))


def asset_rel(path: str | Path) -> Path:
    target = (REPO_ROOT / path).resolve()
    return Path("assets") / target.relative_to(REPO_ROOT)


def publish_href(
    path: str | Path,
    publish_dir: Path,
    copied: set[Path],
    omitted: list[dict[str, str]],
    max_asset_bytes: int,
    force_copy: bool = False,
) -> str:
    target = (REPO_ROOT / path).resolve()
    target.relative_to(REPO_ROOT)
    rel = asset_rel(path)
    destination = publish_dir / rel
    copy_source = target.parent if target.is_file() and target.suffix.lower() == ".html" else target

    if not force_copy and path_size(copy_source) > max_asset_bytes:
        return omitted_href(path, publish_dir, omitted, path_size(copy_source), max_asset_bytes)

    if target.is_dir():
        copy_directory_for_publish(target, destination, copied)
        index_file = destination / "index.html"
        if index_file.exists():
            return html.escape((rel / "index.html").as_posix())
        return html.escape(rel.as_posix() + "/")

    if target.is_file() and target.name == "index.html":
        parent_rel = Path("assets") / target.parent.relative_to(REPO_ROOT)
        parent_destination = publish_dir / parent_rel
        copy_directory_for_publish(target.parent, parent_destination, copied)
        return html.escape((parent_rel / "index.html").as_posix())

    if target.is_file():
        copy_file_for_publish(target, destination, copied)
        if target.suffix.lower() == ".shp":
            copy_shapefile_sidecars(target, destination, copied)
        return html.escape(rel.as_posix())

    return html.escape(str(path))


def path_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    if path.is_dir():
        return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
    return 0


def fmt_bytes(value: int) -> str:
    units = ("B", "KB", "MB", "GB")
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{value} B"


def safe_omitted_name(path: str | Path) -> str:
    raw = str(path).replace(os.sep, "__")
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in raw)


def omitted_href(
    path: str | Path,
    publish_dir: Path,
    omitted: list[dict[str, str]],
    size_bytes: int,
    max_asset_bytes: int,
) -> str:
    rel = Path("assets/_omitted") / f"{safe_omitted_name(path)}.html"
    destination = publish_dir / rel
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        render_omitted_page(str(path), size_bytes, max_asset_bytes),
        encoding="utf-8",
    )
    if not any(item["path"] == str(path) for item in omitted):
        omitted.append(
            {
                "path": str(path),
                "size": fmt_bytes(size_bytes),
                "max_size": fmt_bytes(max_asset_bytes),
                "href": rel.as_posix(),
            }
        )
    return html.escape(rel.as_posix())


def render_omitted_page(path: str, size_bytes: int, max_asset_bytes: int) -> str:
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Large artifact omitted</title>
  <style>
    body {{ margin: 0; padding: 28px; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #17212b; background: #f7f9fa; }}
    main {{ max-width: 860px; margin: 0 auto; background: #fff; border: 1px solid #d8e0e6; border-radius: 8px; padding: 24px; }}
    h1 {{ margin: 0 0 12px; font-size: 22px; }}
    p {{ line-height: 1.6; color: #52606d; }}
    code {{ display: block; padding: 12px; border-radius: 8px; background: #f1f4f6; color: #17212b; overflow-wrap: anywhere; white-space: pre-wrap; }}
  </style>
</head>
<body>
  <main>
    <h1>Large artifact omitted from static bundle</h1>
    <p>This linked artifact was not copied because it is {html.escape(fmt_bytes(size_bytes))}, above the publish limit of {html.escape(fmt_bytes(max_asset_bytes))}.</p>
    <p>Original repository path:</p>
    <code>{html.escape(path)}</code>
  </main>
</body>
</html>
"""


def copy_file_for_publish(source: Path, destination: Path, copied: set[Path]) -> None:
    source = source.resolve()
    if source in copied:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    copied.add(source)


def copy_directory_for_publish(source: Path, destination: Path, copied: set[Path]) -> None:
    source = source.resolve()
    if source in copied:
        return
    ignore = shutil.ignore_patterns(".DS_Store", "__pycache__")
    shutil.copytree(source, destination, dirs_exist_ok=True, ignore=ignore)
    write_directory_indexes(destination)
    copied.add(source)


def copy_shapefile_sidecars(source: Path, destination: Path, copied: set[Path]) -> None:
    for suffix in (".shx", ".dbf", ".prj", ".cpg", ".qpj"):
        sidecar = source.with_suffix(suffix)
        if sidecar.exists():
            copy_file_for_publish(sidecar, destination.with_suffix(suffix), copied)


def write_directory_indexes(root: Path) -> None:
    directories = [path for path in root.rglob("*") if path.is_dir()]
    for directory in sorted([root, *directories], key=lambda path: len(path.parts), reverse=True):
        index_path = directory / "index.html"
        if not index_path.exists():
            index_path.write_text(render_directory_index(directory), encoding="utf-8")


def render_directory_index(directory: Path) -> str:
    entries = []
    for child in sorted(directory.iterdir(), key=lambda path: (path.is_file(), path.name.lower())):
        if child.name == "index.html":
            continue
        if child.is_dir():
            href = f"{child.name}/index.html" if (child / "index.html").exists() else f"{child.name}/"
            label = f"{child.name}/"
        else:
            href = child.name
            label = child.name
        entries.append(f'<li><a href="{html.escape(href)}">{html.escape(label)}</a></li>')
    title = directory.name or "assets"
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} asset listing</title>
  <style>
    body {{ margin: 0; padding: 28px; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #17212b; background: #f7f9fa; }}
    main {{ max-width: 920px; margin: 0 auto; background: #fff; border: 1px solid #d8e0e6; border-radius: 8px; padding: 24px; }}
    h1 {{ font-size: 22px; margin: 0 0 16px; }}
    ul {{ margin: 0; padding-left: 22px; }}
    li {{ margin: 7px 0; overflow-wrap: anywhere; }}
    a {{ color: #2f6f9f; text-underline-offset: 3px; }}
  </style>
</head>
<body>
  <main>
    <h1>{html.escape(title)}</h1>
    <ul>{''.join(entries)}</ul>
  </main>
</body>
</html>
"""


def link_item(path: str, label: str | None = None) -> dict[str, str]:
    return {"label": label or Path(path).name, "path": path}


def fmt_count(value: Any) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:,.3f}".rstrip("0").rstrip(".")
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def count_unique_basin_reports() -> int:
    root = REPO_ROOT / "output/model_analysis/extreme_rain/primary/basin_dissect"
    if not root.exists():
        return 0
    basins: set[str] = set()
    for path in root.glob("*/*.md"):
        stem = path.stem
        if stem.endswith("_ko"):
            stem = stem[:-3]
        if stem.isdigit():
            basins.add(stem)
    return len(basins)


def build_stats() -> dict[str, Any]:
    overall_meta = read_json("output/model_analysis/overall_analysis/run_records/analysis_metadata.json")
    primary = read_json(
        "output/model_analysis/extreme_rain/primary/analysis/analysis_summary.json"
    )
    primary_exposure = read_json(
        "output/model_analysis/extreme_rain/primary/exposure/analysis_summary.json"
    )
    event_regime = read_json("output/model_analysis/quantile_analysis/event_regime_analysis/analysis_summary.json")
    probabilistic = read_json("output/model_analysis/probabilistic_diagnostics/analysis_metadata.json")
    natural = read_json("output/model_analysis/natural_broad_comparison/metadata/analysis_metadata.json")
    scaling = read_json("configs/pilot/basin_splits/scaling_pilot_summary.json")
    drbc_boundary = read_json("output/basin/drbc/basin_define/drbc_boundary_summary.json")
    drbc_quality = read_json("output/basin/drbc/screening/drbc_streamflow_quality_summary.json")
    all_event = read_json("output/basin/all/analysis/event_response/metadata/event_response_summary.json")
    all_regime = read_json("output/basin/all/analysis/event_regime/metadata/selected_variant_visual_summary.json")
    timeseries = read_json("output/basin/timeseries/basin_timeseries_coverage_metadata.json")

    hydrograph_root = REPO_ROOT / "output/model_analysis/extreme_rain/primary/analysis"
    hydrograph_png_count = sum(1 for path in hydrograph_root.glob("*_hydrograph/*.png"))
    hydrograph_gallery_count = sum(1 for path in hydrograph_root.glob("*_hydrograph/index.html"))

    return {
        "overall_meta": overall_meta,
        "primary": primary,
        "primary_exposure": primary_exposure,
        "event_regime": event_regime,
        "probabilistic": probabilistic,
        "natural": natural,
        "scaling": scaling,
        "drbc_boundary": drbc_boundary,
        "drbc_quality": drbc_quality,
        "all_event": all_event,
        "all_regime": all_regime,
        "timeseries": timeseries,
        "hydrograph_png_count": hydrograph_png_count,
        "hydrograph_gallery_count": hydrograph_gallery_count,
        "basin_report_count": count_unique_basin_reports(),
        "station_note_count": max(count_files("docs/references/basin/usgs_station_notes", "*.md") - 1, 0),
        "overall_files": count_files("output/model_analysis/overall_analysis"),
        "quantile_files": count_files("output/model_analysis/quantile_analysis"),
        "extreme_rain_files": count_files("output/model_analysis/extreme_rain"),
        "probabilistic_files": count_files("output/model_analysis/probabilistic_diagnostics"),
        "natural_files": count_files("output/model_analysis/natural_broad_comparison"),
        "paper_files": count_files("output/model_analysis/paper_result_assets"),
        "basin_output_files": count_files("output/basin"),
        "hydrograph_manifest_rows": count_csv_rows(
            "output/model_analysis/quantile_analysis/hydrograph_plot_manifest.csv"
        ),
        "flow_summary_rows": count_csv_rows(
            "output/model_analysis/quantile_analysis/analysis/flow_strata_predictor_summary.csv"
        ),
        "observed_peak_rows": count_csv_rows(
            "output/model_analysis/quantile_analysis/analysis/observed_peak_predictions.csv"
        ),
        "runoff_ratio_files": count_files(
            "output/model_analysis/extreme_rain/primary/analysis/runoff_ratio_diagnostics"
        ),
        "source_counts": csv_col_counts(
            "output/model_analysis/extreme_rain/primary/analysis/runoff_ratio_diagnostics/"
            "primary_stress_runoff_ratio_iqr_tier_basin_mapping.csv",
            "dominant_distance_label",
        ),
    }


def build_analyses(stats: dict[str, Any]) -> list[dict[str, Any]]:
    overall = stats["overall_meta"]
    primary = stats["primary"]
    exposure = stats["primary_exposure"]
    event_regime = stats["event_regime"]
    natural = stats["natural"]
    scaling = stats["scaling"]
    drbc_boundary = stats["drbc_boundary"]
    drbc_quality = stats["drbc_quality"]
    all_event = stats["all_event"]
    all_regime = stats["all_regime"]
    timeseries = stats["timeseries"]

    raw_pool = scaling.get("source_summary", {}).get("raw_broad_pool_total_count")
    prepared_pool = scaling.get("source_summary", {}).get("prepared_broad_pool_total_count")
    test_count = scaling.get("source_summary", {}).get("test_count")
    official_seeds = ", ".join(str(seed) for seed in overall.get("official_seeds", [])) or "111, 222, 444"

    return [
        {
            "id": "drbc-definition",
            "category": "기반 데이터",
            "status": "완료",
            "title": "DRBC holdout basin 정의",
            "purpose": "Delaware River Basin을 regional holdout/evaluation region으로 고정하고, CAMELSH basin과 DRBC boundary의 outlet/overlap 관계를 정리합니다.",
            "use": "Model 1/2 test basin이 왜 DRBC 38개 quality-pass basin으로 좁혀졌는지 설명하는 출발점이에요.",
            "stats": [
                ["CAMELSH evaluated", drbc_boundary.get("camelsh_total_basins_evaluated")],
                ["outlet in DRBC", drbc_boundary.get("camelsh_outlet_in_drbc_count")],
                ["selected overlap>=0.9", drbc_boundary.get("camelsh_selected_count")],
            ],
            "outputs": [
                link_item("output/basin/drbc/basin_define/drbc_boundary_summary.json", "boundary summary"),
                link_item("output/basin/drbc/basin_define/camelsh_drbc_selected.csv", "selected basin table"),
            ],
            "sources": [
                link_item("basins/drbc_boundary/drb_bnd_polygon.shp", "DRBC boundary shp"),
                link_item("scripts/basin/drbc/build_drbc_camelsh_tables.py", "DRBC table generator"),
            ],
            "tags": ["DRBC", "holdout", "basin"],
        },
        {
            "id": "drbc-screening",
            "category": "기반 데이터",
            "status": "완료",
            "title": "DRBC quality gate와 broad/natural screening",
            "purpose": "DRBC selected basin 154개 중 usable streamflow, hydromodification proxy, broad/natural/event-priority cohort를 정리합니다.",
            "use": "Natural/Broad robustness, hydromodification risk, basin outlier 해석의 metadata backbone으로 씁니다.",
            "stats": [
                ["selected", drbc_quality.get("selected_basin_count")],
                ["quality pass", drbc_quality.get("passes_streamflow_quality_gate_count")],
                ["hydromod risk", drbc_quality.get("hydromod_risk_count")],
            ],
            "outputs": [
                link_item("output/basin/drbc/screening/drbc_streamflow_quality_summary.json", "streamflow quality summary"),
                link_item("output/basin/drbc/screening/drbc_provisional_screening_summary.json", "provisional screening summary"),
            ],
            "sources": [
                link_item("scripts/basin/drbc/build_drbc_streamflow_quality_table.py", "quality gate generator"),
                link_item("scripts/basin/drbc/build_drbc_provisional_screening_table.py", "screening generator"),
            ],
            "caution": "natural은 land-cover 자연성만 뜻하지 않고, 현재 repo에서는 hydromodification-risk가 없는 subset을 가리키는 operational label이에요.",
            "tags": ["natural", "broad", "hydromod"],
        },
        {
            "id": "subset300-representativeness",
            "category": "기반 데이터",
            "status": "완료",
            "title": "Subset300 대표성 및 scaling pilot",
            "purpose": "non-DRBC prepared pool 전체 대신 고정 300-basin subset을 쓰는 결정을 static attribute, event-response, random benchmark, compute cost로 방어합니다.",
            "use": "main comparison의 train/validation basin 수가 DRBC test metric을 보고 정해진 것이 아니라는 점을 문서화할 때 씁니다.",
            "stats": [
                ["raw broad pool", raw_pool],
                ["prepared pool", prepared_pool],
                ["fixed subset", 300],
                ["DRBC test", test_count],
            ],
            "outputs": [
                link_item("docs/experiment/analysis/basin/subset300_representativeness_report.md", "representativeness report"),
                link_item("configs/pilot/diagnostics/plots/smd_heatmaps.png", "SMD heatmap"),
                link_item("configs/pilot/diagnostics/permutation_benchmark/subset300_random_benchmark_summary.json", "random benchmark"),
            ],
            "sources": [
                link_item("scripts/scaling/build_scaling_pilot_splits.py", "split builder"),
                link_item("scripts/scaling/build_scaling_pilot_random_subset_benchmark.py", "random benchmark generator"),
            ],
            "caution": "300개 subset은 globally optimal subset이 아니라, compute-constrained main comparison에 충분히 방어 가능한 fixed subset으로 읽는 게 안전해요.",
            "tags": ["subset300", "scaling", "representativeness"],
        },
        {
            "id": "timeseries-coverage",
            "category": "기반 데이터",
            "status": "완료",
            "title": "Split별 time-series coverage 진단",
            "purpose": "fixed split에서 target Streamflow와 dynamic input window가 실제로 얼마나 존재하는지 확인합니다.",
            "use": "metric support, low-support basin caveat, sequence warm-up 구조를 설명할 때 씁니다.",
            "stats": [
                ["train basins", timeseries.get("splits", {}).get("train", {}).get("basin_count")],
                ["validation basins", timeseries.get("splits", {}).get("validation", {}).get("basin_count")],
                ["test basins", timeseries.get("splits", {}).get("test", {}).get("basin_count")],
            ],
            "outputs": [
                link_item("output/basin/timeseries/README.md", "timeseries README"),
                link_item("output/basin/timeseries/basin_timeseries_coverage.png", "coverage overview"),
                link_item("output/basin/timeseries/tables/drbc_test_period_one_minus_missing_rate_table.md", "DRBC test missing-rate table"),
            ],
            "sources": [
                link_item("scripts/basin/split_diagnostics/plot_subset300_timeseries_coverage.py", "coverage generator"),
                link_item("scripts/model/sequence/export_single_sequence_model_io_gantt.py", "sequence Gantt helper"),
            ],
            "tags": ["coverage", "sequence", "support"],
        },
        {
            "id": "return-period-proxy",
            "category": "기반 데이터",
            "status": "완료",
            "title": "Return-period proxy와 external reference 비교",
            "purpose": "CAMELSH hourly annual-maxima 기반 flood/precip return-period proxy를 만들고 USGS/NOAA reference와 비교합니다.",
            "use": "extreme-rain stress event의 rain/flood severity ratio 기준과 proxy 한계를 설명할 때 씁니다.",
            "stats": [
                ["processed basins", read_json("output/basin/all/analysis/return_period/metadata/return_period_summary.json").get("processed_basin_count")],
                ["USGS ok", read_json("output/basin/all/reference_comparison/usgs_flood/metadata/usgs_streamstats_peak_flow_summary.json").get("status_counts", {}).get("ok")],
                ["NOAA Atlas14 ok", read_json("output/basin/all/reference_comparison/noaa_prec/metadata/noaa_atlas14_precip_reference_summary.json").get("status_counts", {}).get("ok")],
            ],
            "outputs": [
                link_item("output/basin/all/analysis/return_period/tables/return_period_reference_table.csv", "return-period proxy table"),
                link_item("output/basin/all/reference_comparison/usgs_flood/tables/return_period_reference_table_with_usgs.csv", "USGS comparison table"),
                link_item("output/basin/all/reference_comparison/noaa_prec", "NOAA reference folder"),
            ],
            "sources": [
                link_item("scripts/basin/all/build_camelsh_return_period_references.py", "proxy generator"),
                link_item("scripts/basin/reference/fetch_usgs_streamstats_peak_flow_references.py", "USGS fetcher"),
                link_item("scripts/basin/reference/fetch_noaa_atlas14_precip_references.py", "NOAA fetcher"),
            ],
            "caution": "이 값은 official flood inventory가 아니라 CAMELSH forcing/streamflow 기반 proxy 및 보조 reference 비교예요.",
            "tags": ["return period", "USGS", "NOAA", "proxy"],
        },
        {
            "id": "all-event-response",
            "category": "기반 데이터",
            "status": "완료",
            "title": "All-basin observed high-flow event-response",
            "purpose": "prepared pool 전체의 Q99 high-flow event candidate와 basin-level event response summary를 만듭니다.",
            "use": "subset300 대표성, flood-generation typing, ML event-regime stratification의 기준 입력으로 씁니다.",
            "stats": [
                ["basins", all_event.get("processed_basin_count")],
                ["events", all_event.get("total_event_count")],
                ["threshold", "Q99"],
            ],
            "outputs": [
                link_item("output/basin/all/analysis/event_response/tables/event_response_table.csv", "event response table"),
                link_item("output/basin/all/analysis/event_response/tables/event_response_basin_summary.csv", "basin summary"),
            ],
            "sources": [
                link_item("scripts/basin/all/build_camelsh_event_response_table.py", "event-response generator"),
            ],
            "tags": ["event response", "Q99", "prepared pool"],
        },
        {
            "id": "flood-generation-typing",
            "category": "기반 데이터",
            "status": "완료",
            "title": "Rule-based flood-generation typing",
            "purpose": "degree-day v2 규칙으로 high-flow event를 recent precipitation, antecedent precipitation, snowmelt/rain-on-snow, uncertain 후보로 나눕니다.",
            "use": "ML event-regime label이 실제 물리 원인처럼 과해석되지 않도록 interpretable QA/baseline label로 씁니다.",
            "stats": [
                ["events", read_json("output/basin/all/analysis/flood_generation/metadata/flood_generation_typing_summary.json").get("event_count")],
                ["basins", read_json("output/basin/all/analysis/flood_generation/metadata/flood_generation_typing_summary.json").get("basin_count")],
                ["method", "degree_day_v2"],
            ],
            "outputs": [
                link_item("output/basin/all/analysis/flood_generation/tables/flood_generation_event_types.csv", "event labels"),
                link_item("output/basin/all/analysis/flood_generation/tables/flood_generation_basin_summary.csv", "basin summary"),
            ],
            "sources": [
                link_item("scripts/basin/all/build_camelsh_flood_generation_typing.py", "typing generator"),
                link_item("docs/experiment/method/basin/flood_generation_typing.md", "method doc"),
            ],
            "tags": ["degree-day", "event label", "QA"],
        },
        {
            "id": "ml-event-regime",
            "category": "기반 데이터",
            "status": "채택 완료",
            "title": "ML event-regime stratification",
            "purpose": "hydromet descriptor feature로 high-flow events를 Recent rainfall, Antecedent / multi-day rain, Weak-driver / snow-influenced 계열로 나눕니다.",
            "use": "Model error를 event regime별로 해석하는 축입니다. rule label과 함께 sensitivity check로 씁니다.",
            "stats": [
                ["events", all_regime.get("event_count")],
                ["basins", all_regime.get("basin_count")],
                ["variant", all_regime.get("variant")],
            ],
            "outputs": [
                link_item("output/basin/all/analysis/event_regime/tables/selected_variant_event_labels.csv", "selected event labels"),
                link_item("output/basin/all/analysis/event_regime/metadata/selected_variant_visual_summary.json", "visual summary"),
            ],
            "sources": [
                link_item("scripts/basin/event_regime/compare_camelsh_flood_generation_ml_variants.py", "variant comparison"),
                link_item("docs/explain/08_ml_flood_generation_typing.md", "explainer"),
            ],
            "caution": "Weak-driver / snow-influenced label은 snow-dominant causal class가 아니라 descriptor-space cluster로 읽어야 해요.",
            "tags": ["event regime", "KMeans", "hydromet"],
        },
        {
            "id": "primary-overall",
            "category": "모델 비교",
            "status": "완료에 가까움",
            "title": "Primary overall performance",
            "purpose": "validation-selected primary checkpoint에서 Model 1과 Model 2 q50의 overall hydrograph skill을 seed-paired로 비교합니다.",
            "use": "Model 2가 중앙예측 성능을 완전히 망가뜨리지 않았는지 확인하는 guardrail이며, Results 첫 표 후보입니다.",
            "stats": [
                ["official seeds", official_seeds],
                ["primary delta rows", overall.get("primary_delta_rows")],
                ["selected metric files", overall.get("selected_metric_files")],
            ],
            "outputs": [
                link_item("docs/experiment/analysis/model/01_primary_overall_performance.md", "canonical analysis doc"),
                link_item("output/model_analysis/overall_analysis/main_comparison/report/overall_performance_conclusion_strategy.md", "conclusion strategy"),
                link_item("output/model_analysis/overall_analysis/main_comparison/tables/primary_epoch_basin_deltas.csv", "paired basin deltas"),
                link_item("output/model_analysis/overall_analysis/main_comparison/figures/overall_conclusion/overall_conclusion_high_flow_quantiles.png", "high-flow quantile conclusion chart"),
            ],
            "sources": [
                link_item("scripts/model/overall/analyze_subset300_epoch_results.py", "overall analyzer"),
                link_item("scripts/model/overall/summarize_subset300_overall_performance_conclusion.py", "conclusion summarizer"),
            ],
            "caution": "headline은 q50 overall gain이 아니라, q50 guardrail과 q95/q99 upper-tail signal을 분리해서 잡는 게 안전해요.",
            "tags": ["Model 1", "Model 2", "q50", "overall"],
        },
        {
            "id": "high-flow-quantile",
            "category": "모델 비교",
            "status": "완료에 가까움",
            "title": "High-flow / peak quantile analysis",
            "purpose": "Q90/Q95/Q99/Q99.9 exceedance와 observed peak hour에서 Model 2 q90/q95/q99가 peak underestimation을 줄이는지 봅니다.",
            "use": "현재 논문의 핵심 가설인 output design 효과를 뒷받침하는 중심 분석입니다.",
            "stats": [
                ["required-series files", count_files("output/model_analysis/quantile_analysis/required_series", "*.csv")],
                ["hydrograph plots", stats["hydrograph_manifest_rows"]],
                ["flow summary rows", stats["flow_summary_rows"]],
            ],
            "outputs": [
                link_item("docs/experiment/analysis/model/02_primary_high_flow_peak_performance.md", "canonical analysis doc"),
                link_item("output/model_analysis/quantile_analysis/analysis/research_interpretation_summary.md", "analysis summary"),
                link_item("output/model_analysis/quantile_analysis/analysis/flow_strata_predictor_aggregate.csv", "flow strata aggregate"),
                link_item("output/model_analysis/quantile_analysis/analysis/charts/primary_q99_and_peak_quantile_zone_by_seed.png", "primary q99 and peak zone chart"),
                link_item("output/model_analysis/quantile_analysis/analysis/charts/primary_peak_relative_bias_by_seed.png", "peak relative bias chart"),
            ],
            "sources": [
                link_item("scripts/model/hydrograph/analyze_subset300_hydrograph_outputs.py", "hydrograph analyzer"),
                link_item("scripts/model/hydrograph/plot_subset300_hydrographs.py", "hydrograph plotter"),
            ],
            "caution": "q99는 calibrated 99% interval이 아니라 upper-tail decision output으로 표현해야 해요.",
            "tags": ["q95", "q99", "peak", "underestimation"],
        },
        {
            "id": "probabilistic-diagnostics",
            "category": "모델 비교",
            "status": "완료에 가까움",
            "title": "Probabilistic calibration / pinball",
            "purpose": "Model 2 q50/q90/q95/q99의 pinball/AQS, all-hour one-sided calibration, high-flow conditional tail hit-rate, upper-tail spread를 진단합니다.",
            "use": "q99를 calibrated 99% interval처럼 과장하지 않도록 caveat와 calibration evidence를 제공합니다.",
            "stats": [
                ["quantiles", ", ".join(read_json("output/model_analysis/probabilistic_diagnostics/analysis_metadata.json").get("quantiles", {}).keys())],
                ["files", stats["probabilistic_files"]],
                ["figures", count_files("output/model_analysis/probabilistic_diagnostics/figures", "*.png")],
            ],
            "outputs": [
                link_item("docs/experiment/analysis/model/08_probabilistic_calibration_pinball.md", "canonical analysis doc"),
                link_item("output/model_analysis/probabilistic_diagnostics/report/probabilistic_diagnostics_report.md", "diagnostics report"),
                link_item("output/model_analysis/probabilistic_diagnostics/quantile_pinball_summary.csv", "pinball summary"),
                link_item("output/model_analysis/probabilistic_diagnostics/figures/primary_all_quantile_calibration.png", "all-hour calibration chart"),
                link_item("output/model_analysis/probabilistic_diagnostics/figures/primary_pinball_by_stratum.png", "pinball by stratum chart"),
            ],
            "sources": [
                link_item("scripts/model/hydrograph/analyze_subset300_probabilistic_diagnostics.py", "probabilistic diagnostics generator"),
            ],
            "caution": "all-hour stratum만 formal one-sided calibration으로 읽고, Q99 exceedance strata는 conditional tail hit-rate로 읽어야 해요.",
            "tags": ["pinball", "calibration", "AQS"],
        },
        {
            "id": "event-regime-errors",
            "category": "모델 비교",
            "status": "완료에 가까움",
            "title": "Event-regime model error analysis",
            "purpose": "570개 observed high-flow events를 ML event-regime, rule label, flood-relevance tier로 나누어 Model 1/2 error를 해석합니다.",
            "use": "upper quantile 효과가 어떤 event context에서 강한지, 그리고 q99가 event NRMSE를 악화시킬 수 있는지 설명합니다.",
            "stats": [
                ["unique events", event_regime.get("event_count_unique")],
                ["basins", event_regime.get("basin_count")],
                ["seed-event rows", event_regime.get("seed_event_rows")],
            ],
            "outputs": [
                link_item("docs/experiment/analysis/model/03_event_regime_performance.md", "canonical analysis doc"),
                link_item("output/model_analysis/quantile_analysis/event_regime_analysis/event_regime_model_error_report.md", "event-regime report"),
                link_item("output/model_analysis/quantile_analysis/event_regime_analysis/paired_delta_aggregate.csv", "paired delta aggregate"),
            ],
            "sources": [
                link_item("scripts/model/event_regime/analyze_subset300_event_regime_errors.py", "event-regime analyzer"),
                link_item("scripts/model/event_regime/plot_subset300_event_regime_summary.py", "summary plotter"),
            ],
            "caution": "event set은 observed high-flow candidates이지 official flood inventory가 아니에요.",
            "tags": ["event regime", "heterogeneity", "q99"],
        },
        {
            "id": "extreme-flood-proxy",
            "category": "모델 비교",
            "status": "부분 완료",
            "title": "Extreme flood proxy sensitivity",
            "purpose": "return-period proxy tier별로 upper quantile performance를 확인합니다.",
            "use": "high-return-period flood-like events가 적은 상황에서 headline이 아니라 supplement/case sensitivity로 씁니다.",
            "stats": [
                ["ge2 proxy events", event_regime.get("flood_relevance_tier_counts_unique_events", {}).get("flood_like_ge_2yr_proxy")],
                ["ge10 proxy events", event_regime.get("flood_relevance_tier_counts_unique_events", {}).get("flood_like_ge_10yr_proxy")],
                ["ge25 proxy events", event_regime.get("flood_relevance_tier_counts_unique_events", {}).get("flood_like_ge_25yr_proxy")],
            ],
            "outputs": [
                link_item("docs/experiment/analysis/model/04_extreme_flood_proxy_performance.md", "canonical analysis doc"),
                link_item("output/model_analysis/quantile_analysis/event_regime_analysis/flood_relevance_tier_predictor_aggregate.csv", "flood-tier aggregate"),
            ],
            "sources": [
                link_item("scripts/model/event_regime/analyze_subset300_event_regime_errors.py", "event analyzer"),
            ],
            "caution": "high-return-period proxy event 수가 작아서 본문 핵심 주장으로 쓰기에는 약해요.",
            "tags": ["flood proxy", "return period", "sensitivity"],
        },
        {
            "id": "extreme-rain-stress",
            "category": "Stress / case 진단",
            "status": "완료에 가까움",
            "title": "Extreme-rain stress test",
            "purpose": "hourly Rainf에서 직접 만든 historical extreme-rain events로 upper quantile peak tracking과 false-positive tradeoff를 확인합니다.",
            "use": "primary DRBC test를 대체하지 않는 stress/robustness evidence로 쓰며, flow graph와 event plots로 실제 hydrograph 모양을 확인합니다.",
            "stats": [
                ["stress events", primary.get("event_count_unique")],
                ["basins", primary.get("basin_count")],
                ["positive response", primary.get("stress_group_counts_unique_events", {}).get("positive_response")],
                ["negative control", primary.get("stress_group_counts_unique_events", {}).get("negative_control")],
            ],
            "outputs": [
                link_item("docs/experiment/analysis/model/05_extreme_rain_stress_test.md", "canonical analysis doc"),
                link_item("output/model_analysis/extreme_rain/primary/analysis/extreme_rain_stress_test_report.md", "primary stress report"),
                link_item("output/model_analysis/extreme_rain/primary/event_plot_median_map_index.html", "interactive median-map explorer"),
            ],
            "sources": [
                link_item("scripts/model/extreme_rain/build_subset300_extreme_rain_event_catalog.py", "event catalog builder"),
                link_item("scripts/model/extreme_rain/analyze_subset300_extreme_rain_stress_test.py", "stress analyzer"),
                link_item("scripts/model/extreme_rain/build_extreme_rain_median_map_index.py", "map index builder"),
            ],
            "caution": "historical 1980-2024 windows를 포함하므로 temporal independence claim에는 쓰지 않아요.",
            "tags": ["extreme rain", "stress", "false positive"],
        },
        {
            "id": "peak-quantile-bracket",
            "category": "Stress / case 진단",
            "status": "완료",
            "title": "Local peak quantile bracket diagnostic",
            "purpose": "extreme-rain observed response peak가 Model 2 q50/q90/q95/q99 ladder 중 어디에 놓이는지 peak 주변 시간창으로 분류합니다.",
            "use": "case-level peak interpretation에서 exact timing mismatch를 완화해 q95/q99 ladder의 의미를 봅니다.",
            "stats": [
                ["window hours", primary.get("peak_quantile_bracket", {}).get("primary_window_hours")],
                ["sensitivity windows", ", ".join(str(x) for x in primary.get("peak_quantile_bracket", {}).get("sensitivity_window_hours", []))],
                ["charts", primary.get("peak_quantile_bracket", {}).get("chart_count")],
            ],
            "outputs": [
                link_item("output/model_analysis/extreme_rain/primary/analysis/peak_quantile_bracket_event_table.csv", "bracket event table"),
                link_item("output/model_analysis/extreme_rain/primary/analysis/peak_quantile_bracket_summary.csv", "bracket summary"),
                link_item("output/model_analysis/extreme_rain/primary/analysis/figures/peak_quantile_bracket", "bracket figures"),
            ],
            "sources": [
                link_item("scripts/model/extreme_rain/analyze_subset300_extreme_rain_stress_test.py", "stress analyzer"),
            ],
            "caution": "calibrated exceedance probability가 아니라 extreme-rain 조건부 diagnostic이에요.",
            "tags": ["peak bracket", "q ladder", "timing"],
        },
        {
            "id": "checkpoint-sensitivity",
            "category": "Robustness / QA",
            "status": "완료에 가까움",
            "title": "Checkpoint sensitivity",
            "purpose": "primary conclusion이 validation-best checkpoint 하나에만 의존하는지 epoch 005-030 grid로 확인합니다.",
            "use": "primary checkpoint 재선정이 아니라 sensitivity/robustness section의 보조 근거로 씁니다.",
            "stats": [
                ["same-epoch delta rows", overall.get("same_epoch_delta_rows")],
                ["validation epochs", "005, 010, 015, 020, 025, 030"],
                ["official seeds", official_seeds],
            ],
            "outputs": [
                link_item("docs/experiment/analysis/model/06_checkpoint_sensitivity.md", "canonical analysis doc"),
                link_item("output/model_analysis/overall_analysis/epoch_sensitivity/figures/test_same_epoch_delta_summary.png", "same-epoch delta chart"),
                link_item("output/model_analysis/extreme_rain/all/analysis/extreme_rain_stress_test_report.md", "all-epoch stress report"),
            ],
            "sources": [
                link_item("scripts/model/overall/analyze_subset300_epoch_results.py", "epoch analyzer"),
                link_item("scripts/model/overall/plot_subset300_checkpoint_sensitivity_compact.py", "compact sensitivity plotter"),
            ],
            "tags": ["checkpoint", "sensitivity", "epoch"],
        },
        {
            "id": "overfit-risk",
            "category": "Robustness / QA",
            "status": "완료",
            "title": "Overfit / test-oracle risk analysis",
            "purpose": "selected primary epoch가 DRBC test 성능을 보고 고른 것처럼 보이는지, validation loss와 test-oracle gap을 비교합니다.",
            "use": "all-epoch sweep을 주장 선택용으로 쓰지 않고 diagnostic으로만 제한하는 근거입니다.",
            "stats": [
                ["files", count_files("output/model_analysis/overall_analysis/overfit_analysis")],
                ["official runs", 6],
                ["primary loss overfit >=5%", "0/6"],
            ],
            "outputs": [
                link_item("output/model_analysis/overall_analysis/overfit_analysis/report/overfit_analysis_report.md", "overfit report"),
                link_item("output/model_analysis/overall_analysis/overfit_analysis/figures/overfit_quantile_inflation_tradeoff.png", "quantile inflation chart"),
            ],
            "sources": [
                link_item("scripts/model/overall/analyze_subset300_overfit.py", "overfit analyzer"),
            ],
            "caution": "q99는 low-response negative-control에서 inflation risk가 있으므로 conservative upper-tail signal로 제한해야 해요.",
            "tags": ["overfit", "test oracle", "inflation"],
        },
        {
            "id": "median-deviation",
            "category": "Robustness / QA",
            "status": "완료",
            "title": "Metric median-deviation basin regime analysis",
            "purpose": "NSE/KGE/FHV의 basin-level value가 metric/model/seed box median에서 얼마나 떨어졌는지 IQR-normalized tier로 분류합니다.",
            "use": "far/extreme basin이 어떤 hydrologic mechanism과 연결되는지, basin_dissect tier와 map explorer 색을 정하는 기준입니다.",
            "stats": [
                ["records per basin max", 18],
                ["basin reports input", stats["basin_report_count"]],
                ["tier profiles", count_csv_rows("output/model_analysis/overall_analysis/main_comparison/attribute_correlations/median_deviation/tables/metric_median_deviation_basin_tier_profile.csv")],
            ],
            "outputs": [
                link_item("output/model_analysis/overall_analysis/main_comparison/attribute_correlations/median_deviation/report/metric_median_deviation_regime_report_ko.md", "Korean regime report"),
                link_item("output/model_analysis/overall_analysis/main_comparison/attribute_correlations/median_deviation/tables/metric_median_deviation_basin_tier_profile.csv", "basin tier profile"),
                link_item("output/model_analysis/overall_analysis/main_comparison/attribute_correlations/median_deviation/figures/metric_median_deviation_all_basin_distance_tier_stacked_counts.png", "tier stacked counts"),
            ],
            "sources": [
                link_item("scripts/model/overall/analyze_subset300_primary_metric_median_deviation_regimes.py", "median-deviation analyzer"),
            ],
            "caution": "ratio가 다른 유역은 이름/위치가 비슷해도 같은 regime으로 묶지 않는 보수적 grouping을 적용했어요.",
            "tags": ["median deviation", "IQR", "basin tier"],
        },
        {
            "id": "outlier-mechanism",
            "category": "Robustness / QA",
            "status": "완료",
            "title": "Primary metric outlier mechanism deep dive",
            "purpose": "반복 outlier basin을 static attributes, event response, hydromod proxies, extreme-rain stress behavior와 결합해 원인 후보를 분리합니다.",
            "use": "small basin, low observed variance, hydromodification, event response를 한 덩어리로 말하지 않고 mechanism별로 설명할 때 씁니다.",
            "stats": [
                ["outlier audit rows", count_csv_rows("output/model_analysis/overall_analysis/main_comparison/attribute_correlations/robustness/tables/primary_metric_attribute_iqr_outlier_audit.csv")],
                ["basin characteristics rows", count_csv_rows("output/model_analysis/overall_analysis/main_comparison/attribute_correlations/robustness/tables/primary_metric_attribute_outlier_basin_characteristics.csv")],
                ["reports", count_files("output/model_analysis/overall_analysis/main_comparison/attribute_correlations/robustness", "*report*.md")],
            ],
            "outputs": [
                link_item("output/model_analysis/overall_analysis/main_comparison/attribute_correlations/robustness/primary_metric_attribute_outlier_static_attributes_report_ko.md", "static attribute report"),
                link_item("output/model_analysis/overall_analysis/main_comparison/attribute_correlations/robustness/primary_metric_attribute_outlier_event_response_report_ko.md", "event-response report"),
                link_item("output/model_analysis/overall_analysis/main_comparison/attribute_correlations/robustness/tables/primary_metric_attribute_outlier_basin_characteristics.csv", "basin characteristics"),
            ],
            "sources": [
                link_item("scripts/model/overall/analyze_subset300_primary_metric_attribute_outlier_robustness.py", "outlier robustness analyzer"),
                link_item("scripts/model/overall/analyze_subset300_primary_outlier_basin_characteristics.py", "outlier characteristic builder"),
            ],
            "tags": ["outlier", "mechanism", "static attributes"],
        },
        {
            "id": "natural-broad",
            "category": "Robustness / QA",
            "status": "완료에 가까움",
            "title": "Broad vs Natural robustness",
            "purpose": "Broad 38, Natural 8, broad non-natural 30 cohort로 primary overall, high-flow, event-window, extreme-rain stress 방향을 비교합니다.",
            "use": "upper-tail 결론이 hydromodification-risk filtering 후에도 사라지지 않는지 확인하는 robustness check입니다.",
            "stats": [
                ["broad all", natural.get("cohorts", {}).get("broad_all_38")],
                ["natural", natural.get("cohorts", {}).get("natural_8")],
                ["broad non-natural", natural.get("cohorts", {}).get("broad_non_natural_30")],
            ],
            "outputs": [
                link_item("docs/experiment/analysis/model/07_broad_vs_natural_robustness.md", "canonical analysis doc"),
                link_item("output/model_analysis/natural_broad_comparison/report/natural_broad_comparison_report.md", "cohort report"),
                link_item("output/model_analysis/natural_broad_comparison/report/natural_outlier_characteristics_report.md", "natural outlier report"),
            ],
            "sources": [
                link_item("scripts/model/overall/analyze_natural_broad_comparison.py", "cohort analyzer"),
            ],
            "caution": "Natural은 8개뿐이라 effect size가 몇 개 small/low-flow-scale basin에 민감해요.",
            "tags": ["natural", "broad", "robustness"],
        },
        {
            "id": "runoff-ratio",
            "category": "Stress / case 진단",
            "status": "완료",
            "title": "Extreme-rain runoff-ratio diagnostics",
            "purpose": "observed Q와 simQ를 같은 baseline-corrected excess convention으로 비교해 rain-response window denominator 대비 runoff ratio를 봅니다.",
            "use": "extreme-rain case에서 유역별 observed/simulated response가 물리적으로 과하거나 약한지 tier별로 해석할 때 씁니다.",
            "stats": [
                ["files", stats["runoff_ratio_files"]],
                ["basin mapping rows", count_csv_rows("output/model_analysis/extreme_rain/primary/analysis/runoff_ratio_diagnostics/primary_stress_runoff_ratio_iqr_tier_basin_mapping.csv")],
                ["figure checks", count_csv_rows("output/model_analysis/extreme_rain/primary/analysis/runoff_ratio_diagnostics/primary_stress_runoff_ratio_iqr_tier_figure_verify.csv")],
            ],
            "outputs": [
                link_item("output/model_analysis/extreme_rain/primary/analysis/runoff_ratio_diagnostics/primary_stress_runoff_ratio_iqr_tier_summary.csv", "tier summary"),
                link_item("output/model_analysis/extreme_rain/primary/analysis/runoff_ratio_diagnostics/figures/primary_stress_runoff_ratio_boxplot_by_iqr_tier_source_excess_linear_y.png", "linear-y excess boxplot"),
            ],
            "sources": [
                link_item("scripts/model/extreme_rain/analyze_subset300_extreme_rain_stress_test.py", "stress analyzer source"),
            ],
            "caution": "denominator는 event catalog의 rain_response_window_mm 문맥으로 읽어야 하며, figure만 보고 추정하면 안 돼요.",
            "tags": ["runoff ratio", "simQ", "extreme rain"],
        },
        {
            "id": "hydrograph-galleries",
            "category": "Stress / case 진단",
            "status": "완료",
            "title": "Observed Q99+ hydrograph galleries",
            "purpose": "DRBC 38개 basin의 observed Q99+ event hydrograph를 각 basin별 gallery와 map explorer로 보여줍니다.",
            "use": "aggregate metric만으로 설명하기 어려운 case를 눈으로 검토하고, basin_dissect 보고서의 대표 event를 고르는 데 씁니다.",
            "stats": [
                ["basin galleries", stats["hydrograph_gallery_count"]],
                ["hydrograph PNGs", stats["hydrograph_png_count"]],
                ["station notes", stats["station_note_count"]],
            ],
            "outputs": [
                link_item("output/model_analysis/extreme_rain/primary/observed_q99_hydrograph_gallery_index.html", "gallery explorer"),
                link_item("output/model_analysis/extreme_rain/primary/analysis/01480400_hydrograph/index.html", "example basin gallery"),
                link_item("output/model_analysis/extreme_rain/primary/event_plot_median_map_index.html", "event median map"),
            ],
            "sources": [
                link_item("scripts/model/extreme_rain/plot_observed_q99_hydrograph_gallery.py", "gallery generator"),
                link_item("scripts/model/extreme_rain/build_observed_q99_hydrograph_gallery_index.py", "gallery index generator"),
            ],
            "tags": ["hydrograph", "gallery", "case review"],
        },
        {
            "id": "basin-dissect",
            "category": "Stress / case 진단",
            "status": "완료",
            "title": "Basin dissect reports",
            "purpose": "primary wet-footprint stress diagnostic을 basin별로 읽어 station/source check, event inventory, hydrograph interpretation, nearby comparison, final diagnosis를 남깁니다.",
            "use": "event suppression, managed-flow, regulation, forcing mismatch 같은 case-level explanation의 local evidence bundle입니다.",
            "stats": [
                ["unique reports", stats["basin_report_count"]],
                ["tier counts", "27 / 4 / 2 / 5"],
                ["station notes", stats["station_note_count"]],
            ],
            "outputs": [
                link_item("output/model_analysis/extreme_rain/primary/basin_dissect/README.md", "basin dissect README"),
                link_item("output/model_analysis/extreme_rain/primary/basin_dissect/extreme_ge_3_iqr/01480400.md", "example report"),
                link_item("docs/references/basin/usgs_station_notes/README.md", "station notes README"),
            ],
            "sources": [
                link_item("docs/experiment/analysis/model/09_event_suppression_diagnosis_protocol.md", "diagnosis protocol"),
            ],
            "caution": "IQR tier 자체가 원인 진단은 아니고, station evidence와 hydrograph behavior가 함께 맞아야 confidence를 붙일 수 있어요.",
            "tags": ["basin dissect", "station notes", "case diagnosis"],
        },
        {
            "id": "event-suppression-protocol",
            "category": "Stress / case 진단",
            "status": "완료",
            "title": "Event suppression / managed-flow diagnosis protocol",
            "purpose": "extreme-rain event에서 observed flow가 눌리거나, weak rain window에서 managed-flow pulse/plateau가 생기는 case를 진단하는 절차입니다.",
            "use": "metric outlier 원인을 바로 확정하지 않고, station note, rain severity, observed response, model response, nearby comparison 순서로 검증하게 합니다.",
            "stats": [
                ["worked examples", 2],
                ["station notes", stats["station_note_count"]],
                ["primary input branch", "primary"],
            ],
            "outputs": [
                link_item("docs/experiment/analysis/model/09_event_suppression_diagnosis_protocol.md", "protocol doc"),
                link_item("docs/references/basin/usgs_station_notes/01480685_marsh_creek_near_downingtown_pa.md", "example station note"),
            ],
            "sources": [
                link_item("output/model_analysis/extreme_rain/primary/analysis/extreme_rain_stress_error_table_wide.csv", "stress error table"),
                link_item("output/model_analysis/extreme_rain/primary/event_simq_plots/event_simq_plot_manifest.csv", "simQ plot manifest"),
            ],
            "tags": ["managed flow", "suppression", "protocol"],
        },
        {
            "id": "paper-assets",
            "category": "Paper-facing",
            "status": "완료",
            "title": "Paper result assets",
            "purpose": "기존 분석 결과를 Results section에 바로 옮기기 쉬운 compact table, compact figure, representative hydrograph 후보로 줄입니다.",
            "use": "논문 본문 표/그림 후보를 빠르게 고르는 staging area입니다.",
            "stats": [
                ["files", stats["paper_files"]],
                ["candidate types", 3],
                ["candidates each", 5],
            ],
            "outputs": [
                link_item("output/model_analysis/paper_result_assets/report/paper_result_assets_report.md", "paper assets report"),
                link_item("output/model_analysis/paper_result_assets/tables/primary_high_flow_peak_compact.csv", "high-flow compact table"),
                link_item("output/model_analysis/paper_result_assets/tables/representative_hydrograph_candidates.md", "representative candidates"),
            ],
            "sources": [
                link_item("scripts/model/overall/build_subset300_paper_result_assets.py", "paper asset builder"),
            ],
            "caution": "representative hydrograph 후보는 자동 ranking 결과라서 최종 삽입 전 visual inspection이 필요해요.",
            "tags": ["paper", "compact table", "figure candidate"],
        },
    ]


def build_previews() -> list[dict[str, str]]:
    return [
        {
            "title": "Subset300 spatial split",
            "path": "output/basin/all/screening/subset300_spatial_split/figures/subset300_conus_split_map.png",
        },
        {
            "title": "Overall high-flow conclusion",
            "path": "output/model_analysis/overall_analysis/main_comparison/figures/overall_conclusion/overall_conclusion_high_flow_quantiles.png",
        },
        {
            "title": "Primary quantile zones",
            "path": "output/model_analysis/quantile_analysis/analysis/charts/primary_q99_and_peak_quantile_zone_by_seed.png",
        },
        {
            "title": "Probabilistic calibration",
            "path": "output/model_analysis/probabilistic_diagnostics/figures/primary_all_quantile_calibration.png",
        },
        {
            "title": "Natural/Broad high-flow",
            "path": "output/model_analysis/natural_broad_comparison/figures/primary_top1_underestimation_by_cohort.png",
        },
        {
            "title": "Overfit / q99 tradeoff",
            "path": "output/model_analysis/overall_analysis/overfit_analysis/figures/overfit_quantile_inflation_tradeoff.png",
        },
        {
            "title": "Median-deviation tiers",
            "path": "output/model_analysis/overall_analysis/main_comparison/attribute_correlations/median_deviation/figures/metric_median_deviation_all_basin_distance_tier_stacked_counts.png",
        },
        {
            "title": "Runoff ratio by tier",
            "path": "output/model_analysis/extreme_rain/primary/analysis/runoff_ratio_diagnostics/figures/primary_stress_runoff_ratio_boxplot_by_iqr_tier_source_excess_linear_y.png",
        },
    ]


def build_flow() -> list[dict[str, str]]:
    return [
        {"label": "Basin 정의", "detail": "DRBC holdout, non-DRBC pool, quality gate"},
        {"label": "Subset 고정", "detail": "scaling_300 대표성, coverage, spatial split"},
        {"label": "Model 비교", "detail": "overall q50 guardrail, q95/q99 high-flow signal"},
        {"label": "Event 해석", "detail": "event-regime, flood proxy, extreme-rain stress"},
        {"label": "Robustness", "detail": "checkpoint, overfit, Natural/Broad, outlier mechanism"},
        {"label": "Paper assets", "detail": "compact tables, figure candidates, case gallery"},
    ]


def status_class(status: str) -> str:
    if "부분" in status:
        return "partial"
    if "가까움" in status:
        return "near"
    if "채택" in status:
        return "adopted"
    return "done"


def material_kind(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if path.startswith("docs/"):
        return "문서"
    if path.startswith("scripts/"):
        return "생성 script"
    if suffix in {".png", ".jpg", ".jpeg", ".svg", ".webp"}:
        return "Figure"
    if suffix in {".csv", ".tsv", ".xlsx", ".parquet"}:
        return "Table"
    if suffix in {".json", ".yaml", ".yml"}:
        return "Metadata"
    if suffix == ".html":
        return "Interactive"
    if suffix == ".md":
        return "Report"
    if suffix == ".shp":
        return "Boundary"
    return "Folder" if (REPO_ROOT / path).is_dir() else "Artifact"


def group_for_analysis(analysis_id: str) -> dict[str, Any]:
    return GROUP_BY_ANALYSIS_ID.get(
        analysis_id,
        {
            "id": "ungrouped",
            "label": "미분류",
            "description": "큰 그룹에 아직 배치되지 않은 분석입니다.",
            "analysis_ids": [],
        },
    )


def summarize_stats(stats: list[list[str]]) -> str:
    if not stats:
        return "핵심 수치는 연결 자료에서 직접 확인합니다."
    return ", ".join(f"{label} {value}" for label, value in stats[:3])


def summarize_materials(items: list[dict[str, Any]], kinds: set[str] | None = None) -> str:
    candidates = [
        item["label"]
        for item in items
        if not kinds or str(item.get("kind", "")) in kinds
    ]
    if not candidates:
        return ""
    if len(candidates) == 1:
        return candidates[0]
    return ", ".join(candidates[:2])


def is_media_path(path: str) -> bool:
    return Path(path).suffix.lower() in {".png", ".jpg", ".jpeg", ".svg", ".webp"}


def image_dimensions(path: str) -> dict[str, int]:
    target = REPO_ROOT / path
    if not target.exists() or target.suffix.lower() != ".png":
        return {}
    try:
        header = target.read_bytes()[:24]
    except OSError:
        return {}
    if header[:8] != b"\x89PNG\r\n\x1a\n" or len(header) < 24:
        return {}
    return {
        "width": int.from_bytes(header[16:20], "big"),
        "height": int.from_bytes(header[20:24], "big"),
    }


def image_attr_text(item: dict[str, Any]) -> str:
    width = item.get("width")
    height = item.get("height")
    if not width or not height:
        return ""
    return f' width="{html.escape(str(width))}" height="{html.escape(str(height))}"'


def detail_steps(item: dict[str, Any]) -> list[dict[str, str]]:
    source_labels = summarize_materials(item.get("sources", []))
    output_labels = summarize_materials(item.get("outputs", []))
    figure_labels = summarize_materials(
        [*item.get("outputs", []), *item.get("sources", [])],
        {"Figure", "Interactive"},
    )
    table_labels = summarize_materials(
        [*item.get("outputs", []), *item.get("sources", [])],
        {"Table", "Metadata"},
    )
    stats_summary = summarize_stats(item.get("stats", []))
    return [
        {
            "label": "근거 수집",
            "body": (
                f"{source_labels}를 기준으로 입력 자료와 생성 절차를 먼저 확인합니다."
                if source_labels
                else "canonical docs와 metadata manifest를 먼저 확인해 분석 입력을 고정합니다."
            ),
        },
        {
            "label": "계산과 비교 수행",
            "body": f"{item.get('purpose', '')} 이 단계에서 모델, 유역, event, quantile 기준을 같은 축으로 맞춥니다.",
        },
        {
            "label": "시각 자료 확인",
            "body": (
                f"{figure_labels}에서 패턴, 방향성, 이상 case를 먼저 눈으로 확인합니다."
                if figure_labels
                else f"{table_labels or output_labels}처럼 표와 문서 중심 자료에서 패턴을 확인합니다."
            ),
        },
        {
            "label": "수치 근거 점검",
            "body": f"{stats_summary}를 headline 수치로 보고, 연결된 table에서 basin/event/seed 단위 근거를 확인합니다.",
        },
        {
            "label": "해석과 한계 정리",
            "body": item.get("caution") or item.get("use", "분석 결과의 쓰임과 한계를 함께 정리합니다."),
        },
    ]


def detail_story(item: dict[str, Any]) -> dict[str, list[str]]:
    resources = [*item.get("outputs", []), *item.get("sources", [])]
    figure_labels = summarize_materials(resources, {"Figure", "Interactive"})
    table_labels = summarize_materials(resources, {"Table", "Metadata"})
    report_labels = summarize_materials(resources, {"문서", "Report"})
    stats_summary = summarize_stats(item.get("stats", []))
    group_label = item.get("groupLabel", "분석")

    visual_note = (
        f"{figure_labels}에서는 선, 막대, 지도, gallery의 상대적 차이를 보면서 어느 모델이나 event 그룹이 튀는지 확인합니다."
        if figure_labels
        else "이 항목은 figure보다 표와 문서가 중심입니다. 그래서 시각 해석은 숫자 table의 행/열 패턴과 연결 문서의 결론 흐름을 기준으로 봅니다."
    )
    numeric_note = (
        f"{table_labels}와 핵심 수치({stats_summary})를 함께 보면서 분석 규모와 비교 단위를 확인합니다."
        if table_labels
        else f"핵심 수치({stats_summary})를 먼저 보고, linked report에서 그 수치가 어떤 조건에서 나온 값인지 확인합니다."
    )
    source_note = (
        f"{report_labels}는 이 dashboard의 짧은 설명보다 더 긴 해석과 caveat를 담고 있어요."
        if report_labels
        else "연결된 script와 metadata는 이 분석이 재현 가능한 절차로 만들어졌는지 확인하는 근거입니다."
    )

    return {
        "plain": [
            f"이 분석은 {group_label} 그룹에 속하며, 핵심 질문은 '{item.get('purpose', '')}'입니다.",
            f"쉽게 말하면 여러 유역과 event를 같은 기준으로 맞춰 놓고, Model 1과 Model 2 또는 관련 진단 결과가 어디에서 달라지는지 확인하는 작업이에요.",
            f"이 결과는 {item.get('use', '')}",
        ],
        "visual": [visual_note, source_note],
        "numeric": [
            numeric_note,
            "숫자는 단독 결론이 아니라 seed, event, basin, cohort 같은 비교 단위와 같이 읽어야 합니다.",
        ],
        "takeaways": [
            item.get("use", ""),
            item.get("caution", "연결 자료의 수치와 그림을 함께 읽어야 과한 결론을 피할 수 있습니다."),
        ],
    }


def build_group_summaries(analyses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {item["id"]: item for item in analyses}
    summaries: list[dict[str, Any]] = []
    for group in ANALYSIS_GROUPS:
        items = [by_id[analysis_id] for analysis_id in group["analysis_ids"] if analysis_id in by_id]
        resources = [resource for item in items for resource in [*item.get("outputs", []), *item.get("sources", [])]]
        status_counts: dict[str, int] = {}
        for item in items:
            status = item.get("statusClass", "done")
            status_counts[status] = status_counts.get(status, 0) + 1
        narrative = GROUP_NARRATIVES.get(group["id"], {})
        summaries.append(
            {
                "id": group["id"],
                "label": group["label"],
                "description": group["description"],
                "question": narrative.get("question", group["description"]),
                "answer": narrative.get("answer", group["description"]),
                "evidence": narrative.get("evidence", ""),
                "caution": narrative.get("caution", ""),
                "analysisIds": [item["id"] for item in items],
                "analysisCount": len(items),
                "resourceCount": len(resources),
                "figureCount": sum(1 for resource in resources if resource.get("kind") in {"Figure", "Interactive"}),
                "tableCount": sum(1 for resource in resources if resource.get("kind") in {"Table", "Metadata"}),
                "doneCount": status_counts.get("done", 0) + status_counts.get("adopted", 0),
                "nearCount": status_counts.get("near", 0),
                "partialCount": status_counts.get("partial", 0),
            }
        )
    return summaries


def write_json_manifest(output_dir: Path, payload: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "analysis_dashboard_data.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def render_html(output_dir: Path, payload: dict[str, Any]) -> str:
    analyses = payload["analyses"]
    categories = list(dict.fromkeys(item["category"] for item in analyses))
    stat_tiles = [
        ("분석 항목", len(analyses)),
        ("공식 seed", "111 / 222 / 444"),
        ("DRBC test basin", payload["stats"].get("primary", {}).get("basin_count")),
        ("Q99+ hydrograph", payload["stats"].get("hydrograph_png_count")),
        ("Basin report", payload["stats"].get("basin_report_count")),
        ("Station note", payload["stats"].get("station_note_count")),
    ]
    verdict_tiles = [
        ("전체 성능", "q50 guardrail 유지", "primary metric과 checkpoint sensitivity를 먼저 확인"),
        ("High-flow", "q95/q99 개선 신호", "peak bracket과 flood proxy에서 첨두 과소추정 완화 여부 확인"),
        ("Event stress", "사건별 반응 분리", "extreme-rain, runoff-ratio, hydrograph를 같은 축에서 비교"),
        ("Robustness", "유역별 예외 추적", "Natural/Broad, outlier mechanism, basin dissect로 결론 보강"),
    ]
    stat_tiles_html = "".join(
        f'<div class="stat"><span>{html.escape(str(label))}</span><strong>{html.escape(fmt_count(value))}</strong></div>'
        for label, value in stat_tiles
    )
    verdict_tiles_html = "".join(
        f"""
        <div class="verdict-card">
          <span>{html.escape(label)}</span>
          <strong>{html.escape(headline)}</strong>
          <small>{html.escape(detail)}</small>
        </div>
        """
        for label, headline, detail in verdict_tiles
    )

    preview_items = []
    for item in payload["previews"]:
        path = REPO_ROOT / item["path"]
        if not path.exists():
            continue
        image_attrs = image_attr_text(item)
        preview_items.append(
            f"""
            <figure class="preview">
              <img src="{html.escape(item['href'])}" alt="{html.escape(item['title'])}"{image_attrs} loading="lazy">
              <figcaption>{html.escape(item['title'])}</figcaption>
            </figure>
            """
        )
    primary_preview = preview_items[1] if len(preview_items) > 1 else (preview_items[0] if preview_items else "")
    secondary_preview_items = preview_items[:1] + preview_items[2:] if len(preview_items) > 1 else preview_items[1:]
    secondary_preview_html = "".join(secondary_preview_items)

    flow_items = "\n".join(
        f"""
        <li>
          <span class="flow-dot"></span>
          <div>
            <strong>{html.escape(item['label'])}</strong>
            <p>{html.escape(item['detail'])}</p>
          </div>
        </li>
        """
        for item in payload["flow"]
    )

    category_buttons = "\n".join(
        f'<button class="chip" data-category="{html.escape(category)}" type="button">{html.escape(category)}</button>'
        for category in categories
    )
    group_filter_buttons = "\n".join(
        f'<button class="group-chip" data-group="{html.escape(group["id"])}" type="button">{html.escape(group["label"])}</button>'
        for group in payload["groups"]
    )

    payload_for_page = json.dumps(payload, ensure_ascii=False)

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Probabilistic Head 분석 대시보드</title>
  <style>
    :root {{
      color-scheme: light;
      --primary: #0066cc;
      --primary-focus: #0071e3;
      --primary-on-dark: #2997ff;
      --primary-foreground: #ffffff;
      --ink: #1d1d1f;
      --muted: #7a7a7a;
      --muted-foreground: #7a7a7a;
      --muted-strong: #333333;
      --canvas: #ffffff;
      --card: #ffffff;
      --parchment: #f5f5f7;
      --pearl: #fafafc;
      --secondary: #f5f5f7;
      --secondary-foreground: #333333;
      --accent: #ffffff;
      --hairline: #e0e0e0;
      --border: #e0e0e0;
      --input: rgba(0, 0, 0, 0.08);
      --divider: #f0f0f0;
      --dark: #272729;
      --dark-2: #2a2a2c;
      --black: #000000;
      --background: var(--parchment);
      --foreground: var(--ink);
      --radius: 18px;
      --product-shadow: rgba(0, 0, 0, 0.22) 3px 5px 30px 0;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "SF Pro Text", ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--parchment);
      color: var(--ink);
      line-height: 1.47;
    }}
    a {{ color: var(--primary); text-decoration-thickness: 1px; text-underline-offset: 3px; }}
    button {{ font: inherit; }}
    h1, h2, h3, p, figcaption, strong, small, span, code, a, button {{
      min-width: 0;
    }}
    .global-nav {{
      height: 44px;
      background: var(--black);
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
    }}
    .global-nav-inner {{
      width: min(100%, 1440px);
      padding: 0 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
    }}
    .global-nav .mark {{ font-weight: 600; }}
    .global-nav span {{ color: #d2d2d7; }}
    .sr-only {{
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }}
    .sub-nav {{
      position: sticky;
      top: 0;
      z-index: 20;
      height: 52px;
      background: rgba(245, 245, 247, 0.86);
      border-bottom: 1px solid rgba(0, 0, 0, 0.08);
      backdrop-filter: saturate(180%) blur(20px);
    }}
    .sub-nav-inner {{
      width: min(100%, 1440px);
      height: 100%;
      margin: 0 auto;
      padding: 0 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
    }}
    .sub-title {{ font-size: 21px; font-weight: 600; }}
    .sub-actions {{ display: flex; align-items: center; gap: 10px; color: var(--muted-strong); font-size: 14px; }}
    .primary-pill {{
      min-height: 44px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 0;
      border-radius: 9999px;
      padding: 11px 22px;
      background: var(--primary);
      color: var(--primary-foreground);
      text-decoration: none;
      cursor: pointer;
    }}
    .primary-pill:active, .chip:active, .analysis-card:active {{ transform: scale(0.95); }}
    .page {{ width: 100%; }}
    [id] {{ scroll-margin-top: 112px; }}
    .hero {{
      background: var(--canvas);
      padding: 26px 24px 20px;
      border-bottom: 1px solid var(--hairline);
    }}
    .hero-inner {{
      width: min(100%, 1440px);
      margin: 0 auto;
      display: grid;
      grid-template-columns: minmax(0, 0.92fr) minmax(440px, 1.08fr);
      align-items: start;
      gap: 24px;
      text-align: left;
    }}
    .hero-inner > *,
    .group-shell > *,
    .filter-panel > *,
    .filter-row > *,
    .card-head > *,
    .resource-row > *,
    .viewer-toolbar > *,
    .preview > * {{
      min-width: 0;
    }}
    .hero-copy {{
      min-width: 0;
      display: grid;
      gap: 10px;
      align-content: start;
    }}
    .eyebrow {{ color: var(--primary); font-size: 14px; font-weight: 600; margin: 0; }}
    h1 {{
      font-family: "SF Pro Display", ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 42px;
      line-height: 1.09;
      letter-spacing: 0;
      font-weight: 600;
      margin: 0;
      overflow-wrap: anywhere;
    }}
    .lead {{
      font-size: 18px;
      color: var(--muted-strong);
      margin: 0;
      max-width: 820px;
      overflow-wrap: anywhere;
    }}
    .mobile-title-break {{ display: none; }}
    .verdict-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      margin-top: 4px;
    }}
    .verdict-card {{
      min-width: 0;
      display: grid;
      gap: 4px;
      background: var(--pearl);
      border: 1px solid var(--hairline);
      border-radius: 12px;
      padding: 12px;
    }}
    .verdict-card span {{
      color: var(--muted);
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .verdict-card strong {{
      font-size: 16px;
      line-height: 1.2;
      overflow-wrap: anywhere;
    }}
    .verdict-card small {{
      color: var(--muted-strong);
      font-size: 12px;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }}
    .hero-preview-panel {{
      min-width: 0;
      background: var(--pearl);
      border: 1px solid var(--hairline);
      border-radius: 18px;
      padding: 14px;
      display: grid;
      gap: 12px;
    }}
    .hero-panel-head {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      min-width: 0;
    }}
    .hero-panel-head div {{
      display: grid;
      gap: 2px;
      min-width: 0;
    }}
    .hero-panel-head span {{ color: var(--muted); font-size: 12px; }}
    .hero-panel-head strong {{ font-size: 15px; line-height: 1.25; }}
    .hero-panel-head code {{
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
      max-width: 46%;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .hero-preview-slot {{ min-width: 0; }}
    .hero-preview-slot .preview {{
      padding: 0;
      min-height: 0;
      gap: 10px;
      background: transparent;
    }}
    .hero-preview-slot .preview img {{
      height: 255px;
      box-shadow: none;
      border: 1px solid var(--hairline);
      background: var(--canvas);
    }}
    .hero-preview-slot .preview figcaption {{
      color: var(--muted-strong);
      font-size: 13px;
    }}
    .dashboard-summary {{
      background: var(--canvas);
      border-bottom: 1px solid var(--hairline);
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 1px;
      background: var(--hairline);
      width: min(100%, 1440px);
      margin: 0 auto;
    }}
    .stat {{
      background: var(--canvas);
      padding: 18px 22px;
      min-height: 84px;
    }}
    .stat span {{ color: var(--muted); font-size: 12px; display: block; }}
    .stat strong {{ font-size: 24px; letter-spacing: 0; font-variant-numeric: tabular-nums; }}
    .overview-stack {{
      width: min(100%, 1440px);
      margin: 0 auto;
      padding: 6px 24px 44px;
      display: grid;
      gap: 22px;
    }}
    .overview-heading {{
      display: grid;
      gap: 6px;
      padding-top: 16px;
    }}
    .overview-heading h2 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.16;
    }}
    .overview-heading p {{ margin: 0; color: var(--muted-strong); }}
    .group-overview {{
      width: 100%;
      margin: 0;
      padding: 0;
      background: var(--parchment);
    }}
    .group-primary {{
      background: transparent;
    }}
    .group-shell {{
      display: grid;
      grid-template-columns: minmax(0, 1.08fr) minmax(340px, 0.92fr);
      gap: 18px 24px;
      align-items: stretch;
      min-width: 0;
      background: transparent;
      border: 0;
      border-radius: 0;
      padding: 0;
    }}
    .group-header {{
      grid-column: 1 / -1;
      min-width: 0;
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      gap: 20px;
      padding: 2px 2px 0;
    }}
    .group-left {{
      min-width: 0;
      display: grid;
    }}
    .group-copy {{
      min-width: 0;
      display: grid;
      align-content: start;
      gap: 10px;
    }}
    .group-copy h2 {{
      margin: 0;
      font-size: 26px;
      line-height: 1.15;
      letter-spacing: 0;
    }}
    .group-copy p {{ margin: 0; color: var(--muted-strong); }}
    .group-header .chip {{
      flex: 0 0 auto;
    }}
    .group-evidence {{
      min-width: 0;
      align-self: stretch;
      padding: 22px;
      display: grid;
      grid-template-rows: auto auto minmax(0, 1fr);
      gap: 16px;
      min-height: 0;
      background: var(--canvas);
      border: 1px solid var(--hairline);
      border-radius: 14px;
    }}
    .group-evidence h3 {{
      margin: 0;
      font-size: 18px;
      line-height: 1.2;
    }}
    .group-evidence p {{
      margin: 0;
      color: var(--muted);
      font-size: 14px;
    }}
    .evidence-bars {{
      display: grid;
      gap: 12px;
      align-content: space-between;
      min-height: 0;
    }}
    .evidence-row {{
      display: grid;
      gap: 8px;
      min-width: 0;
      padding: 8px 0 12px;
      border-bottom: 1px solid var(--divider);
    }}
    .evidence-row:last-child {{ border-bottom: 0; padding-bottom: 0; }}
    .evidence-row-top {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      font-size: 12px;
      color: var(--muted-strong);
      min-width: 0;
    }}
    .evidence-row-top span:first-child {{
      color: var(--ink);
      font-size: 14px;
      font-weight: 700;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .evidence-answer {{
      margin: 0;
      color: var(--ink);
      font-size: 13px;
      line-height: 1.35;
    }}
    .evidence-caution {{
      margin: 0;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
    }}
    .evidence-bar {{
      height: 9px;
      border-radius: 999px;
      background: var(--canvas);
      border: 1px solid var(--hairline);
      overflow: hidden;
    }}
    .evidence-fill {{
      height: 100%;
      width: var(--evidence-width);
      background: var(--primary);
    }}
    .radial-chart svg {{
      width: 100%;
      max-width: 420px;
      height: auto;
      overflow: visible;
    }}
    .radial-segment {{
      cursor: pointer;
      outline: none;
    }}
    .radial-segment text {{
      font-size: 11px;
      fill: var(--muted-strong);
    }}
    .radar-axis {{
      stroke: var(--hairline);
      stroke-width: 1;
    }}
    .radar-area {{
      fill: rgba(0, 102, 204, 0.12);
      stroke: var(--primary);
      stroke-width: 2;
      stroke-linejoin: round;
    }}
    .radar-point {{
      fill: var(--canvas);
      stroke: var(--primary);
      stroke-width: 2;
      transition: fill 160ms ease, r 160ms ease;
    }}
    .radial-segment.active .radar-point,
    .radial-segment:hover .radar-point {{
      fill: var(--primary);
      r: 6;
    }}
    .radial-grid {{
      stroke: var(--hairline);
      fill: none;
    }}
    .radial-center text:first-child {{
      font-size: 30px;
      font-weight: 600;
      fill: var(--ink);
    }}
    .radial-center text:last-child {{
      font-size: 12px;
      fill: var(--muted);
    }}
    .group-cards {{
      min-width: 0;
      padding: 0;
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      align-content: start;
    }}
    .group-card {{
      width: 100%;
      min-width: 0;
      border: 1px solid var(--divider);
      border-radius: 12px;
      background: var(--canvas);
      color: var(--ink);
      padding: 14px;
      display: grid;
      gap: 9px;
      align-content: start;
      text-align: left;
      cursor: pointer;
      overflow: hidden;
      min-height: 0;
    }}
    .group-card.active {{
      border-color: var(--primary);
      background: var(--pearl);
      outline: 1px solid var(--primary);
    }}
    .group-card h3 {{
      margin: 0;
      font-size: 16px;
      line-height: 1.2;
      letter-spacing: 0;
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .group-card p {{
      margin: 0;
      color: var(--muted);
      font-size: 13px;
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .group-kicker {{
      color: var(--muted);
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .group-question {{
      color: var(--muted-strong) !important;
    }}
    .group-answer {{
      display: block;
      font-size: 14px;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }}
    .group-evidence-line,
    .group-caution-line {{
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }}
    .group-caution-line {{
      color: #6f5b00;
    }}
    .group-card .group-question,
    .group-card .group-answer,
    .group-card .group-evidence-line,
    .group-card .group-caution-line {{
      display: -webkit-box;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }}
    .group-card .group-question,
    .group-card .group-answer {{
      -webkit-line-clamp: 2;
    }}
    .group-card .group-evidence-line,
    .group-card .group-caution-line {{
      -webkit-line-clamp: 1;
    }}
    .group-metrics {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 6px;
    }}
    .group-metric {{
      border-radius: 10px;
      background: var(--parchment);
      padding: 7px;
      min-width: 0;
    }}
    .group-metric span {{
      display: block;
      color: var(--muted);
      font-size: 10px;
      overflow-wrap: anywhere;
    }}
    .group-metric strong {{
      display: block;
      font-size: 15px;
      font-variant-numeric: tabular-nums;
      overflow-wrap: anywhere;
    }}
    .group-foot {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px 10px;
      color: var(--muted);
      font-size: 12px;
      border-top: 1px solid var(--divider);
      padding-top: 8px;
      margin-top: 1px;
    }}
    .group-links {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 6px;
      padding-top: 2px;
      min-width: 0;
    }}
    .group-link {{
      appearance: none;
      border: 1px solid var(--primary);
      border-radius: 9999px;
      background: var(--canvas);
      color: var(--primary);
      cursor: pointer;
      min-height: 30px;
      padding: 6px 9px;
      font: inherit;
      font-size: 12px;
      min-width: 0;
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .group-link:hover {{
      background: var(--pearl);
    }}
    .previews {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 1px;
      background: var(--hairline);
      width: 100%;
      margin: 0;
      border: 1px solid var(--hairline);
      border-radius: 18px;
      overflow: hidden;
    }}
    .preview {{
      margin: 0;
      background: var(--canvas);
      min-height: 320px;
      padding: 24px;
      display: grid;
      align-content: space-between;
      gap: 18px;
    }}
    .preview img {{
      width: 100%;
      max-width: 100%;
      min-width: 0;
      height: 220px;
      aspect-ratio: 4 / 3;
      object-fit: contain;
      display: block;
      background: var(--pearl);
      border-radius: 8px;
      box-shadow: var(--product-shadow);
    }}
    .preview figcaption {{
      font-size: 14px;
      color: var(--muted);
      overflow-wrap: anywhere;
    }}
    .workspace {{
      width: min(100%, 1440px);
      margin: 0 auto;
      padding: 18px 24px 34px;
      display: grid;
      grid-template-columns: 1fr;
      gap: 18px;
      align-items: start;
    }}
    .workspace > * {{ min-width: 0; }}
    .workspace-tools {{
      position: sticky;
      top: 52px;
      z-index: 12;
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 10px;
      align-items: stretch;
      padding: 12px 0;
      background: rgba(245, 245, 247, 0.92);
      backdrop-filter: saturate(180%) blur(18px);
    }}
    .panel {{
      background: var(--canvas);
      border: 1px solid var(--hairline);
      border-radius: 18px;
      padding: 18px;
    }}
    .panel h2 {{ font-size: 16px; margin: 0 0 12px; letter-spacing: 0; }}
    .filter-panel {{
      min-width: 0;
      display: grid;
      grid-template-columns: minmax(280px, 1fr) auto;
      gap: 10px 14px;
      align-items: center;
      padding: 10px 14px;
    }}
    .filter-panel > h2 {{
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }}
    .filter-row {{
      display: grid;
      grid-template-columns: minmax(180px, 1fr) auto;
      gap: 10px;
      min-width: 0;
    }}
    .search {{
      width: 100%;
      border: 1px solid rgba(0, 0, 0, 0.08);
      border-radius: 9999px;
      min-height: 40px;
      padding: 10px 18px;
      font: inherit;
      background: var(--canvas);
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      justify-content: flex-end;
      min-width: 0;
    }}
    .group-filter {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; min-width: 0; }}
    .chip {{
      min-height: 40px;
      border: 1px solid var(--divider);
      border-radius: 9999px;
      background: var(--canvas);
      color: var(--ink);
      padding: 8px 14px;
      font: inherit;
      cursor: pointer;
      white-space: nowrap;
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .group-filter {{
      grid-column: 1 / -1;
      padding-top: 2px;
    }}
    .flow-guide {{
      background: transparent;
      border: 0;
      padding: 2px 2px 0;
    }}
    .flow-guide h2 {{
      margin: 0 0 10px;
      font-size: 13px;
      color: var(--muted);
    }}
    .flow {{ list-style: none; padding: 0; margin: 0; display: flex; flex-wrap: wrap; gap: 8px 14px; min-width: 0; }}
    .flow li {{ display: inline-flex; align-items: center; gap: 7px; min-width: 0; }}
    .flow-dot {{ width: 7px; height: 7px; border-radius: 50%; border: 1px solid var(--primary); flex: 0 0 auto; }}
    .flow strong {{ font-size: 12px; white-space: nowrap; }}
    .flow p {{ display: none; }}
    .group-filter-label {{
      color: var(--muted);
      font-size: 12px;
      flex: 0 0 auto;
    }}
    .group-chip {{
      min-height: 32px;
      border: 1px solid var(--divider);
      border-radius: 9999px;
      background: var(--pearl);
      color: var(--muted-strong);
      padding: 6px 10px;
      font: inherit;
      font-size: 12px;
      cursor: pointer;
      white-space: nowrap;
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .group-chip.active {{
      border-color: var(--primary);
      color: var(--primary);
      background: var(--canvas);
    }}
    .workspace.is-tools-stuck .workspace-tools {{
      grid-template-columns: minmax(0, 1fr);
      gap: 8px;
      align-items: stretch;
      padding: 8px 0;
    }}
    .workspace.is-tools-stuck .panel {{
      border-radius: 14px;
      padding: 12px 14px;
    }}
    .workspace.is-tools-stuck .panel h2 {{ font-size: 14px; margin: 0; }}
    .workspace.is-tools-stuck .filter-panel {{
      grid-template-columns: minmax(280px, 1fr) auto;
      align-items: center;
      gap: 8px 12px;
    }}
    .workspace.is-tools-stuck .filter-panel h2 {{ display: none; }}
    .workspace.is-tools-stuck .filter-row {{ gap: 8px; }}
    .workspace.is-tools-stuck .search {{ min-height: 36px; padding: 8px 14px; font-size: 14px; }}
    .workspace.is-tools-stuck .filter-panel .chips {{ display: flex; }}
    .workspace.is-tools-stuck .group-filter {{ display: none; }}
    .workspace.is-tools-stuck .chip {{ min-height: 34px; padding: 7px 12px; font-size: 14px; }}
    .chip.active {{ border-color: var(--primary); background: var(--canvas); color: var(--primary); }}
    .summary-line {{ color: var(--muted); margin: 0 0 14px; }}
    .analysis-stage {{
      min-width: 0;
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 18px;
      align-items: start;
      transition: grid-template-columns 200ms ease;
    }}
    .workspace.has-selection .analysis-stage {{
      grid-template-columns: minmax(260px, 340px) minmax(0, 1fr);
    }}
    .list-pane {{
      min-width: 0;
      transition: opacity 180ms ease;
    }}
    .workspace.has-selection .list-pane {{
      height: auto;
      min-height: 0;
      overflow: visible;
      padding-right: 0;
    }}
    .card-grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 12px;
    }}
    .workspace.is-list-only .card-grid {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
      align-items: stretch;
    }}
    .analysis-card {{
      width: 100%;
      min-width: 0;
      overflow: hidden;
      text-align: left;
      background: var(--canvas);
      border: 1px solid var(--hairline);
      border-radius: 14px;
      padding: 18px;
      display: grid;
      gap: 10px;
      cursor: pointer;
      color: var(--ink);
      transition: border-color 180ms ease, outline-color 180ms ease, padding 220ms ease, transform 220ms ease;
    }}
    .analysis-card.selected {{ border-color: var(--primary); outline: 1px solid var(--primary); }}
    .workspace.has-selection .analysis-card {{
      border-radius: 14px;
      padding: 16px;
      gap: 10px;
    }}
    .workspace.has-selection .detail-cue {{
      display: none;
    }}
    .workspace.has-selection .analysis-card .category-label {{
      font-size: 11px;
    }}
    .workspace.has-selection .analysis-card .card-head h3 {{
      font-size: 16px;
    }}
    .workspace.has-selection .analysis-card .card-text {{
      gap: 4px;
    }}
    .workspace.has-selection .analysis-card .card-text p {{
      font-size: 13px;
      color: var(--muted-strong);
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }}
    .analysis-card:focus-visible, .chip:focus-visible, .group-chip:focus-visible, .search:focus-visible, .primary-pill:focus-visible, .group-card:focus-visible, .group-link:focus-visible {{
      outline: 2px solid var(--primary-focus);
      outline-offset: 3px;
    }}
    .card-head {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; min-width: 0; }}
    .card-head h3 {{
      min-width: 0;
      margin: 0;
      font-size: 19px;
      line-height: 1.19;
      letter-spacing: 0;
      overflow-wrap: anywhere;
    }}
    .badge {{
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 12px;
      white-space: nowrap;
      flex: 0 0 auto;
      border: 1px solid var(--divider);
      background: var(--pearl);
      color: var(--muted-strong);
    }}
    .badge.adopted, .badge.near {{ color: var(--primary); border-color: var(--primary); background: var(--canvas); }}
    .category-label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0; }}
    .card-text {{ display: grid; gap: 8px; }}
    .card-text p {{ margin: 0; overflow-wrap: anywhere; }}
    .card-text .purpose-line {{
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
      color: var(--muted-strong);
    }}
    .card-text b {{ color: var(--ink); }}
    .detail-cue {{ color: var(--primary); font-size: 14px; }}
    .stat-list {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(min(100%, 88px), 1fr));
      gap: 8px;
    }}
    .mini-stat {{
      border: 1px solid var(--hairline);
      border-radius: 18px;
      padding: 10px;
      background: var(--pearl);
      min-width: 0;
    }}
    .mini-stat span {{ display: block; color: var(--muted); font-size: 11px; overflow-wrap: anywhere; }}
    .mini-stat strong {{ display: block; font-size: 16px; overflow-wrap: anywhere; }}
    .links {{ display: grid; gap: 8px; }}
    .link-group {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .link-group a {{
      display: inline-flex;
      align-items: center;
      min-height: 32px;
      border: 1px solid var(--primary);
      border-radius: 9999px;
      padding: 7px 12px;
      background: var(--canvas);
      font-size: 14px;
      text-decoration: none;
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .caution {{
      border: 1px solid var(--hairline);
      padding: 12px 14px;
      background: var(--parchment);
      color: var(--muted-strong);
      border-radius: 18px;
      font-size: 14px;
    }}
    .tags {{
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      align-items: flex-start;
      align-content: flex-start;
    }}
    .tag {{
      display: inline-flex;
      align-items: center;
      flex: 0 0 auto;
      width: max-content;
      max-width: 180px;
      min-height: 24px;
      color: var(--muted-strong);
      background: var(--parchment);
      border-radius: 999px;
      padding: 4px 9px;
      font-size: 12px;
      line-height: 1;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .empty {{ display: none; padding: 26px; background: var(--canvas); border: 1px solid var(--hairline); border-radius: 18px; }}
    .detail-panel {{
      background: var(--canvas);
      border: 1px solid var(--hairline);
      border-radius: 18px;
      height: auto;
      min-height: 0;
      min-width: 0;
      overflow: visible;
      padding: 24px;
      opacity: 0;
      transform: translateY(12px);
      pointer-events: none;
      display: none;
    }}
    .workspace.has-selection .detail-panel {{
      display: block;
      opacity: 1;
      transform: translateY(0);
      pointer-events: auto;
      animation: detail-enter 240ms ease both;
    }}
    @keyframes detail-enter {{
      from {{ opacity: 0; transform: translateY(12px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    .detail-panel h2 {{ font-size: 32px; line-height: 1.18; margin: 8px 0 10px; letter-spacing: 0; }}
    .detail-actions {{
      display: flex;
      justify-content: flex-end;
      margin-bottom: 10px;
    }}
    .detail-lead {{ font-size: 17px; color: var(--muted-strong); margin: 0 0 14px; }}
    .detail-section {{ border-top: 1px solid var(--divider); padding-top: 18px; margin-top: 18px; }}
    .detail-section h3 {{ font-size: 17px; margin: 0 0 12px; }}
    .story-block {{
      display: grid;
      gap: 10px;
      color: var(--muted-strong);
    }}
    .story-block p {{ margin: 0; }}
    .evidence-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }}
    .evidence-note {{
      border: 1px solid var(--hairline);
      border-radius: 14px;
      background: var(--pearl);
      padding: 12px;
      min-width: 0;
    }}
    .evidence-note strong {{ display: block; font-size: 13px; margin-bottom: 6px; }}
    .evidence-note p {{ margin: 0; color: var(--muted); font-size: 13px; }}
    .takeaway-list {{
      margin: 0;
      padding-left: 20px;
      color: var(--muted-strong);
    }}
    .takeaway-list li {{ margin: 7px 0; }}
    .step-list {{ list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; }}
    .step-list li {{ display: grid; grid-template-columns: 32px minmax(0, 1fr); gap: 10px; }}
    .step-index {{
      width: 28px;
      height: 28px;
      border-radius: 9999px;
      background: var(--primary);
      color: #fff;
      display: grid;
      place-items: center;
      font-size: 12px;
    }}
    .step-list strong {{ display: block; font-size: 14px; }}
    .step-list p {{ margin: 3px 0 0; color: var(--muted); font-size: 14px; }}
    .media-grid {{ display: grid; gap: 12px; }}
    .media-tile {{
      display: block;
      text-decoration: none;
    }}
    .media-tile img {{
      width: 100%;
      height: 220px;
      aspect-ratio: 4 / 3;
      object-fit: contain;
      display: block;
      background: var(--pearl);
      border-radius: 8px;
      box-shadow: var(--product-shadow);
    }}
    .media-tile span {{ display: block; color: var(--muted); font-size: 12px; margin-top: 8px; }}
    .media-tile span,
    .resource-link strong,
    .viewer-toolbar strong {{
      overflow-wrap: anywhere;
    }}
    .resource-list {{ display: grid; gap: 10px; }}
    .resource-row {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      align-items: center;
      gap: 10px;
      border-bottom: 1px solid var(--divider);
    }}
    .resource-row:last-child {{ border-bottom: 0; }}
    .resource-link {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      align-items: center;
      gap: 10px;
      padding: 12px 0;
      text-decoration: none;
    }}
    .resource-link strong {{ display: block; color: var(--ink); font-size: 14px; }}
    .resource-link code {{ display: block; color: var(--muted); font-size: 12px; overflow-wrap: anywhere; white-space: normal; }}
    .resource-open {{
      border: 1px solid var(--primary);
      border-radius: 9999px;
      padding: 6px 10px;
      font-size: 12px;
      text-decoration: none;
      white-space: nowrap;
    }}
    .kind-pill {{ border: 1px solid var(--primary); color: var(--primary); border-radius: 9999px; padding: 5px 9px; font-size: 12px; }}
    .artifact-viewer {{
      border: 1px solid var(--hairline);
      border-radius: 18px;
      background: var(--pearl);
      min-height: 260px;
      overflow: hidden;
    }}
    .viewer-toolbar {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      border-bottom: 1px solid var(--divider);
      padding: 12px 14px;
      background: var(--canvas);
    }}
    .viewer-toolbar strong {{ display: block; font-size: 14px; }}
    .viewer-toolbar code {{ display: block; color: var(--muted); font-size: 12px; overflow-wrap: anywhere; white-space: normal; }}
    .viewer-body {{ padding: 14px; min-width: 0; max-width: 100%; overflow: hidden; }}
    .viewer-body img {{
      width: 100%;
      max-height: 520px;
      object-fit: contain;
      display: block;
      background: var(--canvas);
      border-radius: 8px;
    }}
    .viewer-body iframe {{
      width: 100%;
      height: 520px;
      border: 0;
      background: var(--canvas);
      border-radius: 8px;
    }}
    .viewer-body pre {{
      margin: 0;
      max-height: 520px;
      overflow: auto;
      background: var(--canvas);
      border-radius: 8px;
      padding: 14px;
      color: var(--ink);
      font-size: 12px;
      line-height: 1.45;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }}
    .markdown-body {{
      max-height: 620px;
      overflow: auto;
      background: var(--canvas);
      border-radius: 8px;
      padding: 22px;
      font-size: 15px;
      line-height: 1.65;
    }}
    .markdown-body h1, .markdown-body h2, .markdown-body h3 {{
      margin: 24px 0 12px;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--divider);
      line-height: 1.25;
      letter-spacing: 0;
    }}
    .markdown-body h1:first-child, .markdown-body h2:first-child, .markdown-body h3:first-child {{ margin-top: 0; }}
    .markdown-body h1 {{ font-size: 28px; }}
    .markdown-body h2 {{ font-size: 22px; }}
    .markdown-body h3 {{ font-size: 18px; }}
    .markdown-body p {{ margin: 0 0 12px; }}
    .markdown-body ul, .markdown-body ol {{ margin: 0 0 14px; padding-left: 24px; }}
    .markdown-body li {{ margin: 5px 0; }}
    .markdown-body code {{
      background: var(--parchment);
      border-radius: 5px;
      padding: 2px 5px;
      font-size: 0.92em;
    }}
    .markdown-body pre {{
      margin: 0 0 14px;
      overflow: auto;
      background: #f6f8fa;
      border: 1px solid var(--divider);
      border-radius: 8px;
      padding: 14px;
      white-space: pre;
    }}
    .markdown-body pre code {{ background: transparent; padding: 0; }}
    .markdown-body blockquote {{
      margin: 0 0 14px;
      padding: 0 14px;
      color: var(--muted);
      border-left: 4px solid var(--hairline);
    }}
    .markdown-body table {{
      width: 100%;
      border-collapse: collapse;
      margin: 0 0 16px;
      font-size: 14px;
    }}
    .markdown-body th, .markdown-body td {{
      border: 1px solid var(--hairline);
      padding: 7px 9px;
      text-align: left;
      vertical-align: top;
    }}
    .markdown-body th {{ background: var(--parchment); font-weight: 600; }}
    .markdown-body hr {{ border: 0; border-top: 1px solid var(--divider); margin: 22px 0; }}
    .csv-sheet {{
      width: 100%;
      max-width: 100%;
      max-height: 620px;
      overflow: auto;
      background: var(--canvas);
      border-radius: 8px;
      border: 1px solid var(--hairline);
    }}
    .csv-sheet table {{
      width: max-content;
      min-width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      font-size: 12px;
      line-height: 1.35;
    }}
    .csv-sheet th, .csv-sheet td {{
      max-width: 280px;
      min-width: 96px;
      border-right: 1px solid var(--hairline);
      border-bottom: 1px solid var(--hairline);
      padding: 7px 9px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      background: linear-gradient(90deg, hsl(var(--col-hue) 48% 94%) 0 4px, var(--canvas) 4px);
      border-left: 0;
    }}
    .csv-sheet th {{
      position: sticky;
      top: 0;
      z-index: 2;
      background: linear-gradient(90deg, hsl(var(--col-hue) 48% 88%) 0 4px, var(--parchment) 4px);
      font-weight: 600;
      color: var(--ink);
    }}
    .csv-sheet .row-index {{
      position: sticky;
      left: 0;
      z-index: 1;
      min-width: 48px;
      width: 48px;
      background: var(--parchment);
      border-left: 0;
      text-align: right;
      color: var(--muted);
    }}
    .csv-sheet th.row-index {{ z-index: 3; }}
    .csv-note {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--divider);
      background: var(--canvas);
      color: var(--muted);
      font-size: 12px;
    }}
    .viewer-empty {{ padding: 18px; color: var(--muted); }}
    footer {{
      background: var(--parchment);
      color: var(--muted-strong);
      font-size: 12px;
      padding: 48px 24px 64px;
      width: min(100%, 1440px);
      margin: 0 auto;
    }}
    @media (max-width: 1180px) {{
      .hero-inner {{ grid-template-columns: 1fr; align-items: start; }}
      .hero-preview-slot .preview img {{ height: 300px; }}
      .group-shell {{ grid-template-columns: 1fr; }}
      .group-cards {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .workspace-tools {{ position: static; grid-template-columns: 1fr; padding: 0; background: transparent; backdrop-filter: none; }}
      .panel {{ border-radius: 18px; padding: 18px; }}
      .filter-panel {{ grid-template-columns: 1fr; }}
      .filter-panel .chips {{ display: flex; flex-wrap: wrap; overflow-x: visible; justify-content: flex-start; }}
      .flow {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 12px; width: 100%; }}
      .flow li {{ display: grid; grid-template-columns: 16px minmax(0, 1fr); gap: 8px; align-items: start; }}
      .flow-dot {{ margin-top: 7px; width: 8px; height: 8px; }}
      .flow p {{ display: block; margin: 2px 0 0; color: var(--muted); font-size: 12px; line-height: 1.35; }}
      .search {{ min-height: 44px; padding: 12px 20px; font-size: inherit; }}
      .chip {{ min-height: 44px; padding: 10px 16px; font-size: inherit; }}
      .analysis-stage, .workspace.has-selection .analysis-stage {{ grid-template-columns: 1fr; }}
      .workspace.is-list-only .card-grid {{ grid-template-columns: 1fr; }}
      .detail-panel, .workspace.has-selection .detail-panel {{ order: 1; height: auto; min-height: auto; overflow: visible; }}
      .list-pane, .workspace.has-selection .list-pane {{ order: 2; height: auto; min-height: auto; overflow: visible; padding-right: 0; }}
      .stats {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
      .previews {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 760px) {{
      .global-nav-inner {{ padding: 0 16px; gap: 12px; justify-content: flex-start; }}
      .global-nav-inner span:last-child {{ display: none; }}
      .sub-nav-inner {{ padding: 0 16px; gap: 12px; }}
      .sub-title {{
        min-width: 0;
        font-size: 18px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }}
      .sub-actions {{ flex: 0 0 auto; }}
      .primary-pill {{ min-height: 38px; padding: 8px 14px; }}
      h1 {{ font-size: 29px; line-height: 1.1; }}
      .mobile-title-break {{ display: block; }}
      .lead {{ font-size: 16px; line-height: 1.38; }}
      .hero {{ min-height: auto; padding: 16px 16px 12px; }}
      .hero-inner {{ gap: 14px; }}
      .hero-copy {{ gap: 9px; }}
      .verdict-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; }}
      .verdict-card {{ padding: 10px; gap: 3px; }}
      .verdict-card strong {{ font-size: 14px; }}
      .verdict-card small {{ display: none; }}
      .hero-preview-panel {{ padding: 10px; gap: 8px; }}
      .hero-panel-head {{ gap: 10px; }}
      .hero-panel-head code {{ display: none; }}
      .hero-preview-slot .preview {{ gap: 8px; }}
      .hero-preview-slot .preview img {{ height: 80px; max-height: 21vw; }}
      .sub-actions span {{ display: none; }}
      .workspace {{ padding: 16px 16px 40px; }}
      .overview-stack {{ padding: 0 16px 34px; }}
      .workspace-tools {{ gap: 8px; }}
      .panel {{ border-radius: 14px; padding: 12px; }}
      .filter-panel {{ gap: 8px; padding: 12px; }}
      .filter-row {{ grid-template-columns: minmax(0, 1fr) auto; gap: 8px; }}
      .search {{ min-width: 0; min-height: 40px; padding: 9px 14px; }}
      .filter-panel .chips,
      .group-filter {{
        flex-wrap: wrap;
        overflow-x: visible;
        justify-content: flex-start;
        padding-bottom: 2px;
      }}
      .chip,
      .group-chip {{
        width: auto;
        flex: 0 1 auto;
        min-width: 0;
        white-space: normal;
        overflow-wrap: anywhere;
        text-align: center;
        line-height: 1.2;
      }}
      .chip {{ min-height: 38px; padding: 8px 13px; font-size: 14px; }}
      .group-chip {{ min-height: 34px; padding: 7px 10px; }}
      .group-filter {{ grid-column: 1 / -1; gap: 6px; align-items: flex-start; }}
      .group-filter-label {{ display: none; }}
      .flow-guide {{ display: block; padding-top: 0; }}
      .flow-guide h2 {{ display: none; }}
      .flow {{ display: flex; flex-wrap: wrap; gap: 6px; }}
      .flow li {{ display: inline-flex; grid-template-columns: none; gap: 5px; }}
      .flow p {{ display: none; }}
      .group-shell {{ padding: 0; gap: 12px; }}
      .group-header {{ flex-direction: column; align-items: stretch; }}
      .group-evidence {{
        min-height: 0;
        padding: 16px;
        gap: 12px;
      }}
      .group-evidence h3 {{ font-size: 16px; }}
      .group-evidence p {{ font-size: 13px; }}
      .evidence-bars {{ align-content: start; gap: 10px; }}
      .evidence-row {{ padding: 4px 0 10px; }}
      .stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .stat {{ min-height: 58px; padding: 9px 12px; }}
      .stat strong {{ font-size: 19px; }}
      .card-grid, .stat-list, .previews, .evidence-grid {{ grid-template-columns: 1fr; }}
      .group-cards {{ grid-template-columns: 1fr; }}
      .group-card {{
        min-height: 0;
        padding: 12px;
        gap: 7px;
      }}
      .group-card h3 {{ font-size: 15px; }}
      .group-answer {{ font-size: 13px; }}
      .group-question,
      .group-answer,
      .group-evidence-line,
      .group-caution-line {{
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }}
      .group-link {{
        min-height: 34px;
        white-space: normal;
        overflow-wrap: anywhere;
        line-height: 1.2;
        text-overflow: clip;
      }}
      .group-links {{ grid-template-columns: 1fr; }}
      .group-metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .preview img, .media-tile img {{ height: 200px; }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      *, *::before, *::after {{
        animation-duration: 0.001ms !important;
        animation-iteration-count: 1 !important;
        scroll-behavior: auto !important;
        transition-duration: 0.001ms !important;
      }}
    }}
  </style>
</head>
<body>
  <nav class="global-nav" aria-label="Global">
    <div class="global-nav-inner">
      <div class="mark">CAMELS</div>
      <span>Probabilistic Head analysis</span>
      <span>Static dashboard</span>
    </div>
  </nav>
  <nav class="sub-nav" aria-label="Dashboard">
    <div class="sub-nav-inner">
      <div class="sub-title">Probabilistic Head Dashboard</div>
      <div class="sub-actions">
        <span>{fmt_count(len(analyses))} investigations</span>
        <a class="primary-pill" href="#analysis">Explore</a>
      </div>
    </div>
  </nav>
  <div class="page">
    <section class="hero">
      <div class="hero-inner">
        <div class="hero-copy">
          <p class="eyebrow">CAMELS / Model 1 vs Model 2</p>
          <h1>Probabilistic Head<br class="mobile-title-break"> 분석 대시보드</h1>
          <p class="lead">전체 성능을 먼저 확인하고,<br class="mobile-title-break"> high-flow quantile과 event stress,<br class="mobile-title-break"> 유역별 robustness 근거로<br class="mobile-title-break"> 재정렬했어요.</p>
          <div class="verdict-grid" aria-label="핵심 판단 요약">
            {verdict_tiles_html}
          </div>
        </div>
        <aside class="hero-preview-panel" aria-label="대표 판단 figure">
          <div class="hero-panel-head">
            <div>
              <span>대표 figure</span>
              <strong>High-flow 결론을 먼저 확인</strong>
            </div>
            <code>{html.escape(payload['generated_at'])}</code>
          </div>
          <div class="hero-preview-slot">
            {primary_preview}
          </div>
        </aside>
      </div>
    </section>
    <section class="dashboard-summary" aria-label="Dashboard summary">
      <div class="stats">
        {stat_tiles_html}
      </div>
    </section>

    <main id="analysis" class="workspace is-list-only">
      <section class="workspace-tools" aria-label="분석 도구">
        <section class="panel filter-panel">
          <h2>필터</h2>
          <div class="filter-row">
            <label class="sr-only" for="search">분석명, 목적, tag 검색</label>
            <input id="search" class="search" type="search" placeholder="예: q99, basin dissect, calibration" autocomplete="off" aria-label="분석명, 목적, tag 검색">
            <button id="reset" class="chip" type="button">초기화</button>
          </div>
          <div class="chips">
            <button class="chip active" data-category="all" type="button">전체</button>
            {category_buttons}
          </div>
          <div class="group-filter" aria-label="그룹 필터">
            <span class="group-filter-label">그룹</span>
            <button class="group-chip active" data-group="all" type="button">전체 그룹</button>
            {group_filter_buttons}
          </div>
        </section>
      </section>
      <section class="flow-guide" aria-label="분석 흐름 안내">
        <h2>분석 흐름</h2>
        <ol class="flow">{flow_items}</ol>
      </section>
      <section class="analysis-stage">
        <section class="list-pane">
          <p id="summary" class="summary-line"></p>
          <div id="cards" class="card-grid"></div>
          <div id="empty" class="empty">조건에 맞는 분석이 없습니다.</div>
        </section>
        <aside id="detail" class="detail-panel" aria-live="polite"></aside>
      </section>
      <section class="group-overview group-primary" aria-labelledby="group-overview-title">
        <div class="group-shell">
          <div class="group-header">
            <div class="group-copy">
              <p class="eyebrow">Analysis grouping</p>
              <h2 id="group-overview-title">큰 질문별 현재 답</h2>
              <p>자료 개수보다 먼저 각 그룹의 질문, 현재 결론, 대표 근거, 해석 주의점을 보도록 바꿨습니다.</p>
            </div>
            <button class="chip active" data-group="all" type="button">전체 그룹</button>
          </div>
          <div class="group-left">
            <div id="groupCards" class="group-cards"></div>
          </div>
          <div id="groupEvidence" class="group-evidence" aria-label="분석 그룹 evidence bar"></div>
        </div>
      </section>
    </main>
    <section class="overview-stack" aria-labelledby="overview-title">
      <div class="overview-heading">
        <p class="eyebrow">Supporting figures</p>
        <h2 id="overview-title">나머지 대표 figure</h2>
        <p>첫 화면의 결론 figure 아래에서, split·calibration·robustness·runoff-ratio 계열 figure를 이어서 확인합니다.</p>
      </div>
      <section class="previews" aria-label="대표 figure preview">
        {secondary_preview_html}
      </section>
    </section>
    <footer>Generated by scripts/model/overall/build_analysis_inventory_site.py. Output root: {html.escape(payload.get('output_root', 'output/model_analysis/analysis_dashboard'))}.</footer>
  </div>
  <script id="inventory-data" type="application/json">{payload_for_page}</script>
  <script>
    const data = JSON.parse(document.getElementById("inventory-data").textContent);
    const cardsEl = document.getElementById("cards");
    const summaryEl = document.getElementById("summary");
    const emptyEl = document.getElementById("empty");
    const detailEl = document.getElementById("detail");
    const workspaceEl = document.getElementById("analysis");
    const searchEl = document.getElementById("search");
    const resetEl = document.getElementById("reset");
    const groupEvidenceEl = document.getElementById("groupEvidence");
    const groupCardsEl = document.getElementById("groupCards");
    const chips = Array.from(document.querySelectorAll(".chip[data-category]"));
    let currentResources = [];
    let activeCategory = "all";
    let activeGroup = readHashGroup() || "all";
    let selectedId = readHashSelection();

    function readHashSelection() {{
      if (!window.location.hash.startsWith("#analysis-")) return "";
      return window.location.hash.replace("#analysis-", "");
    }}

    function readHashGroup() {{
      if (!window.location.hash.startsWith("#group-")) return "";
      return window.location.hash.replace("#group-", "");
    }}

    function esc(value) {{
      return String(value ?? "").replace(/[&<>"']/g, (char) => ({{
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }}[char]));
    }}

    function linkList(title, items) {{
      if (!items || !items.length) return "";
      const links = items.map(item => `<a href="${{esc(item.href)}}">${{esc(item.label)}}</a>`).join("");
      return `<div class="links"><strong>${{esc(title)}}</strong><div class="link-group">${{links}}</div></div>`;
    }}

    function statList(stats) {{
      if (!stats || !stats.length) return "";
      return `<div class="stat-list">${{stats.map(([label, value]) => `
        <div class="mini-stat"><span>${{esc(label)}}</span><strong>${{esc(value)}}</strong></div>
      `).join("")}}</div>`;
    }}

    function imageAttrs(item) {{
      if (!item || !item.width || !item.height) return "";
      return ` width="${{esc(item.width)}}" height="${{esc(item.height)}}"`;
    }}

    function metric(label, value) {{
      return `<div class="group-metric"><span>${{esc(label)}}</span><strong>${{esc(value)}}</strong></div>`;
    }}

    const groupQuickTargets = {{
      "event-stress": ["hydrograph-galleries", "runoff-ratio", "extreme-rain-stress"],
      "basin-robustness": ["median-deviation", "basin-dissect", "outlier-mechanism"],
      "probabilistic-head": ["high-flow-quantile", "peak-quantile-bracket", "probabilistic-diagnostics"],
      "overall-performance": ["primary-overall", "checkpoint-sensitivity", "overfit-risk"],
      "data-foundation": ["drbc-definition", "subset300-representativeness", "ml-event-regime"],
      "paper-assets": ["paper-assets"]
    }};

    function groupQuickLinks(group) {{
      const ids = groupQuickTargets[group.id] || (group.analysisIds || []).slice(0, 3);
      const links = ids.map(id => data.analyses.find(item => item.id === id)).filter(Boolean);
      if (!links.length) return "";
      return `<div class="group-links">${{links.map(item => `
        <button class="group-link" type="button" data-analysis-id="${{esc(item.id)}}">${{esc(item.title)}}</button>
      `).join("")}}</div>`;
    }}

    function groupCard(group) {{
      const active = activeGroup === group.id ? " active" : "";
      return `<article class="group-card${{active}}" data-group="${{esc(group.id)}}" role="button" tabindex="0" aria-label="${{esc(group.label)}} 그룹 보기">
        <span class="group-kicker">핵심 질문</span>
        <h3>${{esc(group.label)}}</h3>
        <p class="group-question">${{esc(group.question || group.description)}}</p>
        <strong class="group-answer">${{esc(group.answer || group.description)}}</strong>
        <span class="group-evidence-line">대표 근거: ${{esc(group.evidence || "linked outputs")}}</span>
        ${{group.caution ? `<span class="group-caution-line">주의: ${{esc(group.caution)}}</span>` : ""}}
        <div class="group-foot">
          <span>${{esc(group.analysisCount)}} analyses</span>
          <span>${{esc(group.figureCount)}} figures</span>
          <span>${{esc(group.tableCount)}} tables</span>
        </div>
        ${{groupQuickLinks(group)}}
      </article>`;
    }}

    function renderGroupEvidence() {{
      const groups = data.groups || [];
      if (!groups.length) {{
        groupEvidenceEl.innerHTML = "";
        return;
      }}
      const maxResources = Math.max(...groups.map(group => group.resourceCount), 1);
      const rows = groups.map(group => {{
        const width = `${{Math.max(8, Math.round((group.resourceCount / maxResources) * 100))}}%`;
        return `<div class="evidence-row">
          <div class="evidence-row-top">
            <span>${{esc(group.label)}}</span>
            <span>${{group.analysisCount}} analyses · ${{group.resourceCount}} resources</span>
          </div>
          <p class="evidence-answer">${{esc(group.answer || group.description)}}</p>
          ${{group.caution ? `<p class="evidence-caution">주의: ${{esc(group.caution)}}</p>` : ""}}
          <div class="evidence-bar"><div class="evidence-fill" style="--evidence-width:${{width}}"></div></div>
        </div>`;
      }}).join("");
      groupEvidenceEl.innerHTML = `
        <h3>근거 상태 요약</h3>
        <p>막대는 자료량을 보조로 보여주고, 문장은 각 그룹을 읽을 때 먼저 확인할 현재 판단과 caveat입니다.</p>
        <div class="evidence-bars">${{rows}}</div>
      `;
    }}

    function renderGroupOverview() {{
      if (!groupCardsEl || !groupEvidenceEl) return;
      groupCardsEl.innerHTML = (data.groups || []).map(groupCard).join("");
      document.querySelectorAll("[data-group]").forEach(button => {{
        button.classList.toggle("active", button.dataset.group === activeGroup);
      }});
      renderGroupEvidence();
    }}

    function syncWorkspaceMode() {{
      const hasSelection = Boolean(selectedId);
      workspaceEl.classList.toggle("has-selection", hasSelection);
      workspaceEl.classList.toggle("is-list-only", !hasSelection);
      detailEl.setAttribute("aria-hidden", hasSelection ? "false" : "true");
    }}

    function updateToolsStuck() {{
      const desktop = window.matchMedia("(min-width: 1181px)").matches;
      const workspaceTop = workspaceEl.getBoundingClientRect().top;
      workspaceEl.classList.toggle("is-tools-stuck", desktop && workspaceTop < 40);
    }}

    function card(item) {{
      const selected = item.id === selectedId ? " selected" : "";
      const topStats = (item.stats || []).slice(0, 3);
      return `<button class="analysis-card${{selected}}" type="button" data-id="${{esc(item.id)}}" aria-label="${{esc(item.title)}} 상세 보기">
        <div class="category-label">${{esc(item.groupLabel)}} / ${{esc(item.category)}}</div>
        <div class="card-head">
          <h3>${{esc(item.title)}}</h3>
          <span class="badge ${{esc(item.statusClass)}}">${{esc(item.status)}}</span>
        </div>
        <div class="card-text">
          <p class="purpose-line">${{esc(item.purpose)}}</p>
        </div>
        ${{statList(topStats)}}
        <span class="detail-cue">상세 과정과 자료 보기</span>
      </button>`;
    }}

    function stepList(steps) {{
      if (!steps || !steps.length) return "";
      return `<ol class="step-list">${{steps.map((step, index) => `
        <li>
          <span class="step-index">${{index + 1}}</span>
          <div><strong>${{esc(step.label)}}</strong><p>${{esc(step.body)}}</p></div>
        </li>
      `).join("")}}</ol>`;
    }}

    function paragraphBlock(items) {{
      const paragraphs = (items || []).filter(Boolean).map(item => `<p>${{esc(item)}}</p>`).join("");
      return `<div class="story-block">${{paragraphs}}</div>`;
    }}

    function evidenceGrid(story) {{
      const visual = (story.visual || []).filter(Boolean).join(" ");
      const numeric = (story.numeric || []).filter(Boolean).join(" ");
      return `<div class="evidence-grid">
        <div class="evidence-note"><strong>시각적으로 볼 것</strong><p>${{esc(visual)}}</p></div>
        <div class="evidence-note"><strong>수치적으로 볼 것</strong><p>${{esc(numeric)}}</p></div>
      </div>`;
    }}

    function takeawayList(items) {{
      const values = (items || []).filter(Boolean);
      if (!values.length) return "";
      return `<ul class="takeaway-list">${{values.map(item => `<li>${{esc(item)}}</li>`).join("")}}</ul>`;
    }}

    function mediaList(media) {{
      if (!media || !media.length) return "";
      return `<section class="detail-section">
        <h3>대표 자료 미리보기</h3>
        <div class="media-grid">${{media.map(item => `
          <a class="media-tile" href="${{esc(item.href)}}">
            <img src="${{esc(item.href)}}" alt="${{esc(item.label)}}"${{imageAttrs(item)}} loading="lazy">
            <span>${{esc(item.label)}}</span>
          </a>
        `).join("")}}</div>
      </section>`;
    }}

    function resourceList(title, items) {{
      if (!items || !items.length) return "";
      const links = items.map(item => `<div class="resource-row">
        <a class="resource-link" href="${{esc(item.href)}}" data-preview-href="${{esc(item.href)}}" data-preview-label="${{esc(item.label)}}" data-preview-path="${{esc(item.path)}}" data-preview-kind="${{esc(item.kind || "Artifact")}}">
          <span><strong>${{esc(item.label)}}</strong><code>${{esc(item.path)}}</code></span>
          <span class="kind-pill">${{esc(item.kind || "Artifact")}}</span>
        </a>
        <a class="resource-open" href="${{esc(item.href)}}">파일 열기</a>
      </div>`).join("");
      return `<section class="detail-section"><h3>${{esc(title)}}</h3><div class="resource-list">${{links}}</div></section>`;
    }}

    function artifactViewerSection(items) {{
      if (!items || !items.length) return "";
      return `<section class="detail-section">
        <h3>자료 바로보기</h3>
        <div id="artifactViewer" class="artifact-viewer">
          <div class="viewer-empty">아래 자료 링크를 누르면 이 영역에서 바로 확인할 수 있습니다.</div>
        </div>
      </section>`;
    }}

    function previewMode(item) {{
      const href = String(item.href || "").toLowerCase();
      const path = String(item.path || "").toLowerCase();
      if (href.includes("/_omitted/") || href.endsWith(".html")) return "frame";
      if (/\\.(png|jpg|jpeg|svg|webp)$/.test(href) || /\\.(png|jpg|jpeg|svg|webp)$/.test(path)) return "image";
      if (href.endsWith(".md") || path.endsWith(".md")) return "markdown";
      if (href.endsWith(".csv") || path.endsWith(".csv")) return "csv";
      if (/\\.(json|py|txt|yaml|yml|sh|toml|log)$/.test(href) || /\\.(json|py|txt|yaml|yml|sh|toml|log)$/.test(path)) return "text";
      return "frame";
    }}

    function safeHref(value) {{
      const href = String(value || "").trim();
      if (/^javascript:/i.test(href)) return "#";
      return esc(href);
    }}

    function renderInlineMarkdown(value) {{
      let text = esc(value);
      text = text.replace(/\\[([^\\]]+)\\]\\(([^)]+)\\)/g, (_, label, href) => `<a href="${{safeHref(href)}}">${{label}}</a>`);
      text = text.replace(/`([^`]+)`/g, "<code>$1</code>");
      text = text.replace(/\\*\\*([^*]+)\\*\\*/g, "<strong>$1</strong>");
      text = text.replace(/__([^_]+)__/g, "<strong>$1</strong>");
      text = text.replace(/\\*([^*]+)\\*/g, "<em>$1</em>");
      return text;
    }}

    function isTableDivider(line) {{
      return /^\\s*\\|?\\s*:?-{{3,}}:?\\s*(\\|\\s*:?-{{3,}}:?\\s*)+\\|?\\s*$/.test(line);
    }}

    function splitMarkdownTableRow(line) {{
      return line.trim().replace(/^\\|/, "").replace(/\\|$/, "").split("|").map(cell => cell.trim());
    }}

    function renderMarkdownTable(lines, start) {{
      const header = splitMarkdownTableRow(lines[start]);
      let index = start + 2;
      const rows = [];
      while (index < lines.length && /\\|/.test(lines[index]) && lines[index].trim()) {{
        rows.push(splitMarkdownTableRow(lines[index]));
        index += 1;
      }}
      const head = header.map(cell => `<th>${{renderInlineMarkdown(cell)}}</th>`).join("");
      const body = rows.map(row => `<tr>${{row.map(cell => `<td>${{renderInlineMarkdown(cell)}}</td>`).join("")}}</tr>`).join("");
      return {{ html: `<table><thead><tr>${{head}}</tr></thead><tbody>${{body}}</tbody></table>`, next: index }};
    }}

    function renderMarkdown(markdown) {{
      const lines = String(markdown || "").replace(/\\r\\n/g, "\\n").split("\\n");
      const blocks = [];
      let paragraph = [];
      let listType = null;
      let listItems = [];
      let inCode = false;
      let codeLines = [];

      function flushParagraph() {{
        if (!paragraph.length) return;
        blocks.push(`<p>${{renderInlineMarkdown(paragraph.join(" "))}}</p>`);
        paragraph = [];
      }}

      function flushList() {{
        if (!listType) return;
        blocks.push(`<${{listType}}>${{listItems.map(item => `<li>${{renderInlineMarkdown(item)}}</li>`).join("")}}</${{listType}}>`);
        listType = null;
        listItems = [];
      }}

      for (let i = 0; i < lines.length; i += 1) {{
        const line = lines[i];
        const trimmed = line.trim();

        if (trimmed.startsWith("```")) {{
          if (inCode) {{
            blocks.push(`<pre><code>${{esc(codeLines.join("\\n"))}}</code></pre>`);
            inCode = false;
            codeLines = [];
          }} else {{
            flushParagraph();
            flushList();
            inCode = true;
          }}
          continue;
        }}

        if (inCode) {{
          codeLines.push(line);
          continue;
        }}

        if (!trimmed) {{
          flushParagraph();
          flushList();
          continue;
        }}

        if (i + 1 < lines.length && /\\|/.test(line) && isTableDivider(lines[i + 1])) {{
          flushParagraph();
          flushList();
          const table = renderMarkdownTable(lines, i);
          blocks.push(table.html);
          i = table.next - 1;
          continue;
        }}

        const heading = /^(#{{1,6}})\\s+(.+)$/.exec(trimmed);
        if (heading) {{
          flushParagraph();
          flushList();
          const level = Math.min(3, heading[1].length);
          blocks.push(`<h${{level}}>${{renderInlineMarkdown(heading[2])}}</h${{level}}>`);
          continue;
        }}

        if (/^---+$/.test(trimmed)) {{
          flushParagraph();
          flushList();
          blocks.push("<hr>");
          continue;
        }}

        if (trimmed.startsWith(">")) {{
          flushParagraph();
          flushList();
          blocks.push(`<blockquote>${{renderInlineMarkdown(trimmed.replace(/^>\\s?/, ""))}}</blockquote>`);
          continue;
        }}

        const unordered = /^[-*]\\s+(.+)$/.exec(trimmed);
        const ordered = /^\\d+\\.\\s+(.+)$/.exec(trimmed);
        if (unordered || ordered) {{
          flushParagraph();
          const nextType = unordered ? "ul" : "ol";
          if (listType && listType !== nextType) flushList();
          listType = nextType;
          listItems.push((unordered || ordered)[1]);
          continue;
        }}

        paragraph.push(trimmed);
      }}

      if (inCode) blocks.push(`<pre><code>${{esc(codeLines.join("\\n"))}}</code></pre>`);
      flushParagraph();
      flushList();
      return `<article class="markdown-body">${{blocks.join("")}}</article>`;
    }}

    function parseCsv(text, maxRows = 220, maxCols = 48) {{
      const rows = [];
      let row = [];
      let field = "";
      let inQuotes = false;
      for (let i = 0; i < text.length; i += 1) {{
        const char = text[i];
        const next = text[i + 1];
        if (char === '"') {{
          if (inQuotes && next === '"') {{
            field += '"';
            i += 1;
          }} else {{
            inQuotes = !inQuotes;
          }}
        }} else if (char === "," && !inQuotes) {{
          row.push(field);
          field = "";
        }} else if ((char === "\\n" || char === "\\r") && !inQuotes) {{
          if (char === "\\r" && next === "\\n") i += 1;
          row.push(field);
          rows.push(row);
          if (rows.length >= maxRows + 1) break;
          row = [];
          field = "";
        }} else {{
          field += char;
        }}
      }}
      if (rows.length < maxRows + 1 && (field || row.length)) {{
        row.push(field);
        rows.push(row);
      }}
      return rows.map(nextRow => nextRow.slice(0, maxCols));
    }}

    function csvHue(index) {{
      return Math.round((index * 47) % 360);
    }}

    function renderCsvSheet(text) {{
      const rows = parseCsv(text);
      if (!rows.length) return `<div class="viewer-empty">CSV에 표시할 행이 없습니다.</div>`;
      const header = rows[0];
      const bodyRows = rows.slice(1);
      const colCount = Math.max(...rows.map(row => row.length));
      const head = Array.from({{ length: colCount }}, (_, index) => {{
        const label = header[index] || `Column ${{index + 1}}`;
        return `<th style="--col-hue:${{csvHue(index)}}">${{esc(label)}}</th>`;
      }}).join("");
      const body = bodyRows.map((row, rowIndex) => `<tr>
        <td class="row-index">${{rowIndex + 1}}</td>
        ${{Array.from({{ length: colCount }}, (_, colIndex) => `<td style="--col-hue:${{csvHue(colIndex)}}">${{esc(row[colIndex] || "")}}</td>`).join("")}}
      </tr>`).join("");
      const note = `<div class="csv-note">Spreadsheet preview: first ${{bodyRows.length.toLocaleString()}} rows and ${{colCount.toLocaleString()}} columns. Subtle column guides support scanning without turning the table into a color legend.</div>`;
      return `<div class="csv-sheet">${{note}}<table><thead><tr><th class="row-index">#</th>${{head}}</tr></thead><tbody>${{body}}</tbody></table></div>`;
    }}

    function viewerShell(item, body) {{
      return `<div class="viewer-toolbar">
        <span><strong>${{esc(item.label)}}</strong><code>${{esc(item.path)}}</code></span>
        <a class="resource-open" href="${{esc(item.href)}}">파일 열기</a>
      </div><div class="viewer-body">${{body}}</div>`;
    }}

    async function showResourcePreview(item) {{
      const viewer = document.getElementById("artifactViewer");
      if (!viewer || !item) return;
      const mode = previewMode(item);
      viewer.innerHTML = viewerShell(item, `<div class="viewer-empty">자료를 불러오는 중입니다.</div>`);
      if (mode === "image") {{
        viewer.innerHTML = viewerShell(item, `<img src="${{esc(item.href)}}" alt="${{esc(item.label)}}"${{imageAttrs(item)}} loading="lazy">`);
        return;
      }}
      if (mode === "frame") {{
        viewer.innerHTML = viewerShell(item, `<iframe src="${{esc(item.href)}}" title="${{esc(item.label)}}"></iframe>`);
        return;
      }}
      try {{
        const response = await fetch(item.href);
        if (!response.ok) throw new Error(`HTTP ${{response.status}}`);
        const text = await response.text();
        if (mode === "markdown") {{
          viewer.innerHTML = viewerShell(item, renderMarkdown(text));
          return;
        }}
        if (mode === "csv") {{
          viewer.innerHTML = viewerShell(item, renderCsvSheet(text));
          return;
        }}
        const suffix = text.length > 50000 ? "\\n\\n... preview truncated ..." : "";
        viewer.innerHTML = viewerShell(item, `<pre>${{esc(text.slice(0, 50000) + suffix)}}</pre>`);
      }} catch (error) {{
        viewer.innerHTML = viewerShell(item, `<div class="viewer-empty">이 자료는 브라우저 preview로 읽지 못했습니다. 파일 열기를 사용해 주세요.</div>`);
      }}
    }}

    function renderDetail(item) {{
      if (!item) {{
        currentResources = [];
        detailEl.innerHTML = "";
        syncWorkspaceMode();
        return;
      }}
      currentResources = [...(item.outputs || []), ...(item.sources || [])];
      const tags = (item.tags || []).map(tag => `<span class="tag">${{esc(tag)}}</span>`).join("");
      const caution = item.caution ? `<div class="caution">${{esc(item.caution)}}</div>` : "";
      const story = item.story || {{}};
      detailEl.innerHTML = `
        <div class="detail-actions"><button class="chip" type="button" data-clear-selection="true">목록 전체 보기</button></div>
        <div class="category-label">${{esc(item.groupLabel)}} / ${{esc(item.category)}}</div>
        <h2>${{esc(item.title)}}</h2>
        <p class="detail-lead">${{esc(item.purpose)}}</p>
        <div class="tags">${{tags}}</div>
        <section class="detail-section">
          <h3>핵심 해석</h3>
          ${{takeawayList(story.takeaways)}}
        </section>
        ${{mediaList(item.media)}}
        <section class="detail-section">
          <h3>핵심 수치</h3>
          ${{statList(item.stats)}}
        </section>
        ${{resourceList("분석 산출물", item.outputs)}}
        ${{resourceList("생성 script / 근거 자료", item.sources)}}
        ${{artifactViewerSection(currentResources)}}
        <section class="detail-section">
          <h3>쉬운 해석</h3>
          ${{paragraphBlock(story.plain)}}
          ${{caution}}
        </section>
        <section class="detail-section">
          <h3>상세 과정</h3>
          ${{stepList(item.steps)}}
        </section>
        <section class="detail-section">
          <h3>차트/표 읽는 법</h3>
          ${{evidenceGrid(story)}}
        </section>
      `;
      syncWorkspaceMode();
      showResourcePreview(currentResources.find(resource => previewMode(resource) === "image") || currentResources[0]);
    }}

    function preferredScrollBehavior() {{
      return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
    }}

    function scrollToSelection() {{
      window.requestAnimationFrame(() => {{
        const target = window.matchMedia("(max-width: 1180px)").matches ? detailEl : workspaceEl;
        target.scrollIntoView({{ behavior: preferredScrollBehavior(), block: "start" }});
      }});
    }}

    function syncCategoryChips() {{
      chips.forEach(item => item.classList.toggle("active", item.dataset.category === activeCategory));
    }}

    function updateSelectedCards() {{
      cardsEl.querySelectorAll(".analysis-card").forEach(cardEl => {{
        cardEl.classList.toggle("selected", cardEl.dataset.id === selectedId);
      }});
    }}

    function selectAnalysis(id, updateHash = true, scrollDetail = false) {{
      selectedId = id;
      const nextItem = data.analyses.find(analysis => analysis.id === selectedId);
      if (!nextItem) {{
        selectedId = "";
        renderDetail(null);
        updateSelectedCards();
        return;
      }}
      const groupChanged = nextItem.groupId && activeGroup !== nextItem.groupId;
      if (groupChanged) {{
        activeGroup = nextItem.groupId;
        renderGroupOverview();
        render();
      }} else {{
        renderDetail(nextItem);
        updateSelectedCards();
      }}
      if (updateHash && selectedId) {{
        history.replaceState(null, "", `${{window.location.pathname}}${{window.location.search}}#analysis-${{selectedId}}`);
      }}
      if (scrollDetail) {{
        scrollToSelection();
      }}
    }}

    function clearSelection(updateHash = true, scrollList = false) {{
      selectedId = "";
      renderDetail(null);
      updateSelectedCards();
      if (updateHash) {{
        history.replaceState(null, "", `${{window.location.pathname}}${{window.location.search}}#analysis`);
      }}
      if (scrollList) {{
        workspaceEl.scrollIntoView({{ behavior: preferredScrollBehavior(), block: "start" }});
      }}
    }}

    function matches(item, query) {{
      if (!query) return true;
      const haystack = [
        item.title, item.category, item.groupLabel, item.status, item.purpose, item.use, item.caution,
        ...(item.tags || []),
        ...(item.steps || []).map(step => `${{step.label}} ${{step.body}}`),
        ...((item.story && item.story.plain) || []),
        ...((item.story && item.story.visual) || []),
        ...((item.story && item.story.numeric) || []),
        ...(item.outputs || []).map(link => link.label),
        ...(item.outputs || []).map(link => link.path),
        ...(item.sources || []).map(link => link.label),
        ...(item.sources || []).map(link => link.path)
      ].join(" ").toLowerCase();
      return haystack.includes(query.toLowerCase());
    }}

    function activeGroupLabel() {{
      if (activeGroup === "all") return "전체 그룹";
      const group = (data.groups || []).find(item => item.id === activeGroup);
      return group ? group.label : "전체 그룹";
    }}

    function setActiveGroup(groupId, updateHash = true) {{
      activeGroup = groupId || "all";
      renderGroupOverview();
      render();
      if (updateHash) {{
        const nextHash = activeGroup === "all" ? "#analysis" : `#group-${{activeGroup}}`;
        history.replaceState(null, "", `${{window.location.pathname}}${{window.location.search}}${{nextHash}}`);
      }}
    }}

    function toggleActiveGroup(groupId, updateHash = true) {{
      setActiveGroup(activeGroup === groupId ? "all" : groupId, updateHash);
    }}

    function activateHashSelection(scrollDetail = false) {{
      const hashId = readHashSelection();
      if (hashId) {{
        const item = data.analyses.find(analysis => analysis.id === hashId);
        if (!item) return false;
        activeCategory = "all";
        activeGroup = item.groupId || "all";
        searchEl.value = "";
        selectedId = hashId;
        syncCategoryChips();
        renderGroupOverview();
        render();
        if (scrollDetail) scrollToSelection();
        return true;
      }}
      const hashGroup = readHashGroup();
      if (hashGroup) {{
        const groupExists = hashGroup === "all" || (data.groups || []).some(group => group.id === hashGroup);
        if (!groupExists) return false;
        activeCategory = "all";
        activeGroup = hashGroup;
        selectedId = "";
        searchEl.value = "";
        syncCategoryChips();
        renderGroupOverview();
        render();
        return true;
      }}
      return false;
    }}

    function render() {{
      const query = searchEl.value.trim();
      const filtered = data.analyses.filter(item => (
        (activeGroup === "all" || item.groupId === activeGroup) &&
        (activeCategory === "all" || item.category === activeCategory) &&
        matches(item, query)
      ));
      if (selectedId && !filtered.some(item => item.id === selectedId)) {{
        selectedId = "";
      }}
      cardsEl.innerHTML = filtered.map(card).join("");
      summaryEl.textContent = `${{activeGroupLabel()}} · ${{filtered.length}} / ${{data.analyses.length}}개 분석 표시`;
      emptyEl.style.display = filtered.length ? "none" : "block";
      renderDetail(selectedId ? filtered.find(item => item.id === selectedId) : null);
      updateSelectedCards();
    }}

    document.querySelector(".group-overview").addEventListener("click", event => {{
      const analysisTarget = event.target.closest("[data-analysis-id]");
      if (analysisTarget) {{
        selectAnalysis(analysisTarget.dataset.analysisId, true, true);
        return;
      }}
      const target = event.target.closest("[data-group]");
      if (!target) return;
      toggleActiveGroup(target.dataset.group);
    }});

    document.querySelector(".group-overview").addEventListener("keydown", event => {{
      if (event.key !== "Enter" && event.key !== " ") return;
      const analysisTarget = event.target.closest("[data-analysis-id]");
      if (analysisTarget) {{
        event.preventDefault();
        selectAnalysis(analysisTarget.dataset.analysisId, true, true);
        return;
      }}
      const target = event.target.closest("[data-group]");
      if (!target) return;
      event.preventDefault();
      toggleActiveGroup(target.dataset.group);
    }});

    document.querySelector(".filter-panel").addEventListener("click", event => {{
      const target = event.target.closest("[data-group]");
      if (!target) return;
      setActiveGroup(target.dataset.group);
    }});

    cardsEl.addEventListener("click", event => {{
      const cardEl = event.target.closest(".analysis-card");
      if (!cardEl) return;
      selectAnalysis(cardEl.dataset.id, true, true);
    }});

    detailEl.addEventListener("click", event => {{
      const clearButton = event.target.closest("[data-clear-selection]");
      if (clearButton) {{
        clearSelection(true, true);
        return;
      }}
      const link = event.target.closest(".resource-link[data-preview-href]");
      if (!link) return;
      event.preventDefault();
      const item = {{
        href: link.dataset.previewHref,
        label: link.dataset.previewLabel,
        path: link.dataset.previewPath,
        kind: link.dataset.previewKind
      }};
      showResourcePreview(item);
    }});

    chips.forEach(chip => {{
      chip.addEventListener("click", () => {{
        activeCategory = chip.dataset.category;
        syncCategoryChips();
        render();
      }});
    }});
    searchEl.addEventListener("input", render);
    resetEl.addEventListener("click", () => {{
      searchEl.value = "";
      activeCategory = "all";
      activeGroup = "all";
      selectedId = "";
      history.replaceState(null, "", `${{window.location.pathname}}${{window.location.search}}`);
      syncCategoryChips();
      renderGroupOverview();
      render();
    }});
    window.addEventListener("scroll", updateToolsStuck, {{ passive: true }});
    window.addEventListener("resize", updateToolsStuck);
    window.addEventListener("hashchange", () => {{
      if (activateHashSelection(true)) return;
      if (window.location.hash === "#analysis") {{
        clearSelection(false, true);
      }}
    }});
    renderGroupOverview();
    if (!activateHashSelection(true)) {{
      syncCategoryChips();
      render();
    }}
    updateToolsStuck();
  </script>
</body>
</html>
"""


def normalize_for_page(
    analyses: list[dict[str, Any]],
    output_dir: Path,
    publish_dir: Path | None = None,
    copied_assets: set[Path] | None = None,
    omitted_assets: list[dict[str, str]] | None = None,
    max_asset_bytes: int = 0,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    copied_assets = copied_assets if copied_assets is not None else set()
    omitted_assets = omitted_assets if omitted_assets is not None else []
    for item in analyses:
        next_item = dict(item)
        group = group_for_analysis(str(item.get("id", "")))
        next_item["groupId"] = group["id"]
        next_item["groupLabel"] = group["label"]
        next_item["statusClass"] = status_class(str(item.get("status", "")))
        next_item["stats"] = [
            [str(label), fmt_count(value)] for label, value in item.get("stats", []) if value is not None
        ]
        media: list[dict[str, Any]] = []
        for key in ("outputs", "sources"):
            links = []
            for link in item.get(key, []):
                path = link["path"]
                target = REPO_ROOT / path
                if publish_dir is not None and target.exists():
                    href = publish_href(path, publish_dir, copied_assets, omitted_assets, max_asset_bytes)
                else:
                    href = page_href(path, output_dir) if target.exists() else html.escape(path)
                next_link = {
                    "label": link["label"],
                    "href": href,
                    "path": path,
                    "exists": target.exists(),
                    "kind": material_kind(path),
                }
                if target.exists() and is_media_path(path):
                    next_link.update(image_dimensions(path))
                    media.append(
                        {
                            "label": link["label"],
                            "href": href,
                            "path": path,
                            **image_dimensions(path),
                        }
                    )
                links.append(next_link)
            next_item[key] = links
        next_item["media"] = media[:2]
        next_item["steps"] = detail_steps(next_item)
        next_item["story"] = detail_story(next_item)
        normalized.append(next_item)
    return normalized


def normalize_previews(
    previews: list[dict[str, str]],
    output_dir: Path,
    publish_dir: Path | None = None,
    copied_assets: set[Path] | None = None,
    omitted_assets: list[dict[str, str]] | None = None,
    max_asset_bytes: int = 0,
) -> list[dict[str, str]]:
    normalized = []
    copied_assets = copied_assets if copied_assets is not None else set()
    omitted_assets = omitted_assets if omitted_assets is not None else []
    for item in previews:
        if (REPO_ROOT / item["path"]).exists():
            if publish_dir is not None:
                href = publish_href(
                    item["path"],
                    publish_dir,
                    copied_assets,
                    omitted_assets,
                    max_asset_bytes,
                    force_copy=True,
                )
            else:
                href = page_href(item["path"], output_dir)
            normalized.append({**item, "href": href, **image_dimensions(item["path"])})
    return normalized


def build_payload(
    stats: dict[str, Any],
    analyses: list[dict[str, Any]],
    output_dir: Path,
    publish_dir: Path | None = None,
    max_asset_bytes: int = 0,
) -> dict[str, Any]:
    copied_assets: set[Path] = set()
    omitted_assets: list[dict[str, str]] = []
    relative_output = output_dir.relative_to(REPO_ROOT) if output_dir.is_relative_to(REPO_ROOT) else output_dir
    normalized_previews = normalize_previews(
        build_previews(),
        output_dir,
        publish_dir,
        copied_assets,
        omitted_assets,
        max_asset_bytes,
    )
    normalized_analyses = normalize_for_page(
        analyses,
        output_dir,
        publish_dir,
        copied_assets,
        omitted_assets,
        max_asset_bytes,
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z"),
        "repo_root": str(REPO_ROOT),
        "output_root": str(relative_output).replace(os.sep, "/"),
        "publish_bundle": publish_dir is not None,
        "stats": stats,
        "flow": build_flow(),
        "groups": build_group_summaries(normalized_analyses),
        "previews": normalized_previews,
        "analyses": normalized_analyses,
    }
    if publish_dir is not None:
        payload["publish_asset_count"] = len(copied_assets)
        payload["publish_omitted_count"] = len(omitted_assets)
        payload["publish_omitted_assets"] = omitted_assets
        payload["publish_max_linked_asset_bytes"] = max_asset_bytes
    return payload


def prepare_publish_dir(publish_dir: Path) -> None:
    publish_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = publish_dir / "assets"
    if assets_dir.exists():
        shutil.rmtree(assets_dir)


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir if args.output_dir.is_absolute() else REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    stats = build_stats()
    analyses = build_analyses(stats)
    payload = build_payload(stats, analyses, output_dir)
    write_json_manifest(output_dir, payload)
    (output_dir / "index.html").write_text(render_html(output_dir, payload), encoding="utf-8")
    print(f"Wrote {output_dir / 'index.html'}")
    print(f"Wrote {output_dir / 'analysis_dashboard_data.json'}")

    if args.publish_dir is not None:
        publish_dir = args.publish_dir if args.publish_dir.is_absolute() else REPO_ROOT / args.publish_dir
        prepare_publish_dir(publish_dir)
        max_asset_bytes = int(args.max_linked_asset_mb * 1024 * 1024)
        publish_payload = build_payload(stats, analyses, publish_dir, publish_dir, max_asset_bytes)
        write_json_manifest(publish_dir, publish_payload)
        (publish_dir / "index.html").write_text(render_html(publish_dir, publish_payload), encoding="utf-8")
        print(f"Wrote publish bundle {publish_dir / 'index.html'}")
        print(f"Copied publish assets: {publish_payload.get('publish_asset_count')}")
        print(f"Omitted large linked assets: {publish_payload.get('publish_omitted_count')}")


if __name__ == "__main__":
    main()
