"""Windows existing-GWS self-mail; durable uncertainty states never blind-send."""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses
from pathlib import Path

from .common import digest, file_hash, read_json, stamp, write_json


SENDER = "tommytang.cc@gmail.com"
RECIPIENT = "tommytang2414@gmail.com"


def gws(resource: str, action: str, params: dict, body: dict | None = None, upload: Path | None = None) -> dict:
    native = Path(os.environ.get("APPDATA", "")) / "npm/node_modules/@googleworkspace/cli/bin/gws.exe"
    executable = str(native) if native.is_file() else shutil.which("gws")
    if not executable:
        raise ValueError("existing_gws_cli_unavailable")
    command = [executable, "gmail", "users", *resource.split(), action, "--params", json.dumps(params)]
    if body is not None:
        command += ["--json", json.dumps(body)]
    if upload:
        command += ["--upload", str(upload.resolve()), "--upload-content-type", "message/rfc822"]
    result = subprocess.run(command, capture_output=True, encoding="utf-8", timeout=45)
    if result.returncode:
        # OAuth/key diagnostics are not logged; no automatic login or profile switch.
        raise ValueError("existing_gws_operation_failed_auth_or_provider_check_required")
    return json.loads(result.stdout)


def verify(raw: str, expected: EmailMessage) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_=-]+", raw):
        raise ValueError("gmail_raw_encoding")
    message = BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    for name in ("From", "To", "Subject", "Message-ID"):
        if len(message.get_all(name, [])) != 1:
            raise ValueError("gmail_protected_header_count")
    # Gmail assigns its own RFC ID. Reconcile our subject token and exact body;
    # require a well-formed provider ID rather than the replaced requested value.
    if not re.fullmatch(r"<[^\s<>@]+@[^\s<>@]+>", str(message["Message-ID"])):
        raise ValueError("gmail_provider_message_id")
    if message.defects or message.is_multipart() or message.get_content_type() != "text/plain" or message.get("Cc") or message.get("Bcc"):
        raise ValueError("gmail_mime_or_recipient_contract")
    for name in ("From", "To"):
        if getaddresses(message.get_all(name)) != getaddresses(expected.get_all(name)):
            raise ValueError("gmail_exact_recipient_or_sender")
    if str(message["Subject"]) != str(expected["Subject"]) or message.get_content().replace("\r\n", "\n") != expected.get_content().replace("\r\n", "\n"):
        raise ValueError("gmail_frozen_content_mismatch")


def send(item: dict, ledger_root: Path) -> dict:
    if item["recipient"] != RECIPIENT or digest(item["text"].encode()) != item["text_sha256"]:
        raise ValueError("outbox_frozen_recipient_or_body")
    if gws("", "getProfile", {"userId": "me"}).get("emailAddress", "").lower() != SENDER:
        raise ValueError("existing_gws_sender_profile_mismatch")
    token = digest(item["identity"].encode())[:24]
    directory = ledger_root / token
    directory.mkdir(parents=True, exist_ok=True)
    message = EmailMessage(policy=policy.SMTP)
    message["From"], message["To"] = SENDER, RECIPIENT
    message["Subject"] = item["subject"] + " [smartflow-" + token + "]"
    message["Message-ID"] = "<smartflow-" + token + "@local.invalid>"
    message.set_content(item["text"])
    mime = directory / "message.eml"
    ledger = directory / "delivery.json"
    if not ledger.exists():
        mime.write_bytes(message.as_bytes())
        write_json(ledger, {"identity": item["identity"], "text_sha256": item["text_sha256"], "mime_sha256": file_hash(mime), "state": "prepared"})
    state = read_json(ledger)
    if state["identity"] != item["identity"] or state["text_sha256"] != item["text_sha256"] or state["mime_sha256"] != file_hash(mime):
        raise ValueError("delivery_ledger_or_mime_conflict")
    verify(base64.urlsafe_b64encode(mime.read_bytes()).decode(), message)

    def persist(value: str) -> None:
        state.update({"state": value, "updated_at": stamp()})
        write_json(ledger, state)

    if state["state"] in {"sending", "sent"}:
        if state.get("gmail_message_id"):
            identity = state["gmail_message_id"]
        else:
            hits = gws("messages", "list", {"userId": "me", "q": "in:sent subject:smartflow-" + token, "maxResults": 10}).get("messages", [])
            if len(hits) != 1:
                raise ValueError("uncertain_send_requires_inspection_no_resend")
            identity = hits[0]["id"]
        remote = gws("messages", "get", {"userId": "me", "id": identity, "format": "raw"})
        verify(remote["raw"], message)
        if "SENT" not in remote.get("labelIds", []):
            raise ValueError("gmail_sent_label_unconfirmed")
        state["gmail_message_id"] = identity
        persist("sent")
        return state
    if state["state"] == "creating":
        hits = gws("drafts", "list", {"userId": "me", "q": "subject:smartflow-" + token, "maxResults": 10}).get("drafts", [])
        if len(hits) != 1:
            raise ValueError("uncertain_draft_requires_inspection_no_duplicate")
        state["draft_id"] = hits[0]["id"]
        persist("drafted")
    if state["state"] == "prepared":
        persist("creating")
        draft = gws("drafts", "create", {"userId": "me"}, {}, mime)
        state["draft_id"] = draft["id"]
        persist("drafted")
    if state["state"] != "drafted":
        raise ValueError("unknown_delivery_state")
    draft = gws("drafts", "get", {"userId": "me", "id": state["draft_id"], "format": "raw"})
    verify(draft["message"]["raw"], message)
    persist("sending")
    sent = gws("drafts", "send", {"userId": "me"}, {"id": state["draft_id"]})
    state["gmail_message_id"] = sent["id"]
    write_json(ledger, state)
    remote = gws("messages", "get", {"userId": "me", "id": sent["id"], "format": "raw"})
    verify(remote["raw"], message)
    if "SENT" not in remote.get("labelIds", []):
        raise ValueError("gmail_sent_label_unconfirmed")
    persist("sent")
    return state
