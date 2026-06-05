# 04a RQ-4a — Basin Cohort Heterogeneity (M1 NSE Tier)

## 질문 (RQ-4a)

upper quantile output의 peak under 완화 효과·cost가 basin별로 얼마나 다른가? 직관: Model 1 deterministic이 잘 맞추는 basin과 못 맞추는 basin에서 quantile output의 이득은 다를 것이다.

**Cohort 정의:** Model 1 deterministic의 test-period seed-median NSE 기반 3-tier (top / mid / bottom 1/3). 순환참조(circularity) 방지: cohort axis는 central performance(NSE), stratify metric은 peak under (α, β, δ) + cost (FAR, over-pred). 두 axis는 conceptually 다른 측면이라 정보가 보존된다.

## 데이터

- M1 NSE seed-median (per basin): `tables/rq1_central_metrics_seed_median.csv` (A1)
- α / β / δ / FAR / over-pred per-basin: B3 / B4 / B5 / B6
- 85 basin (Q99 events 없는 3 basin 제외하면 82 active)

## 방법

스크립트: `scripts/model/expanded_drbc/compute_rq4a_nse_tier_stratify.py`

- `pd.qcut(M1_NSE_seed_median, q=3, labels=[bottom, mid, top], duplicates='raise')`
- per tier × τ aggregation (basin-median을 cross-basin median으로 묶음)
- B3/B4/B5/B6 per-basin 산출물 직접 aggregate (required_series 재시도 X)

Tier 사이즈: bottom 29 / mid 28 / top 28 = 85 basins

## 결과 (전체 tier × τ, basin-median, Q99 scope)

τ를 model1 baseline부터 q99까지 전 구간으로 보면, 각 tier에서 α가 언제 0으로 꺾이는지가 다르다.

| Tier (n) | τ | α (peak deficit) | β (window capture) | δ (recall) | FAR | Over-pred |
| --- | --- | --- | --- | --- | --- | --- |
| **bottom** (29) | model1 | 0.354 | 1.001 | 0.346 | 0.0190 | 2.048 |
| | q50 | 0.464 | 0.848 | 0.263 | 0.0077 | 1.467 |
| | q90 | 0.000 | 1.255 | 0.723 | 0.0218 | 2.462 |
| | q95 | 0.000 | 1.564 | 0.785 | 0.0305 | 2.534 |
| | q99 | 0.000 | 2.148 | 0.946 | 0.0604 | 3.707 |
| **mid** (28) | model1 | 0.577 | 0.558 | 0.111 | 0.0016 | 1.112 |
| | q50 | 0.681 | 0.390 | 0.070 | 0.0008 | 1.060 |
| | q90 | 0.347 | 0.795 | 0.296 | 0.0034 | 1.726 |
| | q95 | 0.255 | 1.022 | 0.440 | 0.0054 | 2.079 |
| | q99 | 0.000 | 1.369 | 0.618 | 0.0115 | 2.852 |
| **top** (28) | model1 | 0.673 | 0.428 | 0.083 | 0.0007 | 3.296 |
| | q50 | 0.736 | 0.305 | 0.017 | 0.0003 | 2.579 |
| | q90 | 0.469 | 0.599 | 0.158 | 0.0014 | 4.349 |
| | q95 | 0.387 | 0.680 | 0.212 | 0.0025 | 5.206 |
| | q99 | 0.215 | 0.917 | 0.394 | 0.0077 | 7.828 |

**Tier별 M1 NSE seed-median 경계** (`rq4a_nse_tier_assignments.csv`): bottom −171.8 ~ −0.42 (극단 음수 NSE basin 포함: 01443900 −171.8, 01483200 −136.5, 01480400 −107.7), mid −0.39 ~ 0.24, top 0.25 ~ 0.61.

## 핵심 패턴

- **Bottom tier (M1이 못 맞추는 basin)**: q99이 peak underestimation을 완전히 0으로 줄이고(α 0.464→0.000), recall 0.95로 최고. 단 FAR도 0.060으로 최대. α가 **q50→q90 한 단계에서 즉시 0으로 꺾인다**(가파른 전환).
- **Mid tier**: α가 q50(0.68)→q90(0.35)→q95(0.26)→q99(0.00)로 **점진 감소**. q99에서 완전 회복.
- **Top tier (M1이 잘 맞추는 basin)**: α가 끝까지 안 닫힘(q99에서 0.215 잔존, 22%). over-pred magnitude 최대(7.83) — high-flow basin 자체의 큰 절대값. q99 recall도 0.39로 최저.
- **M1 baseline 자체가 빈약**: bottom δ 0.346, top 0.083 — M1 deterministic은 어느 tier에서도 Q99 사건 recall이 35% 이하다. quantile 도입의 동기.
- **τ-spread (q99−q50)로 본 이질성**: α 감소폭 bottom −0.464 / mid −0.681 / top −0.521, δ 증가폭 bottom +0.683 / mid +0.548 / top +0.377. 완화 효과의 절대 폭은 mid·bottom에서 크고 top에서 작다.
- 효과의 직관: M1이 약한 basin일수록 quantile output의 완화 효과가 크지만 FAR 비용도 함께 커지고, M1이 강한 basin은 q99로도 첨두를 다 회복 못 한다.

## 산출물

```text
output/model_analysis/primary/metrics/tables/
  rq4a_nse_tier_assignments.csv
  rq4a_nse_tier_metrics.csv
output/model_analysis/primary/metrics/figures/
  rq4a_tier_metric_heatmap.png
```

## 주의점 (circularity caveat)

- cohort axis가 central performance(NSE), stratify metric이 peak metric이므로 약한 부분 상관은 존재. 강한 순환은 아니다.
- 절대값 (over-pred magnitude)은 basin scale에 종속적이며, top tier에서 over-pred가 큰 것은 high-flow basin 자체의 크기를 반영한다.
- bottom tier에서 α=0은 sub-sample selection effect도 일부 포함될 수 있으나 cohort 정의가 *순환적이지 않으므로* 결과는 신뢰할 수 있다.
