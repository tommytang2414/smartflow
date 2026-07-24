"""Publish a consistent, verified SEC v2 snapshot to the isolated beta S3 key."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smartflow.db.snapshots import create_sqlite_snapshot, database_manifest, sha256_file


SOURCE_DATABASE = Path("/home/ubuntu/SmartFlow-shadow/data/smartflow-v2-shadow.db")
S3_BUCKET = "smartflow-tommy-db"
S3_KEY = "beta/sec-v2-shadow.db"
REQUIRED_TABLES = frozenset(
    {"raw_events", "normalized_events_v2", "collector_runs_v2", "source_health"}
)
REQUIRED_SOURCES = frozenset({"sec_form4", "sec_form144"})


def _validate_snapshot(snapshot_path: Path) -> dict:
    manifest = database_manifest(snapshot_path)
    if manifest["quick_check"] != "ok":
        raise RuntimeError("snapshot quick_check failed")
    if frozenset(manifest["row_counts"]) != REQUIRED_TABLES:
        raise RuntimeError("snapshot schema is not the isolated v2 schema")

    connection = sqlite3.connect(
        f"file:{snapshot_path.resolve().as_posix()}?mode=ro&immutable=1",
        uri=True,
    )
    try:
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise RuntimeError("snapshot foreign key check failed")
        health = connection.execute(
            "SELECT source, state, last_run_status, last_failure_kind "
            "FROM source_health ORDER BY source"
        ).fetchall()
    finally:
        connection.close()

    if frozenset(row[0] for row in health) != REQUIRED_SOURCES:
        raise RuntimeError("required SEC source health rows are missing")
    for source, state, last_run_status, last_failure_kind in health:
        if (
            state != "healthy"
            or last_run_status not in {"success", "empty"}
            or last_failure_kind is not None
        ):
            raise RuntimeError(f"{source} source health is not publishable")
    return manifest


def publish_snapshot(
    source_database: Path = SOURCE_DATABASE,
    *,
    bucket: str = S3_BUCKET,
    key: str = S3_KEY,
) -> dict:
    source_database = source_database.resolve()
    if source_database.name.casefold() == "smartflow.db":
        raise ValueError("refusing legacy smartflow.db")
    if bucket != S3_BUCKET or key != S3_KEY:
        raise ValueError("refusing unapproved S3 destination")

    with tempfile.TemporaryDirectory(prefix="smartflow-sec-beta-") as directory:
        snapshot_path = Path(directory) / "sec-v2-shadow.db"
        create_sqlite_snapshot(source_database, snapshot_path)
        manifest = _validate_snapshot(snapshot_path)
        digest = sha256_file(snapshot_path)
        snapshot_size = snapshot_path.stat().st_size
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        command = [
            "aws",
            "s3api",
            "put-object",
            "--bucket",
            bucket,
            "--key",
            key,
            "--body",
            str(snapshot_path),
            "--server-side-encryption",
            "AES256",
            "--metadata",
            f"snapshot-sha256={digest},generated-at={generated_at}",
            "--output",
            "json",
        ]
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"S3 snapshot upload failed with exit {result.returncode}")
        response = json.loads(result.stdout)

    return {
        "status": "published",
        "bucket": bucket,
        "key": key,
        "version_id": response.get("VersionId"),
        "etag": response.get("ETag"),
        "sha256": digest,
        "size_bytes": snapshot_size,
        "rows_verified": manifest["total_rows"],
        "generated_at": generated_at,
    }


def main() -> None:
    try:
        result = publish_snapshot()
    except Exception as error:
        print(
            json.dumps(
                {"status": "error", "error_code": type(error).__name__},
                sort_keys=True,
            )
        )
        raise SystemExit(1) from error
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
