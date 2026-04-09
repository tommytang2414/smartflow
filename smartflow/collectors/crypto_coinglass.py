"""CoinGlass Collector — Crypto Whale Activity.

Uses CoinGlass API (free tier) to track large positions on Hyperliquid.
API Key found in CryptoStrategy project.

signal_type: whale_long, whale_short, whale_liquidation
"""

import requests
from datetime import datetime
from typing import List, Dict, Any
from smartflow.collectors.base import BaseCollector
from smartflow.config import COINGLASS_API_KEY
from smartflow.utils import RateLimiter

COINGLASS_BASE = "https://open-api-v4.coinglass.com"


class CoinGlassWhaleCollector(BaseCollector):
    """Collect crypto whale positions from CoinGlass Hyperliquid API."""

    name = "coinglass_whale"
    market = "CRYPTO"

    def __init__(self):
        super().__init__()
        self.api_key = COINGLASS_API_KEY
        self.rate_limiter = RateLimiter(10)
        self.headers = {"CG-API-KEY": self.api_key} if self.api_key else {}

    def _get(self, endpoint: str) -> requests.Response:
        self.rate_limiter.wait()
        resp = requests.get(
            f"{COINGLASS_BASE}{endpoint}",
            headers=self.headers,
            timeout=30
        )
        resp.raise_for_status()
        return resp

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch recent whale positions from CoinGlass."""
        if not self.api_key:
            self.logger.warning("COINGLASS_API_KEY not set")
            return []

        self.logger.info("Fetching whale positions from CoinGlass...")
        signals = []

        try:
            resp = self._get("/api/hyperliquid/whale-alert")
            data = resp.json()

            if data.get("code") != "0":
                self.logger.warning(f"CoinGlass API error: {data}")
                return []

            whales = data.get("data", [])
            self.logger.info(f"Found {len(whales)} whale positions")

            for w in whales:
                symbol = w.get("symbol", "")
                position_size = w.get("position_size", 0)
                position_value = w.get("position_value_usd", 0)
                position_action = w.get("position_action")
                create_time_ms = w.get("create_time")

                if not symbol or not create_time_ms:
                    continue

                traded_at = datetime.fromtimestamp(create_time_ms / 1000)

                direction = "BUY"
                signal_type = "whale_long"
                if position_action == 2:
                    direction = "SELL"
                    signal_type = "whale_short"
                elif position_action == 3:
                    signal_type = "whale_liquidation"
                    direction = "LIQUIDATED"

                source_id = f"coinglass_whale_{w.get('user', '')[:20]}_{symbol}_{create_time_ms}"

                signals.append({
                    "signal_type": signal_type,
                    "ticker": symbol.upper(),
                    "entity_name": w.get("user", "")[:40],
                    "entity_type": "whale",
                    "direction": direction,
                    "quantity": abs(position_size),
                    "price": w.get("entry_price"),
                    "value_usd": abs(position_value),
                    "filed_at": datetime.utcnow(),
                    "traded_at": traded_at,
                    "raw_data": {
                        "wallet": w.get("user", ""),
                        "symbol": symbol,
                        "position_size": position_size,
                        "entry_price": w.get("entry_price"),
                        "liq_price": w.get("liq_price"),
                        "position_value_usd": position_value,
                        "position_action": position_action,
                        "exchange": "Hyperliquid",
                    },
                    "source_id": source_id,
                })

        except Exception as e:
            self.logger.error(f"Failed to fetch CoinGlass data: {e}")

        self.logger.info(f"Parsed {len(signals)} whale signals")
        return signals


class CoinGlassOICollector(BaseCollector):
    """Collect crypto open interest data from CoinGlass."""

    name = "coinglass_oi"
    market = "CRYPTO"

    def __init__(self):
        super().__init__()
        self.api_key = COINGLASS_API_KEY
        self.rate_limiter = RateLimiter(10)
        self.headers = {"CG-API-KEY": self.api_key} if self.api_key else {}

    def _get(self, endpoint: str) -> requests.Response:
        self.rate_limiter.wait()
        resp = requests.get(
            f"{COINGLASS_BASE}{endpoint}",
            headers=self.headers,
            timeout=30
        )
        resp.raise_for_status()
        return resp

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch open interest data from CoinGlass."""
        if not self.api_key:
            self.logger.warning("COINGLASS_API_KEY not set")
            return []

        self.logger.info("Fetching OI data from CoinGlass...")
        signals = []

        try:
            resp = self._get("/api/futures/open-interest/aggregated-history?symbol=BTC&interval=1h")
            data = resp.json()

            oi_data = data.get("data", [])
            if not oi_data:
                return []

            latest = oi_data[-1]
            self.logger.info(f"BTC OI latest: {latest}")

            source_id = f"coinglass_oi_btc_{latest.get('time', '')}"

            signals.append({
                "signal_type": "oi_level",
                "ticker": "BTC",
                "entity_name": "CoinGlass",
                "entity_type": "aggregate",
                "direction": "HOLD",
                "quantity": None,
                "price": None,
                "value_usd": float(latest.get("close", 0)),
                "filed_at": datetime.utcnow(),
                "traded_at": datetime.fromtimestamp(latest["time"] / 1000) if latest.get("time") else None,
                "raw_data": {
                    "open": latest.get("open"),
                    "high": latest.get("high"),
                    "low": latest.get("low"),
                    "close": latest.get("close"),
                    "interval": "1h",
                },
                "source_id": source_id,
            })

        except Exception as e:
            self.logger.error(f"Failed to fetch CoinGlass OI data: {e}")

        self.logger.info(f"Parsed {len(signals)} OI signals")
        return signals
