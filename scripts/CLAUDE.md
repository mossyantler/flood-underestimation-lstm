@AGENTS.md

GAGES-II 렌더링 script는 `EPSG:5070`을 기준 CRS로 사용한다. USGS `gagesii-basins` API/cache를 우선 사용하고, `.prj` 없는 로컬 boundary도 `EPSG:5070` 기준으로 처리한다. Manifest에는 geometry source, `target_crs=EPSG:5070`, cache 경로를 남긴다.
