"""Build a new standalone v2 database from a bounded official SFC archive range."""

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ops.manage_v2_shadow import create_shadow_database
from smartflow.db.v2_engine import open_v2_shadow_engine
from smartflow.sfc_history import SFCBackfillSummary, reprocess_sfc_short_history


def iso_date(value: str) -> date:
    return date.fromisoformat(value)


def _sidecars(database_path: Path) -> tuple[Path, Path]:
    return (
        database_path.with_name(f"{database_path.name}-wal"),
        database_path.with_name(f"{database_path.name}-shm"),
    )


def _verify_sfc_database(database_path: Path) -> dict:
    connection = sqlite3.connect(
        f"file:{database_path.resolve().as_posix()}?mode=ro&immutable=1",
        uri=True,
    )
    try:
        quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
        foreign_key_failures = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
        sources = {
            row[0]
            for row in connection.execute(
                "SELECT source FROM raw_events "
                "UNION SELECT source FROM normalized_events_v2 "
                "UNION SELECT collector FROM collector_runs_v2 "
                "UNION SELECT source FROM source_health"
            ).fetchall()
        }
        raw_count = connection.execute(
            "SELECT COUNT(*) FROM raw_events WHERE source='sfc_short'"
        ).fetchone()[0]
        event_count = connection.execute(
            "SELECT COUNT(*) FROM normalized_events_v2 WHERE source='sfc_short'"
        ).fetchone()[0]
        run_count = connection.execute(
            "SELECT COUNT(*) FROM collector_runs_v2 WHERE collector='sfc_short'"
        ).fetchone()[0]
        health = connection.execute(
            "SELECT state, last_run_status, last_failure_kind "
            "FROM source_health WHERE source='sfc_short'"
        ).fetchone()
    finally:
        connection.close()
    if quick_check != "ok" or foreign_key_failures:
        raise RuntimeError("SFC history database integrity check failed")
    if sources != {"sfc_short"}:
        raise RuntimeError(f"SFC history database source isolation failed: {sources}")
    if raw_count < 1 or event_count < 1 or run_count < 1:
        raise RuntimeError("SFC history database is unexpectedly empty")
    if (
        health is None
        or health[0] not in {"healthy", "stale"}
        or health[1:] != ("success", None)
    ):
        raise RuntimeError(f"SFC history database health is not publishable: {health}")
    return {
        "quick_check": quick_check,
        "foreign_key_failures": len(foreign_key_failures),
        "raw_count": raw_count,
        "event_count": event_count,
        "run_count": run_count,
        "health": health[0],
    }


def build_sfc_history_database(
    database: Path,
    *,
    from_date: date,
    to_date: date | None = None,
    http_session=None,
    observed_at: datetime | None = None,
) -> tuple[SFCBackfillSummary, dict]:
    """Build and verify history beside the target, then publish without overwrite."""
    target = database.expanduser().resolve()
    if target.name.casefold() == "smartflow.db":
        raise ValueError("refusing legacy smartflow.db")
    target.parent.mkdir(parents=True, exist_ok=True)
    forbidden = (target, *_sidecars(target))
    existing = [path for path in forbidden if path.exists() or path.is_symlink()]
    if existing:
        raise FileExistsError(f"refusing existing SFC history path(s): {existing}")

    descriptor, building_name = tempfile.mkstemp(
        prefix=f".{target.name}.building-",
        suffix=".db",
        dir=target.parent,
    )
    os.close(descriptor)
    building = Path(building_name)
    building.unlink()
    building_sidecars = _sidecars(building)
    owned_http_session = http_session is None
    http_session = http_session or requests.Session()
    try:
        create_shadow_database(building)
        engine = open_v2_shadow_engine(building)
        try:
            with Session(engine) as session:
                summary = reprocess_sfc_short_history(
                    session,
                    http_session=http_session,
                    from_date=from_date,
                    to_date=to_date,
                    observed_at=observed_at or datetime.now(timezone.utc),
                )
        finally:
            engine.dispose()

        checkpoint = sqlite3.connect(building)
        try:
            checkpoint_result = checkpoint.execute(
                "PRAGMA wal_checkpoint(TRUNCATE)"
            ).fetchone()
        finally:
            checkpoint.close()
        if checkpoint_result[0] != 0:
            raise RuntimeError(
                f"SQLite WAL checkpoint remained busy: {checkpoint_result}"
            )
        for sidecar in building_sidecars:
            sidecar.unlink(missing_ok=True)

        verification = _verify_sfc_database(building)
        os.link(building, target)
        building.unlink()
        return summary, verification
    finally:
        if owned_http_session:
            http_session.close()
        building.unlink(missing_ok=True)
        for sidecar in building_sidecars:
            sidecar.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--from-date", required=True, type=iso_date)
    parser.add_argument("--to-date", type=iso_date)
    args = parser.parse_args()

    database = args.database.resolve()
    summary, verification = build_sfc_history_database(
        database,
        from_date=args.from_date,
        to_date=args.to_date,
    )
    output = asdict(summary)
    output["database"] = str(database)
    output["verification"] = verification
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
