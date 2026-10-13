"""Recoverable local scheduling, frozen outbox and full consistent state backup."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .common import beneath, canonical, digest, file_hash, read_json, stamp, utc, write_json
from .store import ResearchStore


HKT = timezone(timedelta(hours=8))


def queue(store: ResearchStore, identity: str, subject: str, text: str, kind: str) -> dict:
    body = {"identity": identity, "kind": kind, "recipient": "tommytang2414@gmail.com", "subject": subject,
            "text": text, "text_sha256": digest(text.encode())}
    old = store.db.execute("SELECT body FROM operations WHERE identity=?", (identity,)).fetchone()
    if old:
        # A weekly period or fault episode is frozen on first creation, even if
        # later state changes. Never create a second identity just to resend it.
        return json.loads(old[0])
    target = store.root / "outbox" / (digest(identity.encode())[:24] + ".json")
    write_json(target, body)
    receipt = {**body, "file": target.relative_to(store.root).as_posix(), "sha256": file_hash(target)}
    with store.db:
        store.db.execute("INSERT INTO operations VALUES(?,?,'queued',?,?)", (identity, kind, canonical(receipt).decode(), stamp()))
    return receipt


def fault(store: ResearchStore, reason: str) -> None:
    row = store.db.execute("SELECT body,state FROM operations WHERE identity='health-episode'").fetchone()
    if row and row["state"] == "open":
        return
    episode = uuid.uuid4().hex[:16]
    body = {"episode": episode, "reason": reason, "started_at": stamp()}
    queue(store, "fault:" + episode, "SmartFlow 需要處理", "SmartFlow 自動研究未完成。\n原因代碼：" + reason + "\n未將失敗當成無變化，亦冇重送舊報告。\n", "fault")
    with store.db:
        store.db.execute("INSERT INTO operations VALUES('health-episode','health','open',?,?) ON CONFLICT(identity) DO UPDATE SET state='open',body=excluded.body,updated_at=excluded.updated_at", (canonical(body).decode(), stamp()))


def recovered(store: ResearchStore) -> None:
    row = store.db.execute("SELECT body FROM operations WHERE identity='health-episode' AND state='open'").fetchone()
    if row:
        body = json.loads(row[0])
        queue(store, "recovery:" + body["episode"], "SmartFlow 已恢復檢查", "SmartFlow 已重新完成一輪資料／研究檢查。\n來源 HOLD、行情未接通及觀察窗口仍以最新報告為準。\n", "recovery")
        with store.db:
            store.db.execute("UPDATE operations SET state='closed',updated_at=? WHERE identity='health-episode'", (stamp(),))


def weekly(store: ResearchStore, cutoff: datetime) -> dict | None:
    day = cutoff.astimezone(HKT).date()
    if day.weekday() != 5 or cutoff.astimezone(HKT).hour < 12:
        return None
    rows = store.db.execute("SELECT * FROM runs WHERE status='approved' AND completed_at>? AND completed_at<=? ORDER BY rowid", (stamp(cutoff-timedelta(days=7)), stamp(cutoff))).fetchall()
    review_days = {utc(row[0]).astimezone(HKT).date() for row in store.db.execute("SELECT completed_at FROM runs WHERE status='approved' AND completed_at<=?", (stamp(cutoff),))}
    manual_days = set()
    for row in store.db.execute("SELECT body,updated_at FROM operations WHERE kind='owner_review' AND state='recorded' AND updated_at<=?", (stamp(cutoff),)):
        receipt = json.loads(row[0])
        run = store.db.execute("SELECT completed_at,report_hash FROM runs WHERE id=? AND status='approved' AND completed_at<=?", (receipt["run_id"], stamp(cutoff))).fetchone()
        if run and run["report_hash"] == receipt["report_sha256"]:
            manual_days.add(utc(row["updated_at"]).astimezone(HKT).date())
    # Seven real reviewed days remain an activation prerequisite for automatic
    # investment-report delivery; a truthful operational digest is allowed now.
    text = ["SmartFlow 每週狀況", "截點：" + stamp(cutoff), "本週通過覆核報告：" + str(len(rows)),
            "實際已覆核日數：" + str(len(review_days)), "待處理問題：" + str(store.status()["open_tasks"])]
    text.append("操作者明確手動驗收日數：" + str(len(manual_days)))
    if len(manual_days) < 7:
        text.append("投資研究週報仍在觀察期；未達七個手動驗收研究日，今次只寄營運狀況。GPT 覆核唔代替操作者驗收。")
    else:
        for row in rows:
            directory = beneath(store.root, row["directory"])
            if file_hash(directory / "manifest.json") != row["manifest_hash"]:
                raise ValueError("weekly_manifest_tamper")
            for name, expected in read_json(directory / "manifest.json")["files"].items():
                if file_hash(beneath(directory, name)) != expected:
                    raise ValueError("weekly_artifact_tamper")
            text.extend(["\n報告 " + row["id"], (directory / "REPORT.md").read_text(encoding="utf-8")])
    latest = store.db.execute("SELECT status,details FROM cycles ORDER BY rowid DESC LIMIT 1").fetchone()
    if latest:
        details = json.loads(latest["details"])
        text.append("最新 cycle：" + latest["status"])
        for source in details.get("source_assessments", []):
            text.append(source["source"] + ": " + source["snapshot_gate"])
    text.append("行情／成效驗證未接通時保留 unavailable；唔代表零回報或已證明 alpha。")
    return queue(store, "weekly:" + day.isoformat(), "SmartFlow 每週摘要 " + day.isoformat(), "\n".join(text) + "\n", "weekly")


def backup(store: ResearchStore, destination: Path) -> dict:
    destination = destination.resolve()
    if destination.resolve().is_relative_to(store.root.resolve()):
        raise ValueError("backup_destination_must_be_outside_state")
    destination.mkdir(parents=True, exist_ok=True)
    label = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    archive = destination / ("state-" + label + ".zip")
    files = {}
    with tempfile.TemporaryDirectory(prefix="backup-", dir=destination) as temporary:
        dbfile = Path(temporary) / "research.sqlite3"
        target = sqlite3.connect(dbfile)
        store.db.backup(target)
        target.close()
        with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as z:
            z.write(dbfile, "state/research.sqlite3")
            files["state/research.sqlite3"] = file_hash(dbfile)
            for path in sorted(store.root.rglob("*")):
                if not path.is_file() or path.name in {"research.sqlite3", "research.sqlite3-wal", "research.sqlite3-shm", "research.lock"}:
                    continue
                name = "state/" + path.relative_to(store.root).as_posix()
                z.write(path, name)
                files[name] = file_hash(path)
            for path in sorted(store.root.parent.glob("aliases*.json")) + [store.root.parent / "release.json"]:
                if path.is_file():
                    z.write(path, path.name)
                    files[path.name] = file_hash(path)
            z.writestr("backup-manifest.json", canonical({"schema": "smartflow-state-backup-v1", "files": files}))
    receipt = {"archive": str(archive), "sha256": file_hash(archive), "bytes": archive.stat().st_size,
               "files": len(files), "created_at": stamp(), "offhost": "pending_gateway_copy_and_restore_verification"}
    write_json(destination / "latest.json", receipt)
    return receipt


def scheduled(root: Path, inbox: Path, executable: Path, exports: Path, *, research: bool = True, news_root: Path | None = None) -> dict:
    from .__main__ import single_writer
    from .automation import cycle
    with single_writer(root):
        store = ResearchStore(root)
        result = {"status": "maintenance_only"}
        attempt = {"id": uuid.uuid4().hex, "started_at": stamp(), "status": "running", "research": research}
        try:
            write_json(exports / "latest-attempt.json", attempt)
            if research:
                incoming = read_json(inbox)
                bundle = beneath(inbox.parent, incoming["directory"])
                for name, expected in incoming["files"].items():
                    if file_hash(beneath(bundle, name)) != expected:
                        raise ValueError("scheduled_input_bundle_tamper")
                result = cycle(store, bundle / "aliases.json", bundle / "snapshots", bundle / "company", executable,
                               as_of=datetime.now(timezone.utc), news_root=news_root)
                if result["status"] in {"approved", "no_material_change", "health_only"}:
                    recovered(store)
            weekly(store, datetime.now(timezone.utc))
        except Exception as error:
            code = str(error)[:120] if isinstance(error, ValueError) else type(error).__name__
            fault(store, code)
            result = {"status": "needs_attention", "reason_code": code}
        finally:
            try:
                result["backup"] = backup(store, exports)
            except Exception as error:
                code = "backup_" + type(error).__name__
                result.update({"status": "needs_attention", "reason_code": code, "backup": {"status": "failed"}})
                fault(store, code)
            finally:
                try:
                    write_json(exports / "latest-attempt.json", {**attempt, "status": result["status"], "completed_at": stamp(), "backup": result.get("backup")})
                finally:
                    store.close()
        return result
