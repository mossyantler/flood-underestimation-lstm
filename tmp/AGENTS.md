# tmp/ Agent Notes

루트 `AGENTS.md`를 먼저 따른다. 이 폴더는 scratch, staging, 임시 다운로드/중간 파일을 두는 gitignored 공간이다.

---

## 디렉토리 구조

```text
tmp/
├── *_smoke/                 # smoke test와 negative control 산출물
├── *_check/                 # catalog, runner, data integrity 임시 점검
├── lit_extract/             # 문헌/PDF 추출 staging
├── pdf_extract/             # PDF 추출 staging
├── pdf_text/                # PDF text extraction 임시 결과
└── reference_text/          # 외부 reference text staging
```

`tmp/`의 하위 폴더는 오래 유지되는 API가 아니다. 새 작업은 목적이 드러나는 폴더명을 만들고, 보존할 결과는 `output/`이나 `docs/`의 적절한 위치로 옮긴다.

---

## 구성 규칙

- `tmp/`의 파일은 canonical 산출물이 아니다. 보존해야 하는 결과는 `output/`의 적절한 `tables/`, `figures/`, `metadata/`로 옮긴다.
- 사용자가 만든 임시 파일을 임의로 삭제하지 않는다. 정리가 필요하면 내가 만든 파일인지 확인한다.
- 대용량 다운로드, 압축 해제, 변환 staging은 이곳을 우선 사용한다.
- 재현성에 필요한 중간 처리 규칙은 tmp 파일이 아니라 script와 metadata에 남긴다.
