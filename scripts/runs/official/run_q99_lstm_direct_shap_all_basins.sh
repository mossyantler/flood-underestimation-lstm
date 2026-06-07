#!/usr/bin/env bash
# Run q99 direct SHAP for all 85 DRBC test basins, seeds 111/222/444.
# Previous run used --max-events 120 (basin-sorted CSV) → only 8 basins covered.
# This script removes the cap (--max-events 0) to cover all basins.
#
# Usage (remote GPU):
#   bash scripts/runs/official/run_q99_lstm_direct_shap_all_basins.sh
#
# Estimated: ~1222 events × 3 seeds × 64 SHAP samples on single GPU.
# Outputs overwrite output/model_analysis/shap/q99/

set -euo pipefail

SEEDS=(111 222 444)
DEVICE="${DEVICE:-cuda}"

for SEED in "${SEEDS[@]}"; do
    echo "===== seed ${SEED} ====="
    uv run scripts/model/overall/compute_q99_lstm_direct_shap.py \
        --analysis-scope q99 \
        --seed "${SEED}" \
        --device "${DEVICE}" \
        --quantiles q50 q90 q95 q99 \
        --max-events 0 \
        --background-events 32 \
        --shap-samples 64
    echo "===== seed ${SEED} done ====="
done

echo "All seeds done. Re-run direction analysis:"
echo "  uv run scripts/model/overall/analyze_shap_direction_patterns.py"
