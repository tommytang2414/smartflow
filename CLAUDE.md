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
│   ├── stock_volume.py    # US stock volume anomaly scanner ✅ (Yahoo Finance)
│   ├── stock_regime.py    # Market regime + 52w high/low scanner ✅
│   ├── stock_momentum.py  # Percentile-ranked momentum ✅
│   │   ├── crypto_exchange.py # Glassnode/CoinGlass exchange flows ❌ TODO
│   │   ├── options_tradier.py # Tradier RT options chain ❌ TODO
│   │   └── options_darkpool.py # FINRA + unusual activity ❌ TODO
│   ├── parsers/
│   │   ├── edgar_xml.py       # Form 4 XML parser ✅ (P=BUY, S=SELL only)
│   │   ├── form144_xml.py     # Form 144 XML parser ✅ (CIK→ticker)
│   │   └── hkex_html.py       # HKEX HTML parser ✅
│   ├── scheduler.py           # APScheduler orchestrator ✅ DONE
│   ├── helpers/
│   │   └── yfinance.py       # Yahoo Finance v8 Chart API helper ✅
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
COINGLASS_API_KEY=replace_me  # Required only when the corrected collector is re-enabled
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

### 2026-07-23 — CCASS Non-Directional Contract and Compliance Gate

- Official semantics confirm CCASS rows are participant holdings after settlement; HKSCC does not recognise the underlying client beneficial interests.
- Removed directional meaning in the new v2 path: holdings use `custody_snapshot`, concentration uses `concentration_measurement`, and every event has `side=None`.
- Added `attributes` JSON to v2 normalized events for participant type, issued-share percentage, transparent concentration inputs, HHI, and explicit interpretation limits.
- Reconciliation reports custody balance changes only. Missing/new participants are not converted into sales/purchases.
- Local audit: 133,955 holdings, 659 metrics, and 352 unsupported SELL signals. Immutable production snapshot: 316,811 holdings, 1,555 metrics, and 850 unsupported directions (849 SELL, 1 BUY).
- HKEX terms prohibit scripted/mechanical access and systematic database creation without permission. The existing ViewState scraper remains disabled; fixtures are synthetic and no live scrape/history copy was performed.
- Full offline verification covers 66 tests; production remains unchanged.

### 2026-07-23 — SFC Bounded History Rebuild and Publication Freshness

- Audited both `data/smartflow.db` and immutable snapshot `snapshots/2026/07/22/pre-rehabilitation-20260722-013106.db`; each has zero `sfc_short_data` rows.
- Bounded official reconstruction to 2026-04-10, the first Git appearance of `hkex_short.py`, instead of downloading unrelated pre-project history.
- Added `ops/reprocess_sfc_history.py`, which requires a new output path and refuses overwrite, plus read-only `ops/audit_sfc_legacy.py`.
- Disposable live rebuild processed 14 official reports and 17,019 events through v2. The identical rerun observed all 17,019 but inserted zero raw reports or normalized events.
- Added optional event-publication freshness to source health. A successful fetch no longer hides an overdue weekly publication: 2026-07-10 is `stale` on 2026-07-23 with `last_event_exceeded_sla`.
- No production database, schema, scheduler, or collector changed.

### 2026-07-23 — SFC Discovery and Weekly Reconciliation

- Added read-only discovery from the official SFC archive index instead of guessed annual URL patterns.
- Rejects non-SFC links and archive-link/CSV reporting-date mismatches; index drift preserves the HTML evidence and remains a parser failure.
- Added week-over-week reconciliation with explicit `newly_reported` and `not_in_current_report` states; absence is never coerced to zero.
- Live disposable rehearsal discovered 10 July 2026 and normalized all 1,233 rows; the later publication-freshness gate correctly classifies that report as stale on 23 July.
- Full two-week reconciliation compared 1,231 versus 1,233 rows: 761 changed, 470 unchanged, and 2 newly reported.
- Production collectors and schema remain unchanged.

### 2026-07-23 — SFC Weekly Short-Position Contract

- Replaced the legacy semantic assumption in the new v2 path: SFC publishes aggregated reportable net short positions, not weekly short-selling turnover or per-stock short percentages.
- Added strict official CSV parsing for report date, stock code/name, aggregate shares, and aggregate HKD value using exact decimal values.
- Normalized one anonymous `position_snapshot` with `side=SHORT` per stock; no `SELL` action or reporting entity is inferred.
- Parser drift and malformed data preserve the raw CSV, record `failure_kind=parser`, and degrade health; the weekly source uses a ten-day freshness SLA.
- Full offline suite now covers 48 tests. Production collectors and schema remain unchanged.

### 2026-07-23 — SEC Live-Feed Failure Taxonomy

- Added Form 4/Form 144 HTTP ingestion wrappers that require a contact-bearing SEC User-Agent.
- Classified missing identity and HTTP 401/403 as `auth`, request/non-2xx failures as `source`, and malformed successful responses as `parser` with raw-body preservation.
- Verified healthy 200 responses continue through v2 normalization, persistence, outcome, and health refresh.
- Full offline suite now covers 42 tests; the adapter remains disconnected from production collectors.

### 2026-07-23 — Multi-Owner Form 4 Attribution

- Corrected the official Pershing Square fixture to all four reporting owners and all four transactions.
- Form 4 parsing now preserves all owners and role flags; normalization stores them in `entities` under one deterministic group entity per filing transaction.
- Avoided multiplying the same transaction across owners, which would overstate shares and value.
- Fixed unreachable date parsing that had left Form 4 normalized `event_at` empty; timestamps now normalize to UTC.
- Bumped Form 4 parser version to `sec-form4-v2`; official fixture agreement remains 100%.

### 2026-07-23 — SQLite Snapshot and Restore Rehearsal

- Added SQLite backup/restore helpers and a CLI verifier for local databases or S3 snapshot objects.
- Restore targets are never overwritten; verification compares schema, row counts, `quick_check`, and SHA-256 bytes.
- Local legacy rehearsal passed for 78,663,680 bytes, 8 tables, and 319,825 rows.
- Dated production snapshot rehearsal passed for 201,900,032 bytes, 8 tables, and 774,475 rows; snapshot and restored SHA-256 values matched.
- S3 remained read-only and generated local temporary files were cleaned automatically.

### 2026-07-23 — Parent-Observed Timeout Outcomes

- Extracted structured outcome and health refresh logic for reuse by ingestion and runtime code.
- Added a v2 process adapter that records timeout evidence from the surviving parent after the child is terminated and joined.
- Verified a 10-second child is terminated at 0.2 seconds and recorded as timeout/degraded; production wiring remains intentionally disabled.

### 2026-07-23 — Official SEC Fixture Agreement Gate

- Expanded official-source coverage with actual Shift4 P-purchase and Coca-Cola S-sale Form 4 filings.
- Added a machine-readable fixture manifest and verifier with a 95% release threshold.
- Verified all four maintained official fixtures at 100% agreement; no production collector was enabled.

### 2026-07-22 — Offline SEC Ingestion Gate

- Wired an offline Form 4/Form 144 ingestion service through raw XML capture, parser, transaction normalizer, atomic persistence, structured run outcome, and source-health refresh.
- Successful reruns retain observed event counts while inserting zero duplicates.
- Malformed XML preserves the raw filing and records `failure_kind=parser`; normalizer contract failures preserve raw evidence and record `failure_kind=schema`.
- Added end-to-end tests for Form 4, Form 144, idempotent reruns, parser failure, schema failure, and health transitions.
- Full offline suite passes 33 tests; legacy-copy migration rehearsal remains repeatable with `quick_check=ok`.
- The service remains disconnected from production collectors; no collector, production schema, or report was enabled.

### 2026-07-22 — Source Health and Freshness Semantics

- Added the v2 `source_health` current-state table with explicit healthy, stale, degraded, unknown, and disabled states.
- Added source-specific cadence/SLA policies and deterministic evaluation from the latest run plus last successful collection timestamp.
- A recent successful empty result is healthy; auth/schema/parser/source/timeout failures remain degraded and cannot masquerade as no events.
- Added idempotent current-health persistence and tests for empty, timeout, stale, disabled, unknown, and state-update behavior.
- Full offline suite passes 29 tests; the repeatable migration rehearsal now verifies four v2 tables without changing 8 legacy tables or 319,825 rows.

### 2026-07-22 — Transaction-Level SEC Evidence Pipeline

- Added atomic, idempotent v2 persistence for one immutable raw filing and all derived normalized events.
- Rejects changed payloads and normalized identities attached to different raw evidence instead of overwriting or silently deduplicating them.
- Added transaction-level Form 4 normalization with distinct action and side; only P/S events receive BUY/SELL sides and every event links to its filing evidence.
- Added Form 144 normalization as `proposed_sale` with `side=SELL` and `execution_status=proposed`, keeping sale intent distinct from execution.
- Preserved exact decimal inputs and normalized SEC timestamps to UTC.
- Expanded the full offline suite to 24 passing tests and repeated the legacy-copy migration rehearsal successfully.
- Kept v2 persistence and normalizers disconnected from production collectors pending individual release gates.

### 2026-07-22 — Enforceable Collector Timeouts

- Replaced the scheduler's `ThreadPoolExecutor` timeout with a cross-platform spawned-process boundary.
- A timed-out collector is now terminated and joined before the scheduler continues, so a hung worker cannot linger behind a false hard-timeout log.
- Preserved circuit-breaker and conditional S3-upload behavior in the parent scheduler process.
- Added tests for child return values, remote failures, and actual wall-clock termination; the full offline suite now passes 17 tests.
- Kept the runtime change undeployed and all collectors disabled pending v2 persistence and source release gates.

### 2026-07-22 — V2 Evidence Schema Foundation

- Added isolated `raw_events`, `normalized_events_v2`, and `collector_runs_v2` models without changing legacy `Base` or `init_db()`.
- Added deterministic source-event IDs, canonical payload hashing, source/raw evidence links, parser versions, quality state, structured failure taxonomy, and fixed-precision numeric fields.
- Added explicit repeatable schema creation and a disposable-copy migration verifier.
- Applied the schema twice to the local 78.7 MB legacy DB backup: 8 legacy tables and 319,825 rows were unchanged, all three v2 tables were present, and `PRAGMA quick_check` returned `ok`.
- Expanded the offline suite to 14 passing tests, including uniqueness, precision, migration repeatability, legacy compatibility, and empty-vs-failure semantics.

### 2026-07-22 — SEC Parser Correctness Foundation

- Added deterministic SEC Form 4 and Form 144 fixtures plus focused `unittest` parser contracts.
- Fixed Form 4 aggregation so non-market codes cannot default to `SELL` or inflate directional notional; mixed P/S filings now remain `MIXED`.
- Preserved acquired/disposed codes and accepted official boolean relationship values such as `true`.
- Fixed the SEC `company_tickers.json` `cik_str` mapping and Form 144 relationship extraction.
- Reclassified Form 144 output as proposed-sale intent with no executed `traded_at`, and changed filing identities to accession-based source IDs.
- Kept all production collectors disabled; this change is a tested Phase 1 foundation, not a production re-enable.

### 2026-07-22 — Lightsail Ingress Audit

- Mapped every public Lightsail rule to the actual shared-host service before proposing closure; no production firewall rule was changed.
- Identified `5001` as the active CCSP Quiz API, `8080` as an unauthenticated Watchtower dashboard, and `8501` as stale with no listener.
- Confirmed UFW is inactive, SSH still permits direct root key login, IMDSv1 is enabled, Tailscale is absent, and the running SSM Agent is not registered as an alternate admin path.
- Corrected the local Lightsail private-key ACL after explicit approval by removing broad inherited access and retaining only the owner, `SYSTEM`, and `Administrators`; CLI SSH verification passed.
- Removed only public `8080` and `8501`, leaving `22` and the active CCSP `5001` rule unchanged; tracked desired and rollback states under `ops/`.
- Verified Watchtower remains healthy on localhost, external Watchtower access is blocked, CCSP still returns its expected unauthenticated 401, and SmartFlow PID plus database counters are unchanged.
- Production deployment commit: `d8e1aed`.

### 2026-07-22 — Lambda Failure Monitoring

- Repaired the existing `smartflow-report-errors` alarm by setting missing data to `notBreaching` while preserving its one-error threshold and SNS actions.
- Set `/aws/lambda/smartflow-report` retention to 30 days.
- Added and confirmed `TOMMYTANG2414@GMAIL.COM` on `smartflow-lambda-alerts`; SNS accepted the labelled test message as `1eba8770-9eb6-5471-b866-e5a95bb1a13b`, and the recipient confirmed delivery.
- Left the enabled daily EventBridge schedule, default retry behaviour, and absent DLQ unchanged for separate review.

### 2026-07-22 — Lambda Least-Privilege IAM

- Replaced `AmazonS3ReadOnlyAccess`, `AmazonSESFullAccess`, and `CloudWatchLogsFullAccess` on `smartflow-lambda-role` with tracked inline policy `SmartFlowLambdaRuntime` from commit `846c6dd`.
- Restricted S3 to the live `smartflow.db`, SES to the exact sender/recipient route, and CloudWatch Logs to `/aws/lambda/smartflow-report`.
- Initial SES verification failed because sandbox authorization also evaluated the recipient identity; rollback reattached all three policies, then the corrected condition-scoped policy was deployed.
- Final containment invoke returned HTTP 200, sent the remediation email, wrote scoped logs, and skipped the DB and MiniMax path. The role now has zero attached managed policies.

### 2026-07-22 — S3 Versioning and Scoped Retention

- Enabled versioning on `smartflow-tommy-db` and replaced the blanket 30-day expiry with the reviewed lifecycle in `ops/s3-lifecycle.json`.
- Retained `snapshots/` indefinitely, kept live DB non-current versions for 30 days, and retained operational backups plus `short-alpha/` objects for 30 days.
- Changed VPS restart backups to `backups/YYYYMMDD/smartflow.db`; deployed commit `d9ba3fb` without restarting scheduler PID `640336`.
- Verified the live lifecycle against the tracked desired state and confirmed the Phase 0 snapshot and current DB remained visible and encrypted.
- Deferred CoinGlass provider revocation because the paid credential belongs to a third party; SmartFlow files and runtimes remain cleared.

### 2026-07-22 — Rehabilitation Programme Approved

- Added `PROJECT_PLAN.md` covering the correctness-first business, functional, technical, security, reporting, and signal-validation roadmap.
- Froze new-source expansion until the programme release gates pass.
- Established that the legacy production database remains immutable and that Phase 0 must disable authoritative `LONG`/`SHORT` reporting or mark it explicitly unverified during remediation.
- Defined a 2026-09-06 decision gate for retaining SmartFlow as directional intelligence or a descriptive research platform.
- Started Phase 0 and recorded the production before-state in `PHASE0_RUNBOOK.md`.
- Preserved and verified the pre-rehabilitation production DB at `s3://smartflow-tommy-db/snapshots/2026/07/22/pre-rehabilitation-20260722-013106.db`; SQLite `PRAGMA quick_check` returned `ok`.
- Added and locally verified Lambda `REPORT_MODE=containment`; it sends a remediation notice without downloading the DB, querying legacy signals, or calling MiniMax.
- Deployed containment mode to the production Lambda from rewritten commit `a26a22f`; manual invocation returned `status=containment`, sent the remediation notice, and confirmed no DB download or MiniMax call. Pre-change Lambda is preserved as version `1`.
- Added the P0-003 collector containment policy: all 19 legacy collectors are disabled until their source-specific release gates pass, with guards in scheduler and manual CLI paths.
- Deployed P0-003 to the VPS from rewritten commit `b8d9841`; all 19 collectors were skipped, one scheduler process remained healthy, and the collection-run high-water mark stayed at `231829` beyond the former 60-second interval.
- Redacted the exposed CoinGlass credential from current tracked documentation and cleared it from local/VPS runtime environments. Provider revocation remains pending authenticated CoinGlass access; do not create a replacement until the v2 collector is release-ready.
- Rewrote all 24 Git commits with `git-filter-repo` after explicit approval and force-pushed with a lease; fresh-clone and VPS all-ref scans found zero credential hits. The VPS-only stash was sanitized and preserved as `refs/archive/sanitized-vps-stash`.

### 2026-05-24 — US Stock Market Flow Enhancement (Phase 1 & 2)

**3 new collectors added:**
- `stock_volume.py` — volume anomaly scanner (volume > 3x 20d avg). Source: Yahoo Finance v8 Chart API.
- `stock_regime.py` — SPY/VIX composite (BULL/NEUTRAL/RISK_OFF) + 52w high/low per stock.
- `stock_momentum.py` — percentile-ranked momentum across 1d/5d/20d/60d timeframes.

**Infrastructure:**
- `helpers/yfinance.py` — shared Yahoo Finance v8 Chart API helper. No key required.
- `data/stock_universe.toml` — ticker universe config (38 stocks/ETFs), editable without code changes.

**Poll intervals:** stock_volume 15min, stock_regime 15min, stock_momentum hourly.

**Deprecation notices added** to crypto_whale.py, crypto_arkham.py, hkex_northbound.py docstrings.

Commit `f6c7a59` after the credential-history rewrite.

- Removed `SmartFlow.lnk` from Windows Startup folder (`AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup`)
- SmartFlow now runs exclusively on VPS (`18.139.210.59`), no local autostart needed

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
- Commit `1ff8169` after the credential-history rewrite; deployed to VPS with scheduler PID=380964

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
