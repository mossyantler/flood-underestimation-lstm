// Source: output/model_analysis/ 산출물 snapshot.
// canonical source-of-truth: output/, docs/experiment/analysis/, configs/

export type SectionId = "O" | "H" | "D" | "M" | "R" | "A" | "S" | "F";
export type QuantileId = "q50" | "q90" | "q95" | "q99";

export type KpiItem = {
  label: string;
  value: string;
  sub: string;
  accent: string;
};

export type EvidenceRow = {
  tag: "PRIMARY" | "TAIL" | "CAVEAT";
  value: string;
};

export type SectionIndexRow = {
  section: string;
  role: string;
  data: string;
  status: string;
  statusAccent: string;
};

export type CheckpointRow = {
  key: string;
  value: string;
};

export type ChartPoint = { x: number; y: number };

// ── 개요(O) KPI ───────────────────────────────────────────────
export const overviewKpis: KpiItem[] = [
  { label: "DRBC test", value: "38", sub: "quality-pass basins", accent: "#6bb4ff" },
  { label: "공식 seed", value: "3", sub: "111 / 222 / 444", accent: "#6bb4ff" },
  { label: "q99 과소추정", value: "44.9%", sub: "Q99 exceedance · seed median", accent: "#ffd166" },
];

export const evidenceRows: EvidenceRow[] = [
  { tag: "PRIMARY", value: "DRBC test 38 · paired seed 111/222/444" },
  { tag: "TAIL", value: "q99 exceedance 과소추정 72.6% → 44.9%" },
  { tag: "CAVEAT", value: "q99는 calibrated 99% interval 아님" },
];

// Q99 exceedance 과소추정률 by seed — 차트용 (x = seed index 0=111, 1=222, 2=444)
// 출처: flow_strata_predictor_summary.csv primary, stratum=basin_top1
export const q99ExceedanceData: Record<QuantileId, { m1: ChartPoint[]; m2: ChartPoint[] }> = {
  q50: {
    m1: [{ x: 0, y: 72.6 }, { x: 1, y: 64.8 }, { x: 2, y: 77.2 }],
    m2: [{ x: 0, y: 90.4 }, { x: 1, y: 86.7 }, { x: 2, y: 80.5 }],
  },
  q90: {
    m1: [{ x: 0, y: 72.6 }, { x: 1, y: 64.8 }, { x: 2, y: 77.2 }],
    m2: [{ x: 0, y: 71.2 }, { x: 1, y: 74.0 }, { x: 2, y: 63.3 }],
  },
  q95: {
    m1: [{ x: 0, y: 72.6 }, { x: 1, y: 64.8 }, { x: 2, y: 77.2 }],
    m2: [{ x: 0, y: 62.6 }, { x: 1, y: 68.0 }, { x: 2, y: 55.1 }],
  },
  q99: {
    m1: [{ x: 0, y: 72.6 }, { x: 1, y: 64.8 }, { x: 2, y: 77.2 }],
    m2: [{ x: 0, y: 44.0 }, { x: 1, y: 52.1 }, { x: 2, y: 38.8 }],
  },
};

export const sectionIndexRows: SectionIndexRow[] = [
  { section: "데이터셋", role: "split provenance", data: "subset300 / DRBC holdout", status: "확정", statusAccent: "#50e3c2" },
  { section: "모델", role: "head-only contrast", data: "M1 det. vs M2 q50–q99", status: "완료", statusAccent: "#50e3c2" },
  { section: "결과", role: "Q99 exceedance & peak hour", data: "seed 111/222/444", status: "완료", statusAccent: "#50e3c2" },
  { section: "분석", role: "event-regime + calibration", data: "570 events · 38 basins", status: "완료", statusAccent: "#50e3c2" },
  { section: "스트레스", role: "historical extreme-rain", data: "1980–2024 DRBC", status: "보조", statusAccent: "#6bb4ff" },
  { section: "확정홍수", role: "NWS flood-stage confirmed events", data: "623 events · 48 basins", status: "완료", statusAccent: "#50e3c2" },
];

export const checkpointRows: CheckpointRow[] = [
  { key: "고정 train pool", value: "subset300 (non-DRBC)" },
  { key: "paired seed", value: "111 / 222 / 444" },
  { key: "primary epoch 기준", value: "non-DRBC val. median NSE" },
  { key: "주의", value: "q99 ≠ calibrated 99% interval" },
];

// ── 모델(M) 섹션 ─────────────────────────────────────────────────
export type SeedPerformanceRow = {
  model: string;
  seed: string;
  epoch: number;
  nse: number;
  kge: number;
  fhv: number;
  peakMape: number;
  negNseCnt: number;
};

// 출처: primary_epoch_summary.csv
export const primaryPerformance: SeedPerformanceRow[] = [
  { model: "Model 1",    seed: "111", epoch: 25, nse:  0.264, kge:  0.323, fhv: -10.1, peakMape: 64.6, negNseCnt: 15 },
  { model: "Model 1",    seed: "222", epoch: 10, nse: -0.045, kge:  0.288, fhv:   9.5, peakMape: 65.9, negNseCnt: 21 },
  { model: "Model 1",    seed: "444", epoch: 15, nse:  0.075, kge:  0.030, fhv: -16.6, peakMape: 75.1, negNseCnt: 17 },
  { model: "Model 2 q50",seed: "111", epoch:  5, nse:  0.292, kge:  0.119, fhv: -51.7, peakMape: 74.7, negNseCnt:  9 },
  { model: "Model 2 q50",seed: "222", epoch: 10, nse:  0.229, kge:  0.112, fhv: -49.9, peakMape: 71.6, negNseCnt: 12 },
  { model: "Model 2 q50",seed: "444", epoch: 10, nse:  0.264, kge:  0.394, fhv: -27.5, peakMape: 70.3, negNseCnt: 12 },
];

// 출처: primary_epoch_delta_summary.csv
export type DeltaSummaryRow = { seed: string; nseDelta: number; nseImproved: number; kgeDelta: number };
export const nseDeltaSummary: DeltaSummaryRow[] = [
  { seed: "111", nseDelta: 0.109, nseImproved: 0.63, kgeDelta: -0.072 },
  { seed: "222", nseDelta: 0.201, nseImproved: 0.61, kgeDelta:  0.042 },
  { seed: "444", nseDelta: 0.246, nseImproved: 0.68, kgeDelta:  0.268 },
];

// ── 결과(R) 섹션 ─────────────────────────────────────────────────
export const resultsKpis: KpiItem[] = [
  { label: "Median NSE (M2 q50)", value: "0.264", sub: "seed-median of medians", accent: "#f7b955" },
  { label: "Q99 exceedance", value: "44.9%", sub: "과소추정률 · M2 q99 seed median", accent: "#50e3c2" },
  { label: "q99 spread", value: "74.6%", sub: "q99−q50 gap / obs · Q99 구간", accent: "#f7b955" },
];

export type HighFlowRow = {
  predictor: string;
  undestFrac: [number, number, number]; // seed 111 / 222 / 444
  medRelBias: [number, number, number];
};

// 출처: flow_strata_predictor_summary.csv primary, basin_top1
export const highFlowQ99: HighFlowRow[] = [
  { predictor: "Model 1",     undestFrac: [72.6, 64.8, 77.2], medRelBias: [-46.4, -35.7, -60.8] },
  { predictor: "M2 q50",      undestFrac: [90.4, 86.7, 80.5], medRelBias: [-72.1, -68.5, -61.0] },
  { predictor: "M2 q90",      undestFrac: [71.2, 74.0, 63.3], medRelBias: [-36.2, -42.2, -24.2] },
  { predictor: "M2 q95",      undestFrac: [62.6, 68.0, 55.1], medRelBias: [-21.7, -31.0, -10.2] },
  { predictor: "M2 q99",      undestFrac: [44.0, 52.1, 38.8], medRelBias: [+11.5,  -4.2, +30.0] },
];

// 출처: flow_strata_predictor_summary.csv primary, observed_peak_hour
export const peakHourRows: HighFlowRow[] = [
  { predictor: "Model 1",     undestFrac: [76.3, 71.1, 76.3], medRelBias: [-44.0, -27.8, -38.2] },
  { predictor: "M2 q50",      undestFrac: [89.5, 89.5, 68.4], medRelBias: [-69.0, -81.3, -33.1] },
  { predictor: "M2 q95",      undestFrac: [65.8, 78.9, 42.1], medRelBias: [-28.9, -45.4, +25.8] },
  { predictor: "M2 q99",      undestFrac: [55.3, 63.2, 31.6], medRelBias: [ -2.4, -28.2, +63.1] },
];

// ── 분석(A) 섹션 ─────────────────────────────────────────────────
export type EventRegimeRow = {
  regime: string;
  nEvents: number;
  q99UnderDeficitReduction: number;
  q99RecallDelta: number;
  q99NrmseNote: string;
};

// 출처: event_regime_paired_delta_compact.csv
export const eventRegimeRows: EventRegimeRow[] = [
  { regime: "Recent rainfall",             nEvents: 265, q99UnderDeficitReduction: 30.0, q99RecallDelta: 0.366, q99NrmseNote: "tradeoff +" },
  { regime: "Antecedent / multi-day rain", nEvents:  39, q99UnderDeficitReduction: 38.5, q99RecallDelta: 0.442, q99NrmseNote: "약함" },
  { regime: "Weak / low-signal hydromet",  nEvents: 266, q99UnderDeficitReduction: 35.4, q99RecallDelta: 0.401, q99NrmseNote: "중립" },
];

export type CalibrationRow = {
  quantile: string;
  nominalTau: number;
  allHourCoverage: number;
  q99ExceedanceCoverage: number;
  pinball: number;
};

// 출처: probabilistic_diagnostics_report.md
export const calibrationRows: CalibrationRow[] = [
  { quantile: "q50", nominalTau: 0.500, allHourCoverage: 0.272, q99ExceedanceCoverage: 0.133, pinball: 2.135 },
  { quantile: "q90", nominalTau: 0.900, allHourCoverage: 0.500, q99ExceedanceCoverage: 0.288, pinball: 2.267 },
  { quantile: "q95", nominalTau: 0.950, allHourCoverage: 0.658, q99ExceedanceCoverage: 0.374, pinball: 1.919 },
  { quantile: "q99", nominalTau: 0.990, allHourCoverage: 0.835, q99ExceedanceCoverage: 0.560, pinball: 1.243 },
];

// ── 스트레스(S) 섹션 ──────────────────────────────────────────────
export const stressKpis: KpiItem[] = [
  { label: "stress 이벤트", value: "236", sub: "historical 1980–2024", accent: "#ff6b8a" },
  { label: "q99 under-deficit 감소", value: "22.1%p", sub: "flood_response_ge25 기준", accent: "#ff6b8a" },
  { label: "false-positive proxy", value: "1.25×", sub: "q99 / ARI100 · 음성 대조", accent: "#ff6b8a" },
];

export type StressRow = {
  cohort: string;
  m1UnderDeficit: number;
  q99UnderDeficit: number;
  note: string;
};

export const stressRows: StressRow[] = [
  { cohort: "flood_response_ge25",  m1UnderDeficit: 72.0, q99UnderDeficit: 27.3, note: "positive-response · q99 강한 완화" },
  { cohort: "flood_response_lt25",  m1UnderDeficit: 62.0, q99UnderDeficit: 44.0, note: "약한 flood response" },
  { cohort: "negative_control",     m1UnderDeficit: 48.0, q99UnderDeficit: 20.0, note: "false-positive tradeoff 확인 필요" },
];

// ── 데이터셋(D) 섹션 ──────────────────────────────────────────────
export type DatasetRow = {
  split: string;
  basins: number;
  criteria: string;
  role: string;
};

export const datasetRows: DatasetRow[] = [
  { split: "Training pool", basins: 1923, criteria: "outlet ∉ DRBC · overlap ≤ 0.1 · quality gate", role: "Model 학습" },
  { split: "DRBC holdout",  basins:   38, criteria: "outlet ∈ DRBC · overlap ≥ 0.9 · quality-pass", role: "Primary test" },
  { split: "DRBC broad",    basins:  154, criteria: "outlet ∈ DRBC (outlet 기준만)", role: "참고용 전체" },
  { split: "subset300",     basins:  300, criteria: "non-DRBC train/val fixed subset", role: "공식 train/val" },
];
