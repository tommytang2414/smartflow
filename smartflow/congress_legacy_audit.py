"""Read-only audit of legacy Congress identity and amount semantics."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path


def audit_congress_legacy(database_path: Path) -> dict:
    path = database_path.resolve()
    connection = sqlite3.connect(
        f"file:{path.as_posix()}?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if "smart_money_signals" not in tables:
            raise ValueError("legacy database has no smart_money_signals table")
        rows = connection.execute(
            """
            SELECT source_id, ticker, entity_name, direction, value_usd,
                   traded_at, filed_at, raw_data
            FROM smart_money_signals
            WHERE source = 'congress'
            ORDER BY id
            """
        ).fetchall()
    finally:
        connection.close()

    directions: dict[str, int] = {}
    upstream_sources: dict[str, int] = {}
    missing_ticker = 0
    range_disclosures = 0
    range_value_lower_bounds = 0
    range_value_midpoints = 0
    non_report_row_identity = 0
    first_transaction_at = None
    last_transaction_at = None
    for row in rows:
        direction = str(row["direction"] or "UNKNOWN")
        directions[direction] = directions.get(direction, 0) + 1
        if not str(row["ticker"] or "").strip():
            missing_ticker += 1
        source_id = str(row["source_id"] or "")
        if source_id.startswith("congress_"):
            non_report_row_identity += 1
        raw = {}
        try:
            raw = json.loads(row["raw_data"] or "{}")
        except json.JSONDecodeError:
            raw = {}
        upstream = str(
            raw.get("source")
            or (
                "unspecified_legacy_api"
                if raw.get("amount_range")
                else "unknown"
            )
        )
        upstream_sources[upstream] = upstream_sources.get(upstream, 0) + 1
        amount = str(raw.get("amount_range") or raw.get("amount_str") or "")
        match = re.fullmatch(
            r"\$?([\d,]+(?:\.\d+)?)\s*-\s*\$?([\d,]+(?:\.\d+)?)",
            amount,
        )
        if match:
            range_disclosures += 1
            lower = float(match.group(1).replace(",", ""))
            upper = float(match.group(2).replace(",", ""))
            stored_value = float(row["value_usd"] or 0)
            if stored_value == lower:
                range_value_lower_bounds += 1
            if stored_value == (lower + upper) / 2:
                range_value_midpoints += 1
        transaction_at = row["traded_at"]
        if transaction_at:
            first_transaction_at = min(
                value for value in (first_transaction_at, transaction_at) if value
            )
            last_transaction_at = max(
                value for value in (last_transaction_at, transaction_at) if value
            )

    return {
        "rows": len(rows),
        "directions": dict(sorted(directions.items())),
        "upstream_sources": dict(sorted(upstream_sources.items())),
        "missing_ticker_rows": missing_ticker,
        "range_disclosure_rows": range_disclosures,
        "range_value_lower_bound_rows": range_value_lower_bounds,
        "range_value_midpoint_rows": range_value_midpoints,
        "non_report_row_identity_rows": non_report_row_identity,
        "official_report_row_traceable": 0,
        "first_transaction_at": first_transaction_at,
        "last_transaction_at": last_transaction_at,
        "status": "legacy_identity_and_amount_semantics_unsupported",
        "treatment": (
            "retain as audit history; rebuild from official report evidence; "
            "do not migrate derived range values or legacy source IDs as ground truth"
        ),
    }
