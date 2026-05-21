import type { AnalysisModuleCopy } from "./evidence-types";

export const analysisModuleCopy = [
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

export function getAnalysisModuleCopy(moduleId: string): AnalysisModuleCopy | undefined {
  return analysisModuleCopy.find((item) => item.moduleId === moduleId);
}
