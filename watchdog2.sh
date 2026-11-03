#!/bin/zsh
# Restarts: (1) disagg at vs30=150 (class E), (2) the aashto chain (resume all-classes, then class-E).
cd "$(dirname "$0")"
TABLE="/Users/aksharrawal/Downloads/GA Seismic Data with County - AASHTO 9th 1(vs30_mosaic_GA_table (9thdata)).csv"
LOG=watchdog2.log
MAX_RESTARTS=30
d_restarts=0; a_restarts=0
log() { echo "$(date '+%F %T') $*" >> $LOG; }
stalled() { [[ -f "$1" ]] && (( $(date +%s) - $(stat -f %m "$1") > 20 * 60 )); }
log "watchdog2 started"
while true; do
  # ---- disaggregation, class E (vs30=150)
  if [[ ! -f disagg_out_E/disagg_grid.csv ]]; then
    if pgrep -f "disagg_adaptive.py.*disagg_out_E" >/dev/null && stalled disagg_out_E/points.jsonl; then
      log "STALL disaggE: no new points for 20 min, killing"; pkill -f "disagg_adaptive.py.*disagg_out_E"; sleep 5
    fi
    if ! pgrep -f "disagg_adaptive.py.*disagg_out_E" >/dev/null; then
      if (( d_restarts >= MAX_RESTARTS )); then
        log "GIVING UP on disaggE after $d_restarts restarts"
      else
        d_restarts=$((d_restarts+1))
        log "RESTART disaggE (#$d_restarts)"
        nohup python3 -u disagg_adaptive.py "$TABLE" --out disagg_out_E --vs30 150 --spot-check 300 --concurrency 4 --min-interval 0.6 >> disagg_out_E/run.log 2>&1 &
      fi
    fi
  elif [[ -z $d_reported ]]; then
    log "DONE disaggE: $(grep -E 'wrote|spot check:' disagg_out_E/run.log | tail -2 | tr '\n' ' ')"; d_reported=1
  fi
  # ---- aashto chain (resume all-classes, then class E)
  if [[ ! -f aashto_out_E/DONE ]]; then
    if pgrep -f "run_aashto_chain|aashto_batch.py" >/dev/null; then
      latest=$(ls -t aashto_out/values.jsonl aashto_out_E/values.jsonl 2>/dev/null | head -1)
      if [[ -n "$latest" ]] && stalled "$latest"; then
        log "STALL aashto chain: no new values for 20 min, killing"; pkill -f "run_aashto_chain"; pkill -f "aashto_batch.py"; sleep 5
      fi
    fi
    if ! pgrep -f "run_aashto_chain|aashto_batch.py" >/dev/null; then
      if (( a_restarts >= MAX_RESTARTS )); then
        log "GIVING UP on aashto chain after $a_restarts restarts"
      else
        a_restarts=$((a_restarts+1))
        log "RESTART aashto chain (#$a_restarts)"
        mkdir -p aashto_out_E
        nohup ./run_aashto_chain.sh >> aashto_out_E/run.log 2>&1 &
      fi
    fi
  elif [[ -z $a_reported ]]; then
    log "DONE aashto chain (class E pass): $(grep wrote aashto_out_E/run.log | tail -1)"; a_reported=1
  fi
  if [[ -f disagg_out_E/disagg_grid.csv && -f aashto_out_E/DONE ]]; then log "ALL DONE"; exit 0; fi
  if (( d_restarts >= MAX_RESTARTS && a_restarts >= MAX_RESTARTS )); then log "watchdog2 exiting, both gave up"; exit 1; fi
  sleep 60
done
