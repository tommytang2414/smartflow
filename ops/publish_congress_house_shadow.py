"""Publish a verified House Congress shadow snapshot to exact S3 paths."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from smartflow.db.snapshots import create_sqlite_snapshot, database_manifest, sha256_file


SOURCE_DATABASE = Path(
    "/home/ubuntu/SmartFlow-shadow/data/congress-house-v2-shadow.db"
)
S3_BUCKET = "smartflow-tommy-db"
S3_KEY = "beta/congress-house-v2-shadow.db"
ARCHIVE_PREFIX = "snapshots/congress-house-v2"
HKT = timezone(timedelta(hours=8), name="HKT")
REQUIRED_TABLES = frozenset(
    {"raw_events", "normalized_events_v2", "collector_runs_v2", "source_health"}
)
MAX_SNAPSHOT_BYTES = 512 * 1024 * 1024


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
        source_rows = connection.execute(
            "SELECT source FROM raw_events "
            "UNION SELECT source FROM normalized_events_v2 "
            "UNION SELECT collector FROM collector_runs_v2 "
            "UNION SELECT source FROM source_health"
        ).fetchall()
        health = connection.execute(
            "SELECT state, last_run_status, last_failure_kind "
            "FROM source_health WHERE source='congress'"
        ).fetchone()
    finally:
        connection.close()

    if {row[0] for row in source_rows} != {"congress"}:
        raise RuntimeError("snapshot is not isolated to Congress")
    if (
        health is None
        or health[0] != "healthy"
        or health[1] not in {"success", "empty"}
        or health[2] is not None
    ):
        raise RuntimeError("Congress source health is not publishable")
    return manifest


def _put_object(
    *,
    bucket: str,
    key: str,
    body: Path,
    metadata: str,
    if_none_match: bool = False,
) -> dict:
    command = [
        "aws",
        "s3api",
        "put-object",
        "--bucket",
        bucket,
        "--key",
        key,
        "--body",
        str(body),
        "--server-side-encryption",
        "AES256",
        "--metadata",
        metadata,
    ]
    if if_none_match:
        command.extend(["--if-none-match", "*"])
    command.extend(["--output", "json"])
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        if if_none_match and "PreconditionFailed" in result.stderr:
            return {"status": "already_exists"}
        raise RuntimeError(
            f"S3 upload failed for approved object with exit {result.returncode}"
        )
    response = json.loads(result.stdout)
    return {
        "status": "uploaded",
        "version_id": response.get("VersionId"),
        "etag": response.get("ETag"),
    }


def publish_snapshot(
    source_database: Path = SOURCE_DATABASE,
    *,
    bucket: str = S3_BUCKET,
    key: str = S3_KEY,
    now: datetime | None = None,
) -> dict:
    source_database = source_database.resolve()
    if source_database.name.casefold() == "smartflow.db":
        raise ValueError("refusing legacy smartflow.db")
    if bucket != S3_BUCKET or key != S3_KEY:
        raise ValueError("refusing unapproved S3 destination")
    generated_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    with tempfile.TemporaryDirectory(prefix="smartflow-congress-house-") as directory:
        snapshot_path = Path(directory) / "congress-house-v2-shadow.db"
        create_sqlite_snapshot(source_database, snapshot_path)
        manifest = _validate_snapshot(snapshot_path)
        digest = sha256_file(snapshot_path)
        size_bytes = snapshot_path.stat().st_size
        if size_bytes > MAX_SNAPSHOT_BYTES:
            raise RuntimeError("Congress snapshot exceeds the approved size limit")
        generated_text = generated_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        response = _put_object(
            bucket=bucket,
            key=key,
            body=snapshot_path,
            metadata=f"snapshot-sha256={digest},generated-at={generated_text}",
        )

        archive = None
        hkt_date = generated_at.astimezone(HKT)
        if hkt_date.day == 1:
            archive_key = (
                f"{ARCHIVE_PREFIX}/{hkt_date:%Y/%m}/"
                f"congress-house-v2-shadow-{hkt_date:%Y%m%d}.db"
            )
            archive = {
                "key": archive_key,
                **_put_object(
                    bucket=bucket,
                    key=archive_key,
                    body=snapshot_path,
                    metadata=(
                        f"snapshot-sha256={digest},generated-at={generated_text},"
                        "retention-class=monthly-append-only"
                    ),
                    if_none_match=True,
                ),
            }

    return {
        "status": "published",
        "bucket": bucket,
        "key": key,
        "version_id": response.get("version_id"),
        "etag": response.get("etag"),
        "sha256": digest,
        "size_bytes": size_bytes,
        "rows_verified": manifest["total_rows"],
        "generated_at": generated_text,
        "archive": archive,
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
