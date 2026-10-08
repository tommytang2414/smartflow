from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .common import canonical, digest, file_hash, read_json, readonly, stamp, utc, write_json
from .store import ResearchStore


BUCKET = "smartflow-tommy-db"
KEYS = {
    "sec": "beta/sec-v2-shadow.db",
    "house": "beta/congress-house-v2-shadow.db",
    "sfc": "beta/sfc-short-v2-shadow.db",
}
SOURCES = {"sec": {"sec_form4", "sec_form144"}, "house": {"congress"}, "sfc": {"sfc_short"}}
TABLES = {"raw_events", "normalized_events_v2", "collector_runs_v2", "source_health"}
MAX_BYTES = 512 * 1024 * 1024


def sync_aws(destination: Path) -> dict:
    """Uses existing operator auth; never installs credentials or modifies S3."""
    destination.mkdir(parents=True, exist_ok=True)
    results = {}
    for group, key in KEYS.items():
        head = subprocess.run(["aws", "s3api", "head-object", "--bucket", BUCKET, "--key", key, "--output", "json"],
                              check=True, capture_output=True, text=True, timeout=60)
        metadata = json.loads(head.stdout)
        version = metadata.get("VersionId")
        if not version or version == "null":
            raise ValueError("versioned_snapshot_required")
        manifest = {"bucket": BUCKET, "key": key, "version_id": version,
                    "sha256": metadata["Metadata"]["snapshot-sha256"],
                    "generated_at": metadata["Metadata"]["generated-at"], "size_bytes": metadata["ContentLength"]}
        if not 0 < manifest["size_bytes"] <= MAX_BYTES:
            raise ValueError("snapshot_size_limit")
        target = destination / (group + "-" + manifest["sha256"] + ".db")
        if target.exists():
            if file_hash(target) != manifest["sha256"]:
                raise ValueError("existing_cache_hash_conflict")
        else:
            with tempfile.TemporaryDirectory(prefix="download-", dir=destination) as folder:
                temporary = Path(folder) / "snapshot.db"
                subprocess.run(["aws", "s3api", "get-object", "--bucket", BUCKET, "--key", key,
                                "--version-id", version, str(temporary), "--output", "json"],
                               check=True, capture_output=True, timeout=180)
                if temporary.stat().st_size != manifest["size_bytes"] or file_hash(temporary) != manifest["sha256"]:
                    raise ValueError("snapshot_download_hash_mismatch")
                temporary.replace(target)
        manifest["file"] = target.name
        write_json(destination / (group + "-manifest.json"), manifest)
        results[group] = manifest
    return results


def import_snapshot(store: ResearchStore, group: str, path: Path, manifest: dict,
                    *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if group not in KEYS or manifest.get("bucket") != BUCKET or manifest.get("key") != KEYS[group]:
        raise ValueError("snapshot_destination_not_allowlisted")
    if not manifest.get("version_id") or manifest["version_id"] == "null":
        raise ValueError("snapshot_version_missing")
    expected = manifest.get("sha256", "")
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("snapshot_digest_invalid")
    if path.name.lower() == "smartflow.db" or not 0 < path.stat().st_size <= MAX_BYTES:
        raise ValueError("invalid_snapshot_file")
    if path.stat().st_size != manifest["size_bytes"] or file_hash(path) != expected:
        raise ValueError("snapshot_hash_mismatch")
    generated = utc(manifest["generated_at"])
    if generated > now + timedelta(minutes=5):
        raise ValueError("snapshot_from_future")
    identity = digest(canonical([group, manifest["version_id"], expected]))
    old = store.db.execute("SELECT manifest FROM imports WHERE identity=?", (identity,)).fetchone()
    if old:
        if read_json_value(old[0]) != manifest:
            raise ValueError("snapshot_manifest_conflict")
        return {"status": "already_imported", "import_id": identity, "inserted": 0}
    cache = store.root / "snapshots" / (expected + ".db")
    cache.parent.mkdir(exist_ok=True)
    if not cache.exists():
        with tempfile.TemporaryDirectory(prefix="import-", dir=cache.parent) as folder:
            temporary = Path(folder) / "snapshot.db"
            shutil.copyfile(path, temporary)
            if file_hash(temporary) != expected:
                raise ValueError("snapshot_changed_during_copy")
            temporary.replace(cache)
    elif file_hash(cache) != expected:
        raise ValueError("cache_hash_conflict")
    connection = readonly(cache)
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if tables != TABLES or connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("snapshot_schema_or_integrity")
        if connection.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("snapshot_foreign_keys")
        actual = {row[0] for row in connection.execute("SELECT source FROM raw_events UNION SELECT source FROM normalized_events_v2 UNION SELECT collector FROM collector_runs_v2 UNION SELECT source FROM source_health")}
        if actual != SOURCES[group]:
            raise ValueError("snapshot_source_contamination")
        health = [dict(row) for row in connection.execute("SELECT * FROM source_health")]
        for row in health:
            for field in ("checked_at", "last_run_at", "last_success_at"):
                if row[field] and utc(row[field]) > generated + timedelta(minutes=5):
                    raise ValueError("health_timestamp_from_future")
        parents = {}
        inserted = 0
        with store.db:
            for row in connection.execute("SELECT id,source,source_event_id,payload,payload_sha256 FROM raw_events"):
                if digest(canonical(json.loads(row["payload"]))) != row["payload_sha256"]:
                    raise ValueError("raw_payload_hash_mismatch")
                key = canonical([row["source"], row["source_event_id"]]).decode()
                parents[row["id"]] = (row["source"], row["source_event_id"], row["payload_sha256"])
                previous = store.db.execute("SELECT payload_hash FROM raw_evidence WHERE identity=?", (key,)).fetchone()
                if previous and previous[0] != row["payload_sha256"]:
                    raise ValueError("immutable_raw_identity_conflict")
                store.db.execute("INSERT OR IGNORE INTO raw_evidence VALUES(?,?)", (key, row["payload_sha256"]))
            # SQLite NUMERIC affinity is read as TEXT; never introduce a Python float.
            for row in connection.execute("SELECT *,CAST(quantity AS TEXT) AS exact_quantity,CAST(price AS TEXT) AS exact_price,CAST(value AS TEXT) AS exact_value FROM normalized_events_v2"):
                body = dict(row)
                parent = parents.get(body["raw_event_id"])
                if not parent or parent[0] != body["source"]:
                    raise ValueError("normalized_parent_source_mismatch")
                for field in ("entities", "attributes", "quality_reasons"):
                    body[field] = json.loads(body[field]) if body[field] else ([] if field != "attributes" else {})
                for field in ("quantity", "price", "value"):
                    body[field] = body.pop("exact_" + field)
                body.pop("id")
                body.pop("raw_event_id")
                body["raw_identity"] = parent[1]
                body["raw_hash"] = parent[2]
                evidence_id = "E" + digest(canonical([body["source"], body["source_event_id"], body["parser_version"]]))[:24]
                fingerprint = digest(canonical(body))
                previous = store.db.execute("SELECT fingerprint FROM evidence WHERE id=?", (evidence_id,)).fetchone()
                if previous and previous[0] != fingerprint:
                    raise ValueError("immutable_normalized_identity_conflict")
                if not previous:
                    store.db.execute("INSERT INTO evidence VALUES(?,?,?,?,?,?,?)", (evidence_id, body["source"], body["source_event_id"], body["parser_version"], fingerprint, canonical(body).decode(), stamp(now)))
                    inserted += 1
            store.db.execute("INSERT INTO imports VALUES(?,?,?,?)", (identity, group, canonical(manifest).decode(), stamp(now)))
            for row in health:
                previous = store.db.execute("SELECT generated_at FROM source_state WHERE source=?", (row["source"],)).fetchone()
                if previous and utc(previous[0]) > generated:
                    continue
                store.db.execute("INSERT OR REPLACE INTO source_state VALUES(?,?,?,?)", (row["source"], identity, canonical(row).decode(), stamp(generated)))
        return {"status": "imported", "import_id": identity, "inserted": inserted, "raw_parents": len(parents)}
    finally:
        connection.close()


def read_json_value(value: str) -> Any:
    return json.loads(value)
