#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pandas>=2.2",
# ]
# ///

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_ML_DIR = Path("output/basin/all/analysis/event_regime/tables")
DEFAULT_REFERENCE = Path("output/basin/all/reference_comparison/usgs_flood/tables/return_period_reference_table_with_usgs.csv")
DEFAULT_SUMMARY_DIR = Path("output/basin/all/analysis/event_regime/metadata")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Attach CAMELSH proxy flood_ari and USGS StreamStats peak-flow reference "
            "columns to ML experiment CSVs that contain gauge_id."
        )
    )
    parser.add_argument("--ml-dir", type=Path, default=DEFAULT_ML_DIR, help="ML experiment output directory.")
    parser.add_argument("--summary-dir", type=Path, default=DEFAULT_SUMMARY_DIR, help="Directory for run metadata.")
    parser.add_argument(
        "--reference-csv",
        type=Path,
        default=DEFAULT_REFERENCE,
        help="Return-period reference table already enriched with USGS StreamStats columns.",
    )
    parser.add_argument(
        "--suffix",
        default="_with_usgs",
        help="Suffix inserted before .csv for enriched outputs.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite source CSVs instead of writing suffixed copies.",
    )
    parser.add_argument(
        "--include-existing-with-usgs",
        action="store_true",
        help="Also process CSVs whose stem already ends with the suffix.",
    )
    return parser.parse_args()


def normalize_gauge_id(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    if text.isdigit() and len(text) < 8:
        text = text.zfill(8)
    return text


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def reference_columns(columns: list[str]) -> list[str]:
    selected = ["gauge_id"]
    for col in columns:
        if col == "gauge_id":
            continue
        if re.fullmatch(r"flood_ari\d+", col):
            selected.append(col)
        elif col == "flood_ari_source":
            selected.append(col)
        elif col.startswith("usgs_flood_ari"):
            selected.append(col)
        elif col.startswith("usgs_to_camelsh_flood_ari"):
            selected.append(col)
        elif col.startswith("camelsh_minus_usgs_flood_ari"):
            selected.append(col)
        elif col in {
            "usgs_station_code",
            "usgs_station_name",
            "usgs_station_region",
            "usgs_station_is_regulated",
            "usgs_peak_flow_fetch_status",
            "usgs_peak_flow_available_count",
            "usgs_peak_flow_selected_count",
            "usgs_peak_flow_missing_periods",
        }:
            selected.append(col)
    return selected


def read_csv_with_gauge(path: Path) -> pd.DataFrame:
    header = pd.read_csv(path, nrows=0)
    dtype = {"gauge_id": str} if "gauge_id" in header.columns else None
    return pd.read_csv(path, dtype=dtype)


def output_path_for(path: Path, suffix: str, overwrite: bool) -> Path:
    if overwrite:
        return path
    return path.with_name(f"{path.stem}{suffix}{path.suffix}")


def main() -> None:
    args = parse_args()
    args.summary_dir.mkdir(parents=True, exist_ok=True)
    if not args.ml_dir.exists():
        raise SystemExit(f"ML experiment directory does not exist: {args.ml_dir}")
    if not args.reference_csv.exists():
        raise SystemExit(f"Reference CSV does not exist: {args.reference_csv}")

    reference = pd.read_csv(args.reference_csv, dtype={"gauge_id": str})
    reference["gauge_id"] = reference["gauge_id"].map(normalize_gauge_id)
    keep_cols = reference_columns(reference.columns.tolist())
    reference = reference[keep_cols].drop_duplicates("gauge_id")

    processed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for path in sorted(args.ml_dir.rglob("*.csv")):
        if not args.include_existing_with_usgs and path.stem.endswith(args.suffix):
            skipped.append({"path": str(path), "reason": "already_suffixed"})
            continue

        header = pd.read_csv(path, nrows=0)
        if "gauge_id" not in header.columns:
            skipped.append({"path": str(path), "reason": "no_gauge_id"})
            continue

        frame = read_csv_with_gauge(path)
        frame["gauge_id"] = frame["gauge_id"].map(normalize_gauge_id)
        original_cols = frame.columns.tolist()
        drop_cols = [col for col in reference.columns if col != "gauge_id" and col in frame.columns]
        if drop_cols:
            frame = frame.drop(columns=drop_cols)

        enriched = frame.merge(reference, on="gauge_id", how="left")
        out_path = output_path_for(path, args.suffix, args.overwrite)
        enriched.to_csv(out_path, index=False)

        matched = int(enriched["usgs_peak_flow_fetch_status"].notna().sum())
        usgs_100_count = int(pd.to_numeric(enriched.get("usgs_flood_ari100"), errors="coerce").notna().sum())
        processed.append(
            {
                "input": str(path),
                "output": str(out_path),
                "row_count": int(len(enriched)),
                "original_column_count": len(original_cols),
                "output_column_count": int(len(enriched.columns)),
                "matched_reference_rows": matched,
                "usgs_flood_ari100_nonnull_rows": usgs_100_count,
            }
        )
        print(f"Wrote {out_path} ({len(enriched)} rows, {len(enriched.columns)} columns)", flush=True)

    summary = {
        "ml_dir": str(args.ml_dir),
        "reference_csv": str(args.reference_csv),
        "reference_columns": keep_cols,
        "processed_count": len(processed),
        "skipped_count": len(skipped),
        "processed": processed,
        "skipped": skipped,
    }
    summary_path = args.summary_dir / "usgs_peak_flow_ml_csv_application_summary.json"
    summary_path.write_text(json.dumps(json_safe(summary), indent=2), encoding="utf-8")
    print(f"Wrote summary: {summary_path}", flush=True)


if __name__ == "__main__":
    main()
