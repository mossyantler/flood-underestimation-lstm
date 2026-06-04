# output/model_analysis 재구조화 실행 계획서

**작성:** 2026-05-31
**상태:** 승인 대기
**근거 표준:** `CLAUDE.md` 산출물 경로 규칙, `AGENTS.md` output 분석 폴더 표준 (이미 고정됨)

---

## 1. 목표

`output/model_analysis/` 분석 산출물을 **표준 폴더 구조 + 파일명 규칙**으로 재배치한다.
이름 변경은 구조 이동 뒤에 적용한다(구조 먼저, 이름 나중).

확정 top-level:

| 주제 | 형태 | 하위 분석 |
| --- | --- | --- |
| `primary/` (구 `drbc_test`) | 그룹 | `metrics/` · `calibration/` |
| `confirmed_flood/` | 평탄 | NWS flood stage 기준 |
| `q99_analysis/` | 그룹 | `performance/` · `causes/` |
| `band_signal/` (구 `rising_limb_comparison` + `drbc_test/ub_*`) | 그룹 | `band_shape/` · `slope_signal/` · `signal_sweep/` · `method_compare/` |
| `shap/` (구 `shap_analysis`) | 그룹 | `q99/` · `test_split/` |

`band_signal/` = 관측 첨두가 예측 밴드(q50~q99) 어디에 드는지(관측 위치 구간) + 그 위치를 예측하는 신호. 구 `drbc_test`의 `ub_*`(band_shape)와 구 `rising_limb_comparison`을 통합.

표준 하위: `figures/ tables/ data/ report/ gallery/` (+ 각 폴더 `README.md`).

---

## 2. 영향 범위

| 항목 | 규모 |
| --- | --- |
| `model_analysis` 문자열 박힌 스크립트 | **112개** |
| `expanded_drbc` 문자열 박힌 스크립트 | 51개 |
| output 데이터 크기 | 17G (gitignored) |
| 갤러리 PNG | 2만+ (q99 event_plots/simq 10G가 주범) |
| git tracked in output | `output/AGENTS.md` 1개뿐 → git 충돌 거의 없음 |

### 핵심 위험 — 스크립트 폴더명 ≠ output 주제명

| 스크립트 폴더 | 실제 산출 output 주제 |
| --- | --- |
| `scripts/model/expanded_drbc/` | `primary/`(rq*) + `band_signal/`(ub_*→band_shape, rise_slope, signal_sweep) |
| `scripts/model/extreme_rain/` | `q99_analysis/` |
| `scripts/model/overall/` | `q99_analysis/causes/` + `shap/` + `primary/` eval |
| `scripts/model/confirmed_flood/` | `confirmed_flood/` |
| `scripts/model/hydrograph/` | `primary/calibration/` 등 |

→ 단순 1:1 매핑 아님. 출력경로 문자열을 **스크립트별로** 확인해야 함.

### 검증 한계

대부분 분석 스크립트는 `runs/` checkpoint + 전체 데이터 + CUDA 필요 → **로컬 전량 재실행 불가**.
출력경로 수정의 정합성은 (a) 정적 grep 일치 + (b) 재실행 가능한 일부만 smoke 재생성으로 확인.

---

## 3. 단계별 실행

### Phase 0 — 사전 안전장치
1. 현재 트리 매니페스트 저장: `find output/model_analysis -type f > tmp/reorg/manifest_before.txt`
2. 크기·파일수 스냅샷 기록.
3. 즉시 삭제 대상 정리:
   - `confirmed_flood/hydrographs_smoke/` (smoke 찌꺼기)
   - `confirmed_flood/confirmed_flood/` (중복 의심 — 내용 확인 후)
   - 전 디렉토리 `.DS_Store`
4. gitignored 확인 (`git status` 영향 0인지).

### Phase 1 — 폴더 구조 이동 (내용 보존, mv)
주제별 `mv` 매핑. 갤러리(대용량)는 마지막에.

**① `drbc_test/` → `primary/` (그룹 2) + `band_signal/band_shape/`**
```
drbc_test/figures/{rq*,stratified_*,metric_boxplots,paired_seed_comparison}  → primary/metrics/figures/
drbc_test/tables/{rq*,paired_*,primary_*,stratified_*,basin_metrics,cross_tab_*}  → primary/metrics/tables/
drbc_test/{raw_metrics,raw_timeseries,required_series}                        → primary/metrics/data/
drbc_test/{evaluation_manifest.csv,performance_analysis_summary.json,timeseries_summary.json}  → primary/metrics/report/
drbc_test/probabilistic_diagnostics/figures/   → primary/calibration/figures/
drbc_test/probabilistic_diagnostics/*.csv,*.json  → primary/calibration/tables/
drbc_test/probabilistic_diagnostics/report/report.md  → primary/calibration/report/
drbc_test/figures/ub_*                          → band_signal/band_shape/figures/   (ub_ → band_)
drbc_test/tables/ub_*                           → band_signal/band_shape/tables/    (ub_ → band_)
drbc_test/report/quantile_ladder_signal_explainer.html  → band_signal/band_shape/report/
```

**② `confirmed_flood/` → 평탄**
```
confirmed_flood/{figures,analysis/figures,coverage/figures}  → confirmed_flood/figures/
confirmed_flood/{tables,analysis/*.csv,performance/*}        → confirmed_flood/tables/
confirmed_flood/{catalog,coverage/*.csv,inference,noaa_cache}  → confirmed_flood/data/
confirmed_flood/hydrographs/{major,minor,moderate}           → confirmed_flood/gallery/
```

**③ `q99_analysis/` → 그룹 2 (expanded_drbc 벗김)**
```
q99_analysis/expanded_drbc/figures/                          → q99_analysis/performance/figures/
q99_analysis/expanded_drbc/analysis/figures/peak_quantile_bracket/  → q99_analysis/performance/figures/
q99_analysis/expanded_drbc/analysis/*.csv                    → q99_analysis/performance/tables/
q99_analysis/expanded_drbc/{inference,exposure,map_geometry} → q99_analysis/performance/data/
q99_analysis/expanded_drbc/analysis/*_stress_test_report.md,analysis_summary.json  → q99_analysis/performance/report/
q99_analysis/expanded_drbc/{event_plots,event_simq_plots,basin_performance/hydrograph}  → q99_analysis/performance/gallery/
q99_analysis/figures/{q99_driver_*,q99_event_forcing_*,q99_lstm_attribution_*}  → q99_analysis/causes/figures/
q99_analysis/tables/*                                        → q99_analysis/causes/tables/
```
→ `expanded_drbc/` 폴더 소멸.

**④ `rising_limb_comparison/` + `drbc_test/ub_*` → `band_signal/` 그룹 4**
```
(band_shape는 ① 에서 이동 → band_signal/band_shape/)
rising_limb_comparison/quantile_rise_slope_signal/{summary.md,tables}  → band_signal/slope_signal/{report,tables}
rising_limb_comparison/signal_sweep/{figures,tables}        → band_signal/signal_sweep/
rising_limb_comparison/figures/{m4_*,spearman}              → band_signal/method_compare/figures/
rising_limb_comparison/rise_h_windows/                      → band_signal/method_compare/data/
```
→ `rising_limb_comparison/` 폴더 소멸. `band_signal/` 최종 하위 = `band_shape/ slope_signal/ signal_sweep/ method_compare/`.

**⑤ `shap_analysis/` → `shap/` 그룹 2**
```
shap_analysis/q99_analysis/{figures,tables,report}          → shap/q99/
shap_analysis/q99_analysis/metadata/                        → shap/q99/data/
shap_analysis/test_split_analysis/{figures,tables,report}   → shap/test_split/
shap_analysis/test_split_analysis/metadata/                 → shap/test_split/data/
```

각 신규 분석 폴더에 `README.md` 스텁 생성 (무엇을→왜→어떻게 해석).

### Phase 2 — 생성 스크립트 출력경로 수정
1. 경로 rename map 작성 (Phase 1 매핑 = source-of-truth).
2. 각 스크립트의 **출력경로 리터럴** 확인:
   - `grep -n "model_analysis" <script>` 로 출력 문자열 위치 특정.
   - 변수로 조립된 경로(`base / "drbc_test"` 등)는 수동 확인.
3. 우선순위 그룹:
   - **A. official runner** (`scripts/runs/official/run_expanded_drbc_*.sh`, `run_subset300_extreme_rain_*.sh`) — 진입점, 먼저.
   - **B. `scripts/model/{confirmed_flood,expanded_drbc,extreme_rain,overall,hydrograph}/`** — 핵심 분석.
   - **C. `scripts/_lib/expanded_drbc.py`** — 공용 helper (다수 의존, 신중).
   - **D. dashboard export / dev / event_regime / sequence** — 후순위.
4. **스크립트 디렉토리 rename(`expanded_drbc`→…)은 이 계획 범위 밖** (별 작업). 지금은 출력경로 문자열만.

### Phase 3 — 파일명 규칙 적용
표준대로:
- 폴더 맥락 prefix 제거: `confirmed_flood_`, `q99_`, `primary_`.
- 실험맥락 prefix 제거: `subset300_`, `expanded_drbc_`. "expanded" 단어 전면 삭제.
- `ub_` → `band_`.
- 식별자 보존: `seed*`, `model1/2`, `q50~q99`, `with/without_outliers`. 약어 `rq1~4`,`m3/m4`,`q99` 유지.
- 기존 산출 파일명 + **스크립트 내 출력 파일명 문자열** 동시 수정.

### Phase 4 — 문서 동기화
- `output/AGENTS.md` 재작성 (현재 stale, 옛 `overall_analysis/quantile_analysis` 구조 → 신 구조).
- `output/model_analysis/README.md` 재작성.
- `scripts/README.md`, `scripts/AGENTS.md` 출력경로 언급 갱신.
- `docs/experiment/method/model/model_analysis_output_layout.md` 갱신.
- `dashboard/lib/` snapshot 경로 참조 점검.

### Phase 5 — 검증
- 정적: `manifest_before` ↔ `manifest_after` 파일수·총량 대조 (이동 누락 0).
- 정적: `grep -r "drbc_test\|rising_limb_comparison\|shap_analysis\|expanded_drbc" scripts/` 잔존 0 (의도 제외).
- 동적(가능 범위): smoke 재실행으로 신 경로 생성 확인 (`tmp/`에 한정).
- dashboard `npm run typecheck` (snapshot 경로 영향 시).

---

## 4. 롤백
- Phase 1은 mv만 → 역 mv 매핑으로 복원 가능. `manifest_before.txt` 기준.
- Phase 2·3 스크립트 수정은 git tracked → `git checkout` 복원.
- output은 gitignored라 git 롤백 불가 → Phase 0 매니페스트가 유일 복원 근거. 대용량 삭제 전 매니페스트 필수.

---

## 5. 결정 확정
1. **band_shape 위치**: `primary`에서 빼서 `band_signal/`로 통합. `ub_*`(밴드 모양/위치/gap) + 구 `rising_limb_comparison`을 `band_signal/` 한 우산. → `primary/`는 `metrics/`+`calibration/` 2개.
2. **`confirmed_flood/confirmed_flood/` 중복 폴더**: 실재하지 않음(유령, 트리 출력 오인). 처리 불필요.
3. **스크립트 디렉토리 rename**(`expanded_drbc`/`extreme_rain` → 의미명): **이번 범위 밖.** output 재구조화 완료+검증 후 별도 작업. (import 경로·runner·`run_all.py` 영향 → output 이동과 동시 진행 금지, 순차 분리.)
4. **재실행 불가 스크립트 검증**: 정적 검증 전량 필수(옛 경로 grep=0, 신 경로 일치) + 로컬 가능한 가벼운 스크립트 1~2개만 tmp smoke. CUDA/checkpoint 필요분은 다음 공식 GPU 실행에서 자연 검증, 그 전까진 정적 통과=잠정 OK.

---

## 6. 권장 실행 순서
Phase 0 → 1 (주제별, 갤러리 마지막) → 검증(파일수) → 2 (runner→핵심→helper) → 3 → 4 → 5.
각 Phase 종료마다 매니페스트/typecheck로 중간 검증. 한 번에 몰아서 하지 않는다.
