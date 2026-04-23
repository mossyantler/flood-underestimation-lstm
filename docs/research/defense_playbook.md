# 디펜드 플레이북

## 서술 목적

이 문서는 현재 연구 설계를 디펜드할 때 예상되는 질문을 먼저 뽑고, 각 질문에 대해 `현재 답변 가능 수준`, `취약한 이유`, `권장 수정안`을 한 번에 정리하기 위한 내부 기준 문서다. 논문 본문 초안이라기보다, 연구 설계를 스스로 점검하고 교수님/심사자 질문에 대비하기 위한 방어 메모에 가깝다.

## 다루는 범위

- 모델 설계형 hydrology 논문들이 보통 어떤 실험 구조를 쓰는지
- 현재 우리 설계가 그 관행과 비교해 어디서 약한지
- 예상 질문과 1차 답변 논리
- 실제로 바꾸는 것이 좋은 설계 변경안

## 다루지 않는 범위

- basin source CSV의 세부 컬럼 정의
- event extraction의 구현 상세
- future-work conceptual core의 수식 상세

## 1. 먼저 기준선을 어떻게 잡아야 하나

우리 연구의 핵심 novelty는 `새로운 basin screening 방법`이 아니라, `deterministic LSTM -> probabilistic head`라는 모델 구조 비교를 flood-focused setting에서 수행하는 데 있다. 이 점을 잊으면 basin selection과 screening이 연구 본체를 가리는 구조가 된다.

모델 구조를 개선하는 large-sample neural hydrology 문헌은 대체로 basin screening을 최소화한다. 보통은 이미 community benchmark로 자리 잡은 basin subset을 쓰고, 모델 간 공정성을 위해 `같은 basin set`, `같은 split`, `같은 forcing`, `같은 static attributes`, `같은 backbone 또는 유사한 tuning budget`을 유지한다. basin을 새로 복잡하게 고르기보다, 비교 조건을 고정하는 쪽이 일반적이다.

예를 들면 Kratzert et al. (2019)은 CAMELS 531 basin을 그대로 사용해 single universal LSTM을 학습했고, Klotz et al. (2022)은 uncertainty estimation 실험에서도 같은 531 basin benchmark와 고정된 train/validation/test period를 유지했다. Kratzert et al. (2024)의 “Never train a Long Short-Term Memory network on a single basin”도 basin을 새로 복잡하게 고르기보다, large-sample training의 이점을 같은 CAMELS benchmark에서 보여주는 구조다. Frame et al. (2022)은 극한 event 일반화 문제를 다루면서도 basin screening을 전면에 내세우지 않고, extreme-event evaluation design 쪽에 초점을 두었다. Liu et al. (2024)의 national-scale hybrid study 역시 여러 hybrid variant를 같은 national-scale basin pool 위에서 비교했다.

즉 문헌에서 주로 보는 설계 원칙은 아래와 같다.

1. `benchmark basin set 또는 단순 품질 필터`를 쓴다. basin selection이 모델 논문의 주제가 아니면, basin 정의는 최대한 단순하게 유지한다.
2. `같은 데이터 조건에서 모델만 바꾼다.` 모델 구조 비교 논문은 basin 쪽 선택 논리보다 comparison fairness가 더 중요하다.
3. `claim과 split이 일치해야 한다.` regional generalization을 주장하면 basin holdout, extreme robustness를 주장하면 event holdout이 있어야 한다.
4. `후처리 해석과 본 실험을 분리한다.` flood generation typing이나 custom susceptibility score는 main screening보다 post-hoc interpretation에 두는 것이 일반적으로 더 안전하다.

이 기준선 위에서 보면, 현재 우리 설계의 강점은 `DRBC holdout`을 분명히 잡았다는 점이고, 약점은 `basin screening이 한동안 본 실험보다 너무 앞에 나갔다`는 점이다.

## 2. 현재 우리 설계를 한 문장으로 다시 정리하면

현재 가장 디펜더블한 설계 요약은 아래다.

`non-DRBC CAMELSH basin 중 minimum quality gate와 split-level usability gate를 통과한 prepared pool에서 HUC02-stratified fixed subset300을 구성해 global multi-basin model을 학습하고, DRBC Delaware basin을 regional holdout evaluation region으로 두며, DRBC 내부에서는 observed-flow 기반 flood relevance screening을 통해 최종 평가 cohort를 확정한다.`

이 문장 안에 우리 설계의 핵심이 다 들어 있다. Delaware를 왜 쓰는지, basin screening을 왜 하는지, 모델 비교가 어디서 일어나는지가 한 번에 정리된다.

## 2A. 왜 Delaware / DRBC가 시험장이어야 하나

이 질문은 앞으로 가장 자주 받게 될 가능성이 높다. 여기서 중요한 것은 `Delaware가 미국에서 가장 홍수가 많은 유역이기 때문`이라고 단정하지 않는 것이다. 현재 우리 설계는 Delaware를 “가장 극단적인 flood hotspot”으로 택한 것이 아니라, `regional holdout evaluation region`으로 택한 것이다.

즉 우리가 Delaware를 쓰는 이유는 아래 네 가지다.

첫째, `공간적으로 일관된 holdout region`이기 때문이다. random basin sample은 training basin과 test basin이 공간적으로 섞이기 쉽고, hydrologic similarity leakage를 완전히 피하기 어렵다. 반면 DRBC는 하나의 연속된 수문 권역이기 때문에 “다른 지역에서 학습한 모델이 이 지역 전체로 일반화되는가”를 보기 좋다.

둘째, `충분한 평가 basin 수`가 있기 때문이다. 현재 DRBC 기준 CAMELSH selected basin은 154개이고, broad checklist 기준 test candidate basin은 38개다. 즉 Delaware는 단일 case basin이 아니라, regional evaluation cohort를 구성할 수 있을 정도의 basin 수를 제공한다.

셋째, `상류-하류 수문 조건이 한 권역 안에서 꽤 다양하다.` 현재 broad checklist 기준 test candidate basin만 봐도 basin area는 약 10.8–4560.6 km², 경사는 약 0.18–11.57 %, forest 비율은 약 10.6–75.0 %, developed 비율은 약 4.9–80.5 % 범위를 가진다. 즉 Delaware는 하나의 권역이지만 작은 headwater부터 큰 mainstem 영향 basin까지, 비교적 다양한 flood response 조건을 포함한다.

넷째, `실제 flood relevance와 관리 맥락이 분명하다.` Delaware mainstem에서는 2004, 2005, 2006년에 세 차례 큰 홍수가 이어졌고, 이 때문에 DRBC 차원의 Interstate Flood Mitigation Task Force가 꾸려졌다. DRBC 60주년 timeline도 이를 명시하고 있고, NWS/NOAA 자료에서도 Delaware Basin의 반복적 mainstem flooding 사례가 계속 확인된다. 즉 Delaware는 단순히 편의상 고른 곳이 아니라, flood damage reduction과 regional water management 맥락이 강한 유역이다. 출처는 [DRBC timeline](https://timeline.drbc.gov/), [NWS historical floods](https://www.weather.gov/marfc/HistoricalFloods), [NWS Delaware flood history](https://www.weather.gov/safety/flood-states-de), [NWS New Jersey flood history](https://www.weather.gov/safety/flood-states-nj)다.

정리하면 이렇게 답하는 것이 가장 좋다.

`우리는 Delaware를 무작위 표본 대신 선택했다. 이유는 이 유역이 연속된 하나의 수문 권역으로서 regional holdout 실험에 적합하고, 평가 가능한 basin 수가 충분하며, 상류-하류 flood response 조건이 다양하고, 실제 flood management relevance가 뚜렷하기 때문이다. 따라서 Delaware는 임의의 한 점 표본이 아니라, spatially coherent하고 hydrologically meaningful한 regional test bed다. 다만 여기서 평가되는 것은 Delaware regional model이 아니라, 다른 basin에서 학습한 global model의 regional generalization 성능이다.`

또 하나 중요한 점은 `random sampling과 Delaware holdout은 대체관계가 아니라 보완관계`라는 것이다. random basin sample도 robustness check로는 유용하지만, 그건 `regional transfer`를 직접 검증하지 못한다. 반대로 Delaware holdout은 random sample보다 더 강한 공간적 일반화 질문을 던질 수 있다. 즉 random sample만 쓰면 “공간적으로 엮인 basin 사이의 전이”가 아니라 “섞여 있는 basin 집합 안에서의 평균적 generalization”만 보게 된다.

## 2B. Delaware 선택에 대해 지금 당장 하면 안 되는 주장

아래 주장은 현재 근거가 부족하므로 피하는 것이 좋다.

- `Delaware가 미국에서 가장 홍수가 자주 나는 유역이라서 골랐다`
- `Delaware가 flood-prone basin을 가장 많이 포함하므로 최적이다`
- `Delaware의 모든 subbasin이 flood 연구에 이상적이다`

이런 주장을 하려면 전국 단위 비교 통계나 final observed-flow screening 결과가 있어야 한다. 현재는 그 수준까지 가지 않았기 때문에, Delaware는 `최고의 flood hotspot`이 아니라 `정당한 regional holdout test bed`라고 설명하는 것이 정확하다.

## 2C. 만약 “random sample이면 안 되나?”라고 다시 물으면

답은 이렇게 하면 된다.

`가능하다. 하지만 random sample은 regional holdout이 검증하는 질문과 다르다. random sample은 basin이 공간적으로 섞여 있기 때문에 training basin과 test basin의 기후·지형·하천망 특성이 서로 비슷할 가능성이 높다. 반면 Delaware holdout은 하나의 연속된 권역 전체를 학습에서 제외하므로, 모델이 truly unseen region으로 얼마나 일반화되는지를 더 엄격하게 볼 수 있다.`

즉 random sample은 `평균적인 basin generalization`, Delaware holdout은 `지역 단위 generalization`을 보는 방식이라고 이해하면 된다.

## 2D. 현재 우리가 둔 basin 관련 가정과 그 이유

유역을 다루면서 우리가 둔 가정은 꽤 많다. 중요한 것은 “이 가정이 진실이라서” 두는 것이 아니라, `비교 가능한 실험을 만들기 위한 operational assumption`으로 둔다는 점을 분명히 하는 것이다.

### 가정 1. DRBC polygon은 evaluation region의 공식 경계다

이 가정의 이유는 연구권역을 재현 가능하게 고정하기 위해서다. HUC exploratory layer나 visual clipping 결과를 쓰면 경계가 흔들리기 때문에, DRBC 공식 polygon을 기준으로 잡는다.

### 가정 2. DRBC basin 선택은 outlet + overlap으로 정의한다

이 가정의 이유는 basin polygon과 region polygon이 완전히 같은 체계가 아니기 때문이다. outlet만 보면 basin majority가 밖으로 나가도 포함되고, overlap만 보면 outlet가 밖인데도 들어올 수 있다. 그래서 `outlet_in_drbc == True`와 `overlap_ratio_of_basin >= 0.9`를 동시에 요구한다.

### 가정 3. non-DRBC training basin은 outlet가 DRBC 밖이고, polygon overlap은 0.1 이하까지 허용한다

이 가정의 이유는 CAMELSH polygon과 DRBC polygon의 source mismatch 때문이다. 실제로는 겹치지 않는데 geometry source 차이 때문에 작은 overlap이 생길 수 있으므로, outlet는 엄격히 밖에 두고 polygon은 작은 overlap을 허용한다.

### 가정 4. basin 품질은 usable years, estimated-flow fraction, boundary confidence로 먼저 거른다

이 가정의 이유는 모델 성능 차이가 hydrology 때문인지 data quality 때문인지 분리하기 위해서다. 자료가 짧거나 estimated flow가 많거나 basin boundary가 불확실하면, flood 모델 비교를 해도 해석이 약해진다.

### 가정 5. minimum quality gate를 통과한 basin에 대해서만 split-level usability gate를 적용한다

이 가정의 이유는 basin-level 품질 문제와 split-period 사용 가능성 문제를 분리하기 위해서다. 현재 공식 checklist에서는 먼저 `minimum_quality_gate_pass`를 판단하고, 그다음 train `720`, validation `168`, test `168` valid `Streamflow` 기준으로 `usability_status`를 정한다.

### 가정 6. 연도에 값이 조금 있다고 해서 그 해를 usable year로 세지 않는다

이 가정의 이유는 관측 기간을 과대평가하지 않기 위해서다. 그래서 annual coverage가 충분한 해만 usable year로 인정한다.

### 가정 7. 정적 basin 특성은 공식 최종 screening이 아니라 보조 해석 수단이다

이 가정의 이유는 slope, forest, soil 같은 정적 변수만으로 실제 flood relevance를 확정할 수 없기 때문이다. 정적 변수는 basin을 이해하는 데는 좋지만, 최종 flood-relevant cohort는 observed-flow 지표로 닫아야 한다.

### 가정 8. final flood-relevant basin은 observed-flow metric으로 정한다

이 가정의 이유는 우리 논문의 중심이 `홍수 가능성이 있어 보이는 basin`이 아니라 `실제 고유량 response에서 모델 차이가 드러나는 basin`이기 때문이다. 그래서 annual peaks, Q99 frequency, RBI 같은 observed-flow 기반 지표가 최종 기준이 된다.

### 가정 9. training과 evaluation의 basin 역할은 분리한다

이 가정의 이유는 global learning과 regional generalization을 동시에 보기 위해서다. 학습은 많은 basin에서 하고, 평가는 Delaware holdout에서 수행해야 “보지 않은 지역으로의 전이”를 직접 볼 수 있다.

## 2E. 현재 구현된 Model 1 스냅샷

현재 프로젝트의 공식 compute-constrained baseline 정의는 broad config를 reference로 유지하면서 `scaling_300` basin file을 override해 실행하는 `subset300` setup이다. 즉 디펜스에서는 broad config를 backbone/reference definition으로 설명하되, 실제 본 실험 실행 cohort는 고정된 `subset300`이라는 점을 분리해서 말하는 것이 맞다.

현재 구현된 backbone은 vendored NeuralHydrology의 `CudaLSTM`이다. 입력층에서는 `dynamic forcing` 시계열과 `static attributes`를 함께 처리하고, static vector는 embedding 또는 identity를 거친 뒤 각 시간 스텝에 반복 연결된다. 그다음 single-layer LSTM이 hidden state를 만들고, 마지막에는 `regression head`가 각 시간 스텝의 `Streamflow` 예측값을 낸다.

현재 baseline config는 아래처럼 요약할 수 있다.

| 항목 | 현재 값 | 디펜스에서의 설명 |
| --- | --- | --- |
| `model` | `cudalstm` | standard multi-basin LSTM baseline |
| `head` | `regression` | deterministic point prediction head |
| `loss` | `nse` | basin-scale 차이를 고려한 hydrology baseline loss |
| `seq_length` | `336` | 336시간, 즉 14일 입력 문맥 |
| `predict_last_n` | `24` | 마지막 24시간에 대해서만 loss와 metric 계산 |
| `hidden_size` | `128` | broad baseline의 기본 hidden size |
| `batch_size` | `256` | broad baseline의 기본 batch 크기 |
| `device` | `cuda` 또는 환경별 가용 장치 | 공식 비교는 broad config와 동일한 계산 조건에서 수행 |

입력값은 `11개 dynamic forcing`과 `8개 static attributes`다. 현재 dynamic forcing은 `Rainf`, `Tair`, `PotEvap`, `SWdown`, `Qair`, `PSurf`, `Wind_E`, `Wind_N`, `LWdown`, `CAPE`, `CRainf_frac`를 사용한다. static attributes는 `area`, `slope`, `aridity`, `snow_fraction`, `soil_depth`, `permeability`, `forest_fraction`, `baseflow_index`다. 여기서 변수명은 CAMELSH generic dataset의 표기를 그대로 쓴다.

출력은 `총합`이 아니라 `시간별 Streamflow 시계열`이다. 모델 head는 내부적으로 입력 시퀀스 길이 전체에 대해 `y_hat`를 만들지만, 학습 loss와 evaluation metric은 마지막 `24시간`만 잘라서 쓴다. 따라서 디펜스에서는 이 모델을 `336시간 입력을 받아 마지막 24시간의 hourly Streamflow 시계열을 예측하는 모델`이라고 설명하는 것이 가장 정확하다.

출력값의 단위도 구분해서 말해야 한다. 네트워크 내부에서는 scaler를 적용한 normalized `Streamflow`를 학습하지만, evaluation 단계에서는 inverse scaling을 거친 뒤 실제 `Streamflow` 스케일에서 metric을 계산한다. 따라서 “모델이 내는 최종 결과”는 물리 단위의 discharge time series이고, cumulative runoff나 event total volume은 이 시계열을 후처리해서 계산하는 값이다.

현재 baseline의 basin 구성은 fixed `subset300` 기준 `train 269 / validation 31 / test 38`이다. 이 subset은 broad prepared pool `1903`에서 HUC02-stratified 방식으로 뽑았고, static attribute diagnostics와 observed-flow event-response diagnostics 모두에서 representativeness가 크게 무너지지 않는다는 점을 확인한 뒤 채택했다. 따라서 디펜스에서는 “임의 축소 실험”이 아니라 “대표성 점검을 거쳐 고정한 compute-constrained main comparison cohort”라고 설명하는 것이 맞다.

## 3. 현재 설계의 가장 큰 취약점

### 3.1 Delaware 사용 이유가 한동안 약했다

예전 흐름에서는 “왜 굳이 Delaware냐”에 대한 답이 case study convenience에 가까웠다. 지금은 `Delaware = training region이 아니라 regional holdout evaluation region`으로 재정의했기 때문에 훨씬 강해졌지만, 이 논리를 문서와 발표에서 일관되게 유지해야 한다.

지금 방어의 핵심은 “Delaware가 특별해서가 아니라, spatially coherent하고 hydrologically meaningful한 holdout region이기 때문에 쓴다”는 것이다. 즉 `지역 관심`이 아니라 `일반화 평가 설계`가 먼저다.

### 3.2 basin screening이 모델 논문치고 무거웠다

정적 커스텀 점수까지 공식 screening처럼 보이면, 심사자는 “이 논문은 flood susceptibility 논문인가, 모델 설계 논문인가?”라고 묻기 쉽다. 그래서 현재처럼 정적 점수는 내부 shortlist용으로만 낮추고, 공식 screening은 `공간 기준 -> minimum quality gate -> split-level usability gate -> observed-flow flood relevance -> hydromod split`으로 단순화하는 것이 맞다.

### 3.3 final observed-flow screening이 아직 구현 전이다

이건 지금 가장 큰 실제 취약점이다. 현재 broad checklist와 prepared split 기준으로 `minimum quality gate`와 `split-level usability gate`까지는 닫혔지만, DRBC 내부의 `annual peaks`, `Q99 frequency`, `RBI`, `event runoff coefficient`를 계산한 final event-response table은 아직 없다. 따라서 “이 basin들이 flood-relevant하다”는 주장은 아직 provisional 단계다.

즉 현재는 `평가 가능한 basin`까지 정리된 상태이지, `flood-focused 최종 평가 cohort`가 확정된 상태는 아니다.

### 3.4 비교 실험의 공정성 규칙이 아직 약하다

현재 config는 잡혀 있지만, `몇 개 seed로 돌릴지`, `Model 1과 Model 2를 완전히 같은 hyperparameter budget으로 비교할지`, `head-only ablation과 full fine-tuning을 어떻게 나눌지`가 아직 명확히 잠기지 않았다. 모델 비교 논문에서는 이 부분이 basin selection보다 더 자주 공격받는다.

### 3.5 tolerance overlap 0.1은 설명은 가능하지만 민감도 확인이 필요하다

현재 non-DRBC training pool은 `outlet_in_drbc == False`이면서 `overlap_ratio_of_basin <= 0.1`까지 허용한다. 이건 source mismatch를 반영한 합리적 완화 규칙이지만, reviewer는 “왜 0.1이냐”고 물을 수 있다. 다행히 실제로 추가된 quality-pass basin이 3개뿐이라 위험은 크지 않지만, `0 vs 0.1 sensitivity`는 한 번 확인해 두는 것이 좋다.

## 4. 예상 질문과 답변, 그리고 권장 수정안

아래 질문들은 실제 디펜드에서 나올 가능성이 높은 순서대로 정리했다.

### Q1. 왜 굳이 Delaware / DRBC를 쓰나요?

현재 가장 좋은 답은 이거다. 우리는 Delaware가 특별한 hydrologic truth를 대표해서 쓰는 것이 아니라, `regional holdout evaluation region`으로 쓰고 있다. 즉 모델 학습은 non-DRBC CAMELSH basin에서 global하게 수행하고, Delaware는 처음 보는 지역에서의 일반화와 flood-focused 해석을 동시에 보기 위한 coherent test bed다. 따라서 우리 모델을 Delaware regional model이라고 부르면 안 되고, `global multi-basin model evaluated on the DRBC holdout region`이라고 설명해야 맞다.

이 답변이 먹히려면 발표와 문서에서 Delaware를 `case basin`이 아니라 `holdout region`이라고 일관되게 불러야 한다.

더 강화하려면, 가능하면 후속 단계에서 `second holdout region`을 하나 더 두는 것이 가장 좋다. 그럼 “왜 Delaware만?”이라는 질문이 많이 약해진다.

### Q2. 그러면 Delaware를 안 써도 되는 것 아닌가요?

이 질문에는 “맞다, 학습에는 Delaware가 필요 없다. 그래서 실제로 학습은 Delaware 밖에서 한다”라고 먼저 인정하는 것이 좋다. 다만 Delaware는 필요 없어서 남겨둔 것이 아니라, `모델의 regional transfer를 해석 가능한 방식으로 보여주기 위한 평가 region`으로 남겨둔 것이다.

즉 Delaware의 역할은 `training domain`이 아니라 `evaluation domain`이다.

### Q3. basin selection을 왜 이렇게 복잡하게 했나요?

현재 답변은 “공식 screening은 단순하다”로 가야 한다. 즉 basin selection의 공식 단계는

1. DRBC와 outlet/overlap으로 공간 선택,
2. usable years / estimated-flow / boundary confidence 기반 minimum quality gate,
3. split-period valid target count 기반 usability gate,
4. observed-flow 기반 flood relevance,
5. hydromod broad / natural split

뿐이라고 말하면 된다.

정적 커스텀 점수는 공식 선정 규칙이 아니라 내부 shortlist를 빨리 보기 위한 exploratory heuristic이라고 분명히 말해야 한다.

### Q4. 왜 outlet + overlap을 같이 쓰나요?

outlet만 쓰면 basin polygon의 상당 부분이 DRBC 밖으로 나가도 basin이 선택될 수 있고, overlap만 쓰면 outlet가 DRBC 밖인데도 일부가 겹친다고 basin이 포함될 수 있다. 우리는 `DRBC 안에 실제 gauge outlet가 있으면서 basin majority가 DRBC에 속하는 gauged basin`을 원하므로 두 조건을 같이 썼다고 답하면 된다.

이 질문은 현재 비교적 잘 방어 가능하다.

### Q5. 왜 non-DRBC training pool에서 overlap 0.1까지 허용했나요?

이건 geometry source mismatch 때문이다. CAMELSH polygon과 DRBC polygon은 완전히 같은 source geometry가 아니라서, 실제로는 겹치지 않는 basin도 polygon 상에서 미세 overlap이 생길 수 있다. 그래서 outlet는 반드시 DRBC 밖에 두되, polygon overlap은 `0.1 이하`까지는 tolerant하게 허용했다.

다만 이 기준은 아직 민감도 분석이 필요하다. 바로 할 수 있는 보강은 `overlap tolerance 0`과 `0.1`에서 학습 basin 수, validation basin 수, 대표 성능 차이를 비교하는 것이다. 실제로 현재 추가된 quality-pass basin이 3개뿐이므로, reviewer에게 “결과는 tolerance에 크게 의존하지 않는다”고 보여주기 쉽다.

### Q6. quality gate threshold는 왜 usable years 10, estimated flow 15 %, boundary confidence 7인가요?

현재 답변은 `engineering threshold`라는 것을 인정하는 것이 낫다. 즉 이 값들이 어떤 canonical formula에서 그대로 나온 것은 아니지만, 너무 짧은 관측, 높은 estimated-flow 의존, 불확실한 basin boundary를 제거하기 위한 보수적 품질 기준이라고 설명하면 된다.

다만 이 부분은 더 단단하게 만들 수 있다. 추천은 다음과 같다.

1. 현재 threshold를 main setting으로 유지한다.
2. Appendix나 supplementary에서 `usable years 8 / 10 / 15`, `estimated flow 10 / 15 / 20`, `boundary confidence 6 / 7 / 8` 정도의 sensitivity table을 만든다.

threshold 자체보다 `결론이 threshold에 얼마나 민감한지`를 보여주는 것이 더 중요하다.

또 하나 분명히 해야 할 점은, 이 threshold가 broad split의 최종 포함 여부를 한 번에 결정하는 유일한 기준은 아니라는 것이다. 현재 공식 checklist에서는 먼저 `minimum quality gate`를 적용하고, 그 통과 basin에 대해서만 `split-level usability gate`를 한 번 더 본다. 즉 quality gate는 basin-level 1차 스크린이고, `except`는 quality failure가 아니라 split-period target usability failure다.

현재 broad profile의 usability 기준은 `train 720`, `validation 168`, `test 168` valid `Streamflow` count다. 따라서 디펜스에서는 “우리는 basin을 quality와 usability 두 층으로 나눠 관리하고, 공식 상태는 `output/basin/checklists/camelsh_basin_master_checklist_broad.csv`의 `minimum_quality_gate_pass`와 `usability_status`로 추적한다”라고 설명하는 편이 가장 정확하다.

### Q7. usable year를 왜 그렇게 정의했나요?

이 부분은 예전보다 많이 나아졌지만, 여전히 질문이 들어올 수 있다. 지금은 연도에 1시간만 있어도 1년으로 세지 않고, `annual coverage >= 0.8`일 때만 usable year로 인정한다. 이건 방어가 가능하다. “single-hour year는 자료 품질을 과대평가하므로, 연간 coverage 기준을 둔 usable year를 사용했다”고 말하면 된다.

가능하면 이후 event table 구현 때 `usable event year`도 함께 정리하는 것이 좋다. 예를 들어 annual peak를 계산할 수 있는 year와 Q99 event를 안정적으로 셀 수 있는 year를 분리해두면 설명이 더 좋아진다.

### Q8. boundary confidence를 왜 쓰나요? 경계는 원래 정해진 것 아닌가요?

이건 비교적 쉽게 방어된다. basin polygon이 존재한다는 것과, 그 basin polygon이 실제 drainage area를 잘 대표한다는 것은 다르다. GAGES-II 기반 `BASIN_BOUNDARY_CONFIDENCE`는 basin area consistency, HUC10 alignment, gauge-to-stream geometry 관계를 반영한 QA 지표이므로, 우리는 경계가 “있는 basin”이 아니라 “믿을 만한 basin”만 쓰려는 것이라고 답하면 된다.

오히려 이걸 안 썼다면 더 약했을 것이다.

### Q9. 왜 observed-flow screening이 필요한가요? 정적 변수만으로 안 되나요?

정적 변수는 basin이 왜 flood-like response를 낼 수 있는지 설명해 주지만, 실제로 high-flow event가 자주 나타나는지는 직접 보여주지 않는다. 우리 연구의 목적은 flood susceptibility mapping이 아니라 `peak underestimation이 드러나는 basin에서 모델을 평가하는 것`이므로, 최종 cohort는 반드시 observed-flow 지표를 거쳐야 한다.

이 질문도 지금 설계의 핵심 논리와 잘 맞는다. 단, 현재 observed-flow screening이 아직 미구현이므로, 이 답을 하려면 다음 단계 구현이 반드시 따라와야 한다.

### Q10. 왜 annual peaks, Q99 frequency, RBI를 쓰나요?

이 셋은 역할이 다르다. annual peak specific discharge는 `peak magnitude`를, Q99 frequency는 `extreme-flow recurrence`를, RBI는 `flashiness`를 본다. 즉 한 지표로는 부족한 flood relevance를 서로 다른 관점에서 보완하는 구조다.

이건 Klotz et al. (2022)의 benchmark thinking과 flood literature의 high-flow / flashiness 관행과도 잘 맞는다. 다만 논문 본문에서는 너무 많은 지표를 넣기보다, `main 3개 + optional event runoff coefficient` 정도로 단순하게 유지하는 게 좋다.

### Q11. 왜 basin을 먼저 flood type으로 나누지 않나요?

Jiang et al. (2022)와 Stein et al. (2021) 계열 문헌을 따르면, flood generation typing은 `event-first`가 더 자연스럽다. 즉 event를 먼저 recent precipitation / antecedent precipitation / snow-related 등으로 나누고, 그다음 basin별 dominant type 또는 mixture를 요약하는 것이 표준적이다.

우리도 같은 방향을 따르되, 이 분류는 `학습 전 screening`이 아니라 `평가 후 해석` 계층에 둬야 한다. 그렇지 않으면 typing 자체가 또 하나의 screening criterion이 되어 설계가 너무 무거워진다.

### Q12. 왜 global training을 하면서 Delaware에서만 평가하나요?

이건 오히려 현재 설계의 장점이다. large-sample neural hydrology 문헌은 가능한 한 많은 basin으로 학습하는 것이 일반적이고, “Never train...”도 그 방향을 강하게 지지한다. 우리는 global training의 이점을 취하면서, Delaware를 처음 보는 coherent region으로 남겨 regional transfer와 flood-focused evaluation을 동시에 보려는 것이다.

즉 `학습은 넓게`, `평가는 명확하게`라는 구조라고 설명하면 된다.

### Q13. 왜 open-source pretrained weights를 그대로 안 쓰나요?

평가 basin, forcing source, screening rule, flood-focused objective가 기존 pretrained setting과 다르기 때문이다. 공개 weight를 그대로 쓰면 결과가 `모델 구조 차이` 때문인지 `pretraining task mismatch` 때문인지 구분이 어렵다. 따라서 기본은 우리 split과 우리 데이터로 학습하는 것이 맞고, pretrained initialization은 optional ablation으로만 쓰는 것이 좋다.

### Q14. probabilistic model은 head만 학습하나요, backbone도 학습하나요?

현재 가장 좋은 답은 이거다. 본 실험에서는 backbone을 deterministic model과 동일한 조건에서 초기화하되, probabilistic head를 붙인 뒤 end-to-end fine-tuning을 수행한다. head-only training은 “output design만 바꾸면 얼마나 좋아지나”를 보는 보조 ablation으로 두는 것이 맞다.

이 답을 정식 설계 문서에도 명확히 남겨야 한다.

### Q15. Model 1과 Model 2 비교는 정말 공정한가요?

이 질문이 매우 중요하다. basin selection보다 이 질문이 더 크게 들어올 가능성이 높다. 공정한 비교를 위해서는 최소한 아래가 필요하다.

1. 같은 basin split
2. 같은 forcing와 static attributes
3. 같은 temporal window
4. 같은 backbone size와 optimization budget
5. 같은 seed set 또는 다중 seed 평균

현재 문서상 1–4는 어느 정도 잡혀 있지만, `다중 seed`와 `hyperparameter budget fairness`는 아직 약하다. 논문 제출 전에는 반드시 보강해야 한다.

### Q16. 왜 seed가 하나인가요?

현재 config는 `seed: 111`로 잡혀 있어서 이 질문은 피하기 어렵다. 모델 비교 논문에서 single seed는 취약하다. 최소 `3개`, 가능하면 `5개` seed를 두고, basin-aggregate metric에 대해 평균과 분산 또는 bootstrap confidence interval을 보고하는 것이 좋다.

이건 지금 설계에서 가장 빨리 고쳐야 할 부분 중 하나다.

### Q17. 왜 이 날짜 구간(2000–2016)을 썼나요?

현재 broad prepared split은 train 2000–2010, validation 2011–2013, test 2014–2016을 기준으로 닫혀 있다. 다만 왜 이 기간이 hydrologically representative한지에 대한 설명은 아직 충분히 잠기지 않았다.

이 질문에 대비하려면 두 가지 중 하나가 필요하다.

1. CAMELSH hourly 데이터 availability와 DRBC holdout coverage를 기준으로 이 날짜가 가장 안정적인 공통 기간이라는 근거를 제시한다.
2. 아니면 더 benchmark-like한 fixed period를 다시 정의한다.

즉 날짜는 지금 설계에서 또 하나의 취약점이다.

### Q18. 왜 broad cohort와 natural cohort를 나눴나요?

broad cohort는 현실적인 전체 flood-relevant basin, natural cohort는 hydromod 영향이 적은 cleaner subset이라는 점을 분명히 하면 된다. 즉 natural cohort는 본 실험을 대체하는 것이 아니라 `sensitivity / robustness subset`이다.

따라서 main result는 broad cohort로, natural cohort는 robustness check로 위치시키는 것이 좋다.

### Q19. 왜 basin screening을 많이 했나요? 선행은 이렇게 안 하던데요?

이 질문에는 먼저 인정하는 것이 좋다. large-sample neural hydrology의 모델 설계 논문들은 대체로 benchmark basin set을 유지하고, screening을 복잡하게 가져가지 않는다. 우리도 그 방향으로 수정해서, 현재는 정적 heuristic을 공식 screening에서 내리고 `minimum quality gate -> split-level usability gate -> observed-flow relevance` 구조로 단순화했다고 답하면 된다.

즉 이 질문은 “맞는 지적이고 그래서 설계를 줄였다”가 제일 좋은 답이다.

### Q20. 그러면 지금 논문의 핵심 기여는 정확히 무엇인가요?

이 질문에 답이 길어지면 안 된다. 가장 압축된 답은 아래다.

`우리는 global multi-basin training + regional holdout flood-focused evaluation setting에서 deterministic LSTM과 probabilistic quantile LSTM을 같은 backbone 계열에서 비교하고, 특히 extreme peak underestimation과 event-level flood response에서 tail-aware output이 실제로 이득을 주는지 평가한다.`

이 문장 밖으로 basin screening novelty를 꺼내면 오히려 약해진다.

### Q21. 현재 구현된 baseline은 정확히 어떤 아키텍처인가요?

현재 구현된 baseline은 `NeuralHydrology CudaLSTM + regression head`다. 입력층은 dynamic forcing 시계열과 basin static attributes를 결합하고, single-layer LSTM이 hidden state를 계산하며, 마지막 linear regression head가 `Streamflow`를 낸다. 즉 현재 baseline은 `복잡한 hybrid`가 아니라, 가능한 한 plain한 multi-basin LSTM 기준선이다.

### Q22. 입력은 정확히 무엇인가요?

현재 baseline의 입력은 `11개 hourly dynamic forcing`과 `8개 basin static attributes`다. dynamic forcing은 `Rainf`, `Tair`, `PotEvap`, `SWdown`, `Qair`, `PSurf`, `Wind_E`, `Wind_N`, `LWdown`, `CAPE`, `CRainf_frac`이고, static attributes는 `area`, `slope`, `aridity`, `snow_fraction`, `soil_depth`, `permeability`, `forest_fraction`, `baseflow_index`다. 발표에서는 “CAMELSH generic forcing 변수명과 basin static attributes를 함께 사용한다”고 말하면 충분하다.

### Q23. 출력은 한 값인가요, 시계열인가요? 총합인가요?

출력은 `총합`이 아니라 `hourly Streamflow 시계열`이다. 더 정확히 말하면, 이 모델은 `336시간 입력 시퀀스`를 받아 내부적으로 각 시간 스텝의 `y_hat`를 만들고, 그중 마지막 `24시간`을 supervision과 evaluation에 사용한다. 따라서 현재 baseline의 operational output은 `다음 24시간의 hourly Streamflow sequence`라고 설명하는 것이 맞다.

### Q24. 출력값은 실제 유량 단위인가요, normalized 값인가요?

학습 중 네트워크가 직접 다루는 값은 normalized `Streamflow`다. 하지만 validation과 test에서 metric을 계산할 때는 inverse scaling을 거쳐 다시 실제 `Streamflow` 스케일로 바꾼다. 따라서 디펜스에서는 “네트워크 내부 표현은 normalized target이지만, 보고하는 예측은 실제 유량 시계열”이라고 답하면 된다.

### Q25. 왜 `seq_length=336`, `predict_last_n=24`인가요?

이 설정은 `14일 문맥을 보고 마지막 24시간을 맞히는` 구조다. 이유는 antecedent wetness, snow/soil memory, routing memory를 어느 정도 반영하려면 단순히 1~2일 입력만으로는 부족하기 때문이다. 따라서 336시간은 `수문학적 문맥`을 반영하기 위한 기본 입력 길이로 설명하는 것이 맞다.

### Q26. 왜 LSTM을 backbone으로 썼나요?

첫 논문의 질문은 “어떤 backbone이 최고인가”가 아니라, `deterministic -> probabilistic`로 갈 때 flood underestimation이 어떻게 바뀌는가다. 그래서 backbone은 community baseline으로 가장 설명하기 쉬운 `multi-basin LSTM`으로 고정했다. 이렇게 해야 성능 차이를 head 구조의 차이로 해석할 수 있다.

### Q27. 왜 `lagged Q`를 넣지 않았나요?

`lagged Q`를 넣으면 short-horizon 예측 성능은 좋아질 수 있지만, baseline이 지나치게 강해져서 probabilistic head의 순수 효과를 분리하기 어려워진다. 현재 baseline은 forcing와 basin attributes만으로 학습한 뒤, 그 위에서 head 구조를 바꿔도 tail bias가 줄어드는지 보려는 설계다.

### Q28. 현재 공식 subset300 split은 어떻게 정의되나요?

현재 공식 compute-constrained main comparison split은 `train 269 / validation 31 / test 38`이다. train/validation basin은 broad prepared pool `1903`에서 HUC02-stratified 방식으로 뽑은 `scaling_300` subset이고, test basin `38`과 시간 구간은 broad prepared split과 동일하게 유지한다. selection 근거는 non-DRBC validation 성능, static attribute diagnostics, observed-flow event-response diagnostics, compute cost다.

### Q29. 현재 논문용 공식 run 산출물은 준비되어 있나요?

현재 저장소에는 broad config와 subset300 실행 스크립트, prepared split, split manifest가 정리돼 있다. 현재 로컬에는 seed `111`의 subset300 run 산출물이 있으므로 단일 seed 수준 검토는 가능하다. 다만 논문용 공식 비교 결과표를 닫으려면 같은 subset으로 seed `222`, `333`을 추가 실행해 3-seed aggregate를 만들어야 한다고 설명하는 것이 정확하다.

### Q30. 그러면 논문 baseline은 무엇으로 설명해야 하나요?

논문 baseline은 `fixed subset300 main comparison`으로 설명하면 된다. broad config와 prepared split은 여전히 source pool과 reference architecture context를 제공하지만, 현재 본 실험의 직접 실행 기준은 [`../../configs/pilot/basin_splits/scaling_300/`](../../configs/pilot/basin_splits/scaling_300/)과 [`../../scripts/official/run_subset300_multiseed.sh`](../../scripts/official/run_subset300_multiseed.sh)다.

### Q31. Model 2의 출력은 Model 1과 정확히 어떻게 달라지나요?

Model 2는 backbone은 그대로 두고 head만 `quantile head`로 바뀐다. 따라서 point estimate 하나 대신 `q50`, `q90`, `q95`, `q99`의 시계열을 낸다. 여기서도 output은 `총합`이 아니라 `시간별 quantile Streamflow sequence`이고, point metric을 계산할 때는 `q50`을 중심 예측선으로 사용한다.

## 5. 지금 당장 바꾸는 것이 좋은 설계 변경안

아래는 우선순위 순서대로 정리한 변경안이다.

### 5.1 가장 먼저 해야 할 것

첫째, `final observed-flow screening`을 실제로 구현해야 한다. event_response_table이 없으면 flood-focused cohort 주장이 아직 미완성이다.

둘째, `multi-seed protocol`을 고정해야 한다. 적어도 3-seed 평균은 있어야 한다.

셋째, `날짜 구간 선택 근거`를 만들어야 한다. 단순 임시값이면 질문을 피하기 어렵다.

### 5.2 그다음 바로 해야 할 것

넷째, `overlap tolerance 0 vs 0.1 sensitivity`를 짧게라도 확인해야 한다. 실제 basin 수 차이는 작으니 금방 끝날 가능성이 높다.

다섯째, `Model 2의 학습 규칙`을 문서에 더 분명히 적어야 한다. 특히 end-to-end fine-tuning이 본 실험이고, head-only는 ablation이라는 점을 명시하는 것이 좋다.

여섯째, `main cohort`와 `robustness cohort`를 역할상 분리해야 한다. broad는 main, natural은 sensitivity다.

### 5.3 있으면 아주 좋은 것

일곱째, second holdout region을 하나 더 두면 Delaware 편중 비판이 크게 줄어든다.

여덟째, probabilistic metric의 공식 reporting set을 잠그는 것이 좋다. pinball loss, coverage, calibration을 어떤 방식으로 산출할지 지금부터 고정하는 편이 좋다.

아홉째, event typing은 main claim이 아니라 post-hoc interpretation layer로 분명히 두는 것이 좋다.

## 6. 순수 모델 설계 논문 관점에서 본 우리 설계의 취약점

모델 설계 논문만 놓고 보면, 현재 우리 설계의 취약점은 아래처럼 요약된다.

첫째, `연구 질문이 두 갈래로 갈라질 위험`이 있다. 하나는 model architecture comparison이고, 다른 하나는 flood-focused basin/event selection이다. 심사자는 보통 둘 중 하나만 main story로 보길 원한다. 따라서 main story는 반드시 모델 비교로 고정해야 한다.

둘째, `실험 공정성 규칙이 완전히 잠기지 않았다.` 같은 backbone, 같은 split, 같은 hyperparameter budget, 같은 seed protocol이 확정되어야 한다.

셋째, `physics-guided conceptual core는 아직 future work 수준이다.` Model 1/2는 비교적 바로 실험 가능하지만, conceptual core와 regularization은 아직 상세 설계 단계에 가깝다. 이 상태에서 논문 타이틀과 기여를 3-model full comparison으로 고정하면 위험하다.

넷째, `flood relevance evidence가 아직 event level에서 닫히지 않았다.` 지금은 minimum quality gate와 usability gate까지는 확정됐지만, final flood-relevant cohort는 아직 아니다.

다섯째, `Delaware holdout만으로 일반화 주장을 크게 하면 약하다.` regional case-based holdout으로는 충분하지만, “일반적으로 그렇다”는 주장을 강하게 하려면 second holdout 또는 wider test가 있으면 좋다.

## 7. 지금 시점에서 가장 디펜더블한 발표용 버전

지금 바로 교수님 앞에서 가장 안전하게 설명하려면 아래 문장 구조로 가는 것이 좋다.

먼저, 이 연구의 핵심은 basin screening이 아니라 모델 구조 비교라고 말한다. 학습은 large-sample CAMELSH basin에서 수행하고, Delaware는 regional holdout evaluation region으로 사용한다고 명시한다. 그다음 DRBC 내부에서는 basin을 flood mapping 관점이 아니라 `evaluation cohort construction` 관점에서 고른다고 설명한다. 그래서 공식 screening은 공간 선택, minimum quality gate, split-level usability gate, observed-flow flood relevance, hydromod split의 다섯 단계로 단순화했다고 말한다. 마지막으로 정적 커스텀 점수는 논문 본문용 공식 선정 규칙이 아니라 내부 exploratory shortlist라고 선을 긋는다.

이렇게 정리하면 질문이 들어와도 “우리는 모델 논문인데 screening을 왜 이렇게 복잡하게 했냐”는 공격을 대부분 피해 갈 수 있다.

## 8. 문헌 메모

아래 문헌은 현재 설계를 설명할 때 가장 직접적으로 연결되는 축이다.

- Kratzert et al. (2019), *Towards learning universal, regional, and local hydrological behaviors via machine learning applied to large-sample datasets*. single universal LSTM을 531 CAMELS basin에 학습시켜 large-sample training의 기준선을 제시했다. [HESS](https://hess.copernicus.org/articles/23/5089/2019/)
- Klotz et al. (2022), *Uncertainty estimation with deep learning for rainfall–runoff modeling*. 같은 531 basin benchmark와 고정된 train/validation/test를 유지하면서 probabilistic benchmarking procedure를 제시했다. [HESS](https://hess.copernicus.org/articles/26/1673/2022/)
- Kratzert et al. (2024), *Never train a Long Short-Term Memory (LSTM) network on a single basin*. basin selection을 복잡하게 하기보다 large-sample training 자체를 표준으로 두는 입장을 강하게 제시한다. [HESS](https://hess.copernicus.org/articles/28/4187/2024/)
- Frame et al. (2022), *Deep learning rainfall–runoff predictions of extreme events*. physics-constrained 모델과 pure LSTM을 extreme-event context에서 비교하면서, out-of-sample return period event에서 차이를 분석했다. [HESS](https://hess.copernicus.org/articles/26/3377/2022/)
- Liu et al. (2024), *A national-scale hybrid model for enhanced streamflow estimation*. national-scale basin pool 위에서 여러 hybrid variant를 공통 실험 구조로 비교했다. [HESS](https://hess.copernicus.org/articles/28/2871/2024/)
- Jiang et al. (2022), *River flooding mechanisms and their changes in Europe revealed by explainable machine learning*. event-first, basin-summary flood generation typing의 큰 방향을 제공한다. [HESS](https://hess.copernicus.org/articles/26/6339/2022/)

## 문서 정리

현재 우리 설계는 아예 잘못된 것은 아니다. 다만 `모델 설계 논문`으로서 가장 취약한 지점은 basin 쪽이 아니라 `main story 분산`, `final observed-flow screening 미구현`, `single-seed / 날짜 근거 / fairness rule 미고정` 쪽이다. 따라서 다음 액션은 basin selection을 더 복잡하게 하는 것이 아니라, `observed-flow screening 구현`, `seed protocol 고정`, `날짜 근거 확정`, `Model 2 학습 규칙 명시`에 집중하는 것이 맞다.

## 관련 문서

- [`architecture.md`](architecture.md): 현재 논문 범위의 backbone과 head 구조, future-work core 메모
- [`experiment_protocol.md`](experiment_protocol.md): split, loss, metric, config key 규칙
- [`../../output/basin/checklists/camelsh_basin_master_checklist_broad.csv`](../../output/basin/checklists/camelsh_basin_master_checklist_broad.csv): broad profile의 공식 basin checklist
- [`../../configs/camelsh_hourly_model1_drbc_holdout_broad.yml`](../../configs/camelsh_hourly_model1_drbc_holdout_broad.yml): 현재 subset300 main comparison의 reference deterministic config
- [`../../configs/camelsh_hourly_model2_drbc_holdout_broad.yml`](../../configs/camelsh_hourly_model2_drbc_holdout_broad.yml): 현재 subset300 main comparison의 reference probabilistic config
- [`../../scripts/official/run_subset300_multiseed.sh`](../../scripts/official/run_subset300_multiseed.sh): 현재 공식 compute-constrained main comparison runner
