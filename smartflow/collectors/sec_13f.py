"""SEC EDGAR 13F Collector — Institutional Holdings.

13F filings are quarterly reports from institutional investment managers
with >$100M AUM. They reveal what the biggest funds are holding.

Source: EDGAR Atom feed for 13F-HR filings.
Holdings are in quarter-named XML files (e.g., Q4_2025.xml).
"""

import requests
from datetime import datetime
from typing import List, Dict, Any
from lxml import etree
from smartflow.collectors.base import BaseCollector
from smartflow.config import SEC_EDGAR_EMAIL, SEC_EDGAR_RATE_LIMIT
from smartflow.utils import RateLimiter, retry

EDGAR_FEED_URL = "https://www.sec.gov/cgi-bin/browse-edgar"


class SEC13FCollector(BaseCollector):
    """Collect institutional holdings from SEC EDGAR 13F filings."""

    name = "sec_13f"
    market = "US"

    def __init__(self):
        super().__init__()
        self.rate_limiter = RateLimiter(SEC_EDGAR_RATE_LIMIT)
        self.headers = {
            "User-Agent": f"SmartFlow/0.1 ({SEC_EDGAR_EMAIL})",
            "Accept-Encoding": "gzip, deflate",
        }
        self.count = 40

    @retry(max_attempts=3)
    def _get(self, url: str, params: dict = None) -> requests.Response:
        self.rate_limiter.wait()
        resp = requests.get(url, params=params, headers=self.headers, timeout=30)
        resp.raise_for_status()
        return resp

    def _search_recent_13f(self) -> List[Dict[str, Any]]:
        """Search for recent 13F-HR filings."""
        params = {
            "action": "getcurrent",
            "type": "13F-HR",
            "dateb": "",
            "owner": "include",
            "count": self.count,
            "search_text": "",
            "output": "atom",
        }

        resp = self._get(EDGAR_FEED_URL, params)
        return self._parse_atom_feed(resp.text)

    def _parse_atom_feed(self, xml_text: str) -> List[Dict[str, Any]]:
        from lxml import etree

        filings = []
        try:
            root = etree.fromstring(xml_text.encode())
        except etree.XMLSyntaxError:
            return filings

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall(".//atom:entry", ns)

        for entry in entries:
            link_el = entry.find("atom:link", ns)
            title = entry.findtext("atom:title", "", ns)
            updated = entry.findtext("atom:updated", "", ns)

            if link_el is None:
                continue

            filing_url = link_el.get("href", "")
            filer_name = title.replace("13F-HR", "").replace("13F-HR/A", "").strip(" -")
            cik = ""
            if "(" in filer_name:
                parts = filer_name.rsplit("(", 1)
                filer_name = parts[0].strip()
                cik = parts[1].rstrip(")").strip()

            filings.append({
                "url": filing_url,
                "filer_name": filer_name,
                "cik": cik,
                "updated": updated,
            })

        return filings

    def _find_info_table_xml(self, filing_url: str) -> str:
        """Find the holdings XML file on the filing index page."""
        try:
            resp = self._get(filing_url)
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "lxml")

            for link in soup.find_all("a"):
                href = link.get("href", "")
                text = link.get_text(strip=True)
                if href.endswith(".xml") and "Q" in text and "xslForm" not in href:
                    return href if href.startswith("http") else f"https://www.sec.gov{href}"

            for link in soup.find_all("a"):
                href = link.get("href", "")
                if "Archives" in href and href.endswith(".xml") and "xslForm" not in href:
                    return href if href.startswith("http") else f"https://www.sec.gov{href}"

        except Exception:
            pass
        return None

    def _parse_13f_holdings(self, xml_url: str) -> List[Dict[str, Any]]:
        """Parse 13F holdings from infoTable XML."""
        holdings = []
        try:
            resp = self._get(xml_url)
            root = etree.fromstring(resp.content)

            INFO_NS = "http://www.sec.gov/edgar/document/thirteenf/informationtable"

            for entry in root.iter():
                if "infoTable" not in entry.tag:
                    continue

                def get_text(parent, tag_suffix):
                    for el in parent.iter():
                        if el.tag.endswith(tag_suffix) and el.text:
                            return el.text.strip()
                    return ""

                name_of_issuer = get_text(entry, "nameOfIssuer")
                title_of_class = get_text(entry, "titleOfClass")
                cusip = get_text(entry, "cusip")
                value_str = get_text(entry, "value")
                shares_str = get_text(entry, "sshPrnamt")

                if not name_of_issuer or not cusip:
                    continue

                try:
                    value_float = float(value_str) * 1000 if value_str else 0
                    shares_float = float(shares_str) if shares_str else 0
                except ValueError:
                    continue

                holdings.append({
                    "issuer": name_of_issuer,
                    "title": title_of_class,
                    "cusip": cusip,
                    "value_usd": value_float,
                    "shares": shares_float,
                })

        except Exception:
            pass

        return holdings

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch recent 13F filings and extract top holdings."""
        self.logger.info("Fetching recent 13F filings from SEC EDGAR...")
        filings = self._search_recent_13f()
        self.logger.info(f"Found {len(filings)} recent 13F filings")

        signals = []
        for filing in filings:
            url = filing.get("url", "")
            filer = filing.get("filer_name", "Unknown")

            try:
                xml_url = self._find_info_table_xml(url)
                if not xml_url:
                    continue

                holdings = self._parse_13f_holdings(xml_url)
                if not holdings:
                    continue

                for h in holdings:
                    if h["value_usd"] < 10_000_000:
                        continue

                    source_id = f"13f_{filing.get('cik', '')}_{h['cusip']}_{xml_url.split('/')[-2]}"

                    signals.append({
                        "signal_type": "13f_holding",
                        "ticker": h["issuer"].upper()[:10],
                        "entity_name": filer,
                        "entity_type": "institution",
                        "direction": "HOLD",
                        "quantity": h["shares"],
                        "value_usd": h["value_usd"],
                        "filed_at": datetime.utcnow(),
                        "raw_data": {
                            "cusip": h["cusip"],
                            "title_of_class": h["title"],
                            "filing_url": url,
                            "filer_cik": filing.get("cik", ""),
                        },
                        "source_id": source_id,
                    })

            except Exception as e:
                self.logger.debug(f"Failed to process 13F from {filer}: {e}")
                continue

        self.logger.info(f"Parsed {len(signals)} institutional holding signals")
        return signals
