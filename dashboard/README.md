# CAMELS 실험 분석 대시보드

Model 1 (deterministic LSTM) vs Model 2 (probabilistic quantile head) 비교를 읽기 위한 dense analytic dashboard입니다. 화면은 연구 결론의 source-of-truth가 아니라 `output/`, `docs/experiment/analysis/`, `configs/` 산출물을 축약한 표시 layer입니다.

## Run

```bash
export PATH="/opt/homebrew/bin:$PATH"
npm install
npm run dev
```

기본 주소: `http://localhost:3000` → `/overview` redirect. 로컬에서는 `com.camels.dashboard.dev` LaunchAgent가 3000 포트를 유지합니다.

현재 top-level IA는 아래 5개 section입니다.

| Route | 역할 |
| --- | --- |
| `/overview` | 프로젝트 진행 상태, quick result, next action queue |
| `/experiment` | 공식 비교축, split policy, seed/checkpoint, test matrix, workflow |
| `/foundation` | Dataset / Model / Basin 기반 설명 |
| `/analysis` | main result, hydrograph, stress, confirmed flood, event regime, attribute, calibration |
| `/reference` | 선행연구와 관련연구를 section별로 묶는 map |

Confirmed flood 화면은 top-level이 아니라 Analysis module입니다: `http://localhost:3000/analysis/confirmed-flood`

Homebrew Node 25에서 Next dev가 `localStorage.getItem is not a function`을 내면 Node experimental Web Storage를 끄고 실행합니다.

```bash
NODE_OPTIONS=--no-experimental-webstorage npm run dev -- -p 3001
```

## Figma Source

- File key: `Yww4tmRcPSQswHfeov50gH`
- Desktop: node `16:2` (O·개요), `16:194` (R·결과) — 1680×1020
- Mobile: node `470:199` (O·개요), `470:1297` (R·결과) — 430×932

## Source Data

화면 수치는 `lib/dashboard-data.ts` typed snapshot을 사용합니다. canonical source-of-truth는 아래 파일과 폴더입니다.

- `output/model_analysis/analysis_dashboard/analysis_dashboard_data.json`
- `output/model_analysis/overall_analysis/main_comparison/tables/overall_performance_high_flow_quantile_summary.csv`
- `output/model_analysis/overall_analysis/main_comparison/tables/primary_epoch_summary.csv`
- `output/model_analysis/overall_analysis/main_comparison/tables/overall_performance_seed_delta_summary_long.csv`
- `output/model_analysis/probabilistic_diagnostics/quantile_calibration_summary.csv`
- `output/model_analysis/extreme_rain/primary/analysis/analysis_summary.json`
- `output/model_analysis/confirmed_flood/performance/drbc_confirmed_flood_performance.csv`
- `output/model_analysis/confirmed_flood/inference/confirmed_flood_event_windows_used.csv`
- `output/model_analysis/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv`
- `output/model_analysis/confirmed_flood/coverage/nws_flood_stage_coverage.csv`
- `basins/drbc_boundary/drb_bnd_polygon.shp`
- `basins/CAMELSH_data/shapefiles/CAMELSH_shapefile.shp`
- `docs/experiment/analysis/basin/subset300_representativeness_report.md`
- `docs/experiment/method/model/architecture.md`

Evaluation test matrix는 `lib/evaluation-tests-data.ts` snapshot을 사용합니다. 이 파일은 first test, extreme-rain stress test, confirmed flood test의 현재 source coverage를 분리해 보여 줍니다. First와 extreme은 expanded DRBC basin 기준 rerun이 끝난 산출만 공식값으로 승격합니다.

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run --script scripts/model/overall/export_evaluation_tests_dashboard_snapshot.py
```

현재 dashboard snapshot의 공식 경계는 DRBC primary test expanded observed **85개** 유역, fixed subset300 train/validation, paired seed `111 / 222 / 444`, excluded seed `333`, Model 1 deterministic head, Model 2 q50/q90/q95/q99 quantile head입니다. Top 1% flow stratum underestimation은 expanded DRBC snapshot 재생성 결과를 기준으로 표시해야 하며, q99는 calibrated interval이나 return-period estimate로 읽지 않습니다.

Confirmed flood snapshot은 아래 명령으로 canonical output에서 재생성합니다. 이 화면은 NWS flood-stage 초과 event 기준의 `623 events / 48 basins` inference 결과를 사용하고, NOAA Storm Events annotation은 flood type 보조 정보로만 표시합니다. 지도는 DRBC boundary shapefile과 CAMELSH basin polygon을 읽어 SVG path로 저장하며, gauge marker는 같은 크기의 위치점으로만 표시합니다.

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run --script scripts/model/confirmed_flood/export_confirmed_flood_dashboard_snapshot.py
```

## Preview Assets

`dashboard/public/figures/`에는 작은 PNG preview만 둡니다. 원본 figure와 full hydrograph gallery는 계속 `output/` 아래에 둡니다.

- `/figures/high-flow-quantiles.png` ← `output/model_analysis/overall_analysis/main_comparison/figures/overall_conclusion/overall_conclusion_high_flow_quantiles.png`
- `/figures/stress-tradeoff.png` ← `output/model_analysis/overall_analysis/main_comparison/figures/overall_conclusion/overall_conclusion_stress_tradeoff.png`
- `/figures/checkpoint-sensitivity.png` ← `output/model_analysis/paper_result_assets/figures/checkpoint_sensitivity_compact.png`
- `/figures/event-regime-delta.png` ← `output/model_analysis/paper_result_assets/figures/event_regime_paired_delta_compact.png`
- `/figures/quantile-calibration.png` ← `output/model_analysis/probabilistic_diagnostics/figures/primary_all_quantile_calibration.png`
- `/figures/input-coverage-overview.png` ← `output/basin/timeseries/input_coverage/figures/overview.png`

## Dataset Evidence Explorer

`/foundation/dataset`은 Dataset viewer prototype입니다. 이 화면은 `docs/`, `configs/`, `output/`, `database/local/`, `dashboard/data/`의 allowlisted artifact를 읽어 Markdown renderer, CSV preview grid, image/chart preview, DB preset shell로 보여줍니다.

CSV는 브라우저에 전체를 싣지 않고 server-side preview로 header, first 50 rows, row count, column count, file size를 표시합니다. DB preset shell은 read-only query aid의 위치를 보여주는 UI이며, 자유 SQL 실행기는 아닙니다.

## 검증

```bash
npm run typecheck
```

로컬 dev server가 3000에서 떠 있는 동안에는 `.next` cache 충돌을 피하기 위해 `npm run build`를 별도로 실행하지 않습니다. 500 응답에 `Cannot find module './*.js'`가 보이면 `dashboard/.next`를 지우고 LaunchAgent를 재시작합니다.
