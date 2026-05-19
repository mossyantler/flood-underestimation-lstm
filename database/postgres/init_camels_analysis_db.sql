CREATE SCHEMA IF NOT EXISTS analysis;

CREATE TABLE IF NOT EXISTS analysis.csv_files (
    id bigserial PRIMARY KEY,
    source_path text NOT NULL UNIQUE,
    relative_path text NOT NULL,
    sha256 text NOT NULL,
    row_count integer NOT NULL,
    column_names text[] NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now(),
    importer text NOT NULL DEFAULT 'database/postgres/import_camels_csvs.py',
    notes text
);

CREATE TABLE IF NOT EXISTS analysis.csv_rows (
    file_id bigint NOT NULL REFERENCES analysis.csv_files(id) ON DELETE CASCADE,
    row_number integer NOT NULL,
    row_data jsonb NOT NULL,
    PRIMARY KEY (file_id, row_number)
);

CREATE INDEX IF NOT EXISTS csv_rows_file_id_idx
    ON analysis.csv_rows (file_id);

CREATE INDEX IF NOT EXISTS csv_rows_row_data_gin_idx
    ON analysis.csv_rows USING gin (row_data);

CREATE TABLE IF NOT EXISTS analysis.basin_membership (
    basin text PRIMARY KEY,
    in_broad_test boolean NOT NULL,
    in_natural_test boolean NOT NULL,
    exclusive_cohort text NOT NULL,
    source_path text NOT NULL,
    source_row integer NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS basin_membership_exclusive_cohort_idx
    ON analysis.basin_membership (exclusive_cohort);

CREATE TABLE IF NOT EXISTS analysis.basin_metrics (
    model text NOT NULL,
    seed integer NOT NULL,
    split text NOT NULL,
    epoch integer NOT NULL,
    run_name text,
    source text,
    metric_path text,
    basin text NOT NULL,
    nse double precision,
    kge double precision,
    fhv double precision,
    peak_timing double precision,
    peak_mape double precision,
    source_path text NOT NULL,
    source_row integer NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (model, seed, split, epoch, basin)
);

CREATE INDEX IF NOT EXISTS basin_metrics_basin_idx
    ON analysis.basin_metrics (basin);

CREATE INDEX IF NOT EXISTS basin_metrics_model_seed_split_epoch_idx
    ON analysis.basin_metrics (model, seed, split, epoch);

CREATE TABLE IF NOT EXISTS analysis.primary_epoch_basin_deltas (
    seed integer NOT NULL,
    basin text NOT NULL,
    model1_epoch integer NOT NULL,
    model2_epoch integer NOT NULL,
    delta_nse double precision,
    delta_kge double precision,
    delta_fhv double precision,
    abs_fhv_reduction double precision,
    peak_timing_reduction double precision,
    peak_mape_reduction double precision,
    source_path text NOT NULL,
    source_row integer NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (seed, basin)
);

CREATE INDEX IF NOT EXISTS primary_epoch_basin_deltas_basin_idx
    ON analysis.primary_epoch_basin_deltas (basin);

CREATE TABLE IF NOT EXISTS analysis.extreme_rain_events (
    split text NOT NULL,
    gauge_id text NOT NULL,
    event_id text NOT NULL,
    event_time_mode text,
    rolling_endpoint_start timestamp,
    rolling_endpoint_peak timestamp,
    rolling_severity_peak_time timestamp,
    rolling_endpoint_end timestamp,
    rolling_envelope_start timestamp,
    rolling_envelope_end timestamp,
    rain_start timestamp,
    rain_peak timestamp,
    rain_end timestamp,
    wet_cluster_total_rain double precision,
    wet_cluster_peak_rainf double precision,
    wet_rain_threshold_mm_h double precision,
    wet_gap_hours double precision,
    water_year integer,
    peak_month integer,
    rain_event_n_hours double precision,
    rolling_endpoint_event_n_hours double precision,
    rain_coverage double precision,
    precip_reference_flag text,
    return_period_confidence_flag text,
    flood_record_years double precision,
    return_period_record_years double precision,
    temporal_relation text,
    max_prec_ari25_ratio double precision,
    peak_time_for_ari25_ratio timestamp,
    dominant_duration_for_ari25h double precision,
    max_prec_ari25_1h_ratio double precision,
    max_prec_ari25_6h_ratio double precision,
    max_prec_ari25_24h_ratio double precision,
    max_prec_ari25_72h_ratio double precision,
    max_prec_ari50_ratio double precision,
    peak_time_for_ari50_ratio timestamp,
    dominant_duration_for_ari50h double precision,
    max_prec_ari50_1h_ratio double precision,
    max_prec_ari50_6h_ratio double precision,
    max_prec_ari50_24h_ratio double precision,
    max_prec_ari50_72h_ratio double precision,
    max_prec_ari100_ratio double precision,
    peak_time_for_ari100_ratio timestamp,
    dominant_duration_for_ari100h double precision,
    max_prec_ari100_1h_ratio double precision,
    max_prec_ari100_6h_ratio double precision,
    max_prec_ari100_24h_ratio double precision,
    max_prec_ari100_72h_ratio double precision,
    rain_cohort text,
    response_window_start timestamp,
    response_window_end timestamp,
    response_window_n_hours double precision,
    streamflow_response_coverage double precision,
    streamflow_q99_threshold double precision,
    obs_peak_to_flood_ari2 double precision,
    obs_peak_to_flood_ari25 double precision,
    obs_peak_to_flood_ari50 double precision,
    obs_peak_to_flood_ari100 double precision,
    observed_response_peak double precision,
    observed_response_peak_time timestamp,
    response_lag_hours double precision,
    response_class text,
    response_skipped_reason text,
    response_lag_from_rain_peak_h double precision,
    response_lag_from_rain_start_h double precision,
    temporal_alignment_flag text,
    flood_ari2 double precision,
    flood_ari25 double precision,
    flood_ari50 double precision,
    flood_ari100 double precision,
    storm_group_id text,
    source_path text NOT NULL,
    source_row integer NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (gauge_id, event_id)
);

CREATE INDEX IF NOT EXISTS extreme_rain_events_gauge_id_idx
    ON analysis.extreme_rain_events (gauge_id);

CREATE INDEX IF NOT EXISTS extreme_rain_events_split_rain_cohort_idx
    ON analysis.extreme_rain_events (split, rain_cohort);

CREATE TABLE IF NOT EXISTS analysis.basin_static_attributes (
    gauge_id text PRIMARY KEY,
    area double precision,
    huc02 text,
    state text,
    slope double precision,
    aridity double precision,
    snow_fraction double precision,
    soil_depth double precision,
    permeability double precision,
    baseflow_index double precision,
    forest_fraction double precision,
    source_path text NOT NULL,
    source_row integer NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS analysis.basin_flood_generation (
    gauge_id text PRIMARY KEY,
    gauge_name text,
    state text,
    huc02 text,
    drain_sqkm_attr double precision,
    area double precision,
    snow_fraction double precision,
    event_count integer,
    dominant_flood_generation_type text,
    dominant_type_if_any text,
    dominant_type_share double precision,
    recent_precipitation_count integer,
    antecedent_precipitation_count integer,
    snowmelt_or_rain_on_snow_count integer,
    uncertain_high_flow_candidate_count integer,
    recent_precipitation_share double precision,
    antecedent_precipitation_share double precision,
    snowmelt_or_rain_on_snow_share double precision,
    uncertain_high_flow_candidate_share double precision,
    low_confidence_event_share double precision,
    mean_recent_precipitation_strength double precision,
    mean_antecedent_precipitation_strength double precision,
    mean_snowmelt_or_rain_on_snow_strength double precision,
    source_path text NOT NULL,
    source_row integer NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS analysis.basin_event_response (
    gauge_id text PRIMARY KEY,
    gauge_name text,
    state text,
    huc02 text,
    drain_sqkm_attr double precision,
    area double precision,
    snow_fraction double precision,
    obs_years_usable double precision,
    processing_status text,
    selected_threshold_quantile text,
    selected_threshold_value double precision,
    q99_event_count integer,
    q98_event_count integer,
    q95_event_count integer,
    event_count integer,
    flood_like_ge_2yr_proxy_event_count integer,
    high_flow_below_2yr_proxy_event_count integer,
    high_flow_candidate_unrated_event_count integer,
    annual_peak_years integer,
    unit_area_peak_median double precision,
    unit_area_peak_p90 double precision,
    q99_event_frequency double precision,
    rbi double precision,
    rising_time_median_hours double precision,
    event_duration_median_hours double precision,
    event_runoff_coefficient_median double precision,
    annual_peak_unit_area_median double precision,
    annual_peak_unit_area_p90 double precision,
    return_period_method text,
    min_annual_coverage double precision,
    flood_ari_source text,
    prec_ari_source text,
    flood_record_years double precision,
    return_period_record_years double precision,
    return_period_confidence_flag text,
    flood_ari2 double precision,
    flood_ari5 double precision,
    flood_ari10 double precision,
    flood_ari25 double precision,
    flood_ari50 double precision,
    flood_ari100 double precision,
    prec_record_years_1h double precision,
    prec_ari2_1h double precision,
    prec_ari5_1h double precision,
    prec_ari10_1h double precision,
    prec_ari25_1h double precision,
    prec_ari50_1h double precision,
    prec_ari100_1h double precision,
    prec_record_years_6h double precision,
    prec_ari2_6h double precision,
    prec_ari5_6h double precision,
    prec_ari10_6h double precision,
    prec_ari25_6h double precision,
    prec_ari50_6h double precision,
    prec_ari100_6h double precision,
    prec_record_years_24h double precision,
    prec_ari2_24h double precision,
    prec_ari5_24h double precision,
    prec_ari10_24h double precision,
    prec_ari25_24h double precision,
    prec_ari50_24h double precision,
    prec_ari100_24h double precision,
    prec_record_years_72h double precision,
    prec_ari2_72h double precision,
    prec_ari5_72h double precision,
    prec_ari10_72h double precision,
    prec_ari25_72h double precision,
    prec_ari50_72h double precision,
    prec_ari100_72h double precision,
    source_path text NOT NULL,
    source_row integer NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS analysis.basin_event_regime (
    gauge_id text PRIMARY KEY,
    cluster_0_share double precision,
    cluster_1_share double precision,
    cluster_2_share double precision,
    event_count integer,
    top1_share double precision,
    top2_share double precision,
    cluster_entropy double precision,
    top1_cluster integer,
    ml_dominant_label text,
    ml_map_label text,
    gauge_name text,
    state text,
    huc02 text,
    drain_sqkm_attr double precision,
    event_count_event integer,
    dominant_flood_generation_type text,
    dominant_type_share double precision,
    huc02_name text,
    source_path text NOT NULL,
    source_row integer NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS analysis.probabilistic_pinball (
    comparison text NOT NULL,
    seed integer NOT NULL,
    model1_epoch integer NOT NULL,
    model2_epoch integer NOT NULL,
    stratum text NOT NULL,
    stratum_label text,
    quantile text NOT NULL,
    nominal_tau double precision,
    n_rows integer,
    n_basins integer,
    mean_obs double precision,
    median_obs double precision,
    mean_pinball double precision,
    median_pinball double precision,
    mean_aqs double precision,
    median_aqs double precision,
    mean_pinball_pct_mean_obs double precision,
    median_pinball_pct_median_obs double precision,
    source_path text NOT NULL,
    source_row integer NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (comparison, seed, model1_epoch, model2_epoch, stratum, quantile)
);

CREATE TABLE IF NOT EXISTS analysis.probabilistic_calibration (
    comparison text NOT NULL,
    seed integer NOT NULL,
    model1_epoch integer NOT NULL,
    model2_epoch integer NOT NULL,
    stratum text NOT NULL,
    stratum_label text,
    quantile text NOT NULL,
    nominal_tau double precision,
    n_rows integer,
    n_basins integer,
    mean_obs double precision,
    median_obs double precision,
    empirical_coverage double precision,
    coverage_error double precision,
    abs_coverage_error double precision,
    undercoverage_error double precision,
    overcoverage_error double precision,
    underestimation_fraction double precision,
    calibration_context text NOT NULL,
    source_path text NOT NULL,
    source_row integer NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (comparison, seed, model1_epoch, model2_epoch, stratum, quantile, calibration_context)
);

CREATE TABLE IF NOT EXISTS analysis.probabilistic_tail_spread (
    comparison text NOT NULL,
    seed integer NOT NULL,
    model1_epoch integer NOT NULL,
    model2_epoch integer NOT NULL,
    stratum text NOT NULL,
    stratum_label text,
    n_rows integer,
    n_basins integer,
    mean_obs double precision,
    median_obs double precision,
    mean_q90_minus_q50 double precision,
    median_q90_minus_q50 double precision,
    mean_q90_minus_q50_pct_obs double precision,
    median_q90_minus_q50_pct_obs double precision,
    mean_q95_minus_q90 double precision,
    median_q95_minus_q90 double precision,
    mean_q95_minus_q90_pct_obs double precision,
    median_q95_minus_q90_pct_obs double precision,
    mean_q99_minus_q95 double precision,
    median_q99_minus_q95 double precision,
    mean_q99_minus_q95_pct_obs double precision,
    median_q99_minus_q95_pct_obs double precision,
    mean_q99_minus_q50 double precision,
    median_q99_minus_q50 double precision,
    mean_q99_minus_q50_pct_obs double precision,
    median_q99_minus_q50_pct_obs double precision,
    q90_lt_q50_rows integer,
    q95_lt_q90_rows integer,
    q99_lt_q95_rows integer,
    source_path text NOT NULL,
    source_row integer NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (comparison, seed, model1_epoch, model2_epoch, stratum)
);

-- ── Confirmed Flood Evaluation ────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS analysis.nws_flood_stage_coverage (
    usgs_id text PRIMARY KEY,
    nws_lid text,
    county_fips text,
    minor_stage_ft double precision,
    moderate_stage_ft double precision,
    major_stage_ft double precision,
    minor_discharge_cms double precision,
    moderate_discharge_cms double precision,
    major_discharge_cms double precision,
    coverage_status text NOT NULL,
    source_path text NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS analysis.nws_coverage_bias (
    attribute text NOT NULL,
    covered_n integer,
    missing_n integer,
    covered_median double precision,
    missing_median double precision,
    ks_stat double precision,
    ks_pvalue double precision,
    source_path text NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (attribute)
);

CREATE TABLE IF NOT EXISTS analysis.drbc_confirmed_flood_events (
    usgs_id text NOT NULL,
    peak_time timestamptz NOT NULL,
    peak_discharge_cms double precision,
    flood_tier text NOT NULL,
    tier_limited boolean NOT NULL DEFAULT false,
    noaa_corroborated boolean NOT NULL DEFAULT false,
    period text NOT NULL,
    forcing_coverage_min double precision,
    source_path text NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (usgs_id, peak_time)
);

CREATE INDEX IF NOT EXISTS drbc_confirmed_flood_events_usgs_id_idx
    ON analysis.drbc_confirmed_flood_events (usgs_id);

CREATE INDEX IF NOT EXISTS drbc_confirmed_flood_events_flood_tier_idx
    ON analysis.drbc_confirmed_flood_events (flood_tier);

CREATE TABLE IF NOT EXISTS analysis.drbc_confirmed_flood_performance (
    usgs_id text NOT NULL,
    peak_time timestamptz NOT NULL,
    model text NOT NULL,
    seed integer NOT NULL,
    quantile text NOT NULL,
    obs_peak_cms double precision,
    pred_peak_cms double precision,
    peak_under_deficit double precision,
    is_underestimate boolean,
    exceeds_minor_stage boolean,
    event_nrmse double precision,
    flood_tier text,
    noaa_corroborated boolean,
    source_path text NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (usgs_id, peak_time, model, seed, quantile)
);

CREATE INDEX IF NOT EXISTS drbc_confirmed_flood_performance_model_seed_idx
    ON analysis.drbc_confirmed_flood_performance (model, seed);

CREATE INDEX IF NOT EXISTS drbc_confirmed_flood_performance_flood_tier_idx
    ON analysis.drbc_confirmed_flood_performance (flood_tier);

CREATE OR REPLACE VIEW analysis.primary_basin_metrics_with_cohort AS
SELECT
    bm.*,
    mb.exclusive_cohort,
    mb.in_broad_test,
    mb.in_natural_test
FROM analysis.basin_metrics bm
LEFT JOIN analysis.basin_membership mb
    ON bm.basin = mb.basin;

CREATE OR REPLACE VIEW analysis.primary_epoch_deltas_with_cohort AS
SELECT
    d.*,
    mb.exclusive_cohort,
    mb.in_broad_test,
    mb.in_natural_test
FROM analysis.primary_epoch_basin_deltas d
LEFT JOIN analysis.basin_membership mb
    ON d.basin = mb.basin;
