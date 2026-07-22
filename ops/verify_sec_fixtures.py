"""Measure parser agreement against maintained official SEC fixture expectations."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smartflow.parsers.edgar_xml import parse_form4_xml
from smartflow.parsers.form144_xml import parse_form144_xml


DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "sec" / "expectations.json"


def _read_path(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        current = current[int(part)] if isinstance(current, list) else current[part]
    if isinstance(current, datetime):
        return current.isoformat()
    return current


def verify_fixture_agreement(manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    fixtures = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = []

    for fixture in fixtures:
        xml_content = (manifest_path.parent / fixture["file"]).read_text(encoding="utf-8")
        if fixture["parser"] == "form4":
            parsed = parse_form4_xml(xml_content)
        elif fixture["parser"] == "form144":
            parsed = parse_form144_xml(xml_content, cik_ticker_cache=fixture.get("ticker_cache"))
        else:
            raise ValueError(f"unsupported parser: {fixture['parser']}")

        mismatches = []
        if parsed is None:
            mismatches.append({"path": "$", "expected": "parsed filing", "actual": None})
        else:
            for path, expected in fixture["expected"].items():
                try:
                    actual = _read_path(parsed, path)
                except (KeyError, IndexError, TypeError) as error:
                    actual = f"missing:{type(error).__name__}"
                if actual != expected:
                    mismatches.append({"path": path, "expected": expected, "actual": actual})

        results.append(
            {
                "name": fixture["name"],
                "passed": not mismatches,
                "mismatches": mismatches,
            }
        )

    passed = sum(result["passed"] for result in results)
    total = len(results)
    agreement_pct = (passed / total * 100) if total else 0.0
    return {
        "passed": passed,
        "total": total,
        "agreement_pct": agreement_pct,
        "fixtures": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--minimum", type=float, default=95.0)
    args = parser.parse_args()
    result = verify_fixture_agreement(args.manifest)
    print(json.dumps(result, indent=2))
    if result["agreement_pct"] < args.minimum:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
