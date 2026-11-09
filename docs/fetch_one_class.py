#!/usr/bin/env python3
"""Usage: python3 fetch_one_class.py input.csv output.csv
input.csv needs "lat" and "lon" columns. Set CLASS and VS30 below first."""
import csv, json, sys, time, urllib.request

CLASS, VS30, RETURN_PERIOD = "D", 260, 1033  # change CLASS + VS30 together (see page 1 table)

def fetch(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)

def one_point(lat, lon):
    design = fetch(
        f"https://earthquake.usgs.gov/ws/building-codes/aashto-2009/calculate"
        f"?latitude={lat}&longitude={lon}&siteClass={CLASS}")["response"]["data"]
    disagg = fetch(
        f"https://earthquake.usgs.gov/ws/nshmp/conus-2018.R1/dynamic/disagg/"
        f"{lon}/{lat}/{VS30}/{RETURN_PERIOD}?imt=PGA")
    mode = next(s for s in disagg["response"]["disaggs"][0]["data"][0]["summary"]
                if s["name"] == "Mode (largest m-r bin)")["data"]
    mw = next(d["value"] for d in mode if d["name"] == "m")
    r_km = next(d["value"] for d in mode if d["name"] == "r")
    return {"lat": lat, "lon": lon, "As": design["as"], "Sd1": design["sd1"],
            "PGA": design["pga"], "Ss": design["ss"], "S1": design["s1"],
            "Sds": design["sds"], "Zone": design["sdc"], "Modal_Mw": mw, "Modal_R_km": r_km}

with open(sys.argv[1], newline="") as fin, \
     open(sys.argv[2], "w", newline="") as fout:
    writer = None
    for row in csv.DictReader(fin):
        result = one_point(row["lat"], row["lon"])
        if writer is None:
            writer = csv.DictWriter(fout, fieldnames=result.keys())
            writer.writeheader()
        writer.writerow(result)
        time.sleep(0.5)  # be polite to USGS
