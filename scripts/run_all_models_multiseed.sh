#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -d ".venv" ]; then
  uv python install 3.11
  uv venv --python 3.11 .venv
fi
source .venv/bin/activate
export PYTHONPATH="$ROOT_DIR/vendor/neuralhydrology${PYTHONPATH:+:$PYTHONPATH}"

SEEDS=(111 222 333)
MODELS=("model1" "model2")

echo "=== Starting Full Multi-Seed Training (Model 1 & Model 2) ==="
echo "Memory optimizations (num_workers=2, cache_validation_data=False) applied."

for MODEL in "${MODELS[@]}"; do
  BASE_CONFIG="$ROOT_DIR/configs/camelsh_hourly_${MODEL}_drbc_holdout_broad.yml"
  
  if [ ! -f "$BASE_CONFIG" ]; then
    echo "Config not found: $BASE_CONFIG. Skipping $MODEL..."
    continue
  fi

  for SEED in "${SEEDS[@]}"; do
    echo ""
    echo "=========================================================="
    echo ">>> 🚀 Training starting for: $MODEL | seed: $SEED"
    echo "=========================================================="
    
    RUN_CONFIG="${BASE_CONFIG%.yml}_seed_${SEED}.yml"
    
    sed -e "s/^seed:.*$/seed: $SEED/" \
        -e "s/^num_workers:.*$/num_workers: 2/" \
        -e "s/^cache_validation_data:.*$/cache_validation_data: False/" \
        "$BASE_CONFIG" > "$RUN_CONFIG"

    python -m neuralhydrology.nh_run train --config-file "$RUN_CONFIG"
    
    echo ">>> ✅ Training completed for: $MODEL | seed: $SEED"
  done
done

echo ""
echo "🎉 === All trainings (Model 1 & Model 2) completed successfully! === 🎉"
