# output/ Agent Notes

루트 `AGENTS.md`를 먼저 따른다.
이 디렉토리는 **gitignored output 공간**이며, 분석 산출물·발표·논문용 figure/table/metadata를 보관한다.
코드나 config는 두지 않는다. 생성 스크립트와 실행 진입점은 `scripts/`에, 공식 config는 `configs/`에 둔다.

---

## 디렉토리 구조 (현재 기준)

```
output/
├── basin/                        # basin 정의·screening·event 분석 산출물
│   ├── all/                      # CAMELSH 전체 또는 non-DRBC training-pool 기준
│   │   ├── analysis/             # basin 특성·event·flood 분석
│   │   │   ├── event_regime/
│   │   │   ├── event_response/
│   │   │   ├── flood_generation/
│   │   │   └── return_period/
│   │   ├── reference_comparison/ # USGS/NOAA 보조 reference 비교
│   │   │   ├── noaa_prec/
│   │   │   └── usgs_flood/
│   │   ├── screening/            # training pool 선별 산출물
│   │   │   └── subset300_spatial_split/
│   │   ├── cache/                # 재계산 비용이 큰 중간 결과
│   │   └── archive/              # 구식 산출물 보존
│   ├── drbc/                     # DRBC holdout/evaluation region 기준
│   │   ├── basin_define/         # DRBC basin 정의 파일 (mapping, selected IDs 등)
│   │   ├── analysis/
│   │   │   ├── basin_attributes/
│   │   │   └── event_response/
│   │   ├── screening/
│   │   └── archive/
│   └── timeseries/               # basin split·target/input coverage·단일 sequence 진단
│
├── model_analysis/               # 고정 300-basin main comparison 모델 분석 산출물
│   ├── overall_analysis/         # Model 1/2 전체 성능 분석
│   │   ├── main_comparison/      # 공식 결과 (figures/, tables/, report/)
│   │   ├── epoch_sensitivity/    # epoch robustness 진단
│   │   ├── result_checks/        # 이상치·방법 점검
│   │   └── run_records/          # 실행 기록·provenance
│   ├── quantile_analysis/        # q50/q90/q95/q99 hydrograph·quantile 분석
│   │   ├── analysis/
│   │   ├── event_regime_analysis/
│   │   ├── primary_seed_basin/
│   │   ├── quantile_exports/
│   │   └── required_series/
│   └── extreme_rain/             # extreme-rain stress test 산출물
│       ├── primary/              # primary checkpoint (exposure/, inference/, analysis/, event_plots/)
│       ├── primary_time_aligned/ # wet-footprint time-aligned v2 diagnostic
│       └── all/                  # validation epoch grid sensitivity (inference/, analysis/)
│
└── presentation/                 # 발표·논문용 프레젠테이션/자료/figure 모음
    └── midterm/
        └── figures/
```

---

## 파일 배치 규칙

| 유형                            | 배치 위치                           |
| ------------------------------- | ----------------------------------- |
| 그림 파일 (png, pdf, svg 등)    | `figures/`                        |
| 집계 표·CSV                    | `tables/`                         |
| 실행 기록·provenance·manifest | `run_records/` 또는 `metadata/` |
| 로그                            | `logs/` (해당 분석 폴더 아래)     |
| 재계산 비용이 큰 중간 결과      | `cache/`                          |
| 구식 산출물 (삭제 전 보존)      | `archive/`                        |

- `figures/`에는 실제 그림 파일만 둔다. manifest·guide는 `run_records/`나 `metadata/`에 둔다.
- 새 top-level 폴더를 만들 때는 기존 `all/`·`drbc/` 폴더와의 차이를 해당 README나 manifest에 남긴다.
- 새 분석 폴더는 가능하면 `figures/`, `tables/`, `metadata/` 또는 `run_records/`, `logs/`, `cache/` 같은 공통 하위 구조를 사용한다. 임의 이름을 만들 때는 같은 계층의 기존 폴더명과 맞춘다.
- 공식 논문 결과와 smoke/dev 결과를 같은 폴더에 섞지 않는다. 임시 점검 결과는 먼저 `tmp/`에 두고, 보존할 가치가 있으면 README 또는 manifest와 함께 `output/`으로 옮긴다.

---

## 분석 범위별 규칙

### `basin/`

- **`all/`**: CAMELSH 전체 또는 non-DRBC training-pool 기준 산출물.
- **`drbc/`**: DRBC holdout/evaluation 기준 산출물. `basin_define/`에 DRBC 선정 파일(`camelsh_drbc_selected.csv` 등)을 고정한다.
- **`timeseries/`**: basin split·temporal coverage 진단. 모델 분석이 아니라 데이터 support 성격이므로 `model_analysis/` 아래에 두지 않는다.

### `model_analysis/`

- 폴더 이름에는 `subset300_` prefix를 붙이지 않는다. 일부 실행 스크립트 이름에는 실험 식별용으로 남아 있으나, 산출물 경로는 prefix 없이 유지한다.
- **`overall_analysis/main_comparison/`**: Model 1/2 공식 비교 결과만 둔다. 실험 세팅이나 epoch 그리드가 달라지면 `epoch_sensitivity/`나 `result_checks/`를 사용한다.
- **`extreme_rain/primary/`**: validation 기준 primary checkpoint 하나만 사용한 stress-test 결과. `exposure/`, `inference/`, `analysis/`, `event_plots/` 하위 폴더를 유지한다.
- **`extreme_rain/primary_time_aligned/`**: 기존 primary 결과를 덮어쓰지 않고 rain event 시간축을 wet-footprint 기준으로 보정한 v2 diagnostic 결과. `analysis/`에는 peak quantile-bracket CSV/figure를 함께 둘 수 있다.
- **`extreme_rain/all/`**: epoch grid(`005 / 010 / 015 / 020 / 025 / 030`) sensitivity sweep. primary checkpoint를 재선정하는 용도가 아니라 checkpoint robustness 진단용이다.

### `presentation/`

- 발표·논문용 최종 figure만 보관한다. 중간 draft나 작업본은 해당 `model_analysis/` 또는 `basin/` 하위 폴더에 둔다.

---

## 에이전트 체크리스트

새 산출물을 추가하거나 경로를 변경할 때 아래를 확인한다.

1. **배치 위치 확인**: 위 디렉토리 구조와 파일 배치 규칙에 맞는 위치인가?
2. **문서 동기화**: 경로 변경이 공식 workflow에 영향을 주면 `scripts/README.md`와 관련 `docs/`도 함께 갱신한다.
3. **prefix 금지**: 산출물 폴더 이름에 `subset300_` 같은 실험 prefix를 새로 추가하지 않는다.
4. **archive vs 삭제**: 구식 산출물은 바로 삭제하지 말고 `archive/`로 이동한 뒤 사유를 README에 남긴다.
5. **cache 재사용**: 재계산 비용이 큰 중간 결과는 `cache/`에 두고, 스크립트에서 존재 여부를 확인해 재사용한다.
