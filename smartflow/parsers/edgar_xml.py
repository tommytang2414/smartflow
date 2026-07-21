"""Parse SEC EDGAR Form 4 XML filings."""

from datetime import datetime
from typing import Any, Dict, Optional

from lxml import etree


def parse_form4_xml(xml_content: str) -> Optional[Dict[str, Any]]:
    """Parse a Form 4 XML document into structured data."""
    try:
        root = etree.fromstring(xml_content.encode() if isinstance(xml_content, str) else xml_content)
    except etree.XMLSyntaxError:
        return None

    def find(element, path):
        result = element.find(path)
        if result is None:
            for child in element.iter():
                if child.tag.split("}")[-1].lower() == path.lower():
                    return child
        return result

    def find_text(element, path, default=""):
        item = find(element, path)
        return item.text.strip() if item is not None and item.text else default

    def is_true(value: str) -> bool:
        return value.strip().lower() in {"1", "true"}

    issuer = find(root, "issuer")
    if issuer is None:
        return None

    issuer_cik = find_text(issuer, "issuerCik")
    issuer_name = find_text(issuer, "issuerName")
    issuer_ticker = find_text(issuer, "issuerTradingSymbol")

    owner_el = find(root, "reportingOwner")
    if owner_el is None:
        return None

    owner_id = find(owner_el, "reportingOwnerId")
    owner_name = find_text(owner_id, "rptOwnerName") if owner_id is not None else ""
    owner_cik = find_text(owner_id, "rptOwnerCik") if owner_id is not None else ""

    relationship = find(owner_el, "reportingOwnerRelationship")
    is_director = is_true(find_text(relationship, "isDirector")) if relationship is not None else False
    is_officer = is_true(find_text(relationship, "isOfficer")) if relationship is not None else False
    officer_title = find_text(relationship, "officerTitle") if relationship is not None else ""

    transactions = []
    for transaction_element in root.iter():
        tag = transaction_element.tag.split("}")[-1]
        if tag != "nonDerivativeTransaction":
            continue

        security_title = find_text(transaction_element, ".//securityTitle/value", "")
        transaction_date = find_text(transaction_element, ".//transactionDate/value", "")
        transaction_code = find_text(transaction_element, ".//transactionCoding/transactionCode", "")

        amounts = find(transaction_element, ".//transactionAmounts")
        if amounts is None:
            continue

        shares = find_text(amounts, ".//transactionShares/value", "0")
        price_per_share = find_text(amounts, ".//transactionPricePerShare/value", "0")
        acquired_disposed = find_text(
            amounts,
            ".//transactionAcquiredDisposedCode/value",
            "",
        )

        try:
            shares_float = float(shares)
            price_float = float(price_per_share) if price_per_share else 0.0
        except ValueError:
            continue

        # Only P/S represent open-market or private purchase/sale direction.
        # Preserve all other SEC codes without creating false buy/sell signals.
        if transaction_code == "P":
            direction = "BUY"
        elif transaction_code == "S":
            direction = "SELL"
        elif transaction_code == "G":
            direction = "TRANSFER"
        else:
            direction = "HOLD"

        transactions.append(
            {
                "security": security_title,
                "date": transaction_date,
                "code": transaction_code,
                "shares": shares_float,
                "price": price_float,
                "direction": direction,
                "acquired_disposed": acquired_disposed,
                "value": shares_float * price_float,
            }
        )

    if not transactions:
        return None

    directional_transactions = [
        transaction
        for transaction in transactions
        if transaction["direction"] in {"BUY", "SELL"}
    ]
    directions = {transaction["direction"] for transaction in directional_transactions}
    if directions == {"BUY", "SELL"}:
        net_direction = "MIXED"
    elif directions == {"BUY"}:
        net_direction = "BUY"
    elif directions == {"SELL"}:
        net_direction = "SELL"
    elif all(transaction["direction"] == "TRANSFER" for transaction in transactions):
        net_direction = "TRANSFER"
    else:
        net_direction = "HOLD"

    # Non-market grants, gifts and exercises must not inflate directional notional.
    total_value = sum(transaction["value"] for transaction in directional_transactions)
    total_shares = sum(transaction["shares"] for transaction in directional_transactions)

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
        "total_shares": total_shares,
        "total_value": total_value,
        "traded_at": traded_at,
    }
