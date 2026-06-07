# Project Agent Context

코딩 에이전트가 CAMELS 프로젝트 작업 시 참조할 핵심 맥락.
연구 배경·논문 서술은 `docs/experiment/method/model/` 하위 문서 참조.

---

## 응답 및 문서 작성 스타일

- 응답, `docs/`, `report/` 본문은 한국어 기본.
- API, LSTM, SHAP, quantile, calibration, coverage, RandomForest, surrogate model 같은 고정 전문 용어는 영어 그대로. 일반 설명어·문장 연결·해석 문장은 한국어.
- 영어 사용은 필요한 고정 전문 용어와 코드 식별자에만 제한한다. 설명용 제목·표 머리글·일반 개념어는 가능한 한 한국어로 쓴다.
- 전문 용어, 자체 규정 단어, 새로 만든 지표명은 첫 등장 시 반드시 한국어 풀이를 붙인다. 예: `coverage`는 "관측값이 예측 quantile 아래에 들어오는 비율".
- `obs class`, `signal feature`, `risk tier`, `leakage`, `anchor`처럼 분석 과정에서 만든 내부 용어를 그대로 던지지 않는다. 각각 "관측 위치 구간", "신호 지표", "위험 단계", "관측값 누수", "계산 기준 시점"처럼 한국어 이름을 먼저 쓰고, 필요할 때만 괄호 안에 영어/코드명을 병기한다.
- HTML, dashboard, 발표자료, 설명 문서처럼 독자 이해가 목적인 산출물은 특히 영어 약어·내부 용어를 남발하지 않는다. 표와 그림에는 "무엇을 뜻하는 값인지"를 한 문장으로 풀어 쓴다.
- 논문·발표·연구 검토용 figure image(`figures/`, `gallery/`의 PNG/PDF/SVG) 안의 title, axis label, legend, colorbar, tick label은 영어로 작성한다. 특히 SHAP 분석 figure는 모든 chart에 간결한 영어 title을 둔다. 이 규칙은 본문 한국어 기본 규칙보다 우선한다.
- 연구용 figure에서는 plotting area 안에 설명 문장, seed/basin/prediction 같은 metadata 주석을 직접 넣지 않는다. 필요한 해석은 caption, report, manifest, 본문 문장처럼 figure 밖에 둔다. 단, SHAP bar의 bar-end value label과 SHAP force/waterfall처럼 공식 diagnostic plot API가 plot 구조상 표시하는 contribution value label은 예외로 두되, 표시 feature 수를 줄여 겹침과 과밀을 피한다.
- `docs/` 또는 `report/` 작성 시 대학생 수준 가독성. 순서: "무엇을 보는 분석인지" → "왜 필요한지" → "결과를 어떻게 해석해야 하는지".
- `docs/explain/` 설명 자료는 **수문학 전공 대학생** 기준으로 쓴다. 유역·하천 유량·홍수 첨두·재현기간·NSE/KGE 같은 수문학 기본 개념은 전제하고 다시 풀지 않는다. 반면 기계학습 배경(LSTM, quantile, calibration 등)은 전제하지 않고 첫 등장 시 한 번만 짚는다. 간결하게 쓰고 일상 비유·장황한 단계 풀이는 지양한다. 한국어 위주로 쓰며, 불가피한 고정 전문 용어만 영어로 둔다.
- 수식·지표·모델 구조 설명 시 정의와 직관적 의미 함께. 논문용 문장에서는 과장·미확인 인과 단정 금지.

## Paper draft / Notion 운영

- Notion은 논문 draft를 확인하고 수정하는 공간이다. 운영 규칙, export 절차, 원본 artifact 준비 방법은 Notion에 쓰지 않는다.
- Notion 문장은 논문 본문처럼 간결하게 쓴다. AI가 설명하는 듯한 말투, 작업 보고 말투, 장황한 안내문을 넣지 않는다.
- Notion page와 database title에는 이모지를 쓰지 않는다.
- `Draft`는 버전 관리를 위한 full-page database로 둔다. 각 논문 본문은 `Draft` database row page에 둔다.
- Draft version을 freeze하거나 export할 때의 절차와 보관 규칙은 repo 문서(`AGENTS.md`, `CLAUDE.md`, `draft/README.md`, `draft/notion_exports/README.md`)에서 관리한다.
- Notion 밖에서 준비하는 figure, table, export, source path, canonical 근거는 repo에 기록한다. Notion에는 논문 검토에 필요한 최종 draft 내용만 둔다.

---

## 연구 목표 (한 줄)

Multi-basin LSTM 기반 수문 예측에서 **극한 홍수 첨두 과소추정**을 줄이기 위해, deterministic baseline과 probabilistic quantile extension 비교. physics-guided hybrid는 후속 확장.

## 작업 제목

**Reducing Extreme Flood Underestimation with Probabilistic Extensions of Multi-Basin LSTM Models**

## 핵심 가설

1. Deterministic LSTM의 peak underestimation 상당 부분은 **output design** 문제. Probabilistic head만 추가해도 extreme flood 지표 의미 있게 개선 가능.
2. physics-guided core는 후속 연구에서 **timing과 basin generalization**에 추가 이득 가능성.
3. 이 후속 이득은 snow 또는 groundwater 영향이 큰 유역에서 더 크게 나타날 수 있음.

---

## 공식 비교 구조

| 모델    | 구조                                                            | 역할                                            |
| ------- | --------------------------------------------------------------- | ----------------------------------------------- |
| Model 1 | Deterministic multi-basin LSTM                                  | Baseline. 모든 개선은 이것 대비 비교            |
| Model 2 | Probabilistic multi-basin LSTM (backbone 동일, head만 quantile) | Output design만으로 peak bias가 줄어드는지 검증 |

`Model 3` 관련 conceptual core 설계 메모는 보존하되, 현재 논문 공식 비교축에는 미포함. 상세 아키텍처는 [`docs/experiment/method/model/architecture.md`](docs/experiment/method/model/architecture.md) 참조.

`scaling pilot`은 basin 수 결정용 운영 실험. deterministic Model 1로 전국 범위 stratified subset `100 / 300 / 600` 비교 후, non-DRBC train/validation basin 수는 `300` 고정. 선택 기준: `non-DRBC validation 성능 + static attribute distribution diagnostics + observed-flow event-response diagnostics + random same-size subset benchmark + compute cost`. DRBC holdout test metric으로 pilot basin 수 선택 금지. seed `111`의 `scaling_300` subset 고정, Model 1 / Model 2 seed `111 / 222 / 444` 동일 subset 재사용. 현재 공식 primary DRBC test split은 expanded observed 기준 **85개**이며 `configs/pilot/basin_splits/scaling_300/test.txt`는 `configs/basin_splits/drbc_expanded_observed_test/test.txt`와 같은 85개 유역을 사용한다. Model 2 seed `333`은 NaN loss로 중단, 공정한 paired-seed 비교를 위해 완료된 Model 1 seed `333`도 final aggregate 제외.

극한호우 보조 test는 subset300 primary DRBC test 대체 아님. hourly `Rainf`에서 만든 rain-event catalog로 train/validation exposure와 DRBC historical stress response 점검. `drbc_historical_stress`는 DRBC basin holdout 조건 유지하나 historical `1980-2024` 사용 → temporal independence claim 부적합. All-validation-epoch 결과는 checkpoint sensitivity 진단이며 stress/test 결과로 primary epoch 재선택 용도 아님.

---

## 프로젝트 범위

- **데이터셋**: CAMELSH hourly 기본. CAMELS-US local dataset 미사용, 로컬 데이터 의존성 제거.
- **시간 해상도**: 기본 hourly. 필요 시 후속에서 daily aggregation ablation 별도.
- **Backbone**: 첫 논문은 LSTM 고정. Transformer 등은 후속 분리.

## 입력 구성

- **Dynamic forcing**: `prcp`, `tmax`, `tmin`, `srad`, `vp`, 필요 시 `PET`
- **Static attributes**: area, slope, aridity, snow fraction, soil depth, permeability, forest fraction, baseflow index
- **Lagged Q**: 기본 모델 미포함. 후속 ablation 분리.

## 실험 Split

1. **Temporal split**: 동일 유역, 다른 시기
2. **Regional basin holdout (PUB/PUR)**: DRBC Delaware basin 전체를 holdout region, 나머지 basin으로 `global multi-basin model` 학습 후 DRBC에서 일반화 평가
3. **Extreme-event holdout**: basin별 상위 홍수 이벤트 일부를 학습 제외

## 평가 지표

- **전체 성능**: NSE, KGE, NSElog
- **Flood-specific** (핵심): FHV, Peak Relative Error, Peak Timing Error, top 1% flow recall, event-level RMSE
- **Probabilistic model 추가**: pinball loss, coverage, calibration

---

## 저장소 구조

```text
.
├── basins/              # CAMELSH 원자료·shapefile·DRBC 경계 → basins/AGENTS.md
│   ├── CAMELSH/         # (gitignored)
│   ├── CAMELSH_data/    # (gitignored)
│   ├── CAMELSH_download/ # (gitignored)
│   ├── drbc_boundary/
│   └── huc8_delware/
├── configs/             # 공식 basin split, scaling pilot config → configs/AGENTS.md
│   ├── basin_splits/
│   └── pilot/
├── data/                # NH-style CAMELSH generic 데이터셋 → data/AGENTS.md
│   └── CAMELSH_generic/
│       └── drbc_holdout_broad/  # (gitignored)
├── docs/                # 방법론·결과 분석·논문 문서 → docs/AGENTS.md
│   ├── archive/
│   ├── experiment/
│   ├── explain/
│   ├── paper/
│   ├── references/
│   └── templates/
├── dashboard/           # React 기반 실험 분석 대시보드 → dashboard/AGENTS.md
├── database/            # PostgreSQL/DuckDB 분석 cache와 import helper → database/AGENTS.md
├── scripts/             # 전처리·분석·figure·실험 실행 스크립트 → scripts/AGENTS.md
│   ├── _lib/            # 공용 script helper
│   ├── basin/           # 유역 screening·reference·diagnostic
│   ├── data/            # download·matching·NH generic data preparation
│   ├── model/           # Model 1/2 결과 분석·stress test·sequence helper
│   ├── ops/             # 서버·repo 운영 helper
│   ├── scaling/         # scaling pilot split·diagnostic·plot
│   └── runs/            # official/pilot/dev run 진입점
├── vendor/              # upstream NeuralHydrology 참조 코드 → vendor/AGENTS.md
│   └── neuralhydrology/
├── output/              # (gitignored) 분석·모델·발표 산출물 → output/AGENTS.md
├── runs/                # (gitignored) 학습 checkpoint → runs/AGENTS.md
├── logs/                # (gitignored) 실행 로그 → logs/AGENTS.md
└── tmp/                 # (gitignored) scratch / staging → tmp/AGENTS.md
```

각 디렉터리 상세 배치 규칙은 해당 `AGENTS.md` 참조.

### 최상위 디렉토리 역할

| 디렉토리 | 역할 | 작업 시 기준 |
| --- | --- | --- |
| `basins/` | CAMELSH 원자료, shapefile, DRBC boundary, static attributes 원천 자료 공간 | 원자료 직접 수정 금지, 변환은 script로 재현 가능하게. DRBC boundary 변경 = split 정의 변경. |
| `configs/` | 공식 basin split, fixed `scaling_300` subset, broad/pilot/dev config source-of-truth | split·핵심 config key/default 변경 시 공식 실험 조건 변경으로 보고 docs/scripts 함께 갱신. |
| `data/` | NeuralHydrology generic format으로 준비된 CAMELSH hourly dataset | prepared data는 재생성 가능한 gitignored 산출물. 공식 split 원본은 `configs/`. |
| `docs/` | 연구 방법, 분석 해석, 논문/발표 문서 | canonical 판단은 `docs/experiment/method/`와 `docs/experiment/analysis/` 우선. archive/reference/explain은 공식 근거 불가. |
| `dashboard/` | React 기반 실험 분석 대시보드와 UI snapshot asset | 분석 source-of-truth는 `output/`, `docs/experiment/analysis/`, `configs/`. dashboard는 표시용 UI + snapshot asset만. 디자인은 `vercel/DESIGN.md` 준수. |
| `database/` | PostgreSQL/DuckDB 분석 cache schema, import helper, local database artifact 경로 | 원본 source-of-truth 대체 불가. 반복 join 필요 summary는 PostgreSQL, 큰 CSV/Parquet 탐색은 DuckDB. `database/local/` 생성물은 git 불가. |
| `scripts/` | 전처리, screening, 분석, figure 생성, run 실행 진입점 | 새 코드는 `uv run` 실행 가능하게. runner → `scripts/runs/`, basin 분석 → `scripts/basin/`, 모델 결과 분석 → `scripts/model/`, scaling pilot 진단 → `scripts/scaling/`, 데이터 준비 → `scripts/data/`, 운영 helper → `scripts/ops/`. 산출물 → `output/`, 학습 run → `runs/`, scratch → `tmp/`. |
| `vendor/` | vendored NeuralHydrology upstream source | runtime dependency 직접 수정 금지. 수정 시 재현성 영향 문서화. |
| `output/` | 분석·모델·발표 산출물 gitignored 보관 공간 | code/config 불가. 공식/smoke/dev 결과 혼재 금지. 경로 변경 시 docs/scripts 갱신. |
| `runs/` | NeuralHydrology training run, checkpoint, validation output | checkpoint·optimizer state 임의 삭제·이동·평탄화 금지. 분석 결과는 가능하면 `output/` export. |
| `logs/` | 실행 로그·임시 진단 로그 | canonical 결과 표 아님, 재현성 보조 자료. 요약 결과는 `output/` 정리. |
| `tmp/` | scratch, staging, smoke test, 임시 다운로드/추출 공간 | canonical 산출물 아님. 보존할 결과는 `output/` 또는 `docs/`로 이동 후 metadata 보존. |

### Database 사용 기준

PostgreSQL과 DuckDB는 데이터 확인, JOIN, sanity check, DBeaver grid 탐색의 1차 조회 기준으로 사용 가능. basin 속성, event response/regime, model metric, probabilistic diagnostics 함께 비교 시 `analysis.*` typed table과 DuckDB view 우선 조회 가능.

단, 데이터 내용 수정 기준은 원본 artifact·generator script. DB 직접 `UPDATE`로 canonical data 수정 금지. 이상값 발견 시 `analysis.csv_files`의 `relative_path`, `sha256`, `imported_at`로 원본 확인 후 `output/`, `configs/`, `data/`의 원본 CSV 또는 생성 script 수정 → importer 재실행.

DB cache 구조 변경 (schema, importer, migration, DuckDB view 수정) 시 `database/`에서 처리. `database/local/` 생성물은 git 불가. 값 의미·해석 변경 시 관련 `docs/experiment/analysis/` 또는 source generator 문서 함께 갱신.

- **대상 유역**: Delaware River Basin Commission 기준 Delaware River Basin. 공식 기준 레이어: `basins/drbc_boundary/drb_bnd_polygon.shp`.
- **학습 전략**: DRBC는 regional holdout / evaluation region. 모델 학습은 outlet가 DRBC 밖이고 polygon overlap `0.1` 이하인 tolerant non-DRBC CAMELSH basin. 현재 backbone은 non-DRBC basin 학습 global multi-basin model.
- **DRBC 선택 기준**: `outlet_in_drbc == True` 및 `overlap_ratio_of_basin >= 0.9` → **154개** (outlet 기준만이면 192개).
- **Training pool 기준**: `outlet_in_drbc == False` 및 `overlap_ratio_of_basin <= 0.1`, 이후 usable year / estimated-flow fraction / boundary confidence quality gate 적용 → **1923개** quality-pass basin.

## output 분석 폴더 표준

`output/model_analysis/` 분석 산출물은 아래 표준을 따른다. 코드/config는 두지 않는다.

주제(top-level) = 평가셋·분석 단위. 각 주제는 **평탄형** 또는 **그룹형** 하나만 쓴다. 섞지 않는다.

- **평탄형** (분석 1개): 주제 폴더 = `README.md` + `figures/` `tables/` `data/` `report/` `gallery/`
- **그룹형** (분석 2개+): 주제 폴더 = `README.md` + 하위 분석별 표준 폴더. 주제 직속에 `figures/`·`tables/`를 두지 않는다.

| 표준 하위 폴더 | 담는 것 |
| --- | --- |
| `figures/` | 결론용 대표 그림 (.png) |
| `tables/` | 수치 표 (.csv .parquet) |
| `data/` | 입력·중간물·캐시 (추론 원본, catalog, metadata, .geojson .json) |
| `report/` | 사람이 읽는 요약 (.md .html, summary .json) |
| `gallery/` | basin별 대량 그림. `figures/`와 분리 |

배치 규칙:

- 그림은 `figures/`(또는 `gallery/`)에만. 다른 곳에 흩지 않는다.
- 주제·분석 폴더 root에 파일을 직접 두지 않는다. 전부 표준 하위 폴더로.
- 분석 폴더 안에 다른 분석 이름을 넣지 않는다. 최대 2단계. 더 깊어지면 별 주제로 분리.
- 한 분석이 여러 갈래면(예: 오차 원인 basin/forcing/attribution) 폴더를 더 파지 말고 파일명 prefix로 구분.

확정 top-level 구조:

| 주제 | 형태 | 하위 분석 |
| --- | --- | --- |
| `primary/` | 그룹 | `metrics/` · `calibration/` |
| `confirmed_flood/` | 평탄 | NWS flood stage 기준 실제 홍수 event |
| `q99_analysis/` | 그룹 | `performance/` · `causes/` |
| `band_signal/` | 그룹 | `band_shape/` · `slope_signal/` · `signal_sweep/` · `method_compare/` |
| `shap/` | 그룹 | `q99/` · `test_split/` · `direction/` |

`band_signal/` = 관측 첨두가 예측 밴드(q50~q99) 어디에 드는지(관측 위치 구간)와 그 위치를 예측하는 신호를 묶은 주제. 하위: `band_shape`(밴드 폭·꼬리·위치·gap), `slope_signal`(상승 기울기 신호), `signal_sweep`(위치 구간 신호 탐색), `method_compare`(상승부 onset 검출법 비교).

파일명 규칙:

- 폴더가 주는 맥락 prefix 제거: `confirmed_flood_`, `q99_`, `primary_` 등 폴더명과 중복되는 접두어.
- 실험맥락 prefix 제거: `subset300_`, `expanded_drbc_`. **"expanded" 용어는 쓰지 않는다** (모든 test·분석이 expanded).
- 식별자는 보존: `seed111/222/444`, `model1/model2`, `q50/q90/q95/q99`, `with_outliers/without_outliers`.
- 약어: `ub_`(upper band) 접두 제거. `band_signal/band_shape/` 폴더가 band 맥락을 주므로 `ub_band_shape_*`→`band_shape_*`, `ub_location_class_*`→`location_class_*` 식. 그 외(`rq1~rq4`, `m3/m4`, `q99`)는 유지.

파일명은 생성 스크립트가 출력한다. 폴더·파일명 규칙 변경 시 해당 스크립트의 출력 경로·파일명 문자열도 같은 작업에서 수정한다. 상세 레이아웃은 `output/AGENTS.md` 참조(이 표준과 동기화 유지).

## 개발 환경 규칙

- **패키지 관리**: `uv` 표준. 새 코드는 `uv run` 실행 가능해야 함.
- **터미널 PATH**: `uv`, `python`, `soffice`, `brew` 등 Homebrew 도구 사용 시 항상 `export PATH="/opt/homebrew/bin:$PATH"` 먼저 적용.

## Subagents 사용 원칙

작업이 독립 축으로 분리되거나 코드베이스 조사와 구현 검증 병렬 처리로 시간 단축 가능 시 subagents 적극 사용. 대상: 넓은 코드베이스 탐색, 문서 정합성 점검, 테스트 실패 원인 조사, 파일 범위가 다른 구현 작업.

Subagent 위임 시 책임 범위 좁고 명확하게 지정. 코드 변경 작업이면 담당 파일·모듈 분리 명시. 다른 agent·사용자 변경 되돌리지 말고 맞춰 작업 명시.

Main agent는 최종 통합 책임. 반환된 변경 사항·근거 검토, 공식 실험 설정·데이터 경로·문서 정합성 규칙 충돌 확인, 필요한 테스트·sanity check 직접 수행.

Subagents 남용 금지. 단순 한 파일 수정, 즉시 확인 가능한 명령 실행, 바로 다음 단계가 특정 조사 결과에 막힌 작업은 main agent 직접 처리. 병렬 작업 구성 시 중복 조사·동일 파일 동시 수정 방지.

## 원격 실행 메모

- 현재 Elice GPU 인스턴스 접속 기준:
- 사용자 이름: `elicer`
- 접속 주소: `central-02.tcp.tunnel.elice.io:23818`
- SSH 비밀키: `/Users/jang-minyeop/.ssh/elice.pem`
- 원격 서버 OS: `Ubuntu 22.04.5 LTS`
- 재접속 예시: `ssh -i /Users/jang-minyeop/.ssh/elice.pem elicer@central-01.tcp.tunnel.elice.io -p 27612`
- `export PATH="/opt/homebrew/bin:$PATH"` 규칙은 **로컬 macOS 터미널에서만** 적용. 원격 Ubuntu 인스턴스에서는 Homebrew PATH 추가 금지, 필요 시 `~/.local/bin` 같은 사용자 로컬 PATH만 사용.

## 문서 정합성 유지 규칙

파일 구조, 공식 실험 설정, 연구 질문, workflow, 실행 진입점, 산출물 위치 추가/삭제/변경 시 `canonical` 범위 영향 여부 먼저 판단.

아래 항목에 영향 있으면 코드 변경과 같은 작업 안에서 관련 문서 함께 갱신:

- `AGENTS.md`
- `README.md`
- `docs/README.md`
- 해당 canonical `docs/experiment/method/model/`, `docs/experiment/method/` 문서
- `docs/experiment/analysis/model/` 분석 문서 (산출물 경로·실험 설정 변경 시)
- 관련 `configs/README.md`, `scripts/README.md`, 실행 스크립트

아래 변경은 문서 동기화 필수:

- 공식 모델 비교축 변경
- 공식 config key 또는 기본값 변경
- split source-of-truth 변경
- 파일/폴더 경로 이동 또는 이름 변경
- 공식 실행 진입점 변경
- 산출물 저장 위치 변경

dev-only 실험, local sanity 설정, exploratory 메모, archive 이동 등 공식 기준에 직접 영향 없는 변경은 `AGENTS.md` 갱신 불필요. 해당 `dev` 또는 `archive` 문서만 갱신.

## 구현 순서 원칙

**완료**
1. Basin 조사: DRBC holdout 확정 → non-DRBC training pool 확정 → static/profile 분석 → flood-relevant screening
2. Model 1 (deterministic) 학습 — seed 111 / 222 / 444
3. Model 2 (probabilistic, quantile head) 학습 — seed 111 / 222 / 444
4. Primary 성능 분석, extreme-rain stress test, checkpoint sensitivity 진단

**후속 (논문 범위 외)**
- Model 3 (physics-guided hybrid): exploratory / future work
- Natural subset robustness (`07`), probabilistic calibration pinball (`08`): 예정
