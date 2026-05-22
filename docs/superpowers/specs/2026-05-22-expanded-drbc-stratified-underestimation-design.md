# Expanded DRBC Stratified Underestimation Analysis — Design Spec

**Date**: 2026-05-22
**Script**: `scripts/model/overall/analyze_expanded_drbc_stratified_underestimation.py`
**Status**: Design approved

---

## 목적

85-basin expanded DRBC test에서 관측 유량 분위수 기반 stratum별 과소추정 지표를 계산한다.
연구 목적(극한 홍수 첨두 과소추정 감소)을 directly 반영하는 방향성 있는 메트릭을
overall 분석에 추가한다. 논문 Table 1 직접 생성 목표.

---

## 입력

```
output/model_analysis/expanded/expanded_drbc_test/required_series/seed{111,222,444}/primary_required_series.csv
```

컬럼: `seed, basin, datetime, obs, model1, q50, q90, q95, q99`

- test period: 2014–2016 (약 17,520 시간스텝 / basin)
- 85 basins, seeds 111/222/444

---

## Stratum 정의

각 basin의 **test period 관측 유량(obs)** 분포에서 백분위수 계산.
모델 output quantile(q90/q95/q99)이 아님.

| Stratum | 조건 | 예상 시간스텝 / basin |
|---------|------|-----------------------|
| `all` | obs not NaN | ~17,520 |
| `obs_q90_plus` | obs > basin_Q90(obs) | ~1,752 (10%) |
| `obs_q95_plus` | obs > basin_Q95(obs) | ~876 (5%) |
| `obs_q99_plus` | obs > basin_Q99(obs) | ~175 (1%) |

Stratum은 **nested**: obs_q99_plus ⊂ obs_q95_plus ⊂ obs_q90_plus ⊂ all.
각 stratum은 독립적으로 집계 (누적이 아닌 초과 조건).

---

## 평가 컬럼

| 컬럼 | 의미 |
|------|------|
| `model1` | Model 1 결정론적 예측 |
| `q50` | Model 2 q50 (중앙 예측선) |
| `q90` | Model 2 q90 |
| `q95` | Model 2 q95 |
| `q99` | Model 2 q99 |

---

## 계산 메트릭

각 (stratum × pred_col × basin × seed) 조합:

```python
under_fraction = (pred < obs).mean()          # P(pred < obs)
rel_errors = (pred - obs) / obs               # 부호 있는 상대 오차
median_rel_bias = rel_errors.median()         # 중앙값 (음수 = 과소추정)
```

obs = 0인 행 제거 (division-by-zero 방지 + 저유량 노이즈 제거).
obs NaN 행 제거.

---

## 집계 순서

1. **Basin-level**: 각 (stratum × pred_col) → `under_fraction`, `median_rel_bias` per basin per seed
2. **Seed-level summary**: 85 basin median → (stratum × pred_col × seed) 요약
3. **Final summary**: 3 seed median → (stratum × pred_col) 최종 값

---

## 출력

### `tables/stratified_underestimation_summary.csv`
논문 Table 1 직접 사용. 행 = stratum, 열 = (pred_col × metric).

```
stratum, n_basins, n_timesteps_median,
model1_under_frac, model1_med_rel_bias,
q50_under_frac, q50_med_rel_bias,
q90_under_frac, q90_med_rel_bias,
q95_under_frac, q95_med_rel_bias,
q99_under_frac, q99_med_rel_bias
```

### `tables/stratified_underestimation_by_seed.csv`
Seed별 robustness 확인. 행 = (seed × stratum).

```
seed, stratum, n_basins,
model1_under_frac, model1_med_rel_bias, ...(같은 패턴)
```

---

## 해석 프레임

| Stratum | 기대 패턴 |
|---------|-----------|
| `all` | q50 ≈ model1 guardrail. q50 under_frac이 model1보다 높으면 q50 중앙선 악화 확인. |
| `obs_q90_plus` | q90이 model1보다 under_frac 낮아야 연구 claim 성립. |
| `obs_q95_plus` | q95가 under_frac 추가 감소. |
| `obs_q99_plus` | q99가 under_frac 최소화. Overprediction bias(med_rel_bias 양수)도 함께 확인. |

---

## 스크립트 구조

```
scripts/model/overall/analyze_expanded_drbc_stratified_underestimation.py

main()
├── load_required_series()        — 3 seed CSV 로드 및 concat
├── compute_basin_thresholds()    — basin별 Q90/Q95/Q99 of obs
├── assign_strata()               — 각 행에 stratum 플래그
├── compute_basin_metrics()       — (stratum × pred_col × basin × seed) → under_frac, med_rel_bias
├── aggregate_to_seed_summary()   — basin median → seed-level
├── aggregate_to_final_summary()  — seed median → final
└── write_outputs()               — 두 CSV 저장
```

의존성: numpy, pandas (matplotlib 불필요 — 이 스크립트는 table 전용).

---

## Legacy 삭제 (별도 진행)

- `output/model_analysis/legacy/` 전체 디렉터리
- legacy를 생성하는 38-basin 스크립트 목록 별도 확정 후 삭제

---

## 비고

- seed 333 제외 (Model 2 NaN loss 중단, paired comparison에서 제외 정책 유지)
- basin-specific 백분위수는 test period obs만 사용 (train period 포함 안 함)
- `n_timesteps_median`은 85 basin 중위 timestep 수 (stratum 희소성 확인용)
