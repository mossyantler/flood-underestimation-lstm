#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "duckdb>=1.1",
# ]
# ///
"""Small DuckDB helper for CAMELS CSV inventory, inspection, and Parquet export."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

import duckdb


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE = REPO_ROOT / "database/local/duckdb/camels.duckdb"
DEFAULT_ROOTS = [Path("output"), Path("configs"), Path("docs")]
DEFAULT_PARQUET_ROOT = REPO_ROOT / "database/local/duckdb/parquet"

CORE_VIEWS = {
    "basin_metrics": Path("output/model_analysis/overall_analysis/epoch_sensitivity/tables/basin_metrics.csv"),
    "primary_epoch_basin_deltas": Path(
        "output/model_analysis/overall_analysis/main_comparison/tables/primary_epoch_basin_deltas.csv"
    ),
    "expanded_drbc_primary_summary": Path(
        "output/model_analysis/expanded_drbc_test/tables/primary_summary_by_seed.csv"
    ),
    "expanded_drbc_manifest": Path("configs/basin_splits/drbc_expanded_observed_test/manifest.csv"),
    "basin_membership": Path("output/model_analysis/natural_broad_comparison/tables/basin_membership.csv"),
    "extreme_rain_event_catalog": Path(
        "output/model_analysis/extreme_rain/primary/exposure/extreme_rain_event_catalog.csv"
    ),
    "extreme_rain_stress_long_primary": Path(
        "output/model_analysis/extreme_rain/primary/analysis/extreme_rain_stress_error_table_long.csv"
    ),
    "nws_flood_stage_coverage": Path("output/model_analysis/confirmed_flood/coverage/nws_flood_stage_coverage.csv"),
    "nws_coverage_bias": Path("output/model_analysis/confirmed_flood/coverage/coverage_bias_report.csv"),
    "drbc_confirmed_flood_events": Path("output/model_analysis/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv"),
    "drbc_confirmed_flood_performance": Path("output/model_analysis/confirmed_flood/performance/drbc_confirmed_flood_performance.csv"),
    "drbc_confirmed_flood_hydrograph_manifest": Path(
        "output/model_analysis/confirmed_flood/hydrographs/confirmed_flood_hydrograph_manifest.csv"
    ),
}

RUN_TEST_METRICS_GLOB = "runs/subset_comparison/**/test/model_epoch*/test_metrics.csv"
OBS_TIMESERIES_GLOB = "data/CAMELSH_generic/drbc_holdout_broad/time_series_csv/*.csv"
QUANTILE_REQUIRED_SERIES_GLOB = "output/model_analysis/quantile_analysis/required_series/**/*.csv"
QUANTILE_EXPORTS_GLOB = "output/model_analysis/quantile_analysis/quantile_exports/*.csv"
GAGES_ATTRIBUTES_GLOB = "basins/CAMELSH_data/attributes/*.csv"


def repo_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def relative_path(path: Path) -> Path:
    absolute = repo_path(path).resolve()
    try:
        return absolute.relative_to(REPO_ROOT)
    except ValueError:
        return absolute


def sql_literal(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def read_csv_expr(path: Path) -> str:
    return f"read_csv_auto({sql_literal(repo_path(path))}, union_by_name=true)"


def read_csv_glob_expr(pattern: str) -> str:
    return f"read_csv_auto({sql_literal(REPO_ROOT / pattern)}, union_by_name=true, filename=true)"


def read_parquet_glob_expr(pattern: str) -> str:
    return f"read_parquet({sql_literal(DEFAULT_PARQUET_ROOT / pattern)}, union_by_name=true, filename=true)"


def safe_identifier(value: str) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z_]+", "_", value).strip("_").lower()
    if not cleaned:
        cleaned = "csv_view"
    if cleaned[0].isdigit():
        cleaned = f"csv_{cleaned}"
    return cleaned


def connect(database: Path, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    database = repo_path(database)
    if read_only and not database.exists():
        raise FileNotFoundError(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(database), read_only=read_only)


def ensure_metadata_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS camels_meta")
    con.execute("CREATE SCHEMA IF NOT EXISTS camels_csv")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS camels_meta.csv_inventory (
            relative_path VARCHAR PRIMARY KEY,
            absolute_path VARCHAR NOT NULL,
            file_name VARCHAR NOT NULL,
            stem VARCHAR NOT NULL,
            top_level VARCHAR,
            path_group VARCHAR,
            size_bytes BIGINT NOT NULL,
            size_mb DOUBLE NOT NULL,
            modified_at TIMESTAMP NOT NULL,
            is_large BOOLEAN NOT NULL,
            recommended_backend VARCHAR NOT NULL,
            row_count BIGINT,
            cataloged_at TIMESTAMP NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS camels_meta.csv_views (
            view_schema VARCHAR NOT NULL,
            view_name VARCHAR NOT NULL,
            relative_path VARCHAR NOT NULL,
            absolute_path VARCHAR NOT NULL,
            created_at TIMESTAMP NOT NULL,
            PRIMARY KEY (view_schema, view_name)
        )
        """
    )


def iter_csv_paths(roots: Sequence[Path]) -> Iterable[Path]:
    for root in roots:
        absolute_root = repo_path(root)
        if not absolute_root.exists():
            continue
        yield from sorted(absolute_root.rglob("*.csv"))


def path_group_for(path: Path) -> str:
    parts = relative_path(path).parts
    if len(parts) >= 3:
        return "/".join(parts[:3])
    return "/".join(parts)


def backend_hint(size_bytes: int, rel: Path) -> str:
    rel_text = str(rel)
    if "required_series" in rel_text or "quantile_exports" in rel_text:
        return "duckdb_parquet"
    if size_bytes >= 50 * 1024 * 1024:
        return "duckdb_parquet"
    return "postgres_or_duckdb"


def count_rows_with_duckdb(con: duckdb.DuckDBPyConnection, path: Path) -> int:
    return int(con.execute(f"SELECT count(*) FROM {read_csv_expr(path)}").fetchone()[0])


def refresh_inventory(args: argparse.Namespace) -> None:
    con = connect(args.database)
    ensure_metadata_schema(con)

    now = datetime.now()
    rows = []
    for path in iter_csv_paths(args.roots):
        stat = path.stat()
        rel = relative_path(path)
        row_count = count_rows_with_duckdb(con, path) if args.row_counts else None
        rows.append(
            (
                str(rel),
                str(path.resolve()),
                path.name,
                path.stem,
                rel.parts[0] if rel.parts else None,
                path_group_for(path),
                stat.st_size,
                stat.st_size / 1024 / 1024,
                datetime.fromtimestamp(stat.st_mtime),
                stat.st_size >= args.large_threshold_mb * 1024 * 1024,
                backend_hint(stat.st_size, rel),
                row_count,
                now,
            )
        )

    con.execute("DELETE FROM camels_meta.csv_inventory")
    if rows:
        con.executemany(
            """
            INSERT INTO camels_meta.csv_inventory (
                relative_path,
                absolute_path,
                file_name,
                stem,
                top_level,
                path_group,
                size_bytes,
                size_mb,
                modified_at,
                is_large,
                recommended_backend,
                row_count,
                cataloged_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    if args.core_views:
        create_core_views(con)

    print(f"cataloged {len(rows)} CSV files in {relative_path(args.database)}")


def register_view_metadata(
    con: duckdb.DuckDBPyConnection,
    *,
    view_name: str,
    relative: str,
    absolute: str,
) -> None:
    con.execute(
        """
        INSERT OR REPLACE INTO camels_meta.csv_views (
            view_schema, view_name, relative_path, absolute_path, created_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        ["camels_csv", view_name, relative, absolute, datetime.now()],
    )


def create_relation_view(
    con: duckdb.DuckDBPyConnection,
    name: str,
    relation_sql: str,
    *,
    relative: str,
    absolute: str,
) -> None:
    view_name = safe_identifier(name)
    con.execute("CREATE SCHEMA IF NOT EXISTS camels_csv")
    con.execute(f"CREATE OR REPLACE VIEW camels_csv.{view_name} AS SELECT * FROM {relation_sql}")
    register_view_metadata(
        con,
        view_name=view_name,
        relative=relative,
        absolute=absolute,
    )


def create_csv_view(con: duckdb.DuckDBPyConnection, name: str, path: Path) -> None:
    absolute_path = repo_path(path)
    if not absolute_path.exists():
        raise FileNotFoundError(absolute_path)
    create_relation_view(
        con,
        name,
        read_csv_expr(absolute_path),
        relative=str(relative_path(absolute_path)),
        absolute=str(absolute_path.resolve()),
    )


def create_glob_view(con: duckdb.DuckDBPyConnection, name: str, pattern: str) -> None:
    if not sorted(REPO_ROOT.glob(pattern)):
        return
    create_relation_view(
        con,
        name,
        read_csv_glob_expr(pattern),
        relative=pattern,
        absolute=str(REPO_ROOT / pattern),
    )


def create_obs_timeseries_view(con: duckdb.DuckDBPyConnection) -> None:
    if not sorted(REPO_ROOT.glob(OBS_TIMESERIES_GLOB)):
        return
    relation_sql = (
        "(SELECT "
        "regexp_extract(filename, '([^/]+)\\.csv$', 1) AS gauge_id, "
        f"* FROM {read_csv_glob_expr(OBS_TIMESERIES_GLOB)})"
    )
    create_relation_view(
        con,
        "obs_timeseries",
        relation_sql,
        relative=OBS_TIMESERIES_GLOB,
        absolute=str(REPO_ROOT / OBS_TIMESERIES_GLOB),
    )


def parquet_pattern_for(csv_pattern: str) -> str:
    return csv_pattern.removesuffix(".csv") + ".parquet"


def create_parquet_preferred_view(con: duckdb.DuckDBPyConnection, name: str, csv_pattern: str) -> None:
    parquet_pattern = parquet_pattern_for(csv_pattern)
    if sorted(DEFAULT_PARQUET_ROOT.glob(parquet_pattern)):
        create_relation_view(
            con,
            name,
            read_parquet_glob_expr(parquet_pattern),
            relative=str(Path("database/local/duckdb/parquet") / parquet_pattern),
            absolute=str(DEFAULT_PARQUET_ROOT / parquet_pattern),
        )
        return
    create_glob_view(con, name, csv_pattern)


def create_core_views(con: duckdb.DuckDBPyConnection) -> None:
    ensure_metadata_schema(con)
    for name, path in CORE_VIEWS.items():
        if repo_path(path).exists():
            create_csv_view(con, name, path)
    create_subset300_raw_test_metrics_view(con)


def create_extended_views(con: duckdb.DuckDBPyConnection) -> None:
    ensure_metadata_schema(con)
    create_obs_timeseries_view(con)
    create_parquet_preferred_view(con, "quantile_required_series", QUANTILE_REQUIRED_SERIES_GLOB)
    create_parquet_preferred_view(con, "quantile_exports", QUANTILE_EXPORTS_GLOB)
    for path in sorted(REPO_ROOT.glob(GAGES_ATTRIBUTES_GLOB)):
        create_csv_view(con, path.stem, path)


def create_subset300_raw_test_metrics_view(con: duckdb.DuckDBPyConnection) -> None:
    pattern = REPO_ROOT / RUN_TEST_METRICS_GLOB
    matching_files = sorted(REPO_ROOT.glob(RUN_TEST_METRICS_GLOB))
    if not matching_files:
        return

    con.execute("CREATE SCHEMA IF NOT EXISTS camels_csv")
    con.execute(
        f"""
        CREATE OR REPLACE VIEW camels_csv.subset300_raw_test_metrics AS
        WITH raw AS (
            SELECT *
            FROM read_csv_auto({sql_literal(pattern)}, union_by_name=true, filename=true)
        )
        SELECT
            regexp_extract(filename, 'camelsh_hourly_(model[12])_', 1) AS model,
            CAST(regexp_extract(filename, 'seed([0-9]+)', 1) AS INTEGER) AS seed,
            CAST(regexp_extract(filename, 'model_epoch([0-9]+)', 1) AS INTEGER) AS epoch,
            regexp_extract(filename, 'runs/subset_comparison/([^/]+)', 1) AS run_name,
            filename AS metric_path,
            basin,
            NSE AS nse,
            KGE AS kge,
            FHV AS fhv,
            "Peak-Timing" AS peak_timing,
            "Peak-MAPE" AS peak_mape
        FROM raw
        """
    )
    con.execute(
        """
        INSERT OR REPLACE INTO camels_meta.csv_views (
            view_schema, view_name, relative_path, absolute_path, created_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        [
            "camels_csv",
            "subset300_raw_test_metrics",
            RUN_TEST_METRICS_GLOB,
            str(pattern),
            datetime.now(),
        ],
    )


def register_views(args: argparse.Namespace) -> None:
    con = connect(args.database)
    ensure_metadata_schema(con)
    if args.core or not args.csv_paths:
        create_core_views(con)
        if args.extended:
            create_extended_views(con)
    for path in args.csv_paths:
        create_csv_view(con, args.name or path.stem, path)
    rows = con.execute("SELECT view_schema, view_name, relative_path FROM camels_meta.csv_views ORDER BY view_name").fetchall()
    print_table(["schema", "view", "relative_path"], rows)


def inspect_csv(args: argparse.Namespace) -> None:
    con = duckdb.connect()
    path = repo_path(args.csv_path)
    if not path.exists():
        raise FileNotFoundError(path)

    print(f"path: {relative_path(path)}")
    print(f"size: {path.stat().st_size / 1024 / 1024:.2f} MB")

    row_count = count_rows_with_duckdb(con, path)
    print(f"rows: {row_count}")

    print("\nschema:")
    schema_rows = con.execute(f"DESCRIBE SELECT * FROM {read_csv_expr(path)}").fetchall()
    print_table(["column", "type", "null", "key", "default", "extra"], schema_rows)

    print(f"\nsample ({args.limit} rows):")
    sample = con.execute(f"SELECT * FROM {read_csv_expr(path)} LIMIT {args.limit}").fetchall()
    columns = [description[0] for description in con.description]
    print_table(columns, sample, max_width=args.max_width)


def expand_csv_inputs(csv_paths: Sequence[Path]) -> list[Path]:
    expanded: list[Path] = []
    for csv_path in csv_paths:
        path_text = str(csv_path)
        if any(char in path_text for char in "*?[]"):
            matches = sorted(REPO_ROOT.glob(path_text))
            if not matches:
                raise FileNotFoundError(path_text)
            expanded.extend(matches)
            continue

        source = repo_path(csv_path)
        if source.is_dir():
            expanded.extend(sorted(source.rglob("*.csv")))
        else:
            expanded.append(source)
    return expanded


def export_parquet(args: argparse.Namespace) -> None:
    con = duckdb.connect()
    output_root = repo_path(args.output_root)
    compression = args.compression.upper()
    for source in expand_csv_inputs(args.csv_paths):
        if not source.exists():
            raise FileNotFoundError(source)
        rel = relative_path(source)
        target = output_root / rel.with_suffix(".parquet")
        if target.exists() and not args.overwrite:
            print(f"skip existing {relative_path(target)}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        con.execute(
            f"""
            COPY (
                SELECT * FROM {read_csv_expr(source)}
            ) TO {sql_literal(target)} (
                FORMAT PARQUET,
                COMPRESSION {compression}
            )
            """
        )
        print(f"wrote {relative_path(target)}")


def run_query(args: argparse.Namespace) -> None:
    con = connect(args.database, read_only=True)
    rows = con.execute(args.sql).fetchall()
    columns = [description[0] for description in con.description]
    print_table(columns, rows, max_width=args.max_width)


def print_table(columns: Sequence[str], rows: Sequence[Sequence[object]], max_width: int = 48) -> None:
    values = [[format_cell(cell, max_width=max_width) for cell in row] for row in rows]
    widths = [
        min(max(len(str(column)), *(len(row[index]) for row in values)) if values else len(str(column)), max_width)
        for index, column in enumerate(columns)
    ]
    header = " | ".join(str(column).ljust(widths[index]) for index, column in enumerate(columns))
    divider = "-+-".join("-" * width for width in widths)
    print(header)
    print(divider)
    for row in values:
        print(" | ".join(row[index].ljust(widths[index]) for index in range(len(columns))))


def format_cell(value: object, max_width: int) -> str:
    if value is None:
        text = ""
    else:
        text = str(value)
    text = text.replace("\n", " ")
    if len(text) > max_width:
        return text[: max_width - 1] + "..."
    return text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE,
        help="DuckDB database file. Defaults to database/local/duckdb/camels.duckdb.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    catalog = subparsers.add_parser("catalog", help="Build a CSV inventory table.")
    catalog.add_argument("--roots", nargs="+", type=Path, default=DEFAULT_ROOTS)
    catalog.add_argument("--row-counts", action="store_true", help="Count rows with DuckDB. This can be slow.")
    catalog.add_argument("--large-threshold-mb", type=int, default=50)
    catalog.add_argument("--no-core-views", dest="core_views", action="store_false")
    catalog.set_defaults(func=refresh_inventory, core_views=True)

    inspect = subparsers.add_parser("inspect", help="Inspect one CSV with DuckDB.")
    inspect.add_argument("csv_path", type=Path)
    inspect.add_argument("--limit", type=int, default=5)
    inspect.add_argument("--max-width", type=int, default=48)
    inspect.set_defaults(func=inspect_csv)

    parquet = subparsers.add_parser("to-parquet", help="Convert explicit CSV files to Parquet.")
    parquet.add_argument("csv_paths", nargs="+", type=Path)
    parquet.add_argument("--output-root", type=Path, default=DEFAULT_PARQUET_ROOT)
    parquet.add_argument("--compression", default="zstd", choices=["zstd", "snappy", "gzip", "uncompressed"])
    parquet.add_argument("--overwrite", action="store_true")
    parquet.set_defaults(func=export_parquet)

    views = subparsers.add_parser("views", help="Register CSV files as DuckDB views.")
    views.add_argument("csv_paths", nargs="*", type=Path)
    views.add_argument("--name", help="View name for a single CSV path.")
    views.add_argument("--core", action="store_true", help="Register the default core CAMELS CSV views.")
    views.add_argument(
        "--no-extended",
        dest="extended",
        action="store_false",
        help="When no explicit CSV paths are provided, skip time-series and raw attribute views.",
    )
    views.set_defaults(func=register_views, extended=True)

    query = subparsers.add_parser("query", help="Run SQL against the DuckDB database.")
    query.add_argument("sql")
    query.add_argument("--max-width", type=int, default=80)
    query.set_defaults(func=run_query)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
