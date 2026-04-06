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

"$ROOT_DIR/scripts/download_demo_data.sh"

export PYTHONPATH="$ROOT_DIR/vendor/neuralhydrology${PYTHONPATH:+:$PYTHONPATH}"

python -m neuralhydrology.nh_run train \
  --config-file "$ROOT_DIR/configs/camels_us_01022500_daymet.yml"

LATEST_RUN="$(find "$ROOT_DIR/runs" -maxdepth 1 -mindepth 1 -type d -name 'camels_us_01022500_daymet_[0-9][0-9][0-9][0-9]_[0-9][0-9][0-9][0-9][0-9][0-9]' | sort | tail -n 1)"

if [ -z "$LATEST_RUN" ]; then
  echo "Training finished, but no run directory was found."
  exit 1
fi

python -m neuralhydrology.nh_run evaluate --run-dir "$LATEST_RUN"

echo "Latest run directory: $LATEST_RUN"
