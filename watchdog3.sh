#!/bin/zsh
cd "$(dirname "$0")"
LOG=watchdog3.log
MAX_RESTARTS=30
a_restarts=0; d_restarts=0
log() { echo "$(date '+%F %T') $*" >> $LOG; }
stalled() { [[ -f "$1" ]] && (( $(date +%s) - $(stat -f %m "$1") > 20 * 60 )); }
log "watchdog3 started"
while true; do
  if [[ ! -f aashto_out_CD/DONE ]]; then
    if pgrep -f "run_aashto_cd|aashto_batch.py.*aashto_out_CD" >/dev/null && stalled aashto_out_CD/values.jsonl; then
      log "STALL aashtoCD: killing"; pkill -f "run_aashto_cd|aashto_batch.py.*aashto_out_CD"; sleep 5
    fi
    if ! pgrep -f "run_aashto_cd|aashto_batch.py.*aashto_out_CD" >/dev/null; then
      if (( a_restarts >= MAX_RESTARTS )); then log "GIVING UP aashtoCD"; else
        a_restarts=$((a_restarts+1)); log "RESTART aashtoCD (#$a_restarts)"
        nohup ./run_aashto_cd.sh >> aashto_out_CD/run.log 2>&1 &
      fi
    fi
  elif [[ -z $a_reported ]]; then log "DONE aashtoCD: $(grep wrote aashto_out_CD/run.log | tail -1)"; a_reported=1; fi

  if [[ ! -f disagg_out_D/disagg_grid.csv ]]; then
    latest=$(ls -t disagg_out_C/points.jsonl disagg_out_D/points.jsonl 2>/dev/null | head -1)
    if pgrep -f "run_disagg_cd|disagg_adaptive.py.*disagg_out_[CD]" >/dev/null && [[ -n "$latest" ]] && stalled "$latest"; then
      log "STALL disaggCD: killing"; pkill -f "run_disagg_cd|disagg_adaptive.py.*disagg_out_[CD]"; sleep 5
    fi
    if ! pgrep -f "run_disagg_cd|disagg_adaptive.py.*disagg_out_[CD]" >/dev/null; then
      if (( d_restarts >= MAX_RESTARTS )); then log "GIVING UP disaggCD"; else
        d_restarts=$((d_restarts+1)); log "RESTART disaggCD (#$d_restarts)"
        nohup ./run_disagg_cd.sh >> disagg_out_C/run.log 2>&1 &
      fi
    fi
  elif [[ -z $d_reported ]]; then log "DONE disaggCD"; d_reported=1; fi

  if [[ -f aashto_out_CD/DONE && -f disagg_out_D/disagg_grid.csv ]]; then log "ALL DONE"; exit 0; fi
  if (( a_restarts >= MAX_RESTARTS && d_restarts >= MAX_RESTARTS )); then log "watchdog3 exiting, both gave up"; exit 1; fi
  sleep 60
done
