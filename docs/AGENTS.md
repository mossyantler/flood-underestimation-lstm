# docs/ Agent Notes

루트 `AGENTS.md`를 먼저 따른다. 이 폴더는 연구 방법, 분석 결과, 논문/발표 해석을 정리하는 문서 공간이다.

새 작업 시작 전 문서 읽기 순서는 `docs/experiment/README.md`의 Recommended Order를 따른다.

---

## 디렉토리 구조

```text
docs/
├── experiment/                 # 현재 연구 방법·분석 문서
│   ├── method/                 # 채택한 방법과 실행 기준
│   │   ├── basin/              # DRBC holdout, training pool, screening 기준
│   │   ├── data/               # 원자료 → prepared data 처리 흐름
│   │   └── model/              # Model 1/2 구조, config, metric, 분석 protocol
│   └── analysis/               # 결과 해석 문서
│       ├── basin/              # subset 대표성, basin diagnostics
│       └── model/              # Model 1/2 결과 분석 축별 문서
├── paper/                      # 논문 proposal, defense, writing draft
├── references/                 # 외부 문헌·개념 메모
├── explain/                    # 입문자용 설명
├── templates/                  # 문서 템플릿·작성 규칙
└── archive/                    # 구식 초안 보존
```

---

## 하위 폴더 지도

| 폴더 | 역할 | canonical 지위 |
| --- | --- | --- |
| `experiment/method/` | 현재 연구에서 채택한 방법의 source of truth | **canonical** |
| `experiment/method/model/` | Model 1/2 구조, split, config, metric, 결과 분석 규칙 | **canonical** |
| `experiment/method/basin/` | DRBC holdout, training pool, screening, event candidate 기준 | **canonical** |
| `experiment/method/data/` | 원자료 → 분석 산출물 end-to-end 처리 흐름 | **canonical** |
| `experiment/analysis/model/` | Model 1/2 결과 해석 문서. 완료 문서와 예정 문서를 상태로 구분 | **canonical** |
| `experiment/analysis/basin/` | subset 대표성, basin diagnostics | canonical |
| `paper/` | 논문 proposal, defense playbook | 논문 전용 |
| `references/` | 외부 문헌 메모, glossary, 학습 노트 | 참조용 (공식 기준 아님) |
| `explain/` | 학부생/입문자용 설명 | 비공식 |
| `templates/` | 문서 작성 규칙 | 비공식 |
| `archive/` | 구식 초안 보존 | 비공식, 공식 문서로 인용 금지 |

---

## 규칙

- **canonical vs 비공식**: `experiment/method/`와 `experiment/analysis/`만 canonical이다. `references/`, `explain/`, `templates/`, `archive/`는 참조용이며 공식 기준으로 인용하지 않는다. 에이전트가 실험 결정 사항을 조회할 때 `experiment/method/` 문서를 먼저 참조한다.
- **Model 3 경계**: `experiment/method/model/` 안에 physics-guided / conceptual core 메모가 있더라도 현재 논문의 공식 비교축은 Model 1 deterministic LSTM과 Model 2 probabilistic quantile LSTM이다. Model 3 관련 내용은 future work 또는 exploratory note로만 다룬다.
- **결과 해석 문서** (`experiment/analysis/model/`): 산출물 경로, 실행 진입점, 실험 설정이 변경되면 해당 분석 문서도 함께 갱신한다. 결과가 아직 없으면 예정/계획으로 명시하고, 관찰되지 않은 결론을 쓰지 않는다.
- **method 문서 동기화**: 모델 비교축, split 기준, 실행 진입점, 산출물 경로가 바뀌면 `experiment/method/` 해당 문서를 함께 갱신한다. 루트 규칙에 따라 `README.md`, `docs/README.md`, 관련 `configs/README.md`, `scripts/README.md`, 실행 스크립트도 영향 범위에 포함되는지 확인한다.
- **구조도·workflow**: 문서 안에 작성할 때는 Mermaid를 사용한다.
- **archive**: 보존용 초안이다. 최신 공식 기준과 충돌하는 내용을 공식 문서처럼 인용하지 않는다.
