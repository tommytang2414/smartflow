"""Arkham Intelligence Collector.

Labels whale wallet addresses for the crypto pipeline.
Arkham provides entity labels (e.g., "Binance Hot Wallet", "Justin Sun", "Jump Trading").

Source: https://api.arkhamintelligence.com/v1
API Key: Free tier available at https://app.arkhamintelligence.com

Use case: Label unknown whale addresses from CoinGlass/Whale Alert data.
Run as enrichment after whale data is collected.

signal_type: wallet_label (enrichment — adds labels to raw wallet data)
"""

import requests
from datetime import datetime
from typing import List, Dict, Any, Optional
from smartflow.collectors.base import BaseCollector
from smartflow.utils import get_logger, retry

ARKHAM_BASE_URL = "https://api.arkhamintelligence.com/v1"


class ArkhamClient:
    """Low-level Arkham Intelligence API client."""

    HEADERS = {
        "User-Agent": "SmartFlow/1.0",
        "Accept": "application/json",
    }

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.logger = get_logger("arkham_client")

    def _get(self, endpoint: str, params: dict = None) -> Optional[dict]:
        if not self.api_key:
            self.logger.warning("ARKHAM_API_KEY not set — skipping")
            return None

        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            resp = self.session.get(
                f"{ARKHAM_BASE_URL}/{endpoint}",
                params=params,
                headers=headers,
                timeout=30,
            )
            if resp.status_code == 401:
                self.logger.error("Arkham API key invalid")
                return None
            if resp.status_code == 403:
                self.logger.warning("Arkham API access denied (check plan limits)")
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self.logger.warning(f"Arkham API error: {e}")
            return None

    def search_entity(self, query: str) -> Optional[List[Dict]]:
        """Search for entity by name/address."""
        data = self._get("entities/search", params={"query": query})
        if not data:
            return None
        return data.get("results", []) or data.get("entities", [])

    def get_entity_transactions(self, entity_id: str, limit: int = 50) -> Optional[List[Dict]]:
        """Get transactions for a labeled entity."""
        data = self._get(f"entities/{entity_id}/transactions", params={"limit": limit})
        if not data:
            return None
        return data.get("transactions", []) or data.get("results", [])

    def get_address_labels(self, address: str, chain: str = "ethereum") -> Optional[Dict]:
        """Get labels for a specific wallet address."""
        data = self._get(f"addresses/{chain}/{address}")
        if not data:
            return None
        return data

    def get_large_transactions(self, min_usd: float = 100_000,
                                chains: List[str] = None,
                                limit: int = 100) -> Optional[List[Dict]]:
        """Get recent large transactions across chains."""
        chains = chains or ["ethereum", "bitcoin", "solana"]
        all_txs = []

        for chain in chains:
            params = {
                "minValue": min_usd,
                "limit": limit,
                "chain": chain,
            }
            data = self._get("transactions", params=params)
            if data:
                txs = data.get("transactions", []) or data.get("results", []) or []
                all_txs.extend(txs)

        return all_txs if all_txs else None


def label_known_whale(address: str, api_key: str) -> Optional[str]:
    """Quick helper: get a label for a whale address."""
    client = ArkhamClient(api_key)
    result = client.get_address_labels(address)
    if not result:
        return None
    entities = result.get("entities", []) or result.get("labels", [])
    if entities:
        return entities[0].get("name") or entities[0].get("label")
    return None


class ArkhamWhaleLabelCollector(BaseCollector):
    """Label unknown whale addresses using Arkham Intelligence.

    This collector is different from other collectors — it enriches
    existing data rather than fetching new signals. It should be run
    after other whale collectors to label newly discovered addresses.
    """

    name = "arkham_labels"
    market = "CRYPTO"

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch labels for whale addresses found in other pipelines."""
        from smartflow.config import ARKHAM_API_KEY

        if not ARKHAM_API_KEY:
            self.logger.warning("ARKHAM_API_KEY not set — Arkham labels skipped")
            return []

        client = ArkhamClient(ARKHAM_API_KEY)
        signals = []

        # Get recent CoinGlass whale addresses that need labeling
        from smartflow.db.engine import get_session
        from smartflow.db.models import SmartMoneySignal

        session = get_session()
        recent_whales = (
            session.query(SmartMoneySignal)
            .filter(
                SmartMoneySignal.source == "coinglass_whale",
                SmartMoneySignal.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0)
            )
            .limit(100)
            .all()
        )
        session.close()

        # Get known labeled addresses from a small cache
        labeled_cache = {}

        for whale in recent_whales:
            raw = whale.raw_data or {}
            address = raw.get("wallet") or raw.get("address") or ""
            if not address or address in labeled_cache:
                continue

            label = client.get_address_labels(address)
            if not label:
                continue

            entities = label.get("entities", []) or label.get("labels", [])
            if not entities:
                continue

            entity_name = entities[0].get("name") or entities[0].get("label")
            if not entity_name:
                continue

            labeled_cache[address] = entity_name

            source_id = f"arkham_label_{address}"

            signals.append({
                "signal_type": "wallet_label",
                "market": "CRYPTO",
                "ticker": whale.ticker,
                "entity_name": entity_name,
                "entity_type": "labeled_whale",
                "direction": whale.direction,
                "quantity": whale.quantity,
                "price": whale.price,
                "value_usd": whale.value_usd,
                "filed_at": whale.filed_at,
                "traded_at": whale.traded_at,
                "raw_data": {
                    "address": address,
                    "label": entity_name,
                    "source": "arkham_intelligence",
                    "original_entity": whale.entity_name,
                },
                "source_id": source_id,
            })

        self.logger.info(f"Arkham labeled {len(signals)} whale addresses")
        return signals
