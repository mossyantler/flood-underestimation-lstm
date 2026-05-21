# DRBC 유역별 진단 리포트 카드 설계

**날짜**: 2026-05-18
**스크립트**:
- `scripts/model/overall/compute_drbc_basin_report_card_data.py`
- `scripts/model/overall/plot_drbc_basin_report_cards.py`
**출력 루트**: `output/model_analysis/legacy/overall_analysis/main_comparison/drbc_basin_report_cards/`

---

## 분석 목표

38개 DRBC 유역 각각에 대해 "왜 성능이 낮은가"를 진단하는 다차원 리포트 카드를 생성한다.
유량 구간별 성능, 고유량 계절 패턴, 사건 단위 첨두 오차, 선행 조건 효과, 상승/하강 구간 비대칭을 포함한다.
최종 결과물은 논문에 직접 사용 가능한 publication-quality 그림이다.

---

## 입력 데이터

| 역할 | 파일 경로 |
|------|----------|
| Raw quantile series | `output/model_analysis/legacy/quantile_analysis/required_series/seed{s}/epoch{e}_required_series.csv` |
| 유역 특성 | `output/basin/drbc/analysis/basin_attributes/tables/drbc_selected_basin_analysis_table.csv` |
| Basin metrics (ID 추출용) | `output/model_analysis/legacy/overall_analysis/epoch_sensitivity/tables/basin_metrics.csv` |
| Obs 기반 특성 (CV, FDC slope 등) | 기존 `within_basin/tables/within_basin_rho_table.csv` 참조 가능 |

Primary epochs: 111→(m1:25, m2:5), 222→(m1:10, m2:10), 444→(m1:15, m2:10)
3 seed 중앙값 집계.

---

## 분석 차원 (5개)

### ① 유량 구간별 성능

**Q-bins (4개):**
| 구간 | 정의 | 의미 |
|------|------|------|
| Q0–Q50 | obs ≤ 50th percentile | 저유량 |
| Q50–Q90 | 50th < obs ≤ 90th percentile | 평상류 |
| Q90–Q99 | 90th < obs ≤ 99th percentile | 고유량 |
| Q99+ | obs > 99th percentile | 극한유량 |

Percentile은 유역별 test period obs 기준으로 계산.

**계산 지표:**
- M1 MAPE: `mean(|obs - model1| / obs) × 100` (%)
- M2 q50 MAPE: `mean(|obs - q50| / obs) × 100` (%)
- M1 Bias: `mean(model1 - obs) / mean(obs) × 100` (%)
- M2 q50 Bias: `mean(q50 - obs) / mean(obs) × 100` (%)
- M2 q90 Coverage: `mean(obs ≤ q90)` (이상적: 0.90)
- M2 q99 Coverage: `mean(obs ≤ q99)` (이상적: 0.99)
- M2 interval width ratio: `mean((q99 - q50) / obs)` per bin

### ② 고유량 계절 패턴

**계절 정의:**
- DJF: 12, 1, 2월
- MAM: 3, 4, 5월
- JJA: 6, 7, 8월
- SON: 9, 10, 11월

**계산 내용:**
- Q99+ 시간대의 계절별 발생 비율 (4계절 합산 = 100%)
- 계절별 M1 MAPE (모든 시간대 기준)
- 계절별 M1 Bias (%)

### ③ 사건 단위 첨두 오차

**홍수 사건 식별:**
- 임계값: 유역별 Q95 (test period obs 기준)
- 사건 시작: obs가 Q95 초과하는 첫 시각
- 사건 종료: obs가 Q95 이하로 돌아온 시각
- 사건 간 최소 분리: 24시간 (짧은 갭은 동일 사건으로 병합)
- 최소 지속 시간: 3시간

**사건별 지표:**
- `peak_ratio`: M1 예측 첨두 / obs 첨두 (1에 가까울수록 좋음)
- `timing_error`: obs 첨두 시각 - M1 첨두 시각 (시간, 양수 = M1이 늦음)
- `volume_error`: (M1 누적 - obs 누적) / obs 누적 × 100 (%)
- `season`: 첨두 발생 계절

**유역별 요약:**
- 총 사건 수
- 포착률: `peak_ratio ≥ 0.7`인 사건 비율 (%)
- 중앙값 peak_ratio
- 중앙값 timing_error (h)

### ④ 선행 조건 효과

**선행 조건 계산:**
- 각 사건 시작 직전 7일의 obs 평균 유량
- 유역별 모든 사건의 7일 평균 분포에서:
  - 건조 (dry): 하위 33%
  - 보통 (normal): 중간 33%
  - 습윤 (wet): 상위 33%

**계산 지표 (조건별):**
- M1 MAPE (%)
- M1 Bias (%)
- 사건 수 (각 조건에 해당하는 사건)

최소 3개 사건 이상인 조건만 계산, 미만이면 NaN.

### ⑤ 상승/하강 구간 비대칭

**구간 정의:**
- Rising limb: 사건 시작 ~ 첨두 시각 직전
- Falling limb: 첨두 시각 다음 ~ 사건 종료
- 최소 3 time step 이상인 구간만 계산

**계산 지표:**
- M1 Bias_rising: `mean(model1 - obs) / mean(obs) × 100` (%)
- M1 Bias_falling: 동일
- M2 q50 Bias_rising / Bias_falling

유역 단위 집계: 모든 사건의 rising/falling time step을 합산해서 계산.

---

## 리포트 카드 그림 레이아웃

### 유역별 8-패널 통합 그림

크기: 14 × 9 inches, 300 dpi
파일명: `report_cards/{basin_id}_report_card.png`

```
┌─────────────────┬──────────────────┬──────────────────┬──────────────────┐
│  P1: FDC        │  P2: 구간별 MAPE │  P3: 구간별 Bias │  P4: M2 구간폭   │
│  obs/M1/M2 q50  │  M1(파랑)        │  M1 vs M2 q50    │  width/obs ratio │
│  (log-log)      │  M2 q50(주황)    │  0-기준선 포함   │  + q90/q99 cover │
├─────────────────┼──────────────────┼──────────────────┼──────────────────┤
│  P5: 계절 패턴  │  P6: 사건 첨두   │  P7: 선행 조건   │  P8: 상승/하강   │
│  Q99+ 분포(막대)│  obs peak vs     │  dry/normal/wet  │  Rising vs       │
│  + 계절별 MAPE  │  peak_ratio(산점)│  M1 MAPE         │  Falling M1 Bias │
│  (이중 축)      │  계절 색상 코딩  │                  │  + M2 q50        │
└─────────────────┴──────────────────┴──────────────────┴──────────────────┘
```

그림 제목: `Basin {basin_id} — {basin_name}  (Area={area:.0f} km²  |  within_bias_ρ={rho:.3f})`

### 유역별 개별 패널 그림

크기: 5 × 4 inches, 150 dpi
파일명: `report_cards/panels/{basin_id}_p{1-8}_{name}.png`

### Cross-basin 요약 그림 (6개)

| 파일명 | 내용 | 크기 |
|--------|------|------|
| `heatmap_regime_Q0Q50.png` | 특성 × 성능 상관 (저유량) | 10×8 |
| `heatmap_regime_Q50Q90.png` | 특성 × 성능 상관 (평상류) | 10×8 |
| `heatmap_regime_Q90Q99.png` | 특성 × 성능 상관 (고유량) | 10×8 |
| `heatmap_regime_Q99plus.png` | 특성 × 성능 상관 (극한) | 10×8 |
| `event_capture_rate_ranking.png` | 38유역 포착률 수평 bar (면적 색상) | 8×10 |
| `antecedent_effect_distribution.png` | dry vs wet MAPE 차이 분포 | 6×5 |

Feature-regime heatmap: 20특성 × 4지표(M1 MAPE, M1 Bias, M2 q50 MAPE, M2 q99 coverage) Spearman ρ + BH FDR(α=0.05, 80쌍)

---

## 출력 구조

```
drbc_basin_report_cards/
├── tables/
│   ├── flow_regime_performance.csv       # 38 × 4bins × 지표 (seed 중앙값)
│   ├── seasonal_performance.csv          # 38 × 4seasons × 지표
│   ├── event_peak_errors.csv             # 사건별 peak_ratio / timing / volume / season
│   ├── event_summary_per_basin.csv       # 유역별 사건수, 포착률, 중앙값 ratio/timing
│   ├── antecedent_condition_perf.csv     # 38 × 3conditions × 지표
│   ├── rising_falling_bias.csv           # 38 × 2phases × 지표
│   └── feature_regime_correlations.csv  # 4bins × 20features × 4metrics (ρ + BH p)
│
├── figures/
│   ├── report_cards/
│   │   ├── {basin_id}_report_card.png   # 8-panel 통합 (38개)
│   │   └── panels/
│   │       ├── {basin_id}_p1_fdc.png
│   │       ├── {basin_id}_p2_regime_mape.png
│   │       ├── {basin_id}_p3_regime_bias.png
│   │       ├── {basin_id}_p4_m2_interval.png
│   │       ├── {basin_id}_p5_seasonal.png
│   │       ├── {basin_id}_p6_event_peak.png
│   │       ├── {basin_id}_p7_antecedent.png
│   │       └── {basin_id}_p8_rising_falling.png
│   │
│   └── cross_basin/
│       ├── heatmap_regime_Q0Q50.png
│       ├── heatmap_regime_Q50Q90.png
│       ├── heatmap_regime_Q90Q99.png
│       ├── heatmap_regime_Q99plus.png
│       ├── event_capture_rate_ranking.png
│       └── antecedent_effect_distribution.png
│
└── report/
    └── drbc_basin_report_cards_summary.md
```

---

## 코드 아키텍처

### 스크립트 1: `compute_drbc_basin_report_card_data.py`

```python
# dependencies: matplotlib, numpy, pandas, scipy, statsmodels

OFFICIAL_SEEDS = [111, 222, 444]
PRIMARY_EPOCHS = {111: {"model1": 25, "model2": 5},
                  222: {"model1": 10, "model2": 10},
                  444: {"model1": 15, "model2": 10}}
Q_BIN_LABELS = ["Q0-Q50", "Q50-Q90", "Q90-Q99", "Q99+"]
SEASONS = {"DJF": [12, 1, 2], "MAM": [3, 4, 5], "JJA": [6, 7, 8], "SON": [9, 10, 11]}

main()
├── _get_basin_ids()
├── load_series_seed_median()          # 3 seed 시리즈 로드 → 시간별 중앙값
├── compute_flow_regime_perf()
│   ├── _compute_q_bins()              # 유역별 Q-bin 경계값
│   └── _compute_metrics_in_bin()     # MAPE / Bias / coverage / width per bin
├── detect_flood_events()
│   └── _merge_short_gaps()           # 24h 미만 갭 병합
├── compute_event_peak_errors()        # 사건 테이블 생성
├── compute_event_summary()            # 유역별 요약
├── compute_seasonal_perf()
├── compute_antecedent_conditions()
│   └── _classify_antecedent()        # dry/normal/wet 분류
├── compute_rising_falling()
│   └── _split_event_at_peak()
├── compute_feature_regime_corr()
│   └── _bh_fdr()
└── write_all_tables()
```

### 스크립트 2: `plot_drbc_basin_report_cards.py`

```python
main()
├── load_tables()                       # 모든 CSV 로드
├── load_basin_metadata()              # 이름, 면적, within_bias_rho
├── for basin in basin_ids:
│   ├── _plot_p1_fdc()
│   ├── _plot_p2_regime_mape()
│   ├── _plot_p3_regime_bias()
│   ├── _plot_p4_m2_interval()
│   ├── _plot_p5_seasonal()
│   ├── _plot_p6_event_peak()
│   ├── _plot_p7_antecedent()
│   ├── _plot_p8_rising_falling()
│   └── _assemble_report_card()        # 8 axes → 14×9 figure
│
├── plot_regime_heatmaps()             # 4개 cross-basin heatmap
├── plot_event_capture_ranking()
└── plot_antecedent_effect_dist()
```

---

## 제약 및 주의사항

- **seed 집계 방식**: obs는 모든 seed에서 동일하므로 사건 식별(event detection)과 Q-bin 경계값은 1회만 계산. 모든 지표(MAPE, Bias, coverage 등)는 seed별로 각각 계산한 후 seed 중앙값(3 seed)으로 집계.
- Q-bin percentile은 test period (2014-01-01 ~ 2016-12-31) obs만 기준
- 사건 식별 시 obs NaN 시간대는 제외
- 사건 수가 10개 미만인 유역은 선행 조건 / 상승하강 분석에서 NaN 처리
- Feature-regime correlation: Q99+ bin에서 유역별 obs 시간 수 < 30이면 해당 유역의 Q99+ 지표를 NaN 처리 (cross-basin n=38에서 해당 유역 제외)
- MAPE 계산 시 obs ≤ 0인 시간대 제외 (0 division 방지)
