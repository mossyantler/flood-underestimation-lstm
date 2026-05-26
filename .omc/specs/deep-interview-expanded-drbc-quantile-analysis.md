# Deep Interview Spec: Expanded DRBC Quantile (Probabilistic) Analysis

## Metadata
- Interview ID: di-quantile-20260525
- Rounds: 5 (+ Round 0 topology, + Round 0 reframe)
- Final Ambiguity Score: 19%
- Type: brownfield
- Generated: 2026-05-25
- Threshold: 0.2
- Threshold Source: default
- Initial Context Summarized: no
- Status: PASSED
- Challenge modes used: contrarian (Round 4)

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.85 | 0.35 | 0.2975 |
| Constraint Clarity | 0.80 | 0.25 | 0.200 |
| Success Criteria | 0.85 | 0.25 | 0.2125 |
| Context Clarity | 0.65 | 0.15 | 0.0975 |
| **Total Clarity** | | | **0.8075** |
| **Ambiguity** | | | **0.1925** |

## Topology
| Component | Status | Description | Coverage / Deferral Note |
|-----------|--------|-------------|--------------------------|
| Expanded parity 진단 포트 (C1) | active | 기존 probabilistic quantile diagnostic(calibration curve, coverage by stratum, pinball/AQS, upper-tail spread)을 expanded DRBC test set에 재실행. scaling_300/154와 동일 구조 → 직접 비교. | AC1–AC6, AC10–AC12 |
| Expanded 새 metric (C2) | active | expanded DRBC quantile 출력에 peak/event capture + skill score(climatology baseline) primary, CRPS(4-quantile 근사) secondary 추가. | AC7–AC9, AC12 |

## Goal
expanded DRBC observed test split(test 유역이 넓어짐)에 대해 Model 2의 quantile(q50/q90/q95/q99) probabilistic 진단을 다시 산출한다. (1) 기존 scaling_300/primary-DRBC(154) 진단 suite를 expanded DRBC에 parity로 포트하여 154-vs-expanded 비교를 만들고, (2) peak/event quantile capture·climatology-baseline skill score를 primary 새 metric으로, CRPS(4-quantile 근사)를 caveat 단 secondary로 추가한다. 6종 magnitude stratum은 비교용으로 재사용하고, minor/moderate/major flood tier 계층을 expanded 전용으로 덧붙인다.

## Constraints
- 입력: `output/model_analysis/expanded_drbc_test/required_series/seed{S}/primary_required_series.csv` + `raw_timeseries/model2_seed{S}_epoch{E}.csv` (q50/q90/q95/q99 포함, 이미 존재).
- Seed/epoch: primary epoch map 재사용 `{111:(25,5), 222:(10,10), 444:(15,10)}` (Model 2 학습/검증 epoch). seed 333 제외(기존 정책).
- Stratum: 기존 6종 magnitude stratum 재사용 — `all`, `basin_top10`(Q90), `basin_top5`(Q95), `basin_top1`(Q99), `basin_top0_1`(Q99.9), `observed_peak_hour`. 154 비교 가능성 유지.
- Tier: `expanded_drbc_tier_profile.csv`의 minor/moderate/major flood tier 계층을 expanded 전용으로 추가.
- Quantile set: q50/q90/q95/q99 = one-sided upper만. lower tail 없음.
- 출력 경로: `output/model_analysis/expanded_drbc_test/probabilistic_diagnostics/`.
- 기존 scaling_300 산출물(`output/model_analysis/legacy/probabilistic_diagnostics/`)은 비교 baseline으로만 읽고 덮어쓰지 않음.

## Non-Goals
- Interval score / Winkler score / 95% PI width — lower quantile 없어 계산 불가, 공식 metric 제외 (doc 08 기준 유지).
- Lower quantile(q05/q10/q25) re-export 또는 모델 재학습 — 이번 범위 밖 (CRPS 정식화는 추후).
- Model 2가 완전히 calibrated probabilistic forecast라는 주장 — calibration caveat 방어용 분석으로만 사용.
- Primary epoch 재선정 — 진단용만, 고정 epoch 유지.
- scaling_300/154 기존 산출물 재생성/수정.

## Acceptance Criteria
- [ ] AC1: expanded DRBC quantile calibration summary + by-stratum CSV (6 magnitude strata), primary seed 전부 생성
- [ ] AC2: pinball/AQS summary + by-stratum CSV
- [ ] AC3: upper-tail spread(q99-q50 등) summary + by-stratum CSV
- [ ] AC4: quantile crossing sanity check (q90<q50, q95<q90, q99<q95 = 0 rows) 통과
- [ ] AC5: calibration / pinball / spread 주요 figure 생성 (scaling_300 figure 구조와 정합)
- [ ] AC6: report.md (`.../probabilistic_diagnostics/report/`) 생성
- [ ] AC7: peak/event quantile capture rate table (observed peak + event window)
- [ ] AC8: quantile skill score vs climatology baseline table
- [ ] AC9: CRPS (4-quantile 근사) 산출 + "upper-only 근사" caveat report에 명시
- [ ] AC10: minor/moderate/major tier별 calibration/coverage figure (expanded 전용)
- [ ] AC11: 154(scaling_300) vs expanded 비교 table
- [ ] AC12: doc `docs/experiment/analysis/model/08_probabilistic_calibration_pinball.md`에 expanded DRBC 섹션 추가 (수치·caveat 동기화)

## Assumptions Exposed & Resolved
| Assumption | Challenge | Resolution |
|------------|-----------|------------|
| "quantile 분석"이 새 metric 추가 | reframe: 진짜 driver는 expanded DRBC 확장 | parity 포트 + 새 metric 결합으로 재정의 |
| 모든 probabilistic metric 추가 가능 | lower quantile 없어 interval/Winkler 불가 (doc 08) | interval/Winkler 제외, CRPS는 근사 caveat |
| CRPS를 정식 metric으로 | upper-only quantile → 근사일 뿐 | peak capture+skill score primary, CRPS secondary caveat |
| scaling_300 pooled 진단 그대로 복제 | (Contrarian) expanded tier 이질성을 pooled가 가림 | 6 magnitude stratum 유지 + tier 계층 추가 |
| 산출물 형태 불명 | repo 관례 = CSV+figure+report+doc | full 산출물 + doc 08 expanded 섹션 |

## Technical Context
- 기존 진단 스크립트: `scripts/model/hydrograph/analyze_subset300_probabilistic_diagnostics.py` (argparse, DEFAULT_INPUT_DIR=`legacy/quantile_analysis`, QUANTILES q50/q90/q95/q99, STRATA 6종) → input-dir 교체로 expanded 재실행 가능. `scripts/model/hydrograph/plot_subset300_quantile_coverage.py`.
- Expanded DRBC 파이프라인: `scripts/basin/drbc/build_drbc_expanded_observed_test_split.py`, `scripts/data/prepare_drbc_expanded_observed_test_dataset.py`, `scripts/model/overall/infer_drbc_expanded_drbc_test.py`(q50/q90/q95/q99 출력), `evaluate_subset300_expanded_drbc_test.py`, `analyze_expanded_drbc_test_performance.py`, `analyze_expanded_drbc_stratified_underestimation.py`. Runner: `scripts/runs/official/run_expanded_drbc_test_evaluation.sh`.
- 기존 expanded 산출물(존재): `output/model_analysis/expanded_drbc_test/{raw_timeseries, required_series, raw_metrics, tables, figures}`, `expanded_drbc_tier_profile.csv`, stratified_underestimation 산출물. **probabilistic quantile diagnostic은 미존재 = 이번 작업의 gap.**
- 해석 기준(doc 08 계승): all-hour coverage는 empirical one-sided coverage, conditional high-flow stratum은 tail hit-rate. q99는 upper-tail/tail-aware output이지 calibrated 99% predictive quantile 아님.
- 문서 동기화 규칙(CLAUDE.md): 산출물 경로·분석 결론 변경 시 관련 docs 갱신.

## Ontology (Key Entities)
| Entity | Type | Fields | Relationships |
|--------|------|--------|---------------|
| ExpandedDRBCTest | core domain | basins(확장), period 2014-2016, observed | has many QuantileForecast |
| QuantileForecast | core domain | q50, q90, q95, q99 (one-sided upper) | belongs to ExpandedDRBCTest; scored by metrics |
| Calibration | metric | nominal_tau, empirical_coverage | over Stratum |
| Coverage | metric | coverage_fraction by stratum | over Stratum |
| PinballAQS | metric | pinball, AQS by quantile | over Stratum |
| UpperTailSpread | metric | q99-q50, q99-q95 | over Stratum |
| PeakCapture | metric (new) | capture rate at peak/event hour | over Event/PeakHour |
| SkillScore | metric (new) | skill vs climatology baseline | over QuantileForecast |
| CRPS | metric (new, approx) | 4-quantile approximation | over QuantileForecast (caveat) |
| FloodTier | supporting | minor, moderate, major | stratifies ExpandedDRBCTest |

## Ontology Convergence
| Round | Entity Count | New | Changed | Stable | Stability Ratio |
|-------|-------------|-----|---------|--------|----------------|
| 1 | 7 | 7 | - | - | N/A |
| 2 | 7 | 0 | 0 | 7 | 100% |
| 0-reframe | 9 | 2 (ExpandedDRBCTest, UpperTailSpread) | 0 | 7 | 78% |
| 3 | 9 | 0 | 0 | 9 | 100% |
| 4 | 10 | 1 (FloodTier) | 0 | 9 | 90% |
| 5 | 10 | 0 | 0 | 10 | 100% |

## Interview Transcript
<details>
<summary>Full Q&A (Round 0 + 5 rounds, with reframe)</summary>

### Round 0 (topology)
**Q:** quantile 작업 대부분 존재. "진행"이 가리키는 top-level 작업?
**A:** 새 metric 추가 (CRPS/interval 등)

### Round 1
**Q:** 현 q50/q90/q95/q99 제약(interval/Winkler 불가)에서 우선 metric?
**A:** peak/event capture + skill score/pinball decomposition + CRPS(근사). interval/Winkler 제외.
**Ambiguity:** 42%

### Round 2
**Q:** 새 metric 데이터 scope?
**A:** DRBC test basin 집중.
**Ambiguity:** 40%

### Round 0 (reframe — user clarification)
**Q:** expanded DRBC로 test 유역 넓어짐. 다시 할 quantile 분석 scope? (사용자: "어떤 분석이 맞아?")
**A:** parity 포트(calibration/coverage/pinball/AQS/spread) + 새 metric.
**Ambiguity:** 47%

### Round 3
**Q:** upper-only quantile set에서 새 metric 정의·검증?
**A:** robust 우선 — peak/event capture + skill score(climatology) primary, CRPS 근사 caveat.
**Ambiguity:** 32%

### Round 4 (Contrarian)
**Q:** [Contrarian] pooled parity 복제가 맞나? expanded tier 이질성 무시?
**A:** parity 6-stratum 재사용 + minor/moderate/major tier 계층 추가. primary epoch map 재사용.
**Ambiguity:** 24%

### Round 5
**Q:** 어떤 산출물이 '끝'? (경로: expanded_drbc_test/probabilistic_diagnostics/)
**A:** full + doc 갱신 — CSV + figures + 154-vs-expanded 비교 + tier figures + report.md + doc 08 expanded 섹션.
**Ambiguity:** 19% (threshold 20% 도달)

</details>
