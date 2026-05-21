# 01477000 - Chester Creek near Chester, PA

## Source Check

Checked for the Wave 4 basin hydrograph diagnosis on 2026-05-06.

Primary USGS monitoring-location page:

- URL: https://waterdata.usgs.gov/monitoring-location/USGS-01477000/
- Station name: Chester Creek near Chester, PA.
- Site type: stream.
- Location: Delaware County, Pennsylvania; decimal coordinates approximately `39.8690009, -75.4082494`.
- Drainage area: `61.1 mi2`.
- Gage/altitude datum on the current page: altitude `23.41 ft`, vertical datum `NGVD29`.
- Cooperators shown on the monitoring page include Pennsylvania Department of Environmental Protection, USGS Cooperative Matching Funds, and USGS Federal Priority Streamgages.

USGS NWIS site-service check:

- URL: https://waterservices.usgs.gov/nwis/site/?format=rdb&sites=01477000&siteOutput=expanded
- Confirms station number `01477000`, station name, stream site type, drainage area `61.1 mi2`, HUC `02040202`, and time zone `EST`.

Water-data report PDFs checked:

- WY 1999 PDF: https://pubs.usgs.gov/wdr/1999/dela-99/wdr_del-1999/pdfs/01477000.pdf
- WY 2003 PDF: https://pubs.usgs.gov/wdr/wdr-pa-03-1/pdfs/01477000.pdf
- A guessed WY 2013 site-data-sheet URL, `https://wdr.water.usgs.gov/wy2013/pdfs/01477000.2013.pdf`, returned `404`.

## Key Station Facts

The checked WDR PDFs identify the site as being on the right bank `30 ft` downstream from the Dutton Mill Road bridge and `3.0 mi` northwest of Chester. They list drainage area `61.1 mi2` and period of record beginning in August 1931, with monthly discharges only for some periods.

The WDR gage note says this is a water-stage recorder. It also records historical site/gage changes: prior to June 27, 1966, the water-stage recorder was `50 ft` upstream, and from June 28, 1966 to October 4, 1967, a nonrecording gage was used `30 ft` upstream and at the gage, at the same datum.

The important human-flow note is a diversion, not a named reservoir regulation statement at the gage. The 1999 WDR says there was a diversion about `2.6 mi` upstream into the Ridley Creek basin by Philadelphia Suburban Water Company, equivalent to a mean daily discharge of `3.2 ft3/s` for that year. The 2003 WDR gives the same upstream diversion description, with Aqua Pennsylvania Water Company as the named operator, equivalent to `2.5 ft3/s` for that year.

The checked WDR remarks describe records as good in WY 1999 except estimated daily discharges, which are poor, and fair in WY 2003 except estimated daily discharges, which are poor. The 1999 report lists the WY 1999 maximum instantaneous peak flow as `13,400 ft3/s` on September 16, 1999, and notes the historical maximum peak flow as `21,000 ft3/s` on September 13, 1971. The rating above `2,400 ft3/s` was extended using indirect measurements.

## Local Metadata Cross-Check

The local StreamStats cache at `output/basin/all/cache/usgs_streamstats/01477000.json` reports `isRegulated = false`. Local GAGES-II hydromodification attributes still show basin-scale human-flow context: `NDAMS_2009 = 4`, `MAJ_NDAMS_2009 = 0`, `STOR_NOR_2009 = 4.95 ML/km2`, `CANALS_PCT = 0`, `FRESHW_WITHDRAWAL = 1584.12 ML/yr/km2`, and `NPDES_MAJ_DENS = 1.91`.

Interpretation constraint for basin-dissect reports: treat the upstream diversion and high water-use proxy as relevant human-flow context, but do not diagnose event-scale reservoir regulation or managed release unless the hydrograph evidence independently supports it. The checked official sources do not provide a direct named-reservoir regulation remark for this station.
