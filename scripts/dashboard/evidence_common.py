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

    kind = kind_for(relative_path)
    return Candidate(
        id=stable_id(text),
        title=title_from_path(relative_path),
        section=section,
        module=module,
        kind=kind,
        role_hint=role,
        priority_hint=priority,
        source_path=text,
        tags=";".join(part for part in [section, module, kind] if part),
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
