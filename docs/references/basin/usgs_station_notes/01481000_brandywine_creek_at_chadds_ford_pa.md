# 01481000 - Brandywine Creek at Chadds Ford, PA

Reviewed on 2026-05-06 for the final-wave basin hydrograph diagnosis.

## Checked sources

- USGS monitoring location page: https://waterdata.usgs.gov/monitoring-location/USGS-01481000/
- USGS current-conditions legacy page: https://waterdata.usgs.gov/nwis/uv?legacy=1&site_no=01481000
- USGS site service record: https://waterservices.usgs.gov/nwis/site/?format=rdb&sites=01481000&siteOutput=expanded
- USGS Water-Year Summary page: https://waterdata.usgs.gov/pa/nwis/wys_rpt/?site_no=01481000
- USGS Water-Data Report PDF, water year 2013: https://wdr.water.usgs.gov/wy2013/pdfs/01481000.2013.pdf
- USGS Scientific Investigations Report 2023-5086, September 2021 Ida flood characterization: https://pubs.usgs.gov/publication/sir20235086/full

## Station facts

The official USGS station name is `Brandywine Creek at Chadds Ford, PA`. The site service gives drainage area `287 mi2`, consistent with the local CAMELSH/DRBC area of about `755.17 km2`.

The current station text places the gage in Delaware County, Pennsylvania, on the left bank `27 ft` upstream from the Penn Central Railroad bridge at Chadds Ford, `150 ft` upstream from Harvey Run, and `1,200 ft` downstream from the U.S. Highway 1 bridge. Surface-water records cover August 1911 to September 1953 and October 1962 to the current period, with prior monthly discharge published before October 1911.

The current station text describes a water-stage recorder, crest-stage gage, water-quality monitor, and Pluvio precipitation gage. The current datum is `149.7 ft` above NAVD88. USGS notes that the gage datum had previously been erroneously reported as `150.45 ft` above NGVD29 before January 3, 2023.

## Regulation and water-use context

The key station-context fact is upstream regulation, but not a fully regulated target outlet. The 2013 Water-Data Report states that flow has been regulated since November 1973 by Marsh Creek Reservoir, station `01480684`, about `17 mi` upstream. This is consistent with the local GAGES-II hydromod metadata showing multiple dams in the contributing basin, including major dams.

The checked local StreamStats cache for this station reports `isRegulated = false`, which conflicts with the Water-Data Report remark. For basin diagnosis, treat the direct Water-Data Report regulation remark as a required caveat, while recognizing that Chadds Ford integrates a much larger main-stem Brandywine basin and is not equivalent to the completely regulated Marsh Creek outlet.

The USGS 2023 Ida flood report identifies the September 2021 Chadds Ford peak as `49,000 ft3/s`, rank `1`, with annual exceedance probability less than `0.2%` and recurrence interval greater than `500 yr`. The report also includes Brandywine Creek flood-documentation mapping near Chadds Ford. This supports treating the September 2021 peak as a real regional extreme flood, not a release-like artifact.

## Data-quality notes

The 2013 Water-Data Report rates records as good except estimated daily discharges, which are poor. The local CAMELSH hourly streamflow series for this station begins with valid observations on `2007-10-01 05:00`, so earlier extreme-rain catalog events at this station have unrated observed-response coverage in the local analysis artifacts.

No hourly reservoir operation, gate-setting, storage, release, diversion, or withdrawal operation records were reviewed for this note. Event-level release claims should therefore remain low confidence unless supported by separate operation records.
