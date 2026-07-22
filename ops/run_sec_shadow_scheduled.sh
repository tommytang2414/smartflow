#!/bin/bash
set -euo pipefail

umask 077

SOURCE="${1:-}"
case "$SOURCE" in
    sec_form4|sec_form144) ;;
    *) echo "source must be sec_form4 or sec_form144" >&2; exit 2 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="/home/ubuntu/.config/smartflow/sec-shadow.env"
DATABASE="$PROJECT_DIR/data/smartflow-v2-shadow.db"

test -f "$ENV_FILE"
test "$(stat -c '%u' "$ENV_FILE")" = "$(id -u)"
test "$(stat -c '%a' "$ENV_FILE")" = "600"

mapfile -t ENV_LINES < <(grep -v '^[[:space:]]*$' "$ENV_FILE")
test "${#ENV_LINES[@]}" = "1"
case "${ENV_LINES[0]}" in
    SEC_EDGAR_EMAIL=*) ;;
    *) echo "SEC shadow environment file has an unexpected key" >&2; exit 2 ;;
esac
export SEC_EDGAR_EMAIL="${ENV_LINES[0]#SEC_EDGAR_EMAIL=}"

cd "$PROJECT_DIR"
exec /usr/bin/python3 ops/run_sec_shadow.py \
    --database "$DATABASE" \
    --source "$SOURCE" \
    --limit 5 \
    --timeout-seconds 240
