# SmartFlow — Smart Money Data Pipeline

## What This Is

A Python data pipeline that tracks privileged market participants across 4 markets. The philosophy: insiders, institutions, Congress members, and crypto whales leave public trails — we capture them systematically and eat what they leave behind.

---

## Project Structure

```
C:\Users\user\SmartFlow\
├── smartflow/
│   ├── config.py              # API keys, DB config, poll intervals
│   ├── db/
│   │   ├── models.py          # SQLAlchemy models (7 tables)
│   │   └── engine.py          # DB connection, init_db()
│   ├── collectors/
│   │   ├── base.py            # BaseCollector abstract class
│   │   ├── sec_insider.py     # SEC Form 4 ✅ DONE
│   │   ├── sec_13f.py         # SEC 13F institutional holdings ✅ DONE
│   │   ├── congress.py        # Congress trades via QuiverQuant ✅ DONE
│   │   ├── sec_form144.py     # Form 144 pre-sale notices ✅ DONE
│   │   ├── sec_13d.py         # SC 13D/13G activist filings ✅ DONE
│   │   ├── crypto_coinglass.py # CoinGlass whale positions ✅ DONE
│   │   ├── hkex_director.py   # HKEX director search ✅ BUILT (2026-03-25)
│   ├── hkex_dealings.py   # HKEX director dealings (buy/sell) ✅ BUILT (2026-03-25)
│   ├── hkex_ccass.py      # CCASS custody ✅ DONE
│   ├── hkex_participants.py # CCASS participant list helper ✅
│   ├── hkex_watchlist.py  # CCASS stock watchlist ✅
│   ├── hkex_northbound.py # Stock Connect northbound ✅ BUILT (2026-03-25)
│   ├── hkex_short.py      # SFC short position reports ✅ BUILT (2026-03-25)
│   ├── finra_darkpool.py  # FINRA ATS dark pool ❌ Blocked
│   │   ├── crypto_whale.py     # Whale Alert ❌ TODO (needs API key)
│   │   ├── crypto_arkham.py   # Arkham Intelligence ❌ TODO
│   │   ├── crypto_exchange.py # Glassnode/CoinGlass exchange flows ❌ TODO
│   │   ├── options_tradier.py # Tradier RT options chain ❌ TODO
│   │   └── options_darkpool.py # FINRA + unusual activity ❌ TODO
│   ├── parsers/
│   │   ├── edgar_xml.py       # Form 4 XML parser ✅ DONE
│   │   ├── form144_xml.py     # Form 144 XML parser ✅ DONE
│   │   └── hkex_html.py       # HKEX HTML parser ❌ TODO
│   ├── scheduler.py           # APScheduler orchestrator ✅ DONE
│   ├── alert_bot.py          # Telegram alert bot ✅ BUILT
│   ├── dashboard.py          # Streamlit dashboard ✅ BUILT
│   └── __main__.py            # CLI entrypoint ✅ DONE
├── data/smartflow.db          # SQLite DB (~1085 signals as of 2026-03-24)
├── logs/smartflow.log
├── presentation-engine.py     # McKinsey PPTX generator
├── smartflow-deck.json        # Deck data
├── .env                       # API keys (never commit)
├── .env.example
└── requirements.txt
```

---

## Database Schema

### `smart_money_signals` — Main table, all signals
```sql
id, source, market, signal_type, ticker, entity_name, entity_type,
direction, quantity, price, value_usd, filed_at, traded_at,
raw_data (JSON), created_at, source_id (UNIQUE — dedup key)
```

- `source`: `sec_form4`, `congress`, `sec_form144`, `coinglass_whale`, etc.
- `market`: `US`, `HK`, `CRYPTO`, `OPTIONS`
- `signal_type`: `insider_buy`, `insider_sell`, `congress_buy`, `13f_holding`, `whale_long`, `whale_short`, etc.
- `direction`: `BUY`, `SELL`, `TRANSFER_IN`, `TRANSFER_OUT`, `HOLD`
- `entity_type`: `insider`, `officer`, `director`, `institution`, `congress`, `whale`

### `tracked_entities` — Watchlist
```sql
id, entity_type, name, identifier (CIK/wallet/HKEX code), market, notes, is_active
```

### `collection_runs` — Audit log
```sql
id, collector, started_at, finished_at, records_found, status, error_message
```

### `CCASSwatchlist`, `CCASSHolding`, `CCASSMetric` — HK CCASS data
```sql
-- CCASSwatchlist: stocks to monitor
id, stock_code (UNIQUE), stock_name, board, notes, is_active, added_at

-- CCASSHolding: daily per-participant holdings
id, stock_code, holding_date, participant_id, participant_name,
participant_type, shares_held, pct_of_total, created_at
UNIQUE(stock_code, holding_date, participant_id)

-- CCASSMetric: daily computed concentration metrics
id, stock_code, metric_date, total_ccass_shares, adjusted_float,
participant_count, broker_count, brkt5, brkt5_prev, brkt5_change,
futu_pct, futu_pct_prev, top1_broker_id, top1_broker_name,
top1_broker_pct, concentration_flag, created_at
UNIQUE(stock_code, metric_date)

### `NorthboundFlow` — Stock Connect daily turnover
```sql
id, trade_date (UNIQUE), northbound_hkd, southbound_hkd,
northbound_quota_pct, created_at
```

### `SFCShortData` — Weekly SFC short position data
```sql
id, week_end_date (UNIQUE), raw_data (JSON), created_at
```

---

## CLI

```bash
# Collect
python -m smartflow collect --source sec_form4
python -m smartflow collect --source coinglass_whale
python -m smartflow collect --source congress
python -m smartflow collect --all

# Query
python -m smartflow query --market US --days 7
python -m smartflow query --ticker AAPL
python -m smartflow query --direction BUY --min-value 500000
python -m smartflow query --source coinglass_whale --limit 50

# Schedule (continuous polling)
python -m smartflow schedule --all
python -m smartflow schedule --source sec_form4,congress,coinglass_whale

# Status
python -m smartflow status
```

---

## Collector Pattern

Every collector inherits `BaseCollector` and implements one method:

```python
class MyCollector(BaseCollector):
    name = "my_source"
    market = "US"

    def fetch(self) -> List[Dict[str, Any]]:
        # Return list of signal dicts with these keys:
        # signal_type, ticker, entity_name, entity_type, direction,
        # quantity, price, value_usd, filed_at, traded_at, raw_data, source_id
        return [...]
```

`BaseCollector.run()` handles: DB session, dedup (via `source_id`), `CollectionRun` logging, error handling.

---

## Environment Variables (`.env`)

```
SEC_EDGAR_EMAIL=tommytang.cc@gmail.com    # Required for EDGAR User-Agent
COINGLASS_API_KEY=REDACTED_CREDENTIAL  # CoinGlass (from CryptoStrategy)
WHALE_ALERT_API_KEY=                       # Free tier: 10 req/min (TODO)
ETHERSCAN_API_KEY=                         # Free: 5 req/sec (TODO)
UNUSUAL_WHALES_API_KEY=                    # Optional, paid ~$50/mo
GLASSNODE_API_KEY=                         # Optional, $29/mo
TG_BOT_TOKEN=                             # Telegram bot token (for alerts)
TG_CHAT_ID=                               # Telegram chat ID (for alerts)
```

---

## Poll Intervals (config.py)

| Collector | Interval | Reason |
|-----------|----------|--------|
| sec_form4 | 5 min | EDGAR Atom feed updates frequently |
| sec_form144 | 60 min | Pre-sale notices, event-driven |
| sec_13d | 60 min | Event-driven, but check hourly |
| congress | 60 min | New disclosures come in batches |
| coinglass_whale | 60 sec | Real-time whale positions (Hyperliquid) |
| coinglass_oi | 60 min | Open interest data (hourly) |
| hkex_director | 60 min | T+3 filing delay anyway |
| hkex_dealings | 60 min | Director buy/sell (T+3 delay) |
| hkex_ccass | 24h | T+1 daily data |
| hkex_northbound | 5 min | Real-time during HK market hours |
| sfc_short | 24h | Weekly publication (Fridays) |
| finra_darkpool | 24h | Weekly publication (BLOCKED) |

---

## Known Issues / Gotchas

- **EDGAR `search-index` does NOT index Form 4 XML** — must use Atom feed (`browse-edgar?output=atom`)
- **SEC requires email in User-Agent** — set `SEC_EDGAR_EMAIL` in `.env` or all EDGAR calls will 403
- **CoinGlass API code field** — response code is string "0" not integer 0 for success
- **13F source_id dedup** — uses `cusip + filer_cik + date`; CUSIPs can repeat across issuers, watch for collisions
- **FINRA CDN blocked** — Cloudflare blocks non-residential IPs (Issue #1)
- **ETF Baskets blocked** — iShares/Vanguard URLs returning 404/403 (Issue #2)
- **HKEX dealings URL dead** — `www3.hkexnews.hk/more/news/companynews` returns 404 (site restructured). Rewritten using Playwright with `www1.hkexnews.hk/search/titlesearch.xhtml`. Searches by stock code + date range, parses results table. Tracks director dealings, share buybacks, and director change announcements.

---

## Current State (2026-04-10)

All Phase 1-4 collectors built. Total signals in DB: **1673** (as of 2026-04-10).

| Collector | Status | Signals | Notes |
|-----------|--------|---------|-------|
| SEC Form 4 | ✅ | 43 | ~4/run |
| Congress trades | ✅ | 1173 | |
| SEC Form 144 | ✅ | 102 | |
| SEC 13F | ✅ | 224 | |
| CoinGlass Whale | ✅ | 98 | ~49/run |
| CoinGlass OI | ✅ | 2 | Open interest |
| HKEX CCASS | ✅ | 21 | Concentration signals |
| HKEX Director | ✅ | 0 | T+3 delay |
| HKEX Dealings | ✅ | 9 | Playwright + title search (2026-04-10) |
| HKEX Northbound | ✅ | 0 | Real-time |
| SFC Short Position | ✅ | 0 | Weekly |
| NQ Short Interest | ✅ | 1 | Contrarian composite SI signal |

Dashboard: `streamlit run smartflow/dashboard.py` → localhost:8501
- Dashboard: sources filter now dynamic from DB (previously hardcoded)
- Dashboard: session management fixed (was module-level, now per-call with try/finally)
- Dashboard: Streamlit deprecation warnings fixed (`applymap`→`map`, `use_container_width`→`width`)

## Pending APIs (need keys)

| Source | Signal | API Key Env Var |
|--------|--------|-----------------|
| Whale Alert | whale_transfer | `WHALE_ALERT_API_KEY` |
| Arkham Intelligence | wallet_label | `ARKHAM_API_KEY` |
| Glassnode | exchange flows | $29/mo |
| Telegram alerts | alert bot | `TG_BOT_TOKEN`, `TG_CHAT_ID` |

## Design Decisions

1. **SQLite first** — migrate to PostgreSQL only when needed
2. **Collector pattern** — each source = one file, `fetch()` returns list of dicts
3. **`source_id` dedup** — deterministic unique ID per signal
4. **Unified schema** — all markets → one `smart_money_signals` table
5. **APScheduler in-process** — no Celery, no Redis
6. **Rate limit respect** — EDGAR max 10 req/sec
7. **`raw_data` JSON** — store full source record always

## Export

```bash
# Export all data to CSV
python -c "
import csv
from smartflow.db.engine import get_session, init_db
from smartflow.db.models import SmartMoneySignal
init_db()
session = get_session()
signals = session.query(SmartMoneySignal).all()
with open('smartflow_all_data.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Date','Source','Signal Type','Ticker','Entity','Direction','Value (USD)','Traded At'])
    for s in signals:
        writer.writerow([s.created_at,s.source,s.signal_type,s.ticker,s.entity_name,s.direction,s.value_usd,s.traded_at])
session.close()
"
```
