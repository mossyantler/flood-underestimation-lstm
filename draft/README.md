# Paper Docs

이 폴더는 논문 proposal, defense playbook, manuscript-facing 문장, Notion 전환 후 frozen export를 둔다. 실행 규칙의 source of truth는 [`../docs/experiment/method/`](../docs/experiment/method/)다.

## Notion draft

Active Notion database: [Draft](https://www.notion.so/bf6bf4959ffa41a18b06856c25d8be47)

| Notion page | Repo source |
| --- | --- |
| [LATEST - paper_draft.html](https://www.notion.so/3716d0284c1681a990f7c28eee267145) | `draft/github_io/paper_draft.html` |
| [v1_original](https://www.notion.so/3716d0284c168189bebde6cfe56863bf) | `draft/github_io/versions/v1_original.html` |
| [v2_expanded](https://www.notion.so/3716d0284c168178b1e5ffc512502677) | `draft/github_io/versions/v2_expanded.html` |
| [v3_current_docx](https://www.notion.so/3716d0284c16815b9d3ed67d5b791fb9) | `draft/github_io/versions/v3_current_docx.html` |
| [v4_pre_review_update](https://www.notion.so/3716d0284c16819782ded0b471ad7fe3) | `draft/github_io/versions/v4_pre_review_update.html` |

각 draft는 `Draft` database의 row page 본문에 들어 있다. database 행을 열면 바로 독립 논문 페이지를 수정할 수 있다. Notion 운영 규칙은 `AGENTS.md`와 `CLAUDE.md`를 따른다.

## Contents

- [`proposal/imrad_proposal.md`](proposal/imrad_proposal.md): 영문 IMRaD proposal
- [`proposal/imrad_proposal_ko.md`](proposal/imrad_proposal_ko.md): 한국어 IMRaD proposal
- [`defense_playbook.md`](defense_playbook.md): 예상 질문, 취약점, 방어 논리
- [`github_io/`](github_io/): legacy GitHub Pages HTML draft archive
- [`notion_exports/`](notion_exports/): Notion frozen version export archive

Proposal이나 defense 문장을 고칠 때는 먼저 [`../docs/experiment/method/model/experiment_protocol.md`](../docs/experiment/method/model/experiment_protocol.md)와 [`../docs/experiment/method/model/result_analysis_protocol.md`](../docs/experiment/method/model/result_analysis_protocol.md)의 공식 설정과 충돌하지 않는지 확인한다.
