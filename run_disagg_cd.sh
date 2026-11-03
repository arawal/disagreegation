#!/bin/zsh
cd "$(dirname "$0")"
TABLE="/Users/aksharrawal/Downloads/GA Seismic Data with County - AASHTO 9th 1(vs30_mosaic_GA_table (9thdata)).csv"
if [[ ! -f disagg_out_C/disagg_grid.csv ]]; then
  python3 -u disagg_adaptive.py "$TABLE" --out disagg_out_C --vs30 530 --spot-check 300 --concurrency 4 --min-interval 0.6
fi
if [[ ! -f disagg_out_C/disagg_grid.csv ]]; then
  echo "=== disagg class C did not finish (exited without writing disagg_grid.csv); not starting class D ==="
  exit 1
fi
echo "=== disagg class C finished, starting class D ==="
python3 -u disagg_adaptive.py "$TABLE" --out disagg_out_D --vs30 260 --spot-check 300 --concurrency 4 --min-interval 0.6
if [[ ! -f disagg_out_D/disagg_grid.csv ]]; then
  echo "=== disagg class D did not finish (exited without writing disagg_grid.csv) ==="
  exit 1
fi
echo "=== disagg class D finished ==="
