"""SmartFlow Alert Bot — Telegram notifications for smart money signals.

Monitors DB for:
- Large whale positions (> $5M)
- Cluster insider buys (≥3 insiders same company)
- Large Congress trades (> $100K)
- Large Form 144 pre-sales (> $1M)
"""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from smartflow.db.engine import get_session, init_db
from smartflow.db.models import SmartMoneySignal

load_dotenv()

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "")


def send_message(text: str) -> bool:
    """Send Telegram message. Returns True if sent successfully."""
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print(f"⚠️ Telegram not configured: TG_BOT_TOKEN={bool(TG_BOT_TOKEN)}, TG_CHAT_ID={bool(TG_CHAT_ID)}")
        return False

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML"}

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            return True
        else:
            print(f"⚠️ Telegram error: {resp.text}")
            return False
    except Exception as e:
        print(f"⚠️ Telegram send failed: {e}")
        return False


def check_large_whales(session, threshold_usd: float = 5_000_000) -> list:
    """Find whale positions > threshold."""
    cutoff = datetime.utcnow() - timedelta(hours=6)
    signals = session.query(SmartMoneySignal).filter(
        SmartMoneySignal.source == "coinglass_whale",
        SmartMoneySignal.value_usd >= threshold_usd,
        SmartMoneySignal.created_at >= cutoff,
    ).order_by(SmartMoneySignal.value_usd.desc()).all()
    return signals


def check_insider_clusters(session, min_count: int = 3, days: int = 5) -> dict:
    """Find tickers with ≥N insiders buying in last N days."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    signals = session.query(SmartMoneySignal).filter(
        SmartMoneySignal.source == "sec_form4",
        SmartMoneySignal.direction == "BUY",
        SmartMoneySignal.created_at >= cutoff,
    ).all()

    ticker_counts = {}
    for s in signals:
        ticker = s.ticker or "N/A"
        if ticker not in ticker_counts:
            ticker_counts[ticker] = []
        ticker_counts[ticker].append(s)

    return {k: v for k, v in ticker_counts.items() if len(v) >= min_count}


def check_large_congress(session, threshold_usd: float = 100_000) -> list:
    """Find Congress trades > threshold."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    signals = session.query(SmartMoneySignal).filter(
        SmartMoneySignal.source == "congress",
        SmartMoneySignal.value_usd >= threshold_usd,
        SmartMoneySignal.direction == "BUY",
        SmartMoneySignal.created_at >= cutoff,
    ).order_by(SmartMoneySignal.value_usd.desc()).all()
    return signals


def check_large_form144(session, threshold_usd: float = 1_000_000) -> list:
    """Find Form 144 pre-sales > threshold."""
    cutoff = datetime.utcnow() - timedelta(days=3)
    signals = session.query(SmartMoneySignal).filter(
        SmartMoneySignal.source == "sec_form144",
        SmartMoneySignal.value_usd >= threshold_usd,
        SmartMoneySignal.created_at >= cutoff,
    ).order_by(SmartMoneySignal.value_usd.desc()).all()
    return signals


def format_whale_alert(signal: SmartMoneySignal) -> str:
    emoji = "🟢" if signal.direction == "BUY" else "🔴"
    value = signal.value_usd or 0
    return (
        f"{emoji} <b>WHALE ALERT</b> {emoji}\n"
        f"───────────────────\n"
        f"<b>Asset:</b> {signal.ticker}\n"
        f"<b>Direction:</b> {signal.direction}\n"
        f"<b>Value:</b> ${value:,.0f}\n"
        f"<b>Wallet:</b> <code>{signal.entity_name}</code>\n"
        f"<b>Time:</b> {signal.traded_at.strftime('%Y-%m-%d %H:%M') if signal.traded_at else 'N/A'} UTC"
    )


def format_insider_cluster(ticker: str, signals: list) -> str:
    total_value = sum(s.value_usd or 0 for s in signals)
    names = [s.entity_name[:20] for s in signals[:3]]
    return (
        f"🟢 <b>INSIDER CLUSTER</b> 🟢\n"
        f"───────────────────\n"
        f"<b>Ticker:</b> ${ticker}\n"
        f"<b>Insiders:</b> {len(signals)}\n"
        f"<b>Total Value:</b> ${total_value:,.0f}\n"
        f"<b>Names:</b> {', '.join(names)}"
    )


def format_congress_alert(signal: SmartMoneySignal) -> str:
    return (
        f"🔵 <b>CONGRESS BUY</b> 🔵\n"
        f"───────────────────\n"
        f"<b>Ticker:</b> ${signal.ticker}\n"
        f"<b>Member:</b> {signal.entity_name}\n"
        f"<b>Value:</b> ${signal.value_usd:,.0f}\n"
        f"<b>Time:</b> {signal.traded_at.strftime('%Y-%m-%d') if signal.traded_at else 'N/A'}"
    )


def format_form144_alert(signal: SmartMoneySignal) -> str:
    return (
        f"⚠️ <b>FORM 144 PRE-SALE</b> ⚠️\n"
        f"───────────────────\n"
        f"<b>Seller:</b> {signal.entity_name}\n"
        f"<b>Company:</b> {signal.raw_data.get('issuer_name', 'N/A') if signal.raw_data else 'N/A'}\n"
        f"<b>Proposed:</b> ${signal.value_usd:,.0f}\n"
        f"<b>Date:</b> {signal.traded_at.strftime('%Y-%m-%d') if signal.traded_at else 'N/A'}"
    )


def run_alert_check():
    """Check for alert conditions and send Telegram messages."""
    init_db()
    session = get_session()

    alerts_sent = 0

    whales = check_large_whales(session, threshold_usd=5_000_000)
    for w in whales[:5]:
        msg = format_whale_alert(w)
        if send_message(msg):
            alerts_sent += 1
            print(f"📤 Sent whale alert: {w.ticker} ${w.value_usd:,.0f}")

    clusters = check_insider_clusters(session, min_count=3, days=5)
    for ticker, signals in clusters.items():
        msg = format_insider_cluster(ticker, signals)
        if send_message(msg):
            alerts_sent += 1
            print(f"📤 Sent cluster alert: {ticker} ({len(signals)} insiders)")

    congress = check_large_congress(session, threshold_usd=100_000)
    for c in congress[:5]:
        msg = format_congress_alert(c)
        if send_message(msg):
            alerts_sent += 1
            print(f"📤 Sent congress alert: {c.ticker} ${c.value_usd:,.0f}")

    form144 = check_large_form144(session, threshold_usd=1_000_000)
    for f in form144[:5]:
        msg = format_form144_alert(f)
        if send_message(msg):
            alerts_sent += 1
            print(f"📤 Sent Form144 alert: {f.entity_name} ${f.value_usd:,.0f}")

    session.close()
    return alerts_sent


if __name__ == "__main__":
    print("🔍 SmartFlow Alert Check")
    count = run_alert_check()
    print(f"✅ Done. Sent {count} alerts.")
