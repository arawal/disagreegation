#!/bin/zsh
cd "$(dirname "$0")"
TABLE="/Users/aksharrawal/Downloads/GA Seismic Data with County - AASHTO 9th 1(vs30_mosaic_GA_table (9thdata)).csv"
python3 -u aashto_batch.py "$TABLE" --out aashto_out_CD --site-classes C,D --concurrency 20 --min-interval 0.03 && touch aashto_out_CD/DONE
echo "=== aashto C,D pass finished ==="
