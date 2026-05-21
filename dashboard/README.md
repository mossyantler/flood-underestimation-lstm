# CAMELS 실험 분석 대시보드

Model 1 (deterministic LSTM) vs Model 2 (probabilistic quantile head) 비교를 읽기 위한 dense analytic dashboard입니다. 화면은 연구 결론의 source-of-truth가 아니라 `output/`, `docs/experiment/analysis/`, `configs/` 산출물을 축약한 표시 layer입니다.

## Run

```bash
export PATH="/opt/homebrew/bin:$PATH"
npm install
npm run dev
```

기본 주소: `http://localhost:3000` → `/overview` redirect

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
- `docs/experiment/analysis/basin/subset300_representativeness_report.md`
- `docs/experiment/method/model/architecture.md`

현재 dashboard snapshot의 핵심 경계는 DRBC primary test 38개 유역, fixed subset300, paired seed `111 / 222 / 444`, excluded seed `333`, Model 1 deterministic head, Model 2 q50/q90/q95/q99 quantile head입니다. Top 1% flow stratum underestimation은 Model 1 `72.6%`, Model 2 q99 `44.0%`로 표시하되, q99는 calibrated interval이나 return-period estimate로 읽지 않습니다.

## Preview Assets

`dashboard/public/figures/`에는 작은 PNG preview만 둡니다. 원본 figure와 full hydrograph gallery는 계속 `output/` 아래에 둡니다.

- `/figures/high-flow-quantiles.png` ← `output/model_analysis/overall_analysis/main_comparison/figures/overall_conclusion/overall_conclusion_high_flow_quantiles.png`
- `/figures/stress-tradeoff.png` ← `output/model_analysis/overall_analysis/main_comparison/figures/overall_conclusion/overall_conclusion_stress_tradeoff.png`
- `/figures/checkpoint-sensitivity.png` ← `output/model_analysis/paper_result_assets/figures/checkpoint_sensitivity_compact.png`
- `/figures/event-regime-delta.png` ← `output/model_analysis/paper_result_assets/figures/event_regime_paired_delta_compact.png`
- `/figures/quantile-calibration.png` ← `output/model_analysis/probabilistic_diagnostics/figures/primary_all_quantile_calibration.png`

## 검증

```bash
npm run typecheck
npm run build
```
