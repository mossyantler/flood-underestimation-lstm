# Expanded DRBC Rebuild — Execution Plan (Iteration 2, consensus-revised)

**Plan ID:** `2026-05-26-expanded-drbc-rebuild-execution`
**Spec source:** `/Users/jang-minyeop/Project/CAMELS/.omc/specs/deep-interview-expanded-drbc-rebuild.md`
**Status:** **PENDING APPROVAL** — consensus complete (Architect iteration 1 → 5 revisions; Critic iteration 1 → 4 revisions + NOAA count correction; iteration 2 applied 20 revisions; Critic iteration 2 VERDICT: APPROVED)
**Date:** 2026-05-26
**Scope:** Phase A + Phase B + Phase C from locked spec. No GPU, no training, no re-inference.

---

## 0. RALPLAN-DR Short-Mode Summary

### Principles (5)

1. **Rebuild from scratch is locked.** RQ-A~G assumptions, IQR-distance tier as primary cohort, scaling_300 / DRBC-38 holdout references — all discarded.
2. **Framework precedes empirical metrics.** RQ-0 framework gates the meaning of every Phase B metric. **Phase C0 (vocabulary lock in `_lib.py` constants) precedes Phase B execution** to enforce this.
3. **No GPU dependency, no re-training, no re-inference.** Phase A/B consume on-disk artifacts only.
4. **Q99 single-threshold; NOAA dual scope.** Per-basin train-period (2000-2010) obs Q99 = canonical threshold for all 85 basins. NOAA confirmed flood (49-basin actual count, see §4 B2) parallel.
5. **Author/review separation.** Phase C docs author narrative; sanity-check sub-step under each Phase A/B item is a separate verification pass.

### Top 3 Decision Drivers

1. **Local MacBook execution constraint.** No GPU. CPU pandas/numpy.
2. **Expanded DRBC observed test (85 basins, seeds 111/222/444) as sole canonical split.**
3. **Interpretation framework as standalone RQ-0** with `_lib.py` vocabulary lock.

### Substantive Design Choice — Script Organization (revised)

**Option A — Per-RQ scripts under `scripts/model/expanded_drbc/` + shared helper at `scripts/_lib/expanded_drbc.py`.**
- Pros: Clean 1:1 RQ-to-doc mapping; matches existing `scripts/_lib/` convention for shared helpers (per `scripts/AGENTS.md`); reused RQ-5 script can also import.
- Cons: New sibling directory; one shared helper module.

**Option B — Extend `scripts/model/hydrograph/analyze_expanded_drbc_*` pattern.**
- Pros: Existing `analyze_expanded_drbc_probabilistic_diagnostics.py:35` already imports `analyze_subset300_probabilistic_diagnostics as base` — preserving helper-sharing pattern.
- Cons: `hydrograph/` misnames non-hydrograph outputs; mixed-purpose dir grows to ~13 files.

**Recommendation (locked): Option A** with helper at `scripts/_lib/expanded_drbc.py` (per `scripts/AGENTS.md` convention, not `scripts/model/expanded_drbc/_lib.py`). The reused `analyze_expanded_drbc_probabilistic_diagnostics.py` (RQ-5) imports the helper for vocabulary constants only. Asymmetry rationale: RQ-5 outputs already on disk and stable; no rewrite needed. Plan-wide single helper closes Architect tension #1.

---

## 1. Inputs (on-disk, verified by Critic empirically)

| Asset | Path | Confirmed |
|---|---|---|
| Required series (per seed) | `output/model_analysis/expanded_drbc_test/required_series/seed{111,222,444}/primary_required_series.csv` | columns: `seed, basin, obs, model1, q50, q90, q95, q99, ...` (Critic verified) |
| Raw metrics (per seed × model × epoch) | `output/model_analysis/expanded_drbc_test/raw_metrics/model{1,2}_seed*_epoch*.csv` | columns: `model, seed, split, epoch, run_name, frequency, basin, NSE, KGE, FHV, Peak-Timing, Peak-MAPE` (Critic verified — **no bias/MAE/RMSE**) |
| RQ-5 source (reuse as-is) | `output/model_analysis/expanded_drbc_test/probabilistic_diagnostics/*` | (no rewrite) |
| NOAA catalog | `output/model_analysis/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv` | 664 rows total, 49 unique `usgs_id` (Critic verified — spec's 48 was wrong) |
| Train-period obs source | `data/CAMELSH_generic/drbc_expanded_observed_test/` | NetCDF, 85 basin, hourly |
| Framework doc (RQ-0) | `docs/experiment/method/model/quantile_output_interpretation.md` | locked |
| Shared helper (NEW) | `scripts/_lib/expanded_drbc.py` | follows `scripts/_lib/camelsh_flood_analysis_utils.py` precedent |

---

## 2. Dependency Graph

```
C0 (vocab lock in _lib.py) ───► [Phase B unblocked]
                                        │
A1 ──────────────────────────────────────┤
                                         ▼
B1 (Q99 events 85)  ─┬─► B3 α ─┐         B7 (NSE-tier; aggregates from B3/B4/B5/B6)
                     ├─► B4 β ─┤         ▲
                     ├─► B5 δ ─┤         │ (A1)
                     └─► B6 cost ────────┘
                                         ▼
B2 (NOAA mapping 49 → expanded overlap N) ┬─► B3 α-NOAA ┐
                                          ├─► B4 β-NOAA ┤  B8 (event-type)
                                          ├─► B6 NOAA  ─┤
                                          └─► B9 (cross-tab) ◄── B1
                                                            ▼
                                                     C1, C2, C3, C4
```

- **C0 (NEW)** precedes Phase B. Lightweight — locks label vocabulary constants, regex patterns, aggregation-order utilities in `scripts/_lib/expanded_drbc.py`.
- **A1** independent (after C0).
- **B1, B2** independent (after C0).
- **B7** depends on A1 + B3/B4/B5/B6 (aggregates per-basin tables, does NOT re-derive from required_series).
- **B8** depends on B2 + B3 + B4 + B6.
- **B9** depends on B1 + B2.
- **Phase C1-C4** runs after all Phase A/B tables exist.

---

## 3. Phase C0 — Vocabulary Lock (precedes Phase B)

### C0.1 — Create `scripts/_lib/expanded_drbc.py`

Lock the following as module-level constants and utilities. Phase B scripts MUST import from this module (no inline redefinition).

```python
# Constants
TAU_ORDER = ["model1", "q50", "q90", "q95", "q99"]
PREDICTION_COLUMNS = {"model1": "model1", "q50": "q50", "q90": "q90", "q95": "q95", "q99": "q99"}
TRAIN_PERIOD = ("2000-01-01", "2010-12-31")
TEST_PERIOD = ("2014-01-01", "2016-12-31")
EVENT_WINDOW_HOURS = 6        # ±6h window
EVENT_MERGE_GAP_HOURS = 12    # Merge peaks closer than this
HIGH_FLOW_PERCENTILE = 0.99   # Q99
SEEDS = (111, 222, 444)

# NOAA canonical labels (Critic-verified empirical lexicon — Riverine/Ice Jam REMOVED)
NOAA_LABELS = ("Flash Flood", "Flood", "Coastal Flood", "Other")
NOAA_REGEX = {
    "Flash Flood":   r"\bFlash Flood(?!\s+(Watch|Advisory))\b",
    "Flood":         r"(?<!Flash )\bFlood(?!\s+(Watch|Advisory))\b",
    "Coastal Flood": r"\bCoastal Flood\b",
}
NOAA_TIE_BREAK = ("Flash Flood", "Coastal Flood", "Flood", "Other")  # Most-specific wins

# Basin id normalization (Critic finding #4 + Architect #2)
def normalize_basin_id(raw: str) -> str:
    """Strip whitespace, zfill to 8 chars (matches CAMELSH convention)."""
    return str(raw).strip().zfill(8)

# Aggregation order (Architect #1 + Critic concur)
def per_basin_seed_then_median(
    df, *, value_col, basin_col="basin_id", seed_col="seed"
):
    """Canonical aggregation: compute value per-basin per-seed → median across seeds within basin.
    Returns DataFrame indexed by basin_col with one value column (median across seeds)."""
    return df.groupby([basin_col, seed_col])[value_col].first().groupby(basin_col).median()

def paired_delta_per_seed(df_m1, df_m2, *, value_col, basin_col="basin_id", seed_col="seed"):
    """Compute delta(M2 q50 − M1) per-basin per-seed; do NOT pre-aggregate either side.
    Returns DataFrame [basin_col, seed_col, delta] with one row per basin × seed.
    Downstream callers median-aggregate across seeds within basin via per_basin_seed_then_median."""
    m1 = df_m1.set_index([basin_col, seed_col])[value_col]
    m2 = df_m2.set_index([basin_col, seed_col])[value_col]
    return (m2 - m1).reset_index(name="delta")

# NaN policy (Critic gap)
def filter_valid_rows(df, *, obs_col="obs", pred_cols=("model1","q50","q90","q95","q99")):
    """Drop rows where obs is NaN. Pred-NaN rows are kept (each metric drops NaN individually)."""
    return df.dropna(subset=[obs_col])
```

**Acceptance:**
- `scripts/_lib/expanded_drbc.py` exists with all listed constants and utilities.
- Importable from both `scripts/model/expanded_drbc/*.py` and `scripts/model/hydrograph/analyze_expanded_drbc_probabilistic_diagnostics.py` (smoke-test import).
- All Phase B scripts have `from camels._lib.expanded_drbc import ...` (or relative `from ..._lib.expanded_drbc import ...`) at top.

**Verification:**
- `python -c "from scripts._lib.expanded_drbc import TAU_ORDER, NOAA_LABELS, normalize_basin_id, per_basin_seed_then_median"` exits 0.
- Vocabulary frozen — any change after Phase B starts requires plan revision.

**MacBook feasibility:** trivial.

---

## 4. Phase A — PARTIAL 보강

### A1 — RQ-1 central metric set 보강

- **Script:** `scripts/model/expanded_drbc/compute_rq1_central_metrics.py` (NEW)
- **Inputs:**
  - `required_series/seed{111,222,444}/primary_required_series.csv` (obs, model1, q50)
  - `raw_metrics/model{1,2}_seed*_epoch*.csv` (NSE/KGE cross-check only — Critic confirmed bias/MAE/RMSE absent)
- **Work:**
  - Recompute NSE, KGE per basin per seed (cross-check against raw_metrics — should match within 1e-6).
  - **Compute new metrics from required_series:** bias = `mean(pred − obs)`, MAE = `mean(|pred − obs|)`, RMSE = `sqrt(mean((pred − obs)^2))`. Pred ∈ {M1, M2 q50}.
  - NaN policy: drop rows where obs is NaN (per C0).
  - **Aggregation order (C0):** per-basin per-seed compute → seed-median per basin → cross-basin pooled summary.
  - **Paired delta:** compute Δ_seed = `metric(M2_q50, seed) − metric(M1, seed)` per basin per seed; then `median_seed(Δ_seed)`. NOT `metric(median(M2_q50)) − metric(median(M1))`.
- **Outputs (wide-form per-basin-seed table):**
  - `tables/rq1_central_metrics_per_basin_seed.csv` — `basin_id, seed, model, nse, kge, bias, mae, rmse` (wide: 5 metric cols × 510 rows = 85×3×2)
  - `tables/rq1_central_metrics_seed_median.csv` — `basin_id, metric, model1, model2_q50, delta_m2_minus_m1` (long: 425 rows = 85×5)
  - `tables/rq1_central_metrics_pooled_summary.csv` — `metric, model1_basin_median, model2_q50_basin_median, delta_basin_median, delta_basin_iqr_low, delta_basin_iqr_high`
  - `figures/rq1_central_metric_boxplots.png`
  - `figures/rq1_paired_delta_scatter.png`
- **Acceptance:**
  - 510 rows in wide-form per-basin-seed table, all 5 metric columns populated.
  - 425 rows in seed-median table.
  - CSV header comment documents: sign convention (bias = mean(pred − obs); MAE/RMSE ≥ 0), aggregation order (per-seed delta then median), NaN policy.
- **Verification (Critic #7 expansion):**
  - NSE/KGE: spot 5 basins, compare new script vs `raw_metrics/model1_seed111_epoch025_metrics.csv` within 1e-6.
  - **bias/MAE/RMSE: NumPy hand-compute for 2 random basins on each metric** (since raw_metrics lacks these columns).
  - Pooled bias for M1 expected slightly negative.
  - Explicitly state B7 uses the **new A1 NSE** (not raw_metrics NSE) for tier assignment.
- **MacBook feasibility:** ~5 min, <1 GB RAM.

---

## 5. Phase B — MISSING 신규

### B1 — Q99 threshold + Q99 exceedance events

- **Script:** `scripts/model/expanded_drbc/build_q99_events.py`
- **Inputs:** `data/CAMELSH_generic/drbc_expanded_observed_test/` (train obs NetCDF), `required_series/seed111/primary_required_series.csv` (canonical test obs).
- **Work:**
  - Per-basin Q99 over train period `TRAIN_PERIOD` (C0 constant), excluding NaN obs (C0 policy).
  - Test-period (C0 `TEST_PERIOD`) local peaks where `obs ≥ Q99_basin`. Merge peaks closer than `EVENT_MERGE_GAP_HOURS=12` (C0).
  - Window `[peak − EVENT_WINDOW_HOURS, peak + EVENT_WINDOW_HOURS]` (C0).
  - **Edge handling (Critic gap):** test-period boundary windows are truncated to test-period extent; record `window_truncated: bool`.
- **Outputs:**
  - `tables/rq2_q99_per_basin_thresholds.csv` — `basin_id, q99_train_value, train_n_hours, n_test_exceedance_events`
  - `tables/rq2_q99_events_85basin.csv` — `basin_id, event_id, peak_time, peak_obs, window_start, window_end, window_truncated`
- **Acceptance:**
  - 85 rows in thresholds table.
  - Sum of `n_test_exceedance_events` = row count in events table.
  - Every untruncated event window = 13 hours; truncated windows ≥ 7h.
  - WARN if any basin has 0 events (acceptance does NOT fail; documented in `tables/rq2_q99_basin_warnings.csv`).
- **Verification:**
  - 3 basins: manual Q99 from NetCDF train slice vs CSV, 1e-3 relative tolerance.
  - Event count per basin expected 5-40.
  - Boundary basin (event near 2014-01-01 00:00 or 2016-12-31 23:00) checked for truncation correctness.
- **MacBook feasibility:** ~5 min, ~2 GB.

### B2 — NOAA event mapping + dominant event-type parsing (HEAVILY REVISED)

- **Script:** `scripts/model/expanded_drbc/build_noaa_mapping.py`
- **Inputs:** `confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv`, `data/CAMELSH_generic/drbc_expanded_observed_test/` (canonical 85-basin id list).
- **Work (revised per Critic #1 + #6 + Architect #2):**
  - **Sub-step 0 — ID normalization (Architect #2 + Critic concur):** apply `normalize_basin_id` (C0) to both NOAA `usgs_id` and expanded basin id list. Emit `tables/rq2_id_normalization_report.csv` with columns `source, raw_id, normalized_id, matched`. Acceptance: zero rows where `matched == False AND raw_id appears in either source` after normalization.
  - **Sub-step 1 — Overlap computation:** intersection of normalized NOAA-49 ∩ expanded-85 (Critic-verified NOAA count = 49 unique `usgs_id`, NOT 48 as in spec).
  - **Sub-step 2 — Annotation parsing (Critic #6 + #1):** apply `NOAA_REGEX` (C0) to `noaa_annotation`. Each event gets a multi-label hit count. `dominant_event_type` = label with highest token count, ties broken by `NOAA_TIE_BREAK` (most-specific wins: Flash Flood > Coastal Flood > Flood > Other).
  - **Sub-step 3 — Unmatched annotation artifact (Architect #3):** emit `tables/rq4b_noaa_annotation_unmatched.csv` (full string for any row that produced zero hits across all regex patterns).
- **Outputs:**
  - `tables/rq2_id_normalization_report.csv`
  - `tables/rq2_noaa_basin_overlap_summary.csv` — columns: `n_noaa_basins, n_expanded_basins, n_overlap, n_noaa_only, n_expanded_only`
  - `tables/rq2_noaa_events_expanded_overlap.csv` — `basin_id, event_id, peak_time, peak_obs, window_start, window_end, in_expanded_85, noaa_annotation, dominant_event_type, flood_tier, window_truncated`
  - `tables/rq4b_event_type_mapping.csv` — `event_type, n_events, n_basins`
  - `tables/rq4b_noaa_annotation_unmatched.csv`
- **Acceptance (Architect #3 + Critic #6):**
  - `n_noaa_basins` empirically computed (expected 49; if different, document and proceed).
  - All `in_expanded_85` ∈ {True, False}; `dominant_event_type` populated.
  - **Unmatched annotation count / total annotation count < 5%** (Architect threshold).
  - **Expected label counts (Critic empirical): Flash Flood ≥ 500 hits, Flood ≥ 100 hits, Coastal Flood ≥ 5 hits, Other < 50** (across all catalog rows, not events).
  - Event-type categories sum to 100% of overlapping events.
- **Verification:**
  - 5 random `noaa_annotation` strings hand-parsed.
  - Check overlap basin list contains expected DRBC-region USGS ids (spot check 3).
  - **If unmatched > 5%, B2 acceptance FAILS** — return to plan revision before continuing Phase B.
- **MacBook feasibility:** <1 min.

### B3 — RQ-2 α event peak under-deficit

- **Script:** `scripts/model/expanded_drbc/compute_rq2_alpha_peak_deficit.py`
- **Inputs:** B1 events (85 scope), B2 events filtered to `in_expanded_85 == True` (NOAA scope), required_series per seed.
- **Work:**
  - At each event's `peak_time`, read `model1_pred, q50, q90, q95, q99` per seed.
  - `peak_under_deficit_τ = max(0, (obs_peak − q_τ_at_peak)) / obs_peak` for τ ∈ TAU_ORDER (C0).
  - NaN policy: drop event if `obs_peak` is NaN; pred-NaN sets that τ row to NaN (other τ still computed).
  - **Aggregation order (C0):** per-event basin × seed × τ → median across events within basin → median across seeds within basin → cross-basin median+IQR.
- **Outputs:**
  - `tables/rq2_alpha_event_peak_deficit_q99.csv` — `basin_id, seed, event_id, tau, peak_under_deficit`
  - `tables/rq2_alpha_event_peak_deficit_q99_summary.csv` — `tau, n_basins, n_events, basin_median_of_event_median, basin_iqr_low, basin_iqr_high`
  - `tables/rq2_alpha_event_peak_deficit_noaa.csv`
  - `tables/rq2_alpha_event_peak_deficit_noaa_summary.csv`
  - `figures/rq2_alpha_by_tau.png`
- **Acceptance (Architect #4):**
  - Q99-scope full table: 85 basins × 3 seeds × ≥1 event × 5 τ.
  - **Cross-basin-median monotonicity:** median across basins is non-increasing in τ (M1 → q50 → q90 → q95 → q99).
  - **Per-basin violation rate:** fraction of basins where per-basin median violates τ-monotonicity must be `< 20%` (else flagged in C2). Quantile crossing already expected per RQ-5, so per-basin violations are NOT acceptance failures.
  - All values in [0, 1].
- **Verification:**
  - 1 event hand-checked.
  - Per-basin violation rate reported in summary CSV.
  - NOAA scope basin count = B2 overlap subset.
- **MacBook feasibility:** ~5 min.

### B4 — RQ-2 β ±6h window peak capture

- **Script:** `scripts/model/expanded_drbc/compute_rq2_beta_window_capture.py`
- **Inputs:** same as B3.
- **Work:**
  - `window_capture_τ = max(q_τ in window) / max(obs in window)`.
  - **Obs > 0 filter (Critic ambiguity):** if `max(obs in window) ≤ 0`, drop the event from this metric (regulated basins with zero/negative observations).
  - Aggregation order per C0.
- **Outputs:**
  - `tables/rq2_beta_window_capture_q99.csv` + summary
  - `tables/rq2_beta_window_capture_noaa.csv` + summary
  - `figures/rq2_beta_by_tau.png`
- **Acceptance (Critic #8):**
  - Capture ratio: flag basins where `max(q_τ window) > 2 × max(obs window)` (tightened from arbitrary "5").
  - Same row count as B3 modulo zero-obs filter (report drop count in CSV).
- **Verification:**
  - Spot-check one event window slice.
  - If α ≈ 0 for an event then β ≥ 1 (timing-modulo).
- **MacBook feasibility:** ~10 min.

### B5 — RQ-2 δ Q99 threshold recall

- **Script:** `scripts/model/expanded_drbc/compute_rq2_delta_threshold_recall.py`
- **Inputs:** B1 thresholds, required_series.
- **Work:**
  - Pooled across TEST_PERIOD hours where `obs ≥ Q99_basin`:
    - `recall_τ = P(q_τ ≥ obs | obs ≥ Q99_basin)` per-basin per-seed per τ.
  - **n_q99_hours assertion:** verify obs identical across seeds for each basin (Critic gap); if not, fail with assertion error.
  - Median across seeds within basin, then median across basins.
- **Outputs:**
  - `tables/rq2_delta_threshold_recall_per_basin_seed.csv` — `basin_id, seed, tau, n_q99_hours, n_hits, recall`
  - `tables/rq2_delta_threshold_recall_summary.csv` — `tau, basin_median_recall, basin_iqr_low, basin_iqr_high, total_q99_hours`
  - `figures/rq2_delta_recall_by_tau.png`
- **Acceptance:**
  - Recall in [0, 1].
  - `n_q99_hours` identical across seeds per basin (assertion).
  - Definition: denominator counts **test-period (2014-2016) hours only** where obs ≥ Q99 (Critic gap clarification).
  - Expected: `recall_M1 ≤ recall_q50 ≤ recall_q90 ≤ recall_q95 ≤ recall_q99` (cross-basin median; per-basin violations OK).
- **Verification:**
  - Total `n_q99_hours` across basins ≈ 22-25k.
  - Hand-compute one basin recall.
- **MacBook feasibility:** ~5 min.

### B6 — RQ-3 cost (FAR + over-prediction magnitude)

- **Script:** `scripts/model/expanded_drbc/compute_rq3_cost.py`
- **Inputs:** B1 thresholds + required_series.
- **Work:**
  - `FAR_τ = P(q_τ > Q99_basin | obs < Q99_basin)` per-basin per-seed per τ.
  - `over_pred_magnitude_τ = mean(q_τ − obs | q_τ > obs)` per-basin per-seed per τ.
  - NaN policy: drop rows with NaN obs.
  - Aggregation order per C0.
- **Outputs:**
  - `tables/rq3_far_per_basin_seed.csv`
  - `tables/rq3_far_summary.csv`
  - `tables/rq3_over_prediction_magnitude_per_basin_seed.csv`
  - `tables/rq3_over_prediction_magnitude_summary.csv`
  - `figures/rq3_cost_recall_tradeoff.png`
- **Acceptance:**
  - `FAR_τ ∈ [0, 1]`.
  - Cross-basin median: `FAR_M1 ≤ FAR_q50 ≤ FAR_q90 ≤ FAR_q95 ≤ FAR_q99`.
  - Over-pred mag ≥ 0.
- **Verification:**
  - Non-Q99 hours ≈ 99% × test hours per basin.
  - Tradeoff scatter (FAR vs δ recall) shows Pareto-like curve.
- **MacBook feasibility:** ~5 min.

### B7 — RQ-4a M1 NSE 3-tier cohort (Architect #4 reword)

- **Script:** `scripts/model/expanded_drbc/compute_rq4a_nse_tier_stratify.py`
- **Inputs:** A1 `rq1_central_metrics_seed_median.csv` (M1 NSE seed-median per basin) + B3/B4/B5/B6 **per-basin tables** (NOT required_series — B7 is pure aggregation).
- **Work (Architect #4):**
  - **Tier boundaries:** `pd.qcut(m1_nse_seed_median, q=3, labels=['bottom','mid','top'], duplicates='raise')`. Tie-breaking deterministic via qcut. If `duplicates='raise'` fails (rare for continuous NSE), fall back to `np.quantile([1/3, 2/3])` + manual binning, documented.
  - Per tier: **aggregate** α median, β median, δ median, FAR median, over-pred median per τ from B3/B4/B5/B6 per-basin tables. (NOT recompute from required_series.)
- **Outputs:**
  - `tables/rq4a_nse_tier_assignments.csv` — `basin_id, m1_nse_seed_median, tier`
  - `tables/rq4a_nse_tier_metrics.csv` — `tier, tau, alpha_median, beta_median, delta_median, far_median, over_pred_median, n_basins`
  - `figures/rq4a_tier_metric_heatmap.png`
- **Acceptance:**
  - Tier sizes 28/29/28 (or document `qcut` rounding).
  - All 5 metrics × 3 tiers × 5 τ populated.
- **Verification:**
  - Tier boundaries match `pd.qcut` deciles.
  - Bottom tier expected to show strongest M2 q90/95/99 alleviation vs M1.
- **MacBook feasibility:** <2 min.

### B8 — RQ-4b NOAA event-type cohort

- **Script:** `scripts/model/expanded_drbc/compute_rq4b_event_type_stratify.py`
- **Inputs:** B2 mapping, NOAA-scope outputs from B3/B4/B6.
- **Work:**
  - Group events by `dominant_event_type` (Flash Flood / Flood / Coastal Flood / Other). Groups with `< 5 events` → "Other".
  - Per group: α median, β median (event-level), FAR/over-pred (per-basin subset).
- **Outputs:**
  - `tables/rq4b_event_type_metrics.csv` — `event_type, tau, n_events, n_basins, alpha_median, beta_median, far_median_basin_subset, over_pred_median_basin_subset`
  - `figures/rq4b_event_type_bar.png`
- **Acceptance:**
  - `n_events` sum across types per τ = NOAA-scope event count in B3.
  - "Other" row present even if empty.
- **Verification:**
  - Flash Flood subset vs B3 NOAA on one basin.
- **MacBook feasibility:** <2 min.

### B9 — Cross-tab Q99 ∩ NOAA sanity

- **Script:** `scripts/model/expanded_drbc/compute_cross_tab_q99_noaa_sanity.py` (renamed per Critic minor)
- **Inputs:** B1 events + B2 NOAA events (overlap basins).
- **Work (Critic ambiguity):**
  - **Geometry locked:** "NOAA inside Q99 window" = NOAA `peak_time` falls within `[Q99_event.window_start, Q99_event.window_end]`. NOT "within 6h of Q99 peak" — use window directly.
  - Per overlap basin: classify NOAA event peak times vs Q99 events.
    - NOAA inside any Q99 window → "both"
    - NOAA outside all Q99 windows → "noaa_only"
    - Q99 event with no NOAA event peak_time inside its window → "q99_only" (window geometry locked; no 12h secondary buffer)
  - Fractions per basin + pooled.
- **Outputs:**
  - `tables/cross_tab_q99_noaa_sanity_per_basin.csv` — `basin_id, n_q99_events, n_noaa_events, n_both, n_noaa_only, n_q99_only, frac_noaa_in_q99, frac_q99_in_noaa`
  - `tables/cross_tab_q99_noaa_sanity_pooled.csv`
- **Acceptance:**
  - Row count = overlap basin count from B2.
  - Pooled `n_both + n_noaa_only` = total NOAA-overlap events.
- **Verification:**
  - Hypothesis: `frac_noaa_in_q99 < 0.5` plausible; `> 0.9` flags Q99 too low.
  - One basin manual check.
- **MacBook feasibility:** <1 min.

---

## 6. Phase C — Documents (after Phase A + B complete)

### C1 — Rewrite `00_research_question_analysis_map.md`

- **Target:** `docs/experiment/analysis/model/00_research_question_analysis_map.md`
- **Action:** Rewrite in place (currently Untracked per `git status`). Replace RQ-A~G with RQ-0/1/2/3/4a/4b/5. Strip `scaling_300` / `DRBC-38 holdout`.
- **Synthesis section (Critic stakeholder note):** Add §"Body vs Supplement" + §"Synthesis: how B3/B4/B5/B6/B7/B8/B9 integrate" — explicit narrative arc tying recall(B5)+α(B3)+β(B4) to peak alleviation claim, FAR+over-pred(B6) to cost claim, tier(B7)+event-type(B8) to heterogeneity claim, cross-tab(B9) as sanity.
- **Acceptance:** 7 RQs listed; only Phase A/B tables referenced; synthesis section present.
- **Verification:** grep tokens (see §8).

### C2 — Extend `quantile_output_interpretation.md`

- **Target:** `docs/experiment/method/model/quantile_output_interpretation.md`
- **Action:** Splice "Expanded DRBC application" section. Keep L1-L4 + Pairwise/Sequence/Spread + 6 prohibited byte-equivalent. Replace RQ-mapping table with new IDs. Inspect existing structure first (Architect note — edit may be larger than append).
- **Acceptance:** RQ-mapping table uses new IDs only; 6-prohibited section byte-equivalent.
- **Verification:** diff confirms structural sections preserved.

### C3 — Reorganize `docs/experiment/analysis/model/01-10_*.md`

| Current | Decision | New name / location |
|---|---|---|
| `00_research_question_analysis_map.md` | rewrite (C1) | (in place) |
| `01_primary_overall_performance.md` | rewrite → RQ-1 | `01_q50_central.md` |
| `02_primary_high_flow_peak_performance.md` | rewrite → RQ-2 | `02_upper_quantile_peak_under.md` |
| `03_event_regime_performance.md` | archive | `docs/archive/analysis_legacy/03_event_regime_performance.md` |
| `04_extreme_flood_proxy_performance.md` | archive | `docs/archive/analysis_legacy/04_extreme_flood_proxy_performance.md` |
| `05_extreme_rain_stress_test.md` | archive | `docs/archive/analysis_legacy/05_extreme_rain_stress_test.md` |
| `06_checkpoint_sensitivity.md` | archive | `docs/archive/analysis_legacy/06_checkpoint_sensitivity.md` |
| `07_broad_vs_natural_robustness.md` | archive | `docs/archive/analysis_legacy/07_broad_vs_natural_robustness.md` |
| `08_probabilistic_calibration_pinball.md` | rewrite → RQ-5 (C4) | `05_calibration_sharpness.md` |
| `09_event_suppression_diagnosis_protocol.md` | archive | `docs/archive/analysis_legacy/09_event_suppression_diagnosis_protocol.md` |
| `10_event_surrogate_shap.md` | archive | `docs/archive/analysis_legacy/10_event_surrogate_shap.md` |
| `subset300_hydrograph_interpretation_report.md` | archive | `docs/archive/analysis_legacy/subset300_hydrograph_interpretation_report.md` |
| (NEW) | create | `03_cost.md` |
| (NEW) | create | `04a_basin_cohort.md` |
| (NEW) | create | `04b_event_type.md` |

- **Archive subfolder (Critic #4):** `docs/archive/analysis_legacy/` (NEW subdir, follows `docs/archive/proposals/` precedent). Avoids flat-archive convention violation.
- **Rename:** `git mv`. Then rewrite content.
- **Dashboard impact (Architect T5):** **Before** C3 git-mv: `grep -rln "01_primary_overall_performance\|02_primary_high_flow\|03_event_regime\|04_extreme_flood_proxy\|05_extreme_rain\|06_checkpoint\|07_broad_vs_natural\|08_probabilistic_calibration\|09_event_suppression\|10_event_surrogate\|subset300_hydrograph_interpretation" dashboard/lib/ scripts/dashboard/`. Any hit = C3 sub-task to update references. Acceptance: hit count is 0 after C3 completes.
- **Acceptance:** active `docs/experiment/analysis/model/` contains exactly: `00`, `01_q50_central`, `02_upper_quantile_peak_under`, `03_cost`, `04a_basin_cohort`, `04b_event_type`, `05_calibration_sharpness`, `README.md`.
- **Verification:** `ls docs/experiment/analysis/model/*.md | wc -l` = 8; `git log --diff-filter=R --name-status` shows renames not deletes; dashboard grep = 0 hits.

### C4 — Absorb `08_*` Phase 1 stub into RQ-5 (Critic #9)

- **Target:** `docs/experiment/analysis/model/05_calibration_sharpness.md` (post-C3 rename).
- **Sub-step 0 (NEW — Critic #5):** Inspect `git diff docs/experiment/analysis/model/08_probabilistic_calibration_pinball.md` (currently Modified, uncommitted). Decision tree:
  - If uncommitted edits include scaling_300 baseline content → discard via `git restore`.
  - If uncommitted edits add expanded DRBC Phase 1 stub content → **commit first** with message `"docs: snapshot 08 phase 1 stub before C4 absorb"`, then proceed to rewrite.
  - Same inspection for `README.md` (also Modified per `git status`).
  - Record chosen path in commit message.
- **Action:** Promote stub to full RQ-5 chapter. Cite `probabilistic_diagnostics/*`. Drop scaling_300 baseline section. Add sub-sections: coverage (one-sided) / pinball / AQS / upper-tail spread / quantile crossing / climatology skill / peak event capture.
- **Acceptance:** No "Phase 1 stub" header; all 7 RQ-5 sub-metrics present; no scaling_300 text.
- **Verification:** grep tokens (see §8).

---

## 7. Cross-Cutting Acceptance Criteria

- **Reproducibility:** Every Phase B script (excluding reused RQ-5) accepts `--input-dir`, `--output-dir`, `--seeds` (matching `analyze_expanded_drbc_probabilistic_diagnostics.py` convention) with sensible defaults. **Exception (Critic #8):** the reused RQ-5 script `analyze_expanded_drbc_probabilistic_diagnostics.py` is exempt from any new CLI requirement; it keeps its existing `--input-dir / --output-dir / --seeds` signature.
- **Seed handling:** per-basin-per-seed table includes `seed` column. Summary tables document aggregator in CSV header comment.
- **No path leakage:** Phase B outputs only under `output/model_analysis/expanded_drbc_test/`.
- **No legacy contamination:** No artifact references `scaling_300`, `subset_300`, `drbc_holdout` (the 38-basin variant). Valid paths: `drbc_expanded_observed_test`, `drbc_holdout_confirmed_flood_events`.
- **Header convention:** Every new script docstring lists RQ ID, inputs, outputs, expected runtime, NaN policy ref to C0.

---

## 8. Verification (per-phase rollup with explicit grep tokens)

| Phase | Manual sample-check | Sanity counter | Range check |
|---|---|---|---|
| C0 | smoke import test | constants/utilities all importable | — |
| A1 | 5 NSE/KGE vs raw_metrics 1e-6; **2 basins NumPy bias/MAE/RMSE 1e-6** | 510-row wide + 425-row long | bias sign |
| B1 | 3 basins hand Q99 | 85 thresholds; events table sum = thresholds count | events 5-40 per basin |
| B2 | 5 NOAA strings hand-parsed | overlap basin count empirically locked (49 ∩ 85) | **unmatched < 5%**; Flash≥500 / Flood≥100 / Coastal≥5 / Other<50 |
| B3 | 1 event hand-deficit | 85 × 3 × 5τ + NOAA scope rows | [0, 1]; cross-basin τ-monotonic; per-basin violation < 20% |
| B4 | 1 event window slice | matches B3 mod zero-obs drop | flag > 2 (was 5) |
| B5 | 1 basin recall by hand | n_q99_hours assertion identical across seeds | [0, 1]; cross-basin τ-monotonic |
| B6 | 1 basin FAR by hand | non-Q99 hours ≈ 99% | FAR ∈ [0,1]; over-pred ≥ 0 |
| B7 | tier boundary = pd.qcut deciles | 28+29+28 = 85 | 5 metrics × 3 tiers × 5τ |
| B8 | Flash Flood vs B3 NOAA | event-type sum = NOAA event count | "Other" row present |
| B9 | one basin overlap by hand | per-basin count = overlap basins | fractions ∈ [0, 1] |
| C1 | manual narrative review | "Synthesis" section present | grep tokens = 0 |
| C2 | diff vs prior file | 6-prohibited byte-equivalent | grep tokens = 0 |
| C3 | git log --diff-filter=R shows renames | 8 active docs; archive subfolder used | dashboard grep = 0 hits |
| C4 | C4.0 inspect step recorded in commit msg | RQ-5 7 sub-metrics present | grep tokens = 0 |

### Grep token list (Critic #9):
`scaling_300`, `subset_300`, `subset300`, `drbc_holdout` (38-basin variant, NOT `drbc_holdout_confirmed_flood_events`), `Phase 1 stub`, `RQ-A`, `RQ-B`, `RQ-C`, `RQ-D`, `RQ-E`, `RQ-F`, `RQ-G`, `IQR-distance tier` (as primary cohort; supplement OK).

---

## 9. Risks & Mitigations (revised)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| NOAA-49 ∩ expanded-85 overlap shrinks below useful sample | **High** | RQ-4b sample tight | B2 locks empirical count; RQ-4b doc states "n=N basins, subset"; B9 quantifies gap |
| Q99 unrealistic for some basins | Medium | 0 or >300 events | B1 records all 85 basin warnings in `rq2_q99_basin_warnings.csv`; does NOT fail acceptance; C2 documents distribution |
| Hourly × 3 seeds × 85 basins OOM on 16 GB MacBook | Medium | OOM | **Explicit fallback trigger:** if `psutil.virtual_memory().available < 4 GB`, switch to one-seed-at-a-time chunked load (single-seed RAM ≤ 1.5 GB measured) |
| Column-name drift between seed CSVs | Low | join breaks | C0 normalizes; B3-B6 import C0 loader |
| Quantile crossing causes per-basin monotonicity violations | **Expected** | spurious B3/B5/B6 acceptance failure if naive | **Resolved:** acceptance is cross-basin median monotonicity; per-basin violation rate threshold (< 20%) is a separate documented metric, NOT acceptance failure |
| `git mv` renames break `dashboard/lib/` references | Medium | dashboard breaks | C3 mandates pre-mv grep across `dashboard/lib/` + `scripts/dashboard/`; acceptance = 0 hits after C3 |
| User picks Option B for script layout | Low | path find-replace | documented as alternative |
| `quantile_output_interpretation.md` already has RQ-mapping with old IDs | Medium | C2 edit > append | C2 inspects file first |
| NOAA `usgs_id` vs `basin_id` padding mismatch | **Medium** | silent join failures | **Resolved:** B2 sub-step 0 normalizes both with `normalize_basin_id` from C0; emits `rq2_id_normalization_report.csv` |
| B2 regex misses non-canonical NOAA strings | **Medium** | RQ-4b under-counts | **Resolved:** B2 emits `rq4b_noaa_annotation_unmatched.csv`; acceptance fails if unmatched > 5% |
| `08_probabilistic_calibration_pinball.md` uncommitted edits silently dropped | **Medium** | edit loss | **Resolved:** C4 sub-step 0 inspect-then-commit-or-stash; same for `README.md` |
| Spec assumed NOAA = 48 basins; actual = 49 | Confirmed | acceptance mis-statement | **Resolved:** B2 locks empirical count, plan §0 and §1 updated |
| Phase B locked vocabulary diverges from C2 framework doc | Medium | Phase B CSV stale | **Resolved:** Phase C0 locks vocabulary in `_lib.py` before Phase B; C2 must use C0 constants |

---

## 10. MacBook Feasibility Rollup

| Phase | Est. wall time (M-series, single-thread) | Peak RAM |
|---|---|---|
| C0 | <1 min | trivial |
| A1 | ~5 min | ~1 GB |
| B1 | ~5 min | ~2 GB |
| B2 | <1 min | <500 MB |
| B3 | ~5 min | ~1 GB |
| B4 | ~10 min | ~1.5 GB |
| B5 | ~5 min | ~1 GB |
| B6 | ~5 min | ~1 GB |
| B7 | <2 min | <500 MB |
| B8 | <2 min | <500 MB |
| B9 | <1 min | <500 MB |
| **Phase A+B+C0 total** | **~40 min** | peak 2 GB |

Fallback (Critic gap clarification): if RAM-constrained, run B-scripts one seed at a time. Each runs in ≤ 1.5 GB.

---

## 11. ADR (Architecture Decision Record)

- **Decision:** Adopt Option A — new directory `scripts/model/expanded_drbc/` for A1 + B1-B9 + B9-cross-tab. Shared helper at `scripts/_lib/expanded_drbc.py` (follows `scripts/_lib/` repo convention, NOT `scripts/model/expanded_drbc/_lib.py`). Reused `scripts/model/hydrograph/analyze_expanded_drbc_probabilistic_diagnostics.py` (RQ-5) imports the shared helper for vocabulary constants only.
- **Decision Drivers:** local MacBook execution; 1:1 RQ-to-doc layout; reuse existing `scripts/_lib/` convention.
- **Alternatives Considered:**
  - *Option B:* Extend `scripts/model/hydrograph/`. Rejected: misleading directory name; preserves the `base` import pattern at the cost of mixed-purpose dir.
  - *Option C (not viable):* monolithic single script. Rejected: per-RQ provenance violated.
  - *Option D (deferred follow-up — Critic stakeholder gap):* Orchestrator pattern `scripts/model/expanded_drbc/run_all.py` for one-command reproducibility. Not in this plan; noted for follow-up.
- **Why chosen:** Option A + shared `_lib/` location closes Architect's "asymmetric RQ-5 location" tension by making helper importable from both directories.
- **Consequences:**
  - Positive: clean provenance; reusable helper; archive-safe.
  - Negative: one new directory + one new `_lib/` module.
- **Follow-ups (out of scope):**
  - `scripts/model/expanded_drbc/run_all.py` orchestrator (Option D).
  - `scripts/model/expanded_drbc/README.md`.
  - `dashboard/lib/` snapshot regeneration for RQ-1, RQ-2 tables.
  - Per-basin geographic map figures (Critic note — defer to paper figure pass).
  - Decision on whether RQ-5 reused script eventually migrates to `scripts/model/expanded_drbc/`.

---

## 12. Plan Summary

- **Plan saved:** `.omc/plans/2026-05-26-expanded-drbc-rebuild-execution.md`
- **Scope:**
  - 11 new scripts (1 C0 helper + 1 Phase A + 9 Phase B).
  - ~27 new output tables, ~8 new figures.
  - 4 Phase C document operations.
- **Complexity:** MEDIUM.
- **Open questions (Phase C0 may resolve some during execution prep):**
  - [x] Script directory: Option A confirmed.
  - [x] `subset300_hydrograph_interpretation_report.md`: archive to `docs/archive/analysis_legacy/` (locked).
  - [x] Dashboard impact: grep step is now C3 acceptance criterion (locked).
  - [ ] Option D orchestrator: deferred follow-up.

---

## 13. Changelog (Iteration 2)

Applied from Architect pass 1 + Critic pass 1:

1. **Aggregation order locked** in C0 `scripts/_lib/expanded_drbc.py`: per-basin per-seed compute → median across seeds within basin → median across basins; deltas at per-seed level.
2. **B2 id-normalization sub-step** added with `rq2_id_normalization_report.csv` + `zfill(8)` rule.
3. **B2 unmatched annotation artifact** `rq4b_noaa_annotation_unmatched.csv` with <5% acceptance.
4. **B7 wording** "recompute" → "aggregate from B3/B4/B5/B6 per-basin tables"; B3 monotonicity reframed cross-basin-median + per-basin <20% violation rate.
5. **Phase C0 added** before Phase B; `_lib.py` location moved to `scripts/_lib/expanded_drbc.py` per repo convention.
6. **B2 canonical labels corrected** to empirical lexicon `{Flash Flood, Flood, Coastal Flood, Other}` (Riverine/Ice Jam removed per Critic verification).
7. **A1 verification strengthened** with NumPy hand-compute of bias/MAE/RMSE on 2 basins.
8. **§7 `--seed-dir-pattern` resolved**: standardized on `--input-dir / --output-dir / --seeds`; RQ-5 reused script exempt from new flags.
9. **C4 sub-step 0** added: inspect uncommitted 08 + README before rename.
10. **NOAA basin count** updated 48 → 49 (empirical); spec assumption flagged.
11. **NaN policy** in C0 `filter_valid_rows` utility; applied B1/B3/B6.
12. **Event-window edge truncation** in B1 (`window_truncated` column).
13. **B7 tier tie-breaking** via `pd.qcut(duplicates='raise')`.
14. **B4 obs > 0 filter** + acceptance flag tightened from `> 5` to `> 2`.
15. **B9 geometry locked**: NOAA `peak_time` ∈ Q99 event window (not "within 6h of peak").
16. **§7 grep token list** explicit.
17. **C3 archive subfolder** `docs/archive/analysis_legacy/`.
18. **C1 synthesis section** mandated for narrative integration.
19. **B7 input clarification**: A1 NSE used (not raw_metrics NSE).
20. **Risks table revised**: every mitigation now actionable, no "log warning only" hand-waves.

---

**Status: pending approval.** Consensus passes Architect+Critic iteration 1 + applied revisions. Plan ready for explicit user execution approval (via team/ralph/separate approval).
