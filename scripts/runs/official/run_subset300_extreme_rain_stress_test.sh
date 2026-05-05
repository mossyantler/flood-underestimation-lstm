#!/usr/bin/env bash
set -euo pipefail

OUTPUT_ROOT="${OUTPUT_ROOT:-output/model_analysis/extreme_rain/primary}"
LOG_DIR="${LOG_DIR:-logs}"
DEVICE="${DEVICE:-cuda:0}"
SEEDS="${SEEDS:-111 222 444}"
EPOCH_MODE="${EPOCH_MODE:-primary}"
VALIDATION_EPOCHS="${VALIDATION_EPOCHS:-5 10 15 20 25 30}"
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
    --output-dir "$OUTPUT_ROOT/exposure"
  )

  if [[ -n "${CATALOG_LIMIT_BASINS:-}" ]]; then
    catalog_cmd+=(--limit-basins "$CATALOG_LIMIT_BASINS")
  fi

  if [[ -n "${CATALOG_SPLITS:-}" ]]; then
    read -r -a catalog_splits <<< "$CATALOG_SPLITS"
    catalog_cmd+=(--splits "${catalog_splits[@]}")
  fi

  run_and_log "$LOG_DIR/extreme_rain_catalog.log" "${catalog_cmd[@]}"
fi

if [[ "$RUN_INFERENCE" == "1" ]]; then
  inference_cmd=(
    uv run scripts/model/extreme_rain/infer_subset300_extreme_rain_windows.py
    --blocks-csv "$BLOCKS_CSV"
    --output-dir "$OUTPUT_ROOT/inference"
    --device "$DEVICE"
    --seeds "${seed_args[@]}"
    --epoch-mode "$EPOCH_MODE"
  )

  if [[ "$EPOCH_MODE" == "validation" ]]; then
    read -r -a validation_epoch_args <<< "$VALIDATION_EPOCHS"
    inference_cmd+=(--validation-epochs "${validation_epoch_args[@]}")
  fi

  if [[ -n "${INFER_LIMIT_EVENTS:-}" ]]; then
    inference_cmd+=(--limit-events "$INFER_LIMIT_EVENTS")
  fi

  if [[ -n "${INFER_LIMIT_BASINS:-}" ]]; then
    inference_cmd+=(--limit-basins "$INFER_LIMIT_BASINS")
  fi

  if [[ -n "${INFER_BATCH_SIZE:-}" ]]; then
    inference_cmd+=(--batch-size "$INFER_BATCH_SIZE")
  fi

  if [[ "$FORCE_INFERENCE" == "1" ]]; then
    inference_cmd+=(--force)
  fi

  run_and_log "$LOG_DIR/extreme_rain_inference.log" "${inference_cmd[@]}"
fi

if [[ "$RUN_ANALYSIS" == "1" ]]; then
  analysis_cmd=(
    uv run scripts/model/extreme_rain/analyze_subset300_extreme_rain_stress_test.py
    --input-dir "$OUTPUT_ROOT/inference"
    --cohort-csv "$COHORT_CSV"
    --output-dir "$OUTPUT_ROOT/analysis"
    --seeds "${seed_args[@]}"
  )

  if [[ -n "${ANALYSIS_LIMIT_EVENTS:-}" ]]; then
    analysis_cmd+=(--limit-events "$ANALYSIS_LIMIT_EVENTS")
  fi

  run_and_log "$LOG_DIR/extreme_rain_analysis.log" "${analysis_cmd[@]}"
fi
