# Script Layout

이 디렉토리는 역할에 따라 스크립트를 구분한다.

- 루트 `scripts/`:
  `README.md`와 `AGENTS.md`만 두는 것을 기본으로 한다. 실제 실행 파일은 목적별 하위 폴더에 둔다.
- `scripts/data/`:
  CAMELSH download, region matching, NeuralHydrology generic dataset preparation을 둔다.
- `scripts/basin/drbc/`:
  DRBC holdout cohort, screening, streamflow quality, event-response table, split file 생성처럼 DRBC basin 정의와 검증에 직접 연결되는 script를 둔다.
- `scripts/basin/all/`:
  CAMELSH 전체 또는 non-DRBC training pool에 대한 master checklist, return-period proxy, observed event response, flood-generation typing 같은 basin-level analysis를 둔다. `degree_day_v2` flood generation typing은 ML event-regime stratification을 점검하는 interpretable QA/baseline label로 유지한다. `build_camelsh_flood_generation_ml_clusters.py`는 초기 lightweight rule-vs-ML KMeans helper이고, 현재 채택한 ML variant는 `scripts/basin/event_regime/compare_camelsh_flood_generation_ml_variants.py`의 `hydromet_only_7 + KMeans(k=3)` 결과다.
- `scripts/basin/reference/`:
  USGS/NOAA 외부 reference fetch와 CAMELSH proxy table 병합 helper를 둔다.
- `scripts/basin/plots/`:
  basin screening, timeseries coverage, external reference comparison 같은 basin-side diagnostic figure를 둔다.
- `scripts/ops/`:
  repo integrity check, Elice bootstrap, NeuralHydrology resume run flattening, NetCDF inspection, validation metric summary 같은 운영 helper를 둔다.
- `scripts/_lib/`:
  여러 script가 import하는 공용 helper만 둔다. 현재는 `camelsh_flood_analysis_utils.py`가 여기에 있다.
- `scripts/runs/official/`:
  official shell runner를 둔다. `run_broad_multiseed.sh`는 broad reference run, `run_subset300_multiseed.sh`는 fixed `scaling_300` subset의 Model 1 / Model 2 seed `111 / 222 / 444` main comparison을 실행한다.
  `run_expanded_drbc_test_evaluation.sh`는 기존 subset300 checkpoint를 그대로 두고 expanded observed DRBC test split에서 재평가한다. 이 runner는 재학습을 수행하지 않는다.
  모델 학습이 아니라 official observed basin analysis를 실행하는 `run_camelsh_flood_analysis.sh`도 여기에 둔다. `.nc` rsync 이후 return-period reference, event response, `degree_day_v2` QA/baseline typing을 한 번에 실행한다.
- `scripts/model/overall/`:
  subset300 primary/epoch metric 집계, outlier check, paired-seed comparison, Model 1/2 architecture figure처럼 전체 성능과 논문 main comparison에 붙는 분석을 둔다.
- `scripts/basin/split_diagnostics/`:
  fixed subset300 split의 공간 분포와 target/input time-series coverage 진단 figure를 둔다.
- `scripts/model/hydrograph/`:
  primary/all-validation checkpoint hydrograph export, high-flow stratum aggregation, quantile coverage 진단을 둔다.
- `scripts/model/event_regime/`:
  observed high-flow event window 단위의 Model 1/2 error를 ML event-regime과 rule label로 stratify하는 분석을 둔다.
- `scripts/model/extreme_rain/`:
  hourly `Rainf` 기반 extreme-rain exposure catalog, checkpoint inference, stress-test aggregate, event plot을 둔다. Inference/analyze 단계는 primary checkpoint와 all-validation-epoch checkpoint grid를 모두 지원한다.
- `scripts/scaling/`:
  deterministic scaling pilot용 전국 stratified subset 생성, static attribute distribution diagnostics, observed-flow event-response diagnostics, random same-size subset benchmark, diagnostics plot을 둔다.
- `scripts/runs/pilot/`:
  scaling pilot training runner를 둔다. `run_deterministic_scaling_pilot.sh`는 `NH_RESUME=1`, `NH_SAVE_ALL_OUTPUT=False`, `NH_SAVE_VALIDATION_RESULTS=False` 같은 환경변수 override를 받아 storage-constrained 실행을 지원하고, resume 후에는 `scripts/ops/flatten_nh_resume_run.py`를 통해 nested `continue_training_from_epoch...` 체인을 평탄화할 수 있다.
- `scripts/runs/dev/`:
  local sanity와 subset comparison helper를 둔다. `run_subset_model_comparison.sh`는 broad official config를 기반으로 subset basin file과 runtime override만 바꿔 `300` 같은 subset run을 실행하는 하위 helper이고, 현재 채택된 `300` main comparison은 `scripts/runs/official/run_subset300_multiseed.sh`가 이 helper를 감싸는 구조다.
- `scripts/basin/event_regime/`:
  ML event-regime variant 비교, selected variant figure, basin group map, GMM sensitivity 같은 exploratory 분석을 둔다. 이 산출물은 논문용 판단 근거로 승격하기 전까지 dev 결과로 취급한다.
- `scripts/model/sequence/`:
  단일 sequence의 모델 입출력 구조와 Gantt chart를 확인하는 개발용 helper를 둔다.

저장소 무결성 점검은 아래처럼 실행한다.

```bash
uv run scripts/ops/check_repo_integrity.py
```

서버에서 rsync가 끝난 hourly NetCDF 전체를 분석할 때는 아래처럼 실행한다. Ubuntu 원격 서버에서는 Homebrew PATH를 추가하지 않는다.

```bash
TIMESERIES_DIR=/path/to/time_series \
OUTPUT_DIR=output/basin/all/analysis \
WORKERS=4 \
bash scripts/runs/official/run_camelsh_flood_analysis.sh
```

새 기본 구조에서는 `OUTPUT_DIR`를 생략하거나 `output/basin/all/analysis`로 둔다. 이 root 아래에서 `return_period/`, `event_response/`, `flood_generation/` 폴더가 먼저 생기고, 각 폴더 안에 `tables/`와 `metadata/`가 나뉜다. USGS/NOAA reference comparison과 cache는 `output/basin/all/reference_comparison/`, `output/basin/all/cache/`를 쓴다.

이미 `return_period_reference_table.csv`가 있고 event response와 typing만 다시 만들 때는 아래처럼 stage flag를 끈다.

```bash
RUN_RETURN_PERIOD=0 \
RUN_EVENT_RESPONSE=1 \
RUN_TYPING=1 \
WORKERS=4 \
bash scripts/runs/official/run_camelsh_flood_analysis.sh
```

기존 CAMELSH hourly annual-maxima proxy 옆에 USGS StreamStats/GageStats peak-flow statistics를 붙일 때는 아래처럼 실행한다. 기본 출력은 `return_period_reference_table_with_usgs.csv`이고, citation별 provenance는 `usgs_streamstats_peak_flow_citations.csv`에 따로 쓴다.

```bash
uv run scripts/basin/reference/fetch_usgs_streamstats_peak_flow_references.py --workers 8
```

기존 CAMELSH hourly annual-maxima precipitation proxy 옆에 NOAA Atlas 14/PFDS point precipitation-frequency estimate를 붙일 때는 아래처럼 실행한다. 기본 입력은 `return_period_reference_table_with_usgs.csv`가 있으면 그것을 쓰고, 없으면 `return_period_reference_table.csv`를 쓴다. 기본 출력은 `return_period_reference_table_with_usgs_noaa14.csv`이고, raw PFDS 응답은 `noaa_atlas14_cache/`에 gauge별 `AMS/PDS` CSV로 보관한다.

```bash
uv run scripts/basin/reference/fetch_noaa_atlas14_precip_references.py --workers 8
```

CAMELSH `Rainf`처럼 basin-average forcing support에 맞춘 NOAA 참고값이 필요하면 아래 gridmean script를 이어서 실행한다. 이 script는 CAMELSH shapefile로 NLDAS 1/8도 basin mask cell을 재구성하고, NOAA Atlas 14 GIS grid를 해당 cell 좌표에서 샘플링해 `noaa14_gridmean_*` 컬럼을 만든다. Atlas 14 project area 밖인 Oregon/Washington HUC02=17 basin은 NOAA Atlas 2 GIS grid의 `2/100-year 6/24h` fallback만 `noaa2_gridmean_*` 컬럼으로 저장한다.

```bash
uv run scripts/basin/reference/fetch_noaa_precip_gridmean_references.py
```

NOAA point/grid precipitation-frequency depth를 CAMELSH basin-average 강수 기준에 더 가깝게 읽고 싶으면, gridmean table에 areal reduction factor를 붙인다. 이 script는 HEC-HMS TP-40/TP-49 depth-area reduction curve를 duration별로 근사 적용해 `noaa14_areal_arf_*`와 `noaa2_areal_arf_*` 컬럼을 추가한다. 기본 입력은 `return_period_reference_table_with_usgs_noaa14_gridmean.csv`, 기본 출력은 `return_period_reference_table_with_usgs_noaa14_gridmean_areal_arf.csv`다. 이 값은 공식 NOAA Atlas 14 product가 아니라, point/grid PFE를 basin areal depth reference로 낮춰 보는 supplementary comparison이다.

```bash
uv run scripts/basin/reference/apply_noaa_areal_reduction_references.py
```

NOAA precipitation reference와 CAMELSH `prec_ari*` 차이를 USGS peak-flow comparison처럼 그림으로 확인할 때는 아래 plotting script를 쓴다. 기본 입력은 `output/basin/all/reference_comparison/noaa_prec/tables/reference_views/comparison_long_all_sources.csv`이고, chart와 summary table, chart guide는 각각 `reference_comparison/noaa_prec/{figures,tables,metadata}/`에 쓴다. Scatter grid, relative-difference boxplot, median trend, heatmap을 만들며, 기본 series는 CAMELSH annual-maxima proxy와 비교하기 좋은 `AMS`다.

```bash
uv run scripts/basin/plots/plot_noaa_precip_comparison.py
```

현재 채택한 ML event-regime stratification을 다시 비교/시각화할 때는 아래 dev scripts를 쓴다. 선택된 결과는 `output/basin/all/analysis/event_regime/{tables,figures,metadata}/`에 두고, 선택되지 않은 variant 비교 산출물은 `output/basin/all/archive/event_regime_variants/`에 둔다. 채택 variant는 `kmeans__hydromet_only_7__k3`다.

```bash
uv run scripts/basin/event_regime/compare_camelsh_flood_generation_ml_variants.py
uv run scripts/basin/event_regime/plot_camelsh_flood_generation_ml_variant.py
uv run scripts/basin/event_regime/plot_camelsh_basin_group_maps.py
```

ML experiment CSV에 USGS StreamStats peak-flow reference를 붙일 때는 아래 helper를 쓴다. `gauge_id`가 있는 CSV만 처리하며, 기본적으로 원본은 유지하고 `*_with_usgs.csv` 병합본을 만든다.

```bash
uv run scripts/basin/reference/apply_usgs_peak_flow_to_ml_experiment_csvs.py
```

`scripts/basin/all/build_camelsh_flood_generation_ml_clusters.py`는 초기 `KMeans(k=4)` exploratory helper로 남겨 둔다. production entry point로 승격하기 전까지는 논문용 판단 근거를 위 dev scripts의 비교 결과에 둔다.

subset300 Model 1/2 seed/epoch sweep 결과를 다시 집계하고 chart를 만들 때는 아래처럼 실행한다. 산출물은 `output/model_analysis/overall_analysis/` 아래에 생성되며, 공식 primary 비교는 `main_comparison/`, epoch sensitivity는 `epoch_sensitivity/`, 실행 기록은 `run_records/`로 나뉜다.

```bash
uv run scripts/model/overall/analyze_subset300_epoch_results.py
```

기존 subset300 Model 1/2 checkpoint를 expanded observed DRBC test split에서 다시 평가할 때는 아래 runner를 사용한다. 기본값은 DRBC 154개 후보에서 quality gate와 2014-2016 target coverage 80%를 통과한 85개 basin을 만들고, `data/CAMELSH_generic/drbc_expanded_observed_test`를 준비한 뒤 seed `111 / 222 / 444`의 validation-selected primary epoch를 `cuda:0`에서 평가한다. 이미 split과 prepared dataset을 서버에 복사해 둔 경우에는 `RUN_SPLIT=0 RUN_PREPARE=0`으로 평가만 다시 돌릴 수 있다.

```bash
DEVICE=cuda:0 \
bash scripts/runs/official/run_expanded_drbc_test_evaluation.sh
```

Model 1 deterministic LSTM과 Model 2 quantile LSTM의 구조 비교도를 발표용 image로 만들 때는 아래 script를 사용한다. `h_{b,t}`, `\hat{Q}_{b,t}`, quantile outputs는 matplotlib mathtext로 렌더링하며, PNG/SVG/PDF를 `output/model_analysis/overall_analysis/main_comparison/figures/model_architecture/` 아래에 쓴다.

```bash
uv run scripts/model/overall/plot_model12_architecture_diagram.py
```

epoch별 basin-level metric 분포를 Model/seed별 box plot으로 확인할 때는 아래처럼 실행한다. 기본값은 DRBC `test`와 non-DRBC `validation` split을 모두 만들고, 공식 paired seed `111 / 222 / 444`를 사용한다. `NSE`, `KGE`, `FHV`, `Peak-Timing`, `Peak-MAPE`, `|FHV|`를 한 장의 2x3 panel에 그리며, figure 산출물은 `figures/epoch_metric_boxplots/{test,validation}/{with_outliers,without_outliers}/`로 나뉜다. Chart manifest와 metadata는 `metadata/epoch_metric_boxplots/`에 둔다. 각 box의 빨간 점은 basin 평균이고 작은 회색 점은 1.5 IQR 기준 이상치다. Validation 기준 primary epoch box는 중간 파란색과 bold tick으로 표시한다.

```bash
uv run python scripts/model/overall/plot_subset300_epoch_metric_boxplots.py
```

box plot 이상치가 어떤 basin에서 반복되는지 조사할 때는 아래 diagnostic을 실행한다. 같은 1.5 IQR 기준으로 outlier record를 만들고, basin metadata와 `2014-2016` test 기간 observed Streamflow 통계를 붙여 `output/model_analysis/overall_analysis/result_checks/outlier_checks/` 아래에 쓴다.

```bash
uv run python scripts/model/overall/analyze_subset300_epoch_metric_outliers.py
```

Primary checkpoint box plot에서 `NSE`, `KGE`, `FHV` 값이 각 model/seed median에서 얼마나 떨어지는지 basin·flow regime 특성과 함께 보려면 아래 script를 사용한다. Median-distance는 해당 box IQR로 나눠 해석하며, snow fraction과 cold-season event fraction처럼 ratio가 실제로 가까운 basin만 conservative하게 group으로 묶는다. 산출물은 `output/model_analysis/overall_analysis/main_comparison/attribute_correlations/median_deviation/` 아래의 `tables/`, `metadata/`, `report/`, `figures/`에 쓴다.

```bash
uv run python scripts/model/overall/analyze_subset300_primary_metric_median_deviation_regimes.py
```

DRBC 38개 basin을 개별 station 단위로 진단할 때는 아래 script를 사용한다. 기존 attribute-metric Spearman 상관, median-distance regime, event-response summary, extreme-rain stress error, USGS station note, basin_dissect report를 join해서 basin별 상세 Markdown report와 38개 summary table을 `output/model_analysis/overall_analysis/main_comparison/individual_basin_diagnostics/` 아래에 쓴다.

```bash
uv run python scripts/model/overall/build_drbc_individual_basin_diagnostics.py
```

Primary checkpoint에서 paired seed 비교를 볼 때는 아래 chart script를 사용한다. 같은 seed와 같은 DRBC basin에서 `Model 2 q50 - Model 1` delta를 계산한 `main_comparison/tables/primary_epoch_basin_deltas.csv`를 사용하며, seed별 delta box plot과 median-delta heatmap을 `main_comparison/figures/paired_seed_comparison/` 아래에 만든다.

```bash
uv run python scripts/model/overall/plot_subset300_primary_paired_seed_comparison.py
```

Broad DRBC test 38개를 Natural 8개와 broad non-natural 30개로 다시 나누어 robustness check를 만들 때는 아래 script를 사용한다. 기존 primary overall metric, hydrograph required-series, event-regime error table, extreme-rain stress table을 읽어 cohort별 aggregate와 figure를 `output/model_analysis/natural_broad_comparison/` 아래에 쓴다.

```bash
uv run scripts/model/overall/analyze_natural_broad_comparison.py
```

논문 Results에 바로 옮기기 쉬운 compact table과 figure 후보를 만들 때는 아래 script를 사용한다. 기존 aggregate 산출물만 읽어서 high-flow/peak compact table, event-regime compact figure, checkpoint sensitivity compact figure, 대표 hydrograph 후보 목록을 `output/model_analysis/paper_result_assets/` 아래에 쓴다.

```bash
uv run python scripts/model/overall/build_subset300_paper_result_assets.py
```

지금까지 생성한 basin-side, model-side, stress-test, robustness, paper-facing 분석을 한 화면에서 훑는 HTML 대시보드를 만들 때는 아래 script를 사용한다. 이 script는 기존 `docs/experiment/analysis/`, `output/model_analysis/`, `output/basin/`, `configs/pilot/diagnostics/`의 report/metadata/manifest를 읽고, 검색·카테고리 필터·대표 figure preview·분석별 상세 패널이 있는 정적 dashboard를 `output/model_analysis/analysis_dashboard/` 아래에 쓴다. UI는 repo root의 `DESIGN.md`에 맞춰 light/dark tile rhythm, Action Blue, pill action, minimal chrome 중심으로 유지한다.

```bash
uv run python scripts/model/overall/build_analysis_inventory_site.py
```

외부 static host에 올릴 수 있는 self-contained dashboard bundle이 필요하면 `--publish-dir`을 같이 준다. 이 bundle은 dashboard 본문과 preview image, 카드의 작은 직접 링크 대상 artifact를 `assets/` 아래에 복사하므로 `output/model_analysis/analysis_dashboard_publish/` 폴더를 그대로 업로드하기 쉽다. 큰 CSV/폴더는 기본 25MB 제한으로 복사하지 않고 원래 repo path를 알려주는 placeholder page로 연결한다.

```bash
uv run python scripts/model/overall/build_analysis_inventory_site.py \
  --publish-dir output/model_analysis/analysis_dashboard_publish
```

고정 300-basin main split의 실제 target coverage를 basin별로 확인할 때는 아래 chart script를 사용한다. 이 script는 `Streamflow`가 처음/마지막으로 존재하는 span만 연결하지 않고, 하루 단위 valid `Streamflow` coverage를 계산해 결측일은 빈 칸으로 남기는 `basin-level daily Streamflow coverage Gantt chart`를 만든다. 산출물은 `output/basin/timeseries/target_coverage/` 아래의 `figures/`, `tables/spans.csv`, `metadata/manifest.json`으로 나뉜다. 현재 main split에서는 dynamic forcing 11개와 static attributes에 split-window 결측이 없어서, sample과 metric support를 줄이는 주 원인은 `Streamflow` target 결측으로 해석한다.

```bash
uv run scripts/basin/split_diagnostics/plot_subset300_timeseries_coverage.py
```

고정 300-basin split의 공간 분포를 CONUS state boundary와 DRBC boundary 위에서 확인할 때는 아래 map script를 사용한다. 산출물은 `output/basin/all/screening/subset300_spatial_split/` 아래에 `figures/subset300_conus_split_map.{png,svg}`, basin label table, manifest로 저장된다.

```bash
uv run scripts/basin/split_diagnostics/plot_subset300_split_map.py
```

같은 외형으로 target coverage가 아니라 모델에 dynamic input window로 실제 들어간 시간의 union만 보려면 `--chart-kind input`을 사용한다. 이 경우 기존 target chart를 덮어쓰지 않고 `output/basin/timeseries/input_coverage/` 아래의 `figures/`, `tables/spans.csv`, `metadata/manifest.json`으로 별도로 쓴다. Input chart는 전체 관측 가능 기간이 아니라 실제 input으로 사용된 기간에 x축을 맞춰 확대해서 그린다.

```bash
uv run scripts/basin/split_diagnostics/plot_subset300_timeseries_coverage.py --chart-kind input
```

primary checkpoint의 basin별 hydrograph를 그리고 Model 2 `q50/q90/q95/q99` upper-tail band를 확인할 때는 아래처럼 실행한다. NeuralHydrology의 `save_all_output=True` 전체 덤프는 `lstm_output`, `h_n`, `c_n`까지 저장해 매우 커질 수 있으므로 쓰지 않는다. 대신 이 스크립트가 checkpoint에서 필요한 `y_quantiles`만 lean export하고, `Model 1 prediction / observed / Model 2 q50-q99 / quantile gap` 시계열 CSV와 넓은 hydrograph plot을 `output/model_analysis/quantile_analysis/` 아래에 만든다.

```bash
uv run scripts/model/hydrograph/plot_subset300_hydrographs.py
```

모든 validation checkpoint(`005 / 010 / 015 / 020 / 025 / 030`)를 같은 epoch의 Model 1/Model 2 쌍으로 그릴 때는 `--epochs all`을 사용한다.

```bash
uv run scripts/model/hydrograph/plot_subset300_hydrographs.py --epochs all --output-dir output/model_analysis/quantile_analysis
```

생성된 hydrograph required-series를 연구 질문에 맞게 다시 집계할 때는 아래 스크립트를 사용한다. `Model 1 prediction / Model 2 q50-q99`를 basin별 상위 유량 구간과 observed peak hour에서 비교하고, coverage, underestimation fraction, relative bias, quantile gap 요약과 chart를 `output/model_analysis/quantile_analysis/analysis/` 아래에 만든다. 또한 primary basin-specific Q99 exceedance hour와 각 basin observed peak가 정확히 어느 Model 2 quantile 구간에 포함되는지 `<=q50`, `q50-q90`, `q90-q95`, `q95-q99`, `>q99`로 분류해 `primary_q99_exceedance_quantile_zone.csv`, `primary_q99_exceedance_quantile_zone_summary.csv`, `observed_peak_quantile_zone.csv`, `observed_peak_quantile_zone_summary.csv`, `observed_peak_quantile_zone_aggregate.csv`를 만든다.

```bash
uv run scripts/model/hydrograph/analyze_subset300_hydrograph_outputs.py
```

Model 2 `q50/q90/q95/q99`가 nominal quantile처럼 관측 유량을 덮는지 확인하는 one-sided coverage 진단은 아래처럼 실행한다. 산출물은 `output/model_analysis/quantile_analysis/analysis/quantile_coverage/` 아래에 만들며, unconditional `all` stratum은 calibration 진단으로, high-flow strata는 tail hit-rate 진단으로 해석한다.

```bash
uv run python scripts/model/hydrograph/plot_subset300_quantile_coverage.py
```

공식 probabilistic diagnostic으로 quantile별 pinball/AQS, all-hour one-sided calibration, high-flow 조건부 tail hit-rate, upper-tail spread를 한 번에 고정할 때는 아래 script를 사용한다. 산출물은 `output/model_analysis/probabilistic_diagnostics/` 아래에 생성되며, `quantile_calibration_by_stratum.csv`의 `all` stratum만 formal calibration으로 읽고 observed-flow strata는 tail hit-rate로 해석한다.

```bash
uv run python scripts/model/hydrograph/analyze_subset300_probabilistic_diagnostics.py
```

Hydrograph/high-flow 산출물의 CSV/차트 해석 방법은 `output/model_analysis/quantile_analysis/analysis/analysis_outputs_guide.md`에, 논문 메시지 중심 해석은 `docs/experiment/analysis/model/subset300_hydrograph_interpretation_report.md`에 정리한다. Probabilistic diagnostic의 최종 해석은 `docs/experiment/analysis/model/08_probabilistic_calibration_pinball.md`를 기준으로 읽는다.

observed high-flow event candidate window 단위로 Model 1/Model 2 error를 비교하고, `hydromet_only_7 + KMeans(k=3)` ML event-regime을 주 stratification으로 쓰는 분석은 아래처럼 실행한다. 같은 산출물에서 `degree_day_v2` rule label sensitivity도 함께 생성한다.

```bash
uv run scripts/model/event_regime/analyze_subset300_event_regime_errors.py
```

Regime별 under-deficit reduction, threshold recall delta, event NRMSE tradeoff를 논문용 한 장 figure로 묶을 때는 아래 script를 사용한다.

```bash
uv run python scripts/model/event_regime/plot_subset300_event_regime_summary.py
```

출력은 `output/model_analysis/quantile_analysis/event_regime_analysis/` 아래에 생성된다. 논문용 실행 순서와 해석 규칙은 `docs/experiment/method/model/camelsh_model12_analysis_methodology_plan.md`에 정리한다.

Event-level error target을 RandomForest surrogate로 근사하고 SHAP으로 q95/q99 under-deficit reduction과 q99 tradeoff의 설명 변수를 확인할 때는 아래 script를 사용한다. 이 SHAP은 원 LSTM의 직접 설명이 아니라 surrogate error model 설명이므로, causal mechanism claim이 아니라 post-hoc diagnostic으로 해석한다.

```bash
uv run scripts/model/event_regime/analyze_subset300_event_surrogate_shap.py
```

출력은 `output/model_analysis/quantile_analysis/event_surrogate_shap/` 아래의 `tables/`, `figures/`, `metadata/`, `report/`에 생성된다.

극한호우가 train/validation에 실제로 있었는지, 그리고 DRBC holdout basin의 historical extreme-rain response에서 Model 1/2가 peak를 따라가는지는 별도 stress test로 본다. 이 분석은 hourly `.nc`의 `Rainf` rolling sum에서 rain-event catalog를 직접 만들고, 기존 checkpoint를 재학습 없이 다시 forward pass한다. 기본값은 validation 기준 primary checkpoint이고, `--epoch-mode validation --validation-epochs 5 10 15 20 25 30`을 주면 모든 validation checkpoint grid를 같은 epoch 번호의 Model 1/2 쌍으로 평가한다.

```bash
uv run scripts/model/extreme_rain/build_subset300_extreme_rain_event_catalog.py
uv run scripts/model/extreme_rain/infer_subset300_extreme_rain_windows.py --device cuda:0
uv run scripts/model/extreme_rain/analyze_subset300_extreme_rain_stress_test.py
uv run scripts/model/extreme_rain/plot_subset300_extreme_rain_events.py
uv run scripts/model/extreme_rain/plot_subset300_extreme_rain_flow_graph_examples.py
uv run scripts/model/extreme_rain/plot_subset300_extreme_rain_simq_events.py
uv run scripts/model/extreme_rain/build_extreme_rain_median_map_index.py
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
bash scripts/runs/official/run_subset300_extreme_rain_stress_test.sh
```

Primary extreme-rain stress-test는 rain/streamflow 시간축을 wet-footprint 기준으로 맞춰 `primary/` 아래에 만든다. Catalog는 rolling exceedance trigger를 먼저 잡되 `--event-time-mode wet_footprint`로 실제 wet cluster의 `rain_start / rain_peak / rain_end`를 쓴다. Cohort에 새로 필요한 block이 있으면 그 block만 `infer_subset300_extreme_rain_windows.py --blocks-csv ...`로 보충한 뒤 `primary/inference/required_series/`에 seed별로 합쳐서 사용한다.

```bash
uv run scripts/model/extreme_rain/build_subset300_extreme_rain_event_catalog.py \
  --event-time-mode wet_footprint \
  --output-dir output/model_analysis/extreme_rain/primary/exposure

uv run scripts/model/extreme_rain/analyze_subset300_extreme_rain_stress_test.py \
  --input-dir output/model_analysis/extreme_rain/primary/inference \
  --cohort-csv output/model_analysis/extreme_rain/primary/exposure/drbc_historical_stress_cohort.csv \
  --output-dir output/model_analysis/extreme_rain/primary/analysis

uv run scripts/model/extreme_rain/plot_subset300_extreme_rain_events.py \
  --cohort-csv output/model_analysis/extreme_rain/primary/exposure/drbc_historical_stress_cohort.csv \
  --output-dir output/model_analysis/extreme_rain/primary/event_plots

uv run scripts/model/extreme_rain/plot_subset300_extreme_rain_simq_events.py \
  --event-manifest output/model_analysis/extreme_rain/primary/event_plots/event_plot_manifest.csv \
  --cohort-csv output/model_analysis/extreme_rain/primary/exposure/drbc_historical_stress_cohort.csv \
  --stress-long-csv output/model_analysis/extreme_rain/primary/analysis/extreme_rain_stress_error_table_long.csv \
  --series-dir output/model_analysis/extreme_rain/primary/inference/required_series \
  --output-dir output/model_analysis/extreme_rain/primary/event_simq_plots

uv run scripts/model/extreme_rain/build_extreme_rain_median_map_index.py \
  --event-manifest output/model_analysis/extreme_rain/primary/event_plots/event_plot_manifest.csv \
  --simq-event-manifest output/model_analysis/extreme_rain/primary/event_simq_plots/event_simq_plot_manifest.csv \
  --output-html output/model_analysis/extreme_rain/primary/event_plot_median_map_index.html

uv run scripts/model/extreme_rain/plot_observed_q99_hydrograph_gallery.py \
  --all-gauges \
  --skip-existing

uv run scripts/model/extreme_rain/build_observed_q99_hydrograph_gallery_index.py
```

`analyze_subset300_extreme_rain_stress_test.py`는 primary wet-footprint 기준으로 `Local Peak Quantile Bracket` diagnostic도 같이 생성한다. 기본 window는 `--peak-quantile-window-hours 6`이고 sensitivity는 `--peak-quantile-sensitivity-hours 0 12`다. 새 산출물은 `analysis/peak_quantile_bracket_event_table.csv`, `peak_quantile_bracket_summary.csv`, `peak_quantile_bracket_aggregate.csv`, `peak_quantile_bracket_sensitivity.csv`, `peak_quantile_bracket_chart_manifest.csv`, 그리고 `analysis/figures/peak_quantile_bracket/`의 stacked-bar, `tau_hat` violin, `>q99` overflow plot이다. 이 값은 flood forecast probability가 아니라 observed response peak가 Model 2 `q50/q90/q95/q99` ladder 안에서 어디에 놓이는지 보는 stress diagnostic으로만 읽는다.

원격 GPU 서버에서는 같은 세 단계를 wrapper로 실행해 로그를 고정 이름으로 남긴다. smoke test는 `CATALOG_LIMIT_BASINS`, `INFER_LIMIT_EVENTS`, `INFER_LIMIT_BASINS`, `SEEDS` 환경변수로 좁혀 돌리고, full run은 기본값 그대로 사용한다.

```bash
DEVICE=cuda:0 bash scripts/runs/official/run_subset300_extreme_rain_stress_test.sh
```

Primary 출력은 `output/model_analysis/extreme_rain/primary/` 아래에 생성된다. 모든 validation epoch sweep 출력은 `output/model_analysis/extreme_rain/all/` 아래에 둔다. 주요 산출물은 `exposure/extreme_rain_event_catalog.csv`, `exposure/inference_blocks.csv`, `inference/inference_manifest.csv`, `inference/required_series/`, `analysis/extreme_rain_stress_error_table_long.csv`, `analysis/paired_delta_aggregate.csv`, `analysis/paired_delta_epoch_aggregate.csv`, `analysis/extreme_rain_stress_test_report.md`다. Event별 강우-관측유량 확인 plot은 `plot_subset300_extreme_rain_events.py`로 만들며 `event_plots/event_plot_index.html`와 `event_plot_manifest.csv`를 생성한다. 전체 236개 event에서 Model 1과 Model 2 `q50/q95/q99`를 seed별 flow panel로 겹쳐 보는 plot은 `plot_subset300_extreme_rain_simq_events.py`가 `event_simq_plots/` 아래에 생성하며, stress analysis table에 peak bracket 컬럼이 있으면 각 seed panel에 bracket annotation을 표시한다. `build_extreme_rain_median_map_index.py`는 `event_simq_plot_manifest.csv`가 있으면 이 sim-Q plot을 우선 사용하고, 없으면 observed-only event manifest로 fallback하여 `event_plot_median_map_index.html`을 만든다. DRBC basin별 historical observed Q99+ event hydrograph 전체를 볼 때는 `plot_observed_q99_hydrograph_gallery.py --all-gauges --skip-existing`가 `analysis/{gauge_id}_hydrograph/` 아래에 PNG, manifest, `index.html`을 만들고, `build_observed_q99_hydrograph_gallery_index.py`가 `observed_q99_hydrograph_gallery_index.html` map index를 만든다. 이 HTML map은 `subset300_conus_split_map`과 같은 EPSG:5070 투영으로 CAMELSH basin과 DRBC boundary를 겹쳐 그린다. 대표 event 3개를 본문/부록용으로 따로 고르는 figure는 `plot_subset300_extreme_rain_flow_graph_examples.py`로 만들며 `flow_graph_diagnostic/` 아래에 `figures/`, `tables/`, `metadata/`를 생성한다. 이 stress test는 primary `2014-2016` DRBC test를 대체하지 않고, historical extreme-rain event에 대한 보조 진단으로 해석한다.

Confirmed flood inference도 primary hydrograph와 같은 lean time-series 계약을 따른다. 아래 명령은 NWS flood-stage catalog를 읽어 `output/model_analysis/confirmed_flood/inference/raw_model_exports/`에 모델별 raw prediction CSV를, `inference/required_series/seed*/primary_required_series.csv`에 `obs / model1 / q50 / q90 / q95 / q99`를 inner-join한 event-window 시계열을 쓴다. `required_series`에는 LSTM warmup을 포함한 전체 inference window가 저장되고, metric 계산은 `in_eval_window == True`인 `[peak_time - 24h, peak_time + 168h]` 구간만 사용해 `output/model_analysis/confirmed_flood/performance/drbc_confirmed_flood_performance.csv`를 다시 만든다.

Confirmed flood는 expanded observed test dataset을 그대로 쓰지 않는다. 먼저 confirmed flood catalog를 만든 뒤, catalog event만 대상으로 별도 GenericDataset을 준비한다. 이 준비 단계는 `timeseries.7z`와 `timeseries_nonobs.7z`에서 forcing을 찾고, 필요하면 `Hourly2.zip`의 observed streamflow를 붙여 `data/CAMELSH_generic/drbc_holdout_confirmed_flood_events/` 아래에 `time_series/`, `attributes/static_attributes.csv`, `splits/test.txt`, `splits/event_windows.csv`, `splits/event_window_manifest.csv`를 쓴다. Inference script는 이 `splits/event_windows.csv`가 있으면 catalog에서 window를 다시 만들지 않고 prepared event window를 우선 사용한다.

```bash
uv run scripts/data/prepare_drbc_confirmed_flood_event_dataset.py
```

```bash
uv run scripts/model/confirmed_flood/infer_drbc_confirmed_flood_events.py --device cpu
```

Confirmed flood event별 hydrograph는 아래 script로 만든다. Layout은 extreme-rain sim-Q hydrograph와 같이 상단 Rainf panel, 아래 seed별 streamflow panel 구조를 쓴다. Flow 기준선은 임의 ARI가 아니라 NWS `minor/moderate/major` flood-stage discharge를 쓰고, NOAA Storm Events와 매칭된 event는 flow panel에 NOAA 기록 날짜 vertical marker와 event type label을 표시한다.

```bash
uv run scripts/model/confirmed_flood/plot_drbc_confirmed_flood_hydrographs.py
```

React dashboard의 confirmed flood 화면은 canonical output CSV를 직접 runtime dependency로 물지 않고, 작은 typed snapshot으로 갱신한다. 성능 구분은 Model 1 `det` peak under-deficit과 Model 2 `q99` peak under-deficit의 paired-seed median 차이를 기준으로 하며, flood 유형은 NWS `minor/moderate/major`, event type은 NOAA Storm Events annotation에서 가져온다. 지도 geometry는 `basins/drbc_boundary/drb_bnd_polygon.shp`와 `basins/CAMELSH_data/shapefiles/CAMELSH_shapefile.shp`에서 SVG path로 추출하고, gauge 점은 같은 크기의 위치 marker로만 표시한다.

```bash
uv run scripts/model/confirmed_flood/export_confirmed_flood_dashboard_snapshot.py
```
