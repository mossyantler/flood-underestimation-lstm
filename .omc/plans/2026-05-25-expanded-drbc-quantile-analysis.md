# Plan: Expanded DRBC Quantile (Probabilistic) Diagnostics

- Status: pending approval
- Source spec: `.omc/specs/deep-interview-expanded-drbc-quantile-analysis.md`
- Mode: consensus (--consensus --direct), RALPLAN-DR short
- Generated: 2026-05-25 (rev. 2 after Architect+Critic consensus)
- Consensus: Architect + Critic reviewed; iteration 1 REJECT → rev.2 → iteration 2 **APPROVED** (residual required changes: none).

## Consensus non-blocking notes (impl-time)
- AC7 "event window" 정의 미확정: 구현 시 새로 만들지 말고 기존 event-window 정의(예: extreme_rain/confirmed_flood event 정의) 재사용 확인.
- import-safe: imported helper의 import-time 부작용은 `matplotlib.use`(line 12)뿐인지 확인. module-level const(line 19-20)는 신규 entrypoint가 override하는 default라 low-risk.

## Requirements Summary
expanded DRBC observed test split에 Model 2 quantile(q50/q90/q95/q99, one-sided upper) probabilistic 진단을 산출한다. 두 단계로 분리한다:
- **Phase 1 (이번 실행)**: expanded standalone 진단 + 새 metric + report + doc stub. 디스크에 입력이 모두 존재해 즉시 가능.
- **Phase 2 (gated, 보류)**: scaling_300/154 baseline 부재로 154-vs-expanded 비교는 baseline 재생성 후로 미룬다.

## Critical on-disk findings (consensus-verified)
- **scaling_300 legacy baseline 부재**: `output/model_analysis/legacy/probabilistic_diagnostics/`, `output/model_analysis/legacy/quantile_analysis/` 모두 없음. scaling_300 `required_series`(epoch-named)도 전무 → **154 baseline 재생성 입력조차 없음**. ⇒ 154-vs-expanded 비교(구 AC11)는 이번 cycle 불가.
- **obs NaN**: expanded `primary_required_series.csv` = 2,233,885 rows 중 **172,057 NaN obs (7.70%)**. 재사용 helper가 NaN obs를 drop → `all` stratum coverage 분모 = 관측 시간만.
- **tier 파일**: 정확 경로 `output/model_analysis/expanded_drbc_test/tables/expanded_drbc_tier_profile.csv`, **basin-level 85행**, tier 컬럼 `dominant_distance_label` ∈ {<0.5, 0.5-1.5, 1.5-3, >=3 IQR} = IQR-distance **error tier** (minor/moderate/major 아님).
- **입력 layout**: expanded는 `required_series/seed{S}/primary_required_series.csv` 단일 파일. 기존 스크립트의 `epoch{E:03d}_required_series.csv` 패턴(line 21, 84-85)·same-epoch grid(main line 641-645)와 불일치 → 직접 `main()` 재사용 시 FileNotFoundError.
- 기존 helper `_stratum_masks`(106)는 입력 파일 자체 obs에서 per-basin 임계값 산출 → dataset-relative. 코드 동일해도 disjoint basin set 간 절대 임계값 비교 불가.

## RALPLAN-DR Summary

### Principles
1. **Comparability ≠ code parity**: 동일 helper 재사용만으로 154-vs-expanded 수치 비교가 성립하지 않음(basin set·obs-NaN 분모·dataset-relative 임계값 차이). 비교는 report에서 명시적으로 caveat.
2. **Helper reuse, official script untouched**: 검증된 helper 재사용, 공식 스크립트 무수정 (회귀 방지).
3. **Honest caveats**: upper-only quantile, obs-NaN 분모, dataset-relative 임계값, q99는 calibrated 99% quantile 아님 — 모두 report·doc 08 명시.
4. **Fail-fast preconditions**: 입력 부재 시 작업 시작 전 명확히 실패.
5. **No silent overwrite / no leakage**: baseline 읽기 전용, skill-score baseline은 train-period만.

### Decision Drivers (top 3)
1. scaling_300 baseline + 재생성 입력 부재 → 154 비교는 이번에 불가, 단계 분리 필요.
2. expanded 입력 layout·obs-NaN·tier 의미가 기존 스크립트 가정과 다름 → 신규 loader + 명시 contract.
3. 논문 무결성: CRPS 오명명·skill-score leakage·잘못된 비교는 잘못된 publishable 수치 생산 위험.

### Viable Options
**Option A — 신규 entrypoint, helper import, same-epoch skip (favored)**
`scripts/model/hydrograph/analyze_expanded_drbc_probabilistic_diagnostics.py` 신설. expanded loader(primary 파일) + helper import + `comparison="primary"` 주입 + same-epoch grid 미사용 + tier join + 새 metric.
- Pros: parity 구조 유지, 공식 스크립트 무수정, expanded contract 격리.
- Cons: import 결합(import-time side effect: matplotlib.use line 12, path const 19-20 점검 필요), 일부 helper의 dataset-relative 가정 상속 → report caveat로 흡수.

**Option B — 기존 스크립트에 input-mode 플래그**: 공식 스크립트 침습·scaling_300 회귀 위험 → Principle 2 위반, 기각.

**Invalidation**: `scripts/_lib/` helper 추출(C)은 결합도는 낮추나 dataset-relative contract 문제를 해결 못 하고 범위만 키움 → 이번 보류.

## Phase 1 — Acceptance Criteria (이번 실행, testable)
- [ ] AC0: **pre-flight precondition** — 시작 전 디스크 검증: 3개 `required_series/seed{111,222,444}/primary_required_series.csv`, `tables/expanded_drbc_tier_profile.csv` 존재. 하나라도 없으면 누락 경로 명시하며 non-zero 종료.
- [ ] AC1: calibration summary + by-stratum CSV (6 magnitude strata), seed 111/222/444 전부, `output/model_analysis/expanded_drbc_test/probabilistic_diagnostics/`.
- [ ] AC2: pinball/AQS summary + by-stratum CSV (AQS=2×pinball, 기존 factor 재사용).
- [ ] AC3: upper-tail spread(q99-q50, q99-q95 등) summary + by-stratum CSV.
- [ ] AC4: quantile crossing sanity check (q90<q50, q95<q90, q99<q95) = 0 rows 출력.
- [ ] AC5: calibration/pinball/spread figure (same-epoch calibration-error figure는 입력 부재로 **제외**).
- [ ] AC6: report.md (`.../probabilistic_diagnostics/report/`). q99 nominal_tau=0.99이지만 calibrated 99% quantile 아님(doc 08) caveat 포함.
- [ ] AC7: peak/event quantile capture rate table (observed_peak_hour + event window).
- [ ] AC8: quantile skill score table — baseline = **train-period(2000-2010) per-basin climatology quantile만** (test-period 금지). baseline source period를 코드·report에 assert.
- [ ] AC9: **upper-tail pinball proxy** (q50/q90/q95/q99 pinball 평균). "CRPS" 토큰 사용 금지(report·CSV header grep 0건). upper-only 근사 caveat.
- [ ] AC10: **IQR-distance error-tier별** calibration/coverage figure — `dominant_distance_label` 사용, basin→row join. report에 "error-derived grouping, coverage-by-tier 부분 순환성" caveat. (minor/moderate/major 표현 금지.)
- [ ] AC11: **metadata 기록** — seed별 n_rows, NaN obs drop 수, stratum별 n_basins, per-basin threshold 산출 방식을 `comparability_manifest.json`에 저장.
- [ ] AC12: doc `docs/experiment/analysis/model/08_probabilistic_calibration_pinball.md` expanded **stub 섹션** 추가 — Phase 1 수치 + caveat(obs-NaN 분모, dataset-relative 임계값, upper-tail proxy, 154 비교 보류).

## Phase 2 — Gated (보류, 이번 done-criteria 아님)
- 154-vs-expanded 비교 table: scaling_300 baseline 재생성(별도 inference 필요) 후에만 가능. 선행: scaling_300 quantile required_series 확보 → 기존 스크립트 실행 → 비교. **Phase 1 완료·사용자 승인 후 별도 계획.**

## Implementation Steps
1. **Step 0 pre-flight (AC0)** — 입력 경로 fail-fast 검증.
2. **신규 entrypoint** `scripts/model/hydrograph/analyze_expanded_drbc_probabilistic_diagnostics.py`:
   - expanded loader: `primary_required_series.csv` 직접 로드(컬럼 obs/q50/q90/q95/q99/basin/datetime). `epoch{E:03d}` 패턴·same-epoch grid 미사용.
   - helper import (import-safe 확인: `if __name__=="__main__"` guard, import-time 부작용 점검): `_stratum_masks`(104), `_summarize_quantile`(139), `_summarize_spread`(203), `_aggregate_*`(278/302/333), `_save_*`, `_write_report`(487). `comparison="primary"` 주입.
3. **C1 parity 산출 (AC1-AC6)** — calibration/coverage/pinball/AQS/spread/crossing → CSV + figures. NaN obs drop 수·분모 metadata 기록.
4. **C2 새 metric (AC7-AC9)** — peak/event capture; skill score(train-period climatology baseline, leakage 금지); upper-tail pinball proxy.
5. **tier 계층 (AC10)** — `tables/expanded_drbc_tier_profile.csv` basin→row join, error-tier별 figure + 순환성 caveat.
6. **metadata (AC11)** — `comparability_manifest.json`.
7. **report + doc stub (AC6, AC12)**.

## Risks and Mitigations
- **R1 baseline 부재**: Phase 2로 분리, AC11 metadata로 향후 비교 준비. (해결)
- **R2 obs-NaN 분모 차이**: 분모=관측시간 명시 + NaN count metadata + report caveat. (해결)
- **R3 tier 의미·순환성**: minor/moderate/major 폐기, dominant_distance_label 사용 + 순환성 caveat. (해결)
- **R4 skill-score leakage**: train-period(2000-2010) per-basin climatology만, source period assert. (해결)
- **R5 CRPS 오명명**: "upper-tail pinball proxy"로 rename, "CRPS" 금지 grep 검증. (해결)
- **R6 helper import 부작용/결합**: import-safe 점검, imported helper 목록 주석 고정. dataset-relative 임계값은 report caveat. (완화)
- **R7 same-epoch grid 부재**: 해당 figure/grid 기능 제외(AC5). (해결)

## Verification Steps
- AC0 pre-flight: 입력 1개 일부러 가린 dry run → non-zero 종료 + 누락 경로 메시지.
- `uv run scripts/model/hydrograph/analyze_expanded_drbc_probabilistic_diagnostics.py` 성공, FileNotFoundError 없음, primary CSV non-empty.
- crossing check 0 rows.
- `grep -ri crps output/model_analysis/expanded_drbc_test/probabilistic_diagnostics/` → 0건.
- skill-score 코드에 baseline period=2000-2010 assert 존재.
- `comparability_manifest.json`에 n_rows/NaN/n_basins 존재.
- doc 08 expanded stub가 산출 수치·caveat와 일치.

## ADR
- **Decision**: Option A(신규 entrypoint + helper import + same-epoch skip)로 expanded 진단을 **Phase 1만** 구현하고, 154-vs-expanded 비교는 Phase 2로 gate.
- **Drivers**: scaling_300 baseline·재생성 입력 부재; expanded 입력/obs-NaN/tier contract 차이; 논문 무결성(leakage·오명명·잘못된 비교 방지).
- **Alternatives considered**: (B) 공식 스크립트 플래그 분기 — 회귀 위험으로 기각; (C) `_lib` helper 추출 — contract 미해결·범위 확대로 보류; 단일 phase full 비교 — baseline 부재로 불가.
- **Why chosen**: 즉시 가능한 standalone 가치 확보 + 공식 스크립트 보호 + 비교의 전제(baseline) 미충족을 정직하게 분리.
- **Consequences**: 이번엔 154 비교 없음(Phase 2 대기); expanded 진단·새 metric·doc stub 확보; metadata로 향후 비교 준비. 새 entrypoint가 helper import에 결합.
- **Follow-ups**: Phase 2 baseline 재생성 계획; 필요 시 helper `_lib` 추출 검토; skill-score 2차 baseline(persistence/seasonal) 검토.

## Changelog (rev.2, consensus-applied)
- 154-vs-expanded 비교를 Phase 2로 분리 (baseline 디스크 부재 확인).
- Step 0 pre-flight precondition(AC0) 추가.
- AC10: minor/moderate/major → IQR-distance error-tier(dominant_distance_label) + 순환성 caveat.
- AC9: CRPS → "upper-tail pinball proxy", 토큰 금지 검증.
- AC8: skill-score baseline을 train-period(2000-2010)로 고정, leakage 금지.
- obs-NaN 분모 명시 + comparability_manifest.json(AC11) 추가.
- same-epoch grid figure 제외(AC5), 입력 layout 불일치 신규 loader로 흡수.
- tier_profile 경로 수정(`tables/`), q99 nominal caveat, dataset-relative 임계값 caveat 추가.
- ADR 추가.
