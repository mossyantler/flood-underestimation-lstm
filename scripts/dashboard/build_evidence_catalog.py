#!/usr/bin/env python3
"""Build dashboard evidence catalog TypeScript and normalized DB CSVs."""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
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


def extract_analysis_copy(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"export const analysisModuleCopy = (\[.*?\]) as const", text, re.S)
    if not match:
        raise ValueError(f"cannot find JSON-compatible analysisModuleCopy in {path}")
    rows = json.loads(match.group(1))
    validate_analysis_modules(rows)
    return rows


def validate_analysis_modules(rows: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for row in rows:
        module_id = row["moduleId"]
        expected = f"{row['section']}/{row['module']}"
        if module_id != expected:
            raise ValueError(f"moduleId mismatch: {module_id!r} != {expected!r}")
        if module_id in seen:
            raise ValueError(f"duplicate moduleId: {module_id}")
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


def read_curation(repo_root: Path, path: Path) -> list[dict[str, Any]]:
    repo_root = repo_root.resolve()
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != REQUIRED_CURATION_COLUMNS:
            raise ValueError(f"unexpected curation columns in {path}: {reader.fieldnames}")
        for row in reader:
            evidence_id = row["id"]
            if evidence_id in seen_ids:
                raise ValueError(f"duplicate evidence id: {evidence_id}")
            seen_ids.add(evidence_id)

            source = repo_root / row["source_path"]
            if not source.exists():
                raise FileNotFoundError(row["source_path"])

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
                "sourcePath": row["source_path"],
                "generatorPath": row["generator_path"] or None,
                "docPath": row["doc_path"] or None,
                "chartPath": row["chart_path"] or None,
                "tablePath": row["table_path"] or None,
                "galleryPath": row["gallery_path"] or None,
                "analysisPurpose": row["analysis_purpose"] or None,
                "shortDescription": row["short_description"] or None,
                "tags": [tag for tag in row["tags"].split(";") if tag],
                "status": row["status"],
                "notes": row["notes"] or None,
            })
    return sorted(rows, key=lambda item: (item["section"], item["module"], item["priority"], item["title"]))


def _strip_none(value: Any) -> Any:
    if isinstance(value, list):
        return [_strip_none(item) for item in value]
    if isinstance(value, dict):
        return {key: _strip_none(item) for key, item in value.items() if item is not None}
    return value


def write_typescript(modules: list[dict[str, Any]], items: list[dict[str, Any]], output: Path) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "import type { AnalysisModuleCopy, EvidenceItem } from \"./evidence-types\";\n\n"
        f"export const evidenceCatalogGeneratedAt = {json.dumps(generated_at)};\n\n"
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
    write_typescript(modules, items, args.output_ts)
    write_normalized_csvs(modules, items, args.modules_output, args.items_output)
    print(f"wrote {output_label(args.output_ts, args.repo_root)} items={len(items)} modules={len(modules)}")


if __name__ == "__main__":
    main()
