# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repo.

---

## 연구 개요

Multi-basin LSTM 수문 예측, **극한 홍수 첨두 과소추정** 감소 연구.
공식 비교축: **Model 1 (Deterministic LSTM)** vs **Model 2 (Probabilistic quantile LSTM)**.
Model 3 (physics-guided hybrid): 후속 확장, 현재 논문 범위 밖.

**고정 조건**: seed `111 / 222 / 444`, non-DRBC `scaling_300` subset, temporal split `train 2000–2010 / validation 2011–2013 / test 2014–2016`

---

## 개발 환경

### Python (루트 레벨 스크립트)

`uv run`으로 실행.

```bash
export PATH="/opt/homebrew/bin:$PATH"   # 로컬 macOS에서만 적용, 원격 Ubuntu는 불필요
uv run scripts/<path>.py
```

### Dashboard (Next.js)

```bash
cd dashboard
npm install
npm run dev           # http://localhost:3000
npm run typecheck     # UI/data type 변경 후 최소 실행
npm run build         # route/layout/dependency/asset 변경 시 실행
```

- dependency: `package-lock.json` 기준 npm만 (yarn/pnpm 금지).

### 원격 GPU 서버 (Elice)

```bash
ssh -i ~/.ssh/elice.pem elicer@central-02.tcp.tunnel.elice.io -p 15699
```

- Ubuntu 22.04, Homebrew PATH 추가 안 함.

---

## 저장소 구조 (큰 그림)

```text
configs/              # 공식 basin split, pilot config → source-of-truth
  pilot/basin_splits/scaling_300/   # 고정 300-basin main comparison split
data/CAMELSH_generic/ # NH-style hourly dataset (gitignored)
basins/               # CAMELSH 원자료, DRBC boundary shapefile
docs/experiment/
  method/             # 모델 구조, 데이터 처리 방법 → canonical 기준
  analysis/model/     # 실험 결과 분석 문서
scripts/
  runs/official/      # 공식 실행 진입점 (shell runner)
  runs/pilot/         # scaling pilot training runner
  runs/dev/           # local sanity / subset comparison helper
  model/              # 결과 분석 (overall, hydrograph, event_regime, extreme_rain)
  basin/              # basin screening, reference fetch, split diagnostics
  data/               # download, NH generic data preparation
  ops/                # repo integrity, run flattening, metric summary
  _lib/               # 공용 helper (camelsh_flood_analysis_utils.py)
  scaling/            # scaling pilot diagnostics
vendor/neuralhydrology/ # vendored upstream, 직접 수정 피할 것
dashboard/            # Next.js 대시보드 (분석 source-of-truth 아님)
output/               # (gitignored) 모든 분석/그림 산출물
runs/                 # (gitignored) 학습 checkpoint
```

---

## 핵심 실행 명령

### 저장소 무결성 점검

```bash
uv run scripts/ops/check_repo_integrity.py
```

### 공식 학습 (원격 GPU)

```bash
# Model 1 & Model 2 seed 111/222/444 (scaling_300 subset)
bash scripts/runs/official/run_subset300_multiseed.sh
```

### 전체 basin flood analysis (rsync 후)

```bash
TIMESERIES_DIR=/path/to/time_series \
OUTPUT_DIR=output/basin/all/analysis \
WORKERS=4 \
bash scripts/runs/official/run_camelsh_flood_analysis.sh
```

### 모델 결과 집계

```bash
uv run scripts/model/overall/analyze_subset300_epoch_results.py
uv run scripts/model/hydrograph/plot_subset300_hydrographs.py
uv run scripts/model/hydrograph/analyze_subset300_hydrograph_outputs.py
uv run scripts/model/hydrograph/analyze_subset300_probabilistic_diagnostics.py
```

### Extreme-rain stress test

```bash
DEVICE=cuda:0 bash scripts/runs/official/run_subset300_extreme_rain_stress_test.sh
```

---

## 아키텍처 원칙

### Source-of-truth 계층

| 영역 | 위치 |
| --- | --- |
| 공식 모델 비교 결론 | `docs/experiment/analysis/model/` |
| 데이터 처리 방법 | `docs/experiment/method/` |
| basin split 정의 | `configs/pilot/basin_splits/scaling_300/` (not `configs/basin_splits/`) |
| 공식 config | `configs/camelsh_hourly_*_drbc_holdout_broad.yml` |
| 산출물 | `output/` (gitignored, 재생성 가능) |

- `dashboard/lib/` snapshot 데이터: source-of-truth 파생 표시용 사본.
- `docs/archive/`, `docs/explain/`, `docs/references/`: 공식 근거 아님.

### DRBC holdout 경계

- DRBC holdout: `outlet_in_drbc == True` AND `overlap_ratio >= 0.9` → **154개 basin**
- Training pool: `outlet_in_drbc == False` AND `overlap_ratio <= 0.1`, quality gate 통과 → **1923개** (고정 subset **300개** 사용)
- Primary DRBC test (`2014-2016`): extreme-rain stress test / checkpoint sensitivity 진단으로 대체 금지.

### Seed / epoch 정책

- 공식 paired seed: `111 / 222 / 444`. Model 2 seed `333`: NaN loss 중단. Model 1 seed `333`: fair comparison 위해 final aggregate 제외.
- Checkpoint sensitivity: 진단용만, primary epoch 재선정 금지.

### 산출물 경로 규칙

- 분석 결과 → `output/model_analysis/`
- Basin-side 결과 → `output/basin/`
- extreme-rain primary (wet-footprint 시간축) → `output/model_analysis/legacy/extreme_rain/primary/`
- epoch sweep → `output/model_analysis/legacy/extreme_rain/all/`

---

## 문서 동기화 규칙

아래 변경 시 코드와 동일 작업 안에서 관련 문서 갱신.

- 공식 모델 비교축, config key/기본값, split source-of-truth 변경
- 파일/폴더 경로 이동·이름 변경
- 공식 실행 진입점, 산출물 저장 위치 변경

갱신 대상: `AGENTS.md`, `README.md`, `docs/README.md`, 해당 `docs/experiment/method/` 문서, 관련 `configs/README.md`, `scripts/README.md`.

dev-only 실험 / exploratory 메모: 해당 `dev` 또는 `archive` 문서만 갱신.

---

## Dashboard 작업 규칙

- 수치·caption 수정 전: `output/model_analysis/`, `docs/experiment/analysis/`, `configs/` 근거 파일 먼저 확인.
- 대용량 CSV·hydrograph gallery·checkpoint: `dashboard/` 안에 넣지 않는다.
- figure preview → `dashboard/public/figures/`, UI reference image → `dashboard/public/research/`.
- UI 변경 후: `npm run typecheck`, build/route 영향 시 `npm run build` 실행.