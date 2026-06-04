# output/ 배치 규칙

루트 `AGENTS.md`를 먼저 따른다. `output/`은 **gitignored 산출물 공간**이다.

이 문서는 *현재 구조 스냅샷이 아니라 규칙*이다. 새 분석·파일·폴더는 아래 규칙으로 위치를 **도출**한다. 규칙으로 안 풀리는 경우가 생기면 임의 배치하지 말고 이 문서를 먼저 개정한다.

각 규칙은 `원칙 / 예외 / 예시`로 적는다.

---

## 규칙 0 — output 적재 대상

- **원칙**: 재생성 가능한 분석 산출물(그림·표·중간물·요약·갤러리)만 둔다.
- **예외**: 없다. 코드는 `scripts/`, config는 `configs/`, 원자료는 `basins/`·`data/`.
- **예시**: `metric_boxplots.png` ✓ / `analyze_x.py` ✗ / `split.yml` ✗

## 규칙 1 — 주제(top-level) 추가

- **원칙**: 평가셋 또는 분석 축이 기존 주제와 **다르면** 새 top-level 주제. **같으면** 기존 주제의 하위 분석.
- **예외**: 기존 평가셋을 다른 각도로 보는 분석은 새 top-level을 만들지 말고 그 주제 하위로 넣는다.
- **예시**: 다른 holdout region 평가 → 새 주제. NWS stage 기준 추가 분석 → `confirmed_flood/` 하위.

## 규칙 2 — 평탄형 vs 그룹형

- **원칙**: 주제 내 독립 분석이 **1개면 평탄형**(주제 폴더 = 표준 폴더). **2개+면 그룹형**(주제 = `README.md` + 분석별 표준 폴더). 둘을 섞지 않는다.
- **예외**: 평탄형이라도 basin별 대량 그림이 있으면 `gallery/`를 추가한다. 평탄형 주제에 2번째 독립 분석이 추가되면 **그룹형으로 승격**(기존 산출물을 하위 분석 폴더로 내린다).
- **예시**: `confirmed_flood/{figures,tables,data,report,gallery}` (평탄). `primary/{metrics,calibration}/...` (그룹).

## 규칙 3 — 표준 하위 폴더 5종

- **원칙**: 모든 파일은 `figures/` `tables/` `data/` `report/` `gallery/` 중 하나에 성격으로 배정한다.
  - `figures/` = 결론용 대표 그림 (.png)
  - `tables/` = 수치 표 (.csv, .parquet)
  - `data/` = 입력·중간물·캐시 (추론 원본, catalog, metadata, .geojson, .json)
  - `report/` = 사람이 읽는 요약 (.md, .html, summary .json)
  - `gallery/` = basin별 대량 그림 (`figures/`와 분리)
- **예외**: 5종에 안 맞는 새 유형은 우선 `data/`. 정말 새 범주면 이 문서로 표준을 **개정한 뒤** 적용한다.
- **예시**: `lstm_attribution.png`→figures / `metrics.csv`→tables / 추론 원본·`catalog`·`metadata`→data / `report.md`→report / `event_plots`→gallery.

## 규칙 4 — 깊이·중첩

- **원칙**: 최대 2단계(주제 / 분석). 분석 내부는 표준 5폴더까지만 판다.
- **예외**: 한 분석이 여러 갈래면(예: 오차 원인 basin/forcing/attribution) 폴더를 더 파지 말고 **파일명 prefix**로 구분한다.
- **예시**: `causes/figures/`에 `q99_lstm_attribution_*` · `q99_event_forcing_*` · `basin_q99_error_*` (causes 안에 attribution/forcing/basin 폴더를 만들지 않는다).
- **적신호**: 분석 안에 또 다른 분석 이름이 생기면 → 별 주제로 분리하라는 신호.

## 규칙 5 — 파일명

- **원칙**: 폴더가 주는 맥락은 파일명에서 제거한다. 식별자·의미 토큰은 보존한다.
- **제거**: 폴더명 중복 접두(`confirmed_flood_`, `primary_`), upper-band `ub_`(폴더 `band_shape`가 맥락 제공), 실험맥락(`subset300_`, `expanded_drbc_`, "expanded" 단어).
- **보존**: 식별자(`seed111/222/444`, `model1/model2`, `q50/q90/q95/q99`, `with_outliers/without_outliers`), 의미 약어(`q99`=임계값, `rq1~rq4`, `m3/m4`).
- **예외**: 약어/토큰이 폴더와 겹쳐도 "의미"(임계값·방법·비교 대상)를 가지면 유지한다.
- **예시**: `confirmed_flood_tier_aggregate.csv`→`tier_aggregate.csv` / `ub_location_class.csv`→`location_class.csv` / `q99_lstm_attribution.csv`→**유지** / `154_vs_expanded_comparison.csv`→**유지**.

## 규칙 6 — 금지

- **원칙**: 주제·분석 폴더 root에 파일을 직접 두지 않는다. 같은 그림을 두 곳에 두지 않는다. 공식 결과와 smoke/dev 결과를 같은 폴더에 섞지 않는다.
- **예외**: 임시 점검은 `tmp/`에 둔다. 보존 가치가 생기면 README와 함께 `output/`으로 옮긴다.
- **예시**: 모든 산출물은 표준 하위 폴더로. smoke 출력 → `tmp/`.

## 규칙 7 — 스크립트 동기화

- **원칙**: 폴더·파일명은 생성 스크립트가 출력한다. 규칙을 적용해 경로·이름을 바꾸면 **해당 스크립트의 출력 경로·파일명 문자열도 같은 작업에서** 수정한다.
- **예외**: 없다. 동기화를 빠뜨리면 다음 실행에 옛 구조가 재생성된다.
- **예시**: 주제를 `drbc_test`→`primary`로 옮기면 해당 `scripts/model/*`의 출력 경로도 `primary`로 바꾼다.

## 규칙 8 — 지도 산출물 provenance (GAGES-II)

- **원칙**: GAGES-II geometry 기반 지도 산출물은 manifest에 provenance를 기록한다.
- **필수 항목**: GAGES-II 출처(USGS `gagesii-basins` API/cache 또는 로컬 shapefile), 최종 렌더 CRS `EPSG:5070`, DRBC boundary clip 여부, cache 경로.
- **예시**: `plot_drbc_gagesii_paper_map` 산출물 옆 manifest에 위 항목을 기록한다.

---

## 적용 범위

- **`model_analysis/`**: 위 규칙 전면 적용. 현재 주제 목록은 루트 `AGENTS.md`·`CLAUDE.md`의 "output 분석 폴더 표준" 표 참조(현재 상태이며, 규칙 1·2로 갱신된다).
- **`basin/`, `presentation/`**: 동일 원칙(규칙 0·3·5·6) 적용. 영역 특화 구조는 같은 규칙으로 점진 정렬한다.
