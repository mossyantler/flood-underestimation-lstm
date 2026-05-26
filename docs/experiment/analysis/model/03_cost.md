# 03 RQ-3 Cost — False Alarm Rate + Over-prediction Magnitude

## 질문 (RQ-3)

upper quantile output(q90/q95/q99)이 peak underestimation을 줄이는 이득(RQ-2)의 대가로 어떤 false-positive / over-prediction 비용이 따라오는가? cost는 두 축으로 정의한다.

- **FAR (false alarm rate)**: `P(q_τ > Q99_basin | obs < Q99_basin)` — per-basin per-seed
- **Over-prediction magnitude**: `mean(q_τ − obs | q_τ > obs)` — per-basin per-seed

## 데이터

- expanded DRBC observed test (85 basin, seed 111/222/444, test 2014-2016)
- per-basin Q99 threshold: train period 2000-2010 obs 분위 (`tables/rq2_q99_per_basin_thresholds.csv`)
- 모델 출력: `output/model_analysis/expanded_drbc_test/required_series/seed{111,222,444}/`

## 방법

스크립트: `scripts/model/expanded_drbc/compute_rq3_cost.py`

aggregation 순서 (C0 canonical): per-basin per-seed compute → median across seeds within basin → cross-basin median + IQR.

- FAR denominator: obs < Q99인 test-period 시각 (≈ 99% 전체 hour).
- Over-pred magnitude denominator: 시각별 `q_τ > obs`인 부분 mean.

## 결과 — cross-basin median (Q99 baseline, 85 basin)

| τ | FAR | Over-prediction magnitude |
| --- | --- | --- |
| model1 | 0.0018 | 1.80 |
| q50 | 0.0007 | 1.47 |
| q90 | 0.0042 | 2.19 |
| q95 | 0.0063 | 2.29 |
| q99 | 0.0164 | 3.44 |

τ가 커질수록 FAR이 단조 증가 (q50 → q99 9× 폭증). Over-prediction magnitude도 비례 증가.

`figures/rq3_cost_recall_tradeoff.png`: B5 recall과 B6 FAR을 동일 axis에 그려 Pareto-like 관계 시각화.

## RQ-2 ↔ RQ-3 통합 해석

RQ-2 (recall, B5) + RQ-3 (FAR, B6) 결합:

| τ | recall (basin median) | FAR (basin median) |
| --- | --- | --- |
| q50 | 0.07 | 0.0007 |
| q90 | 0.28 | 0.0042 |
| q95 | 0.38 | 0.0063 |
| q99 | 0.58 | 0.0164 |

upper τ는 recall을 monotone 증가(0.07 → 0.58)시키면서 FAR도 monotone 증가(0.0007 → 0.0164)시킨다. recall 8× 증가 vs FAR 23× 증가 → recall–cost 비대칭. 운영 의사결정자가 trade-off 선택 가능.

## 해석 framework 적용 (RQ-0)

[`docs/experiment/method/model/quantile_output_interpretation.md`](../../method/model/quantile_output_interpretation.md)의 L3 (운영 decision output) layer + Sequence reading. RQ-3는 "upper quantile output을 alert level로 쓸 때 false-positive 비용을 함께 측정" 원칙을 구현한다.

## 산출물

```text
output/model_analysis/expanded_drbc_test/tables/
  rq3_far_per_basin_seed.csv
  rq3_far_summary.csv
  rq3_over_prediction_magnitude_per_basin_seed.csv
  rq3_over_prediction_magnitude_summary.csv
output/model_analysis/expanded_drbc_test/figures/
  rq3_cost_recall_tradeoff.png
```

## 주의점

- FAR이 절대값으로 작아 보이는 이유는 분모가 99%의 non-exceedance 시간이기 때문이다. Q99 exceedance가 매우 드문 사건임을 반영한다.
- Over-pred magnitude는 obs unit (mm/hr 단위 streamflow). 절대값 비교는 basin scale에 종속적이며, basin 간 비교 시 relative scale (obs / over-pred ratio)도 함께 본다.
- operational/economic cost (재해 대응 단위 비용)은 본 분석 범위 밖이다.
