# CAMELS — Multi-Basin LSTM Flood Prediction

Multi-basin LSTM 기반 수문 예측에서 **극한 홍수 첨두 과소추정**을 줄이기 위한 연구 프로젝트.

Deterministic → Probabilistic → Physics-guided hybrid 세 모델을 단계적으로 비교한다.

## 디렉토리 구조

```text
.
├── agents.md            # 에이전트 작업 맥락
├── basins/
│   ├── drbc_boundary/   # DRBC Delaware River Basin 공식 경계
│   ├── huc8_delware/    # 초기 HUC8 exploratory shapefile
│   └── CAMELSH_data/    # CAMELSH shapefiles / attributes 추출본
├── configs/             # NeuralHydrology 실험 설정
├── data/CAMELS_US/
│   └── camels_attributes_v2.0/  # legacy CAMELS-US 속성 데이터
├── docs/
│   ├── workflow/        # basin 처리 절차와 데이터 준비 워크플로
│   └── research/        # architecture, design, literature-review
├── output/
│   └── basin/           # basin 관련 산출물
├── scripts/             # basin 전처리, download, run 스크립트
└── runs/                # (gitignored) 학습 출력
```

## 대상 유역

현재 basin 조사의 공식 기준은 DRBC의 `Delaware River Basin` 경계다.
실무 기준 레이어는 `basins/drbc_boundary/drb_bnd_polygon.shp`이고, HUC8 레이어는 초기 exploratory 참고자료로만 둔다.

## 환경

- **패키지 관리**: `uv`
- **실행**: `uv run`으로 재현 가능해야 함

## 현재 workflow

현재 basin screening과 basin cohort 정의의 기본 데이터셋은 CAMELSH다.
현재 기준 스크립트는 아래 두 개다.

- `scripts/download_camelsh_core.py`: Zenodo에서 `info.csv`, `attributes.7z`, `shapefiles.7z`를 내려받고 압축을 푼다.
- `scripts/build_drbc_camelsh_tables.py`: DRBC 공식 경계를 기준으로 CAMELSH basin subset과 overlap 진단 테이블을 생성한다.
- `scripts/build_drbc_camelsh_gpkg.py`: DRBC boundary, selected basins, outlets를 QGIS용 `GPKG`로 묶는다.

이전 HUC8 기반 exploratory 스크립트와 CAMELS-US 기반 초기 스크립트도 남아 있지만, 현재 프로젝트의 basin 기준과 기본 데이터셋은 각각 `DRBC boundary`, `CAMELSH`로 고정한다.

## 관련 문서

- [`agents.md`](agents.md) — 에이전트 작업 맥락 및 프로젝트 규칙
- [`docs/workflow/basin.md`](docs/workflow/basin.md) — basin 처리 절차, 단계별 목적, 현재 산출물 정리
- [`docs/research/architecture.md`](docs/research/architecture.md) — 모델 아키텍처 상세
- [`docs/research/design.md`](docs/research/design.md) — 실험 설계
- [`docs/research/literature-review.md`](docs/research/literature-review.md) — 선행연구 정리
