# LSTM 개선형 Hydrology 논문 조사와 Study Method

이 문서는 연구자 관점의 정리 문서다. 용어와 문맥이 아직 낯설다면 먼저 [lstm_hydrology_study_notes_beginner.md](./lstm_hydrology_study_notes_beginner.md)를 읽고 오는 편이 훨씬 수월하다.

## 이 문서의 목적

이 문서는 `LSTM 개선형 hydrology` 문헌을 프로젝트 관점에서 다시 읽기 위한 작업 메모다. 단순히 “어떤 모델이 좋았다”를 적는 문서가 아니라, 각 논문이 실제로 어떤 가정 위에 서 있는지, basin data를 어떻게 만들고 다뤘는지, basin을 어떻게 조사하고 층화했는지, large-sample 혹은 big-data 조건을 어떻게 처리했는지를 정리한다.

여기서 말하는 “모두 조사”는 현실적으로 완전한 전수 목록이라기보다, `2018–2025` 사이에 형성된 대표적인 LSTM 계열 수문 문헌을 가능한 넓게 훑고, 현재 CAMELS 프로젝트와 직접 연결되는 논문군을 우선 깊게 읽는 방식으로 해석한다. 특히 `multi-basin rainfall–runoff`, `PUB/PUR`, `probabilistic/uncertainty`, `physics-guided / hybrid`, `flood forecasting`, `training data curation` 축을 중심으로 정리한다.

## 먼저 결론

문헌을 한 줄로 요약하면 이렇다. 최근 hydrology의 LSTM 개선은 단순히 hidden size를 키우는 방향이 아니라, `학습 단위(local -> multi-basin)`, `입력 설계(single forcing -> multi-forcing / multi-timescale / lagged observation)`, `출력 설계(point -> probabilistic)`, `구조 설계(unconstrained -> mass-conserving / routing-aware / hybrid)`, `데이터 설계(random basin pool -> hydrologically diverse training pool)`로 이동해 왔다.

현재 CAMELS 프로젝트에 가장 직접적으로 중요한 메시지는 다섯 가지다.

1. `single-basin`보다 `multi-basin`이 거의 항상 강하다. 이유는 basin diversity 자체가 regularization 역할을 하고, rare flood와 snow/groundwater regime을 더 많이 보게 해 주기 때문이다.
2. basin의 “가까움”보다 hydrologic diversity가 더 중요할 수 있다. 지역적으로 먼 basin이 오히려 일반화를 더 잘 돕는다는 결과가 반복된다.
3. lumped basin-average 입력은 여전히 강력한 baseline이지만, 큰 basin이나 pseudo-ungauged 조건에서는 spatial heterogeneity 손실이 분명한 약점이다.
4. flood나 extreme를 제대로 다루려면 point prediction만으로는 부족하다. probabilistic head, uncertainty calibration, event-specific metric이 필요하다.
5. physics-guided 구조는 무조건 이득이 아니다. 잘 설계하면 timing/interpretability/large-basin routing에 도움이 되지만, 나쁘게 설계하면 오히려 LSTM이 physics error를 떠안게 된다.

## 문헌 지도

### 1. Baseline, multi-basin, regionalization

| 문헌 | 무엇을 바꿨나 | 핵심 가정 | basin/data 처리 | 우리 프로젝트 함의 |
|---|---|---|---|---|
| [Kratzert et al., 2018, *Rainfall–runoff modelling using Long Short-Term Memory (LSTM) networks*](https://hess.copernicus.org/articles/22/6005/2018/) | local LSTM보다 regional LSTM을 명확한 baseline으로 제시 | 서로 다른 basin 사이에도 공유 가능한 hydrologic regularity가 있다 | CAMELS 기반 multi-basin 실험, 지역 학습과 basin별 학습을 직접 비교 | Model 1 baseline은 single-basin이 아니라 multi-basin이어야 한다 |
| [Kratzert et al., 2019, *Towards learning universal, regional, and local hydrological behaviors via machine learning applied to large-sample datasets*](https://hess.copernicus.org/articles/23/5089/2019/) | `EA-LSTM`으로 static attributes를 gate 수준에서 반영 | 정적 basin attribute는 basin identity를 요약하는 유효한 descriptor다 | CAMELS large-sample, dynamic forcing와 static attributes를 분리해서 사용 | static attribute 선택이 단순 부가정보가 아니라 basin generalization의 핵심이다 |
| [Kratzert et al., 2019, *Toward improved predictions in ungauged basins: Exploiting the power of machine learning*](https://doi.org/10.1029/2019WR026065) | LSTM을 PUB 문제에 직접 적용 | ungauged basin도 nearby/similar catchment parameter transfer보다 data-driven regional learning이 더 낫다 | meteorological forcing + physical descriptors를 함께 사용 | DRBC holdout 같은 regional holdout 설계의 정당화에 바로 연결된다 |
| [Lees et al., 2021, *Benchmarking data-driven rainfall–runoff models in Great Britain: a comparison of long short-term memory (LSTM)-based models with four lumped conceptual models*](https://hess.copernicus.org/articles/25/5517/2021/) | CAMELS-GB에서 LSTM과 개념모형을 공정 비교 | LSTM 평가는 반드시 strong hydrology benchmark와 함께 해야 한다 | 669개 GB catchment, daily large-sample benchmark | 우리도 deterministic baseline 비교를 단순 internal ablation로 끝내지 말고 hydrology convention 안에서 읽어야 한다 |
| [Arsenault et al., 2023, *Continuous streamflow prediction in ungauged basins: long short-term memory neural networks clearly outperform traditional hydrological models*](https://hess.copernicus.org/articles/27/139/2023/) | leave-one-out regionalization에서 LSTM과 전통 regionalization을 직접 비교 | PUB에서는 “유사 basin 선택”보다 region-wide representation이 더 강할 수 있다 | 북동부 북미 148 catchment, leave-one-out CV, pseudo-ungauged 평가 | DRBC regional holdout을 설계할 때 basin transfer보다 broad pool 학습이 낫다는 근거가 된다 |
| [Kratzert et al., 2024, *HESS Opinions: Never train an LSTM on a single basin*](https://doi.org/10.5194/hess-2023-275) | 의견 논문이지만 기준점을 재정의 | LSTM의 장점은 sequence model 그 자체보다 large-sample learning에서 나온다 | single-basin 설정을 비판하고 multi-basin을 기본값으로 둠 | CAMELS 프로젝트의 baseline 철학과 거의 일치한다 |

### 2. 입력 설계, 시간 해상도, 상태 회복

| 문헌 | 무엇을 바꿨나 | 핵심 가정 | basin/data 처리 | 우리 프로젝트 함의 |
|---|---|---|---|---|
| [Gauch et al., 2021, *Rainfall-Runoff Prediction at Multiple Timescales with a Single Long Short-Term Memory Network*](https://arxiv.org/abs/2010.07921) | daily와 hourly 같은 여러 time scale을 한 모델에서 다룸 | 다른 시간 해상도의 정보가 상호 보완적이다 | multi-timescale sequence 구성과 별도 prediction head 사용 | CAMELSH hourly를 기본으로 두되, daily aggregation ablation을 분리할 근거가 된다 |
| [Nearing et al., 2021, *A note on leveraging synergy in multiple meteorological data sets with deep learning for rainfall–runoff modeling*](https://hess.copernicus.org/articles/25/2685/2021/) | 여러 forcing product를 동시에 입력 | forcing uncertainty는 ensemble로만 처리할 필요가 없고, LSTM이 제품 간 차이를 학습해 결합할 수 있다 | CAMELS 531 basin, Daymet/Maurer/NLDAS의 5개 forcing variable을 모두 사용, CONUS-wide normalization, 325/531 basin에서 Maurer의 1일 lag 가능성을 별도 점검 | forcing product 차이와 calendar shift 같은 전처리 문제를 모델 성능 문제와 분리해서 봐야 한다 |
| [Feng et al., 2020, *Enhancing streamflow forecast and extracting insights using long-short term memory networks with data integration at continental scales*](https://doi.org/10.1029/2019WR026793) | 관측 자료를 LSTM에 통합하는 data integration | state recovery에 직접 도움이 되는 관측을 넣으면 forecast skill이 오른다 | continental-scale data integration 실험 | lagged Q를 baseline과 분리해야 하는 이유를 설명해 준다 |
| [Modi et al., 2025, *Improving streamflow simulation through machine learning-powered data integration and its potential for forecasting in the Western U.S.*](https://hess.copernicus.org/articles/29/5453/2025/) | lagged Q와 lagged SWE를 시차별로 통합 | LSTM은 이미 일부 state를 내부적으로 추론하지만, 직접 관측은 특정 regime에서 추가 이득을 줄 수 있다 | Western U.S.에서 snow-dominated / rain-dominated basin을 분리해 평가, 일/월 단위 모두 분석 | snow basin, spring-melt basin, rain basin을 나눠서 평가해야 한다는 점이 중요하다 |

### 3. Probabilistic, uncertainty, extreme-event readout

| 문헌 | 무엇을 바꿨나 | 핵심 가정 | basin/data 처리 | 우리 프로젝트 함의 |
|---|---|---|---|---|
| [Klotz et al., 2022, *Uncertainty estimation with deep learning for rainfall–runoff modeling*](https://hess.copernicus.org/articles/26/1673/2022/) | point prediction 위에 uncertainty benchmark를 도입 | actionable hydrologic prediction에는 calibrated uncertainty가 필수다 | CAMELS benchmark 위에서 `MC Dropout`, `GMM`, `CMAL`, `UMAL` 비교 | Model 2는 단순 quantile 하나가 아니라 calibration까지 평가해야 설득력이 생긴다 |
| [Frame et al., preprint, *Deep learning rainfall-runoff predictions of extreme events*](https://hess.copernicus.org/preprints/hess-2021-423/hess-2021-423-ATC1.pdf) | extreme-event holdout과 high-flow 성능 자체를 전면화 | 평균적인 skill과 extreme skill은 다르게 측정해야 한다 | extreme를 학습에서 일부 제외한 뒤 high-flow 재현성 평가 | 현재 프로젝트의 `extreme-event holdout` 설계와 직접 닿아 있다 |
| [Nevo et al., 2022, *Flood forecasting with machine learning models in an operational framework*](https://hess.copernicus.org/articles/26/4013/2022/) | 연구용이 아니라 실제 operational flood warning 시스템에 LSTM을 탑재 | flood forecasting은 정확도만 아니라 실시간성, lead time, alerting pipeline까지 포함한다 | 대규모 운영 시스템에서 LSTM 기반 stage forecasting 사용, 인도/방글라데시 등 대규모 서비스 범위를 다룸 | 논문용 평가와 운영형 forecast는 metric, latency, data validation 체계가 달라진다는 점을 상기시킨다 |

### 4. Physics-guided, constrained, hybrid, interpretability

| 문헌 | 무엇을 바꿨나 | 핵심 가정 | basin/data 처리 | 우리 프로젝트 함의 |
|---|---|---|---|---|
| [Hoedt et al., 2021, *MC-LSTM: Mass-Conserving LSTM*](https://arxiv.org/abs/2101.05186) | LSTM cell 자체에 mass conservation을 심음 | 유량 예측 문제의 일부는 수지 제약을 구조에 심어서 줄일 수 있다 | `mass input`과 `auxiliary input`을 분리하며, mass input과 target은 일반 normalization에서 제외 | future-work conceptual core를 설계한다면 “입력/출력에만 물리 해석을 붙이는 것”보다 state-update 구조를 건드리는 방식이 더 낫다는 시사점을 준다 |
| [Lees et al., 2022, *Hydrological concept formation inside LSTM networks*](https://hess.copernicus.org/articles/26/3079/2022/) | 내부 state가 실제 hydrologic storage를 닮는지 probe로 검사 | LSTM이 잘 맞는 이유가 단순 black-box fitting이 아니라 learned hydrologic memory일 수 있다 | 669 CAMELS-GB basin, 1년 길이 daily sequence, ERA5-Land soil moisture와 snow depth를 probe target으로 사용, snow 분석은 강설 비율 5% 이상 basin으로 제한 | basin subgroup을 만든 뒤 해석해야 한다는 점, 그리고 hidden state 해석을 통해 snow/soil memory를 점검할 수 있다는 점이 중요하다 |
| [Wang and Karimi, 2022, *Impact of spatial distribution information of rainfall in runoff simulation using deep learning method*](https://doi.org/10.5194/hess-26-2387-2022) | 강수의 공간 분포 자체를 입력 설계의 문제로 제기 | lumped rainfall average가 basin response를 충분히 설명하지 못할 수 있다 | rainfall spatial distribution 정보의 유효성을 비교 | 큰 유역이나 공간적으로 이질적인 유역에서는 lumped forcing이 약점일 수 있다 |
| [Pokharel et al., 2023, *Effects of mass balance, energy balance, and storage-discharge constraints on LSTM for streamflow prediction*](https://doi.org/10.1016/j.envsoft.2023.105730) | 여러 물리 제약을 LSTM에 체계적으로 부착 | constraint는 종류별로 효과가 다르고, 성능과 해석 가능성의 trade-off가 있다 | constraint 유형별 비교 실험 | future-work conceptual core에서 어떤 물리 제약을 먼저 넣을지 우선순위를 세울 때 참고할 만하다 |
| [Yu et al., 2024, *Enhancing long short-term memory (LSTM)-based streamflow prediction with a spatially distributed approach*](https://hess.copernicus.org/articles/28/2107/2024/) | lumped LSTM 뒤에 routing-aware spatial recursion을 붙임 | basin-average 입력만으로는 large basin과 pseudo-ungauged basin에서 정보 손실이 크다 | Great Lakes 141 training basin, 224 gauged station 평가, subbasin scale local prediction 후 routing | DRBC처럼 basin size와 내부 heterogeneity가 다양한 영역에서는 routing-aware hybrid가 특히 의미 있다 |
| [Xiang et al., 2025, *An explainable deep learning model based on hydrological principles for flood simulation and forecasting*](https://hess.copernicus.org/articles/29/7217/2025/) | XAJ runoff-generation layer와 LSTM을 결합 | flood simulation에서는 peak magnitude와 timing을 위해 conceptual core가 직접 도움이 될 수 있다 | 중국 2개 basin의 event-scale flood simulation, PRE와 peak timing difference를 강조 | multi-basin 대규모 benchmark는 아니지만, flood-specific hybrid 설계 감각을 제공한다 |

### 5. Training data curation, dataset scaling, hydrologic diversity

| 문헌 | 무엇을 바꿨나 | 핵심 가정 | basin/data 처리 | 우리 프로젝트 함의 |
|---|---|---|---|---|
| [Gauch et al., 2021, *The proper care and feeding of CAMELS: How limited training data affects streamflow prediction*](https://doi.org/10.1016/j.envsoft.2020.104926) | “데이터를 얼마나 오래, 얼마나 많이 줘야 하는가”를 정면으로 다룸 | LSTM은 short record에서 급격히 약해지고, 더 긴 기간과 더 많은 basin에서 이득을 본다 | training record length와 basin count 효과를 비교 | quality-pass basin을 넓게 확보하는 현재 전략이 맞다는 근거다 |
| [Snieder and Khan, 2025, *A diversity-centric strategy for the selection of spatio-temporal training data for LSTM-based streamflow forecasting*](https://hess.copernicus.org/articles/29/785/2025/) | training data selection을 hydrologic diversity 관점으로 재정의 | 비슷한 basin을 더 모으는 것보다, 다른 basin을 섞는 것이 더 유익할 수 있다 | cluster-based undersampling, basin clustering, random forest feature importance, temporal/spatial diversity 분리 평가 | non-DRBC training pool을 “가깝다”보다 “hydrologically diverse하다” 기준으로 보는 게 더 낫다 |
| [Addor et al., 2017, *The CAMELS data set: catchment attributes and meteorology for large-sample studies*](https://hess.copernicus.org/articles/21/5293/2017/) | large-sample hydrology의 표준 입력 틀 제공 | basin behavior 비교에는 static attribute와 forcing을 같이 표준화해 둔 데이터셋이 필요하다 | CAMELS-US의 정적 속성, forcing, discharge 체계화 | 현재 attribute 설계와 basin screening의 출발점이다 |
| [Coxon et al., 2020, *CAMELS-GB: hydrometeorological time series and landscape attributes for 671 catchments in Great Britain*](https://essd.copernicus.org/articles/12/2459/2020/) | 지역 확장형 CAMELS 계열 | basin generalization 연구는 여러 나라의 CAMELS-like dataset에서 재검증되어야 한다 | 671개 GB catchment의 time series + landscape attributes | basin attribute를 단일 국가 포맷에 묶지 말고 portable하게 관리해야 한다 |
| [Kratzert et al., 2023, *Caravan – A global community dataset for large-sample hydrology*](https://doi.org/10.1038/s41597-023-01975-w) | 글로벌 large-sample hydrology 데이터셋 | big-data learning의 병목은 모델보다 데이터 통합 표준화일 수 있다 | 여러 국가/대륙의 CAMELS-like dataset을 공통 형식으로 정리 | 후속 연구에서 DRBC 바깥 generalization 범위를 넓히기 좋은 기반이다 |

## 문헌들이 반복해서 따르는 가정

### 1. Shared hydrology 가정

multi-basin LSTM 논문 대부분은 basin마다 다른 물리 파라미터가 존재하더라도, `강수-기온-증발산-정적 지형 속성 -> 유출` 사이에는 basin 간에 공유 가능한 표현이 있다고 가정한다. 이 가정이 깨지면 regional LSTM은 성립하지 않는다. Kratzert 계열 논문과 Arsenault 2023은 이 shared representation이 실제로 강하다는 쪽에 가깝다.

### 2. Static attributes 가정

EA-LSTM 이후 문헌은 static attributes를 단순 보조 feature가 아니라 `basin identity encoder`로 본다. 면적, 고도, 경사, aridity, soil, geology, land cover, snow index 같은 변수는 basin별 기억용량과 response speed를 설명하는 proxy다. 다만 이 가정은 `attribute 품질`에 크게 의존한다.

### 3. Lumped approximation 가정

대부분의 large-sample LSTM 문헌은 gridded forcing을 basin polygon 안에서 평균내어 lumped 입력을 만든다. 이건 계산량과 reproducibility 면에서 좋지만, spatial storm heterogeneity, subbasin routing, 큰 유역 내부의 눈/비 혼합 같은 정보는 잃는다. Yu 2024와 Wang and Karimi 2022는 바로 이 가정의 약점을 찌른다.

### 4. More diverse data is better 가정

Kratzert 2018/2019, Gauch 2021, Snieder and Khan 2025를 같이 보면, “내 basin과 비슷한 basin만 모아야 한다”는 직관은 항상 맞지 않는다. 오히려 hydrologically dissimilar basin이 representation을 더 안정적으로 만들어 줄 수 있다.

### 5. Point prediction은 extreme를 충분히 설명하지 못한다는 가정

uncertainty와 extreme-event 문헌은 평균제곱오차나 NSE 중심 학습이 tail을 누를 수 있다고 본다. 따라서 flood peak를 보려면 calibration, quantile, mixture density, event metric이 필요하다는 방향으로 이동한다.

### 6. Physics guidance는 설계 품질에 따라 약이 되기도 하고 독이 되기도 한다는 가정

MC-LSTM, constraint LSTM, routing-aware hybrid, XAJ-LSTM 계열은 모두 “physics를 더하면 좋아질 수 있다”는 가정을 갖는다. 하지만 최근 하이브리드 문헌들을 같이 읽어보면, physics가 실제 상태 업데이트를 개선하지 못하면 LSTM이 오히려 physics bias를 보정하느라 부담이 커질 수 있다. 그래서 물리 제약의 종류와 위치가 중요하다.

## basin data를 실제로 어떻게 처리하는가

### 1. Dynamic forcing

대부분의 논문은 `precipitation`, `temperature`, `PET`를 기본 축으로 둔다. CAMELS 계열에서는 여기에 `shortwave radiation`, `vapor pressure`까지 자주 포함된다. multi-forcing 논문은 Daymet, Maurer, NLDAS처럼 동일 물리량의 여러 product를 병렬 입력으로 넣는다.

실무적으로 중요한 부분은 forcing 품질 차이를 그냥 모델이 해결할 것이라고 넘기지 않는다는 점이다. Nearing 2021은 Maurer와 Daymet 사이 1일 정렬 문제를 basin별 lag-correlation으로 직접 점검했다. 이건 지금 CAMELSH hourly forcing에서도 그대로 따라야 할 태도다.

### 2. Static attributes

static은 보통 다음 계열로 묶인다.

- 지형: area, elevation, slope, drainage density
- 기후: aridity, fraction of snow, seasonality
- 토양/지질: soil depth, porosity, permeability
- 식생/토지피복: forest fraction, NDVI proxy, land cover class
- 수문학적 요약자: baseflow index, runoff ratio, FDC slope

중요한 점은 static을 많이 넣는 것보다 `일관된 출처와 품질`이 더 중요하다는 것이다. CAMELS/CAMELS-GB/Caravan 논문은 이 점에서 dataset engineering 자체를 연구 기반으로 취급한다.

### 3. Normalization

large-sample LSTM 문헌은 basin별 표준화보다 `전체 basin 공통 평균/표준편차`를 자주 쓴다. 그래야 model이 basin 간 scale 차이를 직접 배우고, unseen basin에도 같은 transform을 적용할 수 있기 때문이다.

다만 mass-conserving 계열은 예외가 있다. MC-LSTM처럼 mass input을 명시적으로 저장하는 구조는 `mass input`과 `target discharge`를 일반적인 z-score normalization에서 빼는 편이 많다. 물수지 구조를 보존해야 하기 때문이다.

### 4. Sequence length와 spin-up

daily 문헌은 365일 길이 sequence를 자주 쓴다. hourly 문헌은 더 긴 memory와 storage recovery를 위해 더 긴 sequence가 필요할 가능성이 크다. multi-timescale 논문은 같은 basin에서도 time scale별 sequence 구성이 별도라는 점을 분명히 보여 준다.

### 5. Split

대부분의 논문이 아래 셋 중 하나 또는 둘을 택한다.

1. temporal split
2. basin holdout 혹은 leave-one-out regionalization
3. pseudo-ungauged evaluation

우리 프로젝트는 여기에 `extreme-event holdout`을 추가하려고 하는데, 이건 기존 문헌의 blind spot을 메우는 방향이다.

### 6. Quality control

dataset 논문은 기본 QC를 제공하지만, 실제 LSTM 논문은 그 위에 연구 목적별 필터를 더 얹는다. 예를 들어 snow process를 볼 때는 snow-affected basin만 따로 보고, large-basin routing 문제를 볼 때는 일정 면적 이상의 basin만 따로 본다. 즉 basin subset을 연구 질문에 맞게 재구성하는 게 일반적이다.

## basin을 어떻게 조사하고 분석하는가

### 1. basin을 먼저 지도 위에서 고정하고, 그다음 속성과 응답을 본다

대부분의 좋은 논문은 basin cohort를 공간적으로 먼저 정의하고, 그 위에 static attribute와 observed flow behavior를 얹는다. basin을 “데이터 row”가 아니라 “공간 단위의 hydrologic entity”로 취급하는 셈이다.

### 2. basin subgroup을 나눠서 본다

문헌에서 자주 쓰는 basin stratification은 다음과 같다.

- snow-dominated vs rain-dominated
- large basin vs small basin
- gauged vs pseudo-ungauged
- hydrologically similar vs dissimilar cluster
- 훈련에 포함된 basin vs 완전 holdout basin

Modi 2025는 SWE data integration 효과를 snow/rain basin으로 나눠 보고, Yu 2024는 large basin과 pseudo-ungauged basin에서 spatial hybrid 효과가 더 크다는 점을 본다. 이건 우리도 DRBC basin을 `snow influence`, `baseflow influence`, `basin size`, `human modification`으로 층화해 봐야 한다는 뜻이다.

### 3. observed flow metric으로 basin relevance를 판단한다

최근 flood 논문들은 static attribute만으로 flood-prone basin을 정의하지 않는다. annual peak, peak timing, rising limb, high-flow bias, event error를 함께 본다. 이건 현재 저장소의 `screening -> event-level table -> flood-prone cohort` 방향과 일치한다.

### 4. hidden state도 조사 대상이 된다

Lees 2022는 basin별 hydrograph만 보는 데서 멈추지 않고, LSTM cell state와 ERA5-Land soil moisture / snow depth를 연결해 “모델이 무엇을 기억하는가”를 본다. 즉 basin 조사는 입력 테이블만 보는 게 아니라, 학습된 state representation까지 확장될 수 있다.

## big-data를 다루는 방법

### 1. basin 수를 늘리는 것과 basin 다양성을 늘리는 것을 구분한다

문헌의 최신 흐름은 단순히 basin을 많이 모으는 것에서 끝나지 않는다. Snieder and Khan 2025는 clustering을 이용해 temporal diversity와 spatial diversity를 따로 정의했고, 비슷한 basin을 더 모으는 것보다 다른 basin을 섞는 편이 유익할 수 있음을 보였다.

따라서 training pool은 “DRBC와 멀리 떨어진 basin을 포함하는가”보다 “snow, aridity, response speed, storage regime의 다양성이 충분한가”를 봐야 한다.

### 2. raw gridded data를 무조건 lumped average로 끝내지 않는다

lumped average는 편하지만, 큰 basin이나 storm heterogeneity가 큰 지역에서는 정보 손실이 크다. spatial rainfall 분포를 직접 반영하거나, subbasin routing을 따로 두는 하이브리드가 최근에 늘고 있다. 이건 hourly flood 연구일수록 더 중요해진다.

### 3. product ensemble 대신 learned fusion을 쓴다

기존 hydrology는 forcing product마다 separate run을 돌려 ensemble average를 내는 경우가 많았지만, LSTM 문헌은 여러 forcing product를 동시에 넣고 `모델이 스스로 조합하게` 만드는 쪽으로 이동한다. Nearing 2021이 대표적이다.

### 4. training data를 줄일 때도 무작정 random subsampling을 하지 않는다

big-data cost를 줄일 때 random subsampling은 hydrologic diversity를 깨뜨릴 수 있다. Snieder and Khan 2025는 cluster-based undersampling으로 temporal redundancy를 줄였고, 절반 수준으로 줄여도 성능 손실이 크지 않을 수 있음을 보였다.

### 5. ensemble과 seed variance를 별도 관리한다

uncertainty 논문과 operational 논문은 prediction uncertainty와 seed randomness를 섞어 보지 않는다. benchmark용 seed ensemble, probabilistic head의 aleatoric uncertainty, forcing product 차이에 따른 input uncertainty를 분리해서 다룬다.

## CAMELS 프로젝트에 바로 적용할 Study Method

### Step 1. 문헌 읽기 순서를 먼저 고정한다

다음 순서로 읽는 게 가장 효율적이다.

1. `Kratzert 2018 -> Kratzert 2019 -> Arsenault 2023 -> HESS Opinion 2024`
2. `Nearing 2021 -> Gauch 2021 multi-timescale -> Klotz 2022`
3. `Lees 2022 -> MC-LSTM 2021 -> Yu 2024 -> Xiang 2025`
4. `Snieder and Khan 2025 -> Caravan 2023`

이 순서는 baseline, data design, uncertainty, hybrid, data curation 순으로 논리를 쌓기 좋다.

### Step 2. basin 조사와 model 설계를 분리한다

문헌을 보면 좋은 연구일수록 basin screening이 모델 튜닝의 부산물이 아니다. 먼저 공간적 basin cohort를 정의하고, 그다음 품질 필터, 그다음 observed-flow 기반 flood relevance를 붙인다. 현재 저장소의 `DRBC holdout + non-DRBC training pool` 전략은 이 원칙에 맞는다.

### Step 3. training pool은 proximity가 아니라 diversity로 본다

학습용 basin은 `DRBC 밖`이라는 공간 규칙만으로는 부족하다. snow fraction, aridity, elevation, slope, baseflow index, seasonality, runoff ratio, event flashiness 같은 지표로 training pool의 다양성을 확인해야 한다. 이건 Snieder and Khan 2025의 핵심 메시지와 맞닿는다.

### Step 4. Model 1에서 절대 섞지 말아야 할 것들을 분리한다

Model 1에서는 `lagged Q`, `physics-guided core`, `spatial routing hybrid`, `probabilistic head`를 한 번에 넣지 않는 편이 좋다. baseline이 흔들리면 나중에 개선 원인을 분리할 수 없다. baseline은 wide multi-basin deterministic LSTM으로 두고, 입력도 forcing + static까지만 유지하는 게 좋다.

### Step 5. Model 2는 단순히 loss만 바꾸는 게 아니라 evaluation도 바꿔야 한다

quantile이나 mixture-density head를 넣는 순간 평가도 바뀌어야 한다. NSE만 보고 끝내면 probabilistic head의 장점이 사라진다. pinball loss, coverage, calibration, high-flow quantile reliability를 같이 봐야 한다.

### Step 6. Physics-guided conceptual core는 future work로 둔다

문헌을 종합하면, naive dynamic-parameter hybrid는 해석과 안정성에서 곤란해질 가능성이 높다. 따라서 현재 논문은 `Model 1 vs Model 2` 비교에 집중하고, conceptual core는 `snow storage`, `soil storage`, `fast runoff`, `slow/baseflow`, `routing storage` 같은 최소 상태를 두는 bounded future-work 방향으로만 남겨 두는 편이 안전하다.

### Step 7. basin subgroup 평가를 기본값으로 둔다

최종 표와 그림은 전체 median만 보여 주면 부족하다. 최소한 다음 subgroup을 같이 봐야 한다.

- snow-influenced basin vs rain-dominated basin
- high-baseflow basin vs flashy basin
- small basin vs large basin
- DRBC interior core basin vs boundary-near basin
- natural basin vs modified basin

이 subgroup 평가는 현재 논문의 `Model 1 vs Model 2` 차이를 해석하는 데도 중요하고, 나중에 conceptual core를 붙일 경우 어느 subgroup에서 후속 이득을 기대할지 정리하는 데도 도움이 된다.

### Step 8. event-level table을 논문의 중심 분석 단위로 끌어올린다

현재 저장소의 다음 단계가 `forcing/streamflow 품질 정보 + event-level 지표`를 DRBC holdout에 붙이는 일인데, 문헌을 보면 이게 맞다. flood 연구에서 basin 평균 score만으로는 peak underestimation을 설명할 수 없다. event table이 있어야 peak magnitude, timing, rise/fall asymmetry를 따로 볼 수 있다.

## 지금 당장 추적 가치가 높은 추가 문헌

아래 논문들은 이번 메모에서 핵심 문헌처럼 깊게 요약하지는 않았지만, reference network를 따라가다 보면 현재 프로젝트와 직접 연결될 가능성이 높다.

- [De la Fuente et al., 2024, *Toward interpretable LSTM-based modeling of hydrological systems*](https://doi.org/10.5194/hess-28-945-2024)
- [Xie et al., 2021, *Physics-guided deep learning for rainfall-runoff modeling by considering extreme events and monotonic relationships*](https://doi.org/10.1016/j.jhydrol.2021.127043)
- [Yang et al., 2020, *A physical process and machine learning combined hydrological model for daily streamflow simulations of large watersheds with limited observation data*](https://doi.org/10.1016/j.jhydrol.2020.125206)
- [Cui et al., 2021, *A novel hybrid XAJ-LSTM model for multi-step-ahead flood forecasting*](https://doi.org/10.2166/nh.2021.016)
- [Alizadeh et al., 2021, *A novel attention-based LSTM cell post-processor coupled with Bayesian optimization for streamflow prediction*](https://doi.org/10.1016/j.jhydrol.2021.126526)
- [Cho and Kim, 2022, *Improving streamflow prediction in the WRF-Hydro model with LSTM networks*](https://doi.org/10.1016/j.jhydrol.2021.127297)
- [Tang et al., 2023, *Optimal Postprocessing Strategies With LSTM for Global Streamflow Prediction in Ungauged Basins*](https://doi.org/10.1029/2022WR034352)
- [Wang and Gupta, 2024, *Towards interpretable physical-conceptual catchment-scale hydrological modeling using the mass-conserving-perceptron*](https://doi.org/10.1029/2024WR037224)

## CAMELS 프로젝트에 대한 최종 정리

현재 프로젝트의 질문은 “어떤 backbone이 더 센가”가 아니라, `왜 extreme flood peak가 눌리는가`, `output design만 바꿔도 좋아지는가`다. 이번 문헌 조사를 기준으로 보면, 첫 논문은 `multi-basin LSTM baseline -> probabilistic head` 비교로 닫고, bounded conceptual core는 future work로 두는 게 가장 자연스럽다.

또 하나 중요한 점은, basin analysis가 논문 앞부분의 준비 작업이 아니라 결과 해석의 핵심이라는 점이다. basin을 어떻게 고르고, 어떤 subgroup으로 나누고, 어떤 event를 extreme로 정의했는지가 모델 구조만큼 중요하다. 따라서 현재 저장소의 `DRBC holdout basin 조사 -> quality gate -> event table -> flood-prone screening` 파이프라인은 literature와 잘 맞는다. 다음 단계에서는 여기에 `hydrologic diversity audit`와 `subgroup-aware evaluation plan`만 더 얹으면 된다.
