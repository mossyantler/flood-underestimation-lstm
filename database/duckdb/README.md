# CAMELS DuckDB Helper

이 폴더는 큰 CSV를 PostgreSQL에 모두 넣지 않고도 빠르게 훑기 위한 DuckDB helper를 둔다.
PostgreSQL은 반복 join과 dashboard-facing summary DB로 쓰고, DuckDB는 대형 CSV/Parquet 분석 엔진으로 쓴다.

Python package는 프로젝트 전역 dependency에 추가하지 않았다. `camels_duckdb_tool.py` 안의 PEP 723 header가 `duckdb`를 script-local dependency로 설치한다.

기본 CSV inventory와 core view를 만들려면 아래처럼 실행한다.

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run --script database/duckdb/camels_duckdb_tool.py catalog
```

기본 database file은 `database/local/duckdb/camels.duckdb`다. DBeaver에서 DuckDB connection을 만들 수 있으면 이 파일을 열어 `camels_meta.csv_inventory`와 `camels_csv.*` view를 볼 수 있다.
DuckDB는 file-based database라 write lock이 있다. DBeaver가 파일을 잡고 있을 때 `catalog`나 `views`처럼 database를 수정하는 명령이 실패하면 DBeaver connection을 잠시 끊고 다시 실행한다. `query`, `inspect`, `to-parquet`는 읽기 중심으로 동작한다.

표준 view 묶음만 갱신하려면 `views`를 실행한다.

```bash
uv run --script database/duckdb/camels_duckdb_tool.py views
```

이 명령은 core CSV view, `camels_csv.obs_timeseries`, `camels_csv.quantile_required_series`, `camels_csv.quantile_exports`, `basins/CAMELSH_data/attributes/*.csv`의 raw attribute view를 등록한다. `obs_timeseries`는 파일명에서 `gauge_id`를 파생해 붙인다. quantile 시계열 view는 `database/local/duckdb/parquet/` 아래 Parquet 변환본이 있으면 그쪽을 우선 사용하고, 없으면 원본 CSV glob을 직접 읽는다.

큰 CSV 하나를 빠르게 확인하려면:

```bash
uv run --script database/duckdb/camels_duckdb_tool.py inspect \
  output/model_analysis/overall_analysis/epoch_sensitivity/tables/basin_metrics.csv
```

명시한 CSV를 Parquet로 변환하려면:

```bash
uv run --script database/duckdb/camels_duckdb_tool.py to-parquet \
  output/model_analysis/quantile_analysis/required_series/seed111/epoch005_required_series.csv
```

기본 출력은 `database/local/duckdb/parquet/` 아래에 원래 상대 경로를 유지한 `.parquet` 파일이다. `required_series`나 `quantile_exports`처럼 100MB 이상인 시간 단위 series는 PostgreSQL typed table보다 이 방식이 더 적합하다. 디렉터리나 glob도 입력으로 줄 수 있다.

```bash
uv run --script database/duckdb/camels_duckdb_tool.py to-parquet \
  output/model_analysis/quantile_analysis/required_series \
  output/model_analysis/quantile_analysis/quantile_exports
```

DuckDB database에 만든 inventory를 SQL로 보려면:

```bash
uv run --script database/duckdb/camels_duckdb_tool.py query "
SELECT path_group, count(*) AS csv_count, round(sum(size_mb), 1) AS size_mb
FROM camels_meta.csv_inventory
GROUP BY path_group
ORDER BY size_mb DESC
LIMIT 20
"
```

## Test Result View

`catalog`는 `runs/subset_comparison/**/test/model_epoch*/test_metrics.csv`를 묶은 view도 만든다.

```sql
SELECT *
FROM camels_csv.subset300_raw_test_metrics
LIMIT 50;
```

이 view는 원본 `test_metrics.csv`를 복사하지 않고 DuckDB가 glob으로 직접 읽는다. `model`, `seed`, `epoch`, `run_name`, `metric_path`는 파일 경로에서 파싱한다.
