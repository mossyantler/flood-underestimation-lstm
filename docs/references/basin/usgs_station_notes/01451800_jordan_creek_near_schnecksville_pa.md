# 01451800 Jordan Creek near Schnecksville, PA

## Source Check

- USGS monitoring location page: <https://waterdata.usgs.gov/monitoring-location/USGS-01451800/>
- USGS NWIS inventory/API page: <https://waterservices.usgs.gov/nwis/site/?format=rdb&sites=01451800&siteOutput=expanded&siteStatus=all>
- USGS annual water-data report PDF checked: <https://pubs.usgs.gov/wdr/wdr-pa-03-1/pdfs/01451800.pdf>
- Retrieved: 2026-05-06 Asia/Seoul

## Station Context

USGS lists the station as `01451800 Jordan Creek near Schnecksville, PA`, a stream site in Lehigh County, Pennsylvania. The current USGS monitoring-location metadata gives a drainage area of `53.0 mi2`, coordinates near `40.661762, -75.626854`, and gage altitude/datum `380.48 ft NAVD88`.

The accessible station observation text notes that prior to `2015-06-16` the gage included a concrete control, and prior to `1973-10-02` it was a non-recording gage at a bridge `54 ft` upstream at the same datum. The 2003 annual water-data report places the gage on the left bank downstream from the wooden covered bridge at Trexler-Lehigh County Game Preserve, about `1.0 mi` downstream from Mill Creek and `1.1 mi` southwest of Schnecksville. It lists the period of record as February 1966 to current year for that report.

No explicit regulation, reservoir, diversion, canal, or managed-release remark was found in the USGS station page text or the checked annual water-data report PDF. The 2003 PDF says discharge records were good except estimated daily discharges, which were poor. That is a general daily-record caveat and is not direct evidence for a specific hourly event in the CAMELSH diagnostic.

## Use In 01451800 Diagnosis

For the `primary` extreme-rain basin dissection, the station note does not make reservoir/dam regulation a primary explanation. Local metadata points the same way: StreamStats cache has `isRegulated = false`, GAGES-II dam proxies have `NDAMS_2009 = 0`, `MAJ_NDAMS_2009 = 0`, and `STOR_NOR_2009 = 0`.

The safer interpretation is that event-level mismatches at this basin should first be read as rainfall footprint, antecedent wetness, infiltration/storage, routing, and model response-design effects. Water use is present in the local proxy (`FRESHW_WITHDRAWAL = 75.06 ML/yr/km2`), but no canal, major NPDES, dam-storage, or station-source evidence reviewed here supports using water management as the primary cause of flood-peak attenuation.
