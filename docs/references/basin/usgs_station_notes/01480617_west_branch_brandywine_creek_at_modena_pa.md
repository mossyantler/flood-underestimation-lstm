# USGS station note: 01480617 West Branch Brandywine Creek at Modena, PA

Accessed: 2026-05-06 Asia/Seoul.

Sources checked:

- USGS monitoring location page: https://waterdata.usgs.gov/monitoring-location/01480617/
- USGS legacy current-conditions page with station text: https://waterdata.usgs.gov/nwis/uv?legacy=1&site_no=01480617
- USGS site inventory page: https://waterdata.usgs.gov/nwis/inventory/?agency_cd=USGS&site_no=01480617
- USGS Water-Year Summary Reports page: https://waterdata.usgs.gov/nwis/wys_rpt/?site_no=01480617
- USGS Water-Data Report search result for station PDF text, checked for availability; direct `https://wdr.water.usgs.gov/wy2013/pdfs/01480617.2013.pdf` returned 404 on the access date.

Station/source summary:

- Station name: `01480617 West Branch Brandywine Creek at Modena, PA`.
- Location: Chester County, Pennsylvania, Hydrologic Unit `02040205`. The checked USGS station text places the gage on the left bank at the SR 15068 bridge at Modena, `300 ft` upstream from Dennis Run.
- Drainage area: USGS lists `55.0 mi2`, close to the local CAMELSH/DRBC area of `143.49 km2`.
- Period of record: January 1970 to current year.
- Gage/datum: water-stage recorder, crest-stage gage, water-quality monitor, and Pluvio precipitation gage. The checked station text lists gage elevation `262.52 ft` above NAVD88, with satellite telemetry at the station.
- Cooperation and water-use context: USGS station text says records of diversion were provided by the City of Coatesville. The station is funded by the Chester County Water Resources Authority and the USGS. Search-indexed USGS water-data text for this station notes some diversion from Rock Run Reservoir to West Branch Brandywine Creek through the Coatesville water-supply system; this was not recovered as a directly downloadable annual station PDF on the access date.
- Regulation/diversion interpretation: the checked source set supports a local diversion/water-supply context, but the live station text does not identify a flood-control reservoir operation at the Modena gage. The local StreamStats cache reports `isRegulated = false`. Local GAGES-II hydromodification attributes show `NDAMS_2009 = 2`, `MAJ_NDAMS_2009 = 1`, `STOR_NOR_2009 = 19.21 ML/km2`, nearest dam distance `6.53 km`, nearest major dam distance `8.51 km`, `FRESHW_WITHDRAWAL = 186.87 ML/yr/km2`, `NPDES_MAJ_DENS = 1.394`, and no mapped canals.
- Rating/quality caveat: the checked Water-Year Summary page was available through the USGS water-year-summary interface, but the static HTML did not expose a clean station-report manuscript without interacting with the application. The legacy station remarks note interruptions in water-quality records from equipment malfunctions; no specific flood-rating caveat was recovered from the live station text during this review.

Use in basin diagnosis:

Treat this as a West Branch Brandywine station with documented water-supply/diversion context and moderate local hydromodification proxies, but not as a high-confidence flood-control-reservoir outlet. Event-scale diagnosis should rely on hydrograph timing, observed response magnitude, model error direction, and the upstream Coatesville / downstream Brandywine comparisons before assigning managed-flow causality.

For extreme-rain events, Rock Run Reservoir / Coatesville diversion context is most relevant as a caveat for low-flow, recession, or dry-window behavior. It should not be used alone to explain flood-peak attenuation unless the event hydrograph shows delayed attenuation, release-like plateaus, or step changes that are not explainable by rainfall and routing.
