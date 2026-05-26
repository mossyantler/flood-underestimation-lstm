# Suggested Commands

## Python Scripts (macOS local)
```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run scripts/<path>.py
```

## Repo Integrity Check
```bash
uv run scripts/ops/check_repo_integrity.py
```

## Official Training (remote GPU)
```bash
bash scripts/runs/official/run_subset300_multiseed.sh
```

## Model Result Aggregation
```bash
uv run scripts/model/overall/analyze_subset300_epoch_results.py
uv run scripts/model/hydrograph/plot_subset300_hydrographs.py
uv run scripts/model/hydrograph/analyze_subset300_hydrograph_outputs.py
uv run scripts/model/hydrograph/analyze_subset300_probabilistic_diagnostics.py
```

## Full Basin Flood Analysis (after rsync)
```bash
TIMESERIES_DIR=/path/to/time_series \
OUTPUT_DIR=output/basin/all/analysis \
WORKERS=4 \
bash scripts/runs/official/run_camelsh_flood_analysis.sh
```

## Extreme-Rain Stress Test
```bash
DEVICE=cuda:0 bash scripts/runs/official/run_subset300_extreme_rain_stress_test.sh
```

## Dashboard (from dashboard/)
```bash
cd dashboard
npm install
npm run dev           # http://localhost:3000
npm run typecheck     # after UI/data type changes
npm run build         # after route/layout/dependency/asset changes
```
