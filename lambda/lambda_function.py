"""SmartFlow daily email with fail-closed containment and owner-brief modes."""

from __future__ import annotations

import http.client
import json
import os
import ssl
import sys
from datetime import datetime, timezone
from email.message import EmailMessage


def _log(message: str) -> None:
    """Write UTF-8 without relying on the Lambda host console encoding."""
    sys.stdout.buffer.write((message + "\n").encode("utf-8", errors="replace"))
    sys.stdout.flush()


VERSION = "v6-m3-owner-brief"
S3_BUCKET = os.environ["S3_BUCKET"]
SES_FROM = os.environ["SES_FROM"]
EMAIL_TO = os.environ["EMAIL_TO"]
DECISION_PACK_KEY = "beta/sec-v2-decision-pack.json"
SENT_MARKER_PREFIX = "beta/sec-owner-sent/"
MINIMAX_HOST = "api.minimaxi.com"
MINIMAX_PATH = "/v1/text/chatcompletion_v2"
MINIMAX_MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M3")
M3_TIMEOUT_SECONDS = 45
M3_MAX_TOKENS = 4_096


def send_email(report: str, subject: str) -> None:
    import boto3

    ses = boto3.client("ses")
    ses.send_email(
        Source=SES_FROM,
        Destination={"ToAddresses": [EMAIL_TO]},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {"Text": {"Data": report, "Charset": "UTF-8"}},
        },
    )
    _log("Email accepted by SES")


def send_email_with_csv(
    report: str,
    subject: str,
    *,
    csv_payload: bytes,
    filename: str,
) -> None:
    import boto3

    message = EmailMessage()
    message["From"] = SES_FROM
    message["To"] = EMAIL_TO
    message["Subject"] = subject
    message.set_content(report, subtype="plain", charset="utf-8")
    message.add_attachment(
        csv_payload,
        maintype="text",
        subtype="csv",
        filename=filename,
    )
    raw_message = message.as_bytes()
    if len(raw_message) > 10 * 1024 * 1024:
        raise RuntimeError("EMAIL_SIZE_INVALID")
    boto3.client("ses").send_raw_email(
        Source=SES_FROM,
        Destinations=[EMAIL_TO],
        RawMessage={"Data": raw_message},
    )
    _log("Email with deep-dive CSV accepted by SES")


def build_containment_notice() -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"""SmartFlow 資料品質修復通知 — {today}

SmartFlow 目前正進行資料語義、collector health、report traceability 同 signal validation 修復。

修復期間：
- 暫停所有 LONG、SHORT 及方向性建議
- 不會使用現有資料生成 AI 投資結論
- Production raw data collection 會按已批准的 remediation plan 逐步檢查及收窄

完成 parser correctness、evidence traceability、freshness 同 reliability release gates 前，任何舊有 SmartFlow signal 都只可視為未驗證研究資料。
"""


def _download_decision_pack():
    import boto3

    from owner_brief import MAX_PACK_BYTES, OwnerBriefError

    response = boto3.client("s3").get_object(
        Bucket=S3_BUCKET,
        Key=DECISION_PACK_KEY,
    )
    content_length = int(response["ContentLength"])
    if content_length <= 0 or content_length > MAX_PACK_BYTES:
        raise OwnerBriefError("PACK_SIZE_INVALID")
    payload = response["Body"].read(MAX_PACK_BYTES + 1)
    if len(payload) != content_length or len(payload) > MAX_PACK_BYTES:
        raise OwnerBriefError("PACK_SIZE_MISMATCH")
    _log(f"Decision pack downloaded: {content_length} bytes")
    return payload, response.get("Metadata", {}), response["LastModified"]


def _call_m3(messages: list[dict[str, str]]) -> dict:
    from owner_brief import MAX_M3_RESPONSE_BYTES, OwnerBriefError

    api_key = os.environ.get("MINIMAX_API_KEY", "")
    if not api_key:
        raise OwnerBriefError("M3_KEY_MISSING")
    request_payload = json.dumps(
        {
            "model": MINIMAX_MODEL,
            "messages": messages,
            "thinking": {"type": "adaptive"},
            "temperature": 0.1,
            "max_tokens": M3_MAX_TOKENS,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    connection = http.client.HTTPSConnection(
        MINIMAX_HOST,
        timeout=M3_TIMEOUT_SECONDS,
        context=ssl.create_default_context(),
    )
    try:
        connection.request(
            "POST",
            MINIMAX_PATH,
            body=request_payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "SmartFlow-M3-Owner-Brief/1.0",
            },
        )
        response = connection.getresponse()
        content_type = response.getheader("Content-Type", "")
        body = response.read(MAX_M3_RESPONSE_BYTES + 1)
    finally:
        connection.close()
    if response.status != 200:
        raise OwnerBriefError("M3_PROVIDER_STATUS")
    if "application/json" not in content_type.casefold():
        raise OwnerBriefError("M3_CONTENT_TYPE_INVALID")
    if not body or len(body) > MAX_M3_RESPONSE_BYTES:
        raise OwnerBriefError("M3_RESPONSE_SIZE_INVALID")
    try:
        return json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OwnerBriefError("M3_RESPONSE_JSON_INVALID") from exc


def _generate_narrative(pack: dict) -> tuple[dict, bool]:
    from owner_brief import (
        M3OutputError,
        build_m3_messages,
        deterministic_narrative,
        validate_m3_response,
    )

    messages = build_m3_messages(pack)
    for attempt in range(2):
        try:
            response = _call_m3(messages)
            narrative = validate_m3_response(
                response,
                pack=pack,
                expected_model=MINIMAX_MODEL,
            )
            _log("M3 narrative accepted by local validator")
            return narrative, True
        except M3OutputError:
            if attempt == 0:
                continue
            break
        except Exception:
            break
    _log("M3 narrative unavailable; deterministic fallback selected")
    return deterministic_narrative(pack), False


def _marker_key(report_id: str) -> str:
    if not report_id.startswith("SFO-") or len(report_id) > 64:
        raise ValueError("invalid report id")
    if any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for character in report_id):
        raise ValueError("invalid report id")
    return f"{SENT_MARKER_PREFIX}{report_id}.json"


def _marker_exists(report_id: str) -> bool:
    import boto3

    key = _marker_key(report_id)
    try:
        boto3.client("s3").head_object(Bucket=S3_BUCKET, Key=key)
        return True
    except Exception as exc:
        response = getattr(exc, "response", {})
        code = str(response.get("Error", {}).get("Code", ""))
        # S3 returns 403 for a missing key when this least-privilege role has
        # exact GetObject access but intentionally has no ListBucket access.
        if code in {"403", "AccessDenied", "404", "NoSuchKey", "NotFound"}:
            return False
        raise


def _write_marker(pack: dict, *, ai_used: bool) -> None:
    import boto3

    marker = json.dumps(
        {
            "report_id": pack["report_id"],
            "snapshot_sha256": pack["snapshot_sha256"],
            "sent_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "ai_used": ai_used,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    boto3.client("s3").put_object(
        Bucket=S3_BUCKET,
        Key=_marker_key(pack["report_id"]),
        Body=marker,
        ContentType="application/json",
        ServerSideEncryption="AES256",
    )


def _run_owner_brief() -> dict[str, int | str | bool]:
    from owner_brief import (
        OwnerBriefError,
        build_deep_dive_csv,
        render_owner_email,
        validate_decision_pack,
    )
    from beta_report import build_pause_notice

    try:
        payload, metadata, last_modified = _download_decision_pack()
        pack = validate_decision_pack(
            payload,
            metadata=metadata,
            object_last_modified=last_modified,
            now=datetime.now(timezone.utc),
        )
    except OwnerBriefError as exc:
        _log(f"Owner brief paused: {exc.code}")
        body = build_pause_notice(exc.code)
        subject = (
            "SmartFlow BETA PAUSED — DATA HEALTH — "
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        )
        send_email(body, subject)
        return {"status": "beta_paused", "reason": exc.code, "chars": len(body)}
    except Exception:
        _log("Owner brief paused: INTERNAL_VALIDATION_ERROR")
        body = build_pause_notice("INTERNAL_VALIDATION_ERROR")
        subject = (
            "SmartFlow BETA PAUSED — DATA HEALTH — "
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        )
        send_email(body, subject)
        return {
            "status": "beta_paused",
            "reason": "INTERNAL_VALIDATION_ERROR",
            "chars": len(body),
        }

    if _marker_exists(pack["report_id"]):
        _log("Duplicate report suppressed by sent marker")
        return {"status": "duplicate_suppressed", "report_id": pack["report_id"]}

    narrative, ai_used = _generate_narrative(pack)
    csv_payload = None
    try:
        csv_payload = build_deep_dive_csv(pack)
        subject, body = render_owner_email(pack, narrative, ai_used=ai_used)
        send_email_with_csv(
            body,
            subject,
            csv_payload=csv_payload,
            filename=f"SmartFlow_SEC_Deep_Dive_{pack['report_date']}.csv",
        )
    except OwnerBriefError:
        _log("Deep-dive CSV unavailable; sending report without attachment")
        subject, body = render_owner_email(
            pack,
            narrative,
            ai_used=ai_used,
            attachment_available=False,
        )
        send_email(body, subject)

    try:
        _write_marker(pack, ai_used=ai_used)
    except Exception:
        _log("Sent marker write failed after SES acceptance")
    _log(
        f"Owner brief completed: report_id={pack['report_id']} "
        f"ai_used={str(ai_used).lower()} events={len(pack['events'])}"
    )
    return {
        "status": "owner_brief",
        "report_id": pack["report_id"],
        "ai_used": ai_used,
        "chars": len(body),
        "csv_bytes": len(csv_payload or b""),
    }


def handler(event, context):
    del event, context
    report_mode = os.environ.get("REPORT_MODE", "containment").strip().lower()
    _log(f"Lambda {VERSION} started in {report_mode} mode")

    if report_mode == "containment":
        report = build_containment_notice()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        send_email(report, f"SmartFlow Daily — REMEDIATION — {today}")
        _log("Containment notice sent; decision pack was not read")
        return {"status": "containment", "chars": len(report)}

    if report_mode in {"informational_beta", "owner_brief"}:
        return _run_owner_brief()

    raise ValueError(f"Unsupported REPORT_MODE: {report_mode}")
