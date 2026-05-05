#!/usr/bin/env bash
# =============================================================================
# bootstrap_elice.sh  — Elice Cloud A100 원클릭 부트스트랩
#
# 사용법 (서버 터미널에서):
#   curl -fsSL https://raw.githubusercontent.com/mossyantler/flood-underestimation-lstm/main/scripts/ops/bootstrap_elice.sh | bash
#
# 또는 repo를 이미 clone한 경우:
#   bash scripts/ops/bootstrap_elice.sh [--skip-data] [--model {1|2|both}]
#
# 옵션:
#   --skip-data    데이터가 이미 있는 경우 다운로드/추출 건너뜀
#   --model 1      Model 1 (deterministic)만 학습
#   --model 2      Model 2 (probabilistic)만 학습
#   --model both   Model 1 → 2 순서로 순차 학습 (기본값)
# =============================================================================
set -euo pipefail

REPO_URL="${GITHUB_REPO:-git@github.com:mossyantler/flood-underestimation-lstm.git}"
REPO_DIR="${ELICE_WORKSPACE:-/workspace/CAMELS}"
ARCHIVE_PATH="basins/CAMELSH_download/timeseries.7z"

# .env 로드 (있으면)
if [ -f ".env" ]; then
  set -o allexport
  source .env
  set +o allexport
fi

SKIP_DATA=false
TRAIN_MODEL="both"

# ── 인자 파싱 ───────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --skip-data) SKIP_DATA=true; shift ;;
    --model) TRAIN_MODEL="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

echo "======================================================"
echo " CAMELS Elice Cloud Bootstrap"
echo " Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo " Model: $TRAIN_MODEL  |  Skip data: $SKIP_DATA"
echo "======================================================"

# ── 1. 저장소 clone (현재 디렉토리가 repo가 아닌 경우만) ────────────────────
if [ ! -f "scripts/ops/bootstrap_elice.sh" ]; then
  echo ""
  echo "▶ [1/5] Cloning repository..."
  git clone "$REPO_URL" "$REPO_DIR"
  cd "$REPO_DIR"
else
  echo ""
  echo "▶ [1/5] Already in repository root. Pulling latest..."
  git pull --ff-only || true
fi

# ── 2. Python 환경 구축 (uv 기반) ────────────────────────────────────────────
echo ""
echo "▶ [2/5] Setting up Python environment with uv..."

# uv가 없으면 설치
if ! command -v uv &>/dev/null; then
  echo "  Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.cargo/bin:$PATH"
fi

# Python 3.11 venv 생성
if [ ! -d ".venv" ]; then
  uv python install 3.11 --quiet
  uv venv --python 3.11 .venv
fi
source .venv/bin/activate

# 의존성 설치 (CAMELSH dataset preparation용)
echo "  Installing Python dependencies..."
uv pip install --quiet "pandas>=2.2" "xarray>=2024.1" "netcdf4>=1.7" "py7zr>=0.22"

# NeuralHydrology: vendor 우선, 없으면 pip
export PYTHONPATH="$(pwd)/vendor/neuralhydrology${PYTHONPATH:+:$PYTHONPATH}"
if ! python -c "import neuralhydrology" &>/dev/null; then
  echo "  neuralhydrology not found in vendor — installing from pip..."
  uv pip install --quiet neuralhydrology
fi

echo "  ✓ Environment ready"
python -c "import torch; print(f'  torch {torch.__version__} | CUDA {torch.version.cuda} | GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"NONE\"}')"

# ── 3. 데이터 다운로드 + 추출 ─────────────────────────────────────────────────
if [ "$SKIP_DATA" = false ]; then
  echo ""
  echo "▶ [3/5] Downloading & extracting CAMELSH dataset..."
  echo "  Source: Zenodo record 15066778 (~20GB download → ~75GB extracted)"
  echo "  Started: $(date '+%H:%M:%S')"

  mkdir -p "$(dirname "$ARCHIVE_PATH")"

  # aria2c가 있으면 병렬 다운로드 (훨씬 빠름)
  if command -v aria2c &>/dev/null && [ ! -f "$ARCHIVE_PATH" ]; then
    ZENODO_URL=$(python -c "
import urllib.request, json
with urllib.request.urlopen('https://zenodo.org/api/records/15066778', timeout=30) as r:
    data = json.load(r)
for f in data['files']:
    if f['key'] == 'timeseries.7z':
        print(f['links']['self'])
        break
")
    echo "  Using aria2c for multi-connection download..."
    aria2c -x 16 -s 16 -k 10M -o "$ARCHIVE_PATH" "$ZENODO_URL"
  fi

  # prepare 스크립트로 다운로드 + 추출 + split 생성
  python scripts/data/prepare_camelsh_generic_dataset.py \
    --profile broad \
    --archive-path "$ARCHIVE_PATH" \
    --download-if-missing

  echo "  ✓ Dataset ready: $(date '+%H:%M:%S')"
else
  echo ""
  echo "▶ [3/5] Skipping data download (--skip-data)"
fi

# ── 4. 데이터 무결성 확인 ─────────────────────────────────────────────────────
echo ""
echo "▶ [4/5] Verifying data..."
NC_COUNT=$(ls data/CAMELSH_generic/drbc_holdout_broad/time_series/*.nc 2>/dev/null | wc -l | tr -d ' ')
TRAIN_COUNT=$(wc -l < data/CAMELSH_generic/drbc_holdout_broad/splits/train.txt | tr -d ' ')
echo "  NetCDF files: $NC_COUNT"
echo "  Train basins: $TRAIN_COUNT"

if [ "$NC_COUNT" -lt 100 ]; then
  echo "  ✗ Too few NetCDF files. Data may be incomplete. Re-run without --skip-data."
  exit 1
fi
echo "  ✓ Data looks good"

# ── 5. 학습 시작 ─────────────────────────────────────────────────────────────
echo ""
echo "▶ [5/5] Starting training..."
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

run_model() {
  local model_num=$1
  local config_file="configs/camelsh_hourly_model${model_num}_drbc_holdout_broad.yml"
  echo "------------------------------------------------------"
  echo " Training Model ${model_num} | Config: $config_file"
  echo " Start: $(date '+%H:%M:%S')"
  echo "------------------------------------------------------"
  python -m neuralhydrology.nh_run train --config-file "$config_file"
  echo " Done:  $(date '+%H:%M:%S')"
}

case "$TRAIN_MODEL" in
  1)    run_model 1 ;;
  2)    run_model 2 ;;
  both) run_model 1; run_model 2 ;;
  *)    echo "Unknown --model value: $TRAIN_MODEL (use 1, 2, or both)"; exit 1 ;;
esac

echo ""
echo "======================================================"
echo " All done: $(date '+%Y-%m-%d %H:%M:%S')"
echo " Results: ./runs/"
echo "======================================================"
