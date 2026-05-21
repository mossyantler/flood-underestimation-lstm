export type StatusTone = "good" | "near" | "warn" | "neutral";

export type KpiCard = {
  label: string;
  value: string;
  detail: string;
  tone: StatusTone;
  detailSlug?: string;
};

export type GroupSummary = {
  id: string;
  label: string;
  description: string;
  answer: string;
  analysisCount: number;
  figureCount: number;
  tableCount: number;
  status: StatusTone;
  detailSlug?: string;
};

export type AnalysisItem = {
  id: string;
  groupId: string;
  title: string;
  status: string;
  purpose: string;
  use: string;
  metrics: Array<[string, string]>;
  tags: string[];
  detailSlug?: string;
};

export type QuantileComparison = {
  predictor: string;
  underestimationFraction: number;
  medianRelativeBiasPct: number;
  medianAbsError: number;
  tone: StatusTone;
};

export type SeedDelta = {
  seed: string;
  medianDeltaNse: number;
  improvedFractionNse: number;
  medianDeltaKge: number;
  improvedFractionKge: number;
};

export type FigurePreview = {
  title: string;
  caption: string;
  src: string;
  detailSlug?: string;
};

export type EvidenceLevel = "Primary" | "Stress" | "Diagnostic";

export type DetailPageSpec = {
  slug: string;
  sectionLabel: string;
  title: string;
  evidenceLevel: EvidenceLevel;
  comparisonContext: string;
  caveat: string;
  readingRule: string;
  summary: string;
  sourcePaths: string[];
  tablePreview: {
    title: string;
    columns: string[];
    rows: string[][];
    sourcePath: string;
  };
  chartPreview: {
    title: string;
    caption: string;
    values: Array<{
      label: string;
      value: number;
      tone: StatusTone;
    }>;
  };
  figurePreview: {
    title: string;
    src: string;
    caption: string;
    sourcePath: string;
  };
};

export type SourceLink = {
  label: string;
  href: string;
  kind: string;
};

export type DashboardData = {
  generatedAt: string;
  scope: {
    title: string;
    subtitle: string;
    primaryQuestion: string;
    officialSeeds: string[];
    excludedSeeds: string[];
    model1: string;
    model2: string;
  };
  kpis: KpiCard[];
  groups: GroupSummary[];
  analyses: AnalysisItem[];
  quantiles: QuantileComparison[];
  seedDeltas: SeedDelta[];
  figures: FigurePreview[];
  sources: SourceLink[];
  details: DetailPageSpec[];
};

export const dashboardData: DashboardData = {
  generatedAt: "2026-05-14",
  scope: {
    title: "CAMELS 실험 분석",
    subtitle:
      "Subset300 DRBC holdout에서 Model 1 deterministic baseline과 Model 2 probabilistic quantile head를 비교합니다.",
    primaryQuestion: "Quantile head는 extreme flood peak 과소추정을 줄이나요?",
    officialSeeds: ["111", "222", "444"],
    excludedSeeds: ["333"],
    model1: "Deterministic multi-basin LSTM",
    model2: "Probabilistic multi-basin LSTM, 동일 backbone + quantile head"
  },
  kpis: [
    {
      label: "DRBC test 유역",
      value: "38",
      detail: "quality gate를 통과한 DRBC holdout 유역",
      tone: "good",
      detailSlug: "dataset-split-boundary"
    },
    {
      label: "공식 paired seed",
      value: "3",
      detail: "111 / 222 / 444, seed 333 제외",
      tone: "good",
      detailSlug: "model-comparison-contract"
    },
    {
      label: "Q99 과소추정",
      value: "0.440",
      detail: "Model 2 q99, 유역별 상위 1% 유량 stratum",
      tone: "near",
      detailSlug: "primary-high-flow-quantiles"
    },
    {
      label: "Stress 이벤트",
      value: "236",
      detail: "primary wet-footprint DRBC historical stress event",
      tone: "neutral",
      detailSlug: "stress-supplementary-check"
    },
    {
      label: "Hydrograph PNG",
      value: "7,137",
      detail: "38개 유역 observed Q99+ gallery",
      tone: "neutral",
      detailSlug: "hydrograph-review"
    }
  ],
  groups: [
    {
      id: "data-foundation",
      label: "데이터 기반",
      description: "DRBC holdout, subset300, high-flow event label, coverage check.",
      answer:
        "DRBC holdout, subset300, event label 기준은 재현 가능한 상태로 묶여 있어요.",
      analysisCount: 6,
      figureCount: 2,
      tableCount: 13,
      status: "good",
      detailSlug: "dataset-split-boundary"
    },
    {
      id: "overall-performance",
      label: "전체 성능",
      description: "Primary Model 1 vs Model 2 paired metric과 checkpoint sensitivity.",
      answer:
        "q50 guardrail과 checkpoint sensitivity를 함께 보면 큰 손상 없이 비교축을 유지합니다.",
      analysisCount: 3,
      figureCount: 3,
      tableCount: 1,
      status: "near",
      detailSlug: "primary-results-guardrail"
    },
    {
      id: "probabilistic-head",
      label: "Quantile head 진단",
      description: "Q50 / Q90 / Q95 / Q99 high-flow behavior와 calibration diagnostics.",
      answer:
        "q95/q99 계열에서 high-flow 과소추정 완화 신호를 직접 확인합니다.",
      analysisCount: 4,
      figureCount: 4,
      tableCount: 5,
      status: "near",
      detailSlug: "primary-high-flow-quantiles"
    },
    {
      id: "event-stress",
      label: "Event / Stress",
      description: "Extreme-rain stress, runoff-ratio, event-regime, hydrograph review.",
      answer:
        "extreme-rain, runoff-ratio, hydrograph를 나눠 사건별 반응 차이를 추적합니다.",
      analysisCount: 4,
      figureCount: 5,
      tableCount: 2,
      status: "near",
      detailSlug: "stress-supplementary-check"
    },
    {
      id: "basin-robustness",
      label: "유역 robustness",
      description: "Natural/Broad robustness, outlier mechanism, basin-level diagnosis.",
      answer:
        "Natural/Broad, outlier mechanism, basin dissect로 유역별 편향과 예외를 분리합니다.",
      analysisCount: 4,
      figureCount: 1,
      tableCount: 4,
      status: "good",
      detailSlug: "analysis-calibration-robustness"
    },
    {
      id: "paper-assets",
      label: "논문 산출물",
      description: "후보 figure, compact table, paper-facing staging output.",
      answer:
        "본문 후보 표와 figure를 따로 staging해서 분석 산출물에서 바로 추적할 수 있습니다.",
      analysisCount: 1,
      figureCount: 0,
      tableCount: 1,
      status: "good",
      detailSlug: "paper-asset-sources"
    }
  ],
  analyses: [
    {
      id: "drbc-definition",
      groupId: "data-foundation",
      title: "DRBC holdout 유역 정의",
      status: "완료",
      purpose: "DRBC regional holdout의 공간 정의를 고정합니다.",
      use: "test region과 training 제외 규칙의 기준점입니다.",
      metrics: [
        ["평가 CAMELSH", "9,008"],
        ["DRBC 내 outlet", "192"],
        ["overlap >= 0.9 선택", "154"]
      ],
      tags: ["split", "DRBC", "boundary"]
    },
    {
      id: "drbc-screening",
      groupId: "data-foundation",
      title: "DRBC quality gate와 broad/natural screening",
      status: "완료",
      purpose: "DRBC basin 중 usable streamflow 기준을 통과한 test basin을 확정합니다.",
      use: "broad 38과 natural 8 robustness 비교의 공통 모집단입니다.",
      metrics: [
        ["선택", "154"],
        ["quality pass", "38"],
        ["hydromod risk", "127"]
      ],
      tags: ["quality", "natural", "hydromod"]
    },
    {
      id: "subset300-representativeness",
      groupId: "data-foundation",
      title: "Subset300 대표성과 scaling pilot",
      status: "완료",
      purpose: "compute-constrained main comparison의 train/validation basin 수를 고정합니다.",
      use: "DRBC test 성능이 아니라 validation, static distribution, cost를 같이 보는 운영 결정입니다.",
      metrics: [
        ["raw broad pool", "1,923"],
        ["prepared pool", "1,903"],
        ["고정 subset", "300"]
      ],
      tags: ["subset300", "scaling", "pilot"]
    },
    {
      id: "timeseries-coverage",
      groupId: "data-foundation",
      title: "Split별 time-series coverage 진단",
      status: "완료",
      purpose: "train / validation / test timeline의 target coverage를 점검합니다.",
      use: "low-coverage basin이 metric을 왜곡하지 않는지 확인합니다.",
      metrics: [
        ["train 유역", "269"],
        ["validation 유역", "31"],
        ["test 유역", "38"]
      ],
      tags: ["coverage", "timeline", "hourly"]
    },
    {
      id: "all-event-response",
      groupId: "data-foundation",
      title: "전체 유역 observed high-flow event response",
      status: "완료",
      purpose: "Q99 기반 observed high-flow event catalog를 만듭니다.",
      use: "stress test와 event-regime 분석의 event universe입니다.",
      metrics: [
        ["유역", "1,961"],
        ["event", "184,140"],
        ["threshold", "Q99"]
      ],
      tags: ["events", "Q99", "observed"]
    },
    {
      id: "ml-event-regime",
      groupId: "data-foundation",
      title: "ML event-regime stratification",
      status: "채택 완료",
      purpose: "hydromet descriptor 기반 event regime를 보수적으로 나눕니다.",
      use: "regime별 성능 차이를 해석하되 causal mechanism으로 과장하지 않습니다.",
      metrics: [
        ["event", "184,140"],
        ["유역", "1,961"],
        ["variant", "kmeans hydromet k3"]
      ],
      tags: ["regime", "kmeans", "descriptor"]
    },
    {
      id: "primary-overall",
      groupId: "overall-performance",
      title: "Primary 전체 성능",
      status: "완료에 가까움",
      purpose: "공식 seed에서 Model 1과 Model 2의 paired metric delta를 봅니다.",
      use: "전체 성능 손상 여부와 q50 guardrail을 확인합니다.",
      metrics: [
        ["공식 seed", "111, 222, 444"],
        ["primary delta row", "114"],
        ["선택 metric file", "72"]
      ],
      tags: ["NSE", "KGE", "paired"]
    },
    {
      id: "checkpoint-sensitivity",
      groupId: "overall-performance",
      title: "Checkpoint sensitivity",
      status: "완료에 가까움",
      purpose: "all-validation-epoch 결과가 primary conclusion에 얼마나 민감한지 점검합니다.",
      use: "stress/test 결과로 primary epoch를 재선택하지 않는다는 guardrail입니다.",
      metrics: [
        ["same-epoch delta row", "684"],
        ["validation epoch", "005-030"],
        ["공식 seed", "111, 222, 444"]
      ],
      tags: ["epoch", "sensitivity", "guardrail"]
    },
    {
      id: "overfit-risk",
      groupId: "overall-performance",
      title: "Overfit / test-oracle risk 분석",
      status: "완료",
      purpose: "checkpoint 선택이 test oracle처럼 동작하지 않는지 확인합니다.",
      use: "논문 해석에서 checkpoint sensitivity를 보조 근거로만 쓰게 합니다.",
      metrics: [
        ["file", "14"],
        ["공식 run", "6"],
        ["primary loss overfit >= 5%", "0/6"]
      ],
      tags: ["overfit", "oracle", "loss"]
    },
    {
      id: "high-flow-quantile",
      groupId: "probabilistic-head",
      title: "High-flow / peak quantile 분석",
      status: "완료에 가까움",
      purpose: "Q95 / Q99 prediction이 high-flow peak 과소추정을 줄이는지 봅니다.",
      use: "Model 2의 output design 개선 효과를 가장 직접적으로 보여 줍니다.",
      metrics: [
        ["required-series file", "18"],
        ["hydrograph plot", "684"],
        ["flow summary row", "630"]
      ],
      tags: ["q95", "q99", "peak"]
    },
    {
      id: "probabilistic-diagnostics",
      groupId: "probabilistic-head",
      title: "Probabilistic calibration / pinball",
      status: "완료에 가까움",
      purpose: "pinball loss, one-sided coverage, upper-tail spread를 분리해 점검합니다.",
      use: "q99 peak hit-rate를 unconditional calibration으로 오해하지 않게 합니다.",
      metrics: [
        ["quantiles", "q50, q90, q95, q99"],
        ["file", "14"],
        ["figure", "4"]
      ],
      tags: ["pinball", "coverage", "calibration"]
    },
    {
      id: "extreme-flood-proxy",
      groupId: "probabilistic-head",
      title: "Extreme flood proxy sensitivity",
      status: "부분 완료",
      purpose: "return-period proxy tier에서 signal이 유지되는지 봅니다.",
      use: "event 수가 작아 claim strength를 낮춰야 하는 구간을 표시합니다.",
      metrics: [
        ["ge2 proxy event", "30"],
        ["ge10 proxy event", "9"],
        ["ge25 proxy event", "1"]
      ],
      tags: ["proxy", "return-period", "sparse"]
    },
    {
      id: "peak-quantile-bracket",
      groupId: "probabilistic-head",
      title: "Local peak quantile bracket 진단",
      status: "완료",
      purpose: "observed peak 주변 window에서 어느 quantile이 peak를 bracket하는지 봅니다.",
      use: "event-level q50 / q90 / q95 / q99의 역할 차이를 설명합니다.",
      metrics: [
        ["window hour", "6"],
        ["sensitivity window", "0, 12"],
        ["chart", "3"]
      ],
      tags: ["bracket", "peak", "event"]
    },
    {
      id: "event-regime-errors",
      groupId: "event-stress",
      title: "Event-regime model error 분석",
      status: "완료에 가까움",
      purpose: "event regime별 paired error delta를 비교합니다.",
      use: "recent rainfall, antecedent, weak/low-signal 구간을 나눠 해석합니다.",
      metrics: [
        ["unique event", "570"],
        ["유역", "38"],
        ["seed-event row", "1,710"]
      ],
      tags: ["event", "regime", "error"]
    },
    {
      id: "extreme-rain-stress",
      groupId: "event-stress",
      title: "Extreme-rain stress test",
      status: "완료에 가까움",
      purpose: "historical extreme-rain events에서 Model 2 upper quantiles의 response를 봅니다.",
      use: "primary DRBC test를 대체하지 않는 basin-holdout stress diagnostic입니다.",
      metrics: [
        ["stress event", "236"],
        ["유역", "38"],
        ["positive response", "157"]
      ],
      tags: ["rain", "stress", "historical"]
    },
    {
      id: "runoff-ratio",
      groupId: "event-stress",
      title: "Extreme-rain runoff-ratio 진단",
      status: "완료",
      purpose: "observed and simulated runoff ratio를 event window 기준으로 비교합니다.",
      use: "rain denominator window가 해석을 어떻게 바꾸는지 드러냅니다.",
      metrics: [
        ["file", "17"],
        ["basin mapping row", "38"],
        ["figure check", "4"]
      ],
      tags: ["runoff-ratio", "event", "rain"]
    },
    {
      id: "hydrograph-galleries",
      groupId: "event-stress",
      title: "Observed Q99+ hydrograph gallery",
      status: "완료",
      purpose: "basin별 representative hydrograph를 interactive gallery로 확인합니다.",
      use: "metric table에서 보이지 않는 timing, magnitude, managed-flow artifact를 봅니다.",
      metrics: [
        ["basin gallery", "38"],
        ["hydrograph PNG", "7,137"],
        ["station note", "38"]
      ],
      tags: ["hydrograph", "gallery", "Q99"]
    },
    {
      id: "median-deviation",
      groupId: "basin-robustness",
      title: "Metric median-deviation 유역 regime 분석",
      status: "완료",
      purpose: "basin별 metric profile이 cohort median에서 얼마나 벗어나는지 봅니다.",
      use: "ratio가 다른 유역을 같은 regime로 묶지 않기 위한 guardrail입니다.",
      metrics: [
        ["basin별 최대 record", "18"],
        ["basin report input", "38"],
        ["tier profile", "38"]
      ],
      tags: ["basin", "regime", "median"]
    },
    {
      id: "outlier-mechanism",
      groupId: "basin-robustness",
      title: "Primary metric outlier mechanism deep dive",
      status: "완료",
      purpose: "outlier basins를 hydromodification, size, event response 등 mechanism별로 분리합니다.",
      use: "한 요인으로 과잉 설명하지 않도록 basin note와 metric을 함께 봅니다.",
      metrics: [
        ["outlier audit row", "167"],
        ["basin characteristic row", "38"],
        ["report", "6"]
      ],
      tags: ["outlier", "mechanism", "basin"]
    },
    {
      id: "natural-broad",
      groupId: "basin-robustness",
      title: "Broad vs Natural robustness",
      status: "완료에 가까움",
      purpose: "Natural 8과 Broad 38에서 signal이 같은 방향인지 비교합니다.",
      use: "Natural aggregate가 일부 outlier에 과도하게 좌우되는지 점검합니다.",
      metrics: [
        ["broad all", "38"],
        ["natural", "8"],
        ["broad non-natural", "30"]
      ],
      tags: ["natural", "broad", "robustness"]
    },
    {
      id: "basin-dissect",
      groupId: "basin-robustness",
      title: "Basin dissect report",
      status: "완료",
      purpose: "38개 DRBC basin 각각의 metric, event, station-note를 통합합니다.",
      use: "global aggregate 이후 local explanation을 확인하는 마지막 분석 레이어입니다.",
      metrics: [
        ["unique report", "38"],
        ["tier count", "27 / 4 / 2 / 5"],
        ["station note", "38"]
      ],
      tags: ["basin-dissect", "reports", "notes"]
    },
    {
      id: "paper-assets",
      groupId: "paper-assets",
      title: "논문 결과 산출물",
      status: "완료",
      purpose: "paper-facing compact chart/table candidates를 staging합니다.",
      use: "대시보드 탐색 결과를 논문 figure 후보와 연결합니다.",
      metrics: [
        ["file", "12"],
        ["candidate type", "3"],
        ["type별 candidate", "5"]
      ],
      tags: ["paper", "figures", "tables"]
    }
  ],
  quantiles: [
    {
      predictor: "Model 1",
      underestimationFraction: 0.7256,
      medianRelativeBiasPct: -46.44,
      medianAbsError: 16.36,
      tone: "warn"
    },
    {
      predictor: "Model 2 q50",
      underestimationFraction: 0.8667,
      medianRelativeBiasPct: -68.47,
      medianAbsError: 17.01,
      tone: "warn"
    },
    {
      predictor: "Model 2 q95",
      underestimationFraction: 0.6263,
      medianRelativeBiasPct: -21.71,
      medianAbsError: 12.31,
      tone: "near"
    },
    {
      predictor: "Model 2 q99",
      underestimationFraction: 0.4396,
      medianRelativeBiasPct: 11.49,
      medianAbsError: 16.24,
      tone: "good"
    }
  ],
  seedDeltas: [
    {
      seed: "111",
      medianDeltaNse: 0.109,
      improvedFractionNse: 0.632,
      medianDeltaKge: -0.072,
      improvedFractionKge: 0.421
    },
    {
      seed: "222",
      medianDeltaNse: 0.201,
      improvedFractionNse: 0.605,
      medianDeltaKge: 0.042,
      improvedFractionKge: 0.553
    },
    {
      seed: "444",
      medianDeltaNse: 0.246,
      improvedFractionNse: 0.684,
      medianDeltaKge: 0.268,
      improvedFractionKge: 0.684
    }
  ],
  figures: [
    {
      title: "High-flow quantile 결론",
      caption: "Model 2 upper quantile은 유역별 top 1% 과소추정 비율을 낮춥니다.",
      src: "/figures/high-flow-quantiles.png",
      detailSlug: "primary-high-flow-quantiles"
    },
    {
      title: "Stress tradeoff",
      caption: "Extreme-rain positive response와 negative-control behavior를 함께 봅니다.",
      src: "/figures/stress-tradeoff.png",
      detailSlug: "stress-supplementary-check"
    },
    {
      title: "Checkpoint sensitivity",
      caption: "Primary와 same-epoch sensitivity를 압축해서 비교합니다.",
      src: "/figures/checkpoint-sensitivity.png",
      detailSlug: "primary-results-guardrail"
    },
    {
      title: "Event regime delta",
      caption: "Paired event-regime error delta를 논문용 compact asset으로 정리했습니다.",
      src: "/figures/event-regime-delta.png",
      detailSlug: "analysis-calibration-robustness"
    },
    {
      title: "Quantile calibration",
      caption: "All-hour one-sided coverage는 tail hit-rate diagnostics와 분리해서 해석합니다.",
      src: "/figures/quantile-calibration.png",
      detailSlug: "analysis-calibration-robustness"
    }
  ],
  sources: [
    {
      label: "Lazyweb 디자인 리서치 보고서",
      href: "../.lazyweb/design-research/experiment-analysis-dashboard-2026-05-14/report.html",
      kind: "레이아웃 리서치"
    },
    {
      label: "analysis_dashboard_data.json",
      href: "../output/model_analysis/analysis_dashboard/analysis_dashboard_data.json",
      kind: "로컬 source"
    },
    {
      label: "High-flow quantile summary",
      href: "../output/model_analysis/overall_analysis/main_comparison/tables/overall_performance_high_flow_quantile_summary.csv",
      kind: "로컬 table"
    },
    {
      label: "Extreme-rain paired delta aggregate",
      href: "../output/model_analysis/extreme_rain/primary/analysis/paired_delta_aggregate.csv",
      kind: "로컬 table"
    }
  ],
  details: [
    {
      slug: "dataset-split-boundary",
      sectionLabel: "Dataset",
      title: "DRBC holdout와 subset300 source boundary",
      evidenceLevel: "Primary",
      comparisonContext:
        "non-DRBC fixed subset300으로 학습하고 DRBC 38개 quality-pass basin에서 Model 1과 Model 2를 평가합니다.",
      caveat:
        "DRBC boundary와 split provenance는 dashboard가 새로 정의하지 않습니다. source-of-truth는 configs, docs, output의 분석 산출물입니다.",
      readingRule:
        "Dataset detail은 결과 해석의 전제만 고정합니다. stress historical period는 primary temporal independence 근거로 읽지 않습니다.",
      summary:
        "CAMELSH hourly 기반 non-DRBC train/validation과 DRBC holdout을 분리하고, seed 111에서 고른 scaling_300 subset을 공식 Model 1/2 paired seed에 재사용합니다.",
      sourcePaths: [
        "configs/basin_splits/",
        "output/model_analysis/analysis_dashboard/analysis_dashboard_data.json",
        "docs/experiment/method/data/data_processing_analysis_guide.md"
      ],
      tablePreview: {
        title: "Split snapshot",
        columns: ["unit", "count", "role"],
        rows: [
          ["non-DRBC quality-pass pool", "1,923", "training candidate"],
          ["fixed subset", "300", "compute-constrained main comparison"],
          ["train basins", "269", "model fitting"],
          ["validation basins", "31", "epoch selection"],
          ["DRBC test basins", "38", "primary holdout"]
        ],
        sourcePath: "dashboard/lib/dashboard-data.ts"
      },
      chartPreview: {
        title: "Basin split scale",
        caption: "Prepared subset and DRBC holdout are shown only as scope context.",
        values: [
          { label: "pool", value: 1923, tone: "neutral" },
          { label: "subset", value: 300, tone: "near" },
          { label: "test", value: 38, tone: "good" }
        ]
      },
      figurePreview: {
        title: "High-flow dashboard preview",
        src: "/figures/high-flow-quantiles.png",
        caption:
          "Figure slot reuses the existing dashboard preview asset; no full output gallery is copied.",
        sourcePath:
          "output/model_analysis/overall_analysis/main_comparison/figures/overall_conclusion/overall_conclusion_high_flow_quantiles.png"
      }
    },
    {
      slug: "model-comparison-contract",
      sectionLabel: "Model",
      title: "Model 1 vs Model 2 head-only comparison",
      evidenceLevel: "Primary",
      comparisonContext:
        "Model 1은 deterministic multi-basin LSTM이고 Model 2는 동일 backbone에 quantile head만 추가합니다.",
      caveat:
        "현재 공식 비교축에는 physics-guided Model 3를 포함하지 않습니다. q50은 central guardrail이고 q95/q99는 flood-tail bracket으로 읽습니다.",
      readingRule:
        "성능 개선 claim은 backbone 교체가 아니라 output design 차이에서 나온 paired comparison으로 제한합니다.",
      summary:
        "공식 paired seed 111 / 222 / 444를 같은 subset에서 비교하고, NaN loss로 중단된 Model 2 seed 333과 대응 Model 1 seed 333은 aggregate에서 제외합니다.",
      sourcePaths: [
        "docs/experiment/method/model/architecture.md",
        "output/model_analysis/overall_analysis/main_comparison/figures/model_architecture/model12_architecture_comparison.png",
        "runs/"
      ],
      tablePreview: {
        title: "Paired seed contract",
        columns: ["seed", "Model 1", "Model 2", "aggregate use"],
        rows: [
          ["111", "complete", "complete", "included"],
          ["222", "complete", "complete", "included"],
          ["333", "complete", "NaN loss", "excluded"],
          ["444", "complete", "complete", "included"]
        ],
        sourcePath: "dashboard/lib/dashboard-data.ts"
      },
      chartPreview: {
        title: "Official paired coverage",
        caption: "Included seeds are the only rows used for final paired aggregate.",
        values: [
          { label: "included", value: 3, tone: "good" },
          { label: "excluded", value: 1, tone: "warn" }
        ]
      },
      figurePreview: {
        title: "Checkpoint sensitivity preview",
        src: "/figures/checkpoint-sensitivity.png",
        caption:
          "Checkpoint sweep is a sensitivity diagnostic, not a rule for reselecting primary epoch from stress/test output.",
        sourcePath:
          "output/model_analysis/paper_result_assets/figures/checkpoint_sensitivity_compact.png"
      }
    },
    {
      slug: "primary-high-flow-quantiles",
      sectionLabel: "Results",
      title: "High-flow quantile and peak underestimation detail",
      evidenceLevel: "Primary",
      comparisonContext:
        "Model 1, Model 2 q50, q95, q99 are compared on DRBC paired-seed high-flow and peak readouts.",
      caveat:
        "q99 is an upper-tail decision output, not a calibrated 99% interval, return-period estimate, or unconditional probability forecast.",
      readingRule:
        "Read q50 as the central-skill guardrail and q95/q99 as flood-tail bracket evidence. Do not use q99 hit-rate as calibration by itself.",
      summary:
        "Top 1% flow stratum underestimation falls from 72.6% for Model 1 to 44.0% for Model 2 q99, while q50 remains a separate guardrail question.",
      sourcePaths: [
        "output/model_analysis/paper_result_assets/tables/primary_high_flow_peak_compact.csv",
        "output/model_analysis/overall_analysis/main_comparison/tables/overall_performance_high_flow_quantile_summary.csv",
        "output/model_analysis/paper_result_assets/figures/high_flow_quantile_ladder_compact.png"
      ],
      tablePreview: {
        title: "High-flow preview rows",
        columns: ["predictor", "underestimation", "median bias", "median abs error"],
        rows: [
          ["Model 1", "72.6%", "-46.44%", "16.36"],
          ["Model 2 q50", "86.7%", "-68.47%", "17.01"],
          ["Model 2 q95", "62.6%", "-21.71%", "12.31"],
          ["Model 2 q99", "44.0%", "11.49%", "16.24"]
        ],
        sourcePath:
          "output/model_analysis/paper_result_assets/tables/primary_high_flow_peak_compact.csv"
      },
      chartPreview: {
        title: "Underestimation ladder",
        caption:
          "Lower bars are better for underestimation fraction; this is primary paired evidence.",
        values: [
          { label: "M1", value: 72.56, tone: "warn" },
          { label: "q50", value: 86.67, tone: "warn" },
          { label: "q95", value: 62.63, tone: "near" },
          { label: "q99", value: 43.96, tone: "good" }
        ]
      },
      figurePreview: {
        title: "High-flow quantile preview",
        src: "/figures/high-flow-quantiles.png",
        caption:
          "PNG preview is bundled as a small dashboard asset; the original output path remains the source boundary.",
        sourcePath:
          "output/model_analysis/overall_analysis/main_comparison/figures/overall_conclusion/overall_conclusion_high_flow_quantiles.png"
      }
    },
    {
      slug: "primary-results-guardrail",
      sectionLabel: "Results",
      title: "Primary q50 guardrail and checkpoint sensitivity",
      evidenceLevel: "Diagnostic",
      comparisonContext:
        "q50 central performance and all-validation-epoch checkpoint sweeps are read beside the primary high-flow result.",
      caveat:
        "All-validation-epoch results are checkpoint sensitivity diagnostics. They are not used to reselect the primary epoch using DRBC stress/test behavior.",
      readingRule:
        "Use this page to check whether the main conclusion is fragile to checkpoint choice, not to strengthen the primary evidence level.",
      summary:
        "Official seed deltas show mixed metric behavior, so the dashboard keeps central-skill guardrails visible next to the tail-focused claim.",
      sourcePaths: [
        "output/model_analysis/overall_analysis/main_comparison/tables/primary_epoch_delta_summary.csv",
        "output/model_analysis/paper_result_assets/figures/checkpoint_sensitivity_compact.png",
        "docs/experiment/analysis/model/06_checkpoint_sensitivity.md"
      ],
      tablePreview: {
        title: "Seed delta preview",
        columns: ["seed", "median dNSE", "NSE improved", "median dKGE"],
        rows: [
          ["111", "+0.109", "63.2%", "-0.072"],
          ["222", "+0.201", "60.5%", "+0.042"],
          ["444", "+0.246", "68.4%", "+0.268"]
        ],
        sourcePath:
          "output/model_analysis/overall_analysis/main_comparison/tables/primary_epoch_delta_summary.csv"
      },
      chartPreview: {
        title: "NSE improvement share",
        caption: "Seed-level paired guardrail, not flood-tail evidence by itself.",
        values: [
          { label: "111", value: 63.2, tone: "near" },
          { label: "222", value: 60.5, tone: "near" },
          { label: "444", value: 68.4, tone: "good" }
        ]
      },
      figurePreview: {
        title: "Checkpoint sensitivity",
        src: "/figures/checkpoint-sensitivity.png",
        caption: "Compact preview of primary vs same-epoch sensitivity behavior.",
        sourcePath:
          "output/model_analysis/paper_result_assets/figures/checkpoint_sensitivity_compact.png"
      }
    },
    {
      slug: "hydrograph-review",
      sectionLabel: "Hydrograph",
      title: "Representative hydrograph review",
      evidenceLevel: "Diagnostic",
      comparisonContext:
        "Observed Q, Model 1, and Model 2 q50/q95/q99 are read in the same event window for selected representative candidates.",
      caveat:
        "The dashboard does not copy the full hydrograph gallery. Candidate selection and source paths must remain visible to avoid cherry-picking.",
      readingRule:
        "Use hydrograph pages to inspect shape, timing, and magnitude examples after reading aggregate metrics.",
      summary:
        "The layout reserves slots for candidate table, React chart preview, and PNG viewer while pointing to manifest/source paths for the full gallery.",
      sourcePaths: [
        "output/model_analysis/paper_result_assets/tables/representative_hydrograph_candidates.csv",
        "output/model_analysis/quantile_analysis/hydrograph_plot_manifest.csv",
        "output/model_analysis/quantile_analysis/primary_seed_basin/"
      ],
      tablePreview: {
        title: "Candidate type preview",
        columns: ["candidate_type", "count", "reading"],
        rows: [
          ["q99_success_near_peak", "5", "upper quantile brackets peak"],
          ["q99_still_underestimates", "5", "failure mode"],
          ["q99_overpredicts", "5", "false-positive risk"]
        ],
        sourcePath:
          "output/model_analysis/paper_result_assets/tables/representative_hydrograph_candidates.csv"
      },
      chartPreview: {
        title: "Candidate queue balance",
        caption: "Representative review queue only; full gallery remains outside dashboard bundle.",
        values: [
          { label: "success", value: 5, tone: "good" },
          { label: "under", value: 5, tone: "warn" },
          { label: "over", value: 5, tone: "near" }
        ]
      },
      figurePreview: {
        title: "Event regime preview",
        src: "/figures/event-regime-delta.png",
        caption: "Placeholder figure slot demonstrates aspect-ratio-safe PNG viewing.",
        sourcePath:
          "output/model_analysis/paper_result_assets/figures/event_regime_paired_delta_compact.png"
      }
    },
    {
      slug: "analysis-calibration-robustness",
      sectionLabel: "Analysis",
      title: "Calibration, event regime, and robustness caveats",
      evidenceLevel: "Diagnostic",
      comparisonContext:
        "Event-regime deltas, Broad/Natural robustness, and calibration/pinball diagnostics bound the primary result.",
      caveat:
        "Calibration diagnostics must not turn q99 into a calibrated 99% interval. Natural cohort results have small-N risk and should not replace Broad 38 primary readout.",
      readingRule:
        "Read these panels as heterogeneity and claim-boundary diagnostics rather than ranking tables.",
      summary:
        "The detail page keeps q99 calibration caveat, regime descriptor caveat, and Natural/Broad sample-size boundary next to source paths.",
      sourcePaths: [
        "output/model_analysis/quantile_analysis/event_regime_analysis/paired_delta_aggregate.csv",
        "output/model_analysis/probabilistic_diagnostics/quantile_calibration_summary.csv",
        "output/model_analysis/natural_broad_comparison/tables/"
      ],
      tablePreview: {
        title: "Calibration preview",
        columns: ["quantile", "nominal", "empirical coverage", "reading"],
        rows: [
          ["q50", "0.50", "central", "guardrail"],
          ["q90", "0.90", "diagnostic", "upper-tail spread"],
          ["q95", "0.95", "diagnostic", "flood bracket"],
          ["q99", "0.99", "not calibrated", "decision output"]
        ],
        sourcePath:
          "output/model_analysis/probabilistic_diagnostics/quantile_calibration_summary.csv"
      },
      chartPreview: {
        title: "Quantile role strip",
        caption: "Values encode role order, not empirical calibration.",
        values: [
          { label: "q50", value: 50, tone: "neutral" },
          { label: "q90", value: 90, tone: "near" },
          { label: "q95", value: 95, tone: "near" },
          { label: "q99", value: 99, tone: "warn" }
        ]
      },
      figurePreview: {
        title: "Quantile calibration preview",
        src: "/figures/quantile-calibration.png",
        caption:
          "Calibration PNG is shown as a caveat viewer, not as primary flood evidence.",
        sourcePath:
          "output/model_analysis/probabilistic_diagnostics/figures/primary_all_quantile_calibration.png"
      }
    },
    {
      slug: "stress-supplementary-check",
      sectionLabel: "Stress",
      title: "Extreme-rain historical stress supplementary check",
      evidenceLevel: "Stress",
      comparisonContext:
        "DRBC basin holdout is retained, but the stress catalog uses historical 1980-2024 extreme-rain events.",
      caveat:
        "Stress is supplementary and does not replace subset300 primary DRBC test. Because it uses historical 1980-2024, do not use it for temporal independence claims.",
      readingRule:
        "Read positive-response and negative-control behavior together: q99 may reduce under-deficit while increasing false-positive risk.",
      summary:
        "The stress detail page displays event scope, response-class tradeoff, peak bracket preview, and source paths without importing the full stress PNG gallery.",
      sourcePaths: [
        "output/model_analysis/extreme_rain/primary/analysis/paired_delta_aggregate.csv",
        "output/model_analysis/extreme_rain/primary/event_simq_plots/event_simq_plot_manifest.csv",
        "output/model_analysis/extreme_rain/primary/analysis/figures/peak_quantile_bracket/response_class_peak_quantile_bracket_stacked.png"
      ],
      tablePreview: {
        title: "Stress scope preview",
        columns: ["item", "value", "reading"],
        rows: [
          ["historical period", "1980-2024", "supplementary"],
          ["stress events", "236", "DRBC historical catalog"],
          ["positive response", "157", "benefit check"],
          ["negative control", "79", "false-positive check"]
        ],
        sourcePath:
          "output/model_analysis/extreme_rain/primary/analysis/paired_delta_aggregate.csv"
      },
      chartPreview: {
        title: "Stress response split",
        caption:
          "Stress counts are scope context and must be read below primary evidence level.",
        values: [
          { label: "positive", value: 157, tone: "good" },
          { label: "negative", value: 79, tone: "warn" }
        ]
      },
      figurePreview: {
        title: "Stress tradeoff preview",
        src: "/figures/stress-tradeoff.png",
        caption:
          "Small bundled PNG preview; full stress gallery and manifests stay in output/.",
        sourcePath:
          "output/model_analysis/overall_analysis/main_comparison/figures/overall_conclusion/overall_conclusion_stress_tradeoff.png"
      }
    },
    {
      slug: "paper-asset-sources",
      sectionLabel: "Report",
      title: "Paper-facing asset and source path inventory",
      evidenceLevel: "Diagnostic",
      comparisonContext:
        "Compact tables and PNG previews are routing aids from the dashboard back to canonical analysis outputs.",
      caveat:
        "Dashboard preview assets are not source-of-truth. Update canonical docs/output first, then refresh dashboard snapshots if values change.",
      readingRule:
        "Use this page as an audit surface for source paths, not as a place to introduce new research conclusions.",
      summary:
        "The route shows source lists, table preview slots, chart preview slots, and PNG viewers in the same layout used by the analysis detail pages.",
      sourcePaths: [
        "output/model_analysis/paper_result_assets/",
        "docs/experiment/analysis/model/",
        "dashboard/public/figures/"
      ],
      tablePreview: {
        title: "Bundled figure preview assets",
        columns: ["asset", "dashboard path", "role"],
        rows: [
          ["High-flow quantiles", "/figures/high-flow-quantiles.png", "primary preview"],
          ["Stress tradeoff", "/figures/stress-tradeoff.png", "stress preview"],
          ["Checkpoint sensitivity", "/figures/checkpoint-sensitivity.png", "diagnostic preview"]
        ],
        sourcePath: "dashboard/public/figures/"
      },
      chartPreview: {
        title: "Preview inventory",
        caption: "Small dashboard assets only; no full gallery or output tree is copied.",
        values: [
          { label: "figures", value: 5, tone: "good" },
          { label: "sources", value: 4, tone: "neutral" }
        ]
      },
      figurePreview: {
        title: "Checkpoint preview",
        src: "/figures/checkpoint-sensitivity.png",
        caption: "PNG viewer slot keeps aspect ratio and source boundary visible.",
        sourcePath:
          "output/model_analysis/paper_result_assets/figures/checkpoint_sensitivity_compact.png"
      }
    }
  ]
};

export function getDetailPage(slug: string) {
  return dashboardData.details.find((detail) => detail.slug === slug);
}
