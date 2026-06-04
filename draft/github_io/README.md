# Legacy GitHub Pages Draft Archive

이 폴더는 Notion 전환 이전에 사용한 GitHub Pages 기반 논문 draft archive다.

## 보존 기준

- `index.html`, `paper_draft.html`, `versions/*.html`은 과거 HTML snapshot으로 유지한다.
- 새 논문 version을 만들기 위해 기존 HTML 파일을 덮어쓰지 않는다.
- 새 frozen draft export는 `../notion_exports/<version>_<YYYY-MM-DD>/`에 저장한다.
- 이 폴더의 `figures/`와 `docx_images/`는 과거 HTML 재현용 asset이다. 최신 논문 figure의 source-of-truth는 `output/` 또는 관련 생성 script에서 확인한다.

## 전환 기준

Notion [Draft](https://www.notion.so/bf6bf4959ffa41a18b06856c25d8be47)는 논문 draft 확인 및 수정 공간이고, 이 폴더는 legacy archive다. 2026-05-31 기준 `paper_draft.html`과 `versions/*.html`은 `Draft` database의 row page 본문으로 이식했다. 실험 설정과 결과 해석의 canonical 기준은 `docs/experiment/`와 `output/`에 둔다.
