# Project Agent Context

이 문서는 코딩 에이전트가 CAMELS 프로젝트에서 작업할 때 참조해야 할 핵심 맥락을 정리한 것이다.
연구 배경의 일반론이나 논문 서술 방향은 `docs/research/` 하위 문서를 참조한다.

---

## 연구 목표 (한 줄)

Multi-basin LSTM 기반 수문 예측에서 **극한 홍수 첨두 과소추정**을 줄이기 위해, deterministic → probabilistic → physics-guided hybrid 세 모델을 단계 비교한다.

## 작업 제목

**Reducing Extreme Flood Underestimation with Probabilistic and Physics-Guided Extensions of Multi-Basin LSTM Models**

## 핵심 가설

1. Deterministic LSTM의 peak underestimation 상당 부분은 **output design** 문제이다. Probabilistic head만 추가해도 extreme flood 지표가 의미 있게 좋아질 수 있다.
2. Physics-guided core를 얹으면 **timing과 basin generalization**에서 추가 이득이 있을 수 있다.
3. 이 추가 이득은 snow 영향 또는 groundwater 영향이 큰 유역에서 더 크게 나타날 수 있다.

---

## 세 모델 비교 구조

| 모델 | 구조 | 역할 |
|------|------|------|
| Model 1 | Deterministic multi-basin LSTM | Baseline. 모든 개선은 이것 대비 비교 |
| Model 2 | Probabilistic multi-basin LSTM (backbone 동일, head만 quantile) | Output design만으로 peak bias가 줄어드는지 검증 |
| Model 3 | Physics-guided probabilistic hybrid (flux/bounded-coefficient head + conceptual core) | Probabilistic만으로 부족한 부분이 있는지 확인 |

자세한 아키텍처는 [`docs/research/architecture.md`](docs/research/architecture.md) 참조.

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
2. **Basin holdout (PUB/PUR)**: 처음 보는 유역 일반화
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
│   ├── drbc_boundary/  # DRBC Delaware River Basin 공식 경계
│   ├── huc8_delware/   # 초기 HUC8 exploratory shapefile
│   └── CAMELSH_data/   # CAMELSH shapefiles / attributes 추출본
├── configs/             # NeuralHydrology 실험 설정 (현재 비어 있음)
├── data/CAMELS_US/
│   └── camels_attributes_v2.0/  # legacy CAMELS-US 속성 데이터
├── docs/
│   ├── context/         # 프로젝트 맥락 문서
│   └── research/        # architecture, design, literature-review
├── output/
│   └── basin/           # basin 관련 산출물
├── scripts/             # download, run 스크립트
└── runs/                # (gitignored) 학습 출력
```

- **대상 유역**: Delaware River Basin Commission 기준 Delaware River Basin. 공식 기준 레이어는 `basins/drbc_boundary/drb_bnd_polygon.shp`.
- 이전 테스트용 01022500 config와 forcing/streamflow 데이터는 삭제됨.
- CAMELSH shapefile과 attributes 추출본은 `basins/CAMELSH_data/` 아래에 둔다.
- Static attributes (`camels_attributes_v2.0/`)는 legacy 참고 자료이므로 유지한다.
- 향후 DRBC Delaware basin에 맞는 CAMELSH forcing/streamflow subset과 config를 작성해야 한다.

## 개발 환경 규칙

- **패키지 관리**: `uv` 표준. 새 코드는 `uv run`으로 실행 가능해야 한다.
- **전처리/분석**: Python 스크립트 또는 notebook. DRBC basin 기준 subset 정의, 속성 병합, 홍수 취약 후보 추출 등을 수행한다.
- **반복 가능성**: one-off 분석이 아닌 반복 가능한 스크립트 형태로 유지.

## 구현 순서 원칙

1. Model 1 (deterministic) → Model 2 (probabilistic) 순서로 먼저 재현 가능하게 구현
2. Model 3 (physics-guided hybrid)은 그 다음에 넣어 incremental gain 확인
3. 모델 학습 전에 **basin 조사 단계** 선행: DRBC boundary 기준 CAMELSH subset 확정 → forcing/streamflow/static attributes 결합 → flood-prone subbasin screening table 생성
