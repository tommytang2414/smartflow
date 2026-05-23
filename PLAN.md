# SmartFlow — US Stock Scanning Master Plan
## Planned: 7 New Collectors across 3 Batches

---

## Signal Schema (Unified)

Every new collector outputs into `smart_money_signals` with:

```
source           = <collector_name>
market           = "US"
signal_type      = <defined per collector>
ticker           = <equity ticker, uppercase>
entity_name      = <source-specific entity>
entity_type      = "institution" | "market_maker" | "news" | "index" | "sector"
direction       = "BUY" | "SELL" | "HOLD" | "INFO"
quantity        = <integer or None>
price           = <float or None>
value_usd       = <estimated float or None>
filed_at        = <date string "YYYY-MM-DD">
traded_at       = <date string "YYYY-MM-DD">
raw_data        = <full JSON response>
source_id       = <deterministic unique id>
```

---

## BATCH 1 — Quick Wins (Data freely available, easy to implement)

### B1.1: Unusual Options Activity (Yahoo Finance scrape)

**Source:** Yahoo Finance options chain — no API key needed.
**Endpoint:** `https://query1.finance.yahoo.com/v7/finance/options/{TICKER}`
**What to grab:**
- For a universe of ~50 liquid stocks (SPY-track, top volume), pull option volume vs. open interest
- Volume > 5x average OI = unusual
- Detect directional skew: call volume / put volume ratio

**Signal schema:**
```
signal_type = "options_unusual_call" | "options_unusual_put" | "options_sweep_call" | "options_sweep_put"
entity_name = "<TICKER>"
entity_type = "market_maker"
direction = "BUY" (calls=bullish) | "SELL" (puts=bearish)
value_usd = estimated_notional = volume * option_price * 100 (contract multiplier)
```

**Difficulty:** Low-Medium. Need to pick a universe (top 50 by market cap or volume). Yahoo Finance blocks server-side by User-Agent — use a realistic UA.

**Poll interval:** 15 min during market hours, 1h after hours.

**Universe:** Build a pre-defined list (~100 tickers: mega-cap, tech, financial). No dynamic discovery needed for v1.

**source_id:** `yahoo_opts_{ticker}_{date}_{direction}`

**Implementation notes:**
- Yahoo Finance options API returns: `{optionChain: {result: [{options: [{calls: [], puts: []}]}]}}`
- Fields: `volume`, `openInterest`, `lastPrice`, `strike`, `expiration`
- Sweep = block trade (>500 contracts in a single print, unusual volume)
- Only during market hours (09:30-16:00 ET) — skip outside to save rate

---

### B1.2: Short Interest — ShortSqueeze.com scrape

**Source:** `https://shortsqueeze.com/?symbol={TICKER}&wakeup=1` or their API if available.
**Fallback:** `https://www.shortsqueeze.com/shortsqueeze.php?Symbol={TICKER}&table=institutional_ownership`
**Better source:** `https://finra.org/Regulation/ShortSelling/ConsolidatedLimitOrderBreaks` — FINRA weekly published CSV

**Simplest approach (FINRA CSV):**
- FINRA publishes weekly `cbss_weekly.csv` with all short positions
- Download: `https://www.finra.org/sites/default/files/2022-08/shortsellsample.csv` (sample)
- Full file: `https://www.finra.org/sites/default/files/2022-08/shortsalldata.csv` — but needs auth
- Alternative: scrape ShortSqueeze.com for top short-interest stocks
  - `https://shortsqueeze.com/?symbol=spy&wakeup=1` returns table with short_float, cost_to_borrow, days_to_cover

**Signal schema:**
```
signal_type = "short_squeeze_candidate" | "short_cover_detected"
entity_name = "<TICKER>"
entity_type = "market_maker"
direction = "SELL" (high short = bearish pressure, squeeze candidate)
direction = "BUY"  (short_cover = price recovery signal)
value_usd = short_interest_dollars (shares * price)
```

**Key metrics from ShortSqueeze:**
- `shortFloat` (% of float sold short)
- `costToBorrow` (CTB basis points)
- `daysToCover` (how long to buy back at avg daily volume)
- `shortableShares` / `availableShares`

**Difficulty:** Low. One-page scrape per ticker OR a bulk list page.

**Poll interval:** Daily (S+D data updates weekly, but CTB changes more frequently).

**Implementation notes:**
- Focus on high-CTB stocks (>50% = expensive to borrow = likely short squeeze candidate)
- Build a screener table: top 20 by `shortFloat * costToBorrow`
- Use `requests-html` or plain `requests` + BeautifulSoup (ShortSqueeze blocks bots, may need rotation)

**source_id:** `shortsqueeze_{ticker}_{date}`

---

### B1.3: SEC EDGAR Full-Text Search (keyword alerts)

**Source:** SEC EDGAR full-text search API.
**Endpoint:** `https://efts.sec.gov/LATEST/search-index?q={keyword}&dateRange=custom&startdt={start}&enddt={end}&forms=10-K,10-Q,8-K`
**Better:** EDGAR search UI API: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=8-K&dateb=&owner=include&count=40`

**What to detect:**
- `"buyback"` / `"repurchase"` → company is buying its own stock (bullish signal)
- `"going concern"` → auditor warning (bearish)
- `"delisting"` / `"nasdaq"` → compliance warning
- `"material adverse"` / `"MAC"` → deal risk
- `"activist"` / `"investor"` in 13D filings
- `"insider"` purchase in 8-K (Form 4 embedded in 8-K)

**8-K is most valuable:**
- 8-K filed for: earnings results, material agreements, changes in officers, bankruptcies, financial distress
- Many 8-K filings have NO numeric data — just text events
- EDGAR has an 8-K "disclosure events" taxonomy

**Signal schema:**
```
signal_type = "buyback_announced" | "going_concern" | "delisting_warning" | "earnings_beat" | "activist_13d"
entity_name = "<CIK or company name>"
entity_type = "institution" (corp action) or "institution" (activist)
direction = "BUY" | "SELL" | "INFO" | "HOLD"
```

**Difficulty:** Medium. Need to parse EDGAR text. Keyword matching is simple but effective.

**Poll interval:** Every 30 min (8-K filings come in batches).

**Implementation notes:**
- Start with a curated keyword list (5-10 keywords)
- Use EDGAR's RSS feed for 8-K: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&company=&dateb=&owner=include&count=40&action=getcompany`
- RSS is easier to parse than full-text search
- Map CIK → ticker using SEC `company_tickers.json` (already used in existing code)

**source_id:** `edgar_kw_{keyword}_{cik}_{date}`

---

## BATCH 2 — Sentiment + News

### B2.1: Finviz News Scanner + Stock Screener

**Source:** Finviz news feed + screener API.
**Endpoints:**
- News: `https://finviz.com/news/news.aspx` (RSS-style)
- Screener: `https://finviz.com/screener.ashx?v=152&f=ind_stocksonly,sh_curvol_o500,sh_price_o20&o=ticker&r=1` (no API key needed for basic screener, but Finviz blocks scrapers)

**What to grab:**
- News per ticker: `https://finviz.com/quote.ashx?t={TICKER}&o=date`
- Aggregate news sentiment: if multiple news about same ticker in 24h → signal
- Screener filters: stocks with unusual news volume, gap up/down, news catalyst

**Better source for news:** NewsAPI.org free tier (25 req/day) for financial news:
- `https://newsapi.org/v2/everything?q={TICKER}&sortBy=publishedAt&apiKey=KEY`
- Sources: `bloomberg, reuters, cnbc, marketwatch, seekingalpha`
- Free tier: 25 requests/day, results only 1 day old max

**Alternative: Alpha Vantage News Sentiment API**
- `https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={TICKER}&apikey=KEY`
- Free tier: 25 req/day, requires key

**Signal schema:**
```
signal_type = "news_bullish" | "news_bearish" | "news_neutral"
entity_name = "<TICKER>"
entity_type = "news"
direction = "BUY" | "SELL" | "INFO"
value_usd = None
```

**Difficulty:** Medium. Need news aggregation. Simple keyword sentiment scoring.

**Poll interval:** 30 min.

**Implementation notes:**
- Use keyword-based sentiment: `"beat"`, `"raise"`, `"upgrade"`, `"buy"`, `"strong"` → bullish
- `"miss"`, `"cut"`, `"downgrade"`, `"weak"`, `"loss"` → bearish
- Source attribution: Reuters/Bloomberg/CNBC weighted higher than unknown sources
- Keep a 24h rolling news cache per ticker to avoid duplicate signals

**source_id:** `news_sent_{ticker}_{date}`

---

### B2.2: FinFed / Fintel / Whale Wisdom Institutional Ownership Tracker

**Source:** Whale Wisdom (whalewisdom.com) — SEC 13F filing data with a human-readable API
**Free:** Yes, basic scraping possible. WhaleWisdom shows institutional ownership %.
**Better:** Fintel (fintel.io) — has both short interest AND institutional ownership.
**Endpoint:** `https://fintel.io/s/{TICKER}/ownership` (requires JS)
**Scrapable:** `https://whalewisdom.com/holder/{CIK}` — shows top holders, ownership %

**Alternative: Open Insider (openinsider.com)**
- Scrapable summary table: latest insider buys/sells
- Free, no API key
- `http://www.openinsider.com/latest-acquisitions` — latest acquisitions/acquisitions

**Signal schema:**
```
signal_type = "institution_adding" | "institution_reducing" | "top10_holding_change"
entity_name = "<INSTITUTION NAME>"
entity_type = "institution"
direction = "BUY" (adding) | "SELL" (reducing)
ticker = "<STOCK TICKER>"
value_usd = shares_changed * price
```

**Difficulty:** Medium. Institutional ownership changes are quarter-lagged (13F delay = 45 days). Not great for real-time.

**Better use:** Focus on **top holders appearing in new 13F filings** (quarterly update).
- New 13F filers = institutions that just started disclosing (first-time filers)
- This is WhaleWisdom's "Newly Listed" tab — actionable because first filing is new position
- Or: institutions that INCREASED position by >20% QoQ in a major holding

**Poll interval:** Daily (institutions file 13F within 45 days, but new filers come in more frequently).

**source_id:** `whalewisdom_new_{cik}_{date}`

---

### B2.3: Benzinga / MarketWatch Intraday News Scan

**Source:** Benzinga API (`https://api.benzinga.com/api/v2/`) — requires paid key.
**Free alternative:** Benzinga RSS: `https://www.benzinga.com/feed/tag/markets`
**Better:** MarketWatch RSS: `https://feeds.marketwatch.com/marketwatch/topstories/` + per-ticker
**Alternative:** Seeking Alpha: `https://seekingalpha.com/analysis/{TICKER}/overview` — blocks scraping

**Signal schema:** Same as B2.1 news sentiment.

**Difficulty:** Medium.

---

## BATCH 3 — Advanced / Data-Heavy

### B3.1: Dark Pool / OTC Volume (FINRA Alternative Trading System data)

**Source:** FINRA publishes ATS (Alternative Trading System) data weekly.
**URL:** `https://www.finra.org/regulation/transparency/alternative-trading-systems/data-resources`
**File:** Weekly published as XLSX/CSV — `ats_{date}.csv`
**What it shows:**
- Dark pool volume as % of total volume
- Per-venue (Goldman Sachs Sigma X, Citadel, etc.)
- "Print" (execute) vs "Quote" activity

**Signal schema:**
```
signal_type = "darkpool_surge" | "darkpool_rotation"
entity_name = "<DARK POOL NAME>"
entity_type = "market_maker"
direction = "INFO" (dark pool activity = hidden order flow = signal for price action)
value_usd = total_volume_dark_pool_usd
```

**Difficulty:** Medium-High. Weekly data, slightly stale. Requires parsing XLSX.

**Poll interval:** Weekly (Friday after market close).

---

### B3.2: Options Market Making / Gamma Exposure (GEX) Estimator

**Source:** Self-built from Yahoo Finance options chain (already have in B1.1).
**What is GEX (Gamma Exposure)?**
- Measures $gamma of options market makers at each strike price
- Positive GEX = dealers hedging causes price to move in direction of move
- Negative GEX = dealers fighting the price move
- Key formula: GEX = Sum(gamma_i * S * w_i) where w = 0.5 for ATM, decreasing for OTM

**How to calculate:**
- Pull full options chain (all strikes, all expirations) for SPY and major tickers
- Calculate gamma for each contract: `gamma = (N(d1) / (S * sigma * sqrt(T)))`
- Sum by strike — above and below current price
- Net GEX = net gamma exposure of dealers

**Signal schema:**
```
signal_type = "gamma_squeeze_positive" | "gamma_squeeze_negative" | "gamma_pin_risk"
entity_name = "<TICKER>"
entity_type = "market_maker"
direction = "BUY" | "SELL" | "HOLD"
value_usd = total_notional_gamma
```

**Difficulty:** High. Requires options math, full chain data, and is ticker-specific.
- Requires per-ticker options chain with all strikes (Yahoo covers this)
- Gamma calculation: `gamma = lambda * N'(d1) / (S * sigma * sqrt(T))`
- Need historical vol (20-day realized) per ticker
- This is compute-heavy — do for top 20 tickers only

**Poll interval:** 5 min during market hours.

---

### B3.3: Composite US Smart Money Score (Portfolio Signal Aggregator)

**NOT a collector — a signal generator that runs on existing data.**

After implementing all Batch 1-2 collectors, run a nightly composite query:

```
FOR each ticker in recent_signals:
  score = 0
  +2 insider_buy (Form 4)
  -2 insider_sell (Form 4)
  +3 congress_buy
  -3 congress_sell
  +1 institution_new_13f
  +2 whale_long (crypto-adjacent equities from CoinGlass)
  +1 unusual_options_call
  -1 unusual_options_put
  +2 high_short_float (squeeze candidate)
  +1 earnings_beat (news)
  -2 going_concern (news)

  IF score >= 4 → BUY signal, score <= -4 → SELL signal
```

**Output:** New table `composite_signals` or just a special signal type.
```
signal_type = "composite_buy" | "composite_sell"
entity_name = "<TICKER>"
source = "composite_score"
value_usd = composite_score (raw integer)
```

**Difficulty:** Low (just SQL + Python aggregation).

**Poll interval:** Daily (after market close).

---

## Implementation Priority + Batch Summary

| # | Collector | Source | Difficulty | Batch |
|---|-----------|--------|-----------|-------|
| 1 | Unusual Options (Yahoo) | Yahoo Finance | Low-Medium | B1 |
| 2 | Short Interest (ShortSqueeze/Finra) | ShortSqueeze.com | Low | B1 |
| 3 | EDGAR Keyword Alert (8-K) | SEC EDGAR RSS | Medium | B1 |
| 4 | News Sentiment (NewsAPI/MarketWatch) | NewsAPI.org | Medium | B2 |
| 5 | Open Insider Tracker | openinsider.com | Low-Medium | B2 |
| 6 | Dark Pool Volume (FINRA ATS) | FINRA weekly CSV | Medium | B3 |
| 7 | Gamma Exposure (GEX) | Yahoo Finance chain | High | B3 |
| 8 | Composite Score | Existing DB signals | Low | B3 (or standalone) |

---

## Recommended Build Order

1. **B1.2 Short Interest** — shortest time to signal, high impact (short squeeze candidates)
2. **B1.1 Unusual Options** — immediate market signal, uses existing Yahoo pattern
3. **B1.3 EDGAR Keyword** — leverages existing EDGAR infrastructure (already have parser)
4. **B2.5 Open Insider** — easy scrape, fresh insider data, no API key needed
5. **B2.1 News Sentiment** — quick to add, useful context
6. **B3.7 GEX** — most complex but powerful for intraday signals
7. **B3.6 Dark Pool** — weekly data, low priority
8. **Composite Score** — always last, built on everything else

---

## Database Changes

**No schema changes needed** — all new signals fit existing `smart_money_signals` table.

New `signal_type` values to add to docs:
- `options_unusual_call`, `options_unusual_put`
- `options_sweep_call`, `options_sweep_put`
- `short_squeeze_candidate`, `short_cover_detected`
- `buyback_announced`, `going_concern`, `delisting_warning`
- `earnings_beat`, `earnings_miss`, `news_bullish`, `news_bearish`
- `institution_adding`, `institution_reducing`
- `darkpool_surge`
- `gamma_squeeze_positive`, `gamma_squeeze_negative`
- `composite_buy`, `composite_sell`

---

## Environment Variables Needed

```
NEWS_API_KEY=        # NewsAPI.org free tier (25/day)
SHORTSQUEEZE_PROXY=  # Optional: proxy if ShortSqueeze blocks VPS IP
```

---

## Poll Intervals (updated)

| Collector | Interval | Notes |
|-----------|----------|-------|
| options_unusual | 900s (15min) | Market hours only |
| shortsqueeze | 86400s (daily) | Weekly data |
| edgar_kw | 1800s (30min) | 8-K batches |
| news_sentiment | 1800s (30min) | NewsAPI rate limit |
| openinsider | 3600s (hourly) | New insider prints |
| darkpool | 604800s (weekly) | FINRA publishes Friday |
| gex | 300s (5min) | Market hours only |
| composite_score | 86400s (daily) | EOD aggregation |