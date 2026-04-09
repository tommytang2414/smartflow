"""The Graph / Uniswap V3 DEX Whale Swap Collector.

Tracks large DEX swaps on Uniswap V3 (Ethereum) as a proxy for whale activity.
Large swaps (> $100K) often indicate smart money moving.

Source: https://thegraph.com/explorer/subgraphs/J4vpM9G2mAVCuQXmKtMoJbwft15MsVfC9
Alternative: https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3

signal_type: dex_whale_swap
"""

import requests
from datetime import datetime
from typing import List, Dict, Any
from smartflow.collectors.base import BaseCollector
from smartflow.utils import get_logger, retry

UNISWAP_V3_SUBGRAPH = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"

WHALE_THRESHOLD_USD = 100_000  # $100K minimum swap to flag

QUERY_LARGE_SWAPS = """
query LargeSwaps($minAmount: String!, $blockNumber: Int!) {
  swaps(
    first: 100
    orderBy: amountUSD
    orderDirection: desc
    where: {
      amountUSD_gte: $minAmount
      blockNumber_gte: $blockNumber
    }
  ) {
    id
    transaction { id }
    blockNumber
    timestamp
    account
    origin
    tokenIn { symbol id decimals }
    tokenOut { symbol id decimals }
    amountIn
    amountOut
    amountUSD
    fee
  }
}
"""


def get_recent_block_number() -> int:
    """Approximate current block number (Ethereum ~12s/block)."""
    import time
    return 19000000  # Static fallback — update periodically


class DEXWhaleCollector(BaseCollector):
    """Collect large Uniswap V3 swaps as whale activity signals."""

    name = "dex_whale"
    market = "CRYPTO"

    @retry(max_attempts=3, backoff=2.0)
    def _query_subgraph(self, query: str, variables: dict) -> dict:
        resp = requests.post(
            UNISWAP_V3_SUBGRAPH,
            json={"query": query, "variables": variables},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch recent large DEX swaps on Uniswap V3."""
        self.logger.info("Fetching Uniswap V3 whale swaps")

        try:
            recent_block = get_recent_block_number()
            result = self._query_subgraph(QUERY_LARGE_SWAPS, {
                "minAmount": str(WHALE_THRESHOLD_USD),
                "blockNumber": recent_block - 1000,  # last ~200 blocks (~40 min)
            })
        except Exception as e:
            self.logger.warning(f"Uniswap subgraph query failed: {e}")
            return []

        swaps = result.get("data", {}).get("swaps", [])
        self.logger.info(f"Found {len(swaps)} large swaps (>$100K)")

        signals = []
        seen_ids = set()

        for swap in swaps:
            swap_id = swap.get("id", "")
            if swap_id in seen_ids:
                continue
            seen_ids.add(swap_id)

            amount_usd = float(swap.get("amountUSD", 0) or 0)
            if amount_usd < WHALE_THRESHOLD_USD:
                continue

            token_in = swap.get("tokenIn", {}) or {}
            token_out = swap.get("tokenOut", {}) or {}
            amount_in = float(swap.get("amountIn", 0) or 0)
            amount_out = float(swap.get("amountOut", 0) or 0)

            decimals_in = int(token_in.get("decimals", 18))
            decimals_out = int(token_out.get("decimals", 18))

            price = amount_usd / amount_in if amount_in > 0 else 0

            direction = "BUY" if token_in.get("symbol") == "USDC" or token_in.get("symbol") == "USDT" else "SELL"

            source_id = f"dex_swap_{swap_id}"

            signals.append({
                "signal_type": "dex_whale_swap",
                "ticker": token_out.get("symbol", token_in.get("symbol", "UNKNOWN")),
                "entity_name": f"0x{swap.get('origin', '')[:10]}...",
                "entity_type": "whale",
                "direction": direction,
                "quantity": amount_out / (10 ** decimals_out),
                "price": price,
                "value_usd": round(amount_usd, 2),
                "filed_at": datetime.fromtimestamp(int(swap.get("timestamp", 0))),
                "traded_at": datetime.fromtimestamp(int(swap.get("timestamp", 0))),
                "raw_data": {
                    "swap_id": swap_id,
                    "tx_hash": swap.get("transaction", {}).get("id", ""),
                    "block": swap.get("blockNumber"),
                    "token_in": token_in.get("symbol"),
                    "token_in_address": token_in.get("id"),
                    "amount_in": amount_in / (10 ** decimals_in),
                    "token_out": token_out.get("symbol"),
                    "token_out_address": token_out.get("id"),
                    "amount_out": amount_out / (10 ** decimals_out),
                    "fee_tier": swap.get("fee"),
                    "wallet": swap.get("origin"),
                },
                "source_id": source_id,
            })

        return signals
