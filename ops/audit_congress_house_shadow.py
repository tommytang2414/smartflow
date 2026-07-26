"""Read-only operational audit for the isolated House Congress shadow DB."""

import argparse
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


EXPECTED_TABLES = {
    "collector_runs_v2",
    "normalized_events_v2",
    "raw_events",
    "source_health",
}


def audit(database_path: Path, *, since_hours: int = 24) -> dict:
    resolved = database_path.expanduser().resolve()
    if resolved.name.casefold() == "smartflow.db":
        raise ValueError("refusing legacy smartflow.db")
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    if since_hours < 1:
        raise ValueError("since_hours must be positive")

    since = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    connection = sqlite3.connect(
        f"file:{resolved.as_posix()}?mode=ro",
        uri=True,
    )
    try:
        quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
        foreign_key_failures = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        raw_count = connection.execute(
            "SELECT COUNT(*) FROM raw_events WHERE source='congress'"
        ).fetchone()[0]
        event_count = connection.execute(
            "SELECT COUNT(*) FROM normalized_events_v2 WHERE source='congress'"
        ).fetchone()[0]
        unexpected_sources = connection.execute(
            "SELECT source FROM raw_events WHERE source <> 'congress' "
            "UNION SELECT source FROM normalized_events_v2 WHERE source <> 'congress' "
            "UNION SELECT collector FROM collector_runs_v2 WHERE collector <> 'congress' "
            "UNION SELECT source FROM source_health WHERE source <> 'congress'"
        ).fetchall()
        raw_without_children = connection.execute(
            "SELECT COUNT(*) FROM raw_events AS raw "
            "WHERE raw.source='congress' AND raw.source_event_id LIKE 'house:%' "
            "AND NOT EXISTS ("
            "SELECT 1 FROM normalized_events_v2 AS event "
            "WHERE event.raw_event_id=raw.id)"
        ).fetchone()[0]
        invalid_semantics = connection.execute(
            "SELECT COUNT(*) FROM normalized_events_v2 "
            "WHERE source <> 'congress' "
            "OR parser_version NOT IN ("
            "'congress-house-ptr-v2','congress-house-ptr-v3') "
            "OR execution_status <> 'reported' "
            "OR value IS NOT NULL "
            "OR (event_type='congress_periodic_transaction' AND NOT ("
            "(action='purchase' AND side='BUY') "
            "OR (action='sale' AND side='SELL') "
            "OR (action='exchange' AND side IS NULL))) "
            "OR (event_type='congress_document_notice' AND NOT ("
            "action IN ('unparsed_document','amendment_requires_reconciliation') "
            "AND side IS NULL "
            "AND quality_status='warning')) "
            "OR event_type NOT IN ("
            "'congress_periodic_transaction','congress_document_notice')"
        ).fetchone()[0]
        outcomes = connection.execute(
            "SELECT status, COUNT(*) FROM collector_runs_v2 "
            "WHERE collector='congress' AND started_at >= ? "
            "GROUP BY status ORDER BY status",
            (since.isoformat(sep=" "),),
        ).fetchall()
        health = connection.execute(
            "SELECT state, reason, last_run_status, last_failure_kind, "
            "last_run_at, last_success_at FROM source_health "
            "WHERE source='congress'"
        ).fetchone()
        event_dates = connection.execute(
            "SELECT MIN(event_at), MAX(event_at), MIN(filed_at), MAX(filed_at) "
            "FROM normalized_events_v2 WHERE source='congress'"
        ).fetchone()
    finally:
        connection.close()

    healthy_runs = sum(
        count for status, count in outcomes if status in {"success", "empty"}
    )
    total_runs = sum(count for _, count in outcomes)
    health_result = None
    if health is not None:
        health_result = {
            "state": health[0],
            "reason": health[1],
            "last_run_status": health[2],
            "last_failure_kind": health[3],
            "last_run_at": health[4],
            "last_success_at": health[5],
        }

    release_ready = (
        quick_check == "ok"
        and not foreign_key_failures
        and tables == EXPECTED_TABLES
        and not unexpected_sources
        and raw_without_children == 0
        and invalid_semantics == 0
        and health_result is not None
        and health_result["state"] == "healthy"
        and total_runs > 0
    )
    return {
        "database": str(resolved),
        "since_hours": since_hours,
        "release_ready": release_ready,
        "quick_check": quick_check,
        "foreign_key_failures": len(foreign_key_failures),
        "schema_exact": tables == EXPECTED_TABLES,
        "unexpected_sources": [row[0] for row in unexpected_sources],
        "raw_count": raw_count,
        "event_count": event_count,
        "raw_without_normalized_children": raw_without_children,
        "invalid_semantics": invalid_semantics,
        "outcomes": dict(outcomes),
        "reliability_pct": (
            round(healthy_runs / total_runs * 100, 2) if total_runs else None
        ),
        "health": health_result,
        "event_dates": {
            "transaction_min": event_dates[0],
            "transaction_max": event_dates[1],
            "filing_min": event_dates[2],
            "filing_max": event_dates[3],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    parser.add_argument("--since-hours", type=int, default=24)
    args = parser.parse_args()
    print(json.dumps(audit(args.database, since_hours=args.since_hours), indent=2))


if __name__ == "__main__":
    main()
