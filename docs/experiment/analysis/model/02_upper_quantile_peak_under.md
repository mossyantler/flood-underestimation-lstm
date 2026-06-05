# 02 RQ-2 — Upper Quantile Peak Underestimation Reduction

## 질문 (RQ-2)

Model 2의 upper quantile output(`q90 / q95 / q99`)이 Model 1 deterministic 대비 expanded DRBC peak underestimation을 줄이는가? 본 RQ는 본 연구의 중심 주장이다. 세 metric의 triplet으로 측정한다.

- **α — event peak under-deficit**: per-event `(obs_peak − q_τ_at_peak)_+ / obs_peak`
- **β — ±6h window peak capture**: per-event `max(q_τ in window) / max(obs in window)`
- **δ — Q99 threshold recall**: pooled `P(q_τ ≥ obs | obs ≥ Q99_basin)`

Q99 (85 basin) + NOAA (overlap = 21 basin in test period) dual scope.

## 데이터

- `tables/rq2_q99_per_basin_thresholds.csv` (B1; per-basin train-period Q99)
- `tables/rq2_q99_events_85basin.csv` (B1; 926 events / 82 active basin)
- `output/model_analysis/primary/metrics/tables/rq2_noaa_events_overlap.csv` (B2; NOAA confirmed flood + dominant event-type)
- 모델 출력: `output/model_analysis/primary/metrics/data/required_series/seed{111,222,444}/required_series.csv`

## 방법

스크립트 3개:
- α: `scripts/model/expanded_drbc/compute_rq2_alpha_peak_deficit.py` (B3)
- β: `scripts/model/expanded_drbc/compute_rq2_beta_window_capture.py` (B4)
- δ: `scripts/model/expanded_drbc/compute_rq2_delta_threshold_recall.py` (B5)

Aggregation 순서 (C0): per-basin per-seed compute → median across events within basin/seed → median across seeds within basin → cross-basin median + IQR.

### 검증 (acceptance)

- 모든 값 [0, 1] 범위 (β의 경우 capture ratio라 > 1 가능; q99에서 가끔 > 2 자연스러움).
- Cross-basin median **q50 → q99 단조** non-increasing(α), non-decreasing(β, δ).
- 단조성은 Model 2 quantile sequence (q50 → q90 → q95 → q99)에 한정. M1과 q50 비교는 RQ-1 영역.
- Per-basin τ-monotonicity violation rate = 0% (B3 결과: Q99 scope 0%, NOAA scope 0%). Monotonic Quantile head 구조상 보장되는 sanity 확인 (assert는 pipeline bug guard).

## 결과 — Q99 scope (85 basin)

### α (event peak under-deficit)

| τ | basin median | IQR (low/high) |
| --- | --- | --- |
| model1 | 0.588 | 0.228 / 0.762 |
| q50 | 0.657 | 0.298 / 0.816 |
| q90 | 0.376 | 0.000 / 0.561 |
| q95 | 0.272 | 0.000 / 0.442 |
| q99 | **0.018** | 0.000 / 0.283 |

q50 → q99 33× 개선. q99에서 peak deficit cross-basin median ≈ 0 — peak 시각에서 q99이 obs를 거의 정확히 잡는다.

### β (±6h window capture)

| τ | basin median |
| --- | --- |
| model1 | 0.519 |
| q50 | 0.444 |
| q90 | 0.733 |
| q95 | 0.920 |
| q99 | **1.306** |

q99이 window 안에서 1.3× obs까지 overshoots — peak에서 충분한 보수성.

### δ (Q99 threshold recall, pooled)

| τ | basin median recall |
| --- | --- |
| model1 | 0.143 |
| q50 | 0.069 |
| q90 | 0.280 |
| q95 | 0.379 |
| q99 | **0.583** |

q99이 high-flow 시각의 58%를 cover. q50과 비교해 8.5× 개선.

## 결과 — NOAA scope (test-period overlap 21 basin / 65 events)

| τ | α (basin median) [IQR] | β (basin median) [IQR] |
| --- | --- | --- |
| model1 | 0.676 [0.516 / 0.828] | 0.400 [0.194 / 0.647] |
| q50 | 0.788 [0.739 / 0.817] | 0.282 [0.223 / 0.368] |
| q90 | 0.482 [0.428 / 0.630] | 0.566 [0.465 / 0.703] |
| q95 | 0.404 [0.273 / 0.544] | 0.677 [0.552 / 0.818] |
| q99 | **0.172** [0.000 / 0.367] | **0.977** [0.814 / 1.402] |

NOAA confirmed flood event-set 위에서도 q99이 peak deficit 17% / window capture 98% — Q99 scope와 같은 방향. 단 **NOAA scope의 q99 α(0.172)는 Q99 scope(0.018)보다 약 9.5배 크다** — NOAA 공식 확인 홍수가 모델이 더 잡기 어려운 hard subset임을 보여 준다(모든 τ에서 NOAA α > Q99 α).

### Q99 ∩ NOAA cross-tab (sanity)

`compute_cross_tab_q99_noaa_sanity.py`: NOAA event 65개가 **전부 Q99 window 안**(NOAA ⊆ Q99, 100%)이다. 역으로 Q99 event 중 NOAA가 보강하는 비율은 **16.7%**뿐 — Q99 임계가 NOAA보다 inclusive하다. 즉 NOAA scope는 Q99 scope의 hard subset이며, 두 scope 결과가 같은 방향이라는 점이 결론의 견고성을 뒷받침한다.

## 통합 해석

upper quantile output (q90 / q95 / q99)이 Model 1 deterministic 및 Model 2 q50 대비 peak underestimation을 monotone하게 줄인다. q99에서 cross-basin median peak deficit ≈ 0 (Q99 scope), recall ≈ 0.58. Effect는 NOAA confirmed flood event-set에서도 재현된다 (basin scope 다름에도 동일 방향).

이 reduction은 RQ-3 (cost) 분석과 결합해서 해석되어야 한다 — recall 증가 8× vs FAR 증가 24× 비대칭 tradeoff.

**Uncertainty Band framing**: q99 Q99-scope α-median ≈ 0 / NOAA-scope β ≈ 0.977은 q99이 obs를 초과한다는 뜻이기도 하다. q99을 단일 정답 예측이 아닌 q50~q99 band의 upper envelope로 보면, 관측 peak가 band 내부에 들어오는가(α ≈ 0 = obs가 q99 아래)와 그 대가로 over-prediction cost가 얼마나 발생하는가(β > 1 / FAR 증가)를 함께 설명해야 한다. gap trajectory 관점에서 τ 증가 → under-gap 감소 + over-gap 증가는 단순 tradeoff이며, 이 band framing은 RQ-3 cost 분석으로 직결된다.

## 해석 framework 적용 (RQ-0)

[`docs/experiment/method/model/quantile_output_interpretation.md`](../../method/model/quantile_output_interpretation.md)의 L3 + L4 layer + **Sequence reading** (τ = 50 → 90 → 95 → 99 진행). q_τ를 "decision output / conservatism level"로 해석. PI / return-period / 양방향 calibration 표현은 사용 금지.

## 산출물

```text
output/model_analysis/primary/metrics/tables/
  rq2_alpha_event_peak_deficit_q99.csv + _summary.csv
  rq2_alpha_event_peak_deficit_noaa.csv + _summary.csv
  rq2_beta_window_capture_q99.csv + _summary.csv
  rq2_beta_window_capture_noaa.csv + _summary.csv
  rq2_delta_threshold_recall_per_basin_seed.csv + _summary.csv
output/model_analysis/primary/metrics/figures/
  rq2_alpha_by_tau.png
  rq2_beta_by_tau.png
  rq2_delta_recall_by_tau.png
```

## 주의점

- M1 → q50 transition은 RQ-1 (central performance) 영역이며 단조성 가정 없음. M2 q50는 peak에서 더 under-bias (RQ-1 결과).
- per-basin monotonicity는 Monotonic Quantile head(누적 softplus 증분) 구조상 by construction 보장된다. q_τ가 단조 → α = `(obs_peak − q_τ)_+ / obs_peak`도 τ에 대해 단조 비증가 → per-basin median도 단조 보존. 따라서 위반율 0%는 구조적 필연이며, sanity 확인의 의미를 가진다.
- β > 1.3 (q99 in Q99 scope)은 over-capture으로 해석되며, RQ-3의 over-prediction magnitude 증가로 연결된다.
- NOAA scope sample size 작음 (21 basin / 65 events). 단조 방향성이 일관하다는 것이 결과의 주요 가치이며 절대값 비교에는 caveat.
