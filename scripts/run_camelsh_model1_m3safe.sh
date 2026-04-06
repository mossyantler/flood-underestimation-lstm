#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -d ".venv" ]; then
  uv python install 3.11
  uv venv --python 3.11 .venv
fi

source .venv/bin/activate

if ! python -c "import neuralhydrology" >/dev/null 2>&1; then
  uv pip install neuralhydrology
fi

export PYTHONPATH="$ROOT_DIR/vendor/neuralhydrology${PYTHONPATH:+:$PYTHONPATH}"

DATA_DIR="$ROOT_DIR/data/CAMELSH_generic/drbc_holdout_broad"
if [ ! -d "$DATA_DIR/time_series" ]; then
  echo "Prepared GenericDataset not found at $DATA_DIR"
  exit 1
fi

uv run scripts/build_camelsh_safe_splits.py

python -m neuralhydrology.nh_run train \
  --config-file "$ROOT_DIR/configs/camelsh_hourly_model1_drbc_holdout_m3safe.yml"
