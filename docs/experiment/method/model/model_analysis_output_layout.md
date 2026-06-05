# Model Analysis Output Layout

이 문서는 `output/model_analysis/` 아래 산출물 폴더의 현재 역할을 설명한다. 세부 배치 규칙은 `output/AGENTS.md`를 우선한다. 파일명에는 폴더명이 이미 주는 `confirmed_flood_`, `q99_`, `primary_`, `subset300_`, `expanded_drbc_` 같은 중복 접두어를 붙이지 않는다.

## 현재 공식 구조

| 폴더 | 형태 | 역할 |
| --- | --- | --- |
| `primary/` | 그룹형 | expanded DRBC observed test 85개 유역의 공식 Model 1/2 primary 결과. `metrics/`와 `calibration/`으로 분리한다. |
| `confirmed_flood/` | 평탄형 | NWS flood-stage 기준 확인 홍수 event catalog와 관련 요약. Q99 사건을 대체하지 않는 보조 홍수 범위다. |
| `q99_analysis/` | 그룹형 | 관측 Q99 초과 사건 중심 성능·원인 분석. `performance/`, `causes/`로 나눈다. |
| `band_signal/` | 그룹형 | 관측 첨두가 `q50/q90/q95/q99` 예측 사다리 어디에 놓이는지와 그 신호를 분석한다. |
| `shap/` | 그룹형 | 직접 SHAP 분석. `q99/`는 Q99 사건 조건부, `test_split/`은 전체 test split 조건부 분석이다. |
| `natural_broad_comparison/` | 평탄형 또는 legacy | pre-expanded broad/natural robustness 보조 산출물. 현재 paper canonical primary 근거로 쓰지 않는다. |

## `primary/` 하위 구조

```text
output/model_analysis/primary/
├── metrics/
│   ├── data/required_series/seed{111,222,444}/required_series.csv
│   ├── data/raw_metrics/
│   ├── tables/rq1_*, rq2_*, rq3_*, rq4a_*, rq4b_*, cross_tab_*.csv
│   └── figures/rq1_*, rq2_*, rq3_*, rq4a_*, rq4b_*.png
└── calibration/
    ├── tables/quantile_*, upper_tail_*, tier_*, comparability_manifest.json
    ├── figures/
    └── report/report.md
```

`primary/metrics/`는 RQ-1~4와 Q99/NOAA cross-tab 산출물의 기준 위치다. 재생성 진입점은 `scripts/model/expanded_drbc/run_all.py`다.

`primary/calibration/`은 RQ-5 calibration·sharpness 산출물의 기준 위치다. `coverage`는 "관측값이 예측 quantile 아래에 들어오는 비율"이며, lower quantile이 없으므로 `q99`를 calibrated 99% prediction interval이나 return-period estimate로 해석하지 않는다.

## `band_signal/` 하위 구조

```text
output/model_analysis/band_signal/
├── band_shape/
├── slope_signal/
├── signal_sweep/
└── method_compare/
```

`band_signal/`은 관측 위치 구간(관측 첨두가 `q50`~`q99` 예측 사다리 어디에 놓이는지)과 그 위치를 예고하는 신호를 묶은 주제다.

| 하위 폴더 | 역할 |
| --- | --- |
| `band_shape/` | 밴드 폭, 꼬리 모양, 위치 구간, gap trajectory, hydrograph fan. |
| `slope_signal/` | 상승 기울기 기반 신호 분석. |
| `signal_sweep/` | 강우·대류·유역·seed spread 후보 신호 탐색. |
| `method_compare/` | 상승부 onset 검출법 비교. |

## `shap/` 하위 구조

```text
output/model_analysis/shap/
├── q99/
└── test_split/
```

`shap/q99/`는 Q99 사건 조건부 직접 SHAP 결과를 보존한다. `shap/test_split/`은 test split 전체에서 저유량·중유량·고유량·극유량 조건을 비교하는 직접 SHAP 분석이다.

## 이름 규칙

- output 파일명에서 `expanded`는 쓰지 않는다. expanded observed DRBC test 85개 유역이라는 조건은 config, data split, 문서 설명에서 확인한다.
- 산출물 폴더 root에 표·그림 파일을 직접 두지 않는다. 표는 `tables/`, 그림은 `figures/` 또는 대량 basin별 그림용 `gallery/`에 둔다.
- 분석 폴더 안에 같은 분석 이름을 다시 중첩하지 않는다. 한 분석 안의 갈래는 하위 폴더 추가보다 파일명 prefix로 구분한다.
