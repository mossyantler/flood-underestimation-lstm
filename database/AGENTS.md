# database/ Agent Notes

루트 `AGENTS.md`를 먼저 따른다. 이 폴더는 CAMELS 분석 산출물을 PostgreSQL과 DuckDB에서 재사용하기 위한 schema, import helper, database-local cache 규칙을 둔다.

---

## 역할

- `postgres/`: 반복 조회, join, DBeaver grid 확인, dashboard backend 후보에 쓰는 PostgreSQL schema와 CSV import helper를 둔다.
- `duckdb/`: 큰 CSV inventory, ad hoc SQL inspection, Parquet 변환 helper를 둔다.
- `local/`: `.duckdb`, Parquet export 같은 로컬 생성 database artifact를 둔다. 이 폴더는 gitignore 대상이며 canonical source가 아니다.

## 원칙

- 원본 source-of-truth는 계속 `configs/`, `docs/`, `output/`의 CSV/JSON/Markdown이다. database는 분석 cache와 조회 편의 계층으로만 취급한다.
- `database/local/`의 생성물은 직접 커밋하지 않는다. 보존해야 하는 해석 결과는 `output/` 또는 `docs/`에 별도로 남긴다.
- PostgreSQL에는 basin/event/model-run summary처럼 반복 join이 필요한 typed table을 우선 둔다.
- DuckDB/Parquet는 `required_series`, `quantile_exports`처럼 큰 시간 단위 CSV를 빠르게 훑거나 columnar format으로 바꾸는 용도에 둔다.
- macOS 로컬에서 실행할 때는 `export PATH="/opt/homebrew/bin:$PATH"`를 먼저 적용한다.
