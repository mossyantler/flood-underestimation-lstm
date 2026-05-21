# CAMELS PostgreSQL Analysis Cache

이 폴더는 CAMELS CSV 산출물을 PostgreSQL에서 빠르게 조회하기 위한 로컬 분석 cache를 만든다.
`configs/`, `docs/`, `output/`의 기존 파일이 계속 source-of-truth이고, PostgreSQL은 반복 질문과 join을 줄이기 위한 보조 색인으로만 쓴다.

초기화와 기본 CSV import는 아래처럼 실행한다.

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run --script database/postgres/import_camels_csvs.py
```

기본 database 이름은 `camels`이고, schema 이름은 `analysis`다. import helper는 database가 없으면 만들고, `analysis.csv_files`에 원본 CSV metadata를 등록한다. `analysis.csv_rows`의 raw `jsonb` 행 저장은 기본으로 꺼져 있으며, 원본 행 단위 보관이 필요할 때만 `--store-raw`를 붙인다.

현재 typed table은 다음과 같다.

- `analysis.basin_membership`: DRBC 38개 basin의 broad/natural cohort membership.
- `analysis.basin_metrics`: subset300 epoch sensitivity의 basin-level `NSE`, `KGE`, `FHV`, `Peak-Timing`, `Peak-MAPE`.
- `analysis.primary_epoch_basin_deltas`: primary epoch의 paired-seed Model 2 minus Model 1 basin delta.
- `analysis.extreme_rain_events`: primary extreme-rain event catalog의 event-level 핵심 metadata.
- `analysis.basin_static_attributes`: prepared CAMELSH generic dataset의 basin static attributes.
- `analysis.basin_flood_generation`: basin별 flood generation type 요약.
- `analysis.basin_event_response`: basin별 high-flow event response와 ARI proxy 요약.
- `analysis.basin_event_regime`: basin별 event-regime cluster/map label 요약.
- `analysis.probabilistic_pinball`: probabilistic diagnostics의 quantile pinball summary.
- `analysis.probabilistic_calibration`: probabilistic diagnostics의 quantile calibration summary.
- `analysis.probabilistic_tail_spread`: probabilistic diagnostics의 upper-tail spread summary.

핵심 typed table은 source file을 감사용 `source_path`로 남기지만 primary key에는 경로를 넣지 않는다. 경로 이동으로 같은 실험 결과가 중복 적재되는 것을 막기 위해 `basin_metrics`는 `(model, seed, split, epoch, basin)`, `primary_epoch_basin_deltas`는 `(seed, basin)`, `extreme_rain_events`는 `(gauge_id, event_id)`를 key로 쓴다.

Typed importer는 현재 import하는 `source_path`의 기존 행만 지운 뒤 staging table에서 `ON CONFLICT` upsert를 수행한다. 그래서 같은 typed table에 다른 source의 disjoint row가 있으면 보존되고, natural key가 겹치면 현재 import한 CSV 값과 `source_path`가 최신값으로 덮인다.

예시 조회:

```bash
psql -d camels -c "
SELECT model, split, count(*) AS rows, round(avg(nse)::numeric, 3) AS mean_nse
FROM analysis.basin_metrics
GROUP BY model, split
ORDER BY model, split;
"
```

cohort까지 붙여 보려면 view를 사용한다.

```bash
psql -d camels -c "
SELECT exclusive_cohort, round(avg(delta_nse)::numeric, 3) AS mean_delta_nse
FROM analysis.primary_epoch_deltas_with_cohort
GROUP BY exclusive_cohort
ORDER BY exclusive_cohort;
"
```

새 CSV를 일단 원본 행 단위로만 등록하고 싶을 때는 path를 넘기면 된다. typed table에 매핑되지 않은 CSV도 `analysis.csv_files`와 `analysis.csv_rows`에는 들어간다.

```bash
uv run --script database/postgres/import_camels_csvs.py --store-raw \
  output/model_analysis/probabilistic_diagnostics/quantile_pinball_summary.csv
```

`--store-raw`를 빼면 `analysis.csv_files` metadata만 갱신되고, 대응 typed importer가 있는 CSV는 typed table까지 갱신된다.
