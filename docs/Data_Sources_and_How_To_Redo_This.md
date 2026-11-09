---
title: "USGS API Calls Used for the Georgia Seismic Design Table"
geometry: margin=1in
fontsize: 11pt
colorlinks: true
---

All numbers in this dataset come from two free USGS web services. One call
per point gets the design values; one call per point gets the
characteristic earthquake (Modal Mw, Modal R). Substitute `LAT` / `LON` for
the point's coordinates, `CLASS` for the site class letter (A–E), and `VS30`
for that class's Vs30 (table below). Both use the 2018 national hazard
model, PGA, and the 1,033-year (7%-in-75-year) return period, fixed in the
calls themselves.

**Design values** (As, Sd1, PGA, Ss, S1, Sds, design category):

```
https://earthquake.usgs.gov/ws/building-codes/aashto-2009/calculate?latitude=LAT&longitude=LON&siteClass=CLASS
```

**Characteristic earthquake** (Modal Mw, Modal R):

```
https://earthquake.usgs.gov/ws/nshmp/conus-2018.R1/dynamic/disagg/LON/LAT/VS30/1033?imt=PGA
```

| Site Class | `VS30` (m/s) |
|---|---|
| A | 1500 |
| B | 1080 |
| C | 530 |
| D | 260 |
| E | 150 |

Example, Atlanta (33.75, -84.39), Site Class D:

```
https://earthquake.usgs.gov/ws/building-codes/aashto-2009/calculate?latitude=33.75&longitude=-84.39&siteClass=D

https://earthquake.usgs.gov/ws/nshmp/conus-2018.R1/dynamic/disagg/-84.39/33.75/260/1033?imt=PGA
```
