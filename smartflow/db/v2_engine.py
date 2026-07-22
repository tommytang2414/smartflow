"""Guarded SQLite engine for the isolated v2 shadow runtime."""

import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from smartflow.db.v2_schema import V2_TABLES


def open_v2_shadow_engine(database_path: Path) -> Engine:
    """Open only an existing WAL database containing exactly the v2 schema."""
    requested = database_path.expanduser()
    if requested.is_symlink():
        raise ValueError("v2 shadow database must not be a symbolic link")
    resolved = requested.resolve()
    if resolved.name.casefold() == "smartflow.db":
        raise ValueError("refusing legacy smartflow.db")
    if not resolved.is_file():
        raise FileNotFoundError(resolved)

    engine = create_engine(
        f"sqlite:///{resolved.as_posix()}",
        connect_args={"timeout": 5},
    )

    @event.listens_for(engine, "connect")
    def configure_connection(connection, _connection_record):
        cursor = connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
        finally:
            cursor.close()

    try:
        with engine.connect() as connection:
            quick_check = connection.exec_driver_sql("PRAGMA quick_check").scalar_one()
            journal_mode = connection.exec_driver_sql("PRAGMA journal_mode").scalar_one()
            foreign_keys = connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one()
            tables = {
                row[0]
                for row in connection.exec_driver_sql(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                )
            }
        if quick_check != "ok":
            raise RuntimeError(f"SQLite quick_check failed: {quick_check}")
        if str(journal_mode).casefold() != "wal":
            raise RuntimeError(f"v2 shadow database is not in WAL mode: {journal_mode}")
        if foreign_keys != 1:
            raise RuntimeError("SQLite foreign key enforcement is disabled")
        if tables != V2_TABLES:
            raise RuntimeError(
                "v2 shadow schema mismatch: "
                f"missing={sorted(V2_TABLES - tables)}, extra={sorted(tables - V2_TABLES)}"
            )
        return engine
    except Exception:
        engine.dispose()
        raise
