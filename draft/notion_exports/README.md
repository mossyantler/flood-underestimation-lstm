# Notion Frozen Draft Export Archive

이 폴더는 Notion에서 freeze한 논문 draft version의 export snapshot을 저장한다.

Active Notion database: [Draft](https://www.notion.so/bf6bf4959ffa41a18b06856c25d8be47)

## 폴더 규칙

각 version은 별도 하위 폴더에 저장한다.

```text
draft/notion_exports/
├── v5_2026-05-31/
│   ├── README.md
│   ├── manuscript.pdf
│   ├── manuscript.html
│   └── manuscript.docx
└── submission_2026-06-xx/
    ├── README.md
    └── ...
```

## Version README template

각 export folder의 `README.md`에는 아래 항목을 기록한다.

```markdown
# <version> Notion export

- Notion page:
- Export date:
- Status: frozen | submitted
- Base source:
- Canonical basis:
  - docs/experiment/...
  - output/...
- Figure/table snapshot:
- Notes:
```

## 금지 사항

- 새 version을 기존 folder에 덮어쓰지 않는다.
- `draft/github_io/index.html` 또는 `draft/github_io/paper_draft.html`을 새 draft 공유용으로 재사용하지 않는다.
- Notion에 붙인 이미지·표를 원본 figure/table로 간주하지 않는다.
