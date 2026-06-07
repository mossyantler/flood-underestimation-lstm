# 02 RQ-2 — Model 2 출력 심층 분석

## 질문 (RQ-2)

Model 2 probabilistic quantile LSTM의 4-quantile 출력(`q50 / q90 / q95 / q99`)은 어떻게 생겼는가? 입력 특성과 출력 간 상관 구조는 무엇이고, 유량 체제·강우 유형·실제 홍수 상황에서 출력 패턴이 어떻게 달라지는가?

각 하위 분석은 **Model 2 출력 자체를 기술(describe)** 한다. τ-진행이 과소추정을 실제로 줄이는지에 대한 모델 평가(predicted vs actual)는 RQ-3(§3e)에서 다룬다.

공통 데이터:
- expanded DRBC observed test (85 basin, seed `111 / 222 / 444`, test 2014-2016)
- 모델 출력: `output/model_analysis/primary/metrics/data/required_series/seed{111,222,444}/required_series.csv`

하위 분석: **2a** 각 quantile 출력 특성 · **2b** 입력-출력 상관(SHAP) · **2c** 밴드 형태 및 gap 구조 · **2d** 보정 및 예리도 · **2e** 실제 홍수 사건 출력 · **2f** 강우 유형별 출력 패턴.

---

## 2a. 각 quantile 출력 특성 (τ별 α/β/δ)

**질문**: `q50→q90→q95→q99` τ-진행에서 각 quantile 출력이 관측 첨두를 어떻게 표현하는가?

**비자명성**: "q99 출력값이 q50보다 높다"는 by construction 자명하다. 비자명한 주장은 "pinball loss 훈련 목적 함수 전환이 극한 유량 표현을 개선한다"이며, RQ-1(q50도 함께 개선: NSE +0.149)이 이 학습 효과를 뒷받침한다.

Metric triplet (각 τ의 출력을 관측 첨두에 견주어 기술):
- **α — event peak under-deficit**: per-event `(obs_peak − q_τ_at_peak)_+ / obs_peak`
- **β — ±6h window peak capture**: per-event `max(q_τ in window) / max(obs in window)`
- **δ — Q99 threshold recall**: pooled `P(q_τ ≥ obs | obs ≥ Q99_basin)`

스크립트:
- α: `scripts/model/expanded_drbc/compute_rq2_alpha_peak_deficit.py`
- β: `scripts/model/expanded_drbc/compute_rq2_beta_window_capture.py`
- δ: `scripts/model/expanded_drbc/compute_rq2_delta_threshold_recall.py`

### 결과 — Q99 scope (85 basin / 926 events)

**α (event peak under-deficit, basin median)**

| τ | basin median | IQR (low / high) |
| --- | --- | --- |
| model1 | 0.588 | 0.228 / 0.762 |
| q50 | 0.657 | 0.298 / 0.816 |
| q90 | 0.376 | 0.000 / 0.561 |
| q95 | 0.272 | 0.000 / 0.442 |
| q99 | **0.018** | 0.000 / 0.283 |

**β (±6h window capture)** / **δ (Q99 threshold recall, pooled)** / **miss rate (1 − δ)**

| τ | β (basin median) | δ recall | miss rate (%) |
| --- | --- | --- | ---: |
| model1 | 0.519 | 0.143 | 85.7 |
| q50 | 0.444 | 0.069 | 93.1 |
| q90 | 0.733 | 0.280 | 72.0 |
| q95 | 0.920 | 0.379 | 62.1 |
| q99 | **1.306** | **0.583** | **41.7** |

### 결과 — NOAA scope (21 basin / 65 events)

| τ | α (basin median) [IQR] | β (basin median) [IQR] |
| --- | --- | --- |
| model1 | 0.676 [0.516 / 0.828] | 0.400 [0.194 / 0.647] |
| q50 | 0.788 [0.739 / 0.817] | 0.282 [0.223 / 0.368] |
| q90 | 0.482 [0.428 / 0.630] | 0.566 [0.465 / 0.703] |
| q95 | 0.404 [0.273 / 0.544] | 0.677 [0.552 / 0.818] |
| q99 | **0.172** [0.000 / 0.367] | **0.977** [0.814 / 1.402] |

NOAA confirmed flood 위에서도 q99이 peak deficit 17% / window capture 98% — Q99 scope와 같은 방향. **NOAA scope의 q99 α(0.172)는 Q99 scope(0.018)의 약 9.5배** — NOAA 공식 확인 홍수가 모델이 더 잡기 어려운 hard subset임을 보여 준다.

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
  rq2_alpha_by_tau.png · rq2_tau_progression.png · rq2_beta_by_tau.png · rq2_delta_recall_by_tau.png
```

---

## 2b. 입력-출력 상관 (SHAP)

**질문**: 어떤 입력 특성이 Model 2의 예측 기여에 어떻게 작용하는가?

SHAP(SHapley Additive exPlanations) 분석은 Model 2 예측 기여도를 정적 유역 속성과 동적 기상 강제력으로 분해한다. 핵심 발견:
- **정적 ≫ 동적**: 정적 유역 속성이 동적 기상 강제력보다 압도적으로 큰 기여(보고서 기준 66–75배).
- **area × soil_depth 게이트**: 집수 면적이 크더라도 얕은 토양 조건에서만 q99 기여를 강하게 상향하는 게이트 구조.
- **slope 극한 반전**: 경사 기여의 부호가 극한 구간에서 반전.
- **강우 유형 신호**: 대류성 강수비(CRainf_frac)·CAPE가 강우 유형을 구분하는 동적 신호로 등장 → 이 구분법을 **§2f가 차용**(SHAP value 자체는 미사용).

분석 범위:
- `direction/`: 특성별 방향성(양/음) 기여
- `q99/`: Q99 초과 사건의 SHAP 기여
- `test_split/`: test split 전체 SHAP 분포

스크립트: `scripts/runs/official/run_q99_lstm_direct_shap_all_basins.sh`

산출물:
```text
output/model_analysis/shap/
├── direction/   report/ · figures/ · tables/ · data/
├── q99/
└── test_split/
```

---

## 2c. 밴드 형태 및 gap 구조

**질문**: q50~q99 예측 밴드의 폭·꼬리·위치는 어떻게 생겼고, τ 사이의 gap은 어떻게 변하는가?

밴드 형태 분석은 출력 밴드의 기하(폭·상단 꼬리·중심 위치)와 인접 τ 사이의 gap trajectory를 기술한다. 관측 위치와의 상관(신호 분석)은 RQ-3(§3b)에서 다루고, 여기서는 **출력 밴드 자체의 형태**만 본다.

**핵심 패턴**:
- **밴드 폭**: `q99 − q50` 폭이 관측 첨두 시각에서 절대값 최대로 벌어진다. 전체 시각 기준 폭은 관측의 약 122%.
- **gap trajectory**: q50→q90→q95 구간의 과소-gap이 점진 수렴하다가, q95→q99에서 추가로 좁혀지는 동시에 q99 위쪽으로 **과대-gap(over-gap)** 이 처음 등장한다(Q99 scope 유역 중앙값 상대 over_gap 0.122).
- 상단 꼬리는 NOAA scope에서 더 두껍다 — hard subset에서 밴드가 더 넓게 벌어진다.

스크립트:
- `scripts/model/expanded_drbc/compute_band_shape.py`
- `scripts/model/expanded_drbc/compute_gap_trajectory.py`

산출물:
```text
output/model_analysis/band_signal/band_shape/tables/
  band_shape_metrics_noaa.csv
  gap_trajectory_noaa.csv + _summary.csv
output/model_analysis/band_signal/band_shape/   # band_shape 주제 폴더 (tables/figures)
```

---

## 2d. 보정 및 예리도 (calibration / sharpness)

**질문**: Model 2의 `q50/q90/q95/q99`가 quantile forecast로서 얼마나 calibrated·sharp한가?

`calibration`은 관측값이 예측 quantile 아래에 들어오는 비율(포함률)이 공칭값과 얼마나 맞는지를, `sharpness`(예리도)는 예측이 climatology 대비 얼마나 더 정보적인지를 가리킨다.

스크립트: `scripts/model/hydrograph/analyze_expanded_drbc_probabilistic_diagnostics.py`

### All-hour one-sided 포함률

| τ | nominal | empirical (basin median) | coverage error |
| --- | --- | --- | --- |
| q50 | 0.50 | **0.339** | −0.16 |
| q90 | 0.90 | **0.506** | −0.39 |
| q95 | 0.95 | **0.638** | −0.31 |
| q99 | 0.99 | **0.787** | −0.20 |

모든 τ에서 공칭값보다 낮은 undercoverage. **`q99` ≠ "calibrated 99% predictive quantile"**.

### Pinball / tail hit-rate / skill score (basin median)

| τ | mean pinball | Q99-exceedance tail hit-rate | skill score (vs climatology) |
| --- | --- | --- | --- |
| q50 | 4.656 | 0.218 | +0.104 |
| q90 | 3.658 | 0.371 | **+0.217** |
| q95 | 2.858 | 0.424 | +0.132 |
| q99 | **1.638** | **0.563** | −0.271 |

- q99이 mean pinball 최소 — high-flow asymmetric loss에 잘 맞춰진다.
- Q99 이상 시각의 56%를 q99이 잡는다 — §2a δ-recall 0.583과 일치.
- **q99은 climatology baseline 대비 sharpness 손해** — 극단 quantile은 단순 climatology 추정 대비 pinball 악화.

**프레이밍**: "calibration이 완전하지 않더라도 high-flow tail에서 의미 있게 peak를 잡는 **upper-tail decision output**"으로 frame한다. "calibrated 99% predictive quantile" 표현 사용 금지.

산출물:
```text
output/model_analysis/primary/calibration/
  tables/   quantile_pinball_summary.csv · quantile_calibration_summary.csv
            upper_tail_spread_summary.csv · peak_event_capture_rate.csv · quantile_skill_score.csv
  report/report.md
  figures/
```

---

## 2e. 실제 홍수 사건 출력 (NOAA confirmed flood)

**질문**: NWS flood-stage 기준 실제 확인 홍수 사건에서 Model 2 출력은 어떤 패턴을 보이며, 홍수 유형(Flash Flood vs Flood)별로 어떻게 달라지는가?

NWS flood-stage exceedance catalog(664 events / 49 USGS basin)를 expanded DRBC 85 시험 유역 × 2014–2016 시험기간으로 자른다.

**사건 수 정의 (혼용 금지)**:
- **전체 NOAA 확인 홍수**: **65 events / 21 basin** — §2a NOAA scope, §3a NOAA 분포의 기준.
- **홍수 유형 subset**: NOAA Storm Events 주석에서 유형이 확정된 사건만 = **Flash Flood 8 + Flood 32 = 40 events**. 나머지(NoNOAA 등)는 유형 미확정으로 유형별 표에서 제외. 유형별 α는 이 40-event subset 기준이다.

스크립트:
- `scripts/model/expanded_drbc/build_noaa_mapping.py`
- `scripts/model/expanded_drbc/compute_rq4b_event_type_stratify.py`

### α (peak deficit) — 홍수 유형별, 전 τ (유형 subset)

| Event Type (n_events / n_basins) | model1 | q50 | q90 | q95 | q99 |
| --- | --- | --- | --- | --- | --- |
| Flash Flood (8 / 6) | 0.926 | 0.943 | 0.776 | 0.696 | **0.417** |
| Flood (32 / 15) | 0.569 | 0.780 | 0.472 | 0.382 | **0.060** |

**핵심 패턴**:
- **Flash Flood가 가장 어려운 유형**: q99에서도 peak deficit 0.42 잔존. Flood(0.06) 대비 약 7배.
- **Flood (riverine)**: q99에서 deficit 0.06 — quantile 출력이 잘 작동.
- 돌발홍수의 과소추정 잔존은 §2f의 대류성 강수비·CAPE 신호, RQ-3(§3b)의 CRainf_frac 결과와 일관.

> **주의 (순환 위험)**: NWS flood-stage 정의가 quantile 임계와 결합될 가능성이 있으므로, 유형 미확정(NoNOAA) 사건은 NOAA-confirmed 주장 근거로 쓰지 않는다.

산출물:
```text
output/model_analysis/confirmed_flood/   data/ · figures/ · tables/ · report/
output/model_analysis/primary/metrics/tables/  rq4b_event_type_mapping.csv · rq4b_event_type_metrics.csv
output/model_analysis/primary/metrics/figures/ rq4b_event_type_bar.png
```

---

## 2f. 강우 유형별 출력 패턴 (신규 분석)

**질문**: 대류성(convective) 강수와 전선성(frontal) 강수에서 Model 2의 τ 출력 분포와 첨두 과소(α)는 어떻게 달라지는가?

§2b SHAP이 발견한 **강우 유형 구분법(대류성 강수비 CRainf_frac)** 을 차용하되, SHAP value 파일은 import하지 않고 NOAA 확인 홍수 사건에서 강우 유형별 출력 패턴을 새로 계산한다.

**SSOT split**: CRainf 중앙값 이분 임계는 `scripts/_lib/expanded_drbc.py`의 공용 함수 `crainf_median_split`에서 가져오며, **RQ-3(§3c)의 obs_class 층화 분포와 동일한 split**을 공유한다. 같은 split에서 고 CRainf 그룹의 above_q99 비율 67.9%, 저 CRainf 24.1%가 나오며(§3c, draft 표 9 인접 서술), 본 분석은 이 split을 공유하되 산출은 obs_class 분포가 아닌 **출력값 차원(첨두 포착률·α)** 이다.

**n-gate**: 강우 유형 셀의 사건 수 n<10이면 통계를 suppress한다(예: NOAA 이벤트타입 Flash Flood n=8은 자동 제외). 본 CRainf 이분은 고 28 / 저 29로 모두 통과.

스크립트: `scripts/model/expanded_drbc/compute_rq2f_rain_type_output.py`

### 첨두 포착률(capture = 1 − α) 및 α — CRainf 축, τ별 (NOAA 57-event subset)

| 강우 유형 (n) | τ | 첨두 포착률 (median) | α (median) |
| --- | --- | --- | --- |
| 대류성 High CRainf (28) | q50 | 0.210 | 0.790 |
| | q95 | 0.475 | 0.525 |
| | q99 | **0.667** | **0.333** |
| 전선성 Low CRainf (29) | q50 | 0.250 | 0.750 |
| | q95 | 0.734 | 0.266 |
| | q99 | **1.000** | **0.000** |

**핵심 패턴**:
- **전선성 강수**: q99에서 α=0.000(첨두 완전 포착) — quantile 출력이 전선성 첨두를 충분히 잡는다.
- **대류성 강수**: q99에서도 α=0.333 잔존(첨두의 약 2/3만 포착) — 대류성 첨두는 전 τ에서 포착 저항.
- **대류성/전선성 α 대비**: q95에서 대류성 α가 전선성의 약 1.97배. 강우 유형이 출력 포착력을 강하게 가른다.
- 이 패턴은 §2e의 Flash Flood 과소추정 잔존(약 7배), RQ-3(§3b)의 CRainf_frac 독립 신호와 일관.

> 본 절은 **NOAA 57-event subset**(CRainf 특성이 산출된 사건) 기준이다. §2a NOAA scope의 65 events(전체 확인 홍수), §2e 유형 subset 40 events와 표본이 다르므로 혼용하지 않는다.

산출물:
```text
output/model_analysis/primary/metrics/tables/
  rq2f_rain_type_tau_output.csv   # 강우유형 × τ 첨두 포착률 분포
  rq2f_rain_type_alpha.csv        # 강우유형 × τ α 패턴
  rq2f_rain_type_contrast.csv     # 대류성 vs 전선성 α 대비
output/model_analysis/primary/metrics/figures/
  rq2f_rain_type_patterns.png
```

---

## 주의점

- band vs point 비대칭: Model 2의 q99는 밴드(범위)이고 Model 1은 점 예측이다. 직접 비교 대신 τ-진행 내부 단조성을 보이고, Model 1과의 연결은 RQ-1(q50 ≈ Model 1)을 통해 간접적으로 맺는다.
- q99에서 `q99` ≠ "calibrated 99% predictive quantile". upper-tail decision output 표현 유지.
- 사건 수 N 혼용 금지: NOAA 전체 **65** / CRainf 유형 subset **57**(§2f) / 홍수 유형 subset **40**(§2e, Flash 8 + Flood 32).
- FAR·over-prediction 비용과 M1 NSE tier 이질성은 본 RQ-2 출력 기술에서 분리하여 RQ-3(§3e 모델 평가)에서 predicted vs actual 혼동행렬 틀로 다룬다.
