# basins/ Agent Notes

루트 `AGENTS.md`를 먼저 따른다. 이 폴더는 CAMELSH 원자료, shapefile, attributes, DRBC boundary 같은 공간/유역 원천 자료를 둔다.

---

## 디렉토리 구조

```text
basins/
├── CAMELSH/                  # upstream CAMELSH code/reference checkout (gitignored)
├── CAMELSH_data/             # CAMELSH 원자료와 attributes (gitignored)
│   ├── attributes/           # static attributes source-of-truth
│   ├── hourly_observed/      # hourly observed NetCDF 등 원시 시계열
│   └── shapefiles/           # CAMELSH basin geometry
├── CAMELSH_download/         # 원자료 다운로드 staging (있을 수 있음, gitignored)
├── drbc_boundary/            # 공식 DRBC boundary layer
├── huc8_delware/             # 초기 탐색용 legacy HUC8 자료
└── us_boundaries/            # 지도 plotting 보조 경계 자료 (gitignored)
```

---

## 구성 규칙

- `basins/drbc_boundary/drb_bnd_polygon.shp`는 DRBC holdout을 정의하는 공식 경계다. 경계 파일을 바꾸거나 대체하면 split 정의와 문서 정합성에 직접 영향이 있으므로 관련 scripts/docs도 함께 갱신한다.
- `basins/CAMELSH/`, `basins/CAMELSH_data/`, `basins/CAMELSH_download/`는 대용량/원자료 성격이며 gitignored다. 원자료를 직접 수정하기보다 반복 가능한 script로 변환한다.
- raw-to-prepared dataset 결과는 `data/CAMELSH_generic/` 아래에 둔다. screening, diagnostics, reference comparison 같은 분석 산출물은 `output/` 아래에 둔다.
- CAMELSH basin ID는 문자열로 다루고, USGS site number의 leading zero가 사라지지 않게 한다.
- 좌표계가 없는 CAMELSH shapefile은 기존 scripts 관례처럼 WGS84(`EPSG:4326`)로 해석하고, 면적/overlap 계산은 적절한 projected CRS를 사용한다.
- `basins/CAMELSH_data/attributes/`가 static attributes의 source-of-truth다. 새 static attribute를 추가하거나 변경하면 이 경로를 기준으로 처리하고 관련 config와 docs를 함께 갱신한다.
- `basins/huc8_delware/`는 초기 HUC8 탐색용 레거시 자료다. 현재 공식 workflow에서 사용하지 않으므로 수정하거나 의존성을 추가하지 않는다.
