# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repo.

---

## 응답 및 문서 작성 스타일

- 응답, 설명 문서, HTML/report 산출물은 한국어 기본으로 작성한다.
- 영어는 API, LSTM, quantile, calibration, coverage, SHAP, RandomForest처럼 고정된 전문 용어와 코드 식별자에만 제한한다. 일반 설명어·제목·표 머리글은 가능한 한 한국어로 쓴다.
- 전문 용어, 자체 규정 단어, 새 지표명은 첫 등장 시 반드시 한국어 풀이를 붙인다. 예: `coverage`는 "관측값이 예측 quantile 아래에 들어오는 비율".
- `obs class`, `signal feature`, `risk tier`, `leakage`, `anchor` 같은 내부 용어를 그대로 쓰지 않는다. 한국어 이름을 먼저 쓴 뒤 필요하면 괄호에 코드명/영어를 병기한다.
  - `obs class` → 관측 위치 구간
  - `signal feature` → 신호 지표
  - `risk tier` → 위험 단계
  - `leakage` → 관측값 누수
  - `anchor` → 계산 기준 시점
- 대학생 수준 설명 자료는 "무엇을 보는 분석인지" → "왜 필요한지" → "어떻게 해석해야 하는지" 순서로 쓴다.
- `docs/explain/` 설명 자료는 **수문학 전공 대학생** 기준으로 쓴다. 유역·하천 유량·홍수 첨두·재현기간·NSE/KGE 같은 수문학 기본 개념은 전제하고 다시 풀지 않는다. 반면 기계학습 배경(LSTM, quantile, calibration 등)은 전제하지 않고 첫 등장 시 한 번만 짚는다. 간결하게 쓰고 일상 비유·장황한 단계 풀이는 지양한다. 한국어 위주로 작성하며, 불가피한 고정 전문 용어만 영어로 남긴다.

## Paper draft / Notion 운영

- Notion은 논문 draft를 확인하고 수정하는 공간이다. 운영 규칙, export 절차, 원본 artifact 준비 방법은 Notion에 쓰지 않는다.
- Notion 문장은 논문 본문처럼 간결하게 쓴다. AI가 설명하는 듯한 말투, 작업 보고 말투, 장황한 안내문을 넣지 않는다.
- Notion page와 database title에는 이모지를 쓰지 않는다.
- `Draft`는 버전 관리를 위한 full-page database로 둔다. 각 논문 본문은 `Draft` database row page에 둔다.
- Draft version을 freeze하거나 export할 때의 절차와 보관 규칙은 repo 문서(`AGENTS.md`, `CLAUDE.md`, `draft/README.md`, `draft/notion_exports/README.md`)에서 관리한다.
- Notion 밖에서 준비하는 figure, table, export, source path, canonical 근거는 repo에 기록한다. Notion에는 논문 검토에 필요한 최종 draft 내용만 둔다.

---

## 연구 개요

Multi-basin LSTM 수문 예측, **극한 홍수 첨두 과소추정** 감소 연구.
공식 비교축: **Model 1 (Deterministic LSTM)** vs **Model 2 (Probabilistic quantile LSTM)**.
Model 3 (physics-guided hybrid): 후속 확장, 현재 논문 범위 밖.

**고정 조건**: seed `111 / 222 / 444`, non-DRBC `scaling_300` train/validation subset, expanded observed DRBC test **85개**, temporal split `train 2000–2010 / validation 2011–2013 / test 2014–2016`

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
ssh -i ~/.ssh/elice.pem elicer@central-01.tcp.tunnel.elice.io -p 27612
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
- Primary DRBC test (`2014-2016`): `configs/basin_splits/drbc_expanded_observed_test/test.txt` 기준 **85개**. extreme-rain stress test / checkpoint sensitivity 진단으로 대체 금지.

### Seed / epoch 정책

- 공식 paired seed: `111 / 222 / 444`. Model 2 seed `333`: NaN loss 중단. Model 1 seed `333`: fair comparison 위해 final aggregate 제외.
- Checkpoint sensitivity: 진단용만, primary epoch 재선정 금지.

### 산출물 경로 규칙

- 분석 결과 → `output/model_analysis/`
- Basin-side 결과 → `output/basin/`

#### model_analysis 분석 폴더 표준

주제(top-level) = 평가셋·분석 단위. 각 주제는 **평탄형** 또는 **그룹형** 하나만 쓴다. 섞지 않는다.

- **평탄형** (분석 1개): 주제 폴더 = `README.md` + `figures/` `tables/` `data/` `report/` `gallery/`
- **그룹형** (분석 2개+): 주제 폴더 = `README.md` + 하위 분석별 표준 폴더. 주제 직속에 `figures/`·`tables/`를 두지 않는다.

표준 하위 폴더 의미:

| 폴더 | 담는 것 |
| --- | --- |
| `figures/` | 결론용 대표 그림 (.png) |
| `tables/` | 수치 표 (.csv .parquet) |
| `data/` | 입력·중간물·캐시 (추론 원본, catalog, metadata, .geojson .json) |
| `report/` | 사람이 읽는 요약 (.md .html, summary .json) |
| `gallery/` | basin별 대량 그림. `figures/`와 분리 |

규칙:

- 그림은 `figures/`(또는 `gallery/`)에만 둔다. 다른 곳에 흩지 않는다.
- 주제·분석 폴더 root에 파일을 직접 두지 않는다. 전부 표준 하위 폴더로.
- 분석 폴더 안에 다른 분석 이름을 넣지 않는다. 최대 2단계. 더 깊어지면 별 주제로 분리.
- 한 분석이 여러 갈래면(예: 오차 원인 basin/forcing/attribution) 폴더를 더 파지 말고 파일명 prefix로 구분한다.

확정 top-level 구조:

| 주제 | 형태 | 하위 분석 |
| --- | --- | --- |
| `primary/` | 그룹 | `metrics/` · `calibration/` |
| `confirmed_flood/` | 평탄 | (NWS flood stage 기준 실제 홍수 event) |
| `q99_analysis/` | 그룹 | `performance/` · `causes/` |
| `band_signal/` | 그룹 | `band_shape/` · `slope_signal/` · `signal_sweep/` · `method_compare/` |
| `shap/` | 그룹 | `q99/` · `test_split/` |

`band_signal/` = 관측 첨두가 예측 밴드(q50~q99) 어디에 드는지(관측 위치 구간)와 그 위치를 예측하는 신호를 묶은 주제. `band_shape`(밴드 폭·꼬리·위치·gap), `slope_signal`(상승 기울기 신호), `signal_sweep`(위치 구간 신호 탐색), `method_compare`(상승부 onset 검출법 비교).

#### 파일명 규칙

- 폴더가 주는 맥락 prefix 제거: `confirmed_flood_`, `q99_`, `primary_` 등 폴더명과 중복되는 접두어.
- 실험맥락 prefix 제거: `subset300_`, `expanded_drbc_`. **"expanded" 용어는 쓰지 않는다** (모든 test·분석이 expanded이므로 군더더기).
- 식별자는 보존: `seed111/222/444`, `model1/model2`, `q50/q90/q95/q99`, `with_outliers/without_outliers`.
- 약어 처리: `ub_`(upper band) 접두는 제거한다. `band_signal/band_shape/` 폴더가 band 맥락을 주므로 `ub_band_shape_*`→`band_shape_*`, `ub_location_class_*`→`location_class_*` 식. 그 외 약어(`rq1~rq4`, `m3/m4`, `q99`)는 유지.

파일명은 생성 스크립트가 출력한다. 폴더·파일명 규칙을 바꾸면 **해당 스크립트의 출력 경로·파일명 문자열도 같은 작업에서 수정**한다.

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
