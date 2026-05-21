# USGS 01469500 Little Schuylkill River at Tamaqua, PA

Source check date: 2026-05-06 KST.

Sources reviewed:

- USGS current legacy monitoring page: https://waterdata.usgs.gov/nwis/uv?agency_cd=USGS&legacy=1&site_no=01469500
- USGS Water Data for the Nation monitoring page: https://waterdata.usgs.gov/monitoring-location/USGS-01469500/
- USGS annual water-data report PDF, water year 2003 station sheet: https://pubs.usgs.gov/wdr/wdr-pa-03-1/pdfs/01469500.pdf
- USGS NWIS site service RDB: https://waterservices.usgs.gov/nwis/site/?format=rdb&sites=01469500&siteOutput=expanded

Station identity and basin:

- Station name: Little Schuylkill River at Tamaqua, PA.
- Drainage area: 42.9 square miles, equivalent to about 111.1 square kilometers. The local CAMELSH/GAGES-II attribute table uses 114.3441 square kilometers.
- Location: Schuylkill County, Pennsylvania, Hydrologic Unit 02040203, left bank along State Route 309, 0.6 miles upstream from Tamaqua and 0.8 miles upstream from Panther Creek.
- Period of record: October 1919 to current year; June 1916 to September 1919 had gage heights and discharge measurements only.

Gage and datum notes:

- Current legacy station text lists a water-stage recorder, crest-stage gage, weighing bucket precipitation gage, and concrete control.
- Current datum is 816.82 ft above NAVD88. Before 2024-02-14, the datum was reported as 817.48 ft above NGVD29.
- Before 1929-06-21, a non-recording gage was used 3,600 ft downstream at a datum 28.64 ft lower.

Regulation, diversion, and data-quality notes:

- Current USGS station text states that flow is regulated by Still Creek Reservoir, station 01469200, 6.5 miles upstream.
- The 2003 annual water-data report also states the same reservoir regulation and says estimated daily discharges are poor. It also notes that diversion and change-in-contents records for Still Creek Reservoir were provided by the Borough of Tamaqua.
- The current station page states that 15-minute precipitation data are temporary and that no NWS flood stage has been determined for the station.
- Local StreamStats cache marks `isRegulated = false`, but this conflicts with the direct USGS station text and local GAGES-II dam attributes. For event diagnosis, treat the USGS station remark as the controlling source for regulation context.

Use in event-suppression diagnosis:

- Regulation by Still Creek Reservoir is documented and should remain an active explanation for peak attenuation, timing delay, or release-shaped recession patterns.
- However, the station is not automatically a reservoir false-positive case. Event-level hydrographs still need to separate long-duration basin-wide flood response from short-burst low-response negative controls.
