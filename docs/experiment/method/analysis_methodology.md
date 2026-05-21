# 실험 분석 방법론 (Experimental Analysis Methodology)

본 문서는 Multi-basin LSTM 기반 하천 유량 예측에서 **결정론적 모델(M1)과 확률론적 모델(M2)의 극한 홍수 첨두 과소추정 개선 효과**를 평가하기 위한 공식 분석 방법론이다. 최근 선행 연구(Baste et al., 2026) 및 심사 과정에서 제기된 학술적 한계를 보완하고, 본 연구의 독창성(Hourly 해상도, PUB/Regional holdout, 명확한 한계 제시)을 부각하도록 설계되었다.

---

## 1. 극한 이벤트(Extreme Event)의 이중 정의

수문학적 극한 이벤트의 정의는 목적에 따라 달라져야 하므로, 본 연구는 **분포 기반(Distribution-based)**과 **이벤트 기반(Event-based)** 두 가지 정의를 병행하여 사용한다.

### 1.1. 분포 기반 정의 (연속 시계열 평가용)
- **정의**: 테스트 기간 전체 관측 유량 분포 기준 **상위 X%**에 해당하는 타임스텝
- **구분**: Q50~Q75(보통), Q75~Q90(높음), Q90~Q95(홍수), Q95~Q99(극한), **Q99+(초극한)**, **Top 0.1%(최상위 극단)**
- **용도**: 모델 간 과소추정 비율 비교, Calibration 평가 (Baste et al.과 직접 비교 목적)

### 1.2. 이벤트 기반 정의 (POT; Peak-Over-Threshold)
- **정의**: 유역별 관측 유량이 **Q90을 초과**하여 지속되는 연속된 타임스텝의 군집
- **구분**:
  - **Rising Limb (상승부)**: 임계값 돌파 시점 ~ 관측 첨두 도달 시점
  - **Falling Limb (하강부)**: 관측 첨두 ~ 임계값 하회 시점
- **용도**: Timing vs Magnitude 오차 분해, Hit/Miss/False Alarm 탐지 능력 평가

---

## 2. 예측값 추출 기준

평가 목적에 따라 M1과 M2에서 추출하는 예측값이 다르다. 이 비대칭성을 평가의 목적으로 명확히 규정한다.

- **M1 (Deterministic)**: `Q_pred` (단일 점 추정치)
- **M2 (Probabilistic, Quantile)**: `F̂(q|x)` (예측 분포)
  - **점 예측 대리**: `Q50` (중앙값) → 평균 성능 비교용
  - **불확실성 상위 경계**: `Q90`, `Q95`, `Q99` → 극한 이벤트 포착 능력 평가용
  - **분포 전체**: CRPS 및 Pinball Loss → 전체 분포 품질 종합 평가용

---

## 3. 핵심 분석 5축 (Five Axes of Analysis)

### [축 1] 이벤트 강도별 조건부 성능 및 탐지 능력
극한 이벤트 강도에 따른 과소추정 개선도와 실무적 탐지 능력을 평가한다.

**A. 과소추정 비율 (Underestimation Ratio)**
- **지표**: 각 분위수 Tier별 `P(Q_pred < Q_obs)` (M1) vs `P(Q_obs > Q̂_0.99)` (M2)
- **목적**: "Top 0.1% 이벤트에서 M1은 X%를 놓치지만, M2는 상위 경계를 통해 Y% 방어함"을 입증

**B. Hit / Miss / False Alarm 평가**
- **정의**: 관측 유량이 임계값(Q95 등) 초과 시 홍수 발생으로 간주. M1은 `Q_pred > 임계값`, M2는 `Q̂_0.95 > 임계값`일 때 경보 발령으로 간주.
- **지표**: Hit Rate, False Alarm Rate, Critical Success Index (CSI)

### [축 2] 유역 특성별 조건부 성능 (Basin Attribute Stratification)
Output design 변경이 어느 물리적 조건에서 효과적인지 파악한다. (Baste et al. 심사 지적 보완)

- **지표**: 유역별 첨두 상대 오차(PRE) 개선폭 `Δ_PRE = PRE_M1 - PRE_M2(Q50)` 및 Coverage 개선폭
- **대상 속성**: `aridity` (건조도), `snow_frac` (적설 비율), `baseflow_index` (기저유량 비율)
- **목적**: M2의 성능 개선이 Rain-dominated/Flashy 유역에 집중되고, Snow-dominated 유역에서는 한계가 있음을 증명.

### [축 3] 신뢰도 및 Sharpness-Coverage 교환 (Calibration & Reliability)
M2가 출력하는 불확실성 구간이 통계적으로 유효한지 검증한다.

- **PIT Histogram**: 전체 유량 vs 극한 유량(Q95+) 분리 비교 (Heavy-tail 과소추정 확인)
- **Conditional Coverage Curve**: `Nominal Coverage(α)` 대비 실제 `Empirical Coverage` 비교
- **Sharpness vs Coverage**: 구간 너비(Q90-Q10)와 Coverage 간의 상충 관계(Trade-off)를 2D 플롯으로 시각화
- **CRPS vs Pinball Loss**: 점 추정(MSE/NSE)의 한계를 넘어선 공정 비교 지표 활용

### [축 4] 오차 원인 분해 (Timing vs Magnitude) 및 Limb 분석
Hourly 해상도의 장점을 살려 첨두 오차의 본질을 분석한다.

- **Magnitude Error**: `(Q_obs_peak - Q_pred_peak) / Q_obs_peak`
- **Timing Error**: `T_obs_peak - T_pred_peak` (시간 단위 측정)
- **목적**: M2의 Probabilistic head가 **크기(Magnitude) 오차는 줄이지만 타이밍(Timing) 오차는 줄이지 못함**을 증명. 이는 향후 Physics-guided hybrid 모델의 필요성으로 연결됨.
- **Limb 분석**: Rising Limb에서의 예측 성능(조기 탐지)과 Falling Limb의 감수 곡선 성능 비교.

### [축 5] 분포 외(OOD) 이벤트 및 Saturation 한계 분석
LSTM의 고질적 한계인 예측 포화(Saturation) 현상을 엄밀히 진단한다.

- **OOD 정의**: 훈련 기간 최대 유량(`Q_train_max`) 대비 이벤트 크기 비율 (예: `Q_obs > 1.5 * Q_train_max`)
- **분석**: OOD 이벤트에서 M2의 예측 구간 너비 확장 여부 및 Coverage 붕괴 여부 확인
- **목적**: M2 역시 훈련 데이터의 범위를 크게 벗어난 초극한 홍수에서는 Saturation이 발생한다는 한계를 논문에 명시적으로 서술하여 학술적 신뢰도 확보. DRBC Holdout (PUB) 환경에서의 스트레스 테스트를 통해 일반화 한계 제시.

---

## 4. 본 방법론의 학술적 강점
1. **Hourly + Regional Holdout 결합**: 기존 Daily + Temporal split 연구들의 한계를 극복.
2. **비대칭 비교의 정당화**: M1과 M2의 근본적 구조 차이를 인정하고, 목적(평균 vs 극한, 점 vs 분포)에 맞는 분리된 지표 적용.
3. **한계의 명시적 수용**: 축 4(타이밍 문제)와 축 5(OOD Saturation)를 통해 딥러닝 모델의 물리적 한계를 투명하게 공개, 후속 연구(Physics-guided)의 강력한 논거로 활용.
