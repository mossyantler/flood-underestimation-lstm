# Task Completion Checklist

## Python script changes
```bash
uv run scripts/ops/check_repo_integrity.py
```
Run after any path moves, file renames, or structural changes.

## Dashboard changes
```bash
cd dashboard && npm run typecheck     # always after UI/type/helper changes
cd dashboard && npm run build         # after route/layout/dep/asset changes
```

## Doc sync (required when applicable)
After changing official model comparison axis, config keys, split paths, run entry points, or output locations:
- Update: `AGENTS.md`, `README.md`, `docs/README.md`, relevant `docs/experiment/method/` docs, `configs/README.md`, `scripts/README.md`

## Verification
- Output artifacts are in `output/` (gitignored) — verify by re-running analysis scripts
- Dashboard snapshot data in `lib/` — verify source path still valid after output restructure
