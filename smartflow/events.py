"""Deterministic identity and payload helpers for normalized event ingestion."""

import hashlib
import json
from typing import Any


def make_source_event_id(source: str, *identity_parts: Any) -> str:
    """Build a stable source-scoped ID when the upstream source has no native ID."""
    normalized_source = source.strip().lower()
    if not normalized_source:
        raise ValueError("source is required")
    if not identity_parts or any(part is None or str(part).strip() == "" for part in identity_parts):
        raise ValueError("all identity parts are required")

    canonical_identity = json.dumps(
        identity_parts,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical_identity.encode("utf-8")).hexdigest()
    return f"{normalized_source}:{digest}"


def payload_sha256(payload: Any) -> str:
    """Hash JSON-compatible payloads with stable key ordering and encoding."""
    canonical_payload = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
