"""CCASS Daily Shareholding Collector — HK Smart Money / 莊家 Detection.

Scrapes HKEX CCASS shareholding data for each stock in the watchlist.
Computes concentration metrics to detect 莊家 accumulation/distribution.

Key metrics:
  BrkT5  — Top 5 broker % of adjusted float (>69% = danger zone)
  futu_pct — FUTU Securities % (reverse indicator: high = retail = 莊家 exiting)
  top1_pct — Single largest broker concentration

Alert thresholds (from ccass-sentinel empirical research on 132 IPOs):
  BrkT5 > 69% → RED   (50% probability of >50% drawdown)
  BrkT5 > 55% → AMBER
  BrkT5 < 55% → GREEN

Source: https://www3.hkexnews.hk/sdw/search/searchsdw.aspx
Method: ASP.NET ViewState POST scraping (pure requests, no Selenium needed)
"""

import re
import time
import random
import requests
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.exc import IntegrityError

from smartflow.collectors.base import BaseCollector
from smartflow.collectors.hkex_participants import load_participants, get_participant_type
from smartflow.collectors.hkex_watchlist import get_active_watchlist, seed_watchlist
from smartflow.db.engine import get_session, init_db
from smartflow.db.models import CCASSHolding, CCASSMetric, SmartMoneySignal
from smartflow.utils import get_logger, retry

CCASS_URL = "https://www3.hkexnews.hk/sdw/search/searchsdw.aspx"
FUTU_ID = "B01955"
CSDC_ID = "A00005"   # Immobilized H-share internal — exclude from adjusted float

# Concentration thresholds
THRESHOLD_RED   = 69.0   # BrkT5 > 69% → RED flag
THRESHOLD_AMBER = 55.0   # BrkT5 > 55% → AMBER


class CCASSClient:
    """Low-level CCASS HTML scraper using ASP.NET ViewState POST."""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www3.hkexnews.hk/sdw/search/searchsdw.aspx",
        # Content-Type NOT set here — only added per-request in POST calls
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self._viewstate = None
        self._viewstate_gen = None
        self._today_token = None
        self.logger = get_logger("ccass_client")

    def _fetch_viewstate(self) -> bool:
        """GET the search page to extract ASP.NET ViewState tokens."""
        try:
            resp = self.session.get(CCASS_URL, timeout=30)
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
    def fetch_holdings(self, stock_code: str, holding_date: date) -> List[Dict]:
        """Fetch CCASS holdings for a single stock on a given date.

        Returns list of dicts: {participant_id, participant_name, shares_held, pct_of_total}
        """
        # Lazy load ViewState (can be reused across requests)
        if self._viewstate is None:
            if not self._fetch_viewstate():
                raise RuntimeError("Could not fetch CCASS ViewState")

        date_str = holding_date.strftime("%Y/%m/%d")
        code_padded = stock_code.zfill(5)

        payload = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": self._viewstate,
            "__VIEWSTATEGENERATOR": self._viewstate_gen,
            "today": self._today_token,
            "sortBy": "shareholding",
            "sortDirection": "desc",
            "originalShareholdingDate": "",
            "alertMsg": "",
            "txtShareholdingDate": date_str,
            "txtStockCode": code_padded,
            "txtStockName": "",
            "txtParticipantID": "",
            "txtParticipantName": "",
            "txtSelPartID": "",
            "btnSearch": "Search",   # named submit button trigger
        }

        # Random delay to avoid rate limiting
        time.sleep(random.uniform(0.3, 0.8))

        resp = self.session.post(
            CCASS_URL, data=payload, timeout=30,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()

        return self._parse_holdings_html(resp.text, code_padded)

    def _parse_holdings_html(self, html: str, stock_code: str) -> List[Dict]:
        """Parse CCASS holdings table using CSS class-based structure.

        Each row has:
          <td class="col-participant-id">    → participant ID
          <td class="col-participant-name">  → name
          <td class="col-address">           → address (skip)
          <td class="col-shareholding">      → shares
          <td class="col-shareholding-percent"> → %
        Values are inside <div class="mobile-list-body">...</div>
        """
        holdings = []

        def extract_body(td_html: str) -> str:
            m = re.search(r'class="mobile-list-body">([^<]*)<', td_html)
            return m.group(1).strip() if m else ""

        # Extract all <tr> blocks
        rows = re.findall(r'<tr>(.*?)</tr>', html, re.DOTALL | re.IGNORECASE)

        for row in rows:
            # Extract each <td> by class
            pid_td   = re.search(r'<td[^>]*col-participant-id[^>]*>(.*?)</td>', row, re.DOTALL)
            pname_td = re.search(r'<td[^>]*col-participant-name[^>]*>(.*?)</td>', row, re.DOTALL)
            shares_td = re.search(r'<td[^>]*col-shareholding[^"]*text-right[^>]*>(.*?)</td>', row, re.DOTALL)
            pct_td   = re.search(r'<td[^>]*col-shareholding-percent[^>]*>(.*?)</td>', row, re.DOTALL)

            if not (pid_td and shares_td and pct_td):
                continue

            participant_id   = extract_body(pid_td.group(1))
            participant_name = extract_body(pname_td.group(1)) if pname_td else ""
            shares_raw       = extract_body(shares_td.group(1)).replace(",", "")
            pct_raw          = extract_body(pct_td.group(1)).replace("%", "").replace(",", "")

            if not re.match(r'^[A-Z]\d{4,6}$', participant_id):
                continue

            try:
                shares = float(shares_raw)
                pct = float(pct_raw)
            except ValueError:
                continue

            if shares <= 0:
                continue

            holdings.append({
                "participant_id": participant_id,
                "participant_name": participant_name,
                "shares_held": shares,
                "pct_of_total": pct,
            })

        return holdings


class CCASSCollector(BaseCollector):
    """Collect daily CCASS shareholding data and compute 莊家 concentration metrics."""

    name = "hkex_ccass"
    market = "HK"

    def __init__(self, workers: int = 3):
        super().__init__()
        self.workers = workers
        self.client = CCASSClient()
        self.participants = {}

    def _load_dependencies(self):
        """Load participant list and ensure watchlist is seeded."""
        self.participants = load_participants()
        # Seed watchlist if empty
        from smartflow.db.engine import get_session
        session = get_session()
        from smartflow.db.models import CCASSwatchlist
        count = session.query(CCASSwatchlist).count()
        session.close()
        if count == 0:
            seed_watchlist()

    def _get_target_date(self) -> date:
        """Get the most recent CCASS data date (T-1 on weekdays, skip weekends)."""
        d = date.today() - timedelta(days=1)
        # CCASS not published on weekends
        while d.weekday() >= 5:  # Saturday=5, Sunday=6
            d -= timedelta(days=1)
        return d

    def _compute_metrics(self, stock_code: str, holdings: List[Dict],
                         target_date: date) -> Optional[Dict]:
        """Compute concentration metrics from holdings list."""
        if not holdings:
            return None

        total_shares = sum(h["shares_held"] for h in holdings)

        # Adjusted float: exclude A00005 (CSDC immobilized H-shares)
        csdc_shares = sum(h["shares_held"] for h in holdings if h["participant_id"] == CSDC_ID)
        adjusted_float = total_shares - csdc_shares
        if adjusted_float <= 0:
            adjusted_float = total_shares

        # Broker-only holdings (B-prefix)
        broker_holdings = [h for h in holdings if h["participant_id"].startswith("B")]
        broker_holdings_sorted = sorted(broker_holdings, key=lambda x: x["shares_held"], reverse=True)

        # Top 5 broker % of adjusted float
        top5_shares = sum(h["shares_held"] for h in broker_holdings_sorted[:5])
        brkt5 = (top5_shares / adjusted_float * 100) if adjusted_float > 0 else 0.0

        # FUTU holdings
        futu_holdings = next((h for h in holdings if h["participant_id"] == FUTU_ID), None)
        futu_pct = (futu_holdings["shares_held"] / adjusted_float * 100) if futu_holdings and adjusted_float > 0 else 0.0

        # Top 1 broker
        top1 = broker_holdings_sorted[0] if broker_holdings_sorted else None
        top1_id = top1["participant_id"] if top1 else None
        top1_name = (self.participants.get(top1_id, {}).get("name") or top1["participant_name"]) if top1 else None
        top1_pct = (top1["shares_held"] / adjusted_float * 100) if top1 and adjusted_float > 0 else 0.0

        # Concentration flag
        if brkt5 >= THRESHOLD_RED:
            flag = "RED"
        elif brkt5 >= THRESHOLD_AMBER:
            flag = "AMBER"
        else:
            flag = "GREEN"

        return {
            "stock_code": stock_code,
            "metric_date": target_date,
            "total_ccass_shares": total_shares,
            "adjusted_float": adjusted_float,
            "participant_count": len(holdings),
            "broker_count": len(broker_holdings),
            "brkt5": round(brkt5, 2),
            "futu_pct": round(futu_pct, 2),
            "top1_broker_id": top1_id,
            "top1_broker_name": top1_name,
            "top1_broker_pct": round(top1_pct, 2),
            "concentration_flag": flag,
        }

    def _get_prev_metrics(self, stock_code: str, before_date: date) -> Optional[Dict]:
        """Fetch previous day's metrics for delta calculation."""
        session = get_session()
        prev = (session.query(CCASSMetric)
                .filter(CCASSMetric.stock_code == stock_code,
                        CCASSMetric.metric_date < before_date)
                .order_by(CCASSMetric.metric_date.desc())
                .first())
        result = {"brkt5": prev.brkt5, "futu_pct": prev.futu_pct} if prev else None
        session.close()
        return result

    def _save_holdings(self, stock_code: str, holdings: List[Dict], target_date: date) -> int:
        """Save raw holdings to DB. Returns number inserted."""
        session = get_session()
        inserted = 0
        for h in holdings:
            ptype = get_participant_type(h["participant_id"])
            pname = (self.participants.get(h["participant_id"], {}).get("name")
                     or h["participant_name"])
            row = CCASSHolding(
                stock_code=stock_code,
                holding_date=target_date,
                participant_id=h["participant_id"],
                participant_name=pname,
                participant_type=ptype,
                shares_held=h["shares_held"],
                pct_of_total=h["pct_of_total"],
            )
            session.add(row)
            try:
                session.commit()
                inserted += 1
            except IntegrityError:
                session.rollback()
        session.close()
        return inserted

    def _save_metrics(self, metrics: Dict, prev: Optional[Dict]) -> bool:
        """Save computed metrics to DB."""
        session = get_session()
        m = CCASSMetric(
            stock_code=metrics["stock_code"],
            metric_date=metrics["metric_date"],
            total_ccass_shares=metrics["total_ccass_shares"],
            adjusted_float=metrics["adjusted_float"],
            participant_count=metrics["participant_count"],
            broker_count=metrics["broker_count"],
            brkt5=metrics["brkt5"],
            brkt5_prev=prev["brkt5"] if prev else None,
            brkt5_change=(metrics["brkt5"] - prev["brkt5"]) if prev else None,
            futu_pct=metrics["futu_pct"],
            futu_pct_prev=prev["futu_pct"] if prev else None,
            top1_broker_id=metrics["top1_broker_id"],
            top1_broker_name=metrics["top1_broker_name"],
            top1_broker_pct=metrics["top1_broker_pct"],
            concentration_flag=metrics["concentration_flag"],
        )
        session.add(m)
        try:
            session.commit()
            session.close()
            return True
        except IntegrityError:
            session.rollback()
            session.close()
            return False

    def _process_stock(self, stock: Dict, target_date: date) -> List[Dict]:
        """Fetch, save holdings, compute metrics, return alert signals for one stock."""
        code = stock["stock_code"]
        name = stock.get("stock_name", code)
        signals = []

        try:
            holdings = self.client.fetch_holdings(code, target_date)
            if not holdings:
                self.logger.debug(f"{code}: no holdings returned")
                return signals

            self._save_holdings(code, holdings, target_date)

            metrics = self._compute_metrics(code, holdings, target_date)
            if not metrics:
                return signals

            prev = self._get_prev_metrics(code, target_date)
            self._save_metrics(metrics, prev)

            # Generate alert signals for notable concentration
            flag = metrics["concentration_flag"]
            brkt5 = metrics["brkt5"]
            brkt5_change = (metrics["brkt5"] - prev["brkt5"]) if prev else None

            # Signal: first time RED flag OR BrkT5 spike
            if flag == "RED":
                source_id = f"ccass_red_{code}_{target_date}"
                signals.append({
                    "signal_type": "ccass_high_concentration",
                    "ticker": code,
                    "entity_name": name,
                    "entity_type": "hk_stock",
                    "direction": "SELL",  # High concentration = sell warning
                    "value_usd": None,
                    "filed_at": datetime.combine(target_date, datetime.min.time()),
                    "raw_data": {
                        "brkt5": brkt5,
                        "futu_pct": metrics["futu_pct"],
                        "participant_count": metrics["participant_count"],
                        "top1_broker": metrics["top1_broker_name"],
                        "top1_broker_pct": metrics["top1_broker_pct"],
                        "concentration_flag": flag,
                    },
                    "source_id": source_id,
                })

            # Signal: sudden BrkT5 increase (accumulation) — only if NOT already RED
            # RED takes priority; simultaneous RED + accumulation is a conflict
            if brkt5_change and brkt5_change >= 5.0 and flag != "RED":
                source_id = f"ccass_accum_{code}_{target_date}"
                signals.append({
                    "signal_type": "ccass_accumulation",
                    "ticker": code,
                    "entity_name": name,
                    "entity_type": "hk_stock",
                    "direction": "BUY",
                    "value_usd": None,
                    "filed_at": datetime.combine(target_date, datetime.min.time()),
                    "raw_data": {
                        "brkt5": brkt5,
                        "brkt5_change": round(brkt5_change, 2),
                        "prev_brkt5": round(prev["brkt5"], 2) if prev else None,
                        "top1_broker": metrics["top1_broker_name"],
                    },
                    "source_id": source_id,
                })

            # Signal: FUTU accumulation (retail = distribution warning)
            if metrics["futu_pct"] and metrics["futu_pct"] >= 10.0:
                source_id = f"ccass_futu_{code}_{target_date}"
                signals.append({
                    "signal_type": "ccass_futu_spike",
                    "ticker": code,
                    "entity_name": name,
                    "entity_type": "hk_stock",
                    "direction": "SELL",  # FUTU spike = retail buying = contra-indicator
                    "value_usd": None,
                    "filed_at": datetime.combine(target_date, datetime.min.time()),
                    "raw_data": {
                        "futu_pct": metrics["futu_pct"],
                        "brkt5": brkt5,
                        "note": "FUTU accumulation: historical median return -36.9% (contra-indicator)",
                    },
                    "source_id": source_id,
                })

            self.logger.info(
                f"{code} {target_date}: BrkT5={brkt5:.1f}% "
                f"FUTU={metrics['futu_pct']:.1f}% "
                f"[{flag}] "
                f"{'▲'+str(round(brkt5_change,1))+'%' if brkt5_change and brkt5_change > 0 else ''}"
            )

        except Exception as e:
            self.logger.warning(f"{code}: failed — {e}")

        return signals

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch CCASS data for all watchlist stocks. Returns alert signals."""
        self._load_dependencies()
        target_date = self._get_target_date()
        watchlist = get_active_watchlist()

        self.logger.info(
            f"Collecting CCASS data for {len(watchlist)} stocks, date={target_date}"
        )

        # Pre-load ViewState before spawning threads (avoids race condition)
        if not self.client._fetch_viewstate():
            self.logger.error("Failed to fetch CCASS ViewState — aborting")
            return []

        all_signals = []

        # Parallel scraping with limited workers
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {
                executor.submit(self._process_stock, stock, target_date): stock
                for stock in watchlist
            }
            for future in as_completed(futures):
                try:
                    signals = future.result()
                    all_signals.extend(signals)
                except Exception as e:
                    stock = futures[future]
                    self.logger.warning(f"Worker failed for {stock['stock_code']}: {e}")

        self.logger.info(
            f"CCASS collection done: {len(watchlist)} stocks, {len(all_signals)} alert signals"
        )
        return all_signals
