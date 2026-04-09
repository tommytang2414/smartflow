"""Whale Alert API Collector.

Tracks large cryptocurrency transactions across multiple chains.
Free tier: 10 requests/minute, transactions > $100K only.

Source: https://api.whale-alert.io/v1/transactions
API Key: Set WHALE_ALERT_API_KEY in .env (free tier available)

signal_type: whale_transfer_in, whale_transfer_out
"""

import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from smartflow.collectors.base import BaseCollector
from smartflow.utils import get_logger, retry

WHALE_ALERT_URL = "https://api.whale-alert.io/v1/transactions"
MIN_VALUE_USD = 100_000  # Free tier only shows >$100K


class WhaleAlertClient:
    """Low-level Whale Alert API client."""

    HEADERS = {
        "User-Agent": "SmartFlow/1.0",
    }

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.logger = get_logger("whale_alert_client")

    @retry(max_attempts=3, backoff=2.0)
    def fetch_transactions(self,
                           start: datetime = None,
                           end: datetime = None,
                           min_value: int = MIN_VALUE_USD) -> Optional[List[Dict]]:
        """Fetch whale alert transactions.

        Args:
            start: Start time (default: 6 hours ago)
            end: End time (default: now)
            min_value: Minimum USD value (default: $100K)
        """
        if not self.api_key:
            self.logger.warning("WHALE_ALERT_API_KEY not set — skipping")
            return None

        if start is None:
            start = datetime.utcnow() - timedelta(hours=6)
        if end is None:
            end = datetime.utcnow()

        params = {
            "key": self.api_key,
            "start": int(start.timestamp()),
            "end": int(end.timestamp()),
            "min_value": min_value,
        }

        try:
            resp = self.session.get(WHALE_ALERT_URL, params=params, timeout=30)
            if resp.status_code == 401:
                self.logger.error("Whale Alert API key invalid")
                return None
            if resp.status_code == 429:
                self.logger.warning("Whale Alert rate limited")
                return None
            resp.raise_for_status()
            data = resp.json()
            return data.get("transactions", [])
        except requests.exceptions.HTTPError as e:
            self.logger.warning(f"Whale Alert HTTP error: {e}")
            return None
        except Exception as e:
            self.logger.warning(f"Whale Alert fetch error: {e}")
            return None


def _chain_to_market(chain: str) -> str:
    """Map Whale Alert chain to our market tag."""
    mapping = {
        "bitcoin": "CRYPTO",
        "ethereum": "CRYPTO",
        "solana": "CRYPTO",
        "tron": "CRYPTO",
        "ripple": "CRYPTO",
        "cardano": "CRYPTO",
        "dogecoin": "CRYPTO",
        "polkadot": "CRYPTO",
        "avalanche": "CRYPTO",
        "chainlink": "CRYPTO",
    }
    return mapping.get(chain.lower(), "CRYPTO")


def _detect_direction(tx: Dict) -> str:
    """Detect transfer direction from known exchange addresses."""
    from_add = tx.get("from", {})
    to_add = tx.get("to", {})

    known_exchanges = [
        "binance", "coinbase", "kraken", "ftx", "huobi",
        "okx", "kucoin", "bitfinex", "gemini", "bithumb",
    ]

    from_name = (from_add.get("owner", {}) or {}).get("name", "").lower()
    to_name = (to_add.get("owner", {}) or {}).get("name", "").lower()

    if any(ex in from_name for ex in known_exchanges):
        return "TRANSFER_OUT"
    if any(ex in to_name for ex in known_exchanges):
        return "TRANSFER_IN"
    return "TRANSFER"


class WhaleAlertCollector(BaseCollector):
    """Collect whale transactions via Whale Alert API."""

    name = "whale_alert"
    market = "CRYPTO"

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch recent whale transactions."""
        from smartflow.config import WHALE_ALERT_API_KEY

        client = WhaleAlertClient(WHALE_ALERT_API_KEY)
        transactions = client.fetch_transactions()

        if transactions is None:
            return []

        self.logger.info(f"Whale Alert: {len(transactions)} transactions")
        signals = []

        for tx in transactions:
            blockchain = tx.get("blockchain", "unknown")
            symbol = tx.get("symbol", "")
            amount = float(tx.get("amount", 0) or 0)
            amount_usd = float(tx.get("amount_usd", 0) or 0)
            timestamp = tx.get("timestamp", 0)

            from_add = (tx.get("from", {}) or {})
            to_add = (tx.get("to", {}) or {})
            from_owner = (from_add.get("owner", {}) or {})
            to_owner = (to_add.get("owner", {}) or {})

            source_id = f"whale_{blockchain}_{tx.get('id', '')}_{tx.get('hash', '')}"

            direction = _detect_direction(tx)

            signals.append({
                "signal_type": "whale_transfer",
                "market": _chain_to_market(blockchain),
                "ticker": symbol,
                "entity_name": from_owner.get("name") or to_owner.get("name") or f"{blockchain} wallet",
                "entity_type": "whale",
                "direction": direction,
                "quantity": amount,
                "price": amount_usd / amount if amount > 0 else 0,
                "value_usd": round(amount_usd, 2),
                "filed_at": datetime.fromtimestamp(timestamp) if timestamp else datetime.utcnow(),
                "traded_at": datetime.fromtimestamp(timestamp) if timestamp else datetime.utcnow(),
                "raw_data": {
                    "tx_id": tx.get("id"),
                    "hash": tx.get("hash"),
                    "blockchain": blockchain,
                    "from_address": from_add.get("address"),
                    "from_owner_name": from_owner.get("name"),
                    "to_address": to_add.get("address"),
                    "to_owner_name": to_owner.get("name"),
                    "transaction_type": tx.get("transaction_type"),
                    "flag_on_gui": tx.get("flag_on_gui"),
                },
                "source_id": source_id,
            })

        return signals
