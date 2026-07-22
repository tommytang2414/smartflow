"""Print a read-only semantic audit of a legacy SmartFlow CCASS database."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smartflow.ccass_legacy_audit import audit_ccass_legacy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit_ccass_legacy(args.database), indent=2))


if __name__ == "__main__":
    main()
