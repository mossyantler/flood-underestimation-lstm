# 01483700 - St. Jones River at Dover, DE

## Checked sources

- USGS current-conditions / monitoring-location page: https://waterdata.usgs.gov/nwis/uv?legacy=1&site_no=01483700
- USGS Water-Year Summary page: https://waterdata.usgs.gov/nwis/wys_rpt/?site_no=01483700
- USGS Scientific Investigations Report 2022-5005, peak-flow and low-flow magnitude estimates for nontidal streams in Delaware: https://pubs.usgs.gov/publication/sir20225005/full
- USGS annual Water Data Report PDF: not found as a station-specific PDF during this check. The Water-Year Summary page states that 2006-2013 reports are available as Annual Water Data Reports and 2014 onward as on-demand Water-Year Summary reports.

## Station facts

USGS identifies this station as `01483700 ST. JONES RIVER AT DOVER, DE`. The Water-Year Summary gives latitude `39°09'49.4"` and longitude `75°31'08.7"` referenced to NAD83 in Kent County, Delaware, Hydrologic Unit `02040207`. The station is on the left bank `150 ft` upstream from Division Street Bridge in Dover, `1,950 ft` downstream from Silver Lake, and `12.5 mi` upstream from the mouth.

The official drainage area is `31.9 mi2`, close to the local CAMELSH/DRBC area of about `80.96 km2`. Surface-water records begin in January 1958 and continue to the current year. The gage is described as a water-stage recorder, concrete control, and crest-stage gage. The Water-Year Summary lists the gage datum as about `-0.77 ft` NAVD88, with a prior-to-June-1973 datum `0.50 ft` higher.

## Regulation, tide, and data-quality context

The key station-context fact is that the current USGS page says flow is affected by Silver Lake and frequently affected by tide and wind. It also notes that storm tides increase stream water levels at the gage, and that higher stage readings may produce discharge estimates that are higher than actual. This is a direct caveat for event-scale hydrograph diagnosis at this station.

The Water-Year Summary similarly says flow is affected by Silver Lake and frequently affected by tide and wind. It lists recent discharge records as good or fair depending on water year, with estimated discharges considered poor.

The local StreamStats cache marks `isRegulated = false`, while local GAGES-II hydromod attributes show one non-major dam (`NDAMS_2009 = 1`, `MAJ_NDAMS_2009 = 0`) and nonzero normal storage (`STOR_NOR_2009 = 21.81 ML/km2`). I therefore treat this as a Silver Lake / low-gradient coastal backwater and storage caveat rather than a strong major-reservoir regulation case.

## Regional reference context

USGS SIR 2022-5005 includes `01483700 St Jones River at Dover, DE` in Delaware Coastal Plain analyses, with drainage area `30.7 mi2` in its summary tables and a Coastal Plain fraction of `1.00`. The same report's low-flow table lists the site as not used in the low-flow regression set, while its peak-flow table includes the station among Delaware nontidal peak-flow stations. This supports using the station as a Coastal Plain gage, but does not remove the station-specific Silver Lake and tide/wind caveat for hourly event interpretation.
