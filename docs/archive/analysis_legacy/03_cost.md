# 03 RQ-3 Cost — False Alarm Rate + Over-prediction Magnitude

## 질문 (RQ-3)

upper quantile output(q90/q95/q99)이 peak underestimation을 줄이는 이득(RQ-2)의 대가로 어떤 false-positive / over-prediction 비용이 따라오는가? cost는 두 축으로 정의한다.

- **FAR (false alarm rate)**: `P(q_τ > Q99_basin | obs < Q99_basin)` — per-basin per-seed
- **Over-prediction magnitude**: `mean(q_τ − obs | q_τ > obs)` — per-basin per-seed

## 데이터

- expanded DRBC observed test (85 basin, seed 111/222/444, test 2014-2016)
- per-basin Q99 threshold: train period 2000-2010 obs 분위 (`tables/rq2_q99_per_basin_thresholds.csv`)
- 모델 출력: `output/model_analysis/primary/metrics/data/required_series/seed{111,222,444}/required_series.csv`

## 방법

스크립트: `scripts/model/expanded_drbc/compute_rq3_cost.py`

aggregation 순서 (C0 canonical): per-basin per-seed compute → median across seeds within basin → cross-basin median + IQR.

- FAR denominator: obs < Q99인 test-period 시각 (≈ 99% 전체 hour).
- Over-pred magnitude denominator: 시각별 `q_τ > obs`인 부분 mean.

## 결과 — cross-basin median + IQR (Q99 baseline, 85 basin)

| τ | FAR [IQR low / high] | Over-prediction magnitude [IQR low / high] |
| --- | --- | --- |
| model1 | 0.0018 [0.0 / 0.0073] | 1.80 [1.00 / 5.10] |
| q50 | 0.00068 [0.00004 / 0.0048] | 1.47 [0.85 / 4.17] |
| q90 | 0.0042 [0.0012 / 0.0139] | 2.19 [1.24 / 6.05] |
| q95 | 0.0063 [0.0020 / 0.0198] | 2.29 [1.47 / 7.33] |
| q99 | 0.0164 [0.0060 / 0.0359] | 3.44 [2.42 / 10.47] |

τ가 커질수록 FAR이 단조 증가 (q50 0.00068 → q99 0.0164, 약 **24배 폭증**). Over-prediction magnitude도 비례 증가 (q50 1.47 → q99 3.44, 약 2.3배).

IQR 폭이 넓다 (q99 FAR 0.006~0.036, over-pred 2.4~10.5) — basin 간 cost 이질성이 크다. over-pred magnitude는 basin 평균 유량 규모에 종속되므로 top-NSE basin(원래 고유량)에서 절대값이 크다(RQ-4a 참조).

`figures/rq3_cost_recall_tradeoff.png`: B5 recall과 B6 FAR을 동일 axis에 그려 Pareto-like 관계 시각화.

## RQ-2 ↔ RQ-3 통합 해석

RQ-2 (recall, B5) + RQ-3 (FAR, B6) 결합:

| τ | recall (basin median) | FAR (basin median) |
| --- | --- | --- |
| q50 | 0.07 | 0.0007 |
| q90 | 0.28 | 0.0042 |
| q95 | 0.38 | 0.0063 |
| q99 | 0.58 | 0.0164 |

upper τ는 recall을 monotone 증가(0.069 → 0.583, 약 8배)시키면서 FAR도 monotone 증가(0.00068 → 0.0164, 약 24배)시킨다. 절대 증가폭으로 보면 FAR 변화(+0.016)가 recall 변화(+0.51)보다 훨씬 작아, **드문 false alarm 비용 대비 recall 이득이 크다**. 단 배수로는 FAR이 더 가파르게 증가하므로 운영 의사결정자는 recall–cost trade-off에서 τ를 선택한다(q95가 recall 0.38 / FAR 0.0063으로 균형점 후보).

## 해석 framework 적용 (RQ-0)

[`docs/experiment/method/model/quantile_output_interpretation.md`](../../method/model/quantile_output_interpretation.md)의 L3 (운영 decision output) layer + Sequence reading. RQ-3는 "upper quantile output을 alert level로 쓸 때 false-positive 비용을 함께 측정" 원칙을 구현한다.

## 산출물

```text
output/model_analysis/primary/metrics/tables/
  rq3_far_per_basin_seed.csv
  rq3_far_summary.csv
  rq3_over_prediction_magnitude_per_basin_seed.csv
  rq3_over_prediction_magnitude_summary.csv
output/model_analysis/primary/metrics/figures/
  rq3_cost_recall_tradeoff.png
```

## 주의점

- FAR이 절대값으로 작아 보이는 이유는 분모가 99%의 non-exceedance 시간이기 때문이다. Q99 exceedance가 매우 드문 사건임을 반영한다.
- Over-pred magnitude는 obs unit (mm/hr 단위 streamflow). 절대값 비교는 basin scale에 종속적이며, basin 간 비교 시 relative scale (obs / over-pred ratio)도 함께 본다.
- operational/economic cost (재해 대응 단위 비용)은 본 분석 범위 밖이다.
