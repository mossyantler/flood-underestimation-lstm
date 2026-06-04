@AGENTS.md

GAGES-II basin geometry를 지도 렌더링에 사용할 때는 `EPSG:5070`(NAD83 / Conus Albers)을 기준 CRS로 사용한다. USGS `gagesii-basins` API/cache를 우선하고, `.prj` 없는 로컬 GAGES-II boundary도 `EPSG:5070` 기준으로 처리한다. 렌더링·clip·거리/면적 계산은 DRBC boundary와 함께 `EPSG:5070`에서 수행한다.
