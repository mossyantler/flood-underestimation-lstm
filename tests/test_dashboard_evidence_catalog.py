from __future__ import annotations

import csv
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from scripts.dashboard import evidence_common as common
from scripts.dashboard import scan_evidence_candidates as scanner


CURATION_FIELDNAMES = [
    "id", "title", "section", "module", "kind", "role", "priority",
    "show_in_dashboard", "source_path", "generator_path", "doc_path",
    "chart_path", "table_path", "gallery_path", "analysis_purpose",
    "short_description", "tags", "status", "notes",
]


def write_curation(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CURATION_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def curation_row(**overrides: str) -> dict[str, str]:
    row = {
        "id": "primary-high-flow-md",
        "title": "Primary high-flow peak performance",
        "section": "analysis",
        "module": "main-result",
        "kind": "doc",
        "role": "canonical",
        "priority": "1",
        "show_in_dashboard": "true",
        "source_path": "docs/example.md",
        "generator_path": "",
        "doc_path": "",
        "chart_path": "",
        "table_path": "",
        "gallery_path": "",
        "analysis_purpose": "Purpose",
        "short_description": "Description",
        "tags": "analysis;main-result",
        "status": "ready",
        "notes": "",
    }
    row.update(overrides)
    return row


def analysis_copy_text(*modules: str) -> str:
    if not modules:
        modules = ("main-result",)
    rows = []
    for module in modules:
        rows.append(
            '{"moduleId":"analysis/%s","section":"analysis","module":"%s",'
            '"title":"Module","analysisPurpose":"purpose","background":"bg",'
            '"coreData":"data","interpretationMethod":"method",'
            '"currentJudgment":"judgment","status":"ready"}' % (module, module)
        )
    return "export const analysisModuleCopy = [%s] as const;" % ",".join(rows)


class DashboardEvidenceCatalogTests(unittest.TestCase):
    def test_classify_main_result_doc(self) -> None:
        candidate = common.classify_path(
            Path("docs/experiment/analysis/model/02_primary_high_flow_peak_performance.md")
        )
        self.assertEqual(candidate.section, "analysis")
        self.assertEqual(candidate.module, "main-result")
        self.assertEqual(candidate.kind, "doc")
        self.assertEqual(candidate.role_hint, "canonical")

    def test_scanner_excludes_raw_timeseries_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "output/model_analysis/primary/metrics/data/raw_timeseries/model1_seed111_epoch025.csv"
            raw.parent.mkdir(parents=True)
            raw.write_text("a,b\n1,2\n", encoding="utf-8")
            candidates = scanner.scan_paths(root)
            self.assertEqual(candidates, [])

    def test_scanner_keeps_summary_chart_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = root / "docs/experiment/analysis/model/02_primary_high_flow_peak_performance.md"
            fig = root / "output/model_analysis/primary/calibration/figures/all_quantile_calibration.png"
            summary = root / "output/model_analysis/primary/metrics/report/analysis_summary.json"
            for path in [doc, fig, summary]:
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.suffix == ".md":
                    path.write_text("# Title\n", encoding="utf-8")
                else:
                    path.write_bytes(b"demo")
            candidates = scanner.scan_paths(root)
            rels = {row.source_path for row in candidates}
            self.assertIn("docs/experiment/analysis/model/02_primary_high_flow_peak_performance.md", rels)
            self.assertIn(
                "output/model_analysis/primary/calibration/figures/all_quantile_calibration.png",
                rels,
            )
            self.assertIn("output/model_analysis/primary/metrics/report/analysis_summary.json", rels)

    def test_scanner_script_runs_as_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = root / "docs/experiment/analysis/model/02_primary_high_flow_peak_performance.md"
            output = root / "dashboard/data/evidence_candidates.csv"
            doc.parent.mkdir(parents=True, exist_ok=True)
            doc.write_text("# Title\n", encoding="utf-8")
            script = Path("scripts/dashboard/scan_evidence_candidates.py").resolve()

            result = subprocess.run(
                [sys.executable, str(script), "--repo-root", str(root), "--output", str(output)],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("rows=1", result.stdout)
            self.assertTrue(output.exists())

    def test_scanner_preserves_markdown_h1_when_cwd_differs_from_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as cwd_tmp:
            root = Path(tmp)
            doc = root / "docs/experiment/analysis/model/fixture.md"
            doc.parent.mkdir(parents=True, exist_ok=True)
            doc.write_text("# Fixture Title\n\nBody\n", encoding="utf-8")
            original_cwd = Path.cwd()

            try:
                os.chdir(cwd_tmp)
                candidates = scanner.scan_paths(root)
            finally:
                os.chdir(original_cwd)

            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0].title, "Fixture Title")
            self.assertEqual(candidates[0].source_path, "docs/experiment/analysis/model/fixture.md")

    def test_scanner_script_accepts_output_outside_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as out_tmp:
            root = Path(tmp)
            doc = root / "docs/experiment/analysis/model/fixture.md"
            output = Path(out_tmp) / "evidence_candidates.csv"
            doc.parent.mkdir(parents=True, exist_ok=True)
            doc.write_text("# Fixture Title\n", encoding="utf-8")
            script = Path("scripts/dashboard/scan_evidence_candidates.py").resolve()

            result = subprocess.run(
                [sys.executable, str(script), "--repo-root", str(root), "--output", str(output)],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(str(output), result.stdout)
            self.assertIn("rows=1", result.stdout)
            self.assertTrue(output.exists())
            self.assertNotIn(b"\r\n", output.read_bytes())

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

    def test_extract_analysis_copy_rejects_mismatched_module_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ts = root / "dashboard/lib/analysis-copy.ts"
            ts.parent.mkdir(parents=True)
            ts.write_text(
                'export const analysisModuleCopy = [{"moduleId":"analysis/wrong","section":"analysis","module":"main-result","title":"Main","analysisPurpose":"purpose","background":"bg","coreData":"data","interpretationMethod":"method","currentJudgment":"judgment","status":"ready"}] as const;',
                encoding="utf-8",
            )
            from scripts.dashboard import build_evidence_catalog as builder

            with self.assertRaisesRegex(ValueError, "moduleId"):
                builder.extract_analysis_copy(ts)

    def test_extract_analysis_copy_rejects_duplicate_module_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ts = root / "dashboard/lib/analysis-copy.ts"
            ts.parent.mkdir(parents=True)
            module = '{"moduleId":"analysis/main-result","section":"analysis","module":"main-result","title":"Main","analysisPurpose":"purpose","background":"bg","coreData":"data","interpretationMethod":"method","currentJudgment":"judgment","status":"ready"}'
            ts.write_text(
                f"export const analysisModuleCopy = [{module},{module}] as const;",
                encoding="utf-8",
            )
            from scripts.dashboard import build_evidence_catalog as builder

            with self.assertRaisesRegex(ValueError, "duplicate moduleId"):
                builder.extract_analysis_copy(ts)

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

    def test_build_catalog_rejects_duplicate_item_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "docs/example.md"
            source.parent.mkdir(parents=True)
            source.write_text("# Example\n", encoding="utf-8")
            curation = root / "dashboard/data/evidence_curation.csv"
            curation.parent.mkdir(parents=True)
            fieldnames = [
                "id", "title", "section", "module", "kind", "role", "priority",
                "show_in_dashboard", "source_path", "generator_path", "doc_path",
                "chart_path", "table_path", "gallery_path", "analysis_purpose",
                "short_description", "tags", "status", "notes",
            ]
            row = {
                "id": "duplicate", "title": "Example", "section": "analysis",
                "module": "main-result", "kind": "doc", "role": "canonical",
                "priority": "1", "show_in_dashboard": "true",
                "source_path": "docs/example.md", "generator_path": "",
                "doc_path": "", "chart_path": "", "table_path": "", "gallery_path": "",
                "analysis_purpose": "", "short_description": "", "tags": "analysis",
                "status": "ready", "notes": "",
            }
            with curation.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow(row)
                writer.writerow(row)
            from scripts.dashboard import build_evidence_catalog as builder

            with self.assertRaisesRegex(ValueError, "duplicate evidence id"):
                builder.read_curation(root, curation)

    def test_build_catalog_rejects_orphan_item_module(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "docs/example.md"
            source.parent.mkdir(parents=True)
            source.write_text("# Example\n", encoding="utf-8")
            curation = root / "dashboard/data/evidence_curation.csv"
            write_curation(curation, [curation_row(module="calibration")])
            analysis_copy = root / "dashboard/lib/analysis-copy.ts"
            analysis_copy.parent.mkdir(parents=True)
            analysis_copy.write_text(analysis_copy_text("main-result"), encoding="utf-8")
            script = Path("scripts/dashboard/build_evidence_catalog.py").resolve()

            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--repo-root",
                    str(root),
                    "--curation",
                    str(curation),
                    "--analysis-copy",
                    str(analysis_copy),
                    "--output-ts",
                    str(root / "dashboard/lib/evidence-catalog.ts"),
                    "--modules-output",
                    str(root / "dashboard/data/evidence_catalog_modules.csv"),
                    "--items-output",
                    str(root / "dashboard/data/evidence_catalog_items.csv"),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("orphan evidence moduleId", result.stderr)

    def test_build_catalog_rejects_path_outside_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            outside = Path(tmp) / "outside.md"
            outside.write_text("# Outside\n", encoding="utf-8")
            curation = root / "dashboard/data/evidence_curation.csv"
            write_curation(curation, [curation_row(source_path="../outside.md")])
            from scripts.dashboard import build_evidence_catalog as builder

            with self.assertRaisesRegex(ValueError, "escapes repo root"):
                builder.read_curation(root, curation)

    def test_build_catalog_rejects_missing_optional_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "docs/example.md"
            source.parent.mkdir(parents=True)
            source.write_text("# Example\n", encoding="utf-8")
            curation = root / "dashboard/data/evidence_curation.csv"
            write_curation(curation, [curation_row(doc_path="docs/missing.md")])
            from scripts.dashboard import build_evidence_catalog as builder

            with self.assertRaisesRegex(FileNotFoundError, "doc_path"):
                builder.read_curation(root, curation)

    def test_build_catalog_repeated_run_leaves_outputs_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "docs/example.md"
            source.parent.mkdir(parents=True)
            source.write_text("# Example\n", encoding="utf-8")
            curation = root / "dashboard/data/evidence_curation.csv"
            write_curation(curation, [curation_row()])
            analysis_copy = root / "dashboard/lib/analysis-copy.ts"
            analysis_copy.parent.mkdir(parents=True)
            analysis_copy.write_text(analysis_copy_text("main-result"), encoding="utf-8")
            output_ts = root / "dashboard/lib/evidence-catalog.ts"
            modules_output = root / "dashboard/data/evidence_catalog_modules.csv"
            items_output = root / "dashboard/data/evidence_catalog_items.csv"
            script = Path("scripts/dashboard/build_evidence_catalog.py").resolve()
            command = [
                sys.executable,
                str(script),
                "--repo-root",
                str(root),
                "--curation",
                str(curation),
                "--analysis-copy",
                str(analysis_copy),
                "--output-ts",
                str(output_ts),
                "--modules-output",
                str(modules_output),
                "--items-output",
                str(items_output),
            ]

            first = subprocess.run(command, check=False, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            first_bytes = {
                path: path.read_bytes()
                for path in [output_ts, modules_output, items_output]
            }
            time.sleep(1.1)
            second = subprocess.run(command, check=False, capture_output=True, text=True)
            self.assertEqual(second.returncode, 0, second.stderr)

            self.assertEqual(first_bytes, {
                path: path.read_bytes()
                for path in [output_ts, modules_output, items_output]
            })
