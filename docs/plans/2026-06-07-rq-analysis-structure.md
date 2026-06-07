# RQ 분석 구조 확정 (2026-06-07)

이 문서는 RQ-1/2/3 정의와 하위 분석 목록을 고정한다.
분석 설계 변경 시 `.omc/plans/rq-analysis-structure.md`와 함께 갱신한다.

---

## 브랜치 네이밍 확정

| 코드 | 새 이름 | 내용 | 행 수 | 역할 |
|------|--------|------|-------|------|
| branchB2 | **AllRain** | 전체 강우 사건 (2014-2016 test 기간) | 16,639건 | RF 훈련 데이터 |
| branchB | **NOAA** | NWS 확인 홍수 사건 | 57건 | overlay 평가 |
| branchA | **Q99** | Q99 초과 사건 | 926건 | 불필요 — 문서에서 제외 |

---

## RQ-1 — Model 1 vs Model 2 q50 base 성능 비교

**질문:** Model 2 q50이 Model 1 대비 중앙 예측 성능을 유지하는가?
RQ-2 진입 전제 확립 (q50 ≈ M1).

| 하위 | 분석 내용 |
|------|----------|
| 1a. 6-metric 비교 | NSE/KGE/Bias/MAE/RMSE/FHV (basin-median delta) |
| 1b. per-basin boxplot | 분포 전반 이질성 확인 |

핵심 수치: NSE +0.149, RMSE −0.273, MAE −0.197

---

## RQ-2 — Model 2 출력 심층 분석

**질문:** Model 2의 4-quantile 출력(q50/q90/q95/q99)은 어떻게 생겼는가?
입력-출력 상관 구조는? 유량 체제·강우 유형·실제 홍수 상황에서 출력 패턴이 어떻게 달라지는가?

> 각 하위 분석은 Model 2 출력 자체를 기술(describe)한다.
> τ 진행이 과소추정을 줄이는지에 대한 모델 평가는 RQ-3에서 다룬다.

| 하위 | 분석 내용 |
|------|----------|
| **2a. 각 quantile 출력 특성** | τ별 α/β/δ 기술. 단일 τ 점 추정 진단. |
| **2b. 입력-출력 상관 (SHAP)** | 정적 vs 동적 기여도, area×soil_depth 게이트, slope 극한 반전, 강우 유형 신호 (CRainf_frac, CAPE) |
| **2c. 밴드 형태 및 gap 구조** | q50~q99 밴드 폭·꼬리·위치, gap trajectory (q95→q99 과소간격 수렴 + 과대간격 등장) |
| **2d. 보정 및 예리도** | 전 τ 경험적 포함률 vs 공칭값, Pinball 손실, climatology 대비 skill score |
| **2e. 실제 홍수 사건 출력** | NOAA 확인 홍수 65건 21유역 출력 관찰, 홍수 유형별 패턴 (Flash Flood vs Flood) |
| **2f. 강우 유형별 출력 패턴** | SHAP의 CRainf_frac·CAPE 강우 유형 구분법 차용, 대류성 vs 전선성 사건에서 τ 출력 분포·α 패턴 신규 분석 (SHAP 결과 미사용) |

---

## RQ-3 — obs_class 해석 방법론 + 모델 평가

**질문:** Model 2 출력을 해석하는 obs_class 틀은 무엇이고,
그 틀로 Model 2가 Model 1 대비 과소추정을 실제로 줄이는가?

> 모델 평가 단위 = predicted obs_class (RF 분류기) vs actual obs_class
> predicted < actual → 과소추정 / predicted > actual → 과대추정
> 기존 FAR/over-pred → FN rate / FP rate 혼동행렬로 대체

| 하위 | 분석 내용 |
|------|----------|
| **3a. obs_class 틀 정의** | 관측 위치 구간 0–4 서수 정의, Q99/NOAA 사건 실제 분포 확인 |
| **3b. 독립 신호 분류** | 신호 3분류 (I: 독립 / C: 밴드결합 / L: 누수), 3-scope Spearman r (Q99/NOAA/전체강우) |
| **3c. area 사분위 층화 분포** | area Q1~Q4별 above_q99 비율 단조 증가 (Q1 20% → Q4 65%) |
| **3d. RF obs_class 분류기 훈련** | S1 features → predicted obs_class, AllRain Basin GroupKFold + Event StratifiedKFold upper bound, S1 vs S1+S2(band) ablation |
| **3e. 모델 평가 — predicted vs actual** | predicted vs actual obs_class 혼동행렬. FN rate = 과소추정, FP rate = 과대추정/false alarm. M1 NSE tier별 분포 포함. |
| **3f. NOAA overlay 검증** | AllRain으로 훈련 → NOAA 완전 held-out 유역 평가 (basin intersection = 0) |

---

## 논리 흐름

```
RQ-1 (전제: q50 ≈ M1)
  → RQ-2 (Model 2 출력이 어떻게 생겼는가)
      → RQ-3 (obs_class로 해석 → RF로 추정 → M1 대비 평가)
```

| 역할 | RQ |
|------|-----|
| base 성능 비교 (전제) | RQ-1 |
| Model 2 출력 특성 (중심) | RQ-2 |
| obs_class 해석 + 모델 평가 (기여 + 결론) | RQ-3 |
