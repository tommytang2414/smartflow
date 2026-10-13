"""Existing Windows AWS/GWS bridge; no credentials copied to the Mac."""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import tempfile
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .common import beneath, canonical, digest, file_hash, read_json, stamp, utc, write_json
from .company import fetch as fetch_company
from .delivery import send
from .snapshots import sync_aws


REMOTE = "vortex@192.168.50.228"
ROOT = "/Users/vortex/Applications/smartflow-research"
SSH = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=yes",
       "-o", "UserKnownHostsFile=C:/Users/User/.ssh/hk-newsroom-mac-known_hosts", "-o", "IdentitiesOnly=yes",
       "-i", "C:/Users/User/.ssh/hk-newsroom-mac"]


def remote(command: str) -> str:
    return subprocess.run(["ssh", *SSH, REMOTE, command], check=True, capture_output=True, encoding="utf-8", timeout=180).stdout


def scp(source: str, target: str) -> None:
    subprocess.run(["scp", *SSH, source, target], check=True, capture_output=True, timeout=300)


def refresh(root: Path, aliases_path: Path) -> dict:
    label = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    folder = root / "refresh" / label
    folder.mkdir(parents=True, exist_ok=False)
    definitions = read_json(aliases_path)
    write_json(folder / "aliases.json", definitions)
    sync_aws(folder / "snapshots")
    fetch_company(definitions, folder / "company", "tommytang.cc@gmail.com")
    files = {p.relative_to(folder).as_posix(): file_hash(p) for p in sorted(folder.rglob("*")) if p.is_file()}
    archive = folder.parent / (label + ".zip")
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as z:
        for name in files:
            z.write(folder / name, name)
    sha = file_hash(archive)
    remote("mkdir -p " + ROOT + "/inbox")
    scp(str(archive.resolve()), REMOTE + ":" + ROOT + "/inbox/" + label + ".zip")
    # Arguments are generated fixed-format labels/hashes; never interpolate
    # collected issuer text, filenames, credentials or a provider response.
    script = "\n".join([
        "import pathlib,zipfile,hashlib,json", f"r=pathlib.Path('{ROOT}/inbox')", f"a=r/'{label}.zip'",
        f"assert hashlib.sha256(a.read_bytes()).hexdigest()=='{sha}'", f"d=r/'{label}';d.mkdir(exist_ok=False)",
        "with zipfile.ZipFile(a) as z:", " for n in z.namelist():assert (d/n).resolve().is_relative_to(d)", " z.extractall(d)",
        "files={p.relative_to(d).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in d.rglob('*') if p.is_file()}",
        "value={'directory':d.name,'files':files,'archive_sha256':hashlib.sha256(a.read_bytes()).hexdigest()}",
        "t=r/'latest.json.tmp';t.write_text(json.dumps(value,sort_keys=True));t.replace(r/'latest.json')", "print(json.dumps(value))"])
    result = subprocess.run(["ssh", *SSH, REMOTE, "cd " + ROOT + " && .venv/bin/python -"], input=script,
                            check=True, capture_output=True, encoding="utf-8", timeout=180)
    receipt = {"status": "refreshed", "label": label, "archive_sha256": sha, "files": len(files), "mac": json.loads(result.stdout)}
    write_json(folder / "receipt.json", receipt)
    write_json(root / "last-refresh.json", {"completed_at": stamp(), **receipt})
    return {"status": "refreshed", "label": label, "files": len(files)}


def restore_verify(archive: Path, destination: Path) -> tuple[sqlite3.Connection, dict]:
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            beneath(destination, name)
        z.extractall(destination)
    manifest = read_json(destination / "backup-manifest.json")
    if manifest.get("schema") != "smartflow-state-backup-v1":
        raise ValueError("backup_manifest_contract")
    for name, expected in manifest["files"].items():
        if file_hash(beneath(destination, name)) != expected:
            raise ValueError("backup_file_hash_mismatch")
    db = sqlite3.connect(destination / "state/research.sqlite3")
    db.row_factory = sqlite3.Row
    try:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok" or db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("backup_restored_database_integrity")
        approved = 0
        for row in db.execute("SELECT * FROM runs WHERE status='approved'"):
            directory = beneath(destination / "state", row["directory"])
            if file_hash(directory / "manifest.json") != row["manifest_hash"]:
                raise ValueError("backup_restored_run_manifest")
            for name, expected in read_json(directory / "manifest.json")["files"].items():
                if file_hash(beneath(directory, name)) != expected:
                    raise ValueError("backup_restored_run_artifact")
            approved += 1
        for row in db.execute("SELECT directory,result_hash FROM task_attempts"):
            if file_hash(beneath(destination / "state", row["directory"]) / "result.json") != row["result_hash"]:
                raise ValueError("backup_restored_followup_tamper")
        for path in (destination / "state/snapshots").glob("*.db"):
            if file_hash(path) != path.stem:
                raise ValueError("backup_restored_source_cache_tamper")
        return db, {"status": "restore_verified", "files": len(manifest["files"]), "approved_runs": approved}
    except Exception:
        db.close()
        raise


def drain(root: Path) -> dict:
    attempt = json.loads(remote("cat " + ROOT + "/exports/operations/latest-attempt.json"))
    now = datetime.now(timezone.utc)
    if attempt["status"] == "running":
        if now - utc(attempt["started_at"]) <= timedelta(minutes=90):
            return {"status": "waiting_for_scheduled_attempt", "attempt": attempt["id"]}
        raise ValueError("scheduled_attempt_interrupted_or_overdue")
    if not attempt.get("backup", {}).get("sha256"):
        raise ValueError("latest_scheduled_backup_failed")
    receipt = json.loads(remote("cat " + ROOT + "/exports/operations/latest.json"))
    if attempt["backup"]["sha256"] != receipt["sha256"]:
        raise ValueError("backup_not_bound_to_latest_scheduled_attempt")
    created = utc(receipt["created_at"])
    local_now = now.astimezone(timezone(timedelta(hours=8)))
    if (created > now or now-created > timedelta(hours=26)
            or (local_now.hour >= 12 and created.astimezone(local_now.tzinfo).date() != local_now.date())):
        raise ValueError("scheduled_backup_stale_or_missing_today")
    archive_name = Path(receipt["archive"]).name
    if not re.fullmatch(r"state-\d{8}T\d{6}Z-[0-9a-f]{8}\.zip", archive_name) or receipt["archive"] != ROOT + "/exports/operations/" + archive_name:
        raise ValueError("remote_backup_path_contract")
    destination = root / "backups" / archive_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        with tempfile.TemporaryDirectory(prefix="pull-", dir=destination.parent) as temporary:
            downloaded = Path(temporary) / archive_name
            scp(REMOTE + ":" + receipt["archive"], str(downloaded))
            if file_hash(downloaded) != receipt["sha256"]:
                raise ValueError("offhost_backup_transfer_hash")
            downloaded.replace(destination)
    if file_hash(destination) != receipt["sha256"]:
        raise ValueError("existing_offhost_backup_hash")
    confirmations = []
    with tempfile.TemporaryDirectory(prefix="restore-", dir=root) as temporary:
        restored = Path(temporary)
        db, verification = restore_verify(destination, restored)
        try:
            for row in db.execute("SELECT * FROM operations WHERE state='queued' AND kind IN ('weekly','fault','recovery','canary') ORDER BY rowid LIMIT 16"):
                item = json.loads(row["body"])
                path = beneath(restored / "state", item["file"])
                if file_hash(path) != item["sha256"] or read_json(path) != {k: item[k] for k in ("identity", "kind", "recipient", "subject", "text", "text_sha256")}:
                    raise ValueError("restored_outbox_binding")
                ledger = root / "delivery" / (digest(item["identity"].encode())[:24]) / "delivery.json"
                if ledger.exists() and read_json(ledger).get("state") == "sent":
                    sent = read_json(ledger)
                    if sent["identity"] != item["identity"] or sent["text_sha256"] != item["text_sha256"]:
                        raise ValueError("confirmed_delivery_binding")
                else:
                    sent = send(item, root / "delivery")
                confirmations.append({"identity": item["identity"], "text_sha256": item["text_sha256"], "gmail_message_id": sent["gmail_message_id"]})
        finally:
            db.close()
    result = {**verification, "archive": str(destination), "sha256": receipt["sha256"], "confirmations": confirmations, "verified_at": stamp()}
    write_json(root / "backups" / (archive_name + ".receipt.json"), result)
    write_json(root / "last-drain.json", result)
    if confirmations:
        path = root / "confirmed-deliveries.json"
        write_json(path, confirmations)
        scp(str(path.resolve()), REMOTE + ":" + ROOT + "/inbox/confirmed-deliveries.json")
        remote("cd " + ROOT + " && .venv/bin/python -m smartflow.research --state state confirm-delivery --receipts inbox/confirmed-deliveries.json")
    return result


def main() -> None:
    from .__main__ import single_writer
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("refresh", "drain"))
    parser.add_argument("--root", type=Path, default=Path("data/research-prototype/gateway"))
    parser.add_argument("--aliases", type=Path, default=Path("data/research-prototype/aliases-us-v3.json"))
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    with single_writer(args.root):
        try:
            result = refresh(args.root, args.aliases) if args.mode == "refresh" else drain(args.root)
            episode_path = args.root / ("gateway-fault-" + args.mode + ".json")
            if episode_path.exists() and result.get("status") in {"refreshed", "restore_verified"}:
                episode = read_json(episode_path)
                if episode["state"] == "open":
                    text = "SmartFlow Windows " + args.mode + " 流程已恢復；其他流程、Mac 研究及來源 gates 仍以實際 receipt 為準。\n"
                    send({"identity": "gateway-recovery:" + episode["episode"], "recipient": "tommytang2414@gmail.com", "subject": "SmartFlow 接駁已恢復", "text": text, "text_sha256": digest(text.encode())}, args.root / "delivery")
                    write_json(episode_path, {**episode, "state": "closed", "recovered_at": stamp()})
            write_json(args.root / (args.mode + "-status.json"), {"completed_at": stamp(), **result})
            print(json.dumps(result, ensure_ascii=False))
        except Exception as error:
            code = str(error)[:140] if isinstance(error, ValueError) else type(error).__name__
            write_json(args.root / (args.mode + "-status.json"), {"status": "needs_attention", "reason_code": code, "recorded_at": stamp()})
            episode_path = args.root / ("gateway-fault-" + args.mode + ".json")
            episode = read_json(episode_path) if episode_path.exists() else {"state": "closed"}
            if episode["state"] == "closed":
                episode = {"episode": uuid.uuid4().hex[:16], "state": "open", "reason_code": code, "started_at": stamp(), "notified": False}
                write_json(episode_path, episode)
            if not episode.get("notified"):
                text = "SmartFlow Windows 接駁／異機備份未完成。\n原因代碼：" + episode["reason_code"] + "\n請檢查 Windows／Mac 是否開機、LAN 連線及既有供應商登入。冇自動重新授權或重送舊報告。\n"
                try:
                    send({"identity": "gateway-fault:" + episode["episode"], "recipient": "tommytang2414@gmail.com", "subject": "SmartFlow 接駁需要處理", "text": text, "text_sha256": digest(text.encode())}, args.root / "delivery")
                    write_json(episode_path, {**episode, "notified": True})
                except Exception:
                    pass  # Original failure receipt survives an unavailable mail route.
            raise SystemExit("gateway_needs_attention:" + code) from None


if __name__ == "__main__":
    main()
