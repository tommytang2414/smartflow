"""Bounded evidence checks. Unknown answers stay open; no inferred motives."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta

from .common import beneath, canonical, digest, file_hash, read_json, stamp, utc, write_json
from .evidence import AGE_DAYS, aliases, security_key, select_events, source_assessments
from .insider import enrich
from .store import ResearchStore


def check_due(store: ResearchStore, definitions: list[dict], cutoff: datetime,
              company: dict | None = None, *, limit: int = 32) -> dict:
    if not 1 <= limit <= 32:
        raise ValueError("followup_check_limit")
    events, _ = select_events(store, cutoff)
    identity, _ = select_events(store, cutoff, identity_only=True)
    approved_aliases = aliases(identity, definitions)
    assessments = source_assessments(store, cutoff)
    allowed = {s["source"] for s in assessments if s["eligible_for_current_research"]}
    grouped, transitions = {}, {}
    for event in events:
        key, _ = security_key(event, approved_aliases)
        old_key, _ = security_key(event, {})
        grouped.setdefault(key, []).append(event)
        transitions.setdefault(old_key, set()).add(key)
    tasks = store.db.execute("""SELECT t.*, MAX(a.next_check_at) next_check
        FROM tasks t LEFT JOIN task_attempts a ON a.task_id=t.id AND a.cutoff<=?
        WHERE t.state='pending' AND t.created_at<=? GROUP BY t.id
        HAVING next_check IS NULL OR next_check<=?
        ORDER BY COALESCE(next_check,t.created_at),t.id LIMIT ?""", (stamp(cutoff), stamp(cutoff), stamp(cutoff), limit)).fetchall()
    results, cache = [], {}
    for task in tasks:
        original_key = task["security_key"]
        candidates = transitions.get(original_key, set())
        key = next(iter(candidates)) if len(candidates) == 1 else original_key
        if key not in cache:
            records = [e for e in grouped.get(key, []) if utc(e["observed_at"]) >= cutoff - timedelta(days=90)]
            current = [e for e in records if e["source"] in allowed
                       and utc(e["observed_at"]) >= cutoff - timedelta(days=AGE_DAYS[e["source"]])
                       and (e["source"] == "sec_form144" or utc(e["event_at"]) >= cutoff - timedelta(days=AGE_DAYS[e["source"]]))]
            sides = {e["side"] for e in current if e["source"] in {"sec_form4", "congress"} and e["action"] in {"purchase", "sale"}}
            stance = "MIXED" if sides == {"BUY", "SELL"} else "ACCUMULATION" if sides == {"BUY"} else "DISTRIBUTION" if sides == {"SELL"} else "CONTEXT_ONLY"
            raw_candidates = sorted((e for e in records if e["source"] == "sec_form4"), key=lambda e: (e["observed_at"], e["id"]), reverse=True)[:32]
            raw_checks = enrich(store, raw_candidates)
            cache[key] = {"current_evidence_ids": sorted(e["id"] for e in current),
                "history_evidence_ids": sorted(e["id"] for e in records),
                "raw_hashes": sorted({e["raw_hash"] for e in records}),
                "current_action_counts": dict(sorted(Counter(e["action"] for e in current).items())),
                "full_current_stance": stance, "raw_checks": raw_checks,
                "raw_check_limit": 32, "raw_checks_not_attempted": max(0, sum(e["source"] == "sec_form4" for e in records) - 32),
                "company_documents": (company or {}).get("by_security", {}).get(key, []),
                "company_coverage": (company or {}).get("coverage", {}).get(key, {"status": "NOT_COVERED"}),
                "alias_proofs": approved_aliases.get(key, {}).get("proof_ids", [])}
        checked = cache[key]
        question = task["question"]
        route = ("identity" if any(term in question for term in ("identity", "security_key", "對應", "標的")) else
                 "full_local_evidence" if any(term in question for term in ("未納入", "未審閱", "重複原始", "尚未審閱")) else
                 "disclosed_holdings" if "持倉" in question else
                 "issuer_context" if any(term in question for term in ("業績", "估值", "價格", "股價")) else "motivation")
        outcome = "PARTIAL" if route in {"identity", "full_local_evidence", "issuer_context", "disclosed_holdings"} and checked["history_evidence_ids"] else "UNKNOWN"
        limits = {
            "identity": "Only exact validated issuer/class proof and the same event identity may map an old task. Unresolved classes stay separate; a candidate mapping still needs reviewed interpretation.",
            "full_local_evidence": "Checked all eligible normalized local evidence in the window, not just twelve packet rows. Deterministic stance is not a reviewed investment conclusion; unimported disclosures and full exhibits remain uncovered.",
            "disclosed_holdings": "Matched up to thirty-two raw SEC rows; holdings-after is that disclosed row only. House PTR lacks complete household holdings; no total portfolio or current position inferred.",
            "issuer_context": "Checked bounded primary issuer documents. Complete earnings exhibits, valuation, prices and future performance require their own verified sources.",
            "motivation": "Public transaction records do not establish intent, tax circumstances or portfolio motives. No motive inferred from a plan flag or later issuer announcements."
        }
        body = {"schema": "smartflow-followup-v1", "task_id": task["id"], "question": question,
                "original_security_key": original_key, "checked_security_key": key,
                "route": route, "outcome": outcome, "checked": checked,
                "source_gates": [[s["source"], s["snapshot_gate"], s["eligible_for_current_research"]] for s in assessments],
                "limitation": limits[route], "resolved": False,
                "sources": [json.loads(row[0]) for row in store.db.execute("SELECT manifest FROM imports WHERE identity IN (SELECT import_id FROM source_state) ORDER BY identity")]}
        input_hash = digest(canonical(body))
        attempt_id = "F" + digest(canonical([task["id"], stamp(cutoff), input_hash]))[:24]
        directory = store.root / "followups" / attempt_id
        directory.mkdir(parents=True, exist_ok=True)
        result = {**body, "cutoff": stamp(cutoff), "next_check_at": stamp(cutoff + timedelta(days=2)), "input_hash": input_hash}
        target = directory / "result.json"
        if target.exists() and read_json(target) != result:
            raise ValueError("followup_attempt_conflict")
        if not target.exists():
            write_json(target, result)
        with store.db:
            store.db.execute("INSERT OR IGNORE INTO task_attempts VALUES(?,?,?,?,?,?,?,?)",
                (attempt_id, task["id"], stamp(cutoff), input_hash, file_hash(target), directory.relative_to(store.root).as_posix(), outcome, result["next_check_at"]))
        results.append({"attempt_id": attempt_id, "task_id": task["id"], "security_key": key, "outcome": outcome, "resolved": False})
    return {"checked": len(results), "attempts": results, "scope": "bounded_evidence_checks_not_automatic_resolution"}


def latest_results(store: ResearchStore, cutoff: datetime) -> list[dict]:
    results = []
    for row in store.db.execute("SELECT a.* FROM task_attempts a WHERE a.rowid=(SELECT MAX(b.rowid) FROM task_attempts b WHERE b.task_id=a.task_id AND b.cutoff<=?) ORDER BY a.task_id", (stamp(cutoff),)):
        target = beneath(store.root, row["directory"]) / "result.json"
        if file_hash(target) != row["result_hash"]:
            raise ValueError("followup_result_tamper")
        result = read_json(target)
        if result["task_id"] != row["task_id"] or result["input_hash"] != row["input_hash"]:
            raise ValueError("followup_result_binding")
        semantic = {**result["checked"], "company_documents": sorted(
            [d["issuer_cik"], d["accession"], d["raw_sha256"], d["text_sha256"]]
            for d in result["checked"]["company_documents"])}
        results.append({"id": row["id"], "task_id": row["task_id"], "security_key": result["checked_security_key"],
                        "route": result["route"], "outcome": row["outcome"], "checked": result["checked"],
                        "result_hash": row["result_hash"], "limitation": result["limitation"],
                        "semantic_hash": digest(canonical([result["route"], result["outcome"], semantic, result["source_gates"]]))})
    return results
