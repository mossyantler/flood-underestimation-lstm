# CAMELS 실험 분석 대시보드

Model 1 (deterministic LSTM) vs Model 2 (probabilistic quantile head) 비교 대시보드.

## Run

```bash
export PATH="/opt/homebrew/bin:$PATH"
npm install
npm run dev
```

기본 주소: `http://localhost:3000` → `/overview` redirect

## Figma Source

- File key: `Yww4tmRcPSQswHfeov50gH`
- Desktop: node `16:2` (O·개요), `16:194` (R·결과) — 1680×1020
- Mobile: node `470:199` (O·개요), `470:1297` (R·결과) — 430×932

## Source Data

화면 수치는 `lib/dashboard-data.ts` typed snapshot 사용.
canonical source-of-truth: `output/`, `docs/experiment/analysis/`, `configs/`

## 검증

```bash
npm run typecheck
npm run build
```
