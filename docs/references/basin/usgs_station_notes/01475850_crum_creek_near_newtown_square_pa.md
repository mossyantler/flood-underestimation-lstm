# USGS station note: 01475850 Crum Creek near Newtown Square, PA

Accessed: 2026-05-06 Asia/Seoul.

Sources checked:

- USGS monitoring location page: https://waterdata.usgs.gov/monitoring-location/USGS-01475850/
- USGS legacy current-conditions page with station text: https://waterdata.usgs.gov/nwis/uv?legacy=1&site_no=01475850
- USGS Water-Year Summary Reports page: https://waterdata.usgs.gov/nwis/wys_rpt/?site_no=01475850
- USGS annual water-data report PDF, water year 2003: https://pubs.usgs.gov/wdr/wdr-pa-03-1/pdfs/01475850.pdf

Station/source summary:

- Station name: `01475850 Crum Creek near Newtown Square, PA`.
- Location: Delaware County, Pennsylvania, at Castle Rock bridge on State Highway 3, `0.6 mi` upstream from Preston Run, `0.8 mi` upstream from Springton Reservoir, and `2.0 mi` west of Newtown Square.
- Drainage area: USGS lists `15.8 mi2`, close to the local CAMELSH/DRBC area of `40.98 km2`.
- Period of record: October 1981 to current year, with occasional low-flow measurements in water years 1932, 1949, and 1970-1977, plus annual maximum records for 1977-1981.
- Gage/datum: water-stage recorder and crest-stage gage. The current station text and water-year 2003 PDF list the datum as `207.75 ft` above NGVD29.
- Cooperation/funding: Delaware River Basin Commission.
- Regulation/diversion remarks: the checked USGS station text does not state upstream regulation or diversion for this site. The station is upstream from Springton Reservoir, so the reservoir is not a direct upstream outlet-control explanation for this gauge. The local StreamStats cache also reports `isRegulated = false`.
- Rating/quality caveat: the water-year 2003 PDF describes discharge records as fair except estimated daily discharges, which are poor. Its 2003 peak-flow table notes that the June 20, 2003 annual maximum was above a base discharge of `600 ft3/s` and that the peak was from a rating curve extended above `1,300 ft3/s` using a slope-area measurement.
- Water-Year Summary availability: the USGS Water-Year Summary Reports app was checked, but the command-line/static fetch exposed the Shiny application shell rather than a specific rendered 01475850 summary. The historical water-year 2003 PDF was available and used as the report-style source.

Use in basin diagnosis:

Do not treat this station as a known directly regulated outlet. The more defensible station-level context is a small, partly developed Piedmont basin with high local water-use proxy in the CAMELSH/GAGES metadata, one minor dam proxy, and no USGS/StreamStats regulation flag. Event-scale hydrograph mismatches should first be read as small-basin flashiness, gridded-precipitation footprint mismatch, local storage/detention, or data/rating uncertainty before invoking reservoir operation.
