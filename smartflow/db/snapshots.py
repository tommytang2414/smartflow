"""Consistent SQLite snapshots and exact-file restore verification."""

import hashlib
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Any


def _read_only_connection(database_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{database_path.resolve().as_posix()}?mode=ro", uri=True)


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def database_manifest(database_path: Path) -> dict[str, Any]:
    connection = _read_only_connection(database_path)
    try:
        quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
        schema = connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()
        tables = [row[1] for row in schema if row[0] == "table"]
        row_counts = {
            table: connection.execute(
                f"SELECT COUNT(1) FROM {_quote_identifier(table)}"
            ).fetchone()[0]
            for table in tables
        }
        return {
            "quick_check": quick_check,
            "schema": schema,
            "row_counts": row_counts,
            "total_rows": sum(row_counts.values()),
        }
    finally:
        connection.close()


def create_sqlite_snapshot(source_path: Path, snapshot_path: Path) -> None:
    source_path = source_path.resolve()
    snapshot_path = snapshot_path.resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if snapshot_path.exists():
        raise FileExistsError(snapshot_path)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)

    source = _read_only_connection(source_path)
    destination = sqlite3.connect(snapshot_path)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()


def restore_sqlite_snapshot(snapshot_path: Path, restore_path: Path) -> None:
    snapshot_path = snapshot_path.resolve()
    restore_path = restore_path.resolve()
    if not snapshot_path.is_file():
        raise FileNotFoundError(snapshot_path)
    if restore_path.exists():
        raise FileExistsError(restore_path)
    restore_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(snapshot_path, restore_path)


def rehearse_snapshot_restore(source_path: Path) -> dict[str, Any]:
    source_path = source_path.resolve()
    source_manifest = database_manifest(source_path)
    if source_manifest["quick_check"] != "ok":
        raise RuntimeError(f"source quick_check failed: {source_manifest['quick_check']}")

    with tempfile.TemporaryDirectory(prefix="smartflow-restore-") as temporary_directory:
        temporary_path = Path(temporary_directory)
        snapshot_path = temporary_path / "snapshot.db"
        restore_path = temporary_path / "restored.db"
        create_sqlite_snapshot(source_path, snapshot_path)
        restore_sqlite_snapshot(snapshot_path, restore_path)

        snapshot_manifest = database_manifest(snapshot_path)
        restore_manifest = database_manifest(restore_path)
        snapshot_sha256 = sha256_file(snapshot_path)
        restore_sha256 = sha256_file(restore_path)

        if snapshot_manifest != source_manifest:
            raise RuntimeError("snapshot schema, row counts, or quick_check differ from source")
        if restore_manifest != snapshot_manifest:
            raise RuntimeError("restored database differs logically from snapshot")
        if restore_sha256 != snapshot_sha256:
            raise RuntimeError("restored database bytes differ from snapshot")

        return {
            "source": str(source_path),
            "source_size_bytes": source_path.stat().st_size,
            "snapshot_size_bytes": snapshot_path.stat().st_size,
            "tables_verified": len(source_manifest["row_counts"]),
            "rows_verified": source_manifest["total_rows"],
            "quick_check": restore_manifest["quick_check"],
            "snapshot_sha256": snapshot_sha256,
            "restore_sha256": restore_sha256,
            "byte_identical_restore": True,
        }
