"""Create or verify an isolated, empty SmartFlow v2 shadow database."""

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


LEGACY_DATABASE_NAME = "smartflow.db"


def _sidecars(database_path: Path) -> tuple[Path, Path]:
    return (
        database_path.with_name(f"{database_path.name}-wal"),
        database_path.with_name(f"{database_path.name}-shm"),
    )


def _validate_shadow_target(database_path: Path) -> Path:
    resolved = database_path.expanduser().resolve()
    if resolved.name.casefold() == LEGACY_DATABASE_NAME:
        raise ValueError(
            f"refusing legacy database name {LEGACY_DATABASE_NAME!r}; "
            "use an explicit shadow filename"
        )
    return resolved


def _journal_mode_from_header(database_path: Path) -> str:
    with database_path.open("rb") as database_file:
        header = database_file.read(100)
    if len(header) != 100 or not header.startswith(b"SQLite format 3\x00"):
        raise RuntimeError("target is not a valid SQLite 3 database")
    return "wal" if header[18:20] == b"\x02\x02" else "delete"


def verify_shadow_database(database_path: Path) -> dict:
    """Verify an existing shadow DB without opening it for writes."""
    resolved = _validate_shadow_target(database_path)
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    present_sidecars = [path for path in _sidecars(resolved) if path.exists()]
    if present_sidecars:
        raise RuntimeError(
            "shadow verification requires a cleanly closed database; "
            f"sidecars present: {present_sidecars}"
        )

    before_stat = resolved.stat()
    connection = sqlite3.connect(
        f"file:{resolved.as_posix()}?mode=ro&immutable=1",
        uri=True,
    )
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
        quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        row_counts = {
            table: connection.execute(f'SELECT COUNT(1) FROM "{table}"').fetchone()[0]
            for table in sorted(tables)
        }
    finally:
        connection.close()

    after_stat = resolved.stat()
    journal_mode = _journal_mode_from_header(resolved)
    if quick_check != "ok":
        raise RuntimeError(f"SQLite quick_check failed: {quick_check}")
    if tables != V2_TABLES:
        raise RuntimeError(
            "shadow schema mismatch: "
            f"missing={sorted(V2_TABLES - tables)}, extra={sorted(tables - V2_TABLES)}"
        )
    if any(row_counts.values()):
        raise RuntimeError(f"shadow database is not empty: {row_counts}")
    if journal_mode.casefold() != "wal":
        raise RuntimeError(f"shadow journal mode is {journal_mode!r}, expected 'wal'")
    if foreign_keys != 1:
        raise RuntimeError("SQLite foreign key enforcement could not be enabled")
    if (before_stat.st_size, before_stat.st_mtime_ns) != (
        after_stat.st_size,
        after_stat.st_mtime_ns,
    ):
        raise RuntimeError("read-only verification changed the database file")

    return {
        "database": str(resolved),
        "database_bytes": after_stat.st_size,
        "foreign_keys": "on",
        "journal_mode": journal_mode.casefold(),
        "quick_check": quick_check,
        "row_counts": row_counts,
        "tables": sorted(tables),
    }


def create_shadow_database(database_path: Path) -> dict:
    """Build a new v2 DB beside the target, verify it, then publish without overwrite."""
    target = _validate_shadow_target(database_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    forbidden_paths = (target, *_sidecars(target))
    existing = [path for path in forbidden_paths if path.exists() or path.is_symlink()]
    if existing:
        raise FileExistsError(f"refusing existing shadow path(s): {existing}")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.building-",
        suffix=".db",
        dir=target.parent,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    temporary_sidecars = _sidecars(temporary_path)
    try:
        connection = sqlite3.connect(temporary_path)
        try:
            journal_mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            connection.execute("PRAGMA foreign_keys=ON")
            if journal_mode.casefold() != "wal":
                raise RuntimeError(f"could not enable WAL mode: {journal_mode!r}")
        finally:
            connection.close()

        engine = create_engine(f"sqlite:///{temporary_path.as_posix()}")
        try:
            create_v2_schema(engine)
        finally:
            engine.dispose()

        checkpoint_connection = sqlite3.connect(temporary_path)
        try:
            checkpoint = checkpoint_connection.execute(
                "PRAGMA wal_checkpoint(TRUNCATE)"
            ).fetchone()
        finally:
            checkpoint_connection.close()
        if checkpoint[0] != 0:
            raise RuntimeError(f"SQLite WAL checkpoint remained busy: {checkpoint}")
        for sidecar in temporary_sidecars:
            sidecar.unlink(missing_ok=True)

        verification = verify_shadow_database(temporary_path)
        if any(path.exists() for path in temporary_sidecars):
            raise RuntimeError("SQLite WAL sidecars remain after clean shutdown")

        os.link(temporary_path, target)
        temporary_path.unlink()
        published = verify_shadow_database(target)
        published["created"] = True
        return published
    finally:
        temporary_path.unlink(missing_ok=True)
        for sidecar in temporary_sidecars:
            sidecar.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create or read-only verify an isolated SmartFlow v2 shadow DB"
    )
    parser.add_argument("action", choices=("create", "verify"))
    parser.add_argument("database", type=Path)
    args = parser.parse_args()

    if args.action == "create":
        result = create_shadow_database(args.database)
    else:
        result = verify_shadow_database(args.database)
        result["created"] = False
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
