"""Parse official SFC aggregated reportable short-position CSV files."""

import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import StringIO
from typing import Any


EXPECTED_HEADERS = (
    "Date",
    "Stock Code",
    "Stock Name",
    "Aggregated Reportable Short Positions (Shares)",
    "Aggregated Reportable Short Positions (HK$)",
)


class SFCShortCSVError(ValueError):
    pass


def _decimal(value: str, *, field: str, row_number: int) -> Decimal | None:
    normalized = value.strip().replace(",", "")
    if normalized.lower() in {"n.a.", "n.a", "na"}:
        return None
    try:
        result = Decimal(normalized)
    except (InvalidOperation, ValueError) as error:
        raise SFCShortCSVError(
            f"invalid {field} at CSV row {row_number}: {value!r}"
        ) from error
    if result < 0:
        raise SFCShortCSVError(f"negative {field} at CSV row {row_number}")
    return result


def parse_sfc_short_csv(csv_content: str) -> dict[str, Any]:
    """Parse one weekly report, enforcing its official five-column contract."""
    reader = csv.DictReader(StringIO(csv_content.lstrip("\ufeff")))
    headers = tuple(reader.fieldnames or ())
    if headers != EXPECTED_HEADERS:
        raise SFCShortCSVError(
            f"unexpected SFC short-position headers: {headers!r}"
        )

    records = []
    reporting_date = None
    seen_stock_codes: set[str] = set()
    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise SFCShortCSVError(f"unexpected extra fields at CSV row {row_number}")
        if any(value is None for value in row.values()):
            raise SFCShortCSVError(f"missing fields at CSV row {row_number}")

        try:
            row_date = datetime.strptime(row["Date"].strip(), "%d/%m/%Y").date()
        except (AttributeError, ValueError) as error:
            raise SFCShortCSVError(f"invalid reporting date at CSV row {row_number}") from error

        if reporting_date is None:
            reporting_date = row_date
        elif row_date != reporting_date:
            raise SFCShortCSVError(
                f"mixed reporting dates at CSV row {row_number}: {row_date}"
            )

        raw_stock_code = row["Stock Code"].strip()
        if not raw_stock_code.isdigit():
            raise SFCShortCSVError(f"invalid stock code at CSV row {row_number}")
        stock_code = raw_stock_code.zfill(5)
        if stock_code in seen_stock_codes:
            raise SFCShortCSVError(
                f"duplicate stock code at CSV row {row_number}: {stock_code}"
            )
        seen_stock_codes.add(stock_code)

        stock_name = row["Stock Name"].strip()
        if not stock_name:
            raise SFCShortCSVError(f"missing stock name at CSV row {row_number}")

        shares = _decimal(
            row["Aggregated Reportable Short Positions (Shares)"],
            field="short-position shares",
            row_number=row_number,
        )
        if shares is None:
            raise SFCShortCSVError(
                f"short-position shares cannot be n.a. at CSV row {row_number}"
            )
        market_value_hkd = _decimal(
            row["Aggregated Reportable Short Positions (HK$)"],
            field="short-position market value",
            row_number=row_number,
        )
        records.append(
            {
                "reporting_date": row_date,
                "stock_code": stock_code,
                "stock_name": stock_name,
                "shares": shares,
                "market_value_hkd": market_value_hkd,
            }
        )

    if reporting_date is None or not records:
        raise SFCShortCSVError("SFC short-position report contains no records")
    return {"reporting_date": reporting_date, "records": records}
