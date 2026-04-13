#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.8",
#   "netcdf4>=1.7",
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "xarray>=2024.1",
# ]
# ///

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect a NetCDF file with xarray and optionally save a quick-look PNG preview."
    )
    parser.add_argument("path", type=Path, help="Path to a .nc or .nc4 file.")
    parser.add_argument(
        "--variables",
        nargs="*",
        default=None,
        help="Variables to preview. Defaults to the first three 1D time-series variables.",
    )
    parser.add_argument("--start-date", type=str, default=None, help="Optional inclusive start date.")
    parser.add_argument("--end-date", type=str, default=None, help="Optional inclusive end date.")
    parser.add_argument(
        "--head",
        type=int,
        default=5,
        help="Number of preview rows to print from the selected variables.",
    )
    parser.add_argument(
        "--plot-png",
        type=Path,
        default=None,
        help="Optional PNG path for a quick-look plot of the selected variables.",
    )
    parser.add_argument(
        "--describe-all",
        action="store_true",
        help="Print summary statistics for all data variables, not just the preview variables.",
    )
    return parser.parse_args()


def detect_time_coord(ds: xr.Dataset) -> str | None:
    for name in ("date", "time", "DateTime"):
        if name in ds.coords:
            return name

    for name, coord in ds.coords.items():
        if np.issubdtype(coord.dtype, np.datetime64):
            return name

    return None


def select_preview_variables(
    ds: xr.Dataset, requested: list[str] | None, time_coord: str | None
) -> list[str]:
    if requested:
        missing = [name for name in requested if name not in ds.data_vars]
        if missing:
            raise SystemExit(f"Dataset에 없는 변수가 있습니다: {', '.join(missing)}")
        return requested

    if time_coord is None:
        return list(ds.data_vars)[:3]

    previewable = [
        name
        for name, da in ds.data_vars.items()
        if da.ndim == 1 and da.dims == (time_coord,)
    ]
    if previewable:
        return previewable[:3]
    return list(ds.data_vars)[:3]


def maybe_slice_time(ds: xr.Dataset, time_coord: str | None, start_date: str | None, end_date: str | None) -> xr.Dataset:
    if time_coord is None or (start_date is None and end_date is None):
        return ds

    return ds.sel({time_coord: slice(start_date, end_date)})


def build_preview_frame(ds: xr.Dataset, variables: list[str], time_coord: str | None) -> pd.DataFrame:
    previewable = []
    for name in variables:
        da = ds[name]
        if time_coord is not None and da.ndim == 1 and da.dims == (time_coord,):
            previewable.append(name)
        elif time_coord is None and da.ndim == 1:
            previewable.append(name)

    if not previewable:
        raise SystemExit("선택한 변수 중에서 1D preview를 만들 수 있는 변수가 없습니다.")

    frame = ds[previewable].to_dataframe()
    if time_coord is not None and time_coord in frame.index.names:
        frame.index.name = time_coord
    return frame


def print_variable_summary(ds: xr.Dataset, variables: list[str]) -> None:
    print("Variable summary:")
    for name in variables:
        da = ds[name]
        valid_count = int(da.count().item()) if da.size else 0
        line = f"- {name}: dtype={da.dtype}, dims={da.dims}, shape={da.shape}, valid={valid_count}"
        if np.issubdtype(da.dtype, np.number) and da.count().item() > 0:
            line += (
                f", min={float(da.min(skipna=True).item()):.6g}"
                f", max={float(da.max(skipna=True).item()):.6g}"
                f", mean={float(da.mean(skipna=True).item()):.6g}"
            )
        print(line)


def save_preview_plot(frame: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(
        nrows=len(frame.columns),
        ncols=1,
        figsize=(12, 3 * len(frame.columns)),
        sharex=True,
        squeeze=False,
    )

    for ax, column in zip(axes.flatten(), frame.columns):
        ax.plot(frame.index, frame[column], linewidth=0.8)
        ax.set_ylabel(column)
        ax.grid(alpha=0.25)

    axes[-1, 0].set_xlabel(frame.index.name or "index")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    if not args.path.exists():
        raise SystemExit(f"파일이 없습니다: {args.path}")

    with xr.open_dataset(args.path, engine="netcdf4") as ds:
        time_coord = detect_time_coord(ds)
        subset = maybe_slice_time(ds, time_coord, args.start_date, args.end_date)
        variables = select_preview_variables(subset, args.variables, time_coord)

        print(f"Path: {args.path}")
        print(f"Time coordinate: {time_coord or 'not found'}")
        print(f"Dimensions: {dict(subset.sizes)}")
        print(f"Coordinates: {list(subset.coords)}")
        print(f"Data variables: {list(subset.data_vars)}")
        print()

        summary_variables = list(subset.data_vars) if args.describe_all else variables
        print_variable_summary(subset, summary_variables)
        if args.describe_all and variables != summary_variables:
            print()
            print(f"Preview variables: {variables}")
        print()

        frame = build_preview_frame(subset, variables, time_coord)
        if args.head > 0:
            print(f"Preview ({min(args.head, len(frame))} rows):")
            print(frame.head(args.head).to_string())
            print()

        if args.plot_png is not None:
            save_preview_plot(frame, args.plot_png)
            print(f"Saved preview PNG: {args.plot_png}")


if __name__ == "__main__":
    main()
