"""Derived Form 4 context; never changes normalized transactions or source gates."""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree as ET

from .common import canonical, digest, readonly, utc


VERSION = "form4-research-context-v1"


def text(node, path: str, default: str = "") -> str:
    found = node.find(path)
    return (found.text or "").strip() if found is not None else default


def derive(event: dict, xml: str) -> dict:
    base = {"version": VERSION, "raw_hash": event["raw_hash"], "status": "UNKNOWN_TRANSACTION_MATCH",
            "owners": event["entities"], "limitations": [
                "P/S 包括 open-market 或 private 交易；唔由代碼推斷公開市場成交。",
                "計劃標記屬 filing-level；持倉數量只屬該行披露，唔代表目前全部持倉。",
                "reporting owners 屬整份 filing；多 owner 唔逐筆分配交易／金額或視作獨立 conviction。"]}
    if len(xml.encode()) > 10 * 1024 * 1024 or "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
        raise ValueError("unsafe_form4_context_xml")
    root = ET.fromstring(xml)
    for node in root.iter():
        node.tag = node.tag.split("}")[-1]
    if text(root, "issuer/issuerCik").lstrip("0") != event["security_id"].lstrip("0"):
        return base
    # Reconstruct the production parser's accepted order, including derivatives
    # and excluding missing amounts/invalid float strings before assigning IDs.
    accepted = []
    for ordinal, node in enumerate(n for n in root.iter() if n.tag in {"nonDerivativeTransaction", "derivativeTransaction"}):
        amounts = node.find(".//transactionAmounts")
        if amounts is None:
            continue
        shares = text(amounts, ".//transactionShares/value", "0")
        price = text(amounts, ".//transactionPricePerShare/value", "0")
        try:
            float(shares)
            float(price) if price else 0.0
        except ValueError:
            continue
        accepted.append((ordinal, node, shares, price or "0"))
    matches = []
    for index, (ordinal, node, shares, price) in enumerate(accepted):
        identity = "sec_form4:" + digest(json.dumps([event["raw_identity"], index], ensure_ascii=False, separators=(",", ":")).encode())
        if identity != event["source_event_id"]:
            continue
        try:
            matched = (node.tag == "nonDerivativeTransaction"
                       and text(node, ".//securityTitle/value") == event["attributes"]["security_title"]
                       and text(node, ".//transactionCoding/transactionCode") == event["attributes"]["transaction_code"]
                       and text(node, ".//transactionAmounts/transactionAcquiredDisposedCode/value") == event["attributes"]["acquired_disposed"]
                       and text(node, ".//transactionDate/value") == utc(event["event_at"]).date().isoformat()
                       and Decimal(shares) == Decimal(event["quantity"])
                       and Decimal(price) == Decimal(event["price"]))
        except (InvalidOperation, TypeError):
            matched = False
        if matched:
            matches.append((index, ordinal, node, shares, price))
    if len(matches) != 1:
        return base
    index, ordinal, node, shares, price = matches[0]
    footnotes = {n.get("id"): " ".join("".join(n.itertext()).split()) for n in root.findall(".//footnotes/footnote")}
    fields = {}
    for name, path in {"coding": "transactionCoding", "shares": "transactionAmounts/transactionShares",
                       "price": "transactionAmounts/transactionPricePerShare", "holdings_after": "postTransactionAmounts/sharesOwnedFollowingTransaction",
                       "ownership": "ownershipNature"}.items():
        field = node.find(path)
        refs = [n.get("id") for n in field.iter("footnoteId")] if field is not None else []
        fields[name] = [{"id": ref, "text": footnotes.get(ref), "status": "FOUND" if ref in footnotes else "MISSING"} for ref in refs]
    indicator = text(root, "aff10b5One").lower()
    result = {**base, "status": "MATCHED", "accepted_transaction_index": index, "xml_transaction_ordinal": ordinal,
              "filing_plan_indicator": True if indicator in {"true", "1"} else False if indicator in {"false", "0"} else None,
              "plan_indicator_locator": "ownershipDocument/aff10b5One", "disclosed_quantity": shares,
              "disclosed_price": price, "computed_disclosed_notional": str(Decimal(shares) * Decimal(price)),
              "notional_basis": "quantity_times_disclosed_price_may_be_weighted_average",
              "holdings_after": text(node, "postTransactionAmounts/sharesOwnedFollowingTransaction/value") or None,
              "ownership_kind": text(node, "ownershipNature/directOrIndirectOwnership/value") or None,
              "nature_of_ownership": text(node, "ownershipNature/natureOfOwnership/value") or None,
              "field_footnotes": fields, "position_percentage": None,
              "position_percentage_status": "NOT_INFERRED_DISCLOSED_LINE_IS_NOT_TOTAL_CURRENT_POSITION"}
    result["context_sha256"] = digest(canonical(result))
    return result


def enrich(store, events: list[dict]) -> dict[str, dict]:
    selected = [e for e in events if e["source"] == "sec_form4"]
    if not selected:
        return {}
    state = store.db.execute("SELECT i.manifest FROM source_state s JOIN imports i ON i.identity=s.import_id WHERE s.source='sec_form4'").fetchone()
    if not state:
        return {}
    manifest = json.loads(state[0])
    connection = readonly(store.root / "snapshots" / (manifest["sha256"] + ".db"))
    result = {}
    try:
        for event in selected:
            row = connection.execute("SELECT payload,payload_sha256 FROM raw_events WHERE source='sec_form4' AND source_event_id=?", (event["raw_identity"],)).fetchone()
            if not row:
                result[event["id"]] = {"status": "RAW_NOT_IN_LATEST_SNAPSHOT", "owners": event["entities"], "version": VERSION}
                continue
            payload = json.loads(row[0])
            if digest(canonical(payload)) != event["raw_hash"] or row[1] != event["raw_hash"]:
                raise ValueError("form4_context_raw_hash_mismatch")
            result[event["id"]] = derive(event, payload["xml"]) if isinstance(payload.get("xml"), str) else {"status": "RAW_XML_UNAVAILABLE", "owners": event["entities"], "version": VERSION}
    finally:
        connection.close()
    return result
