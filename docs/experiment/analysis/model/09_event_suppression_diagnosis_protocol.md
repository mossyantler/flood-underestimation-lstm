# 09 Event Suppression / Managed-Flow Diagnosis Protocol

## 질문

이 문서는 extreme-rain stress event에서 강수 forcing은 강한데 관측 유량 response가 낮거나, 반대로 강수 forcing은 약한데 관측 유량만 큰 pulse/plateau를 보이는 case를 어떻게 진단할지 정리한다. 목표는 `01480685_rain_drbc_historical_stress_0005`에서 수행한 case-level 분석을 다른 DRBC 유역과 event에도 같은 순서로 반복 적용하는 것이다.

이 문서는 새 metric이나 공식 screening rule이 아니다. `output/model_analysis/extreme_rain/primary_time_aligned/`에 이미 만들어진 event catalog, model prediction, basin metadata를 읽고, 특정 event가 왜 "눌려 보이는지" 또는 왜 precipitation-driven model이 만들기 어려운 extra-flow signal을 보이는지 post-hoc으로 해석하는 절차다.

## 사용 시점

이 protocol은 아래 상황에서 쓴다.

1. `rain_cohort`는 `prec_ge100`, `prec_ge50`, `prec_ge25`처럼 높지만 `response_class`가 `negative_control` 쪽으로 분류된 event를 설명해야 할 때 사용한다. 특히 `high_flow_non_flood_q99_only`는 Q99 이상 high flow는 있었지만 flood proxy까지는 오르지 않은 case라 원인 진단 가치가 크다.
2. Sim-Q plot에서 Model 1이나 Model 2 `q95/q99`가 강수 직후 큰 peak를 만들었는데 observed streamflow는 낮고 완만하게 움직일 때 사용한다. 이 경우 모델이 자연 유역의 quick response를 만든 것인지, 관측 유량이 reservoir나 diversion 같은 실제 조절 영향을 받은 것인지 분리해야 한다.
3. Rainf가 거의 없거나 약한데 observed streamflow가 일정한 plateau, 계단형 jump, 갑작스러운 pulse를 보이고 sim이 따라가지 못할 때 사용한다. 이 경우 reservoir release, return flow, wastewater discharge, interbasin transfer, pump/gate operation 같은 managed-flow signal 가능성을 점검한다.
4. `>=3 IQR` 같은 basin-level outlier를 보다가 특정 유역의 obs가 sim보다 반복적으로 눌리거나, 반대로 dry-window에서 obs만 크게 올라가는 패턴을 볼 때 사용한다. 단, 이 protocol은 event-scale hydrograph 진단용이므로 전체 test-period metric outlier의 원인을 바로 확정하는 용도로 쓰지 않는다.

## 입력 파일

기본은 `primary_time_aligned` 산출물을 사용한다. 이 버전은 rain event 시간을 rolling exceedance endpoint가 아니라 wet footprint 기준으로 다시 맞춘 diagnostic이라, case-level hydrograph 해석에 더 안전하다. 원본 `primary` 결과를 덮어쓰지 않는 보조 진단이라는 점은 유지한다.

| 목적 | 파일 | 핵심 컬럼 |
| --- | --- | --- |
| event severity와 observed response | `output/model_analysis/extreme_rain/primary_time_aligned/exposure/extreme_rain_event_catalog.csv` | `event_id`, `gauge_id`, `rain_start`, `rain_peak`, `rain_end`, `wet_cluster_total_rain`, `wet_cluster_peak_rainf`, `max_prec_ari*_ratio`, `dominant_duration_for_ari100h`, `observed_response_peak`, `observed_response_peak_time`, `response_lag_from_rain_peak_h`, `streamflow_q99_threshold`, `flood_ari*`, `obs_peak_to_flood_ari*`, `response_class` |
| plot과 basin context | `output/model_analysis/extreme_rain/primary_time_aligned/event_simq_plots/event_simq_plot_manifest.csv` | `plot_path`, `gauge_name`, `drain_sqkm_attr`, `hydromod_risk`, `forest_pct`, `developed_pct`, `wetland_pct`, `NDAMS_2009`, `MAJ_NDAMS_2009`, `STOR_NOR_2009`, `CANALS_PCT`, `FRESHW_WITHDRAWAL` |
| model false-positive 또는 under-response | `output/model_analysis/extreme_rain/primary_time_aligned/analysis/extreme_rain_stress_error_table_wide.csv` | `seed`, `model1_window_peak`, `model1_window_peak_time`, `model1_window_peak_rel_error_pct`, `model1_signed_peak_timing_error_hours`, `q50_window_peak`, `q95_window_peak`, `q99_window_peak`, `q99_window_peak_time`, `q99_window_peak_rel_error_pct`, `q99_signed_peak_timing_error_hours` |
| observed forcing/flow 시계열 | `data/CAMELSH_generic/drbc_holdout_broad/time_series/{gauge_id}.nc` | `Rainf`, `Streamflow` |
| DRBC static attributes | `output/basin/drbc/analysis/basin_attributes/tables/drbc_selected_static_attributes_full.csv` | `drain_sqkm_attr`, `overlap_ratio_of_basin`, `SLOPE_PCT`, `BFI_AVE`, `DEVNLCD06`, `FORESTNLCD06`, `WATERNLCD06`, `WOODYWETNLCD06`, `EMERGWETNLCD06` |
| hydromod proxy | `basins/CAMELSH_data/attributes/attributes_gageii_HydroMod_Dams.csv` | `NDAMS_2009`, `MAJ_NDAMS_2009`, `STOR_NOR_2009`, `STOR_NID_2009`, `RAW_DIS_NEAREST_DAM`, `RAW_DIS_NEAREST_MAJ_DAM` |
| water-use proxy | `basins/CAMELSH_data/attributes/attributes_gageii_HydroMod_Other.csv` | `FRESHW_WITHDRAWAL`, `CANALS_PCT`, `CANALS_MAINSTEM_PCT`, `NPDES_MAJ_DENS`, `PCT_IRRIG_AG` |
| external station context cache | `output/basin/all/cache/usgs_streamstats/{gauge_id}.json` | `isRegulated`, `name`, `location`, `statistics`, `characteristics` |
| required external station notes | USGS monitoring location page, available USGS annual water-data report PDF, local station-note artifact | regulation/diversion remarks, station relocation/datum notes, rating/estimated-flow caveats, period-of-record context, saved source summary |

USGS monitoring location page는 case-level 진단을 시작할 때 반드시 먼저 읽는다. Annual water-data report PDF는 모든 station에 항상 쉽게 연결되는 것은 아니므로, 찾을 수 있으면 읽고 찾지 못하면 `not found`로 기록한다. 확인한 source summary는 [`docs/references/basin/usgs_station_notes/`](../../../references/basin/usgs_station_notes/) 아래에 `gauge_id`별 markdown artifact로 따로 저장한다. 이 외부 note는 local metadata보다 최신이거나 더 직접적인 regulation/diversion 설명을 줄 수 있으므로, hydromod/managed-flow 해석에서는 선택 사항이 아니라 초기 확인 항목이다.

## 진단 절차

### 0. USGS station note를 먼저 확인한다

수치 분석에 들어가기 전에 `gauge_id`의 USGS monitoring location page를 열고 station note를 읽는다. 확인할 항목은 station name, drainage area, gage/datum 변경, regulation/diversion remark, reservoir 또는 lake 이름, rating/estimated-flow caveat, period-of-record note다. Annual water-data report PDF가 있으면 `EXTREMES`, `REMARKS`, `COOPERATION`, `GAGE`, `REGULATION` 관련 문장을 함께 확인한다.

결과는 짧게 기록한다. 예를 들어 `USGS note: flow regulated by Blue Marsh Lake and other reservoirs; no direct operation record reviewed`처럼 쓴다. 같은 내용을 `docs/references/basin/usgs_station_notes/{gauge_id}_{station_slug}.md`에도 저장해 둔다. Station page나 PDF를 아직 읽지 않은 상태에서는 원인을 확정하지 않고 `preliminary`로만 둔다.

### 1. Rain severity를 재구성한다

먼저 event가 왜 stress 후보로 들어왔는지 확인한다. `wet_cluster_total_rain`과 `wet_cluster_peak_rainf`는 event footprint의 총량과 순간 강도를 보여주고, `max_prec_ari25_ratio`, `max_prec_ari50_ratio`, `max_prec_ari100_ratio`는 basin별 precipitation proxy 대비 severity를 보여준다.

중요한 것은 `dominant_duration_for_ari100h`와 duration별 ratio다. `max_prec_ari100_1h_ratio`만 1을 넘고 6h, 24h, 72h ratio가 낮으면 짧은 burst형 storm이다. 반대로 24h 또는 72h ratio가 크면 장시간 누적형 storm이라 basin storage, antecedent wetness, reservoir operation 해석이 더 중요해진다.

Read-only 확인 예시는 아래처럼 둔다.

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run python - <<'PY'
import pandas as pd

event_id = "01480685_rain_drbc_historical_stress_0005"
catalog = pd.read_csv(
    "output/model_analysis/extreme_rain/primary_time_aligned/exposure/extreme_rain_event_catalog.csv"
)
row = catalog.loc[catalog["event_id"].eq(event_id)].iloc[0]

cols = [
    "rain_start",
    "rain_peak",
    "rain_end",
    "wet_cluster_total_rain",
    "wet_cluster_peak_rainf",
    "max_prec_ari100_1h_ratio",
    "max_prec_ari100_6h_ratio",
    "max_prec_ari100_24h_ratio",
    "max_prec_ari100_72h_ratio",
    "dominant_duration_for_ari100h",
    "rain_cohort",
]
print(row[cols].to_string())
PY
```

판정 문장은 숫자를 그대로 반복하기보다 형태를 요약한다. 예를 들어 "ARI100 초과가 1h burst에서 주로 나온 event"와 "24-72h 누적 강수가 큰 event"는 원인 후보가 달라진다. 반대로 hydrograph에서 큰 `obs > sim` pulse가 보이는데 event window의 `Rainf`가 약하면, 해당 pulse가 이 rain event의 직접 runoff인지부터 의심해야 한다.

### 2. Observed response를 독립적으로 판정한다

다음으로 observed streamflow가 실제로 flood-like response였는지 본다. `response_class`를 그대로 받아쓰지 말고, `observed_response_peak`, `streamflow_q99_threshold`, `flood_ari2`, `obs_peak_to_flood_ari2`, `response_lag_from_rain_peak_h`를 함께 읽는다.

기본 판정은 아래 순서로 한다.

1. `observed_response_peak >= flood_ari2`이면 최소한 flood proxy response는 있었다고 본다. 이때 모델이 낮으면 underestimation case다.
2. `observed_response_peak >= streamflow_q99_threshold`이지만 `< flood_ari2`이면 high-flow non-flood case다. 이 경우 큰 비가 있었더라도 flood miss라고 단정하지 말고, negative-control 또는 attenuated response로 본다.
3. `observed_response_peak < streamflow_q99_threshold`이면 low-response negative control이다. 이 경우 Model 2 upper quantile이 크게 튀면 false-positive tradeoff를 보여주는 사례가 된다.
4. `response_lag_from_rain_peak_h`가 작은 유역 규모에 비해 매우 길면 storage, reservoir, downstream release, basin mismatch 가능성을 우선 점검한다.
5. Rainf가 거의 없거나 약한 dry window에서 observed streamflow가 Q99 이상으로 올라가거나 plateau를 만들면, rainfall-runoff response로 바로 해석하지 않는다. 먼저 antecedent rain, snowmelt, missed forcing, boundary mismatch를 배제한 뒤 managed release 또는 return flow 후보로 둔다.

Observed-only 판단을 먼저 끝내야 모델 해석이 안정된다. 모델이 크게 튀었다는 사실만으로 observed가 "비정상적으로 낮다"고 말하면 안 된다.

### 3. 모델이 어떤 response를 만들었는지 확인한다

`extreme_rain_stress_error_table_wide.csv`에서 seed별 `model1_window_peak`, `q50_window_peak`, `q95_window_peak`, `q99_window_peak`와 peak time을 본다. 여기서는 모델 성능 우열보다 hydrograph 모양을 읽는 것이 목적이다.

Read-only 확인 예시는 아래처럼 둔다.

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run python - <<'PY'
import pandas as pd

event_id = "01480685_rain_drbc_historical_stress_0005"
wide = pd.read_csv(
    "output/model_analysis/extreme_rain/primary_time_aligned/analysis/extreme_rain_stress_error_table_wide.csv"
)
rows = wide.loc[wide["event_id"].eq(event_id)]

cols = [
    "seed",
    "observed_peak_from_series",
    "observed_peak_time_from_series",
    "model1_window_peak",
    "model1_window_peak_time",
    "model1_signed_peak_timing_error_hours",
    "q50_window_peak",
    "q95_window_peak",
    "q99_window_peak",
    "q99_window_peak_time",
    "q99_signed_peak_timing_error_hours",
]
print(rows[cols].to_string(index=False))
PY
```

모델 peak가 `rain_peak` 직후 크고 observed peak가 훨씬 늦게 작게 나오면, 모델은 자연 유역의 quick response를 만든 반면 실제 outlet flow는 attenuated/released response였을 가능성이 있다. 반대로 모델 peak도 낮고 observed만 낮으면 false-positive라기보다 stress event 자체가 flow response를 만들지 않은 negative-control일 수 있다.

Hydrograph는 `obs < sim` 방향만 보지 않는다. Rainf가 없거나 약한데 observed가 sim보다 갑자기 크고, 그 모양이 자연 recession이 아니라 일정한 plateau, 계단형 상승/하강, 반복적인 daily pulse라면 managed extra-flow signal로 따로 표시한다. 이때 `obs > sim`은 모델이 flood를 과소추정했다는 evidence가 아니라, forcing으로 설명되지 않는 관측 유량 성분이 있다는 evidence일 수 있다.

### 4. Basin-level 원인 후보를 확인한다

원인 후보는 hydromodification부터 확인한다. 작은 유역에서 `NDAMS_2009 > 0`, `MAJ_NDAMS_2009 > 0`, `STOR_NOR_2009`가 크고 `RAW_DIS_NEAREST_MAJ_DAM`이 작으면 reservoir/dam regulation 가능성이 높다. 이 경우 water use보다 storage와 release operation이 peak attenuation과 timing delay를 더 잘 설명하는 경우가 많다.

Water use는 `FRESHW_WITHDRAWAL`과 `PCT_IRRIG_AG`, canal proxy를 함께 본다. 이 값은 작은 유역에서 low-flow bias를 크게 만들 수 있지만, flood peak가 수십 `m3/s` 차이로 눌린 event를 단독으로 설명하기는 어려울 때가 많다. 특히 event가 폭우 직후 peak attenuation과 multi-day lag를 보이면 withdrawal보다는 reservoir/storage를 먼저 본다.

Human-driven flow alteration은 양방향이다. Withdrawal, diversion out, reservoir filling, detention은 `obs < sim` 쪽으로 보일 수 있고, reservoir release, return flow, wastewater discharge, transfer, pump/gate operation은 `obs > sim` 쪽으로 보일 수 있다. 따라서 basin metadata를 볼 때는 "물이 빠져서 눌림"뿐 아니라 "강수 없이 추가 유량이 들어옴"도 함께 열어 둔다.

Land cover와 urban/storage context는 `DEVNLCD06`, impervious, `WATERNLCD06`, wetland, `HIRES_LENTIC_PCT`, StreamStats의 storage-related characteristic을 함께 본다. Urbanization은 일반적으로 quick response를 키울 수도 있지만, stormwater detention이나 pond/lake storage가 크면 hydrograph를 누르고 늦출 수 있다.

Read-only 확인 예시는 아래처럼 둔다.

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run python - <<'PY'
import json
from pathlib import Path

import pandas as pd

gauge_id = "01480685"
manifest = pd.read_csv(
    "output/model_analysis/extreme_rain/primary_time_aligned/event_simq_plots/event_simq_plot_manifest.csv",
    dtype={"gauge_id": str},
)
event = manifest.loc[
    manifest["event_id"].eq(f"{gauge_id}_rain_drbc_historical_stress_0005")
].iloc[0]

cols = [
    "gauge_name",
    "drain_sqkm_attr",
    "hydromod_risk",
    "forest_pct",
    "developed_pct",
    "wetland_pct",
    "NDAMS_2009",
    "MAJ_NDAMS_2009",
    "STOR_NOR_2009",
    "CANALS_PCT",
    "FRESHW_WITHDRAWAL",
]
print(event[cols].to_string())

cache = Path(f"output/basin/all/cache/usgs_streamstats/{gauge_id}.json")
if cache.exists():
    data = json.loads(cache.read_text())
    print({"name": data.get("name"), "isRegulated": data.get("isRegulated")})
PY
```

### 5. Nearby 또는 upstream/downstream 비교를 넣는다

가능하면 같은 storm 시간대의 인접 gauge 또는 같은 stream 상류/하류 gauge를 비교한다. 이 단계가 원인 판정력을 가장 많이 올린다. 같은 `Rainf` burst를 받았는데 상류 natural-ish gauge는 즉각 반응하고, 하류 regulated gauge만 늦고 완만하면 reservoir/dam regulation evidence가 강해진다.

Read-only 확인 예시는 아래처럼 둔다.

```bash
export PATH="/opt/homebrew/bin:$PATH"
uv run python - <<'PY'
from pathlib import Path

import xarray as xr

for gauge_id in ["01480675", "01480685"]:
    path = Path(f"data/CAMELSH_generic/drbc_holdout_broad/time_series/{gauge_id}.nc")
    ds = xr.open_dataset(path).sel(date=slice("2020-08-04 00:00", "2020-08-08 23:00"))
    df = ds[["Rainf", "Streamflow"]].to_dataframe().reset_index()
    rain_peak = df.loc[df["Rainf"].idxmax()]
    q_peak = df.loc[df["Streamflow"].idxmax()]
    print(gauge_id)
    print("rain peak:", rain_peak.date, float(rain_peak.Rainf))
    print("flow peak:", q_peak.date, float(q_peak.Streamflow))
PY
```

인접 비교를 할 때는 "같은 forcing grid를 공유한다"는 점도 같이 확인한다. 같은 `Rainf`가 들어간 두 gauge의 flow response가 다르면 precipitation miss보다 basin operation, storage, routing, boundary 차이가 더 그럴듯해진다.

## 원인 판정 규칙

아래 규칙은 배타적 taxonomy가 아니다. 실제 보고에서는 primary cause 하나와 secondary context를 분리한다.

| 원인 후보 | 지지 evidence | 단독 원인으로 보기 어려운 조건 |
| --- | --- | --- |
| `reservoir/dam regulation` | `isRegulated=true`, `MAJ_NDAMS_2009 > 0`, 큰 `STOR_NOR_2009`, 작은 `RAW_DIS_NEAREST_MAJ_DAM`, observed peak의 큰 lag, 강수 직후 quick response 부재, upstream gauge는 즉각 반응하지만 downstream gauge는 감쇠 | dam/storage proxy가 없고 response lag도 짧으면 주원인으로 올리지 않는다. Model이 과대 peak를 만든 것만으로 reservoir를 추정하지 않는다. |
| `water use/withdrawal` | 높은 `FRESHW_WITHDRAWAL`, irrigation/canal proxy, 여름 또는 갈수기 중심의 `obs < sim`, low-flow/recession 구간의 지속적 bias | 폭우 event에서 peak가 수십 `m3/s` 단위로 눌리고 multi-day lag가 나타나면 단독 원인으로 약하다. Withdrawal은 평균 flux라 event peak attenuation을 직접 설명하려면 추가 근거가 필요하다. |
| `managed release / return flow` | Rainf가 없거나 약한 dry window에서 `obs > sim` pulse나 plateau가 생김, 반복적인 daily pulse, step-like rise/fall, dam/canal/NPDES/transfer/pump context, upstream/downstream에서 특정 지점 이후만 유량이 증가 | antecedent rain, snowmelt, missed forcing, basin boundary mismatch를 배제하지 못하면 단독 원인으로 올리지 않는다. 단일 pulse만 있고 facility proxy가 약하면 low-confidence candidate로 둔다. |
| `urban/storage/detention` | 높은 developed/impervious와 pond/lake/wetland/storage proxy, 짧은 storm에서 observed response가 분산되거나 secondary pulse가 나타남 | urbanization은 quick response를 키우는 방향도 가능하므로, detention/storage 근거 없이 "developed라서 눌림"이라고 쓰지 않는다. |
| `forcing or storm footprint mismatch` | 인접 gauge는 낮은 rain인데 해당 basin forcing만 과도함, radar/gauge reference 불확실, `precip_reference_flag` 이상, event footprint가 basin 일부에만 걸렸을 가능성 | 같은 forcing을 받은 nearby/upstream basin들이 강하게 반응했거나, 여러 duration ratio가 일관되면 forcing miss만으로 설명하지 않는다. |
| `boundary/data quality issue` | 낮은 `overlap_ratio_of_basin`, boundary confidence 문제, estimated flow fraction 높음, station relocation/rating issue note, observed peak timing이 rain window와 물리적으로 맞지 않음 | boundary와 quality gate가 양호하고 nearby comparison이 hydromod를 지지하면 보조 caveat로만 둔다. |

판정 confidence는 `high`, `medium`, `low` 세 단계로 둔다. USGS station note를 읽지 않은 상태에서는 세 단계 confidence를 붙이지 않고 `preliminary`로만 둔다. `high`는 station note를 확인했고, event hydrograph, basin proxy, nearby/upstream comparison 중 최소 두 축이 station note와 같은 원인을 가리킬 때만 쓴다. `medium`은 station note를 확인했지만 비교 gauge가 없거나 basin proxy와 hydrograph 중 일부만 맞을 때 쓴다. `low`는 station note를 확인했는데도 모델-관측 차이를 설명할 basin/event-level 근거가 약할 때 쓴다.

## 01480685 worked example

대상 event는 `01480685_rain_drbc_historical_stress_0005`이고, 유역은 `Marsh Creek near Downingtown, PA`다. 결론은 water use 단독보다 Marsh Creek Reservoir/Dam regulation이 주원인인 high-confidence attenuation case로 보는 것이 안전하다.

Rain severity는 짧은 burst형이다. Time-aligned catalog 기준 `rain_start = 2020-08-04 11:00`, `rain_peak = 2020-08-04 16:00`, `rain_end = 2020-08-04 17:00`이고, `wet_cluster_total_rain = 124.06 mm`, `wet_cluster_peak_rainf = 48.06 mm/h`다. `max_prec_ari100_ratio = 1.15`이고 `dominant_duration_for_ari100h = 1`이라, ARI100 초과 신호는 1h 강수에서 주로 나온다.

Observed response는 flood-like하지 않다. `observed_response_peak = 5.14 m3/s`이고 peak time은 `2020-08-06 18:00`이다. 이는 `rain_peak` 이후 50시간 뒤다. `streamflow_q99_threshold = 4.84 m3/s`는 넘지만 `flood_ari2 = 10.45 m3/s`의 절반 정도라 `obs_peak_to_flood_ari2 = 0.49`다. 따라서 이 event는 `high_flow_non_flood_q99_only`로 보는 것이 맞다.

모델은 강수 직후 자연 유역형 quick response를 만든다. Seed `111 / 222 / 444`에서 Model 1 window peak는 각각 `95.52 / 75.69 / 47.77 m3/s`이고, Model 2 `q99` window peak는 `215.84 / 155.64 / 74.22 m3/s`다. Peak time도 대부분 `2020-08-04 16:00-20:00` 사이로, observed peak보다 약 46-50시간 빠르다. 즉 "모델이 flood response를 놓쳤다"가 아니라, negative-control event에서 모델이 false-positive flood-like response를 만든 case다.

Basin metadata는 regulation 해석을 강하게 지지한다. `drain_sqkm_attr = 52.06 km2`인 작은 유역이고, `hydromod_risk = True`, `NDAMS_2009 = 1`, `MAJ_NDAMS_2009 = 1`, `STOR_NOR_2009 = 151.10 ML/km2`다. StreamStats cache도 `isRegulated = true`로 되어 있다. `FRESHW_WITHDRAWAL = 192.43 ML/yr/km2`라 water use context는 있지만, 이 event의 multi-day lag와 flood peak attenuation을 단독으로 설명하기에는 약하다.

Upstream/downstream comparison도 regulation 쪽이다. 같은 2020-08-04 16:00 storm에서 upstream `01480675 Marsh Creek near Glenmoore`는 `Rainf = 48.06 mm/h`를 받고 `2020-08-04 19:00`에 `Streamflow = 9.20 m3/s`까지 빠르게 반응했다. Downstream `01480685`는 같은 rain peak를 받았지만 `2020-08-06 18:00`에야 `5.14 m3/s`로 완만하게 peak가 나왔다. 같은 forcing 아래에서 상류는 quick response, 하류는 delayed/attenuated response를 보이므로 precipitation miss보다 reservoir/dam regulation 해석이 더 강하다.

보고 문장은 아래처럼 쓴다.

```text
01480685-0005는 1h ARI100 proxy를 넘는 short-burst rain event였지만, 관측 유량은 Q99를 살짝 넘고 flood ARI2의 0.49배에 머문 high-flow non-flood case다. 모델은 강수 직후 큰 quick response를 만들었지만, 관측 peak는 50시간 지연되어 작게 나타났다. 작은 유역 바로 상류의 major dam/storage proxy와 upstream/downstream contrast가 모두 같은 방향이므로, 이 event는 water use 단독보다는 Marsh Creek Reservoir/Dam regulation에 의한 attenuation case로 분류한다.
```

## 01471510 worked example

대상 event는 `01471510_rain_drbc_historical_stress_0005`이고, 유역은 `Schuylkill River at Reading, PA`다. 이 예시는 작은 유역의 단일 dam attenuation 사례가 아니라, 큰 mainstem regulated basin에서 ARI100급 24h rain이 Q99+ high flow를 만들었지만 flood proxy까지는 넘지 않은 mixed attenuation case로 보는 것이 안전하다. USGS source summary는 [`01471510_schuylkill_river_at_reading_pa.md`](../../../references/basin/usgs_station_notes/01471510_schuylkill_river_at_reading_pa.md)에 따로 저장했다.

Station note는 regulation 해석을 먼저 열어 둬야 함을 보여준다. USGS page와 historic water-data report PDF는 이 station의 flow가 Still Creek Reservoir, Blue Marsh Lake, Lake Ontelaunee의 영향을 받는다고 설명한다. 다만 이 source는 station-level context이지, 2010-09-30 event의 실제 reservoir operation record는 아니다. 따라서 confidence는 `medium`으로 두고, primary cause를 `regulated/storage context`로 쓰되 specific operation claim은 하지 않는다.

Rain severity는 장시간 누적형이다. Time-aligned catalog 기준 `rain_start = 2010-09-30 09:00`, `rain_peak = 2010-09-30 14:00`, `rain_end = 2010-10-01 09:00`이고, `wet_cluster_total_rain = 144.98 mm`, `wet_cluster_peak_rainf = 12.10 mm/h`다. `max_prec_ari100_ratio = 1.01`이고 `dominant_duration_for_ari100h = 24`라, `01480685-0005`처럼 1h burst가 아니라 24h 누적 강수가 stress signal을 만든 event다.

Observed response는 high-flow non-flood다. `observed_response_peak = 431.83 m3/s`이고 peak time은 `2010-10-01 17:00`이다. 이는 `rain_peak` 이후 27시간 뒤다. `streamflow_q99_threshold = 249.61 m3/s`는 넘지만 `flood_ari2 = 482.01 m3/s`에는 못 미쳐 `obs_peak_to_flood_ari2 = 0.90`이다. 따라서 이 event는 flood miss라기보다 ARI2 바로 아래에서 멈춘 `high_flow_non_flood_q99_only` case로 정리한다.

모델 response는 seed별로 엇갈린다. Seed `111`의 Model 1은 `734.31 m3/s`로 observed보다 `+70.05%` 크게 예측했고, seed `222 / 444`는 각각 `272.01 / 231.10 m3/s`로 낮게 예측했다. Model 2 `q99` peak는 seed `111 / 222 / 444`에서 `342.17 / 325.37 / 324.78 m3/s`로 모두 observed peak보다 낮다. 즉 이 case는 단순한 model false-positive가 아니라, deterministic seed 하나는 over-response, 다른 deterministic seeds와 quantile upper tail은 under-response를 보인 mixed model-behavior case다.

Basin metadata는 regulation/storage context를 강하게 지지한다. 유역 면적은 `2303.51 km2`로 크고, StreamStats cache는 `isRegulated = true`다. GAGES-II hydromod proxy도 `NDAMS_2009 = 54`, `MAJ_NDAMS_2009 = 21`, `STOR_NOR_2009 = 48.95 ML/km2`, `STOR_NID_2009 = 173.30 ML/km2`, `RAW_DIS_NEAREST_MAJ_DAM = 9.44 km`를 보인다. Water-use proxy인 `FRESHW_WITHDRAWAL = 47.22 ML/yr/km2`와 `CANALS_PCT = 1.47%`도 있지만, 이 event의 Q99+ response와 ARI2 직전 attenuation을 단독으로 설명하는 증거로 쓰기에는 regulation/storage evidence가 더 직접적이다.

Nearby comparison은 mixed interpretation을 뒷받침한다. 같은 2010-09-30 to 2010-10-06 window에서 upstream/mainstem `01470500 Schuylkill River at Berne`은 `2010-10-01 12:00`에 `188.87 m3/s`로 peak가 났고, `01470960 Tulpehocken Creek at Blue Marsh Damsite`는 `2010-10-05 14:00`에야 `10.07 m3/s`로 늦게 peak가 났다. 반면 `01471510 Reading`은 `2010-10-01 17:00`에 `431.83 m3/s`, downstream `01472000 Pottstown`은 `2010-10-01 11:00`에 `593.24 m3/s`, `01473500 Norristown`은 `2010-10-01 15:00`에 `2017.57 m3/s`까지 올랐다. Blue Marsh Damsite의 delayed signal은 storage/release context를 지지하지만, 큰 mainstem과 하류 tributary contributions 때문에 `01480685`처럼 단일 upstream/downstream attenuation으로만 설명하면 과하다.

보고 문장은 아래처럼 쓴다.

```text
01471510-0005는 24h ARI100 proxy에 거의 해당하는 long-duration rain event였고, 관측 유량은 Q99를 넘었지만 flood ARI2의 0.90배에 머문 high-flow non-flood case다. USGS station note와 hydromod metadata는 Still Creek Reservoir, Blue Marsh Lake, Lake Ontelaunee를 포함한 regulated/storage context를 강하게 지지한다. 다만 이 유역은 2303 km2 규모의 mainstem basin이고 downstream gauges에서는 큰 flood response가 나타나므로, 특정 operation 때문에 suppressed됐다고 단정하지 않고 regulated/storage context plus storm-footprint/routing effects가 Reading outlet response를 ARI2 아래로 제한한 medium-confidence case로 분류한다.
```

## 보고 템플릿

다른 event를 진단할 때는 아래 항목을 채운다.

```text
event_id:
gauge_id / gauge_name:
diagnosis:
confidence:

station-note check:
- USGS monitoring location page:
- annual water-data report PDF:
- saved station-note artifact:
- relevant station remarks:

rain evidence:
- rain_start / rain_peak / rain_end:
- wet_cluster_total_rain:
- wet_cluster_peak_rainf:
- max_prec_ari100_ratio and dominant duration:

observed response:
- observed_response_peak and time:
- streamflow_q99_threshold:
- flood_ari2 and obs_peak_to_flood_ari2:
- response_class:
- lag from rain peak:

model behavior:
- Model 1 window peak and timing by seed:
- Model 2 q50/q95/q99 window peak and timing by seed:
- false-positive or under-response interpretation:
- obs < sim suppression pattern or obs > sim extra-flow pattern:

basin evidence:
- area and land cover:
- hydromod flags:
- storage/dam/canal/water-use proxies:
- StreamStats context:

nearby/upstream comparison:
- comparison gauge:
- same-storm Rainf:
- observed Streamflow peak and timing:
- implication:

final interpretation:
- primary cause:
- secondary context:
- direction: suppressed response / managed extra-flow / mixed:
- not-likely explanation:
- caveat:
```

최종 문장에서는 causal claim을 과장하지 않는다. "reservoir operation record를 직접 본 결과"가 아니라면 `operation caused`보다 `regulated/storage context best explains the attenuation` 또는 `managed-flow context is a plausible explanation for the extra-flow signal`처럼 쓴다. `q99`가 큰 peak를 만들었다는 사실은 false-positive tradeoff evidence이지, observed가 잘못됐다는 근거가 아니다. 마찬가지로 dry-window에서 `obs > sim`이 생겼다는 사실만으로 특정 시설물 방류를 확정하지 않고, antecedent rain, snowmelt, missed forcing, boundary/data quality를 배제한 정도에 맞춰 confidence를 낮추거나 높인다.
