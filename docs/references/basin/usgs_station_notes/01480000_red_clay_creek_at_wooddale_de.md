# USGS station note: 01480000 Red Clay Creek at Wooddale, DE

Accessed: 2026-05-06 Asia/Seoul.

Sources checked:

- USGS monitoring location page: https://waterdata.usgs.gov/monitoring-location/01480000/
- USGS Water-Year Summary Reports page, checked with water year 2024 discharge summary: https://waterdata.usgs.gov/nwis/wys_rpt/?site_no=01480000
- USGS Water-Data Report MD-DE-DC 1999, volume 1 PDF: https://pubs.usgs.gov/wdr/wdr-md-de-dc-99-1/pdf/WDR-1999v1.pdf

Station/source summary:

- Station name: `01480000 Red Clay Creek at Wooddale, DE`.
- Location: New Castle County, Delaware, Hydrologic Unit `02040205`. The USGS station text places the gage on the right bank `12 ft` upstream from the State Highway 48 bridge, `0.3 mi` south of Wooddale, `2.3 mi` north of Marshallton, and `4.9 mi` upstream from the mouth.
- Drainage area: USGS lists `47.0 mi2`, close to the local CAMELSH/DRBC area of `122.61 km2`.
- Period of record: surface-water records begin in April 1943 and continue to current year.
- Gage/datum: water-stage recorder, concrete control, and crest-stage gage. The current station page lists datum `80.31 ft` above NAVD88 and `81.46 ft` above NGVD29; the water-year summary lists `80.34 ft` above NAVD88. Before September 21, 1950, a nonrecording gage was located `10 ft` downstream at the same gage datum.
- Regulation/diversion remarks: USGS remarks say low flows are augmented at times by inflow from Hoopes Reservoir, located `1.7 mi` upstream from the gage on an unnamed tributary to Red Clay Creek. The reservoir capacity is listed as `2,000,000,000 gal`. Water from Brandywine Creek is pumped into Hoopes Reservoir and released into Red Clay Creek during low-flow periods. Water from Red Clay Creek is also used for municipal supply.
- Rating/quality caveat: the 2024 Water-Year Summary says recent records are generally good, but high discharges and estimated discharges are poorer. Specifically, water years 2020-2023 are good except flows above `1,700 ft3/s` and estimated discharges, which are poor; water years 2017-2019 use a `1,000 ft3/s` high-flow caveat. Earlier annual water-data reports contain the pre-2014 accuracy statements.
- The checked 1999 Water-Data Report repeats the Hoopes Reservoir and municipal-supply remarks. For water year 1999, it lists an annual maximum instantaneous discharge of `7,650 ft3/s` on September 16, 1999 and marks some September daily means as estimated.

Use in basin diagnosis:

Treat this station as a Red Clay Creek outlet with explicit low-flow augmentation and municipal water-supply context, but not as a station where the checked USGS sources identify flood-control reservoir regulation of high flows. Local metadata are mixed in the same direction: GAGES-II hydromodification attributes show dams and one major dam in the basin, while the local StreamStats cache reports `isRegulated = false`.

For extreme-rain hydrograph diagnosis, Hoopes Reservoir is important context for dry-window low-flow pulses, elevated baseflow, or release-like plateaus. It should not be used alone to explain flood-scale peak suppression unless the event hydrograph, dam/storage proxies, and nearby upstream/downstream comparisons also point to storage or release operation.
