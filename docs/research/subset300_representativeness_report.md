# Subset300 Representativeness Report

## 목적

이 문서는 현재 compute-constrained main comparison에서 사용하는 `scaling_300` subset이 prepared non-DRBC executable pool을 얼마나 잘 대표하는지 해석하고, 왜 이 subset을 seed `111 / 222 / 333`의 Model 1 / Model 2에 공통으로 고정해도 되는지를 기록한다.

핵심 질문은 두 가지다.

1. `scaling_300`이 prepared pool의 `static attribute` 분포를 충분히 보존하는가.
2. `scaling_300`이 prepared pool의 `observed-flow event-response` 분포를 충분히 보존하는가.

이 문서는 `공식 basin-count 선택 결과를 해석하는 보고서`이지, DRBC holdout test metric 기반의 모델 우열 보고서가 아니다.

## 선행연구 맥락

large-sample neural hydrology의 주류 논문들은 보통 `대표 subset을 새로 뽑고 검증`하는 구조를 쓰지 않는다. 대신 먼저 curated benchmark set을 만들고, 이후 모델 논문들은 그 고정 benchmark를 그대로 재사용한다.

예를 들어 Newman et al. (2015)는 CONUS `671`개 unimpaired basin을 community dataset과 benchmark로 제시했고, Addor et al. (2017)는 같은 `671`개 basin에 정적 catchment attribute를 붙여 CAMELS benchmark를 완성했다. Kratzert et al. (2019)는 그중 `531` basin을 사용해 단일 LSTM benchmark를 제시했고, Klotz et al. (2022)는 같은 `531` basin을 uncertainty benchmark에 그대로 재사용했다. 즉 이 계열 논문에서 공정성의 핵심은 `새 subset 최적화`보다 `고정 benchmark 재사용`에 있다.

반대로 compute 제약 때문에 subset을 직접 뽑아야 하는 경우에는 hydrology ML보다 `environmental sampling` 문헌이 더 직접적인 방법론을 준다. Minasny and McBratney (2006)의 conditioned Latin hypercube sampling(cLHS)은 `표본이 공변량의 multivariate distribution을 최대한 stratify하도록` 설계하자는 접근이고, 실무적으로는 `marginal distribution`과 `correlation structure`를 함께 보존하는 방향으로 읽는다.

현재 `subset300` 방법은 이 둘을 절충한 구조로 이해하는 것이 맞다. 즉 `benchmark-first` 원칙에 따라 한 번 고른 subset을 모든 seed와 모델에 고정하고, subset 생성 자체는 `HUC02 stratification + covariate / event-response balance + random same-size subset benchmark`로 방어하는 방식이다.

## 분석 대상과 입력 산출물

현재 기준 pool과 subset은 아래처럼 고정한다.

- prepared non-DRBC executable pool: `1903` basin
- adopted subset: `300` basin
- adopted subset split: train `269`, validation `31`
- regional holdout test basin: `38`

분석에 사용한 입력 산출물은 아래와 같다.

- prepared pool manifest: [`../../configs/pilot/basin_splits/prepared_pool_manifest.csv`](../../configs/pilot/basin_splits/prepared_pool_manifest.csv)
- adopted subset manifest: [`../../configs/pilot/basin_splits/scaling_300/manifest.csv`](../../configs/pilot/basin_splits/scaling_300/manifest.csv)
- static diagnostics summary: [`../../configs/pilot/diagnostics/attribute_distribution_scope_summary.csv`](../../configs/pilot/diagnostics/attribute_distribution_scope_summary.csv)
- event-response diagnostics summary: [`../../configs/pilot/diagnostics/event_response/event_response_scope_summary.csv`](../../configs/pilot/diagnostics/event_response/event_response_scope_summary.csv)
- random same-size subset benchmark: [`../../configs/pilot/diagnostics/permutation_benchmark/subset300_random_benchmark_summary.csv`](../../configs/pilot/diagnostics/permutation_benchmark/subset300_random_benchmark_summary.csv)

`event-response` 요약은 hourly prepared time series에서 basin별 `annual_peak_unit_area_median`, `q99_event_frequency`, `rbi`, `unit_area_peak_median`, `rising_time_median_hours`, `event_duration_median_hours`, `event_count`, `annual_peak_years`를 계산해 비교했다.

## 판단 기준

이 보고서에서는 `standardized mean difference (SMD)`를 대표성의 1차 지표로 사용한다. 값이 작을수록 prepared pool과 subset의 차이가 작다. 본 프로젝트에서는 운영 판단용으로 아래처럼 읽는다.

- `max abs SMD < 0.10`: 매우 양호
- `0.10 <= max abs SMD < 0.25`: 허용 가능하나 해석 주의
- `>= 0.25`: representativeness risk가 큼

다만 SMD만으로는 “이 subset이 random하게 뽑은 300개보다 실제로 더 나은가”를 말하기 어렵다. 그래서 prepared pool에서 같은 split 크기(`269/31`)를 유지한 random subset을 `200회` 반복 추출해 benchmark 분포를 만들었다. 여기서는 `lower_tail_percentile`이 낮을수록 현재 adopted subset이 random subset들보다 mismatch가 더 작다는 뜻이다.

이 benchmark는 `formal null-hypothesis significance test`라기보다, 현재 adopted subset의 상대적 품질을 읽기 위한 `operational permutation benchmark`다.

또한 본 프로젝트는 cLHS의 아이디어를 참고하되, 그 알고리즘 자체를 직접 구현한 것은 아니다. 즉 현재 방법은 `cLHS-style representativeness audit`에 가깝고, 엄밀한 의미의 `cLHS-optimized subset`이라고 부르지는 않는다.

## 결과 요약

결론부터 말하면, 현재 `scaling_300`은 `static attribute`와 `observed-flow event-response`를 모두 크게 훼손하지 않았고, 특히 `validation split`과 `event-response` 축에서 random same-size subset보다 뚜렷하게 더 좋은 편이다. 따라서 현재 compute-constrained main comparison에서 이 subset을 고정하는 결정은 방어 가능하다.

다만 이 결론은 `300이 가능한 모든 300개 subset 중 최적`이라는 뜻은 아니다. 더 정확한 표현은 `prepared pool을 충분히 잘 대표하는 고정 subset이며, random 같은 크기 subset과 비교해도 약하지 않다`는 것이다.

## 1. Static Attribute Diagnostics

static attribute 진단 결과는 아래처럼 읽는다.

| Scope | Max abs SMD | Mean abs SMD | 해석 |
| --- | ---: | ---: | --- |
| combined | `0.0709` | `0.0467` | 전체적으로 양호 |
| train | `0.0719` | `0.0503` | 전체적으로 양호 |
| validation | `0.1417` | `0.0334` | worst attribute 하나는 약간 벌어지지만 평균적으로는 안정적 |

핵심은 validation에서 `soil_depth`가 `0.1417`로 `0.10`을 넘었다는 점이다. 따라서 static 관점에서 `완벽한 분포 보존`이라고 말할 수는 없다. 반면 다른 값들은 전반적으로 작고, mean abs SMD는 validation에서 오히려 낮다. 즉 validation split에 `특정 attribute 하나의 localized imbalance`는 있지만, split 전체가 무너진 상태는 아니다.

## 2. Observed-Flow Event-Response Diagnostics

event-response 진단 결과는 static보다 더 강하다.

| Scope | Max abs SMD | Mean abs SMD | 0.10 초과 metric 수 | 해석 |
| --- | ---: | ---: | ---: | --- |
| combined | `0.0584` | `0.0283` | `0` | 매우 양호 |
| train | `0.0567` | `0.0301` | `0` | 매우 양호 |
| validation | `0.0891` | `0.0492` | `0` | 매우 양호 |

중요한 점은 `validation`에서도 모든 event-response metric이 `0.10` 아래라는 점이다. 즉 현재 adopted subset은 prepared pool 대비 `high-flow frequency`, `flashiness`, `peak magnitude`, `event shape` 같은 동적 수문 반응을 꽤 잘 보존한다. 본 프로젝트가 flood underestimation에 초점을 둔다는 점을 고려하면, 이 축의 안정성이 static보다 더 중요하다.

## 3. Random Same-Size Subset Benchmark

`200회` random subset benchmark는 현재 adopted subset이 단순히 “나쁘지 않다”를 넘어, 같은 크기의 random subset들보다도 대체로 더 낫다는 점을 보여준다.

### 3.1 Event-Response Benchmark

event-response mismatch는 random subset 대비 분명히 강하다.

| Scope | Statistic | Actual | Random median | Random p95 | Random 대비 더 좋은 비율 |
| --- | --- | ---: | ---: | ---: | ---: |
| combined | max abs SMD | `0.0584` | `0.0760` | `0.1407` | `80.0%` |
| combined | mean abs SMD | `0.0283` | `0.0385` | `0.0754` | `78.5%` |
| train | max abs SMD | `0.0567` | `0.0810` | `0.1509` | `85.5%` |
| train | mean abs SMD | `0.0301` | `0.0414` | `0.0801` | `78.5%` |
| validation | max abs SMD | `0.0891` | `0.2589` | `0.4301` | `96.5%` |
| validation | mean abs SMD | `0.0492` | `0.1229` | `0.2274` | `97.5%` |

특히 validation event-response mismatch는 random subset의 거의 대부분보다 작다. 이건 단순히 “허용 가능” 수준이 아니라, 현재 adopted subset이 validation basin에서 동적 flood-response 분포를 상당히 잘 보존했다는 강한 신호다.

### 3.2 Static Benchmark

static benchmark는 조금 더 혼합적이다.

| Scope | Statistic | Actual | Random median | Random p95 | Random 대비 더 좋은 비율 |
| --- | --- | ---: | ---: | ---: | ---: |
| combined | max abs SMD | `0.0709` | `0.0899` | `0.1355` | `76.5%` |
| combined | mean abs SMD | `0.0467` | `0.0416` | `0.0663` | `35.5%` |
| train | max abs SMD | `0.0719` | `0.0909` | `0.1467` | `80.5%` |
| train | mean abs SMD | `0.0503` | `0.0431` | `0.0731` | `29.5%` |
| validation | max abs SMD | `0.1417` | `0.2684` | `0.4146` | `94.5%` |
| validation | mean abs SMD | `0.0334` | `0.1256` | `0.2045` | `100.0%` |

해석은 두 층으로 나눠야 한다.

첫째, `max abs SMD`와 validation mismatch 기준으로는 현재 subset이 random subset보다 분명히 더 낫다. 특히 validation은 static 쪽도 random 대비 훨씬 잘 matched됐다.

둘째, `combined/train mean abs SMD` 기준으로는 현재 subset이 random median보다 약간 불리하다. 즉 현재 subset이 static balance의 모든 집계 방식에서 random보다 우월한 것은 아니다.

이 차이는 중요한 caveat다. 따라서 현재 subset을 `globally optimal static subset`이라고 부르면 과장이고, `validation과 dynamic flood-response 보존을 포함해 전체적으로 강한 compute-constrained subset`이라고 부르는 것이 맞다.

## 4. Operational Confidence

현재 `subset300 고정` 결정에 대한 판단 신뢰도는 `moderate-to-high` 또는 한국어로 `중상`이 적절하다.

이렇게 판단한 이유는 아래와 같다.

1. static diagnostics만 본 것이 아니라, flood 연구에 더 직접적인 observed-flow event-response diagnostics까지 포함했다.
2. event-response SMD가 `combined/train/validation` 전 범위에서 `0.10` 아래였다.
3. random same-size subset benchmark에서도 event-response와 validation split mismatch가 random subset의 대다수보다 작았다.
4. 다만 static `combined/train mean abs SMD`는 random median보다 더 좋다고 말할 수 없어서, `매우 높음`까지 올리기는 어렵다.

즉 현재 결정은 `임시 편의 선택`은 아니고, `충분한 대표성 근거를 갖춘 운영적 고정 결정`으로 보는 것이 맞다.

## 5. 권고 해석

현재 본 실험에서는 아래처럼 서술하는 것이 가장 안전하다.

`The compute-constrained main comparison uses a fixed HUC02-stratified subset of 300 non-DRBC basins. This subset was selected using deterministic pilot validation performance, static attribute balance, observed-flow event-response balance, and a random same-size subset benchmark, rather than DRBC holdout test performance.`

한국어로는 아래처럼 정리할 수 있다.

`현재 본 실험은 prepared non-DRBC pool 전체를 직접 학습하지 않고, representative audit을 거쳐 고정한 scaling_300 subset을 사용한다. 이 subset은 non-DRBC validation 성능, static attribute diagnostics, observed-flow event-response diagnostics, random same-size subset benchmark, compute cost를 함께 보고 채택했다.`

## 6. 운영 결정

이 보고서를 기준으로 현재 운영 결정은 아래처럼 고정한다.

1. 현재 `scaling_300` subset을 compute-constrained main comparison의 공식 train/validation basin file로 유지한다.
2. 이미 완료된 seed `111`의 Model 1 / Model 2 run은 유효한 본 실험 산출물로 유지한다.
3. 남은 seed `222`, `333`의 Model 1 / Model 2는 같은 subset을 그대로 재사용한다.
4. 이후 성능 해석은 `subset300 main comparison`으로 따로 부르고, broad prepared split 전체와는 구분해 기록한다.

공식 실행 진입점은 [`../../scripts/official/run_subset300_multiseed.sh`](../../scripts/official/run_subset300_multiseed.sh)다.

이 운영 결정은 선행연구 맥락과도 맞는다. 즉 이후 Model 1 / Model 2의 seed 비교에서는 subset을 다시 흔들지 않고, 고정된 benchmark cohort를 유지하는 것이 더 타당하다.

## 7. 남은 Caveat

이 보고서가 있어도 아래 주장은 피하는 것이 좋다.

- `300이 전국 prepared pool을 완벽하게 대표한다`
- `300이 모든 가능한 300개 subset 중 최적이다`
- `formal significance test로 subset optimality가 증명됐다`

대신 아래처럼 말하는 것이 적절하다.

- `300은 compute-constrained main comparison에 충분히 적합한 representative subset이다`
- `300은 random same-size subset보다 대체로 더 잘 matched됐다`
- `근거는 특히 validation split과 observed-flow event-response 축에서 강하다`

## 관련 산출물

- [`../../configs/pilot/diagnostics/attribute_distribution_scope_summary.csv`](../../configs/pilot/diagnostics/attribute_distribution_scope_summary.csv)
- [`../../configs/pilot/diagnostics/event_response/event_response_scope_summary.csv`](../../configs/pilot/diagnostics/event_response/event_response_scope_summary.csv)
- [`../../configs/pilot/diagnostics/permutation_benchmark/subset300_random_benchmark_summary.csv`](../../configs/pilot/diagnostics/permutation_benchmark/subset300_random_benchmark_summary.csv)
- [`../../configs/pilot/diagnostics/permutation_benchmark/subset300_random_benchmark_summary.json`](../../configs/pilot/diagnostics/permutation_benchmark/subset300_random_benchmark_summary.json)
- [`../../scripts/pilot/build_scaling_pilot_event_response_diagnostics.py`](../../scripts/pilot/build_scaling_pilot_event_response_diagnostics.py)
- [`../../scripts/pilot/build_scaling_pilot_random_subset_benchmark.py`](../../scripts/pilot/build_scaling_pilot_random_subset_benchmark.py)
