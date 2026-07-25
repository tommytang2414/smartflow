#!/bin/bash
set -euo pipefail

umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV="$PROJECT_DIR/.venv-congress-house"
LOCK_FILE="$SCRIPT_DIR/congress-house-runtime-requirements.txt"

test ! -e "$VENV"
/usr/bin/python3 -m venv --system-site-packages "$VENV"
"$VENV/bin/python" -m pip install \
    --disable-pip-version-check \
    --require-hashes \
    --no-deps \
    --requirement "$LOCK_FILE"
"$VENV/bin/python" - <<'PY'
from importlib.metadata import version

expected = {
    "pdfplumber": "0.11.10",
    "pdfminer.six": "20260107",
    "pypdfium2": "5.11.0",
    "Pillow": "12.2.0",
}
actual = {package: version(package) for package in expected}
if actual != expected:
    raise SystemExit(f"Congress runtime version mismatch: {actual}")

import pdfplumber
from PIL import Image
from pdfminer.high_level import extract_text
import pypdfium2

print(actual)
PY
