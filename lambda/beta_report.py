"""Deterministic, non-directional SEC beta report renderer."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit


REQUIRED_TABLES = frozenset(
    {"raw_events", "normalized_events_v2", "collector_runs_v2", "source_health"}
)
REQUIRED_SOURCES = ("sec_form4", "sec_form144")
MAX_SNAPSHOT_AGE = timedelta(hours=26)
MAX_FUTURE_SKEW = timedelta(minutes=5)
LOOKBACK = timedelta(hours=24)
MAX_WINDOW_ROWS = 5_000
MAX_ITEMS_PER_CATEGORY = 20
HKT = timezone(timedelta(hours=8), name="HKT")
TRUSTED_PARSER_VERSIONS = {
    "sec_form4": "sec-form4-v4",
    "sec_form144": "sec-form144-v1",
}


class BetaReportError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class BetaReport:
    report_date: str
    body: str


def _utc(value: datetime | str | None) -> datetime:
    if value is None:
        raise BetaReportError("TIMESTAMP_MISSING")
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise BetaReportError("TIMESTAMP_INVALID") from exc
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _read_only_connection(database_path: Path) -> sqlite3.Connection:
    if not database_path.is_file():
        raise BetaReportError("SNAPSHOT_MISSING")
    connection = sqlite3.connect(
        f"file:{database_path.resolve().as_posix()}?mode=ro&immutable=1",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _validate_database(connection: sqlite3.Connection) -> None:
    if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        raise BetaReportError("SNAPSHOT_INTEGRITY_FAILED")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise BetaReportError("SNAPSHOT_FOREIGN_KEY_FAILED")

    tables = frozenset(
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    )
    if tables != REQUIRED_TABLES:
        raise BetaReportError("SNAPSHOT_SCHEMA_INVALID")


def _validate_snapshot_time(snapshot_at: datetime, now: datetime) -> datetime:
    snapshot_at = _utc(snapshot_at)
    now = _utc(now)
    age = now - snapshot_at
    if age > MAX_SNAPSHOT_AGE or age < -MAX_FUTURE_SKEW:
        raise BetaReportError("SNAPSHOT_STALE")
    return snapshot_at


def _load_health(
    connection: sqlite3.Connection,
    snapshot_at: datetime,
) -> list[sqlite3.Row]:
    rows = connection.execute(
        "SELECT source, state, reason, last_run_status, last_failure_kind, "
        "last_success_at, checked_at, freshness_sla_seconds "
        "FROM source_health WHERE source IN (?, ?) ORDER BY source",
        REQUIRED_SOURCES,
    ).fetchall()
    if frozenset(row["source"] for row in rows) != frozenset(REQUIRED_SOURCES):
        raise BetaReportError("SOURCE_HEALTH_MISSING")

    for row in rows:
        if (
            row["state"] != "healthy"
            or row["last_run_status"] not in {"success", "empty"}
            or row["last_failure_kind"] is not None
        ):
            raise BetaReportError("SOURCE_HEALTH_UNSAFE")
        last_success_at = _utc(row["last_success_at"])
        checked_at = _utc(row["checked_at"])
        freshness_sla = timedelta(seconds=int(row["freshness_sla_seconds"]))
        if snapshot_at - last_success_at > freshness_sla:
            raise BetaReportError("SOURCE_HEALTH_STALE")
        if last_success_at - snapshot_at > MAX_FUTURE_SKEW:
            raise BetaReportError("SOURCE_HEALTH_FUTURE")
        if snapshot_at - checked_at > freshness_sla:
            raise BetaReportError("SOURCE_HEALTH_STALE")
    return rows


def _valid_sec_url(value: str | None) -> bool:
    if not value or len(value) > 500 or any(char.isspace() for char in value):
        return False
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme == "https"
            and parsed.hostname == "www.sec.gov"
            and parsed.port is None
            and parsed.path.startswith("/Archives/")
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        return False


def _clean(value: object, limit: int) -> str:
    text = " ".join(str(value or "N/A").split())
    return text[:limit]


def _ticker(value: object) -> str:
    text = _clean(value, 32)
    if text.upper() in {"N/A", "NONE", "NULL", "UNKNOWN"}:
        return "ticker not supplied"
    return text


def _money(value: object, currency: object) -> str:
    if value is None:
        return "not disclosed"
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise BetaReportError("VALUE_INVALID") from exc
    return f"{_clean(currency, 8)} {amount:,.2f}"


def _quantity(value: object) -> str:
    if value is None:
        return "not disclosed"
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise BetaReportError("QUANTITY_INVALID") from exc
    return f"{amount:,.4f}".rstrip("0").rstrip(".")


def _timestamp(value: object) -> str:
    return _utc(str(value) if value is not None else None).strftime("%Y-%m-%d %H:%M UTC")


def _load_window_rows(
    connection: sqlite3.Connection,
    snapshot_at: datetime,
) -> list[sqlite3.Row]:
    window_start = snapshot_at - LOOKBACK
    window_end = snapshot_at + MAX_FUTURE_SKEW
    rows = connection.execute(
        "SELECT source, source_event_id, event_type, action, side, "
        "execution_status, ticker, entity_name, quantity, price, value, currency, "
        "event_at, filed_at, observed_at, source_url, parser_version, "
        "quality_status, quality_reasons "
        "FROM normalized_events_v2 "
        "WHERE source IN (?, ?) AND observed_at >= ? AND observed_at <= ? "
        "ORDER BY observed_at DESC, source_event_id",
        (
            *REQUIRED_SOURCES,
            window_start.replace(tzinfo=None).isoformat(sep=" "),
            window_end.replace(tzinfo=None).isoformat(sep=" "),
        ),
    ).fetchall()
    if len(rows) > MAX_WINDOW_ROWS:
        raise BetaReportError("EVENT_VOLUME_UNBOUNDED")
    return rows


def _validate_selected_row(row: sqlite3.Row) -> None:
    if not _valid_sec_url(row["source_url"]):
        raise BetaReportError("SOURCE_URL_INVALID")
    if row["quality_status"] != "valid":
        raise BetaReportError("SELECTED_EVENT_QUALITY_INVALID")
    try:
        reasons = json.loads(row["quality_reasons"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise BetaReportError("QUALITY_REASONS_INVALID") from exc
    if reasons:
        raise BetaReportError("SELECTED_EVENT_QUALITY_INVALID")

    if row["source"] == "sec_form4":
        expected_side = {"purchase": "BUY", "sale": "SELL"}.get(row["action"])
        if (
            row["event_type"] != "form4_transaction"
            or row["execution_status"] != "reported"
            or row["side"] != expected_side
            or expected_side is None
            or row["parser_version"] != TRUSTED_PARSER_VERSIONS["sec_form4"]
        ):
            raise BetaReportError("FORM4_SEMANTICS_INVALID")
    elif row["source"] == "sec_form144":
        if (
            row["event_type"] != "form144_notice"
            or row["action"] != "proposed_sale"
            or row["execution_status"] != "proposed"
            or row["side"] != "SELL"
            or row["parser_version"] != TRUSTED_PARSER_VERSIONS["sec_form144"]
        ):
            raise BetaReportError("FORM144_SEMANTICS_INVALID")
    else:
        raise BetaReportError("SOURCE_UNSUPPORTED")


def _rank(rows: list[sqlite3.Row]) -> list[sqlite3.Row]:
    def key(row: sqlite3.Row):
        try:
            value = Decimal(str(row["value"])) if row["value"] is not None else Decimal("-1")
        except InvalidOperation as exc:
            raise BetaReportError("VALUE_INVALID") from exc
        return (value, _utc(row["observed_at"]), row["source_event_id"])

    return sorted(rows, key=key, reverse=True)[:MAX_ITEMS_PER_CATEGORY]


def _render_item(row: sqlite3.Row, label: str) -> list[str]:
    _validate_selected_row(row)
    return [
        f"- [{label}] {_ticker(row['ticker'])} — {_clean(row['entity_name'], 120)}",
        (
            f"  quantity: {_quantity(row['quantity'])} | "
            f"disclosed value: {_money(row['value'], row['currency'])}"
        ),
        (
            f"  event: {_timestamp(row['event_at'])} | "
            f"filed: {_timestamp(row['filed_at'])} | "
            f"observed: {_timestamp(row['observed_at'])}"
        ),
        (
            f"  parser: {_clean(row['parser_version'], 32)} | "
            f"quality: {row['quality_status']} | SEC: {row['source_url']}"
        ),
    ]


def build_beta_report(
    database_path: Path,
    *,
    snapshot_at: datetime,
    now: datetime,
) -> BetaReport:
    snapshot_at = _validate_snapshot_time(snapshot_at, now)
    connection = _read_only_connection(database_path)
    try:
        _validate_database(connection)
        health_rows = _load_health(connection, snapshot_at)
        rows = _load_window_rows(connection, snapshot_at)
    finally:
        connection.close()

    quality_valid_rows = [row for row in rows if row["quality_status"] == "valid"]
    excluded_quality = len(rows) - len(quality_valid_rows)
    valid_rows = [
        row
        for row in quality_valid_rows
        if row["parser_version"] == TRUSTED_PARSER_VERSIONS.get(row["source"])
    ]
    excluded_parser = len(quality_valid_rows) - len(valid_rows)
    purchases = [
        row
        for row in valid_rows
        if row["source"] == "sec_form4"
        and row["event_type"] == "form4_transaction"
        and row["action"] == "purchase"
    ]
    sales = [
        row
        for row in valid_rows
        if row["source"] == "sec_form4"
        and row["event_type"] == "form4_transaction"
        and row["action"] == "sale"
    ]
    proposed = [row for row in valid_rows if row["source"] == "sec_form144"]
    other_form4 = [
        row
        for row in valid_rows
        if row["source"] == "sec_form4"
        and not (
            row["event_type"] == "form4_transaction"
            and row["action"] in {"purchase", "sale"}
        )
    ]

    report_date = snapshot_at.astimezone(HKT).strftime("%Y-%m-%d")
    window_start = snapshot_at - LOOKBACK
    lines = [
        f"SmartFlow Informational Beta — SEC Filing Brief — {report_date}",
        "",
        "INFORMATIONAL ONLY — NOT INVESTMENT ADVICE — NO TRADING SIGNAL",
        (
            "This report is a deterministic summary of SEC filings. It contains no "
            "directional recommendation and does not use an LLM."
        ),
        (
            "Form 4 items describe reported filing transactions. Form 144 items are "
            "proposed sales only and must not be treated as completed trades."
        ),
        "",
        "DATA WINDOW",
        f"- start: {window_start.strftime('%Y-%m-%d %H:%M UTC')}",
        f"- snapshot: {snapshot_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "- sources: SEC Form 4 and SEC Form 144 only",
        "",
        "SOURCE HEALTH",
    ]
    for row in health_rows:
        lines.append(
            f"- {row['source']}: {row['state']} | last success: "
            f"{_timestamp(row['last_success_at'])} | reason: {_clean(row['reason'], 128)}"
        )

    lines.extend(
        [
            "",
            "COUNTS",
            f"- Form 4 reported purchases (code P): {len(purchases)}",
            f"- Form 4 reported sales (code S): {len(sales)}",
            f"- Other valid Form 4 events excluded from detail: {len(other_form4)}",
            f"- Form 144 proposed sale notices: {len(proposed)}",
            f"- Warning/invalid events excluded from detail: {excluded_quality}",
            f"- Events from superseded parser versions excluded: {excluded_parser}",
            "",
            (
                f"TOP REPORTED FORM 4 PURCHASES BY DISCLOSED VALUE "
                f"(max {MAX_ITEMS_PER_CATEGORY})"
            ),
        ]
    )
    if purchases:
        for row in _rank(purchases):
            lines.extend(_render_item(row, "reported purchase"))
    else:
        lines.append("- none observed in this window")

    lines.extend(
        [
            "",
            (
                f"TOP REPORTED FORM 4 SALES BY DISCLOSED VALUE "
                f"(max {MAX_ITEMS_PER_CATEGORY})"
            ),
        ]
    )
    if sales:
        for row in _rank(sales):
            lines.extend(_render_item(row, "reported sale"))
    else:
        lines.append("- none observed in this window")

    lines.extend(
        [
            "",
            (
                f"TOP FORM 144 PROPOSED SALES BY DISCLOSED VALUE "
                f"(NOT EXECUTED; max {MAX_ITEMS_PER_CATEGORY})"
            ),
        ]
    )
    if proposed:
        for row in _rank(proposed):
            lines.extend(_render_item(row, "proposed sale — not executed"))
    else:
        lines.append("- none observed in this window")

    lines.extend(
        [
            "",
            "LIMITATIONS",
            "- Ranking is by disclosed value for compact presentation, not conviction.",
            "- Missing or undisclosed values are not estimated.",
            "- Refer to each linked SEC filing as the primary evidence.",
            "- Beta output is paused automatically when snapshot integrity or source health fails.",
            "",
        ]
    )
    return BetaReport(report_date=report_date, body="\n".join(lines))


def build_pause_notice(reason_code: str) -> str:
    safe_codes = {
        "EVENT_VOLUME_UNBOUNDED",
        "FORM144_SEMANTICS_INVALID",
        "FORM4_SEMANTICS_INVALID",
        "INTERNAL_VALIDATION_ERROR",
        "QUALITY_REASONS_INVALID",
        "QUANTITY_INVALID",
        "SELECTED_EVENT_QUALITY_INVALID",
        "SNAPSHOT_FOREIGN_KEY_FAILED",
        "SNAPSHOT_INTEGRITY_FAILED",
        "SNAPSHOT_MISSING",
        "SNAPSHOT_SCHEMA_INVALID",
        "SNAPSHOT_SIZE_INVALID",
        "SNAPSHOT_SIZE_MISMATCH",
        "SNAPSHOT_STALE",
        "SOURCE_HEALTH_FUTURE",
        "SOURCE_HEALTH_MISSING",
        "SOURCE_HEALTH_STALE",
        "SOURCE_HEALTH_UNSAFE",
        "SOURCE_UNSUPPORTED",
        "SOURCE_URL_INVALID",
        "TIMESTAMP_INVALID",
        "TIMESTAMP_MISSING",
        "VALUE_INVALID",
    }
    if reason_code not in safe_codes:
        reason_code = "INTERNAL_VALIDATION_ERROR"
    return f"""SmartFlow Informational Beta — REPORT PAUSED

INFORMATIONAL ONLY — NOT INVESTMENT ADVICE — NO TRADING SIGNAL

No filing summary was produced because a fail-closed data gate did not pass.

Reason code: {reason_code}

No legacy database was used, no LLM was called, and no directional recommendation was generated.
Review the SEC shadow pipeline and publish a verified snapshot before resuming the beta report.
"""
