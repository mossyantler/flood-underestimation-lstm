# Script Layout

이 디렉토리는 역할에 따라 스크립트를 구분한다.

- 루트 `scripts/`:
  데이터 준비, basin 분석, screening, integrity check, NeuralHydrology resume run 평탄화 helper처럼 canonical workflow에 직접 연결되는 스크립트를 둔다. 현재 DRBC screening 쪽 canonical 진입점에는 `build_drbc_basin_analysis_table.py`, `build_drbc_streamflow_quality_table.py`, `build_drbc_preliminary_screening_table.py`, `build_drbc_provisional_screening_table.py`, `build_drbc_event_response_table.py`가 포함된다. 서버 all-basin flood analysis용으로는 `build_camelsh_return_period_references.py`, `build_camelsh_event_response_table.py`, `build_camelsh_flood_generation_typing.py`를 순서대로 사용한다. USGS 기준 peak-flow reference가 필요하면 `fetch_usgs_streamstats_peak_flow_references.py`로 StreamStats/GageStats `Peak-Flow Statistics`를 기존 CAMELSH proxy table 옆에 붙이고, NOAA 기준 precipitation-frequency reference가 필요하면 `fetch_noaa_atlas14_precip_references.py`, `fetch_noaa_precip_gridmean_references.py`, `apply_noaa_areal_reduction_references.py`를 순서대로 사용해 point, basin-mask gridmean, areal-ARF 보조 reference를 붙인다. event response table은 official flood inventory가 아니라 observed high-flow event candidate table로 해석하고, `degree_day_v2` flood generation typing은 ML event-regime stratification을 점검하는 interpretable QA/baseline label로 유지한다. `build_camelsh_flood_generation_ml_clusters.py`는 초기 lightweight rule-vs-ML KMeans helper이고, 현재 채택한 ML variant는 `scripts/dev/compare_camelsh_flood_generation_ml_variants.py`의 `hydromet_only_7 + KMeans(k=3)` 결과다.
- `scripts/official/`:
  공식 실험 실행 진입점을 둔다. 현재는 full broad runner `run_broad_multiseed.sh`와, compute-constrained main comparison에서 fixed `scaling_300` subset을 Model 1 / Model 2 seed `111 / 222 / 444`에 공통 적용하는 `run_subset300_multiseed.sh`를 함께 둔다. subset300 epoch sweep 결과를 집계하고 diagnostic chart를 만들 때는 `analyze_subset300_epoch_results.py`를 사용한다. Hydrograph required-series를 high-flow stratum으로 다시 집계할 때는 `analyze_subset300_hydrograph_outputs.py`, observed high-flow event window를 ML event-regime과 rule label로 stratify할 때는 `analyze_subset300_event_regime_errors.py`를 사용한다. 극한호우 exposure와 DRBC historical stress test는 `build_subset300_extreme_rain_event_catalog.py`, `infer_subset300_extreme_rain_windows.py`, `analyze_subset300_extreme_rain_stress_test.py`를 순서대로 실행하고, inference/analyze 단계는 primary checkpoint와 all-validation-epoch checkpoint grid를 모두 지원한다. Model 2 seed `333`은 NaN loss로 실패했고, 공정한 paired-seed 비교를 위해 Model 1 seed `333`도 final aggregate에서 제외한다. `.nc` rsync 이후 서버 유역 분석은 `run_camelsh_flood_analysis.sh`가 return-period reference, event response, `degree_day_v2` QA/baseline typing을 한 번에 실행한다.
- `scripts/pilot/`:
  deterministic scaling pilot용 전국 stratified subset 생성, static attribute distribution diagnostics, observed-flow event-response diagnostics, random same-size subset benchmark, diagnostics 해석용 plot 생성, 실행 진입점을 둔다. 이 경로는 basin-count selection의 근거를 남기는 운영 pilot 경로이며, 현재는 채택된 `300` subset의 representativeness audit 근거도 함께 둔다. pilot runner는 `NH_RESUME=1`, `NH_SAVE_ALL_OUTPUT=False`, `NH_SAVE_VALIDATION_RESULTS=False` 같은 환경변수 override를 받아 storage-constrained 실행을 지원하고, resume 후에는 `scripts/flatten_nh_resume_run.py`를 통해 nested `continue_training_from_epoch...` 체인을 평탄화할 수 있다. 단일 top-level resume folder 바로 아래에 checkpoint가 생성된 경우에는 helper가 archive만 하고 checkpoint를 옮기지 않을 수 있으므로, resume 후 `model_epoch*.pt`, `optimizer_state_epoch*.pt`, `validation/model_epoch*`가 원래 run directory top-level에 있는지 확인한다.
- `scripts/dev/`:
  local sanity, 빠른 로컬 점검, subset 기반 Model 1/Model 2 비교 helper처럼 개발용 실행 진입점을 둔다. `run_subset_model_comparison.sh`는 broad official config를 기반으로 subset basin file과 runtime override만 바꿔 `300` 같은 subset run을 실행하는 하위 helper이고, 현재 채택된 `300` main comparison은 `scripts/official/run_subset300_multiseed.sh`가 이 helper를 감싸는 구조다. 일회성 NaN loss batch 때문에 resume이 막힐 때는 `NH_ALLOW_SUBSEQUENT_NAN_LOSSES`로 NeuralHydrology의 `allow_subsequent_nan_losses`를 명시적으로 override할 수 있다. flood generation 분석 쪽에서는 `compare_camelsh_flood_generation_ml_variants.py`, `plot_camelsh_flood_generation_ml_variant.py`, `plot_camelsh_basin_group_maps.py`가 현재 채택한 ML event-regime stratification과 figure/map 생성을 담당한다.

저장소 무결성 점검은 아래처럼 실행한다.

```bash
uv run scripts/check_repo_integrity.py
```

서버에서 rsync가 끝난 hourly NetCDF 전체를 분석할 때는 아래처럼 실행한다. Ubuntu 원격 서버에서는 Homebrew PATH를 추가하지 않는다.

```bash
TIMESERIES_DIR=/path/to/time_series \
OUTPUT_DIR=output/basin/all/analysis \
WORKERS=4 \
bash scripts/official/run_camelsh_flood_analysis.sh
```

새 기본 구조에서는 `OUTPUT_DIR`를 생략하거나 `output/basin/all/analysis`로 둔다. 이 root 아래에서 `return_period/`, `event_response/`, `flood_generation/` 폴더가 먼저 생기고, 각 폴더 안에 `tables/`와 `metadata/`가 나뉜다. USGS/NOAA reference comparison과 cache는 `output/basin/all/reference_comparison/`, `output/basin/all/cache/`를 쓴다.

이미 `return_period_reference_table.csv`가 있고 event response와 typing만 다시 만들 때는 아래처럼 stage flag를 끈다.

```bash
RUN_RETURN_PERIOD=0 \
RUN_EVENT_RESPONSE=1 \
RUN_TYPING=1 \
WORKERS=4 \
bash scripts/official/run_camelsh_flood_analysis.sh
```

기존 CAMELSH hourly annual-maxima proxy 옆에 USGS StreamStats/GageStats peak-flow statistics를 붙일 때는 아래처럼 실행한다. 기본 출력은 `return_period_reference_table_with_usgs.csv`이고, citation별 provenance는 `usgs_streamstats_peak_flow_citations.csv`에 따로 쓴다.

```bash
uv run scripts/fetch_usgs_streamstats_peak_flow_references.py --workers 8
```

기존 CAMELSH hourly annual-maxima precipitation proxy 옆에 NOAA Atlas 14/PFDS point precipitation-frequency estimate를 붙일 때는 아래처럼 실행한다. 기본 입력은 `return_period_reference_table_with_usgs.csv`가 있으면 그것을 쓰고, 없으면 `return_period_reference_table.csv`를 쓴다. 기본 출력은 `return_period_reference_table_with_usgs_noaa14.csv`이고, raw PFDS 응답은 `noaa_atlas14_cache/`에 gauge별 `AMS/PDS` CSV로 보관한다.

```bash
uv run scripts/fetch_noaa_atlas14_precip_references.py --workers 8
```

CAMELSH `Rainf`처럼 basin-average forcing support에 맞춘 NOAA 참고값이 필요하면 아래 gridmean script를 이어서 실행한다. 이 script는 CAMELSH shapefile로 NLDAS 1/8도 basin mask cell을 재구성하고, NOAA Atlas 14 GIS grid를 해당 cell 좌표에서 샘플링해 `noaa14_gridmean_*` 컬럼을 만든다. Atlas 14 project area 밖인 Oregon/Washington HUC02=17 basin은 NOAA Atlas 2 GIS grid의 `2/100-year 6/24h` fallback만 `noaa2_gridmean_*` 컬럼으로 저장한다.

```bash
uv run scripts/fetch_noaa_precip_gridmean_references.py
```

NOAA point/grid precipitation-frequency depth를 CAMELSH basin-average 강수 기준에 더 가깝게 읽고 싶으면, gridmean table에 areal reduction factor를 붙인다. 이 script는 HEC-HMS TP-40/TP-49 depth-area reduction curve를 duration별로 근사 적용해 `noaa14_areal_arf_*`와 `noaa2_areal_arf_*` 컬럼을 추가한다. 기본 입력은 `return_period_reference_table_with_usgs_noaa14_gridmean.csv`, 기본 출력은 `return_period_reference_table_with_usgs_noaa14_gridmean_areal_arf.csv`다. 이 값은 공식 NOAA Atlas 14 product가 아니라, point/grid PFE를 basin areal depth reference로 낮춰 보는 supplementary comparison이다.

```bash
uv run scripts/apply_noaa_areal_reduction_references.py
```

NOAA precipitation reference와 CAMELSH `prec_ari*` 차이를 USGS peak-flow comparison처럼 그림으로 확인할 때는 아래 plotting script를 쓴다. 기본 입력은 `output/basin/all/reference_comparison/noaa_prec/tables/reference_views/comparison_long_all_sources.csv`이고, chart와 summary table, chart guide는 각각 `reference_comparison/noaa_prec/{figures,tables,metadata}/`에 쓴다. Scatter grid, relative-difference boxplot, median trend, heatmap을 만들며, 기본 series는 CAMELSH annual-maxima proxy와 비교하기 좋은 `AMS`다.

```bash
uv run scripts/plot_noaa_precip_comparison.py
```

현재 채택한 ML event-regime stratification을 다시 비교/시각화할 때는 아래 dev scripts를 쓴다. 선택된 결과는 `output/basin/all/analysis/event_regime/{tables,figures,metadata}/`에 두고, 선택되지 않은 variant 비교 산출물은 `output/basin/all/archive/event_regime_variants/`에 둔다. 채택 variant는 `kmeans__hydromet_only_7__k3`다.

```bash
uv run scripts/dev/compare_camelsh_flood_generation_ml_variants.py
uv run scripts/dev/plot_camelsh_flood_generation_ml_variant.py
uv run scripts/dev/plot_camelsh_basin_group_maps.py
```

ML experiment CSV에 USGS StreamStats peak-flow reference를 붙일 때는 아래 helper를 쓴다. `gauge_id`가 있는 CSV만 처리하며, 기본적으로 원본은 유지하고 `*_with_usgs.csv` 병합본을 만든다.

```bash
uv run scripts/apply_usgs_peak_flow_to_ml_experiment_csvs.py
```

루트의 `build_camelsh_flood_generation_ml_clusters.py`는 초기 `KMeans(k=4)` exploratory helper로 남겨 둔다. production entry point로 승격하기 전까지는 논문용 판단 근거를 위 dev scripts의 비교 결과에 둔다.

subset300 Model 1/2 seed/epoch sweep 결과를 다시 집계하고 chart를 만들 때는 아래처럼 실행한다. 산출물은 `output/model_analysis/overall_analysis/` 아래에 생성되며, 공식 primary 비교는 `main_comparison/`, epoch sensitivity는 `epoch_sensitivity/`, 실행 기록은 `run_records/`로 나뉜다.

```bash
uv run scripts/official/analyze_subset300_epoch_results.py
```

epoch별 basin-level metric 분포를 Model/seed별 box plot으로 확인할 때는 아래처럼 실행한다. 기본값은 DRBC `test`와 non-DRBC `validation` split을 모두 만들고, 공식 paired seed `111 / 222 / 444`를 사용한다. `NSE`, `KGE`, `FHV`, `Peak-Timing`, `Peak-MAPE`, `|FHV|`를 한 장의 2x3 panel에 그리며, 산출물은 `test/with_outliers`, `test/without_outliers`, `validation/with_outliers`, `validation/without_outliers`로 나뉜다. 각 box의 빨간 점은 basin 평균이고 작은 회색 점은 1.5 IQR 기준 이상치다. Validation 기준 primary epoch box는 중간 파란색과 bold tick으로 표시한다.

```bash
uv run python scripts/official/plot_subset300_epoch_metric_boxplots.py
```

box plot 이상치가 어떤 basin에서 반복되는지 조사할 때는 아래 diagnostic을 실행한다. 같은 1.5 IQR 기준으로 outlier record를 만들고, basin metadata와 `2014-2016` test 기간 observed Streamflow 통계를 붙여 `output/model_analysis/overall_analysis/result_checks/outlier_checks/` 아래에 쓴다.

```bash
uv run python scripts/official/analyze_subset300_epoch_metric_outliers.py
```

Primary checkpoint에서 paired seed 비교를 볼 때는 아래 chart script를 사용한다. 같은 seed와 같은 DRBC basin에서 `Model 2 q50 - Model 1` delta를 계산한 `main_comparison/tables/primary_epoch_basin_deltas.csv`를 사용하며, seed별 delta box plot과 median-delta heatmap을 `main_comparison/figures/paired_seed_comparison/` 아래에 만든다.

```bash
uv run python scripts/official/plot_subset300_primary_paired_seed_comparison.py
```

고정 300-basin main split의 실제 target coverage를 basin별로 확인할 때는 아래 chart script를 사용한다. 이 script는 `Streamflow`가 처음/마지막으로 존재하는 span만 연결하지 않고, 하루 단위 valid `Streamflow` coverage를 계산해 결측일은 빈 칸으로 남기는 `basin-level daily Streamflow coverage Gantt chart`를 만든다. 산출물은 `output/basin/timeseries/target_coverage/` 아래의 `figures/`, `tables/spans.csv`, `metadata/manifest.json`으로 나뉜다. 현재 main split에서는 dynamic forcing 11개와 static attributes에 split-window 결측이 없어서, sample과 metric support를 줄이는 주 원인은 `Streamflow` target 결측으로 해석한다.

```bash
uv run scripts/official/plot_subset300_timeseries_coverage.py
```

고정 300-basin split의 공간 분포를 CONUS state boundary와 DRBC boundary 위에서 확인할 때는 아래 map script를 사용한다. 산출물은 `output/basin/all/screening/subset300_spatial_split/` 아래에 `figures/subset300_conus_split_map.{png,svg}`, basin label table, manifest로 저장된다.

```bash
uv run scripts/official/plot_subset300_split_map.py
```

같은 외형으로 target coverage가 아니라 모델에 dynamic input window로 실제 들어간 시간의 union만 보려면 `--chart-kind input`을 사용한다. 이 경우 기존 target chart를 덮어쓰지 않고 `output/basin/timeseries/input_coverage/` 아래의 `figures/`, `tables/spans.csv`, `metadata/manifest.json`으로 별도로 쓴다. Input chart는 전체 관측 가능 기간이 아니라 실제 input으로 사용된 기간에 x축을 맞춰 확대해서 그린다.

```bash
uv run scripts/official/plot_subset300_timeseries_coverage.py --chart-kind input
```

primary checkpoint의 basin별 hydrograph를 그리고 Model 2 `q50/q90/q95/q99` upper-tail band를 확인할 때는 아래처럼 실행한다. NeuralHydrology의 `save_all_output=True` 전체 덤프는 `lstm_output`, `h_n`, `c_n`까지 저장해 매우 커질 수 있으므로 쓰지 않는다. 대신 이 스크립트가 checkpoint에서 필요한 `y_quantiles`만 lean export하고, `Model 1 prediction / observed / Model 2 q50-q99 / quantile gap` 시계열 CSV와 넓은 hydrograph plot을 `output/model_analysis/quantile_analysis/` 아래에 만든다.

```bash
uv run scripts/official/plot_subset300_hydrographs.py
```

모든 validation checkpoint(`005 / 010 / 015 / 020 / 025 / 030`)를 같은 epoch의 Model 1/Model 2 쌍으로 그릴 때는 `--epochs all`을 사용한다.

```bash
uv run scripts/official/plot_subset300_hydrographs.py --epochs all --output-dir output/model_analysis/quantile_analysis
```

생성된 hydrograph required-series를 연구 질문에 맞게 다시 집계할 때는 아래 스크립트를 사용한다. `Model 1 prediction / Model 2 q50-q99`를 basin별 상위 유량 구간과 observed peak hour에서 비교하고, coverage, underestimation fraction, relative bias, quantile gap 요약과 chart를 `output/model_analysis/quantile_analysis/analysis/` 아래에 만든다.

```bash
uv run scripts/official/analyze_subset300_hydrograph_outputs.py
```

Model 2 `q50/q90/q95/q99`가 nominal quantile처럼 관측 유량을 덮는지 확인하는 one-sided coverage 진단은 아래처럼 실행한다. 산출물은 `output/model_analysis/quantile_analysis/analysis/quantile_coverage/` 아래에 만들며, unconditional `all` stratum은 calibration 진단으로, high-flow strata는 tail hit-rate 진단으로 해석한다.

```bash
uv run python scripts/official/plot_subset300_quantile_coverage.py
```

해당 산출물의 CSV/차트 해석 방법은 `output/model_analysis/quantile_analysis/analysis/analysis_outputs_guide.md`에, 논문 메시지 중심 해석은 `docs/experiment/analysis/model/subset300_hydrograph_interpretation_report.md`에 정리한다.

observed high-flow event candidate window 단위로 Model 1/Model 2 error를 비교하고, `hydromet_only_7 + KMeans(k=3)` ML event-regime을 주 stratification으로 쓰는 분석은 아래처럼 실행한다. 같은 산출물에서 `degree_day_v2` rule label sensitivity도 함께 생성한다.

```bash
uv run scripts/official/analyze_subset300_event_regime_errors.py
```

출력은 `output/model_analysis/quantile_analysis/event_regime_analysis/` 아래에 생성된다. 논문용 실행 순서와 해석 규칙은 `docs/experiment/method/model/camelsh_model12_analysis_methodology_plan.md`에 정리한다.

극한호우가 train/validation에 실제로 있었는지, 그리고 DRBC holdout basin의 historical extreme-rain response에서 Model 1/2가 peak를 따라가는지는 별도 stress test로 본다. 이 분석은 hourly `.nc`의 `Rainf` rolling sum에서 rain-event catalog를 직접 만들고, 기존 checkpoint를 재학습 없이 다시 forward pass한다. 기본값은 validation 기준 primary checkpoint이고, `--epoch-mode validation --validation-epochs 5 10 15 20 25 30`을 주면 모든 validation checkpoint grid를 같은 epoch 번호의 Model 1/2 쌍으로 평가한다.

```bash
uv run scripts/official/build_subset300_extreme_rain_event_catalog.py
uv run scripts/official/infer_subset300_extreme_rain_windows.py --device cuda:0
uv run scripts/official/analyze_subset300_extreme_rain_stress_test.py
uv run scripts/official/plot_subset300_extreme_rain_events.py
```

Primary 결과를 기준으로 둔 뒤 validation checkpoint sensitivity를 별도 산출물로 만들 때는 catalog를 재사용하고 output root를 분리한다.

```bash
OUTPUT_ROOT=output/model_analysis/extreme_rain/all \
RUN_CATALOG=0 \
EPOCH_MODE=validation \
VALIDATION_EPOCHS="5 10 15 20 25 30" \
BLOCKS_CSV=output/model_analysis/extreme_rain/primary/exposure/inference_blocks.csv \
COHORT_CSV=output/model_analysis/extreme_rain/primary/exposure/drbc_historical_stress_cohort.csv \
DEVICE=cuda:0 \
bash scripts/official/run_subset300_extreme_rain_stress_test.sh
```

원격 GPU 서버에서는 같은 세 단계를 wrapper로 실행해 로그를 고정 이름으로 남긴다. smoke test는 `CATALOG_LIMIT_BASINS`, `INFER_LIMIT_EVENTS`, `INFER_LIMIT_BASINS`, `SEEDS` 환경변수로 좁혀 돌리고, full run은 기본값 그대로 사용한다.

```bash
DEVICE=cuda:0 bash scripts/official/run_subset300_extreme_rain_stress_test.sh
```

Primary 출력은 `output/model_analysis/extreme_rain/primary/` 아래에 생성된다. 모든 validation epoch sweep 출력은 `output/model_analysis/extreme_rain/all/` 아래에 둔다. 주요 산출물은 `exposure/extreme_rain_event_catalog.csv`, `exposure/inference_blocks.csv`, `inference/inference_manifest.csv`, `inference/required_series/`, `analysis/extreme_rain_stress_error_table_long.csv`, `analysis/paired_delta_aggregate.csv`, `analysis/paired_delta_epoch_aggregate.csv`, `analysis/extreme_rain_stress_test_report.md`다. Event별 강우-유량 확인 plot은 `plot_subset300_extreme_rain_events.py`로 만들며 `output/model_analysis/extreme_rain/primary/event_plots/event_plot_index.html`와 `event_plot_manifest.csv`를 생성한다. 이 stress test는 primary `2014-2016` DRBC test를 대체하지 않고, historical extreme-rain event에 대한 보조 진단으로 해석한다.
