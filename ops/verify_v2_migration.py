"""Apply v2 schema twice to a disposable SQLite backup and verify legacy invariants."""

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smartflow.db.v2_schema import V2_TABLES, create_v2_schema


def legacy_snapshot(connection: sqlite3.Connection) -> dict:
    rows = connection.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return {
        name: {
            "sql": sql,
            "rows": connection.execute(f'SELECT COUNT(1) FROM "{name}"').fetchone()[0],
        }
        for name, sql in rows
        if name not in V2_TABLES
    }


def verify(source_path: Path) -> dict:
    source_path = source_path.resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    file_descriptor, copy_name = tempfile.mkstemp(prefix="smartflow-v2-", suffix=".db")
    os.close(file_descriptor)
    copy_path = Path(copy_name)
    try:
        source = sqlite3.connect(f"file:{source_path.as_posix()}?mode=ro", uri=True)
        destination = sqlite3.connect(copy_path)
        try:
            source.backup(destination)
            before = legacy_snapshot(destination)
        finally:
            source.close()
            destination.close()

        engine = create_engine(f"sqlite:///{copy_path}")
        try:
            create_v2_schema(engine)
            create_v2_schema(engine)
        finally:
            engine.dispose()

        migrated = sqlite3.connect(copy_path)
        try:
            after = legacy_snapshot(migrated)
            quick_check = migrated.execute("PRAGMA quick_check").fetchone()[0]
            created_tables = {
                row[0]
                for row in migrated.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            } & V2_TABLES
        finally:
            migrated.close()

        if before != after:
            raise RuntimeError("legacy table definitions or row counts changed")
        if created_tables != V2_TABLES:
            raise RuntimeError(f"missing v2 tables: {sorted(V2_TABLES - created_tables)}")
        if quick_check != "ok":
            raise RuntimeError(f"SQLite quick_check failed: {quick_check}")

        return {
            "source": str(source_path),
            "legacy_tables_verified": len(before),
            "legacy_rows_verified": sum(item["rows"] for item in before.values()),
            "v2_tables": sorted(created_tables),
            "repeatable": True,
            "quick_check": quick_check,
        }
    finally:
        copy_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path, help="Legacy SQLite DB to copy read-only")
    args = parser.parse_args()
    print(json.dumps(verify(args.database), indent=2))


if __name__ == "__main__":
    main()
