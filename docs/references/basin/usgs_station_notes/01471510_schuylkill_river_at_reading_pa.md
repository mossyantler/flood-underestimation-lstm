# 01471510 Schuylkill River at Reading, PA

## Source Check

- USGS monitoring location page: <https://waterdata.usgs.gov/monitoring-location/USGS-01471510/>
- USGS legacy daily/current page with station-specific text: <https://waterdata.usgs.gov/pa/nwis/dv?site_no=01471510>
- USGS Water-Year Summary page checked: <https://waterdata.usgs.gov/pa/nwis/wys_rpt/?site_no=01471510>
- USGS annual water-data report PDF checked: <https://pubs.usgs.gov/wdr/wdr-pa-03-1/pdfs/01471510.pdf>
- USGS Water Data Report 2010 publication page checked for event-year context: <https://pubs.usgs.gov/publication/wdr2010>
- Retrieved: 2026-05-06 Asia/Seoul

## Station Context

USGS lists the station as `01471510 Schuylkill River at Reading, PA`. The drainage area is `880 mi2`, and the station is just downstream of Tulpehocken Creek near Reading. The site is operated in cooperation with the U.S. Army Corps of Engineers, Philadelphia District.

The key station-level remark is that flow at this gauge is regulated by Still Creek Reservoir, Blue Marsh Lake, and to some extent Lake Ontelaunee. This remark matters directly for event-level hydrograph interpretation because a precipitation-driven model can produce a quick natural response while the observed outlet flow can be attenuated, delayed, or otherwise shaped by upstream storage and release operations.

The current USGS page also notes a gage relocation to the Penn Street Bridge on 2023-04-25, with a low-flow gage-height control change. The 2025 Water-Year Summary gives the current location as the downstream side of the Penn Street Bridge, 1.25 mi downstream from Tulpehocken Creek, and lists earlier recorder locations: 2,800 ft downstream during 1977-1979, 1,300 ft downstream during 1979-2018, and 2,700 ft downstream during 2018-2023, all at the same datum. This is not a direct explanation for the older events analyzed below, but it should be recorded when interpreting long-period station data and the 2023 event.

The 2025 Water-Year Summary reports that records are fair except for estimated discharges and periods above 5,000 ft3/s, which are poor; water-quality records are fair to poor. The 2003 annual water-data report PDF repeats the regulation context and notes that estimated daily discharges are lower quality. These caveats are background only here because the model diagnostic uses local hourly time-series data and no reservoir operation record was reviewed.

## Use In 01471510 Basin Diagnosis

For `01471510` stress-event diagnosis, the USGS station note makes `reservoir/dam regulation` a required candidate, not an optional afterthought. Local metadata also points in the same direction: `isRegulated = true`, `NDAMS_2009 = 54`, `MAJ_NDAMS_2009 = 21`, and large normalized storage proxies.

Events such as `01471510_rain_drbc_historical_stress_0005`, `0006`, and `0007` should therefore be reported with regulated/storage-routing context. They are not as clean as small headwater cases because this is a much larger mainstem basin, storm footprint and tributary phasing matter, and nearby gauges show that flood response was still present in the broader Schuylkill system. The station note supports regulation as a major context, but it does not by itself prove a specific release or gate operation during any individual event.
