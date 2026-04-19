# Project Agent Context

이 문서는 코딩 에이전트가 CAMELS 프로젝트에서 작업할 때 참조해야 할 핵심 맥락을 정리한 것이다.
연구 배경의 일반론이나 논문 서술 방향은 `docs/research/` 하위 문서를 참조한다.

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

| 모델 | 구조 | 역할 |
|------|------|------|
| Model 1 | Deterministic multi-basin LSTM | Baseline. 모든 개선은 이것 대비 비교 |
| Model 2 | Probabilistic multi-basin LSTM (backbone 동일, head만 quantile) | Output design만으로 peak bias가 줄어드는지 검증 |

`Model 3` 관련 conceptual core 설계 메모는 남겨 두되, 현재 논문의 공식 비교축에는 포함하지 않는다. 자세한 아키텍처는 [`docs/research/architecture.md`](docs/research/architecture.md) 참조.

`scaling pilot`은 별도 운영 결정용 실험이다. deterministic Model 1만 사용해 전국 범위 stratified subset `100 / 300 / 600`에서 basin 수를 줄여도 되는지 먼저 점검하고, 이 결과로 최종 main comparison basin 수를 정한다. 이 pilot은 본문용 `Model 1 vs Model 2` 공식 비교 결과로 직접 보고하지 않는다. basin 수 선택은 `non-DRBC validation 성능 + static attribute distribution diagnostics + compute cost`를 함께 보고 내리며, DRBC holdout test metric으로 pilot basin 수를 고르지 않는다.

---

## 프로젝트 범위

- **데이터셋**: CAMELSH hourly를 기본 데이터셋으로 사용한다. CAMELS-US daily는 legacy 비교 또는 참고 자료로만 둔다.
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

## 현재 저장소 상태

```text
.
├── basins/
│   ├── CAMELSH/         # CAMELSH upstream 로컬 체크아웃 (gitignored)
│   ├── CAMELSH_data/    # CAMELSH shapefiles / attributes / hourly observed 추출본 (gitignored)
│   ├── CAMELSH_download/ # CAMELSH 원본 다운로드 보관 디렉터리 (gitignored)
│   ├── drbc_boundary/   # DRBC Delaware River Basin 공식 경계
│   └── huc8_delware/    # 초기 HUC8 exploratory shapefile / QGIS 자산
├── configs/
│   ├── basin_splits/    # official raw holdout / training pool basin split 산출물
│   └── pilot/           # scaling pilot 전용 config와 stratified subset split
├── data/
│   ├── CAMELSH_generic/
│   │   └── drbc_holdout_broad/  # NH-style CAMELSH generic 데이터셋 (gitignored)
│   └── CAMELS_US/
│       ├── basin_mean_forcing/  # legacy forcing 원본 (gitignored)
│       ├── camels_attributes_v2.0/  # legacy CAMELS-US 속성 데이터
│       └── usgs_streamflow/     # legacy streamflow 원본 (gitignored)
├── docs/
│   ├── learn/           # 참고 학습 메모
│   ├── references/      # glossary, proposal, planning 문서
│   ├── research/        # architecture, design, literature-review
│   └── workflow/        # basin selection / screening 워크플로
├── scripts/             # 다운로드, 전처리, 분석, 실행 스크립트
│   └── pilot/           # scaling pilot subset 생성 및 실행 스크립트
├── vendor/
│   └── neuralhydrology/ # upstream 코드 참조용 vendor copy
├── output/              # (gitignored) basin 분석 산출물, 필요 시 생성
├── runs/                # (gitignored) 학습 출력, 필요 시 생성
└── tmp/                 # (gitignored) scratch / download staging, 필요 시 생성
```

- **대상 유역**: Delaware River Basin Commission 기준 Delaware River Basin. 공식 기준 레이어는 `basins/drbc_boundary/drb_bnd_polygon.shp`.
- **학습 전략**: DRBC는 regional holdout / evaluation region으로 둔다. 모델 학습은 outlet가 DRBC 밖에 있고 polygon overlap이 `0.1` 이하인 tolerant non-DRBC CAMELSH basin에서 수행한다. 즉 현재 backbone은 Delaware regional model이 아니라, non-DRBC basin으로 학습한 global multi-basin model이다.
- CAMELSH shapefile과 attributes 추출본은 `basins/CAMELSH_data/` 아래에 둔다.
- Static attributes (`camels_attributes_v2.0/`)는 legacy 참고 자료이므로 유지한다.
- 생성 산출물은 기본적으로 gitignored 디렉터리인 `output/`, `runs/`, `tmp/` 아래에 둔다.
- DRBC 기준 CAMELSH subset 산출물은 `output/basin/drbc_camelsh/` 아래에 둔다.
- global training pool 관련 산출물은 `output/basin/camelsh_training_non_drbc/` 아래에 둔다.
- 현재 선택 규칙은 `outlet_in_drbc == True`와 `overlap_ratio_of_basin >= 0.9`이고, 이에 해당하는 basin은 `154개`다. outlet만 기준으로 보면 `192개`다.
- 현재 training pool 규칙은 `outlet_in_drbc == False` 이고 `overlap_ratio_of_basin <= 0.1`까지는 source mismatch에 따른 small overlap으로 허용하는 것이다. 그다음 usable year / estimated-flow fraction / boundary confidence quality gate를 적용한다. 현재 quality-pass training basin은 `1923개`다.
- compute 절감용 scaling pilot은 이 `1923개` raw non-DRBC broad pool을 source-of-truth로 보되, 실행 가능한 subset은 broad prepared split manifest를 통해 `train 1705 / validation 198`의 prepared broad basin에서 뽑는다. 현재 HUC02-stratified pilot subset `100 / 300 / 600`, prepared pool manifest, 그리고 static attribute distribution diagnostics는 `configs/pilot/` 아래에 둔다.
- 현재 `scripts/build_drbc_basin_analysis_table.py`로 static basin analysis table을 생성하며, 결과는 `output/basin/drbc_camelsh/analysis/` 아래에 둔다.
- 다음 단계는 DRBC holdout basin들에 forcing/streamflow 품질 정보와 event-level 지표를 붙여 flood-prone screening으로 넘어가는 것이다.

## 개발 환경 규칙

- **패키지 관리**: `uv` 표준. 새 코드는 `uv run`으로 실행 가능해야 한다.
- **터미널 PATH**: `uv`, `python`, `soffice`, `brew` 등 Homebrew 도구를 사용할 때는 항상 먼저 `export PATH="/opt/homebrew/bin:$PATH"`를 적용한다.
- **전처리/분석**: Python 스크립트 또는 notebook. DRBC holdout subset 정의, non-DRBC training pool 정의, 속성 병합, 홍수 취약 후보 추출 등을 수행한다.
- **반복 가능성**: one-off 분석이 아닌 반복 가능한 스크립트 형태로 유지.

## 원격 실행 메모

- 현재 Elice GPU 인스턴스 작업용 접속 정보는 아래를 기준으로 한다.
- 사용자 이름: `elicer`
- 접속 주소: `central-01.tcp.tunnel.elice.io:23894`
- SSH 비밀키 루트: `/Users/jang-minyeop/.ssh/elice.pem`
- 원격 서버 OS: `Ubuntu 22.04.5 LTS`
- 원격 실험을 다시 붙일 때는 예를 들어 `ssh -i /Users/jang-minyeop/.ssh/elice.pem elicer@central-01.tcp.tunnel.elice.io -p 23894` 형식을 사용한다.
- `export PATH="/opt/homebrew/bin:$PATH"` 규칙은 **로컬 macOS 터미널에서만** 적용한다. 원격 Ubuntu 인스턴스에서는 Homebrew PATH를 추가하지 말고, 필요하면 `~/.local/bin` 같은 사용자 로컬 PATH만 잡는다.

## 문서 정합성 유지 규칙

프로젝트의 파일 구조, 공식 실험 설정, 연구 질문, workflow, 실행 진입점, 산출물 위치가 추가/삭제/변경되면, 그 변경이 `canonical` 범위에 영향을 주는지 먼저 판단한다.

다음 항목에 영향이 있으면, 코드 변경과 같은 작업 안에서 관련 문서를 함께 갱신한다.

- `AGENTS.md`
- `README.md`
- `docs/README.md`
- 해당 canonical `docs/research/`, `docs/workflow/` 문서
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

1. Model 1 (deterministic) → Model 2 (probabilistic) 순서로 먼저 재현 가능하게 구현
2. Model 3 (physics-guided hybrid)은 현재 논문 범위 밖의 exploratory / future work로 둔다
3. 모델 학습 전에 **basin 조사 단계** 선행: DRBC boundary 기준 holdout subset 확정 → non-DRBC training pool 확정 → DRBC selected basin static/profile 분석 → forcing/streamflow 결합 → flood-prone basin screening table 생성
