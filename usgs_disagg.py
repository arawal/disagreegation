#!/usr/bin/env python3
"""Batch query the USGS NSHMP disaggregation web service.

Reads sites from a CSV, calls the service once per site, and writes:
  - raw/<site>.json   full service response per site
  - summary.csv       one row per site with the summary values
  - sources.csv       one row per contributing source per site

Input CSV columns: lat, lon and an optional name column.

Example:
  python3 usgs_disagg.py sites.csv --out results
"""

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE_URL = "https://earthquake.usgs.gov/ws/nshmp/conus-2018.R1/dynamic/disagg"
TOP_SOURCES = 5


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sites", help="CSV file with lat, lon and optional name columns")
    p.add_argument("--out", default="results", help="output directory (default: results)")
    p.add_argument("--vs30", type=int, default=760, help="Vs30 in m/s (default: 760, site class BC)")
    p.add_argument("--return-period", type=int, default=2475, help="return period in years (default: 2475)")
    p.add_argument("--imt", default="PGA", help="intensity measure type (default: PGA)")
    p.add_argument("--base-url", default=BASE_URL, help="service URL for a different model")
    p.add_argument("--retries", type=int, default=3, help="retries per site on failure (default: 3)")
    p.add_argument("--delay", type=float, default=1.0, help="seconds to wait between requests (default: 1)")
    return p.parse_args()


def read_sites(path):
    sites = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        cols = {c.lower().strip(): c for c in reader.fieldnames}
        lat_col = next((cols[c] for c in ("lat", "latitude") if c in cols), None)
        lon_col = next((cols[c] for c in ("lon", "lng", "long", "longitude") if c in cols), None)
        name_col = next((cols[c] for c in ("name", "site", "id") if c in cols), None)
        if not lat_col or not lon_col:
            sys.exit("input CSV needs lat and lon columns")
        for i, row in enumerate(reader, start=1):
            lat = float(row[lat_col])
            lon = float(row[lon_col])
            name = row[name_col].strip() if name_col and row[name_col].strip() else f"site{i:03d}"
            sites.append({"name": name, "lat": lat, "lon": lon})
    return sites


def fetch(url, retries):
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=300) as resp:
                data = json.load(resp)
            if data.get("status") != "success":
                raise RuntimeError(f"service returned {data.get('status')}: {data.get('response')}")
            return data
        except (urllib.error.URLError, RuntimeError, json.JSONDecodeError) as e:
            last_err = e
            print(f"    attempt {attempt} failed: {e}", file=sys.stderr)
            time.sleep(5 * attempt)
    raise RuntimeError(f"gave up after {retries} attempts: {last_err}")


def summarize(site, data, imt):
    """Flatten the Total component summary into one dict."""
    disagg = next(d for d in data["response"]["disaggs"] if d["imt"]["value"] == imt)
    total = next(c for c in disagg["data"] if c["component"] == "Total")
    blocks = {s["name"]: {x["name"]: x["value"] for x in s["data"]} for s in total["summary"]}

    target = blocks.get("Disaggregation targets", {})
    recovered = blocks.get("Recovered targets", {})
    mean = blocks.get("Mean (over all sources)", {})
    mode_mr = blocks.get("Mode (largest m-r bin)", {})
    mode_mre = blocks.get("Mode (largest m-r-ε₀ bin)", {})
    gm_key = next((k for k in target if k.endswith("ground motion")), None)

    row = {
        "name": site["name"],
        "lat": site["lat"],
        "lon": site["lon"],
        "imt": imt,
        "target_return_period_yr": target.get("Return period"),
        "target_ground_motion": target.get(gm_key) if gm_key else None,
        "recovered_return_period_yr": recovered.get("Return period"),
        "mean_m": mean.get("m"),
        "mean_r_km": mean.get("r"),
        "mean_eps": mean.get("ε₀"),
        "mode_mr_m": mode_mr.get("m"),
        "mode_mr_r_km": mode_mr.get("r"),
        "mode_mr_eps": mode_mr.get("ε₀"),
        "mode_mr_contrib_pct": mode_mr.get("Contribution"),
        "mode_mre_m": mode_mre.get("m"),
        "mode_mre_r_km": mode_mre.get("r"),
        "mode_mre_eps": mode_mre.get("ε₀"),
        "mode_mre_contrib_pct": mode_mre.get("Contribution"),
    }
    # The service lists each source set, then the single sources inside it.
    # Rank only the sets so the same source does not appear twice.
    sets = sorted((s for s in total.get("sources", []) if s["type"] == "SET"), key=lambda s: -s["contribution"])
    for i in range(TOP_SOURCES):
        src = sets[i] if i < len(sets) else {}
        row[f"source{i+1}_name"] = src.get("name")
        row[f"source{i+1}_type"] = src.get("source")
        row[f"source{i+1}_contrib_pct"] = src.get("contribution")
    return row


def source_rows(site, data, imt):
    """One row per entry in the Total component source table."""
    disagg = next(d for d in data["response"]["disaggs"] if d["imt"]["value"] == imt)
    total = next(c for c in disagg["data"] if c["component"] == "Total")
    rows = []
    for s in total.get("sources", []):
        rows.append({
            "name": site["name"],
            "lat": site["lat"],
            "lon": site["lon"],
            "source_name": s["name"],
            "source_type": s["source"],
            "level": s["type"],
            "contrib_pct": s["contribution"],
            "r_km": s["r"],
            "m": s["m"],
            "eps": s["ε"],
            "azimuth": s["azimuth"],
            "src_lat": s["latitude"],
            "src_lon": s["longitude"],
        })
    return rows


def main():
    args = parse_args()
    sites = read_sites(args.sites)
    out = Path(args.out)
    raw_dir = out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    src_rows = []
    failures = []
    print(f"{len(sites)} sites, vs30={args.vs30}, return period={args.return_period}, imt={args.imt}")
    for n, site in enumerate(sites, start=1):
        url = f"{args.base_url}/{site['lon']}/{site['lat']}/{args.vs30}/{args.return_period}?" + urllib.parse.urlencode({"imt": args.imt})
        print(f"[{n}/{len(sites)}] {site['name']} ({site['lat']}, {site['lon']})")
        raw_path = raw_dir / f"{site['name']}.json"
        try:
            if raw_path.exists():
                print("    using cached raw file")
                data = json.loads(raw_path.read_text())
            else:
                data = fetch(url, args.retries)
                raw_path.write_text(json.dumps(data, indent=1, ensure_ascii=False))
                time.sleep(args.delay)
            rows.append(summarize(site, data, args.imt))
            src_rows.extend(source_rows(site, data, args.imt))
        except Exception as e:
            print(f"    FAILED: {e}", file=sys.stderr)
            failures.append((site["name"], str(e)))

    if rows:
        csv_path = out / "summary.csv"
        with open(csv_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {csv_path} ({len(rows)} rows)")
    if src_rows:
        src_path = out / "sources.csv"
        with open(src_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(src_rows[0].keys()))
            w.writeheader()
            w.writerows(src_rows)
        print(f"wrote {src_path} ({len(src_rows)} rows)")
    if failures:
        print(f"{len(failures)} sites failed:", file=sys.stderr)
        for name, err in failures:
            print(f"  {name}: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
