# Experiment Protocol

## 서술 목적

이 문서는 모델 실험의 `실행 규범`을 묶은 기준 문서다. 즉 어떤 split을 만들고, 어떤 config key를 쓰고, loss와 metric을 어떻게 계산할지를 정리한다. 현재 논문의 공식 프로토콜은 Model 1과 Model 2에만 적용한다.

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

현재 논문의 공식 비교 축은 아래 두 모델이다.

| 모델 | 목적 | 기본 config 방향 |
| --- | --- | --- |
| Model 1 | deterministic baseline | `model: cudalstm`, `head: regression`, `loss: nse` |
| Model 2 | output design 효과 검증 | `model: cudalstm`, `head: quantile`, `loss: pinball` |

핵심 원칙은 `backbone은 고정하고, head와 loss만 비교축에 맞게 바꾼다`는 점이다. 그래야 Model 1 대비 Model 2의 개선을 `tail-aware output`의 효과로 해석할 수 있다.

Model 3 physics-guided probabilistic hybrid는 저장소에 남겨 두지만, 현재 논문의 공식 프로토콜 대상은 아니다. 따라서 이 문서의 normative rule은 Model 1과 Model 2에만 적용한다.

## 2. 공통 데이터 규칙

모든 공식 비교 실험은 `hourly streamflow prediction`을 대상으로 한다. 입력은 `dynamic forcing + static attributes`이고, 기본 입력 집합은 아래를 권장한다.

- Dynamic forcing: `prcp`, `tmax`, `tmin`, `srad`, `vp`, 필요 시 `PET`
- Static attributes: `area`, `slope`, `aridity`, `snow fraction`, `soil depth`, `permeability`, `forest fraction`, `baseflow index`

`lagged Q`는 현재 baseline 비교축에서는 쓰지 않는다. lagged observation이 들어가면 deterministic baseline이 과하게 강해지고, probabilistic head의 순수 효과를 분리하기 어렵기 때문이다.

## 3. Split 생성 규칙

Model 1과 Model 2는 같은 split 정의를 공유해야 한다. 같은 split에서 backbone과 input 구성을 유지한 채 head만 달라져야 비교가 성립한다.

### 3.1 Temporal split

Temporal split은 `같은 basin, 다른 시기`를 평가하는 기본 split이다. 구현에서는 같은 basin file을 쓰고, `train_start_date`, `train_end_date`, `validation_start_date`, `validation_end_date`, `test_start_date`, `test_end_date`를 시간축으로만 나눈다.

핵심 규칙은 다음과 같다.

1. train, validation, test 기간은 시간적으로 겹치지 않아야 한다.
2. 같은 basin 집합을 사용하되, 날짜 경계만 달라야 한다.
3. Model 1과 Model 2는 동일한 basin file과 동일한 날짜 경계를 재사용한다.

이 split은 `same-basin / different-time` 일반화를 확인하는 기준선 역할을 한다.

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

요약 수치는 [`../../output/basin/splits/drbc_holdout/drbc_holdout_split_summary.json`](../../output/basin/splits/drbc_holdout/drbc_holdout_split_summary.json)에 정리한다.

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

여기서 `q50`은 중심선이고, `q90`, `q95`, `q99`는 upper-tail 응답을 직접 학습한다. 현재 vendored NeuralHydrology 구현은 quantile crossing을 막기 위해 상위 quantile을 `positive increment` 구조로 만든다. 즉 \(q_{50} \le q_{90} \le q_{95} \le q_{99}\)가 자동으로 유지된다.

기본 loss는 weighted pinball loss다.

$$
L = \sum_k w_k \, \operatorname{Pinball}(y, q_{\tau_k})
$$

첫 비교 실험에서는 `quantile_loss_weights`를 동일 가중치로 두고, 필요하면 tail-emphasized ablation을 별도로 둔다. 그래야 `head 구조의 효과`와 `가중치 조정 효과`를 섞지 않는다.

### 4.3 후속 연구 메모

Model 3를 후속으로 확장한다면, Model 2의 probabilistic loss 위에 conceptual core 관련 regularization을 추가하는 방향이 자연스럽다.

$$
L_{\text{total}} = L_{\text{prob}} + \lambda_{\text{mass}} L_{\text{mass\_balance}} + \lambda_{\text{nonneg}} L_{\text{nonnegativity}} + \lambda_{\text{bound}} L_{\text{storage\_bounds}}
$$

다만 이 식은 현재 논문의 공식 프로토콜이 아니다. `physics regularization term`, `state variable schema`, `bounded coefficient definition`이 확정되면 별도 follow-up protocol 문서로 다루는 것이 맞다.

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
6. `Model 3 physics-guided hybrid follow-up`

## 문서 정리

이 문서는 현재 논문 범위의 모델 구현과 Methods 서술의 `운영 기준`이다. 앞으로 split, loss, metric, config key, run artifact 규칙은 Model 1과 Model 2 비교에 대해 이 문서를 source of truth로 삼는다.

## 관련 문서

- [`design.md`](design.md): 연구 질문과 비교 가설
- [`architecture.md`](architecture.md): 모델 구조와 head 역할
- [`probabilistic_head_guide.md`](probabilistic_head_guide.md): quantile head 직관 설명
- [`../workflow/event_response_spec.md`](../workflow/event_response_spec.md): extreme-event 정의와 event descriptor 규칙
