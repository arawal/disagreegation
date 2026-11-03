# Georgia Seismic Design Data

Builds an AASHTO 9th Edition seismic design table for Georgia, using two public
USGS web services: the AASHTO Design Maps service (design values) and the
National Seismic Hazard Model disaggregation service (the characteristic
earthquake). About 213,000 points, one per 30 arc-second grid cell.

**Non-technical readers:** see
[`docs/Data_Sources_and_How_To_Redo_This.pdf`](docs/Data_Sources_and_How_To_Redo_This.pdf)
for a plain-English explanation of where the numbers come from and how to
redo this.

**This file** is the short technical how-to: what to run, and which settings
to change.

## Requirements

- Python 3.9 or newer. No other packages are required — the scripts use only
  Python's standard library.

## The input file

A CSV with, at minimum, longitude and latitude in the first two columns, and
a header taking up the first 2 rows (`--skip-header-rows`, default 2). The
project's own input file is `GA Seismic Data with County - AASHTO 9th 1
(vs30_mosaic_GA_table (9thdata)).csv` (not included in this repo — ask
whoever ran this originally, or substitute your own coordinate list in the
same shape).

## Running it

There are three scripts, run in order. Each one is resumable: if you stop it
(or it crashes, or your computer sleeps) and run the exact same command
again, it picks up from where it left off instead of starting over.

### 1. Disaggregation (the characteristic earthquake)

```bash
python3 disagg_adaptive.py your_table.csv --out disagg_out_D --vs30 260 --spot-check 300
```

Runs once per soil class you need. Key settings:

| Flag | What it controls | Default |
|---|---|---|
| `--vs30` | soil stiffness in m/s — see the table below | 760 |
| `--return-period` | hazard level in years | 1033 (AASHTO's "7% in 75 years") |
| `--imt` | ground motion measure | `PGA` |
| `--spot-check N` | re-fetch N random interpolated points at the end, to report accuracy | 0 (off) |
| `--concurrency` | parallel requests | 4 |
| `--min-interval` | seconds between request starts | 0.6 |

Site class → `--vs30` to use:

| Site Class | A | B | C | D | E |
|---|---|---|---|---|---|
| `--vs30` | 1500 | 1080 | 530 | 260 | 150 |

This step is the slow one: expect several hours to about a day per class,
and watch the console for progress. Raise `--concurrency` /lower
`--min-interval` only if you see `rate_limited=0` for a long stretch — this
service pushes back hard if you go too fast (see `docs/` PDF, Section 5).

### 2. AASHTO design values

```bash
python3 aashto_batch.py your_table.csv --out aashto_out_D --site-classes D
```

| Flag | What it controls | Default |
|---|---|---|
| `--site-classes` | comma list, e.g. `C,D`, or a single class | `A,B,C,D,E` |
| `--own-class-column N` | instead of the list above, use each row's own site class (column N, 0-based) | off |
| `--concurrency` | parallel requests | 6 |
| `--min-interval` | seconds between request starts | 0.1 |

This step is much faster than disaggregation — typically a few hours even
for all five classes across the whole table.

### 3. Merge into one spreadsheet

```bash
python3 fill_table.py your_table.csv \
  --force-class D --trim-to-force-class \
  --aashto aashto_out_D/aashto_values.csv \
  --disagg disagg_out_D/disagg_grid.csv
```

| Flag | What it controls |
|---|---|
| `--force-class X` | fill every row's block as if it were site class X, ignoring that row's own class |
| `--own-class-only` | instead, fill only each row's own site class's block |
| `--trim-to-force-class` | with `--force-class`, drop the other four (always-empty) class blocks instead of leaving them blank — much smaller file |
| (no flag) | fill all five class blocks for every row, from a single `--aashto`/`--disagg` source |

Writes two files per run into `--out` (default `output/`): a `_filled.csv`
matching the input layout, and an `_extended.csv` with Zone, PGA, Ss, S1 and
Sds added to each class block.

## Keeping it running unattended

`watchdog3.sh` and the `run_*.sh` scripts show the pattern used to run these
for days at a time: start a script with `nohup ... &`, and have a small loop
check every minute whether it's still running and restart it from cache if
not. Adapt the paths inside them for a new run, or just re-invoke the three
commands above by hand.

## Tests

```bash
python3 -m unittest test_disagg_adaptive
```

Checks the disaggregation script's grid-refinement logic offline, with no
network calls.
