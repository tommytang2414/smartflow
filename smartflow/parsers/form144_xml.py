"""Parse SEC EDGAR Form 144 XML filings."""

from datetime import datetime
from typing import Any, Dict, Optional

from lxml import etree

_CIK_TICKER_CACHE: Optional[Dict[str, str]] = None


def _get_cik_ticker_cache() -> Dict[str, str]:
    """Fetch SEC company_tickers.json and build a normalized CIK-to-ticker map."""
    global _CIK_TICKER_CACHE
    if _CIK_TICKER_CACHE is not None:
        return _CIK_TICKER_CACHE

    try:
        import requests

        response = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers={"User-Agent": "SmartFlow/0.1 tommytang.cc@gmail.com"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        _CIK_TICKER_CACHE = {
            str(record["cik_str"]).lstrip("0") or "0": record["ticker"]
            for record in data.values()
        }
    except Exception:
        _CIK_TICKER_CACHE = {}
    return _CIK_TICKER_CACHE


def parse_form144_xml(
    xml_content: str,
    cik_ticker_cache: Optional[Dict[str, str]] = None,
) -> Optional[Dict[str, Any]]:
    """Parse a proposed-sale notice without treating it as an executed sale."""
    try:
        root = etree.fromstring(xml_content.encode() if isinstance(xml_content, str) else xml_content)
    except etree.XMLSyntaxError:
        return None

    namespace = {"edgar": "http://www.sec.gov/edgar/ownership"}

    def find(element, path):
        return element.find(path, namespace)

    def find_text(element, path, default=""):
        item = find(element, path)
        if item is not None and item.text:
            return item.text.strip()
        return default

    form_data = find(root, "edgar:formData")
    if form_data is None:
        return None

    issuer_info = find(form_data, "edgar:issuerInfo")
    securities_info = find(form_data, "edgar:securitiesInformation")

    issuer_cik = ""
    issuer_name = ""
    filer_name = ""
    relationship = ""
    securities_title = ""
    no_of_units_sold = 0
    aggregate_market_value = 0.0
    approximate_sale_date = ""

    filer_cik = root.findtext(
        ".//edgar:headerData/edgar:filerInfo/edgar:filer/edgar:filerCredentials/edgar:cik",
        default="",
        namespaces=namespace,
    )

    if issuer_info is not None:
        issuer_cik = find_text(issuer_info, "edgar:issuerCik")
        issuer_name = find_text(issuer_info, "edgar:issuerName")
        filer_name = find_text(
            issuer_info,
            "edgar:nameOfPersonForWhoseAccountTheSecuritiesAreToBeSold",
        )
        relationship_element = find(issuer_info, "edgar:relationshipsToIssuer")
        if relationship_element is not None:
            relationship = ", ".join(
                item.text.strip()
                for item in relationship_element.iter()
                if item.tag.split("}")[-1] == "relationshipToIssuer"
                and item.text
                and item.text.strip()
            )

    if securities_info is not None:
        securities_title = find_text(securities_info, "edgar:securitiesClassTitle")
        no_of_units_sold_text = find_text(securities_info, "edgar:noOfUnitsSold", "0")
        try:
            no_of_units_sold = int(no_of_units_sold_text.replace(",", ""))
        except ValueError:
            pass

        aggregate_market_value_text = find_text(
            securities_info,
            "edgar:aggregateMarketValue",
            "0",
        )
        try:
            aggregate_market_value = float(aggregate_market_value_text.replace(",", ""))
        except ValueError:
            pass

        approximate_sale_date = find_text(securities_info, "edgar:approxSaleDate")

    if not issuer_name and not filer_name:
        return None

    proposed_sale_at = None
    if approximate_sale_date:
        for date_format in ("%m/%d/%Y", "%Y-%m-%d", "%Y%m%d"):
            try:
                proposed_sale_at = datetime.strptime(approximate_sale_date, date_format)
                break
            except ValueError:
                continue

    ticker_cache = cik_ticker_cache if cik_ticker_cache is not None else _get_cik_ticker_cache()

    return {
        "ticker": ticker_cache.get(issuer_cik.lstrip("0") or "0", ""),
        "issuer_name": issuer_name,
        "issuer_cik": issuer_cik,
        "filer_name": filer_name,
        "filer_cik": filer_cik,
        "relationship": relationship,
        "security_title": securities_title,
        "no_of_units_sold": no_of_units_sold,
        "proposed_amount": aggregate_market_value,
        "proposed_sale_at": proposed_sale_at,
    }
