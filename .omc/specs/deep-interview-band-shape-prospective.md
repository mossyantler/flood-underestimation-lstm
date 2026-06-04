# Deep Interview Spec: Band-Shape Prospective Framework

## Metadata
- Interview ID: di-band-shape-20260527
- Rounds: 8 (Round 0 topology + 8 rounds)
- Final Ambiguity Score: 14%
- Type: brownfield
- Generated: 2026-05-27
- Threshold: 0.2
- Threshold Source: default
- Status: PASSED

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.90 | 0.35 | 0.315 |
| Constraint Clarity | 0.85 | 0.25 | 0.2125 |
| Success Criteria | 0.85 | 0.25 | 0.2125 |
| Context Clarity | 0.80 | 0.15 | 0.120 |
| **Total Clarity** | | | **0.860** |
| **Ambiguity** | | | **0.140** |

## Topology
| Component | Status | Description |
|-----------|--------|-------------|
| Band shape metric 계산 (C1) | active | rel_width = (q99-q50)/q50, g3_ratio = (q99-q95)/(q99-q50) 를 Q99/NOAA event peak마다 계산 |
| Spearman r 검증 (C2) | active | rel_width + g3_ratio vs above_q99 binary, per-event pooled Spearman r 산출 |
| Figure + Paper subsection (C3) | active | scatter figure + Results 새 subsection 초안 |

## Goal

q50/q90/q95/q99만 주어진 상태(obs 없음)에서 band shape 두 지표로 obs가 above_q99일 가능성을 사전 예측하는 prospective framework를 구축하고 경험적으로 검증한다.

- **rel_width** = `(q99-q50)/q50`: 전체 band 상대 폭 — 모델 불확실성의 크기
- **g3_ratio** = `(q99-q95)/(q99-q50)`: 극단 꼬리 비중 — 불확실성이 상단에 집중된 정도

Spearman r(rel_width, obs_class_ordinal)과 Spearman r(g3_ratio, obs_class_ordinal)로 예측력을 검증하며, r > 0.3 & p < 0.05이면 "예측력 존재"로 주장한다. obs_class_ordinal: below_q50=0, q50_to_q90=1, q90_to_q95=2, q95_to_q99=3, above_q99=4.

결과는 논문 Results 새 subsection에 Spearman r 테이블 + scatter figure로 보고된다.

## Constraints
- 입력: `output/model_analysis/expanded_drbc_test/required_series/seed{S}/primary_required_series.csv` (q50/q90/q95/q99 포함, 기존 존재)
- obs_class ground truth: B10(`compute_ub_location_class.py`) 산출물 재사용 또는 동일 로직으로 내부 재계산
- Spearman r 계산 단위: Q99/NOAA 이벤트 × 유역 × seed 전체 pooling (per-event rows)
- 모델 재학습·재추론·quantile 재보정 없음
- q99는 "calibrated 99% predictive interval"이나 return-period 표현 금지
- uv run으로 실행 가능한 PEP 723 script

## Non-Goals
- obs 없이 실시간 운영 예보 시스템 구현
- above_q99 확률을 logistic regression으로 fitting (탐색적 노트 수준)
- RQ-0~5 구조 교체 — 이 분석은 supplementary
- g1/g2/g3 개별 3개 signal 사용 (multicollinearity 이유로 제외)

## Acceptance Criteria
- [ ] AC1: `tables/ub_band_shape_metrics_{q99,noaa}.csv` — event peak마다 rel_width, g3_ratio, obs_class
- [ ] AC2: `tables/ub_band_shape_spearman.csv` — scope(q99/noaa) × metric(rel_width/g3_ratio) × (r, p_value, n)
- [ ] AC3: `figures/ub_band_shape_scatter.png` — rel_width x-axis, above_q99 binary jitter, Q99/NOAA 패널 분리
- [ ] AC4: Paper Results 초안 subsection — "Band Width and Tail Shape as Prospective Risk Indicators" 제목, Spearman r 테이블 포함 (`docs/paper/results_expanded_drbc_draft.md` 갱신)
- [ ] AC5: `run_all.py` B12 step 추가

## Technical Design

### 입력 흐름
```
required_series/seed{S}/primary_required_series.csv
  → B10 obs_class (above_q99 binary ground truth)
  → B12 compute rel_width, g3_ratio at event peaks
  → Spearman r 계산
  → tables/ + figures/ 산출
```

### 핵심 수식
```python
rel_width   = (q99 - q50) / q50          # 상대 폭
g3          = q99 - q95                  # 극단 꼬리 절대 폭
total_width = q99 - q50
g3_ratio    = g3 / total_width           # 극단 꼬리 비중 (0~1)
```

### 집계 로직
1. Q99 이벤트 pool: B10과 동일 peak_time × basin × seed rows
2. NOAA 이벤트 pool: 동일 구조
3. per-seed 행 포함 — seed 평균 내리지 않고 raw rows로 Spearman r 계산
4. 3 seed × n_events × n_basins = 총 N rows

### 출력 경로
```
output/model_analysis/expanded_drbc_test/
  tables/ub_band_shape_metrics_q99.csv
  tables/ub_band_shape_metrics_noaa.csv
  tables/ub_band_shape_spearman.csv
  figures/ub_band_shape_scatter.png
```

### Script
`scripts/model/expanded_drbc/compute_ub_band_shape.py`

## Ontology (Key Entities)
| Entity | Type | Fields |
|--------|------|--------|
| BandShapeEvent | core | basin_id, peak_time, seed, scope, rel_width, g3_ratio |
| ObsClass | core | basin_id, peak_time, seed, scope, obs_class, above_q99_binary |
| SpearmanResult | metric | scope, metric_name, r, p_value, n |

## Interview Transcript (요약)
- Round 1: 기존 UB 분석(location class + gap trajectory)이 retrospective → obs 없는 prospective 필요
- Round 2: Band width → obs가 들어갈 gap 예측이 핵심 goal
- Round 3: 이미 구현된 A(upper-tail spread), C(tau progression) 개념 확인
- Round 4: User idea 1 (width → obs class), User idea 2 (g1/g2/g3 gap 분해)
- Round 5: A+C+1+2 통합 → g3_ratio + rel_width 2-signal 추천 도출
- Round 6: 추천 확인 — rel_width + g3_ratio 채택 (g1/g2/g3 개별 제외)
- Round 7: 검증 기준 = Spearman r > 0.3 & p < 0.05
- Round 8: 논문 배치 = Results 새 subsection, per-event pooled
