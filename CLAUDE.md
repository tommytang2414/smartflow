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
│   │   ├── hkex_director.py   # HKEX director search ✅
│   ├── hkex_dealings.py   # HKEX director dealings (buy/sell) ✅
│   ├── hkex_ccass.py      # CCASS custody ✅ (RED/AMBER/GREEN signals)
│   ├── hkex_participants.py # CCASS participant list helper ✅
│   ├── hkex_watchlist.py  # CCASS stock watchlist ✅
│   ├── hkex_northbound.py # Stock Connect northbound ✅
│   ├── hkex_short.py      # SFC short position reports ✅
│   ├── finra_darkpool.py  # FINRA ATS dark pool ❌ Blocked
│   ├── crypto_whale.py     # Whale Alert ❌ No free tier
│   ├── crypto_arkham.py   # Arkham Intelligence ❌ No free tier
│   │   ├── crypto_exchange.py # Glassnode/CoinGlass exchange flows ❌ TODO
│   │   ├── options_tradier.py # Tradier RT options chain ❌ TODO
│   │   └── options_darkpool.py # FINRA + unusual activity ❌ TODO
│   ├── parsers/
│   │   ├── edgar_xml.py       # Form 4 XML parser ✅ (P=BUY, S=SELL only)
│   │   ├── form144_xml.py     # Form 144 XML parser ✅ (CIK→ticker)
│   │   └── hkex_html.py       # HKEX HTML parser ✅
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
COINGLASS_API_KEY=5e3c70b131744fd5be3ae31878002971  # CoinGlass (from CryptoStrategy)
TG_BOT_TOKEN=                             # Telegram bot token (for alerts)
TG_CHAT_ID=                               # Telegram chat ID (for alerts)
```

Note: Whale Alert has no free tier. Arkham requires credit card. Self-built whale tracker via DEXScreener API (free, no key) — pending VPS test.

---

## Poll Intervals (config.py)

| Collector | Interval | Reason |
|-----------|----------|--------|
| sec_form4 | 5 min | EDGAR Atom feed updates frequently |
| sec_form144 | 60 min | Pre-sale notices, event-driven |
| sec_13d | 60 min | Event-driven, but check hourly |
| sec_13f | 60 min | Quarterly filings |
| congress | 60 min | New disclosures come in batches |
| coinglass_whale | 60 sec | Real-time whale positions (Hyperliquid) |
| coinglass_oi | 60 min | Open interest data (hourly) |
| dex_whale | 5 min | DEX swap feeds (live block number now) |
| whale_alert | 5 min | Whale transfers (0 signals — no free tier) |
| arkham_labels | 60 min | Wallet labels (0 signals — no free tier) |
| hkex_director | 60 min | T+3 filing delay anyway |
| hkex_dealings | 60 min | Director buy/sell (T+3 delay) |
| hkex_ccass | 24h | T+1 daily data |
| hkex_northbound | 5 min | Real-time during HK market hours |
| sfc_short | 24h | Weekly publication (Fridays) |
| nq_si | 24h | NQ short interest composite z-score |
| finra_darkpool | 24h | Weekly publication (BLOCKED) |

---

## Known Issues / Gotchas

- **EDGAR `search-index` does NOT index Form 4 XML** — must use Atom feed (`browse-edgar?output=atom`)
- **SEC requires email in User-Agent** — set `SEC_EDGAR_EMAIL` in `.env` or all EDGAR calls will 403
- **CoinGlass API code field** — response code is string "0" not integer 0 for success
- **SEC company_tickers.json format** — field is `title` (not `name`): `{"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}`
- **13F source_id dedup** — uses `cusip + filer_cik + date`; CUSIPs can repeat across issuers, watch for collisions
- **FINRA CDN blocked** — Cloudflare blocks non-residential IPs
- **ETF Baskets blocked** — iShares/Vanguard URLs returning 404/403
- **HKEX dealings URL dead** — `www3.hkexnews.hk/more/news/companynews` returns 404. Rewritten using Playwright with `www1.hkexnews.hk/search/titlesearch.xhtml`. Autocomplete click does NOT set hidden `#stockId` field — must set via JS after click.
- **Form 4 direction** — only `P` (purchase) = BUY and `S` (sale) = SELL are true market direction. `M`/`G` = TRANSFER. `F`/`W`/`A`/`D` = HOLD (option exercise/grant/acquired/disposed — not cash market transactions)
- **Whale Alert / Arkham** — no free tier. Self-built solution via DEXScreener API pending.

---

## Current State (2026-04-19)

**VPS running** — PID managed via `~/SmartFlow/smartflow.pid`. Restart via `./smartflow_vps.sh`.

### Scheduler Architecture (as of 2026-04-19)

**Circuit breaker** — after 5 consecutive failures, a collector is backed off to 4h interval.
Log message: `CIRCUIT OPEN — N consecutive failures`. To reset: restart the scheduler.

**Hard timeout** — each collector runs in a ThreadPoolExecutor with a per-collector timeout
(see `COLLECTOR_TIMEOUTS` in `config.py`). Hangs count as failures toward circuit breaker.

**S3 upload** — only when `count > 0` new signals. Not on every run.

**Disabled collectors** (`DISABLED_COLLECTORS` in config.py) — skipped entirely at startup:
| Collector | Reason | Since |
|-----------|--------|-------|
| `dex_whale` | The Graph hosted service shut down (DNS → `error.thegraph.com`) | Jun 2024 |
| `hkex_northbound` | `www3.hkexnews.hk/schin/SC/NorthboundTradingData.aspx` → 404 | Apr 2026 |
| `congress` | QuiverQuant API 401 Unauthorized — free tier revoked | Apr 17, 2026 |
| `nq_si` | Hardcoded Windows path `C:/Users/user/nq-short-interest` — not on VPS | Apr 19, 2026 |
| `whale_alert` | No free tier | Always |
| `arkham_labels` | Requires credit card | Always |

To re-enable a collector once fixed: remove from `DISABLED_COLLECTORS` in `config.py`, commit, pull on VPS, restart via `./smartflow_vps.sh`.

### HKEX www3 Status
- `www3.hkexnews.hk/sdw/search/searchsdw.aspx` (CCASS) — **alive** as of Apr 2026
- `www3.hkexnews.hk/schin/SC/` (Stock Connect) — **dead** (404), hence northbound disabled
- `www3.hkexnews.hk/search/titlesearch.xhtml` → migrated to `www1.hkexnews.hk` (done)

### Known Broken (to fix)
- **Congress trades**: QuiverQuant free tier revoked. Options: (1) pay for QuiverQuant, (2) use House Stock Watcher API (free), (3) scrape disclosure.gov directly.
- **DEX whale**: The Graph deprecated. Options: (1) The Graph Network with API key, (2) use a different free Ethereum data source.
- **HKEX Northbound**: Find new URL on HKEX website for Stock Connect turnover data.

## Current State (2026-04-10)

**VPS running** — `python3 -m smartflow schedule --all` (PID 41116) on `18.139.210.59`. DB: `~/SmartFlow/data/smartflow.db` (3.1MB).

Total signals in DB: **~2950** (as of 2026-04-10).

| Collector | Status | Signals | Notes |
|-----------|--------|---------|-------|
| SEC Form 4 (sec_form4) | ✅ | ~97 | P=BUY, S=SELL only; M/G=TRANSFER |
| Congress trades | ✅ | ~1198 | QuiverQuant free tier |
| SEC Form 144 | ✅ | ~196 | CIK→ticker via SEC company_tickers.json |
| SEC 13F | ✅ | ~387 | Name→ticker via SEC company_tickers.json |
| CoinGlass Whale | ✅ | ~265 | |
| CoinGlass OI | ✅ | ~8 | Open interest |
| HKEX CCASS | ✅ | ~31 | RED/AMBER/GREEN concentration flags |
| HKEX Director | ✅ | ~0 | T+3 delay |
| HKEX Dealings | ✅ | ~27 | Playwright + title search |
| HKEX Northbound | ✅ | ~0 | Real-time Stock Connect |
| SFC Short Position | ✅ | ~0 | Weekly |
| NQ Short Interest | ✅ | ~1 | Rolling z-score (20-period window) |
| DEX Whale (dex_whale) | ✅ FIX | 0→pending | Was static block 19M; now live RPC |
| Whale Alert | ❌ | 0 | No free tier |
| Arkham Labels | ❌ | 0 | No free tier |

Dashboard: `streamlit run smartflow/dashboard.py` → localhost:8501

## Pending APIs / Self-Built Solutions

| Source | Status | Solution |
|--------|--------|----------|
| Whale Alert | ❌ No free tier | Self-built: DEXScreener API (free, no key) |
| Arkham Intelligence | ❌ Credit card required | Self-built: DEXScreener API |
| Glassnode | ❌ Paid $29/mo | Not needed — CoinGlass covers crypto |
| Telegram alerts | Optional | Not critical |

**DEXScreener API** — `https://api.dexscreener.com/latest/dex/tokens/{address}/swaps` — tested 200 OK from Windows. Pending: test from VPS, then rewrite `crypto_dex.py`.

## Design Decisions

1. **SQLite first** — migrate to PostgreSQL only when needed
2. **Collector pattern** — each source = one file, `fetch()` returns list of dicts
3. **`source_id` dedup** — deterministic unique ID per signal
4. **Unified schema** — all markets → one `smart_money_signals` table
5. **APScheduler in-process** — no Celery, no Redis
6. **Rate limit respect** — EDGAR max 10 req/sec
7. **`raw_data` JSON** — store full source record always
8. **S3 upload after each run** — scheduler uploads DB to `s3://smartflow-tommy-db/` after every collector run; Lambda always has fresh data

## VPS Operations

```bash
# Restart scheduler (daily cron does this automatically at 06:00 UTC)
ssh ubuntu@18.139.210.59
cd ~/SmartFlow && ./smartflow_vps.sh

# Check if running
cat smartflow.pid && ps aux | grep $(cat smartflow.pid)

# Tail live log (find today's log file)
tail -f logs/smartflow_$(date +%Y%m%d)_*.log

# Check circuit breaker status
grep 'CIRCUIT OPEN\|Recovered\|Failure [0-9]' logs/smartflow.log | tail -20

# Add/remove disabled collector
# Edit smartflow/config.py → DISABLED_COLLECTORS, commit, pull, restart
```

## Changelog

### 2026-04-19 — Circuit Breaker + Dead Collector Cleanup + VPS Restart Fix

**Root cause investigation** — found 6 problems that had accumulated since Apr 10:
1. `smartflow_vps.sh` — no execute permission (cron silently failed for 9 days)
2. `dex_whale` — The Graph hosted service dead, 1440 DNS error lines/day
3. `hkex_northbound` — `www3.hkexnews.hk/schin` 404, 288 errors/day
4. `hkex_ccass` + `hkex_dealings` — hanging silently; `as_completed()` had no timeout;
   APScheduler `max_instances=1` caused starvation (no new signals for 7 days)
5. Congress API — QuiverQuant 401 since Apr 17 (free tier revoked)
6. S3 upload on every run including 0-signal runs (~2880 unnecessary PUTs/day)

**Fixes:**
- `smartflow_vps.sh` rewritten: PID file management, stray process cleanup, startup verification, pre-restart S3 backup
- `config.py`: added `DISABLED_COLLECTORS`, `CIRCUIT_BREAKER_THRESHOLD/BACKOFF`, `COLLECTOR_TIMEOUTS`
- `scheduler.py` rewritten: circuit breaker (5 fails → 4h backoff), hard timeout per collector (ThreadPoolExecutor + `future.result(timeout)`), S3 only on `count > 0`, disabled collector skip
- `hkex_ccass.py`: `as_completed(timeout=800s)` prevents infinite hang
- `hkex_dealings.py`: `page.set_default_timeout(15000)` + explicit timeouts on locator actions
- Commit `491f162`, pushed to GitHub, deployed to VPS, new scheduler PID=380964

### 2026-04-10 — Bug Fixes + VPS + Whale Tracker Rebuild

**6 critical bug fixes:**

1. **crypto_dex.py** — `get_recent_block_number()` returned static `19000000` (Sep 2023). Replaced with live ETH block number via `https://eth.public-rpc.com`. Falls back to static only if RPC fails.

2. **edgar_xml.py (Form 4)** — Transaction code `A` (Acquired) and `D` (Disposed) were being mapped to BUY/SELL. These represent stock option exercises, gifts, etc. — not true market direction. Fixed: only `P`=BUY, `S`=SELL are true direction. `M`/`G`=TRANSFER. `F`/`W`/`A`/`D`=HOLD.

3. **form144_xml.py** — Form 144 ticker was `None` for all signals. Added CIK→ticker lookup via SEC `company_tickers.json` (cached at startup). `issuer_cik` → SEC ticker.

4. **sec_13f.py** — 13F holdings returned company name instead of ticker (e.g. "MICROSOFT CORP" instead of "MSFT"). Major rewrite: added 18K+ entry name→ticker cache using SEC `company_tickers.json`. Normalizes names (strips punctuation, common suffixes: INC/CORP/CO/LTD/LLC/HOLDINGS/GROUP/PARTNERS/LP/GP/etc.). Tested: WALMART IN→WMT ✅, MICROSOFT CORP→MSFT ✅, VISA INC→V ✅.

5. **nq_si.py** — `expanding()` z-score was statistically meaningless (early period had tiny sample size). Changed to `rolling(window=20, min_periods=20)`.

6. **hkex_ccass.py** — Same stock could fire both RED (SELL) and accumulation spike (BUY) simultaneously. Fixed: RED flag now blocks simultaneous accumulation signal. RED takes priority.

**S3 upload in scheduler** — `scheduler.py` now uploads `smartflow.db` to `s3://smartflow-tommy-db/smartflow.db` after each collector run. Lambda always has fresh data.

**VPS state (confirmed via SSH 2026-04-10):**
- Process: `python3 -m smartflow schedule --all` (PID 41116)
- SmartFlow code: `~/SmartFlow/` (git clone from GitHub, not the old no-git directory)
- boto3 installed: `pip install -q boto3`
- DB: `~/SmartFlow/data/smartflow.db` (3.1MB, ~2950 signals)

**Whale tracker self-built** — Whale Alert has no free tier. Arkham requires credit card. Building own whale tracker via DEXScreener API (free, no key, tested 200 OK). Pending: test from VPS, then rewrite `crypto_dex.py`.

### 2026-04-10 — Lambda Daily Report Pipeline LIVE

**AWS Lambda pipeline deployed** — fully automated daily research report:

- Lambda function `smartflow-report` deployed (Python 3.12, 90s timeout)
- S3 bucket `smartflow-tommy-db` for DB storage
- EventBridge rule `smartflow-daily-report` triggers daily at 08:00 HK time
- MiniMax-M2.7 generates Chinese research report from SmartFlow data
- SES sends report to TOMMYTANG2414@GMAIL.COM
- All Lambda code in `lambda/` directory, deployed via zip package

**Fixes along the way:**
- DB_PATH env var stuck on Windows path — fixed via --cli-input-json
- cp950 encoding crash in Lambda runtime — fixed by replacing logging with stdout.buffer binary writes
- MiniMax-Text-01 not supported — changed to MiniMax-M2.7
- SES email not verified — verified both sender/receiver in SES sandbox
- MiniMax API timeout (30s) — increased to 60s, Lambda timeout to 90s

### 2026-04-10 — Phase 2 Complete, VPS Deployment

**HKEX Dealings rewrite** — `www3.hkexnews.hk/more/news/companynews` returned 404. Completely rewritten using Playwright + `www1.hkexnews.hk/search/titlesearch.xhtml`. Key fix: autocomplete click does NOT set hidden `#stockId` field — must set via JS after click. Parses 4-cell results table (Release Time, Stock Code, Stock Short Name, Document). Tracks director dealings (17350 = 0 results → falls back to "Change in Directors" 12350) and director changes.

**VPS deployment** — SmartFlow moved to AWS Lightsail (`18.139.210.59`). Data collection now runs on cloud:
- SmartFlow code at `~/SmartFlow/`
- Cron job: `0 6 * * * ~/SmartFlow/smartflow_vps.sh` (daily 06:00 UTC)
- Log rotation: `0 7 * * * ~/SmartFlow/cleanup_logs.sh` (keep 7 days)
- DB stays on VPS at `~/SmartFlow/data/smartflow.db`
- Stale `hkex_dealings` running status fixed in DB

**SSH key** — correct key for `18.139.210.59`: `C:\Users\user\PycharmProjects\CryptoStrategy\mcp_server\LightsailDefaultKey-ap-southeast-1.pem`, user `ubuntu` (NOT `bitnami` or the `Kronos` path).

**Windows scheduler removed** — `SmartFlow_Scheduler` Windows Task Scheduler task deleted. All collection now on VPS.

**GitHub backup** — repo created at `https://github.com/tommytang2414/smartflow`. Initial commit: Phase 1-2 code (44 files). README.md added. `.env` excluded via `.gitignore`.

**README** — full project documentation written: quick start, CLI reference, collector pattern, DB schema, VPS ops, design decisions.

## Lambda Daily Report Pipeline

Fully automated daily research report generation using AWS Lambda + MiniMax + SES.

### Architecture

```
VPS @ 06:00 HK time
    → Collectors run → smartflow.db updated
    → aws s3 cp smartflow.db s3://smartflow-tommy-db/smartflow.db

AWS Lambda @ 08:00 HK time (EventBridge cron)
    → Download smartflow.db from S3
    → Run queries.py → daily_brief() JSON
    → Build Chinese prompt → MiniMax-M2.7
    → Send report via SES to TOMMYTANG2414@GMAIL.COM
```

### Lambda Function: smartflow-report

| Setting | Value |
|---------|-------|
| Runtime | Python 3.12 |
| Timeout | 90 seconds |
| Memory | 512 MB |
| Handler | lambda_function.handler |
| S3 Bucket | smartflow-tommy-db |
| Key | smartflow.db |
| Model | MiniMax-M2.7 |
| Email | SES → TOMMYTANG2414@GMAIL.COM |

### AWS Resources

| Resource | ARN / ID |
|----------|----------|
| S3 Bucket | smartflow-tommy-db |
| Lambda | smartflow-report (ap-southeast-1:760981412816) |
| IAM Role | smartflow-lambda-role |
| SES From | tommytang.cc@gmail.com |
| SES To | TOMMYTANG2414@GMAIL.COM |
| EventBridge | smartflow-daily-report (cron: 0 0 * * ? * = 08:00 HK) |

### Lambda Env Vars

```
S3_BUCKET=smartflow-tommy-db
DB_PATH=/tmp/smartflow.db
SES_FROM=tommytang.cc@gmail.com
EMAIL_TO=TOMMYTANG2414@GMAIL.COM
MINIMAX_API_KEY=sk-cp-...
PYTHONIOENCODING=utf-8
```

### Deploy Lambda

```bash
# Package
python -c "
import zipfile, os
src = r'C:\Users\user\SmartFlow\lambda'
with zipfile.ZipFile(r'C:\tmp\smartflow_lambda.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    z.write(os.path.join(src, 'lambda_function.py'), 'lambda_function.py')
    z.write(os.path.join(src, 'queries.py'), 'queries.py')
"

# Deploy
aws lambda update-function-code --function-name smartflow-report --zip-file fileb://C:/tmp/smartflow_lambda.zip
```

### Manual Test

```bash
aws lambda invoke --function-name smartflow-report /tmp/result.json
```

### View Logs

```powershell
aws logs get-log-events --log-group-name /aws/lambda/smartflow-report --log-stream-name (Get newest)
```

### MiniMax Model

Model: `MiniMax-M2.7` — only model supported by this API key plan.

### SES Status

Both tommytang.cc@gmail.com and TOMMYTANG2414@GMAIL.COM are verified in SES sandbox.

To send to any email: AWS Console → SES → Account → Request Production Access.

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
