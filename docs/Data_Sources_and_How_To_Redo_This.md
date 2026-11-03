---
title: "Georgia Seismic Design Data: Where It Came From and How to Redo It"
subtitle: "A plain-English guide for anyone who needs to understand, check, or reproduce this dataset — no programming background required."
geometry: margin=1in
fontsize: 11pt
colorlinks: true
---

## 1. What this dataset is

This project fills in a table of earthquake design numbers for about 213,000
points spread evenly across the state of Georgia, roughly one point every
800 meters. The table follows the AASHTO (American Association of State
Highway and Transportation Officials) 9th Edition bridge design standard.
Each point needs two kinds of numbers:

- **Design values** — the official shaking numbers an engineer plugs into a
  bridge design (As, Sd1, PGA, Ss, S1, Sds, and a design category letter).
- **The "characteristic earthquake"** — in plain terms, the single most
  representative earthquake (how big, and how far away) behind the shaking
  risk at that point. The table calls these "Modal Mw" (size) and
  "Modal R" (distance).

## 2. Where the numbers come from

Both kinds of numbers come from free, public tools run by the **US
Geological Survey (USGS)**, the US government's earth-science agency. No
number here was guessed or estimated by AI. Every number traces back to one
of these two official USGS tools, running USGS's current national earthquake
hazard model (the "2018 update", the standard one at the time this was
built).

| Tool | What it gives you | Link |
|---|---|---|
| AASHTO Design Maps | Design values (As, Sd1, PGA, Ss, S1, Sds, design category) | [Open tool](https://earthquake.usgs.gov/ws/building-codes) |
| Hazard Disaggregation | The characteristic earthquake (Modal Mw and Modal R) | [Open tool](https://earthquake.usgs.gov/nshmp/hazard/disagg) |

## 3. The settings that were used

Every request to USGS used the same settings, so the whole table is
consistent:

- **Hazard level:** a 1,033-year return period — the standard AASHTO bridge
  level, sometimes described as "about a 7% chance in 75 years."
- **What is measured:** PGA, "peak ground acceleration" — roughly, how hard
  the ground shakes.
- **Soil stiffness ("Vs30"):** each AASHTO Site Class stands for a different
  soil stiffness. The table below is what USGS uses for each letter; this
  project ran the stiffer-soil values (530, 260 and 150) plus 760, which
  doubles as the stiff end of Class B.

| Site Class | A | B | C | D | E |
|---|---|---|---|---|---|
| Soil stiffness (Vs30, m/s) | 1500 | 1080 | 530 | 260 | 150 |
| Run in this project? | no (see Section 7) | partly (via 760) | yes | yes | yes |

## 4. How the numbers were actually collected

The ordinary USGS website only answers one location at a time. This project
needed answers for roughly 213,000 locations, times several soil classes.
That is far too slow to do by hand. Luckily, both USGS tools also work as an
"API": a plain web address that hands back the numbers directly, instead of
showing a page. A short program can send that same web address thousands of
times in a row, automatically.

A program in this folder sent one such request per location and saved each
answer. Here is what one request looks like. Paste it into a browser to see
the real answer for that one spot (Atlanta, Site Class D):

```
https://earthquake.usgs.gov/ws/building-codes/aashto-2009/calculate?latitude=33.75&longitude=-84.39&siteClass=D
```

And the matching request for the characteristic earthquake (same spot, soil
stiffness 260, 1,033-year level):

```
https://earthquake.usgs.gov/ws/nshmp/conus-2018.R1/dynamic/disagg/-84.39/33.75/260/1033?imt=PGA
```

## 5. A necessary shortcut, and its small tradeoff

The characteristic-earthquake tool is slow, several seconds per request, and
must be asked once per soil class. Asking it directly at all 213,000 points,
for every soil class, would have taken many days per class just waiting on
that one tool. So the program took a shortcut: it asked the tool directly at
a well-spread sample of points, then estimated the points in between from
their nearest already-answered neighbors. Think of reading a value between
two marked points on a graph. It only estimated where nearby points already
agreed closely. Anywhere they did not agree, it asked more points nearby
until they did.

To check this shortcut, the program re-asked USGS directly for 300 random
estimated points per soil class, then compared the two answers. Across all
four soil classes, 96% to 97% of those checks matched USGS's real answer
closely (earthquake size within 0.1, distance within 5 km). Almost all the
rest still named the right earthquake, just with the distance figure one
step off. A small handful showed a real difference, right at a boundary
where the governing earthquake switches from a nearby small one to a distant
large one. The design-value numbers (As, Sd1, PGA, Ss, S1, Sds) never use
this shortcut. The program asked for every one of the 213,000-plus points
directly.

## 6. What is in this folder

| File / folder | What it is |
|---|---|
| `output/` | The finished tables. See Section 8 for which file to use. |
| `aashto_batch.py` | Asks the AASHTO Design Maps tool for a list of points, one soil class at a time or several at once. |
| `disagg_adaptive.py` | Asks the Disaggregation tool for the characteristic earthquake, using the sampling shortcut from Section 5, for one soil class at a time. |
| `fill_table.py` | Combines the two tools' answers into one spreadsheet, in the original table's layout. |
| `usgs_client.py` | Shared plumbing: makes sure requests don't go to USGS faster than it allows, and automatically waits and retries if USGS is briefly unavailable. |
| `run_*.sh`, `watchdog*.sh` | Convenience scripts that run the above in the right order for hours or days at a time without someone watching, restarting automatically if anything stops partway. |
| `test_disagg_adaptive.py` | Automated checks confirming the shortcut in Section 5 behaves correctly. |

## 7. Step by step: how to redo this in the future

Anyone with this folder, the two Python programs below, and the Georgia
coordinate list (a spreadsheet of longitude, latitude, county, and existing
soil data — the same list this project started from) can redo any part of
this, or extend it to a soil class not yet run (Class A, soil stiffness
1500, or a full statewide Class B at 1080).

1. **Install Python 3** on the computer doing the work. No other setup is
   required; the scripts use only Python's built-in tools.
2. **Ask for the characteristic earthquake** for a soil class, for example
   Class A:
   ```
   python3 disagg_adaptive.py your_coordinate_list.csv --out disagg_out_A --vs30 1500 --spot-check 300
   ```
3. **Ask for the design values** for the same soil class, for every point:
   ```
   python3 aashto_batch.py your_coordinate_list.csv --out aashto_out_A --site-classes A
   ```
4. **Combine the two** into one finished spreadsheet:
   ```
   python3 fill_table.py your_coordinate_list.csv --force-class A --trim-to-force-class --aashto aashto_out_A/aashto_values.csv --disagg disagg_out_A/disagg_grid.csv
   ```

Expect each soil class to take somewhere between several hours and about a
day, because USGS limits how fast any one computer may ask it questions. The
scripts already wait and retry on their own when that happens — it is
normal to start a step and leave it running unattended, and it will pick
back up on its own if it is ever interrupted, re-using what it already
collected instead of starting over.

## 8. Which finished file to use

Inside `output/`, use the files named `..._forced_class_X_trimmed.csv`
(X = C, D, or E). These are the clean, self-consistent tables. Every point
in one of these files used that one soil class for both the design values
and the characteristic earthquake, with no mixing. Hand one of these to an
engineer.

The earlier files named `..._filled.csv` and `..._own_class.csv` use each
point's own real soil class for the design values, but one fixed soil
stiffness (760) for the characteristic earthquake everywhere. Treat those as
a quick first look, not a final answer, except where a point's real class is
already close to 760.

---

*Every number in this dataset can be independently re-checked at any time by
typing the website addresses above (with different coordinates) directly
into a web browser — no special access or account is needed; these are free
public USGS tools.*
