"""Stock Volume Anomaly Scanner.

Tracks unusual volume spikes in the US stock universe.
Volume > 3x 20-day average → signal.

Signal types:
  ACCUMULATION — price up + volume spike (smart money buying)
  DISTRIBUTION — price down + volume spike (smart money selling)
  VOLUME_SPIKE_NEUTRAL — volume spike but price flat (unknown direction)

Poll: every 15 minutes during US market hours.
Source: Yahoo Finance v8 Chart API (no key required).
"""

import time
from datetime import date
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from smartflow.collectors.base import BaseCollector
from smartflow.helpers.yfinance import fetch_daily_bars, get_universe_tickers, rate_limit_sleep

VOLUME_SPIKE_THRESHOLD = 3.0   # volume must be 3x average to trigger
LOOKBACK_BARS = 20             # bars to compute rolling average (excludes today)
MIN_VOLUME = 5_000_000          # skip very low volume stocks (likely pre-ipo / dead)
POLL_INTERVAL = 900            # 15 min
TIMEOUT = 120                  # seconds


class StockVolumeCollector(BaseCollector):
    name = "stock_volume"
    market = "US_STOCKS"

    def fetch(self) -> List[Dict[str, Any]]:
        tickers = get_universe_tickers()
        # Exclude index/ETF tickers — we only track stocks
        exclude = {"SPY", "XLK", "XLF", "XLV", "XLE", "XLY", "XLI", "XRE", "XLB", "XLU", "%5EVIX"}
        stock_tickers = [t for t in tickers if t not in exclude]

        self.logger.info(f"Checking {len(stock_tickers)} stocks for volume anomalies...")

        results = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(self._check_ticker, ticker): ticker
                for ticker in stock_tickers
            }
            for future in as_completed(futures, timeout=TIMEOUT):
                ticker = futures[future]
                try:
                    signals = future.result()
                    if signals:
                        results.extend(signals)
                except Exception as e:
                    self.logger.warning(f"{ticker} failed: {e}")

        self.logger.info(f"Volume anomalies found: {len(results)}")
        return results

    def _check_ticker(self, ticker: str) -> List[Dict[str, Any]]:
        """Check one ticker for volume anomaly. Returns list (0, 1, or 2 signals)."""
        bars = fetch_daily_bars(ticker, range="1mo")
        if not bars or len(bars) < LOOKBACK_BARS + 1:
            return []

        # Separate last bar (today) from historical bars
        today_bar = bars[-1]
        hist_bars = bars[:-1]

        # Compute 20-day rolling average from historical (exclude today)
        hist_volumes = [b["volume"] for b in hist_bars if b["volume"] and b["volume"] > 0]
        if len(hist_volumes) < LOOKBACK_BARS:
            return []

        avg_vol = sum(hist_volumes) / len(hist_volumes)

        # Skip low-volume stocks
        if avg_vol < MIN_VOLUME:
            return []

        last_vol = today_bar["volume"]
        last_close = today_bar["close"]
        prev_close = hist_bars[-1]["close"] if hist_bars else None

        if last_vol is None or last_close is None or prev_close is None:
            return []

        vol_ratio = last_vol / avg_vol
        price_change = (last_close - prev_close) / prev_close * 100

        today_date = today_bar["timestamp"].date()

        # Only signal if volume spike threshold met
        if vol_ratio < VOLUME_SPIKE_THRESHOLD:
            return []

        # Determine direction
        if price_change > 0.5:
            signal_type = "volume_accumulation"    # price up + big vol
            direction = "BUY"
        elif price_change < -0.5:
            signal_type = "volume_distribution"    # price down + big vol
            direction = "SELL"
        else:
            signal_type = "volume_spike_neutral"  # big vol but price flat
            direction = "HOLD"

        # Only flag SPY/volume regime if today's bar is recent (weekday, not pre-market weirdness)
        # Always store — the date check is informational

        return [{
            "market": self.market,
            "signal_type": signal_type,
            "ticker": ticker,
            "entity_name": ticker,
            "entity_type": "stock",
            "direction": direction,
            "quantity": last_vol,
            "price": last_close,
            "value_usd": last_vol * last_close,       # approximate dollar volume
            "filed_at": today_bar["timestamp"],
            "traded_at": today_bar["timestamp"],
            "source_id": f"{ticker}:vol:{today_date.isoformat()}",
            "raw_data": {
                "volume": last_vol,
                "avg_volume_20d": avg_vol,
                "vol_ratio": round(vol_ratio, 2),
                "price_change_pct": round(price_change, 2),
                "prev_close": prev_close,
            },
        }]