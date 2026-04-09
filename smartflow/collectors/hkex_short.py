"""SFC Short Position Reports Collector.

Tracks short selling activity in Hong Kong listed securities.
SFC publishes weekly short position data showing short sell values as % of total turnover.

High short interest = bearish signal (unless it's a well-known short seller)
Short position increase = potential bearish accumulation by known short sellers

Source: https://www.sfc.hk/eng/short-selling-reports
Method: CSV/Excel download or HTML table scraping
"""

import re
import time
import random
import requests
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional
from io import BytesIO, StringIO
import csv
from smartflow.collectors.base import BaseCollector
from smartflow.utils import get_logger, retry

SFC_SHORT_URL = "https://www.sfc.hk/eng/short-selling-reports"


class SFCShortClient:
    """Low-level SFC short position data scraper."""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.logger = get_logger("sfc_short_client")

    @retry(max_attempts=3, backoff=2.0)
    def fetch_short_data(self, week_end_date: date) -> Optional[Dict]:
        """Fetch SFC short position data for the week ending on week_end_date.

        The SFC provides data as a CSV download. We try multiple URL patterns.
        """
        year = week_end_date.year
        # SFC URL pattern for short selling reports
        # Format: weekly data by year
        url_patterns = [
            f"https://www.sfc.hk/eng/short-selling-reports?year={year}",
            f"https://www.sfc.hk/eng/short-selling-reports/weekly-short-selling-report-{year}",
        ]

        for url in url_patterns:
            try:
                resp = self.session.get(url, timeout=30)
                if resp.status_code != 200:
                    continue

                # Try to find CSV download link in the page
                csv_links = re.findall(r'href=["\']([^"\']+\.csv[^"\']*)["\']', resp.text, re.IGNORECASE)
                if csv_links:
                    csv_url = csv_links[0]
                    if not csv_url.startswith("http"):
                        csv_url = "https://www.sfc.hk" + csv_url
                    csv_resp = self.session.get(csv_url, timeout=30)
                    if csv_resp.status_code == 200:
                        return self._parse_csv(csv_resp.text, week_end_date)

                # Try to find table data in HTML
                data = self._parse_html_table(resp.text, week_end_date)
                if data:
                    return data

            except Exception as e:
                self.logger.warning(f"Failed to fetch from {url}: {e}")
                continue

        return None

    def _parse_csv(self, csv_text: str, week_end_date: date) -> Optional[Dict]:
        """Parse SFC short selling CSV."""
        try:
            reader = csv.DictReader(StringIO(csv_text))
            records = []
            for row in reader:
                stock_code = row.get("Stock Code", row.get("stock_code", ""))
                short_value = row.get("Short Sell Value (HKD)", row.get("short_value", ""))
                total_turnover = row.get("Total Turnover (HKD)", row.get("total_turnover", ""))
                short_pct = row.get("Short Sell as % of Total Turnover",
                                   row.get("short_pct", ""))

                if not stock_code:
                    continue

                records.append({
                    "stock_code": str(stock_code).zfill(5),
                    "short_value_hkd": float(short_value.replace(",", "")) if short_value else 0,
                    "total_turnover_hkd": float(total_turnover.replace(",", "")) if total_turnover else 0,
                    "short_pct": float(short_pct.replace("%", "")) if short_pct else 0,
                })
            return {"week_end_date": week_end_date, "records": records}
        except Exception as e:
            self.logger.warning(f"CSV parse error: {e}")
            return None

    def _parse_html_table(self, html: str, week_end_date: date) -> Optional[Dict]:
        """Parse SFC short selling HTML table."""
        from bs4 import BeautifulSoup

        try:
            soup = BeautifulSoup(html, "html.parser")
            table = soup.find("table")
            if not table:
                return None

            rows = table.find_all("tr")
            if len(rows) < 2:
                return None

            # Get header row to find column indices
            header_cells = rows[0].find_all(["th", "td"])
            headers = [h.get_text(strip=True).lower() for h in header_cells]

            # Find relevant column indices
            stock_col = next((i for i, h in enumerate(headers) if "code" in h or "stock" in h), 0)
            short_col = next((i for i, h in enumerate(headers) if "short" in h and "value" in h), 1)
            total_col = next((i for i, h in enumerate(headers) if "total" in h and "turnover" in h), 2)
            pct_col = next((i for i, h in enumerate(headers) if "%" in h or "ratio" in h), 3)

            records = []
            for row in rows[1:]:
                cells = row.find_all(["th", "td"])
                if len(cells) <= max(stock_col, short_col, total_col, pct_col):
                    continue

                def get_text(cell):
                    return cell.get_text(strip=True).replace(",", "").replace("%", "")

                stock_code = get_text(cells[stock_col])
                if not stock_code or not stock_code.isdigit():
                    continue

                records.append({
                    "stock_code": stock_code.zfill(5),
                    "short_value_hkd": float(get_text(cells[short_col])) if get_text(cells[short_col]) else 0,
                    "total_turnover_hkd": float(get_text(cells[total_col])) if get_text(cells[total_col]) else 0,
                    "short_pct": float(get_text(cells[pct_col])) if get_text(cells[pct_col]) else 0,
                })

            if records:
                return {"week_end_date": week_end_date, "records": records}
            return None

        except Exception as e:
            self.logger.warning(f"HTML parse error: {e}")
            return None


class SFCShortCollector(BaseCollector):
    """Collect weekly SFC short position reports."""

    name = "sfc_short"
    market = "HK"

    def _get_week_end_date(self) -> date:
        """Get the most recent Friday (SFC publishes weekly data)."""
        d = date.today()
        # Find last Friday
        while d.weekday() != 4:  # Friday = 4
            d -= timedelta(days=1)
        return d

    def _get_prev_data(self, before_date: date) -> Dict[str, float]:
        """Get previous week's short % for comparison."""
        from smartflow.db.engine import get_session
        from smartflow.db.models import SFCShortData

        session = get_session()
        prev = (session.query(SFCShortData)
                .filter(SFCShortData.week_end_date < before_date)
                .order_by(SFCShortData.week_end_date.desc())
                .first())
        result = {}
        if prev and prev.raw_data:
            for r in prev.raw_data:
                result[r["stock_code"]] = r.get("short_pct", 0)
        session.close()
        return result

    def _save_data(self, data: Dict) -> bool:
        """Save short position data to DB."""
        from smartflow.db.engine import get_session
        from smartflow.db.models import SFCShortData
        from sqlalchemy.exc import IntegrityError

        session = get_session()
        sfc = SFCShortData(
            week_end_date=data["week_end_date"],
            raw_data=data["records"],
        )
        session.add(sfc)
        try:
            session.commit()
            session.close()
            return True
        except IntegrityError:
            session.rollback()
            session.close()
            return False

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch SFC short position data. Returns alert signals."""
        client = SFCShortClient()
        target_date = self._get_week_end_date()

        self.logger.info(f"Fetching SFC short data for week ending {target_date}")

        data = client.fetch_short_data(target_date)
        if not data or not data.get("records"):
            self.logger.warning(f"No SFC short data for week ending {target_date}")
            return []

        self._save_data(data)

        prev = self._get_prev_data(target_date)
        signals = []

        for rec in data["records"]:
            code = rec["stock_code"]
            short_pct = rec["short_pct"]
            prev_pct = prev.get(code, 0)
            pct_change = short_pct - prev_pct

            # Signal: short % > 20% (very high short pressure)
            if short_pct > 20.0:
                source_id = f"sfc_short_hi_{code}_{target_date}"
                signals.append({
                    "signal_type": "hk_short_high",
                    "ticker": code,
                    "entity_name": None,
                    "entity_type": "hk_stock",
                    "direction": "SELL",
                    "value_usd": round(rec["short_value_hkd"] / 7.8, 2),
                    "filed_at": datetime.combine(target_date, datetime.min.time()),
                    "traded_at": None,
                    "raw_data": {
                        "short_pct": short_pct,
                        "short_value_hkd": rec["short_value_hkd"],
                        "total_turnover_hkd": rec["total_turnover_hkd"],
                        "prev_short_pct": prev_pct,
                        "pct_change": pct_change,
                    },
                    "source_id": source_id,
                })

            # Signal: significant short % increase (shorts accumulating)
            elif pct_change >= 5.0 and short_pct >= 5.0:
                source_id = f"sfc_short_inc_{code}_{target_date}"
                signals.append({
                    "signal_type": "hk_short_increase",
                    "ticker": code,
                    "entity_name": None,
                    "entity_type": "hk_stock",
                    "direction": "SELL",
                    "value_usd": round(rec["short_value_hkd"] / 7.8, 2),
                    "filed_at": datetime.combine(target_date, datetime.min.time()),
                    "traded_at": None,
                    "raw_data": {
                        "short_pct": short_pct,
                        "short_value_hkd": rec["short_value_hkd"],
                        "prev_short_pct": prev_pct,
                        "pct_change": pct_change,
                    },
                    "source_id": source_id,
                })

        self.logger.info(
            f"SFC short data: {len(data['records'])} stocks, {len(signals)} alert signals"
        )
        return signals
