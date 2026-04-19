import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

DB_URL = f"sqlite:///{DATA_DIR / 'smartflow.db'}"

# SEC EDGAR
SEC_EDGAR_EMAIL = os.getenv("SEC_EDGAR_EMAIL", "")
SEC_EDGAR_BASE_URL = "https://efts.sec.gov/LATEST"
SEC_EDGAR_FILINGS_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
SEC_EDGAR_RATE_LIMIT = 10  # max requests per second

# Whale Alert
WHALE_ALERT_API_KEY = os.getenv("WHALE_ALERT_API_KEY", "")
WHALE_ALERT_BASE_URL = "https://api.whale-alert.io/v1"

# Etherscan
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
ETHERSCAN_BASE_URL = "https://api.etherscan.io/api"

# CoinGlass
COINGLASS_API_KEY = os.getenv("COINGLASS_API_KEY", "")

# Arkham Intelligence (free API key at https://app.arkhamintelligence.com)
ARKHAM_API_KEY = os.getenv("ARKHAM_API_KEY", "")

# Unusual Whales
UNUSUAL_WHALES_API_KEY = os.getenv("UNUSUAL_WHALES_API_KEY", "")

# Telegram Alerts
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "")

# Collectors that are permanently disabled (dead APIs, broken URLs)
# Add/remove names here — scheduler will skip these entirely.
DISABLED_COLLECTORS = {
    "dex_whale",         # The Graph hosted service shut down 2024, DNS → error.thegraph.com
    "hkex_northbound",   # www3.hkexnews.hk/schin/SC/NorthboundTradingData.aspx → 404 (HKEX decomm)
    "congress",          # QuiverQuant API 401 since 2026-04-17 — free tier revoked
    "whale_alert",       # No free tier
    "arkham_labels",     # Requires credit card
}

# Circuit breaker: after this many consecutive failures, back off to CIRCUIT_BREAKER_BACKOFF
CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_BREAKER_BACKOFF = 14400  # 4 hours — collector stays at this interval until manually reset

# Hard wall-clock timeout per collector (seconds). If a collector run exceeds this,
# it is abandoned and counted as a failure toward the circuit breaker.
# Python threads cannot be forcibly killed — the thread may linger, but the scheduler
# moves on and the circuit breaker handles repeated hangs.
COLLECTOR_TIMEOUTS = {
    "hkex_ccass":     900,   # 15 min — 24+ stocks × Playwright/ASP.NET scraping
    "hkex_dealings":  600,   # 10 min — 10 stocks × Playwright
    "sec_13f":        600,   # 10 min — large XML parse
    "sec_form4":      120,   # 2 min
    "sec_form144":    120,
    "sec_13d":        120,
    "congress":       60,
    "coinglass_whale": 30,
    "coinglass_oi":   30,
    "hkex_director":  120,
    "hkex_northbound": 60,
    "sfc_short":      120,
    "nq_si":          60,
    "dex_whale":      30,
    "default":        180,   # fallback for any unlisted collector
}

# Scheduler intervals (seconds)
POLL_INTERVALS = {
    "sec_form4": 300,       # 5 min
    "sec_13f": 86400,       # daily (quarterly data)
    "sec_13d": 3600,        # hourly
    "sec_form144": 3600,    # hourly (Form 144 pre-sale notices)
    "congress": 3600,       # hourly
    "coinglass_whale": 60,  # 1 min
    "coinglass_oi": 3600,   # hourly
    "dex_whale": 60,        # 1 min (Uniswap V3 large swaps)
    "whale_alert": 300,     # 5 min (free tier: 10 req/min)
    "arkham_labels": 3600,  # hourly (API rate limited)
    "hkex_director": 3600,
    "hkex_dealings": 3600,   # director buy/sell (T+3 delay)
    "hkex_ccass": 86400,    # daily
    "hkex_northbound": 300,  # 5 min during HK market hours
    "sfc_short": 86400,       # weekly (published Fridays)
    "hkex_shareholder": 3600,
    "crypto_exchange": 3600,
    "options_unusual": 300,
    "options_darkpool": 86400,
    "nq_si": 86400,   # daily (FINRA publishes bi-monthly, cache checked on each run)
}
