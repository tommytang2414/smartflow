# SmartFlow — Smart Money Data Pipeline

> Tracks privileged market participants across US, HK, and Crypto markets. Insiders, institutions, Congress members, and crypto whales leave public trails — we capture them systematically.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Markets & Signals

| Market | Sources | Signal Types |
|--------|---------|--------------|
| **US** | SEC Form 4, SEC 13F, SEC Form 144, SEC 13D, Congress Trades | Insider buys/sells, institutional holdings, pre-sale notices, activist filings |
| **HK** | HKEX Director Dealings, HKEX CCASS, Stock Connect Northbound, SFC Short | Director buy/sell, custodian concentration (莊家 detection), fund flow |
| **CRYPTO** | CoinGlass Whale Positions, CoinGlass Open Interest | Whale long/short, OI signals |
| **OPTIONS** | NQ Short Interest (FINRA) | Contrarian composite SI signal |

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/tommytang2414/smartflow.git
cd smartflow
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your API keys
```

Required environment variables:

```env
SEC_EDGAR_EMAIL=your-email@example.com   # Required for SEC EDGAR (any email works)
COINGLASS_API_KEY=your_key              # From coinglass.com
```

Optional: `WHALE_ALERT_API_KEY`, `TG_BOT_TOKEN`, `TG_CHAT_ID`

### 3. Run

```bash
# Collect from all sources (one-shot)
python -m smartflow collect --all

# Query signals
python -m smartflow query --market US --days 7
python -m smartflow query --ticker AAPL --limit 20
python -m smartflow query --direction BUY --min-value 500000

# Start continuous scheduler (runs forever)
python -m smartflow schedule --all

# Dashboard
streamlit run smartflow/dashboard.py
# → http://localhost:8501
```

---

## CLI Reference

```bash
# Collect
python -m smartflow collect --source sec_form4           # Single source
python -m smartflow collect --source sec_form4,congress  # Multiple
python -m smartflow collect --all                       # All collectors

# Query
python -m smartflow query --market US --days 7           # Last 7 days, US market
python -m smartflow query --ticker AAPL                   # By ticker
python -m smartflow query --direction BUY --min-value 100000  # Large buys
python -m smartflow query --source congress --limit 50    # From Congress only

# CCASS (HK stock concentration / 莊家 detection)
python -m smartflow ccass --stock 00700                  # Per stock
python -m smartflow ccass --flag RED                      # High concentration alerts

# Watchlist
python -m smartflow watchlist list
python -m smartflow watchlist add --code 00700 --name "Tencent"
python -m smartflow watchlist seed                        # Seed with HK heavyweights

# Status
python -m smartflow status                               # Collection run history
```

---

## Architecture

### Collector Pattern

Every data source is a single file in `smartflow/collectors/`, inheriting from `BaseCollector`:

```python
from smartflow.collectors.base import BaseCollector

class MyCollector(BaseCollector):
    name = "my_source"   # Used as source_id prefix
    market = "US"

    def fetch(self) -> List[Dict]:
        # Fetch from API / scrape
        return [{
            "signal_type": "insider_buy",
            "ticker": "AAPL",
            "entity_name": "Tim Cook",
            "entity_type": "insider",
            "direction": "BUY",
            "quantity": 50000,
            "price": 178.50,
            "value_usd": 8_925_000,
            "filed_at": datetime(2026, 4, 8),
            "traded_at": datetime(2026, 4, 7),
            "raw_data": { ... },    # Full source record
            "source_id": "my_source_aapl_tcook_20260408",  # Unique dedup key
        }]
```

`BaseCollector.run()` handles: DB session, deduplication via `source_id`, `CollectionRun` audit logging, error handling.

### Database

SQLite at `data/smartflow.db`. 7 tables:

| Table | Purpose |
|-------|---------|
| `smart_money_signals` | All signals — unified schema across markets |
| `tracked_entities` | Watchlist of entities to monitor |
| `collection_runs` | Audit log of every collection run |
| `ccass_watchlist` | HK stocks to monitor via CCASS |
| `ccass_holdings` | Daily per-participant CCASS holdings |
| `ccass_metrics` | Daily computed concentration metrics |
| `northbound_flow` | Stock Connect northbound/southbound turnover |
| `sfc_short_data` | Weekly SFC short position data |

---

## Collectors

| Collector | Market | Interval | Notes |
|-----------|--------|----------|-------|
| `sec_form4` | US | 5 min | EDGAR Atom feed — insider buys/sells |
| `sec_13f` | US | daily | Institutional holdings (quarterly) |
| `sec_form144` | US | 60 min | Pre-sale notices |
| `sec_13d` | US | 60 min | Activist filings (13D/13G) |
| `congress` | US | 60 min | QuiverQuant — Congress trades |
| `coinglass_whale` | CRYPTO | 60 sec | CoinGlass whale positions (Hyperliquid) |
| `coinglass_oi` | CRYPTO | 60 min | CoinGlass open interest |
| `hkex_dealings` | HK | 60 min | Director buy/sell via HKEX title search |
| `hkex_ccass` | HK | 24h | Custodian concentration metrics |
| `hkex_northbound` | HK | 5 min | Stock Connect northbound turnover |
| `sfc_short` | HK | 24h | SFC weekly short position reports |
| `nq_si` | OPTIONS | 24h | NQ contrarian SI signal (bi-monthly FINRA) |

---

## VPS Deployment

SmartFlow runs on a VPS (AWS Lightsail) with daily cron collection:

```bash
# SSH to VPS
ssh -i LightsailDefaultKey-ap-southeast-1.pem ubuntu@18.139.210.59

# Manual run
cd ~/SmartFlow && python3 -m smartflow collect --all

# View logs
tail -f ~/SmartFlow/logs/smartflow.log

# Check cron
crontab -l
# 0 6 * * * ~/SmartFlow/smartflow_vps.sh >> ~/SmartFlow/logs/cron.log 2>&1
```

Crontab runs at **06:00 UTC daily**. Log rotation cleans logs older than 7 days (07:00 UTC daily).

---

## Directory Structure

```
smartflow/
├── collectors/          # One file per data source
│   ├── base.py         # BaseCollector abstract class
│   ├── sec_insider.py  # SEC Form 4
│   ├── congress.py     # Congress trades
│   └── ...
├── db/
│   ├── models.py       # SQLAlchemy models
│   └── engine.py       # DB connection
├── parsers/            # HTML/XML parsers
├── scheduler.py         # APScheduler orchestrator
├── dashboard.py         # Streamlit dashboard
├── config.py           # API keys, poll intervals
└── __main__.py         # CLI entrypoint
data/
├── smartflow.db         # SQLite DB
└── ccass_participants.json
.env                     # API keys (not committed)
.env.example             # Template
```

---

## Design Decisions

1. **SQLite first** — zero infrastructure, portable, sufficient for <1M rows
2. **Collector pattern** — one file per source, `fetch()` returns signal dicts
3. **`source_id` dedup** — every signal has a deterministic unique ID; duplicates are skipped silently
4. **Unified schema** — all markets share one `smart_money_signals` table
5. **APScheduler in-process** — no Redis, no Celery
6. **`raw_data` JSON** — always store the full source record for auditability
7. **SEC EDGAR requires email** — set `SEC_EDGAR_EMAIL` or all EDGAR requests 403
8. **HKEX is fully JavaScript** — requires Playwright; servlet API always returns 0 records

---

## Known Issues

- **FINRA darkpool** — Cloudflare blocks non-residential IPs
- **ETF Baskets** — iShares/Vanguard URLs returning 403
- **HKEX Director (t2code 17350)** — returns 0 results; category "Change in Directors" (12350) used instead
- **SEC Form 4 XML** — not indexed in `search-index`; must use Atom feed

---

## License

MIT — Tommytang
