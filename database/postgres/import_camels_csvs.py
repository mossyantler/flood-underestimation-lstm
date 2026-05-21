#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Initialize the CAMELS PostgreSQL analysis cache and import core CSVs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_SQL = Path(__file__).with_name("init_camels_analysis_db.sql")

BASIN_METRICS = Path("output/model_analysis/legacy/overall_analysis/epoch_sensitivity/tables/basin_metrics.csv")
PRIMARY_DELTAS = Path("output/model_analysis/legacy/overall_analysis/main_comparison/tables/primary_epoch_basin_deltas.csv")
BASIN_MEMBERSHIP = Path("output/model_analysis/legacy/natural_broad_comparison/tables/basin_membership.csv")
EXTREME_RAIN_EVENTS = Path("output/model_analysis/legacy/extreme_rain/primary/exposure/extreme_rain_event_catalog.csv")
BASIN_STATIC_ATTRIBUTES = Path("data/CAMELSH_generic/drbc_holdout_broad/attributes/static_attributes.csv")
BASIN_FLOOD_GENERATION = Path("output/basin/all/analysis/flood_generation/tables/flood_generation_basin_summary.csv")
BASIN_EVENT_RESPONSE = Path("output/basin/all/analysis/event_response/tables/event_response_basin_summary.csv")
BASIN_EVENT_REGIME = Path("output/basin/all/analysis/event_regime/tables/selected_variant_basin_map_labels.csv")
PROB_PINBALL = Path("output/model_analysis/legacy/probabilistic_diagnostics/quantile_pinball_summary.csv")
PROB_CALIBRATION = Path("output/model_analysis/legacy/probabilistic_diagnostics/quantile_calibration_summary.csv")
PROB_TAIL_SPREAD = Path("output/model_analysis/legacy/probabilistic_diagnostics/upper_tail_spread_summary.csv")
NWS_FLOOD_STAGE_COVERAGE = Path("output/model_analysis/expanded/confirmed_flood/coverage/nws_flood_stage_coverage.csv")
NWS_COVERAGE_BIAS = Path("output/model_analysis/expanded/confirmed_flood/coverage/coverage_bias_report.csv")
DRBC_CONFIRMED_FLOOD_EVENTS = Path("output/model_analysis/expanded/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv")
DRBC_CONFIRMED_FLOOD_PERFORMANCE = Path("output/model_analysis/expanded/confirmed_flood/performance/drbc_confirmed_flood_performance.csv")
CONFIRMED_FLOOD_TIMESERIES_SEED111 = Path("output/model_analysis/expanded/confirmed_flood/inference/required_series/seed111/primary_required_series.csv")
CONFIRMED_FLOOD_TIMESERIES_SEED222 = Path("output/model_analysis/expanded/confirmed_flood/inference/required_series/seed222/primary_required_series.csv")
CONFIRMED_FLOOD_TIMESERIES_SEED444 = Path("output/model_analysis/expanded/confirmed_flood/inference/required_series/seed444/primary_required_series.csv")

EXPANDED_DRBC_BASIN_METRICS = Path("output/model_analysis/expanded/expanded_drbc_test/tables/basin_metrics.csv")
EXPANDED_DRBC_EXTREME_RAIN_EVENTS = Path("output/model_analysis/expanded/extreme_rain/expanded_drbc/exposure/extreme_rain_event_catalog.csv")
EXPANDED_DRBC_TIMESERIES_SEED111 = Path("output/model_analysis/expanded/expanded_drbc_test/required_series/seed111/primary_required_series.csv")
EXPANDED_DRBC_TIMESERIES_SEED222 = Path("output/model_analysis/expanded/expanded_drbc_test/required_series/seed222/primary_required_series.csv")
EXPANDED_DRBC_TIMESERIES_SEED444 = Path("output/model_analysis/expanded/expanded_drbc_test/required_series/seed444/primary_required_series.csv")
RETURN_PERIOD_REFERENCES = Path("output/basin/all/analysis/return_period/tables/return_period_reference_table_with_drbc_expanded85.csv")
EXTREME_RAIN_COHORT_PREDICTOR_SUMMARY_EXPANDED = Path("output/model_analysis/expanded/extreme_rain/expanded_drbc/analysis/cohort_predictor_summary.csv")
EXTREME_RAIN_PAIRED_DELTA_SUMMARY_EXPANDED = Path("output/model_analysis/expanded/extreme_rain/expanded_drbc/analysis/paired_delta_seed_summary.csv")

DEFAULT_CSVS = [
    BASIN_METRICS,
    PRIMARY_DELTAS,
    BASIN_MEMBERSHIP,
    EXTREME_RAIN_EVENTS,
    BASIN_STATIC_ATTRIBUTES,
    BASIN_FLOOD_GENERATION,
    BASIN_EVENT_RESPONSE,
    BASIN_EVENT_REGIME,
    PROB_PINBALL,
    PROB_CALIBRATION,
    PROB_TAIL_SPREAD,
    NWS_FLOOD_STAGE_COVERAGE,
    NWS_COVERAGE_BIAS,
    DRBC_CONFIRMED_FLOOD_EVENTS,
    DRBC_CONFIRMED_FLOOD_PERFORMANCE,
    CONFIRMED_FLOOD_TIMESERIES_SEED111,
    CONFIRMED_FLOOD_TIMESERIES_SEED222,
    CONFIRMED_FLOOD_TIMESERIES_SEED444,
    EXPANDED_DRBC_BASIN_METRICS,
    EXPANDED_DRBC_EXTREME_RAIN_EVENTS,
    EXPANDED_DRBC_TIMESERIES_SEED111,
    EXPANDED_DRBC_TIMESERIES_SEED222,
    EXPANDED_DRBC_TIMESERIES_SEED444,
    RETURN_PERIOD_REFERENCES,
    EXTREME_RAIN_COHORT_PREDICTOR_SUMMARY_EXPANDED,
    EXTREME_RAIN_PAIRED_DELTA_SUMMARY_EXPANDED,
]

IMPORTER = "database/postgres/import_camels_csvs.py"
ColumnSpec = tuple[str, str, Callable[[str | None], str]]


def run_command(args: list[str], *, input_text: str | None = None, capture: bool = False) -> str:
    completed = subprocess.run(
        args,
        input=input_text,
        text=True,
        check=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    return completed.stdout.strip() if capture else ""


def run_psql(database: str, sql: str, *, capture: bool = False) -> str:
    args = ["psql", "-v", "ON_ERROR_STOP=1", "-d", database]
    if capture:
        args.extend(["-Atq"])
    return run_command(
        args,
        input_text=sql,
        capture=capture,
    )


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def sql_text_array(values: Iterable[str]) -> str:
    return "ARRAY[" + ", ".join(sql_literal(value) for value in values) + "]::text[]"


def sql_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def sql_column_list(columns: Iterable[str]) -> str:
    return ", ".join(sql_identifier(column) for column in columns)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{path} has no CSV header")
        return reader.fieldnames, list(reader)


def to_int(value: str | None) -> str:
    if value is None or value.strip() == "" or value.strip().lower() in {"nan", "na", "none"}:
        return r"\N"
    return str(int(float(value)))


def to_float(value: str | None) -> str:
    if value is None or value.strip() == "" or value.strip().lower() in {"nan", "na", "none"}:
        return r"\N"
    return str(float(value))


def to_text(value: str | None) -> str:
    if value in (None, ""):
        return r"\N"
    return value


def to_bool(value: str | None) -> str:
    if value in (None, ""):
        return r"\N"
    lowered = value.strip().lower()
    if lowered in {"true", "t", "1", "yes"}:
        return "true"
    if lowered in {"false", "f", "0", "no"}:
        return "false"
    raise ValueError(f"cannot parse boolean value: {value!r}")


def copy_csv(database: str, table: str, columns: list[str], rows: Iterable[list[str]]) -> None:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    for row in rows:
        writer.writerow(row)

    copy_sql = (
        f"COPY {table} ({', '.join(columns)}) "
        "FROM STDIN WITH (FORMAT csv, NULL '\\N');\n"
        f"{buffer.getvalue()}\\.\n"
    )
    run_psql(database, copy_sql)


def copy_upsert_csv(
    database: str,
    table: str,
    columns: list[str],
    rows: Iterable[list[str]],
    *,
    conflict_columns: list[str],
    source_path: str,
) -> None:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    for row in rows:
        writer.writerow(row)

    non_conflict_columns = [column for column in columns if column not in set(conflict_columns)]
    update_assignments = [
        f"{sql_identifier(column)} = EXCLUDED.{sql_identifier(column)}" for column in non_conflict_columns
    ]
    update_assignments.append("imported_at = now()")

    copy_sql = (
        "BEGIN;\n"
        f"DELETE FROM {table} WHERE source_path = {sql_literal(source_path)};\n"
        f"CREATE TEMP TABLE import_stage (LIKE {table} INCLUDING DEFAULTS) ON COMMIT DROP;\n"
        f"COPY import_stage ({sql_column_list(columns)}) "
        "FROM STDIN WITH (FORMAT csv, NULL '\\N');\n"
        f"{buffer.getvalue()}\\.\n"
        f"INSERT INTO {table} ({sql_column_list(columns)})\n"
        f"SELECT {sql_column_list(columns)} FROM import_stage\n"
        f"ON CONFLICT ({sql_column_list(conflict_columns)}) DO UPDATE SET\n"
        f"    {', '.join(update_assignments)};\n"
        "COMMIT;\n"
    )
    run_psql(database, copy_sql)


def ensure_database(database: str, owner_database: str = "postgres") -> None:
    exists = run_command(
        [
            "psql",
            "-Atqc",
            f"SELECT 1 FROM pg_database WHERE datname = {sql_literal(database)};",
            owner_database,
        ],
        capture=True,
    )
    if exists != "1":
        run_command(["createdb", database])


def init_schema(database: str) -> None:
    run_command(["psql", "-v", "ON_ERROR_STOP=1", "-d", database, "-f", str(SCHEMA_SQL)])


def register_csv(database: str, relative_path: Path, columns: list[str], rows: list[dict[str, str]]) -> int:
    absolute_path = REPO_ROOT / relative_path
    source_path = str(absolute_path)
    checksum = sha256_file(absolute_path)
    sql = f"""
INSERT INTO analysis.csv_files (
    source_path, relative_path, sha256, row_count, column_names, imported_at, importer
) VALUES (
    {sql_literal(source_path)},
    {sql_literal(str(relative_path))},
    {sql_literal(checksum)},
    {len(rows)},
    {sql_text_array(columns)},
    now(),
    {sql_literal(IMPORTER)}
)
ON CONFLICT (source_path) DO UPDATE SET
    relative_path = EXCLUDED.relative_path,
    sha256 = EXCLUDED.sha256,
    row_count = EXCLUDED.row_count,
    column_names = EXCLUDED.column_names,
    imported_at = now(),
    importer = EXCLUDED.importer
RETURNING id;
"""
    return int(run_psql(database, sql, capture=True))


def import_raw_rows(
    database: str,
    file_id: int,
    rows: list[dict[str, str]],
) -> None:
    run_psql(database, f"DELETE FROM analysis.csv_rows WHERE file_id = {file_id};")
    copy_rows = [
        [str(file_id), str(index), json.dumps(row, ensure_ascii=False)]
        for index, row in enumerate(rows, start=1)
    ]
    copy_csv(database, "analysis.csv_rows", ["file_id", "row_number", "row_data"], copy_rows)


def clear_raw_rows(database: str, file_id: int) -> None:
    run_psql(database, f"DELETE FROM analysis.csv_rows WHERE file_id = {file_id};")


def import_mapped_table(
    database: str,
    relative_path: Path,
    rows: list[dict[str, str]],
    *,
    table: str,
    mapping: list[ColumnSpec],
    conflict_columns: list[str],
) -> None:
    source_path = str(REPO_ROOT / relative_path)
    copy_rows = []
    for index, row in enumerate(rows, start=1):
        copy_rows.append(
            [converter(row.get(csv_column)) for csv_column, _db_column, converter in mapping]
            + [source_path, str(index)]
        )
    copy_upsert_csv(
        database,
        table,
        [db_column for _csv_column, db_column, _converter in mapping] + ["source_path", "source_row"],
        copy_rows,
        conflict_columns=conflict_columns,
        source_path=source_path,
    )


def import_basin_membership(database: str, relative_path: Path, rows: list[dict[str, str]]) -> None:
    source_path = str(REPO_ROOT / relative_path)
    copy_rows = []
    for index, row in enumerate(rows, start=1):
        copy_rows.append(
            [
                to_text(row.get("basin")),
                to_bool(row.get("in_broad_test")),
                to_bool(row.get("in_natural_test")),
                to_text(row.get("exclusive_cohort")),
                source_path,
                str(index),
            ]
        )
    copy_upsert_csv(
        database,
        "analysis.basin_membership",
        ["basin", "in_broad_test", "in_natural_test", "exclusive_cohort", "source_path", "source_row"],
        copy_rows,
        conflict_columns=["basin"],
        source_path=source_path,
    )


def import_basin_metrics(database: str, relative_path: Path, rows: list[dict[str, str]]) -> None:
    source_path = str(REPO_ROOT / relative_path)
    copy_rows = []
    for index, row in enumerate(rows, start=1):
        copy_rows.append(
            [
                to_text(row.get("model")),
                to_int(row.get("seed")),
                to_text(row.get("split")),
                to_int(row.get("epoch")),
                to_text(row.get("run_name")),
                to_text(row.get("source")),
                to_text(row.get("metric_path")),
                to_text(row.get("basin")),
                to_float(row.get("NSE")),
                to_float(row.get("KGE")),
                to_float(row.get("FHV")),
                to_float(row.get("Peak-Timing")),
                to_float(row.get("Peak-MAPE")),
                source_path,
                str(index),
            ]
        )
    copy_upsert_csv(
        database,
        "analysis.basin_metrics",
        [
            "model",
            "seed",
            "split",
            "epoch",
            "run_name",
            "source",
            "metric_path",
            "basin",
            "nse",
            "kge",
            "fhv",
            "peak_timing",
            "peak_mape",
            "source_path",
            "source_row",
        ],
        copy_rows,
        conflict_columns=["model", "seed", "split", "epoch", "basin"],
        source_path=source_path,
    )


def import_primary_deltas(database: str, relative_path: Path, rows: list[dict[str, str]]) -> None:
    source_path = str(REPO_ROOT / relative_path)
    copy_rows = []
    for index, row in enumerate(rows, start=1):
        copy_rows.append(
            [
                to_int(row.get("seed")),
                to_text(row.get("basin")),
                to_int(row.get("model1_epoch")),
                to_int(row.get("model2_epoch")),
                to_float(row.get("delta_NSE")),
                to_float(row.get("delta_KGE")),
                to_float(row.get("delta_FHV")),
                to_float(row.get("abs_FHV_reduction")),
                to_float(row.get("Peak_Timing_reduction")),
                to_float(row.get("Peak_MAPE_reduction")),
                source_path,
                str(index),
            ]
        )
    copy_upsert_csv(
        database,
        "analysis.primary_epoch_basin_deltas",
        [
            "seed",
            "basin",
            "model1_epoch",
            "model2_epoch",
            "delta_nse",
            "delta_kge",
            "delta_fhv",
            "abs_fhv_reduction",
            "peak_timing_reduction",
            "peak_mape_reduction",
            "source_path",
            "source_row",
        ],
        copy_rows,
        conflict_columns=["seed", "basin"],
        source_path=source_path,
    )


def import_extreme_rain_events(database: str, relative_path: Path, rows: list[dict[str, str]]) -> None:
    source_path = str(REPO_ROOT / relative_path)
    copy_rows = []
    for index, row in enumerate(rows, start=1):
        copy_rows.append(
            [
                to_text(row.get("split")),
                to_text(row.get("gauge_id")),
                to_text(row.get("event_id")),
                to_text(row.get("event_time_mode")),
                to_text(row.get("rolling_endpoint_start")),
                to_text(row.get("rolling_endpoint_peak")),
                to_text(row.get("rolling_severity_peak_time")),
                to_text(row.get("rolling_endpoint_end")),
                to_text(row.get("rolling_envelope_start")),
                to_text(row.get("rolling_envelope_end")),
                to_text(row.get("rain_start")),
                to_text(row.get("rain_peak")),
                to_text(row.get("rain_end")),
                to_float(row.get("wet_cluster_total_rain")),
                to_float(row.get("wet_cluster_peak_rainf")),
                to_float(row.get("wet_rain_threshold_mm_h")),
                to_float(row.get("wet_gap_hours")),
                to_int(row.get("water_year")),
                to_int(row.get("peak_month")),
                to_float(row.get("rain_event_n_hours")),
                to_float(row.get("rolling_endpoint_event_n_hours")),
                to_float(row.get("rain_coverage")),
                to_text(row.get("precip_reference_flag")),
                to_text(row.get("return_period_confidence_flag")),
                to_float(row.get("flood_record_years")),
                to_float(row.get("return_period_record_years")),
                to_text(row.get("temporal_relation")),
                to_float(row.get("max_prec_ari25_ratio")),
                to_text(row.get("peak_time_for_ari25_ratio")),
                to_float(row.get("dominant_duration_for_ari25h")),
                to_float(row.get("max_prec_ari25_1h_ratio")),
                to_float(row.get("max_prec_ari25_6h_ratio")),
                to_float(row.get("max_prec_ari25_24h_ratio")),
                to_float(row.get("max_prec_ari25_72h_ratio")),
                to_float(row.get("max_prec_ari50_ratio")),
                to_text(row.get("peak_time_for_ari50_ratio")),
                to_float(row.get("dominant_duration_for_ari50h")),
                to_float(row.get("max_prec_ari50_1h_ratio")),
                to_float(row.get("max_prec_ari50_6h_ratio")),
                to_float(row.get("max_prec_ari50_24h_ratio")),
                to_float(row.get("max_prec_ari50_72h_ratio")),
                to_float(row.get("max_prec_ari100_ratio")),
                to_text(row.get("peak_time_for_ari100_ratio")),
                to_float(row.get("dominant_duration_for_ari100h")),
                to_float(row.get("max_prec_ari100_1h_ratio")),
                to_float(row.get("max_prec_ari100_6h_ratio")),
                to_float(row.get("max_prec_ari100_24h_ratio")),
                to_float(row.get("max_prec_ari100_72h_ratio")),
                to_text(row.get("rain_cohort")),
                to_text(row.get("response_window_start")),
                to_text(row.get("response_window_end")),
                to_float(row.get("response_window_n_hours")),
                to_float(row.get("streamflow_response_coverage")),
                to_float(row.get("streamflow_q99_threshold")),
                to_float(row.get("obs_peak_to_flood_ari2")),
                to_float(row.get("obs_peak_to_flood_ari25")),
                to_float(row.get("obs_peak_to_flood_ari50")),
                to_float(row.get("obs_peak_to_flood_ari100")),
                to_float(row.get("observed_response_peak")),
                to_text(row.get("observed_response_peak_time")),
                to_float(row.get("response_lag_hours")),
                to_text(row.get("response_class")),
                to_text(row.get("response_skipped_reason")),
                to_float(row.get("response_lag_from_rain_peak_h")),
                to_float(row.get("response_lag_from_rain_start_h")),
                to_text(row.get("temporal_alignment_flag")),
                to_float(row.get("flood_ari2")),
                to_float(row.get("flood_ari25")),
                to_float(row.get("flood_ari50")),
                to_float(row.get("flood_ari100")),
                to_text(row.get("storm_group_id")),
                source_path,
                str(index),
            ]
        )
    copy_upsert_csv(
        database,
        "analysis.extreme_rain_events",
        [
            "split",
            "gauge_id",
            "event_id",
            "event_time_mode",
            "rolling_endpoint_start",
            "rolling_endpoint_peak",
            "rolling_severity_peak_time",
            "rolling_endpoint_end",
            "rolling_envelope_start",
            "rolling_envelope_end",
            "rain_start",
            "rain_peak",
            "rain_end",
            "wet_cluster_total_rain",
            "wet_cluster_peak_rainf",
            "wet_rain_threshold_mm_h",
            "wet_gap_hours",
            "water_year",
            "peak_month",
            "rain_event_n_hours",
            "rolling_endpoint_event_n_hours",
            "rain_coverage",
            "precip_reference_flag",
            "return_period_confidence_flag",
            "flood_record_years",
            "return_period_record_years",
            "temporal_relation",
            "max_prec_ari25_ratio",
            "peak_time_for_ari25_ratio",
            "dominant_duration_for_ari25h",
            "max_prec_ari25_1h_ratio",
            "max_prec_ari25_6h_ratio",
            "max_prec_ari25_24h_ratio",
            "max_prec_ari25_72h_ratio",
            "max_prec_ari50_ratio",
            "peak_time_for_ari50_ratio",
            "dominant_duration_for_ari50h",
            "max_prec_ari50_1h_ratio",
            "max_prec_ari50_6h_ratio",
            "max_prec_ari50_24h_ratio",
            "max_prec_ari50_72h_ratio",
            "max_prec_ari100_ratio",
            "peak_time_for_ari100_ratio",
            "dominant_duration_for_ari100h",
            "max_prec_ari100_1h_ratio",
            "max_prec_ari100_6h_ratio",
            "max_prec_ari100_24h_ratio",
            "max_prec_ari100_72h_ratio",
            "rain_cohort",
            "response_window_start",
            "response_window_end",
            "response_window_n_hours",
            "streamflow_response_coverage",
            "streamflow_q99_threshold",
            "obs_peak_to_flood_ari2",
            "obs_peak_to_flood_ari25",
            "obs_peak_to_flood_ari50",
            "obs_peak_to_flood_ari100",
            "observed_response_peak",
            "observed_response_peak_time",
            "response_lag_hours",
            "response_class",
            "response_skipped_reason",
            "response_lag_from_rain_peak_h",
            "response_lag_from_rain_start_h",
            "temporal_alignment_flag",
            "flood_ari2",
            "flood_ari25",
            "flood_ari50",
            "flood_ari100",
            "storm_group_id",
            "source_path",
            "source_row",
        ],
        copy_rows,
        conflict_columns=["gauge_id", "event_id"],
        source_path=source_path,
    )


def import_basin_static_attributes(database: str, relative_path: Path, rows: list[dict[str, str]]) -> None:
    import_mapped_table(
        database,
        relative_path,
        rows,
        table="analysis.basin_static_attributes",
        conflict_columns=["gauge_id"],
        mapping=[
            ("gauge_id", "gauge_id", to_text),
            ("area", "area", to_float),
            ("HUC02", "huc02", to_text),
            ("STATE", "state", to_text),
            ("slope", "slope", to_float),
            ("aridity", "aridity", to_float),
            ("snow_fraction", "snow_fraction", to_float),
            ("soil_depth", "soil_depth", to_float),
            ("permeability", "permeability", to_float),
            ("baseflow_index", "baseflow_index", to_float),
            ("forest_fraction", "forest_fraction", to_float),
        ],
    )


def import_basin_flood_generation(database: str, relative_path: Path, rows: list[dict[str, str]]) -> None:
    import_mapped_table(
        database,
        relative_path,
        rows,
        table="analysis.basin_flood_generation",
        conflict_columns=["gauge_id"],
        mapping=[
            ("gauge_id", "gauge_id", to_text),
            ("gauge_name", "gauge_name", to_text),
            ("state", "state", to_text),
            ("huc02", "huc02", to_text),
            ("drain_sqkm_attr", "drain_sqkm_attr", to_float),
            ("area", "area", to_float),
            ("snow_fraction", "snow_fraction", to_float),
            ("event_count", "event_count", to_int),
            ("dominant_flood_generation_type", "dominant_flood_generation_type", to_text),
            ("dominant_type_if_any", "dominant_type_if_any", to_text),
            ("dominant_type_share", "dominant_type_share", to_float),
            ("recent_precipitation_count", "recent_precipitation_count", to_int),
            ("antecedent_precipitation_count", "antecedent_precipitation_count", to_int),
            ("snowmelt_or_rain_on_snow_count", "snowmelt_or_rain_on_snow_count", to_int),
            ("uncertain_high_flow_candidate_count", "uncertain_high_flow_candidate_count", to_int),
            ("recent_precipitation_share", "recent_precipitation_share", to_float),
            ("antecedent_precipitation_share", "antecedent_precipitation_share", to_float),
            ("snowmelt_or_rain_on_snow_share", "snowmelt_or_rain_on_snow_share", to_float),
            ("uncertain_high_flow_candidate_share", "uncertain_high_flow_candidate_share", to_float),
            ("low_confidence_event_share", "low_confidence_event_share", to_float),
            ("mean_recent_precipitation_strength", "mean_recent_precipitation_strength", to_float),
            ("mean_antecedent_precipitation_strength", "mean_antecedent_precipitation_strength", to_float),
            ("mean_snowmelt_or_rain_on_snow_strength", "mean_snowmelt_or_rain_on_snow_strength", to_float),
        ],
    )


def import_basin_event_response(database: str, relative_path: Path, rows: list[dict[str, str]]) -> None:
    import_mapped_table(
        database,
        relative_path,
        rows,
        table="analysis.basin_event_response",
        conflict_columns=["gauge_id"],
        mapping=[
            ("gauge_id", "gauge_id", to_text),
            ("gauge_name", "gauge_name", to_text),
            ("state", "state", to_text),
            ("huc02", "huc02", to_text),
            ("drain_sqkm_attr", "drain_sqkm_attr", to_float),
            ("area", "area", to_float),
            ("snow_fraction", "snow_fraction", to_float),
            ("obs_years_usable", "obs_years_usable", to_float),
            ("processing_status", "processing_status", to_text),
            ("selected_threshold_quantile", "selected_threshold_quantile", to_text),
            ("selected_threshold_value", "selected_threshold_value", to_float),
            ("q99_event_count", "q99_event_count", to_int),
            ("q98_event_count", "q98_event_count", to_int),
            ("q95_event_count", "q95_event_count", to_int),
            ("event_count", "event_count", to_int),
            ("flood_like_ge_2yr_proxy_event_count", "flood_like_ge_2yr_proxy_event_count", to_int),
            ("high_flow_below_2yr_proxy_event_count", "high_flow_below_2yr_proxy_event_count", to_int),
            ("high_flow_candidate_unrated_event_count", "high_flow_candidate_unrated_event_count", to_int),
            ("annual_peak_years", "annual_peak_years", to_int),
            ("unit_area_peak_median", "unit_area_peak_median", to_float),
            ("unit_area_peak_p90", "unit_area_peak_p90", to_float),
            ("q99_event_frequency", "q99_event_frequency", to_float),
            ("rbi", "rbi", to_float),
            ("rising_time_median_hours", "rising_time_median_hours", to_float),
            ("event_duration_median_hours", "event_duration_median_hours", to_float),
            ("event_runoff_coefficient_median", "event_runoff_coefficient_median", to_float),
            ("annual_peak_unit_area_median", "annual_peak_unit_area_median", to_float),
            ("annual_peak_unit_area_p90", "annual_peak_unit_area_p90", to_float),
            ("return_period_method", "return_period_method", to_text),
            ("min_annual_coverage", "min_annual_coverage", to_float),
            ("flood_ari_source", "flood_ari_source", to_text),
            ("prec_ari_source", "prec_ari_source", to_text),
            ("flood_record_years", "flood_record_years", to_float),
            ("return_period_record_years", "return_period_record_years", to_float),
            ("return_period_confidence_flag", "return_period_confidence_flag", to_text),
            ("flood_ari2", "flood_ari2", to_float),
            ("flood_ari5", "flood_ari5", to_float),
            ("flood_ari10", "flood_ari10", to_float),
            ("flood_ari25", "flood_ari25", to_float),
            ("flood_ari50", "flood_ari50", to_float),
            ("flood_ari100", "flood_ari100", to_float),
            ("prec_record_years_1h", "prec_record_years_1h", to_float),
            ("prec_ari2_1h", "prec_ari2_1h", to_float),
            ("prec_ari5_1h", "prec_ari5_1h", to_float),
            ("prec_ari10_1h", "prec_ari10_1h", to_float),
            ("prec_ari25_1h", "prec_ari25_1h", to_float),
            ("prec_ari50_1h", "prec_ari50_1h", to_float),
            ("prec_ari100_1h", "prec_ari100_1h", to_float),
            ("prec_record_years_6h", "prec_record_years_6h", to_float),
            ("prec_ari2_6h", "prec_ari2_6h", to_float),
            ("prec_ari5_6h", "prec_ari5_6h", to_float),
            ("prec_ari10_6h", "prec_ari10_6h", to_float),
            ("prec_ari25_6h", "prec_ari25_6h", to_float),
            ("prec_ari50_6h", "prec_ari50_6h", to_float),
            ("prec_ari100_6h", "prec_ari100_6h", to_float),
            ("prec_record_years_24h", "prec_record_years_24h", to_float),
            ("prec_ari2_24h", "prec_ari2_24h", to_float),
            ("prec_ari5_24h", "prec_ari5_24h", to_float),
            ("prec_ari10_24h", "prec_ari10_24h", to_float),
            ("prec_ari25_24h", "prec_ari25_24h", to_float),
            ("prec_ari50_24h", "prec_ari50_24h", to_float),
            ("prec_ari100_24h", "prec_ari100_24h", to_float),
            ("prec_record_years_72h", "prec_record_years_72h", to_float),
            ("prec_ari2_72h", "prec_ari2_72h", to_float),
            ("prec_ari5_72h", "prec_ari5_72h", to_float),
            ("prec_ari10_72h", "prec_ari10_72h", to_float),
            ("prec_ari25_72h", "prec_ari25_72h", to_float),
            ("prec_ari50_72h", "prec_ari50_72h", to_float),
            ("prec_ari100_72h", "prec_ari100_72h", to_float),
        ],
    )


def import_basin_event_regime(database: str, relative_path: Path, rows: list[dict[str, str]]) -> None:
    import_mapped_table(
        database,
        relative_path,
        rows,
        table="analysis.basin_event_regime",
        conflict_columns=["gauge_id"],
        mapping=[
            ("gauge_id", "gauge_id", to_text),
            ("cluster_0_share", "cluster_0_share", to_float),
            ("cluster_1_share", "cluster_1_share", to_float),
            ("cluster_2_share", "cluster_2_share", to_float),
            ("event_count", "event_count", to_int),
            ("top1_share", "top1_share", to_float),
            ("top2_share", "top2_share", to_float),
            ("cluster_entropy", "cluster_entropy", to_float),
            ("top1_cluster", "top1_cluster", to_int),
            ("ml_dominant_label", "ml_dominant_label", to_text),
            ("ml_map_label", "ml_map_label", to_text),
            ("gauge_name", "gauge_name", to_text),
            ("state", "state", to_text),
            ("huc02", "huc02", to_text),
            ("drain_sqkm_attr", "drain_sqkm_attr", to_float),
            ("event_count_event", "event_count_event", to_int),
            ("dominant_flood_generation_type", "dominant_flood_generation_type", to_text),
            ("dominant_type_share", "dominant_type_share", to_float),
            ("huc02_name", "huc02_name", to_text),
        ],
    )


def import_probabilistic_pinball(database: str, relative_path: Path, rows: list[dict[str, str]]) -> None:
    import_mapped_table(
        database,
        relative_path,
        rows,
        table="analysis.probabilistic_pinball",
        conflict_columns=["comparison", "seed", "model1_epoch", "model2_epoch", "stratum", "quantile"],
        mapping=[
            ("comparison", "comparison", to_text),
            ("seed", "seed", to_int),
            ("model1_epoch", "model1_epoch", to_int),
            ("model2_epoch", "model2_epoch", to_int),
            ("stratum", "stratum", to_text),
            ("stratum_label", "stratum_label", to_text),
            ("quantile", "quantile", to_text),
            ("nominal_tau", "nominal_tau", to_float),
            ("n_rows", "n_rows", to_int),
            ("n_basins", "n_basins", to_int),
            ("mean_obs", "mean_obs", to_float),
            ("median_obs", "median_obs", to_float),
            ("mean_pinball", "mean_pinball", to_float),
            ("median_pinball", "median_pinball", to_float),
            ("mean_aqs", "mean_aqs", to_float),
            ("median_aqs", "median_aqs", to_float),
            ("mean_pinball_pct_mean_obs", "mean_pinball_pct_mean_obs", to_float),
            ("median_pinball_pct_median_obs", "median_pinball_pct_median_obs", to_float),
        ],
    )


def import_probabilistic_calibration(database: str, relative_path: Path, rows: list[dict[str, str]]) -> None:
    import_mapped_table(
        database,
        relative_path,
        rows,
        table="analysis.probabilistic_calibration",
        conflict_columns=[
            "comparison",
            "seed",
            "model1_epoch",
            "model2_epoch",
            "stratum",
            "quantile",
            "calibration_context",
        ],
        mapping=[
            ("comparison", "comparison", to_text),
            ("seed", "seed", to_int),
            ("model1_epoch", "model1_epoch", to_int),
            ("model2_epoch", "model2_epoch", to_int),
            ("stratum", "stratum", to_text),
            ("stratum_label", "stratum_label", to_text),
            ("quantile", "quantile", to_text),
            ("nominal_tau", "nominal_tau", to_float),
            ("n_rows", "n_rows", to_int),
            ("n_basins", "n_basins", to_int),
            ("mean_obs", "mean_obs", to_float),
            ("median_obs", "median_obs", to_float),
            ("empirical_coverage", "empirical_coverage", to_float),
            ("coverage_error", "coverage_error", to_float),
            ("abs_coverage_error", "abs_coverage_error", to_float),
            ("undercoverage_error", "undercoverage_error", to_float),
            ("overcoverage_error", "overcoverage_error", to_float),
            ("underestimation_fraction", "underestimation_fraction", to_float),
            ("calibration_context", "calibration_context", to_text),
        ],
    )


def import_probabilistic_tail_spread(database: str, relative_path: Path, rows: list[dict[str, str]]) -> None:
    import_mapped_table(
        database,
        relative_path,
        rows,
        table="analysis.probabilistic_tail_spread",
        conflict_columns=["comparison", "seed", "model1_epoch", "model2_epoch", "stratum"],
        mapping=[
            ("comparison", "comparison", to_text),
            ("seed", "seed", to_int),
            ("model1_epoch", "model1_epoch", to_int),
            ("model2_epoch", "model2_epoch", to_int),
            ("stratum", "stratum", to_text),
            ("stratum_label", "stratum_label", to_text),
            ("n_rows", "n_rows", to_int),
            ("n_basins", "n_basins", to_int),
            ("mean_obs", "mean_obs", to_float),
            ("median_obs", "median_obs", to_float),
            ("mean_q90_minus_q50", "mean_q90_minus_q50", to_float),
            ("median_q90_minus_q50", "median_q90_minus_q50", to_float),
            ("mean_q90_minus_q50_pct_obs", "mean_q90_minus_q50_pct_obs", to_float),
            ("median_q90_minus_q50_pct_obs", "median_q90_minus_q50_pct_obs", to_float),
            ("mean_q95_minus_q90", "mean_q95_minus_q90", to_float),
            ("median_q95_minus_q90", "median_q95_minus_q90", to_float),
            ("mean_q95_minus_q90_pct_obs", "mean_q95_minus_q90_pct_obs", to_float),
            ("median_q95_minus_q90_pct_obs", "median_q95_minus_q90_pct_obs", to_float),
            ("mean_q99_minus_q95", "mean_q99_minus_q95", to_float),
            ("median_q99_minus_q95", "median_q99_minus_q95", to_float),
            ("mean_q99_minus_q95_pct_obs", "mean_q99_minus_q95_pct_obs", to_float),
            ("median_q99_minus_q95_pct_obs", "median_q99_minus_q95_pct_obs", to_float),
            ("mean_q99_minus_q50", "mean_q99_minus_q50", to_float),
            ("median_q99_minus_q50", "median_q99_minus_q50", to_float),
            ("mean_q99_minus_q50_pct_obs", "mean_q99_minus_q50_pct_obs", to_float),
            ("median_q99_minus_q50_pct_obs", "median_q99_minus_q50_pct_obs", to_float),
            ("q90_lt_q50_rows", "q90_lt_q50_rows", to_int),
            ("q95_lt_q90_rows", "q95_lt_q90_rows", to_int),
            ("q99_lt_q95_rows", "q99_lt_q95_rows", to_int),
        ],
    )


def import_nws_flood_stage_coverage(database: str, relative_path: Path, rows: list[dict[str, str]]) -> None:
    import_mapped_table(
        database,
        relative_path,
        rows,
        table="analysis.nws_flood_stage_coverage",
        conflict_columns=["usgs_id"],
        mapping=[
            ("usgs_id", "usgs_id", to_text),
            ("nws_lid", "nws_lid", to_text),
            ("county_fips", "county_fips", to_text),
            ("minor_stage_ft", "minor_stage_ft", to_float),
            ("moderate_stage_ft", "moderate_stage_ft", to_float),
            ("major_stage_ft", "major_stage_ft", to_float),
            ("minor_discharge_cms", "minor_discharge_cms", to_float),
            ("moderate_discharge_cms", "moderate_discharge_cms", to_float),
            ("major_discharge_cms", "major_discharge_cms", to_float),
            ("coverage_status", "coverage_status", to_text),
        ],
    )


def import_nws_coverage_bias(database: str, relative_path: Path, rows: list[dict[str, str]]) -> None:
    import_mapped_table(
        database,
        relative_path,
        rows,
        table="analysis.nws_coverage_bias",
        conflict_columns=["attribute"],
        mapping=[
            ("attribute", "attribute", to_text),
            ("covered_n", "covered_n", to_int),
            ("missing_n", "missing_n", to_int),
            ("covered_median", "covered_median", to_float),
            ("missing_median", "missing_median", to_float),
            ("ks_stat", "ks_stat", to_float),
            ("ks_pvalue", "ks_pvalue", to_float),
        ],
    )


def import_drbc_confirmed_flood_events(database: str, relative_path: Path, rows: list[dict[str, str]]) -> None:
    import_mapped_table(
        database,
        relative_path,
        rows,
        table="analysis.drbc_confirmed_flood_events",
        conflict_columns=["usgs_id", "peak_time"],
        mapping=[
            ("usgs_id", "usgs_id", to_text),
            ("peak_time", "peak_time", to_text),
            ("peak_discharge_cms", "peak_discharge_cms", to_float),
            ("flood_tier", "flood_tier", to_text),
            ("tier_limited", "tier_limited", to_bool),
            ("noaa_corroborated", "noaa_corroborated", to_bool),
            ("period", "period", to_text),
            ("forcing_coverage_min", "forcing_coverage_min", to_float),
        ],
    )


def import_drbc_confirmed_flood_performance(database: str, relative_path: Path, rows: list[dict[str, str]]) -> None:
    import_mapped_table(
        database,
        relative_path,
        rows,
        table="analysis.drbc_confirmed_flood_performance",
        conflict_columns=["usgs_id", "peak_time", "model", "seed", "quantile"],
        mapping=[
            ("usgs_id", "usgs_id", to_text),
            ("peak_time", "peak_time", to_text),
            ("model", "model", to_text),
            ("seed", "seed", to_int),
            ("quantile", "quantile", to_text),
            ("obs_peak_cms", "obs_peak_cms", to_float),
            ("pred_peak_cms", "pred_peak_cms", to_float),
            ("peak_under_deficit", "peak_under_deficit", to_float),
            ("is_underestimate", "is_underestimate", to_bool),
            ("exceeds_minor_stage", "exceeds_minor_stage", to_bool),
            ("event_nrmse", "event_nrmse", to_float),
            ("flood_tier", "flood_tier", to_text),
            ("noaa_corroborated", "noaa_corroborated", to_bool),
        ],
    )


def import_confirmed_flood_timeseries(database: str, relative_path: Path, rows: list[dict[str, str]]) -> None:
    import_mapped_table(
        database,
        relative_path,
        rows,
        table="analysis.confirmed_flood_timeseries",
        conflict_columns=["event_id", "seed", "datetime"],
        mapping=[
            ("event_id", "event_id", to_text),
            ("seed", "seed", to_int),
            ("basin", "basin", to_text),
            ("model1_epoch", "model1_epoch", to_int),
            ("model2_epoch", "model2_epoch", to_int),
            ("peak_time", "peak_time", to_text),
            ("datetime", "datetime", to_text),
            ("in_eval_window", "in_eval_window", to_bool),
            ("obs", "obs", to_float),
            ("model1", "model1", to_float),
            ("model2_q50_result", "model2_q50_result", to_float),
            ("q50", "q50", to_float),
            ("q90", "q90", to_float),
            ("q95", "q95", to_float),
            ("q99", "q99", to_float),
            ("q90_minus_q50", "q90_minus_q50", to_float),
            ("q95_minus_q90", "q95_minus_q90", to_float),
            ("q99_minus_q95", "q99_minus_q95", to_float),
            ("q99_minus_q50", "q99_minus_q50", to_float),
            ("model2_q50_minus_model1", "model2_q50_minus_model1", to_float),
            ("flood_tier", "flood_tier", to_text),
            ("noaa_corroborated", "noaa_corroborated", to_bool),
            ("period", "period", to_text),
        ],
    )


def import_expanded_drbc_timeseries(database: str, relative_path: Path, rows: list[dict[str, str]]) -> None:
    import_mapped_table(
        database, relative_path, rows,
        table="analysis.expanded_drbc_timeseries",
        conflict_columns=["seed", "basin", "datetime"],
        mapping=[
            ("seed", "seed", to_int),
            ("basin", "basin", to_text),
            ("model1_epoch", "model1_epoch", to_int),
            ("model2_epoch", "model2_epoch", to_int),
            ("datetime", "datetime", to_text),
            ("obs", "obs", to_float),
            ("model1", "model1", to_float),
            ("model2_q50_result", "model2_q50_result", to_float),
            ("q50", "q50", to_float),
            ("q90", "q90", to_float),
            ("q95", "q95", to_float),
            ("q99", "q99", to_float),
            ("q90_minus_q50", "q90_minus_q50", to_float),
            ("q95_minus_q90", "q95_minus_q90", to_float),
            ("q99_minus_q95", "q99_minus_q95", to_float),
            ("q99_minus_q50", "q99_minus_q50", to_float),
            ("model2_q50_minus_model1", "model2_q50_minus_model1", to_float),
        ],
    )


def import_return_period_references(database: str, relative_path: Path, rows: list[dict[str, str]]) -> None:
    import_mapped_table(
        database, relative_path, rows,
        table="analysis.return_period_references",
        conflict_columns=["gauge_id"],
        mapping=[
            ("gauge_id", "gauge_id", to_text),
            ("gauge_name", "gauge_name", to_text),
            ("state", "state", to_text),
            ("huc02", "huc02", to_text),
            ("area", "area", to_float),
            ("drain_sqkm_attr", "drain_sqkm_attr", to_float),
            ("snow_fraction", "snow_fraction", to_float),
            ("return_period_method", "return_period_method", to_text),
            ("min_annual_coverage", "min_annual_coverage", to_float),
            ("flood_ari_source", "flood_ari_source", to_text),
            ("prec_ari_source", "prec_ari_source", to_text),
            ("flood_record_years", "flood_record_years", to_float),
            ("return_period_record_years", "return_period_record_years", to_float),
            ("return_period_confidence_flag", "return_period_confidence_flag", to_text),
            ("flood_ari2", "flood_ari2", to_float),
            ("flood_ari5", "flood_ari5", to_float),
            ("flood_ari10", "flood_ari10", to_float),
            ("flood_ari25", "flood_ari25", to_float),
            ("flood_ari50", "flood_ari50", to_float),
            ("flood_ari100", "flood_ari100", to_float),
            ("prec_record_years_1h", "prec_record_years_1h", to_float),
            ("prec_ari2_1h", "prec_ari2_1h", to_float), ("prec_ari5_1h", "prec_ari5_1h", to_float),
            ("prec_ari10_1h", "prec_ari10_1h", to_float), ("prec_ari25_1h", "prec_ari25_1h", to_float),
            ("prec_ari50_1h", "prec_ari50_1h", to_float), ("prec_ari100_1h", "prec_ari100_1h", to_float),
            ("prec_record_years_6h", "prec_record_years_6h", to_float),
            ("prec_ari2_6h", "prec_ari2_6h", to_float), ("prec_ari5_6h", "prec_ari5_6h", to_float),
            ("prec_ari10_6h", "prec_ari10_6h", to_float), ("prec_ari25_6h", "prec_ari25_6h", to_float),
            ("prec_ari50_6h", "prec_ari50_6h", to_float), ("prec_ari100_6h", "prec_ari100_6h", to_float),
            ("prec_record_years_24h", "prec_record_years_24h", to_float),
            ("prec_ari2_24h", "prec_ari2_24h", to_float), ("prec_ari5_24h", "prec_ari5_24h", to_float),
            ("prec_ari10_24h", "prec_ari10_24h", to_float), ("prec_ari25_24h", "prec_ari25_24h", to_float),
            ("prec_ari50_24h", "prec_ari50_24h", to_float), ("prec_ari100_24h", "prec_ari100_24h", to_float),
            ("prec_record_years_72h", "prec_record_years_72h", to_float),
            ("prec_ari2_72h", "prec_ari2_72h", to_float), ("prec_ari5_72h", "prec_ari5_72h", to_float),
            ("prec_ari10_72h", "prec_ari10_72h", to_float), ("prec_ari25_72h", "prec_ari25_72h", to_float),
            ("prec_ari50_72h", "prec_ari50_72h", to_float), ("prec_ari100_72h", "prec_ari100_72h", to_float),
        ],
    )


def import_extreme_rain_cohort_predictor_summary(database: str, relative_path: Path, rows: list[dict[str, str]]) -> None:
    import_mapped_table(
        database, relative_path, rows,
        table="analysis.extreme_rain_cohort_predictor_summary",
        conflict_columns=["comparison", "stress_group", "response_class", "seed", "epoch_label", "predictor"],
        mapping=[
            ("comparison", "comparison", to_text),
            ("stress_group", "stress_group", to_text),
            ("response_class", "response_class", to_text),
            ("seed", "seed", to_int),
            ("epoch_label", "epoch_label", to_text),
            ("model1_epoch", "model1_epoch", to_int),
            ("model2_epoch", "model2_epoch", to_int),
            ("predictor", "predictor", to_text),
            ("predictor_label", "predictor_label", to_text),
            ("n_events", "n_events", to_int),
            ("n_basins", "n_basins", to_int),
            ("median_observed_peak", "median_observed_peak", to_float),
            ("underestimation_fraction_at_observed_peak", "underestimation_fraction_at_observed_peak", to_float),
            ("mean_obs_peak_rel_error_pct", "mean_obs_peak_rel_error_pct", to_float),
            ("median_obs_peak_rel_error_pct", "median_obs_peak_rel_error_pct", to_float),
            ("mean_obs_peak_under_deficit_pct", "mean_obs_peak_under_deficit_pct", to_float),
            ("median_obs_peak_under_deficit_pct", "median_obs_peak_under_deficit_pct", to_float),
            ("mean_event_nrmse_pct", "mean_event_nrmse_pct", to_float),
            ("median_event_nrmse_pct", "median_event_nrmse_pct", to_float),
            ("mean_threshold_exceedance_recall", "mean_threshold_exceedance_recall", to_float),
            ("median_threshold_exceedance_recall", "median_threshold_exceedance_recall", to_float),
            ("median_pred_window_peak_to_flood_ari25", "median_pred_window_peak_to_flood_ari25", to_float),
            ("median_pred_window_peak_to_flood_ari50", "median_pred_window_peak_to_flood_ari50", to_float),
            ("median_pred_window_peak_to_flood_ari100", "median_pred_window_peak_to_flood_ari100", to_float),
            ("fraction_pred_crosses_flood_ari25", "fraction_pred_crosses_flood_ari25", to_float),
            ("fraction_pred_crosses_flood_ari50", "fraction_pred_crosses_flood_ari50", to_float),
            ("fraction_pred_crosses_flood_ari100", "fraction_pred_crosses_flood_ari100", to_float),
        ],
    )


def import_extreme_rain_paired_delta_summary(database: str, relative_path: Path, rows: list[dict[str, str]]) -> None:
    import_mapped_table(
        database, relative_path, rows,
        table="analysis.extreme_rain_paired_delta_summary",
        conflict_columns=["seed", "epoch_label", "stratification", "stratum", "predictor"],
        mapping=[
            ("seed", "seed", to_int),
            ("epoch_label", "epoch_label", to_text),
            ("model1_epoch", "model1_epoch", to_int),
            ("model2_epoch", "model2_epoch", to_int),
            ("stratification", "stratification", to_text),
            ("stratum", "stratum", to_text),
            ("predictor", "predictor", to_text),
            ("predictor_label", "predictor_label", to_text),
            ("n_events", "n_events", to_int),
            ("n_basins", "n_basins", to_int),
            ("median_delta_NSE", "median_delta_nse", to_float),
            ("mean_delta_NSE", "mean_delta_nse", to_float),
            ("median_delta_KGE", "median_delta_kge", to_float),
            ("mean_delta_KGE", "mean_delta_kge", to_float),
            ("median_delta_FHV", "median_delta_fhv", to_float),
            ("mean_delta_FHV", "mean_delta_fhv", to_float),
        ],
    )


def import_csv(database: str, relative_path: Path, *, store_raw: bool = False) -> None:
    absolute_path = REPO_ROOT / relative_path
    if not absolute_path.exists():
        raise FileNotFoundError(absolute_path)

    columns, rows = read_csv(absolute_path)
    file_id = register_csv(database, relative_path, columns, rows)
    if store_raw:
        import_raw_rows(database, file_id, rows)
    else:
        clear_raw_rows(database, file_id)

    if relative_path == BASIN_MEMBERSHIP:
        import_basin_membership(database, relative_path, rows)
    elif relative_path == BASIN_METRICS:
        import_basin_metrics(database, relative_path, rows)
    elif relative_path == PRIMARY_DELTAS:
        import_primary_deltas(database, relative_path, rows)
    elif relative_path == EXTREME_RAIN_EVENTS:
        import_extreme_rain_events(database, relative_path, rows)
    elif relative_path == BASIN_STATIC_ATTRIBUTES:
        import_basin_static_attributes(database, relative_path, rows)
    elif relative_path == BASIN_FLOOD_GENERATION:
        import_basin_flood_generation(database, relative_path, rows)
    elif relative_path == BASIN_EVENT_RESPONSE:
        import_basin_event_response(database, relative_path, rows)
    elif relative_path == BASIN_EVENT_REGIME:
        import_basin_event_regime(database, relative_path, rows)
    elif relative_path == PROB_PINBALL:
        import_probabilistic_pinball(database, relative_path, rows)
    elif relative_path == PROB_CALIBRATION:
        import_probabilistic_calibration(database, relative_path, rows)
    elif relative_path == PROB_TAIL_SPREAD:
        import_probabilistic_tail_spread(database, relative_path, rows)
    elif relative_path == NWS_FLOOD_STAGE_COVERAGE:
        import_nws_flood_stage_coverage(database, relative_path, rows)
    elif relative_path == NWS_COVERAGE_BIAS:
        import_nws_coverage_bias(database, relative_path, rows)
    elif relative_path == DRBC_CONFIRMED_FLOOD_EVENTS:
        import_drbc_confirmed_flood_events(database, relative_path, rows)
    elif relative_path == DRBC_CONFIRMED_FLOOD_PERFORMANCE:
        import_drbc_confirmed_flood_performance(database, relative_path, rows)
    elif relative_path in (
        CONFIRMED_FLOOD_TIMESERIES_SEED111,
        CONFIRMED_FLOOD_TIMESERIES_SEED222,
        CONFIRMED_FLOOD_TIMESERIES_SEED444,
    ):
        import_confirmed_flood_timeseries(database, relative_path, rows)
    elif relative_path == EXPANDED_DRBC_BASIN_METRICS:
        import_basin_metrics(database, relative_path, rows)
    elif relative_path == EXPANDED_DRBC_EXTREME_RAIN_EVENTS:
        import_extreme_rain_events(database, relative_path, rows)
    elif relative_path in (
        EXPANDED_DRBC_TIMESERIES_SEED111,
        EXPANDED_DRBC_TIMESERIES_SEED222,
        EXPANDED_DRBC_TIMESERIES_SEED444,
    ):
        import_expanded_drbc_timeseries(database, relative_path, rows)
    elif relative_path == RETURN_PERIOD_REFERENCES:
        import_return_period_references(database, relative_path, rows)
    elif relative_path == EXTREME_RAIN_COHORT_PREDICTOR_SUMMARY_EXPANDED:
        import_extreme_rain_cohort_predictor_summary(database, relative_path, rows)
    elif relative_path == EXTREME_RAIN_PAIRED_DELTA_SUMMARY_EXPANDED:
        import_extreme_rain_paired_delta_summary(database, relative_path, rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default="camels", help="PostgreSQL database name.")
    parser.add_argument(
        "--skip-create-db",
        action="store_true",
        help="Do not create the database if it does not exist.",
    )
    parser.add_argument(
        "--skip-schema",
        action="store_true",
        help="Do not apply init_camels_analysis_db.sql before importing.",
    )
    parser.add_argument(
        "--store-raw",
        action="store_true",
        help="csv_rows에 raw jsonb 데이터를 저장한다. 기본값은 metadata와 typed table만 갱신한다.",
    )
    parser.add_argument(
        "csv_paths",
        nargs="*",
        type=Path,
        help="CSV paths relative to the repository root. Defaults to the core CAMELS analysis tables.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = args.csv_paths or DEFAULT_CSVS

    if not args.skip_create_db:
        ensure_database(args.database)
    if not args.skip_schema:
        init_schema(args.database)

    for path in paths:
        relative_path = path if not path.is_absolute() else path.relative_to(REPO_ROOT)
        import_csv(args.database, relative_path, store_raw=args.store_raw)
        print(f"imported {relative_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
