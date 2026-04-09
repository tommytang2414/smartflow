#!/bin/bash
# SmartFlow VPS Runner — runs the full collector suite
# Usage: ./smartflow_vps.sh

export PATH=$HOME/.local/bin:$PATH
export PYTHONIOENCODING=utf-8

cd ~/SmartFlow

LOGFILE="logs/smartflow_$(date +%Y%m%d_%H%M%S).log"

echo "[$(date)] SmartFlow collection starting..." >> $LOGFILE
python3 -m smartflow schedule --all >> $LOGFILE 2>&1 &
echo "[$(date)] SmartFlow started in background, PID=$!" >> $LOGFILE
