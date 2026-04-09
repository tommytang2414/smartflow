"""
SmartFlow Analyst — Database Query Module
Queries smartflow.db and returns structured JSON for analyst consumption.
"""

import os
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Any

LOCAL_DB = r"C:\Users\user\SmartFlow\data\smartflow.db"


def _connect(db_path: str = None) -> sqlite3.Connection:
    # Lambda sets DB_PATH env var; local Windows uses hardcoded path
    path = db_path or os.environ.get("DB_PATH", LOCAL_DB)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def get_summary() -> dict[str, Any]:
    """High-level overview of all data sources."""
    conn = _connect()
    cur = conn.cursor()
    tables = [
        "smart_money_signals",
        "tracked_entities",
        "collection_runs",
        "ccass_watchlist",
        "ccass_holdings",
        "ccass_metrics",
        "northbound_flow",
        "sfc_short_data",
    ]
    result = {}
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        cnt = cur.fetchone()[0]
        cur.execute(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 1")
        row = cur.fetchone()
        last = dict(row) if row else None
        result[t] = {"count": cnt, "last_record": last}
    conn.close()
    return result


def get_congress_signals(days: int = 30) -> dict[str, Any]:
    """Congress trading: buy/sell ratio, top picks, top sells."""
    conn = _connect()
    cur = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    # Overall ratio
    cur.execute(
        """
        SELECT direction, COUNT(*) as cnt
        FROM smart_money_signals
        WHERE signal_type IN ('congress_buy', 'congress_sell')
          AND filed_at >= ?
        GROUP BY direction
        """,
        (cutoff,),
    )
    rows = cur.fetchall()
    total_buy = total_sell = 0
    for r in rows:
        if r["direction"] == "BUY":
            total_buy = r["cnt"]
        elif r["direction"] == "SELL":
            total_sell = r["cnt"]
    ratio = round(total_buy / total_sell, 2) if total_sell > 0 else None

    # Top buys
    cur.execute(
        """
        SELECT ticker, COUNT(*) as cnt, COUNT(DISTINCT entity_name) as who
        FROM smart_money_signals
        WHERE signal_type = 'congress_buy' AND filed_at >= ?
        GROUP BY ticker ORDER BY cnt DESC LIMIT 10
        """,
        (cutoff,),
    )
    top_buys = [dict(r) for r in cur.fetchall()]

    # Top sells
    cur.execute(
        """
        SELECT ticker, COUNT(*) as cnt, COUNT(DISTINCT entity_name) as who
        FROM smart_money_signals
        WHERE signal_type = 'congress_sell' AND filed_at >= ?
        GROUP BY ticker ORDER BY cnt DESC LIMIT 10
        """,
        (cutoff,),
    )
    top_sells = [dict(r) for r in cur.fetchall()]

    # Notable sold with multiple sellers (HAVING not WHERE — cnt is aggregate alias)
    cur.execute(
        """
        SELECT ticker, direction, COUNT(*) as cnt, COUNT(DISTINCT entity_name) as who
        FROM smart_money_signals
        WHERE signal_type = 'congress_sell'
          AND filed_at >= ?
        GROUP BY ticker, direction
        HAVING COUNT(*) >= 3
        ORDER BY cnt DESC
        """,
        (cutoff,),
    )
    heavy_sells = [dict(r) for r in cur.fetchall()]

    conn.close()
    return {
        "days": days,
        "total_buy": total_buy,
        "total_sell": total_sell,
        "buy_sell_ratio": ratio,
        "interpretation": (
            "BULLISH" if ratio and ratio > 1.2
            else "BEARISH" if ratio and ratio < 0.8
            else "NEUTRAL"
        ),
        "top_buys": top_buys,
        "top_sells": top_sells,
        "heavy_sells": heavy_sells,
    }


def get_insider_signals(days: int = 30) -> dict[str, Any]:
    """Insider buys — officers and insiders buying their own stock."""
    conn = _connect()
    cur = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    cur.execute(
        """
        SELECT ticker, entity_name, entity_type, quantity, price,
               filed_at, direction, signal_type
        FROM smart_money_signals
        WHERE signal_type IN ('insider_buy', 'insider_sell')
          AND filed_at >= ?
        ORDER BY filed_at DESC
        """,
        (cutoff,),
    )
    rows = [dict(r) for r in cur.fetchall()]

    # Group by ticker
    by_ticker = {}
    for r in rows:
        t = r["ticker"] or "N/A"
        if t not in by_ticker:
            by_ticker[t] = []
        by_ticker[t].append(r)

    conn.close()
    return {
        "days": days,
        "signals": rows,
        "by_ticker": by_ticker,
        "total_signals": len(rows),
    }


def get_whale_signals(days: int = 30) -> dict[str, Any]:
    """Crypto whale positions — BTC, ETH, SOL large moves."""
    conn = _connect()
    cur = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    cur.execute(
        """
        SELECT ticker, direction, quantity, price, filed_at, value_usd
        FROM smart_money_signals
        WHERE signal_type IN ('whale_long', 'whale_short')
          AND filed_at >= ?
        ORDER BY filed_at DESC
        """,
        (cutoff,),
    )
    rows = [dict(r) for r in cur.fetchall()]

    # Aggregate by ticker
    by_ticker = {}
    for r in rows:
        t = r["ticker"]
        if t not in by_ticker:
            by_ticker[t] = {"ticker": t, "total_qty": 0, "avg_price": 0, "signals": 0, "buy_signals": 0}
        qty = r["quantity"] or 0
        price = r["price"] or 0
        if r["direction"] == "BUY":
            by_ticker[t]["total_qty"] += qty
            by_ticker[t]["avg_price"] = (
                (by_ticker[t]["avg_price"] * by_ticker[t]["buy_signals"] + price)
                / (by_ticker[t]["buy_signals"] + 1)
            )
            by_ticker[t]["buy_signals"] += 1
        by_ticker[t]["signals"] += 1

    conn.close()
    return {
        "days": days,
        "raw_signals": rows,
        "by_ticker": list(by_ticker.values()),
        "total_signals": len(rows),
    }


def get_hk_director_signals(days: int = 14) -> dict[str, Any]:
    """HK listed company director dealings — buy/sell/transfer."""
    conn = _connect()
    cur = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    cur.execute(
        """
        SELECT ticker, entity_name, direction, signal_type,
               filed_at, traded_at, raw_data
        FROM smart_money_signals
        WHERE market = 'HK'
          AND filed_at >= ?
        ORDER BY filed_at DESC
        """,
        (cutoff,),
    )
    rows = [dict(r) for r in cur.fetchall()]

    # Extract headline from raw_data JSON
    for r in rows:
        try:
            raw = json.loads(r["raw_data"]) if r["raw_data"] else {}
            r["headline"] = (raw.get("headline") or "")[:100]
        except Exception:
            r["headline"] = ""

    # Summary by ticker
    by_ticker = {}
    for r in rows:
        t = r["ticker"]
        if t not in by_ticker:
            by_ticker[t] = {"ticker": t, "signals": [], "buy": 0, "sell": 0, "transfer": 0}
        by_ticker[t]["signals"].append(r)
        d = r["direction"].upper()
        if "BUY" in d:
            by_ticker[t]["buy"] += 1
        elif "SELL" in d:
            by_ticker[t]["sell"] += 1
        else:
            by_ticker[t]["transfer"] += 1

    conn.close()
    return {
        "days": days,
        "raw_signals": rows,
        "by_ticker": {k: v for k, v in sorted(by_ticker.items(), key=lambda x: -len(x[1]["signals"]))},
        "total_signals": len(rows),
    }


def get_ccass_flags() -> dict[str, Any]:
    """CCASS concentration flags — RED / AMBER / GREEN stocks."""
    conn = _connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT stock_code, metric_date,
               brkt5, brkt5_change,
               futu_pct, futu_pct_prev,
               top1_broker_name, top1_broker_pct,
               concentration_flag,
               total_ccass_shares, participant_count,
               broker_count
        FROM ccass_metrics
        WHERE metric_date = (SELECT MAX(metric_date) FROM ccass_metrics)
        ORDER BY
            CASE concentration_flag
                WHEN 'RED' THEN 1
                WHEN 'AMBER' THEN 2
                WHEN 'GREEN' THEN 3
            END,
            top1_broker_pct DESC
        """
    )
    rows = [dict(r) for r in cur.fetchall()]

    summary = {"RED": [], "AMBER": [], "GREEN": []}
    for r in rows:
        flag = r["concentration_flag"]
        if flag in summary:
            summary[flag].append(r)

    conn.close()
    return {
        "as_of_date": rows[0]["metric_date"] if rows else None,
        "flags": summary,
        "total_stocks": len(rows),
    }


def get_collection_status() -> dict[str, Any]:
    """Latest collection run status for each data source."""
    conn = _connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT collector, MAX(started_at) as last_run, status, records_found
        FROM collection_runs
        GROUP BY collector
        ORDER BY last_run DESC
        """
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"runs": rows}


def daily_brief() -> dict[str, Any]:
    """Composite daily brief combining all signals."""
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "summary": get_summary(),
        "congress": get_congress_signals(30),
        "insider": get_insider_signals(30),
        "whale": get_whale_signals(30),
        "hk_directors": get_hk_director_signals(14),
        "ccass": get_ccass_flags(),
        "collection": get_collection_status(),
    }


if __name__ == "__main__":
    brief = daily_brief()
    print(json.dumps(brief, indent=2, default=str))
