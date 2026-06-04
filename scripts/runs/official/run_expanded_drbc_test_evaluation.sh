#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT_DIR"

LOG_DIR="${LOG_DIR:-logs}"
OUTPUT_DIR="${OUTPUT_DIR:-output/model_analysis/primary/metrics}"
DATA_DIR="${DATA_DIR:-data/CAMELSH_generic/drbc_expanded_observed_test}"
BASIN_FILE="${BASIN_FILE:-$DATA_DIR/splits/test.txt}"
RUN_ROOT="${RUN_ROOT:-runs/subset_comparison}"
DEVICE="${DEVICE:-cuda:0}"
SEEDS="${SEEDS:-111 222 444}"
RUN_SPLIT="${RUN_SPLIT:-1}"
RUN_PREPARE="${RUN_PREPARE:-1}"
RUN_EVALUATION="${RUN_EVALUATION:-1}"
FORCE_PREPARE="${FORCE_PREPARE:-0}"
FORCE_EVALUATION="${FORCE_EVALUATION:-0}"

mkdir -p "$LOG_DIR" "$OUTPUT_DIR"
read -r -a seed_args <<< "$SEEDS"

run_and_log() {
  local log_file="$1"
  shift

  printf 'Running:'
  printf ' %q' "$@"
  printf '\n'
  "$@" 2>&1 | tee "$log_file"
}

if [[ "$RUN_SPLIT" == "1" ]]; then
  run_and_log "$LOG_DIR/expanded_drbc_split.log" \
    uv run scripts/basin/drbc/build_drbc_expanded_observed_test_split.py
fi

if [[ "$RUN_PREPARE" == "1" ]]; then
  prepare_cmd=(
    uv run scripts/data/prepare_drbc_expanded_observed_test_dataset.py
    --output-dir "$DATA_DIR"
  )

  if [[ "$FORCE_PREPARE" == "1" ]]; then
    prepare_cmd+=(--force)
  fi

  if [[ -n "${PREPARE_LIMIT_BASINS:-}" ]]; then
    prepare_cmd+=(--limit-basins "$PREPARE_LIMIT_BASINS")
  fi

  run_and_log "$LOG_DIR/expanded_drbc_prepare.log" "${prepare_cmd[@]}"
fi

if [[ "$RUN_EVALUATION" == "1" ]]; then
  eval_cmd=(
    uv run scripts/model/overall/evaluate_subset300_expanded_drbc_test.py
    --run-root "$RUN_ROOT"
    --data-dir "$DATA_DIR"
    --basin-file "$BASIN_FILE"
    --output-dir "$OUTPUT_DIR"
    --device "$DEVICE"
    --seeds "${seed_args[@]}"
  )

  if [[ -n "${EVAL_BATCH_SIZE:-}" ]]; then
    eval_cmd+=(--batch-size "$EVAL_BATCH_SIZE")
  fi

  if [[ -n "${EVAL_LIMIT_BASINS:-}" ]]; then
    eval_cmd+=(--limit-basins "$EVAL_LIMIT_BASINS")
  fi

  if [[ "$FORCE_EVALUATION" == "1" ]]; then
    eval_cmd+=(--force)
  fi

  run_and_log "$LOG_DIR/expanded_drbc_evaluation.log" "${eval_cmd[@]}"
fi
