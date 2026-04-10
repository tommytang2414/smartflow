"""Parse SEC EDGAR Form 4 XML filings."""

from typing import Dict, Any, List, Optional
from datetime import datetime
from lxml import etree


def parse_form4_xml(xml_content: str) -> Optional[Dict[str, Any]]:
    """Parse a Form 4 XML document into structured data.

    Returns None if parsing fails or the filing is not a standard Form 4.
    """
    try:
        root = etree.fromstring(xml_content.encode() if isinstance(xml_content, str) else xml_content)
    except etree.XMLSyntaxError:
        return None

    # Try with and without namespace
    def find(element, path):
        result = element.find(path)
        if result is None:
            for child in element.iter():
                if child.tag.split("}")[-1].lower() == path.lower():
                    return child
        return result

    def find_text(element, path, default=""):
        el = find(element, path)
        return el.text.strip() if el is not None and el.text else default

    # Issuer info
    issuer = find(root, "issuer")
    if issuer is None:
        return None

    issuer_cik = find_text(issuer, "issuerCik")
    issuer_name = find_text(issuer, "issuerName")
    issuer_ticker = find_text(issuer, "issuerTradingSymbol")

    # Reporting owner
    owner_el = find(root, "reportingOwner")
    if owner_el is None:
        return None

    owner_id = find(owner_el, "reportingOwnerId")
    owner_name = find_text(owner_id, "rptOwnerName") if owner_id is not None else ""
    owner_cik = find_text(owner_id, "rptOwnerCik") if owner_id is not None else ""

    # Owner relationship
    relationship = find(owner_el, "reportingOwnerRelationship")
    is_director = find_text(relationship, "isDirector") == "1" if relationship is not None else False
    is_officer = find_text(relationship, "isOfficer") == "1" if relationship is not None else False
    officer_title = find_text(relationship, "officerTitle") if relationship is not None else ""

    # Transactions (non-derivative)
    transactions = []
    for txn_el in root.iter():
        tag = txn_el.tag.split("}")[-1] if "}" in txn_el.tag else txn_el.tag
        if tag != "nonDerivativeTransaction":
            continue

        security_title = find_text(txn_el, ".//securityTitle/value", "")
        tx_date = find_text(txn_el, ".//transactionDate/value", "")
        tx_code = find_text(txn_el, ".//transactionCoding/transactionCode", "")

        amounts = find(txn_el, ".//transactionAmounts")
        if amounts is None:
            continue

        shares = find_text(amounts, ".//transactionShares/value", "0")
        price_per_share = find_text(amounts, ".//transactionPricePerShare/value", "0")
        acq_disp = find_text(amounts, ".//transactionAcquiredDisposedCode/value", "")

        try:
            shares_float = float(shares)
            price_float = float(price_per_share) if price_per_share else 0.0
        except ValueError:
            continue

        # transactionCode: P=Purchase, S=Sale — only these are true BUY/SELL
        # M=Merger, G=Gift, F=Option exercise, W=Option grant
        # A=Acquired (can be stock option exercise), D=Disposed (can be gift)
        if tx_code == "P":
            direction = "BUY"
        elif tx_code == "S":
            direction = "SELL"
        elif tx_code in ("M", "G"):
            direction = "TRANSFER"
        else:
            direction = "HOLD"  # F, W, A, D — option exercise/grant/acquired/disposed (no cash market direction)

        transactions.append({
            "security": security_title,
            "date": tx_date,
            "code": tx_code,
            "shares": shares_float,
            "price": price_float,
            "direction": direction,
            "value": shares_float * price_float,
        })

    if not transactions:
        return None

    # Aggregate: total buy/sell value
    total_value = sum(t["value"] for t in transactions)
    net_direction = "BUY" if any(t["direction"] == "BUY" for t in transactions) else "SELL"

    # Use the first transaction's date
    traded_at = None
    if transactions[0]["date"]:
        try:
            traded_at = datetime.strptime(transactions[0]["date"], "%Y-%m-%d")
        except ValueError:
            pass

    entity_type = "insider"
    if is_officer:
        entity_type = "officer"
    elif is_director:
        entity_type = "director"

    return {
        "ticker": issuer_ticker.upper() if issuer_ticker else None,
        "issuer_name": issuer_name,
        "issuer_cik": issuer_cik,
        "entity_name": owner_name,
        "entity_cik": owner_cik,
        "entity_type": entity_type,
        "officer_title": officer_title,
        "direction": net_direction,
        "transactions": transactions,
        "total_shares": sum(t["shares"] for t in transactions if t["direction"] == net_direction),
        "total_value": total_value,
        "traded_at": traded_at,
    }
