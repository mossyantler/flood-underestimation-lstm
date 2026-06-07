# 02 RQ-2 — Model 2 상세 분석

## 질문 (RQ-2)

Model 2 probabilistic quantile LSTM의 내부 구조와 성능을 어떻게 이해할 것인가? `q50→q90→q95→q99` τ-진행이 극한 홍수 첨두 과소추정을 체계적으로 줄이는지 확인하고, 이 결과를 SHAP·band signal·calibration·이질성 분석으로 뒷받침한다.

공통 데이터:
- expanded DRBC observed test (85 basin, seed 111/222/444, test 2014-2016)
- 모델 출력: `output/model_analysis/primary/metrics/data/required_series/seed{111,222,444}/required_series.csv`

---

## 2a. Q99/NOAA peak underestimation (τ-진행)

**질문**: τ 수준이 높아질수록 expanded DRBC peak underestimation이 체계적으로 줄어드는가?

**비자명성**: "q99 출력값이 q50보다 높다"는 by construction 자명하다. 비자명한 주장은 "pinball loss 훈련 목적 함수 전환이 극한 유량 표현을 개선한다"이며, RQ-1(q50도 함께 개선: NSE +0.149)이 이 non-trivial 학습 효과를 뒷받침한다.

Metric triplet:
- **α — event peak under-deficit**: per-event `(obs_peak − q_τ_at_peak)_+ / obs_peak`
- **β — ±6h window peak capture**: per-event `max(q_τ in window) / max(obs in window)`
- **δ — Q99 threshold recall**: pooled `P(q_τ ≥ obs | obs ≥ Q99_basin)`

스크립트:
- α: `scripts/model/expanded_drbc/compute_rq2_alpha_peak_deficit.py`
- β: `scripts/model/expanded_drbc/compute_rq2_beta_window_capture.py`
- δ: `scripts/model/expanded_drbc/compute_rq2_delta_threshold_recall.py`

### 결과 — Q99 scope (85 basin)

**α (event peak under-deficit)**

| τ | basin median | IQR (low/high) |
| --- | --- | --- |
| model1 | 0.588 | 0.228 / 0.762 |
| q50 | 0.657 | 0.298 / 0.816 |
| q90 | 0.376 | 0.000 / 0.561 |
| q95 | 0.272 | 0.000 / 0.442 |
| q99 | **0.018** | 0.000 / 0.283 |

**β (±6h window capture)**

| τ | basin median |
| --- | --- |
| model1 | 0.519 |
| q50 | 0.444 |
| q90 | 0.733 |
| q95 | 0.920 |
| q99 | **1.306** |

**δ (Q99 threshold recall, pooled)**

| τ | basin median recall |
| --- | --- |
| model1 | 0.143 |
| q50 | 0.069 |
| q90 | 0.280 |
| q95 | 0.379 |
| q99 | **0.583** |

**miss rate (1 − δ)**

| τ | miss rate (%) |
| --- | ---: |
| model1 | 85.7 |
| q50 | 93.1 |
| q90 | 72.0 |
| q95 | 62.1 |
| **q99** | **41.7** |

### 결과 — NOAA scope (21 basin / 65 events)

| τ | α (basin median) [IQR] | β (basin median) [IQR] |
| --- | --- | --- |
| model1 | 0.676 [0.516 / 0.828] | 0.400 [0.194 / 0.647] |
| q50 | 0.788 [0.739 / 0.817] | 0.282 [0.223 / 0.368] |
| q90 | 0.482 [0.428 / 0.630] | 0.566 [0.465 / 0.703] |
| q95 | 0.404 [0.273 / 0.544] | 0.677 [0.552 / 0.818] |
| q99 | **0.172** [0.000 / 0.367] | **0.977** [0.814 / 1.402] |

NOAA confirmed flood 위에서도 q99이 peak deficit 17% / window capture 98% — Q99 scope와 같은 방향. **NOAA scope의 q99 α(0.172)는 Q99 scope(0.018)보다 약 9.5배 크다** — NOAA 공식 확인 홍수가 모델이 더 잡기 어려운 hard subset임을 보여 준다.

산출물:
```text
output/model_analysis/primary/metrics/tables/
  rq2_alpha_event_peak_deficit_q99.csv + _summary.csv
  rq2_alpha_event_peak_deficit_noaa.csv + _summary.csv
  rq2_beta_window_capture_q99.csv + _summary.csv
  rq2_beta_window_capture_noaa.csv + _summary.csv
  rq2_delta_threshold_recall_per_basin_seed.csv + _summary.csv
  rq2_miss_rate_summary.csv
output/model_analysis/primary/metrics/figures/
  rq2_alpha_by_tau.png
  rq2_tau_progression.png
  rq2_beta_by_tau.png
  rq2_delta_recall_by_tau.png
```

---

## 2b. SHAP 분석

**질문**: 어떤 입력 특성이 Model 2의 예측에 어떻게 기여하는가?

SHAP(SHapley Additive exPlanations) 분석은 Model 2의 예측 기여도를 분해한다. 고유량 사건에서 어떤 특성(기상 강제력, 유역 특성)이 q99 예측을 높이거나 낮추는지 확인한다.

분석 범위:
- `direction/`: 특성별 방향성(양/음) 분석 — 어떤 특성이 예측을 올리는가
- `q99/`: Q99 초과 사건에서의 SHAP 기여도
- `test_split/`: test split 전체에서의 SHAP 분포

스크립트: `scripts/runs/official/run_q99_lstm_direct_shap_all_basins.sh`

산출물:
```text
output/model_analysis/shap/
├── direction/
│   ├── report/direction_research_analysis.md
│   ├── figures/
│   ├── tables/
│   └── data/
├── q99/
└── test_split/
```

---

## 2c. Spearman r / band signal

**질문**: 예측 밴드(`q50`~`q99`)의 형태와 관측 위치의 상관관계는 무엇인가?

band signal 분석은 예측 밴드의 형태(폭·꼬리·위치)와 관측 첨두 위치의 상관관계를 탐색한다. obs_class 상관관계 분석과 함께 읽혀야 하며, 진짜 신호(독립 신호)와 가짜 신호(밴드 결합·선택 편향)를 구별한다.

**독립 신호 순위 (Spearman r vs obs_class)**

| 신호 | Q99 | NOAA | 전체강우 |
| --- | ---: | ---: | ---: |
| **유역 면적 area** | **+0.50** | **+0.50** | +0.27 |
| **대류성 강수비 CRainf_frac** | +0.05 | **+0.39** | +0.13 |
| baseflow_index | +0.20 | +0.44 | +0.20 |
| permeability | +0.32 | +0.04 | +0.26 |
| CAPE | +0.03 | +0.22 | +0.13 |

밴드 폭·강우 총량 등 밴드 결합 신호는 선택 편향 또는 정의상 결합으로 판정 — 예측 신호로 쓸 수 없음. 상세 분석은 [`03_rq3_obs_class_interpretation.md`](03_rq3_obs_class_interpretation.md)에서 다룬다.

스크립트:
- `scripts/model/expanded_drbc/signal_sweep_nondrbc_allrain.py`
- `scripts/model/expanded_drbc/build_obsclass_features.py`

산출물:
```text
output/model_analysis/band_signal/
├── band_shape/tables/   location_class_{q99,noaa}_summary.csv, band_shape_spearman.csv
├── signal_sweep/tables/ branchA_spearman.csv, branchB2_spearman.csv
├── slope_signal/tables/ quantile_rise_slope_spearman.csv
└── signal_sweep/figures/ signal_sweep_3scope.png
```

---

## 2d. confirmed flood 성능

**질문**: NWS flood-stage 기준 확인 홍수 사건에서 Model 2의 성능은 어떠한가?

NWS flood-stage exceedance catalog(664 events / 49 USGS basin)를 expanded DRBC 85개 시험 유역 × 2014–2016 시험기간으로 자른 사건 범위(65 events / 21 basin)에서 Model 2의 성능을 평가한다.

산출물:
```text
output/model_analysis/confirmed_flood/
├── data/catalog/drbc_confirmed_flood_event_catalog.csv
├── figures/
├── tables/
└── report/
```

---

## 2e. cost: FAR·over-prediction

**질문**: upper quantile output이 peak underestimation을 줄이는 이득의 대가로 어떤 false-positive / over-prediction 비용이 따라오는가?

- **FAR (false alarm rate)**: `P(q_τ > Q99_basin | obs < Q99_basin)`
- **Over-prediction magnitude**: `mean(q_τ − obs | q_τ > obs)`

스크립트: `scripts/model/expanded_drbc/compute_rq3_cost.py`

### 결과 — cross-basin median + IQR (Q99 baseline, 85 basin)

| τ | FAR [IQR low / high] | Over-prediction magnitude [IQR low / high] |
| --- | --- | --- |
| model1 | 0.0018 [0.0 / 0.0073] | 1.80 [1.00 / 5.10] |
| q50 | 0.00068 [0.00004 / 0.0048] | 1.47 [0.85 / 4.17] |
| q90 | 0.0042 [0.0012 / 0.0139] | 2.19 [1.24 / 6.05] |
| q95 | 0.0063 [0.0020 / 0.0198] | 2.29 [1.47 / 7.33] |
| q99 | 0.0164 [0.0060 / 0.0359] | 3.44 [2.42 / 10.47] |

**2a ↔ 2e 통합 해석**:

| τ | recall (δ) | FAR |
| --- | --- | --- |
| q50 | 0.07 | 0.0007 |
| q90 | 0.28 | 0.0042 |
| q95 | 0.38 | 0.0063 |
| q99 | 0.58 | 0.0164 |

upper τ는 recall 8배 증가(0.069→0.583)와 FAR 24배 증가(0.00068→0.0164)를 동반한다. 절대 증가폭으로 보면 FAR 변화(+0.016)가 recall 변화(+0.51)보다 훨씬 작아, **드문 false alarm 비용 대비 recall 이득이 크다**.

산출물:
```text
output/model_analysis/primary/metrics/tables/
  rq3_far_per_basin_seed.csv
  rq3_far_summary.csv
  rq3_over_prediction_magnitude_per_basin_seed.csv
  rq3_over_prediction_magnitude_summary.csv
output/model_analysis/primary/metrics/figures/
  rq3_cost_recall_tradeoff.png
```

---

## 2f. calibration/sharpness

**질문**: Model 2의 `q50/q90/q95/q99`가 quantile forecast로서 얼마나 calibrated·sharp한가?

스크립트: `scripts/model/hydrograph/analyze_expanded_drbc_probabilistic_diagnostics.py`

### All-hour one-sided calibration

| τ | nominal | empirical (basin median) | coverage error |
| --- | --- | --- | --- |
| q50 | 0.50 | **0.339** | −0.16 |
| q90 | 0.90 | **0.506** | −0.39 |
| q95 | 0.95 | **0.638** | −0.31 |
| q99 | 0.99 | **0.787** | −0.20 |

모든 τ에서 nominal보다 낮은 undercoverage. **`q99` ≠ "calibrated 99% predictive quantile"**.

### Pinball / AQS (all-hour, basin median)

| τ | mean pinball |
| --- | --- |
| q50 | 4.656 |
| q90 | 3.658 |
| q95 | 2.858 |
| q99 | **1.638** |

q99이 mean pinball 최소 — high-flow asymmetric loss에 잘 맞춰진다.

### Q99-exceedance tail hit-rate (조건부)

| τ | tail hit-rate |
| --- | --- |
| q50 | 0.218 |
| q90 | 0.371 |
| q95 | 0.424 |
| q99 | **0.563** |

obs가 Q99 이상인 시각의 56%를 q99이 잡는다. RQ-2a δ-recall 0.583과 일치하는 신호.

### Skill score (vs train-period climatology)

| τ | skill score |
| --- | --- |
| q50 | +0.104 |
| q90 | **+0.217** |
| q95 | +0.132 |
| q99 | −0.271 |

**q99은 climatology baseline 대비 sharpness 손해** — 극단 quantile은 climatology 단순 추정 대비 pinball 악화.

### 통합 해석

RQ-2 / RQ-2e 결과를 "calibration이 완전하지 않더라도 high-flow tail에서 의미 있게 peak를 잡는 decision output"으로 frame한다. **upper-tail decision output**, **tail-aware output** 표현 사용. "calibrated 99% predictive quantile" 표현 사용 금지.

산출물:
```text
output/model_analysis/primary/calibration/
  quantile_pinball_summary.csv
  quantile_calibration_summary.csv
  upper_tail_spread_summary.csv
  peak_event_capture_rate.csv
  quantile_skill_score.csv
  report/report.md
  figures/
```

---

## 2g. 이질성 (basin cohort + event-type)

### 2g-i. Basin cohort heterogeneity (M1 NSE tier)

upper quantile output의 peak under 완화 효과·cost가 basin별로 얼마나 다른가? M1 NSE 3-tier(top/mid/bottom 1/3) 기준.

스크립트: `scripts/model/expanded_drbc/compute_rq4a_nse_tier_stratify.py`

Tier 사이즈: bottom 29 / mid 28 / top 28 = 85 basins. Tier 경계: bottom −171.8~−0.42, mid −0.39~0.24, top 0.25~0.61.

**핵심 패턴**:
- **Bottom tier** (M1이 못 맞추는 basin): q99에서 α = 0 (peak 완전 회복). 단 FAR = 0.060으로 최대.
- **Mid tier**: α가 q50(0.68)→q99(0.00)로 점진 감소.
- **Top tier** (M1이 잘 맞추는 basin): q99에서 α 0.215 잔존. over-pred magnitude 최대(7.83).

전체 tier × τ 결과:

| Tier (n) | τ | α | β | δ | FAR | Over-pred |
| --- | --- | --- | --- | --- | --- | --- |
| bottom (29) | q50 | 0.464 | 0.848 | 0.263 | 0.0077 | 1.467 |
| | q99 | **0.000** | 2.148 | 0.946 | 0.0604 | 3.707 |
| mid (28) | q50 | 0.681 | 0.390 | 0.070 | 0.0008 | 1.060 |
| | q99 | **0.000** | 1.369 | 0.618 | 0.0115 | 2.852 |
| top (28) | q50 | 0.736 | 0.305 | 0.017 | 0.0003 | 2.579 |
| | q99 | **0.215** | 0.917 | 0.394 | 0.0077 | 7.828 |

산출물:
```text
output/model_analysis/primary/metrics/tables/
  rq4a_nse_tier_assignments.csv
  rq4a_nse_tier_metrics.csv
output/model_analysis/primary/metrics/figures/
  rq4a_tier_metric_heatmap.png
```

### 2g-ii. Event-type heterogeneity (NOAA confirmed flood)

upper quantile output의 peak alleviation 효과·cost가 NOAA Storm Events 분류 event-type별로 얼마나 다른가?

스크립트: `scripts/model/expanded_drbc/compute_rq4b_event_type_stratify.py`

**α (peak deficit) — 전 τ**

| Event Type (n_events / n_basins) | model1 | q50 | q90 | q95 | q99 |
| --- | --- | --- | --- | --- | --- |
| Flash Flood (8 / 6) | 0.926 | 0.943 | 0.776 | 0.696 | **0.417** |
| Flood (32 / 15) | 0.569 | 0.780 | 0.472 | 0.382 | **0.060** |
| NoNOAA (25 / 9) | 0.715 | 0.782 | 0.442 | 0.349 | **0.000** |

**핵심 패턴**:
- **Flash Flood가 가장 어려운 event-type**: q99에서도 peak deficit 0.42 잔존. Flood(0.06)와 비교 시 약 7배 차이.
- **Flood (riverine)**: q99에서 peak deficit 0.06 — quantile output이 잘 작동.
- 돌발홍수에서 과소추정 잔존은 RQ-3의 대류성 강수비·CAPE 신호 결과와 일관된다.

산출물:
```text
output/model_analysis/primary/metrics/tables/
  rq4b_event_type_mapping.csv
  rq4b_event_type_metrics.csv
output/model_analysis/primary/metrics/figures/
  rq4b_event_type_bar.png
```

---

## 주의점

- band vs point 비대칭: Model 2의 q99는 밴드(범위)이고 Model 1은 점 예측이라 직접 비교는 구조가 다르다. 직접 비교 대신 τ-진행 내부 단조성을 보이고, Model 1과의 연결은 RQ-1(q50 ≈ Model 1)을 통해 간접적으로만 맺는다.
- q99에서 `q99` ≠ "calibrated 99% predictive quantile". upper-tail decision output 표현 유지.
- FAR 절대값이 작아 보이는 이유: 분모가 99%의 non-exceedance 시간이기 때문. Q99 exceedance가 매우 드문 사건임을 반영한다.
- NoNOAA q99 α=0.000 순환 위험: NWS flood-stage 정의가 quantile 임계와 결합될 가능성 — NoNOAA 결과를 NOAA-confirmed 주장 근거로 쓰지 않는다.
