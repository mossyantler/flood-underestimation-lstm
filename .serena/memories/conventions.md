# Conventions

## Experimental Invariants
- Never change `configs/pilot/basin_splits/scaling_300/` — this is the fixed official split
- Config YAML core variables (`model`, `head`, `loss`, `seq_length`, `predict_last_n`, basin files, seed) = research design conditions. Experimental changes → separate dev/pilot config
- Basin ID files: one string ID per line, preserve leading zeros

## Script Organization
- `scripts/runs/official/` = official entry points only
- `scripts/runs/pilot/` = scaling pilot runners
- `scripts/runs/dev/` = local sanity/subset helpers
- `scripts/model/` = result analysis (overall, hydrograph, event_regime, extreme_rain, expanded_drbc, sequence, confirmed_flood)
- `scripts/_lib/` = shared helpers (import from here, don't duplicate)
- Never put exploratory/dev-only code in `scripts/runs/official/`

## Dashboard Code Organization
- Route-level composition → `app/`
- Reusable UI components → `components/`
- Pure formatting/data helpers + typed snapshots → `lib/`
- Figure previews (from output/) → `public/figures/`
- UI reference/design images → `public/research/`
- QA screenshots + Figma exports → `figma/`

## Dashboard Data Rules
- Dashboard values must trace back to `output/model_analysis/`, `docs/experiment/analysis/`, or `configs/`
- Never put large CSV, checkpoints, or full hydrograph galleries in `dashboard/`
- Snapshot data in `lib/` needs `generatedAt` + source path when from computed output

## Doc Sync Requirements
When changing: official model comparison axis, config keys/defaults, split source-of-truth, file/folder paths, official run entry points, or output locations → update `AGENTS.md`, `README.md`, `docs/README.md`, relevant `docs/experiment/method/` docs, `configs/README.md`, `scripts/README.md` in the same task.

## Checkpoint / Epoch Policy
- Checkpoint sensitivity = diagnostic only; do NOT use to re-select primary epoch
- Primary DRBC test (`2014-2016`) cannot be substituted with extreme-rain stress test or checkpoint sensitivity diagnostics
