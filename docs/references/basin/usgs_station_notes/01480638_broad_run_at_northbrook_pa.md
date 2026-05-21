# USGS station note: 01480638 Broad Run at Northbrook, PA

Accessed: 2026-05-06 Asia/Seoul.

Sources checked:

- USGS monitoring location page: https://waterdata.usgs.gov/monitoring-location/01480638/
- USGS NWIS site service, expanded site file: https://waterservices.usgs.gov/nwis/site/?format=rdb&sites=01480638&siteOutput=expanded
- USGS legacy current-conditions page with station text: https://waterdata.usgs.gov/nwis/uv?legacy=1&site_no=01480638
- USGS Water-Year Summary Reports page: https://waterdata.usgs.gov/nwis/wys_rpt/?site_no=01480638
- USGS Water-Data Report PDF, water year 2003: https://pubs.usgs.gov/wdr/wdr-pa-03-1/pdfs/01480638.pdf
- USGS Scientific Investigations Report 2005-5156, Broad Run watershed study: https://pubs.usgs.gov/sir/2005/5156/Broad-Run.pdf

Station/source summary:

- Station name: `01480638 Broad Run at Northbrook, PA`.
- Location: Chester County, Pennsylvania, Hydrologic Unit `02040205`/Brandywine-Christina. The 2003 Water-Data Report places the gage on the right bank `50 ft` upstream from Northbrook Road and `2.2 mi` south of Marshalton.
- Drainage area: USGS lists `6.39 mi2`, close to the local CAMELSH/DRBC area of `16.5213 km2`.
- Period of record: the current USGS monitoring page says water data back to 1998 are available online. The 2003 Water-Data Report lists water-discharge records from December 2002 to current year.
- Gage/datum: water-stage recorder and crest-stage gage. The official site file and 2003 Water-Data Report list gage elevation `190.78 ft` above NAVD88.
- Cooperation: the current monitoring page lists operation in cooperation with the Chester County Water Resources Authority and USGS Cooperative Matching Funds.
- Regulation/diversion interpretation: the checked official station sources do not identify a reservoir or dam regulation remark for this station. Local StreamStats cache reports `isRegulated = false`, and local GAGES-II dam/canal/NPDES proxies have `NDAMS_2009 = 0`, `MAJ_NDAMS_2009 = 0`, `STOR_NOR_2009 = 0`, `CANALS_PCT = 0`, and `NPDES_MAJ_DENS = 0`. Freshwater-withdrawal context exists in the local GAGES-II proxy (`FRESHW_WITHDRAWAL = 192.43 ML/yr/km2`), but no reviewed source tied that value to event-scale flood operations at the gage.
- Rating/quality caveat: the 2003 Water-Data Report rates discharge records as fair except estimated daily discharges and records above `100 ft3/s`, which are poor. The current monitoring page also records a revision note: gage height and discharge for `2021-09-15` to `2021-10-06` were revised on `2022-08-26` based on gage-height equipment error. This revision window does not include the `2021-09-01/02` Ida event used in the local stress catalog, but it is close enough to keep as a station-quality caveat.
- Watershed/geomorphic context: USGS SIR 2005-5156 describes the Broad Run watershed as `7.08 mi2`, with `6.39 mi2` draining to station `01480638`. For April 2003 to March 2004, the study estimated `67.8 in` precipitation, `38.8 in` streamflow, `31.5 in` base flow, and `7.30 in` direct runoff. The report classifies the watershed as generally functioning like a non-urban mixed-use watershed, with base flow representing about `81%` of total streamflow during that study year.
- Floodplain/channel context: the same SIR says the main branch of Broad Run generally has an available, functioning flood plain and is not entrenched at a large scale, while localized channelization, road/driveway crossings, and increased runoff affect smaller reaches. The lower geomorphic study reach is near the gage and lies where the steeper valley of Broad Run meets the broad, flat flood plain of the West Branch Brandywine Creek.

Use in basin diagnosis:

Treat this station as a small, low-hydromodification Broad Run outlet with meaningful high-flow rating and local floodplain/conveyance caveats, not as a high-confidence regulated reservoir outlet. Event-scale hydrograph diagnosis should therefore avoid reservoir/dam claims unless the hydrograph itself shows independent managed-release evidence. Repeated model peaks above observed flow are better interpreted as model over-response or upper-tail false positives on a small flashy basin, with station high-flow rating uncertainty and floodplain/channel conveyance as secondary caveats.
