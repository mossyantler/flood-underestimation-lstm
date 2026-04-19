#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pandas>=2.2",
# ]
# ///

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd


DEFAULT_SUBSET_SIZES = [100, 300, 600]
STATIC_ATTRIBUTE_COLUMNS = [
    "area",
    "slope",
    "aridity",
    "snow_fraction",
    "soil_depth",
    "permeability",
    "forest_fraction",
    "baseflow_index",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build reproducible nationwide stratified train/validation subsets for the "
            "deterministic basin-count scaling pilot."
        )
    )
    parser.add_argument(
        "--prepared-split-manifest",
        type=Path,
        default=Path("data/CAMELSH_generic/drbc_holdout_broad/splits/split_manifest.csv"),
        help="Prepared broad split manifest used to keep pilot subsets executable.",
    )
    parser.add_argument(
        "--raw-train-basin-file",
        type=Path,
        default=Path("configs/basin_splits/drbc_holdout_train_broad.txt"),
        help="Official raw broad training split file.",
    )
    parser.add_argument(
        "--raw-validation-basin-file",
        type=Path,
        default=Path("configs/basin_splits/drbc_holdout_validation_broad.txt"),
        help="Official raw broad validation split file.",
    )
    parser.add_argument(
        "--prepared-test-basin-file",
        type=Path,
        default=Path("data/CAMELSH_generic/drbc_holdout_broad/splits/test.txt"),
        help="Prepared DRBC quality-pass test split file shared with the official broad setup.",
    )
    parser.add_argument(
        "--training-selected-csv",
        type=Path,
        default=Path("output/basin/camelsh_training_non_drbc/camelsh_non_drbc_training_selected.csv"),
        help=(
            "Optional quality-pass non-DRBC training pool table. If present, metadata from "
            "this file are reused, otherwise basin attributes are used as fallback."
        ),
    )
    parser.add_argument(
        "--basin-id-csv",
        type=Path,
        default=Path("basins/CAMELSH_data/attributes/attributes_gageii_BasinID.csv"),
        help="CAMELSH BasinID attributes table used to recover HUC02/state metadata.",
    )
    parser.add_argument(
        "--prepared-static-attributes-csv",
        type=Path,
        default=Path("data/CAMELSH_generic/drbc_holdout_broad/attributes/static_attributes.csv"),
        help="Prepared broad static-attributes table used to attach hydrologic attributes to pilot manifests.",
    )
    parser.add_argument(
        "--attributes-dir",
        type=Path,
        default=Path("basins/CAMELSH_data/attributes"),
        help="Raw CAMELSH attributes directory used as fallback when the prepared static-attributes CSV is missing.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("configs/pilot/basin_splits"),
        help="Directory where pilot subset split files and manifests will be written.",
    )
    parser.add_argument(
        "--subset-sizes",
        type=int,
        nargs="+",
        default=DEFAULT_SUBSET_SIZES,
        help="Total non-DRBC train+validation basin counts to create for the scaling pilot.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260419,
        help="Base random seed used for deterministic subset generation.",
    )
    parser.add_argument(
        "--stratify-col",
        type=str,
        default="camelsh_huc02",
        help="Metadata column used for nationwide stratified sampling.",
    )
    return parser.parse_args()


def read_basin_ids(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_raw_pool(train_path: Path, validation_path: Path) -> pd.DataFrame:
    train_ids = pd.DataFrame({"gauge_id": read_basin_ids(train_path), "original_split": "train"})
    validation_ids = pd.DataFrame({"gauge_id": read_basin_ids(validation_path), "original_split": "validation"})
    pool = pd.concat([train_ids, validation_ids], ignore_index=True)
    return pool.sort_values(["original_split", "gauge_id"]).reset_index(drop=True)


def load_prepared_manifest(path: Path) -> pd.DataFrame:
    manifest = pd.read_csv(path, dtype={"gauge_id": str})
    mask = (
        manifest["original_split"].isin(["train", "validation"])
        & manifest["prepared_split_status"].isin(["train", "validation"])
        & (~manifest["excluded_by_usability_gate"].fillna(False))
    )
    prepared = manifest.loc[mask].copy()
    return prepared.sort_values(["original_split", "gauge_id"]).reset_index(drop=True)


def load_basin_metadata(path: Path) -> pd.DataFrame:
    basin_meta = pd.read_csv(path, dtype={"STAID": str})[
        ["STAID", "STANAME", "HUC02", "STATE", "DRAIN_SQKM", "LAT_GAGE", "LNG_GAGE"]
    ].rename(
        columns={
            "STAID": "gauge_id",
            "STANAME": "gauge_name",
            "HUC02": "camelsh_huc02",
            "STATE": "state",
            "DRAIN_SQKM": "drain_sqkm_attr",
            "LAT_GAGE": "lat_gage",
            "LNG_GAGE": "lng_gage",
        }
    )
    basin_meta["camelsh_huc02"] = basin_meta["camelsh_huc02"].astype(str).str.zfill(2)
    return basin_meta


def load_static_attributes_from_raw(attributes_dir: Path) -> pd.DataFrame:
    basin_id = pd.read_csv(attributes_dir / "attributes_gageii_BasinID.csv", dtype={"STAID": str})[
        ["STAID", "DRAIN_SQKM"]
    ].rename(columns={"STAID": "gauge_id", "DRAIN_SQKM": "area"})
    topo = pd.read_csv(attributes_dir / "attributes_gageii_Topo.csv", dtype={"STAID": str})[
        ["STAID", "SLOPE_PCT"]
    ].rename(columns={"STAID": "gauge_id", "SLOPE_PCT": "slope"})
    clim = pd.read_csv(attributes_dir / "attributes_nldas2_climate.csv", dtype={"STAID": str})[
        ["STAID", "aridity_index", "frac_snow"]
    ].rename(columns={"STAID": "gauge_id", "aridity_index": "aridity", "frac_snow": "snow_fraction"})
    soil = pd.read_csv(attributes_dir / "attributes_gageii_Soils.csv", dtype={"STAID": str})[
        ["STAID", "ROCKDEPAVE", "PERMAVE"]
    ].rename(columns={"STAID": "gauge_id", "ROCKDEPAVE": "soil_depth", "PERMAVE": "permeability"})
    hydro = pd.read_csv(attributes_dir / "attributes_gageii_Hydro.csv", dtype={"STAID": str})[
        ["STAID", "BFI_AVE"]
    ].rename(columns={"STAID": "gauge_id", "BFI_AVE": "baseflow_index"})
    lc = pd.read_csv(attributes_dir / "attributes_gageii_LC06_Basin.csv", dtype={"STAID": str})[
        ["STAID", "FORESTNLCD06"]
    ].rename(columns={"STAID": "gauge_id"})
    lc["forest_fraction"] = pd.to_numeric(lc["FORESTNLCD06"], errors="coerce") / 100.0
    lc = lc[["gauge_id", "forest_fraction"]]

    return (
        basin_id.merge(topo, on="gauge_id")
        .merge(clim, on="gauge_id")
        .merge(soil, on="gauge_id")
        .merge(hydro, on="gauge_id")
        .merge(lc, on="gauge_id")
    )


def load_static_attributes(prepared_static_attributes_csv: Path, attributes_dir: Path) -> pd.DataFrame:
    if prepared_static_attributes_csv.exists():
        static_df = pd.read_csv(prepared_static_attributes_csv, dtype={"gauge_id": str})
    else:
        static_df = load_static_attributes_from_raw(attributes_dir=attributes_dir)

    rename_map = {"HUC02": "camelsh_huc02", "STATE": "state"}
    static_df = static_df.rename(columns=rename_map).copy()
    if "camelsh_huc02" in static_df.columns:
        static_df["camelsh_huc02"] = static_df["camelsh_huc02"].astype(str).str.zfill(2)

    keep_cols = ["gauge_id", *STATIC_ATTRIBUTE_COLUMNS]
    optional_cols = [col for col in ["camelsh_huc02", "state"] if col in static_df.columns]
    return static_df[[*keep_cols, *optional_cols]].drop_duplicates(subset=["gauge_id"])


def load_training_selected_metadata(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None

    selected = pd.read_csv(path, dtype={"gauge_id": str})
    keep_cols = [col for col in ["gauge_id", "camelsh_huc02", "state", "gauge_name", "drain_sqkm_attr"] if col in selected.columns]
    if not keep_cols:
        return None

    meta = selected[keep_cols].drop_duplicates(subset=["gauge_id"]).copy()
    if "camelsh_huc02" in meta.columns:
        meta["camelsh_huc02"] = meta["camelsh_huc02"].astype(str).str.zfill(2)
    return meta


def coalesce_metadata(primary: pd.DataFrame, fallback: pd.DataFrame) -> pd.DataFrame:
    merged = fallback.merge(primary, on="gauge_id", how="left", suffixes=("_fallback", ""))
    for col in ["camelsh_huc02", "state", "gauge_name", "drain_sqkm_attr"]:
        if col in merged.columns:
            continue
        preferred = f"{col}"
        fallback_col = f"{col}_fallback"
        if preferred in merged.columns and fallback_col in merged.columns:
            merged[col] = merged[preferred].fillna(merged[fallback_col])
    for col in ["camelsh_huc02", "state", "gauge_name", "drain_sqkm_attr"]:
        fallback_col = f"{col}_fallback"
        if fallback_col in merged.columns and col in merged.columns:
            merged[col] = merged[col].fillna(merged[fallback_col])
            merged = merged.drop(columns=[fallback_col])
    extra_drop = [col for col in merged.columns if col.endswith("_fallback")]
    if extra_drop:
        merged = merged.drop(columns=extra_drop)
    return merged


def value_counts_dict(series: pd.Series) -> dict[str, int]:
    cleaned = series.fillna("NA").astype(str)
    return {str(k): int(v) for k, v in cleaned.value_counts().sort_index().to_dict().items()}


def largest_remainder_allocation(
    group_sizes: pd.Series,
    target_count: int,
    ensure_min_per_group: bool,
) -> dict[str, int]:
    if target_count < 0:
        raise ValueError("target_count must be non-negative")
    if group_sizes.empty:
        if target_count != 0:
            raise ValueError("Cannot allocate a positive target_count from an empty group set")
        return {}

    sizes = group_sizes.astype(int).sort_index()
    total_available = int(sizes.sum())
    if target_count > total_available:
        raise ValueError(
            f"Requested {target_count} samples but only {total_available} are available."
        )

    min_counts = pd.Series(0, index=sizes.index, dtype=int)
    if ensure_min_per_group and target_count >= len(sizes):
        min_counts[:] = 1

    remaining_capacity = sizes - min_counts
    remaining_target = target_count - int(min_counts.sum())
    if remaining_target < 0:
        raise ValueError("Minimum-per-group allocation exceeded target_count")

    allocation = min_counts.copy()
    if remaining_target == 0:
        return {str(group): int(count) for group, count in allocation.items()}

    if int(remaining_capacity.sum()) == 0:
        return {str(group): int(count) for group, count in allocation.items()}

    exact = remaining_capacity / remaining_capacity.sum() * remaining_target
    floors = exact.apply(math.floor).astype(int)
    allocation += floors
    leftovers = remaining_target - int(floors.sum())

    remainders = (exact - floors).sort_values(ascending=False)
    for group in remainders.index:
        if leftovers == 0:
            break
        if allocation[group] < sizes[group]:
            allocation[group] += 1
            leftovers -= 1

    if leftovers > 0:
        spare_groups = [group for group in sizes.index if allocation[group] < sizes[group]]
        for group in spare_groups:
            if leftovers == 0:
                break
            allocation[group] += 1
            leftovers -= 1

    if leftovers != 0:
        raise ValueError("Failed to allocate all requested samples")

    return {str(group): int(count) for group, count in allocation.items()}


def stratified_sample(
    df: pd.DataFrame,
    group_col: str,
    target_count: int,
    seed: int,
    ensure_min_per_group: bool,
) -> pd.DataFrame:
    if target_count == 0:
        return df.iloc[0:0].copy()
    if target_count > len(df):
        raise ValueError(
            f"Requested {target_count} samples from a pool with only {len(df)} rows."
        )

    grouped = df.copy()
    grouped[group_col] = grouped[group_col].fillna("NA").astype(str)
    group_sizes = grouped[group_col].value_counts().sort_index()
    allocation = largest_remainder_allocation(
        group_sizes=group_sizes,
        target_count=target_count,
        ensure_min_per_group=ensure_min_per_group,
    )

    parts: list[pd.DataFrame] = []
    for idx, group in enumerate(sorted(allocation)):
        n_select = allocation[group]
        if n_select == 0:
            continue
        group_df = grouped[grouped[group_col] == group].sample(
            frac=1.0,
            random_state=seed + idx,
        )
        sampled = group_df.iloc[:n_select].copy()
        sampled["sampling_seed"] = seed + idx
        sampled["stratum_source_count"] = int(group_sizes[group])
        sampled["stratum_selected_count"] = n_select
        parts.append(sampled)

    if not parts:
        return grouped.iloc[0:0].copy()

    sampled_df = pd.concat(parts, ignore_index=True)
    if len(sampled_df) != target_count:
        raise ValueError(
            f"Expected {target_count} sampled rows but created {len(sampled_df)} rows."
        )
    return sampled_df.sort_values("gauge_id").reset_index(drop=True)


def write_basin_file(path: Path, gauge_ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(gauge_ids) + ("\n" if gauge_ids else ""), encoding="utf-8")


def build_candidate_pool(
    raw_pool: pd.DataFrame,
    prepared_manifest: pd.DataFrame,
    metadata: pd.DataFrame,
    static_attributes: pd.DataFrame,
    stratify_col: str,
) -> pd.DataFrame:
    candidate = raw_pool.merge(
        prepared_manifest[
            [
                "gauge_id",
                "original_split",
                "actual_valid_target_count",
                "obs_years_usable",
                "first_obs_year_usable",
                "last_obs_year_usable",
            ]
        ],
        on=["gauge_id", "original_split"],
        how="inner",
    ).merge(metadata, on="gauge_id", how="left")

    static_attributes = static_attributes.rename(
        columns={col: f"{col}_static" for col in ["camelsh_huc02", "state"] if col in static_attributes.columns}
    )
    candidate = candidate.merge(static_attributes, on="gauge_id", how="left")

    for col, fallback_col in [("camelsh_huc02", "camelsh_huc02_static"), ("state", "state_static")]:
        if fallback_col in candidate.columns:
            candidate[col] = candidate[col].fillna(candidate[fallback_col])
            candidate = candidate.drop(columns=[fallback_col])

    if stratify_col not in candidate.columns:
        raise ValueError(f"Requested stratify column `{stratify_col}` is not available.")
    if candidate[stratify_col].isna().any():
        missing_count = int(candidate[stratify_col].isna().sum())
        raise ValueError(
            f"Pilot candidate pool has {missing_count} rows with missing `{stratify_col}`."
        )

    candidate[stratify_col] = candidate[stratify_col].astype(str)

    missing_static_cols = [col for col in STATIC_ATTRIBUTE_COLUMNS if col not in candidate.columns]
    if missing_static_cols:
        raise ValueError(f"Missing static attribute columns in pilot candidate pool: {missing_static_cols}")
    for col in STATIC_ATTRIBUTE_COLUMNS:
        if candidate[col].isna().any():
            missing_count = int(candidate[col].isna().sum())
            raise ValueError(f"Pilot candidate pool has {missing_count} rows with missing `{col}`.")

    return candidate.sort_values(["original_split", stratify_col, "gauge_id"]).reset_index(drop=True)


def split_target_counts(candidate: pd.DataFrame, target_size: int) -> dict[str, int]:
    source_counts = candidate["original_split"].value_counts().sort_index()
    counts = largest_remainder_allocation(
        group_sizes=source_counts,
        target_count=target_size,
        ensure_min_per_group=False,
    )
    if target_size >= 2:
        for split in ["train", "validation"]:
            if split in counts and counts[split] == 0:
                donor = max(counts, key=counts.get)
                if counts[donor] <= 1:
                    raise ValueError("Unable to guarantee non-empty train/validation pilot splits")
                counts[donor] -= 1
                counts[split] = 1
    return counts


def build_subset(
    candidate: pd.DataFrame,
    target_size: int,
    test_ids: list[str],
    stratify_col: str,
    seed: int,
    output_dir: Path,
) -> dict[str, object]:
    split_counts = split_target_counts(candidate, target_size=target_size)
    subset_parts: list[pd.DataFrame] = []

    for offset, split in enumerate(["train", "validation"]):
        split_df = candidate[candidate["original_split"] == split].copy()
        sampled = stratified_sample(
            df=split_df,
            group_col=stratify_col,
            target_count=split_counts.get(split, 0),
            seed=seed + (1000 * (offset + 1)) + target_size,
            ensure_min_per_group=(split == "train"),
        )
        sampled["pilot_split"] = split
        sampled["pilot_subset_size"] = target_size
        subset_parts.append(sampled)

    subset = pd.concat(subset_parts, ignore_index=True).sort_values(["pilot_split", "gauge_id"]).reset_index(drop=True)
    if len(subset) != target_size:
        raise ValueError(f"Subset size drift detected for target {target_size}: {len(subset)} rows")

    subset_dir = output_dir / f"scaling_{target_size}"
    subset_dir.mkdir(parents=True, exist_ok=True)

    train_ids = subset.loc[subset["pilot_split"] == "train", "gauge_id"].tolist()
    validation_ids = subset.loc[subset["pilot_split"] == "validation", "gauge_id"].tolist()

    write_basin_file(subset_dir / "train.txt", train_ids)
    write_basin_file(subset_dir / "validation.txt", validation_ids)
    write_basin_file(subset_dir / "test.txt", test_ids)

    manifest_cols = [
        "gauge_id",
        "pilot_split",
        "original_split",
        "camelsh_huc02",
        "state",
        "gauge_name",
        "drain_sqkm_attr",
        "obs_years_usable",
        "first_obs_year_usable",
        "last_obs_year_usable",
        "actual_valid_target_count",
        "sampling_seed",
        "stratum_source_count",
        "stratum_selected_count",
        *STATIC_ATTRIBUTE_COLUMNS,
    ]
    manifest_path = subset_dir / "manifest.csv"
    subset[manifest_cols].to_csv(manifest_path, index=False)

    summary = {
        "subset_size": target_size,
        "train_count": int(len(train_ids)),
        "validation_count": int(len(validation_ids)),
        "test_count": int(len(test_ids)),
        "subset_dir": str(subset_dir),
        "manifest_path": str(manifest_path),
        "stratify_col": stratify_col,
        "stratified_huc02_counts": {
            "train": value_counts_dict(subset.loc[subset["pilot_split"] == "train", stratify_col]),
            "validation": value_counts_dict(subset.loc[subset["pilot_split"] == "validation", stratify_col]),
            "combined": value_counts_dict(subset[stratify_col]),
        },
    }

    summary_path = subset_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    return summary


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    raw_pool = load_raw_pool(
        train_path=args.raw_train_basin_file,
        validation_path=args.raw_validation_basin_file,
    )
    prepared_manifest = load_prepared_manifest(args.prepared_split_manifest)
    basin_meta = load_basin_metadata(args.basin_id_csv)
    selected_meta = load_training_selected_metadata(args.training_selected_csv)
    metadata = basin_meta if selected_meta is None else coalesce_metadata(selected_meta, basin_meta)
    static_attributes = load_static_attributes(
        prepared_static_attributes_csv=args.prepared_static_attributes_csv,
        attributes_dir=args.attributes_dir,
    )

    candidate = build_candidate_pool(
        raw_pool=raw_pool,
        prepared_manifest=prepared_manifest,
        metadata=metadata,
        static_attributes=static_attributes,
        stratify_col=args.stratify_col,
    )
    test_ids = read_basin_ids(args.prepared_test_basin_file)

    prepared_pool_manifest_path = args.output_dir / "prepared_pool_manifest.csv"
    candidate[
        [
            "gauge_id",
            "original_split",
            "camelsh_huc02",
            "state",
            "gauge_name",
            "drain_sqkm_attr",
            "actual_valid_target_count",
            "obs_years_usable",
            "first_obs_year_usable",
            "last_obs_year_usable",
            *STATIC_ATTRIBUTE_COLUMNS,
        ]
    ].to_csv(prepared_pool_manifest_path, index=False)

    subset_summaries: list[dict[str, object]] = []
    for subset_size in sorted(set(args.subset_sizes)):
        subset_summaries.append(
            build_subset(
                candidate=candidate,
                target_size=subset_size,
                test_ids=test_ids,
                stratify_col=args.stratify_col,
                seed=args.seed,
                output_dir=args.output_dir,
            )
        )

    source_summary = {
        "raw_broad_pool_total_count": int(len(raw_pool)),
        "raw_broad_train_count": int((raw_pool["original_split"] == "train").sum()),
        "raw_broad_validation_count": int((raw_pool["original_split"] == "validation").sum()),
        "prepared_broad_pool_total_count": int(len(candidate)),
        "prepared_broad_train_count": int((candidate["original_split"] == "train").sum()),
        "prepared_broad_validation_count": int((candidate["original_split"] == "validation").sum()),
        "prepared_broad_huc02_counts": value_counts_dict(candidate[args.stratify_col]),
        "stratify_col": args.stratify_col,
        "test_count": int(len(test_ids)),
    }

    summary = {
        "pilot_name": "deterministic_basin_count_scaling_pilot",
        "description": (
            "Operational pilot for choosing a compute-feasible nationwide non-DRBC basin count. "
            "This is not the official Model 1 vs Model 2 main comparison."
        ),
        "random_seed": args.seed,
        "source_files": {
            "prepared_split_manifest": str(args.prepared_split_manifest),
            "raw_train_basin_file": str(args.raw_train_basin_file),
            "raw_validation_basin_file": str(args.raw_validation_basin_file),
            "prepared_test_basin_file": str(args.prepared_test_basin_file),
            "training_selected_csv": str(args.training_selected_csv),
            "basin_id_csv": str(args.basin_id_csv),
            "prepared_static_attributes_csv": str(args.prepared_static_attributes_csv),
        },
        "source_summary": source_summary,
        "prepared_pool_manifest_path": str(prepared_pool_manifest_path),
        "subsets": subset_summaries,
    }

    summary_path = args.output_dir / "scaling_pilot_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Wrote scaling pilot split files under: {args.output_dir}")
    print(f"Wrote scaling pilot summary: {summary_path}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
