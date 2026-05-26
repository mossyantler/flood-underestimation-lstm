# CAMELS Project Core

## Purpose
Multi-basin LSTM hydrology prediction. Goal: reduce extreme flood peak underestimation.
Official comparison axis: **Model 1** (Deterministic LSTM) vs **Model 2** (Probabilistic quantile LSTM).
Model 3 (physics-guided hybrid) = out of current paper scope.

## Fixed Experimental Conditions
- Seeds: `111 / 222 / 444`. Seed `333` excluded from final aggregate (NaN loss on Model 2; Model 1 excluded for fair comparison).
- Subset: non-DRBC `scaling_300`
- Temporal split: train `2000–2010`, validation `2011–2013`, test `2014–2016`

## Basin Definitions
- DRBC holdout: `outlet_in_drbc == True` AND `overlap_ratio >= 0.9` → **154 basins**
- Training pool: `outlet_in_drbc == False` AND `overlap_ratio <= 0.1`, quality gate → **1923 basins** (fixed subset: **300**)

## Source-of-Truth Hierarchy
| Domain | Location |
|--------|----------|
| Official model comparison conclusions | `docs/experiment/analysis/model/` |
| Data processing methods | `docs/experiment/method/` |
| Basin split definitions | `configs/pilot/basin_splits/scaling_300/` |
| Official configs | `configs/camelsh_hourly_*_drbc_holdout_broad.yml` |
| Analysis outputs | `output/` (gitignored, regenerable) |

- `dashboard/lib/` snapshot = display-only copy, NOT source-of-truth
- `docs/archive/`, `docs/explain/`, `docs/references/` = not authoritative

## Key Directories
```
configs/              # Official splits + configs (source-of-truth)
data/CAMELSH_generic/ # NH-style hourly dataset (gitignored)
docs/experiment/      # method/ and analysis/model/
scripts/              # All analysis entry points
vendor/neuralhydrology/ # Vendored upstream — do NOT modify directly
output/               # Gitignored analysis/figure artifacts
runs/                 # Gitignored training checkpoints
dashboard/            # Next.js display UI
```

## Output Path Rules
- Model analysis → `output/model_analysis/`
- Basin-side results → `output/basin/`
- Extreme-rain primary → `output/model_analysis/legacy/extreme_rain/primary/`
- Epoch sweep → `output/model_analysis/legacy/extreme_rain/all/`

## Shared Python Helpers
`scripts/_lib/camelsh_flood_analysis_utils.py` — main shared utility
`scripts/_lib/expanded_drbc.py` — expanded DRBC helper

See `mem:tech_stack` for languages/tools. See `mem:suggested_commands` for run commands. See `mem:conventions` for code style.
