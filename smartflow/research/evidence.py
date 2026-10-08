from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

from .common import canonical, digest, file_hash, readonly, stamp, utc
from .snapshots import SOURCES
from .store import ResearchStore


VERSIONS = {"sec_form4": ["sec-form4-v4"], "sec_form144": ["sec-form144-v1"],
            "congress": ["congress-house-ptr-v2", "congress-house-ptr-v3", "congress-house-ptr-v4"],
            "sfc_short": ["sfc-short-v1"]}
INTERVALS = {"sec_form4": 300, "sec_form144": 3600, "congress": 3600, "sfc_short": 86400}
AGE_DAYS = {"sec_form4": 7, "sec_form144": 7, "congress": 90, "sfc_short": 10}


def source_assessments(store: ResearchStore, as_of: datetime) -> list[dict]:
    result = []
    for state in store.db.execute("SELECT s.*,i.manifest FROM source_state s JOIN imports i ON i.identity=s.import_id ORDER BY source"):
        health = json.loads(state["health"])
        manifest = json.loads(state["manifest"])
        generated = utc(state["generated_at"])
        snapshot_fresh = timedelta(0) <= as_of - generated <= timedelta(hours=36)
        snapshot = store.root / "snapshots" / (manifest["sha256"] + ".db")
        if file_hash(snapshot) != manifest["sha256"]:
            raise ValueError("source_snapshot_cache_tamper")
        connection = readonly(snapshot)
        try:
            cutoff = generated - timedelta(days=14)
            runs = [dict(r) for r in connection.execute("SELECT * FROM collector_runs_v2 WHERE collector=? ORDER BY started_at,id", (state["source"],))
                    if cutoff <= utc(r["started_at"]) <= generated]
            interval = INTERVALS[state["source"]]
            slots = {int(utc(r["started_at"]).timestamp()) // interval for r in runs}
            expected = 14 * 86400 // interval
            good = sum(r["status"] in {"success", "empty"} and not r["failure_kind"] for r in runs)
            reliability = Decimal(good) / Decimal(len(runs)) if runs else Decimal(0)
            coverage = min(Decimal(len(slots)) / Decimal(expected), Decimal(1))
            last_details = json.loads(runs[-1]["details"] or "{}") if runs else {}
            parent_ids = {row[0] for row in connection.execute("SELECT id FROM raw_events WHERE source=?", (state["source"],))}
            child_parent_ids = {row[0] for row in connection.execute("SELECT raw_event_id FROM normalized_events_v2 WHERE source=?", (state["source"],))}
            raw_only = len(parent_ids - child_parent_ids)
            semantic_errors = rejected_raw = 0
            if state["source"] == "congress":
                from ops.audit_congress_house_shadow import audit
                semantic_errors = audit(snapshot, since_hours=336)["invalid_semantics"]
            elif state["source"] == "sfc_short":
                from ops.audit_sfc_short_shadow import audit
                audited = audit(snapshot)
                semantic_errors, rejected_raw = audited["invalid_semantics"], audited["rejected_raw"]
        finally:
            connection.close()
        reported_health = health["state"] == "healthy" and health["last_run_status"] in {"success", "empty"} and not health["last_failure_kind"]
        event_fresh = True
        if state["source"] == "sfc_short":
            event_fresh = bool(health["last_event_at"]) and timedelta(0) <= as_of - utc(health["last_event_at"]) <= timedelta(days=10)
        gate = reported_health and reliability >= Decimal("0.99") and coverage >= Decimal("0.99") and semantic_errors == rejected_raw == 0
        if state["source"] == "congress":
            gate = gate and last_details.get("reports_remaining") == 0 and raw_only == 0
        if state["source"] == "sfc_short":
            gate = gate and raw_only == 0 and event_fresh
        result.append({"source": state["source"], "generated_at": stamp(generated),
                       "version_id": manifest["version_id"], "snapshot_hash": manifest["sha256"],
                       "health_as_of": health["checked_at"], "health_at_snapshot": health["state"],
                       "current_health": "UNKNOWN_NO_LIVE_RECEIPT", "snapshot_fresh": snapshot_fresh,
                       "event_fresh": event_fresh, "window_runs": len(runs), "window_slot_coverage": str(coverage),
                       "window_reliability": str(reliability), "raw_without_children": raw_only,
                       "invalid_semantics": semantic_errors, "rejected_raw": rejected_raw,
                       "snapshot_gate": "PASS" if gate else "HOLD", "eligible_for_current_research": bool(gate and snapshot_fresh and event_fresh)})
    return result


def select_events(store: ResearchStore, as_of: datetime) -> tuple[list[dict], Counter]:
    newest = {}
    excluded = Counter()
    for row in store.db.execute("SELECT id,body,fingerprint,imported_at FROM evidence"):
        body = json.loads(row["body"])
        if digest(canonical(body)) != row["fingerprint"]:
            raise ValueError("local_evidence_fingerprint_mismatch")
        versions = VERSIONS.get(body["source"], [])
        if body["parser_version"] not in versions:
            excluded["untrusted_parser"] += 1
            continue
        key = (body["source"], body["source_event_id"])
        previous = newest.get(key)
        if previous and versions.index(previous["parser_version"]) >= versions.index(body["parser_version"]):
            excluded["superseded_parser"] += 1
            continue
        if previous:
            excluded["superseded_parser"] += 1
        body["id"] = row["id"]
        body["research_first_imported_at"] = row["imported_at"]
        newest[key] = body
    selected = []
    for body in newest.values():
        reason = eligibility(body, as_of)
        if reason:
            excluded[reason] += 1
        else:
            selected.append(body)
    return selected, excluded


def eligibility(event: dict, as_of: datetime) -> str | None:
    if event["quality_status"] != "valid":
        return "quality_warning_or_invalid"
    if not event["ticker"] or not event["security_id"]:
        return "missing_security_identity"
    if not event["event_at"] or utc(event["observed_at"]) > as_of:
        return "missing_date_or_not_yet_observed"
    source, action, side = event["source"], event["action"], event["side"]
    url = urlparse(event.get("source_url") or "")
    hosts = {"sec_form4": {"www.sec.gov", "sec.gov"}, "sec_form144": {"www.sec.gov", "sec.gov"},
             "congress": {"disclosures-clerk.house.gov"}, "sfc_short": {"www.sfc.hk", "sfc.hk"}}
    if url.scheme != "https" or url.hostname not in hosts[source] or url.username or url.password:
        return "unapproved_evidence_url"
    attrs = event["attributes"]
    if source != "sec_form144" and utc(event["event_at"]) > as_of:
        return "future_transaction_or_reporting_date"
    if event.get("filed_at") and utc(event["filed_at"]) > as_of:
        return "future_filing_date"
    if source == "sec_form4":
        if not (event["event_type"] == "form4_transaction" and event["execution_status"] == "reported"
                and attrs.get("instrument_type") == "non_derivative"
                and (attrs.get("transaction_code"), action, side) in {("P", "purchase", "BUY"), ("S", "sale", "SELL")}):
            return "not_open_market_equity_transaction"
    elif source == "sec_form144":
        if not (event["event_type"] == "form144_notice" and action == "proposed_sale" and side == "SELL" and event["execution_status"] == "proposed"):
            return "invalid_proposed_sale_contract"
    elif source == "congress":
        if not (event["event_type"] == "congress_periodic_transaction" and event["execution_status"] == "reported"
                and event["value"] is None and (action, side) in {("purchase", "BUY"), ("sale", "SELL"), ("exchange", None)}):
            return "invalid_congress_contract"
        if attrs.get("asset_type") != "ST":
            return "congress_non_stock_or_unknown_instrument"
        try:
            lower = Decimal(attrs["amount_lower"])
            upper = Decimal(attrs["amount_upper"]) if attrs.get("amount_upper") is not None else None
            if not lower.is_finite() or lower < 0 or (upper is not None and (not upper.is_finite() or upper < lower)):
                return "invalid_disclosed_range"
        except (KeyError, ArithmeticError, TypeError):
            return "invalid_disclosed_range"
    elif source == "sfc_short":
        if not (event["event_type"] == "aggregated_reportable_short_position" and action == "position_snapshot"
                and side == "SHORT" and event["execution_status"] == "reported" and not event["entity_id"]):
            return "invalid_sfc_snapshot_contract"
    for field in ("quantity", "price", "value"):
        if event.get(field) is not None:
            try:
                if not Decimal(event[field]).is_finite() or Decimal(event[field]) < 0:
                    return "invalid_numeric"
            except ArithmeticError:
                return "invalid_numeric"
    return None


def aliases(events: list[dict], definitions: list[dict]) -> dict[str, dict]:
    by_id = {event["id"]: event for event in events}
    result = {}
    for item in definitions:
        required = {"security_key", "market", "ticker", "issuer_cik", "sec_titles", "valid_from", "valid_to", "proof_ids", "company_terms"}
        if set(item) != required or item["market"] != "US" or len(item["sec_titles"]) != 1:
            raise ValueError("invalid_alias_contract")
        if item["security_key"] in result or not re.fullmatch(r"[A-Z0-9.:_-]+", item["security_key"]):
            raise ValueError("duplicate_or_invalid_alias")
        proofs = [by_id.get(key) for key in item["proof_ids"]]
        if not proofs or any(proof is None for proof in proofs):
            raise ValueError("alias_proof_not_eligible")
        sec_proofs = [proof for proof in proofs if proof["source"] == "sec_form4" and proof["ticker"] == item["ticker"]
                      and proof["security_id"].lstrip("0") == item["issuer_cik"].lstrip("0")
                      and proof["attributes"].get("security_title", "").casefold() in {title.casefold() for title in item["sec_titles"]}]
        if not sec_proofs or utc(item["valid_from"]) >= utc(item["valid_to"]) or not any(
            utc(item["valid_from"]) <= utc(proof["event_at"]) < utc(item["valid_to"]) for proof in sec_proofs):
            raise ValueError("alias_issuer_class_proof_mismatch")
        result[item["security_key"]] = item
    return result


def security_key(event: dict, definitions: dict[str, dict]) -> tuple[str, bool]:
    found = []
    for key, item in definitions.items():
        if event["market"] != item["market"] or event["ticker"] != item["ticker"]:
            continue
        # The alias interval describes the instrument at the transaction/proposal date.
        date = utc(event["event_at"])
        if not utc(item["valid_from"]) <= date < utc(item["valid_to"]):
            continue
        if event["source"] in {"sec_form4", "sec_form144"}:
            if event["security_id"].lstrip("0") != item["issuer_cik"].lstrip("0"):
                continue
            if event["source"] == "sec_form4" and event["attributes"].get("security_title", "").casefold() not in {x.casefold() for x in item["sec_titles"]}:
                continue
            # Form144 lacks share-class evidence; leave proposed notices separate.
            if event["source"] == "sec_form144":
                continue
        elif event["source"] != "congress" or event["security_id"] != "US:" + item["ticker"]:
            continue
        found.append(key)
    if len(found) > 1:
        raise ValueError("ambiguous_security_alias")
    if found:
        return found[0], True
    title = event["attributes"].get("security_title", "unknown_class")
    return "UNRESOLVED:" + digest(canonical([event["source"], event["security_id"], event["ticker"], title]))[:16], False


def actors(event: dict) -> list[str]:
    if event["source"] == "sec_form4":
        return sorted({"actor:" + digest(canonical(["sec", owner["entity_cik"].lstrip("0")]))[:16] for owner in event["entities"] if owner.get("entity_cik")})
    if event["source"] == "congress" and event["entity_id"]:
        return ["house_household:" + digest(event["entity_id"].encode())[:16]]
    return []
