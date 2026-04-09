"""SmartFlow Streamlit Dashboard.

Usage:
    cd C:/Users/user/SmartFlow
    streamlit run smartflow/dashboard.py
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from smartflow.db.engine import get_session, init_db
from smartflow.db.models import SmartMoneySignal

st.set_page_config(page_title="SmartFlow", page_icon="📊", layout="wide")

init_db()

# Dynamically get available sources from DB
def get_available_sources():
    session = get_session()
    try:
        from sqlalchemy import func
        sources = [r[0] for r in session.query(SmartMoneySignal.source).distinct().all()]
        return sorted(sources)
    finally:
        session.close()


def get_signals(source=None, market=None, days=7, min_value=None, direction=None, limit=500):
    session = get_session()
    try:
        query = session.query(SmartMoneySignal)

        if days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.filter(SmartMoneySignal.created_at >= cutoff)
        if source:
            query = query.filter(SmartMoneySignal.source == source)
        if market:
            query = query.filter(SmartMoneySignal.market == market)
        if direction:
            query = query.filter(SmartMoneySignal.direction == direction)
        if min_value:
            query = query.filter(SmartMoneySignal.value_usd >= min_value)

        return query.order_by(SmartMoneySignal.created_at.desc()).limit(limit).all()
    finally:
        session.close()


def signals_to_df(signals):
    if not signals:
        return pd.DataFrame()
    
    rows = []
    for s in signals:
        rows.append({
            "Time": s.created_at.strftime("%Y-%m-%d %H:%M") if s.created_at else "",
            "Source": s.source,
            "Signal": s.signal_type,
            "Ticker": s.ticker or "N/A",
            "Entity": (s.entity_name or "")[:30],
            "Direction": s.direction,
            "Value (USD)": s.value_usd or 0,
            "Traded": s.traded_at.strftime("%Y-%m-%d") if s.traded_at else "N/A",
        })
    return pd.DataFrame(rows)


st.title("📊 SmartFlow — Smart Money Dashboard")

# Sidebar filters
st.sidebar.header("Filters")

sources = ["all"] + get_available_sources()
source_filter = st.sidebar.selectbox("Source", sources)

markets = ["all", "US", "CRYPTO", "HK", "OPTIONS"]
market_filter = st.sidebar.selectbox("Market", markets)

days_filter = st.sidebar.slider("Days", 1, 30, 7)

min_value_filter = st.sidebar.number_input("Min Value (USD)", 0, 10000000, 0, step=100000)

directions = ["all", "BUY", "SELL"]
direction_filter = st.sidebar.selectbox("Direction", directions)

# Apply filters
source = None if source_filter == "all" else source_filter
market = None if market_filter == "all" else market_filter
direction = None if direction_filter == "all" else direction_filter
min_value = min_value_filter if min_value_filter > 0 else None

signals = get_signals(
    source=source,
    market=market,
    days=days_filter,
    min_value=min_value,
    direction=direction,
    limit=500
)

df = signals_to_df(signals)

# Stats
col1, col2, col3, col4 = st.columns(4)

total_signals = len(signals)
buy_count = len([s for s in signals if s.direction == "BUY"])
sell_count = len([s for s in signals if s.direction == "SELL"])
total_value = sum(s.value_usd or 0 for s in signals)

col1.metric("Total Signals", total_signals)
col2.metric("Buy Signals", buy_count)
col3.metric("Sell Signals", sell_count)
col4.metric("Total Value", f"${total_value/1e6:.1f}M" if total_value > 1e6 else f"${total_value/1e3:.1f}K")

# Main table
st.subheader(f"Recent Signals ({total_signals} found)")

if not df.empty:
    # Format the Value column
    df["Value (USD)"] = df["Value (USD)"].apply(lambda x: f"${x:,.0f}" if x else "N/A")
    
    # Color code direction
    def color_direction(val):
        if val == "BUY":
            return "color: green"
        elif val == "SELL":
            return "color: red"
        return ""
    
    st.dataframe(
        df.style.map(color_direction, subset=["Direction"]),
        width='stretch',
        height=500
    )
else:
    st.info("No signals found matching your filters.")

# Source breakdown
st.subheader("By Source")
if not df.empty:
    source_counts = df["Source"].value_counts()
    st.bar_chart(source_counts)

# Top tickers
st.subheader("Top Tickers (by signal count)")
if not df.empty:
    ticker_counts = df[df["Ticker"] != "N/A"]["Ticker"].value_counts().head(10)
    st.bar_chart(ticker_counts)

# Large trades
st.subheader("Large Trades (>$1M)")
large_trades = [s for s in signals if (s.value_usd or 0) > 1_000_000]
if large_trades:
    large_df = signals_to_df(large_trades)
    large_df["Value (USD)"] = large_df["Value (USD)"].apply(lambda x: f"${float(x.replace('$','').replace(',','')):,.0f}" if isinstance(x, str) else f"${x:,.0f}")
    st.dataframe(large_df, width='stretch')
else:
    st.info("No trades over $1M in selected period")
