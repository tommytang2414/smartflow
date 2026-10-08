from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from .common import canonical, digest, stamp, utc
from .evidence import AGE_DAYS, actors, aliases, security_key, select_events, source_assessments
from .store import ResearchStore


LIMITATIONS = {
    "sec_form4": "披露交易唔代表目前持倉或交易動機；只包含有效 non-derivative P/S。",
    "sec_form144": "出售意向，唔係已執行 sale；缺 share-class identity 時另列。",
    "congress": "延遲披露；金額係 range，同一 member household 唔算多個 actor。",
    "sfc_short": "匿名 weekly net-short snapshot，唔係賣出交易或已識別持有人。",
}


def build_pack(store: ResearchStore, definitions: list[dict], *, as_of: datetime,
               news: dict | None = None, max_stocks: int = 5) -> dict:
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
    return {"schema_version": "smartflow-research-pack-v1", "as_of": stamp(as_of), "mode": "personal_research_report_only",
            "bootstrap": not bool(analyzed), "source_assessments": states, "source_exclusions": dict(sorted(exclusions.items())),
            "alias_hash": digest(canonical(definitions)), "total_candidates": len(candidates), "not_reviewed_candidates": max(0, len(candidates) - max_stocks),
            "dossiers": chosen, "news_coverage": (news or {}).get("coverage", {"status": "NOT_IMPORTED", "us_issuer_macro": "NOT_COVERED"}),
            "research_policy": "Deterministic facts and priorities; proposed sales and HK short positions are context only. AI inferences remain hypotheses, not trade instructions."}
