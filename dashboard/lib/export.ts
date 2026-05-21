import {
  primaryPerformance, nseDeltaSummary,
  highFlowQ99, peakHourRows,
  eventRegimeRows, calibrationRows,
  stressRows, datasetRows,
} from "./dashboard-data";
import { confirmedFloodSnapshot } from "./confirmed-flood-data";

function toCsv(headers: string[], rows: (string | number)[][]): string {
  const escape = (v: string | number) => {
    const s = String(v);
    return s.includes(",") || s.includes("\n") ? `"${s}"` : s;
  };
  return [headers, ...rows].map((r) => r.map(escape).join(",")).join("\n");
}

export const SECTION_CSV: Record<string, { csv: string; filename: string }> = {
  overview: {
    filename: "camels_overview_kpi.csv",
    csv: toCsv(
      ["metric", "value", "note"],
      [
        ["DRBC test basins", 38, "quality-pass"],
        ["official seeds", 3, "111/222/444"],
        ["q99 underestimation fraction (seed median)", "0.449", "Q99 exceedance stratum"],
      ]
    ),
  },
  model: {
    filename: "camels_model_primary_performance.csv",
    csv: toCsv(
      ["model", "seed", "epoch", "median_NSE", "median_KGE", "median_FHV", "median_Peak_MAPE", "neg_NSE_count"],
      primaryPerformance.map((r) => [r.model, r.seed, r.epoch, r.nse, r.kge, r.fhv, r.peakMape, r.negNseCnt])
    ),
  },
  results: {
    filename: "camels_results_highflow_q99.csv",
    csv: toCsv(
      ["predictor", "undest_frac_111", "undest_frac_222", "undest_frac_444", "med_rel_bias_111", "med_rel_bias_222", "med_rel_bias_444"],
      highFlowQ99.map((r) => [r.predictor, ...r.undestFrac, ...r.medRelBias])
    ),
  },
  analysis: {
    filename: "camels_analysis_event_regime_calibration.csv",
    csv: [
      toCsv(
        ["regime", "n_events", "q99_under_deficit_reduction_pct", "q99_recall_delta", "q99_nrmse_note"],
        eventRegimeRows.map((r) => [r.regime, r.nEvents, r.q99UnderDeficitReduction, r.q99RecallDelta, r.q99NrmseNote])
      ),
      "",
      toCsv(
        ["quantile", "nominal_tau", "all_hour_coverage", "q99_exceedance_hit_rate", "pinball"],
        calibrationRows.map((r) => [r.quantile, r.nominalTau, r.allHourCoverage, r.q99ExceedanceCoverage, r.pinball])
      ),
    ].join("\n"),
  },
  stress: {
    filename: "camels_stress_cohort.csv",
    csv: toCsv(
      ["cohort", "m1_under_deficit_pct", "q99_under_deficit_pct", "note"],
      stressRows.map((r) => [r.cohort, r.m1UnderDeficit, r.q99UnderDeficit, r.note])
    ),
  },
  dataset: {
    filename: "camels_dataset_split.csv",
    csv: toCsv(
      ["split", "basins", "criteria", "role"],
      datasetRows.map((r) => [r.split, r.basins, r.criteria, r.role])
    ),
  },
  hydrograph: {
    filename: "camels_hydrograph_quantile_zone.csv",
    csv: toCsv(
      ["zone", "count", "fraction_pct", "note"],
      [
        ["> q99", 12574, 44.9, "Q99 exceedance rows above q99"],
        ["q95–q99", 4748, 17.0, ""],
        ["q90–q95", 2130, 7.6, ""],
        ["q50–q90", 4566, 16.3, ""],
        ["≤ q50", 3960, 14.2, "still underestimated"],
      ]
    ),
  },
  "confirmed-flood": {
    filename: "camels_confirmed_flood_event_snapshot.csv",
    csv: toCsv(
      [
        "event_id", "usgs_id", "peak_time", "flood_tier", "period", "noaa_type",
        "performance_type", "m1_under_deficit", "q99_under_deficit", "q99_reduction",
      ],
      confirmedFloodSnapshot.events.map((r) => [
        r.eventId, r.usgsId, r.peakTime, r.floodTier, r.period, r.noaaType,
        r.performanceType, r.m1Under ?? "", r.q99Under ?? "", r.q99Reduction ?? "",
      ])
    ),
  },
};

export const NSE_DELTA_CSV = toCsv(
  ["seed", "median_delta_NSE", "nse_improved_fraction", "median_delta_KGE"],
  nseDeltaSummary.map((r) => [r.seed, r.nseDelta, r.nseImproved, r.kgeDelta])
);

export const PEAK_HOUR_CSV = toCsv(
  ["predictor", "undest_frac_111", "undest_frac_222", "undest_frac_444", "med_rel_bias_111", "med_rel_bias_222", "med_rel_bias_444"],
  peakHourRows.map((r) => [r.predictor, ...r.undestFrac, ...r.medRelBias])
);
