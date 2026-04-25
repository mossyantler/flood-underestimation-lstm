# Experiment Protocol

## 서술 목적

이 문서는 모델 실험의 `실행 규범`을 묶은 기준 문서다. 즉 어떤 split을 만들고, 어떤 config key를 쓰고, loss와 metric을 어떻게 계산할지를 정리한다.

## 다루는 범위

- 첫 논문 범위의 dataset, split, loss, metric 규칙
- NeuralHydrology config key 대응
- built-in metric과 custom post-processing 경계
- run 산출물과 보고 규칙

## 다루지 않는 범위

- 연구 질문의 배경 설명
- 모델 구조의 개념적 서술
- quantile head의 직관적 가이드

## 상세 서술

## 1. 실험 단위와 비교 축

현재 공식 비교 축은 아래 두 모델이다.

| 모델 | 목적 | 기본 config 방향 |
| --- | --- | --- |
| Model 1 | deterministic baseline | `model: cudalstm`, `head: regression`, `loss: nse` |
| Model 2 | output design 효과 검증 | `model: cudalstm`, `head: quantile`, `loss: pinball` |

핵심 원칙은 `backbone은 고정하고, head만 바꾼다`는 점이다. 그래야 Model 1 대비 Model 2의 개선을 `tail-aware output`의 효과로 해석할 수 있다. `physics-guided conceptual core`는 현재 논문 범위 밖의 future work 메모다.

### 1.1 Model 1 vs Model 2 공식 통제변인

첫 논문의 본 비교축에서는 `Model 1 vs Model 2`를 가장 먼저 고정한다. 이 비교는 `deterministic baseline`과 `probabilistic head`의 차이만 보려는 실험이므로, 아래 항목은 공식 통제변인으로 잠근다.

| 범주 | config key | 공식 고정값 |
| --- | --- | --- |
| dataset | `dataset` | `generic` |
| prepared data root | `data_dir` | `./data/CAMELSH_generic/drbc_holdout_broad` |
| basin split | `train_basin_file` | `./data/CAMELSH_generic/drbc_holdout_broad/splits/train.txt` |
| basin split | `validation_basin_file` | `./data/CAMELSH_generic/drbc_holdout_broad/splits/validation.txt` |
| basin split | `test_basin_file` | `./data/CAMELSH_generic/drbc_holdout_broad/splits/test.txt` |
| train 기간 | `train_start_date`, `train_end_date` | `01/01/2000` to `31/12/2010` |
| validation 기간 | `validation_start_date`, `validation_end_date` | `01/01/2011` to `31/12/2013` |
| test 기간 | `test_start_date`, `test_end_date` | `01/01/2014` to `31/12/2016` |
| backbone | `model` | `cudalstm` |
| dynamic input | `dynamic_inputs` | `Rainf`, `Tair`, `PotEvap`, `SWdown`, `Qair`, `PSurf`, `Wind_E`, `Wind_N`, `LWdown`, `CAPE`, `CRainf_frac` |
| static input | `static_attributes` | `area`, `slope`, `aridity`, `snow_fraction`, `soil_depth`, `permeability`, `forest_fraction`, `baseflow_index` |
| target | `target_variables` | `Streamflow` |
| nonnegative target rule | `clip_targets_to_zero` | `Streamflow` |
| lookback | `seq_length` | `336` |
| supervised horizon | `predict_last_n` | `24` |
| hidden dimension | `hidden_size` | `128` |
| forget gate init | `initial_forget_bias` | `3` |
| dropout | `output_dropout` | `0.3` |
| optimizer | `optimizer` | `Adam` |
| learning rate schedule | `learning_rate` | epoch `0: 10^{-3}`, `10: 5 \times 10^{-4}`, `20: 10^{-4}` |
| batch size | `batch_size` | broad reference `256`; subset300 main comparison actual run `384` |
| epochs | `epochs` | `30` |
| gradient clipping | `clip_gradient_norm` | `1` |
| validation cadence | `validate_every` | broad reference `1`; subset300 main comparison actual run `5` |
| validation basin sampling | `validate_n_random_basins` | broad reference `200`; subset300 main comparison actual run `31` |
| built-in metric set | `metrics` | `NSE`, `KGE`, `FHV`, `Peak-Timing`, `Peak-MAPE` |
| output 저장 | `save_all_output` | broad reference `True`; subset300 main comparison actual run `False` |
| validation prediction 저장 | `save_validation_results` | `True` |

여기서 중요한 점은 `lagged Q`를 넣지 않는다는 것이다. lagged discharge를 넣으면 short-horizon baseline이 과도하게 강해져서, probabilistic head 자체가 peak underestimation을 얼마나 줄였는지 해석하기 어려워진다.

### 1.2 Model 1 vs Model 2에서 바뀌는 값

위 표를 고정한 상태에서, Model 1과 Model 2 사이에서 공식적으로 달라질 수 있는 값은 아래뿐이다.

| 비교 항목 | Model 1 | Model 2 |
| --- | --- | --- |
| `experiment_name` | `camelsh_hourly_model1_drbc_holdout_broad` | `camelsh_hourly_model2_drbc_holdout_broad` |
| `head` | `regression` | `quantile` |
| `loss` | `nse` | `pinball` |
| `quantiles` | 해당 없음 | `[0.5, 0.9, 0.95, 0.99]` |
| `quantile_loss_weights` | 해당 없음 | `[1.0, 1.0, 1.0, 1.0]` |

이 규칙의 의미는 단순하다. Model 1 대비 Model 2의 차이는 `output design과 training objective의 차이`로만 해석해야 한다. hidden size, 입력 변수, split, optimizer까지 같이 바뀌면 결과 차이를 probabilistic head의 효과라고 말할 수 없다.

### 1.3 Seed protocol 고정 규칙

single seed 비교는 모델 비교 논문에서 취약하므로, 본 실험의 공식 보고 규칙은 모델별 `3-repeat average`로 잠근다. 첫 제출 버전의 기본 seed set은 아래처럼 둔다.

```yaml
model1_seeds: [111, 222, 444]
model2_seeds: [111, 222, 444]
```

Model 1과 Model 2는 같은 `scaling_300` basin file과 같은 runtime setting으로 반복 실행한다. Model 2 seed `333`은 NaN loss로 중단되어 final comparison에서는 seed `444`를 replacement repeat로 쓴다. 공정한 paired-seed 비교를 위해 완료된 Model 1 seed `333`도 final aggregate에서 제외한다. 논문 본문과 내부 요약표에는 basin-aggregate metric의 `mean \pm std`를 우선 보고한다.

추가 seed를 더 돌리는 것은 가능하지만, 본문 기준선은 모델별 세 repeat를 먼저 끝낸다. 반대로 hardware 제약 때문에 repeat 수를 줄이는 것은 공식 비교 실험에서는 허용하지 않는다.

seed override가 필요하면 broad config를 임시로 복사해 seed만 바꾼 temporary override config를 만들어 반복 실행하면 된다. 현재 저장소에는 reference broad runner [`../../scripts/official/run_broad_multiseed.sh`](../../scripts/official/run_broad_multiseed.sh), 현재 채택된 fixed `subset300` main comparison runner [`../../scripts/official/run_subset300_multiseed.sh`](../../scripts/official/run_subset300_multiseed.sh), 로컬 점검용 실행 스크립트 [`../../scripts/dev/run_local_sanity.sh`](../../scripts/dev/run_local_sanity.sh)가 있다. deterministic scaling pilot은 별도 경로 [`../../scripts/pilot/run_deterministic_scaling_pilot.sh`](../../scripts/pilot/run_deterministic_scaling_pilot.sh)로 분리해 두고, 본 3-repeat main comparison runner와 섞지 않는다.

### 1.4 환경 파라미터 취급 규칙

`device`, `num_workers`, `cache_validation_data`, `log_interval` 같은 값은 실행 환경 파라미터다. 이 값들은 실험 재현성과 실행 가능성에는 중요하지만, 연구 질문 자체를 정의하는 핵심 통제변인과는 구분한다.

공식 비교표와 논문 Methods에서는 가능한 한 같은 환경에서 Model 1과 Model 2를 돌린다. 다만 환경 차이 때문에 `batch_size`, `hidden_size`, `seq_length`, split, input 목록 같은 핵심 통제변인을 모델별로 다르게 바꾸는 것은 허용하지 않는다. 현재 compute-constrained 공식 비교축은 broad config를 reference로 유지하되, basin file은 [`../../configs/pilot/basin_splits/scaling_300/`](../../configs/pilot/basin_splits/scaling_300/)으로 고정한 `subset300` 실행 기준이다. 실제 subset300 run config에는 helper override로 `batch_size=384`, `validate_every=5`, `validate_n_random_basins=31`, `save_all_output=False`, `save_validation_results=True`가 저장된다.

현재 broad config의 기본 `device`는 `cuda:0`으로 둔다. 다만 broad 실행 스크립트는 `NH_DEVICE` 환경변수로 일시 override를 받을 수 있으므로, 로컬 점검이 필요하면 `NH_DEVICE=mps` 또는 `NH_DEVICE=cpu`로 실행할 수 있다. 이 경우에도 공식 보고용 비교 실험에서는 Model 1과 Model 2에 같은 환경 값을 써야 한다.

### 1.5 Deterministic scaling pilot의 위치

scaling pilot은 `최종 non-DRBC basin 수를 운영적으로 정하기 위한 pilot`이다. 즉 이 실험은 `공식 Model 1 vs Model 2 main comparison`이 아니라, compute 제약 아래에서 전국 범위 multi-basin frame을 유지하려면 basin 수를 어디까지 줄일 수 있는지 먼저 보는 의사결정 단계다.

선행연구 맥락도 이 해석과 맞춘다. large-sample neural hydrology benchmark 논문들은 보통 quality-filtered fixed basin set을 먼저 정의하고, 이후 모델 논문에서는 그 benchmark를 그대로 재사용한다. 즉 subset을 seed나 모델마다 다시 최적화하는 접근은 benchmark fairness와 맞지 않는다. 현재 프로젝트도 basin-count pilot을 한 번 닫은 뒤에는 동일한 subset을 모든 seed와 모델에 고정한다.

현재 pilot은 아래 원칙을 따른다.

1. `Model 1 deterministic baseline`만 사용한다. quantile head나 warm-start는 pilot에 넣지 않는다.
2. backbone과 시간 경계는 official broad setup과 같게 둔다. 즉 `hidden_size=128`, `seq_length=336`, `predict_last_n=24`, `train 2000–2010`, `validation 2011–2013`, `test 2014–2016`을 유지한다.
3. basin 수만 바꾼다. 현재 tracked subset은 `100 / 300 / 600`이고, raw broad non-DRBC pool `1923`을 source-of-truth로 보되 실제 실행 가능한 subset은 broad prepared train/validation basin `1903`에서 HUC02-stratified 방식으로 생성한다.
4. pilot run은 official broad config와 출력 경로를 공유하지 않는다. 현재 pilot config는 [`../../configs/pilot/`](../../configs/pilot/), subset manifest는 [`../../configs/pilot/basin_splits/`](../../configs/pilot/basin_splits/), run output은 `./runs/scaling_pilot` 아래에 둔다.
5. pilot의 기본 실행 단위는 `from-scratch deterministic run`이다. 다만 본문용 공식 보고 규칙인 model별 `3-repeat average`는 main comparison에만 잠그고, pilot은 운영 판단용 기본 seed로 먼저 돌린다.
6. basin-count 선택은 `non-DRBC validation 성능 + static attribute distribution diagnostics + observed-flow event-response diagnostics + random same-size subset benchmark + compute cost`를 함께 보고 내린다. DRBC holdout test metric은 pilot basin 수 선택에 사용하지 않는다. subset 생성 논리는 `fixed benchmark reuse` 관행과 `cLHS-style covariate representativeness` 아이디어를 절충한 것으로 읽는다.

pilot 의사결정은 현재 `300`에서 닫는다. 대표성 점검은 [`../../configs/pilot/diagnostics/attribute_distribution_scope_summary.csv`](../../configs/pilot/diagnostics/attribute_distribution_scope_summary.csv), [`../../configs/pilot/diagnostics/event_response/event_response_scope_summary.csv`](../../configs/pilot/diagnostics/event_response/event_response_scope_summary.csv), [`../../configs/pilot/diagnostics/permutation_benchmark/subset300_random_benchmark_summary.csv`](../../configs/pilot/diagnostics/permutation_benchmark/subset300_random_benchmark_summary.csv)를 함께 기준으로 읽는다. observed-flow 진단에서 `scaling_300`의 max absolute standardized mean difference는 `combined 0.0584`, `train 0.0567`, `validation 0.0891`로 모두 `0.10` 아래였고, random same-size subset benchmark에서도 event-response validation mismatch는 random draw의 `96.5~97.5%`보다 더 좋았다. 현재는 seed `111`에서 사용한 같은 `scaling_300` basin file을 Model 1 / Model 2 seed `111 / 222 / 444`에도 그대로 재사용한다.

따라서 Methods나 내부 결과표에서 pilot 결과를 인용할 때는 반드시 `basin-count selection pilot` 또는 `operational scaling pilot`이라고 명시해야 한다. 다만 pilot decision이 이미 닫힌 뒤의 본 실험 실행은 `subset300 main comparison`으로 따로 부르고, `main comparison result`와 파일 경로를 분리해 기록한다.

## 2. 공통 데이터 규칙

모든 실험은 `CAMELSH hourly` 기반 `hourly streamflow prediction`을 대상으로 한다. 입력은 `dynamic forcing + static attributes`이고, 기본 입력 집합은 아래를 권장한다.

- Dynamic forcing: `prcp`, `tmax`, `tmin`, `srad`, `vp`, 필요 시 `PET`
- Static attributes: `area`, `slope`, `aridity`, `snow fraction`, `soil depth`, `permeability`, `forest fraction`, `baseflow index`

`lagged Q`는 현재 baseline 비교축에서는 쓰지 않는다. lagged observation이 들어가면 deterministic baseline이 과하게 강해지고, probabilistic head의 순수 효과를 분리하기 어렵기 때문이다.

## 3. Split 생성 규칙

두 모델은 같은 split 정의를 공유해야 한다. 같은 split에서 backbone과 head만 달라져야 비교가 성립한다.

### 3.1 Temporal split

Temporal split은 `같은 basin, 다른 시기`를 평가하는 기본 split이다. 구현에서는 같은 basin file을 쓰고, `train_start_date`, `train_end_date`, `validation_start_date`, `validation_end_date`, `test_start_date`, `test_end_date`를 시간축으로만 나눈다.

핵심 규칙은 다음과 같다.

1. train, validation, test 기간은 시간적으로 겹치지 않아야 한다.
2. 같은 basin 집합을 사용하되, 날짜 경계만 달라야 한다.
3. Model 1과 Model 2는 동일한 basin file과 동일한 날짜 경계를 재사용한다.

이 split은 `same-basin / different-time` 일반화를 확인하는 기준선 역할을 한다.

#### 3.1.1 왜 `2000-01-01`부터 `2016-12-31`까지를 쓰는가

CAMELSH hourly 관측 가용 연도 자체는 더 길다. 실제 hourly availability table 기준으로 연도 범위는 `1980`부터 `2024`까지다. 다만 첫 논문의 공식 benchmark는 `가장 이른 관측 연도`가 아니라, `많은 basin이 공통으로 비교 가능한 현대 구간`을 기준으로 잡는다.

현재 broad quality-pass basin 후보 `1961개`를 기준으로 보면, `first_obs_year_usable`의 중앙값은 `1995`, 25 분위는 `1991`, 75 분위는 `2001`이다. 즉 1980년대부터 안정적으로 usable한 basin은 많지 않다. 실제로 `1990-01-01`부터 `2016-12-31`까지 usable span을 덮는 basin은 `37/1961`뿐이고, `2000-01-01`부터 `2016-12-31`까지는 `1375/1961`이 남는다.

따라서 첫 공식 비교에서는 `1980년대부터의 장기 관측소 몇 개`에 맞추기보다, 더 많은 basin을 유지하면서 같은 시간 경계를 공정하게 공유할 수 있는 `2000-01-01`부터 `2016-12-31`까지를 공통 창으로 사용한다. 이 선택은 basin pool 보존과 temporal benchmark 재현성을 우선한 것이다.

세부 경계도 같은 논리로 잡는다. `train = 2000-01-01 ~ 2010-12-31`은 hourly LSTM이 antecedent wetness, seasonal cycle, routing memory를 학습하기에 충분한 `11년` 학습 구간을 확보하기 위한 것이다. `validation = 2011-01-01 ~ 2013-12-31`, `test = 2014-01-01 ~ 2016-12-31`은 tuning 구간과 최종 평가 구간을 각각 `3년`씩 분리해, 미래 정보 누수 없이 calibration과 final reporting을 구분하기 위한 것이다.

즉 현재 시간 경계는 `수문학적으로 유일한 정답`이라기보다, `공정 비교`, `충분한 학습 길이`, `basin pool 보존`, `prepared split 재현성`을 동시에 만족시키기 위한 운영 기준으로 이해하는 것이 맞다.

### 3.2 Basin holdout split

Basin holdout은 `처음 보는 basin`에 대한 일반화를 평가한다. 현재 기본 설계에서는 `DRBC Delaware basin 전체`를 regional holdout test region으로 두고, `train_basin_file`과 `validation_basin_file`은 outlet가 DRBC 밖에 있으며 polygon overlap은 `0.1` 이하까지 허용한 basin으로 구성한다. 즉 실험 구조는 `global multi-basin training + DRBC regional holdout evaluation`이고, Delaware regional model을 따로 학습하는 것은 아니다. 구현에서는 `train_basin_file`, `validation_basin_file`, `test_basin_file`을 서로 분리한다.

핵심 규칙은 다음과 같다.

1. train과 test basin은 반드시 disjoint해야 한다.
2. validation basin도 train/test와 겹치지 않는 독립 집합을 권장한다.
3. 현재 regional holdout 실험에서는 DRBC와 `공간적으로 겹치는 basin`을 train에서 제외해 leakage를 줄인다.
4. 날짜 범위는 가급적 동일 기간으로 두고, 일반화의 차이가 basin identity에서 오도록 만든다.

현재 기본 split file은 아래를 사용한다.

- broad training: [`../../configs/basin_splits/drbc_holdout_train_broad.txt`](../../configs/basin_splits/drbc_holdout_train_broad.txt)
- broad validation: [`../../configs/basin_splits/drbc_holdout_validation_broad.txt`](../../configs/basin_splits/drbc_holdout_validation_broad.txt)
- broad test: [`../../configs/basin_splits/drbc_holdout_test_drbc_quality.txt`](../../configs/basin_splits/drbc_holdout_test_drbc_quality.txt)
- natural training: [`../../configs/basin_splits/drbc_holdout_train_natural.txt`](../../configs/basin_splits/drbc_holdout_train_natural.txt)
- natural validation: [`../../configs/basin_splits/drbc_holdout_validation_natural.txt`](../../configs/basin_splits/drbc_holdout_validation_natural.txt)
- natural test: [`../../configs/basin_splits/drbc_holdout_test_drbc_quality_natural.txt`](../../configs/basin_splits/drbc_holdout_test_drbc_quality_natural.txt)

scaling pilot은 위 official broad split과 test region을 고정한 채, non-DRBC broad train/validation basin만 HUC02-stratified subset으로 축소한다. 현재 tracked subset 경로는 아래를 사용한다.

- pilot 100: [`../../configs/pilot/basin_splits/scaling_100/train.txt`](../../configs/pilot/basin_splits/scaling_100/train.txt), [`../../configs/pilot/basin_splits/scaling_100/validation.txt`](../../configs/pilot/basin_splits/scaling_100/validation.txt), [`../../configs/pilot/basin_splits/scaling_100/test.txt`](../../configs/pilot/basin_splits/scaling_100/test.txt)
- pilot 300: [`../../configs/pilot/basin_splits/scaling_300/train.txt`](../../configs/pilot/basin_splits/scaling_300/train.txt), [`../../configs/pilot/basin_splits/scaling_300/validation.txt`](../../configs/pilot/basin_splits/scaling_300/validation.txt), [`../../configs/pilot/basin_splits/scaling_300/test.txt`](../../configs/pilot/basin_splits/scaling_300/test.txt)
- pilot 600: [`../../configs/pilot/basin_splits/scaling_600/train.txt`](../../configs/pilot/basin_splits/scaling_600/train.txt), [`../../configs/pilot/basin_splits/scaling_600/validation.txt`](../../configs/pilot/basin_splits/scaling_600/validation.txt), [`../../configs/pilot/basin_splits/scaling_600/test.txt`](../../configs/pilot/basin_splits/scaling_600/test.txt)

요약 수치는 [`../../output/basin/splits/drbc_holdout/drbc_holdout_split_summary.json`](../../output/basin/splits/drbc_holdout/drbc_holdout_split_summary.json)에 정리한다.
pilot subset 요약과 stratified manifest는 [`../../configs/pilot/basin_splits/scaling_pilot_summary.json`](../../configs/pilot/basin_splits/scaling_pilot_summary.json), [`../../configs/pilot/basin_splits/prepared_pool_manifest.csv`](../../configs/pilot/basin_splits/prepared_pool_manifest.csv), 각 `scaling_*/manifest.csv`에 정리한다. static attribute distribution diagnostics는 [`../../configs/pilot/diagnostics/attribute_distribution_scope_summary.csv`](../../configs/pilot/diagnostics/attribute_distribution_scope_summary.csv)와 관련 CSV/JSON에 정리하고, 해석용 시각화 목록은 [`../../configs/pilot/diagnostics/plots/plot_manifest.json`](../../configs/pilot/diagnostics/plots/plot_manifest.json)에 정리한다.

현재 본 실험의 공식 train/validation basin file은 위 tracked subset 중 `pilot 300`만 사용한다. 즉 train `269`, validation `31`, test `38` 구성을 Model 1 / Model 2 seed `111 / 222 / 444`에 공통으로 고정하고, 공식 실행 진입점은 [`../../scripts/official/run_subset300_multiseed.sh`](../../scripts/official/run_subset300_multiseed.sh)다. broad prepared split 전체 `1705 / 198 / 38`은 subset 생성의 source pool과 reference architecture context로 유지하되, 현재 compute-constrained main comparison의 직접 실행 split은 아니다.

이 split은 문헌에서 말하는 PUB/PUR 성격의 regionalization 평가에 해당한다. 중요한 점은 여기서 평가 대상이 regional holdout일 뿐, 학습 모델 자체는 non-DRBC basin들로 학습한 global model이라는 것이다.

### 3.3 Extreme-event holdout split

Extreme-event holdout은 `훈련 분포 바깥의 flood peak`에 대한 외삽 성능을 보기 위한 split이다. 이 split은 반드시 [`event_response_spec.md`](../workflow/event_response_spec.md)를 기준으로 event를 정의한 뒤 만들어야 한다.

현재 규칙은 아래를 따른다.

1. basin별 high-flow threshold는 기본 `Q99`를 쓴다.
2. Q99 기준 독립 event 수가 5개 미만이면 `Q98`, 그래도 5개 미만이면 `Q95`로 fallback한다.
3. 독립 event 판정은 `72시간 inter-event separation`을 사용한다.
4. event boundary는 peak 기준 threshold crossing으로 자른다.
5. holdout 대상은 basin별 상위 event 일부이며, 이 구간은 train에서 제외하고 test에서만 평가한다.

이 split의 목적은 test 기간을 뒤로 미루는 것이 아니라, 학습 중 거의 보지 못한 extreme peak에 모델이 얼마나 견디는지 보는 데 있다.

### 3.4 Minimum quality gate와 usability gate

현재 broad profile의 공식 basin 추적 표는 [`../../output/basin/checklists/camelsh_basin_master_checklist_broad.csv`](../../output/basin/checklists/camelsh_basin_master_checklist_broad.csv)다. 이 표는 CAMELSH 전체 9008 basin에 대해 `minimum quality gate`와 `split-level usability gate`를 같은 기준으로 기록한다.

`minimum quality gate`는 basin-level 1차 스크린이다. 현재 공식 기준은 `passes_obs_years_gate`, `passes_estimated_flow_gate`, `passes_boundary_conf_gate`이고, 결과는 `minimum_quality_gate_pass`와 `minimum_quality_gate_reason`으로 남긴다.

`usability gate`는 minimum quality gate를 통과한 broad split 후보에만 적용한다. 현재 기준은 아래처럼 고정한다.

- `train`: valid `Streamflow` count `>= 720`
- `validation`: valid `Streamflow` count `>= 168`
- `test`: valid `Streamflow` count `>= 168`

최종 상태는 `usability_status`로 관리한다. 의미는 아래처럼 고정한다.

- `train`, `validation`, `test`: 해당 split에서 target usability를 통과한 basin
- `except`: minimum quality gate는 통과했지만 split-period target usability를 통과하지 못한 basin
- `not_applicable`: minimum quality gate에서 먼저 탈락했거나 broad split 후보가 아닌 basin

prepared broad split과 split manifest는 [`../../data/CAMELSH_generic/drbc_holdout_broad/splits/`](../../data/CAMELSH_generic/drbc_holdout_broad/splits/) 아래에 둔다. broad prepared split은 현재도 subset 생성의 source pool과 reference run definition으로 유지한다. 다만 compute 제약을 반영한 현재 공식 main comparison은 broad config를 reference로 유지하면서 train/validation basin file만 [`../../configs/pilot/basin_splits/scaling_300/`](../../configs/pilot/basin_splits/scaling_300/)으로 override해 실행한다. scaling pilot 관련 결과 split과 diagnostics는 `configs/pilot/` 아래에 별도로 둔다.

## 4. 모델별 loss 규칙

### 4.1 Model 1: deterministic baseline

Model 1의 기본 loss는 `nse`로 둔다. 수문 자료는 basin 간 scale 차이가 크기 때문에, 첫 baseline은 `mse`보다 `nse`가 더 자연스럽다.

`mse`는 optional ablation으로만 둔다. 즉 `MSE baseline`을 별도 실험으로 추가하는 것은 가능하지만, 첫 논문의 공식 baseline은 `loss: nse`를 우선 기준으로 삼는다.

### 4.2 Model 2: quantile probabilistic baseline

Model 2는 backbone은 Model 1과 동일하고, 출력 head만 quantile 구조로 바꾼다. 현재 구현 기준의 기본 quantile set은 아래와 같다.

```yaml
head: quantile
loss: pinball
quantiles: [0.5, 0.9, 0.95, 0.99]
quantile_loss_weights: [1.0, 1.0, 1.0, 1.0]
```

여기서 `q50`은 중심선이고, `q90`, `q95`, `q99`는 upper-tail 응답을 직접 학습한다. 현재 vendored NeuralHydrology 구현은 quantile crossing을 막기 위해 상위 quantile을 `positive increment` 구조로 만든다. 즉 `q50 <= q90 <= q95 <= q99`가 자동으로 유지된다.

기본 loss는 weighted pinball loss다.

```text
L = Σ_k w_k Pinball(y, q_tau_k)
```

첫 비교 실험에서는 `quantile_loss_weights`를 동일 가중치로 두고, 필요하면 tail-emphasized ablation을 별도로 둔다. 그래야 `head 구조의 효과`와 `가중치 조정 효과`를 섞지 않는다.

### 4.3 Future Work 메모

physics-guided conceptual core는 현재 논문의 공식 비교축이 아니다. 다만 후속 연구에서는 Model 2의 probabilistic loss 위에 conceptual core 관련 regularization을 추가하는 방향을 고려할 수 있다.

```text
L_total = L_prob + λ_mass L_mass_balance + λ_nonneg L_nonnegativity + λ_bound L_storage_bounds
```

현재 문서의 즉시 구현 대상은 Model 1과 Model 2로 제한한다. conceptual core는 `physics regularization term`, `state variable schema`, `bounded coefficient definition`이 확정되면 별도 문서에서 확장한다.

## 5. Metric 계산 규칙

metric은 `point metric`, `flood-specific metric`, `probabilistic metric`으로 나눠 계산한다. 중요한 원칙은 `point metric은 모두 y_hat 기준`이라는 점이다. 따라서 Model 2에서는 `q50`을 `y_hat`으로 보고 point metric을 계산한다.

### 5.1 Point metric

필수 보고 대상은 `NSE`, `KGE`, `NSElog`다.

- `NSE`, `KGE`는 현재 vendored NeuralHydrology built-in metric으로 직접 계산 가능하다.
- `NSElog`는 현재 vendored NeuralHydrology에 built-in으로 없으므로, post-processing 단계에서 별도 계산한다.

즉 config의 `metrics:`에는 우선 built-in metric만 넣고, `NSElog`는 run output을 읽어 custom evaluation script에서 추가 산출하는 방식을 기본으로 둔다.

### 5.2 Flood-specific metric

현재 프로젝트의 flood 특화 metric은 아래를 공식 대상으로 둔다.

- `FHV`
- `Peak Relative Error`
- `Peak Timing Error`
- `top 1% flow recall`
- `event-level RMSE`

이 중 현재 vendored NeuralHydrology에서 바로 계산 가능한 built-in metric은 아래와 같다.

| 프로젝트 용어 | NeuralHydrology metric key | 비고 |
| --- | --- | --- |
| `FHV` | `FHV` | 직접 사용 가능 |
| `Peak Timing Error` | `Peak-Timing` | 직접 사용 가능 |
| `Peak Relative Error` | `Peak-MAPE` | built-in은 absolute percentage error라서, signed relative error가 필요하면 custom post-processing 추가 |
| missed peak 비율 | `Missed-Peaks` | 보조 진단 지표로 사용 가능 |

`top 1% flow recall`과 `event-level RMSE`는 현재 built-in이 아니므로 custom post-processing으로 계산한다. 특히 `event-level RMSE`는 event 정의가 [`event_response_spec.md`](../workflow/event_response_spec.md)와 일치해야 하므로, event table 기반 후처리로 계산하는 것을 원칙으로 한다.

### 5.3 Probabilistic metric

Model 2에서는 아래 probabilistic metric을 추가 보고한다.

- `pinball loss`
- `coverage`
- `calibration`

여기서 `pinball loss`는 training/validation loss와 같은 정의를 사용한다. `coverage`는 예를 들어 `q90`이면 실제 관측의 약 90%가 그 아래에 들어가는지를 보는 값이고, `calibration`은 예측 quantile과 관측 빈도가 얼마나 잘 맞는지 보는 값이다.

현재 vendored NeuralHydrology에는 coverage/calibration built-in metric이 없으므로, `test_all_output.p` 또는 후속 export 결과를 읽는 custom evaluation script에서 계산한다.

## 6. Config key 대응 규칙

논문 문장과 실제 config가 다르게 불리면 구현이 흔들리기 쉽다. 따라서 아래 key 이름을 공식 대응 규칙으로 둔다.

| 개념 | config key | 현재 기준 |
| --- | --- | --- |
| backbone | `model` | `cudalstm` |
| output head | `head` | `regression`, `quantile` |
| training loss | `loss` | `nse`, `pinball` |
| quantile set | `quantiles` | `[0.5, 0.9, 0.95, 0.99]` |
| quantile weight | `quantile_loss_weights` | 기본 equal weight |
| forcing source | `forcings` | dataset source에 맞춤 |
| dynamic input 목록 | `dynamic_inputs` | forcing 변수명 리스트 |
| static input 목록 | `static_attributes` | basin attribute 리스트 |
| target variable | `target_variables` | 보통 discharge 1개 |
| lookback length | `seq_length` | hourly 기준 별도 결정 |
| supervised horizon | `predict_last_n` | hourly 기준 별도 결정 |
| basin split | `train_basin_file`, `validation_basin_file`, `test_basin_file` | split별 basin 목록 파일 |
| time split | `train_start_date`, `train_end_date`, `validation_start_date`, `validation_end_date`, `test_start_date`, `test_end_date` | temporal boundary |
| evaluation metric list | `metrics` | built-in metric만 직접 입력 |

중요한 점은 `metrics`에 논문용 모든 지표를 그대로 넣지 않는다는 점이다. 현재 framework가 직접 계산하는 metric과, 후처리로 계산하는 metric을 구분해야 한다. 예를 들어 `NSElog`, `coverage`, `calibration`, `top 1% flow recall`, `event-level RMSE`는 현재 별도 평가 스크립트에서 계산해야 한다.

## 7. 기준 config 템플릿

Model 1과 Model 2의 최소 기준 형태는 아래처럼 정리한다.

### 7.1 Model 1 template

```yaml
model: cudalstm
head: regression
loss: nse

dynamic_inputs: [...]
static_attributes: [...]
target_variables: [...]

seq_length: ...
predict_last_n: ...
```

### 7.2 Model 2 template

```yaml
model: cudalstm
head: quantile
loss: pinball

quantiles: [0.5, 0.9, 0.95, 0.99]
quantile_loss_weights: [1.0, 1.0, 1.0, 1.0]

dynamic_inputs: [...]
static_attributes: [...]
target_variables: [...]

seq_length: ...
predict_last_n: ...
```

Model 2는 Model 1과 `같은 split`, `같은 backbone`, `같은 input 구성`을 유지해야 한다. 다르게 두는 것은 원칙적으로 `head`, `loss`, 그리고 quantile 관련 key뿐이다.

## 8. 산출물과 보고 규칙

run 결과는 기본적으로 `runs/<experiment_name>_<timestamp>/` 아래에 저장한다. 현재 기준으로 최소 확인 대상은 아래 파일들이다.

- `output.log`: 학습 및 평가 로그
- `config.yml`: 실제 실행에 사용된 config 사본
- `test/.../test_metrics.csv`: framework built-in metric 결과
- `test/.../test_results.p`: 예측/관측 요약 결과
- `test/.../test_all_output.p`: probabilistic head를 포함한 full output

논문 표와 그림을 만들 때는 이 raw artifact에서 직접 값을 가져오지 말고, `post-processing script -> tidy csv` 단계를 한 번 거친다. 그래야 built-in metric과 custom metric, event-based metric이 한 표에 일관되게 합쳐진다.

권장 산출물 이름은 아래처럼 둔다.

- `summary_metrics.csv`: basin-level 또는 overall 요약 metric
- `event_metrics.csv`: event-level flood metric 요약
- `quantile_diagnostics.csv`: coverage, calibration, pinball 요약

## 9. 현재 구현 상태

현재 저장소에서는 Model 2용 `quantile head + pinball loss`가 vendored NeuralHydrology에 이미 추가되어 있다. 따라서 즉시 재현 가능한 범위는 아래까지다.

1. `NeuralHydrology cudalstm + regression head`
2. `NeuralHydrology cudalstm + quantile head`

반면 아래 항목은 아직 custom post-processing 또는 후속 구현이 필요하다.

1. `NSElog`
2. `top 1% flow recall`
3. `event-level RMSE`
4. `coverage`
5. `calibration`
6. future-work conceptual core

## 문서 정리

이 문서는 모델 구현과 논문 Methods 서술의 `운영 기준`이다. 앞으로 split, loss, metric, config key, run artifact 규칙은 이 문서를 source of truth로 삼는다.

## 관련 문서

- [`design.md`](design.md): 연구 질문과 비교 가설
- [`architecture.md`](architecture.md): 모델 구조와 head 역할
- [`result_analysis_protocol.md`](result_analysis_protocol.md): 학습 완료 뒤 결과 비교 순서와 해석 규칙
- [`probabilistic_head_guide.md`](probabilistic_head_guide.md): quantile head 직관 설명
- [`../workflow/event_response_spec.md`](../workflow/event_response_spec.md): extreme-event 정의와 event descriptor 규칙
