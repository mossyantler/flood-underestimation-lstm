import type { AnalysisModuleCopy, EvidenceItem } from "./evidence-types";

export const evidenceCatalogGeneratedAt = "2026-05-21T07:39:05Z";

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
