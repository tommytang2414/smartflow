"""Yahoo Finance API helper — shared across stock collectors.

Uses the v8 Chart API: https://query1.finance.yahoo.com/v8/finance/chart/{ticker}
No API key required. Requires email User-Agent per SEC guidance (not SEC's rule,
but Yahoo's — we use it anyway to avoid 403s).

Usage:
    from smartflow.helpers.yfinance import fetch_chart, fetch_daily_bars

    data = fetch_chart("AAPL", range="1mo", interval="1d")
    # data = { "meta": {...}, "timestamp": [...], "indicators": {...} }
"""

import time
import requests
from datetime import datetime
from typing import Optional, List, Dict, Any
from smartflow.utils import get_logger, retry

YAHOO_CHART_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (smartflow@tommytang.cc)"

logger = get_logger("yfinance")


@retry(max_attempts=3, backoff=2.0)
def _get(url: str, params: Optional[dict] = None) -> dict:
    """HTTP GET with retry + error handling."""
    resp = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=15)
    if resp.status_code == 404:
        raise ValueError(f"404 Not Found: {url}")
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def fetch_chart(
    ticker: str,
    range: str = "1mo",
    interval: str = "1d",
) -> Optional[Dict[str, Any]]:
    """Fetch OHLCV chart data for a ticker.

    Args:
        ticker: e.g. "AAPL", "SPY", "%5EVIX" (VIX)
        range: "1d", "5d", "1mo", "3mo", "1y", "5y", "max"
        interval: "5m", "1h", "1d", "1wk"

    Returns:
        dict with keys: meta, timestamp, indicators (quote,adjclose) or None on failure
    """
    url = f"{YAHOO_CHART_BASE}/{ticker}"
    params = {"range": range, "interval": interval, "includeAdjustedClose": "true"}
    try:
        data = _get(url, params)
        result = data.get("chart", {}).get("result")
        if not result:
            logger.warning(f"{ticker}: no result in chart response")
            return None
        return result[0]
    except Exception as e:
        logger.warning(f"{ticker}: fetch failed — {e}")
        return None


def fetch_daily_bars(
    ticker: str,
    range: str = "3mo",
) -> List[Dict[str, Any]]:
    """Fetch daily OHLCV bars as list of dicts.

    Args:
        ticker: e.g. "AAPL"
        range: "1mo", "3mo", "1y", "2y"

    Returns:
        List of {timestamp, open, high, low, close, volume} dicts, most recent last.
        Returns empty list on failure.
    """
    data = fetch_chart(ticker, range=range, interval="1d")
    if not data:
        return []

    ts_list = data.get("timestamp", [])
    quote = (data.get("indicators", {}).get("quote") or [{}])[0]
    adjclose = (data.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose", [None] * len(ts_list))

    bars = []
    for i, ts in enumerate(ts_list):
        close = quote.get("close", [None])[i] if isinstance(quote.get("close"), list) else None
        open_ = quote.get("open", [None])[i] if isinstance(quote.get("open"), list) else None
        high = quote.get("high", [None])[i] if isinstance(quote.get("high"), list) else None
        low = quote.get("low", [None])[i] if isinstance(quote.get("low"), list) else None
        volume = quote.get("volume", [None])[i] if isinstance(quote.get("volume"), list) else None
        adj = adjclose[i] if isinstance(adjclose, list) else None

        if close is None:
            continue

        bars.append({
            "timestamp": datetime.utcfromtimestamp(ts),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "adjclose": adj if adj is not None else close,
            "volume": volume,
        })
    return bars


def get_last_price(ticker: str) -> Optional[float]:
    """Get most recent closing price. Fast single-point query."""
    data = fetch_chart(ticker, range="5d", interval="1d")
    if not data:
        return None
    quote = (data.get("indicators", {}) or {}).get("quote") or [{}]
    closes = (quote[0] or {}).get("close") or []
    # Get last non-None close
    for c in reversed(closes):
        if c is not None:
            return float(c)
    return None


def rate_limit_sleep(n_requests: int, per_seconds: float = 10.0):
    """Sleep to respect Yahoo Finance rate limits (~10 req/10s observed)."""
    time.sleep(per_seconds / n_requests)


def get_universe_tickers() -> List[str]:
    """Load all tickers from stock_universe.toml."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

    from pathlib import Path
    path = Path(__file__).resolve().parent.parent / "data" / "stock_universe.toml"
    if not path.exists():
        logger.warning(f"stock_universe.toml not found at {path}")
        return []

    with open(path, "rb") as f:
        config = tomllib.load(f)

    tickers = []
    for section in ["mega_cap", "large_cap", "sector_etfs", "indices"]:
        tickers.extend(config.get(section, {}).get("tickers", []))
    return list(set(tickers))