#!/bin/bash
set -euo pipefail

umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DATABASE="$PROJECT_DIR/data/sfc-short-v2-shadow.db"
PYTHON="/usr/bin/python3"

test -x "$PYTHON"
cd "$PROJECT_DIR"
exec "$PYTHON" ops/run_sfc_short_shadow.py \
    --database "$DATABASE" \
    --timeout-seconds 180
