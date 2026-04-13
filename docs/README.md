# CAMELS Docs

이 문서는 저장소 문서 체계의 기준 포털이다. 사람용 문서는 루트 `README.md`와 이 문서에서 시작한다. 각 폴더의 `README.md`는 폴더 안에서만 쓰는 로컬 인덱스다.

## Docs taxonomy

```mermaid
flowchart TD
    A["docs/README.md<br/>canonical docs portal"]

    A --> B["workflow/"]
    A --> C["research/"]
    A --> D["references/"]
    A --> E["meta/"]

    B --> B1["Canonical<br/>basin_cohort_definition.md<br/>basin_analysis.md<br/>basin_screening_method.md<br/>event_response_spec.md<br/>flood_generation_typing.md"]
    B --> B2["Support<br/>basin_source_csv_guide.md"]

    C --> C1["Canonical<br/>design.md<br/>architecture.md<br/>experiment_protocol.md<br/>literature_review.md"]
    C --> C2["Support<br/>probabilistic_head_guide.md<br/>defense_playbook.md"]

    D --> D1["Support references<br/>lstm_hydrology_study_notes.md<br/>lstm_hydrology_study_notes_beginner.md<br/>river_basin_analysis_study_guide.md"]

    E --> E1["Support meta<br/>writing_guide.md"]
```

## Canonical vs support

공식 규칙, 정의, 실험 기준은 canonical 문서에만 둔다. guide, playbook, study note, writing guide는 support 문서다. support 문서는 설명과 배경을 보강하지만 source of truth가 되지 않는다.

| Area | Role | Local index |
| --- | --- | --- |
| [`workflow/`](workflow/README.md) | basin selection, screening, event workflow의 공식 기준 | [`workflow/README.md`](workflow/README.md) |
| [`research/`](research/README.md) | 연구 질문, 모델 구조, 실험 규범의 공식 기준 | [`research/README.md`](research/README.md) |
| [`references/`](references/README.md) | 외부 자료를 CAMELS 맥락으로 옮긴 참고 노트 | [`references/README.md`](references/README.md) |
| [`meta/`](meta/README.md) | 문서 작성 규칙과 contributor guidance | [`meta/README.md`](meta/README.md) |

## Recommended reading paths

```mermaid
flowchart TD
    A["README.md"] --> B["docs/README.md"]

    B --> W0["workflow path"]
    W0 --> W1["workflow/README.md"]
    W1 --> W2["basin_cohort_definition.md"]
    W2 --> W3["basin_analysis.md"]
    W3 --> W4["basin_screening_method.md"]
    W4 --> W5["event_response_spec.md"]
    W5 --> W6["flood_generation_typing.md"]
    W2 -. support when needed .-> WS["basin_source_csv_guide.md"]

    B --> R0["research path"]
    R0 --> R1["research/README.md"]
    R1 --> R2["design.md"]
    R2 --> R3["literature_review.md"]
    R2 --> R4["architecture.md"]
    R4 --> R5["experiment_protocol.md"]
    R4 -. support when needed .-> RS1["probabilistic_head_guide.md"]
    R2 -. stress test .-> RS2["defense_playbook.md"]

    B --> X0["background path"]
    X0 --> X1["references/README.md"]
    X1 --> X2["lstm_hydrology_study_notes_beginner.md"]
    X2 --> X3["lstm_hydrology_study_notes.md"]
    X1 --> X4["river_basin_analysis_study_guide.md"]

    B --> M0["contributor path"]
    M0 --> M1["meta/README.md"]
    M1 --> M2["writing_guide.md"]
```

## Folder indexes

- [`workflow/README.md`](workflow/README.md): workflow 문서의 관계와 읽기 순서를 정리한다.
- [`research/README.md`](research/README.md): research 문서의 기준선과 support 문서를 정리한다.
- [`references/README.md`](references/README.md): 참고 노트의 역할과 읽기 순서를 정리한다.
- [`meta/README.md`](meta/README.md): 문서 작성 규칙과 메타 문서를 정리한다.
