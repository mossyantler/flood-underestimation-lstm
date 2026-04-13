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
  echo "Run: uv run scripts/prepare_camelsh_generic_dataset.py --profile broad --download-if-missing"
  exit 1
fi

CONFIG_FILE="$ROOT_DIR/configs/camelsh_hourly_model1_drbc_holdout_broad.yml"
TMP_CONFIG=""

cleanup() {
  if [ -n "$TMP_CONFIG" ] && [ -f "$TMP_CONFIG" ]; then
    rm -f "$TMP_CONFIG"
  fi
}

trap cleanup EXIT

if [ -n "${NH_SEED:-}" ] || [ -n "${NH_DEVICE:-}" ] || [ -n "${NH_EXPERIMENT_SUFFIX:-}" ]; then
  TMP_CONFIG="$(mktemp "${TMPDIR:-/tmp}/camelsh_model1_broad.XXXXXX.yml")"
  export CONFIG_FILE TMP_CONFIG NH_SEED NH_DEVICE NH_EXPERIMENT_SUFFIX
  python - <<'PY'
import os
from pathlib import Path

import yaml

config_path = Path(os.environ["CONFIG_FILE"])
tmp_path = Path(os.environ["TMP_CONFIG"])
cfg = yaml.safe_load(config_path.read_text())

seed = os.environ.get("NH_SEED")
device = os.environ.get("NH_DEVICE")
suffix = os.environ.get("NH_EXPERIMENT_SUFFIX", "").strip()

if seed:
    cfg["seed"] = int(seed)
    seed_suffix = f"seed{seed}"
    suffix = f"{suffix}_{seed_suffix}" if suffix else seed_suffix

if device:
    cfg["device"] = device

if suffix:
    cfg["experiment_name"] = f"{cfg['experiment_name']}_{suffix}"

tmp_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
PY
  CONFIG_FILE="$TMP_CONFIG"
fi

echo "Running Model 1 broad config: $CONFIG_FILE"

python -m neuralhydrology.nh_run train \
  --config-file "$CONFIG_FILE"
