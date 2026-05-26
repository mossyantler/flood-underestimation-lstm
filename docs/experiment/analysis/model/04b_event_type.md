# 04b RQ-4b — NOAA Confirmed Flood Event-type Heterogeneity

## 질문 (RQ-4b)

upper quantile output의 peak alleviation 효과·cost가 NOAA Storm Events에서 분류된 event-type (Flash Flood / Flood / Coastal Flood)별로 얼마나 다른가?

본 분석은 expanded DRBC 85 basin 중 NOAA confirmed flood catalog가 cover하는 부분집합 (basin overlap = 46, test-period event-bearing basin ≈ 21) 위에서 진행된다. event-type label은 catalog `noaa_annotation` 필드 정규식 파싱으로 추출한다.

## 데이터

- NOAA event catalog: `output/model_analysis/confirmed_flood/catalog/drbc_confirmed_flood_event_catalog.csv` (664 events; 49 USGS basin)
- expanded DRBC 85 basin과 매핑: B2 산출물 `tables/rq2_noaa_basin_overlap_summary.csv` (overlap = 46)
- per-event α / β: B3 / B4 NOAA scope 산출물
- per-basin FAR / over-pred: B6 (Q99 baseline)

### Event-type 분류

`noaa_annotation` 정규식 파싱 (`scripts/_lib/expanded_drbc.NOAA_REGEX`):
- `Flash Flood`: `\bFlash Flood\b(?!\s+(?:Watch|Advisory))`
- `Flood`: `(?<!Flash )(?<!Coastal )\bFlood\b(?!\s+(?:Watch|Advisory))`
- `Coastal Flood`: `\bCoastal Flood\b`

Tie-break (`NOAA_TIE_BREAK`, most-specific wins): `Flash Flood > Coastal Flood > Flood > Other`. 그룹별 events < 5는 "Other"로 lump.

`NoNOAA`: NWS flood-stage exceedance event 중 NOAA Storm Events corroboration 없음 (annotation = `-`). 데이터 품질 카테고리이며 RQ-4b paper 카테고리에서 분리.

## 결과 (in_expanded_85 ∩ test-period 2014-2016 = 65 events / 21 basins)

| Event Type | n_events | n_basins | α (q50→q99) | β (q50→q99) | FAR (q50→q99) |
| --- | --- | --- | --- | --- | --- |
| Flash Flood | 8 | 6 | 0.94 → 0.42 | 0.08 → 0.88 | 0.0004 → 0.027 |
| Flood | 32 | 15 | 0.78 → 0.06 | 0.29 → 1.09 | 0.0004 → 0.021 |
| NoNOAA | 25 | 9 | 0.78 → 0.00 | 0.28 → 1.20 | 0.0007 → 0.025 |

(Coastal Flood: test-period × expanded-85 교집합 event 부족 → 표 미포함)

## 핵심 패턴

- **Flash Flood**: q99에서도 peak deficit 0.42 잔존 — 가장 어려운 event-type. β는 0.88 (좀 못 미침). 짧은 첨두에서 모델의 lag가 작용.
- **Flood (riverine-style)**: q99에서 peak deficit 0.06으로 떨어짐 — quantile output이 잘 작동.
- **NoNOAA (NWS flood-stage but no NOAA Storm Events corroboration)**: 동작 양상이 Flood 카테고리와 유사. 단 데이터 품질이 다르므로 paper에서 사용 시 주의.

## 산출물

```text
output/model_analysis/expanded_drbc_test/tables/
  rq2_id_normalization_report.csv
  rq2_noaa_basin_overlap_summary.csv
  rq2_noaa_events_expanded_overlap.csv
  rq4b_event_type_mapping.csv
  rq4b_noaa_annotation_unmatched.csv
  rq4b_event_type_metrics.csv
output/model_analysis/expanded_drbc_test/figures/
  rq4b_event_type_bar.png
```

## 주의점

- **Sample size 작음**: Flash Flood 8 events / 6 basins, Coastal Flood paper 표에서 제외. 통계적 추론보다 case-comparison으로 읽는다.
- **basin scope mismatch**: expanded 85 ∩ NOAA 49 = 46 basin (즉 NOAA-49 중 3개는 expanded에 없음, expanded-85 중 39개는 NOAA에 없음). RQ-2 Q99 (85 basin) 결과와 동일 scale 비교 시 caveat.
- **NoNOAA 카테고리**: NWS flood-stage exceedance를 NOAA Storm Events가 corroborate하지 않은 event다. 모델 행동 자체는 정상 분석되지만 paper headline에 사용할 때는 NWS-only임을 명시한다.
- **regex 검증**: catalog 전체 hit 수 = Flash Flood 853 / Flood 136 / Coastal Flood 9 (PRD acceptance criteria 모두 충족).
