"""SEC EDGAR SC 13D / 13G Collector — Activist & Passive Investor Filings.

SC 13D = Activist investor (beneficial owner >=5%, intends to influence management)
SC 13G = Passive investor (beneficial owner >=5%, no intent to influence)

Source: EDGAR Atom feed
- 13D: https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=SC+13D&output=atom
- 13G: https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=SC+13G&output=atom

signal_type: activist_new_position, activist_increase, activist_decrease
             passive_new_position, passive_increase, passive_decrease
"""

import requests
from datetime import datetime
from typing import List, Dict, Any, Optional
from lxml import etree
from smartflow.collectors.base import BaseCollector
from smartflow.config import SEC_EDGAR_EMAIL, SEC_EDGAR_RATE_LIMIT
from smartflow.utils import RateLimiter, retry

EDGAR_FEED_URL = "https://www.sec.gov/cgi-bin/browse-edgar"


class SEC13DCollector(BaseCollector):
    """Collect SC 13D (activist) and SC 13G (passive) filings from SEC EDGAR."""

    name = "sec_13d"
    market = "US"

    def __init__(self, count: int = 100):
        super().__init__()
        if not SEC_EDGAR_EMAIL:
            self.logger.warning("SEC_EDGAR_EMAIL not set — EDGAR requires contact email in User-Agent")
        self.count = count
        self.rate_limiter = RateLimiter(SEC_EDGAR_RATE_LIMIT)
        self.headers = {
            "User-Agent": f"SmartFlow/0.1 ({SEC_EDGAR_EMAIL})" if SEC_EDGAR_EMAIL else "SmartFlow/0.1",
            "Accept-Encoding": "gzip, deflate",
        }

    @retry(max_attempts=3)
    def _get(self, url: str, params: dict = None) -> requests.Response:
        self.rate_limiter.wait()
        resp = requests.get(url, params=params, headers=self.headers, timeout=30)
        resp.raise_for_status()
        return resp

    def _get_recent_filings(self, form_type: str) -> List[Dict[str, Any]]:
        """Get recent 13D/13G filings from EDGAR Atom feed."""
        params = {
            "action": "getcurrent",
            "type": form_type,
            "dateb": "",
            "count": self.count,
            "output": "atom",
        }

        resp = self._get(EDGAR_FEED_URL, params)
        return self._parse_atom_feed(resp.text, form_type)

    def _parse_atom_feed(self, xml_text: str, form_type: str) -> List[Dict[str, Any]]:
        """Parse EDGAR Atom feed into filing metadata."""
        filings = []
        try:
            root = etree.fromstring(xml_text.encode())
        except etree.XMLSyntaxError:
            return filings

        ns = {"atom": "http://www.w3.org/2005/Atom"}

        for entry in root.findall(".//atom:entry", ns):
            link_el = entry.find("atom:link", ns)
            if link_el is None:
                continue

            index_url = link_el.get("href", "")
            title = entry.findtext("atom:title", "", ns)
            updated = entry.findtext("atom:updated", "", ns)
            entry_id = entry.findtext("atom:id", "", ns)

            accession = ""
            if "accession-number=" in entry_id:
                accession = entry_id.split("accession-number=")[1]

            filings.append({
                "index_url": index_url,
                "title": title,
                "updated": updated,
                "accession": accession,
                "form_type": form_type,
            })

        return filings

    def _find_xml_in_index(self, index_url: str) -> str:
        """Given a filing index page URL, find and return the SC 13D/G XML content."""
        try:
            resp = self._get(index_url)

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "lxml")

            archives_links = []
            for link in soup.find_all("a"):
                href = link.get("href", "")
                if "Archives" in href and ("primary_doc.xml" in href or href.endswith(".xml") or href.endswith(".txt")):
                    archives_links.append(href)

            for href in archives_links:
                if "R" in href.split("/")[-1]:
                    continue
                xml_url = href if href.startswith("http") else f"https://www.sec.gov{href}"
                xml_resp = self._get(xml_url)
                content = xml_resp.text
                if content and len(content) > 500:
                    return content

        except Exception as e:
            self.logger.debug(f"Failed to fetch document from {index_url}: {e}")

        return ""

    def _parse_13d_xml(self, xml_content: str, form_type: str) -> Optional[Dict[str, Any]]:
        """Parse SC 13D or SC 13G XML document."""
        try:
            root = etree.fromstring(xml_content.encode() if isinstance(xml_content, str) else xml_content)
        except etree.XMLSyntaxError:
            return None

        ns = {"edgar": "http://www.sec.gov/edgar/document/sec13d"}

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

        form_data = ns_find(root, "edgar:formData") or root
        if form_data is None:
            form_data = root

        subject_info = ns_find(form_data, "edigar:subjectCompany") or ns_find(form_data, "subjectCompany") or form_data
        if subject_info is None:
            subject_info = root

        issuer_name = ""
        issuer_ticker = ""
        issuer_cik = ""

        for el in root.iter():
            tag = el.tag.split("}")[-1].lower() if "}" in el.tag else el.tag.lower()
            if tag in ("IssuerName", "issuername", "nameOfIssuer"):
                issuer_name = (el.text or "").strip()
            elif tag in ("IssuerTradingSymbol", "issuersymbol", "tradingSymbol"):
                issuer_ticker = (el.text or "").strip()
            elif tag in ("IssuerCik", "issuercik"):
                issuer_cik = (el.text or "").strip()

        if not issuer_name:
            return None

        filing_date_str = ""
        for el in root.iter():
            tag = el.tag.split("}")[-1].lower() if "}" in el.tag else el.tag.lower()
            if "filed" in tag and "date" in tag and el.text:
                filing_date_str = el.text.strip()
                break

        filed_at = None
        if filing_date_str:
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"):
                try:
                    filed_at = datetime.strptime(filing_date_str, fmt)
                    break
                except ValueError:
                    continue

        return {
            "ticker": issuer_ticker.upper() if issuer_ticker else None,
            "issuer_name": issuer_name,
            "issuer_cik": issuer_cik,
            "filed_at": filed_at,
            "form_type": form_type,
        }

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch recent 13D/13G filings and parse them into signals."""
        self.logger.info("Fetching SC 13D/G filings from SEC EDGAR...")

        all_signals = []

        for form_type in ["SC+13D", "SC+13G"]:
            filings = self._get_recent_filings(form_type)
            self.logger.info(f"Found {len(filings)} {form_type} filings in feed")

            for filing in filings:
                index_url = filing.get("index_url", "")
                if not index_url:
                    continue

                try:
                    doc_content = self._find_xml_in_index(index_url)
                    if not doc_content:
                        continue

                    parsed = self._parse_13d_xml(doc_content, form_type)
                    if not parsed:
                        continue

                    source_id = f"{form_type.replace('+', '')}_{parsed.get('issuer_cik', '')}_{parsed.get('ticker', '')}_{parsed.get('filed_at', '')}"

                    if "13D" in form_type:
                        signal_type = "activist_new_position"
                    else:
                        signal_type = "passive_new_position"

                    all_signals.append({
                        "signal_type": signal_type,
                        "ticker": parsed.get("ticker"),
                        "entity_name": parsed.get("issuer_name"),
                        "entity_type": "activist" if "13D" in form_type else "passive_investor",
                        "direction": "BUY",
                        "quantity": None,
                        "price": None,
                        "value_usd": None,
                        "filed_at": datetime.utcnow(),
                        "traded_at": parsed.get("filed_at"),
                        "raw_data": {
                            "issuer_name": parsed.get("issuer_name", ""),
                            "issuer_cik": parsed.get("issuer_cik", ""),
                            "form_type": form_type,
                            "filing_url": index_url,
                            "accession": filing.get("accession", ""),
                            "document_content": doc_content[:2000] if doc_content else "",
                        },
                        "source_id": source_id,
                    })

                except Exception as e:
                    self.logger.debug(f"Failed to process {form_type} filing {index_url}: {e}")
                    continue

        self.logger.info(f"Parsed {len(all_signals)} 13D/13G signals")
        return all_signals
