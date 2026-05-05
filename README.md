# CAMELSH — Multi-Basin LSTM Flood Prediction

Multi-basin LSTM 기반 수문 예측에서 **극한 홍수 첨두 과소추정**을 줄이기 위한 연구 프로젝트.

공식 비교축은 `Deterministic LSTM → Probabilistic quantile LSTM` 두 모델이다. `physics-guided hybrid`는 후속 확장으로 둔다.

---

## 디렉토리 구조

```text
.
├── basins/              # CAMELSH 원자료·shapefile·DRBC 경계 → basins/AGENTS.md
├── configs/             # 공식 basin split, scaling pilot config → configs/README.md
├── data/                # NH-style CAMELSH generic 데이터셋 → data/AGENTS.md
├── docs/                # 방법론·결과 분석·논문 문서 → docs/README.md
├── scripts/             # 전처리·분석·실험 실행 스크립트 → scripts/README.md
├── vendor/              # upstream NeuralHydrology 참조 코드
├── output/              # (gitignored) 분석·모델 산출물
├── runs/                # (gitignored) 학습 checkpoint
├── logs/                # (gitignored) 실행 로그
└── tmp/                 # (gitignored) scratch / staging
```

---

## 실험 설계 요약

| 항목 | 내용 |
| --- | --- |
| 데이터셋 | CAMELSH hourly |
| 학습 전략 | non-DRBC basin으로 학습한 global multi-basin model |
| Holdout region | DRBC Delaware River Basin (154개 basin) |
| Training pool | quality-pass non-DRBC basin 1923개, 고정 subset 300개 사용 |
| 공식 seed | 111 / 222 / 444 (Model 1 & Model 2 공통) |
| 시간 split | train 2000–2010 / validation 2011–2013 / test 2014–2016 |

---

## 관련 문서

| 문서 | 역할 |
| --- | --- |
| [`AGENTS.md`](AGENTS.md) | 에이전트 작업 맥락 및 프로젝트 규칙 |
| [`docs/experiment/README.md`](docs/experiment/README.md) | 공식 방법·분석 문서 구조 및 읽기 순서 |
| [`docs/experiment/method/data/data_processing_analysis_guide.md`](docs/experiment/method/data/data_processing_analysis_guide.md) | 원자료 → 분석 산출물 end-to-end 처리 흐름 |
| [`scripts/README.md`](scripts/README.md) | data/basin/ops/runs 스크립트 역할 및 실행 순서 |
| [`configs/README.md`](configs/README.md) | canonical config, pilot config, raw split 역할 구분 |
| [`docs/README.md`](docs/README.md) | `docs/` 전체 문서 인덱스 |

---

## 환경

```bash
# 패키지 관리: uv
uv run <script.py>

# 원격 접속 (Elice GPU)
ssh -i ~/.ssh/elice.pem elicer@central-02.tcp.tunnel.elice.io -p 15699
```
