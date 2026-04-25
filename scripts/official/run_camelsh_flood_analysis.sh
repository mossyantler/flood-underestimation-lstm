#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$PROJECT_ROOT"

TIMESERIES_DIR="${TIMESERIES_DIR:-data/CAMELSH_generic/drbc_holdout_broad/time_series}"
TIMESERIES_CSV_DIR="${TIMESERIES_CSV_DIR:-data/CAMELSH_generic/drbc_holdout_broad/time_series_csv}"
OUTPUT_DIR="${OUTPUT_DIR:-output/basin/camelsh_all/flood_analysis}"
WORKERS="${WORKERS:-2}"
if [[ -z "${UV_BIN:-}" ]]; then
  if command -v uv >/dev/null 2>&1; then
    UV_BIN="uv"
  elif [[ -x "$HOME/.local/bin/uv" ]]; then
    UV_BIN="$HOME/.local/bin/uv"
  else
    UV_BIN="uv"
  fi
fi

if [[ ! -d "$TIMESERIES_DIR" ]]; then
  echo "Time-series directory does not exist: $TIMESERIES_DIR" >&2
  exit 1
fi

if ! find "$TIMESERIES_DIR" -maxdepth 1 -name '*.nc' -print -quit | grep -q .; then
  echo "No .nc files found in $TIMESERIES_DIR. Finish rsync before running this analysis." >&2
  exit 1
fi

echo "Running CAMELSH all-basin flood analysis"
echo "  timeseries: $TIMESERIES_DIR"
echo "  output:     $OUTPUT_DIR"
echo "  workers:    $WORKERS"

return_period_cmd=(
  "$UV_BIN" run scripts/build_camelsh_return_period_references.py
  --timeseries-dir "$TIMESERIES_DIR"
  --timeseries-csv-dir "$TIMESERIES_CSV_DIR"
  --output-dir "$OUTPUT_DIR"
  --workers "$WORKERS"
)
event_response_cmd=(
  "$UV_BIN" run scripts/build_camelsh_event_response_table.py
  --timeseries-dir "$TIMESERIES_DIR"
  --timeseries-csv-dir "$TIMESERIES_CSV_DIR"
  --return-period-csv "$OUTPUT_DIR/return_period_reference_table.csv"
  --output-dir "$OUTPUT_DIR"
  --workers "$WORKERS"
)
if [[ -n "${LIMIT:-}" ]]; then
  return_period_cmd+=(--limit "$LIMIT")
  event_response_cmd+=(--limit "$LIMIT")
fi
if [[ -n "${BASIN_LIST:-}" ]]; then
  return_period_cmd+=(--basin-list "$BASIN_LIST")
  event_response_cmd+=(--basin-list "$BASIN_LIST")
fi

"${return_period_cmd[@]}"
"${event_response_cmd[@]}"

"$UV_BIN" run scripts/build_camelsh_flood_generation_typing.py \
  --event-response-csv "$OUTPUT_DIR/event_response_table.csv" \
  --output-dir "$OUTPUT_DIR"

echo "CAMELSH flood analysis complete: $OUTPUT_DIR"
