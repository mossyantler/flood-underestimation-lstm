#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=1.26",
#   "pandas>=2.2",
# ]
# ///

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_OUTPUT_DIR = Path("output/basin/all")
DEFAULT_INPUT_CSV = (
    DEFAULT_OUTPUT_DIR
    / "reference_comparison/noaa_prec/tables/return_period_reference_table_with_usgs_noaa14_gridmean.csv"
)

NOAA_SERIES = ("ams", "pds")
RETURN_PERIODS = (2, 5, 10, 25, 50, 100)
DURATIONS = (1, 6, 24, 72)
ATLAS2_PERIODS = (2, 100)
ATLAS2_DURATIONS = (6, 24)
SQKM_TO_SQMI = 0.3861021585424458

NOAA_ATLAS14_ARF_GUIDANCE_URL = "https://www.weather.gov/owp/hdsc_faqs"
HEC_HMS_TP40_49_URL = (
    "https://www.hec.usace.army.mil/confluence/hmsdocs/hmstrm/meteorology/precipitation/frequency-storm"
)
HEC_HMS_3DAY_URL = (
    "https://www.hec.usace.army.mil/confluence/hmsdocs/hmstrm/meteorology/precipitation/"
    "frequency-storm/frequency-storm-3-day-depth-compute"
)

# Approximate digitization of the HEC-HMS TP-40 reduction curve figure for 1/6/24h.
# The 72h curve is approximated from the HEC-HMS 3-day reduction example and is
# intentionally marked as an approximate reference, not an official NOAA product.
ARF_CURVES: dict[int, tuple[tuple[float, float], ...]] = {
    1: (
        (0.0, 1.000),
        (10.0, 0.925),
        (25.0, 0.865),
        (50.0, 0.795),
        (75.0, 0.750),
        (100.0, 0.720),
        (150.0, 0.680),
        (200.0, 0.665),
        (250.0, 0.657),
        (300.0, 0.652),
        (350.0, 0.650),
        (400.0, 0.650),
    ),
    6: (
        (0.0, 1.000),
        (10.0, 0.970),
        (25.0, 0.940),
        (50.0, 0.910),
        (75.0, 0.890),
        (100.0, 0.875),
        (150.0, 0.852),
        (200.0, 0.840),
        (250.0, 0.835),
        (300.0, 0.832),
        (350.0, 0.832),
        (400.0, 0.832),
    ),
    24: (
        (0.0, 1.000),
        (10.0, 0.988),
        (25.0, 0.972),
        (50.0, 0.955),
        (75.0, 0.945),
        (100.0, 0.937),
        (150.0, 0.925),
        (200.0, 0.917),
        (250.0, 0.913),
        (300.0, 0.911),
        (350.0, 0.911),
        (400.0, 0.911),
    ),
    72: (
        (0.0, 1.000),
        (10.0, 0.992),
        (25.0, 0.981),
        (50.0, 0.970),
        (75.0, 0.962),
        (100.0, 0.953),
        (150.0, 0.946),
        (200.0, 0.943),
        (250.0, 0.941),
        (300.0, 0.940),
        (350.0, 0.940),
        (400.0, 0.940),
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply areal reduction factors to NOAA grid-mean precipitation-frequency references. "
            "The output keeps CAMELSH prec_ari* and noaa14_gridmean_* intact and appends "
            "noaa14_areal_arf_* / noaa2_areal_arf_* columns as supplementary references."
        )
    )
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_INPUT_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-csv", type=Path, default=None)
    parser.add_argument(
        "--small-area-threshold-sqmi",
        type=float,
        default=30.0,
        help="Basins at or below this area are left unreduced, following common HEC-HMS small-area guidance.",
    )
    parser.add_argument(
        "--large-area-policy",
        choices=["cap", "extrapolate"],
        default="cap",
        help=(
            "How to handle basins above 400 square miles, where TP-40/49 curves should be used cautiously. "
            "`cap` uses the 400 sq mi ARF and marks status as capped; `extrapolate` linearly extends the "
            "last curve segment and marks status as extrapolated."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional first-N row limit for smoke testing.",
    )
    parser.add_argument("--gauge-id", action="append", default=[], help="Optional gauge ID filter. Can repeat.")
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
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def default_output_csv(input_csv: Path) -> Path:
    if input_csv.stem.endswith("_areal_arf"):
        return input_csv
    return input_csv.with_name(f"{input_csv.stem}_areal_arf{input_csv.suffix}")


def drop_existing_areal_arf_columns(frame: pd.DataFrame) -> pd.DataFrame:
    drop_cols = [
        col
        for col in frame.columns
        if col.startswith("noaa14_areal_arf_")
        or col.startswith("noaa2_areal_arf_")
        or col.startswith("camelsh_minus_noaa14_areal_arf_")
        or col.startswith("camelsh_minus_noaa2_areal_arf_")
        or "_noaa14_areal_arf_" in col
        or "_noaa2_areal_arf_" in col
    ]
    return frame.drop(columns=drop_cols, errors="ignore")


def basin_area_sqkm(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    area = pd.Series(np.nan, index=frame.index, dtype=float)
    source = pd.Series(pd.NA, index=frame.index, dtype=object)
    for column, label in (("drain_sqkm_attr", "drain_sqkm_attr"), ("area", "area")):
        if column not in frame.columns:
            continue
        candidate = pd.to_numeric(frame[column], errors="coerce")
        use = area.isna() & candidate.notna() & (candidate > 0)
        area.loc[use] = candidate.loc[use]
        source.loc[use] = label
    return area, source


def interpolate_arf(
    area_sqmi: pd.Series,
    duration: int,
    *,
    small_area_threshold_sqmi: float,
    large_area_policy: str,
) -> tuple[pd.Series, pd.Series]:
    points = np.asarray(ARF_CURVES[duration], dtype=float)
    xs = points[:, 0]
    ys = points[:, 1]
    values = pd.Series(np.nan, index=area_sqmi.index, dtype=float)
    status = pd.Series("missing_area", index=area_sqmi.index, dtype=object)

    valid = area_sqmi.notna() & np.isfinite(area_sqmi) & (area_sqmi > 0)
    small = valid & (area_sqmi <= small_area_threshold_sqmi)
    normal = valid & (area_sqmi > small_area_threshold_sqmi) & (area_sqmi <= xs[-1])
    large = valid & (area_sqmi > xs[-1])

    values.loc[small] = 1.0
    status.loc[small] = "small_area_unreduced"

    if bool(normal.any()):
        values.loc[normal] = np.interp(area_sqmi.loc[normal].to_numpy(dtype=float), xs, ys)
        status.loc[normal] = "ok"

    if bool(large.any()):
        if large_area_policy == "cap":
            values.loc[large] = ys[-1]
            status.loc[large] = "area_gt_400sqmi_capped"
        else:
            slope = (ys[-1] - ys[-2]) / (xs[-1] - xs[-2])
            extrapolated = ys[-1] + slope * (area_sqmi.loc[large].to_numpy(dtype=float) - xs[-1])
            values.loc[large] = np.clip(extrapolated, 0.0, 1.0)
            status.loc[large] = "area_gt_400sqmi_extrapolated"
    return values, status


def add_arf_metadata(frame: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    output = frame.copy()
    area_sqkm, area_source = basin_area_sqkm(output)
    output["noaa_areal_arf_area_sqkm"] = area_sqkm
    output["noaa_areal_arf_area_sqmi"] = area_sqkm * SQKM_TO_SQMI
    output["noaa_areal_arf_area_source"] = area_source
    output["noaa_areal_arf_method"] = "HEC-HMS_TP40_49_approximate_depth_area_reduction"
    output["noaa_areal_arf_source"] = (
        "NOAA/USACE guidance: Atlas 14 point PFE should be converted to areal estimates with ARF; "
        "curves approximated from HEC-HMS TP-40/TP-49 documentation."
    )
    output["noaa_areal_arf_guidance_url"] = NOAA_ATLAS14_ARF_GUIDANCE_URL
    output["noaa_areal_arf_curve_url"] = HEC_HMS_TP40_49_URL
    output["noaa_areal_arf_3day_curve_url"] = HEC_HMS_3DAY_URL
    output["noaa_areal_arf_note"] = (
        "Supplementary areal-adjusted NOAA-derived reference only; not an official NOAA Atlas 14 product "
        "and not a replacement for CAMELSH forcing-space prec_ari* thresholds."
    )
    output["noaa_areal_arf_small_area_threshold_sqmi"] = float(args.small_area_threshold_sqmi)
    output["noaa_areal_arf_large_area_policy"] = args.large_area_policy

    for duration in DURATIONS:
        factor, status = interpolate_arf(
            output["noaa_areal_arf_area_sqmi"],
            duration,
            small_area_threshold_sqmi=args.small_area_threshold_sqmi,
            large_area_policy=args.large_area_policy,
        )
        output[f"noaa_areal_arf_factor_{duration}h"] = factor
        output[f"noaa_areal_arf_status_{duration}h"] = status
    return output


def add_adjusted_noaa_columns(frame: pd.DataFrame) -> pd.DataFrame:
    adjusted: dict[str, pd.Series] = {}
    for series in NOAA_SERIES:
        for period in RETURN_PERIODS:
            for duration in DURATIONS:
                source_col = f"noaa14_gridmean_{series}_prec_ari{period}_{duration}h"
                factor_col = f"noaa_areal_arf_factor_{duration}h"
                if source_col not in frame.columns or factor_col not in frame.columns:
                    continue
                source = pd.to_numeric(frame[source_col], errors="coerce")
                factor = pd.to_numeric(frame[factor_col], errors="coerce")
                adjusted[f"noaa14_areal_arf_{series}_prec_ari{period}_{duration}h"] = source * factor

    for period in ATLAS2_PERIODS:
        for duration in ATLAS2_DURATIONS:
            source_col = f"noaa2_gridmean_prec_ari{period}_{duration}h"
            factor_col = f"noaa_areal_arf_factor_{duration}h"
            if source_col not in frame.columns or factor_col not in frame.columns:
                continue
            source = pd.to_numeric(frame[source_col], errors="coerce")
            factor = pd.to_numeric(frame[factor_col], errors="coerce")
            adjusted[f"noaa2_areal_arf_prec_ari{period}_{duration}h"] = source * factor

    if not adjusted:
        return frame
    return pd.concat([frame, pd.DataFrame(adjusted, index=frame.index)], axis=1)


def add_comparison_columns(frame: pd.DataFrame) -> pd.DataFrame:
    comparison: dict[str, pd.Series] = {}
    for series in NOAA_SERIES:
        for period in RETURN_PERIODS:
            for duration in DURATIONS:
                camelsh_col = f"prec_ari{period}_{duration}h"
                noaa_col = f"noaa14_areal_arf_{series}_prec_ari{period}_{duration}h"
                if camelsh_col not in frame.columns or noaa_col not in frame.columns:
                    continue
                camelsh = pd.to_numeric(frame[camelsh_col], errors="coerce")
                noaa = pd.to_numeric(frame[noaa_col], errors="coerce")
                comparison[f"noaa14_areal_arf_{series}_to_camelsh_prec_ari{period}_{duration}h"] = noaa / camelsh
                comparison[f"camelsh_minus_noaa14_areal_arf_{series}_prec_ari{period}_{duration}h"] = camelsh - noaa
                comparison[f"camelsh_minus_noaa14_areal_arf_{series}_prec_ari{period}_{duration}h_relative"] = (
                    camelsh - noaa
                ) / noaa

    for period in ATLAS2_PERIODS:
        for duration in ATLAS2_DURATIONS:
            camelsh_col = f"prec_ari{period}_{duration}h"
            noaa_col = f"noaa2_areal_arf_prec_ari{period}_{duration}h"
            if camelsh_col not in frame.columns or noaa_col not in frame.columns:
                continue
            camelsh = pd.to_numeric(frame[camelsh_col], errors="coerce")
            noaa = pd.to_numeric(frame[noaa_col], errors="coerce")
            comparison[f"noaa2_areal_arf_to_camelsh_prec_ari{period}_{duration}h"] = noaa / camelsh
            comparison[f"camelsh_minus_noaa2_areal_arf_prec_ari{period}_{duration}h"] = camelsh - noaa
            comparison[f"camelsh_minus_noaa2_areal_arf_prec_ari{period}_{duration}h_relative"] = (camelsh - noaa) / noaa

    if not comparison:
        return frame
    return pd.concat([frame, pd.DataFrame(comparison, index=frame.index)], axis=1)


def insert_areal_arf_columns_near_prec_proxy(frame: pd.DataFrame) -> pd.DataFrame:
    desired: list[str] = []
    used: set[str] = set()
    metadata_prefixes = (
        "noaa_areal_arf_",
    )
    for col in frame.columns:
        if col in used:
            continue
        desired.append(col)
        used.add(col)
        match = re.fullmatch(r"prec_ari(\d+)_(\d+)h", col)
        if not match:
            continue
        period = int(match.group(1))
        duration = int(match.group(2))
        for series in NOAA_SERIES:
            for extra in [
                f"noaa14_areal_arf_{series}_prec_ari{period}_{duration}h",
                f"noaa14_areal_arf_{series}_to_camelsh_prec_ari{period}_{duration}h",
                f"camelsh_minus_noaa14_areal_arf_{series}_prec_ari{period}_{duration}h",
                f"camelsh_minus_noaa14_areal_arf_{series}_prec_ari{period}_{duration}h_relative",
            ]:
                if extra in frame.columns and extra not in used:
                    desired.append(extra)
                    used.add(extra)
        if period in ATLAS2_PERIODS and duration in ATLAS2_DURATIONS:
            for extra in [
                f"noaa2_areal_arf_prec_ari{period}_{duration}h",
                f"noaa2_areal_arf_to_camelsh_prec_ari{period}_{duration}h",
                f"camelsh_minus_noaa2_areal_arf_prec_ari{period}_{duration}h",
                f"camelsh_minus_noaa2_areal_arf_prec_ari{period}_{duration}h_relative",
            ]:
                if extra in frame.columns and extra not in used:
                    desired.append(extra)
                    used.add(extra)

    # Keep ARF metadata together near the end unless it was already consumed.
    for prefix in metadata_prefixes:
        for col in frame.columns:
            if col.startswith(prefix) and col not in used:
                desired.append(col)
                used.add(col)
    desired.extend(col for col in frame.columns if col not in used)
    return frame.reindex(columns=desired)


def write_summary(frame: pd.DataFrame, args: argparse.Namespace, output_csv: Path) -> None:
    metadata_dir = args.output_dir / "reference_comparison" / "noaa_prec" / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    factor_cols = [f"noaa_areal_arf_factor_{duration}h" for duration in DURATIONS if f"noaa_areal_arf_factor_{duration}h" in frame.columns]
    status_cols = [f"noaa_areal_arf_status_{duration}h" for duration in DURATIONS if f"noaa_areal_arf_status_{duration}h" in frame.columns]
    noaa14_cols = [col for col in frame.columns if re.fullmatch(r"noaa14_areal_arf_(ams|pds)_prec_ari\d+_\d+h", col)]
    noaa2_cols = [col for col in frame.columns if re.fullmatch(r"noaa2_areal_arf_prec_ari\d+_\d+h", col)]
    comparison_cols = [
        col
        for col in frame.columns
        if re.fullmatch(r"camelsh_minus_noaa(14|2)_areal_arf_.*_relative", col)
    ]

    summary = {
        "input_csv": str(args.input_csv),
        "output_csv": str(output_csv),
        "station_count": int(len(frame)),
        "method": "HEC-HMS_TP40_49_approximate_depth_area_reduction",
        "small_area_threshold_sqmi": args.small_area_threshold_sqmi,
        "large_area_policy": args.large_area_policy,
        "source_guidance_urls": {
            "noaa_hdsc_faq": NOAA_ATLAS14_ARF_GUIDANCE_URL,
            "hec_hms_tp40_49": HEC_HMS_TP40_49_URL,
            "hec_hms_3day": HEC_HMS_3DAY_URL,
        },
        "factor_summary": {
            col: pd.to_numeric(frame[col], errors="coerce").describe().to_dict()
            for col in factor_cols
        },
        "status_counts": {
            col: frame[col].value_counts(dropna=False).to_dict()
            for col in status_cols
        },
        "noaa14_areal_arf_non_null_counts": {
            col: int(pd.to_numeric(frame[col], errors="coerce").notna().sum())
            for col in noaa14_cols
        },
        "noaa2_areal_arf_non_null_counts": {
            col: int(pd.to_numeric(frame[col], errors="coerce").notna().sum())
            for col in noaa2_cols
        },
        "relative_difference_summary": {
            col: pd.to_numeric(frame[col], errors="coerce").describe().to_dict()
            for col in comparison_cols
        },
    }
    summary_path = metadata_dir / "noaa_areal_arf_precip_reference_summary.json"
    summary_path.write_text(json.dumps(json_safe(summary), indent=2), encoding="utf-8")
    print(f"Wrote summary: {summary_path}", flush=True)
    compact_summary = {
        "station_count": summary["station_count"],
        "small_area_threshold_sqmi": summary["small_area_threshold_sqmi"],
        "large_area_policy": summary["large_area_policy"],
        "status_counts": summary["status_counts"],
    }
    print(json.dumps(json_safe(compact_summary), indent=2), flush=True)


def main() -> None:
    args = parse_args()
    if not args.input_csv.exists():
        raise SystemExit(f"Input CSV not found: {args.input_csv}")
    table_dir = args.output_dir / "reference_comparison" / "noaa_prec" / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)
    output_csv = args.output_csv or table_dir / default_output_csv(args.input_csv).name
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    frame = pd.read_csv(args.input_csv, dtype={"gauge_id": str, "huc02": str}, low_memory=False)
    frame["gauge_id"] = frame["gauge_id"].map(normalize_gauge_id)
    if args.gauge_id:
        requested = {normalize_gauge_id(item) for item in args.gauge_id}
        frame = frame[frame["gauge_id"].isin(requested)].copy()
    if args.limit is not None:
        frame = frame.head(args.limit).copy()
    if frame.empty:
        raise SystemExit("No rows matched the requested input/filter options.")

    frame = drop_existing_areal_arf_columns(frame)
    frame = add_arf_metadata(frame, args)
    frame = add_adjusted_noaa_columns(frame)
    frame = add_comparison_columns(frame)
    frame = insert_areal_arf_columns_near_prec_proxy(frame)

    frame.to_csv(output_csv, index=False)
    print(f"Wrote areal-ARF-adjusted table: {output_csv}", flush=True)
    write_summary(frame, args, output_csv)


if __name__ == "__main__":
    main()
