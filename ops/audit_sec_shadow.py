"""Read-only operational summary for the SEC v2 shadow database."""

import argparse
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


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
        event_counts = connection.execute(
            "SELECT source, COUNT(*) FROM normalized_events_v2 "
            "GROUP BY source ORDER BY source"
        ).fetchall()
        raw_counts = connection.execute(
            "SELECT source, COUNT(*) FROM raw_events GROUP BY source ORDER BY source"
        ).fetchall()
        outcome_counts = connection.execute(
            "SELECT collector, status, COUNT(*) FROM collector_runs_v2 "
            "WHERE started_at >= ? GROUP BY collector, status ORDER BY collector, status",
            (since.isoformat(sep=" "),),
        ).fetchall()
        health = connection.execute(
            "SELECT source, state, reason, last_run_status, last_failure_kind, "
            "last_run_at, last_success_at FROM source_health ORDER BY source"
        ).fetchall()
        semantics = connection.execute(
            "SELECT source, event_type, action, COALESCE(side, 'NONE'), "
            "execution_status, COUNT(*) FROM normalized_events_v2 "
            "GROUP BY source, event_type, action, side, execution_status "
            "ORDER BY source, event_type, action, side"
        ).fetchall()
    finally:
        connection.close()

    if quick_check != "ok":
        raise RuntimeError(f"SQLite quick_check failed: {quick_check}")

    reliability = {}
    for collector, status, count in outcome_counts:
        item = reliability.setdefault(collector, {"healthy_runs": 0, "total_runs": 0})
        item["total_runs"] += count
        if status in {"success", "empty"}:
            item["healthy_runs"] += count
    for item in reliability.values():
        item["reliability_pct"] = round(
            item["healthy_runs"] / item["total_runs"] * 100,
            2,
        )

    return {
        "database": str(resolved),
        "since_hours": since_hours,
        "quick_check": quick_check,
        "raw_counts": dict(raw_counts),
        "event_counts": dict(event_counts),
        "outcome_counts": [
            {"source": source, "status": status, "count": count}
            for source, status, count in outcome_counts
        ],
        "reliability": reliability,
        "health": [
            {
                "source": row[0],
                "state": row[1],
                "reason": row[2],
                "last_run_status": row[3],
                "last_failure_kind": row[4],
                "last_run_at": row[5],
                "last_success_at": row[6],
            }
            for row in health
        ],
        "semantics": [
            {
                "source": row[0],
                "event_type": row[1],
                "action": row[2],
                "side": row[3],
                "execution_status": row[4],
                "count": row[5],
            }
            for row in semantics
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    parser.add_argument("--since-hours", type=int, default=24)
    args = parser.parse_args()
    print(json.dumps(audit(args.database, since_hours=args.since_hours), indent=2))


if __name__ == "__main__":
    main()
