"""Daily bounded orchestration; sealed inputs, content changes and real receipts."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .common import beneath, canonical, digest, file_hash, read_json, stamp, write_json
from .company import load as load_company
from .followups import check_due
from .model import render_report
from .news import import_news
from .pack import build_pack
from .snapshots import KEYS, import_snapshot
from .store import ResearchStore


HKT = timezone(timedelta(hours=8))


def cycle(store: ResearchStore, definitions_path: Path, snapshots: Path, company_root: Path,
          executable: Path | None, *, as_of: datetime, news_root: Path | None = None) -> dict:
    # Called under the existing single-writer lock. A killed attempt is preserved,
    # not silently retried or converted into a no-change/success receipt.
    for row in store.db.execute("SELECT id,run_id,details FROM cycles WHERE status IN ('running','model_running')").fetchall():
        details = {**json.loads(row["details"]), "recovered_as": "interrupted_previous_writer"}
        terminal = "interrupted"
        run = store.db.execute("SELECT * FROM runs WHERE id=?", (row["run_id"],)).fetchone() if row["run_id"] else None
        if run and run["status"] == "approved":
            run_directory = beneath(store.root, run["directory"])
            if file_hash(run_directory / "manifest.json") != run["manifest_hash"]:
                raise ValueError("recovery_approved_manifest_tamper")
            for name, expected in read_json(run_directory / "manifest.json")["files"].items():
                if file_hash(beneath(run_directory, name)) != expected:
                    raise ValueError("recovery_approved_artifact_tamper")
            terminal = "approved"
            details.update({"recovered_as": "verified_approved_run", "analysis": {
                "run_id": run["id"], "report": str(run_directory / "REPORT.md"), "status": "approved"}})
        elif run and run["status"] in {"prepared", "analyzing"}:
            with store.db:
                store.db.execute("UPDATE runs SET status='needs_attention',completed_at=? WHERE id=?", (stamp(), run["id"]))
        write_json(store.root / "cycles" / row["id"] / "recovery.json", {"status": terminal, "details": details, "recorded_at": stamp()})
        with store.db:
            store.db.execute("UPDATE cycles SET status=?,completed_at=?,details=? WHERE id=?",
                             (terminal, stamp(), canonical(details).decode(), row["id"]))
    identity = "Y" + uuid.uuid4().hex[:24]
    directory = store.root / "cycles" / identity
    directory.mkdir(parents=True, exist_ok=False)
    details = {"cutoff": stamp(as_of), "model_attempted": False, "daily_model_cycle_limit": 1}
    with store.db:
        store.db.execute("INSERT INTO cycles VALUES(?,?,NULL,'running',NULL,NULL,?)",
                         (identity, stamp(as_of), canonical(details).decode()))
    material_hash, run_id = None, None
    try:
        imports = {}
        for group in KEYS:
            manifest = read_json(snapshots / (group + "-manifest.json"))
            imports[group] = import_snapshot(store, group, beneath(snapshots, manifest["file"]), manifest)
        definitions = read_json(definitions_path)
        company = load_company(company_root, definitions, as_of, store.root / "cycle-company" / identity)
        if not company["fresh"]:
            raise ValueError("company_refresh_not_fresh")
        news = import_news(news_root, definitions, as_of, store.root / "news-cache") if news_root else None
        checks = check_due(store, definitions, as_of, company)
        pack = build_pack(store, definitions, as_of=as_of, news=news, company=company)
        for source in pack["source_assessments"]:
            if not source["snapshot_fresh"]:
                raise ValueError("source_snapshot_stale:" + source["source"])
            if source["health_at_snapshot"] != "healthy" and not (
                    source["source"] == "sfc_short" and source["health_at_snapshot"] == "stale"):
                raise ValueError("source_health_at_snapshot_unhealthy:" + source["source"])
        last_cycle = store.db.execute("SELECT details FROM cycles WHERE status IN ('approved','no_material_change','health_only') ORDER BY rowid DESC LIMIT 1").fetchone()
        old_gates = {s["source"]: s["snapshot_gate"] for s in json.loads(last_cycle[0]).get("source_assessments", [])} if last_cycle else {}
        for source in pack["source_assessments"]:
            if old_gates.get(source["source"]) == "PASS" and source["snapshot_gate"] == "HOLD":
                raise ValueError("source_gate_regressed:" + source["source"])
        material_hash = digest(canonical(pack["material_inputs"]))
        write_json(directory / "CHECK.json", pack)
        previous = store.db.execute("SELECT material_hash FROM cycles WHERE status IN ('approved','no_material_change','health_only') AND id<>? ORDER BY rowid DESC LIMIT 1", (identity,)).fetchone()
        details.update({"imports": imports, "followups": checks, "material_hash": material_hash,
                        "candidate_count": pack["total_candidates"], "source_assessments": pack["source_assessments"]})
        if previous and previous[0] == material_hash:
            status = "no_material_change"
        elif not pack["dossiers"]:
            status = "health_only"
        elif executable is None:
            status = "model_not_requested"
        else:
            day = as_of.astimezone(HKT).date().isoformat()
            budget_key = "model-day:" + day
            reserved = store.db.execute("SELECT state FROM operations WHERE identity=?", (budget_key,)).fetchone()
            if reserved:
                status = "deferred_daily_model_budget"
            else:
                details["model_attempted"] = True
                with store.db:
                    store.db.execute("INSERT INTO operations VALUES(?,'model_budget','reserved',?,?)",
                                     (budget_key, canonical({"cycle_id": identity, "material_hash": material_hash}).decode(), stamp()))
                    store.db.execute("UPDATE cycles SET status='model_running',details=? WHERE id=?",
                                     (canonical(details).decode(), identity))
                from .__main__ import analyze, prepare
                prepared = prepare(store, definitions_path, as_of, news_root, company_root)
                run_id = prepared[1]
                with store.db:
                    store.db.execute("UPDATE cycles SET material_hash=?,run_id=? WHERE id=?", (material_hash, run_id, identity))
                result = analyze(store, definitions_path, executable, as_of, news_root, company_root, prepared=prepared)
                run_id, status = result["run_id"], "approved"
                details["analysis"] = result
                with store.db:
                    store.db.execute("UPDATE operations SET state='completed',updated_at=? WHERE identity=?", (stamp(), budget_key))
        result = {"cycle_id": identity, "status": status, "cutoff": stamp(as_of), "material_hash": material_hash,
                  "run_id": run_id, "model_attempted": details["model_attempted"], "followups_checked": checks["checked"],
                  "delivery": "outbox_only_until_gateway_confirmation"}
        note = ("無重大內容變化；今輪冇叫 GPT。" if status == "no_material_change" else
                "今輪冇合資格 current dossier；只更新資料狀況。" if status == "health_only" else
                "資料有變化，已用盡本日本工具模型輪次；保留待處理，唔當無變化。" if status == "deferred_daily_model_budget" else
                "GPT 分析已通過獨立覆核。" if status == "approved" else "檢查模式；未執行 GPT。")
        (directory / "STATUS.md").write_text(note + "\n\n" + render_report(pack, None, status=status), encoding="utf-8")
        write_json(directory / "receipt.json", {**result, "details": details, "completed_at": stamp()})
        with store.db:
            store.db.execute("UPDATE cycles SET status=?,completed_at=?,material_hash=?,run_id=?,details=? WHERE id=?",
                (status, stamp(), material_hash, run_id, canonical(details).decode(), identity))
        return result
    except Exception as error:
        code = str(error)[:160] if isinstance(error, ValueError) else type(error).__name__
        details["reason_code"] = code
        write_json(directory / "failure.json", {"status": "needs_attention", "reason_code": code, "recorded_at": stamp()})
        with store.db:
            store.db.execute("UPDATE cycles SET status='needs_attention',completed_at=?,details=? WHERE id=?",
                             (stamp(), canonical(details).decode(), identity))
        raise
