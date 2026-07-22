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

    def elements_by_local_name(element, name):
        return [item for item in element.iter() if item.tag.split("}")[-1] == name]

    issuer = find(root, "issuer")
    if issuer is None:
        return None

    issuer_cik = find_text(issuer, "issuerCik")
    issuer_name = find_text(issuer, "issuerName")
    issuer_ticker = find_text(issuer, "issuerTradingSymbol")

    reporting_owners = []
    for owner_element in elements_by_local_name(root, "reportingOwner"):
        owner_id = find(owner_element, "reportingOwnerId")
        relationship = find(owner_element, "reportingOwnerRelationship")
        is_director = (
            is_true(find_text(relationship, "isDirector")) if relationship is not None else False
        )
        is_officer = (
            is_true(find_text(relationship, "isOfficer")) if relationship is not None else False
        )
        is_ten_percent_owner = (
            is_true(find_text(relationship, "isTenPercentOwner"))
            if relationship is not None
            else False
        )
        is_other = (
            is_true(find_text(relationship, "isOther")) if relationship is not None else False
        )
        entity_type = "insider"
        if is_officer:
            entity_type = "officer"
        elif is_director:
            entity_type = "director"
        elif is_ten_percent_owner:
            entity_type = "ten_percent_owner"

        reporting_owners.append(
            {
                "entity_name": find_text(owner_id, "rptOwnerName") if owner_id is not None else "",
                "entity_cik": find_text(owner_id, "rptOwnerCik") if owner_id is not None else "",
                "entity_type": entity_type,
                "officer_title": (
                    find_text(relationship, "officerTitle") if relationship is not None else ""
                ),
                "is_director": is_director,
                "is_officer": is_officer,
                "is_ten_percent_owner": is_ten_percent_owner,
                "is_other": is_other,
            }
        )

    if not reporting_owners:
        return None

    primary_owner = reporting_owners[0]

    transactions = []
    for transaction_element in root.iter():
        tag = transaction_element.tag.split("}")[-1]
        if tag not in {"nonDerivativeTransaction", "derivativeTransaction"}:
            continue
        instrument_type = "derivative" if tag == "derivativeTransaction" else "non_derivative"

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
        exercise_price = find_text(
            transaction_element,
            ".//conversionOrExercisePrice/value",
            "",
        )
        expiration_date = find_text(
            transaction_element,
            ".//expirationDate/value",
            "",
        )
        underlying_security = find_text(
            transaction_element,
            ".//underlyingSecurityTitle/value",
            "",
        )
        underlying_shares = find_text(
            transaction_element,
            ".//underlyingSecurityShares/value",
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
                "shares_raw": shares,
                "price": price_float,
                "price_raw": price_per_share,
                "direction": direction,
                "acquired_disposed": acquired_disposed,
                "instrument_type": instrument_type,
                "exercise_price_raw": exercise_price,
                "expiration_date": expiration_date,
                "underlying_security": underlying_security,
                "underlying_shares_raw": underlying_shares,
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

    return {
        "ticker": issuer_ticker.upper() if issuer_ticker else None,
        "issuer_name": issuer_name,
        "issuer_cik": issuer_cik,
        "entity_name": primary_owner["entity_name"],
        "entity_cik": primary_owner["entity_cik"],
        "entity_type": primary_owner["entity_type"],
        "officer_title": primary_owner["officer_title"],
        "reporting_owners": reporting_owners,
        "direction": net_direction,
        "transactions": transactions,
        "total_shares": total_shares,
        "total_value": total_value,
        "traded_at": traded_at,
    }
