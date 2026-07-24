"""SmartFlow daily email with fail-closed containment and SEC beta modes."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def _log(message: str) -> None:
    """Write UTF-8 without relying on the Lambda host console encoding."""
    sys.stdout.buffer.write((message + "\n").encode("utf-8", errors="replace"))
    sys.stdout.flush()


VERSION = "v5-informational-beta"
S3_BUCKET = os.environ["S3_BUCKET"]
SES_FROM = os.environ["SES_FROM"]
EMAIL_TO = os.environ["EMAIL_TO"]
BETA_S3_KEY = "beta/sec-v2-shadow.db"
BETA_DB_PATH = Path("/tmp/smartflow-v2-beta.db")


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


def _download_beta_snapshot():
    import boto3

    s3 = boto3.client("s3")
    metadata = s3.head_object(Bucket=S3_BUCKET, Key=BETA_S3_KEY)
    content_length = int(metadata["ContentLength"])
    if content_length <= 0 or content_length > 100 * 1024 * 1024:
        from beta_report import BetaReportError

        raise BetaReportError("SNAPSHOT_SIZE_INVALID")

    try:
        BETA_DB_PATH.unlink(missing_ok=True)
        s3.download_file(S3_BUCKET, BETA_S3_KEY, str(BETA_DB_PATH))
    except Exception:
        BETA_DB_PATH.unlink(missing_ok=True)
        raise

    if BETA_DB_PATH.stat().st_size != content_length:
        BETA_DB_PATH.unlink(missing_ok=True)
        from beta_report import BetaReportError

        raise BetaReportError("SNAPSHOT_SIZE_MISMATCH")

    _log(f"Beta snapshot downloaded: {content_length} bytes")
    return metadata["LastModified"]


def _run_informational_beta() -> dict[str, int | str]:
    from beta_report import BetaReportError, build_beta_report, build_pause_notice

    try:
        snapshot_at = _download_beta_snapshot()
        report = build_beta_report(
            BETA_DB_PATH,
            snapshot_at=snapshot_at,
            now=datetime.now(timezone.utc),
        )
        subject = f"SmartFlow BETA — Informational SEC Brief — {report.report_date}"
        send_email(report.body, subject)
        return {"status": "informational_beta", "chars": len(report.body)}
    except BetaReportError as exc:
        _log(f"Beta report paused: {exc.code}")
        body = build_pause_notice(exc.code)
        subject = (
            "SmartFlow BETA PAUSED — DATA HEALTH — "
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        )
        send_email(body, subject)
        return {"status": "beta_paused", "reason": exc.code, "chars": len(body)}
    except Exception as exc:
        _log(f"Beta report paused: INTERNAL_VALIDATION_ERROR ({type(exc).__name__})")
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
    finally:
        BETA_DB_PATH.unlink(missing_ok=True)


def handler(event, context):
    del event, context
    report_mode = os.environ.get("REPORT_MODE", "containment").strip().lower()
    _log(f"Lambda {VERSION} started in {report_mode} mode")

    if report_mode == "containment":
        report = build_containment_notice()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        send_email(report, f"SmartFlow Daily — REMEDIATION — {today}")
        _log("Containment notice sent; S3 beta snapshot was not read")
        return {"status": "containment", "chars": len(report)}

    if report_mode == "informational_beta":
        return _run_informational_beta()

    raise ValueError(f"Unsupported REPORT_MODE: {report_mode}")
