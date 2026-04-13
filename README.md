# CAMELS

CAMELS는 multi-basin LSTM 기반 수문 예측에서 극한 홍수 첨두 과소추정을 줄이는 방법을 비교하는 연구 저장소다.

비교 대상은 세 단계다.

1. deterministic multi-basin LSTM
2. probabilistic multi-basin LSTM
3. physics-guided probabilistic hybrid

## Current study setup

- 데이터셋: CAMELSH hourly
- 평가 지역: DRBC Delaware River Basin holdout
- 학습 풀: quality-pass non-DRBC CAMELSH basins
- 핵심 질문: output design과 physics guidance가 extreme flood underestimation을 얼마나 줄이는가

## Repository map

- `docs/README.md`: 사람이 읽는 문서의 기준 포털
- `docs/workflow/`: basin selection, screening, event workflow
- `docs/research/`: 모델 구조, 연구 설계, 실험 프로토콜
- `docs/references/`: 학습 노트와 보조 참고 자료
- `docs/meta/`: 문서 작성 규칙
- `scripts/`: 반복 가능한 데이터 준비와 실험 스크립트

## Current status

현재 저장소는 DRBC holdout basin 정의, non-DRBC training pool 정의, 정적 basin analysis, provisional screening까지 정리되어 있다. 다음 핵심 단계는 observed-flow 기반 event table과 final flood-prone screening을 붙여 Model 1과 Model 2 비교를 더 직접적으로 해석하는 것이다.

## Start here

문서 탐색은 [`docs/README.md`](docs/README.md)에서 시작한다.
