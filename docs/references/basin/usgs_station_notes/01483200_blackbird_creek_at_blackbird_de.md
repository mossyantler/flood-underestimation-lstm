# USGS station note: 01483200 Blackbird Creek at Blackbird, DE

Accessed: 2026-05-06 Asia/Seoul.

Sources checked:

- USGS monitoring location page: https://waterdata.usgs.gov/monitoring-location/01483200/
- USGS legacy current-conditions page with station text: https://waterdata.usgs.gov/nwis/uv?legacy=1&site_no=01483200
- USGS NWIS site inventory page: https://waterdata.usgs.gov/nwis/inventory/?agency_cd=USGS&site_no=01483200
- USGS NWIS site service, expanded site file: https://waterservices.usgs.gov/nwis/site/?format=rdb&sites=01483200&siteOutput=expanded&siteStatus=all
- USGS Water-Year Summary Reports page: https://waterdata.usgs.gov/nwis/wys_rpt/?site_no=01483200
- USGS Water-Data Report PDF, water year 1999: https://pubs.usgs.gov/wdr/wdr-md-de-dc-99-1/pdf/WDR-1999v1.pdf

Station/source summary:

- Station name: `01483200 Blackbird Creek at Blackbird, DE`.
- Location: New Castle County, Delaware, Hydrologic Unit `02040205`. The current USGS station text places the gage on the left bank `15 ft` downstream from highway culverts, `0.5 mi` upstream from Barlow Branch, `0.6 mi` southwest of Blackbird, `5.6 mi` northwest of Smyrna, and `13.8 mi` upstream from the mouth.
- Drainage area: the current USGS site inventory and site service list `4.06 mi2`, close to the local CAMELSH/DRBC area of `10.7901 km2`.
- Period of record: annual maximums for water years 1952-56, occasional low-flow measurements for water years 1952-53 and 1955-56, and continuous daily discharge from October 1956 to current year. The NWIS inventory page lists daily discharge from `1956-10-01` through `2025-11-16`, peak streamflow through `2024-03-23`, and water-year summaries from `2006` through `2024`.
- Gage/datum: water-stage recorder with concrete control since May 23, 1968. The current USGS text gives gage datum `17.10 ft` above NAVD88 and `17.89 ft` above NGVD29. Earlier gage configurations were at nearby/right-bank sites and a datum `1.0 ft` higher before June 17, 1986.
- Regulation/diversion interpretation: the current USGS station text and the 1999 Water-Data Report both state that there is occasional regulation at low and medium flow by Blackbird Lake Dam upstream from the station. This is a direct station-context fact, but it is not the same as documented high-flow flood control for the stress events.
- Local hydromod context: the local StreamStats cache reports `isRegulated = false`; local GAGES-II dam proxies have `NDAMS_2009 = 0`, `MAJ_NDAMS_2009 = 0`, and `STOR_NOR_2009 = 0`; canal and major NPDES proxies are zero. The local freshwater-withdrawal proxy is high (`FRESHW_WITHDRAWAL = 498.825 ML/yr/km2`), but no reviewed source tied it to event-scale flood operations.
- Coastal plain/storage context: StreamStats characteristics mark the basin as entirely Coastal Plain and list storage-related values including `Percent Storage from NLCD2016 = 23.27%` and `Percent Storage from NHD = 4.54%`. Local static attributes also show very low basin slope (`SLOPE_PCT = 0.458`) and substantial woody wetland (`11.39%`).
- Rating/quality caveat: the 1999 Water-Data Report says records were good except estimated daily discharges from missing record, which were poor. The 1999 instantaneous peak flow of `789 ft3/s` was from a rating curve extended above `600 ft3/s`.

Use in basin diagnosis:

Treat this station as a small, low-gradient Delaware Coastal Plain basin with wetland/storage influence and a documented low/medium-flow regulation caveat from Blackbird Lake Dam. Do not diagnose high-flow reservoir suppression solely from model overprediction: official and local sources do not support a high-confidence regulated flood-control outlet, and event hydrographs must independently show delayed release or dry-window managed-flow behavior before making that stronger claim.
