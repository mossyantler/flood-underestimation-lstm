# CAMELS Next.js 분석 대시보드

DRBC holdout에서 Model 1 deterministic LSTM과 Model 2 probabilistic quantile head를 비교하는 dense analytic dashboard입니다. 이전 React/Next 구현은 삭제하지 않고 `../react-2026-05-14/` 아래에 보존했습니다.

## Run

```bash
export PATH="/opt/homebrew/bin:$PATH"
npm install
npm run dev
```

기본 주소는 `http://localhost:3000`입니다. 주요 panel과 card는 `/details/[slug]` route로 이어지며, 최소 detail page는 새 dark CAMELS shell과 같은 visual system을 사용합니다.

## Figma Source

새 구현은 Figma rough design을 기준으로 재구성했습니다.

- Figma file key: `Yww4tmRcPSQswHfeov50gH`
- Desktop page: `↳ Dashboard`, prototype frame `421:236` overview, `421:3260` results, target size `1680x1020`
- Mobile page: `↳ Dashboard · Mobile Adaptive`, frame `470:199` overview, `470:1297` results, target size `430x932`
- Local design source: `../../figma/dashboard layout rough design.fig`
- Local reference exports and visual QA screenshots, when regenerated, should live under `../../figma/`.

## Source Data

화면 값은 `lib/dashboard-data.ts`의 typed snapshot을 사용합니다. 이 snapshot은 아래 분석 산출물에서 dashboard 표시용으로 축약한 값이며, canonical source-of-truth는 계속 `output/`, `docs/experiment/analysis/`, `docs/experiment/method/`, `configs/`에 둡니다.

- `output/model_analysis/analysis_dashboard/analysis_dashboard_data.json`
- `output/model_analysis/overall_analysis/main_comparison/tables/overall_performance_high_flow_quantile_summary.csv`
- `output/model_analysis/extreme_rain/primary/analysis/paired_delta_aggregate.csv`
- `output/model_analysis/paper_result_assets/`

Figure preview는 기존 `public/figures/` 경로를 그대로 재사용합니다. `public/research/`와 `public/figures/`는 legacy로 이동하지 않았습니다.

## Layout Contract

Desktop은 82px icon rail, 390px context sidebar, main workbench 구조를 따릅니다. 기본 theme는 dark이고, theme toggle은 `localStorage`에 저장됩니다. Mobile은 sidebar를 접고 horizontal section pills와 single-column KPI stack으로 전환합니다.

UI 변경 뒤에는 최소한 아래 검증을 실행합니다.

```bash
export PATH="/opt/homebrew/bin:$PATH"
npm run typecheck
```

route, static params, image loading, production bundle에 영향을 주는 변경이면 build까지 확인합니다.

```bash
export PATH="/opt/homebrew/bin:$PATH"
npm run build
```

이번 Figma rebuild의 visual QA screenshot은 top-level `../../figma/`에 남기는 기준입니다. 이 파일들은 화면 검증 기록이며 분석 source-of-truth는 아닙니다.
