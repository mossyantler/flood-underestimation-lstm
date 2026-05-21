# DRBC 유역 특성 × 모델 성능 상관관계 분석 설계

**날짜**: 2026-05-18  
**스크립트**: `scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py`  
**출력 루트**: `output/model_analysis/legacy/overall_analysis/main_comparison/drbc_attribute_metric_correlations/`

---

## 분석 목표

38개 DRBC 유역에 대해 20개 유역 특성과 24개 모델 성능 지표 간 Spearman 상관관계를 분석한다. Model 1(결정론적)과 Model 2(확률론적, q50 대표값 + quantile coverage) 모두 포함하며, 어떤 유역 특성이 모델 성능 차이를 설명하는지 파악하는 것이 목적이다.

---

## 입력 데이터

| 역할 | 파일 경로 |
|------|----------|
| 유역 특성 | `output/basin/drbc/analysis/basin_attributes/tables/drbc_selected_basin_analysis_table.csv` |
| 결정론적 지표 (절댓값) | `output/model_analysis/legacy/overall_analysis/epoch_sensitivity/tables/basin_metrics.csv` |
| Paired delta (M2−M1) | `output/model_analysis/legacy/overall_analysis/main_comparison/tables/primary_epoch_basin_deltas.csv` |
| Primary epoch 매핑 | `output/model_analysis/legacy/overall_analysis/main_comparison/tables/primary_epoch_summary.csv` |
| Raw quantile series | `output/model_analysis/legacy/quantile_analysis/required_series/seed{s}/epoch{e}_required_series.csv` |

Primary epoch 매핑으로 올바른 seed × epoch 조합만 로딩한다 (seed 111→epoch 25/5, 222→10/10, 444→15/10).  
공식 seeds: 111, 222, 444 (seed 333 제외).

---

## 유역 특성 (20개)

### CSV에서 직접 읽는 특성 (16개)

| # | 레이블 | 소스 컬럼 | 변환 |
|---|--------|----------|------|
| 1 | 유역 면적 | `drain_sqkm_attr` | — |
| 2 | 유역 면적 log | `drain_sqkm_attr` | log10 |
| 3 | Snow fraction | `frac_snow` | — |
| 4 | Seasonal | `p_seasonality` | — |
| 5 | 위도 | `lat_gage` | — |
| 6 | Elevation | `elev_mean_m` | — |
| 7 | Slope | `slope_pct` | — |
| 8 | Human use | `developed_frac` | — |
| 9 | Land use (forest) | `forest_frac` | — |
| 10 | Permeability | `soil_permeability_index` | — |
| 11 | Aridity | `aridity` | — |
| 12 | Baseflow index | `baseflow_index_pct` | — |
| 13 | 고강도 강수 빈도 | `high_prec_freq` | — |
| 14 | 토양 유효수분용량 | `soil_available_water_capacity` | — |
| 15 | Sand 비율 | `SANDAVE` | — |
| 16 | Clay 비율 | `CLAYAVE` | — |

### Raw series obs에서 계산하는 특성 (4개)

`obs`는 모든 seed에서 동일한 관측값이므로 seed 111 primary series 하나에서만 읽는다.

| # | 레이블 | 계산 방법 |
|---|--------|----------|
| 17 | 유량 변동성 (CV) | `std(obs) / mean(obs)` per basin |
| 18 | FDC 기울기 | `log10(Q10_obs / Q90_obs)` per basin |
| 19 | Q99 절대값 | `np.percentile(obs, 99)` per basin |
| 20 | 평균 유량 | `mean(obs)` per basin |

---

## 성능 지표 (24개)

### 결정론적 지표 (15개)

분석 단위: seed × basin. 집계 단위: 3 seed 중앙값 → basin 38개.

| 그룹 | 지표 |
|------|------|
| Model 1 절댓값 (5) | NSE, KGE, FHV, Peak-Timing, Peak-MAPE |
| Model 2 q50 절댓값 (5) | NSE, KGE, FHV, Peak-Timing, Peak-MAPE |
| Paired delta M2−M1 (5) | ΔNSE, ΔKGE, ΔFHV, ΔPeak-Timing, ΔPeak-MAPE |

### 확률론적 지표 (9개, Model 2 전용)

Raw series에서 유역별로 직접 계산 후 seed 중앙값 집계.

| 그룹 | 지표 | 설명 |
|------|------|------|
| Pinball all-hour (4) | `pinball_q50/q90/q95/q99` | `mean(pinball_loss(obs, q_tau, tau))` per basin |
| Coverage all-hour (4) | `coverage_q50/q90/q95/q99` | `mean(obs <= q_tau)` per basin |
| Tail hit rate (1) | `tail_hit_q99` | Q99-exceedance 시간대 `mean(obs <= q99)` |

---

## 통계 분석

- **방법**: Spearman 순위 상관 (n=38 basins)
- **검정**: 각 (특성, 지표) 쌍 양측 p-value
- **다중 비교 보정**: Benjamini–Hochberg FDR (α=0.05), 480 쌍 내에서 적용
- **유의성 플래그**: BH-adjusted p < 0.05

---

## 출력 구조

```
drbc_attribute_metric_correlations/
├── tables/
│   ├── basin_feature_metric_table.csv          # 38 basins × (20특성 + 24지표) master table
│   ├── spearman_correlations.csv               # 480쌍 ρ, p-value, BH p, significant 플래그
│   ├── top_correlations.csv                    # |ρ| 상위 N쌍 (기본 top_n=20)
│   └── computed_obs_features.csv              # obs 계산 특성 중간 산출물
├── figures/
│   ├── heatmap_model1.png                      # M1 지표 × 20특성
│   ├── heatmap_model2_q50.png                  # M2 q50 지표 × 20특성
│   ├── heatmap_model2_prob.png                 # 확률론적 지표 × 20특성
│   ├── heatmap_delta.png                       # Paired delta × 20특성
│   └── scatter/{metric}_{feature}_scatter.png  # BH-significant 쌍만 생성
├── metadata/
│   └── analysis_metadata.json
└── report/
    └── drbc_attribute_metric_correlation_report.md
```

### 마크다운 리포트 구성

1. 분석 개요 (특성 수, 지표 수, 유역 수, seeds)
2. Top 상관 쌍 표 (|ρ| ≥ 0.4 기준)
3. 지표 그룹별 주요 발견 (결정론적 / 확률론적)
4. Heatmap 그림 삽입
5. 주의사항 (n=38 소표본, 독립성 가정 한계)

---

## 코드 아키텍처

```
main()
├── parse_args()
├── load_basin_features()
│   └── add_log10_area()
├── load_deterministic_metrics()
│   └── filter_primary_epochs()
├── compute_obs_features()
│   ├── load_primary_series()
│   └── aggregate_seed_median()
├── compute_probabilistic_metrics()
│   ├── pinball_loss(obs, pred, tau)
│   └── tail_hit_rate(obs, q99_pred)
├── build_master_table()
├── run_spearman_correlations()
│   └── bh_fdr_correction()
├── write_tables()
├── write_heatmaps()        # 4개 heatmap
├── write_scatters()        # BH-significant 쌍만
├── write_report()
└── write_metadata()
```

### 의존성

```
# /// script
# dependencies = [
#   "matplotlib>=3.8",
#   "numpy>=1.26",
#   "pandas>=2.2",
#   "scipy>=1.13",
#   "statsmodels>=0.14",
# ]
# ///
```

### CLI

```bash
uv run scripts/model/overall/analyze_drbc_basin_attribute_metric_correlations.py \
  --seeds 111 222 444 \
  --top-n 20 \
  --fdr-alpha 0.05
```

---

## 제약 및 주의사항

- n=38로 소표본이므로 Spearman ρ의 신뢰구간이 넓다. 유의미한 상관도 해석 시 주의.
- 3 seed × 38 basin = 114행이지만 seed 간 독립성이 완전하지 않으므로, **주 결론은 seed 중앙값 집계(n=38) 기준**으로 제시한다.
- Pinball 값은 유량 단위(m³/s)에 비례하므로 절대값 직접 비교보다 특성과의 상관 방향에 집중한다.
- Q99-exceedance tail hit rate는 formal calibration이 아닌 조건부 hit rate로 해석한다.
