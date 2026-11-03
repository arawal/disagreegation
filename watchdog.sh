#!/bin/zsh
# Restarts the disagg and AASHTO runs if they exit before finishing.
cd "$(dirname "$0")"
TABLE="/Users/aksharrawal/Downloads/GA Seismic Data with County - AASHTO 9th 1(vs30_mosaic_GA_table (9thdata)).csv"
LOG=watchdog.log
MAX_RESTARTS=20
d_restarts=0; a_restarts=0
log() { echo "$(date '+%F %T') $*" >> $LOG; }
STALL_MIN=20
# true if the file has not been modified in STALL_MIN minutes
stalled() { [[ -f "$1" ]] && (( $(date +%s) - $(stat -f %m "$1") > STALL_MIN * 60 )); }
log "watchdog started"
while true; do
  # ---- disaggregation
  if [[ ! -f disagg_out/disagg_grid.csv ]]; then
    if pgrep -f "disagg_adaptive.py" >/dev/null && stalled disagg_out/points.jsonl; then
      log "STALL disagg: no new points for $STALL_MIN min, killing"; pkill -f "disagg_adaptive.py"; sleep 5
    fi
    if ! pgrep -f "disagg_adaptive.py" >/dev/null; then
      if (( d_restarts >= MAX_RESTARTS )); then
        log "GIVING UP on disagg after $d_restarts restarts"; d_done_giveup=1
      else
        d_restarts=$((d_restarts+1))
        log "RESTART disagg (#$d_restarts): last log lines: $(tail -2 disagg_out/run.log | tr '\n' ' ')"
        nohup python3 -u disagg_adaptive.py "$TABLE" --out disagg_out --spot-check 300 >> disagg_out/run.log 2>&1 &
      fi
    fi
  elif [[ -z $d_reported ]]; then
    log "DONE disagg: $(grep -E 'wrote|spot check:' disagg_out/run.log | tail -2 | tr '\n' ' ')"; d_reported=1
  fi
  # ---- AASHTO
  if [[ ! -f aashto_out/DONE ]]; then
    if pgrep -f "aashto_batch.py" >/dev/null && stalled aashto_out/values.jsonl; then
      log "STALL aashto: no new values for $STALL_MIN min, killing"; pkill -f "run_aashto"; pkill -f "aashto_batch.py"; sleep 5
    fi
    if ! pgrep -f "aashto_batch.py|run_aashto" >/dev/null; then
      if (( a_restarts >= MAX_RESTARTS )); then
        log "GIVING UP on aashto after $a_restarts restarts"
      else
        a_restarts=$((a_restarts+1))
        log "RESTART aashto (#$a_restarts): last log lines: $(tail -2 aashto_out/run.log | tr '\n' ' ')"
        nohup ./run_aashto2.sh >> aashto_out/run.log 2>&1 &
      fi
    fi
  elif [[ -z $a_reported ]]; then
    log "DONE aashto: $(grep wrote aashto_out/run.log | tail -1)"; a_reported=1
  fi
  if [[ -f disagg_out/disagg_grid.csv && -f aashto_out/DONE ]]; then log "ALL DONE"; exit 0; fi
  if (( d_restarts >= MAX_RESTARTS && a_restarts >= MAX_RESTARTS )); then log "watchdog exiting, both gave up"; exit 1; fi
  sleep 60
done
