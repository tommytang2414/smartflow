"""Congress Trades Collector v2.

Fetches US Congress member stock trades from the official Congressional
Disclosure Portal (disclosure.house.gov) — free, no API key required.

Congress members must disclose trades within 45 days (STOCK Act).
This replaces the QuiverQuant-based v1 which had its free tier revoked.

Data source: https://disclosure.house.gov/L2/Disclosure/Forms/CongressionalDisclosure.aspx
Alternative (Senate-only): https://seec.senate.gov/priv/ogl/ogl-transactions-cgi-bin/
                             (requires Senate credentials — use disclosure.house.gov instead)
"""

import re
import time
import random
import requests
from datetime import datetime, date
from typing import List, Dict, Any
from smartflow.collectors.base import BaseCollector
from smartflow.utils import get_logger, retry

# Official Congressional Disclosure Portal
DISCLOSURE_BASE = "https://disclosure.house.gov/L2/Disclosure/Forms"
LIST_URL = f"{DISCLOSURE_BASE}/CongressionalDisclosure.aspx"
SEARCH_URL = f"{DISCLOSURE_BASE}/CongressionalDisclosure.aspx"

HEADERS = {
    "User-Agent": "SmartFlow/1.0 (tommytang.cc@gmail.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": LIST_URL,
}


class CongressDisclosureClient:
    """Low-level scraper for the official Congressional Disclosure Portal.

    The portal uses ASP.NET ViewState — requires a GET first to extract tokens,
    then POST with the form data.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._viewstate = None
        self._viewstate_gen = None
        self._event_validation = None
        self.logger = get_logger("congress_client")

    @retry(max_attempts=3, backoff=2.0)
    def _get_page(self, url: str = SEARCH_URL) -> bool:
        """GET the disclosure page to extract ASP.NET ViewState tokens."""
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            html = resp.text

            vs = re.search(r'id="__VIEWSTATE"\s+value="([^"]*)"', html)
            vsg = re.search(r'id="__VIEWSTATEGENERATOR"\s+value="([^"]*)"', html)
            ev = re.search(r'id="__EVENTVALIDATION"\s+value="([^"]*)"', html)

            if not vs:
                return False

            self._viewstate = vs.group(1)
            self._viewstate_gen = vsg.group(1) if vsg else ""
            self._event_validation = ev.group(1) if ev else ""
            return True
        except Exception as e:
            self.logger.warning(f"Failed to fetch disclosure page: {e}")
            return False

    @retry(max_attempts=3, backoff=2.0)
    def search_transactions(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        page_size: int = 100,
    ) -> List[Dict[str, Any]]:
        """Search for congressional transactions within a date range.

        The form requires: date range, submit button.
        Results table columns: Member, Transaction Date, Office, Committee,
        Disclosure Type, Transactions, Amount, Re-Priced?
        """
        if self._viewstate is None:
            if not self._get_page():
                raise RuntimeError("Could not fetch Congressional Disclosure page")

        # Default to last 90 days
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - __import__("datetime").timedelta(days=90)

        payload = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": self._viewstate,
            "__VIEWSTATEGENERATOR": self._viewstate_gen,
            "__EVENTVALIDATION": self._event_validation,
            "ctl00$MainContent$txtBeginDate": start_date.strftime("%m/%d/%Y"),
            "ctl00$MainContent$txtEndDate": end_date.strftime("%m/%d/%Y"),
            "ctl00$MainContent$btnSearch": "Search",
        }

        time.sleep(random.uniform(0.5, 1.5))

        resp = self.session.post(
            SEARCH_URL,
            data=payload,
            timeout=60,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()

        return self._parse_results_html(resp.text)

    def _parse_results_html(self, html: str) -> List[Dict[str, Any]]:
        """Parse the transaction results table from disclosure portal HTML.

        Each row has: Member, Transaction Date, Office, Committee,
        Disclosure Type, # Transactions, Amount, Re-Priced?
        """
        transactions = []

        # Table rows pattern
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL | re.IGNORECASE)
        if not rows:
            self.logger.warning("No transaction rows found in disclosure HTML")
            return []

        def cell_value(cell_html: str) -> str:
            m = re.search(r'>([^<]*)</td>', cell_html, re.DOTALL)
            return m.group(1).strip() if m else ""

        for row in rows:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if len(cells) < 6:
                continue

            member = cell_value(cells[0])
            if not member or member in ("Member", ""):
                continue

            tx_date_str = cell_value(cells[1])
            office = cell_value(cells[2])
            committee = cell_value(cells[3])
            disclosure_type = cell_value(cells[4])
            tx_count = cell_value(cells[5])
            amount_str = cell_value(cells[6]) if len(cells) > 6 else ""

            transactions.append({
                "member": member,
                "tx_date": tx_date_str,
                "office": office,
                "committee": committee,
                "disclosure_type": disclosure_type,
                "tx_count": tx_count,
                "amount_str": amount_str,
            })

        self.logger.info(f"Parsed {len(transactions)} transaction rows")
        return transactions


def _parse_amount(amount_str: str) -> float:
    """Parse amount range string to midpoint value."""
    if not amount_str:
        return 0.0
    amount_str = str(amount_str).replace("$", "").replace(",", "").strip()
    if " - " in amount_str:
        parts = amount_str.split(" - ")
        try:
            return (float(parts[0].strip()) + float(parts[1].strip())) / 2
        except ValueError:
            return 0.0
    try:
        return float(amount_str)
    except ValueError:
        return 0.0


def _detect_direction(amount_str: str, disclosure_type: str) -> str:
    """Infer trade direction from amount string and disclosure type."""
    typ = (disclosure_type or "").lower()
    if "purchase" in typ or "buy" in typ:
        return "BUY"
    if "sale" in typ or "sell" in typ:
        return "SELL"
    if "exchange" in typ:
        return "EXCHANGE"
    return "BUY"  # Default to BUY for unidentified types


class CongressCollector(BaseCollector):
    """Collect Congress member stock trades from disclosure.house.gov."""

    name = "congress"
    market = "US"

    def __init__(self):
        super().__init__()
        self.client = CongressDisclosureClient()

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch recent congressional transactions from the official disclosure portal."""
        self.logger.info("Fetching congressional transactions from disclosure.house.gov...")

        try:
            transactions = self.client.search_transactions()
        except Exception as e:
            self.logger.error(f"Failed to fetch congressional disclosures: {e}")
            return []

        if not transactions:
            self.logger.warning("No congressional transactions found")
            return []

        self.logger.info(f"Found {len(transactions)} transactions")

        signals = []
        seen_ids: set[str] = set()

        for txn in transactions:
            member = txn.get("member", "")
            tx_date_str = txn.get("tx_date", "")
            if not member or not tx_date_str:
                continue

            # Build source_id from member + date (deterministic)
            source_id = f"congress_{member}_{tx_date_str}"
            if source_id in seen_ids:
                continue
            seen_ids.add(source_id)

            amount_str = txn.get("amount_str", "")
            value_usd = _parse_amount(amount_str)
            disclosure_type = txn.get("disclosure_type", "")
            direction = _detect_direction(amount_str, disclosure_type)

            # Parse transaction date
            traded_at = None
            if tx_date_str:
                for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%B %d, %Y"):
                    try:
                        dt = datetime.strptime(tx_date_str, fmt)
                        traded_at = dt
                        break
                    except ValueError:
                        continue

            # Ticker extraction is not available from disclosure.house.gov alone
            # (the portal lists by Member, not by security)
            # Filed date = today (disclosure filing date)
            filed_at = datetime.utcnow()

            signals.append({
                "signal_type": f"congress_{direction.lower()}",
                "ticker": None,  # Congress disclosures are by member, not ticker
                "entity_name": member,
                "entity_type": "congress",
                "direction": direction,
                "quantity": None,
                "price": None,
                "value_usd": value_usd,
                "filed_at": filed_at,
                "traded_at": traded_at,
                "raw_data": {
                    "office": txn.get("office"),
                    "committee": txn.get("committee"),
                    "disclosure_type": disclosure_type,
                    "tx_count": txn.get("tx_count"),
                    "amount_str": amount_str,
                },
                "source_id": source_id,
            })

        self.logger.info(f"Parsed {len(signals)} congressional trade signals")
        return signals