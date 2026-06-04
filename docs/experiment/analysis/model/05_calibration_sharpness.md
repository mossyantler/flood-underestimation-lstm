# 05 RQ-5 — Quantile Output Calibration & Sharpness

## 질문 (RQ-5)

Model 2의 `q50 / q90 / q95 / q99`가 quantile forecast로서 얼마나 잘 calibrated 되어 있고 sharpness는 어떠한가? quantile output을 RQ-2 / RQ-3 decision output으로 쓰기 위한 통계적 품질 진단이다.

## 데이터

- expanded DRBC observed test (85 basin, seed 111/222/444)
- 입력 시리즈: seed별 raw row 2,233,885개 → NaN obs 172,057개 (7.70%) drop → 2,061,828 row × seed (85 basin)
- Train-period climatology (skill score baseline): expanded dataset NetCDF의 obs `Streamflow`, 2000-01-01 ~ 2010-12-31 train window 안 한정 (85 basin · 6,365,405 row)

## 방법 (재활용)

스크립트: `scripts/model/hydrograph/analyze_expanded_drbc_probabilistic_diagnostics.py` (reuse — ADR §10 Option A의 RQ-5 in-place reuse 결정).

산출물:

```text
output/model_analysis/expanded_drbc_test/probabilistic_diagnostics/
  quantile_pinball_summary.csv
  quantile_pinball_by_stratum.csv
  quantile_calibration_summary.csv
  quantile_calibration_by_stratum.csv
  upper_tail_spread_summary.csv
  upper_tail_spread_by_stratum.csv
  quantile_crossing_check.csv
  peak_event_capture_rate.csv  + _agg.csv
  quantile_skill_score.csv     + _agg.csv
  tier_calibration.csv          + _agg.csv
  upper_tail_pinball_proxy.csv  + _agg.csv
  comparability_manifest.json
  report/report.md
  figures/{primary_all_quantile_calibration, primary_pinball_by_stratum, primary_q99_q50_spread_by_stratum, tier_calibration_by_iqr_distance}.png
```

## 해석 기준 (RQ-0 framework)

[`docs/experiment/method/model/quantile_output_interpretation.md`](../../method/model/quantile_output_interpretation.md)의 6 prohibited 해석:
- `coverage_fraction = mean(obs ≤ q_τ)`는 **전체 test period**에서 empirical one-sided coverage. 조건부 high-flow stratum에서는 calibration 아닌 **tail hit-rate**로 읽는다.
- lower quantile 부재이므로 PI / interval score / Winkler / 양방향 calibration 사용 금지.
- `q99`를 100-year flood quantile / 98% PI 상한으로 사용 금지.

## 결과 (primary seed median)

### All-hour one-sided calibration

| τ | nominal | empirical (median basin) | coverage error |
| --- | --- | --- | --- |
| q50 | 0.50 | **0.339** | −0.16 |
| q90 | 0.90 | **0.506** | −0.39 |
| q95 | 0.95 | **0.638** | −0.31 |
| q99 | 0.99 | **0.787** | −0.20 |

모든 τ에서 nominal 보다 낮은 undercoverage. q99의 empirical coverage = 0.787 → **`q99` ≠ "calibrated 99% predictive quantile"**.

### Pinball / AQS (all-hour, basin median)

| τ | mean pinball | AQS (= 2 × pinball) |
| --- | --- | --- |
| q50 | 4.656 | 9.312 |
| q90 | 3.658 | 7.316 |
| q95 | 2.858 | 5.715 |
| q99 | **1.638** | 3.276 |

q99이 mean pinball 최소. asymmetric loss 기준 상위 quantile이 유리하게 보이지만 calibration undercoverage와 함께 읽어야 한다.

### Q99-exceedance tail hit-rate (조건부)

| τ | tail hit-rate |
| --- | --- |
| q50 | 0.218 |
| q90 | 0.371 |
| q95 | 0.424 |
| q99 | **0.563** |

obs가 Q99 이상인 시각의 56%를 q99이 잡는다 (44%는 여전히 놓침). RQ-2 δ-recall 0.583과 일치하는 신호.

### Peak event capture (RQ-2 β 연계)

obs peak hour + ±6h window:
- q99 peak hour 평균 capture rate: **0.522**
- q99 ±6h window 평균 capture rate: **0.643**

### Train-period climatology skill score (vs train-period per-basin climatology quantile)

baseline = train (2000-2010) per-basin climatology quantile만 사용 (test 누수 금지).

| τ | skill score |
| --- | --- |
| q50 | +0.104 |
| q90 | **+0.217** |
| q95 | +0.132 |
| q99 | −0.271 |

q90 / q95 / q50 모두 baseline 대비 양의 skill. **q99**은 baseline 보다 mean pinball이 나쁨 — 극단 quantile은 climatology 단순 추정 대비 sharpness 손해를 본다.

### Upper-tail spread (`q99 − q50`)

primary Q99-exceedance stratum에서 median spread = **20.836**, 관측값 대비 **74.581%**. q99이 high-flow 시각에서 q50 위로 obs의 75% 폭만큼 보수성 추가.

### CRPS 4-분위 상위 근사 (secondary, caveat 포함)

CRPS_approx = 2 × mean_pinball across {q50, q90, q95, q99}. lower tail 부재이므로 **full two-sided CRPS 아님** — upper-only 근사치.

| stratum | CRPS_approx (상위 4-quantile 근사) |
| --- | --- |
| All hours | 6.671 |
| Observed peak hour | **169.564** |

> `upper_tail_pinball_proxy` = CRPS_approx / 2. high-flow stratum에서 급격히 증가. 참조 산출물: `crps_4quantile_upper_approx.csv`.

### 154 유역 vs expanded 85 유역 비교 (AC11 — deferred)

`output/model_analysis/legacy/` 미존재로 비교 불가. `154_vs_expanded_comparison.csv`에 blocking 사유와 재생성 방법 기록. legacy quantile_analysis 입력이 복원되면 `analyze_subset300_probabilistic_diagnostics.py` 재실행으로 활성화 가능.

### Quantile crossing

`q90 < q50`, `q95 < q90`, `q99 < q95` 모두 **0 row** — quantile monotonicity sanity 통과.

### IQR-distance error tier calibration (caveat: 부분적 circular)

| tier | q99 empirical coverage |
| --- | --- |
| < 0.5 IQR | 0.745 |
| 0.5–1.5 IQR | 0.770 |
| 1.5–3 IQR | 0.999 |
| ≥ 3 IQR | 0.990 |

tier는 error 분포에서 파생된 grouping이므로 **부분 순환적**. 독립적 calibration 검증으로 읽지 말고, basin heterogeneity 진단 보조로만 사용. Paper에서는 supplement로 격등.

### Stratum별 coverage 열화 (all-hour → 극단)

전체 시각에서 극단 stratum으로 갈수록 q99 포함률이 더 떨어진다 — 명목에서 멀어진다.

| stratum | q99 empirical coverage |
| --- | --- |
| all-hour | 0.787 |
| observed peak hour | 0.522 |
| Basin Q99.9-exceedance | 0.572 |

극단 첨두에서 q99조차 obs를 절반 정도만 덮는다(0.52). RQ-2의 `above_q99` 47% 결과와 정합 — calibration 열화가 곧 첨두 과소추정이다.

### Seed 이질성

seed 111/222/444 간 all-hour 포함률 편차가 작지 않다 (q50 0.273~0.351, q99 0.745~0.808). 본문은 seed-median 또는 3-seed 평균을 쓰되, point estimate를 단정적으로 읽지 않고 seed 범위를 함께 보고한다.

## 통합 해석

1. quantile output은 nominal level보다 **undercoverage**한다 (q99 empirical 0.787 < 0.99). "calibrated 99% predictive quantile"라는 표현은 사용 금지.
2. Pinball / AQS 관점에서는 q99이 가장 낮은 mean pinball — high-flow asymmetric loss에 잘 맞춰진다.
3. Q99-exceedance stratum (high-flow tail) 에서 q99의 hit-rate 56% — RQ-2 결과와 일치.
4. q99은 climatology baseline 대비 sharpness 손해 (skill = −0.27) — extreme quantile output은 climatology-aware decision tradeoff 안에서 해석해야 한다.
5. RQ-2 / RQ-3 결과를 "calibration이 완전하지 않더라도 high-flow tail에서 의미 있게 peak를 잡는 decision output"으로 일관되게 frame한다.

## 산출물 (재활용)

위 §"방법" 산출물 목록 참조. 별도 신규 산출물은 없다. paper 본문은 all-hour calibration plot + Q99-exceedance tail hit-rate / pinball compact table만 사용하고, same-epoch calibration error / stratum별 세부 표는 supplement로 보낸다.

## 주의점

- IQR-distance tier calibration은 circularity caveat 함께 명시.
- `q99`가 peak underestimation을 줄인다(RQ-2)고 해서 "calibrated 99% quantile"이라는 표현으로 paper에 쓰면 안 된다. **upper-tail decision output**, **tail-aware output** 같은 표현 유지.
- 본 분석은 Model 2가 probabilistic forecast로서 완전히 calibrated되었음을 주장하기 위한 근거가 아니다. upper-quantile improvement 주장의 **calibration caveat을 명확히 하는 방어용** 분석으로 쓴다.
