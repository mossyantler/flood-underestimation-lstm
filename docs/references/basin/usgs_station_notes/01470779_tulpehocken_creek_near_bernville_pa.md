# 01470779 Tulpehocken Creek near Bernville, PA

## Source Check

- USGS monitoring location page: <https://waterdata.usgs.gov/monitoring-location/USGS-01470779/>
- USGS NWIS site service/API page: <https://waterservices.usgs.gov/nwis/site/?format=rdb&sites=01470779&siteOutput=expanded&siteStatus=all>
- USGS annual water-data report PDF checked: <https://pubs.usgs.gov/wdr/wdr-pa-03-1/pdfs/01470779.pdf>
- Retrieved: 2026-05-06 Asia/Seoul

## Station Context

USGS lists this site as `01470779 Tulpehocken Creek near Bernville, PA`, a stream site in Berks County, Pennsylvania. The current monitoring-location metadata gives drainage area `70.4 mi2`, contributing drainage area `70.4 mi2`, coordinates near `40.413344, -76.171585`, hydrologic unit `020402030403`, and gage altitude `310.5 ft NAVD88`.

The checked water-year 2003 annual report gives older station-text context: location on the left bank about `30 ft` downstream from Mill Road bridge at Kricks Mill, `0.4 mi` upstream from Mill Creek, and `3.5 mi` west of Bernville. That report lists drainage area `66.5 mi2`, period of record beginning November 1974, a water-stage recorder and crest-stage gage, and a gage datum of `311.26 ft NGVD29`. The report says discharge records were fair except estimated daily discharges, which were poor, and notes that the January 24, 1979 maximum peak flow was from a rating curve extended above `740 ft3/s`.

No explicit USGS station remark was found for reservoir regulation, diversion, canal control, or managed release at this gauge. The current monitoring-location page does include station observation text saying that local pumping effects can be seen during summer low flow. That is relevant background for low-flow and dry-window interpretation, but it is not direct evidence for event-scale flood-peak regulation.

## Use In 01470779 Diagnosis

For the `primary` extreme-rain basin dissection, do not treat `01470779` as a directly dam-regulated outlet. Local metadata agrees on that narrow point: StreamStats cache has `isRegulated = false`, and GAGES-II dam attributes have `NDAMS_2009 = 0`, `MAJ_NDAMS_2009 = 0`, and `STOR_NOR_2009 = 0`.

Human-use context is still present. Local attributes show nonzero canal, NPDES, freshwater-withdrawal, and power-generation proxies, and USGS notes pumping effects during summer low flow. Those sources support a secondary managed-flow caveat for low-flow/recession and possible small dry-window extra-flow signals, while storm-peak diagnosis should first consider storm footprint, antecedent wetness, basin routing/storage, and model response behavior.
