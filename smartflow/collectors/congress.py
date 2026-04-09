"""Congress Trades Collector.

Fetches US Congress member stock trades from QuiverQuant free API.
Congress members must disclose trades within 45 days (STOCK Act).
"""

import requests
from datetime import datetime
from typing import List, Dict, Any
from smartflow.collectors.base import BaseCollector
from smartflow.utils import RateLimiter, retry

QUIVER_CONGRESS_URL = "https://api.quiverquant.com/beta/live/congresstrading"


class CongressCollector(BaseCollector):
    """Collect Congress member stock trades via QuiverQuant."""

    name = "congress"
    market = "US"

    def __init__(self):
        super().__init__()
        self.rate_limiter = RateLimiter(2)
        self.headers = {
            "User-Agent": "SmartFlow/0.1",
        }

    @retry(max_attempts=3)
    def _get(self, url: str) -> requests.Response:
        self.rate_limiter.wait()
        resp = requests.get(url, headers=self.headers, timeout=30)
        resp.raise_for_status()
        return resp

    def _parse_amount(self, amount_str: str) -> float:
        """Parse amount range string like '$1,001 - $15,000' to midpoint."""
        if not amount_str:
            return 0.0
        amount_str = str(amount_str).replace("$", "").replace(",", "").strip()

        if " - " in amount_str:
            parts = amount_str.split(" - ")
            try:
                low = float(parts[0].strip())
                high = float(parts[1].strip())
                return (low + high) / 2
            except ValueError:
                return 0.0

        try:
            return float(amount_str)
        except ValueError:
            return 0.0

    def _normalize_direction(self, tx_type: str) -> str:
        tx_type = tx_type.lower().strip() if tx_type else ""
        if "purchase" in tx_type or "buy" in tx_type:
            return "BUY"
        elif "sale" in tx_type or "sell" in tx_type:
            return "SELL"
        elif "exchange" in tx_type:
            return "EXCHANGE"
        return tx_type.upper()

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch recent Congress trades from QuiverQuant."""
        self.logger.info("Fetching Congress trades from QuiverQuant...")

        try:
            resp = self._get(QUIVER_CONGRESS_URL)
            data = resp.json()
        except Exception as e:
            self.logger.error(f"Failed to fetch QuiverQuant data: {e}")
            return []

        if not isinstance(data, list):
            self.logger.warning(f"Unexpected response format: {type(data)}")
            return []

        self.logger.info(f"Found {len(data)} Congress transactions")

        signals = []
        for txn in data:
            ticker = txn.get("Ticker", "")
            if not ticker or ticker == "--" or ticker == "N/A":
                continue

            representative = txn.get("Representative", "Unknown")
            tx_type = txn.get("Transaction", "")
            amount_range = txn.get("Range", "")
            amount_val = txn.get("Amount", "")
            tx_date = txn.get("TransactionDate", "")
            report_date = txn.get("ReportDate", "")
            chamber = txn.get("House", "")
            party = txn.get("Party", "")

            direction = self._normalize_direction(tx_type)

            # Use Amount if available, otherwise parse Range
            if amount_val:
                value_usd = self._parse_amount(str(amount_val))
            else:
                value_usd = self._parse_amount(amount_range)

            traded_at = None
            if tx_date:
                try:
                    traded_at = datetime.strptime(tx_date, "%Y-%m-%d")
                except ValueError:
                    pass

            filed_at = None
            if report_date:
                try:
                    filed_at = datetime.strptime(report_date, "%Y-%m-%d")
                except ValueError:
                    pass

            source_id = f"congress_{representative}_{ticker}_{tx_date}"

            signals.append({
                "signal_type": f"congress_{direction.lower()}",
                "ticker": ticker.upper(),
                "entity_name": representative,
                "entity_type": "congress",
                "direction": direction,
                "value_usd": value_usd,
                "filed_at": filed_at,
                "traded_at": traded_at,
                "raw_data": {
                    "chamber": chamber,
                    "party": party,
                    "transaction_type": tx_type,
                    "amount_range": amount_range,
                    "bio_guide_id": txn.get("BioGuideID", ""),
                    "excess_return": txn.get("ExcessReturn"),
                    "price_change": txn.get("PriceChange"),
                    "spy_change": txn.get("SPYChange"),
                },
                "source_id": source_id,
            })

        self.logger.info(f"Parsed {len(signals)} Congress trade signals")
        return signals
