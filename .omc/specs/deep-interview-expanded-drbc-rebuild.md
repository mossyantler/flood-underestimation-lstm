# Deep Interview Spec: Expanded DRBC — RQ Rebuild · Ideal Analysis · Gap · Execution Plan

## Metadata
- Interview ID: di-expanded-drbc-rebuild-20260526
- Rounds: 10 (+ Round 0 topology gate)
- Final Ambiguity Score: ~13%
- Type: brownfield
- Generated: 2026-05-26
- Threshold: 0.20
- Threshold Source: default
- Initial Context Summarized: no
- Status: PASSED

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.90 | 0.35 | 0.315 |
| Constraint Clarity | 0.85 | 0.25 | 0.213 |
| Success Criteria | 0.85 | 0.25 | 0.213 |
| Context Clarity | 0.90 | 0.15 | 0.135 |
| **Total Clarity** | | | **0.876** |
| **Ambiguity** | | | **0.124** |

## Topology
Sequential 4-component pipeline (locked Round 0).

| Component | Status | Description | Coverage |
|---|---|---|---|
| `rq-definition` | active | expanded DRBC 기준 RQ rebuild (scratch) | 7-RQ skeleton locked |
| `ideal-analysis-design` | active | local MacBook 제약 위 각 RQ에 답 줄 분석 설계 | RQ-0~5 design locked |
| `gap-analysis` | active | 현재 분석 ↔ 이상적 분석 매칭 (match/discard/supplement) | MATCH 2 · PARTIAL 2 · MISMATCH→supplement 3 · MISSING 5 |
| `execution-plan` | active | 미실행 분석 실행 계획 (실행 자체는 deferred) | Phase A · B · C locked |

## Goal

Expanded DRBC observed test split (85 basin, seed 111/222/444) 위에서 Model 1 deterministic LSTM과 Model 2 probabilistic quantile LSTM(`q50/q90/q95/q99`)의 극한 홍수 첨두 과소추정(peak underestimation) 완화 효과를 평가하는 논문을 위해, (1) 핵심 가설을 7개 연구 질문으로 분해하고, (2) 각 RQ에 답을 줄 수 있는 분석을 local MacBook 제약(re-inference 가능하되 학습 불가) 위에서 설계하며, (3) 현재 산출물과 이상적 설계의 간극을 분류하고, (4) 미실행 분석의 실행 계획을 확정한다. 핵심 주장은 단일 metric 완화가 아니라, **병렬 quantile output(q50/q90/q95/q99)을 어떻게 동시 해석할지의 framework + 그 framework 위에서 quantile model이 deterministic 대비 peak under를 완화하는지의 실증**이다.

## Constraints

- Baseline split: expanded DRBC observed test, 85 basin (subset_300/DRBC-38 holdout 폐기 — expanded만 canonical)
- Seed: 111 / 222 / 444 (paired). 학습·inference 재생성 X — 산출물 디스크 보유
- Local MacBook 제약: 학습 불가. Re-inference는 가능(CPU, 느림)하되 본 계획에서는 분석 재가공만 (raw_timeseries, required_series, raw_metrics 활용)
- NOAA confirmed flood scope: 48 basin (expanded 85의 부분집합 가정 — execution 시 매핑 확인 필요)
- High-flow threshold: per-basin Q99 (train-period 2000-2010 obs 기반) 단일
- Event window: ±6h
- Robustness(과거 RQ-E) / extreme-rain stress test / event regime ML clustering / hydromet condition SHAP — paper scope OUT
- 해석 framework는 `docs/experiment/method/model/quantile_output_interpretation.md` 채택(rebuild 아님)
- Cost 정의: FAR + over-prediction magnitude (operational/economic cost는 OUT)

## Non-Goals

- Robustness 견고성 RQ (checkpoint sensitivity / cohort split 재테스트)
- ML event-regime clustering, hydromet driver SHAP
- Extreme-rain stress test 재실행
- scaling_300 / DRBC-38 holdout 보존 분석 (legacy 폴더 외 모든 RQ 정의에서 폐기)
- Calibrated 양방향 prediction interval, return-period, Winkler / interval score 주장
- Operational/economic cost 단위 변환
- Model 3 (physics-guided hybrid) 확장

## Acceptance Criteria

### RQ list 잠금
- [ ] 7-RQ skeleton 그대로: RQ-0 framework, RQ-1 q50 central, RQ-2 upper quantile peak under, RQ-3 cost (FAR + over-pred magnitude), RQ-4a basin cohort heterogeneity, RQ-4b NOAA event-type heterogeneity, RQ-5 calibration·sharpness
- [ ] 각 RQ는 단일 명확한 질문으로 진술됨

### Ideal analysis design 잠금
- [ ] RQ-0: `quantile_output_interpretation.md` 채택, expanded DRBC 맥락 재기술
- [ ] RQ-1: NSE / KGE / bias / MAE / RMSE 5-metric, paired delta (M2 q50 − M1) per-basin per-seed, seed median
- [ ] RQ-2 metric triplet: (α) event peak hour under-deficit `(obs − q_τ)_+ / obs`, (β) ±6h window peak capture `max(q_τ)/max(obs)`, (δ) Q99 threshold recall `P(q_τ ≥ obs | obs ≥ Q99)`
- [ ] RQ-2/3 dual scope: Q99 per-basin threshold (85 basin) + NOAA confirmed flood (48 basin) + cross-tab sanity
- [ ] RQ-3: FAR at Q99 + over-prediction magnitude conditional on `q_τ > obs`
- [ ] RQ-4a: M1 deterministic NSE 3-tier (top/mid/bottom 1/3) cohort, 각 tier 안에서 RQ-2(α+β+δ) + RQ-3 stratify
- [ ] RQ-4b: NOAA `noaa_annotation` dominant event-type label grouping, <5 events lump → "Other"
- [ ] RQ-5: one-sided coverage / pinball / AQS / upper-tail spread / quantile crossing / climatology skill / peak event capture

### Gap classification 잠금
- [ ] MATCH (재활용): RQ-0 framework doc, RQ-5 probabilistic_diagnostics 산출물
- [ ] PARTIAL (재활용 + 보강): RQ-1(bias/MAE/RMSE 추가 필요), RQ-4b(48 basin 매핑 확인 + event-type 파싱 신규)
- [ ] MISMATCH → Supplement: `stratified_underestimation_*`, `expanded_drbc_tier_profile`, FHV/Peak-Timing/Peak-MAPE figures
- [ ] DISCARD: 없음
- [ ] MISSING → 신규: RQ-2 α/β/δ, RQ-3 cost, RQ-4a NSE-tier, RQ-4b event-type 파싱, Cross-tab sanity

### Execution plan 잠금
- [ ] Phase A (PARTIAL 보강) — A1 RQ-1 metric 보강
- [ ] Phase B (MISSING 신규) — B1 Q99 event 추출, B2 NOAA event 매핑·파싱, B3 RQ-2 α, B4 RQ-2 β, B5 RQ-2 δ, B6 RQ-3 cost, B7 RQ-4a NSE-tier, B8 RQ-4b event-type, B9 Cross-tab sanity
- [ ] Phase C (docs) — C1 `00_research_question_analysis_map.md` 재작성, C2 `quantile_output_interpretation.md` expanded DRBC 특화, C3 `01-10_*.md` 폴더 재편 (7-RQ 1:1), C4 08 doc Phase 1 stub → RQ-5 정식 흡수
- [ ] 의존성: B1·B2 → (B3·B4·B5·B6 병렬) → (B7·B8·B9) → C. A1 독립.
- [ ] 모든 Phase 항목 local MacBook CPU로 실행 가능

## Assumptions Exposed & Resolved

| Assumption | Challenge | Resolution |
|---|---|---|
| 기존 RQ-A~G가 expanded DRBC에도 유효 | "test 다시하면서 다른 실험 진행" — split bias 가능 | Rebuild from scratch, 7-RQ로 재구조화 |
| Robustness가 필수 RQ | scope 결정 | RQ-(f) 폐기 |
| q_τ 직접 비교가 peak under 답을 줌 | "직접적 답인지 의문" | Framework 잠금 후 metric 도출 (Sequence reading at high-flow stratum) |
| "Cost" 자명 | 명시 안 됨 | FAR + over-prediction magnitude로 잠금 |
| Heterogeneity = 6-axis | 너무 분산 | basin (M1 NSE tier) + event-type (NOAA dominant label) 두 sub-RQ로 한정 |
| NOAA가 모든 expanded basin cover | 48/85 부분집합 | NOAA dual scope 명시, 매핑은 execution B2에서 확인 |
| "정확도별 cohort" 직관 | 순환참조 risk | central NSE tier로 우회 (peak metric과 다른 측면) |
| 기존 IQR-distance tier 사용 | 08 doc도 circularity 경고 | Supplement로 강등, NSE-tier가 primary |
| 기존 stratified_underestimation = RQ-2 답 | metric 정의 다름 | Supplement, RQ-2 triplet 신규 산출 |
| 학습·inference 재생성 필요 | local 제약 | 학습 X, re-inference 가능하나 본 계획 불요 |

## Technical Context

### Brownfield assets (expanded DRBC)
- 데이터: `data/CAMELSH_generic/drbc_expanded_observed_test/` (85 basin, 4 forcing, hourly)
- 모델 출력 (디스크 보유): `output/model_analysis/expanded_drbc_test/raw_timeseries/`, `required_series/seed{111,222,444}/`, `raw_metrics/model{1,2}_seed*_epoch*.csv`
- 분석 출력: `tables/{basin_metrics, paired_delta_*, primary_epoch_*, stratified_underestimation_*, expanded_drbc_tier_profile}.csv`, `figures/{stratified_underestimation_abs/rel, metric_boxplots, paired_seed_comparison}`, `probabilistic_diagnostics/` (RQ-5 full)
- NOAA confirmed flood: `output/model_analysis/confirmed_flood/{catalog, noaa_cache, performance, analysis, tables}` + `data/CAMELSH_generic/drbc_holdout_confirmed_flood_events/` (48 basin, 623 ready events, post-2013)

### Reference scripts
- `analyze_expanded_drbc_test_performance.py` (overall NSE/KGE/FHV/Peak metric)
- `analyze_expanded_drbc_stratified_underestimation.py` (obs-percentile stratum)
- `analyze_expanded_drbc_probabilistic_diagnostics.py` (RQ-5 full)
- `build_expanded_drbc_tier_profile.py` (IQR-distance tier)
- `scripts/model/confirmed_flood/*` (NOAA pipeline, DRBC 48)
- `scripts/data/prepare_drbc_confirmed_flood_event_dataset.py` (NOAA catalog → GenericDataset)

### Method/protocol docs
- `docs/experiment/method/model/quantile_output_interpretation.md` (RQ-0 framework, 채택)
- `docs/experiment/method/model/probabilistic_head_guide.md` (head + pinball 정의)
- `docs/experiment/method/model/experiment_protocol.md` (split/seed/epoch)
- `docs/experiment/analysis/model/00_research_question_analysis_map.md` (구 RQ map — 재작성 대상)
- `docs/experiment/analysis/model/08_probabilistic_calibration_pinball.md` (Phase 1 stub — RQ-5 정식 흡수 대상)

## Ontology (Key Entities)

| Entity | Type | Fields | Relationships |
|---|---|---|---|
| Model 1 | core domain | deterministic LSTM, single point prediction | central comparator for RQ-1, baseline for RQ-2 |
| Model 2 | core domain | probabilistic quantile LSTM, output q50/q90/q95/q99 | central(q50) + decision outputs(q90/95/99) |
| Quantile output (q_τ) | core domain | τ ∈ {0.50, 0.90, 0.95, 0.99}, per-time scalar | q50=central, q90/95/99=conservatism levels (NOT PI bounds) |
| Interpretation framework | methodology | L1-L4 layers, Pairwise/Sequence/Spread reading, 6 prohibited | RQ-0 deliverable, prerequisite for RQ-1-5 |
| Expanded DRBC test | dataset | 85 basin observed test, test period 2014-2016 | primary baseline for all RQs |
| Q99 threshold | derived | per-basin train-period 2000-2010 obs 99th percentile | RQ-2 δ + RQ-3 FAR base |
| Q99 exceedance event | derived | 시각 obs ≥ Q99 + window | RQ-2 α/β event scope (85 basin) |
| NOAA confirmed flood event | event | 48 basin, 623 events, post-2013, fields: usgs_id, peak_time, flood_tier, noaa_annotation | RQ-2 α/β event scope (subset), RQ-4b grouping |
| NOAA event-type label | derived | parsed from noaa_annotation (Flash Flood / Riverine / ...) | RQ-4b grouping key |
| Event peak under-deficit (α) | metric | `(obs_peak − q_τ_at_peak)_+ / obs_peak` per event | RQ-2 primary |
| Window peak capture (β) | metric | `max_±6h(q_τ) / max_±6h(obs)` per event | RQ-2 secondary |
| Threshold recall (δ) | metric | `P(q_τ ≥ obs | obs ≥ Q99)` pooled | RQ-2 pooled |
| FAR | metric | `P(q_τ > Q99 | obs < Q99)` per-basin | RQ-3 |
| Over-prediction magnitude | metric | `mean(q_τ − obs | q_τ > obs)` | RQ-3 |
| M1 NSE tier | cohort | 3-tier top/mid/bottom 1/3 by M1 test-period NSE | RQ-4a stratification key |

## Execution Plan Detail

### Phase A — PARTIAL 보강
- **A1**: RQ-1 metric set 보강
  - 입력: `raw_metrics/model{1,2}_seed*_epoch*.csv` 또는 `required_series/`
  - 작업: NSE / KGE 외 bias, MAE, RMSE 산출 + paired delta (M2 q50 − M1) per-basin per-seed → seed median
  - 출력: `tables/rq1_central_metrics_seed_median.csv` + box/scatter figure
  - 의존: 없음

### Phase B — MISSING 신규
- **B1**: Q99 per-basin threshold + Q99 exceedance event window
  - 입력: `required_series/seed*/obs` 또는 dataset NetCDF train period 2000-2010
  - 작업: per-basin train-period obs Q99 산출 → test period에서 exceedance window 추출 (peak ± window_hours)
  - 출력: `tables/rq2_q99_events_85basin.csv`
  - 의존: 없음
- **B2**: NOAA event → expanded 48 basin 매핑 + 파싱
  - 입력: `output/model_analysis/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv` + expanded DRBC basin list
  - 작업: basin 교집합 확인 + `noaa_annotation` 정규식 파싱 → dominant event-type label
  - 출력: `tables/rq2_noaa_events_expanded_overlap.csv` + `tables/rq4b_event_type_mapping.csv`
  - 의존: 없음
- **B3**: RQ-2 α event peak under-deficit
  - 입력: B1, B2 + `required_series/seed*/{model1, q50, q90, q95, q99}`
  - 작업: 각 event peak hour에서 τ별 `(obs − q_τ)_+ / obs` 계산, basin → seed → final aggregate
  - 출력: `tables/rq2_alpha_event_peak_deficit_q99.csv`, `tables/rq2_alpha_event_peak_deficit_noaa.csv`
  - 의존: B1, B2
- **B4**: RQ-2 β ±6h window peak capture
  - 입력: B1, B2 + required_series
  - 작업: window 안 `max(q_τ) / max(obs)` τ별
  - 출력: `tables/rq2_beta_window_capture_q99.csv`, `tables/rq2_beta_window_capture_noaa.csv`
  - 의존: B1, B2
- **B5**: RQ-2 δ Q99 threshold recall
  - 입력: B1 + required_series
  - 작업: pooled (모든 시각 obs ≥ Q99에서 q_τ ≥ obs hit-rate) τ별
  - 출력: `tables/rq2_delta_threshold_recall.csv`
  - 의존: B1
- **B6**: RQ-3 cost
  - 입력: B1 + required_series
  - 작업: FAR = `P(q_τ > Q99 | obs < Q99)`, over-pred mag = `mean(q_τ − obs | q_τ > obs)` per-basin per-seed τ별 → median
  - 출력: `tables/rq3_far.csv`, `tables/rq3_over_prediction_magnitude.csv`
  - 의존: B1
- **B7**: RQ-4a M1 NSE 3-tier stratify
  - 입력: M1 NSE per-basin (raw_metrics 또는 A1 산출), B3-B6 결과
  - 작업: M1 NSE 3-tier (top/mid/bottom 1/3) → 각 tier 안에서 RQ-2(α+β+δ) + RQ-3 aggregate
  - 출력: `tables/rq4a_nse_tier_*.csv` + tier × metric heatmap
  - 의존: A1, B3-B6
- **B8**: RQ-4b NOAA event-type stratify
  - 입력: B2 mapping + B3, B4, B6 NOAA scope 결과
  - 작업: dominant event-type group(<5 events → Other) → 각 group RQ-2(α+β) + RQ-3
  - 출력: `tables/rq4b_event_type_*.csv` + group × metric bar
  - 의존: B2, B3, B4, B6
- **B9**: Cross-tab Q99 ∩ NOAA sanity
  - 입력: B1 Q99 event times + B2 NOAA event times (48 basin subset)
  - 작업: 두 event 시간 overlap 비율, NOAA event 중 obs Q99 안 넘는 비율, Q99 exceedance 중 NOAA 미기록 비율
  - 출력: `tables/cross_tab_q99_noaa_sanity.csv`
  - 의존: B1, B2

### Phase C — 문서
- **C1**: `docs/experiment/analysis/model/00_research_question_analysis_map.md` 재작성
  - 7-RQ skeleton 반영 (RQ-A~G 폐기 → RQ-0/1/2/3/4a/4b/5)
  - scaling_300 / DRBC-38 holdout 참조 삭제, expanded DRBC만
  - 본문/supplement 배치 가이드 갱신
- **C2**: `docs/experiment/method/model/quantile_output_interpretation.md` 확장
  - L1-L4 layer + Pairwise/Sequence/Spread reading 유지
  - 6 prohibited 그대로
  - RQ별 layer 매핑 표를 새 RQ ID로 갱신
- **C3**: `docs/experiment/analysis/model/01-10_*.md` 폴더 재편
  - 7-RQ 1:1 매핑되도록 파일 재명명·재구성 (예: `01_q50_central.md`, `02_upper_quantile_peak_under.md`, `03_cost.md`, `04a_basin_cohort.md`, `04b_event_type.md`, `05_calibration_sharpness.md`, `00_research_question_map.md` + framework는 method 폴더)
  - 기존 03/04/06/07/09/10 docs는 archive
- **C4**: `08_probabilistic_calibration_pinball.md` Phase 1 stub 흡수
  - Phase 1 stub → `05_calibration_sharpness.md` 정식 분석으로 통합
  - 비교 대상 scaling_300 baseline 절 폐기

### Local MacBook 실행 가능성
- 모든 Phase B 항목: CPU-only pandas/numpy. raw_timeseries CSV 또는 required_series NetCDF/parquet 위 aggregate. event window는 ±N hour subset만 메모리 로드.
- 학습 X. Inference 재실행 불필요 — model output은 디스크에 이미 있음.
- 추정 처리 시간: Phase B 전체 single-thread로 수십 분 ~ 1시간 수준.

## Topology Coverage Notes

| Component | Coverage |
|---|---|
| `rq-definition` | 7-RQ skeleton acceptance criteria 충족 |
| `ideal-analysis-design` | 7-RQ별 분석 설계 acceptance criteria 충족, local MacBook 제약 검증 완료 |
| `gap-analysis` | MATCH/PARTIAL/MISMATCH→supplement/DISCARD/MISSING 분류 완료 |
| `execution-plan` | Phase A/B/C 의존성·산출물·local feasibility 명시 |

## Ontology Convergence

| Round | Entities | Stability |
|---|---|---|
| Round 0 | 4 (Topology components) | N/A (initial) |
| Round 3 | 12 (M1, M2, q_τ, framework, expanded DRBC + scope axes) | new growth |
| Round 6 | 18 (+ Q99 threshold, NOAA event, event-type label, peak metrics) | mostly additive |
| Round 10 (final) | 22 (final list above) | converged |

## Interview Transcript Summary

10 rounds + Round 0 topology gate.

- Round 0 (topology): 3-component → 2-component → 4-component sequential locked (rq-definition → ideal-analysis-design → gap-analysis → execution-plan)
- Round 1: rebuild from scratch (RQ-A~G discarded)
- Round 2: core claim = framework + alleviation 이중 주장
- Round 3: framework = independent RQ track (RQ-0)
- Round 4: scope = a+b+c+d+e (robustness 제외)
- Round 5: heterogeneity = basin + event(NOAA) sub-RQs, "condition" 폐기
- Round 6: cost = FAR + over-prediction magnitude
- Round 7: RQ-2 metric triplet (α+β+δ)
- Round 8: framework path = existing doc + expanded DRBC 특화
- Round 9: Q99 single threshold + NOAA dual + cross-tab sanity
- Round 10: NSE-tier cohort (circularity 우회) + RQ-1·4b·5 design 잠금 + Gap dump + Execution plan 잠금

## Phase Gate Status

- 본 spec은 **pending approval** 상태로 종료
- 다음 단계 선택은 사용자 명시적 승인 필요 (omc-plan 정련 / autopilot / ralph / team / 추가 인터뷰)
- 본 인터뷰는 실행을 수행하지 않음 (Phase B/C 항목은 별도 승인 후 실행)
