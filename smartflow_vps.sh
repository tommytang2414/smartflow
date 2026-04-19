#!/bin/bash
# SmartFlow VPS Runner — daily restart via cron at 06:00 UTC
# Kills any existing scheduler process before starting a fresh one.
# Usage: ./smartflow_vps.sh (called by cron, or manually)

set -euo pipefail

export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export PYTHONIOENCODING=utf-8

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/smartflow.pid"
LOG_DIR="$SCRIPT_DIR/logs"
LOGFILE="$LOG_DIR/smartflow_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOGFILE"
}

log "=== SmartFlow VPS Runner starting ==="

# --- Kill existing scheduler process ---
if [[ -f "$PID_FILE" ]]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        log "Stopping existing scheduler (PID=$OLD_PID)..."
        kill "$OLD_PID"
        for i in $(seq 1 15); do
            if ! kill -0 "$OLD_PID" 2>/dev/null; then
                log "Stopped cleanly after ${i}s"
                break
            fi
            sleep 1
        done
        if kill -0 "$OLD_PID" 2>/dev/null; then
            log "Force-killing PID=$OLD_PID"
            kill -9 "$OLD_PID" 2>/dev/null || true
        fi
    else
        log "PID file found but process $OLD_PID is not running (stale PID file)"
    fi
    rm -f "$PID_FILE"
fi

# Kill any stray smartflow scheduler processes not tracked by PID file
STRAY=$(pgrep -f "python3 -m smartflow schedule" 2>/dev/null || true)
if [[ -n "$STRAY" ]]; then
    log "Killing stray scheduler PIDs: $STRAY"
    echo "$STRAY" | xargs kill 2>/dev/null || true
    sleep 2
fi

# --- Upload DB to S3 before restart ---
log "Uploading current DB to S3 before restart..."
aws s3 cp "$SCRIPT_DIR/data/smartflow.db" \
    "s3://smartflow-tommy-db/$(date +%Y%m%d)/smartflow.db" >> "$LOGFILE" 2>&1 || \
    log "WARNING: S3 pre-restart upload failed (non-fatal)"

# --- Start fresh scheduler ---
cd "$SCRIPT_DIR"
log "Starting scheduler..."
nohup python3 -m smartflow schedule --all >> "$LOGFILE" 2>&1 &
NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"
log "Scheduler started: PID=$NEW_PID, log=$LOGFILE"

sleep 5
if kill -0 "$NEW_PID" 2>/dev/null; then
    log "Scheduler confirmed running (PID=$NEW_PID)"
else
    log "ERROR: Scheduler exited immediately — check $LOGFILE"
    exit 1
fi
