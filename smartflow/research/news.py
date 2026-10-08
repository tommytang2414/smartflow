from __future__ import annotations

import json
from email.utils import parsedate_to_datetime
from pathlib import Path

from .common import beneath, digest, file_hash, read_json, readonly, utc, stamp


def publication_time(value: str | None):
    if not value:
        return None
    try:
        return utc(value)
    except ValueError:
        try:
            return utc(parsedate_to_datetime(value))
        except (TypeError, ValueError):
            return None


def import_news(root: Path, definitions: list[dict], as_of, cache: Path | None = None) -> dict:
    """Read direct SQL and immutable files; never use newsroom Store/history CLI."""
    root = root.resolve()
    connection = readonly(root / "newsroom.sqlite3")
    selected = {item["security_key"]: [] for item in definitions}
    counts = {"verified_originals": 0, "trusted_publications": 0, "excluded_legacy_or_unpinned": 0}
    try:
        connection.execute("BEGIN")
        documents = []
        for row in connection.execute("SELECT * FROM documents ORDER BY retrieved_at DESC,id DESC"):
            published = publication_time(row["published_at"])
            if utc(row["retrieved_at"]) > as_of or (published and published > as_of):
                continue
            document = dict(row)
            document["published_at_raw"] = row["published_at"]
            document["published_at"] = stamp(published) if published else None
            documents.append(document)
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        publications = [dict(row) for row in connection.execute("SELECT * FROM publications ORDER BY sent_at DESC") if utc(row["sent_at"]) <= as_of] if "publications" in tables else []
        for publication in publications:
            if not {"submission_integrity", "editorial_reviews"} <= tables:
                counts["excluded_legacy_or_unpinned"] += 1
                continue
            identity = publication["analysis_hash"]
            pin = connection.execute("SELECT * FROM submission_integrity WHERE analysis_hash=?", (identity,)).fetchone()
            review = connection.execute("SELECT * FROM editorial_reviews WHERE analysis_hash=?", (identity,)).fetchone()
            if not pin or not review:
                counts["excluded_legacy_or_unpinned"] += 1
                continue
            directory = beneath(root, publication["directory"])
            if pin["directory"] != publication["directory"] or review["directory"] != publication["directory"]:
                raise ValueError("news_publication_directory_mismatch")
            manifest_path = beneath(directory, "submission-manifest.json")
            manifest_bytes = manifest_path.read_bytes()
            if digest(manifest_bytes) != pin["manifest_hash"]:
                raise ValueError("news_manifest_pin_mismatch")
            manifest = json.loads(manifest_bytes)
            packet = read_json(beneath(directory, "packet-manifest.json"))
            if packet.get("delivery_version") != 1:
                counts["excluded_legacy_or_unpinned"] += 1
                continue
            required = {"analysis.json", "packet-manifest.json", "PACKET.md", "DIGEST.md", "RESEARCH_LEDGER.md",
                        "EMAIL.txt", "EMAIL.html", "email-subject.json", "mechanical-validation.json", "source-health.json", "analyst-notes.md", "BETA_REPORT.md"}
            required.update("sources/" + name for name in packet["source_files"])
            if set(manifest["files"]) != required:
                raise ValueError("news_frozen_artifact_set_mismatch")
            analysis_bytes = beneath(directory, "analysis.json").read_bytes()
            if manifest["analysis_hash"] != identity or digest(analysis_bytes) != identity:
                raise ValueError("news_analysis_identity_mismatch")
            for relative, metadata in manifest["files"].items():
                artifact = beneath(directory, relative)
                expected = metadata["sha256"] if isinstance(metadata, dict) else metadata
                if file_hash(artifact) != expected:
                    raise ValueError("news_artifact_hash_mismatch")
            record_path = beneath(directory, "review-record.json")
            record_bytes = record_path.read_bytes()
            record = json.loads(record_bytes)
            if not (digest(record_bytes) == review["record_hash"] and record["analysis_sha256"] == identity
                    and record.get("submission_manifest_sha256") == pin["manifest_hash"]
                    and record["verdict"] == review["verdict"] == "PASS_WITH_LIMITATIONS"):
                raise ValueError("news_formal_review_binding_mismatch")
            json.loads(analysis_bytes)
            counts["trusted_publications"] += 1
        for document in documents:
            text_path = beneath(root, document["text_path"])
            if text_path.stat().st_size > 2 * 1024 * 1024:
                continue
            text_bytes = text_path.read_bytes()
            text = text_bytes.decode("utf-8")
            matches = [item for item in definitions if item["company_terms"] and any(term.casefold() in (document["title"] + "\n" + text).casefold() for term in item["company_terms"])]
            if not matches:
                continue
            raw_path = beneath(root, document["raw_path"])
            if raw_path.stat().st_size > 32 * 1024 * 1024:
                continue
            raw_bytes = raw_path.read_bytes()
            if digest(text_bytes) != document["text_hash"] or digest(raw_bytes) != document["raw_hash"]:
                raise ValueError("news_original_hash_mismatch")
            counts["verified_originals"] += 1
            for item in matches:
                if len(selected[item["security_key"]]) >= 2:
                    continue
                if cache:
                    cache.mkdir(parents=True, exist_ok=True)
                    for contents, expected, suffix in ((text_bytes, document["text_hash"], ".txt"), (raw_bytes, document["raw_hash"], ".raw")):
                        target = cache / (expected + suffix)
                        if target.exists():
                            if file_hash(target) != expected:
                                raise ValueError("news_cache_identity_conflict")
                        else:
                            temporary = target.with_suffix(suffix + ".tmp")
                            temporary.write_bytes(contents)
                            temporary.replace(target)
                term = next(term for term in item["company_terms"] if term.casefold() in (document["title"] + "\n" + text).casefold())
                position = text.casefold().find(term.casefold())
                excerpt = text[max(position - 120, 0):max(position - 120, 0) + 500] if position >= 0 else text[:500]
                selected[item["security_key"]].append({"id": "N" + digest((str(document["id"]) + document["text_hash"]).encode())[:24],
                    "kind": "primary_original", "origin": "hk-civic-newsroom", "document_id": document["id"],
                    "title": document["title"], "url": document["url"], "raw_hash": document["raw_hash"], "text_hash": document["text_hash"],
                    "published_at": document["published_at"], "retrieved_at": document["retrieved_at"], "public_available_at": None,
                    "excerpt": excerpt, "relevance": "keyword_candidate_requires_review", "page": None})
        # Phase 1 only supplies verified originals to the model. Existing secondary
        # review integrity is audited, but its conclusions require a fuller quote adapter.
        connection.rollback()
        return {"by_security": selected, "coverage": {"status": "VERIFIED_READ_ONLY_IMPORT", **counts,
                    "us_issuer_macro": "NOT_COVERED", "history_links": "NOT_IMPORTED_HYPOTHESES_ONLY"}}
    finally:
        connection.close()
