# CAMELS — Multi-Basin LSTM Flood Prediction

Multi-basin LSTM 기반 수문 예측에서 **극한 홍수 첨두 과소추정**을 줄이기 위한 연구 프로젝트.

Deterministic → Probabilistic → Physics-guided hybrid 세 모델을 단계적으로 비교한다.

## 디렉토리 구조

```text
.
├── agents.md            # 에이전트 작업 맥락
├── basins/
│   └── huc8_delware/    # Delaware basin HUC8 shapefile
├── configs/             # NeuralHydrology 실험 설정
├── data/CAMELS_US/
│   └── camels_attributes_v2.0/  # CAMELS 유역 속성 데이터
├── docs/
│   └── research/        # architecture, design, literature-review
├── scripts/             # download, run 스크립트
└── runs/                # (gitignored) 학습 출력
```

## 대상 유역

Delaware basin (HUC8). `basins/huc8_delware/`에 shapefile 형태로 보관.

## 환경

- **패키지 관리**: `uv`
- **실행**: `uv run`으로 재현 가능해야 함

## 관련 문서

- [`agents.md`](agents.md) — 에이전트 작업 맥락 및 프로젝트 규칙
- [`docs/research/architecture.md`](docs/research/architecture.md) — 모델 아키텍처 상세
- [`docs/research/design.md`](docs/research/design.md) — 실험 설계
- [`docs/research/literature-review.md`](docs/research/literature-review.md) — 선행연구 정리
