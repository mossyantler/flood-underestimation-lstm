#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT_DIR"
FLATTEN_HELPER="$ROOT_DIR/scripts/ops/flatten_nh_resume_run.py"

if [ "$#" -gt 0 ]; then
  SIZES=("$@")
else
  SIZES=("100" "300" "600")
fi

SEEDS_STRING="${NH_SEEDS:-111}"
read -r -a SEEDS <<< "$SEEDS_STRING"

PILOT_EPOCHS="${NH_PILOT_EPOCHS:-30}"
PILOT_NUM_WORKERS="${NH_NUM_WORKERS:-2}"
PILOT_CACHE_VALIDATION="${NH_CACHE_VALIDATION_DATA:-False}"
PILOT_DEVICE="${NH_DEVICE:-}"
PILOT_SAVE_ALL_OUTPUT="${NH_SAVE_ALL_OUTPUT:-}"
PILOT_SAVE_VALIDATION_RESULTS="${NH_SAVE_VALIDATION_RESULTS:-}"
PILOT_DRY_RUN="${NH_DRY_RUN:-0}"
PILOT_EXPERIMENT_SUFFIX="${NH_EXPERIMENT_SUFFIX:-}"
PILOT_RESUME="${NH_RESUME:-0}"

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
  echo "Run: uv run scripts/data/prepare_camelsh_generic_dataset.py --profile broad --download-if-missing"
  exit 1
fi

for SIZE in "${SIZES[@]}"; do
  BASE_CONFIG="$ROOT_DIR/configs/pilot/camelsh_hourly_model1_drbc_holdout_scaling_${SIZE}.yml"
  SPLIT_DIR="$ROOT_DIR/configs/pilot/basin_splits/scaling_${SIZE}"

  if [ ! -f "$BASE_CONFIG" ]; then
    echo "Pilot config not found: $BASE_CONFIG"
    exit 1
  fi

  if [ ! -f "$SPLIT_DIR/train.txt" ] || [ ! -f "$SPLIT_DIR/validation.txt" ] || [ ! -f "$SPLIT_DIR/test.txt" ]; then
    echo "Pilot split files not found under $SPLIT_DIR"
    echo "Run: uv run scripts/scaling/build_scaling_pilot_splits.py"
    exit 1
  fi

  for SEED in "${SEEDS[@]}"; do
    TMP_CONFIG="$(mktemp "${TMPDIR:-/tmp}/camelsh_scaling_${SIZE}_seed${SEED}.XXXXXX")"
    export BASE_CONFIG TMP_CONFIG SEED SIZE PILOT_EPOCHS PILOT_NUM_WORKERS PILOT_CACHE_VALIDATION PILOT_DEVICE PILOT_SAVE_ALL_OUTPUT PILOT_SAVE_VALIDATION_RESULTS PILOT_EXPERIMENT_SUFFIX PILOT_RESUME ROOT_DIR FLATTEN_HELPER
    RESUME_INFO="$(
      python - <<'PY'
import os
import shlex
import subprocess
from pathlib import Path

import yaml

config_path = Path(os.environ["BASE_CONFIG"])
tmp_path = Path(os.environ["TMP_CONFIG"])

cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
seed = int(os.environ["SEED"])
epochs = int(os.environ["PILOT_EPOCHS"])
num_workers = int(os.environ["PILOT_NUM_WORKERS"])
cache_validation = os.environ["PILOT_CACHE_VALIDATION"].strip().lower() in {"1", "true", "yes", "on"}
device = os.environ.get("PILOT_DEVICE", "").strip()
save_all_output_raw = os.environ.get("PILOT_SAVE_ALL_OUTPUT", "").strip()
save_validation_results_raw = os.environ.get("PILOT_SAVE_VALIDATION_RESULTS", "").strip()
suffix = os.environ.get("PILOT_EXPERIMENT_SUFFIX", "").strip()
resume_requested = os.environ.get("PILOT_RESUME", "0").strip().lower() in {"1", "true", "yes", "on"}
run_root = Path(os.environ["ROOT_DIR"]) / "runs" / "scaling_pilot"
flatten_helper = Path(os.environ["FLATTEN_HELPER"])


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}

cfg["seed"] = seed
cfg["epochs"] = epochs
cfg["num_workers"] = num_workers
cfg["cache_validation_data"] = cache_validation

experiment_name = f"{cfg['experiment_name']}_seed{seed}"
if suffix:
    experiment_name = f"{experiment_name}_{suffix}"
cfg["experiment_name"] = experiment_name

if device:
    cfg["device"] = device

if save_all_output_raw:
    cfg["save_all_output"] = parse_bool(save_all_output_raw)

if save_validation_results_raw:
    cfg["save_validation_results"] = parse_bool(save_validation_results_raw)

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
            "base_run_dir": best_completed["run_dir"],
            "matched_run_dir": best_completed["run_dir"],
            "last_common_epoch": best_completed["last_common_epoch"],
            "remaining_epochs": 0,
        }
    elif best_resumable is not None:
        remaining_epochs = epochs - best_resumable["last_common_epoch"]
        cfg = {
            "continue_from_epoch": best_resumable["last_common_epoch"],
            "epochs": remaining_epochs,
            "num_workers": num_workers,
            "cache_validation_data": cache_validation,
        }
        if device:
            cfg["device"] = device
        if save_all_output_raw:
            cfg["save_all_output"] = parse_bool(save_all_output_raw)
        if save_validation_results_raw:
            cfg["save_validation_results"] = parse_bool(save_validation_results_raw)
        resume_state = {
            "mode": "continue",
            "experiment_name": experiment_name,
            "base_run_dir": best_resumable["run_dir"],
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
    echo "Pilot run: size=${SIZE} | seed=${SEED} | target_epochs=${PILOT_EPOCHS} | mode=${mode}"
    echo "Config: $TMP_CONFIG"
    if [ "$mode" = "continue" ]; then
      echo "Resume run dir: $matched_run_dir"
      echo "Continue from epoch: $last_common_epoch | remaining_epochs=${remaining_epochs}"
    elif [ "$mode" = "skip" ]; then
      echo "Existing completed run dir: $matched_run_dir"
      echo "Last completed epoch: $last_common_epoch"
    fi
    echo "=========================================================="

    if [ "$PILOT_DRY_RUN" = "1" ]; then
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
