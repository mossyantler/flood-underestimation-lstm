# Documentation Layout

이 디렉토리는 코드와 분리해 관리하는 문서 포털이다. 루트 `README.md`가 프로젝트 개요를 다룬다면, `docs/README.md`는 문서 위치와 읽기 순서를 안내한다.

## Folder Map

```text
docs/
├── archive/                 # 과거 proposal, planning snapshot
├── templates/               # 문서 작성 규칙과 템플릿
├── references/              # 외부 문헌과 학습 노트
│   ├── basin/
│   ├── method/
│   └── analysis/
├── experiment/              # 현재 실험의 공식 방법과 분석 문서
│   ├── method/
│   │   ├── basin/
│   │   ├── data/
│   │   └── model/
│   └── analysis/
│       ├── basin/
│       └── model/
├── paper/                   # proposal, defense playbook, manuscript 재료
└── explain/                 # 학부생/입문자용 설명
```

## Main Entry Points

- [`experiment/README.md`](experiment/README.md): 현재 실험 문서의 전체 구조
- [`experiment/method/README.md`](experiment/method/README.md): basin/data/model 방법 문서의 읽기 순서
- [`experiment/method/model/experiment_protocol.md`](experiment/method/model/experiment_protocol.md): split, loss, metric, checkpoint, run artifact 규칙
- [`experiment/method/model/result_analysis_protocol.md`](experiment/method/model/result_analysis_protocol.md): Model 1/2 결과 비교와 해석 순서
- [`experiment/method/basin/event_response_spec.md`](experiment/method/basin/event_response_spec.md): hourly observed high-flow event candidate 생성 규칙
- [`experiment/analysis/model/README.md`](experiment/analysis/model/README.md): Model 1/2 분석 축별 결과 문서
- [`paper/proposal/imrad_proposal.md`](paper/proposal/imrad_proposal.md): 영문 IMRaD proposal
- [`paper/proposal/imrad_proposal_ko.md`](paper/proposal/imrad_proposal_ko.md): 한국어 IMRaD proposal
- [`paper/defense_playbook.md`](paper/defense_playbook.md): 설계 방어용 예상 질문과 답변

## Folder Roles

`experiment/method/`는 현재 프로젝트에서 실제로 채택한 방법의 source of truth다. 외부 문헌 요약이나 과거 제안서 초안은 이곳에 두지 않는다.

`experiment/analysis/`는 산출물을 해석하는 문서다. basin representativeness, model performance, checkpoint sensitivity처럼 결과를 읽는 문서는 여기에 둔다.

`references/`는 외부 문헌, 개념 정리, glossary를 보관한다. 좋은 아이디어가 공식 방법으로 승격되면 `experiment/method/`에 다시 반영한다.

`paper/`는 proposal, defense, manuscript-facing 문장을 둔다. 실행 규칙의 source of truth는 아니며, 필요하면 `experiment/method/`를 참조한다.

`explain/`은 CAMELS 연구를 처음 읽는 독자를 위한 쉬운 설명이다. 정확한 규칙보다 큰 그림과 직관을 우선한다.

에이전트 작업 맥락은 루트의 [`AGENTS.md`](../AGENTS.md)를 참조한다.
