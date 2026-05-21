from __future__ import annotations

import tempfile
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.dashboard import evidence_common as common
from scripts.dashboard import scan_evidence_candidates as scanner


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
                if path.suffix == ".md":
                    path.write_text("# Title\n", encoding="utf-8")
                else:
                    path.write_bytes(b"demo")
            candidates = scanner.scan_paths(root)
            rels = {row.source_path for row in candidates}
            self.assertIn("docs/experiment/analysis/model/02_primary_high_flow_peak_performance.md", rels)
            self.assertIn(
                "output/model_analysis/probabilistic_diagnostics/figures/primary_all_quantile_calibration.png",
                rels,
            )
            self.assertIn("output/model_analysis/expanded_drbc_test/analysis_summary.json", rels)

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
