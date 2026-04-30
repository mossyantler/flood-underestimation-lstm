# Experiment Method

이 폴더는 현재 연구에서 실제로 채택한 방법 문서의 source of truth다.

## Areas

- [`basin/`](basin/): DRBC holdout, non-DRBC training pool, screening, event candidate, flood-generation typing
- [`data/`](data/): CAMELSH 원자료에서 split/event/model-output 분석으로 이어지는 처리 흐름
- [`model/`](model/): Model 1/2 구조, split, config, metric, checkpoint, 결과 분석 규칙

## Reading Path

1. 전체 연구 설계는 [`model/design.md`](model/design.md)
2. 모델 구조는 [`model/architecture.md`](model/architecture.md)
3. 공식 실행 규칙은 [`model/experiment_protocol.md`](model/experiment_protocol.md)
4. 결과 분석 규칙은 [`model/result_analysis_protocol.md`](model/result_analysis_protocol.md)
5. basin 정의는 [`basin/basin_cohort_definition.md`](basin/basin_cohort_definition.md)
6. event 분석 규칙은 [`basin/event_response_spec.md`](basin/event_response_spec.md)
7. 데이터 처리 흐름은 [`data/data_processing_analysis_guide.md`](data/data_processing_analysis_guide.md)

산출물 폴더 규칙은 [`basin/basin_output_layout.md`](basin/basin_output_layout.md)와 [`model/model_analysis_output_layout.md`](model/model_analysis_output_layout.md)를 따른다.
