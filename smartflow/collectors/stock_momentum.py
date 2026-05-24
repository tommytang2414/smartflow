"""Price Momentum Ranker — ranked across 4 timeframes.

Fetches all stocks, computes 1d/5d/20d/60d returns, then ranks.
Top 20% = momentum_long, bottom 20% = momentum_short.

Poll: hourly (momentum doesn't change fast).
Source: Yahoo Finance v8 Chart API (no key required).
"""

import time
from datetime import datetime, date
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from smartflow.collectors.base import BaseCollector
from smartflow.helpers.yfinance import fetch_daily_bars, get_universe_tickers

RANGE_60D = "3mo"    # enough to get 60d return
TOP_PCT = 0.20       # top 20% = momentum_long
BOTTOM_PCT = 0.20    # bottom 20% = momentum_short
POLL_INTERVAL = 3600  # 1 hour
TIMEOUT = 180        # seconds


def compute_returns(bars: List[Dict], periods: List[int]) -> Dict[int, float]:
    """Compute percentage return for each period. bars[-1] = today."""
    if not bars or len(bars) < max(periods) + 1:
        return {}
    closes = [b["close"] for b in bars if b.get("close")]
    if len(closes) < max(periods) + 1:
        return {}
    latest = closes[-1]
    returns = {}
    for p in periods:
        if len(closes) >= p + 1:
            prev = closes[-p - 1]
            if prev and prev > 0:
                returns[p] = round((latest - prev) / prev * 100, 3)
    return returns


def percentile_rank(value: float, all_values: List[float]) -> float:
    """Return percentile of value among all_values (0-100)."""
    sorted_vals = sorted(all_values)
    count_below = sum(1 for v in sorted_vals if v < value)
    return round(count_below / len(sorted_vals) * 100, 1)


class StockMomentumCollector(BaseCollector):
    name = "stock_momentum"
    market = "US_STOCKS"

    def fetch(self) -> List[Dict[str, Any]]:
        tickers = get_universe_tickers()
        exclude = {"SPY", "XLK", "XLF", "XLV", "XLE", "XLY", "XLI", "XRE", "XLB", "XLU", "%5EVIX"}
        stock_tickers = [t for t in tickers if t not in exclude]

        self.logger.info(f"Computing momentum for {len(stock_tickers)} stocks...")

        # Step 1: fetch all data in parallel
        raw_data: Dict[str, Dict] = {}
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(self._fetch_ticker_data, ticker): ticker
                for ticker in stock_tickers
            }
            for future in as_completed(futures, timeout=TIMEOUT):
                ticker = futures[future]
                try:
                    data = future.result()
                    if data:
                        raw_data[ticker] = data
                except Exception as e:
                    self.logger.warning(f"{ticker}: {e}")

        # Step 2: compute returns for each ticker
        all_tickers = list(raw_data.keys())
        all_1d = []
        all_5d = []
        all_20d = []
        all_60d = []

        ticker_returns = {}
        for ticker, data in raw_data.items():
            returns = compute_returns(data["bars"], [1, 5, 20, 60])
            if returns:
                ticker_returns[ticker] = returns
                all_1d.append(returns.get(1, 0))
                all_5d.append(returns.get(5, 0))
                all_20d.append(returns.get(20, 0))
                all_60d.append(returns.get(60, 0))

        # Step 3: rank each ticker across 4 timeframes
        scored = []
        for ticker, returns in ticker_returns.items():
            r1 = returns.get(1, 0)
            r5 = returns.get(5, 0)
            r20 = returns.get(20, 0)
            r60 = returns.get(60, 0)

            p1 = percentile_rank(r1, all_1d)
            p5 = percentile_rank(r5, all_5d)
            p20 = percentile_rank(r20, all_20d)
            p60 = percentile_rank(r60, all_60d)

            # Composite: weighted average (more weight on longer-term)
            composite = round((p1 * 0.1 + p5 * 0.2 + p20 * 0.3 + p60 * 0.4), 1)

            scored.append({
                "ticker": ticker,
                "returns": returns,
                "percentiles": {"1d": p1, "5d": p5, "20d": p20, "60d": p60},
                "composite": composite,
                "last_close": raw_data[ticker]["bars"][-1]["close"],
                "last_bar": raw_data[ticker]["bars"][-1]["timestamp"],
            })

        # Step 4: sort by composite score, emit signals
        scored.sort(key=lambda x: x["composite"], reverse=True)
        n = len(scored)
        top_n = max(1, int(n * TOP_PCT))
        bottom_n = max(1, int(n * BOTTOM_PCT))

        today = date.today().isoformat()
        signals = []

        for i, item in enumerate(scored):
            if i < top_n:
                signal_type = "momentum_long"
                direction = "BUY"
            elif i >= n - bottom_n:
                signal_type = "momentum_short"
                direction = "SELL"
            else:
                continue  # skip middle 60%

            signals.append({
                "market": self.market,
                "signal_type": signal_type,
                "ticker": item["ticker"],
                "entity_name": item["ticker"],
                "entity_type": "stock",
                "direction": direction,
                "quantity": None,
                "price": item["last_close"],
                "value_usd": 0,  # rank-based, no dollar value
                "filed_at": datetime.utcnow(),
                "traded_at": item["last_bar"],
                "source_id": f"{item['ticker']}:momentum:{today}",
                "raw_data": {
                    "1d": item["returns"].get(1, 0),
                    "5d": item["returns"].get(5, 0),
                    "20d": item["returns"].get(20, 0),
                    "60d": item["returns"].get(60, 0),
                    "composite_score": item["composite"],
                    "percentile_1d": item["percentiles"]["1d"],
                    "percentile_5d": item["percentiles"]["5d"],
                    "percentile_20d": item["percentiles"]["20d"],
                    "percentile_60d": item["percentiles"]["60d"],
                    "rank": i + 1,
                    "total": n,
                },
            })

        self.logger.info(f"Momentum: {top_n} long, {bottom_n} short out of {n} stocks")
        return signals

    def _fetch_ticker_data(self, ticker: str) -> Dict[str, Any]:
        """Fetch daily bars for a ticker. Returns None on failure."""
        bars = fetch_daily_bars(ticker, range=RANGE_60D)
        return {"bars": bars} if bars else None