"""Disposable operational rehearsal: no network, model calls or live state writes."""
from __future__ import annotations

import copy
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from ops.verify_research_prototype import NOW, event, rejects, snapshot
from smartflow.research.automation import cycle
from smartflow.research.__main__ import prepare
from smartflow.research.common import canonical, digest, file_hash, stamp, write_json
from smartflow.research.evidence import aliases, select_events
from smartflow.research.followups import check_due, latest_results
from smartflow.research.pack import build_pack
from smartflow.research.snapshots import import_snapshot
from smartflow.research.store import ResearchStore


def main():
    with tempfile.TemporaryDirectory(prefix="smartflow-readiness-") as temporary:
        root = Path(temporary)
        snapshots = root / "snapshots"
        snapshots.mkdir()
        events = [event("sec_form4", "proof"), event("congress", "house")]
        gift = event("sec_form4", "gift", action="gift", title="Class A Common Stock")
        gift["attributes"]["transaction_code"] = "G"
        gift["side"] = None
        events.append(gift)
        proposed = event("sec_form144", "proposed", action="sale")
        proposed.update(event_type="form144_notice", action="proposed_sale", execution_status="proposed", parser_version="sec-form144-v1")
        short = event("sfc_short", "short")
        short.update(event_type="aggregated_reportable_short_position", action="position_snapshot", side="SHORT", entity_id=None, market="HK", parser_version="sfc-short-v2", source_url="https://www.sfc.hk/sample.csv")
        for group, selected in (("sec", [e for e in events if e["source"] == "sec_form4"] + [proposed]),
                                ("house", [events[1]]), ("sfc", [short])):
            path, manifest = snapshot(snapshots, group, selected)
            write_json(snapshots / (group + "-manifest.json"), manifest)
        store = ResearchStore(root / "state")
        try:
            for group in ("sec", "house", "sfc"):
                from smartflow.research.common import read_json
                manifest = read_json(snapshots / (group + "-manifest.json"))
                import_snapshot(store, group, snapshots / manifest["file"], manifest)
            selected, _ = select_events(store, NOW)
            identity, _ = select_events(store, NOW, identity_only=True)
            gift_id = next(e["id"] for e in identity if e["source_event_id"] == "gift")
            assert all(e["source_event_id"] != "gift" for e in selected)
            definitions = [{"security_key": "US:ACME:CLASS_A", "market": "US", "ticker": "ACME",
                "issuer_cik": "0000000001", "sec_titles": ["Class A Common Stock"],
                "valid_from": "2026-01-01T00:00:00Z", "valid_to": "2027-01-01T00:00:00Z",
                "proof_ids": [gift_id], "company_terms": ["Acme"]}]
            assert "US:ACME:CLASS_A" in aliases(identity, definitions)
            aliases_path = root / "aliases.json"
            write_json(aliases_path, definitions)
            with store.db:
                store.db.execute("INSERT INTO runs(id,pack_hash,directory,status) VALUES('fixture',?,'fixture','prepared')", ("f"*64,))
                key = build_pack(store, definitions, as_of=NOW)["dossiers"][0]["security_key"]
                store.db.execute("INSERT INTO tasks VALUES('task',?,'未審閱完整證據','pending',?,'fixture')", (key, stamp(NOW)))
            checked = check_due(store, definitions, NOW)
            assert checked["checked"] == 1
            assert check_due(store, definitions, NOW)["checked"] == 0
            assert latest_results(store, NOW - timedelta(seconds=1)) == []
            # A future check must not suppress the task at a historical cutoff.
            assert check_due(store, definitions, NOW + timedelta(days=4))["checked"] == 1
            assert check_due(store, definitions, NOW + timedelta(days=2))["checked"] == 1
            assert store.db.execute("SELECT state FROM tasks").fetchone()[0] == "pending"
            rows = latest_results(store, NOW)
            original = store.root / store.db.execute("SELECT directory FROM task_attempts WHERE id=?", (rows[0]["id"],)).fetchone()[0] / "result.json"
            saved = original.read_bytes()
            original.write_bytes(saved + b" ")
            rejects(lambda: latest_results(store, NOW), "followup_result_tamper")
            original.write_bytes(saved)
            packet, prepared_id, prepared_directory = prepare(store, aliases_path, NOW, None)
            sealed = list((prepared_directory / "followup-originals").glob("*.json"))
            assert sealed and file_hash(sealed[0]) in {f["result_hash"] for d in packet["dossiers"] for f in d["followup_checks"]}
            company = {"fresh": True, "by_security": {}, "coverage": {}, "manifest_sha256": "c"*64}
            with patch("smartflow.research.automation.load_company", return_value=company), \
                 patch("smartflow.research.__main__.prepare", return_value=({}, "fixture", root)), \
                 patch("smartflow.research.__main__.analyze", return_value={"run_id": "fixture", "report": "fixture"}) as model:
                first = cycle(store, aliases_path, snapshots, root, Path("unused"), as_of=NOW)
                assert first["status"] == "approved" and model.call_count == 1
                second = cycle(store, aliases_path, snapshots, root, Path("unused"), as_of=NOW+timedelta(seconds=1))
                assert second["status"] == "no_material_change" and model.call_count == 1
                fixture_directory = store.root / "fixture"
                fixture_directory.mkdir()
                (fixture_directory / "REPORT.md").write_text("fixture only", encoding="utf-8")
                write_json(fixture_directory / "manifest.json", {"files": {"REPORT.md": file_hash(fixture_directory / "REPORT.md")}})
                with store.db:
                    store.db.execute("UPDATE runs SET status='approved',manifest_hash=?,completed_at=? WHERE id='fixture'", (file_hash(fixture_directory / "manifest.json"), stamp()))
                    store.db.execute("UPDATE cycles SET status='model_running' WHERE id=?", (first["cycle_id"],))
                recovered = cycle(store, aliases_path, snapshots, root, Path("unused"), as_of=NOW+timedelta(seconds=2))
                assert recovered["status"] == "no_material_change" and model.call_count == 1
                assert store.db.execute("SELECT status FROM cycles WHERE id=?", (first["cycle_id"],)).fetchone()[0] == "approved"
                # A changed exact alias manifest is material, but cannot bypass
                # the reserved daily model cycle by triggering repeatedly.
                changed = copy.deepcopy(definitions)
                changed[0]["company_terms"].append("Acme Corporation")
                write_json(aliases_path, changed)
                third = cycle(store, aliases_path, snapshots, root, Path("unused"), as_of=NOW+timedelta(seconds=3))
                assert third["status"] == "deferred_daily_model_budget" and model.call_count == 1
            assert store.db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
            assert not store.db.execute("PRAGMA foreign_key_check").fetchall()
            print(canonical({"status": "PASS", "checks": ["identity-only gift is never directional",
                "immutable due checks; replay zero; future attempt cannot suppress historical check",
                "unknown question stays open; cutoff and tamper checks",
                "follow-up originals sealed in prepared packet; interrupted approved run reconciled",
                "unchanged content skips GPT; changed content respects daily reservation",
                "SQLite integrity and foreign keys"], "network_calls": 0, "model_calls": 0}).decode())
        finally:
            store.close()


if __name__ == "__main__":
    main()
