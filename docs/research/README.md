# Research Docs

이 폴더는 연구 질문, 모델 구조, 실험 규범을 정리한다. canonical 문서가 비교 실험의 source of truth이고, support 문서는 설명과 검토를 보강한다.

## Structure

```mermaid
flowchart TD
    A[research/README.md] --> B[design.md<br/>research question and comparison]
    B --> C[literature_review.md<br/>related work map]
    B --> D[architecture.md<br/>model structure]
    D --> E[experiment_protocol.md<br/>execution rules]
    D -. support .-> F[probabilistic_head_guide.md]
    B -. support .-> G[defense_playbook.md]
```

## Canonical docs

| Document | Role |
| --- | --- |
| [`design.md`](design.md) | 연구 질문, 비교축, 평가 방향을 정리한다. |
| [`architecture.md`](architecture.md) | Model 1, Model 2, Model 3 구조를 구분한다. |
| [`experiment_protocol.md`](experiment_protocol.md) | split, loss, metric, config 규칙을 고정한다. |
| [`literature_review.md`](literature_review.md) | related work의 축과 인용 방향을 정리한다. |

## Support docs

| Document | Role |
| --- | --- |
| [`probabilistic_head_guide.md`](probabilistic_head_guide.md) | probabilistic head의 직관을 설명한다. |
| [`defense_playbook.md`](defense_playbook.md) | 예상 질문과 취약 지점을 점검한다. |

## Recommended order

1. [`design.md`](design.md)
2. [`literature_review.md`](literature_review.md)
3. [`architecture.md`](architecture.md)
4. [`experiment_protocol.md`](experiment_protocol.md)
5. 필요할 때 [`probabilistic_head_guide.md`](probabilistic_head_guide.md)
6. 방어 논리 점검이 필요할 때 [`defense_playbook.md`](defense_playbook.md)
