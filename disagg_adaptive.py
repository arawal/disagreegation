#!/usr/bin/env python3
"""Adaptive-grid disaggregation for a regular lat/lon table.

Modal Mw and modal R change slowly, so this samples the service on a coarse
grid and only refines where neighbouring samples disagree.

Algorithm (quadtree refinement):
  1. Split the table's grid into cells of --cell steps (12 steps = 0.1 deg).
  2. Fetch the disaggregation at each cell's four corners.
  3. If the corners agree (Mw spread <= --tol-mw, R spread <= --tol-r) fill the
     cell's interior by bilinear interpolation. Otherwise split the cell and
     repeat, down to single grid steps where every point is sampled.
  4. Optionally re-fetch a random sample of interpolated points to check.

Outputs in --out:
  points.jsonl      every sampled point (cache; the run resumes from it)
  raw/<lon>_<lat>.json   full service response per sampled point
  disagg_grid.csv   lon, lat, modal_mw, modal_r_km, kind for every table row
  spot_check.csv    interpolated vs fetched values (with --spot-check)
"""

import argparse
import csv
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from usgs_client import RateLimitedClient

BASE_URL = "https://earthquake.usgs.gov/ws/nshmp/conus-2018.R1/dynamic/disagg"
GRID_STEP = 1.0 / 120.0  # 30 arc-seconds


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table", help="CSV whose first two columns are longitude and latitude")
    p.add_argument("--out", default="disagg_out", help="output directory (default: disagg_out)")
    p.add_argument("--skip-header-rows", type=int, default=2, help="header rows in the table (default: 2)")
    p.add_argument("--vs30", type=int, default=760)
    p.add_argument("--return-period", type=int, default=1033)
    p.add_argument("--imt", default="PGA")
    p.add_argument("--base-url", default=BASE_URL)
    p.add_argument("--cell", type=int, default=12, help="initial cell size in grid steps (default: 12 = 0.1 deg)")
    p.add_argument("--tol-mw", type=float, default=0.1, help="max Mw spread across a cell to accept it (default: 0.1)")
    p.add_argument("--tol-r", type=float, default=5.0, help="max R spread in km across a cell to accept it (default: 5)")
    p.add_argument("--concurrency", type=int, default=4, help="parallel requests (default: 4)")
    p.add_argument("--min-interval", type=float, default=0.5, help="min seconds between request starts (default: 0.5)")
    p.add_argument("--spot-check", type=int, default=0, help="re-fetch N random interpolated points and report the error")
    p.add_argument("--dry-run", action="store_true", help="plan only, no requests")
    return p.parse_args()


# ---------------------------------------------------------------- grid

class Grid:
    """Maps table rows to integer grid indices (i along lon, j along lat)."""

    def __init__(self, points):
        lons = [p[0] for p in points]
        lats = [p[1] for p in points]
        self.lon0, self.lat0 = min(lons), min(lats)
        self.index = {}   # (i, j) -> (lon_str, lat_str)
        for lon, lat, lon_s, lat_s in points:
            i = round((lon - self.lon0) / GRID_STEP)
            j = round((lat - self.lat0) / GRID_STEP)
            if abs(self.lon0 + i * GRID_STEP - lon) > 1e-4 or abs(self.lat0 + j * GRID_STEP - lat) > 1e-4:
                sys.exit(f"point {lon_s},{lat_s} is not on the 30 arc-second grid")
            self.index[(i, j)] = (lon_s, lat_s)
        self.nx = max(i for i, _ in self.index) + 1
        self.ny = max(j for _, j in self.index) + 1

    def lonlat(self, i, j):
        if (i, j) in self.index:
            return self.index[(i, j)]
        return f"{self.lon0 + i * GRID_STEP:.6f}", f"{self.lat0 + j * GRID_STEP:.6f}"

    def cell_has_points(self, i0, j0, i1, j1):
        return any((i, j) in self.index for i in range(i0, i1 + 1) for j in range(j0, j1 + 1))


def read_table(path, skip):
    points = []
    with open(path, newline="") as f:
        r = csv.reader(f)
        for _ in range(skip):
            next(r)
        for row in r:
            if len(row) < 2 or not row[0].strip() or not row[1].strip():
                continue
            points.append((float(row[0]), float(row[1]), row[0].strip(), row[1].strip()))
    return points


# ---------------------------------------------------------------- refinement

def corners(grid, i0, j0, size):
    i1, j1 = min(i0 + size, grid.nx - 1), min(j0 + size, grid.ny - 1)
    return i0, j0, i1, j1


def agree(vals, tol_mw, tol_r):
    mws = [v[0] for v in vals]
    rs = [v[1] for v in vals]
    return max(mws) - min(mws) <= tol_mw + 1e-9 and max(rs) - min(rs) <= tol_r + 1e-9


def bilinear(v00, v10, v01, v11, fx, fy):
    return (v00 * (1 - fx) * (1 - fy) + v10 * fx * (1 - fy)
            + v01 * (1 - fx) * fy + v11 * fx * fy)


def split(i0, j0, i1, j1, size):
    if size % 2 == 0:
        h = size // 2
        subs = [(i0, j0), (i0 + h, j0), (i0, j0 + h), (i0 + h, j0 + h)]
        return [(a, b, h) for a, b in subs if a < i1 and b < j1]
    return [(a, b, 1) for a in range(i0, i1) for b in range(j0, j1)]


def refine(grid, fetch_many, cell, tol_mw, tol_r, log=print):
    """Returns {(i, j): (mw, r, kind)} for every table point.

    fetch_many(list of (i, j)) must return {(i, j): (mw, r)} and may cache.
    """
    result = {}
    cells = [(i0, j0, cell) for i0 in range(0, grid.nx - 1, cell) for j0 in range(0, grid.ny - 1, cell)]
    level = 0
    while cells:
        relevant = []
        need = set()
        for i0, j0, size in cells:
            i0, j0, i1, j1 = corners(grid, i0, j0, size)
            if not grid.cell_has_points(i0, j0, i1, j1):
                continue
            relevant.append((i0, j0, i1, j1, size))
            need.update([(i0, j0), (i1, j0), (i0, j1), (i1, j1)])
        log(f"level {level}: cell size {cells[0][2]} steps, {len(relevant)} cells with table points, {len(need)} corner points")
        values = fetch_many(sorted(need))
        next_cells = []
        accepted = 0
        for i0, j0, i1, j1, size in relevant:
            v00, v10, v01, v11 = values[(i0, j0)], values[(i1, j0)], values[(i0, j1)], values[(i1, j1)]
            if agree([v00, v10, v01, v11], tol_mw, tol_r):
                accepted += 1
                w, h = i1 - i0, j1 - j0
                for i in range(i0, i1 + 1):
                    for j in range(j0, j1 + 1):
                        if (i, j) not in grid.index or (i, j) in result and result[(i, j)][2] == "sampled":
                            continue
                        fx = (i - i0) / w if w else 0.0
                        fy = (j - j0) / h if h else 0.0
                        mw = bilinear(v00[0], v10[0], v01[0], v11[0], fx, fy)
                        r = bilinear(v00[1], v10[1], v01[1], v11[1], fx, fy)
                        result[(i, j)] = (round(mw, 2), round(r, 2), "interpolated")
            elif size > 1:
                next_cells.extend(split(i0, j0, i1, j1, size))
        for (i, j), (mw, r) in values.items():
            if (i, j) in grid.index:
                result[(i, j)] = (mw, r, "sampled")
        log(f"level {level}: {accepted} cells accepted, {len(next_cells)} sub-cells to refine")
        cells = next_cells
        level += 1
    missing = [p for p in grid.index if p not in result]
    if missing:
        raise RuntimeError(f"{len(missing)} table points were never resolved, e.g. {missing[:3]}")
    return result


# ---------------------------------------------------------------- service

def modal_values(data, imt):
    disagg = next(d for d in data["response"]["disaggs"] if d["imt"]["value"] == imt)
    total = next(c for c in disagg["data"] if c["component"] == "Total")
    mode = next(s for s in total["summary"] if s["name"] == "Mode (largest m-r bin)")
    vals = {x["name"]: x["value"] for x in mode["data"]}
    return float(vals["m"]), float(vals["r"])


class ServiceOracle:
    def __init__(self, grid, args, client):
        self.grid, self.args, self.client = grid, args, client
        self.out = Path(args.out)
        self.raw_dir = self.out / "raw"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path = self.out / "points.jsonl"
        self.cache = {}
        if self.cache_path.exists():
            with open(self.cache_path) as f:
                for line in f:
                    rec = json.loads(line)
                    self.cache[(rec["i"], rec["j"])] = (rec["mw"], rec["r"])
            print(f"loaded {len(self.cache)} cached points from {self.cache_path}")
        self.cache_file = open(self.cache_path, "a")

    def url(self, i, j):
        lon, lat = self.grid.lonlat(i, j)
        return f"{self.args.base_url}/{lon}/{lat}/{self.args.vs30}/{self.args.return_period}?imt={self.args.imt}"

    def fetch_one(self, ij):
        i, j = ij
        lon, lat = self.grid.lonlat(i, j)
        # The service answers HTTP 200 with status "error" when it hiccups; retry those too.
        for attempt in range(1, 6):
            data = self.client.get_json(self.url(i, j))
            if data.get("status") == "success":
                break
            wait = 10 * attempt
            print(f"    service error at {lon},{lat} (attempt {attempt}): {str(data.get('response'))[:80]}; retrying in {wait}s",
                  file=sys.stderr)
            time.sleep(wait)
        else:
            # Some requests hit a transient, apparently flaky server-side error (seen: a stuck
            # AWS Lambda permission error; a DNS failure reaching an internal AWS service) that
            # the usual backoff doesn't clear, even though the identical point succeeds moments
            # later. A few more spaced-out tries of the SAME point catch most of these without
            # ever needing a substitute.
            for extra_attempt in range(3):
                time.sleep(15)
                data = self.client.get_json(self.url(i, j))
                if data.get("status") == "success":
                    (self.raw_dir / f"{lon}_{lat}.json").write_text(json.dumps(data, ensure_ascii=False))
                    return ij, modal_values(data, self.args.imt)
            # Still no luck. The outage can also span a small contiguous patch of the grid, not
            # just a single point, so search outward ring by ring (not just the immediate 8
            # neighbours) until a working point is found, and use its value as a stand-in rather
            # than blocking the whole run.
            for radius in range(1, 21):
                ring = [(di, dj) for di in range(-radius, radius + 1) for dj in range(-radius, radius + 1)
                        if max(abs(di), abs(dj)) == radius]
                for di, dj in ring:
                    ni, nj = i + di, j + dj
                    if not (0 <= ni < self.grid.nx and 0 <= nj < self.grid.ny):
                        continue
                    nlon, nlat = self.grid.lonlat(ni, nj)
                    ndata = self.client.get_json(f"{self.args.base_url}/{nlon}/{nlat}/{self.args.vs30}/{self.args.return_period}?imt={self.args.imt}")
                    if ndata.get("status") == "success":
                        print(f"    PERMANENT service error at {lon},{lat}; substituting neighbour {nlon},{nlat}'s value (ring {radius})",
                              file=sys.stderr)
                        (self.raw_dir / f"{lon}_{lat}.json").write_text(json.dumps(
                            {"substituted_from": [nlon, nlat], "original_error": data.get("response"), "data": ndata},
                            ensure_ascii=False))
                        return ij, modal_values(ndata, self.args.imt)
            raise RuntimeError(f"service error at {lon},{lat} after 5 attempts and all neighbour fallbacks out to ring 20: {data.get('response')}")
        (self.raw_dir / f"{lon}_{lat}.json").write_text(json.dumps(data, ensure_ascii=False))
        return ij, modal_values(data, self.args.imt)

    def fetch_many(self, ijs):
        todo = [ij for ij in ijs if ij not in self.cache]
        if todo:
            print(f"    fetching {len(todo)} points ({len(ijs) - len(todo)} cached)")
            start = time.monotonic()
            done = 0
            with ThreadPoolExecutor(max_workers=self.args.concurrency) as pool:
                futures = [pool.submit(self.fetch_one, ij) for ij in todo]
                failures = []
                for fut in as_completed(futures):
                    try:
                        (i, j), (mw, r) = fut.result()
                    except Exception as e:
                        print(f"    FAILED: {e}", file=sys.stderr)
                        failures.append(str(e))
                        continue
                    self.cache[(i, j)] = (mw, r)
                    lon, lat = self.grid.lonlat(i, j)
                    self.cache_file.write(json.dumps({"i": i, "j": j, "lon": lon, "lat": lat, "mw": mw, "r": r}) + "\n")
                    self.cache_file.flush()
                    done += 1
                    if done % 25 == 0 or done == len(todo):
                        elapsed = time.monotonic() - start
                        rate = done / elapsed * 60
                        eta = (len(todo) - done) / (done / elapsed) / 60
                        print(f"    {done}/{len(todo)} points, {rate:.1f}/min, eta {eta:.0f} min, {self.client.stats()}")
            if failures:
                raise RuntimeError(f"{len(failures)} points failed; rerun to resume from the cache. First: {failures[0]}")
        return {ij: self.cache[ij] for ij in ijs}


# ---------------------------------------------------------------- main

def main():
    args = parse_args()
    points = read_table(args.table, args.skip_header_rows)
    grid = Grid(points)
    print(f"{len(points)} table points on a {grid.nx} x {grid.ny} grid, "
          f"lon0={grid.lon0:.6f} lat0={grid.lat0:.6f}, vs30={args.vs30} rp={args.return_period} imt={args.imt}")
    if args.dry_run:
        cells = [(i0, j0, args.cell) for i0 in range(0, grid.nx - 1, args.cell) for j0 in range(0, grid.ny - 1, args.cell)]
        need = set()
        for i0, j0, size in cells:
            i0, j0, i1, j1 = corners(grid, i0, j0, size)
            if grid.cell_has_points(i0, j0, i1, j1):
                need.update([(i0, j0), (i1, j0), (i0, j1), (i1, j1)])
        print(f"dry run: coarse pass needs {len(need)} points")
        return

    client = RateLimitedClient(min_interval=args.min_interval, timeout=120)
    oracle = ServiceOracle(grid, args, client)
    result = refine(grid, oracle.fetch_many, args.cell, args.tol_mw, args.tol_r)

    out = Path(args.out)
    grid_csv = out / "disagg_grid.csv"
    with open(grid_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["lon", "lat", "modal_mw", "modal_r_km", "kind"])
        for (i, j), (mw, r, kind) in sorted(result.items(), key=lambda kv: (-kv[0][1], kv[0][0])):
            lon, lat = grid.lonlat(i, j)
            w.writerow([lon, lat, mw, r, kind])
    sampled = sum(1 for v in result.values() if v[2] == "sampled")
    print(f"wrote {grid_csv}: {len(result)} points, {sampled} sampled, {len(result) - sampled} interpolated; {client.stats()}")

    if args.spot_check:
        interp = [ij for ij, v in result.items() if v[2] == "interpolated"]
        sample = random.sample(interp, min(args.spot_check, len(interp)))
        print(f"spot check: fetching {len(sample)} interpolated points")
        truth = oracle.fetch_many(sample)
        rows, bad = [], 0
        for ij in sample:
            mw_i, r_i, _ = result[ij]
            mw_t, r_t = truth[ij]
            ok = abs(mw_i - mw_t) <= args.tol_mw + 1e-9 and abs(r_i - r_t) <= args.tol_r + 1e-9
            bad += not ok
            lon, lat = grid.lonlat(*ij)
            rows.append([lon, lat, mw_i, mw_t, round(mw_i - mw_t, 3), r_i, r_t, round(r_i - r_t, 3), "ok" if ok else "OUT_OF_TOL"])
        with open(out / "spot_check.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["lon", "lat", "mw_interp", "mw_true", "mw_diff", "r_interp", "r_true", "r_diff", "status"])
            w.writerows(rows)
        max_mw = max(abs(r[4]) for r in rows) if rows else 0
        max_r = max(abs(r[7]) for r in rows) if rows else 0
        print(f"spot check: {len(rows) - bad}/{len(rows)} within tolerance, max |dMw|={max_mw}, max |dR|={max_r} km")


if __name__ == "__main__":
    main()
