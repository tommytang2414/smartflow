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
import json
import time
import random
import http.client
import requests
from datetime import datetime, date
from typing import List, Dict, Any
from smartflow.collectors.base import BaseCollector
from smartflow.utils import get_logger, retry

# QuiverQuant beta API (requires session cookies from main page)
QUIVER_API = "https://api.quiverquant.com/beta/live/congresstrading"
QUIVER_MAIN_PAGE = "https://www.quiverquant.com/congresstrading/"

# Official Congressional Disclosure Portal (fallback)
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


# ------------------------------------------------------------------
# QuiverQuant client (primary source — confirmed 200 OK from VPS)
# ------------------------------------------------------------------

def _fetch_quiver() -> List[Dict[str, Any]]:
    """Fetch congressional trades from QuiverQuant beta API (primary source).

    The API requires session cookies from the main QuiverQuant page first,
    AND the requests library must not use HTTP/2 (ALPN negotiation interferes
    with the cookie signing). We use http.client directly for the API call
    with HTTP/1.1 to match the browser behavior.
    """
    # Step 1: get session cookies from main page
    session = requests.Session()
    try:
        session.get(QUIVER_MAIN_PAGE, timeout=15,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; SmartFlow/1.0)"})
    except Exception:
        pass

    # Step 2: call API with HTTP/1.1 (bypasses HTTP/2 ALPN cookie issues)
    cookies_str = "; ".join(f"{k}={v}" for k, v in session.cookies.items())
    conn = http.client.HTTPSConnection("api.quiverquant.com", timeout=30)
    try:
        conn.request("GET", "/beta/live/congresstrading", headers={
            "Host": "api.quiverquant.com",
            "Cookie": cookies_str,
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Referer": QUIVER_MAIN_PAGE,
            "Accept-Language": "en-US,en;q=0.9",
        })
        resp = conn.getresponse()
        if resp.status != 200:
            raise RuntimeError(f"QuiverQuant API returned {resp.status}: {resp.read()[:200]}")
        return json.loads(resp.read())
    finally:
        conn.close()


def _parse_quiver_transactions(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize QuiverQuant records to internal transaction format."""
    transactions = []
    for r in raw:
        rep = r.get("Representative", "")
        ticker = r.get("Ticker", "")
        txn_type = r.get("Transaction", "")
        amount_str = r.get("Amount", "")
        report_date_str = r.get("ReportDate", "")
        transaction_date_str = r.get("TransactionDate", "")

        if not rep:
            continue

        transactions.append({
            "member": rep,
            "ticker": ticker or None,
            "tx_date": transaction_date_str or report_date_str,
            "disclosure_type": txn_type,
            "amount_str": amount_str,
            "party": r.get("Party", ""),
            "house": r.get("House", ""),
            "price_change": r.get("PriceChange", ""),
            "spy_change": r.get("SPYChange", ""),
            "excess_return": r.get("ExcessReturn", ""),
        })
    return transactions


class CongressCollector(BaseCollector):
    """Collect Congress member stock trades from disclosure.house.gov."""

    name = "congress"
    market = "US"

    def __init__(self):
        super().__init__()
        self.client = CongressDisclosureClient()

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch congressional transactions — QuiverQuant primary, disclosure.house.gov fallback."""
        self.logger.info("Fetching congressional transactions (QuiverQuant primary)...")

        transactions = []
        source = None

        # Primary: QuiverQuant beta API (confirmed 200 OK from VPS)
        try:
            raw = _fetch_quiver()
            transactions = _parse_quiver_transactions(raw)
            source = "quiverquant"
            self.logger.info(f"QuiverQuant: {len(transactions)} transactions fetched")
        except Exception as e:
            self.logger.warning(f"QuiverQuant failed ({e}), falling back to disclosure.house.gov...")

        # Fallback: official disclosure portal (ASP.NET scraping)
        if not transactions:
            try:
                transactions = self.client.search_transactions()
                source = "disclosure"
                self.logger.info(f"Disclosure portal fallback: {len(transactions)} transactions fetched")
            except Exception as e:
                self.logger.error(f"Falling back to disclosure.house.gov failed: {e}")

        if not transactions:
            self.logger.warning("No congressional transactions found from any source")
            return []

        self.logger.info(f"Processing {len(transactions)} transactions (source: {source})")

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
                for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y"):
                    try:
                        dt = datetime.strptime(tx_date_str, fmt)
                        traded_at = dt
                        break
                    except ValueError:
                        continue

            # Ticker: available from QuiverQuant, None from disclosure portal
            ticker = txn.get("ticker")

            filed_at = datetime.utcnow()

            raw_data = {
                "disclosure_type": disclosure_type,
                "amount_str": amount_str,
                "source": source,
            }

            # Add QuiverQuant-specific fields if available
            if source == "quiverquant":
                raw_data.update({
                    "party": txn.get("party"),
                    "house": txn.get("house"),
                    "price_change": txn.get("price_change"),
                    "spy_change": txn.get("spy_change"),
                    "excess_return": txn.get("excess_return"),
                })
            else:
                raw_data.update({
                    "office": txn.get("office"),
                    "committee": txn.get("committee"),
                    "tx_count": txn.get("tx_count"),
                })

            signals.append({
                "signal_type": f"congress_{direction.lower()}",
                "ticker": ticker,
                "entity_name": member,
                "entity_type": "congress",
                "direction": direction,
                "quantity": None,
                "price": None,
                "value_usd": value_usd,
                "filed_at": filed_at,
                "traded_at": traded_at,
                "raw_data": raw_data,
                "source_id": source_id,
            })

        self.logger.info(f"Parsed {len(signals)} congressional trade signals")
        return signals