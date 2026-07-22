"""Print a read-only legacy-versus-v2 SFC coverage audit."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smartflow.sfc_legacy_audit import audit_sfc_legacy_against_v2


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy-database", required=True, type=Path)
    parser.add_argument("--v2-database", required=True, type=Path)
    args = parser.parse_args()
    result = audit_sfc_legacy_against_v2(
        args.legacy_database,
        args.v2_database,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
