#!/bin/bash
set -euo pipefail

umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DATABASE="$PROJECT_DIR/data/congress-house-v2-shadow.db"
YEAR="$(date -u +%Y)"
PYTHON="$PROJECT_DIR/.venv-congress-house/bin/python"

test -x "$PYTHON"
cd "$PROJECT_DIR"
exec "$PYTHON" ops/run_congress_house_shadow.py \
    --database "$DATABASE" \
    --year "$YEAR" \
    --limit 25 \
    --timeout-seconds 300
