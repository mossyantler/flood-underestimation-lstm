# CAMELS Dashboard Evidence Portal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a catalog-backed onboarding evidence portal so CAMELS dashboard pages can explain each analysis purpose and link docs/output charts, reports, tables, galleries, and DB mirror rows.

**Architecture:** Keep dashboard copy source-of-truth in `dashboard/lib/analysis-copy.ts`, artifact curation in CSV, and generated runtime data in `dashboard/lib/evidence-catalog.ts`. Python scripts scan `docs/` and `output/`, build typed dashboard snapshots, and mirror normalized catalog rows into PostgreSQL and DuckDB without making either database canonical.

**Tech Stack:** Next.js App Router, TypeScript typed snapshots, Python 3.11 scripts with stdlib CSV/JSON, PostgreSQL SQL/import helper, DuckDB local helper, `unittest`, `npm run typecheck`, `uv run --script`.

---

## Scope Check

This plan implements the first evidence portal slice from the spec:

- candidate scanner
- CSV curation seed
- `analysis-copy.ts`
- `evidence-catalog.ts`
- PostgreSQL mirror
- DuckDB mirror
- catalog-backed UI blocks on `/overview`, `/foundation/dataset`, and `/analysis/main-result`

It does not render all chart files, add an in-browser CSV editor, or make DB rows source-of-truth.

## File Structure

Create or modify these files:

- Create `scripts/dashboard/evidence_common.py`: shared scanner/classifier/CSV helpers.
- Create `scripts/dashboard/scan_evidence_candidates.py`: scan `docs/` and `output/` to `dashboard/data/evidence_candidates.csv`.
- Create `scripts/dashboard/build_evidence_catalog.py`: read curation CSV and JSON-compatible TS copy, write dashboard TS catalog and normalized DB CSVs.
- Create `tests/test_dashboard_evidence_catalog.py`: unit tests for scanner classification, curation validation, TS copy extraction, and generated normalized rows.
- Create `dashboard/data/evidence_curation.csv`: first curated evidence seed.
- Create `dashboard/data/evidence_candidates.csv`: generated candidate snapshot from current repo scan.
- Create `dashboard/data/evidence_catalog_modules.csv`: generated normalized module copy rows for DB import.
- Create `dashboard/data/evidence_catalog_items.csv`: generated normalized evidence item rows for DB import.
- Create `dashboard/lib/evidence-types.ts`: dashboard evidence types and status/role constants.
- Create `dashboard/lib/analysis-copy.ts`: canonical UI copy for current dashboard modules.
- Create `dashboard/lib/evidence-catalog.ts`: generated runtime evidence catalog.
- Create `dashboard/components/evidence-block.tsx`: shared evidence portal UI block.
- Modify `dashboard/app/[section]/page.tsx`: add homepage evidence shortcuts.
- Modify `dashboard/app/[section]/[detail]/page.tsx`: render catalog-backed blocks on selected detail pages.
- Modify `dashboard/app/globals.css`: styles for evidence portal cards.
- Create `database/postgres/init_dashboard_evidence.sql`: `analysis_dashboard` schema.
- Create `database/postgres/import_dashboard_evidence.py`: import normalized catalog CSVs into PostgreSQL.
- Create `database/duckdb/build_dashboard_evidence_views.py`: build DuckDB mirror tables/views.
- Modify `database/README.md`: document dashboard evidence mirror source-of-truth boundary.
- Modify `dashboard/README.md`: document evidence catalog workflow.

Keep generated local DB files under `database/local/` untracked.

## Task 1: Evidence Types and Canonical Module Copy

**Files:**
- Create: `dashboard/lib/evidence-types.ts`
- Create: `dashboard/lib/analysis-copy.ts`

- [ ] **Step 1: Create evidence type definitions**

Create `dashboard/lib/evidence-types.ts` with this shape:

```ts
export const EVIDENCE_SECTIONS = ["overview", "experiment", "foundation", "analysis", "reference"] as const;
export const EVIDENCE_KINDS = ["doc", "report", "chart", "table", "gallery", "script", "data"] as const;
export const EVIDENCE_ROLES = ["canonical", "supporting", "archive"] as const;
export const EVIDENCE_STATUSES = ["ready", "needs-rerun", "planned", "stale", "archive"] as const;

export type EvidenceSection = (typeof EVIDENCE_SECTIONS)[number];
export type EvidenceKind = (typeof EVIDENCE_KINDS)[number];
export type EvidenceRole = (typeof EVIDENCE_ROLES)[number];
export type EvidenceStatus = (typeof EVIDENCE_STATUSES)[number];

export type AnalysisModuleCopy = {
  moduleId: string;
  section: EvidenceSection;
  module: string;
  title: string;
  analysisPurpose: string;
  background: string;
  coreData: string;
  interpretationMethod: string;
  currentJudgment: string;
  status: EvidenceStatus;
};

export type EvidenceItem = {
  id: string;
  moduleId: string;
  title: string;
  section: EvidenceSection;
  module: string;
  kind: EvidenceKind;
  role: EvidenceRole;
  priority: 1 | 2 | 3;
  showInDashboard: boolean;
  sourcePath: string;
  generatorPath?: string;
  docPath?: string;
  chartPath?: string;
  tablePath?: string;
  galleryPath?: string;
  analysisPurpose?: string;
  shortDescription?: string;
  tags: string[];
  status: EvidenceStatus;
  notes?: string;
};
```

- [ ] **Step 2: Create JSON-compatible module copy**

Create `dashboard/lib/analysis-copy.ts`. The exported array must stay JSON-compatible between `=` and `] as const` because Python will parse it with `json.loads`.

Seed exactly these three modules in Task 1. Add more modules in later tasks only after this first catalog slice passes verification:

```ts
import type { AnalysisModuleCopy } from "./evidence-types";

export const analysisModuleCopy = [
  {
    "moduleId": "overview/status",
    "section": "overview",
    "module": "status",
    "title": "Overview status",
    "analysisPurpose": "프로젝트 진행 상태와 rerun queue를 빠르게 확인한다.",
    "background": "뒤늦게 합류한 동료는 먼저 무엇이 완료됐고 무엇이 아직 공식 claim에 올라갈 수 없는지 알아야 한다.",
    "coreData": "evaluation test snapshot, overview status KPI, confirmed flood summary, paired seed policy.",
    "interpretationMethod": "ready는 dashboard 공식 해석에 사용할 수 있는 상태이고, needs-rerun은 source universe가 아직 맞지 않아 공식값으로 쓰지 않는 상태다.",
    "currentJudgment": "Model 1/2 paired seed 비교와 confirmed flood layer는 준비됐고, first/extreme test는 expanded basin 기준 rerun queue에 있다.",
    "status": "ready"
  },
  {
    "moduleId": "foundation/dataset",
    "section": "foundation",
    "module": "dataset",
    "title": "Dataset",
    "analysisPurpose": "CAMELSH 원천, model input, result data, analysis data의 경계를 구분한다.",
    "background": "산출물이 많아지면 input, raw result, analysis summary가 섞인다. 동료가 데이터 성격을 먼저 알아야 잘못된 비교를 피할 수 있다.",
    "coreData": "CAMELSH hourly source, prepared generic dataset, split files, coverage diagnostics, analysis summary tables.",
    "interpretationMethod": "input data는 모델에 들어간 자료, result data는 inference와 metric raw output, analysis data는 결과 해석을 위해 가공한 table/chart로 읽는다.",
    "currentJudgment": "Dashboard는 source-of-truth를 대체하지 않고, configs/docs/output에 있는 데이터와 산출물의 접근 경로를 정리한다.",
    "status": "ready"
  },
  {
    "moduleId": "analysis/main-result",
    "section": "analysis",
    "module": "main-result",
    "title": "Main result",
    "analysisPurpose": "Model 2 quantile head가 Model 1 대비 extreme peak 과소추정을 줄였는지 확인한다.",
    "background": "Model 1은 하나의 point prediction만 내기 때문에 extreme peak에서 낮게 예측될 수 있다. Model 2는 같은 LSTM backbone에 quantile head를 붙여 upper-tail prediction을 직접 비교한다.",
    "coreData": "DRBC holdout, paired seed 111/222/444, Q99 exceedance, observed peak hour.",
    "interpretationMethod": "underestimation fraction은 관측값보다 예측값이 낮은 비율이다. 낮을수록 peak를 덜 놓쳤다는 뜻이지만 q99를 calibrated 99% interval로 해석하면 안 된다.",
    "currentJudgment": "q99는 peak underestimation을 줄이는 방향이 보인다. Calibration과 false-positive tradeoff는 별도 module에서 확인한다.",
    "status": "ready"
  }
] as const satisfies readonly AnalysisModuleCopy[];

export function getAnalysisModuleCopy(moduleId: string) {
  return analysisModuleCopy.find((item) => item.moduleId === moduleId);
}
```

- [ ] **Step 3: Run TypeScript check**

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd dashboard
npm run typecheck
```

Expected: `tsc --noEmit` exits `0`.

- [ ] **Step 4: Commit Task 1**

```bash
git add dashboard/lib/evidence-types.ts dashboard/lib/analysis-copy.ts
git commit -m "feat: define dashboard evidence copy types"
```

## Task 2: Candidate Scanner

**Files:**
- Create: `scripts/dashboard/evidence_common.py`
- Create: `scripts/dashboard/scan_evidence_candidates.py`
- Create: `tests/test_dashboard_evidence_catalog.py`
- Create: `dashboard/data/evidence_candidates.csv`

- [ ] **Step 1: Write scanner tests**

Add these test cases to `tests/test_dashboard_evidence_catalog.py`:

```python
from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.dashboard import evidence_common as common
from scripts.dashboard import scan_evidence_candidates as scanner


class DashboardEvidenceCatalogTests(unittest.TestCase):
    def test_classify_main_result_doc(self) -> None:
        candidate = common.classify_path(Path("docs/experiment/analysis/model/02_primary_high_flow_peak_performance.md"))
        self.assertEqual(candidate.section, "analysis")
        self.assertEqual(candidate.module, "main-result")
        self.assertEqual(candidate.kind, "doc")
        self.assertEqual(candidate.role_hint, "canonical")

    def test_scanner_excludes_raw_timeseries_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "output/model_analysis/expanded_drbc_test/raw_timeseries/model1_seed111_epoch025.csv"
            raw.parent.mkdir(parents=True)
            raw.write_text("a,b\n1,2\n", encoding="utf-8")
            candidates = scanner.scan_paths(root)
            self.assertEqual(candidates, [])

    def test_scanner_keeps_summary_chart_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = root / "docs/experiment/analysis/model/02_primary_high_flow_peak_performance.md"
            fig = root / "output/model_analysis/probabilistic_diagnostics/figures/primary_all_quantile_calibration.png"
            summary = root / "output/model_analysis/expanded_drbc_test/analysis_summary.json"
            for path in [doc, fig, summary]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# Title\n", encoding="utf-8") if path.suffix == ".md" else path.write_bytes(b"demo")
            candidates = scanner.scan_paths(root)
            rels = {row.source_path for row in candidates}
            self.assertIn("docs/experiment/analysis/model/02_primary_high_flow_peak_performance.md", rels)
            self.assertIn("output/model_analysis/probabilistic_diagnostics/figures/primary_all_quantile_calibration.png", rels)
            self.assertIn("output/model_analysis/expanded_drbc_test/analysis_summary.json", rels)
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run python -m unittest tests.test_dashboard_evidence_catalog -v
```

Expected: FAIL with import error because `scripts/dashboard/evidence_common.py` does not exist.

- [ ] **Step 3: Implement shared scanner helpers**

Create `scripts/dashboard/evidence_common.py` with:

```python
from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


SECTIONS = {"overview", "experiment", "foundation", "analysis", "reference"}
KINDS = {"doc", "report", "chart", "table", "gallery", "script", "data"}
ROLES = {"canonical", "supporting", "archive"}
STATUSES = {"ready", "needs-rerun", "planned", "stale", "archive"}


@dataclass(frozen=True)
class Candidate:
    id: str
    title: str
    section: str
    module: str
    kind: str
    role_hint: str
    priority_hint: int
    source_path: str
    tags: str
    status_hint: str


def stable_id(source_path: str) -> str:
    stem = re.sub(r"[^0-9a-zA-Z]+", "-", Path(source_path).stem).strip("-").lower()
    digest = hashlib.sha1(source_path.encode("utf-8")).hexdigest()[:8]
    return f"{stem}-{digest}"


def title_from_path(path: Path) -> str:
    if path.suffix.lower() == ".md" and path.exists():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    return path.stem.replace("_", " ").replace("-", " ").strip().title()


def kind_for(path: Path) -> str:
    suffix = path.suffix.lower()
    name = path.name.lower()
    if suffix == ".md" and "report" in name:
        return "report"
    if suffix == ".md":
        return "doc"
    if suffix in {".png", ".svg"}:
        return "chart"
    if suffix == ".html":
        return "gallery"
    if suffix == ".csv":
        return "table"
    if suffix == ".json":
        return "data"
    if suffix in {".py", ".sh"}:
        return "script"
    return "data"


def classify_path(relative_path: Path) -> Candidate:
    text = str(relative_path).replace("\\", "/")
    lower = text.lower()
    section = "analysis"
    module = "main-result"
    role = "supporting"
    priority = 2
    status = "ready"

    if lower.startswith("docs/references/"):
        section, module = "reference", "analysis"
    elif "experiment/method" in lower or "expanded_drbc_test" in lower:
        section, module = "experiment", "workflow"
    elif "method/data" in lower or "timeseries" in lower or "input_coverage" in lower:
        section, module = "foundation", "dataset"
    elif "method/model" in lower or "model_structure" in lower or "hyperparameter" in lower:
        section, module = "foundation", "model"
    elif "/basin/" in lower or "drbc_boundary" in lower or "basin_attributes" in lower:
        section, module = "foundation", "basin"
    elif "hydrograph" in lower or "event_plot" in lower:
        section, module = "analysis", "hydrograph"
    elif "confirmed_flood" in lower:
        section, module = "analysis", "confirmed-flood"
    elif "probabilistic_diagnostics" in lower or "calibration" in lower or "pinball" in lower:
        section, module = "analysis", "calibration"
    elif "stress" in lower or "extreme_rain" in lower:
        section, module = "analysis", "stress"
    elif "event_regime" in lower:
        section, module = "analysis", "event-regime"
    elif "attribute" in lower:
        section, module = "analysis", "attribute"

    if "docs/experiment/analysis" in lower or "paper_result_assets" in lower:
        role = "canonical"
        priority = 1
    if "archive" in lower:
        role = "archive"
        priority = 3
        status = "archive"
    if "expanded_drbc_test" in lower or "extreme_rain" in lower:
        status = "needs-rerun" if "expanded" in lower or "extreme_rain" in lower else status

    return Candidate(
        id=stable_id(text),
        title=title_from_path(relative_path),
        section=section,
        module=module,
        kind=kind_for(relative_path),
        role_hint=role,
        priority_hint=priority,
        source_path=text,
        tags=";".join(part for part in [section, module, kind_for(relative_path)] if part),
        status_hint=status,
    )


def write_candidates_csv(path: Path, rows: list[Candidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(Candidate.__dataclass_fields__.keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)
```

- [ ] **Step 4: Implement scanner script**

Create `scripts/dashboard/scan_evidence_candidates.py` with:

```python
#!/usr/bin/env python3
"""Scan docs/output artifacts into dashboard evidence candidate CSV."""
from __future__ import annotations

import argparse
from pathlib import Path

from scripts.dashboard.evidence_common import Candidate, classify_path, write_candidates_csv


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "dashboard/data/evidence_candidates.csv"
SCAN_ROOTS = [Path("docs"), Path("output")]
INCLUDE_SUFFIXES = {".md", ".html", ".png", ".svg", ".csv", ".json"}
EXCLUDED_PARTS = {"raw_model_exports", "raw_timeseries", "required_series", "quantile_exports"}


def should_include(path: Path) -> bool:
    lower_parts = {part.lower() for part in path.parts}
    if lower_parts & EXCLUDED_PARTS:
        return False
    suffix = path.suffix.lower()
    if suffix not in INCLUDE_SUFFIXES:
        return False
    text = str(path).lower()
    if suffix in {".csv", ".json"}:
        return any(token in text for token in ["summary", "manifest", "metadata", "chart_manifest", "coverage", "primary_epoch"])
    return True


def scan_paths(root: Path) -> list[Candidate]:
    rows: list[Candidate] = []
    for scan_root in SCAN_ROOTS:
        absolute_root = root / scan_root
        if not absolute_root.exists():
            continue
        for path in sorted(absolute_root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            if should_include(rel):
                rows.append(classify_path(rel))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    rows = scan_paths(args.repo_root)
    write_candidates_csv(args.output, rows)
    print(f"wrote {args.output.relative_to(args.repo_root)} rows={len(rows)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run scanner tests**

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run python -m unittest tests.test_dashboard_evidence_catalog -v
```

Expected: all scanner tests pass.

- [ ] **Step 6: Generate candidates**

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run scripts/dashboard/scan_evidence_candidates.py
```

Expected: prints `wrote dashboard/data/evidence_candidates.csv rows=<positive number>`.

- [ ] **Step 7: Commit Task 2**

```bash
git add scripts/dashboard/evidence_common.py scripts/dashboard/scan_evidence_candidates.py tests/test_dashboard_evidence_catalog.py dashboard/data/evidence_candidates.csv
git commit -m "feat: scan dashboard evidence candidates"
```

## Task 3: Curation CSV and Catalog Builder

**Files:**
- Create: `dashboard/data/evidence_curation.csv`
- Create: `scripts/dashboard/build_evidence_catalog.py`
- Create: `dashboard/lib/evidence-catalog.ts`
- Create: `dashboard/data/evidence_catalog_modules.csv`
- Create: `dashboard/data/evidence_catalog_items.csv`
- Modify: `tests/test_dashboard_evidence_catalog.py`

- [ ] **Step 1: Add builder tests**

Append these tests:

```python
    def test_extract_analysis_copy_from_ts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ts = root / "dashboard/lib/analysis-copy.ts"
            ts.parent.mkdir(parents=True)
            ts.write_text(
                'export const analysisModuleCopy = [{"moduleId":"analysis/main-result","section":"analysis","module":"main-result","title":"Main","analysisPurpose":"purpose","background":"bg","coreData":"data","interpretationMethod":"method","currentJudgment":"judgment","status":"ready"}] as const;',
                encoding="utf-8",
            )
            from scripts.dashboard import build_evidence_catalog as builder
            rows = builder.extract_analysis_copy(ts)
            self.assertEqual(rows[0]["moduleId"], "analysis/main-result")

    def test_build_catalog_rejects_missing_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            curation = root / "dashboard/data/evidence_curation.csv"
            curation.parent.mkdir(parents=True)
            with curation.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=[
                    "id", "title", "section", "module", "kind", "role", "priority",
                    "show_in_dashboard", "source_path", "generator_path", "doc_path",
                    "chart_path", "table_path", "gallery_path", "analysis_purpose",
                    "short_description", "tags", "status", "notes",
                ])
                writer.writeheader()
                writer.writerow({
                    "id": "missing", "title": "Missing", "section": "analysis",
                    "module": "main-result", "kind": "doc", "role": "canonical",
                    "priority": "1", "show_in_dashboard": "true",
                    "source_path": "docs/missing.md", "generator_path": "",
                    "doc_path": "", "chart_path": "", "table_path": "", "gallery_path": "",
                    "analysis_purpose": "", "short_description": "", "tags": "analysis",
                    "status": "ready", "notes": "",
                })
            from scripts.dashboard import build_evidence_catalog as builder
            with self.assertRaises(FileNotFoundError):
                builder.read_curation(root, curation)
```

- [ ] **Step 2: Create curation seed CSV**

Create `dashboard/data/evidence_curation.csv` with these rows first. Use comma CSV quoting for descriptions that contain commas.

```csv
id,title,section,module,kind,role,priority,show_in_dashboard,source_path,generator_path,doc_path,chart_path,table_path,gallery_path,analysis_purpose,short_description,tags,status,notes
architecture-md,Model architecture,foundation,model,doc,canonical,1,true,docs/experiment/method/model/architecture.md,,docs/experiment/method/model/architecture.md,,,,Model 1 and Model 2 비교 구조,LSTM backbone and quantile head boundary,model;architecture;canonical,ready,
primary-high-flow-md,Primary high-flow peak performance,analysis,main-result,doc,canonical,1,true,docs/experiment/analysis/model/02_primary_high_flow_peak_performance.md,,docs/experiment/analysis/model/02_primary_high_flow_peak_performance.md,,,,Model 2 q99 peak underestimation claim,Main claim interpretation doc,analysis;main-result;q99,ready,
paper-assets-report,Paper result assets report,overview,status,report,canonical,1,true,output/model_analysis/paper_result_assets/report/paper_result_assets_report.md,,output/model_analysis/paper_result_assets/report/paper_result_assets_report.md,,,,Homepage result evidence,Paper-ready result asset summary,overview;paper-assets,ready,
high-flow-chart,High-flow quantile comparison,analysis,main-result,chart,canonical,1,true,output/model_analysis/overall_analysis/main_comparison/figures/overall_conclusion/overall_conclusion_high_flow_quantiles.png,,docs/experiment/analysis/model/02_primary_high_flow_peak_performance.md,output/model_analysis/overall_analysis/main_comparison/figures/overall_conclusion/overall_conclusion_high_flow_quantiles.png,,,Q99 exceedance quantile comparison,Primary chart for peak underestimation claim,analysis;chart;q99,ready,
dataset-guide,Data processing guide,foundation,dataset,doc,canonical,1,true,docs/experiment/method/data/data_processing_analysis_guide.md,,docs/experiment/method/data/data_processing_analysis_guide.md,,,,Input result analysis data boundary,Dataset workflow guide,foundation;dataset;data,ready,
input-coverage-overview,Input coverage overview,foundation,dataset,chart,supporting,2,true,output/basin/timeseries/input_coverage/figures/overview.png,,,output/basin/timeseries/input_coverage/figures/overview.png,,,CAMELSH input coverage,Input coverage figure,foundation;dataset;coverage,ready,
confirmed-flood-performance,Confirmed flood performance table,analysis,confirmed-flood,table,canonical,1,true,output/model_analysis/confirmed_flood/performance/drbc_confirmed_flood_performance.csv,scripts/model/confirmed_flood/export_confirmed_flood_dashboard_snapshot.py,,,output/model_analysis/confirmed_flood/performance/drbc_confirmed_flood_performance.csv,,NWS flood-stage event audit,Confirmed flood model performance rows,analysis;confirmed-flood,ready,
calibration-report,Probabilistic diagnostics report,analysis,calibration,report,canonical,1,true,output/model_analysis/probabilistic_diagnostics/report/probabilistic_diagnostics_report.md,,output/model_analysis/probabilistic_diagnostics/report/probabilistic_diagnostics_report.md,,,,q99 calibration caveat,Quantile coverage and pinball interpretation,analysis;calibration,ready,
hydrograph-candidates,Representative hydrograph candidates,analysis,hydrograph,table,canonical,1,true,output/model_analysis/paper_result_assets/tables/representative_hydrograph_candidates.csv,,,,output/model_analysis/paper_result_assets/tables/representative_hydrograph_candidates.csv,,Hydrograph representative evidence,Selected basin/event hydrograph candidates,analysis;hydrograph,ready,
reference-related-papers,Related papers map,reference,analysis,doc,supporting,2,true,docs/references/related_papers.md,,docs/references/related_papers.md,,,,Literature map for analysis claims,Related paper index,reference;papers,supporting,ready,
```

- [ ] **Step 3: Implement catalog builder**

Create `scripts/dashboard/build_evidence_catalog.py` with functions:

```python
#!/usr/bin/env python3
"""Build dashboard evidence catalog TypeScript and normalized DB CSVs."""
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
CURATION_CSV = REPO_ROOT / "dashboard/data/evidence_curation.csv"
ANALYSIS_COPY_TS = REPO_ROOT / "dashboard/lib/analysis-copy.ts"
OUT_TS = REPO_ROOT / "dashboard/lib/evidence-catalog.ts"
OUT_MODULES = REPO_ROOT / "dashboard/data/evidence_catalog_modules.csv"
OUT_ITEMS = REPO_ROOT / "dashboard/data/evidence_catalog_items.csv"


def extract_analysis_copy(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"export const analysisModuleCopy = (\\[.*?\\]) as const", text, re.S)
    if not match:
        raise ValueError(f"cannot find JSON-compatible analysisModuleCopy in {path}")
    return json.loads(match.group(1))


def parse_bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise ValueError(f"expected true/false, got {value!r}")


def read_curation(repo_root: Path, path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            source = repo_root / row["source_path"]
            if not source.exists():
                raise FileNotFoundError(row["source_path"])
            rows.append({
                "id": row["id"],
                "moduleId": f"{row['section']}/{row['module']}",
                "title": row["title"],
                "section": row["section"],
                "module": row["module"],
                "kind": row["kind"],
                "role": row["role"],
                "priority": int(row["priority"]),
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


def write_typescript(modules: list[dict[str, Any]], items: list[dict[str, Any]], output: Path) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    output.write_text(
        "import type { AnalysisModuleCopy, EvidenceItem } from \"./evidence-types\";\\n\\n"
        f"export const evidenceCatalogGeneratedAt = {json.dumps(generated_at)};\\n\\n"
        "export const evidenceModules = "
        + json.dumps(modules, ensure_ascii=False, indent=2)
        + " as const satisfies readonly AnalysisModuleCopy[];\\n\\n"
        "export const evidenceItems = "
        + json.dumps(items, ensure_ascii=False, indent=2)
        + " as const satisfies readonly EvidenceItem[];\\n\\n"
        "export function getEvidenceForModule(moduleId: string) {\\n"
        "  return evidenceItems.filter((item) => item.moduleId === moduleId && item.showInDashboard);\\n"
        "}\\n\\n"
        "export function getCopyForModule(moduleId: string) {\\n"
        "  return evidenceModules.find((item) => item.moduleId === moduleId);\\n"
        "}\\n",
        encoding="utf-8",
    )


def write_normalized_csvs(modules: list[dict[str, Any]], items: list[dict[str, Any]]) -> None:
    OUT_MODULES.parent.mkdir(parents=True, exist_ok=True)
    with OUT_MODULES.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["module_id", "section", "module", "title", "analysis_purpose", "background", "core_data", "interpretation_method", "current_judgment", "status"])
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
    with OUT_ITEMS.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["evidence_id", "module_id", "title", "kind", "role", "priority", "source_path", "generator_path", "tags", "status", "show_in_dashboard"])
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--curation", type=Path, default=CURATION_CSV)
    parser.add_argument("--analysis-copy", type=Path, default=ANALYSIS_COPY_TS)
    parser.add_argument("--output-ts", type=Path, default=OUT_TS)
    args = parser.parse_args()
    modules = extract_analysis_copy(args.analysis_copy)
    items = read_curation(args.repo_root, args.curation)
    write_typescript(modules, items, args.output_ts)
    write_normalized_csvs(modules, items)
    print(f"wrote {args.output_ts.relative_to(args.repo_root)} items={len(items)} modules={len(modules)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run catalog tests and builder**

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run python -m unittest tests.test_dashboard_evidence_catalog -v
uv run scripts/dashboard/build_evidence_catalog.py
```

Expected:

- unittest exits `0`
- builder prints `wrote dashboard/lib/evidence-catalog.ts items=10 modules=3`

- [ ] **Step 5: Run TypeScript check**

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd dashboard
npm run typecheck
```

Expected: exits `0`.

- [ ] **Step 6: Commit Task 3**

```bash
git add dashboard/data/evidence_curation.csv dashboard/data/evidence_catalog_modules.csv dashboard/data/evidence_catalog_items.csv dashboard/lib/evidence-catalog.ts scripts/dashboard/build_evidence_catalog.py tests/test_dashboard_evidence_catalog.py
git commit -m "feat: build dashboard evidence catalog"
```

## Task 4: Catalog-Backed Evidence UI

**Files:**
- Create: `dashboard/components/evidence-block.tsx`
- Modify: `dashboard/app/[section]/page.tsx`
- Modify: `dashboard/app/[section]/[detail]/page.tsx`
- Modify: `dashboard/app/globals.css`

- [ ] **Step 1: Create shared evidence block component**

Create `dashboard/components/evidence-block.tsx`:

```tsx
import Link from "next/link";
import type { AnalysisModuleCopy, EvidenceItem } from "@/lib/evidence-types";

type EvidenceBlockProps = {
  copy: AnalysisModuleCopy;
  items: readonly EvidenceItem[];
};

const ROLE_LABEL: Record<EvidenceItem["role"], string> = {
  canonical: "공식",
  supporting: "보조",
  archive: "보관",
};

export function EvidenceBlock({ copy, items }: EvidenceBlockProps) {
  const visibleItems = [...items].sort((a, b) => a.priority - b.priority || a.title.localeCompare(b.title));
  return (
    <section className="evidence-block">
      <div className="evidence-copy-grid">
        <article className="evidence-copy-card">
          <span>분석 목적</span>
          <p>{copy.analysisPurpose}</p>
        </article>
        <article className="evidence-copy-card">
          <span>배경 설명</span>
          <p>{copy.background}</p>
        </article>
        <article className="evidence-copy-card">
          <span>핵심 데이터</span>
          <p>{copy.coreData}</p>
        </article>
        <article className="evidence-copy-card">
          <span>해석 방법</span>
          <p>{copy.interpretationMethod}</p>
        </article>
        <article className="evidence-copy-card evidence-copy-card-wide">
          <span>현재 판단</span>
          <p>{copy.currentJudgment}</p>
        </article>
      </div>
      <div className="evidence-list" aria-label={`${copy.title} 근거 경로`}>
        {visibleItems.map((item) => (
          <EvidenceRow key={item.id} item={item} />
        ))}
      </div>
    </section>
  );
}

function EvidenceRow({ item }: { item: EvidenceItem }) {
  const path = item.chartPath ?? item.galleryPath ?? item.docPath ?? item.tablePath ?? item.sourcePath;
  return (
    <article className="evidence-row" data-role={item.role}>
      <div>
        <span className="evidence-row-kicker">{ROLE_LABEL[item.role]} · {item.kind}</span>
        <strong>{item.title}</strong>
        {item.shortDescription && <p>{item.shortDescription}</p>}
      </div>
      <code>{item.sourcePath}</code>
      {path.startsWith("/") || path.startsWith("http") ? (
        <Link href={path} className="panel-detail-link">열기</Link>
      ) : (
        <span className="panel-detail-link" aria-label="local source path">source</span>
      )}
    </article>
  );
}
```

- [ ] **Step 2: Wire `/overview` homepage shortcuts**

Modify `dashboard/app/[section]/page.tsx`:

```tsx
import { EvidenceBlock } from "@/components/evidence-block";
import { getCopyForModule, getEvidenceForModule } from "@/lib/evidence-catalog";
```

Inside `OverviewSection`, after `<StatusBoard />`, add:

```tsx
const copy = getCopyForModule("overview/status");
const evidence = getEvidenceForModule("overview/status");

{copy && <EvidenceBlock copy={copy} items={evidence} />}
```

If `OverviewSection` is not allowed to use local constants before return, convert it to:

```tsx
function OverviewSection() {
  const copy = getCopyForModule("overview/status");
  const evidence = getEvidenceForModule("overview/status");
  return (
    <>
      <p className="section-lede">
        CAMELS dashboard는 연구 claim의 상태와 근거를 관리하고, headline indicator에서 raw hydrologic evidence까지 내려가는 실험 검토 workbench다.
      </p>
      <StatusBoard />
      {copy && <EvidenceBlock copy={copy} items={evidence} />}
    </>
  );
}
```

- [ ] **Step 3: Wire detail pages**

In `dashboard/app/[section]/[detail]/page.tsx`, import:

```tsx
import { EvidenceBlock } from "@/components/evidence-block";
import { getCopyForModule, getEvidenceForModule } from "@/lib/evidence-catalog";
```

In `DetailPage`, after the ``const content = DETAIL_CONTENT[`${section}/${detail}`];`` line, add:

```tsx
const moduleId = `${section}/${detail}`;
const copy = getCopyForModule(moduleId);
const evidence = getEvidenceForModule(moduleId);
```

After the lede and before the existing panel grid, render:

```tsx
{copy && <EvidenceBlock copy={copy} items={evidence} />}
```

- [ ] **Step 4: Add evidence styles**

Append to `dashboard/app/globals.css`:

```css
.evidence-block {
  display: grid;
  gap: 12px;
}

.evidence-copy-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.evidence-copy-card {
  background: var(--panel);
  border: 1px solid var(--hairline);
  border-radius: var(--r-lg);
  display: grid;
  gap: 7px;
  padding: 14px;
}

.evidence-copy-card-wide {
  grid-column: 1 / -1;
}

.evidence-copy-card span,
.evidence-row-kicker {
  color: var(--ink-dim);
  font-family: var(--font-geist-mono), monospace;
  font-size: 9px;
}

.evidence-copy-card p,
.evidence-row p {
  color: var(--ink-body);
  font-size: 12px;
  line-height: 1.65;
  margin: 0;
}

.evidence-list {
  display: grid;
  gap: 8px;
}

.evidence-row {
  align-items: start;
  background: var(--panel-inner);
  border: 1px solid var(--hairline);
  border-radius: var(--r-md);
  display: grid;
  gap: 8px;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr) auto;
  padding: 12px;
}

.evidence-row[data-role="canonical"] {
  border-color: color-mix(in srgb, #50e3c2 36%, var(--hairline));
}

.evidence-row strong {
  color: var(--ink);
  display: block;
  font-size: 12px;
  margin-top: 4px;
}

.evidence-row code {
  color: var(--ink-dim);
  font-family: var(--font-geist-mono), monospace;
  font-size: 9px;
  overflow-wrap: anywhere;
}

@media (max-width: 899px) {
  .evidence-copy-grid,
  .evidence-row {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 5: Verify UI typecheck and routes**

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd dashboard
npm run typecheck
```

Expected: exits `0`.

Run from repo root:

```bash
export PATH="/opt/homebrew/bin:$PATH"
for p in overview foundation/dataset analysis/main-result; do
  code=$(curl -s -o /tmp/camels_evidence_${p//\//_}.html -w '%{http_code}' "http://localhost:3000/$p")
  printf '%s %s\n' "$p" "$code"
done
```

Expected:

```text
overview 200
foundation/dataset 200
analysis/main-result 200
```

- [ ] **Step 6: Commit Task 4**

```bash
git add dashboard/components/evidence-block.tsx dashboard/app/[section]/page.tsx dashboard/app/[section]/[detail]/page.tsx dashboard/app/globals.css
git commit -m "feat: show catalog-backed dashboard evidence blocks"
```

## Task 5: PostgreSQL Mirror

**Files:**
- Create: `database/postgres/init_dashboard_evidence.sql`
- Create: `database/postgres/import_dashboard_evidence.py`
- Modify: `database/README.md`

- [ ] **Step 1: Create PostgreSQL schema file**

Create `database/postgres/init_dashboard_evidence.sql`:

```sql
CREATE SCHEMA IF NOT EXISTS analysis_dashboard;

CREATE TABLE IF NOT EXISTS analysis_dashboard.modules (
    module_id text PRIMARY KEY,
    section text NOT NULL,
    module text NOT NULL,
    title text NOT NULL,
    analysis_purpose text NOT NULL,
    background text NOT NULL,
    core_data text NOT NULL,
    interpretation_method text NOT NULL,
    current_judgment text NOT NULL,
    status text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS analysis_dashboard.evidence_items (
    evidence_id text PRIMARY KEY,
    module_id text NOT NULL REFERENCES analysis_dashboard.modules(module_id) ON DELETE CASCADE,
    title text NOT NULL,
    kind text NOT NULL,
    role text NOT NULL,
    priority integer NOT NULL,
    source_path text NOT NULL,
    generator_path text,
    tags text[] NOT NULL,
    status text NOT NULL,
    show_in_dashboard boolean NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS evidence_items_module_id_idx
    ON analysis_dashboard.evidence_items (module_id);

CREATE INDEX IF NOT EXISTS evidence_items_role_priority_idx
    ON analysis_dashboard.evidence_items (role, priority);
```

- [ ] **Step 2: Create importer**

Create `database/postgres/import_dashboard_evidence.py` with:

```python
#!/usr/bin/env python3
"""Import dashboard evidence catalog mirror into PostgreSQL."""
from __future__ import annotations

import argparse
import csv
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_SQL = REPO_ROOT / "database/postgres/init_dashboard_evidence.sql"
MODULES_CSV = REPO_ROOT / "dashboard/data/evidence_catalog_modules.csv"
ITEMS_CSV = REPO_ROOT / "dashboard/data/evidence_catalog_items.csv"


def run_psql(database: str, sql: str | None = None, file_path: Path | None = None) -> None:
    args = ["psql", "-v", "ON_ERROR_STOP=1", "-d", database]
    if file_path is not None:
        args.extend(["-f", str(file_path)])
        subprocess.run(args, check=True)
        return
    subprocess.run(args, input=sql, text=True, check=True)


def sql_literal(value: str | None) -> str:
    if value is None or value == "":
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def sql_array(value: str) -> str:
    tags = [tag for tag in value.split(";") if tag]
    return "ARRAY[" + ", ".join(sql_literal(tag) for tag in tags) + "]::text[]"


def import_modules(database: str, path: Path) -> int:
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    values = []
    for row in rows:
        values.append(
            "("
            + ", ".join(
                sql_literal(row[column])
                for column in [
                    "module_id", "section", "module", "title", "analysis_purpose",
                    "background", "core_data", "interpretation_method", "current_judgment", "status",
                ]
            )
            + ")"
        )
    if values:
        run_psql(database, "TRUNCATE analysis_dashboard.evidence_items, analysis_dashboard.modules;\n")
        run_psql(
            database,
            "INSERT INTO analysis_dashboard.modules (module_id, section, module, title, analysis_purpose, background, core_data, interpretation_method, current_judgment, status) VALUES\n"
            + ",\n".join(values)
            + " ON CONFLICT (module_id) DO UPDATE SET title = EXCLUDED.title, analysis_purpose = EXCLUDED.analysis_purpose, updated_at = now();\n",
        )
    return len(rows)


def import_items(database: str, path: Path) -> int:
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    values = []
    for row in rows:
        values.append(
            "("
            + ", ".join([
                sql_literal(row["evidence_id"]),
                sql_literal(row["module_id"]),
                sql_literal(row["title"]),
                sql_literal(row["kind"]),
                sql_literal(row["role"]),
                row["priority"],
                sql_literal(row["source_path"]),
                sql_literal(row["generator_path"]),
                sql_array(row["tags"]),
                sql_literal(row["status"]),
                row["show_in_dashboard"],
            ])
            + ")"
        )
    if values:
        run_psql(
            database,
            "INSERT INTO analysis_dashboard.evidence_items (evidence_id, module_id, title, kind, role, priority, source_path, generator_path, tags, status, show_in_dashboard) VALUES\n"
            + ",\n".join(values)
            + " ON CONFLICT (evidence_id) DO UPDATE SET title = EXCLUDED.title, role = EXCLUDED.role, priority = EXCLUDED.priority, updated_at = now();\n",
        )
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default="camels")
    parser.add_argument("--modules", type=Path, default=MODULES_CSV)
    parser.add_argument("--items", type=Path, default=ITEMS_CSV)
    args = parser.parse_args()
    run_psql(args.database, file_path=SCHEMA_SQL)
    module_count = import_modules(args.database, args.modules)
    item_count = import_items(args.database, args.items)
    print(f"imported analysis_dashboard.modules={module_count} evidence_items={item_count}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Document source-of-truth boundary**

Append to `database/README.md`:

```markdown
## Dashboard Evidence Mirror

`analysis_dashboard.*` tables mirror `dashboard/lib/analysis-copy.ts` and `dashboard/data/evidence_curation.csv`.
Do not edit these rows directly. Update the TypeScript copy or CSV curation file, regenerate `dashboard/lib/evidence-catalog.ts`, then rerun the importer.
```

- [ ] **Step 4: Verify importer syntax**

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run python -m py_compile database/postgres/import_dashboard_evidence.py
```

Expected: exits `0`.

If local PostgreSQL database `camels` is available, run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run database/postgres/import_dashboard_evidence.py --database camels
```

Expected: prints `imported analysis_dashboard.modules=3 evidence_items=10`.

- [ ] **Step 5: Commit Task 5**

```bash
git add database/postgres/init_dashboard_evidence.sql database/postgres/import_dashboard_evidence.py database/README.md
git commit -m "feat: mirror dashboard evidence catalog in postgres"
```

## Task 6: DuckDB Mirror

**Files:**
- Create: `database/duckdb/build_dashboard_evidence_views.py`
- Modify: `database/duckdb/README.md`

- [ ] **Step 1: Create DuckDB mirror script**

Create `database/duckdb/build_dashboard_evidence_views.py`:

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["duckdb>=1.1"]
# ///
"""Build DuckDB mirror tables for dashboard evidence catalog."""
from __future__ import annotations

import argparse
from pathlib import Path

import duckdb


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE = REPO_ROOT / "database/local/duckdb/camels.duckdb"
MODULES_CSV = REPO_ROOT / "dashboard/data/evidence_catalog_modules.csv"
ITEMS_CSV = REPO_ROOT / "dashboard/data/evidence_catalog_items.csv"


def build_views(database: Path, modules_csv: Path, items_csv: Path) -> tuple[int, int]:
    database.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(database)) as con:
        con.execute("CREATE SCHEMA IF NOT EXISTS analysis_dashboard")
        con.execute(
            "CREATE OR REPLACE TABLE analysis_dashboard.modules AS "
            "SELECT * FROM read_csv_auto(?, union_by_name=true)",
            [str(modules_csv)],
        )
        con.execute(
            "CREATE OR REPLACE TABLE analysis_dashboard.evidence_items AS "
            "SELECT * FROM read_csv_auto(?, union_by_name=true)",
            [str(items_csv)],
        )
        module_count = int(con.execute("SELECT count(*) FROM analysis_dashboard.modules").fetchone()[0])
        item_count = int(con.execute("SELECT count(*) FROM analysis_dashboard.evidence_items").fetchone()[0])
    return module_count, item_count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--modules", type=Path, default=MODULES_CSV)
    parser.add_argument("--items", type=Path, default=ITEMS_CSV)
    args = parser.parse_args()
    module_count, item_count = build_views(args.database, args.modules, args.items)
    print(f"built duckdb analysis_dashboard.modules={module_count} evidence_items={item_count}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add DuckDB README note**

Append to `database/duckdb/README.md`:

```markdown
## Dashboard Evidence Mirror

Run `uv run --script database/duckdb/build_dashboard_evidence_views.py` to mirror `dashboard/data/evidence_catalog_modules.csv` and `dashboard/data/evidence_catalog_items.csv` into `analysis_dashboard.*` DuckDB tables.
These tables are query aids for artifact coverage, missing source paths, and joins with large output CSVs.
```

- [ ] **Step 3: Run DuckDB mirror**

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run --script database/duckdb/build_dashboard_evidence_views.py
```

Expected: prints `built duckdb analysis_dashboard.modules=3 evidence_items=10`.

- [ ] **Step 4: Commit Task 6**

```bash
git add database/duckdb/build_dashboard_evidence_views.py database/duckdb/README.md
git commit -m "feat: mirror dashboard evidence catalog in duckdb"
```

## Task 7: Dashboard README and Final Smoke Verification

**Files:**
- Modify: `dashboard/README.md`
- Modify: `scripts/README.md`

- [ ] **Step 1: Document evidence workflow in dashboard README**

Add this section to `dashboard/README.md`:

````markdown
## Evidence Portal Workflow

Dashboard evidence uses three layers:

- `dashboard/lib/analysis-copy.ts`: canonical UI explanation copy.
- `dashboard/data/evidence_curation.csv`: human-curated artifact classification.
- `dashboard/lib/evidence-catalog.ts`: generated runtime snapshot.

Regenerate candidate and runtime catalog:

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run scripts/dashboard/scan_evidence_candidates.py
uv run scripts/dashboard/build_evidence_catalog.py
```

Mirror to databases:

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run database/postgres/import_dashboard_evidence.py --database camels
uv run --script database/duckdb/build_dashboard_evidence_views.py
```

Do not update PostgreSQL or DuckDB rows directly. Update `analysis-copy.ts`, `evidence_curation.csv`, or source artifacts, then regenerate.
````

- [ ] **Step 2: Document script location in scripts README**

Append this bullet immediately after the existing `scripts/model/overall/` bullet in `scripts/README.md`:

```markdown
- `scripts/dashboard/scan_evidence_candidates.py`, `scripts/dashboard/build_evidence_catalog.py`: dashboard evidence portal candidate scan and typed catalog generation.
```

- [ ] **Step 3: Run full verification**

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run python -m unittest tests.test_dashboard_evidence_catalog -v
uv run scripts/dashboard/scan_evidence_candidates.py
uv run scripts/dashboard/build_evidence_catalog.py
uv run --script database/duckdb/build_dashboard_evidence_views.py
cd dashboard
npm run typecheck
```

Expected:

- unittest exits `0`
- scanner writes candidate CSV
- catalog builder writes TS catalog with `items=10 modules=3`
- DuckDB script prints `modules=3 evidence_items=10`
- typecheck exits `0`

- [ ] **Step 4: Verify routes on existing 3000 dev server**

Run from repo root:

```bash
export PATH="/opt/homebrew/bin:$PATH"
for p in overview foundation/dataset analysis/main-result; do
  code=$(curl -s -o /tmp/camels_evidence_final_${p//\//_}.html -w '%{http_code}' "http://localhost:3000/$p")
  printf '%s %s\n' "$p" "$code"
done
```

Expected:

```text
overview 200
foundation/dataset 200
analysis/main-result 200
```

- [ ] **Step 5: Commit Task 7**

```bash
git add dashboard/README.md scripts/README.md
git commit -m "docs: document dashboard evidence catalog workflow"
```

## Final Review Checklist

- [ ] Run `git status --short --branch` and verify only unrelated pre-existing dirty files remain.
- [ ] Run `rg -n 'TBD|PLACEHOLDER|TO''DO' dashboard/lib dashboard/components scripts/dashboard database/postgres/import_dashboard_evidence.py database/duckdb/build_dashboard_evidence_views.py tests/test_dashboard_evidence_catalog.py`.
- [ ] Confirm `dashboard/lib/evidence-catalog.ts` is generated and committed.
- [ ] Confirm `dashboard/data/evidence_curation.csv` is committed and editable in spreadsheet tools.
- [ ] Confirm `database/local/duckdb/camels.duckdb` is not staged.
- [ ] Confirm final response lists commands run and any skipped PostgreSQL live import if local DB is unavailable.
