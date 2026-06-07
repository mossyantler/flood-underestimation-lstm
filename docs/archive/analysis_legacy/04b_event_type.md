# 04b RQ-4b — NOAA Confirmed Flood Event-type Heterogeneity

## 질문 (RQ-4b)

upper quantile output의 peak alleviation 효과·cost가 NOAA Storm Events에서 분류된 event-type (Flash Flood / Flood / Coastal Flood)별로 얼마나 다른가?

본 분석은 expanded DRBC 85 basin 중 NOAA confirmed flood catalog가 cover하는 부분집합 (basin overlap = 46, test-period event-bearing basin ≈ 21) 위에서 진행된다. event-type label은 catalog `noaa_annotation` 필드 정규식 파싱으로 추출한다.

## 데이터

- NOAA/NWS 확인 홍수 catalog: `output/model_analysis/confirmed_flood/data/catalog/drbc_confirmed_flood_event_catalog.csv` (664 events; 49 USGS basin)
- expanded DRBC 85 basin과 매핑: B2 산출물 `tables/rq2_noaa_basin_overlap_summary.csv` (overlap = 46)
- per-event α / β: B3 / B4 NOAA scope 산출물
- per-basin FAR / over-pred: B6 (Q99 baseline)

### Event-type 분류

`noaa_annotation` 정규식 파싱 (`scripts/_lib/expanded_drbc.py`의 `NOAA_REGEX`):
- `Flash Flood`: `\bFlash Flood\b(?!\s+(?:Watch|Advisory))`
- `Flood`: `(?<!Flash )(?<!Coastal )\bFlood\b(?!\s+(?:Watch|Advisory))`
- `Coastal Flood`: `\bCoastal Flood\b`

Tie-break (`NOAA_TIE_BREAK`, most-specific wins): `Flash Flood > Coastal Flood > Flood > Other`. 그룹별 events < 5는 "Other"로 lump.

`NoNOAA`: NWS flood-stage exceedance event 중 NOAA Storm Events corroboration 없음 (annotation = `-`). 데이터 품질 카테고리이며 RQ-4b paper 카테고리에서 분리.

## 결과 (in_expanded_85 ∩ test-period 2014-2016 = 65 events / 21 basins)

### α (peak deficit) — model1 baseline 포함 전 τ

| Event Type (n_events / n_basins) | model1 | q50 | q90 | q95 | q99 |
| --- | --- | --- | --- | --- | --- |
| Flash Flood (8 / 6) | 0.926 | 0.943 | 0.776 | 0.696 | **0.417** |
| Flood (32 / 15) | 0.569 | 0.780 | 0.472 | 0.382 | **0.060** |
| NoNOAA (25 / 9) | 0.715 | 0.782 | 0.442 | 0.349 | **0.000** |

### β (window capture) + cost (q99)

| Event Type | β q50→q99 | FAR q99 | over-pred q99 |
| --- | --- | --- | --- |
| Flash Flood | 0.082 → 0.877 | 0.027 | 2.18 |
| Flood | 0.285 → 1.091 | 0.021 | 2.36 |
| NoNOAA | 0.279 → 1.197 | 0.025 | 2.73 |

(Coastal Flood: 전체 catalog 8 events / 4 basins이나 test-period × expanded-85 교집합 0건 → 표 미포함. 시간·공간 편향이라 명시.)

## 핵심 패턴

- **Flash Flood가 가장 어려운 event-type**: q99에서도 peak deficit 0.42 잔존. q99 α를 Flood(0.06)와 비교하면 **약 7배 차이**. model1→q99 완화율도 Flash 55%(0.926→0.417) vs Flood 89%(0.569→0.060)로, 돌발홍수에서 quantile 이득이 가장 작다. 짧은 첨두의 lag가 원인.
- **Flood (riverine)**: q99에서 peak deficit 0.06 — quantile output이 잘 작동.
- **over-prediction cost**: q99 over-pred는 Flash 2.18 < Flood 2.36 < NoNOAA 2.73로 비슷한 수준. FAR도 0.021~0.027로 event-type 간 차이 작다 — 완화 효과 차이가 비용 차이로는 안 나타남.
- 이 결론(돌발홍수에서 과소추정 잔존)은 RQ-0 신호 분석(대류성 강수비·CAPE가 돌발홍수 과소추정 신호)과 일관된다.

## 산출물

```text
output/model_analysis/primary/metrics/tables/
  rq2_id_normalization_report.csv
  rq2_noaa_basin_overlap_summary.csv
  rq4b_event_type_mapping.csv
  rq4b_noaa_annotation_unmatched.csv   (0 rows — 미분류 event 없음)
  rq4b_event_type_metrics.csv
output/model_analysis/primary/metrics/figures/
  rq4b_event_type_bar.png
```

## 주의점

- **Sample size 작음**: Flash Flood 8 events / 6 basins, Coastal Flood paper 표에서 제외. 통계적 추론보다 case-comparison으로 읽는다.
- **basin scope mismatch**: expanded 85 ∩ NOAA 49 = 46 basin. RQ-2 Q99 (85 basin) 결과와 동일 scale 비교 시 caveat.
- **NoNOAA q99 α=0.000 순환 위험**: NoNOAA(NWS flood-stage exceedance)는 q99에서 peak deficit이 정확히 0이다. NWS flood-stage 정의가 quantile 임계와 결합돼 있을 가능성이 있어, NoNOAA 결과를 NOAA-confirmed 주장 근거로 쓰지 않는다. 데이터 품질 카테고리로만 둔다. unmatched event는 0건(모든 test-period event가 정규식으로 분류됨).
- **regex 검증**: catalog 전체 hit 수 = Flash Flood 853 / Flood 136 / Coastal Flood 9.
- **regex 검증**: catalog 전체 hit 수 = Flash Flood 853 / Flood 136 / Coastal Flood 9 (PRD acceptance criteria 모두 충족).
