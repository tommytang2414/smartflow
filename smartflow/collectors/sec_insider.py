"""SEC EDGAR Form 4 Collector — Insider Trades.

Uses EDGAR's Atom feed to find recent Form 4 filings,
then fetches and parses the XML to extract insider transaction data.
"""

import requests
from datetime import datetime
from typing import List, Dict, Any
from lxml import etree
from smartflow.collectors.base import BaseCollector
from smartflow.parsers.edgar_xml import parse_form4_xml
from smartflow.config import SEC_EDGAR_EMAIL, SEC_EDGAR_RATE_LIMIT
from smartflow.utils import RateLimiter, retry

EDGAR_FEED_URL = "https://www.sec.gov/cgi-bin/browse-edgar"


class SECInsiderCollector(BaseCollector):
    """Collect insider trades from SEC EDGAR Form 4 filings."""

    name = "sec_form4"
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

    def _get_recent_filings(self) -> List[Dict[str, Any]]:
        """Get recent Form 4 filings from EDGAR Atom feed."""
        params = {
            "action": "getcurrent",
            "type": "4",
            "dateb": "",
            "owner": "include",
            "count": self.count,
            "search_text": "",
            "output": "atom",
        }

        resp = self._get(EDGAR_FEED_URL, params)
        return self._parse_atom_feed(resp.text)

    def _parse_atom_feed(self, xml_text: str) -> List[Dict[str, Any]]:
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

            # Extract accession number from id (urn:tag:sec.gov,2008:accession-number=...)
            accession = ""
            if "accession-number=" in entry_id:
                accession = entry_id.split("accession-number=")[1]

            filings.append({
                "index_url": index_url,
                "title": title,
                "updated": updated,
                "accession": accession,
            })

        return filings

    def _find_xml_in_index(self, index_url: str) -> str:
        """Given a filing index page URL, find and return the Form 4 XML content."""
        try:
            resp = self._get(index_url)

            # Parse the index page to find the XML document link
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "lxml")

            # Look for XML files in the filing documents table
            for link in soup.find_all("a"):
                href = link.get("href", "")
                if href.endswith(".xml") and "R" not in href.split("/")[-1]:
                    xml_url = href if href.startswith("http") else f"https://www.sec.gov{href}"
                    xml_resp = self._get(xml_url)
                    # Verify it's actually a Form 4 XML
                    if "<ownershipDocument" in xml_resp.text:
                        return xml_resp.text

        except Exception as e:
            self.logger.debug(f"Failed to fetch XML from {index_url}: {e}")

        return ""

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch recent Form 4 filings and parse them into signals."""
        self.logger.info("Fetching recent Form 4 filings from SEC EDGAR...")
        filings = self._get_recent_filings()
        self.logger.info(f"Found {len(filings)} Form 4 filings in feed")

        signals = []
        errors = 0

        for filing in filings:
            index_url = filing.get("index_url", "")
            if not index_url:
                continue

            try:
                xml_text = self._find_xml_in_index(index_url)
                if not xml_text:
                    continue

                parsed = parse_form4_xml(xml_text)
                if not parsed:
                    continue

                source_id = f"form4_{parsed.get('entity_cik', '')}_{parsed.get('ticker', '')}_{parsed.get('traded_at', '')}"
                signal_type = f"insider_{parsed['direction'].lower()}"

                signals.append({
                    "signal_type": signal_type,
                    "ticker": parsed["ticker"],
                    "entity_name": parsed["entity_name"],
                    "entity_type": parsed["entity_type"],
                    "direction": parsed["direction"],
                    "quantity": parsed["total_shares"],
                    "price": parsed["transactions"][0]["price"] if parsed["transactions"] else None,
                    "value_usd": parsed["total_value"],
                    "filed_at": datetime.utcnow(),
                    "traded_at": parsed["traded_at"],
                    "raw_data": {
                        "issuer_name": parsed["issuer_name"],
                        "officer_title": parsed.get("officer_title", ""),
                        "transactions": [
                            {k: v for k, v in t.items() if k != "date" or isinstance(v, str)}
                            for t in parsed["transactions"]
                        ],
                        "filing_url": index_url,
                        "accession": filing.get("accession", ""),
                    },
                    "source_id": source_id,
                })

            except Exception as e:
                errors += 1
                if errors <= 3:
                    self.logger.warning(f"Failed to process filing {index_url}: {e}")
                continue

        if errors > 3:
            self.logger.warning(f"Suppressed {errors - 3} additional errors")

        self.logger.info(f"Parsed {len(signals)} insider trade signals from {len(filings)} filings")
        return signals
