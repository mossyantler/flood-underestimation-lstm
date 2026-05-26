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

## 결과 (요약 — basin-median per tier × τ, Q99 scope)

| Tier | τ | α (peak deficit) | β (window capture) | δ (recall) | FAR | Over-pred |
| --- | --- | --- | --- | --- | --- | --- |
| top | q50 | 0.74 | 0.31 | 0.02 | 0.0003 | 2.58 |
| top | q99 | 0.22 | 0.92 | 0.39 | 0.0077 | 7.83 |
| mid | q50 | 0.68 | 0.39 | 0.07 | 0.0008 | 1.06 |
| mid | q99 | 0.00 | 1.37 | 0.62 | 0.0115 | 2.85 |
| bottom | q50 | 0.46 | 0.85 | 0.26 | 0.0077 | 1.47 |
| bottom | q99 | 0.00 | 2.15 | 0.95 | 0.0604 | 3.71 |

## 핵심 패턴

- **Bottom tier (poorly modeled basins by M1)**: q99이 peak underestimation을 거의 0으로 줄임 (α=0). recall 0.95. 단 FAR도 가장 큼 (0.06).
- **Top tier (well-modeled basins by M1)**: q99 peak under 22% 잔존, recall 0.39. over-pred magnitude는 가장 크다 (7.83) — high-flow basin 자체가 큰 절대값.
- 효과의 직관: M1이 약한 basin일수록 quantile model의 alleviation 효과가 절대적으로 크지만, 그 대가도 함께 커진다.

## 산출물

```text
output/model_analysis/expanded_drbc_test/tables/
  rq4a_nse_tier_assignments.csv
  rq4a_nse_tier_metrics.csv
output/model_analysis/expanded_drbc_test/figures/
  rq4a_tier_metric_heatmap.png
```

## 주의점 (circularity caveat)

- cohort axis가 central performance(NSE), stratify metric이 peak metric이므로 약한 부분 상관은 존재. 강한 순환은 아니다.
- 절대값 (over-pred magnitude)은 basin scale에 종속적이며, top tier에서 over-pred가 큰 것은 high-flow basin 자체의 크기를 반영한다.
- bottom tier에서 α=0은 sub-sample selection effect도 일부 포함될 수 있으나 cohort 정의가 *순환적이지 않으므로* 결과는 신뢰할 수 있다.
