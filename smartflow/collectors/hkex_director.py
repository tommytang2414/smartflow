"""HKEX Director Search Collector.

Searches HKEX Director Search page to find directors and their associated companies.
This gives the list of directorships, not director dealings (which require a different search).

Source: https://www3.hkexnews.hk/reports/dirsearch?sc_lang=en

Note: This search requires Playwright due to JavaScript form interaction.
"""

import time
from typing import List, Dict, Any
from datetime import datetime
from playwright.sync_api import sync_playwright
from smartflow.collectors.base import BaseCollector


class HKEXDirectorCollector(BaseCollector):
    """Collect HKEX director information via Playwright search."""

    name = "hkex_director"
    market = "HK"

    def __init__(self, search_name: str = None):
        super().__init__()
        self.search_name = search_name

    def _search_directors(self, name: str) -> List[Dict[str, Any]]:
        """Search for director by name and return list of directorships."""
        results = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            try:
                page.goto(
                    "https://www3.hkexnews.hk/reports/dirsearch?sc_lang=en",
                    timeout=30000
                )
                page.wait_for_timeout(3000)

                # Click director name radio
                page.locator('label[for=searchby_directorname]').click()
                page.wait_for_timeout(500)

                # Fill director name (needs 3+ characters)
                if len(name) < 3:
                    name = name + "   "
                page.locator("#searchby_directorname_txt").fill(name[:200])
                page.wait_for_timeout(500)

                # Submit
                page.locator("input[type=submit]").click()
                page.wait_for_timeout(8000)

                # Parse results
                from bs4 import BeautifulSoup
                html = page.content()
                soup = BeautifulSoup(html, "html.parser")
                rows = soup.find_all("tr")

                # Data rows have mobile-list-body divs with actual values
                for row in rows[1:]:  # Skip header row
                    cells = row.find_all("td")
                    if len(cells) >= 5:
                        # Extract from mobile-list-body divs
                        def get_body_text(cell):
                            body = cell.find("div", class_="mobile-list-body")
                            if body:
                                return body.get_text().strip()
                            return ""
                        
                        stock_code = get_body_text(cells[2])
                        company_en = get_body_text(cells[3])
                        company_cn = get_body_text(cells[4])
                        
                        if stock_code and stock_code.isdigit():
                            results.append({
                                "director_name": name,
                                "stock_code": stock_code,
                                "company_name_en": company_en,
                                "company_name_cn": company_cn,
                            })

            except Exception as e:
                self.logger.warning(f"Failed to search director {name}: {e}")
            finally:
                browser.close()

        return results

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch director information."""
        if not self.search_name:
            self.logger.warning("No search_name provided for HKEX director search")
            return []

        self.logger.info(f"Searching HKEX for director: {self.search_name}")
        
        directorships = self._search_directors(self.search_name)
        self.logger.info(f"Found {len(directorships)} directorships")

        signals = []
        for d in directorships:
            source_id = f"hkex_dir_{d['director_name']}_{d['stock_code']}"
            
            signals.append({
                "signal_type": "hk_director_listing",
                "ticker": d["stock_code"],
                "entity_name": d["director_name"],
                "entity_type": "director",
                "direction": "HOLD",
                "quantity": None,
                "price": None,
                "value_usd": None,
                "filed_at": datetime.utcnow(),
                "traded_at": None,
                "raw_data": {
                    "company_name_en": d["company_name_en"],
                    "company_name_cn": d["company_name_cn"],
                    "search_name": self.search_name,
                },
                "source_id": source_id,
            })

        return signals


def search_directors_by_name(name: str) -> List[Dict[str, Any]]:
    """Standalone function to search HKEX for a director by name."""
    collector = HKEXDirectorCollector(search_name=name)
    return collector.fetch()
