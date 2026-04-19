"""HKEX Director Dealings Collector.

Fetches director buy/sell transactions and director-related announcements
from HKEX company announcements using the title search at:
https://www1.hkexnews.hk/search/titlesearch.xhtml

Director dealings (category 17350) have 0 results in HKEX index - the
narrow "Model Code prohibited" category rarely has filings. Instead, we
track broader director-related announcements which are more signal-rich:
  - Change in Directors / Important Executive Functions (12350)
  - Director biographical changes (12950)
  - Chief Executive changes (12951)
  - Re-election/Appointment of Director (14600)

Source: HKEX Title Search (www1.hkexnews.hk)
"""

import time
import re
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

from smartflow.collectors.base import BaseCollector
from smartflow.utils import get_logger, retry

# Director-related category codes (t2code values)
DIRECTOR_CATEGORIES = {
    "17350": "Dealings in Securities by Director where Otherwise Prohibited under Model Code",
    "12350": "Change in Directors or of Important Executive Functions or Responsibilities",
    "12950": "Change in a Director's or Supervisor's Biographical Details",
    "12951": "Change in Chief Executive",
    "12952": "List of Directors and their Role and Function",
    "14600": "Re-election or Appointment of Director subject to Shareholders' Approval",
}

# Which categories indicate actual dealings vs structural changes
DEALING_CATEGORIES = {"17350"}  # Only this is actual dealings
CHANGE_CATEGORIES = {"12350", "12950", "12951", "14600", "12952"}


class HKEXDealingsCollector(BaseCollector):
    """Collect HKEX director dealings and director-change announcements.

    Searches HKEX title search for a given stock code, parses the results
    table, and emits signals for director-related announcements.
    """

    name = "hkex_dealings"
    market = "HK"

    def __init__(self, stock_codes: List[str] = None, days_back: int = 7):
        """
        Args:
            stock_codes: List of HK stock codes to search (e.g. ["00700", "00001"]).
                         If None, uses default HK heavyweights.
            days_back: How many days back to search (default 7).
        """
        super().__init__()
        self.stock_codes = stock_codes or ["00700", "00001", "09988", "03690", "00941",
                                           "00388", "02318", "02382", "00688", "00857"]
        self.days_back = days_back

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch director-related announcements for configured stock codes."""
        signals = []
        from_dt = date.today() - timedelta(days=self.days_back)

        for code in self.stock_codes:
            try:
                results = self._search_stock(code, from_dt)
                for r in results:
                    signal = self._parse_result(r, code)
                    if signal:
                        signals.append(signal)
                self.logger.info(f"[hkex_dealings] {code}: {len(results)} results")
            except Exception as e:
                self.logger.warning(f"[hkex_dealings] Failed for {code}: {e}")

        self.logger.info(f"[hkex_dealings] Total: {len(signals)} signals from {len(self.stock_codes)} stocks")
        return signals

    def _search_stock(self, stock_code: str, from_dt: date) -> List[Dict]:
        """Search HKEX title search for a stock code and date range."""
        results = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "Chrome/122.0.0.0 Safari/537.36"
            )
            # 50s hard cap per page: goto(30s) + waits + search + parse, with margin
            page = context.new_page()
            page.set_default_timeout(15000)

            try:
                page.goto(
                    "https://www1.hkexnews.hk/search/titlesearch.xhtml",
                    timeout=30000
                )
                page.wait_for_timeout(8000)

                # Handle cookie consent
                try:
                    page.locator('button:has-text("Accept")').click(timeout=3000)
                    page.wait_for_timeout(1000)
                except Exception:
                    pass

                # Step 1: Fill stock code in autocomplete field
                page.locator("#searchStockCode").fill(stock_code, timeout=15000)
                page.wait_for_timeout(3000)

                # Step 2: Click first autocomplete suggestion to set display value
                suggestions = page.locator("#autocomplete-list-0 tr.autocomplete-suggestion")
                count = suggestions.count()

                if count == 0:
                    self.logger.warning(f"[hkex_dealings] No autocomplete for {stock_code}")
                    browser.close()
                    return []

                suggestions.first.click(timeout=15000)
                page.wait_for_timeout(2000)

                # Step 2b: Set hidden stockId directly via JavaScript to ensure it's populated
                # The autocomplete click sets the display text but stockId may not be set.
                # We get the numeric stock ID from the autocomplete suggestion's first <td>.
                stock_id_from_suggestion = page.evaluate('''
                    (function() {
                        var firstSuggestion = document.querySelector("#autocomplete-list-0 tr.autocomplete-suggestion td span");
                        return firstSuggestion ? firstSuggestion.textContent.trim() : "";
                    })()
                ''')
                # stock_id_from_suggestion is the STOCK CODE (e.g. "00700"), not the numeric DB id.
                # We need the numeric stock ID to set stockId field. Use 5-digit padded stock code.
                page.evaluate(f'''
                    var stockIdField = document.querySelector("#stockId");
                    if (stockIdField) {{
                        stockIdField.value = "{stock_code.zfill(5)}";
                    }}
                    var stockCodeField = document.querySelector("#stockCode");
                    if (stockCodeField) {{
                        stockCodeField.value = "{stock_code.zfill(5)}";
                    }}
                ''')
                page.wait_for_timeout(500)

                # Step 3: Set date range
                to_dt = date.today()
                page.evaluate(f'''
                    document.querySelector("#searchDate-From").value = "{from_dt.strftime('%Y/%m/%d')}";
                    document.querySelector("#searchDate-To").value = "{to_dt.strftime('%Y/%m/%d')}";
                ''')
                page.wait_for_timeout(500)

                # Step 4: Click SEARCH button
                page.locator(".filter__btn-applyFilters-js").click(timeout=15000)
                page.wait_for_timeout(5000)

                # Step 5: Parse results table
                html = page.content()
                results = self._parse_html_table(html, stock_code)

            except Exception as e:
                self.logger.warning(f"[hkex_dealings] Playwright error for {stock_code}: {e}")
            finally:
                browser.close()

        return results

    def _parse_html_table(self, html: str, stock_code: str) -> List[Dict]:
        """Parse announcement rows from the HKEX search results HTML."""
        soup = BeautifulSoup(html, "html.parser")
        results = []

        table = soup.find("table", class_="table")
        if not table:
            return []

        tbody = table.find("tbody")
        if not tbody:
            return []

        rows = tbody.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 3:
                continue

            # Cell 0: Release Time:DD/MM/YYYY HH:MM
            # Cell 1: Stock Code:XXXXXYYYYY
            # Cell 2: Stock Short Name:NAME
            # Cell 3: Document:CATEGORY - DESCRIPTION(KB)

            cell_texts = [c.get_text(strip=True) for c in cells]
            raw_htmls = [str(c) for c in cells]

            if len(cells) < 4:
                continue

            # Extract release date/time from first cell
            datetime_match = re.search(r"(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})", cell_texts[0])
            if not datetime_match:
                continue

            release_date_str, release_time = datetime_match.groups()
            release_dt = datetime.strptime(f"{release_date_str} {release_time}", "%d/%m/%Y %H:%M")

            # Document cell (Cell 3) contains "Document:CATEGORY - DESCRIPTION(KB)"
            document_text = cell_texts[3]
            if document_text.startswith("Document:"):
                document_text = document_text[len("Document:"):]

            # Extract category from [brackets]
            category_match = re.search(r"\[([^\]]+)\]", document_text)
            category = category_match.group(1) if category_match else ""

            # Look for document link in the row
            view_link = ""
            links = row.find_all("a")
            for link in links:
                href = link.get("href", "")
                text = link.get_text(strip=True)
                if "View Documents" in text or (href and "viewdoc" in href.lower()):
                    view_link = ("https://www1.hkexnews.hk" + href) if href.startswith("/") else href
                    break

            results.append({
                "stock_code": stock_code,
                "release_dt": release_dt,
                "headline": document_text,
                "view_link": view_link,
                "category": category,
                "raw_cells": cell_texts,
                "raw_html": raw_htmls,
            })

        return results

    def _parse_result(self, r: Dict, stock_code: str) -> Optional[Dict]:
        """Convert a parsed result into a SmartMoneySignal dict."""
        headline = r.get("headline", "")
        category = r.get("category", "").lower()
        release_dt = r.get("release_dt")

        # Determine signal type and direction
        direction = "TRANSFER"  # neutral default

        # Dealings-related keywords
        dealing_keywords = ["dealings", "director", "chief executive", "acquisition",
                           "disposal", "share buyback", "model code"]
        change_keywords = ["change", "appoint", "re-elect", "resign", "biographical",
                          "director"]

        is_dealing = any(k in category for k in dealing_keywords) or \
                     any(k in headline.lower() for k in dealing_keywords)
        is_change = any(k in category for k in change_keywords) or \
                    any(k in headline.lower() for k in change_keywords)

        if is_dealing:
            signal_type = "hk_director_dealing"
            # Determine direction from headline
            if "buyback" in headline.lower() or "purchase" in headline.lower():
                direction = "BUY"
            elif "disposal" in headline.lower() or "sell" in headline.lower():
                direction = "SELL"
        elif is_change:
            signal_type = "hk_director_change"
        else:
            # Not a director-related announcement
            return None

        # Extract entity name from headline (often contains person name)
        entity_name = self._extract_director_name(headline, r.get("raw_cells", []))

        source_id = f"hkex_dealings_{stock_code}_{release_dt.strftime('%Y%m%d%H%M')}_{hash(headline) % 100000}"

        return {
            "signal_type": signal_type,
            "ticker": stock_code,
            "entity_name": entity_name,
            "entity_type": "director",
            "direction": direction,
            "quantity": None,
            "price": None,
            "value_usd": None,
            "filed_at": release_dt,
            "traded_at": None,
            "raw_data": {
                "headline": headline,
                "category": category,
                "view_link": r.get("view_link", ""),
                "stock_name": r.get("raw_cells", [""])[1] if r.get("raw_cells") else "",
            },
            "source_id": source_id,
        }

    def _extract_director_name(self, headline: str, cells: List[str]) -> str:
        """Extract director name from headline or table cells."""
        # Look for patterns like "MR. CHAN" or names in parentheses
        name_patterns = [
            r"\b(MR\.?\s+\w+)",
            r"\b(MS\.?\s+\w+)",
            r"\b(MRS\.?\s+\w+)",
            r"\([A-Z][a-z]+\s+[A-Z][a-z]+\)",
        ]
        for pattern in name_patterns:
            match = re.search(pattern, headline, re.IGNORECASE)
            if match:
                return match.group(0)

        # Return empty if no name found
        return ""
