# Project Agent Context

이 문서는 코딩 에이전트가 CAMELS 프로젝트에서 작업할 때 참조해야 할 핵심 맥락을 정리한 것이다.
연구 배경의 일반론이나 논문 서술 방향은 `docs/experiment/method/model/` 하위 문서를 참조한다.

---

## 연구 목표 (한 줄)

Multi-basin LSTM 기반 수문 예측에서 **극한 홍수 첨두 과소추정**을 줄이기 위해, deterministic baseline과 probabilistic quantile extension을 비교한다. physics-guided hybrid는 후속 확장으로 둔다.

## 작업 제목

**Reducing Extreme Flood Underestimation with Probabilistic Extensions of Multi-Basin LSTM Models**

## 핵심 가설

1. Deterministic LSTM의 peak underestimation 상당 부분은 **output design** 문제이다. Probabilistic head만 추가해도 extreme flood 지표가 의미 있게 좋아질 수 있다.
2. physics-guided core는 후속 연구에서 **timing과 basin generalization**에 추가 이득을 줄 가능성이 있다.
3. 이 후속 이득은 snow 영향 또는 groundwater 영향이 큰 유역에서 더 크게 나타날 수 있다.

---

## 공식 비교 구조

| 모델    | 구조                                                            | 역할                                            |
| ------- | --------------------------------------------------------------- | ----------------------------------------------- |
| Model 1 | Deterministic multi-basin LSTM                                  | Baseline. 모든 개선은 이것 대비 비교            |
| Model 2 | Probabilistic multi-basin LSTM (backbone 동일, head만 quantile) | Output design만으로 peak bias가 줄어드는지 검증 |

`Model 3` 관련 conceptual core 설계 메모는 남겨 두되, 현재 논문의 공식 비교축에는 포함하지 않는다. 자세한 아키텍처는 [`docs/experiment/method/model/architecture.md`](docs/experiment/method/model/architecture.md) 참조.

`scaling pilot`은 basin 수를 정하기 위한 운영 결정용 실험이었다. deterministic Model 1로 전국 범위 stratified subset `100 / 300 / 600`을 비교한 뒤, 현재 compute-constrained main comparison의 non-DRBC train/validation basin 수는 `300`으로 고정한다. 이 선택은 `non-DRBC validation 성능 + static attribute distribution diagnostics + observed-flow event-response diagnostics + random same-size subset benchmark + compute cost`를 함께 보고 내리며, DRBC holdout test metric으로 pilot basin 수를 고르지 않는다. 현재 seed `111`에서 사용한 `scaling_300` subset을 고정하고, Model 1 / Model 2 seed `111 / 222 / 444`가 같은 subset을 그대로 재사용한다. Model 2 seed `333`은 NaN loss로 중단되었고, 공정한 paired-seed 비교를 위해 완료된 Model 1 seed `333`도 final aggregate에서 제외한다.

극한호우 보조 test는 subset300 primary DRBC test를 대체하지 않고, hourly `Rainf`에서 직접 만든 rain-event catalog로 train/validation exposure와 DRBC historical stress response를 점검한다. `drbc_historical_stress`는 DRBC basin holdout 조건은 유지하지만 historical `1980-2024` 기간을 쓰므로 temporal independence claim에는 사용하지 않는다. All-validation-epoch 결과는 checkpoint sensitivity 진단이며 stress/test 결과로 primary epoch를 다시 고르는 용도가 아니다.

---

## 프로젝트 범위

- **데이터셋**: CAMELSH hourly를 기본 데이터셋으로 사용한다. CAMELS-US local dataset은 사용하지 않으며 로컬 데이터 의존성에서 제거한다.
- **시간 해상도**: 기본은 시간 단위(hourly)다. 필요 시 후속 단계에서 daily aggregation ablation을 별도로 둘 수 있다.
- **Backbone**: 첫 논문에서는 LSTM 고정. Transformer 등은 후속으로 분리.

## 입력 구성

- **Dynamic forcing**: `prcp`, `tmax`, `tmin`, `srad`, `vp`, 필요 시 `PET`
- **Static attributes**: area, slope, aridity, snow fraction, soil depth, permeability, forest fraction, baseflow index
- **Lagged Q**: 기본 모델에는 미포함. 후속 ablation으로 분리.

## 실험 Split

1. **Temporal split**: 같은 유역, 다른 시기
2. **Regional basin holdout (PUB/PUR)**: DRBC Delaware basin 전체를 holdout region으로 두고, 나머지 basin으로 `global multi-basin model`을 학습한 뒤 DRBC에서 일반화를 평가
3. **Extreme-event holdout**: basin별 상위 홍수 이벤트 일부를 학습에서 배제

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

각 디렉터리의 상세 배치 규칙은 해당 `AGENTS.md`를 참조한다.

### 최상위 디렉토리 역할

| 디렉토리 | 역할 | 작업 시 기준 |
| --- | --- | --- |
| `basins/` | CAMELSH 원자료, shapefile, DRBC boundary, static attributes 같은 원천 자료 공간 | 원자료는 직접 수정하지 않고, 변환은 script로 재현 가능하게 만든다. DRBC boundary 변경은 split 정의 변경으로 본다. |
| `configs/` | 공식 basin split, fixed `scaling_300` subset, broad/pilot/dev config의 source-of-truth | split이나 핵심 config key/default를 바꾸면 공식 실험 조건 변경으로 보고 docs/scripts를 함께 갱신한다. |
| `data/` | NeuralHydrology generic format으로 준비된 CAMELSH hourly dataset | prepared data는 재생성 가능한 gitignored 산출물이다. 공식 split 원본은 `configs/`에 둔다. |
| `docs/` | 연구 방법, 분석 해석, 논문/발표 문서 | canonical 판단은 `docs/experiment/method/`와 `docs/experiment/analysis/`를 우선하고, archive/reference/explain은 공식 근거로 쓰지 않는다. |
| `scripts/` | 전처리, screening, 분석, figure 생성, run 실행 진입점 | 새 코드는 `uv run`으로 실행 가능하게 두고, 실행 성격의 runner는 `scripts/runs/`, basin 분석은 `scripts/basin/`, 모델 결과 분석은 `scripts/model/`, scaling pilot 진단은 `scripts/scaling/`, 데이터 준비는 `scripts/data/`, 운영 helper는 `scripts/ops/`에 둔다. 산출물은 `output/`, 학습 run은 `runs/`, scratch는 `tmp/`로 보낸다. |
| `vendor/` | vendored NeuralHydrology upstream source | 일부 workflow에서 runtime dependency로 쓰이므로 직접 수정은 피하고, 수정 시 재현성 영향을 문서화한다. |
| `output/` | 분석·모델·발표 산출물의 gitignored 보관 공간 | code/config를 두지 않는다. 공식 결과와 smoke/dev 결과를 섞지 않고, 경로 변경 시 docs/scripts를 갱신한다. |
| `runs/` | NeuralHydrology training run, checkpoint, validation output | checkpoint와 optimizer state는 임의 삭제·이동·평탄화하지 않는다. 분석 결과는 가능하면 `output/`으로 export한다. |
| `logs/` | 실행 로그와 임시 진단 로그 | canonical 결과 표가 아니라 재현성 보조 자료로 취급한다. 요약 결과는 `output/`에 정리한다. |
| `tmp/` | scratch, staging, smoke test, 임시 다운로드/추출 공간 | canonical 산출물이 아니다. 보존할 결과는 `output/` 또는 `docs/`로 옮기고 metadata를 남긴다. |

- **대상 유역**: Delaware River Basin Commission 기준 Delaware River Basin. 공식 기준 레이어는 `basins/drbc_boundary/drb_bnd_polygon.shp`.
- **학습 전략**: DRBC는 regional holdout / evaluation region으로 둔다. 모델 학습은 outlet가 DRBC 밖에 있고 polygon overlap이 `0.1` 이하인 tolerant non-DRBC CAMELSH basin에서 수행한다. 즉 현재 backbone은 Delaware regional model이 아니라, non-DRBC basin으로 학습한 global multi-basin model이다.
- **DRBC 선택 기준**: `outlet_in_drbc == True` 및 `overlap_ratio_of_basin >= 0.9` → **154개** (outlet 기준만이면 192개).
- **Training pool 기준**: `outlet_in_drbc == False` 및 `overlap_ratio_of_basin <= 0.1`, 이후 usable year / estimated-flow fraction / boundary confidence quality gate 적용 → **1923개** quality-pass basin.

## 개발 환경 규칙

- **패키지 관리**: `uv` 표준. 새 코드는 `uv run`으로 실행 가능해야 한다.
- **터미널 PATH**: `uv`, `python`, `soffice`, `brew` 등 Homebrew 도구를 사용할 때는 항상 먼저 `export PATH="/opt/homebrew/bin:$PATH"`를 적용한다.

## Subagents 사용 원칙

작업이 여러 독립 축으로 나뉘거나, 코드베이스 조사와 구현 검증을 병렬로 진행하면 시간이 줄어드는 경우에는 subagents를 적극적으로 사용한다. 예를 들어 넓은 코드베이스 탐색, 문서 정합성 점검, 테스트 실패 원인 조사, 서로 다른 파일 범위의 구현 작업은 subagent에 맡기기 좋은 대상이다.

Subagent에게 일을 맡길 때는 책임 범위를 좁고 명확하게 지정한다. 코드 변경 작업이면 담당 파일 또는 모듈을 분리해서 알려 주고, 다른 agent나 사용자의 변경을 되돌리지 말고 그 변경과 함께 맞춰 작업하라고 명시한다.

Main agent는 subagents의 결과를 그대로 합치는 데서 끝내지 말고, 최종 통합 책임을 진다. 반환된 변경 사항과 근거를 검토하고, 프로젝트의 공식 실험 설정, 데이터 경로, 문서 정합성 규칙과 충돌하지 않는지 확인한 뒤 필요한 테스트나 sanity check를 직접 수행한다.

Subagents를 남용하지는 않는다. 단순한 한 파일 수정, 즉시 확인 가능한 명령 실행, 바로 다음 단계가 특정 조사 결과에 막혀 있는 작업은 main agent가 직접 처리한다. 병렬 작업을 만들 때는 중복 조사나 같은 파일 동시 수정이 생기지 않도록 역할을 분리한다.

## 원격 실행 메모

- 현재 Elice GPU 인스턴스 작업용 접속 정보는 아래를 기준으로 한다.
- 사용자 이름: `elicer`
- 접속 주소: `central-02.tcp.tunnel.elice.io:15699`
- SSH 비밀키 루트: `/Users/jang-minyeop/.ssh/elice.pem`
- 원격 서버 OS: `Ubuntu 22.04.5 LTS`
- 원격 실험을 다시 붙일 때는 예를 들어 `ssh -i /Users/jang-minyeop/.ssh/elice.pem elicer@central-02.tcp.tunnel.elice.io -p 15699` 형식을 사용한다.
- `export PATH="/opt/homebrew/bin:$PATH"` 규칙은 **로컬 macOS 터미널에서만** 적용한다. 원격 Ubuntu 인스턴스에서는 Homebrew PATH를 추가하지 말고, 필요하면 `~/.local/bin` 같은 사용자 로컬 PATH만 잡는다.

## 문서 정합성 유지 규칙

프로젝트의 파일 구조, 공식 실험 설정, 연구 질문, workflow, 실행 진입점, 산출물 위치가 추가/삭제/변경되면, 그 변경이 `canonical` 범위에 영향을 주는지 먼저 판단한다.

다음 항목에 영향이 있으면, 코드 변경과 같은 작업 안에서 관련 문서를 함께 갱신한다.

- `AGENTS.md`
- `README.md`
- `docs/README.md`
- 해당 canonical `docs/experiment/method/model/`, `docs/experiment/method/` 문서
- `docs/experiment/analysis/model/` 분석 문서 (산출물 경로·실험 설정 변경 시)
- 관련 `configs/README.md`, `scripts/README.md`, 실행 스크립트

특히 아래 변경은 문서 동기화를 필수로 한다.

- 공식 모델 비교축 변경
- 공식 config key 또는 기본값 변경
- split source-of-truth 변경
- 파일/폴더 경로 이동 또는 이름 변경
- 공식 실행 진입점 변경
- 산출물 저장 위치 변경

반대로 dev-only 실험, local sanity 설정, exploratory 메모, archive 이동처럼 공식 기준에 직접 영향을 주지 않는 변경은 `AGENTS.md`까지 반드시 갱신할 필요는 없다. 이 경우에는 해당 `dev` 또는 `archive` 문서만 갱신한다.

## 구현 순서 원칙

**완료**
1. Basin 조사: DRBC holdout 확정 → non-DRBC training pool 확정 → static/profile 분석 → flood-relevant screening
2. Model 1 (deterministic) 학습 — seed 111 / 222 / 444
3. Model 2 (probabilistic, quantile head) 학습 — seed 111 / 222 / 444
4. Primary 성능 분석, extreme-rain stress test, checkpoint sensitivity 진단

**후속 (논문 범위 외)**
- Model 3 (physics-guided hybrid): exploratory / future work
- Natural subset robustness (`07`), probabilistic calibration pinball (`08`): 예정
