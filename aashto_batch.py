#!/usr/bin/env python3
"""Batch query the USGS AASHTO-2009 design map service.

One request per table point per site class. Results are appended to a
JSONL cache as they arrive, so a stopped run resumes where it left off.

Outputs in --out:
  values.jsonl        cache of every fetched (lon, lat, site class) result
  aashto_values.csv   lon, lat, site_class, pga, fpga, as, ss, fa, sds, s1, fv, sd1, sdc, ts, t0
                      (rows stream in as they arrive; rewritten in table order at the end)
"""

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from usgs_client import RateLimitedClient

BASE_URL = "https://earthquake.usgs.gov/ws/building-codes/aashto-2009/calculate"
FIELDS = ["pga", "fpga", "as", "ss", "fa", "sds", "s1", "fv", "sd1", "sdc", "ts", "t0"]


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table", help="CSV whose first two columns are longitude and latitude")
    p.add_argument("--out", default="aashto_out")
    p.add_argument("--skip-header-rows", type=int, default=2)
    p.add_argument("--site-classes", default="A,B,C,D,E", help="comma list (default: A,B,C,D,E)")
    p.add_argument("--own-class-column", type=int, default=None,
                   help="0-based column holding each row's site class; if set, only that class is fetched per row")
    p.add_argument("--concurrency", type=int, default=6)
    p.add_argument("--min-interval", type=float, default=0.1, help="min seconds between request starts (default: 0.1)")
    p.add_argument("--base-url", default=BASE_URL)
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def read_jobs(path, skip, classes, own_col):
    jobs = []
    with open(path, newline="") as f:
        r = csv.reader(f)
        for _ in range(skip):
            next(r)
        for row in r:
            if len(row) < 2 or not row[0].strip() or not row[1].strip():
                continue
            lon, lat = row[0].strip(), row[1].strip()
            if own_col is not None:
                jobs.append((lon, lat, row[own_col].strip().upper()))
            else:
                jobs.extend((lon, lat, c) for c in classes)
    return jobs


def main():
    args = parse_args()
    classes = [c.strip().upper() for c in args.site_classes.split(",") if c.strip()]
    jobs = read_jobs(args.table, args.skip_header_rows, classes, args.own_class_column)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cache_path = out / "values.jsonl"
    cache = {}
    if cache_path.exists():
        with open(cache_path) as f:
            for line in f:
                rec = json.loads(line)
                cache[(rec["lon"], rec["lat"], rec["site_class"])] = rec
    todo = [j for j in jobs if j not in cache]
    print(f"{len(jobs)} jobs, {len(cache)} cached, {len(todo)} to fetch, concurrency={args.concurrency}")
    if args.dry_run:
        return

    client = RateLimitedClient(min_interval=args.min_interval, timeout=60)
    csv_path = out / "aashto_values.csv"
    csv_fields = ["lon", "lat", "site_class"] + FIELDS
    # Start the CSV from the cache so a viewer can watch rows arrive.
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_fields)
        w.writeheader()
        for j in jobs:
            if j in cache:
                w.writerow(cache[j])

    def fetch(job):
        lon, lat, sc = job
        url = f"{args.base_url}?latitude={lat}&longitude={lon}&siteClass={sc}&title=batch"
        data = client.get_json(url)
        req = data.get("request", {})
        if req.get("status") != "success":
            raise RuntimeError(f"service error at {lon},{lat},{sc}: {data}")
        d = data["response"]["data"]
        rec = {"lon": lon, "lat": lat, "site_class": sc}
        rec.update({k: d.get(k) for k in FIELDS})
        return job, rec

    if todo:
        start = time.monotonic()
        done = 0
        with open(cache_path, "a") as cf, open(csv_path, "a", newline="") as sf, \
                ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            stream = csv.DictWriter(sf, fieldnames=csv_fields)
            futures = [pool.submit(fetch, j) for j in todo]
            for fut in as_completed(futures):
                try:
                    job, rec = fut.result()
                except Exception as e:
                    print(f"FAILED: {e}", file=sys.stderr)
                    continue
                cache[job] = rec
                cf.write(json.dumps(rec) + "\n")
                cf.flush()
                stream.writerow(rec)
                sf.flush()
                done += 1
                if done % 200 == 0 or done == len(todo):
                    el = time.monotonic() - start
                    print(f"  {done}/{len(todo)}  {done / el * 60:.0f}/min  eta {(len(todo) - done) / (done / el) / 60:.0f} min  {client.stats()}")

    missing = [j for j in jobs if j not in cache]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_fields)
        w.writeheader()
        for j in jobs:
            if j in cache:
                w.writerow(cache[j])
    print(f"wrote {csv_path}: {len(jobs) - len(missing)} rows, {len(missing)} missing")
    if missing:
        sys.exit(1)


if __name__ == "__main__":
    main()
