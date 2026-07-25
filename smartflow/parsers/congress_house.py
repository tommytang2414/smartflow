"""Parse official U.S. House PTR index XML and PDF word coordinates."""

from __future__ import annotations

import re
from io import BytesIO
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from xml.etree import ElementTree


HOUSE_INDEX_URL = (
    "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip"
)
HOUSE_PTR_URL = (
    "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"
)
DATE_PATTERN = re.compile(r"^\d{2}/\d{2}/\d{4}$")
TICKER_PATTERN = re.compile(r"\(([A-Z][A-Z0-9./-]{0,9})\)(?:\s*\[[A-Z]+\])?")
EXCHANGE_TICKER_PATTERN = re.compile(
    r"\b(?:NASDAQ|NYSE|NYSEARCA|OTC(?:MKTS|QX|QB)?):\s*([A-Z][A-Z0-9./-]{0,9})\b"
)


class HouseDisclosureError(ValueError):
    pass


def _date(value: str, field: str) -> date:
    try:
        return datetime.strptime(value.strip(), "%m/%d/%Y").date()
    except ValueError as error:
        raise HouseDisclosureError(f"invalid {field}: {value!r}") from error


def parse_house_index_xml(xml_content: str, *, expected_year: int) -> list[dict[str, Any]]:
    """Return Periodic Transaction Report metadata from the official year index."""
    try:
        root = ElementTree.fromstring(xml_content)
    except ElementTree.ParseError as error:
        raise HouseDisclosureError("invalid House financial-disclosure index XML") from error
    if root.tag != "FinancialDisclosure":
        raise HouseDisclosureError(f"unexpected House index root: {root.tag}")

    reports = []
    seen_doc_ids: set[str] = set()
    for member in root.findall("Member"):
        filing_type = (member.findtext("FilingType") or "").strip()
        if filing_type != "P":
            continue
        year_text = (member.findtext("Year") or "").strip()
        doc_id = (member.findtext("DocID") or "").strip()
        first = (member.findtext("First") or "").strip()
        last = (member.findtext("Last") or "").strip()
        state_district = (member.findtext("StateDst") or "").strip()
        if year_text != str(expected_year):
            raise HouseDisclosureError(
                f"House PTR index year mismatch: {year_text!r}"
            )
        if not doc_id.isdigit() or not first or not last:
            raise HouseDisclosureError("House PTR index row is missing identity fields")
        if doc_id in seen_doc_ids:
            raise HouseDisclosureError(f"duplicate House PTR DocID: {doc_id}")
        seen_doc_ids.add(doc_id)
        reports.append(
            {
                "chamber": "house",
                "doc_id": doc_id,
                "member_name": " ".join((first, last)),
                "state_district": state_district,
                "filing_type": filing_type,
                "filing_date": _date(
                    member.findtext("FilingDate") or "",
                    "filing date",
                ),
                "source_url": HOUSE_PTR_URL.format(
                    year=expected_year,
                    doc_id=doc_id,
                ),
            }
        )
    if not reports:
        raise HouseDisclosureError("House index contains no Periodic Transaction Reports")
    return reports


def _group_lines(words: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    lines: list[list[dict[str, Any]]] = []
    for word in sorted(words, key=lambda item: (float(item["top"]), float(item["x0"]))):
        try:
            top = float(word["top"])
            x0 = float(word["x0"])
            text = str(word["text"])
        except (KeyError, TypeError, ValueError) as error:
            raise HouseDisclosureError("invalid PDF word coordinates") from error
        normalized = {"top": top, "x0": x0, "text": text}
        if not lines or abs(lines[-1][0]["top"] - top) > 1:
            lines.append([normalized])
        else:
            lines[-1].append(normalized)
    return lines


def _column_text(line: list[dict[str, Any]], start: float, end: float) -> str:
    return " ".join(
        word["text"]
        for word in sorted(line, key=lambda item: item["x0"])
        if start <= word["x0"] < end
    ).strip()


def _core_row(line: list[dict[str, Any]]) -> bool:
    transaction_date = _column_text(line, 320, 380)
    notification_date = _column_text(line, 380, 445)
    transaction_type = _column_text(line, 255, 320)
    return (
        bool(DATE_PATTERN.fullmatch(transaction_date))
        and bool(DATE_PATTERN.fullmatch(notification_date))
        and transaction_type[:1] in {"P", "S", "E"}
    )


def _amount_range(value: str) -> tuple[Decimal, Decimal | None, bool]:
    cleaned = " ".join(value.replace(",", "").split())
    over = re.fullmatch(r"Over \$(\d+(?:\.\d+)?)", cleaned, re.IGNORECASE)
    if over:
        return Decimal(over.group(1)), None, True
    exact = re.fullmatch(r"\$(\d+(?:\.\d+)?)", cleaned)
    if exact:
        amount = Decimal(exact.group(1))
        if amount <= 0:
            raise HouseDisclosureError(f"invalid House PTR amount: {value!r}")
        return amount, amount, False
    match = re.fullmatch(
        r"\$(\d+(?:\.\d+)?)\s*-\s*\$(\d+(?:\.\d+)?)",
        cleaned,
    )
    if not match:
        raise HouseDisclosureError(f"invalid House PTR amount range: {value!r}")
    try:
        lower = Decimal(match.group(1))
        upper = Decimal(match.group(2))
    except InvalidOperation as error:
        raise HouseDisclosureError(f"invalid House PTR amount range: {value!r}") from error
    if lower <= 0 or upper < lower:
        raise HouseDisclosureError(f"invalid House PTR amount range: {value!r}")
    return lower, upper, True


def _ticker(asset: str) -> str | None:
    matches = TICKER_PATTERN.findall(asset)
    if matches:
        return matches[-1].replace("/", ".")
    exchange_match = EXCHANGE_TICKER_PATTERN.search(asset)
    if exchange_match:
        return exchange_match.group(1).replace("/", ".")
    return None


def parse_house_ptr_word_pages(
    pages: list[list[dict[str, Any]]],
    *,
    report: dict[str, Any],
) -> dict[str, Any]:
    """Parse transaction rows from pdfplumber-style word coordinates."""
    if report.get("chamber") != "house" or not str(report.get("doc_id", "")).isdigit():
        raise HouseDisclosureError("invalid House PTR report metadata")

    transactions = []
    has_text_layer = any(words for words in pages)
    for page_number, words in enumerate(pages, start=1):
        lines = _group_lines(words)
        row_indexes = [index for index, line in enumerate(lines) if _core_row(line)]
        for position, line_index in enumerate(row_indexes):
            line = lines[line_index]
            asset_parts = [_column_text(line, 100, 255)]
            amount_parts = [_column_text(line, 440, 520)]
            next_row = (
                row_indexes[position + 1]
                if position + 1 < len(row_indexes)
                else len(lines)
            )
            for continuation in lines[line_index + 1 : next_row]:
                if any("\x00" in word["text"] for word in continuation):
                    break
                part = _column_text(continuation, 100, 255)
                if part:
                    asset_parts.append(part)
                amount_part = _column_text(continuation, 440, 520)
                if amount_part:
                    amount_parts.append(amount_part)
            asset = " ".join(part for part in asset_parts if part).strip()
            if not asset:
                raise HouseDisclosureError("House PTR transaction is missing asset")

            transaction_type = _column_text(line, 255, 320)
            action_code = transaction_type[:1]
            amount_lower, amount_upper, amount_is_range = _amount_range(
                " ".join(amount_parts)
            )
            transactions.append(
                {
                    "row_number": len(transactions) + 1,
                    "page_number": page_number,
                    "owner_code": _column_text(line, 60, 100) or None,
                    "asset": asset,
                    "asset_type": (
                        re.findall(r"\[([A-Z]+)\]", asset)[-1]
                        if re.findall(r"\[([A-Z]+)\]", asset)
                        else None
                    ),
                    "ticker": _ticker(asset),
                    "transaction_code": action_code,
                    "transaction_type": transaction_type,
                    "transaction_date": _date(
                        _column_text(line, 320, 380),
                        "transaction date",
                    ),
                    "notification_date": _date(
                        _column_text(line, 380, 445),
                        "notification date",
                    ),
                    "amount_lower": amount_lower,
                    "amount_upper": amount_upper,
                    "amount_is_range": amount_is_range,
                }
            )
    if not transactions:
        if not has_text_layer:
            return {
                **report,
                "document_status": "requires_ocr",
                "transactions": [],
            }
        raise HouseDisclosureError("House PTR PDF contains no recognized transactions")
    return {
        **report,
        "document_status": "parsed",
        "transactions": transactions,
    }


def extract_house_ptr_pdf(
    pdf_path: str,
    *,
    report: dict[str, Any],
) -> dict[str, Any]:
    """Extract a local official PTR PDF without performing network access."""
    try:
        import pdfplumber
    except ImportError as error:
        raise RuntimeError("pdfplumber is required for House PTR parsing") from error

    try:
        with pdfplumber.open(pdf_path) as document:
            pages = [page.extract_words() for page in document.pages]
    except Exception as error:
        raise HouseDisclosureError("could not read House PTR PDF") from error
    return parse_house_ptr_word_pages(pages, report=report)


def extract_house_ptr_pdf_bytes(
    pdf_content: bytes,
    *,
    report: dict[str, Any],
) -> dict[str, Any]:
    """Extract an official PTR PDF held in memory."""
    if not pdf_content.startswith(b"%PDF-"):
        raise HouseDisclosureError("House PTR payload is not a PDF")
    try:
        import pdfplumber
    except ImportError as error:
        raise RuntimeError("pdfplumber is required for House PTR parsing") from error

    try:
        with pdfplumber.open(BytesIO(pdf_content)) as document:
            pages = [page.extract_words() for page in document.pages]
    except Exception as error:
        raise HouseDisclosureError("could not read House PTR PDF") from error
    return parse_house_ptr_word_pages(pages, report=report)
