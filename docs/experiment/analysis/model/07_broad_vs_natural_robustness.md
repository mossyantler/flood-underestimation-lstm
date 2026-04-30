# 07 Broad vs Natural Robustness 분석

## 질문

이 분석은 hydromodification risk가 적은 Natural subset에서도 Model 2 upper quantile의 paired-delta 방향이 Broad main result와 유사하게 유지되는지 확인하기 위한 robustness check다.

## 상태

예정이다. Natural split file은 준비되어 있지만, `output/model_analysis/` 아래에 Natural 전용 model-output 분석 산출물은 아직 없다. 따라서 이 문서에는 결과 해석을 쓰지 않는다.

현재 확인된 split file은 아래와 같다.

```text
configs/basin_splits/drbc_holdout_train_natural.txt
configs/basin_splits/drbc_holdout_validation_natural.txt
configs/basin_splits/drbc_holdout_test_drbc_quality_natural.txt
```

Natural DRBC test basin은 8개이고, Broad DRBC test basin 38개 안에 모두 포함된다. 따라서 가장 빠른 robustness 분석은 기존 Broad test 결과를 Natural 8개 basin으로 filter해서 paired delta를 다시 계산하는 방식이다.

## 예정 산출물

계획된 출력 위치는 아래처럼 둔다.

```text
output/model_analysis/natural_robustness/
```

예정 표는 `natural_primary_epoch_delta_summary.csv`, `natural_high_flow_delta_summary.csv`, `natural_event_regime_delta_summary.csv`다. 본문에는 Natural이 main result를 대체하지 않고 robustness subset이라는 점을 명확히 써야 한다.

## 주의점

Natural test basin이 8개뿐이므로 p-value나 강한 일반화 주장을 하기에 부족하다. 이 분석의 목적은 conclusion direction이 hydromodification-risk filtering에 의해 완전히 뒤집히지 않는지 확인하는 것이다.
