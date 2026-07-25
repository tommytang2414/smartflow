"""Validated SEC decision pack, owner brief, M3 output and CSV contracts."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from io import StringIO
from pathlib import Path
from typing import Any

from beta_report import (
    HKT,
    LOOKBACK,
    MAX_FUTURE_SKEW,
    MAX_WINDOW_ROWS,
    REQUIRED_SOURCES,
    TRUSTED_PARSER_VERSIONS,
    BetaReportError,
    _load_health,
    _read_only_connection,
    _utc,
    _valid_sec_url,
    _validate_database,
    _validate_selected_row,
)


SCHEMA_VERSION = "smartflow-sec-owner-brief-v1"
PROMPT_VERSION = "smartflow-m3-owner-brief-v1"
MAX_PACK_BYTES = 5 * 1024 * 1024
MAX_PACK_AGE = timedelta(hours=2)
MAX_CSV_BYTES = 5 * 1024 * 1024
MAX_M3_RESPONSE_BYTES = 256 * 1024
MAX_M3_NARRATIVE_CHARS = 1_800
TOP_RESEARCH_ITEMS = 3
RESULTS = frozenset(
    {"PURCHASE_HEAVY", "SALE_HEAVY", "MIXED", "INSUFFICIENT_DATA"}
)
ACTIONS = frozenset({"NO_URGENT_ACTION", "MANUAL_REVIEW"})
PACK_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "prompt_version",
        "generated_at",
        "snapshot_at",
        "snapshot_sha256",
        "window_start",
        "window_end",
        "report_date",
        "report_id",
        "source_health",
        "summary",
        "evidence",
        "events",
    }
)
SUMMARY_KEYS = frozenset(
    {
        "result",
        "business_action",
        "purchase_count",
        "sale_count",
        "proposed_sale_count",
        "purchase_value",
        "sale_value",
        "proposed_sale_value",
        "total_disclosed_value",
        "top_evidence_concentration_pct",
        "observed_total",
        "excluded_quality",
        "excluded_parser",
        "excluded_other_form4",
    }
)
EVENT_KEYS = frozenset(
    {
        "source",
        "source_event_id",
        "accession",
        "event_type",
        "action",
        "side",
        "execution_status",
        "ticker",
        "entity_name",
        "quantity",
        "price",
        "value",
        "currency",
        "event_at",
        "filed_at",
        "observed_at",
        "parser_version",
        "quality_status",
        "raw_payload_sha256",
        "source_url",
    }
)
EVIDENCE_KEYS = frozenset(
    {
        "accession",
        "ticker",
        "action",
        "execution_status",
        "transaction_count",
        "disclosed_value",
        "currency",
        "source_url",
        "evidence_id",
    }
)
HEALTH_KEYS = frozenset(
    {
        "source",
        "state",
        "reason",
        "last_run_status",
        "last_success_at",
        "checked_at",
    }
)
FORBIDDEN_PACK_KEYS = frozenset(
    {"payload", "raw_xml", "remarks", "address", "signature", "email", "api_key"}
)
TRADE_WORDS = re.compile(r"\b(?:BUY|SELL|LONG|SHORT)\b", re.IGNORECASE)
HTML_OR_LINK = re.compile(r"<[^>]+>|https?://|www\.", re.IGNORECASE)
NUMBER_TOKEN = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:,\d{3})*(?:\.\d+)?")
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
EVIDENCE_ID = re.compile(r"^E\d{3}$")


class OwnerBriefError(BetaReportError):
    pass


class M3OutputError(OwnerBriefError):
    pass


def _iso(value: datetime) -> str:
    return _utc(value).isoformat(timespec="seconds").replace("+00:00", "Z")


def _decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise OwnerBriefError("VALUE_INVALID") from exc


def _decimal_text(value: Any) -> str | None:
    if value is None:
        return None
    amount = _decimal(value)
    return format(amount, "f")


def _text(value: Any, limit: int, *, default: str = "") -> str:
    cleaned = CONTROL_CHARS.sub("", " ".join(str(value or default).split()))
    return cleaned[:limit]


def _load_pack_rows(connection, snapshot_at: datetime) -> tuple[list[Any], dict[str, int]]:
    window_start = snapshot_at - LOOKBACK
    window_end = snapshot_at + MAX_FUTURE_SKEW
    rows = connection.execute(
        """
        SELECT
            n.source, n.source_event_id, n.event_type, n.action, n.side,
            n.execution_status, n.ticker, n.entity_name, n.quantity, n.price,
            n.value, n.currency, n.event_at, n.filed_at, n.observed_at,
            n.source_url, n.parser_version, n.quality_status, n.quality_reasons,
            r.source_event_id AS accession, r.payload_sha256
        FROM normalized_events_v2 AS n
        JOIN raw_events AS r ON r.id = n.raw_event_id
        WHERE n.source IN (?, ?) AND n.observed_at >= ? AND n.observed_at <= ?
        ORDER BY n.observed_at DESC, n.source_event_id
        """,
        (
            *REQUIRED_SOURCES,
            window_start.replace(tzinfo=None).isoformat(sep=" "),
            window_end.replace(tzinfo=None).isoformat(sep=" "),
        ),
    ).fetchall()
    if len(rows) > MAX_WINDOW_ROWS:
        raise OwnerBriefError("EVENT_VOLUME_UNBOUNDED")

    quality_valid = [row for row in rows if row["quality_status"] == "valid"]
    trusted = [
        row
        for row in quality_valid
        if row["parser_version"] == TRUSTED_PARSER_VERSIONS.get(row["source"])
    ]
    selected = []
    other_form4 = 0
    for row in trusted:
        if row["source"] == "sec_form4":
            if (
                row["event_type"] != "form4_transaction"
                or row["action"] not in {"purchase", "sale"}
            ):
                other_form4 += 1
                continue
        _validate_selected_row(row)
        selected.append(row)
    return selected, {
        "observed_total": len(rows),
        "excluded_quality": len(rows) - len(quality_valid),
        "excluded_parser": len(quality_valid) - len(trusted),
        "excluded_other_form4": other_form4,
    }


def _result(
    purchase_count: int,
    sale_count: int,
    purchase_value: Decimal,
    sale_value: Decimal,
) -> str:
    if purchase_count + sale_count == 0:
        return "INSUFFICIENT_DATA"
    if (
        purchase_count >= Decimal("1.5") * sale_count
        and purchase_value > 0
        and purchase_value >= Decimal("1.5") * sale_value
    ):
        return "PURCHASE_HEAVY"
    if (
        sale_count >= Decimal("1.5") * purchase_count
        and sale_value > 0
        and sale_value >= Decimal("1.5") * purchase_value
    ):
        return "SALE_HEAVY"
    return "MIXED"


def _build_evidence(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for event in events:
        key = (event["accession"], event["ticker"], event["action"])
        current = grouped.setdefault(
            key,
            {
                "accession": event["accession"],
                "ticker": event["ticker"],
                "action": event["action"],
                "execution_status": event["execution_status"],
                "transaction_count": 0,
                "disclosed_value": Decimal("0"),
                "currency": event["currency"],
                "source_url": event["source_url"],
            },
        )
        current["transaction_count"] += 1
        current["disclosed_value"] += _decimal(event["value"])

    ordered = sorted(
        grouped.values(),
        key=lambda item: (
            item["disclosed_value"],
            item["transaction_count"],
            item["ticker"],
            item["accession"],
        ),
        reverse=True,
    )
    evidence = []
    for index, item in enumerate(ordered, start=1):
        evidence.append(
            {
                **item,
                "evidence_id": f"E{index:03d}",
                "disclosed_value": format(item["disclosed_value"], "f"),
            }
        )
    return evidence


def build_decision_pack(
    database_path: Path,
    *,
    snapshot_at: datetime,
    generated_at: datetime,
    snapshot_sha256: str,
) -> bytes:
    snapshot_at = _utc(snapshot_at)
    generated_at = _utc(generated_at)
    if generated_at - snapshot_at > MAX_PACK_AGE or snapshot_at - generated_at > MAX_FUTURE_SKEW:
        raise OwnerBriefError("PACK_SNAPSHOT_TIME_INVALID")
    if not re.fullmatch(r"[0-9a-f]{64}", snapshot_sha256):
        raise OwnerBriefError("SNAPSHOT_HASH_INVALID")

    connection = _read_only_connection(database_path)
    try:
        _validate_database(connection)
        health_rows = _load_health(connection, snapshot_at)
        rows, excluded = _load_pack_rows(connection, snapshot_at)
    finally:
        connection.close()

    events: list[dict[str, Any]] = []
    for row in rows:
        accession = _text(row["accession"], 256)
        payload_sha256 = _text(row["payload_sha256"], 64)
        if not accession or not re.fullmatch(r"[0-9a-f]{64}", payload_sha256):
            raise OwnerBriefError("RAW_EVIDENCE_INVALID")
        events.append(
            {
                "source": row["source"],
                "source_event_id": _text(row["source_event_id"], 256),
                "accession": accession,
                "event_type": row["event_type"],
                "action": row["action"],
                "side": row["side"],
                "execution_status": row["execution_status"],
                "ticker": _text(row["ticker"], 32, default="ticker not supplied"),
                "entity_name": _text(row["entity_name"], 160, default="not supplied"),
                "quantity": _decimal_text(row["quantity"]),
                "price": _decimal_text(row["price"]),
                "value": _decimal_text(row["value"]),
                "currency": _text(row["currency"], 8, default="USD"),
                "event_at": _iso(_utc(row["event_at"])),
                "filed_at": _iso(_utc(row["filed_at"])),
                "observed_at": _iso(_utc(row["observed_at"])),
                "parser_version": row["parser_version"],
                "quality_status": row["quality_status"],
                "raw_payload_sha256": payload_sha256,
                "source_url": row["source_url"],
            }
        )

    purchases = [event for event in events if event["action"] == "purchase"]
    sales = [event for event in events if event["action"] == "sale"]
    proposed = [event for event in events if event["action"] == "proposed_sale"]
    purchase_value = sum((_decimal(event["value"]) for event in purchases), Decimal("0"))
    sale_value = sum((_decimal(event["value"]) for event in sales), Decimal("0"))
    proposed_value = sum((_decimal(event["value"]) for event in proposed), Decimal("0"))
    result = _result(len(purchases), len(sales), purchase_value, sale_value)
    action = (
        "NO_URGENT_ACTION"
        if not purchases and not sales and not proposed
        else "MANUAL_REVIEW"
    )
    evidence = _build_evidence(events)
    top_value = _decimal(evidence[0]["disclosed_value"]) if evidence else Decimal("0")
    total_value = purchase_value + sale_value + proposed_value
    concentration = (
        (top_value / total_value * Decimal("100")).quantize(Decimal("0.01"))
        if total_value > 0
        else Decimal("0")
    )
    report_date = snapshot_at.astimezone(HKT).strftime("%Y-%m-%d")
    report_id = f"SFO-{report_date}-{snapshot_sha256[:12]}"
    pack = {
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "generated_at": _iso(generated_at),
        "snapshot_at": _iso(snapshot_at),
        "snapshot_sha256": snapshot_sha256,
        "window_start": _iso(snapshot_at - LOOKBACK),
        "window_end": _iso(snapshot_at),
        "report_date": report_date,
        "report_id": report_id,
        "source_health": [
            {
                "source": row["source"],
                "state": row["state"],
                "reason": _text(row["reason"], 128),
                "last_run_status": row["last_run_status"],
                "last_success_at": _iso(_utc(row["last_success_at"])),
                "checked_at": _iso(_utc(row["checked_at"])),
            }
            for row in health_rows
        ],
        "summary": {
            "result": result,
            "business_action": action,
            "purchase_count": len(purchases),
            "sale_count": len(sales),
            "proposed_sale_count": len(proposed),
            "purchase_value": format(purchase_value, "f"),
            "sale_value": format(sale_value, "f"),
            "proposed_sale_value": format(proposed_value, "f"),
            "total_disclosed_value": format(total_value, "f"),
            "top_evidence_concentration_pct": format(concentration, "f"),
            **excluded,
        },
        "evidence": evidence,
        "events": events,
    }
    payload = json.dumps(
        pack,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(payload) > MAX_PACK_BYTES:
        raise OwnerBriefError("PACK_SIZE_INVALID")
    return payload


def pack_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _walk_forbidden(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).casefold() in FORBIDDEN_PACK_KEYS:
                raise OwnerBriefError("PACK_FORBIDDEN_FIELD")
            _walk_forbidden(nested)
    elif isinstance(value, list):
        for nested in value:
            _walk_forbidden(nested)


def _validate_pack_event(event: Any) -> None:
    if not isinstance(event, dict) or frozenset(event) != EVENT_KEYS:
        raise OwnerBriefError("PACK_EVENT_SCHEMA_INVALID")
    if not _valid_sec_url(event["source_url"]):
        raise OwnerBriefError("SOURCE_URL_INVALID")
    if event["quality_status"] != "valid":
        raise OwnerBriefError("SELECTED_EVENT_QUALITY_INVALID")
    if event["parser_version"] != TRUSTED_PARSER_VERSIONS.get(event["source"]):
        raise OwnerBriefError("PACK_PARSER_INVALID")
    if not event["accession"] or not event["source_event_id"]:
        raise OwnerBriefError("RAW_EVIDENCE_INVALID")
    if not re.fullmatch(r"[0-9a-f]{64}", event["raw_payload_sha256"]):
        raise OwnerBriefError("RAW_EVIDENCE_INVALID")
    for field in ("event_at", "filed_at", "observed_at"):
        _utc(event[field])
    for field in ("quantity", "price", "value"):
        if event[field] is not None:
            _decimal(event[field])

    if event["source"] == "sec_form4":
        expected_side = {"purchase": "BUY", "sale": "SELL"}.get(event["action"])
        if (
            event["event_type"] != "form4_transaction"
            or event["execution_status"] != "reported"
            or expected_side is None
            or event["side"] != expected_side
        ):
            raise OwnerBriefError("FORM4_SEMANTICS_INVALID")
    elif event["source"] == "sec_form144":
        if (
            event["event_type"] != "form144_notice"
            or event["action"] != "proposed_sale"
            or event["execution_status"] != "proposed"
            or event["side"] != "SELL"
        ):
            raise OwnerBriefError("FORM144_SEMANTICS_INVALID")
    else:
        raise OwnerBriefError("SOURCE_UNSUPPORTED")


def _validate_pack_derivations(pack: dict[str, Any]) -> None:
    summary = pack["summary"]
    events = pack["events"]
    if not isinstance(summary, dict) or frozenset(summary) != SUMMARY_KEYS:
        raise OwnerBriefError("PACK_SUMMARY_SCHEMA_INVALID")
    for field in (
        "purchase_count",
        "sale_count",
        "proposed_sale_count",
        "observed_total",
        "excluded_quality",
        "excluded_parser",
        "excluded_other_form4",
    ):
        if type(summary[field]) is not int or summary[field] < 0:
            raise OwnerBriefError("PACK_SUMMARY_VALUE_INVALID")

    purchases = [event for event in events if event["action"] == "purchase"]
    sales = [event for event in events if event["action"] == "sale"]
    proposed = [event for event in events if event["action"] == "proposed_sale"]
    purchase_value = sum((_decimal(event["value"]) for event in purchases), Decimal("0"))
    sale_value = sum((_decimal(event["value"]) for event in sales), Decimal("0"))
    proposed_value = sum((_decimal(event["value"]) for event in proposed), Decimal("0"))
    total_value = purchase_value + sale_value + proposed_value
    expected_evidence = _build_evidence(events)
    top_value = (
        _decimal(expected_evidence[0]["disclosed_value"])
        if expected_evidence
        else Decimal("0")
    )
    concentration = (
        (top_value / total_value * Decimal("100")).quantize(Decimal("0.01"))
        if total_value > 0
        else Decimal("0")
    )
    expected = {
        "result": _result(
            len(purchases),
            len(sales),
            purchase_value,
            sale_value,
        ),
        "business_action": (
            "NO_URGENT_ACTION"
            if not purchases and not sales and not proposed
            else "MANUAL_REVIEW"
        ),
        "purchase_count": len(purchases),
        "sale_count": len(sales),
        "proposed_sale_count": len(proposed),
        "purchase_value": format(purchase_value, "f"),
        "sale_value": format(sale_value, "f"),
        "proposed_sale_value": format(proposed_value, "f"),
        "total_disclosed_value": format(total_value, "f"),
        "top_evidence_concentration_pct": format(concentration, "f"),
    }
    if any(summary[key] != value for key, value in expected.items()):
        raise OwnerBriefError("PACK_DERIVATION_MISMATCH")
    if summary["observed_total"] < len(events) + summary["excluded_quality"]:
        raise OwnerBriefError("PACK_SUMMARY_VALUE_INVALID")
    if pack["evidence"] != expected_evidence:
        raise OwnerBriefError("PACK_EVIDENCE_MISMATCH")


def validate_decision_pack(
    payload: bytes,
    *,
    metadata: dict[str, str],
    object_last_modified: datetime,
    now: datetime,
) -> dict[str, Any]:
    if not payload or len(payload) > MAX_PACK_BYTES:
        raise OwnerBriefError("PACK_SIZE_INVALID")
    expected_hash = metadata.get("decision-pack-sha256", "")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        raise OwnerBriefError("PACK_HASH_METADATA_INVALID")
    if not hashlib.sha256(payload).hexdigest() == expected_hash:
        raise OwnerBriefError("PACK_HASH_MISMATCH")
    try:
        pack = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OwnerBriefError("PACK_JSON_INVALID") from exc
    if not isinstance(pack, dict) or frozenset(pack) != PACK_TOP_LEVEL_KEYS:
        raise OwnerBriefError("PACK_SCHEMA_INVALID")
    _walk_forbidden(pack)
    if pack["schema_version"] != SCHEMA_VERSION or pack["prompt_version"] != PROMPT_VERSION:
        raise OwnerBriefError("PACK_SCHEMA_INVALID")
    if not re.fullmatch(r"[0-9a-f]{64}", pack.get("snapshot_sha256", "")):
        raise OwnerBriefError("SNAPSHOT_HASH_INVALID")
    if metadata.get("snapshot-sha256") != pack["snapshot_sha256"]:
        raise OwnerBriefError("SNAPSHOT_HASH_MISMATCH")

    now = _utc(now)
    generated_at = _utc(pack["generated_at"])
    snapshot_at = _utc(pack["snapshot_at"])
    last_modified = _utc(object_last_modified)
    for timestamp in (generated_at, snapshot_at, last_modified):
        age = now - timestamp
        if age > MAX_PACK_AGE or age < -MAX_FUTURE_SKEW:
            raise OwnerBriefError("PACK_STALE")
    if abs((generated_at - last_modified).total_seconds()) > 10 * 60:
        raise OwnerBriefError("PACK_OBJECT_TIME_MISMATCH")
    if _utc(pack["window_end"]) != snapshot_at:
        raise OwnerBriefError("PACK_WINDOW_INVALID")
    if snapshot_at - _utc(pack["window_start"]) != LOOKBACK:
        raise OwnerBriefError("PACK_WINDOW_INVALID")
    report_date = snapshot_at.astimezone(HKT).strftime("%Y-%m-%d")
    if pack["report_date"] != report_date:
        raise OwnerBriefError("PACK_REPORT_DATE_INVALID")
    if pack["report_id"] != f"SFO-{report_date}-{pack['snapshot_sha256'][:12]}":
        raise OwnerBriefError("PACK_REPORT_ID_INVALID")

    health = pack.get("source_health")
    if (
        not isinstance(health, list)
        or any(not isinstance(row, dict) or frozenset(row) != HEALTH_KEYS for row in health)
        or {row["source"] for row in health} != set(REQUIRED_SOURCES)
    ):
        raise OwnerBriefError("SOURCE_HEALTH_MISSING")
    if any(
        row["state"] != "healthy"
        or row["last_run_status"] not in {"success", "empty"}
        for row in health
    ):
        raise OwnerBriefError("SOURCE_HEALTH_UNSAFE")
    for row in health:
        _utc(row["last_success_at"])
        _utc(row["checked_at"])
    events = pack.get("events")
    evidence = pack.get("evidence")
    if not isinstance(events, list) or len(events) > MAX_WINDOW_ROWS:
        raise OwnerBriefError("EVENT_VOLUME_UNBOUNDED")
    if not isinstance(evidence, list) or len(evidence) > MAX_WINDOW_ROWS:
        raise OwnerBriefError("PACK_SCHEMA_INVALID")
    for event in events:
        _validate_pack_event(event)
    for row in evidence:
        if not isinstance(row, dict) or frozenset(row) != EVIDENCE_KEYS:
            raise OwnerBriefError("PACK_EVIDENCE_SCHEMA_INVALID")
    _validate_pack_derivations(pack)
    if pack["summary"]["result"] not in RESULTS:
        raise OwnerBriefError("PACK_RESULT_INVALID")
    if pack["summary"]["business_action"] not in ACTIONS:
        raise OwnerBriefError("PACK_ACTION_INVALID")
    return pack


def build_m3_fact_pack(pack: dict[str, Any]) -> dict[str, Any]:
    summary = pack["summary"]
    facts = {
        "prompt_version": pack["prompt_version"],
        "report_id": pack["report_id"],
        "deterministic_result": summary["result"],
        "business_action": summary["business_action"],
        "counts": {
            "purchase": str(summary["purchase_count"]),
            "sale": str(summary["sale_count"]),
            "proposed_sale": str(summary["proposed_sale_count"]),
        },
        "disclosed_values_usd": {
            "purchase": str(summary["purchase_value"]),
            "sale": str(summary["sale_value"]),
            "proposed_sale": str(summary["proposed_sale_value"]),
            "total": str(summary["total_disclosed_value"]),
        },
        "top_evidence_concentration_pct": str(
            summary["top_evidence_concentration_pct"]
        ),
        "priority_evidence": [
            {
                "evidence_id": row["evidence_id"],
                "ticker": row["ticker"],
                "category": row["action"],
                "transaction_count": str(row["transaction_count"]),
                "disclosed_value_usd": str(row["disclosed_value"]),
                "execution_status": row["execution_status"],
            }
            for row in pack["evidence"][:TOP_RESEARCH_ITEMS]
        ],
        "limitations": [
            "SEC Form 4 coverage is limited to trusted reported P/S transactions.",
            "SEC Form 144 is proposed, not confirmed executed.",
            "Missing disclosed values are not estimated.",
            "Internal informational decision support only.",
        ],
    }
    serialized = json.dumps(facts, ensure_ascii=False, sort_keys=True)
    forbidden_values = [
        event.get("entity_name", "")
        for event in pack["events"]
        if event.get("entity_name")
    ] + [event.get("source_url", "") for event in pack["events"]]
    if any(value and value in serialized for value in forbidden_values):
        raise OwnerBriefError("M3_FACT_PACK_PRIVACY_FAILED")
    return facts


def build_m3_messages(pack: dict[str, Any]) -> list[dict[str, str]]:
    facts = build_m3_fact_pack(pack)
    system = (
        "You write a concise Traditional Chinese business-owner briefing from the "
        "provided typed facts only. Return one JSON object with exactly: headline, "
        "summary, risk_note, result, business_action, evidence_ids. Do not add facts, "
        "numbers, tickers, links, people, trading instructions or HTML. Form 144 is "
        "always proposed and not confirmed executed. In headline, summary and "
        "risk_note, do not write counts, amounts, percentages, dates or quantities; "
        "the only permitted numeral is the fixed filing name Form 144. Return raw "
        "JSON without a Markdown code fence. Do not expose reasoning."
    )
    user = json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _strip_thinking(content: str) -> str:
    text = content.strip()
    if "<think>" in text or "</think>" in text:
        match = re.fullmatch(r"\s*<think>.*?</think>\s*(\{.*\})\s*", text, re.DOTALL)
        if not match:
            raise M3OutputError("M3_REASONING_LEAK")
        text = match.group(1)
    if "<think" in text.casefold() or "</think" in text.casefold():
        raise M3OutputError("M3_REASONING_LEAK")
    fenced = re.fullmatch(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL | re.I)
    if fenced:
        text = fenced.group(1)
    if "```" in text:
        raise M3OutputError("M3_OUTPUT_JSON_INVALID")
    return text


def validate_m3_response(
    response: dict[str, Any],
    *,
    pack: dict[str, Any],
    expected_model: str,
) -> dict[str, Any]:
    if not isinstance(response, dict) or response.get("model") != expected_model:
        raise M3OutputError("M3_MODEL_MISMATCH")
    if any(
        response.get(key) not in {None, False, 0}
        for key in ("input_sensitive", "output_sensitive")
    ):
        raise M3OutputError("M3_SENSITIVE_OUTPUT")
    choices = response.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise M3OutputError("M3_RESPONSE_INVALID")
    choice = choices[0]
    if choice.get("finish_reason") != "stop":
        raise M3OutputError("M3_FINISH_INVALID")
    message = choice.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise M3OutputError("M3_RESPONSE_INVALID")
    content = _strip_thinking(message["content"])
    if len(content) > MAX_M3_NARRATIVE_CHARS:
        raise M3OutputError("M3_OUTPUT_TOO_LONG")
    try:
        output = json.loads(content)
    except json.JSONDecodeError as exc:
        raise M3OutputError("M3_OUTPUT_JSON_INVALID") from exc
    expected_keys = {
        "headline",
        "summary",
        "risk_note",
        "result",
        "business_action",
        "evidence_ids",
    }
    if not isinstance(output, dict) or set(output) != expected_keys:
        raise M3OutputError("M3_OUTPUT_SCHEMA_INVALID")
    summary = pack["summary"]
    if output["result"] != summary["result"]:
        raise M3OutputError("M3_RESULT_MISMATCH")
    if output["business_action"] != summary["business_action"]:
        raise M3OutputError("M3_ACTION_MISMATCH")
    narrative = " ".join(
        str(output[key]) for key in ("headline", "summary", "risk_note")
    )
    if len(narrative) > MAX_M3_NARRATIVE_CHARS:
        raise M3OutputError("M3_OUTPUT_TOO_LONG")
    if TRADE_WORDS.search(narrative):
        raise M3OutputError("M3_TRADE_INSTRUCTION")
    if HTML_OR_LINK.search(narrative):
        raise M3OutputError("M3_LINK_OR_HTML")
    form144_claim = re.search(r"Form\s*144(.{0,60})", narrative, re.I)
    if form144_claim:
        claim = form144_claim.group(1)
        positive_execution = re.search(
            r"executed|completed|已執行|已完成|確認成交",
            claim,
            re.I,
        )
        negated = re.search(r"\bnot\b|未|非|不", claim, re.I)
        if positive_execution and not negated:
            raise M3OutputError("M3_FORM144_EXECUTION_CLAIM")

    allowed_tickers = {
        row["ticker"] for row in pack["evidence"] if row.get("ticker")
    }
    uppercase_tokens = set(re.findall(r"\b[A-Z][A-Z0-9.-]{0,9}\b", narrative))
    harmless = {"SEC", "Form", "M3", "AI"}
    if uppercase_tokens - allowed_tickers - harmless:
        raise M3OutputError("M3_TICKER_INVENTED")

    evidence_ids = output["evidence_ids"]
    allowed_evidence = {row["evidence_id"] for row in pack["evidence"]}
    if (
        not isinstance(evidence_ids, list)
        or len(evidence_ids) > TOP_RESEARCH_ITEMS
        or any(not isinstance(item, str) or not EVIDENCE_ID.fullmatch(item) for item in evidence_ids)
        or not set(evidence_ids).issubset(allowed_evidence)
    ):
        raise M3OutputError("M3_EVIDENCE_INVALID")

    fact_json = json.dumps(build_m3_fact_pack(pack), ensure_ascii=False)
    allowed_numbers = {
        token.replace(",", "") for token in NUMBER_TOKEN.findall(fact_json)
    }
    narrative_without_ids = re.sub(r"\bE\d{3}\b", "", narrative)
    output_numbers = {
        token.replace(",", "") for token in NUMBER_TOKEN.findall(narrative_without_ids)
    }
    if not output_numbers.issubset(allowed_numbers):
        raise M3OutputError("M3_NUMBER_INVENTED")
    return output


def deterministic_narrative(pack: dict[str, Any]) -> dict[str, Any]:
    summary = pack["summary"]
    result_labels = {
        "PURCHASE_HEAVY": "申報買入在宗數及披露金額均較集中",
        "SALE_HEAVY": "申報賣出在宗數及披露金額均較集中",
        "MIXED": "申報方向未形成一致結論",
        "INSUFFICIENT_DATA": "可信 Form 4 P/S 資料不足",
    }
    return {
        "headline": result_labels[summary["result"]],
        "summary": (
            f"可信範圍包括 {summary['purchase_count']} 宗 reported purchase、"
            f"{summary['sale_count']} 宗 reported sale，以及 "
            f"{summary['proposed_sale_count']} 宗 Form 144 proposed sale。"
        ),
        "risk_note": (
            "只反映 SEC filing；缺失金額不作估算，Form 144 不代表已完成交易。"
        ),
        "result": summary["result"],
        "business_action": summary["business_action"],
        "evidence_ids": [
            row["evidence_id"] for row in pack["evidence"][:TOP_RESEARCH_ITEMS]
        ],
    }


def render_owner_email(
    pack: dict[str, Any],
    narrative: dict[str, Any],
    *,
    ai_used: bool,
    attachment_available: bool = True,
) -> tuple[str, str]:
    summary = pack["summary"]
    fallback_prefix = "" if ai_used else "[DETERMINISTIC FALLBACK]"
    subject = (
        f"{fallback_prefix}[{summary['result']}][{summary['business_action'].replace('_', ' ')}] "
        f"SmartFlow SEC Brief - {pack['report_date']}"
    )
    lines = [
        f"SmartFlow SEC Business Owner Brief — {pack['report_date']}",
        "",
        f"RESULT: {summary['result']}",
        f"BUSINESS ACTION: {summary['business_action']}",
        "",
        "今日結論",
        narrative["headline"],
        narrative["summary"],
        "",
        "主要風險",
        narrative["risk_note"],
        "",
        "優先研究項目",
    ]
    evidence_by_id = {row["evidence_id"]: row for row in pack["evidence"]}
    selected = [
        evidence_by_id[item]
        for item in narrative.get("evidence_ids", [])
        if item in evidence_by_id
    ]
    if not selected:
        lines.append("- 本時段沒有可列出的可信 filing evidence。")
    for row in selected[:TOP_RESEARCH_ITEMS]:
        category = {
            "purchase": "reported purchase",
            "sale": "reported sale",
            "proposed_sale": "proposed sale — not confirmed executed",
        }[row["action"]]
        lines.append(
            f"- {row['evidence_id']} | {row['ticker']} | {category} | "
            f"{row['transaction_count']} transaction(s) | USD {row['disclosed_value']}"
        )
        lines.append(f"  SEC evidence: {row['source_url']}")
    lines.extend(
        [
            "",
            "Coverage / limitations",
            (
                f"- trusted events: {len(pack['events'])}; excluded quality: "
                f"{summary['excluded_quality']}; superseded parser: "
                f"{summary['excluded_parser']}"
            ),
            (
                "- Form 4 only includes trusted reported P/S transactions. "
                "Form 144 is proposed, not confirmed executed."
            ),
            "- Missing disclosed values are not estimated.",
            (
                "- Deep-dive CSV attached."
                if attachment_available
                else "- Deep-dive attachment unavailable; raw evidence remains server-side."
            ),
            "",
            f"Report ID: {pack['report_id']}",
            f"Snapshot: {pack['snapshot_at']}",
            "INFORMATIONAL ONLY — NOT INVESTMENT ADVICE — NO AUTOMATED TRADING",
            "",
        ]
    )
    return subject, "\n".join(lines)


CSV_FIELDS = (
    "evidence_id",
    "accession",
    "source",
    "event_type",
    "action",
    "side",
    "execution_status",
    "ticker",
    "entity_name",
    "quantity",
    "price",
    "value",
    "currency",
    "event_at",
    "filed_at",
    "observed_at",
    "parser_version",
    "quality_status",
    "raw_payload_sha256",
    "sec_url",
)


def _csv_cell(value: Any, limit: int = 500) -> str:
    text = CONTROL_CHARS.sub("", str(value or "")).replace("\r", " ").replace("\n", " ")
    text = text[:limit]
    if text.lstrip().startswith(("=", "+", "-", "@")):
        text = "'" + text
    return text


def build_deep_dive_csv(pack: dict[str, Any]) -> bytes:
    evidence_map: dict[tuple[str, str, str], str] = {
        (row["accession"], row["ticker"], row["action"]): row["evidence_id"]
        for row in pack["evidence"]
    }
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for event in pack["events"]:
        row = {
            "evidence_id": evidence_map[
                (event["accession"], event["ticker"], event["action"])
            ],
            "accession": event["accession"],
            "source": event["source"],
            "event_type": event["event_type"],
            "action": event["action"],
            "side": event["side"],
            "execution_status": event["execution_status"],
            "ticker": event["ticker"],
            "entity_name": event["entity_name"],
            "quantity": event["quantity"],
            "price": event["price"],
            "value": event["value"],
            "currency": event["currency"],
            "event_at": event["event_at"],
            "filed_at": event["filed_at"],
            "observed_at": event["observed_at"],
            "parser_version": event["parser_version"],
            "quality_status": event["quality_status"],
            "raw_payload_sha256": event["raw_payload_sha256"],
            "sec_url": event["source_url"],
        }
        writer.writerow({key: _csv_cell(value) for key, value in row.items()})
    payload = b"\xef\xbb\xbf" + output.getvalue().encode("utf-8")
    if len(payload) > MAX_CSV_BYTES:
        raise OwnerBriefError("CSV_SIZE_INVALID")
    if b"raw_xml" in payload.lower():
        raise OwnerBriefError("CSV_RAW_XML_FORBIDDEN")
    return payload
