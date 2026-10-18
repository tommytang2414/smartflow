"""Disposable operational rehearsal: no network, model calls or live state writes."""
from __future__ import annotations

import copy
import base64
import tempfile
import sys
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
from smartflow.research.model import render_report
from smartflow.research.prices import parse as parse_prices, outcomes, contract
from smartflow.research.delivery import send, SENDER, RECIPIENT
from smartflow.research.operations import backup, queue, weekly
from smartflow.research.operations import scheduled
from smartflow.research import gateway
from smartflow.research.gateway import restore_verify
from smartflow.research.company import excerpts
from email.message import EmailMessage
from email import policy


def main():
    with tempfile.TemporaryDirectory(prefix="smartflow-readiness-") as temporary:
        root = Path(temporary)
        merger = "Each share of Class A common stock outstanding before the Effective Time will be converted\ninto the right to receive $6.05 in cash. " + "Closing conditions remain outstanding. " * 40
        assert any("$6.05 in cash" in quote["quote"] for quote in excerpts(merger))
        performance = "Gross profit increased compared with the prior year period. " * 8
        assert any("Gross profit increased" in quote["quote"] for quote in excerpts(performance))
        listing = {"security_key": "US:ACME:CLASS_A", "symbol": "ACME", "exchange": "NASDAQ", "currency": "USD", "timezone": "America/New_York"}
        body = {"status": "ok", "meta": {"symbol": "ACME", "exchange": "NASDAQ", "currency": "USD", "exchange_timezone": "America/New_York", "interval": "1day"},
                "values": [{"datetime": "2026-10-07", "open": "100", "high": "110", "low": "95", "close": "105", "volume": "10"}]}
        price_cutoff = NOW + timedelta(hours=4)
        price_rows = parse_prices(body, listing, price_cutoff)
        assert len(price_rows) == 1
        assert parse_prices(body, listing, price_cutoff-timedelta(seconds=1)) == []
        unknown = outcomes({"US:ACME:CLASS_A": price_rows, "BENCHMARK:SPY": price_rows}, "US:ACME:CLASS_A", NOW-timedelta(days=2), price_cutoff)
        assert unknown["horizons"]["1"]["stock_return_pct"] == "5.00"
        assert unknown["horizons"]["5"]["stock_return_pct"] is None
        missing = outcomes({"BENCHMARK:SPY": price_rows}, "US:ACME:CLASS_A", NOW-timedelta(days=2), price_cutoff)
        assert missing["horizons"]["1"]["status"] == "MISSING_MATCHED_STOCK_SESSION"
        duplicate = copy.deepcopy(body);duplicate["values"] *= 2
        rejects(lambda: parse_prices(duplicate, listing, NOW), "duplicate_or_weekend")
        wrong = copy.deepcopy(body);wrong["meta"]["symbol"] = "OTHER"
        rejects(lambda: parse_prices(wrong, listing, NOW), "identity")
        calls = []
        item = {"identity": "fixture-canary", "recipient": RECIPIENT, "subject": "Fixture", "text": "Test only\n", "text_sha256": digest(b"Test only\n")}
        message = EmailMessage(policy=policy.SMTP)
        message["From"], message["To"] = SENDER, RECIPIENT
        message["Subject"] = item["subject"] + " [smartflow-" + digest(item["identity"].encode())[:24] + "]"
        message["Message-ID"] = "<provider@fixture.invalid>"
        message.set_content(item["text"])
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        def fake_gws(resource, action, params, body=None, upload=None):
            calls.append((resource, action))
            if action == "getProfile": return {"emailAddress": SENDER}
            if (resource, action) == ("drafts", "create"): return {"id": "draft"}
            if (resource, action) == ("drafts", "get"): return {"message": {"raw": raw}}
            if (resource, action) == ("drafts", "send"): return {"id": "sent"}
            if (resource, action) == ("messages", "get"): return {"raw": raw, "labelIds": ["SENT"]}
            if action == "list": return {}
            raise AssertionError((resource, action))
        with patch("smartflow.research.delivery.gws", side_effect=fake_gws):
            assert send(item, root / "delivery")["state"] == "sent"
            assert send(item, root / "delivery")["state"] == "sent"
            assert calls.count(("drafts", "send")) == 1
            uncertain = root / "delivery" / digest(item["identity"].encode())[:24] / "delivery.json"
            from smartflow.research.common import read_json
            state = read_json(uncertain);state.pop("gmail_message_id");state["state"] = "sending";write_json(uncertain, state)
            rejects(lambda: send(item, root / "delivery"), "uncertain_send")
            assert calls.count(("drafts", "send")) == 1
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
            rejects(lambda: aliases(identity, [{**definitions[0], "instrument_type": "UNKNOWN"}]), "invalid_alias_contract")
            target = definitions[0]["security_key"]
            focused = build_pack(store, definitions, as_of=NOW, security_keys=[target])
            assert [d["security_key"] for d in focused["dossiers"]] == [target]
            assert focused["not_reviewed_candidates"] == focused["total_candidates"] - 1
            rejects(lambda: build_pack(store, definitions, as_of=NOW, security_keys=[target, target]), "targeted_security_keys_invalid")
            rejects(lambda: build_pack(store, definitions, as_of=NOW, security_keys=["US:UNKNOWN:COMMON"]), "targeted_security_keys_invalid")
            fund_definitions = [{**definitions[0], "instrument_type": "CLOSED_END_FUND"}]
            fund_packet = build_pack(store, fund_definitions, as_of=NOW, security_keys=[target])
            fund = fund_packet["dossiers"][0]
            assert fund["stance"] == "CONTEXT_ONLY" and fund["priority"] == "NO_DIRECTIONAL_EVIDENCE"
            assert fund["distinct_actors"] == 0 and fund["purchase_sources"] == fund["sale_sources"] == []
            assert fund["evidence"] and fund["identity_resolved"]
            assert "封閉式基金" in render_report(fund_packet, None, status="fixture")
            assert "營運公司方向確認 actor：0" in render_report(fund_packet, None, status="fixture")
            new_identity = copy.deepcopy(fund_packet);new_identity["bootstrap"] = False
            assert "本輪標的未有可比較嘅同身份批准結論" in render_report(new_identity, None, status="fixture")
            new_identity["dossiers"][0]["previous_approved"] = {"fixture": True}
            assert "保留上次批准研究嘅比較" in render_report(new_identity, None, status="fixture")
            # A verified alias whose proof interval is valid but no current
            # eligible records exist must never silently fall back to another name.
            with patch("smartflow.research.pack.source_assessments", return_value=[]):
                rejects(lambda: build_pack(store, definitions, as_of=NOW, security_keys=[target]), "targeted_security_has_no_eligible_current_evidence")
            fund_store = ResearchStore(root / "fund-state")
            try:
                for group in ("sec", "house", "sfc"):
                    manifest = read_json(snapshots / (group + "-manifest.json"))
                    import_snapshot(fund_store, group, snapshots / manifest["file"], manifest)
                with fund_store.db:
                    fund_store.db.execute("INSERT INTO runs(id,pack_hash,directory,status) VALUES('fund-fixture',?,'fixture','prepared')", ("e"*64,))
                    fund_store.db.execute("INSERT INTO tasks VALUES('fund-task',?,'基金身份是否已核實','pending',?,'fund-fixture')", (target, stamp(NOW)))
                assert check_due(fund_store, fund_definitions, NOW)["checked"] == 1
                assert latest_results(fund_store, NOW)[0]["checked"]["full_current_stance"] == "CONTEXT_ONLY"
            finally:
                fund_store.close()
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
            unresolved = copy.deepcopy(packet)
            for dossier in unresolved["dossiers"]:
                dossier["identity_resolved"] = False
                dossier["ticker"] = "UNVERIFIED_TICKER"
            rendered = render_report(unresolved, None, status="fixture only")
            assert "## UNVERIFIED_TICKER" not in rendered and "| UNVERIFIED_TICKER |" not in rendered
            assert "未核實標的" in rendered
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
                    store.db.execute("UPDATE runs SET status='approved',manifest_hash=?,completed_at=? WHERE id='fixture'", (file_hash(fixture_directory / "manifest.json"), stamp(NOW+timedelta(days=6))))
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
                rejects(lambda: cycle(store, aliases_path, snapshots, root, Path("unused"), as_of=NOW+timedelta(days=2,seconds=1)), "source_snapshot_stale")
                assert model.call_count == 1
                from smartflow.research.common import read_json
                import json
                previous = store.db.execute("SELECT id,details FROM cycles WHERE status='no_material_change' ORDER BY rowid DESC LIMIT 1").fetchone()
                previous_details = json.loads(previous["details"])
                for source in previous_details["source_assessments"]:
                    if source["source"] == "sfc_short": source["snapshot_gate"] = "PASS"
                with store.db:
                    store.db.execute("UPDATE cycles SET details=? WHERE id=?", (canonical(previous_details).decode(), previous["id"]))
                aged = build_pack(store, changed, as_of=NOW+timedelta(seconds=5), company=company)
                for source in aged["source_assessments"]:
                    if source["source"] == "sfc_short":
                        source.update(snapshot_gate="HOLD", health_at_snapshot="stale", event_fresh=False)
                with patch("smartflow.research.automation.build_pack", return_value=aged):
                    age_hold = cycle(store, aliases_path, snapshots, root, Path("unused"), as_of=NOW+timedelta(seconds=5))
                assert age_hold["status"] == "deferred_daily_model_budget" and model.call_count == 1
            assert store.db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
            assert not store.db.execute("PRAGMA foreign_key_check").fetchall()
            # This synthetic approved row has a deliberately minimal manifest;
            # restore verification still checks it and every real prepared file.
            queue(store, "canary:fixture", "Fixture", "Test only\n", "canary")
            saved_backup = backup(store, root / "exports")
            restored = root / "restored";restored.mkdir()
            restored_db, verified = restore_verify(Path(saved_backup["archive"]), restored)
            assert verified["approved_runs"] == 1
            assert restored_db.execute("SELECT COUNT(*) FROM task_attempts").fetchone()[0] == 3
            restored_db.close()
            # Seven synthetic model-reviewed dates cannot activate the original
            # manual-acceptance gate. No fabricated operator receipts are added.
            with store.db:
                for day_index in range(6):
                    store.db.execute("INSERT INTO runs(id,pack_hash,directory,status,completed_at) VALUES(?,?,?,'approved',?)", ("review-day-"+str(day_index), str(day_index)*64, "unused", stamp(NOW+timedelta(days=day_index))))
            digest_note = weekly(store, NOW+timedelta(days=9,hours=4))
            assert "GPT 覆核唔代替操作者驗收" in digest_note["text"]
            with store.db:
                for accepted_id in ["fixture"] + ["review-day-"+str(i) for i in range(6)]:
                    store.db.execute("UPDATE runs SET report_hash=? WHERE id=?", ("f"*64, accepted_id))
                    store.db.execute("INSERT INTO operations VALUES(?,'owner_review','recorded',?,?)", ("owner-reviewed:"+accepted_id,
                        canonical({"run_id": accepted_id, "report_sha256": "f"*64, "actor": "explicit_owner_review_fixture"}).decode(), stamp(NOW+timedelta(days=7))))
            same_day_note = weekly(store, NOW+timedelta(days=16,hours=4))
            assert "操作者明確手動驗收日數：1" in same_day_note["text"]
            assert "GPT 覆核唔代替操作者驗收" in same_day_note["text"]
            rejects(lambda: backup(store, store.root / "exports"), "backup_destination")
            with patch("smartflow.research.operations.backup", side_effect=OSError("fixture")):
                failure = scheduled(root / "failure-state", root / "unused-inbox", Path("unused"), root / "failure-exports", research=False)
            assert failure["status"] == "needs_attention" and failure["reason_code"] == "backup_OSError"
            attempt = read_json(root / "failure-exports/latest-attempt.json")
            with patch("smartflow.research.gateway.remote", return_value=canonical(attempt).decode()):
                rejects(lambda: gateway.drain(root / "failed-drain"), "latest_scheduled_backup_failed")
            notices = []
            bridge = root / "bridge"
            with patch("smartflow.research.gateway.send", side_effect=lambda item, _: notices.append(item["identity"]) or {}), \
                 patch("smartflow.research.gateway.refresh", return_value={"status": "refreshed"}):
                with patch.object(sys, "argv", ["gateway", "drain", "--root", str(bridge)]), patch("smartflow.research.gateway.drain", side_effect=ValueError("fixture")):
                    try: gateway.main()
                    except SystemExit: pass
                with patch.object(sys, "argv", ["gateway", "refresh", "--root", str(bridge)]): gateway.main()
                assert len(notices) == 1 and notices[0].startswith("gateway-fault:")
                with patch.object(sys, "argv", ["gateway", "drain", "--root", str(bridge)]), patch("smartflow.research.gateway.drain", return_value={"status": "restore_verified"}): gateway.main()
                assert len(notices) == 2 and notices[1].startswith("gateway-recovery:")
            print(canonical({"status": "PASS", "checks": ["identity-only gift is never directional",
                "exact manual target selection; unknown, duplicate and unavailable targets rejected; fund is context only",
                "immutable due checks; replay zero; future attempt cannot suppress historical check",
                "unknown question stays open; cutoff and tamper checks",
                "follow-up originals sealed in prepared packet; interrupted approved run reconciled",
                "daily bar cutoff, identity, matched sessions and pending/missing values",
                "strict self-mail readback, replay sends once and uncertain-send never retries",
                "consistent complete state archive restored with source/run/follow-up hashes",
                "backup failure closes store, refuses old backup; independent refresh/drain fault episodes",
                "stale source blocks model; seven GPT dates cannot replace manual acceptance",
                "unchanged content skips GPT; changed content respects daily reservation",
                "SQLite integrity and foreign keys"], "network_calls": 0, "model_calls": 0}).decode())
        finally:
            store.close()


if __name__ == "__main__":
    main()
