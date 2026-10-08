from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from .common import canonical, digest, stamp, utc
from .evidence import AGE_DAYS, actors, aliases, security_key, select_events, source_assessments
from .store import ResearchStore
from .insider import enrich


LIMITATIONS = {
    "sec_form4": "披露交易唔代表目前持倉或交易動機；non-derivative P/S 包括 open-market 或 private purchase/sale。",
    "sec_form144": "出售意向，唔係已執行 sale；缺 share-class identity 時另列。",
    "congress": "延遲披露；金額係 range，同一 member household 唔算多個 actor。",
    "sfc_short": "匿名 weekly net-short snapshot，唔係賣出交易或已識別持有人。",
}


def build_pack(store: ResearchStore, definitions: list[dict], *, as_of: datetime,
               news: dict | None = None, max_stocks: int = 5, company: dict | None = None) -> dict:
    events, exclusions = select_events(store, as_of)
    definitions_by_key = aliases(events, definitions)
    states = source_assessments(store, as_of)
    allowed = {item["source"] for item in states if item["eligible_for_current_research"]}
    grouped = defaultdict(list)
    identities = {}
    for event in events:
        key, resolved = security_key(event, definitions_by_key)
        identities[key] = {"security_key": key, "ticker": event["ticker"], "market": event["market"], "identity_resolved": resolved}
        grouped[key].append(event)
    analyzed = {row[0] for row in store.db.execute("SELECT evidence_id FROM analyzed")}
    first_approval = store.db.execute("SELECT completed_at FROM runs WHERE status='approved' ORDER BY rowid LIMIT 1").fetchone()
    candidates = []
    for key, records in grouped.items():
        current = [event for event in records if event["source"] in allowed
                   and utc(event["observed_at"]) >= as_of - timedelta(days=AGE_DAYS[event["source"]])
                   and (event["source"] == "sec_form144" or utc(event["event_at"]) >= as_of - timedelta(days=AGE_DAYS[event["source"]]))]
        if not current:
            continue
        buy_actors, sale_actors = set(), set()
        buy_sources, sale_sources = set(), set()
        unknown_actors = 0
        for event in current:
            if event["source"] not in {"sec_form4", "congress"} or event["action"] not in {"purchase", "sale"}:
                continue
            people = actors(event)
            unknown_actors += not bool(people)
            if event["action"] == "purchase":
                buy_actors.update(people)
                buy_sources.add(event["source"])
            else:
                sale_actors.update(people)
                sale_sources.add(event["source"])
        stance = "MIXED" if buy_sources and sale_sources else "ACCUMULATION" if buy_sources else "DISTRIBUTION" if sale_sources else "CONTEXT_ONLY"
        actor_count = len(buy_actors | sale_actors)
        priority = "FOLLOW_UP_HIGH" if stance == "MIXED" or max(len(buy_sources), len(sale_sources)) >= 2 or actor_count >= 3 else "FOLLOW_UP_MEDIUM" if actor_count >= 2 else "FOLLOW_UP_LOW" if stance != "CONTEXT_ONLY" else "NO_DIRECTIONAL_EVIDENCE"
        previous = store.previous(key)
        # An initial import is bootstrap context, not thousands of new alert events.
        new_ids = [event["id"] for event in current if event["id"] not in analyzed
                   and utc(event["research_first_imported_at"]) > utc(first_approval[0])] if first_approval else []
        history = [event for event in records if utc(event["observed_at"]) >= as_of - timedelta(days=90)]
        ordered = sorted(history, key=lambda event: (event not in current, event["id"] not in new_ids, -utc(event["observed_at"]).timestamp(), event["id"]))
        # Reserve both sides/sources and multiple actors before filling the bounded context.
        reserved, seen_units = [], set()
        for event in ordered:
            unit = (event["source"], event["action"])
            if unit not in seen_units:
                reserved.append(event)
                seen_units.add(unit)
        seen_units = set()
        for event in ordered:
            unit = (event["source"], event["action"], tuple(actors(event)))
            if unit not in seen_units and event not in reserved and len(reserved) < 8:
                reserved.append(event)
                seen_units.add(unit)
        chosen = reserved + [event for event in ordered if event not in reserved][:max(0, 12 - len(reserved))]
        evidence = [{"id": event["id"], "source": event["source"], "action": event["action"],
                     "execution_status": event["execution_status"], "event_at": event["event_at"],
                     "filed_at": event["filed_at"], "observed_at": event["observed_at"], "public_available_at": None,
                     "value": event["value"], "quantity": event["quantity"], "currency": event["currency"],
                     "amount_lower": event["attributes"].get("amount_lower"), "amount_upper": event["attributes"].get("amount_upper"),
                     "source_url": event["source_url"], "raw_hash": event["raw_hash"], "parser_version": event["parser_version"],
                     "actor_ids": actors(event), "current_window": event in current,
                     "transaction_code": event["attributes"].get("transaction_code"),
                     "issuer_cik": event["security_id"] if event["source"] == "sec_form4" else None,
                     "source_current_eligible": event["source"] in allowed,
                     "new_since_approved_analysis": event["id"] in new_ids} for event in chosen]
        tasks = [dict(row) for row in store.db.execute("SELECT id,question,created_at FROM tasks WHERE security_key=? AND state='pending' ORDER BY created_at LIMIT 3", (key,))]
        candidates.append({**identities[key], "stance": stance, "priority": priority, "distinct_actors": actor_count,
                           "unknown_actor_events": unknown_actors, "purchase_sources": sorted(buy_sources), "sale_sources": sorted(sale_sources),
                           "current_evidence_count": len(current), "history_evidence_count": len(history),
                           "not_in_packet_count": len(history) - len(chosen), "new_evidence_count": len(new_ids),
                           "unreviewed_evidence_count": sum(event["id"] not in analyzed for event in current),
                           "evidence": evidence, "previous_approved": previous, "pending_tasks": tasks,
                           "limitations": [LIMITATIONS[source] for source in sorted({event["source"] for event in history})]
                           + [source + " 未過 current source gate；相關個別已驗證事件只作歷史 context，唔計入本輪 stance／actor confirmation。"
                              for source in sorted({event["source"] for event in history} - allowed)],
                           "news": (news or {}).get("by_security", {}).get(key, [])})
    order = {"FOLLOW_UP_HIGH": 0, "FOLLOW_UP_MEDIUM": 1, "FOLLOW_UP_LOW": 2, "NO_DIRECTIONAL_EVIDENCE": 3}
    candidates.sort(key=lambda item: (order[item["priority"]], -int(item["identity_resolved"]), -item["new_evidence_count"], -item["distinct_actors"], item["ticker"]))
    chosen = candidates[:max_stocks]
    selected_ids = {record["id"] for dossier in chosen for record in dossier["evidence"]}
    contexts = enrich(store, [event for event in events if event["id"] in selected_ids])
    for dossier in chosen:
        for event in dossier["evidence"]:
            event["insider_context"] = contexts.get(event["id"])
        dossier["company_documents"] = (company or {}).get("by_security", {}).get(dossier["security_key"], [])
        dossier["company_coverage"] = (company or {}).get("coverage", {}).get(dossier["security_key"], {"status": "IDENTITY_UNRESOLVED" if not dossier["identity_resolved"] else "NOT_IMPORTED"})
        dossier["price_context"] = (company or {}).get("prices", {"status": "NOT_IMPORTED", "returns": None, "volume": None})
        dossier["company_context_fresh"] = bool(dossier["company_documents"]) and (company or {}).get("fresh", False)
        previous_dossier = store.previous_dossier(dossier["security_key"]) if dossier["previous_approved"] else None
        dossier["company_document_change"] = company_change(dossier["company_documents"], previous_dossier)
        sec_records = [e for e in grouped[dossier["security_key"]] if e["source"] == "sec_form4"
                       and utc(e["observed_at"]) >= as_of - timedelta(days=90)]
        repeats = defaultdict(set)
        for event in sec_records:
            if actors(event):
                repeats[(tuple(actors(event)), event["action"])].add(event["raw_identity"])
        dossier["historical_insider_activity"] = {"window_days": 90, "events": len(sec_records),
            "distinct_filings": len({e["raw_identity"] for e in sec_records}),
            "distinct_actors": len({a for e in sec_records for a in actors(e)}),
            "repeat_actor_action_groups": sum(len(filings) >= 2 for filings in repeats.values()), "current_confirmation": False,
            "meaning": "Filing-owner/action groups recur across distinct filings; not transaction attribution, independent conviction or a buy cluster"}
    return {"schema_version": "smartflow-research-pack-v2", "as_of": stamp(as_of), "mode": "personal_research_report_only",
            "bootstrap": not bool(analyzed), "source_assessments": states, "source_exclusions": dict(sorted(exclusions.items())),
            "alias_hash": digest(canonical(definitions)), "total_candidates": len(candidates), "not_reviewed_candidates": max(0, len(candidates) - max_stocks),
            "dossiers": chosen, "news_coverage": (news or {}).get("coverage", {"status": "NOT_IMPORTED", "us_issuer_macro": "NOT_COVERED"}),
            "company_context_manifest": (company or {}).get("manifest_sha256"),
            "company_context_fresh": (company or {}).get("fresh", False),
            "research_policy": "Deterministic facts and priorities; proposed sales and HK short positions are context only. AI inferences remain hypotheses, not trade instructions."}


def company_change(documents: list[dict], previous: dict | None) -> dict:
    def key(doc):
        # A new retrieval/receipt ID is not a new issuer filing or new content.
        return digest(canonical([doc["issuer_cik"], doc["accession"], doc["raw_sha256"], doc["text_sha256"]]))
    comparable = previous is not None and bool(previous.get("company_documents")) and previous.get("company_coverage", {}).get("status") == "BOUNDED_RECENT_FILINGS"
    old = {key(doc) for doc in previous["company_documents"]} if comparable else set()
    current = {key(doc) for doc in documents}
    status = "NO_CURRENT_COMPANY_ORIGINALS" if not documents else "NO_VERIFIED_PREVIOUS_DOSSIER" if previous is None else "NO_COMPARABLE_PREVIOUS_COMPANY_CONTEXT" if not comparable else "UNCHANGED" if old == current else "CHANGED"
    return {"basis": "issuer_accession_raw_and_text_content_not_retrieval_time",
            "status": status,
            "new_original_ids": [doc["id"] for doc in documents if key(doc) not in old] if comparable and documents else [],
            "unchanged_original_ids": [doc["id"] for doc in documents if key(doc) in old] if comparable else [],
            "removed_original_keys": sorted(old - current) if comparable and documents else []}
