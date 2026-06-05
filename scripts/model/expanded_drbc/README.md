# scripts/model/expanded_drbc/

Expanded DRBC observed test (85 basin, seed 111/222/444, test 2014-2016) 기반 RQ 분석 스크립트.
공통 상수·유틸리티는 `scripts/_lib/expanded_drbc.py` (C0) 에서 import.

## 실행 순서

```text
Phase A  (독립)
  compute_rq1_central_metrics.py        # A1 — RQ-1 central metrics (NSE/KGE/bias/MAE/RMSE)

Phase B  (B1·B2 먼저, 이후 병렬 가능)
  build_q99_events.py                   # B1 — per-basin Q99 threshold + event extraction
  build_noaa_mapping.py                 # B2 — NOAA catalog → expanded basin mapping

  compute_rq2_alpha_peak_deficit.py     # B3 — RQ-2 α event peak under-deficit
  compute_rq2_beta_window_capture.py    # B4 — RQ-2 β ±6h window capture
  compute_rq2_delta_threshold_recall.py # B5 — RQ-2 δ Q99 threshold recall

  compute_rq3_cost.py                   # B6 — RQ-3 FAR + over-prediction magnitude
  compute_rq4a_nse_tier_stratify.py     # B7 — RQ-4a M1 NSE 3-tier cohort (depends B3-B6)
  compute_rq4b_event_type_stratify.py   # B8 — RQ-4b NOAA event-type cohort (depends B2·B3)
  compute_cross_tab_q99_noaa_sanity.py  # B9 — Q99 ∩ NOAA geometry sanity (depends B1·B2)

  compute_ub_location_class.py          # B10 — UB obs location class (below_q50 ~ above_q99)
  compute_ub_gap_trajectory.py          # B11 — UB gap trajectory (under/over-gap by τ)
  compute_ub_band_shape.py              # B12 — UB band-shape prospective (rel_width, g3_ratio, Spearman r)
```

## 실행 방법

전체 RQ-0~4 산출물을 canonical 순서로 재생성:

```bash
uv run scripts/model/expanded_drbc/run_all.py
```

실제 실행 전 child command만 확인:

```bash
uv run scripts/model/expanded_drbc/run_all.py --dry-run
```

개별 script만 다시 실행:

```bash
uv run scripts/model/expanded_drbc/<script>.py
```

## 산출물

```text
output/model_analysis/primary/metrics/
├── data/required_series/seed{111,222,444}/required_series.csv
├── data/raw_metrics/
├── tables/     # rq1_*, rq2_*, rq3_*, rq4a_*, rq4b_*, cross_tab_* CSV
└── figures/    # rq1_*, rq2_*, rq3_*, rq4a_*, rq4b_* PNG

output/model_analysis/band_signal/
├── band_shape/    # band_shape_*, location_class_*, hydrograph fan
├── slope_signal/
├── signal_sweep/
└── method_compare/
```

RQ-5 calibration·sharpness 산출물은 `scripts/model/hydrograph/analyze_expanded_drbc_probabilistic_diagnostics.py` 재활용 → `output/model_analysis/primary/calibration/`.

## 분석 문서

각 RQ 결과는 `docs/experiment/analysis/model/` 에서 관리.
