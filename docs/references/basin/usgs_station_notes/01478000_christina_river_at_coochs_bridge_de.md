# USGS station note: 01478000 Christina River at Coochs Bridge, DE

Accessed: 2026-05-06 Asia/Seoul.

Sources checked:

- USGS monitoring location page: https://waterdata.usgs.gov/monitoring-location/01478000/
- USGS legacy current-conditions page with station text: https://waterdata.usgs.gov/nwis/uv?legacy=1&site_no=01478000
- USGS Water-Year Summary Reports page: https://waterdata.usgs.gov/nwis/wys_rpt/?site_no=01478000
- USGS annual water-data report PDF, water year 2001: https://pubs.usgs.gov/wdr/wdr-md-de-dc-01-1/pdf/WDR-MD-DE-DC.2001vol1.pdf

Station/source summary:

- Station name: `01478000 Christina River at Coochs Bridge, DE`.
- Location: New Castle County, Delaware, on the right bank `60 ft` downstream from the highway bridge, `0.5 mi` southeast of Coochs Bridge, `3.3 mi` south of Newark, `3.6 mi` upstream from Belltown Run, and `22.6 mi` upstream from the mouth.
- Drainage area: USGS lists `20.5 mi2`, close to the local CAMELSH/DRBC area of `54.01 km2`.
- Period of record: April 1943 to current year.
- Gage/datum: water-stage recorder and crest-stage gage. The current USGS station text lists datum `24.43 ft NAVD88` and `25.54 ft NGVD29`. Earlier gage locations were at the same datum: a nonrecording gage upstream of the bridge before September 14, 1944; a recording gage on the left bank at the downstream side of the bridge from September 14, 1944 to May 13, 1969; and a recording gage on the left bank `82 ft` downstream from the bridge from May 26, 1969 to December 5, 1973.
- Regulation/diversion remarks: the checked USGS station text states that low and medium flow are regulated by a mill upstream from the station. It does not identify a major upstream reservoir or flood-control dam for this site. The local StreamStats cache reports `isRegulated = false`.
- Rating/quality caveat: the Water-Year Summary page states that water years 2020-2021 discharge records were good; water years 2022-2024 were good except estimated discharges, which were poor; and water year 2013 and earlier accuracy statements are in Annual Water Data Reports. The water-year 2001 PDF reports no estimated daily discharges, records good, and the same low/medium-flow mill regulation note.
- Water-Year Summary availability: the USGS Water-Year Summary Reports page was available for this site and states that water-year summaries exist for recent years, while annual water-data reports cover older years. A historical water-year 2001 PDF was available and used as a report-style source.

Use in basin diagnosis:

Do not treat this site as a known major reservoir-regulated flood outlet. The defensible station-level context is a small Christina River basin with some low/medium-flow mill regulation in the official USGS text, high developed land in local attributes, high water-withdrawal proxy in GAGES-II, but no local dam/storage proxy and `isRegulated = false` in the StreamStats cache. Event-scale high-flow mismatches should therefore be diagnosed first as small-basin storm-footprint/local runoff sensitivity, model amplitude error, or data coverage/rating uncertainty; mill regulation is most appropriate as low-flow or recession context unless event evidence directly supports a managed-flow claim.
