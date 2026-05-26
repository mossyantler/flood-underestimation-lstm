# 01 RQ-1 — q50 Central Performance

## 질문 (RQ-1)

Model 2 probabilistic quantile LSTM의 conditional median output `q50`이 Model 1 deterministic LSTM 대비 중앙예측(central) 성능을 큰 손해 없이 유지하는가? RQ-1은 RQ-2 (upper quantile peak under reduction) 주장의 전제 조건이다 — `q50`이 무너지면 quantile model의 가치가 약해진다.

## 데이터

- expanded DRBC observed test (85 basin, seed 111/222/444, test 2014-2016)
- 모델 출력: `output/model_analysis/expanded_drbc_test/required_series/seed{111,222,444}/primary_required_series.csv`
- 비교 대상: Model 1 deterministic prediction (`model1`), Model 2 conditional median (`q50`)

## 방법

스크립트: `scripts/model/expanded_drbc/compute_rq1_central_metrics.py`

- 5-metric: NSE, KGE, bias = mean(pred − obs), MAE = mean(|pred − obs|), RMSE = sqrt(mean((pred − obs)²))
- per-basin per-seed 각 모델별 metric 산출
- Paired delta = `metric(M2_q50, seed) − metric(M1, seed)` per basin per seed (per-seed level delta, not delta-of-medians)
- Aggregation: per-basin per-seed → median across seeds within basin → cross-basin pooled summary
- NaN policy: obs-NaN 시각 drop (C0)

### 검증 (acceptance)

- NSE/KGE: 새 산출물 vs `raw_metrics/model1_seed111_epoch025_metrics.csv` 1e-6 이내 (5 basin spot-check, max diff = 1.29e-7).
- bias/MAE/RMSE: NumPy 핸드 컴퓨트 (2 basin) 1e-6 이내 (실제 diff = 0 / 4.44e-16).
- 510-row wide + 425-row long contract 충족.

## 결과 (cross-basin pooled summary)

| Metric | M1 (basin median) | M2 q50 (basin median) | Δ (q50 − M1, basin median) | Δ IQR low / high |
| --- | --- | --- | --- | --- |
| NSE | −0.031 | 0.225 | **+0.149** | −0.039 / +0.448 |
| KGE | 0.082 | 0.158 | +0.041 | −0.087 / +0.343 |
| Bias | −0.459 | −0.948 | −0.437 | −1.087 / +0.319 |
| MAE | 2.584 | 2.509 | −0.197 | −0.780 / +0.126 |
| RMSE | 4.850 | 4.393 | −0.273 | −1.140 / +0.246 |

### 해석

- **NSE / KGE / RMSE / MAE**: M2 q50가 M1 대비 개선. NSE +0.15, RMSE −0.27, MAE −0.20.
- **Bias**: M2 q50가 더 negative — 평균적으로 obs보다 더 under-predict한다. **RQ-2 / RQ-5 결과와 일관:** q50은 conditional median이지만 high-flow 시각에서 strong under-bias를 보인다. M1은 quadratic loss에 의해 mean을 따라가는 반면, M2 q50은 pinball loss에 의해 median을 따라가므로 skewed flow 분포에서 mean ≠ median 차이가 bias로 드러난다.

→ 전체적으로 q50은 central 성능을 유지(NSE/RMSE 개선)하는 한편 high-flow 시각에서는 under-bias가 더 크다. 이는 RQ-2 (upper quantile alleviation) 동기를 정당화한다.

## 해석 framework 적용 (RQ-0)

[`docs/experiment/method/model/quantile_output_interpretation.md`](../../method/model/quantile_output_interpretation.md)의 L3 (운영 decision output) layer + Pairwise reading (q50 vs M1). `q50`만 사용하고 `q90/q95/q99`를 끌고 들어오지 않는다.

## 산출물

```text
output/model_analysis/expanded_drbc_test/tables/
  rq1_central_metrics_per_basin_seed.csv     (510 rows)
  rq1_central_metrics_seed_median.csv        (425 rows)
  rq1_central_metrics_pooled_summary.csv
output/model_analysis/expanded_drbc_test/figures/
  rq1_central_metric_boxplots.png
  rq1_paired_delta_scatter.png
```

## 주의점

- bias의 sign 차이는 M1 (mean-tracking) vs M2 q50 (median-tracking) loss difference. 본질적 model failure가 아니다.
- "큰 손해 없이"의 정량적 기준은 plan에서 명시되지 않았으나 NSE +0.15는 paper 본문 headline으로 사용 가능한 수준이다.
