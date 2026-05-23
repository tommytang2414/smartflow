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


def _get_eth_block_number() -> int:
    """Fetch latest Ethereum block number via public RPC."""
    import requests as _requests
    try:
        resp = _requests.post(
            "https://eth.public-rpc.com",
            json={"method": "eth_blockNumber", "params": [], "id": 1},
            timeout=10,
        )
        resp.raise_for_status()
        return int(resp.json()["result"], 16)
    except Exception:
        return 0


def get_recent_block_number() -> int:
    """Get approximate current block number. Falls back to conservative offset on error."""
    block = _get_eth_block_number()
    if block > 0:
        # Return block - 1000 to get ~last 200 blocks (~40 min of history)
        return block - 1000
    return 19000000  # Static fallback only when RPC fails


class DEXWhaleCollector(BaseCollector):
    """Collect large Uniswap V3 swaps as whale activity signals."""

    name = "dex_whale"
    market = "CRYPTO"

    def _query_dexscreener(self, query: str) -> dict:
        """Query DEXScreener search API for recent large swaps."""
        # DEXScreener search: returns pairs across all chains
        # Filter by volume to find large token movements
        resp = requests.get(
            "https://api.dexscreener.com/latest/dex/search",
            params={"q": query, "limit": 50},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()

    def _fetch_recent_swaps(self, token_addr: str, chain: str = "ethereum") -> List[Dict]:
        """Fetch recent swaps for a specific token from DEXScreener."""
        # Try swaps endpoint (may 404 on some tokens — graceful fallback)
        try:
            resp = requests.get(
                f"https://api.dexscreener.com/latest/dex/tokens/{token_addr}/swaps",
                params={"limit": 20},
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json().get("swaps", [])
        except Exception:
            pass
        return []

    def _whale_pairs(self) -> List[Dict]:
        """Get top pairs by volume across all chains (whale activity proxy)."""
        resp = requests.get(
            "https://api.dexscreener.com/latest/dex/tokens/0xdAC17F958D2ee523a2206206994857ec00eAD1CF",
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        return data.get("pairs") or []

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch recent large DEX pairs as whale activity signals via DEXScreener.

        Strategy: use DEXScreener search to find pairs with high 24h volume —
        large volume = large capital flow = whale activity.
        Also scan top pairs by volume directly.
        """
        self.logger.info("Fetching DEX whale activity via DEXScreener...")

        # Whitelist of major tokens to monitor (whale targets)
        WHALE_TOKENS = [
            ("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "USDC", "ethereum"),
            ("0xdAC17F958D2ee523a2206206994857ec00eAD1CF", "USDT", "ethereum"),
            ("0x2260FAC5E5542a773Aa44fCFfea1B477304A4093", "WBTC", "ethereum"),
            ("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", "WETH", "ethereum"),
            ("0x514910771AF9Ca656af840dff83E8264EcF986CA", "LINK", "ethereum"),
            ("0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984", "UNI", "ethereum"),
            ("0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9", "AAVE", "ethereum"),
            ("0xExchangeToken1", "SOL", "solana"),
            ("0xExchangeToken2", "RAY", "solana"),
        ]

        signals = []
        seen_tickers: set[str] = set()

        # Search for high-volume pairs (whale proxy)
        try:
            result = self._query_dexscreener("BTC ETH USDC USDT")
            pairs = result.get("pairs", []) or []
            self.logger.info(f"DEXScreener search: {len(pairs)} pairs found")
        except Exception as e:
            self.logger.warning(f"DEXScreener search failed: {e}")
            pairs = []

        for pair in pairs[:20]:  # Top 20 by relevance
            try:
                base = pair.get("baseToken", {}) or {}
                quote = pair.get("quoteToken", {}) or {}
                ticker = base.get("symbol", "")
                if not ticker or ticker in seen_tickers:
                    continue
                seen_tickers.add(ticker)

                price_usd = float(pair.get("priceUsd") or 0)
                vol_24h = float(pair.get("volume", {}).get("h24") or 0)
                m5_buys = int(pair.get("txns", {}).get("m5", {}).get("buys") or 0)
                m5_sells = int(pair.get("txns", {}).get("m5", {}).get("sells") or 0)
                chain = pair.get("chainId", "unknown")
                dex = pair.get("dexId", "")
                liquidity = float(pair.get("liquidity", {}).get("usd") or 0)
                price_change = float(pair.get("priceChange", {}).get("h24") or 0)

                # Only flag pairs with significant volume (> $100K 24h)
                if vol_24h < WHALE_THRESHOLD_USD:
                    continue

                # Direction: buy-heavy = bullish, sell-heavy = bearish
                if m5_buys > m5_sells * 2:
                    direction = "BUY"
                elif m5_sells > m5_buys * 2:
                    direction = "SELL"
                else:
                    direction = "HOLD"

                value_usd = vol_24h  # 24h volume as notional
                traded_at = datetime.utcnow()
                source_id = f"dex_whale_{chain}_{ticker}_{traded_at.strftime('%Y%m%d%H%M')}"

                signals.append({
                    "signal_type": "dex_whale_swap",
                    "ticker": ticker,
                    "entity_name": f"{chain}:{dex}",
                    "entity_type": "whale",
                    "direction": direction,
                    "quantity": None,
                    "price": price_usd,
                    "value_usd": round(value_usd, 2),
                    "filed_at": traded_at,
                    "traded_at": traded_at,
                    "raw_data": {
                        "chain": chain,
                        "dex": dex,
                        "pair_address": pair.get("pairAddress", ""),
                        "volume_24h": vol_24h,
                        "liquidity_usd": liquidity,
                        "price_change_24h": price_change,
                        "m5_buys": m5_buys,
                        "m5_sells": m5_sells,
                        "quote_token": quote.get("symbol", ""),
                        "url": pair.get("url", ""),
                    },
                    "source_id": source_id,
                })

            except Exception as e:
                continue

        self.logger.info(f"Parsed {len(signals)} DEX whale signals (vol > $100K)")
        return signals
