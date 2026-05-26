# 08 Probabilistic Calibration / Pinball 분석

## 질문

이 분석은 Model 2의 `q50/q90/q95/q99`가 quantile forecast로서 얼마나 잘 calibrated되어 있는지, 그리고 quantile별 pinball/AQS가 어떤지 확인하기 위한 probabilistic diagnostic이다.

## 상태

완료에 가깝다. `scripts/model/hydrograph/analyze_subset300_probabilistic_diagnostics.py`가 실행되어 quantile별 pinball/AQS, one-sided calibration, high-flow 조건부 tail hit-rate, upper-tail spread table과 figure가 생성되어 있다.

주요 산출물은 아래에 있다.

```text
output/model_analysis/legacy/probabilistic_diagnostics/
```

## 생성된 표와 그림

주요 CSV는 `quantile_pinball_summary.csv`, `quantile_pinball_by_stratum.csv`, `quantile_calibration_summary.csv`, `quantile_calibration_by_stratum.csv`, `upper_tail_spread_summary.csv`, `upper_tail_spread_by_stratum.csv`, `input_manifest.csv`, `chart_manifest.csv`다. 요약 report는 아래에 있다.

```text
output/model_analysis/legacy/probabilistic_diagnostics/report/probabilistic_diagnostics_report.md
```

생성된 주요 그림은 아래 네 개다.

```text
output/model_analysis/legacy/probabilistic_diagnostics/figures/primary_all_quantile_calibration.png
output/model_analysis/legacy/probabilistic_diagnostics/figures/primary_pinball_by_stratum.png
output/model_analysis/legacy/probabilistic_diagnostics/figures/primary_q99_q50_spread_by_stratum.png
output/model_analysis/legacy/probabilistic_diagnostics/figures/same_epoch_all_calibration_error.png
```

## 해석 기준

현재 quantile set은 `q50/q90/q95/q99`뿐이다. Lower quantile이 없으므로 central prediction interval, interval score, Winkler score, 95% PI width는 공식 metric으로 쓰지 않는다.

`coverage_fraction = mean(obs <= q_tau)`는 전체 test period에서는 empirical one-sided coverage로 읽을 수 있다. 하지만 observed Q99 exceedance 같은 조건부 high-flow stratum에서는 formal calibration이라기보다 tail hit-rate로 읽어야 한다. 이미 관측 유량이 큰 시점만 골랐기 때문이다.

## 현재 해석

Primary all-hour calibration은 Model 2 quantile이 nominal level보다 낮게 잡혀 있음을 보여준다. Median empirical coverage는 `q50 = 0.272`, `q90 = 0.500`, `q95 = 0.658`, `q99 = 0.835`다. 따라서 `q99`는 peak underestimation을 줄이는 upper-tail output이지만, calibrated 99% predictive quantile이라고 쓰면 안 된다.

Pinball/AQS 관점에서는 all-hour 기준 `q99`의 mean pinball loss가 가장 낮다. Primary seed median 기준 mean pinball은 `q50 = 2.135`, `q90 = 2.267`, `q95 = 1.919`, `q99 = 1.243`이고, AQS는 각각 `4.270`, `4.535`, `3.838`, `2.486`이다. 이는 현재 test distribution에서 높은 quantile output이 asymmetric loss 기준으로 유리하게 보인다는 뜻이지만, nominal calibration 부족과 함께 읽어야 한다.

Observed Q99-exceedance stratum에서는 calibration이 아니라 tail hit-rate로 읽는다. 이 조건부 stratum에서 median empirical coverage는 `q50 = 0.133`, `q90 = 0.288`, `q95 = 0.374`, `q99 = 0.560`이다. 즉 `q99`도 Q99-exceedance hour의 약 44%는 여전히 넘지 못하지만, `q50/q95`보다 underestimation을 줄인다.

Upper-tail spread는 Model 2가 high-flow에서 central line 위로 얼마나 여유를 두는지 보여준다. Primary Q99-exceedance에서 median `q99-q50` spread는 `20.836`이고 관측값 대비 `74.581%`다. Quantile crossing sanity check는 `q90<q50`, `q95<q90`, `q99<q95` 모두 0 row로 통과했다.

## 주의점

`q99`가 peak underestimation을 줄인다고 해서 calibrated 99% predictive quantile이라고 말하면 안 된다. 현재 calibration table은 오히려 nominal undercoverage를 보여주므로, 논문에서는 `upper-tail decision output` 또는 `tail-aware output`이라는 표현을 유지한다.

## Expanded DRBC observed test (Phase 1 stub)

이 절은 위 scaling_300 분석과 **별개 split**인 expanded DRBC observed test split(85 basin, seed 111/222/444)에서 Model 2 quantile probabilistic 진단을 standalone으로 산출한 Phase 1 결과다. `scripts/model/hydrograph/analyze_expanded_drbc_probabilistic_diagnostics.py`가 위 scaling_300 스크립트의 helper를 재사용해 실행했다. **154-vs-expanded 비교는 Phase 2로 보류**한다(scaling_300 baseline과 재생성 입력이 디스크에 없음).

주요 산출물은 아래에 있다.

```text
output/model_analysis/expanded_drbc_test/probabilistic_diagnostics/
```

요약 report는 `report/report.md`, 입력·결측·basin 수 메타데이터는 `comparability_manifest.json`에 있다. 그림은 `figures/`에 네 개(`primary_all_quantile_calibration.png`, `primary_pinball_by_stratum.png`, `primary_q99_q50_spread_by_stratum.png`, `tier_calibration_by_iqr_distance.png`)다. same-epoch grid 입력이 없으므로 same-epoch calibration-error figure는 제외했다.

### 입력 / 결측

seed별 raw row 2,233,885개 중 NaN obs 172,057개(7.70%)를 drop했다. 즉 observed row는 seed별 2,061,828개, 85 basin이다. **all-stratum coverage 분모는 관측 시간만**이다(결측 시간 제외).

### Expanded all-hour calibration

scaling_300과 마찬가지로 nominal level보다 낮게 잡히는 undercoverage 패턴을 보인다. Primary seed median 기준 empirical coverage는 `q50 = 0.339`, `q90 = 0.506`, `q95 = 0.638`, `q99 = 0.787`이다. coverage error는 모두 음수이며, `q99`도 expanded split에서 약 0.99에 못 미친다.

### Expanded all-hour pinball / AQS

all-hour median mean pinball은 `q50 = 4.656`, `q90 = 3.658`, `q95 = 2.858`, `q99 = 1.638`로 scaling_300과 동일하게 `q99`가 가장 낮다. AQS(=2×pinball)는 각각 `9.312`, `7.316`, `5.715`, `3.276`이다.

### Expanded Q99-exceedance tail hit-rate

조건부 high-flow stratum이므로 calibration이 아니라 tail hit-rate로 읽는다. median empirical coverage는 `q50 = 0.218`, `q90 = 0.371`, `q95 = 0.424`, `q99 = 0.563`이다. `q99`도 Q99-exceedance hour의 약 44%는 여전히 넘지 못한다.

### Peak / event quantile capture (AC7)

관측 peak hour와 그 주변 event window에서 obs peak를 capture하는 비율이다. event window 정의는 extreme-rain stress test(`scripts/model/extreme_rain/analyze_subset300_extreme_rain_stress_test.py`의 `peak_quantile_bracket_metrics`, default `--peak-quantile-window-hours=6`)를 재사용한 **관측 peak ±6h**다. seed 평균 capture rate는 peak hour 기준 `q99 = 0.522`, ±6h window 기준 `q99 = 0.643`이다.

### Quantile skill score vs train-period climatology (AC8)

baseline은 **train period(2000-2010)** per-basin climatology quantile만 사용한다(test-period 누수 금지). climatology obs는 expanded dataset NetCDF의 observed `Streamflow`(test period에서 required-series `obs`와 동일 scale)에서 train window만 잘라 85 basin·6,365,405 row로 산출했고, 코드에서 window를 `[2000-01-01, 2010-12-31]` 이내로 assert한다. skill = `1 - model_pinball / baseline_pinball`(클수록 좋음). seed 평균 skill score는 `q50 = +0.104`, `q90 = +0.217`, `q95 = +0.132`, `q99 = -0.271`이다. 즉 `q99`는 train climatology baseline보다 오히려 pinball이 나쁘다.

### Upper-tail pinball proxy (AC9)

upper quantile set(q50/q90/q95/q99)의 pinball 평균이다. 이는 **upper-tail 근사값**일 뿐이며 lower tail이 없으므로 two-sided 분포 score가 아니다(따라서 CRPS로 명명하지 않는다). all-hour proxy는 `3.335`, observed peak hour stratum에서는 `84.782`로 high-flow에서 급격히 커진다.

### IQR-distance error-tier calibration (AC10)

tier는 `tables/expanded_drbc_tier_profile.csv`의 `dominant_distance_label`(IQR-distance error tier, basin-level)을 row 단위로 join한 것이다. q99 기준 tier별 empirical coverage는 `<0.5 IQR = 0.745`, `0.5-1.5 IQR = 0.770`, `1.5-3 IQR = 0.999`, `>=3 IQR = 0.990`이다. **주의:** 이 tier는 error에서 파생된 grouping이므로 coverage-by-tier는 부분적으로 순환적이며(error가 큰 basin이 coverage도 높게 보임), 독립적인 calibration 검증으로 읽으면 안 된다.

### Phase 1 caveat

- **obs-NaN 분모:** all-stratum coverage 분모는 관측 시간만이다(결측 7.70% drop).
- **dataset-relative 임계값:** high-flow stratum 임계값은 이 split 자체 obs에서 per-basin으로 산출했다. 따라서 disjoint basin set(154 vs expanded) 간 절대값 비교가 성립하지 않는다.
- **q99는 calibrated 99% quantile 아님:** `nominal_tau = 0.99`는 training target일 뿐이며, calibration table은 오히려 undercoverage를 보여준다.
- **upper-tail proxy:** pinball proxy와 모든 coverage는 one-sided upper 값이다. lower tail, interval score, central PI는 정의하지 않는다.
- **Phase 2 보류:** 154-vs-expanded 비교는 scaling_300 baseline 재생성 후로 미룬다. 비교 준비용 메타데이터(per-seed row/NaN/basin 수, threshold 산출 방식, climatology baseline period)는 `comparability_manifest.json`에 기록했다.

## 남은 작업

본문에는 all-hour calibration plot과 Q99-exceedance tail hit-rate/pinball compact table만 넣고, same-epoch calibration error와 stratum별 상세 table은 supplement로 보내는 편이 좋다. 이 분석은 Model 2가 probabilistic forecast로 완전히 calibrated되었음을 주장하기 위한 근거가 아니라, upper quantile improvement claim의 calibration caveat를 명확히 하는 방어용 분석으로 쓰는 것이 안전하다.
