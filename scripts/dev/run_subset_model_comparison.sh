#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

FLATTEN_HELPER="$ROOT_DIR/scripts/flatten_nh_resume_run.py"
SIZE="${1:-300}"

MODELS_STRING="${NH_MODELS:-model1 model2}"
read -r -a MODELS <<< "$MODELS_STRING"

SEEDS_STRING="${NH_SEEDS:-111}"
read -r -a SEEDS <<< "$SEEDS_STRING"

RUN_ROOT="${NH_RUN_ROOT:-$ROOT_DIR/runs/subset_comparison}"
RUN_EPOCHS="${NH_EPOCHS:-30}"
RUN_BATCH_SIZE="${NH_BATCH_SIZE:-384}"
RUN_NUM_WORKERS="${NH_NUM_WORKERS:-6}"
RUN_VALIDATE_EVERY="${NH_VALIDATE_EVERY:-5}"
RUN_CACHE_VALIDATION="${NH_CACHE_VALIDATION_DATA:-False}"
RUN_DEVICE="${NH_DEVICE:-cuda:0}"
RUN_SAVE_ALL_OUTPUT="${NH_SAVE_ALL_OUTPUT:-False}"
RUN_SAVE_VALIDATION_RESULTS="${NH_SAVE_VALIDATION_RESULTS:-True}"
RUN_SAVE_WEIGHTS_EVERY="${NH_SAVE_WEIGHTS_EVERY:-1}"
RUN_LOG_TENSORBOARD="${NH_LOG_TENSORBOARD:-False}"
RUN_DRY_RUN="${NH_DRY_RUN:-0}"
RUN_EXPERIMENT_SUFFIX="${NH_EXPERIMENT_SUFFIX:-}"
RUN_RESUME="${NH_RESUME:-1}"

if [ ! -d ".venv" ]; then
  uv python install 3.11
  uv venv --python 3.11 .venv
fi

source .venv/bin/activate

if ! python -c "import neuralhydrology" >/dev/null 2>&1; then
  uv pip install neuralhydrology
fi

if ! python -c "import yaml" >/dev/null 2>&1; then
  uv pip install pyyaml
fi

export PYTHONPATH="$ROOT_DIR/vendor/neuralhydrology${PYTHONPATH:+:$PYTHONPATH}"

DATA_DIR="$ROOT_DIR/data/CAMELSH_generic/drbc_holdout_broad"
if [ ! -d "$DATA_DIR/time_series" ]; then
  echo "Prepared broad GenericDataset not found at $DATA_DIR"
  echo "Run: uv run scripts/prepare_camelsh_generic_dataset.py --profile broad --download-if-missing"
  exit 1
fi

SPLIT_DIR="$ROOT_DIR/configs/pilot/basin_splits/scaling_${SIZE}"
if [ ! -f "$SPLIT_DIR/train.txt" ] || [ ! -f "$SPLIT_DIR/validation.txt" ] || [ ! -f "$SPLIT_DIR/test.txt" ]; then
  echo "Subset split files not found under $SPLIT_DIR"
  echo "Run: uv run scripts/pilot/build_scaling_pilot_splits.py"
  exit 1
fi

mkdir -p "$RUN_ROOT"

VALIDATION_COUNT="$(wc -l < "$SPLIT_DIR/validation.txt" | tr -d ' ')"

for MODEL in "${MODELS[@]}"; do
  BASE_CONFIG="$ROOT_DIR/configs/camelsh_hourly_${MODEL}_drbc_holdout_broad.yml"
  if [ ! -f "$BASE_CONFIG" ]; then
    echo "Subset comparison base config not found: $BASE_CONFIG"
    exit 1
  fi

  for SEED in "${SEEDS[@]}"; do
    TMP_CONFIG="$(mktemp "${TMPDIR:-/tmp}/camelsh_subset_${SIZE}_${MODEL}_seed${SEED}.XXXXXX")"
    export BASE_CONFIG TMP_CONFIG MODEL SIZE SEED RUN_ROOT RUN_EPOCHS RUN_BATCH_SIZE RUN_NUM_WORKERS RUN_VALIDATE_EVERY RUN_CACHE_VALIDATION RUN_DEVICE RUN_SAVE_ALL_OUTPUT RUN_SAVE_VALIDATION_RESULTS RUN_SAVE_WEIGHTS_EVERY RUN_LOG_TENSORBOARD RUN_EXPERIMENT_SUFFIX RUN_RESUME ROOT_DIR FLATTEN_HELPER SPLIT_DIR VALIDATION_COUNT
    RESUME_INFO="$(
      python - <<'PY'
import os
import shlex
import subprocess
from pathlib import Path

import yaml


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


config_path = Path(os.environ["BASE_CONFIG"])
tmp_path = Path(os.environ["TMP_CONFIG"])
split_dir = Path(os.environ["SPLIT_DIR"])
run_root = Path(os.environ["RUN_ROOT"])
flatten_helper = Path(os.environ["FLATTEN_HELPER"])

cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))

size = os.environ["SIZE"]
seed = int(os.environ["SEED"])
epochs = int(os.environ["RUN_EPOCHS"])
batch_size = int(os.environ["RUN_BATCH_SIZE"])
num_workers = int(os.environ["RUN_NUM_WORKERS"])
validate_every = int(os.environ["RUN_VALIDATE_EVERY"])
cache_validation = parse_bool(os.environ["RUN_CACHE_VALIDATION"])
device = os.environ["RUN_DEVICE"].strip()
save_all_output = parse_bool(os.environ["RUN_SAVE_ALL_OUTPUT"])
save_validation_results = parse_bool(os.environ["RUN_SAVE_VALIDATION_RESULTS"])
save_weights_every = int(os.environ["RUN_SAVE_WEIGHTS_EVERY"])
log_tensorboard = parse_bool(os.environ["RUN_LOG_TENSORBOARD"])
validation_count = int(os.environ["VALIDATION_COUNT"])
suffix = os.environ.get("RUN_EXPERIMENT_SUFFIX", "").strip()
resume_requested = parse_bool(os.environ.get("RUN_RESUME", "1"))

cfg["seed"] = seed
cfg["epochs"] = epochs
cfg["batch_size"] = batch_size
cfg["num_workers"] = num_workers
cfg["validate_every"] = validate_every
cfg["validate_n_random_basins"] = validation_count
cfg["cache_validation_data"] = cache_validation
cfg["save_all_output"] = save_all_output
cfg["save_validation_results"] = save_validation_results
cfg["save_weights_every"] = save_weights_every
cfg["log_tensorboard"] = log_tensorboard
cfg["run_dir"] = str(run_root)
cfg["train_basin_file"] = str(split_dir / "train.txt")
cfg["validation_basin_file"] = str(split_dir / "validation.txt")
cfg["test_basin_file"] = str(split_dir / "test.txt")
cfg["device"] = device

base_experiment_name = cfg["experiment_name"]
if base_experiment_name.endswith("_broad"):
    base_experiment_name = base_experiment_name[:-6]
base_experiment_name = f"{base_experiment_name}_subset{size}"

experiment_name = f"{base_experiment_name}_seed{seed}"
if suffix:
    experiment_name = f"{experiment_name}_{suffix}"
cfg["experiment_name"] = experiment_name

resume_state = {
    "mode": "train",
    "experiment_name": experiment_name,
    "base_run_dir": None,
    "matched_run_dir": None,
    "last_common_epoch": None,
    "remaining_epochs": epochs,
}

if resume_requested and run_root.exists():
    candidates = [p for p in run_root.iterdir() if p.is_dir() and p.name.startswith(f"{experiment_name}_")]
    for candidate in candidates:
        subprocess.run(
            [os.environ.get("PYTHON", "python"), str(flatten_helper), "--run-dir", str(candidate), "--quiet"],
            check=True,
        )

    best_completed = None
    best_resumable = None

    for candidate in candidates:
        run_dirs = [candidate]
        run_dirs.extend(
            p for p in candidate.rglob("continue_training_from_epoch*")
            if p.is_dir()
        )

        for run_dir in run_dirs:
            if not (run_dir / "config.yml").exists():
                continue

            model_epochs = {int(p.stem.split("model_epoch")[-1]) for p in run_dir.glob("model_epoch*.pt")}
            optimizer_epochs = {
                int(p.stem.split("optimizer_state_epoch")[-1]) for p in run_dir.glob("optimizer_state_epoch*.pt")
            }
            common_epochs = sorted(model_epochs & optimizer_epochs)
            if not common_epochs:
                continue

            last_common = common_epochs[-1]
            record = {
                "base_run_dir": str(candidate),
                "run_dir": str(run_dir),
                "last_common_epoch": last_common,
                "mtime": run_dir.stat().st_mtime,
            }
            if last_common >= epochs:
                if best_completed is None or (record["last_common_epoch"], record["mtime"]) > (
                    best_completed["last_common_epoch"],
                    best_completed["mtime"],
                ):
                    best_completed = record
            else:
                if best_resumable is None or (record["last_common_epoch"], record["mtime"]) > (
                    best_resumable["last_common_epoch"],
                    best_resumable["mtime"],
                ):
                    best_resumable = record

    if best_completed is not None:
        resume_state = {
            "mode": "skip",
            "experiment_name": experiment_name,
            "base_run_dir": best_completed["base_run_dir"],
            "matched_run_dir": best_completed["run_dir"],
            "last_common_epoch": best_completed["last_common_epoch"],
            "remaining_epochs": 0,
        }
    elif best_resumable is not None:
        remaining_epochs = epochs - best_resumable["last_common_epoch"]
        cfg = {
            "continue_from_epoch": best_resumable["last_common_epoch"],
            "epochs": remaining_epochs,
            "batch_size": batch_size,
            "num_workers": num_workers,
            "validate_every": validate_every,
            "validate_n_random_basins": validation_count,
            "cache_validation_data": cache_validation,
            "save_all_output": save_all_output,
            "save_validation_results": save_validation_results,
            "save_weights_every": save_weights_every,
            "log_tensorboard": log_tensorboard,
            "device": device,
        }
        resume_state = {
            "mode": "continue",
            "experiment_name": experiment_name,
            "base_run_dir": best_resumable["base_run_dir"],
            "matched_run_dir": best_resumable["run_dir"],
            "last_common_epoch": best_resumable["last_common_epoch"],
            "remaining_epochs": remaining_epochs,
        }

tmp_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

for key, value in resume_state.items():
    rendered = "" if value is None else str(value)
    print(f"{key}={shlex.quote(rendered)}")
PY
    )"
    eval "$RESUME_INFO"

    echo ""
    echo "=========================================================="
    echo "Subset comparison: size=${SIZE} | model=${MODEL} | seed=${SEED} | target_epochs=${RUN_EPOCHS} | mode=${mode}"
    echo "Config: $TMP_CONFIG"
    echo "Run root: $RUN_ROOT"
    echo "Overrides: batch_size=${RUN_BATCH_SIZE}, num_workers=${RUN_NUM_WORKERS}, validate_every=${RUN_VALIDATE_EVERY}, cache_validation_data=${RUN_CACHE_VALIDATION}, save_all_output=${RUN_SAVE_ALL_OUTPUT}, save_validation_results=${RUN_SAVE_VALIDATION_RESULTS}"
    if [ "$mode" = "continue" ]; then
      echo "Resume run dir: $matched_run_dir"
      echo "Continue from epoch: $last_common_epoch | remaining_epochs=${remaining_epochs}"
    elif [ "$mode" = "skip" ]; then
      echo "Existing completed run dir: $matched_run_dir"
      echo "Last completed epoch: $last_common_epoch"
    fi
    echo "=========================================================="

    if [ "$RUN_DRY_RUN" = "1" ]; then
      cat "$TMP_CONFIG"
      rm -f "$TMP_CONFIG"
      continue
    fi

    if [ "$mode" = "skip" ]; then
      rm -f "$TMP_CONFIG"
      continue
    elif [ "$mode" = "continue" ]; then
      python -m neuralhydrology.nh_run continue_training \
        --run-dir "$matched_run_dir" \
        --config-file "$TMP_CONFIG"
      python "$FLATTEN_HELPER" --run-dir "$base_run_dir" --quiet
    else
      python -m neuralhydrology.nh_run train \
        --config-file "$TMP_CONFIG"
    fi

    rm -f "$TMP_CONFIG"
  done
done
