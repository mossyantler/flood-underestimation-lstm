#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def _epoch_from_name(name: str) -> int | None:
    if "epoch" not in name:
        return None
    try:
        return int(name.split("epoch")[-1].split(".")[0])
    except ValueError:
        return None


def _sorted_resume_dirs(root: Path) -> list[Path]:
    nested = [p for p in root.rglob("continue_training_from_epoch*") if p.is_dir()]
    return sorted(nested, key=lambda p: (len(p.relative_to(root).parts), str(p)))


def _top_level_resume_roots(run_dir: Path) -> list[Path]:
    return sorted(
        [p for p in run_dir.iterdir() if p.is_dir() and p.name.startswith("continue_training_from_epoch")],
        key=lambda p: p.name,
    )


def _ensure_archive_dest(archive_root: Path, name: str) -> Path:
    candidate = archive_root / name
    if not candidate.exists():
        return candidate

    index = 2
    while True:
        candidate = archive_root / f"{name}_{index:02d}"
        if not candidate.exists():
            return candidate
        index += 1


def _safe_move_file(src: Path, dst: Path) -> bool:
    if dst.exists():
        if dst.stat().st_size != src.stat().st_size:
            raise RuntimeError(f"Refusing to overwrite different file: {dst}")
        src.unlink()
        return False

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return True


def _safe_move_tree(src: Path, dst: Path) -> bool:
    if dst.exists():
        return False

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return True


def _write_combined_log(run_dir: Path, log_paths: Iterable[Path]) -> None:
    combined_path = run_dir / "output_combined.log"
    combined_path.parent.mkdir(parents=True, exist_ok=True)

    chunks: list[str] = []
    for log_path in log_paths:
        if not log_path.exists():
            continue
        rel = log_path.relative_to(run_dir)
        chunks.append(f"===== {rel} =====\n")
        chunks.append(log_path.read_text(encoding="utf-8", errors="replace"))
        if not chunks[-1].endswith("\n"):
            chunks.append("\n")
        chunks.append("\n")

    if chunks:
        combined_path.write_text("".join(chunks), encoding="utf-8")


def flatten_resume_chain(run_dir: Path, quiet: bool = False) -> int:
    run_dir = run_dir.resolve()
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    resume_roots = _top_level_resume_roots(run_dir)
    if not resume_roots:
        if not quiet:
            print(f"[flatten] no nested resume folders under {run_dir}")
        return 0

    validation_root = run_dir / "validation"
    validation_root.mkdir(parents=True, exist_ok=True)
    archive_root = run_dir / "_resume_archive"
    archive_root.mkdir(parents=True, exist_ok=True)

    log_paths: list[Path] = []
    if (run_dir / "output.log").exists():
        log_paths.append(run_dir / "output.log")

    summary_lines = [
        f"run_dir: {run_dir}",
        f"generated_at_utc: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]

    moved_anything = False

    for resume_root in resume_roots:
        moved_epochs: set[int] = set()

        for nested_dir in _sorted_resume_dirs(resume_root):
            output_log = nested_dir / "output.log"
            if output_log.exists():
                log_paths.append(output_log)

            for checkpoint in sorted(nested_dir.glob("model_epoch*.pt")):
                epoch = _epoch_from_name(checkpoint.name)
                if _safe_move_file(checkpoint, run_dir / checkpoint.name):
                    moved_anything = True
                if epoch is not None:
                    moved_epochs.add(epoch)

            for optimizer_state in sorted(nested_dir.glob("optimizer_state_epoch*.pt")):
                epoch = _epoch_from_name(optimizer_state.name)
                if _safe_move_file(optimizer_state, run_dir / optimizer_state.name):
                    moved_anything = True
                if epoch is not None:
                    moved_epochs.add(epoch)

            nested_validation = nested_dir / "validation"
            if nested_validation.exists():
                for epoch_dir in sorted(nested_validation.glob("model_epoch*")):
                    epoch = _epoch_from_name(epoch_dir.name)
                    if _safe_move_tree(epoch_dir, validation_root / epoch_dir.name):
                        moved_anything = True
                    if epoch is not None:
                        moved_epochs.add(epoch)

        archive_dest = _ensure_archive_dest(archive_root, resume_root.name)
        shutil.move(str(resume_root), str(archive_dest))

        if moved_epochs:
            summary_lines.append(
                f"{resume_root.name}: moved epochs {min(moved_epochs)}-{max(moved_epochs)} "
                f"and archived to {archive_dest.relative_to(run_dir)}"
            )
        else:
            summary_lines.append(
                f"{resume_root.name}: no checkpoint/validation artifacts moved, archived to "
                f"{archive_dest.relative_to(run_dir)}"
            )

    _write_combined_log(run_dir, log_paths)

    summary_path = run_dir / "resume_chain_summary.txt"
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    if not quiet:
        if moved_anything:
            print(f"[flatten] flattened nested resume chain under {run_dir}")
        else:
            print(f"[flatten] archived nested resume folders under {run_dir} (no movable artifacts)")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Flatten nested NeuralHydrology continue_training folders.")
    parser.add_argument("--run-dir", required=True, help="Top-level NH run directory")
    parser.add_argument("--quiet", action="store_true", help="Suppress informational output")
    args = parser.parse_args()
    return flatten_resume_chain(Path(args.run_dir), quiet=args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
