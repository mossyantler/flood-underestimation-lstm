# CAMELS Database Helpers

이 폴더는 CAMELS 분석 산출물을 사람이 DBeaver로 보고, AI가 작은 SQL 결과만 읽도록 돕는 database 보조 계층이다.

원본 source-of-truth는 계속 `configs/`, `docs/`, `output/`에 있다. PostgreSQL과 DuckDB는 원본을 대체하지 않고, 반복 조회와 큰 CSV 탐색을 쉽게 만드는 cache로 쓴다.

## PostgreSQL

PostgreSQL은 basin/event/model-run summary처럼 반복 join과 typed table이 필요한 자료에 쓴다.

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run --script database/postgres/import_camels_csvs.py
```

기본 database 이름은 `camels`, schema 이름은 `analysis`다. 기본 import는 typed table과 `csv_files` metadata만 갱신하고, raw `jsonb` 행 저장은 `--store-raw`를 붙였을 때만 수행한다. 자세한 내용은 [`postgres/README.md`](postgres/README.md)를 본다.

## DuckDB

DuckDB는 CSV inventory, 큰 CSV ad hoc inspection, Parquet 변환에 쓴다.

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run --script database/duckdb/camels_duckdb_tool.py catalog
```

기본 DuckDB file은 `database/local/duckdb/camels.duckdb`다. 이 경로는 DBeaver DuckDB connection에서 그대로 열 수 있다. `database/local/`은 gitignore 대상이다.

`views` 명령은 core CSV view에 더해 관측 시계열, quantile 시계열, raw GAGES-II attributes view를 등록한다. quantile 시계열은 `database/local/duckdb/parquet/` 아래 변환본이 있으면 Parquet를 우선 사용하고, 없으면 원본 CSV glob을 직접 읽는다.

자세한 내용은 [`duckdb/README.md`](duckdb/README.md)를 본다.
