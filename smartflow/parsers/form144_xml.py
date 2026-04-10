"""Parse SEC EDGAR Form 144 XML filings."""

from typing import Dict, Any, Optional
from datetime import datetime
from lxml import etree

# CIK → ticker cache fetched once from SEC
_CIK_TICKER_CACHE: Optional[Dict[str, str]] = None


def _get_cik_ticker_cache() -> Dict[str, str]:
    """Fetch SEC company_tickers.json and build CIK→ticker mapping."""
    global _CIK_TICKER_CACHE
    if _CIK_TICKER_CACHE is not None:
        return _CIK_TICKER_CACHE

    try:
        import requests
        resp = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers={"User-Agent": "SmartFlow/0.1 tommytang.cc@gmail.com"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        # Structure: {"cik": "0000320193", "ticker": "AAPL", "name": "Apple Inc"}
        _CIK_TICKER_CACHE = {str(r["cik"]).lstrip("0") or str(r["cik"]): r["ticker"] for r in data.values()}
    except Exception:
        _CIK_TICKER_CACHE = {}
    return _CIK_TICKER_CACHE
def parse_form144_xml(xml_content: str) -> Optional[Dict[str, Any]]:
    """Parse a Form 144 XML document into structured data.

    Form 144 is a notice of proposed sale of securities — direction is always SELL.
    Returns None if parsing fails.
    """
    try:
        root = etree.fromstring(xml_content.encode() if isinstance(xml_content, str) else xml_content)
    except etree.XMLSyntaxError:
        return None

    ns = {"edgar": "http://www.sec.gov/edgar/ownership"}

    def ns_find(element, path):
        return element.find(path, ns)

    def ns_find_text(element, path, default=""):
        el = ns_find(element, path)
        if el is not None and el.text:
            return el.text.strip()
        return default

    def iter_find_text(element, tag_name, default=""):
        for el in element.iter():
            if el.tag.split("}")[-1].lower() == tag_name.lower() and el.text:
                return el.text.strip()
        return default

    form_data = ns_find(root, "edgar:formData")
    if form_data is None:
        return None

    issuer_info = ns_find(form_data, "edgar:issuerInfo")
    securities_info = ns_find(form_data, "edgar:securitiesInformation")

    issuer_cik = ""
    issuer_name = ""
    filer_name = ""
    relationship = ""
    ticker = ""
    securities_title = ""
    no_of_units_sold = 0
    aggregate_market_value = 0.0
    approx_sale_date = ""

    header_data = ns_find(root, "edgar:headerData")
    filer_cik = ""
    if header_data is not None:
        filer_cik = root.findtext(
            ".//edgar:headerData/edgar:filerInfo/edgar:filer/edgar:filerCredentials/edgar:cik",
            namespaces=ns
        ) or ""

    if issuer_info is not None:
        issuer_cik = ns_find_text(issuer_info, "edgar:issuerCik")
        issuer_name = ns_find_text(issuer_info, "edgar:issuerName")
        filer_name = ns_find_text(issuer_info, "edgar:nameOfPersonForWhoseAccountTheSecuritiesAreToBeSold")
        rel_el = ns_find(issuer_info, "edgar:relationshipsToIssuer")
        if rel_el is not None:
            relationship = iter_find_text(rel_el, "")

    if securities_info is not None:
        securities_title = ns_find_text(securities_info, "edgar:securitiesClassTitle")
        no_of_units_sold_str = ns_find_text(securities_info, "edgar:noOfUnitsSold", "0")
        try:
            no_of_units_sold = int(no_of_units_sold_str.replace(",", ""))
        except ValueError:
            pass

        agg_mv_str = ns_find_text(securities_info, "edgar:aggregateMarketValue", "0")
        try:
            aggregate_market_value = float(agg_mv_str.replace(",", ""))
        except ValueError:
            pass

        approx_sale_date = ns_find_text(securities_info, "edgar:approxSaleDate")

    if not issuer_name and not filer_name:
        return None

    traded_at = None
    if approx_sale_date:
        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%Y%m%d"):
            try:
                traded_at = datetime.strptime(approx_sale_date, fmt)
                break
            except ValueError:
                continue

    return {
        "ticker": _get_cik_ticker_cache().get(issuer_cik.lstrip("0"), ""),
        "issuer_name": issuer_name,
        "issuer_cik": issuer_cik,
        "filer_name": filer_name,
        "filer_cik": filer_cik,
        "relationship": relationship,
        "security_title": securities_title,
        "no_of_units_sold": no_of_units_sold,
        "proposed_amount": aggregate_market_value,
        "traded_at": traded_at,
    }
