#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

SEEDS_STRING="${NH_SEEDS:-111 222 333}"
MODELS_STRING="${NH_MODELS:-model1 model2}"
RUN_ROOT="${NH_RUN_ROOT:-$ROOT_DIR/runs/subset300_main_comparison}"

export NH_SEEDS="$SEEDS_STRING"
export NH_MODELS="$MODELS_STRING"
export NH_RUN_ROOT="$RUN_ROOT"

"$ROOT_DIR/scripts/dev/run_subset_model_comparison.sh" 300
