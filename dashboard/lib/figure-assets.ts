export type FigureAsset = {
  id: string;
  src: string;
  alt: string;
  title: string;
  kicker: string;
  caption: string;
  source: string;
};

export const figureAssets = {
  highFlowQuantiles: {
    id: "high-flow-quantiles",
    src: "/figures/high-flow-quantiles.png",
    alt: "Model 1 and Model 2 quantile predictors compared on high-flow underestimation",
    kicker: "Primary result",
    title: "High-flow quantile 비교",
    caption:
      "Q99 exceedance와 observed peak hour에서 q99 head가 deterministic peak underestimation을 얼마나 낮추는지 보여준다.",
    source:
      "output/model_analysis/overall_analysis/main_comparison/figures/overall_conclusion/overall_conclusion_high_flow_quantiles.png",
  },
  stressTradeoff: {
    id: "stress-tradeoff",
    src: "/figures/stress-tradeoff.png",
    alt: "Extreme-rain stress tradeoff between flood-response cohorts and false-positive proxy",
    kicker: "Stress diagnostic",
    title: "Extreme-rain tradeoff",
    caption:
      "historical stress event에서 q99가 flood-response event를 더 잘 잡는 대신 negative-control proxy도 같이 커지는지 확인한다.",
    source:
      "output/model_analysis/overall_analysis/main_comparison/figures/overall_conclusion/overall_conclusion_stress_tradeoff.png",
  },
  checkpointSensitivity: {
    id: "checkpoint-sensitivity",
    src: "/figures/checkpoint-sensitivity.png",
    alt: "Checkpoint sensitivity compact diagnostic for primary and all-epoch quantile behavior",
    kicker: "Robustness",
    title: "Checkpoint sensitivity",
    caption:
      "primary epoch 결과가 checkpoint grid 안에서 특별히 유리한 outlier인지 확인하는 보조 진단이다.",
    source:
      "output/model_analysis/paper_result_assets/figures/checkpoint_sensitivity_compact.png",
  },
  eventRegimeDelta: {
    id: "event-regime-delta",
    src: "/figures/event-regime-delta.png",
    alt: "Event-regime paired delta compact diagnostic for q99 effects",
    kicker: "Event regime",
    title: "Regime별 paired delta",
    caption:
      "570개 high-flow event를 regime으로 나눠 q99 under-deficit 감소와 recall 개선이 어느 조건에서 강한지 본다.",
    source:
      "output/model_analysis/paper_result_assets/figures/event_regime_paired_delta_compact.png",
  },
  quantileCalibration: {
    id: "quantile-calibration",
    src: "/figures/quantile-calibration.png",
    alt: "Primary quantile calibration coverage and diagnostic chart",
    kicker: "Calibration",
    title: "Quantile calibration",
    caption:
      "q99가 peak bias 완화에는 유효하지만 calibrated 99% interval로 해석하면 안 되는 근거를 보여준다.",
    source:
      "output/model_analysis/probabilistic_diagnostics/figures/primary_all_quantile_calibration.png",
  },
} satisfies Record<string, FigureAsset>;

export const overviewFigureDeck = [
  figureAssets.highFlowQuantiles,
  figureAssets.eventRegimeDelta,
  figureAssets.stressTradeoff,
];

export const resultFigureDeck = [
  figureAssets.highFlowQuantiles,
  figureAssets.checkpointSensitivity,
];

export const analysisFigureDeck = [
  figureAssets.eventRegimeDelta,
  figureAssets.quantileCalibration,
];

export const stressFigureDeck = [
  figureAssets.stressTradeoff,
  figureAssets.checkpointSensitivity,
];
