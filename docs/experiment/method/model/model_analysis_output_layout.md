# Model Analysis Output Layout

이 문서는 `output/model_analysis/` 아래 산출물 폴더의 역할을 설명한다. 폴더명에는 더 이상 `subset300_` prefix를 붙이지 않는다. 현재 실험이 고정 300-basin main comparison이라는 사실은 config와 runner 이름에서 확인하고, 산출물 경로는 분석 목적 중심으로 읽는다.

| Folder | Purpose |
| --- | --- |
| `overall_analysis/` | Model 1/2의 전체 성능 분석 산출물이다. 공식 결과는 `main_comparison/`, epoch robustness는 `epoch_sensitivity/`, 이상치/방법 점검은 `result_checks/`, 실행 기록은 `run_records/`에 둔다. |
| `quantile_analysis/` | 모든 validation checkpoint의 required-series와 q50/q90/q95/q99 hydrograph 분석 결과를 둔다. high-flow strata, peak-hour, quantile coverage, event-regime 분석의 기준 입력이다. |
| `extreme_rain/primary/` | validation 기준 primary checkpoint만 사용한 extreme-rain exposure/stress-test 산출물이다. event catalog, inference required-series, paired delta aggregate, event plot, 대표 event의 prediction-overlaid flow graph diagnostic을 포함한다. |
| `extreme_rain/all/` | primary 선택과 분리된 checkpoint sensitivity 진단용 extreme-rain sweep 산출물이다. validation epoch grid `005 / 010 / 015 / 020 / 025 / 030` 전체를 비교한다. |
| `natural_broad_comparison/` | Broad DRBC test 38개를 Natural 8개와 broad non-natural 30개로 다시 나누어 primary overall, high-flow, event-window, extreme-rain stress 방향을 비교한 robustness 산출물이다. |
| `../basin/timeseries/` | fixed split의 target/input coverage, basin time-series overview, 단일 sequence 구조 진단 산출물. 시간축 coverage는 basin/data support 성격이므로 `model_analysis/`가 아니라 `output/basin/timeseries/`에 둔다. |

`overall_analysis/` 안에서는 파일 역할을 폴더명으로 바로 알 수 있게 아래 구조를 사용한다.

| Folder | Purpose |
| --- | --- |
| `overall_analysis/main_comparison/` | validation 기준 primary checkpoint에서 Model 1과 Model 2 `q50`을 비교한 공식 전체 성능 결과다. |
| `overall_analysis/epoch_sensitivity/` | epoch `005 / 010 / 015 / 020 / 025 / 030` 전체를 훑어 primary 결과가 특정 checkpoint 하나에만 의존하는지 확인하는 보조 분석이다. Figure는 `figures/`, 집계표는 `tables/`, 학습/검증 로그는 `logs/`, chart manifest와 metadata는 `metadata/`에 둔다. |
| `overall_analysis/result_checks/` | outlier basin, seed ensemble method 비교처럼 결과 해석을 점검하기 위한 diagnostic 산출물이다. |
| `overall_analysis/run_records/` | metric file manifest, 분석 metadata처럼 재현성과 입력 출처 추적에 쓰는 실행 기록이다. |

현재 로컬에 없는 `probabilistic_diagnostics/` 같은 폴더는 해당 분석을 새로 실행할 때만 생성된다. 생성되면 이 문서와 `scripts/README.md`의 경로 설명을 함께 갱신한다.
