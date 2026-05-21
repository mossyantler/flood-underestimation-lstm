#!/usr/bin/env bash
# Extreme rain stress test for expanded observed DRBC test basins (85 basins).
# Reuses existing subset300 checkpoints — no retraining.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT_DIR"

OUTPUT_ROOT="${OUTPUT_ROOT:-output/model_analysis/expanded/extreme_rain/expanded_drbc}"
LOG_DIR="${LOG_DIR:-logs}"
DEVICE="${DEVICE:-cuda:0}"
SEEDS="${SEEDS:-111 222 444}"
EPOCH_MODE="${EPOCH_MODE:-primary}"
EVENT_TIME_MODE="${EVENT_TIME_MODE:-wet_footprint}"

DATA_DIR="${DATA_DIR:-data/CAMELSH_generic/drbc_expanded_observed_test/time_series}"
DATA_ROOT="${DATA_ROOT:-data/CAMELSH_generic/drbc_expanded_observed_test}"
SPLIT_DIR="${SPLIT_DIR:-configs/basin_splits/drbc_expanded_observed_test}"
TEST_BASIN_FILE="${TEST_BASIN_FILE:-configs/basin_splits/drbc_expanded_observed_test/test.txt}"

RETURN_PERIOD_CSV="${RETURN_PERIOD_CSV:-output/basin/all/analysis/return_period/tables/return_period_reference_table_with_drbc_expanded85.csv}"
BLOCKS_CSV="${BLOCKS_CSV:-$OUTPUT_ROOT/exposure/inference_blocks.csv}"
COHORT_CSV="${COHORT_CSV:-$OUTPUT_ROOT/exposure/drbc_historical_stress_cohort.csv}"

RUN_CATALOG="${RUN_CATALOG:-1}"
RUN_INFERENCE="${RUN_INFERENCE:-1}"
RUN_ANALYSIS="${RUN_ANALYSIS:-1}"
FORCE_INFERENCE="${FORCE_INFERENCE:-0}"

mkdir -p "$LOG_DIR" "$OUTPUT_ROOT"
read -r -a seed_args <<< "$SEEDS"

run_and_log() {
    local log_file="$1"
    shift
    printf 'Running:'
    printf ' %q' "$@"
    printf '\n'
    "$@" 2>&1 | tee "$log_file"
}

if [[ "$RUN_CATALOG" == "1" ]]; then
    catalog_cmd=(
        uv run scripts/model/extreme_rain/build_subset300_extreme_rain_event_catalog.py
        --data-dir "$DATA_DIR"
        --split-dir "$SPLIT_DIR"
        --splits drbc_historical_stress
        --return-period-csv "$RETURN_PERIOD_CSV"
        --output-dir "$OUTPUT_ROOT/exposure"
        --event-time-mode "$EVENT_TIME_MODE"
    )
    [[ -n "${CATALOG_LIMIT_BASINS:-}" ]] && catalog_cmd+=(--limit-basins "$CATALOG_LIMIT_BASINS")
    run_and_log "$LOG_DIR/expanded_drbc_extreme_rain_catalog.log" "${catalog_cmd[@]}"
fi

if [[ "$RUN_INFERENCE" == "1" ]]; then
    infer_cmd=(
        uv run scripts/model/extreme_rain/infer_subset300_extreme_rain_windows.py
        --blocks-csv "$BLOCKS_CSV"
        --output-dir "$OUTPUT_ROOT/inference"
        --data-root "$DATA_ROOT"
        --test-basin-file "$TEST_BASIN_FILE"
        --device "$DEVICE"
        --seeds "${seed_args[@]}"
        --epoch-mode "$EPOCH_MODE"
    )
    [[ -n "${EVAL_BATCH_SIZE:-}" ]] && infer_cmd+=(--batch-size "$EVAL_BATCH_SIZE")
    [[ -n "${LIMIT_BASINS:-}" ]] && infer_cmd+=(--limit-basins "$LIMIT_BASINS")
    [[ -n "${LIMIT_EVENTS:-}" ]] && infer_cmd+=(--limit-events "$LIMIT_EVENTS")
    [[ "$FORCE_INFERENCE" == "1" ]] && infer_cmd+=(--force)
    run_and_log "$LOG_DIR/expanded_drbc_extreme_rain_inference.log" "${infer_cmd[@]}"
fi

if [[ "$RUN_ANALYSIS" == "1" ]]; then
    analysis_cmd=(
        uv run scripts/model/extreme_rain/analyze_subset300_extreme_rain_stress_test.py
        --input-dir "$OUTPUT_ROOT/inference"
        --cohort-csv "$COHORT_CSV"
        --output-dir "$OUTPUT_ROOT/analysis"
        --seeds "${seed_args[@]}"
    )
    run_and_log "$LOG_DIR/expanded_drbc_extreme_rain_analysis.log" "${analysis_cmd[@]}"
fi
