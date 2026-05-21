# USGS station note: 01480015 Red Clay Creek near Stanton, DE

Accessed: 2026-05-06 Asia/Seoul.

Sources checked:

- USGS monitoring location page: https://waterdata.usgs.gov/monitoring-location/USGS-01480015/
- USGS legacy current-conditions page with station text: https://waterdata.usgs.gov/nwis/uv?legacy=1&site_no=01480015
- USGS site inventory page: https://waterdata.usgs.gov/nwis/inventory/?site_no=01480015
- USGS Water-Year Summary Reports page: https://waterdata.usgs.gov/nwis/wys_rpt/?site_no=01480015
- USGS Water-Data Report MD-DE-DC 2000, volume 1 PDF: https://pubs.usgs.gov/wdr/wdr-md-de-dc-00-1/WDR-MD-DE-DC-2000v1.pdf

Station/source summary:

- Station name: `01480015 Red Clay Creek near Stanton, DE`.
- Location: New Castle County, Delaware, Hydrologic Unit `02040205`. The USGS station text places the gage on the right bank at the downstream side of the westbound lane of the State Highway 4 bridge, near Stanton, `0.9 mi` upstream from the mouth.
- Drainage area: USGS lists `52.4 mi2`, close to the local CAMELSH/DRBC area of `135.88 km2`.
- Period of record: surface-water records begin in October 1988 and continue to current year. The site inventory lists daily discharge from `1988-10-01`, current/historical observations from `1989-06-09`, and peak streamflow records beginning in 1989.
- Gage/datum: water-stage recorder and crest-stage gage. Current USGS text lists datum `-1.15 ft` above NAVD88 and `0.00 ft` above NGVD29.
- Regulation/diversion remarks: USGS remarks say records were adjusted for inflow from June 1994 to September 2011. Low flows are augmented at times by inflow from Hoopes Reservoir, located `5.7 mi` upstream from the gage on an unnamed tributary to Red Clay Creek, with capacity `2,000,000,000 gal`. Water from Brandywine Creek is pumped into Hoopes Reservoir and released into Red Clay Creek during low-flow periods. Water from Red Clay Creek is used for municipal supply.
- Rating/quality caveat: the Water-Year Summary page says water years 2021-2024 are fair except estimated discharges, which are poor. For water years 2017-2020 and 2014-2016, records are good below `2,000 ft3/s` and fair above, except estimated discharges, which are poor. Earlier Water-Data Reports should be used for water year 2013 and prior accuracy statements.
- The checked 2000 Water-Data Report repeats the Hoopes Reservoir and municipal-supply remarks, states that no Hoopes releases were observed during water year 2000, and describes some high-flow and gage-height values as estimated or affected by backwater. It also notes annual-mean/runoff values adjusted for Hoopes inflow since June 1994.

Use in basin diagnosis:

Treat this as the lower Red Clay Creek gage with explicit low-flow augmentation, municipal-supply use, and an inflow-adjustment history through September 2011. This is strong station-level context for low-flow bias, dry-window plateaus, or release-like behavior, but the checked USGS sources do not identify a flood-control reservoir operation that should automatically explain flood-peak attenuation.

For extreme-rain hydrograph diagnosis, use Hoopes Reservoir and municipal-supply operations as secondary context unless the event hydrograph itself shows a dry-window pulse, plateau, step change, or attenuation pattern that is not shared by upstream Red Clay Creek gages. Local metadata are mixed: GAGES-II hydromodification attributes show `NDAMS_2009 = 3`, `MAJ_NDAMS_2009 = 1`, high freshwater withdrawal, and a major NPDES density proxy, while the local StreamStats cache reports `isRegulated = false`.
