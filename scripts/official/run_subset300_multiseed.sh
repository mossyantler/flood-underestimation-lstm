#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

MODEL1_SEEDS_STRING="${NH_MODEL1_SEEDS:-${NH_SEEDS:-111 222 444}}"
MODEL2_SEEDS_STRING="${NH_MODEL2_SEEDS:-${NH_SEEDS:-111 222 444}}"
MODELS_STRING="${NH_MODELS:-model1 model2}"
RUN_ROOT="${NH_RUN_ROOT:-$ROOT_DIR/runs/subset_comparison}"

export NH_RUN_ROOT="$RUN_ROOT"

read -r -a MODELS <<< "$MODELS_STRING"

for MODEL in "${MODELS[@]}"; do
  case "$MODEL" in
    model1)
      SEEDS_STRING="$MODEL1_SEEDS_STRING"
      ;;
    model2)
      SEEDS_STRING="$MODEL2_SEEDS_STRING"
      ;;
    *)
      SEEDS_STRING="${NH_SEEDS:-111 222 444}"
      ;;
  esac

  export NH_SEEDS="$SEEDS_STRING"
  export NH_MODELS="$MODEL"

  "$ROOT_DIR/scripts/dev/run_subset_model_comparison.sh" 300
done
