"""Read-only operational audit for the isolated SFC short shadow DB."""

import argparse
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse


EXPECTED_TABLES = {
    "collector_runs_v2",
    "normalized_events_v2",
    "raw_events",
    "source_health",
}


def _is_official_sfc_url(value: str | None) -> int:
    parsed = urlparse(value or "")
    hostname = (parsed.hostname or "").lower()
    return int(
        parsed.scheme == "https"
        and (hostname == "sfc.hk" or hostname.endswith(".sfc.hk"))
    )


def audit(database_path: Path, *, since_days: int = 14) -> dict:
    resolved = database_path.expanduser().resolve()
    if resolved.name.casefold() == "smartflow.db":
        raise ValueError("refusing legacy smartflow.db")
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    if since_days < 1:
        raise ValueError("since_days must be positive")

    since = datetime.now(timezone.utc) - timedelta(days=since_days)
    connection = sqlite3.connect(
        f"file:{resolved.as_posix()}?mode=ro",
        uri=True,
    )
    connection.create_function(
        "is_official_sfc_url",
        1,
        _is_official_sfc_url,
        deterministic=True,
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
            "SELECT COUNT(*) FROM raw_events WHERE source='sfc_short'"
        ).fetchone()[0]
        event_count = connection.execute(
            "SELECT COUNT(*) FROM normalized_events_v2 WHERE source='sfc_short'"
        ).fetchone()[0]
        unexpected_sources = connection.execute(
            "SELECT source FROM raw_events WHERE source <> 'sfc_short' "
            "UNION SELECT source FROM normalized_events_v2 "
            "WHERE source <> 'sfc_short' "
            "UNION SELECT collector FROM collector_runs_v2 "
            "WHERE collector <> 'sfc_short' "
            "UNION SELECT source FROM source_health WHERE source <> 'sfc_short'"
        ).fetchall()
        raw_without_children = connection.execute(
            "SELECT COUNT(*) FROM raw_events AS raw "
            "WHERE raw.source='sfc_short' "
            "AND raw.source_event_id LIKE 'sfc_short_report:%' "
            "AND NOT EXISTS ("
            "SELECT 1 FROM normalized_events_v2 AS event "
            "WHERE event.raw_event_id=raw.id)"
        ).fetchone()[0]
        rejected_raw = connection.execute(
            "SELECT COUNT(*) FROM raw_events "
            "WHERE source='sfc_short' "
            "AND source_event_id NOT LIKE 'sfc_short_report:%'"
        ).fetchone()[0]
        invalid_semantics = connection.execute(
            "SELECT COUNT(*) FROM normalized_events_v2 "
            "WHERE source <> 'sfc_short' "
            "OR parser_version <> 'sfc-short-v1' "
            "OR event_type <> 'aggregated_reportable_short_position' "
            "OR action <> 'position_snapshot' "
            "OR side <> 'SHORT' "
            "OR execution_status <> 'reported' "
            "OR market <> 'HK' "
            "OR entity_id IS NOT NULL OR entity_name IS NOT NULL "
            "OR quantity IS NULL OR quantity < 0 "
            "OR (value IS NULL AND ("
            "quality_status <> 'warning' OR NOT EXISTS ("
            "SELECT 1 FROM json_each(normalized_events_v2.quality_reasons) "
            "WHERE json_each.value='market_value_not_available'))) "
            "OR (value IS NOT NULL AND ("
            "value < 0 OR quality_status <> 'valid' "
            "OR json_array_length(quality_reasons) <> 0)) "
            "OR currency <> 'HKD' "
            "OR security_id NOT LIKE 'HKEX:%' "
            "OR ticker NOT LIKE '%.HK' "
            "OR is_official_sfc_url(source_url) <> 1"
        ).fetchone()[0]
        outcomes = connection.execute(
            "SELECT status, COUNT(*) FROM collector_runs_v2 "
            "WHERE collector='sfc_short' AND started_at >= ? "
            "GROUP BY status ORDER BY status",
            (since.isoformat(sep=" "),),
        ).fetchall()
        health = connection.execute(
            "SELECT state, reason, last_run_status, last_failure_kind, "
            "last_run_at, last_success_at, last_event_at FROM source_health "
            "WHERE source='sfc_short'"
        ).fetchone()
        event_dates = connection.execute(
            "SELECT MIN(event_at), MAX(event_at) "
            "FROM normalized_events_v2 WHERE source='sfc_short'"
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
            "last_event_at": health[6],
        }

    release_ready = (
        quick_check == "ok"
        and not foreign_key_failures
        and tables == EXPECTED_TABLES
        and not unexpected_sources
        and raw_without_children == 0
        and rejected_raw == 0
        and invalid_semantics == 0
        and health_result is not None
        and health_result["state"] == "healthy"
        and health_result["last_run_status"] in {"success", "empty"}
        and health_result["last_failure_kind"] is None
        and total_runs > 0
    )
    return {
        "database": str(resolved),
        "since_days": since_days,
        "release_ready": release_ready,
        "quick_check": quick_check,
        "foreign_key_failures": len(foreign_key_failures),
        "schema_exact": tables == EXPECTED_TABLES,
        "unexpected_sources": [row[0] for row in unexpected_sources],
        "raw_count": raw_count,
        "event_count": event_count,
        "raw_without_normalized_children": raw_without_children,
        "rejected_raw": rejected_raw,
        "invalid_semantics": invalid_semantics,
        "outcomes": dict(outcomes),
        "reliability_pct": (
            round(healthy_runs / total_runs * 100, 2) if total_runs else None
        ),
        "health": health_result,
        "reporting_dates": {
            "min": event_dates[0],
            "max": event_dates[1],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    parser.add_argument("--since-days", type=int, default=14)
    args = parser.parse_args()
    print(json.dumps(audit(args.database, since_days=args.since_days), indent=2))


if __name__ == "__main__":
    main()
