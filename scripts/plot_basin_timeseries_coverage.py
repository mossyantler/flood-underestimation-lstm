#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.8",
#   "pandas>=2.2",
#   "pyyaml>=6.0",
# ]
# ///
"""Plot basin observation spans for the fixed subset300 main split."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "configs/pilot/camelsh_hourly_model1_drbc_holdout_scaling_300.yml"
DEFAULT_PREPARED_MANIFEST = (
    PROJECT_ROOT / "data/CAMELSH_generic/drbc_holdout_broad/splits/split_manifest.csv"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "output/basin/timeseries/basin_timeseries_coverage.png"
DEFAULT_METADATA = PROJECT_ROOT / "output/basin/timeseries/basin_timeseries_coverage_metadata.json"

SPLIT_ORDER = ("train", "validation", "test")
SPLIT_LABELS = {
    "train": "Train",
    "validation": "Validation",
    "test": "Test",
}
COLORS = {
    "train": "#4C72B0",
    "validation": "#DD8452",
    "test": "#55A868",
}
BG = "#F8F9FA"
GRID = "#CED4DA"
TEXT = "#212529"
MUTED = "#6C757D"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a fixed main-split basin coverage Gantt chart. The chart "
            "uses the configured subset300 split files and validates that every "
            "basin passed the prepared split-window target filter."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="NeuralHydrology config that defines split files and split dates.",
    )
    parser.add_argument(
        "--prepared-manifest",
        type=Path,
        default=DEFAULT_PREPARED_MANIFEST,
        help="Prepared broad split manifest with split-window filtering metadata.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output PNG path.",
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=DEFAULT_METADATA,
        help="Output JSON metadata path.",
    )
    return parser.parse_args()


def resolve_path(path_like: str | Path, base: Path = PROJECT_ROOT) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    return base / path


def read_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fp:
        config = yaml.safe_load(fp)
    if not isinstance(config, dict):
        raise ValueError(f"Config did not parse as a mapping: {path}")
    return config


def parse_config_date(value: str) -> pd.Timestamp:
    return pd.to_datetime(value, dayfirst=True)


def read_basin_file(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def split_files_from_config(config: dict[str, Any]) -> dict[str, Path]:
    return {
        split: resolve_path(config[f"{split}_basin_file"])
        for split in SPLIT_ORDER
    }


def split_periods_from_config(config: dict[str, Any]) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    periods: dict[str, tuple[pd.Timestamp, pd.Timestamp]] = {}
    for split in SPLIT_ORDER:
        periods[split] = (
            parse_config_date(config[f"{split}_start_date"]),
            parse_config_date(config[f"{split}_end_date"]),
        )
    return periods


def build_fixed_split_frame(
    prepared_manifest_path: Path,
    split_files: dict[str, Path],
    periods: dict[str, tuple[pd.Timestamp, pd.Timestamp]],
) -> pd.DataFrame:
    manifest = pd.read_csv(prepared_manifest_path, dtype={"gauge_id": str})
    required_cols = {
        "gauge_id",
        "original_split",
        "prepared_split_status",
        "split_start_date",
        "split_end_date",
        "min_valid_target_count",
        "actual_valid_target_count",
        "obs_years_usable",
        "first_obs_year_usable",
        "last_obs_year_usable",
        "excluded_by_usability_gate",
    }
    missing_cols = sorted(required_cols - set(manifest.columns))
    if missing_cols:
        raise ValueError(f"Prepared manifest is missing columns: {missing_cols}")

    rows: list[pd.DataFrame] = []
    for split in SPLIT_ORDER:
        basin_ids = read_basin_file(split_files[split])
        selected = manifest[manifest["gauge_id"].isin(basin_ids)].copy()
        missing_ids = sorted(set(basin_ids) - set(selected["gauge_id"]))
        if missing_ids:
            raise ValueError(f"{split} basin ids missing from prepared manifest: {missing_ids[:10]}")

        if selected["gauge_id"].duplicated().any():
            dupes = selected.loc[selected["gauge_id"].duplicated(), "gauge_id"].tolist()
            raise ValueError(f"{split} has duplicated prepared manifest rows: {dupes[:10]}")

        invalid = selected[
            (selected["original_split"] != split)
            | (selected["prepared_split_status"] != split)
            | (selected["excluded_by_usability_gate"].fillna(True).astype(bool))
        ].copy()
        if not invalid.empty:
            sample = invalid[
                [
                    "gauge_id",
                    "original_split",
                    "prepared_split_status",
                    "excluded_by_usability_gate",
                    "actual_valid_target_count",
                    "min_valid_target_count",
                ]
            ].head(10)
            raise ValueError(
                f"{split} contains basin ids that did not pass the prepared split-window gate:\n"
                f"{sample.to_string(index=False)}"
            )

        configured_start, configured_end = periods[split]
        manifest_start = pd.to_datetime(selected["split_start_date"])
        manifest_end = pd.to_datetime(selected["split_end_date"])
        if not ((manifest_start == configured_start).all() and (manifest_end == configured_end).all()):
            raise ValueError(
                f"{split} config dates do not match prepared manifest split dates. "
                f"Config={configured_start:%Y-%m-%d}..{configured_end:%Y-%m-%d}"
            )

        selected["split"] = split
        selected["configured_start"] = configured_start
        selected["configured_end"] = configured_end
        selected["_order"] = selected["gauge_id"].map({gauge_id: i for i, gauge_id in enumerate(basin_ids)})
        rows.append(selected)

    fixed = pd.concat(rows, ignore_index=True)
    for col in [
        "first_obs_year_usable",
        "last_obs_year_usable",
        "obs_years_usable",
        "min_valid_target_count",
        "actual_valid_target_count",
    ]:
        fixed[col] = pd.to_numeric(fixed[col], errors="coerce")

    if fixed[["first_obs_year_usable", "last_obs_year_usable"]].isna().any().any():
        bad = fixed[fixed[["first_obs_year_usable", "last_obs_year_usable"]].isna().any(axis=1)]
        raise ValueError(f"Missing usable-year span for basin ids: {bad['gauge_id'].head(10).tolist()}")

    fixed["_split_order"] = fixed["split"].map({split: i for i, split in enumerate(SPLIT_ORDER)})
    fixed = fixed.sort_values(
        ["_split_order", "first_obs_year_usable", "last_obs_year_usable", "_order", "gauge_id"]
    ).reset_index(drop=True)
    return fixed


def year_window(start: pd.Timestamp, end: pd.Timestamp) -> tuple[int, int]:
    return int(start.year), int(end.year + 1)


def plot_coverage(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    n_basins = len(df)
    fig_height = max(14, n_basins * 0.078)
    fig, ax = plt.subplots(figsize=(18, fig_height), facecolor=BG)
    ax.set_facecolor(BG)

    for split in SPLIT_ORDER:
        split_df = df[df["split"] == split]
        start = pd.Timestamp(split_df["configured_start"].iloc[0])
        end = pd.Timestamp(split_df["configured_end"].iloc[0])
        x0, x1 = year_window(start, end)
        ax.axvspan(x0, x1, color=COLORS[split], alpha=0.055, zorder=0)

    bar_height = 0.72
    for idx, row in df.iterrows():
        split = row["split"]
        color = COLORS[split]
        start_year = int(row["first_obs_year_usable"])
        end_year = int(row["last_obs_year_usable"]) + 1
        ax.barh(
            idx,
            end_year - start_year,
            left=start_year,
            height=bar_height,
            color=color,
            alpha=0.82,
            zorder=3,
        )

        window_start, window_end = year_window(
            pd.Timestamp(row["configured_start"]),
            pd.Timestamp(row["configured_end"]),
        )
        ax.barh(
            idx,
            window_end - window_start,
            left=window_start,
            height=bar_height * 0.42,
            color="white",
            alpha=0.46,
            zorder=4,
        )

    previous_split = None
    for idx, row in df.iterrows():
        split = row["split"]
        if split == previous_split:
            continue
        if previous_split is not None:
            ax.axhline(idx - 0.5, color=GRID, lw=0.9, linestyle="--", zorder=2)
        group = df[df["split"] == split]
        center = (group.index.min() + group.index.max()) / 2
        threshold = int(group["min_valid_target_count"].iloc[0])
        ax.text(
            2025.5,
            center,
            f"{SPLIT_LABELS[split]}\n(n={len(group)}, min valid={threshold})",
            ha="left",
            va="center",
            fontsize=8.1,
            color=COLORS[split],
            fontweight="bold",
        )
        previous_split = split

    for x in range(1986, 2026, 2):
        ax.axvline(x, color=GRID, lw=0.4, zorder=1)

    split_counts = df["split"].value_counts().reindex(SPLIT_ORDER).fillna(0).astype(int)
    ax.set_title(
        "Fixed Main Split Basin Observation Coverage\n"
        f"train={split_counts['train']} | validation={split_counts['validation']} | test(DRBC)={split_counts['test']}",
        fontsize=13,
        fontweight="bold",
        color=TEXT,
        pad=12,
    )
    ax.set_xlabel(
        "Year (bar = usable observation years, white stripe = configured split window that passed target filtering)",
        fontsize=9.5,
        color=MUTED,
    )
    ax.set_ylabel("Basin ID (gauge_id)", fontsize=10, color=MUTED)

    ax.set_xlim(1985, 2028)
    ax.set_ylim(-0.8, n_basins - 0.2)
    ax.invert_yaxis()
    ax.set_yticks(range(n_basins))
    ax.set_yticklabels(df["gauge_id"].tolist(), fontsize=4.6, color=TEXT)
    ax.tick_params(axis="y", length=0, pad=2)
    ax.set_xticks(range(1986, 2026, 2))
    ax.set_xticklabels(range(1986, 2026, 2), fontsize=8.5, color=MUTED)
    ax.tick_params(axis="x", which="both", color=GRID)

    for spine in ax.spines.values():
        spine.set_edgecolor(GRID)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    handles = [
        mpatches.Patch(facecolor=COLORS["train"], label="Train subset (2000-2010)"),
        mpatches.Patch(facecolor=COLORS["validation"], label="Validation subset (2011-2013)"),
        mpatches.Patch(facecolor=COLORS["test"], label="DRBC test holdout (2014-2016)"),
        mpatches.Patch(facecolor="white", edgecolor=GRID, label="Configured split window"),
    ]
    ax.legend(
        handles=handles,
        loc="upper left",
        fontsize=9,
        frameon=True,
        fancybox=False,
        edgecolor=GRID,
        facecolor="white",
    )

    fig.tight_layout()
    fig.savefig(output_path, dpi=160, bbox_inches="tight", facecolor=BG)
    plt.close(fig)


def write_metadata(
    df: pd.DataFrame,
    metadata_path: Path,
    output_path: Path,
    config_path: Path,
    prepared_manifest_path: Path,
) -> None:
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "chart": str(output_path.relative_to(PROJECT_ROOT)),
        "config": str(config_path.relative_to(PROJECT_ROOT)),
        "prepared_manifest": str(prepared_manifest_path.relative_to(PROJECT_ROOT)),
        "filtering_basis": (
            "All plotted basins are read from the configured fixed main split files "
            "and validated against prepared_split_status plus excluded_by_usability_gate. "
            "actual_valid_target_count is therefore the count inside that split's configured timeline."
        ),
        "splits": {},
    }
    for split in SPLIT_ORDER:
        split_df = df[df["split"] == split]
        summary["splits"][split] = {
            "basin_count": int(len(split_df)),
            "configured_start": pd.Timestamp(split_df["configured_start"].iloc[0]).strftime("%Y-%m-%d"),
            "configured_end": pd.Timestamp(split_df["configured_end"].iloc[0]).strftime("%Y-%m-%d"),
            "min_valid_target_count": int(split_df["min_valid_target_count"].iloc[0]),
            "actual_valid_target_count_min": int(split_df["actual_valid_target_count"].min()),
            "actual_valid_target_count_median": float(split_df["actual_valid_target_count"].median()),
            "actual_valid_target_count_max": int(split_df["actual_valid_target_count"].max()),
        }
    metadata_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    config_path = resolve_path(args.config)
    prepared_manifest_path = resolve_path(args.prepared_manifest)
    output_path = resolve_path(args.output)
    metadata_path = resolve_path(args.metadata)

    config = read_config(config_path)
    split_files = split_files_from_config(config)
    periods = split_periods_from_config(config)
    df = build_fixed_split_frame(
        prepared_manifest_path=prepared_manifest_path,
        split_files=split_files,
        periods=periods,
    )
    plot_coverage(df, output_path)
    write_metadata(df, metadata_path, output_path, config_path, prepared_manifest_path)

    counts = df["split"].value_counts().reindex(SPLIT_ORDER).fillna(0).astype(int)
    print(
        f"Saved -> {output_path} "
        f"(train={counts['train']}, validation={counts['validation']}, test={counts['test']})"
    )
    print(f"Saved -> {metadata_path}")


if __name__ == "__main__":
    main()
