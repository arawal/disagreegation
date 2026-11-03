#!/usr/bin/env python3
"""Merge the AASHTO and disaggregation results into the GA table layout.

Writes two files in --out:
  <name>_filled.csv    the input layout, with As, Sd1, Modal Mw and Modal R
                       filled in each site class block
  <name>_extended.csv  the same, plus Zone (SDC), PGA, Ss, S1 and Sds columns
                       in each site class block

Cells stay blank where no result exists yet, so this can be run while the
fetch scripts are still going.
"""

import argparse
import csv
import sys
from pathlib import Path

BLOCK_CLASSES = ["A", "B", "C", "D", "E"]
BLOCK_START = 6      # column index where the Site Class A block begins
BLOCK_WIDTH = 5      # Site Class, As, Sd1, Modal Mw, Modal R
EXTRA = [("Zone (SDC)", "sdc"), ("PGA", "pga"), ("Ss", "ss"), ("S1", "s1"), ("Sds", "sds")]


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("--aashto", default="aashto_out/aashto_values.csv")
    p.add_argument("--disagg", default="disagg_out/disagg_grid.csv")
    p.add_argument("--out", default="output")
    p.add_argument("--own-class-only", action="store_true",
                   help="fill only the block matching each row's Site Class column; leave the other blocks' values empty")
    p.add_argument("--force-class",
                   help="ignore each row's own Site Class; use this class's AASHTO/disagg results for every row's block of this class, leave other blocks empty")
    p.add_argument("--trim-to-force-class", action="store_true",
                   help="with --force-class, drop the other four (always-empty) class blocks' columns entirely instead of leaving them blank")
    args = p.parse_args()
    if args.trim_to_force_class and not args.force_class:
        p.error("--trim-to-force-class requires --force-class")
    return args


def load_aashto(path):
    vals = {}
    if not Path(path).exists():
        print(f"no AASHTO results at {path} yet", file=sys.stderr)
        return vals
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            vals[(row["lon"], row["lat"], row["site_class"])] = row
    return vals


def load_disagg(path):
    vals = {}
    if not Path(path).exists():
        print(f"no disaggregation grid at {path} yet", file=sys.stderr)
        return vals
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            vals[(row["lon"], row["lat"])] = (row["modal_mw"], row["modal_r_km"])
    return vals


def main():
    args = parse_args()
    aashto = load_aashto(args.aashto)
    disagg = load_disagg(args.disagg)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = Path(args.table).stem
    if args.force_class:
        suffix = f"_forced_class_{args.force_class.upper()}"
        if args.trim_to_force_class:
            suffix += "_trimmed"
    else:
        suffix = "_own_class" if args.own_class_only else ""
    filled_path = out / f"{stem}_filled{suffix}.csv"
    ext_path = out / f"{stem}_extended{suffix}.csv"

    with open(args.table, newline="") as f:
        reader = csv.reader(f)
        h1, h2 = next(reader), next(reader)
        rows = list(reader)

    classes_to_write = [args.force_class.upper()] if args.trim_to_force_class else BLOCK_CLASSES

    # header rows for the extended layout
    ext_h1, ext_h2 = h1[:BLOCK_START], h2[:BLOCK_START]
    for cls in classes_to_write:
        k = BLOCK_CLASSES.index(cls)
        s = BLOCK_START + k * BLOCK_WIDTH
        ext_h1 += h1[s:s + BLOCK_WIDTH] + [""] * len(EXTRA)
        ext_h2 += h2[s:s + BLOCK_WIDTH] + [name for name, _ in EXTRA]
    filled_h1, filled_h2 = h1[:BLOCK_START], h2[:BLOCK_START]
    for cls in classes_to_write:
        k = BLOCK_CLASSES.index(cls)
        s = BLOCK_START + k * BLOCK_WIDTH
        filled_h1 += h1[s:s + BLOCK_WIDTH]
        filled_h2 += h2[s:s + BLOCK_WIDTH]

    n_aashto = n_disagg = 0
    with open(filled_path, "w", newline="") as ff, open(ext_path, "w", newline="") as fe:
        wf, we = csv.writer(ff), csv.writer(fe)
        wf.writerow(filled_h1); wf.writerow(filled_h2)
        we.writerow(ext_h1); we.writerow(ext_h2)
        for row in rows:
            if len(row) < BLOCK_START + BLOCK_WIDTH * len(BLOCK_CLASSES):
                row = row + [""] * (BLOCK_START + BLOCK_WIDTH * len(BLOCK_CLASSES) - len(row))
            lon, lat = row[0].strip(), row[1].strip()
            own = args.force_class.upper() if args.force_class else row[5].strip().upper()
            mw, r = disagg.get((lon, lat), ("", ""))
            if mw:
                n_disagg += 1
            filled = row[:BLOCK_START]
            ext = row[:BLOCK_START]
            for cls in classes_to_write:
                k = BLOCK_CLASSES.index(cls)
                s = BLOCK_START + k * BLOCK_WIDTH
                if (args.own_class_only or args.force_class) and cls != own:
                    block = [cls, "", "", "", ""]
                    filled += block
                    ext += block + [""] * len(EXTRA)
                    continue
                a = aashto.get((lon, lat, cls))
                if a:
                    n_aashto += 1
                block = [cls, a["as"] if a else "", a["sd1"] if a else "", mw, r]
                filled += block
                ext += block + [a[key] if a else "" for _, key in EXTRA]
            wf.writerow(filled)
            we.writerow(ext)

    total_blocks = len(rows) * len(classes_to_write)
    print(f"rows: {len(rows)}")
    print(f"AASHTO blocks filled: {n_aashto}/{total_blocks}")
    print(f"disagg rows filled:   {n_disagg}/{len(rows)}")
    print(f"wrote {filled_path}")
    print(f"wrote {ext_path}")


if __name__ == "__main__":
    main()
