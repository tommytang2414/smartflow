"""Read-only coverage audit between legacy SFC storage and rebuilt v2 evidence."""

import json
import sqlite3
from pathlib import Path
from typing import Any


def _readonly_connection(path: Path) -> sqlite3.Connection:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True)


def audit_sfc_legacy_against_v2(
    legacy_database: Path,
    v2_database: Path,
) -> dict[str, Any]:
    """Report coverage only; legacy turnover-shaped rows are not convertible."""
    legacy = _readonly_connection(legacy_database)
    v2 = _readonly_connection(v2_database)
    try:
        legacy_tables = {
            row[0]
            for row in legacy.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if "sfc_short_data" not in legacy_tables:
            legacy_rows = []
        else:
            legacy_rows = legacy.execute(
                "SELECT week_end_date, raw_data FROM sfc_short_data ORDER BY week_end_date"
            ).fetchall()

        legacy_record_count = 0
        legacy_keys: set[str] = set()
        for _, raw_data in legacy_rows:
            records = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
            for record in records or []:
                legacy_record_count += 1
                legacy_keys.update(record)

        v2_tables = {
            row[0]
            for row in v2.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        required_v2 = {"raw_events", "normalized_events_v2"}
        if not required_v2.issubset(v2_tables):
            raise ValueError("v2 database does not contain the SFC evidence tables")

        raw_payloads = v2.execute(
            "SELECT payload FROM raw_events WHERE source = 'sfc_short'"
        ).fetchall()
        official_raw_reports = 0
        for (payload,) in raw_payloads:
            parsed_payload = json.loads(payload) if isinstance(payload, str) else payload
            if parsed_payload.get("content_type") == "text/csv":
                official_raw_reports += 1

        v2_row = v2.execute(
            "SELECT COUNT(*), MIN(event_at), MAX(event_at) "
            "FROM normalized_events_v2 WHERE source = 'sfc_short'"
        ).fetchone()
        v2_dates = v2.execute(
            "SELECT DISTINCT substr(event_at, 1, 10) "
            "FROM normalized_events_v2 WHERE source = 'sfc_short' ORDER BY 1"
        ).fetchall()

        return {
            "legacy_database": str(legacy_database.resolve()),
            "v2_database": str(v2_database.resolve()),
            "legacy_weeks": len(legacy_rows),
            "legacy_records": legacy_record_count,
            "legacy_date_range": [
                legacy_rows[0][0] if legacy_rows else None,
                legacy_rows[-1][0] if legacy_rows else None,
            ],
            "legacy_record_fields": sorted(legacy_keys),
            "official_raw_reports": official_raw_reports,
            "v2_weeks": len(v2_dates),
            "v2_events": v2_row[0],
            "v2_date_range": [
                v2_dates[0][0] if v2_dates else None,
                v2_dates[-1][0] if v2_dates else None,
            ],
            "status": (
                "no_legacy_history"
                if not legacy_rows
                else "legacy_not_semantically_comparable"
            ),
            "numeric_reconciliation_performed": False,
            "reason": (
                "legacy SFC table contains no rows"
                if not legacy_rows
                else "legacy fields describe inferred turnover percentages, not official aggregate positions"
            ),
        }
    finally:
        legacy.close()
        v2.close()
