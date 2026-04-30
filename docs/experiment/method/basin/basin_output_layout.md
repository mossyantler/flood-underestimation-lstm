# Basin Output Layout

`output/basin/`의 현재 주요 top-level 폴더는 `all/`과 `drbc/`다. 다만 분석 범위나 방법이 기존 두 범주와 명확히 다르면 `method/`처럼 별도 top-level 폴더를 추가할 수 있다. 이전의 `camelsh_all/`, `drbc_camelsh/`, `camelsh_training_non_drbc/`, `checklists/`, `splits/`처럼 같은 의미를 중복하는 top-level 이름은 새 산출물에서 만들지 않는다.

| Folder | Purpose |
| --- | --- |
| `output/basin/all/` | CAMELSH 전체 basin inventory 또는 non-DRBC training pool 기준 산출물. 전 유역 분석은 `analysis/`, 외부 reference 비교는 `reference_comparison/`, quality gate/checklist/training-pool screening은 `screening/`, raw service 응답은 `cache/`, legacy/rerun은 `archive/`에 둔다. |
| `output/basin/drbc/` | DRBC holdout/evaluation region 산출물. DRBC selected/intersect/mapping/GPKG는 `basin_define/`, static/event 분석은 `analysis/`, quality/provisional gate는 `screening/`, smoke/legacy rerun은 `archive/`에 둔다. |

이 layout은 저장 경로의 의미를 짧게 유지하기 위한 규칙이다. 파일명에는 필요하면 `camelsh`, `drbc`, `non_drbc` 같은 의미 있는 stem을 그대로 둘 수 있다. 새 top-level 분류를 추가할 때는 기존 `all/` 또는 `drbc/` 아래에 둘 수 없는 이유를 README나 manifest에 남긴다.

`analysis/`는 주제별 폴더를 먼저 둔다. 예를 들어 `analysis/return_period/tables/`, `analysis/event_response/tables/`, `analysis/flood_generation/tables/`, `analysis/event_regime/figures/`처럼 분석 목적을 먼저 읽고 그 아래에서 `tables/`, `figures/`, `metadata/`를 구분한다.

USGS/NOAA 보조 자료는 CAMELSH proxy와 외부/보조 reference의 차이를 비교하는 목적이므로 `reference_comparison/`을 `analysis/`와 같은 level에 둔다. 내부 이름은 직접 `usgs_flood/`와 `noaa_prec/`를 사용하며, `usgs/usgs_flood` 또는 `noaa/noaa_prec` 같은 추가 중첩은 만들지 않는다.
