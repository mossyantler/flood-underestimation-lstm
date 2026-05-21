#!/usr/bin/env python3
"""Build dashboard evidence catalog TypeScript and normalized DB CSVs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CURATION_CSV = REPO_ROOT / "dashboard/data/evidence_curation.csv"
ANALYSIS_COPY_TS = REPO_ROOT / "dashboard/lib/analysis-copy.ts"
OUT_TS = REPO_ROOT / "dashboard/lib/evidence-catalog.ts"
OUT_MODULES = REPO_ROOT / "dashboard/data/evidence_catalog_modules.csv"
OUT_ITEMS = REPO_ROOT / "dashboard/data/evidence_catalog_items.csv"

REQUIRED_CURATION_COLUMNS = [
    "id",
    "title",
    "section",
    "module",
    "kind",
    "role",
    "priority",
    "show_in_dashboard",
    "source_path",
    "generator_path",
    "doc_path",
    "chart_path",
    "table_path",
    "gallery_path",
    "analysis_purpose",
    "short_description",
    "tags",
    "status",
    "notes",
]
REQUIRED_MODULE_KEYS = [
    "moduleId",
    "section",
    "module",
    "title",
    "analysisPurpose",
    "background",
    "coreData",
    "interpretationMethod",
    "currentJudgment",
    "status",
]
REQUIRED_CURATION_VALUES = [
    "id",
    "title",
    "section",
    "module",
    "kind",
    "role",
    "priority",
    "show_in_dashboard",
    "source_path",
    "status",
]
PATH_COLUMNS = [
    "source_path",
    "generator_path",
    "doc_path",
    "chart_path",
    "table_path",
    "gallery_path",
]
SECTION_VALUES = {"overview", "experiment", "foundation", "analysis", "reference"}
KIND_VALUES = {"doc", "report", "chart", "table", "gallery", "script", "data"}
ROLE_VALUES = {"canonical", "supporting", "archive"}
STATUS_VALUES = {"ready", "needs-rerun", "planned", "stale", "archive"}


def extract_analysis_copy(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"export const analysisModuleCopy = (\[.*?\]) as const", text, re.S)
    if not match:
        raise ValueError(f"cannot find JSON-compatible analysisModuleCopy in {path}")
    rows = json.loads(match.group(1))
    validate_analysis_modules(rows)
    return rows


def validate_analysis_modules(rows: list[dict[str, Any]]) -> None:
    if not isinstance(rows, list):
        raise ValueError("analysisModuleCopy must be a list")
    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"analysis module row {index} must be an object")
        missing = [key for key in REQUIRED_MODULE_KEYS if key not in row]
        if missing:
            raise ValueError(f"analysis module row {index} missing required keys: {', '.join(missing)}")
        for key in REQUIRED_MODULE_KEYS:
            if not isinstance(row[key], str) or not row[key].strip():
                raise ValueError(f"analysis module row {index} has empty required key: {key}")

        module_id = row["moduleId"]
        expected = f"{row['section']}/{row['module']}"
        if module_id != expected:
            raise ValueError(f"moduleId mismatch: {module_id!r} != {expected!r}")
        if module_id in seen:
            raise ValueError(f"duplicate moduleId: {module_id}")
        if row["section"] not in SECTION_VALUES:
            raise ValueError(f"invalid section for module {module_id}: {row['section']!r}")
        if row["status"] not in STATUS_VALUES:
            raise ValueError(f"invalid status for module {module_id}: {row['status']!r}")
        seen.add(module_id)


def parse_bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise ValueError(f"expected true/false, got {value!r}")


def parse_priority(value: str) -> int:
    priority = int(value)
    if priority not in {1, 2, 3}:
        raise ValueError(f"expected priority 1, 2, or 3, got {value!r}")
    return priority


def validate_curation_row(row: dict[str, str], row_number: int) -> None:
    missing = [key for key in REQUIRED_CURATION_VALUES if not (row.get(key) or "").strip()]
    if missing:
        raise ValueError(f"curation row {row_number} missing required values: {', '.join(missing)}")
    evidence_id = row["id"]
    if row["section"] not in SECTION_VALUES:
        raise ValueError(f"invalid section for evidence {evidence_id}: {row['section']!r}")
    if row["kind"] not in KIND_VALUES:
        raise ValueError(f"invalid kind for evidence {evidence_id}: {row['kind']!r}")
    if row["role"] not in ROLE_VALUES:
        raise ValueError(f"invalid role for evidence {evidence_id}: {row['role']!r}")
    if row["status"] not in STATUS_VALUES:
        raise ValueError(f"invalid status for evidence {evidence_id}: {row['status']!r}")


def validate_repo_path(repo_root: Path, value: str, column: str, evidence_id: str) -> str | None:
    clean_value = value.strip()
    if not clean_value:
        return None
    candidate = Path(clean_value)
    if candidate.is_absolute():
        raise ValueError(f"{column} for {evidence_id} must be relative: {clean_value}")
    resolved = (repo_root / candidate).resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(f"{column} for {evidence_id} escapes repo root: {clean_value}") from exc
    if not resolved.exists():
        raise FileNotFoundError(f"{column} for {evidence_id} does not exist: {clean_value}")
    return clean_value


def read_curation(repo_root: Path, path: Path) -> list[dict[str, Any]]:
    repo_root = repo_root.resolve()
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != REQUIRED_CURATION_COLUMNS:
            raise ValueError(f"unexpected curation columns in {path}: {reader.fieldnames}")
        for row_number, row in enumerate(reader, start=2):
            validate_curation_row(row, row_number)
            evidence_id = row["id"]
            if evidence_id in seen_ids:
                raise ValueError(f"duplicate evidence id: {evidence_id}")
            seen_ids.add(evidence_id)

            paths = {
                column: validate_repo_path(repo_root, row[column], column, evidence_id)
                for column in PATH_COLUMNS
            }

            rows.append({
                "id": evidence_id,
                "moduleId": f"{row['section']}/{row['module']}",
                "title": row["title"],
                "section": row["section"],
                "module": row["module"],
                "kind": row["kind"],
                "role": row["role"],
                "priority": parse_priority(row["priority"]),
                "showInDashboard": parse_bool(row["show_in_dashboard"]),
                "sourcePath": paths["source_path"],
                "generatorPath": paths["generator_path"],
                "docPath": paths["doc_path"],
                "chartPath": paths["chart_path"],
                "tablePath": paths["table_path"],
                "galleryPath": paths["gallery_path"],
                "analysisPurpose": row["analysis_purpose"] or None,
                "shortDescription": row["short_description"] or None,
                "tags": [tag for tag in row["tags"].split(";") if tag],
                "status": row["status"],
                "notes": row["notes"] or None,
            })
    return sorted(rows, key=lambda item: (item["section"], item["module"], item["priority"], item["title"]))


def validate_catalog_links(modules: list[dict[str, Any]], items: list[dict[str, Any]]) -> None:
    module_ids = {module["moduleId"] for module in modules}
    for item in items:
        module_id = item["moduleId"]
        if module_id not in module_ids:
            raise ValueError(f"orphan evidence moduleId: {module_id} for item {item['id']}")


def _strip_none(value: Any) -> Any:
    if isinstance(value, list):
        return [_strip_none(item) for item in value]
    if isinstance(value, dict):
        return {key: _strip_none(item) for key, item in value.items() if item is not None}
    return value


def catalog_input_hash(modules: list[dict[str, Any]], items: list[dict[str, Any]]) -> str:
    payload = json.dumps(
        {"modules": _strip_none(modules), "items": _strip_none(items)},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_typescript(modules: list[dict[str, Any]], items: list[dict[str, Any]], output: Path) -> None:
    input_hash = catalog_input_hash(modules, items)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "import type { AnalysisModuleCopy, EvidenceItem } from \"./evidence-types\";\n\n"
        f"export const evidenceCatalogInputHash = {json.dumps(input_hash)};\n\n"
        "export const evidenceModules = "
        + json.dumps(_strip_none(modules), ensure_ascii=False, indent=2)
        + " as const satisfies readonly AnalysisModuleCopy[];\n\n"
        "export const evidenceItems = "
        + json.dumps(_strip_none(items), ensure_ascii=False, indent=2)
        + " as const satisfies readonly EvidenceItem[];\n\n"
        "export function getEvidenceForModule(moduleId: string): EvidenceItem[] {\n"
        "  return evidenceItems.filter((item) => item.moduleId === moduleId && item.showInDashboard);\n"
        "}\n\n"
        "export function getCopyForModule(moduleId: string): AnalysisModuleCopy | undefined {\n"
        "  return evidenceModules.find((item) => item.moduleId === moduleId);\n"
        "}\n",
        encoding="utf-8",
    )


def write_normalized_csvs(
    modules: list[dict[str, Any]],
    items: list[dict[str, Any]],
    modules_output: Path = OUT_MODULES,
    items_output: Path = OUT_ITEMS,
) -> None:
    modules_output.parent.mkdir(parents=True, exist_ok=True)
    with modules_output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "module_id",
                "section",
                "module",
                "title",
                "analysis_purpose",
                "background",
                "core_data",
                "interpretation_method",
                "current_judgment",
                "status",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        for module in modules:
            writer.writerow({
                "module_id": module["moduleId"],
                "section": module["section"],
                "module": module["module"],
                "title": module["title"],
                "analysis_purpose": module["analysisPurpose"],
                "background": module["background"],
                "core_data": module["coreData"],
                "interpretation_method": module["interpretationMethod"],
                "current_judgment": module["currentJudgment"],
                "status": module["status"],
            })

    items_output.parent.mkdir(parents=True, exist_ok=True)
    with items_output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "evidence_id",
                "module_id",
                "title",
                "kind",
                "role",
                "priority",
                "source_path",
                "generator_path",
                "tags",
                "status",
                "show_in_dashboard",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        for item in items:
            writer.writerow({
                "evidence_id": item["id"],
                "module_id": item["moduleId"],
                "title": item["title"],
                "kind": item["kind"],
                "role": item["role"],
                "priority": item["priority"],
                "source_path": item["sourcePath"],
                "generator_path": item.get("generatorPath") or "",
                "tags": ";".join(item["tags"]),
                "status": item["status"],
                "show_in_dashboard": str(item["showInDashboard"]).lower(),
            })


def output_label(output: Path, repo_root: Path) -> str:
    try:
        return str(output.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(output if output.is_absolute() else output.resolve())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--curation", type=Path, default=CURATION_CSV)
    parser.add_argument("--analysis-copy", type=Path, default=ANALYSIS_COPY_TS)
    parser.add_argument("--output-ts", type=Path, default=OUT_TS)
    parser.add_argument("--modules-output", type=Path, default=OUT_MODULES)
    parser.add_argument("--items-output", type=Path, default=OUT_ITEMS)
    args = parser.parse_args()

    modules = extract_analysis_copy(args.analysis_copy)
    items = read_curation(args.repo_root, args.curation)
    validate_catalog_links(modules, items)
    write_typescript(modules, items, args.output_ts)
    write_normalized_csvs(modules, items, args.modules_output, args.items_output)
    print(f"wrote {output_label(args.output_ts, args.repo_root)} items={len(items)} modules={len(modules)}")


if __name__ == "__main__":
    main()
