"""Market Regime Scanner — SPY/VIX composite + 52-Week High/Low monitor.

Signals:
  BULL      — SPY within 2% of 52w high AND VIX < 15
  RISK_OFF  — SPY within 5% of 52w low OR VIX > 25
  NEUTRAL   — everything else

Also flags individual tickers within 2% of their 52w high → HIGH52W.

Poll: every 15 minutes.
Source: Yahoo Finance v8 Chart API (SPY + %5EVIX).
"""

from datetime import date, datetime
from typing import List, Dict, Any
from smartflow.collectors.base import BaseCollector
from smartflow.helpers.yfinance import fetch_chart, get_universe_tickers

# Regime thresholds
VIX_BULL_THRESHOLD = 15
VIX_RISK_THRESHOLD = 25
SPY_NEAR_HIGH_PCT = 0.02    # within 2% of 52w high
SPY_NEAR_LOW_PCT = 0.05     # within 5% of 52w low


class StockRegimeCollector(BaseCollector):
    name = "stock_regime"
    market = "US_STOCKS"

    def fetch(self) -> List[Dict[str, Any]]:
        signals = []

        # 1. Market regime — SPY + VIX
        regime_signal = self._fetch_regime()
        if regime_signal:
            signals.append(regime_signal)

        # 2. 52w high/low per stock
        high_signals = self._fetch_52w_highs()
        signals.extend(high_signals)

        self.logger.info(f"Regime signals: {len(signals)} total")
        return signals

    def _fetch_regime(self) -> Dict[str, Any]:
        """Compute SPY/VIX composite regime signal."""
        spy_data = fetch_chart("SPY", range="1y")
        vix_data = fetch_chart("%5EVIX", range="5d")

        if not spy_data or not vix_data:
            self.logger.warning("Missing SPY or VIX data for regime")
            return None

        meta = spy_data["meta"]
        spy_price = meta["regularMarketPrice"]
        spy_high = meta.get("fiftyTwoWeekHigh") or meta.get("fiftyTwoWeekHigh")
        spy_low = meta.get("fiftyTwoWeekLow")

        # VIX last reading
        vix_quote = (vix_data.get("indicators", {}).get("quote") or [{}])[0]
        vix_closes = vix_quote.get("close") or []
        vix = vix_closes[-1] if vix_closes else None

        if vix is None:
            self.logger.warning("No VIX data available")
            return None

        # Compute regime
        if spy_high and spy_price >= spy_high * (1 - SPY_NEAR_HIGH_PCT) and vix < VIX_BULL_THRESHOLD:
            regime = "BULL"
        elif (spy_low and spy_price <= spy_low * (1 + SPY_NEAR_LOW_PCT)) or vix > VIX_RISK_THRESHOLD:
            regime = "RISK_OFF"
        else:
            regime = "NEUTRAL"

        today = date.today().isoformat()

        return {
            "market": self.market,
            "signal_type": f"market_regime_{regime.lower()}",
            "ticker": "SPY",
            "entity_name": "Market",
            "entity_type": "market_index",
            "direction": None,
            "quantity": None,
            "price": spy_price,
            "value_usd": None,
            "filed_at": datetime.utcnow(),
            "traded_at": datetime.utcnow(),
            "source_id": f"SPY:regime:{today}",
            "raw_data": {
                "spy_price": spy_price,
                "spy_52w_high": spy_high,
                "spy_52w_low": spy_low,
                "vix": round(vix, 2),
                "regime": regime,
                "spy_pct_from_high": round((spy_high - spy_price) / spy_high * 100, 2) if spy_high else None,
                "spy_pct_from_low": round((spy_price - spy_low) / spy_low * 100, 2) if spy_low else None,
            },
        }

    def _fetch_52w_highs(self) -> List[Dict[str, Any]]:
        """Flag stocks within 2% of their 52w high."""
        tickers = get_universe_tickers()
        exclude = {"SPY", "XLK", "XLF", "XLV", "XLE", "XLY", "XLI", "XRE", "XLB", "XLU", "%5EVIX"}
        stock_tickers = [t for t in tickers if t not in exclude]

        signals = []
        today = date.today().isoformat()

        for ticker in stock_tickers:
            try:
                data = fetch_chart(ticker, range="1y")
                if not data:
                    continue

                meta = data["meta"]
                price = meta.get("regularMarketPrice")
                high_52 = meta.get("fiftyTwoWeekHigh")
                low_52 = meta.get("fiftyTwoWeekLow")

                if price is None or high_52 is None:
                    continue

                # Within 2% of 52w high
                if high_52 > 0 and price >= high_52 * (1 - SPY_NEAR_HIGH_PCT):
                    signals.append({
                        "market": self.market,
                        "signal_type": "high52w",
                        "ticker": ticker,
                        "entity_name": ticker,
                        "entity_type": "stock",
                        "direction": "BUY",         # near-high = institutional momentum
                        "quantity": None,
                        "price": price,
                        "value_usd": None,
                        "filed_at": datetime.utcnow(),
                        "traded_at": datetime.utcnow(),
                        "source_id": f"{ticker}:52whigh:{today}",
                        "raw_data": {
                            "price": price,
                            "high52w": high_52,
                            "low52w": low_52,
                            "pct_from_high": round((high_52 - price) / high_52 * 100, 2),
                        },
                    })
            except Exception as e:
                self.logger.warning(f"{ticker}: {e}")
                continue

        return signals