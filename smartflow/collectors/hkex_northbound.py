"""HKEX Stock Connect Northbound/Southbound Flow Collector.

Tracks daily Northbound (HK→China via Stock Connect) and Southbound (China→HK) trading volumes.
High northbound flow = Hong Kong capital flowing into China = bullish for HK/China stocks.

Source: https://www3.hkexnews.hk/schin/SC/index.html
Method: ASP.NET ViewState POST scraping (same pattern as CCASS)
"""

import re
import time
import random
import requests
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional
from smartflow.collectors.base import BaseCollector
from smartflow.utils import get_logger, retry

SC_URL = "https://www3.hkexnews.hk/schin/SC/index.html"
SC_DATA_URL = "https://www3.hkexnews.hk/schin/SC/NorthboundTradingData.aspx"


class StockConnectClient:
    """Low-level Stock Connect HTML scraper using ASP.NET ViewState POST."""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": SC_DATA_URL,
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self._viewstate = None
        self._viewstate_gen = None
        self._today_token = None
        self.logger = get_logger("sc_client")

    def _fetch_viewstate(self) -> bool:
        """GET the page to extract ASP.NET ViewState tokens."""
        try:
            resp = self.session.get(SC_DATA_URL, timeout=30)
            resp.raise_for_status()
            html = resp.text

            vs = re.search(r'id="__VIEWSTATE"\s+value="([^"]*)"', html)
            vsg = re.search(r'id="__VIEWSTATEGENERATOR"\s+value="([^"]*)"', html)
            today = re.search(r'id="today"\s+value="([^"]*)"', html)

            if not vs:
                return False

            self._viewstate = vs.group(1)
            self._viewstate_gen = vsg.group(1) if vsg else ""
            self._today_token = today.group(1) if today else ""
            return True
        except Exception as e:
            self.logger.warning(f"Failed to fetch ViewState: {e}")
            return False

    @retry(max_attempts=3, backoff=2.0)
    def fetch_turnover(self, trade_date: date) -> Optional[Dict]:
        """Fetch Stock Connect turnover data for a given date.

        Returns dict with northbound and southbound turnover in HKD.
        """
        if self._viewstate is None:
            if not self._fetch_viewstate():
                raise RuntimeError("Could not fetch Stock Connect ViewState")

        date_str = trade_date.strftime("%Y/%m/%d")

        payload = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": self._viewstate,
            "__VIEWSTATEGENERATOR": self._viewstate_gen,
            "today": self._today_token,
            "sortBy": "date",
            "sortDirection": "desc",
            "txtTradeDate": date_str,
            "btnSearch": "Search",
        }

        time.sleep(random.uniform(0.3, 0.8))

        resp = self.session.post(
            SC_DATA_URL, data=payload, timeout=30,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()

        return self._parse_turnover_html(resp.text, trade_date)

    def _parse_turnover_html(self, html: str, trade_date: date) -> Optional[Dict]:
        """Parse Stock Connect turnover table.

        Columns: Date, Northbound Turnover (HKD), Southbound Turnover (HKD),
                 Northbound Quota Used (%), Southbound Quota Used (%)
        Values inside <div class="mobile-list-body">...</div>
        """
        def extract_body(td_html: str) -> str:
            m = re.search(r'class="mobile-list-body">([^<]*)<', td_html)
            return m.group(1).strip() if m else ""

        rows = re.findall(r'<tr>(.*?)</tr>', html, re.DOTALL | re.IGNORECASE)

        for row in rows:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if len(cells) < 4:
                continue

            date_cell = extract_body(cells[0])
            nb_turnover = extract_body(cells[1])   # Northbound HKD
            sb_turnover = extract_body(cells[2])   # Southbound HKD
            nb_quota = extract_body(cells[3])       # Northbound quota %

            if not date_cell or date_cell == "Date":
                continue

            def parse_hkd(s: str) -> Optional[float]:
                s = s.replace(",", "").replace(" ", "")
                try:
                    return float(s)
                except ValueError:
                    return None

            def parse_pct(s: str) -> Optional[float]:
                s = s.replace("%", "").replace(",", "").replace(" ", "")
                try:
                    return float(s)
                except ValueError:
                    return None

            nb_hkd = parse_hkd(nb_turnover)
            sb_hkd = parse_hkd(sb_turnover)
            nb_pct = parse_pct(nb_quota)

            if nb_hkd is not None:
                return {
                    "trade_date": trade_date,
                    "northbound_hkd": nb_hkd,
                    "southbound_hkd": sb_hkd,
                    "northbound_quota_pct": nb_pct,
                }

        return None


class HKEXNorthboundCollector(BaseCollector):
    """Collect daily Stock Connect northbound/southbound turnover data."""

    name = "hkex_northbound"
    market = "HK"

    def _get_target_date(self) -> date:
        """Get most recent trading day (skip weekends)."""
        d = date.today() - timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        return d

    def _get_prev_turnover(self, before_date: date) -> Optional[Dict]:
        """Fetch previous day's turnover for delta calculation."""
        from smartflow.db.engine import get_session
        from smartflow.db.models import NorthboundFlow

        session = get_session()
        prev = (session.query(NorthboundFlow)
                .filter(NorthboundFlow.trade_date < before_date)
                .order_by(NorthboundFlow.trade_date.desc())
                .first())
        result = {
            "northbound_hkd": prev.northbound_hkd if prev else None,
            "southbound_hkd": prev.southbound_hkd if prev else None,
        }
        session.close()
        return result

    def _save_turnover(self, data: Dict) -> bool:
        """Save turnover data to DB."""
        from smartflow.db.engine import get_session
        from smartflow.db.models import NorthboundFlow
        from sqlalchemy.exc import IntegrityError

        session = get_session()
        nf = NorthboundFlow(
            trade_date=data["trade_date"],
            northbound_hkd=data["northbound_hkd"],
            southbound_hkd=data["southbound_hkd"],
            northbound_quota_pct=data.get("northbound_quota_pct"),
        )
        session.add(nf)
        try:
            session.commit()
            session.close()
            return True
        except IntegrityError:
            session.rollback()
            session.close()
            return False

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch Stock Connect turnover data. Returns alert signals."""
        client = StockConnectClient()
        target_date = self._get_target_date()

        self.logger.info(f"Fetching Stock Connect data for {target_date}")

        if not client._fetch_viewstate():
            self.logger.error("Failed to fetch Stock Connect ViewState")
            return []

        data = client.fetch_turnover(target_date)
        if not data:
            self.logger.warning(f"No Stock Connect data for {target_date}")
            return []

        self._save_turnover(data)

        prev = self._get_prev_turnover(target_date)
        signals = []

        nb = data["northbound_hkd"]
        sb = data.get("southbound_hkd") or 0
        nb_prev = prev.get("northbound_hkd") or 0

        # Signal: Northbound flow > HKD 10B (significant China allocation)
        if nb >= 10_000_000_000:
            source_id = f"sc_nb_{target_date}"
            nb_chn = nb / 1_000_000_000
            pct_change = ((nb - nb_prev) / nb_prev * 100) if nb_prev > 0 else 0

            signals.append({
                "signal_type": "northbound_quota_spike",
                "ticker": "HKSCC",
                "entity_name": "Stock Connect Northbound",
                "entity_type": "hk_stock",
                "direction": "BUY",
                "value_usd": round(nb / 7.8, 2),  # approximate USD
                "filed_at": datetime.combine(target_date, datetime.min.time()),
                "traded_at": None,
                "raw_data": {
                    "northbound_hkd": nb,
                    "northbound_chn": round(nb_chn, 1),
                    "southbound_hkd": sb,
                    "northbound_quota_pct": data.get("northbound_quota_pct"),
                    "pct_change_vs_prev": round(pct_change, 1),
                    "nb_sb_ratio": round(nb / sb, 2) if sb > 0 else None,
                },
                "source_id": source_id,
            })
            self.logger.info(
                f"Northbound {target_date}: HKD {nb_chn:.1f}B "
                f"(prev: HKD {nb_prev/1e9:.1f}B, {pct_change:+.1f}%)"
            )

        return signals
