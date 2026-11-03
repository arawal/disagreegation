#!/bin/zsh
# Pass 1: each row's own site class. Pass 2: all five classes (cache skips pass 1 results).
cd "$(dirname "$0")"
TABLE="/Users/aksharrawal/Downloads/GA Seismic Data with County - AASHTO 9th 1(vs30_mosaic_GA_table (9thdata)).csv"
python3 -u aashto_batch.py "$TABLE" --out aashto_out --own-class-column 5
echo "=== own-class pass finished, starting all-classes pass ==="
python3 -u aashto_batch.py "$TABLE" --out aashto_out
echo "=== all-classes pass finished ==="
