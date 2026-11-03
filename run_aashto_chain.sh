#!/bin/zsh
# Class-E-for-everyone pass only. The per-row-class (all-classes) pass was stopped by request;
# its partial cache in aashto_out/ is kept but no longer being extended.
cd "$(dirname "$0")"
TABLE="/Users/aksharrawal/Downloads/GA Seismic Data with County - AASHTO 9th 1(vs30_mosaic_GA_table (9thdata)).csv"
echo "=== starting class-E-for-everyone pass ==="
python3 -u aashto_batch.py "$TABLE" --out aashto_out_E --site-classes E --concurrency 20 --min-interval 0.03 && touch aashto_out_E/DONE
echo "=== class-E pass finished ==="
