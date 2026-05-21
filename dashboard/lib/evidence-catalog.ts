import type { AnalysisModuleCopy, EvidenceItem } from "./evidence-types";

export const evidenceCatalogInputHash = "f5ddeb94b97f067738ca3545cafbd84940114ed39323d93adb96369e502a7416";

export const evidenceModules = [
  {
    "moduleId": "overview/status",
    "section": "overview",
    "module": "status",
    "title": "Overview status",
    "analysisPurpose": "프로젝트 진행 상태와 rerun queue를 빠르게 확인한다.",
    "background": "뒤늦게 합류한 동료는 먼저 무엇이 완료됐고 무엇이 아직 공식 claim에 올라갈 수 없는지 알아야 한다.",
    "coreData": "evaluation test snapshot, overview status KPI, confirmed flood summary, paired seed policy.",
    "interpretationMethod": "ready는 dashboard 공식 해석에 사용할 수 있는 상태이고, needs-rerun은 source universe가 아직 맞지 않아 공식값으로 쓰지 않는 상태다.",
    "currentJudgment": "Model 1/2 paired seed 비교와 confirmed flood layer는 준비됐고, first/extreme test는 expanded basin 기준 rerun queue에 있다.",
    "status": "ready"
  },
  {
    "moduleId": "foundation/dataset",
    "section": "foundation",
    "module": "dataset",
    "title": "Dataset",
    "analysisPurpose": "CAMELSH 원천, model input, result data, analysis data의 경계를 구분한다.",
    "background": "산출물이 많아지면 input, raw result, analysis summary가 섞인다. 동료가 데이터 성격을 먼저 알아야 잘못된 비교를 피할 수 있다.",
    "coreData": "CAMELSH hourly source, prepared generic dataset, split files, coverage diagnostics, analysis summary tables.",
    "interpretationMethod": "input data는 모델에 들어간 자료, result data는 inference와 metric raw output, analysis data는 결과 해석을 위해 가공한 table/chart로 읽는다.",
    "currentJudgment": "Dashboard는 source-of-truth를 대체하지 않고, configs/docs/output에 있는 데이터와 산출물의 접근 경로를 정리한다.",
    "status": "ready"
  },
  {
    "moduleId": "foundation/model",
    "section": "foundation",
    "module": "model",
    "title": "Model",
    "analysisPurpose": "Model 1 deterministic baseline과 Model 2 probabilistic quantile extension의 비교 경계를 고정한다.",
    "background": "현재 논문 비교축은 backbone을 바꾸는 실험이 아니라 같은 LSTM backbone에서 output head를 바꾼 효과를 보는 구조다.",
    "coreData": "Model 1 architecture, Model 2 quantile head, paired seed 111/222/444, subset300 split.",
    "interpretationMethod": "모델 구조 문서는 성능 해석 전에 어떤 차이가 실험적으로 허용됐는지 확인하는 기준으로 읽는다.",
    "currentJudgment": "Dashboard evidence는 Model 1 vs Model 2 비교를 공식 축으로 두고, physics-guided extension은 후속 연구로 분리한다.",
    "status": "ready"
  },
  {
    "moduleId": "analysis/main-result",
    "section": "analysis",
    "module": "main-result",
    "title": "Main result",
    "analysisPurpose": "Model 2 quantile head가 Model 1 대비 extreme peak 과소추정을 줄였는지 확인한다.",
    "background": "Model 1은 하나의 point prediction만 내기 때문에 extreme peak에서 낮게 예측될 수 있다. Model 2는 같은 LSTM backbone에 quantile head를 붙여 upper-tail prediction을 직접 비교한다.",
    "coreData": "DRBC holdout, paired seed 111/222/444, Q99 exceedance, observed peak hour.",
    "interpretationMethod": "underestimation fraction은 관측값보다 예측값이 낮은 비율이다. 낮을수록 peak를 덜 놓쳤다는 뜻이지만 q99를 calibrated 99% interval로 해석하면 안 된다.",
    "currentJudgment": "q99는 peak underestimation을 줄이는 방향이 보인다. Calibration과 false-positive tradeoff는 별도 module에서 확인한다.",
    "status": "ready"
  },
  {
    "moduleId": "analysis/confirmed-flood",
    "section": "analysis",
    "module": "confirmed-flood",
    "title": "Confirmed flood",
    "analysisPurpose": "NWS flood-stage 기반 confirmed flood event에서 Model 1/2의 event-level 성능을 점검한다.",
    "background": "Q99 threshold는 후보 event 기준이고 official flood label은 아니다. Confirmed flood module은 외부 flood-stage 기준과 모델 예측을 연결해 해석 리스크를 줄인다.",
    "coreData": "DRBC confirmed flood event table, performance CSV, inferred event hydrograph snapshot.",
    "interpretationMethod": "event 단위 성능은 source universe와 stage coverage가 맞는지 먼저 확인한 뒤 peak bias, recall, timing을 함께 읽는다.",
    "currentJudgment": "Confirmed flood evidence는 dashboard에서 별도 module로 분리해 Q99 stress test와 혼동하지 않게 둔다.",
    "status": "ready"
  },
  {
    "moduleId": "analysis/calibration",
    "section": "analysis",
    "module": "calibration",
    "title": "Calibration",
    "analysisPurpose": "Model 2 quantile output이 peak reduction과 calibration tradeoff를 어떻게 보이는지 확인한다.",
    "background": "q99가 높은 peak를 잘 덮어도 calibrated 99% interval이라는 뜻은 아니다. Coverage와 pinball loss를 따로 봐야 한다.",
    "coreData": "probabilistic diagnostics report, quantile coverage, pinball loss, calibration plots.",
    "interpretationMethod": "coverage는 관측값이 예측 quantile 아래에 들어오는 비율이다. q95/q99가 지나치게 낮거나 높으면 peak 개선과 uncertainty 해석을 분리한다.",
    "currentJudgment": "Calibration module은 main-result claim의 caveat layer로 쓰며, q99 성능을 interval reliability로 과대해석하지 않게 한다.",
    "status": "ready"
  },
  {
    "moduleId": "analysis/hydrograph",
    "section": "analysis",
    "module": "hydrograph",
    "title": "Hydrograph",
    "analysisPurpose": "대표 event hydrograph 후보를 통해 aggregate metric이 실제 시간축 예측에서 어떻게 보이는지 확인한다.",
    "background": "전체 metric만 보면 peak 크기와 timing 오류가 섞일 수 있다. Hydrograph view는 event shape와 peak hour 주변 오차를 직접 확인하게 해준다.",
    "coreData": "representative hydrograph candidate table, observed peak hour, model prediction series, basin metadata.",
    "interpretationMethod": "대표 hydrograph는 headline metric의 예시이지 전체 분포를 대체하지 않는다. Basin, event, seed 조건을 함께 읽는다.",
    "currentJudgment": "Hydrograph evidence는 paper figure 후보와 dashboard drilldown의 연결점으로 유지한다.",
    "status": "ready"
  },
  {
    "moduleId": "reference/analysis",
    "section": "reference",
    "module": "analysis",
    "title": "Analysis references",
    "analysisPurpose": "성능 해석과 flood typing 논의를 뒷받침하는 reference map을 확인한다.",
    "background": "연구 결론은 dashboard 내부 문구만으로 확정하면 안 된다. Related papers와 method notes를 같이 봐야 해석 범위가 안전하다.",
    "coreData": "related papers index, flood-generation typing literature notes, method reference summaries.",
    "interpretationMethod": "Reference module은 claim source가 아니라 해석 보조 자료다. 공식 실험 결과는 docs/experiment와 output 산출물을 우선한다.",
    "currentJudgment": "Reference evidence는 dashboard에서 supporting role로 노출해 분석 문서와 문헌 근거를 빠르게 연결한다.",
    "status": "ready"
  }
] as const satisfies readonly AnalysisModuleCopy[];

export const evidenceItems = [
  {
    "id": "calibration-report",
    "moduleId": "analysis/calibration",
    "title": "Probabilistic diagnostics report",
    "section": "analysis",
    "module": "calibration",
    "kind": "report",
    "role": "canonical",
    "priority": 1,
    "showInDashboard": true,
    "sourcePath": "output/model_analysis/probabilistic_diagnostics/report/probabilistic_diagnostics_report.md",
    "docPath": "output/model_analysis/probabilistic_diagnostics/report/probabilistic_diagnostics_report.md",
    "analysisPurpose": "q99 calibration caveat",
    "shortDescription": "Quantile coverage and pinball interpretation",
    "tags": [
      "analysis",
      "calibration"
    ],
    "status": "ready"
  },
  {
    "id": "confirmed-flood-performance",
    "moduleId": "analysis/confirmed-flood",
    "title": "Confirmed flood performance table",
    "section": "analysis",
    "module": "confirmed-flood",
    "kind": "table",
    "role": "canonical",
    "priority": 1,
    "showInDashboard": true,
    "sourcePath": "output/model_analysis/confirmed_flood/performance/drbc_confirmed_flood_performance.csv",
    "generatorPath": "scripts/model/confirmed_flood/export_confirmed_flood_dashboard_snapshot.py",
    "tablePath": "output/model_analysis/confirmed_flood/performance/drbc_confirmed_flood_performance.csv",
    "analysisPurpose": "NWS flood-stage event audit",
    "shortDescription": "Confirmed flood model performance rows",
    "tags": [
      "analysis",
      "confirmed-flood"
    ],
    "status": "ready"
  },
  {
    "id": "hydrograph-candidates",
    "moduleId": "analysis/hydrograph",
    "title": "Representative hydrograph candidates",
    "section": "analysis",
    "module": "hydrograph",
    "kind": "table",
    "role": "canonical",
    "priority": 1,
    "showInDashboard": true,
    "sourcePath": "output/model_analysis/paper_result_assets/tables/representative_hydrograph_candidates.csv",
    "tablePath": "output/model_analysis/paper_result_assets/tables/representative_hydrograph_candidates.csv",
    "analysisPurpose": "Hydrograph representative evidence",
    "shortDescription": "Selected basin/event hydrograph candidates",
    "tags": [
      "analysis",
      "hydrograph"
    ],
    "status": "ready"
  },
  {
    "id": "high-flow-chart",
    "moduleId": "analysis/main-result",
    "title": "High-flow quantile comparison",
    "section": "analysis",
    "module": "main-result",
    "kind": "chart",
    "role": "canonical",
    "priority": 1,
    "showInDashboard": true,
    "sourcePath": "output/model_analysis/overall_analysis/main_comparison/figures/overall_conclusion/overall_conclusion_high_flow_quantiles.png",
    "docPath": "docs/experiment/analysis/model/02_primary_high_flow_peak_performance.md",
    "chartPath": "output/model_analysis/overall_analysis/main_comparison/figures/overall_conclusion/overall_conclusion_high_flow_quantiles.png",
    "analysisPurpose": "Q99 exceedance quantile comparison",
    "shortDescription": "Primary chart for peak underestimation claim",
    "tags": [
      "analysis",
      "chart",
      "q99"
    ],
    "status": "ready"
  },
  {
    "id": "primary-high-flow-md",
    "moduleId": "analysis/main-result",
    "title": "Primary high-flow peak performance",
    "section": "analysis",
    "module": "main-result",
    "kind": "doc",
    "role": "canonical",
    "priority": 1,
    "showInDashboard": true,
    "sourcePath": "docs/experiment/analysis/model/02_primary_high_flow_peak_performance.md",
    "docPath": "docs/experiment/analysis/model/02_primary_high_flow_peak_performance.md",
    "analysisPurpose": "Model 2 q99 peak underestimation claim",
    "shortDescription": "Main claim interpretation doc",
    "tags": [
      "analysis",
      "main-result",
      "q99"
    ],
    "status": "ready"
  },
  {
    "id": "dataset-guide",
    "moduleId": "foundation/dataset",
    "title": "Data processing guide",
    "section": "foundation",
    "module": "dataset",
    "kind": "doc",
    "role": "canonical",
    "priority": 1,
    "showInDashboard": true,
    "sourcePath": "docs/experiment/method/data/data_processing_analysis_guide.md",
    "docPath": "docs/experiment/method/data/data_processing_analysis_guide.md",
    "analysisPurpose": "Input result analysis data boundary",
    "shortDescription": "Dataset workflow guide",
    "tags": [
      "foundation",
      "dataset",
      "data"
    ],
    "status": "ready"
  },
  {
    "id": "input-coverage-overview",
    "moduleId": "foundation/dataset",
    "title": "Input coverage overview",
    "section": "foundation",
    "module": "dataset",
    "kind": "chart",
    "role": "supporting",
    "priority": 2,
    "showInDashboard": true,
    "sourcePath": "output/basin/timeseries/input_coverage/figures/overview.png",
    "chartPath": "output/basin/timeseries/input_coverage/figures/overview.png",
    "analysisPurpose": "CAMELSH input coverage",
    "shortDescription": "Input coverage figure",
    "tags": [
      "foundation",
      "dataset",
      "coverage"
    ],
    "status": "ready"
  },
  {
    "id": "architecture-md",
    "moduleId": "foundation/model",
    "title": "Model architecture",
    "section": "foundation",
    "module": "model",
    "kind": "doc",
    "role": "canonical",
    "priority": 1,
    "showInDashboard": true,
    "sourcePath": "docs/experiment/method/model/architecture.md",
    "docPath": "docs/experiment/method/model/architecture.md",
    "analysisPurpose": "Model 1 and Model 2 비교 구조",
    "shortDescription": "LSTM backbone and quantile head boundary",
    "tags": [
      "model",
      "architecture",
      "canonical"
    ],
    "status": "ready"
  },
  {
    "id": "paper-assets-report",
    "moduleId": "overview/status",
    "title": "Paper result assets report",
    "section": "overview",
    "module": "status",
    "kind": "report",
    "role": "canonical",
    "priority": 1,
    "showInDashboard": true,
    "sourcePath": "output/model_analysis/paper_result_assets/report/paper_result_assets_report.md",
    "docPath": "output/model_analysis/paper_result_assets/report/paper_result_assets_report.md",
    "analysisPurpose": "Homepage result evidence",
    "shortDescription": "Paper-ready result asset summary",
    "tags": [
      "overview",
      "paper-assets"
    ],
    "status": "ready"
  },
  {
    "id": "reference-related-papers",
    "moduleId": "reference/analysis",
    "title": "Related papers map",
    "section": "reference",
    "module": "analysis",
    "kind": "doc",
    "role": "supporting",
    "priority": 2,
    "showInDashboard": true,
    "sourcePath": "docs/references/related_papers.md",
    "docPath": "docs/references/related_papers.md",
    "analysisPurpose": "Literature map for analysis claims",
    "shortDescription": "Related paper index",
    "tags": [
      "reference",
      "papers"
    ],
    "status": "ready"
  }
] as const satisfies readonly EvidenceItem[];

export function getEvidenceForModule(moduleId: string): EvidenceItem[] {
  return evidenceItems.filter((item) => item.moduleId === moduleId && item.showInDashboard);
}

export function getCopyForModule(moduleId: string): AnalysisModuleCopy | undefined {
  return evidenceModules.find((item) => item.moduleId === moduleId);
}
