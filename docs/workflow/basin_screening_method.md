# Basin Screening Method

## 서술 목적

이 문서는 basin screening 방법을 `논문 본문용 규범`으로 정리한다. 핵심은 `DRBC를 regional holdout evaluation region으로 두고`, `학습용 basin pool`과 `DRBC 평가 cohort`를 분리해서 설명하는 것이다. 즉 이 문서가 다루는 screening은 Delaware regional model을 만들기 위한 과정이 아니라, `global multi-basin model`의 평가 cohort를 구성하기 위한 과정이다. 정적 heuristic은 공식 screening method로 쓰지 않고, DRBC 평가 cohort에 대해서만 `공간 선택 -> 품질 필터 -> observed-flow 기반 flood relevance 판정 -> hydromodification에 따른 cohort 분리`의 네 단계를 공식 screening으로 둔다.

## 다루는 범위

- basin screening의 공식 단계와 수식
- quality gate와 observed-flow 기반 flood relevance 판정 원칙
- broad / natural cohort 분리 규칙

## 다루지 않는 범위

- 현재 통과 basin 수와 산출물 inventory
- source CSV의 세부 컬럼 설명
- event table 자체의 생성 규칙

## 상세 서술

이 문서에서 말하는 screening의 목적은 “어떤 basin이 모델 비교에 적합한가”를 정하는 것이지, 지도 위 모든 basin의 flood susceptibility를 새로 정의하는 것이 아니다. 현재 저장소의 정적 커스텀 점수도 공식 screening의 일부가 아니라 exploratory prioritization 도구로만 쓴다.

현재 통과 basin 수나 생성된 테이블 같은 상태 정보는 [`basin_analysis.md`](basin_analysis.md), source CSV와 컬럼 사전은 [`basin_source_csv_guide.md`](basin_source_csv_guide.md)를 본다.

## 1. 전체 실험 구조

현재 basin 관련 실험 구조는 두 층으로 나뉜다.

첫째, `global training pool`이다. 이건 outlet가 DRBC 밖에 있고 polygon overlap은 `0.1` 이하까지 허용한 tolerant non-DRBC CAMELSH basin 중 quality gate를 통과한 basin 집합이다. 모델 backbone 학습은 이 basin pool에서 수행한다.

둘째, `DRBC holdout evaluation cohort`다. 이건 DRBC 내부 basin 중 flood-focused 평가와 해석에 사용할 basin 집합이다. 이 문서의 공식 screening은 이 두 번째 집합을 어떻게 정할 것인지에 관한 것이다.

즉 training pool은 `공간적으로 DRBC를 피하고 품질을 만족하는 basin을 넓게 확보`하는 데 목적이 있고, DRBC screening은 `observed high-flow relevance가 높은 basin을 평가 cohort로 고르는 데` 목적이 있다. 여기서 평가 cohort는 global model의 regional performance를 보기 위한 것이지, 별도의 regional model 학습 집합이 아니다.

## 2. 전체 구조

최종적으로 사용할 screening 파이프라인은 아래 네 단계다.

1. `DRBC + CAMELSH overlap/outlet 기준 basin 선택`
2. `usable years, estimated-flow fraction, boundary confidence 기반 품질 필터`
3. `annual peaks, Q99 frequency, RBI 같은 observed-flow metric 기반 flood-relevant basin 선정`
4. `hydromod risk 여부에 따라 broad / natural cohort 분리`

이 구조를 쓰는 이유는 단순하다. 연구권역을 고정하고, 데이터 품질을 보장하고, 실제 flood-like response를 확인한 뒤, anthropogenic disturbance를 분리해 보기 위해서다.

## 3. Step 1: DRBC + CAMELSH 기반 basin 선택

### 2.1 연구권역 정의

연구권역은 Delaware River Basin Commission의 공식 경계 polygon으로 정의한다. basin screening의 출발점은 이 DRBC polygon과 CAMELSH basin set의 공간 관계를 계산하는 것이다.

### 2.2 공간 선택 규칙

CAMELSH basin \(i\)가 연구권역 후보에 들어오려면 두 조건을 동시에 만족해야 한다.

첫째, basin outlet point가 DRBC polygon 내부에 있어야 한다.

$$
O_i =
\mathbf{1}\!\left(
\mathrm{covers}\!\left(\Omega_{\mathrm{DRBC}},\; p_i\right)
\right)
$$

여기서 \(\Omega_{\mathrm{DRBC}}\)는 DRBC polygon이고, \(p_i\)는 basin \(i\)의 gauge outlet point다.

둘째, basin polygon의 대부분이 DRBC 내부에 있어야 한다. 이를 위해 basin overlap ratio를

$$
r_i = \frac{
\mathrm{Area}\!\left(B_i \cap \Omega_{\mathrm{DRBC}}\right)
}{
\mathrm{Area}\!\left(B_i\right)
}
$$

로 정의한다. 여기서 \(B_i\)는 basin \(i\)의 polygon이다.

현재 선택 기준은

$$
O_i = 1
\quad \text{and} \quad
r_i \ge 0.9
$$

이다.

### 2.3 왜 outlet와 overlap을 같이 쓰는가

outlet 기준만 쓰면 basin polygon의 상당 부분이 연구권역 밖으로 나가도 basin이 포함될 수 있다. 반대로 polygon overlap만 쓰면 outlet가 연구권역 밖인데도 일부가 겹친다는 이유만으로 basin이 포함될 수 있다. 우리는 basin을 실제 연구권역에 속한 `gauged basin`으로 해석하고 싶기 때문에, outlet를 주 anchor로 두고 overlap ratio를 quality control criterion으로 같이 사용한다.

즉 이 단계의 목적은 “DRBC를 대표하는 CAMELSH basin 후보를 고르는 것”이다.

## 4. Step 2: 품질 필터

### 3.1 왜 flood relevance보다 품질을 먼저 보는가

모델 비교 연구에서는 basin의 flood 성향보다 먼저 “이 basin에서 나온 결과를 믿을 수 있는가”가 중요하다. 관측이 짧거나, estimated flow 비율이 높거나, basin boundary가 불확실하면 성능 차이를 hydrologic behavior로 해석하기 어렵다.

그래서 flood-relevant basin을 고르기 전에 먼저 basin quality gate를 적용한다.

### 3.2 usable year의 정의

연도에 값이 1시간만 있어도 “관측연도 1년”으로 세면 자료 품질을 과대평가하게 된다. 따라서 우리는 `usable year`를 사용한다.

각 basin \(i\), 연도 \(y\)에 대해 annual coverage를

$$
C_{i,y} = \frac{H^{\mathrm{obs}}_{i,y}}{H^{\mathrm{tot}}_y}
$$

로 정의한다. 여기서 \(H^{\mathrm{obs}}_{i,y}\)는 그 해의 observed hourly record 수이고, \(H^{\mathrm{tot}}_y\)는 그 해의 총 시간 수다.

그다음 usable year indicator를

$$
U_{i,y} =
\begin{cases}
1, & C_{i,y} \ge \tau_c \\
0, & C_{i,y} < \tau_c
\end{cases}
$$

로 정의한다. 현재 기본값은

$$
\tau_c = 0.8
$$

이다.

최종 usable year 수는

$$
Y_i^{\mathrm{usable}} = \sum_y U_{i,y}
$$

로 계산한다.

### 3.3 품질 게이트 수식

현재 basin \(i\)는 아래 세 조건을 모두 만족할 때만 quality-pass basin으로 본다.

첫째, usable year 수가 충분해야 한다.

$$
Y_i^{\mathrm{usable}} \ge \tau_y
$$

현재는

$$
\tau_y = 10
$$

이다.

둘째, estimated flow 비율이 너무 높지 않아야 한다.

$$
E_i \le \tau_e
$$

여기서 \(E_i\)는 `FLOW_PCT_EST_VALUES`이고, 현재

$$
\tau_e = 15\%
$$

이다.

셋째, basin boundary confidence가 충분히 높아야 한다.

$$
B_i \ge \tau_b
$$

여기서 \(B_i\)는 `BASIN_BOUNDARY_CONFIDENCE`이고, 현재

$$
\tau_b = 7
$$

이다.

따라서 basin \(i\)의 quality-pass indicator는

$$
Q_i =
\mathbf{1}\!\left(Y_i^{\mathrm{usable}} \ge \tau_y\right)
\cdot
\mathbf{1}\!\left(E_i \le \tau_e\right)
\cdot
\mathbf{1}\!\left(B_i \ge \tau_b\right)
$$

로 쓸 수 있다.

### 3.4 boundary confidence를 왜 쓰는가

유역 경계 polygon이 있다고 해서 그 basin boundary가 항상 신뢰할 만하다는 뜻은 아니다. GAGES-II 기반 `BASIN_BOUNDARY_CONFIDENCE`는 basin area와 NWIS drainage area의 일치도, HUC10과의 정합성, gauge 위치와 basin boundary 및 하천망의 관계를 바탕으로 매겨진 QA 지표다.

즉 우리는 “polygon이 있는 basin”이 아니라 “경계 품질이 충분한 basin”만 남긴다. 이는 model input basin과 observed discharge target의 공간 일관성에 중요하다.

## 5. Step 3: Observed-flow 기반 flood-relevant basin 선정

### 4.1 왜 정적 heuristic보다 observed-flow가 중심이어야 하는가

정적 basin 특성은 basin이 왜 빠르게 반응할 가능성이 있는지 설명해 주지만, 큰 flood-like event가 실제로 자주 나타나는지는 직접 보여주지 않는다. 예를 들어 slope가 크고 storage가 작아도 annual peaks가 작고 high-flow frequency가 낮으면, 우리 연구에서는 우선순위가 낮아질 수 있다.

따라서 최종 flood-relevant basin 선정은 observed-flow metric을 중심으로 해야 한다.

### 4.2 사용할 핵심 지표

최종 screening에서는 아래 세 가지 observed-flow 지표를 핵심으로 쓴다.

첫째는 `annual peak specific discharge`다. basin 면적이 다르기 때문에 연 최대 유량을 basin area로 나눠 비교한다.

$$
q_{i,y}^{\mathrm{peak}} = \frac{Q_{i,y}^{\max}}{A_i}
$$

여기서 \(Q_{i,y}^{\max}\)는 basin \(i\)의 연도 \(y\) 최대 유량이고, \(A_i\)는 basin area다.

둘째는 `Q99 event frequency`다. usable year당 Q99-level high-flow event가 얼마나 자주 나타나는지 본다.

$$
F_i^{99} = \frac{N_i^{99}}{Y_i^{\mathrm{usable}}}
$$

여기서 \(N_i^{99}\)는 basin \(i\)에서 Q99 threshold를 초과한 독립 event의 개수다.

셋째는 `Richards–Baker Flashiness Index (RBI)`다.

$$
\mathrm{RBI}_i =
\frac{
\sum_{t=1}^{T-1} \left|Q_{i,t+1}-Q_{i,t}\right|
}{
\sum_{t=1}^{T} Q_{i,t}
}
$$

이 값이 클수록 hydrograph가 더 급격하게 변하는 flashy basin으로 해석한다.

필요하면 `annual peak representative value`로 median, mean, upper quantile 중 하나를 선택하고, event 분리를 위해 최소 inter-event separation 조건을 함께 둘 수 있다. 하지만 핵심 논리는 바뀌지 않는다. 최종 ranking은 `peak magnitude`, `extreme-flow frequency`, `flashiness`를 중심으로 해야 한다.

### 4.3 event sufficiency gate

observed-flow metric도 sample이 충분해야 의미가 있다. 따라서 flood relevance를 판정하기 전, annual peak와 extreme-flow event sample이 너무 적은 basin은 제외한다.

권장 gate는

$$
P_i =
\mathbf{1}\!\left(Y_i^{\mathrm{peak}} \ge 10\right)
\cdot
\mathbf{1}\!\left(N_i^{99} \ge 5\right)
$$

처럼 둘 수 있다. 여기서 \(Y_i^{\mathrm{peak}}\)는 annual peak를 계산할 수 있는 usable year 수다.

즉 basin \(i\)는 quality gate뿐 아니라 event sufficiency gate도 통과해야 최종 flood relevance 평가 대상이 된다.

### 4.4 observed-flow score

최종 observed-flow score는 rank 기반으로 간단하게 구성할 수 있다.

$$
\begin{aligned}
S_i^{\mathrm{obs}} =\;&
w_1\,R_i^{\uparrow}\!\left(\widetilde{q_i^{\mathrm{peak}}}\right)
\\
&+ w_2\,R_i^{\uparrow}\!\left(F_i^{99}\right)
\\
&+ w_3\,R_i^{\uparrow}\!\left(\mathrm{RBI}_i\right)
\end{aligned}
$$

여기서 \(\widetilde{q_i^{\mathrm{peak}}}\)는 basin \(i\)의 representative annual peak specific discharge이고, \(w_1+w_2+w_3=1\)이다.

이때 중요한 점은 exact weight 자체보다 `최종 basin 선정에서 observed-flow가 중심`이라는 사실이다. 가중치는 연구 목적에 따라 조정할 수 있지만, flood relevance를 설명하는 주 신호가 annual peaks, Q99 frequency, flashiness라는 점이 더 중요하다.

### 4.5 왜 이 세 지표를 쓰는가

`annual peaks`는 가장 전통적인 flood frequency 분석의 출발점이다. 미국에서는 Bulletin 17C가 annual peak series를 기반으로 flood frequency를 추정하는 대표 기준이다. 따라서 annual peak specific discharge를 basin screening에 쓰는 것은 매우 표준적이다.

`Q99 frequency`는 extreme high-flow가 실제로 얼마나 자주 나타나는지를 보여준다. 이는 단순히 peak가 한 번 컸는지보다, basin이 반복적으로 extreme response를 보이는지를 판단하는 데 유용하다.

`RBI`는 hydrograph의 급격한 변화를 정량화한다. 우리 연구가 peak underestimation과 빠른 flood response에 관심이 있기 때문에, flashiness는 매우 직접적인 relevance metric이다.

### 4.6 재현기간별 강수량과 홍수량 reference descriptor

Observed-flow screening의 핵심 점수는 여전히 `annual peak specific discharge`, `Q99 event frequency`, `RBI`를 중심으로 둔다. 다만 basin 해석과 event response table의 맥락 설명을 강화하기 위해, 재현기간별 강수량과 홍수량을 `reference descriptor`로 추가한다.

이 descriptor는 공식 모델 성능 metric도 아니고, Model 2의 `q99`와 직접 비교하는 target도 아니다. 역할은 각 basin의 extreme rainfall forcing scale과 observed flood magnitude scale을 설명하는 것이다.

권장 return period set은 아래처럼 둔다.

```text
T = 2, 5, 10, 25, 50, 100 years
```

강수 쪽은 duration별 precipitation frequency estimate를 둔다. 문서와 산출물에서는 `P100` 대신 `prec_ari100_24h`처럼 `prec_ari{T}_{duration}` 형식을 권장한다. 예를 들어 duration \(d\)에 대해 \(P_{i,T}^{(d)}\)를 basin \(i\)의 \(T\)-year precipitation depth로 정의하되, 컬럼명은 아래처럼 둔다.

```text
prec_ari2_1h, prec_ari5_1h, ..., prec_ari100_1h
prec_ari2_6h, prec_ari5_6h, ..., prec_ari100_6h
prec_ari2_24h, prec_ari5_24h, ..., prec_ari100_24h
prec_ari2_72h, prec_ari5_72h, ..., prec_ari100_72h
```

이 duration set은 event response table의 forcing window와 맞춘다. `1h`는 peak 직전 최대 hourly rainfall intensity proxy와 연결하고, `6h`, `24h`, `72h`는 각각 `recent_rain_6h`, `recent_rain_24h`, `recent_rain_72h`와 직접 비교한다. 따라서 `24h`는 대표 예시일 뿐 단독 기준이 아니며, hourly flood response 해석에서는 네 duration을 함께 둔다.

장기적으로 공식 참고값은 NOAA Atlas 14 / PFDS의 precipitation frequency estimates를 사용하는 것이 가장 좋다. basin-level 값은 구현 단계에서 outlet point, basin centroid, 또는 gridded estimate의 area-weighted average 중 하나로 고정해야 한다. 다만 현재 서버 all-basin 구현은 CAMELSH hourly forcing에서 duration별 rolling precipitation annual maximum을 뽑아 Gumbel 분포를 맞춘 proxy를 우선 생성한다. 따라서 현재 산출물은 공식 NOAA frequency product가 아니라 `prec_ari_source`와 함께 해석하는 내부 reference다.

유량 쪽은 annual maximum streamflow series 기반 flood-frequency estimate를 둔다. 문서와 산출물에서는 `Q100` 대신 `flood_ari100`처럼 `flood_ari{T}` 형식을 권장한다. basin \(i\)의 water year \(y\)에서 annual maximum hourly streamflow를

$$
M_{i,y} = \max_{t \in y} Q_{i,t}
$$

로 두고, return period \(T\)에 대응하는 flood magnitude를 \(F^{\mathrm{flood}}_{i,T}\)로 기록한다.

가능하면 USGS annual peak record와 Bulletin 17C / PeakFQ / StreamStats 계열 결과를 우선 reference로 사용한다. CAMELSH hourly streamflow에서 직접 계산할 경우에는 `hourly annual maximum based flood_ari reference estimate` 또는 `proxy`로 명시한다. 특히 100년 값은 관측 record length보다 긴 tail extrapolation이 될 수 있으므로, record length와 confidence flag를 함께 둔다.

이 descriptor를 event table과 결합하면 event별 상대 규모도 계산할 수 있다.

$$
\mathrm{peak\_to\_flood\_ari100}_{e,i}
=
\frac{Q^{\mathrm{peak}}_{e,i}}{F^{\mathrm{flood}}_{i,100}}
$$

$$
\mathrm{rain24h\_to\_prec\_ari100\_24h}_{e,i}
=
\frac{P^{(24h)}_{e,i}}{P^{(24h)}_{i,100}}
$$

이 값들은 event가 해당 basin의 참고 극한 규모에 비해 어느 정도였는지 설명하는 데 쓴다. 단, `100-year rainfall event`가 곧 `100-year flood event`를 만든다고 해석하면 안 된다. antecedent wetness, snowmelt, storage, hydromodification, basin shape가 rainfall-runoff 변환을 바꾸기 때문이다.

## 6. Step 4: broad / natural cohort 분리

final observed-flow screening 이후에는 hydromodification risk를 기준으로 cohort를 두 개로 나눈다.

먼저 broad cohort는 flood-relevant basins 전체를 포괄하는 집합이다.

$$
\mathcal{C}^{\mathrm{broad}} =
\left\{
i \;\middle|\; Q_i = 1,\; P_i = 1,\; \operatorname{rank}(S_i^{\mathrm{obs}}) \le K_b
\right\}
$$

여기서 \(K_b\)는 broad cohort 크기다.

그다음 natural cohort는 hydromodification risk가 없는 basin만 따로 뽑은 집합이다.

$$
\mathcal{C}^{\mathrm{natural}} =
\left\{
i \;\middle|\; Q_i = 1,\; P_i = 1,\; H_i = 0,\; \operatorname{rank}(S_i^{\mathrm{obs}} \mid H_i = 0) \le K_n
\right\}
$$

여기서 \(H_i\)는 hydromod risk indicator다.

이렇게 두 cohort를 나누는 이유는, 하나는 현실적인 전체 basin 환경에서의 모델 성능을 보고, 다른 하나는 anthropogenic disturbance가 적은 basin에서 모델 구조 차이를 더 깨끗하게 보기 위해서다.

## 7. 구현 연결

현재 저장소에서는 DRBC + CAMELSH basin 선택, DRBC holdout 쪽 품질 필터, exploratory static prioritization, 그리고 non-DRBC training pool quality filtering까지 일부 결과가 준비되어 있다. 산출물의 현재 상태와 파일 inventory는 [`basin_analysis.md`](basin_analysis.md)를 본다.

중요한 점은 구현 진척 자체보다 `논문 본문에서 어떤 screening logic을 공식으로 채택할 것인가`다. 따라서 이미 계산된 static score는 supplementary 또는 exploratory priority level로만 다루고, 본문의 공식 screening은 여전히 이 문서의 네 단계를 기준으로 설명한다.

## 8. 외부 문헌과 현재 방법의 관계

이 문서에서 exact formula가 외부에서 그대로 온 것은 아니다. basin selection의 outlet + overlap 조건, usable year threshold, quality gate threshold, 그리고 broad / natural cohort 크기 같은 것은 현재 연구 설계에서 정한 기준이다.

반대로 아래 요소들은 외부 문헌과 표준 practice에 기대고 있다.

- basin behavior를 climate, topography, hydrology, land cover, soil, geology로 설명하는 large-sample framework는 Addor et al. (2017)의 CAMELS 데이터셋 설명과 정합적이다.
- annual peak series를 이용한 flood frequency 접근은 Bulletin 17C의 전통적 framework와 정합적이다.
- 재현기간별 precipitation frequency estimate는 NOAA Atlas 14 / PFDS를 공식 참고값으로 사용한다.
- event runoff coefficient와 storm response를 event rainfall, basin storage, antecedent condition과 연결해 해석하는 접근은 Merz and Blöschl (2009)와 정합적이다.
- flashiness를 정량화하는 데 RBI를 사용하는 것은 실제 hourly streamflow classification에 이를 사용한 HESS 2023 연구와 정합적이다.

즉 현재 방법론은 `문헌에서 검증된 hydrologic metric`을 중심으로 하고, `cohort construction logic`은 우리 연구 목적에 맞게 설계한 구조라고 설명하는 것이 가장 정확하다.

## 9. 참고 문헌과 링크

- Addor, N., Newman, A. J., Mizukami, N., and Clark, M. P. (2017): The CAMELS data set: catchment attributes and meteorology for large-sample studies, HESS, 21, 5293–5313. [https://hess.copernicus.org/articles/21/5293/2017/hess-21-5293-2017.html](https://hess.copernicus.org/articles/21/5293/2017/hess-21-5293-2017.html)
- NOAA Atlas 14 / Precipitation Frequency Data Server: precipitation frequency estimates by duration and average recurrence interval. [https://hdsc.nws.noaa.gov/pfds/](https://hdsc.nws.noaa.gov/pfds/)
- Merz, R. and Blöschl, G. (2009): A regional analysis of event runoff coefficients with respect to climate and catchment characteristics in Austria, Water Resources Research, 45, W01405. [https://www.waterresources.at/fileadmin/user_uploads/Publications/Merz_and_Bloeschl_WRR_2009.pdf](https://www.waterresources.at/fileadmin/user_uploads/Publications/Merz_and_Bloeschl_WRR_2009.pdf)
- England, J. F. Jr. et al. (2019): Guidelines for determining flood flow frequency — Bulletin 17C, U.S. Geological Survey. [https://www.usgs.gov/publications/guidelines-determining-flood-flow-frequency-bulletin-17c](https://www.usgs.gov/publications/guidelines-determining-flood-flow-frequency-bulletin-17c)
- Stein, E. D. et al. (2023): Advancing stream classification and hydrologic modeling of ungaged basins for environmental flow management in coastal southern California, HESS, 27, 3021–3047. [https://hess.copernicus.org/articles/27/3021/2023/hess-27-3021-2023.html](https://hess.copernicus.org/articles/27/3021/2023/hess-27-3021-2023.html)

## 문서 정리

이 문서는 논문 본문에서 사용할 공식 basin screening 규범을 묶는다. exploratory static score는 보조 우선순위 도구로만 두고, 본문에서는 공간 선택, 품질 게이트, observed-flow relevance, cohort 분리의 네 단계를 기준으로 설명하는 것이 맞다.

최종 cohort 선정의 중심은 observed-flow 지표다. 현재 구현 상태나 임시 테이블보다, 본문에서 어떤 screening logic을 공식으로 채택할지가 이 문서의 핵심이다. 다만 모델 학습은 DRBC 내부가 아니라 non-DRBC training pool에서 수행한다는 점을 같이 기억해야 한다.

## 관련 문서

- basin subset과 공간 anchor는 [`basin_cohort_definition.md`](basin_cohort_definition.md)에서 정리한다.
- 현재 산출물 상태와 provisional screening 결과는 [`basin_analysis.md`](basin_analysis.md)에서 다룬다.
- source CSV와 정적 컬럼 사전은 [`basin_source_csv_guide.md`](basin_source_csv_guide.md)에서 다룬다.
- event-level observed-flow 입력 규칙은 [`event_response_spec.md`](event_response_spec.md)에서 다룬다.
