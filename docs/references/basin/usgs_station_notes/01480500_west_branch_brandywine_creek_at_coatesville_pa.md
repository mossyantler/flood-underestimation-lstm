# USGS station note: 01480500 West Branch Brandywine Creek at Coatesville, PA

Accessed: 2026-05-06 Asia/Seoul.

Sources checked:

- USGS monitoring location page: https://waterdata.usgs.gov/monitoring-location/USGS-01480500/
- USGS legacy current-conditions page: https://waterdata.usgs.gov/nwis/uv?legacy=1&site_no=01480500
- USGS Water-Data Report 2001 PDF: https://pubs.usgs.gov/wdr/2001/del-01-1/pdfs/01480500.pdf
- USGS Water-Data Report 1999 PDF: https://pubs.usgs.gov/wdr/1999/dela-99/wdr_del-1999/pdfs/01480500.pdf

Station/source summary:

- Station name: `01480500 West Branch Brandywine Creek at Coatesville, PA`.
- Location: Chester County, Pennsylvania, Hydrologic Unit `02040205`. The USGS station text places the gage on the right bank at the city limits of Coatesville, `1,200 ft` upstream from the bridge on old Lincoln Highway and `0.6 mi` downstream from Rock Run.
- Drainage area: USGS lists `45.8 mi2`, close to the local CAMELSH/DRBC area of `119.38 km2`.
- Period of record: water-discharge records run from October 1943 to December 1951 and from January 1970 to current year.
- Gage/datum: water-stage recorder, crest-stage gage, water-quality monitor, and V-notch sharp-crested weir. The current station text lists gage elevation `306.05 ft` above NGVD29 from survey. From September 10, 1943 to December 31, 1951, a nonrecording gage was located `1,100 ft` downstream at a different datum.
- Regulation/diversion remarks: the checked historic Water-Data Reports state that there is diversion from Rock Run Reservoir, station `01480465`, `2.6 mi` upstream. The reservoir capacity is listed as `982 acre-ft`, and the diversion is for municipal supply of the city of Coatesville. The 1999 and 2001 reports also note that diversion values include change in contents from Rock Run Reservoir.
- Rating/quality caveat: the 1999 report describes records as good except estimated daily discharges, which are fair; the 2001 report describes records as good except estimated daily discharges, which are poor. The current monitoring page labels recent instantaneous data provisional. The historic reports note the June 29, 1973 peak-flow rating extension above `7,800 ft3/s` on the basis of a slope-area measurement.
- Cooperation: the current page lists funding from Chester County Water Resources Authority and USGS Cooperative Matching Funds. The historic reports state that records of diversion were provided by the city of Coatesville.

Use in basin diagnosis:

Treat this station as a West Branch Brandywine Creek gage with explicit upstream municipal-supply diversion and Rock Run Reservoir context. The checked sources do not identify a flood-control reservoir operation at the station, and the local StreamStats cache reports `isRegulated = false`, so event-scale flood attenuation or release claims need hydrograph and nearby-gauge support.

For extreme-rain hydrograph diagnosis, Rock Run Reservoir and municipal supply are important caveats for low-flow or dry-window behavior and for possible managed-flow artifacts. They should not be used alone to explain flood-scale peak suppression, especially when the observed hydrograph shows fast rainfall-linked peaks and the upstream/downstream Brandywine sequence responds coherently.
