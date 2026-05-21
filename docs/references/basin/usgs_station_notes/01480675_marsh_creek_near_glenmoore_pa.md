# USGS station note: 01480675 Marsh Creek near Glenmoore, PA

Accessed: 2026-05-06 Asia/Seoul.

Sources checked:

- USGS monitoring location page: https://waterdata.usgs.gov/monitoring-location/01480675/
- USGS monitoring-location API JSON: https://api.waterdata.usgs.gov/ogcapi/v0/collections/monitoring-locations/items/USGS-01480675?f=json
- USGS NWIS site service, expanded site file: https://waterservices.usgs.gov/nwis/site/?format=rdb&sites=01480675&siteOutput=expanded
- USGS legacy current-conditions page with station text, checked through the Water Data interface: https://waterdata.usgs.gov/nwis/dv/?referred_module=sw&site_no=01480675
- USGS Water-Year Summary Reports page: https://waterdata.usgs.gov/nwis/wys_rpt/?site_no=01480675
- USGS Water-Data Report PDF, water year 2003: https://pubs.usgs.gov/wdr/wdr-pa-03-1/pdfs/01480675.pdf

Station/source summary:

- Station name: `01480675 Marsh Creek near Glenmoore, PA`.
- Location: Chester County, Pennsylvania, Hydrologic Unit `02040205`. The 2003 Water-Data Report places the gage on the left bank `200 ft` north of the Pennsylvania Turnpike, `1.2 mi` downstream from Lyons Run, `1.8 mi` upstream from Black Horse Creek, and `3.0 mi` northeast of Glenmoore.
- Drainage area: USGS lists `8.57 mi2`, close to the local CAMELSH/DRBC area of `22.1463 km2`.
- Period of record: July 1966 to current year in the 2003 Water-Data Report; the NWIS site service lists the inventory date as `196607`.
- Gage/datum: the Water-Data Report describes a water-stage recorder, crest-stage gage, and concrete control. The current monitoring-location API lists altitude `445.4 ft` above NAVD88 from a GNSS survey. The current revision note says that, before February 19, 2025, the gage datum had been erroneously reported as `450 ft` above NGVD29.
- Cooperation: the current monitoring page lists operation in cooperation with the Pennsylvania Department of Environmental Protection, Bureau of Safe Drinking Water, and USGS Cooperative Matching Funds.
- Regulation/diversion interpretation: no checked official station text or Water-Data Report remark identified reservoir regulation or diversion at this gage. The local StreamStats cache reports `isRegulated = false`. Local GAGES-II hydromodification attributes show `NDAMS_2009 = 0`, `MAJ_NDAMS_2009 = 0`, `STOR_NOR_2009 = 0`, `STOR_NID_2009 = 0`, no mapped canals, and no major NPDES density. Freshwater withdrawal is nonzero (`192.4294 ML/yr/km2`), but that proxy alone should not be treated as flood-control regulation.
- Rating/quality caveat: the 2003 Water-Data Report says records were good except estimated daily discharges, which were poor. The period-of-record maximum peak flow listed in that report was `946 ft3/s` on June 22, 1972, with the rating curve extended above `903 ft3/s`. The live Water-Year Summary application was reachable, but static retrieval did not expose a clean station-specific manuscript without interacting with the application.

Use in basin diagnosis:

Treat this as a small Marsh Creek headwater station with no high-confidence official regulation remark at the gage. Event-scale hydrograph diagnosis should not assign reservoir/dam regulation as the primary cause unless the event evidence independently supports it. For the current extreme-rain diagnosis, the stronger source-supported context is small basin scale, low ordinary flow, no mapped dam storage in the local hydromodification attributes, and a datum/reporting caveat that does not explain flood-volume suppression.

Downstream Marsh Creek and Brandywine stations may have separate reservoir or managed-flow context, but that context should not be transferred upstream to `01480675` without direct source evidence.
